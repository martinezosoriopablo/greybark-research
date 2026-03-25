# -*- coding: utf-8 -*-
"""
Greybark Research - Council Preflight Validator
=================================================

Valida completitud, frescura y calidad de los datos antes de
ejecutar una sesión del AI Council.

Chequeos:
1. Módulos cuantitativos: error/OK, frescura, truncamiento, stubs
2. Disponibilidad por agente del panel
3. Reportes diarios: cantidad, antigüedad, tamaño
4. Veredicto global: GO / CAUTION / NO_GO

Uso standalone:
    python council_preflight_validator.py -t macro
    python council_preflight_validator.py -t macro --json
    python council_preflight_validator.py -t macro --strict

Uso programático:
    from council_preflight_validator import CouncilPreflightValidator
    validator = CouncilPreflightValidator()
    preflight = validator.validate(quant_data, daily_summary, daily_context)
    validator.print_report(preflight)
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Criticidad por módulo
CRITICAL_MODULES = {'regime', 'macro_usa', 'chile'}
IMPORTANT_MODULES = {'inflation', 'rates', 'risk', 'china'}
OPTIONAL_MODULES = {'chile_extended', 'international', 'breadth'}

ALL_MODULES = CRITICAL_MODULES | IMPORTANT_MODULES | OPTIONAL_MODULES

# Mapeo agente → módulos requeridos
AGENT_MODULE_MAP = {
    'macro':  ['regime', 'macro_usa', 'inflation', 'chile', 'china'],
    'rv':     ['regime', 'breadth', 'international', 'macro_usa'],
    'rf':     ['regime', 'rates', 'inflation', 'chile', 'chile_extended', 'international'],
    'riesgo': ['regime', 'risk', 'china'],
    'geo':    ['regime'],  # + daily_context (se valida aparte)
}

# Umbrales de frescura (horas)
FRESHNESS_THRESHOLDS = {
    'regime': 24, 'macro_usa': 24, 'chile': 24,
    'inflation': 24, 'rates': 24, 'risk': 24,
    'china': 168, 'chile_extended': 168, 'international': 168,
    'breadth': 24,
}

# Límites de tamaño (chars del JSON serializado)
TRUNCATION_LIMIT = 8000
DAILY_CONTEXT_LIMIT = 4000

# Stubs conocidos
KNOWN_STUBS = {
    'breadth': lambda d: set(d.keys()) == {'signal'} and d.get('signal') == 'OK',
}

# Reportes diarios
MIN_REPORTS = 3
IDEAL_REPORTS = 10
MAX_REPORT_AGE_DAYS = 3


# ---------------------------------------------------------------------------
# Dataclasses para resultados
# ---------------------------------------------------------------------------

@dataclass
class ModuleStatus:
    name: str
    status: str  # GREEN, YELLOW, RED
    has_data: bool
    has_error: bool
    error_msg: str = ''
    is_stub: bool = False
    size_bytes: int = 0
    size_str: str = ''
    freshness_hours: Optional[float] = None
    freshness_str: str = ''
    truncation_risk: bool = False
    criticality: str = ''  # CRITICAL, IMPORTANT, OPTIONAL
    detail: str = ''

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AgentStatus:
    name: str
    required_modules: List[str] = field(default_factory=list)
    available_modules: List[str] = field(default_factory=list)
    missing_modules: List[str] = field(default_factory=list)
    available_count: int = 0
    required_count: int = 0
    pct: float = 0.0
    status: str = 'GREEN'  # GREEN, YELLOW, RED

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DailyReportsStatus:
    reports_count: int = 0
    last_report_date: str = ''
    age_days: Optional[float] = None
    context_size: int = 0
    context_truncation_risk: bool = False
    status: str = 'GREEN'
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PreflightResult:
    timestamp: str = ''
    overall_verdict: str = 'GO'  # GO, CAUTION, NO_GO
    modules: Dict[str, ModuleStatus] = field(default_factory=dict)
    agents: Dict[str, AgentStatus] = field(default_factory=dict)
    daily_reports: DailyReportsStatus = field(default_factory=DailyReportsStatus)
    issues: List[str] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)  # GREEN/YELLOW/RED counts

    def to_dict(self) -> Dict:
        d = {
            'timestamp': self.timestamp,
            'overall_verdict': self.overall_verdict,
            'modules': {k: v.to_dict() for k, v in self.modules.items()},
            'agents': {k: v.to_dict() for k, v in self.agents.items()},
            'daily_reports': self.daily_reports.to_dict(),
            'issues': self.issues,
            'summary': self.summary,
        }
        return d


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class CouncilPreflightValidator:
    """Ejecuta pre-flight checks antes de una sesión del AI Council."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    # ----- Módulos cuantitativos -----

    def _check_module(self, name: str, data: Any) -> ModuleStatus:
        """Evalúa un módulo cuantitativo individual."""
        ms = ModuleStatus(name=name, has_data=False, has_error=False, status='RED')

        # Criticidad
        if name in CRITICAL_MODULES:
            ms.criticality = 'CRITICAL'
        elif name in IMPORTANT_MODULES:
            ms.criticality = 'IMPORTANT'
        else:
            ms.criticality = 'OPTIONAL'

        # Sin datos
        if data is None:
            ms.has_error = True
            ms.error_msg = 'Module missing (None)'
            ms.detail = 'No data returned'
            ms.status = 'RED'
            return ms

        # Error explícito
        if isinstance(data, dict) and 'error' in data and len(data) == 1:
            ms.has_error = True
            ms.error_msg = str(data['error'])
            ms.detail = f'ERROR: {ms.error_msg}'
            ms.status = 'RED'
            return ms

        ms.has_data = True

        # Tamaño
        serialized = json.dumps(data, default=str, ensure_ascii=False)
        ms.size_bytes = len(serialized)
        if ms.size_bytes < 1024:
            ms.size_str = f'{ms.size_bytes}B'
        else:
            ms.size_str = f'{ms.size_bytes / 1024:.1f}KB'

        # Riesgo de truncamiento
        if ms.size_bytes > TRUNCATION_LIMIT:
            ms.truncation_risk = True

        # Stub conocido
        if name in KNOWN_STUBS and isinstance(data, dict):
            if KNOWN_STUBS[name](data):
                ms.is_stub = True
                ms.detail = 'STUB (solo retorna signal OK)'
                ms.status = 'YELLOW'
                return ms

        # Frescura: buscar timestamp / as_of en los datos
        freshness = self._extract_freshness(data)
        if freshness is not None:
            ms.freshness_hours = freshness
            threshold = FRESHNESS_THRESHOLDS.get(name, 24)
            if freshness <= threshold:
                ms.freshness_str = f'Fresco ({freshness:.1f}h)'
            else:
                ms.freshness_str = f'Stale ({freshness:.0f}h, umbral={threshold}h)'
                ms.status = 'YELLOW'
                ms.detail = ms.freshness_str
                return ms
        else:
            ms.freshness_str = 'Sin timestamp'

        # Si pasó todo, es GREEN
        if ms.truncation_risk:
            ms.status = 'YELLOW'
            ms.detail = f'Truncation risk ({ms.size_str} > {TRUNCATION_LIMIT / 1024:.0f}KB)'
        else:
            ms.status = 'GREEN'
            ms.detail = f'{ms.freshness_str} | {ms.size_str}'

        return ms

    def _extract_freshness(self, data: Any) -> Optional[float]:
        """Intenta extraer horas desde el último update del dato."""
        if not isinstance(data, dict):
            return None

        now = datetime.now()
        for key in ('as_of', 'timestamp', 'last_updated', 'date', 'as_of_date'):
            val = data.get(key)
            if val is None:
                # Buscar un nivel más profundo
                for sub in data.values():
                    if isinstance(sub, dict) and key in sub:
                        val = sub[key]
                        break
            if val is not None:
                try:
                    if isinstance(val, str):
                        # Intentar varios formatos
                        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                                    '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                            try:
                                dt = datetime.strptime(val[:26], fmt)
                                delta = (now - dt).total_seconds() / 3600
                                return max(0, delta)
                            except ValueError:
                                continue
                    elif isinstance(val, (int, float)):
                        # Epoch seconds
                        dt = datetime.fromtimestamp(val)
                        delta = (now - dt).total_seconds() / 3600
                        return max(0, delta)
                except Exception:
                    continue
        return None

    # ----- Disponibilidad por agente -----

    def _check_agent(self, agent: str, module_statuses: Dict[str, ModuleStatus]) -> AgentStatus:
        """Evalúa disponibilidad de datos para un agente."""
        required = AGENT_MODULE_MAP.get(agent, [])
        available = [m for m in required if m in module_statuses and module_statuses[m].has_data]
        missing = [m for m in required if m not in available]

        req_count = len(required)
        avail_count = len(available)
        pct = (avail_count / req_count * 100) if req_count > 0 else 100.0

        # Status = peor componente requerido
        if missing:
            worst = 'YELLOW'
            for m in missing:
                ms = module_statuses.get(m)
                if ms and ms.criticality == 'CRITICAL':
                    worst = 'RED'
                    break
            status = worst
        else:
            status = 'GREEN'

        return AgentStatus(
            name=agent,
            required_modules=required,
            available_modules=available,
            missing_modules=missing,
            available_count=avail_count,
            required_count=req_count,
            pct=pct,
            status=status,
        )

    # ----- Reportes diarios -----

    def _check_daily_reports(self, daily_summary: Dict, daily_context: str) -> DailyReportsStatus:
        """Valida cantidad, frescura y tamaño de los reportes diarios."""
        ds = DailyReportsStatus()
        ds.reports_count = daily_summary.get('reports_count', 0)
        ds.context_size = len(daily_context) if daily_context else 0
        ds.context_truncation_risk = ds.context_size > DAILY_CONTEXT_LIMIT

        # Fecha del último reporte
        ultimos = daily_summary.get('ultimos_reportes', [])
        if ultimos:
            ds.last_report_date = ultimos[-1].get('date', '')
        else:
            period = daily_summary.get('period', '')
            if ' a ' in period:
                ds.last_report_date = period.split(' a ')[-1]

        # Antigüedad
        if ds.last_report_date:
            try:
                last_dt = datetime.strptime(ds.last_report_date, '%Y-%m-%d')
                ds.age_days = (datetime.now() - last_dt).total_seconds() / 86400
            except ValueError:
                ds.age_days = None

        # Evaluar status
        issues = []
        status = 'GREEN'

        if ds.reports_count == 0:
            status = 'RED'
            issues.append('Sin reportes diarios')
        elif ds.reports_count < MIN_REPORTS:
            status = 'YELLOW'
            issues.append(f'Pocos reportes ({ds.reports_count} < {MIN_REPORTS})')
        elif ds.reports_count < IDEAL_REPORTS:
            issues.append(f'Reportes bajo ideal ({ds.reports_count} < {IDEAL_REPORTS})')

        if ds.age_days is not None and ds.age_days > MAX_REPORT_AGE_DAYS:
            status = 'YELLOW' if status != 'RED' else 'RED'
            issues.append(f'Último reporte hace {ds.age_days:.0f} días (max {MAX_REPORT_AGE_DAYS})')

        if ds.context_truncation_risk:
            issues.append(f'Contexto excede {DAILY_CONTEXT_LIMIT} chars ({ds.context_size})')

        ds.status = status
        ds.issues = issues
        return ds

    # ----- Validación principal -----

    def validate(
        self,
        quant_data: Dict[str, Any],
        daily_summary: Dict[str, Any],
        daily_context: str = ''
    ) -> PreflightResult:
        """
        Ejecuta todos los chequeos pre-flight.

        Args:
            quant_data: Dict de datos cuantitativos (output de collect_quantitative_data)
            daily_summary: Dict resumen de reportes diarios
            daily_context: Texto formateado de reportes para prompts

        Returns:
            PreflightResult con todos los resultados
        """
        result = PreflightResult()
        result.timestamp = datetime.now().isoformat()

        # 1. Chequear cada módulo
        for mod_name in sorted(ALL_MODULES):
            mod_data = quant_data.get(mod_name)
            result.modules[mod_name] = self._check_module(mod_name, mod_data)

        # 2. Chequear cada agente
        for agent in AGENT_MODULE_MAP:
            result.agents[agent] = self._check_agent(agent, result.modules)

        # 3. Chequear reportes diarios
        result.daily_reports = self._check_daily_reports(daily_summary, daily_context)

        # 4. Conteo resumen
        counts = {'GREEN': 0, 'YELLOW': 0, 'RED': 0}
        for ms in result.modules.values():
            counts[ms.status] = counts.get(ms.status, 0) + 1
        result.summary = counts

        # 5. Determinar veredicto global + issues
        issues = []
        verdict = 'GO'

        for ms in result.modules.values():
            if ms.status == 'RED':
                if ms.criticality == 'CRITICAL':
                    verdict = 'NO_GO'
                    issues.append(f'{ms.name} CRITICAL falló: {ms.error_msg or ms.detail}')
                else:
                    if verdict != 'NO_GO':
                        verdict = 'CAUTION'
                    issues.append(f'{ms.name} falló ({ms.criticality.lower()}): {ms.error_msg or ms.detail}')
            elif ms.status == 'YELLOW':
                if verdict == 'GO':
                    verdict = 'CAUTION'
                issues.append(f'{ms.name}: {ms.detail}')

        if result.daily_reports.status == 'RED':
            if verdict != 'NO_GO':
                verdict = 'CAUTION'
            issues.extend(result.daily_reports.issues)
        elif result.daily_reports.issues:
            if verdict == 'GO':
                verdict = 'CAUTION'
            issues.extend(result.daily_reports.issues)

        result.overall_verdict = verdict
        result.issues = issues

        return result

    # ----- Output formateado -----

    def print_report(self, result: PreflightResult):
        """Imprime el reporte pre-flight formateado en terminal."""
        g = result.summary.get('GREEN', 0)
        y = result.summary.get('YELLOW', 0)
        r = result.summary.get('RED', 0)

        print()
        print('=' * 62)
        print('AI COUNCIL - PREFLIGHT CHECK')
        print('=' * 62)

        # --- Módulos ---
        print(f'\n--- MODULOS CUANTITATIVOS ({g}/{g+y+r} GREEN, {y} YELLOW, {r} RED) ---\n')
        for name in sorted(result.modules.keys()):
            ms = result.modules[name]
            tag = f'[{ms.status:6s}]'
            if ms.has_error:
                info = f'ERROR: {ms.error_msg[:50]}'
            elif ms.is_stub:
                info = ms.detail
            else:
                parts = []
                if ms.freshness_str:
                    parts.append(ms.freshness_str)
                parts.append(ms.size_str)
                info = ' | '.join(parts)
            print(f'  {tag}  {name:20s} | {info}')

        # --- Reportes ---
        dr = result.daily_reports
        print(f'\n--- REPORTES DIARIOS ---\n')
        parts = [f'Reportes: {dr.reports_count}']
        if dr.last_report_date:
            parts.append(f'Ultimo: {dr.last_report_date}')
        parts.append(f'[{dr.status}]')
        print(f'  {" | ".join(parts)}')
        for issue in dr.issues:
            print(f'    - {issue}')

        # --- Agentes ---
        print(f'\n--- DISPONIBILIDAD POR AGENTE ---\n')
        for agent_name in AGENT_MODULE_MAP:
            ag = result.agents[agent_name]
            pct_str = f'{ag.pct:5.0f}%'
            missing_str = ''
            if ag.missing_modules:
                missing_str = f' falta: {", ".join(ag.missing_modules)}'
            print(f'  {agent_name:8s} | {ag.available_count}/{ag.required_count} ({pct_str}) | [{ag.status:6s}]{missing_str}')

        # --- Veredicto ---
        print()
        print('=' * 62)
        print(f'VEREDICTO: {result.overall_verdict}')
        if result.issues:
            for issue in result.issues:
                print(f'  - {issue}')
        print('=' * 62)
        print()


# ---------------------------------------------------------------------------
# CLI standalone
# ---------------------------------------------------------------------------

def main():
    """Ejecuta el preflight validator como script independiente."""
    parser = argparse.ArgumentParser(
        description='AI Council Preflight Validator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Ejemplos:\n'
               '  python council_preflight_validator.py -t macro\n'
               '  python council_preflight_validator.py -t macro --json\n'
               '  python council_preflight_validator.py -t macro --strict\n'
    )
    parser.add_argument('--type', '-t', default='macro',
                        choices=['macro', 'rv', 'rf', 'aa'],
                        help='Tipo de reporte (default: macro)')
    parser.add_argument('--json', action='store_true',
                        help='Output en formato JSON')
    parser.add_argument('--strict', action='store_true',
                        help='Exit code: 0=GO, 1=CAUTION, 2=NO_GO')

    args = parser.parse_args()

    # Importar collector
    sys.path.insert(0, str(Path(__file__).parent))

    from council_data_collector import CouncilDataCollector

    collector = CouncilDataCollector(verbose=not args.json)
    quant_data = collector.collect_quantitative_data()
    daily_summary = collector.collect_daily_reports_summary(days=30)
    daily_context = collector.daily_parser.format_for_council(daily_summary)

    validator = CouncilPreflightValidator(verbose=not args.json)
    result = validator.validate(quant_data, daily_summary, daily_context)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        validator.print_report(result)

    if args.strict:
        code_map = {'GO': 0, 'CAUTION': 1, 'NO_GO': 2}
        sys.exit(code_map.get(result.overall_verdict, 2))


if __name__ == '__main__':
    main()

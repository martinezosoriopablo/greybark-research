# -*- coding: utf-8 -*-
"""
Greybark Research - Pipeline Mensual Unificado
===============================================

Ejecuta el pipeline completo para generar TODOS los reportes mensuales:
1. Recopila datos cuantitativos (macro + equity)
2. Procesa noticias (daily reports + DF + WSJ)
3. Analiza research externo
4. Ejecuta AI Council (una sesión)
5. Genera reportes (Macro, RV, RF, AA)

Uso:
    python run_monthly.py                    # Pipeline completo
    python run_monthly.py --dry-run          # Solo recopilar, no council
    python run_monthly.py --skip-collect     # Usar datos ya recopilados
    python run_monthly.py --reports macro rv # Solo algunos reportes
    python run_monthly.py --no-confirm       # Sin pausa de confirmación
"""

import os
import sys
import json
import argparse
import time
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Fix Windows console encoding
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8:replace')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Agregar paths
sys.path.insert(0, str(Path(__file__).parent))
LIB_PATH = Path(__file__).parent.parent / "02_greybark_library"
sys.path.insert(0, str(LIB_PATH))


# =========================================================================
# CONFIGURACIÓN
# =========================================================================

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
COUNCIL_DIR = OUTPUT_DIR / "council"
REPORTS_DIR = OUTPUT_DIR / "reports"
EQUITY_DIR = OUTPUT_DIR / "equity_data"
RF_DIR = OUTPUT_DIR / "rf_data"
FORECAST_DIR = OUTPUT_DIR / "forecasts"

VALID_REPORTS = ['macro', 'rv', 'rf', 'aa']

WSJ_DATA_PATH = Path(os.environ.get('WSJ_DATA_PATH', str(Path.home() / "OneDrive/Documentos/proyectos/wsj_data")))


# =========================================================================
# PIPELINE
# =========================================================================

class MonthlyPipeline:
    """Pipeline mensual unificado de Greybark Research."""

    def __init__(
        self,
        dry_run: bool = False,
        skip_collect: bool = False,
        no_confirm: bool = False,
        reports: List[str] = None,
        open_browser: bool = False,
    ):
        self.dry_run = dry_run
        self.skip_collect = skip_collect
        self.no_confirm = no_confirm
        self.reports = reports or VALID_REPORTS
        self.open_browser = open_browser
        self.date_str = datetime.now().strftime('%Y-%m-%d')
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # State
        self.data = {}
        self.council_result = None
        self.report_results = []
        self.errors = []
        self.start_time = None

        # Ensure output dirs exist
        for d in [COUNCIL_DIR, REPORTS_DIR, EQUITY_DIR, RF_DIR, FORECAST_DIR]:
            d.mkdir(parents=True, exist_ok=True)

    def _print(self, msg: str):
        print(msg)

    def _print_header(self, phase: str, title: str):
        print(f"\n{'=' * 70}")
        print(f"[{phase}] {title}")
        print(f"{'=' * 70}")

    def _print_step(self, msg: str, indent: int = 1):
        prefix = "  " * indent
        print(f"{prefix}-> {msg}")

    def _print_ok(self, msg: str, indent: int = 2):
        prefix = "  " * indent
        print(f"{prefix}[OK] {msg}")

    def _print_err(self, msg: str, indent: int = 2):
        prefix = "  " * indent
        print(f"{prefix}[ERR] {msg}")

    # =====================================================================
    # FASE 1: RECOPILACIÓN DE DATOS
    # =====================================================================

    def collect_all_data(self) -> Dict[str, Any]:
        """Recopila TODOS los datos necesarios para el pipeline."""
        self._print_header("FASE 1", "RECOPILACIÓN DE ANTECEDENTES")
        phase_start = time.time()

        data = {}

        # 1a. Datos macro cuantitativos
        self._print_step("Datos cuantitativos macro (10 módulos)...")
        try:
            from council_data_collector import CouncilDataCollector
            collector = CouncilDataCollector(verbose=True)
            data['macro_quant'] = collector.collect_quantitative_data()
            modules_ok = sum(1 for v in data['macro_quant'].values()
                           if isinstance(v, dict) and 'error' not in v)
            self._print_ok(f"Macro: {modules_ok}/{len(data['macro_quant'])} módulos OK")
        except Exception as e:
            data['macro_quant'] = {'error': str(e)}
            self._print_err(f"Macro quant: {e}")
            self.errors.append(f"Fase 1 - Macro quant: {e}")

        # 1b. Datos equity
        self._print_step("Datos equity (10 módulos)...")
        try:
            from equity_data_collector import EquityDataCollector
            eq_collector = EquityDataCollector(verbose=True)
            data['equity'] = eq_collector.collect_all()
            eq_path = eq_collector.save(data['equity'])
            meta = data['equity'].get('metadata', {})
            self._print_ok(f"Equity: {meta.get('modules_ok', '?')}/{meta.get('modules_total', '?')} OK "
                          f"({meta.get('elapsed_seconds', '?')}s) -> {eq_path}")
        except Exception as e:
            data['equity'] = {'error': str(e)}
            self._print_err(f"Equity: {e}")
            self.errors.append(f"Fase 1 - Equity: {e}")

        # 1c. Datos renta fija
        self._print_step("Datos renta fija (9 módulos)...")
        try:
            from rf_data_collector import RFDataCollector
            rf_collector = RFDataCollector(verbose=True)
            data['rf'] = rf_collector.collect_all()
            rf_path = rf_collector.save(data['rf'])
            rf_meta = data['rf'].get('metadata', {})
            self._print_ok(f"RF: {rf_meta.get('modules_ok', '?')}/9 OK "
                          f"({rf_meta.get('elapsed_seconds', '?')}s) -> {rf_path}")
        except Exception as e:
            data['rf'] = {'error': str(e)}
            self._print_err(f"RF: {e}")
            self.errors.append(f"Fase 1 - RF: {e}")

        # 1d. Forecast engine
        self._print_step("Pronósticos cuantitativos (forecast engine)...")
        try:
            from forecast_engine import ForecastEngine
            fc_engine = ForecastEngine(verbose=True)
            data['forecasts'] = fc_engine.generate_all(
                equity_data=data.get('equity', {}),
                rf_data=data.get('rf', {}),
                quant_data=data.get('macro_quant', {}),
            )
            fc_path = fc_engine.save(data['forecasts'])
            fc_meta = data['forecasts'].get('metadata', {})
            self._print_ok(f"Forecasts: {fc_meta.get('modules_ok', '?')}/4 módulos OK "
                          f"({fc_meta.get('elapsed_seconds', '?')}s) -> {fc_path}")
        except Exception as e:
            data['forecasts'] = {'error': str(e)}
            self._print_err(f"Forecasts: {e}")
            self.errors.append(f"Fase 1 - Forecasts: {e}")

        # 1e. Daily intelligence digest
        self._print_step("Inteligencia diaria (30 días de reportes)...")
        try:
            if 'collector' not in dir():
                from council_data_collector import CouncilDataCollector
                collector = CouncilDataCollector(verbose=True)

            data['daily_summary'] = collector.collect_daily_reports_summary(30)
            data['intelligence'] = collector.collect_intelligence_digest()
            n_themes = len(data['intelligence'].get('themes', {}))
            n_ideas = len(data['intelligence'].get('tactical_ideas', []))
            self._print_ok(f"Intelligence: {n_themes} temas, {n_ideas} ideas tácticas")
        except Exception as e:
            data['daily_summary'] = {'error': str(e)}
            data['intelligence'] = {'error': str(e)}
            self._print_err(f"Intelligence: {e}")
            self.errors.append(f"Fase 1 - Intelligence: {e}")

        # 1f. WSJ summaries (si existen)
        self._print_step("WSJ summaries...")
        data['wsj'] = self._collect_wsj_summaries()
        if data['wsj'].get('available'):
            self._print_ok(f"WSJ: {data['wsj'].get('files_read', 0)} resúmenes leídos")
        else:
            self._print_step("WSJ: no disponible (omitido)", indent=2)

        # 1g. External research
        self._print_step("Research externo...")
        try:
            data['research'] = collector.collect_external_research()
            if data['research']:
                self._print_ok(f"Research: {len(data['research'])} chars")
            else:
                self._print_step("Research: sin archivos en input/research/", indent=2)
        except Exception as e:
            data['research'] = ''
            self._print_err(f"Research: {e}")
            self.errors.append(f"Fase 1 - Research: {e}")

        # 1h. User directives
        self._print_step("User directives...")
        try:
            data['directives'] = collector.collect_user_directives()
        except Exception as e:
            data['directives'] = ''
            self._print_err(f"Directives: {e}")

        elapsed = time.time() - phase_start
        self._print(f"\n  Fase 1 completada en {elapsed:.1f}s")

        return data

    def _collect_wsj_summaries(self, days: int = 7) -> Dict[str, Any]:
        """Lee resúmenes WSJ si están disponibles."""
        if not WSJ_DATA_PATH.exists():
            return {'available': False, 'reason': 'path not found'}

        try:
            files = sorted(WSJ_DATA_PATH.glob("*.txt"), reverse=True)
            if not files:
                return {'available': False, 'reason': 'no files'}

            recent = files[:days]
            summaries = []
            for f in recent:
                try:
                    text = f.read_text(encoding='utf-8')
                    summaries.append({
                        'file': f.name,
                        'content': text[:3000],
                        'length': len(text),
                    })
                except Exception:
                    continue

            if not summaries:
                return {'available': False, 'reason': 'no readable files'}

            return {
                'available': True,
                'files_read': len(summaries),
                'total_chars': sum(s['length'] for s in summaries),
                'latest': summaries[0]['content'][:2000] if summaries else '',
            }
        except Exception as e:
            return {'available': False, 'reason': str(e)}

    def _load_existing_data(self) -> Dict[str, Any]:
        """Carga datos ya recopilados desde archivos JSON."""
        self._print_header("FASE 1", "CARGANDO DATOS EXISTENTES (--skip-collect)")
        data = {}

        # Buscar equity data más reciente
        eq_files = sorted(EQUITY_DIR.glob("equity_data_*.json"), reverse=True)
        if eq_files:
            with open(eq_files[0], 'r', encoding='utf-8') as f:
                data['equity'] = json.load(f)
            self._print_ok(f"Equity data: {eq_files[0].name}")
        else:
            data['equity'] = {'error': 'No equity data found'}
            self._print_err("No equity data found in output/equity_data/")

        # Buscar council input más reciente (tiene macro_quant dentro)
        ci_files = sorted(COUNCIL_DIR.glob("council_input_*.json"), reverse=True)
        if ci_files:
            with open(ci_files[0], 'r', encoding='utf-8') as f:
                council_input = json.load(f)
            data['macro_quant'] = council_input.get('quantitative', {})
            data['daily_summary'] = council_input.get('daily_summary', {})
            data['intelligence'] = council_input.get('intelligence', {})
            data['research'] = council_input.get('external_research', '')
            data['directives'] = council_input.get('user_directives', '')
            self._print_ok(f"Council input: {ci_files[0].name}")
        else:
            # Run fresh collection for macro data since no cached input
            self._print_step("No council input cache found, collecting macro data fresh...")
            try:
                from council_data_collector import CouncilDataCollector
                collector = CouncilDataCollector(verbose=True)
                data['macro_quant'] = collector.collect_quantitative_data()
                data['daily_summary'] = collector.collect_daily_reports_summary(30)
                data['intelligence'] = collector.collect_intelligence_digest()
                data['research'] = collector.collect_external_research()
                data['directives'] = collector.collect_user_directives()
            except Exception as e:
                data['macro_quant'] = {'error': str(e)}
                self._print_err(f"Macro collection fallback: {e}")

        # Buscar RF data más reciente
        rf_files = sorted(RF_DIR.glob("rf_data_*.json"), reverse=True)
        if rf_files:
            with open(rf_files[0], 'r', encoding='utf-8') as f:
                data['rf'] = json.load(f)
            self._print_ok(f"RF data: {rf_files[0].name}")
        else:
            data['rf'] = {'error': 'No RF data found'}
            self._print_err("No RF data found in output/rf_data/")

        # Buscar forecast data más reciente
        fc_files = sorted(FORECAST_DIR.glob("forecast_*.json"), reverse=True)
        if fc_files:
            with open(fc_files[0], 'r', encoding='utf-8') as f:
                data['forecasts'] = json.load(f)
            self._print_ok(f"Forecast data: {fc_files[0].name}")
        else:
            data['forecasts'] = {'error': 'No forecast data found'}
            self._print_step("No forecast data found (will use defaults)", indent=2)

        data['wsj'] = self._collect_wsj_summaries()
        return data

    # =====================================================================
    # FASE 2: PREFLIGHT CHECK
    # =====================================================================

    def preflight_check(self, data: Dict[str, Any]) -> str:
        """Muestra resumen de datos y espera confirmación."""
        self._print_header("FASE 2", "PREFLIGHT CHECK")

        # --- Módulos macro ---
        macro_quant = data.get('macro_quant', {})
        if isinstance(macro_quant, dict) and 'error' not in macro_quant:
            macro_ok = sum(1 for v in macro_quant.values()
                         if isinstance(v, dict) and 'error' not in v)
            macro_total = len(macro_quant)
            macro_errs = [k for k, v in macro_quant.items()
                         if isinstance(v, dict) and 'error' in v]
        else:
            macro_ok, macro_total = 0, 0
            macro_errs = ['ALL']

        # --- Módulos equity ---
        equity = data.get('equity', {})
        if isinstance(equity, dict) and 'error' not in equity:
            eq_meta = equity.get('metadata', {})
            eq_ok = eq_meta.get('modules_ok', 0)
            eq_total = eq_meta.get('modules_total', 0)
        else:
            eq_ok, eq_total = 0, 0

        # --- Módulos RF ---
        rf = data.get('rf', {})
        if isinstance(rf, dict) and 'error' not in rf:
            rf_meta = rf.get('metadata', {})
            rf_ok = rf_meta.get('modules_ok', 0)
            rf_total = 9
        else:
            rf_ok, rf_total = 0, 9

        # --- Intelligence ---
        intel = data.get('intelligence', {})
        intel_ok = isinstance(intel, dict) and 'error' not in intel
        n_themes = len(intel.get('themes', {})) if intel_ok else 0

        # --- Daily reports ---
        daily = data.get('daily_summary', {})
        n_reports = daily.get('reports_count', 0) if isinstance(daily, dict) else 0

        # --- Research ---
        research = data.get('research', '')
        has_research = bool(research and len(research) > 50)

        # --- Directives ---
        directives = data.get('directives', '')
        has_directives = bool(directives and len(directives) > 10)

        # --- Forecasts ---
        fc = data.get('forecasts', {})
        fc_ok = isinstance(fc, dict) and 'error' not in fc
        fc_modules = fc.get('metadata', {}).get('modules_ok', 0) if fc_ok else 0

        # --- WSJ ---
        wsj = data.get('wsj', {})
        has_wsj = wsj.get('available', False)

        # Print summary
        print(f"\n  {'COMPONENTE':<35} {'ESTADO':<12} DETALLE")
        print(f"  {'-' * 70}")
        print(f"  {'Macro cuantitativos':<35} {'OK' if macro_ok > 5 else 'WARN':<12} {macro_ok}/{macro_total} módulos")
        if macro_errs and macro_errs != ['ALL']:
            print(f"  {'  errores:':<35} {'...':<12} {', '.join(macro_errs)}")
        print(f"  {'Equity cuantitativos':<35} {'OK' if eq_ok > 5 else 'WARN':<12} {eq_ok}/{eq_total} módulos")
        print(f"  {'Renta fija cuantitativos':<35} {'OK' if rf_ok > 5 else 'WARN':<12} {rf_ok}/{rf_total} módulos")
        print(f"  {'Forecast engine':<35} {'OK' if fc_modules > 2 else ('WARN' if fc_ok else '---'):<12} {fc_modules}/4 módulos")
        print(f"  {'Intelligence Digest':<35} {'OK' if intel_ok else 'ERR':<12} {n_themes} temas")
        print(f"  {'Reportes diarios':<35} {'OK' if n_reports > 5 else 'WARN':<12} {n_reports} reportes")
        print(f"  {'Research externo':<35} {'OK' if has_research else '---':<12} {len(research)} chars")
        print(f"  {'User directives':<35} {'OK' if has_directives else '---':<12} {'sí' if has_directives else 'no'}")
        print(f"  {'WSJ summaries':<35} {'OK' if has_wsj else '---':<12} {'sí' if has_wsj else 'no'}")
        print(f"  {'-' * 70}")

        # --- Preflight formal (usa el validador existente) ---
        verdict = 'GO'
        try:
            from council_preflight_validator import CouncilPreflightValidator
            validator = CouncilPreflightValidator(verbose=False)

            from daily_intelligence_digest import DailyIntelligenceDigest
            dig = DailyIntelligenceDigest(business_days=22)
            daily_context = dig.format_for_council(intel) if intel_ok else ''

            preflight_result = validator.validate(macro_quant, daily, daily_context)
            verdict = preflight_result.overall_verdict
            validator.print_report(preflight_result)
        except Exception as e:
            self._print_err(f"Preflight validator: {e}")
            # Manual verdict
            if macro_ok < 3:
                verdict = 'NO_GO'
            elif macro_ok < 7:
                verdict = 'CAUTION'

        # Print verdict
        verdict_icons = {'GO': '[GO]', 'CAUTION': '[CAUTION]', 'NO_GO': '[NO-GO]'}
        print(f"\n  Veredicto: {verdict_icons.get(verdict, verdict)} {verdict}")

        # Reportes a generar
        print(f"\n  Reportes programados: {', '.join(self.reports)}")

        if self.dry_run:
            print(f"\n  [DRY RUN] Pipeline se detiene aquí.")
            return verdict

        if verdict == 'NO_GO':
            print(f"\n  [NO-GO] Datos críticos faltantes. Pipeline abortado.")
            print(f"  Revise los errores arriba y vuelva a intentar.")
            return verdict

        # Confirmación del usuario
        if not self.no_confirm:
            print(f"\n  Costo estimado del Council: ~$2-3 USD (8 llamadas Claude)")
            try:
                resp = input("\n  Presione ENTER para continuar, o 'q' + ENTER para cancelar: ")
                if resp.strip().lower() in ('q', 'quit', 'n', 'no'):
                    print("\n  Pipeline cancelado por el usuario.")
                    return 'CANCELLED'
            except (KeyboardInterrupt, EOFError):
                print("\n\n  Pipeline cancelado.")
                return 'CANCELLED'

        return verdict

    # =====================================================================
    # FASE 3: AI COUNCIL
    # =====================================================================

    def run_council(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ejecuta una sesión del AI Council con datos consolidados."""
        self._print_header("FASE 3", "AI COUNCIL SESSION")
        phase_start = time.time()

        # Cargar council_result existente si hay uno reciente del día
        existing = sorted(COUNCIL_DIR.glob(f"council_result_{self.date_str}*.json"), reverse=True)
        if existing and self.skip_collect:
            self._print_step(f"Usando council result existente: {existing[0].name}")
            with open(existing[0], 'r', encoding='utf-8') as f:
                return json.load(f)

        try:
            from ai_council_runner import AICouncilRunner
            from council_data_collector import CouncilDataCollector

            # El runner internamente usa CouncilDataCollector.prepare_council_input()
            # que vuelve a recopilar datos. Para evitar doble recopilación,
            # necesitamos inyectar los datos ya recopilados.
            #
            # Approach: crear el runner, reemplazar su data_collector's data,
            # y llamar run_session_sync que internamente llama prepare_council_input.
            #
            # Por ahora, delegamos al runner que re-recopile (es rápido para macro)
            # pero le pasamos equity_data por separado.

            runner = AICouncilRunner(verbose=True)

            # Inyectar equity_data al collector del runner para que lo incluya
            equity_data = data.get('equity', {})
            if equity_data and 'error' not in equity_data:
                runner.data_collector._equity_data = equity_data
                self._print_step("Equity data inyectada al Council input")

            # Inyectar rf_data al collector del runner
            rf_data = data.get('rf', {})
            if rf_data and 'error' not in rf_data:
                runner.data_collector._rf_data = rf_data
                self._print_step("RF data inyectada al Council input")

            # Inyectar forecast_data al collector del runner
            forecast_data = data.get('forecasts', {})
            if forecast_data and 'error' not in forecast_data:
                runner.data_collector._forecast_data = forecast_data
                self._print_step("Forecast data inyectada al Council input")

            print()
            result = runner.run_session_sync(report_type='macro')

            # Guardar resultado
            council_file = COUNCIL_DIR / f"council_result_{self.timestamp}.json"
            runner.save_result(result, str(council_file))

            elapsed = time.time() - phase_start
            api_duration = result.get('metadata', {}).get('duration_seconds', 0)
            self._print(f"\n  Council completado en {elapsed:.1f}s (API: {api_duration:.1f}s)")
            self._print(f"  Resultado: {council_file}")

            return result

        except Exception as e:
            self._print_err(f"Council falló: {e}")
            self.errors.append(f"Fase 3 - Council: {e}")
            import traceback
            traceback.print_exc()
            return None

    # =====================================================================
    # FASE 3.5: REPORT DATA VALIDATION GATE
    # =====================================================================

    def _validate_report_data(self, equity_data: Optional[Dict] = None) -> List[str]:
        """
        Validates that all required data is available for each report.
        Returns list of report types that passed validation.
        Reports that fail are logged and excluded.
        """
        self._print_header("FASE 3.5", "VALIDACIÓN DE DATOS POR REPORTE")

        try:
            from report_data_validator import ReportDataValidator
            from chart_data_provider import ChartDataProvider
        except ImportError as e:
            print(f"  [WARN] Validator not available ({e}), skipping gate")
            return list(self.reports)

        # Build dependencies
        cdp = None
        bbg = None
        bloomberg_path = str(BASE_DIR / "input" / "bloomberg_data.xlsx")

        try:
            cdp = ChartDataProvider()
        except Exception as e:
            print(f"  [WARN] ChartDataProvider init failed: {e}")

        try:
            from bloomberg_reader import BloombergData
            bbg = BloombergData()
        except Exception as e:
            print(f"  [WARN] Bloomberg reader init failed: {e}")

        rf_data = self.data.get('rf', {})
        if isinstance(rf_data, dict) and 'error' in rf_data:
            rf_data = {}

        validator = ReportDataValidator(
            chart_data_provider=cdp,
            bloomberg=bbg,
            rf_data=rf_data,
            equity_data=equity_data or {},
            bloomberg_path=bloomberg_path,
        )

        approved = []
        for report_type in self.reports:
            result = validator.validate(report_type)
            if result.blocked:
                print(f"\n  [BLOCKED] {report_type.upper()}: {result.failed} charts sin datos")
                for r in result.results:
                    if not r.ok and r.error and "(optional" not in r.error:
                        print(f"    - {r.chart_id}: {r.error}")
                self.errors.append(
                    f"Fase 3.5 - {report_type}: BLOCKED ({result.failed} charts sin datos: "
                    f"{', '.join(result.missing)})"
                )
            else:
                print(f"  [OK] {report_type.upper()}: {result.passed}/{result.checked} charts validados")
                approved.append(report_type)

        if len(approved) < len(self.reports):
            blocked = set(self.reports) - set(approved)
            print(f"\n  Reportes bloqueados: {', '.join(blocked)}")
            print(f"  Reportes aprobados:  {', '.join(approved) if approved else 'ninguno'}")

        return approved

    # =====================================================================
    # FASE 4: GENERACIÓN DE REPORTES
    # =====================================================================

    def generate_reports(
        self,
        council_result: Optional[Dict],
        equity_data: Optional[Dict],
        forecast_data: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """Genera todos los reportes solicitados."""
        self._print_header("FASE 4", "GENERACIÓN DE REPORTES")
        results = []

        for report_name in self.reports:
            self._print_step(f"Generando reporte: {report_name.upper()}...")
            start = time.time()

            try:
                output_path = self._generate_single_report(
                    report_name, council_result, equity_data, forecast_data
                )
                elapsed = time.time() - start
                results.append({
                    'report': report_name,
                    'status': 'OK',
                    'path': output_path,
                    'duration': round(elapsed, 1),
                })
                self._print_ok(f"{report_name}: {output_path} ({elapsed:.1f}s)")

            except Exception as e:
                elapsed = time.time() - start
                results.append({
                    'report': report_name,
                    'status': 'ERROR',
                    'error': str(e),
                    'duration': round(elapsed, 1),
                })
                self._print_err(f"{report_name}: {e}")
                self.errors.append(f"Fase 4 - {report_name}: {e}")

        return results

    def _generate_single_report(
        self,
        report_name: str,
        council_result: Optional[Dict],
        equity_data: Optional[Dict],
        forecast_data: Optional[Dict] = None,
    ) -> str:
        """Genera un reporte individual. Retorna path al HTML."""

        if report_name == 'macro':
            from macro_report_renderer import MacroReportRenderer
            quant_data = self.data.get('macro_quant')
            if isinstance(quant_data, dict) and 'error' in quant_data:
                quant_data = None
            renderer = MacroReportRenderer(
                council_result=council_result,
                forecast_data=forecast_data,
                quant_data=quant_data,
                verbose=True,
            )
            return renderer.render()

        elif report_name == 'rv':
            from rv_report_renderer import RVReportRenderer
            renderer = RVReportRenderer(
                council_result=council_result,
                market_data=equity_data,
                forecast_data=forecast_data,
                verbose=True,
            )
            return renderer.render()

        elif report_name == 'rf':
            from rf_report_renderer import RFReportRenderer
            # Get RF quant data
            rf_data = self.data.get('rf')
            if isinstance(rf_data, dict) and 'error' in rf_data:
                rf_data = None
            renderer = RFReportRenderer(
                council_result=council_result,
                market_data=rf_data,
                forecast_data=forecast_data,
                verbose=True,
            )
            return renderer.render()

        elif report_name == 'aa':
            from asset_allocation_renderer import AssetAllocationRenderer
            # Combine equity + RF data for AA report
            aa_data = {}
            rf_data = self.data.get('rf')
            if isinstance(rf_data, dict) and 'error' not in rf_data:
                aa_data.update(rf_data)
            if equity_data and isinstance(equity_data, dict):
                aa_data['equity'] = equity_data
            renderer = AssetAllocationRenderer(
                council_result=council_result,
                market_data=aa_data if aa_data else None,
                forecast_data=forecast_data,
                verbose=True,
            )
            return renderer.render()

        else:
            raise ValueError(f"Reporte desconocido: {report_name}")

    # =====================================================================
    # FASE 5: RESUMEN Y ENTREGA
    # =====================================================================

    def print_summary(self, report_results: List[Dict[str, Any]]):
        """Muestra resumen final del pipeline."""
        total_elapsed = time.time() - self.start_time

        self._print_header("FASE 5", "RESUMEN DEL PIPELINE")

        # Reportes generados
        print(f"\n  {'REPORTE':<20} {'ESTADO':<10} {'TIEMPO':<10} PATH")
        print(f"  {'-' * 70}")

        ok_count = 0
        err_count = 0
        for r in report_results:
            status_icon = "[OK]" if r['status'] == 'OK' else "[ERR]"
            path_str = r.get('path', r.get('error', '-'))
            print(f"  {r['report']:<20} {status_icon:<10} {r['duration']}s{'':<5} {path_str}")
            if r['status'] == 'OK':
                ok_count += 1
            else:
                err_count += 1

        print(f"  {'-' * 70}")

        # Errores
        if self.errors:
            print(f"\n  Errores encontrados ({len(self.errors)}):")
            for err in self.errors:
                print(f"    - {err}")

        # Totales
        print(f"\n  Reportes: {ok_count} generados, {err_count} con error")
        print(f"  Tiempo total: {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)")
        print(f"  Fecha: {self.date_str}")

        # Abrir en browser
        if self.open_browser:
            for r in report_results:
                if r['status'] == 'OK' and r.get('path'):
                    try:
                        webbrowser.open(f"file:///{r['path']}")
                    except Exception:
                        pass

        print(f"\n{'=' * 70}")
        print(f"GREYBARK RESEARCH - PIPELINE COMPLETADO")
        print(f"{'=' * 70}\n")

    # =====================================================================
    # RUN
    # =====================================================================

    def run(self) -> int:
        """Ejecuta el pipeline completo. Retorna 0 si OK, 1 si error."""
        self.start_time = time.time()

        print("\n" + "=" * 70)
        print("  GREYBARK RESEARCH - PIPELINE MENSUAL UNIFICADO")
        print("=" * 70)
        print(f"  Fecha: {self.date_str}")
        print(f"  Reportes: {', '.join(self.reports)}")
        print(f"  Modo: {'DRY RUN' if self.dry_run else 'PRODUCCIÓN'}")
        if self.skip_collect:
            print(f"  Skip collect: sí (usando datos existentes)")
        if self.no_confirm:
            print(f"  Confirmación: deshabilitada")

        # ---- FASE 1: Recopilación ----
        if self.skip_collect:
            self.data = self._load_existing_data()
        else:
            self.data = self.collect_all_data()

        # ---- FASE 2: Pre-Council Package ----
        # Generate ALL charts, tables, and intelligence briefing BEFORE council
        from pre_council_package import PreCouncilPackage
        self.pre_council = PreCouncilPackage(
            data=self.data, reports=self.reports, verbose=True
        )
        self.pre_council_pkg = self.pre_council.build()

        # Check which reports passed validation
        approved_reports = self.pre_council.get_approved_reports()
        blocked_reports = self.pre_council.get_blocked_reports()

        if blocked_reports:
            for br in blocked_reports:
                val = self.pre_council_pkg['validation'].get(br, {})
                missing = val.get('missing', [])
                total = val.get('total_required', 0)
                generated = val.get('generated', 0)

                print(f"\n  [WARN] {br.upper()}: {len(missing)}/{total} charts faltantes:")
                for m in missing:
                    print(f"    - {m}")

                # Decision logic: ask user or auto-approve
                if self.no_confirm:
                    # Auto mode: tolerate up to 3 missing required charts
                    if len(missing) <= 3:
                        print(f"  [AUTO] {br.upper()}: {len(missing)} faltantes (tolerancia ≤3), aprobado con advertencia")
                        approved_reports.append(br)
                    else:
                        print(f"  [AUTO] {br.upper()}: {len(missing)} faltantes (>3), BLOQUEADO")
                        self.errors.append(f"Fase 2 - {br}: {len(missing)} charts sin datos")
                else:
                    # Interactive mode: ask user
                    try:
                        print(f"\n  El reporte {br.upper()} tiene {generated} de {total} charts.")
                        print(f"  Faltan {len(missing)} charts required.")
                        resp = input(f"  ¿Generar {br.upper()} de todas formas? (s/n): ").strip().lower()
                        if resp in ('s', 'si', 'sí', 'y', 'yes'):
                            approved_reports.append(br)
                            print(f"  [OK] {br.upper()}: aprobado manualmente por el usuario")
                        else:
                            print(f"  [SKIP] {br.upper()}: omitido por el usuario")
                            self.errors.append(f"Fase 2 - {br}: omitido por usuario ({len(missing)} charts faltantes)")
                    except (EOFError, KeyboardInterrupt):
                        print(f"\n  [SKIP] {br.upper()}: omitido (sin input)")

        if not approved_reports:
            print("\n  [NO_GO] Ningún reporte pasó la validación de datos. Abortando.")
            return 1

        self.reports = approved_reports

        # ---- FASE 3: Preflight (council-specific checks) ----
        verdict = self.preflight_check(self.data)

        if verdict in ('NO_GO', 'CANCELLED') or self.dry_run:
            return 1 if verdict == 'NO_GO' else 0

        # ---- FASE 4: AI Council (receives pre-built briefing) ----
        # Inject pre-council briefing into data so council agents receive it
        self.data['pre_council_briefing'] = self.pre_council_pkg.get('briefing', {})
        self.data['pre_council_stats'] = self.pre_council_pkg.get('data_stats', {})
        self.data['pre_council_summary'] = self.pre_council.format_for_council()

        self.council_result = self.run_council(self.data)

        if self.council_result is None:
            print("\n  [ERROR] Council falló. Generando reportes sin council output...")

        if self.council_result and self.council_result.get('aborted'):
            print("\n  [NO-GO] Council abortó por preflight. Generando reportes con defaults...")
            self.council_result = None

        # ---- FASE 5: Ensamblar Reportes (charts ya pre-generados) ----
        equity_data = self.data.get('equity')
        if isinstance(equity_data, dict) and 'error' in equity_data:
            equity_data = None

        forecast_data = self.data.get('forecasts')
        if isinstance(forecast_data, dict) and 'error' in forecast_data:
            forecast_data = None

        self.report_results = self.generate_reports(
            self.council_result, equity_data, forecast_data
        )

        # ---- FASE 6: Resumen ----
        self.print_summary(self.report_results)

        has_errors = any(r['status'] == 'ERROR' for r in self.report_results)
        return 1 if has_errors else 0


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Greybark Research - Pipeline Mensual Unificado',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_monthly.py                      Pipeline completo
  python run_monthly.py --dry-run            Solo recopilar y preflight
  python run_monthly.py --skip-collect       Usar datos ya recopilados
  python run_monthly.py --reports macro rv   Solo macro y RV
  python run_monthly.py --no-confirm         Sin pausa de confirmación
  python run_monthly.py --no-confirm --open  Full auto + abrir browser
        """
    )

    parser.add_argument(
        '--dry-run', action='store_true',
        help='Solo recopila datos y muestra preflight, no ejecuta council'
    )
    parser.add_argument(
        '--skip-collect', action='store_true',
        help='Usar datos ya recopilados (output/equity_data/ y output/council/)'
    )
    parser.add_argument(
        '--no-confirm', action='store_true',
        help='No pausar para confirmación antes del council'
    )
    parser.add_argument(
        '--reports', nargs='+', choices=VALID_REPORTS, default=VALID_REPORTS,
        help=f'Reportes a generar (default: {" ".join(VALID_REPORTS)})'
    )
    parser.add_argument(
        '--open', action='store_true', dest='open_browser',
        help='Abrir reportes en browser al finalizar'
    )

    args = parser.parse_args()

    pipeline = MonthlyPipeline(
        dry_run=args.dry_run,
        skip_collect=args.skip_collect,
        no_confirm=args.no_confirm,
        reports=args.reports,
        open_browser=args.open_browser,
    )

    exit_code = pipeline.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

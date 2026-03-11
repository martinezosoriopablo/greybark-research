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

# Load .env file (API keys: ANTHROPIC, FRED, BCCh, BEA, AlphaVantage)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
        branding: dict = None,
        output_dir: str = None,
        client_prompts: dict = None,
    ):
        self.dry_run = dry_run
        self.skip_collect = skip_collect
        self.no_confirm = no_confirm
        self.reports = reports or VALID_REPORTS
        self.open_browser = open_browser
        self.date_str = datetime.now().strftime('%Y-%m-%d')
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Client customization (None = Greybark defaults)
        self.branding = branding
        self.custom_output_dir = Path(output_dir) if output_dir else None
        self.client_prompts = client_prompts

        # State
        self.data = {}
        self.council_result = None
        self.report_results = []
        self.errors = []
        self.start_time = None

        # Ensure output dirs exist
        for d in [COUNCIL_DIR, REPORTS_DIR, EQUITY_DIR, RF_DIR, FORECAST_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        if self.custom_output_dir:
            self.custom_output_dir.mkdir(parents=True, exist_ok=True)

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
    # FASE 2.1: INFORME DE ANTECEDENTES
    # =====================================================================

    def generate_antecedentes(self, data: Dict[str, Any]) -> Optional[Dict]:
        """Generate the formal Informe de Antecedentes (Phase 2.1).

        Validates data completeness field-by-field and generates
        JSON + HTML background reports documenting all available data.
        """
        self._print_header("FASE 2.1", "INFORME DE ANTECEDENTES")
        start = time.time()

        try:
            from data_completeness_validator import DataCompletenessValidator
            from antecedentes_report import AntecedentesReport
            from council_data_collector import CouncilDataCollector

            # Rebuild agent_data_map to validate
            collector = CouncilDataCollector(verbose=False)
            macro_quant = data.get('macro_quant', {})
            daily_summary = data.get('daily_summary', {})
            intelligence = data.get('intelligence', {})

            agent_data_map = collector._prepare_agent_specific_data(
                macro_quant, daily_summary, intelligence, 'macro'
            )

            # Inject equity/rf data if available
            equity_data = data.get('equity', {})
            if equity_data and isinstance(equity_data, dict) and 'error' not in equity_data:
                rv_agent = agent_data_map.get('rv', {})
                rv_agent['equity_data'] = {
                    'valuations': equity_data.get('valuations', {}),
                    'earnings': equity_data.get('earnings', {}),
                    'factors': equity_data.get('factors', {}),
                    'sectors': equity_data.get('sectors', {}),
                }
                riesgo_agent = agent_data_map.get('riesgo', {})
                riesgo_agent['equity_risk'] = equity_data.get('risk', {})

            rf_data = data.get('rf', {})
            if rf_data and isinstance(rf_data, dict) and 'error' not in rf_data:
                rf_agent = agent_data_map.get('rf', {})
                rf_agent['rf_data'] = {
                    'yield_curve': rf_data.get('yield_curve', {}),
                    'credit_spreads': rf_data.get('credit_spreads', {}),
                    'inflation': rf_data.get('inflation', {}),
                }

            # Run completeness validation
            validator = DataCompletenessValidator(verbose=True)
            completeness = validator.validate(agent_data_map)
            validator.print_report(completeness)

            # Store completeness for later phases
            self._completeness = completeness

            # Generate antecedentes report
            report_gen = AntecedentesReport(verbose=True)
            report = report_gen.generate(
                agent_data_map, completeness,
                metadata={'date': self.date_str, 'pipeline': 'monthly'}
            )

            # Save JSON + HTML
            report_gen.save_json(report, self.date_str)
            report_gen.save_html(report, self.date_str)

            elapsed = time.time() - start
            self._print(f"\n  Antecedentes completado en {elapsed:.1f}s")
            return report

        except Exception as e:
            self._print_err(f"Antecedentes falló: {e}")
            import traceback
            traceback.print_exc()
            self.errors.append(f"Fase 2.1 - Antecedentes: {e}")
            return None

    # =====================================================================
    # FASE 2.2: LIBRO DE ANTECEDENTES
    # =====================================================================

    def generate_antecedentes_briefing(self, data: Dict[str, Any]) -> Optional[str]:
        """Generate comprehensive Libro de Antecedentes (Phase 2.2).

        Full pre-council briefing with charts, tables, and data presentation
        for the human portfolio manager.
        """
        self._print_header("FASE 2.2", "LIBRO DE ANTECEDENTES")
        start = time.time()

        try:
            from antecedentes_briefing_generator import AntecedentesBriefingGenerator

            completeness = getattr(self, '_completeness', None)

            generator = AntecedentesBriefingGenerator(
                data=data,
                completeness=completeness,
                branding=self.branding,
                verbose=True,
            )

            output_dir = str(self.custom_output_dir) if self.custom_output_dir else None
            path = generator.render(output_dir=output_dir)

            elapsed = time.time() - start
            self._print(f"\n  Libro de Antecedentes completado en {elapsed:.1f}s")
            self._print(f"  -> {path}")
            return path

        except Exception as e:
            self._print_err(f"Libro de Antecedentes falló: {e}")
            import traceback
            traceback.print_exc()
            self.errors.append(f"Fase 2.2 - Libro de Antecedentes: {e}")
            return None

    # =====================================================================
    # FASE 2.5: INTELLIGENCE BRIEFING
    # =====================================================================

    def generate_intelligence_briefing(self, data: Dict[str, Any]) -> Optional[Dict]:
        """Genera el intelligence briefing ejecutivo pre-comité."""
        self._print_header("FASE 2.5", "INTELLIGENCE BRIEFING")

        intelligence = data.get('intelligence', {})
        daily_context = data.get('daily_context', '')
        directives = data.get('directives', '')

        if not intelligence or 'error' in intelligence:
            self._print_step("Sin intelligence digest — skipping briefing")
            return None

        try:
            from intelligence_briefing_generator import IntelligenceBriefingGenerator
            from intelligence_briefing_renderer import IntelligenceBriefingRenderer

            # Generar briefing
            gen = IntelligenceBriefingGenerator(
                intelligence, daily_context, directives, verbose=True
            )
            briefing = gen.generate_briefing()

            # Renderizar HTML
            renderer = IntelligenceBriefingRenderer(briefing, verbose=True)
            path = renderer.render()
            self._print_ok(f"Briefing: {path}")

            # Guardar briefing formateado para inyectar en council
            self.data['intelligence_briefing'] = gen.format_for_council()
            self._print_ok(f"Briefing para council: {len(self.data['intelligence_briefing'])} chars")

            return briefing

        except Exception as e:
            self._print_err(f"Intelligence briefing falló: {e}")
            self.errors.append(f"Fase 2.5 - Briefing: {e}")
            import traceback
            traceback.print_exc()
            return None

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

            runner = AICouncilRunner(verbose=True, client_prompts=self.client_prompts)

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

            # Inyectar intelligence_briefing al collector del runner
            intelligence_briefing = data.get('intelligence_briefing', '')
            if intelligence_briefing:
                runner.data_collector._intelligence_briefing = intelligence_briefing
                self._print_step("Intelligence briefing inyectado al Council input")

            # Inyectar WSJ summaries al collector del runner
            wsj_data = data.get('wsj', {})
            if wsj_data.get('available') and wsj_data.get('summaries'):
                wsj_text = "\n\n".join(
                    f"[{s.get('date', 'N/D')}] {s.get('summary', '')}"
                    for s in wsj_data['summaries'][:7]
                )
                runner.data_collector._wsj_context = wsj_text
                self._print_step(f"WSJ summaries inyectados ({len(wsj_data['summaries'])} resumenes)")

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
        self._report_contents = {}  # Collect for auditor

        for report_name in self.reports:
            self._print_step(f"Generando reporte: {report_name.upper()}...")
            start = time.time()

            try:
                output_path, content = self._generate_single_report(
                    report_name, council_result, equity_data, forecast_data
                )
                elapsed = time.time() - start
                results.append({
                    'report': report_name,
                    'status': 'OK',
                    'path': output_path,
                    'duration': round(elapsed, 1),
                })
                if content:
                    self._report_contents[report_name] = content
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
    ) -> tuple:
        """Genera un reporte individual. Retorna (path, content_dict)."""

        if report_name == 'macro':
            from macro_report_renderer import MacroReportRenderer
            # Pass ALL collected macro_quant data (BEA, OECD, AKShare, ECB, BCRP, NYFed, etc.)
            macro_quant = {}
            if self.data:
                macro_quant = self.data.get('macro_agent_data', {})
                if not macro_quant:
                    mq = self.data.get('macro_quant', {})
                    if isinstance(mq, dict) and 'error' not in mq:
                        # Pass entire macro_quant — all 10 modules + external APIs
                        macro_quant = dict(mq)
                    else:
                        macro_quant = {}
                    # Ensure chile_extended sub-fields are accessible at top level
                    chile_ext = macro_quant.get('chile_extended', self.data.get('chile_extended', {}))
                    if chile_ext and isinstance(chile_ext, dict) and 'error' not in chile_ext:
                        macro_quant.setdefault('chile_eee', chile_ext.get('eee_expectations', {}))
                        macro_quant.setdefault('chile_imce', chile_ext.get('imce', {}))
                        macro_quant.setdefault('chile_ipc_detail', chile_ext.get('ipc_detail', {}))
                    # Ensure nyfed rstar accessible at top level for backward compat
                    nyfed = macro_quant.get('nyfed', {})
                    if nyfed and isinstance(nyfed, dict) and 'error' not in nyfed:
                        macro_quant.setdefault('nyfed_rstar', nyfed.get('rstar', {}))
            renderer = MacroReportRenderer(
                council_result=council_result,
                forecast_data=forecast_data,
                verbose=True,
                branding=self.branding,
                quant_data=macro_quant,
            )
            path = renderer.render()

        elif report_name == 'rv':
            from rv_report_renderer import RVReportRenderer
            renderer = RVReportRenderer(
                council_result=council_result,
                market_data=equity_data,
                forecast_data=forecast_data,
                verbose=True,
                branding=self.branding,
            )
            path = renderer.render()

        elif report_name == 'rf':
            from rf_report_renderer import RFReportRenderer
            # Get RF quant data
            rf_data = self.data.get('rf')
            if isinstance(rf_data, dict) and 'error' in rf_data:
                rf_data = None
            # Inject nyfed r-star into rf_data for neutral rate
            if rf_data and isinstance(rf_data, dict):
                nyfed = self.data.get('macro_quant', {}).get('nyfed', {})
                if nyfed and 'error' not in nyfed:
                    rf_data['nyfed_rstar'] = nyfed.get('rstar', {})
            # Inject sovereign curves (ECB Svensson, MoF Japan) into rf_data
            if rf_data is None:
                rf_data = {}
            sov_curves = self.data.get('macro_quant', {}).get('sovereign_curves', {})
            if sov_curves and 'error' not in sov_curves:
                rf_data['sovereign_curves'] = sov_curves
            # Inject BCRP EMBI spreads for LatAm section
            macro_quant = self.data.get('macro_quant', {})
            if isinstance(macro_quant, dict):
                bcrp = macro_quant.get('bcrp_embi') or macro_quant.get('bcrp', {})
                if bcrp and isinstance(bcrp, dict) and 'error' not in bcrp:
                    rf_data.setdefault('bcrp_embi', bcrp)
                # Inject ECB API data (DFR, HICP, M3, EA yield)
                ecb = macro_quant.get('ecb', {})
                if ecb and isinstance(ecb, dict) and 'error' not in ecb:
                    rf_data.setdefault('ecb', ecb)
                # Inject Cleveland Fed r-star if collected
                clev = macro_quant.get('cleveland_rstar', {})
                if clev and isinstance(clev, dict) and 'error' not in clev:
                    rf_data.setdefault('cleveland_rstar', clev)
            renderer = RFReportRenderer(
                council_result=council_result,
                market_data=rf_data,
                forecast_data=forecast_data,
                verbose=True,
                branding=self.branding,
            )
            path = renderer.render()

        elif report_name == 'aa':
            from asset_allocation_renderer import AssetAllocationRenderer
            # Combine equity + RF data for AA report
            aa_data = {}
            rf_data = self.data.get('rf')
            if isinstance(rf_data, dict) and 'error' not in rf_data:
                aa_data.update(rf_data)
            if equity_data and isinstance(equity_data, dict):
                aa_data['equity'] = equity_data
            # Inject nyfed r-star
            nyfed = self.data.get('macro_quant', {}).get('nyfed', {})
            if nyfed and 'error' not in nyfed:
                aa_data['nyfed_rstar'] = nyfed.get('rstar', {})
            # Inject macro_quant so AA content generator can access macro data
            macro_quant = self.data.get('macro_quant', {})
            if isinstance(macro_quant, dict) and 'error' not in macro_quant:
                for key in ['macro_usa', 'chile', 'chile_extended', 'chile_rates',
                            'regime', 'inflation', 'rates', 'leading_indicators',
                            'china', 'risk', 'breadth', 'international', 'bloomberg',
                            'bea', 'oecd', 'ecb', 'bcrp_embi', 'bcrp',
                            'akshare_china', 'akshare', 'nyfed', 'sovereign_curves']:
                    if key in macro_quant and key not in aa_data:
                        aa_data[key] = macro_quant[key]
                # Map tpm_expectations from rates
                rates = macro_quant.get('rates', {})
                if isinstance(rates, dict) and 'tpm_expectations' in rates:
                    aa_data['tpm_expectations'] = rates['tpm_expectations']
            # Ensure credit_spreads from rf_data are available
            if 'credit_spreads' not in aa_data:
                rf_raw = self.data.get('rf', {})
                if isinstance(rf_raw, dict) and 'credit_spreads' in rf_raw:
                    aa_data['credit_spreads'] = rf_raw['credit_spreads']
            # Duration analytics
            if 'duration' not in aa_data:
                rf_raw = self.data.get('rf', {})
                if isinstance(rf_raw, dict) and 'duration' in rf_raw:
                    aa_data['duration'] = rf_raw['duration']
            renderer = AssetAllocationRenderer(
                council_result=council_result,
                market_data=aa_data if aa_data else None,
                forecast_data=forecast_data,
                verbose=True,
                branding=self.branding,
            )
            path = renderer.render()

        else:
            raise ValueError(f"Reporte desconocido: {report_name}")

        content = getattr(renderer, 'last_content', None)

        # Copy to custom output dir if specified
        if self.custom_output_dir and path and os.path.exists(path):
            import shutil
            dest = self.custom_output_dir / os.path.basename(path)
            shutil.copy2(path, dest)
            return str(dest), content
        return path, content

    # =====================================================================
    # FASE 3.5: VALIDACIÓN POST-COUNCIL
    # =====================================================================

    def validate_post_council(self, council_result: Dict, data: Dict) -> Optional[Dict]:
        """Validate agent outputs against their input data (Phase 3.5)."""
        if not council_result or council_result.get('aborted'):
            return None

        self._print_header("FASE 3.5", "VALIDACIÓN POST-COUNCIL")
        start = time.time()

        try:
            from post_council_validator import PostCouncilValidator

            # We need council_input with agent_data — reconstruct from runner's collector
            # The simplest approach: rebuild agent_data from our data
            from council_data_collector import CouncilDataCollector
            collector = CouncilDataCollector(verbose=False)

            # Quick prepare to get agent_data map
            macro_quant = data.get('macro_quant', {})
            daily_summary = data.get('daily_summary', {})
            intelligence = data.get('intelligence', {})

            agent_data_map = collector._prepare_agent_specific_data(
                macro_quant, daily_summary, intelligence, 'macro'
            )

            # Inject equity/rf data same as in run_council
            equity_data = data.get('equity', {})
            if equity_data and isinstance(equity_data, dict) and 'error' not in equity_data:
                rv_agent = agent_data_map.get('rv', {})
                rv_agent['equity_data'] = {
                    'valuations': equity_data.get('valuations', {}),
                    'earnings': equity_data.get('earnings', {}),
                    'factors': equity_data.get('factors', {}),
                    'sectors': equity_data.get('sectors', {}),
                }
                riesgo_agent = agent_data_map.get('riesgo', {})
                riesgo_agent['equity_risk'] = equity_data.get('risk', {})
                riesgo_agent['equity_credit'] = equity_data.get('credit', {})

            rf_data = data.get('rf', {})
            if rf_data and isinstance(rf_data, dict) and 'error' not in rf_data:
                rf_agent = agent_data_map.get('rf', {})
                rf_agent['rf_data'] = {
                    'yield_curve': rf_data.get('yield_curve', {}),
                    'credit_spreads': rf_data.get('credit_spreads', {}),
                    'inflation': rf_data.get('inflation', {}),
                }
                riesgo_agent = agent_data_map.get('riesgo', {})
                riesgo_agent['rf_credit'] = rf_data.get('credit_spreads', {})

            council_input = {'agent_data': agent_data_map}

            validator = PostCouncilValidator(verbose=True)
            report = validator.validate_all(council_result, council_input)

            print(validator.format_report(report))

            # Save
            validator.save(report, self.date_str)

            elapsed = time.time() - start
            self._print(f"\n  Validación post-council completada en {elapsed:.1f}s")

            return report

        except Exception as e:
            self._print_err(f"Validación post-council falló: {e}")
            import traceback
            traceback.print_exc()
            return None

    # =====================================================================
    # FASE 4.5: AUDITORÍA DE COHERENCIA
    # =====================================================================

    def audit_coherence(self) -> Dict[str, Any]:
        """Audita coherencia entre los 4 reportes generados.

        If HIGH flags are found, escalates to refinador for resolution,
        then regenerates affected reports with correction directives.
        """
        contents = getattr(self, '_report_contents', {})
        if len(contents) < 2:
            self._print_step("Auditoría omitida (menos de 2 reportes generados)")
            return {}

        self._print_header("FASE 4.5", "AUDITORÍA DE COHERENCIA")
        start = time.time()

        try:
            from report_auditor import (
                audit_reports, format_audit_report,
                resolve_flags, format_resolution,
                numeric_audit,
            )
            from coherence_validator import format_coherence_report

            # --- Step 0: Numeric coherence (deterministic) ---
            source_data = {
                'quant_data': self.data.get('quant', {}),
                'rf_data': self.data.get('rf', {}),
                'equity_data': self.data.get('equity', {}),
            }
            numeric_result = numeric_audit(source_data, contents)
            print(format_coherence_report(numeric_result))

            # --- Step 1: LLM Audit ---
            result = audit_reports(contents)
            print(format_audit_report(result))

            # Merge numeric flags into LLM audit
            result.setdefault("flags", []).extend(numeric_result.get("flags", []))
            result["numeric_coherence"] = numeric_result.get("coherence_score")

            high_flags = [f for f in result.get("flags", []) if f.get("severity") == "high"]

            if not high_flags:
                elapsed = time.time() - start
                self._print(f"\n  Auditoría completada en {elapsed:.1f}s — sin flags críticos")
                self._save_audit(result)
                return result

            # --- Step 2: Refinador resolves ---
            self._print(f"\n  {len(high_flags)} flags HIGH → escalando al Refinador...")
            resolution = resolve_flags(result, self.council_result or {})
            print(format_resolution(resolution))

            corrections = resolution.get("corrections", [])
            if not corrections or resolution.get("status") != "resolved":
                elapsed = time.time() - start
                self._print(f"\n  Refinador no generó correcciones. Auditoría en {elapsed:.1f}s")
                result["resolution"] = resolution
                self._save_audit(result)
                return result

            # --- Step 3: Regenerate affected reports ---
            affected = set(c.get("report") for c in corrections if c.get("report"))
            self._print(f"\n  Regenerando reportes: {', '.join(r.upper() for r in affected)}...")

            # Build per-report directive strings
            directives = {}
            for c in corrections:
                rpt = c.get("report", "")
                if rpt:
                    directives.setdefault(rpt, []).append(c.get("directive", ""))

            equity_data = self.data.get('equity')
            if isinstance(equity_data, dict) and 'error' in equity_data:
                equity_data = None
            forecast_data = self.data.get('forecasts')
            if isinstance(forecast_data, dict) and 'error' in forecast_data:
                forecast_data = None

            from narrative_engine import set_correction_directive, clear_correction_directive

            for report_name in affected:
                if report_name not in self.reports:
                    continue
                directive_text = " ".join(directives.get(report_name, []))
                self._print_step(f"  Regenerando {report_name.upper()} con correcciones...")

                try:
                    set_correction_directive(directive_text)
                    path, new_content = self._generate_single_report(
                        report_name, self.council_result, equity_data,
                        forecast_data,
                    )
                    if new_content:
                        self._report_contents[report_name] = new_content
                    # Update report_results
                    for r in self.report_results:
                        if r['report'] == report_name:
                            r['path'] = path
                            r['corrected'] = True
                    self._print_ok(f"  {report_name.upper()} regenerado: {path}")
                except Exception as e:
                    self._print_err(f"  {report_name.upper()} regeneración falló: {e}")
                finally:
                    clear_correction_directive()

            elapsed = time.time() - start
            self._print(f"\n  Auditoría + corrección completada en {elapsed:.1f}s")

            result["resolution"] = resolution
            self._save_audit(result)
            return result

        except Exception as e:
            self._print_err(f"Auditoría falló: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'reason': str(e)}

    def _save_audit(self, result: Dict):
        """Save audit result to JSON."""
        audit_path = REPORTS_DIR / f"audit_{self.date_str}.json"
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        self._print(f"  Resultado: {audit_path}")

    # =====================================================================
    # FASE 4.6: DATA INTEGRITY REPORT
    # =====================================================================

    def generate_integrity_report(self) -> Optional[Dict]:
        """Generate a summary data integrity report (Phase 4.6).

        Aggregates results from: completeness validation (2.1),
        post-council validation (3.5), and coherence audit (4.5).
        """
        self._print_header("FASE 4.6", "DATA INTEGRITY REPORT")

        report = {
            'date': self.date_str,
            'timestamp': datetime.now().isoformat(),
            'completeness': {},
            'post_council': {},
            'coherence_audit': {},
            'overall_verdict': 'UNKNOWN',
        }

        # Completeness
        completeness = getattr(self, '_completeness', None)
        if completeness:
            report['completeness'] = {
                'verdict': completeness.verdict,
                'agents': {
                    name: {
                        'required_coverage': round(ac.required_coverage * 100, 1),
                        'important_coverage': round(ac.important_coverage * 100, 1),
                    }
                    for name, ac in completeness.agents.items()
                }
            }

        # Post-council
        post_council = getattr(self, 'post_council_result', None)
        if post_council:
            report['post_council'] = {
                'verdict': post_council.get('verdict', '?'),
                'total_flags': post_council.get('total_flags', 0),
                'flags_summary': [
                    f"{f.get('agent')}: {f.get('classification')} — {f.get('value')}"
                    for f in post_council.get('flags', [])[:10]
                ],
            }

        # Coherence audit
        audit = getattr(self, 'audit_result', None)
        if audit and isinstance(audit, dict):
            high_flags = [f for f in audit.get('flags', []) if f.get('severity') == 'high']
            report['coherence_audit'] = {
                'total_flags': len(audit.get('flags', [])),
                'high_flags': len(high_flags),
                'resolved': bool(audit.get('resolution', {}).get('status') == 'resolved'),
            }

        # Overall verdict
        verdicts = []
        if completeness:
            verdicts.append(completeness.verdict)
        if post_council:
            verdicts.append(post_council.get('verdict', 'UNKNOWN'))

        if 'NO_GO' in verdicts:
            report['overall_verdict'] = 'FAILED'
        elif 'SIGNIFICANT' in verdicts or 'CAUTION' in verdicts:
            report['overall_verdict'] = 'CAUTION'
        elif all(v in ('GO', 'CLEAN', 'MINOR') for v in verdicts):
            report['overall_verdict'] = 'CLEAN'
        else:
            report['overall_verdict'] = 'UNKNOWN'

        # Save
        path = REPORTS_DIR / f"data_integrity_{self.date_str}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Print summary
        print(f"\n  Data Integrity Verdict: [{report['overall_verdict']}]")
        if completeness:
            print(f"    Completeness: {completeness.verdict}")
        if post_council:
            print(f"    Post-council: {post_council.get('verdict', '?')} ({post_council.get('total_flags', 0)} flags)")
        if audit and isinstance(audit, dict):
            print(f"    Coherence: {len(audit.get('flags', []))} flags")
        print(f"  Saved: {path}")

        return report

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

        # ---- FASE 0: API Health Check ----
        if not self.skip_collect:
            try:
                from api_health_checker import check_all_apis, format_health_report
                self._print_header("FASE 0", "API HEALTH CHECK")
                health = check_all_apis(quick=True)
                print(format_health_report(health))
                if health["verdict"] == "NO_GO":
                    print("\n  [ABORT] Critical APIs are down. Fix before running pipeline.")
                    return 1
            except Exception as e:
                print(f"  [SKIP] Health check failed: {e}")

        # ---- FASE 1: Recopilación ----
        if self.skip_collect:
            self.data = self._load_existing_data()
        else:
            self.data = self.collect_all_data()

        # ---- FASE 2: Preflight ----
        verdict = self.preflight_check(self.data)

        if verdict in ('NO_GO', 'CANCELLED') or self.dry_run:
            return 1 if verdict == 'NO_GO' else 0

        # ---- FASE 2.1: Informe de Antecedentes ----
        self.antecedentes = self.generate_antecedentes(self.data)

        # ---- FASE 2.2: Libro de Antecedentes ----
        self.libro = self.generate_antecedentes_briefing(self.data)

        # ---- FASE 2.5: Intelligence Briefing ----
        self.briefing = self.generate_intelligence_briefing(self.data)

        # ---- FASE 3: AI Council ----
        self.council_result = self.run_council(self.data)

        if self.council_result is None:
            print("\n  [ERROR] Council falló. Generando reportes sin council output...")

        if self.council_result and self.council_result.get('aborted'):
            print("\n  [NO-GO] Council abortó por preflight. Generando reportes con defaults...")
            self.council_result = None

        # ---- FASE 3.5: Validación Post-Council ----
        self.post_council_result = self.validate_post_council(
            self.council_result, self.data
        )

        # ---- FASE 4: Reportes ----
        equity_data = self.data.get('equity')
        if isinstance(equity_data, dict) and 'error' in equity_data:
            equity_data = None

        forecast_data = self.data.get('forecasts')
        if isinstance(forecast_data, dict) and 'error' in forecast_data:
            forecast_data = None

        self.report_results = self.generate_reports(
            self.council_result, equity_data, forecast_data
        )

        # ---- FASE 4.5: Auditoría de Coherencia ----
        self.audit_result = self.audit_coherence()

        # ---- FASE 4.6: Data Integrity Report ----
        self.integrity_report = self.generate_integrity_report()

        # ---- FASE 5: Resumen ----
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

# -*- coding: utf-8 -*-
"""
Greybark Research — Pre-Council Package Builder
=================================================

Generates ALL visual assets (charts + tables) and intelligence briefings
BEFORE the AI Council runs. This ensures:

1. All data is validated and complete before spending tokens on the council
2. Charts are pre-generated with real data (no fallbacks)
3. The council receives a structured briefing like a "research department"
4. Report assembly (Phase 4) only pastes pre-built pieces — cannot fail

Output: PreCouncilPackage dict with:
  - charts: {report_type: {chart_id: base64_png}}
  - tables: {report_type: {table_id: html_string}}
  - briefing: {section: summary_text}  (LLM-generated from daily/research/DF)
  - data_stats: {chart_id: {trend, level, change}}
  - validation: {report_type: {ok: bool, missing: []}}
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Output directory for pre-council assets
OUTPUT_DIR = Path(__file__).parent / "output" / "pre_council"


class PreCouncilPackage:
    """Builds the complete pre-council package: charts, tables, briefing."""

    def __init__(self, data: Dict[str, Any], reports: List[str], verbose: bool = True):
        """
        Args:
            data: Full collected data from Phase 1 (macro_quant, equity, rf, forecasts, etc.)
            reports: List of report types to prepare ['macro', 'rv', 'rf', 'aa']
            verbose: Print progress
        """
        self.data = data
        self.reports = reports
        self.verbose = verbose
        self.package = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'reports': reports,
            },
            'charts': {},       # {report_type: {chart_id: base64}}
            'tables': {},       # {report_type: {table_id: html}}
            'briefing': {},     # {section: text}
            'data_stats': {},   # {chart_id: {trend, level, change}}
            'validation': {},   # {report_type: {ok, missing}}
        }
        self._failures = []

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    # =====================================================================
    # MAIN ENTRY POINT
    # =====================================================================

    def build(self) -> Dict[str, Any]:
        """Build the complete pre-council package. Returns the package dict."""
        start = time.time()
        self._print(f"\n{'=' * 70}")
        self._print(f"[FASE 2] PRE-COUNCIL PACKAGE")
        self._print(f"{'=' * 70}")

        # Step 1: Generate charts for each report
        self._print("\n  -> Generando charts con datos reales...")
        self._generate_all_charts()

        # Step 2: Generate intelligence briefing
        self._print("\n  -> Generando briefing de inteligencia...")
        self._generate_briefing()

        # Step 3: Validate completeness
        self._print("\n  -> Validando completitud...")
        self._validate_package()

        # Step 4: Extract data stats for council
        self._print("\n  -> Extrayendo estadísticas clave...")
        self._extract_data_stats()

        elapsed = time.time() - start
        self.package['metadata']['build_time_seconds'] = round(elapsed, 1)
        self.package['metadata']['chart_failures'] = self._failures

        # Summary
        total_charts = sum(len(c) for c in self.package['charts'].values())
        total_failed = len(self._failures)
        blocked = [rt for rt, v in self.package['validation'].items() if not v.get('ok', True)]

        self._print(f"\n  Pre-Council Package:")
        self._print(f"    Charts generados: {total_charts}")
        self._print(f"    Charts fallidos:  {total_failed}")
        self._print(f"    Briefing:         {len(self.package['briefing'])} secciones")
        self._print(f"    Reportes OK:      {len(self.reports) - len(blocked)}/{len(self.reports)}")
        if blocked:
            self._print(f"    BLOQUEADOS:       {', '.join(blocked)}")
        self._print(f"    Tiempo:           {elapsed:.1f}s")

        # Save to disk
        self._save()

        return self.package

    # =====================================================================
    # STEP 1: CHART GENERATION
    # =====================================================================

    def _generate_all_charts(self):
        """Generate charts for each requested report type."""
        for report_type in self.reports:
            self._print(f"    [{report_type.upper()}] ", )
            try:
                charts = self._generate_report_charts(report_type)
                self.package['charts'][report_type] = charts
                self._print(f"    [{report_type.upper()}] {len(charts)} charts OK")
            except Exception as e:
                self.package['charts'][report_type] = {}
                self._print(f"    [{report_type.upper()}] ERROR: {e}")
                self._failures.append({'report': report_type, 'error': str(e)})

    def _generate_report_charts(self, report_type: str) -> Dict[str, str]:
        """Generate all charts for a specific report type."""
        if report_type == 'macro':
            return self._generate_macro_charts()
        elif report_type == 'rv':
            return self._generate_rv_charts()
        elif report_type == 'rf':
            return self._generate_rf_charts()
        elif report_type == 'aa':
            return {}  # AA has no charts
        return {}

    def _generate_macro_charts(self) -> Dict[str, str]:
        """Generate all 24 macro charts using ChartDataProvider + Bloomberg."""
        from chart_data_provider import ChartDataProvider
        from chart_generator import MacroChartsGenerator, ChartDataError

        cdp = ChartDataProvider()

        # Inject spot values from quant data
        spot = {}
        quant = self.data.get('macro_quant', {})
        if isinstance(quant, dict) and 'error' not in quant:
            risk = quant.get('risk', {})
            if isinstance(risk, dict):
                vix_d = risk.get('vix', {})
                if isinstance(vix_d, dict):
                    spot['vix'] = vix_d.get('current')
            chile = quant.get('chile', {})
            if isinstance(chile, dict):
                spot['tpm'] = chile.get('tpm')
                spot['copper'] = chile.get('copper_price')
        cdp._injected_spot = {k: v for k, v in spot.items() if v is not None}

        # Bloomberg reader
        bloomberg = None
        try:
            from bloomberg_reader import BloombergData
            bloomberg = BloombergData()
        except Exception as e:
            logger.warning("Bloomberg not available: %s", e)

        charts_gen = MacroChartsGenerator(
            data_provider=cdp,
            forecast_data=self.data.get('forecasts'),
            bloomberg=bloomberg,
        )

        # Generate time series charts (the 22 main ones)
        charts = charts_gen.generate_macro_time_series_charts()

        # Track failures
        for f in charts_gen.get_chart_failures():
            self._failures.append({
                'report': 'macro', 'chart_id': f['chart_id'], 'error': f['error']
            })

        return charts

    def _generate_rv_charts(self) -> Dict[str, str]:
        """Generate all 12 RV charts."""
        from rv_chart_generator import RVChartsGenerator

        equity_data = self.data.get('equity', {})
        if isinstance(equity_data, dict) and 'error' in equity_data:
            equity_data = {}

        chart_gen = RVChartsGenerator(market_data=equity_data)
        return chart_gen.generate_all_charts()

    def _generate_rf_charts(self) -> Dict[str, str]:
        """Generate all 8 RF charts."""
        from rf_chart_generator import RFChartsGenerator

        rf_data = self.data.get('rf', {})
        if isinstance(rf_data, dict) and 'error' in rf_data:
            rf_data = {}

        chart_gen = RFChartsGenerator(rf_data)
        return chart_gen.generate_all_charts()

    # =====================================================================
    # STEP 2: INTELLIGENCE BRIEFING
    # =====================================================================

    def _generate_briefing(self):
        """Generate structured intelligence briefing using LLM.

        Organizes daily reports, DF intelligence, WSJ, and research
        into sections that each council agent can consume.
        """
        briefing = {}

        # Gather raw inputs
        intelligence = self.data.get('intelligence', {})
        daily_summary = self.data.get('daily_summary', {})
        research = self.data.get('research', '')
        wsj = self.data.get('wsj', {})
        directives = self.data.get('directives', '')

        # Format intelligence digest (already has format_for_council)
        daily_context = ''
        if intelligence and 'error' not in intelligence:
            try:
                from daily_intelligence_digest import DailyIntelligenceDigest
                daily_context = DailyIntelligenceDigest.format_for_council(intelligence)
            except Exception as e:
                logger.warning("Intelligence formatting failed: %s", e)

        # Build section-specific briefings using LLM
        try:
            briefing = self._build_sectioned_briefing(
                daily_context=daily_context,
                research=research,
                wsj=wsj,
                intelligence=intelligence,
                directives=directives,
            )
        except Exception as e:
            logger.warning("LLM briefing generation failed: %s", e)
            # Fallback: pass raw intelligence without LLM summary
            briefing = {
                'macro': daily_context[:3000] if daily_context else 'Sin datos de inteligencia diaria.',
                'rv': daily_context[:3000] if daily_context else 'Sin datos.',
                'rf': daily_context[:3000] if daily_context else 'Sin datos.',
                'riesgo': daily_context[:3000] if daily_context else 'Sin datos.',
                'geo': daily_context[:3000] if daily_context else 'Sin datos.',
                'research_summary': research[:2000] if research else 'Sin research externo.',
            }

        self.package['briefing'] = briefing
        self._print(f"    Briefing: {len(briefing)} secciones generadas")

    def _build_sectioned_briefing(
        self,
        daily_context: str,
        research: str,
        wsj: Dict,
        intelligence: Dict,
        directives: str,
    ) -> Dict[str, str]:
        """Use LLM to synthesize intelligence into agent-specific sections."""
        try:
            import anthropic
            client = anthropic.Anthropic()
        except Exception:
            logger.warning("Anthropic client not available, using raw intelligence")
            return {}

        # Build WSJ context
        wsj_text = ''
        if wsj and wsj.get('available'):
            summaries = wsj.get('summaries', [])
            wsj_text = '\n'.join(s.get('content', '')[:500] for s in summaries[:5])

        # Extract themes for context
        themes_text = ''
        if intelligence and isinstance(intelligence, dict):
            themes = intelligence.get('themes', {})
            top_themes = sorted(themes.items(), key=lambda x: x[1].get('score', 0), reverse=True)[:10]
            themes_text = '\n'.join(f"- {t[0]}: score {t[1].get('score', 0):.1f}, trend {t[1].get('trend', '?')}"
                                   for t in top_themes)

        prompt = f"""Eres el departamento de estudios y estadísticas de Greybark Research.
Tu trabajo es organizar la inteligencia de mercado en secciones para el comité de inversiones.

FUENTES DE INFORMACIÓN:
1. Reportes diarios AM/PM (últimos 30 días):
{daily_context[:6000]}

2. Temas dominantes identificados:
{themes_text}

3. Research externo (Goldman, JPM, MS):
{research[:3000] if research else 'No disponible'}

4. WSJ:
{wsj_text[:2000] if wsj_text else 'No disponible'}

5. Directivas del usuario:
{directives[:1000] if directives else 'Sin directivas específicas'}

INSTRUCCIONES:
Genera un briefing estructurado en EXACTAMENTE estas 6 secciones.
Cada sección debe ser un resumen conciso (200-400 palabras) de lo más relevante
para ese tema, citando datos específicos cuando estén disponibles.

Secciones:
1. MACRO: Crecimiento, empleo, política fiscal, actividad económica global
2. INFLACION_TASAS: Inflación, bancos centrales, curvas de rendimiento, expectativas de tasas
3. RENTA_VARIABLE: Valuaciones, earnings, sectores, flujos, posicionamiento
4. RENTA_FIJA: Spreads, crédito, duración, soberanos, EM debt
5. RIESGO_GEOPOLITICA: VIX, EPU, conflictos, elecciones, commodities, supply chain
6. CHILE_LATAM: TPM, IPC, IMACEC, cobre, tipo de cambio, política local

Formato: JSON con las 6 claves. Solo el JSON, sin markdown.
"""

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()

            # Parse JSON
            if text.startswith('{'):
                briefing = json.loads(text)
            else:
                # Try to extract JSON from response
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    briefing = json.loads(text[start:end])
                else:
                    raise ValueError("No JSON found in response")

            # Map sections to agent names
            section_map = {
                'MACRO': 'macro',
                'INFLACION_TASAS': 'rf',
                'RENTA_VARIABLE': 'rv',
                'RENTA_FIJA': 'rf_credit',
                'RIESGO_GEOPOLITICA': 'riesgo',
                'CHILE_LATAM': 'chile',
            }
            result = {}
            for section_key, agent_key in section_map.items():
                result[agent_key] = briefing.get(section_key, '')

            # Add raw research summary
            result['research_summary'] = research[:2000] if research else ''
            result['directives'] = directives or ''

            return result

        except Exception as e:
            logger.warning("LLM briefing failed: %s", e)
            return {}

    # =====================================================================
    # STEP 3: VALIDATION
    # =====================================================================

    def _validate_package(self):
        """Validate that each report has all required charts."""
        from data_manifest import get_required_charts

        for report_type in self.reports:
            required = get_required_charts(report_type)
            generated = set(self.package['charts'].get(report_type, {}).keys())

            missing = []
            for dep in required:
                if dep.chart_id not in generated:
                    missing.append(dep.chart_id)

            ok = len(missing) == 0
            self.package['validation'][report_type] = {
                'ok': ok,
                'total_required': len(required),
                'generated': len(generated),
                'missing': missing,
            }

            status = "OK" if ok else f"BLOCKED ({len(missing)} missing)"
            self._print(f"    [{report_type.upper()}] {status}")
            if missing:
                for m in missing[:5]:
                    self._print(f"      - {m}")
                if len(missing) > 5:
                    self._print(f"      ... y {len(missing) - 5} más")

    # =====================================================================
    # STEP 4: DATA STATS FOR COUNCIL
    # =====================================================================

    def _extract_data_stats(self):
        """Extract key statistics from data for council consumption.

        These are the numbers behind each chart — trends, levels, changes —
        so the council can reference precise data in its analysis.
        """
        stats = {}
        quant = self.data.get('macro_quant', {})
        equity = self.data.get('equity', {})
        rf = self.data.get('rf', {})

        # Macro stats
        if isinstance(quant, dict) and 'error' not in quant:
            macro_usa = quant.get('macro_usa', {})
            if isinstance(macro_usa, dict) and 'error' not in macro_usa:
                stats['gdp_usa'] = macro_usa.get('gdp')
                stats['unemployment_usa'] = macro_usa.get('unemployment')
                stats['payrolls'] = macro_usa.get('payrolls')

            inflation = quant.get('inflation', {})
            if isinstance(inflation, dict) and 'error' not in inflation:
                stats['cpi_core'] = inflation.get('cpi_core_yoy')
                stats['breakeven_5y'] = inflation.get('breakeven_5y')
                stats['breakeven_10y'] = inflation.get('breakeven_10y')

            chile = quant.get('chile', {})
            if isinstance(chile, dict) and 'error' not in chile:
                stats['tpm'] = chile.get('tpm')
                stats['imacec'] = chile.get('imacec')
                stats['ipc_chile'] = chile.get('ipc')
                stats['usdclp'] = chile.get('usd_clp')

            risk = quant.get('risk', {})
            if isinstance(risk, dict) and 'error' not in risk:
                vix = risk.get('vix', {})
                if isinstance(vix, dict):
                    stats['vix'] = vix.get('current')

            rates = quant.get('rates', {})
            if isinstance(rates, dict) and 'error' not in rates:
                stats['fed_rate'] = rates.get('terminal_rate')

        # Equity stats
        if isinstance(equity, dict) and 'error' not in equity:
            valuations = equity.get('valuations', {})
            if isinstance(valuations, dict):
                for region in ['us', 'europe', 'em', 'chile']:
                    v = valuations.get(region, {})
                    if isinstance(v, dict):
                        stats[f'pe_{region}'] = v.get('pe_trailing')
                        returns = v.get('returns', {})
                        if isinstance(returns, dict):
                            stats[f'return_ytd_{region}'] = returns.get('ytd')

        self.package['data_stats'] = stats
        self._print(f"    {len(stats)} estadísticas extraídas")

    # =====================================================================
    # SAVE
    # =====================================================================

    def _save(self):
        """Save package metadata to disk (charts are kept in memory for assembly)."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save metadata + briefing + stats + validation (not chart binary data)
        meta_path = OUTPUT_DIR / f"pre_council_{ts}.json"
        saveable = {
            'metadata': self.package['metadata'],
            'briefing': self.package['briefing'],
            'data_stats': self.package['data_stats'],
            'validation': self.package['validation'],
            'charts_generated': {
                rt: list(charts.keys())
                for rt, charts in self.package['charts'].items()
            },
        }
        try:
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(saveable, f, ensure_ascii=False, indent=2, default=str)
            self._print(f"    Guardado: {meta_path}")
        except Exception as e:
            logger.warning("Failed to save pre-council package: %s", e)

    # =====================================================================
    # ACCESSORS
    # =====================================================================

    def get_charts(self, report_type: str) -> Dict[str, str]:
        """Get pre-generated charts for a report type."""
        return self.package.get('charts', {}).get(report_type, {})

    def get_briefing(self, section: str = None) -> Any:
        """Get briefing text, optionally for a specific section."""
        if section:
            return self.package.get('briefing', {}).get(section, '')
        return self.package.get('briefing', {})

    def get_approved_reports(self) -> List[str]:
        """Get list of reports that passed validation."""
        return [
            rt for rt in self.reports
            if self.package.get('validation', {}).get(rt, {}).get('ok', False)
        ]

    def get_blocked_reports(self) -> List[str]:
        """Get list of reports that failed validation."""
        return [
            rt for rt in self.reports
            if not self.package.get('validation', {}).get(rt, {}).get('ok', True)
        ]

    def format_for_council(self) -> str:
        """Format the package as a text summary for the council agents."""
        lines = ["=" * 60]
        lines.append("DEPARTAMENTO DE ESTUDIOS — BRIEFING PRE-COUNCIL")
        lines.append("=" * 60)

        # Data stats
        stats = self.package.get('data_stats', {})
        if stats:
            lines.append("\nDATOS DE MERCADO CLAVE:")
            for key, val in stats.items():
                if val is not None:
                    lines.append(f"  {key}: {val}")

        # Briefing sections
        briefing = self.package.get('briefing', {})
        for section, text in briefing.items():
            if text and section not in ('research_summary', 'directives'):
                lines.append(f"\n--- {section.upper()} ---")
                lines.append(str(text)[:800])

        # Research
        research = briefing.get('research_summary', '')
        if research:
            lines.append("\n--- RESEARCH EXTERNO ---")
            lines.append(research[:1000])

        # Directives
        directives = briefing.get('directives', '')
        if directives:
            lines.append("\n--- DIRECTIVAS DEL USUARIO ---")
            lines.append(directives[:500])

        # Charts status
        lines.append("\nCHARTS PRE-GENERADOS:")
        for rt in self.reports:
            charts = self.package.get('charts', {}).get(rt, {})
            validation = self.package.get('validation', {}).get(rt, {})
            status = "OK" if validation.get('ok') else "INCOMPLETO"
            lines.append(f"  {rt.upper()}: {len(charts)} charts [{status}]")

        return '\n'.join(lines)

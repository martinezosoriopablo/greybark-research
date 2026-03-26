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

        # Render HTML briefing
        self._print("\n  -> Generando HTML briefing...")
        try:
            html_path = self.render_html()
            self.package['metadata']['html_path'] = html_path
        except Exception as e:
            logger.warning("HTML briefing generation failed: %s", e)

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
                daily_context = DailyIntelligenceDigest().format_for_council(intelligence)
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

    # =====================================================================
    # HTML REPORT — Professional Pre-Council Briefing
    # =====================================================================

    def render_html(self, output_dir: str = None) -> str:
        """Render the pre-council package as a professional HTML document.

        Returns path to the generated HTML file.
        """
        from datetime import datetime

        MONTHS_ES = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
        }

        now = datetime.now()
        fecha = f"{now.day} {MONTHS_ES[now.month]} {now.year}"
        hora = now.strftime('%H:%M')

        # Build sections
        briefing = self.package.get('briefing', {})
        stats = self.package.get('data_stats', {})
        validation = self.package.get('validation', {})
        charts = self.package.get('charts', {})
        metadata = self.package.get('metadata', {})

        # --- Market Stats Table ---
        stats_rows = ''
        stat_labels = {
            'gdp_usa': ('PIB USA QoQ', '%'),
            'unemployment_usa': ('Desempleo USA', '%'),
            'cpi_core': ('CPI Core YoY', '%'),
            'breakeven_5y': ('Breakeven 5Y', '%'),
            'breakeven_10y': ('Breakeven 10Y', '%'),
            'fed_rate': ('Fed Funds Rate', '%'),
            'tpm': ('TPM Chile', '%'),
            'imacec': ('IMACEC', '%'),
            'ipc_chile': ('IPC Chile YoY', '%'),
            'usdclp': ('USD/CLP', ''),
            'vix': ('VIX', ''),
            'pe_us': ('P/E S&P 500', 'x'),
            'pe_europe': ('P/E Europa', 'x'),
            'pe_em': ('P/E EM', 'x'),
            'pe_chile': ('P/E Chile', 'x'),
            'return_ytd_us': ('Return YTD USA', '%'),
            'return_ytd_europe': ('Return YTD Europa', '%'),
            'return_ytd_chile': ('Return YTD Chile', '%'),
        }
        for key, (label, unit) in stat_labels.items():
            val = stats.get(key)
            if val is not None:
                # Unwrap dict values (APIs return {'value': x, ...})
                if isinstance(val, dict):
                    val = val.get('value', val.get('current', val.get('latest', val.get('rate'))))
                # Unwrap numpy types
                try:
                    import numpy as np
                    if isinstance(val, (np.integer, np.floating)):
                        val = float(val)
                except (ImportError, TypeError):
                    pass
                if val is None:
                    continue
                if isinstance(val, (int, float)):
                    formatted = f"{val:,.2f}{unit}"
                else:
                    formatted = f"{val}{unit}"
                stats_rows += f'<tr><td>{label}</td><td style="text-align:right;font-weight:600">{formatted}</td></tr>\n'

        # --- Briefing Sections ---
        section_labels = {
            'macro': 'Macroeconomía',
            'rf': 'Inflación y Tasas',
            'rv': 'Renta Variable',
            'rf_credit': 'Renta Fija y Crédito',
            'riesgo': 'Riesgos y Geopolítica',
            'chile': 'Chile y LatAm',
        }
        briefing_html = ''
        for key, label in section_labels.items():
            text = briefing.get(key, '')
            if text:
                # Convert newlines to paragraphs
                paragraphs = '\n'.join(f'<p>{p.strip()}</p>' for p in str(text).split('\n') if p.strip())
                briefing_html += f'''
                <div class="briefing-section">
                    <h3>{label}</h3>
                    {paragraphs}
                </div>
                '''

        # --- Research ---
        research_html = ''
        research_text = briefing.get('research_summary', '')
        if research_text:
            paragraphs = '\n'.join(f'<p>{p.strip()}</p>' for p in str(research_text).split('\n') if p.strip())
            research_html = f'''
            <div class="briefing-section">
                <h3>Research Externo (Goldman, JPM, MS)</h3>
                {paragraphs}
            </div>
            '''

        # --- Charts Grid per Report ---
        charts_html = ''
        for report_type in self.reports:
            report_charts = charts.get(report_type, {})
            val = validation.get(report_type, {})
            status = 'OK' if val.get('ok') else f"INCOMPLETO ({len(val.get('missing', []))} faltantes)"
            status_class = 'status-ok' if val.get('ok') else 'status-warn'

            charts_html += f'''
            <div class="report-section">
                <h2>{report_type.upper()} <span class="{status_class}">[{status}]</span></h2>
                <p>{len(report_charts)} charts generados</p>
            '''

            if val.get('missing'):
                charts_html += '<div class="missing-list"><strong>Charts faltantes:</strong><ul>'
                for m in val['missing']:
                    charts_html += f'<li>{m}</li>'
                charts_html += '</ul></div>'

            # Chart grid
            if report_charts:
                charts_html += '<div class="chart-grid">'
                for chart_id, chart_data in report_charts.items():
                    if chart_data and len(chart_data) > 100:
                        # It's a base64 image or SVG
                        if chart_data.startswith('<'):
                            # SVG or HTML
                            charts_html += f'''
                            <div class="chart-card">
                                <div class="chart-title">{chart_id}</div>
                                {chart_data}
                            </div>
                            '''
                        elif 'base64' in chart_data or chart_data.startswith('data:'):
                            charts_html += f'''
                            <div class="chart-card">
                                <div class="chart-title">{chart_id}</div>
                                <img src="{chart_data}" alt="{chart_id}" style="max-width:100%">
                            </div>
                            '''
                        else:
                            # Try as raw base64
                            charts_html += f'''
                            <div class="chart-card">
                                <div class="chart-title">{chart_id}</div>
                                <img src="data:image/png;base64,{chart_data}" alt="{chart_id}" style="max-width:100%">
                            </div>
                            '''
                charts_html += '</div>'

            charts_html += '</div>'

        # --- Validation Summary ---
        validation_rows = ''
        for rt in self.reports:
            val = validation.get(rt, {})
            total = val.get('total_required', 0)
            gen = val.get('generated', 0)
            missing = len(val.get('missing', []))
            ok = val.get('ok', False)
            badge = '<span class="badge-ok">OK</span>' if ok else f'<span class="badge-warn">{missing} faltantes</span>'
            validation_rows += f'<tr><td>{rt.upper()}</td><td>{gen}</td><td>{total}</td><td>{badge}</td></tr>\n'

        # --- Directives ---
        directives_html = ''
        directives_text = briefing.get('directives', '') or self.data.get('directives', '')
        if directives_text:
            directives_html = f'''
            <div class="directives-box">
                <h3>Directivas del Usuario</h3>
                <p>{directives_text}</p>
            </div>
            '''

        # --- Full HTML ---
        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Pre-Council Briefing — Greybark Research</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 10pt;
            color: #1a1a1a;
            background: #f5f5f5;
            line-height: 1.5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; background: #fff; padding: 0; }}

        /* Header */
        .header {{
            background: #1a1a1a;
            color: #fff;
            padding: 25px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            font-family: 'Arial Black', 'Segoe UI', sans-serif;
            font-size: 18pt;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}
        .header .subtitle {{
            color: #dd6b20;
            font-size: 11pt;
            font-weight: 600;
        }}
        .header .date {{
            text-align: right;
            font-size: 9pt;
            opacity: 0.8;
        }}

        /* Sections */
        .section {{
            padding: 25px 40px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .section h2 {{
            font-size: 14pt;
            font-weight: 700;
            color: #1a1a1a;
            border-bottom: 2px solid #dd6b20;
            padding-bottom: 6px;
            margin-bottom: 15px;
        }}

        /* Stats Table */
        .stats-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 9.5pt;
        }}
        .stats-table td {{
            padding: 5px 12px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .stats-table tr:nth-child(even) {{
            background: #f7f7f7;
        }}

        /* Briefing Sections */
        .briefing-section {{
            margin-bottom: 20px;
            padding: 15px 20px;
            background: #fafafa;
            border-left: 3px solid #dd6b20;
        }}
        .briefing-section h3 {{
            font-size: 11pt;
            color: #1a1a1a;
            margin-bottom: 8px;
        }}
        .briefing-section p {{
            font-size: 9.5pt;
            margin-bottom: 6px;
            color: #2d3748;
        }}

        /* Charts */
        .report-section {{
            padding: 20px 40px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .report-section h2 {{
            font-size: 13pt;
            margin-bottom: 10px;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        .chart-card {{
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 10px;
            background: #fff;
        }}
        .chart-card img {{
            width: 100%;
            height: auto;
        }}
        .chart-title {{
            font-size: 8.5pt;
            font-weight: 600;
            color: #4a5568;
            margin-bottom: 5px;
            text-transform: uppercase;
        }}

        /* Badges */
        .badge-ok {{
            background: #276749; color: #fff;
            padding: 2px 8px; border-radius: 3px; font-size: 8.5pt;
        }}
        .badge-warn {{
            background: #c53030; color: #fff;
            padding: 2px 8px; border-radius: 3px; font-size: 8.5pt;
        }}
        .status-ok {{ color: #276749; font-size: 9pt; }}
        .status-warn {{ color: #c53030; font-size: 9pt; }}

        /* Validation Table */
        .validation-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 9.5pt;
        }}
        .validation-table th {{
            background: #1a1a1a; color: #fff;
            padding: 8px 12px; text-align: left;
        }}
        .validation-table td {{
            padding: 6px 12px; border-bottom: 1px solid #e2e8f0;
        }}

        /* Missing list */
        .missing-list {{
            background: #fff5f5; border: 1px solid #fed7d7;
            padding: 10px 15px; margin: 10px 0; border-radius: 4px;
            font-size: 9pt;
        }}
        .missing-list ul {{ margin-left: 20px; }}

        /* Directives */
        .directives-box {{
            background: #fffff0; border: 2px solid #dd6b20;
            padding: 15px 20px; margin: 15px 0; border-radius: 4px;
        }}
        .directives-box h3 {{ color: #dd6b20; margin-bottom: 8px; }}

        /* Footer */
        .footer {{
            background: #f7f7f7;
            border-top: 2px solid #1a1a1a;
            padding: 15px 40px;
            text-align: center;
            font-size: 8pt;
            color: #718096;
        }}

        /* Print */
        @media print {{
            body {{ background: #fff; }}
            .chart-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .report-section, .section {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="header">
        <div>
            <h1>Greybark Research</h1>
            <div class="subtitle">Pre-Council Briefing — Departamento de Estudios</div>
        </div>
        <div class="date">
            {fecha}<br>{hora}<br>
            Build: {metadata.get('build_time_seconds', '?')}s
        </div>
    </div>

    {directives_html}

    <!-- Validation Summary -->
    <div class="section">
        <h2>Estado de Datos por Reporte</h2>
        <table class="validation-table">
            <tr><th>Reporte</th><th>Charts Generados</th><th>Charts Required</th><th>Estado</th></tr>
            {validation_rows}
        </table>
    </div>

    <!-- Market Stats -->
    <div class="section">
        <h2>Datos de Mercado Verificados</h2>
        <table class="stats-table">
            {stats_rows}
        </table>
    </div>

    <!-- Intelligence Briefing -->
    <div class="section">
        <h2>Briefing de Inteligencia</h2>
        {briefing_html}
        {research_html}
    </div>

    <!-- Charts by Report -->
    {charts_html}

    <!-- Footer -->
    <div class="footer">
        Greybark Research — Pre-Council Briefing — Generado {fecha} {hora}<br>
        Documento interno. No distribuir sin autorización.
    </div>

</div>
</body>
</html>'''

        # Save
        out_dir = Path(output_dir) if output_dir else Path(__file__).parent / "output" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = now.strftime('%Y%m%d')
        path = out_dir / f"pre_council_briefing_{ts}.html"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"    HTML Briefing: {path}")
        return str(path)

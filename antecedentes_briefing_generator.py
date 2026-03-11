# -*- coding: utf-8 -*-
"""
Greybark Research — Libro de Antecedentes Generator
=====================================================

Genera el documento completo pre-council con todos los datos, gráficos,
tablas y narrativas del Intelligence Digest. Sirve como briefing para
el gestor humano y documentación de lo que reciben los agentes IA.

Fase 2.2 del pipeline mensual.

Uso:
    gen = AntecedentesBriefingGenerator(data, completeness, branding)
    path = gen.render()
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

GREYBARK_PATH = Path(__file__).parent.parent / "02_greybark_library"
sys.path.insert(0, str(GREYBARK_PATH))

MONTHS_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}

# Category → CSS class for theme cards
CATEGORY_CSS = {
    'Política Monetaria': 'cat-monetaria',
    'Inflación': 'cat-inflacion',
    'Crecimiento': 'cat-crecimiento',
    'Geopolítica': 'cat-geopolitica',
    'Tecnología': 'cat-tecnologia',
    'Chile': 'cat-chile',
    'Riesgo': 'cat-riesgo',
}

TREND_ARROWS = {
    'creciente': '<span class="trend-up">&#9650;</span>',
    'decreciente': '<span class="trend-down">&#9660;</span>',
    'estable': '<span class="trend-flat">&#9654;</span>',
    'nuevo': '<span style="color:#dd6b20">&#9733;</span>',
}


class AntecedentesBriefingGenerator:
    """Generates the comprehensive Libro de Antecedentes (Phase 2.2)."""

    def __init__(
        self,
        data: Dict[str, Any],
        completeness=None,
        branding: dict = None,
        verbose: bool = True,
    ):
        self.data = data
        self.completeness = completeness
        self.branding = branding or {}
        self.verbose = verbose
        self.now = datetime.now()
        self.date_str = self.now.strftime('%Y-%m-%d')
        self._charts: Dict[str, str] = {}

        # Shortcuts
        self.mq = data.get('macro_quant', {})
        self.intel = data.get('intelligence', {})

        # Chart tools (lazy init)
        self._macro_charts = None
        self._init_charts()

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _init_charts(self):
        """Initialize chart generators (reuse existing MacroChartsGenerator)."""
        try:
            from bloomberg_reader import BloombergData
            bbg = BloombergData()
            bbg_obj = bbg if bbg.available else None
        except Exception:
            bbg_obj = None

        try:
            from chart_data_provider import ChartDataProvider
            from chart_generator import MacroChartsGenerator
            dp = ChartDataProvider(lookback_months=120, bloomberg=bbg_obj)
            self._macro_charts = MacroChartsGenerator(
                data_provider=dp,
                forecast_data=self.data.get('forecasts'),
                branding=self.branding,
            )
            self._print("[Briefing] Chart tools initialized")
        except Exception as e:
            self._print(f"[Briefing] Charts unavailable: {e}")

    # ═══════════════════════════════════════════════════════════════
    # HTML HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _fv(self, val, unit: str = '', decimals: int = 1) -> str:
        """Format a value for display. Unwraps dict/numpy types from APIs."""
        # Unwrap dict values (FRED/OECD/yfinance return structured dicts)
        if isinstance(val, dict):
            val = val.get('value', val.get('current', val.get('latest', val.get('rate'))))
        # Handle numpy types
        try:
            import numpy as np
            if isinstance(val, (np.integer, np.floating)):
                val = float(val)
        except (ImportError, TypeError):
            pass
        if val is None:
            return '<span style="color:#a0aec0">N/D</span>'
        if isinstance(val, (int, float)):
            s = f'{val:,.{decimals}f}'
            if unit:
                s += f' {unit}'
            return f'<code>{s}</code>'
        return str(val)

    def _arrow(self, current, previous) -> str:
        """Change arrow with color. Unwraps dict types."""
        if isinstance(current, dict):
            current = current.get('value', current.get('current', current.get('latest')))
        if isinstance(previous, dict):
            previous = previous.get('value', previous.get('current', previous.get('latest')))
        if current is None or previous is None:
            return ''
        try:
            diff = float(current) - float(previous)
        except (TypeError, ValueError):
            return ''
        if diff > 0.01:
            return f'<span class="trend-up">&#9650; +{diff:.1f}</span>'
        elif diff < -0.01:
            return f'<span class="trend-down">&#9660; {diff:.1f}</span>'
        return '<span class="trend-flat">&#9654; 0.0</span>'

    def _sg(self, d: dict, *keys, default=None):
        """Safe nested get."""
        cur = d
        for k in keys:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(k, default)
            if cur is default:
                return default
        return cur

    def _table(self, headers: List[str], rows: List[list], title: str = '') -> str:
        """Render a data table."""
        html = ''
        if title:
            html += f'<h4 class="subsection-title">{title}</h4>\n'
        html += '<table class="data-table"><thead><tr>'
        for i, h in enumerate(headers):
            cls = ' class="right"' if i > 0 else ''
            html += f'<th{cls}>{h}</th>'
        html += '</tr></thead><tbody>\n'
        for row in rows:
            html += '<tr>'
            for i, cell in enumerate(row):
                cls = ' class="right"' if i > 0 else ''
                html += f'<td{cls}>{cell}</td>'
            html += '</tr>\n'
        html += '</tbody></table>\n'
        return html

    # ═══════════════════════════════════════════════════════════════
    # CHART GENERATION
    # ═══════════════════════════════════════════════════════════════

    def _generate_all_charts(self):
        """Generate all charts via MacroChartsGenerator (reuse)."""
        if not self._macro_charts:
            return

        chart_map = {
            'yield_curve': '_generate_yield_curve',
            'yield_spreads': '_generate_yield_spreads',
            'inflation_evolution': '_generate_inflation_evolution',
            'labor_unemployment': '_generate_labor_unemployment',
            'pmi_global': '_generate_pmi_global',
            'usa_leading': '_generate_usa_leading_indicators',
            'inflation_components_ts': '_generate_inflation_components_ts',
            'europe_dashboard': '_generate_europe_dashboard',
            'europe_pmi': '_generate_europe_pmi',
            'china_dashboard': '_generate_china_dashboard',
            'china_trade': '_generate_china_trade_chart',
            'chile_dashboard': '_generate_chile_dashboard',
            'chile_inflation_components': '_generate_chile_inflation_components',
            'chile_external': '_generate_chile_external_chart',
            'latam_rates': '_generate_latam_rates',
            'commodity_prices': '_generate_commodity_prices',
            'global_equities': '_generate_global_equities',
            'epu_geopolitics': '_generate_epu_geopolitics',
            'fed_vs_ecb_bcch': '_generate_policy_rates_comparison',
        }

        for chart_id, method_name in chart_map.items():
            try:
                method = getattr(self._macro_charts, method_name, None)
                if method:
                    result = method()
                    if result:
                        self._charts[chart_id] = result
            except Exception as e:
                self._print(f"  [WARN] Chart '{chart_id}': {e}")

        self._generate_embi_bar_chart()
        self._print(f"[Briefing] {len(self._charts)} charts generated")

    def _generate_embi_bar_chart(self):
        """EMBI spreads horizontal bar chart."""
        bcrp = self.mq.get('bcrp_embi', {})
        if not bcrp or 'error' in bcrp:
            return
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            import io, base64

            names = []
            vals = []
            colors = []
            for campo in ['embi_chile', 'embi_peru', 'embi_brasil', 'embi_mexico',
                          'embi_colombia', 'embi_argentina', 'embi_latam', 'embi_total']:
                entry = bcrp.get(campo, {})
                if isinstance(entry, dict) and 'latest' in entry:
                    label = campo.replace('embi_', '').title()
                    names.append(label)
                    vals.append(entry['latest'])
                    colors.append('#dd6b20' if campo == 'embi_chile' else '#4a5568')

            if not names:
                return

            fig, ax = plt.subplots(figsize=(7, 3.5))
            y_pos = range(len(names))
            ax.barh(y_pos, vals, color=colors, height=0.6)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(names, fontsize=9)
            ax.set_xlabel('Spread (bps)', fontsize=9)
            ax.set_title('EMBI Global Spreads', fontsize=11, fontweight='bold')
            ax.invert_yaxis()
            for i, v in enumerate(vals):
                ax.text(v + 5, i, f'{v:.0f}', va='center', fontsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            self._charts['embi_spreads'] = 'data:image/png;base64,' + base64.b64encode(buf.read()).decode()
        except Exception as e:
            self._print(f"  [WARN] EMBI chart: {e}")

    # ═══════════════════════════════════════════════════════════════
    # SECTION BUILDERS
    # ═══════════════════════════════════════════════════════════════

    def _build_header_section(self) -> Dict:
        """Summary cards row."""
        comp = self.completeness
        total = 0
        present = 0
        verdict = 'N/A'
        req_pct = 0

        if comp:
            try:
                cd = comp if isinstance(comp, dict) else comp.to_dict()
                for ag in cd.get('agents', {}).values():
                    total += ag.get('required_total', 0) + ag.get('important_total', 0) + ag.get('optional_total', 0)
                    present += ag.get('required_present', 0) + ag.get('important_present', 0) + ag.get('optional_present', 0)
                verdict = cd.get('verdict', 'N/A')
                req_total = sum(a.get('required_total', 0) for a in cd.get('agents', {}).values())
                req_present = sum(a.get('required_present', 0) for a in cd.get('agents', {}).values())
                req_pct = (req_present / req_total * 100) if req_total else 0
            except Exception:
                pass

        cov_pct = (present / total * 100) if total else 0
        v_cls = 'card-go' if verdict == 'GO' else ('card-caution' if verdict == 'CAUTION' else 'card-nogo')
        v_badge_cls = 'verdict-go' if verdict == 'GO' else ('verdict-caution' if verdict == 'CAUTION' else 'verdict-no_go')

        cards = f'''<div class="summary-cards">
            <div class="summary-card"><div class="card-icon">&#128202;</div>
                <div class="card-value">11</div><div class="card-label">APIs Activas</div></div>
            <div class="summary-card"><div class="card-icon">&#128203;</div>
                <div class="card-value">{total}</div><div class="card-label">Campos Totales</div></div>
            <div class="summary-card"><div class="card-icon">&#9989;</div>
                <div class="card-value">{cov_pct:.0f}%</div><div class="card-label">Cobertura Total</div></div>
            <div class="summary-card {v_cls}"><div class="card-icon">&#128161;</div>
                <div class="card-value"><span class="verdict-badge {v_badge_cls}">{verdict}</span></div>
                <div class="card-label">Required {req_pct:.0f}%</div></div>
        </div>'''

        return {'id': 'header', 'title': '', 'html': '', 'chart_ids': [],
                '_summary_cards': cards,
                '_verdict_badge': f'<span class="verdict-badge {v_badge_cls}">{verdict}</span>'}

    def _build_regime_section(self) -> Dict:
        """Regime classification."""
        regime = self.mq.get('regime', {})
        if 'error' in regime:
            return {'id': 'regime', 'title': 'II. Regimen de Mercado',
                    'html': '<p>Datos de régimen no disponibles.</p>', 'chart_ids': []}

        current = regime.get('current_regime', 'UNKNOWN')
        score = regime.get('score', 0)
        desc = regime.get('description', '')
        probs = regime.get('probabilities', {})
        indicators = regime.get('indicators', {})

        css_cls = f'regime-{current.lower()}'
        html = f'<div class="regime-container">'
        html += f'<div class="regime-badge {css_cls}">{current}</div>'
        html += f'<div class="regime-score">Score: {score:+.2f} &mdash; {desc}</div></div>'

        # Probability bars
        if probs:
            html += '<div class="prob-bars">'
            colors = {'EXPANSION': '#48bb78', 'MODERATE_GROWTH': '#a0aec0',
                      'LATE_CYCLE_BOOM': '#ecc94b', 'SLOWDOWN': '#fc8181', 'RECESSION': '#c53030'}
            for regime_name, prob in sorted(probs.items(), key=lambda x: -x[1]):
                pct = prob * 100 if prob <= 1 else prob
                color = colors.get(regime_name, '#a0aec0')
                html += f'''<div class="prob-row">
                    <div class="prob-label">{regime_name}</div>
                    <div class="prob-bar-bg"><div class="prob-bar-fill" style="width:{pct:.0f}%;background:{color}">{pct:.1f}%</div></div>
                </div>'''
            html += '</div>'

        # Indicators table
        if indicators:
            rows = []
            for k, v in indicators.items():
                try:
                    nv = float(v)
                    rows.append([k, f'<code>{nv:+.0f}</code>',
                                 '<span class="trend-up">Soporte</span>' if nv > 0 else '<span class="trend-down">Riesgo</span>',
                                 abs(nv)])
                except (TypeError, ValueError):
                    rows.append([k, str(v), '', 0])
            rows.sort(key=lambda x: -x[3])
            rows = [[r[0], r[1], r[2]] for r in rows]
            html += self._table(['Indicador', 'Score', 'Señal'], rows, 'Indicadores')

        return {'id': 'regime', 'title': 'II. Regimen de Mercado', 'html': html, 'chart_ids': []}

    def _build_usa_section(self) -> Dict:
        """Estados Unidos: macro, inflation, BEA, Fed, NY Fed."""
        html = ''
        macro = self.mq.get('macro_usa', {})
        inflation = self.mq.get('inflation', {})
        bea = self.mq.get('bea', {})
        nyfed = self.mq.get('nyfed', {})
        rates = self.mq.get('rates', {})
        lei = self.mq.get('leading_indicators', {})

        # Key Macro table — FRED returns structured dicts; _fv() unwraps 'value'
        rows = [
            ['GDP Real QoQ', self._fv(self._sg(macro, 'gdp'), '%'),
             self._sg(macro, 'gdp', 'period', default='')],
            ['Desempleo', self._fv(self._sg(macro, 'unemployment'), '%'),
             self._arrow(self._sg(macro, 'unemployment', 'value'),
                         self._sg(macro, 'unemployment', 'prev'))],
            ['Payrolls (NFP)', self._fv(self._sg(macro, 'payrolls'), 'K', 0), ''],
            ['Retail Sales MoM', self._fv(self._sg(macro, 'retail_sales'), '%'), ''],
            ['Retail Sales YoY', self._fv(self._sg(macro, 'retail_sales', 'yoy'), '%'), ''],
            ['Industrial Prod MoM', self._fv(self._sg(macro, 'industrial_prod'), '%'), ''],
            ['Housing Starts', self._fv(self._sg(macro, 'housing_starts'), 'M', 2), ''],
            ['Durable Goods MoM', self._fv(self._sg(macro, 'durable_goods'), '%'), ''],
        ]
        html += self._table(['Indicador', 'Valor', ''], rows, 'Macro USA')

        # Inflation detail
        rows = [
            ['CPI All Items YoY', self._fv(self._sg(inflation, 'cpi_all_yoy'), '%'), ''],
            ['CPI Core YoY', self._fv(self._sg(inflation, 'cpi_core_yoy'), '%'), ''],
            ['CPI Services YoY', self._fv(self._sg(inflation, 'cpi_services_yoy'), '%'),
             self._sg(inflation, 'services_status', default='')],
            ['Breakeven 5Y', self._fv(self._sg(inflation, 'breakeven_5y'), '%'), ''],
            ['Breakeven 10Y', self._fv(self._sg(inflation, 'breakeven_10y'), '%'), ''],
            ['Forward 5Y5Y', self._fv(self._sg(inflation, 'forward_5y5y'), '%'), ''],
            ['Real Rate 10Y (TIPS)', self._fv(self._sg(inflation, 'real_rate_10y'), '%'), ''],
        ]
        html += self._table(['Indicador', 'Valor', 'Status'], rows, 'Inflacion')

        # BEA
        if bea and 'error' not in bea:
            bea_rows = []
            gdp = bea.get('gdp', {})
            if isinstance(gdp, dict) and '_source' in gdp:
                bea_rows.append(['GDP Real QoQ (BEA)', self._fv(gdp.get('real_gdp_qoq'), '%'), ''])
            pce = bea.get('pce_inflation', {})
            if isinstance(pce, dict) and '_source' in pce:
                bea_rows.append(['PCE Headline YoY', self._fv(pce.get('pce_headline_yoy'), '%'), ''])
                bea_rows.append(['PCE Core YoY', self._fv(pce.get('pce_core_yoy'), '%'), ''])
            income = bea.get('personal_income', {})
            if isinstance(income, dict) and '_source' in income:
                bea_rows.append(['Personal Income MoM', self._fv(income.get('personal_income_mom'), '%'), ''])
                bea_rows.append(['Saving Rate', self._fv(income.get('saving_rate'), '%'), ''])
            profits = bea.get('corporate_profits', {})
            if isinstance(profits, dict) and '_source' in profits:
                bea_rows.append(['Corporate Profits QoQ', self._fv(profits.get('profits_qoq'), '%'), ''])
            if bea_rows:
                html += self._table(['BEA', 'Valor', ''], bea_rows, 'Bureau of Economic Analysis')

        # Leading Indicators
        if lei and 'error' not in lei:
            lei_rows = [
                ['LEI USA (OECD CLI)', self._fv(self._sg(lei, 'lei_usa'), '', 2),
                 self._sg(lei, 'lei_usa', 'trend', default='')],
                ['LEI Eurozone', self._fv(self._sg(lei, 'lei_eurozone'), '', 2), ''],
                ['Consumer Conf EZ', self._fv(self._sg(lei, 'consumer_confidence_ez'), '', 1), ''],
                ['CFNAI', self._fv(self._sg(lei, 'cfnai'), '', 2),
                 self._sg(lei, 'cfnai', 'trend', default='')],
                ['U.Mich Sentiment', self._fv(self._sg(lei, 'umich_sentiment'), '', 1), ''],
            ]
            html += self._table(['Leading Indicator', 'Valor', 'Status'], lei_rows, 'Leading Indicators')

        # Fed Expectations
        fed = rates.get('fed_expectations', {})
        if fed:
            html += f'<h4 class="subsection-title">Fed Expectations</h4>'
            direction = rates.get('direction', '')
            cuts = rates.get('cuts_expected', 0)
            terminal = rates.get('terminal_rate')
            html += f'<p style="margin:8px 0;font-size:9.5pt"><strong>Direction:</strong> {direction} &mdash; '
            html += f'<strong>Cuts:</strong> {cuts} &mdash; '
            html += f'<strong>Terminal:</strong> {self._fv(terminal, "%")}</p>'

            meetings = fed.get('meetings', [])
            if meetings:
                m_rows = []
                for m in meetings[:6]:
                    m_rows.append([
                        m.get('meeting', ''),
                        self._fv(m.get('expected_rate'), '%', 2),
                        m.get('scenarios', [{}])[0].get('action', '') if m.get('scenarios') else '',
                    ])
                html += self._table(['Reunión', 'Tasa Esperada', 'Escenario'], m_rows)

        # NY Fed
        if nyfed and 'error' not in nyfed:
            nyfed_rows = []
            ref = nyfed.get('reference_rates', {})
            if isinstance(ref, dict):
                nyfed_rows.append(['SOFR', self._fv(ref.get('sofr'), '%', 2), ''])
                nyfed_rows.append(['EFFR', self._fv(ref.get('effr'), '%', 2), ''])
            rstar = nyfed.get('rstar', {})
            if isinstance(rstar, dict):
                nyfed_rows.append(['R* (Laubach-Williams)', self._fv(rstar.get('value'), '%', 2),
                                   rstar.get('date', '')])
            gscpi = nyfed.get('gscpi', {})
            if isinstance(gscpi, dict):
                nyfed_rows.append(['GSCPI', self._fv(gscpi.get('value'), '', 2), gscpi.get('date', '')])
            tp = nyfed.get('term_premia', {})
            if isinstance(tp, dict):
                nyfed_rows.append(['Term Premium 10Y', self._fv(tp.get('tp_10y'), '%', 2), ''])
            if nyfed_rows:
                html += self._table(['NY Fed', 'Valor', 'Período'], nyfed_rows, 'NY Fed')

        charts = ['yield_curve', 'yield_spreads', 'inflation_evolution', 'labor_unemployment',
                  'pmi_global', 'usa_leading', 'inflation_components_ts']
        return {'id': 'usa', 'title': 'III. Estados Unidos', 'html': html, 'chart_ids': charts}

    def _build_europe_section(self) -> Dict:
        """Europa & Zona Euro."""
        html = ''
        ecb = self.mq.get('ecb', {})
        oecd = self.mq.get('oecd', {})
        intl = self.mq.get('international', {})

        # ECB table
        if ecb and 'error' not in ecb:
            ECB_LABELS = {
                'ecb_dfr': ('Deposit Facility Rate', '%'),
                'hicp_euro_yoy': ('HICP Euro YoY', '%'),
                'ea_10y_yield': ('EA 10Y Yield', '%'),
                'eur_usd': ('EUR/USD', ''),
                'm3_euro_stock': ('M3 (EUR mn)', 'mn'),
            }
            rows = []
            for key, (label, unit) in ECB_LABELS.items():
                val = ecb.get(key)
                rows.append([label, self._fv(val, unit, 2 if unit != 'mn' else 0)])
            html += self._table(['ECB', 'Valor'], rows, 'Banco Central Europeo')

        # OECD table
        if oecd and 'error' not in oecd:
            for indicator_name, indicator_key in [('CLI (Composite Leading)', 'cli'),
                                                   ('Consumer Confidence', 'cci'),
                                                   ('Business Confidence', 'bci')]:
                ind_data = oecd.get(indicator_key, {})
                if ind_data and isinstance(ind_data, dict) and len(ind_data) > 1:
                    rows = [[country, self._fv(val, '', 2)]
                            for country, val in sorted(ind_data.items())
                            if country not in ('_source', 'timestamp', 'period')]
                    if rows:
                        html += self._table(['País', indicator_name], rows[:10])

        # International bonds
        bonds = intl.get('bonds_10y', {})
        if bonds and isinstance(bonds, dict):
            rows = [[k, self._fv(v, '%', 2)] for k, v in sorted(bonds.items())
                    if v is not None and k not in ('_source', 'timestamp')]
            if rows:
                html += self._table(['País', 'Bono 10Y'], rows[:10], 'Bonos Soberanos 10Y')

        return {'id': 'europe', 'title': 'IV. Europa & Zona Euro', 'html': html,
                'chart_ids': ['europe_dashboard', 'europe_pmi']}

    def _build_china_section(self) -> Dict:
        """China — AKShare NBS + Bloomberg."""
        html = ''
        ak = self.mq.get('akshare_china', {})

        if not ak or 'error' in ak:
            html = '<p>Datos de China no disponibles.</p>'
            return {'id': 'china', 'title': 'V. China', 'html': html,
                    'chart_ids': ['china_dashboard', 'china_trade']}

        # PMI
        pmi_rows = [
            ['PMI Manufacturing (NBS)', self._fv(ak.get('pmi_mfg')), self._arrow(ak.get('pmi_mfg'), ak.get('pmi_mfg_prev'))],
            ['PMI Services (NBS)', self._fv(ak.get('pmi_svc')), self._arrow(ak.get('pmi_svc'), ak.get('pmi_svc_prev'))],
            ['Caixin Mfg', self._fv(ak.get('caixin_mfg')), self._arrow(ak.get('caixin_mfg'), ak.get('caixin_mfg_prev'))],
            ['Caixin Services', self._fv(ak.get('caixin_svc')), self._arrow(ak.get('caixin_svc'), ak.get('caixin_svc_prev'))],
        ]
        html += self._table(['PMI', 'Actual', 'vs Anterior'], pmi_rows, 'PMI')

        # Prices
        price_rows = [
            ['CPI YoY', self._fv(ak.get('cpi_yoy'), '%'), self._arrow(ak.get('cpi_yoy'), ak.get('cpi_yoy_prev'))],
            ['PPI YoY', self._fv(ak.get('ppi_yoy'), '%'), self._arrow(ak.get('ppi_yoy'), ak.get('ppi_yoy_prev'))],
        ]
        html += self._table(['Precios', 'Actual', 'vs Anterior'], price_rows, 'Precios')

        # Credit
        credit_rows = [
            ['M2 YoY', self._fv(ak.get('m2_yoy'), '%'), self._arrow(ak.get('m2_yoy'), ak.get('m2_yoy_prev'))],
            ['TSF', self._fv(ak.get('tsf'), '亿元', 0), ''],
            ['New Loans', self._fv(ak.get('new_loans'), '亿元', 0), ''],
        ]
        html += self._table(['Crédito', 'Actual', 'vs Anterior'], credit_rows, 'Crédito y Liquidez')

        # Activity
        activity_rows = [
            ['Industrial Prod YoY', self._fv(ak.get('industrial_prod_yoy'), '%'),
             self._arrow(ak.get('industrial_prod_yoy'), ak.get('industrial_prod_yoy_prev'))],
            ['Retail Sales YoY', self._fv(ak.get('retail_sales_yoy'), '%'),
             self._arrow(ak.get('retail_sales_yoy'), ak.get('retail_sales_yoy_prev'))],
        ]
        html += self._table(['Actividad', 'Actual', 'vs Anterior'], activity_rows, 'Actividad')

        # Trade
        trade_rows = [
            ['Exports YoY', self._fv(ak.get('exp_yoy'), '%'), self._arrow(ak.get('exp_yoy'), ak.get('exp_yoy_prev'))],
            ['Imports YoY', self._fv(ak.get('imp_yoy'), '%'), self._arrow(ak.get('imp_yoy'), ak.get('imp_yoy_prev'))],
            ['Trade Balance', self._fv(ak.get('trade_bal'), 'USD bn'), ''],
        ]
        html += self._table(['Comercio', 'Actual', 'vs Anterior'], trade_rows, 'Comercio Exterior')

        # Policy
        policy_rows = [
            ['LPR 1Y', self._fv(ak.get('lpr_1y'), '%'), self._arrow(ak.get('lpr_1y'), ak.get('lpr_1y_prev'))],
            ['LPR 5Y', self._fv(ak.get('lpr_5y'), '%'), self._arrow(ak.get('lpr_5y'), ak.get('lpr_5y_prev'))],
            ['RRR', self._fv(ak.get('rrr'), '%'), self._arrow(ak.get('rrr'), ak.get('rrr_prev'))],
        ]
        html += self._table(['Política', 'Actual', 'vs Anterior'], policy_rows, 'PBOC / Política')

        # Property
        prop_rows = [
            ['Home Price YoY Tier 1', self._fv(ak.get('home_price_yoy_tier1'), '%'), ''],
            ['Home Price YoY Beijing', self._fv(ak.get('home_price_yoy_bj'), '%'), ''],
            ['Home Price YoY Shanghai', self._fv(ak.get('home_price_yoy_sh'), '%'), ''],
        ]
        html += self._table(['Propiedad', 'Actual', ''], prop_rows, 'Propiedad (NBS 70 Ciudades)')

        return {'id': 'china', 'title': 'V. China', 'html': html,
                'chart_ids': ['china_dashboard', 'china_trade']}

    def _build_chile_latam_section(self) -> Dict:
        """Chile & LatAm."""
        html = ''
        chile = self.mq.get('chile', {})
        ext = self.mq.get('chile_extended', {})
        bcrp = self.mq.get('bcrp_embi', {})
        imf = self.mq.get('imf_weo', {})

        # Merge chile + chile_extended.macro for best coverage
        ext_macro = ext.get('macro', {}) if isinstance(ext, dict) else {}
        # chile_extended.macro has: tpm, ipc_yoy, imacec_yoy, desempleo, usd_clp, uf, ipec
        # chile (ChileAnalytics) has: tpm, ipc, imacec, usd_clp, uf, copper
        chile_rows = [
            ['TPM', self._fv(ext_macro.get('tpm') or chile.get('tpm'), '%'), ''],
            ['IPC YoY', self._fv(ext_macro.get('ipc_yoy') or chile.get('ipc'), '%'), ''],
            ['IMACEC YoY', self._fv(ext_macro.get('imacec_yoy') or chile.get('imacec'), '%'), ''],
            ['Desempleo', self._fv(ext_macro.get('desempleo'), '%'), ''],
            ['USD/CLP', self._fv(ext_macro.get('usd_clp') or chile.get('usd_clp'), '', 0), ''],
            ['UF', self._fv(ext_macro.get('uf') or chile.get('uf'), '', 0), ''],
            ['IPEC (Confianza)', self._fv(ext_macro.get('ipec')), ''],
            ['TPM Real', self._fv(ext_macro.get('tpm_real') or chile.get('real_tpm'), '%', 2), ''],
        ]
        html += self._table(['Chile', 'Valor', ''], chile_rows, 'Chile Macro')

        # EEE Expectations
        eee = ext.get('eee_expectations', {})
        if eee and isinstance(eee, dict) and 'error' not in eee:
            eee_rows = []
            for k, v in eee.items():
                if k not in ('_source', 'timestamp', 'error') and v is not None:
                    eee_rows.append([k.replace('_', ' ').title(), self._fv(v, '', 2)])
            if eee_rows:
                html += self._table(['EEE (Encuesta Expectativas)', 'Valor'], eee_rows, 'Expectativas EEE')

        # IMCE
        imce = ext.get('imce', {})
        if imce and isinstance(imce, dict) and 'error' not in imce:
            imce_rows = [[k.replace('_', ' ').title(), self._fv(v)]
                         for k, v in imce.items()
                         if k not in ('_source', 'timestamp', 'error') and v is not None]
            if imce_rows:
                html += self._table(['IMCE', 'Valor'], imce_rows, 'IMCE (Confianza Empresarial)')

        # SPC Curve
        spc = ext.get('spc_curve', {})
        if spc and isinstance(spc, dict) and 'error' not in spc:
            spc_rows = [[k.upper(), self._fv(v, '%', 2)]
                        for k, v in spc.items()
                        if k not in ('_source', 'timestamp', 'error') and v is not None]
            if spc_rows:
                html += self._table(['Instrumento', 'Tasa'], spc_rows, 'Curva SPC (Mercado Secundario)')

        # IPC Detail
        ipc_d = ext.get('ipc_detail', {})
        if ipc_d and isinstance(ipc_d, dict) and 'error' not in ipc_d:
            ipc_rows = [[k.replace('_', ' ').title(), self._fv(v, '%', 2)]
                        for k, v in ipc_d.items()
                        if k not in ('_source', 'timestamp', 'error') and v is not None]
            if ipc_rows:
                html += self._table(['Componente IPC', 'Valor'], ipc_rows, 'IPC Detalle')

        # Commodities
        commodities = ext.get('commodities', {})
        if commodities and isinstance(commodities, dict) and 'error' not in commodities:
            comm_rows = [[k.replace('_', ' ').title(), self._fv(v, '', 2)]
                         for k, v in commodities.items()
                         if k not in ('_source', 'timestamp', 'error') and v is not None]
            if comm_rows:
                html += self._table(['Commodity', 'Precio'], comm_rows, 'Commodities')

        # EMBI Spreads
        if bcrp and 'error' not in bcrp:
            embi_rows = []
            for campo in ['embi_chile', 'embi_peru', 'embi_brasil', 'embi_mexico',
                          'embi_colombia', 'embi_argentina', 'embi_latam', 'embi_total']:
                entry = bcrp.get(campo, {})
                if isinstance(entry, dict) and 'latest' in entry:
                    label = campo.replace('embi_', '').title()
                    chg = entry.get('chg')
                    chg_str = f'<span class="{"trend-up" if chg and chg > 0 else "trend-down"}">{chg:+.0f}</span>' if chg else ''
                    embi_rows.append([label, self._fv(entry['latest'], 'bps', 0),
                                     entry.get('date', ''), chg_str])
            if embi_rows:
                html += self._table(['EMBI', 'Spread', 'Fecha', 'Chg MoM'], embi_rows, 'EMBI Global Spreads (BCRP)')

        # IMF WEO Consensus
        if imf and 'error' not in imf:
            gdp = imf.get('gdp', {})
            inf = imf.get('inflation', {})
            if gdp or inf:
                weo_rows = []
                for country in ['usa', 'eurozone', 'china', 'chile', 'world']:
                    label = country.upper() if country != 'eurozone' else 'Eurozone'
                    weo_rows.append([label, self._fv(gdp.get(country), '%'),
                                    self._fv(inf.get(country), '%')])
                html += self._table(['País', 'GDP 2026 (%)', 'Inflation 2026 (%)'], weo_rows,
                                    f'IMF WEO Consensus — {imf.get("source", "")}')

        charts = ['chile_dashboard', 'chile_inflation_components', 'chile_external',
                  'latam_rates', 'commodity_prices', 'embi_spreads']
        return {'id': 'chile_latam', 'title': 'VI. Chile & LatAm', 'html': html, 'chart_ids': charts}

    def _build_markets_risk_section(self) -> Dict:
        """Markets & Risk."""
        html = ''
        risk = self.mq.get('risk', {})
        breadth = self.mq.get('breadth', {})
        av = self.mq.get('alphavantage', {})
        bbg = self.mq.get('bloomberg', {})
        intl = self.mq.get('international', {})

        # Equity Indices
        indices = intl.get('stock_indices', {})
        if indices and isinstance(indices, dict):
            idx_rows = [[k, self._fv(v, '', 2)] for k, v in sorted(indices.items())
                        if v is not None and k not in ('_source', 'timestamp')]
            if idx_rows:
                html += self._table(['Indice', 'Valor'], idx_rows, 'Indices Bursátiles')

        # Risk Metrics — only show rows with data (yfinance-dependent)
        if risk and 'error' not in risk:
            _risk_fields = [
                ('VIX', 'vix', '', 1),
                ('VaR 95% Daily', 'var_95_daily', '%', 2),
                ('VaR 99% Daily', 'var_99_daily', '%', 2),
                ('Expected Shortfall 95%', 'es_95', '%', 2),
                ('Max Drawdown', 'max_drawdown', '%', 2),
                ('Current Drawdown', 'current_drawdown', '%', 2),
                ('Diversification Score', 'diversification_score', '', 2),
            ]
            risk_rows = []
            for label, key, unit, dec in _risk_fields:
                val = risk.get(key)
                if val is not None:
                    risk_rows.append([label, self._fv(val, unit, dec), ''])
            if risk_rows:
                html += self._table(['Métrica', 'Valor', ''], risk_rows, 'Métricas de Riesgo')

        # Breadth — only show rows with data (yfinance-dependent)
        if breadth and 'error' not in breadth:
            br_rows = []
            if breadth.get('pct_above_50ma') is not None:
                br_rows.append(['% Above 50MA', self._fv(breadth['pct_above_50ma'], '%'), ''])
            if breadth.get('breadth_signal'):
                br_rows.append(['Breadth Signal', breadth['breadth_signal'], ''])
            if breadth.get('risk_appetite_score') is not None:
                br_rows.append(['Risk Appetite Score', self._fv(breadth['risk_appetite_score'], '', 2), ''])
            if breadth.get('risk_appetite_signal'):
                br_rows.append(['Risk Appetite Signal', breadth['risk_appetite_signal'], ''])
            if breadth.get('cyclical_defensive_spread') is not None:
                br_rows.append(['Cyclical-Defensive Spread', self._fv(breadth['cyclical_defensive_spread'], '%'), ''])
            if breadth.get('cycle_position'):
                br_rows.append(['Cycle Position', breadth['cycle_position'], ''])
            if br_rows:
                html += self._table(['Breadth', 'Valor', ''], br_rows, 'Market Breadth')

        # AlphaVantage Sentiment
        if av and 'error' not in av:
            sentiment = av.get('sector_sentiment', {})
            if sentiment:
                sent_rows = []
                for sector, sdata in sorted(sentiment.items()):
                    if isinstance(sdata, dict):
                        score = sdata.get('avg_sentiment', 0)
                        label = sdata.get('sentiment_label', 'N/D')
                        cls = 'trend-up' if label == 'BULLISH' else ('trend-down' if label == 'BEARISH' else '')
                        sent_rows.append([sector.title(), self._fv(score, '', 3),
                                          f'<span class="{cls}">{label}</span>'])
                if sent_rows:
                    html += self._table(['Sector', 'Score', 'Señal'], sent_rows, 'AlphaVantage Sentiment')

            movers = av.get('market_movers', {})
            if movers:
                for mover_type, mover_list in [('Top Gainers', movers.get('top_gainers', [])),
                                                ('Top Losers', movers.get('top_losers', []))]:
                    if mover_list:
                        m_rows = [[m.get('ticker', ''), self._fv(float(m.get('price', 0)), '$', 2),
                                   m.get('change_percentage', '')]
                                  for m in mover_list[:5] if isinstance(m, dict)]
                        if m_rows:
                            html += self._table(['Ticker', 'Precio', 'Cambio'], m_rows, mover_type)

        # Bloomberg CDS
        cds = bbg.get('cds', {})
        if cds and isinstance(cds, dict) and len(cds) > 1:
            cds_rows = [[k, self._fv(v, 'bps', 0)] for k, v in sorted(cds.items())
                        if v is not None and k not in ('_source', 'timestamp', 'error', 'available')]
            if cds_rows:
                html += self._table(['País', 'CDS 5Y'], cds_rows[:14], 'CDS Spreads (Bloomberg)')

        # Bloomberg OAS
        oas = bbg.get('credit_spreads', {})
        if oas and isinstance(oas, dict) and len(oas) > 1:
            oas_rows = [[k, self._fv(v, 'bps', 0)] for k, v in sorted(oas.items())
                        if v is not None and k not in ('_source', 'timestamp', 'error', 'available')]
            if oas_rows:
                html += self._table(['Sector', 'OAS'], oas_rows[:14], 'OAS IG/HY por Sector (Bloomberg)')

        return {'id': 'markets', 'title': 'VII. Mercados & Riesgo', 'html': html,
                'chart_ids': ['global_equities', 'epu_geopolitics']}

    def _build_intelligence_section(self) -> Dict:
        """Intelligence Digest — themes, sentiment, ideas, events."""
        html = ''
        themes = self.intel.get('themes', {})
        sentiment = self.intel.get('sentiment_evolution', [])
        ideas = self.intel.get('tactical_ideas', [])
        events = self.intel.get('key_events', [])
        narratives = self.intel.get('weekly_narratives', [])

        # Themes grid
        if themes:
            html += '<h4 class="subsection-title">Temas Dominantes</h4>'
            html += '<div class="themes-grid">'
            for tid, t in list(themes.items())[:10]:
                cat = t.get('category', '')
                css = CATEGORY_CSS.get(cat, '')
                trend = t.get('trend', '')
                arrow = TREND_ARROWS.get(trend, '')
                days = t.get('report_days', 0)
                contexts = t.get('recent_contexts', [])
                context_text = contexts[0][:150] + '...' if contexts else ''

                html += f'''<div class="theme-card {css}">
                    <div class="theme-name">{tid.replace("_", " ").title()} {arrow}</div>
                    <div class="theme-meta">{cat} &mdash; {days} días &mdash; {trend}</div>
                    <div class="theme-context">{context_text}</div>
                </div>'''
            html += '</div>'

        # Sentiment timeline
        if sentiment:
            html += '<h4 class="subsection-title">Evolución de Sentimiento</h4>'
            html += '<div class="sentiment-timeline">'
            for week in sentiment:
                label = week.get('week', '')
                on = week.get('avg_risk_on', 0) * 100
                off = week.get('avg_risk_off', 0) * 100
                cau = week.get('avg_cautious', 0) * 100
                html += f'''<div class="sentiment-week">
                    <div class="sentiment-week-label">{label}</div>
                    <div class="sentiment-bar-group">
                        <div class="sentiment-bar-segment sentiment-on" style="width:{on:.0f}%">{on:.0f}%</div>
                        <div class="sentiment-bar-segment sentiment-cautious" style="width:{cau:.0f}%">{cau:.0f}%</div>
                        <div class="sentiment-bar-segment sentiment-off" style="width:{off:.0f}%">{off:.0f}%</div>
                    </div>
                </div>'''
            html += '</div>'

        # Tactical ideas
        if ideas:
            html += '<h4 class="subsection-title">Ideas Tácticas Recientes</h4>'
            idea_rows = [[i.get('date', ''), i.get('category', ''),
                          i.get('idea', '')[:200]] for i in ideas[-8:]]
            html += self._table(['Fecha', 'Categoría', 'Idea'], idea_rows)

        # Weekly narratives
        if narratives:
            html += '<h4 class="subsection-title">Narrativas Semanales</h4>'
            for wn in narratives[-4:]:
                week = wn.get('week', '')
                highlights = wn.get('highlights', [])
                if highlights:
                    html += f'<details class="collapsible"><summary>{week}</summary><ul style="margin:8px 20px">'
                    for h in highlights[:4]:
                        html += f'<li style="margin:3px 0;font-size:9pt;color:#4a4a4a">{h}</li>'
                    html += '</ul></details>'

        # Key events
        if events:
            html += '<h4 class="subsection-title">Eventos / Agenda</h4>'
            ev_rows = [[e.get('from_date', ''), e.get('event', '')] for e in events[:10]]
            html += self._table(['Fecha', 'Evento'], ev_rows)

        if not html:
            html = '<p>Intelligence Digest no disponible.</p>'

        return {'id': 'intelligence', 'title': 'VIII. Intelligence Digest', 'html': html, 'chart_ids': []}

    def _build_research_section(self) -> Dict:
        """External research synthesis."""
        research = self.data.get('research', '')
        if not research:
            html = '<p style="color:#a0aec0;font-style:italic">No se proporcionó research externo para esta sesión.</p>'
        else:
            html = f'<div class="narrative-box">{research}</div>'
        return {'id': 'research', 'title': 'IX. Research Externo', 'html': html, 'chart_ids': []}

    def _build_directives_section(self) -> Dict:
        """User directives."""
        directives = self.data.get('directives', '')
        if not directives:
            html = '<p style="color:#a0aec0;font-style:italic">Sin directivas específicas del gestor.</p>'
        else:
            html = f'<div class="narrative-box">{directives}</div>'
        return {'id': 'directives', 'title': 'X. Directivas del Gestor', 'html': html, 'chart_ids': []}

    def _build_coverage_section(self) -> Dict:
        """Data coverage summary from CompletenessResult."""
        comp = self.completeness
        if not comp:
            return {'id': 'coverage', 'title': 'XI. Cobertura de Datos',
                    'html': '<p>Validación de completeness no disponible.</p>', 'chart_ids': []}

        try:
            cd = comp if isinstance(comp, dict) else comp.to_dict()
        except Exception:
            return {'id': 'coverage', 'title': 'XI. Cobertura de Datos',
                    'html': '<p>Error procesando completeness.</p>', 'chart_ids': []}

        html = ''
        agents = cd.get('agents', {})
        for agent_name, ag in agents.items():
            req_t = ag.get('required_total', 0)
            req_p = ag.get('required_present', 0)
            imp_t = ag.get('important_total', 0)
            imp_p = ag.get('important_present', 0)
            opt_t = ag.get('optional_total', 0)
            opt_p = ag.get('optional_present', 0)
            total = req_t + imp_t + opt_t
            present = req_p + imp_p + opt_p
            pct = (present / total * 100) if total else 0
            bar_color = '#48bb78' if pct >= 80 else ('#ecc94b' if pct >= 60 else '#fc8181')

            html += f'''<div class="coverage-row">
                <div class="coverage-agent">{agent_name}</div>
                <div class="coverage-bar-bg"><div class="coverage-bar-fill" style="width:{pct:.0f}%;background:{bar_color}"></div></div>
                <div class="coverage-pct" style="color:{bar_color}">{pct:.0f}%</div>
            </div>'''
            html += f'<div style="font-size:8pt;color:#717171;margin:0 0 8px 108px">R: {req_p}/{req_t} &bull; I: {imp_p}/{imp_t} &bull; O: {opt_p}/{opt_t}</div>'

            # Show missing required fields
            missing_req = [f for f in ag.get('missing_fields', [])
                          if isinstance(f, dict) and f.get('priority') == 'required']
            if missing_req:
                html += '<details class="collapsible"><summary style="color:#c53030">Campos Required Faltantes</summary><ul style="margin:5px 20px">'
                for f in missing_req:
                    html += f'<li style="font-size:8.5pt;color:#c53030">{f.get("field", "?")} ({f.get("source", "?")})</li>'
                html += '</ul></details>'

        return {'id': 'coverage', 'title': 'XI. Cobertura de Datos', 'html': html, 'chart_ids': []}

    # ═══════════════════════════════════════════════════════════════
    # CORE: generate + render
    # ═══════════════════════════════════════════════════════════════

    def generate(self) -> Dict[str, Any]:
        """Build all sections."""
        self._print("[Briefing] Generating content...")

        builders = [
            self._build_header_section,
            self._build_regime_section,
            self._build_usa_section,
            self._build_europe_section,
            self._build_china_section,
            self._build_chile_latam_section,
            self._build_markets_risk_section,
            self._build_intelligence_section,
            self._build_research_section,
            self._build_directives_section,
            self._build_coverage_section,
        ]

        sections = []
        header_data = {}
        for builder in builders:
            try:
                section = builder()
                if section:
                    if section['id'] == 'header':
                        header_data = section
                    else:
                        sections.append(section)
            except Exception as e:
                self._print(f"  [WARN] {builder.__name__}: {e}")

        return {'sections': sections, 'header': header_data}

    def render(self, output_dir: str = None) -> str:
        """Generate content, charts, render template, save HTML."""
        import time
        start = time.time()

        content = self.generate()

        # Generate charts
        self._print("[Briefing] Generating charts...")
        self._generate_all_charts()

        # Load Jinja2 template
        from jinja2 import Environment, FileSystemLoader
        template_dir = Path(__file__).parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,
        )
        template = env.get_template('antecedentes_briefing.html')

        # Date formatting
        fecha = f'{self.now.day} {MONTHS_ES[self.now.month]} {self.now.year}'

        header = content.get('header', {})

        context = {
            'fecha_reporte': fecha,
            'generated_at': self.now.strftime('%Y-%m-%d %H:%M'),
            'sections': content['sections'],
            'charts': self._charts,
            'summary_cards_html': header.get('_summary_cards', ''),
            'verdict_badge': header.get('_verdict_badge', ''),
            # Branding
            'primary_color': self.branding.get('primary_color', '#1a1a1a'),
            'accent_color': self.branding.get('accent_color', '#dd6b20'),
            'green_color': self.branding.get('green_color', '#276749'),
            'red_color': self.branding.get('red_color', '#c53030'),
            'font_family': self.branding.get('font_family', "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"),
            'header_font_family': self.branding.get('header_font_family', "'Archio Black', 'Arial Black', 'Segoe UI', sans-serif"),
            'company_name': self.branding.get('company_name', 'Research'),
        }

        html = template.render(**context)

        # Strip all N/D from final output
        from html_nd_cleaner import clean_nd
        html = clean_nd(html)

        # Save
        out_dir = Path(output_dir) if output_dir else Path(__file__).parent / "output" / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"antecedentes_briefing_{self.date_str}.html"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

        elapsed = time.time() - start
        self._print(f"[Briefing] Done in {elapsed:.1f}s — {path}")
        return str(path)


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("Libro de Antecedentes — Standalone Test\n")

    # Collect real data
    from council_data_collector import CouncilDataCollector
    collector = CouncilDataCollector(verbose=True)
    macro_quant = collector.collect_quantitative_data()

    # Build data dict matching run_monthly.py structure
    data = {
        'macro_quant': macro_quant,
        'intelligence': collector.collect_intelligence_digest(),
        'daily_summary': collector.collect_daily_reports_summary(30),
        'research': collector.collect_external_research(),
        'directives': collector.collect_user_directives(),
    }

    # Run completeness validation
    try:
        from data_completeness_validator import DataCompletenessValidator
        daily_summary = data.get('daily_summary', {})
        intelligence = data.get('intelligence', {})
        agent_data_map = collector._prepare_agent_specific_data(
            macro_quant, daily_summary, intelligence, 'macro'
        )
        validator = DataCompletenessValidator(verbose=False)
        completeness = validator.validate(agent_data_map)
    except Exception:
        completeness = None

    gen = AntecedentesBriefingGenerator(data, completeness=completeness)
    path = gen.render()
    print(f"\nOutput: {path}")

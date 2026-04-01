# -*- coding: utf-8 -*-
"""
Greybark Research - Renta Variable Report Renderer
===================================================

Renderiza el reporte de Renta Variable combinando:
- Contenido narrativo (RVContentGenerator)
- Template HTML profesional
- Datos de mercado

Produce el reporte final con analisis sectorial, valorizaciones y views.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from html import escape as _html_escape
from jinja2 import Environment, FileSystemLoader, Undefined


def _esc(val, default='') -> str:
    """HTML-escape a value for safe injection into templates."""
    if val is None:
        return default
    return _html_escape(str(val))


def _md_to_html_inline(text: str) -> str:
    """Convert markdown bold/italic to HTML inline, preserving <style> blocks."""
    if not text or not isinstance(text, str):
        return text or ''
    styles = []
    def _save_style(m):
        styles.append(m.group(0))
        return f'__STYLE_BLOCK_{len(styles)-1}__'
    text = re.sub(r'<style[^>]*>.*?</style>', _save_style, text, flags=re.DOTALL)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    for i, style in enumerate(styles):
        text = text.replace(f'__STYLE_BLOCK_{i}__', style)
    return text

sys.path.insert(0, str(Path(__file__).parent))

from rv_content_generator import RVContentGenerator
from rv_chart_generator import RVChartsGenerator
from equity_data_collector import EquityDataCollector
from table_builder import (
    build_view_rows, build_calendar_rows, build_summary_rows,
    Badge, fmt_bold, fmt_small
)


class RVReportRenderer:
    """Renderizador del Reporte de Renta Variable profesional."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, verbose: bool = True, branding: dict = None):
        self.council_result = council_result or {}
        self.market_data = market_data or {}
        self.forecast_data = forecast_data
        self.verbose = verbose
        self.branding = branding or {}
        self.template_path = Path(__file__).parent / "templates" / "rv_report_professional.html"
        self.template_name = "rv_report_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            undefined=Undefined,
            autoescape=False,
        )

        self.content_generator = RVContentGenerator(
            self.council_result, self.market_data, forecast_data=self.forecast_data,
            company_name=self.branding.get('company_name', ''))

        # Inject Bloomberg data if available
        try:
            from bloomberg_reader import BloombergData
            bbg = BloombergData()
            if bbg.available:
                self.content_generator.bloomberg = bbg
        except Exception:
            pass

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _get_spanish_month(self, month: int) -> str:
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return meses.get(month, 'Mes')

    def render(self, output_filename: str = None) -> str:
        """Genera el reporte completo."""
        self._print("\n" + "="*60)
        self._print("GREYBARK - RENTA VARIABLE REPORT RENDERER")
        self._print("="*60)

        # 1. Generar contenido
        self._print("[1/4] Generando contenido de renta variable...")
        content = self.content_generator.generate_all_content()
        self.last_content = content

        # 2. Generar charts
        self._print("[2/4] Generando charts de renta variable...")
        chart_gen = RVChartsGenerator(market_data=self.market_data, branding=self.branding)
        charts = chart_gen.generate_all_charts()
        chart_count = sum(1 for v in charts.values() if v and v.startswith('data:image'))
        self._print(f"  {chart_count}/{len(charts)} charts generados con datos reales")

        # 3. Cargar template Jinja2
        self._print("[3/4] Cargando template profesional...")
        template = self._jinja_env.get_template(self.template_name)

        # 4. Renderizar
        self._print("[4/4] Renderizando reporte...")
        html = self._render_template(template, content, charts)

        # 4. Guardar
        if output_filename is None:
            output_filename = f"rv_report_{datetime.now().strftime('%Y-%m-%d')}.html"

        # Append data provenance div (hidden, for audit)
        html = self._append_provenance(html)

        # Convert any remaining markdown bold/italic to HTML
        html = _md_to_html_inline(html)

        # Clean up truncated text and unresolved placeholders (Bug #4)
        html = re.sub(r'\[BLOQUE:\s*[^\]]*\]', '', html)
        html = re.sub(r'<strong>[A-ZÁÉÍÓÚÑ]{2,6}</strong>\s*$', '', html, flags=re.MULTILINE)

        # Strip all N/D from final output
        from html_nd_cleaner import clean_nd
        html = clean_nd(html)

        # Post-render quality check
        from report_quality_checker import check_report_quality, print_quality_report
        issues = check_report_quality(html, 'rv')
        print_quality_report(issues, 'rv')

        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"\n[OK] Reporte RV generado: {output_path}")
        return str(output_path)

    def _append_provenance(self, html: str) -> str:
        """Append hidden data provenance div to HTML for audit trail."""
        try:
            from narrative_engine import get_provenance_records, clear_provenance_records
            import json as _json
            records = get_provenance_records()
            if records:
                provenance_json = _json.dumps(records, ensure_ascii=False, indent=2)
                div = (
                    f'\n<div id="data-provenance" style="display:none" '
                    f'data-report="rv" data-generated="{datetime.now().isoformat()}">'
                    f'\n{provenance_json}\n</div>\n'
                )
                if '</body>' in html:
                    html = html.replace('</body>', div + '</body>')
                else:
                    html += div
                clear_provenance_records()
        except Exception:
            pass
        return html

    def _render_template(self, template, content: Dict, charts: Dict = None) -> str:
        """Renderiza el template con el contenido y charts usando Jinja2."""

        now = datetime.now()
        replacements = {
            '{{fecha_reporte}}': f"{now.day} {self._get_spanish_month(now.month)} {now.year}",
        }

        # 1. RESUMEN EJECUTIVO
        resumen = content.get('resumen_ejecutivo', {})
        postura = resumen.get('postura_global', {})

        view_str = postura.get('view', 'NEUTRAL')
        replacements['{{postura_global}}'] = view_str
        replacements['{{stance_class}}'] = view_str.lower() if isinstance(view_str, str) else 'neutral'
        replacements['{{postura_narrativa}}'] = postura.get('narrativa', '')

        # Stance spectrum - highlight active postura
        active_view = view_str.upper() if isinstance(view_str, str) else 'NEUTRAL'
        for stance in ['cauteloso', 'neutral', 'constructivo', 'agresivo']:
            replacements[f'{{{{spectrum_active_{stance}}}}}'] = 'spectrum-active' if stance.upper() == active_view else ''

        # Summary table
        summary_rows = ''
        for r in resumen.get('tabla_resumen', []):
            view_class = self._get_view_class(r.get('view'))
            summary_rows += f'''<tr>
                <td>{_esc(r.get('mercado', ''))}</td>
                <td>{_esc(r.get('indice', ''))}</td>
                <td class="center"><span class="view-badge {view_class}">{_esc(r.get('view', 'N'))}</span></td>
                <td class="center">{_esc(r.get('cambio', '-'))}</td>
                <td>{_esc(r.get('driver', ''))}</td>
            </tr>'''
        replacements['{{summary_table_rows}}'] = summary_rows

        # Key calls
        key_calls = ''.join([f'<li>{kc}</li>' for kc in resumen.get('key_calls', [])])
        replacements['{{key_calls_html}}'] = key_calls

        # 2. VALORIZACIONES
        val = content.get('valorizaciones', {})
        replacements['{{valuation_narrative}}'] = val.get('narrativa', '')

        # Multiples table — hide EV/EBITDA column if all N/D
        has_ev = any(m.get('ev_ebitda') not in (None, 'N/D', '') for m in val.get('multiples_region', []))
        mult_rows = ''
        for m in val.get('multiples_region', []):
            val_class = self._get_valuation_class(m.get('vs_10y_avg', ''))
            ev_col = f'<td class="center">{m.get("ev_ebitda", "N/D")}</td>' if has_ev else ''
            mult_rows += f'''<tr>
                <td><strong>{m.get('mercado', '')}</strong></td>
                <td class="center">{m.get('pe_fwd', 'N/D')}</td>
                <td class="center {val_class}">{m.get('vs_10y_avg', 'N/D')}</td>
                {ev_col}
                <td class="center">{m.get('pb', 'N/D')}</td>
                <td class="center">{m.get('div_yield', 'N/D')}</td>
                <td>{m.get('comentario', '')}</td>
            </tr>'''
        replacements['{{multiples_table_rows}}'] = mult_rows
        # Hide EV/EBITDA header if column hidden
        if not has_ev:
            replacements['{{ev_ebitda_header}}'] = ''
        else:
            replacements['{{ev_ebitda_header}}'] = '<th class="center">EV/EBITDA</th>'

        # PE Targets (fair value model)
        pe_targets = val.get('pe_targets', [])
        pe_target_rows = ''
        for t in pe_targets:
            t_signal = t.get('signal', 'JUSTO')
            signal_class = 'val-cheap' if t_signal == 'BARATO' else 'val-expensive' if t_signal == 'CARO' else 'val-fair'
            pe_target_rows += f'''<tr>
                <td><strong>{t.get('mercado', '')}</strong></td>
                <td class="center">{t.get('pe_actual', 'N/D')}</td>
                <td class="center">{t.get('pe_fair', 'N/D')}</td>
                <td class="center {signal_class}"><strong>{t_signal}</strong></td>
                <td class="center">{t.get('upside', 'N/D')}</td>
                <td class="center" style="font-size:8pt;">{t.get('fed_model', 'N/D')}</td>
                <td class="center" style="font-size:8pt;">{t.get('mean_rev', 'N/D')}</td>
            </tr>'''
        replacements['{{pe_target_rows}}'] = pe_target_rows
        replacements['{{has_pe_targets}}'] = 'true' if pe_targets else 'false'

        # ERP
        erp = val.get('equity_risk_premium', {})
        replacements['{{erp_narrative}}'] = erp.get('narrativa', '')

        erp_rows = ''
        for e in erp.get('datos', []):
            erp_rows += f'''<tr>
                <td>{e.get('mercado', '')}</td>
                <td class="center">{e.get('earning_yield', 'N/D')}</td>
                <td class="center">{e.get('tasa_real', 'N/D')}</td>
                <td class="center"><strong>{e.get('erp', 'N/D')}</strong></td>
                <td>{e.get('vs_historia', '')}</td>
            </tr>'''
        replacements['{{erp_table_rows}}'] = erp_rows

        # 3. EARNINGS
        earn = content.get('earnings', {})
        replacements['{{earnings_narrative}}'] = earn.get('narrativa', '')

        # Earnings growth
        earn_rows = ''
        for e in earn.get('earnings_growth', []):
            rev_str = str(e.get('revision_3m', 'N/D'))
            rev_class = 'val-cheap' if rev_str.startswith('+') else 'val-expensive' if rev_str.startswith('-') else ''
            # Support both old format (eps_2025/eps_2026f) and new format (beat_rate/pe_trailing/pe_forward)
            if 'eps_2025' in e:
                earn_rows += f'''<tr>
                <td>{e.get('region', '')}</td>
                <td class="center">{e.get('eps_2025', 'N/D')}</td>
                <td class="center">{e.get('eps_2026f', 'N/D')}</td>
                <td class="center"><strong>{e.get('growth', 'N/D')}</strong></td>
                <td class="center {rev_class}">{rev_str}</td>
            </tr>'''
            else:
                earn_rows += f'''<tr>
                <td>{e.get('region', '')}</td>
                <td class="center">{e.get('beat_rate', 'N/D')}</td>
                <td class="center">{e.get('pe_forward', e.get('pe_trailing', 'N/D'))}</td>
                <td class="center"><strong>{e.get('growth', 'N/D')}</strong></td>
                <td class="center {rev_class}">{rev_str}</td>
            </tr>'''
        replacements['{{earnings_table_rows}}'] = earn_rows

        # Revisions
        rev = earn.get('revision_trends', {})
        rev_rows = ''
        for r in rev.get('por_region', []):
            r_tendencia = r.get('tendencia', '')
            trend_class = 'val-cheap' if 'Fuerte' in r_tendencia or 'Mejorando' in r_tendencia else 'val-expensive' if 'Deteriorando' in r_tendencia else ''
            rev_rows += f'''<tr>
                <td>{r.get('region', '')}</td>
                <td class="center">{r.get('upgrades', 'N/D')}</td>
                <td class="center">{r.get('downgrades', 'N/D')}</td>
                <td class="center"><strong>{r.get('net', 'N/D')}</strong></td>
                <td class="{trend_class}">{r_tendencia}</td>
            </tr>'''
        replacements['{{revisions_table_rows}}'] = rev_rows

        # 4. SECTORES
        sect = content.get('sectores', {})
        replacements['{{sector_narrative}}'] = sect.get('narrativa', '')

        # Sector matrix
        matrix_rows = ''
        for s in sect.get('matriz_sectorial', []):
            view_class = self._get_view_class(s.get('view', 'N'))
            matrix_rows += f'''<tr>
                <td class="sector-name">{_esc(s.get('sector', ''))}</td>
                <td><span class="view-badge {view_class}">{_esc(s.get('view', 'N'))}</span></td>
                <td>{_esc(s.get('valuacion', ''))}</td>
                <td>{_esc(s.get('momentum', ''))}</td>
                <td>{_esc(s.get('earnings', ''))}</td>
                <td style="text-align:left; font-size:8pt;">{_esc(s.get('catalizador', ''))}</td>
            </tr>'''
        replacements['{{sector_matrix_rows}}'] = matrix_rows

        # Preferred sectors
        pref_html = ''
        for s in sect.get('sectores_preferidos', []):
            subsectors = ''.join([f'<span class="sector-tag preferred">{_esc(sub)}</span>' for sub in s.get('subsectores', [])])
            avoid = ''.join([f'<span class="sector-tag avoid">{_esc(a)}</span>' for a in s.get('evitar', [])])
            pref_html += f'''
            <div class="sector-card ow">
                <div class="sector-card-header">
                    <h4>{_esc(s.get('sector', ''))}</h4>
                    <span class="view-badge badge-ow">{_esc(s.get('view', 'OW'))} | Upside: {_esc(s.get('upside', 'N/D'))}</span>
                </div>
                <div class="sector-card-body">
                    <p>{_esc(s.get('tesis', ''))}</p>
                    <div class="sector-tags">
                        <strong style="font-size:8pt;">Preferidos:</strong> {subsectors}
                    </div>
                    <div class="sector-tags" style="margin-top:5px;">
                        <strong style="font-size:8pt;">Evitar:</strong> {avoid}
                    </div>
                </div>
            </div>'''
        replacements['{{preferred_sectors_html}}'] = pref_html

        # Avoid sectors
        avoid_html = ''
        for s in sect.get('sectores_evitar', []):
            avoid_html += f'''
            <div class="sector-card uw">
                <div class="sector-card-header">
                    <h4>{_esc(s.get('sector', ''))}</h4>
                    <span class="view-badge badge-uw">{_esc(s.get('view', 'UW'))}</span>
                </div>
                <div class="sector-card-body">
                    <p>{_esc(s.get('razon', ''))}</p>
                    <p style="font-size:9pt; color: var(--text-light);"><strong>¿Qué cambiaría?</strong> {_esc(s.get('que_cambiaria', ''))}</p>
                </div>
            </div>'''
        replacements['{{avoid_sectors_html}}'] = avoid_html

        # 5. STYLE & FACTORS
        style = content.get('style_factors', {})
        gv = style.get('growth_vs_value', {})
        replacements['{{growth_value_narrative}}'] = gv.get('narrativa', '')
        replacements['{{style_recommendation}}'] = style.get('recomendacion_style', {}).get('recomendacion', '')

        # Factor table — handle both list (legacy) and dict (new) format
        fp = style.get('factor_performance', [])
        if isinstance(fp, dict):
            factor_list = fp.get('factors', [])
            has_scores = fp.get('has_scores', False)
        else:
            factor_list = fp
            has_scores = any(f.get('score') not in ('N/D', '-') for f in factor_list
                            if f.get('factor') != 'Composite (por region)')

        factor_rows = ''
        for f in factor_list:
            view_class = self._get_view_class(f.get('view', 'N'))
            if has_scores:
                factor_rows += f'''<tr>
                <td>{f.get('factor', '')}</td>
                <td class="center">{f.get('score', 'N/D')}</td>
                <td class="center">{f.get('ytd', 'N/D')}</td>
                <td class="center"><span class="view-badge {view_class}">{f.get('view', 'N')}</span></td>
            </tr>'''
            else:
                factor_rows += f'''<tr>
                <td>{f.get('factor', '')}</td>
                <td class="center">{f.get('ytd', 'N/D')}</td>
                <td class="center"><span class="view-badge {view_class}">{f.get('view', 'N')}</span></td>
            </tr>'''
        replacements['{{factor_table_rows}}'] = factor_rows
        replacements['{{factor_has_scores}}'] = 'true' if has_scores else 'false'

        # 6. REGIONAL VIEWS
        regions = content.get('regiones', {})
        regional_html = ''

        for key in ['us', 'europe', 'em', 'japan']:
            r = regions.get(key, {})
            view_class = self._get_view_class(r.get('view', 'N'))
            regional_html += f'''
            <div class="region-card">
                <div class="region-card-header">
                    <span class="region-name">{_esc(r.get('mercado', ''))} ({_esc(r.get('indice', ''))})</span>
                    <span class="region-view">{r.get('view', 'N')}</span>
                </div>
                <div class="region-card-body">
                    <div class="region-metrics">
                        <div class="metric-box">
                            <div class="metric-label">P/E Forward</div>
                            <div class="metric-value">{r.get('pe_actual', 'N/D')}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Retorno Esp. 12M</div>
                            <div class="metric-value" style="color: var(--success);">{r.get('upside', 'N/D')}</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-label">Cambio</div>
                            <div class="metric-value">{r.get('cambio', '')}</div>
                        </div>
                    </div>
                    <p style="color: var(--text-medium);">{_esc(r.get('narrativa', ''))}</p>
                </div>
            </div>'''
        replacements['{{regional_views_html}}'] = regional_html

        # Chile highlight
        chile = regions.get('chile', {})
        replacements['{{chile_narrative}}'] = chile.get('narrativa', '')
        replacements['{{chile_pe}}'] = chile.get('pe_actual', 'N/D')
        replacements['{{chile_target}}'] = chile.get('target_12m', 'N/D')
        replacements['{{chile_upside}}'] = chile.get('upside', 'N/D')
        # Dynamic dividend yield from chile picks or ECH ETF
        chile_dy = chile.get('top_picks', [{}])[0].get('div_yield', 'N/D') if chile.get('top_picks') else 'N/D'
        if chile_dy == 'N/D':
            ech_v = self.market_data.get('valuations', {}).get('chile', {})
            ech_dy = ech_v.get('dividend_yield')
            chile_dy = f"{ech_dy:.1f}%" if ech_dy else 'N/D'
        replacements['{{chile_div_yield}}'] = chile_dy

        chile_picks = ''
        for p in chile.get('top_picks', []):
            chile_picks += f'''<tr>
                <td><strong>{_esc(p.get('empresa', ''))}</strong></td>
                <td>{_esc(p.get('ticker', ''))}</td>
                <td>{_esc(p.get('pe', 'N/D'))}</td>
                <td>{_esc(p.get('div_yield', 'N/D'))}</td>
                <td>{_esc(p.get('rationale', ''))}</td>
            </tr>'''
        replacements['{{chile_picks_rows}}'] = chile_picks

        # 7. FLUJOS Y POSICIONAMIENTO
        flows = content.get('flujos_posicionamiento', {})
        flujos_reg = flows.get('flujos_regionales', {})
        replacements['{{flows_narrative}}'] = flujos_reg.get('narrativa', '')

        flows_rows = ''
        for f in flujos_reg.get('datos', []):
            ytd_val = f.get('flujo_ytd') or f.get('retorno_ytd', 'N/D')
            m1_val = f.get('flujo_1m') or f.get('retorno_1m', 'N/D')
            flows_rows += f'''<tr>
                <td>{_esc(f.get('region', ''))}</td>
                <td class="center">{_esc(ytd_val)}</td>
                <td class="center">{_esc(m1_val)}</td>
            </tr>'''
        replacements['{{flows_table_rows}}'] = flows_rows

        pos_rows = ''
        for p in flows.get('posicionamiento', {}).get('indicadores', []):
            pos_rows += f'''<tr>
                <td>{_esc(p.get('indicador', ''))}</td>
                <td class="center"><strong>{_esc(p.get('valor', 'N/D'))}</strong></td>
                <td>{_esc(p.get('comentario', ''))}</td>
            </tr>'''
        replacements['{{positioning_table_rows}}'] = pos_rows

        # 8. RIESGOS Y CATALIZADORES
        risks = content.get('riesgos_catalizadores', {})

        risks_html = ''
        for r in risks.get('top_risks', []):
            risks_html += f'''
            <div class="risk-card">
                <div class="risk-header">
                    <span class="risk-name">{_esc(r.get('riesgo', ''))}</span>
                    <span class="risk-metrics">
                        <span>Prob: <strong>{_esc(r.get('probabilidad', 'N/D'))}</strong></span>
                        <span>Impacto: <strong>{_esc(r.get('impacto', 'N/D'))}</strong></span>
                    </span>
                </div>
                <p style="margin: 10px 0; color: var(--text-medium);">{_esc(r.get('descripcion', ''))}</p>
                <p style="font-size: 9pt; color: var(--text-light);"><strong>Hedge:</strong> {_esc(r.get('hedge', ''))}</p>
            </div>'''
        replacements['{{risks_html}}'] = risks_html

        catalysts = ''.join([f'<li>{c}</li>' for c in risks.get('catalizadores_positivos', [])])
        replacements['{{catalysts_html}}'] = catalysts

        replacements['{{calendar_rows}}'] = build_calendar_rows(risks.get('calendario', []))

        # 9. RESUMEN POSICIONAMIENTO
        summary = content.get('resumen_posicionamiento', {})

        replacements['{{summary_positioning_rows}}'] = build_summary_rows(
            summary.get('tabla_final', []), key_field='categoria', value_field='recomendacion')
        replacements['{{mensaje_clave}}'] = summary.get('mensaje_clave', '')

        # Convert {{key}} → key for Jinja2 context
        context = {}
        for key, value in replacements.items():
            clean = key.replace('{{', '').replace('}}', '')
            context[clean] = str(value)

        # Charts
        if charts:
            for chart_id, chart_data in charts.items():
                if chart_data and chart_data.startswith('data:image'):
                    context[chart_id] = f'<div class="chart-container"><img src="{chart_data}" alt="{chart_id}"></div>'
                else:
                    context[chart_id] = chart_data or ''

        # Inject branding (templates use |default() for fallback)
        if self.branding:
            context.update(self.branding)

        return template.render(**context)

    def _get_view_class(self, view: str) -> str:
        """Retorna clase CSS segun view."""
        if not view or not isinstance(view, str):
            return 'badge-neutral'
        view_upper = view.upper().strip()
        if any(kw in view_upper for kw in ['OW', 'OVERWEIGHT', 'SOBREPONDERAR', 'SOBREPONDER']):
            return 'badge-ow'
        elif any(kw in view_upper for kw in ['UW', 'UNDERWEIGHT', 'SUBPONDERAR', 'SUBPONDER']):
            return 'badge-uw'
        return 'badge-neutral'

    def _get_valuation_class(self, vs_avg: str) -> str:
        """Retorna clase CSS segun valuacion vs promedio."""
        if not vs_avg or not isinstance(vs_avg, str):
            return 'val-fair'
        try:
            if vs_avg.startswith('+') and float(vs_avg.replace('%', '').replace('+', '')) > 10:
                return 'val-expensive'
            elif vs_avg.startswith('-'):
                return 'val-cheap'
        except (ValueError, TypeError):
            pass
        return 'val-fair'


def main():
    """Genera el reporte RV profesional."""
    import argparse

    parser = argparse.ArgumentParser(description='Generador Reporte Renta Variable')
    parser.add_argument('--council-file', help='Archivo JSON con resultado del council')
    parser.add_argument('--equity-data', help='Archivo JSON con datos equity pre-recopilados')
    parser.add_argument('--no-collect', action='store_true', help='No recopilar datos (solo usar defaults)')
    parser.add_argument('--output', '-o', help='Nombre archivo de salida')
    args = parser.parse_args()

    # Cargar council result si existe
    council_result = None
    council_file = args.council_file

    if not council_file:
        output_dir = Path(__file__).parent / "output" / "council"
        council_files = list(output_dir.glob("council_result_*.json"))
        if council_files:
            council_file = str(sorted(council_files)[-1])

    if council_file:
        print(f"[INFO] Cargando council: {council_file}")
        with open(council_file, 'r', encoding='utf-8') as f:
            council_result = json.load(f)
    else:
        print("[INFO] Sin council file - usando defaults hardcoded")

    # Recopilar datos equity
    market_data = None

    if args.equity_data:
        print(f"[INFO] Cargando equity data: {args.equity_data}")
        with open(args.equity_data, 'r', encoding='utf-8') as f:
            market_data = json.load(f)
    elif not args.no_collect:
        # Auto-buscar datos recientes (< 24h)
        equity_dir = Path(__file__).parent / "output" / "equity_data"
        if equity_dir.exists():
            equity_files = sorted(equity_dir.glob("equity_data_*.json"), reverse=True)
            if equity_files:
                print(f"[INFO] Equity data encontrada: {equity_files[0].name}")
                with open(equity_files[0], 'r', encoding='utf-8') as f:
                    market_data = json.load(f)

        if not market_data:
            print("[INFO] Recopilando datos equity en tiempo real...")
            collector = EquityDataCollector(verbose=True)
            market_data = collector.collect_all()
            collector.save(market_data)
    else:
        print("[INFO] --no-collect: sin datos de mercado")

    renderer = RVReportRenderer(council_result=council_result, market_data=market_data, verbose=True)
    output_path = renderer.render(output_filename=args.output)

    # Abrir en navegador
    import webbrowser
    webbrowser.open(str(output_path))


if __name__ == "__main__":
    main()

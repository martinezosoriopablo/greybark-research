# -*- coding: utf-8 -*-
"""
Greybark Research - Renta Fija Report Renderer
================================================

Renderiza el reporte de Renta Fija combinando:
- Contenido narrativo (RFContentGenerator)
- Template HTML profesional
- Datos de mercado

Produce el reporte final con duration, credito y views de tasas.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, Undefined

sys.path.insert(0, str(Path(__file__).parent))

from rf_content_generator import RFContentGenerator
from table_builder import (
    build_view_rows, build_calendar_rows, build_summary_rows,
    Badge, fmt_bold, fmt_small
)


def _md_to_html(text: str) -> str:
    """Convert basic markdown (bold, headings) to HTML inline."""
    if not text:
        return text
    # Remove markdown headings (## RENTA FIJA → nothing, it's a section title)
    text = re.sub(r'^#{1,4}\s+.*$', '', text, flags=re.MULTILINE)
    # Bold **text** → <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic *text* → <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Clean up extra whitespace from removed headings
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class RFReportRenderer:
    """Renderizador del Reporte de Renta Fija profesional."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, verbose: bool = True, branding: dict = None):
        self.council_result = council_result or {}
        self.market_data = market_data or {}
        self.forecast_data = forecast_data
        self.verbose = verbose
        self.branding = branding or {}
        self.template_path = Path(__file__).parent / "templates" / "rf_report_professional.html"
        self.template_name = "rf_report_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            undefined=Undefined,
            autoescape=False,
        )

        self.content_generator = RFContentGenerator(
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
        self._print("GREYBARK RESEARCH - RENTA FIJA REPORT RENDERER")
        self._print("="*60)

        self._print("[1/4] Generando contenido de renta fija...")
        content = self.content_generator.generate_all_content()
        self.last_content = content

        self._print("[2/4] Cargando template profesional...")
        template = self._jinja_env.get_template(self.template_name)

        self._print("[3/4] Generando charts...")
        charts = {}
        try:
            from rf_chart_generator import RFChartsGenerator
            charts_gen = RFChartsGenerator(self.market_data, branding=self.branding)
            charts = charts_gen.generate_all_charts()
            real_count = len([v for v in charts.values() if 'base64' in v])
            self._print(f"  Charts: {real_count}/{len(charts)} generados con datos reales")
        except Exception as e:
            self._print(f"  [WARN] Charts: {e}")

        self._print("[4/4] Renderizando reporte...")
        html = self._render_template(template, content, charts)

        if output_filename is None:
            output_filename = f"rf_report_{datetime.now().strftime('%Y-%m-%d')}.html"

        # Append data provenance div (hidden, for audit)
        html = self._append_provenance(html)

        # Strip all N/D from final output
        from html_nd_cleaner import clean_nd
        html = clean_nd(html)

        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"\n[OK] Reporte RF generado: {output_path}")
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
                    f'data-report="rf" data-generated="{datetime.now().isoformat()}">'
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
        """Renderiza el template con el contenido usando Jinja2."""

        now = datetime.now()
        replacements = {
            '{{fecha_reporte}}': f"{now.day} {self._get_spanish_month(now.month)} {now.year}",
        }

        # 1. RESUMEN EJECUTIVO
        resumen = content.get('resumen_ejecutivo', {})
        postura = resumen.get('postura_global', {})

        replacements['{{postura_global}}'] = postura.get('view', 'Neutral')
        replacements['{{duration_stance}}'] = postura.get('duration_stance', '')
        replacements['{{credit_stance}}'] = postura.get('credit_stance', '')
        replacements['{{postura_narrativa}}'] = _md_to_html(postura.get('narrativa', ''))

        # Stance spectrum - highlight active postura
        active_view = postura.get('view', 'Neutral').upper()
        for stance in ['cauteloso', 'neutral', 'constructivo', 'agresivo']:
            replacements[f'{{{{spectrum_active_{stance}}}}}'] = 'spectrum-active' if stance.upper() == active_view else ''

        # Summary table
        summary_rows = ''
        for r in resumen.get('tabla_resumen', []):
            view_class = self._get_view_class(r.get('view', 'N'))
            summary_rows += f'''<tr>
                <td><strong>{r.get('segmento', '')}</strong></td>
                <td class="center"><span class="view-badge {view_class}">{r.get('view', 'N')}</span></td>
                <td class="center">{r.get('duration', '')}</td>
                <td class="center yield-high">{r.get('yield', '')}</td>
                <td class="center">{r.get('spread', '')}</td>
                <td>{_md_to_html(r.get('driver', ''))}</td>
            </tr>'''
        replacements['{{summary_table_rows}}'] = summary_rows

        key_calls = ''.join([f'<li>{_md_to_html(kc)}</li>' for kc in resumen.get('key_calls', [])])
        replacements['{{key_calls_html}}'] = key_calls

        # 2. AMBIENTE DE TASAS
        tasas = content.get('ambiente_tasas', {})
        replacements['{{rates_narrative}}'] = _md_to_html(tasas.get('narrativa', ''))

        yields_rows = ''
        for y in tasas.get('yields_globales', []):
            yields_rows += f'''<tr>
                <td><strong>{y.get('mercado', '')}</strong></td>
                <td class="center">{y.get('y2', '-')}</td>
                <td class="center">{y.get('y5', '-')}</td>
                <td class="center yield-high">{y.get('y10', '-')}</td>
                <td class="center">{y.get('y30', '-')}</td>
                <td class="center">{y.get('curva_2_10', '-')}</td>
                <td class="center">{y.get('vs_1m', '-')}</td>
            </tr>'''
        replacements['{{yields_table_rows}}'] = yields_rows

        real_rows = ''
        tasas_reales = tasas.get('tasas_reales', {})
        for r in tasas_reales.get('datos', []):
            # Skip rows where all numeric values are N/D
            if r.get('yield_real', 'N/D') == 'N/D' and r.get('breakeven', 'N/D') == 'N/D' and r.get('nominal', 'N/D') == 'N/D':
                continue
            real_rows += f'''<tr>
                <td>{r.get('mercado', '')}</td>
                <td class="center yield-high">{r.get('yield_real', 'N/D')}</td>
                <td class="center">{r.get('breakeven', 'N/D')}</td>
                <td class="center">{r.get('nominal', 'N/D')}</td>
                <td>{r.get('vs_historia', '')}</td>
            </tr>'''
        replacements['{{real_rates_rows}}'] = real_rows

        # Neutral rate section (if available)
        neutral = tasas.get('neutral_rate')
        if neutral and neutral.get('rows'):
            nr_html = f'''
            <h3 style="margin-top: 25px;">{neutral.get('titulo', '')}</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Fuente</th>
                        <th class="center">r* Real</th>
                        <th class="center">i* Nominal</th>
                        <th>Nota</th>
                    </tr>
                </thead>
                <tbody>'''
            for nr in neutral.get('rows', []):
                nr_html += f'''
                    <tr>
                        <td>{nr.get('fuente', '')}</td>
                        <td class="center">{nr.get('r_star_real', '')}</td>
                        <td class="center">{nr.get('i_star_nominal', '')}</td>
                        <td>{nr.get('nota', '')}</td>
                    </tr>'''
            nr_html += '''
                </tbody>
            </table>'''
            replacements['{{neutral_rate_section}}'] = nr_html
        else:
            replacements['{{neutral_rate_section}}'] = ''

        # 3. DURATION
        duration = content.get('duration', {})
        replacements['{{duration_narrative}}'] = _md_to_html(duration.get('view_global', {}).get('rationale', ''))

        dur_rows = ''
        for d in duration.get('por_mercado', []):
            d_view = d.get('duration_view', '')
            dur_class = 'badge-long' if 'Larga' in d_view else 'badge-short' if 'Corta' in d_view else 'badge-neutral'
            dur_rows += f'''<tr>
                <td><strong>{d.get('mercado', '')}</strong></td>
                <td class="center"><span class="view-badge {dur_class}">{d_view}</span></td>
                <td class="center">{d.get('benchmark', '')}</td>
                <td class="center">{d.get('recomendacion', '')}</td>
                <td>{d.get('posicion_curva', '')}</td>
                <td>{_md_to_html(d.get('rationale', ''))}</td>
            </tr>'''
        replacements['{{duration_table_rows}}'] = dur_rows

        # Duration trades
        dur_trades = ''
        for t in duration.get('trades_recomendados', []):
            dur_trades += f'''
            <div class="trade-card">
                <div class="trade-header">
                    <span class="trade-name">{_md_to_html(t.get('trade', 'N/D'))}</span>
                </div>
                <p style="color: var(--text-medium); margin-bottom: 10px;">{_md_to_html(t.get('rationale', ''))}</p>
                <div class="trade-metrics">
                    <div class="trade-metric">
                        <div class="label">Instrumento</div>
                        <div class="value">{t.get('instrumento', 'N/D')}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Carry (3M)</div>
                        <div class="value">{t.get('carry', 'N/D')}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Objetivo</div>
                        <div class="value">{t.get('target', 'N/D')}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Stop-loss</div>
                        <div class="value">{t.get('stop', 'N/D')}</div>
                    </div>
                </div>
            </div>'''
        replacements['{{duration_trades_html}}'] = dur_trades

        # 4. CREDITO
        credito = content.get('credito', {})
        replacements['{{credit_narrative}}'] = _md_to_html(credito.get('narrativa', ''))

        ig = credito.get('investment_grade', {})
        replacements['{{ig_view}}'] = ig.get('view', 'N')
        replacements['{{ig_badge_class}}'] = self._get_view_class(ig.get('view', 'N'))
        replacements['{{ig_spread}}'] = ig.get('spread_actual', '')
        replacements['{{ig_yield}}'] = ig.get('yield_total', '')
        replacements['{{ig_vs_historia}}'] = ig.get('spread_vs_historia', '')

        hy = credito.get('high_yield', {})
        replacements['{{hy_view}}'] = hy.get('view', 'N')
        replacements['{{hy_badge_class}}'] = self._get_view_class(hy.get('view', 'N'))
        replacements['{{hy_spread}}'] = hy.get('spread_actual', '')
        replacements['{{hy_yield}}'] = hy.get('yield_total', '')
        replacements['{{hy_vs_historia}}'] = hy.get('spread_vs_historia', '')

        # IG/HY por rating (real data from FRED)
        ig_rating_rows = ''
        for r in ig.get('por_rating_real', []):
            ig_rating_rows += f'''<tr>
                <td>{r.get('rating', '')}</td>
                <td class="center">{r.get('spread', '')}</td>
                <td class="center">{r.get('percentil', '-')}</td>
                <td>{_md_to_html(r.get('señal', ''))}</td>
            </tr>'''
        replacements['{{ig_rating_rows}}'] = ig_rating_rows

        hy_rating_rows = ''
        for r in hy.get('por_rating', []):
            hy_rating_rows += f'''<tr>
                <td>{r.get('rating', '')}</td>
                <td class="center">{r.get('spread', '')}</td>
                <td>{_md_to_html(r.get('comentario', ''))}</td>
            </tr>'''
        replacements['{{hy_rating_rows}}'] = hy_rating_rows

        # 5. EM DEBT
        em = content.get('em_debt', {})
        replacements['{{em_narrative}}'] = _md_to_html(em.get('narrativa', ''))

        hc = em.get('hard_currency', {})
        replacements['{{em_hc_view}}'] = hc.get('view', 'N')
        replacements['{{em_hc_class}}'] = self._get_view_class(hc.get('view', 'N'))
        replacements['{{em_hc_spread}}'] = hc.get('spread', '')
        replacements['{{em_hc_yield}}'] = hc.get('yield', '')

        lc = em.get('local_currency', {})
        replacements['{{em_lc_view}}'] = lc.get('view', 'N')
        replacements['{{em_lc_class}}'] = self._get_view_class(lc.get('view', 'N'))

        country_rows = ''
        for c in em.get('por_pais', []):
            hc_class = self._get_view_class(c.get('hc_view', 'N'))
            lc_class = self._get_view_class(c.get('lc_view', 'N'))
            country_rows += f'''<tr>
                <td><strong>{c.get('pais', '')}</strong></td>
                <td class="center"><span class="view-badge {hc_class}">{c.get('hc_view', 'N')}</span></td>
                <td class="center"><span class="view-badge {lc_class}">{c.get('lc_view', 'N')}</span></td>
                <td class="center yield-high">{c.get('yield_hc', '')}</td>
                <td class="center">{c.get('spread', '')}</td>
                <td class="center">{c.get('rating', '')}</td>
                <td>{_md_to_html(c.get('driver', ''))}</td>
            </tr>'''
        replacements['{{em_country_rows}}'] = country_rows

        # 6. CHILE
        chile = content.get('chile', {})
        sov = chile.get('soberanos', {})
        replacements['{{chile_sovereign_narrative}}'] = _md_to_html(sov.get('narrativa', ''))

        bcp_rows = ''
        for b in sov.get('curva_bcp', []):
            b_view = b.get('view', 'N')
            view_class = 'badge-ow' if 'OW' in b_view else 'badge-neutral'
            bcp_rows += f'''<tr>
                <td>{b.get('plazo', '')}</td>
                <td>{b.get('yield', '')}</td>
                <td>{b.get('vs_1m', '')}</td>
                <td><span class="view-badge {view_class}">{b_view}</span></td>
            </tr>'''
        replacements['{{chile_bcp_rows}}'] = bcp_rows

        bcu_rows = ''
        for b in sov.get('curva_bcu', []):
            b_view = b.get('view', 'N')
            view_class = 'badge-ow' if 'OW' in b_view else 'badge-neutral'
            bcu_rows += f'''<tr>
                <td>{b.get('plazo', '')}</td>
                <td>{b.get('yield', '')}</td>
                <td>{b.get('vs_1m', '')}</td>
                <td><span class="view-badge {view_class}">{b_view}</span></td>
            </tr>'''
        replacements['{{chile_bcu_rows}}'] = bcu_rows

        corp = chile.get('corporativos', {})
        replacements['{{chile_corp_narrative}}'] = _md_to_html(corp.get('narrativa', ''))

        mm = chile.get('money_market', {})
        mm_rows = ''
        for m in mm.get('alternativas', []):
            mm_rows += f'''<tr>
                <td>{m.get('instrumento', '')}</td>
                <td class="center yield-high">{m.get('tasa', '')}</td>
                <td class="center">{m.get('liquidez', '')}</td>
                <td>{m.get('view', '')}</td>
            </tr>'''
        replacements['{{chile_mm_rows}}'] = mm_rows

        # 7. RIESGOS Y OPORTUNIDADES
        risks = content.get('riesgos_oportunidades', {})

        risks_html = ''
        for r in risks.get('top_risks', []):
            risks_html += f'''
            <div class="risk-card">
                <div class="risk-header">
                    <span class="risk-name">{_md_to_html(r.get('riesgo', 'N/D'))}</span>
                    <span style="font-size: 9pt; color: var(--text-light);">
                        Prob: <strong>{r.get('probabilidad', 'N/D')}</strong> | Impacto: <strong>{r.get('impacto', r.get('severidad', 'N/D'))}</strong>
                    </span>
                </div>
                <p style="margin: 10px 0; color: var(--text-medium);">{_md_to_html(r.get('descripcion', ''))}</p>
                <p style="font-size: 9pt; color: var(--text-light);"><strong>Cobertura:</strong> {_md_to_html(r.get('hedge', r.get('mitigacion', 'N/D')))}</p>
            </div>'''
        replacements['{{risks_html}}'] = risks_html

        opps = ''.join([f'<li>{_md_to_html(o)}</li>' for o in risks.get('oportunidades', [])])
        replacements['{{opportunities_html}}'] = opps

        trades_html = ''
        for t in risks.get('trades', []):
            trades_html += f'''
            <div class="trade-card">
                <div class="trade-header">
                    <span class="trade-name">{_md_to_html(t.get('trade', 'N/D'))}</span>
                </div>
                <p style="color: var(--text-medium); margin-bottom: 10px;">{_md_to_html(t.get('rationale', ''))}</p>
                <div class="trade-metrics">
                    <div class="trade-metric">
                        <div class="label">Entrada</div>
                        <div class="value">{t.get('entry', 'N/D')}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Objetivo</div>
                        <div class="value">{t.get('target', 'N/D')}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Stop-loss</div>
                        <div class="value">{t.get('stop', 'N/D')}</div>
                    </div>
                </div>
            </div>'''
        replacements['{{trades_html}}'] = trades_html

        # 8. RESUMEN
        summary = content.get('resumen_posicionamiento', {})

        replacements['{{summary_rows}}'] = build_summary_rows(
            summary.get('tabla_final', []), key_field='dimension', value_field='recomendacion')
        replacements['{{mensaje_clave}}'] = summary.get('mensaje_clave', '')

        # Convert {{key}} → key for Jinja2 context
        context = {}
        for key, value in replacements.items():
            clean = key.replace('{{', '').replace('}}', '')
            context[clean] = str(value)

        # Charts
        if charts:
            for chart_id, img_data in charts.items():
                if img_data and img_data.startswith('data:image'):
                    context[chart_id] = f'<img src="{img_data}" style="max-width: 100%; height: auto;" alt="{chart_id}">'
                else:
                    context[chart_id] = img_data or ''

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


def main():
    """Genera el reporte RF profesional."""
    import argparse
    import glob as glob_mod

    parser = argparse.ArgumentParser(description='Greybark Research - Reporte Renta Fija')
    parser.add_argument('--output', '-o', help='Nombre archivo de salida')
    parser.add_argument('--council-file', help='JSON council result')
    parser.add_argument('--rf-data', help='JSON rf_data_collector output')
    parser.add_argument('--no-collect', action='store_true',
                        help='No recopilar RF data (solo si --rf-data)')
    args = parser.parse_args()

    # Load council result
    council_result = None
    if args.council_file:
        with open(args.council_file, 'r', encoding='utf-8') as f:
            council_result = json.load(f)
    else:
        # Auto-find most recent
        council_dir = Path(__file__).parent / "output" / "council"
        files = sorted(council_dir.glob("council_result_*.json"), reverse=True)
        if files:
            print(f"[Auto] Council: {files[0].name}")
            with open(files[0], 'r', encoding='utf-8') as f:
                council_result = json.load(f)

    # Load RF data
    market_data = None
    if args.rf_data:
        with open(args.rf_data, 'r', encoding='utf-8') as f:
            market_data = json.load(f)
    elif not args.no_collect:
        # Try to collect fresh RF data
        try:
            from rf_data_collector import RFDataCollector
            collector = RFDataCollector(verbose=True)
            market_data = collector.collect_all()
            collector.save(market_data)
        except Exception as e:
            print(f"[WARN] RF data collection failed: {e}")
        # Or auto-find most recent
        if not market_data:
            rf_dir = Path(__file__).parent / "output" / "rf_data"
            files = sorted(rf_dir.glob("rf_data_*.json"), reverse=True)
            if files:
                print(f"[Auto] RF data: {files[0].name}")
                with open(files[0], 'r', encoding='utf-8') as f:
                    market_data = json.load(f)

    renderer = RFReportRenderer(
        council_result=council_result,
        market_data=market_data,
        verbose=True,
    )
    output_path = renderer.render(output_filename=args.output)

    import subprocess
    subprocess.run(['start', '', output_path], shell=True)


if __name__ == "__main__":
    main()

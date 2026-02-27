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
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent))

from rf_content_generator import RFContentGenerator


class RFReportRenderer:
    """Renderizador del Reporte de Renta Fija profesional."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, verbose: bool = True):
        self.council_result = council_result or {}
        self.market_data = market_data or {}
        self.forecast_data = forecast_data
        self.verbose = verbose
        self.template_path = Path(__file__).parent / "templates" / "rf_report_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.content_generator = RFContentGenerator(
            self.council_result, self.market_data, forecast_data=self.forecast_data)

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

        self._print("[2/4] Cargando template profesional...")
        with open(self.template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        self._print("[3/4] Renderizando reporte...")
        html = self._render_template(template, content)

        self._print("[4/4] Generando e inyectando charts...")
        try:
            from rf_chart_generator import RFChartsGenerator
            charts_gen = RFChartsGenerator(self.market_data)
            charts = charts_gen.generate_all_charts()
            for chart_id, img_data in charts.items():
                if img_data.startswith('data:image'):
                    img_tag = f'<img src="{img_data}" style="max-width: 100%; height: auto;" alt="{chart_id}">'
                else:
                    img_tag = img_data  # placeholder HTML
                html = html.replace(f'{{{{{chart_id}}}}}', img_tag)
            real_count = len([v for v in charts.values() if 'base64' in v])
            self._print(f"  Charts: {real_count}/{len(charts)} generados con datos reales")
        except Exception as e:
            self._print(f"  [WARN] Charts: {e}")

        # Clean unresolved chart placeholders
        import re
        html = re.sub(r'\{\{rf_[a-z_]+\}\}', '', html)

        if output_filename is None:
            output_filename = f"rf_report_{datetime.now().strftime('%Y-%m-%d')}.html"

        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"\n[OK] Reporte RF generado: {output_path}")
        return str(output_path)

    def _render_template(self, template: str, content: Dict) -> str:
        """Renderiza el template con el contenido."""

        now = datetime.now()
        replacements = {
            '{{fecha_reporte}}': f"{now.day} {self._get_spanish_month(now.month)} {now.year}",
        }

        # 1. RESUMEN EJECUTIVO
        resumen = content['resumen_ejecutivo']
        postura = resumen['postura_global']

        replacements['{{postura_global}}'] = postura['view']
        replacements['{{duration_stance}}'] = postura['duration_stance']
        replacements['{{credit_stance}}'] = postura['credit_stance']
        replacements['{{postura_narrativa}}'] = postura['narrativa']

        # Stance spectrum - highlight active postura
        active_view = postura['view'].upper()
        for stance in ['cauteloso', 'neutral', 'constructivo', 'agresivo']:
            replacements[f'{{{{spectrum_active_{stance}}}}}'] = 'spectrum-active' if stance.upper() == active_view else ''

        # Summary table
        summary_rows = ''
        for r in resumen['tabla_resumen']:
            view_class = self._get_view_class(r['view'])
            summary_rows += f'''<tr>
                <td><strong>{r['segmento']}</strong></td>
                <td class="center"><span class="view-badge {view_class}">{r['view']}</span></td>
                <td class="center">{r['duration']}</td>
                <td class="center yield-high">{r['yield']}</td>
                <td class="center">{r['spread']}</td>
                <td>{r['driver']}</td>
            </tr>'''
        replacements['{{summary_table_rows}}'] = summary_rows

        key_calls = ''.join([f'<li>{kc}</li>' for kc in resumen['key_calls']])
        replacements['{{key_calls_html}}'] = key_calls

        # 2. AMBIENTE DE TASAS
        tasas = content['ambiente_tasas']
        replacements['{{rates_narrative}}'] = tasas['narrativa']

        yields_rows = ''
        for y in tasas['yields_globales']:
            yields_rows += f'''<tr>
                <td><strong>{y['mercado']}</strong></td>
                <td class="center">{y.get('y2', '-')}</td>
                <td class="center">{y.get('y5', '-')}</td>
                <td class="center yield-high">{y.get('y10', '-')}</td>
                <td class="center">{y.get('y30', '-')}</td>
                <td class="center">{y.get('curva_2_10', '-')}</td>
                <td class="center">{y.get('vs_1m', '-')}</td>
            </tr>'''
        replacements['{{yields_table_rows}}'] = yields_rows

        real_rows = ''
        for r in tasas['tasas_reales']['datos']:
            # Skip rows where all numeric values are N/D
            if r['yield_real'] == 'N/D' and r['breakeven'] == 'N/D' and r['nominal'] == 'N/D':
                continue
            real_rows += f'''<tr>
                <td>{r['mercado']}</td>
                <td class="center yield-high">{r['yield_real']}</td>
                <td class="center">{r['breakeven']}</td>
                <td class="center">{r['nominal']}</td>
                <td>{r['vs_historia']}</td>
            </tr>'''
        replacements['{{real_rates_rows}}'] = real_rows

        # 3. DURATION
        duration = content['duration']
        replacements['{{duration_narrative}}'] = duration['view_global']['rationale']

        dur_rows = ''
        for d in duration['por_mercado']:
            dur_class = 'badge-long' if 'Larga' in d['duration_view'] else 'badge-short' if 'Corta' in d['duration_view'] else 'badge-neutral'
            dur_rows += f'''<tr>
                <td><strong>{d['mercado']}</strong></td>
                <td class="center"><span class="view-badge {dur_class}">{d['duration_view']}</span></td>
                <td class="center">{d['benchmark']}</td>
                <td class="center">{d['recomendacion']}</td>
                <td>{d['posicion_curva']}</td>
                <td>{d['rationale']}</td>
            </tr>'''
        replacements['{{duration_table_rows}}'] = dur_rows

        # Duration trades
        dur_trades = ''
        for t in duration['trades_recomendados']:
            dur_trades += f'''
            <div class="trade-card">
                <div class="trade-header">
                    <span class="trade-name">{t['trade']}</span>
                </div>
                <p style="color: var(--text-medium); margin-bottom: 10px;">{t['rationale']}</p>
                <div class="trade-metrics">
                    <div class="trade-metric">
                        <div class="label">Instrumento</div>
                        <div class="value">{t['instrumento']}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Carry (3M)</div>
                        <div class="value">{t['carry']}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Target</div>
                        <div class="value">{t['target']}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Stop</div>
                        <div class="value">{t['stop']}</div>
                    </div>
                </div>
            </div>'''
        replacements['{{duration_trades_html}}'] = dur_trades

        # 4. CREDITO
        credito = content['credito']
        replacements['{{credit_narrative}}'] = credito['narrativa']

        ig = credito['investment_grade']
        replacements['{{ig_view}}'] = ig['view']
        replacements['{{ig_spread}}'] = ig['spread_actual']
        replacements['{{ig_yield}}'] = ig['yield_total']
        replacements['{{ig_vs_historia}}'] = ig['spread_vs_historia']

        hy = credito['high_yield']
        replacements['{{hy_view}}'] = hy['view']
        replacements['{{hy_spread}}'] = hy['spread_actual']
        replacements['{{hy_yield}}'] = hy['yield_total']
        replacements['{{hy_vs_historia}}'] = hy['spread_vs_historia']

        # IG/HY por rating (real data from FRED)
        ig_rating_rows = ''
        for r in ig.get('por_rating_real', []):
            ig_rating_rows += f'''<tr>
                <td>{r['rating']}</td>
                <td class="center">{r['spread']}</td>
                <td class="center">{r.get('percentil', '-')}</td>
                <td>{r.get('señal', '')}</td>
            </tr>'''
        replacements['{{ig_rating_rows}}'] = ig_rating_rows

        hy_rating_rows = ''
        for r in hy.get('por_rating', []):
            hy_rating_rows += f'''<tr>
                <td>{r['rating']}</td>
                <td class="center">{r['spread']}</td>
                <td>{r.get('comentario', '')}</td>
            </tr>'''
        replacements['{{hy_rating_rows}}'] = hy_rating_rows

        # 5. EM DEBT
        em = content['em_debt']
        replacements['{{em_narrative}}'] = em['narrativa']

        hc = em['hard_currency']
        replacements['{{em_hc_view}}'] = hc['view']
        replacements['{{em_hc_spread}}'] = hc['spread']
        replacements['{{em_hc_yield}}'] = hc['yield']

        lc = em['local_currency']
        replacements['{{em_lc_view}}'] = lc['view']

        country_rows = ''
        for c in em['por_pais']:
            hc_class = self._get_view_class(c['hc_view'])
            lc_class = self._get_view_class(c['lc_view'])
            country_rows += f'''<tr>
                <td><strong>{c['pais']}</strong></td>
                <td class="center"><span class="view-badge {hc_class}">{c['hc_view']}</span></td>
                <td class="center"><span class="view-badge {lc_class}">{c['lc_view']}</span></td>
                <td class="center yield-high">{c['yield_hc']}</td>
                <td class="center">{c['spread']}</td>
                <td class="center">{c['rating']}</td>
                <td>{c['driver']}</td>
            </tr>'''
        replacements['{{em_country_rows}}'] = country_rows

        # 6. CHILE
        chile = content['chile']
        sov = chile['soberanos']
        replacements['{{chile_sovereign_narrative}}'] = sov['narrativa']

        bcp_rows = ''
        for b in sov['curva_bcp']:
            view_class = 'badge-ow' if 'OW' in b['view'] else 'badge-neutral'
            bcp_rows += f'''<tr>
                <td>{b['plazo']}</td>
                <td>{b['yield']}</td>
                <td>{b['vs_1m']}</td>
                <td><span class="view-badge {view_class}">{b['view']}</span></td>
            </tr>'''
        replacements['{{chile_bcp_rows}}'] = bcp_rows

        bcu_rows = ''
        for b in sov['curva_bcu']:
            view_class = 'badge-ow' if 'OW' in b['view'] else 'badge-neutral'
            bcu_rows += f'''<tr>
                <td>{b['plazo']}</td>
                <td>{b['yield']}</td>
                <td>{b['vs_1m']}</td>
                <td><span class="view-badge {view_class}">{b['view']}</span></td>
            </tr>'''
        replacements['{{chile_bcu_rows}}'] = bcu_rows

        corp = chile['corporativos']
        replacements['{{chile_corp_narrative}}'] = corp['narrativa']

        mm = chile['money_market']
        mm_rows = ''
        for m in mm['alternativas']:
            mm_rows += f'''<tr>
                <td>{m['instrumento']}</td>
                <td class="center yield-high">{m['tasa']}</td>
                <td class="center">{m['liquidez']}</td>
                <td>{m['view']}</td>
            </tr>'''
        replacements['{{chile_mm_rows}}'] = mm_rows

        # 7. RIESGOS Y OPORTUNIDADES
        risks = content['riesgos_oportunidades']

        risks_html = ''
        for r in risks['top_risks']:
            risks_html += f'''
            <div class="risk-card">
                <div class="risk-header">
                    <span class="risk-name">{r['riesgo']}</span>
                    <span style="font-size: 9pt; color: var(--text-light);">
                        Prob: <strong>{r['probabilidad']}</strong> | Impacto: <strong>{r['impacto']}</strong>
                    </span>
                </div>
                <p style="margin: 10px 0; color: var(--text-medium);">{r['descripcion']}</p>
                <p style="font-size: 9pt; color: var(--text-light);"><strong>Hedge:</strong> {r['hedge']}</p>
            </div>'''
        replacements['{{risks_html}}'] = risks_html

        opps = ''.join([f'<li>{o}</li>' for o in risks['oportunidades']])
        replacements['{{opportunities_html}}'] = opps

        trades_html = ''
        for t in risks['trades']:
            trades_html += f'''
            <div class="trade-card">
                <div class="trade-header">
                    <span class="trade-name">{t['trade']}</span>
                </div>
                <p style="color: var(--text-medium); margin-bottom: 10px;">{t['rationale']}</p>
                <div class="trade-metrics">
                    <div class="trade-metric">
                        <div class="label">Entry</div>
                        <div class="value">{t['entry']}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Target</div>
                        <div class="value">{t['target']}</div>
                    </div>
                    <div class="trade-metric">
                        <div class="label">Stop</div>
                        <div class="value">{t['stop']}</div>
                    </div>
                </div>
            </div>'''
        replacements['{{trades_html}}'] = trades_html

        # 8. RESUMEN
        summary = content['resumen_posicionamiento']

        sum_rows = ''
        for s in summary['tabla_final']:
            sum_rows += f'''<tr>
                <th>{s['dimension']}</th>
                <td>{s['recomendacion']}</td>
            </tr>'''
        replacements['{{summary_rows}}'] = sum_rows
        replacements['{{mensaje_clave}}'] = summary['mensaje_clave']

        # Apply all replacements
        for key, value in replacements.items():
            template = template.replace(key, str(value))

        return template

    def _get_view_class(self, view: str) -> str:
        """Retorna clase CSS segun view."""
        view_upper = view.upper()
        if view_upper in ['OW', 'OVERWEIGHT']:
            return 'badge-ow'
        elif view_upper in ['UW', 'UNDERWEIGHT']:
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

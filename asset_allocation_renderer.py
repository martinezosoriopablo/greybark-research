# -*- coding: utf-8 -*-
"""
Greybark Research - Asset Allocation Report Renderer
======================================================

Renderiza el reporte de Asset Allocation combinando:
- Contenido narrativo (AssetAllocationContentGenerator)
- Template HTML profesional
- Datos cuantitativos

Produce el reporte final con recomendaciones OW/UW listo para cliente.
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

from asset_allocation_content_generator import AssetAllocationContentGenerator
from council_data_collector import CouncilDataCollector
from table_builder import (
    build_calendar_rows, build_view_rows, Badge, fmt_bold, fmt_small
)


class AssetAllocationRenderer:
    """Renderizador del Reporte de Asset Allocation profesional."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, verbose: bool = True, branding: dict = None):
        self.council_result = council_result or {}
        self.market_data = market_data or {}
        self.forecast_data = forecast_data
        self.verbose = verbose
        self.branding = branding or {}
        self.template_path = Path(__file__).parent / "templates" / "asset_allocation_professional.html"
        self.template_name = "asset_allocation_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            undefined=Undefined,
            autoescape=False,
        )

        # Inicializar generador de contenido con datos cuantitativos
        self.content_generator = AssetAllocationContentGenerator(
            self.council_result, quant_data=self.market_data,
            forecast_data=self.forecast_data,
            company_name=self.branding.get('company_name', '')
        )

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

    @staticmethod
    def _sanitize_css_class(value: str) -> str:
        """Sanitize a string for use as a CSS class name."""
        import re
        s = value.lower().strip()
        # Map known values
        css_map = {
            'sin recomendación': 'neutral', 'sin recomendacion': 'neutral',
            'n/d': 'nd', 'n/a': 'na', 'neutral': 'n',
            'sobreponderar': 'ow', 'sobreponder': 'ow', 'ow': 'ow', 'overweight': 'ow',
            'subponderar': 'uw', 'subponder': 'uw', 'uw': 'uw', 'underweight': 'uw',
        }
        if s in css_map:
            return css_map[s]
        # Replace non-alphanumeric chars with hyphens
        s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
        return s or 'unknown'

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
        self._print("GREYBARK - ASSET ALLOCATION REPORT RENDERER")
        self._print("="*60)

        # 1. Generar contenido
        self._print("[1/3] Generando contenido narrativo...")
        content = self.content_generator.generate_all_content()
        self.last_content = content

        # 2. Cargar template Jinja2
        self._print("[2/3] Cargando template profesional...")
        template = self._jinja_env.get_template(self.template_name)

        # 3. Renderizar
        self._print("[3/3] Renderizando reporte...")
        html = self._render_template(template, content)

        # 4. Guardar
        if output_filename is None:
            output_filename = f"asset_allocation_{datetime.now().strftime('%Y-%m-%d')}_professional.html"

        # Append data provenance div (hidden, for audit)
        html = self._append_provenance(html)

        # Convert any remaining markdown bold/italic to HTML
        html = _md_to_html_inline(html)

        # Strip all N/D from final output
        from html_nd_cleaner import clean_nd
        html = clean_nd(html)

        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"\n[OK] Reporte generado: {output_path}")
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
                    f'data-report="aa" data-generated="{datetime.now().isoformat()}">'
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

    def _render_template(self, template, content: Dict) -> str:
        """Renderiza el template con el contenido."""

        # Metadata
        now = datetime.now()
        replacements = {
            '{{fecha_reporte}}': f"{now.day} {self._get_spanish_month(now.month)} {now.year}",
            '{{timestamp}}': now.isoformat()
        }

        # 1. RESUMEN EJECUTIVO
        resumen = content.get('resumen_ejecutivo', {})
        postura = resumen.get('postura', {})

        replacements['{{intro_paragraph}}'] = resumen.get('parrafo_intro', '')
        postura_view = postura.get('view', 'Neutral')
        replacements['{{postura_view}}'] = postura_view
        replacements['{{postura_sesgo}}'] = postura.get('sesgo', '')
        replacements['{{postura_class}}'] = (postura_view or 'neutral').lower()
        replacements['{{conviccion_text}}'] = postura.get('conviccion', '')

        # Stance spectrum - highlight active postura
        active_view = (postura_view or '').upper()
        for stance in ['cauteloso', 'neutral', 'constructivo', 'agresivo']:
            replacements[f'{{{{spectrum_active_{stance}}}}}'] = 'spectrum-active' if stance.upper() == active_view else ''

        # Conviccion porcentaje
        conv_map = {'ALTA': 85, 'MEDIA-ALTA': 75, 'MEDIA': 60, 'BAJA': 40}
        replacements['{{conviccion_pct}}'] = str(conv_map.get(postura.get('conviccion', ''), 60))

        # Key points
        kp_html = ''.join([f'<li>{kp}</li>' for kp in resumen.get('key_points', [])])
        replacements['{{key_points_html}}'] = kp_html
        replacements['{{catalizador}}'] = (resumen.get('catalizador', '') or '').strip(' |')

        # 2. DASHBOARD DE POSICIONAMIENTO
        dashboard = content.get('dashboard', {})
        for key, placeholder in [('renta_variable', 'dashboard_rv_rows'),
                                  ('renta_fija', 'dashboard_rf_rows'),
                                  ('commodities_fx', 'dashboard_comm_rows')]:
            rows_html = ''
            for item in dashboard.get(key, []):
                item_view = item.get('view', 'N')
                item_cambio = item.get('cambio', '→')
                view_class = f"dash-{self._sanitize_css_class(item_view)}"
                arrow_map = {'↑': 'dash-arrow-up', '↓': 'dash-arrow-down',
                             '→': 'dash-arrow-flat', 'NEW': 'dash-arrow-up'}
                arrow_class = arrow_map.get(item_cambio, 'dash-arrow-flat')
                rows_html += f'''<div class="dashboard-row">
                    <span class="dashboard-asset">{item.get('asset', '')}</span>
                    <span class="{view_class}">{item_view}</span>
                    <span class="dash-arrow {arrow_class}">{item_cambio}</span>
                    <span class="dash-conviction">{item.get('conviccion', '')}</span>
                </div>'''
            replacements[f'{{{{{placeholder}}}}}'] = rows_html

        # 3. MES EN REVISION
        mes = content.get('mes_en_revision', {})

        # Economia Global
        eco = mes.get('economia_global', {})
        replacements['{{economia_global_narrativa}}'] = eco.get('narrativa', '')
        eco_rows = ''.join([
            f"<tr><td>{d.get('indicador', '')}</td><td>{d.get('actual', '')}</td><td>{d.get('anterior', '')}</td><td>{d.get('sorpresa', '')}</td></tr>"
            for d in eco.get('datos', [])
        ])
        replacements['{{economia_global_tabla}}'] = eco_rows

        # Mercados
        merc = mes.get('mercados', {})
        replacements['{{mercados_narrativa}}'] = merc.get('narrativa', '')
        merc_rows = ''.join([
            f"<tr><td>{d.get('asset', '')}</td><td>{d.get('retorno', '')}</td><td>{d.get('ytd', d.get('cambio', ''))}</td></tr>"
            for d in merc.get('performance', [])
        ])
        replacements['{{mercados_tabla}}'] = merc_rows

        # Geopolitica
        geo = mes.get('politica_geopolitica', {})
        replacements['{{geopolitica_narrativa}}'] = geo.get('narrativa', '')
        geo_rows = ''.join([
            f"<tr><td>{d.get('evento', '')}</td><td>{d.get('impacto', '')}</td><td>{d.get('probabilidad', '')}</td></tr>"
            for d in geo.get('eventos', [])
        ])
        replacements['{{geopolitica_tabla}}'] = geo_rows

        # Chile
        chile = mes.get('chile', {})
        replacements['{{chile_narrativa}}'] = chile.get('narrativa', '')
        chile_rows = ''.join([
            f"<tr><td>{d.get('indicador', '')}</td><td>{d.get('valor', '')}</td><td>{d.get('tendencia', '')}</td></tr>"
            for d in chile.get('datos', [])
        ])
        replacements['{{chile_tabla}}'] = chile_rows

        # 3. ESCENARIOS
        esc = content.get('escenarios', {})
        escenario_base = esc.get('escenario_base', '')
        replacements['{{escenario_base}}'] = escenario_base
        replacements['{{escenario_base_desc}}'] = esc.get('descripcion_base', '')

        # Find base scenario probability
        base_prob = 50
        for e in esc.get('escenarios', []):
            e_nombre = e.get('nombre', '')
            if (e_nombre or '').upper() == (escenario_base or '').upper().replace('_', ' '):
                base_prob = e.get('probabilidad', 50)
                break
        replacements['{{escenario_base_prob}}'] = str(base_prob)

        # Scenario cards
        scenario_html = ''
        for e in esc.get('escenarios', []):
            e_nombre = e.get('nombre', '')
            is_base = 'base' if (e_nombre or '').upper().replace(' ', '_') == (escenario_base or '').upper().replace(' ', '_') else ''
            scenario_html += f'''
            <div class="scenario-card {is_base}">
                <div class="scenario-name">{_esc(e_nombre)}</div>
                <div class="scenario-prob">{_esc(e.get('probabilidad', ''))}%</div>
                <div class="scenario-desc">{_esc(e.get('descripcion', ''))}</div>
                <div style="font-size: 9pt; color: #718096;"><strong>Qué comprar:</strong> {_esc(e.get('que_comprar', ''))}</div>
            </div>
            '''
        replacements['{{scenarios_html}}'] = scenario_html

        # Scenarios table
        impl_map = {'UP': '+', 'DOWN': '-', 'SIDEWAYS': '=', 'MIXED': '+/-'}
        esc_table = ''
        for e in esc.get('escenarios', []):
            impl = e.get('implicancias', {})
            eq_val = impl.get('equities', 'N/D')
            bd_val = impl.get('bonds', 'N/D')
            usd_val = impl.get('usd', 'N/D')
            cm_val = impl.get('commodities', 'N/D')
            esc_table += f'''<tr>
                <td>{_esc(e.get('nombre', ''))}</td>
                <td><strong>{_esc(e.get('probabilidad', ''))}%</strong></td>
                <td>{impl_map.get(eq_val, eq_val)}</td>
                <td>{impl_map.get(bd_val, bd_val)}</td>
                <td>{impl_map.get(usd_val, usd_val)}</td>
                <td>{impl_map.get(cm_val, cm_val)}</td>
            </tr>'''
        replacements['{{scenarios_table}}'] = esc_table

        # 4. REGIONAL VIEWS
        regional_html = ''
        for view in content.get('views_regionales', []):
            view_val = view.get('view', 'N')
            view_class = self._sanitize_css_class(view_val)
            badge_class = f"badge-{view_class}"

            # Arguments
            args_favor = ''.join([
                f"<li>{_esc(a.get('punto', ''))}<span class='argument-dato'>{_esc(a.get('dato', ''))}</span></li>"
                for a in view.get('argumentos_favor', [])
            ])
            args_contra = ''.join([
                f"<li>{_esc(a.get('punto', ''))}<span class='argument-dato'>{_esc(a.get('dato', ''))}</span></li>"
                for a in view.get('argumentos_contra', [])
            ])

            regional_html += f'''
            <div class="view-card">
                <div class="view-header">
                    <span class="view-region">{_esc(view.get('region', ''))}</span>
                    <span class="view-badge {badge_class}">{_esc(view_val)} | Conviccion: {_esc(view.get('conviccion', ''))}</span>
                </div>
                <div class="view-body">
                    <div class="view-tesis">{_esc(view.get('tesis', ''))}</div>
                    <div class="arguments-grid">
                        <div class="arguments-column pro">
                            <h4>Argumentos a Favor</h4>
                            <ul>{args_favor}</ul>
                        </div>
                        <div class="arguments-column contra">
                            <h4>Argumentos en Contra</h4>
                            <ul>{args_contra}</ul>
                        </div>
                    </div>
                    <div class="trigger-box">
                        <strong>Trigger para cambiar de opinión:</strong><br>
                        {_esc(view.get('trigger_cambio', ''))}
                    </div>
                </div>
            </div>
            '''
        replacements['{{regional_views_html}}'] = regional_html

        # 5. ASSET CLASSES
        ac = content.get('asset_classes', {})

        # Equity
        eq = ac.get('renta_variable', {})
        replacements['{{equity_view_global}}'] = eq.get('view_global', '')
        eq_rows = ''.join([
            f"<tr><td>{_esc(r.get('region', ''))}</td><td><span class='view-badge badge-{self._sanitize_css_class(r.get('view', 'N'))}'>{_esc(r.get('view', 'N'))}</span></td><td>{_esc(r.get('rationale', ''))}</td></tr>"
            for r in eq.get('por_region', [])
        ])
        replacements['{{equity_regions_table}}'] = eq_rows
        replacements['{{sectores_preferidos}}'] = ', '.join(eq.get('sectores_preferidos', []))
        replacements['{{sectores_evitar}}'] = ', '.join(eq.get('sectores_evitar', []))
        replacements['{{factor_tilt}}'] = eq.get('factor_tilt', '')

        # Fixed Income
        rf = ac.get('renta_fija', {})
        replacements['{{rf_view_tasas}}'] = rf.get('view_tasas', '')
        replacements['{{rf_view_duration}}'] = rf.get('view_duration', '')
        replacements['{{rf_view_credito}}'] = rf.get('view_credito', '')
        rf_rows = ''.join([
            f"<tr><td>{_esc(c.get('tramo', ''))}</td><td><span class='view-badge badge-{self._sanitize_css_class(c.get('view', 'N'))}'>{_esc(c.get('view', 'N'))}</span></td><td>{_esc(c.get('rationale', ''))}</td></tr>"
            for c in rf.get('curva', [])
        ])
        replacements['{{rf_curva_table}}'] = rf_rows

        chile_rf = rf.get('chile_especifico', {})
        replacements['{{chile_tpm_path}}'] = chile_rf.get('tpm_path', '')
        replacements['{{chile_carry_trade}}'] = chile_rf.get('carry_trade', '')
        replacements['{{chile_rf_recomendacion}}'] = chile_rf.get('recomendacion', '')

        # FX
        fx = ac.get('monedas', {})
        replacements['{{fx_view_usd}}'] = fx.get('view_usd', '')
        fx_rows = ''.join([
            f"<tr><td>{_esc(p.get('par', ''))}</td><td>{_esc(p.get('view', ''))}</td><td>{_esc(p.get('target_3m', ''))}</td><td>{_esc(p.get('target_12m', ''))}</td><td>{_esc(p.get('rationale', ''))}</td></tr>"
            for p in fx.get('pares', [])
        ])
        replacements['{{fx_table}}'] = fx_rows

        # Commodities
        comm = ac.get('commodities', {})
        comm_rows = ''.join([
            f"<tr><td>{_esc(c.get('nombre', ''))}</td><td>{_esc(c.get('view', ''))}</td><td>{_esc(c.get('target', ''))}</td><td>{_esc(c.get('rationale', ''))}</td></tr>"
            for c in comm.get('commodities', [])
        ])
        replacements['{{commodities_table}}'] = comm_rows

        # 6. RISKS
        risks = content.get('riesgos', {})

        # Risk cards
        risks_html = ''
        for r in risks.get('top_risks', []):
            risks_html += f'''
            <div class="risk-card">
                <div class="risk-header">
                    <span class="risk-name">{_esc(r.get('nombre', ''))}</span>
                    <span class="risk-metrics">
                        <span>Prob: <strong>{_esc(r.get('probabilidad', ''))}%</strong></span>
                        <span>Impacto: <strong>{_esc(r.get('impacto', ''))}</strong></span>
                    </span>
                </div>
                <div class="risk-body">
                    <p>{_esc(r.get('descripcion', ''))}</p>
                    <p style="font-size: 9pt; color: #718096;"><strong>Señal temprana:</strong> {_esc(r.get('senal_temprana', ''))}</p>
                    <div class="risk-hedge">
                        <strong>Hedge recomendado:</strong><br>
                        {_esc(r.get('hedge', ''))}
                    </div>
                </div>
            </div>
            '''
        replacements['{{risks_html}}'] = risks_html

        # Calendar
        replacements['{{calendar_table}}'] = build_calendar_rows(risks.get('calendario_eventos', []))

        # Triggers
        triggers_html = ''.join([f'<li>{_esc(t)}</li>' for t in risks.get('triggers_reconvocatoria', [])])
        replacements['{{triggers_html}}'] = triggers_html

        # 8. PORTAFOLIOS MODELO
        portfolios = content.get('portafolios_modelo', [])
        if portfolios:
            # Header: profile names
            header_html = ''
            for p in portfolios:
                header_html += f'<th>{p.get("perfil", "")}<br><span class="port-risk-score">Riesgo: {p.get("risk_score", "")}</span></th>'
            replacements['{{portfolios_header_html}}'] = header_html

            # Body: asset classes as rows, profiles as columns
            first_allocs = portfolios[0].get('allocations', [])
            asset_names = [a.get('asset', '') for a in first_allocs]
            body_html = ''
            for i, asset in enumerate(asset_names):
                body_html += '<tr>'
                body_html += f'<td>{asset}</td>'
                for p in portfolios:
                    p_allocs = p.get('allocations', [])
                    alloc = p_allocs[i] if i < len(p_allocs) else {}
                    alloc_cambio = alloc.get('cambio', '→')
                    cambio_map = {'↑': 'pct-change-up', '↓': 'pct-change-down', '→': 'pct-change-flat'}
                    cambio_class = cambio_map.get(alloc_cambio, 'pct-change-flat')
                    arrow_map = {'↑': '&#9650;', '↓': '&#9660;', '→': ''}
                    arrow_html = arrow_map.get(alloc_cambio, '')
                    arrow_span = f' <span class="{cambio_class}">{arrow_html}</span>' if arrow_html else ''
                    body_html += f'<td>{alloc.get("pct", 0)}%{arrow_span}</td>'
                body_html += '</tr>'
            # Total row
            body_html += '<tr class="total-row">'
            body_html += '<td>Total</td>'
            for p in portfolios:
                total = sum(a.get('pct', 0) for a in p.get('allocations', []))
                body_html += f'<td>{total}%</td>'
            body_html += '</tr>'
            replacements['{{portfolios_body_html}}'] = body_html
        else:
            replacements['{{portfolios_header_html}}'] = ''
            replacements['{{portfolios_body_html}}'] = ''

        # 9. FOCUS LIST
        focus = content.get('focus_list', {})
        focus_html = ''
        category_titles = {
            'renta_variable': 'Renta Variable',
            'renta_fija': 'Renta Fija',
            'commodities': 'Commodities & FX'
        }
        for cat_key, cat_title in category_titles.items():
            items = focus.get(cat_key, [])
            if not items:
                continue
            focus_html += f'''<div class="focus-category">
                <div class="focus-category-title">{cat_title}</div>
                <table class="focus-table">
                    <thead>
                        <tr>
                            <th>Ticker</th>
                            <th>Instrumento</th>
                            <th>View</th>
                            <th>Rationale</th>
                        </tr>
                    </thead>
                    <tbody>'''
            for item in items:
                item_view = item.get('view', 'N')
                badge_class = f"badge-{self._sanitize_css_class(item_view)}"
                focus_html += f'''<tr>
                    <td><span class="focus-ticker">{_esc(item.get('ticker', ''))}</span></td>
                    <td><span class="focus-name">{_esc(item.get('nombre', ''))}</span></td>
                    <td><span class="view-badge {badge_class}">{_esc(item_view)}</span></td>
                    <td>{_esc(item.get('rationale', ''))}</td>
                </tr>'''
            focus_html += '''</tbody>
                </table>
            </div>'''
        replacements['{{focus_list_html}}'] = focus_html

        # 10. CAUSAL TREE
        replacements['{{causal_tree_html}}'] = self._render_causal_tree()

        # Convert {{key}} → key for Jinja2 context
        context = {}
        for key, value in replacements.items():
            clean = key.replace('{{', '').replace('}}', '')
            context[clean] = str(value)

        # Inject branding (templates use |default() for fallback)
        if self.branding:
            context.update(self.branding)

        return template.render(**context)


    def _render_causal_tree(self) -> str:
        """Render CAUSAL_TREE JSON as SVG flow diagram."""
        from council_parser import CouncilParser
        from causal_tree_renderer import render_causal_tree_html
        parser = CouncilParser(self.council_result)
        tree = parser.get_causal_tree()
        if not tree:
            return ''
        return render_causal_tree_html(tree)


def main():
    """Genera el reporte de Asset Allocation profesional."""
    import argparse

    parser = argparse.ArgumentParser(description='Generador Reporte Asset Allocation Profesional')
    parser.add_argument('--council-file', help='Archivo JSON con resultado del council')
    parser.add_argument('--output', '-o', help='Nombre archivo de salida')
    args = parser.parse_args()

    # Cargar council result si existe
    council_result = None
    council_file = args.council_file

    if not council_file:
        # Buscar el mas reciente (aa_council o council_result)
        output_dir = Path(__file__).parent / "output" / "council"
        council_files = list(output_dir.glob("aa_council_*.json")) + list(output_dir.glob("council_result_*.json"))
        if council_files:
            council_file = str(sorted(council_files)[-1])

    if council_file:
        print(f"[INFO] Cargando council: {council_file}")
        with open(council_file, 'r', encoding='utf-8') as f:
            council_result = json.load(f)

    renderer = AssetAllocationRenderer(council_result=council_result, verbose=True)
    output_path = renderer.render(output_filename=args.output)

    # Abrir en navegador
    import webbrowser
    webbrowser.open(str(output_path))


if __name__ == "__main__":
    main()

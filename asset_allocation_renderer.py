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


def _esc_narrative(val, default='') -> str:
    """HTML-escape but preserve <strong>/<em> tags and convert **markdown** bold."""
    if val is None:
        return default
    text = _html_escape(str(val))
    text = text.replace('&lt;strong&gt;', '<strong>').replace('&lt;/strong&gt;', '</strong>')
    text = text.replace('&lt;em&gt;', '<em>').replace('&lt;/em&gt;', '</em>')
    text = text.replace('&lt;br&gt;', '<br>').replace('&lt;br/&gt;', '<br>')
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


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

    def _safe_q(self, *keys):
        """Navigate market_data by key path, return None if missing."""
        d = self.market_data
        if not d:
            return None
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return None
            d = d[k]
        if isinstance(d, dict) and ('value' in d or 'current' in d):
            d = d.get('value') or d.get('current')
        try:
            return float(d) if d is not None else None
        except (ValueError, TypeError):
            return None

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

        # Post-render quality check
        from report_quality_checker import check_report_quality, print_quality_report
        issues = check_report_quality(html, 'aa')
        print_quality_report(issues, 'aa')

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
                from report_enhancements import conviction_stars
                conv_html = conviction_stars(item.get('conviccion', ''))
                rows_html += f'''<div class="dashboard-row">
                    <span class="dashboard-asset">{item.get('asset', '')}</span>
                    <span class="{view_class}">{item_view}</span>
                    <span class="dash-arrow {arrow_class}">{item_cambio}</span>
                    <span class="dash-conviction">{conv_html}</span>
                </div>'''
            replacements[f'{{{{{placeholder}}}}}'] = rows_html

        # 1b. TRAFFIC-LIGHT GRID + PULL QUOTE
        try:
            from report_enhancements import generate_traffic_light_grid_html, generate_pull_quote_html

            # Build traffic-light from dashboard views
            tl_views = {}
            for item in dashboard.get('renta_variable', []) + dashboard.get('renta_fija', []) + dashboard.get('commodities_fx', []):
                asset = item.get('asset', '')
                view = item.get('view', 'N')
                conv = item.get('conviccion', '')
                tl_views[asset] = {
                    'tactical': {'view': view, 'conviction': conv},
                    'strategic': {'view': view, 'conviction': conv},
                }
            replacements['{{traffic_light_html}}'] = generate_traffic_light_grid_html(tl_views)

            # Pull quote from council final recommendation (first strong statement)
            final_rec = self.council_result.get('final_recommendation', '') if self.council_result else ''
            pull_text = ''
            if final_rec:
                # Find first sentence that contains a strong view
                import re
                sentences = re.split(r'[.!]\s+', final_rec[:2000])
                for s in sentences:
                    if any(word in s.lower() for word in ['creemos', 'vemos', 'nuestra lectura', 'adoptamos', 'mantenemos', 'recomendamos']):
                        pull_text = s.strip().rstrip('.')
                        break
            replacements['{{pull_quote_html}}'] = generate_pull_quote_html(pull_text) if pull_text else ''
        except Exception as e:
            if self.verbose:
                print(f"  [WARN] Traffic light/pull quote: {e}")
            replacements['{{traffic_light_html}}'] = ''
            replacements['{{pull_quote_html}}'] = ''

        # 2a. QUANT SIGNAL DASHBOARD + Z-SCORE TABLE
        try:
            from report_enhancements import generate_quant_signal_dashboard_html, generate_zscore_table_html

            # Build quant signals from TAA + council views
            taa = self.market_data.get('taa', {}) if self.market_data else {}
            tilts = taa.get('tilts', {}).get('tilts_by_class', {}) if taa else {}

            quant_signals = {}
            for asset_class in ['US Equity', 'Intl Equity', 'Fixed Income', 'Commodities', 'Alternatives']:
                tilt = tilts.get(asset_class, {})
                mom = tilt.get('momentum_signal')
                quant_signals[asset_class] = {
                    'momentum': 'positive' if mom and mom > 0 else ('negative' if mom and mom < 0 else None),
                    'carry': None,  # Could be enriched from yield data
                    'value': None,  # Could be enriched from PE percentiles
                    'vol_regime': None,
                    'overlay': '',
                    'final_view': '',
                }
            replacements['{{quant_signals_html}}'] = generate_quant_signal_dashboard_html(quant_signals) if any(
                s.get('momentum') for s in quant_signals.values()) else ''

            # Build z-score table from Bloomberg percentiles + quant data
            zscore_metrics = []
            z_data = [
                ('VIX', 'risk', 'vix', '', 20.0),
                ('UST 10Y', 'yield_curve', '10Y', '%', 2.5),
                ('IG Spread', 'credit_spreads', 'ig_spread', 'bp', 120.0),
                ('S&P 500 P/E', 'equity', 'pe', 'x', 20.0),
                ('CPI Core', 'inflation', 'cpi_core_yoy', '%', 2.5),
                ('TPM Chile', 'chile', 'tpm', '%', 3.5),
            ]
            for name, *path, unit, hist_avg in z_data:
                val = self._safe_q(*path) if len(path) > 1 else self._safe_q(path[0])
                if val is not None and hist_avg > 0:
                    # Approximate z-score using percentile from Bloomberg if available
                    z_approx = (val - hist_avg) / (hist_avg * 0.3) if hist_avg else None
                    zscore_metrics.append({
                        'name': name, 'current': val, 'avg_5y': hist_avg,
                        'zscore': z_approx, 'unit': unit,
                    })
            replacements['{{zscore_table_html}}'] = generate_zscore_table_html(zscore_metrics) if zscore_metrics else ''
        except Exception as e:
            if self.verbose:
                print(f"  [WARN] Quant signals/zscore: {e}")
            replacements['{{quant_signals_html}}'] = ''
            replacements['{{zscore_table_html}}'] = ''

        # 2a-cont. TEMA CENTRAL DEL MES
        try:
            from report_enhancements import generate_tema_central_html
            intel = self.council_result.get('intelligence', {}) if self.council_result else {}
            themes = intel.get('themes', {})
            # Get analyst calls if available
            try:
                from analyst_calls_reader import AnalystCallsReader
                acr = AnalystCallsReader(verbose=False)
                calls = acr.get_recent_calls(days=7)
            except Exception:
                calls = []
            replacements['{{tema_central_html}}'] = generate_tema_central_html(themes, calls, variant='full')
        except Exception as e:
            if self.verbose:
                print(f"  [WARN] Tema central: {e}")
            replacements['{{tema_central_html}}'] = ''

        # 2b. TIER 2 ENHANCEMENTS: "Qué Cambió" + "Qué Está Priceado"
        try:
            from report_enhancements import generate_what_changed_html, generate_whats_priced_in_html

            # Build current views for "What Changed"
            current_views = {}
            for item in dashboard.get('renta_variable', []) + dashboard.get('renta_fija', []) + dashboard.get('commodities_fx', []):
                current_views[item.get('asset', '')] = {
                    'view': item.get('view', ''),
                    'level': item.get('nivel', ''),
                    'label': item.get('asset', ''),
                }

            # Get previous views from historical store
            prev_views = {}
            try:
                from historical_store import HistoricalStore
                store = HistoricalStore()
                prev = store.get_previous()
                # Map historical metrics to views (simplified)
                if prev:
                    prev_views = {k: {'view': '', 'level': str(v)} for k, v in prev.items()}
            except Exception:
                pass

            replacements['{{what_changed_html}}'] = generate_what_changed_html(current_views, prev_views)

            # Build rate data for "What's Priced In"
            rate_data = {
                'fed_funds_current': self._safe_q('rates', 'fed_funds', 'current'),
                'fed_terminal': self._safe_q('rates', 'terminal_rate'),
                'tpm_current': self._safe_q('chile', 'tpm'),
                'tpm_terminal': self._safe_q('chile_extended', 'eof_expectations', 'tpm_12m'),
                'sp500_pe': self._safe_q('equity', 'valuations', 'us', 'pe_forward') or self._safe_q('equity', 'valuations', 'us', 'pe_trailing'),
                'ust_10y': self._safe_q('yield_curve', 'current_curve', '10Y'),
            }
            replacements['{{whats_priced_in_html}}'] = generate_whats_priced_in_html(rate_data)
        except Exception as e:
            if self.verbose:
                print(f"  [WARN] Tier 2 enhancements: {e}")
            replacements['{{what_changed_html}}'] = ''
            replacements['{{whats_priced_in_html}}'] = ''

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

        # Copper sensitivity for Chile
        try:
            from report_enhancements import generate_copper_sensitivity_html
            copper = self._safe_q('equity', 'bcch_indices', 'copper', 'value')
            usdclp = self._safe_q('chile', 'usd_clp')
            replacements['{{copper_sensitivity_html}}'] = generate_copper_sensitivity_html(copper, usdclp)
        except Exception:
            replacements['{{copper_sensitivity_html}}'] = ''

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
                <div class="scenario-desc">{_esc_narrative(e.get('descripcion', ''))}</div>
                <div style="font-size: 9pt; color: #718096;"><strong>Qué comprar:</strong> {_esc(e.get('que_comprar', ''))}</div>
            </div>
            '''
        replacements['{{scenarios_html}}'] = scenario_html

        # Scenarios table — only show implicancias if at least one scenario has them
        impl_map = {'UP': '+', 'DOWN': '-', 'SIDEWAYS': '=', 'MIXED': '+/-'}
        has_impl = any(e.get('implicancias') for e in esc.get('escenarios', []))
        esc_table = ''
        for e in esc.get('escenarios', []):
            impl = e.get('implicancias', {})
            eq_val = impl.get('equities', '') if has_impl else ''
            bd_val = impl.get('bonds', '') if has_impl else ''
            usd_val = impl.get('usd', '') if has_impl else ''
            cm_val = impl.get('commodities', '') if has_impl else ''
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
                    <div class="view-tesis">{_esc_narrative(view.get('tesis', ''))}</div>
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
            f"<tr><td>{_esc(r.get('region', ''))}</td><td><span class='view-badge badge-{self._sanitize_css_class(r.get('view', 'N'))}'>{_esc(r.get('view', 'N'))}</span></td><td>{_esc_narrative(r.get('rationale', ''))}</td></tr>"
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
            f"<tr><td>{_esc(c.get('tramo', ''))}</td><td><span class='view-badge badge-{self._sanitize_css_class(c.get('view', 'N'))}'>{_esc(c.get('view', 'N'))}</span></td><td>{_esc_narrative(c.get('rationale', ''))}</td></tr>"
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
            f"<tr><td>{_esc(p.get('par', ''))}</td><td>{_esc(p.get('view', ''))}</td><td>{_esc(p.get('target_3m', ''))}</td><td>{_esc(p.get('target_12m', ''))}</td><td>{_esc_narrative(p.get('rationale', ''))}</td></tr>"
            for p in fx.get('pares', [])
        ])
        replacements['{{fx_table}}'] = fx_rows

        # Commodities
        comm = ac.get('commodities', {})
        comm_rows = ''.join([
            f"<tr><td>{_esc(c.get('nombre', ''))}</td><td>{_esc(c.get('view', ''))}</td><td>{_esc(c.get('target', ''))}</td><td>{_esc_narrative(c.get('rationale', ''))}</td></tr>"
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
                    <p>{_esc_narrative(r.get('descripcion', ''))}</p>
                    <p style="font-size: 9pt; color: #718096;"><strong>Señal temprana:</strong> {_esc(r.get('senal_temprana', ''))}</p>
                    <div class="risk-hedge">
                        <strong>Hedge recomendado:</strong><br>
                        {_esc_narrative(r.get('hedge', ''))}
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

        # 7b. "DÓNDE PODEMOS ESTAR EQUIVOCADOS" (Bridgewater-style)
        try:
            from report_enhancements import generate_where_wrong_html
            # Extract falsifiable conditions from risks
            where_wrong_risks = []
            for r in risks.get('top_risks', []):
                if r.get('senal_temprana') or r.get('hedge'):
                    where_wrong_risks.append({
                        'condition': r.get('nombre', ''),
                        'trigger': r.get('senal_temprana', 'Ver análisis del comité'),
                        'impact': f"Prob: {r.get('probabilidad', '?')}% — {r.get('impacto', '')}",
                        'probability': f"{r.get('probabilidad', '?')}%",
                    })
            replacements['{{where_wrong_html}}'] = generate_where_wrong_html(where_wrong_risks)
        except Exception:
            replacements['{{where_wrong_html}}'] = ''

        # 7c. CROSS-ASSET IMPLICATIONS MATRIX
        try:
            from report_enhancements import generate_cross_asset_matrix_html
            # Build from council scenario base + views
            base_scenario = content.get('escenarios', {}).get('escenario_base', 'Escenario base del comité')
            equity_view = content.get('asset_classes', {}).get('renta_variable', {}).get('view_global', '')
            rf_view = content.get('asset_classes', {}).get('renta_fija', {}).get('view_tasas', '')
            fx_view = content.get('asset_classes', {}).get('monedas', {}).get('view_usd', '')
            comm_view = content.get('asset_classes', {}).get('commodities', {}).get('commodities', [{}])

            implications = {}
            if equity_view:
                direction = 'down' if 'UW' in equity_view.upper() or 'BAJO' in equity_view.upper() else ('up' if 'OW' in equity_view.upper() else 'neutral')
                implications['Renta Variable'] = {'direction': direction, 'rationale': equity_view[:100]}
            if rf_view:
                direction = 'down' if 'HIGHER' in rf_view.upper() or 'ALZA' in rf_view.upper() else ('up' if 'LOWER' in rf_view.upper() or 'BAJA' in rf_view.upper() else 'neutral')
                implications['Renta Fija'] = {'direction': direction, 'rationale': rf_view[:100]}
            if fx_view:
                implications['USD / FX'] = {'direction': 'neutral', 'rationale': fx_view[:100]}
            if comm_view:
                implications['Commodities'] = {'direction': 'neutral', 'rationale': 'Ver detalle por commodity'}

            if implications:
                replacements['{{cross_asset_html}}'] = generate_cross_asset_matrix_html({
                    'base_scenario': base_scenario if isinstance(base_scenario, str) else 'Escenario base',
                    'implications': implications,
                })
            else:
                replacements['{{cross_asset_html}}'] = ''
        except Exception:
            replacements['{{cross_asset_html}}'] = ''

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
                    <td>{_esc_narrative(item.get('rationale', ''))}</td>
                </tr>'''
            focus_html += '''</tbody>
                </table>
            </div>'''
        replacements['{{focus_list_html}}'] = focus_html

        # 10. CAUSAL TREE
        replacements['{{causal_tree_html}}'] = self._render_causal_tree()

        # 11. HERRAMIENTA CUANTITATIVA TAA
        replacements['{{quant_tool_html}}'] = self._render_quant_tool()

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


    def _render_quant_tool(self) -> str:
        """Render the Herramienta Cuantitativa TAA section."""
        try:
            taa_data = self.market_data.get('taa', {}) if self.market_data else {}
            if not taa_data or 'error' in taa_data:
                return ''

            from taa_report_section import render_quant_tool_section

            # Try to extract council views for concordance
            council_views = {}
            try:
                from council_parser import CouncilParser
                parser = CouncilParser(self.council_result)
                equity_views = parser.get_block('EQUITY_VIEWS') or ''
                fi_views = parser.get_block('FI_POSITIONING') or ''
                # Map council views to asset class format for concordance
                for line in (equity_views + '\n' + fi_views).split('\n'):
                    line_lower = line.lower().strip()
                    if 'usa' in line_lower or 'us equity' in line_lower or 's&p' in line_lower:
                        if 'ow' in line_lower or 'sobrepon' in line_lower:
                            council_views['US Equity'] = {'direction': 'OW'}
                        elif 'uw' in line_lower or 'subpon' in line_lower:
                            council_views['US Equity'] = {'direction': 'UW'}
                        elif 'neutral' in line_lower:
                            council_views['US Equity'] = {'direction': 'N'}
                    if 'europa' in line_lower or 'eafe' in line_lower or 'internacional' in line_lower:
                        if 'ow' in line_lower or 'sobrepon' in line_lower:
                            council_views['Intl Equity'] = {'direction': 'OW'}
                        elif 'uw' in line_lower or 'subpon' in line_lower:
                            council_views['Intl Equity'] = {'direction': 'UW'}
                        elif 'neutral' in line_lower:
                            council_views['Intl Equity'] = {'direction': 'N'}
                    if 'renta fija' in line_lower or 'duration' in line_lower or 'fixed' in line_lower:
                        if 'ow' in line_lower or 'sobrepon' in line_lower or 'larga' in line_lower:
                            council_views['Fixed Income'] = {'direction': 'OW'}
                        elif 'uw' in line_lower or 'subpon' in line_lower or 'corta' in line_lower:
                            council_views['Fixed Income'] = {'direction': 'UW'}
                        elif 'neutral' in line_lower:
                            council_views['Fixed Income'] = {'direction': 'N'}
            except Exception:
                pass

            return render_quant_tool_section(taa_data, council_views=council_views or None)

        except Exception as e:
            if self.verbose:
                print(f"  [WARN] TAA section render failed: {e}")
            return ''


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

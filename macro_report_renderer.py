# -*- coding: utf-8 -*-
"""
Greybark Research - Macro Report Renderer
==========================================

Renderiza el reporte Macro combinando:
- Contenido narrativo (MacroContentGenerator)
- Template HTML profesional estilo GS/Itau
- Datos cuantitativos

Este reporte es de analisis económico puro - NO incluye recomendaciones de inversion.
Para el reporte de Asset Allocation con OW/UW, ver asset_allocation_renderer.py
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, Undefined


def _md_to_html_inline(text: str) -> str:
    """Convert markdown bold/italic to HTML inline, preserving <style> blocks."""
    if not text or not isinstance(text, str):
        return text or ''
    # Protect <style> blocks from markdown conversion
    styles = []
    def _save_style(m):
        styles.append(m.group(0))
        return f'__STYLE_BLOCK_{len(styles)-1}__'
    text = re.sub(r'<style[^>]*>.*?</style>', _save_style, text, flags=re.DOTALL)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Restore <style> blocks
    for i, style in enumerate(styles):
        text = text.replace(f'__STYLE_BLOCK_{i}__', style)
    return text

sys.path.insert(0, str(Path(__file__).parent))

from macro_content_generator import MacroContentGenerator
from chart_generator import MacroChartsGenerator
from chart_data_provider import ChartDataProvider
from table_builder import (
    build_indicator_rows, build_forecast_rows, build_calendar_rows,
    build_commodity_rows, fmt_bold, fmt_small, fmt_change, Badge, Trend
)


class MacroReportRenderer:
    """Renderizador del Reporte Macro profesional."""

    def __init__(self, council_result: Dict = None, forecast_data: Dict = None,
                 verbose: bool = True, branding: dict = None, quant_data: Dict = None):
        self.council_result = council_result or {}
        self.forecast_data = forecast_data
        self.quant_data = quant_data or {}
        self.verbose = verbose
        self.branding = branding or {}
        self.template_path = Path(__file__).parent / "templates" / "macro_report_professional.html"
        self.template_name = "macro_report_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            undefined=Undefined,
            autoescape=False,
        )

        # Load Bloomberg data (shared by content generator and chart provider)
        self._bloomberg = None
        try:
            from bloomberg_reader import BloombergData
            bbg = BloombergData()
            if bbg.available:
                self._bloomberg = bbg
        except Exception:
            pass

        # Initialize ChartDataProvider for real data (with Bloomberg for PMI/trade)
        try:
            self._data_provider = ChartDataProvider(lookback_months=120)
        except Exception:
            self._data_provider = None

        # Inject spot values from quant_data so chart annotations match text
        if self._data_provider and self.quant_data:
            spot = {}
            risk = self.quant_data.get('risk', {})
            if isinstance(risk, dict):
                vix_d = risk.get('vix', {})
                if isinstance(vix_d, dict):
                    spot['vix'] = vix_d.get('current')
            chile = self.quant_data.get('chile', {})
            if isinstance(chile, dict):
                spot['tpm'] = chile.get('tpm')
                spot['copper'] = chile.get('copper_price')
            inflation = self.quant_data.get('inflation', {})
            if isinstance(inflation, dict):
                spot['breakeven_5y'] = inflation.get('breakeven_5y')
                spot['breakeven_10y'] = inflation.get('breakeven_10y')
            rates = self.quant_data.get('rates', {})
            if isinstance(rates, dict):
                spot['ust_10y'] = rates.get('terminal_rate')
            self._data_provider._injected_spot = {k: v for k, v in spot.items() if v is not None}

        # Inicializar generador de contenido (with data provider for real Chile data)
        self.content_generator = MacroContentGenerator(
            self.council_result, quant_data=self.quant_data,
            data_provider=self._data_provider,
            forecast_data=self.forecast_data,
            company_name=self.branding.get('company_name', ''))

        # Inject Bloomberg data into content generator
        if self._bloomberg:
            self.content_generator.bloomberg = self._bloomberg

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
        self._print("GREYBARK RESEARCH - MACRO REPORT RENDERER")
        self._print("="*60)

        # 1. Generar contenido
        self._print("[1/3] Generando contenido macro...")
        content = self.content_generator.generate_all_content()
        self.last_content = content

        # 2. Renderizar con Jinja2
        self._print("[2/3] Cargando template profesional...")
        template = self._jinja_env.get_template(self.template_name)

        # 3. Renderizar
        self._print("[3/3] Renderizando reporte...")
        html = self._render_template(template, content)

        # 4. Guardar
        if output_filename is None:
            output_filename = f"macro_report_{datetime.now().strftime('%Y-%m-%d')}.html"

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

        self._print(f"\n[OK] Reporte Macro generado: {output_path}")
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
                    f'data-report="macro" data-generated="{datetime.now().isoformat()}">'
                    f'\n{provenance_json}\n</div>\n'
                )
                # Insert before </body> if present, else append
                if '</body>' in html:
                    html = html.replace('</body>', div + '</body>')
                else:
                    html += div
                clear_provenance_records()
        except Exception:
            pass
        return html

    def _render_template(self, template, content: Dict) -> str:
        """Renderiza el template con el contenido usando Jinja2."""

        now = datetime.now()
        replacements = {
            '{{fecha_reporte}}': f"{now.day} {self._get_spanish_month(now.month)} {now.year}",
        }

        # 1. RESUMEN EJECUTIVO
        resumen = content['resumen_ejecutivo']
        replacements['{{parrafo_intro}}'] = resumen['parrafo_intro']

        # Stance spectrum - highlight active postura
        postura = resumen.get('postura', {'view': 'NEUTRAL'})
        active_view = postura['view'].upper()
        for stance in ['cauteloso', 'neutral', 'constructivo', 'agresivo']:
            replacements[f'{{{{spectrum_active_{stance}}}}}'] = 'spectrum-active' if stance.upper() == active_view else ''

        # Key takeaways
        kt_html = ''.join([f'<li>{kt}</li>' for kt in resumen['key_takeaways']])
        replacements['{{key_takeaways_html}}'] = kt_html

        # Forecasts tables
        forecasts = resumen['forecasts_table']

        # GDP, Inflation, Rates — all use the same forecast row pattern
        replacements['{{gdp_forecasts_rows}}'] = build_forecast_rows(
            forecasts['gdp_growth'], vs_class_fn=self._get_vs_class)
        replacements['{{inflation_forecasts_rows}}'] = build_forecast_rows(
            forecasts['inflation_core'], vs_class_fn=self._get_vs_class)
        replacements['{{rates_forecasts_rows}}'] = build_forecast_rows(
            forecasts['policy_rates'], vs_class_fn=self._get_vs_class)

        # Econometric Projections Table
        replacements['{{econometric_projections_table}}'] = self._generate_econometric_projections_table()

        # Probability-Weighted Forecasts
        ponderado = content['pronóstico_ponderado']
        replacements['{{weighted_metodologia}}'] = ponderado.get('metodologia', 'N/D')

        weighted_rows = ''
        for esc in ponderado['escenarios']:
            weighted_rows += f'''<tr>
                <td>{esc['nombre']}</td>
                <td style="text-align:center">{esc['probabilidad']}</td>
                <td style="text-align:center">{esc['gdp_us']}</td>
                <td style="text-align:center">{esc.get('gdp_world', 'N/D')}</td>
                <td style="text-align:center">{esc['sp500']}</td>
            </tr>'''
        replacements['{{weighted_scenarios_rows}}'] = weighted_rows

        replacements['{{weighted_gdp_us}}'] = ponderado['weighted_forecasts'].get('gdp_us', 'N/D')
        replacements['{{weighted_gdp_world}}'] = ponderado['weighted_forecasts'].get('gdp_world', 'N/D')
        replacements['{{weighted_sp500}}'] = ponderado['weighted_forecasts'].get('sp500', 'N/D')
        replacements['{{weighted_implicancia}}'] = ponderado['implicancia']

        # Vs Previous Forecast
        vs_prev = content['vs_pronóstico_anterior']
        replacements['{{previous_fecha}}'] = vs_prev['fecha_anterior']

        vs_prev_rows = ''
        for cambio in vs_prev['cambios']:
            vs_prev_rows += f'''<tr>
                <td>{cambio['variable']}</td>
                <td style="text-align:center">{cambio['anterior']}</td>
                <td style="text-align:center">{cambio['actual']}</td>
                <td style="text-align:center"><strong>{cambio['cambio']}</strong></td>
                <td style="font-size: 8pt;">{cambio['razon']}</td>
            </tr>'''
        replacements['{{vs_previous_rows}}'] = vs_prev_rows

        track = vs_prev['track_record']
        replacements['{{track_record_aciertos}}'] = ''.join(
            f'<li>{a}</li>' for a in track['aciertos']
        )
        replacements['{{track_record_errores}}'] = ''.join(
            f'<li>{e}</li>' for e in track['errores']
        )

        # 2. ESTADOS UNIDOS
        usa = content['estados_unidos']

        # Growth
        growth = usa['crecimiento']
        replacements['{{usa_growth_narrative}}'] = growth['narrativa']

        # Labor
        labor = usa['mercado_laboral']
        replacements['{{usa_labor_narrative}}'] = labor['narrativa']

        replacements['{{usa_labor_rows}}'] = build_indicator_rows(labor['datos'])

        # JOLTS
        replacements['{{usa_jolts_narrative}}'] = labor.get('narrativa_jolts', '')
        replacements['{{usa_jolts_rows}}'] = build_indicator_rows(labor.get('jolts', []))

        # Wages
        replacements['{{usa_wages_narrative}}'] = labor.get('narrativa_salarios', '')
        replacements['{{usa_wages_rows}}'] = build_indicator_rows(labor.get('salarios', []))

        # Inflation
        inflation = usa['inflación']
        replacements['{{usa_inflation_narrative}}'] = inflation['narrativa']

        inf_rows = ''
        for d in inflation['datos']:
            inf_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d['mom']}</td>
            </tr>'''
        replacements['{{usa_inflation_rows}}'] = inf_rows

        comp_rows = ''
        for c in inflation['componentes']:
            trend_class = self._get_trend_class(c['tendencia'])
            comp_rows += f'''<tr>
                <td>{c['componente']}</td>
                <td>{c['valor']}</td>
                <td class="{trend_class}">{c['tendencia']}</td>
            </tr>'''
        replacements['{{usa_inflation_components}}'] = comp_rows

        # Fed
        fed = usa['política_monetaria']
        replacements['{{fed_narrative}}'] = fed['narrativa']
        replacements['{{fed_actual}}'] = fed['tasas']['actual']
        replacements['{{fed_neutral}}'] = fed['tasas']['neutral_estimada']
        replacements['{{fed_proyección}}'] = fed['tasas']['proyección_2026']

        fed_meetings = ''
        for m in fed['proximas_reuniones']:
            fed_meetings += f'''<tr>
                <td>{m['fecha']}</td>
                <td>{m['expectativa']}</td>
                <td>{m['probabilidad']}</td>
            </tr>'''
        replacements['{{fed_meetings_rows}}'] = fed_meetings

        # Fiscal
        fiscal = usa['política_fiscal']
        replacements['{{usa_fiscal_narrative}}'] = fiscal['narrativa']

        fiscal_rows = ''
        for d in fiscal['datos']:
            fiscal_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d.get('anterior', d.get('comentario', ''))}</td>
            </tr>'''
        replacements['{{usa_fiscal_rows}}'] = fiscal_rows

        # 3. EUROPA
        europe = content['europa']

        # Growth
        eu_growth = europe['crecimiento']
        replacements['{{europe_growth_narrative}}'] = eu_growth['narrativa']

        eu_gdp_rows = ''
        for p in eu_growth['por_pais']:
            eu_gdp_rows += f'''<tr>
                <td>{p['pais']}</td>
                <td>{p['gdp_2025']}</td>
                <td><strong>{p['gdp_2026f']}</strong></td>
                <td>{p['consenso']}</td>
            </tr>'''
        replacements['{{europe_gdp_rows}}'] = eu_gdp_rows

        # Inflation
        eu_inf = europe['inflación']
        replacements['{{europe_inflation_narrative}}'] = eu_inf['narrativa']

        eu_inf_rows = ''
        for d in eu_inf['datos']:
            eu_inf_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d['anterior']}</td>
            </tr>'''
        replacements['{{europe_inflation_rows}}'] = eu_inf_rows

        # ECB
        ecb = europe['política_monetaria']
        replacements['{{ecb_narrative}}'] = ecb['narrativa']
        replacements['{{ecb_actual}}'] = ecb['tasas']['deposito_actual']
        replacements['{{ecb_proyección}}'] = ecb['tasas']['proyección_2026']
        replacements['{{ecb_neutral}}'] = ecb['tasas']['neutral_estimada']

        # 4. CHINA
        china = content['china']

        # Growth
        ch_growth = china['crecimiento']
        replacements['{{china_growth_narrative}}'] = ch_growth['narrativa']

        ch_growth_rows = ''
        for d in ch_growth['datos']:
            ch_growth_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d.get('target', d.get('anterior', ''))}</td>
            </tr>'''
        replacements['{{china_growth_rows}}'] = ch_growth_rows

        # Property
        property = china['sector_inmobiliario']
        replacements['{{china_property_narrative}}'] = property['narrativa']

        property_rows = ''
        for d in property['datos']:
            property_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d['anterior']}</td>
            </tr>'''
        replacements['{{china_property_rows}}'] = property_rows

        # Credit
        replacements['{{china_credit_narrative}}'] = china['impulso_crediticio']['narrativa']

        # Trade
        replacements['{{china_trade_narrative}}'] = china['comercio_exterior']['narrativa']

        # 5. CHILE Y LATAM
        chile = content['chile_latam']

        # Chile Growth
        ch_growth = chile['chile_crecimiento']
        replacements['{{chile_growth_narrative}}'] = ch_growth['narrativa']

        replacements['{{chile_growth_rows}}'] = build_indicator_rows(ch_growth['datos'])

        # Chile Inflation
        ch_inf = chile['chile_inflación']
        replacements['{{chile_inflation_narrative}}'] = ch_inf['narrativa']

        chile_inf_rows = ''
        for d in ch_inf['datos']:
            chile_inf_rows += f'''<tr>
                <td>{d['indicador']}</td>
                <td>{d['valor']}</td>
                <td>{d['anterior']}</td>
            </tr>'''
        replacements['{{chile_inflation_rows}}'] = chile_inf_rows

        # BCCh
        bcch = chile['chile_política_monetaria']
        replacements['{{bcch_narrative}}'] = bcch['narrativa']
        replacements['{{tpm_actual}}'] = bcch['tasas']['tpm_actual']
        replacements['{{tpm_neutral}}'] = bcch['tasas']['tpm_neutral']
        replacements['{{tpm_proyección}}'] = bcch['tasas']['proyección_2026']

        # Commodities
        comm = chile['commodities_relevantes']
        comm_rows = ''
        for c in comm['commodities']:
            comm_rows += f'''<tr>
                <td><strong>{c['nombre']}</strong></td>
                <td>{c['precio_actual']}</td>
                <td>{c['cambio']}</td>
                <td>{c['outlook']}</td>
                <td style="font-size: 8pt;">{c['drivers']}</td>
            </tr>'''
        replacements['{{commodities_rows}}'] = comm_rows

        # Commodities Performance Table (real BCCh data)
        comm_perf_table = ''
        if self._data_provider:
            try:
                comm_data = self._data_provider.get_commodities_table()
                if comm_data:
                    from table_builder import commodity_table
                    comm_perf_table = commodity_table(comm_data)
                    comm_perf_table += '\n<p style="font-size:8pt;color:#a0aec0;text-align:right;margin-top:2px;">Fuente: BCCh API (datos reales)</p>'
            except Exception:
                pass
        replacements['{{commodities_performance_table}}'] = comm_perf_table

        # LatAm
        latam = chile['latam_context']
        latam_rows = ''
        for p in latam['paises']:
            latam_rows += f'''<tr>
                <td><strong>{p['pais']}</strong></td>
                <td>{p['gdp']}</td>
                <td>{p['inflación']}</td>
                <td>{p['tasa']}</td>
                <td style="font-size: 8pt;">{p['riesgo_principal']}</td>
            </tr>'''
        replacements['{{latam_rows}}'] = latam_rows

        # 6. TEMAS MACRO
        temas = content['temas_macro']

        themes_html = ''
        for t in temas['temas']:
            themes_html += f'''
            <div class="region-card">
                <div class="region-card-header">{t.get('titulo', 'N/D')}</div>
                <div class="region-card-body">
                    <p>{t.get('descripcion', '')}</p>
                </div>
            </div>'''
        replacements['{{macro_themes_html}}'] = themes_html

        # Calendar
        replacements['{{calendar_rows}}'] = build_calendar_rows(temas['calendario_eventos'])

        # 7. ESCENARIOS Y RIESGOS
        esc = content['escenarios_riesgos']

        # Scenarios — handle both old dict format and new list format
        scenarios_raw = esc.get('escenarios', {})
        scenarios_html = ''
        if isinstance(scenarios_raw, dict):
            scenario_list = scenarios_raw.get('escenarios', [])
            if isinstance(scenario_list, dict):
                # Old format: dict of dicts
                for key, s in scenario_list.items():
                    scenarios_html += f'''
                    <div class="scenario-card {key}">
                        <div class="scenario-header">
                            <span class="scenario-name">{s.get("nombre", key)}</span>
                            <span class="scenario-prob">{s.get("probabilidad", "N/D")}%</span>
                        </div>
                        <div class="scenario-desc">{s.get("descripcion", "")}</div>
                    </div>'''
            else:
                # New format: list of dicts
                for s in scenario_list:
                    nombre = s.get('nombre', 'N/D')
                    prob = s.get('probabilidad', 'N/D')
                    desc = s.get('descripcion', '')
                    scenarios_html += f'''
                    <div class="scenario-card">
                        <div class="scenario-header">
                            <span class="scenario-name">{nombre}</span>
                            <span class="scenario-prob">{prob}</span>
                        </div>
                        <div class="scenario-desc">{desc}</div>
                    </div>'''
            narrativa = scenarios_raw.get('narrativa', '')
            if narrativa:
                scenarios_html += f'<p style="margin-top:12px;color:#4a5568;">{narrativa}</p>'
        replacements['{{scenarios_html}}'] = scenarios_html

        # Risks — handle both old list format and new dict format
        risks_raw = esc.get('top_risks', {})
        risks_html = ''
        if isinstance(risks_raw, dict):
            risk_list = risks_raw.get('riesgos', [])
            narrativa = risks_raw.get('narrativa', '')
        elif isinstance(risks_raw, list):
            risk_list = risks_raw
            narrativa = ''
        else:
            risk_list = []
            narrativa = ''
        for r in risk_list:
            risks_html += f'''
            <div class="risk-card">
                <div class="risk-header">
                    <span class="risk-name">{r.get("nombre", "N/D")}</span>
                    <span class="risk-metrics">
                        <span>Prob: <strong>{r.get("probabilidad", "N/D")}</strong></span>
                        <span>Impacto: <strong>{r.get("impacto", "N/D")}</strong></span>
                    </span>
                </div>
                <p style="margin: 10px 0; color: #4a5568;">{r.get("descripcion", "")}</p>
                {'<p style="font-size: 9pt; color: #718096;"><strong>Horizonte:</strong> ' + r.get("horizonte", "") + '</p>' if r.get("horizonte") else ''}
                {'<p style="font-size: 9pt; color: #718096;"><strong>Señal temprana:</strong> ' + monitoreo_val + '</p>' if (monitoreo_val := r.get("senal_temprana", r.get("monitoreo", ""))) and monitoreo_val != r.get("nombre", "") else ''}
            </div>'''
        if narrativa and not risk_list:
            risks_html = f'<p style="color:#4a5568;">{narrativa}</p>'
        replacements['{{risks_html}}'] = risks_html

        # 8. CONCLUSIONES
        concl = content.get('conclusiones', {})
        replacements['{{conclusiones_intro}}'] = concl.get('intro', '')
        replacements['{{conclusiones_posicionamiento}}'] = concl.get('posicionamiento_resumen', '')
        replacements['{{conclusiones_proximo}}'] = concl.get('proximo_reporte', '')

        # Build vistas HTML
        vistas_html = ''
        for v in concl.get('vistas', []):
            vs_color = '#276749' if 'alineado' in v.get('vs_consenso', '').lower() else (
                '#c53030' if 'encima' in v.get('vs_consenso', '').lower() or 'hawkish' in v.get('vs_consenso', '').lower() or 'mayor' in v.get('vs_consenso', '').lower()
                else '#744210'
            )
            vistas_html += f'''
            <div style="margin-bottom: 18px; padding: 12px 15px; border: 1px solid #e2e8f0; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4 style="color: var(--primary-blue); margin: 0; font-size: 11pt;">{v['tema']}</h4>
                    <span style="background: {vs_color}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 8pt; font-weight: 600;">{v['vs_consenso']}</span>
                </div>
                <p style="margin-bottom: 8px;">{v['vista_grb']}</p>
                <p style="font-size: 9pt; color: #718096; margin: 0;"><strong>vs Consenso:</strong> {v['vs_detalle']}</p>
            </div>'''
        replacements['{{conclusiones_vistas_html}}'] = vistas_html

        # 9. CHARTS
        chart_map = {
                '{{chart_inflation_evolution}}': 'inflation_evolution',
                '{{chart_fed_vs_ecb_bcch}}': 'fed_vs_ecb_bcch',
                '{{chart_labor_unemployment}}': 'labor_unemployment',
                '{{chart_labor_nfp}}': 'labor_nfp',
                '{{chart_labor_jolts}}': 'labor_jolts',
                '{{chart_labor_wages}}': 'labor_wages',
                '{{chart_pmi_global}}': 'pmi_global',
                '{{chart_commodity_prices}}': 'commodity_prices',
                '{{chart_energy_food}}': 'energy_food',
                '{{chart_yield_curve}}': 'yield_curve',
                '{{chart_yield_spreads}}': 'yield_spreads',
                '{{chart_inflation_heatmap}}': 'inflation_heatmap',
                '{{chart_inflation_components_ts}}': 'inflation_components_ts',
                # commodities_performance replaced by HTML table
                '{{chart_risk_matrix}}': 'risk_matrix',
                '{{chart_usa_leading_indicators}}': 'usa_leading_indicators',
                '{{chart_europe_dashboard}}': 'europe_dashboard',
                '{{chart_europe_pmi}}': 'europe_pmi',
                '{{chart_global_equities}}': 'global_equities',
                '{{chart_china_dashboard}}': 'china_dashboard',
                '{{chart_china_trade}}': 'china_trade',
                '{{chart_chile_dashboard}}': 'chile_dashboard',
                '{{chart_chile_inflation_components}}': 'chile_inflation_components',
                '{{chart_chile_external}}': 'chile_external',
                '{{chart_latam_rates}}': 'latam_rates',
                '{{chart_epu_geopolitics}}': 'epu_geopolitics',
            }
        try:
            # Reuse the same data provider instance (already created in __init__)
            provider = self._data_provider
            if provider:
                self._print("  [OK] ChartDataProvider activo (datos reales BCCh)")
            else:
                self._print("  [INFO] Sin ChartDataProvider — charts usaran fallback")

            macro_charts = MacroChartsGenerator(data_provider=provider, forecast_data=self.forecast_data, branding=self.branding, bloomberg=self._bloomberg)
            all_charts = macro_charts.generate_all_charts(content)
            for placeholder, chart_id in chart_map.items():
                replacements[placeholder] = all_charts.get(chart_id, '')
            self._print(f"  [OK] {len(all_charts)} charts generados")

            # Log chart data source summary
            summary = macro_charts.get_chart_source_summary()
            self._print(f"  [CHARTS] {summary['real_api']} real | {summary['partial_real']} partial | "
                        f"{summary['fallback_estimated']} fallback | {summary['content_generated']} generated "
                        f"({summary['real_pct']}% real)")
            if summary['details']['fallback']:
                self._print(f"  [CHARTS] Fallback: {', '.join(summary['details']['fallback'])}")
        except Exception as e:
            self._print(f"  [WARN] Charts no generados: {e}")
            for placeholder in chart_map:
                replacements[placeholder] = ''

        # Convert {{key}} → key for Jinja2 context
        context = {}
        for key, value in replacements.items():
            clean = key.replace('{{', '').replace('}}', '')
            context[clean] = str(value)

        # Inject branding (templates use |default() for fallback)
        if self.branding:
            context.update(self.branding)

        return template.render(**context)

    def _get_vs_class(self, vs: str) -> str:
        """Retorna clase CSS segun cambio vs anterior."""
        if vs.startswith('+'):
            return 'vs-positive'
        elif vs.startswith('-'):
            return 'vs-negative'
        return 'vs-neutral'

    def _get_trend_class(self, trend: str) -> str:
        """Retorna clase CSS segun tendencia."""
        trend_lower = trend.lower()
        if any(word in trend_lower for word in ['recuperando', 'solido', 'expansión', 'firme']):
            return 'trend-up'
        elif any(word in trend_lower for word in ['debil', 'contracción', 'caida', 'deflacion']):
            return 'trend-down'
        return 'trend-neutral'

    def _generate_econometric_projections_table(self) -> str:
        """Genera tabla HTML de proyecciones cuantitativas blended desde forecast_data."""
        fd = self.forecast_data or {}
        if not fd:
            return '<p style="color:#718096; font-style:italic;">Proyecciones no disponibles — ejecutar forecast engine.</p>'

        def _fmt(val, decimals=1):
            if val is None:
                return 'N/D'
            try:
                return f"{float(val):.{decimals}f}%"
            except (ValueError, TypeError):
                return 'N/D'

        def _trend_arrow(direction):
            if not direction:
                return ''
            d = str(direction).upper()
            if d in ('RISING', 'HIKING'):
                return ' <span style="color:#c53030;">&#9650;</span>'
            elif d in ('FALLING', 'EASING'):
                return ' <span style="color:#276749;">&#9660;</span>'
            return ' <span style="color:#744210;">&#9654;</span>'

        def _range_fmt(rng):
            if not rng or not isinstance(rng, list) or len(rng) < 2:
                return 'N/D'
            return f"{rng[0]:.1f} – {rng[1]:.1f}"

        # IMF consensus data
        imf = fd.get('imf_consensus', {})
        imf_gdp = imf.get('gdp', {}) if isinstance(imf, dict) and 'error' not in imf else {}
        imf_infl = imf.get('inflation', {}) if isinstance(imf, dict) and 'error' not in imf else {}

        rows = []

        # --- GDP ---
        rows.append(('header', 'Crecimiento (PIB)', None, None, None, None, None, None))
        gdp = fd.get('gdp_forecasts', {})
        for label, key in [('USA', 'usa'), ('Eurozona', 'eurozone'), ('China', 'china'), ('Chile', 'chile')]:
            g = gdp.get(key, {})
            if isinstance(g, dict) and 'error' not in g:
                c_imf = imf_gdp.get(key)
                # Compute range from forecast ± 0.5pp if not available
                rng = g.get('range')
                if not rng:
                    fc = g.get('forecast_12m')
                    if fc is not None:
                        rng = [round(fc - 0.5, 1), round(fc + 0.5, 1)]
                rows.append(('data', label,
                             _fmt(g.get('current')),
                             _fmt(g.get('forecast_12m')),
                             _fmt(c_imf) if c_imf is not None else '—',
                             _range_fmt(rng),
                             _trend_arrow(g.get('lei_signal', g.get('trend', ''))),
                             g.get('source', '')))

        # --- Inflation ---
        rows.append(('header', 'Inflación (IPC)', None, None, None, None, None, None))
        infl = fd.get('inflation_forecasts', {})
        for label, key in [('USA', 'usa'), ('Eurozona', 'eurozone'), ('Chile', 'chile')]:
            i = infl.get(key, {})
            if isinstance(i, dict) and 'error' not in i:
                c_imf = imf_infl.get(key)
                rows.append(('data', label,
                             _fmt(i.get('current')),
                             _fmt(i.get('forecast_12m')),
                             _fmt(c_imf) if c_imf is not None else '—',
                             _range_fmt(i.get('range')),
                             _trend_arrow(i.get('trend', '')),
                             ''))

        # --- Policy Rates ---
        rows.append(('header', 'Tasas de Política', None, None, None, None, None, None))
        rates = fd.get('rate_forecasts', {})
        for label, key in [('Fed Funds', 'fed_funds'), ('TPM Chile', 'tpm_chile'), ('ECB Depo', 'ecb')]:
            r = rates.get(key, {})
            if isinstance(r, dict):
                cuts = r.get('cuts_expected', 0)
                hikes = r.get('hikes_expected', 0)
                moves = ''
                if cuts:
                    moves = f'{cuts} corte{"s" if cuts > 1 else ""}'
                elif hikes:
                    moves = f'{hikes} alza{"s" if hikes > 1 else ""}'
                rows.append(('data', label,
                             _fmt(r.get('current'), 2),
                             _fmt(r.get('forecast_12m'), 2),
                             '—',
                             f"Terminal: {_fmt(r.get('terminal'), 2)}",
                             _trend_arrow(r.get('direction', '')),
                             moves))

        # Build HTML table
        html = '''<table class="forecasts-table" style="width:100%; margin-top:10px;">
            <thead>
                <tr>
                    <th style="text-align:left;">Variable</th>
                    <th style="text-align:center;">Actual</th>
                    <th style="text-align:center;">12M Fwd</th>
                    <th style="text-align:center;">Consenso IMF</th>
                    <th style="text-align:center;">Rango / Terminal</th>
                    <th style="text-align:center;">Tend.</th>
                    <th style="text-align:center;">Nota</th>
                </tr>
            </thead>
            <tbody>'''

        for row in rows:
            if row[0] == 'header':
                html += f'''
                <tr class="region-header">
                    <td colspan="7"><strong>{row[1]}</strong></td>
                </tr>'''
            else:
                html += f'''
                <tr>
                    <td>{row[1]}</td>
                    <td style="text-align:center;">{row[2]}</td>
                    <td style="text-align:center;"><strong>{row[3]}</strong></td>
                    <td style="text-align:center; color:#718096;">{row[4]}</td>
                    <td style="text-align:center; font-size:8pt; color:#4a4a4a;">{row[5]}</td>
                    <td style="text-align:center;">{row[6]}</td>
                    <td style="text-align:center; font-size:8pt; color:#718096;">{row[7]}</td>
                </tr>'''

        html += '''
            </tbody>
        </table>'''

        return html


def main():
    """Genera el reporte Macro profesional."""
    import argparse

    parser = argparse.ArgumentParser(description='Generador Reporte Macro Profesional')
    parser.add_argument('--council-file', help='Archivo JSON con resultado del council')
    parser.add_argument('--forecast-data', help='Archivo JSON con forecast data')
    parser.add_argument('--output', '-o', help='Nombre archivo de salida')
    args = parser.parse_args()

    # Cargar council result si existe
    council_result = None
    council_file = args.council_file

    if not council_file:
        # Buscar el mas reciente
        output_dir = Path(__file__).parent / "output" / "council"
        council_files = list(output_dir.glob("council_result_*.json"))
        if council_files:
            council_file = str(sorted(council_files)[-1])

    if council_file:
        print(f"[INFO] Cargando council: {council_file}")
        with open(council_file, 'r', encoding='utf-8') as f:
            council_result = json.load(f)

    # Cargar forecast data si existe
    forecast_data = None
    forecast_file = args.forecast_data

    if not forecast_file:
        fc_dir = Path(__file__).parent / "output" / "forecasts"
        fc_files = list(fc_dir.glob("forecast_*.json"))
        if fc_files:
            forecast_file = str(sorted(fc_files)[-1])

    if forecast_file:
        print(f"[INFO] Cargando forecasts: {forecast_file}")
        with open(forecast_file, 'r', encoding='utf-8') as f:
            forecast_data = json.load(f)

    renderer = MacroReportRenderer(council_result=council_result, forecast_data=forecast_data, verbose=True)
    output_path = renderer.render(output_filename=args.output)

    # Abrir en navegador
    import subprocess
    subprocess.run(['start', '', output_path], shell=True)


if __name__ == "__main__":
    main()

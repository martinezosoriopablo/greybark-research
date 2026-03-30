# -*- coding: utf-8 -*-
"""
Greybark Research - Macro Content Generator
=============================================

Genera el CONTENIDO narrativo para el reporte Macro mensual.
Sigue la estructura de Goldman Sachs / Itau:
- Forecasts cuantitativos vs consenso
- GDP growth y drivers por region
- Inflación (CPI, Core, PCE, wages)
- Mercado laboral (NFP, desempleo, participación)
- Política monetaria (Fed, BCE, BCCh)
- Política fiscal
- Riesgos macro y escenarios

IMPORTANTE: Este reporte NO incluye recomendaciones de inversion (OW/UW).
Para recomendaciones de asset allocation, ver asset_allocation_content_generator.py
"""

import json
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Setup paths for BCCh client
sys.path.insert(0, str(Path(__file__).parent))


class MacroContentGenerator:
    """Generador de contenido narrativo para Reporte Macro."""

    def __init__(self, council_result: Dict = None, quant_data: Dict = None,
                 data_provider=None, forecast_data: Dict = None,
                 company_name: str = ""):
        self.council = council_result or {}
        self.quant = quant_data or {}
        self.data = data_provider  # ChartDataProvider for real BCCh data
        self.forecast = forecast_data or {}
        self.company_name = company_name
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)
        self.year = self.date.year
        self._chile_latest = None  # Lazy-loaded real data cache
        self._usa_latest = None    # Lazy-loaded USA real data cache
        self._europe_latest = None  # Lazy-loaded Europe real data cache
        self._china_latest = None   # Lazy-loaded China real data cache
        self.bloomberg = None  # Injected externally
        self._parser = None  # Lazy council parser

    @staticmethod
    def _sf(val):
        """Safe float: convert pd.Series, numpy, dict to plain float. Returns None if not numeric."""
        if val is None:
            return None
        try:
            import pandas as pd
            if isinstance(val, pd.Series):
                return float(val.iloc[-1]) if not val.empty else None
        except (ImportError, TypeError, IndexError):
            pass
        if isinstance(val, dict):
            val = val.get('value', val.get('current', val.get('latest')))
        try:
            import numpy as np
            if isinstance(val, (np.integer, np.floating)):
                return float(val)
        except (ImportError, TypeError):
            pass
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @property
    def parser(self):
        """Lazy-init council parser."""
        if self._parser is None:
            try:
                from council_parser import CouncilParser
                self._parser = CouncilParser(self.council)
            except Exception:
                from council_parser import CouncilParser
                self._parser = CouncilParser({})
        return self._parser

    def _get_spanish_month(self, month: int) -> str:
        """Retorna nombre del mes en espanol."""
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return meses.get(month, 'Mes')

    def _extract_from_panel(self, agent: str) -> str:
        """Extrae contenido de un agente del panel."""
        panel = self.council.get('panel_outputs', {})
        return panel.get(agent, '')

    def _get_chile_latest(self) -> Dict[str, Optional[float]]:
        """Obtiene últimos datos reales de Chile desde BCCh API (cached)."""
        if self._chile_latest is not None:
            return self._chile_latest
        if self.data:
            try:
                self._chile_latest = self.data.get_chile_latest()
                return self._chile_latest
            except Exception:
                pass
        self._chile_latest = {}
        return self._chile_latest

    def _get_usa_latest(self) -> Dict[str, Optional[float]]:
        """Obtiene últimos datos reales de USA desde FRED API (cached)."""
        if self._usa_latest is not None:
            return self._usa_latest
        if self.data:
            try:
                self._usa_latest = self.data.get_usa_latest()
                return self._usa_latest
            except Exception:
                pass
        self._usa_latest = {}
        return self._usa_latest

    def _get_europe_latest(self) -> Dict[str, Optional[float]]:
        """Obtiene últimos datos reales de Europa desde BCCh API (cached)."""
        if self._europe_latest is not None:
            return self._europe_latest
        if self.data:
            try:
                self._europe_latest = self.data.get_europe_latest()
                return self._europe_latest
            except Exception:
                pass
        self._europe_latest = {}
        return self._europe_latest

    def _get_china_latest(self) -> Dict[str, Optional[float]]:
        """Obtiene últimos datos reales de China desde BCCh API (cached)."""
        if self._china_latest is not None:
            return self._china_latest
        if self.data:
            try:
                self._china_latest = self.data.get_china_latest()
                return self._china_latest
            except Exception:
                pass
        self._china_latest = {}
        return self._china_latest

    def _q(self, *keys, default=None):
        """Navigate nested quant_data dict by key path."""
        d = self.quant
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

    def _fmt(self, val: Optional[float], suffix: str = '%', decimals: int = 1) -> str:
        """Formatea un valor numérico, retorna 'N/D' si None."""
        if val is None:
            return 'N/D'
        return f"{val:.{decimals}f}{suffix}"

    # =========================================================================
    # SECCION 1: RESUMEN EJECUTIVO Y FORECASTS
    # =========================================================================

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Genera resumen ejecutivo con tabla de forecasts principal."""

        return {
            'titulo': f"Perspectivas Macro - {self.month_name} {self.year}",
            'parrafo_intro': self._generate_macro_intro(),
            'postura': self._determine_macro_postura(),
            'key_takeaways': self._generate_key_takeaways(),
            'forecasts_table': self._generate_forecasts_table()
        }

    def _determine_macro_postura(self) -> Dict[str, str]:
        """Determina la postura macro del comité desde council output."""
        final = self.council.get('final_recommendation', '')
        cio = self.council.get('cio_synthesis', '')
        text = (final + ' ' + cio).lower()

        if not text.strip():
            return {'view': 'N/D'}

        import re as _re
        # AGRESIVO: solo si explícitamente dice "postura agresiva"
        if _re.search(r'postura\s+(agresiva|agresivo)', text) or 'fuerte risk-on' in text:
            view = 'AGRESIVO'
        elif 'defensiva moderada' in text or 'defensivo moderado' in text:
            view = 'CAUTELOSO'
        elif 'risk-off' in text or 'postura defensiva' in text:
            view = 'CAUTELOSO'
        elif 'recesi' in text and 'evita' not in text:
            view = 'CAUTELOSO'
        elif 'expansión tardía' in text or 'expansion tardia' in text:
            view = 'CONSTRUCTIVO'
        elif 'constructiv' in text and 'cauteloso' not in text:
            view = 'CONSTRUCTIVO'
        else:
            view = 'NEUTRAL'

        return {'view': view}

    def _generate_macro_intro(self) -> str:
        """Genera parrafo introductorio macro usando council output via Claude."""
        from narrative_engine import generate_narrative

        final_rec = self.council.get('final_recommendation', '')
        cio = self.council.get('cio_synthesis', '')
        panels = self.council.get('panel_outputs', {})
        macro_panel = panels.get('macro', '')
        geo_panel = panels.get('geo', '')

        council_context = f"FINAL REC:\n{final_rec}\n\nCIO:\n{cio}\n\nMACRO PANEL:\n{macro_panel[:2000]}\n\nGEO PANEL:\n{geo_panel[:1000]}"

        result = generate_narrative(
            section_name="macro_intro",
            prompt=(
                f"Escribe la introduccion ejecutiva del reporte macro de {self.month_name} {self.year}. "
                "3-4 parrafos cubriendo: (1) panorama macro global y regimen economico actual, "
                "(2) principales dinamicas de EE.UU. (crecimiento, inflacion, Fed), "
                "(3) principales riesgos geopoliticos y comerciales del mes, "
                "(4) sintesis de Europa, China y Chile. "
                "Usa los datos del council como base — NO inventes numeros. "
                "Separa parrafos con <br><br>. Maximo 400 palabras."
                "\n\nESTRUCTURA: Escribe un RESUMEN AUTOCONTENIDO que un gestor entienda sin leer el resto del reporte. Incluye: régimen macro actual + dato clave, postura general + horizonte, qué cambió vs período anterior, principal oportunidad + dato, principal riesgo + dato. Explica jerga técnica en primera mención (paréntesis)."
            ),
            council_context=council_context,
            company_name=self.company_name,
            max_tokens=1500,
        )
        if result:
            return result

        # Fallback minimal
        return (
            f"El escenario macro global de {self.month_name} {self.year} se caracteriza por "
            f"dinámicas complejas en crecimiento, inflación y política monetaria. "
            f"Este reporte detalla nuestro análisis por región y escenarios ponderados por probabilidad."
        )

    def _generate_key_takeaways(self) -> List[str]:
        """Genera key takeaways del mes via Claude, usando council output."""
        from narrative_engine import generate_narrative

        final_rec = self.council.get('final_recommendation', '')
        cio = self.council.get('cio_synthesis', '')

        if not (final_rec or cio):
            return ["N/D — key takeaways requieren council session."]

        council_context = f"FINAL REC:\n{final_rec[:2000]}\n\nCIO:\n{cio[:2000]}"

        result = generate_narrative(
            section_name="macro_takeaways",
            prompt=(
                f"Genera exactamente 5-6 key takeaways del reporte macro de {self.month_name} {self.year}. "
                "Cada takeaway debe tener formato: '<strong>Titulo Corto</strong>: Explicacion en 1-2 oraciones.' "
                "Cubrir: regimen economico, politica monetaria, geopolitica/comercio, tecnologia/IA (si relevante), "
                "Chile, y un riesgo clave. Usa SOLO datos que aparecen en el council. "
                "Devuelve cada takeaway separado por \\n (una linea por takeaway). NO uses bullets ni numeracion."
                "\n\nPara cada takeaway, sigue la cadena: DATO → INTERPRETACION → IMPLICACION para portafolios. Incluye 'qué cambió' vs período anterior donde sea relevante."
            ),
            council_context=council_context,
            company_name=self.company_name,
            max_tokens=1000,
        )
        if result:
            lines = [l.strip() for l in result.split('\n') if l.strip()]
            if len(lines) >= 3:
                return lines

        return ["N/D — narrative engine no retorno takeaways validos."]

    def _fc(self, *keys, default=None):
        """Accede a forecast_data siguiendo ruta de keys."""
        d = self.forecast
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

    def _fc_pct(self, *keys, default='N/D') -> str:
        """Formatea forecast value como porcentaje."""
        val = self._fc(*keys)
        if val is None:
            return default
        try:
            return f"{float(val):.1f}%"
        except (ValueError, TypeError):
            return default

    def _generate_forecasts_table(self) -> Dict[str, List[Dict]]:
        """Genera tabla de forecasts tipo GS. Usa forecast_data si disponible, hardcoded como fallback."""

        # Check if forecast engine data is available
        has_gdp = bool(self._fc('gdp_forecasts'))
        has_infl = bool(self._fc('inflation_forecasts'))
        has_rates = bool(self._fc('rate_forecasts'))

        if has_gdp or has_infl or has_rates:
            return self._generate_forecasts_table_real()

        # No forecast data — return empty with N/D
        return {
            'gdp_growth': [
                {'region': r, 'actual_2025': 'N/D', 'forecast_2026': 'N/D', 'consenso': 'N/D', 'vs_anterior': 'N/A'}
                for r in ['USA', 'Eurozona', 'China', 'Chile']
            ],
            'inflation_core': [
                {'region': r, 'actual_2025': 'N/D', 'forecast_2026': 'N/D', 'consenso': 'N/D', 'vs_anterior': 'N/A'}
                for r in ['USA', 'Eurozona', 'Chile']
            ],
            'policy_rates': [
                {'banco': b, 'actual': 'N/D', 'forecast_2026': 'N/D', 'consenso': 'N/D', 'vs_anterior': 'N/A'}
                for b in ['Fed Funds', 'ECB Deposit', 'BCCh (Banco Central de Chile) TPM (Tasa de Política Monetaria)']
            ],
        }

    def _generate_forecasts_table_real(self) -> Dict[str, List[Dict]]:
        """Genera tabla de forecasts con datos reales del forecast engine."""

        # GDP Growth
        gdp_rows = []
        gdp_map = [
            ('USA', 'usa'), ('Eurozona', 'eurozone'), ('China', 'china'), ('Chile', 'chile'),
        ]
        for label, key in gdp_map:
            fc = self._fc('gdp_forecasts', key, default={})
            current = fc.get('current')
            forecast = fc.get('forecast_12m')
            consensus_val = self._fc('imf_consensus', 'gdp', key)
            gdp_rows.append({
                'region': label,
                'actual_2025': f"{current:.1f}%" if current else 'N/D',
                'forecast_2026': f"{forecast:.1f}%" if forecast else 'N/D',
                'consenso': f"{consensus_val:.1f}%" if consensus_val else 'N/D',
                'vs_anterior': '=',
                'source': 'Forecast Engine',
            })

        # Inflation
        infl_rows = []
        infl_map = [
            ('USA', 'usa'), ('Eurozona', 'eurozone'), ('Chile', 'chile'),
        ]
        for label, key in infl_map:
            fc = self._fc('inflation_forecasts', key, default={})
            current = fc.get('current')
            forecast = fc.get('forecast_12m')
            trend = fc.get('trend', '')
            consensus_val = self._fc('imf_consensus', 'inflation', key)
            infl_rows.append({
                'region': label,
                'actual_2025': f"{current:.1f}%" if current else 'N/D',
                'forecast_2026': f"{forecast:.1f}%" if forecast else 'N/D',
                'consenso': f"{consensus_val:.1f}%" if consensus_val else 'N/D',
                'vs_anterior': '=',
                'trend': trend,
                'source': 'Forecast Engine',
            })

        # Policy Rates — use terminal rate as market consensus (WEO no publica rates)
        rate_rows = []
        rate_map = [
            ('Fed Funds', 'fed_funds'), ('ECB Deposit', 'ecb'), ('BCCh TPM (Tasa de Política Monetaria)', 'tpm_chile'),
        ]
        for label, key in rate_map:
            fc = self._fc('rate_forecasts', key, default={})
            current = fc.get('current')
            forecast_12m = fc.get('forecast_12m')
            direction = fc.get('direction', '')
            terminal = fc.get('terminal')
            consenso = f"{terminal:.2f}%" if terminal is not None else 'N/D'
            rate_rows.append({
                'banco': label,
                'actual': f"{current:.2f}%" if current else 'N/D',
                'forecast_2026': f"{forecast_12m:.2f}%" if forecast_12m else 'N/D',
                'consenso': consenso,
                'vs_anterior': '=',
                'direction': direction,
                'source': 'Forecast Engine',
            })

        return {
            'gdp_growth': gdp_rows,
            'inflation_core': infl_rows,
            'policy_rates': rate_rows,
        }

    @staticmethod
    def _classify_scenario(name: str) -> str:
        """Classify a scenario name as 'upside', 'downside', or 'base'."""
        lower = name.lower()
        if any(w in lower for w in ('upside', 'alcista', 'optimista', 'bull',
                                     'soft landing', 'aterrizaje suave')):
            return 'upside'
        if any(w in lower for w in ('downside', 'bajista', 'pesimista', 'bear',
                                     'recesión', 'recesion', 'hard landing',
                                     'crisis', 'stagflation', 'estanflación')):
            return 'downside'
        return 'base'

    def _get_sp500_index_level(self) -> Optional[float]:
        """Fetch the actual S&P 500 index level (^GSPC) via yfinance."""
        try:
            import yfinance as yf
            idx = yf.Ticker('^GSPC')
            hist = idx.history(period='5d')
            if hist.empty:
                return None
            return float(hist['Close'].iloc[-1])
        except Exception:
            return None

    def generate_probability_weighted_forecasts(self) -> Dict[str, Any]:
        """Genera pronósticos ponderados por probabilidad de escenarios.
        Uses council scenario data and forecast engine equity targets.
        S&P 500 values are displayed as index levels (^GSPC), not SPY ETF prices.
        Each scenario gets a differentiated S&P target: base=target, upside=range_high, downside=range_low."""

        # Get scenario probabilities from council
        scenarios = self.parser.get_scenario_probs() if self.parser else None
        if not scenarios:
            return {
                'titulo': 'Pronóstico Ponderado por Escenarios',
                'metodologia': 'Weighted Average = Σ(Probabilidad_i × Pronóstico_i)',
                'escenarios': [],
                'weighted_forecasts': {},
                'implicancia': 'N/D — Sin escenarios definidos por el comité.',
            }

        # Get equity target data from forecast engine
        sp500_data = self._fc('equity_targets', 'sp500') or {}
        spy_target = sp500_data.get('target_12m')       # SPY ETF price
        spy_current = sp500_data.get('current_price')    # SPY ETF price
        spy_range = sp500_data.get('range', [])          # [low, high] in SPY prices
        spy_range_low = spy_range[0] if len(spy_range) >= 2 else spy_target
        spy_range_high = spy_range[1] if len(spy_range) >= 2 else spy_target

        # Compute SPY→S&P 500 index scaling factor
        # The forecast engine uses SPY (ETF ~1/10 of index). We need actual index levels.
        sp500_index = self._get_sp500_index_level()
        if sp500_index and spy_current and spy_current > 0:
            spy_to_index = sp500_index / spy_current
        elif spy_current and spy_current > 0:
            spy_to_index = 10.0  # Fallback: SPY ≈ S&P 500 / 10
        else:
            spy_to_index = 10.0

        # Convert SPY prices to S&P 500 index levels
        sp_current = round(spy_current * spy_to_index) if spy_current else None
        sp_target = round(spy_target * spy_to_index) if spy_target else None
        sp_range_low = round(spy_range_low * spy_to_index) if spy_range_low else sp_target
        sp_range_high = round(spy_range_high * spy_to_index) if spy_range_high else sp_target

        # Map scenario type → S&P 500 index target
        sp_by_type = {
            'base': sp_target,
            'upside': sp_range_high,
            'downside': sp_range_low,
        }

        gdp_us_fc = self._fc('gdp_forecasts', 'usa', 'forecast_12m')
        # World GDP: try IMF consensus first, then forecast engine 'world' key
        gdp_world_fc = self._fc('imf_consensus', 'gdp', 'world')
        if gdp_world_fc is None:
            gdp_world_fc = self._fc('gdp_forecasts', 'world', 'forecast_12m')

        # Scenario-specific GDP adjustments (base=0, upside=+0.5pp, downside=-1.0pp)
        gdp_adj = {'base': 0.0, 'upside': 0.5, 'downside': -1.0}

        # Build scenario rows from council data
        scenario_rows = []
        weighted_gdp_parts = []
        weighted_gdp_world_parts = []
        weighted_sp_parts = []

        for key, data in scenarios.items():
            prob = data.get('prob', 0)
            name = data.get('name', key)

            # Classify scenario to pick the right S&P target
            sc_type = self._classify_scenario(name)
            sp_val = sp_by_type.get(sc_type)

            # GDP USA: scenario-adjusted forecast
            adj = gdp_adj.get(sc_type, 0.0)
            gdp_val = round(gdp_us_fc + adj, 1) if gdp_us_fc is not None else None
            gdp_display = f'{gdp_val:.1f}%' if gdp_val is not None else 'N/D'

            # GDP World: scenario-adjusted forecast
            gdp_world_val = round(gdp_world_fc + adj, 1) if gdp_world_fc is not None else None
            gdp_world_display = f'{gdp_world_val:.1f}%' if gdp_world_val is not None else 'N/D'

            # S&P 500: per-scenario index level
            sp_display = f'{sp_val:,.0f}' if sp_val else 'N/D'

            scenario_rows.append({
                'nombre': name,
                'probabilidad': f"{int(prob * 100)}%",
                'gdp_us': gdp_display,
                'gdp_world': gdp_world_display,
                'sp500': sp_display,
            })

            if gdp_val is not None:
                weighted_gdp_parts.append(prob * gdp_val)
            if gdp_world_val is not None:
                weighted_gdp_world_parts.append(prob * gdp_world_val)
            if sp_val:
                weighted_sp_parts.append(prob * sp_val)

        # Compute weighted forecasts only if we have data
        weighted_forecasts = {}
        if weighted_gdp_parts:
            gdp_weighted = sum(weighted_gdp_parts)
            weighted_forecasts['gdp_us'] = f'{gdp_weighted:.1f}%'
        if weighted_gdp_world_parts:
            gdp_world_weighted = sum(weighted_gdp_world_parts)
            weighted_forecasts['gdp_world'] = f'{gdp_world_weighted:.1f}%'
        if weighted_sp_parts:
            sp_weighted = sum(weighted_sp_parts)
            weighted_forecasts['sp500'] = f'{sp_weighted:,.0f}'

        # Build implicancia text
        if weighted_forecasts.get('gdp_us') and weighted_forecasts.get('sp500') and sp_current:
            gdp_w = sum(weighted_gdp_parts)
            sp_w = sum(weighted_sp_parts)
            implicancia = (
                f"El pronóstico ponderado de PIB (Producto Interno Bruto) USA es {gdp_w:.1f}%. El S&P 500 ponderado de "
                f"{sp_w:,.0f} implica un retorno de "
                f"{((sp_w / sp_current - 1) * 100):.1f}% desde niveles actuales."
            )
        elif weighted_forecasts.get('gdp_us'):
            implicancia = f"El pronóstico ponderado de PIB (Producto Interno Bruto) USA es {sum(weighted_gdp_parts):.1f}%."
        else:
            implicancia = 'N/D — Datos insuficientes para pronóstico ponderado.'

        return {
            'titulo': 'Pronóstico Ponderado por Escenarios',
            'metodologia': 'Weighted Average = Σ(Probabilidad_i × Pronóstico_i)',
            'escenarios': scenario_rows,
            'weighted_forecasts': weighted_forecasts,
            'implicancia': implicancia,
        }

    def generate_vs_previous_forecast(self) -> Dict[str, Any]:
        """Genera seccion comparativa vs pronóstico anterior.
        Compara con el forecast más reciente guardado en output/forecasts/."""

        cambios = []
        prev = self._load_previous_forecast()

        if prev and self.forecast:
            # Compare GDP
            for region, label in [('usa', 'PIB (Producto Interno Bruto) USA'), ('china', 'PIB China'), ('chile', 'PIB Chile')]:
                curr = self._fc('gdp_forecasts', region, 'forecast_12m')
                prev_val = self._nested_get(prev, 'gdp_forecasts', region, 'forecast_12m')
                if curr is not None and prev_val is not None:
                    diff = curr - prev_val
                    cambios.append({
                        'variable': f'{label} 2026',
                        'anterior': f'{prev_val:.1f}%',
                        'actual': f'{curr:.1f}%',
                        'cambio': f'{diff:+.1f}pp',
                        'razon': 'Actualización del Forecast Engine',
                    })

            # Compare rates
            for rate, label in [('fed_funds', 'Fed Funds YE'), ('tpm_chile', 'TPM (Tasa de Política Monetaria) Chile YE')]:
                curr = self._fc('rate_forecasts', rate, 'forecast_12m')
                prev_val = self._nested_get(prev, 'rate_forecasts', rate, 'forecast_12m')
                if curr is not None and prev_val is not None:
                    diff_bp = round((curr - prev_val) * 100)
                    cambios.append({
                        'variable': f'{label} 2026',
                        'anterior': f'{prev_val:.2f}%',
                        'actual': f'{curr:.2f}%',
                        'cambio': f'{diff_bp:+d}bp',
                        'razon': 'Actualización del Forecast Engine',
                    })

            # Compare inflation
            curr_infl = self._fc('inflation_forecasts', 'usa', 'forecast_12m')
            prev_infl = self._nested_get(prev, 'inflation_forecasts', 'usa', 'forecast_12m')
            if curr_infl is not None and prev_infl is not None:
                diff = curr_infl - prev_infl
                cambios.append({
                    'variable': 'CPI Core (Inflación subyacente, excl. alimentos y energía) USA',
                    'anterior': f'{prev_infl:.1f}%',
                    'actual': f'{curr_infl:.1f}%',
                    'cambio': f'{diff:+.1f}pp',
                    'razon': 'Actualización del Forecast Engine',
                })

        # Fallback if no comparison possible
        if not cambios:
            cambios = [
                {'variable': 'PIB USA 2026', 'anterior': 'N/D', 'actual': self._fc_pct('gdp_forecasts', 'usa', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
                {'variable': 'Fed Funds YE', 'anterior': 'N/D', 'actual': self._fc_pct('rate_forecasts', 'fed_funds', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
                {'variable': 'CPI Core (Inflación subyacente) USA', 'anterior': 'N/D', 'actual': self._fc_pct('inflation_forecasts', 'usa', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
            ]

        prev_date = 'Mes anterior'
        if prev:
            prev_ts = self._nested_get(prev, 'metadata', 'timestamp')
            if prev_ts:
                try:
                    prev_date = datetime.fromisoformat(prev_ts).strftime('%B %Y')
                except Exception:
                    pass

        return {
            'titulo': 'Cambios vs Reporte Anterior',
            'fecha_anterior': prev_date,
            'cambios': cambios,
            'track_record': {
                'titulo': 'Aciertos del Reporte Anterior',
                'aciertos': [],
                'errores': []
            },
            'narrativa': (
                "Pronósticos generados por el Forecast Engine cuantitativo. "
                "Los cambios reflejan actualizaciones en datos macro, expectativas "
                "de mercado y modelos de valuación."
            )
        }

    def _load_previous_forecast(self) -> Optional[Dict]:
        """Carga el forecast anterior más reciente desde output/forecasts/."""
        try:
            fc_dir = Path(__file__).parent / "output" / "forecasts"
            files = sorted(fc_dir.glob("forecast_*.json"), reverse=True)
            if len(files) < 2:
                return None  # Need at least 2 (current + previous)
            # Skip the most recent (current run), load the second most recent
            with open(files[1], 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def _nested_get(self, d: Dict, *keys, default=None):
        """Navigate nested dict safely."""
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

    # =========================================================================
    # SECCION 2: ESTADOS UNIDOS
    # =========================================================================

    def generate_usa_section(self) -> Dict[str, Any]:
        """Genera seccion completa de EE.UU."""

        return {
            'crecimiento': self._generate_usa_growth(),
            'mercado_laboral': self._generate_usa_labor(),
            'inflación': self._generate_usa_inflation(),
            'política_monetaria': self._generate_fed_policy(),
            'política_fiscal': self._generate_usa_fiscal()
        }

    def _generate_usa_growth(self) -> Dict[str, Any]:
        """Genera seccion de crecimiento EE.UU."""
        d = self._get_usa_latest()
        gdp_val = self._fmt(d.get('gdp_qoq'))
        no_raw = d.get('mfg_new_orders_bn')
        no_val = f"${no_raw:.0f}bn" if no_raw else 'N/D'
        hs_raw = d.get('housing_starts')
        hs_val = f"{hs_raw/1000:.2f}M" if hs_raw else 'N/D'
        cc_val = self._fmt(d.get('consumer_confidence'), suffix='')

        # --- BEA GDP components (real data if available) ---
        bea = self._q('bea') or {}
        bea_parts = []
        if isinstance(bea, dict) and 'error' not in bea:
            gdp_comps = bea.get('gdp_components', {})
            for comp, label in [('personal_consumption', 'Consumo Personal'),
                                ('gross_private_investment', 'Inversión Privada'),
                                ('government', 'Gasto Gobierno'),
                                ('net_exports', 'Export. Netas')]:
                v = gdp_comps.get(comp)
                if v is not None:
                    bea_parts.append(f"{label}: {v:+.1f}%")
            pce = bea.get('pce', {})
            pce_total = pce.get('total_yoy')
            if pce_total is not None:
                bea_parts.append(f"PCE Total YoY: {pce_total:.1f}%")

        # --- OECD leading indicators ---
        oecd = self._q('oecd') or {}
        oecd_parts = []
        if isinstance(oecd, dict) and 'error' not in oecd:
            cli_usa = oecd.get('cli_usa') or oecd.get('cli', {}).get('usa')
            if cli_usa is not None:
                oecd_parts.append(f"OECD CLI USA: {cli_usa:.1f}")
            bci = oecd.get('business_confidence', {}).get('usa')
            if bci is not None:
                oecd_parts.append(f"Confianza Empresarial OECD: {bci:.1f}")

        from narrative_engine import generate_narrative
        quant_ctx = f"GDP QoQ anualizado: {gdp_val}. Mfg New Orders: {no_val}. Housing Starts: {hs_val}. Consumer Confidence: {cc_val}."
        if bea_parts:
            quant_ctx += f" BEA componentes: {'; '.join(bea_parts)}."
        if oecd_parts:
            quant_ctx += f" {'; '.join(oecd_parts)}."
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1500]
        narrativa = generate_narrative(
            section_name="usa_growth",
            prompt=(
                "Describe el estado del crecimiento de EE.UU. en 2-3 oraciones basandote SOLO en los datos proporcionados. "
                "NO asumas direccion (solido/debil) — deduce del GDP y leading indicators. Maximo 80 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=350,
        ) or f"GDP EE.UU.: {gdp_val}. Mfg New Orders: {no_val}. Housing Starts: {hs_val}. Consumer Confidence: {cc_val}."

        indicators = [
            {'indicador': 'Mfg New Orders (Nuevas Órdenes Industriales)', 'valor': no_val, 'tendencia': '-'},
            {'indicador': 'Housing Starts (Inicios de Vivienda)', 'valor': hs_val, 'tendencia': '-'},
            {'indicador': 'Consumer Confidence (Confianza del Consumidor)', 'valor': cc_val, 'tendencia': '-'},
        ]
        # Add BEA GDP components if available
        if isinstance(bea, dict) and 'error' not in bea:
            gdp_comps = bea.get('gdp_components', {})
            for comp, label in [('personal_consumption', 'Consumo Personal (BEA)'),
                                ('gross_private_investment', 'Inversión Privada (BEA)')]:
                v = gdp_comps.get(comp)
                if v is not None:
                    indicators.append({'indicador': label, 'valor': f"{v:+.1f}%", 'tendencia': '-'})
        # Add OECD CLI if available
        if isinstance(oecd, dict) and 'error' not in oecd:
            cli_usa = oecd.get('cli_usa') or oecd.get('cli', {}).get('usa')
            if cli_usa is not None:
                indicators.append({'indicador': 'OECD CLI EE.UU.', 'valor': f"{cli_usa:.1f}", 'tendencia': '-'})

        return {
            'titulo': 'Crecimiento Económico',
            'narrativa': narrativa,
            'drivers': [],
            'leading_indicators': indicators,
        }

    def _generate_usa_labor(self) -> Dict[str, Any]:
        """Genera seccion de mercado laboral EE.UU."""
        d = self._get_usa_latest()

        nfp = d.get('nfp')
        nfp_str = f"{nfp:+,.0f}K" if nfp is not None else 'N/D'
        nfp_prev = d.get('nfp_prev')
        nfp_prev_str = f"{nfp_prev:+,.0f}K" if nfp_prev is not None else 'N/D'
        u3_str = self._fmt(d.get('unemployment'))
        u3_prev_str = self._fmt(d.get('unemployment_prev'))
        u6_str = self._fmt(d.get('u6'))
        u6_prev_str = self._fmt(d.get('u6_prev'))
        lfpr_str = self._fmt(d.get('lfpr'))
        lfpr_prev_str = self._fmt(d.get('lfpr_prev'))
        prime_str = self._fmt(d.get('prime_age'))
        prime_prev_str = self._fmt(d.get('prime_age_prev'))
        ic_raw = d.get('initial_claims')
        ic_str = f"{ic_raw/1000:.0f}K" if ic_raw else 'N/D'
        ic_prev = d.get('initial_claims_prev')
        ic_prev_str = f"{ic_prev/1000:.0f}K" if ic_prev else 'N/D'
        cc_raw = d.get('continuing_claims')
        cc_str = f"{cc_raw/1000:.2f}M" if cc_raw else 'N/D'
        cc_prev = d.get('continuing_claims_prev')
        cc_prev_str = f"{cc_prev/1000:.2f}M" if cc_prev else 'N/D'
        ahe_str = self._fmt(d.get('ahe_yoy'), suffix='% a/a')
        ahe_prev_str = self._fmt(d.get('ahe_yoy_prev'), suffix='% a/a')
        jo_raw = d.get('job_openings')
        jo_str = f"{jo_raw/1000:.1f}M" if jo_raw else 'N/D'
        jo_prev = d.get('job_openings_prev')
        jo_prev_str = f"{jo_prev/1000:.1f}M" if jo_prev else 'N/D'
        qr_str = self._fmt(d.get('quits_rate'))
        qr_prev_str = self._fmt(d.get('quits_rate_prev'))

        from narrative_engine import generate_narrative
        quant_ctx = (
            f"NFP: {nfp_str} (prev {nfp_prev_str}). U3: {u3_str} (prev {u3_prev_str}). "
            f"U6: {u6_str}. LFPR: {lfpr_str}. Prime-Age: {prime_str}. "
            f"Initial Claims: {ic_str} (prev {ic_prev_str}). Continuing Claims: {cc_str}. "
            f"Job Openings: {jo_str} (prev {jo_prev_str}). Quits Rate: {qr_str}. AHE: {ahe_str} (prev {ahe_prev_str})."
        )
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1500]
        narrativa = generate_narrative(
            section_name="usa_labor",
            prompt=(
                "Describe el estado del mercado laboral de EE.UU. en 2-3 oraciones basandote SOLO en los datos. "
                "Deduce la direccion de los datos (anterior vs actual), NO asumas. Maximo 80 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=350,
        ) or f"NFP: {nfp_str}. Desempleo U3: {u3_str}. AHE: {ahe_str}."

        narrativa_jolts = generate_narrative(
            section_name="usa_jolts",
            prompt=(
                "Describe JOLTS en 1-2 oraciones con los datos proporcionados. NO asumas direccion. Maximo 40 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context="", quant_context=f"Job Openings: {jo_str} (prev {jo_prev_str}). Quits Rate: {qr_str} (prev {qr_prev_str}).",
            company_name=self.company_name, max_tokens=500,
        ) or f"Job Openings: {jo_str}. Quits Rate: {qr_str}."

        narrativa_salarios = generate_narrative(
            section_name="usa_wages",
            prompt=(
                "Describe presiones salariales en 1-2 oraciones con los datos. NO inventes umbrales ni estimaciones. Maximo 40 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context="", quant_context=f"AHE YoY: {ahe_str} (prev {ahe_prev_str}).",
            company_name=self.company_name, max_tokens=500,
        ) or f"AHE: {ahe_str}."

        def _trend(curr, prev):
            """Compute trend from current vs previous string values."""
            try:
                c = float(str(curr).replace('%', '').replace('K', '').replace('M', '').replace('$', '').replace('+', '').replace(',', '').strip())
                p = float(str(prev).replace('%', '').replace('K', '').replace('M', '').replace('$', '').replace('+', '').replace(',', '').strip())
                if c > p * 1.02: return 'Subiendo'
                if c < p * 0.98: return 'Bajando'
                return 'Estable'
            except (ValueError, TypeError):
                return '-'

        return {
            'titulo': 'Mercado Laboral',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Non-Farm Payrolls (Nóminas no agrícolas)', 'valor': nfp_str, 'anterior': nfp_prev_str, 'tendencia': _trend(nfp, nfp_prev)},
                {'indicador': 'Tasa Desempleo (U3)', 'valor': u3_str, 'anterior': u3_prev_str, 'tendencia': _trend(d.get('unemployment'), d.get('unemployment_prev'))},
                {'indicador': 'Desempleo Amplio (U6)', 'valor': u6_str, 'anterior': u6_prev_str, 'tendencia': _trend(d.get('u6'), d.get('u6_prev'))},
                {'indicador': 'Participación Laboral', 'valor': lfpr_str, 'anterior': lfpr_prev_str, 'tendencia': _trend(d.get('lfpr'), d.get('lfpr_prev'))},
                {'indicador': 'Participación Prime-Age', 'valor': prime_str, 'anterior': prime_prev_str, 'tendencia': _trend(d.get('prime_age'), d.get('prime_age_prev'))},
                {'indicador': 'Initial Claims (Solicitudes iniciales seguro desempleo)', 'valor': ic_str, 'anterior': ic_prev_str, 'tendencia': _trend(ic_raw, ic_prev)},
                {'indicador': 'Continuing Claims (Solicitudes continuas seguro desempleo)', 'valor': cc_str, 'anterior': cc_prev_str, 'tendencia': _trend(cc_raw, cc_prev)},
            ],
            'jolts': [
                {'indicador': 'Job Openings (Vacantes laborales JOLTS)', 'valor': jo_str, 'anterior': jo_prev_str, 'tendencia': _trend(jo_raw, jo_prev)},
                {'indicador': 'Quits Rate (Tasa de renuncias voluntarias)', 'valor': qr_str, 'anterior': qr_prev_str, 'tendencia': _trend(d.get('quits_rate'), d.get('quits_rate_prev'))},
            ],
            'salarios': [
                {'indicador': 'AHE (Avg Hourly Earnings — Salarios promedio por hora)', 'valor': ahe_str, 'anterior': ahe_prev_str, 'tendencia': _trend(d.get('ahe_yoy'), d.get('ahe_yoy_prev'))},
            ],
            'narrativa_jolts': narrativa_jolts,
            'narrativa_salarios': narrativa_salarios,
        }

    def _generate_usa_inflation(self) -> Dict[str, Any]:
        """Genera seccion de inflación EE.UU."""
        d = self._get_usa_latest()

        cpi_h_yoy = self._fmt(d.get('cpi_headline_yoy'), suffix='% a/a')
        cpi_c_yoy = self._fmt(d.get('cpi_core_yoy'), suffix='% a/a')
        pce_c_yoy = self._fmt(d.get('pce_core_yoy'), suffix='% a/a')
        cpi_h_mom = d.get('cpi_headline_mom')
        cpi_h_mom_str = f"{cpi_h_mom:+.2f}%" if cpi_h_mom is not None else 'N/D'
        cpi_c_mom = d.get('cpi_core_mom')
        cpi_c_mom_str = f"{cpi_c_mom:+.2f}%" if cpi_c_mom is not None else 'N/D'
        pce_c_mom = d.get('pce_core_mom')
        pce_c_mom_str = f"{pce_c_mom:+.2f}%" if pce_c_mom is not None else 'N/D'
        umich = self._fmt(d.get('umich_sentiment'), suffix='')

        from narrative_engine import generate_narrative
        quant_ctx = f"CPI Headline YoY: {cpi_h_yoy} (MoM: {cpi_h_mom_str}). CPI Core YoY: {cpi_c_yoy} (MoM: {cpi_c_mom_str}). PCE Core YoY: {pce_c_yoy} (MoM: {pce_c_mom_str}). UMich Sentiment: {umich}."
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1500]
        narrativa = generate_narrative(
            section_name="usa_inflation",
            prompt=(
                "Describe la inflacion de EE.UU. en 2-3 oraciones basandote SOLO en los datos. "
                "Compara con target de 2% de la Fed. NO asumas direccion — deduce de los numeros. Maximo 80 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=350,
        ) or f"CPI Headline: {cpi_h_yoy}. CPI Core: {cpi_c_yoy}. PCE Core: {pce_c_yoy}."

        return {
            'titulo': 'Inflación',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'CPI Headline (IPC general EE.UU.)', 'valor': cpi_h_yoy, 'anterior': self._fmt(d.get('cpi_headline_yoy_prev')), 'mom': cpi_h_mom_str},
                {'indicador': 'CPI Core (IPC subyacente, excl. alimentos y energía)', 'valor': cpi_c_yoy, 'anterior': self._fmt(d.get('cpi_core_yoy_prev')), 'mom': cpi_c_mom_str},
                {'indicador': 'PCE Core (Gasto de consumo personal subyacente — indicador preferido de la Fed)', 'valor': pce_c_yoy, 'anterior': self._fmt(d.get('pce_core_yoy_prev')), 'mom': pce_c_mom_str},
            ],
            'componentes': self._build_cpi_components(),
            'expectativas': [
                {'medida': 'UMich Sentiment (Confianza del Consumidor, U. de Michigan)', 'valor': umich, 'comentario': 'Fuente: FRED'},
                {'medida': 'Fed Target (Meta de inflación PCE)', 'valor': '2.0%', 'comentario': 'Objetivo de largo plazo de la Fed'},
            ]
        }

    def _build_cpi_components(self) -> List[Dict]:
        """Build CPI components from FRED data."""
        if not self.data:
            return [{'componente': c, 'valor': 'N/D', 'tendencia': '-'} for c in
                    ['Shelter (Vivienda)', 'Services ex-Energy (Servicios excl. Energía)', 'Core Goods (Bienes subyacentes)', 'Food (Alimentos)', 'Energy (Energía)']]
        try:
            comp = self.data.get_usa_cpi_breakdown()
        except Exception:
            comp = {}
        mapping = [
            ('Shelter (Vivienda)', 'shelter'),
            ('Services ex-Energy (Servicios excl. Energía)', 'services_ex_energy'),
            ('Core Goods (Bienes subyacentes)', 'goods_ex_food_energy'),
            ('Food (Alimentos)', 'food'),
            ('Energy (Energía)', 'energy'),
        ]
        result = []
        for label, key in mapping:
            val = self._sf(comp.get(key))
            val_str = f"{val:.1f}% a/a" if val is not None else 'N/D'
            result.append({'componente': label, 'valor': val_str, 'tendencia': '-'})
        return result

    def _get_fed_neutral(self, dots: dict) -> str:
        """Fed neutral rate: dots longer_run > NY Fed r-star > forecast terminal."""
        if self.data and dots and dots.get('longer_run'):
            return f"{dots['longer_run']}%"
        # NY Fed r-star from quant_data
        rstar = self.quant.get('nyfed_rstar', {})
        if rstar and not rstar.get('error'):
            rstar_val = rstar.get('rstar') or rstar.get('r_star')
            if rstar_val is not None:
                return f"{rstar_val:.2f}% (NY Fed r*)"
        fc = self._fc_pct('rate_forecasts', 'fed_funds', 'terminal')
        if fc != 'N/D':
            return fc
        # No hardcoded fallback — return N/D if all sources unavailable
        return "N/D — fuentes de tasa neutral no disponibles"

    def _generate_fed_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria Fed."""
        d = self._get_usa_latest()
        ff = d.get('fed_funds')
        ff_str = self._fmt(ff)
        pce_core = d.get('pce_core_yoy')
        real_rate = None
        if ff is not None and pce_core is not None:
            real_rate = round(ff - pce_core, 1)
        real_str = self._fmt(real_rate)

        # Try to get Fed dots from FRED
        dot_plot = {
            '2026': {'mediana': 'N/D', 'rango': 'N/D'},
            '2027': {'mediana': 'N/D', 'rango': 'N/D'},
            'largo_plazo': {'mediana': 'N/D', 'rango': 'N/D'}
        }
        dots = None
        if self.data:
            try:
                dots = self.data.fred.get_fed_dots()
                if dots and dots.get('by_year'):
                    for yr, val in dots['by_year'].items():
                        yr_key = str(yr)
                        rng = dots.get('range', {}).get(yr, {})
                        rng_str = f"{rng.get('low', 'N/D')}%-{rng.get('high', 'N/D')}%" if rng else 'N/D'
                        dot_plot[yr_key] = {'mediana': f"{val}%", 'rango': rng_str}
                    if dots.get('longer_run'):
                        lr_rng = dots.get('longer_run_range', {})
                        lr_str = f"{lr_rng.get('low', 'N/D')}%-{lr_rng.get('high', 'N/D')}%" if lr_rng else 'N/D'
                        dot_plot['largo_plazo'] = {'mediana': f"{dots['longer_run']}%", 'rango': lr_str}
            except Exception:
                pass

        return {
            'titulo': 'Política Monetaria - Federal Reserve',
            'narrativa': (
                f"El Fed Funds se ubica en {ff_str}. "
                f"Con la inflación Core PCE en {self._fmt(pce_core)} y el mercado laboral en equilibrio, "
                f"la Fed se encuentra evaluando su política. La tasa real se situa en {real_str}."
            ),
            'tasas': {
                'actual': ff_str,
                'neutral_estimada': self._get_fed_neutral(dots),
                'real_actual': real_str,
                'proyección_2026': self._fc_pct('rate_forecasts', 'fed_funds', 'forecast_12m'),
                'mercado_implica': self._fc_pct('rate_forecasts', 'fed_funds', 'terminal'),
            },
            'dot_plot': dot_plot,
            'taylor_rule': self._build_taylor_rule(ff),
            'riesgos': self._generate_fed_risks(ff, pce_core, real_rate),
            'proximas_reuniones': self._build_fed_meetings()
        }

    def _generate_fed_risks(self, ff, pce_core, real_rate) -> List[str]:
        """Generate Fed policy risks via Sonnet — no hardcoded opinions."""
        from narrative_engine import generate_data_driven_narrative
        import json as _json

        quant_parts = []
        if ff is not None:
            quant_parts.append(f"Fed Funds: {ff}%")
        if pce_core is not None:
            quant_parts.append(f"Core PCE: {pce_core}%")
        if real_rate is not None:
            quant_parts.append(f"Tasa real: {real_rate}%")
        unemployment = self._q('macro_usa', 'unemployment')
        if unemployment is not None:
            quant_parts.append(f"Desempleo: {unemployment}%")

        council_text = self.council.get('panel_outputs', {}).get('macro', '')
        if council_text:
            quant_parts.append(f"Council macro: {council_text[:500]}")

        quant_ctx = " | ".join(quant_parts) if quant_parts else ""
        if not quant_ctx:
            return ['Datos insuficientes para evaluación de riesgos']

        result = generate_data_driven_narrative(
            section_name="macro_fed_risks",
            prompt=(
                "Genera exactamente 3 riesgos para la política monetaria de la Fed "
                "basados en los datos disponibles. Formato JSON: "
                '["riesgo 1 en 1 oración con dato", "riesgo 2", "riesgo 3"]. '
                "Cada riesgo debe referenciar un dato concreto. SOLO JSON."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=400,
        )
        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, list) and len(parsed) >= 2:
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass
        return ['Evaluar datos macro actualizados para riesgos específicos']

    def _build_taylor_rule(self, ff: float = None) -> Dict[str, str]:
        """Build Taylor Rule dict from econometric detail in forecast data."""
        econ = self.forecast.get('econometric_detail', {})
        taylor = econ.get('taylor_fed', {})
        suggested = taylor.get('taylor_rate') or taylor.get('inertia_rate')
        if suggested is not None:
            diff = round(suggested - ff, 2) if ff is not None else None
            diff_str = f"{diff:+.2f}pp" if diff is not None else 'N/D'
            return {
                'tasa_sugerida': f"{suggested:.2f}%",
                'diferencia': diff_str,
                'comentario': f"Taylor puro: {taylor.get('pure_taylor', 'N/D')}%, con inercia: {suggested:.2f}%"
            }
        return {'tasa_sugerida': 'N/D', 'diferencia': 'N/D', 'comentario': 'Datos insuficientes'}

    def _build_fed_meetings(self) -> List[Dict[str, str]]:
        """Build Fed meetings from forecast data (FedWatch methodology)."""
        fc = self.forecast.get('rate_forecasts', {}).get('fed_funds', {})
        cuts = fc.get('cuts_expected', 0) or 0
        terminal = fc.get('terminal')
        current = fc.get('current')

        # 2026 FOMC schedule from config
        from greybark.config import FOMC_2026
        schedule = [(d, i * 40) for i, (d, _) in enumerate(FOMC_2026[1:])]  # skip past meetings

        if current is None or terminal is None or cuts == 0:
            # No data — return first 3 with N/D
            return [{'fecha': s[0], 'expectativa': 'TBD', 'probabilidad': 'N/D'}
                    for s in schedule[:3]]

        # Distribute cuts across meetings (market expects earlier cuts)
        rate = current
        step = 0.25
        cuts_remaining = int(cuts)
        meetings = []
        for date_str, _ in schedule[:3]:
            if cuts_remaining > 0 and rate > terminal + 0.01:
                action = f"-25bp → {rate - step:.2f}%"
                rate -= step
                cuts_remaining -= 1
            else:
                action = 'Hold'
            # Confidence based on proximity and cuts remaining
            if action == 'Hold':
                prob = '85%+'
            else:
                prob = '70%+' if cuts_remaining >= 0 else '50%+'
            meetings.append({'fecha': date_str, 'expectativa': action, 'probabilidad': prob})

        return meetings

    def _generate_fiscal_risks(self, deficit_str, debt_str, interest_str) -> List[str]:
        """Generate fiscal risks via Sonnet — no hardcoded opinions."""
        from narrative_engine import generate_data_driven_narrative
        import json as _json

        quant_ctx = f"Déficit/PIB: {deficit_str} | Deuda/PIB: {debt_str} | Costo deuda: {interest_str}"
        council_text = self.council.get('panel_outputs', {}).get('macro', '')
        if council_text:
            quant_ctx += f" | Council: {council_text[:300]}"

        result = generate_data_driven_narrative(
            section_name="macro_fiscal_risks",
            prompt=(
                "Genera exactamente 2 riesgos fiscales de EE.UU. basados en los datos. "
                'Formato JSON: ["riesgo 1 con dato", "riesgo 2 con dato"]. SOLO JSON.'
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=300,
        )
        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, list) and len(parsed) >= 1:
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass
        return [f'Déficit fiscal {deficit_str} requiere monitoreo', f'Costo de deuda {interest_str} en tendencia alcista']

    def _generate_usa_fiscal(self) -> Dict[str, Any]:
        """Genera seccion de política fiscal EE.UU."""
        fiscal = {}
        if self.data:
            try:
                fiscal = self.data.get_usa_fiscal()
            except Exception:
                pass

        deficit = fiscal.get('deficit_gdp')
        debt = fiscal.get('debt_gdp')
        interest = fiscal.get('interest_gdp')

        deficit_str = f"{deficit:.1f}% GDP" if deficit is not None else 'N/D'
        debt_str = f"{debt:.1f}% GDP" if debt is not None else 'N/D'
        interest_str = f"{interest:.1f}% GDP" if interest is not None else 'N/D'

        # Dynamic narrative based on data
        if deficit is not None and debt is not None and interest is not None:
            deficit_dir = "se amplió" if (fiscal.get('deficit_gdp_prev') and deficit < fiscal['deficit_gdp_prev']) else "se redujo"
            narrativa = (
                f"El déficit fiscal federal se ubica en {deficit_str} ({deficit_dir} vs {self._fmt(fiscal.get('deficit_gdp_prev'))} previo). "
                f"La deuda pública total alcanza {debt_str}, "
                f"mientras los costos de servicio de deuda representan {interest_str} del producto, "
                f"reflejando el impacto acumulado de tasas más altas sobre el stock de deuda."
            )
        else:
            narrativa = (
                f"El déficit fiscal se ubica en {deficit_str}. "
                f"La deuda pública se sitúa en {debt_str}. "
                f"Los costos de servicio de deuda representan {interest_str}."
            )

        return {
            'titulo': 'Política Fiscal',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Déficit Fiscal', 'valor': deficit_str, 'anterior': self._fmt(fiscal.get('deficit_gdp_prev'))},
                {'indicador': 'Deuda Publica', 'valor': debt_str, 'anterior': self._fmt(fiscal.get('debt_gdp_prev'))},
                {'indicador': 'Costo Deuda', 'valor': interest_str, 'anterior': self._fmt(fiscal.get('interest_gdp_prev'))},
            ],
            'riesgos': self._generate_fiscal_risks(deficit_str, debt_str, interest_str)
        }

    # =========================================================================
    # SECCION 3: EUROPA
    # =========================================================================

    def generate_europe_section(self) -> Dict[str, Any]:
        """Genera seccion de Europa."""

        return {
            'crecimiento': self._generate_europe_growth(),
            'inflación': self._generate_europe_inflation(),
            'política_monetaria': self._generate_ecb_policy(),
            'riesgos_especificos': self._generate_europe_risks()
        }

    def _generate_europe_growth(self) -> Dict[str, Any]:
        """Genera seccion de crecimiento Europa."""
        eu = self._get_europe_latest()

        # Real data with fallback
        gdp_ez = self._fmt(eu.get('gdp_qoq'), suffix='% t/t')
        gdp_de = self._fmt(eu.get('gdp_alemania'), suffix='% t/t')
        gdp_fr = self._fmt(eu.get('gdp_francia'), suffix='% t/t')
        gdp_uk = self._fmt(eu.get('gdp_uk'), suffix='% t/t')
        desemp = self._fmt(eu.get('unemployment'))

        has_real = bool(eu.get('gdp_qoq') is not None)
        src = ' (datos BCCh)' if has_real else ''

        return {
            'titulo': f'Crecimiento - Eurozona{src}',
            'narrativa': (
                f"La economía europea muestra recuperación gradual. "
                f"El último GDP trimestral Eurozona: {gdp_ez}. "
                f"Alemania: {gdp_de}, Francia: {gdp_fr}, UK: {gdp_uk}. "
                f"Desempleo Eurozona: {desemp}. "
                f"El sector manufacturero comienza a estabilizarse mientras servicios "
                f"mantiene expansión moderada."
            ),
            'por_pais': [
                {'pais': 'Eurozona', 'gdp_2025': gdp_ez, 'gdp_2026f': self._fc_pct('gdp_forecasts', 'eurozone', 'forecast_12m'), 'consenso': 'N/D'},
                {'pais': 'Alemania', 'gdp_2025': gdp_de, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
                {'pais': 'Francia', 'gdp_2025': gdp_fr, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
                {'pais': 'UK', 'gdp_2025': gdp_uk, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
            ],
            'indicadores': [
                {'indicador': 'Desempleo Eurozona', 'valor': desemp, 'comentario': 'BCCh' if has_real else 'Estimado'},
                {'indicador': 'PMI (Índice de Gerentes de Compra) Manufacturing', 'valor': self._get_bloomberg_pmi('euro_mfg'), 'comentario': 'Bloomberg'},
                {'indicador': 'PMI Services', 'valor': self._get_bloomberg_pmi('euro_svc'), 'comentario': 'Bloomberg'},
            ],
            'desafios_estructurales': [
                'Demografia adversa - población en edad laboral decreciendo',
                'Competitividad industrial erosionada vs China/US',
                'Costos de energía estructuralmente más altos',
                'Fragmentacion política limita reformas'
            ]
        }

    def _bbg_val(self, campo_id: str, decimals: int = 1) -> str:
        """Get a formatted Bloomberg value by campo_id, or 'N/D' if unavailable."""
        if self.bloomberg:
            try:
                val = self.bloomberg.get_latest(campo_id)
                if val is not None:
                    return f"{val:.{decimals}f}"
            except Exception:
                pass
        return 'N/D'

    def _bbg_prev(self, campo_id: str, decimals: int = 1) -> str:
        """Get a formatted Bloomberg previous-month value, or 'N/D'."""
        if self.bloomberg:
            try:
                val = self.bloomberg.get_previous(campo_id)
                if val is not None:
                    return f"{val:.{decimals}f}"
            except Exception:
                pass
        return 'N/D'

    def _get_bloomberg_pmi(self, key: str) -> str:
        """Get PMI from Bloomberg data."""
        if self.bloomberg:
            try:
                pmi = self.bloomberg.get_pmi_latest()
                if pmi and key in pmi:
                    return f"{pmi[key]:.1f}"
            except Exception:
                pass
        return 'N/D'

    def _generate_europe_inflation(self) -> Dict[str, Any]:
        """Genera seccion de inflación Europa."""
        eu = self._get_europe_latest()

        cpi_val = self._fmt(eu.get('cpi'))
        core_val = self._fmt(eu.get('core_cpi'))
        ppi_val = self._fmt(eu.get('ppi'))

        has_real = bool(eu.get('cpi') is not None)
        src = ' (datos BCCh)' if has_real else ''

        return {
            'titulo': f'Inflación - Eurozona{src}',
            'narrativa': (
                f"La inflación europea se ubica con HICP headline en {cpi_val}, "
                f"mientras el core converge a {core_val}. "
                f"PPI Eurozona: {ppi_val}. "
                f"Los salarios negociados se han moderado. La inflación de servicios "
                f"cede, permitiendo al BCE mantener tasas estables cerca de neutral."
            ),
            'datos': [
                {'indicador': 'HICP Headline (IPC armonizado Eurozona)', 'valor': cpi_val, 'anterior': '-'},
                {'indicador': 'HICP Core (IPC armonizado subyacente)', 'valor': core_val, 'anterior': '-'},
                {'indicador': 'PPI Eurozona (Índice de Precios al Productor)', 'valor': ppi_val, 'anterior': '-'},
                {'indicador': 'Salarios Negociados', 'valor': 'N/D', 'anterior': 'N/D'},
            ]
        }

    def _generate_ecb_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria BCE."""
        eu = self._get_europe_latest()

        ecb_rate = self._fmt(eu.get('ecb_rate'), decimals=2)
        bund_10y = self._fmt(eu.get('bund_10y'), decimals=2)

        # --- ECB API direct data (DFR, HICP, M3) ---
        ecb_api = self._q('ecb') or {}
        ecb_parts = []
        if isinstance(ecb_api, dict) and 'error' not in ecb_api:
            dfr = ecb_api.get('deposit_facility_rate') or ecb_api.get('dfr')
            if dfr is not None:
                # Prefer ECB API over BCCh for deposit rate
                ecb_rate = f"{float(dfr):.2f}%"
                ecb_parts.append(f"DFR (ECB): {ecb_rate}")
            hicp = ecb_api.get('hicp_yoy')
            if hicp is not None:
                ecb_parts.append(f"HICP (ECB): {float(hicp):.1f}%")
            m3 = ecb_api.get('m3_yoy')
            if m3 is not None:
                ecb_parts.append(f"M3 YoY (ECB): {float(m3):.1f}%")
            ea_10y = ecb_api.get('ea_10y_yield') or ecb_api.get('ea_benchmark_10y')
            if ea_10y is not None:
                ecb_parts.append(f"EA 10Y: {float(ea_10y):.2f}%")

        has_real = bool(eu.get('ecb_rate') is not None or ecb_parts)
        src = ' (datos BCCh + ECB)' if ecb_parts else (' (datos BCCh)' if has_real else '')

        from narrative_engine import generate_narrative
        quant_ctx = f"ECB Deposit Rate: {ecb_rate}. Bund 10Y: {bund_10y}."
        if ecb_parts:
            quant_ctx += f" {'; '.join(ecb_parts)}."
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1000]
        narrativa = generate_narrative(
            section_name="ecb_policy",
            prompt=(
                "Describe la politica monetaria del BCE en 2-3 oraciones basandote SOLO en los datos. "
                "NO proyectes recortes ni movimientos futuros — eso viene del council. Maximo 60 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=300,
        ) or f"ECB Deposit Rate: {ecb_rate}. Bund 10Y: {bund_10y}."

        return {
            'titulo': f'Política Monetaria - BCE{src}',
            'narrativa': narrativa,
            'tasas': {
                'deposito_actual': ecb_rate,
                'refi_actual': bund_10y,
                'proyección_2026': self._fc_pct('rate_forecasts', 'ecb', 'forecast_12m'),
                'neutral_estimada': self._fc_pct('rate_forecasts', 'ecb', 'terminal'),
            },
            'próximos_movimientos': [],
            'balance_riesgos': {
                'dovish': 'Debilidad económica mayor a la esperada',
                'hawkish': 'Inflación persistente por encima del objetivo'
            }
        }

    def _generate_europe_risks(self) -> Dict[str, Any]:
        """Genera riesgos especificos Europa via Claude."""
        from narrative_engine import generate_narrative
        council_ctx = self.council.get('panel_outputs', {}).get('geo', '')[:1500]
        result = generate_narrative(
            section_name="europe_risks",
            prompt=(
                "Lista 2-3 riesgos especificos de Europa basandote en el council output. "
                "Formato JSON: [{\"nombre\": \"...\", \"descripcion\": \"...\", \"probabilidad\": \"Alta/Media/Baja\", \"impacto\": \"Alto/Medio/Bajo\"}]. "
                "Solo riesgos mencionados o derivados del council. Si no hay contexto, devuelve []."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx, quant_context="",
            company_name=self.company_name, max_tokens=500,
        )
        riesgos = []
        if result:
            import json as _json
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = _json.loads(cleaned)
                if isinstance(parsed, list):
                    riesgos = parsed
            except (_json.JSONDecodeError, KeyError):
                pass
        return {
            'titulo': 'Riesgos Especificos Europa',
            'riesgos': riesgos if riesgos else [{'nombre': 'Fragmentación política', 'descripcion': 'Riesgo de divergencia fiscal entre miembros de la Eurozona.', 'probabilidad': 'Media', 'impacto': 'Medio'}]
        }

    # =========================================================================
    # SECCION 4: CHINA
    # =========================================================================

    def generate_china_section(self) -> Dict[str, Any]:
        """Genera seccion de China."""

        return {
            'crecimiento': self._generate_china_growth(),
            'sector_inmobiliario': self._generate_china_property(),
            'impulso_crediticio': self._generate_china_credit(),
            'comercio_exterior': self._generate_china_trade(),
            'política_monetaria': self._generate_pboc_policy()
        }

    def _generate_china_growth(self) -> Dict[str, Any]:
        """Genera seccion de crecimiento China."""
        cn = self._get_china_latest()

        gdp_val = self._fmt(cn.get('gdp_qoq'), suffix='% t/t')
        cpi_val = self._fmt(cn.get('cpi_yoy') or cn.get('cpi'))
        cpi_prev = self._fmt(cn.get('cpi_yoy_prev'))
        desemp_val = self._fmt(cn.get('unemployment'))
        ppi_val = self._fmt(cn.get('ppi_yoy') or cn.get('ppi'))
        ppi_prev = self._fmt(cn.get('ppi_yoy_prev'))

        # PMI: AKShare (NBS) > Bloomberg
        pmi_mfg = self._fmt(cn.get('pmi_mfg'))
        pmi_mfg_prev = self._fmt(cn.get('pmi_mfg_prev'))
        if pmi_mfg == 'N/D':
            pmi_mfg = self._get_bloomberg_pmi('china_mfg')
        pmi_svc = self._fmt(cn.get('pmi_svc'))
        pmi_svc_prev = self._fmt(cn.get('pmi_svc_prev'))
        if pmi_svc == 'N/D':
            pmi_svc = self._get_bloomberg_pmi('china_svc')

        # Caixin PMI
        caixin_mfg = self._fmt(cn.get('caixin_mfg'))
        caixin_svc = self._fmt(cn.get('caixin_svc'))

        # Activity
        ip_val = self._fmt(cn.get('industrial_prod_yoy'))
        ip_prev = self._fmt(cn.get('industrial_prod_yoy_prev'))
        rs_val = self._fmt(cn.get('retail_sales_yoy'))
        rs_prev = self._fmt(cn.get('retail_sales_yoy_prev'))

        # --- AKShare China real data (NBS direct) ---
        ak = self._q('akshare_china') or self._q('akshare') or {}
        ak_parts = []
        if isinstance(ak, dict) and 'error' not in ak:
            # AKShare can provide more granular NBS data
            for ak_key, ak_label in [('fai_ytd', 'Inversión Fija (FAI) YTD'),
                                      ('m2_yoy', 'M2 YoY'), ('tso_yoy', 'TSF YoY')]:
                v = ak.get(ak_key)
                if v is not None:
                    ak_parts.append(f"{ak_label}: {v:.1f}%")
            # Overwrite N/D values with AKShare if BCCh missed them
            if ip_val == 'N/D' and ak.get('industrial_production_yoy') is not None:
                ip_val = self._fmt(ak['industrial_production_yoy'])
            if rs_val == 'N/D' and ak.get('retail_sales_yoy') is not None:
                rs_val = self._fmt(ak['retail_sales_yoy'])
            if cpi_val == 'N/D' and ak.get('cpi_yoy') is not None:
                cpi_val = self._fmt(ak['cpi_yoy'])
            if ppi_val == 'N/D' and ak.get('ppi_yoy') is not None:
                ppi_val = self._fmt(ak['ppi_yoy'])

        has_real = bool(cn.get('gdp_qoq') is not None or cn.get('pmi_mfg') is not None)
        src = ' (BCCh + NBS)' if has_real else ''

        from narrative_engine import generate_narrative
        quant_ctx = (
            f"China GDP QoQ: {gdp_val}. CPI YoY: {cpi_val}. PPI YoY: {ppi_val}. "
            f"Desempleo: {desemp_val}. PMI Mfg (NBS): {pmi_mfg}. PMI Svc: {pmi_svc}. "
            f"Caixin Mfg: {caixin_mfg}. Prod Industrial: {ip_val}. Ventas Retail: {rs_val}."
        )
        if ak_parts:
            quant_ctx += f" AKShare NBS: {'; '.join(ak_parts)}."
        council_ctx = self.council.get('panel_outputs', {}).get('geo', '')[:1000]
        narrativa = generate_narrative(
            section_name="china_growth",
            prompt=(
                "Describe el crecimiento de China en 2-3 oraciones basandote SOLO en datos. "
                "NO asumas direccion del property sector ni exportaciones sin datos. Maximo 60 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=300,
        ) or f"China GDP: {gdp_val}. CPI: {cpi_val}. PMI Mfg: {pmi_mfg}."

        return {
            'titulo': f'Crecimiento{src}',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'GDP QoQ (PIB trimestral)', 'valor': gdp_val, 'anterior': 'BCCh'},
                {'indicador': 'CPI YoY (IPC interanual)', 'valor': cpi_val, 'anterior': cpi_prev},
                {'indicador': 'PPI YoY (Precios al Productor interanual)', 'valor': ppi_val, 'anterior': ppi_prev},
                {'indicador': 'Desempleo Urbano', 'valor': desemp_val, 'anterior': '-'},
            ],
            'indicadores': [
                {'indicador': 'PMI (Índice de Gerentes de Compra) Manufacturing (NBS)', 'valor': pmi_mfg, 'anterior': pmi_mfg_prev, 'comentario': 'NBS'},
                {'indicador': 'PMI Services (NBS)', 'valor': pmi_svc, 'anterior': pmi_svc_prev, 'comentario': 'NBS'},
                {'indicador': 'Caixin Mfg PMI (sector privado)', 'valor': caixin_mfg, 'anterior': self._fmt(cn.get('caixin_mfg_prev')), 'comentario': 'Caixin'},
                {'indicador': 'Caixin Services PMI (sector privado)', 'valor': caixin_svc, 'anterior': self._fmt(cn.get('caixin_svc_prev')), 'comentario': 'Caixin'},
                {'indicador': 'Producción Industrial YoY (interanual)', 'valor': ip_val, 'anterior': ip_prev, 'comentario': 'NBS'},
                {'indicador': 'Ventas Retail YoY (Ventas Minoristas interanual)', 'valor': rs_val, 'anterior': rs_prev, 'comentario': 'NBS'},
            ]
        }

    def _generate_china_property(self) -> Dict[str, Any]:
        """Genera seccion de sector inmobiliario China."""
        cn = self._get_china_latest()

        # Property Sales: Bloomberg > AKShare
        prop_sales = self._bbg_val('china_property_sales_yoy')
        prop_prev = self._bbg_prev('china_property_sales_yoy')

        # Home Prices: AKShare (NBS 70-city data)
        hp_tier1 = self._fmt(cn.get('home_price_yoy_tier1'))
        hp_tier1_prev = self._fmt(cn.get('home_price_yoy_tier1_prev'))
        hp_bj = self._fmt(cn.get('home_price_yoy_bj'))
        hp_sh = self._fmt(cn.get('home_price_yoy_sh'))

        has_data = prop_sales != 'N/D' or hp_tier1 != 'N/D'
        if has_data:
            from narrative_engine import generate_narrative
            parts = []
            if prop_sales != 'N/D':
                parts.append(f"Property Sales YoY: {prop_sales}%")
            if hp_tier1 != 'N/D':
                parts.append(f"Home Prices Tier 1 YoY: {hp_tier1}")
            if hp_bj != 'N/D':
                parts.append(f"Beijing: {hp_bj}")
            if hp_sh != 'N/D':
                parts.append(f"Shanghai: {hp_sh}")
            narrativa = generate_narrative(
                section_name="china_property",
                prompt=(
                    "Describe el sector inmobiliario de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras."
                    "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
                ),
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context='. '.join(parts) + '.',
                company_name=self.company_name, max_tokens=500,
            ) or f"Sector inmobiliario China: {'. '.join(parts)}."
        else:
            narrativa = "Datos de sector inmobiliario no disponibles."

        return {
            'titulo': 'Sector Inmobiliario',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Ventas Inmobiliarias YoY', 'valor': prop_sales, 'anterior': prop_prev},
                {'indicador': 'Precios Vivienda Tier 1 YoY (ciudades principales)', 'valor': hp_tier1, 'anterior': hp_tier1_prev},
                {'indicador': 'Precios Vivienda Beijing YoY', 'valor': hp_bj, 'anterior': '-'},
                {'indicador': 'Precios Vivienda Shanghai YoY', 'valor': hp_sh, 'anterior': '-'},
            ],
            'políticas_soporte': [],
            'drag_estimado': {}
        }

    def _generate_china_credit(self) -> Dict[str, Any]:
        """Genera seccion de impulso crediticio China."""
        cn = self._get_china_latest()

        # TSF: AKShare (absolute 亿元) > Bloomberg (YoY %)
        tsf_bbg = self._bbg_val('china_tsf_yoy')
        tsf_bbg_prev = self._bbg_prev('china_tsf_yoy')
        tsf_ak = cn.get('tsf')  # absolute 亿元 (100M CNY)
        tsf_ak_prev = cn.get('tsf_prev')

        # New Loans: AKShare > Bloomberg
        new_loans_bbg = self._bbg_val('china_new_loans', 0)
        new_loans_bbg_prev = self._bbg_prev('china_new_loans', 0)
        new_loans_ak = cn.get('new_loans')
        new_loans_ak_prev = cn.get('new_loans_prev')

        # M2: AKShare > Bloomberg
        m2_bbg = self._bbg_val('china_m2_yoy')
        m2_bbg_prev = self._bbg_prev('china_m2_yoy')
        m2_ak = cn.get('m2_yoy')
        m2_ak_prev = cn.get('m2_yoy_prev')

        # Use best available source
        m2 = f"{m2_ak:.1f}" if m2_ak is not None else m2_bbg
        m2_prev = self._fmt(m2_ak_prev) if m2_ak_prev is not None else m2_bbg_prev
        tsf = f"{tsf_ak:,.0f}" if tsf_ak is not None else tsf_bbg
        tsf_prev = f"{tsf_ak_prev:,.0f}" if tsf_ak_prev is not None else tsf_bbg_prev
        new_loans = f"{new_loans_ak:,.0f}" if new_loans_ak is not None else new_loans_bbg
        new_loans_prev = f"{new_loans_ak_prev:,.0f}" if new_loans_ak_prev is not None else new_loans_bbg_prev

        has_data = m2 != 'N/D' or tsf != 'N/D'
        parts = []
        if m2 != 'N/D':
            parts.append(f"M2: {m2}% YoY")
        if tsf != 'N/D':
            parts.append(f"TSF: {tsf} bn CNY")
        if new_loans != 'N/D':
            parts.append(f"New Loans: {new_loans} bn CNY")

        if has_data:
            from narrative_engine import generate_narrative
            narrativa = generate_narrative(
                section_name="china_credit",
                prompt=(
                    "Describe el impulso crediticio de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras."
                    "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
                ),
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context=', '.join(parts),
                company_name=self.company_name, max_tokens=500,
            ) or f"Impulso crediticio China: {', '.join(parts)}."
        else:
            narrativa = "Datos de impulso crediticio chino no disponibles."

        return {
            'titulo': 'Impulso Crediticio',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'M2 Growth YoY (masa monetaria amplia, interanual)', 'valor': m2, 'anterior': m2_prev},
                {'indicador': 'TSF (亿元)', 'valor': tsf, 'anterior': tsf_prev},
                {'indicador': 'New Yuan Loans (亿元)', 'valor': new_loans, 'anterior': new_loans_prev},
            ],
            'implicancias_globales': (
                "El credit impulse positivo en China históricamente precede mejor demanda "
                "de commodities y crecimiento global con lag de 6-9 meses."
            )
        }

    def _generate_china_trade(self) -> Dict[str, Any]:
        """Genera seccion de comercio exterior China."""
        cn = self._get_china_latest()

        # Trade: AKShare > Bloomberg
        exp_ak = cn.get('exp_yoy')
        imp_ak = cn.get('imp_yoy')
        tb_ak = cn.get('trade_bal')

        exp_yoy = f"{exp_ak:.1f}" if exp_ak is not None else self._bbg_val('china_exp_yoy')
        exp_prev = self._fmt(cn.get('exp_yoy_prev')) if cn.get('exp_yoy_prev') is not None else self._bbg_prev('china_exp_yoy')
        imp_yoy = f"{imp_ak:.1f}" if imp_ak is not None else self._bbg_val('china_imp_yoy')
        imp_prev = self._fmt(cn.get('imp_yoy_prev')) if cn.get('imp_yoy_prev') is not None else self._bbg_prev('china_imp_yoy')
        trade_bal = f"{tb_ak:.1f}" if tb_ak is not None else self._bbg_val('china_trade_bal', 1)
        trade_prev = f"{cn['trade_bal_prev']:.1f}" if cn.get('trade_bal_prev') is not None else self._bbg_prev('china_trade_bal', 1)

        has_data = exp_yoy != 'N/D' or trade_bal != 'N/D'
        if has_data:
            parts = []
            if exp_yoy != 'N/D':
                parts.append(f"Exports YoY: {exp_yoy}%")
            if imp_yoy != 'N/D':
                parts.append(f"Imports YoY: {imp_yoy}%")
            if trade_bal != 'N/D':
                parts.append(f"Trade Balance: USD {trade_bal}bn")
            from narrative_engine import generate_narrative
            narrativa = generate_narrative(
                section_name="china_trade",
                prompt=(
                    "Describe el comercio exterior de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras."
                    "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
                ),
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context=', '.join(parts),
                company_name=self.company_name, max_tokens=500,
            ) or f"Comercio exterior China: {', '.join(parts)}."
        else:
            narrativa = "Datos de comercio exterior chino no disponibles."

        return {
            'titulo': 'Comercio Exterior',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Trade Balance (USD bn)', 'valor': trade_bal, 'anterior': trade_prev},
                {'indicador': 'Exports YoY', 'valor': exp_yoy, 'anterior': exp_prev},
                {'indicador': 'Imports YoY', 'valor': imp_yoy, 'anterior': imp_prev},
            ],
            'implicancias_commodities': []
        }

    def _generate_pboc_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria PBOC."""
        cn = self._get_china_latest()

        pboc_rate = self._fmt(cn.get('pboc_rate'), decimals=2)
        cny_val = f"{cn['cny_usd']:.2f}" if cn.get('cny_usd') is not None else 'N/D'
        shanghai = f"{cn['shanghai']:.0f}" if cn.get('shanghai') is not None else 'N/D'

        # LPR and RRR from AKShare (NBS)
        lpr_1y = self._fmt(cn.get('lpr_1y'), decimals=2)
        lpr_5y = self._fmt(cn.get('lpr_5y'), decimals=2)
        rrr = self._fmt(cn.get('rrr'), decimals=1)
        lpr_1y_prev = self._fmt(cn.get('lpr_1y_prev'), decimals=2)
        lpr_5y_prev = self._fmt(cn.get('lpr_5y_prev'), decimals=2)
        rrr_prev = self._fmt(cn.get('rrr_prev'), decimals=1)

        has_real = bool(cn.get('pboc_rate') is not None or cn.get('lpr_1y') is not None)
        src = ' (BCCh + NBS)' if has_real else ''

        from narrative_engine import generate_narrative
        quant_ctx = (
            f"PBOC Rate: {pboc_rate}. LPR 1Y: {lpr_1y}. LPR 5Y: {lpr_5y}. "
            f"RRR: {rrr}. CNY/USD: {cny_val}. Shanghai Composite: {shanghai}."
        )
        narrativa = generate_narrative(
            section_name="pboc_policy",
            prompt=(
                "Describe la politica monetaria del PBOC en 1-2 oraciones con los datos. "
                "NO proyectes movimientos futuros — eso viene del council. Maximo 40 palabras."
                "\n\nSigue la cadena dato→interpretación→implicación. Especifica horizonte temporal (táctico 1-3m o estratégico 6-12m)."
            ),
            council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
            quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=500,
        ) or f"PBOC Rate: {pboc_rate}. LPR 1Y: {lpr_1y}. CNY/USD: {cny_val}."

        return {
            'titulo': f'Política Monetaria - PBOC{src}',
            'narrativa': narrativa,
            'tasas': {
                'pboc_rate': pboc_rate,
                'lpr_1y': lpr_1y,
                'lpr_1y_prev': lpr_1y_prev,
                'lpr_5y': lpr_5y,
                'lpr_5y_prev': lpr_5y_prev,
                'rrr': rrr,
                'rrr_prev': rrr_prev,
                'yuan_usdcny': cny_val,
                'shanghai': shanghai,
            },
            'outlook': {
                'tasas': 'Sesgo expansivo: recortes graduales de LPR esperados',
                'rrr': 'Probable recorte adicional para impulsar liquidez',
                'yuan': 'Depreciación controlada por PBoC'
            }
        }

    # =========================================================================
    # SECCION 5: CHILE Y LATAM
    # =========================================================================

    def generate_chile_section(self) -> Dict[str, Any]:
        """Genera seccion de Chile y LatAm."""

        return {
            'chile_crecimiento': self._generate_chile_growth(),
            'chile_inflación': self._generate_chile_inflation(),
            'chile_política_monetaria': self._generate_bcch_policy(),
            'chile_cuentas_externas': self._generate_chile_external(),
            'commodities_relevantes': self._generate_commodities(),
            'latam_context': self._generate_latam_context()
        }

    def _generate_chile_growth(self) -> Dict[str, Any]:
        """Genera seccion de crecimiento Chile."""
        cl = self._get_chile_latest()
        imacec = cl.get('imacec_yoy')
        desemp = cl.get('desempleo')

        # Use real values if available
        imacec_str = (self._fmt(imacec) + ' a/a') if imacec is not None else 'N/D'
        desemp_str = self._fmt(desemp)

        imacec_desc = 'expansión' if imacec is not None and imacec > 0 else 'contracción' if imacec is not None and imacec < 0 else 'variación'
        recupera_desc = 'consolida su recuperación' if imacec is not None and imacec > 0 else 'muestra debilidad' if imacec is not None and imacec < 0 else 'se mantiene'
        narrativa = (
            f"La economía chilena {recupera_desc}. "
            f"El IMACEC muestra {imacec_desc} de {imacec_str}, "
            f"con servicios y mineria como drivers. "
            f"El consumo privado mantiene dinamismo apoyado por salarios reales positivos. "
            f"La tasa de desempleo se ubica en {desemp_str}. "
            f"Proyección de GDP para 2026: {self._fc_pct('gdp_forecasts', 'chile', 'forecast_12m')}."
        )

        return {
            'titulo': 'Chile - Crecimiento',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'IMACEC', 'valor': imacec_str, 'anterior': self._fmt(cl.get('imacec_yoy_prev')), 'tendencia': '-'},
                {'indicador': 'GDP Trim (t/t-4)', 'valor': self._fmt(cl.get('pib_trim_yoy'), '%'),
                 'anterior': self._fmt(cl.get('pib_trim_yoy_prev'), '%'), 'tendencia': '-'},
                {'indicador': 'Consumo Privado', 'valor': self._fmt(cl.get('consumo_privado_yoy'), '%') + ' a/a' if cl.get('consumo_privado_yoy') is not None else 'N/D',
                 'anterior': self._fmt(cl.get('consumo_privado_yoy_prev'), '%'), 'tendencia': '-'},
                {'indicador': 'Inversión (FBCF)', 'valor': self._fmt(cl.get('fbcf_yoy'), '%') + ' a/a' if cl.get('fbcf_yoy') is not None else 'N/D',
                 'anterior': self._fmt(cl.get('fbcf_yoy_prev'), '%'), 'tendencia': '-'},
            ],
            'mercado_laboral': [
                {'indicador': 'Tasa Desempleo', 'valor': desemp_str, 'anterior': self._fmt(cl.get('desempleo_prev'))},
            ]
        }

    def _generate_chile_inflation(self) -> Dict[str, Any]:
        """Genera seccion de inflación Chile."""
        cl = self._get_chile_latest()
        ipc_yoy = cl.get('ipc_yoy')
        ipc_mom = cl.get('ipc_mom')

        ipc_yoy_str = (self._fmt(ipc_yoy) + ' a/a') if ipc_yoy is not None else 'N/D'
        ipc_mom_str = f"+{self._fmt(ipc_mom)}" if ipc_mom is not None else 'N/D'

        narrativa = (
            f"IPC Chile headline: {ipc_yoy_str}, variacion mensual: {ipc_mom_str}. "
            f"Meta BCCh: 3.0%."
        )

        return {
            'titulo': 'Chile - Inflación',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'IPC Headline', 'valor': ipc_yoy_str, 'anterior': self._fmt(cl.get('ipc_yoy_prev')), 'mom': ipc_mom_str},
                {'indicador': 'IPC Subyacente (SAE)', 'valor': 'N/D', 'anterior': 'N/D', 'mom': 'N/D'},
            ],
            'expectativas': self._build_eee_expectations()
        }

    def _build_eee_expectations(self) -> List[Dict[str, str]]:
        """Build EEE expectations from quant_data (chile_eee from BCCh)."""
        eee = self.quant.get('chile_eee', {})
        if not eee or 'error' in eee:
            return [
                {'medida': 'EEE 1 año', 'valor': 'N/D', 'anterior': 'N/D'},
                {'medida': 'EEE 2 años', 'valor': 'N/D', 'anterior': 'N/D'},
            ]
        rows = []
        # EEE inflation expectations
        infl_1y = eee.get('inflation_1y')
        infl_2y = eee.get('inflation_2y')
        tpm_1y = eee.get('tpm_12m')
        tpm_2y = eee.get('tpm_24m')
        if infl_1y is not None:
            rows.append({'medida': 'EEE Inflación 1 año', 'valor': f"{infl_1y:.1f}%", 'anterior': '-'})
        if infl_2y is not None:
            rows.append({'medida': 'EEE Inflación 2 años', 'valor': f"{infl_2y:.1f}%", 'anterior': '-'})
        if tpm_1y is not None:
            rows.append({'medida': 'EEE TPM 12M', 'valor': f"{tpm_1y:.2f}%", 'anterior': '-'})
        if tpm_2y is not None:
            rows.append({'medida': 'EEE TPM 24M', 'valor': f"{tpm_2y:.2f}%", 'anterior': '-'})
        if not rows:
            return [
                {'medida': 'EEE 1 año', 'valor': 'N/D', 'anterior': 'N/D'},
                {'medida': 'EEE 2 años', 'valor': 'N/D', 'anterior': 'N/D'},
            ]
        return rows

    def _generate_bcch_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria BCCh."""
        cl = self._get_chile_latest()
        tpm = cl.get('tpm')
        ipc_yoy = cl.get('ipc_yoy')

        tpm_str = self._fmt(tpm)
        tpm_real_str = self._fmt(tpm - ipc_yoy, decimals=1) if (tpm is not None and ipc_yoy is not None) else 'N/D'

        narrativa = (
            f"El BCCh mantiene la TPM en {tpm_str}. "
            f"Con la inflación en meta y la economía creciendo cerca de potencial, el BCCh "
            f"se encuentra cerca del neutral. La TPM real se ubica en {tpm_real_str}, "
            f"ligeramente restrictivo pero convergiendo a neutral."
        )

        return {
            'titulo': 'Chile - Política Monetaria (BCCh)',
            'narrativa': narrativa,
            'tasas': {
                'tpm_actual': tpm_str,
                'tpm_neutral': self._fc_pct('rate_forecasts', 'tpm_chile', 'terminal'),
                'tpm_real': tpm_real_str,
                'proyección_2026': self._fc_pct('rate_forecasts', 'tpm_chile', 'forecast_12m'),
                'consenso_2026': self._fc_pct('rate_forecasts', 'tpm_chile', 'terminal'),
            },
            'ipom_path': [
                {'trimestre': 'Q1 2026', 'tpm_proyectada': tpm_str},
                {'trimestre': 'Q2 2026', 'tpm_proyectada': self._fc_pct('rate_forecasts', 'tpm_chile', 'forecast_12m')},
            ],
            'comunicacion': (
                "El Consejo del BCCh senala que mantendra la TPM en niveles cercanos al neutral, "
                "evaluando la evolución de la inflación y la actividad económica."
            ),
            'proximas_reuniones': [],  # No market-implied probabilities available
        }

    def _generate_chile_external(self) -> Dict[str, Any]:
        """Genera seccion de cuentas externas Chile."""
        cl = self._get_chile_latest()
        usd_clp = cl.get('usd_clp')

        usdclp_str = f"{usd_clp:.0f}" if usd_clp is not None else 'N/D'

        narrativa = (
            f"El tipo de cambio se ubica en {usdclp_str} CLP/USD. "
            f"Los terminos de intercambio dependen del precio del cobre y el litio."
        )

        return {
            'titulo': 'Chile - Cuentas Externas',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Cuenta Corriente', 'valor': 'N/D', 'anterior': 'N/D'},
                {'indicador': 'Balanza Comercial', 'valor': 'N/D', 'anterior': 'N/D'},
            ],
            'tipo_cambio': {
                'usdclp_actual': usdclp_str,
                'rango_12m': 'N/D',
                'drivers': 'Diferencial tasas, precio cobre, risk appetite global',
            }
        }

    def _generate_commodities(self) -> Dict[str, Any]:
        """Genera seccion de commodities relevantes para Chile."""
        # Try to get real copper price from BCCh data provider
        copper_price = None
        copper_prev = None
        if self.data:
            try:
                comm = self.data.get_commodities()
                cobre_series = comm.get('cobre')
                if cobre_series is not None and len(cobre_series) > 0:
                    copper_price = float(cobre_series.iloc[-1])
                    if len(cobre_series) > 20:
                        copper_prev = float(cobre_series.iloc[-21])  # ~1 month ago
            except Exception:
                pass
        copper_str = f'${copper_price:.2f}/lb' if copper_price else 'N/D'
        copper_prev_str = f'${copper_prev:.2f}/lb' if copper_prev else '-'
        copper_chg = 'N/D'
        if copper_price and copper_prev:
            pct = ((copper_price / copper_prev) - 1) * 100
            copper_chg = f'{pct:+.1f}%'

        # Get litio and brent from BCCh if available
        litio_str = 'N/D'
        litio_prev_str = '-'
        litio_chg = 'N/D'
        brent_str = 'N/D'
        brent_prev_str = '-'
        brent_chg = 'N/D'
        if self.data:
            try:
                comm = self.data.get_commodities()
                litio_series = comm.get('litio')
                if litio_series is not None and len(litio_series) > 0:
                    litio_val = float(litio_series.iloc[-1])
                    litio_str = f'${litio_val:,.1f}/kg'
                    if len(litio_series) > 20:
                        litio_prev_val = float(litio_series.iloc[-21])
                        litio_prev_str = f'${litio_prev_val:,.1f}/kg'
                        litio_chg = f'{((litio_val / litio_prev_val) - 1) * 100:+.1f}%'
                brent_series = comm.get('petroleo')
                if brent_series is not None and len(brent_series) > 0:
                    brent_val = float(brent_series.iloc[-1])
                    brent_str = f'${brent_val:.1f}/bbl'
                    if len(brent_series) > 20:
                        brent_prev_val = float(brent_series.iloc[-21])
                        brent_prev_str = f'${brent_prev_val:.1f}/bbl'
                        brent_chg = f'{((brent_val / brent_prev_val) - 1) * 100:+.1f}%'
            except Exception:
                pass

        # Text-mine commodity outlook from council
        def _commodity_outlook(name_lower, chg_str):
            """Derive outlook from council text or price trend."""
            council_text = ''
            if self.council:
                for key in ('final_recommendation', 'cio_synthesis'):
                    council_text += ' ' + (self.council.get(key, '') or '')
                for panel in self.council.get('panel_outputs', {}).values():
                    council_text += ' ' + (panel if isinstance(panel, str) else '')
            import re as _re
            # Strip markdown headers and metadata lines to avoid leaking raw council text
            ct = _re.sub(r'#[^\n]*\n?', '', council_text)
            ct = _re.sub(r'\*\*[^*]*\*\*', '', ct)
            ct = _re.sub(r'---+', '', ct)
            ct = ct.lower()
            # Search council for commodity mentions
            sentences = _re.split(r'[.;]\s*', ct)
            relevant = [s for s in sentences if name_lower in s and len(s.strip()) > 15]
            if relevant:
                snippet = relevant[0].strip()
                if len(snippet) > 80:
                    snippet = snippet[:77] + '...'
                return snippet[0].upper() + snippet[1:] if snippet else 'Neutral'
            # Fallback: derive from price change
            try:
                pct = float(chg_str.replace('%', '').replace('+', ''))
                if pct > 5:
                    return 'Positivo (tendencia alcista)'
                elif pct < -5:
                    return 'Negativo (tendencia bajista)'
                else:
                    return 'Neutral (rango lateral)'
            except (ValueError, AttributeError):
                return 'N/D'

        def _commodity_drivers(name_lower):
            drivers_map = {
                'cobre': 'Demanda China, transición energética, inventarios LME',
                'litio': 'Demanda EV, capacidad nueva, precios spot vs contrato',
                'petróleo': 'Decisiones OPEC+, demanda global, inventarios EIA',
            }
            return drivers_map.get(name_lower, 'Oferta/demanda global')

        return {
            'titulo': 'Commodities Relevantes',
            'commodities': [
                {
                    'nombre': 'Cobre',
                    'precio_actual': copper_str,
                    'precio_anterior': copper_prev_str,
                    'cambio': copper_chg,
                    'outlook': _commodity_outlook('cobre', copper_chg),
                    'balance': 'N/D',
                    'drivers': _commodity_drivers('cobre'),
                    'inventarios': {},
                    'supply': {},
                    'breakeven_costs': {},
                },
                {
                    'nombre': 'Litio',
                    'precio_actual': litio_str,
                    'precio_anterior': litio_prev_str,
                    'cambio': litio_chg,
                    'outlook': _commodity_outlook('litio', litio_chg),
                    'balance': 'N/D',
                    'drivers': _commodity_drivers('litio'),
                    'inventarios': {},
                    'supply': {},
                    'breakeven_costs': {},
                },
                {
                    'nombre': 'Petróleo (Brent)',
                    'precio_actual': brent_str,
                    'precio_anterior': brent_prev_str,
                    'cambio': brent_chg,
                    'outlook': _commodity_outlook('petróleo', brent_chg),
                    'balance': 'N/D',
                    'drivers': _commodity_drivers('petróleo'),
                    'inventarios': {},
                    'breakeven_costs': {},
                }
            ],
            'transmisión_global': {},
            'impacto_fiscal': {},
        }

    def _generate_latam_context(self) -> Dict[str, Any]:
        """Genera contexto de LatAm."""
        return {
            'titulo': 'Contexto LatAm',
            'paises': self._build_latam_table(),
            'diferenciacion_chile': 'Chile se diferencia por marco institucional sólido, grado de inversión y ciclo monetario avanzado.'
        }

    def _build_latam_table(self) -> List[Dict]:
        """Build LatAm macro table from BCCh data (get_latam_rates returns pd.Series per rate)."""
        if not self.data:
            return [{'pais': p, 'gdp': 'N/D', 'inflación': 'N/D', 'tasa': 'N/D', 'outlook': '-', 'riesgo_principal': '-'}
                    for p in ['Brasil', 'Mexico', 'Colombia']]
        try:
            latam = self.data.get_latam_rates()
        except Exception:
            latam = {}
        # Map country names to series keys returned by get_latam_rates()
        rate_map = {
            'Brasil': ('Selic (Brasil)', 'Selic'),
            'Mexico': ('Banxico (Mexico)', 'Banxico'),
            'Colombia': ('BanRep (Colombia)', 'BanRep'),
            'Chile': ('BCCh TPM (Chile)', 'BCCh'),
        }
        result = []
        import pandas as pd
        for country, (series_key, rate_name) in rate_map.items():
            series = latam.get(series_key)
            tasa = None
            if isinstance(series, pd.Series) and not series.empty:
                tasa = float(series.iloc[-1])
            elif isinstance(series, (int, float)):
                tasa = float(series)
            result.append({
                'pais': country,
                'gdp': 'N/D',
                'inflación': 'N/D',
                'tasa': f"{tasa:.2f}% ({rate_name})" if tasa is not None else 'N/D',
                'outlook': '-',
                'riesgo_principal': '-',
            })
        return result

    # =========================================================================
    # SECCION 6: TEMAS MACRO CLAVE
    # =========================================================================

    def generate_macro_themes(self) -> Dict[str, Any]:
        """Genera seccion de temás macro clave."""

        return {
            'temas': self._generate_key_themes(),
            'calendario_eventos': self._generate_events_calendar()
        }

    def _generate_key_themes(self) -> List[Dict[str, Any]]:
        """Genera temas macro clave, enriquecidos con council output."""
        panels = self.council.get('panel_outputs', {})
        geo_panel = panels.get('geo', '')
        rv_panel = panels.get('rv', '')
        risk_panel = panels.get('riesgo', '')

        # EPU indicators (from data provider or quant)
        epu_data = {}
        if self.data:
            try:
                usa_latest = self._get_usa_latest()
                epu_data['usa'] = usa_latest.get('epu_usa')
            except Exception:
                pass
            try:
                china_latest = self._get_china_latest()
                epu_data['china'] = china_latest.get('epu_china')
            except Exception:
                pass
        # Fallback from quant data
        if not epu_data.get('china'):
            china_q = self.quant.get('china', {})
            if isinstance(china_q, dict) and 'error' not in china_q:
                epu_val = china_q.get('epu', {})
                if isinstance(epu_val, dict):
                    epu_data['china'] = epu_val.get('value') or epu_val.get('current')

        # Build EPU summary for geopolitics theme
        epu_lines = []
        for region, label in [('usa', 'EE.UU.'), ('china', 'China')]:
            val = epu_data.get(region)
            if val is not None:
                level = 'EXTREMO' if val > 300 else ('ELEVADO' if val > 200 else ('MODERADO' if val > 100 else 'BAJO'))
                epu_lines.append(f"{label}: {val:.0f} ({level})")

        epu_html = ''
        if epu_lines:
            epu_html = (
                '<br><br><strong>Índice de Incertidumbre Política (EPU)</strong>: '
                + ' | '.join(epu_lines)
                + '. <em>Base histórica = 100. Valores sobre 200 indican incertidumbre elevada.</em>'
            )

        # Generate themes dynamically from council output via Claude
        from narrative_engine import generate_narrative
        import json as _json

        panels = self.council.get('panel_outputs', {})
        final_rec = self.council.get('final_recommendation', '')
        council_text = (
            f"GEO PANEL:\n{geo_panel[:1500]}\n\n"
            f"RV PANEL:\n{rv_panel[:1000]}\n\n"
            f"RISK PANEL:\n{risk_panel[:1000]}\n\n"
            f"FINAL REC:\n{final_rec[:1500]}"
        )

        result = generate_narrative(
            section_name="macro_themes",
            prompt=(
                f"Genera exactamente 3-4 temas macro clave de {self.month_name} {self.year} "
                "basandote SOLO en lo que discute el council. "
                "Devuelve un JSON array donde cada elemento tiene: "
                '{"titulo": "string", "descripcion": "string (HTML, 80-120 palabras)", '
                '"impacto_macro": {"key": "value string"}}. '
                "Las descripciones deben ser en prosa analitica, no listas. "
                "Usa <strong> solo para datos criticos o price targets. "
                "NO inventes datos que no aparezcan en el council."
                "\n\nPara cada tema, incluye: escenario_base (prob + dato soporte) y escenario_riesgo (prob + dato soporte + qué lo invalida)."
            ),
            council_context=council_text,
            company_name=self.company_name,
            max_tokens=1500,
            temperature=0.2,
        )

        if result:
            # Try to parse JSON from Claude response
            try:
                # Strip markdown code fences if present
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                themes = _json.loads(cleaned)
                if isinstance(themes, list) and len(themes) >= 2:
                    # Append EPU data to first theme if available
                    if epu_html and themes:
                        themes[0]['descripcion'] = themes[0].get('descripcion', '') + epu_html
                    return themes
            except (_json.JSONDecodeError, KeyError, IndexError):
                pass

        return [{
            'titulo': 'N/D',
            'descripcion': 'Temas macro no disponibles — council session requerida.' + epu_html,
            'impacto_macro': {'global': 'N/D'}
        }]

    def _generate_events_calendar(self) -> List[Dict[str, Any]]:
        """Genera calendario de eventos clave via Claude."""
        from narrative_engine import generate_narrative
        import json as _json
        result = generate_narrative(
            section_name="events_calendar",
            prompt=(
                f"Genera un calendario de 4-6 eventos macro clave FUTUROS (despues del {self.date.day} de {self.month_name} {self.year}). "
                "Formato JSON: [{\"fecha\": \"DD Mon\", \"evento\": \"...\", \"relevancia\": \"Alta/Media\", \"impacto_potencial\": \"...\"}]. "
                "Incluye: FOMC/Fed, ECB, BCCh, datos de inflacion y PIB relevantes. "
                "SOLO eventos que NO hayan ocurrido aun. Devuelve SOLO el JSON."
            ),
            council_context="", quant_context="",
            company_name=self.company_name, max_tokens=500,
        )
        if result:
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = _json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) >= 2:
                    return parsed
            except (_json.JSONDecodeError, KeyError):
                pass
        return [{'fecha': '-', 'evento': 'Calendario no disponible', 'relevancia': '-', 'impacto_potencial': '-'}]

    # =========================================================================
    # SECCION 7: ESCENARIOS Y RIESGOS
    # =========================================================================

    def generate_scenarios_risks(self) -> Dict[str, Any]:
        """Genera seccion de escenarios y riesgos."""

        return {
            'escenarios': self._generate_scenarios(),
            'top_risks': self._generate_top_risks()
        }

    def _generate_scenarios(self) -> Dict[str, Any]:
        """Scenarios from council parser — zero hardcoded data."""
        scenarios = self.parser.get_scenario_probs() if self.parser else None
        if not scenarios:
            return {
                'escenarios': [],
                'narrativa': 'Sin escenarios definidos por el comité.'
            }

        result = []
        for key, data in scenarios.items():
            prob_raw = data.get('prob', None)
            prob_str = f"{int(prob_raw * 100)}%" if isinstance(prob_raw, (int, float)) else 'N/D'
            desc = data.get('description', '')
            result.append({
                'nombre': data.get('name', key),
                'probabilidad': prob_str,
                'descripcion': desc,
            })

        return {
            'escenarios': result,
            'narrativa': ''  # Will be filled by narrative_engine
        }

    def _generate_top_risks(self) -> Dict[str, Any]:
        """Top risks from council — zero hardcoded data."""
        risks = self.parser.get_risk_assessment() if self.parser else None
        if not risks:
            return {
                'riesgos': [],
                'narrativa': 'Sin evaluación de riesgos del comité.'
            }

        result = []
        for r in risks[:5]:  # Top 5
            result.append({
                'nombre': r.get('risk', 'N/D'),
                'probabilidad': f"{r['probability']}" if r.get('probability') else 'N/D',
                'impacto': r.get('impact', 'N/D'),
                'horizonte': r.get('horizon', 'N/D'),
                'senal_temprana': r.get('early_signal', r.get('monitoring', '')),
            })

        return {
            'riesgos': result,
            'narrativa': ''  # Will be filled by narrative_engine
        }

    # =========================================================================
    # SECCION 8: CONCLUSIONES Y VISTA DEL COMITE
    # =========================================================================

    def generate_conclusions(self) -> Dict[str, Any]:
        """Genera conclusiones con vistas sobre inflacion, crecimiento,
        bancos centrales y posicionamiento vs consenso."""

        final_rec = self.council.get('final_recommendation', '')
        cio = self.council.get('cio_synthesis', '')
        panels = self.council.get('panel_outputs', {})

        if final_rec or cio:
            return self._build_council_conclusions(final_rec, cio, panels)

        # Fallback sin council
        return self._build_default_conclusions()

    def _build_council_conclusions(self, final_rec: str, cio: str,
                                    panels: Dict) -> Dict[str, Any]:
        """Construye conclusiones desde council output via Claude."""
        from narrative_engine import generate_narrative
        import json as _json

        council_text = (
            f"FINAL REC:\n{final_rec[:3000]}\n\n"
            f"CIO:\n{cio[:2000]}\n\n"
            f"MACRO:\n{panels.get('macro', '')[:1000]}\n\n"
            f"RF:\n{panels.get('rf', '')[:1000]}\n\n"
            f"GEO:\n{panels.get('geo', '')[:1000]}\n\n"
            f"RIESGO:\n{panels.get('riesgo', '')[:1000]}"
        )

        # Generate intro paragraph
        intro = generate_narrative(
            section_name="conclusions_intro",
            prompt=(
                f"Escribe 2-3 oraciones introductorias para la seccion de conclusiones del "
                f"reporte macro de {self.month_name} {self.year}. Indica que estas son las vistas "
                "principales y como se comparan con el consenso. Tono: directo, profesional. "
                "NO menciones 'comité', 'panel', 'council', 'agentes'. Maximo 60 palabras."
            ),
            council_context=council_text[:1000],
            company_name=self.company_name,
            max_tokens=300,
        )
        if not intro:
            intro = (
                f"Las conclusiones de {self.month_name} {self.year} reflejan nuestro análisis "
                f"integrado de las principales variables macro."
            )

        # Generate vistas as structured JSON
        vistas_raw = generate_narrative(
            section_name="conclusions_vistas",
            prompt=(
                "Genera exactamente 4-5 vistas tematicas basadas en lo que discute el council. "
                "Devuelve un JSON array donde cada elemento tiene: "
                '{"tema": "string (ej: Inflacion, Crecimiento, Bancos Centrales, etc)", '
                '"vista_grb": "string (2-4 oraciones con nuestra lectura, usando datos del council)", '
                '"vs_consenso": "string corto (ej: Por encima del consenso, Alineado, Mas cauto)", '
                '"vs_detalle": "string (1-2 oraciones explicando la diferencia vs consenso)"}. '
                "Los temas deben reflejar lo que realmente discutio el council — NO usar temas genericos "
                "si el council no los aborda. Usa datos concretos del council."
                "\n\nCada vista regional debe incluir: convicción (ALTA/MEDIA/BAJA) con evidencia explícita, qué cambió vs período anterior, y horizonte temporal. Explica jerga en primera mención."
            ),
            council_context=council_text,
            company_name=self.company_name,
            max_tokens=1500,
            temperature=0.2,
        )

        vistas = []
        if vistas_raw:
            try:
                cleaned = vistas_raw.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                vistas = _json.loads(cleaned)
            except (_json.JSONDecodeError, KeyError):
                pass

        if not vistas:
            vistas = [
                {'tema': 'Panorama General', 'vista_grb': 'Ver sección de análisis para detalle.',
                 'vs_consenso': 'Ver detalle', 'vs_detalle': 'Análisis completo en secciones anteriores.'}
            ]

        # Generate positioning summary
        pos_resumen = generate_narrative(
            section_name="conclusions_positioning",
            prompt=(
                "Escribe un parrafo de posicionamiento general (3-4 oraciones). "
                "Resume la postura (risk-on/off/selectivo), las principales preferencias "
                "de activos, y el catalizador clave a monitorear. "
                "Usa <strong> para la postura general. Maximo 80 palabras."
            ),
            council_context=f"FINAL REC:\n{final_rec[:2000]}",
            company_name=self.company_name,
            max_tokens=400,
        )
        if not pos_resumen:
            pos_resumen = 'N/D — narrative engine no genero posicionamiento.'

        return {
            'titulo': f'Conclusiones — {self.month_name} {self.year}',
            'intro': intro,
            'vistas': vistas,
            'posicionamiento_resumen': pos_resumen,
            'proximo_reporte': (
                'Este análisis macro sirve como input para los reportes complementarios de '
                'Asset Allocation y Renta Fija.'
            )
        }

    def _build_default_conclusions(self) -> Dict[str, Any]:
        """Conclusiones generadas por Sonnet usando datos macro disponibles."""
        from narrative_engine import generate_data_driven_narrative, generate_structured_json

        # Build comprehensive quant context
        quant_parts = []
        for key, label in [('gdp', 'GDP US'), ('core_cpi', 'Core CPI'), ('unemployment', 'Desempleo'),
                           ('fed_rate', 'Fed Funds'), ('recession_prob', 'Prob Recesión')]:
            val = self._q('macro_usa', key)
            if val is not None:
                quant_parts.append(f"{label}: {val}%")
        regime = self._q('regime', 'current')
        if regime:
            quant_parts.append(f"Régimen: {regime}")
        tpm = self._q('chile', 'tpm')
        if tpm is not None:
            quant_parts.append(f"TPM Chile: {tpm}%")
        quant_ctx = " | ".join(quant_parts) if quant_parts else "Datos macro limitados"

        # Generate intro
        intro = generate_data_driven_narrative(
            section_name="macro_conclusions_intro_dd",
            prompt=(
                f"Escribe 2 oraciones de introducción para las conclusiones macro de "
                f"{self.month_name} {self.year}. Resume el panorama macro usando los datos. "
                "Máximo 50 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=400,
        )
        if not intro:
            intro = f"Las conclusiones de {self.month_name} {self.year} reflejan el análisis de las principales variables macro."

        # Generate vistas
        vistas_result = generate_structured_json(
            section_name="macro_conclusions_vistas_dd",
            prompt=(
                "Genera 3-4 vistas macro basadas en los datos. Formato JSON: "
                '[{"tema": "nombre del tema", "vista_grb": "nuestra vista en 1 oración con dato", '
                '"vs_consenso": "ABOVE/BELOW/IN-LINE", "vs_detalle": "1 oración"}]. '
                "Temas: Crecimiento, Inflación, Política Monetaria, Chile (si hay datos). SOLO JSON."
            ),
            context=quant_ctx,
            company_name=self.company_name,
            max_tokens=800,
        )
        if isinstance(vistas_result, list) and len(vistas_result) >= 2:
            vistas = vistas_result
        else:
            vistas = [{'tema': 'Macro', 'vista_grb': f'Datos: {quant_ctx}', 'vs_consenso': 'N/D', 'vs_detalle': 'Análisis basado en datos cuantitativos'}]

        # Generate posicionamiento
        pos = generate_data_driven_narrative(
            section_name="macro_conclusions_pos_dd",
            prompt=(
                "Escribe 1 oración resumiendo el posicionamiento macro general basado en los datos. "
                "Máximo 30 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=200,
        )
        if not pos:
            pos = f"Posicionamiento basado en: {quant_ctx}."

        return {
            'titulo': f'Conclusiones — {self.month_name} {self.year}',
            'intro': intro,
            'vistas': vistas,
            'posicionamiento_resumen': pos,
            'proximo_reporte': 'Este análisis macro sirve como input para los reportes complementarios de Asset Allocation y Renta Fija.'
        }

    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte macro."""
        # Set up anti-fabrication filter with verified macro data
        try:
            from narrative_engine import set_verified_data, clear_verified_data, build_verified_data_macro
            vd = build_verified_data_macro(self.quant, self.data)
            if vd:
                set_verified_data(vd)
        except Exception:
            pass

        content = {
            'metadata': {
                'fecha': self.date.strftime('%Y-%m-%d'),
                'mes': self.month_name,
                'año': self.year,
                'tipo_reporte': 'MACRO'
            },
            'resumen_ejecutivo': self.generate_executive_summary(),
            'pronóstico_ponderado': self.generate_probability_weighted_forecasts(),
            'vs_pronóstico_anterior': self.generate_vs_previous_forecast(),
            'estados_unidos': self.generate_usa_section(),
            'europa': self.generate_europe_section(),
            'china': self.generate_china_section(),
            'chile_latam': self.generate_chile_section(),
            'temas_macro': self.generate_macro_themes(),
            'escenarios_riesgos': self.generate_scenarios_risks(),
            'conclusiones': self.generate_conclusions()
        }

        # Clear anti-fabrication verified data
        try:
            from narrative_engine import clear_verified_data
            clear_verified_data()
        except Exception:
            pass

        return content


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Test del generador."""
    generator = MacroContentGenerator()
    content = generator.generate_all_content()

    import json
    print(json.dumps(content, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

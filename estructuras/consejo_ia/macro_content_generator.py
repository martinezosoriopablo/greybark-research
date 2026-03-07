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
sys.path.insert(0, str(Path(__file__).parent.parent / "02_greybark_library"))


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
            ),
            council_context=council_context,
            company_name=self.company_name,
            max_tokens=1200,
        )
        if result:
            return result

        # Fallback minimal
        return (
            f"El escenario macro global de {self.month_name} {self.year} se caracteriza por "
            f"dinamicas complejas en crecimiento, inflacion y politica monetaria. "
            f"Este reporte detalla nuestro analisis por region y escenarios ponderados por probabilidad."
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
            ),
            council_context=council_context,
            company_name=self.company_name,
            max_tokens=800,
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
                for r in ['USA', 'Euro Area', 'China', 'Chile']
            ],
            'inflation_core': [
                {'region': r, 'actual_2025': 'N/D', 'forecast_2026': 'N/D', 'consenso': 'N/D', 'vs_anterior': 'N/A'}
                for r in ['USA', 'Euro Area', 'Chile']
            ],
            'policy_rates': [
                {'banco': b, 'actual': 'N/D', 'forecast_2026': 'N/D', 'consenso': 'N/D', 'vs_anterior': 'N/A'}
                for b in ['Fed Funds', 'ECB Deposit', 'BCCh TPM']
            ],
        }

    def _generate_forecasts_table_real(self) -> Dict[str, List[Dict]]:
        """Genera tabla de forecasts con datos reales del forecast engine."""

        # GDP Growth
        gdp_rows = []
        gdp_map = [
            ('USA', 'usa'), ('Euro Area', 'eurozone'), ('China', 'china'), ('Chile', 'chile'),
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
            ('USA', 'usa'), ('Euro Area', 'eurozone'), ('Chile', 'chile'),
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
            ('Fed Funds', 'fed_funds'), ('ECB Deposit', 'ecb'), ('BCCh TPM', 'tpm_chile'),
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

            # GDP USA: use forecast engine if available, otherwise N/D
            gdp_val = gdp_us_fc if gdp_us_fc is not None else None
            gdp_display = f'{gdp_val:.1f}%' if gdp_val is not None else 'N/D'

            # GDP World: use IMF consensus or forecast engine, otherwise N/D
            gdp_world_val = gdp_world_fc if gdp_world_fc is not None else None
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
                f"El pronóstico ponderado de GDP USA es {gdp_w:.1f}%. El S&P 500 ponderado de "
                f"{sp_w:,.0f} implica un retorno de "
                f"{((sp_w / sp_current - 1) * 100):.1f}% desde niveles actuales."
            )
        elif weighted_forecasts.get('gdp_us'):
            implicancia = f"El pronóstico ponderado de GDP USA es {sum(weighted_gdp_parts):.1f}%."
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
            for region, label in [('usa', 'GDP USA'), ('china', 'GDP China'), ('chile', 'GDP Chile')]:
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
            for rate, label in [('fed_funds', 'Fed Funds YE'), ('tpm_chile', 'TPM Chile YE')]:
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
                    'variable': 'CPI Core USA',
                    'anterior': f'{prev_infl:.1f}%',
                    'actual': f'{curr_infl:.1f}%',
                    'cambio': f'{diff:+.1f}pp',
                    'razon': 'Actualización del Forecast Engine',
                })

        # Fallback if no comparison possible
        if not cambios:
            cambios = [
                {'variable': 'GDP USA 2026', 'anterior': 'N/D', 'actual': self._fc_pct('gdp_forecasts', 'usa', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
                {'variable': 'Fed Funds YE', 'anterior': 'N/D', 'actual': self._fc_pct('rate_forecasts', 'fed_funds', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
                {'variable': 'CPI Core USA', 'anterior': 'N/D', 'actual': self._fc_pct('inflation_forecasts', 'usa', 'forecast_12m'), 'cambio': 'N/A', 'razon': 'Primera ejecución del Forecast Engine'},
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

        from narrative_engine import generate_narrative
        quant_ctx = f"GDP QoQ anualizado: {gdp_val}. Mfg New Orders: {no_val}. Housing Starts: {hs_val}. Consumer Confidence: {cc_val}."
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1500]
        narrativa = generate_narrative(
            section_name="usa_growth",
            prompt=(
                "Describe el estado del crecimiento de EE.UU. en 2-3 oraciones basandote SOLO en los datos proporcionados. "
                "NO asumas direccion (solido/debil) — deduce del GDP y leading indicators. Maximo 80 palabras."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=250,
        ) or f"GDP EE.UU.: {gdp_val}. Mfg New Orders: {no_val}. Housing Starts: {hs_val}. Consumer Confidence: {cc_val}."

        return {
            'titulo': 'Crecimiento Económico',
            'narrativa': narrativa,
            'drivers': [],
            'leading_indicators': [
                {'indicador': 'Mfg New Orders', 'valor': no_val, 'tendencia': '-'},
                {'indicador': 'Housing Starts', 'valor': hs_val, 'tendencia': '-'},
                {'indicador': 'Consumer Confidence', 'valor': cc_val, 'tendencia': '-'},
            ]
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
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=250,
        ) or f"NFP: {nfp_str}. Desempleo U3: {u3_str}. AHE: {ahe_str}."

        narrativa_jolts = generate_narrative(
            section_name="usa_jolts",
            prompt=(
                "Describe JOLTS en 1-2 oraciones con los datos proporcionados. NO asumas direccion. Maximo 40 palabras."
            ),
            council_context="", quant_context=f"Job Openings: {jo_str} (prev {jo_prev_str}). Quits Rate: {qr_str} (prev {qr_prev_str}).",
            company_name=self.company_name, max_tokens=150,
        ) or f"Job Openings: {jo_str}. Quits Rate: {qr_str}."

        narrativa_salarios = generate_narrative(
            section_name="usa_wages",
            prompt=(
                "Describe presiones salariales en 1-2 oraciones con los datos. NO inventes umbrales ni estimaciones. Maximo 40 palabras."
            ),
            council_context="", quant_context=f"AHE YoY: {ahe_str} (prev {ahe_prev_str}).",
            company_name=self.company_name, max_tokens=150,
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
                {'indicador': 'Non-Farm Payrolls', 'valor': nfp_str, 'anterior': nfp_prev_str, 'tendencia': _trend(nfp, nfp_prev)},
                {'indicador': 'Tasa Desempleo (U3)', 'valor': u3_str, 'anterior': u3_prev_str, 'tendencia': _trend(d.get('unemployment'), d.get('unemployment_prev'))},
                {'indicador': 'Desempleo Amplio (U6)', 'valor': u6_str, 'anterior': u6_prev_str, 'tendencia': _trend(d.get('u6'), d.get('u6_prev'))},
                {'indicador': 'Participación Laboral', 'valor': lfpr_str, 'anterior': lfpr_prev_str, 'tendencia': _trend(d.get('lfpr'), d.get('lfpr_prev'))},
                {'indicador': 'Participación Prime-Age', 'valor': prime_str, 'anterior': prime_prev_str, 'tendencia': _trend(d.get('prime_age'), d.get('prime_age_prev'))},
                {'indicador': 'Initial Claims', 'valor': ic_str, 'anterior': ic_prev_str, 'tendencia': _trend(ic_raw, ic_prev)},
                {'indicador': 'Continuing Claims', 'valor': cc_str, 'anterior': cc_prev_str, 'tendencia': _trend(cc_raw, cc_prev)},
            ],
            'jolts': [
                {'indicador': 'Job Openings', 'valor': jo_str, 'anterior': jo_prev_str, 'tendencia': _trend(jo_raw, jo_prev)},
                {'indicador': 'Quits Rate', 'valor': qr_str, 'anterior': qr_prev_str, 'tendencia': _trend(d.get('quits_rate'), d.get('quits_rate_prev'))},
            ],
            'salarios': [
                {'indicador': 'AHE (Avg Hourly Earnings)', 'valor': ahe_str, 'anterior': ahe_prev_str, 'tendencia': _trend(d.get('ahe_yoy'), d.get('ahe_yoy_prev'))},
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
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=250,
        ) or f"CPI Headline: {cpi_h_yoy}. CPI Core: {cpi_c_yoy}. PCE Core: {pce_c_yoy}."

        return {
            'titulo': 'Inflación',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'CPI Headline', 'valor': cpi_h_yoy, 'anterior': 'N/D', 'mom': cpi_h_mom_str},
                {'indicador': 'CPI Core', 'valor': cpi_c_yoy, 'anterior': 'N/D', 'mom': cpi_c_mom_str},
                {'indicador': 'PCE Core', 'valor': pce_c_yoy, 'anterior': 'N/D', 'mom': pce_c_mom_str},
            ],
            'componentes': self._build_cpi_components(),
            'expectativas': [
                {'medida': 'UMich Sentiment', 'valor': umich, 'comentario': 'Datos FRED'},
                {'medida': 'SPF 10yr', 'valor': 'N/D', 'comentario': '-'},
            ]
        }

    def _build_cpi_components(self) -> List[Dict]:
        """Build CPI components from FRED data."""
        if not self.data:
            return [{'componente': c, 'valor': 'N/D', 'tendencia': '-'} for c in
                    ['Shelter', 'Services ex-Energy', 'Core Goods', 'Food', 'Energy']]
        try:
            comp = self.data.get_usa_cpi_components()
        except Exception:
            comp = {}
        mapping = [
            ('Shelter', 'shelter'),
            ('Services ex-Energy', 'services_ex_energy'),
            ('Core Goods', 'goods_ex_food_energy'),
            ('Food', 'food'),
            ('Energy', 'energy'),
        ]
        result = []
        for label, key in mapping:
            val = comp.get(key)
            val_str = f"{val:.1f}% a/a" if val is not None else 'N/D'
            result.append({'componente': label, 'valor': val_str, 'tendencia': '-'})
        return result

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
                'neutral_estimada': 'N/D',
                'real_actual': real_str,
                'proyección_2026': self._fc_pct('rate_forecasts', 'fed_funds', 'forecast_12m'),
                'mercado_implica': 'N/D',
            },
            'dot_plot': dot_plot,
            'taylor_rule': self._build_taylor_rule(ff),
            'riesgos': [
                'Reaceleración de inflación servicios forzaria pausa prolongada',
                'Debilidad inesperada en empleo aceleraria recortes',
                'Incertidumbre geopolítica y política comercial'
            ],
            'proximas_reuniones': self._build_fed_meetings()
        }

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

        return {
            'titulo': 'Política Fiscal',
            'narrativa': (
                f"El déficit fiscal se ubica en {deficit_str}. "
                f"La deuda publica se situa en {debt_str}. "
                f"Los costos de servicio de deuda representan {interest_str}."
            ),
            'datos': [
                {'indicador': 'Déficit Fiscal', 'valor': deficit_str, 'anterior': 'N/D'},
                {'indicador': 'Deuda Publica', 'valor': debt_str, 'anterior': 'N/D'},
                {'indicador': 'Costo Deuda', 'valor': interest_str, 'anterior': 'N/D'},
            ],
            'riesgos': [
                'Politica fiscal expansiva podria ampliar déficit',
                'Gasto en defensa creciente por tensiones geopolíticas',
            ]
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
            'titulo': f'Crecimiento - Euro Area{src}',
            'narrativa': (
                f"La economía europea muestra recuperación gradual. "
                f"El ultimo GDP trimestral Eurozona: {gdp_ez}. "
                f"Alemania: {gdp_de}, Francia: {gdp_fr}, UK: {gdp_uk}. "
                f"Desempleo Eurozona: {desemp}. "
                f"El sector manufacturero comienza a estabilizarse mientras servicios "
                f"mantiene expansión moderada."
            ),
            'por_pais': [
                {'pais': 'Euro Area', 'gdp_2025': gdp_ez, 'gdp_2026f': self._fc_pct('gdp_forecasts', 'eurozone', 'forecast_12m'), 'consenso': 'N/D'},
                {'pais': 'Alemania', 'gdp_2025': gdp_de, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
                {'pais': 'Francia', 'gdp_2025': gdp_fr, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
                {'pais': 'UK', 'gdp_2025': gdp_uk, 'gdp_2026f': 'N/D', 'consenso': 'N/D'},
            ],
            'indicadores': [
                {'indicador': 'Desempleo Eurozona', 'valor': desemp, 'comentario': 'BCCh' if has_real else 'Estimado'},
                {'indicador': 'PMI Manufacturing', 'valor': self._get_bloomberg_pmi('euro_mfg'), 'comentario': 'Bloomberg'},
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
            'titulo': f'Inflación - Euro Area{src}',
            'narrativa': (
                f"La inflación europea se ubica con HICP headline en {cpi_val}, "
                f"mientras el core converge a {core_val}. "
                f"PPI Eurozona: {ppi_val}. "
                f"Los salarios negociados se han moderado. La inflación de servicios "
                f"cede, permitiendo al BCE mantener tasas estables cerca de neutral."
            ),
            'datos': [
                {'indicador': 'HICP Headline', 'valor': cpi_val, 'anterior': '-'},
                {'indicador': 'HICP Core', 'valor': core_val, 'anterior': '-'},
                {'indicador': 'PPI Eurozona', 'valor': ppi_val, 'anterior': '-'},
                {'indicador': 'Salarios Negociados', 'valor': 'N/D', 'anterior': 'N/D'},
            ]
        }

    def _generate_ecb_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria BCE."""
        eu = self._get_europe_latest()

        ecb_rate = self._fmt(eu.get('ecb_rate'), decimals=2)
        bund_10y = self._fmt(eu.get('bund_10y'), decimals=2)

        has_real = bool(eu.get('ecb_rate') is not None)
        src = ' (datos BCCh)' if has_real else ''

        from narrative_engine import generate_narrative
        quant_ctx = f"ECB Deposit Rate: {ecb_rate}. Bund 10Y: {bund_10y}."
        council_ctx = self.council.get('panel_outputs', {}).get('macro', '')[:1000]
        narrativa = generate_narrative(
            section_name="ecb_policy",
            prompt=(
                "Describe la politica monetaria del BCE en 2-3 oraciones basandote SOLO en los datos. "
                "NO proyectes recortes ni movimientos futuros — eso viene del council. Maximo 60 palabras."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=200,
        ) or f"ECB Deposit Rate: {ecb_rate}. Bund 10Y: {bund_10y}."

        return {
            'titulo': f'Política Monetaria - BCE{src}',
            'narrativa': narrativa,
            'tasas': {
                'deposito_actual': ecb_rate,
                'refi_actual': bund_10y,
                'proyección_2026': self._fc_pct('rate_forecasts', 'ecb', 'forecast_12m'),
                'neutral_estimada': 'N/D',
            },
            'próximos_movimientos': [],
            'balance_riesgos': {
                'dovish': 'N/D — ver council',
                'hawkish': 'N/D — ver council'
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
            ),
            council_context=council_ctx, quant_context="",
            company_name=self.company_name, max_tokens=400,
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
            'riesgos': riesgos if riesgos else [{'nombre': 'N/D', 'descripcion': 'Ver council para riesgos Europa.', 'probabilidad': '-', 'impacto': '-'}]
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
        cpi_val = self._fmt(cn.get('cpi'))
        desemp_val = self._fmt(cn.get('unemployment'))

        has_real = bool(cn.get('gdp_qoq') is not None)
        src = ' (datos BCCh)' if has_real else ''

        from narrative_engine import generate_narrative
        quant_ctx = f"China GDP QoQ: {gdp_val}. CPI: {cpi_val}. Desempleo urbano: {desemp_val}."
        council_ctx = self.council.get('panel_outputs', {}).get('geo', '')[:1000]
        narrativa = generate_narrative(
            section_name="china_growth",
            prompt=(
                "Describe el crecimiento de China en 2-3 oraciones basandote SOLO en datos. "
                "NO asumas direccion del property sector ni exportaciones sin datos. Maximo 60 palabras."
            ),
            council_context=council_ctx, quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=200,
        ) or f"China GDP: {gdp_val}. CPI: {cpi_val}. Desempleo: {desemp_val}."

        return {
            'titulo': f'Crecimiento{src}',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'GDP ultimo trimestre', 'valor': gdp_val, 'anterior': 'BCCh' if has_real else 'Estimado'},
                {'indicador': 'CPI YoY', 'valor': cpi_val, 'anterior': 'BCCh' if cn.get('cpi') is not None else 'Estimado'},
                {'indicador': 'Desempleo Urbano', 'valor': desemp_val, 'anterior': 'BCCh' if cn.get('unemployment') is not None else 'Estimado'},
            ],
            'indicadores': [
                {'indicador': 'PMI Manufacturing', 'valor': self._get_bloomberg_pmi('china_mfg'), 'comentario': 'Bloomberg'},
                {'indicador': 'PMI Services', 'valor': self._get_bloomberg_pmi('china_svc'), 'comentario': 'Bloomberg'},
            ]
        }

    def _generate_china_property(self) -> Dict[str, Any]:
        """Genera seccion de sector inmobiliario China."""
        prop_sales = self._bbg_val('china_property_sales_yoy')
        prop_prev = self._bbg_prev('china_property_sales_yoy')

        has_bbg = prop_sales != 'N/D'
        if has_bbg:
            from narrative_engine import generate_narrative
            narrativa = generate_narrative(
                section_name="china_property",
                prompt="Describe el sector inmobiliario de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras.",
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context=f"Property Sales YoY: {prop_sales}%.",
                company_name=self.company_name, max_tokens=150,
            ) or f"Ventas de propiedades residenciales YoY: {prop_sales}%."
        else:
            narrativa = "Datos de sector inmobiliario no disponibles."

        return {
            'titulo': 'Sector Inmobiliario',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Property Sales YoY', 'valor': prop_sales, 'anterior': prop_prev},
                {'indicador': 'Housing Starts', 'valor': 'N/D', 'anterior': 'N/D'},
                {'indicador': 'Home Prices (Tier 1)', 'valor': 'N/D', 'anterior': 'N/D'},
                {'indicador': 'Developer Funding', 'valor': 'N/D', 'anterior': 'N/D'},
            ],
            'políticas_soporte': [],
            'drag_estimado': {}
        }

    def _generate_china_credit(self) -> Dict[str, Any]:
        """Genera seccion de impulso crediticio China."""
        tsf = self._bbg_val('china_tsf_yoy')
        tsf_prev = self._bbg_prev('china_tsf_yoy')
        new_loans = self._bbg_val('china_new_loans', 0)
        new_loans_prev = self._bbg_prev('china_new_loans', 0)
        m2 = self._bbg_val('china_m2_yoy')
        m2_prev = self._bbg_prev('china_m2_yoy')

        has_bbg = tsf != 'N/D' or m2 != 'N/D'
        if has_bbg:
            parts = []
            if tsf != 'N/D':
                parts.append(f"TSF: {tsf}% YoY")
            if m2 != 'N/D':
                parts.append(f"M2: {m2}% YoY")
            from narrative_engine import generate_narrative
            narrativa = generate_narrative(
                section_name="china_credit",
                prompt="Describe el impulso crediticio de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras.",
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context=', '.join(parts),
                company_name=self.company_name, max_tokens=150,
            ) or f"Impulso crediticio China: {', '.join(parts)}."
        else:
            narrativa = "Datos de impulso crediticio chino no disponibles."

        return {
            'titulo': 'Impulso Crediticio',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'TSF Growth YoY', 'valor': tsf, 'anterior': tsf_prev},
                {'indicador': 'New Yuan Loans', 'valor': new_loans, 'anterior': new_loans_prev},
                {'indicador': 'Credit Impulse', 'valor': 'N/D', 'anterior': 'N/D'},
                {'indicador': 'M2 Growth YoY', 'valor': m2, 'anterior': m2_prev},
            ],
            'implicancias_globales': (
                "El credit impulse positivo en China históricamente precede mejor demanda "
                "de commodities y crecimiento global con lag de 6-9 meses."
            )
        }

    def _generate_china_trade(self) -> Dict[str, Any]:
        """Genera seccion de comercio exterior China."""
        trade_bal = self._bbg_val('china_trade_bal', 1)
        trade_prev = self._bbg_prev('china_trade_bal', 1)
        exp_yoy = self._bbg_val('china_exp_yoy')
        exp_prev = self._bbg_prev('china_exp_yoy')
        imp_yoy = self._bbg_val('china_imp_yoy')
        imp_prev = self._bbg_prev('china_imp_yoy')

        has_bbg = exp_yoy != 'N/D' or trade_bal != 'N/D'
        if has_bbg:
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
                prompt="Describe el comercio exterior de China en 1-2 oraciones con los datos. NO asumas direccion. Maximo 40 palabras.",
                council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
                quant_context=', '.join(parts),
                company_name=self.company_name, max_tokens=150,
            ) or f"Comercio exterior China: {', '.join(parts)}."
        else:
            narrativa = "Datos de comercio exterior chino no disponibles."

        return {
            'titulo': 'Comercio Exterior',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Trade Balance', 'valor': trade_bal, 'anterior': trade_prev},
                {'indicador': 'Exports YoY', 'valor': exp_yoy, 'anterior': exp_prev},
                {'indicador': 'Imports YoY', 'valor': imp_yoy, 'anterior': imp_prev},
            ],
            'implicancias_commodities': ['N/D — ver council para implicancias commodities']
        }

    def _generate_pboc_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria PBOC."""
        cn = self._get_china_latest()

        pboc_rate = self._fmt(cn.get('pboc_rate'), decimals=2)
        cny_val = f"{cn['cny_usd']:.2f}" if cn.get('cny_usd') is not None else 'N/D'
        shanghai = f"{cn['shanghai']:.0f}" if cn.get('shanghai') is not None else 'N/D'

        has_real = bool(cn.get('pboc_rate') is not None)
        src = ' (datos BCCh)' if has_real else ''

        from narrative_engine import generate_narrative
        quant_ctx = f"PBOC Rate: {pboc_rate}. CNY/USD: {cny_val}. Shanghai Composite: {shanghai}."
        narrativa = generate_narrative(
            section_name="pboc_policy",
            prompt=(
                "Describe la politica monetaria del PBOC en 1-2 oraciones con los datos. "
                "NO proyectes movimientos futuros — eso viene del council. Maximo 40 palabras."
            ),
            council_context=self.council.get('panel_outputs', {}).get('geo', '')[:500],
            quant_context=quant_ctx,
            company_name=self.company_name, max_tokens=150,
        ) or f"PBOC Rate: {pboc_rate}. CNY/USD: {cny_val}. Shanghai: {shanghai}."

        return {
            'titulo': f'Política Monetaria - PBOC{src}',
            'narrativa': narrativa,
            'tasas': {
                'pboc_rate': pboc_rate,
                'lpr_1y': 'N/D',
                'lpr_5y': 'N/D',
                'rrr': 'N/D',
                'yuan_usdcny': cny_val,
            },
            'outlook': {
                'tasas': 'N/D — ver council',
                'rrr': 'N/D — ver council',
                'yuan': 'N/D — ver council'
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

        narrativa = (
            f"La economía chilena consolida su recuperación. "
            f"El IMACEC muestra expansión de {imacec_str}, "
            f"con servicios y mineria como drivers. "
            f"El consumo privado mantiene dinamismo apoyado por salarios reales positivos. "
            f"La tasa de desempleo se ubica en {desemp_str}. "
            f"Proyección de GDP para 2026: {self._fc_pct('gdp_forecasts', 'chile', 'forecast_12m')}."
        )

        return {
            'titulo': 'Chile - Crecimiento',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'IMACEC', 'valor': imacec_str, 'anterior': 'N/D', 'tendencia': '-'},
                {'indicador': 'GDP Trim (t/t-4)', 'valor': 'N/D', 'anterior': 'N/D', 'tendencia': '-'},
                {'indicador': 'Consumo Privado', 'valor': 'N/D', 'anterior': 'N/D', 'tendencia': '-'},
                {'indicador': 'Inversion (FBCF)', 'valor': 'N/D', 'anterior': 'N/D', 'tendencia': '-'},
            ],
            'mercado_laboral': [
                {'indicador': 'Tasa Desempleo', 'valor': desemp_str, 'anterior': 'N/D'},
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
                {'indicador': 'IPC Headline', 'valor': ipc_yoy_str, 'anterior': 'N/D', 'mom': ipc_mom_str},
                {'indicador': 'IPC Subyacente (SAE)', 'valor': 'N/D', 'anterior': 'N/D', 'mom': 'N/D'},
            ],
            'expectativas': [
                {'medida': 'EEE 1 año', 'valor': 'N/D', 'anterior': 'N/D'},
                {'medida': 'EEE 2 años', 'valor': 'N/D', 'anterior': 'N/D'},
            ]
        }

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
                'tpm_neutral': 'N/D',
                'tpm_real': tpm_real_str,
                'proyección_2026': self._fc_pct('rate_forecasts', 'tpm_chile', 'forecast_12m'),
                'consenso_2026': 'N/D',
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
        if self.data:
            try:
                comm = self.data.get_commodities()
                cobre_series = comm.get('cobre')
                if cobre_series is not None and len(cobre_series) > 0:
                    copper_price = float(cobre_series.iloc[-1])  # BCCh returns USD/lb directly
            except Exception:
                pass
        copper_str = f'${copper_price:.2f}/lb' if copper_price else 'N/D'

        # Get litio and brent from BCCh if available
        litio_str = 'N/D'
        brent_str = 'N/D'
        if self.data:
            try:
                comm = self.data.get_commodities()
                litio_series = comm.get('litio')
                if litio_series is not None and len(litio_series) > 0:
                    litio_val = float(litio_series.iloc[-1])
                    litio_str = f'${litio_val:,.0f}/ton'
                brent_series = comm.get('petroleo')
                if brent_series is not None and len(brent_series) > 0:
                    brent_val = float(brent_series.iloc[-1])
                    brent_str = f'${brent_val:.1f}/bbl'
            except Exception:
                pass

        return {
            'titulo': 'Commodities Relevantes',
            'commodities': [
                {
                    'nombre': 'Cobre',
                    'precio_actual': copper_str,
                    'precio_anterior': 'N/D',
                    'cambio': 'N/D',
                    'outlook': 'N/D — ver council',
                    'balance': 'N/D — ver council',
                    'drivers': 'N/D — ver council',
                    'inventarios': {},
                    'supply': {},
                    'breakeven_costs': {},
                },
                {
                    'nombre': 'Litio',
                    'precio_actual': litio_str,
                    'precio_anterior': 'N/D',
                    'cambio': 'N/D',
                    'outlook': 'N/D — ver council',
                    'balance': 'N/D — ver council',
                    'drivers': 'N/D — ver council',
                    'inventarios': {},
                    'supply': {},
                    'breakeven_costs': {},
                },
                {
                    'nombre': 'Petróleo (Brent)',
                    'precio_actual': brent_str,
                    'precio_anterior': 'N/D',
                    'cambio': 'N/D',
                    'outlook': 'N/D — ver council',
                    'balance': 'N/D — ver council',
                    'drivers': 'N/D — ver council',
                    'inventarios': {},
                    'breakeven_costs': {},
                }
            ],
            'transmisión_global': {},  # No free data for fiscal sensitivity analysis
            'impacto_fiscal': {},  # No free data for fiscal impact estimates
        }

    def _generate_latam_context(self) -> Dict[str, Any]:
        """Genera contexto de LatAm."""
        return {
            'titulo': 'Contexto LatAm',
            'paises': self._build_latam_table(),
            'diferenciacion_chile': 'N/D — ver council para diferenciacion Chile vs LatAm.'
        }

    def _build_latam_table(self) -> List[Dict]:
        """Build LatAm macro table from BCCh data."""
        if not self.data:
            return [{'pais': p, 'gdp': 'N/D', 'inflación': 'N/D', 'tasa': 'N/D', 'outlook': '-', 'riesgo_principal': '-'}
                    for p in ['Brasil', 'Mexico', 'Colombia']]
        try:
            latam = self.data.get_latam_macro()
        except Exception:
            latam = {}
        result = []
        names = {'Brasil': 'Selic', 'Mexico': 'Banxico', 'Colombia': 'BanRep', 'Peru': 'BCRP'}
        for country, rate_name in names.items():
            d = latam.get(country, {})
            cpi = d.get('cpi')
            tasa = d.get('tasa')
            result.append({
                'pais': country,
                'gdp': 'N/D',
                'inflación': f"{cpi:.1f}%" if cpi is not None else 'N/D',
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
                f"Genera un calendario de 4-6 eventos macro clave para el proximo mes ({self.month_name} {self.year}). "
                "Formato JSON: [{\"fecha\": \"DD Mon\", \"evento\": \"...\", \"relevancia\": \"Alta/Media\", \"impacto_potencial\": \"...\"}]. "
                "Incluye: FOMC/Fed, ECB, BCCh, datos de inflacion y PIB relevantes. "
                "Las fechas deben ser aproximadas para el mes indicado. Devuelve SOLO el JSON."
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
            result.append({
                'nombre': data.get('name', key),
                'probabilidad': data.get('prob', 'N/D'),
                'descripcion': data.get('description', 'Sin descripción'),
                'implicancias': {
                    'gdp_us': 'N/D',
                    'inflación_us': 'N/D',
                    'fed_funds': 'N/D',
                    'sp500': 'N/D',
                },
                'triggers': []
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
                'monitoreo': r.get('risk', ''),
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
            max_tokens=200,
        )
        if not intro:
            intro = (
                f"Las conclusiones de {self.month_name} {self.year} reflejan nuestro analisis "
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
                {'tema': 'Panorama General', 'vista_grb': 'Ver seccion de analisis para detalle.',
                 'vs_consenso': 'Ver detalle', 'vs_detalle': 'Analisis completo en secciones anteriores.'}
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
            max_tokens=300,
        )
        if not pos_resumen:
            pos_resumen = 'N/D — narrative engine no genero posicionamiento.'

        return {
            'titulo': f'Conclusiones — {self.month_name} {self.year}',
            'intro': intro,
            'vistas': vistas,
            'posicionamiento_resumen': pos_resumen,
            'proximo_reporte': (
                'Este analisis macro sirve como input para los reportes complementarios de '
                'Asset Allocation y Renta Fija.'
            )
        }

    def _build_default_conclusions(self) -> Dict[str, Any]:
        """Conclusiones fallback sin council output."""
        return {
            'titulo': 'Conclusiones',
            'intro': (
                f"Las conclusiones de {self.month_name} {self.year} reflejan nuestro analisis "
                f"integrado de las principales variables macro."
            ),
            'vistas': [
                {
                    'tema': 'N/D',
                    'vista_grb': 'N/D — council session requerida.',
                    'vs_consenso': 'N/D',
                    'vs_detalle': 'N/D'
                },
            ],
            'posicionamiento_resumen': 'N/D — ver council para posicionamiento.',
            'proximo_reporte': 'Este analisis sirve como input para reportes de Asset Allocation y Renta Fija.'
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

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
            return {'view': 'NEUTRAL'}

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
            return [
                "Crecimiento global con dinamicas mixtas entre regiones desarrolladas y emergentes",
                "Inflacion convergiendo gradualmente en economias desarrolladas, servicios con inercia",
                "Bancos centrales en modo de evaluacion; proximos movimientos dependen de datos",
                "Chile con fundamentos solidos; cobre como soporte a cuentas externas",
            ]

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

        return [
            "Dinamicas macro complejas requieren posicionamiento selectivo",
            "Politica monetaria en evaluacion; datos proximos seran determinantes",
            "Chile con fundamentos diferenciados positivamente en la region",
        ]

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

        # Hardcoded fallback
        return self._generate_forecasts_table_hardcoded()

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

    def _generate_forecasts_table_hardcoded(self) -> Dict[str, List[Dict]]:
        """Fallback: tabla de forecasts 100% hardcodeada."""
        return {
            'gdp_growth': [
                {'region': 'World', 'actual_2025': '2.8%', 'forecast_2026': '2.9%', 'consenso': '2.7%', 'vs_anterior': '+0.1'},
                {'region': 'USA', 'actual_2025': '2.4%', 'forecast_2026': '2.2%', 'consenso': '2.0%', 'vs_anterior': '='},
                {'region': 'Euro Area', 'actual_2025': '1.2%', 'forecast_2026': '1.4%', 'consenso': '1.2%', 'vs_anterior': '+0.2'},
                {'region': 'China', 'actual_2025': '4.8%', 'forecast_2026': '4.5%', 'consenso': '4.3%', 'vs_anterior': '='},
                {'region': 'Chile', 'actual_2025': '2.3%', 'forecast_2026': '2.5%', 'consenso': '2.2%', 'vs_anterior': '+0.3'},
            ],
            'inflation_core': [
                {'region': 'USA', 'actual_2025': '2.6%', 'forecast_2026': '2.3%', 'consenso': '2.4%', 'vs_anterior': '-0.1'},
                {'region': 'Euro Area', 'actual_2025': '2.3%', 'forecast_2026': '2.0%', 'consenso': '2.1%', 'vs_anterior': '='},
                {'region': 'Chile', 'actual_2025': '3.2%', 'forecast_2026': '3.0%', 'consenso': '3.1%', 'vs_anterior': '='},
            ],
            'policy_rates': [
                {'banco': 'Fed Funds', 'actual': '3.75%', 'forecast_2026': '3.50%', 'consenso': '3.50%', 'vs_anterior': '='},
                {'banco': 'ECB Deposit', 'actual': '2.25%', 'forecast_2026': '2.00%', 'consenso': '2.00%', 'vs_anterior': '='},
                {'banco': 'BCCh TPM', 'actual': '4.50%', 'forecast_2026': '4.25%', 'consenso': '4.25%', 'vs_anterior': '='},
            ]
        }

    def generate_probability_weighted_forecasts(self) -> Dict[str, Any]:
        """Genera pronósticos ponderados por probabilidad de escenarios.
        Uses equity targets from forecast engine if available."""

        # Get S&P 500 target from forecast engine
        sp500_target = self._fc('equity_targets', 'sp500', 'target_12m')
        sp500_current = self._fc('equity_targets', 'sp500', 'current_price')
        gdp_us_fc = self._fc('gdp_forecasts', 'usa', 'forecast_12m')

        # Scenario S&P targets centered on engine forecast
        if sp500_target and sp500_current:
            base = sp500_target
            # Bull = +8% above target, Bear = -15% from current
            bull_sp = round(sp500_current * 1.15)
            bear_sp = round(sp500_current * 0.85)
        else:
            base = 5800
            bull_sp = 6200
            bear_sp = 4800

        base_gdp = gdp_us_fc if gdp_us_fc else 2.2

        scenarios = {
            'soft_landing': {'prob': 0.55, 'gdp_us': base_gdp, 'gdp_world': 2.9, 'sp500': base},
            'no_landing': {'prob': 0.20, 'gdp_us': base_gdp + 0.6, 'gdp_world': 3.3, 'sp500': bull_sp},
            'hard_landing': {'prob': 0.25, 'gdp_us': 0.5, 'gdp_world': 2.0, 'sp500': bear_sp}
        }

        gdp_us_weighted = sum(s['prob'] * s['gdp_us'] for s in scenarios.values())
        gdp_world_weighted = sum(s['prob'] * s['gdp_world'] for s in scenarios.values())
        sp500_weighted = sum(s['prob'] * s['sp500'] for s in scenarios.values())

        return {
            'titulo': 'Pronóstico Ponderado por Escenarios',
            'metodologia': 'Weighted Average = Σ(Probabilidad_i × Pronóstico_i)',
            'escenarios': [
                {'nombre': 'Soft Landing', 'probabilidad': '55%',
                 'gdp_us': f'{scenarios["soft_landing"]["gdp_us"]:.1f}%', 'gdp_world': '2.9%',
                 'sp500': f'{scenarios["soft_landing"]["sp500"]:,.0f}'},
                {'nombre': 'No Landing', 'probabilidad': '20%',
                 'gdp_us': f'{scenarios["no_landing"]["gdp_us"]:.1f}%', 'gdp_world': '3.3%',
                 'sp500': f'{scenarios["no_landing"]["sp500"]:,.0f}'},
                {'nombre': 'Hard Landing', 'probabilidad': '25%',
                 'gdp_us': '0.5%', 'gdp_world': '2.0%',
                 'sp500': f'{scenarios["hard_landing"]["sp500"]:,.0f}'},
            ],
            'weighted_forecasts': {
                'gdp_us': f'{gdp_us_weighted:.1f}%',
                'gdp_world': f'{gdp_world_weighted:.1f}%',
                'sp500': f'{sp500_weighted:,.0f}',
                'formula_example': f'GDP US = (0.55×{base_gdp:.1f}) + (0.20×{base_gdp+0.6:.1f}) + (0.25×0.5) = {gdp_us_weighted:.1f}%'
            },
            'implicancia': (
                f"El pronóstico ponderado de GDP USA es {gdp_us_weighted:.1f}%, reflejando el peso "
                f"significativo del escenario de hard landing (25%). El S&P 500 ponderado de "
                f"{sp500_weighted:,.0f} implica un retorno de "
                f"{((sp500_weighted / sp500_current - 1) * 100):.1f}% desde niveles actuales."
                if sp500_current else
                f"El pronóstico ponderado de GDP USA es {gdp_us_weighted:.1f}%."
            )
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

        return {
            'titulo': 'Crecimiento Económico',
            'narrativa': (
                f"El crecimiento de EE.UU. se mantiene solido, con el GDP "
                f"expandiendose a una tasa anualizada de {gdp_val} en el ultimo trimestre. "
                f"El consumo privado sigue siendo el principal motor, soportado por un mercado laboral "
                f"equilibrado y ganancias reales de salarios. La inversion empresarial se recupera "
                f"con impulso del sector tech/AI."
            ),
            'drivers': [
                {'componente': 'Consumo Privado', 'contribución': '+1.8pp', 'tendencia': 'Solido'},
                {'componente': 'Inversion Fija', 'contribución': '+0.4pp', 'tendencia': 'Mixto'},
                {'componente': 'Gobierno', 'contribución': '+0.3pp', 'tendencia': 'Estable'},
                {'componente': 'Net Exports', 'contribución': '-0.2pp', 'tendencia': 'Drag'},
                {'componente': 'Inventarios', 'contribución': '+0.5pp', 'tendencia': 'Volatil'},
            ],
            'leading_indicators': [
                {'indicador': 'Mfg New Orders', 'valor': no_val, 'tendencia': 'Leading'},
                {'indicador': 'Housing Starts', 'valor': hs_val, 'tendencia': 'Recuperando'},
                {'indicador': 'Consumer Confidence', 'valor': cc_val, 'tendencia': 'Estable'},
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

        return {
            'titulo': 'Mercado Laboral',
            'narrativa': (
                f"El mercado laboral mantiene su fortaleza aunque con señales de normalización gradual. "
                f"La creacion de empleo (NFP) se situa en {nfp_str} mensual. "
                f"La tasa de desempleo se mantiene en {u3_str}, "
                f"ligeramente por encima del NAIRU estimado de 4.0%. Las presiones salariales se "
                f"moderan con el AHE en {ahe_str}."
            ),
            'datos': [
                {'indicador': 'Non-Farm Payrolls', 'valor': nfp_str, 'anterior': nfp_prev_str, 'tendencia': 'Moderando'},
                {'indicador': 'Tasa Desempleo (U3)', 'valor': u3_str, 'anterior': u3_prev_str, 'tendencia': 'Estable'},
                {'indicador': 'Desempleo Amplio (U6)', 'valor': u6_str, 'anterior': u6_prev_str, 'tendencia': 'Estable'},
                {'indicador': 'Participación Laboral', 'valor': lfpr_str, 'anterior': lfpr_prev_str, 'tendencia': 'Estable'},
                {'indicador': 'Participación Prime-Age', 'valor': prime_str, 'anterior': prime_prev_str, 'tendencia': 'Recuperando'},
                {'indicador': 'Initial Claims', 'valor': ic_str, 'anterior': ic_prev_str, 'tendencia': 'Bajas'},
                {'indicador': 'Continuing Claims', 'valor': cc_str, 'anterior': cc_prev_str, 'tendencia': 'Estable'},
            ],
            'jolts': [
                {'indicador': 'Job Openings', 'valor': jo_str, 'anterior': jo_prev_str, 'tendencia': 'Normalizando'},
                {'indicador': 'Quits Rate', 'valor': qr_str, 'anterior': qr_prev_str, 'tendencia': 'Estable'},
            ],
            'salarios': [
                {'indicador': 'AHE (Avg Hourly Earnings)', 'valor': ahe_str, 'anterior': ahe_prev_str, 'tendencia': 'Moderando'},
            ],
            'narrativa_jolts': (
                f"Los datos JOLTS confirman la normalización del mercado laboral. Las ofertas de empleo "
                f"se situan en {jo_str}, mientras el quits rate en {qr_str} se ha normalizado, "
                f"sugiriendo menor confianza de los trabajadores para cambiar de empleo."
            ),
            'narrativa_salarios': (
                f"Las presiones salariales se moderan gradualmente. El AHE crece {ahe_str}, "
                f"aun por encima del nivel consistente con inflación de 2% (~3.5% con productividad de 1.5%)."
            )
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

        return {
            'titulo': 'Inflación',
            'narrativa': (
                f"La desinflación continua su curso, aunque a un ritmo más lento de lo esperado. "
                f"El Core PCE, la metrica preferida de la Fed, se ubica en {pce_c_yoy}, aun por encima "
                f"del target de 2%. El CPI headline se situa en {cpi_h_yoy}. "
                f"La inflación de servicios ex-housing permanece sticky, mientras que la inflación "
                f"de bienes se encuentra en desaceleración."
            ),
            'datos': [
                {'indicador': 'CPI Headline', 'valor': cpi_h_yoy, 'anterior': 'N/D', 'mom': cpi_h_mom_str},
                {'indicador': 'CPI Core', 'valor': cpi_c_yoy, 'anterior': 'N/D', 'mom': cpi_c_mom_str},
                {'indicador': 'PCE Core', 'valor': pce_c_yoy, 'anterior': 'N/D', 'mom': pce_c_mom_str},
            ],
            'componentes': [
                {'componente': 'Shelter', 'valor': '5.1% a/a', 'tendencia': 'Desacelerando'},
                {'componente': 'Services ex-Housing', 'valor': '3.5% a/a', 'tendencia': 'Sticky'},
                {'componente': 'Core Goods', 'valor': '-0.3% a/a', 'tendencia': 'Deflacion'},
                {'componente': 'Food', 'valor': '2.1% a/a', 'tendencia': 'Estable'},
                {'componente': 'Energy', 'valor': '-2.5% a/a', 'tendencia': 'Deflacion'},
            ],
            'expectativas': [
                {'medida': 'UMich Sentiment', 'valor': umich, 'comentario': 'Datos FRED'},
                {'medida': 'SPF 10yr', 'valor': '2.1%', 'comentario': 'Ancladas'},
            ]
        }

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
                'neutral_estimada': '3.00%',
                'real_actual': real_str,
                'proyección_2026': '3.50%',
                'mercado_implica': '3.25%'
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

        # 2026 FOMC schedule (key meetings)
        schedule = [
            ('Mar 18-19', 34), ('May 6-7', 76), ('Jun 17-18', 125),
            ('Jul 29-30', 167), ('Sep 16-17', 216), ('Oct 28-29', 258),
        ]

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
        return {
            'titulo': 'Política Fiscal',
            'narrativa': (
                "El déficit fiscal cerro 2025 en 5.8% del GDP tras esfuerzos de consolidacion. "
                "Para 2026 proyectamos déficit de 5.5% con impulso fiscal neutro. La deuda publica "
                "se estabiliza en 123% del GDP. Los costos de servicio de deuda siguen elevados "
                "pero menores que en 2024 gracias a la baja de tasas."
            ),
            'datos': [
                {'indicador': 'Déficit Fiscal', 'valor': '-5.5% GDP', 'anterior': '-5.8%'},
                {'indicador': 'Deuda Publica', 'valor': '123% GDP', 'anterior': '122%'},
                {'indicador': 'Impulso Fiscal', 'valor': '0.0pp', 'comentario': 'Neutro'},
                {'indicador': 'Costo Deuda', 'valor': '3.0% GDP', 'anterior': '3.2%'},
            ],
            'riesgos': [
                'Nuevos tax cuts de administracion Trump podrian ampliar déficit',
                'Gasto en defensa creciente por tensiones geopolíticas',
                'Moody\'s mantiene outlook negativo sobre rating AAA'
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
        gdp_ez = self._fmt(eu.get('gdp_qoq'), suffix='% t/t') if eu.get('gdp_qoq') is not None else '1.2%'
        gdp_de = self._fmt(eu.get('gdp_alemania'), suffix='% t/t') if eu.get('gdp_alemania') is not None else '0.6%'
        gdp_fr = self._fmt(eu.get('gdp_francia'), suffix='% t/t') if eu.get('gdp_francia') is not None else '1.1%'
        gdp_uk = self._fmt(eu.get('gdp_uk'), suffix='% t/t') if eu.get('gdp_uk') is not None else '1.0%'
        desemp = self._fmt(eu.get('unemployment')) if eu.get('unemployment') is not None else '6.4%'

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
                {'pais': 'Euro Area', 'gdp_2025': gdp_ez, 'gdp_2026f': '1.4%', 'consenso': '1.2%'},
                {'pais': 'Alemania', 'gdp_2025': gdp_de, 'gdp_2026f': '1.0%', 'consenso': '0.8%'},
                {'pais': 'Francia', 'gdp_2025': gdp_fr, 'gdp_2026f': '1.3%', 'consenso': '1.1%'},
                {'pais': 'UK', 'gdp_2025': gdp_uk, 'gdp_2026f': '1.2%', 'consenso': '1.1%'},
            ],
            'indicadores': [
                {'indicador': 'Desempleo Eurozona', 'valor': desemp, 'comentario': 'BCCh' if has_real else 'Estimado'},
                {'indicador': 'PMI Manufacturing', 'valor': '46.2', 'comentario': 'Estimado (propietario)'},
                {'indicador': 'PMI Services', 'valor': '51.5', 'comentario': 'Estimado (propietario)'},
            ],
            'desafios_estructurales': [
                'Demografia adversa - población en edad laboral decreciendo',
                'Competitividad industrial erosionada vs China/US',
                'Costos de energía estructuralmente más altos',
                'Fragmentacion política limita reformas'
            ]
        }

    def _generate_europe_inflation(self) -> Dict[str, Any]:
        """Genera seccion de inflación Europa."""
        eu = self._get_europe_latest()

        cpi_val = self._fmt(eu.get('cpi')) if eu.get('cpi') is not None else '2.1%'
        core_val = self._fmt(eu.get('core_cpi')) if eu.get('core_cpi') is not None else '2.3%'
        ppi_val = self._fmt(eu.get('ppi')) if eu.get('ppi') is not None else 'N/D'

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
                {'indicador': 'Salarios Negociados', 'valor': '3.2%', 'anterior': '3.5%'},
            ]
        }

    def _generate_ecb_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria BCE."""
        eu = self._get_europe_latest()

        ecb_rate = self._fmt(eu.get('ecb_rate'), decimals=2) if eu.get('ecb_rate') is not None else '2.25%'
        bund_10y = self._fmt(eu.get('bund_10y'), decimals=2) if eu.get('bund_10y') is not None else '2.30%'

        has_real = bool(eu.get('ecb_rate') is not None)
        src = ' (datos BCCh)' if has_real else ''

        return {
            'titulo': f'Política Monetaria - BCE{src}',
            'narrativa': (
                f"El BCE tiene la tasa de referencia en {ecb_rate}, cerca de su nivel neutral estimado. "
                f"Bund 10Y en {bund_10y}. "
                f"Tras los recortes de 2025, el BCE se encuentra en modo de espera evaluando "
                f"si la inflación se mantiene anclada. Proyectamos un recorte adicional de 25bp "
                f"en H2 2026 si el crecimiento decepciona."
            ),
            'tasas': {
                'deposito_actual': ecb_rate,
                'refi_actual': bund_10y,
                'proyección_2026': '2.00%',
                'neutral_estimada': '2.00%'
            },
            'próximos_movimientos': [
                {'fecha': 'Marzo', 'expectativa': 'Hold', 'probabilidad': '85%'},
                {'fecha': 'Junio', 'expectativa': 'Hold', 'probabilidad': '70%'},
                {'fecha': 'Septiembre', 'expectativa': '-25bp', 'probabilidad': '50%'},
            ],
            'balance_riesgos': {
                'dovish': 'Crecimiento aun debil, EUR fuerte, crédito restringido',
                'hawkish': 'Inflación servicios rebotando, salarios acelerando'
            }
        }

    def _generate_europe_risks(self) -> Dict[str, Any]:
        """Genera riesgos especificos Europa."""
        return {
            'titulo': 'Riesgos Especificos Europa',
            'riesgos': [
                {
                    'nombre': 'Competencia China en Manufactura',
                    'descripcion': 'Overcapacity china presiona precios y margenes del sector automotriz y quimico europeo',
                    'probabilidad': 'Alta',
                    'impacto': 'Medio'
                },
                {
                    'nombre': 'Costos de Energía',
                    'descripcion': 'Precios del gas natural estructuralmente más altos que pre-2022, afectando competitividad',
                    'probabilidad': 'Alta',
                    'impacto': 'Medio'
                },
                {
                    'nombre': 'Fragmentacion Política',
                    'descripcion': 'Gobiernos debiles en Francia y Alemania limitan capacidad de reformás y política fiscal',
                    'probabilidad': 'Media',
                    'impacto': 'Medio'
                }
            ]
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

        gdp_val = self._fmt(cn.get('gdp_qoq'), suffix='% t/t') if cn.get('gdp_qoq') is not None else '4.8% a/a'
        cpi_val = self._fmt(cn.get('cpi')) if cn.get('cpi') is not None else '0.3%'
        desemp_val = self._fmt(cn.get('unemployment')) if cn.get('unemployment') is not None else '5.0%'

        has_real = bool(cn.get('gdp_qoq') is not None)
        src = ' (datos BCCh)' if has_real else ''

        return {
            'titulo': f'Crecimiento{src}',
            'narrativa': (
                f"China con GDP trimestral de {gdp_val}. "
                f"CPI: {cpi_val}, desempleo urbano: {desemp_val}. "
                f"El sector inmobiliario sigue como drag aunque menor, mientras que "
                f"exportaciones enfrentan aranceles crecientes. El consumo domestico muestra "
                f"recuperación gradual, siendo el foco de la política económica."
            ),
            'datos': [
                {'indicador': 'GDP ultimo trimestre', 'valor': gdp_val, 'anterior': 'BCCh' if has_real else 'Estimado'},
                {'indicador': 'CPI YoY', 'valor': cpi_val, 'anterior': 'BCCh' if cn.get('cpi') is not None else 'Estimado'},
                {'indicador': 'Desempleo Urbano', 'valor': desemp_val, 'anterior': 'BCCh' if cn.get('unemployment') is not None else 'Estimado'},
            ],
            'indicadores': [
                {'indicador': 'PMI Manufacturing', 'valor': '50.2', 'comentario': 'Estimado (propietario)'},
                {'indicador': 'PMI Services', 'valor': '52.1', 'comentario': 'Estimado (propietario)'},
            ]
        }

    def _generate_china_property(self) -> Dict[str, Any]:
        """Genera seccion de sector inmobiliario China."""
        return {
            'titulo': 'Sector Inmobiliario',
            'narrativa': (
                "El sector inmobiliario muestra señales de estabilizacion tras las agresivas "
                "medidas de soporte, aunque los niveles de actividad permanecen deprimidos vs "
                "2021. Las ventas de propiedades caen 15% a/a pero el ritmo de caida se modera. "
                "Estimamos que el drag del sector sobre el GDP sera de -0.5pp en 2026, "
                "menor que el -1.0pp de 2025."
            ),
            'datos': [
                {'indicador': 'Property Sales', 'valor': '-15% a/a', 'anterior': '-20%'},
                {'indicador': 'Housing Starts', 'valor': '-25% a/a', 'anterior': '-30%'},
                {'indicador': 'Home Prices (Tier 1)', 'valor': '-3% a/a', 'anterior': '-5%'},
                {'indicador': 'Developer Funding', 'valor': '-10% a/a', 'anterior': '-15%'},
            ],
            'políticas_soporte': [
                'Reduccion tasas hipotecarias',
                'Relajacion restricciónes de compra en ciudades Tier 2-3',
                'Programa de compra de inventarios por gobiernos locales',
                'Financiamiento a developers viables'
            ],
            'drag_estimado': {
                '2024': '-1.0pp del GDP',
                '2025f': '-0.5pp del GDP',
                '2026f': '-0.2pp del GDP'
            }
        }

    def _generate_china_credit(self) -> Dict[str, Any]:
        """Genera seccion de impulso crediticio China."""
        return {
            'titulo': 'Impulso Crediticio',
            'narrativa': (
                "El impulso crediticio se ha vuelto positivo tras meses de contracción, "
                "senalando mejor soporte al crecimiento. El Total Social Financing crece "
                "al 10% a/a, con expansión en bonos gubernamentales compensando debilidad "
                "en crédito corporativo y shadow banking."
            ),
            'datos': [
                {'indicador': 'TSF Growth', 'valor': '10.0% a/a', 'anterior': '9.5%'},
                {'indicador': 'New Yuan Loans', 'valor': 'CNY 1.2T', 'anterior': 'CNY 1.0T'},
                {'indicador': 'Credit Impulse', 'valor': '+2.5pp', 'anterior': '+1.0pp'},
                {'indicador': 'M2 Growth', 'valor': '8.5% a/a', 'anterior': '8.0%'},
            ],
            'implicancias_globales': (
                "El credit impulse positivo en China históricamente precede mejor demanda "
                "de commodities y crecimiento global con lag de 6-9 meses."
            )
        }

    def _generate_china_trade(self) -> Dict[str, Any]:
        """Genera seccion de comercio exterior China."""
        return {
            'titulo': 'Comercio Exterior',
            'narrativa': (
                "Las exportaciones chinas mantienen fortaleza impulsadas por productos "
                "manufacturados, especialmente autos eléctricos, paneles solares y maquinaria. "
                "El superávit comercial se mantiene en niveles record, generando tensiones "
                "comerciales con socios. El overcapacity industrial es un riesgo para "
                "competidores globales."
            ),
            'datos': [
                {'indicador': 'Trade Balance', 'valor': '$75B', 'anterior': '$70B'},
                {'indicador': 'Exports', 'valor': '+8% a/a', 'anterior': '+5%'},
                {'indicador': 'Imports', 'valor': '+2% a/a', 'anterior': '-1%'},
                {'indicador': 'Exports to US', 'valor': '+12% a/a', 'comentario': 'Front-loading?'},
            ],
            'implicancias_commodities': [
                'Demanda de cobre estable por sector construcción/infra',
                'Demanda de petróleo moderada por EVs y eficiencia',
                'Demanda de hierro debil por property sector'
            ]
        }

    def _generate_pboc_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria PBOC."""
        cn = self._get_china_latest()

        pboc_rate = self._fmt(cn.get('pboc_rate'), decimals=2) if cn.get('pboc_rate') is not None else '2.50%'
        cny_val = f"{cn['cny_usd']:.2f}" if cn.get('cny_usd') is not None else '7.30'
        shanghai = f"{cn['shanghai']:.0f}" if cn.get('shanghai') is not None else 'N/D'

        has_real = bool(cn.get('pboc_rate') is not None)
        src = ' (datos BCCh)' if has_real else ''

        return {
            'titulo': f'Política Monetaria - PBOC{src}',
            'narrativa': (
                f"El PBOC tiene la tasa de referencia en {pboc_rate}. "
                f"CNY/USD: {cny_val}. Shanghai Composite: {shanghai}. "
                f"Las tasas se han reducido significativamente y ahora hay menos espacio. "
                f"El RRR podria reducirse 25bp adicionales si el crecimiento decepciona."
            ),
            'tasas': {
                'pboc_rate': pboc_rate,
                'lpr_1y': '3.10%',
                'lpr_5y': '3.60%',
                'rrr': '9.50%',
                'yuan_usdcny': cny_val
            },
            'outlook': {
                'tasas': 'Sesgo neutral, espacio limitado para más recortes',
                'rrr': 'Posible -25bp si crecimiento decepciona',
                'yuan': 'Depreciacion gradual aceptada'
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
        imacec_str = self._fmt(imacec) + ' a/a' if imacec is not None else '2.5% a/a'
        desemp_str = self._fmt(desemp) if desemp is not None else '8.5%'

        narrativa = (
            f"La economía chilena consolida su recuperación. "
            f"El IMACEC muestra expansión de {imacec_str if imacec is not None else '~2.5% a/a'}, "
            f"con servicios y mineria como drivers. "
            f"El consumo privado mantiene dinamismo apoyado por salarios reales positivos. "
            f"La tasa de desempleo se ubica en {desemp_str}. "
            f"Proyectamos GDP de 2.5% para 2026."
        )

        return {
            'titulo': 'Chile - Crecimiento',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'IMACEC', 'valor': imacec_str, 'anterior': '2.2%', 'tendencia': 'Recuperando'},
                {'indicador': 'GDP Trim (t/t-4)', 'valor': '2.3%', 'anterior': '2.0%', 'tendencia': 'Estable'},
                {'indicador': 'Consumo Privado', 'valor': '3.5% a/a', 'anterior': '3.0%', 'tendencia': 'Solido'},
                {'indicador': 'Inversion (FBCF)', 'valor': '-2.0% a/a', 'anterior': '-3.5%', 'tendencia': 'Debil'},
                {'indicador': 'Exportaciones', 'valor': '4.5% a/a', 'anterior': '3.8%', 'tendencia': 'Firme'},
            ],
            'mercado_laboral': [
                {'indicador': 'Tasa Desempleo', 'valor': desemp_str, 'anterior': '8.8%'},
                {'indicador': 'Ocupacion', 'valor': '+1.5% a/a', 'anterior': '+1.2%'},
                {'indicador': 'Participación', 'valor': '60.5%', 'anterior': '60.2%'},
                {'indicador': 'Salarios Reales', 'valor': '+1.8% a/a', 'anterior': '+1.5%'},
            ]
        }

    def _generate_chile_inflation(self) -> Dict[str, Any]:
        """Genera seccion de inflación Chile."""
        cl = self._get_chile_latest()
        ipc_yoy = cl.get('ipc_yoy')
        ipc_mom = cl.get('ipc_mom')

        ipc_yoy_str = self._fmt(ipc_yoy) + ' a/a' if ipc_yoy is not None else '3.8% a/a'
        ipc_mom_str = f"+{self._fmt(ipc_mom)}" if ipc_mom is not None else '+0.2%'

        narrativa = (
            f"La desinflación continua on track, con el IPC convergiendo hacia la meta. "
            f"El IPC headline se ubica en {ipc_yoy_str}, "
            f"con una variación mensual de {ipc_mom_str}. "
            f"Las expectativas de inflación a 2 años se mantienen ancladas en 3.0%."
        )

        return {
            'titulo': 'Chile - Inflación',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'IPC Headline', 'valor': ipc_yoy_str, 'anterior': '4.2%', 'mom': ipc_mom_str},
                {'indicador': 'IPC Subyacente (SAE)', 'valor': '3.6% a/a', 'anterior': '3.9%', 'mom': '+0.3%'},
                {'indicador': 'Transables', 'valor': '-0.5% a/a', 'anterior': '0.2%', 'comentario': 'Deflacion'},
                {'indicador': 'No Transables', 'valor': '4.5% a/a', 'anterior': '4.8%', 'comentario': 'Moderando'},
            ],
            'expectativas': [
                {'medida': 'EEE 1 año', 'valor': '3.2%', 'anterior': '3.4%'},
                {'medida': 'EEE 2 años', 'valor': '3.0%', 'anterior': '3.0%'},
                {'medida': 'EOF 1 año', 'valor': '3.3%', 'anterior': '3.5%'},
                {'medida': 'Breakevens 2y', 'valor': '3.1%', 'anterior': '3.2%'},
            ]
        }

    def _generate_bcch_policy(self) -> Dict[str, Any]:
        """Genera seccion de política monetaria BCCh."""
        cl = self._get_chile_latest()
        tpm = cl.get('tpm')
        ipc_yoy = cl.get('ipc_yoy')

        tpm_str = self._fmt(tpm) if tpm is not None else '4.50%'
        tpm_real_str = self._fmt(tpm - ipc_yoy, decimals=1) if (tpm is not None and ipc_yoy is not None) else '1.5%'

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
                'tpm_neutral': '4.00%',
                'tpm_real': tpm_real_str,
                'proyección_2026': '4.25%',
                'consenso_2026': '4.25%'
            },
            'ipom_path': [
                {'trimestre': 'Q1 2026', 'tpm_proyectada': tpm_str},
                {'trimestre': 'Q2 2026', 'tpm_proyectada': '4.25%'},
                {'trimestre': 'Q3 2026', 'tpm_proyectada': '4.25%'},
                {'trimestre': 'Q4 2026', 'tpm_proyectada': '4.25%'},
            ],
            'comunicacion': (
                "El Consejo del BCCh senala que mantendra la TPM en niveles cercanos al neutral, "
                "evaluando la evolución de la inflación y la actividad económica."
            ),
            'proximas_reuniones': [
                {'fecha': 'Mar 2026', 'expectativa': 'Hold', 'probabilidad': '70%'},
                {'fecha': 'May 2026', 'expectativa': '-25bp', 'probabilidad': '55%'},
                {'fecha': 'Jul 2026', 'expectativa': 'Hold', 'probabilidad': '60%'},
            ]
        }

    def _generate_chile_external(self) -> Dict[str, Any]:
        """Genera seccion de cuentas externas Chile."""
        cl = self._get_chile_latest()
        usd_clp = cl.get('usd_clp')

        usdclp_str = f"{usd_clp:.0f}" if usd_clp is not None else '920'

        narrativa = (
            "La cuenta corriente se ha corregido significativamente desde los déficits "
            "record de 2022. El déficit se ubica en -3.5% del GDP, financiado principalmente "
            "por IED. Los terminos de intercambio mejoran levemente por precio del cobre, "
            f"aunque el litio sigue deprimido. El tipo de cambio se ubica en "
            f"{usdclp_str} CLP/USD."
        )

        return {
            'titulo': 'Chile - Cuentas Externas',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'Cuenta Corriente', 'valor': '-3.5% GDP', 'anterior': '-4.2%'},
                {'indicador': 'Balanza Comercial', 'valor': '+$1.5B', 'anterior': '+$1.2B'},
                {'indicador': 'Terminos de Intercambio', 'valor': '+2% a/a', 'anterior': '-5%'},
                {'indicador': 'IED Neta', 'valor': '$8B ytd', 'anterior': '$7B'},
            ],
            'tipo_cambio': {
                'usdclp_actual': usdclp_str,
                'rango_12m': '850-980',
                'drivers': 'Diferencial tasas, precio cobre, risk appetite global'
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
        copper_str = f'${copper_price:.2f}/lb' if copper_price else '$4.35/lb'

        return {
            'titulo': 'Commodities Relevantes',
            'commodities': [
                {
                    'nombre': 'Cobre',
                    'precio_actual': copper_str,
                    'precio_anterior': '$4.20/lb',
                    'cambio': '+3.6%',
                    'outlook': 'Constructivo',
                    'balance': 'Déficit proyectado 2026-2027',
                    'drivers': 'Transición energetica, AI data centers, oferta limitada',
                    'inventarios': {
                        'lme': '185K tons',
                        'shfe': '95K tons',
                        'comex': '22K tons',
                        'total': '302K tons',
                        'dias_consumo': '4.2 dias',
                        'vs_promedio_5y': '-35%',
                        'tendencia': 'Normalizando pero aun tight'
                    },
                    'supply': {
                        'producción_2026e': '22.5M tons',
                        'demanda_2026e': '23.2M tons',
                        'déficit': '-700K tons',
                        'crecimiento_oferta': '+2.1%',
                        'crecimiento_demanda': '+3.5%'
                    },
                    'breakeven_costs': {
                        'percentil_90': '$3.50/lb',
                        'percentil_75': '$3.00/lb',
                        'percentil_50': '$2.50/lb',
                        'costo_marginal': '$3.80/lb',
                        'comentario': 'Precios actuales muy sobre costo marginal - soportan expansión'
                    }
                },
                {
                    'nombre': 'Litio',
                    'precio_actual': '$10K/ton',
                    'precio_anterior': '$12K/ton',
                    'cambio': '-16.7%',
                    'outlook': 'Estabilizando',
                    'balance': 'Superávit moderandose por cierre de capacidad marginal',
                    'drivers': 'Demanda EV solida pero oferta aun abundante',
                    'inventarios': {
                        'china_carbonato': '85K tons',
                        'dias_consumo': '28 dias',
                        'tendencia': 'Estabilizandose tras drawdown'
                    },
                    'supply': {
                        'producción_2026e': '1.2M LCE tons',
                        'demanda_2026e': '1.1M LCE tons',
                        'superávit': '+100K tons',
                        'crecimiento_oferta': '+15%',
                        'crecimiento_demanda': '+20%'
                    },
                    'breakeven_costs': {
                        'australia_spodumene': '$12K/ton',
                        'chile_salmuera': '$6K/ton',
                        'argentina_salmuera': '$8K/ton',
                        'costo_marginal': '$14K/ton',
                        'comentario': 'Precios bajo costo marginal - productores australianos bajo presion'
                    }
                },
                {
                    'nombre': 'Petróleo (Brent)',
                    'precio_actual': '$78/bbl',
                    'precio_anterior': '$82/bbl',
                    'cambio': '-4.9%',
                    'outlook': 'Neutral',
                    'balance': 'Equilibrado con OPEC+ support',
                    'drivers': 'Demanda China debil, OPEC+ disciplinado, geopolítica',
                    'inventarios': {
                        'oecd': '2.75B bbl',
                        'dias_cobertura': '62 dias',
                        'vs_promedio_5y': '+3%'
                    },
                    'breakeven_costs': {
                        'shale_us': '$50/bbl',
                        'offshore': '$45/bbl',
                        'opec': '$35/bbl',
                        'fiscal_breakeven_saudi': '$85/bbl'
                    }
                }
            ],
            'transmisión_global': {
                'titulo': 'Transmision a Chile',
                'cobre_impacto': {
                    'cuenta_corriente': '+$1.5B por cada +$0.50/lb',
                    'ingresos_fiscales': '+$1.2B por cada +$0.50/lb',
                    'tipo_cambio': '-25 CLP/USD por cada +$0.50/lb'
                },
                'petróleo_impacto': {
                    'importaciones': '-$0.8B por cada +$10/bbl',
                    'inflación': '+0.15pp IPC por cada +$10/bbl'
                }
            },
            'impacto_fiscal': {
                'cobre': '+$2.5B ingresos fiscales vs 2025',
                'litio': 'Neutral vs expectativas revisadas',
                'neto': 'Positivo para cuentas fiscales 2026'
            }
        }

    def _generate_latam_context(self) -> Dict[str, Any]:
        """Genera contexto de LatAm."""
        return {
            'titulo': 'Contexto LatAm',
            'paises': [
                {
                    'pais': 'Brasil',
                    'gdp': '2.0%',
                    'inflación': '4.5%',
                    'tasa': '11.75% (Selic)',
                    'outlook': 'Fiscal sigue como riesgo; BCB hawkish',
                    'riesgo_principal': 'Desanclaje expectativas inflación, sostenibilidad fiscal'
                },
                {
                    'pais': 'Mexico',
                    'gdp': '1.8%',
                    'inflación': '4.2%',
                    'tasa': '10.25% (Banxico)',
                    'outlook': 'Nearshoring beneficia, Banxico en recortes',
                    'riesgo_principal': 'Relacion con US post-elecciones, PEMEX'
                },
                {
                    'pais': 'Colombia',
                    'gdp': '1.5%',
                    'inflación': '5.5%',
                    'tasa': '9.50%',
                    'outlook': 'Desinflación lenta, BanRep cautioso',
                    'riesgo_principal': 'Política económica, déficit fiscal'
                }
            ],
            'diferenciacion_chile': (
                "Chile se diferencia positivamente por: (1) Inflación controlada y convergiendo, "
                "(2) Banco central credible con espacio para recortes, (3) Cuentas externas "
                "en correccion, (4) Precio del cobre favorable."
            )
        }

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

        # Minimal fallback — no stale market calls
        fallback = [
            {
                'titulo': 'Panorama Geopolitico y Comercial',
                'descripcion': (
                    "Las dinamicas geopoliticas y comerciales dominan el panorama macro de este mes. "
                    "Monitorear desarrollos de politica comercial y tensiones regionales."
                    + epu_html
                ),
                'impacto_macro': {'global': 'Incertidumbre elevada requiere posicionamiento defensivo selectivo'}
            },
            {
                'titulo': 'Dinamicas de Crecimiento e Inflacion',
                'descripcion': (
                    "El balance entre crecimiento e inflacion sigue siendo el factor central "
                    "para la politica monetaria y el posicionamiento de portafolios."
                ),
                'impacto_macro': {'global': 'Bancos centrales en modo data-dependent'}
            },
        ]
        return fallback

    def _generate_events_calendar(self) -> List[Dict[str, Any]]:
        """Genera calendario de eventos clave."""
        return [
            {'fecha': '12 Feb', 'evento': 'CPI USA Enero', 'relevancia': 'Alta', 'impacto_potencial': 'Confirma path de inflación'},
            {'fecha': '27 Feb', 'evento': 'GDP USA Q4 (final)', 'relevancia': 'Media', 'impacto_potencial': 'Validacion soft landing'},
            {'fecha': '6 Mar', 'evento': 'ECB Decision', 'relevancia': 'Alta', 'impacto_potencial': 'Signal de terminal rate'},
            {'fecha': '18-19 Mar', 'evento': 'FOMC + Dot Plot', 'relevancia': 'Alta', 'impacto_potencial': 'Path de tasas 2026'},
            {'fecha': '25 Mar', 'evento': 'Reunion BCCh', 'relevancia': 'Alta', 'impacto_potencial': 'Signal de TPM path'},
            {'fecha': '30 Abr', 'evento': 'PIB Chile Q1', 'relevancia': 'Media', 'impacto_potencial': 'Confirmacion recuperación'},
        ]

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
        """Genera escenarios macro."""
        return {
            'base': {
                'nombre': 'Soft Landing',
                'probabilidad': 55,
                'descripcion': (
                    "Crecimiento global se mantiene en 2.5-3.0%, inflación converge a targets, "
                    "bancos centrales recortan tasas gradualmente. US evita recesión con "
                    "desaceleración moderada. China estabiliza con estimulos."
                ),
                'implicancias': {
                    'gdp_us': '2.0-2.5%',
                    'inflación_us': '2.3-2.8%',
                    'fed_funds': '3.50-4.00%',
                    'sp500': '+5-10%'
                }
            },
            'upside': {
                'nombre': 'No Landing / Re-acceleracion',
                'probabilidad': 20,
                'descripcion': (
                    "Crecimiento supera expectativas, productividad por AI, mercado laboral "
                    "robusto. Riesgo: reflacion que fuerza a Fed a pausar o revertir recortes."
                ),
                'implicancias': {
                    'gdp_us': '2.5-3.0%',
                    'inflación_us': '3.0-3.5%',
                    'fed_funds': '4.00-4.50%',
                    'sp500': '+10-15%'
                },
                'triggers': [
                    'GDP Q1 > 3% anualizado',
                    'Core PCE estancado en 3%+',
                    'NFP > 250K promedio'
                ]
            },
            'downside': {
                'nombre': 'Hard Landing / Recesión',
                'probabilidad': 25,
                'descripcion': (
                    "Credit crunch, colapso consumo, desempleo sube a 5.5%+. "
                    "Fed forzado a recortes agresivos. Risk off global."
                ),
                'implicancias': {
                    'gdp_us': '-0.5-0.5%',
                    'inflación_us': '1.5-2.0%',
                    'fed_funds': '2.50-3.00%',
                    'sp500': '-15-20%'
                },
                'triggers': [
                    'Initial claims > 300K sostenido',
                    'Desempleo > 5%',
                    'Credit spreads HY > 500bp'
                ]
            }
        }

    def _generate_top_risks(self) -> List[Dict[str, Any]]:
        """Genera top 3 riesgos macro."""
        return [
            {
                'nombre': 'Escalada Comercial US-China',
                'probabilidad': '30%',
                'impacto': 'Alto',
                'descripcion': (
                    "Aranceles adicionales de 25%+ podrian reducir GDP global en 0.5pp "
                    "y generar presion inflaciónaria. Cadenas de suministro dislocadas."
                ),
                'senal_temprana': 'Anuncios de aranceles post-inauguracion, retorica agresiva',
                'implicancia_macro': 'GDP -0.3pp, CPI +0.5pp, USD fortaleza'
            },
            {
                'nombre': 'Inflación Sticky / Fed Hawkish',
                'probabilidad': '25%',
                'impacto': 'Medio-Alto',
                'descripcion': (
                    "Inflación de servicios no cede, Fed pausa o revierte recortes. "
                    "Tasas largas suben, valuaciones bajo presion."
                ),
                'senal_temprana': 'Core PCE > 3% por 3 meses, wages acelerando',
                'implicancia_macro': 'Fed Funds 4.5%+ EOY, 10y > 5%'
            },
            {
                'nombre': 'Crisis Fiscal / Debt Ceiling',
                'probabilidad': '20%',
                'impacto': 'Medio',
                'descripcion': (
                    "Negociaciones de debt ceiling generan volatilidad. Riesgo de shutdown "
                    "o downgrade crediticio. Presion sobre tasas largas."
                ),
                'senal_temprana': 'Stalemate en Congreso, CDS US widening',
                'implicancia_macro': 'Term premium sube, USD debilidad temporal'
            }
        ]

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
            pos_resumen = 'Postura selectiva con enfasis en datos proximos como catalizador.'

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
                    'tema': 'Crecimiento e Inflacion',
                    'vista_grb': 'Dinamicas mixtas requieren monitoreo cercano de datos proximos.',
                    'vs_consenso': 'En evaluacion',
                    'vs_detalle': 'Pendiente de datos clave para definir posicion relativa al consenso.'
                },
                {
                    'tema': 'Politica Monetaria',
                    'vista_grb': 'Bancos centrales en modo data-dependent.',
                    'vs_consenso': 'Alineado',
                    'vs_detalle': 'Vista alineada con expectativas del mercado.'
                },
            ],
            'posicionamiento_resumen': 'Postura neutral con sesgo constructivo.',
            'proximo_reporte': 'Este analisis sirve como input para reportes de Asset Allocation y Renta Fija.'
        }

    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte macro."""

        return {
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

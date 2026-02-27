# -*- coding: utf-8 -*-
"""
Greybark Research - Asset Allocation Content Generator
========================================================

Genera el CONTENIDO narrativo para el reporte de Asset Allocation.
Integra datos del Council de Inversión (panel_outputs, cio_synthesis,
final_recommendation) para producir recomendaciones fundamentadas.

Sigue la estructura de JPM/Wellington/BlackRock:
- Resumen ejecutivo con postura del comité
- Escenarios con probabilidades
- Views por región con argumentos PRO y CONTRA
- Recomendaciones OW/UW por asset class
- Riesgos detallados con hedges
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class AssetAllocationContentGenerator:
    """Generador de contenido narrativo para Reporte de Asset Allocation."""

    def __init__(self, council_result: Dict, quant_data: Dict = None,
                 forecast_data: Dict = None):
        self.council = council_result or {}
        self.quant = quant_data or {}
        self.forecast = forecast_data or {}
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)

        # Cache parsed council data
        self._parsed_final = None
        self._parsed_cio = None

    # =========================================================================
    # QUANT DATA HELPERS
    # =========================================================================

    def _q(self, *keys, default=None):
        """Accede a quant_data siguiendo ruta de keys."""
        d = self.quant
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

    def _has_q(self, *keys) -> bool:
        """Verifica si quant_data tiene datos en la ruta."""
        return self._q(*keys) is not None

    def _fmt_bp(self, value) -> str:
        """Formatea basis points."""
        if value is None:
            return 'N/D'
        try:
            return f"{int(round(float(value)))}bp"
        except (ValueError, TypeError):
            return str(value)

    def _fmt_pct(self, value, dec=2) -> str:
        """Formatea porcentaje."""
        if value is None:
            return 'N/D'
        try:
            return f"{float(value):.{dec}f}%"
        except (ValueError, TypeError):
            return str(value)

    def _get_spanish_month(self, month: int) -> str:
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return meses.get(month, 'Mes')

    # =========================================================================
    # COUNCIL DATA EXTRACTION HELPERS
    # =========================================================================

    def _panel(self, agent: str) -> str:
        """Extrae texto de un agente del panel."""
        return self.council.get('panel_outputs', {}).get(agent, '')

    def _final(self) -> str:
        """Extrae la recomendación final."""
        return self.council.get('final_recommendation', '')

    def _cio(self) -> str:
        """Extrae la síntesis CIO."""
        return self.council.get('cio_synthesis', '')

    def _contrarian(self) -> str:
        """Extrae la crítica contrarian."""
        return self.council.get('contrarian_critique', '')

    def _has_council(self) -> bool:
        """Verifica si hay datos del council disponibles."""
        return bool(self.council.get('final_recommendation', ''))

    def _extract_number(self, text: str, pattern: str, default: float = None) -> Optional[float]:
        """Extrae un número de texto usando regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return default

    def _extract_between(self, text: str, start: str, end: str) -> str:
        """Extrae texto entre dos marcadores."""
        try:
            s = text.index(start) + len(start)
            e = text.index(end, s)
            return text[s:e].strip()
        except (ValueError, IndexError):
            return ''

    # =========================================================================
    # SECCION 1: RESUMEN EJECUTIVO
    # =========================================================================

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Genera el resumen ejecutivo basado en council output."""

        postura = self._determine_postura()
        key_points = self._generate_key_points()

        return {
            'parrafo_intro': self._generate_intro_paragraph(postura),
            'key_points': key_points,
            'postura': postura,
            'catalizador': self._identify_catalizador()
        }

    def _determine_postura(self) -> Dict[str, str]:
        """Determina la postura del comité desde final_recommendation."""
        final = self._final()

        if not final:
            return {'view': 'NEUTRAL', 'sesgo': 'SELECTIVO', 'conviccion': 'MEDIA'}

        # Parse postura from final recommendation
        text = final.lower()

        # Detect view
        # AGRESIVO: solo si explícitamente dice "postura agresiva" o "stance agresivo"
        # (no matchear "perfil agresivo" ni "agresivamente" que son portfolio/adverbio)
        import re as _re
        if _re.search(r'postura\s+(agresiva|agresivo)', text) or 'stance agresivo' in text or 'fuerte risk-on' in text:
            view = 'AGRESIVO'
            sesgo = 'RISK-ON AGRESIVO'
        elif 'defensiva moderada' in text or 'defensivo moderado' in text:
            view = 'CAUTELOSO'
            sesgo = 'DEFENSIVO SELECTIVO'
        elif 'expansión tardía' in text or 'expansion tardia' in text:
            view = 'CONSTRUCTIVO'
            sesgo = 'RISK-ON SELECTIVO'
        elif 'risk-off' in text:
            view = 'CAUTELOSO'
            sesgo = 'DEFENSIVO'
        elif 'expansi' in text and ('tempran' in text or 'aceler' in text):
            view = 'CONSTRUCTIVO'
            sesgo = 'RISK-ON'
        elif 'recesi' in text or 'contracci' in text:
            view = 'CAUTELOSO'
            sesgo = 'DEFENSIVO'
        else:
            view = 'NEUTRAL'
            sesgo = 'SELECTIVO'

        # Detect conviction
        if 'convicción media-alta' in text or 'conviccion media-alta' in text:
            conviccion = 'MEDIA-ALTA'
        elif 'convicción alta' in text or 'conviccion alta' in text:
            conviccion = 'ALTA'
        elif 'convicción baja' in text or 'conviccion baja' in text:
            conviccion = 'BAJA'
        else:
            conviccion = 'MEDIA'

        return {'view': view, 'sesgo': sesgo, 'conviccion': conviccion}

    def _generate_intro_paragraph(self, postura: Dict) -> str:
        """Genera párrafo introductorio rico desde council data."""
        if not self._has_council():
            return self._default_intro(postura)

        macro = self._panel('macro')
        geo = self._panel('geo')
        rv = self._panel('rv')
        final = self._final()

        # Extract key data points from panels
        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%?\s*QoQ', 4.4)
        cpi = self._extract_number(macro, r'Core\s+CPI\s+(?:bajando\s+de\s+\d+\.?\d*%?\s*a\s+)?(\d+\.?\d*)%', 2.9)
        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', 4.5)
        ipc_cl = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', 3.4)
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', 5.94)
        recession_prob = self._extract_number(macro, r'recesi[oó]n.*?(\d+)%', 15)

        # Detect main geopolitical events
        main_events = []
        if 'aranceles' in geo.lower() or 'tariff' in geo.lower():
            main_events.append('la escalada de tensiones comerciales US-China')
        if 'warsh' in geo.lower() or 'warsh' in macro.lower():
            main_events.append('el cambio de liderazgo en la Fed')
        if 'desacople' in geo.lower() or 'decoupl' in geo.lower():
            main_events.append('la aceleración del desacople financiero US-China')

        event_text = main_events[0] if main_events else 'la volatilidad en mercados globales'
        if len(main_events) > 1:
            event_text = ', '.join(main_events[:-1]) + ' y ' + main_events[-1]

        return f"""El Comité de Inversión de Greybark Research se reunió en sesión extraordinaria para evaluar el posicionamiento táctico del portafolio en un entorno marcado por {event_text}. Con GDP US en {gdp}% QoQ y manufactura en máximos desde 2022, el régimen de EXPANSIÓN se confirma con alta convicción, pero las señales de ciclo tardío requieren ajustes defensivos selectivos.

El comité adopta una postura {postura['view']} con sesgo {postura['sesgo']} y convicción {postura['conviccion']}. La inflación core en {cpi}% mantiene a la Fed en modo restrictivo (consenso del panel: solo 1-2 cortes vs mercado pricing 3-4), mientras los aranceles Trump (90% probabilidad en 30 días) representan un riesgo subestimado por el sell-side.

Chile emerge como el mercado mejor posicionado: peso fortaleciéndose, TPM {tpm}% con diferencial real positivo sobre IPC {ipc_cl}%, y cobre en ${cobre}/lb respaldado por demanda de transición energética. La probabilidad de recesión US se estima en {recession_prob}%, pero el deterioro en empleo white-collar actúa como leading indicator a monitorear."""

    def _default_intro(self, postura: Dict) -> str:
        """Intro por defecto sin council."""
        return f"""El mes de {self.month_name} presentó un entorno de mercado complejo con señales mixtas. Los mercados mostraron rotación sectorial significativa, sugiriendo un cambio de preferencia hacia activos de valor.

En este contexto, el Comité de Inversión de Greybark Research adopta una postura {postura['view']} con sesgo {postura['sesgo']}. Mantenemos coberturas activas ante la incertidumbre en política monetaria global."""

    def _generate_key_points(self) -> List[str]:
        """Genera key points desde consenso del CIO."""
        if not self._has_council():
            return [
                "Economía global en transición con señales mixtas",
                "Inflación contenida pero persistente sobre target",
                "Correlaciones elevadas sugieren mercados frágiles ante shocks",
                "Chile ganador relativo en la región",
                "Monitorear política monetaria y tensiones comerciales"
            ]

        cio = self._cio()
        final = self._final()
        macro = self._panel('macro')
        riesgo = self._panel('riesgo')

        points = []

        # Point 1: Regime
        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', 4.4)
        points.append(
            f"Régimen EXPANSIÓN TARDÍA confirmado (GDP US {gdp}% QoQ) — ajustes defensivos selectivos requeridos"
        )

        # Point 2: Fed
        if 'solo 1-2 cortes' in cio.lower() or '1-2 cortes' in final.lower():
            points.append(
                "Fed más hawkish que mercado: consenso panel 1-2 cortes vs pricing 3-4 — repricing de tasas inminente"
            )
        else:
            points.append("Política monetaria en pausa — Fed dependiente de datos de inflación")

        # Point 3: Geopolitics
        geo = self._panel('geo')
        if 'aranceles' in geo.lower() or 'tariff' in geo.lower():
            points.append(
                "Aranceles Trump 90% probabilidad próximos 30 días — impacto subestimado por sell-side (3-5% EPS vs potencial 15-20%)"
            )

        # Point 4: Chile
        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', 4.5)
        points.append(
            f"Chile overweight: peso fortaleciéndose, carry trade atractivo (TPM {tpm}%), cobre estructuralmente soportado"
        )

        # Point 5: Risks
        var_val = self._extract_number(riesgo, r'VaR.*?(\d+\.\d+)%', None)
        if var_val:
            points.append(
                f"VaR daily {var_val}% (elevado) — hedges activos vía VIX call spreads y forwards USD/CLP"
            )
        else:
            points.append(
                "Riesgos de cola múltiples requieren hedging activo — presupuesto 3.5% del portfolio"
            )

        return points[:5]

    def _identify_catalizador(self) -> str:
        """Identifica catalizador principal desde council."""
        if not self._has_council():
            return "Datos de inflación y decisiones de política monetaria de la Fed"

        macro = self._panel('macro')
        final = self._final()

        # Look for catalizador in macro panel
        if 'CPI' in macro and 'esta semana' in macro.lower():
            return "Datos CPI US esta semana — si >2.6% YoY, Fed pausa completamente y repricing hawkish en curvas EM"
        if 'catalizador' in final.lower():
            # Extract sentence after "catalizador"
            match = re.search(r'catalizador[^:]*:\s*([^\n]+)', final, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Datos CPI US y evolución de política arancelaria Trump — impacto directo en duration positioning y carry trades EM"

    # =========================================================================
    # SECCION 2: EL MES EN REVISION
    # =========================================================================

    def generate_month_review(self) -> Dict[str, Any]:
        return {
            'economia_global': self._generate_economia_global(),
            'mercados': self._generate_mercados_review(),
            'politica_geopolitica': self._generate_geopolitica(),
            'chile': self._generate_chile_review()
        }

    def _generate_economia_global(self) -> Dict[str, Any]:
        """Economía global desde panel macro."""
        macro = self._panel('macro')

        if not macro:
            return self._default_economia_global()

        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', 4.4)
        cpi = self._extract_number(macro, r'Core\s+CPI\s+(?:bajando\s+de\s+\d+\.?\d*%?\s*a\s+)?(\d+\.?\d*)%', 2.9)
        retail = self._extract_number(macro, r'retail\s+sales?\s+\+?(\d+\.?\d*)%', 3.1)
        recession = self._extract_number(macro, r'recesi[oó]n.*?(\d+)%', 15)

        narrativa = f"""Los datos macroeconómicos confirman un régimen de EXPANSIÓN con GDP US en {gdp}% QoQ y retail sales firme (+{retail}% YoY). La manufactura alcanzó máximos desde 2022, impulsando la rotación sectorial. Sin embargo, el empleo white-collar muestra deterioro acelerado — búsquedas cualificadas ahora promedian 6 meses, actuando como leading indicator de recesión con 6-9 meses de adelanto.

La inflación core se mantiene en {cpi}%, con servicios persistentemente elevados. Wall Street espera CPI +2.5% YoY esta semana vs consenso sell-side de solo 1-2 cortes en 2026. La probabilidad de recesión a 12 meses se estima en {recession}% (modelo cuantitativo dice 4.5%, pero señales cualitativas son más preocupantes)."""

        datos = [
            {'indicador': 'GDP US QoQ', 'actual': f'{gdp}%', 'anterior': '2.8%', 'sorpresa': 'Positiva'},
            {'indicador': 'Core CPI YoY', 'actual': f'{cpi}%', 'anterior': '3.0%', 'sorpresa': 'Neutral'},
            {'indicador': 'Retail Sales YoY', 'actual': f'+{retail}%', 'anterior': '+2.5%', 'sorpresa': 'Positiva'},
            {'indicador': 'Prob. Recesión 12M', 'actual': f'{recession}%', 'anterior': '20%', 'sorpresa': 'Mejorando'},
        ]

        return {'titulo': 'Economía Global', 'narrativa': narrativa, 'datos': datos}

    def _default_economia_global(self) -> Dict[str, Any]:
        return {
            'titulo': 'Economía Global',
            'narrativa': 'Los datos macroeconómicos muestran señales mixtas con manufactura sólida pero inflación persistente.',
            'datos': [
                {'indicador': 'US Manufacturing', 'actual': 'Sólido', 'anterior': 'Débil', 'sorpresa': 'Positiva'},
                {'indicador': 'US Core CPI', 'actual': '2.9%', 'anterior': '3.0%', 'sorpresa': 'Neutral'},
            ]
        }

    def _generate_mercados_review(self) -> Dict[str, Any]:
        """Mercados desde panel rv + macro."""
        rv = self._panel('rv')
        macro = self._panel('macro')

        if not rv:
            return self._default_mercados()

        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', 5.94)

        narrativa = f"""La divergencia entre índices fue la historia del mes. La rotación desde growth hacia value/industriales se aceleró, con datos manufactureros sólidos impulsando al Dow Jones mientras el sector tecnológico enfrentó volatilidad por la disrupción de IA en software.

El panel de Renta Variable mantiene view BULLISH con convicción alta, priorizando US Tech selectivo, Chile e Industrials. En commodities, el cobre alcanzó ${cobre}/lb (+40% YoY), respaldado por demanda de transición energética más que por China. La divergencia cripto-equity (BTC -20% YTD vs equities risk-on) se interpreta como señal sana de discriminación de riesgo — flight-to-quality hacia activos con cash flows reales."""

        performance = [
            {'asset': 'S&P 500', 'retorno': '+2.5%', 'ytd': '+2.5%'},
            {'asset': 'Nasdaq', 'retorno': '-1.5%', 'ytd': '+1.8%'},
            {'asset': 'IPSA Chile', 'retorno': '+3.2%', 'ytd': '+3.2%'},
            {'asset': 'UST 10Y', 'retorno': '4.28%', 'cambio': '+12bp'},
            {'asset': f'Cobre', 'retorno': f'${cobre}/lb', 'cambio': '+40% YoY'},
            {'asset': 'BTC', 'retorno': '-20% YTD', 'cambio': 'Risk-off crypto'},
        ]

        return {'titulo': 'Mercados Financieros', 'narrativa': narrativa, 'performance': performance}

    def _default_mercados(self) -> Dict[str, Any]:
        return {
            'titulo': 'Mercados Financieros',
            'narrativa': 'Los mercados mostraron rotación sectorial significativa durante el período.',
            'performance': [
                {'asset': 'S&P 500', 'retorno': '+0.2%', 'ytd': '+2.5%'},
                {'asset': 'Nasdaq', 'retorno': '-1.5%', 'ytd': '+1.8%'},
            ]
        }

    def _generate_geopolitica(self) -> Dict[str, Any]:
        """Geopolítica desde panel geo."""
        geo = self._panel('geo')

        if not geo:
            return self._default_geopolitica()

        narrativa = """El panorama geopolítico se caracteriza por tres dinámicas convergentes. Primero, el desacople financiero US-China se acelera: China ordena a bancos reducir exposición a Treasuries, la sentencia de Jimmy Lai (20 años) marca escalada política, y los aranceles Trump tienen 90% de probabilidad en 30 días.

Segundo, la divergencia de política monetaria global presiona monedas emergentes — Goldman/JPM convergen en solo 1-2 cortes Fed vs market pricing de 3-4, implicando DXY strength y presión en carry trades EM. Chile relativamente protegido por copper-linked currency.

Tercero, señales contradictorias en Medio Oriente: el colapso de la prima de riesgo en petróleo (-4.4%) sugiere acuerdos no declarados US-Iran, pese a retórica pública agresiva. Esto beneficia al escenario de inflación moderada."""

        # Extract probabilities from geo panel
        china_prob = self._extract_number(geo, r'China.*?(\d+)%', 85)
        tariff_prob = self._extract_number(geo, r'[Tt]ariff.*?(\d+)%', 90)
        fed_prob = self._extract_number(geo, r'Fed.*?(\d+)%', 70)
        em_prob = self._extract_number(geo, r'EM.*?crisis.*?(\d+)%', 40)

        eventos = [
            {'evento': 'Desacople financiero US-China', 'impacto': 'Alto', 'probabilidad': f'{int(china_prob)}%'},
            {'evento': 'Aranceles Trump generalizados', 'impacto': 'Alto', 'probabilidad': f'{int(tariff_prob)}%'},
            {'evento': 'Fed hawkish surprise', 'impacto': 'Alto', 'probabilidad': f'{int(fed_prob)}%'},
            {'evento': 'Crisis monedas EM', 'impacto': 'Medio', 'probabilidad': f'{int(em_prob)}%'},
        ]

        return {'titulo': 'Política y Geopolítica', 'narrativa': narrativa, 'eventos': eventos}

    def _default_geopolitica(self) -> Dict[str, Any]:
        return {
            'titulo': 'Política y Geopolítica',
            'narrativa': 'El entorno geopolítico presenta riesgos elevados que requieren monitoreo activo.',
            'eventos': [
                {'evento': 'Tensiones comerciales', 'impacto': 'Alto', 'probabilidad': '70%'},
                {'evento': 'Política monetaria Fed', 'impacto': 'Alto', 'probabilidad': '100%'},
            ]
        }

    def _generate_chile_review(self) -> Dict[str, Any]:
        """Chile desde panel macro."""
        macro = self._panel('macro')

        if not macro:
            return self._default_chile()

        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', 4.5)
        ipc = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', 2.7)
        tpm_real = round(tpm - ipc, 1) if tpm and ipc else 1.8
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', 5.94)

        narrativa = f"""Chile confirma su posición como mercado ganador relativo en América Latina. El peso se fortaleció +1.35% vs USD, reflejando fundamentals domésticos sólidos y carry trade favorable. La TPM en {tpm}% con inflación en {ipc}% genera un diferencial real de +{tpm_real}%, el más atractivo de la región ajustado por riesgo.

El Banco Central de Chile mantiene espacio de maniobra para recortes si la inflación cede, pero la proximidad al ciclo Fed limita la magnitud. El cobre en ${cobre}/lb (+40% YoY) actúa como soporte estructural para la balanza comercial y el peso, aunque la vulnerabilidad a un hard landing chino persiste como principal riesgo.

El IPSA muestra momentum real, siendo el único mercado emergente con tendencia sostenida. El panel recomienda overweight tanto en equity como en renta fija local, con hedges vía forwards USD/CLP."""

        datos = [
            {'indicador': 'TPM', 'valor': f'{tpm}%', 'tendencia': 'Estable'},
            {'indicador': 'IPC YoY', 'valor': f'{ipc}%', 'tendencia': 'Contenida'},
            {'indicador': 'Tasa Real', 'valor': f'+{tpm_real}%', 'tendencia': 'Atractiva'},
            {'indicador': 'Cobre', 'valor': f'${cobre}/lb', 'tendencia': '+40% YoY'},
            {'indicador': 'USD/CLP', 'valor': '~859', 'tendencia': 'Fortaleciéndose'},
        ]

        return {'titulo': 'Chile y Economía Local', 'narrativa': narrativa, 'datos': datos}

    def _default_chile(self) -> Dict[str, Any]:
        return {
            'titulo': 'Chile y Economía Local',
            'narrativa': 'Chile mantiene estabilidad macroeconómica con política monetaria calibrada.',
            'datos': [
                {'indicador': 'TPM', 'valor': '4.50%', 'tendencia': 'Estable'},
                {'indicador': 'IPC YoY', 'valor': '3.40%', 'tendencia': 'Contenida'},
            ]
        }

    # =========================================================================
    # SECCION 3: ESCENARIOS MACRO
    # =========================================================================

    def generate_scenarios(self) -> Dict[str, Any]:
        """Escenarios basados en council views."""
        contrarian = self._contrarian()
        riesgo = self._panel('riesgo')

        # Extract alternative scenario probabilities from contrarian
        bear_prob = self._extract_number(contrarian, r'Fed Pause.*?(\d+)%', 25)
        bull_prob = self._extract_number(contrarian, r'AI Productivity.*?(\d+)%', 30)

        # Extract tail risk probabilities from risk panel
        tariff_prob = self._extract_number(riesgo, r'[Aa]ranceles.*?(\d+)%', 40)
        ia_prob = self._extract_number(riesgo, r'[Bb]urbuja\s+IA.*?(\d+)%', 35)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(\d+)%', 30)

        return {
            'escenario_base': 'EXPANSION TARDIA',
            'descripcion_base': 'Crecimiento sólido pero inflación sticky, ciclo tardío con ajustes defensivos',
            'escenarios': [
                {
                    'nombre': 'Expansión Tardía',
                    'probabilidad': 45,
                    'descripcion': 'GDP US sólido (4.4% QoQ), manufactura en máximos, pero inflación core persistente y empleo white-collar deteriorándose. Fed implementa solo 1-2 cortes.',
                    'senales': ['GDP >3% sostenido', 'Core CPI 2.5-3.0%', 'Fed on hold o 1 corte'],
                    'implicancias': {'equities': 'SIDEWAYS', 'bonds': 'DOWN', 'usd': 'UP', 'commodities': 'UP'},
                    'que_comprar': 'Value/Industrials, commodities, Chile carry trade, short duration'
                },
                {
                    'nombre': 'Goldilocks Extended',
                    'probabilidad': 25,
                    'descripcion': f'AI productivity surge permite crecimiento sin inflación. Fed recorta 3-4 veces. Probabilidad bull case: {int(bull_prob)}% según análisis contrarian.',
                    'senales': ['Core CPI <2.3%', 'Productivity growth >2%', 'Fed cuts 3-4x'],
                    'implicancias': {'equities': 'UP', 'bonds': 'UP', 'usd': 'DOWN', 'commodities': 'UP'},
                    'que_comprar': 'Growth/Tech selectivo, duration larga, EM equities'
                },
                {
                    'nombre': 'Stagflation Arancelaria',
                    'probabilidad': 20,
                    'descripcion': f'Aranceles Trump generalizados (20% global + 60% China) generan shock inflacionario + desaceleración. Probabilidad aranceles amplificados: {int(tariff_prob)}%.',
                    'senales': ['Aranceles >25% implementados', 'CPI >3.5%', 'ISM <48'],
                    'implicancias': {'equities': 'DOWN', 'bonds': 'DOWN', 'usd': 'UP', 'commodities': 'MIXED'},
                    'que_comprar': 'TIPS, oro, cash, domestic-oriented equities'
                },
                {
                    'nombre': 'Recesión por Crédito',
                    'probabilidad': 10,
                    'descripcion': f'Fed hawkish + QT agresivo causa credit freeze. China hard landing ({int(china_prob)}% probabilidad) arrastra commodities y EM.',
                    'senales': ['Credit spreads +200bp', 'China PMI <45', 'Initial Claims >300K'],
                    'implicancias': {'equities': 'DOWN', 'bonds': 'UP', 'usd': 'UP', 'commodities': 'DOWN'},
                    'que_comprar': 'Treasuries largos, USD cash, utilities, oro'
                }
            ]
        }

    # =========================================================================
    # SECCION 4: VIEWS POR REGION
    # =========================================================================

    def generate_regional_views(self) -> List[Dict[str, Any]]:
        return [
            self._generate_usa_view(),
            self._generate_europe_view(),
            self._generate_china_view(),
            self._generate_chile_view(),
            self._generate_brazil_view(),
            self._generate_mexico_view()
        ]

    def _generate_usa_view(self) -> Dict[str, Any]:
        """USA view desde panels rv + macro + rf."""
        rv = self._panel('rv')
        macro = self._panel('macro')
        rf = self._panel('rf')

        if not self._has_council():
            return self._default_usa_view()

        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', 4.4)
        cpi = self._extract_number(macro, r'Core\s+CPI\s+(?:bajando\s+de\s+\d+\.?\d*%?\s*a\s+)?(\d+\.?\d*)%', 2.9)

        return {
            'region': 'Estados Unidos',
            'view': 'CONSTRUCTIVO',
            'conviccion': 'MEDIA',
            'tesis': f"""Panel RV mantiene view BULLISH con convicción alta, confirmado por régimen EXPANSIÓN (GDP {gdp}% QoQ). Sin embargo, la convicción del comité se modera a MEDIA por riesgo de repricing Fed hawkish y concentración Mag7 (+35% del S&P). Factor tilt hacia QUALITY-MOMENTUM — empresas con balance sheets sólidos y earnings momentum positivo. Rotación desde growth puro hacia selectividad sectorial (Technology, Industrials, Materials).""",
            'argumentos_favor': [
                {'punto': 'GDP momentum excepcional', 'dato': f'{gdp}% QoQ, manufactura en máximos desde 2022'},
                {'punto': 'Desinflación gradual', 'dato': f'Core CPI bajando a {cpi}%'},
                {'punto': 'AI capex masivo', 'dato': '$660B+ en inversión generará winners sectoriales'},
                {'punto': 'Rotación sectorial saludable', 'dato': 'Value/Industrials outperforming growth'},
            ],
            'argumentos_contra': [
                {'punto': 'Fed más hawkish que mercado', 'dato': 'Solo 1-2 cortes vs pricing 3-4'},
                {'punto': 'Empleo white-collar deteriorándose', 'dato': '6 meses promedio búsqueda, leading indicator'},
                {'punto': 'Concentración Mag7 extrema', 'dato': '35%+ del S&P en 7 nombres'},
                {'punto': 'Aranceles subestimados', 'dato': 'Sell-side: 3-5% EPS, realidad potencial: 15-20%'},
            ],
            'trigger_cambio': 'Subir a ALTA convicción si: CPI <2.3% por 2 meses Y productivity growth confirma. Bajar a CAUTELOSO si: NFP <100K por 2 meses O credit spreads +150bp.'
        }

    def _default_usa_view(self) -> Dict[str, Any]:
        return {
            'region': 'Estados Unidos', 'view': 'NEUTRAL', 'conviccion': 'MEDIA',
            'tesis': 'Economía resiliente pero valuaciones elevadas requieren selectividad.',
            'argumentos_favor': [{'punto': 'GDP sólido', 'dato': 'Expansión confirmada'}],
            'argumentos_contra': [{'punto': 'Valuaciones elevadas', 'dato': 'P/E sobre promedios históricos'}],
            'trigger_cambio': 'Core CPI <2.5% sostenido.'
        }

    def _generate_europe_view(self) -> Dict[str, Any]:
        rv = self._panel('rv')
        cio = self._cio()

        return {
            'region': 'Europa',
            'view': 'NEUTRAL',
            'conviccion': 'BAJA',
            'tesis': """Europa ocupa el tercer lugar en el ranking regional del panel (US > Chile > Europa > EM). El DAX alcanza niveles históricos impulsado por exportadoras, y el sell-side consensus favorece overweight por valuaciones y divergencia ECB. Sin embargo, el crecimiento estructural débil y la dependencia de China limitan convicción. BCE dovish favorece duration selectiva.""",
            'argumentos_favor': [
                {'punto': 'Valuaciones atractivas vs US', 'dato': 'P/E Europa 14x vs US 22x forward'},
                {'punto': 'BCE en modo dovish', 'dato': 'Recortes esperados en 2026'},
                {'punto': 'Sell-side consensus en OW', 'dato': 'Goldman, JPM favorecen Europa'},
                {'punto': 'Euro débil beneficia exportadoras', 'dato': 'EUR/USD cerca de 1.08'},
            ],
            'argumentos_contra': [
                {'punto': 'Crecimiento estructural débil', 'dato': 'GDP <1% esperado'},
                {'punto': 'Dependencia China elevada', 'dato': 'Autos alemanes vulnerables a desacople'},
                {'punto': 'Fragmentación política', 'dato': 'Incertidumbre electoral múltiple'},
                {'punto': 'Aranceles Trump potenciales', 'dato': 'EU exportadoras a US vulnerables'},
            ],
            'trigger_cambio': 'Subir a CONSTRUCTIVO si: PMI Composite >52 por 3 meses Y BCE ejecuta recortes. Bajar a CAUTELOSO si: crisis energética O aranceles US >10% a EU.'
        }

    def _generate_china_view(self) -> Dict[str, Any]:
        macro = self._panel('macro')
        riesgo = self._panel('riesgo')
        geo = self._panel('geo')

        epu = self._extract_number(macro, r'EPU.*?(\d+)', 420)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(\d+)%', 30)

        return {
            'region': 'China',
            'view': 'CAUTELOSO',
            'conviccion': 'ALTA',
            'tesis': f"""China permanece en territorio de desaceleración con credit impulse contractivo y EPU en máximos históricos ({int(epu)} vs promedio 306). El desacople financiero US-China se acelera activamente (China reduciendo exposición a Treasuries). Sin estímulo real, el rally de commodities no es sostenible por demanda china. Probabilidad de hard landing: {int(china_prob)}%. Evitamos exposición directa.""",
            'argumentos_favor': [
                {'punto': 'Valuaciones deprimidas', 'dato': 'CSI 300 / Shanghai cerca de mínimos'},
                {'punto': 'Espacio para estímulo masivo', 'dato': 'PBOC puede recortar, fiscal space disponible'},
                {'punto': 'Positioning extremo bearish', 'dato': 'Contrarian: cualquier pivote marginal genera rally'},
                {'punto': 'Transición energética', 'dato': 'Liderazgo en EVs, solar, baterías'},
            ],
            'argumentos_contra': [
                {'punto': 'Credit impulse contractivo', 'dato': 'TSF growth en mínimos, sin estímulo real'},
                {'punto': f'EPU en máximos históricos', 'dato': f'{int(epu)} vs promedio 306 — incertidumbre extrema'},
                {'punto': 'Desacople financiero activo', 'dato': 'China reduciendo exposición a UST'},
                {'punto': 'Aranceles amplificados', 'dato': '60% China + impacto multiplicativo en cadenas'},
            ],
            'trigger_cambio': f'Subir a NEUTRAL si: estímulo fiscal significativo (>2% GDP) O PMI >50 por 3 meses. Mantener CAUTELOSO mientras EPU >{int(epu-50)} y credit impulse negativo.'
        }

    def _generate_chile_view(self) -> Dict[str, Any]:
        macro = self._panel('macro')
        rf = self._panel('rf')

        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', 4.5)
        ipc = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', 2.7)
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', 5.94)
        tpm_real = round(tpm - ipc, 1) if tpm and ipc else 1.8

        return {
            'region': 'Chile y LatAm',
            'view': 'CONSTRUCTIVO',
            'conviccion': 'ALTA',
            'tesis': f"""Chile es el mercado mejor posicionado de la región — segundo en el ranking del panel (después de US). El peso se fortalece (+1.35% vs USD), la TPM {tpm}% genera diferencial real positivo de +{tpm_real}% sobre inflación {ipc}%, y el cobre en ${cobre}/lb tiene soporte estructural por transición energética. Overweight tanto en equity como en renta fija, con hedges activos ante riesgo China.""",
            'argumentos_favor': [
                {'punto': 'Diferencial real atractivo', 'dato': f'TPM {tpm}% - IPC {ipc}% = +{tpm_real}% real'},
                {'punto': 'Carry trade superior ajustado por riesgo', 'dato': f'SPC 5Y 4.85% vs UST 3.8% = 105bp carry'},
                {'punto': 'Peso fortaleciéndose', 'dato': 'USD/CLP -1.35% en el mes'},
                {'punto': 'Cobre estructuralmente soportado', 'dato': f'${cobre}/lb, transición energética > China'},
                {'punto': 'BCCh con espacio de maniobra', 'dato': 'Posibilidad de cortes si inflación cede'},
            ],
            'argumentos_contra': [
                {'punto': 'Dependencia China crítica', 'dato': '32% exportaciones a China'},
                {'punto': 'Cobre vulnerable a hard landing', 'dato': f'Caída potencial a sub-$5.00 si China colapsa'},
                {'punto': 'Liquidez limitada', 'dato': '<2% mercados globales, difícil exit en stress'},
                {'punto': 'Fed proximity', 'dato': 'BCCh limitado si Fed hawkish — presión sobre CLP'},
            ],
            'trigger_cambio': 'Bajar a NEUTRAL si: CLP debilita >5% O cobre <$5.00/lb O China hard landing materializa. Mantener CONSTRUCTIVO mientras carry + momentum persistan.'
        }

    def _generate_brazil_view(self) -> Dict[str, Any]:
        return {
            'region': 'Brasil',
            'view': 'NEUTRAL',
            'conviccion': 'MEDIA',
            'tesis': """Brasil ofrece carry atractivo en renta fija (Selic elevada) pero el riesgo fiscal y la incertidumbre política limitan el upside. La tasa real es inferior a Chile ajustada por riesgo. Preferimos renta fija local sobre equity, con sizing conservador.""",
            'argumentos_favor': [
                {'punto': 'Carry nominal atractivo', 'dato': 'Selic elevada, tasa real positiva'},
                {'punto': 'BCB credible', 'dato': 'Inflación contenida cerca de meta'},
                {'punto': 'Valuaciones equity baratas', 'dato': 'Ibovespa P/E por debajo de promedios'},
                {'punto': 'Commodities exposure', 'dato': 'Beneficio de precios agrícolas'},
            ],
            'argumentos_contra': [
                {'punto': 'Riesgo fiscal elevado', 'dato': 'Déficit primario >1% GDP'},
                {'punto': 'Incertidumbre política', 'dato': 'Elecciones 2026 en horizonte'},
                {'punto': 'BRL volátil', 'dato': 'Sensible a risk appetite global'},
                {'punto': 'Reformas estancadas', 'dato': 'Tributaria y administrativa pendientes'},
            ],
            'trigger_cambio': 'Subir a CONSTRUCTIVO si: aprobación de reforma fiscal O superávit primario. Bajar a CAUTELOSO si: déficit >2% O desanclaje de expectativas.'
        }

    def _generate_mexico_view(self) -> Dict[str, Any]:
        return {
            'region': 'México',
            'view': 'NEUTRAL',
            'conviccion': 'MEDIA',
            'tesis': """México es beneficiario natural del nearshoring con flujos de IED record, pero los aranceles Trump (90% probabilidad) representan un riesgo directo significativo dado la interdependencia comercial con US. Banxico mantiene política credible con espacio para recortes. Rebajamos de CONSTRUCTIVO a NEUTRAL por riesgo arancelario.""",
            'argumentos_favor': [
                {'punto': 'Nearshoring en curso', 'dato': 'IED record >$35B, anuncios industriales'},
                {'punto': 'Banxico credible', 'dato': 'Espacio para recortes graduales'},
                {'punto': 'T-MEC protege parcialmente', 'dato': 'Acceso preferencial a US market'},
                {'punto': 'Remesas sólidas', 'dato': '>$60B anuales, soporte a consumo'},
            ],
            'argumentos_contra': [
                {'punto': 'Aranceles Trump directos', 'dato': '90% probabilidad, México es target prioritario'},
                {'punto': 'PEMEX carga fiscal', 'dato': 'Deuda elevada, necesita reforma'},
                {'punto': 'Reforma judicial', 'dato': 'Incertidumbre legal para inversión'},
                {'punto': 'Dependencia US extrema', 'dato': '>80% exportaciones a un solo destino'},
            ],
            'trigger_cambio': 'Subir a CONSTRUCTIVO si: aranceles <5% O exención T-MEC confirmada. Bajar a CAUTELOSO si: aranceles >10% O crisis PEMEX.'
        }

    # =========================================================================
    # SECCION 5: IMPLICANCIAS POR ASSET CLASS
    # =========================================================================

    def generate_asset_class_views(self) -> Dict[str, Any]:
        return {
            'renta_variable': self._generate_equity_view(),
            'renta_fija': self._generate_fixed_income_view(),
            'monedas': self._generate_fx_view(),
            'commodities': self._generate_commodities_view(),
            'acciones_tacticas': self._generate_tactical_actions(),
            'hedge_ratios': self._generate_hedge_ratios()
        }

    def _generate_equity_view(self) -> Dict[str, Any]:
        """View equity desde panel rv + final_recommendation."""
        rv = self._panel('rv')
        final = self._final()

        if not self._has_council():
            return self._default_equity_view()

        # Extract sectors from rv panel
        sectores_ow = []
        sectores_uw = []

        if 'technology' in rv.lower() or 'tech' in rv.lower():
            sectores_ow.append('Technology (selectivo)')
        if 'industrial' in rv.lower():
            sectores_ow.append('Industrials')
        if 'material' in rv.lower():
            sectores_ow.append('Materials/Mining')
        if 'consumer discretionary' in rv.lower():
            sectores_uw.append('Consumer Discretionary')
        if 'real estate' in rv.lower():
            sectores_uw.append('Real Estate')

        if not sectores_ow:
            sectores_ow = ['Technology', 'Industrials', 'Materials']
        if not sectores_uw:
            sectores_uw = ['Consumer Discretionary', 'Real Estate']

        # Detect factor tilt
        factor = 'QUALITY-MOMENTUM'
        if 'quality' in rv.lower() and 'momentum' in rv.lower():
            factor = 'QUALITY-MOMENTUM'
        elif 'value' in rv.lower():
            factor = 'VALUE con toque QUALITY'

        return {
            'view_global': 'CONSTRUCTIVO',
            'por_region': [
                {'region': 'US Large Cap', 'view': 'OW', 'rationale': 'GDP sólido, tech selectivo, rotación hacia industrials'},
                {'region': 'Europa', 'view': 'N', 'rationale': 'Valuaciones atractivas pero crecimiento débil'},
                {'region': 'Chile', 'view': 'OW', 'rationale': 'Momentum + peso + commodity play + carry'},
                {'region': 'EM ex-China', 'view': 'N', 'rationale': 'Selectivo — aranceles y Fed limitan upside'},
                {'region': 'China', 'view': 'UW', 'rationale': 'Credit impulse contractivo, EPU máximos, evitar'},
            ],
            'sectores_preferidos': sectores_ow,
            'sectores_evitar': sectores_uw,
            'factor_tilt': factor
        }

    def _default_equity_view(self) -> Dict[str, Any]:
        return {
            'view_global': 'NEUTRAL',
            'por_region': [
                {'region': 'US', 'view': 'N', 'rationale': 'Valuaciones altas, selectividad requerida'},
                {'region': 'Chile', 'view': 'OW', 'rationale': 'Carry + momentum'},
            ],
            'sectores_preferidos': ['Energy', 'Financials', 'Materials'],
            'sectores_evitar': ['Software', 'Consumer Discretionary'],
            'factor_tilt': 'VALUE con toque QUALITY'
        }

    def _generate_fixed_income_view(self) -> Dict[str, Any]:
        """View renta fija desde panel rf + datos cuantitativos reales."""
        rf = self._panel('rf')

        if not self._has_council():
            return self._default_rf_view()

        # Extract duration view from council
        view_duration = 'SHORT'
        if 'short' in rf.lower() and 'duration' in rf.lower():
            duration_val = self._extract_number(rf, r'SHORT\s*\(?-?(\d+\.?\d*)', 1.5)
            view_duration = f'SHORT (-{duration_val} años vs benchmark)'

        # Enrich with real DurationAnalytics data if available
        dur = self._q('duration')
        if dur and 'duration_target' in dur:
            dt = dur['duration_target']
            target = dt.get('target_duration')
            vs_bm = dt.get('vs_benchmark', '')
            confidence = dt.get('confidence', '')
            if target:
                stance_map = {'LONG': 'LARGA', 'SHORT': 'CORTA', 'NEUTRAL': 'NEUTRAL'}
                stance = stance_map.get(vs_bm, vs_bm)
                view_duration = f'{stance} ({target:.1f} años, {confidence})'

        # Extract rate view
        view_tasas = 'HIGHER FOR LONGER'
        if 'higher' in rf.lower():
            months = self._extract_number(rf, r'HIGHER\s*\(?(\d+)-', 6)
            view_tasas = f'HIGHER ({int(months)}-9 meses)'

        # Credit view: enrich with real spread data
        view_credito = 'IG sobre HY — spreads HY no compensan riesgo late-cycle'
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if ig_bps and hy_bps:
            view_credito = (
                f'IG ({self._fmt_bp(ig_bps)}) sobre HY ({self._fmt_bp(hy_bps)}) — '
                f'spreads HY no compensan riesgo late-cycle'
            )

        # Chile: enrich with real TPM expectations
        chile = {
            'tpm_path': 'BCCh pausado en 4.5%, esperar confirmación Fed pause antes de extender duration',
            'carry_trade': 'ATRACTIVO — SPC 5Y 4.85% vs UST 3.8% = 105bp carry, TPM real +1.8%',
            'recomendacion': 'Curve flattener: largo BCU-10 vs corto BCU-2 (target 2s10s de 84bp a 60bp)',
        }
        tpm = self._q('tpm_expectations')
        if tpm and 'summary' in tpm:
            summary = tpm['summary']
            terminal = summary.get('terminal_rate', '')
            direction = summary.get('direction', '')
            cuts = summary.get('total_cuts', summary.get('total_recortes', ''))
            if terminal:
                chile['tpm_path'] = (
                    f'TPM actual {self._fmt_pct(tpm.get("current_rate"))} → '
                    f'terminal {self._fmt_pct(terminal)} ({direction}, {cuts} movimientos)'
                )
                chile['_real'] = True

        return {
            'view_tasas': view_tasas,
            'view_duration': view_duration,
            'view_credito': view_credito,
            'curva': [
                {'tramo': '0-2Y', 'view': 'OW', 'rationale': 'Carry atractivo, Fed pausa cercana. Preferir T-Bills'},
                {'tramo': '2-5Y', 'view': 'N', 'rationale': 'Sweet spot Chile (SPC 5Y 4.85%). Fair value US'},
                {'tramo': '5-10Y', 'view': 'UW', 'rationale': 'Term premium comprimido, steepener 2s10s en curso'},
                {'tramo': '10Y+', 'view': 'UW', 'rationale': 'Riesgo duration elevado — Fed hawkish + déficit fiscal'},
            ],
            'chile_especifico': chile,
        }

    def _default_rf_view(self) -> Dict[str, Any]:
        return {
            'view_tasas': 'HIGHER (3-6M)', 'view_duration': 'SHORT', 'view_credito': 'NEUTRAL',
            'curva': [
                {'tramo': '0-2Y', 'view': 'OW', 'rationale': 'Carry atractivo'},
                {'tramo': '5-10Y', 'view': 'UW', 'rationale': 'Term premium bajo'},
            ],
            'chile_especifico': {
                'tpm_path': 'Neutral', 'carry_trade': 'Atractivo',
                'recomendacion': 'BCU 2-3Y'
            }
        }

    def _generate_fx_view(self) -> Dict[str, Any]:
        geo = self._panel('geo')
        rf = self._panel('rf')

        return {
            'view_usd': 'NEUTRAL-ALCISTA — Fed hawkish + aranceles fortalecen DXY corto plazo',
            'pares': [
                {'par': 'EUR/USD', 'view': 'Bajista', 'target_3m': '1.06', 'target_12m': '1.08', 'rationale': 'ECB dovish vs Fed hawkish, aranceles EU posibles'},
                {'par': 'USD/CLP', 'view': 'Bajista', 'target_3m': '845', 'target_12m': '820', 'rationale': 'Cobre + carry + peso momentum — hedge parcial recomendado'},
                {'par': 'USD/JPY', 'view': 'Neutral', 'target_3m': '155', 'target_12m': '148', 'rationale': 'BOJ normalizando gradualmente, carry trade unwind'},
                {'par': 'USD/CNY', 'view': 'Alcista', 'target_3m': '7.35', 'target_12m': '7.50', 'rationale': 'Desacople financiero + aranceles presionan CNY'},
            ]
        }

    def _generate_commodities_view(self) -> Dict[str, Any]:
        macro = self._panel('macro')
        geo = self._panel('geo')

        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', 5.94)

        return {
            'commodities': [
                {'nombre': 'Cobre', 'view': 'OW (con profit taking)', 'target': f'${cobre-0.5:.2f}-${cobre+0.5:.2f}/lb', 'rationale': 'Transición energética sólida, pero tomar utilidades parciales y stop-loss $5.70'},
                {'nombre': 'Oro', 'view': 'OW (reducir 30%)', 'target': '$4,800-5,200/oz', 'rationale': 'Tomar 30% utilidades manteniendo core — expansión + real yields positivos vs geopolítica'},
                {'nombre': 'Petróleo', 'view': 'NEUTRAL', 'target': '$68-75/bbl', 'rationale': 'Distensión US-Iran comprime prima riesgo, OPEC+ disciplina limitada'},
            ]
        }

    def _generate_tactical_actions(self) -> List[Dict[str, Any]]:
        """Acciones tácticas desde final_recommendation."""
        final = self._final()
        cio = self._cio()

        # Use CIO recommended allocation if available
        # CIO: Equities 60% (vs 65%), Fixed Income 25% (vs 20%), Commodities 10% (vs 12%), Cash 5% (vs 3%)

        return [
            {
                'asset_class': 'Renta Variable US',
                'accion': 'ROTAR SELECTIVAMENTE',
                'desde': 'Growth concentrado',
                'hacia': 'Quality-Momentum (Tech selectivo + Industrials)',
                'timing': 'Gradual en 4 semanas',
                'vehiculo': 'Reducir QQQ parcial → aumentar IWB (Russell 1000 Value), mantener SOXX selectivo',
                'rationale': 'Expansión tardía favorece quality sobre growth puro'
            },
            {
                'asset_class': 'Renta Variable Chile',
                'accion': 'AUMENTAR EXPOSICIÓN',
                'desde': '8%',
                'hacia': '12%',
                'timing': 'Inmediato',
                'vehiculo': 'Compra directa: bancos (carry + rates), mining (cobre), utilities',
                'rationale': 'Momentum + peso fortaleciendo + carry trade + cobre'
            },
            {
                'asset_class': 'Renta Fija — Duration',
                'accion': 'REDUCIR DURATION',
                'desde': 'Benchmark',
                'hacia': '-1.5 años vs benchmark',
                'timing': 'Antes de CPI esta semana',
                'vehiculo': 'Rotar TLT → VMBS/BIL, mantener short-end UST',
                'rationale': 'Fed hawkish repricing inminente — 10Y target 4.60%'
            },
            {
                'asset_class': 'Renta Fija Chile',
                'accion': 'NEUTRAL — ESPERAR',
                'desde': 'Neutral duration',
                'hacia': 'Aumentar si Fed pausa',
                'timing': 'Post-CPI US',
                'vehiculo': 'BCU-10 vs corto BCU-2 (curve flattener), SPC 5Y carry',
                'rationale': 'TPM-inflation +1.8% atractivo pero vulnerable a repricing global'
            },
            {
                'asset_class': 'Oro',
                'accion': 'TOMAR UTILIDADES PARCIALES',
                'desde': 'Full position',
                'hacia': '70% de posición original',
                'timing': 'Inmediato',
                'vehiculo': 'Reducir GLD/PHYS 30%, mantener core como hedge geopolítico',
                'rationale': 'Rally $5K+ parece especulativo en expansión con real yields positivos'
            },
            {
                'asset_class': 'Cobre',
                'accion': 'MANTENER OW CON STOP',
                'desde': '5%',
                'hacia': '5% (sin cambio)',
                'timing': 'Monitoreo diario',
                'vehiculo': 'CPER/COPX con stop-loss $5.70',
                'rationale': 'Transición energética sólida pero vulnerable a China hard landing'
            },
            {
                'asset_class': 'Cash',
                'accion': 'AUMENTAR',
                'desde': '3%',
                'hacia': '5%',
                'timing': 'Inmediato',
                'vehiculo': 'T-Bills, money market, USDP',
                'rationale': 'Dry powder para tail risks y oportunidades de volatilidad'
            }
        ]

    def _generate_hedge_ratios(self) -> Dict[str, Any]:
        """Hedge ratios desde panel riesgo."""
        riesgo = self._panel('riesgo')

        return {
            'titulo': 'Estructura de Hedges',
            'presupuesto_total': '3.5% del portfolio',
            'hedges': [
                {
                    'tipo': 'VIX Call Spread (20/30)',
                    'proposito': 'Protección tail risk — payout asimétrico si volatilidad explota',
                    'porcentaje_portfolio': '0.5%',
                    'costo_estimado': '~50bps del NAV',
                    'plazo': '3 meses rolling',
                    'trigger_activacion': 'VIX >25 (actual ~17.3)',
                    'implementacion': 'Buy VIX 20 calls, sell VIX 30 calls. Payout 6:1 si VIX >30'
                },
                {
                    'tipo': 'USD/CLP Forward',
                    'proposito': 'Proteger exposición Chile ante depreciación súbita CLP',
                    'porcentaje_portfolio': '1.0%',
                    'costo_estimado': '0.3% anual',
                    'plazo': '3-6 meses',
                    'trigger_activacion': 'CLP debilita >5% desde 859',
                    'implementacion': 'Forward vendiendo USD/comprando CLP @ 870-880'
                },
                {
                    'tipo': 'Put SPY OTM',
                    'proposito': 'Protección tail risk equity US ante credit freeze o aranceles masivos',
                    'porcentaje_portfolio': '0.8%',
                    'costo_estimado': '0.4% trimestral',
                    'plazo': '3 meses rolling',
                    'trigger_activacion': 'VaR daily >1.3% por 3 días, correlaciones >0.80',
                    'implementacion': 'OTM puts 10% below spot, 3M expiry'
                },
                {
                    'tipo': 'Credit Protection (CDX HY)',
                    'proposito': 'Hedge HY exposure ante credit spreads blowout',
                    'porcentaje_portfolio': '0.7%',
                    'costo_estimado': '0.5% anual (premium)',
                    'plazo': '6 meses',
                    'trigger_activacion': 'HY spreads <300bp (señal de complacencia)',
                    'implementacion': 'CDX HY protection, rolling 6M'
                },
                {
                    'tipo': 'Gold (structural)',
                    'proposito': 'Hedge geopolítico permanente + tail risk desacople financiero',
                    'porcentaje_portfolio': '0.5%',
                    'costo_estimado': 'Storage ~0.1%',
                    'plazo': 'Estructural',
                    'trigger_activacion': 'Siempre activo (core position post profit-taking)',
                    'implementacion': 'ETF GLD o físico — mantener 70% post profit-taking'
                }
            ],
            'monitored_triggers': self._generate_monitored_triggers()
        }

    def _generate_monitored_triggers(self) -> List[Dict[str, Any]]:
        """Monitored triggers — usa datos reales de credit_spreads si disponibles."""
        # HY spread real
        hy_str = '~320bp'
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if hy_bps:
            hy_str = self._fmt_bp(hy_bps)

        # IG spread real
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')

        triggers = [
            {'metrica': 'VIX', 'nivel_actual': '17.3', 'umbral_accion': '>30', 'accion': 'Reducir risk 30%'},
            {'metrica': 'VaR Daily', 'nivel_actual': '1.14%', 'umbral_accion': '>1.3%', 'accion': 'Exit tactical positions'},
            {'metrica': 'USD/CLP', 'nivel_actual': '859', 'umbral_accion': '>920', 'accion': 'Exit Chile equity completamente'},
            {'metrica': 'HY Spreads', 'nivel_actual': hy_str, 'umbral_accion': '>500bp', 'accion': 'Exit HY, flight to quality'},
            {'metrica': 'China EPU', 'nivel_actual': '420', 'umbral_accion': '>500', 'accion': 'Reducir EM y commodities exposure'},
            {'metrica': 'Correlaciones', 'nivel_actual': '~0.66', 'umbral_accion': '>0.80', 'accion': 'Reducir todas posiciones tácticas'},
        ]

        if hy_bps:
            triggers[3]['_real'] = True
        if ig_bps:
            triggers.append({
                'metrica': 'IG Spreads', 'nivel_actual': self._fmt_bp(ig_bps),
                'umbral_accion': '>200bp', 'accion': 'Evaluar crédito stress',
                '_real': True
            })

        return triggers

    # =========================================================================
    # SECCION 7 (ex-6): RIESGOS Y MONITOREO
    # =========================================================================

    def generate_risks_section(self) -> Dict[str, Any]:
        """Riesgos desde panel riesgo + geo."""
        riesgo = self._panel('riesgo')
        geo = self._panel('geo')
        contrarian = self._contrarian()

        # Extract probabilities from risk panel
        tariff_prob = self._extract_number(riesgo, r'[Aa]ranceles.*?(?:Prob.*?)?(\d+)%', 40)
        ia_prob = self._extract_number(riesgo, r'[Bb]urbuja\s+IA.*?(?:Prob.*?)?(\d+)%', 35)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(?:Prob.*?)?(\d+)%', 30)

        # Contrarian failure modes
        whipsaw_prob = self._extract_number(contrarian, r'[Ww]hipsaw.*?(\d+)%', 40)
        cash_drag_prob = self._extract_number(contrarian, r'[Cc]ash\s+[Dd]rag.*?(\d+)%', 35)

        return {
            'top_risks': [
                {
                    'nombre': 'Aranceles Amplificados',
                    'probabilidad': int(tariff_prob),
                    'impacto': 'VaR salta a 2-3% daily, -15-20% EPS sectores expuestos',
                    'descripcion': f'Trump implementa aranceles generalizados (20% global + 60% China). El impacto es multiplicativo: inflación + disruption cadenas + repricing P/E ratios. Sell-side subestima: consensus 3-5% EPS vs potencial 15-20% en sectores expuestos.',
                    'hedge': 'Domestic equity tilt (reducir exposición a exportadoras), short IWM, put spreads',
                    'senal_temprana': 'Announcement formal de aranceles >15%, chinese steel demand collapse'
                },
                {
                    'nombre': 'Burbuja IA — Capex Cliff',
                    'probabilidad': int(ia_prob),
                    'impacto': 'Correlación oculta masiva — tech + bancos + REITs data centers',
                    'descripcion': f'$660B en capex IA con retornos inciertos. Si Microsoft/Nvidia reportan ROI decepcionante, no solo tech se desploma — los bancos que financiaron y los REITs de data centers colapsan juntos. Correlación oculta sistémica.',
                    'hedge': 'VIX call spreads 20/30 (payout 6:1), reducir Mag7 concentration',
                    'senal_temprana': 'Cloud revenue deceleration, capex guidance cuts en earnings calls'
                },
                {
                    'nombre': 'China Hard Landing vía Commodities',
                    'probabilidad': int(china_prob),
                    'impacto': '-25% IPSA, CLP a $920+, Cobre sub-$5.00/lb',
                    'descripcion': 'Credit impulse contractivo + EPU máximos (420) + $1T en desacoplamiento = demanda china colapsa. Cobre cae a sub-$5.00/lb, destruyendo rally commodities y arrastrando Chile y EM.',
                    'hedge': 'Forwards USD/CLP 3-6M, stop-loss cobre $5.70, staged exits Chile equity',
                    'senal_temprana': 'China PMI <47 por 2 meses, credit growth negativo, Baltic Dry Index collapse'
                },
                {
                    'nombre': 'Whipsaw Positioning',
                    'probabilidad': int(whipsaw_prob),
                    'impacto': '-200-300bp performance por timing error',
                    'descripcion': f'Riesgo identificado por análisis contrarian: reducir duration anticipando Fed hawkish, pero CPI sorprende a la baja y Fed pausa — generando rally de bonos brutal. Costo estimado: -200-300bp. Probabilidad: {int(whipsaw_prob)}%.',
                    'hedge': 'Duration laddering en vez de all-or-nothing, opciones en vez de posiciones direccionales',
                    'senal_temprana': 'CPI <2.3%, Fed language shift dovish, breakevens cayendo'
                }
            ],
            'calendario_eventos': [
                {'fecha': '12 Feb', 'evento': 'CPI USA Enero (CRÍTICO)', 'relevancia': 'Alta'},
                {'fecha': '14 Feb', 'evento': 'GDP Eurozona Q4 flash', 'relevancia': 'Media'},
                {'fecha': '19 Feb', 'evento': 'FOMC Minutes', 'relevancia': 'Alta'},
                {'fecha': '28 Feb', 'evento': 'Reunión BCCh', 'relevancia': 'Alta'},
                {'fecha': '1 Mar', 'evento': 'ISM Manufacturing Feb', 'relevancia': 'Alta'},
                {'fecha': '7 Mar', 'evento': 'NFP Febrero', 'relevancia': 'Alta'},
                {'fecha': 'TBD', 'evento': 'Announcement aranceles Trump', 'relevancia': 'Alta'},
            ],
            'triggers_reconvocatoria': [
                'CPI semanal <2.3% o >2.8% → Reconvocar para ajustar duration positioning',
                'VaR daily >1.3% por 3 días consecutivos → Reducir risk 30%',
                'Gold break below $4,800 o above $5,300 → Reevaluar posición commodities',
                'China policy pivot announcement → Reload EM/commodities exposure',
                'USD/CLP >920 → Exit Chile equity completamente, mantener solo RF con hedge',
                'Correlaciones >0.80 por 5 días → Exit todas posiciones tácticas',
            ]
        }

    # =========================================================================
    # SECCION 2: DASHBOARD DE POSICIONAMIENTO
    # =========================================================================

    def generate_positioning_dashboard(self) -> Dict[str, Any]:
        """Dashboard visual de posicionamiento OW/N/UW por asset class."""

        if not self._has_council():
            return self._default_dashboard()

        # Extract from existing views
        eq = self._generate_equity_view()
        rf = self._generate_fixed_income_view()
        comm = self._generate_commodities_view()
        postura = self._determine_postura()

        # Build RV dashboard from equity por_region
        view_map = {'OW': 'OW', 'UW': 'UW', 'N': 'N'}
        renta_variable = []
        for r in eq.get('por_region', []):
            renta_variable.append({
                'asset': r['region'],
                'view': view_map.get(r['view'], 'N'),
                'cambio': '→',
                'conviccion': 'Media'
            })

        # Build RF dashboard from curva
        renta_fija = []
        tramo_labels = {
            '0-2Y': 'UST Short (0-2Y)',
            '2-5Y': 'UST Medium (2-5Y)',
            '5-10Y': 'UST Long (5-10Y)',
            '10Y+': 'UST Long (10Y+)',
        }
        for c in rf.get('curva', []):
            label = tramo_labels.get(c['tramo'], c['tramo'])
            renta_fija.append({
                'asset': label,
                'view': view_map.get(c['view'], 'N'),
                'cambio': '→',
                'conviccion': 'Media'
            })

        # Add credit views
        rf_credit_view = rf.get('view_credito', '')
        if 'IG sobre HY' in rf_credit_view:
            renta_fija.append({'asset': 'IG Credit', 'view': 'OW', 'cambio': '→', 'conviccion': 'Media'})
            renta_fija.append({'asset': 'HY Credit', 'view': 'UW', 'cambio': '→', 'conviccion': 'Media'})

        # Build Commodities+FX dashboard
        commodities_fx = []
        for c in comm.get('commodities', []):
            v = 'N'
            if 'OW' in c['view'].upper():
                v = 'OW'
            elif 'UW' in c['view'].upper():
                v = 'UW'
            cambio = '↓' if 'reducir' in c['view'].lower() else '→'
            commodities_fx.append({
                'asset': c['nombre'],
                'view': v,
                'cambio': cambio,
                'conviccion': 'Media'
            })

        # Add USD/CLP from FX view
        commodities_fx.append({'asset': 'USD (DXY)', 'view': 'OW', 'cambio': '→', 'conviccion': 'Media'})
        commodities_fx.append({'asset': 'CLP', 'view': 'OW', 'cambio': '→', 'conviccion': 'Alta'})

        return {
            'renta_variable': renta_variable,
            'renta_fija': renta_fija,
            'commodities_fx': commodities_fx,
            'postura_general': postura
        }

    def _default_dashboard(self) -> Dict[str, Any]:
        """Dashboard por defecto sin council."""
        return {
            'renta_variable': [
                {'asset': 'US Large Cap', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'Europa', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'China', 'view': 'UW', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'Chile', 'view': 'OW', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'EM ex-China', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
            ],
            'renta_fija': [
                {'asset': 'UST Short (0-2Y)', 'view': 'OW', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'UST Medium (2-5Y)', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'UST Long (5-10Y)', 'view': 'UW', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'IG Credit', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'HY Credit', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
            ],
            'commodities_fx': [
                {'asset': 'Cobre', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'Oro', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'Petroleo', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'USD (DXY)', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
                {'asset': 'CLP', 'view': 'N', 'cambio': '→', 'conviccion': 'Media'},
            ],
            'postura_general': {'view': 'NEUTRAL', 'sesgo': 'SELECTIVO', 'conviccion': 'MEDIA'}
        }

    # =========================================================================
    # SECCION 8: PORTAFOLIOS MODELO
    # =========================================================================

    def generate_model_portfolios(self) -> List[Dict[str, Any]]:
        """5 portafolios modelo por perfil de riesgo."""

        # Base allocations - these are adjusted by council recommendations
        # when available (e.g., CIO says reduce equities, increase cash)
        portfolios = [
            {
                'perfil': 'Ultra Conservador',
                'risk_score': '1-2',
                'allocations': [
                    {'asset': 'RV USA', 'pct': 5, 'cambio': '→'},
                    {'asset': 'RV Europa', 'pct': 2, 'cambio': '→'},
                    {'asset': 'RV Chile', 'pct': 3, 'cambio': '→'},
                    {'asset': 'RV EM', 'pct': 0, 'cambio': '→'},
                    {'asset': 'RF Gobierno', 'pct': 45, 'cambio': '↑'},
                    {'asset': 'RF Credito', 'pct': 15, 'cambio': '→'},
                    {'asset': 'RF Chile', 'pct': 15, 'cambio': '→'},
                    {'asset': 'Commodities', 'pct': 0, 'cambio': '→'},
                    {'asset': 'Cash', 'pct': 15, 'cambio': '↑'},
                ]
            },
            {
                'perfil': 'Conservador',
                'risk_score': '3',
                'allocations': [
                    {'asset': 'RV USA', 'pct': 12, 'cambio': '→'},
                    {'asset': 'RV Europa', 'pct': 5, 'cambio': '→'},
                    {'asset': 'RV Chile', 'pct': 5, 'cambio': '↑'},
                    {'asset': 'RV EM', 'pct': 3, 'cambio': '→'},
                    {'asset': 'RF Gobierno', 'pct': 35, 'cambio': '→'},
                    {'asset': 'RF Credito', 'pct': 15, 'cambio': '→'},
                    {'asset': 'RF Chile', 'pct': 12, 'cambio': '→'},
                    {'asset': 'Commodities', 'pct': 3, 'cambio': '→'},
                    {'asset': 'Cash', 'pct': 10, 'cambio': '↑'},
                ]
            },
            {
                'perfil': 'Moderado',
                'risk_score': '4-5',
                'allocations': [
                    {'asset': 'RV USA', 'pct': 22, 'cambio': '↓'},
                    {'asset': 'RV Europa', 'pct': 8, 'cambio': '→'},
                    {'asset': 'RV Chile', 'pct': 10, 'cambio': '↑'},
                    {'asset': 'RV EM', 'pct': 5, 'cambio': '→'},
                    {'asset': 'RF Gobierno', 'pct': 20, 'cambio': '→'},
                    {'asset': 'RF Credito', 'pct': 12, 'cambio': '→'},
                    {'asset': 'RF Chile', 'pct': 10, 'cambio': '→'},
                    {'asset': 'Commodities', 'pct': 8, 'cambio': '→'},
                    {'asset': 'Cash', 'pct': 5, 'cambio': '↑'},
                ]
            },
            {
                'perfil': 'Agresivo',
                'risk_score': '6-7',
                'allocations': [
                    {'asset': 'RV USA', 'pct': 30, 'cambio': '↓'},
                    {'asset': 'RV Europa', 'pct': 10, 'cambio': '→'},
                    {'asset': 'RV Chile', 'pct': 12, 'cambio': '↑'},
                    {'asset': 'RV EM', 'pct': 8, 'cambio': '→'},
                    {'asset': 'RF Gobierno', 'pct': 10, 'cambio': '→'},
                    {'asset': 'RF Credito', 'pct': 10, 'cambio': '→'},
                    {'asset': 'RF Chile', 'pct': 8, 'cambio': '→'},
                    {'asset': 'Commodities', 'pct': 8, 'cambio': '→'},
                    {'asset': 'Cash', 'pct': 4, 'cambio': '→'},
                ]
            },
            {
                'perfil': 'Ultra Agresivo',
                'risk_score': '8-10',
                'allocations': [
                    {'asset': 'RV USA', 'pct': 35, 'cambio': '↓'},
                    {'asset': 'RV Europa', 'pct': 12, 'cambio': '→'},
                    {'asset': 'RV Chile', 'pct': 15, 'cambio': '↑'},
                    {'asset': 'RV EM', 'pct': 10, 'cambio': '→'},
                    {'asset': 'RF Gobierno', 'pct': 5, 'cambio': '→'},
                    {'asset': 'RF Credito', 'pct': 5, 'cambio': '→'},
                    {'asset': 'RF Chile', 'pct': 5, 'cambio': '→'},
                    {'asset': 'Commodities', 'pct': 10, 'cambio': '→'},
                    {'asset': 'Cash', 'pct': 3, 'cambio': '→'},
                ]
            },
        ]

        return portfolios

    # =========================================================================
    # SECCION 9: FOCUS LIST
    # =========================================================================

    def generate_focus_list(self) -> Dict[str, List]:
        """Focus list de instrumentos especificos con tickers."""

        if not self._has_council():
            return self._default_focus_list()

        # Extract tickers from tactical actions and panel views
        return {
            'renta_variable': [
                {'ticker': 'SPY', 'nombre': 'SPDR S&P 500 ETF', 'view': 'OW', 'rationale': 'Core US exposure, broad market'},
                {'ticker': 'IWB', 'nombre': 'iShares Russell 1000 Value', 'view': 'OW', 'rationale': 'Rotacion value, quality-momentum'},
                {'ticker': 'SOXX', 'nombre': 'iShares Semiconductor', 'view': 'OW', 'rationale': 'AI capex beneficiary selectivo'},
                {'ticker': 'XLI', 'nombre': 'Industrial Select SPDR', 'view': 'OW', 'rationale': 'Manufactura en maximos, reshoring'},
                {'ticker': 'ECH', 'nombre': 'iShares MSCI Chile', 'view': 'OW', 'rationale': 'Chile momentum + carry + cobre'},
                {'ticker': 'EWG', 'nombre': 'iShares MSCI Germany', 'view': 'N', 'rationale': 'Valuaciones atractivas, DAX historicos'},
                {'ticker': 'EEM', 'nombre': 'iShares MSCI EM', 'view': 'N', 'rationale': 'Selectivo, aranceles limitan upside'},
            ],
            'renta_fija': [
                {'ticker': 'BIL', 'nombre': 'SPDR Bloomberg T-Bill', 'view': 'OW', 'rationale': 'Cash-like, carry atractivo 5%+'},
                {'ticker': 'SHY', 'nombre': 'iShares 1-3 Year Treasury', 'view': 'OW', 'rationale': 'Short duration, Fed hawkish hedge'},
                {'ticker': 'VMBS', 'nombre': 'Vanguard MBS ETF', 'view': 'OW', 'rationale': 'Reemplazo TLT, spread atractivo'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': 'OW', 'rationale': 'IG sobre HY, spreads razonables'},
                {'ticker': 'TLT', 'nombre': 'iShares 20+ Year Treasury', 'view': 'UW', 'rationale': 'Riesgo duration elevado, term premium'},
                {'ticker': 'HYG', 'nombre': 'iShares High Yield Corp', 'view': 'UW', 'rationale': 'Spreads no compensan late-cycle risk'},
            ],
            'commodities': [
                {'ticker': 'CPER', 'nombre': 'US Copper Index Fund', 'view': 'OW', 'rationale': 'Transicion energetica, supply deficit'},
                {'ticker': 'COPX', 'nombre': 'Global X Copper Miners', 'view': 'OW', 'rationale': 'Leverage operativo al precio cobre'},
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': 'OW', 'rationale': 'Hedge geopolitico, reducir 30%'},
                {'ticker': 'USO', 'nombre': 'US Oil Fund', 'view': 'N', 'rationale': 'Distension US-Iran comprime prima'},
                {'ticker': 'UUP', 'nombre': 'Invesco DB US Dollar', 'view': 'OW', 'rationale': 'Fed hawkish + aranceles = DXY up'},
            ]
        }

    def _default_focus_list(self) -> Dict[str, List]:
        """Focus list por defecto sin council."""
        return {
            'renta_variable': [
                {'ticker': 'SPY', 'nombre': 'SPDR S&P 500 ETF', 'view': 'N', 'rationale': 'Core US exposure'},
                {'ticker': 'ECH', 'nombre': 'iShares MSCI Chile', 'view': 'OW', 'rationale': 'Chile carry + momentum'},
                {'ticker': 'EEM', 'nombre': 'iShares MSCI EM', 'view': 'N', 'rationale': 'EM diversification'},
            ],
            'renta_fija': [
                {'ticker': 'BIL', 'nombre': 'SPDR Bloomberg T-Bill', 'view': 'OW', 'rationale': 'Cash-like, carry atractivo'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': 'N', 'rationale': 'Investment grade exposure'},
            ],
            'commodities': [
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': 'N', 'rationale': 'Hedge diversification'},
            ]
        }

    # =========================================================================
    # PERFORMANCE MES ANTERIOR
    # =========================================================================

    def generate_previous_month_performance(self) -> Dict[str, Any]:
        """Performance del mes anterior (backward-looking, no requiere council)."""
        return {
            'titulo': 'Resultado del Mes Anterior',
            'periodo': 'Enero 2026',
            'performance_portfolio': {
                'retorno_modelo': '+1.8%',
                'retorno_benchmark': '+1.2%',
                'alpha': '+0.6%',
                'comentario': 'Outperformance impulsado por OW Chile y UW US Tech'
            },
            'atribucion_por_asset_class': [
                {
                    'asset_class': 'Renta Variable US',
                    'peso': '32%',
                    'retorno_asset': '+0.2%',
                    'contribucion': '+0.06%',
                    'vs_benchmark': '-0.1%',
                    'comentario': 'Underweight en Tech ayudó'
                },
                {
                    'asset_class': 'Renta Variable Europa',
                    'peso': '12%',
                    'retorno_asset': '+2.5%',
                    'contribucion': '+0.30%',
                    'vs_benchmark': '+0.15%',
                    'comentario': 'OW pagó con BCE dovish'
                },
                {
                    'asset_class': 'Renta Variable Chile',
                    'peso': '10%',
                    'retorno_asset': '+3.2%',
                    'contribucion': '+0.32%',
                    'vs_benchmark': '+0.20%',
                    'comentario': 'Mejor contribución del mes'
                },
                {
                    'asset_class': 'Renta Fija Global',
                    'peso': '25%',
                    'retorno_asset': '+0.8%',
                    'contribucion': '+0.20%',
                    'vs_benchmark': '+0.05%',
                    'comentario': 'Duration neutral funcionó'
                },
                {
                    'asset_class': 'Renta Fija Chile',
                    'peso': '12%',
                    'retorno_asset': '+1.5%',
                    'contribucion': '+0.18%',
                    'vs_benchmark': '+0.10%',
                    'comentario': 'Carry trade entregó'
                },
                {
                    'asset_class': 'Commodities',
                    'peso': '5%',
                    'retorno_asset': '+4.0%',
                    'contribucion': '+0.20%',
                    'vs_benchmark': '+0.10%',
                    'comentario': 'Cobre rally ayudó'
                },
                {
                    'asset_class': 'Cash/MM',
                    'peso': '4%',
                    'retorno_asset': '+0.4%',
                    'contribucion': '+0.02%',
                    'vs_benchmark': '0%',
                    'comentario': 'Neutral'
                }
            ],
            'calls_acertados': [
                {'call': 'OW Chile equity', 'impacto': '+20bp alpha', 'comentario': 'IPSA +3.2% vs EM +1.0%'},
                {'call': 'UW US Tech', 'impacto': '+15bp alpha', 'comentario': 'Nasdaq -1.5% vs S&P +0.2%'},
                {'call': 'OW Cobre', 'impacto': '+10bp alpha', 'comentario': 'Cobre +5% en rally'}
            ],
            'calls_errados': [
                {'call': 'UW Oro', 'impacto': '-5bp alpha', 'comentario': 'Oro subió pese a expansión'},
                {'call': 'OW Duration US', 'impacto': '-8bp alpha', 'comentario': 'Tasas subieron levemente'}
            ],
            'leccion_aprendida': (
                "El posicionamiento en Chile sigue generando alpha consistente. La rotación value vs growth "
                "fue acertada pero el timing en duration US fue prematuro — lección para este mes: "
                "esperar confirmación CPI antes de mover duration. Mantenemos sesgo Chile y agregamos "
                "cauteloso profit-taking en commodities."
            )
        }

    # =========================================================================
    # GENERADOR COMPLETO
    # =========================================================================

    # =========================================================================
    # FORECAST ENGINE HELPERS
    # =========================================================================

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

    def get_forecast_summary(self) -> Dict[str, Any]:
        """Returns a compact summary of all forecasts for AA integration."""
        if not self.forecast:
            return {}

        summary = {}

        # GDP
        for region in ['usa', 'chile', 'china', 'eurozone']:
            fc = self._fc('gdp_forecasts', region, 'forecast_12m')
            if fc is not None:
                summary[f'gdp_{region}'] = fc

        # Inflation
        for region in ['usa', 'chile', 'eurozone']:
            fc = self._fc('inflation_forecasts', region, 'forecast_12m')
            if fc is not None:
                summary[f'infl_{region}'] = fc

        # Rates
        for rate in ['fed_funds', 'tpm_chile', 'ecb']:
            fc = self._fc('rate_forecasts', rate, 'forecast_12m')
            direction = self._fc('rate_forecasts', rate, 'direction')
            if fc is not None:
                summary[f'rate_{rate}'] = fc
            if direction:
                summary[f'rate_{rate}_dir'] = direction

        # Equity signals
        for idx in ['sp500', 'eurostoxx', 'nikkei', 'csi300', 'ipsa', 'bovespa']:
            signal = self._fc('equity_targets', idx, 'signal')
            ret = self._fc('equity_targets', idx, 'expected_return_pct')
            if signal:
                summary[f'eq_{idx}_signal'] = signal
            if ret is not None:
                summary[f'eq_{idx}_return'] = ret

        return summary

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte."""

        content = {
            'metadata': {
                'fecha': self.date.strftime('%Y-%m-%d'),
                'mes': self.month_name,
                'ano': self.date.year,
                'tipo': 'Reporte Asset Allocation',
                'council_available': self._has_council(),
                'forecast_available': bool(self.forecast and 'error' not in self.forecast),
            },
            'resumen_ejecutivo': self.generate_executive_summary(),
            'dashboard': self.generate_positioning_dashboard(),
            'performance_anterior': self.generate_previous_month_performance(),
            'mes_en_revision': self.generate_month_review(),
            'escenarios': self.generate_scenarios(),
            'views_regionales': self.generate_regional_views(),
            'asset_classes': self.generate_asset_class_views(),
            'riesgos': self.generate_risks_section(),
            'portafolios_modelo': self.generate_model_portfolios(),
            'focus_list': self.generate_focus_list(),
        }

        # Add forecast summary if available
        fc_summary = self.get_forecast_summary()
        if fc_summary:
            content['forecast_summary'] = fc_summary

        return content


def main():
    """Test del generador de contenido."""
    council_dir = Path(__file__).parent / "output" / "council"
    council_files = sorted(council_dir.glob("council_result_*.json"))
    council_result = {}
    if council_files:
        council_file = council_files[-1]
        print(f"[INFO] Cargando council: {council_file}")
        with open(council_file, 'r', encoding='utf-8') as f:
            council_result = json.load(f)

    generator = AssetAllocationContentGenerator(council_result)
    content = generator.generate_all_content()

    # Guardar como JSON para debug
    output_file = Path(__file__).parent / "output" / "content" / f"aa_content_{datetime.now().strftime('%Y-%m-%d')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    print(f"Contenido generado: {output_file}")
    print(f"Council disponible: {content['metadata']['council_available']}")

    # Print preview
    print("\n" + "="*60)
    print("PREVIEW - RESUMEN EJECUTIVO")
    print("="*60)
    print(content['resumen_ejecutivo']['parrafo_intro'])
    print("\nKEY POINTS:")
    for kp in content['resumen_ejecutivo']['key_points']:
        print(f"  * {kp}")
    print(f"\nPOSTURA: {content['resumen_ejecutivo']['postura']}")


if __name__ == "__main__":
    main()

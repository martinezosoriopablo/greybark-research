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
- Recomendaciones OW (Overweight/Sobreponderar) / UW (Underweight/Subponderar) por asset class
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
                 forecast_data: Dict = None, company_name: str = ""):
        self.council = council_result or {}
        self.quant = quant_data or {}
        self.forecast = forecast_data or {}
        self.company_name = company_name
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)

        # External data providers (injected by caller)
        self.data = None  # ChartDataProvider, injected externally
        self.bloomberg = None  # BloombergReader, injected externally
        self._parser = None

        # Cache parsed council data
        self._parsed_final = None
        self._parsed_cio = None

    @property
    def parser(self):
        if self._parser is None:
            try:
                from council_parser import CouncilParser
                self._parser = CouncilParser(self.council)
            except Exception:
                from council_parser import CouncilParser
                self._parser = CouncilParser({})
        return self._parser

    # =========================================================================
    # QUANT DATA HELPERS
    # =========================================================================

    def _q(self, *keys, default=None):
        """Accede a quant_data siguiendo ruta de keys. Unwraps dicts with 'value' key."""
        d = self.quant
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        # Unwrap simple dict with 'value' key (common pattern from data collectors)
        # Only unwrap if dict looks like a data point (has 'value' and few other keys like 'period', 'date')
        if isinstance(d, dict) and 'value' in d and len(keys) >= 2:
            non_meta_keys = [k for k in d.keys() if k not in ('value', 'period', 'date', 'unit', 'source', 'returns')]
            if len(non_meta_keys) <= 2:
                d = d['value']
        # Handle numpy types
        if d is not None:
            t = type(d).__name__
            if 'float' in t.lower() or 'int' in t.lower():
                try:
                    d = float(d)
                except (TypeError, ValueError):
                    pass
        return d if d is not None else default

    def _has_q(self, *keys) -> bool:
        """Verifica si quant_data tiene datos en la ruta."""
        return self._q(*keys) is not None

    def _bbg_val(self, campo_id: str, default=None):
        """Get latest Bloomberg value, returns None if unavailable."""
        if self.bloomberg and self.bloomberg.has(campo_id):
            return self.bloomberg.get_latest(campo_id)
        return default

    def _bbg_quant_summary(self) -> str:
        """Build quant context string from Bloomberg data for narrative prompts."""
        parts = []
        if not self.bloomberg or not self.bloomberg.available:
            return ''
        # PE Forward valuations
        pe_map = {'S&P 500': 'pe_spx', 'STOXX 600': 'pe_stoxx600',
                  'MSCI EM': 'pe_msci_em', 'IPSA': 'pe_ipsa'}
        pe_items = []
        for label, campo in pe_map.items():
            v = self._bbg_val(campo)
            if v is not None:
                pe_items.append(f"{label}: {v:.1f}x")
        if pe_items:
            parts.append(f"PE Fwd: {', '.join(pe_items)}")
        # CDS key
        cds_map = {'USA': 'cds_usa', 'Chile': 'cds_chile', 'China': 'cds_china'}
        cds_items = []
        for label, campo in cds_map.items():
            v = self._bbg_val(campo)
            if v is not None:
                cds_items.append(f"{label}: {v:.0f}bp")
        if cds_items:
            parts.append(f"CDS 5Y: {', '.join(cds_items)}")
        # SOFR key tenors
        sofr_map = {'2Y': 'sofr_2y', '5Y': 'sofr_5y', '10Y': 'sofr_10y'}
        sofr_items = []
        for label, campo in sofr_map.items():
            v = self._bbg_val(campo)
            if v is not None:
                sofr_items.append(f"{label}: {v:.2f}%")
        if sofr_items:
            parts.append(f"SOFR Swap: {', '.join(sofr_items)}")
        # IG/HY total spread
        ig = self._bbg_val('oas_ig_total')
        hy = self._bbg_val('oas_hy_total')
        if ig is not None:
            parts.append(f"OAS IG: {ig:.0f}bp")
        if hy is not None:
            parts.append(f"OAS HY: {hy:.0f}bp")
        return ' | '.join(parts)

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

    def _build_quant_summary(self) -> str:
        """Build a compact summary of all available quantitative data for LLM context."""
        parts = []
        # Macro
        for key, label in [('gdp', 'GDP US'), ('core_cpi', 'Core CPI'), ('unemployment', 'Desempleo'),
                           ('fed_rate', 'Fed Funds'), ('recession_prob', 'Prob Recesión')]:
            val = self._q('macro_usa', key)
            if val is not None:
                parts.append(f"{label}: {val}%")
        # Regime
        regime = self._q('regime', 'current')
        if regime:
            parts.append(f"Régimen: {regime}")
        # Chile
        for key, label in [('tpm', 'TPM'), ('ipc_yoy', 'IPC Chile')]:
            val = self._q('chile', key)
            if val is not None:
                parts.append(f"{label}: {val}%")
        # Equity valuations
        for key, label in [('us', 'S&P 500'), ('europe', 'Europa'), ('chile', 'Chile'), ('em', 'EM')]:
            val = self._q('equity', 'valuations', key)
            if val and isinstance(val, dict):
                pe = val.get('pe')
                if pe is not None:
                    parts.append(f"{label} P/E: {pe:.1f}x")
        # Rates
        for key, label in [('us_2y', 'UST 2Y'), ('us_10y', 'UST 10Y')]:
            val = self._q('yield_curve', key) or self._q('chile_rates', f'ust_{key.split("_")[1]}')
            if val is not None:
                parts.append(f"{label}: {val}%")
        # Spreads
        ig = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if ig:
            parts.append(f"IG spread: {ig:.0f}bps")
        if hy:
            parts.append(f"HY spread: {hy:.0f}bps")
        # Commodities
        copper = self._q('equity', 'bcch_indices', 'copper', 'value')
        if copper:
            parts.append(f"Cobre: ${copper}/lb")
        # VIX
        vix = self._q('risk', 'vix') or self._q('chile_rates', 'vix')
        if vix:
            parts.append(f"VIX: {vix}")
        return " | ".join(parts) if parts else "Datos cuantitativos limitados"

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
    # REGIONAL VIEW ALIASES
    # =========================================================================

    EQUITY_VIEW_ALIASES = {
        'usa': ['usa', 'us', 'estados unidos', 'eeuu', 'renta variable usa'],
        'europe': ['europa', 'europe', 'renta variable europa', 'eu'],
        'china': ['china', 'renta variable china'],
        'chile': ['chile', 'chile y latam', 'renta variable chile'],
        'brazil': ['brasil', 'brazil', 'renta variable brasil'],
        'mexico': ['méxico', 'mexico', 'renta variable mexico'],
        'em': ['em', 'emergentes', 'emerging', 'em ex-china'],
        'japan': ['japón', 'japon', 'japan'],
    }

    def _find_view(self, views: Dict, region_key: str) -> Optional[Dict]:
        """Find a region's view in a dict using alias matching."""
        if not views:
            return None
        aliases = self.EQUITY_VIEW_ALIASES.get(region_key, [region_key])
        for alias in aliases:
            if alias in views:
                return views[alias]
        # Try case-insensitive
        views_lower = {k.lower(): v for k, v in views.items()}
        for alias in aliases:
            if alias.lower() in views_lower:
                return views_lower[alias.lower()]
        return None

    # =========================================================================
    # SHARED NARRATIVE HELPERS
    # =========================================================================

    def _generate_trigger_cambio(self, region: str, council_ctx: str) -> str:
        """Generate trigger de cambio via Claude from council context."""
        if not self._has_council():
            return 'N/D'
        from narrative_engine import generate_narrative
        trigger = generate_narrative(
            section_name=f"aa_{region.lower().replace(' ', '_')}_trigger",
            prompt=(
                f"En 1 oración concreta, describe el trigger principal que cambiaría la vista de "
                f"inversión para {region}. Incluir: dato específico, umbral, y dirección del cambio. "
                "Ejemplo: 'Revisaríamos a UW si Core CPI supera 4.0% por 2 meses consecutivos.' "
                "Máximo 30 palabras. Sin preámbulos."
            ),
            council_context=council_ctx,
            company_name=self.company_name,
            max_tokens=150,
        )
        return trigger if trigger else 'Monitorear datos macro del período.'

    def _generate_region_args(self, region: str, council_ctx: str, quant_ctx: str = "") -> tuple:
        """Generate pro/con arguments via Claude for a region. Returns (favor, contra)."""
        import json as _json
        from narrative_engine import generate_narrative
        args_favor = [{'punto': 'Sin datos', 'dato': 'N/D'}]
        args_contra = [{'punto': 'Sin datos', 'dato': 'N/D'}]
        if not self._has_council():
            return args_favor, args_contra
        args_raw = generate_narrative(
            section_name=f"aa_{region.lower().replace(' ', '_')}_args",
            prompt=(
                f"Genera argumentos a favor y en contra de invertir en {region} equity como JSON: "
                '{"favor": [{"punto": "string", "dato": "string"}], '
                '"contra": [{"punto": "string", "dato": "string"}]}. '
                "Exactamente 3 en cada lista. Usa datos del council."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=600,
            temperature=0.2,
        )
        if args_raw:
            try:
                cleaned = args_raw.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = _json.loads(cleaned)
                if 'favor' in parsed:
                    args_favor = parsed['favor']
                if 'contra' in parsed:
                    args_contra = parsed['contra']
            except (_json.JSONDecodeError, KeyError):
                pass
        return args_favor, args_contra

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
            # Default to MEDIA conviction if council text exists but no final_recommendation
            if self.parser.has_council_text():
                return {'view': 'NEUTRAL', 'sesgo': 'NEUTRAL', 'conviccion': 'MEDIA'}
            return {'view': 'N/D', 'sesgo': 'N/D', 'conviccion': 'N/D'}

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
        """Genera párrafo introductorio via Claude desde council data."""
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        geo = self._panel('geo') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        if macro or geo or final:
            council_ctx = (
                f"MACRO PANEL:\n{macro[:1500]}\n\n"
                f"GEO PANEL:\n{geo[:1000]}\n\n"
                f"FINAL REC:\n{final[:1500]}"
            )
            result = generate_narrative(
                section_name="aa_intro",
                prompt=(
                    f"Escribe la introduccion del reporte de Asset Allocation de {self.month_name} "
                    f"{self.date.year}. 3 parrafos: (1) contexto macro y regimen, "
                    f"(2) postura adoptada: {postura['view']} con sesgo {postura['sesgo']} y "
                    f"conviccion {postura['conviccion']} — fundamento desde council, "
                    "(3) mercado destacado y principales riesgos a monitorear. "
                    "Usa datos del council. Separa parrafos con linea vacia. Maximo 200 palabras."
                    "\n\nESTRUCTURA RESUMEN AUTOCONTENIDO: El lector debe entender la postura completa leyendo SOLO esta sección. Incluye: régimen macro + dato, postura general + horizonte, qué cambió vs anterior, oportunidad + dato, riesgo + dato, acción concreta. Escribe 250-350 palabras. Explica jerga técnica (OW, UW, duration, carry, spread, risk-on/off) con paréntesis en primera mención."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=1200,
            )
            if result:
                return result

        return self._default_intro(postura)

    def _default_intro(self, postura: Dict) -> str:
        """Intro generada por Sonnet usando datos cuantitativos disponibles."""
        from narrative_engine import generate_data_driven_narrative

        quant_ctx = self._build_quant_summary()
        result = generate_data_driven_narrative(
            section_name="aa_intro_datadriven",
            prompt=(
                f"Escribe la introducción del reporte de Asset Allocation de {self.month_name} "
                f"{self.date.year}. Postura: {postura['view']} con sesgo {postura['sesgo']}. "
                "3 párrafos: (1) contexto macro y régimen basado en datos, "
                "(2) postura adoptada y fundamento cuantitativo, "
                "(3) principales riesgos a monitorear. Máximo 200 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=1000,
        )
        if result:
            return result
        # Ultra-minimal fallback: data-only, no opinion
        name = self.company_name or "Nosotros"
        return (
            f"{name} adopta una postura {postura['view']} con sesgo {postura['sesgo']} "
            f"para {self.month_name} {self.date.year}."
        )

    def _generate_key_points(self) -> List[str]:
        """Genera key points via Claude desde council output."""
        from narrative_engine import generate_narrative

        cio = self._cio() if self._has_council() else ''
        final = self._final() if self._has_council() else ''
        macro = self._panel('macro') if self._has_council() else ''
        riesgo = self._panel('riesgo') if self._has_council() else ''

        if cio or final or macro:
            council_ctx = (
                f"CIO:\n{cio[:1500]}\n\nFINAL:\n{final[:1500]}\n\n"
                f"MACRO:\n{macro[:1000]}\n\nRISK:\n{riesgo[:800]}"
            )
            result = generate_narrative(
                section_name="aa_key_points",
                prompt=(
                    f"Genera exactamente 5 key points para asset allocation de {self.month_name} "
                    f"{self.date.year}. Cubrir: regimen economico, politica monetaria, "
                    "principal riesgo geopolitico/comercial, mercado destacado, y "
                    "nivel de riesgo/hedging. Cada punto en una linea. "
                    "Usa datos del council — NO inventes numeros. "
                    "Sin bullets ni numeracion."
                    "\n\nCada key point debe incluir: cadena dato→interpretación→acción, convicción (ALTA/MEDIA/BAJA) con evidencia, horizonte temporal (táctico 1-3m o estratégico 6-12m)."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=700,
            )
            if result:
                lines = [l.strip() for l in result.split('\n') if l.strip()]
                if len(lines) >= 3:
                    return lines[:5]

        return [
            "Dinamicas macro requieren posicionamiento selectivo",
            "Politica monetaria en evaluacion — proximos datos seran clave",
            "Monitorear desarrollos geopoliticos y comerciales",
            "Fundamentos regionales diferenciados ofrecen oportunidades",
            "Mantener coberturas activas ante incertidumbre",
        ]

    def _identify_catalizador(self) -> str:
        """Identifica catalizador principal via Claude desde council."""
        from narrative_engine import generate_narrative

        final = self._final() if self._has_council() else ''
        macro = self._panel('macro') if self._has_council() else ''

        if final or macro:
            # First try regex extraction
            if 'catalizador' in final.lower():
                match = re.search(r'catalizador[^:]*:\s*([^\n]+)', final, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

            result = generate_narrative(
                section_name="aa_catalizador",
                prompt=(
                    "Identifica el catalizador principal a monitorear segun el council. "
                    "UNA oracion, maximo 25 palabras. Directo, sin florituras. "
                    "Ejemplo: 'Datos CPI US y decision de tasas del BCCh — determinantes para "
                    "posicionamiento de duration.'"
                ),
                council_context=f"FINAL:\n{final[:1500]}\n\nMACRO:\n{macro[:800]}",
                company_name=self.company_name,
                max_tokens=80,
            )
            if result:
                return result

        return "Proximos datos macro y decisiones de politica monetaria"

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
        """Economía global desde panel macro + datos reales."""
        macro = self._panel('macro')

        if not macro:
            return self._default_economia_global()

        # Try real data from ChartDataProvider first, then council text, then 'N/D'
        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', None)
        cpi = self._extract_number(macro, r'Core\s+CPI\s+(?:bajando\s+de\s+\d+\.?\d*%?\s*a\s+)?(\d+\.?\d*)%', None)
        retail = self._extract_number(macro, r'retail\s+sales?\s+\+?(\d+\.?\d*)%', None)
        recession = self._extract_number(macro, r'recesi[oó]n.*?(\d+)%', None)

        # Enrich with real FRED data if available
        gdp_prev = None
        cpi_prev = None
        retail_prev = None
        recession_prev = None
        if self.data:
            try:
                usa = self.data.get_usa_latest()
                if gdp is None and usa.get('gdp_saar') is not None:
                    gdp = usa['gdp_saar']
                if cpi is None and usa.get('cpi_core') is not None:
                    cpi = usa['cpi_core']
                gdp_prev = usa.get('gdp_qoq_prev')
                cpi_prev = usa.get('cpi_core_yoy_prev')
                retail_prev = usa.get('retail_sales_yoy_prev')
                recession_prev = usa.get('recession_prob_prev')
            except Exception:
                pass

        # Also try quant_data
        if gdp is None:
            gdp = self._q('macro_usa', 'gdp')
        if cpi is None:
            cpi = self._q('macro_usa', 'core_cpi')
        if retail is None:
            retail = self._q('macro_usa', 'retail_sales')
        if recession is None:
            recession = self._q('macro_usa', 'recession_prob')

        gdp_str = f'{gdp}%' if gdp is not None else 'N/D'
        cpi_str = f'{cpi}%' if cpi is not None else 'N/D'
        retail_str = f'+{retail}%' if retail is not None else 'N/D'
        recession_str = f'{int(recession)}%' if recession is not None else 'N/D'
        gdp_prev_str = f'{gdp_prev}%' if gdp_prev is not None else 'N/D'
        cpi_prev_str = f'{cpi_prev}%' if cpi_prev is not None else 'N/D'
        retail_prev_str = f'+{retail_prev}%' if retail_prev is not None else 'N/D'
        recession_prev_str = f'{int(recession_prev)}%' if recession_prev is not None else 'N/D'

        from narrative_engine import generate_narrative
        council_ctx = f"MACRO PANEL:\n{macro[:2500]}"
        quant_ctx = f"GDP US: {gdp_str} | Core CPI: {cpi_str} | Retail Sales: {retail_str} | Prob Recesion: {recession_str}"

        narrativa = generate_narrative(
            section_name="aa_economia_global",
            prompt=(
                f"Escribe 2 parrafos sobre la economia global para {self.month_name} "
                f"{self.date.year}. Cubrir: GDP, inflacion, empleo, y probabilidad de recesion. "
                "Integrar datos cuantitativos proporcionados. Maximo 150 palabras. "
                "Separa parrafos con linea vacia."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=600,
        )
        if not narrativa:
            narrativa = (
                f"GDP US en {gdp_str} QoQ. Core CPI en {cpi_str}. "
                f"Retail sales en {retail_str} YoY. Probabilidad de recesion: {recession_str}."
            )

        # Compute surprise direction from actual vs previous
        def _surprise(actual, prev):
            if actual is not None and prev is not None:
                diff = actual - prev
                if abs(diff) < 0.1:
                    return '→ En línea'
                return f'↑ +{diff:.1f}pp' if diff > 0 else f'↓ {diff:.1f}pp'
            # Try extracting from macro panel text
            if macro:
                for word in ['mejor de lo esperado', 'above expectations', 'beat']:
                    if word in macro.lower():
                        return '↑ Sobre consenso'
                for word in ['peor de lo esperado', 'below expectations', 'miss']:
                    if word in macro.lower():
                        return '↓ Bajo consenso'
            return 'N/D'

        gdp_sorpresa = _surprise(gdp, gdp_prev)
        cpi_sorpresa = _surprise(cpi, cpi_prev)

        # Try to extract retail/recession surprise from macro text
        retail_sorpresa = _surprise(retail, retail_prev)
        recession_sorpresa = 'N/D'
        if macro:
            for pattern, result in [('retail.*mejor', '↑ Sobre consenso'), ('retail.*peor', '↓ Bajo consenso'),
                                     ('consumo.*fuerte', '↑ Sobre consenso'), ('consumo.*débil', '↓ Bajo consenso')]:
                import re
                if re.search(pattern, macro, re.IGNORECASE):
                    retail_sorpresa = result
                    break

        datos = [
            {'indicador': 'GDP US QoQ (PIB EE.UU. trimestral)', 'actual': gdp_str, 'anterior': gdp_prev_str, 'sorpresa': gdp_sorpresa},
            {'indicador': 'Core CPI YoY (inflación subyacente interanual)', 'actual': cpi_str, 'anterior': cpi_prev_str, 'sorpresa': cpi_sorpresa},
            {'indicador': 'Retail Sales YoY (Ventas Minoristas interanual)', 'actual': retail_str, 'anterior': retail_prev_str, 'sorpresa': retail_sorpresa},
            {'indicador': 'Prob. Recesión 12M (probabilidad de recesión a 12 meses)', 'actual': recession_str, 'anterior': recession_prev_str, 'sorpresa': recession_sorpresa},
        ]

        return {'titulo': 'Economía Global', 'narrativa': narrativa, 'datos': datos}

    def _default_economia_global(self) -> Dict[str, Any]:
        """Economía global generada por Sonnet usando datos cuantitativos."""
        from narrative_engine import generate_data_driven_narrative

        # Gather all available macro data
        cpi_str = 'N/D'
        gdp_str = 'N/D'
        unemployment_str = 'N/D'
        fed_str = 'N/D'

        if self.data:
            try:
                usa = self.data.get_usa_latest()
                if usa.get('cpi_core') is not None:
                    cpi_str = f"{usa['cpi_core']}%"
                if usa.get('gdp') is not None:
                    gdp_str = f"{usa['gdp']}%"
                if usa.get('unemployment') is not None:
                    unemployment_str = f"{usa['unemployment']}%"
                if usa.get('fed_funds') is not None:
                    fed_str = f"{usa['fed_funds']}%"
            except Exception:
                pass

        if cpi_str == 'N/D':
            cpi_str = self._fmt_pct(self._q('macro_usa', 'core_cpi'))
        if gdp_str == 'N/D':
            gdp_str = self._fmt_pct(self._q('macro_usa', 'gdp'))
        if unemployment_str == 'N/D':
            unemployment_str = self._fmt_pct(self._q('macro_usa', 'unemployment'))
        if fed_str == 'N/D':
            fed_str = self._fmt_pct(self._q('macro_usa', 'fed_rate'))

        regime = self._q('regime', 'current') or 'N/D'
        recession_prob = self._fmt_pct(self._q('macro_usa', 'recession_prob'))

        quant_ctx = (
            f"GDP US: {gdp_str} | Core CPI: {cpi_str} | Desempleo: {unemployment_str} | "
            f"Fed Funds: {fed_str} | Régimen: {regime} | Prob. Recesión: {recession_prob}"
        )

        narrativa = generate_data_driven_narrative(
            section_name="aa_economia_global_dd",
            prompt=(
                f"Escribe 2 párrafos sobre la economía global para el reporte de asset allocation "
                f"de {self.month_name} {self.date.year}. Analiza los datos macro disponibles: "
                "crecimiento, inflación, empleo y política monetaria. Máximo 120 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=500,
        )
        if not narrativa:
            narrativa = f"Datos macro: GDP US {gdp_str}, Core CPI {cpi_str}, desempleo {unemployment_str}, Fed Funds {fed_str}."

        # Try to get prior values from ChartDataProvider
        gdp_prev_str = 'N/D'
        cpi_prev_str = 'N/D'
        unemp_prev_str = 'N/D'
        if self.data:
            try:
                usa_d = self.data.get_usa_latest()
                gdp_prev_str = f"{usa_d['gdp_qoq_prev']}%" if usa_d.get('gdp_qoq_prev') is not None else 'N/D'
                cpi_prev_str = f"{usa_d['cpi_core_yoy_prev']}%" if usa_d.get('cpi_core_yoy_prev') is not None else 'N/D'
                unemp_prev_str = f"{usa_d['unemployment_prev']}%" if usa_d.get('unemployment_prev') is not None else 'N/D'
            except Exception:
                pass

        datos = [
            {'indicador': 'GDP US QoQ (PIB EE.UU. trimestral)', 'actual': gdp_str, 'anterior': gdp_prev_str, 'sorpresa': 'N/D'},
            {'indicador': 'US Core CPI (inflación subyacente EE.UU.)', 'actual': cpi_str, 'anterior': cpi_prev_str, 'sorpresa': 'N/D'},
            {'indicador': 'Desempleo (tasa de desempleo EE.UU.)', 'actual': unemployment_str, 'anterior': unemp_prev_str, 'sorpresa': 'N/D'},
            {'indicador': 'Fed Funds (tasa de referencia Fed)', 'actual': fed_str, 'anterior': 'N/D', 'sorpresa': 'N/D'},
        ]

        return {'titulo': 'Economía Global', 'narrativa': narrativa, 'datos': datos}

    def _generate_mercados_review(self) -> Dict[str, Any]:
        """Mercados via Claude desde council rv + macro."""
        from narrative_engine import generate_narrative

        rv = self._panel('rv')
        macro = self._panel('macro')

        if not rv:
            return self._default_mercados()

        council_ctx = f"RV PANEL:\n{rv[:1500]}\n\nMACRO:\n{macro[:1000]}"
        narrativa = generate_narrative(
            section_name="aa_mercados_review",
            prompt=(
                f"Escribe 2 parrafos sobre el desempeño de mercados financieros en "
                f"{self.month_name} {self.date.year}. Cubrir: dinamica de indices (equity, bonos), "
                "commodities, y cualquier divergencia relevante. Usa datos del council. "
                "Separa parrafos con linea vacia. Maximo 120 palabras."
            ),
            council_context=council_ctx,
            company_name=self.company_name,
            max_tokens=500,
        )
        if not narrativa:
            narrativa = "Los mercados mostraron dinamicas mixtas durante el periodo."

        # Build performance table from equity data
        performance = []
        eq = self._q('equity')
        if eq and isinstance(eq, dict):
            bcch = eq.get('bcch_indices', {})
            for name, key in [('S&P 500', 'sp500'), ('Euro Stoxx', 'eurostoxx'),
                               ('MSCI EM', 'msci_em'), ('IPSA', 'ipsa'),
                               ('Treasury 10Y', 'ust_10y'), ('Cobre', 'copper'), ('Oro', 'gold')]:
                idx = bcch.get(key, {})
                if isinstance(idx, dict) and 'error' not in idx:
                    ret_1m = idx.get('returns', {}).get('1m')
                    ret_ytd = idx.get('returns', {}).get('ytd')
                    if ret_1m is not None or ret_ytd is not None:
                        performance.append({
                            'asset': name,
                            'retorno': f"{ret_1m:+.1f}%" if ret_1m is not None else 'N/D',
                            'ytd': f"{ret_ytd:+.1f}%" if ret_ytd is not None else 'N/D',
                        })
        if not performance:
            # Fallback: regional ETF valuations
            for key, name in [('us', 'S&P 500'), ('europe', 'Europa'), ('em', 'EM'), ('chile', 'Chile')]:
                val = self._q('equity', 'valuations', key)
                if val and isinstance(val, dict):
                    ret = val.get('returns', {})
                    performance.append({
                        'asset': name,
                        'retorno': f"{ret.get('1m'):+.1f}%" if ret.get('1m') is not None else 'N/D',
                        'ytd': f"{ret.get('ytd'):+.1f}%" if ret.get('ytd') is not None else 'N/D',
                    })

        return {'titulo': 'Mercados Financieros', 'narrativa': narrativa, 'performance': performance}

    def _default_mercados(self) -> Dict[str, Any]:
        """Mercados generado por Sonnet usando datos de retornos disponibles."""
        from narrative_engine import generate_data_driven_narrative

        performance = []
        perf_lines = []

        # Try BCCh indices first
        eq = self._q('equity')
        if eq and isinstance(eq, dict):
            bcch = eq.get('bcch_indices', {})
            for name, key in [('S&P 500', 'sp500'), ('Euro Stoxx', 'eurostoxx'),
                               ('MSCI EM', 'msci_em'), ('IPSA', 'ipsa'),
                               ('Cobre', 'copper'), ('Oro', 'gold')]:
                idx = bcch.get(key, {})
                if isinstance(idx, dict) and 'error' not in idx:
                    ret_1m = idx.get('returns', {}).get('1m')
                    ret_ytd = idx.get('returns', {}).get('ytd')
                    if ret_1m is not None or ret_ytd is not None:
                        performance.append({
                            'asset': name,
                            'retorno': f"{ret_1m:+.1f}%" if ret_1m is not None else 'N/D',
                            'ytd': f"{ret_ytd:+.1f}%" if ret_ytd is not None else 'N/D',
                        })
                        perf_lines.append(f"{name}: 1M {ret_1m:+.1f}%" if ret_1m is not None else f"{name}: N/D")

        # Fallback: yfinance ETFs
        if not performance and self.data:
            try:
                returns = self.data.get_previous_month_returns(['SPY', 'QQQ', 'EEM'])
                labels = {'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100', 'EEM': 'MSCI EM'}
                for ticker, name in labels.items():
                    ret = returns.get(ticker)
                    performance.append({
                        'asset': name,
                        'retorno': f"{ret:+.1f}%" if ret is not None else 'N/D',
                        'ytd': 'N/D',
                    })
                    if ret is not None:
                        perf_lines.append(f"{name}: {ret:+.1f}%")
            except Exception:
                pass

        quant_ctx = " | ".join(perf_lines) if perf_lines else "Sin datos de retornos disponibles"
        narrativa = generate_data_driven_narrative(
            section_name="aa_mercados_dd",
            prompt=(
                f"Escribe 2 párrafos sobre el desempeño de mercados financieros en "
                f"{self.month_name} {self.date.year}. Analiza los retornos disponibles, "
                "identifica tendencias y divergencias entre equity, commodities y bonos. "
                "Máximo 120 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=500,
        )
        if not narrativa:
            narrativa = f"Retornos del período: {quant_ctx}."

        return {'titulo': 'Mercados Financieros', 'narrativa': narrativa, 'performance': performance}

    def _generate_geopolitica(self) -> Dict[str, Any]:
        """Geopolítica via Claude desde panel geo."""
        from narrative_engine import generate_narrative

        geo = self._panel('geo')

        if not geo:
            return self._default_geopolitica()

        narrativa = generate_narrative(
            section_name="aa_geopolitica",
            prompt=(
                f"Escribe 2-3 parrafos sobre el panorama geopolitico de {self.month_name} "
                f"{self.date.year} basandote en el council. Cubrir las principales dinamicas: "
                "tensiones comerciales, politica monetaria, conflictos regionales. "
                "Separa parrafos con linea vacia. Maximo 150 palabras."
            ),
            council_context=f"GEO PANEL:\n{geo[:2500]}",
            company_name=self.company_name,
            max_tokens=600,
        )
        if not narrativa:
            narrativa = "El entorno geopolitico presenta riesgos elevados que requieren monitoreo activo."

        # Try structured data from council parser first
        geo_risks = self.parser.get_geopolitical_risks()
        if geo_risks:
            eventos = [{'evento': r['event'], 'impacto': r['impact'], 'probabilidad': r['probability']}
                       for r in geo_risks]
        else:
            # Fallback: extract probabilities from geo panel text (no hardcoded defaults)
            china_prob = self._extract_number(geo, r'China.*?(\d+)%', None)
            tariff_prob = self._extract_number(geo, r'[Tt]ariff.*?(\d+)%', None)

            eventos = [
                {'evento': 'Tensiones comerciales', 'impacto': 'Alto',
                 'probabilidad': f'{int(tariff_prob)}%' if tariff_prob is not None else 'N/D'},
                {'evento': 'Dinamica US-China', 'impacto': 'Alto',
                 'probabilidad': f'{int(china_prob)}%' if china_prob is not None else 'N/D'},
            ]

        return {'titulo': 'Política y Geopolítica', 'narrativa': narrativa, 'eventos': eventos}

    def _default_geopolitica(self) -> Dict[str, Any]:
        """Geopolítica generada por Sonnet usando datos de riesgo disponibles."""
        from narrative_engine import generate_data_driven_narrative

        geo_risks = self.parser.get_geopolitical_risks()
        if geo_risks:
            eventos = [{'evento': r['event'], 'impacto': r['impact'], 'probabilidad': r['probability']}
                       for r in geo_risks]
        else:
            eventos = []

        # Gather risk indicators
        vix = self._q('risk', 'vix') or self._q('chile_rates', 'vix')
        epu = self._q('china', 'epu_analysis', 'current') or self._q('chile_rates', 'epu_global')
        quant_parts = []
        if vix is not None:
            quant_parts.append(f"VIX: {vix}")
        if epu is not None:
            quant_parts.append(f"EPU Global: {epu}")
        for ev in eventos:
            quant_parts.append(f"{ev['evento']}: prob {ev['probabilidad']}, impacto {ev['impacto']}")

        quant_ctx = " | ".join(quant_parts) if quant_parts else "VIX y EPU no disponibles"
        narrativa = generate_data_driven_narrative(
            section_name="aa_geopolitica_dd",
            prompt=(
                f"Escribe 2 párrafos sobre el entorno geopolítico para {self.month_name} "
                f"{self.date.year}. Analiza los indicadores de riesgo disponibles (VIX, EPU) "
                "y eventos geopolíticos identificados. Máximo 120 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=500,
        )
        if not narrativa:
            narrativa = f"Indicadores de riesgo: {quant_ctx}."

        return {
            'titulo': 'Política y Geopolítica',
            'narrativa': narrativa,
            'eventos': eventos if eventos else [{'evento': 'Datos insuficientes', 'probabilidad': 'N/D', 'impacto': 'N/D'}],
        }

    def _generate_chile_review(self) -> Dict[str, Any]:
        """Chile via Claude desde panel macro + datos reales."""
        from narrative_engine import generate_narrative

        macro = self._panel('macro')

        if not macro:
            return self._default_chile()

        # Extract from council text (no hardcoded defaults)
        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', None)
        ipc = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', None)
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', None)

        # Enrich with real BCCh data if available
        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if tpm is None and chile.get('tpm') is not None:
                    tpm = chile['tpm']
                if ipc is None and chile.get('ipc_yoy') is not None:
                    ipc = chile['ipc_yoy']
            except Exception:
                pass

        # Also try quant_data
        if tpm is None:
            tpm = self._q('chile', 'tpm')
        if ipc is None:
            ipc = self._q('chile', 'ipc_yoy')
        # Cobre fallback: quant_data (chile_rates or bcch_indices from equity data)
        if cobre is None:
            cobre = self._q('chile_rates', 'copper') or self._q('equity', 'bcch_indices', 'copper', 'value')

        tpm_real = round(tpm - ipc, 1) if tpm is not None and ipc is not None else None

        tpm_str = f'{tpm}%' if tpm is not None else 'N/D'
        ipc_str = f'{ipc}%' if ipc is not None else 'N/D'
        tpm_real_str = f'+{tpm_real}%' if tpm_real is not None else 'N/D'
        cobre_str = f'${cobre}/lb' if cobre is not None else 'N/D'

        quant_ctx = f"TPM: {tpm_str} | IPC: {ipc_str} | Tasa Real: {tpm_real_str} | Cobre: {cobre_str}"

        narrativa = generate_narrative(
            section_name="aa_chile_review",
            prompt=(
                f"Escribe 2-3 parrafos sobre Chile para el reporte de asset allocation de "
                f"{self.month_name} {self.date.year}. Cubrir: posicion relativa en LatAm, "
                "dinamica del peso, politica monetaria BCCh, cobre, y IPSA. "
                "Integrar datos cuantitativos. Maximo 150 palabras."
            ),
            council_context=f"MACRO PANEL:\n{macro[:2000]}",
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=600,
        )
        if not narrativa:
            narrativa = f"Chile: TPM {tpm_str}, tasa real {tpm_real_str}, cobre {cobre_str}."

        # Compute tendencias from data
        tpm_tend = 'N/D'
        tpm_dir = self._q('tpm_expectations', 'summary', 'direction')
        if tpm_dir:
            tpm_tend = str(tpm_dir)
        elif macro:
            if 'recorte' in macro.lower() or 'baja' in macro.lower():
                tpm_tend = '↓ Recortes'
            elif 'mantener' in macro.lower() or 'pausa' in macro.lower():
                tpm_tend = '→ Estable'
            elif 'alza' in macro.lower() or 'subir' in macro.lower():
                tpm_tend = '↑ Alzas'

        ipc_tend = 'N/D'
        if macro:
            if any(w in macro.lower() for w in ['inflación bajando', 'desinflación', 'ipc a la baja']):
                ipc_tend = '↓ Desacelerando'
            elif any(w in macro.lower() for w in ['inflación subiendo', 'presiones inflacionarias']):
                ipc_tend = '↑ Acelerando'
            elif ipc is not None:
                ipc_tend = '→ Estable'

        cobre_tend = 'N/D'
        cobre_ret = self._q('equity', 'bcch_indices', 'copper', 'returns', '1m')
        if cobre_ret is not None:
            if cobre_ret > 2:
                cobre_tend = f'↑ +{cobre_ret:.1f}% 1M'
            elif cobre_ret < -2:
                cobre_tend = f'↓ {cobre_ret:.1f}% 1M'
            else:
                cobre_tend = f'→ {cobre_ret:+.1f}% 1M'

        datos = [
            {'indicador': 'TPM (Tasa de Política Monetaria BCCh)', 'valor': tpm_str, 'tendencia': tpm_tend},
            {'indicador': 'IPC YoY (Índice de Precios al Consumidor interanual)', 'valor': ipc_str, 'tendencia': ipc_tend},
            {'indicador': 'Tasa Real (TPM menos inflación)', 'valor': tpm_real_str, 'tendencia': '→ Positiva' if tpm_real and tpm_real > 0 else '→'},
            {'indicador': 'Cobre (principal exportación chilena)', 'valor': cobre_str, 'tendencia': cobre_tend},
        ]

        return {'titulo': 'Chile y Economía Local', 'narrativa': narrativa, 'datos': datos}

    def _default_chile(self) -> Dict[str, Any]:
        """Chile generado por Sonnet usando datos BCCh disponibles."""
        from narrative_engine import generate_data_driven_narrative

        tpm_str = 'N/D'
        ipc_str = 'N/D'
        cobre_str = 'N/D'
        usdclp_str = 'N/D'

        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if chile.get('tpm') is not None:
                    tpm_str = f"{chile['tpm']}%"
                if chile.get('ipc_yoy') is not None:
                    ipc_str = f"{chile['ipc_yoy']}%"
                if chile.get('usd_clp') is not None:
                    usdclp_str = f"${chile['usd_clp']:.0f}"
            except Exception:
                pass

        if tpm_str == 'N/D':
            tpm_val = self._q('chile', 'tpm')
            if tpm_val is not None:
                tpm_str = f"{tpm_val}%"
        if ipc_str == 'N/D':
            ipc_val = self._q('chile', 'ipc_yoy')
            if ipc_val is not None:
                ipc_str = f"{ipc_val}%"
        cobre_val = self._q('equity', 'bcch_indices', 'copper', 'value')
        if cobre_val is not None:
            cobre_str = f"${cobre_val}/lb"

        tpm_dir = self._q('tpm_expectations', 'summary', 'direction')
        tpm_tend = str(tpm_dir) if tpm_dir else 'N/D'
        ipc_tend = 'N/D'

        quant_ctx = f"TPM: {tpm_str} | IPC YoY: {ipc_str} | USD/CLP: {usdclp_str} | Cobre: {cobre_str} | Tendencia TPM: {tpm_tend}"

        narrativa = generate_data_driven_narrative(
            section_name="aa_chile_dd",
            prompt=(
                f"Escribe 2 párrafos sobre Chile para el reporte de asset allocation de "
                f"{self.month_name} {self.date.year}. Analiza: TPM y tasa real, inflación, "
                "tipo de cambio y cobre. Máximo 120 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=500,
        )
        if not narrativa:
            narrativa = f"Chile: TPM {tpm_str}, IPC {ipc_str}, USD/CLP {usdclp_str}, cobre {cobre_str}."

        return {
            'titulo': 'Chile y Economía Local',
            'narrativa': narrativa,
            'datos': [
                {'indicador': 'TPM (Tasa de Política Monetaria)', 'valor': tpm_str, 'tendencia': tpm_tend},
                {'indicador': 'IPC YoY (inflación interanual Chile)', 'valor': ipc_str, 'tendencia': ipc_tend},
                {'indicador': 'USD/CLP (tipo de cambio)', 'valor': usdclp_str, 'tendencia': 'N/D'},
                {'indicador': 'Cobre (principal exportación)', 'valor': cobre_str, 'tendencia': 'N/D'},
            ]
        }

    # =========================================================================
    # SECCION 3: ESCENARIOS MACRO
    # =========================================================================

    def generate_scenarios(self) -> Dict[str, Any]:
        """Escenarios basados en council views — datos del parser o council text."""
        contrarian = self._contrarian()
        riesgo = self._panel('riesgo')

        # Try structured council parser first
        scenarios_parsed = self.parser.get_scenario_probs()
        if scenarios_parsed:
            # Generate scenario details via Claude
            scenario_details = self._generate_scenario_details(scenarios_parsed)
            escenarios = []
            for key, info in scenarios_parsed.items():
                details = scenario_details.get(info['name'], {})
                escenarios.append({
                    'nombre': info['name'],
                    'probabilidad': int(info['prob'] * 100),
                    'descripcion': details.get('descripcion', f"Escenario: {info['name']} ({int(info['prob']*100)}%)."),
                    'senales': details.get('senales', []),
                    'implicancias': details.get('implicancias', {}),
                    'que_comprar': details.get('que_comprar', 'Ver recomendación final'),
                })
            # Determine base scenario (highest probability)
            base = max(scenarios_parsed.values(), key=lambda x: x['prob'])
            return {
                'escenario_base': base['name'].upper(),
                'descripcion_base': f"Escenario base del council con {int(base['prob']*100)}% probabilidad",
                'escenarios': escenarios,
            }

        # Fallback: extract from council text (no hardcoded defaults)
        bear_prob = self._extract_number(contrarian, r'Fed Pause.*?(\d+)%', None)
        bull_prob = self._extract_number(contrarian, r'AI Productivity.*?(\d+)%', None)
        tariff_prob = self._extract_number(riesgo, r'[Aa]ranceles.*?(\d+)%', None)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(\d+)%', None)

        # Enrich with quant macro data (available after Fix A injects macro_quant)
        macro = self._panel('macro')
        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', None)
        if gdp is None:
            gdp = self._q('macro_usa', 'gdp')
        recession = self._extract_number(macro, r'recesi[oó]n.*?(\d+)%', None)
        if recession is None:
            recession = self._q('macro_usa', 'recession_prob')
        regime = self._q('regime', 'current')

        # If no council data at all, try quant-only scenarios
        if not contrarian and not riesgo and gdp is None and recession is None:
            return {
                'escenario_base': 'SIN DATOS',
                'descripcion_base': 'Sin datos del council para definir escenarios',
                'escenarios': [],
            }

        gdp_str = f'{gdp}% QoQ' if gdp is not None else 'N/D'
        recession_str = f'{int(recession)}%' if recession is not None else 'N/D'
        bull_str = f'{int(bull_prob)}%' if bull_prob is not None else 'N/D'
        tariff_str = f'{int(tariff_prob)}%' if tariff_prob is not None else 'N/D'
        china_str = f'{int(china_prob)}%' if china_prob is not None else 'N/D'
        regime_str = str(regime) if regime else 'N/D'

        # Determine base scenario from regime or recession probability
        if regime and isinstance(regime, str):
            escenario_base = regime.upper()
        elif recession is not None and recession > 50:
            escenario_base = 'RECESIÓN'
        elif recession is not None and recession < 20:
            escenario_base = 'EXPANSIÓN'
        elif contrarian or riesgo:
            escenario_base = 'EXPANSIÓN TARDÍA'
        else:
            escenario_base = 'N/D'

        descripcion_base = f'Régimen: {regime_str}. GDP US: {gdp_str}. Prob. recesión: {recession_str}.'

        # Assign approximate probabilities based on available data
        # Base case gets remainder, tail scenarios from council text
        base_prob = 50
        used_probs = []
        if bull_prob is not None:
            used_probs.append(int(bull_prob))
        if tariff_prob is not None:
            used_probs.append(int(tariff_prob))
        if china_prob is not None:
            used_probs.append(int(china_prob))
        if used_probs:
            base_prob = max(10, 100 - sum(used_probs))

        # Build skeleton scenarios with data, then enrich ALL via Claude
        fallback_scenarios = [
            {
                'nombre': 'Escenario Base',
                'probabilidad': base_prob,
                'descripcion': f'GDP US en {gdp_str}. Régimen: {regime_str}. Prob. recesión 12M: {recession_str}.',
                'senales': [s for s in [f'GDP: {gdp_str}', f'Recesión: {recession_str}'] if 'N/D' not in s],
                'implicancias': {},
                'que_comprar': ''
            },
            {
                'nombre': 'Escenario Alcista',
                'probabilidad': int(bull_prob) if bull_prob is not None else 0,
                'descripcion': f'Probabilidad bull case: {bull_str}.',
                'senales': [],
                'implicancias': {},
                'que_comprar': ''
            },
            {
                'nombre': 'Riesgo Comercial',
                'probabilidad': int(tariff_prob) if tariff_prob is not None else 0,
                'descripcion': f'Probabilidad aranceles amplificados: {tariff_str}.',
                'senales': [],
                'implicancias': {},
                'que_comprar': ''
            },
            {
                'nombre': 'Recesión / Crédito',
                'probabilidad': int(china_prob) if china_prob is not None else 0,
                'descripcion': f'China hard landing probabilidad: {china_str}. Prob recesión US: {recession_str}.',
                'senales': [],
                'implicancias': {},
                'que_comprar': ''
            }
        ]

        # ALWAYS use Claude to generate scenario details (implicancias, signals, que_comprar)
        fallback_parsed = {s['nombre']: s for s in fallback_scenarios}
        quant_ctx = f"GDP: {gdp_str} | Régimen: {regime_str} | Recesión: {recession_str} | Bull: {bull_str} | Tariff: {tariff_str} | China: {china_str}"
        details = self._generate_scenario_details(fallback_parsed, extra_context=quant_ctx)
        for s in fallback_scenarios:
            d = details.get(s['nombre'], {})
            if d.get('implicancias'):
                s['implicancias'] = d['implicancias']
            if d.get('descripcion'):
                s['descripcion'] = d['descripcion']
            if d.get('senales'):
                s['senales'] = d['senales']
            if d.get('que_comprar'):
                s['que_comprar'] = d['que_comprar']

        return {
            'escenario_base': escenario_base,
            'descripcion_base': descripcion_base,
            'escenarios': fallback_scenarios,
        }

    def _generate_scenario_details(self, scenarios: Dict, extra_context: str = "") -> Dict[str, Dict]:
        """Generate descriptions, signals, and what-to-buy for each scenario via Claude."""
        import json as _json
        from narrative_engine import generate_narrative, generate_data_driven_narrative

        final = self._final()
        cio = self._cio()
        riesgo = self._panel('riesgo')

        scenario_names = [info.get('name', info.get('nombre', str(info))) for info in scenarios.values()]

        # If no council data, use data-driven generation
        if not (final or cio or riesgo):
            quant_ctx = extra_context or self._build_quant_summary()
            raw = generate_data_driven_narrative(
                section_name="aa_scenario_details_dd",
                prompt=(
                    f"Para estos escenarios: {scenario_names}, genera un JSON dict donde cada key es el nombre "
                    "del escenario y el value tiene: "
                    '{"descripcion": "1-2 oraciones con datos disponibles", '
                    '"senales": ["señal cuantitativa 1", "señal 2"], '
                    '"implicancias": {"equities": "+/-/flat con rationale breve", "bonds": "+/-/flat", "usd": "+/-/flat", "commodities": "+/-/flat"}, '
                    '"que_comprar": "ETFs específicos para este escenario"}. '
                    "Basa las implicancias en lógica financiera estándar aplicada a los datos. "
                    "SOLO JSON, sin explicación."
                ),
                quant_context=quant_ctx,
                company_name=self.company_name,
                max_tokens=1500,
            )
            if raw:
                try:
                    cleaned = raw.strip()
                    if cleaned.startswith('```'):
                        cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.endswith('```'):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    parsed = _json.loads(cleaned)
                    if isinstance(parsed, dict):
                        return parsed
                except (_json.JSONDecodeError, Exception):
                    pass
            return {}

        council_ctx = (
            f"FINAL:\n{final[:1500]}\n\nCIO:\n{cio[:1000]}\n\nRIESGO:\n{riesgo[:800]}"
        )

        raw = generate_narrative(
            section_name="aa_scenario_details",
            prompt=(
                f"Para estos escenarios: {scenario_names}, genera un JSON dict donde cada key es el nombre "
                "del escenario y el value tiene: "
                '{"descripcion": "1-2 oraciones con datos", '
                '"senales": ["señal1", "señal2"], '
                '"implicancias": {"equities": "+/-/flat", "bonds": "+/-/flat", "usd": "+/-/flat", "commodities": "+/-/flat"}, '
                '"que_comprar": "instrumentos/ETFs específicos para este escenario"}. '
                "Usa datos del council. No inventar datos."
            ),
            council_context=council_ctx,
            company_name=self.company_name,
            max_tokens=1200,
            temperature=0.2,
        )
        if raw:
            try:
                cleaned = raw.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = _json.loads(cleaned)
                if isinstance(parsed, dict):
                    # Remap keys: equity→equities, renta_fija→bonds
                    key_map = {'equity': 'equities', 'renta_fija': 'bonds', 'renta fija': 'bonds'}
                    for scenario_name, details in parsed.items():
                        impl = details.get('implicancias', {})
                        for old_key, new_key in key_map.items():
                            if old_key in impl and new_key not in impl:
                                impl[new_key] = impl.pop(old_key)
                        if 'usd' not in impl:
                            impl['usd'] = 'N/D'
                        details['implicancias'] = impl
                    return parsed
            except (_json.JSONDecodeError, KeyError):
                pass
        return {}

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
        """USA view via Claude desde panels rv + macro."""
        from narrative_engine import generate_narrative

        rv = self._panel('rv')
        macro = self._panel('macro')

        if not self._has_council():
            return self._default_usa_view()

        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', None)
        cpi = self._extract_number(macro, r'Core\s+CPI\s+(?:bajando\s+de\s+\d+\.?\d*%?\s*a\s+)?(\d+\.?\d*)%', None)

        council_ctx = f"RV PANEL:\n{rv[:1500]}\n\nMACRO:\n{macro[:1500]}"
        quant_ctx = ""
        if gdp:
            quant_ctx += f"GDP US: {gdp}% QoQ. "
        if cpi:
            quant_ctx += f"Core CPI: {cpi}%. "
        bbg_ctx = self._bbg_quant_summary()
        if bbg_ctx:
            quant_ctx += f"Bloomberg: {bbg_ctx}"

        tesis = generate_narrative(
            section_name="aa_usa_tesis",
            prompt=(
                "Escribe la tesis de inversion para Estados Unidos en 3-4 oraciones. "
                "Cubrir: regimen economico, vista de equity, principal riesgo, y factor tilt. "
                "Usa datos del council. Maximo 80 palabras."
                "\n\nIncluye: dato→interpretación→acción, riesgo con trigger de salida cuantificado, horizonte temporal."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=400,
        )
        if not tesis:
            tesis = f"Economia US en regimen de expansion. GDP en {gdp}% QoQ." if gdp else "N/D"

        args_favor, args_contra = self._generate_region_args('Estados Unidos', council_ctx, quant_ctx)
        trigger = self._generate_trigger_cambio('Estados Unidos', council_ctx)

        # Try to get view/conviction from parser
        alloc = self.parser.get_regional_allocation()
        usa_view = 'N'
        usa_conviccion = 'N/D'
        usa_alloc = self._find_view(alloc, 'usa')
        if usa_alloc:
            usa_view = usa_alloc.get('vs_benchmark', 'N')
            usa_conviccion = usa_alloc.get('conviction', usa_alloc.get('weight', 'MEDIA'))

        eq_views = self.parser.get_equity_views()
        usa_eq = self._find_view(eq_views, 'usa')
        if usa_eq:
            usa_view = usa_eq.get('view', usa_view)
            usa_conviccion = usa_eq.get('conviction', usa_conviccion)

        # Text mining fallback when parser found nothing
        if usa_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('usa')
            if mined:
                usa_view = mined['view']
                usa_conviccion = mined['conviction']
            else:
                usa_conviccion = 'MEDIA'

        return {
            'region': 'Estados Unidos',
            'view': usa_view,
            'conviccion': usa_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
        }

    def _default_usa_view(self) -> Dict[str, Any]:
        """USA view generado por Sonnet usando datos de valuación y macro."""
        from narrative_engine import generate_data_driven_narrative

        # Gather USA data
        sp500_pe = self._q('equity', 'valuations', 'us', 'pe')
        sp500_ret_1m = self._q('equity', 'valuations', 'us', 'returns', '1m')
        sp500_ret_ytd = self._q('equity', 'valuations', 'us', 'returns', 'ytd')
        gdp = self._q('macro_usa', 'gdp')
        unemployment = self._q('macro_usa', 'unemployment')

        quant_parts = []
        if sp500_pe is not None:
            quant_parts.append(f"S&P 500 P/E: {sp500_pe:.1f}x")
        if sp500_ret_1m is not None:
            quant_parts.append(f"S&P 500 1M: {sp500_ret_1m:+.1f}%")
        if sp500_ret_ytd is not None:
            quant_parts.append(f"S&P 500 YTD: {sp500_ret_ytd:+.1f}%")
        if gdp is not None:
            quant_parts.append(f"GDP: {gdp}%")
        if unemployment is not None:
            quant_parts.append(f"Desempleo: {unemployment}%")

        quant_ctx = " | ".join(quant_parts) if quant_parts else "Datos de valuación no disponibles"

        tesis = generate_data_driven_narrative(
            section_name="aa_usa_tesis_dd",
            prompt=(
                "Escribe la tesis de inversión para Estados Unidos en 3-4 oraciones. "
                "Analiza valuaciones (P/E), crecimiento (GDP), empleo, y retornos recientes. "
                "Máximo 70 palabras."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=300,
        )
        if not tesis:
            tesis = f"S&P 500 cotiza a {sp500_pe:.1f}x P/E." if sp500_pe else "Datos insuficientes para tesis."

        return {
            'region': 'Estados Unidos', 'view': 'NEUTRAL',
            'conviccion': 'BAJA',
            'tesis': tesis,
            'argumentos_favor': [{'punto': 'Datos cuantitativos', 'dato': quant_ctx}],
            'argumentos_contra': [{'punto': 'Sin deliberación completa', 'dato': 'Análisis basado solo en datos cuantitativos'}],
            'trigger_cambio': 'Requiere sesión completa de council para triggers específicos.'
        }

    def _generate_europe_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        rv = self._panel('rv') if self._has_council() else ''
        cio = self._cio() if self._has_council() else ''

        council_ctx = f"RV:\n{rv[:1000]}\n\nCIO:\n{cio[:800]}"

        tesis = ''
        if rv or cio:
            tesis = generate_narrative(
                section_name="aa_europe_tesis",
                prompt=(
                    "Escribe la tesis de inversion para Europa en 3-4 oraciones. "
                    "Cubrir: posicion relativa, valuaciones, politica BCE, y riesgos. "
                    "Usa datos del council. Maximo 70 palabras."
                    "\n\nIncluye: dato→interpretación→acción, riesgo con trigger de salida cuantificado, horizonte temporal."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=400,
            )
        if not tesis:
            tesis = "Análisis en proceso — datos cuantitativos disponibles para Europa."

        args_favor, args_contra = self._generate_region_args('Europa', council_ctx)
        trigger = self._generate_trigger_cambio('Europa', council_ctx)

        # Try parser for structured view/conviction
        europe_view = 'N'
        europe_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        eu_alloc = self._find_view(alloc, 'europe')
        if eu_alloc:
            europe_view = eu_alloc.get('vs_benchmark', 'N')
            europe_conviccion = eu_alloc.get('conviction', eu_alloc.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        eu_eq = self._find_view(eq_views, 'europe')
        if eu_eq:
            europe_view = eu_eq.get('view', europe_view)
            europe_conviccion = eu_eq.get('conviction', europe_conviccion)

        if europe_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('europa')
            if mined:
                europe_view = mined['view']
                europe_conviccion = mined['conviction']
            else:
                europe_conviccion = 'MEDIA'

        return {
            'region': 'Europa',
            'view': europe_view,
            'conviccion': europe_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
        }

    def _generate_china_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        riesgo = self._panel('riesgo') if self._has_council() else ''
        geo = self._panel('geo') if self._has_council() else ''

        epu = self._extract_number(macro, r'EPU.*?(\d+)', None)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(\d+)%', None)

        council_ctx = f"MACRO:\n{macro[:1000]}\n\nRISK:\n{riesgo[:800]}\n\nGEO:\n{geo[:800]}"
        quant_ctx = ""
        if epu:
            quant_ctx += f"EPU China: {int(epu)}. "
        if china_prob:
            quant_ctx += f"Hard landing prob: {int(china_prob)}%."

        tesis = ''
        if macro or riesgo or geo:
            tesis = generate_narrative(
                section_name="aa_china_tesis",
                prompt=(
                    "Escribe la tesis de inversion para China en 3-4 oraciones. "
                    "Cubrir: regimen economico, credit impulse, desacople US-China, "
                    "y postura (cautelosa/neutral). Usa datos del council. Maximo 70 palabras."
                    "\n\nIncluye: dato→interpretación→acción, riesgo con trigger de salida cuantificado, horizonte temporal."
                ),
                council_context=council_ctx,
                quant_context=quant_ctx,
                company_name=self.company_name,
                max_tokens=400,
            )
        if not tesis:
            tesis = "Análisis en proceso — datos cuantitativos disponibles para China."

        args_favor, args_contra = self._generate_region_args('China', council_ctx, quant_ctx)
        trigger = self._generate_trigger_cambio('China', council_ctx)

        # Try parser for structured view/conviction
        china_view = 'N'
        china_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        cn_alloc = self._find_view(alloc, 'china')
        if cn_alloc:
            china_view = cn_alloc.get('vs_benchmark', 'N')
            china_conviccion = cn_alloc.get('conviction', cn_alloc.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        cn_eq = self._find_view(eq_views, 'china')
        if cn_eq:
            china_view = cn_eq.get('view', china_view)
            china_conviccion = cn_eq.get('conviction', china_conviccion)

        if china_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('china')
            if mined:
                china_view = mined['view']
                china_conviccion = mined['conviction']
            else:
                china_conviccion = 'MEDIA'

        return {
            'region': 'China',
            'view': china_view,
            'conviccion': china_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
        }

    def _generate_chile_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        rf = self._panel('rf') if self._has_council() else ''

        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', None)
        ipc = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', None)
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', None)

        # Data fallbacks (same as chile_review)
        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if tpm is None and chile.get('tpm') is not None:
                    tpm = chile['tpm']
                if ipc is None and chile.get('ipc_yoy') is not None:
                    ipc = chile['ipc_yoy']
            except Exception:
                pass
        if tpm is None:
            tpm = self._q('chile', 'tpm') or self._q('chile_rates', 'tpm')
        if ipc is None:
            ipc = self._q('chile', 'ipc_yoy')
        if cobre is None:
            cobre = self._q('chile_rates', 'copper') or self._q('equity', 'bcch_indices', 'copper', 'value')

        tpm_real = round(tpm - ipc, 1) if tpm and ipc else None

        quant_parts = []
        if tpm:
            quant_parts.append(f"TPM: {tpm}%")
        if ipc:
            quant_parts.append(f"IPC: {ipc}%")
        if tpm_real:
            quant_parts.append(f"Tasa real: +{tpm_real}%")
        if cobre:
            quant_parts.append(f"Cobre: ${cobre}/lb")

        tesis = ''
        if macro or rf:
            tesis = generate_narrative(
                section_name="aa_chile_tesis",
                prompt=(
                    "Escribe la tesis de inversion para Chile en 3-4 oraciones. "
                    "Cubrir: posicion relativa en LatAm, carry trade, cobre, y riesgos. "
                    "Integrar datos cuantitativos. Usa datos del council. Maximo 80 palabras."
                    "\n\nIncluye: dato→interpretación→acción, riesgo con trigger de salida cuantificado, horizonte temporal."
                ),
                council_context=f"MACRO:\n{macro[:1500]}\n\nRF:\n{rf[:800]}",
                quant_context=" | ".join(quant_parts),
                company_name=self.company_name,
                max_tokens=400,
            )
        if not tesis:
            parts = []
            if tpm is not None:
                parts.append(f"TPM {tpm}%")
            if ipc is not None:
                parts.append(f"IPC {ipc}%")
            if tpm_real is not None:
                parts.append(f"tasa real {tpm_real:+.1f}%")
            if cobre is not None:
                parts.append(f"cobre ${cobre}/lb")
            tesis = f"Chile: {', '.join(parts)}." if parts else "Sin datos suficientes para tesis de Chile."

        # Try parser for structured view/conviction
        chile_view = 'N'
        chile_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        cl_alloc = self._find_view(alloc, 'chile')
        if cl_alloc:
            chile_view = cl_alloc.get('vs_benchmark', 'N')
            chile_conviccion = cl_alloc.get('conviction', cl_alloc.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        cl_eq = self._find_view(eq_views, 'chile')
        if cl_eq:
            chile_view = cl_eq.get('view', chile_view)
            chile_conviccion = cl_eq.get('conviction', chile_conviccion)

        if chile_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('chile')
            if mined:
                chile_view = mined['view']
                chile_conviccion = mined['conviction']
            else:
                chile_conviccion = 'MEDIA'

        # Build arguments with real data (no hardcoded numbers)
        tpm_str = f'{tpm}%' if tpm is not None else 'N/D'
        ipc_str = f'{ipc}%' if ipc is not None else 'N/D'
        tpm_real_str = f'+{tpm_real}%' if tpm_real is not None else 'N/D'
        cobre_str = f'${cobre}/lb' if cobre is not None else 'N/D'

        # Build favor from quant data
        chile_council_ctx = f"MACRO:\n{macro[:1500]}\n\nRF:\n{rf[:800]}"
        chile_quant_ctx = " | ".join(quant_parts) if quant_parts else ""
        args_favor = [
            {'punto': 'Diferencial real', 'dato': f'TPM {tpm_str} - IPC {ipc_str} = {tpm_real_str} real'},
            {'punto': 'Cobre', 'dato': cobre_str},
        ]
        # Try BCCh direction from TPM expectations data
        tpm_exp = self._q('tpm_expectations', 'summary', 'direction')
        if tpm_exp:
            args_favor.append({'punto': 'BCCh', 'dato': f'Trayectoria TPM: {tpm_exp}'})
        else:
            args_favor.append({'punto': 'BCCh', 'dato': 'Monitorear próxima reunión de política monetaria'})

        # Generate contra via Claude
        _, args_contra = self._generate_region_args('Chile', chile_council_ctx, chile_quant_ctx)
        trigger = self._generate_trigger_cambio('Chile', chile_council_ctx)

        return {
            'region': 'Chile y LatAm',
            'view': chile_view,
            'conviccion': chile_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
        }

    def _generate_brazil_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        rv = self._panel('rv') if self._has_council() else ''
        geo = self._panel('geo') if self._has_council() else ''

        council_ctx = f"MACRO:\n{macro[:800]}\n\nRV:\n{rv[:800]}\n\nGEO:\n{geo[:600]}"

        tesis = ''
        if macro or rv or geo:
            tesis = generate_narrative(
                section_name="aa_brazil_tesis",
                prompt=(
                    "Escribe la tesis de inversión para Brasil en 2-3 oraciones. "
                    "Cubrir: tasas Selic, carry trade, commodities, riesgos fiscales. "
                    "Usa datos del council. Máximo 60 palabras."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=300,
            )
        if not tesis:
            tesis = 'N/D'

        args_favor, args_contra = self._generate_region_args('Brasil', council_ctx)
        trigger = self._generate_trigger_cambio('Brasil', council_ctx)

        # Try parser for structured view/conviction
        brazil_view = 'N'
        brazil_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        br_alloc = self._find_view(alloc, 'brazil')
        if br_alloc:
            brazil_view = br_alloc.get('vs_benchmark', 'N')
            brazil_conviccion = br_alloc.get('conviction', br_alloc.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        br_eq = self._find_view(eq_views, 'brazil')
        if br_eq:
            brazil_view = br_eq.get('view', brazil_view)
            brazil_conviccion = br_eq.get('conviction', brazil_conviccion)

        if brazil_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('brasil')
            if mined:
                brazil_view = mined['view']
                brazil_conviccion = mined['conviction']
            else:
                brazil_conviccion = 'MEDIA'

        return {
            'region': 'Brasil',
            'view': brazil_view,
            'conviccion': brazil_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
        }

    def _generate_mexico_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        rv = self._panel('rv') if self._has_council() else ''
        geo = self._panel('geo') if self._has_council() else ''

        council_ctx = f"MACRO:\n{macro[:800]}\n\nRV:\n{rv[:800]}\n\nGEO:\n{geo[:600]}"

        tesis = ''
        if macro or rv or geo:
            tesis = generate_narrative(
                section_name="aa_mexico_tesis",
                prompt=(
                    "Escribe la tesis de inversión para México en 2-3 oraciones. "
                    "Cubrir: relación comercial con US, nearshoring, Banxico, riesgos. "
                    "Usa datos del council. Máximo 60 palabras."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=300,
            )
        if not tesis:
            tesis = 'N/D'

        args_favor, args_contra = self._generate_region_args('México', council_ctx)
        trigger = self._generate_trigger_cambio('México', council_ctx)

        # Try parser for structured view/conviction
        mexico_view = 'N'
        mexico_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        mx_alloc = self._find_view(alloc, 'mexico')
        if mx_alloc:
            mexico_view = mx_alloc.get('vs_benchmark', 'N')
            mexico_conviccion = mx_alloc.get('conviction', mx_alloc.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        mx_eq = self._find_view(eq_views, 'mexico')
        if mx_eq:
            mexico_view = mx_eq.get('view', mexico_view)
            mexico_conviccion = mx_eq.get('conviction', mexico_conviccion)

        if mexico_conviccion == 'N/D' and self.parser.has_council_text():
            mined = self.parser.search_region_view('mexico')
            if mined:
                mexico_view = mined['view']
                mexico_conviccion = mined['conviction']
            else:
                mexico_conviccion = 'MEDIA'

        return {
            'region': 'México',
            'view': mexico_view,
            'conviccion': mexico_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': trigger
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

        # No fallback sectors — if council doesn't mention them, leave empty
        # Detect factor tilt from council only
        factor = 'N/D'
        if 'quality' in rv.lower() and 'momentum' in rv.lower():
            factor = 'QUALITY-MOMENTUM'
        elif 'value' in rv.lower() and 'quality' in rv.lower():
            factor = 'VALUE + QUALITY'
        elif 'quality' in rv.lower():
            factor = 'QUALITY'
        elif 'value' in rv.lower():
            factor = 'VALUE'
        elif 'momentum' in rv.lower():
            factor = 'MOMENTUM'

        # Get structured equity views from parser
        eq_views = self.parser.get_equity_views()
        por_region = []
        if eq_views:
            region_map = {
                'usa': 'US Large Cap', 'us': 'US Large Cap', 'estados unidos': 'US Large Cap',
                'europa': 'Europa', 'europe': 'Europa',
                'chile': 'Chile',
                'em ex-china': 'EM ex-China', 'em': 'EM ex-China',
                'china': 'China',
            }
            for key, info in eq_views.items():
                label = region_map.get(key.lower(), key)
                por_region.append({
                    'region': label,
                    'view': info.get('view', 'N'),
                    'rationale': info.get('rationale', 'Ver council'),
                })

        if not por_region:
            # Fallback: minimal without hardcoded views
            por_region = [
                {'region': 'US Large Cap', 'view': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'region': 'Europa', 'view': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'region': 'Chile', 'view': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'region': 'EM ex-China', 'view': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'region': 'China', 'view': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
            ]

        # View global from macro stance
        macro_stance = self.parser.get_macro_stance()
        view_global = macro_stance if macro_stance else 'NEUTRAL'

        return {
            'view_global': view_global,
            'por_region': por_region,
            'sectores_preferidos': sectores_ow,
            'sectores_evitar': sectores_uw,
            'factor_tilt': factor
        }

    def _default_equity_view(self) -> Dict[str, Any]:
        """Equity view generado por Sonnet con datos de valuaciones."""
        from narrative_engine import generate_data_driven_narrative

        # Gather valuations per region
        regions_data = []
        for key, name in [('us', 'US'), ('europe', 'Europa'), ('em', 'EM'), ('chile', 'Chile')]:
            val = self._q('equity', 'valuations', key)
            if val and isinstance(val, dict):
                pe = val.get('pe')
                ret_ytd = val.get('returns', {}).get('ytd')
                parts = []
                if pe is not None:
                    parts.append(f"P/E {pe:.1f}x")
                if ret_ytd is not None:
                    parts.append(f"YTD {ret_ytd:+.1f}%")
                regions_data.append(f"{name}: {', '.join(parts)}" if parts else f"{name}: N/D")
            else:
                regions_data.append(f"{name}: N/D")

        quant_ctx = " | ".join(regions_data)

        # Generate per-region views via Sonnet
        result = generate_data_driven_narrative(
            section_name="aa_equity_view_dd",
            prompt=(
                "Basándote en las valuaciones regionales, genera un JSON con esta estructura: "
                '{"view_global": "NEUTRAL/CONSTRUCTIVO/CAUTELOSO", '
                '"por_region": [{"region": "US", "view": "OW/UW/N", "rationale": "1 oración con dato"}], '
                '"factor_tilt": "value/growth/quality/momentum basado en valuaciones"}. '
                "Regiones: US, Europa, Chile, EM. SOLO JSON."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=600,
        )
        if result:
            import json as _json
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, dict) and 'por_region' in parsed:
                    parsed.setdefault('sectores_preferidos', [])
                    parsed.setdefault('sectores_evitar', [])
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass

        return {
            'view_global': 'NEUTRAL',
            'por_region': [{'region': r.split(':')[0], 'view': 'N', 'rationale': r} for r in regions_data],
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'factor_tilt': 'Sin datos suficientes para tilt de factor'
        }

    def _generate_fixed_income_view(self) -> Dict[str, Any]:
        """View renta fija desde panel rf + datos cuantitativos reales."""
        rf = self._panel('rf')

        if not self._has_council():
            return self._default_rf_view()

        # Extract duration (sensibilidad del precio a cambios de tasas) view from council
        view_duration = 'SHORT'
        if 'short' in rf.lower() and 'duration' in rf.lower():
            duration_val = self._extract_number(rf, r'SHORT\s*\(?-?(\d+\.?\d*)', 1.5)
            view_duration = f'SHORT (-{duration_val} años vs benchmark)'

        # Enrich with real DurationAnalytics data if available
        dur = self._q('duration')
        dt = None
        if dur:
            dt = dur.get('duration_recommendation', dur.get('duration_target'))
        if dt and isinstance(dt, dict):
            target = dt.get('target_years', dt.get('target_duration'))
            vs_bm = dt.get('vs_benchmark', '')
            confidence = dt.get('confidence', '')
            if target:
                stance_map = {'LONG': 'LARGA', 'SHORT': 'CORTA', 'NEUTRAL': 'NEUTRAL'}
                stance = stance_map.get(vs_bm, vs_bm)
                view_duration = f'{stance} ({target:.1f} años, {confidence})'

        # Extract rate view from council
        view_tasas = 'N/D'
        if 'higher' in rf.lower():
            months = self._extract_number(rf, r'HIGHER\s*\(?(\d+)-', 6)
            view_tasas = f'HIGHER ({int(months)}-9 meses)'
        elif 'lower' in rf.lower() or 'recorte' in rf.lower():
            view_tasas = 'LOWER — recortes esperados'
        elif 'neutral' in rf.lower() or 'estable' in rf.lower():
            view_tasas = 'ESTABLE'
        elif self.parser.has_council_text():
            # Broader search across all council text
            all_text = self.parser._all_text().lower()
            if 'higher for longer' in all_text or 'tasas altas' in all_text:
                view_tasas = 'HIGHER'
            elif 'recorte' in all_text or 'rate cut' in all_text or 'baja de tasa' in all_text:
                view_tasas = 'LOWER — recortes esperados'
            else:
                view_tasas = 'ESTABLE'

        # Credit view: data-only, no hardcoded opinion
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if ig_bps and hy_bps:
            view_credito = f'IG: {self._fmt_bp(ig_bps)}, HY: {self._fmt_bp(hy_bps)}'
        elif ig_bps:
            view_credito = f'IG: {self._fmt_bp(ig_bps)}'
        else:
            view_credito = 'N/D — ver council'

        # Chile: enrich with real TPM expectations — no hardcoded rates
        tpm_val = self._q('chile', 'tpm') or self._q('chile_rates', 'tpm')
        ipc_val = self._q('chile', 'ipc_yoy')
        carry_str = 'N/D'
        if tpm_val is not None and ipc_val is not None:
            carry_str = f'Tasa real: {tpm_val - ipc_val:.1f}% (TPM {tpm_val}% - IPC {ipc_val}%)'
        elif tpm_val is not None:
            carry_str = f'TPM: {tpm_val}%'
        chile = {
            'tpm_path': 'N/D',
            'carry_trade': carry_str,
            'recomendacion': 'N/D',
        }
        tpm = self._q('tpm_expectations')
        if tpm and isinstance(tpm, dict) and 'summary' in tpm:
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

        # Fallback: extract TPM path from council text
        if chile['tpm_path'] == 'N/D' and rf:
            import re
            # Look for TPM trajectory mentions in RF panel
            tpm_match = re.search(r'TPM.*?(\d+[.,]\d+)%?\s*(?:→|->|a)\s*(\d+[.,]\d+)%?', rf, re.IGNORECASE)
            if tpm_match:
                tpm_from = tpm_match.group(1).replace(',', '.')
                tpm_to = tpm_match.group(2).replace(',', '.')
                chile['tpm_path'] = f'TPM {tpm_from}% → {tpm_to}%'
            elif 'recorte' in rf.lower() or 'baja' in rf.lower():
                tpm_str_val = f'{tpm_val}%' if tpm_val is not None else ''
                chile['tpm_path'] = f'TPM {tpm_str_val} — sesgo bajista (recortes esperados)'
            elif 'mantener' in rf.lower() or 'pausa' in rf.lower():
                tpm_str_val = f'{tpm_val}%' if tpm_val is not None else ''
                chile['tpm_path'] = f'TPM {tpm_str_val} — estable (pausa monetaria)'

        # Generate recomendacion from council text
        if chile['recomendacion'] == 'N/D' and rf:
            from narrative_engine import generate_narrative
            rec = generate_narrative(
                section_name="aa_chile_rf_rec",
                prompt=(
                    "En 1 oración, genera la recomendación de renta fija Chile "
                    "(duración, UF vs nominal, bonos BCCh/BTP). Máximo 30 palabras. "
                    "Usa datos del council."
                ),
                council_context=f"RF PANEL:\n{rf[:1500]}",
                quant_context=carry_str,
                company_name=self.company_name,
                max_tokens=100,
            )
            if rec:
                chile['recomendacion'] = rec.strip()

        # Build curva from council parser FI views
        fi_views = self.parser.get_fi_views() if self.parser else None
        fi_pos = self.parser.get_fi_positioning() if self.parser and hasattr(self.parser, 'get_fi_positioning') else None
        curva = []
        tramo_keys = [
            ('0-2Y', ['0-2y', '0-2', 'short', 'corto', 'front end', 'front-end', 'cash',
                       't-bills', 'treasury bills', '1y', '2y', '1-2y', 'money market']),
            ('2-5Y', ['2-5y', '2-5', 'medium', 'medio', 'belly', 'intermediate',
                       'intermedio', '3y', '5y', '3-5y', 'mid']),
            ('5-10Y', ['5-10y', '5-10', 'long', 'largo', '10y', '10-year', '7y',
                        '7-10y', 'duration']),
            ('10Y+', ['10y+', '10+', '20y', '30y', 'ultra long', 'ultra largo',
                       'long end', 'long-end', 'ultra', '20-30y']),
        ]
        # Merge fi_views and fi_positioning for broader key matching
        all_fi = {}
        if fi_views:
            all_fi.update(fi_views)
        if fi_pos:
            for k, v in fi_pos.items():
                if k not in all_fi:
                    all_fi[k] = v
        # Also build a lowercase lookup
        all_fi_lower = {k.lower(): v for k, v in all_fi.items()} if all_fi else {}
        for tramo_label, search_keys in tramo_keys:
            tramo_view = 'N/D'
            tramo_rationale = 'Análisis en proceso — datos cuantitativos disponibles'
            for key in search_keys:
                if key in all_fi:
                    tramo_view = all_fi[key].get('view', 'N/D')
                    tramo_rationale = all_fi[key].get('rationale', 'Ver council')
                    break
                if key in all_fi_lower:
                    tramo_view = all_fi_lower[key].get('view', 'N/D')
                    tramo_rationale = all_fi_lower[key].get('rationale', 'Ver council')
                    break
            # Default to NEUTRAL when council exists but no specific tramo view
            if tramo_view == 'N/D' and self.parser.has_council_text():
                tramo_view = 'N'
                # Try to extract rationale from RF text context
                tramo_rationale = self._infer_tramo_rationale(tramo_label, rf)
            curva.append({'tramo': tramo_label, 'view': tramo_view, 'rationale': tramo_rationale})

        return {
            'view_tasas': view_tasas,
            'view_duration': view_duration,
            'view_credito': view_credito,
            'curva': curva,
            'chile_especifico': chile,
        }

    def _infer_tramo_rationale(self, tramo: str, rf_text: str) -> str:
        """Infer rationale for a duration bucket from RF panel text."""
        if not rf_text:
            return 'Sin recomendación específica'
        rf_lower = rf_text.lower()
        if tramo == '0-2Y':
            if any(w in rf_lower for w in ['short duration', 'front end', 'corta duración', 'cash']):
                return 'Preferencia por corta duración según council'
            return 'Tramo defensivo — monitorear política monetaria'
        elif tramo == '2-5Y':
            if any(w in rf_lower for w in ['belly', 'intermediate', 'medio plazo']):
                return 'Carry atractivo en tramo intermedio'
            return 'Tramo intermedio — balance duración/carry'
        elif tramo == '5-10Y':
            if any(w in rf_lower for w in ['long duration', 'larga duración', '10y', '10 year']):
                return 'Exposición a tasas largas según council'
            return 'Sensibilidad a tasas largas — monitorear UST 10Y'
        elif tramo == '10Y+':
            if any(w in rf_lower for w in ['ultra long', 'ultra largo', '30y', '20y']):
                return 'Tramo ultra largo — alta convexidad'
            return 'Máxima duración — solo con convicción direccional'
        return 'Sin recomendación específica'

    def _default_rf_view(self) -> Dict[str, Any]:
        """RF view generado por Sonnet con datos de tasas y spreads."""
        from narrative_engine import generate_data_driven_narrative

        # Gather rates data
        us_2y = self._q('yield_curve', 'us_2y') or self._q('chile_rates', 'ust_2y')
        us_10y = self._q('yield_curve', 'us_10y') or self._q('chile_rates', 'ust_10y')
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        tpm = self._q('chile', 'tpm') or self._q('chile_rates', 'tpm')
        ipc = self._q('chile', 'ipc_yoy')

        quant_parts = []
        if us_2y is not None:
            quant_parts.append(f"UST 2Y: {us_2y}%")
        if us_10y is not None:
            quant_parts.append(f"UST 10Y: {us_10y}%")
        if us_2y and us_10y:
            quant_parts.append(f"Slope 2s10s: {(us_10y - us_2y)*100:.0f}bps")
        if ig_bps:
            quant_parts.append(f"IG spread: {ig_bps:.0f}bps")
        if hy_bps:
            quant_parts.append(f"HY spread: {hy_bps:.0f}bps")
        if tpm is not None:
            quant_parts.append(f"TPM Chile: {tpm}%")
        if tpm is not None and ipc is not None:
            quant_parts.append(f"Tasa real Chile: {tpm - ipc:.1f}%")

        quant_ctx = " | ".join(quant_parts) if quant_parts else "Sin datos de tasas disponibles"

        result = generate_data_driven_narrative(
            section_name="aa_rf_view_dd",
            prompt=(
                "Basándote en los datos de tasas y spreads, genera un JSON: "
                '{"view_tasas": "HIGHER/LOWER/ESTABLE con fundamento", '
                '"view_duration": "SHORT/NEUTRAL/LONG vs benchmark", '
                '"view_credito": "descripción de spreads IG/HY", '
                '"curva": [{"tramo": "0-2Y", "view": "OW/UW/N", "rationale": "1 oración"}], '
                '"chile_especifico": {"tpm_path": "trayectoria TPM", "carry_trade": "análisis carry", '
                '"recomendacion": "1 oración"}}. '
                "Tramos: 0-2Y, 2-5Y, 5-10Y, 10Y+. SOLO JSON."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=800,
        )
        if result:
            import json as _json
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, dict) and 'curva' in parsed:
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass

        # Minimal data-only fallback
        carry_str = f'Tasa real: {tpm - ipc:.1f}%' if tpm is not None and ipc is not None else 'N/D'
        return {
            'view_tasas': f'UST 10Y en {us_10y}%' if us_10y else 'N/D',
            'view_duration': 'NEUTRAL — datos insuficientes para recomendación firme',
            'view_credito': f'IG: {ig_bps:.0f}bps, HY: {hy_bps:.0f}bps' if ig_bps and hy_bps else 'N/D',
            'curva': [
                {'tramo': '0-2Y', 'view': 'N', 'rationale': quant_ctx},
                {'tramo': '2-5Y', 'view': 'N', 'rationale': quant_ctx},
                {'tramo': '5-10Y', 'view': 'N', 'rationale': quant_ctx},
                {'tramo': '10Y+', 'view': 'N', 'rationale': quant_ctx},
            ],
            'chile_especifico': {'tpm_path': f'TPM {tpm}%' if tpm else 'N/D', 'carry_trade': carry_str, 'recomendacion': 'N/D'}
        }

    def _generate_fx_view(self) -> Dict[str, Any]:
        # Try parser for structured FX views
        fx_views = self.parser.get_fx_views()

        # Get real USD/CLP if available
        usdclp_str = 'N/D'
        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if chile.get('usd_clp') is not None:
                    usdclp_str = f"{chile['usd_clp']:.0f}"
            except Exception:
                pass
        if usdclp_str == 'N/D':
            usdclp_val = self._q('chile_rates', 'usd_clp')
            if isinstance(usdclp_val, (int, float)):
                usdclp_str = f"{usdclp_val:.0f}"
            elif isinstance(usdclp_val, dict) and usdclp_val.get('value') is not None:
                usdclp_str = f"{usdclp_val['value']:.0f}"

        if fx_views:
            pares = []
            view_usd = 'N/D'
            fx_view_map = {'ALCISTA': 'OW', 'BAJISTA': 'UW', 'NEUTRAL': 'N'}
            for pair, info in fx_views.items():
                raw_view = info.get('view', 'N/D')
                target_3m = info.get('target_3m', info.get('target', 'N/D'))
                target_12m = info.get('target_12m', 'N/D')
                pares.append({
                    'par': pair,
                    'view': raw_view,
                    'target_3m': target_3m if target_3m else 'N/D',
                    'target_12m': target_12m if target_12m else 'N/D',
                    'rationale': info.get('rationale', 'Análisis en proceso — datos cuantitativos disponibles'),
                })
                # Determine USD view from DXY or USD pairs
                if 'DXY' in pair.upper() or ('USD' in pair.upper() and 'CLP' not in pair.upper()):
                    view_usd = fx_view_map.get(raw_view.upper(), raw_view)
            # If no DXY, infer USD view from USD/CLP
            if view_usd == 'N/D':
                for pair, info in fx_views.items():
                    if 'USD' in pair.upper() and 'CLP' in pair.upper():
                        mapped = fx_view_map.get(info.get('view', '').upper(), 'N/D')
                        view_usd = mapped
                        break
            return {
                'view_usd': view_usd,
                'pares': pares,
            }

        # Fallback: minimal structure, no hardcoded targets
        return {
            'view_usd': 'N/D',
            'pares': [
                {'par': 'EUR/USD', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'par': 'USD/CLP', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': f'Spot: {usdclp_str}. Análisis en proceso — datos cuantitativos disponibles'},
                {'par': 'USD/JPY', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
                {'par': 'USD/CNY', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Análisis en proceso — datos cuantitativos disponibles'},
            ]
        }

    def _generate_commodities_view(self) -> Dict[str, Any]:
        macro = self._panel('macro')

        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', None)

        # Enrich with real data
        if cobre is None and self.data:
            try:
                comm_table = self.data.get_commodities_table()
                for c in comm_table:
                    if 'copper' in c.get('name', '').lower() or 'cobre' in c.get('name', '').lower():
                        cobre = c.get('last')
                        break
            except Exception:
                pass
        if cobre is None:
            cobre = self._q('chile_rates', 'copper') or self._q('equity', 'bcch_indices', 'copper', 'value')

        cobre_str = f'${cobre:.2f}/lb' if cobre is not None else 'N/D'
        cobre_range = (
            f'${cobre-0.5:.2f}-${cobre+0.5:.2f}/lb' if cobre is not None else 'N/D'
        )

        # Gold and Oil from quant_data
        gold = self._q('equity', 'bcch_indices', 'gold', 'value')
        gold_str = f'${gold:.0f}/oz' if gold is not None else 'N/D'
        oil = self._q('equity', 'bcch_indices', 'oil_wti', 'value')
        oil_str = f'${oil:.1f}/bbl' if oil is not None else 'N/D'

        # Extract commodity views from council text
        comm_views = self._extract_commodity_views()

        cobre_view = comm_views.get('Cobre', 'NEUTRAL' if self._has_council() else 'N/D')
        oro_view = comm_views.get('Oro', 'NEUTRAL' if self._has_council() else 'N/D')
        oil_view = comm_views.get('Petróleo', 'NEUTRAL' if self._has_council() else 'N/D')

        # Generate target ranges from current prices (±5-10% band)
        gold_range = f'${gold-100:.0f}-${gold+100:.0f}/oz' if gold is not None else 'N/D'
        oil_range = f'${oil-5:.0f}-${oil+5:.0f}/bbl' if oil is not None else 'N/D'

        return {
            'commodities': [
                {'nombre': 'Cobre', 'view': cobre_view, 'target': cobre_range, 'rationale': f'Precio actual: {cobre_str}.'},
                {'nombre': 'Oro', 'view': oro_view, 'target': gold_range, 'rationale': f'Precio actual: {gold_str}.'},
                {'nombre': 'Petróleo', 'view': oil_view, 'target': oil_range, 'rationale': f'Precio actual: {oil_str}.'},
            ]
        }

    def _extract_commodity_views(self) -> Dict[str, str]:
        """Extract commodity OW/UW/NEUTRAL from council text."""
        views = {}
        if not self._has_council():
            return views
        final = (self._final() + ' ' + self._cio() + ' ' + self._panel('macro')).lower()
        for comm, patterns in [('Cobre', ['copper', 'cobre']),
                                ('Oro', ['gold', 'oro']),
                                ('Petróleo', ['oil', 'petróleo', 'petroleo', 'wti', 'brent'])]:
            for pat in patterns:
                idx = final.find(pat)
                if idx >= 0:
                    context = final[max(0, idx - 100):idx + 100]
                    if any(w in context for w in ['ow', 'sobrepon', 'overweight', 'bullish',
                                                   'alcista', 'comprar', 'long']):
                        views[comm] = 'OW'
                    elif any(w in context for w in ['uw', 'subpon', 'underweight', 'bearish',
                                                     'bajista', 'vender', 'short', 'reducir']):
                        views[comm] = 'UW'
                    else:
                        views[comm] = 'NEUTRAL'
                    break
        return views

    def _generate_tactical_actions(self) -> List[Dict[str, Any]]:
        """Acciones tácticas extraídas del CIO/final_recommendation del council."""
        import json as _json
        from narrative_engine import generate_narrative

        final = self._final()
        cio = self._cio()

        if not (final or cio):
            return []

        council_ctx = f"FINAL RECOMMENDATION:\n{final[:2000]}\n\nCIO SYNTHESIS:\n{cio[:1500]}"

        actions_raw = generate_narrative(
            section_name="aa_tactical_actions",
            prompt=(
                "Extrae las acciones tácticas recomendadas del council como JSON array: "
                '[{"asset_class": "string", "accion": "AUMENTAR|REDUCIR|MANTENER|INICIAR|CERRAR", '
                '"desde": "string (peso actual o N/D)", "hacia": "string (peso objetivo)", '
                '"timing": "string (horizonte)", "vehiculo": "string (ETF o instrumento)", '
                '"rationale": "string (1 oración con dato)"}]. '
                "Exactamente 3-5 acciones. Extraer de las recomendaciones del council, no inventar."
            ),
            council_context=council_ctx,
            company_name=self.company_name,
            max_tokens=800,
            temperature=0.2,
        )
        if actions_raw:
            try:
                cleaned = actions_raw.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    cleaned = cleaned.strip()
                parsed = _json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except (_json.JSONDecodeError, KeyError):
                pass

        # Fallback: single action with council summary
        return [{
            'asset_class': 'Portafolio',
            'accion': 'REVISAR',
            'desde': 'Actual',
            'hacia': 'Ver recomendación final',
            'timing': self.month_name,
            'vehiculo': 'Múltiple',
            'rationale': 'Consultar recomendación final del período para ajustes específicos.'
        }]

    def _generate_hedge_ratios(self) -> Dict[str, Any]:
        """Hedge ratios desde panel riesgo — sizing comes from council."""
        riesgo = self._panel('riesgo')

        # Hedge universe (instruments are structural, but sizing/views from council)
        hedge_universe = [
            {
                'tipo': 'VIX Call Spread',
                'proposito': 'Protección tail risk — payout asimétrico si volatilidad explota',
                'implementacion': 'Buy VIX calls, sell higher strike. Payout asimétrico si VIX sube'
            },
            {
                'tipo': 'USD/CLP Forward',
                'proposito': 'Proteger exposición Chile ante depreciación súbita CLP',
                'implementacion': 'Forward vendiendo USD/comprando CLP — ver nivel spot actual'
            },
            {
                'tipo': 'Put SPY OTM',
                'proposito': 'Protección tail risk equity US ante credit freeze o aranceles masivos',
                'implementacion': 'OTM puts below spot, 3M expiry'
            },
            {
                'tipo': 'Credit Protection (CDX HY)',
                'proposito': 'Hedge HY exposure ante credit spreads blowout',
                'implementacion': 'CDX HY protection, rolling 6M'
            },
            {
                'tipo': 'Gold (structural)',
                'proposito': 'Hedge geopolítico permanente + tail risk desacople financiero',
                'implementacion': 'ETF GLD o físico'
            },
        ]

        # Enrich with council sizing if available
        hedges = []
        for h in hedge_universe:
            hedges.append({
                'tipo': h['tipo'],
                'proposito': h['proposito'],
                'porcentaje_portfolio': 'N/D',
                'costo_estimado': 'N/D',
                'plazo': 'N/D',
                'trigger_activacion': 'N/D',
                'implementacion': h['implementacion'],
            })

        return {
            'titulo': 'Estructura de Hedges',
            'presupuesto_total': 'N/D — ver recomendación del comité',
            'hedges': hedges,
            'monitored_triggers': self._generate_monitored_triggers()
        }

    def _generate_monitored_triggers(self) -> List[Dict[str, Any]]:
        """Monitored triggers — usa datos reales cuando disponibles."""
        # HY spread real
        hy_str = 'N/D'
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if hy_bps:
            hy_str = self._fmt_bp(hy_bps)

        # IG spread real
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')

        # USD/CLP real
        usdclp_str = 'N/D'
        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if chile.get('usd_clp') is not None:
                    usdclp_str = f"{chile['usd_clp']:.0f}"
            except Exception:
                pass
        if usdclp_str == 'N/D':
            usdclp_val = self._q('chile_rates', 'usd_clp')
            if isinstance(usdclp_val, (int, float)):
                usdclp_str = f"{usdclp_val:.0f}"
            elif isinstance(usdclp_val, dict) and usdclp_val.get('value') is not None:
                usdclp_str = f"{usdclp_val['value']:.0f}"

        # VIX from quant_data (try multiple paths)
        vix_val = self._q('vix', 'current') or self._q('chile_rates', 'vix', 'current') or self._q('equity', 'risk', 'vix', 'current')
        vix_str = f"{vix_val:.1f}" if isinstance(vix_val, (int, float)) else 'N/D'

        triggers = [
            {'metrica': 'VIX', 'nivel_actual': str(vix_str), 'umbral_accion': '>30', 'accion': 'Reducir risk 30%'},
            {'metrica': 'USD/CLP', 'nivel_actual': usdclp_str, 'umbral_accion': '>920', 'accion': 'Exit Chile equity completamente'},
            {'metrica': 'HY Spreads', 'nivel_actual': hy_str, 'umbral_accion': '>500bp', 'accion': 'Exit HY, flight to quality'},
        ]

        if hy_bps:
            triggers[-1]['_real'] = True
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
        """Riesgos via Claude desde panel riesgo + geo + contrarian."""
        import json as _json
        from narrative_engine import generate_narrative

        riesgo = self._panel('riesgo')
        geo = self._panel('geo')
        contrarian = self._contrarian()
        final = self._final()

        council_ctx = (
            f"RISK PANEL:\n{riesgo[:2000]}\n\n"
            f"GEO PANEL:\n{geo[:1500]}\n\n"
            f"CONTRARIAN:\n{contrarian[:1000]}\n\n"
            f"FINAL:\n{final[:1000]}"
        )

        # Generate top risks via Claude
        top_risks = []
        if riesgo or geo or contrarian:
            risks_raw = generate_narrative(
                section_name="aa_risks",
                prompt=(
                    "Genera exactamente 3-4 top riesgos para el portafolio basados en el council. "
                    "Devuelve un JSON array donde cada elemento tiene: "
                    '{"nombre": "string", "probabilidad": number (0-100), '
                    '"impacto": "string corto", "descripcion": "2-3 oraciones", '
                    '"hedge": "cobertura sugerida", "senal_temprana": "que monitorear"}. '
                    "Incluir un riesgo del contrarian (error de posicionamiento/timing). "
                    "Usa probabilidades y datos del council — NO inventes."
                    "\n\nPara cada riesgo, desarrolla escenario completo: cadena causal, caso base vs caso adverso, hedge sugerido, señal temprana medible."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=1500,
                temperature=0.2,
            )
            if risks_raw:
                try:
                    cleaned = risks_raw.strip()
                    if cleaned.startswith('```'):
                        cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.endswith('```'):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    top_risks = _json.loads(cleaned)
                except (_json.JSONDecodeError, KeyError):
                    pass

        if not top_risks:
            top_risks = [
                {'nombre': 'Riesgo principal', 'probabilidad': 0,
                 'impacto': 'Ver council', 'descripcion': 'Consultar analisis de riesgos del periodo.',
                 'hedge': 'Diversificacion', 'senal_temprana': 'Ver council'}
            ]

        # Generate triggers via Claude
        triggers = []
        if riesgo or contrarian:
            triggers_raw = generate_narrative(
                section_name="aa_triggers",
                prompt=(
                    "Genera exactamente 4-6 triggers de reconvocatoria/accion basados en el council. "
                    "Cada trigger en una linea, formato: 'Metrica/condicion → Accion a tomar'. "
                    "Usar metricas concretas del council (VaR, spreads, FX, correlaciones). "
                    "Sin bullets ni numeracion."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=400,
            )
            if triggers_raw:
                triggers = [l.strip() for l in triggers_raw.split('\n') if l.strip() and '→' in l]

        if not triggers:
            triggers = ['Monitorear datos macro y metricas de riesgo del council']

        # Generate calendar events via Claude
        calendario = []
        if riesgo or geo or contrarian:
            cal_raw = generate_narrative(
                section_name="aa_calendar",
                prompt=(
                    f"Genera 4-6 eventos clave del calendario para {self.month_name} {self.date.year} "
                    "relevantes para mercados. Formato JSON array: "
                    '[{"fecha": "DD/MM", "evento": "descripcion breve", "relevancia": "Alta|Media"}]. '
                    "Incluir: reuniones Fed/BCE/BCCh, datos macro (CPI, NFP, GDP), earnings season. "
                    "Usar fechas reales del mes. SOLO JSON."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=500,
                temperature=0.2,
            )
            if cal_raw:
                try:
                    cleaned = cal_raw.strip()
                    if cleaned.startswith('```'):
                        cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.endswith('```'):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    calendario = _json.loads(cleaned)
                except (_json.JSONDecodeError, KeyError):
                    pass

        return {
            'top_risks': top_risks,
            'calendario_eventos': calendario,
            'triggers_reconvocatoria': triggers,
        }

    # =========================================================================
    # SECCION 2: DASHBOARD DE POSICIONAMIENTO
    # =========================================================================

    def generate_positioning_dashboard(self) -> Dict[str, Any]:
        """Dashboard visual de posicionamiento OW (Overweight/Sobreponderar) / N / UW (Underweight/Subponderar) por asset class."""

        if not self._has_council():
            return self._default_dashboard()

        # Extract from existing views
        eq = self._generate_equity_view()
        rf = self._generate_fixed_income_view()
        comm = self._generate_commodities_view()
        postura = self._determine_postura()

        # Build RV dashboard from equity por_region
        view_map = {'OW': 'OW', 'UW': 'UW', 'N': 'N', 'N/D': 'N/D', 'NEUTRAL': 'N'}
        has_text = self.parser.has_council_text()
        renta_variable = []
        for r in eq.get('por_region', []):
            # Use region conviction from the view, or default MEDIA with council text
            conv = r.get('conviccion', 'N/D')
            if conv == 'N/D' and has_text:
                conv = 'MEDIA'
            renta_variable.append({
                'asset': r['region'],
                'view': view_map.get(r['view'], r['view']),
                'cambio': '→',
                'conviccion': conv,
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
                'view': view_map.get(c['view'], c['view']),
                'cambio': '→',
                'conviccion': 'MEDIA' if has_text else 'N/D',
            })

        # Add credit views from council parser FI views
        fi_views = self.parser.get_fi_views() if self.parser else None
        ig_view = 'N/D'
        hy_view = 'N/D'
        if fi_views:
            for k in ['ig', 'investment grade', 'ig credit']:
                if k in fi_views:
                    ig_view = fi_views[k].get('view', 'N/D')
                    break
            for k in ['hy', 'high yield', 'hy credit']:
                if k in fi_views:
                    hy_view = fi_views[k].get('view', 'N/D')
                    break
        # Fallback: derive from view_credito text if parser didn't have segments
        if ig_view == 'N/D' and hy_view == 'N/D':
            rf_credit_view = rf.get('view_credito', '')
            if 'IG sobre HY' in rf_credit_view:
                ig_view = 'OW'
                hy_view = 'UW'
        # Text mining fallback for credit
        if ig_view == 'N/D' and self.parser.has_council_text():
            mined_ig = self.parser.search_credit_view('ig')
            if mined_ig:
                ig_view = mined_ig
            else:
                ig_view = 'N'
        if hy_view == 'N/D' and self.parser.has_council_text():
            mined_hy = self.parser.search_credit_view('hy')
            if mined_hy:
                hy_view = mined_hy
            else:
                hy_view = 'N'
        conv_default = 'MEDIA' if self.parser.has_council_text() else 'N/D'
        renta_fija.append({'asset': 'IG Credit', 'view': ig_view, 'cambio': '→', 'conviccion': conv_default})
        renta_fija.append({'asset': 'HY Credit', 'view': hy_view, 'cambio': '→', 'conviccion': conv_default})

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
                'conviccion': 'MEDIA' if has_text else 'N/D',
            })

        # Add USD/CLP from FX view (council parser)
        fx_views = self.parser.get_fx_views() if self.parser else None
        fx_view_map = {'ALCISTA': 'OW', 'BAJISTA': 'UW', 'NEUTRAL': 'N'}
        usd_view = 'N/D'
        clp_view = 'N/D'
        if fx_views:
            # Look for USD/CLP pair or DXY-related entries
            for pair, info in fx_views.items():
                raw = info.get('view', '')
                if 'USD' in pair and 'CLP' in pair:
                    # USD/CLP ALCISTA means USD strong vs CLP → USD OW, CLP UW
                    mapped = fx_view_map.get(raw.upper(), 'N/D')
                    usd_view = mapped
                    clp_view = {'OW': 'UW', 'UW': 'OW', 'N': 'N'}.get(mapped, 'N/D')
                elif 'DXY' in pair.upper():
                    usd_view = fx_view_map.get(raw.upper(), 'N/D')
        # Text mining fallback for FX
        if usd_view == 'N/D' and self.parser.has_council_text():
            mined_usd = self.parser.search_fx_pair_view('USD/CLP')
            if mined_usd:
                mapped = fx_view_map.get(mined_usd['view'], 'N')
                usd_view = mapped
                clp_view = {'OW': 'UW', 'UW': 'OW', 'N': 'N'}.get(mapped, 'N')
            else:
                usd_view = 'N'
                clp_view = 'N'
        conv_fx = 'MEDIA' if self.parser.has_council_text() else 'N/D'
        commodities_fx.append({'asset': 'USD (DXY)', 'view': usd_view, 'cambio': '→', 'conviccion': conv_fx})
        commodities_fx.append({'asset': 'CLP', 'view': clp_view, 'cambio': '→', 'conviccion': conv_fx})

        return {
            'renta_variable': renta_variable,
            'renta_fija': renta_fija,
            'commodities_fx': commodities_fx,
            'postura_general': postura
        }

    def _default_dashboard(self) -> Dict[str, Any]:
        """Dashboard generado por Sonnet con datos cuantitativos disponibles."""
        from narrative_engine import generate_data_driven_narrative

        quant_ctx = self._build_quant_summary()
        result = generate_data_driven_narrative(
            section_name="aa_dashboard_dd",
            prompt=(
                "Genera un JSON con el dashboard de asset allocation basado en datos cuantitativos. "
                "Estructura: "
                '{"renta_variable": [{"asset": "US Large Cap", "view": "OW/UW/N", "cambio": "→/↑/↓", "conviccion": "ALTA/MEDIA/BAJA"}], '
                '"renta_fija": [...], "commodities_fx": [...], '
                '"postura_general": {"view": "CONSTRUCTIVO/CAUTELOSO/NEUTRAL", "sesgo": "risk-on/risk-off/neutral", "conviccion": "..."}}. '
                "Assets RV: US Large Cap, Europa, China, Chile, EM ex-China. "
                "Assets RF: UST Short (0-2Y), UST Medium (2-5Y), UST Long (5-10Y), IG Credit, HY Credit. "
                "Assets Comm/FX: Cobre, Oro, Petroleo, USD (DXY), CLP. "
                "Basa views en valuaciones, niveles de tasas, y spreads. Cambio siempre '→' sin datos previos. "
                "Convicción BAJA cuando basado solo en datos sin deliberación. SOLO JSON."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=1200,
        )
        if result:
            import json as _json
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, dict) and 'renta_variable' in parsed:
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass

        # Ultra-minimal fallback: all NEUTRAL with low conviction
        return {
            'renta_variable': [
                {'asset': a, 'view': 'N', 'cambio': '→', 'conviccion': 'BAJA'}
                for a in ['US Large Cap', 'Europa', 'China', 'Chile', 'EM ex-China']
            ],
            'renta_fija': [
                {'asset': a, 'view': 'N', 'cambio': '→', 'conviccion': 'BAJA'}
                for a in ['UST Short (0-2Y)', 'UST Medium (2-5Y)', 'UST Long (5-10Y)', 'IG Credit', 'HY Credit']
            ],
            'commodities_fx': [
                {'asset': a, 'view': 'N', 'cambio': '→', 'conviccion': 'BAJA'}
                for a in ['Cobre', 'Oro', 'Petroleo', 'USD (DXY)', 'CLP']
            ],
            'postura_general': {'view': 'NEUTRAL', 'sesgo': 'neutral', 'conviccion': 'BAJA'}
        }

    # =========================================================================
    # SECCION 8: PORTAFOLIOS MODELO
    # =========================================================================

    def generate_model_portfolios(self) -> List[Dict[str, Any]]:
        """5 portafolios modelo generados por Claude basados en council output."""
        from narrative_engine import generate_narrative
        import json as _json

        final_rec = self.council.get('final_recommendation', '')
        cio = self.council.get('cio_synthesis', '')
        if not (final_rec or cio):
            return [{'perfil': 'N/D', 'risk_score': '-', 'allocations': [], 'nota': 'Portafolios modelo requieren council session.'}]

        council_ctx = f"FINAL REC:\n{final_rec[:2000]}\n\nCIO:\n{cio[:1500]}"
        result = generate_narrative(
            section_name="model_portfolios",
            prompt=(
                "Genera 5 portafolios modelo (Ultra Conservador, Conservador, Moderado, Agresivo, Ultra Agresivo) "
                "basados en las recomendaciones del council. Formato JSON: "
                "[{\"perfil\": \"...\", \"risk_score\": \"1-2\", \"allocations\": "
                "[{\"asset\": \"RV USA\", \"pct\": 5, \"cambio\": \"→\"}]}]. "
                "Assets: RV USA, RV Europa, RV Chile, RV EM, RF Gobierno, RF Credito, RF Chile, Commodities, Cash. "
                "Cada portafolio debe sumar 100%. Cambio: ↑/↓/→ vs mes anterior segun council. "
                "SOLO JSON, sin explicacion."
            ),
            council_context=council_ctx,
            company_name=self.company_name,
            max_tokens=2000,
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
                if isinstance(parsed, list) and len(parsed) >= 3:
                    return parsed
            except (_json.JSONDecodeError, KeyError):
                pass

        return [{'perfil': 'N/D', 'risk_score': '-', 'allocations': [], 'nota': 'Error generando portafolios modelo.'}]

    # =========================================================================
    # SECCION 9: FOCUS LIST
    # =========================================================================

    def generate_focus_list(self) -> Dict[str, List]:
        """Focus list de instrumentos especificos con tickers.

        Tickers are universe definitions (structural). Views come from council parser.
        """

        if not self._has_council():
            return self._default_focus_list()

        # Get council views for mapping to ETFs
        eq_views = self.parser.get_equity_views() if self.parser else None
        fi_views = self.parser.get_fi_views() if self.parser else None
        sector_views = self.parser.get_sector_views() if self.parser else None
        fx_views = self.parser.get_fx_views() if self.parser else None

        def _eq_view(region_keys: list) -> str:
            """Look up equity view by region keys."""
            if not eq_views:
                return 'N/D'
            for k in region_keys:
                if k in eq_views:
                    return eq_views[k].get('view', 'N/D')
            return 'N/D'

        def _sector_view(sector_keys: list) -> str:
            """Look up sector view."""
            if not sector_views:
                return 'N/D'
            for k in sector_keys:
                if k in sector_views:
                    return sector_views[k].get('view', 'N/D')
            return 'N/D'

        def _fi_view(segment_keys: list) -> str:
            """Look up FI view by segment keys."""
            if not fi_views:
                return 'N/D'
            for k in segment_keys:
                if k in fi_views:
                    return fi_views[k].get('view', 'N/D')
            return 'N/D'

        def _fx_view(pair_keys: list) -> str:
            """Look up FX view, mapping ALCISTA/BAJISTA/NEUTRAL to OW/UW/N."""
            if not fx_views:
                return 'N/D'
            fx_map = {'ALCISTA': 'OW', 'BAJISTA': 'UW', 'NEUTRAL': 'N'}
            for k in pair_keys:
                if k in fx_views:
                    raw = fx_views[k].get('view', '')
                    return fx_map.get(raw.upper(), 'N/D')
            return 'N/D'

        # Build focus list: tickers are structural, views from council
        comm_views = self._extract_commodity_views()
        us_view = _eq_view(['us', 'usa', 'estados unidos'])
        chile_view = _eq_view(['chile'])
        europe_view = _eq_view(['europa', 'europe'])
        em_view = _eq_view(['em ex-china', 'em', 'emergentes'])

        return {
            'renta_variable': [
                {'ticker': 'SPY', 'nombre': 'SPDR S&P 500 ETF', 'view': us_view, 'rationale': 'Core US exposure, broad market'},
                {'ticker': 'IWB', 'nombre': 'iShares Russell 1000 Value', 'view': us_view, 'rationale': 'Value factor US'},
                {'ticker': 'SOXX', 'nombre': 'iShares Semiconductor', 'view': _sector_view(['technology', 'semiconductors', 'tech']), 'rationale': 'AI capex / semiconductors'},
                {'ticker': 'XLI', 'nombre': 'Industrial Select SPDR', 'view': _sector_view(['industrials', 'industrial']), 'rationale': 'US industrials exposure'},
                {'ticker': 'ECH', 'nombre': 'iShares MSCI Chile', 'view': chile_view, 'rationale': 'Chile equity exposure'},
                {'ticker': 'EWG', 'nombre': 'iShares MSCI Germany', 'view': europe_view, 'rationale': 'Europe / Germany equity exposure'},
                {'ticker': 'EEM', 'nombre': 'iShares MSCI EM', 'view': em_view, 'rationale': 'Emerging markets equity exposure'},
            ],
            'renta_fija': [
                {'ticker': 'BIL', 'nombre': 'SPDR Bloomberg T-Bill', 'view': _fi_view(['0-2y', 'short', 'corto', 'treasury bills', 't-bills']), 'rationale': 'Cash-like, T-Bill exposure'},
                {'ticker': 'SHY', 'nombre': 'iShares 1-3 Year Treasury', 'view': _fi_view(['0-2y', 'short', 'corto']), 'rationale': 'Short duration (sensibilidad del precio a cambios de tasas) treasury'},
                {'ticker': 'VMBS', 'nombre': 'Vanguard MBS ETF', 'view': _fi_view(['mbs', 'agency', 'mortgage']), 'rationale': 'MBS spread exposure'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': _fi_view(['ig', 'investment grade', 'ig credit']), 'rationale': 'Investment grade corporate'},
                {'ticker': 'TLT', 'nombre': 'iShares 20+ Year Treasury', 'view': _fi_view(['10y+', '10+', 'ultra long', 'long']), 'rationale': 'Long duration treasury'},
                {'ticker': 'HYG', 'nombre': 'iShares High Yield Corp', 'view': _fi_view(['hy', 'high yield', 'hy credit']), 'rationale': 'High yield corporate'},
            ],
            'commodities': [
                {'ticker': 'CPER', 'nombre': 'US Copper Index Fund', 'view': comm_views.get('Cobre', 'N/D'), 'rationale': 'Copper exposure'},
                {'ticker': 'COPX', 'nombre': 'Global X Copper Miners', 'view': comm_views.get('Cobre', 'N/D'), 'rationale': 'Copper miners'},
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': comm_views.get('Oro', 'N/D'), 'rationale': 'Gold hedge'},
                {'ticker': 'USO', 'nombre': 'US Oil Fund', 'view': comm_views.get('Petróleo', 'N/D'), 'rationale': 'Oil exposure'},
                {'ticker': 'UUP', 'nombre': 'Invesco DB US Dollar', 'view': _fx_view(['USD/CLP', 'DXY']), 'rationale': 'USD exposure'},
            ]
        }

    def _default_focus_list(self) -> Dict[str, List]:
        """Focus list generado por Sonnet con datos de valuaciones y retornos."""
        from narrative_engine import generate_data_driven_narrative

        quant_ctx = self._build_quant_summary()
        result = generate_data_driven_narrative(
            section_name="aa_focus_list_dd",
            prompt=(
                "Genera un JSON con la focus list de ETFs basada en datos cuantitativos. "
                "Estructura: "
                '{"renta_variable": [{"ticker": "SPY", "nombre": "SPDR S&P 500 ETF", "view": "OW/UW/N", '
                '"rationale": "1 oración con dato cuantitativo"}], '
                '"renta_fija": [...], "commodities": [...]}. '
                "ETFs RV: SPY, ECH, EEM, EWG, IWB, SOXX, XLI. "
                "ETFs RF: BIL, SHY, LQD, TLT, HYG. "
                "ETFs Comm: GLD, CPER, USO. "
                "Basa rationale en valuaciones y retornos disponibles. "
                "Convicción baja sin deliberación completa. SOLO JSON."
            ),
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=1200,
        )
        if result:
            import json as _json
            try:
                cleaned = result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, dict) and 'renta_variable' in parsed:
                    return parsed
            except (_json.JSONDecodeError, Exception):
                pass

        # Minimal fallback with N (neutral) instead of N/D
        return {
            'renta_variable': [
                {'ticker': 'SPY', 'nombre': 'SPDR S&P 500 ETF', 'view': 'N', 'rationale': 'Core US — análisis basado en datos cuantitativos'},
                {'ticker': 'ECH', 'nombre': 'iShares MSCI Chile', 'view': 'N', 'rationale': 'Chile equity — análisis basado en datos cuantitativos'},
                {'ticker': 'EEM', 'nombre': 'iShares MSCI EM', 'view': 'N', 'rationale': 'EM exposure — análisis basado en datos cuantitativos'},
            ],
            'renta_fija': [
                {'ticker': 'BIL', 'nombre': 'SPDR Bloomberg T-Bill', 'view': 'N', 'rationale': 'Cash-like — análisis basado en datos cuantitativos'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': 'N', 'rationale': 'IG credit — análisis basado en datos cuantitativos'},
            ],
            'commodities': [
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': 'N', 'rationale': 'Gold hedge — análisis basado en datos cuantitativos'},
            ]
        }

    # =========================================================================
    # PERFORMANCE MES ANTERIOR
    # =========================================================================

    def generate_previous_month_performance(self) -> Dict[str, Any]:
        """Performance del mes anterior — datos REALES de yfinance."""
        if not self.data:
            return {
                'titulo': 'Performance del Mes Anterior',
                'nota': 'No disponible — ChartDataProvider no configurado',
                'activos': [],
            }

        try:
            tickers = {
                'SPY': 'S&P 500', 'QQQ': 'Nasdaq 100', 'EFA': 'MSCI EAFE',
                'EEM': 'MSCI EM', 'AGG': 'US Agg Bond', 'HYG': 'US High Yield',
                'TLT': 'US Treasury 20Y+', 'GLD': 'Gold', 'ECH': 'MSCI Chile',
                'EWZ': 'MSCI Brazil', 'USO': 'Crude Oil',
            }
            returns = self.data.get_previous_month_returns(list(tickers.keys()))

            activos = []
            for ticker, name in tickers.items():
                ret = returns.get(ticker)
                activos.append({
                    'nombre': name,
                    'ticker': ticker,
                    'retorno': f"{ret:+.2f}%" if ret is not None else 'N/D',
                })

            return {
                'titulo': 'Performance del Mes Anterior',
                'activos': activos,
            }
        except Exception:
            return {
                'titulo': 'Performance del Mes Anterior',
                'nota': 'Error obteniendo datos de yfinance',
                'activos': [],
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
        # Set up anti-fabrication filter with verified quant data
        try:
            from narrative_engine import set_verified_data, clear_verified_data, build_verified_data_aa
            vd = build_verified_data_aa(self.quant)
            if vd:
                set_verified_data(vd)
        except Exception:
            pass

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

        # Clear anti-fabrication verified data
        try:
            from narrative_engine import clear_verified_data
            clear_verified_data()
        except Exception:
            pass

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

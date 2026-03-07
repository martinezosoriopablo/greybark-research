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
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=800,
            )
            if result:
                return result

        return self._default_intro(postura)

    def _default_intro(self, postura: Dict) -> str:
        """Intro por defecto sin council."""
        name = self.company_name or "Nosotros"
        return (
            f"El mes de {self.month_name} presenta un entorno de mercado con señales mixtas. "
            f"{name} adopta una postura {postura['view']} con sesgo {postura['sesgo']}. "
            f"Mantenemos coberturas activas ante la incertidumbre en política monetaria global."
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
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=500,
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
        if self.data:
            try:
                usa = self.data.get_usa_latest()
                if gdp is None and usa.get('gdp_saar') is not None:
                    gdp = usa['gdp_saar']
                if cpi is None and usa.get('cpi_core') is not None:
                    cpi = usa['cpi_core']
            except Exception:
                pass

        # Also try quant_data
        if gdp is None:
            gdp = self._q('macro_usa', 'gdp')
        if cpi is None:
            cpi = self._q('macro_usa', 'core_cpi')

        gdp_str = f'{gdp}%' if gdp is not None else 'N/D'
        cpi_str = f'{cpi}%' if cpi is not None else 'N/D'
        retail_str = f'+{retail}%' if retail is not None else 'N/D'
        recession_str = f'{int(recession)}%' if recession is not None else 'N/D'

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

        datos = [
            {'indicador': 'GDP US QoQ', 'actual': gdp_str, 'anterior': 'N/D', 'sorpresa': 'Ver council'},
            {'indicador': 'Core CPI YoY', 'actual': cpi_str, 'anterior': 'N/D', 'sorpresa': 'Ver council'},
            {'indicador': 'Retail Sales YoY', 'actual': retail_str, 'anterior': 'N/D', 'sorpresa': 'Ver council'},
            {'indicador': 'Prob. Recesión 12M', 'actual': recession_str, 'anterior': 'N/D', 'sorpresa': 'Ver council'},
        ]

        return {'titulo': 'Economía Global', 'narrativa': narrativa, 'datos': datos}

    def _default_economia_global(self) -> Dict[str, Any]:
        # Try to get at least CPI from real data
        cpi_str = 'N/D'
        if self.data:
            try:
                usa = self.data.get_usa_latest()
                if usa.get('cpi_core') is not None:
                    cpi_str = f"{usa['cpi_core']}%"
            except Exception:
                pass
        if cpi_str == 'N/D':
            cpi_str = self._fmt_pct(self._q('macro_usa', 'core_cpi'))

        return {
            'titulo': 'Economía Global',
            'narrativa': 'Los datos macroeconómicos muestran señales mixtas. Sin datos del council para mayor detalle.',
            'datos': [
                {'indicador': 'US Core CPI', 'actual': cpi_str, 'anterior': 'N/D', 'sorpresa': 'N/D'},
            ]
        }

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

        return {'titulo': 'Mercados Financieros', 'narrativa': narrativa, 'performance': []}

    def _default_mercados(self) -> Dict[str, Any]:
        performance = []
        if self.data:
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
            except Exception:
                pass

        if not performance:
            performance = [
                {'asset': 'S&P 500', 'retorno': 'N/D', 'ytd': 'N/D'},
                {'asset': 'Nasdaq 100', 'retorno': 'N/D', 'ytd': 'N/D'},
            ]

        return {
            'titulo': 'Mercados Financieros',
            'narrativa': 'Sin datos del council para detalle de mercados.',
            'performance': performance
        }

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
        geo_risks = self.parser.get_geopolitical_risks()
        if geo_risks:
            eventos = [{'evento': r['event'], 'impacto': r['impact'], 'probabilidad': r['probability']}
                       for r in geo_risks]
        else:
            eventos = [
                {'evento': 'Sin evaluación del comité', 'probabilidad': 'N/D', 'impacto': 'N/D'},
            ]
        return {
            'titulo': 'Política y Geopolítica',
            'narrativa': 'El entorno geopolítico presenta riesgos elevados que requieren monitoreo activo.',
            'eventos': eventos,
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

        datos = [
            {'indicador': 'TPM', 'valor': tpm_str, 'tendencia': 'Ver council'},
            {'indicador': 'IPC YoY', 'valor': ipc_str, 'tendencia': 'Ver council'},
            {'indicador': 'Tasa Real', 'valor': tpm_real_str, 'tendencia': 'Ver council'},
            {'indicador': 'Cobre', 'valor': cobre_str, 'tendencia': 'Ver council'},
        ]

        return {'titulo': 'Chile y Economía Local', 'narrativa': narrativa, 'datos': datos}

    def _default_chile(self) -> Dict[str, Any]:
        tpm_str = 'N/D'
        ipc_str = 'N/D'
        if self.data:
            try:
                chile = self.data.get_chile_latest()
                if chile.get('tpm') is not None:
                    tpm_str = f"{chile['tpm']}%"
                if chile.get('ipc_yoy') is not None:
                    ipc_str = f"{chile['ipc_yoy']}%"
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

        return {
            'titulo': 'Chile y Economía Local',
            'narrativa': 'Chile mantiene estabilidad macroeconómica con política monetaria calibrada.',
            'datos': [
                {'indicador': 'TPM', 'valor': tpm_str, 'tendencia': 'Ver council'},
                {'indicador': 'IPC YoY', 'valor': ipc_str, 'tendencia': 'Ver council'},
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
            escenarios = []
            for key, info in scenarios_parsed.items():
                escenarios.append({
                    'nombre': info['name'],
                    'probabilidad': int(info['prob'] * 100),
                    'descripcion': f"Escenario del council: {info['name']}.",
                    'senales': [],
                    'implicancias': {},
                    'que_comprar': 'Ver recomendacion del comite',
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

        # If no council data at all, return empty
        if not contrarian and not riesgo:
            return {
                'escenario_base': 'SIN DATOS',
                'descripcion_base': 'Sin datos del council para definir escenarios',
                'escenarios': [],
            }

        # Build from extracted text data — no numeric literal fallbacks
        macro = self._panel('macro')
        gdp = self._extract_number(macro, r'GDP\s+(?:US\s+)?(\d+\.?\d*)%', None)
        gdp_str = f'{gdp}% QoQ' if gdp is not None else 'N/D'
        bull_str = f'{int(bull_prob)}%' if bull_prob is not None else 'N/D'
        tariff_str = f'{int(tariff_prob)}%' if tariff_prob is not None else 'N/D'
        china_str = f'{int(china_prob)}%' if china_prob is not None else 'N/D'

        return {
            'escenario_base': 'Ver council',
            'descripcion_base': 'Escenarios extraidos del council — verificar con datos del periodo',
            'escenarios': [
                {
                    'nombre': 'Expansion Tardia',
                    'probabilidad': 0,
                    'descripcion': f'GDP US en {gdp_str}. Ver council para detalle de este escenario.',
                    'senales': ['Ver council'],
                    'implicancias': {},
                    'que_comprar': 'Ver recomendacion del comite'
                },
                {
                    'nombre': 'Escenario Alcista',
                    'probabilidad': 0,
                    'descripcion': f'Probabilidad bull case: {bull_str} segun analisis contrarian.',
                    'senales': ['Ver council'],
                    'implicancias': {},
                    'que_comprar': 'Ver recomendacion del comite'
                },
                {
                    'nombre': 'Escenario de Riesgo Comercial',
                    'probabilidad': 0,
                    'descripcion': f'Probabilidad aranceles amplificados: {tariff_str}.',
                    'senales': ['Ver council'],
                    'implicancias': {},
                    'que_comprar': 'Ver recomendacion del comite'
                },
                {
                    'nombre': 'Recesion / Credito',
                    'probabilidad': 0,
                    'descripcion': f'China hard landing probabilidad: {china_str}.',
                    'senales': ['Ver council'],
                    'implicancias': {},
                    'que_comprar': 'Ver recomendacion del comite'
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
        """USA view via Claude desde panels rv + macro."""
        from narrative_engine import generate_narrative
        import json as _json

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
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=300,
        )
        if not tesis:
            tesis = f"Economia US en regimen de expansion. GDP en {gdp}% QoQ." if gdp else "Ver council."

        # Generate pros/cons via Claude
        args_raw = generate_narrative(
            section_name="aa_usa_args",
            prompt=(
                "Genera argumentos a favor y en contra de invertir en US equity como JSON: "
                '{"favor": [{"punto": "string", "dato": "string"}], '
                '"contra": [{"punto": "string", "dato": "string"}]}. '
                "Exactamente 3-4 en cada lista. Usa datos del council."
            ),
            council_context=council_ctx,
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=600,
            temperature=0.2,
        )
        args_favor = [{'punto': 'Ver council', 'dato': f'GDP {gdp}% QoQ' if gdp else 'Sin recomendación del comité'}]
        args_contra = [{'punto': 'Ver council', 'dato': 'Sin recomendación del comité'}]
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

        # Try to get view/conviction from parser
        alloc = self.parser.get_regional_allocation()
        usa_view = 'Sin recomendación'
        usa_conviccion = 'N/D'
        if alloc:
            usa_data = alloc.get('renta variable usa', alloc.get('usa', alloc.get('estados unidos', {})))
            if usa_data:
                usa_view = usa_data.get('vs_benchmark', 'Sin recomendación')
                usa_conviccion = usa_data.get('conviction', usa_data.get('weight', 'MEDIA'))

        eq_views = self.parser.get_equity_views()
        if eq_views:
            usa_eq = eq_views.get('usa', eq_views.get('estados unidos', eq_views.get('us', {})))
            if usa_eq:
                usa_view = usa_eq.get('view', usa_view)
                usa_conviccion = usa_eq.get('conviction', usa_conviccion)

        return {
            'region': 'Estados Unidos',
            'view': usa_view,
            'conviccion': usa_conviccion,
            'tesis': tesis,
            'argumentos_favor': args_favor,
            'argumentos_contra': args_contra,
            'trigger_cambio': 'Datos de inflacion y empleo proximos como catalisis para ajustar conviccion.'
        }

    def _default_usa_view(self) -> Dict[str, Any]:
        # Try to extract tesis from council parser even in default path
        tesis = 'Sin tesis del comité.'
        regional = self.parser.get_regional_allocation() if self.parser else None
        if regional:
            usa_data = regional.get('usa', regional.get('estados unidos', {}))
            if usa_data:
                tesis = usa_data.get('rationale', tesis)

        return {
            'region': 'Estados Unidos', 'view': 'Sin recomendación', 'conviccion': 'N/D',
            'tesis': tesis,
            'argumentos_favor': [{'punto': 'Ver council', 'dato': 'Sin recomendación del comité'}],
            'argumentos_contra': [{'punto': 'Ver council', 'dato': 'Sin recomendación del comité'}],
            'trigger_cambio': 'Ver council para triggers de cambio.'
        }

    def _generate_europe_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        rv = self._panel('rv') if self._has_council() else ''
        cio = self._cio() if self._has_council() else ''

        tesis = ''
        if rv or cio:
            tesis = generate_narrative(
                section_name="aa_europe_tesis",
                prompt=(
                    "Escribe la tesis de inversion para Europa en 3-4 oraciones. "
                    "Cubrir: posicion relativa, valuaciones, politica BCE, y riesgos. "
                    "Usa datos del council. Maximo 70 palabras."
                ),
                council_context=f"RV:\n{rv[:1000]}\n\nCIO:\n{cio[:800]}",
                company_name=self.company_name,
                max_tokens=250,
            )
        if not tesis:
            tesis = "Sin recomendación del comité para Europa."

        # Try parser for structured view/conviction
        europe_view = 'Sin recomendación'
        europe_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        if alloc:
            eu_data = alloc.get('europa', alloc.get('europe', {}))
            if eu_data:
                europe_view = eu_data.get('vs_benchmark', 'Sin recomendación')
                europe_conviccion = eu_data.get('conviction', eu_data.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        if eq_views:
            eu_eq = eq_views.get('europa', eq_views.get('europe', {}))
            if eu_eq:
                europe_view = eu_eq.get('view', europe_view)
                europe_conviccion = eu_eq.get('conviction', europe_conviccion)

        return {
            'region': 'Europa',
            'view': europe_view,
            'conviccion': europe_conviccion,
            'tesis': tesis,
            'argumentos_favor': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'argumentos_contra': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'trigger_cambio': 'Ver council para triggers de cambio.'
        }

    def _generate_china_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        riesgo = self._panel('riesgo') if self._has_council() else ''
        geo = self._panel('geo') if self._has_council() else ''

        epu = self._extract_number(macro, r'EPU.*?(\d+)', None)
        china_prob = self._extract_number(riesgo, r'China\s+Hard.*?(\d+)%', None)

        tesis = ''
        if macro or riesgo or geo:
            council_ctx = f"MACRO:\n{macro[:1000]}\n\nRISK:\n{riesgo[:800]}\n\nGEO:\n{geo[:800]}"
            quant_ctx = ""
            if epu:
                quant_ctx += f"EPU China: {int(epu)}. "
            if china_prob:
                quant_ctx += f"Hard landing prob: {int(china_prob)}%."

            tesis = generate_narrative(
                section_name="aa_china_tesis",
                prompt=(
                    "Escribe la tesis de inversion para China en 3-4 oraciones. "
                    "Cubrir: regimen economico, credit impulse, desacople US-China, "
                    "y postura (cautelosa/neutral). Usa datos del council. Maximo 70 palabras."
                ),
                council_context=council_ctx,
                quant_context=quant_ctx,
                company_name=self.company_name,
                max_tokens=250,
            )
        if not tesis:
            tesis = "Sin recomendación del comité para China."

        # Try parser for structured view/conviction
        china_view = 'Sin recomendación'
        china_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        if alloc:
            cn_data = alloc.get('china', {})
            if cn_data:
                china_view = cn_data.get('vs_benchmark', 'Sin recomendación')
                china_conviccion = cn_data.get('conviction', cn_data.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        if eq_views:
            cn_eq = eq_views.get('china', {})
            if cn_eq:
                china_view = cn_eq.get('view', china_view)
                china_conviccion = cn_eq.get('conviction', china_conviccion)

        return {
            'region': 'China',
            'view': china_view,
            'conviccion': china_conviccion,
            'tesis': tesis,
            'argumentos_favor': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'argumentos_contra': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'trigger_cambio': 'Ver council para triggers de cambio.'
        }

    def _generate_chile_view(self) -> Dict[str, Any]:
        from narrative_engine import generate_narrative

        macro = self._panel('macro') if self._has_council() else ''
        rf = self._panel('rf') if self._has_council() else ''

        tpm = self._extract_number(macro, r'TPM\s+(\d+\.?\d*)%', None)
        ipc = self._extract_number(macro, r'(?:IPC|inflaci[oó]n)\s+(\d+\.?\d*)%', None)
        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', None)
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
                ),
                council_context=f"MACRO:\n{macro[:1500]}\n\nRF:\n{rf[:800]}",
                quant_context=" | ".join(quant_parts),
                company_name=self.company_name,
                max_tokens=300,
            )
        if not tesis:
            tesis = "Sin recomendación del comité para Chile."
            if tpm is not None and ipc is not None:
                tesis = f"Chile con TPM {tpm}% y tasa real +{tpm_real}%."

        # Try parser for structured view/conviction
        chile_view = 'Sin recomendación'
        chile_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        if alloc:
            cl_data = alloc.get('chile', alloc.get('chile y latam', {}))
            if cl_data:
                chile_view = cl_data.get('vs_benchmark', 'Sin recomendación')
                chile_conviccion = cl_data.get('conviction', cl_data.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        if eq_views:
            cl_eq = eq_views.get('chile', eq_views.get('chile y latam', {}))
            if cl_eq:
                chile_view = cl_eq.get('view', chile_view)
                chile_conviccion = cl_eq.get('conviction', chile_conviccion)

        # Build arguments with real data (no hardcoded numbers)
        tpm_str = f'{tpm}%' if tpm is not None else 'N/D'
        ipc_str = f'{ipc}%' if ipc is not None else 'N/D'
        tpm_real_str = f'+{tpm_real}%' if tpm_real is not None else 'N/D'
        cobre_str = f'${cobre}/lb' if cobre is not None else 'N/D'

        return {
            'region': 'Chile y LatAm',
            'view': chile_view,
            'conviccion': chile_conviccion,
            'tesis': tesis,
            'argumentos_favor': [
                {'punto': 'Diferencial real', 'dato': f'TPM {tpm_str} - IPC {ipc_str} = {tpm_real_str} real'},
                {'punto': 'Cobre', 'dato': cobre_str},
                {'punto': 'BCCh', 'dato': 'Ver council para direccion de tasas'},
            ],
            'argumentos_contra': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'trigger_cambio': 'Ver council para triggers de cambio.'
        }

    def _generate_brazil_view(self) -> Dict[str, Any]:
        # Try parser for structured view/conviction
        brazil_view = 'Sin recomendación'
        brazil_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        if alloc:
            br_data = alloc.get('brasil', alloc.get('brazil', {}))
            if br_data:
                brazil_view = br_data.get('vs_benchmark', 'Sin recomendación')
                brazil_conviccion = br_data.get('conviction', br_data.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        if eq_views:
            br_eq = eq_views.get('brasil', eq_views.get('brazil', {}))
            if br_eq:
                brazil_view = br_eq.get('view', brazil_view)
                brazil_conviccion = br_eq.get('conviction', brazil_conviccion)

        return {
            'region': 'Brasil',
            'view': brazil_view,
            'conviccion': brazil_conviccion,
            'tesis': 'Sin recomendación del comité',
            'argumentos_favor': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'argumentos_contra': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'trigger_cambio': 'Ver council para triggers de cambio.'
        }

    def _generate_mexico_view(self) -> Dict[str, Any]:
        # Try parser for structured view/conviction
        mexico_view = 'Sin recomendación'
        mexico_conviccion = 'N/D'
        alloc = self.parser.get_regional_allocation()
        if alloc:
            mx_data = alloc.get('mexico', alloc.get('méxico', {}))
            if mx_data:
                mexico_view = mx_data.get('vs_benchmark', 'Sin recomendación')
                mexico_conviccion = mx_data.get('conviction', mx_data.get('weight', 'MEDIA'))
        eq_views = self.parser.get_equity_views()
        if eq_views:
            mx_eq = eq_views.get('mexico', eq_views.get('méxico', {}))
            if mx_eq:
                mexico_view = mx_eq.get('view', mexico_view)
                mexico_conviccion = mx_eq.get('conviction', mexico_conviccion)

        return {
            'region': 'México',
            'view': mexico_view,
            'conviccion': mexico_conviccion,
            'tesis': 'Sin recomendación del comité',
            'argumentos_favor': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'argumentos_contra': [
                {'punto': 'Ver council', 'dato': 'Sin recomendación del comité'},
            ],
            'trigger_cambio': 'Ver council para triggers de cambio.'
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
                {'region': 'US Large Cap', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'region': 'Europa', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'region': 'Chile', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'region': 'EM ex-China', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'region': 'China', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ]

        # View global from macro stance
        macro_stance = self.parser.get_macro_stance()
        view_global = macro_stance if macro_stance else 'Ver council'

        return {
            'view_global': view_global,
            'por_region': por_region,
            'sectores_preferidos': sectores_ow,
            'sectores_evitar': sectores_uw,
            'factor_tilt': factor
        }

    def _default_equity_view(self) -> Dict[str, Any]:
        return {
            'view_global': 'N/D',
            'por_region': [
                {'region': 'US', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'region': 'Chile', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ],
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'factor_tilt': 'N/D'
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

        # Extract rate view from council
        view_tasas = 'N/D'
        if 'higher' in rf.lower():
            months = self._extract_number(rf, r'HIGHER\s*\(?(\d+)-', 6)
            view_tasas = f'HIGHER ({int(months)}-9 meses)'
        elif 'lower' in rf.lower() or 'recorte' in rf.lower():
            view_tasas = 'LOWER — recortes esperados'
        elif 'neutral' in rf.lower() or 'estable' in rf.lower():
            view_tasas = 'ESTABLE'

        # Credit view: data-only, no hardcoded opinion
        ig_bps = self._q('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._q('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        if ig_bps and hy_bps:
            view_credito = f'IG: {self._fmt_bp(ig_bps)}, HY: {self._fmt_bp(hy_bps)}. Ver council.'
        elif ig_bps:
            view_credito = f'IG: {self._fmt_bp(ig_bps)}. Ver council.'
        else:
            view_credito = 'N/D — ver council'

        # Chile: enrich with real TPM expectations — no hardcoded rates
        chile = {
            'tpm_path': 'Ver council para trayectoria TPM',
            'carry_trade': 'Ver council para evaluacion de carry trade',
            'recomendacion': 'Ver council para recomendacion de curva Chile',
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

        # Build curva from council parser FI views
        fi_views = self.parser.get_fi_views() if self.parser else None
        curva = []
        tramo_keys = [
            ('0-2Y', ['0-2y', 'short', 'corto', 'treasury bills', 't-bills']),
            ('2-5Y', ['2-5y', 'medium', 'medio', 'intermedio']),
            ('5-10Y', ['5-10y', 'long', 'largo']),
            ('10Y+', ['10y+', '10+', 'ultra long', 'ultra largo']),
        ]
        for tramo_label, search_keys in tramo_keys:
            tramo_view = 'N/D'
            tramo_rationale = 'Sin recomendación del comité'
            if fi_views:
                for key in search_keys:
                    if key in fi_views:
                        tramo_view = fi_views[key].get('view', 'N/D')
                        tramo_rationale = fi_views[key].get('rationale', 'Ver council')
                        break
            curva.append({'tramo': tramo_label, 'view': tramo_view, 'rationale': tramo_rationale})

        return {
            'view_tasas': view_tasas,
            'view_duration': view_duration,
            'view_credito': view_credito,
            'curva': curva,
            'chile_especifico': chile,
        }

    def _default_rf_view(self) -> Dict[str, Any]:
        return {
            'view_tasas': 'N/D', 'view_duration': 'N/D', 'view_credito': 'N/D',
            'curva': [
                {'tramo': '0-2Y', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'tramo': '2-5Y', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'tramo': '5-10Y', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'tramo': '10Y+', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ],
            'chile_especifico': {
                'tpm_path': 'N/D', 'carry_trade': 'N/D',
                'recomendacion': 'N/D'
            }
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

        if fx_views:
            pares = []
            for pair, info in fx_views.items():
                pares.append({
                    'par': pair,
                    'view': info.get('view', 'N/D'),
                    'target_3m': 'N/D',
                    'target_12m': 'N/D',
                    'rationale': info.get('rationale', 'Sin recomendación del comité'),
                })
            return {
                'view_usd': 'Ver council para vista USD',
                'pares': pares,
            }

        # Fallback: minimal structure, no hardcoded targets
        return {
            'view_usd': 'Ver council para vista USD',
            'pares': [
                {'par': 'EUR/USD', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'par': 'USD/CLP', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': f'Spot: {usdclp_str}. Sin recomendación del comité'},
                {'par': 'USD/JPY', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'par': 'USD/CNY', 'view': 'N/D', 'target_3m': 'N/D', 'target_12m': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ]
        }

    def _generate_commodities_view(self) -> Dict[str, Any]:
        macro = self._panel('macro')

        cobre = self._extract_number(macro, r'[Cc]obre\s+\$?(\d+\.?\d*)', None)

        # Enrich with real data
        if cobre is None and self.data:
            try:
                chile = self.data.get_chile_latest()
                # cobre might be in commodities table
                comm_table = self.data.get_commodities_table()
                for c in comm_table:
                    if 'copper' in c.get('name', '').lower() or 'cobre' in c.get('name', '').lower():
                        cobre = c.get('last')
                        break
            except Exception:
                pass

        cobre_str = f'${cobre:.2f}/lb' if cobre is not None else 'N/D'
        cobre_range = (
            f'${cobre-0.5:.2f}-${cobre+0.5:.2f}/lb' if cobre is not None else 'N/D'
        )

        return {
            'commodities': [
                {'nombre': 'Cobre', 'view': 'Ver council', 'target': cobre_range, 'rationale': f'Precio actual: {cobre_str}. Ver council para recomendacion.'},
                {'nombre': 'Oro', 'view': 'Ver council', 'target': 'N/D', 'rationale': 'Ver council para recomendacion.'},
                {'nombre': 'Petróleo', 'view': 'Ver council', 'target': 'N/D', 'rationale': 'Ver council para recomendacion.'},
            ]
        }

    def _generate_tactical_actions(self) -> List[Dict[str, Any]]:
        """Acciones tácticas extraídas del CIO/final_recommendation del council."""
        final = self._final()
        cio = self._cio()

        # No hardcoded actions — council provides tactical recommendations
        # If council output available, return placeholder referencing council
        if final or cio:
            return [{
                'asset_class': 'Ver Council',
                'accion': 'CONSULTAR RECOMENDACIÓN',
                'desde': 'N/D',
                'hacia': 'N/D',
                'timing': 'N/D',
                'vehiculo': 'N/D',
                'rationale': 'Las acciones tácticas provienen del CIO y refinador del council. Ver final_recommendation.'
            }]
        return []

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

        # VIX from quant_data
        vix_str = self._q('vix', 'current', default='N/D')
        if isinstance(vix_str, (int, float)):
            vix_str = f"{vix_str:.1f}"

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
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=1200,
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

        return {
            'top_risks': top_risks,
            'calendario_eventos': [],  # Calendar is date-sensitive; left empty for freshness
            'triggers_reconvocatoria': triggers,
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
        view_map = {'OW': 'OW', 'UW': 'UW', 'N': 'N', 'N/D': 'N/D', 'NEUTRAL': 'N'}
        renta_variable = []
        for r in eq.get('por_region', []):
            renta_variable.append({
                'asset': r['region'],
                'view': view_map.get(r['view'], r['view']),
                'cambio': '→',
                'conviccion': 'N/D'
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
                'conviccion': 'N/D'
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
        renta_fija.append({'asset': 'IG Credit', 'view': ig_view, 'cambio': '→', 'conviccion': 'N/D'})
        renta_fija.append({'asset': 'HY Credit', 'view': hy_view, 'cambio': '→', 'conviccion': 'N/D'})

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
                'conviccion': 'N/D'
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
        commodities_fx.append({'asset': 'USD (DXY)', 'view': usd_view, 'cambio': '→', 'conviccion': 'N/D'})
        commodities_fx.append({'asset': 'CLP', 'view': clp_view, 'cambio': '→', 'conviccion': 'N/D'})

        return {
            'renta_variable': renta_variable,
            'renta_fija': renta_fija,
            'commodities_fx': commodities_fx,
            'postura_general': postura
        }

    def _default_dashboard(self) -> Dict[str, Any]:
        """Dashboard por defecto sin council — all views N/D."""
        return {
            'renta_variable': [
                {'asset': 'US Large Cap', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'Europa', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'China', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'Chile', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'EM ex-China', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
            ],
            'renta_fija': [
                {'asset': 'UST Short (0-2Y)', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'UST Medium (2-5Y)', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'UST Long (5-10Y)', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'IG Credit', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'HY Credit', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
            ],
            'commodities_fx': [
                {'asset': 'Cobre', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'Oro', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'Petroleo', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'USD (DXY)', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
                {'asset': 'CLP', 'view': 'N/D', 'cambio': '→', 'conviccion': 'N/D'},
            ],
            'postura_general': {'view': 'N/D', 'sesgo': 'N/D', 'conviccion': 'N/D'}
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
                {'ticker': 'SHY', 'nombre': 'iShares 1-3 Year Treasury', 'view': _fi_view(['0-2y', 'short', 'corto']), 'rationale': 'Short duration treasury'},
                {'ticker': 'VMBS', 'nombre': 'Vanguard MBS ETF', 'view': _fi_view(['mbs', 'agency', 'mortgage']), 'rationale': 'MBS spread exposure'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': _fi_view(['ig', 'investment grade', 'ig credit']), 'rationale': 'Investment grade corporate'},
                {'ticker': 'TLT', 'nombre': 'iShares 20+ Year Treasury', 'view': _fi_view(['10y+', '10+', 'ultra long', 'long']), 'rationale': 'Long duration treasury'},
                {'ticker': 'HYG', 'nombre': 'iShares High Yield Corp', 'view': _fi_view(['hy', 'high yield', 'hy credit']), 'rationale': 'High yield corporate'},
            ],
            'commodities': [
                {'ticker': 'CPER', 'nombre': 'US Copper Index Fund', 'view': 'N/D', 'rationale': 'Copper exposure — ver council para view'},
                {'ticker': 'COPX', 'nombre': 'Global X Copper Miners', 'view': 'N/D', 'rationale': 'Copper miners — ver council para view'},
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': 'N/D', 'rationale': 'Gold hedge — ver council para view'},
                {'ticker': 'USO', 'nombre': 'US Oil Fund', 'view': 'N/D', 'rationale': 'Oil exposure — ver council para view'},
                {'ticker': 'UUP', 'nombre': 'Invesco DB US Dollar', 'view': _fx_view(['USD/CLP', 'DXY']), 'rationale': 'USD exposure — ver council para view'},
            ]
        }

    def _default_focus_list(self) -> Dict[str, List]:
        """Focus list por defecto sin council — all views N/D."""
        return {
            'renta_variable': [
                {'ticker': 'SPY', 'nombre': 'SPDR S&P 500 ETF', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'ticker': 'ECH', 'nombre': 'iShares MSCI Chile', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'ticker': 'EEM', 'nombre': 'iShares MSCI EM', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ],
            'renta_fija': [
                {'ticker': 'BIL', 'nombre': 'SPDR Bloomberg T-Bill', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
                {'ticker': 'LQD', 'nombre': 'iShares IG Corporate', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
            ],
            'commodities': [
                {'ticker': 'GLD', 'nombre': 'SPDR Gold Shares', 'view': 'N/D', 'rationale': 'Sin recomendación del comité'},
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

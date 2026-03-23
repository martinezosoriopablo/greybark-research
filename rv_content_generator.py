# -*- coding: utf-8 -*-
"""
Greybark Research - Renta Variable Content Generator
=====================================================

Genera el CONTENIDO narrativo para el reporte de Renta Variable mensual.
Sigue la estructura de JPM Equity Strategy / MS Global Strategy:
- Valorizaciones por region
- Earnings y fundamentales
- Analisis sectorial con OW/UW
- Style: Growth vs Value
- Factor tilts
- Views regionales detalladas

Este modulo genera contenido especifico de mercados accionarios.
"""

import json
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RVContentGenerator:
    """Generador de contenido narrativo para Reporte de Renta Variable."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, company_name: str = ""):
        self.council = council_result or {}
        self.market_data = market_data or {}
        self.forecast = forecast_data or {}
        self.company_name = company_name
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)
        self.year = self.date.year
        self._used_council_paras = set()  # Track used paragraphs to avoid duplication
        self._parser = None
        self.bloomberg = None  # BloombergReader, injected externally

    def _q(self, *keys, default=None):
        """Navigate nested market_data dict by key path."""
        d = self.market_data
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

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

    # =========================================================================
    # COUNCIL DATA EXTRACTION HELPERS
    # =========================================================================

    def _panel(self, agent: str) -> str:
        """Extrae texto de un agente del panel."""
        return self.council.get('panel_outputs', {}).get(agent, '')

    def _extract_council_narrative(self, agent: str, keywords: list, max_len: int = 600) -> Optional[str]:
        """Extrae un párrafo del council panel que matchee keywords, sin repetir."""
        text = self._panel(agent)
        if not text:
            return None
        for para in text.split('\n\n'):
            p = para.strip()
            p_hash = hash(p[:100])
            if p_hash in self._used_council_paras:
                continue
            if len(p) > 80 and any(kw in p.lower() for kw in keywords):
                self._used_council_paras.add(p_hash)
                # Truncate at sentence boundary to avoid cut-off mid-sentence
                excerpt = p
                if len(excerpt) > max_len:
                    excerpt = excerpt[:max_len]
                    # Find last sentence-ending punctuation within the truncated text
                    last_period = max(excerpt.rfind('. '), excerpt.rfind('.\n'))
                    if last_period > max_len * 0.5:
                        excerpt = excerpt[:last_period + 1]
                    else:
                        # Fall back to word boundary
                        last_space = excerpt.rfind(' ')
                        if last_space > max_len * 0.6:
                            excerpt = excerpt[:last_space]
                return self._md_to_html(excerpt)
        return None

    @staticmethod
    def _truncate_at_sentence(text: str, max_len: int = 500) -> str:
        """Truncate text at a sentence boundary to avoid cutting mid-sentence."""
        if not text or len(text) <= max_len:
            return text
        excerpt = text[:max_len]
        # Try to find last sentence-ending punctuation
        last_period = max(excerpt.rfind('. '), excerpt.rfind('.\n'), excerpt.rfind('.'))
        if last_period > max_len * 0.5:
            return excerpt[:last_period + 1]
        # Fall back to word boundary
        last_space = excerpt.rfind(' ')
        if last_space > max_len * 0.6:
            return excerpt[:last_space]
        return excerpt

    @staticmethod
    def _md_to_html(text: str) -> str:
        """Convierte markdown básico a HTML para inyectar en reportes."""
        if not text:
            return text
        # Headers: # Title → <strong>Title</strong>
        text = re.sub(r'^#{1,3}\s+(.+)$', r'<strong>\1</strong>', text, flags=re.MULTILINE)
        # Bold: **text** → <strong>text</strong>
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic: *text* → <em>text</em>
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Bullet lists: - item → <br>• item
        text = re.sub(r'^\s*[-•]\s+', '• ', text, flags=re.MULTILINE)
        # Numbered lists: 1. item → <br>1. item
        text = re.sub(r'^\s*(\d+)\.\s+', r'\1. ', text, flags=re.MULTILINE)
        # Remove unresolved BLOQUE placeholders and truncated text
        text = re.sub(r'\[BLOQUE:\s*[^\]]*\]', '', text)
        # Remove truncated bold tags (e.g., **ANÁLI at end of text)
        text = re.sub(r'\*\*[A-ZÁÉÍÓÚÑ]{2,10}$', '', text)
        # Line breaks
        text = text.replace('\n\n', '<br><br>').replace('\n', '<br>')
        return text

    def _final(self) -> str:
        """Extrae la recomendación final."""
        return self.council.get('final_recommendation', '')

    def _cio(self) -> str:
        """Extrae la síntesis CIO."""
        return self.council.get('cio_synthesis', '')

    def _has_council(self) -> bool:
        """Verifica si hay datos del council disponibles."""
        return bool(self.council.get('final_recommendation', ''))

    def _extract_number(self, text: str, pattern: str, default=None):
        """Extrae un número de texto usando regex."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except (ValueError, IndexError):
                pass
        return default

    @staticmethod
    def _clean_json(raw: str):
        """Extract and parse JSON from LLM response, handling code fences and surrounding text."""
        import json as _json
        if not raw:
            return None
        cleaned = raw.strip()
        # Remove code fences (```json ... ``` or ``` ... ```)
        if cleaned.startswith('```'):
            first_nl = cleaned.find('\n')
            if first_nl > 0:
                cleaned = cleaned[first_nl + 1:]
            else:
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        # Try direct parse
        try:
            return _json.loads(cleaned)
        except _json.JSONDecodeError:
            pass
        # Regex fallback: find first [ ... ] or { ... } block
        m = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', cleaned)
        if m:
            try:
                return _json.loads(m.group(1))
            except _json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _clean_rationale(rationale: str, pe_value=None) -> str:
        """Clean council rationale text to remove contradictions with actual data.

        - If P/E data IS available, remove phrases claiming it's not.
        - Remove 'percentil X' where X looks like a P/E value (< 50), not a real percentile.
        """
        if not rationale:
            return ''
        cleaned = rationale
        # If PE data is available, strip "sin dato de P/E" type phrases
        if pe_value is not None:
            cleaned = re.sub(
                r',?\s*sin dato de P/?E[^.]*\.?\s*', ' ', cleaned, flags=re.IGNORECASE
            )
            cleaned = re.sub(
                r',?\s*sin dato de valuaci[oó]n[^.]*\.?\s*', ' ', cleaned, flags=re.IGNORECASE
            )
            cleaned = re.sub(
                r',?\s*no hay dato de P/?E[^.]*\.?\s*', ' ', cleaned, flags=re.IGNORECASE
            )
        # Fix "percentil X" where X is a P/E value (small number, not a real percentile)
        # Real percentiles are 0-100; P/E values used as percentiles are typically < 50
        # and match a known P/E value pattern (has decimal like 26.6, 17.8)
        def _fix_percentil(m):
            val = float(m.group(1))
            # If value matches a known P/E range (10-40) with decimal, likely a copy-paste error
            if pe_value is not None and abs(val - pe_value) < 0.5:
                return ''  # Remove the erroneous percentile claim
            return m.group(0)  # Keep legitimate percentiles
        cleaned = re.sub(r'percentil\s+(\d+\.?\d*)', _fix_percentil, cleaned, flags=re.IGNORECASE)
        # Clean up double spaces
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        return cleaned

    # =========================================================================
    # MARKET DATA ACCESS HELPERS
    # =========================================================================

    def _has_data(self) -> bool:
        """Verifica si hay datos de mercado reales disponibles."""
        return bool(self.market_data and self.market_data.get('metadata', {}).get('modules_ok', 0) > 0)

    def _val(self, region_key: str) -> dict:
        """Obtiene valuación de una región. Retorna {} si no hay datos."""
        return self.market_data.get('valuations', {}).get(region_key, {})

    def _sector_ret(self, sector_key: str) -> dict:
        """Obtiene retornos de un sector."""
        return self.market_data.get('sectors', {}).get('sector_returns', {}).get(sector_key, {})

    def _breadth(self) -> dict:
        """Obtiene datos de breadth."""
        return self.market_data.get('sectors', {}).get('breadth', {})

    def _risk_data(self) -> dict:
        """Obtiene datos de riesgo y correlaciones."""
        return self.market_data.get('risk', {})

    def _earnings_data(self) -> dict:
        """Obtiene datos de earnings."""
        return self.market_data.get('earnings', {})

    def _style_data(self) -> dict:
        """Obtiene datos de style (Growth/Value/Size)."""
        return self.market_data.get('style', {})

    def _real_rates_data(self) -> dict:
        """Obtiene datos de tasas reales y ERP."""
        return self.market_data.get('real_rates', {})

    def _credit_data(self) -> dict:
        """Obtiene datos de credit spreads."""
        return self.market_data.get('credit', {})

    def _bcch(self) -> dict:
        """Obtiene datos de índices BCCh (IPSA, USD/CLP, cobre, etc.)."""
        return self.market_data.get('bcch_indices', {})

    def _bcch_val(self, key: str) -> float:
        """Obtiene un valor de BCCh data. None si no disponible."""
        d = self._bcch().get(key, {})
        if isinstance(d, dict) and 'error' not in d:
            return d.get('value')
        return None

    def _bcch_ret(self, key: str, period: str = 'ytd') -> float:
        """Obtiene un retorno de BCCh data. None si no disponible."""
        d = self._bcch().get(key, {})
        if isinstance(d, dict) and 'error' not in d:
            return d.get('returns', {}).get(period)
        return None

    @staticmethod
    def _find_equity_view(views: dict, aliases: list) -> Optional[dict]:
        """Find an equity view by trying multiple key aliases."""
        if not views:
            return None
        for alias in aliases:
            if alias in views:
                return views[alias]
        return None

    def _fmt(self, val, suffix='', decimals=1, prefix='') -> str:
        """Formatea un número para display. Retorna 'N/D' si None."""
        if val is None:
            return 'N/D'
        try:
            return f"{prefix}{val:.{decimals}f}{suffix}"
        except (TypeError, ValueError):
            return str(val)

    # =========================================================================
    # SECCION 1: RESUMEN EJECUTIVO
    # =========================================================================

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Genera resumen ejecutivo del reporte RV."""

        return {
            'titulo': f"Perspectivas Renta Variable - {self.month_name} {self.year}",
            'postura_global': self._generate_global_stance(),
            'tabla_resumen': self._generate_summary_table(),
            'key_calls': self._generate_key_calls()
        }

    def _generate_global_stance(self) -> Dict[str, Any]:
        """Genera postura global de equity con narrativa Claude-powered."""
        has_text = self.parser.has_council_text() if self.parser else False
        result = {
            'view': 'NEUTRAL' if has_text else 'N/D',
            'cambio': '=',
            'conviccion': 'MEDIA' if has_text else 'N/D',
            'driver_principal': '',
            'narrativa': '',
        }

        rv = self._panel('rv') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        # Extract view from council — NO default stance
        if final:
            text = final.lower()
            import re as _re
            if _re.search(r'postura\s+(agresiva|agresivo)', text) or 'fuerte risk-on' in text:
                result['view'] = 'AGRESIVO'
                result['conviccion'] = 'ALTA'
            elif 'defensiva moderada' in text or 'defensivo moderado' in text:
                result['view'] = 'CAUTELOSO'
                result['conviccion'] = 'MEDIA-ALTA'
            elif 'risk-off' in text or 'postura defensiva' in text or 'cauteloso' in text:
                result['view'] = 'CAUTELOSO'
                result['conviccion'] = 'ALTA'
            elif 'subponder' in text or _re.search(r'\buw\b', text) or 'infraponder' in text:
                result['view'] = 'CAUTELOSO'
                result['conviccion'] = 'MEDIA-ALTA'
            elif 'constructiv' in text and 'cauteloso' not in text:
                result['view'] = 'CONSTRUCTIVO'
                result['conviccion'] = 'MEDIA-ALTA'
            elif 'sobreponder' in text or _re.search(r'\bow\b', text) or 'risk-on' in text:
                result['view'] = 'CONSTRUCTIVO'
                result['conviccion'] = 'MEDIA-ALTA'
            elif 'neutral' in text:
                result['view'] = 'NEUTRAL'
                result['conviccion'] = 'MEDIA'
            else:
                # Council exists but no explicit keyword — default to NEUTRAL
                result['view'] = 'NEUTRAL'
                result['conviccion'] = 'MEDIA'

        # Generate narrativa via Claude
        if rv or final:
            from narrative_engine import generate_narrative
            council_ctx = f"RV PANEL:\n{rv[:2000]}\n\nFINAL REC:\n{final[:1500]}"

            # Build list of contradictory words to avoid
            stance_contradictions = {
                'CONSTRUCTIVO': 'NO uses las palabras: cautelosa, cauteloso, defensiva, defensivo, risk-off',
                'AGRESIVO': 'NO uses las palabras: cautelosa, cauteloso, defensiva, defensivo, neutral',
                'CAUTELOSO': 'NO uses las palabras: constructiva, constructivo, agresiva, agresivo, risk-on',
                'NEUTRAL': 'NO uses las palabras: agresiva, agresivo',
            }
            anti_contradiction = stance_contradictions.get(result['view'], '')

            narrativa = generate_narrative(
                section_name="rv_global_stance",
                prompt=(
                    f"Escribe un parrafo de postura global en renta variable para {self.month_name} {self.year}. "
                    f"La postura es {result['view']} con conviccion {result['conviccion']}. "
                    f"IMPORTANTE: La postura es {result['view']}. {anti_contradiction}. "
                    "La narrativa DEBE ser coherente con la postura declarada. "
                    "Explica en 3-4 oraciones el fundamento: earnings, valuaciones, preferencias regionales "
                    "y principal driver. Usa SOLO datos del council."
                    "\n\nEscribe 150-200 palabras. Incluye: qué cambió vs período anterior, principal riesgo "
                    "con trigger de salida cuantificado, horizonte temporal (táctico 1-3m o estratégico 6-12m). "
                    "Explica jerga técnica (OW, UW, P/E, breadth, beta) con paréntesis en primera mención."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=600,
            )
            if narrativa:
                result['narrativa'] = narrativa

            driver = generate_narrative(
                section_name="rv_driver_principal",
                prompt=(
                    "Extrae en UNA frase corta (max 10 palabras) el principal driver de la postura en renta variable "
                    "segun el council. Ejemplo: 'Earnings solidos con valuaciones atractivas ex-US'. "
                    "Solo la frase, sin puntos ni explicacion."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=50,
            )
            if driver:
                result['driver_principal'] = driver

        # Fallbacks
        if not result['narrativa']:
            result['narrativa'] = (
                f"Nuestra postura en renta variable global es {result['view'].lower()} "
                f"para {self.month_name} {self.year}."
            )
        if not result['driver_principal']:
            result['driver_principal'] = 'Ver analisis detallado en secciones siguientes'

        return result

    def _generate_summary_table(self) -> List[Dict[str, Any]]:
        """Genera tabla resumen de views por region con retornos reales."""
        # BCCh index map for local returns
        bcch_ret_map = {
            'Estados Unidos': 'sp500',
            'Europa': 'eurostoxx',
            'Japon': 'nikkei',
            'Chile': 'ipsa',
        }

        # Try to get views from council parser first
        equity_views = self.parser.get_equity_views() or {}

        # Region label → list of parser key aliases (parser lowercases region names)
        equity_alias_map = {
            'Global Equity': ['global', 'global equity'],
            'Estados Unidos': ['usa', 'estados unidos', 'us', 'eeuu'],
            'Europa': ['europa', 'europe'],
            'Emergentes': ['em', 'emergentes', 'emerging'],
            'Japon': ['japón', 'japon', 'japan', 'japn'],
            'Chile': ['chile'],
        }

        defaults = [
            {'mercado': 'Global Equity', 'indice': 'MSCI (Morgan Stanley Capital International) ACWI', 'view': 'N', 'cambio': '=', 'driver': '-'},
            {'mercado': 'Estados Unidos', 'indice': 'S&P 500', 'view': 'N', 'cambio': '=', 'driver': '-'},
            {'mercado': 'Europa', 'indice': 'Stoxx 600', 'view': 'N', 'cambio': '=', 'driver': '-'},
            {'mercado': 'Emergentes', 'indice': 'MSCI EM', 'view': 'N', 'cambio': '=', 'driver': '-'},
            {'mercado': 'Japon', 'indice': 'Topix', 'view': 'N', 'cambio': '=', 'driver': '-'},
            {'mercado': 'Chile', 'indice': 'IPSA', 'view': 'N', 'cambio': '=', 'driver': '-'},
        ]

        # Overlay council views if available
        if equity_views:
            for row in defaults:
                ev = self._find_equity_view(equity_views, equity_alias_map.get(row['mercado'], [row['mercado'].lower()]))
                if ev:
                    row['view'] = ev.get('view', 'N')
                    row['driver'] = ev.get('rationale', '-')

        # Enrich with real BCCh index returns
        for row in defaults:
            bcch_key = bcch_ret_map.get(row['mercado'])
            if bcch_key:
                ytd = self._bcch_ret(bcch_key, 'ytd')
                m1 = self._bcch_ret(bcch_key, '1m')
                if ytd is not None:
                    row['retorno_ytd'] = f"{ytd:+.1f}%"
                if m1 is not None:
                    row['retorno_1m'] = f"{m1:+.1f}%"

        if not self._has_council():
            return defaults

        # Text mining fallback ONLY when structured parser returned nothing
        if not equity_views:
            rv = self._panel('rv')
            geo = self._panel('geo')
            source = rv + '\n' + geo

            # Try to detect region views from council text
            region_map = {
                'Estados Unidos': ('S&P 500', ['estados unidos', 's&p', 'us equity', 'eeuu']),
                'Europa': ('Stoxx 600', ['europa', 'stoxx', 'europe']),
                'Emergentes': ('MSCI EM', ['emergentes', 'em ', 'emerging']),
                'Chile': ('IPSA', ['chile', 'ipsa']),
            }
            text_lower = source.lower()

            for row in defaults:
                if row['mercado'] in region_map:
                    _, keywords = region_map[row['mercado']]
                    for kw in keywords:
                        if kw in text_lower:
                            idx = text_lower.find(kw)
                            context = text_lower[max(0, idx-50):idx+100]
                            if 'underweight' in context or 'uw' in context or 'reducir' in context:
                                row['view'] = 'UW'
                            elif 'overweight' in context or ' ow' in context or 'preferimos' in context or 'sobreponderar' in context:
                                row['view'] = 'OW'
                            elif 'neutral' in context:
                                row['view'] = 'NEUTRAL'
                            break

        return defaults

    def _generate_key_calls(self) -> List[str]:
        """Genera key calls del mes via Claude + datos reales."""
        from narrative_engine import generate_narrative

        # Chile call dinámico con datos BCCh + yfinance
        v = self._val('chile') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        ipsa_level = self._bcch_val('ipsa')
        ipsa_ytd = self._bcch_ret('ipsa', 'ytd')

        chile_quant = ""
        if pe and ipsa_level:
            chile_quant = f"IPSA en {ipsa_level:,.0f} ({pe:.1f}x P/E (Precio/Utilidad))"
            if ipsa_ytd is not None:
                chile_quant += f", {ipsa_ytd:+.1f}% YTD (rendimiento acumulado en el año)"
        elif pe:
            chile_quant = f"ECH a {pe:.1f}x P/E"

        rv = self._panel('rv') if self._has_council() else ''
        cio = self._cio() if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        if rv or cio or final:
            council_ctx = f"RV PANEL:\n{rv[:1500]}\n\nCIO:\n{cio[:1000]}\n\nFINAL:\n{final[:1000]}"
            quant_ctx = f"Datos Chile: {chile_quant}" if chile_quant else ""

            # Build verified_data for anti-fabrication (prevents P/E swap etc.)
            vd = {}
            if self._has_data():
                for rk, vd_key in [('us', 'sp500_pe'), ('europe', 'stoxx600_pe'),
                                    ('em', 'msci_em_pe'), ('chile', 'ipsa_pe')]:
                    rv_val = self._val(rk)
                    pe_v = rv_val.get('pe_trailing') or rv_val.get('pe_forward')
                    if pe_v:
                        vd[vd_key] = pe_v

            # Also add quant_ctx P/E values explicitly to the prompt
            pe_hints = []
            us_pe = self._val('us').get('pe_trailing') or self._val('us').get('pe_forward')
            if us_pe:
                pe_hints.append(f"S&P 500 P/E: {us_pe:.1f}x")
            if pe:
                pe_hints.append(f"IPSA P/E: {pe:.1f}x")
            if pe_hints:
                quant_ctx += "\n" + " | ".join(pe_hints)

            result = generate_narrative(
                section_name="rv_key_calls",
                prompt=(
                    f"Genera exactamente 5 key calls de renta variable para {self.month_name} {self.year}. "
                    "Cada call en una linea, formato: area/region + recomendacion + fundamento breve. "
                    "Cubrir: preferencia regional, sectores favoritos, style/factor tilt, Chile, y principal riesgo. "
                    "Usa datos del council — NO inventes numeros. "
                    "Devuelve cada call en una linea separada por \\n. Sin bullets ni numeracion."
                    "\n\nPara cada call, incluye: dato concreto → interpretación → posición, "
                    "riesgo con trigger de salida, horizonte (táctico 1-3m o estratégico 6-12m)."
                ),
                council_context=council_ctx,
                quant_context=quant_ctx,
                company_name=self.company_name,
                max_tokens=500,
                verified_data=vd if vd else None,
            )
            if result:
                lines = [l.strip() for l in result.split('\n') if l.strip()]
                if len(lines) >= 3:
                    return lines

        # Minimal fallback
        calls = [
            "Ver analisis sectorial y regional en secciones siguientes",
        ]
        if chile_quant:
            calls.append(f"Chile: {chile_quant}")
        return calls

    # =========================================================================
    # SECCION 2: VALORIZACIONES GLOBALES
    # =========================================================================

    def generate_valuations(self) -> Dict[str, Any]:
        """Genera seccion de valorizaciones."""

        return {
            'multiples_region': self._generate_regional_multiples(),
            'pe_targets': self._generate_pe_targets(),
            'equity_risk_premium': self._generate_erp(),
            'valuacion_relativa': self._generate_relative_valuation(),
            'narrativa': self._generate_valuation_narrative()
        }

    # PE trailing 10Y averages by region (updated quarterly, sources: Bloomberg/JPM/MSCI)
    PE_10Y_AVERAGES = {
        'us': 21.5,       # S&P 500 10Y avg trailing PE
        'europe': 15.8,   # Stoxx 600
        'em': 13.2,       # MSCI EM
        'japan': 16.5,    # Topix
        'chile': 14.0,    # IPSA
    }

    def _generate_regional_multiples(self) -> List[Dict[str, Any]]:
        """Genera tabla de multiples por region usando datos reales de yfinance + Bloomberg."""

        # Mapeo región → (key en valuations, nombre display, bbg_key for Bloomberg extended)
        region_map = [
            ('us', 'S&P 500', 'spx'),
            ('europe', 'Stoxx 600', 'stoxx600'),
            ('em', 'MSCI EM', 'msci_em'),
            ('japan', 'Topix', 'topix'),
            ('chile', 'IPSA', 'ipsa'),
        ]

        # Load Bloomberg extended valuations if available
        bbg_vals = {}
        if self.bloomberg:
            try:
                bbg_vals = self.bloomberg.get_valuations_extended()
            except Exception:
                pass

        if not self._has_data():
            # Fallback: tabla sin datos reales (se marca explícitamente)
            return [
                {'mercado': name, 'pe_fwd': 'N/D', 'pe_fwd_label': 'P/E (Precio/Utilidad) Forward',
                 'vs_10y_avg': 'N/D',
                 'ev_ebitda': 'N/D', 'ev_ebitda_label': 'EV/EBITDA (Valor Empresa / Utilidad operativa)',
                 'pb': 'N/D', 'div_yield': 'N/D',
                 'earning_yield': 'N/D', 'comentario': 'Sin datos de mercado'}
                for _, name, _ in region_map
            ]

        result = []
        for key, name, bbg_key in region_map:
            v = self._val(key)
            if 'error' in v or not v:
                result.append({
                    'mercado': name, 'pe_fwd': 'N/D', 'vs_10y_avg': 'N/D',
                    'ev_ebitda': 'N/D', 'pb': 'N/D', 'div_yield': 'N/D',
                    'earning_yield': 'N/D', 'comentario': f'Error obteniendo {key}'
                })
                continue

            pe = v.get('pe_trailing') or v.get('pe_forward')
            pb = v.get('pb')
            div_y = v.get('dividend_yield')
            ey = round(100 / pe, 1) if pe else None

            # Bloomberg overrides: PE 10Y avg, EV/EBITDA (Valor Empresa / Utilidad operativa), Div Yield
            bbg_region = bbg_vals.get(bbg_key, {})
            avg_pe_10y = bbg_region.get('pe_10y')
            ev_ebitda = bbg_region.get('ev')
            bbg_pe_fwd = bbg_region.get('pe')
            bbg_dy = bbg_region.get('dy')

            # Use Bloomberg PE forward if yfinance didn't provide one
            if not pe and bbg_pe_fwd:
                pe = bbg_pe_fwd
                ey = round(100 / pe, 1) if pe else None

            # Use Bloomberg dividend yield if yfinance didn't provide one
            if not div_y and bbg_dy:
                div_y = bbg_dy

            # vs 10Y promedio: Bloomberg → fallback constants
            if not avg_pe_10y:
                avg_pe_10y = self.PE_10Y_AVERAGES.get(key)

            vs_avg = None
            if pe and avg_pe_10y:
                vs_avg = ((pe / avg_pe_10y) - 1) * 100
                vs_str = f"+{vs_avg:.0f}%" if vs_avg > 0 else f"{vs_avg:.0f}%"
            else:
                vs_str = 'N/D'

            # Comentario basado en valuación
            if pe and vs_avg is not None:
                if vs_avg > 15:
                    comentario = 'Caro vs historia'
                elif vs_avg > 5:
                    comentario = 'Sobre promedio'
                elif vs_avg > -5:
                    comentario = 'Fair value'
                elif vs_avg > -10:
                    comentario = 'Descuento atractivo'
                else:
                    comentario = 'Muy atractivo'
            else:
                comentario = 'N/D'

            result.append({
                'mercado': name,
                'pe_fwd': self._fmt(pe, 'x') if pe else 'N/D',
                'vs_10y_avg': vs_str,
                'ev_ebitda': f"{ev_ebitda:.1f}x" if ev_ebitda else 'N/D',
                'ev_ebitda_label': 'EV/EBITDA (Valor Empresa / Utilidad operativa)',
                'pb': self._fmt(pb, 'x') if pb else 'N/D',
                'div_yield': self._fmt(div_y, '%') if div_y else 'N/D',
                'earning_yield': self._fmt(ey, '%') if ey else 'N/D',
                'comentario': comentario,
            })

        return result

    def _generate_pe_targets(self) -> List[Dict[str, Any]]:
        """Genera tabla de PE targets usando modelo econométrico de fair value."""
        try:
            from econometric_models import EquityValuationModel
        except ImportError:
            return []

        model = EquityValuationModel()

        # Get UST 10Y from market_data (real_rates or FRED)
        rr = self._real_rates_data()
        ust_10y = None
        if rr and 'error' not in rr:
            ust_10y = rr.get('ust_10y') or rr.get('nominal_10y')
        if not ust_10y:
            ust_10y = 4.3  # fallback

        targets = []
        region_names = [
            ('us', 'S&P 500'),
            ('europe', 'Stoxx 600'),
            ('em', 'MSCI EM'),
            ('japan', 'Topix'),
            ('chile', 'IPSA'),
        ]
        for region_key, name in region_names:
            v = self._val(region_key)
            pe = v.get('pe_trailing') or v.get('pe_forward')
            if not pe:
                continue
            eps_g = v.get('eps_growth_yoy')
            result = model.fair_pe(region_key, ust_10y, pe, eps_g)
            if result:
                targets.append({
                    'mercado': name,
                    'pe_actual': f"{pe:.1f}x",
                    'pe_fair': f"{result['fair_pe']:.1f}x",
                    'signal': result['signal'],
                    'upside': f"{result['upside_pct']:+.1f}%" if result['upside_pct'] is not None else 'N/D',
                    'fed_model': f"{result['components']['fed_model']:.1f}x" if result['components']['fed_model'] else 'N/D',
                    'mean_rev': f"{result['components']['mean_reversion']:.1f}x",
                    'eg_model': f"{result['components']['earnings_growth']:.1f}x" if result['components']['earnings_growth'] else 'N/D',
                })
        return targets

    def _generate_erp(self) -> Dict[str, Any]:
        """Genera analisis de ERP (Equity Risk Premium — Prima de Riesgo Accionario) usando datos reales."""

        rr = self._real_rates_data()
        real_rate_10y = rr.get('real_rate_10y') if rr and 'error' not in rr else None

        # Calcular ERP por región usando PE real y tasa real FRED
        regions = [
            ('S&P 500', 'us'),
            ('Stoxx 600', 'europe'),
            ('MSCI EM', 'em'),
            ('IPSA', 'chile'),
        ]

        datos = []
        for name, key in regions:
            v = self._val(key) if self._has_data() else {}
            pe = v.get('pe_trailing') or v.get('pe_forward')
            ey = round(100 / pe, 1) if pe else None

            # Usar tasa real US como proxy para todos (simplificación razonable)
            rr_val = real_rate_10y

            if ey is not None and rr_val is not None:
                erp = round(ey - rr_val, 1)
                if erp > 6:
                    vs_hist = 'Muy atractivo'
                elif erp > 4:
                    vs_hist = 'Atractivo'
                elif erp > 2:
                    vs_hist = 'Neutral'
                else:
                    vs_hist = 'Bajo'
            else:
                erp = None
                vs_hist = 'N/D'

            datos.append({
                'mercado': name,
                'earning_yield': self._fmt(ey, '%') if ey else 'N/D',
                'tasa_real': self._fmt(rr_val, '%') if rr_val is not None else 'N/D',
                'erp': self._fmt(erp, '%') if erp is not None else 'N/D',
                'vs_historia': vs_hist,
            })

        # Narrativa dinámica
        erp_us = None
        if datos and datos[0]['erp'] != 'N/D':
            erp_us = float(datos[0]['erp'].replace('%', ''))

        if erp_us is not None:
            narrativa = (
                f"El Equity Risk Premium (ERP) del S&P 500 se ubica en {datos[0]['erp']} "
                f"(earnings yield {datos[0]['earning_yield']} menos tasa real {datos[0]['tasa_real']}). "
            )
            # Comparar con ex-US — solo datos, sin opinión
            ex_us_erps = [d for d in datos[1:] if d['erp'] != 'N/D']
            if ex_us_erps:
                narrativa += f"Mercados ex-US: {', '.join(d['mercado'] + ' ERP ' + d['erp'] for d in ex_us_erps)}."
        else:
            narrativa = (
                "El Equity Risk Premium no pudo ser calculado con datos actuales. "
                "Los datos de tasas reales o valuaciones no están disponibles."
            )

        return {
            'narrativa': narrativa,
            'datos': datos,
        }

    def _generate_relative_valuation(self) -> Dict[str, Any]:
        """Genera valuación relativa usando P/E reales y style spreads."""

        us_v = self._val('us') if self._has_data() else {}
        eu_v = self._val('europe') if self._has_data() else {}
        em_v = self._val('em') if self._has_data() else {}

        us_pe = us_v.get('pe_trailing') or us_v.get('pe_forward')
        eu_pe = eu_v.get('pe_trailing') or eu_v.get('pe_forward')
        em_pe = em_v.get('pe_trailing') or em_v.get('pe_forward')

        # US vs RoW: premium de PE real
        if us_pe and eu_pe:
            us_row_spread = ((us_pe / eu_pe) - 1) * 100
            us_row = {
                'spread_actual': f"{us_row_spread:+.0f}%",
                'us_pe': f"{us_pe:.1f}x",
                'row_pe': f"{eu_pe:.1f}x (Europa)",
                'comentario': 'US premium elevado' if us_row_spread > 30 else 'US premium moderado',
                'implicancia': 'Favorece rotación a RoW' if us_row_spread > 25 else 'Spread razonable',
            }
        else:
            us_row = {'spread_actual': 'N/D', 'comentario': 'Sin datos de PE', 'implicancia': '-'}

        # Growth vs Value spread real
        sd = self._style_data()
        gv_spread = sd.get('growth_value_spread', {}) if sd and 'error' not in sd else {}
        gv_ytd = gv_spread.get('ytd')
        if gv_ytd is not None:
            gv = {
                'spread_ytd': f"{gv_ytd:+.1f}pp",
                'comentario': 'Growth lidera' if gv_ytd > 3 else ('Value lidera' if gv_ytd < -3 else 'Equilibrado'),
                'implicancia': '-',
            }
        else:
            gv = {'spread_ytd': 'N/D', 'comentario': 'Sin datos de style', 'implicancia': '-'}

        # Large vs Small spread real
        size_spread = sd.get('size_spread', {}) if sd and 'error' not in sd else {}
        ls_ytd = size_spread.get('ytd')
        if ls_ytd is not None:
            ls = {
                'spread_ytd': f"{ls_ytd:+.1f}pp",
                'comentario': 'Small caps lideran' if ls_ytd > 3 else ('Large caps lideran' if ls_ytd < -3 else 'Similar'),
                'implicancia': 'Selectivo en small caps de calidad',
            }
        else:
            ls = {'spread_ytd': 'N/D', 'comentario': 'Sin datos de size', 'implicancia': '-'}

        return {
            'us_vs_row': us_row,
            'growth_vs_value': gv,
            'large_vs_small': ls,
        }

    def _generate_valuation_narrative(self) -> str:
        """Genera narrativa de valorizaciones basada en datos reales."""

        # Try council first (deduplicated)
        council_narr = self._extract_council_narrative('rv', ['valuaci', 'p/e', 'multiple', 'valoriza'])
        if council_narr:
            return council_narr

        # Build from real data
        if self._has_data():
            us = self._val('us')
            eu = self._val('europe')
            em = self._val('em')
            ch = self._val('chile')

            us_pe = us.get('pe_trailing') or us.get('pe_forward')
            eu_pe = eu.get('pe_trailing') or eu.get('pe_forward')
            em_pe = em.get('pe_trailing') or em.get('pe_forward')
            ch_pe = ch.get('pe_trailing') or ch.get('pe_forward')

            parts = ["Las valorizaciones globales reflejan dispersión entre mercados. "]

            if us_pe:
                parts.append(f"US cotiza a {us_pe:.1f}x P/E. ")

            ex_us_parts = []
            if eu_pe:
                ex_us_parts.append(f"Europa {eu_pe:.1f}x")
            if em_pe:
                ex_us_parts.append(f"EM {em_pe:.1f}x")
            if ch_pe:
                ex_us_parts.append(f"Chile {ch_pe:.1f}x")
            if ex_us_parts:
                parts.append(f"En contraste, {', '.join(ex_us_parts)} ofrecen valuaciones más atractivas. ")

            # Add regional preference from council if available
            ev = (self.parser.get_equity_views() if self.parser else {}) or {}
            ow_regions = [r.capitalize() for r, d in ev.items() if d.get('view') == 'OW']
            if ow_regions:
                parts.append(f"Preferencia: {', '.join(ow_regions)}.")

            return ''.join(parts)

        return (
            "Sin datos de valuación disponibles. Se requiere ejecutar "
            "equity_data_collector para generar narrativa basada en datos reales."
        )

    # =========================================================================
    # SECCION 3: EARNINGS Y FUNDAMENTALES
    # =========================================================================

    def generate_earnings(self) -> Dict[str, Any]:
        """Genera seccion de earnings."""

        return {
            'earnings_growth': self._generate_earnings_growth(),
            'revision_trends': self._generate_revision_trends(),
            'margenes_roe': self._generate_margins_roe(),
            'earnings_calendar': self._generate_earnings_calendar(),
            'narrativa': self._generate_earnings_narrative()
        }

    def _generate_earnings_growth(self) -> List[Dict[str, Any]]:
        """Genera tabla de crecimiento de earnings con datos reales de AV."""
        ed = self._earnings_data()
        if not ed or 'error' in ed:
            # Fallback — no hardcoded EPS values
            return [
                {'region': 'S&P 500', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
                {'region': 'Stoxx 600', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
                {'region': 'MSCI EM', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
                {'region': 'Topix', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
                {'region': 'IPSA', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
            ]

        rows = []
        group_map = [
            ('us_mega', 'S&P 500', '$'),
            ('europe', 'Stoxx 600', 'E'),
            ('chile', 'IPSA', 'CLP '),
        ]

        for group_key, display_name, currency in group_map:
            group = ed.get(group_key, {})
            if not group or 'error' in group:
                continue

            growth = group.get('avg_eps_growth_yoy')
            revision = group.get('avg_eps_change_30d_pct')
            beat_rate = group.get('avg_beat_rate')
            pe_trailing = group.get('avg_trailing_pe')
            pe_forward = group.get('avg_forward_pe')

            rows.append({
                'region': display_name,
                'growth': self._fmt(growth, '%', 0, '+') if growth and growth > 0 else self._fmt(growth, '%', 0),
                'revision_3m': self._fmt(revision, '%', 1, '+') if revision and revision > 0 else self._fmt(revision, '%', 1),
                'beat_rate': self._fmt(beat_rate, '%', 0),
                'pe_trailing': self._fmt(pe_trailing, 'x', 1),
                'pe_forward': self._fmt(pe_forward, 'x', 1),
            })

        return rows if rows else [
            {'region': 'S&P 500', 'growth': 'N/D', 'revision_3m': 'N/D', 'beat_rate': 'N/D', 'pe_trailing': 'N/D', 'pe_forward': 'N/D'},
        ]

    def _generate_revision_trends(self) -> Dict[str, Any]:
        """Genera tendencias de revisiones con datos reales de EARNINGS_ESTIMATES."""
        ed = self._earnings_data()

        default_result = {
            'narrativa': (
                "Datos de revisiones de earnings no disponibles. "
                "Se requiere ejecutar equity_data_collector para obtener datos reales de revisiones."
            ),
            'por_region': [
                {'region': 'US', 'upgrades': 'N/D', 'downgrades': 'N/D', 'net': 'N/D', 'tendencia': 'N/D'},
                {'region': 'Europa', 'upgrades': 'N/D', 'downgrades': 'N/D', 'net': 'N/D', 'tendencia': 'N/D'},
                {'region': 'EM', 'upgrades': 'N/D', 'downgrades': 'N/D', 'net': 'N/D', 'tendencia': 'N/D'},
                {'region': 'Japon', 'upgrades': 'N/D', 'downgrades': 'N/D', 'net': 'N/D', 'tendencia': 'N/D'},
                {'region': 'Chile', 'upgrades': 'N/D', 'downgrades': 'N/D', 'net': 'N/D', 'tendencia': 'N/D'},
            ]
        }

        if not ed or 'error' in ed:
            return default_result

        region_map = [
            ('us_mega', 'US'),
            ('europe', 'Europa'),
            ('chile', 'Chile'),
        ]

        por_region = []
        any_data = False

        for group_key, display_name in region_map:
            group = ed.get(group_key, {})
            if not group or 'error' in group:
                continue

            upgrade_pct = group.get('avg_upgrade_pct_30d')
            if upgrade_pct is None:
                continue

            any_data = True
            downgrade_pct = round(100 - upgrade_pct, 1)
            net = round(upgrade_pct - downgrade_pct, 1)

            # Determine trend label
            if upgrade_pct >= 65:
                tendencia = 'Fuerte'
            elif upgrade_pct >= 55:
                tendencia = 'Mejorando'
            elif upgrade_pct >= 45:
                tendencia = 'Estable'
            elif upgrade_pct >= 35:
                tendencia = 'Deteriorando'
            else:
                tendencia = 'Debil'

            por_region.append({
                'region': display_name,
                'upgrades': f'{upgrade_pct:.0f}%',
                'downgrades': f'{downgrade_pct:.0f}%',
                'net': f'{net:+.0f}%',
                'tendencia': tendencia,
            })

        if not any_data:
            return default_result

        # Build narrative from real data
        parts = ["Las revisiones de earnings (30d) muestran: "]
        for r in por_region:
            parts.append(f"{r['region']} {r['tendencia'].lower()} ({r['upgrades']} upgrades), ")
        narrative = ''.join(parts).rstrip(', ') + '.'

        return {
            'narrativa': narrative,
            'por_region': por_region,
        }

    def _generate_margins_roe(self) -> Dict[str, Any]:
        """Genera analisis de margenes y ROE con datos reales de AV OVERVIEW."""
        ed = self._earnings_data()

        default_result = {
            'narrativa': (
                "Datos de márgenes y ROE no disponibles. "
                "Se requiere ejecutar equity_data_collector para obtener datos reales."
            ),
            'datos': [
                {'region': 'S&P 500', 'margen_op': 'N/D', 'roe': 'N/D', 'margen_neto': 'N/D', 'tendencia': 'N/D'},
                {'region': 'Stoxx 600', 'margen_op': 'N/D', 'roe': 'N/D', 'margen_neto': 'N/D', 'tendencia': 'N/D'},
                {'region': 'MSCI EM', 'margen_op': 'N/D', 'roe': 'N/D', 'margen_neto': 'N/D', 'tendencia': 'N/D'},
                {'region': 'Topix', 'margen_op': 'N/D', 'roe': 'N/D', 'margen_neto': 'N/D', 'tendencia': 'N/D'},
                {'region': 'IPSA', 'margen_op': 'N/D', 'roe': 'N/D', 'margen_neto': 'N/D', 'tendencia': 'N/D'},
            ]
        }

        if not ed or 'error' in ed:
            return default_result

        group_map = [
            ('us_mega', 'S&P 500'),
            ('europe', 'Stoxx 600'),
            ('chile', 'IPSA'),
        ]

        datos = []
        any_data = False

        for group_key, display_name in group_map:
            group = ed.get(group_key, {})
            if not group or 'error' in group:
                continue

            op_margin = group.get('avg_operating_margin')
            profit_margin = group.get('avg_profit_margin')
            roe = group.get('avg_roe')

            if op_margin is None and profit_margin is None and roe is None:
                continue

            any_data = True

            # Format margins — AV returns as decimal (0.125 = 12.5%)
            def _pct(val):
                if val is None:
                    return 'N/D'
                # AV returns margins as decimals (e.g., 0.125 for 12.5%)
                if abs(val) < 1:
                    return f'{val * 100:.1f}%'
                return f'{val:.1f}%'

            # Derive tendencia from revision momentum
            upgrade_pct = group.get('avg_upgrade_pct_30d')
            if upgrade_pct is not None:
                if upgrade_pct > 70:
                    tendencia = 'Mejorando'
                elif upgrade_pct > 50:
                    tendencia = 'Estable'
                else:
                    tendencia = 'Deteriorando'
            else:
                tendencia = 'N/D'

            datos.append({
                'region': display_name,
                'margen_op': _pct(op_margin),
                'margen_neto': _pct(profit_margin),
                'roe': _pct(roe),
                'tendencia': tendencia,
            })

        if not any_data:
            return default_result

        # Build narrative from real data
        parts = ["Margenes y rentabilidad por region (datos reales AV): "]
        for d in datos:
            parts.append(f"{d['region']}: margen op. {d['margen_op']}, ROE {d['roe']}. ")
        narrative = ''.join(parts)

        return {
            'narrativa': narrative,
            'datos': datos,
        }

    def _generate_earnings_calendar(self) -> List[Dict[str, Any]]:
        """Genera calendario de earnings con datos reales de AV EARNINGS_CALENDAR."""
        ed = self._earnings_data()
        calendar = ed.get('calendar', {}) if ed and 'error' not in ed else {}

        # Placeholder when no real data available
        default_calendar = [
            {'fecha': '-', 'empresa': '-', 'nombre': 'Calendario de earnings no disponible',
             'estimado': 'N/D', 'relevancia': '-'}
        ]

        if not calendar or 'error' in calendar:
            return default_calendar

        entries = calendar.get('entries', [])
        if not entries:
            return default_calendar

        # Filter out past dates — only show upcoming earnings
        from datetime import datetime as _dt
        today = _dt.now().date()

        def _parse_date_safe(s):
            try:
                return _dt.strptime(s, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return _dt.max.date()

        entries = [e for e in entries if _parse_date_safe(e.get('report_date', '')) >= today]
        if not entries:
            return default_calendar

        # Format entries for display (take first 10)
        result = []
        for entry in entries[:10]:
            report_date = entry.get('report_date', '')
            # Format date nicely (YYYY-MM-DD -> DD Mon)
            try:
                from datetime import datetime as dt
                d = dt.strptime(report_date, '%Y-%m-%d')
                months_es = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
                fecha = f"{d.day} {months_es[d.month - 1]}"
            except (ValueError, IndexError):
                fecha = report_date

            estimate = entry.get('estimate')
            estimate_str = f"Est. EPS ${estimate:.2f}" if estimate else 'N/D'

            result.append({
                'fecha': fecha,
                'empresa': entry.get('symbol', ''),
                'nombre': entry.get('name', ''),
                'estimado': estimate_str,
                'relevancia': 'Alta',
            })

        return result if result else default_calendar

    def _generate_earnings_narrative(self) -> str:
        """Genera narrativa de earnings basada en datos reales."""

        # Council first (deduplicated)
        council_narr = self._extract_council_narrative('rv', ['earning', 'eps', 'utilidad', 'beneficio'])
        if council_narr:
            return council_narr

        # Real data from earnings collector
        ed = self._earnings_data()
        if ed and 'error' not in ed:
            parts = []
            us_data = ed.get('us_mega', {})
            if us_data and 'error' not in us_data:
                beat = us_data.get('avg_beat_rate')
                surprise = us_data.get('avg_surprise_pct')
                growth = us_data.get('avg_eps_growth_yoy')
                if beat:
                    parts.append(f"En US, el beat rate promedio de mega caps es {beat:.0f}%")
                if surprise:
                    parts.append(f" con surprise promedio de {surprise:+.1f}%")
                if growth:
                    parts.append(f". Crecimiento YoY de EPS: {growth:+.1f}%")
                parts.append(". ")

            chile_data = ed.get('chile', {})
            if chile_data and 'error' not in chile_data:
                ch_beat = chile_data.get('avg_beat_rate')
                if ch_beat:
                    parts.append(f"En Chile, beat rate de {ch_beat:.0f}%. ")

            if parts:
                return ''.join(parts) + "Los datos de earnings refuerzan selectividad por mercado."

        return (
            "Datos de earnings no disponibles. Se requiere ejecutar "
            "equity_data_collector con acceso a AlphaVantage para datos reales."
        )

    # =========================================================================
    # SECCION 4: ANALISIS SECTORIAL
    # =========================================================================

    def generate_sector_analysis(self) -> Dict[str, Any]:
        """Genera analisis sectorial."""

        return {
            'matriz_sectorial': self._generate_sector_matrix(),
            'sectores_preferidos': self._generate_preferred_sectors(),
            'sectores_evitar': self._generate_avoid_sectors(),
            'narrativa': self._generate_sector_narrative()
        }

    def _generate_sector_matrix(self) -> List[Dict[str, Any]]:
        """Genera matriz sectorial global con retornos reales de ETFs sectoriales."""

        # Mapeo sector → (key en sector_returns, view default, valuacion default, earnings default, catalizador default)
        # Enrich Materials and Energy catalysts with real commodity data from BCCh
        copper = self._bcch_val('copper')
        copper_ytd = self._bcch_ret('copper', 'ytd')
        gold = self._bcch_val('gold')
        gold_ytd = self._bcch_ret('gold', 'ytd')
        oil = self._bcch_val('oil_wti')
        oil_ytd = self._bcch_ret('oil_wti', 'ytd')

        mat_cat = 'Cobre, China estabilizando'
        if copper is not None and copper_ytd is not None:
            mat_cat = f'Cobre {copper:.2f} USD/lb ({copper_ytd:+.1f}% YTD)'
            if gold is not None and gold_ytd is not None:
                mat_cat += f', Oro {gold:,.0f} ({gold_ytd:+.1f}%)'

        energy_cat = 'OPEC+, transicion'
        if oil is not None and oil_ytd is not None:
            energy_cat = f'WTI {oil:.0f} USD/bbl ({oil_ytd:+.1f}% YTD), OPEC+'

        # Get sector views from council parser
        sector_views = self.parser.get_sector_views() or {}

        # Sector name → list of parser key aliases (parser lowercases sector names)
        sector_alias_map = {
            'Technology': ['technology', 'tech'],
            'Healthcare': ['healthcare', 'health', 'salud'],
            'Financials': ['financials', 'financieros', 'banks'],
            'Materials': ['materials', 'materiales'],
            'Industrials': ['industrials', 'industriales'],
            'Consumer Disc.': ['consumer disc', 'consumer disc.', 'consumer discretionary', 'consumo discrecional'],
            'Energy': ['energy', 'energía', 'energia'],
            'Comm Services': ['comm services', 'communication services', 'comunicaciones'],
            'Consumer Staples': ['consumer staples', 'consumo básico', 'staples'],
            'Utilities': ['utilities', 'servicios públicos'],
            'Real Estate': ['real estate', 'inmobiliario'],
        }

        # Derive valuacion and earnings signals from available data
        breadth = self._breadth().get('sector_breadth', {})

        def _sector_valuation(key: str) -> str:
            """Derive valuation label from YTD performance (proxy)."""
            sr = self._sector_ret(key)
            ytd = sr.get('returns', {}).get('ytd') if sr and 'error' not in sr else None
            if ytd is None:
                return '-'
            if ytd > 15:
                return 'Elevada'
            elif ytd > 5:
                return 'Justa-Alta'
            elif ytd > -5:
                return 'Justa'
            elif ytd > -15:
                return 'Justa-Baja'
            else:
                return 'Descontada'

        def _sector_earnings(key: str) -> str:
            """Derive earnings signal from breadth data (% above 50d MA)."""
            # Map sector key to ETF ticker for breadth lookup
            etf_map = {
                'technology': 'XLK', 'healthcare': 'XLV', 'financials': 'XLF',
                'materials': 'XLB', 'industrials': 'XLI', 'consumer_disc': 'XLY',
                'energy': 'XLE', 'comm_services': 'XLC', 'consumer_staples': 'XLP',
                'utilities': 'XLU', 'real_estate': 'XLRE',
            }
            ticker = etf_map.get(key, '')
            if breadth and ticker:
                for etf_key, bdata in breadth.items():
                    if isinstance(bdata, dict) and bdata.get('ticker', '').upper() == ticker:
                        pct = bdata.get('pct_above_50d')
                        if pct is not None:
                            if pct > 60:
                                return 'Fuerte'
                            elif pct > 40:
                                return 'Estable'
                            else:
                                return 'Débil'
            # Fallback: use YTD as proxy
            sr = self._sector_ret(key)
            ytd = sr.get('returns', {}).get('ytd') if sr and 'error' not in sr else None
            if ytd is not None:
                return 'Fuerte' if ytd > 10 else ('Estable' if ytd > -3 else 'Débil')
            return '-'

        sector_map = [
            ('Technology', 'technology', 'N', '-'),
            ('Healthcare', 'healthcare', 'N', '-'),
            ('Financials', 'financials', 'N', '-'),
            ('Materials', 'materials', 'N', mat_cat),
            ('Industrials', 'industrials', 'N', '-'),
            ('Consumer Disc.', 'consumer_disc', 'N', '-'),
            ('Energy', 'energy', 'N', energy_cat),
            ('Comm Services', 'comm_services', 'N', '-'),
            ('Consumer Staples', 'consumer_staples', 'N', '-'),
            ('Utilities', 'utilities', 'N', '-'),
            ('Real Estate', 'real_estate', 'N', '-'),
        ]

        # Overlay council sector views if available
        if sector_views:
            sector_map_updated = []
            for name, key, view, cat_default in sector_map:
                aliases = sector_alias_map.get(name, [name.lower()])
                sv = self._find_equity_view(sector_views, aliases)
                if sv:
                    view = sv.get('view', 'N')
                    cat_default = sv.get('rationale', cat_default)
                sector_map_updated.append((name, key, view, cat_default))
            sector_map = sector_map_updated

        result = []
        for name, key, view, cat_default in sector_map:
            sr = self._sector_ret(key)
            returns = sr.get('returns', {}) if sr and 'error' not in sr else {}

            # Momentum basado en retornos reales
            ytd = returns.get('ytd')
            m1 = returns.get('1m')
            m3 = returns.get('3m')

            if ytd is not None:
                if ytd > 10:
                    momentum = f'Fuerte ({ytd:+.1f}% YTD)'
                elif ytd > 3:
                    momentum = f'Positivo ({ytd:+.1f}% YTD)'
                elif ytd > -3:
                    momentum = f'Neutro ({ytd:+.1f}% YTD)'
                elif ytd > -10:
                    momentum = f'Debil ({ytd:+.1f}% YTD)'
                else:
                    momentum = f'Muy debil ({ytd:+.1f}% YTD)'
            else:
                momentum = 'N/D'

            ret_str = ''
            if m1 is not None:
                ret_str += f'1M: {m1:+.1f}%'
            if m3 is not None:
                ret_str += f' | 3M: {m3:+.1f}%'

            result.append({
                'sector': name,
                'view': view,
                'valuacion': _sector_valuation(key),
                'momentum': momentum,
                'retornos': ret_str if ret_str else 'N/D',
                'earnings': _sector_earnings(key),
                'catalizador': cat_default,
            })

        return result

    def _generate_preferred_sectors(self) -> List[Dict[str, Any]]:
        """Genera detalle de sectores preferidos from council parser."""
        sector_views = self.parser.get_sector_views() or {}

        # Map sector names to ETF keys for return lookup
        sector_etf_map = {
            'healthcare': 'healthcare', 'energy': 'energy', 'consumer staples': 'consumer_staples',
            'utilities': 'utilities', 'technology': 'technology', 'materials': 'materials',
            'industrials': 'industrials', 'financials': 'financials', 'real estate': 'real_estate',
            'consumer disc': 'consumer_disc', 'consumer discretionary': 'consumer_disc',
            'comm services': 'comm_services', 'communication services': 'comm_services',
        }

        # Well-known subsector names per sector for extraction from council text
        sector_subsectors = {
            'healthcare': ['pharma', 'biotech', 'medtech', 'managed care'],
            'energy': ['upstream', 'midstream', 'downstream', 'servicios', 'E&P'],
            'technology': ['software', 'semiconductores', 'cloud', 'hardware', 'AI'],
            'consumer staples': ['alimentos', 'beverages', 'personal care'],
            'utilities': ['eléctricas', 'gas', 'renovables', 'agua'],
            'financials': ['bancos', 'seguros', 'asset management', 'fintech'],
            'materials': ['minería', 'químicos', 'acero', 'oro'],
            'industrials': ['aeroespacial', 'transporte', 'maquinaria'],
        }

        if sector_views:
            preferred = []
            for k, v in sector_views.items():
                if v.get('view') != 'OW':
                    continue
                tesis = v.get('rationale', '-')
                if not tesis or tesis == '-':
                    tesis = self._extract_sector_commentary(k) or '-'

                # Derive upside from sector ETF 1M performance as proxy
                etf_key = sector_etf_map.get(k.lower(), '')
                upside_str = '-'
                if etf_key:
                    sr = self._sector_ret(etf_key)
                    m1 = sr.get('returns', {}).get('1m') if sr and 'error' not in sr else None
                    if m1 is not None:
                        upside_str = f'{m1:+.1f}% 1M'

                # Extract subsector mentions from council text
                subsectores = self._extract_sector_picks(k, sector_subsectors.get(k.lower(), []))
                evitar_list = self._extract_sector_avoids(k)

                preferred.append({
                    'sector': k.title(), 'view': v['view'], 'tesis': tesis,
                    'upside': upside_str, 'subsectores': subsectores, 'evitar': evitar_list,
                })
            if preferred:
                return preferred

        # Fallback: generate from sector returns data
        from narrative_engine import generate_data_driven_narrative
        sector_data = self._q('equity', 'sectors')
        if sector_data and isinstance(sector_data, dict):
            top_sectors = sorted(
                [(k, v.get('returns', {}).get('1m', 0)) for k, v in sector_data.items()
                 if isinstance(v, dict) and 'error' not in v],
                key=lambda x: x[1] if x[1] is not None else 0, reverse=True
            )[:3]
            return [
                {'sector': s[0].replace('_', ' ').title(), 'view': 'OW',
                 'tesis': f'Retorno 1M: {s[1]:+.1f}% — liderazgo sectorial' if s[1] else 'Análisis cuantitativo',
                 'upside': '-', 'subsectores': [], 'evitar': []}
                for s in top_sectors if s[1] is not None
            ] or [{'sector': 'Análisis cuantitativo', 'view': 'N', 'tesis': 'Datos sectoriales insuficientes', 'upside': '-', 'subsectores': [], 'evitar': []}]
        return [{'sector': 'Datos insuficientes', 'view': 'N', 'tesis': 'Requiere datos sectoriales para recomendación', 'upside': '-', 'subsectores': [], 'evitar': []}]

    def _extract_sector_picks(self, sector_name: str, subsector_keywords: list) -> list:
        """Extract subsector/stock mentions from council text for a given sector."""
        rv_text = self._panel('rv')
        if not rv_text:
            return []
        found = []
        sector_lower = sector_name.lower()
        for para in rv_text.split('\n'):
            p = para.strip().lower()
            if sector_lower not in p:
                continue
            for sub in subsector_keywords:
                if sub.lower() in p and sub.title() not in found:
                    found.append(sub.title())
        return found[:4]  # Max 4 subsectors

    def _extract_sector_avoids(self, sector_name: str) -> list:
        """Extract subsectors/stocks to avoid from council text."""
        rv_text = self._panel('rv')
        riesgo_text = self._panel('riesgo')
        if not rv_text and not riesgo_text:
            return []
        found = []
        combined = (rv_text or '') + '\n' + (riesgo_text or '')
        sector_lower = sector_name.lower()
        avoid_keywords = ['evitar', 'reducir', 'uw', 'subponderar', 'riesgo']
        for para in combined.split('\n'):
            p = para.strip()
            p_lower = p.lower()
            if sector_lower in p_lower and any(kw in p_lower for kw in avoid_keywords):
                # Extract a clean sentence containing the avoid keyword
                # Split the paragraph into sentences and pick the relevant one
                sentences = re.split(r'(?<=[.;])\s+', p)
                for sent in sentences:
                    s_lower = sent.strip().lower()
                    if any(kw in s_lower for kw in avoid_keywords):
                        clean = sent.strip()
                        # Cap length but at a word boundary
                        if len(clean) > 80:
                            truncated = clean[:80]
                            last_space = truncated.rfind(' ')
                            if last_space > 40:
                                truncated = truncated[:last_space]
                            clean = truncated
                        if clean and clean not in found:
                            found.append(clean)
                            break
        return found[:3]

    def _extract_sector_commentary(self, sector_name: str) -> Optional[str]:
        """Extrae comentario sectorial del council text."""
        rv_text = self._panel('rv')
        if not rv_text:
            return None
        sector_lower = sector_name.lower()
        for para in rv_text.split('\n'):
            p = para.strip()
            if sector_lower in p.lower() and len(p) > 30:
                return self._md_to_html(self._truncate_at_sentence(p.strip(), 200))
        return None

    def _generate_avoid_sectors(self) -> List[Dict[str, Any]]:
        """Genera detalle de sectores a evitar from council parser."""
        sector_views = self.parser.get_sector_views() or {}
        if sector_views:
            avoid = []
            for k, v in sector_views.items():
                if v.get('view') != 'UW':
                    continue
                razon = v.get('rationale', '-')
                if not razon or razon == '-':
                    razon = self._extract_sector_commentary(k) or '-'
                # Try to extract trigger from council text
                que_cambiaria = '-'
                rv_text = self._panel('rv')
                if rv_text:
                    for para in rv_text.split('\n'):
                        p = para.strip().lower()
                        if k.lower() in p and any(t in p for t in ['cambiaría', 'revertiría', 'si ', 'trigger', 'salida']):
                            que_cambiaria = self._md_to_html(self._truncate_at_sentence(para.strip(), 150))
                            break

                avoid.append({
                    'sector': k.title(), 'view': v['view'],
                    'razon': razon, 'que_cambiaria': que_cambiaria,
                })
            if avoid:
                return avoid

        # Fallback: generate from worst-performing sectors
        sector_data = self._q('equity', 'sectors')
        if sector_data and isinstance(sector_data, dict):
            worst_sectors = sorted(
                [(k, v.get('returns', {}).get('1m', 0)) for k, v in sector_data.items()
                 if isinstance(v, dict) and 'error' not in v],
                key=lambda x: x[1] if x[1] is not None else 0
            )[:2]
            return [
                {'sector': s[0].replace('_', ' ').title(), 'view': 'UW',
                 'razon': f'Retorno 1M: {s[1]:+.1f}% — rezago sectorial' if s[1] else 'Análisis cuantitativo',
                 'que_cambiaria': 'Mejora en datos fundamentales del sector'}
                for s in worst_sectors if s[1] is not None
            ] or [{'sector': 'Datos insuficientes', 'view': 'N', 'razon': 'Requiere análisis completo', 'que_cambiaria': 'N/D'}]
        return [{'sector': 'Datos insuficientes', 'view': 'N', 'razon': 'Requiere datos sectoriales', 'que_cambiaria': 'N/D'}]

    def _generate_sector_narrative(self) -> str:
        """Genera narrativa sectorial."""
        default = (
            "Preferencia sectorial no disponible. "
            "Ver analisis del council para recomendaciones de sectores especificos."
        )

        if not self._has_council():
            return default

        council_narr = self._extract_council_narrative('rv', ['sector', 'overweight', 'underweight', 'tecnolog', 'financ'])
        if council_narr:
            return council_narr

        return default

    # =========================================================================
    # SECCION 5: STYLE & FACTORS
    # =========================================================================

    def generate_style_factors(self) -> Dict[str, Any]:
        """Genera seccion de style y factors."""

        return {
            'growth_vs_value': self._generate_growth_value(),
            'factor_performance': self._generate_factor_performance(),
            'large_vs_small': self._generate_size_analysis(),
            'recomendacion_style': self._generate_style_recommendation()
        }

    def _generate_growth_value(self) -> Dict[str, Any]:
        """Genera analisis Growth vs Value usando datos reales de ETFs."""

        sd = self._style_data()

        if sd and 'error' not in sd and 'growth' in sd and 'value' in sd:
            g_ret = sd.get('growth', {}).get('returns', {})
            v_ret = sd.get('value', {}).get('returns', {})
            gv_spread = sd.get('growth_value_spread', {})
            style_signal = sd.get('style_signal', 'BALANCED')

            performance = {
                'growth_ytd': self._fmt(g_ret.get('ytd'), '%', prefix='+' if (g_ret.get('ytd') or 0) >= 0 else ''),
                'value_ytd': self._fmt(v_ret.get('ytd'), '%', prefix='+' if (v_ret.get('ytd') or 0) >= 0 else ''),
                'spread_ytd': self._fmt(gv_spread.get('ytd'), '%', prefix='+' if (gv_spread.get('ytd') or 0) >= 0 else ''),
                'growth_1m': self._fmt(g_ret.get('1m'), '%', prefix='+' if (g_ret.get('1m') or 0) >= 0 else ''),
                'value_1m': self._fmt(v_ret.get('1m'), '%', prefix='+' if (v_ret.get('1m') or 0) >= 0 else ''),
            }

            # Get style views from council parser
            fv = (self.parser.get_factor_views() if self.parser else {}) or {}
            g_view = fv.get('growth', {})
            v_view = fv.get('value', {})
            q_view = fv.get('quality', {})
            style_suffix = ""
            if g_view.get('view') or v_view.get('view') or q_view.get('view'):
                parts_s = []
                if g_view.get('view'):
                    parts_s.append(f"Growth {g_view['view']}")
                if v_view.get('view'):
                    parts_s.append(f"Value {v_view['view']}")
                if q_view.get('view'):
                    parts_s.append(f"Quality {q_view['view']}")
                style_suffix = " Postura: " + ", ".join(parts_s) + "."
                # Add rationale from strongest conviction
                best_rat = q_view.get('rationale') or g_view.get('rationale') or v_view.get('rationale') or ''
                if best_rat:
                    style_suffix += f" {best_rat}"

            ytd_spread = gv_spread.get('ytd', 0)
            if ytd_spread > 5:
                narrativa = (
                    f"Growth lidera sobre Value YTD "
                    f"({performance['growth_ytd']} vs {performance['value_ytd']}, spread de {performance['spread_ytd']})."
                    f"{style_suffix}"
                )
            elif ytd_spread < -5:
                narrativa = (
                    f"Value supera a Growth YTD ({performance['value_ytd']} vs {performance['growth_ytd']}, "
                    f"spread de {performance['spread_ytd']})."
                    f"{style_suffix}"
                )
            else:
                narrativa = (
                    f"Growth y Value muestran performance similar YTD ({performance['growth_ytd']} vs {performance['value_ytd']})."
                    f"{style_suffix}"
                )
        else:
            performance = {
                'growth_ytd': 'N/D', 'value_ytd': 'N/D', 'spread_ytd': 'N/D',
                'growth_1m': 'N/D', 'value_1m': 'N/D',
            }
            narrativa = "Datos de style no disponibles."
            style_signal = 'BALANCED'

        # Derive preferencia from factor views
        fv_pref = ((self.parser.get_factor_views() if self.parser else {}) or {}) or {}
        pref_parts = []
        for fname in ('quality', 'value', 'growth', 'momentum'):
            fdata = fv_pref.get(fname, {})
            if fdata.get('view') == 'OW':
                pref_parts.append(fname.capitalize())
        preferencia = ' + '.join(pref_parts) if pref_parts else ('BARBELL' if style_signal == 'BALANCED' else style_signal)

        return {
            'performance': performance,
            'valuacion': {
                'growth_pe': 'N/D', 'value_pe': 'N/D',
                'spread': 'N/D', 'vs_historia': 'N/D',
            },
            'narrativa': narrativa,
            'view': 'BARBELL' if style_signal == 'BALANCED' else style_signal,
            'preferencia': preferencia,
        }

    def _generate_factor_performance(self) -> List[Dict[str, Any]]:
        """Genera performance de factores usando scores reales de FactorAnalytics + Bloomberg."""

        fd = self.market_data.get('factors', {})
        has_factors = fd and 'error' not in fd

        # Factor ETF returns desde style data
        sd = self._style_data()
        g_ret = sd.get('growth', {}).get('returns', {}) if sd and 'error' not in sd else {}
        v_ret = sd.get('value', {}).get('returns', {}) if sd and 'error' not in sd else {}
        sm_ret = sd.get('small_cap', {}).get('returns', {}) if sd and 'error' not in sd else {}

        # Bloomberg factor returns (MSCI factor indices) as fallback/supplement
        bbg_factors = {}
        if self.bloomberg:
            try:
                bbg_factors = self.bloomberg.get_factor_returns()
            except Exception:
                pass

        # Scores promedio por factor (SPY como referencia US)
        spy_scores = fd.get('SPY', {}) if has_factors else {}

        # Get factor views from council parser (dynamic, not hardcoded)
        factor_views = self.parser.get_factor_views() or {}
        _has_text = self.parser.has_council_text() if self.parser else False
        _factor_default = 'N' if _has_text else 'N/D'

        def _fv(key: str) -> dict:
            """Lookup factor view from council parser, fallback NEUTRAL when council exists."""
            v = factor_views.get(key, {})
            return {
                'view': v.get('view', _factor_default),
                'rationale': v.get('rationale', '-'),
            }

        def _fv_size() -> dict:
            """Try multiple key variants for size/small cap factor."""
            for key in ('size small', 'size (small)', 'small cap', 'size'):
                v = factor_views.get(key)
                if v:
                    return {
                        'view': v.get('view', _factor_default),
                        'rationale': v.get('rationale', '-'),
                    }
            return {'view': _factor_default, 'rationale': '-'}

        fv_quality = _fv('quality')
        fv_momentum = _fv('momentum')
        fv_value = _fv('value')
        fv_growth = _fv('growth')
        fv_size = _fv_size()

        def _bbg_ytd(bbg_key: str) -> Optional[str]:
            """Get Bloomberg factor YTD return formatted."""
            val = bbg_factors.get(bbg_key)
            if val is not None:
                prefix = '+' if val >= 0 else ''
                return f"{prefix}{val:.1f}%"
            return None

        factors = [
            {
                'factor': 'Quality',
                'score': self._fmt(spy_scores.get('quality'), '/100') if spy_scores.get('quality') is not None else 'N/D',
                'ytd': _bbg_ytd('quality') or 'N/D',
                'view': fv_quality['view'],
                'rationale': fv_quality['rationale'],
            },
            {
                'factor': 'Momentum',
                'score': self._fmt(spy_scores.get('momentum'), '/100') if spy_scores.get('momentum') is not None else 'N/D',
                'ytd': _bbg_ytd('momentum') or 'N/D',
                'view': fv_momentum['view'],
                'rationale': fv_momentum['rationale'],
            },
            {
                'factor': 'Value',
                'score': self._fmt(spy_scores.get('value'), '/100') if spy_scores.get('value') is not None else 'N/D',
                'ytd': self._fmt(v_ret.get('ytd'), '%', prefix='+' if (v_ret.get('ytd') or 0) >= 0 else '') if v_ret.get('ytd') is not None else (_bbg_ytd('value') or 'N/D'),
                'view': fv_value['view'],
                'rationale': fv_value['rationale'],
            },
            {
                'factor': 'Growth',
                'score': self._fmt(spy_scores.get('growth'), '/100') if spy_scores.get('growth') is not None else 'N/D',
                'ytd': self._fmt(g_ret.get('ytd'), '%', prefix='+' if (g_ret.get('ytd') or 0) >= 0 else '') if g_ret.get('ytd') is not None else (_bbg_ytd('growth') or 'N/D'),
                'view': fv_growth['view'],
                'rationale': fv_growth['rationale'],
            },
            {
                'factor': 'Size (Small)',
                'score': 'N/D',
                'ytd': self._fmt(sm_ret.get('ytd'), '%', prefix='+' if (sm_ret.get('ytd') or 0) >= 0 else '') if sm_ret.get('ytd') is not None else (_bbg_ytd('size') or 'N/D'),
                'view': fv_size['view'],
                'rationale': fv_size['rationale'],
            },
        ]

        # Add composite scores for cross-region comparison if available
        if has_factors:
            region_scores = []
            for ticker in ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH']:
                scores = fd.get(ticker, {})
                if scores and 'error' not in scores:
                    comp = scores.get('composite')
                    if comp is not None:
                        region_scores.append({'ticker': ticker, 'composite': comp})
            if region_scores:
                factors.append({
                    'factor': 'Composite (por region)',
                    'score': ' | '.join(f"{s['ticker']}: {s['composite']:.0f}" for s in region_scores),
                    'ytd': '-',
                    'view': '-',
                    'rationale': 'Score compuesto multi-factor por region',
                })

        # Check if any real scores exist (not N/D)
        has_any_scores = any(
            f['score'] not in ('N/D', '-')
            for f in factors
            if f['factor'] != 'Composite (por region)'
        )

        return {'factors': factors, 'has_scores': has_any_scores}

    def _generate_size_analysis(self) -> Dict[str, Any]:
        """Genera analisis Large vs Small usando datos reales de style ETFs."""

        sd = self._style_data()
        has_style = sd and 'error' not in sd

        lg_ret = sd.get('large_cap', {}).get('returns', {}) if has_style else {}
        sm_ret = sd.get('small_cap', {}).get('returns', {}) if has_style else {}
        size_spread = sd.get('size_spread', {}) if has_style else {}
        size_signal = sd.get('size_signal', 'LARGE_CAP') if has_style else 'LARGE_CAP'

        lg_ytd = lg_ret.get('ytd')
        sm_ytd = sm_ret.get('ytd')
        spread_ytd = size_spread.get('ytd')

        # Get size view from council parser
        fv = ((self.parser.get_factor_views() if self.parser else {}) or {}) or {}
        size_view_data = None
        for key in ('size small', 'size (small)', 'small cap', 'size'):
            if key in fv:
                size_view_data = fv[key]
                break
        size_v = size_view_data.get('view', 'NEUTRAL') if size_view_data else 'NEUTRAL'
        size_rat = size_view_data.get('rationale', '') if size_view_data else ''
        size_suffix = f" Postura size: {size_v}." if size_v else ""
        if size_rat:
            size_suffix += f" {size_rat}"

        if lg_ytd is not None and sm_ytd is not None:
            if spread_ytd and spread_ytd > 3:
                narrativa = (
                    f"Small caps ({sm_ytd:+.1f}% YTD) superan a large caps ({lg_ytd:+.1f}% YTD), "
                    f"spread de {spread_ytd:+.1f}pp.{size_suffix}"
                )
            elif spread_ytd and spread_ytd < -3:
                narrativa = (
                    f"Large caps ({lg_ytd:+.1f}% YTD) lideran sobre small caps ({sm_ytd:+.1f}% YTD), "
                    f"spread de {spread_ytd:+.1f}pp.{size_suffix}"
                )
            else:
                narrativa = (
                    f"Large ({lg_ytd:+.1f}% YTD) y small caps ({sm_ytd:+.1f}% YTD) muestran "
                    f"performance similar (spread {spread_ytd:+.1f}pp).{size_suffix}"
                )
        else:
            narrativa = f"Datos de size no disponibles.{size_suffix}" if size_suffix else "Datos de size no disponibles."

        return {
            'performance': {
                'large_ytd': self._fmt(lg_ytd, '%', prefix='+' if (lg_ytd or 0) >= 0 else '') if lg_ytd is not None else 'N/D',
                'small_ytd': self._fmt(sm_ytd, '%', prefix='+' if (sm_ytd or 0) >= 0 else '') if sm_ytd is not None else 'N/D',
                'spread_ytd': self._fmt(spread_ytd, 'pp', prefix='+' if (spread_ytd or 0) >= 0 else '') if spread_ytd is not None else 'N/D',
                'large_1m': self._fmt(lg_ret.get('1m'), '%', prefix='+' if (lg_ret.get('1m') or 0) >= 0 else '') if lg_ret.get('1m') is not None else 'N/D',
                'small_1m': self._fmt(sm_ret.get('1m'), '%', prefix='+' if (sm_ret.get('1m') or 0) >= 0 else '') if sm_ret.get('1m') is not None else 'N/D',
            },
            'signal': size_signal,
            'view': size_v,
            'narrativa': narrativa,
        }

    def _generate_style_recommendation(self) -> Dict[str, Any]:
        """Genera recomendacion de style — contenido viene del council."""
        from narrative_engine import generate_narrative

        # Extract council RV context for style recommendation
        rv_panel = self.council.get('panel_outputs', {}).get('rv', '') if self.council else ''

        if rv_panel:
            rationale = generate_narrative(
                section_name="rv_style_recommendation",
                prompt=(
                    "Escribe 1-2 oraciones sobre la recomendación de estilo de inversión "
                    "(growth vs value, quality, momentum) basándote en el contexto del council. "
                    "Sé específico sobre qué estilo favorecer y por qué."
                ),
                council_context=rv_panel[:1500],
                quant_context="",
                company_name=self.company_name,
                max_tokens=400
            )
        else:
            # Fallback: build from parser factor views
            fv = (self.parser.get_factor_views() if self.parser else {}) or {}
            ow_factors = [f.capitalize() for f, d in fv.items() if d.get('view') == 'OW']
            if ow_factors:
                rationale = f"Preferencia: {', '.join(ow_factors)}."
                best_rat = next((d.get('rationale', '') for f, d in fv.items() if d.get('view') == 'OW' and d.get('rationale')), '')
                if best_rat:
                    rationale += f" {best_rat}"
            else:
                rationale = ""

        # Build recommendation from factor views
        fv_rec = (self.parser.get_factor_views() if self.parser else {}) or {}
        ow_list = [f.capitalize() for f, d in fv_rec.items() if d.get('view') == 'OW']
        recomendacion = ' + '.join(ow_list) if ow_list else 'NEUTRAL'

        return {
            'recomendacion': recomendacion,
            'quality_allocation': 'N/D',
            'value_allocation': 'N/D',
            'evitar': [],
            'rationale': rationale
        }

    # =========================================================================
    # SECCION 6: VIEWS REGIONALES
    # =========================================================================

    def _get_equity_target(self, index_key: str) -> dict:
        """Get target_12m and upside from forecast data if available."""
        targets = self._fc('equity_targets') if self.forecast else None
        if not targets or not isinstance(targets, dict):
            return {}
        data = targets.get(index_key, {})
        if isinstance(data, dict) and 'error' not in data:
            target = data.get('target_12m')
            ret = data.get('expected_return_pct')
            result = {}
            if target is not None:
                result['target_12m'] = f"{target:,.0f}"
            if ret is not None:
                prefix = '+' if ret >= 0 else ''
                result['upside'] = f"{prefix}{ret:.1f}%"
            return result
        return {}

    def generate_regional_views(self) -> Dict[str, Any]:
        """Genera views regionales detalladas."""

        return {
            'us': self._generate_us_view(),
            'europe': self._generate_europe_view(),
            'em': self._generate_em_view(),
            'japan': self._generate_japan_view(),
            'chile': self._generate_chile_view()
        }

    def _generate_us_view(self) -> Dict[str, Any]:
        """Genera view de US con datos reales."""
        v = self._val('us') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        # Try to get US view from council parser
        equity_views = self.parser.get_equity_views() or {}
        us_council_view = self._find_equity_view(equity_views, ['usa', 'estados unidos', 'us', 'eeuu']) or {}
        view = us_council_view.get('view', 'N') if us_council_view else 'N'
        cambio = '='

        # Get equity target from forecast engine
        eq_target = self._get_equity_target('sp500')

        result = {
            'mercado': 'Estados Unidos',
            'indice': 'S&P 500',
            'view': view,
            'cambio': cambio,
            'target_12m': eq_target.get('target_12m', '-'),
            'upside': eq_target.get('upside', '-'),
            'pe_actual': pe_str,
            'pe_historia': 'N/D',
            'narrativa': (
                f"El S&P 500 cotiza a {pe_str} P/E. "
                + (f"El retorno YTD es de {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + (self._clean_rationale(us_council_view.get('rationale', ''), pe_value=pe) + '. '
                   if us_council_view.get('rationale') else '')
            ),
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'catalizadores': [],
            'riesgos': []
        }

        # Enrich from council if available
        if self._has_council():
            rv = self._panel('rv')
            macro = self._panel('macro')
            source = rv + '\n' + macro
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['estados unidos', 's&p', 'us ', 'eeuu', 'norteam']):
                        result['narrativa'] = self._md_to_html(self._truncate_at_sentence(p, 500))
                        break

        return result

    def _generate_europe_view(self) -> Dict[str, Any]:
        """Genera view de Europa con datos reales."""
        v = self._val('europe') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        # Get Europe view from council parser
        equity_views = self.parser.get_equity_views() or {}
        eu_council_view = self._find_equity_view(equity_views, ['europa', 'europe']) or {}

        eq_target = self._get_equity_target('eurostoxx')

        result = {
            'mercado': 'Europa',
            'indice': 'Stoxx 600',
            'view': eu_council_view.get('view', 'N') if eu_council_view else 'N',
            'cambio': '=',
            'target_12m': eq_target.get('target_12m', '-'),
            'upside': eq_target.get('upside', '-'),
            'pe_actual': pe_str,
            'pe_historia': 'N/D',
            'narrativa': (
                f"Europa cotiza a {pe_str} P/E. "
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + (self._clean_rationale(eu_council_view.get('rationale', ''), pe_value=pe) + '. '
                   if eu_council_view.get('rationale') else '')
            ),
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'catalizadores': [],
            'riesgos': []
        }

        if self._has_council():
            rv = self._panel('rv')
            geo = self._panel('geo')
            source = rv + '\n' + geo
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['europa', 'stoxx', 'bce', 'eurozona']):
                        result['narrativa'] = self._md_to_html(self._truncate_at_sentence(p, 500))
                        break

        return result

    def _generate_em_view(self) -> Dict[str, Any]:
        """Genera view de EM con datos reales."""
        v = self._val('em') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        # Get EM view from council parser
        equity_views = self.parser.get_equity_views() or {}
        em_council_view = self._find_equity_view(equity_views, ['em', 'emergentes', 'emerging']) or {}

        eq_target = self._get_equity_target('msci_em')

        result = {
            'mercado': 'Emergentes',
            'indice': 'MSCI EM',
            'view': em_council_view.get('view', 'N') if em_council_view else 'N',
            'cambio': '=',
            'target_12m': eq_target.get('target_12m', '-'),
            'upside': eq_target.get('upside', '-'),
            'pe_actual': pe_str,
            'pe_historia': 'N/D',
            'narrativa': (
                f"EM cotiza a {pe_str} P/E. "
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + (self._clean_rationale(em_council_view.get('rationale', ''), pe_value=pe) + '. '
                   if em_council_view.get('rationale') else '')
            ),
            'paises_preferidos': [],
            'paises_evitar': [],
            'china_view': {
                'view': 'N/D', 'peso_benchmark': 'N/D',
                'peso_recomendado': 'N/D',
                'comentario': 'Ver análisis del council para vista China'
            },
            'catalizadores': [],
            'riesgos': []
        }

        if self._has_council():
            rv = self._panel('rv')
            geo = self._panel('geo')
            source = rv + '\n' + geo
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['emergent', 'em ', 'china', 'india', 'latam']):
                        result['narrativa'] = self._md_to_html(self._truncate_at_sentence(p, 500))
                        break

        return result

    def _generate_japan_view(self) -> Dict[str, Any]:
        """Genera view de Japon con datos reales."""
        v = self._val('japan') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        # Get Japan view from council parser
        equity_views = self.parser.get_equity_views() or {}
        jp_council_view = self._find_equity_view(equity_views, ['japón', 'japon', 'japan', 'japn']) or {}

        eq_target = self._get_equity_target('nikkei')

        return {
            'mercado': 'Japon',
            'indice': 'Topix',
            'view': jp_council_view.get('view', 'N') if jp_council_view else 'N',
            'cambio': '=',
            'target_12m': eq_target.get('target_12m', '-'),
            'upside': eq_target.get('upside', '-'),
            'pe_actual': pe_str,
            'pe_historia': 'N/D',
            'narrativa': (
                f"Japón cotiza a {pe_str} P/E. "
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + (self._clean_rationale(jp_council_view.get('rationale', ''), pe_value=pe) + '. '
                   if jp_council_view.get('rationale') else '')
            ),
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'temas_clave': [],
            'catalizadores': [],
            'riesgos': []
        }

    def _generate_chile_view(self) -> Dict[str, Any]:
        """Genera view de Chile con datos reales (ECH ETF + BCCh IPSA + USD/CLP + cobre)."""
        v = self._val('chile') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')
        div_y = v.get('dividend_yield')
        # Dynamic PE history: use average of real picks if available, else None
        chile_picks_data = self.market_data.get('chile_picks', [])
        real_pes = [p.get('pe_trailing') or p.get('pe_forward')
                    for p in chile_picks_data
                    if (p.get('pe_trailing') or p.get('pe_forward')) is not None]
        pe_historia = round(sum(real_pes) / len(real_pes), 1) if real_pes else None

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        # BCCh real data: IPSA level, USD/CLP, cobre
        ipsa_level = self._bcch_val('ipsa')
        ipsa_ytd = self._bcch_ret('ipsa', 'ytd')
        ipsa_1m = self._bcch_ret('ipsa', '1m')
        ipsa_3m = self._bcch_ret('ipsa', '3m')
        usdclp = self._bcch_val('usd_clp')
        usdclp_1m = self._bcch_ret('usd_clp', '1m')
        usdclp_ytd = self._bcch_ret('usd_clp', 'ytd')
        copper = self._bcch_val('copper')
        copper_ytd = self._bcch_ret('copper', 'ytd')
        lithium = self._bcch_val('lithium')
        lithium_ytd = self._bcch_ret('lithium', 'ytd')

        # DF intelligence para enriquecer narrativa
        df = self.market_data.get('df_intelligence', {}) if self._has_data() else {}
        df_kw = df.get('keywords', {})
        ipsa_mentions = df_kw.get('ipsa_mentions', 0)
        cobre_mentions = df_kw.get('cobre_mentions', 0)

        # Narrativa dinámica con datos reales
        parts = []
        if ipsa_level:
            parts.append(f"El IPSA cotiza en {ipsa_level:,.0f} puntos")
            if ipsa_ytd is not None:
                parts.append(f" ({ipsa_ytd:+.1f}% YTD)")
            parts.append(". ")
        if pe and pe_historia:
            parts.append(f"ECH ETF a {pe_str} P/E, {((pe/pe_historia)-1)*100:+.0f}% vs promedio histórico de {pe_historia}x. ")
        elif pe:
            parts.append(f"ECH ETF a {pe_str} P/E. ")
        if ret_ytd is not None and ipsa_ytd is not None:
            parts.append(f"ECH (USD) {ret_ytd:+.1f}% YTD vs IPSA (CLP) {ipsa_ytd:+.1f}% — diferencia por FX. ")
        elif ret_ytd is not None:
            parts.append(f"Retorno ECH YTD: {ret_ytd:+.1f}%. ")
        if div_y:
            parts.append(f"Dividend yield: {div_y:.1f}%. ")
        if copper is not None and copper_ytd is not None:
            parts.append(f"Cobre a {copper:.2f} USD/lb ({copper_ytd:+.1f}% YTD) apoya tesis de commodities. ")
        if lithium is not None and lithium_ytd is not None:
            parts.append(f"Litio a {lithium:.0f} USD/ton ({lithium_ytd:+.1f}% YTD). ")

        # Agregar contexto de DF si disponible
        if ipsa_mentions > 3 or cobre_mentions > 3:
            parts.append(f"Alta visibilidad en prensa local ({ipsa_mentions} menciones IPSA, {cobre_mentions} menciones cobre). ")

        # Fallback: use council equity view for Chile
        if not parts:
            ev = (self.parser.get_equity_views() if self.parser else {}) or {}
            chile_ev = ev.get('chile', {})
            if chile_ev.get('view'):
                narrativa = f"Chile: {chile_ev['view']}."
                if chile_ev.get('rationale'):
                    narrativa += f" {chile_ev['rationale']}"
            else:
                narrativa = ""
        else:
            narrativa = ''.join(parts)

        # Council enrichment
        if self._has_council():
            rv = self._panel('rv')
            macro = self._panel('macro')
            source = rv + '\n' + macro
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['chile', 'ipsa', 'bcch', 'tpm']):
                        narrativa = self._md_to_html(self._truncate_at_sentence(p, 500))
                        break

        # USD/CLP sensitivity con datos reales
        usdclp_str = f"${usdclp:,.0f}" if usdclp else 'N/D'
        usdclp_chg = f" ({usdclp_1m:+.1f}% 1M, {usdclp_ytd:+.1f}% YTD)" if usdclp_1m is not None and usdclp_ytd is not None else ''

        # Get Chile view from council parser
        equity_views = self.parser.get_equity_views() or {}
        cl_council_view = equity_views.get('chile', {}) if equity_views else {}

        eq_target = self._get_equity_target('ipsa')

        return {
            'mercado': 'Chile',
            'indice': 'IPSA',
            'view': cl_council_view.get('view', 'N') if cl_council_view else 'N',
            'cambio': '=',
            'target_12m': eq_target.get('target_12m', '-'),
            'upside': eq_target.get('upside', '-'),
            'nivel_actual': f"{ipsa_level:,.0f}" if ipsa_level else (f"{price:,.0f}" if price else 'N/D'),
            'ipsa_retornos': {
                'ytd': self._fmt(ipsa_ytd, '%', prefix='+' if (ipsa_ytd or 0) >= 0 else '') if ipsa_ytd is not None else 'N/D',
                '1m': self._fmt(ipsa_1m, '%', prefix='+' if (ipsa_1m or 0) >= 0 else '') if ipsa_1m is not None else 'N/D',
                '3m': self._fmt(ipsa_3m, '%', prefix='+' if (ipsa_3m or 0) >= 0 else '') if ipsa_3m is not None else 'N/D',
            },
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x' if pe_historia else 'N/D',
            'narrativa': narrativa,
            'commodities_context': {
                'cobre': f"{copper:.2f} USD/lb ({copper_ytd:+.1f}% YTD)" if copper and copper_ytd is not None else 'N/D',
                'litio': f"{lithium:.0f} USD/ton ({lithium_ytd:+.1f}% YTD)" if lithium and lithium_ytd is not None else 'N/D',
            },
            'sectores_preferidos': [],
            'sectores_evitar': [],
            'top_picks': self._build_chile_top_picks(chile_picks_data),
            'catalizadores': [],
            'riesgos': [],
            'usd_clp_sensitivity': {
                'titulo': 'Sensibilidad a USD/CLP',
                'nivel_actual': usdclp_str + usdclp_chg,
                'escenarios': [
                    {'escenario': 'CLP fuerte (<$820)', 'impacto_ipsa': '-3%', 'impacto_earnings': '-5%', 'comentario': 'Negativo para exportadores'},
                    {'escenario': f'Neutral (~${usdclp:,.0f})' if usdclp else 'Neutral', 'impacto_ipsa': '0%', 'impacto_earnings': '0%', 'comentario': 'Base case'},
                    {'escenario': 'CLP debil (>$900)', 'impacto_ipsa': '+2%', 'impacto_earnings': '+4%', 'comentario': 'Positivo para exportadores'}
                ],
                'beta_ipsa_usdclp': 'N/D',
                'comentario': 'IPSA tiene correlacion positiva con depreciacion CLP por peso exportadores'
            }
        }

    def _build_chile_top_picks(self, chile_picks_data: list) -> list:
        """Construye top picks de Chile con datos reales o fallback hardcoded."""
        # Rationale por ticker
        rationale_map = {
            'BCH': 'Mejor calidad crediticia, dividend',
            'BSAC': 'Banca retail líder, escala',
            'SQM': 'Litio + cobre, commodities',
            'LTM': 'Recovery aéreo, restructuración',
            'CCU': 'Consumo defensivo, dividend',
        }

        if chile_picks_data:
            top_picks = []
            for p in chile_picks_data:
                pe = p.get('pe_trailing') or p.get('pe_forward')
                div_y = p.get('dividend_yield')
                top_picks.append({
                    'empresa': p['name'],
                    'ticker': p['ticker'],
                    'pe': f"{pe:.1f}x" if pe and pe < 80 else 'N/D',
                    'div_yield': f"{div_y:.1f}%" if div_y else 'N/D',
                    'rationale': rationale_map.get(p['ticker'], 'N/D'),
                })
            return top_picks

        # No real data available — return empty (no fabricated values)
        return []

    # =========================================================================
    # SECCION 7: FLUJOS Y POSICIONAMIENTO
    # =========================================================================

    def generate_flows_positioning(self) -> Dict[str, Any]:
        """Genera seccion de flujos y posicionamiento."""

        return {
            'flujos_regionales': self._generate_regional_flows(),
            'posicionamiento': self._generate_positioning(),
            'technicals': self._generate_technicals()
        }

    def _generate_regional_flows(self) -> Dict[str, Any]:
        """Genera performance regional con retornos reales (flujos requieren EPFR, no disponible)."""

        # Nota: flujos reales requieren EPFR (propietario). Mostramos retornos reales como proxy.
        # BCCh indices mapping for cross-reference with ETF returns
        bcch_map = {
            'us': 'sp500',
            'europe': 'eurostoxx',
            'japan': 'nikkei',
            'chile': 'ipsa',
        }

        regions = [
            ('US Equity', 'us', 'SPY'),
            ('Europe Equity', 'europe', 'EFA'),
            ('EM Equity', 'em', 'EEM'),
            ('Japan Equity', 'japan', 'EWJ'),
            ('Chile Equity (CLP)', 'chile', 'IPSA'),
            ('Chile Equity (USD)', 'chile_usd', 'ECH'),
            ('LatAm Equity', 'latam', 'ILF'),
        ]

        datos = []
        for name, key, ticker in regions:
            # For Chile CLP, use BCCh IPSA directly
            if key == 'chile':
                ipsa_data = self._bcch().get('ipsa', {})
                ret = ipsa_data.get('returns', {}) if isinstance(ipsa_data, dict) else {}
                ytd = ret.get('ytd')
                m1 = ret.get('1m')
                m3 = ret.get('3m')
            elif key == 'chile_usd':
                v = self._val('chile') if self._has_data() else {}
                ret = v.get('returns', {})
                ytd = ret.get('ytd')
                m1 = ret.get('1m')
                m3 = ret.get('3m')
            else:
                v = self._val(key) if self._has_data() else {}
                ret = v.get('returns', {})
                ytd = ret.get('ytd')
                m1 = ret.get('1m')
                m3 = ret.get('3m')

            # BCCh cross-reference for local index returns
            bcch_key = bcch_map.get(key)
            bcch_ytd = self._bcch_ret(bcch_key, 'ytd') if bcch_key and key != 'chile' else None

            if ytd is not None:
                if ytd > 5:
                    tendencia = 'Momentum positivo'
                elif ytd > 0:
                    tendencia = 'Levemente positivo'
                elif ytd > -5:
                    tendencia = 'Lateral'
                else:
                    tendencia = 'Bajo presion'
            else:
                tendencia = 'N/D'

            entry = {
                'region': name,
                'ticker': ticker,
                'retorno_ytd': self._fmt(ytd, '%', prefix='+' if (ytd or 0) >= 0 else '') if ytd is not None else 'N/D',
                'retorno_1m': self._fmt(m1, '%', prefix='+' if (m1 or 0) >= 0 else '') if m1 is not None else 'N/D',
                'retorno_3m': self._fmt(m3, '%', prefix='+' if (m3 or 0) >= 0 else '') if m3 is not None else 'N/D',
                'tendencia': tendencia,
            }
            # Add BCCh local index cross-ref (shows local currency return)
            if bcch_ytd is not None:
                entry['indice_local_ytd'] = self._fmt(bcch_ytd, '%', prefix='+' if bcch_ytd >= 0 else '')

            datos.append(entry)

        # Narrativa dinámica
        with_data = [d for d in datos if d['retorno_ytd'] != 'N/D']
        if with_data:
            best = max(with_data, key=lambda x: float(x['retorno_ytd'].replace('%', '').replace('+', '')))
            worst = min(with_data, key=lambda x: float(x['retorno_ytd'].replace('%', '').replace('+', '')))
            narrativa = (
                f"{best['region']} lidera con retorno YTD de {best['retorno_ytd']}, "
                f"mientras {worst['region']} rezaga con {worst['retorno_ytd']}. "
                "Nota: Datos de flujos reales requieren suscripcion EPFR (no disponible)."
            )
        else:
            narrativa = "Sin datos de retornos regionales. Ejecutar equity_data_collector."

        return {
            'narrativa': narrativa,
            'datos': datos,
            'nota': 'Retornos ETF reales (yfinance). Flujos requieren EPFR (propietario).',
        }

    def _generate_positioning(self) -> Dict[str, Any]:
        """Genera posicionamiento usando breadth, credit spreads y risk data reales."""

        bd = self._breadth()
        has_breadth = bd and 'error' not in bd
        cd = self._credit_data()
        has_credit = cd and 'error' not in cd
        rd = self._risk_data()
        has_risk = rd and 'error' not in rd

        indicadores = []

        # Credit spreads como indicador de riesgo
        if has_credit:
            ig = cd.get('ig_spread')
            hy = cd.get('hy_spread')
            ig_pct = cd.get('ig_percentile')
            hy_pct = cd.get('hy_percentile')
            if ig is not None:
                comentario = f'Percentil {ig_pct:.0f}%' if ig_pct is not None else ''
                indicadores.append({'indicador': 'IG Spread (Investment Grade — diferencial bonos grado de inversión)', 'valor': f'{ig:.0f}bp', 'comentario': comentario})
            if hy is not None:
                comentario = f'Percentil {hy_pct:.0f}%' if hy_pct is not None else ''
                indicadores.append({'indicador': 'HY Spread (High Yield — diferencial bonos alto rendimiento)', 'valor': f'{hy:.0f}bp', 'comentario': comentario})

        # Risk metrics
        if has_risk:
            var95 = rd.get('var_95_daily')
            curr_dd = rd.get('current_drawdown')
            if var95 is not None:
                indicadores.append({'indicador': 'VaR 95% diario (pérdida máxima esperada con 95% de confianza)', 'valor': f'{var95:.2f}%', 'comentario': 'Portfolio equity diversificado'})
            if curr_dd is not None:
                indicadores.append({'indicador': 'Drawdown actual (caída desde el máximo reciente)', 'valor': f'{curr_dd:.1f}%', 'comentario': 'Desde peak'})

        # Breadth
        if has_breadth:
            summary = bd.get('summary', {})
            signal = summary.get('signal', 'N/D')
            cyc_def = bd.get('cyclical_defensive', {})
            indicadores.append({'indicador': 'Breadth Signal (Amplitud de Mercado — % de acciones en tendencia alcista)', 'valor': signal, 'comentario': 'Módulo Amplitud de Mercado'})
            if isinstance(cyc_def, dict) and cyc_def.get('ratio'):
                indicadores.append({'indicador': 'Ciclico/Defensivo', 'valor': f"{cyc_def['ratio']:.2f}", 'comentario': cyc_def.get('signal', '')})

        # Si no hay datos reales, incluir nota
        if not indicadores:
            indicadores = [
                {'indicador': 'N/D', 'valor': '-', 'comentario': 'Sin datos de posicionamiento. Ejecutar equity_data_collector.'},
            ]

        # Narrativa dinámica
        parts = []
        if has_credit:
            hy_sig = cd.get('hy_signal', '')
            if hy_sig:
                parts.append(f"Los spreads de crédito HY ({cd.get('hy_spread', 0):.0f}bp) señalan {hy_sig.lower()}. ")
        if has_breadth:
            parts.append(f"El breadth de mercado muestra señal {bd.get('summary', {}).get('signal', 'N/D')}. ")
        if not parts:
            parts.append("Datos de posicionamiento limitados. Se requieren fuentes propietarias (EPFR, AAII) para análisis completo. ")

        return {
            'narrativa': ''.join(parts),
            'indicadores': indicadores,
        }

    def _generate_technicals(self) -> Dict[str, Any]:
        """Genera analisis tecnico usando datos reales de risk y valuations."""

        rd = self._risk_data()
        has_risk = rd and 'error' not in rd

        # Precio actual del S&P 500
        us_v = self._val('us') if self._has_data() else {}
        spy_price = us_v.get('price')
        spy_high = us_v.get('fifty_two_week_high')
        spy_low = us_v.get('fifty_two_week_low')

        # Risk metrics reales
        var_95 = rd.get('var_95_daily') if has_risk else None
        var_99 = rd.get('var_99_daily') if has_risk else None
        max_dd = rd.get('max_drawdown') if has_risk else None
        curr_dd = rd.get('current_drawdown') if has_risk else None
        div_score = rd.get('diversification_score') if has_risk else None

        # Tendencia simple: precio vs rango 52 semanas
        if spy_price and spy_high and spy_low:
            rango = spy_high - spy_low
            pos_en_rango = ((spy_price - spy_low) / rango * 100) if rango > 0 else 50
            if pos_en_rango > 80:
                tendencia = 'Alcista fuerte'
            elif pos_en_rango > 50:
                tendencia = 'Alcista'
            elif pos_en_rango > 30:
                tendencia = 'Lateral'
            else:
                tendencia = 'Bajista'
        else:
            pos_en_rango = None
            tendencia = 'N/D'

        # VIX real
        vix_data = rd.get('vix', {}) if has_risk else {}
        vix_current = vix_data.get('current')
        vix_avg = vix_data.get('avg_1y')

        if vix_current is not None:
            if vix_current < 15:
                vix_comment = 'Bajo — posible complacencia'
            elif vix_current < 20:
                vix_comment = 'Normal'
            elif vix_current < 30:
                vix_comment = 'Elevado — cautela'
            else:
                vix_comment = 'Muy alto — estres de mercado'
        else:
            vix_comment = 'N/D'

        # Breadth data
        bd = self._breadth()
        breadth_signal = bd.get('summary', {}).get('signal', 'N/D') if bd and 'error' not in bd else 'N/D'
        risk_appetite = bd.get('risk_appetite', {})

        return {
            'sp500': {
                'nivel': f"{spy_price:,.0f}" if spy_price else 'N/D',
                '52w_high': f"{spy_high:,.0f}" if spy_high else 'N/D',
                '52w_low': f"{spy_low:,.0f}" if spy_low else 'N/D',
                'pos_en_rango': f"{pos_en_rango:.0f}%" if pos_en_rango is not None else 'N/D',
                'tendencia': tendencia,
            },
            'vix': {
                'nivel': f"{vix_current:.1f}" if vix_current is not None else 'N/D',
                'promedio_1y': f"{vix_avg:.1f}" if vix_avg is not None else 'N/D',
                'high_1y': f"{vix_data.get('high_1y', 0):.1f}" if vix_data.get('high_1y') else 'N/D',
                'low_1y': f"{vix_data.get('low_1y', 0):.1f}" if vix_data.get('low_1y') else 'N/D',
                'comentario': vix_comment,
            },
            'risk_metrics': {
                'var_95_daily': f"{var_95:.2f}%" if var_95 is not None else 'N/D',
                'var_99_daily': f"{var_99:.2f}%" if var_99 is not None else 'N/D',
                'max_drawdown': f"{max_dd:.1f}%" if max_dd is not None else 'N/D',
                'current_drawdown': f"{curr_dd:.1f}%" if curr_dd is not None else 'N/D',
                'diversification': f"{div_score:.2f}" if div_score is not None else 'N/D',
            },
            'breadth': {
                'signal': breadth_signal,
                'risk_appetite': risk_appetite.get('signal', 'N/D') if isinstance(risk_appetite, dict) else 'N/D',
                'comentario': f'Breadth: {breadth_signal}' if breadth_signal != 'N/D' else 'Sin datos de breadth',
            },
        }

    # =========================================================================
    # SECCION 8: RIESGOS Y CATALIZADORES
    # =========================================================================

    def generate_market_scenarios(self) -> Dict[str, Any]:
        """Genera escenarios bull/base/bear con precios reales actuales."""

        # Precios reales de cada mercado
        us_v = self._val('us') if self._has_data() else {}
        eu_v = self._val('europe') if self._has_data() else {}
        em_v = self._val('em') if self._has_data() else {}
        ch_v = self._val('chile') if self._has_data() else {}

        def _build_scenario(name, val_data, bull_mult, base_mult, bear_mult,
                            bull_prob, base_prob, bear_prob,
                            bull_driver, base_driver, bear_driver):
            price = val_data.get('price')
            if price:
                bull_t = price * bull_mult
                base_t = price * base_mult
                bear_t = price * bear_mult
                ev = bull_prob * bull_t + base_prob * base_t + bear_prob * bear_t
                upside = ((ev / price) - 1) * 100
                return {
                    'mercado': name,
                    'nivel_actual': f"{price:,.0f}",
                    'escenarios': {
                        'bull': {'target': f"{bull_t:,.0f}", 'prob': f"{bull_prob*100:.0f}%", 'driver': bull_driver},
                        'base': {'target': f"{base_t:,.0f}", 'prob': f"{base_prob*100:.0f}%", 'driver': base_driver},
                        'bear': {'target': f"{bear_t:,.0f}", 'prob': f"{bear_prob*100:.0f}%", 'driver': bear_driver},
                    },
                    'expected_value': f"{ev:,.0f}",
                    'upside_ev': f"{upside:+.1f}%",
                }
            else:
                return {
                    'mercado': name,
                    'nivel_actual': 'N/D',
                    'escenarios': {
                        'bull': {'target': 'N/D', 'prob': f"{bull_prob*100:.0f}%", 'driver': bull_driver},
                        'base': {'target': 'N/D', 'prob': f"{base_prob*100:.0f}%", 'driver': base_driver},
                        'bear': {'target': 'N/D', 'prob': f"{bear_prob*100:.0f}%", 'driver': bear_driver},
                    },
                    'expected_value': 'N/D',
                    'upside_ev': 'N/D',
                }

        mercados = [
            _build_scenario('S&P 500', us_v, 1.13, 1.06, 0.87,
                          0.25, 0.55, 0.20,
                          'AI boom, soft landing perfecto, multiples expand',
                          'Earnings +10%, multiples estables',
                          'Recesion, earnings -15%, P/E comprime'),
            _build_scenario('IPSA (ECH)', ch_v, 1.23, 1.15, 0.85,
                          0.30, 0.50, 0.20,
                          'Cobre fuerte, tasas bajan 100bp, consumo acelera',
                          'Earnings +12%, P/E normaliza',
                          'Cobre colapsa, crisis China, risk-off global'),
            _build_scenario('EAFE (Europa)', eu_v, 1.16, 1.09, 0.84,
                          0.25, 0.55, 0.20,
                          'BCE recorta agresivo, China estabiliza',
                          'Crecimiento moderado, earnings +8%',
                          'Crisis energetica, recesion Alemania'),
            _build_scenario('MSCI EM', em_v, 1.20, 1.10, 0.85,
                          0.25, 0.50, 0.25,
                          'China rally, USD debil, commodities up',
                          'Earnings +10%, flujos neutrales',
                          'China hard landing, trade war, USD surge'),
        ]

        # Implicancias dinámicas
        with_ev = [m for m in mercados if m['upside_ev'] != 'N/D']
        if with_ev:
            best = max(with_ev, key=lambda x: float(x['upside_ev'].replace('%', '').replace('+', '')))
            implicancias = (
                f"Los escenarios ponderados sugieren upside moderado en la mayoría de mercados. "
                f"{best['mercado']} ofrece el mejor risk-reward con EV de {best['expected_value']} "
                f"({best['upside_ev']} vs actual)."
            )
        else:
            implicancias = "Sin datos de precios para calcular escenarios ponderados."

        return {
            'titulo': 'Escenarios de Mercado',
            'por_mercado': mercados,
            'implicancias': implicancias,
        }

    def generate_correlation_matrix(self) -> Dict[str, Any]:
        """Genera matriz de correlación usando datos reales de risk/metrics."""

        rd = self._risk_data()
        corr = rd.get('correlation_matrix', {}) if rd and 'error' not in rd else {}

        # Mapeo de tickers a nombres display
        ticker_names = {
            'SPY': 'S&P 500', 'EFA': 'EAFE', 'EEM': 'MSCI EM',
            'EWJ': 'Topix', 'ECH': 'IPSA', 'EWZ': 'Brasil',
            'MCHI': 'China', 'GLD': 'Oro', 'TLT': 'Bonos US', 'HYG': 'High Yield',
        }

        if corr:
            # Construir matriz desde datos reales
            tickers_available = [t for t in ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH', 'MCHI'] if t in corr]
            names = [ticker_names.get(t, t) for t in tickers_available]

            matrix_data = []
            for t1 in tickers_available:
                row = []
                for t2 in tickers_available:
                    row.append(corr.get(t1, {}).get(t2, 0))
                matrix_data.append(row)

            # Observaciones de pares interesantes
            observaciones = []
            pairs = [
                ('SPY', 'EFA', 'S&P 500 / EAFE'),
                ('SPY', 'ECH', 'S&P 500 / IPSA'),
                ('ECH', 'EEM', 'IPSA / MSCI EM'),
                ('EWJ', 'MCHI', 'Topix / China'),
                ('MCHI', 'EEM', 'China / MSCI EM'),
            ]
            for t1, t2, label in pairs:
                if t1 in corr and t2 in corr.get(t1, {}):
                    c = corr[t1][t2]
                    if c > 0.7:
                        com = 'Alta correlación - diversificación limitada'
                    elif c > 0.5:
                        com = 'Correlación moderada'
                    elif c > 0.3:
                        com = 'Baja correlación - beneficio diversificación'
                    else:
                        com = 'Muy baja correlación - alta diversificación'
                    observaciones.append({'par': label, 'corr': f'{c:.2f}', 'comentario': com})

            # Promedio de correlaciones off-diagonal
            all_corrs = []
            for t1 in tickers_available:
                for t2 in tickers_available:
                    if t1 != t2:
                        all_corrs.append(corr.get(t1, {}).get(t2, 0))
            avg_corr = sum(all_corrs) / len(all_corrs) if all_corrs else 0

            period = rd.get('correlation_period', 'últimos 6 meses')

            return {
                'titulo': f'Matriz de Correlación ({period})',
                'matriz': {'mercados': names, 'correlaciones': matrix_data},
                'observaciones': observaciones,
                'tendencia': {
                    'actual': f'{avg_corr:.2f} promedio',
                    'comentario': 'Correlaciones elevadas limitan diversificación' if avg_corr > 0.5 else 'Correlaciones moderadas permiten diversificación',
                },
                'implicancias_portfolio': (
                    f"La correlación promedio entre mercados es {avg_corr:.2f}. "
                    + ("Chile (IPSA) y Japón ofrecen las correlaciones más bajas con US, "
                       "reforzando el caso de allocation." if corr.get('SPY', {}).get('ECH', 1) < 0.6 else
                       "Las correlaciones están elevadas, limitando beneficios de diversificación.")
                ),
                'source': 'Datos reales (yfinance, últimos 6 meses)',
            }
        else:
            # Sin datos reales — devolver estructura vacía con flag
            return {
                'titulo': 'Matriz de Correlación (sin datos)',
                'matriz': {'mercados': [], 'correlaciones': []},
                'observaciones': [],
                'tendencia': {'actual': 'N/D', 'comentario': 'Sin datos de correlación disponibles'},
                'implicancias_portfolio': 'Datos de correlación no disponibles. Se requiere ejecutar equity_data_collector.',
            }

    def generate_risks_catalysts(self) -> Dict[str, Any]:
        """Genera seccion de riesgos y catalizadores."""

        return {
            'top_risks': self._generate_equity_risks(),
            'catalizadores_positivos': self._generate_positive_catalysts(),
            'calendario': self._generate_event_calendar()
        }

    def _generate_equity_risks(self) -> List[Dict[str, Any]]:
        """Genera top riesgos para equity via Claude + datos de credit/risk."""
        import json as _json
        from narrative_engine import generate_narrative

        cd = self._credit_data()
        has_credit = cd and 'error' not in cd
        rd = self._risk_data()
        has_risk = rd and 'error' not in rd

        # Quantitative context
        quant_parts = []
        if has_credit:
            hy = cd.get('hy_spread')
            hy_pct = cd.get('hy_percentile')
            ig = cd.get('ig_spread')
            if hy is not None:
                quant_parts.append(f"HY spread: {hy:.0f}bp" + (f" (percentil {hy_pct:.0f}%)" if hy_pct else ""))
            if ig is not None:
                quant_parts.append(f"IG spread: {ig:.0f}bp")
        if has_risk:
            var95 = rd.get('var_95_daily')
            if var95 is not None:
                quant_parts.append(f"VaR 95%: {var95:.2f}% diario")

        riesgo_panel = self._panel('riesgo') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        if riesgo_panel or final:
            council_ctx = f"RISK PANEL:\n{riesgo_panel[:2000]}\n\nFINAL REC:\n{final[:1000]}"
            quant_ctx = " | ".join(quant_parts) if quant_parts else ""

            result = generate_narrative(
                section_name="rv_equity_risks",
                prompt=(
                    "Genera exactamente 3 top riesgos para renta variable basados en el council. "
                    "Devuelve un JSON array donde cada elemento tiene: "
                    '{"riesgo": "nombre corto", "probabilidad": "XX%", "impacto": "Alto/Muy Alto/Medio", '
                    '"descripcion": "1-2 oraciones", "sectores_afectados": ["sector1", "sector2"], '
                    '"hedge": "string corto con cobertura sugerida"}. '
                    "Usa riesgos que el council realmente identifica. NO inventes probabilidades — "
                    "usa las del council o estima conservadoramente."
                    "\n\nPara cada riesgo, desarrolla: escenario + probabilidad estimada, "
                    "hedge sugerido con costo, señal temprana medible que nos alertaría."
                ),
                council_context=council_ctx,
                quant_context=quant_ctx,
                company_name=self.company_name,
                max_tokens=800,
                temperature=0.2,
            )
            if result:
                try:
                    cleaned = result.strip()
                    if cleaned.startswith('```'):
                        cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                        if cleaned.endswith('```'):
                            cleaned = cleaned[:-3]
                        cleaned = cleaned.strip()
                    risks = _json.loads(cleaned)
                    if isinstance(risks, list) and len(risks) >= 2:
                        return risks
                except (_json.JSONDecodeError, KeyError):
                    pass

        # Minimal fallback
        return [
            {'riesgo': 'Riesgo macro', 'probabilidad': 'N/D', 'impacto': 'Alto',
             'descripcion': 'Ver seccion de riesgos del council para detalle.',
             'sectores_afectados': [], 'hedge': 'Diversificacion'},
        ]

    def _generate_positive_catalysts(self) -> List[str]:
        """Genera catalizadores positivos via Claude."""
        from narrative_engine import generate_narrative

        rv = self._panel('rv') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        if rv or final:
            council_ctx = f"RV PANEL:\n{rv[:1500]}\n\nFINAL:\n{final[:1000]}"
            result = generate_narrative(
                section_name="rv_catalysts",
                prompt=(
                    "Genera exactamente 4-5 catalizadores positivos para renta variable "
                    "basados en lo que discute el council. Cada catalizador en una linea, "
                    "formato: 'Catalizador - impacto esperado'. Sin bullets ni numeracion."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=500,
            )
            if result:
                lines = [l.strip() for l in result.split('\n') if l.strip()]
                if len(lines) >= 3:
                    return lines

        return ["Ver analisis del council para catalizadores especificos"]

    def _generate_event_calendar(self) -> List[Dict[str, Any]]:
        """Genera calendario de eventos desde council data."""
        from narrative_engine import generate_narrative

        # Build month abbreviation for calendar dates
        month_abbr = self.month_name[:3]

        macro = self._panel('macro') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        if macro or final:
            council_ctx = f"MACRO:\n{macro[:2000]}\n\nFINAL:\n{final[:1000]}"
            result = generate_narrative(
                section_name="rv_event_calendar",
                prompt=(
                    f"Genera un calendario de 5-7 eventos macro clave para el próximo mes "
                    f"({self.month_name} {self.year}) relevantes para renta variable. "
                    "Devuelve SOLO un JSON array (sin texto adicional): "
                    "[{\"fecha\": \"DD Mon\", \"evento\": \"nombre\", "
                    "\"relevancia\": \"Alta|Media|Baja\", \"impacto\": \"descripción breve\"}]. "
                    "Incluye: reuniones de bancos centrales (Fed, BCE, BCCh), datos de empleo, "
                    "inflación, GDP, earnings season, etc. Usa fechas reales del calendario "
                    "económico si las conoces, o indica 'semana X' si no. SOLO JSON."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=600,
                temperature=0.2,
            )
            if result:
                parsed = self._clean_json(result)
                if isinstance(parsed, list) and len(parsed) >= 3:
                    return parsed

        # Fallback: basic economic calendar with known recurring events
        return [
            {'fecha': f'Semana 1 {month_abbr}', 'evento': 'ISM Manufacturing PMI (USA)',
             'relevancia': 'Alta', 'impacto': 'Indicador adelantado de actividad industrial'},
            {'fecha': f'Semana 1 {month_abbr}', 'evento': 'Non-Farm Payrolls (NFP)',
             'relevancia': 'Alta', 'impacto': 'Empleo USA - clave para politica Fed'},
            {'fecha': f'Semana 2 {month_abbr}', 'evento': 'CPI USA (Inflacion)',
             'relevancia': 'Alta', 'impacto': 'Dato clave para expectativas de tasas'},
            {'fecha': f'Semana 3 {month_abbr}', 'evento': 'Reunion FOMC (Fed)',
             'relevancia': 'Alta', 'impacto': 'Decision de tasa de politica monetaria'},
            {'fecha': f'Semana 3 {month_abbr}', 'evento': 'Reunion BCE',
             'relevancia': 'Media', 'impacto': 'Politica monetaria Eurozona'},
            {'fecha': f'Semana 4 {month_abbr}', 'evento': 'PIB USA (GDP)',
             'relevancia': 'Media', 'impacto': 'Crecimiento economico trimestral'},
        ]

    # =========================================================================
    # SECCION 9: RESUMEN POSICIONAMIENTO
    # =========================================================================

    def generate_positioning_summary(self) -> Dict[str, Any]:
        """Genera resumen final de posicionamiento via Claude."""
        import json as _json
        from narrative_engine import generate_narrative

        rv = self._panel('rv') if self._has_council() else ''
        final = self._final() if self._has_council() else ''

        tabla_final = []
        mensaje_clave = ''

        # Build authoritative views string from parser (source of truth for consistency)
        equity_views = self.parser.get_equity_views() or {}
        views_str = ''
        if equity_views:
            view_lines = []
            for region, data in equity_views.items():
                v = data.get('view', 'N') if isinstance(data, dict) else 'N'
                view_lines.append(f"{region}: {v}")
            views_str = "VIEWS DEFINITIVOS (usar estos, no inventar): " + ", ".join(view_lines) + ". "

        if rv or final:
            council_ctx = f"RV PANEL:\n{rv[:2000]}\n\nFINAL REC:\n{final[:2000]}"

            # Generate positioning table
            tabla_raw = generate_narrative(
                section_name="rv_positioning_table",
                prompt=(
                    "Genera una tabla de posicionamiento en renta variable como JSON array. "
                    "Cada fila: {\"categoria\": \"string\", \"recomendacion\": \"string\"}. "
                    "Incluir: Equity Global (OW/N/UW), Region Preferida, Region a evitar/neutral, "
                    "Sectores OW, Sectores UW, Style tilt, Factor tilt, Size preference. "
                    + views_str +
                    "IMPORTANTE: Usa exactamente los views regionales indicados arriba (OW/N/UW). "
                    "No contradigas los views — si una region es UW, no la marques como OW. "
                    "Basa las recomendaciones en lo que dice el council."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=500,
                temperature=0.1,
            )
            if tabla_raw:
                parsed = self._clean_json(tabla_raw)
                if isinstance(parsed, list) and len(parsed) >= 3:
                    tabla_final = parsed

            # Generate key message
            mensaje_clave = generate_narrative(
                section_name="rv_mensaje_clave",
                prompt=(
                    "Escribe 2-3 oraciones resumiendo el posicionamiento en renta variable: "
                    "postura general, principales preferencias, y principal riesgo a monitorear. "
                    + views_str +
                    "IMPORTANTE: Usa exactamente los views indicados. Si una region es UW, "
                    "NO la describas como OW estrategico ni positiva. "
                    "Usa datos del council. Maximo 60 palabras."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=400,
            )

        # Fallbacks
        if not tabla_final:
            tabla_final = [
                {'categoria': 'Equity Global', 'recomendacion': 'Ver analisis detallado'},
                {'categoria': 'Posicionamiento', 'recomendacion': 'Basado en council del mes'},
            ]
        if not mensaje_clave:
            mensaje_clave = f'Ver analisis detallado de {self.month_name} {self.year} para posicionamiento.'

        return {'tabla_final': tabla_final, 'mensaje_clave': mensaje_clave}

    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================

    # =========================================================================
    # FORECAST ENGINE — EQUITY TARGETS
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

    def generate_equity_targets(self) -> Dict[str, Any]:
        """Genera sección de targets 12M por índice desde el Forecast Engine.
        Incluye señales OW/N/UW, retorno esperado y desglose por modelo."""

        targets = self._fc('equity_targets')
        if not targets or not isinstance(targets, dict):
            return {
                'titulo': 'Price Targets 12M',
                'available': False,
                'nota': 'Forecast Engine no disponible. Targets no generados.',
            }

        rows = []
        label_map = {
            'sp500': 'S&P 500', 'eurostoxx': 'EuroStoxx 50', 'nikkei': 'Nikkei 225',
            'csi300': 'CSI 300', 'ipsa': 'IPSA', 'bovespa': 'Bovespa',
        }

        for idx_key, label in label_map.items():
            data = targets.get(idx_key, {})
            if isinstance(data, dict) and 'error' not in data:
                rows.append({
                    'indice': label,
                    'precio_actual': data.get('current_price'),
                    'target_12m': data.get('target_12m'),
                    'retorno_esperado': data.get('expected_return_pct'),
                    'signal': data.get('signal', 'N'),
                    'confianza': data.get('confidence', 'LOW'),
                    'rango': data.get('range', []),
                    'modelos_usados': data.get('models_used', 0),
                })

        return {
            'titulo': 'Price Targets 12M — Forecast Engine',
            'available': len(rows) > 0,
            'horizonte': '12 meses',
            'metodologia': '5 modelos ensemble: Earnings Yield + Growth (30%), Fair Value PE (25%), PE Mean-Reversion (20%), Consenso Analistas (15%), Régimen Histórico (10%)',
            'targets': rows,
        }

    def _reconcile_views(self, content: Dict[str, Any]):
        """Compare summary table views vs regional narrative views; log and fix conflicts."""
        table_rows = content.get('resumen_ejecutivo', {}).get('summary_table', [])
        regiones = content.get('regiones', {})

        # Map summary table region names → regional view keys
        region_key_map = {
            'Estados Unidos': 'us',
            'Europa': 'europe',
            'Emergentes': 'em',
            'Japon': 'japan',
            'Chile': 'chile',
        }

        for row in table_rows:
            mercado = row.get('mercado', '')
            rkey = region_key_map.get(mercado)
            if not rkey:
                continue
            regional = regiones.get(rkey, {})
            table_view = row.get('view', 'N')
            narrative_view = regional.get('view', 'N')

            if table_view != narrative_view and narrative_view != 'N':
                logger.warning(
                    f"VIEW CONFLICT: {mercado} — table={table_view}, narrative={narrative_view}. "
                    f"Overriding table to match narrative (parser-sourced)."
                )
                row['view'] = narrative_view

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte RV."""
        # Set up anti-fabrication filter with verified market data
        try:
            from narrative_engine import set_verified_data, clear_verified_data, build_verified_data_rv
            vd = build_verified_data_rv(self.market_data)
            if vd:
                set_verified_data(vd)
        except Exception:
            pass

        content = {
            'metadata': {
                'fecha': self.date.strftime('%Y-%m-%d'),
                'mes': self.month_name,
                'ano': self.year,
                'tipo_reporte': 'RENTA_VARIABLE'
            },
            'resumen_ejecutivo': self.generate_executive_summary(),
            'escenarios_mercado': self.generate_market_scenarios(),
            'matriz_correlacion': self.generate_correlation_matrix(),
            'valorizaciones': self.generate_valuations(),
            'earnings': self.generate_earnings(),
            'sectores': self.generate_sector_analysis(),
            'style_factors': self.generate_style_factors(),
            'regiones': self.generate_regional_views(),
            'flujos_posicionamiento': self.generate_flows_positioning(),
            'riesgos_catalizadores': self.generate_risks_catalysts(),
            'resumen_posicionamiento': self.generate_positioning_summary()
        }

        # Add equity targets from Forecast Engine if available
        eq_targets = self.generate_equity_targets()
        if eq_targets.get('available'):
            content['equity_targets'] = eq_targets

        # Reconciliation: compare summary table views vs regional narrative views
        self._reconcile_views(content)

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
    generator = RVContentGenerator()
    content = generator.generate_all_content()

    import json
    print(json.dumps(content, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

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
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class RVContentGenerator:
    """Generador de contenido narrativo para Reporte de Renta Variable."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None):
        self.council = council_result or {}
        self.market_data = market_data or {}
        self.forecast = forecast_data or {}
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)
        self.year = self.date.year
        self._used_council_paras = set()  # Track used paragraphs to avoid duplication

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
                return self._md_to_html(p[:max_len])
        return None

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
        """Genera postura global de equity."""
        result = {
            'view': 'CONSTRUCTIVO',
            'cambio': '=',
            'conviccion': 'MEDIA-ALTA',
            'driver_principal': 'Earnings resilientes y valuaciones razonables ex-US',
            'narrativa': (
                "Mantenemos una postura constructiva en renta variable global. Los earnings "
                "corporativos muestran resiliencia, con revisiones positivas en la mayoria de regiones. "
                "Si bien las valuaciones en US estan elevadas, el resto del mundo ofrece oportunidades "
                "atractivas. Preferimos Europa, Japon y Chile sobre US en terminos relativos."
            )
        }

        if not self._has_council():
            return result

        rv = self._panel('rv')
        final = self._final()

        # Enrich narrativa from RV panel
        if rv:
            paragraphs = [p.strip() for p in rv.split('\n\n') if len(p.strip()) > 50]
            if paragraphs:
                result['narrativa'] = self._md_to_html(paragraphs[0][:500])

        # Extract view from final recommendation
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
            elif 'constructiv' in text and 'cauteloso' not in text:
                result['view'] = 'CONSTRUCTIVO'
                result['conviccion'] = 'MEDIA-ALTA'
            elif 'neutral' in text:
                result['view'] = 'NEUTRAL'
                result['conviccion'] = 'MEDIA'

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

        defaults = [
            {'mercado': 'Global Equity', 'indice': 'MSCI ACWI', 'view': 'OW', 'cambio': '=', 'driver': 'Earnings resilientes, tasas estables'},
            {'mercado': 'Estados Unidos', 'indice': 'S&P 500', 'view': 'NEUTRAL', 'cambio': '-', 'driver': 'Valuacion elevada, concentracion'},
            {'mercado': 'Europa', 'indice': 'Stoxx 600', 'view': 'OW', 'cambio': '+', 'driver': 'Valuacion atractiva, BCE dovish'},
            {'mercado': 'Emergentes', 'indice': 'MSCI EM', 'view': 'OW', 'cambio': '=', 'driver': 'China estabilizando, valuacion'},
            {'mercado': 'Japon', 'indice': 'Topix', 'view': 'OW', 'cambio': '=', 'driver': 'Reformas corporativas, yen'},
            {'mercado': 'Chile', 'indice': 'IPSA', 'view': 'OW', 'cambio': '+', 'driver': 'Valuacion atractiva, tasas bajando'},
        ]

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
                        # Check for OW/UW/Neutral signals near the keyword
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
        """Genera key calls del mes con datos reales."""
        # Chile call dinámico con datos BCCh + yfinance
        v = self._val('chile') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        ipsa_level = self._bcch_val('ipsa')
        ipsa_ytd = self._bcch_ret('ipsa', 'ytd')

        chile_call = "Chile OW: "
        if pe and ipsa_level:
            chile_call += f"IPSA en {ipsa_level:,.0f} ({pe:.1f}x P/E)"
            if ipsa_ytd is not None:
                chile_call += f", {ipsa_ytd:+.1f}% YTD"
            chile_call += " — valuación atractiva con tasas bajando"
        elif pe:
            chile_call += f"ECH a {pe:.1f}x P/E con upside de 15-20% en 12 meses"
        else:
            chile_call += "IPSA con upside de 15-20% en 12 meses"

        defaults = [
            "Preferimos Europa y Japon sobre US - valuacion relativa mas atractiva",
            "Sectores favoritos: Technology (selectivo), Healthcare, Financials, Materials",
            "Style: Barbell Quality + Value; evitar Growth especulativo",
            chile_call,
            "Principal riesgo: Re-aceleracion de inflacion que fuerce pausa de bancos centrales"
        ]

        if not self._has_council():
            return defaults

        rv = self._panel('rv')
        cio = self._cio()
        source = rv or cio or ''

        # Try to extract bullet points from council
        if source:
            bullets = []
            for line in source.split('\n'):
                line = line.strip()
                if line.startswith(('-', '*', '•')) and len(line) > 20:
                    bullets.append(self._md_to_html(line.lstrip('-*• ').strip()[:200]))
                if len(bullets) >= 5:
                    break
            if len(bullets) >= 3:
                return bullets

        return defaults

    # =========================================================================
    # SECCION 2: VALORIZACIONES GLOBALES
    # =========================================================================

    def generate_valuations(self) -> Dict[str, Any]:
        """Genera seccion de valorizaciones."""

        return {
            'multiples_region': self._generate_regional_multiples(),
            'equity_risk_premium': self._generate_erp(),
            'valuacion_relativa': self._generate_relative_valuation(),
            'narrativa': self._generate_valuation_narrative()
        }

    def _generate_regional_multiples(self) -> List[Dict[str, Any]]:
        """Genera tabla de multiples por region usando datos reales de yfinance."""

        # Mapeo región → (key en valuations, nombre display, PE promedio 10Y estimado)
        region_map = [
            ('us', 'S&P 500', 18.5),
            ('europe', 'Stoxx 600', 14.5),
            ('em', 'MSCI EM', 13.2),
            ('japan', 'Topix', 14.5),
            ('chile', 'IPSA', 12.0),
        ]

        if not self._has_data():
            # Fallback: tabla sin datos reales (se marca explícitamente)
            return [
                {'mercado': name, 'pe_fwd': 'N/D', 'vs_10y_avg': 'N/D',
                 'ev_ebitda': 'N/D', 'pb': 'N/D', 'div_yield': 'N/D',
                 'earning_yield': 'N/D', 'comentario': 'Sin datos de mercado'}
                for _, name, _ in region_map
            ]

        result = []
        for key, name, avg_pe_10y in region_map:
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

            # vs 10Y promedio (usando estimado razonable del promedio histórico)
            if pe:
                vs_avg = ((pe / avg_pe_10y) - 1) * 100
                vs_str = f"+{vs_avg:.0f}%" if vs_avg > 0 else f"{vs_avg:.0f}%"
            else:
                vs_str = 'N/D'

            # Comentario basado en valuación
            if pe and vs_avg:
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
                'ev_ebitda': 'N/D',  # ETFs no reportan EV/EBITDA
                'pb': self._fmt(pb, 'x') if pb else 'N/D',
                'div_yield': self._fmt(div_y, '%') if div_y else 'N/D',
                'earning_yield': self._fmt(ey, '%') if ey else 'N/D',
                'comentario': comentario,
            })

        return result

    def _generate_erp(self) -> Dict[str, Any]:
        """Genera analisis de Equity Risk Premium usando datos reales."""

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
            if erp_us < 3:
                narrativa += "Este nivel es bajo históricamente, sugiriendo que el equity US está caro vs bonos. "
            else:
                narrativa += "Este nivel es razonable, con equity compensando adecuadamente el riesgo. "

            # Comparar con ex-US
            ex_us_erps = [d for d in datos[1:] if d['erp'] != 'N/D']
            if ex_us_erps:
                narrativa += f"Mercados ex-US ofrecen ERPs más amplios, reforzando la preferencia relativa."
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
                'implicancia': 'Barbell approach preferido',
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
                vs_hist = ((us_pe / 18.5) - 1) * 100
                parts.append(f"US cotiza a {us_pe:.1f}x P/E ({vs_hist:+.0f}% vs promedio 10Y). ")

            ex_us_parts = []
            if eu_pe:
                ex_us_parts.append(f"Europa {eu_pe:.1f}x")
            if em_pe:
                ex_us_parts.append(f"EM {em_pe:.1f}x")
            if ch_pe:
                ex_us_parts.append(f"Chile {ch_pe:.1f}x")
            if ex_us_parts:
                parts.append(f"En contraste, {', '.join(ex_us_parts)} ofrecen valuaciones más atractivas. ")

            if us_pe and any([eu_pe, em_pe, ch_pe]):
                parts.append("Este diferencial justifica nuestra preferencia por mercados ex-US.")

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
            # Fallback a defaults estaticos
            return [
                {'region': 'S&P 500', 'eps_2025': '$255', 'eps_2026f': '$280', 'growth': '+10%', 'revision_3m': '+2%'},
                {'region': 'Stoxx 600', 'eps_2025': 'E29', 'eps_2026f': 'E32', 'growth': '+10%', 'revision_3m': '+1%'},
                {'region': 'MSCI EM', 'eps_2025': '$88', 'eps_2026f': '$98', 'growth': '+11%', 'revision_3m': '-1%'},
                {'region': 'Topix', 'eps_2025': 'Y170', 'eps_2026f': 'Y188', 'growth': '+11%', 'revision_3m': '+3%'},
                {'region': 'IPSA', 'eps_2025': 'CLP 2900', 'eps_2026f': 'CLP 3250', 'growth': '+12%', 'revision_3m': '+4%'},
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
                "Las revisiones de earnings muestran tendencia positiva en la mayoria de mercados. "
                "Japon y Chile lideran con revisiones al alza de +3% y +4% en los ultimos 3 meses, "
                "mientras EM muestra leve deterioro por China. El breadth de revisiones "
                "(% de empresas con upgrades vs downgrades) es positivo en 60% de los mercados."
            ),
            'por_region': [
                {'region': 'US', 'upgrades': '52%', 'downgrades': '38%', 'net': '+14%', 'tendencia': 'Mejorando'},
                {'region': 'Europa', 'upgrades': '48%', 'downgrades': '42%', 'net': '+6%', 'tendencia': 'Estable'},
                {'region': 'EM', 'upgrades': '42%', 'downgrades': '48%', 'net': '-6%', 'tendencia': 'Deteriorando'},
                {'region': 'Japon', 'upgrades': '55%', 'downgrades': '35%', 'net': '+20%', 'tendencia': 'Fuerte'},
                {'region': 'Chile', 'upgrades': '58%', 'downgrades': '32%', 'net': '+26%', 'tendencia': 'Muy fuerte'},
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
                "Los margenes operativos se han estabilizado tras la compresion de 2022-2023. "
                "US lidera con margenes de 12.5%, seguido por Japon mejorando a 8.5%. "
                "El ROE muestra dispersion, con US en 18% y Europa en 12%."
            ),
            'datos': [
                {'region': 'S&P 500', 'margen_op': '12.5%', 'roe': '18%', 'margen_neto': '11%', 'tendencia': 'Estable'},
                {'region': 'Stoxx 600', 'margen_op': '9.8%', 'roe': '12%', 'margen_neto': '8%', 'tendencia': 'Mejorando'},
                {'region': 'MSCI EM', 'margen_op': '11.2%', 'roe': '11%', 'margen_neto': '9%', 'tendencia': 'Presion'},
                {'region': 'Topix', 'margen_op': '8.5%', 'roe': '10%', 'margen_neto': '6%', 'tendencia': 'Mejorando'},
                {'region': 'IPSA', 'margen_op': '14.2%', 'roe': '12%', 'margen_neto': '10%', 'tendencia': 'Fuerte'},
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

            datos.append({
                'region': display_name,
                'margen_op': _pct(op_margin),
                'margen_neto': _pct(profit_margin),
                'roe': _pct(roe),
                'tendencia': 'N/D',
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

        default_calendar = [
            {'fecha': '19 Feb', 'empresa': 'NVIDIA', 'sector': 'Technology', 'relevancia': 'Alta', 'expectativa': 'Beat esperado'},
            {'fecha': '20 Feb', 'empresa': 'Walmart', 'sector': 'Consumer', 'relevancia': 'Alta', 'expectativa': 'Guia importante'},
            {'fecha': '25 Feb', 'empresa': 'Salesforce', 'sector': 'Technology', 'relevancia': 'Media', 'expectativa': 'AI monetization'},
            {'fecha': '27 Feb', 'empresa': 'Falabella', 'sector': 'Retail Chile', 'relevancia': 'Alta', 'expectativa': 'Recuperacion consumo'},
            {'fecha': '5 Mar', 'empresa': 'Broadcom', 'sector': 'Semiconductors', 'relevancia': 'Alta', 'expectativa': 'AI demand'},
        ]

        if not calendar or 'error' in calendar:
            return default_calendar

        entries = calendar.get('entries', [])
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

        sector_map = [
            ('Technology', 'technology', 'OW', 'Cara', 'Solido', 'AI capex continua, semiconductors'),
            ('Healthcare', 'healthcare', 'OW', 'Atractiva', 'Estable', 'Innovacion GLP-1, defensivo'),
            ('Financials', 'financials', 'OW', 'Barata', 'Mejorando', 'NIM estabilizando, buybacks'),
            ('Materials', 'materials', 'OW', 'Atractiva', 'Ciclico', mat_cat),
            ('Industrials', 'industrials', 'NEUTRAL', 'Fair', 'Mixto', 'Nearshoring, pero valuacion'),
            ('Consumer Disc.', 'consumer_disc', 'NEUTRAL', 'Cara', 'Presion', 'Consumo normalizando'),
            ('Energy', 'energy', 'NEUTRAL', 'Barata', 'Ciclico', energy_cat),
            ('Comm Services', 'comm_services', 'NEUTRAL', 'Fair', 'Mixto', 'Regulacion, AI beneficiario'),
            ('Consumer Staples', 'consumer_staples', 'UW', 'Cara', 'Estable', 'Sin catalizador, GLP-1 riesgo'),
            ('Utilities', 'utilities', 'UW', 'Cara', 'Estable', 'Tasas aun elevadas'),
            ('Real Estate', 'real_estate', 'UW', 'Mixta', 'Presion', 'Oficinas estructural negativo'),
        ]

        result = []
        for name, key, view, val_default, earn_default, cat_default in sector_map:
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
                'valuacion': val_default,
                'momentum': momentum,
                'retornos': ret_str if ret_str else 'N/D',
                'earnings': earn_default,
                'catalizador': cat_default,
            })

        return result

    def _generate_preferred_sectors(self) -> List[Dict[str, Any]]:
        """Genera detalle de sectores preferidos."""
        return [
            {
                'sector': 'Technology',
                'view': 'OVERWEIGHT',
                'tesis': (
                    "El sector tecnologico sigue siendo el principal beneficiario de la revolucion AI. "
                    "Preferimos exposicion selectiva a semiconductores (NVIDIA, ASML) y hyperscalers "
                    "(Microsoft, Google) sobre software puro que enfrenta disrupcion."
                ),
                'subsectores': ['Semiconductors', 'Cloud Infrastructure', 'Cybersecurity'],
                'evitar': ['Legacy Software', 'Hardware commoditizado'],
                'riesgos': ['Valuacion elevada', 'Regulacion antimonopolio', 'Desaceleracion capex'],
                'upside': '+15-20%',
                'empresas_referencia': ['NVIDIA', 'Microsoft', 'ASML', 'Broadcom']
            },
            {
                'sector': 'Healthcare',
                'view': 'OVERWEIGHT',
                'tesis': (
                    "Healthcare ofrece combinacion atractiva de crecimiento defensivo y valuacion razonable. "
                    "La innovacion en GLP-1 y oncologia provee drivers seculares. Sector sub-owned "
                    "tras underperformance de 2023-2024."
                ),
                'subsectores': ['Large Cap Pharma', 'Biotech selectivo', 'Med Devices'],
                'evitar': ['Managed Care (regulacion)', 'Generic Pharma'],
                'riesgos': ['IRA pricing pressure', 'Clinical trial failures'],
                'upside': '+12-15%',
                'empresas_referencia': ['Eli Lilly', 'Novo Nordisk', 'UnitedHealth', 'Intuitive Surgical']
            },
            {
                'sector': 'Financials',
                'view': 'OVERWEIGHT',
                'tesis': (
                    "Bancos ofrecen valuacion atractiva con NIM estabilizando y calidad crediticia solida. "
                    "El sector se beneficia de curva de tasas normalizandose y buybacks agresivos. "
                    "Preferimos bancos diversificados sobre regionales."
                ),
                'subsectores': ['Large Cap Banks', 'Insurance', 'Asset Managers'],
                'evitar': ['Regional Banks', 'Fintech especulativo'],
                'riesgos': ['Recesion hard landing', 'CRE exposure', 'Regulacion'],
                'upside': '+10-15%',
                'empresas_referencia': ['JPMorgan', 'Bank of America', 'Allianz', 'Blackstone']
            },
            {
                'sector': 'Materials',
                'view': 'OVERWEIGHT',
                'tesis': (
                    "Sector beneficiado por transicion energetica (cobre, litio) y estabilizacion China. "
                    "Valuacion atractiva tras correccion de 2023. Preferimos cobre sobre otros metales "
                    "por deficit estructural de oferta."
                ),
                'subsectores': ['Copper miners', 'Specialty Chemicals', 'Packaging'],
                'evitar': ['Iron ore (China property)', 'Coal'],
                'riesgos': ['Desaceleracion China', 'USD fuerte'],
                'upside': '+15-20%',
                'empresas_referencia': ['Freeport-McMoRan', 'BHP', 'Linde', 'Antofagasta']
            },
        ]

    def _generate_avoid_sectors(self) -> List[Dict[str, Any]]:
        """Genera detalle de sectores a evitar."""
        return [
            {
                'sector': 'Consumer Staples',
                'view': 'UNDERWEIGHT',
                'razon': (
                    "Valuacion cara (P/E 22x) sin crecimiento de earnings. Riesgo estructural de GLP-1 "
                    "drugs afectando volumen de alimentos y bebidas. Sin catalizador positivo visible."
                ),
                'que_cambiaria': 'Correccion de valuacion de 15%+ o evidencia de resiliencia vs GLP-1'
            },
            {
                'sector': 'Utilities',
                'view': 'UNDERWEIGHT',
                'razon': (
                    "Tasas reales elevadas comprimen valuacion del sector. Dividend yield no competitivo "
                    "vs bonos. Capex elevado en renovables sin retornos claros."
                ),
                'que_cambiaria': 'Recortes agresivos de tasas o re-pricing significativo'
            },
            {
                'sector': 'Real Estate',
                'view': 'UNDERWEIGHT',
                'razon': (
                    "Oficinas enfrentan headwind estructural por trabajo remoto. Refinanciamiento "
                    "a tasas mas altas presiona earnings. Data centers son excepcion pero valuacion elevada."
                ),
                'que_cambiaria': 'Normalizacion de ocupacion oficinas o caida de tasas de 100bp+'
            },
        ]

    def _generate_sector_narrative(self) -> str:
        """Genera narrativa sectorial."""
        default = (
            "Nuestra preferencia sectorial refleja un balance entre crecimiento secular (Technology, Healthcare) "
            "y value ciclico (Financials, Materials). Evitamos sectores defensivos caros sin catalizador "
            "(Staples, Utilities) y Real Estate por headwinds estructurales. En Technology somos selectivos, "
            "prefiriendo semiconductores y cloud sobre software legacy."
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

            ytd_spread = gv_spread.get('ytd', 0)
            if ytd_spread > 5:
                narrativa = (
                    f"Growth lidera significativamente sobre Value en lo que va del año "
                    f"({performance['growth_ytd']} vs {performance['value_ytd']}, spread de {performance['spread_ytd']}). "
                    "El dominio de Growth sugiere precaución por concentración. "
                    "Recomendamos barbell: Quality Growth selectivo + Deep Value cíclico."
                )
            elif ytd_spread < -5:
                narrativa = (
                    f"Value ha superado a Growth este año ({performance['value_ytd']} vs {performance['growth_ytd']}). "
                    "La rotación hacia Value refleja tasas elevadas y preferencia por fundamentales. "
                    "Favorecemos Value cíclico (Financials, Materials) con exposición selectiva a Growth de calidad."
                )
            else:
                narrativa = (
                    f"Growth y Value muestran performance similar YTD ({performance['growth_ytd']} vs {performance['value_ytd']}). "
                    "El balance actual apoya un enfoque barbell equilibrado entre Quality Growth "
                    "y Deep Value cíclico, evitando Growth especulativo sin earnings."
                )
        else:
            performance = {
                'growth_ytd': 'N/D', 'value_ytd': 'N/D', 'spread_ytd': 'N/D',
                'growth_1m': 'N/D', 'value_1m': 'N/D',
            }
            narrativa = "Datos de style no disponibles. Mantenemos enfoque barbell Quality + Value como default."
            style_signal = 'BALANCED'

        return {
            'performance': performance,
            'valuacion': {
                'growth_pe': 'N/D', 'value_pe': 'N/D',
                'spread': 'N/D', 'vs_historia': 'N/D',
            },
            'narrativa': narrativa,
            'view': 'BARBELL' if style_signal == 'BALANCED' else style_signal,
            'preferencia': 'Quality Growth + Deep Value',
        }

    def _generate_factor_performance(self) -> List[Dict[str, Any]]:
        """Genera performance de factores usando scores reales de FactorAnalytics."""

        fd = self.market_data.get('factors', {})
        has_factors = fd and 'error' not in fd

        # Factor ETF returns desde style data
        sd = self._style_data()
        g_ret = sd.get('growth', {}).get('returns', {}) if sd and 'error' not in sd else {}
        v_ret = sd.get('value', {}).get('returns', {}) if sd and 'error' not in sd else {}
        sm_ret = sd.get('small_cap', {}).get('returns', {}) if sd and 'error' not in sd else {}

        # Scores promedio por factor (SPY como referencia US)
        spy_scores = fd.get('SPY', {}) if has_factors else {}

        factors = [
            {
                'factor': 'Quality',
                'score': self._fmt(spy_scores.get('quality'), '/100') if spy_scores.get('quality') is not None else 'N/D',
                'ytd': 'N/D',
                'view': 'OW',
                'rationale': 'Late cycle favorece calidad, bajo leverage',
            },
            {
                'factor': 'Momentum',
                'score': self._fmt(spy_scores.get('momentum'), '/100') if spy_scores.get('momentum') is not None else 'N/D',
                'ytd': 'N/D',
                'view': 'NEUTRAL',
                'rationale': 'Funciona pero caro, riesgo de reversal',
            },
            {
                'factor': 'Value',
                'score': self._fmt(spy_scores.get('value'), '/100') if spy_scores.get('value') is not None else 'N/D',
                'ytd': self._fmt(v_ret.get('ytd'), '%', prefix='+' if (v_ret.get('ytd') or 0) >= 0 else '') if v_ret.get('ytd') is not None else 'N/D',
                'view': 'OW',
                'rationale': 'Descuento historico, catalizador de tasas',
            },
            {
                'factor': 'Growth',
                'score': self._fmt(spy_scores.get('growth'), '/100') if spy_scores.get('growth') is not None else 'N/D',
                'ytd': self._fmt(g_ret.get('ytd'), '%', prefix='+' if (g_ret.get('ytd') or 0) >= 0 else '') if g_ret.get('ytd') is not None else 'N/D',
                'view': 'NEUTRAL',
                'rationale': 'Selectivo, solo quality growth',
            },
            {
                'factor': 'Size (Small)',
                'score': 'N/D',
                'ytd': self._fmt(sm_ret.get('ytd'), '%', prefix='+' if (sm_ret.get('ytd') or 0) >= 0 else '') if sm_ret.get('ytd') is not None else 'N/D',
                'view': 'UW',
                'rationale': 'Riesgo refinanciamiento, menos liquidez',
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

        return factors

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

        # Narrativa dinámica
        if lg_ytd is not None and sm_ytd is not None:
            if spread_ytd and spread_ytd > 3:
                narrativa = (
                    f"Small caps ({sm_ytd:+.1f}% YTD) están superando a large caps ({lg_ytd:+.1f}% YTD), "
                    f"spread de {spread_ytd:+.1f}pp. Pero mantenemos cautela por riesgo de refinanciamiento."
                )
            elif spread_ytd and spread_ytd < -3:
                narrativa = (
                    f"Large caps ({lg_ytd:+.1f}% YTD) lideran sobre small caps ({sm_ytd:+.1f}% YTD), "
                    f"spread de {spread_ytd:+.1f}pp. Confirma preferencia por calidad y acceso a capital."
                )
            else:
                narrativa = (
                    f"Large ({lg_ytd:+.1f}% YTD) y small caps ({sm_ytd:+.1f}% YTD) muestran "
                    f"performance similar. Preferimos large caps por menor riesgo de refinanciamiento."
                )
        else:
            narrativa = (
                "Small caps enfrentan headwinds por refinanciamiento a tasas más altas y menor "
                "visibilidad de earnings. Preferimos Large Caps por calidad y acceso a capital."
            )

        return {
            'performance': {
                'large_ytd': self._fmt(lg_ytd, '%', prefix='+' if (lg_ytd or 0) >= 0 else '') if lg_ytd is not None else 'N/D',
                'small_ytd': self._fmt(sm_ytd, '%', prefix='+' if (sm_ytd or 0) >= 0 else '') if sm_ytd is not None else 'N/D',
                'spread_ytd': self._fmt(spread_ytd, 'pp', prefix='+' if (spread_ytd or 0) >= 0 else '') if spread_ytd is not None else 'N/D',
                'large_1m': self._fmt(lg_ret.get('1m'), '%', prefix='+' if (lg_ret.get('1m') or 0) >= 0 else '') if lg_ret.get('1m') is not None else 'N/D',
                'small_1m': self._fmt(sm_ret.get('1m'), '%', prefix='+' if (sm_ret.get('1m') or 0) >= 0 else '') if sm_ret.get('1m') is not None else 'N/D',
            },
            'signal': size_signal,
            'view': 'UNDERWEIGHT Small Caps' if size_signal == 'LARGE_CAP' else 'NEUTRAL Size',
            'narrativa': narrativa,
        }

    def _generate_style_recommendation(self) -> Dict[str, Any]:
        """Genera recomendacion de style."""
        return {
            'recomendacion': 'Quality + Value Barbell',
            'quality_allocation': '60%',
            'value_allocation': '40%',
            'evitar': ['Speculative Growth', 'Low Quality Small Caps'],
            'rationale': (
                "En un entorno de tasas estables y crecimiento moderado, Quality ofrece resiliencia "
                "mientras Value provee upside ciclico. El barbell captura lo mejor de ambos mundos "
                "evitando el Growth especulativo y el Value trap."
            )
        }

    # =========================================================================
    # SECCION 6: VIEWS REGIONALES
    # =========================================================================

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
        pe_historia = 18.5  # Promedio histórico S&P 500

        # View dinámico basado en valuación real
        view = 'NEUTRAL'
        if pe and pe > 22:
            view = 'NEUTRAL'
            cambio = 'Valuación elevada'
        elif pe and pe < 17:
            view = 'OW'
            cambio = 'Descuento atractivo'
        else:
            view = 'NEUTRAL'
            cambio = '='

        result = {
            'mercado': 'Estados Unidos',
            'indice': 'S&P 500',
            'view': view,
            'cambio': cambio,
            'target_12m': f"{price * 1.06:,.0f}" if price else 'N/D',
            'upside': '+6%',
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x',
            'narrativa': (
                f"El S&P 500 cotiza a {pe_str} P/E"
                + (f", {((pe/pe_historia)-1)*100:+.0f}% vs promedio histórico de {pe_historia}x. " if pe else ". ")
                + (f"El retorno YTD es de {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + "Earnings resilientes pero valuación limita upside. Preferimos exposición selectiva."
            ),
            'sectores_preferidos': ['Technology (selectivo)', 'Healthcare', 'Financials'],
            'sectores_evitar': ['Consumer Staples', 'Utilities'],
            'catalizadores': ['Earnings beats', 'Soft landing confirmado', 'AI monetization'],
            'riesgos': ['Valuacion de-rating', 'Concentracion', 'Reflacion']
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
                        result['narrativa'] = self._md_to_html(p[:500])
                        break

        return result

    def _generate_europe_view(self) -> Dict[str, Any]:
        """Genera view de Europa con datos reales."""
        v = self._val('europe') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')
        pe_historia = 14.5

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        result = {
            'mercado': 'Europa',
            'indice': 'Stoxx 600',
            'view': 'OW' if (pe and pe < pe_historia) else 'NEUTRAL',
            'cambio': '=' if not pe else ('Descuento atractivo' if pe < pe_historia else 'Fair value'),
            'target_12m': f"{price * 1.12:,.0f}" if price else 'N/D',
            'upside': '+12%',
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x',
            'narrativa': (
                f"Europa cotiza a {pe_str} P/E"
                + (f", {((pe/pe_historia)-1)*100:+.0f}% vs promedio histórico. " if pe else ". ")
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + "BCE en modo dovish y descuento vs US refuerzan preferencia por mercado europeo."
            ),
            'sectores_preferidos': ['Luxury', 'Industrials', 'Banks', 'Pharma'],
            'sectores_evitar': ['Utilities', 'Autos domesticos'],
            'catalizadores': ['BCE dovish', 'Estabilizacion China', 'Earnings beats'],
            'riesgos': ['Geopolitica Ucrania', 'Energia', 'Fragmentacion politica']
        }

        if self._has_council():
            rv = self._panel('rv')
            geo = self._panel('geo')
            source = rv + '\n' + geo
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['europa', 'stoxx', 'bce', 'eurozona']):
                        result['narrativa'] = self._md_to_html(p[:500])
                        break

        return result

    def _generate_em_view(self) -> Dict[str, Any]:
        """Genera view de EM con datos reales."""
        v = self._val('em') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')
        pe_historia = 13.2

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        result = {
            'mercado': 'Emergentes',
            'indice': 'MSCI EM',
            'view': 'OW' if (pe and pe < pe_historia) else 'NEUTRAL',
            'cambio': '=',
            'target_12m': f"{price * 1.15:,.0f}" if price else 'N/D',
            'upside': '+15%',
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x',
            'narrativa': (
                f"EM cotiza a {pe_str} P/E"
                + (f", {((pe/pe_historia)-1)*100:+.0f}% vs promedio. " if pe else ". ")
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + "Valuación atractiva con China estabilizando y LatAm ofreciendo crecimiento estructural."
            ),
            'paises_preferidos': ['India', 'Indonesia', 'Brasil', 'Mexico'],
            'paises_evitar': ['Turquia', 'Sudafrica'],
            'china_view': {
                'view': 'NEUTRAL', 'peso_benchmark': '25%',
                'peso_recomendado': '20%',
                'comentario': 'Estabilizando pero riesgos estructurales persisten'
            },
            'catalizadores': ['China estabilizando', 'Commodities up', 'Nearshoring'],
            'riesgos': ['USD fortaleza', 'China hard landing', 'Tasas US higher for longer']
        }

        if self._has_council():
            rv = self._panel('rv')
            geo = self._panel('geo')
            source = rv + '\n' + geo
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['emergent', 'em ', 'china', 'india', 'latam']):
                        result['narrativa'] = self._md_to_html(p[:500])
                        break

        return result

    def _generate_japan_view(self) -> Dict[str, Any]:
        """Genera view de Japon con datos reales."""
        v = self._val('japan') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')
        pe_historia = 14.5

        pe_str = self._fmt(pe, 'x') if pe else 'N/D'

        return {
            'mercado': 'Japon',
            'indice': 'Topix',
            'view': 'OW',
            'cambio': '=',
            'target_12m': f"{price * 1.14:,.0f}" if price else 'N/D',
            'upside': '+14%',
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x',
            'narrativa': (
                f"Japón cotiza a {pe_str} P/E"
                + (f", {((pe/pe_historia)-1)*100:+.0f}% vs promedio. " if pe else ". ")
                + (f"Retorno YTD: {ret_ytd:+.1f}%. " if ret_ytd is not None else "")
                + "Reformas corporativas mejoran ROE y payout. Yen débil beneficia exportadores."
            ),
            'sectores_preferidos': ['Autos exportadores', 'Trading Houses', 'Banks', 'Tech'],
            'sectores_evitar': ['Utilities domesticas', 'Retail domestico'],
            'temas_clave': ['Reformas corporativas', 'Unwinding deflation', 'Turismo'],
            'catalizadores': ['Yen estable/debil', 'Buybacks record', 'Earnings upgrades'],
            'riesgos': ['JPY apreciacion rapida', 'BOJ hawkish surprise']
        }

    def _generate_chile_view(self) -> Dict[str, Any]:
        """Genera view de Chile con datos reales (ECH ETF + BCCh IPSA + USD/CLP + cobre)."""
        v = self._val('chile') if self._has_data() else {}
        pe = v.get('pe_trailing') or v.get('pe_forward')
        price = v.get('price')
        ret_ytd = v.get('returns', {}).get('ytd')
        div_y = v.get('dividend_yield')
        # Dynamic PE history: use average of real picks if available, else 12.0
        chile_picks_data = self.market_data.get('chile_picks', [])
        real_pes = [p.get('pe_trailing') or p.get('pe_forward')
                    for p in chile_picks_data
                    if (p.get('pe_trailing') or p.get('pe_forward')) is not None]
        pe_historia = round(sum(real_pes) / len(real_pes), 1) if real_pes else 12.0

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
        if pe:
            parts.append(f"ECH ETF a {pe_str} P/E, {((pe/pe_historia)-1)*100:+.0f}% vs promedio histórico de {pe_historia}x. ")
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

        parts.append("Ciclo de tasas favorable con BCCh en modo dovish. Preferimos bancos, retail y utilities reguladas.")
        narrativa = ''.join(parts) if parts else "Chile muestra valuaciones atractivas con ciclo de tasas favorable."

        # Council enrichment
        if self._has_council():
            rv = self._panel('rv')
            macro = self._panel('macro')
            source = rv + '\n' + macro
            if source.strip():
                for para in source.split('\n\n'):
                    p = para.strip()
                    if len(p) > 80 and any(kw in p.lower() for kw in ['chile', 'ipsa', 'bcch', 'tpm']):
                        narrativa = self._md_to_html(p[:500])
                        break

        # USD/CLP sensitivity con datos reales
        usdclp_str = f"${usdclp:,.0f}" if usdclp else 'N/D'
        usdclp_chg = f" ({usdclp_1m:+.1f}% 1M, {usdclp_ytd:+.1f}% YTD)" if usdclp_1m is not None and usdclp_ytd is not None else ''

        return {
            'mercado': 'Chile',
            'indice': 'IPSA',
            'view': 'OW' if (pe and pe < pe_historia) else 'NEUTRAL',
            'cambio': 'Descuento atractivo' if (pe and pe < pe_historia * 0.9) else '=',
            'target_12m': f"{price * 1.18:,.0f}" if price else 'N/D',
            'upside': '+18%',
            'nivel_actual': f"{ipsa_level:,.0f}" if ipsa_level else (f"{price:,.0f}" if price else 'N/D'),
            'ipsa_retornos': {
                'ytd': self._fmt(ipsa_ytd, '%', prefix='+' if (ipsa_ytd or 0) >= 0 else '') if ipsa_ytd is not None else 'N/D',
                '1m': self._fmt(ipsa_1m, '%', prefix='+' if (ipsa_1m or 0) >= 0 else '') if ipsa_1m is not None else 'N/D',
                '3m': self._fmt(ipsa_3m, '%', prefix='+' if (ipsa_3m or 0) >= 0 else '') if ipsa_3m is not None else 'N/D',
            },
            'pe_actual': pe_str,
            'pe_historia': f'{pe_historia}x',
            'narrativa': narrativa,
            'commodities_context': {
                'cobre': f"{copper:.2f} USD/lb ({copper_ytd:+.1f}% YTD)" if copper and copper_ytd is not None else 'N/D',
                'litio': f"{lithium:.0f} USD/ton ({lithium_ytd:+.1f}% YTD)" if lithium and lithium_ytd is not None else 'N/D',
            },
            'sectores_preferidos': ['Bancos', 'Retail', 'Utilities reguladas', 'Commodities'],
            'sectores_evitar': ['Construccion', 'Small caps iliquidas'],
            'top_picks': self._build_chile_top_picks(chile_picks_data),
            'catalizadores': ['Recortes TPM', 'Cobre fuerte', 'Consumo recuperando'],
            'riesgos': ['Riesgo politico', 'Cobre colapso', 'Liquidez mercado'],
            'usd_clp_sensitivity': {
                'titulo': 'Sensibilidad a USD/CLP',
                'nivel_actual': usdclp_str + usdclp_chg,
                'escenarios': [
                    {'escenario': 'CLP fuerte (<$820)', 'impacto_ipsa': '-3%', 'impacto_earnings': '-5%', 'comentario': 'Negativo para exportadores'},
                    {'escenario': f'Neutral (~${usdclp:,.0f})' if usdclp else 'Neutral', 'impacto_ipsa': '0%', 'impacto_earnings': '0%', 'comentario': 'Base case'},
                    {'escenario': 'CLP debil (>$900)', 'impacto_ipsa': '+2%', 'impacto_earnings': '+4%', 'comentario': 'Positivo para exportadores'}
                ],
                'beta_ipsa_usdclp': '+0.35',
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
                    'rationale': rationale_map.get(p['ticker'], 'Valuación atractiva'),
                })
            return top_picks

        # Fallback hardcoded (marcados como estimados)
        return [
            {'empresa': 'Banco de Chile', 'ticker': 'BCH', 'pe': '~15x (est.)', 'div_yield': '~4.5% (est.)', 'rationale': 'Mejor calidad, dividend'},
            {'empresa': 'Santander Chile', 'ticker': 'BSAC', 'pe': '~14x (est.)', 'div_yield': '~3.5% (est.)', 'rationale': 'Banca retail líder'},
            {'empresa': 'SQM', 'ticker': 'SQM', 'pe': '~17x (est.)', 'div_yield': 'N/D', 'rationale': 'Litio + cobre'},
            {'empresa': 'LATAM Airlines', 'ticker': 'LTM', 'pe': '~12x (est.)', 'div_yield': '~4% (est.)', 'rationale': 'Recovery aéreo'},
        ]

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
                indicadores.append({'indicador': 'IG Spread', 'valor': f'{ig:.0f}bp', 'comentario': comentario})
            if hy is not None:
                comentario = f'Percentil {hy_pct:.0f}%' if hy_pct is not None else ''
                indicadores.append({'indicador': 'HY Spread', 'valor': f'{hy:.0f}bp', 'comentario': comentario})

        # Risk metrics
        if has_risk:
            var95 = rd.get('var_95_daily')
            curr_dd = rd.get('current_drawdown')
            if var95 is not None:
                indicadores.append({'indicador': 'VaR 95% (diario)', 'valor': f'{var95:.2f}%', 'comentario': 'Portfolio equity diversificado'})
            if curr_dd is not None:
                indicadores.append({'indicador': 'Drawdown actual', 'valor': f'{curr_dd:.1f}%', 'comentario': 'Desde máximo reciente'})

        # Breadth
        if has_breadth:
            summary = bd.get('summary', {})
            signal = summary.get('signal', 'N/D')
            cyc_def = bd.get('cyclical_defensive', {})
            indicadores.append({'indicador': 'Breadth Signal', 'valor': signal, 'comentario': 'MarketBreadthAnalytics'})
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
        """Genera top riesgos para equity enriquecidos con credit y risk data."""

        cd = self._credit_data()
        has_credit = cd and 'error' not in cd
        rd = self._risk_data()
        has_risk = rd and 'error' not in rd

        # Señales de riesgo reales para enriquecer descripciones
        credit_context = ''
        if has_credit:
            hy = cd.get('hy_spread')
            hy_pct = cd.get('hy_percentile')
            ig = cd.get('ig_spread')
            if hy is not None:
                credit_context = f" HY spread actual: {hy:.0f}bp (percentil {hy_pct:.0f}%)." if hy_pct else f" HY spread: {hy:.0f}bp."

        risk_context = ''
        if has_risk:
            var95 = rd.get('var_95_daily')
            max_dd = rd.get('max_drawdown')
            if var95 is not None:
                risk_context = f" VaR 95%: {var95:.2f}% diario."

        defaults = [
            {
                'riesgo': 'Reflacion / Fed Hawkish',
                'probabilidad': '25%',
                'impacto': 'Alto',
                'descripcion': f'Inflacion rebota, Fed pausa recortes. Tasas largas suben, P/E comprime.{credit_context}',
                'sectores_afectados': ['Growth', 'Real Estate', 'Utilities'],
                'hedge': 'Financials, Energy, cortos en long duration'
            },
            {
                'riesgo': 'Recesion Hard Landing',
                'probabilidad': '15%',
                'impacto': 'Muy Alto',
                'descripcion': f'Economia cae en recesion, earnings colapsan -20%+.{risk_context}',
                'sectores_afectados': ['Cyclicals', 'Financials', 'Small Caps'],
                'hedge': 'Cash, Healthcare, Staples, Gold'
            },
            {
                'riesgo': 'China Hard Landing',
                'probabilidad': '20%',
                'impacto': 'Alto',
                'descripcion': 'Property crisis se profundiza, contagio a commodities y EM.',
                'sectores_afectados': ['Materials', 'EM', 'Luxury', 'Autos'],
                'hedge': 'Reducir EM, preferir DM domestico'
            },
        ]

        if not self._has_council():
            return defaults

        riesgo = self._panel('riesgo')
        if riesgo:
            for risk in defaults:
                name_lower = risk['riesgo'].lower()
                for para in riesgo.split('\n\n'):
                    p = para.strip()
                    if len(p) > 50:
                        keywords = name_lower.split('/')
                        if any(kw.strip() in p.lower() for kw in keywords):
                            risk['descripcion'] = self._md_to_html(p[:300])
                            break

        return defaults

    def _generate_positive_catalysts(self) -> List[str]:
        """Genera catalizadores positivos."""
        return [
            "AI monetization supera expectativas - boost a Tech earnings",
            "China estimulo agresivo - lift a EM y Materials",
            "Soft landing confirmado - expansion de multiples",
            "Deals M&A aceleran - bid for assets",
            "Buybacks record en 2026 - soporte tecnico"
        ]

    def _generate_event_calendar(self) -> List[Dict[str, Any]]:
        """Genera calendario de eventos."""
        return [
            {'fecha': '19 Feb', 'evento': 'NVIDIA Earnings', 'relevancia': 'Alta', 'impacto': 'AI bellwether'},
            {'fecha': '25 Feb', 'evento': 'PCE Inflation USA', 'relevancia': 'Alta', 'impacto': 'Fed path'},
            {'fecha': '5 Mar', 'evento': 'NPC China', 'relevancia': 'Alta', 'impacto': 'Estimulos'},
            {'fecha': '18-19 Mar', 'evento': 'FOMC Meeting', 'relevancia': 'Alta', 'impacto': 'Tasas'},
            {'fecha': 'Q1', 'evento': 'Earnings Season Q4', 'relevancia': 'Alta', 'impacto': 'Guidance 2026'},
        ]

    # =========================================================================
    # SECCION 9: RESUMEN POSICIONAMIENTO
    # =========================================================================

    def generate_positioning_summary(self) -> Dict[str, Any]:
        """Genera resumen final de posicionamiento."""

        result = {
            'tabla_final': [
                {'categoria': 'Equity Global', 'recomendacion': 'OW vs benchmark'},
                {'categoria': 'Region Preferida', 'recomendacion': 'Europa, Japon, Chile'},
                {'categoria': 'Region Neutral', 'recomendacion': 'Estados Unidos'},
                {'categoria': 'Sectores OW', 'recomendacion': 'Tech (selectivo), Healthcare, Financials, Materials'},
                {'categoria': 'Sectores UW', 'recomendacion': 'Utilities, Real Estate, Consumer Staples'},
                {'categoria': 'Style', 'recomendacion': 'Quality + Value barbell'},
                {'categoria': 'Factor Tilt', 'recomendacion': 'Quality, Value'},
                {'categoria': 'Size', 'recomendacion': 'Large Caps preferido'},
            ],
            'mensaje_clave': (
                "Mantenemos postura constructiva en equity global con preferencia por mercados "
                "ex-US que ofrecen valuacion mas atractiva. Barbell de Quality Growth y Deep Value "
                "en sectores ciclicos. Chile destaca como oportunidad local con upside de 18%."
            )
        }

        if not self._has_council():
            return result

        final = self._final()
        if final:
            # Use first substantial paragraph from final recommendation
            paragraphs = [p.strip() for p in final.split('\n\n') if len(p.strip()) > 50]
            if paragraphs:
                result['mensaje_clave'] = self._md_to_html(paragraphs[0][:400])

        return result

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

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte RV."""

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

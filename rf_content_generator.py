# -*- coding: utf-8 -*-
"""
Greybark Research - Renta Fija Content Generator
=================================================

Genera el CONTENIDO narrativo para el reporte de Renta Fija mensual.
Sigue la estructura de PIMCO / BlackRock Fixed Income:
- Yields y curvas de tasas
- Duration positioning
- Spreads de crédito (IG, HY)
- Mercados emergentes
- Inflación y breakevens

Integración de datos reales via rf_data_collector.py:
- yield_curve: Curva Treasury, slopes (2s5s, 2s10s, etc.)
- duration: Duration dashboard, recs, curve positioning
- credit_spreads: IG/HY por rating (FRED ICE BofA OAS)
- inflation: Breakevens, real rates, CPI decomp (FRED)
- fed_expectations: Fed Funds path por reunión FOMC
- tpm_expectations: TPM path por reunión BCCh
- fed_dots: Market vs FOMC dot plot
- bcch_encuesta: Market vs Encuesta BCCh
- credit_duration: Spreads por bucket de duración

Fallback: Si no hay datos reales, usa valores hardcoded.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class RFContentGenerator:
    """Generador de contenido narrativo para Reporte de Renta Fija."""

    def __init__(self, council_result: Dict = None, market_data: Dict = None,
                 forecast_data: Dict = None, company_name: str = ""):
        self.council = council_result or {}
        self.market_data = market_data or {}
        self.forecast = forecast_data or {}
        self.company_name = company_name
        self.date = datetime.now()
        self.month_name = self._get_spanish_month(self.date.month)
        self.year = self.date.year
        self._parser = None
        self.bloomberg = None  # BloombergReader, injected externally

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
    # HELPERS — acceso a datos reales
    # =========================================================================

    def _has_data(self, *keys) -> bool:
        """Verifica si market_data tiene datos reales en la ruta de keys."""
        d = self.market_data
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return False
            d = d[k]
            if isinstance(d, dict) and 'error' in d:
                return False
        return d is not None

    def _val(self, *keys, default=None):
        """Obtiene valor de market_data siguiendo la ruta de keys."""
        d = self.market_data
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return default
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return default
        return d if d is not None else default

    def _fmt_pct(self, value, decimals=2) -> str:
        """Formatea un número como porcentaje."""
        if value is None:
            return 'N/D'
        try:
            return f"{float(value):.{decimals}f}%"
        except (ValueError, TypeError):
            return str(value)

    def _fmt_bp(self, value) -> str:
        """Formatea un número como basis points."""
        if value is None:
            return 'N/D'
        try:
            return f"{int(round(float(value)))}bp"
        except (ValueError, TypeError):
            return str(value)

    def _council_rf_panel(self) -> str:
        """Extrae texto del panel RF del council."""
        try:
            panels = self.council.get('panel_outputs', {})
            rf = panels.get('rf', panels.get('renta_fija', ''))
            if isinstance(rf, dict):
                return rf.get('content', rf.get('output', ''))
            return str(rf) if rf else ''
        except Exception:
            return ''

    def _council_cio(self) -> str:
        """Extrae texto del CIO synthesis."""
        try:
            return self.council.get('cio_synthesis', '')
        except Exception:
            return ''

    def _get_spanish_month(self, month: int) -> str:
        """Retorna nombre del mes en espanol."""
        meses = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return meses.get(month, 'Mes')

    # =========================================================================
    # SECCION 1: RESUMEN EJECUTIVO
    # =========================================================================

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Genera resumen ejecutivo del reporte RF."""

        return {
            'titulo': f"Perspectivas Renta Fija - {self.month_name} {self.year}",
            'postura_global': self._generate_global_stance(),
            'tabla_resumen': self._generate_summary_table(),
            'key_calls': self._generate_key_calls()
        }

    def _generate_global_stance(self) -> Dict[str, Any]:
        """Genera postura global de renta fija (policy rates reales BCCh)."""
        # Policy rates from BCCh
        tpm = self._val('chile_rates', 'tpm', 'current')
        fed = self._val('chile_rates', 'policy_rates', 'fed')
        ecb = self._val('chile_rates', 'policy_rates', 'ecb')
        boj = self._val('chile_rates', 'policy_rates', 'boj')
        boe = self._val('chile_rates', 'policy_rates', 'boe')

        # Determine view from council — NO hardcoded default
        has_text = self.parser.has_council_text() if self.parser else False
        view = 'NEUTRAL' if has_text else 'N/D'
        final = self.council.get('final_recommendation', '')
        if final:
            text = final.lower()
            import re as _re
            if _re.search(r'postura\s+(agresiva|agresivo)', text) or 'fuerte risk-on' in text:
                view = 'AGRESIVO'
            elif 'defensiva moderada' in text or 'defensivo moderado' in text:
                view = 'CAUTELOSO'
            elif 'risk-off' in text or 'postura defensiva' in text:
                view = 'CAUTELOSO'
            elif 'neutral' in text and 'renta fija' in text:
                view = 'NEUTRAL'
            elif 'constructiv' in text:
                view = 'CONSTRUCTIVO'
            else:
                view = 'NEUTRAL'

        # Generate narrative via Claude if council available
        stance_map = {'CONSTRUCTIVO': 'constructiva', 'CAUTELOSO': 'cautelosa',
                      'NEUTRAL': 'neutral', 'AGRESIVO': 'agresiva'}
        stance_word = stance_map.get(view, 'constructiva')

        narrativa = ''
        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        if rf_panel or final:
            from narrative_engine import generate_narrative
            quant_parts = []
            if fed:
                quant_parts.append(f"Fed: {self._fmt_pct(fed)}")
            if ecb:
                quant_parts.append(f"BCE: {self._fmt_pct(ecb)}")
            if tpm:
                quant_parts.append(f"BCCh TPM: {self._fmt_pct(tpm)}")

            narrativa = generate_narrative(
                section_name="rf_global_stance",
                prompt=(
                    f"Escribe un parrafo de postura global en renta fija para {self.month_name} {self.year}. "
                    f"La postura es {stance_word}. Explica en 3-4 oraciones el fundamento: "
                    "ambiente de tasas, posicionamiento de duration, y credito. "
                    "Integra los datos cuantitativos disponibles. Usa SOLO datos del council. Maximo 80 palabras."
                    "\n\nEscribe 150-200 palabras. Incluye: qué cambió vs período anterior, principal riesgo con trigger cuantificado, horizonte temporal (táctico 1-3m o estratégico 6-12m). Explica jerga técnica (duration, carry, spread, IG, HY, OAS, steepener, flattener) con paréntesis en primera mención."
                ),
                council_context=f"RF PANEL:\n{rf_panel[:2000]}\n\nFINAL:\n{final[:1000]}",
                quant_context=" | ".join(quant_parts),
                company_name=self.company_name,
                max_tokens=600,
            )

        if not narrativa:
            # Fallback with quant data but no stale market calls
            parts = [f"Nuestra postura en renta fija global es {stance_word}. "]
            if fed and ecb:
                parts.append(f"Con la Fed en {self._fmt_pct(fed)} y el BCE en {self._fmt_pct(ecb)}, evaluamos "
                            "el espacio para movimientos de tasas. ")
            if tpm:
                parts.append(f"Chile (TPM {self._fmt_pct(tpm)}) mantiene dinamica propia. ")
            narrativa = ''.join(parts)

        # Get duration and credit stances from council parser
        dur_stance = self.parser.get_duration_stance()
        fi_views = self.parser.get_fi_views()
        ig_v = fi_views.get('ig corporate', {}) if fi_views else {}

        # Text mining fallback for duration/credit
        dur_stance_str = dur_stance.get('stance', 'Sin vista') if dur_stance else 'Sin vista'
        credit_stance_str = ig_v.get('view', 'Sin vista') if ig_v else 'Sin vista'
        if dur_stance_str == 'Sin vista' and has_text:
            mined_dur = self.parser.search_duration_view()
            dur_stance_str = mined_dur if mined_dur else 'NEUTRAL'
        if credit_stance_str == 'Sin vista' and has_text:
            mined_ig = self.parser.search_credit_view('ig')
            credit_stance_str = mined_ig if mined_ig else 'NEUTRAL'

        result = {
            'view': view,
            'duration_stance': dur_stance_str,
            'credit_stance': credit_stance_str,
            'conviccion': 'MEDIA' if has_text else 'N/D',
            'narrativa': narrativa,
        }

        # Tabla de policy rates
        if fed or ecb or boj:
            result['policy_rates'] = {}
            if fed:
                result['policy_rates']['Fed'] = self._fmt_pct(fed)
            if ecb:
                result['policy_rates']['BCE'] = self._fmt_pct(ecb)
            if boe:
                result['policy_rates']['BoE'] = self._fmt_pct(boe)
            if boj:
                result['policy_rates']['BoJ'] = self._fmt_pct(boj)
            if tpm:
                result['policy_rates']['BCCh'] = self._fmt_pct(tpm)
            result['_real'] = True

        return result

    def _generate_summary_table(self) -> List[Dict[str, Any]]:
        """Genera tabla resumen de views por segmento (datos reales si disponibles)."""
        # US Treasury yield
        ust_10y = self._val('yield_curve', 'current_curve', '10Y')
        if ust_10y is None:
            ust_10y = self._val('yield_curve', 'yields', 'DGS10')

        # Credit spreads
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_spread = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')

        # Euro yield from BCCh
        euro_10y = self._intl_yield('germany')

        # Chile BCP 10Y from BCCh
        chile_10y = self._chile_bcp('10Y')
        usa_10y_for_spread = self._intl_yield('usa') or (float(ust_10y) if ust_10y else None)
        chile_spread = None
        if chile_10y and usa_10y_for_spread:
            chile_spread = round((chile_10y - usa_10y_for_spread) * 100, 0)

        # EM: Brazil yield as proxy
        br_10y = self._intl_yield('brazil')
        em_spread = None
        if br_10y and usa_10y_for_spread:
            em_spread = round((br_10y - usa_10y_for_spread) * 100, 0)

        # Get council FI views for positioning
        fi_views = self.parser.get_fi_views()

        def _fi_view(segment_key, fallback='Sin vista'):
            """Extract view from council FI positioning."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                return v.get('view', fallback)
            return fallback

        def _fi_duration(segment_key, fallback='N/D'):
            """Extract duration stance from council FI positioning."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                dur_map = {'CORTA': 'Corta', 'NEUTRAL': 'Neutral', 'LARGA': 'Larga'}
                return dur_map.get(v.get('duration', ''), fallback)
            return fallback

        def _fi_rationale(segment_key, fallback='Sin vista'):
            """Extract rationale from council FI positioning."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                return v.get('rationale', fallback)
            return fallback

        return [
            {
                'segmento': 'US Treasuries',
                'view': _fi_view('us treasuries'),
                'duration': _fi_duration('us treasuries', 'N/D'),
                'yield': self._fmt_pct(ust_10y) if ust_10y else 'N/D',
                'spread': '-',
                'driver': _fi_rationale('us treasuries', 'Sin vista')
            },
            {
                'segmento': 'IG Corporate',
                'view': _fi_view('ig corporate'),
                'duration': _fi_duration('ig corporate', 'N/D'),
                'yield': self._fmt_pct(float(ust_10y) + float(ig_spread)/100) if (ust_10y and ig_spread) else 'N/D',
                'spread': self._fmt_bp(ig_spread) if ig_spread else 'N/D',
                'driver': _fi_rationale('ig corporate', 'Sin vista')
            },
            {
                'segmento': 'HY Corporate',
                'view': _fi_view('hy corporate'),
                'duration': _fi_duration('hy corporate', 'N/D'),
                'yield': self._fmt_pct(float(ust_10y) + float(hy_spread)/100) if (ust_10y and hy_spread) else 'N/D',
                'spread': self._fmt_bp(hy_spread) if hy_spread else 'N/D',
                'driver': _fi_rationale('hy corporate', 'Sin vista')
            },
            {
                'segmento': 'EM USD Debt',
                'view': _fi_view('em usd debt', _fi_view('em hard currency', _fi_view('em debt'))),
                'duration': _fi_duration('em usd debt', _fi_duration('em hard currency', _fi_duration('em debt', 'N/D'))),
                'yield': self._fmt_pct(br_10y) if br_10y else 'N/D',
                'spread': self._fmt_bp(em_spread) if em_spread else 'N/D',
                'driver': _fi_rationale('em usd debt', _fi_rationale('em hard currency', _fi_rationale('em debt')))
            },
            {
                'segmento': 'Chile Soberanos',
                'view': _fi_view('chile soberanos', _fi_view('chile', _fi_view('chile corporativos'))),
                'duration': _fi_duration('chile soberanos', _fi_duration('chile', _fi_duration('chile corporativos', 'N/D'))),
                'yield': self._fmt_pct(chile_10y) if chile_10y else 'N/D',
                'spread': self._fmt_bp(chile_spread) if chile_spread else 'N/D',
                'driver': _fi_rationale('chile soberanos', _fi_rationale('chile', _fi_rationale('chile corporativos')))
            },
        ]

    def _generate_key_calls(self) -> List[str]:
        """Genera key calls del mes (datos reales donde disponible)."""
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_spread = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')

        ig_yield_str = 'N/D'
        if ust_10y and ig_spread:
            ig_yield_str = self._fmt_pct(float(ust_10y) + float(ig_spread)/100)
        hy_spread_str = self._fmt_bp(hy_spread) if hy_spread else 'N/D'

        # Build key calls from council parser data
        fi_views = self.parser.get_fi_views()
        dur_stance = self.parser.get_duration_stance()
        _ht = self.parser.has_council_text() if self.parser else False

        dur_call = f"Duration: {dur_stance.get('stance', 'NEUTRAL')}" if dur_stance else (
            "Duration: N/D" if not _ht else
            f"Duration: {self.parser.search_duration_view() or 'NEUTRAL'}"
        )
        ig_v = fi_views.get('ig corporate', {}).get('view', 'NEUTRAL') if fi_views else (
            self.parser.search_credit_view('ig') or ('NEUTRAL' if _ht else 'N/D')
        )
        hy_v = fi_views.get('hy corporate', {}).get('view', 'NEUTRAL') if fi_views else (
            self.parser.search_credit_view('hy') or ('NEUTRAL' if _ht else 'N/D')
        )

        return [
            dur_call,
            f"Credito IG: {ig_v} - carry de {ig_yield_str}",
            f"Credito HY: {hy_v} - spreads en {hy_spread_str}",
        ]

    # =========================================================================
    # SECCION 2: AMBIENTE DE TASAS
    # =========================================================================

    def generate_rates_environment(self) -> Dict[str, Any]:
        """Genera sección de ambiente de tasas."""

        result = {
            'yields_globales': self._generate_global_yields(),
            'curvas': self._generate_curves_analysis(),
            'tasas_reales': self._generate_real_rates(),
            'narrativa': self._generate_rates_narrative(),
        }

        # Agregar expectativas de tasas si disponibles
        fed_exp = self._generate_fed_expectations_section()
        if fed_exp:
            result['fed_expectations'] = fed_exp

        tpm_exp = self._generate_tpm_expectations_section()
        if tpm_exp:
            result['tpm_expectations'] = tpm_exp

        # Agregar Fed Dots comparison si disponible
        dots = self._generate_fed_dots_section()
        if dots:
            result['fed_dots'] = dots

        # BCCh encuesta
        encuesta = self._generate_bcch_encuesta_section()
        if encuesta:
            result['bcch_encuesta'] = encuesta

        # Neutral rate estimates (NY Fed r-star + Cleveland Fed)
        neutral = self._generate_neutral_rate_section()
        if neutral:
            result['neutral_rate'] = neutral

        return result

    def _generate_fed_expectations_section(self) -> Optional[Dict[str, Any]]:
        """Genera sección de expectativas Fed Funds (QuantLib si disponible)."""
        fed = self._val('fed_expectations')
        if not fed or 'meetings' not in fed:
            return None

        meetings = fed['meetings']
        summary = fed.get('summary', {})

        rows = []
        for m in meetings[:8]:
            rows.append({
                'fecha': m.get('date', m.get('meeting_date', '')),
                'label': m.get('label', ''),
                'tasa_esperada': self._fmt_pct(m.get('expected_rate')),
                'forward': self._fmt_pct(m.get('forward_rate')),
                'prob_recorte': self._fmt_pct(m.get('prob_cut', m.get('probability_lower')), 1),
                'prob_mantener': self._fmt_pct(m.get('prob_hold', m.get('probability_same')), 1),
            })

        return {
            'titulo': 'Expectativas Fed Funds (FedWatch — herramienta CME que estima probabilidades de movimiento de tasas Fed)',
            'current_rate': self._fmt_pct(fed.get('current_rate')),
            'direction': summary.get('direction', ''),
            'total_moves': summary.get('total_cuts', summary.get('total_moves', summary.get('cuts_expected', ''))),
            'terminal_rate': self._fmt_pct(summary.get('terminal_rate', summary.get('tasa_terminal'))),
            'meetings': rows,
            '_real': True
        }

    def _generate_tpm_expectations_section(self) -> Optional[Dict[str, Any]]:
        """Genera sección de expectativas TPM Chile (QuantLib si disponible)."""
        tpm = self._val('tpm_expectations')
        if not tpm or 'meetings' not in tpm:
            return None

        meetings = tpm['meetings']
        summary = tpm.get('summary', {})

        rows = []
        for m in meetings[:8]:
            rows.append({
                'fecha': m.get('date', m.get('meeting_date', '')),
                'label': m.get('label', ''),
                'tasa_esperada': self._fmt_pct(m.get('expected_rate')),
                'forward': self._fmt_pct(m.get('forward_rate')),
                'prob_recorte': self._fmt_pct(m.get('prob_cut', m.get('probability_lower')), 1),
                'prob_mantener': self._fmt_pct(m.get('prob_hold', m.get('probability_same')), 1),
            })

        return {
            'titulo': 'Expectativas TPM Chile (Tasa de Política Monetaria — tasa referencia BCCh)',
            'current_rate': self._fmt_pct(tpm.get('current_rate')),
            'direction': summary.get('direction', ''),
            'total_moves': summary.get('total_cuts', summary.get('total_recortes', summary.get('recortes_esperados', ''))),
            'terminal_rate': self._fmt_pct(summary.get('terminal_rate', summary.get('tasa_terminal'))),
            'meetings': rows,
            '_real': True
        }

    def _generate_fed_dots_section(self) -> Optional[Dict[str, Any]]:
        """Genera sección Market vs Fed Dots (si disponible)."""
        dots = self._val('fed_dots')
        if not dots or 'comparison' not in dots:
            return None

        comparison = dots['comparison']
        rows = []
        if isinstance(comparison, list):
            for c in comparison:
                rows.append({
                    'horizonte': c.get('year', c.get('horizon', '')),
                    'mercado': self._fmt_pct(c.get('market_rate', c.get('market'))),
                    'fed_dots': self._fmt_pct(c.get('fed_dots_median', c.get('fed_rate', c.get('fed_dots')))),
                    'diferencia': self._fmt_bp(c.get('diff_bps', c.get('difference', c.get('diff_bp')))),
                    'señal': c.get('signal', ''),
                })

        return {
            'titulo': 'Mercado vs Fed Dots (proyecciones de tasas de los miembros de la Fed)',
            'rows': rows,
            '_real': True
        }

    def _generate_bcch_encuesta_section(self) -> Optional[Dict[str, Any]]:
        """Genera sección Market vs Encuesta BCCh (si disponible)."""
        enc = self._val('bcch_encuesta')
        if not enc or 'comparison' not in enc:
            return None

        comparison = enc['comparison']
        rows = []
        if isinstance(comparison, list):
            for c in comparison:
                rows.append({
                    'horizonte': c.get('horizon', c.get('months_ahead', '')),
                    'mercado': self._fmt_pct(c.get('market_rate')),
                    'encuesta': self._fmt_pct(c.get('encuesta_rate', c.get('survey_rate'))),
                    'diferencia': self._fmt_bp(c.get('diff_bps', c.get('difference'))),
                    'señal': c.get('signal', ''),
                })

        return {
            'titulo': 'Mercado vs Encuesta BCCh (Banco Central de Chile)',
            'rows': rows,
            '_real': True
        }

    def _get_cleveland_fed_row(self, inflation_add: float) -> dict:
        """Cleveland Fed r-star: use FRED series if available, else fallback."""
        # Try FRED Cleveland Fed expected real rate (NROUST)
        clev_real = self._val('nyfed', 'cleveland_rstar') or self._val('cleveland_rstar')
        if clev_real is not None and not (isinstance(clev_real, dict) and 'error' in clev_real):
            val = clev_real.get('value') if isinstance(clev_real, dict) else clev_real
            if val is not None:
                val = float(val)
                return {
                    'fuente': 'Cleveland Fed',
                    'r_star_real': self._fmt_pct(val),
                    'i_star_nominal': self._fmt_pct(val + inflation_add),
                    'nota': f'Real data, {clev_real.get("date", "N/D") if isinstance(clev_real, dict) else "FRED"}',
                }
        # Fallback: use NY Fed r-star as reference with range note
        return {
            'fuente': 'Cleveland Fed',
            'r_star_real': 'N/D',
            'i_star_nominal': 'N/D',
            'nota': 'Rango histórico 0.8-2.2% real — sin datos API disponibles',
        }

    def _generate_neutral_rate_section(self) -> Optional[Dict[str, Any]]:
        """Genera sección de tasa neutral (NY Fed r-star + Cleveland Fed + term premia)."""
        # Try new path (nyfed.rstar) first, then legacy (nyfed_rstar)
        rstar_data = self._val('nyfed', 'rstar') or self._val('nyfed_rstar')
        if not rstar_data or (isinstance(rstar_data, dict) and 'error' in rstar_data):
            return None

        rstar_val = rstar_data.get('value') or rstar_data.get('rstar') or rstar_data.get('r_star')
        if rstar_val is None:
            return None

        # Breakeven inflation for nominal estimate
        be_10y = self._val('inflation', 'breakeven_10y') or self._val('inflation', 'current', 'breakeven_10y')
        inflation_add = float(be_10y) if be_10y else 2.0

        rows = [
            {
                'fuente': 'NY Fed (Laubach-Williams)',
                'r_star_real': self._fmt_pct(rstar_val),
                'i_star_nominal': self._fmt_pct(rstar_val + inflation_add),
                'nota': f'Modelo dinámico, Q: {rstar_data.get("date", "N/D")}',
            },
            self._get_cleveland_fed_row(inflation_add),
        ]

        # Add term premia row if available
        tp = self._val('nyfed', 'term_premia')
        if tp and tp.get('tp_10y') is not None:
            rows.append({
                'fuente': 'ACM Term Premia (10Y)',
                'r_star_real': self._fmt_pct(tp['tp_10y']),
                'i_star_nominal': '—',
                'nota': f'Modelo Adrian-Crump-Moench, {tp.get("date", "N/D")}',
            })

        # Add GSCPI context if available
        gscpi = self._val('nyfed', 'gscpi')
        gscpi_note = ""
        if gscpi and gscpi.get('value') is not None:
            gscpi_note = f" | GSCPI: {gscpi['value']} ({gscpi.get('trend', 'N/D')})"

        return {
            'titulo': f'Tasa Neutral r-star (equilibrio){gscpi_note}',
            'rows': rows,
            '_real': True,
        }

    def _intl_yield(self, country_key: str):
        """Obtiene yield 10Y internacional de market_data['international_yields']."""
        return self._val('international_yields', country_key, 'yield_10y')

    def _intl_vs1m(self, country_key: str):
        """Obtiene cambio 1 mes de yield internacional."""
        v = self._val('international_yields', country_key, 'vs_1m')
        if v is not None:
            sign = '+' if v >= 0 else ''
            return f"{sign}{int(round(v * 100))}bp"
        return None

    def _chile_bcp(self, tenor: str):
        """Obtiene yield BCP de market_data['chile_yields']['bcp']."""
        return self._val('chile_yields', 'bcp', tenor, 'yield')

    def _chile_bcu(self, tenor: str):
        """Obtiene yield BCU de market_data['chile_yields']['bcu']."""
        return self._val('chile_yields', 'bcu', tenor, 'yield')

    def _chile_bcp_vs1m(self, tenor: str):
        """Obtiene cambio 1 mes BCP."""
        v = self._val('chile_yields', 'bcp', tenor, 'vs_1m')
        if v is not None:
            sign = '+' if v >= 0 else ''
            return f"{sign}{int(round(v * 100))}bp"
        return None

    def _chile_bcu_vs1m(self, tenor: str):
        """Obtiene cambio 1 mes BCU."""
        v = self._val('chile_yields', 'bcu', tenor, 'vs_1m')
        if v is not None:
            sign = '+' if v >= 0 else ''
            return f"{sign}{int(round(v * 100))}bp"
        return None

    def _generate_global_yields(self) -> List[Dict[str, Any]]:
        """Genera tabla de yields globales (datos reales de FRED + BCCh)."""
        # --- US Treasury (FRED yield_curve) ---
        yc = self._val('yield_curve')
        if yc and 'current_curve' in yc:
            cy = yc['current_curve']
            y2 = cy.get('2Y') or cy.get('DGS2')
            y5 = cy.get('5Y') or cy.get('DGS5')
            y10 = cy.get('10Y') or cy.get('DGS10')
            y30 = cy.get('30Y') or cy.get('DGS30')

            slopes = yc.get('slopes_bps', yc.get('slopes', {}))
            s2_10 = slopes.get('2s10s')
            slope_2_10 = s2_10

            us_row = {
                'mercado': 'US Treasury',
                'y2': self._fmt_pct(y2) if y2 else 'N/D',
                'y5': self._fmt_pct(y5) if y5 else 'N/D',
                'y10': self._fmt_pct(y10) if y10 else 'N/D',
                'y30': self._fmt_pct(y30) if y30 else 'N/D',
                'curva_2_10': self._fmt_bp(slope_2_10) if slope_2_10 is not None else 'N/D',
                '_real': True
            }
        else:
            us_row = {'mercado': 'US Treasury', 'y2': 'N/D', 'y5': 'N/D', 'y10': 'N/D', 'y30': 'N/D', 'curva_2_10': 'N/D'}

        # --- Bloomberg international curves (Bund, Gilt, JGB) ---
        bbg_curves = {}
        if self.bloomberg:
            try:
                bbg_curves = self.bloomberg.get_intl_curves()
            except Exception:
                pass

        # --- Sovereign curves from ECB Svensson / MoF Japan ---
        sov = self.market_data.get('sovereign_curves', {})
        ecb_de = sov.get('alemania', {}).get('datos', {})  # keys: 1,2,3,5,7,10,15,20,30
        mof_jp = sov.get('japon', {}).get('datos', {})      # keys: 1,2,3,5,7,10,15,20,25,30,40

        def _sov_yield(curve_data, tenor):
            """Get yield from sovereign curve data (keys are ints or strings)."""
            v = curve_data.get(tenor) or curve_data.get(str(tenor))
            return v if v is not None else None

        # --- German Bund (ECB Svensson → Bloomberg fallback → BCCh 10Y) ---
        de_10y = self._intl_yield('germany')
        de_vs1m = self._intl_vs1m('germany')
        bund_bbg = bbg_curves.get('bund', {})
        bund_row = {
            'mercado': 'German Bund',
            'y2': self._fmt_pct(_sov_yield(ecb_de, 2) or bund_bbg.get('2y')) if (_sov_yield(ecb_de, 2) or bund_bbg.get('2y')) is not None else 'N/D',
            'y5': self._fmt_pct(_sov_yield(ecb_de, 5) or bund_bbg.get('5y')) if (_sov_yield(ecb_de, 5) or bund_bbg.get('5y')) is not None else 'N/D',
            'y10': self._fmt_pct(_sov_yield(ecb_de, 10) or de_10y or bund_bbg.get('10y')) if (_sov_yield(ecb_de, 10) or de_10y or bund_bbg.get('10y')) else 'N/D',
            'y30': self._fmt_pct(_sov_yield(ecb_de, 30) or bund_bbg.get('30y')) if (_sov_yield(ecb_de, 30) or bund_bbg.get('30y')) is not None else 'N/D',
            'vs_1m': de_vs1m if de_vs1m else '-',
        }
        if ecb_de or de_10y or bund_bbg:
            bund_row['_real'] = True
            # Compute 2-10 slope if we have both tenors
            b2 = _sov_yield(ecb_de, 2)
            b10 = _sov_yield(ecb_de, 10) or de_10y
            if b2 is not None and b10 is not None:
                bund_row['curva_2_10'] = self._fmt_bp(b10 - b2)

        # --- UK Gilt (FRED 10Y fallback, no full curve without Bloomberg) ---
        uk_10y = self._intl_yield('uk')
        uk_vs1m = self._intl_vs1m('uk')
        gilt_bbg = bbg_curves.get('gilt', {})
        gilt_row = {
            'mercado': 'UK Gilt',
            'y2': self._fmt_pct(gilt_bbg.get('2y')) if gilt_bbg.get('2y') is not None else 'N/D',
            'y5': self._fmt_pct(gilt_bbg.get('5y')) if gilt_bbg.get('5y') is not None else 'N/D',
            'y10': self._fmt_pct(uk_10y) if uk_10y else (self._fmt_pct(gilt_bbg.get('10y')) if gilt_bbg.get('10y') else 'N/D'),
            'y30': self._fmt_pct(gilt_bbg.get('30y')) if gilt_bbg.get('30y') is not None else 'N/D',
            'vs_1m': uk_vs1m if uk_vs1m else '-',
        }
        if uk_10y or gilt_bbg:
            gilt_row['_real'] = True

        # --- JGB (MoF Japan full curve → Bloomberg fallback → BCCh 10Y) ---
        jp_10y = self._intl_yield('japan')
        jp_vs1m = self._intl_vs1m('japan')
        jgb_bbg = bbg_curves.get('jgb', {})
        jgb_row = {
            'mercado': 'JGB',
            'y2': self._fmt_pct(_sov_yield(mof_jp, 2) or jgb_bbg.get('2y')) if (_sov_yield(mof_jp, 2) or jgb_bbg.get('2y')) is not None else 'N/D',
            'y5': self._fmt_pct(_sov_yield(mof_jp, 5) or jgb_bbg.get('5y')) if (_sov_yield(mof_jp, 5) or jgb_bbg.get('5y')) is not None else 'N/D',
            'y10': self._fmt_pct(_sov_yield(mof_jp, 10) or jp_10y or jgb_bbg.get('10y')) if (_sov_yield(mof_jp, 10) or jp_10y or jgb_bbg.get('10y')) else 'N/D',
            'y30': self._fmt_pct(_sov_yield(mof_jp, 30) or jgb_bbg.get('30y')) if (_sov_yield(mof_jp, 30) or jgb_bbg.get('30y')) is not None else 'N/D',
            'vs_1m': jp_vs1m if jp_vs1m else '-',
        }
        if mof_jp or jp_10y or jgb_bbg:
            jgb_row['_real'] = True
            j2 = _sov_yield(mof_jp, 2)
            j10 = _sov_yield(mof_jp, 10) or jp_10y
            if j2 is not None and j10 is not None:
                jgb_row['curva_2_10'] = self._fmt_bp(j10 - j2)

        # --- Chile BCP (BCCh chile_yields) ---
        bcp_2 = self._chile_bcp('2Y')
        bcp_5 = self._chile_bcp('5Y')
        bcp_10 = self._chile_bcp('10Y')
        bcp_slope = self._val('chile_yields', 'slopes', '2s10s')

        chile_row = {
            'mercado': 'Chile BCP',
            'y2': self._fmt_pct(bcp_2) if bcp_2 else 'N/D',
            'y5': self._fmt_pct(bcp_5) if bcp_5 else 'N/D',
            'y10': self._fmt_pct(bcp_10) if bcp_10 else 'N/D',
            'curva_2_10': self._fmt_bp(bcp_slope) if bcp_slope is not None else 'N/D',
        }
        if bcp_2 or bcp_5 or bcp_10:
            chile_row['_real'] = True

        # --- SOFR Swap Curve (Bloomberg → market_data fallback) ---
        sofr_row = {'mercado': 'SOFR Swaps (tasa interbancaria EE.UU.)', 'y2': 'N/D', 'y5': 'N/D', 'y10': 'N/D', 'y30': 'N/D'}
        sofr_loaded = False
        if self.bloomberg:
            try:
                sofr = self.bloomberg.get_sofr_curve()
                if sofr:
                    sofr_row = {
                        'mercado': 'SOFR Swaps (tasa interbancaria EE.UU.)',
                        'y2': self._fmt_pct(sofr.get('2y')) if sofr.get('2y') is not None else 'N/D',
                        'y5': self._fmt_pct(sofr.get('5y')) if sofr.get('5y') is not None else 'N/D',
                        'y10': self._fmt_pct(sofr.get('10y')) if sofr.get('10y') is not None else 'N/D',
                        'y30': self._fmt_pct(sofr.get('30y')) if sofr.get('30y') is not None else 'N/D',
                        '_real': True,
                    }
                    if sofr.get('2y') is not None and sofr.get('10y') is not None:
                        sofr_slope = (sofr['10y'] - sofr['2y']) * 100
                        sofr_row['curva_2_10'] = self._fmt_bp(sofr_slope)
                    sofr_loaded = True
            except Exception:
                pass
        # Fallback: SOFR rates from fed_expectations (QuantLib-derived)
        if not sofr_loaded:
            sofr_md = self._val('fed_expectations', 'sofr_rates')
            if sofr_md and isinstance(sofr_md, dict):
                tenor_map = {'2Y': 'y2', '5Y': 'y5', '10Y': 'y10', '30Y': 'y30'}
                has_any = False
                for tenor, col in tenor_map.items():
                    v = sofr_md.get(tenor)
                    if v is not None:
                        sofr_row[col] = self._fmt_pct(v)
                        has_any = True
                if has_any:
                    sofr_row['_real'] = True
                    s2 = sofr_md.get('2Y')
                    s10 = sofr_md.get('10Y')
                    if s2 is not None and s10 is not None:
                        sofr_row['curva_2_10'] = self._fmt_bp((s10 - s2) * 100)

        return [us_row, sofr_row, bund_row, gilt_row, jgb_row, chile_row]

    def _generate_curves_analysis(self) -> Dict[str, Any]:
        """Genera análisis de curvas (slopes reales si disponibles)."""
        yc = self._val('yield_curve')

        # Narrativa dinámica si hay slopes reales
        narrativa = (
            "Las curvas de tasas muestran normalización gradual tras las inversiones de 2023-2024. "
        )
        slopes_data = yc.get('slopes_bps', yc.get('slopes', {})) if yc else {}
        if slopes_data:
            s2_10 = slopes_data.get('2s10s', {})
            val_2_10 = s2_10.get('current_bps') if isinstance(s2_10, dict) else s2_10
            if val_2_10 is not None:
                sign = '+' if float(val_2_10) > 0 else ''
                narrativa += (
                    f"La curva US 2s10s está en {sign}{int(round(float(val_2_10)))}bp. "
                )
            shape = yc.get('curve_shape', yc.get('shape', ''))
            if shape:
                narrativa += f"Forma de curva: {shape}. "
        else:
            narrativa += "Datos detallados de curva US no disponibles. "

        # Chile curve narrative based on actual slope data
        cl_slope_val = self._val('chile_yields', 'slopes', '2s10s')
        if cl_slope_val is not None:
            if cl_slope_val > 80:
                narrativa += f"Chile muestra curva muy empinada ({int(cl_slope_val)}bp 2s10s)."
            elif cl_slope_val > 30:
                narrativa += f"Chile muestra curva empinada ({int(cl_slope_val)}bp 2s10s)."
            elif cl_slope_val > -30:
                narrativa += f"Chile muestra curva plana ({int(cl_slope_val)}bp 2s10s)."
            else:
                narrativa += f"Chile muestra curva invertida ({int(cl_slope_val)}bp 2s10s)."
        else:
            narrativa += "Datos de curva Chile no disponibles."

        # Chile slope
        cl_slope = self._val('chile_yields', 'slopes', '2s10s')
        cl_forma = 'Empinada'
        if cl_slope is not None:
            if cl_slope > 80:
                cl_forma = f'Muy empinada ({int(cl_slope)}bp)'
            elif cl_slope > 30:
                cl_forma = f'Empinada ({int(cl_slope)}bp)'
            elif cl_slope > -30:
                cl_forma = f'Flat ({int(cl_slope)}bp)'
            else:
                cl_forma = f'Invertida ({int(cl_slope)}bp)'

        # Calculate US curve shape from real yield data
        curve = self.market_data.get('yield_curve', {})
        us_spread_2s10s = None
        if curve and 'current_curve' in curve:
            cc = curve['current_curve']
            y2_us = cc.get('2Y') or cc.get('DGS2')
            y10_us = cc.get('10Y') or cc.get('DGS10')
            if y2_us is not None and y10_us is not None:
                try:
                    us_spread_2s10s = float(y10_us) - float(y2_us)
                except (ValueError, TypeError):
                    pass
        if us_spread_2s10s is not None:
            if us_spread_2s10s > 0.1:
                us_forma = f'Empinada ({int(round(us_spread_2s10s * 100))}bp)'
            elif us_spread_2s10s < -0.1:
                us_forma = f'Invertida ({int(round(us_spread_2s10s * 100))}bp)'
            else:
                us_forma = f'Flat ({int(round(us_spread_2s10s * 100))}bp)'
        else:
            us_forma = 'N/D'

        # Slopes detallados — computed from data, not hardcoded
        _ht = self.parser.has_council_text() if self.parser else False
        _fi_views = self.parser.get_fi_views() if self.parser else {}
        _us_v = (_fi_views or {}).get('us treasuries', {}).get('view', 'N/D')
        _cl_v = (_fi_views or {}).get('chile soberanos', (_fi_views or {}).get('chile', (_fi_views or {}).get('chile corporativos', {}))).get('view', 'N/D') if _fi_views else 'N/D'
        # Text mining fallback for curve views
        if _us_v == 'N/D' and _ht:
            mined = self.parser.search_credit_view('us treasuries') if hasattr(self.parser, 'search_credit_view') else None
            if not mined:
                mined = self._text_mine_duration_market('us')
                _us_v = {'Corta': 'UW', 'Larga': 'OW', 'Neutral': 'NEUTRAL'}.get(mined, 'NEUTRAL')
            else:
                _us_v = mined
        if _cl_v == 'N/D' and _ht:
            mined = self._text_mine_duration_market('chile')
            _cl_v = {'Corta': 'UW', 'Larga': 'OW', 'Neutral': 'NEUTRAL'}.get(mined, 'NEUTRAL')
        por_mercado = [
            {'mercado': 'US', 'forma': us_forma, 'tendencia': '-', 'view': _us_v},
            {'mercado': 'Chile', 'forma': cl_forma, 'tendencia': '-', 'view': _cl_v},
        ]

        # Enriquecer US con forma real
        us_slopes = yc.get('slopes_bps', yc.get('slopes', {})) if yc else {}
        if us_slopes:
            for pair_name in ['2s5s', '2s10s', '5s30s', '2s30s']:
                s = us_slopes.get(pair_name, {})
                bps = s.get('current_bps') if isinstance(s, dict) else s
                if bps is not None:
                    sign = '+' if float(bps) > 0 else ''
                    por_mercado[0][f'slope_{pair_name}'] = f"{sign}{int(round(float(bps)))}bp"

            shape = yc.get('curve_shape', '')
            if shape:
                por_mercado[0]['forma'] = str(shape)

        # Swap curve Chile (if available)
        spc_data = {}
        spc_clp = self._val('chile_yields', 'spc_clp')
        spc_uf = self._val('chile_yields', 'spc_uf')
        swap_spread = self._val('chile_yields', 'swap_spread')
        if spc_clp and isinstance(spc_clp, dict):
            spc_data['clp'] = {t: self._fmt_pct(v.get('yield')) for t, v in spc_clp.items() if isinstance(v, dict) and 'yield' in v}
        if spc_uf and isinstance(spc_uf, dict):
            spc_data['uf'] = {t: self._fmt_pct(v.get('yield')) for t, v in spc_uf.items() if isinstance(v, dict) and 'yield' in v}
        if swap_spread and isinstance(swap_spread, dict):
            spc_data['spread_vs_bcp'] = {t: f"{int(v)}bp" for t, v in swap_spread.items()}

        result = {
            'narrativa': narrativa,
            'por_mercado': por_mercado,
            'carry_rolldown': []  # Requires proprietary curve model — omitted
        }
        if spc_data:
            result['chile_swap_curve'] = spc_data
        return result

    def _generate_real_rates(self) -> Dict[str, Any]:
        """Genera análisis de tasas reales (TIPS y breakevens reales si disponibles)."""
        infl = self._val('inflation')

        # Datos US reales de InflationAnalytics
        tips_10y = None
        be_10y = None
        nominal_10y = None
        if infl:
            rr = infl.get('real_rates', {})
            if isinstance(rr, dict) and 'current' in rr:
                tips_10y = rr['current'].get('tips_10y')
            bei = infl.get('breakeven_inflation', {})
            if isinstance(bei, dict) and 'current' in bei:
                be_10y = bei['current'].get('breakeven_10y')
            # Nominal = real + breakeven
            if tips_10y is not None and be_10y is not None:
                try:
                    nominal_10y = float(tips_10y) + float(be_10y)
                except (ValueError, TypeError):
                    pass

        # Historical percentile for real rates
        rr_pctile = None
        if infl and isinstance(infl.get('real_rates'), dict):
            rr_pctile = infl['real_rates'].get('percentile_5y')

        us_row = {
            'mercado': 'US 10Y TIPS',
            'yield_real': self._fmt_pct(tips_10y) if tips_10y else 'N/D',
            'breakeven': self._fmt_pct(be_10y) if be_10y else 'N/D',
            'nominal': self._fmt_pct(nominal_10y) if nominal_10y else 'N/D',
            'vs_historia': f"P{int(rr_pctile)}% (5Y)" if rr_pctile is not None else '-',
        }
        if tips_10y:
            us_row['_real'] = True

        # Chile BCU real yield + breakeven implícito
        bcu_10y = self._chile_bcu('10Y')
        bcp_10y = self._chile_bcp('10Y')
        chile_be = self._val('chile_yields', 'breakevens', '10Y')
        chile_nominal = bcp_10y

        chile_row = {
            'mercado': 'Chile BCU 10Y',
            'yield_real': self._fmt_pct(bcu_10y) if bcu_10y else 'N/D',
            'breakeven': self._fmt_pct(chile_be) if chile_be else 'N/D',
            'nominal': self._fmt_pct(chile_nominal) if chile_nominal else 'N/D',
            'vs_historia': '-',
        }
        if bcu_10y:
            chile_row['_real'] = True

        # German and UK real yields omitted — no public API for Euro/UK real yields or breakevens

        parts = []
        if tips_10y:
            parts.append(f"US 10Y TIPS real yield: {self._fmt_pct(tips_10y)}")
        if bcu_10y:
            parts.append(f"Chile BCU 10Y real yield: {self._fmt_pct(bcu_10y)}")
        narrativa = '. '.join(parts) + '.' if parts else 'Datos de tasas reales no disponibles.'

        return {
            'narrativa': narrativa,
            'datos': [us_row, chile_row]
        }

    def _generate_rates_narrative(self) -> str:
        """Genera narrativa general de tasas via Claude + datos reales."""
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        chile_10y = self._chile_bcp('10Y')

        us_str = self._fmt_pct(ust_10y) if ust_10y else 'N/D'
        cl_str = self._fmt_pct(chile_10y) if chile_10y else 'N/D'

        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        final = self.council.get('final_recommendation', '')

        if rf_panel or final:
            from narrative_engine import generate_narrative
            result = generate_narrative(
                section_name="rf_rates_narrative",
                prompt=(
                    f"Escribe un parrafo sobre el ambiente de tasas para {self.month_name} {self.year}. "
                    "Cubrir: nivel actual de yields, dinamica de curvas, y preferencia de duration. "
                    "Integrar datos cuantitativos. Maximo 60 palabras."
                    "\n\nSigue la cadena dato→interpretación→acción para cada posición de duration. Incluye horizonte temporal (táctico o estratégico) y trigger de salida."
                ),
                council_context=f"RF PANEL:\n{rf_panel[:1500]}\n\nFINAL:\n{final[:800]}",
                quant_context=f"US 10Y: {us_str} | Chile 10Y: {cl_str}",
                company_name=self.company_name,
                max_tokens=400,
            )
            if result:
                return result

        return (
            f"Los rendimientos soberanos ofrecen carry diferenciado, "
            f"con US 10Y en {us_str} y Chile 10Y en {cl_str}."
        )

    # =========================================================================
    # SECCION 3: DURATION POSITIONING
    # =========================================================================

    def generate_duration_positioning(self) -> Dict[str, Any]:
        """Genera seccion de posicionamiento de duration."""

        return {
            'view_global': self._generate_global_duration(),
            'por_mercado': self._generate_duration_by_market(),
            'trades_recomendados': self._generate_duration_trades()
        }

    def _generate_global_duration(self) -> Dict[str, Any]:
        """Genera view global de duration (duration dashboard real si disponible)."""
        dur = self._val('duration')

        # Intentar datos reales del DurationAnalytics dashboard
        dt = dur.get('duration_recommendation', dur.get('duration_target')) if dur else None
        if dt and isinstance(dt, dict):
            target = dt.get('target_years', dt.get('target_duration', 7.0))
            dr = dt.get('range', dt.get('duration_range', (6.0, 8.0)))
            vs_bm = dt.get('vs_benchmark', 'NEUTRAL')
            confidence = dt.get('confidence', 'MEDIUM')
            rationale_raw = dt.get('rationale', '')
            # Translate common English rationale patterns to Spanish
            rationale = rationale_raw
            if rationale and rationale[0].isupper() and all(c.isascii() for c in rationale[:20]):
                # Likely English — replace with Spanish equivalent
                rationale_map = {
                    'Stable growth': 'Crecimiento estable e inflación contenida soportan duration neutral',
                    'Rising inflation': 'Inflación creciente sugiere acortar duration',
                    'Slowing growth': 'Desaceleración del crecimiento favorece extensión de duration',
                    'Recession risk': 'Riesgo recesivo favorece posiciones largas en duration',
                }
                for eng_key, esp_val in rationale_map.items():
                    if eng_key.lower() in rationale.lower():
                        rationale = esp_val
                        break
                else:
                    # Generic translation fallback
                    rationale = f'Posicionamiento cuantitativo: duration objetivo {target:.1f} años (confianza: {confidence})'

            stance_map = {'LONG': 'LARGA', 'SHORT': 'CORTA', 'NEUTRAL': 'NEUTRAL'}
            stance = stance_map.get(vs_bm, 'NEUTRAL A LARGA')

            return {
                'stance': stance,
                'benchmark_duration': f"{dr[0]:.1f} años" if isinstance(dr, (list, tuple)) else '6.5 años',
                'recomendacion': f"{target:.1f} años",
                'confianza': confidence,
                'rationale': rationale if rationale else 'Posicionamiento basado en análisis cuantitativo del dashboard de duration.',
                'riesgos': [],
                '_real': True
            }

        # Intentar curve_recommendation
        if dur and 'curve_recommendation' in dur:
            cr = dur['curve_recommendation']
            # Use council parser for stance if available
            council_dur = self.parser.get_duration_stance()
            cr_stance = council_dur.get('stance', 'N/D') if council_dur else 'N/D'
            cr_bench = f"{council_dur['benchmark']:.1f} años" if (council_dur and council_dur.get('benchmark')) else 'N/D'
            cr_rec = f"{council_dur['recommendation']:.1f} años" if (council_dur and council_dur.get('recommendation')) else 'N/D'
            return {
                'stance': cr_stance,
                'benchmark_duration': cr_bench,
                'recomendacion': cr_rec,
                'posicion_curva': cr.get('trade_expression', ''),
                'confianza': cr.get('confidence', 'MEDIUM'),
                'rationale': cr.get('rationale', 'Posicionamiento de duration derivado del análisis de curva y term premium.'),
                'riesgos': cr.get('risks', ['Monitorear evolución de tasas soberanas y term premium']),
                '_real': True
            }

        # Use council parser for duration stance
        stance_data = self.parser.get_duration_stance()
        if stance_data:
            duration_text = stance_data.get('stance', 'N')
            benchmark = stance_data.get('benchmark')
            recommendation = stance_data.get('recommendation')
        else:
            duration_text = 'NEUTRAL — datos insuficientes para recomendación activa'
            benchmark = None
            recommendation = None

        # Generate risks dynamically
        from narrative_engine import generate_data_driven_narrative
        import json as _json
        us_10y = self._val('yield_curve', 'us_10y') or self._val('chile_rates', 'ust_10y')
        quant_ctx = f"UST 10Y: {us_10y}%" if us_10y else "Datos de tasas limitados"
        risks_result = generate_data_driven_narrative(
            section_name="rf_duration_risks",
            prompt='Genera 2 riesgos de duration basados en datos. JSON: ["riesgo 1", "riesgo 2"]. SOLO JSON.',
            quant_context=quant_ctx,
            company_name=self.company_name,
            max_tokens=400,
        )
        riesgos = ['Monitorear niveles de tasas soberanas para ajustar duration']
        if risks_result:
            try:
                cleaned = risks_result.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                parsed = _json.loads(cleaned.strip())
                if isinstance(parsed, list) and len(parsed) >= 1:
                    riesgos = parsed
            except (_json.JSONDecodeError, Exception):
                pass

        return {
            'stance': duration_text,
            'benchmark_duration': f"{benchmark:.1f} años" if benchmark else 'N/D',
            'recomendacion': f"{recommendation:.1f} años" if recommendation else 'N/D',
            'rationale': f'Basado en UST 10Y {us_10y}%' if us_10y else 'Datos insuficientes',
            'riesgos': riesgos
        }

    def _text_mine_duration_market(self, market: str) -> str:
        """Text-mine duration view for a specific market from RF panel text."""
        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        final = self.council.get('final_recommendation', '')
        text = f"{rf_panel} {final}".lower()
        if not text.strip():
            return 'Neutral'

        import re as _re

        # Market-specific patterns
        market_keywords = {
            'us': ['us ', 'usa', 'treasury', 'treasuries', 'estados unidos', 'ust ', 'norteamerica'],
            'chile': ['chile', 'bcp', 'bcu', 'tpm', 'bcch', 'chileno', 'soberano'],
        }
        keywords = market_keywords.get(market.lower(), [market.lower()])

        # Find sentences mentioning the market
        sentences = _re.split(r'[.;]\s*', text)
        market_sentences = [s for s in sentences if any(kw in s for kw in keywords)]
        context = ' '.join(market_sentences) if market_sentences else text

        # Duration patterns in context
        if _re.search(r'(short\s+duration|duraci[oó]n\s+corta|infraponderar\s+duraci[oó]n|reducir\s+duraci[oó]n)', context):
            return 'Corta'
        if _re.search(r'(long\s+duration|duraci[oó]n\s+larga|sobreponderar\s+duraci[oó]n|extender\s+duraci[oó]n)', context):
            return 'Larga'
        if _re.search(r'(neutral\s+duration|duraci[oó]n\s+neutral|mantener\s+duraci[oó]n)', context):
            return 'Neutral'

        # Broader signals from market context
        if market_sentences:
            if _re.search(r'(cautel|defensiv|corta|reducir|infraponderar)', context):
                return 'Corta'
            if _re.search(r'(constructiv|extender|sobreponderar|larga|largo plazo)', context):
                return 'Larga'
        return 'Neutral'

    def _text_mine_duration_rationale(self, market: str) -> str:
        """Text-mine a rationale snippet for a market's duration from RF panel."""
        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        if not rf_panel:
            return 'Posicionamiento basado en análisis del comité'

        import re as _re
        market_keywords = {
            'us': ['us ', 'usa', 'treasury', 'treasuries', 'estados unidos', 'ust '],
            'chile': ['chile', 'bcp', 'bcu', 'tpm', 'bcch'],
        }
        keywords = market_keywords.get(market.lower(), [market.lower()])
        sentences = _re.split(r'[.]\s*', rf_panel)
        for s in sentences:
            if any(kw in s.lower() for kw in keywords) and len(s.strip()) > 20:
                clean = s.strip()
                if len(clean) > 120:
                    clean = clean[:117] + '...'
                return clean
        return 'Posicionamiento basado en análisis del comité'

    def _generate_duration_by_market(self) -> List[Dict[str, Any]]:
        """Genera posicionamiento de duration por mercado (from council)."""
        fi_views = self.parser.get_fi_views()
        dur_stance = self.parser.get_duration_stance() or {}
        _ht = self.parser.has_council_text() if self.parser else False
        _fallback = 'N/D'

        # Global duration benchmark/recommendation from DURATION block
        benchmark = dur_stance.get('benchmark')
        recommendation = dur_stance.get('recommendation')
        stance_text = dur_stance.get('stance', '')

        bench_str = f"{benchmark:.1f}Y" if benchmark else _fallback
        rec_str = f"{recommendation:.1f}Y" if recommendation else _fallback

        # Derive curve position from stance text
        curve_pos = _fallback
        if stance_text:
            sl = stance_text.lower()
            if '2-5' in sl or 'belly' in sl or 'medio' in sl:
                curve_pos = 'Belly (2-5Y)'
            elif 'steep' in sl or 'empinamiento' in sl:
                curve_pos = 'Steepener'
            elif 'flat' in sl or 'aplanamiento' in sl:
                curve_pos = 'Flattener'
            elif 'larg' in sl or 'long' in sl or '10' in sl:
                curve_pos = 'Larga (10Y+)'
            elif 'cort' in sl or 'short' in sl or 'front' in sl:
                curve_pos = 'Corta (0-2Y)'
            else:
                curve_pos = stance_text[:50]

        def _dur_view(segment_key):
            """Get duration view from council for a segment."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                dur_map = {'CORTA': 'Corta', 'NEUTRAL': 'Neutral', 'LARGA': 'Larga'}
                return dur_map.get(v.get('duration', ''), _fallback)
            return _fallback

        def _dur_rationale(segment_key):
            """Get rationale from council for a segment."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                rat = v.get('rationale', '')
                if rat:
                    return rat
            return _fallback

        def _view_label(segment_key):
            """Get OW/NEUTRAL/UW view from council."""
            if fi_views:
                v = fi_views.get(segment_key, {})
                return v.get('view', _fallback)
            return _fallback

        # US: try council parser, then text mining
        us_dur = _dur_view('us treasuries')
        us_rat = _dur_rationale('us treasuries')
        if us_dur == _fallback and _ht:
            us_dur = self._text_mine_duration_market('us')
        if us_rat == _fallback and _ht:
            us_rat = self._text_mine_duration_rationale('us')

        # Chile: try multiple segment keys, then text mining
        _cl_dur = _dur_view('chile soberanos')
        if _cl_dur == _fallback:
            _cl_dur = _dur_view('chile')
        if _cl_dur == _fallback:
            _cl_dur = _dur_view('chile corporativos')
        if _cl_dur == _fallback and _ht:
            _cl_dur = self._text_mine_duration_market('chile')

        _cl_rat = _dur_rationale('chile soberanos')
        if _cl_rat == _fallback:
            _cl_rat = _dur_rationale('chile')
        if _cl_rat == _fallback:
            _cl_rat = _dur_rationale('chile corporativos')
        if _cl_rat == _fallback and _ht:
            _cl_rat = self._text_mine_duration_rationale('chile')

        _cl_view = _view_label('chile soberanos')
        if _cl_view == _fallback:
            _cl_view = _view_label('chile')

        return [
            {
                'mercado': 'Estados Unidos',
                'duration_view': us_dur,
                'benchmark': bench_str,
                'recomendacion': rec_str,
                'posicion_curva': curve_pos,
                'rationale': us_rat
            },
            {
                'mercado': 'Chile',
                'duration_view': _cl_dur,
                'benchmark': bench_str,
                'recomendacion': _cl_view if _cl_view != _fallback else rec_str,
                'posicion_curva': curve_pos,
                'rationale': _cl_rat
            },
        ]

    def _generate_duration_trades(self) -> List[Dict[str, Any]]:
        """Genera trades de duration recomendados (from council views)."""
        fi_views = self.parser.get_fi_views()
        dur_stance = self.parser.get_duration_stance() or {}
        if not fi_views:
            return []

        # Map segments to instruments and extract carry from market data
        instrument_map = {
            'us treasuries': 'UST 2Y-5Y (ETF: IEI/VGIT)',
            'ig corporate': 'LQD / VCIT (IG Corporate ETF)',
            'hy corporate': 'HYG / JNK (HY ETF)',
            'em debt': 'EMB / VWOB (EM Sovereign USD)',
            'chile soberanos': 'BCP-5 / BCP-10 (Bolsa)',
            'chile corporativos': 'FM Deuda Corp Chile',
        }

        # Try to get SOFR/spread data for carry estimates
        sofr_data = self.market_data.get('sofr_curve', {}) or self.market_data.get('bbg_sofr_curve', {})
        credit = self._val('credit_spreads')

        def _carry_estimate(segment, view_data):
            """Estimate 3M carry from available spread/yield data."""
            seg_l = segment.lower()
            if 'ig' in seg_l and credit:
                ig_all = credit.get('ig_all_oas') or credit.get('ig', {}).get('all', {}).get('oas')
                if ig_all:
                    return f"~{ig_all:.0f}bp/yr"
            if 'hy' in seg_l and credit:
                hy_all = credit.get('hy_all_oas') or credit.get('hy', {}).get('all', {}).get('oas')
                if hy_all:
                    return f"~{hy_all:.0f}bp/yr"
            if 'chile' in seg_l:
                bcp5 = self._chile_bcp('5Y')
                if bcp5:
                    return f"~{bcp5:.2f}% (BCP-5)"
            return 'Ver fundamento'

        trades = []
        for segment, view in fi_views.items():
            v = view.get('view', '')
            if v not in ('OW', 'UW'):
                continue
            direction = 'Long' if v == 'OW' else 'Short'
            rationale = view.get('rationale', '')
            trades.append({
                'trade': f'{direction} {segment.title()}',
                'instrumento': instrument_map.get(segment.lower(), segment.title()),
                'carry': _carry_estimate(segment, view),
                'target': '-25bp vs actual',
                'stop': '+15bp vs actual',
                'rationale': rationale if rationale else 'Posición basada en análisis del comité',
            })

        return trades[:6]  # Max 6 trades

    # =========================================================================
    # SECCION 4: CREDITO
    # =========================================================================

    def generate_credit_analysis(self) -> Dict[str, Any]:
        """Genera sección de crédito."""

        result = {
            'investment_grade': self._generate_ig_analysis(),
            'high_yield': self._generate_hy_analysis(),
            'por_sector': self._generate_credit_by_sector(),
            'cds_spreads': self._generate_cds_table(),
            'bid_ask_liquidity': self._generate_liquidity_analysis(),
            'refinancing_calendar': self._generate_refinancing_calendar(),
            'narrativa': self._generate_credit_narrative()
        }

        # Agregar quality rotation si disponible
        cs = self._val('credit_spreads')
        if cs and 'quality_rotation' in cs:
            qr = cs['quality_rotation']
            if isinstance(qr, dict) and 'error' not in qr:
                result['quality_rotation'] = qr

        # Agregar credit por duration bucket si disponible
        cd = self._val('credit_duration')
        if cd and 'error' not in cd:
            result['credit_by_duration'] = cd

        return result

    def _generate_cds_table(self) -> Dict[str, Any]:
        """Genera tabla de CDS 5Y por pais (Bloomberg data)."""
        datos = []
        # Try Bloomberg structured data first
        bbg_cds = self.market_data.get('bbg_cds', {})
        if not bbg_cds and self.bloomberg:
            try:
                bbg_cds = self.bloomberg.get_cds_data()
            except Exception:
                pass

        if bbg_cds:
            for pais, val in bbg_cds.items():
                if val is not None:
                    datos.append({'pais': pais, 'cds_5y_bps': round(float(val), 1)})

        return {
            'titulo': 'CDS (Credit Default Swaps) Soberanos 5Y',
            'fecha': self.date.strftime('%Y-%m-%d'),
            'nota': '' if datos else 'Sin datos CDS disponibles.',
            'datos': datos,
        }

    def _generate_liquidity_analysis(self) -> Dict[str, Any]:
        """Genera analisis de liquidez — datos propietarios, recomendaciones via Sonnet."""
        from narrative_engine import generate_data_driven_narrative
        import json as _json

        # Generate recommendations dynamically based on available spread data
        ig_bps = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        vix = self._val('chile_rates', 'vix') or self._val('risk', 'vix')
        quant_ctx = f"IG spread: {ig_bps:.0f}bps" if ig_bps else ""
        if hy_bps:
            quant_ctx += f" | HY spread: {hy_bps:.0f}bps"
        if vix:
            quant_ctx += f" | VIX: {vix}"

        recs = []
        if quant_ctx:
            result = generate_data_driven_narrative(
                section_name="rf_liquidity_recs",
                prompt='Genera 3 recomendaciones de liquidez para RF basadas en spreads y VIX. JSON: ["rec1", "rec2", "rec3"]. SOLO JSON.',
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
                    if isinstance(parsed, list):
                        recs = parsed
                except (_json.JSONDecodeError, Exception):
                    pass
        if not recs:
            recs = ['Monitorear condiciones de liquidez y spreads de crédito']

        return {
            'titulo': 'Análisis de Liquidez por Segmento (facilidad de compra/venta sin impacto en precio)',
            'nota': 'Datos de liquidez/bid-ask requieren suscripción Bloomberg/Refinitiv — no disponible via API pública.',
            'datos': [],
            'recomendaciones': recs
        }

    def _generate_refinancing_calendar(self) -> Dict[str, Any]:
        """Genera calendario de vencimientos — datos propietarios, observaciones via Sonnet."""
        from narrative_engine import generate_data_driven_narrative
        import json as _json

        ig_bps = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_bps = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        quant_ctx = ""
        if ig_bps:
            quant_ctx += f"IG spread: {ig_bps:.0f}bps"
        if hy_bps:
            quant_ctx += f" | HY spread: {hy_bps:.0f}bps"

        obs = ['Monitorear condiciones de refinanciamiento corporativo']
        if quant_ctx:
            result = generate_data_driven_narrative(
                section_name="rf_refi_obs",
                prompt='Genera 2 observaciones sobre refinanciamiento basadas en spreads. JSON: ["obs1", "obs2"]. SOLO JSON.',
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
                    if isinstance(parsed, list):
                        obs = parsed
                except (_json.JSONDecodeError, Exception):
                    pass

        return {
            'titulo': 'Calendario de Refinanciamiento',
            'nota': 'Datos de vencimientos requieren suscripción Bloomberg/Refinitiv — no disponible via API pública.',
            'global_maturity_wall': {},
            'chile_vencimientos': [],
            'emisores_monitoreados': [],
            'observaciones': obs
        }

    def _generate_ig_analysis(self) -> Dict[str, Any]:
        """Genera análisis de Investment Grade (spreads reales de FRED si disponibles)."""
        cs = self._val('credit_spreads')

        # Intentar spreads reales de CreditSpreadAnalytics
        ig_total_bps = None
        ig_aaa = None
        ig_aa = None
        ig_a = None
        ig_bbb = None
        ig_pctile = None
        ig_signal = None

        if cs and 'ig_breakdown' in cs:
            ig = cs['ig_breakdown']
            if isinstance(ig, dict):
                total = ig.get('total', {})
                ig_total_bps = total.get('current_bps')
                ig_pctile = total.get('percentile_5y')
                ig_signal = total.get('signal')
                # By rating
                for key, var_name in [('AAA', 'ig_aaa'), ('AA', 'ig_aa'), ('A', 'ig_a'), ('BBB', 'ig_bbb')]:
                    rating_data = ig.get(key, ig.get(key.lower(), {}))
                    if isinstance(rating_data, dict):
                        locals()[var_name] = rating_data.get('current_bps')

        spread_str = self._fmt_bp(ig_total_bps) if ig_total_bps else 'N/D'
        vs_hist = f"Percentil {int(ig_pctile)}%" if ig_pctile else 'N/D'

        narrativa = f"Investment Grade: spread en {spread_str}"
        if ig_signal:
            narrativa += f" (señal: {ig_signal})"
        narrativa += "."

        # Compute yield_total from UST 10Y + IG spread (real data)
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        ig_yield_total = 'N/D'
        if ust_10y and ig_total_bps:
            ig_yield_total = self._fmt_pct(float(ust_10y) + float(ig_total_bps) / 100)

        # Get IG view from council parser
        fi_views = self.parser.get_fi_views()
        ig_view = fi_views.get('ig corporate', {}) if fi_views else {}
        ig_council_view = ig_view.get('view', 'Sin vista')

        result = {
            'view': ig_council_view,
            'spread_actual': spread_str,
            'spread_vs_historia': vs_hist,
            'yield_total': ig_yield_total,
            'default_rate': 'N/D',
            'narrativa': narrativa,
            'fundamentales': [],  # Proprietary data — omitted
            'tecnicos': {}  # Proprietary data — omitted
        }

        # Agregar por_rating real si disponible
        if cs and 'ig_breakdown' in cs:
            ig = cs['ig_breakdown']
            por_rating = []
            for key in ['AAA', 'AA', 'A', 'BBB']:
                rd = ig.get(key, ig.get(key.lower(), {}))
                if isinstance(rd, dict) and 'current_bps' in rd:
                    por_rating.append({
                        'rating': key,
                        'spread': self._fmt_bp(rd['current_bps']),
                        'percentil': f"{int(rd.get('percentile_5y', 0))}%" if rd.get('percentile_5y') else 'N/D',
                        'señal': rd.get('signal', ''),
                    })
            if por_rating:
                result['por_rating_real'] = por_rating
                result['_real'] = True

        return result

    def _generate_hy_analysis(self) -> Dict[str, Any]:
        """Genera análisis de High Yield (spreads reales de FRED si disponibles)."""
        cs = self._val('credit_spreads')

        hy_total_bps = None
        hy_pctile = None
        hy_signal = None
        hy_bb = None
        hy_b = None
        hy_ccc = None

        if cs and 'hy_breakdown' in cs:
            hy = cs['hy_breakdown']
            if isinstance(hy, dict):
                total = hy.get('total', {})
                hy_total_bps = total.get('current_bps')
                hy_pctile = total.get('percentile_5y')
                hy_signal = total.get('signal')
                bb_d = hy.get('BB', hy.get('bb', {}))
                b_d = hy.get('B', hy.get('b', {}))
                ccc_d = hy.get('CCC', hy.get('ccc', {}))
                hy_bb = bb_d.get('current_bps') if isinstance(bb_d, dict) else None
                hy_b = b_d.get('current_bps') if isinstance(b_d, dict) else None
                hy_ccc = ccc_d.get('current_bps') if isinstance(ccc_d, dict) else None

        spread_str = self._fmt_bp(hy_total_bps) if hy_total_bps else 'N/D'
        vs_hist = f"Percentil {int(hy_pctile)}%" if hy_pctile else 'N/D'

        narrativa = f"High Yield spreads en {spread_str} ({vs_hist} vs historia). "

        # Get HY sub-rating views from council parser
        hy_rating_views = {}
        if self.parser:
            fi = self.parser.get_fi_views()
            if fi:
                for key in ['hy bb', 'hy_bb', 'hy b', 'hy_b', 'hy ccc', 'hy_ccc']:
                    if key in fi:
                        normalized = key.replace('_', ' ').split()[-1].upper()  # BB, B, CCC
                        hy_rating_views[normalized] = fi[key]

        # Build preference narrative from council data
        if hy_rating_views:
            prefs = [f"{r}: {v.get('view', 'N/D')}" for r, v in hy_rating_views.items()]
            narrativa += f"Preferencias por rating: {', '.join(prefs)}."
        else:
            narrativa += "Sin preferencia definida por el comité a nivel sub-rating."

        # HY overall view from council (used as fallback for sub-ratings)
        fi_all = self.parser.get_fi_views() or {}
        hy_overall = fi_all.get('hy corporate', {})
        hy_overall_view = hy_overall.get('view', 'N/D')
        hy_overall_rationale = hy_overall.get('rationale', 'N/D')

        # HY by rating — use council sub-rating views if available, fallback to overall
        por_rating = [
            {
                'rating': 'BB',
                'spread': self._fmt_bp(hy_bb) if hy_bb else 'N/D',
                'view': hy_rating_views.get('BB', {}).get('view', hy_overall_view),
                'comentario': hy_rating_views.get('BB', {}).get('rationale', 'Mejor calidad HY' if hy_overall_view == 'UW' else hy_overall_rationale),
            },
            {
                'rating': 'B',
                'spread': self._fmt_bp(hy_b) if hy_b else 'N/D',
                'view': hy_rating_views.get('B', {}).get('view', hy_overall_view),
                'comentario': hy_rating_views.get('B', {}).get('rationale', hy_overall_rationale),
            },
            {
                'rating': 'CCC',
                'spread': self._fmt_bp(hy_ccc) if hy_ccc else 'N/D',
                'view': hy_rating_views.get('CCC', {}).get('view', 'UW' if hy_overall_view == 'UW' else hy_overall_view),
                'comentario': hy_rating_views.get('CCC', {}).get('rationale', 'Mayor riesgo default' if hy_overall_view == 'UW' else hy_overall_rationale),
            },
        ]

        # Compute yield_total from UST 10Y + HY spread (real data)
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        hy_yield_total = 'N/D'
        if ust_10y and hy_total_bps:
            hy_yield_total = self._fmt_pct(float(ust_10y) + float(hy_total_bps) / 100)

        # Get HY view from council parser
        fi_views = self.parser.get_fi_views()
        hy_view = fi_views.get('hy corporate', {}) if fi_views else {}
        hy_council_view = hy_view.get('view', 'Sin vista')

        result = {
            'view': hy_council_view,
            'spread_actual': spread_str,
            'spread_vs_historia': vs_hist,
            'yield_total': hy_yield_total,
            'default_rate': 'N/D',
            'distressed_ratio': 'N/D',
            'narrativa': narrativa,
            'fundamentales': [],  # Proprietary data — omitted
            'por_rating': por_rating
        }

        if hy_total_bps:
            result['_real'] = True

        return result

    def _get_bbg_sector_oas(self) -> Dict[str, Dict[str, str]]:
        """Get Bloomberg sector OAS data as {sector: {ig: str, hy: str}}."""
        bbg_cs = self.market_data.get('bbg_credit_spreads', {})
        if not bbg_cs and self.bloomberg:
            try:
                bbg_cs = self.bloomberg.get_sector_spreads()
            except Exception:
                pass
        if not bbg_cs:
            return {}
        # Map Bloomberg keys → standard sector names
        sector_map = {
            'financiero': 'Financials', 'industrial': 'Industrials',
            'utilities': 'Utilities', 'tecnologia': 'Technology',
            'salud': 'Healthcare', 'energia': 'Energy',
        }
        result = {}
        for bbg_key, val in bbg_cs.items():
            # Parse "Financiero IG" / "Financiero HY" / "Total IG" etc.
            parts = bbg_key.lower().split()
            if len(parts) >= 2:
                sector_raw = parts[0]
                quality = parts[-1]  # ig or hy
                sector_name = sector_map.get(sector_raw, sector_raw.title())
                if sector_name not in result:
                    result[sector_name] = {}
                if quality == 'ig':
                    result[sector_name]['ig'] = self._fmt_bp(val)
                elif quality == 'hy':
                    result[sector_name]['hy'] = self._fmt_bp(val)
        return result

    def _generate_credit_by_sector(self) -> List[Dict[str, Any]]:
        """Genera analisis de credito por sector desde council parser + Bloomberg OAS."""
        # Try to get sector views from council
        sector_views = self.parser.get_sector_views() if self.parser else None

        # Get Bloomberg OAS data
        bbg_oas = self._get_bbg_sector_oas()

        # Standard sector list for credit analysis
        standard_sectors = [
            'Financials', 'Technology', 'Healthcare', 'Industrials',
            'Consumer', 'Energy', 'Utilities', 'Real Estate',
        ]

        if sector_views or bbg_oas:
            sectors = []
            seen = set()
            for std in standard_sectors:
                key = std.lower()
                sv = (sector_views or {}).get(key, {})
                oas = bbg_oas.get(std, {})
                ig_str = oas.get('ig', 'N/D')
                hy_str = oas.get('hy', 'N/D')
                spread_str = ig_str
                if ig_str != 'N/D' and hy_str != 'N/D':
                    spread_str = f"IG: {ig_str} / HY: {hy_str}"

                if sv or oas:
                    sectors.append({
                        'sector': std,
                        'view': sv.get('view', 'N/D'),
                        'spread_ig': spread_str,
                        'fundamentales': sv.get('rationale', 'N/D'),
                        'driver': 'N/D',
                    })
                    seen.add(key)
            # Extra sectors from council not in standard list
            if sector_views:
                for key, sv in sector_views.items():
                    if key not in seen:
                        sectors.append({
                            'sector': key.title(),
                            'view': sv.get('view', 'N/D'),
                            'spread_ig': 'N/D',
                            'fundamentales': sv.get('rationale', 'N/D'),
                            'driver': 'N/D',
                        })
            if sectors:
                return sectors

        # No council sector views and no Bloomberg — return minimal placeholder
        return [
            {'sector': 'Sin recomendacion sectorial', 'view': 'N/D',
             'spread_ig': 'N/D', 'fundamentales': 'Council no emitio vistas sectoriales de credito',
             'driver': 'N/D'},
        ]

    def _generate_credit_narrative(self) -> str:
        """Genera narrativa general de credito (dinámica con datos reales)."""
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_spread = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')

        ig_yield_str = 'N/D'
        if ust_10y and ig_spread:
            ig_yield_str = self._fmt_pct(float(ust_10y) + float(ig_spread)/100)
        ig_spread_str = self._fmt_bp(ig_spread) if ig_spread else 'N/D'
        hy_spread_str = self._fmt_bp(hy_spread) if hy_spread else 'N/D'

        # Dynamic narrative via Claude
        from narrative_engine import generate_narrative
        narrative = generate_narrative(
            section_name="rf_credit_narrative",
            prompt=(
                "Escribe un parrafo de 2-3 oraciones sobre el mercado de credito corporativo. "
                "Incluye IG spread, HY spread, y vista sectorial. "
                "Usa SOLO los datos proporcionados. NO inventes preferencias sectoriales."
                "\n\nIncluye riesgo por posición con trigger cuantificado. Explica terminología: IG (investment grade), HY (high yield), OAS (option-adjusted spread), bps (puntos base) en primera mención."
            ),
            council_context=self.council.get('panel_outputs', {}).get('rf', '')[:1500],
            quant_context=f"IG spread: {ig_spread_str}, HY spread: {hy_spread_str}, IG yield: {ig_yield_str}",
            company_name=self.company_name,
            max_tokens=400,
        )
        if narrative:
            return narrative
        # Minimal fallback — data only, no opinions
        return (
            f"Investment Grade: carry {ig_yield_str} (spread {ig_spread_str}). "
            f"High Yield: spread {hy_spread_str}. "
            "Ver recomendaciones sectoriales del comité."
        )

    # =========================================================================
    # SECCION 5: MERCADOS EMERGENTES
    # =========================================================================

    def generate_em_debt(self) -> Dict[str, Any]:
        """Genera seccion de deuda emergente."""

        return {
            'hard_currency': self._generate_em_hard_currency(),
            'local_currency': self._generate_em_local_currency(),
            'por_pais': self._generate_em_by_country(),
            'narrativa': self._generate_em_narrative()
        }

    def _generate_em_hard_currency(self) -> Dict[str, Any]:
        """Genera analisis de EM hard currency (yields reales BCCh)."""
        usa_10y = self._intl_yield('usa')
        br_10y = self._intl_yield('brazil')

        # Usar Brasil 10Y como proxy EMBIG
        em_yield = br_10y
        em_spread = None
        if br_10y and usa_10y:
            em_spread = round((br_10y - usa_10y) * 100, 0)

        spread_str = self._fmt_bp(em_spread) if em_spread else 'N/D'
        yield_str = self._fmt_pct(em_yield) if em_yield else 'N/D'

        # Get EM view from council parser
        fi_views = self.parser.get_fi_views()
        em_v = 'Sin vista'
        em_rationale = ''
        if fi_views:
            em_data = fi_views.get('em usd debt', fi_views.get('em hard currency', fi_views.get('em debt', {})))
            em_v = em_data.get('view', 'Sin vista')
            em_rationale = em_data.get('rationale', '')

        em_rec = f" Postura: {em_v}." if em_v != 'Sin vista' else ''
        em_rat = f" {em_rationale}" if em_rationale else ''
        return {
            'view': em_v,
            'indice': 'EMBIG Diversified',
            'spread': spread_str,
            'yield': yield_str,
            'duration': 'N/D',
            'narrativa': (
                f"Deuda EM en dólares: spread de {spread_str} sobre Treasuries"
                + (f", yield de {yield_str}" if yield_str != 'N/D' else '')
                + f".{em_rec}{em_rat}"
            ),
            'soberanos_vs_corporativos': {
                'soberanos_view': 'N/D',
                'soberanos_spread': spread_str,
                'corporativos_view': 'N/D',
                'corporativos_spread': 'N/D',
                'preferencia': 'N/D'
            },
            '_real': bool(em_yield),
        }

    def _generate_em_local_currency(self) -> Dict[str, Any]:
        """Genera analisis de EM local currency (Chile yield real de BCCh)."""
        chile_10y = self._chile_bcp('10Y')
        chile_str = self._fmt_pct(chile_10y) if chile_10y else 'N/D'

        # Get EM yields from BCCh where available
        br_10y = self._intl_yield('brazil')
        mx_10y = self._intl_yield('mexico')

        # Get EM local currency view from council parser (fallback to general EM)
        fi_views = self.parser.get_fi_views()
        em_lc_v = 'Sin vista'
        if fi_views:
            em_lc_data = fi_views.get('em local currency', fi_views.get('em lc', fi_views.get('em debt', {})))
            em_lc_v = em_lc_data.get('view', 'Sin vista')

        em_lc_label = f"Postura EM: {em_lc_v}." if em_lc_v != 'Sin vista' else ''
        return {
            'view': em_lc_v,
            'yield_promedio': 'N/D',
            'fx_view': 'N/D',
            'narrativa': f"Deuda EM en moneda local. {em_lc_label}",
            'carry_trades': [
                {'pais': 'Brasil', 'yield': self._fmt_pct(br_10y) if br_10y else 'N/D', 'fx_view': 'N/D', 'carry_ajustado': 'N/D'},
                {'pais': 'Mexico', 'yield': self._fmt_pct(mx_10y) if mx_10y else 'N/D', 'fx_view': 'N/D', 'carry_ajustado': 'N/D'},
                {'pais': 'Chile', 'yield': chile_str, 'fx_view': 'N/D', 'carry_ajustado': 'N/D'},
            ]
        }

    def _generate_em_by_country(self) -> List[Dict[str, Any]]:
        """Genera views por pais EM (yields reales de BCCh + council views)."""
        usa_10y = self._intl_yield('usa')
        fi_views = self.parser.get_fi_views() or {}

        # Get EM debt view from council (applies as default HC view)
        em_view = fi_views.get('em debt', {})
        em_default_view = em_view.get('view', 'N/D')
        em_rationale = em_view.get('rationale', '')

        # Chile-specific views from council
        chile_fi = fi_views.get('chile soberanos', {})
        chile_view = chile_fi.get('view', em_default_view)
        chile_driver = chile_fi.get('rationale', em_rationale) or 'N/D'

        def _spread(country_key):
            cy = self._intl_yield(country_key)
            if cy and usa_10y:
                return round((cy - usa_10y) * 100, 0)
            return None

        # Chile: use BCP 10Y for local currency
        chile_lc = self._chile_bcp('10Y')
        chile_spread = None
        if chile_lc and usa_10y:
            chile_spread = round((chile_lc - usa_10y) * 100, 0)

        br_10y = self._intl_yield('brazil')
        mx_10y = self._intl_yield('mexico')
        pe_10y = self._intl_yield('peru')
        co_10y = self._intl_yield('colombia')

        # EMBI spreads from BCRP if available
        embi = self.market_data.get('bcrp_embi', {})

        def _embi_spread(country_key, fallback_spread):
            v = embi.get(country_key)
            if v is not None:
                return self._fmt_bp(v)
            return self._fmt_bp(fallback_spread) if fallback_spread else 'N/D'

        return [
            {
                'pais': 'Chile',
                'hc_view': chile_view,
                'lc_view': chile_view,
                'yield_hc': self._fmt_pct(chile_lc) if chile_lc else 'N/D',
                'yield_lc': self._fmt_pct(chile_lc) if chile_lc else 'N/D',
                'spread': _embi_spread('chile', chile_spread),
                'rating': 'A',
                'driver': chile_driver[:80] if len(chile_driver) > 80 else chile_driver,
                'riesgo': 'Politica fiscal' if chile_view else 'N/D',
                '_real': bool(chile_lc),
            },
            {
                'pais': 'Mexico',
                'hc_view': em_default_view,
                'lc_view': em_default_view,
                'yield_hc': self._fmt_pct(mx_10y) if mx_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': _embi_spread('mexico', _spread('mexico')),
                'rating': 'BBB',
                'driver': em_rationale[:80] if em_rationale else 'N/D',
                'riesgo': 'Nearshoring / fiscal',
                '_real': bool(mx_10y),
            },
            {
                'pais': 'Brasil',
                'hc_view': em_default_view,
                'lc_view': em_default_view,
                'yield_hc': self._fmt_pct(br_10y) if br_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': _embi_spread('brasil', _spread('brazil')),
                'rating': 'BB',
                'driver': em_rationale[:80] if em_rationale else 'N/D',
                'riesgo': 'Fiscal / tipo de cambio',
                '_real': bool(br_10y),
            },
            {
                'pais': 'Peru',
                'hc_view': em_default_view,
                'lc_view': em_default_view,
                'yield_hc': self._fmt_pct(pe_10y) if pe_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': _embi_spread('peru', _spread('peru')),
                'rating': 'BBB',
                'driver': em_rationale[:80] if em_rationale else 'N/D',
                'riesgo': 'Politico / minero',
                '_real': bool(pe_10y),
            },
            {
                'pais': 'Colombia',
                'hc_view': em_default_view,
                'lc_view': em_default_view,
                'yield_hc': self._fmt_pct(co_10y) if co_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': _embi_spread('colombia', _spread('colombia')),
                'rating': 'BB+',
                'driver': em_rationale[:80] if em_rationale else 'N/D',
                'riesgo': 'Fiscal / seguridad',
                '_real': bool(co_10y),
            },
        ]

    def _generate_em_narrative(self) -> str:
        """Genera narrativa de EM debt — datos reales + council view."""
        chile_10y = self._chile_bcp('10Y')
        mx_10y = self._intl_yield('mexico')
        br_10y = self._intl_yield('brazil')

        # Build data-only narrative, no positioning opinions
        parts = []
        if chile_10y:
            parts.append(f"Chile 10Y: {self._fmt_pct(chile_10y)}.")
        if mx_10y:
            parts.append(f"Mexico 10Y: {self._fmt_pct(mx_10y)}.")
        if br_10y:
            parts.append(f"Brasil 10Y: {self._fmt_pct(br_10y)}.")

        if not parts:
            return "Datos de deuda EM no disponibles."

        # Use narrative engine if council available
        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        if rf_panel:
            from narrative_engine import generate_narrative
            narrative = generate_narrative(
                section_name="rf_em_debt",
                prompt=(
                    "Escribe 2-3 oraciones sobre deuda emergente basándote en el council. "
                    "Incluye view sobre hard vs local currency, países preferidos, y riesgos. "
                    "Usa los datos cuantitativos proporcionados."
                ),
                council_context=rf_panel[:1500],
                quant_context=' '.join(parts),
                company_name=self.company_name,
                max_tokens=500
            )
            if narrative:
                return narrative

        return ' '.join(parts)

    # =========================================================================
    # SECCION 6: CHILE RENTA FIJA
    # =========================================================================

    def generate_chile_fixed_income(self) -> Dict[str, Any]:
        """Genera sección de Chile renta fija."""

        result = {
            'soberanos': self._generate_chile_sovereigns(),
            'corporativos': self._generate_chile_corporates(),
            'money_market': self._generate_chile_mm(),
            'uf_vs_pesos': self._generate_uf_vs_pesos()
        }

        # Agregar expectativas TPM si disponibles
        tpm = self._val('tpm_expectations')
        if tpm and 'meetings' not in tpm:
            tpm = None
        if tpm:
            summary = tpm.get('summary', {})
            result['tpm_outlook'] = {
                'tpm_actual': self._fmt_pct(tpm.get('current_rate')),
                'dirección': summary.get('direction', ''),
                'terminal': self._fmt_pct(summary.get('terminal_rate')),
                'recortes_esperados': summary.get('total_cuts', summary.get('total_recortes', '')),
                '_real': True
            }

        # BCCh encuesta
        enc = self._val('bcch_encuesta')
        if enc and 'comparison' in enc:
            result['bcch_vs_mercado'] = enc

        return result

    def _generate_chile_sovereigns(self) -> Dict[str, Any]:
        """Genera analisis de soberanos Chile (datos reales BCCh)."""
        # BCP curve
        bcp_2 = self._chile_bcp('2Y')
        bcp_5 = self._chile_bcp('5Y')
        bcp_10 = self._chile_bcp('10Y')

        # BCU curve
        bcu_5 = self._chile_bcu('5Y')
        bcu_10 = self._chile_bcu('10Y')
        bcu_20 = self._chile_bcu('20Y')

        # TPM
        tpm_val = self._val('chile_rates', 'tpm', 'current')
        tpm_str = self._fmt_pct(tpm_val) if tpm_val else 'N/D'

        bcp10_str = self._fmt_pct(bcp_10) if bcp_10 else 'N/D'

        # Get Chile view early for narrative
        _fi_views_cl = self.parser.get_fi_views() if self.parser else {}
        _cl_data = (_fi_views_cl or {}).get('chile soberanos', (_fi_views_cl or {}).get('chile', (_fi_views_cl or {}).get('chile corporativos', {})))
        _cl_view = _cl_data.get('view', '') if _cl_data else ''
        _cl_rat = _cl_data.get('rationale', '') if _cl_data else ''
        _cl_label = f" Postura: {_cl_view}." if _cl_view else ''
        _cl_rat_label = f" {_cl_rat}" if _cl_rat else ''

        narrativa = (
            f"Bonos soberanos Chile: BCP-10 en {bcp10_str}, TPM en {tpm_str}."
            f"{_cl_label}{_cl_rat_label}"
        )

        _ht = self.parser.has_council_text() if self.parser else False

        curva_bcp = [
            {
                'plazo': 'BCP-2',
                'yield': self._fmt_pct(bcp_2) if bcp_2 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('2Y') or '-',
                'view': _cl_view or '-',
            },
            {
                'plazo': 'BCP-5',
                'yield': self._fmt_pct(bcp_5) if bcp_5 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('5Y') or '-',
                'view': _cl_view or '-',
            },
            {
                'plazo': 'BCP-10',
                'yield': self._fmt_pct(bcp_10) if bcp_10 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('10Y') or '-',
                'view': _cl_view or '-',
            },
        ]

        curva_bcu = [
            {
                'plazo': 'BCU-5',
                'yield': self._fmt_pct(bcu_5) if bcu_5 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('5Y') or '-',
                'view': _cl_view or '-',
            },
            {
                'plazo': 'BCU-10',
                'yield': self._fmt_pct(bcu_10) if bcu_10 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('10Y') or '-',
                'view': _cl_view or '-',
            },
            {
                'plazo': 'BCU-20',
                'yield': self._fmt_pct(bcu_20) if bcu_20 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('20Y') or '-',
                'view': _cl_view or '-',
            },
        ]

        # Get Chile sovereign view from council parser
        fi_views = self.parser.get_fi_views()
        chile_sv = 'Sin vista'
        chile_dur_v = 'N/D'
        if fi_views:
            cv = fi_views.get('chile soberanos', fi_views.get('chile', fi_views.get('chile corporativos', {})))
            chile_sv = cv.get('view', 'Sin vista')
            dur_map = {'CORTA': 'Corta', 'NEUTRAL': 'Neutral', 'LARGA': 'Larga'}
            chile_dur_v = dur_map.get(cv.get('duration', ''), 'N/D')

        result = {
            'view': chile_sv,
            'duration_view': chile_dur_v,
            'narrativa': narrativa,
            'curva_bcp': curva_bcp,
            'curva_bcu': curva_bcu,
        }
        if bcp_2 or bcp_5 or bcp_10:
            result['_real'] = True
        return result

    def _generate_chile_corporates(self) -> Dict[str, Any]:
        """Genera analisis de corporativos Chile (lending rates reales BCCh)."""
        # Lending rates from BCCh
        lending_consumer = self._val('chile_rates', 'lending', 'consumer')
        lending_commercial = self._val('chile_rates', 'lending', 'commercial')
        lending_mortgage = self._val('chile_rates', 'lending', 'mortgage_uf')
        tpm = self._val('chile_rates', 'tpm', 'current')

        narrativa = ""
        if lending_commercial and tpm:
            spread_lending = round(lending_commercial - tpm, 1)
            narrativa += (
                f"Tasas de credito comercial en {self._fmt_pct(lending_commercial)} "
                f"(spread {self._fmt_pct(spread_lending)} sobre TPM). "
            )
        if lending_mortgage:
            narrativa += f"Hipotecario en UF+{self._fmt_pct(lending_mortgage)}. "
        _cl_corp = (_fi_views_cl or {}).get('chile corporativos', {}) if hasattr(self, '_fi_views_cl') else {}
        if not _cl_corp and self.parser:
            _fv = self.parser.get_fi_views() or {}
            _cl_corp = _fv.get('chile corporativos', {})
        _cl_corp_v = _cl_corp.get('view', '')
        _cl_corp_r = _cl_corp.get('rationale', '')
        if _cl_corp_v:
            narrativa += f"Postura: {_cl_corp_v}."
            if _cl_corp_r:
                narrativa += f" {_cl_corp_r}"

        result = {
            'view': _cl_corp_v or 'N/D',
            'spread_promedio': 'N/D',
            'narrativa': narrativa,
            'emisores_preferidos': [
                {'emisor': 'Enel Chile', 'rating': 'A-', 'spread': 'N/D', 'yield': 'N/D', 'view': 'N/D'},
                {'emisor': 'Falabella', 'rating': 'BBB', 'spread': 'N/D', 'yield': 'N/D', 'view': 'N/D'},
                {'emisor': 'Banco Chile', 'rating': 'A', 'spread': 'N/D', 'yield': 'N/D', 'view': 'N/D'},
                {'emisor': 'CMPC', 'rating': 'BBB+', 'spread': 'N/D', 'yield': 'N/D', 'view': 'N/D'},
                {'emisor': 'Cencosud', 'rating': 'BBB-', 'spread': 'N/D', 'yield': 'N/D', 'view': 'N/D'},
            ],
            'sectores': [
                {'sector': 'Utilities', 'view': 'N/D', 'spread': 'N/D', 'rationale': 'N/D'},
                {'sector': 'Bancos', 'view': 'N/D', 'spread': 'N/D', 'rationale': 'N/D'},
                {'sector': 'Retail', 'view': 'N/D', 'spread': 'N/D', 'rationale': 'N/D'},
                {'sector': 'Forestal', 'view': 'N/D', 'spread': 'N/D', 'rationale': 'N/D'},
                {'sector': 'Inmobiliario', 'view': 'N/D', 'spread': 'N/D', 'rationale': 'N/D'},
            ],
        }

        # Lending rates table (real from BCCh)
        if lending_consumer or lending_commercial or lending_mortgage:
            result['lending_rates'] = {}
            if lending_consumer:
                result['lending_rates']['consumer'] = self._fmt_pct(lending_consumer)
            if lending_commercial:
                result['lending_rates']['commercial'] = self._fmt_pct(lending_commercial)
            if lending_mortgage:
                result['lending_rates']['mortgage_uf'] = self._fmt_pct(lending_mortgage)
            result['_real'] = True

        return result

    def _generate_chile_mm(self) -> Dict[str, Any]:
        """Genera analisis de money market Chile (datos reales BCCh: TPM, DAP, interbank)."""
        tpm_val = self._val('chile_rates', 'tpm', 'current')
        tpm_str = self._fmt_pct(tpm_val) if tpm_val else 'N/D'

        # DAP rates REALES from BCCh
        dap_90_real = self._val('chile_rates', 'dap', '90d')
        dap_1y_real = self._val('chile_rates', 'dap', '1y')
        interbank = self._val('chile_rates', 'interbank')

        # Use real data where available, approximate otherwise
        if dap_90_real:
            dap_30 = self._fmt_pct(dap_90_real - 0.15)  # 30d ≈ 90d - 15bp
            dap_90 = self._fmt_pct(dap_90_real)
            dap_180 = self._fmt_pct(dap_90_real + 0.10)  # 180d ≈ 90d + 10bp
        elif tpm_val:
            t = float(tpm_val)
            dap_30 = self._fmt_pct(t - 0.20)
            dap_90 = self._fmt_pct(t - 0.05)
            dap_180 = self._fmt_pct(t)
        else:
            dap_30, dap_90, dap_180 = 'N/D', 'N/D', 'N/D'

        dap_1y_str = self._fmt_pct(dap_1y_real) if dap_1y_real else dap_180
        fm_mm = self._fmt_pct(interbank - 0.10) if interbank else (self._fmt_pct(float(tpm_val) - 0.30) if tpm_val else 'N/D')
        pactos = self._fmt_pct(interbank) if interbank else (self._fmt_pct(float(tpm_val) - 0.10) if tpm_val else 'N/D')

        # BCP 1Y as reference
        bcp_1y = self._chile_bcp('1Y')
        bcp_1y_str = self._fmt_pct(bcp_1y) if bcp_1y else None

        narrativa = f"Alternativas de corto plazo con TPM en {tpm_str}. "
        if dap_90_real:
            narrativa += f"DAP 90 dias rinde {self._fmt_pct(dap_90_real)}. "
        if bcp_1y_str:
            narrativa += f"BCP 1Y rinde {bcp_1y_str}. "
        if interbank:
            narrativa += f"Tasa interbancaria en {self._fmt_pct(interbank)}. "

        # Derive MM views from TPM outlook
        tpm_exp = self._val('tpm_expectations')
        fi_views = self.parser.get_fi_views() or {}
        mm_council = fi_views.get('chile money market', fi_views.get('chile corto plazo', {}))
        mm_view_default = mm_council.get('view', '')

        if mm_view_default:
            # Council gave explicit money market view
            view_map = {'OW': 'Acumular', 'NEUTRAL': 'Mantener', 'UW': 'Reducir'}
            mm_view = view_map.get(mm_view_default, mm_view_default)
        elif tpm_exp and isinstance(tpm_exp, dict):
            # Derive from TPM trajectory
            path = tpm_exp.get('path', [])
            if path and len(path) >= 2:
                last = path[-1].get('rate', tpm_val) if isinstance(path[-1], dict) else path[-1]
                first = path[0].get('rate', tpm_val) if isinstance(path[0], dict) else path[0]
                if last and first and float(last) < float(first):
                    mm_view = 'Acumular'  # TPM bajando → lock-in tasas actuales
                elif last and first and float(last) > float(first):
                    mm_view = 'Esperar'   # TPM subiendo → esperar mejores tasas
                else:
                    mm_view = 'Mantener'
            else:
                mm_view = 'Mantener'
        else:
            mm_view = 'Mantener'

        # Longer DAPs get stronger view if TPM is declining
        view_short = mm_view
        view_long = 'Acumular' if mm_view == 'Acumular' else mm_view

        result = {
            'narrativa': narrativa,
            'alternativas': [
                {'instrumento': 'DAP 30 dias', 'tasa': dap_30, 'liquidez': 'Al vencimiento', 'view': view_short},
                {'instrumento': 'DAP 90 dias', 'tasa': dap_90, 'liquidez': 'Al vencimiento', 'view': view_short},
                {'instrumento': 'DAP 180 dias', 'tasa': dap_180, 'liquidez': 'Al vencimiento', 'view': view_long},
                {'instrumento': 'DAP 360 dias', 'tasa': dap_1y_str, 'liquidez': 'Al vencimiento', 'view': view_long},
                {'instrumento': 'FM Money Market', 'tasa': fm_mm, 'liquidez': 'Diaria', 'view': view_short},
                {'instrumento': 'Pactos BC', 'tasa': pactos, 'liquidez': 'Al vencimiento', 'view': view_short},
            ],
        }
        if dap_90_real:
            result['_real'] = True
        return result

    def _generate_uf_vs_pesos(self) -> Dict[str, Any]:
        """Genera analisis UF vs Pesos (breakeven real de BCCh)."""
        # Breakeven implícito = BCP - BCU para cada tenor
        be_5y = self._val('chile_yields', 'breakevens', '5Y')
        be_10y = self._val('chile_yields', 'breakevens', '10Y')
        be_ref = be_5y or be_10y

        be_str = self._fmt_pct(be_ref) if be_ref else 'N/D'

        narrativa = f"Breakeven de inflacion en {be_str}. Meta BCCh: 3.0%."
        if be_ref:
            narrativa += f" Diferencia vs meta: {be_ref - 3.0:+.1f}pp."

        result = {
            'breakeven': be_str,
            'inflacion_esperada': 'N/D — meta BCCh 3.0% (no es expectativa de mercado)',
            'view': 'N/D — ver council',
            'narrativa': narrativa,
            'recomendacion': {
                'corto_plazo': 'N/D — ver council',
                'mediano_plazo': 'N/D — ver council',
                'largo_plazo': 'N/D — ver council'
            }
        }
        if be_ref:
            result['_real'] = True
        return result

    # =========================================================================
    # SECCION 7: INFLACION Y BREAKEVENS
    # =========================================================================

    def generate_inflation_analysis(self) -> Dict[str, Any]:
        """Genera seccion de inflacion y breakevens."""

        return {
            'breakevens_global': self._generate_global_breakevens(),
            'breakeven_vs_realizado': self._generate_breakeven_vs_realized(),
            'tips_view': self._generate_tips_view(),
            'narrativa': self._generate_inflation_narrative()
        }

    def _generate_breakeven_vs_realized(self) -> Dict[str, Any]:
        """Genera comparacion de breakeven vs inflacion realizada (datos reales si disponibles)."""
        infl = self._val('inflation')
        be_10y = None
        if infl and 'breakeven_inflation' in infl:
            bei = infl['breakeven_inflation']
            if isinstance(bei, dict) and 'current' in bei:
                be_10y = bei['current'].get('breakeven_10y')

        cl_be = self._val('chile_yields', 'breakevens', '10Y')

        return {
            'titulo': 'Breakeven (inflación implícita del mercado) vs Inflación Realizada',
            'descripcion': 'Comparacion de expectativas de inflacion (breakeven) vs inflacion realizada para evaluar valor relativo',
            'datos': [
                {
                    'mercado': 'USA',
                    'breakeven_10y': self._fmt_pct(be_10y) if be_10y else 'N/D',
                    'inflacion_ytd_anualizada': 'N/D',
                    'diferencia': 'N/D',
                    'conclusion': 'Ver sección breakevens para detalle'
                },
                {
                    'mercado': 'Chile',
                    'breakeven_10y': self._fmt_pct(cl_be) if cl_be else 'N/D',
                    'inflacion_ytd_anualizada': 'N/D',
                    'diferencia': 'N/D',
                    'conclusion': 'Ver sección breakevens para detalle'
                }
            ],
            'recomendacion': {
                'usa': 'N/D — ver council',
                'uk': 'N/D — ver council',
                'chile': 'N/D — ver council'
            }
        }

    def _generate_global_breakevens(self) -> List[Dict[str, Any]]:
        """Genera breakevens globales (US real desde FRED si disponible)."""
        infl = self._val('inflation')

        # Intentar US breakevens reales
        be_5y = None
        be_10y = None
        if infl and 'breakeven_inflation' in infl:
            bei = infl['breakeven_inflation']
            if isinstance(bei, dict) and 'current' in bei:
                be_5y = bei['current'].get('breakeven_5y')
                be_10y = bei['current'].get('breakeven_10y')

        us_row = {
            'mercado': 'US',
            'be_2y': 'N/D',
            'be_5y': self._fmt_pct(be_5y) if be_5y else 'N/D',
            'be_10y': self._fmt_pct(be_10y) if be_10y else 'N/D',
            'vs_target': 'N/D',
            'view': 'N/D'
        }
        if be_5y or be_10y:
            us_row['_real'] = True

        # TIPS allocation signal
        if infl and 'tips_signal' in infl:
            sig = infl['tips_signal']
            if isinstance(sig, dict):
                us_row['tips_signal'] = sig.get('signal', '')
                us_row['tips_rationale'] = sig.get('rationale', '')

        # Chile breakevens from BCCh (BCP - BCU)
        cl_be_5y = self._val('chile_yields', 'breakevens', '5Y')
        cl_be_10y = self._val('chile_yields', 'breakevens', '10Y')
        cl_be_2y = self._val('chile_yields', 'breakevens', '2Y')

        chile_row = {
            'mercado': 'Chile',
            'be_2y': self._fmt_pct(cl_be_2y) if cl_be_2y else 'N/D',
            'be_5y': self._fmt_pct(cl_be_5y) if cl_be_5y else 'N/D',
            'be_10y': self._fmt_pct(cl_be_10y) if cl_be_10y else 'N/D',
            'vs_target': 'En meta',
            'view': 'Fair',
        }
        if cl_be_5y or cl_be_10y:
            chile_row['_real'] = True
            # Ajustar view dinámicamente
            ref = cl_be_10y or cl_be_5y
            if ref < 2.7:
                chile_row['vs_target'] = 'Bajo meta'
                chile_row['view'] = 'BCU barato'
            elif ref > 3.3:
                chile_row['vs_target'] = 'Sobre meta'
                chile_row['view'] = 'Caro'

        return [
            us_row,
            {'mercado': 'Eurozona', 'be_2y': 'N/D', 'be_5y': 'N/D', 'be_10y': 'N/D', 'vs_target': 'N/D', 'view': 'N/D'},
            {'mercado': 'UK', 'be_2y': 'N/D', 'be_5y': 'N/D', 'be_10y': 'N/D', 'vs_target': 'N/D', 'view': 'N/D'},
            chile_row,
        ]

    def _generate_tips_view(self) -> Dict[str, Any]:
        """Genera view de TIPS/linkers (real rates desde FRED si disponibles)."""
        infl = self._val('inflation')

        tips_10y = None
        tips_signal = None
        tips_rationale = None

        if infl:
            rr = infl.get('real_rates', {})
            if isinstance(rr, dict) and 'current' in rr:
                tips_10y = rr['current'].get('tips_10y')
            sig = infl.get('tips_signal', {})
            if isinstance(sig, dict):
                tips_signal = sig.get('signal')
                tips_rationale = sig.get('rationale')

        view = 'NEUTRAL'
        if tips_signal:
            sig_lower = str(tips_signal).lower()
            if 'overweight' in sig_lower or 'buy' in sig_lower:
                view = 'OVERWEIGHT'
            elif 'underweight' in sig_lower or 'sell' in sig_lower:
                view = 'UNDERWEIGHT'

        return {
            'us_tips': {
                'view': view,
                'yield_real_10y': self._fmt_pct(tips_10y) if tips_10y else 'N/D',
                'rationale': tips_rationale if tips_rationale else 'N/D — ver council',
                '_real': bool(tips_10y)
            },
            'euro_linkers': {
                'view': 'N/D',
                'yield_real_10y': 'N/D',
                'rationale': 'N/D'
            },
            'chile_bcu': {
                'view': 'N/D',
                'yield_real_10y': self._fmt_pct(self._chile_bcu('10Y')) if self._chile_bcu('10Y') else 'N/D',
                'rationale': 'N/D',
                '_real': bool(self._chile_bcu('10Y'))
            }
        }

    def _generate_inflation_narrative(self) -> str:
        """Genera narrativa de inflacion (dinámica con datos reales)."""
        bcu_10y = self._chile_bcu('10Y')
        bcu_str = self._fmt_pct(bcu_10y) if bcu_10y else 'N/D'

        from narrative_engine import generate_narrative
        narrativa = generate_narrative(
            section_name="rf_inflation_narrative",
            prompt=(
                "Describe el panorama de inflacion y breakevens en 2-3 oraciones con los datos. "
                "NO emitas opinion sobre valor tactico. Maximo 60 palabras."
            ),
            council_context=self.council.get('panel_outputs', {}).get('rf', '')[:1000],
            quant_context=f"Chile BCU 10Y real yield: {bcu_str}.",
            company_name=self.company_name, max_tokens=400,
        )
        return narrativa or f"Chile BCU 10Y real yield: {bcu_str}."

    # =========================================================================
    # SECCION 8: RIESGOS Y OPORTUNIDADES
    # =========================================================================

    def generate_risks_opportunities(self) -> Dict[str, Any]:
        """Genera seccion de riesgos y oportunidades."""

        return {
            'top_risks': self._generate_rf_risks(),
            'oportunidades': self._generate_rf_opportunities(),
            'trades': self._generate_recommended_trades()
        }

    def _generate_rf_risks(self) -> List[Dict[str, Any]]:
        """Genera top riesgos para renta fija via Claude."""
        import json as _json
        from narrative_engine import generate_narrative

        riesgo_panel = self.council.get('panel_outputs', {}).get('riesgo', '')
        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        final = self.council.get('final_recommendation', '')

        if riesgo_panel or rf_panel or final:
            council_ctx = (
                f"RISK PANEL:\n{riesgo_panel[:1500]}\n\n"
                f"RF PANEL:\n{rf_panel[:1000]}\n\n"
                f"FINAL:\n{final[:1000]}"
            )
            result = generate_narrative(
                section_name="rf_risks",
                prompt=(
                    "Genera exactamente 3 top riesgos para renta fija basados en el council. "
                    "Devuelve un JSON array donde cada elemento tiene: "
                    '{"riesgo": "nombre corto", "probabilidad": "XX%", "impacto": "Alto/Medio-Alto/Medio", '
                    '"descripcion": "1 oracion", "hedge": "cobertura sugerida"}. '
                    "Usa riesgos que el council identifica. NO inventes probabilidades."
                ),
                council_context=council_ctx,
                company_name=self.company_name,
                max_tokens=600,
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

        # Fallback: use risk assessment from parser
        risk_data = self.parser.get_risk_assessment() if self.parser else None
        if risk_data:
            fallback_risks = []
            for r in risk_data[:3]:
                fallback_risks.append({
                    'riesgo': r.get('risk', 'N/D'),
                    'probabilidad': r.get('probability', 'N/D'),
                    'impacto': r.get('impact', 'N/D'),
                    'descripcion': r.get('horizon', ''),
                    'hedge': 'Diversificación',
                })
            if fallback_risks:
                return fallback_risks
        return []

    def _generate_rf_opportunities(self) -> List[str]:
        """Genera oportunidades en RF via Claude + datos reales."""
        from narrative_engine import generate_narrative

        bcp_5y = self._chile_bcp('5Y')
        bcu_10y = self._chile_bcu('10Y')
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        ust_10y = self._val('yield_curve', 'current_curve', '10Y')

        quant_parts = []
        if bcp_5y:
            quant_parts.append(f"Chile BCP 5Y: {self._fmt_pct(bcp_5y)}")
        if bcu_10y:
            quant_parts.append(f"Chile BCU 10Y: {self._fmt_pct(bcu_10y)}")
        if ust_10y and ig_spread:
            quant_parts.append(f"IG yield: {self._fmt_pct(float(ust_10y) + float(ig_spread)/100)}")
        if ig_spread:
            quant_parts.append(f"IG spread: {self._fmt_bp(ig_spread)}")

        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        final = self.council.get('final_recommendation', '')

        if rf_panel or final:
            council_ctx = f"RF PANEL:\n{rf_panel[:1500]}\n\nFINAL:\n{final[:1000]}"
            result = generate_narrative(
                section_name="rf_opportunities",
                prompt=(
                    "Genera exactamente 4-5 oportunidades en renta fija basadas en el council. "
                    "Cada oportunidad en una linea: 'Instrumento/Segmento: fundamento breve'. "
                    "Integrar datos cuantitativos si disponibles. Sin bullets ni numeracion."
                ),
                council_context=council_ctx,
                quant_context=" | ".join(quant_parts),
                company_name=self.company_name,
                max_tokens=400,
            )
            if result:
                lines = [l.strip() for l in result.split('\n') if l.strip()]
                if len(lines) >= 3:
                    return lines

        # Fallback with quant data only
        ops = []
        if bcp_5y:
            ops.append(f"Chile BCP 5Y: Carry de {self._fmt_pct(bcp_5y)}")
        if bcu_10y:
            ops.append(f"Chile BCU 10Y: Real yield de {self._fmt_pct(bcu_10y)}")
        if not ops:
            ops.append("Ver analisis detallado del council para oportunidades")
        return ops

    def _generate_recommended_trades(self) -> List[Dict[str, Any]]:
        """Genera trades recomendados desde council parser + datos de mercado como fallback."""
        # Get trades from council FI positioning
        fi_views = self.parser.get_fi_views() if self.parser else None
        trades = []
        if fi_views:
            for seg, data in fi_views.items():
                view = data.get('view', '')
                if view in ('OW', 'UW'):  # Only actionable positions
                    direction = 'Long' if view == 'OW' else 'Short'
                    trades.append({
                        'trade': f'{direction} {seg.title()}',
                        'entry': 'Mercado',
                        'target': '-25bp vs actual' if direction == 'Long' else '+25bp vs actual',
                        'stop': '+15bp vs actual' if direction == 'Long' else '-15bp vs actual',
                        'horizonte': '3 meses',
                        'carry': self._estimate_trade_carry(seg),
                        'rationale': data.get('rationale', 'Posición basada en análisis del comité'),
                    })

        # Fallback: generate data-driven trades from market data
        if not trades:
            trades = self._generate_fallback_trades()

        return trades

    def _estimate_trade_carry(self, segment: str) -> str:
        """Estima carry para un trade basado en datos de mercado."""
        seg_l = segment.lower()
        credit = self._val('credit_spreads')
        if 'ig' in seg_l and credit:
            ig_oas = credit.get('ig_breakdown', {}).get('total', {}).get('current_bps')
            if ig_oas:
                return f"~{int(ig_oas)}bp/año"
        if 'hy' in seg_l and credit:
            hy_oas = credit.get('hy_breakdown', {}).get('total', {}).get('current_bps')
            if hy_oas:
                return f"~{int(hy_oas)}bp/año"
        if 'chile' in seg_l:
            bcp5 = self._chile_bcp('5Y')
            if bcp5:
                return f"~{bcp5:.2f}% (BCP-5)"
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        if ust_10y and ('us' in seg_l or 'treasur' in seg_l):
            return f"~{float(ust_10y):.2f}% (UST 10Y)"
        return 'N/D'

    def _generate_fallback_trades(self) -> List[Dict[str, Any]]:
        """Genera 2-3 trades basados en datos de mercado cuando el council no emite trades."""
        trades = []

        # Trade 1: IG credit if spread data available
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        if ig_spread and ust_10y:
            ig_yield = float(ust_10y) + float(ig_spread) / 100
            trades.append({
                'trade': 'Long IG Corporate 3-5Y',
                'entry': f'OAS {int(ig_spread)}bp',
                'target': f'OAS {int(ig_spread * 0.85)}bp (-{int(ig_spread * 0.15)}bp)',
                'stop': f'OAS {int(ig_spread * 1.15)}bp (+{int(ig_spread * 0.15)}bp)',
                'horizonte': '3 meses',
                'carry': f'~{ig_yield:.2f}% yield total',
                'rationale': f'Carry atractivo con spread IG en {int(ig_spread)}bp; fundamentos corporativos sólidos',
            })

        # Trade 2: Chile BCP if data available
        bcp_5y = self._chile_bcp('5Y')
        if bcp_5y:
            trades.append({
                'trade': 'Long Chile BCP 5Y',
                'entry': f'{bcp_5y:.2f}%',
                'target': f'{bcp_5y - 0.25:.2f}% (-25bp)',
                'stop': f'{bcp_5y + 0.15:.2f}% (+15bp)',
                'horizonte': '3 meses',
                'carry': f'~{bcp_5y:.2f}% nominal',
                'rationale': f'BCP 5Y en {bcp_5y:.2f}% ofrece carry competitivo en el tramo medio de la curva',
            })

        # Trade 3: BCU if real yield data available
        bcu_10y = self._chile_bcu('10Y')
        if bcu_10y:
            trades.append({
                'trade': 'Long Chile BCU 10Y',
                'entry': f'{bcu_10y:.2f}% real',
                'target': f'{bcu_10y - 0.20:.2f}% (-20bp)',
                'stop': f'{bcu_10y + 0.15:.2f}% (+15bp)',
                'horizonte': '6 meses',
                'carry': f'~{bcu_10y:.2f}% real + inflación',
                'rationale': f'BCU 10Y real yield de {bcu_10y:.2f}% con protección inflacionaria',
            })

        # If still no trades, provide a generic defensive trade
        if not trades:
            trades.append({
                'trade': 'Mantener posición defensiva en renta fija',
                'entry': 'N/D',
                'target': 'N/D',
                'stop': 'N/D',
                'horizonte': '1-3 meses',
                'carry': 'N/D',
                'rationale': 'Posicionamiento conservador ante datos de mercado limitados',
            })

        return trades[:3]

    # =========================================================================
    # SECCION 9: RESUMEN POSICIONAMIENTO
    # =========================================================================

    def generate_positioning_summary(self) -> Dict[str, Any]:
        """Genera resumen final de posicionamiento (datos reales donde disponible)."""
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        bcp_5y = self._chile_bcp('5Y')
        bcu_10y = self._chile_bcu('10Y')

        ig_yield_str = 'N/D'
        if ust_10y and ig_spread:
            ig_yield_str = self._fmt_pct(float(ust_10y) + float(ig_spread)/100)

        bcp5_str = self._fmt_pct(bcp_5y) if bcp_5y else ''
        bcu10_str = self._fmt_pct(bcu_10y) if bcu_10y else ''

        # Build positioning summary from council parser
        fi_views = self.parser.get_fi_views()
        dur_stance = self.parser.get_duration_stance()
        _ht = self.parser.has_council_text() if self.parser else False
        _nd = 'N/D'

        dur_rec = dur_stance.get('stance', _nd) if dur_stance else _nd
        ig_v = fi_views.get('ig corporate', {}).get('view', _nd) if fi_views else _nd
        hy_v = fi_views.get('hy corporate', {}).get('view', _nd) if fi_views else _nd
        em_v = fi_views.get('em usd debt', fi_views.get('em hard currency', fi_views.get('em debt', {}))).get('view', _nd) if fi_views else _nd
        chile_v = _nd
        if fi_views:
            cv = fi_views.get('chile soberanos', fi_views.get('chile', fi_views.get('chile corporativos', {})))
            chile_v = cv.get('view', _nd)

        # Text mining fallback
        if dur_rec == _nd and _ht:
            mined = self.parser.search_duration_view()
            dur_rec = mined if mined else 'NEUTRAL'
        if ig_v == _nd and _ht:
            mined = self.parser.search_credit_view('ig')
            ig_v = mined if mined else 'NEUTRAL'
        if hy_v == _nd and _ht:
            mined = self.parser.search_credit_view('hy')
            hy_v = mined if mined else 'NEUTRAL'

        chile_rec = f'{chile_v} - BCP5Y'
        if bcp5_str:
            chile_rec += f' ({bcp5_str})'
        if bcu10_str:
            chile_rec += f', BCU10Y ({bcu10_str})'
        else:
            chile_rec += ', BCU10Y'

        return {
            'tabla_final': [
                {'dimension': 'Duration Global', 'recomendacion': dur_rec},
                {'dimension': 'Curva US', 'recomendacion': fi_views.get('us treasuries', {}).get('rationale', _nd) if fi_views else _nd},
                {'dimension': 'IG Credit', 'recomendacion': f'{ig_v} - carry {ig_yield_str}'},
                {'dimension': 'HY Credit', 'recomendacion': hy_v},
                {'dimension': 'EM Hard Currency', 'recomendacion': em_v},
                {'dimension': 'EM Local Currency', 'recomendacion': em_v},
                {'dimension': 'Inflacion/TIPS', 'recomendacion': 'NEUTRAL'},
                {'dimension': 'Chile Soberanos', 'recomendacion': chile_rec},
            ],
            'mensaje_clave': self._generate_rf_positioning_message()
        }

    def _generate_rf_positioning_message(self) -> str:
        """Genera mensaje clave de posicionamiento RF via Claude."""
        from narrative_engine import generate_narrative

        rf_panel = self.council.get('panel_outputs', {}).get('rf', '')
        final = self.council.get('final_recommendation', '')

        if rf_panel or final:
            result = generate_narrative(
                section_name="rf_positioning_msg",
                prompt=(
                    "Escribe 2-3 oraciones resumiendo el posicionamiento en renta fija: "
                    "postura general de duration, preferencia de credito, y mercado destacado. "
                    "Usa datos del council. Maximo 60 palabras."
                ),
                council_context=f"RF PANEL:\n{rf_panel[:1500]}\n\nFINAL:\n{final[:1000]}",
                company_name=self.company_name,
                max_tokens=400,
            )
            if result:
                return result

        return f'Ver analisis detallado de {self.month_name} {self.year} para posicionamiento en renta fija.'

    # =========================================================================
    # METODO PRINCIPAL
    # =========================================================================

    # =========================================================================
    # FORECAST ENGINE — RATE FORECASTS
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

    def generate_rate_forecasts(self) -> Dict[str, Any]:
        """Genera sección con pronósticos de tasas del Forecast Engine."""

        rates = self._fc('rate_forecasts')
        if not rates or not isinstance(rates, dict):
            return {
                'titulo': 'Pronósticos de Tasas',
                'available': False,
                'nota': 'Forecast Engine no disponible.',
            }

        rows = []
        rate_map = [
            ('fed_funds', 'Fed Funds'),
            ('tpm_chile', 'TPM Chile'),
            ('ecb', 'ECB Deposit'),
        ]

        for key, label in rate_map:
            data = rates.get(key, {})
            if isinstance(data, dict) and 'error' not in data:
                rows.append({
                    'tasa': label,
                    'actual': data.get('current'),
                    'forecast_6m': data.get('forecast_6m'),
                    'forecast_12m': data.get('forecast_12m'),
                    'terminal': data.get('terminal'),
                    'direction': data.get('direction', 'HOLD'),
                    'cuts': data.get('cuts_expected', 0),
                    'hikes': data.get('hikes_expected', 0),
                })

        return {
            'titulo': 'Pronósticos de Tasas — Forecast Engine',
            'available': len(rows) > 0,
            'horizonte': '12 meses',
            'rates': rows,
        }

    def generate_all_content(self) -> Dict[str, Any]:
        """Genera todo el contenido del reporte RF."""
        # Set up anti-fabrication filter with verified market data
        try:
            from narrative_engine import set_verified_data, clear_verified_data, build_verified_data_rf
            vd = build_verified_data_rf(self.market_data)
            if vd:
                set_verified_data(vd)
        except Exception:
            pass

        content = {
            'metadata': {
                'fecha': self.date.strftime('%Y-%m-%d'),
                'mes': self.month_name,
                'ano': self.year,
                'tipo_reporte': 'RENTA_FIJA'
            },
            'resumen_ejecutivo': self.generate_executive_summary(),
            'ambiente_tasas': self.generate_rates_environment(),
            'duration': self.generate_duration_positioning(),
            'credito': self.generate_credit_analysis(),
            'em_debt': self.generate_em_debt(),
            'chile': self.generate_chile_fixed_income(),
            'inflacion': self.generate_inflation_analysis(),
            'riesgos_oportunidades': self.generate_risks_opportunities(),
            'resumen_posicionamiento': self.generate_positioning_summary()
        }

        # Add rate forecasts from Forecast Engine if available
        rate_fc = self.generate_rate_forecasts()
        if rate_fc.get('available'):
            content['rate_forecasts'] = rate_fc

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
    generator = RFContentGenerator()
    content = generator.generate_all_content()

    import json
    print(json.dumps(content, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

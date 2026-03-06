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

        # Determine view - default CONSTRUCTIVO, override from council
        view = 'CONSTRUCTIVO'
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
                ),
                council_context=f"RF PANEL:\n{rf_panel[:2000]}\n\nFINAL:\n{final[:1000]}",
                quant_context=" | ".join(quant_parts),
                company_name=self.company_name,
                max_tokens=300,
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

        result = {
            'view': view,
            'duration_stance': 'NEUTRAL A LARGA',
            'credit_stance': 'OW SELECTIVO',
            'conviccion': 'MEDIA-ALTA',
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

        return [
            {
                'segmento': 'US Treasuries', 'view': 'OW', 'duration': 'Neutral-Larga',
                'yield': self._fmt_pct(ust_10y) if ust_10y else 'N/D',
                'spread': '-', 'driver': 'Fed en pausa, carry atractivo'
            },
            {
                'segmento': 'Euro Sovereigns', 'view': 'OW', 'duration': 'Neutral',
                'yield': self._fmt_pct(euro_10y) if euro_10y else 'N/D',
                'spread': '-', 'driver': 'BCE cerca de terminal'
            },
            {
                'segmento': 'IG Corporate', 'view': 'OW', 'duration': 'Neutral',
                'yield': self._fmt_pct(float(ust_10y) + float(ig_spread)/100) if (ust_10y and ig_spread) else 'N/D',
                'spread': self._fmt_bp(ig_spread) if ig_spread else 'N/D',
                'driver': 'Carry atractivo, fundamentales OK'
            },
            {
                'segmento': 'HY Corporate', 'view': 'NEUTRAL', 'duration': 'Corta',
                'yield': self._fmt_pct(float(ust_10y) + float(hy_spread)/100) if (ust_10y and hy_spread) else 'N/D',
                'spread': self._fmt_bp(hy_spread) if hy_spread else 'N/D',
                'driver': 'Spreads tight, selectivo'
            },
            {
                'segmento': 'EM USD Debt', 'view': 'OW', 'duration': 'Neutral',
                'yield': self._fmt_pct(br_10y) if br_10y else 'N/D',
                'spread': self._fmt_bp(em_spread) if em_spread else 'N/D',
                'driver': 'Yield pickup, selectivo por país'
            },
            {
                'segmento': 'Chile Soberanos', 'view': 'OW', 'duration': 'Larga',
                'yield': self._fmt_pct(chile_10y) if chile_10y else 'N/D',
                'spread': self._fmt_bp(chile_spread) if chile_spread else 'N/D',
                'driver': 'BCCh dovish, carry excelente'
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

        return [
            "Duration: Neutral a Larga globalmente; preferimos Chile y Europa sobre US",
            "Curva US: Posicion steepener 2s10s - normalizacion gradual",
            f"Credito IG: Overweight - carry de {ig_yield_str} atractivo con fundamentales solidos",
            f"Credito HY: Neutral - spreads en {hy_spread_str} son tight historicamente, selectivo",
            "Chile: Larga duration en BCP/BCU, BCCh tiene espacio para seguir recortando"
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
            'titulo': 'Expectativas Fed Funds (FedWatch)',
            'current_rate': self._fmt_pct(fed.get('current_rate')),
            'direction': summary.get('direction', ''),
            'total_moves': summary.get('total_cuts', summary.get('total_moves', '')),
            'terminal_rate': self._fmt_pct(summary.get('terminal_rate')),
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
            'titulo': 'Expectativas TPM Chile',
            'current_rate': self._fmt_pct(tpm.get('current_rate')),
            'direction': summary.get('direction', ''),
            'total_moves': summary.get('total_cuts', summary.get('total_recortes', '')),
            'terminal_rate': self._fmt_pct(summary.get('terminal_rate')),
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
                    'mercado': self._fmt_pct(c.get('market_rate')),
                    'fed_dots': self._fmt_pct(c.get('fed_dots_median', c.get('fed_rate'))),
                    'diferencia': self._fmt_bp(c.get('diff_bps', c.get('difference'))),
                    'señal': c.get('signal', ''),
                })

        return {
            'titulo': 'Mercado vs Fed Dots',
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
            'titulo': 'Mercado vs Encuesta BCCh',
            'rows': rows,
            '_real': True
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

        # --- German Bund (BCCh international_yields) ---
        de_10y = self._intl_yield('germany')
        de_vs1m = self._intl_vs1m('germany')
        bund_row = {
            'mercado': 'German Bund',
            'y10': self._fmt_pct(de_10y) if de_10y else 'N/D',
            'vs_1m': de_vs1m if de_vs1m else '-',
        }
        if de_10y:
            bund_row['_real'] = True

        # --- UK Gilt (BCCh) ---
        uk_10y = self._intl_yield('uk')
        uk_vs1m = self._intl_vs1m('uk')
        gilt_row = {
            'mercado': 'UK Gilt',
            'y10': self._fmt_pct(uk_10y) if uk_10y else 'N/D',
            'vs_1m': uk_vs1m if uk_vs1m else '-',
        }
        if uk_10y:
            gilt_row['_real'] = True

        # --- JGB (BCCh) ---
        jp_10y = self._intl_yield('japan')
        jp_vs1m = self._intl_vs1m('japan')
        jgb_row = {
            'mercado': 'JGB',
            'y10': self._fmt_pct(jp_10y) if jp_10y else 'N/D',
            'vs_1m': jp_vs1m if jp_vs1m else '-',
        }
        if jp_10y:
            jgb_row['_real'] = True

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

        return [us_row, bund_row, gilt_row, jgb_row, chile_row]

    def _generate_curves_analysis(self) -> Dict[str, Any]:
        """Genera análisis de curvas (slopes reales si disponibles)."""
        yc = self._val('yield_curve')

        # Narrativa dinámica si hay slopes reales
        narrativa = (
            "Las curvas de tasas muestran normalización gradual tras las inversiones de 2023-2024. "
        )
        if yc and 'slopes' in yc:
            slopes = yc['slopes']
            s2_10 = slopes.get('2s10s', {})
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
            narrativa += (
                "La curva US se ha empinado +15bp en el tramo 2-10 años, reflejando expectativas de "
                "soft landing y Fed menos agresiva. "
            )
        narrativa += (
            "Chile muestra la curva más empinada por ciclo de recortes del BCCh aún en desarrollo."
        )

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

        # Slopes detallados
        por_mercado = [
            {'mercado': 'US', 'forma': 'Ligeramente empinada', 'tendencia': 'Empinando', 'view': 'Steepener 2s10s'},
            {'mercado': 'Europa', 'forma': 'Flat', 'tendencia': 'Estable', 'view': 'Neutral curva'},
            {'mercado': 'UK', 'forma': 'Empinada', 'tendencia': 'Estable', 'view': 'Flattener táctico'},
            {'mercado': 'Japón', 'forma': 'Muy empinada', 'tendencia': 'Empinando', 'view': 'Neutral, BOJ risk'},
            {'mercado': 'Chile', 'forma': cl_forma, 'tendencia': 'Empinando', 'view': 'Bullet 5Y preferido'},
        ]

        # Enriquecer US con forma real
        if yc and 'slopes' in yc:
            slopes = yc['slopes']
            for pair_name in ['2s5s', '2s10s', '5s30s', '2s30s']:
                s = slopes.get(pair_name, {})
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

        us_row = {
            'mercado': 'US 10Y TIPS',
            'yield_real': self._fmt_pct(tips_10y) if tips_10y else 'N/D',
            'breakeven': self._fmt_pct(be_10y) if be_10y else 'N/D',
            'nominal': self._fmt_pct(nominal_10y) if nominal_10y else 'N/D',
            'vs_historia': 'Alto',
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
            'vs_historia': 'Atractivo',
        }
        if bcu_10y:
            chile_row['_real'] = True

        # German and UK real yields omitted — no public API for Euro/UK real yields or breakevens

        narrativa = "Las tasas reales se mantienen en territorio positivo, reflejando política monetaria aún restrictiva. "
        if tips_10y:
            narrativa += f"US 10Y real en {self._fmt_pct(tips_10y)} ofrece rendimiento atractivo para inversionistas de largo plazo. "
        else:
            narrativa += "US 10Y real ofrece rendimiento atractivo para inversionistas de largo plazo. "
        if bcu_10y:
            narrativa += f"Chile real en {self._fmt_pct(bcu_10y)} es particularmente atractivo dado el perfil de riesgo."
        else:
            narrativa += "Chile real es particularmente atractivo dado el perfil de riesgo."

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
                ),
                council_context=f"RF PANEL:\n{rf_panel[:1500]}\n\nFINAL:\n{final[:800]}",
                quant_context=f"US 10Y: {us_str} | Chile 10Y: {cl_str}",
                company_name=self.company_name,
                max_tokens=250,
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
        if dur and 'duration_target' in dur:
            dt = dur['duration_target']
            target = dt.get('target_duration', 7.0)
            dr = dt.get('duration_range', (6.0, 8.0))
            vs_bm = dt.get('vs_benchmark', 'NEUTRAL')
            confidence = dt.get('confidence', 'MEDIUM')
            rationale = dt.get('rationale', '')

            stance_map = {'LONG': 'LARGA', 'SHORT': 'CORTA', 'NEUTRAL': 'NEUTRAL'}
            stance = stance_map.get(vs_bm, 'NEUTRAL A LARGA')

            return {
                'stance': stance,
                'benchmark_duration': f"{dr[0]:.1f} años" if isinstance(dr, (list, tuple)) else '6.5 años',
                'recomendacion': f"{target:.1f} años",
                'confianza': confidence,
                'rationale': rationale if rationale else (
                    "Favorecemos duration ligeramente larga dado que los bancos centrales están en modo "
                    "de recorte o pausa."
                ),
                'riesgos': [
                    'Reflación por estímulos fiscales',
                    'Cambio de liderazgo en Fed',
                    'Term premium sube por oferta de Treasuries'
                ],
                '_real': True
            }

        # Intentar curve_recommendation
        if dur and 'curve_recommendation' in dur:
            cr = dur['curve_recommendation']
            return {
                'stance': 'NEUTRAL A LARGA',
                'benchmark_duration': '6.5 años',
                'recomendacion': '7.0 años (+0.5)',
                'posicion_curva': cr.get('trade_expression', ''),
                'confianza': cr.get('confidence', 'MEDIUM'),
                'rationale': cr.get('rationale', (
                    "Favorecemos duration ligeramente larga dado que los bancos centrales están en modo "
                    "de recorte o pausa."
                )),
                'riesgos': [
                    'Reflación por estímulos fiscales',
                    'Cambio de liderazgo en Fed',
                    'Term premium sube por oferta de Treasuries'
                ],
                '_real': True
            }

        return {
            'stance': 'NEUTRAL A LARGA',
            'benchmark_duration': '6.5 años',
            'recomendacion': '7.0 años (+0.5)',
            'rationale': (
                "Favorecemos duration ligeramente larga dado que los bancos centrales están en modo "
                "de recorte o pausa. El riesgo de tasas más altas es limitado con inflación convergiendo "
                "a metas. El carry en bonos largos compensa el riesgo de duration."
            ),
            'riesgos': [
                'Reflación por estímulos fiscales',
                'Cambio de liderazgo en Fed (Warsh más hawkish)',
                'Term premium sube por oferta de Treasuries'
            ]
        }

    def _generate_duration_by_market(self) -> List[Dict[str, Any]]:
        """Genera posicionamiento de duration por mercado."""
        return [
            {
                'mercado': 'Estados Unidos',
                'duration_view': 'Neutral-Larga',
                'benchmark': '6.0Y',
                'recomendacion': '6.5Y',
                'posicion_curva': 'Steepener 2s10s',
                'rationale': 'Fed en pausa, curva normalizando'
            },
            {
                'mercado': 'Europa',
                'duration_view': 'Neutral',
                'benchmark': '7.0Y',
                'recomendacion': '7.0Y',
                'posicion_curva': 'Neutral',
                'rationale': 'BCE cerca de terminal, crecimiento debil'
            },
            {
                'mercado': 'UK',
                'duration_view': 'Corta',
                'benchmark': '8.0Y',
                'recomendacion': '7.0Y',
                'posicion_curva': 'Flattener',
                'rationale': 'Inflacion sticky, BOE cautious'
            },
            {
                'mercado': 'Japon',
                'duration_view': 'Underweight',
                'benchmark': '9.0Y',
                'recomendacion': '7.0Y',
                'posicion_curva': 'Neutral',
                'rationale': 'BOJ normalizando, riesgo de subas'
            },
            {
                'mercado': 'Chile',
                'duration_view': 'Larga',
                'benchmark': '5.0Y',
                'recomendacion': '6.0Y',
                'posicion_curva': 'Bullet 5Y',
                'rationale': 'BCCh dovish, carry excelente, inflacion en meta'
            },
        ]

    def _generate_duration_trades(self) -> List[Dict[str, Any]]:
        """Genera trades de duration recomendados."""
        return [
            {
                'trade': 'US 2s10s Steepener',
                'instrumento': 'Long 10Y, Short 2Y',
                'carry': '+0.15% (3m)',
                'target': '+30bp',
                'stop': '-15bp',
                'rationale': 'Normalizacion de curva, Fed terminando'
            },
            {
                'trade': 'Long Chile BCP 5Y',
                'instrumento': 'BCP-5 Bullet',
                'carry': '+1.25% (3m)',
                'target': '4.75% yield',
                'stop': '5.50% yield',
                'rationale': 'BCCh recortando, carry atractivo'
            },
            {
                'trade': 'Short JGB 10Y',
                'instrumento': 'JGB Futures',
                'carry': '-0.25% (3m)',
                'target': '1.20% yield',
                'stop': '0.85% yield',
                'rationale': 'BOJ normalizando politica'
            },
        ]

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
        """Genera tabla de CDS 5Y por pais (proprietary data — no public API)."""
        return {
            'titulo': 'CDS Soberanos 5Y',
            'fecha': self.date.strftime('%Y-%m-%d'),
            'nota': 'Datos CDS requieren suscripción Bloomberg/Refinitiv — no disponible via API pública.',
            'datos': [],
        }

    def _generate_liquidity_analysis(self) -> Dict[str, Any]:
        """Genera analisis de liquidez y bid-ask spreads (proprietary data — no public API)."""
        return {
            'titulo': 'Analisis de Liquidez por Segmento',
            'nota': 'Datos de liquidez/bid-ask requieren suscripción Bloomberg/Refinitiv — no disponible via API pública.',
            'datos': [],
            'recomendaciones': [
                'Mantener 10-15% del portfolio en activos muy liquidos (Treasuries, Bunds)',
                'Staged entry para posiciones Chile corporativo',
                'Evitar HY iliquido en tamanos que no se puedan salir en 3 dias',
                'Monitorear bid-ask como early warning de stress'
            ]
        }

    def _generate_refinancing_calendar(self) -> Dict[str, Any]:
        """Genera calendario de vencimientos y refinanciamiento (manual/proprietary — no API)."""
        return {
            'titulo': 'Calendario de Refinanciamiento',
            'nota': 'Datos de vencimientos requieren suscripción Bloomberg/Refinitiv — no disponible via API pública.',
            'global_maturity_wall': {},
            'chile_vencimientos': [],
            'emisores_monitoreados': [],
            'observaciones': [
                'Monitorear spreads de emisores con vencimientos 2026-2027'
            ]
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

        narrativa = f"Investment Grade ofrece carry atractivo con spreads en {spread_str}"
        if ig_signal:
            narrativa += f" (señal: {ig_signal})"
        narrativa += (
            ". Las empresas IG tienen leverage bajo, "
            "cobertura de intereses fuerte y acceso a mercados de capital. Preferimos sectores "
            "defensivos y financieros sobre cíclicos."
        )

        # Compute yield_total from UST 10Y + IG spread (real data)
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        ig_yield_total = 'N/D'
        if ust_10y and ig_total_bps:
            ig_yield_total = self._fmt_pct(float(ust_10y) + float(ig_total_bps) / 100)

        result = {
            'view': 'OVERWEIGHT',
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

        narrativa = f"High Yield ofrece yield atractivo pero spreads en {spread_str} están {vs_hist.lower()} vs historia. "
        narrativa += (
            "El refinanciamiento de deuda 2025-2026 es un riesgo para emisores más débiles. "
            "Preferimos BB sobre CCC y somos muy selectivos."
        )

        por_rating = [
            {'rating': 'BB', 'spread': self._fmt_bp(hy_bb) if hy_bb else 'N/D', 'view': 'OW', 'comentario': 'Calidad decente'},
            {'rating': 'B', 'spread': self._fmt_bp(hy_b) if hy_b else 'N/D', 'view': 'Neutral', 'comentario': 'Selectivo'},
            {'rating': 'CCC', 'spread': self._fmt_bp(hy_ccc) if hy_ccc else 'N/D', 'view': 'UW', 'comentario': 'Default risk'},
        ]

        # Compute yield_total from UST 10Y + HY spread (real data)
        ust_10y = self._val('yield_curve', 'current_curve', '10Y') or self._val('yield_curve', 'current_curve', 'DGS10')
        hy_yield_total = 'N/D'
        if ust_10y and hy_total_bps:
            hy_yield_total = self._fmt_pct(float(ust_10y) + float(hy_total_bps) / 100)

        result = {
            'view': 'NEUTRAL',
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

    def _generate_credit_by_sector(self) -> List[Dict[str, Any]]:
        """Genera analisis de credito por sector (views cualitativas — spreads por sector no disponibles via API)."""
        return [
            {'sector': 'Financials', 'view': 'OW', 'spread_ig': 'N/D', 'fundamentales': 'Fuertes', 'driver': 'Capital solido, NIM estable'},
            {'sector': 'Technology', 'view': 'OW', 'spread_ig': 'N/D', 'fundamentales': 'Solidos', 'driver': 'Cash rich, bajo leverage'},
            {'sector': 'Healthcare', 'view': 'OW', 'spread_ig': 'N/D', 'fundamentales': 'Estables', 'driver': 'Defensivo, M&A funding'},
            {'sector': 'Industrials', 'view': 'NEUTRAL', 'spread_ig': 'N/D', 'fundamentales': 'Mixtos', 'driver': 'Ciclico, capex'},
            {'sector': 'Consumer', 'view': 'NEUTRAL', 'spread_ig': 'N/D', 'fundamentales': 'Mixtos', 'driver': 'Consumo moderando'},
            {'sector': 'Energy', 'view': 'NEUTRAL', 'spread_ig': 'N/D', 'fundamentales': 'Ciclicos', 'driver': 'Oil price sensitive'},
            {'sector': 'Utilities', 'view': 'UW', 'spread_ig': 'N/D', 'fundamentales': 'Presion', 'driver': 'Capex elevado, regulacion'},
            {'sector': 'Real Estate', 'view': 'UW', 'spread_ig': 'N/D', 'fundamentales': 'Debiles', 'driver': 'Oficinas, refinanciamiento'},
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

        return (
            f"El mercado de credito ofrece oportunidades selectivas. Investment Grade es nuestro segmento "
            f"preferido con carry de {ig_yield_str} (spread {ig_spread_str}) y fundamentales solidos. "
            f"High Yield (spread {hy_spread_str}) requiere mayor selectividad "
            "dado riesgo de refinanciamiento. Por sector, preferimos Financials y "
            "Technology sobre Utilities y Real Estate. En HY, favorecemos BB sobre CCC."
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

        return {
            'view': 'OVERWEIGHT',
            'indice': 'EMBIG Diversified',
            'spread': spread_str,
            'yield': yield_str,
            'duration': '7.0Y',
            'narrativa': (
                f"Deuda EM en dolares ofrece yield pickup atractivo de {spread_str} sobre Treasuries. "
                "Preferimos soberanos IG (Chile, Mexico, Peru) sobre HY (Argentina, Ecuador). "
                "El riesgo principal es fortaleza del USD y desaceleracion China."
            ),
            'soberanos_vs_corporativos': {
                'soberanos_view': 'OW',
                'soberanos_spread': spread_str,
                'corporativos_view': 'Neutral',
                'corporativos_spread': 'N/D',
                'preferencia': 'Soberanos por liquidez y spread pickup'
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

        return {
            'view': 'NEUTRAL A OW',
            'yield_promedio': 'N/D',
            'fx_view': 'Selectivo',
            'narrativa': (
                "Deuda EM en moneda local ofrece yields atractivos con oportunidades "
                "de carry. El riesgo FX es el principal factor. Preferimos paises con bancos centrales "
                "credibles y cuentas externas saludables: Chile, Mexico, Indonesia."
            ),
            'carry_trades': [
                {'pais': 'Brasil', 'yield': self._fmt_pct(br_10y) if br_10y else 'N/D', 'fx_view': 'Neutral', 'carry_ajustado': 'Alto pero fiscal preocupa'},
                {'pais': 'Mexico', 'yield': self._fmt_pct(mx_10y) if mx_10y else 'N/D', 'fx_view': 'Positivo', 'carry_ajustado': 'Atractivo, nearshoring'},
                {'pais': 'Chile', 'yield': chile_str, 'fx_view': 'Positivo', 'carry_ajustado': 'Moderado, cobre soporte'},
                {'pais': 'Indonesia', 'yield': 'N/D', 'fx_view': 'Positivo', 'carry_ajustado': 'Atractivo, BI credible'},
            ]
        }

    def _generate_em_by_country(self) -> List[Dict[str, Any]]:
        """Genera views por pais EM (yields reales de BCCh)."""
        usa_10y = self._intl_yield('usa')

        def _spread(country_key):
            cy = self._intl_yield(country_key)
            if cy and usa_10y:
                return round((cy - usa_10y) * 100, 0)
            return None

        # Chile: use BCP 10Y for local currency
        chile_lc = self._chile_bcp('10Y')
        chile_hc_yield = self._intl_yield('usa')  # Chile USD = UST + spread
        chile_spread = _spread('usa')  # placeholder — use BCP vs UST
        if chile_lc and usa_10y:
            chile_spread = round((chile_lc - usa_10y) * 100, 0)

        br_10y = self._intl_yield('brazil')
        mx_10y = self._intl_yield('mexico')
        pe_10y = self._intl_yield('peru')
        co_10y = self._intl_yield('colombia')

        return [
            {
                'pais': 'Chile',
                'hc_view': 'OW', 'lc_view': 'OW',
                'yield_hc': self._fmt_pct(chile_lc) if chile_lc else 'N/D',
                'yield_lc': self._fmt_pct(chile_lc) if chile_lc else 'N/D',
                'spread': self._fmt_bp(chile_spread) if chile_spread else 'N/D',
                'rating': 'A',
                'driver': 'Macro estable, BCCh credible, cobre soporte',
                'riesgo': 'Politica, liquidez',
                '_real': bool(chile_lc),
            },
            {
                'pais': 'Mexico',
                'hc_view': 'OW', 'lc_view': 'OW',
                'yield_hc': self._fmt_pct(mx_10y) if mx_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': self._fmt_bp(_spread('mexico')) if _spread('mexico') else 'N/D',
                'rating': 'BBB',
                'driver': 'Nearshoring, Banxico credible',
                'riesgo': 'PEMEX, politica US',
                '_real': bool(mx_10y),
            },
            {
                'pais': 'Brasil',
                'hc_view': 'NEUTRAL', 'lc_view': 'OW',
                'yield_hc': self._fmt_pct(br_10y) if br_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': self._fmt_bp(_spread('brazil')) if _spread('brazil') else 'N/D',
                'rating': 'BB',
                'driver': 'Carry atractivo, BCB credible',
                'riesgo': 'Fiscal, politica',
                '_real': bool(br_10y),
            },
            {
                'pais': 'Peru',
                'hc_view': 'OW', 'lc_view': 'NEUTRAL',
                'yield_hc': self._fmt_pct(pe_10y) if pe_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': self._fmt_bp(_spread('peru')) if _spread('peru') else 'N/D',
                'rating': 'BBB',
                'driver': 'Bajo debt/GDP, cobre',
                'riesgo': 'Politica',
                '_real': bool(pe_10y),
            },
            {
                'pais': 'Colombia',
                'hc_view': 'NEUTRAL', 'lc_view': 'NEUTRAL',
                'yield_hc': self._fmt_pct(co_10y) if co_10y else 'N/D',
                'yield_lc': 'N/D',
                'spread': self._fmt_bp(_spread('colombia')) if _spread('colombia') else 'N/D',
                'rating': 'BB+',
                'driver': 'Yield atractivo',
                'riesgo': 'Fiscal, politica, oil',
                '_real': bool(co_10y),
            },
        ]

    def _generate_em_narrative(self) -> str:
        """Genera narrativa de EM debt (dinámica)."""
        chile_10y = self._chile_bcp('10Y')
        mx_10y = self._intl_yield('mexico')
        br_10y = self._intl_yield('brazil')

        parts = ["La deuda emergente ofrece yield pickup atractivo en un mundo de tasas estables. "]
        parts.append("Preferimos hard currency soberanos IG sobre HY por mejor perfil riesgo-retorno. ")
        if chile_10y and mx_10y:
            parts.append(
                f"En moneda local, Chile ({self._fmt_pct(chile_10y)}) y Mexico ({self._fmt_pct(mx_10y)}) "
                "ofrecen la mejor combinacion de carry y estabilidad FX. "
            )
        else:
            parts.append("En moneda local, Chile y Mexico ofrecen la mejor combinacion de carry y estabilidad FX. ")
        if br_10y:
            parts.append(f"Brasil ({self._fmt_pct(br_10y)}) tiene carry alto pero el riesgo fiscal limita la posicion.")
        else:
            parts.append("Brasil tiene carry alto pero el riesgo fiscal limita la posicion.")
        return ''.join(parts)

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

        narrativa = (
            f"Bonos soberanos chilenos ofrecen una combinacion atractiva de yield ({bcp10_str} BCP10), "
            f"carry excelente y upside de capital por recortes del BCCh. La TPM en {tpm_str} tiene "
            "espacio para bajar 25-50bp adicionales en 2026. Preferimos BCP 5Y para el bullet "
            "de la curva y BCU 10Y para proteccion de inflacion."
        )

        curva_bcp = [
            {
                'plazo': 'BCP-2',
                'yield': self._fmt_pct(bcp_2) if bcp_2 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('2Y') or '-',
                'view': 'Neutral',
            },
            {
                'plazo': 'BCP-5',
                'yield': self._fmt_pct(bcp_5) if bcp_5 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('5Y') or '-',
                'view': 'OW - Sweet spot',
            },
            {
                'plazo': 'BCP-10',
                'yield': self._fmt_pct(bcp_10) if bcp_10 else 'N/D',
                'vs_1m': self._chile_bcp_vs1m('10Y') or '-',
                'view': 'OW',
            },
        ]

        curva_bcu = [
            {
                'plazo': 'BCU-5',
                'yield': self._fmt_pct(bcu_5) if bcu_5 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('5Y') or '-',
                'view': 'OW',
            },
            {
                'plazo': 'BCU-10',
                'yield': self._fmt_pct(bcu_10) if bcu_10 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('10Y') or '-',
                'view': 'OW',
            },
            {
                'plazo': 'BCU-20',
                'yield': self._fmt_pct(bcu_20) if bcu_20 else 'N/D',
                'vs_1m': self._chile_bcu_vs1m('20Y') or '-',
                'view': 'Neutral',
            },
        ]

        result = {
            'view': 'OVERWEIGHT',
            'duration_view': 'Larga',
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

        narrativa = (
            "El mercado de bonos corporativos chilenos ofrece spreads atractivos de 100-150bp "
            "sobre soberanos con riesgo crediticio acotado. "
        )
        if lending_commercial and tpm:
            spread_lending = round(lending_commercial - tpm, 1)
            narrativa += (
                f"Tasas de credito comercial en {self._fmt_pct(lending_commercial)} "
                f"(spread {self._fmt_pct(spread_lending)} sobre TPM). "
            )
        if lending_mortgage:
            narrativa += f"Hipotecario en UF+{self._fmt_pct(lending_mortgage)}. "
        narrativa += (
            "Preferimos emisores con grado de inversion y liquidez razonable. "
            "Sectores favoritos: Utilities reguladas, Retail grado de inversion, Bancos."
        )

        result = {
            'view': 'OVERWEIGHT SELECTIVO',
            'spread_promedio': 'N/D',
            'narrativa': narrativa,
            'emisores_preferidos': [
                {'emisor': 'Enel Chile', 'rating': 'A-', 'spread': 'N/D', 'yield': 'N/D', 'view': 'OW'},
                {'emisor': 'Falabella', 'rating': 'BBB', 'spread': 'N/D', 'yield': 'N/D', 'view': 'OW'},
                {'emisor': 'Banco Chile', 'rating': 'A', 'spread': 'N/D', 'yield': 'N/D', 'view': 'OW'},
                {'emisor': 'CMPC', 'rating': 'BBB+', 'spread': 'N/D', 'yield': 'N/D', 'view': 'Neutral'},
                {'emisor': 'Cencosud', 'rating': 'BBB-', 'spread': 'N/D', 'yield': 'N/D', 'view': 'Neutral'},
            ],
            'sectores': [
                {'sector': 'Utilities', 'view': 'OW', 'spread': 'N/D', 'rationale': 'Regulado, predecible'},
                {'sector': 'Bancos', 'view': 'OW', 'spread': 'N/D', 'rationale': 'Capitalizado, liquido'},
                {'sector': 'Retail', 'view': 'Neutral', 'spread': 'N/D', 'rationale': 'Recovery, selectivo'},
                {'sector': 'Forestal', 'view': 'Neutral', 'spread': 'N/D', 'rationale': 'Ciclico'},
                {'sector': 'Inmobiliario', 'view': 'UW', 'spread': 'N/D', 'rationale': 'Presion'},
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

        narrativa = f"Las alternativas de corto plazo ofrecen rendimientos atractivos con la TPM en {tpm_str}. "
        if dap_90_real:
            narrativa += f"DAP 90 dias rinde {self._fmt_pct(dap_90_real)}. "
        if bcp_1y_str:
            narrativa += f"BCP 1Y rinde {bcp_1y_str}. "
        if interbank:
            narrativa += f"Tasa interbancaria en {self._fmt_pct(interbank)}. "

        result = {
            'narrativa': narrativa,
            'alternativas': [
                {'instrumento': 'DAP 30 dias', 'tasa': dap_30, 'liquidez': 'Al vencimiento', 'view': 'Atractivo'},
                {'instrumento': 'DAP 90 dias', 'tasa': dap_90, 'liquidez': 'Al vencimiento', 'view': 'Preferido'},
                {'instrumento': 'DAP 180 dias', 'tasa': dap_180, 'liquidez': 'Al vencimiento', 'view': 'Lock-in rate'},
                {'instrumento': 'DAP 360 dias', 'tasa': dap_1y_str, 'liquidez': 'Al vencimiento', 'view': 'Lock-in'},
                {'instrumento': 'FM Money Market', 'tasa': fm_mm, 'liquidez': 'Diaria', 'view': 'Para liquidez'},
                {'instrumento': 'Pactos BC', 'tasa': pactos, 'liquidez': 'Al vencimiento', 'view': 'Institucional'},
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

        # Determinar view: si BE < 3%, UF barato; si > 3%, pesos barato
        view = 'NEUTRAL'
        if be_ref:
            if be_ref < 2.7:
                view = 'OW UF (BCU)'
            elif be_ref > 3.3:
                view = 'OW PESOS (BCP)'

        narrativa = (
            f"El breakeven de inflacion en {be_str} "
        )
        if be_ref and abs(be_ref - 3.0) < 0.3:
            narrativa += "esta en linea con la meta del BCCh, sugiriendo que no hay valor obvio entre UF y pesos. "
        elif be_ref and be_ref < 3.0:
            narrativa += "esta por debajo de la meta del BCCh, sugiriendo que UF esta barato vs pesos. "
        elif be_ref and be_ref > 3.0:
            narrativa += "esta por sobre la meta del BCCh, sugiriendo cautela con UF. "
        else:
            narrativa += "esta cerca de la meta del BCCh. "
        narrativa += (
            "Para inversionistas con horizontes largos, la UF ofrece proteccion natural. "
            "Para posiciones tacticas, evaluar vs breakeven actual."
        )

        result = {
            'breakeven': be_str,
            'inflacion_esperada': '3.00%',  # BCCh target — not market data
            'view': view,
            'narrativa': narrativa,
            'recomendacion': {
                'corto_plazo': 'Pesos (DAP, BCP corto)',
                'mediano_plazo': 'Mix 50/50',
                'largo_plazo': 'UF preferido (BCU)'
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
            'titulo': 'Breakeven vs Inflacion Realizada',
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
                'usa': 'Neutral - preferir nominal sobre TIPS',
                'uk': 'OW Linkers - oportunidad',
                'chile': 'Leve OW BCU - Real yield atractivo y proteccion'
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
            'vs_target': 'Ligeramente sobre',
            'view': 'Fair'
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
                'rationale': tips_rationale if tips_rationale else 'Breakevens fair, real yield atractivo para largo plazo',
                '_real': bool(tips_10y)
            },
            'euro_linkers': {
                'view': 'NEUTRAL',
                'yield_real_10y': 'N/D',
                'rationale': 'Real yield bajo, breakevens fair'
            },
            'chile_bcu': {
                'view': 'OVERWEIGHT',
                'yield_real_10y': self._fmt_pct(self._chile_bcu('10Y')) if self._chile_bcu('10Y') else 'N/D',
                'rationale': 'Real yield muy atractivo, protección natural',
                '_real': bool(self._chile_bcu('10Y'))
            }
        }

    def _generate_inflation_narrative(self) -> str:
        """Genera narrativa de inflacion (dinámica con datos reales)."""
        bcu_10y = self._chile_bcu('10Y')
        bcu_str = self._fmt_pct(bcu_10y) if bcu_10y else 'N/D'

        return (
            "Los breakevens de inflacion estan anclados cerca de las metas de los bancos centrales "
            "en la mayoria de mercados, sugiriendo expectativas bien comportadas. No vemos valor "
            f"tactico claro en posiciones de inflacion en US o Europa. Chile ofrece la oportunidad "
            f"mas atractiva con BCU 10Y rindiendo {bcu_str} real, atractivo para horizontes largos."
        )

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

        return [
            {'riesgo': 'Ver council', 'probabilidad': 'N/D', 'impacto': 'N/D',
             'descripcion': 'Consultar analisis de riesgos del periodo.', 'hedge': 'Diversificacion'},
        ]

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
        """Genera trades recomendados (niveles basados en datos reales)."""
        bcp_5y = self._chile_bcp('5Y')
        ig_spread = self._val('credit_spreads', 'ig_breakdown', 'total', 'current_bps')
        hy_spread = self._val('credit_spreads', 'hy_breakdown', 'total', 'current_bps')
        mx_10y = self._intl_yield('mexico')

        trades = [
            {
                'trade': 'Long Chile BCP 5Y',
                'entry': self._fmt_pct(bcp_5y) if bcp_5y else 'N/D',
                'target': self._fmt_pct(bcp_5y - 0.40) if bcp_5y else 'N/D',
                'stop': self._fmt_pct(bcp_5y + 0.30) if bcp_5y else 'N/D',
                'horizonte': '6 meses',
                'carry': 'N/D',
                'rationale': 'BCCh dovish, curva empinada'
            },
            {
                'trade': 'OW IG vs HY',
                'entry': f'IG spread {self._fmt_bp(ig_spread)}, HY {self._fmt_bp(hy_spread)}' if (ig_spread and hy_spread) else 'N/D',
                'target': 'Spread compression IG, widening HY',
                'stop': 'HY outperform 2%',
                'horizonte': '3-6 meses',
                'carry': 'N/D',
                'rationale': 'HY spreads tight, default risk'
            },
            {
                'trade': 'Long Mexico 10Y USD',
                'entry': self._fmt_pct(mx_10y) if mx_10y else 'N/D',
                'target': self._fmt_pct(mx_10y - 0.50) if mx_10y else 'N/D',
                'stop': self._fmt_pct(mx_10y + 0.30) if mx_10y else 'N/D',
                'horizonte': '6 meses',
                'carry': 'N/D',
                'rationale': 'Nearshoring, Banxico credible'
            },
        ]
        return trades

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

        chile_rec = 'OW - BCP5Y'
        if bcp5_str:
            chile_rec += f' ({bcp5_str})'
        if bcu10_str:
            chile_rec += f', BCU10Y ({bcu10_str})'
        else:
            chile_rec += ', BCU10Y'

        return {
            'tabla_final': [
                {'dimension': 'Duration Global', 'recomendacion': 'Neutral a Larga'},
                {'dimension': 'Mercado Preferido', 'recomendacion': 'Chile, Europa'},
                {'dimension': 'Curva US', 'recomendacion': 'Steepener 2s10s'},
                {'dimension': 'IG Credit', 'recomendacion': f'OW - carry {ig_yield_str}'},
                {'dimension': 'HY Credit', 'recomendacion': 'Neutral - selectivo BB'},
                {'dimension': 'EM Hard Currency', 'recomendacion': 'OW - Chile, Mexico, Peru'},
                {'dimension': 'EM Local Currency', 'recomendacion': 'OW selectivo - Chile, Mexico'},
                {'dimension': 'Inflacion/TIPS', 'recomendacion': 'Neutral US, OW Chile BCU'},
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
                max_tokens=200,
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

# -*- coding: utf-8 -*-
"""
Greybark Research - Fixed Income Data Collector
================================================

Orquestador cuantitativo para el reporte de Renta Fija.
Recopila datos REALES de múltiples fuentes usando los módulos existentes
de la biblioteca greybark.

Fuentes de datos:
- DurationAnalytics (FRED): Yield curve, duration recs, credit spread analysis
- CreditSpreadAnalytics (FRED): IG/HY by rating, quality rotation signals
- InflationAnalytics (FRED): Breakevens, real rates, CPI decomp, TIPS signal
- Fed Expectations (CommLoan SOFR + QuantLib): Fed Funds path by FOMC meeting
- TPM Expectations (BCCh SPC + QuantLib): TPM Chile path by BCCh meeting
- Fed Dots Comparison (FRED + CommLoan): Market vs FOMC dot plot
- BCCh Encuesta Comparison (BCCh): Market vs encuesta EEE

Patrón: try/except por módulo, falla silenciosa con {'error': str(e)}.
Misma arquitectura que equity_data_collector.py.

Uso:
    collector = RFDataCollector(verbose=True)
    data = collector.collect_all()
    # data se pasa a RFContentGenerator(market_data=data)
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Fix Windows console encoding
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Agregar paths para imports
sys.path.insert(0, str(Path(__file__).parent))
LIB_PATH = Path(__file__).parent
sys.path.insert(0, str(LIB_PATH))

# Output directory
OUTPUT_DIR = Path(__file__).parent / "output" / "rf_data"


class RFDataCollector:
    """Recopila datos cuantitativos de renta fija desde múltiples fuentes."""

    def __init__(self, verbose: bool = True,
                 current_fed_funds: float = None,
                 current_tpm: float = None):
        self.verbose = verbose
        # Auto-fetch current rates from APIs if not provided
        self.current_fed_funds = current_fed_funds or self._fetch_current_fed_funds()
        self.current_tpm = current_tpm or self._fetch_current_tpm()

    def _fetch_current_tpm(self) -> float:
        """Fetch current TPM from BCCh API. Fallback 4.50%."""
        try:
            from greybark.data_sources.bcch_client import BCChClient
            client = BCChClient()
            df = client.get_series('F022.TPM.TIN.D001.NO.Z.D', days_back=60)
            if df is not None and not df.empty:
                val = float(df.iloc[-1])
                if 0 < val < 20:
                    self._print(f"  [BCCh] TPM actual: {val}%")
                    return val
        except Exception:
            pass
        self._print("  [WARN] TPM: usando fallback 4.50%")
        return 4.50

    def _fetch_current_fed_funds(self) -> float:
        """Fetch current Fed Funds from FRED. Fallback 4.50%."""
        try:
            from datetime import timedelta
            from greybark.data_sources.fred_client import FREDClient
            from datetime import date as dt_date
            client = FREDClient()
            start = dt_date.today() - timedelta(days=60)
            df = client.get_series('DFF', start_date=start)
            if df is not None and not df.empty:
                val = float(df.iloc[-1])
                if 0 <= val < 20:
                    self._print(f"  [FRED] Fed Funds actual: {val}%")
                    return val
        except Exception:
            pass
        self._print("  [WARN] Fed Funds: usando fallback 4.50%")
        return 4.50

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    # =========================================================================
    # MÓDULO 1: Duration Dashboard (yield curve + duration recs + credit)
    # =========================================================================

    def collect_duration(self) -> Dict[str, Any]:
        """
        DurationAnalytics: yield curve analysis, duration targeting,
        credit spread analysis, curve positioning.
        Source: FRED Treasury yields + credit spreads.
        """
        self._print("  [1/12] Duration Analytics...")
        try:
            from greybark.analytics.fixed_income.duration_analytics import DurationAnalytics
            da = DurationAnalytics()
            dashboard = da.get_duration_dashboard()
            self._print(f"  [OK] Duration: {len(dashboard)} keys")
            return dashboard
        except Exception as e:
            self._print(f"  [ERR] Duration: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 2: Yield Curve Analysis (detailed)
    # =========================================================================

    def collect_yield_curve(self) -> Dict[str, Any]:
        """
        DurationAnalytics: detailed yield curve shape, slopes (2s5s, 2s10s,
        5s30s, 2s30s), steepening/flattening signals.
        Source: FRED Treasury yields.
        """
        self._print("  [2/12] Yield Curve Analysis...")
        try:
            from greybark.analytics.fixed_income.duration_analytics import DurationAnalytics
            da = DurationAnalytics()
            curve = da.get_yield_curve_analysis()
            self._print(f"  [OK] Yield Curve: {len(curve)} keys")
            return curve
        except Exception as e:
            self._print(f"  [ERR] Yield Curve: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 3: Credit Spread Dashboard (IG/HY by rating)
    # =========================================================================

    def collect_credit_spreads(self) -> Dict[str, Any]:
        """
        CreditSpreadAnalytics: IG by rating (AAA/AA/A/BBB), HY by rating
        (BB/B/CCC), quality rotation signals, spread percentiles.
        Source: FRED ICE BofA OAS indices.
        """
        self._print("  [3/12] Credit Spreads...")
        try:
            from greybark.analytics.credit.credit_spreads import CreditSpreadAnalytics
            cs = CreditSpreadAnalytics()
            dashboard = cs.get_credit_dashboard()
            self._print(f"  [OK] Credit Spreads: {len(dashboard)} keys")
            return dashboard
        except Exception as e:
            self._print(f"  [ERR] Credit Spreads: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 4: Inflation Dashboard (breakevens, real rates, CPI, TIPS)
    # =========================================================================

    def collect_inflation(self) -> Dict[str, Any]:
        """
        InflationAnalytics: breakeven inflation (5y/10y/30y), real rates
        (TIPS yields), CPI decomposition, wage-price analysis, TIPS signal.
        Source: FRED (T5YIE, T10YIE, DFII*, CPIAUCSL, etc.).
        """
        self._print("  [4/12] Inflation Analytics...")
        try:
            from greybark.analytics.macro.inflation_analytics import InflationAnalytics
            ia = InflationAnalytics()
            dashboard = ia.get_inflation_dashboard()
            self._print(f"  [OK] Inflation: {len(dashboard)} keys")
            return dashboard
        except Exception as e:
            self._print(f"  [ERR] Inflation: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 5: Fed Funds Expectations (SOFR → QuantLib → Fed Funds path)
    # =========================================================================

    def collect_fed_expectations(self) -> Dict[str, Any]:
        """
        FedWatch-style expectations: SOFR forwards from CommLoan, bootstrapped
        via QuantLib into Fed Funds path by FOMC meeting.
        Source: CommLoan SOFR + QuantLib.
        """
        self._print("  [5/12] Fed Expectations...")
        try:
            from greybark.analytics.rate_expectations.usd_expectations import generate_fed_expectations
            result = generate_fed_expectations(
                current_fed_funds=self.current_fed_funds,
                num_meetings=8
            )
            meetings_count = len(result.get('meetings', []))
            self._print(f"  [OK] Fed Expectations: {meetings_count} meetings")
            return result
        except Exception as e:
            self._print(f"  [ERR] Fed Expectations: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 6: TPM Chile Expectations (SPC → QuantLib → TPM path)
    # =========================================================================

    def collect_tpm_expectations(self) -> Dict[str, Any]:
        """
        TPM expectations: Swaps Promedio Cámara from BCCh, bootstrapped
        via QuantLib into TPM path by BCCh meeting.
        Source: BCCh REST API + QuantLib.
        """
        self._print("  [6/12] TPM Expectations...")
        try:
            from greybark.analytics.rate_expectations.clp_expectations import generate_tpm_expectations
            result = generate_tpm_expectations(
                current_tpm=self.current_tpm,
                num_meetings=8
            )
            meetings_count = len(result.get('meetings', []))
            self._print(f"  [OK] TPM Expectations: {meetings_count} meetings")
            return result
        except Exception as e:
            self._print(f"  [ERR] TPM Expectations: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 7: Market vs Fed Dots
    # =========================================================================

    def collect_fed_dots(self) -> Dict[str, Any]:
        """
        Compare market implied rates (SOFR curve) vs FOMC dot plot projections.
        Source: CommLoan SOFR + FRED FOMC dots.
        """
        self._print("  [7/12] Fed Dots Comparison...")
        try:
            from greybark.analytics.rate_expectations.fed_dots_comparison import compare_market_vs_fed_dots
            result = compare_market_vs_fed_dots(
                current_fed_funds=self.current_fed_funds
            )
            self._print(f"  [OK] Fed Dots: {len(result)} keys")
            return result
        except Exception as e:
            self._print(f"  [ERR] Fed Dots: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 8: Market vs BCCh Encuesta
    # =========================================================================

    def collect_bcch_encuesta(self) -> Dict[str, Any]:
        """
        Compare market implied rates (SPC curve) vs BCCh Encuesta de
        Expectativas Económicas (EEE).
        Source: BCCh REST API + QuantLib.
        """
        self._print("  [8/12] BCCh Encuesta Comparison...")
        try:
            from greybark.analytics.rate_expectations.bcch_encuesta_comparison import compare_market_vs_encuesta
            result = compare_market_vs_encuesta(
                current_tpm=self.current_tpm
            )
            self._print(f"  [OK] BCCh Encuesta: {len(result)} keys")
            return result
        except Exception as e:
            self._print(f"  [ERR] BCCh Encuesta: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 9: Credit Spread Analysis (from DurationAnalytics)
    # =========================================================================

    def collect_credit_duration(self) -> Dict[str, Any]:
        """
        DurationAnalytics credit spread analysis: spread levels by maturity
        bucket, percentiles, compression/widening signals.
        Source: FRED ICE BofA OAS by duration bucket.
        """
        self._print("  [9/12] Credit Duration Analysis...")
        try:
            from greybark.analytics.fixed_income.duration_analytics import DurationAnalytics
            da = DurationAnalytics()
            result = da.get_credit_spread_analysis()
            self._print(f"  [OK] Credit Duration: {len(result)} keys")
            return result
        except Exception as e:
            self._print(f"  [ERR] Credit Duration: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 10: International Government Bond Yields (BCCh API)
    # =========================================================================

    def collect_international_yields(self) -> Dict[str, Any]:
        """
        Government bond yields 10Y for major markets via BCCh API.
        Series: F019.TBG.TAS.{country}.D
        Countries: USA, Germany, UK, Japan, Brazil, Mexico, Colombia, Peru.
        """
        self._print("  [10/12] International Yields (BCCh)...")
        try:
            from greybark.data_sources.bcch_client import BCChClient
            client = BCChClient()

            series_map = {
                'usa': 'F019.TBG.TAS.10.D',
                'germany': 'F019.TBG.TAS.20.D',
                'uk': 'F019.TBG.TAS.UK.D',
                'japan': 'F019.TBG.TAS.30.D',
                'brazil': 'F019.TBG.TAS.BRA.D',
                'mexico': 'F019.TBG.TAS.MEX.D',
                'colombia': 'F019.TBG.TAS.COL.D',
                'peru': 'F019.TBG.TAS.PER.D',
            }

            result = {}
            for country, code in series_map.items():
                try:
                    data = client.get_series(code, days_back=90)
                    if data is not None and len(data) > 0:
                        latest = float(data.dropna().iloc[-1])
                        prev_month = float(data.dropna().iloc[-22]) if len(data.dropna()) > 22 else None
                        result[country] = {
                            'yield_10y': round(latest, 2),
                            'vs_1m': round(latest - prev_month, 2) if prev_month else None,
                            'as_of': str(data.dropna().index[-1].date()),
                        }
                except Exception:
                    pass

            # Calcular spreads vs USA
            usa_yield = result.get('usa', {}).get('yield_10y')
            if usa_yield:
                for country in result:
                    if country != 'usa':
                        cy = result[country].get('yield_10y')
                        if cy is not None:
                            result[country]['spread_vs_usa'] = round((cy - usa_yield) * 100, 0)

            ok_count = len(result)
            self._print(f"  [OK] International Yields: {ok_count} countries")
            return result
        except Exception as e:
            self._print(f"  [ERR] International Yields: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 11: Chile Bond Yields — BCP + BCU curves (BCCh API)
    # =========================================================================

    def collect_chile_yields(self) -> Dict[str, Any]:
        """
        Chile sovereign bond yields: BCP (nominal, CLP) and BCU (real, UF).
        Daily series from BCCh API.
        BCP: F022.BCLP.TIS.AN{tenor}.NO.Z.D
        BCU: F022.BUF.TIS.AN{tenor}.UF.Z.D
        """
        self._print("  [11/12] Chile Bond Yields (BCCh)...")
        try:
            from greybark.data_sources.bcch_client import BCChClient
            client = BCChClient()

            bcp_series = {
                '1Y': 'F022.BCLP.TIS.AN01.NO.Z.D',
                '2Y': 'F022.BCLP.TIS.AN02.NO.Z.D',
                '5Y': 'F022.BCLP.TIS.AN05.NO.Z.D',
                '10Y': 'F022.BCLP.TIS.AN10.NO.Z.D',
            }

            bcu_series = {
                '2Y': 'F022.BUF.TIS.AN02.UF.Z.D',
                '5Y': 'F022.BUF.TIS.AN05.UF.Z.D',
                '10Y': 'F022.BUF.TIS.AN10.UF.Z.D',
                '20Y': 'F022.BUF.TIS.AN20.UF.Z.D',
                '30Y': 'F022.BUF.TIS.AN30.UF.Z.D',
            }

            def _fetch_curve(series_dict):
                curve = {}
                for tenor, code in series_dict.items():
                    try:
                        data = client.get_series(code, days_back=90)
                        if data is not None and len(data.dropna()) > 0:
                            clean = data.dropna()
                            latest = float(clean.iloc[-1])
                            prev_month = float(clean.iloc[-22]) if len(clean) > 22 else None
                            curve[tenor] = {
                                'yield': round(latest, 2),
                                'vs_1m': round(latest - prev_month, 2) if prev_month else None,
                                'as_of': str(clean.index[-1].date()),
                            }
                    except Exception:
                        pass
                return curve

            bcp_curve = _fetch_curve(bcp_series)
            bcu_curve = _fetch_curve(bcu_series)

            # Breakevens implícitos (BCP - BCU)
            breakevens = {}
            for tenor in ['2Y', '5Y', '10Y']:
                bcp_val = bcp_curve.get(tenor, {}).get('yield')
                bcu_val = bcu_curve.get(tenor, {}).get('yield')
                if bcp_val is not None and bcu_val is not None:
                    breakevens[tenor] = round(bcp_val - bcu_val, 2)

            # Slopes
            slopes = {}
            bcp_2 = bcp_curve.get('2Y', {}).get('yield')
            bcp_5 = bcp_curve.get('5Y', {}).get('yield')
            bcp_10 = bcp_curve.get('10Y', {}).get('yield')
            if bcp_2 is not None and bcp_10 is not None:
                slopes['2s10s'] = round((bcp_10 - bcp_2) * 100, 0)
            if bcp_2 is not None and bcp_5 is not None:
                slopes['2s5s'] = round((bcp_5 - bcp_2) * 100, 0)
            if bcp_5 is not None and bcp_10 is not None:
                slopes['5s10s'] = round((bcp_10 - bcp_5) * 100, 0)

            # Swap curve CLP + UF
            spc_clp_series = {
                '2Y': 'F022.SPC.TIN.AN02.NO.Z.D',
                '5Y': 'F022.SPC.TIN.AN05.NO.Z.D',
                '10Y': 'F022.SPC.TIN.AN10.NO.Z.D',
            }
            spc_uf_series = {
                '5Y': 'F022.SPC.TIN.AN05.UF.Z.D',
                '10Y': 'F022.SPC.TIN.AN10.UF.Z.D',
            }
            spc_clp = _fetch_curve(spc_clp_series)
            spc_uf = _fetch_curve(spc_uf_series)

            # Swap spread (SPC CLP - BCP) en bp
            swap_spread = {}
            for tenor in ['2Y', '5Y', '10Y']:
                spc_val = spc_clp.get(tenor, {}).get('yield')
                bcp_val = bcp_curve.get(tenor, {}).get('yield')
                if spc_val is not None and bcp_val is not None:
                    swap_spread[tenor] = round((spc_val - bcp_val) * 100, 0)

            result = {
                'bcp': bcp_curve,
                'bcu': bcu_curve,
                'spc_clp': spc_clp,
                'spc_uf': spc_uf,
                'breakevens': breakevens,
                'slopes': slopes,
                'swap_spread': swap_spread,
            }
            self._print(f"  [OK] Chile Yields: BCP {len(bcp_curve)}, BCU {len(bcu_curve)}, SPC {len(spc_clp)}+{len(spc_uf)} tenors")
            return result
        except Exception as e:
            self._print(f"  [ERR] Chile Yields: {e}")
            return {'error': str(e)}

    # =========================================================================
    # MÓDULO 12: Chile Rates & Market Indicators (BCCh API)
    # =========================================================================

    def collect_chile_rates(self) -> Dict[str, Any]:
        """
        Chile rates, deposit rates, lending rates, volatility from BCCh API.
        TPM, DAP, lending, interbank, VIX, MOVE, international policy rates.
        """
        self._print("  [12/12] Chile Rates & Indicators (BCCh)...")
        try:
            from greybark.data_sources.bcch_client import BCChClient
            client = BCChClient()

            result = {}

            def _latest(code, days=90):
                """Fetch latest value from BCCh series."""
                try:
                    data = client.get_series(code, days_back=days)
                    if data is not None and len(data.dropna()) > 0:
                        clean = data.dropna()
                        return round(float(clean.iloc[-1]), 2)
                except Exception:
                    pass
                return None

            def _latest_with_stats(code, days=365):
                """Fetch latest + avg/high/low for volatility indices."""
                try:
                    data = client.get_series(code, days_back=days)
                    if data is not None and len(data.dropna()) > 0:
                        clean = data.dropna()
                        return {
                            'current': round(float(clean.iloc[-1]), 2),
                            'avg_1y': round(float(clean.mean()), 2),
                            'high_1y': round(float(clean.max()), 2),
                            'low_1y': round(float(clean.min()), 2),
                            'as_of': str(clean.index[-1].date()),
                        }
                except Exception:
                    pass
                return None

            # TPM actual
            tpm = _latest('F022.TPM.TIN.D001.NO.Z.D')
            if tpm is not None:
                result['tpm'] = {'current': tpm}

            # Chile IPC YoY (from monthly variation series)
            try:
                ipc_series = bcch.get_series('F074.IPC.VAR.Z.Z.C.M', lookback_months=14)
                if ipc_series is not None and len(ipc_series) >= 13:
                    # Compute YoY from monthly variations: (1+m1/100)*(1+m2/100)*...*(1+m12/100)-1)*100
                    monthly = ipc_series.tail(12).values
                    yoy = 1.0
                    for m in monthly:
                        yoy *= (1 + m / 100)
                    result['ipc_yoy'] = round((yoy - 1) * 100, 1)
                    self._print(f"    [OK] Chile IPC YoY: {result['ipc_yoy']}%")
            except Exception:
                pass

            # DAP rates (deposit rates by tenor)
            dap_90 = _latest('F022.TDP.TIS.D090.NO.Z.D')
            dap_1y = _latest('F022.TDP.TIS.AN01.NO.Z.D')
            if dap_90 is not None or dap_1y is not None:
                result['dap'] = {}
                if dap_90 is not None:
                    result['dap']['90d'] = dap_90
                if dap_1y is not None:
                    result['dap']['1y'] = dap_1y

            # Interbank rate
            interbank = _latest('F022.TIB.TIP.D001.NO.Z.M')
            if interbank is not None:
                result['interbank'] = interbank

            # Lending rates
            lending_consumer = _latest('F022.CON.TIP.Z.NO.Z.D')
            lending_commercial = _latest('F022.COM.TIP.Z.NO.Z.D')
            lending_mortgage = _latest('F022.VIV.TIP.MA03.UF.Z.D')
            if any(v is not None for v in [lending_consumer, lending_commercial, lending_mortgage]):
                result['lending'] = {}
                if lending_consumer is not None:
                    result['lending']['consumer'] = lending_consumer
                if lending_commercial is not None:
                    result['lending']['commercial'] = lending_commercial
                if lending_mortgage is not None:
                    result['lending']['mortgage_uf'] = lending_mortgage

            # VIX
            vix = _latest_with_stats('F019.VIX.IND.90.D')
            if vix:
                result['vix'] = vix

            # MOVE (bond volatility index)
            move = _latest_with_stats('F019.MOVE.IND.90.D')
            if move:
                result['move'] = move

            # International policy rates
            intl_rates_map = {
                'fed': 'F019.TPM.TIN.10.D',
                'ecb': 'F019.TPM.TIN.20.D',
                'boj': 'F019.TPM.TIN.30.D',
                'boe': 'F019.TPM.TIN.UK.D',
                'pboc': 'F019.TPM.TIN.CHN.D',
                'bcb': 'F019.TPM.TIN.BRA.D',
                'banxico': 'F019.TPM.TIN.MEX.D',
            }
            policy_rates = {}
            for bank, code in intl_rates_map.items():
                rate = _latest(code)
                if rate is not None:
                    policy_rates[bank] = rate
            if policy_rates:
                result['policy_rates'] = policy_rates

            self._print(f"  [OK] Chile Rates: {len(result)} categories")
            return result
        except Exception as e:
            self._print(f"  [ERR] Chile Rates: {e}")
            return {'error': str(e)}

    # =========================================================================
    # ORQUESTADOR: collect_all()
    # =========================================================================

    def collect_all(self) -> Dict[str, Any]:
        """
        Ejecuta TODOS los módulos secuencialmente.
        Cada módulo falla de forma independiente.

        Returns:
            Dict con las siguientes claves:
            - duration: DurationAnalytics dashboard
            - yield_curve: Yield curve analysis (slopes, shape)
            - credit_spreads: CreditSpreadAnalytics dashboard (IG/HY by rating)
            - inflation: InflationAnalytics dashboard (breakevens, real rates)
            - fed_expectations: Fed Funds path by FOMC meeting
            - tpm_expectations: TPM path by BCCh meeting
            - fed_dots: Market vs FOMC dot plot
            - bcch_encuesta: Market vs BCCh survey
            - credit_duration: Credit spreads by duration bucket
            - international_yields: 10Y govt bond yields (BCCh)
            - chile_yields: BCP/BCU curves (BCCh)
            - chile_rates: TPM, VIX, MOVE (BCCh)
            - metadata: Timestamp, modules OK/ERR count
        """
        self._print("=" * 60)
        self._print("GREYBARK RESEARCH — RF DATA COLLECTOR")
        self._print("=" * 60)
        self._print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self._print(f"Fed Funds actual: {self.current_fed_funds}%")
        self._print(f"TPM actual: {self.current_tpm}%")
        self._print("")

        data = {}
        t0 = datetime.now()

        # Módulo 1: Duration Dashboard
        data['duration'] = self.collect_duration()

        # Módulo 2: Yield Curve
        data['yield_curve'] = self.collect_yield_curve()

        # Módulo 3: Credit Spreads (CreditSpreadAnalytics)
        data['credit_spreads'] = self.collect_credit_spreads()

        # Módulo 4: Inflation
        data['inflation'] = self.collect_inflation()

        # Módulo 5: Fed Expectations
        data['fed_expectations'] = self.collect_fed_expectations()

        # Módulo 6: TPM Expectations
        data['tpm_expectations'] = self.collect_tpm_expectations()

        # Módulo 7: Fed Dots
        data['fed_dots'] = self.collect_fed_dots()

        # Módulo 8: BCCh Encuesta
        data['bcch_encuesta'] = self.collect_bcch_encuesta()

        # Módulo 9: Credit Duration
        data['credit_duration'] = self.collect_credit_duration()

        # Módulo 10: International Yields (BCCh)
        data['international_yields'] = self.collect_international_yields()

        # Módulo 11: Chile Bond Yields (BCCh)
        data['chile_yields'] = self.collect_chile_yields()

        # Módulo 12: Chile Rates & Indicators (BCCh)
        data['chile_rates'] = self.collect_chile_rates()

        # Metadata
        elapsed = (datetime.now() - t0).total_seconds()
        modules_ok = sum(1 for k, v in data.items()
                         if k != 'metadata' and isinstance(v, dict) and 'error' not in v)
        modules_err = sum(1 for k, v in data.items()
                          if k != 'metadata' and isinstance(v, dict) and 'error' in v)

        data['metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': round(elapsed, 1),
            'modules_ok': modules_ok,
            'modules_err': modules_err,
            'fed_funds_input': self.current_fed_funds,
            'tpm_input': self.current_tpm,
        }

        self._print("")
        self._print(f"Completado en {elapsed:.1f}s — {modules_ok} OK, {modules_err} ERR")
        self._print("=" * 60)

        return data

    # =========================================================================
    # SAVE
    # =========================================================================

    def save(self, data: Dict, output_dir: Path = None) -> Path:
        """Guarda los datos recopilados en JSON."""
        out_dir = output_dir or OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = out_dir / f"rf_data_{timestamp}.json"

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"Guardado: {filepath}")
        return filepath


# =============================================================================
# CLI
# =============================================================================

def main():
    """Ejecuta el collector de RF y guarda los datos."""
    import argparse
    parser = argparse.ArgumentParser(description='Greybark Research - RF Data Collector')
    parser.add_argument('--fed-funds', type=float, default=4.50,
                        help='Current Fed Funds rate (default: 4.50)')
    parser.add_argument('--tpm', type=float, default=5.00,
                        help='Current TPM rate (default: 5.00)')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not save to file')
    parser.add_argument('--module', type=str, default=None,
                        help='Run a single module (duration, yield_curve, credit_spreads, '
                             'inflation, fed_expectations, tpm_expectations, fed_dots, '
                             'bcch_encuesta, credit_duration, international_yields, '
                             'chile_yields, chile_rates)')
    args = parser.parse_args()

    collector = RFDataCollector(
        verbose=True,
        current_fed_funds=args.fed_funds,
        current_tpm=args.tpm,
    )

    if args.module:
        # Run single module
        method_map = {
            'duration': collector.collect_duration,
            'yield_curve': collector.collect_yield_curve,
            'credit_spreads': collector.collect_credit_spreads,
            'inflation': collector.collect_inflation,
            'fed_expectations': collector.collect_fed_expectations,
            'tpm_expectations': collector.collect_tpm_expectations,
            'fed_dots': collector.collect_fed_dots,
            'bcch_encuesta': collector.collect_bcch_encuesta,
            'credit_duration': collector.collect_credit_duration,
            'international_yields': collector.collect_international_yields,
            'chile_yields': collector.collect_chile_yields,
            'chile_rates': collector.collect_chile_rates,
        }
        if args.module not in method_map:
            print(f"Módulo desconocido: {args.module}")
            print(f"Opciones: {', '.join(method_map.keys())}")
            return
        result = method_map[args.module]()
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        data = collector.collect_all()
        if not args.no_save:
            collector.save(data)

        # Resumen
        print("\n--- RESUMEN ---")
        for key, val in data.items():
            if key == 'metadata':
                continue
            if isinstance(val, dict) and 'error' in val:
                print(f"  {key}: ERROR — {val['error'][:80]}")
            else:
                print(f"  {key}: OK ({len(val) if isinstance(val, dict) else '?'} keys)")


if __name__ == '__main__':
    main()

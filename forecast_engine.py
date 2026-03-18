# -*- coding: utf-8 -*-
"""
Greybark Research - Forecast Engine
=====================================

Motor de pronósticos cuantitativos que alimenta al AI Council y los reportes.
Genera forecasts de:
- Equity targets (6 índices, 5 modelos ensemble)
- Inflación (USA, Chile, Eurozona)
- GDP (USA, Chile, China, Eurozona)
- Tasas (Fed Funds, TPM Chile, ECB)

Patrón: try/except por módulo, falla silenciosa con fallback.
Misma arquitectura que equity_data_collector.py.

Uso:
    engine = ForecastEngine(verbose=True)
    forecasts = engine.generate_all(equity_data, rf_data, quant_data)
    engine.save(forecasts)
"""

import sys
import os
import json
import time
import math
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional, Tuple

# Fix Windows console encoding
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Agregar paths
sys.path.insert(0, str(Path(__file__).parent))
LIB_PATH = Path(__file__).parent
sys.path.insert(0, str(LIB_PATH))

OUTPUT_DIR = Path(__file__).parent / "output" / "forecasts"


# =========================================================================
# CONFIGURACIÓN
# =========================================================================

# Equity Risk Premiums by region
ERP = {
    'us': 4.0,
    'europe': 4.5,
    'japan': 4.5,
    'china': 6.0,
    'chile': 6.0,
    'brazil': 6.0,
}

# ETF universe for equity targets
EQUITY_UNIVERSE = {
    'sp500':     {'ticker': 'SPY', 'name': 'S&P 500',      'region': 'us',     'erp': 4.0},
    'eurostoxx': {'ticker': 'FEZ', 'name': 'EuroStoxx 50',  'region': 'europe', 'erp': 4.5},
    'nikkei':    {'ticker': 'EWJ', 'name': 'Nikkei 225',    'region': 'japan',  'erp': 4.5},
    'csi300':    {'ticker': 'MCHI', 'name': 'CSI 300/China', 'region': 'china',  'erp': 6.0},
    'ipsa':      {'ticker': 'ECH', 'name': 'IPSA/Chile',    'region': 'chile',  'erp': 6.0},
    'bovespa':   {'ticker': 'EWZ', 'name': 'Bovespa',       'region': 'brazil', 'erp': 6.0},
}

# Top holdings for analyst target consensus (per ETF)
TOP_HOLDINGS = {
    'SPY': ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL', 'META'],
    'FEZ': ['ASML', 'SAP', 'TTE', 'SIE', 'SAN', 'AI.PA'],
    'EWJ': ['TM', 'SONY', 'MUFG', 'HMC', 'SMFG', 'NTT'],
    'MCHI': ['BABA', 'TCEHY', 'PDD', 'JD', 'BIDU', 'NIO'],
    'ECH': [],   # No liquid US-listed Chilean stocks for AV
    'EWZ': ['VALE', 'PBR', 'ITUB', 'BBD', 'ABEV', 'NU'],
}

# Model weights
MODEL_WEIGHTS = {
    'eyg': 0.30,           # Earnings Yield + Growth
    'fair_pe': 0.25,       # Fair Value PE (ERP)
    'pe_reversion': 0.20,  # PE Mean-Reversion
    'consensus': 0.15,     # Analyst Consensus
    'regime': 0.10,        # Regime Historical
}

# Historical returns by regime (annualized 12M)
REGIME_RETURNS = {
    'EXPANSION':        {'us': 12.0, 'europe': 10.0, 'japan': 8.0, 'china': 10.0, 'chile': 14.0, 'brazil': 16.0},
    'MODERATE_GROWTH':  {'us': 8.0,  'europe': 6.0,  'japan': 5.0, 'china': 6.0,  'chile': 10.0, 'brazil': 10.0},
    'LATE_CYCLE_BOOM':  {'us': 5.0,  'europe': 3.0,  'japan': 2.0, 'china': 3.0,  'chile': 6.0,  'brazil': 5.0},
    'SLOWDOWN':         {'us': -2.0, 'europe': -5.0, 'japan': -4.0,'china': -5.0, 'chile': -3.0, 'brazil': -8.0},
    'RECESSION':        {'us': -15.0,'europe': -20.0,'japan': -18.0,'china': -20.0,'chile': -15.0,'brazil': -25.0},
}


class ForecastEngine:
    """Motor de pronósticos cuantitativos para Greybark Research."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._fred = None
        self._bcch = None

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    # =====================================================================
    # LAZY LOADERS
    # =====================================================================

    def _get_fred(self):
        if self._fred is None:
            from greybark.data_sources.fred_client import FREDClient
            self._fred = FREDClient()
        return self._fred

    def _get_bcch(self):
        if self._bcch is None:
            from greybark.data_sources.bcch_extended import BCChExtendedClient
            self._bcch = BCChExtendedClient()
        return self._bcch

    def _safe_float(self, val, default=None) -> Optional[float]:
        if val is None:
            return default
        try:
            v = float(val)
            return v if not math.isnan(v) and not math.isinf(v) else default
        except (ValueError, TypeError):
            return default

    # =====================================================================
    # GENERATE ALL
    # =====================================================================

    def generate_all(
        self,
        equity_data: Dict = None,
        rf_data: Dict = None,
        quant_data: Dict = None,
    ) -> Dict[str, Any]:
        """
        Genera TODOS los pronósticos.

        Args:
            equity_data: Output de EquityDataCollector.collect_all()
            rf_data: Output de RFDataCollector.collect_all()
            quant_data: Output de CouncilDataCollector.collect_quantitative_data()

        Returns:
            Dict con forecasts completos
        """
        self._print("\n" + "=" * 60)
        self._print("FORECAST ENGINE - Generando pronósticos")
        self._print("=" * 60)
        start = time.time()

        equity_data = equity_data or {}
        rf_data = rf_data or {}
        quant_data = quant_data or {}

        modules_ok = 0
        result = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'horizon_months': 12,
                'modules_ok': 0,
            },
            'equity_targets': {},
            'inflation_forecasts': {},
            'gdp_forecasts': {},
            'rate_forecasts': {},
        }

        # 0. Run econometric models suite
        self._econ = None
        self._print("\n[0/4] Modelos econométricos...")
        try:
            from econometric_models import EconometricSuite
            suite = EconometricSuite(verbose=self.verbose)
            self._econ = suite.run_all()
            econ_ok = self._econ['metadata']['models_ok']
            econ_total = self._econ['metadata']['models_run']
            self._print(f"  [OK] Econométricos: {econ_ok}/{econ_total} modelos")
        except Exception as e:
            self._print(f"  [WARN] Econométricos no disponibles: {e}")
            self._econ = None

        # 1. Inflation forecasts
        self._print("\n[1/4] Pronósticos de inflación...")
        try:
            result['inflation_forecasts'] = self._forecast_inflation(
                quant_data, rf_data
            )
            # Blend with econometric models
            if self._econ:
                result['inflation_forecasts'] = self._blend_inflation(
                    result['inflation_forecasts']
                )
            n = sum(1 for v in result['inflation_forecasts'].values()
                    if isinstance(v, dict) and 'error' not in v)
            modules_ok += 1 if n > 0 else 0
            self._print(f"  [OK] Inflación: {n}/3 regiones")
        except Exception as e:
            self._print(f"  [ERR] Inflación: {e}")
            result['inflation_forecasts'] = {'error': str(e)}

        # 2. Rate forecasts
        self._print("\n[2/4] Pronósticos de tasas...")
        try:
            result['rate_forecasts'] = self._forecast_rates(
                quant_data, rf_data
            )
            # Blend with econometric models
            if self._econ:
                result['rate_forecasts'] = self._blend_rates(
                    result['rate_forecasts']
                )
            n = sum(1 for v in result['rate_forecasts'].values()
                    if isinstance(v, dict) and 'error' not in v)
            modules_ok += 1 if n > 0 else 0
            self._print(f"  [OK] Tasas: {n}/3 bancos centrales")
        except Exception as e:
            self._print(f"  [ERR] Tasas: {e}")
            result['rate_forecasts'] = {'error': str(e)}

        # 3. GDP forecasts
        self._print("\n[3/4] Pronósticos de GDP...")
        try:
            result['gdp_forecasts'] = self._forecast_gdp(quant_data)
            # Blend with econometric models
            if self._econ:
                result['gdp_forecasts'] = self._blend_gdp(
                    result['gdp_forecasts']
                )
            n = sum(1 for v in result['gdp_forecasts'].values()
                    if isinstance(v, dict) and 'error' not in v)
            modules_ok += 1 if n > 0 else 0
            self._print(f"  [OK] GDP: {n}/4 regiones")
        except Exception as e:
            self._print(f"  [ERR] GDP: {e}")
            result['gdp_forecasts'] = {'error': str(e)}

        # 4. Equity targets
        self._print("\n[4/4] Targets de renta variable...")
        try:
            result['equity_targets'] = self._forecast_equity(
                equity_data, quant_data
            )
            n = sum(1 for v in result['equity_targets'].values()
                    if isinstance(v, dict) and 'error' not in v)
            modules_ok += 1 if n > 0 else 0
            self._print(f"  [OK] Equity: {n}/6 índices")
        except Exception as e:
            self._print(f"  [ERR] Equity: {e}")
            result['equity_targets'] = {'error': str(e)}

        # 5. IMF WEO Consensus
        self._print("\n[5/5] IMF WEO consensus...")
        try:
            from imf_weo_client import IMFWEOClient
            imf = IMFWEOClient()
            consensus = imf.fetch_consensus(year=2026)
            if 'error' not in consensus:
                result['imf_consensus'] = consensus
                # Inject into individual forecasts
                for region in ('usa', 'eurozone', 'china', 'chile'):
                    gdp_fc = result.get('gdp_forecasts', {}).get(region)
                    if isinstance(gdp_fc, dict) and 'error' not in gdp_fc:
                        gdp_fc['consensus_imf'] = consensus.get('gdp', {}).get(region)
                    infl_fc = result.get('inflation_forecasts', {}).get(region)
                    if isinstance(infl_fc, dict) and 'error' not in infl_fc:
                        infl_fc['consensus_imf'] = consensus.get('inflation', {}).get(region)
                n_gdp = sum(1 for v in consensus.get('gdp', {}).values() if v is not None)
                n_infl = sum(1 for v in consensus.get('inflation', {}).values() if v is not None)
                self._print(f"  [OK] IMF WEO: {n_gdp} GDP + {n_infl} inflación")
            else:
                self._print(f"  [WARN] IMF WEO: {consensus['error']}")
                result['imf_consensus'] = consensus
        except Exception as e:
            self._print(f"  [WARN] IMF WEO no disponible: {e}")
            result['imf_consensus'] = {'error': str(e)}

        elapsed = time.time() - start
        result['metadata']['modules_ok'] = modules_ok
        result['metadata']['elapsed_seconds'] = round(elapsed, 1)
        if self._econ:
            result['metadata']['econometric_models'] = {
                'models_run': self._econ['metadata']['models_run'],
                'models_ok': self._econ['metadata']['models_ok'],
            }
        result['econometric_detail'] = self._econ if self._econ else None

        self._print(f"\n{'=' * 60}")
        self._print(f"Forecast Engine completado: {modules_ok}/4 módulos OK ({elapsed:.1f}s)")
        self._print(f"{'=' * 60}\n")

        return result

    # =====================================================================
    # INFLATION FORECASTS
    # =====================================================================

    def _forecast_inflation(self, quant: Dict, rf_data: Dict) -> Dict:
        """Genera pronósticos de inflación para USA, Chile, Eurozona."""
        forecasts = {}

        # USA
        try:
            forecasts['usa'] = self._forecast_inflation_usa(quant, rf_data)
            self._print(f"    USA: {forecasts['usa'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    USA: ERR - {e}")
            forecasts['usa'] = {'error': str(e)}

        # Chile
        try:
            forecasts['chile'] = self._forecast_inflation_chile(quant)
            self._print(f"    Chile: {forecasts['chile'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    Chile: ERR - {e}")
            forecasts['chile'] = {'error': str(e)}

        # Eurozone
        try:
            forecasts['eurozone'] = self._forecast_inflation_eurozone()
            self._print(f"    Eurozona: {forecasts['eurozone'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    Eurozona: ERR - {e}")
            forecasts['eurozone'] = {'error': str(e)}

        return forecasts

    def _forecast_inflation_usa(self, quant: Dict, rf_data: Dict) -> Dict:
        """
        USA inflation forecast.
        Sources: Breakeven 5Y (40%) + Michigan Survey (30%) + Cleveland Fed (30%)
        """
        fred = self._get_fred()
        components = {}

        # 1. Breakeven 5Y (T5YIE) — market expectation
        be5y = None
        try:
            be5y_val = fred.get_latest_value('T5YIE')
            if be5y_val:
                be5y = round(float(be5y_val), 2)
                components['breakeven_5y'] = be5y
        except Exception:
            pass

        # Fallback: use quant inflation data
        if be5y is None:
            infl = quant.get('inflation', {})
            if isinstance(infl, dict) and 'error' not in infl:
                be5y = self._safe_float(infl.get('breakeven_5y'))
                if be5y:
                    components['breakeven_5y'] = be5y

        # 2. Michigan Survey (MICH) — consumer expectation
        michigan = None
        try:
            mich_val = fred.get_latest_value('MICH')
            if mich_val:
                michigan = round(float(mich_val), 2)
                components['michigan_1y'] = michigan
        except Exception:
            pass

        # 3. Cleveland Fed 1Y expected inflation (EXPINF1YR)
        cleveland = None
        try:
            clev_val = fred.get_latest_value('EXPINF1YR')
            if clev_val:
                cleveland = round(float(clev_val), 2)
                components['cleveland_1y'] = cleveland
        except Exception:
            pass

        # Current CPI
        current = None
        try:
            cpi_val = fred.get_latest_value('CPIAUCSL')
            cpi_series = fred.get_series('CPIAUCSL')
            if cpi_series is not None and len(cpi_series) >= 13:
                last = float(cpi_series.iloc[-1])
                year_ago = float(cpi_series.iloc[-13])
                current = round((last / year_ago - 1) * 100, 2)
                components['current_cpi_yoy'] = current
        except Exception:
            pass

        # Weighted average: 40% breakeven + 30% michigan + 30% cleveland
        values = []
        weights = []
        if be5y is not None:
            values.append(be5y)
            weights.append(0.40)
        if michigan is not None:
            values.append(michigan)
            weights.append(0.30)
        if cleveland is not None:
            values.append(cleveland)
            weights.append(0.30)

        if not values:
            return {'error': 'No inflation data available', 'components': components}

        # Normalize weights
        total_w = sum(weights)
        forecast = sum(v * w for v, w in zip(values, weights)) / total_w
        forecast = round(forecast, 2)

        # Range = min/max of inputs
        range_low = round(min(values) - 0.2, 1)
        range_high = round(max(values) + 0.2, 1)

        # Trend
        trend = 'STABLE'
        if current and forecast < current - 0.3:
            trend = 'DECLINING'
        elif current and forecast > current + 0.3:
            trend = 'RISING'

        return {
            'current': current,
            'forecast_12m': forecast,
            'range': [range_low, range_high],
            'trend': trend,
            'components': components,
            'weights': {'breakeven_5y': 0.40, 'michigan': 0.30, 'cleveland': 0.30},
        }

    def _forecast_inflation_chile(self, quant: Dict) -> Dict:
        """
        Chile inflation forecast.
        Sources: BCCh EEE 12M (60%) + Breakeven BCP/BCU (40%)
        Fallback: CPI trend from F074 monthly variations (50%) + BCCh target 3% (50%)
        """
        bcch = self._get_bcch()
        components = {}

        # 1. BCCh EEE IPC 12M (F089.IPC.V12.Z.M) — may be blocked on API
        eee_ipc = None
        try:
            val = bcch.get_latest('F089.IPC.V12.Z.M')
            if val is not None:
                eee_ipc = round(float(val), 2)
                components['eee_ipc_12m'] = eee_ipc
        except Exception:
            pass

        # 2. Breakeven from BCP vs BCU (chile_analytics)
        chile_be = None
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            chile = ChileAnalytics()
            be_data = chile.get_breakeven_inflation()
            if be_data and 'breakevens' in be_data:
                be5y = self._safe_float(be_data['breakevens'].get('5Y'))
                if be5y:
                    chile_be = round(be5y, 2)
                    components['breakeven_5y'] = chile_be
        except Exception:
            pass

        # 3. Current IPC YoY from F074 monthly variations (rolling 12M product)
        current = None
        chile_data = quant.get('chile', {})
        if isinstance(chile_data, dict) and 'error' not in chile_data:
            current = self._safe_float(chile_data.get('ipc'))
            if current:
                components['current_ipc_yoy'] = round(current, 2)

        # If no current from quant, compute from BCCh F074 monthly variations
        cpi_trend = None
        if current is None or eee_ipc is None:
            try:
                cpi_series = bcch.get_series('F074.IPC.VAR.Z.Z.C.M', days_back=730)
                if cpi_series is not None and len(cpi_series) >= 12:
                    # Compute YoY: product of (1 + monthly_var/100) over last 12 months
                    last12 = cpi_series.iloc[-12:].astype(float)
                    yoy = (1 + last12 / 100).prod()
                    cpi_yoy = round((yoy - 1) * 100, 2)
                    components['cpi_yoy_computed'] = cpi_yoy
                    if current is None:
                        current = cpi_yoy
                        components['current_ipc_yoy'] = cpi_yoy
                    # Use recent 6M trend to project forward
                    last6 = cpi_series.iloc[-6:].astype(float)
                    ann_rate = round(((1 + last6.mean() / 100) ** 12 - 1) * 100, 2)
                    cpi_trend = ann_rate
                    components['cpi_trend_6m_ann'] = ann_rate
            except Exception:
                pass

        # Weighted: 60% EEE + 40% breakeven
        values = []
        weights = []
        if eee_ipc is not None:
            values.append(eee_ipc)
            weights.append(0.60)
        if chile_be is not None:
            values.append(chile_be)
            weights.append(0.40)

        # Fallback: CPI trend (50%) + BCCh target 3% (50%)
        if not values:
            bcch_target = 3.0
            components['bcch_target'] = bcch_target
            if cpi_trend is not None:
                values.append(cpi_trend)
                weights.append(0.50)
            elif current is not None:
                values.append(current)
                weights.append(0.50)
            values.append(bcch_target)
            weights.append(0.50)

        if not values:
            return {'error': 'No Chile inflation data', 'components': components}

        total_w = sum(weights)
        forecast = round(sum(v * w for v, w in zip(values, weights)) / total_w, 2)

        range_low = round(min(values) - 0.3, 1)
        range_high = round(max(values) + 0.3, 1)

        trend = 'STABLE'
        if current and forecast < current - 0.3:
            trend = 'DECLINING'
        elif current and forecast > current + 0.3:
            trend = 'RISING'

        return {
            'current': round(current, 2) if current else None,
            'forecast_12m': forecast,
            'range': [range_low, range_high],
            'trend': trend,
            'components': components,
            'weights': {'eee_12m': 0.60, 'breakeven': 0.40},
        }

    def _forecast_inflation_eurozone(self) -> Dict:
        """
        Eurozone inflation forecast.
        Sources: BCCh IPC intl trend (50%) + ECB target anchor 2% (50%)
        """
        bcch = self._get_bcch()
        components = {}

        # 1. BCCh IPC Eurozone YoY trend
        current_ez = None
        try:
            val = bcch.get_latest('F019.IPC.V12.20.M')
            if val is not None:
                current_ez = round(float(val), 2)
                components['current_ipc_yoy'] = current_ez
        except Exception:
            pass

        # 2. ECB target anchor
        ecb_target = 2.0
        components['ecb_target'] = ecb_target

        # Trend-based: current moves toward target
        if current_ez is not None:
            # 50% current trend + 50% target anchor
            forecast = round(current_ez * 0.50 + ecb_target * 0.50, 2)
        else:
            forecast = ecb_target

        range_low = round(forecast - 0.3, 1)
        range_high = round(forecast + 0.3, 1)

        trend = 'STABLE'
        if current_ez and forecast < current_ez - 0.3:
            trend = 'DECLINING'
        elif current_ez and forecast > current_ez + 0.3:
            trend = 'RISING'

        return {
            'current': current_ez,
            'forecast_12m': forecast,
            'range': [range_low, range_high],
            'trend': trend,
            'components': components,
            'weights': {'bcch_trend': 0.50, 'ecb_anchor': 0.50},
        }

    # =====================================================================
    # RATE FORECASTS
    # =====================================================================

    def _forecast_rates(self, quant: Dict, rf_data: Dict) -> Dict:
        """Genera pronósticos de tasas para Fed, TPM, ECB."""
        forecasts = {}

        # Fed Funds
        try:
            forecasts['fed_funds'] = self._forecast_rates_fed(quant, rf_data)
            self._print(f"    Fed: {forecasts['fed_funds'].get('current', '?')}% -> "
                       f"{forecasts['fed_funds'].get('forecast_12m', '?')}%")
        except Exception as e:
            self._print(f"    Fed: ERR - {e}")
            forecasts['fed_funds'] = {'error': str(e)}

        # TPM Chile
        try:
            forecasts['tpm_chile'] = self._forecast_rates_tpm(quant, rf_data)
            self._print(f"    TPM: {forecasts['tpm_chile'].get('current', '?')}% -> "
                       f"{forecasts['tpm_chile'].get('forecast_12m', '?')}%")
        except Exception as e:
            self._print(f"    TPM: ERR - {e}")
            forecasts['tpm_chile'] = {'error': str(e)}

        # ECB
        try:
            forecasts['ecb'] = self._forecast_rates_ecb()
            self._print(f"    ECB: {forecasts['ecb'].get('current', '?')}% -> "
                       f"{forecasts['ecb'].get('forecast_12m', '?')}%")
        except Exception as e:
            self._print(f"    ECB: ERR - {e}")
            forecasts['ecb'] = {'error': str(e)}

        return forecasts

    def _forecast_rates_fed(self, quant: Dict, rf_data: Dict) -> Dict:
        """Fed Funds forecast. Wraps existing usd_expectations module."""
        # Get actual Fed Funds rate from FRED (most reliable)
        fred_rate = None
        try:
            fred = self._get_fred()
            val = fred.get_latest_value('DFF')
            if val is not None:
                fred_rate = round(float(val), 2)
        except Exception:
            pass

        # Use existing rates data if available
        rates = quant.get('rates', {})
        if isinstance(rates, dict) and 'error' not in rates:
            fed_exp = rates.get('fed_expectations', {})
            summary = fed_exp.get('summary', {})
            # Prefer FRED actual rate over module default
            current = fred_rate or self._safe_float(fed_exp.get('current_rate'), 4.25)
            terminal = self._safe_float(summary.get('terminal_rate'))
            cuts = summary.get('cuts_expected', 0)
            hikes = summary.get('hikes_expected', 0)
            direction = summary.get('direction', 'HOLD')

            # Estimate 6m and 12m rates from meetings
            meetings = fed_exp.get('meetings', [])
            rate_6m = current
            rate_12m = terminal if terminal else current
            for m in meetings:
                days = m.get('days_to_meeting', 0)
                exp_rate = self._safe_float(m.get('expected_rate'))
                if exp_rate:
                    if 150 < days < 210:
                        rate_6m = exp_rate
                    elif 330 < days < 400:
                        rate_12m = exp_rate

            return {
                'current': current,
                'forecast_6m': round(rate_6m, 2),
                'forecast_12m': round(rate_12m, 2),
                'terminal': round(terminal, 2) if terminal else None,
                'direction': direction,
                'cuts_expected': cuts,
                'hikes_expected': hikes,
            }

        # Fallback: call module directly
        from greybark.analytics.rate_expectations.usd_expectations import generate_fed_expectations
        fallback_fed = fred_rate or 4.25
        fed_exp = generate_fed_expectations(current_fed_funds=fallback_fed, num_meetings=12)
        summary = fed_exp.get('summary', {})
        return {
            'current': fred_rate or fed_exp.get('current_rate', 4.25),
            'forecast_6m': None,
            'forecast_12m': self._safe_float(summary.get('terminal_rate')),
            'terminal': self._safe_float(summary.get('terminal_rate')),
            'direction': summary.get('direction', 'HOLD'),
            'cuts_expected': summary.get('cuts_expected', 0),
            'hikes_expected': summary.get('hikes_expected', 0),
        }

    def _forecast_rates_tpm(self, quant: Dict, rf_data: Dict) -> Dict:
        """TPM Chile forecast. Wraps existing clp_expectations module."""
        # Get actual TPM from BCCh chile_rates (most reliable)
        bcch_tpm = None
        if rf_data and isinstance(rf_data, dict):
            chile_rates = rf_data.get('chile_rates', {})
            if isinstance(chile_rates, dict) and 'error' not in chile_rates:
                tpm_data = chile_rates.get('tpm', {})
                if isinstance(tpm_data, dict):
                    bcch_tpm = self._safe_float(tpm_data.get('current'))

        # Try rf_data first (has tpm_expectations)
        tpm_exp = None
        if rf_data and isinstance(rf_data, dict) and 'error' not in rf_data:
            tpm_exp = rf_data.get('tpm_expectations', {})
            if isinstance(tpm_exp, dict) and 'error' in tpm_exp:
                tpm_exp = None

        if tpm_exp:
            summary = tpm_exp.get('summary', {})
            # Prefer BCCh actual TPM over tpm_expectations default
            current = bcch_tpm or self._safe_float(tpm_exp.get('current_rate'), 4.50)
            terminal = self._safe_float(summary.get('tasa_terminal'))

            meetings = tpm_exp.get('meetings', [])
            rate_6m = current
            rate_12m = terminal if terminal else current
            for m in meetings:
                days = m.get('days_to_meeting', 0)
                exp_rate = self._safe_float(m.get('expected_rate'))
                if exp_rate:
                    if 150 < days < 210:
                        rate_6m = exp_rate
                    elif 330 < days < 400:
                        rate_12m = exp_rate

            direction_map = {'RECORTES': 'EASING', 'ALZAS': 'TIGHTENING', 'MANTENCIÓN': 'HOLD'}
            direction = direction_map.get(summary.get('direction', ''), summary.get('direction', 'HOLD'))

            return {
                'current': current,
                'forecast_6m': round(rate_6m, 2),
                'forecast_12m': round(rate_12m, 2),
                'terminal': round(terminal, 2) if terminal else None,
                'direction': direction,
                'cuts_expected': summary.get('recortes_esperados', 0),
                'hikes_expected': summary.get('alzas_esperadas', 0),
            }

        # Fallback: call module directly
        from greybark.analytics.rate_expectations.clp_expectations import generate_tpm_expectations
        fallback_tpm = bcch_tpm or 4.50
        tpm_exp = generate_tpm_expectations(current_tpm=fallback_tpm, num_meetings=12)
        summary = tpm_exp.get('summary', {})
        direction_map = {'RECORTES': 'EASING', 'ALZAS': 'TIGHTENING', 'MANTENCIÓN': 'HOLD'}
        return {
            'current': tpm_exp.get('current_rate', 5.00),
            'forecast_6m': None,
            'forecast_12m': self._safe_float(summary.get('tasa_terminal')),
            'terminal': self._safe_float(summary.get('tasa_terminal')),
            'direction': direction_map.get(summary.get('direction', ''), 'HOLD'),
            'cuts_expected': summary.get('recortes_esperados', 0),
            'hikes_expected': summary.get('alzas_esperadas', 0),
        }

    def _forecast_rates_ecb(self) -> Dict:
        """ECB rate forecast. Simple inflation gap model."""
        bcch = self._get_bcch()

        # Current ECB rate
        current = None
        try:
            val = bcch.get_latest('F019.TPM.TIN.GE.D')
            if val is not None:
                current = round(float(val), 2)
        except Exception:
            pass

        if current is None:
            current = 2.50  # reasonable default

        # Inflation gap model: if inflation > 2%, ECB holds/hikes; if < 2%, ECB cuts
        ez_inflation = None
        try:
            val = bcch.get_latest('F019.IPC.V12.20.M')
            if val is not None:
                ez_inflation = round(float(val), 2)
        except Exception:
            pass

        target = 2.0
        if ez_inflation is not None:
            gap = ez_inflation - target
            # Rule: ~25bp adjustment per 0.5% inflation gap, max 2 moves in 12M
            moves = max(-2, min(2, round(gap / 0.50)))
            forecast_12m = round(current + moves * 0.25, 2)
            direction = 'EASING' if moves < 0 else ('TIGHTENING' if moves > 0 else 'HOLD')
        else:
            # Default: 1 cut over 12M
            forecast_12m = round(current - 0.25, 2)
            direction = 'EASING'

        forecast_6m = round((current + forecast_12m) / 2 * 4) / 4  # Round to nearest 25bp

        return {
            'current': current,
            'forecast_6m': forecast_6m,
            'forecast_12m': forecast_12m,
            'terminal': forecast_12m,
            'direction': direction,
            'cuts_expected': max(0, round((current - forecast_12m) / 0.25)),
            'hikes_expected': max(0, round((forecast_12m - current) / 0.25)),
            'inflation_gap': round(ez_inflation - target, 2) if ez_inflation else None,
        }

    # =====================================================================
    # GDP FORECASTS
    # =====================================================================

    def _forecast_gdp(self, quant: Dict) -> Dict:
        """Genera pronósticos de GDP para USA, Chile, China, Eurozona."""
        forecasts = {}

        # USA
        try:
            forecasts['usa'] = self._forecast_gdp_usa(quant)
            self._print(f"    USA: {forecasts['usa'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    USA: ERR - {e}")
            forecasts['usa'] = {'error': str(e)}

        # Chile
        try:
            forecasts['chile'] = self._forecast_gdp_chile(quant)
            self._print(f"    Chile: {forecasts['chile'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    Chile: ERR - {e}")
            forecasts['chile'] = {'error': str(e)}

        # China
        try:
            forecasts['china'] = self._forecast_gdp_china(quant)
            self._print(f"    China: {forecasts['china'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    China: ERR - {e}")
            forecasts['china'] = {'error': str(e)}

        # Eurozone
        try:
            forecasts['eurozone'] = self._forecast_gdp_eurozone()
            self._print(f"    Eurozona: {forecasts['eurozone'].get('forecast_12m', 'N/A')}%")
        except Exception as e:
            self._print(f"    Eurozona: ERR - {e}")
            forecasts['eurozone'] = {'error': str(e)}

        return forecasts

    def _forecast_gdp_usa(self, quant: Dict) -> Dict:
        """
        USA GDP forecast.
        Sources: GDPNow (40%) + LEI trend (30%) + Yield curve 2s10s (30%)
        """
        fred = self._get_fred()
        components = {}

        # Current GDP from quant
        current = None
        macro_usa = quant.get('macro_usa', {})
        if isinstance(macro_usa, dict) and 'error' not in macro_usa:
            gdp_data = macro_usa.get('gdp', {})
            if isinstance(gdp_data, dict):
                current = self._safe_float(gdp_data.get('qoq_change') or gdp_data.get('value'))

        # 1. Atlanta Fed GDPNow
        gdpnow = None
        try:
            val = fred.get_latest_value('GDPNOW')
            if val is not None:
                gdpnow = round(float(val), 2)
                components['gdpnow'] = gdpnow
        except Exception:
            pass

        # 2. LEI trend signal
        lei_signal = 'STABLE'
        lei_val = None
        try:
            lei_series = fred.get_series('USSLIND')
            if lei_series is not None and len(lei_series) >= 7:
                latest = float(lei_series.iloc[-1])
                six_ago = float(lei_series.iloc[-7])
                lei_change = ((latest / six_ago) - 1) * 100
                components['lei_6m_change'] = round(lei_change, 2)
                if lei_change < -2:
                    lei_signal = 'CONTRACTING'
                    lei_val = 0.5  # weak GDP
                elif lei_change < 0:
                    lei_signal = 'WEAKENING'
                    lei_val = 1.5
                elif lei_change < 2:
                    lei_signal = 'STABLE'
                    lei_val = 2.2
                else:
                    lei_signal = 'EXPANDING'
                    lei_val = 2.8
                components['lei_signal'] = lei_signal
        except Exception:
            pass

        # 3. Yield curve 2s10s
        yc_signal = 'NEUTRAL'
        yc_val = None
        try:
            spread = fred.get_latest_value('T10Y2Y')
            if spread is not None:
                spread = float(spread)
                components['yield_curve_2s10s'] = round(spread, 2)
                if spread < -0.5:
                    yc_signal = 'RECESSION_WARNING'
                    yc_val = 0.5
                elif spread < 0:
                    yc_signal = 'CAUTION'
                    yc_val = 1.5
                elif spread < 0.5:
                    yc_signal = 'NEUTRAL'
                    yc_val = 2.0
                else:
                    yc_signal = 'POSITIVE'
                    yc_val = 2.5
                components['yc_signal'] = yc_signal
        except Exception:
            pass

        # Weighted average: 40% GDPNow + 30% LEI + 30% yield curve
        values = []
        weights = []
        if gdpnow is not None:
            values.append(gdpnow)
            weights.append(0.40)
        if lei_val is not None:
            values.append(lei_val)
            weights.append(0.30)
        if yc_val is not None:
            values.append(yc_val)
            weights.append(0.30)

        if not values:
            # Ultimate fallback
            return {
                'current': current,
                'forecast_12m': 2.0,
                'gdpnow': None,
                'lei_signal': 'UNKNOWN',
                'components': components,
            }

        total_w = sum(weights)
        forecast = round(sum(v * w for v, w in zip(values, weights)) / total_w, 2)

        return {
            'current': round(current, 2) if current else None,
            'forecast_12m': forecast,
            'gdpnow': gdpnow,
            'lei_signal': lei_signal,
            'components': components,
            'weights': {'gdpnow': 0.40, 'lei': 0.30, 'yield_curve': 0.30},
        }

    def _forecast_gdp_chile(self, quant: Dict) -> Dict:
        """
        Chile GDP forecast.
        Sources: BCCh EEE PIB (70%) + IMACEC trend (30%)
        """
        bcch = self._get_bcch()
        components = {}

        # Current IMACEC
        current = None
        chile_data = quant.get('chile', {})
        if isinstance(chile_data, dict) and 'error' not in chile_data:
            current = self._safe_float(chile_data.get('imacec'))
            if current:
                components['imacec_yoy'] = round(current, 2)

        # 1. BCCh EEE PIB año actual
        eee_pib = None
        try:
            val = bcch.get_latest('F089.PIB.VAR.Z.M')
            if val is not None:
                eee_pib = round(float(val), 2)
                components['eee_pib_actual'] = eee_pib
        except Exception:
            pass

        # If EEE not available, try next year
        if eee_pib is None:
            try:
                val = bcch.get_latest('F089.PIB.VAR.Z1.M')
                if val is not None:
                    eee_pib = round(float(val), 2)
                    components['eee_pib_siguiente'] = eee_pib
            except Exception:
                pass

        # 2. IMACEC trend (simple 6-month average as proxy)
        imacec_trend = None
        try:
            imacec_series = bcch.get_series('F032.IMC.V12.Z.Z.2018.Z.Z.0.M')
            if imacec_series is not None and len(imacec_series) >= 6:
                last_6 = imacec_series.iloc[-6:].astype(float)
                imacec_trend = round(float(last_6.mean()), 2)
                components['imacec_6m_avg'] = imacec_trend
        except Exception:
            pass

        # Weighted: 70% EEE + 30% IMACEC trend
        values = []
        weights = []
        if eee_pib is not None:
            values.append(eee_pib)
            weights.append(0.70)
        if imacec_trend is not None:
            values.append(imacec_trend)
            weights.append(0.30)

        if not values:
            return {'current': current, 'forecast_12m': 2.0, 'components': components}

        total_w = sum(weights)
        forecast = round(sum(v * w for v, w in zip(values, weights)) / total_w, 2)

        return {
            'current': round(current, 2) if current else None,
            'forecast_12m': forecast,
            'components': components,
            'weights': {'eee_pib': 0.70, 'imacec_trend': 0.30},
        }

    def _forecast_gdp_china(self, quant: Dict) -> Dict:
        """
        China GDP forecast.
        Sources: BCCh GDP QoQ (50%) + Credit impulse (30%) + Commodities (20%)
        """
        bcch = self._get_bcch()
        components = {}

        # 1. BCCh GDP China QoQ
        gdp_qoq = None
        try:
            val = bcch.get_latest('F019.PIB.VAR.CHN.T')
            if val is not None:
                gdp_qoq = round(float(val), 2)
                components['gdp_qoq'] = gdp_qoq
        except Exception:
            pass

        # 2. Credit impulse from quant
        credit_signal = None
        china_data = quant.get('china', {})
        if isinstance(china_data, dict) and 'error' not in china_data:
            ci = china_data.get('credit_impulse', {})
            if isinstance(ci, dict):
                signal = ci.get('impulse_signal', 'unknown')
                components['credit_impulse'] = signal
                if signal == 'expansion':
                    credit_signal = 5.0
                elif signal == 'neutral':
                    credit_signal = 4.5
                else:
                    credit_signal = 3.5

        # 3. Commodity demand
        commodity_signal = None
        if isinstance(china_data, dict) and 'error' not in china_data:
            cd = china_data.get('commodity_demand', {})
            if isinstance(cd, dict):
                composite = cd.get('composite', 'NEUTRAL')
                components['commodity_demand'] = composite
                if composite == 'EXPANSION':
                    commodity_signal = 5.0
                elif composite == 'NEUTRAL':
                    commodity_signal = 4.5
                else:
                    commodity_signal = 3.5

        # Weighted: 50% GDP QoQ + 30% credit + 20% commodities
        values = []
        weights = []
        if gdp_qoq is not None:
            values.append(gdp_qoq)
            weights.append(0.50)
        if credit_signal is not None:
            values.append(credit_signal)
            weights.append(0.30)
        if commodity_signal is not None:
            values.append(commodity_signal)
            weights.append(0.20)

        if not values:
            return {'current': gdp_qoq, 'forecast_12m': 4.5, 'components': components}

        total_w = sum(weights)
        forecast = round(sum(v * w for v, w in zip(values, weights)) / total_w, 2)

        return {
            'current': gdp_qoq,
            'forecast_12m': forecast,
            'components': components,
            'weights': {'gdp_qoq': 0.50, 'credit_impulse': 0.30, 'commodities': 0.20},
        }

    def _forecast_gdp_eurozone(self) -> Dict:
        """
        Eurozone GDP forecast.
        Sources: BCCh GDP QoQ (60%) + unemployment trend (40%)
        """
        bcch = self._get_bcch()
        components = {}

        # 1. BCCh GDP Eurozone QoQ
        gdp_qoq = None
        try:
            val = bcch.get_latest('F019.PIB.VAR.20.T')
            if val is not None:
                gdp_qoq = round(float(val), 2)
                components['gdp_qoq'] = gdp_qoq
        except Exception:
            pass

        # 2. Unemployment trend
        unemp_signal = None
        try:
            unemp_series = bcch.get_series('F019.DES.TAS.20.M')
            if unemp_series is not None and len(unemp_series) >= 7:
                latest = float(unemp_series.iloc[-1])
                six_ago = float(unemp_series.iloc[-7])
                change = latest - six_ago
                components['unemployment'] = round(latest, 2)
                components['unemployment_6m_change'] = round(change, 2)
                # Lower unemployment = better GDP
                if change < -0.3:
                    unemp_signal = 1.8  # improving
                elif change < 0:
                    unemp_signal = 1.4
                elif change < 0.3:
                    unemp_signal = 1.0
                else:
                    unemp_signal = 0.5  # deteriorating
        except Exception:
            pass

        # Weighted: 60% GDP QoQ + 40% unemployment
        values = []
        weights = []
        if gdp_qoq is not None:
            values.append(gdp_qoq)
            weights.append(0.60)
        if unemp_signal is not None:
            values.append(unemp_signal)
            weights.append(0.40)

        if not values:
            return {'current': gdp_qoq, 'forecast_12m': 1.2, 'components': components}

        total_w = sum(weights)
        forecast = round(sum(v * w for v, w in zip(values, weights)) / total_w, 2)

        return {
            'current': gdp_qoq,
            'forecast_12m': forecast,
            'components': components,
            'weights': {'gdp_qoq': 0.60, 'unemployment': 0.40},
        }

    # =====================================================================
    # EQUITY TARGETS
    # =====================================================================

    def _forecast_equity(self, equity_data: Dict, quant_data: Dict) -> Dict:
        """Genera targets para 6 índices usando 5 modelos ensemble."""
        targets = {}

        # Get regime for Model 5
        regime = 'MODERATE_GROWTH'
        regime_data = quant_data.get('regime', {})
        if isinstance(regime_data, dict) and 'error' not in regime_data:
            regime = regime_data.get('current_regime',
                     regime_data.get('classification', 'MODERATE_GROWTH'))

        # Get real rate for Model 2
        real_rate = None
        try:
            fred = self._get_fred()
            tips10 = fred.get_latest_value('DFII10')  # 10Y TIPS
            if tips10 is not None:
                real_rate = float(tips10)
        except Exception:
            pass
        if real_rate is None:
            # Fallback from quant inflation data
            infl = quant_data.get('inflation', {})
            if isinstance(infl, dict) and 'error' not in infl:
                real_rate = self._safe_float(infl.get('real_rate_10y'))
        if real_rate is None:
            real_rate = 2.0  # sensible default

        for idx_key, idx_cfg in EQUITY_UNIVERSE.items():
            try:
                target = self._forecast_single_equity(
                    idx_key, idx_cfg, equity_data, real_rate, regime
                )
                targets[idx_key] = target
                ret = target.get('expected_return_pct', 0)
                sig = target.get('signal', '?')
                self._print(f"    {idx_cfg['name']}: {ret:+.1f}% ({sig})")
            except Exception as e:
                self._print(f"    {idx_cfg['name']}: ERR - {e}")
                targets[idx_key] = {'error': str(e)}

        return targets

    def _forecast_single_equity(
        self,
        idx_key: str,
        idx_cfg: Dict,
        equity_data: Dict,
        real_rate: float,
        regime: str,
    ) -> Dict:
        """
        Genera target para un índice usando 5 modelos ensemble.
        """
        ticker = idx_cfg['ticker']
        region = idx_cfg['region']
        erp = idx_cfg['erp']

        # Get current price from yfinance
        current_price = self._get_etf_price(ticker)
        if current_price is None:
            return {'error': f'No price for {ticker}'}

        # Get valuations from equity_data
        valuations = {}
        if equity_data and isinstance(equity_data, dict) and 'error' not in equity_data:
            val_data = equity_data.get('valuations', {})
            if isinstance(val_data, dict) and 'error' not in val_data:
                for reg_key, reg_val in val_data.items():
                    if isinstance(reg_val, dict) and reg_val.get('ticker') == ticker:
                        valuations = reg_val
                        break

        forward_pe = self._safe_float(valuations.get('forward_pe'))
        trailing_pe = self._safe_float(valuations.get('trailing_pe'))

        models = {}
        model_returns = {}

        # ---- Model 1: Earnings Yield + Growth (30%) ----
        try:
            ret1 = self._model_eyg(forward_pe, equity_data, ticker)
            if ret1 is not None:
                models['eyg'] = {'return_pct': round(ret1, 2), 'status': 'OK'}
                model_returns['eyg'] = ret1
        except Exception as e:
            models['eyg'] = {'error': str(e)}

        # ---- Model 2: Fair Value PE via ERP (25%) ----
        try:
            ret2 = self._model_fair_pe(real_rate, erp, forward_pe, current_price, valuations)
            if ret2 is not None:
                models['fair_pe'] = {'return_pct': round(ret2, 2), 'status': 'OK'}
                model_returns['fair_pe'] = ret2
        except Exception as e:
            models['fair_pe'] = {'error': str(e)}

        # ---- Model 3: PE Mean-Reversion (20%) ----
        try:
            ret3 = self._model_pe_reversion(ticker, trailing_pe)
            if ret3 is not None:
                models['pe_reversion'] = {'return_pct': round(ret3, 2), 'status': 'OK'}
                model_returns['pe_reversion'] = ret3
        except Exception as e:
            models['pe_reversion'] = {'error': str(e)}

        # ---- Model 4: Analyst Consensus (15%) ----
        try:
            ret4 = self._model_consensus(ticker, current_price)
            if ret4 is not None:
                models['consensus'] = {'return_pct': round(ret4, 2), 'status': 'OK'}
                model_returns['consensus'] = ret4
        except Exception as e:
            models['consensus'] = {'error': str(e)}

        # ---- Model 5: Regime Historical (10%) ----
        try:
            ret5 = REGIME_RETURNS.get(regime, REGIME_RETURNS['MODERATE_GROWTH']).get(region, 5.0)
            models['regime'] = {'return_pct': round(ret5, 2), 'regime': regime, 'status': 'OK'}
            model_returns['regime'] = ret5
        except Exception as e:
            models['regime'] = {'error': str(e)}

        # ---- Ensemble ----
        if not model_returns:
            return {
                'current_price': round(current_price, 2),
                'error': 'No models produced results',
                'models': models,
            }

        # Weighted average with redistribution if model missing
        total_weight = 0
        weighted_sum = 0
        for model_name, ret in model_returns.items():
            w = MODEL_WEIGHTS.get(model_name, 0)
            weighted_sum += ret * w
            total_weight += w

        expected_return = weighted_sum / total_weight
        target_12m = round(current_price * (1 + expected_return / 100), 2)

        # Confidence from model spread
        rets = list(model_returns.values())
        spread = max(rets) - min(rets)
        if spread < 5:
            confidence = 'HIGH'
        elif spread < 15:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'

        # Range
        range_low = round(current_price * (1 + min(rets) / 100), 2)
        range_high = round(current_price * (1 + max(rets) / 100), 2)

        # Signal
        if expected_return > 8:
            signal = 'OW'
        elif expected_return > 3:
            signal = 'N'
        else:
            signal = 'UW'

        return {
            'current_price': round(current_price, 2),
            'target_12m': target_12m,
            'expected_return_pct': round(expected_return, 2),
            'confidence': confidence,
            'range': [range_low, range_high],
            'signal': signal,
            'models_used': len(model_returns),
            'models': models,
        }

    # ---- Individual Equity Models ----

    def _model_eyg(self, forward_pe: Optional[float], equity_data: Dict, ticker: str) -> Optional[float]:
        """Model 1: Earnings Yield + Growth. Return = E/P + g_forward"""
        if forward_pe is None or forward_pe <= 0:
            return None

        earnings_yield = 100.0 / forward_pe  # E/P in %

        # Get EPS growth from earnings data
        eps_growth = 5.0  # default
        if equity_data and isinstance(equity_data, dict):
            earnings = equity_data.get('earnings', {})
            if isinstance(earnings, dict) and 'error' not in earnings:
                # Try to find growth estimate
                for ticker_data in earnings.values():
                    if isinstance(ticker_data, dict):
                        g = self._safe_float(ticker_data.get('eps_growth_pct'))
                        if g is not None:
                            eps_growth = g
                            break

        return earnings_yield + eps_growth

    def _model_fair_pe(
        self,
        real_rate: float,
        erp: float,
        forward_pe: Optional[float],
        current_price: float,
        valuations: Dict,
    ) -> Optional[float]:
        """Model 2: Fair Value PE from ERP. Fair PE = 1/(real_rate + ERP); Target = Fair PE x FwdEPS"""
        if forward_pe is None or forward_pe <= 0:
            return None

        fair_pe = 100.0 / (real_rate + erp)  # e.g., 1/(2+4) = 16.7x
        fair_pe = max(8, min(35, fair_pe))  # clamp to reasonable range

        # Forward EPS = price / forward PE
        fwd_eps = current_price / forward_pe
        target = fair_pe * fwd_eps
        ret = ((target / current_price) - 1) * 100
        return ret

    def _model_pe_reversion(self, ticker: str, trailing_pe: Optional[float]) -> Optional[float]:
        """Model 3: PE mean-reversion. If PE above 5Y avg, expect compression."""
        if trailing_pe is None or trailing_pe <= 0:
            return None

        # Get 5Y average PE from yfinance history
        try:
            import yfinance as yf
            etf = yf.Ticker(ticker)
            hist = etf.history(period='5y')
            if hist.empty or len(hist) < 250:
                return None

            # Use price/earnings proxy: current PE vs average
            # Simple: percentile of current PE in 5Y range
            avg_return_5y = ((float(hist['Close'].iloc[-1]) / float(hist['Close'].iloc[0])) ** (1/5) - 1) * 100

            # Mean-reversion: if PE is high, expect below-average returns
            # Rough calibration: 20x avg PE as neutral
            pe_avg = 20.0  # market long-term average
            pe_ratio = trailing_pe / pe_avg
            # If PE = 25 (125% of avg), reduce expected return by ~25%
            adjustment = (1 - pe_ratio) * avg_return_5y
            expected = avg_return_5y + adjustment
            return max(-20, min(30, expected))

        except Exception:
            return None

    def _model_consensus(self, etf_ticker: str, current_price: float) -> Optional[float]:
        """Model 4: Analyst consensus from AlphaVantage for top holdings."""
        holdings = TOP_HOLDINGS.get(etf_ticker, [])
        if not holdings:
            return None

        try:
            from greybark.config import config
            if not config.alphavantage.api_key:
                return None

            import requests
            targets = []
            returns = []

            for stock in holdings[:4]:  # Limit API calls
                try:
                    url = (f"https://www.alphavantage.co/query"
                           f"?function=OVERVIEW&symbol={stock}"
                           f"&apikey={config.alphavantage.api_key}")
                    resp = requests.get(url, timeout=10)
                    data = resp.json()
                    target = self._safe_float(data.get('AnalystTargetPrice'))
                    price = self._safe_float(data.get('50DayMovingAverage'))
                    if target and price and price > 0:
                        ret = ((target / price) - 1) * 100
                        returns.append(ret)
                except Exception:
                    continue

            if not returns:
                return None

            # Average of analyst implied returns for top holdings
            return sum(returns) / len(returns)

        except Exception:
            return None

    def _get_etf_price(self, ticker: str) -> Optional[float]:
        """Get current ETF price from yfinance."""
        try:
            import yfinance as yf
            etf = yf.Ticker(ticker)
            hist = etf.history(period='5d')
            if hist.empty:
                return None
            return float(hist['Close'].iloc[-1])
        except Exception:
            return None

    # =====================================================================
    # ECONOMETRIC BLENDING
    # =====================================================================
    #
    # Blend survey/market forecasts (Layer 1) with econometric models (Layer 2).
    # Weights: Survey 40% + ARIMA 20% + VAR 20% + Structural 20%
    # If a model is missing, its weight redistributes to others.

    def _weighted_blend(self, values_weights: List[Tuple[float, float]]) -> Optional[float]:
        """Weighted average with automatic redistribution of missing weights."""
        items = [(v, w) for v, w in values_weights if v is not None]
        if not items:
            return None
        total_w = sum(w for _, w in items)
        if total_w <= 0:
            return None
        return round(sum(v * w for v, w in items) / total_w, 2)

    def _blend_inflation(self, base_forecasts: Dict) -> Dict:
        """Blend inflation forecasts with econometric models."""
        econ = self._econ
        arima = econ.get('arima', {})
        var_data = econ.get('var')
        phillips = econ.get('phillips')

        # USA inflation
        usa = base_forecasts.get('usa', {})
        if isinstance(usa, dict) and 'error' not in usa:
            survey_fc = self._safe_float(usa.get('forecast_12m'))
            arima_fc = self._safe_float((arima.get('inflation_usa') or {}).get('point_forecast'))
            var_fc = self._safe_float(
                (var_data or {}).get('forecasts', {}).get('cpi_yoy', {}).get('point_forecast')
            )
            phillips_fc = self._safe_float((phillips or {}).get('forecast_inflation'))

            blended = self._weighted_blend([
                (survey_fc, 0.40),
                (arima_fc, 0.20),
                (var_fc, 0.20),
                (phillips_fc, 0.20),
            ])
            if blended is not None:
                usa['forecast_12m_survey'] = survey_fc
                usa['forecast_12m'] = blended
                usa['econometric'] = {
                    'arima': arima_fc,
                    'var': var_fc,
                    'phillips': phillips_fc,
                }
                # Update range
                all_vals = [v for v in [survey_fc, arima_fc, var_fc, phillips_fc] if v is not None]
                if all_vals:
                    usa['range'] = [round(min(all_vals) - 0.3, 1), round(max(all_vals) + 0.3, 1)]
            base_forecasts['usa'] = usa

        # Chile inflation
        chile = base_forecasts.get('chile', {})
        if isinstance(chile, dict) and 'error' not in chile:
            survey_fc = self._safe_float(chile.get('forecast_12m'))
            arima_fc = self._safe_float((arima.get('inflation_chile') or {}).get('point_forecast'))

            blended = self._weighted_blend([
                (survey_fc, 0.60),   # EEE + breakeven get more weight (no VAR/Phillips for Chile)
                (arima_fc, 0.40),
            ])
            if blended is not None:
                chile['forecast_12m_survey'] = survey_fc
                chile['forecast_12m'] = blended
                chile['econometric'] = {'arima': arima_fc}
            base_forecasts['chile'] = chile

        return base_forecasts

    def _blend_rates(self, base_forecasts: Dict) -> Dict:
        """Blend rate forecasts with econometric models."""
        econ = self._econ
        arima = econ.get('arima', {})
        var_data = econ.get('var')
        taylor = econ.get('taylor', {})

        # Fed Funds
        fed = base_forecasts.get('fed_funds', {})
        if isinstance(fed, dict) and 'error' not in fed:
            survey_fc = self._safe_float(fed.get('forecast_12m'))
            arima_fc = self._safe_float((arima.get('fed_funds') or {}).get('point_forecast'))
            var_fc = self._safe_float(
                (var_data or {}).get('forecasts', {}).get('fed_funds', {}).get('point_forecast')
            )
            taylor_fc = self._safe_float((taylor.get('fed') or {}).get('forecast_12m'))

            blended = self._weighted_blend([
                (survey_fc, 0.40),
                (arima_fc, 0.20),
                (var_fc, 0.20),
                (taylor_fc, 0.20),
            ])
            if blended is not None:
                # Round to nearest 25bp
                blended = round(blended * 4) / 4
                fed['forecast_12m_market'] = survey_fc
                fed['forecast_12m'] = blended
                fed['econometric'] = {
                    'arima': arima_fc,
                    'var': var_fc,
                    'taylor': taylor_fc,
                }
            base_forecasts['fed_funds'] = fed

        # TPM Chile
        tpm = base_forecasts.get('tpm_chile', {})
        if isinstance(tpm, dict) and 'error' not in tpm:
            survey_fc = self._safe_float(tpm.get('forecast_12m'))
            taylor_fc = self._safe_float((taylor.get('tpm') or {}).get('forecast_12m'))

            blended = self._weighted_blend([
                (survey_fc, 0.60),   # SPC forwards more reliable for Chile
                (taylor_fc, 0.40),
            ])
            if blended is not None:
                blended = round(blended * 4) / 4
                tpm['forecast_12m_market'] = survey_fc
                tpm['forecast_12m'] = blended
                tpm['econometric'] = {'taylor': taylor_fc}
            base_forecasts['tpm_chile'] = tpm

        # ECB
        ecb = base_forecasts.get('ecb', {})
        if isinstance(ecb, dict) and 'error' not in ecb:
            survey_fc = self._safe_float(ecb.get('forecast_12m'))
            taylor_fc = self._safe_float((taylor.get('ecb') or {}).get('forecast_12m'))

            blended = self._weighted_blend([
                (survey_fc, 0.60),
                (taylor_fc, 0.40),
            ])
            if blended is not None:
                blended = round(blended * 4) / 4
                ecb['forecast_12m_market'] = survey_fc
                ecb['forecast_12m'] = blended
                ecb['econometric'] = {'taylor': taylor_fc}
            base_forecasts['ecb'] = ecb

        return base_forecasts

    def _blend_gdp(self, base_forecasts: Dict) -> Dict:
        """Blend GDP forecasts with econometric models."""
        econ = self._econ
        arima = econ.get('arima', {})
        var_data = econ.get('var')

        # USA GDP
        usa = base_forecasts.get('usa', {})
        if isinstance(usa, dict) and 'error' not in usa:
            survey_fc = self._safe_float(usa.get('forecast_12m'))
            arima_fc = self._safe_float((arima.get('gdp_usa') or {}).get('point_forecast'))
            var_fc = self._safe_float(
                (var_data or {}).get('forecasts', {}).get('gdp_growth', {}).get('point_forecast')
            )

            blended = self._weighted_blend([
                (survey_fc, 0.50),   # GDPNow/LEI/YC survey gets more weight
                (arima_fc, 0.25),
                (var_fc, 0.25),
            ])
            if blended is not None:
                usa['forecast_12m_survey'] = survey_fc
                usa['forecast_12m'] = blended
                usa['econometric'] = {
                    'arima': arima_fc,
                    'var': var_fc,
                }
            base_forecasts['usa'] = usa

        # Other regions: no econometric models, keep survey-only
        return base_forecasts

    # =====================================================================
    # SAVE
    # =====================================================================

    def save(self, forecasts: Dict, filepath: str = None) -> str:
        """Guarda forecasts en JSON."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            filepath = str(OUTPUT_DIR / f"forecast_{timestamp}.json")

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(forecasts, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[ForecastEngine] Guardado en: {filepath}")
        return filepath


# =========================================================================
# CLI / STANDALONE
# =========================================================================

def main():
    """Ejecución standalone del Forecast Engine."""
    print("=" * 60)
    print("GREYBARK RESEARCH - FORECAST ENGINE")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    engine = ForecastEngine(verbose=True)

    # Try loading existing data if available
    equity_data = {}
    rf_data = {}
    quant_data = {}

    eq_dir = Path(__file__).parent / "output" / "equity_data"
    rf_dir = Path(__file__).parent / "output" / "rf_data"

    # Load most recent equity data
    try:
        eq_files = sorted(eq_dir.glob("equity_data_*.json"), reverse=True)
        if eq_files:
            with open(eq_files[0], 'r', encoding='utf-8') as f:
                equity_data = json.load(f)
            print(f"\nEquity data: {eq_files[0].name}")
    except Exception as e:
        print(f"No equity data: {e}")

    # Load most recent RF data
    try:
        rf_files = sorted(rf_dir.glob("rf_data_*.json"), reverse=True)
        if rf_files:
            with open(rf_files[0], 'r', encoding='utf-8') as f:
                rf_data = json.load(f)
            print(f"RF data: {rf_files[0].name}")
    except Exception as e:
        print(f"No RF data: {e}")

    # Collect fresh quant data for regime etc.
    try:
        from council_data_collector import CouncilDataCollector
        collector = CouncilDataCollector(verbose=False)
        quant_data = collector.collect_quantitative_data()
        print(f"Quant data: {sum(1 for v in quant_data.values() if isinstance(v, dict) and 'error' not in v)} modules OK")
    except Exception as e:
        print(f"No quant data: {e}")

    # Generate
    forecasts = engine.generate_all(equity_data, rf_data, quant_data)

    # Save
    path = engine.save(forecasts)

    # Print summary
    print("\n" + "=" * 60)
    print("RESUMEN DE PRONÓSTICOS")
    print("=" * 60)

    # Inflation
    infl = forecasts.get('inflation_forecasts', {})
    if isinstance(infl, dict) and 'error' not in infl:
        print("\nInflación (12M forecast):")
        for region, data in infl.items():
            if isinstance(data, dict) and 'error' not in data:
                curr = data.get('current', '?')
                fc = data.get('forecast_12m', '?')
                trend = data.get('trend', '?')
                print(f"  {region:>10}: {curr}% -> {fc}% ({trend})")

    # GDP
    gdp = forecasts.get('gdp_forecasts', {})
    if isinstance(gdp, dict) and 'error' not in gdp:
        print("\nGDP (12M forecast):")
        for region, data in gdp.items():
            if isinstance(data, dict) and 'error' not in data:
                curr = data.get('current', '?')
                fc = data.get('forecast_12m', '?')
                print(f"  {region:>10}: {curr}% -> {fc}%")

    # Rates
    rates = forecasts.get('rate_forecasts', {})
    if isinstance(rates, dict) and 'error' not in rates:
        print("\nTasas (12M forecast):")
        for rate, data in rates.items():
            if isinstance(data, dict) and 'error' not in data:
                curr = data.get('current', '?')
                fc = data.get('forecast_12m', '?')
                direction = data.get('direction', '?')
                print(f"  {rate:>12}: {curr}% -> {fc}% ({direction})")

    # Equity
    eq = forecasts.get('equity_targets', {})
    if isinstance(eq, dict) and 'error' not in eq:
        print("\nEquity Targets (12M):")
        for idx, data in eq.items():
            if isinstance(data, dict) and 'error' not in data:
                curr = data.get('current_price', '?')
                tgt = data.get('target_12m', '?')
                ret = data.get('expected_return_pct', 0)
                sig = data.get('signal', '?')
                conf = data.get('confidence', '?')
                print(f"  {idx:>10}: ${curr} -> ${tgt} ({ret:+.1f}%) [{sig}] conf={conf}")

    print(f"\nGuardado en: {path}")


if __name__ == "__main__":
    main()

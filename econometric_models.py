# -*- coding: utf-8 -*-
"""
Greybark Research - Econometric Models
========================================

Modelos econométricos para el Forecast Engine:
1. ARIMAForecaster: Auto-ARIMA por serie individual (momentum + estacionalidad)
2. VARForecaster: VAR multivariado (interdependencias macro)
3. TaylorRule: Modelo estructural de tasas de interés
4. PhillipsCurve: Link inflación ↔ desempleo

Todos retornan: point_forecast, confidence_interval_68, confidence_interval_95

Dependencias: statsmodels, pmdarima, pandas, numpy
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd

# Windows encoding fix
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

# Suppress convergence warnings during model fitting
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', module='statsmodels')
warnings.filterwarnings('ignore', module='pmdarima')

# Paths
sys.path.insert(0, str(Path(__file__).parent))
LIB_PATH = Path(__file__).parent.parent / "02_greybark_library"
sys.path.insert(0, str(LIB_PATH))

# Econometric models need 20+ years of data (not FRED default 5Y)
_ECON_START = date(2003, 1, 1)
_BCCH_DAYS_LONG = 8400  # ~23 years


# =========================================================================
# 1. ARIMA FORECASTER
# =========================================================================

class ARIMAForecaster:
    """
    Auto-ARIMA por serie individual.
    Captura momentum, tendencia y estacionalidad.
    Usa pmdarima.auto_arima para selección automática de (p,d,q)(P,D,Q,m).
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._fred = None
        self._bcch = None

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

    def _fred_long(self, series_id: str) -> Optional[pd.Series]:
        """Fetch FRED series with 20+ year lookback."""
        return self._get_fred().get_series(series_id, start_date=_ECON_START)

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [ARIMA] {msg}")

    def forecast_series(
        self,
        series: pd.Series,
        steps: int = 12,
        seasonal: bool = True,
        m: int = 12,
    ) -> Optional[Dict[str, Any]]:
        """
        Ajusta auto_arima a una serie y genera forecast.

        Args:
            series: pd.Series con DatetimeIndex
            steps: Períodos a pronosticar
            seasonal: Si usar componente estacional
            m: Frecuencia estacional (12=mensual, 4=trimestral)

        Returns:
            Dict con forecast, ci_68, ci_95, model_info
        """
        if series is None or len(series) < 24:
            return None

        try:
            import pmdarima as pm

            # Clean series
            s = series.dropna().astype(float)
            if len(s) < 24:
                return None

            # Auto-ARIMA with robust settings
            model = pm.auto_arima(
                s,
                seasonal=seasonal,
                m=m if seasonal else 1,
                stepwise=True,
                suppress_warnings=True,
                error_action='ignore',
                max_p=4, max_q=4,
                max_P=2, max_Q=2,
                max_d=2, max_D=1,
                trace=False,
                n_fits=50,
                information_criterion='aic',
                with_intercept=True,
            )

            # Verify model was actually fit
            if model is None or model.order is None:
                self._log("auto_arima returned invalid model")
                return None

            # Forecast
            fc, conf_int_95 = model.predict(n_periods=steps, return_conf_int=True, alpha=0.05)
            _, conf_int_68 = model.predict(n_periods=steps, return_conf_int=True, alpha=0.32)

            # Last value
            last_val = float(s.iloc[-1])

            # Point forecast at horizon
            point = float(fc[-1]) if len(fc) > 0 else last_val

            # Confidence intervals at horizon
            ci_68 = [float(conf_int_68[-1, 0]), float(conf_int_68[-1, 1])] if len(conf_int_68) > 0 else [point - 0.5, point + 0.5]
            ci_95 = [float(conf_int_95[-1, 0]), float(conf_int_95[-1, 1])] if len(conf_int_95) > 0 else [point - 1.0, point + 1.0]

            # Full path for fan chart
            path = [float(x) for x in fc]
            ci_95_path = [[float(r[0]), float(r[1])] for r in conf_int_95]

            # Model info
            order = model.order
            seasonal_order = model.seasonal_order if seasonal else None
            aic = float(model.aic()) if hasattr(model, 'aic') else None

            return {
                'point_forecast': round(point, 4),
                'ci_68': [round(ci_68[0], 4), round(ci_68[1], 4)],
                'ci_95': [round(ci_95[0], 4), round(ci_95[1], 4)],
                'path': [round(x, 4) for x in path],
                'ci_95_path': ci_95_path,
                'last_actual': round(last_val, 4),
                'model_order': f"ARIMA{order}",
                'seasonal_order': str(seasonal_order) if seasonal_order else None,
                'aic': round(aic, 1) if aic else None,
                'n_obs': len(s),
            }

        except Exception as e:
            self._log(f"ARIMA failed: {e}")
            return None

    def forecast_inflation_usa(self, steps: int = 12) -> Optional[Dict]:
        """ARIMA forecast of US CPI YoY."""
        try:
            cpi = self._fred_long('CPIAUCSL')
            if cpi is None or len(cpi) < 60:
                return None

            # Compute YoY
            cpi_yoy = cpi.pct_change(12) * 100
            cpi_yoy = cpi_yoy.dropna()

            self._log(f"CPI YoY: {len(cpi_yoy)} obs, last={cpi_yoy.iloc[-1]:.2f}%")
            result = self.forecast_series(cpi_yoy, steps=steps, seasonal=True, m=12)
            if result:
                self._log(f"CPI forecast: {result['last_actual']:.2f}% -> {result['point_forecast']:.2f}%")
            return result
        except Exception as e:
            self._log(f"Inflation USA ARIMA failed: {e}")
            return None

    def forecast_inflation_chile(self, steps: int = 12) -> Optional[Dict]:
        """ARIMA forecast of Chile IPC YoY."""
        try:
            bcch = self._get_bcch()

            # Chile CPI monthly variation → compute YoY via rolling product
            ipc_var = bcch.get_series('F074.IPC.VAR.Z.Z.C.M', days_back=_BCCH_DAYS_LONG)
            if ipc_var is None or len(ipc_var) < 24:
                return None
            # Monthly var is %MoM. Convert: (1+v1/100)*(1+v2/100)*...*(1+v12/100) - 1
            ipc_factor = (1 + ipc_var.astype(float) / 100)
            ipc_yoy = (ipc_factor.rolling(12).apply(lambda x: x.prod(), raw=True) - 1) * 100
            ipc_yoy = ipc_yoy.dropna()

            if len(ipc_yoy) < 36:
                return None

            self._log(f"Chile IPC YoY: {len(ipc_yoy)} obs, last={ipc_yoy.iloc[-1]:.2f}%")
            result = self.forecast_series(ipc_yoy, steps=steps, seasonal=True, m=12)
            if result:
                self._log(f"Chile IPC forecast: {result['last_actual']:.2f}% -> {result['point_forecast']:.2f}%")
            return result
        except Exception as e:
            self._log(f"Inflation Chile ARIMA failed: {e}")
            return None

    def forecast_gdp_usa(self, steps: int = 4) -> Optional[Dict]:
        """ARIMA forecast of US GDP QoQ annualized."""
        try:
            gdp = self._fred_long('GDPC1')
            if gdp is None or len(gdp) < 40:
                return None

            # Compute QoQ annualized
            gdp_qoq = gdp.pct_change() * 400  # QoQ annualized
            gdp_qoq = gdp_qoq.dropna()

            self._log(f"GDP QoQ: {len(gdp_qoq)} obs, last={gdp_qoq.iloc[-1]:.2f}%")
            result = self.forecast_series(gdp_qoq, steps=steps, seasonal=True, m=4)
            if result:
                self._log(f"GDP forecast: {result['last_actual']:.2f}% -> {result['point_forecast']:.2f}%")
            return result
        except Exception as e:
            self._log(f"GDP USA ARIMA failed: {e}")
            return None

    def forecast_unemployment(self, steps: int = 12) -> Optional[Dict]:
        """ARIMA forecast of US unemployment rate."""
        try:
            unemp = self._fred_long('UNRATE')
            if unemp is None or len(unemp) < 60:
                return None

            unemp = unemp.dropna().astype(float)
            self._log(f"Unemployment: {len(unemp)} obs, last={unemp.iloc[-1]:.1f}%")

            # Try auto_arima first (seasonal then non-seasonal)
            result = self.forecast_series(unemp, steps=steps, seasonal=True, m=12)
            if result is None:
                self._log("Retrying without seasonality...")
                result = self.forecast_series(unemp, steps=steps, seasonal=False, m=1)

            # Fallback: manual ARIMA(1,1,0) if auto_arima fails
            if result is None:
                self._log("Auto-ARIMA failed, using manual ARIMA(1,1,0)...")
                try:
                    from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
                    model = StatsARIMA(unemp, order=(1, 1, 0)).fit()
                    fc = model.forecast(steps=steps)
                    last_val = float(unemp.iloc[-1])
                    point = float(fc.iloc[-1])
                    resid_std = float(model.resid.std())
                    h_factor = np.sqrt(steps)
                    result = {
                        'point_forecast': round(point, 4),
                        'ci_68': [round(point - resid_std * h_factor, 4),
                                  round(point + resid_std * h_factor, 4)],
                        'ci_95': [round(point - 1.96 * resid_std * h_factor, 4),
                                  round(point + 1.96 * resid_std * h_factor, 4)],
                        'path': [round(float(x), 4) for x in fc],
                        'last_actual': round(last_val, 4),
                        'model_order': 'ARIMA(1,1,0)',
                        'seasonal_order': None,
                        'aic': round(float(model.aic), 1),
                        'n_obs': len(unemp),
                    }
                except Exception as e2:
                    self._log(f"Manual ARIMA also failed: {e2}")

            if result:
                self._log(f"Unemp forecast: {result['last_actual']:.1f}% -> {result['point_forecast']:.1f}%")
            return result
        except Exception as e:
            self._log(f"Unemployment ARIMA failed: {e}")
            return None

    def forecast_fed_funds(self, steps: int = 12) -> Optional[Dict]:
        """ARIMA forecast of Fed Funds rate."""
        try:
            ff = self._fred_long('DFF')
            if ff is None or len(ff) < 120:
                return None

            # Resample to monthly (average)
            ff_m = ff.resample('M').mean().dropna().astype(float)
            if len(ff_m) < 60:
                return None

            self._log(f"Fed Funds monthly: {len(ff_m)} obs, last={ff_m.iloc[-1]:.2f}%")
            result = self.forecast_series(ff_m, steps=steps, seasonal=False, m=1)
            if result:
                self._log(f"Fed forecast: {result['last_actual']:.2f}% -> {result['point_forecast']:.2f}%")
            return result
        except Exception as e:
            self._log(f"Fed Funds ARIMA failed: {e}")
            return None


# =========================================================================
# 2. VAR FORECASTER
# =========================================================================

class VARForecaster:
    """
    Vector Autoregression (VAR) multivariado.
    Captura interdependencias: GDP ↔ Inflación ↔ Tasas ↔ Desempleo.
    Estándar de bancos centrales (modelo reducido).
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._fred = None

    def _get_fred(self):
        if self._fred is None:
            from greybark.data_sources.fred_client import FREDClient
            self._fred = FREDClient()
        return self._fred

    def _fred_long(self, series_id: str) -> Optional[pd.Series]:
        """Fetch FRED series with 20+ year lookback."""
        return self._get_fred().get_series(series_id, start_date=_ECON_START)

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [VAR] {msg}")

    def forecast_usa_macro(self, steps: int = 4) -> Optional[Dict[str, Any]]:
        """
        VAR(p) sobre sistema de 4 variables USA:
        [GDP_growth, CPI_YoY, Fed_Funds, Unemployment]

        Usa datos trimestrales para coherencia con GDP.

        Returns:
            Dict con forecasts por variable + impulse responses
        """
        try:
            from statsmodels.tsa.api import VAR as StatsVAR

            # Fetch with 20+ year lookback for robust estimation
            gdp = self._fred_long('GDPC1')
            cpi = self._fred_long('CPIAUCSL')
            ff = self._fred_long('DFF')
            unemp = self._fred_long('UNRATE')

            if any(s is None for s in [gdp, cpi, ff, unemp]):
                self._log("Missing series for VAR")
                return None

            # Transform to quarterly — align all to same QE period index
            # GDP is already quarterly but may have start-of-quarter dates
            # Resample all to QE to ensure aligned indices
            gdp_q = gdp.resample('QE').last()
            gdp_g = gdp_q.pct_change() * 400  # QoQ annualized
            cpi_q = cpi.resample('QE').last()
            cpi_yoy = cpi_q.pct_change(4) * 100  # YoY
            ff_q = ff.resample('QE').mean()
            unemp_q = unemp.resample('QE').last()

            # Build DataFrame — all now share QE index
            df = pd.DataFrame({
                'gdp_growth': gdp_g,
                'cpi_yoy': cpi_yoy,
                'fed_funds': ff_q,
                'unemployment': unemp_q,
            }).dropna()

            if len(df) < 40:
                self._log(f"Insufficient data for VAR: {len(df)} obs")
                return None

            self._log(f"VAR data: {len(df)} quarters, {df.columns.tolist()}")

            # Fit VAR with automatic lag selection (max 8 quarters)
            model = StatsVAR(df)

            # Select optimal lag via AIC
            max_lags = min(8, len(df) // 5)
            try:
                lag_result = model.select_order(maxlags=max_lags)
                optimal_lag = lag_result.aic
                if optimal_lag < 1:
                    optimal_lag = 2
            except Exception:
                optimal_lag = 2

            self._log(f"Optimal lag: {optimal_lag}")

            # Fit
            results = model.fit(optimal_lag)

            # Forecast
            fc = results.forecast(df.values[-optimal_lag:], steps=steps)

            # Forecast error variance decomposition for confidence intervals
            # Use residual std as proxy for CI
            residuals = results.resid
            std_residuals = residuals.std()

            # Build output
            forecasts = {}
            var_names = ['gdp_growth', 'cpi_yoy', 'fed_funds', 'unemployment']

            for i, var in enumerate(var_names):
                path = [float(fc[t, i]) for t in range(steps)]
                point = path[-1]
                std = float(std_residuals.iloc[i])

                # CI from residual std, growing with sqrt(horizon)
                horizon_factor = np.sqrt(steps)
                ci_68 = [round(point - std * horizon_factor, 4),
                         round(point + std * horizon_factor, 4)]
                ci_95 = [round(point - 1.96 * std * horizon_factor, 4),
                         round(point + 1.96 * std * horizon_factor, 4)]

                forecasts[var] = {
                    'point_forecast': round(point, 4),
                    'ci_68': ci_68,
                    'ci_95': ci_95,
                    'path': [round(x, 4) for x in path],
                    'last_actual': round(float(df[var].iloc[-1]), 4),
                    'residual_std': round(std, 4),
                }

            # Granger causality summary (which variables predict which)
            granger = {}
            for var in var_names:
                try:
                    gc = results.test_causality(var, causing=[v for v in var_names if v != var],
                                                 kind='f')
                    granger[var] = {
                        'f_stat': round(float(gc.test_statistic), 2),
                        'p_value': round(float(gc.pvalue), 4),
                        'significant': gc.pvalue < 0.05,
                    }
                except Exception:
                    pass

            self._log(f"VAR forecast complete: {steps} steps ahead")
            for var in var_names:
                fc_val = forecasts[var]['point_forecast']
                last = forecasts[var]['last_actual']
                self._log(f"  {var}: {last:.2f} -> {fc_val:.2f}")

            return {
                'forecasts': forecasts,
                'model_info': {
                    'type': 'VAR',
                    'lag_order': optimal_lag,
                    'n_obs': len(df),
                    'variables': var_names,
                    'aic': round(float(results.aic), 1),
                    'bic': round(float(results.bic), 1),
                },
                'granger_causality': granger,
            }

        except Exception as e:
            self._log(f"VAR forecast failed: {e}")
            return None


# =========================================================================
# 3. TAYLOR RULE
# =========================================================================

class TaylorRule:
    """
    Modelo Taylor Rule para tasas de política monetaria.

    r = r* + π + 0.5(π - π*) + 0.5(y - y*)

    Donde:
    - r*: Tasa real neutral (estimada)
    - π: Inflación actual
    - π*: Meta de inflación
    - y - y*: Output gap (diferencia vs potencial)

    Variantes:
    - Original Taylor (1993): coefs 0.5/0.5
    - Modified Taylor: coefs calibrados por región
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._fred = None
        self._bcch = None

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

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [Taylor] {msg}")

    def _fetch_nairu(self, default: float = 4.2) -> float:
        """Fetch CBO NAIRU from FRED (NROU quarterly). Fallback to default."""
        try:
            fred = self._get_fred()
            s = fred.get_series('NROU', start_date=date(2020, 1, 1))
            if s is not None and len(s) > 0:
                val = float(s.dropna().iloc[-1])
                if 2.0 <= val <= 8.0:
                    self._log(f"CBO NAIRU from FRED: {val:.1f}%")
                    return round(val, 2)
        except Exception as e:
            self._log(f"NAIRU fetch failed: {e}")
        return default

    def fed_rate(
        self,
        inflation: float = None,
        unemployment: float = None,
        inflation_target: float = 2.0,
        r_star: float = 0.5,
        nairu: float = None,
        okun_coef: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Taylor Rule para Fed Funds.

        Output gap proxy: Okun's Law — gap ≈ -okun * (u - u*)

        Args:
            inflation: Core PCE YoY (%)
            unemployment: Current unemployment rate (%)
            inflation_target: Fed target (2%)
            r_star: Real neutral rate estimate (0.5%)
            nairu: Natural rate of unemployment (None = fetch from FRED NROU)
            okun_coef: Okun coefficient (2.0)
        """
        if nairu is None:
            nairu = self._fetch_nairu(default=4.2)
        fred = self._get_fred()

        # Fetch current values if not provided
        if inflation is None:
            try:
                pce = fred.get_series('PCEPILFE', start_date=date(2023, 1, 1))  # Core PCE, 2Y enough
                if pce is not None and len(pce) >= 13:
                    inflation = (float(pce.iloc[-1]) / float(pce.iloc[-13]) - 1) * 100
            except Exception:
                pass

        if unemployment is None:
            try:
                unemployment = float(fred.get_latest_value('UNRATE'))
            except Exception:
                pass

        if inflation is None or unemployment is None:
            self._log("Missing data for Taylor Rule")
            return {'error': 'Missing inflation or unemployment data'}

        # Output gap via Okun's Law
        output_gap = -okun_coef * (unemployment - nairu)

        # Taylor Rule
        # Original: r = r* + π + 0.5*(π - π*) + 0.5*(y - y*)
        taylor_rate = r_star + inflation + 0.5 * (inflation - inflation_target) + 0.5 * output_gap

        # Inertia-adjusted (partial adjustment): Fed doesn't jump to Taylor rate
        # r_actual = 0.85 * r_prev + 0.15 * r_taylor
        current_ff = None
        try:
            current_ff = float(fred.get_latest_value('DFF'))
        except Exception:
            pass

        if current_ff is not None:
            inertia_rate = 0.85 * current_ff + 0.15 * taylor_rate
        else:
            inertia_rate = taylor_rate

        # Rate in 12M: assume 40% convergence to Taylor from inertia
        forecast_12m = inertia_rate + 0.40 * (taylor_rate - inertia_rate)

        # Round to nearest 25bp
        forecast_12m_rounded = round(forecast_12m * 4) / 4

        self._log(f"Inflation={inflation:.2f}%, Unemployment={unemployment:.1f}%")
        self._log(f"Output gap={output_gap:.2f}%, r*={r_star:.1f}%")
        self._log(f"Pure Taylor={taylor_rate:.2f}%, Inertia={inertia_rate:.2f}%")
        self._log(f"12M forecast={forecast_12m_rounded:.2f}%")

        return {
            'taylor_rate': round(taylor_rate, 4),
            'inertia_rate': round(inertia_rate, 4),
            'forecast_12m': round(forecast_12m_rounded, 2),
            'current_rate': current_ff,
            'inputs': {
                'inflation': round(inflation, 2),
                'unemployment': round(unemployment, 1),
                'output_gap': round(output_gap, 2),
                'r_star': r_star,
                'nairu': nairu,
                'inflation_target': inflation_target,
            },
            'gap_vs_actual': round(taylor_rate - current_ff, 2) if current_ff else None,
            'model': 'Taylor Rule (inertia-adjusted)',
        }

    def tpm_chile(
        self,
        inflation: float = None,
        imacec: float = None,
        inflation_target: float = 3.0,
        r_star: float = 1.0,
        potential_growth: float = 2.5,
    ) -> Dict[str, Any]:
        """
        Taylor Rule para TPM Chile.
        Usa IMACEC YoY como proxy de output gap.
        """
        bcch = self._get_bcch()

        if inflation is None:
            try:
                # Chile CPI monthly variation → compute YoY via rolling product
                ipc_var = bcch.get_series('F074.IPC.VAR.Z.Z.C.M', days_back=500)
                if ipc_var is not None and len(ipc_var) >= 12:
                    factors = (1 + ipc_var.astype(float) / 100)
                    yoy = (factors.rolling(12).apply(lambda x: x.prod(), raw=True) - 1) * 100
                    yoy = yoy.dropna()
                    if len(yoy) > 0:
                        inflation = float(yoy.iloc[-1])
                        self._log(f"Chile CPI YoY from monthly: {inflation:.2f}% ({len(ipc_var)} obs)")
            except Exception as e:
                self._log(f"Chile CPI fetch failed: {e}")
            # Fallback: EEE 12M expectation
            if inflation is None:
                try:
                    val = bcch.get_latest('F089.IPC.V12.Z.M')
                    if val is not None:
                        inflation = float(val)
                        self._log(f"Chile inflation from EEE: {inflation:.2f}%")
                except Exception:
                    pass

        if imacec is None:
            try:
                val = bcch.get_latest('F032.IMC.V12.Z.Z.2018.Z.Z.0.M')
                if val is not None:
                    imacec = float(val)
            except Exception:
                pass

        if inflation is None:
            return {'error': 'Missing Chile inflation data'}

        # Output gap from IMACEC
        output_gap = (imacec - potential_growth) if imacec else 0.0

        # Taylor Rule for BCCh
        taylor_rate = r_star + inflation + 0.5 * (inflation - inflation_target) + 0.5 * output_gap

        # Current TPM
        current_tpm = None
        try:
            val = bcch.get_latest('F022.TPM.TIN.D001.NO.Z.D')
            if val is not None:
                current_tpm = float(val)
        except Exception:
            pass

        if current_tpm is not None:
            inertia_rate = 0.80 * current_tpm + 0.20 * taylor_rate
        else:
            inertia_rate = taylor_rate

        forecast_12m = inertia_rate + 0.40 * (taylor_rate - inertia_rate)
        forecast_12m_rounded = round(forecast_12m * 4) / 4

        self._log(f"Chile: Inflation={inflation:.1f}%, IMACEC={imacec or 'N/A'}%")
        self._log(f"TPM Taylor={taylor_rate:.2f}%, forecast 12M={forecast_12m_rounded:.2f}%")

        return {
            'taylor_rate': round(taylor_rate, 4),
            'inertia_rate': round(inertia_rate, 4),
            'forecast_12m': round(forecast_12m_rounded, 2),
            'current_rate': current_tpm,
            'inputs': {
                'inflation': round(inflation, 2),
                'imacec': round(imacec, 2) if imacec else None,
                'output_gap': round(output_gap, 2),
                'r_star': r_star,
                'potential_growth': potential_growth,
                'inflation_target': inflation_target,
            },
            'gap_vs_actual': round(taylor_rate - current_tpm, 2) if current_tpm else None,
            'model': 'Taylor Rule Chile (inertia-adjusted)',
        }

    def ecb_rate(
        self,
        inflation: float = None,
        unemployment: float = None,
        inflation_target: float = 2.0,
        r_star: float = 0.0,
        nairu: float = 6.5,
        okun_coef: float = 1.5,
    ) -> Dict[str, Any]:
        """Taylor Rule for ECB."""
        bcch = self._get_bcch()

        if inflation is None:
            try:
                val = bcch.get_latest('F019.IPC.V12.20.M')
                if val is not None:
                    inflation = float(val)
            except Exception:
                pass

        if unemployment is None:
            try:
                val = bcch.get_latest('F019.DES.TAS.20.M')
                if val is not None:
                    unemployment = float(val)
            except Exception:
                pass

        if inflation is None:
            return {'error': 'Missing Eurozone inflation data'}

        output_gap = -okun_coef * (unemployment - nairu) if unemployment else 0.0

        taylor_rate = r_star + inflation + 0.5 * (inflation - inflation_target) + 0.5 * output_gap

        # Current ECB rate
        current_ecb = None
        try:
            val = bcch.get_latest('F019.TPM.TIN.GE.D')
            if val is not None:
                current_ecb = float(val)
        except Exception:
            pass

        if current_ecb is not None:
            inertia_rate = 0.85 * current_ecb + 0.15 * taylor_rate
        else:
            inertia_rate = taylor_rate

        forecast_12m = inertia_rate + 0.40 * (taylor_rate - inertia_rate)
        forecast_12m_rounded = round(forecast_12m * 4) / 4

        self._log(f"ECB: Inflation={inflation:.1f}%, Unemployment={unemployment or 'N/A'}%")
        self._log(f"ECB Taylor={taylor_rate:.2f}%, forecast 12M={forecast_12m_rounded:.2f}%")

        return {
            'taylor_rate': round(taylor_rate, 4),
            'inertia_rate': round(inertia_rate, 4),
            'forecast_12m': round(forecast_12m_rounded, 2),
            'current_rate': current_ecb,
            'inputs': {
                'inflation': round(inflation, 2) if inflation else None,
                'unemployment': round(unemployment, 1) if unemployment else None,
                'output_gap': round(output_gap, 2),
                'r_star': r_star,
                'nairu': nairu,
                'inflation_target': inflation_target,
            },
            'gap_vs_actual': round(taylor_rate - current_ecb, 2) if current_ecb else None,
            'model': 'Taylor Rule ECB (inertia-adjusted)',
        }


# =========================================================================
# 4. PHILLIPS CURVE
# =========================================================================

class PhillipsCurve:
    """
    Phillips Curve: relación inflación ↔ desempleo.

    Modelo: π = π_e + β(u* - u) + ε
    - π_e: Expectativas de inflación (backward-looking o breakeven)
    - β: Pendiente de la curva (estimada por OLS)
    - u*: NAIRU
    - u: Desempleo actual

    Sirve para:
    1. Forecast de inflación dado un path de desempleo
    2. Estimar si la inflación está "justificada" por el mercado laboral
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._fred = None

    def _get_fred(self):
        if self._fred is None:
            from greybark.data_sources.fred_client import FREDClient
            self._fred = FREDClient()
        return self._fred

    def _fred_long(self, series_id: str) -> Optional[pd.Series]:
        """Fetch FRED series with 20+ year lookback."""
        return self._get_fred().get_series(series_id, start_date=_ECON_START)

    def _log(self, msg: str):
        if self.verbose:
            print(f"  [Phillips] {msg}")

    def estimate_and_forecast(
        self,
        unemployment_forecast: float = None,
        nairu: float = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Estima Phillips Curve con datos históricos y genera forecast.

        1. Descarga CPI Core YoY y Unemployment (10+ años)
        2. Estima β por OLS: Δπ = α + β(u - u*) + ε
        3. Proyecta inflación dado unemployment_forecast

        Args:
            unemployment_forecast: Unemployment rate esperado en 12M
            nairu: NAIRU (None = fetch from FRED NROU, fallback 4.2%)

        Returns:
            Dict con forecast, coefficient, R², etc.
        """
        if nairu is None:
            # Fetch CBO NAIRU from FRED
            try:
                fred = self._get_fred()
                nrou = fred.get_series('NROU', start_date=date(2020, 1, 1))
                if nrou is not None and len(nrou) > 0:
                    nairu = round(float(nrou.dropna().iloc[-1]), 2)
                    self._log(f"Phillips: CBO NAIRU from FRED: {nairu}%")
            except Exception:
                pass
            if nairu is None:
                nairu = 4.2

        try:
            from statsmodels.regression.linear_model import OLS
            import statsmodels.api as sm

            # Fetch 20+ years for robust estimation
            cpi = self._fred_long('CPILFESL')  # Core CPI
            unemp = self._fred_long('UNRATE')

            if cpi is None or unemp is None:
                return None

            # Compute Core CPI YoY
            cpi_yoy = cpi.pct_change(12) * 100
            cpi_yoy = cpi_yoy.dropna()

            # Align on common dates (monthly)
            df = pd.DataFrame({
                'inflation': cpi_yoy,
                'unemployment': unemp,
            }).dropna()

            if len(df) < 60:
                self._log(f"Insufficient data: {len(df)} obs")
                return None

            # Use last 20 years for estimation (post-2005)
            df = df.loc['2005-01-01':]
            if len(df) < 60:
                df = pd.DataFrame({
                    'inflation': cpi_yoy,
                    'unemployment': unemp,
                }).dropna().iloc[-240:]

            # Phillips Curve: π = α + β*(u - u*) + ε
            # Where u - u* is the unemployment gap
            df['unemp_gap'] = df['unemployment'] - nairu

            # Lag unemployment gap by 6 months (policy transmission)
            df['unemp_gap_lag6'] = df['unemp_gap'].shift(6)
            df = df.dropna()

            X = sm.add_constant(df['unemp_gap_lag6'])
            y = df['inflation']

            model = OLS(y, X).fit()

            beta = float(model.params.iloc[1])
            alpha = float(model.params.iloc[0])
            r_squared = float(model.rsquared)
            n_obs = len(df)

            self._log(f"Phillips: alpha={alpha:.3f}, beta={beta:.3f}, R2={r_squared:.3f}, n={n_obs}")

            # Current values
            current_inflation = float(df['inflation'].iloc[-1])
            current_unemp = float(df['unemployment'].iloc[-1])

            # Forecast
            if unemployment_forecast is None:
                # Use ARIMA forecast if available, otherwise assume stable
                unemployment_forecast = current_unemp

            future_gap = unemployment_forecast - nairu
            forecast_inflation = alpha + beta * future_gap

            # Residual-based confidence interval
            resid_std = float(model.resid.std())
            ci_68 = [round(forecast_inflation - resid_std, 2),
                     round(forecast_inflation + resid_std, 2)]
            ci_95 = [round(forecast_inflation - 1.96 * resid_std, 2),
                     round(forecast_inflation + 1.96 * resid_std, 2)]

            # Assessment: is current inflation "justified" by labor market?
            implied_current = alpha + beta * (current_unemp - nairu)
            residual = current_inflation - implied_current
            if abs(residual) < resid_std * 0.5:
                assessment = 'JUSTIFIED'
            elif residual > 0:
                assessment = 'ABOVE_CURVE'  # Inflation higher than Phillips implies
            else:
                assessment = 'BELOW_CURVE'

            self._log(f"Current: pi={current_inflation:.2f}%, u={current_unemp:.1f}%")
            self._log(f"Implied by Phillips: {implied_current:.2f}% (residual: {residual:+.2f}pp)")
            self._log(f"Forecast (u={unemployment_forecast:.1f}%): pi={forecast_inflation:.2f}%")

            return {
                'forecast_inflation': round(forecast_inflation, 2),
                'ci_68': ci_68,
                'ci_95': ci_95,
                'current_inflation': round(current_inflation, 2),
                'current_unemployment': round(current_unemp, 1),
                'unemployment_forecast': round(unemployment_forecast, 1),
                'implied_current': round(implied_current, 2),
                'residual': round(residual, 2),
                'assessment': assessment,
                'coefficients': {
                    'alpha': round(alpha, 4),
                    'beta': round(beta, 4),
                    'r_squared': round(r_squared, 4),
                    'residual_std': round(resid_std, 4),
                    'nairu': nairu,
                },
                'model_info': {
                    'type': 'Phillips Curve (augmented, 6M lag)',
                    'n_obs': n_obs,
                    'sample': f"{df.index[0].strftime('%Y-%m')} to {df.index[-1].strftime('%Y-%m')}",
                },
            }

        except Exception as e:
            self._log(f"Phillips Curve failed: {e}")
            return None


# =========================================================================
# COMBINED INTERFACE
# =========================================================================

class EconometricSuite:
    """
    Suite integrada de modelos econométricos.
    Interfaz única para el ForecastEngine.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.arima = ARIMAForecaster(verbose=verbose)
        self.var = VARForecaster(verbose=verbose)
        self.taylor = TaylorRule(verbose=verbose)
        self.phillips = PhillipsCurve(verbose=verbose)

    def run_all(self) -> Dict[str, Any]:
        """Ejecuta todos los modelos econométricos."""
        results = {
            'arima': {},
            'var': None,
            'taylor': {},
            'phillips': None,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'models_run': 0,
                'models_ok': 0,
            }
        }

        models_run = 0
        models_ok = 0

        # ARIMA forecasts
        if self.verbose:
            print("\n  --- ARIMA Forecasts ---")

        for name, method in [
            ('inflation_usa', self.arima.forecast_inflation_usa),
            ('inflation_chile', self.arima.forecast_inflation_chile),
            ('gdp_usa', self.arima.forecast_gdp_usa),
            ('unemployment', self.arima.forecast_unemployment),
            ('fed_funds', self.arima.forecast_fed_funds),
        ]:
            models_run += 1
            try:
                r = method()
                if r is not None:
                    results['arima'][name] = r
                    models_ok += 1
            except Exception as e:
                if self.verbose:
                    print(f"  [ARIMA] {name} failed: {e}")

        # VAR
        if self.verbose:
            print("\n  --- VAR Forecast ---")
        models_run += 1
        try:
            var_result = self.var.forecast_usa_macro(steps=4)
            if var_result is not None:
                results['var'] = var_result
                models_ok += 1
        except Exception as e:
            if self.verbose:
                print(f"  [VAR] Failed: {e}")

        # Taylor Rule
        if self.verbose:
            print("\n  --- Taylor Rule ---")
        for name, method in [
            ('fed', self.taylor.fed_rate),
            ('tpm', self.taylor.tpm_chile),
            ('ecb', self.taylor.ecb_rate),
        ]:
            models_run += 1
            try:
                r = method()
                if r is not None and 'error' not in r:
                    results['taylor'][name] = r
                    models_ok += 1
            except Exception as e:
                if self.verbose:
                    print(f"  [Taylor] {name} failed: {e}")

        # Phillips Curve
        if self.verbose:
            print("\n  --- Phillips Curve ---")
        models_run += 1

        # Get unemployment forecast from ARIMA if available
        unemp_fc = None
        arima_unemp = results['arima'].get('unemployment')
        if arima_unemp:
            unemp_fc = arima_unemp.get('point_forecast')

        try:
            pc_result = self.phillips.estimate_and_forecast(unemployment_forecast=unemp_fc)
            if pc_result is not None:
                results['phillips'] = pc_result
                models_ok += 1
        except Exception as e:
            if self.verbose:
                print(f"  [Phillips] Failed: {e}")

        results['metadata']['models_run'] = models_run
        results['metadata']['models_ok'] = models_ok

        return results


# =========================================================================
# 5. EQUITY VALUATION MODEL (Fair P/E)
# =========================================================================

class EquityValuationModel:
    """
    Modelo de valuación fair value para P/E por región.
    Combina Fed Model, Mean Reversion, y Earnings Growth.

    Fair P/E = weighted average de 3 enfoques:
    1. Fed Model (40%): Fair P/E = 1 / (UST_10Y + ERP_equilibrium)
    2. Mean Reversion (40%): PE_10Y_avg × (1 + ajuste_macro)
    3. Earnings Growth (20%): PE × (1 + EPS_growth) / (1 + required_return)
    """

    PE_10Y_AVERAGES = {
        'us': 21.5,       # S&P 500 10Y avg trailing PE
        'europe': 15.8,   # Stoxx 600
        'em': 13.2,       # MSCI EM
        'japan': 16.5,    # Topix
        'chile': 14.0,    # IPSA
    }

    def fair_pe(
        self,
        region: str,
        ust_10y: float,
        current_pe: float,
        eps_growth: float = None,
        gdp_vs_trend: float = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Calcula fair P/E para una región.

        Args:
            region: 'us', 'europe', 'em', 'japan', 'chile'
            ust_10y: UST 10Y yield en % (e.g. 4.3)
            current_pe: P/E trailing actual
            eps_growth: EPS growth YoY en % (e.g. 8.0)
            gdp_vs_trend: GDP gap vs trend en % (positivo = above trend)

        Returns:
            Dict con fair_pe, upside_pct, signal, components
        """
        if not current_pe or current_pe <= 0:
            return None

        erp = 0.045  # equilibrium ERP (4.5%)

        # 1. Fed Model: Fair P/E = 1 / (10Y yield + ERP)
        fed_pe = None
        if ust_10y and ust_10y > 0:
            fed_pe = 1 / (ust_10y / 100 + erp)

        # 2. Mean Reversion: PE_10Y_avg * (1 + macro_adjustment)
        avg_pe = self.PE_10Y_AVERAGES.get(region, 17.0)
        macro_adj = 1 + (gdp_vs_trend / 100) * 0.5  # ±5% adj per 10% GDP gap
        mean_rev_pe = avg_pe * macro_adj

        # 3. Earnings Growth Model
        eg_pe = None
        if eps_growth is not None and current_pe > 0:
            req_return = (ust_10y or 4.0) / 100 + erp
            if req_return > 0:
                eg_pe = current_pe * (1 + eps_growth / 100) / (1 + req_return)

        # Weighted average
        components = []
        if fed_pe and fed_pe > 0:
            components.append((fed_pe, 0.4))
        if mean_rev_pe and mean_rev_pe > 0:
            components.append((mean_rev_pe, 0.4))
        if eg_pe and eg_pe > 0:
            components.append((eg_pe, 0.2))

        if not components:
            return None

        total_weight = sum(w for _, w in components)
        fair = sum(v * w for v, w in components) / total_weight

        upside_pct = round((fair / current_pe - 1) * 100, 1) if current_pe else None

        if upside_pct is not None:
            if upside_pct > 10:
                signal = 'BARATO'
            elif upside_pct < -10:
                signal = 'CARO'
            else:
                signal = 'FAIR'
        else:
            signal = 'N/D'

        return {
            'fair_pe': round(fair, 1),
            'upside_pct': upside_pct,
            'signal': signal,
            'components': {
                'fed_model': round(fed_pe, 1) if fed_pe else None,
                'mean_reversion': round(mean_rev_pe, 1),
                'earnings_growth': round(eg_pe, 1) if eg_pe else None,
            },
        }


# =========================================================================
# STANDALONE TEST
# =========================================================================

def main():
    """Test de la suite econométrica."""
    import time

    print("=" * 60)
    print("GREYBARK RESEARCH - ECONOMETRIC MODELS TEST")
    print("=" * 60)

    suite = EconometricSuite(verbose=True)
    start = time.time()
    results = suite.run_all()
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"RESULTADOS ({elapsed:.1f}s)")
    print(f"{'=' * 60}")
    print(f"Modelos corridos: {results['metadata']['models_run']}")
    print(f"Modelos OK: {results['metadata']['models_ok']}")

    # ARIMA
    arima = results.get('arima', {})
    if arima:
        print(f"\nARIMA ({len(arima)} series):")
        for name, data in arima.items():
            print(f"  {name}: {data['last_actual']:.2f} -> {data['point_forecast']:.2f} "
                  f"[{data['ci_68'][0]:.2f}, {data['ci_68'][1]:.2f}] "
                  f"({data['model_order']})")

    # VAR
    var = results.get('var')
    if var:
        print(f"\nVAR ({var['model_info']['type']}, lag={var['model_info']['lag_order']}):")
        for name, data in var['forecasts'].items():
            print(f"  {name}: {data['last_actual']:.2f} -> {data['point_forecast']:.2f} "
                  f"[{data['ci_95'][0]:.2f}, {data['ci_95'][1]:.2f}]")

    # Taylor
    taylor = results.get('taylor', {})
    if taylor:
        print(f"\nTaylor Rule:")
        for name, data in taylor.items():
            curr = data.get('current_rate', '?')
            pure = data.get('taylor_rate', '?')
            fc = data.get('forecast_12m', '?')
            gap = data.get('gap_vs_actual', '?')
            print(f"  {name}: actual={curr}%, Taylor={pure:.2f}%, 12M={fc}% (gap={gap}pp)")

    # Phillips
    pc = results.get('phillips')
    if pc:
        print(f"\nPhillips Curve:")
        print(f"  beta={pc['coefficients']['beta']:.4f}, R2={pc['coefficients']['r_squared']:.3f}")
        print(f"  Current: infl={pc['current_inflation']:.1f}%, u={pc['current_unemployment']:.1f}%")
        print(f"  Implied: {pc['implied_current']:.1f}% ({pc['assessment']})")
        print(f"  Forecast (u={pc['unemployment_forecast']:.1f}%): infl={pc['forecast_inflation']:.1f}%"
              f" [{pc['ci_68'][0]:.1f}, {pc['ci_68'][1]:.1f}]")


if __name__ == "__main__":
    main()

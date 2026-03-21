# -*- coding: utf-8 -*-
"""
Greybark Research - Chart Data Provider
=========================================

Provee series de tiempo REALES para charts del macro report.
Centraliza la obtención de datos desde BCCh REST API + FRED.

Cada método retorna datos en formato listo para charts:
  - pd.Series con DatetimeIndex para series individuales
  - Dict[str, pd.Series] para grupos de series
  - Fallback a None si la API falla (el chart generator usa _interp())
"""

import sys
import time
import logging
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Optional, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))

from greybark.data_sources.bcch_client import BCChClient
from greybark.data_sources.fred_client import FREDClient
from greybark.config import BCChSeries, FREDSeries


class ChartDataProvider:
    """Provee series de tiempo reales para charts del macro report."""

    MAX_RETRIES = 3
    RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff

    def __init__(self, lookback_months: int = 120, injected_spot: Dict[str, float] = None):
        self.bcch = BCChClient()
        self.fred = FREDClient()
        self.lookback_days = lookback_months * 31  # ~10 years
        self.start = date.today() - timedelta(days=self.lookback_days)
        self.end = date.today()
        self._cache: Dict[str, pd.Series] = {}
        self._usa_latest = None  # Lazy-loaded USA data cache
        self._injected_spot = injected_spot or {}
        self._fetch_stats = {'ok': 0, 'retried': 0, 'failed': 0}

    def _retry_fetch(self, fn, label: str):
        """Execute fn() with up to MAX_RETRIES retries + exponential backoff."""
        last_err = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                result = fn()
                if attempt > 0:
                    self._fetch_stats['retried'] += 1
                    logger.info("ChartDataProvider: %s succeeded on attempt %d", label, attempt + 1)
                self._fetch_stats['ok'] += 1
                return result
            except Exception as e:
                last_err = e
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    logger.warning(
                        "ChartDataProvider: %s attempt %d failed (%s), retrying in %.1fs",
                        label, attempt + 1, e, delay
                    )
                    time.sleep(delay)
        self._fetch_stats['failed'] += 1
        logger.error("ChartDataProvider: %s FAILED after %d attempts: %s", label, self.MAX_RETRIES + 1, last_err)
        return None

    def get_spot(self, key: str, default=None):
        """Return injected spot value if available, else default."""
        return self._injected_spot.get(key, default)

    def get_series(self, series_id: str, resample: str = None) -> Optional[pd.Series]:
        """
        Fetch + cache + optional resample a mensual.

        Args:
            series_id: BCCh series identifier
            resample: 'M' for monthly, None to keep original frequency

        Returns:
            pd.Series with DatetimeIndex, or None if failed
        """
        cache_key = f"{series_id}_{resample or 'raw'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self._retry_fetch(
            lambda: self.bcch.get_series(
                series_id,
                start_date=self.start,
                end_date=self.end,
                days_back=self.lookback_days
            ),
            f"BCCh:{series_id}"
        )

        if data is None or (hasattr(data, '__len__') and len(data) == 0):
            return None

        # Only resample if data is truly high-frequency (daily).
        # Monthly series (e.g., IMACEC, IPC) already have ~1 point/month
        # and resampling can collapse points due to date parsing quirks.
        if resample and hasattr(data.index, 'to_period'):
            n_points = len(data)
            date_range_days = (data.index[-1] - data.index[0]).days
            avg_gap = date_range_days / max(n_points - 1, 1) if n_points > 1 else 30

            # Only resample if avg gap < 15 days (i.e., daily data)
            if avg_gap < 15:
                try:
                    freq = 'ME' if resample == 'M' else resample
                    data = data.resample(freq).last().dropna()
                except Exception:
                    pass

        self._cache[cache_key] = data
        return data

    # =========================================================================
    # FORMAT HELPERS
    # =========================================================================

    def series_to_chart_data(self, series: pd.Series,
                             date_fmt: str = '%b%y') -> List[Tuple[str, float]]:
        """
        Convierte pd.Series a List[Tuple[str, float]] para chart_gen.

        Args:
            series: pd.Series with DatetimeIndex
            date_fmt: strftime format for labels (default: 'Feb16')

        Returns:
            List of (label, value) tuples
        """
        if series is None:
            return []
        result = []
        for dt, val in series.items():
            try:
                label = pd.Timestamp(dt).strftime(date_fmt)
                result.append((label, round(float(val), 2)))
            except (ValueError, TypeError):
                continue
        return result

    def compute_yoy_from_monthly_var(self, series_id: str) -> Optional[pd.Series]:
        """
        Calcula IPC YoY rolling 12m desde variaciones mensuales.
        Útil para IPC_VAR que reporta variaciones mensuales.

        Returns:
            pd.Series con inflación YoY acumulada rolling 12 meses
        """
        monthly = self.get_series(series_id, resample='M')
        if monthly is None or len(monthly) < 12:
            return None

        # Rolling sum of 12 monthly variations = YoY
        yoy = monthly.rolling(12).sum()
        return yoy.dropna()

    # =========================================================================
    # CHILE
    # =========================================================================

    def get_chile_dashboard(self) -> Dict[str, Optional[pd.Series]]:
        """
        IMACEC YoY, Desempleo, IPC YoY (calculado), USD/CLP.
        Para chile_dashboard chart (4 paneles).
        """
        return {
            'imacec': self.get_series(BCChSeries.IMACEC_YOY, resample='M'),
            'desempleo': self.get_series(BCChSeries.DESEMPLEO, resample='M'),
            'ipc_yoy': self.compute_yoy_from_monthly_var(BCChSeries.IPC_VAR),
            'usd_clp': self.get_series(BCChSeries.USD_CLP, resample='M'),
        }

    def get_chile_ipc_yoy(self) -> Optional[pd.Series]:
        """IPC YoY rolling 12m desde variaciones mensuales."""
        return self.compute_yoy_from_monthly_var(BCChSeries.IPC_VAR)

    def get_chile_external(self) -> Dict[str, Optional[pd.Series]]:
        """
        Exportaciones, Importaciones, Cobre para chile_external chart.
        """
        return {
            'exportaciones': self.get_series(BCChSeries.EXPORTACIONES, resample='M'),
            'importaciones': self.get_series(BCChSeries.IMPORTACIONES, resample='M'),
            'cobre': self.get_series(BCChSeries.COBRE, resample='M'),
        }

    def get_chile_latest(self) -> Dict[str, Optional[float]]:
        """
        Últimos valores de indicadores Chile para narrativas/tablas.
        """
        return {
            'imacec_yoy': self.bcch.get_imacec(),
            'desempleo': self.bcch.get_latest_value(BCChSeries.DESEMPLEO),
            'ipc_yoy': self.bcch.get_ipc_yoy(),
            'ipc_mom': self.bcch.get_ipc_mom(),
            'usd_clp': self.bcch.get_usd_clp(),
            'tpm': self.bcch.get_tpm(),
            'uf': self.bcch.get_uf(),
        }

    # =========================================================================
    # CHILE IPC COMPONENTS (COICOP divisions)
    # =========================================================================

    def get_chile_ipc_components(self, months: int = 36) -> Optional[Dict]:
        """
        IPC Chile desglosado por divisiones COICOP agrupadas en 5 categorías.

        Fetch 13 índices de división (base 2023=100) + 13 ponderaciones.
        Computa YoY desde índice y contribución ponderada.

        Returns:
            Dict with:
              'categories': list of month labels (str)
              'components': Dict[str, List[float]] — contribuciones en pp por grupo
              'total': List[float] — IPC total (suma de contribuciones)
            or None if insufficient data.
        """
        import numpy as np

        # 13 divisiones COICOP — series BCCh índice + ponderación
        divisions = [
            ('DIV10000', 'Alimentos y bebidas no alcohólicas'),
            ('DIV20000', 'Bebidas alcohólicas y tabaco'),
            ('DIV30000', 'Vestuario y calzado'),
            ('DIV40000', 'Vivienda y servicios básicos'),
            ('DIV50000', 'Equipamiento hogar'),
            ('DIV60000', 'Salud'),
            ('DIV70000', 'Transporte'),
            ('DIV80000', 'Info y comunicación'),
            ('DIV90000', 'Recreación'),
            ('DIV100000', 'Educación'),
            ('DIV110000', 'Restaurantes y alojamiento'),
            ('DIV120000', 'Seguros y servicios financieros'),
            ('DIV130000', 'Bienes y servicios diversos'),
        ]

        # Agrupación en 5 categorías para el chart
        groups = {
            'Alimentos': [0, 1],        # Div 1 + 2
            'Vivienda y SS.BB.': [3],    # Div 4
            'Transporte': [6],           # Div 7
            'Servicios excl. Viv.': [5, 7, 8, 9, 10, 11, 12],  # Div 6,8,9,10,11,12,13
            'Bienes excl. Alim.': [2, 4],  # Div 3 + 5
        }

        # Fetch all 13 index series + weights
        indices = {}
        weights = {}
        for i, (div_code, _name) in enumerate(divisions):
            idx_sid = f'F074.IPC.IND.{div_code}.2023.C.M'
            pon_sid = f'F074.IPC.PON.{div_code}.2023.C.M'
            idx_s = self.get_series(idx_sid)
            pon_s = self.get_series(pon_sid)
            if idx_s is not None and len(idx_s) >= 13:
                indices[i] = idx_s
            if pon_s is not None and len(pon_s) > 0:
                # Weight is a percentage (e.g., 19.08)
                weights[i] = float(pon_s.iloc[-1]) / 100.0

        # Need at least 10 of 13 divisions to produce a meaningful chart
        if len(indices) < 10 or len(weights) < 10:
            return None

        # Compute YoY for each division: (index[t] / index[t-12] - 1) * 100
        yoy_series = {}
        for i, idx_s in indices.items():
            yoy = idx_s.pct_change(12) * 100
            yoy = yoy.dropna()
            if len(yoy) > 0:
                yoy_series[i] = yoy

        if len(yoy_series) < 10:
            return None

        # Find common date range across all YoY series
        common_idx = None
        for s in yoy_series.values():
            if common_idx is None:
                common_idx = s.index
            else:
                common_idx = common_idx.intersection(s.index)

        if common_idx is None or len(common_idx) < 6:
            return None

        # Limit to last N months
        common_idx = common_idx.sort_values()[-months:]

        # Build grouped contributions
        components = {}
        for group_name, div_indices in groups.items():
            contrib = np.zeros(len(common_idx))
            for di in div_indices:
                if di in yoy_series and di in weights:
                    aligned = yoy_series[di].reindex(common_idx)
                    vals = aligned.fillna(0).values
                    contrib += weights[di] * vals
            components[group_name] = [round(float(v), 3) for v in contrib]

        # Total = sum of all contributions
        total = [round(sum(components[g][j] for g in components), 2)
                 for j in range(len(common_idx))]

        # Month labels
        categories = [pd.Timestamp(dt).strftime('%b%y') for dt in common_idx]

        return {
            'categories': categories,
            'components': components,
            'total': total,
        }

    # =========================================================================
    # INTERNATIONAL INFLATION
    # =========================================================================

    def get_inflation_intl(self) -> Dict[str, Optional[pd.Series]]:
        """IPC YoY de 10 países (BCChSeries.IPC_INTL_*)."""
        return {
            'USA': self.get_series(BCChSeries.IPC_INTL_USA, resample='M'),
            'Eurozona': self.get_series(BCChSeries.IPC_INTL_EUROZONA, resample='M'),
            'China': self.get_series(BCChSeries.IPC_INTL_CHINA, resample='M'),
            'Japon': self.get_series(BCChSeries.IPC_INTL_JAPON, resample='M'),
            'UK': self.get_series(BCChSeries.IPC_INTL_UK, resample='M'),
            'Brasil': self.get_series(BCChSeries.IPC_INTL_BRASIL, resample='M'),
            'Mexico': self.get_series(BCChSeries.IPC_INTL_MEXICO, resample='M'),
            'Argentina': self.get_series(BCChSeries.IPC_INTL_ARGENTINA, resample='M'),
            'Peru': self.get_series(BCChSeries.IPC_INTL_PERU, resample='M'),
            'Colombia': self.get_series(BCChSeries.IPC_INTL_COLOMBIA, resample='M'),
        }

    # =========================================================================
    # POLICY RATES
    # =========================================================================

    def get_policy_rates(self) -> Dict[str, Optional[pd.Series]]:
        """TPM de bancos centrales globales."""
        return {
            'Fed Funds (USA)': self.get_series(BCChSeries.TPM_USA, resample='M'),
            'ECB Deposit (EUR)': self.get_series(BCChSeries.TPM_EUROZONA, resample='M'),
            'BoE Rate (UK)': self.get_series(BCChSeries.TPM_UK, resample='M'),
            'BoJ Rate (JPN)': self.get_series(BCChSeries.TPM_JAPON, resample='M'),
            'BCCh TPM (CHL)': self.get_series(BCChSeries.TPM, resample='M'),
            'PBOC MLF (CHN)': self.get_series(BCChSeries.TPM_CHINA, resample='M'),
        }

    def get_latam_rates(self) -> Dict[str, Optional[pd.Series]]:
        """TPM LatAm: Chile, Brasil, México, Colombia."""
        return {
            'BCCh TPM (Chile)': self.get_series(BCChSeries.TPM, resample='M'),
            'Selic (Brasil)': self.get_series(BCChSeries.TPM_BRASIL, resample='M'),
            'Banxico (Mexico)': self.get_series(BCChSeries.TPM_MEXICO, resample='M'),
            'BanRep (Colombia)': self.get_series(BCChSeries.TPM_COLOMBIA, resample='M'),
        }

    # =========================================================================
    # COMMODITIES
    # =========================================================================

    def _get_yfinance_spot(self, ticker: str) -> Optional[float]:
        """Fetch latest spot price from yfinance (daily, no lag)."""
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period='5d')
            if hist is not None and len(hist) > 0:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            logger.warning("yfinance spot %s failed: %s", ticker, e)
        return None

    def _append_spot_if_stale(self, series: Optional[pd.Series],
                               yf_ticker: str, max_age_days: int = 35) -> Optional[pd.Series]:
        """If BCCh series is >max_age_days old, append yfinance spot as current data point."""
        if series is None or len(series) == 0:
            return series
        last_date = pd.Timestamp(series.index[-1])
        age = (pd.Timestamp.now() - last_date).days
        if age <= max_age_days:
            return series  # Fresh enough
        spot = self._get_yfinance_spot(yf_ticker)
        if spot is None:
            return series
        today = pd.Timestamp(date.today())
        new_point = pd.Series([spot], index=[today], name=series.name)
        updated = pd.concat([series, new_point])
        logger.info("ChartDataProvider: %s stale (%dd), appended yfinance spot %.2f", yf_ticker, age, spot)
        return updated

    def get_commodities(self) -> Dict[str, Optional[pd.Series]]:
        """Cobre, Oro, Brent para commodity_prices chart. yfinance spot if BCCh stale."""
        brent = self.get_series(BCChSeries.BRENT, resample='M')
        cobre = self.get_series(BCChSeries.COBRE, resample='M')
        oro = self.get_series(BCChSeries.ORO, resample='M')
        return {
            'brent': self._append_spot_if_stale(brent, 'BZ=F'),
            'petroleo': self._append_spot_if_stale(brent, 'BZ=F'),
            'cobre': self._append_spot_if_stale(cobre, 'HG=F'),
            'oro': self._append_spot_if_stale(oro, 'GC=F'),
        }

    def get_commodities_table(self) -> List[Dict]:
        """Datos para tabla de commodities: valor actual, cambio 1m, 3m, 1y.
        Uses yfinance spot if BCCh data is stale (>35 days old)."""
        # (name, BCCh series, unit, yfinance ticker for spot)
        commodities = [
            ('Cobre', BCChSeries.COBRE, 'USD/lb', 'HG=F'),
            ('Oro', BCChSeries.ORO, 'USD/oz', 'GC=F'),
            ('Brent', BCChSeries.BRENT, 'USD/bbl', 'BZ=F'),
            ('WTI', BCChSeries.WTI, 'USD/bbl', 'CL=F'),
            ('Gas Natural', BCChSeries.GAS_NATURAL, 'USD/MMBtu', 'NG=F'),
            ('Plata', BCChSeries.PLATA, 'USD/oz', 'SI=F'),
            ('Litio', BCChSeries.LITIO, 'USD/ton', None),
        ]
        result = []
        for name, sid, unit, yf_ticker in commodities:
            s = self.get_series(sid, resample='M')
            if yf_ticker:
                s = self._append_spot_if_stale(s, yf_ticker)
            if s is None or len(s) < 2:
                continue
            current = float(s.iloc[-1])
            row = {'nombre': name, 'unidad': unit, 'actual': current}
            # 1m change
            if len(s) >= 2:
                prev1m = float(s.iloc[-2])
                row['chg_1m'] = round((current / prev1m - 1) * 100, 1) if prev1m != 0 else None
            # 3m change
            if len(s) >= 4:
                prev3m = float(s.iloc[-4])
                row['chg_3m'] = round((current / prev3m - 1) * 100, 1) if prev3m != 0 else None
            # 1y change
            if len(s) >= 13:
                prev1y = float(s.iloc[-13])
                row['chg_1y'] = round((current / prev1y - 1) * 100, 1) if prev1y != 0 else None
            result.append(row)
        return result

    def get_energy(self) -> Dict[str, Optional[pd.Series]]:
        """WTI, Gas Natural para energy_food chart. yfinance spot if stale."""
        wti = self.get_series(BCChSeries.WTI, resample='M')
        gas = self.get_series(BCChSeries.GAS_NATURAL, resample='M')
        brent = self.get_series(BCChSeries.BRENT, resample='M')
        return {
            'wti': self._append_spot_if_stale(wti, 'CL=F'),
            'gas': self._append_spot_if_stale(gas, 'NG=F'),
            'brent': self._append_spot_if_stale(brent, 'BZ=F'),
        }

    # =========================================================================
    # BONDS
    # =========================================================================

    def get_bond10y(self) -> Dict[str, Optional[pd.Series]]:
        """Bonos 10Y de países disponibles."""
        return {
            'USA': self.get_series(BCChSeries.BOND10_USA, resample='M'),
            'Eurozona': self.get_series(BCChSeries.BOND10_EUROZONA, resample='M'),
            'Japon': self.get_series(BCChSeries.BOND10_JAPON, resample='M'),
            'UK': self.get_series(BCChSeries.BOND10_UK, resample='M'),
            'Chile': self.get_series(BCChSeries.BOND10_CHILE, resample='M'),
            'Brasil': self.get_series(BCChSeries.BOND10_BRASIL, resample='M'),
            'Mexico': self.get_series(BCChSeries.BOND10_MEXICO, resample='M'),
            'Colombia': self.get_series(BCChSeries.BOND10_COLOMBIA, resample='M'),
        }

    # =========================================================================
    # INFLATION HEATMAP DATA
    # =========================================================================

    def get_inflation_heatmap_data(self, months: int = 24) -> Optional[Dict]:
        """
        Datos para heatmap de inflación: 10 países × últimos N meses.

        Returns:
            Dict with 'countries', 'col_labels', 'data' (list of lists),
            or None if insufficient data.
        """
        country_series = {
            'USA': BCChSeries.IPC_INTL_USA,
            'Euro Area': BCChSeries.IPC_INTL_EUROZONA,
            'UK': BCChSeries.IPC_INTL_UK,
            'Japon': BCChSeries.IPC_INTL_JAPON,
            'China': BCChSeries.IPC_INTL_CHINA,
            'Brasil': BCChSeries.IPC_INTL_BRASIL,
            'Mexico': BCChSeries.IPC_INTL_MEXICO,
            'Peru': BCChSeries.IPC_INTL_PERU,
            'Colombia': BCChSeries.IPC_INTL_COLOMBIA,
        }

        # Fetch Chile IPC YoY
        chile_yoy = self.get_chile_ipc_yoy()

        all_data = {}
        for name, sid in country_series.items():
            s = self.get_series(sid, resample='M')
            if s is not None and len(s) >= months:
                all_data[name] = s.iloc[-months:]

        if chile_yoy is not None and len(chile_yoy) >= months:
            all_data['Chile'] = chile_yoy.iloc[-months:]

        if len(all_data) < 5:
            return None

        # Build aligned matrix
        # Use the date index from the first valid series
        ref_index = None
        for s in all_data.values():
            if ref_index is None or len(s) > len(ref_index):
                ref_index = s.index[-months:]

        countries = list(all_data.keys())
        col_labels = [pd.Timestamp(dt).strftime('%b%y') for dt in ref_index]
        data = []
        for country in countries:
            s = all_data[country]
            # Reindex to align with reference
            aligned = s.reindex(ref_index, method='nearest', tolerance=pd.Timedelta('15D'))
            row = [round(float(v), 1) if pd.notna(v) else 0.0 for v in aligned.values]
            data.append(row)

        return {
            'countries': countries,
            'col_labels': col_labels,
            'data': data,
        }

    # =========================================================================
    # FRED HELPER
    # =========================================================================

    def get_fred_series(self, series_id: str, resample: str = 'M') -> Optional[pd.Series]:
        """
        Fetch FRED series with cache and optional resample to monthly.

        Args:
            series_id: FRED series ID (e.g., 'UNRATE')
            resample: 'M' for monthly, None to keep original frequency

        Returns:
            pd.Series with DatetimeIndex, or None if failed
        """
        cache_key = f"fred_{series_id}_{resample or 'raw'}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        data = self._retry_fetch(
            lambda: self.fred.get_series(
                series_id,
                start_date=self.start,
                end_date=self.end
            ),
            f"FRED:{series_id}"
        )

        if data is None or (hasattr(data, '__len__') and len(data) == 0):
            return None

        # Drop NaN values from FRED (common in daily series)
        data = data.dropna()

        if resample and len(data) > 0:
            n_points = len(data)
            date_range_days = (data.index[-1] - data.index[0]).days
            avg_gap = date_range_days / max(n_points - 1, 1) if n_points > 1 else 30

            # Only resample daily data (avg gap < 15 days)
            if avg_gap < 15:
                try:
                    freq = 'ME' if resample == 'M' else resample
                    data = data.resample(freq).last().dropna()
                except Exception:
                    pass

        self._cache[cache_key] = data
        return data

    # =========================================================================
    # USA LABOR MARKET (FRED)
    # =========================================================================

    def get_usa_unemployment(self) -> Dict[str, Optional[pd.Series]]:
        """U3 (UNRATE) and U6 (U6RATE) unemployment rates."""
        return {
            'u3': self.get_fred_series(FREDSeries.UNEMPLOYMENT),
            'u6': self.get_fred_series(FREDSeries.U6_RATE),
        }

    def get_usa_nfp(self) -> Optional[pd.Series]:
        """PAYEMS monthly change (Non-Farm Payrolls in thousands)."""
        payems = self.get_fred_series(FREDSeries.PAYROLLS)
        if payems is None or len(payems) < 2:
            return None
        # Monthly change in thousands
        nfp = payems.diff()
        return nfp.dropna()

    def get_usa_jolts(self) -> Dict[str, Optional[pd.Series]]:
        """JOLTS: Job Openings, Quits Rate, and computed Openings/Unemployed ratio."""
        openings = self.get_fred_series(FREDSeries.JOB_OPENINGS)
        quits = self.get_fred_series(FREDSeries.QUITS_RATE)

        # Compute ratio: openings (thousands) / unemployed persons
        ratio = None
        u3 = self.get_fred_series(FREDSeries.UNEMPLOYMENT)
        payems = self.get_fred_series(FREDSeries.PAYROLLS)
        if openings is not None and u3 is not None and payems is not None:
            try:
                # Approximate unemployed = (u3/100) * labor_force
                # labor_force ≈ payems / (1 - u3/100)
                # unemployed ≈ payems * u3 / (100 - u3)
                # openings is in thousands, payems in thousands
                aligned = pd.DataFrame({
                    'openings': openings,
                    'u3': u3,
                    'payems': payems
                }).dropna()
                if len(aligned) > 0:
                    unemployed = aligned['payems'] * aligned['u3'] / (100 - aligned['u3'])
                    ratio = (aligned['openings'] / unemployed).rename('ratio')
            except Exception:
                pass

        return {
            'openings': openings,
            'quits': quits,
            'ratio': ratio,
        }

    def get_usa_wages(self) -> Dict[str, Optional[pd.Series]]:
        """AHE YoY, LFPR, Prime-Age participation, ECI."""
        ahe = self.get_fred_series(FREDSeries.AHE)
        ahe_yoy = None
        if ahe is not None and len(ahe) >= 13:
            ahe_yoy = ahe.pct_change(12) * 100

        eci = self.get_fred_series(FREDSeries.ECI_WAGES)
        eci_yoy = None
        if eci is not None and len(eci) >= 5:
            # ECI is quarterly; YoY = pct_change(4)
            eci_yoy = eci.pct_change(4) * 100

        return {
            'ahe_yoy': ahe_yoy,
            'eci_yoy': eci_yoy,
            'lfpr': self.get_fred_series(FREDSeries.CIVPART),
            'prime_age': self.get_fred_series(FREDSeries.PRIME_AGE_EPOP),
        }

    # =========================================================================
    # USA INFLATION (FRED)
    # =========================================================================

    def get_usa_cpi(self) -> Dict[str, Optional[pd.Series]]:
        """CPI Headline YoY, Core CPI YoY, Core PCE YoY."""
        headline = self.get_fred_series(FREDSeries.HEADLINE_CPI)
        core = self.get_fred_series(FREDSeries.CORE_CPI)
        pce_core = self.get_fred_series(FREDSeries.CORE_PCE)

        def yoy(s):
            if s is not None and len(s) >= 13:
                return s.pct_change(12) * 100
            return None

        return {
            'cpi_headline_yoy': yoy(headline),
            'cpi_core_yoy': yoy(core),
            'pce_core_yoy': yoy(pce_core),
        }

    # =========================================================================
    # USA LEADING INDICATORS (FRED)
    # =========================================================================

    def get_usa_leading(self) -> Dict[str, Optional[pd.Series]]:
        """Mfg New Orders, Housing Starts, Consumer Confidence, UMich Sentiment.
        Note: ISM PMI is proprietary (not on FRED). NEWORDER = Manufacturers' New Orders ($M)."""
        new_orders = self.get_fred_series(FREDSeries.ISM_NEW_ORDERS)
        # Convert to billions for readability
        if new_orders is not None:
            new_orders = new_orders / 1000
        return {
            'mfg_new_orders_bn': new_orders,
            'housing_starts': self.get_fred_series(FREDSeries.HOUSING_STARTS),
            'consumer_confidence': self.get_fred_series(FREDSeries.CONSUMER_CONFIDENCE),
            'umich_sentiment': self.get_fred_series(FREDSeries.UMICH_SENTIMENT),
        }

    # =========================================================================
    # USA CPI BREAKDOWN (FRED)
    # =========================================================================

    def get_usa_cpi_breakdown(self) -> Dict[str, Optional[pd.Series]]:
        """CPI component time series (YoY) for stacked chart."""
        components = [
            ('shelter', FREDSeries.CPI_SHELTER),
            ('services_ex_shelter', FREDSeries.CPI_SERVICES_EX_ENERGY),
            ('core_goods', FREDSeries.CPI_COMMODITIES_EX_FOOD_ENERGY),
            ('food', FREDSeries.CPI_FOOD),
            ('energy', FREDSeries.CPI_ENERGY),
        ]
        result = {}
        for key, sid in components:
            s = self.get_fred_series(sid)
            if s is not None and len(s) >= 13:
                yoy = s.pct_change(12) * 100
                result[key] = yoy.dropna()
            else:
                result[key] = None
        return result

    # =========================================================================
    # YIELD CURVE (FRED)
    # =========================================================================

    def get_yield_curve_current(self) -> Dict[str, Optional[float]]:
        """Latest treasury yields for yield curve chart: 1M through 30Y."""
        tenors = {
            '1M': FREDSeries.TREASURY_1MO,
            '3M': FREDSeries.TREASURY_3MO,
            '6M': FREDSeries.TREASURY_6MO,
            '1Y': FREDSeries.TREASURY_1Y,
            '2Y': FREDSeries.TREASURY_2Y,
            '5Y': FREDSeries.TREASURY_5Y,
            '10Y': FREDSeries.TREASURY_10Y,
            '30Y': FREDSeries.TREASURY_30Y,
        }
        result = {}
        for label, sid in tenors.items():
            s = self.get_fred_series(sid, resample=None)
            if s is not None and len(s) > 0:
                result[label] = round(float(s.dropna().iloc[-1]), 2)
            else:
                result[label] = None
        return result

    def get_yield_curve_historical(self) -> Dict[str, Dict[str, Optional[float]]]:
        """Current, 1-month-ago, and 1-year-ago yield curves."""
        tenors = {
            '1M': FREDSeries.TREASURY_1MO,
            '3M': FREDSeries.TREASURY_3MO,
            '6M': FREDSeries.TREASURY_6MO,
            '1Y': FREDSeries.TREASURY_1Y,
            '2Y': FREDSeries.TREASURY_2Y,
            '5Y': FREDSeries.TREASURY_5Y,
            '10Y': FREDSeries.TREASURY_10Y,
            '30Y': FREDSeries.TREASURY_30Y,
        }
        current = {}
        previous = {}
        year_ago = {}
        for label, sid in tenors.items():
            s = self.get_fred_series(sid, resample=None)
            if s is not None and len(s) > 0:
                s_clean = s.dropna()
                current[label] = round(float(s_clean.iloc[-1]), 2)
                # ~1 month ago (20 trading days)
                if len(s_clean) > 20:
                    previous[label] = round(float(s_clean.iloc[-21]), 2)
                # ~1 year ago (250 trading days)
                if len(s_clean) > 250:
                    year_ago[label] = round(float(s_clean.iloc[-251]), 2)
        return {
            'current': current,
            'previous': previous,
            'year_ago': year_ago,
        }

    def get_yield_spreads(self) -> Dict[str, Optional[pd.Series]]:
        """DGS2, DGS10, DGS3MO full time series for spread calculation."""
        return {
            'y2': self.get_fred_series(FREDSeries.TREASURY_2Y),
            'y10': self.get_fred_series(FREDSeries.TREASURY_10Y),
            'y3m': self.get_fred_series(FREDSeries.TREASURY_3MO),
        }

    # =========================================================================
    # USA LATEST VALUES (for content generator)
    # =========================================================================

    def get_usa_latest(self) -> Dict[str, Optional[float]]:
        """Latest values for USA macro narrative/tables."""
        result = {}

        # Unemployment
        u3 = self.get_fred_series(FREDSeries.UNEMPLOYMENT)
        if u3 is not None and len(u3) > 0:
            result['unemployment'] = round(float(u3.iloc[-1]), 1)
            if len(u3) > 1:
                result['unemployment_prev'] = round(float(u3.iloc[-2]), 1)

        u6 = self.get_fred_series(FREDSeries.U6_RATE)
        if u6 is not None and len(u6) > 0:
            result['u6'] = round(float(u6.iloc[-1]), 1)
            if len(u6) > 1:
                result['u6_prev'] = round(float(u6.iloc[-2]), 1)

        # NFP
        payems = self.get_fred_series(FREDSeries.PAYROLLS)
        if payems is not None and len(payems) >= 3:
            result['nfp'] = round(float(payems.iloc[-1] - payems.iloc[-2]), 0)
            result['nfp_prev'] = round(float(payems.iloc[-2] - payems.iloc[-3]), 0)

        # Participation
        lfpr = self.get_fred_series(FREDSeries.CIVPART)
        if lfpr is not None and len(lfpr) > 0:
            result['lfpr'] = round(float(lfpr.iloc[-1]), 1)
            if len(lfpr) > 1:
                result['lfpr_prev'] = round(float(lfpr.iloc[-2]), 1)
        prime = self.get_fred_series(FREDSeries.PRIME_AGE_EPOP)
        if prime is not None and len(prime) > 0:
            result['prime_age'] = round(float(prime.iloc[-1]), 1)
            if len(prime) > 1:
                result['prime_age_prev'] = round(float(prime.iloc[-2]), 1)

        # Claims
        ic = self.get_fred_series(FREDSeries.INITIAL_CLAIMS)
        if ic is not None and len(ic) > 0:
            result['initial_claims'] = round(float(ic.iloc[-1]), 0)
            if len(ic) > 1:
                result['initial_claims_prev'] = round(float(ic.iloc[-2]), 0)
        cc = self.get_fred_series(FREDSeries.CONTINUING_CLAIMS)
        if cc is not None and len(cc) > 0:
            result['continuing_claims'] = round(float(cc.iloc[-1]), 0)
            if len(cc) > 1:
                result['continuing_claims_prev'] = round(float(cc.iloc[-2]), 0)

        # Wages
        ahe = self.get_fred_series(FREDSeries.AHE)
        if ahe is not None and len(ahe) >= 13:
            ahe_yoy = float(ahe.iloc[-1] / ahe.iloc[-13] - 1) * 100
            result['ahe_yoy'] = round(ahe_yoy, 1)
            if len(ahe) >= 14:
                ahe_yoy_prev = float(ahe.iloc[-2] / ahe.iloc[-14] - 1) * 100
                result['ahe_yoy_prev'] = round(ahe_yoy_prev, 1)

        # CPI / PCE (YoY from levels)
        for key, sid in [('cpi_headline', FREDSeries.HEADLINE_CPI),
                         ('cpi_core', FREDSeries.CORE_CPI),
                         ('pce_core', FREDSeries.CORE_PCE)]:
            s = self.get_fred_series(sid)
            if s is not None and len(s) >= 13:
                yoy = float(s.iloc[-1] / s.iloc[-13] - 1) * 100
                result[f'{key}_yoy'] = round(yoy, 1)
            if s is not None and len(s) >= 2:
                mom = float(s.iloc[-1] / s.iloc[-2] - 1) * 100
                result[f'{key}_mom'] = round(mom, 2)

        # UMich Sentiment
        umich = self.get_fred_series(FREDSeries.UMICH_SENTIMENT)
        if umich is not None and len(umich) > 0:
            result['umich_sentiment'] = round(float(umich.iloc[-1]), 1)

        # Fed Funds
        ff = self.get_fred_series(FREDSeries.FED_FUNDS, resample=None)
        if ff is not None and len(ff) > 0:
            result['fed_funds'] = round(float(ff.dropna().iloc[-1]), 2)

        # GDP (quarterly, QoQ annualized)
        gdp = self.get_fred_series(FREDSeries.GDP, resample=None)
        if gdp is not None and len(gdp) >= 2:
            gdp_clean = gdp.dropna()
            if len(gdp_clean) >= 2:
                qoq = ((float(gdp_clean.iloc[-1]) / float(gdp_clean.iloc[-2])) ** 4 - 1) * 100
                result['gdp_qoq'] = round(qoq, 1)

        # Manufacturers' New Orders (billions)
        ism = self.get_fred_series(FREDSeries.ISM_NEW_ORDERS)
        if ism is not None and len(ism) > 0:
            result['mfg_new_orders_bn'] = round(float(ism.iloc[-1]) / 1000, 1)

        # Housing Starts
        houst = self.get_fred_series(FREDSeries.HOUSING_STARTS)
        if houst is not None and len(houst) > 0:
            result['housing_starts'] = round(float(houst.iloc[-1]), 0)

        # Consumer Confidence
        cc_idx = self.get_fred_series(FREDSeries.CONSUMER_CONFIDENCE)
        if cc_idx is not None and len(cc_idx) > 0:
            result['consumer_confidence'] = round(float(cc_idx.iloc[-1]), 1)

        # JOLTS
        jo = self.get_fred_series(FREDSeries.JOB_OPENINGS)
        if jo is not None and len(jo) > 0:
            result['job_openings'] = round(float(jo.iloc[-1]), 0)
            if len(jo) > 1:
                result['job_openings_prev'] = round(float(jo.iloc[-2]), 0)
        qr = self.get_fred_series(FREDSeries.QUITS_RATE)
        if qr is not None and len(qr) > 0:
            result['quits_rate'] = round(float(qr.iloc[-1]), 1)
            if len(qr) > 1:
                result['quits_rate_prev'] = round(float(qr.iloc[-2]), 1)

        # EPU — Economic Policy Uncertainty
        try:
            epu_us = self.fred.get_latest_value('USEPUINDXM')
            if epu_us is not None:
                result['epu_usa'] = round(float(epu_us), 1)
        except Exception:
            pass

        return result

    # =========================================================================
    # EUROPE (BCCh)
    # =========================================================================

    def get_europe_dashboard(self) -> Dict[str, Optional[pd.Series]]:
        """GDP Eurozona, CPI, Core CPI, unemployment — for charts."""
        return {
            'gdp': self.get_series(BCChSeries.GDP_EUROZONA, resample='M'),
            'cpi': self.get_series(BCChSeries.IPC_INTL_EUROZONA, resample='M'),
            'core_cpi': self.get_series(BCChSeries.CORE_INTL_EUROZONA, resample='M'),
            'unemployment': self.get_series(BCChSeries.DESEMP_EUROZONA, resample='M'),
        }

    def get_europe_latest(self) -> Dict[str, Optional[float]]:
        """Ultimos valores Europa para narrativas/tablas."""
        result = {}
        # GDP Eurozona (QoQ trimestral)
        gdp = self.get_series(BCChSeries.GDP_EUROZONA)
        if gdp is not None and len(gdp) > 0:
            result['gdp_qoq'] = round(float(gdp.iloc[-1]), 1)
        # GDP por pais
        for key, sid in [('gdp_alemania', BCChSeries.GDP_ALEMANIA),
                         ('gdp_francia', BCChSeries.GDP_FRANCIA),
                         ('gdp_uk', BCChSeries.GDP_UK)]:
            s = self.get_series(sid)
            if s is not None and len(s) > 0:
                result[key] = round(float(s.iloc[-1]), 1)
        # CPI / Core / PPI
        for key, sid in [('cpi', BCChSeries.IPC_INTL_EUROZONA),
                         ('core_cpi', BCChSeries.CORE_INTL_EUROZONA),
                         ('ppi', BCChSeries.PPI_EUROZONA)]:
            s = self.get_series(sid, resample='M')
            if s is not None and len(s) > 0:
                result[key] = round(float(s.iloc[-1]), 1)
        # Unemployment
        desemp = self.get_series(BCChSeries.DESEMP_EUROZONA, resample='M')
        if desemp is not None and len(desemp) > 0:
            result['unemployment'] = round(float(desemp.iloc[-1]), 1)
        # ECB rate
        ecb = self.get_series(BCChSeries.TPM_EUROZONA, resample='M')
        if ecb is not None and len(ecb) > 0:
            result['ecb_rate'] = round(float(ecb.iloc[-1]), 2)
        # Bond 10Y
        bond = self.get_series(BCChSeries.BOND10_EUROZONA, resample='M')
        if bond is not None and len(bond) > 0:
            result['bund_10y'] = round(float(bond.iloc[-1]), 2)
        return result

    # =========================================================================
    # CHINA (BCCh)
    # =========================================================================

    def get_china_dashboard_data(self) -> Dict[str, Optional[pd.Series]]:
        """GDP, CPI, PPI, unemployment — for china_dashboard chart."""
        return {
            'gdp': self.get_series(BCChSeries.GDP_CHINA, resample='M'),
            'cpi': self.get_series(BCChSeries.IPC_INTL_CHINA, resample='M'),
            'ppi': self.get_series(BCChSeries.PPI_CHINA, resample='M'),
            'unemployment': self.get_series(BCChSeries.DESEMP_CHINA, resample='M'),
        }

    def get_china_latest(self) -> Dict[str, Optional[float]]:
        """Ultimos valores China para narrativas/tablas."""
        result = {}
        # GDP (QoQ trimestral)
        gdp = self.get_series(BCChSeries.GDP_CHINA)
        if gdp is not None and len(gdp) > 0:
            result['gdp_qoq'] = round(float(gdp.iloc[-1]), 1)
        # CPI, Core CPI, PPI
        for key, sid in [('cpi', BCChSeries.IPC_INTL_CHINA),
                         ('core_cpi', BCChSeries.CORE_INTL_CHINA),
                         ('ppi', BCChSeries.PPI_CHINA)]:
            s = self.get_series(sid, resample='M')
            if s is not None and len(s) > 0:
                result[key] = round(float(s.iloc[-1]), 1)
        # Unemployment
        desemp = self.get_series(BCChSeries.DESEMP_CHINA, resample='M')
        if desemp is not None and len(desemp) > 0:
            result['unemployment'] = round(float(desemp.iloc[-1]), 1)
        # PBOC rate
        pboc = self.get_series(BCChSeries.TPM_CHINA, resample='M')
        if pboc is not None and len(pboc) > 0:
            result['pboc_rate'] = round(float(pboc.iloc[-1]), 2)
        # Shanghai index
        shg = self.get_series(BCChSeries.SHANGHAI, resample='M')
        if shg is not None and len(shg) > 0:
            result['shanghai'] = round(float(shg.iloc[-1]), 0)
        # CNY/USD
        cny = self.get_series(BCChSeries.CNY_USD, resample='M')
        if cny is not None and len(cny) > 0:
            result['cny_usd'] = round(float(cny.iloc[-1]), 2)

        # EPU — Economic Policy Uncertainty (China)
        try:
            epu_cn = self.get_series('F019.EPU.IND.CHN.M', resample='M')
            if epu_cn is not None and len(epu_cn) > 0:
                result['epu_china'] = round(float(epu_cn.iloc[-1]), 1)
        except Exception:
            pass

        return result

    def get_epu_intl(self) -> Dict[str, Optional['pd.Series']]:
        """EPU time series: USA, China, Europa, Global (BCCh + FRED)."""
        result = {}
        # BCCh series
        for key, sid in [('EE.UU.', 'F019.EPU.IND.10.M'),
                         ('China', 'F019.EPU.IND.CHN.M'),
                         ('Europa', 'F019.EPU.IND.94.M'),
                         ('Global', 'F019.EPU.IND.90.M')]:
            s = self.get_series(sid, resample='M')
            if s is not None and len(s) > 0:
                result[key] = s
        # FRED fallback for USA if BCCh didn't work
        if 'EE.UU.' not in result:
            try:
                usa_fred = self.get_fred_series('USEPUINDXM', resample='M')
                if usa_fred is not None and len(usa_fred) > 0:
                    result['EE.UU.'] = usa_fred
            except Exception:
                pass
        return result

    # =========================================================================
    # USA FISCAL DATA (FRED)
    # =========================================================================

    def get_usa_fiscal(self) -> Dict[str, Optional[float]]:
        """US fiscal indicators from FRED as % of GDP.

        Returns dict with keys:
            deficit_gdp, deficit_gdp_prev, debt_gdp, debt_gdp_prev,
            interest_gdp, interest_gdp_prev
        """
        result = {}

        # Federal Deficit as % of GDP (annual, negative = deficit)
        deficit_s = self.get_fred_series('FYFSGDA188S', resample=None)
        if deficit_s is not None and len(deficit_s) >= 2:
            result['deficit_gdp'] = round(float(deficit_s.iloc[-1]), 1)
            result['deficit_gdp_prev'] = round(float(deficit_s.iloc[-2]), 1)

        # Federal Debt: Total Public Debt as % of GDP (quarterly)
        debt_s = self.get_fred_series('GFDEGDQ188S', resample=None)
        if debt_s is not None and len(debt_s) >= 2:
            result['debt_gdp'] = round(float(debt_s.iloc[-1]), 1)
            result['debt_gdp_prev'] = round(float(debt_s.iloc[-2]), 1)

        # Interest payments as % of GDP (quarterly)
        interest_s = self.get_fred_series('FYOIGDA188S', resample=None)
        if interest_s is not None and len(interest_s) >= 2:
            result['interest_gdp'] = round(float(interest_s.iloc[-1]), 1)
            result['interest_gdp_prev'] = round(float(interest_s.iloc[-2]), 1)

        return result

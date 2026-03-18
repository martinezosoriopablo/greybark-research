# -*- coding: utf-8 -*-
"""
Greybark Research — NY Fed Markets API Client
===============================================

Federal Reserve Bank of New York Markets Data.
Free, no API key required.

Reference Rates (daily, JSON API):
- SOFR (Secured Overnight Financing Rate)
- EFFR (Effective Federal Funds Rate)
- OBFR (Overnight Bank Funding Rate)
- TGCR (Tri-Party General Collateral Rate)
- BGCR (Broad General Collateral Rate)
- SOFRAI (SOFR Average Index)

Research Data (Excel downloads from NY Fed):
- GSCPI (Global Supply Chain Pressure Index, monthly)
- R-star (Natural Rate of Interest, quarterly)

Term Premia sourced via FRED (ACM model, daily):
- THREEFYTP10 (10Y), THREEFYTP5 (5Y), THREEFYTP2 (2Y), THREEFYTP1 (1Y)

Usage:
    from greybark.data_sources.nyfed_client import NYFedClient

    nyfed = NYFedClient()
    rates = nyfed.get_reference_rates()
    sofr = nyfed.get_sofr_detail()
    gscpi = nyfed.get_gscpi()
    rstar = nyfed.get_rstar()
    premia = nyfed.get_term_premia()
    dash = nyfed.get_full_dashboard()
"""

import io
import logging
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    import pandas as pd
except ImportError:
    pd = None

logger = logging.getLogger(__name__)

# JSON API endpoints
RATES_BASE = "https://markets.newyorkfed.org/api"
RATES_ALL_LATEST = f"{RATES_BASE}/rates/all/latest.json"
SOFR_LAST_N = f"{RATES_BASE}/rates/secured/sofr/last/{{n}}.json"
EFFR_LAST_N = f"{RATES_BASE}/rates/unsecured/effr/last/{{n}}.json"

# Excel download URLs for research data
GSCPI_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
RSTAR_URL = "https://www.newyorkfed.org/medialibrary/media/research/economists/williams/data/Laubach_Williams_current_estimates.xlsx"

# ACM Term Premia via FRED (NY Fed Excel URL is broken)
TERM_PREMIA_FRED = {
    'tp_1y': 'THREEFYTP1',
    'tp_2y': 'THREEFYTP2',
    'tp_5y': 'THREEFYTP5',
    'tp_10y': 'THREEFYTP10',
}


class NYFedClient:
    """Client for NY Fed Markets API and research data."""

    def __init__(self):
        if requests is None:
            raise ImportError("requests is required: pip install requests")

    # =========================================================================
    # REFERENCE RATES (JSON API)
    # =========================================================================

    def get_reference_rates(self) -> Dict[str, Any]:
        """Fetch all reference rates (latest values).

        Returns:
            Dict with SOFR, EFFR, OBFR, TGCR, BGCR, SOFRAI
            Each: {rate, date, percentile_25th, percentile_75th, volume}
        """
        try:
            resp = requests.get(RATES_ALL_LATEST, timeout=15)
            if resp.status_code != 200:
                logger.error(f"NY Fed rates API error: {resp.status_code}")
                return {}

            data = resp.json()
            result = {}

            # Parse reference rates from response
            for rate_data in data.get('refRates', []):
                rate_type = rate_data.get('type', '')
                entry = {
                    'rate': _safe_float(rate_data.get('percentRate')),
                    'date': rate_data.get('effectiveDate'),
                    'percentile_25th': _safe_float(rate_data.get('percentPercentile25')),
                    'percentile_75th': _safe_float(rate_data.get('percentPercentile75')),
                    'volume_billions': _safe_float(rate_data.get('volumeInBillions')),
                }
                result[rate_type.lower()] = entry

            result['_source'] = 'NYFed:ReferenceRates'
            return result

        except Exception as e:
            logger.error(f"NY Fed reference rates error: {e}")
            return {}

    def get_sofr_detail(self, n_days: int = 30) -> Dict[str, Any]:
        """Fetch SOFR detail with history.

        Args:
            n_days: Number of recent business days

        Returns:
            Dict with latest SOFR, history, and volume info
        """
        try:
            url = SOFR_LAST_N.format(n=n_days)
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                logger.error(f"NY Fed SOFR API error: {resp.status_code}")
                return {}

            data = resp.json()
            rates = data.get('refRates', [])
            if not rates:
                return {}

            # Latest
            latest = rates[0]
            result = {
                'rate': _safe_float(latest.get('percentRate')),
                'date': latest.get('effectiveDate'),
                'percentile_1st': _safe_float(latest.get('percentPercentile1')),
                'percentile_25th': _safe_float(latest.get('percentPercentile25')),
                'percentile_75th': _safe_float(latest.get('percentPercentile75')),
                'percentile_99th': _safe_float(latest.get('percentPercentile99')),
                'volume_billions': _safe_float(latest.get('volumeInBillions')),
                'history': [],
            }

            for r in rates:
                result['history'].append({
                    'date': r.get('effectiveDate'),
                    'rate': _safe_float(r.get('percentRate')),
                    'volume': _safe_float(r.get('volumeInBillions')),
                })

            result['_source'] = 'NYFed:SOFR'
            return result

        except Exception as e:
            logger.error(f"NY Fed SOFR detail error: {e}")
            return {}

    # =========================================================================
    # RESEARCH DATA (Excel downloads)
    # =========================================================================

    def get_gscpi(self, months: int = 120) -> Dict[str, Any]:
        """Global Supply Chain Pressure Index (monthly time series).

        Measures global supply chain conditions.
        0 = historical average, positive = pressures above average.

        Args:
            months: Number of months of history to return (default 36)

        Returns:
            {value, date, trend, history: [{date, value}, ...], _source}
        """
        if pd is None:
            logger.error("pandas required for GSCPI Excel parsing")
            return {}

        try:
            resp = requests.get(GSCPI_URL, timeout=30)
            if resp.status_code != 200:
                logger.error(f"GSCPI download error: {resp.status_code}")
                return {}

            # File is old .xls format (OLE2), sheet "GSCPI Monthly Data"
            df = pd.read_excel(
                io.BytesIO(resp.content),
                sheet_name='GSCPI Monthly Data',
                engine='xlrd',
            )
            # Columns: Date, GSCPI (+ some unnamed)
            df = df[['Date', 'GSCPI']].dropna(subset=['GSCPI'])
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')

            # Take last N months
            df = df.tail(months)

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else None

            # Build history list
            history = []
            for _, row in df.iterrows():
                history.append({
                    'date': row['Date'].strftime('%Y-%m'),
                    'value': round(float(row['GSCPI']), 2),
                })

            result = {
                'value': round(float(latest['GSCPI']), 2),
                'date': latest['Date'].strftime('%Y-%m'),
                'history': history,
                '_source': 'NYFed:GSCPI',
            }

            if prev is not None:
                result['prev_value'] = round(float(prev['GSCPI']), 2)
                result['prev_date'] = prev['Date'].strftime('%Y-%m')
                result['trend'] = 'rising' if result['value'] > result['prev_value'] else 'falling'

            return result

        except Exception as e:
            logger.error(f"NY Fed GSCPI error: {e}")
            return {}

    def get_rstar(self, quarters: int = 40) -> Dict[str, Any]:
        """Natural Rate of Interest / R-star (Laubach-Williams, quarterly).

        Estimated real short-term interest rate consistent with
        full employment and stable inflation.

        Args:
            quarters: Number of quarters of history to return (default 20 = 5 years)

        Returns:
            {value, date, trend_growth, history: [{date, rstar, trend_growth}, ...], _source}
        """
        if pd is None:
            logger.error("pandas required for R-star Excel parsing")
            return {}

        try:
            resp = requests.get(RSTAR_URL, timeout=30)
            if resp.status_code != 200:
                logger.error(f"R-star download error: {resp.status_code}")
                return {}

            # Sheet "data": rows 0-4=description, row 5=headers, row 6+=data
            # Col 0=Date, 1=blank, 2=rstar(one-sided), 3=g(one-sided),
            # 7=rstar(two-sided), 8=g(two-sided)
            # Use two-sided estimates (more accurate for recent quarters)
            df = pd.read_excel(
                io.BytesIO(resp.content),
                sheet_name='data',
                header=None,
                skiprows=6,
                engine='openpyxl',
            )
            date_col = 0
            rstar_col = 7   # two-sided rstar
            trend_col = 8   # two-sided trend growth

            df = df.dropna(subset=[rstar_col])
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(date_col)

            # Take last N quarters
            df = df.tail(quarters)

            latest = df.iloc[-1]
            q = (latest[date_col].month - 1) // 3 + 1

            # Build history
            history = []
            for _, row in df.iterrows():
                qr = (row[date_col].month - 1) // 3 + 1
                history.append({
                    'date': f"{row[date_col].year}-Q{qr}",
                    'rstar': round(float(row[rstar_col]), 2),
                    'trend_growth': round(float(row[trend_col]), 2),
                })

            result = {
                'value': round(float(latest[rstar_col]), 2),
                'date': f"{latest[date_col].year}-Q{q}",
                'trend_growth': round(float(latest[trend_col]), 2),
                'history': history,
                '_source': 'NYFed:Rstar',
            }

            return result

        except Exception as e:
            logger.error(f"NY Fed R-star error: {e}")
            return {}

    def get_term_premia(self, months: int = 120) -> Dict[str, Any]:
        """Treasury Term Premia (ACM model, daily via FRED).

        Estimated term premium for 1Y, 2Y, 5Y, 10Y maturities.
        Uses Adrian-Crump-Moench model. Data from FRED.

        Args:
            months: Months of history to return (default 24)

        Returns:
            {tp_1y, tp_2y, tp_5y, tp_10y, date,
             history: {tp_10y: [{date, value}, ...], ...}, _source}
        """
        try:
            from ..config import config
            from fredapi import Fred
            from datetime import date as date_cls, timedelta
            fred = Fred(api_key=config.fred.api_key)

            start = date_cls.today() - timedelta(days=months * 30)
            result = {'_source': 'FRED:ACMTermPremia', 'history': {}}
            latest_date = None

            for key, series_id in TERM_PREMIA_FRED.items():
                try:
                    s = fred.get_series(series_id, observation_start=start).dropna()
                    if len(s) > 0:
                        result[key] = round(float(s.iloc[-1]), 4)
                        if latest_date is None:
                            latest_date = s.index[-1].strftime('%Y-%m-%d')

                        # Monthly averages for history (daily is too much)
                        monthly = s.resample('ME').mean().dropna()
                        result['history'][key] = [
                            {'date': idx.strftime('%Y-%m'),
                             'value': round(float(val), 4)}
                            for idx, val in monthly.items()
                        ]
                except Exception:
                    pass

            result['date'] = latest_date
            return result

        except Exception as e:
            logger.error(f"Term Premia error: {e}")
            return {}

    # =========================================================================
    # DASHBOARD
    # =========================================================================

    def get_full_dashboard(self) -> Dict[str, Any]:
        """Fetch all NY Fed data.

        Returns:
            Dict with all sections: reference_rates, sofr_detail,
            gscpi, rstar, term_premia
        """
        return {
            'reference_rates': self.get_reference_rates(),
            'sofr_detail': self.get_sofr_detail(),
            'gscpi': self.get_gscpi(),
            'rstar': self.get_rstar(),
            'term_premia': self.get_term_premia(),
        }


def _safe_float(val) -> Optional[float]:
    """Convert to float safely, return None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def main():
    """Test NY Fed client."""
    client = NYFedClient()

    print("=== Reference Rates ===")
    rates = client.get_reference_rates()
    for k, v in rates.items():
        if k != '_source':
            print(f"  {k}: rate={v.get('rate')}%, vol=${v.get('volume_billions', 'N/A')}B")

    print("\n=== SOFR Detail ===")
    sofr = client.get_sofr_detail()
    if sofr:
        print(f"  Rate: {sofr.get('rate')}%")
        print(f"  Date: {sofr.get('date')}")
        print(f"  Volume: ${sofr.get('volume_billions')}B")
        print(f"  Range: P1={sofr.get('percentile_1st')} - P99={sofr.get('percentile_99th')}")

    print("\n=== GSCPI ===")
    gscpi = client.get_gscpi()
    if gscpi:
        print(f"  Value: {gscpi.get('value')} ({gscpi.get('date')})")
        print(f"  Prev: {gscpi.get('prev_value')} ({gscpi.get('prev_date')})")
        print(f"  Trend: {gscpi.get('trend')}")

    print("\n=== R-star ===")
    rstar = client.get_rstar()
    if rstar:
        print(f"  R-star: {rstar.get('value')}% ({rstar.get('date')})")
        print(f"  Trend growth: {rstar.get('trend_growth')}%")

    print("\n=== Term Premia ===")
    tp = client.get_term_premia()
    if tp:
        print(f"  Date: {tp.get('date')}")
        for m in ['tp_1y', 'tp_2y', 'tp_5y', 'tp_7y', 'tp_10y']:
            if m in tp:
                print(f"  {m}: {tp[m]}%")


if __name__ == "__main__":
    main()

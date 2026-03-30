"""
Grey Bark - FRED API Client
Federal Reserve Economic Data

Includes Fed Dots (Summary of Economic Projections)
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Union
import pandas as pd

try:
    from fredapi import Fred
except ImportError:
    raise ImportError("Please install fredapi: pip install fredapi")

from ..config import config, FREDSeries


class FREDClient:
    """
    Client for FRED (Federal Reserve Economic Data) API
    
    Usage:
        client = FREDClient()
        
        # Single series
        data = client.get_series('DGS10')
        
        # Multiple series
        data = client.get_multiple_series(['DGS2', 'DGS10'])
        
        # Fed Dots
        dots = client.get_fed_dots()
    """
    
    def __init__(self, api_key: str = None, timeout: int = 30):
        """Initialize FRED client with request timeout."""
        self.api_key = api_key or config.fred.api_key
        self._client = Fred(api_key=self.api_key)
        # Patch fredapi's internal session to enforce timeout
        import requests as _req
        _session = _req.Session()
        _original_get = _session.get
        def _get_with_timeout(*args, **kwargs):
            kwargs.setdefault('timeout', timeout)
            return _original_get(*args, **kwargs)
        _session.get = _get_with_timeout
        if hasattr(self._client, 'session'):
            self._client.session = _session
    
    def get_series(self, 
                   series_id: str, 
                   start_date: date = None,
                   end_date: date = None) -> pd.Series:
        """
        Fetch a single series from FRED
        
        Args:
            series_id: FRED series ID (e.g., 'DGS10')
            start_date: Start date (default: 5 years ago)
            end_date: End date (default: today)
        
        Returns:
            pandas Series with the data
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365*5)
        
        try:
            data = self._client.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date
            )
            return data
        except Exception as e:
            print(f"[FRED] Error fetching {series_id}: {e}")
            raise
    
    def get_multiple_series(self, 
                            series_ids: List[str],
                            start_date: date = None,
                            end_date: date = None) -> Dict[str, pd.Series]:
        """
        Fetch multiple series from FRED
        
        Args:
            series_ids: List of FRED series IDs
            start_date: Start date
            end_date: End date
        
        Returns:
            Dict mapping series_id to pandas Series
        """
        result = {}
        for series_id in series_ids:
            try:
                result[series_id] = self.get_series(series_id, start_date, end_date)
            except Exception as e:
                print(f"[FRED] Skipping {series_id}: {e}")
        return result
    
    def get_latest_value(self, series_id: str) -> Optional[float]:
        """Get the most recent value for a series"""
        data = self.get_series(series_id)
        if data is not None and len(data) > 0:
            return float(data.iloc[-1])
        return None
    
    # =========================================================================
    # FED DOTS (Summary of Economic Projections)
    # =========================================================================
    
    def get_fed_dots(self) -> Dict:
        """
        Fetch Fed Dots (FOMC Summary of Economic Projections)
        
        Returns:
            Dict with:
                - by_year: Dict[int, float] - Median projection by year
                - longer_run: float - Longer run median
                - range: Dict[int, Dict] - High/low range by year
                - longer_run_range: Dict - High/low longer run
                - last_updated: str - Date of last update
        """
        print("[FRED] Fetching Fed Dots...")
        
        dots = {
            'by_year': {},
            'longer_run': None,
            'range': {},
            'longer_run_range': {},
            'last_updated': None
        }
        
        try:
            # Median by year
            median_data = self._client.get_series(FREDSeries.FED_DOTS_MEDIAN)
            if median_data is not None and len(median_data) > 0:
                dots['last_updated'] = median_data.index[-1].strftime('%Y-%m-%d')
                
                # Get last 5 observations (current projections)
                recent = median_data.tail(5)
                for proj_date, value in recent.items():
                    year = proj_date.year
                    if year >= date.today().year:
                        dots['by_year'][year] = round(float(value), 3)
                        print(f"  ✓ {year}: {value:.3f}%")
            
            # Longer run median
            lr_data = self._client.get_series(FREDSeries.FED_DOTS_MEDIAN_LR)
            if lr_data is not None and len(lr_data) > 0:
                dots['longer_run'] = round(float(lr_data.iloc[-1]), 3)
                print(f"  ✓ Longer Run: {dots['longer_run']:.3f}%")
            
            # Range (high/low)
            try:
                range_high = self._client.get_series(FREDSeries.FED_DOTS_RANGE_HIGH)
                range_low = self._client.get_series(FREDSeries.FED_DOTS_RANGE_LOW)
                
                if range_high is not None and range_low is not None:
                    for proj_date, high_val in range_high.tail(5).items():
                        year = proj_date.year
                        if year >= date.today().year:
                            dots['range'][year] = {
                                'high': round(float(high_val), 3)
                            }
                    
                    for proj_date, low_val in range_low.tail(5).items():
                        year = proj_date.year
                        if year in dots['range']:
                            dots['range'][year]['low'] = round(float(low_val), 3)
            except:
                pass
            
            # Longer run range
            try:
                lr_high = self._client.get_series(FREDSeries.FED_DOTS_RANGE_HIGH_LR)
                lr_low = self._client.get_series(FREDSeries.FED_DOTS_RANGE_LOW_LR)
                
                if lr_high is not None and lr_low is not None:
                    dots['longer_run_range'] = {
                        'high': round(float(lr_high.iloc[-1]), 3),
                        'low': round(float(lr_low.iloc[-1]), 3)
                    }
                    print(f"  ✓ LR Range: {dots['longer_run_range']['low']:.2f}% - {dots['longer_run_range']['high']:.2f}%")
            except:
                pass
            
            print(f"[FRED] ✓ Fed Dots fetched (last update: {dots['last_updated']})")
            return dots
            
        except Exception as e:
            print(f"[FRED] ✗ Error fetching Fed Dots: {e}")
            raise
    
    # =========================================================================
    # REGIME CLASSIFICATION SERIES
    # =========================================================================
    
    def get_regime_indicators(self) -> Dict[str, pd.Series]:
        """
        Fetch all FRED series needed for regime classification
        
        Returns:
            Dict with series for yield curve, HY spreads, confidence, etc.
        """
        series_ids = [
            FREDSeries.TREASURY_2Y,
            FREDSeries.TREASURY_10Y,
            FREDSeries.HY_SPREADS,
            FREDSeries.CONSUMER_CONFIDENCE,
            FREDSeries.ISM_NEW_ORDERS,
            FREDSeries.M2_MONEY_SUPPLY,
            FREDSeries.INITIAL_CLAIMS,
        ]
        
        return self.get_multiple_series(series_ids)
    
    def get_yield_curve_spread(self) -> Optional[float]:
        """Calculate 2s10s yield curve spread in basis points"""
        try:
            dgs2 = self.get_latest_value(FREDSeries.TREASURY_2Y)
            dgs10 = self.get_latest_value(FREDSeries.TREASURY_10Y)

            if dgs2 is not None and dgs10 is not None:
                return round((dgs10 - dgs2) * 100, 1)  # Convert to bp
            return None
        except Exception as e:
            print(f"[FRED] Error calculating yield curve: {e}")
            return None

    # =========================================================================
    # US MACRO DASHBOARD
    # =========================================================================

    def get_us_macro_dashboard(self) -> Dict:
        """
        Fetch comprehensive US macro indicators

        Series:
        - GDPC1: Real GDP (quarterly)
        - UNRATE: Unemployment Rate (monthly)
        - PAYEMS: Nonfarm Payrolls (monthly)
        - RSXFS: Retail Sales ex Food Services (monthly)
        - INDPRO: Industrial Production (monthly)
        - HOUST: Housing Starts (monthly)
        - DGORDER: Durable Goods Orders (monthly)

        Returns:
            Dict with macro indicators and their changes
        """
        print("[FRED] Fetching US Macro Dashboard...")

        dashboard = {
            'gdp': None,
            'unemployment': None,
            'payrolls': None,
            'retail_sales': None,
            'industrial_prod': None,
            'housing_starts': None,
            'durable_goods': None,
            'timestamp': None
        }

        from datetime import datetime
        dashboard['timestamp'] = datetime.now().isoformat()

        # GDP (GDPC1) - Real GDP, quarterly, seasonally adjusted
        try:
            gdp = self.get_series('GDPC1')
            if gdp is not None and len(gdp) >= 2:
                current = gdp.iloc[-1]
                prev = gdp.iloc[-2]
                # QoQ annualized growth rate
                qoq_change = ((current / prev) ** 4 - 1) * 100

                # Determine quarter
                last_date = gdp.index[-1]
                quarter = f"Q{(last_date.month - 1) // 3 + 1} {last_date.year}"

                dashboard['gdp'] = {
                    'value': round(qoq_change, 1),
                    'period': quarter,
                    'qoq_change': round(qoq_change, 1),
                    'level_billions': round(current / 1000, 1)
                }
                print(f"  ✓ GDP: {qoq_change:.1f}% ({quarter})")
        except Exception as e:
            print(f"  ✗ GDP error: {e}")

        # Unemployment (UNRATE)
        try:
            unrate = self.get_series('UNRATE')
            if unrate is not None and len(unrate) >= 2:
                current = unrate.iloc[-1]
                prev = unrate.iloc[-2]

                # Trend determination
                if current < prev - 0.1:
                    trend = 'falling'
                elif current > prev + 0.1:
                    trend = 'rising'
                else:
                    trend = 'stable'

                dashboard['unemployment'] = {
                    'value': round(current, 1),
                    'prev': round(prev, 1),
                    'trend': trend
                }
                print(f"  ✓ Unemployment: {current:.1f}% (prev: {prev:.1f}%)")
        except Exception as e:
            print(f"  ✗ Unemployment error: {e}")

        # Nonfarm Payrolls (PAYEMS) - Total nonfarm, thousands
        try:
            payems = self.get_series('PAYEMS')
            if payems is not None and len(payems) >= 2:
                current = payems.iloc[-1]
                prev = payems.iloc[-2]
                # Monthly change in thousands
                change_k = current - prev

                dashboard['payrolls'] = {
                    'value': round(change_k, 0),
                    'unit': 'K',
                    'prev': round(payems.iloc[-2] - payems.iloc[-3], 0) if len(payems) >= 3 else None,
                    'total_millions': round(current / 1000, 1)
                }
                print(f"  ✓ Payrolls: {change_k:+.0f}K")
        except Exception as e:
            print(f"  ✗ Payrolls error: {e}")

        # Retail Sales ex Food Services (RSXFS)
        try:
            retail = self.get_series('RSXFS')
            if retail is not None and len(retail) >= 13:
                current = retail.iloc[-1]
                prev = retail.iloc[-2]
                year_ago = retail.iloc[-13]

                mom = ((current / prev) - 1) * 100
                yoy = ((current / year_ago) - 1) * 100

                dashboard['retail_sales'] = {
                    'value': round(mom, 1),
                    'unit': '%mom',
                    'yoy': round(yoy, 1)
                }
                print(f"  ✓ Retail Sales: {mom:+.1f}% MoM, {yoy:+.1f}% YoY")
        except Exception as e:
            print(f"  ✗ Retail Sales error: {e}")

        # Industrial Production (INDPRO)
        try:
            indpro = self.get_series('INDPRO')
            if indpro is not None and len(indpro) >= 2:
                current = indpro.iloc[-1]
                prev = indpro.iloc[-2]
                mom = ((current / prev) - 1) * 100

                dashboard['industrial_prod'] = {
                    'value': round(mom, 1),
                    'unit': '%mom',
                    'index': round(current, 1)
                }
                print(f"  ✓ Industrial Production: {mom:+.1f}% MoM")
        except Exception as e:
            print(f"  ✗ Industrial Production error: {e}")

        # Housing Starts (HOUST) - Thousands, SAAR
        try:
            houst = self.get_series('HOUST')
            if houst is not None and len(houst) >= 2:
                current = houst.iloc[-1]
                prev = houst.iloc[-2]
                mom_change = ((current / prev) - 1) * 100

                dashboard['housing_starts'] = {
                    'value': round(current / 1000, 2),
                    'unit': 'M',
                    'mom_change': round(mom_change, 1)
                }
                print(f"  ✓ Housing Starts: {current/1000:.2f}M ({mom_change:+.1f}% MoM)")
        except Exception as e:
            print(f"  ✗ Housing Starts error: {e}")

        # Durable Goods Orders (DGORDER)
        try:
            durable = self.get_series('DGORDER')
            if durable is not None and len(durable) >= 2:
                current = durable.iloc[-1]
                prev = durable.iloc[-2]
                mom = ((current / prev) - 1) * 100

                dashboard['durable_goods'] = {
                    'value': round(mom, 1),
                    'unit': '%mom'
                }
                print(f"  ✓ Durable Goods: {mom:+.1f}% MoM")
        except Exception as e:
            print(f"  ✗ Durable Goods error: {e}")

        print(f"[FRED] ✓ US Macro Dashboard complete")
        return dashboard

    # =========================================================================
    # LEADING INDICATORS
    # =========================================================================

    def get_leading_indicators(self) -> Dict:
        """
        Fetch leading economic indicators from FRED.

        Series:
        - ICSA: Initial Jobless Claims (weekly)
        - UMCSENT: U. Michigan Consumer Sentiment (monthly)
        - NEWORDER: Manufacturers' New Orders (monthly)
        - PERMIT: Building Permits (monthly)
        - T10Y3M: 10Y-3M Treasury Spread (daily)

        Returns:
            Dict with latest values for each indicator
        """
        print("[FRED] Fetching Leading Indicators...")
        indicators = {'timestamp': None}

        from datetime import datetime
        indicators['timestamp'] = datetime.now().isoformat()

        series_map = {
            'initial_claims': 'ICSA',
            'consumer_sentiment': 'UMCSENT',
            'new_orders': 'NEWORDER',
            'building_permits': 'PERMIT',
            'yield_spread_10y3m': 'T10Y3M',
        }

        for key, sid in series_map.items():
            try:
                val = self.get_latest_value(sid)
                indicators[key] = val
                if val is not None:
                    print(f"  ✓ {key}: {val:.1f}")
            except Exception as e:
                indicators[key] = None
                print(f"  ✗ {key}: {e}")

        print("[FRED] ✓ Leading Indicators complete")
        return indicators

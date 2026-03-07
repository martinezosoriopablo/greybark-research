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
    
    def __init__(self, api_key: str = None):
        """Initialize FRED client"""
        self.api_key = api_key or config.fred.api_key
        self._client = Fred(api_key=self.api_key)
    
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
            start_date = end_date - timedelta(days=365*10)
        
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

    def get_leading_indicators(self) -> Dict:
        """
        Fetch leading economic indicators for USA and Eurozone.

        Series:
        - USALOLITOAASTSAM: OECD CLI USA Amplitude Adjusted (monthly)
        - BSCICP02EZM460S: OECD Business Confidence Euro Area (monthly, leading proxy)
        - CSCICP02EZM460S: Consumer Confidence Euro Area (monthly)
        - CFNAI: Chicago Fed National Activity Index (monthly)
        - UMCSENT: U Michigan Consumer Sentiment (monthly)

        Returns:
            Dict with leading indicators, levels, and trends
        """
        print("[FRED] Fetching Leading Indicators...")

        result = {
            'lei_usa': None,
            'lei_eurozone': None,
            'consumer_confidence_ez': None,
            'cfnai': None,
            'umich_sentiment': None,
            'timestamp': None,
        }

        from datetime import datetime
        result['timestamp'] = datetime.now().isoformat()

        # OECD CLI USA Amplitude Adjusted
        try:
            cli = self.get_series(FREDSeries.LEADING_INDEX_OECD)
            if cli is not None and len(cli) >= 2:
                current = cli.iloc[-1]
                prev = cli.iloc[-2]
                last_date = cli.index[-1]
                trend = 'expanding' if current > 100 else 'contracting'
                result['lei_usa'] = {
                    'value': round(current, 2),
                    'prev': round(prev, 2),
                    'change': round(current - prev, 2),
                    'trend': trend,
                    'period': last_date.strftime('%Y-%m'),
                    'source': 'FRED:USALOLITOAASTSAM',
                }
                print(f"  ✓ LEI USA (OECD CLI): {current:.2f} ({trend})")
        except Exception as e:
            print(f"  ✗ LEI USA error: {e}")

        # OECD Business Confidence Euro Area (leading proxy)
        try:
            bci = self.get_series(FREDSeries.LEADING_INDEX_EZ)
            if bci is not None and len(bci) >= 2:
                current = bci.iloc[-1]
                prev = bci.iloc[-2]
                last_date = bci.index[-1]
                trend = 'expanding' if current > 100 else 'contracting'
                result['lei_eurozone'] = {
                    'value': round(current, 2),
                    'prev': round(prev, 2),
                    'change': round(current - prev, 2),
                    'trend': trend,
                    'period': last_date.strftime('%Y-%m'),
                    'source': 'FRED:BSCICP02EZM460S',
                }
                print(f"  ✓ LEI Eurozone (Biz Conf): {current:.2f} ({trend})")
        except Exception as e:
            print(f"  ✗ LEI Eurozone error: {e}")

        # Consumer Confidence Euro Area
        try:
            cci = self.get_series(FREDSeries.CONSUMER_CONFIDENCE_EZ)
            if cci is not None and len(cci) >= 2:
                current = cci.iloc[-1]
                prev = cci.iloc[-2]
                last_date = cci.index[-1]
                result['consumer_confidence_ez'] = {
                    'value': round(current, 1),
                    'prev': round(prev, 1),
                    'change': round(current - prev, 1),
                    'period': last_date.strftime('%Y-%m'),
                    'source': 'FRED:CSCICP02EZM460S',
                }
                print(f"  ✓ Consumer Conf EZ: {current:.1f}")
        except Exception as e:
            print(f"  ✗ Consumer Conf EZ error: {e}")

        # Chicago Fed National Activity Index
        try:
            cfnai = self.get_series('CFNAI')
            if cfnai is not None and len(cfnai) >= 2:
                current = cfnai.iloc[-1]
                prev = cfnai.iloc[-2]
                last_date = cfnai.index[-1]
                # CFNAI: 0 = trend growth, negative = below trend
                trend = 'above_trend' if current > 0 else 'below_trend'
                result['cfnai'] = {
                    'value': round(current, 2),
                    'prev': round(prev, 2),
                    'trend': trend,
                    'period': last_date.strftime('%Y-%m'),
                    'source': 'FRED:CFNAI',
                }
                print(f"  ✓ CFNAI: {current:.2f} ({trend})")
        except Exception as e:
            print(f"  ✗ CFNAI error: {e}")

        # U Michigan Consumer Sentiment
        try:
            umich = self.get_series(FREDSeries.UMICH_SENTIMENT)
            if umich is not None and len(umich) >= 2:
                current = umich.iloc[-1]
                prev = umich.iloc[-2]
                last_date = umich.index[-1]
                result['umich_sentiment'] = {
                    'value': round(current, 1),
                    'prev': round(prev, 1),
                    'change': round(current - prev, 1),
                    'period': last_date.strftime('%Y-%m'),
                    'source': 'FRED:UMCSENT',
                }
                print(f"  ✓ U.Mich Sentiment: {current:.1f}")
        except Exception as e:
            print(f"  ✗ U.Mich error: {e}")

        print("[FRED] ✓ Leading Indicators complete")
        return result

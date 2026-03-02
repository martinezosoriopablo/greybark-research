"""
Greybark Research - China Credit Impulse Module
Mejora #8 del AI Council

Provides China macro/credit analysis using available data sources:
- China EPU (Economic Policy Uncertainty) from BCCh
- Copper as China demand proxy
- Iron Ore as construction proxy
- FRED China-related series
- FXI/MCHI ETF performance

Note: Direct PBOC credit data requires Bloomberg/Reuters.
This module uses proxy indicators available through our APIs.

Author: Greybark Research
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from data_sources.bcch_client import BCChClient
    from data_sources.fred_client import FREDClient
except ImportError:
    from greybark.data_sources.bcch_client import BCChClient
    from greybark.data_sources.fred_client import FREDClient


# =============================================================================
# SERIES CODES
# =============================================================================

class ChinaSeries:
    """Available China-related series"""
    
    # BCCh Series
    CHINA_EPU = "F019.EPU.IND.CHN.M"      # China Economic Policy Uncertainty
    COPPER_PRICE = "F019.PPB.PRE.40.M"    # Copper (China demand proxy)
    
    # FRED Series
    CHINA_GDP = "MKTGDPCNA646NWDB"        # China GDP (World Bank, annual)
    CHINA_CPI = "CHNCPIALLMINMEI"         # China CPI
    CHINA_EXPORTS = "XTEXVA01CNM667S"     # China Exports
    CHINA_IMPORTS = "XTIMVA01CNM667S"     # China Imports
    CHINA_PMI_MFG = "CHNPMIMMR"           # China PMI Manufacturing (if available)
    
    # Commodity proxies (FRED)
    IRON_ORE = "PIORECRUSDM"              # Iron Ore Price (China demand proxy)
    
    # Yahoo Finance ETFs
    FXI = "FXI"                           # iShares China Large-Cap ETF
    MCHI = "MCHI"                         # iShares MSCI China ETF
    KWEB = "KWEB"                         # KraneShares China Internet ETF


class ChinaSignal(Enum):
    """China credit impulse signals"""
    EXPANSION = "expansion"      # Credit expanding, growth positive
    NEUTRAL = "neutral"          # Credit stable
    CONTRACTION = "contraction"  # Credit tightening
    UNKNOWN = "unknown"


# =============================================================================
# MAIN CLASS
# =============================================================================

class ChinaCreditAnalytics:
    """
    China Credit Impulse Analytics
    
    Uses proxy indicators to estimate China credit/growth conditions:
    - EPU (Economic Policy Uncertainty)
    - Commodity prices (copper, iron ore)
    - Trade data (exports/imports)
    - China ETF performance
    
    Note: For true credit impulse, Bloomberg/Reuters data required.
    This provides directional signals from available data.
    
    Usage:
        analytics = ChinaCreditAnalytics()
        
        # Get China dashboard
        dashboard = analytics.get_china_dashboard()
        
        # Get credit impulse proxy
        impulse = analytics.get_credit_impulse_proxy()
    """
    
    def __init__(self, bcch_user: str = None, bcch_password: str = None,
                 fred_api_key: str = None):
        """Initialize with API credentials"""
        self.bcch = BCChClient(user=bcch_user, password=bcch_password)
        self.fred = FREDClient(api_key=fred_api_key)
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    def _get_china_epu(self, lookback_months: int = 24) -> Optional[pd.Series]:
        """Fetch China EPU from BCCh"""
        try:
            data = self.bcch.get_series(
                ChinaSeries.CHINA_EPU,
                days_back=lookback_months * 31
            )
            return data
        except Exception as e:
            print(f"  ✗ Error fetching China EPU: {e}")
            return None
    
    def _get_copper(self, lookback_months: int = 24) -> Optional[pd.Series]:
        """Fetch copper price from BCCh"""
        try:
            data = self.bcch.get_series(
                ChinaSeries.COPPER_PRICE,
                days_back=lookback_months * 31
            )
            return data
        except Exception as e:
            print(f"  ✗ Error fetching copper: {e}")
            return None
    
    def _get_iron_ore(self, lookback_months: int = 24) -> Optional[pd.Series]:
        """Fetch iron ore price from FRED"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_months * 31)
            
            data = self.fred.get_series(
                ChinaSeries.IRON_ORE,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            return data
        except Exception as e:
            print(f"  ✗ Error fetching iron ore: {e}")
            return None
    
    def _get_china_trade(self, lookback_months: int = 24) -> Dict[str, pd.Series]:
        """Fetch China trade data from FRED"""
        trade_data = {}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_months * 31)
        
        for name, series_id in [('exports', ChinaSeries.CHINA_EXPORTS),
                                 ('imports', ChinaSeries.CHINA_IMPORTS)]:
            try:
                data = self.fred.get_series(
                    series_id,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
                if data is not None:
                    trade_data[name] = data
            except Exception:
                pass
        
        return trade_data
    
    def _get_china_etf_data(self) -> Dict[str, Any]:
        """Fetch China ETF data from Yahoo Finance"""
        try:
            import yfinance as yf
        except ImportError:
            return {'error': 'yfinance not installed'}
        
        etf_data = {}
        
        for ticker in [ChinaSeries.FXI, ChinaSeries.MCHI, ChinaSeries.KWEB]:
            try:
                etf = yf.Ticker(ticker)
                hist = etf.history(period='1y')
                
                if len(hist) > 0:
                    current = hist['Close'].iloc[-1]
                    
                    # Calculate returns
                    ret_1m = (current / hist['Close'].iloc[-21] - 1) * 100 if len(hist) >= 21 else None
                    ret_3m = (current / hist['Close'].iloc[-63] - 1) * 100 if len(hist) >= 63 else None
                    ret_ytd = (current / hist['Close'].iloc[0] - 1) * 100
                    
                    etf_data[ticker] = {
                        'price': round(current, 2),
                        'return_1m': round(ret_1m, 1) if ret_1m else None,
                        'return_3m': round(ret_3m, 1) if ret_3m else None,
                        'return_ytd': round(ret_ytd, 1)
                    }
            except Exception as e:
                print(f"  ✗ Error fetching {ticker}: {e}")
        
        return etf_data
    
    # =========================================================================
    # ANALYSIS METHODS
    # =========================================================================
    
    def get_china_epu_analysis(self) -> Dict[str, Any]:
        """
        Analyze China Economic Policy Uncertainty
        
        Returns:
            Current level, trend, and interpretation
        """
        print("[China] Analyzing EPU...")
        
        epu = self._get_china_epu()
        
        if epu is None or len(epu) < 6:
            return {'error': 'Insufficient EPU data'}
        
        current = epu.iloc[-1]
        avg_12m = epu.tail(12).mean() if len(epu) >= 12 else epu.mean()
        avg_24m = epu.mean()
        
        # Calculate momentum
        if len(epu) >= 3:
            mom_3m = current - epu.iloc[-3]
        else:
            mom_3m = 0
        
        # Determine level
        if current > 200:
            level = 'VERY_HIGH'
            interpretation = 'Extreme policy uncertainty - risk-off for China assets'
        elif current > 150:
            level = 'HIGH'
            interpretation = 'Elevated uncertainty - cautious stance recommended'
        elif current > 100:
            level = 'MODERATE'
            interpretation = 'Normal uncertainty levels'
        else:
            level = 'LOW'
            interpretation = 'Low uncertainty - favorable for risk assets'
        
        # Trend
        if mom_3m > 20:
            trend = 'RISING'
        elif mom_3m < -20:
            trend = 'FALLING'
        else:
            trend = 'STABLE'
        
        return {
            'current': round(current, 1),
            'avg_12m': round(avg_12m, 1),
            'avg_24m': round(avg_24m, 1),
            'level': level,
            'trend': trend,
            'momentum_3m': round(mom_3m, 1),
            'interpretation': interpretation,
            'as_of': datetime.now().isoformat()
        }
    
    def get_commodity_demand_signals(self) -> Dict[str, Any]:
        """
        Analyze commodity prices as China demand proxy
        
        Copper and Iron Ore are key indicators of China industrial demand
        """
        print("[China] Analyzing commodity demand signals...")
        
        signals = {}
        
        # Copper
        copper = self._get_copper()
        if copper is not None and len(copper) >= 6:
            current = copper.iloc[-1]
            avg_6m = copper.tail(6).mean()
            avg_12m = copper.tail(12).mean() if len(copper) >= 12 else copper.mean()
            
            # YoY change
            if len(copper) >= 12:
                yoy = (current / copper.iloc[-12] - 1) * 100
            else:
                yoy = 0
            
            signals['copper'] = {
                'current': round(current, 2),
                'avg_6m': round(avg_6m, 2),
                'yoy_change': round(yoy, 1),
                'signal': 'BULLISH' if yoy > 10 else 'BEARISH' if yoy < -10 else 'NEUTRAL',
                'interpretation': 'Strong industrial demand' if yoy > 10 else 'Weak demand' if yoy < -10 else 'Stable demand'
            }
            print(f"  ✓ Copper: ${current:.2f} ({yoy:+.1f}% YoY)")
        
        # Iron Ore
        iron = self._get_iron_ore()
        if iron is not None and len(iron) >= 6:
            current = iron.iloc[-1]
            avg_6m = iron.tail(6).mean()
            
            if len(iron) >= 12:
                yoy = (current / iron.iloc[-12] - 1) * 100
            else:
                yoy = 0
            
            signals['iron_ore'] = {
                'current': round(current, 2),
                'avg_6m': round(avg_6m, 2),
                'yoy_change': round(yoy, 1),
                'signal': 'BULLISH' if yoy > 15 else 'BEARISH' if yoy < -15 else 'NEUTRAL',
                'interpretation': 'Construction/infrastructure demand strong' if yoy > 15 else 'Weak construction' if yoy < -15 else 'Stable'
            }
            print(f"  ✓ Iron Ore: ${current:.2f} ({yoy:+.1f}% YoY)")
        
        # Composite signal
        commodity_signals = [s['signal'] for s in signals.values()]
        if commodity_signals.count('BULLISH') >= len(commodity_signals) * 0.6:
            composite = 'EXPANSION'
        elif commodity_signals.count('BEARISH') >= len(commodity_signals) * 0.6:
            composite = 'CONTRACTION'
        else:
            composite = 'NEUTRAL'
        
        signals['composite'] = composite
        signals['as_of'] = datetime.now().isoformat()
        
        return signals
    
    def get_trade_analysis(self) -> Dict[str, Any]:
        """
        Analyze China trade data
        
        Exports and imports indicate global demand and domestic consumption
        """
        print("[China] Analyzing trade data...")
        
        trade = self._get_china_trade()
        
        if not trade:
            return {'error': 'Could not fetch trade data'}
        
        analysis = {}
        
        for name, data in trade.items():
            if data is not None and len(data) >= 12:
                current = data.iloc[-1]
                yoy = (current / data.iloc[-12] - 1) * 100 if len(data) >= 12 else 0
                
                analysis[name] = {
                    'current_billions': round(current / 1000, 1),  # Assuming millions
                    'yoy_change': round(yoy, 1),
                    'trend': 'UP' if yoy > 5 else 'DOWN' if yoy < -5 else 'FLAT'
                }
                print(f"  ✓ {name.capitalize()}: {yoy:+.1f}% YoY")
        
        # Trade balance trend
        if 'exports' in analysis and 'imports' in analysis:
            exp_trend = analysis['exports']['yoy_change']
            imp_trend = analysis['imports']['yoy_change']
            
            if imp_trend > exp_trend + 5:
                analysis['balance_signal'] = 'DOMESTIC_STRENGTH'
                analysis['interpretation'] = 'Imports growing faster - domestic demand strong'
            elif exp_trend > imp_trend + 5:
                analysis['balance_signal'] = 'EXPORT_LED'
                analysis['interpretation'] = 'Exports outpacing - global demand driven'
            else:
                analysis['balance_signal'] = 'BALANCED'
                analysis['interpretation'] = 'Balanced trade growth'
        
        analysis['as_of'] = datetime.now().isoformat()
        return analysis
    
    def get_credit_impulse_proxy(self) -> Dict[str, Any]:
        """
        Estimate China credit impulse from available proxies
        
        True credit impulse requires TSF (Total Social Financing) data.
        This provides a proxy using:
        - Commodity demand (copper, iron ore)
        - EPU (policy uncertainty)
        - ETF flows
        
        Returns:
            Estimated credit impulse signal and confidence
        """
        print("[China] Calculating credit impulse proxy...")
        
        # Gather all signals
        epu = self.get_china_epu_analysis()
        commodities = self.get_commodity_demand_signals()
        etfs = self._get_china_etf_data()
        
        signals = []
        
        # EPU signal (inverted - low EPU = positive for credit)
        if 'level' in epu:
            if epu['level'] in ['LOW', 'MODERATE']:
                signals.append(1)  # Positive
            elif epu['level'] == 'VERY_HIGH':
                signals.append(-1)  # Negative
            else:
                signals.append(0)  # Neutral
        
        # Commodity signal
        if commodities.get('composite') == 'EXPANSION':
            signals.append(1)
        elif commodities.get('composite') == 'CONTRACTION':
            signals.append(-1)
        else:
            signals.append(0)
        
        # ETF momentum signal
        etf_returns = []
        for ticker, data in etfs.items():
            if isinstance(data, dict) and 'return_3m' in data and data['return_3m']:
                etf_returns.append(data['return_3m'])
        
        if etf_returns:
            avg_return = np.mean(etf_returns)
            if avg_return > 10:
                signals.append(1)
            elif avg_return < -10:
                signals.append(-1)
            else:
                signals.append(0)
        
        # Calculate composite
        if signals:
            avg_signal = np.mean(signals)
            
            if avg_signal > 0.3:
                impulse = ChinaSignal.EXPANSION
                interpretation = "Credit conditions appear accommodative - positive for growth"
            elif avg_signal < -0.3:
                impulse = ChinaSignal.CONTRACTION
                interpretation = "Credit conditions appear tight - headwind for growth"
            else:
                impulse = ChinaSignal.NEUTRAL
                interpretation = "Credit conditions appear neutral"
        else:
            impulse = ChinaSignal.UNKNOWN
            interpretation = "Insufficient data for assessment"
        
        return {
            'impulse_signal': impulse.value,
            'confidence': 'MODERATE',  # Proxy-based, not direct data
            'interpretation': interpretation,
            'methodology_note': 'Based on proxy indicators (EPU, commodities, ETFs). For true credit impulse, use Bloomberg TSF data.',
            'components': {
                'epu_signal': epu.get('level', 'N/A'),
                'commodity_signal': commodities.get('composite', 'N/A'),
                'etf_momentum': round(np.mean(etf_returns), 1) if etf_returns else 'N/A'
            },
            'as_of': datetime.now().isoformat()
        }
    
    def get_china_dashboard(self) -> Dict[str, Any]:
        """
        Comprehensive China macro dashboard
        
        Combines all available China indicators
        """
        print("=" * 50)
        print("CHINA CREDIT/MACRO DASHBOARD")
        print("=" * 50)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            
            # EPU
            'policy_uncertainty': self.get_china_epu_analysis(),
            
            # Commodities
            'commodity_demand': self.get_commodity_demand_signals(),
            
            # Trade
            'trade': self.get_trade_analysis(),
            
            # ETFs
            'etf_performance': self._get_china_etf_data(),
            
            # Credit impulse proxy
            'credit_impulse': self.get_credit_impulse_proxy(),
            
            # Summary
            'summary': {}
        }
        
        # Generate summary
        dashboard['summary'] = self._generate_summary(dashboard)
        
        return dashboard
    
    def _generate_summary(self, dashboard: Dict) -> Dict:
        """Generate executive summary"""
        summary = {
            'overall_signal': dashboard['credit_impulse'].get('impulse_signal', 'unknown'),
            'key_points': [],
            'investment_implications': []
        }
        
        # EPU insight
        epu = dashboard.get('policy_uncertainty', {})
        if epu.get('level'):
            summary['key_points'].append(f"Policy uncertainty: {epu['level']}")
        
        # Commodity insight
        commodities = dashboard.get('commodity_demand', {})
        if commodities.get('composite'):
            summary['key_points'].append(f"Commodity demand: {commodities['composite']}")
        
        # Investment implications
        impulse = dashboard['credit_impulse'].get('impulse_signal', 'neutral')
        
        if impulse == 'expansion':
            summary['investment_implications'] = [
                "Overweight China/EM equities",
                "Positive for commodities",
                "Consider cyclical sectors"
            ]
        elif impulse == 'contraction':
            summary['investment_implications'] = [
                "Underweight China exposure",
                "Cautious on commodities",
                "Favor defensive sectors"
            ]
        else:
            summary['investment_implications'] = [
                "Neutral China allocation",
                "Monitor for trend change",
                "Selective opportunities"
            ]
        
        return summary


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - CHINA CREDIT ANALYTICS TEST")
    print("=" * 60)
    
    analytics = ChinaCreditAnalytics()
    
    print("\n--- Available Methods ---")
    print("  • get_china_epu_analysis()")
    print("  • get_commodity_demand_signals()")
    print("  • get_trade_analysis()")
    print("  • get_credit_impulse_proxy()")
    print("  • get_china_dashboard()")
    
    print("\n--- Data Sources ---")
    print("  • BCCh: China EPU, Copper")
    print("  • FRED: Iron Ore, Trade data")
    print("  • Yahoo: FXI, MCHI, KWEB ETFs")
    
    print("\n✅ China Credit Analytics module loaded successfully")

"""
Greybark Research - Market Breadth Analytics Module
Mejora #10 del AI Council

Market breadth indicators using available data:
- Sector performance breadth (via ETFs)
- New highs/lows proxy (via sector momentum)
- Risk-on/Risk-off indicator
- Advance/Decline proxy
- McClellan-style oscillator approximation

Data Sources:
- Yahoo Finance (sector ETFs)
- FRED (VIX, credit spreads as risk proxies)

Author: Greybark Research
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# =============================================================================
# SECTOR ETF MAPPINGS
# =============================================================================

class SectorETFs:
    """S&P 500 Sector ETFs (SPDR)"""
    
    # 11 GICS Sectors
    SECTORS = {
        'XLK': 'Technology',
        'XLV': 'Healthcare',
        'XLF': 'Financials',
        'XLY': 'Consumer Discretionary',
        'XLP': 'Consumer Staples',
        'XLE': 'Energy',
        'XLI': 'Industrials',
        'XLB': 'Materials',
        'XLRE': 'Real Estate',
        'XLU': 'Utilities',
        'XLC': 'Communication Services',
    }
    
    # Cyclical vs Defensive
    CYCLICAL = ['XLK', 'XLY', 'XLF', 'XLI', 'XLB', 'XLE']
    DEFENSIVE = ['XLV', 'XLP', 'XLU', 'XLRE']
    
    # Risk-on vs Risk-off pairs
    RISK_ON = ['XLY', 'XLK', 'XLF']   # Consumer Disc, Tech, Financials
    RISK_OFF = ['XLU', 'XLP', 'XLV']  # Utilities, Staples, Healthcare


class MarketETFs:
    """Broad market ETFs"""
    SPY = 'SPY'       # S&P 500
    QQQ = 'QQQ'       # Nasdaq 100
    IWM = 'IWM'       # Russell 2000
    DIA = 'DIA'       # Dow Jones
    VTI = 'VTI'       # Total Market


class BreadthSignal(Enum):
    """Market breadth signals"""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


# =============================================================================
# MAIN CLASS
# =============================================================================

class MarketBreadthAnalytics:
    """
    Market Breadth Analytics
    
    Provides breadth indicators using sector ETFs and market data:
    - Sector participation (how many sectors advancing)
    - Cyclical vs Defensive ratio
    - Risk-on vs Risk-off indicator
    - Equal-weight vs Cap-weight divergence
    - Breadth thrust indicators
    
    Note: True advance/decline data requires exchange feeds.
    This module uses sector ETFs as a breadth proxy.
    
    Usage:
        analytics = MarketBreadthAnalytics()
        
        # Sector breadth
        breadth = analytics.get_sector_breadth()
        
        # Risk appetite
        risk = analytics.get_risk_appetite_indicator()
        
        # Full dashboard
        dashboard = analytics.get_breadth_dashboard()
    """
    
    def __init__(self):
        """Initialize analytics"""
        self._cache = {}
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    def _get_etf_data(self, ticker: str, period: str = '1y') -> Optional[pd.DataFrame]:
        """Fetch ETF price data from Yahoo Finance"""
        try:
            import yfinance as yf
            etf = yf.Ticker(ticker)
            hist = etf.history(period=period)
            return hist if len(hist) > 0 else None
        except Exception as e:
            print(f"  ✗ Error fetching {ticker}: {e}")
            return None
    
    def _calculate_returns(self, prices: pd.Series, 
                          periods: Dict[str, int] = None) -> Dict[str, float]:
        """Calculate returns for multiple periods"""
        if periods is None:
            periods = {'1D': 1, '1W': 5, '1M': 21, '3M': 63, 'YTD': None}
        
        returns = {}
        current = prices.iloc[-1]
        
        for period, days in periods.items():
            if days is None:  # YTD
                # Find first trading day of year (tz-aware if index is)
                year_start = datetime(prices.index[-1].year, 1, 1)
                if hasattr(prices.index, 'tz') and prices.index.tz is not None:
                    year_start = pd.Timestamp(year_start, tz=prices.index.tz)
                mask = prices.index >= year_start
                if mask.any():
                    start_price = prices[mask].iloc[0]
                    returns[period] = (current / start_price - 1) * 100
            elif len(prices) > days:
                returns[period] = (current / prices.iloc[-days] - 1) * 100
        
        return returns
    
    # =========================================================================
    # SECTOR BREADTH
    # =========================================================================
    
    def get_sector_breadth(self) -> Dict[str, Any]:
        """
        Analyze sector breadth
        
        Calculates how many sectors are:
        - Above/below their 50-day MA
        - Positive/negative over various timeframes
        - Leading/lagging vs SPY
        
        Returns:
            Sector breadth analysis with participation metrics
        """
        print("[Breadth] Analyzing sector participation...")
        
        sector_data = {}
        
        # Fetch all sector ETFs
        for ticker, name in SectorETFs.SECTORS.items():
            data = self._get_etf_data(ticker)
            
            if data is not None and len(data) > 50:
                close = data['Close']
                current = close.iloc[-1]
                
                # Moving averages
                ma_50 = close.rolling(50).mean().iloc[-1]
                ma_200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
                
                # Returns
                returns = self._calculate_returns(close)
                
                sector_data[ticker] = {
                    'name': name,
                    'price': round(current, 2),
                    'above_50ma': current > ma_50,
                    'above_200ma': current > ma_200 if ma_200 else None,
                    'returns': {k: round(v, 2) for k, v in returns.items()},
                    'ma_50': round(ma_50, 2),
                }
                
                print(f"  ✓ {ticker} ({name}): {returns.get('1M', 0):+.1f}% 1M, {'↑' if current > ma_50 else '↓'} 50MA")
        
        # Calculate breadth metrics
        total_sectors = len(sector_data)
        
        if total_sectors > 0:
            # Sectors above 50MA
            above_50ma = sum(1 for s in sector_data.values() if s['above_50ma'])
            pct_above_50ma = above_50ma / total_sectors * 100
            
            # Sectors positive 1M
            positive_1m = sum(1 for s in sector_data.values() if s['returns'].get('1M', 0) > 0)
            pct_positive_1m = positive_1m / total_sectors * 100
            
            # Determine breadth signal
            if pct_above_50ma >= 80:
                breadth_signal = BreadthSignal.STRONG_BULLISH
            elif pct_above_50ma >= 60:
                breadth_signal = BreadthSignal.BULLISH
            elif pct_above_50ma >= 40:
                breadth_signal = BreadthSignal.NEUTRAL
            elif pct_above_50ma >= 20:
                breadth_signal = BreadthSignal.BEARISH
            else:
                breadth_signal = BreadthSignal.STRONG_BEARISH
            
            metrics = {
                'sectors_above_50ma': above_50ma,
                'pct_above_50ma': round(pct_above_50ma, 1),
                'sectors_positive_1m': positive_1m,
                'pct_positive_1m': round(pct_positive_1m, 1),
                'breadth_signal': breadth_signal.value,
                'total_sectors': total_sectors
            }
        else:
            metrics = {'error': 'No sector data available'}
        
        return {
            'sectors': sector_data,
            'metrics': metrics,
            'interpretation': self._interpret_breadth(metrics),
            'as_of': datetime.now().isoformat()
        }
    
    def _interpret_breadth(self, metrics: Dict) -> str:
        """Interpret breadth metrics"""
        pct = metrics.get('pct_above_50ma', 50)
        
        if pct >= 80:
            return "Very strong breadth - broad participation in rally"
        elif pct >= 60:
            return "Healthy breadth - majority of sectors participating"
        elif pct >= 40:
            return "Mixed breadth - selective participation"
        elif pct >= 20:
            return "Weak breadth - narrow leadership"
        else:
            return "Very weak breadth - broad selling pressure"
    
    # =========================================================================
    # RISK APPETITE
    # =========================================================================
    
    def get_risk_appetite_indicator(self) -> Dict[str, Any]:
        """
        Calculate risk-on vs risk-off indicator
        
        Compares performance of:
        - Risk-on: Consumer Discretionary, Tech, Financials
        - Risk-off: Utilities, Staples, Healthcare
        
        Returns:
            Risk appetite signal and ratio
        """
        print("[Breadth] Calculating risk appetite...")
        
        risk_on_returns = []
        risk_off_returns = []
        
        # Calculate 1M returns for risk-on sectors
        for ticker in SectorETFs.RISK_ON:
            data = self._get_etf_data(ticker)
            if data is not None and len(data) >= 21:
                ret = (data['Close'].iloc[-1] / data['Close'].iloc[-21] - 1) * 100
                risk_on_returns.append(ret)
        
        # Calculate 1M returns for risk-off sectors
        for ticker in SectorETFs.RISK_OFF:
            data = self._get_etf_data(ticker)
            if data is not None and len(data) >= 21:
                ret = (data['Close'].iloc[-1] / data['Close'].iloc[-21] - 1) * 100
                risk_off_returns.append(ret)
        
        if risk_on_returns and risk_off_returns:
            avg_risk_on = np.mean(risk_on_returns)
            avg_risk_off = np.mean(risk_off_returns)
            
            # Risk appetite = Risk-on - Risk-off
            risk_appetite = avg_risk_on - avg_risk_off
            
            if risk_appetite > 5:
                signal = 'STRONG_RISK_ON'
                interpretation = 'Markets favor risk assets - bullish sentiment'
            elif risk_appetite > 2:
                signal = 'RISK_ON'
                interpretation = 'Moderate risk appetite - growth favored'
            elif risk_appetite > -2:
                signal = 'NEUTRAL'
                interpretation = 'Balanced risk appetite'
            elif risk_appetite > -5:
                signal = 'RISK_OFF'
                interpretation = 'Defensive positioning - caution warranted'
            else:
                signal = 'STRONG_RISK_OFF'
                interpretation = 'Flight to safety - significant risk aversion'
            
            return {
                'risk_appetite_score': round(risk_appetite, 2),
                'risk_on_avg_return': round(avg_risk_on, 2),
                'risk_off_avg_return': round(avg_risk_off, 2),
                'signal': signal,
                'interpretation': interpretation,
                'as_of': datetime.now().isoformat()
            }
        
        return {'error': 'Insufficient data for risk appetite calculation'}
    
    # =========================================================================
    # CYCLICAL VS DEFENSIVE
    # =========================================================================
    
    def get_cyclical_defensive_ratio(self) -> Dict[str, Any]:
        """
        Analyze cyclical vs defensive sector performance
        
        Cyclical: Tech, Consumer Disc, Financials, Industrials, Materials, Energy
        Defensive: Healthcare, Staples, Utilities, Real Estate
        
        Returns:
            Cyclical/defensive analysis and signal
        """
        print("[Breadth] Analyzing cyclical vs defensive...")
        
        cyclical_returns = []
        defensive_returns = []
        
        # Cyclical sectors
        for ticker in SectorETFs.CYCLICAL:
            data = self._get_etf_data(ticker)
            if data is not None and len(data) >= 21:
                ret = (data['Close'].iloc[-1] / data['Close'].iloc[-21] - 1) * 100
                cyclical_returns.append(ret)
        
        # Defensive sectors
        for ticker in SectorETFs.DEFENSIVE:
            data = self._get_etf_data(ticker)
            if data is not None and len(data) >= 21:
                ret = (data['Close'].iloc[-1] / data['Close'].iloc[-21] - 1) * 100
                defensive_returns.append(ret)
        
        if cyclical_returns and defensive_returns:
            avg_cyclical = np.mean(cyclical_returns)
            avg_defensive = np.mean(defensive_returns)
            
            ratio = avg_cyclical - avg_defensive
            
            if ratio > 3:
                signal = 'CYCLICAL_LEADERSHIP'
                cycle_position = 'Early/Mid Cycle - growth expanding'
            elif ratio > 0:
                signal = 'SLIGHT_CYCLICAL'
                cycle_position = 'Mid Cycle - balanced growth'
            elif ratio > -3:
                signal = 'SLIGHT_DEFENSIVE'
                cycle_position = 'Late Cycle - slowing growth'
            else:
                signal = 'DEFENSIVE_LEADERSHIP'
                cycle_position = 'Late/Recession - defensive positioning warranted'
            
            return {
                'cyclical_avg_return': round(avg_cyclical, 2),
                'defensive_avg_return': round(avg_defensive, 2),
                'spread': round(ratio, 2),
                'signal': signal,
                'cycle_position': cycle_position,
                'as_of': datetime.now().isoformat()
            }
        
        return {'error': 'Insufficient data'}
    
    # =========================================================================
    # SMALL CAP VS LARGE CAP
    # =========================================================================
    
    def get_size_factor_signal(self) -> Dict[str, Any]:
        """
        Analyze small cap vs large cap performance (IWM vs SPY)
        
        Small cap outperformance often signals risk-on and economic optimism
        """
        print("[Breadth] Analyzing size factor...")
        
        spy = self._get_etf_data(MarketETFs.SPY)
        iwm = self._get_etf_data(MarketETFs.IWM)
        
        if spy is None or iwm is None:
            return {'error': 'Could not fetch ETF data'}
        
        periods = {'1W': 5, '1M': 21, '3M': 63}
        
        analysis = {}
        
        for period, days in periods.items():
            if len(spy) > days and len(iwm) > days:
                spy_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[-days] - 1) * 100
                iwm_ret = (iwm['Close'].iloc[-1] / iwm['Close'].iloc[-days] - 1) * 100
                
                spread = iwm_ret - spy_ret
                
                analysis[period] = {
                    'spy_return': round(spy_ret, 2),
                    'iwm_return': round(iwm_ret, 2),
                    'spread': round(spread, 2),
                    'leader': 'Small Cap' if spread > 0 else 'Large Cap'
                }
        
        # Overall signal based on 1M
        spread_1m = analysis.get('1M', {}).get('spread', 0)
        
        if spread_1m > 3:
            signal = 'SMALL_CAP_LEADERSHIP'
            interpretation = 'Risk appetite strong - small caps leading'
        elif spread_1m > 0:
            signal = 'SLIGHT_SMALL_CAP'
            interpretation = 'Modest small cap outperformance'
        elif spread_1m > -3:
            signal = 'SLIGHT_LARGE_CAP'
            interpretation = 'Large cap quality favored'
        else:
            signal = 'LARGE_CAP_LEADERSHIP'
            interpretation = 'Flight to quality - large caps preferred'
        
        return {
            'periods': analysis,
            'signal': signal,
            'interpretation': interpretation,
            'as_of': datetime.now().isoformat()
        }
    
    # =========================================================================
    # COMPREHENSIVE DASHBOARD
    # =========================================================================
    
    def get_breadth_dashboard(self) -> Dict[str, Any]:
        """
        Comprehensive market breadth dashboard
        
        Combines all breadth indicators for full market health assessment
        """
        print("=" * 50)
        print("MARKET BREADTH DASHBOARD")
        print("=" * 50)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            
            # Sector breadth
            'sector_breadth': self.get_sector_breadth(),
            
            # Risk appetite
            'risk_appetite': self.get_risk_appetite_indicator(),
            
            # Cyclical vs defensive
            'cyclical_defensive': self.get_cyclical_defensive_ratio(),
            
            # Size factor
            'size_factor': self.get_size_factor_signal(),
            
            # Summary
            'summary': {}
        }
        
        # Generate summary
        dashboard['summary'] = self._generate_summary(dashboard)
        
        return dashboard
    
    def _generate_summary(self, dashboard: Dict) -> Dict:
        """Generate executive summary"""
        summary = {
            'overall_breadth': 'UNKNOWN',
            'key_signals': [],
            'market_health': 'UNKNOWN',
            'recommendations': []
        }
        
        # Aggregate signals
        signals = []
        
        # Sector breadth
        breadth = dashboard.get('sector_breadth', {}).get('metrics', {})
        if 'breadth_signal' in breadth:
            signals.append(breadth['breadth_signal'])
            summary['key_signals'].append(f"Sector breadth: {breadth['breadth_signal']}")
        
        # Risk appetite
        risk = dashboard.get('risk_appetite', {})
        if 'signal' in risk:
            summary['key_signals'].append(f"Risk appetite: {risk['signal']}")
            if 'RISK_ON' in risk['signal']:
                signals.append('bullish')
            elif 'RISK_OFF' in risk['signal']:
                signals.append('bearish')
        
        # Cyclical/Defensive
        cycle = dashboard.get('cyclical_defensive', {})
        if 'signal' in cycle:
            summary['key_signals'].append(f"Cycle position: {cycle['signal']}")
        
        # Size factor
        size = dashboard.get('size_factor', {})
        if 'signal' in size:
            summary['key_signals'].append(f"Size factor: {size['signal']}")
        
        # Overall assessment
        bullish_count = sum(1 for s in signals if 'bullish' in s.lower() or 'risk_on' in s.lower())
        bearish_count = sum(1 for s in signals if 'bearish' in s.lower() or 'risk_off' in s.lower())
        
        if bullish_count > bearish_count + 1:
            summary['overall_breadth'] = 'BULLISH'
            summary['market_health'] = 'HEALTHY'
            summary['recommendations'] = [
                "Broad market participation supports uptrend",
                "Favor beta exposure",
                "Consider adding cyclical/growth exposure"
            ]
        elif bearish_count > bullish_count + 1:
            summary['overall_breadth'] = 'BEARISH'
            summary['market_health'] = 'DETERIORATING'
            summary['recommendations'] = [
                "Narrow leadership - rally vulnerable",
                "Reduce beta exposure",
                "Favor quality and defensive sectors"
            ]
        else:
            summary['overall_breadth'] = 'NEUTRAL'
            summary['market_health'] = 'MIXED'
            summary['recommendations'] = [
                "Mixed signals - selective positioning",
                "Monitor for trend confirmation",
                "Balance cyclical and defensive exposure"
            ]
        
        return summary


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - MARKET BREADTH ANALYTICS TEST")
    print("=" * 60)
    
    analytics = MarketBreadthAnalytics()
    
    print("\n--- Available Methods ---")
    print("  • get_sector_breadth()")
    print("  • get_risk_appetite_indicator()")
    print("  • get_cyclical_defensive_ratio()")
    print("  • get_size_factor_signal()")
    print("  • get_breadth_dashboard()")
    
    print("\n--- Data Sources ---")
    print("  • Sector ETFs: XLK, XLV, XLF, XLY, etc.")
    print("  • Market ETFs: SPY, QQQ, IWM")
    
    print("\n✅ Market Breadth Analytics module loaded successfully")

"""
Greybark Research - Credit Spread Analytics Module
Mejora #9 del AI Council

Detailed credit spread analysis:
- IG spreads by rating (AAA, AA, A, BBB)
- HY spreads (BB, B, CCC)
- Sector spreads (Financials, Industrials, Utilities)
- Spread percentiles and signals
- Quality rotation recommendations

Data Source: FRED (ICE BofA Indices)

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
    from data_sources.fred_client import FREDClient
except ImportError:
    from greybark.data_sources.fred_client import FREDClient


# =============================================================================
# FRED SERIES CODES
# =============================================================================

class CreditSpreadSeries:
    """FRED ICE BofA Credit Spread Series"""
    
    # Investment Grade by Rating
    IG_TOTAL = "BAMLC0A0CM"           # US Corporate Master OAS
    IG_AAA = "BAMLC0A1CAAA"           # AAA OAS
    IG_AA = "BAMLC0A2CAA"             # AA OAS
    IG_A = "BAMLC0A3CA"               # A OAS
    IG_BBB = "BAMLC0A4CBBB"           # BBB OAS
    
    # High Yield by Rating
    HY_TOTAL = "BAMLH0A0HYM2"         # US HY Master II OAS
    HY_BB = "BAMLH0A1HYBB"            # BB OAS
    HY_B = "BAMLH0A2HYB"              # B OAS
    HY_CCC = "BAMLH0A3HYC"            # CCC & Lower OAS
    
    # By Sector (if available)
    IG_FINANCIAL = "BAMLC0A0CMFIN"    # IG Financials (may not exist)
    IG_INDUSTRIAL = "BAMLC0A0CMIND"   # IG Industrials (may not exist)
    IG_UTILITY = "BAMLC0A0CMUTL"      # IG Utilities (may not exist)
    
    # Duration buckets
    IG_1_3Y = "BAMLC1A0C13Y"          # 1-3Y OAS
    IG_3_5Y = "BAMLC2A0C35Y"          # 3-5Y OAS
    IG_5_7Y = "BAMLC3A0C57Y"          # 5-7Y OAS
    IG_7_10Y = "BAMLC4A0C710Y"        # 7-10Y OAS
    IG_10PLUS = "BAMLC7A0C1015Y"      # 10-15Y OAS


# Historical thresholds for spread levels
SPREAD_THRESHOLDS = {
    'IG_TOTAL': {'tight': 80, 'normal': 120, 'wide': 180, 'crisis': 300},
    'IG_AAA': {'tight': 40, 'normal': 60, 'wide': 90, 'crisis': 150},
    'IG_AA': {'tight': 50, 'normal': 75, 'wide': 110, 'crisis': 180},
    'IG_A': {'tight': 70, 'normal': 100, 'wide': 150, 'crisis': 250},
    'IG_BBB': {'tight': 120, 'normal': 170, 'wide': 250, 'crisis': 400},
    'HY_TOTAL': {'tight': 300, 'normal': 450, 'wide': 600, 'crisis': 900},
    'HY_BB': {'tight': 200, 'normal': 300, 'wide': 450, 'crisis': 700},
    'HY_B': {'tight': 350, 'normal': 500, 'wide': 700, 'crisis': 1000},
    'HY_CCC': {'tight': 700, 'normal': 1000, 'wide': 1400, 'crisis': 2000},
}


class SpreadLevel(Enum):
    """Spread level classification"""
    TIGHT = "tight"
    NORMAL = "normal"
    WIDE = "wide"
    CRISIS = "crisis"


# =============================================================================
# MAIN CLASS
# =============================================================================

class CreditSpreadAnalytics:
    """
    Credit Spread Analytics
    
    Detailed analysis of credit spreads by:
    - Rating (AAA, AA, A, BBB, BB, B, CCC)
    - Duration bucket
    - Quality rotation signals
    
    Usage:
        analytics = CreditSpreadAnalytics()
        
        # IG breakdown by rating
        ig = analytics.get_ig_breakdown()
        
        # Quality rotation signal
        rotation = analytics.get_quality_rotation_signal()
        
        # Full dashboard
        dashboard = analytics.get_credit_dashboard()
    """
    
    def __init__(self, fred_api_key: Optional[str] = None):
        """Initialize with FRED API key"""
        self.fred = FREDClient(api_key=fred_api_key)
        self._cache = {}
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    def _fetch_spread_series(self, series_id: str, 
                             lookback_years: int = 5) -> Optional[pd.Series]:
        """Fetch spread series from FRED"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_years * 365)
            
            data = self.fred.get_series(
                series_id,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            return data
        except Exception as e:
            print(f"  ✗ Error fetching {series_id}: {e}")
            return None
    
    def _classify_spread_level(self, spread: float, 
                                thresholds: Dict) -> SpreadLevel:
        """Classify spread level based on thresholds"""
        if spread <= thresholds['tight']:
            return SpreadLevel.TIGHT
        elif spread <= thresholds['normal']:
            return SpreadLevel.NORMAL
        elif spread <= thresholds['wide']:
            return SpreadLevel.WIDE
        else:
            return SpreadLevel.CRISIS
    
    # =========================================================================
    # IG ANALYSIS
    # =========================================================================
    
    def get_ig_breakdown(self) -> Dict[str, Any]:
        """
        Investment Grade spread breakdown by rating
        
        Returns:
            Dict with AAA, AA, A, BBB spreads and analysis
        """
        print("[Credit] Fetching IG spread breakdown...")
        
        breakdown = {}
        
        # Fetch each rating
        ratings = {
            'total': ('IG_TOTAL', CreditSpreadSeries.IG_TOTAL),
            'aaa': ('IG_AAA', CreditSpreadSeries.IG_AAA),
            'aa': ('IG_AA', CreditSpreadSeries.IG_AA),
            'a': ('IG_A', CreditSpreadSeries.IG_A),
            'bbb': ('IG_BBB', CreditSpreadSeries.IG_BBB),
        }
        
        for key, (threshold_key, series_id) in ratings.items():
            data = self._fetch_spread_series(series_id)
            
            if data is not None and len(data) > 0:
                current = data.iloc[-1]
                
                # Calculate percentile
                percentile = (data < current).mean() * 100
                
                # Calculate momentum
                if len(data) >= 21:
                    mom_1m = current - data.iloc[-21]
                else:
                    mom_1m = 0
                    
                if len(data) >= 63:
                    mom_3m = current - data.iloc[-63]
                else:
                    mom_3m = 0
                
                # Classify level
                thresholds = SPREAD_THRESHOLDS.get(threshold_key, SPREAD_THRESHOLDS['IG_TOTAL'])
                level = self._classify_spread_level(current, thresholds)
                
                # Signal
                if level == SpreadLevel.WIDE:
                    signal = 'ATTRACTIVE'
                elif level == SpreadLevel.TIGHT:
                    signal = 'EXPENSIVE'
                else:
                    signal = 'FAIR_VALUE'
                
                breakdown[key] = {
                    'current_bps': round(current, 0),
                    'percentile_5y': round(percentile, 1),
                    'level': level.value,
                    'signal': signal,
                    'momentum_1m_bps': round(mom_1m, 0),
                    'momentum_3m_bps': round(mom_3m, 0),
                    'thresholds': thresholds
                }
                
                print(f"  ✓ {key.upper():5}: {current:.0f}bps ({percentile:.0f}th pctl) - {level.value}")
        
        breakdown['as_of'] = datetime.now().isoformat()
        return breakdown
    
    def get_hy_breakdown(self) -> Dict[str, Any]:
        """
        High Yield spread breakdown by rating
        
        Returns:
            Dict with BB, B, CCC spreads and analysis
        """
        print("[Credit] Fetching HY spread breakdown...")
        
        breakdown = {}
        
        ratings = {
            'total': ('HY_TOTAL', CreditSpreadSeries.HY_TOTAL),
            'bb': ('HY_BB', CreditSpreadSeries.HY_BB),
            'b': ('HY_B', CreditSpreadSeries.HY_B),
            'ccc': ('HY_CCC', CreditSpreadSeries.HY_CCC),
        }
        
        for key, (threshold_key, series_id) in ratings.items():
            data = self._fetch_spread_series(series_id)
            
            if data is not None and len(data) > 0:
                current = data.iloc[-1]
                percentile = (data < current).mean() * 100
                
                if len(data) >= 21:
                    mom_1m = current - data.iloc[-21]
                else:
                    mom_1m = 0
                
                thresholds = SPREAD_THRESHOLDS.get(threshold_key, SPREAD_THRESHOLDS['HY_TOTAL'])
                level = self._classify_spread_level(current, thresholds)
                
                if level == SpreadLevel.WIDE:
                    signal = 'ATTRACTIVE'
                elif level == SpreadLevel.TIGHT:
                    signal = 'EXPENSIVE'
                else:
                    signal = 'FAIR_VALUE'
                
                breakdown[key] = {
                    'current_bps': round(current, 0),
                    'percentile_5y': round(percentile, 1),
                    'level': level.value,
                    'signal': signal,
                    'momentum_1m_bps': round(mom_1m, 0),
                }
                
                print(f"  ✓ {key.upper():5}: {current:.0f}bps ({percentile:.0f}th pctl) - {level.value}")
        
        breakdown['as_of'] = datetime.now().isoformat()
        return breakdown
    
    # =========================================================================
    # QUALITY ROTATION
    # =========================================================================
    
    def get_quality_rotation_signal(self) -> Dict[str, Any]:
        """
        Quality rotation signal based on spread ratios
        
        Analyzes:
        - BBB/A spread ratio (IG quality)
        - B/BB spread ratio (HY quality)
        - HY/IG ratio (overall risk appetite)
        
        Returns:
            Quality rotation recommendation
        """
        print("[Credit] Analyzing quality rotation...")
        
        # Fetch spreads
        ig_a = self._fetch_spread_series(CreditSpreadSeries.IG_A)
        ig_bbb = self._fetch_spread_series(CreditSpreadSeries.IG_BBB)
        hy_bb = self._fetch_spread_series(CreditSpreadSeries.HY_BB)
        hy_b = self._fetch_spread_series(CreditSpreadSeries.HY_B)
        ig_total = self._fetch_spread_series(CreditSpreadSeries.IG_TOTAL)
        hy_total = self._fetch_spread_series(CreditSpreadSeries.HY_TOTAL)
        
        ratios = {}
        signals = []
        
        # BBB/A ratio (IG quality spread)
        if ig_a is not None and ig_bbb is not None and len(ig_a) > 0 and len(ig_bbb) > 0:
            current_ratio = ig_bbb.iloc[-1] / ig_a.iloc[-1]
            
            # Historical context
            hist_ratio = ig_bbb / ig_a
            percentile = (hist_ratio < current_ratio).mean() * 100
            
            ratios['bbb_a_ratio'] = {
                'current': round(current_ratio, 2),
                'percentile': round(percentile, 1),
                'interpretation': 'BBB cheap vs A' if percentile > 60 else 'A cheap vs BBB' if percentile < 40 else 'Fair'
            }
            
            if percentile > 60:
                signals.append('down_in_quality')  # BBB is cheap
            elif percentile < 40:
                signals.append('up_in_quality')    # A is cheap
        
        # B/BB ratio (HY quality spread)
        if hy_bb is not None and hy_b is not None and len(hy_bb) > 0 and len(hy_b) > 0:
            current_ratio = hy_b.iloc[-1] / hy_bb.iloc[-1]
            hist_ratio = hy_b / hy_bb
            percentile = (hist_ratio < current_ratio).mean() * 100
            
            ratios['b_bb_ratio'] = {
                'current': round(current_ratio, 2),
                'percentile': round(percentile, 1),
                'interpretation': 'B cheap vs BB' if percentile > 60 else 'BB cheap vs B' if percentile < 40 else 'Fair'
            }
            
            if percentile > 60:
                signals.append('down_in_quality')
            elif percentile < 40:
                signals.append('up_in_quality')
        
        # HY/IG ratio (overall risk appetite)
        if ig_total is not None and hy_total is not None and len(ig_total) > 0 and len(hy_total) > 0:
            current_ratio = hy_total.iloc[-1] / ig_total.iloc[-1]
            hist_ratio = hy_total / ig_total
            percentile = (hist_ratio < current_ratio).mean() * 100
            
            ratios['hy_ig_ratio'] = {
                'current': round(current_ratio, 2),
                'percentile': round(percentile, 1),
                'interpretation': 'HY cheap vs IG' if percentile > 60 else 'IG cheap vs HY' if percentile < 40 else 'Fair'
            }
        
        # Determine overall recommendation
        down_count = signals.count('down_in_quality')
        up_count = signals.count('up_in_quality')
        
        if down_count > up_count:
            recommendation = 'DOWN_IN_QUALITY'
            rationale = 'Lower quality credits offer attractive spreads vs higher quality'
        elif up_count > down_count:
            recommendation = 'UP_IN_QUALITY'
            rationale = 'Higher quality credits offer better risk-adjusted value'
        else:
            recommendation = 'NEUTRAL'
            rationale = 'Quality spreads are fairly valued - no strong rotation signal'
        
        return {
            'recommendation': recommendation,
            'rationale': rationale,
            'ratios': ratios,
            'signals': signals,
            'as_of': datetime.now().isoformat()
        }
    
    # =========================================================================
    # COMPREHENSIVE DASHBOARD
    # =========================================================================
    
    def get_credit_dashboard(self) -> Dict[str, Any]:
        """
        Comprehensive credit spread dashboard
        
        Includes IG, HY, quality rotation, and investment implications
        """
        print("=" * 50)
        print("CREDIT SPREAD DASHBOARD")
        print("=" * 50)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            
            # IG breakdown
            'ig_breakdown': self.get_ig_breakdown(),
            
            # HY breakdown
            'hy_breakdown': self.get_hy_breakdown(),
            
            # Quality rotation
            'quality_rotation': self.get_quality_rotation_signal(),
            
            # Summary
            'summary': {}
        }
        
        # Generate summary
        dashboard['summary'] = self._generate_summary(dashboard)
        
        return dashboard
    
    def _generate_summary(self, dashboard: Dict) -> Dict:
        """Generate executive summary"""
        summary = {
            'key_metrics': {},
            'recommendations': [],
            'risks': []
        }
        
        # Key metrics
        ig = dashboard.get('ig_breakdown', {})
        hy = dashboard.get('hy_breakdown', {})
        
        if 'total' in ig:
            summary['key_metrics']['ig_spread'] = f"{ig['total']['current_bps']:.0f}bps ({ig['total']['level']})"
        if 'total' in hy:
            summary['key_metrics']['hy_spread'] = f"{hy['total']['current_bps']:.0f}bps ({hy['total']['level']})"
        
        # Recommendations based on levels
        quality = dashboard.get('quality_rotation', {})
        summary['recommendations'].append(f"Quality: {quality.get('recommendation', 'NEUTRAL')}")
        
        # IG recommendation
        if 'total' in ig:
            if ig['total']['level'] == 'wide':
                summary['recommendations'].append("IG: OVERWEIGHT - spreads attractive")
            elif ig['total']['level'] == 'tight':
                summary['recommendations'].append("IG: UNDERWEIGHT - spreads tight")
            else:
                summary['recommendations'].append("IG: NEUTRAL")
        
        # HY recommendation
        if 'total' in hy:
            if hy['total']['level'] == 'wide':
                summary['recommendations'].append("HY: SELECTIVE OVERWEIGHT - spreads compensate for risk")
            elif hy['total']['level'] == 'tight':
                summary['recommendations'].append("HY: UNDERWEIGHT - inadequate risk compensation")
            else:
                summary['recommendations'].append("HY: NEUTRAL")
        
        # Risks
        if hy.get('ccc', {}).get('level') == 'crisis':
            summary['risks'].append("CCC spreads at distressed levels - default risk elevated")
        
        ig_momentum = ig.get('total', {}).get('momentum_1m_bps', 0)
        if ig_momentum > 20:
            summary['risks'].append("IG spreads widening - credit conditions deteriorating")
        
        return summary


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - CREDIT SPREAD ANALYTICS TEST")
    print("=" * 60)
    
    analytics = CreditSpreadAnalytics()
    
    print("\n--- Available Methods ---")
    print("  • get_ig_breakdown()")
    print("  • get_hy_breakdown()")
    print("  • get_quality_rotation_signal()")
    print("  • get_credit_dashboard()")
    
    print("\n--- FRED Series Used ---")
    print("  • IG: BAMLC0A0CM (Total), BAMLC0A1CAAA (AAA), etc.")
    print("  • HY: BAMLH0A0HYM2 (Total), BAMLH0A1HYBB (BB), etc.")
    
    print("\n✅ Credit Spread Analytics module loaded successfully")

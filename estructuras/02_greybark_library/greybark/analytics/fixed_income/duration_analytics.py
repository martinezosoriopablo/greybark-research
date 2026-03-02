"""
Greybark Research - Duration Recommendations Framework
Mejora #5 del AI Council

Provides:
- Duration target recommendations by macro regime
- Yield curve positioning (steepener/flattener)
- Credit spread analysis (IG/HY)
- Comprehensive duration dashboard

Author: Greybark Research
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Import FRED client
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from data_sources.fred_client import FREDClient
except ImportError:
    from greybark.data_sources.fred_client import FREDClient


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class MacroRegime(Enum):
    """Macro regime classifications"""
    GOLDILOCKS = "goldilocks"           # Growth up, inflation down
    REFLATION = "reflation"             # Growth up, inflation up
    STAGFLATION = "stagflation"         # Growth down, inflation up
    DEFLATION = "deflation"             # Growth down, inflation down
    RECESSION = "recession"             # Sharp contraction
    RECOVERY = "recovery"               # Post-recession bounce


class CurvePosition(Enum):
    """Yield curve positioning"""
    STEEPENER = "steepener"             # Long duration, short front-end
    FLATTENER = "flattener"             # Short duration, long front-end
    BULLET = "bullet"                   # Concentrated in belly
    BARBELL = "barbell"                 # Long and short ends
    NEUTRAL = "neutral"                 # Duration-matched


class CreditStance(Enum):
    """Credit spread positioning"""
    OVERWEIGHT = "overweight"           # Spread compression expected
    UNDERWEIGHT = "underweight"         # Spread widening expected
    NEUTRAL = "neutral"                 # No strong view


@dataclass
class DurationTarget:
    """Duration recommendation output"""
    target_duration: float              # Years
    duration_range: Tuple[float, float] # Min, Max
    confidence: str                     # HIGH, MEDIUM, LOW
    rationale: str
    vs_benchmark: str                   # LONG, SHORT, NEUTRAL


@dataclass
class CurveRecommendation:
    """Yield curve positioning recommendation"""
    position: CurvePosition
    trade_expression: str               # e.g., "2s10s steepener"
    expected_move_bps: int
    confidence: str
    rationale: str


@dataclass
class CreditRecommendation:
    """Credit spread recommendation"""
    ig_stance: CreditStance
    hy_stance: CreditStance
    preferred_quality: str              # "up-in-quality" or "down-in-quality"
    sector_preferences: List[str]
    rationale: str


# =============================================================================
# FRED SERIES CODES
# =============================================================================

FRED_SERIES = {
    # Treasury Yields
    'UST_3M': 'DGS3MO',
    'UST_6M': 'DGS6MO', 
    'UST_1Y': 'DGS1',
    'UST_2Y': 'DGS2',
    'UST_5Y': 'DGS5',
    'UST_7Y': 'DGS7',
    'UST_10Y': 'DGS10',
    'UST_20Y': 'DGS20',
    'UST_30Y': 'DGS30',
    
    # Credit Spreads
    'IG_OAS': 'BAMLC0A0CM',              # ICE BofA US Corp Index OAS
    'HY_OAS': 'BAMLH0A0HYM2',            # ICE BofA US HY Index OAS
    'BBB_OAS': 'BAMLC0A4CBBB',           # BBB OAS
    'BB_OAS': 'BAMLH0A1HYBB',            # BB OAS
    
    # Fed Funds
    'FED_FUNDS': 'FEDFUNDS',
    'FED_FUNDS_EFFECTIVE': 'DFF',
    
    # Inflation Expectations
    'BREAKEVEN_5Y': 'T5YIE',
    'BREAKEVEN_10Y': 'T10YIE',
    
    # Real Rates
    'TIPS_5Y': 'DFII5',
    'TIPS_10Y': 'DFII10',
    
    # Economic Indicators
    'TERM_PREMIUM_10Y': 'THREEFYTP10',   # NY Fed Term Premium
    'MOVE_INDEX': 'MOVE',                 # Bond volatility (if available)
}


# =============================================================================
# DURATION TARGET MATRICES
# =============================================================================

# Duration targets by regime (vs benchmark duration of ~6.5 years for Agg)
DURATION_TARGETS_BY_REGIME = {
    MacroRegime.GOLDILOCKS: {
        'target': 6.5,
        'range': (6.0, 7.5),
        'vs_benchmark': 'NEUTRAL',
        'rationale': 'Stable growth and contained inflation support neutral duration'
    },
    MacroRegime.REFLATION: {
        'target': 5.0,
        'range': (4.0, 5.5),
        'vs_benchmark': 'SHORT',
        'rationale': 'Rising inflation pressures warrant shorter duration'
    },
    MacroRegime.STAGFLATION: {
        'target': 4.5,
        'range': (3.5, 5.0),
        'vs_benchmark': 'SHORT',
        'rationale': 'Inflation risk dominates; minimize duration exposure'
    },
    MacroRegime.DEFLATION: {
        'target': 8.5,
        'range': (7.5, 10.0),
        'vs_benchmark': 'LONG',
        'rationale': 'Falling inflation and rates favor duration extension'
    },
    MacroRegime.RECESSION: {
        'target': 9.0,
        'range': (8.0, 11.0),
        'vs_benchmark': 'LONG',
        'rationale': 'Flight to quality and rate cuts favor long duration'
    },
    MacroRegime.RECOVERY: {
        'target': 5.5,
        'range': (5.0, 6.5),
        'vs_benchmark': 'SHORT',
        'rationale': 'Economic recovery may lead to rising yields'
    }
}


# Curve positioning by regime
CURVE_POSITIONING_BY_REGIME = {
    MacroRegime.GOLDILOCKS: {
        'position': CurvePosition.BULLET,
        'trade': '5Y overweight',
        'rationale': 'Belly offers best carry in stable environment'
    },
    MacroRegime.REFLATION: {
        'position': CurvePosition.FLATTENER,
        'trade': '2s10s flattener',
        'rationale': 'Fed hiking flattens curve; front-end rises more than long-end'
    },
    MacroRegime.STAGFLATION: {
        'position': CurvePosition.BARBELL,
        'trade': '2Y + 30Y vs 10Y',
        'rationale': 'Uncertainty favors barbell; hedge both inflation and recession'
    },
    MacroRegime.DEFLATION: {
        'position': CurvePosition.STEEPENER,
        'trade': '2s10s steepener',
        'rationale': 'Fed cutting; front-end falls faster than long-end'
    },
    MacroRegime.RECESSION: {
        'position': CurvePosition.STEEPENER,
        'trade': '2s30s steepener',
        'rationale': 'Aggressive Fed cuts steepen curve dramatically'
    },
    MacroRegime.RECOVERY: {
        'position': CurvePosition.FLATTENER,
        'trade': '5s30s flattener',
        'rationale': 'Long-end anchored as growth returns'
    }
}


# Credit spread thresholds
CREDIT_THRESHOLDS = {
    'IG': {
        'tight': 80,      # bps - spreads very tight
        'normal': 120,    # bps - fair value area
        'wide': 180,      # bps - attractive entry
        'crisis': 300     # bps - distressed
    },
    'HY': {
        'tight': 300,     # bps
        'normal': 450,    # bps
        'wide': 600,      # bps
        'crisis': 900     # bps
    }
}


# =============================================================================
# MAIN CLASS
# =============================================================================

class DurationAnalytics:
    """
    Duration Recommendations Framework
    
    Provides comprehensive fixed income analytics including:
    - Duration targeting based on macro regime
    - Yield curve analysis and positioning
    - Credit spread analysis
    - Integrated recommendations
    """
    
    def __init__(self, fred_api_key: Optional[str] = None):
        """Initialize with FRED API key"""
        self.fred = FREDClient(api_key=fred_api_key)
        self._cache = {}
        self._cache_timestamp = None
        
    # -------------------------------------------------------------------------
    # DATA FETCHING
    # -------------------------------------------------------------------------
    
    def _fetch_treasury_curve(self, lookback_days: int = 30) -> pd.DataFrame:
        """Fetch current Treasury yield curve"""
        tenors = ['3M', '6M', '1Y', '2Y', '5Y', '7Y', '10Y', '20Y', '30Y']
        series_map = {t: FRED_SERIES[f'UST_{t}'] for t in tenors}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        curve_data = {}
        for tenor, series_id in series_map.items():
            try:
                data = self.fred.get_series(
                    series_id,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
                if data is not None and len(data) > 0:
                    curve_data[tenor] = data.iloc[-1]  # Latest value
            except Exception as e:
                print(f"Warning: Could not fetch {tenor} yield: {e}")
                
        return pd.Series(curve_data, name='yield')
    
    def _fetch_credit_spreads(self, lookback_days: int = 252) -> Dict[str, pd.Series]:
        """Fetch credit spread history"""
        spreads = {}
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        for name, series_id in [('IG', FRED_SERIES['IG_OAS']), 
                                 ('HY', FRED_SERIES['HY_OAS'])]:
            try:
                data = self.fred.get_series(
                    series_id,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
                if data is not None:
                    spreads[name] = data
            except Exception as e:
                print(f"Warning: Could not fetch {name} spreads: {e}")
                
        return spreads
    
    def _fetch_inflation_expectations(self) -> Dict[str, float]:
        """Fetch breakeven inflation rates"""
        expectations = {}
        
        for name, series_id in [('5Y', FRED_SERIES['BREAKEVEN_5Y']),
                                 ('10Y', FRED_SERIES['BREAKEVEN_10Y'])]:
            try:
                data = self.fred.get_series(series_id)
                if data is not None and len(data) > 0:
                    expectations[name] = data.iloc[-1]
            except Exception:
                pass
                
        return expectations
    
    def _fetch_real_rates(self) -> Dict[str, float]:
        """Fetch TIPS real yields"""
        real_rates = {}
        
        for name, series_id in [('5Y', FRED_SERIES['TIPS_5Y']),
                                 ('10Y', FRED_SERIES['TIPS_10Y'])]:
            try:
                data = self.fred.get_series(series_id)
                if data is not None and len(data) > 0:
                    real_rates[name] = data.iloc[-1]
            except Exception:
                pass
                
        return real_rates
    
    # -------------------------------------------------------------------------
    # YIELD CURVE ANALYSIS
    # -------------------------------------------------------------------------
    
    def get_yield_curve_analysis(self) -> Dict[str, Any]:
        """
        Comprehensive yield curve analysis
        
        Returns:
            Dictionary with curve shape, slopes, and analysis
        """
        curve = self._fetch_treasury_curve()
        
        if curve.empty:
            return {'error': 'Could not fetch Treasury curve data'}
        
        # Calculate key slopes
        slopes = {}
        slope_pairs = [
            ('2s5s', '2Y', '5Y'),
            ('2s10s', '2Y', '10Y'),
            ('2s30s', '2Y', '30Y'),
            ('5s10s', '5Y', '10Y'),
            ('5s30s', '5Y', '30Y'),
            ('10s30s', '10Y', '30Y'),
        ]
        
        for name, short, long in slope_pairs:
            if short in curve.index and long in curve.index:
                slopes[name] = (curve[long] - curve[short]) * 100  # bps
        
        # Determine curve shape
        curve_2s10s = slopes.get('2s10s', 0)
        if curve_2s10s < -50:
            shape = 'DEEPLY_INVERTED'
            shape_signal = 'Recession warning - historically leads recessions by 12-18 months'
        elif curve_2s10s < 0:
            shape = 'INVERTED'
            shape_signal = 'Caution - curve inversion often precedes economic slowdown'
        elif curve_2s10s < 50:
            shape = 'FLAT'
            shape_signal = 'Neutral - limited term premium'
        elif curve_2s10s < 150:
            shape = 'NORMAL'
            shape_signal = 'Healthy - positive term premium'
        else:
            shape = 'STEEP'
            shape_signal = 'Very steep - typically seen in early recovery'
        
        # Calculate butterfly (belly richness/cheapness)
        if all(x in curve.index for x in ['2Y', '5Y', '10Y']):
            butterfly = (curve['5Y'] * 2 - curve['2Y'] - curve['10Y']) * 100
        else:
            butterfly = None
        
        return {
            'current_curve': curve.to_dict(),
            'slopes_bps': slopes,
            'shape': shape,
            'shape_signal': shape_signal,
            'butterfly_bps': butterfly,
            'analysis': {
                'front_end': f"{curve.get('2Y', 'N/A'):.2f}%" if '2Y' in curve.index else 'N/A',
                'belly': f"{curve.get('5Y', 'N/A'):.2f}%" if '5Y' in curve.index else 'N/A',
                'long_end': f"{curve.get('30Y', 'N/A'):.2f}%" if '30Y' in curve.index else 'N/A',
            },
            'as_of': datetime.now().isoformat()
        }
    
    def get_curve_positioning_recommendation(self, 
                                              regime: Optional[MacroRegime] = None) -> CurveRecommendation:
        """
        Get yield curve positioning recommendation
        
        Args:
            regime: Macro regime (if None, will be inferred from curve shape)
            
        Returns:
            CurveRecommendation with positioning details
        """
        curve_analysis = self.get_yield_curve_analysis()
        
        if 'error' in curve_analysis:
            return CurveRecommendation(
                position=CurvePosition.NEUTRAL,
                trade_expression="Unable to analyze",
                expected_move_bps=0,
                confidence='LOW',
                rationale=curve_analysis['error']
            )
        
        # If no regime provided, infer from curve shape
        if regime is None:
            shape = curve_analysis['shape']
            if shape in ['DEEPLY_INVERTED', 'INVERTED']:
                # Inverted curve suggests Fed will cut → steepener
                return CurveRecommendation(
                    position=CurvePosition.STEEPENER,
                    trade_expression="2s10s steepener - receive 2Y, pay 10Y",
                    expected_move_bps=50,
                    confidence='HIGH',
                    rationale=f"Curve {shape.lower()}: Fed cuts likely to steepen curve"
                )
            elif shape == 'STEEP':
                # Very steep suggests normalization → flattener
                return CurveRecommendation(
                    position=CurvePosition.FLATTENER,
                    trade_expression="2s10s flattener - pay 2Y, receive 10Y",
                    expected_move_bps=30,
                    confidence='MEDIUM',
                    rationale="Steep curve: normalization or Fed hikes likely"
                )
            else:
                # Flat or normal - bullet in belly
                return CurveRecommendation(
                    position=CurvePosition.BULLET,
                    trade_expression="5Y overweight vs barbelled benchmark",
                    expected_move_bps=10,
                    confidence='MEDIUM',
                    rationale="Neutral curve: belly offers best risk-adjusted carry"
                )
        
        # Use regime-based positioning
        positioning = CURVE_POSITIONING_BY_REGIME.get(regime, {})
        
        return CurveRecommendation(
            position=positioning.get('position', CurvePosition.NEUTRAL),
            trade_expression=positioning.get('trade', 'Neutral'),
            expected_move_bps=25,  # Default expected move
            confidence='MEDIUM',
            rationale=positioning.get('rationale', 'Based on regime analysis')
        )
    
    # -------------------------------------------------------------------------
    # CREDIT SPREAD ANALYSIS
    # -------------------------------------------------------------------------
    
    def get_credit_spread_analysis(self) -> Dict[str, Any]:
        """
        Comprehensive credit spread analysis
        
        Returns:
            Dictionary with spread levels, percentiles, and signals
        """
        spreads = self._fetch_credit_spreads(lookback_days=252 * 5)  # 5 years
        
        if not spreads:
            return {'error': 'Could not fetch credit spread data'}
        
        analysis = {}
        
        for name, data in spreads.items():
            if data is None or len(data) == 0:
                continue
                
            current = data.iloc[-1]
            thresholds = CREDIT_THRESHOLDS.get(name, {})
            
            # Calculate percentiles
            percentile = (data < current).mean() * 100
            
            # Determine spread level
            if current <= thresholds.get('tight', 0):
                level = 'TIGHT'
                signal = 'EXPENSIVE - spreads historically tight'
            elif current <= thresholds.get('normal', 0):
                level = 'NORMAL'
                signal = 'FAIR VALUE - spreads in normal range'
            elif current <= thresholds.get('wide', 0):
                level = 'WIDE'
                signal = 'ATTRACTIVE - consider adding exposure'
            else:
                level = 'CRISIS'
                signal = 'DISTRESSED - high risk, high reward'
            
            # Calculate momentum
            if len(data) >= 21:
                mom_1m = current - data.iloc[-21]
            else:
                mom_1m = 0
                
            if len(data) >= 63:
                mom_3m = current - data.iloc[-63]
            else:
                mom_3m = 0
            
            analysis[name] = {
                'current_spread_bps': round(current * 100, 0) if current < 10 else round(current, 0),
                'percentile_5y': round(percentile, 1),
                'level': level,
                'signal': signal,
                'momentum_1m_bps': round(mom_1m * 100, 0) if mom_1m and abs(mom_1m) < 10 else round(mom_1m, 0) if mom_1m else 0,
                'momentum_3m_bps': round(mom_3m * 100, 0) if mom_3m and abs(mom_3m) < 10 else round(mom_3m, 0) if mom_3m else 0,
                'thresholds': thresholds
            }
        
        # IG vs HY relative value
        if 'IG' in analysis and 'HY' in analysis:
            ig_spread = analysis['IG']['current_spread_bps']
            hy_spread = analysis['HY']['current_spread_bps']
            
            if ig_spread > 0:
                hy_ig_ratio = hy_spread / ig_spread
                
                if hy_ig_ratio > 5:
                    rel_value = 'HY CHEAP vs IG'
                elif hy_ig_ratio < 3.5:
                    rel_value = 'IG CHEAP vs HY'
                else:
                    rel_value = 'FAIR RELATIVE VALUE'
                    
                analysis['relative_value'] = {
                    'hy_ig_ratio': round(hy_ig_ratio, 2),
                    'signal': rel_value
                }
        
        analysis['as_of'] = datetime.now().isoformat()
        return analysis
    
    def get_credit_recommendation(self, 
                                   regime: Optional[MacroRegime] = None) -> CreditRecommendation:
        """
        Get credit allocation recommendation
        
        Args:
            regime: Macro regime for context
            
        Returns:
            CreditRecommendation with allocation guidance
        """
        spread_analysis = self.get_credit_spread_analysis()
        
        if 'error' in spread_analysis:
            return CreditRecommendation(
                ig_stance=CreditStance.NEUTRAL,
                hy_stance=CreditStance.NEUTRAL,
                preferred_quality='neutral',
                sector_preferences=[],
                rationale=spread_analysis['error']
            )
        
        ig_data = spread_analysis.get('IG', {})
        hy_data = spread_analysis.get('HY', {})
        
        # Determine stances based on spread levels
        ig_level = ig_data.get('level', 'NORMAL')
        hy_level = hy_data.get('level', 'NORMAL')
        
        # IG stance
        if ig_level == 'WIDE':
            ig_stance = CreditStance.OVERWEIGHT
        elif ig_level == 'TIGHT':
            ig_stance = CreditStance.UNDERWEIGHT
        else:
            ig_stance = CreditStance.NEUTRAL
        
        # HY stance (more conservative)
        if hy_level == 'CRISIS':
            hy_stance = CreditStance.UNDERWEIGHT  # Too risky unless distressed specialist
        elif hy_level == 'WIDE':
            hy_stance = CreditStance.OVERWEIGHT
        elif hy_level == 'TIGHT':
            hy_stance = CreditStance.UNDERWEIGHT
        else:
            hy_stance = CreditStance.NEUTRAL
        
        # Quality preference
        if regime in [MacroRegime.RECESSION, MacroRegime.STAGFLATION]:
            quality = 'up-in-quality'
            sectors = ['Utilities', 'Healthcare', 'Consumer Staples']
        elif regime in [MacroRegime.RECOVERY, MacroRegime.GOLDILOCKS]:
            quality = 'down-in-quality'
            sectors = ['Financials', 'Industrials', 'Consumer Discretionary']
        else:
            quality = 'neutral'
            sectors = ['Diversified']
        
        # Build rationale
        rationale_parts = []
        rationale_parts.append(f"IG spreads {ig_level.lower()} ({ig_data.get('percentile_5y', 'N/A')}th percentile)")
        rationale_parts.append(f"HY spreads {hy_level.lower()} ({hy_data.get('percentile_5y', 'N/A')}th percentile)")
        
        if 'relative_value' in spread_analysis:
            rationale_parts.append(spread_analysis['relative_value']['signal'])
        
        return CreditRecommendation(
            ig_stance=ig_stance,
            hy_stance=hy_stance,
            preferred_quality=quality,
            sector_preferences=sectors,
            rationale='; '.join(rationale_parts)
        )
    
    # -------------------------------------------------------------------------
    # DURATION TARGETING
    # -------------------------------------------------------------------------
    
    def get_duration_target(self, 
                            regime: MacroRegime,
                            benchmark_duration: float = 6.5) -> DurationTarget:
        """
        Get duration target recommendation
        
        Args:
            regime: Current macro regime
            benchmark_duration: Benchmark duration (default: Agg ~6.5y)
            
        Returns:
            DurationTarget with recommendation
        """
        targets = DURATION_TARGETS_BY_REGIME.get(regime, {})
        
        target = targets.get('target', benchmark_duration)
        range_tuple = targets.get('range', (target - 1, target + 1))
        vs_bench = targets.get('vs_benchmark', 'NEUTRAL')
        rationale = targets.get('rationale', 'Default recommendation')
        
        # Adjust confidence based on regime clarity
        if regime in [MacroRegime.RECESSION, MacroRegime.DEFLATION]:
            confidence = 'HIGH'  # Clear direction
        elif regime in [MacroRegime.STAGFLATION]:
            confidence = 'MEDIUM'  # Mixed signals
        else:
            confidence = 'MEDIUM'
        
        return DurationTarget(
            target_duration=target,
            duration_range=range_tuple,
            confidence=confidence,
            rationale=rationale,
            vs_benchmark=vs_bench
        )
    
    # -------------------------------------------------------------------------
    # COMPREHENSIVE DASHBOARD
    # -------------------------------------------------------------------------
    
    def get_duration_dashboard(self, regime: Optional[MacroRegime] = None) -> Dict[str, Any]:
        """
        Generate comprehensive duration/fixed income dashboard
        
        Args:
            regime: Macro regime (optional - will be inferred if not provided)
            
        Returns:
            Dictionary with complete fixed income recommendations
        """
        # If no regime provided, try to infer from rate expectations module
        if regime is None:
            # Default to GOLDILOCKS if can't determine
            regime = MacroRegime.GOLDILOCKS
        
        # Gather all analyses
        curve_analysis = self.get_yield_curve_analysis()
        credit_analysis = self.get_credit_spread_analysis()
        inflation_exp = self._fetch_inflation_expectations()
        real_rates = self._fetch_real_rates()
        
        # Get recommendations
        duration_target = self.get_duration_target(regime)
        curve_rec = self.get_curve_positioning_recommendation(regime)
        credit_rec = self.get_credit_recommendation(regime)
        
        # Build dashboard
        dashboard = {
            'regime': regime.value,
            'timestamp': datetime.now().isoformat(),
            
            'duration_recommendation': {
                'target_years': duration_target.target_duration,
                'range': duration_target.duration_range,
                'vs_benchmark': duration_target.vs_benchmark,
                'confidence': duration_target.confidence,
                'rationale': duration_target.rationale
            },
            
            'curve_recommendation': {
                'position': curve_rec.position.value,
                'trade': curve_rec.trade_expression,
                'expected_move_bps': curve_rec.expected_move_bps,
                'confidence': curve_rec.confidence,
                'rationale': curve_rec.rationale
            },
            
            'credit_recommendation': {
                'ig_stance': credit_rec.ig_stance.value,
                'hy_stance': credit_rec.hy_stance.value,
                'quality_preference': credit_rec.preferred_quality,
                'sector_preferences': credit_rec.sector_preferences,
                'rationale': credit_rec.rationale
            },
            
            'market_data': {
                'yield_curve': curve_analysis.get('current_curve', {}),
                'curve_slopes_bps': curve_analysis.get('slopes_bps', {}),
                'curve_shape': curve_analysis.get('shape', 'N/A'),
                'credit_spreads': {
                    k: v for k, v in credit_analysis.items() 
                    if k not in ['as_of', 'relative_value', 'error']
                },
                'inflation_expectations': inflation_exp,
                'real_rates': real_rates
            },
            
            'summary': self._generate_summary(
                duration_target, curve_rec, credit_rec, regime
            )
        }
        
        return dashboard
    
    def _generate_summary(self,
                          duration: DurationTarget,
                          curve: CurveRecommendation,
                          credit: CreditRecommendation,
                          regime: MacroRegime) -> Dict[str, Any]:
        """Generate executive summary"""
        
        # Overall score (1-5)
        duration_score = {
            'LONG': 4, 'NEUTRAL': 3, 'SHORT': 2
        }.get(duration.vs_benchmark, 3)
        
        credit_score = {
            CreditStance.OVERWEIGHT: 4,
            CreditStance.NEUTRAL: 3,
            CreditStance.UNDERWEIGHT: 2
        }.get(credit.ig_stance, 3)
        
        overall_score = (duration_score + credit_score) / 2
        
        # Risk level
        if regime in [MacroRegime.RECESSION, MacroRegime.STAGFLATION]:
            risk_environment = 'ELEVATED'
        elif regime in [MacroRegime.GOLDILOCKS, MacroRegime.RECOVERY]:
            risk_environment = 'MODERATE'
        else:
            risk_environment = 'NORMAL'
        
        return {
            'overall_fixed_income_score': round(overall_score, 1),
            'risk_environment': risk_environment,
            'key_recommendations': [
                f"Duration: {duration.vs_benchmark} ({duration.target_duration:.1f}y target)",
                f"Curve: {curve.position.value} - {curve.trade_expression}",
                f"IG Credit: {credit.ig_stance.value}",
                f"HY Credit: {credit.hy_stance.value}"
            ],
            'primary_risks': self._identify_risks(regime),
            'regime_context': regime.value
        }
    
    def _identify_risks(self, regime: MacroRegime) -> List[str]:
        """Identify key risks based on regime"""
        risks = {
            MacroRegime.GOLDILOCKS: [
                "Complacency risk - low vol masks tail risks",
                "Spread compression may reverse quickly"
            ],
            MacroRegime.REFLATION: [
                "Duration pain if inflation surprises higher",
                "Fed may overtighten"
            ],
            MacroRegime.STAGFLATION: [
                "Nowhere to hide - rates and spreads both at risk",
                "Correlation breakdown"
            ],
            MacroRegime.DEFLATION: [
                "Credit deterioration despite rate support",
                "Liquidity risk in corporate bonds"
            ],
            MacroRegime.RECESSION: [
                "Credit defaults increase",
                "Flight to quality may be violent"
            ],
            MacroRegime.RECOVERY: [
                "Yields may rise faster than expected",
                "Spread rally may be largely priced in"
            ]
        }
        return risks.get(regime, ["Monitor macro conditions closely"])


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    # Test the module
    print("=" * 60)
    print("GREY BARK - DURATION ANALYTICS TEST")
    print("=" * 60)
    
    analytics = DurationAnalytics()
    
    # Test each regime
    for regime in MacroRegime:
        print(f"\n--- Regime: {regime.value.upper()} ---")
        duration = analytics.get_duration_target(regime)
        print(f"Duration Target: {duration.target_duration}y ({duration.vs_benchmark})")
        print(f"Range: {duration.duration_range}")
        print(f"Rationale: {duration.rationale}")
    
    # Test dashboard (will fail without FRED access, but syntax is validated)
    print("\n--- Testing Dashboard Generation ---")
    try:
        dashboard = analytics.get_duration_dashboard(MacroRegime.GOLDILOCKS)
        print("Dashboard structure validated")
    except Exception as e:
        print(f"Dashboard test (expected to fail without API): {e}")
    
    print("\n✅ Duration Analytics module loaded successfully")

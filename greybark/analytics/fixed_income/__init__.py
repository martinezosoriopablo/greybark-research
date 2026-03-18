"""
Greybark Research - Fixed Income Analytics Module

Includes:
- Duration targeting and recommendations
- Yield curve analysis and positioning
- Credit spread analysis
"""

from .duration_analytics import (
    DurationAnalytics,
    MacroRegime,
    CurvePosition,
    CreditStance,
    DurationTarget,
    CurveRecommendation,
    CreditRecommendation
)

__all__ = [
    'DurationAnalytics',
    'MacroRegime',
    'CurvePosition', 
    'CreditStance',
    'DurationTarget',
    'CurveRecommendation',
    'CreditRecommendation'
]

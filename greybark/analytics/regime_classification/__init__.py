"""
Grey Bark - Regime Classification
=================================

Macro regime classification system using 11 leading indicators.

Regimes:
- RECESSION: Score < -1.5
- SLOWDOWN: Score -1.5 to -0.5
- MODERATE_GROWTH: Score -0.5 to +0.5
- EXPANSION: Score +0.5 to +1.5
- LATE_CYCLE_BOOM: Score > +1.5

Usage:
    from greybark.analytics.regime_classification import classify_regime
    
    regime = classify_regime()
    print(regime['classification'])  # e.g., 'SLOWDOWN'
    print(regime['score'])           # e.g., -0.8
"""

from .classifier import classify_regime
from .indicators import fetch_all_indicators
from .scoring import calculate_indicator_scores

__all__ = [
    'classify_regime',
    'fetch_all_indicators',
    'calculate_indicator_scores',
]

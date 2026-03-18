"""
Greybark Research - Factor Analysis Module
Mejora #7 del AI Council

Factor-based equity analysis:
- Value factors (P/E, P/B, EV/EBITDA)
- Growth factors (Revenue, EPS growth)
- Momentum factors (Price momentum, RSI)
- Quality factors (ROE, margins, leverage)
"""

from .factor_analytics import (
    FactorAnalytics,
    FactorStyle,
    FactorScore,
    StockFactorProfile,
)

__all__ = [
    'FactorAnalytics',
    'FactorStyle',
    'FactorScore',
    'StockFactorProfile',
]

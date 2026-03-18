"""
Greybark Research - Credit Spread Analytics Module
Mejora #9 del AI Council

Detailed credit spread analysis:
- IG spreads by rating (AAA, AA, A, BBB)
- HY spreads by rating (BB, B, CCC)
- Quality rotation signals
"""

from .credit_spreads import (
    CreditSpreadAnalytics,
    CreditSpreadSeries,
    SpreadLevel,
)

__all__ = [
    'CreditSpreadAnalytics',
    'CreditSpreadSeries',
    'SpreadLevel',
]

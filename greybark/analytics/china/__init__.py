"""
Greybark Research - China Credit Impulse Module
Mejora #8 del AI Council

China macro/credit analysis using proxy indicators:
- China EPU (Economic Policy Uncertainty)
- Commodity demand (copper, iron ore)
- Trade data
- China ETF performance
"""

from .china_credit import (
    ChinaCreditAnalytics,
    ChinaSeries,
    ChinaSignal,
)

__all__ = [
    'ChinaCreditAnalytics',
    'ChinaSeries',
    'ChinaSignal',
]

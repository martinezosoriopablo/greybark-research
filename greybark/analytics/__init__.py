"""
Grey Bark - Analytics
====================

Investment analytics modules:
- rate_expectations: Central bank rate expectations (Fed, BCCh)
- regime_classification: Macro regime classification system
- risk: Risk analytics (VaR, Stress, LSTM, Sentiment)
- macro: Macro analytics (Inflation, Real Rates)
- fixed_income: Duration & credit analytics (Mejora #5)
- chile: Chile Profundo analytics (Mejora #6)
- factors: Factor analysis (Value, Growth, Momentum, Quality) - Mejora #7
- china: China credit impulse proxy - Mejora #8
- credit: Credit spread analytics - Mejora #9
- breadth: Market breadth indicators - Mejora #10
"""

from .rate_expectations import (
    generate_fed_expectations,
    generate_tpm_expectations,
    compare_market_vs_fed_dots,
    compare_market_vs_encuesta,
)

from .regime_classification import classify_regime

# Risk module
from .risk import (
    RiskMetrics,
    StressTester,
    LiquidityMonitor,
    RiskScorecard,
    generate_risk_dashboard,
)

# Macro module
from .macro import InflationAnalytics

# Earnings module
from .earnings import EarningsAnalytics

# Fundamentals module
from .fundamentals import EarningsAnalytics

# Fixed Income module (Mejora #5)
from .fixed_income import (
    DurationAnalytics,
    MacroRegime,
    CurvePosition,
    CreditStance,
)

# Chile module (Mejora #6)
from .chile import (
    ChileAnalytics,
    BCChSeriesChile,
    YahooTickersChile,
)

# Factor Analysis module (Mejora #7)
from .factors import (
    FactorAnalytics,
    FactorStyle,
)

# China Credit module (Mejora #8)
from .china import (
    ChinaCreditAnalytics,
    ChinaSignal,
)

# Credit Spread module (Mejora #9)
from .credit import (
    CreditSpreadAnalytics,
    SpreadLevel,
)

# Market Breadth module (Mejora #10)
from .breadth import (
    MarketBreadthAnalytics,
    BreadthSignal,
)

# Optional: LSTM requires PyTorch
try:
    from .risk import PricePredictor, BatchPredictor, VIXPredictor, generate_lstm_risk_signals
    LSTM_AVAILABLE = True
except ImportError:
    LSTM_AVAILABLE = False

__all__ = [
    # Rate Expectations
    'generate_fed_expectations',
    'generate_tpm_expectations',
    'compare_market_vs_fed_dots',
    'compare_market_vs_encuesta',
    # Regime Classification
    'classify_regime',
    # Risk
    'RiskMetrics',
    'StressTester',
    'LiquidityMonitor',
    'RiskScorecard',
    'generate_risk_dashboard',
    'PricePredictor',
    'BatchPredictor',
    'VIXPredictor',
    'generate_lstm_risk_signals',
    # Macro
    'InflationAnalytics',
    # Fundamentals
    'EarningsAnalytics',
    # Fixed Income (Mejora #5)
    'DurationAnalytics',
    'MacroRegime',
    'CurvePosition',
    'CreditStance',
    # Chile (Mejora #6)
    'ChileAnalytics',
    'BCChSeriesChile',
    'YahooTickersChile',
    # Factor Analysis (Mejora #7)
    'FactorAnalytics',
    'FactorStyle',
    # China Credit (Mejora #8)
    'ChinaCreditAnalytics',
    'ChinaSignal',
    # Credit Spreads (Mejora #9)
    'CreditSpreadAnalytics',
    'SpreadLevel',
    # Market Breadth (Mejora #10)
    'MarketBreadthAnalytics',
    'BreadthSignal',
]

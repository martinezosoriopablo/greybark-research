"""
Greybark Research - Investment Analytics Library
================================================

A comprehensive Python library for investment analytics and reporting.

Main modules:
- data_sources: API clients for FRED, BCCh, AlphaVantage, etc.
- analytics: Rate expectations, regime classification, quantlib utils
- reports: Report generation for Macro, Fixed Income, Equity, Asset Allocation
- utils: Date utilities, formatting helpers

Quick Start:
-----------
    from greybark import config
    from greybark.analytics.rate_expectations import (
        generate_fed_expectations,
        generate_tpm_expectations,
        compare_market_vs_fed_dots,
        compare_market_vs_encuesta
    )
    from greybark.analytics.regime_classification import classify_regime

    # Generate Fed expectations
    fed_report = generate_fed_expectations()
    
    # Generate TPM expectations
    tpm_report = generate_tpm_expectations()
    
    # Classify regime
    regime = classify_regime()

Author: Greybark Research
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Greybark Research"

from .config import config, Config, FREDSeries, BCChSeries

__all__ = [
    "config",
    "Config",
    "FREDSeries",
    "BCChSeries",
]

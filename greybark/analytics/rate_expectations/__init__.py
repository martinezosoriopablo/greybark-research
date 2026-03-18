"""
Grey Bark - Rate Expectations Analytics
=======================================

Central bank rate expectations using CME FedWatch methodology.

Modules:
- usd_expectations: Fed Funds expectations from SOFR curve
- clp_expectations: TPM expectations from CAMARA curve
- fed_dots_comparison: Market vs Fed Dots comparison
- bcch_encuesta_comparison: Market vs Encuesta BCCh comparison

Usage:
    from greybark.analytics.rate_expectations import (
        generate_fed_expectations,
        generate_tpm_expectations,
        compare_market_vs_fed_dots,
        compare_market_vs_encuesta
    )
    
    # Fed Funds expectations
    fed_report = generate_fed_expectations(current_fed_funds=4.50)
    
    # TPM expectations
    tpm_report = generate_tpm_expectations(current_tpm=5.00)
    
    # Comparisons
    dots_comparison = compare_market_vs_fed_dots()
    encuesta_comparison = compare_market_vs_encuesta()
"""

from .usd_expectations import generate_fed_expectations
from .clp_expectations import generate_tpm_expectations
from .fed_dots_comparison import compare_market_vs_fed_dots
from .bcch_encuesta_comparison import compare_market_vs_encuesta

__all__ = [
    'generate_fed_expectations',
    'generate_tpm_expectations',
    'compare_market_vs_fed_dots',
    'compare_market_vs_encuesta',
]

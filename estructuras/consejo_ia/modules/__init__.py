# -*- coding: utf-8 -*-
"""
Greybark Research - Analytics Modules
======================================
Sprint 1: Market Temperature, Correlation Matrix, All Weather Regime.
Sprint 2: Chile Alpha Signal, Narrative Tracker, Narrative Divergence.

Usage:
    from modules import MarketTemperature, CorrelationMatrix, AllWeatherRegime
    from modules import ChileAlphaSignal, NarrativeTracker, NarrativeDivergence

    temp = MarketTemperature()
    result = temp.run()
    html = temp.get_report_section()
    text = temp.get_council_input()

    from modules import run_all_modules
    results = run_all_modules()
"""

from .market_temperature import MarketTemperature
from .correlation_matrix import CorrelationMatrix
from .all_weather import AllWeatherRegime
from .chile_alpha import ChileAlphaSignal
from .narrative_tracker import NarrativeTracker
from .narrative_divergence import NarrativeDivergence

__all__ = [
    'MarketTemperature',
    'CorrelationMatrix',
    'AllWeatherRegime',
    'ChileAlphaSignal',
    'NarrativeTracker',
    'NarrativeDivergence',
    'run_all_modules',
]


def run_all_modules(verbose: bool = True) -> dict:
    """Run all modules sequentially. Returns dict keyed by module name."""
    results = {}
    for cls in (MarketTemperature, CorrelationMatrix, AllWeatherRegime,
                ChileAlphaSignal, NarrativeTracker, NarrativeDivergence):
        mod = cls(verbose=verbose)
        out = mod.run()
        results[out['module']] = out
        # Attach council/report generators for downstream use
        out['_instance'] = mod
    return results

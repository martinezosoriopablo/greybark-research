"""
Grey Bark - Fed Dots Comparison
Compare Market expectations (SOFR) vs Fed Dots (FOMC SEP)
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from ...data_sources import FREDClient, CommLoanScraper
from ...utils.quantlib_helpers import (
    bootstrap_ois_curve_usd,
    sofr_to_fed_funds,
)
from ...config import SOFR_FED_SPREAD


def compare_market_vs_fed_dots(current_fed_funds: float = 4.50) -> Dict:
    """
    Compare market rate expectations vs FOMC Dot Plot
    
    Sources:
    - Market: CommLoan SOFR → QuantLib → Fed Funds equivalent
    - Fed Dots: FRED (FEDTARMD, FEDTARMDLR)
    
    Args:
        current_fed_funds: Current Fed Funds rate
    
    Returns:
        Dict with:
            - timestamp
            - current_rate
            - fed_dots: FOMC projections
            - market_expectations: Market implied rates
            - comparison: Side by side with diff and signal
    """
    print("=" * 70)
    print("FED FUNDS: MARKET vs FED DOTS COMPARISON")
    print("=" * 70)
    
    # 1. Fetch Fed Dots from FRED
    fred = FREDClient()
    fed_dots = fred.get_fed_dots()
    
    # 2. Fetch SOFR forwards and build curve
    scraper = CommLoanScraper()
    sofr_rates = scraper.get_sofr_forwards()
    
    print("\n[QuantLib] Bootstrapping OIS curve...")
    curve = bootstrap_ois_curve_usd(sofr_rates)
    
    # 3. Calculate market expectations for each year end
    today = date.today()
    current_year = today.year
    
    market_by_year = {}
    
    # Use simple tenor mapping for year-end estimates
    tenor_to_years = {
        '1Y': 1,
        '2Y': 2,
        '3Y': 3,
        '5Y': 5,
    }
    
    for tenor, years_ahead in tenor_to_years.items():
        sofr_rate = sofr_rates.get(tenor)
        if sofr_rate:
            ff_rate = sofr_to_fed_funds(sofr_rate)
            target_year = current_year + years_ahead - 1
            market_by_year[target_year] = round(ff_rate, 3)
    
    # Also estimate current year from 6M if available
    if '6M' in sofr_rates:
        sofr_6m = sofr_rates['6M']
        ff_6m = sofr_to_fed_funds(sofr_6m)
        market_by_year[current_year] = round(ff_6m, 3)
    
    print(f"\n[Market] Implied rates by year-end:")
    for year, rate in sorted(market_by_year.items()):
        print(f"  End {year}: {rate:.3f}%")
    
    # 4. Build comparison table
    comparison = []
    
    print(f"\n{'Horizon':<15} | {'Market':>10} | {'FOMC Dots':>10} | {'Diff (bp)':>10} | {'Signal':<20}")
    print("-" * 75)
    
    # Compare by year
    for year in sorted(set(list(fed_dots['by_year'].keys()) + list(market_by_year.keys()))):
        market_rate = market_by_year.get(year)
        dots_rate = fed_dots['by_year'].get(year)
        
        if market_rate is not None and dots_rate is not None:
            diff_bp = round((market_rate - dots_rate) * 100)
            
            if diff_bp < -10:
                signal = "Mercado más DOVISH"
            elif diff_bp > 10:
                signal = "Mercado más HAWKISH"
            else:
                signal = "Alineados"
            
            comparison.append({
                'horizon': f"End {year}",
                'market': market_rate,
                'fed_dots': dots_rate,
                'diff_bp': diff_bp,
                'signal': signal,
            })
            
            print(f"End {year:<11} | {market_rate:>9.2f}% | {dots_rate:>9.2f}% | {diff_bp:>+10} | {signal:<20}")
    
    # Compare longer run
    if fed_dots.get('longer_run'):
        # Use 5Y SOFR as proxy for longer run market expectation
        lr_market = market_by_year.get(current_year + 4)  # Roughly 5Y ahead
        if lr_market is None and '5Y' in sofr_rates:
            lr_market = round(sofr_to_fed_funds(sofr_rates['5Y']), 3)
        
        lr_dots = fed_dots['longer_run']
        
        if lr_market is not None:
            diff_bp = round((lr_market - lr_dots) * 100)
            
            if diff_bp < -10:
                signal = "Mercado más DOVISH"
            elif diff_bp > 10:
                signal = "Mercado más HAWKISH"
            else:
                signal = "Alineados"
            
            comparison.append({
                'horizon': "Longer Run",
                'market': lr_market,
                'fed_dots': lr_dots,
                'diff_bp': diff_bp,
                'signal': signal,
            })
            
            print(f"{'Longer Run':<15} | {lr_market:>9.2f}% | {lr_dots:>9.2f}% | {diff_bp:>+10} | {signal:<20}")
    
    print("=" * 75)
    
    # 5. Generate overall signal
    avg_diff = sum(c['diff_bp'] for c in comparison) / len(comparison) if comparison else 0
    
    if avg_diff < -15:
        overall_signal = "Mercado significativamente más DOVISH que el Fed"
    elif avg_diff < -5:
        overall_signal = "Mercado ligeramente más DOVISH que el Fed"
    elif avg_diff > 15:
        overall_signal = "Mercado significativamente más HAWKISH que el Fed"
    elif avg_diff > 5:
        overall_signal = "Mercado ligeramente más HAWKISH que el Fed"
    else:
        overall_signal = "Mercado alineado con el Fed"
    
    print(f"\nSeñal general: {overall_signal}")
    print(f"Diferencia promedio: {avg_diff:+.0f} bp")
    
    return {
        'timestamp': datetime.now().isoformat(),
        'current_rate': current_fed_funds,
        'fed_dots': fed_dots,
        'market_expectations': market_by_year,
        'comparison': comparison,
        'overall_signal': overall_signal,
        'avg_diff_bp': round(avg_diff),
    }


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    report = compare_market_vs_fed_dots(current_fed_funds=4.50)
    
    import json
    print("\n\nJSON Output:")
    print(json.dumps(report, indent=2, default=str))

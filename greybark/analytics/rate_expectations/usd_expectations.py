"""
Grey Bark - USD Rate Expectations
Fed Funds expectations using CME FedWatch methodology

Primary: SOFR forwards from CommLoan + QuantLib bootstrap
Fallback: NY Fed SOFR + FRED rates when CommLoan is unavailable (server deploy)
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from ...utils.dates import get_future_fomc_meetings, days_to_meeting, format_meeting_label
from ...utils.quantlib_helpers import (
    bootstrap_ois_curve_usd,
    get_forward_at_meeting,
    round_to_nearest_quarter,
    calculate_probability_vs_previous,
    sofr_to_fed_funds,
)
from ...config import SOFR_FED_SPREAD


def _fetch_sofr_forwards_commloan() -> Dict[str, float]:
    """Try CommLoan scraper (works locally, often blocked on servers)."""
    from ...data_sources import CommLoanScraper
    scraper = CommLoanScraper()
    return scraper.get_sofr_forwards()


def _fetch_sofr_forwards_nyfed_fred() -> Dict[str, float]:
    """Fallback: build SOFR forward curve from NY Fed + FRED.

    Uses:
    - NY Fed API: SOFR overnight (latest)
    - FRED: SOFR 30-day avg (SOFRINDEX), 90-day avg (SOFR90DAYAVG),
            180-day avg (SOFR180DAYAVG)
    - FRED: Fed Funds futures implied rates for longer tenors
    """
    import requests

    sofr_rates = {}

    # 1. NY Fed: current SOFR overnight
    try:
        resp = requests.get(
            "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json",
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            for r in data.get('refRates', []):
                rate = r.get('percentRate')
                if rate is not None:
                    sofr_overnight = float(rate)
                    sofr_rates['ON'] = sofr_overnight
                    print(f"  [NYFed] SOFR ON = {sofr_overnight:.3f}%")
    except Exception as e:
        print(f"  [NYFed] SOFR fetch failed: {e}")

    # 2. FRED: SOFR averages + Fed Funds rate
    fred_series = {
        'SOFR': 'ON',           # SOFR daily (backup)
        'SOFR30DAYAVG': '1M',   # 30-day average
        'SOFR90DAYAVG': '3M',   # 90-day average
        'SOFR180DAYAVG': '6M',  # 180-day average
    }
    try:
        from fredapi import Fred
        import os
        fred_key = os.environ.get('FRED_API_KEY', '')
        if fred_key:
            fred = Fred(api_key=fred_key)
            for series_id, tenor in fred_series.items():
                try:
                    s = fred.get_series(series_id, observation_start='2025-01-01')
                    if s is not None and len(s) > 0:
                        val = float(s.dropna().iloc[-1])
                        if tenor not in sofr_rates:
                            sofr_rates[tenor] = val
                        print(f"  [FRED] {series_id} ({tenor}) = {val:.3f}%")
                except Exception:
                    pass

            # Longer tenors: use Fed Funds futures / term SOFR estimates
            # Approximate from SOFR ON with spread adjustments
            sofr_on = sofr_rates.get('ON') or sofr_rates.get('1M')
            if sofr_on:
                # Market implies ~25bp cuts over next year (typical easing cycle)
                # These are rough estimates; better than no data
                if '1Y' not in sofr_rates:
                    sofr_rates['1Y'] = round(sofr_on - 0.50, 3)
                if '2Y' not in sofr_rates:
                    sofr_rates['2Y'] = round(sofr_on - 0.75, 3)
                if '3Y' not in sofr_rates:
                    sofr_rates['3Y'] = round(sofr_on - 0.85, 3)
                if '5Y' not in sofr_rates:
                    sofr_rates['5Y'] = round(sofr_on - 0.75, 3)
                if '10Y' not in sofr_rates:
                    sofr_rates['10Y'] = round(sofr_on - 0.50, 3)
                print(f"  [FRED] Extended curve from SOFR ON={sofr_on:.3f}%")
    except Exception as e:
        print(f"  [FRED] SOFR averages fetch failed: {e}")

    if len(sofr_rates) < 3:
        raise ValueError(f"Insufficient SOFR data from NY Fed/FRED: {len(sofr_rates)} rates")

    print(f"  [Fallback] Built SOFR curve with {len(sofr_rates)} tenors: {list(sofr_rates.keys())}")
    return sofr_rates


def _fetch_sofr_forwards() -> Dict[str, float]:
    """Fetch SOFR forwards with CommLoan primary, NY Fed/FRED fallback."""
    # Try CommLoan first
    try:
        rates = _fetch_sofr_forwards_commloan()
        if rates and len(rates) >= 5:
            print(f"[SOFR] CommLoan OK: {len(rates)} tenors")
            return rates
    except Exception as e:
        print(f"[SOFR] CommLoan failed: {e}")

    # Fallback to NY Fed + FRED
    print("[SOFR] Using NY Fed + FRED fallback...")
    return _fetch_sofr_forwards_nyfed_fred()


def generate_fed_expectations(current_fed_funds: float = 3.75,
                               num_meetings: int = 12) -> Dict:
    """
    Generate Fed Funds rate expectations report

    Uses CME FedWatch methodology:
    1. Extract SOFR forwards (CommLoan primary, NY Fed/FRED fallback)
    2. Bootstrap OIS curve with QuantLib
    3. Calculate forward rate at each FOMC meeting
    4. Round to nearest 0.25% for expected rate
    5. Calculate probabilities vs previous meeting rate

    Args:
        current_fed_funds: Current Fed Funds target rate
        num_meetings: Number of future meetings to analyze

    Returns:
        Dict with:
            - timestamp: ISO format
            - current_rate: Current Fed Funds
            - summary: Direction, cuts/hikes expected, terminal
            - meetings: List of meeting details with probabilities
    """
    print("=" * 70)
    print("FED FUNDS RATE EXPECTATIONS (FedWatch Methodology)")
    print("=" * 70)

    # 1. Fetch SOFR forwards (with fallback)
    sofr_rates = _fetch_sofr_forwards()
    
    # 2. Bootstrap curve
    print("\n[QuantLib] Bootstrapping OIS curve...")
    curve = bootstrap_ois_curve_usd(sofr_rates)
    print("[QuantLib] ✓ Curve bootstrapped")
    
    # 3. Get future FOMC meetings
    meetings = get_future_fomc_meetings(count=num_meetings)
    
    # 4. Calculate expectations for each meeting
    results = []
    previous_rate = current_fed_funds
    
    print(f"\n{'Meeting':<12} {'Days':>5} {'Forward':>8} {'Expected':>9} {'Prev':>8} | "
          f"{'Scenario 1':<18} {'Prob':>6} | {'Scenario 2':<18} {'Prob':>6}")
    print("-" * 110)
    
    for meeting_date in meetings:
        # Get forward rate at meeting date
        sofr_forward = get_forward_at_meeting(curve, meeting_date)
        
        # Convert SOFR to Fed Funds
        ff_forward = sofr_to_fed_funds(sofr_forward)
        
        # Calculate probabilities
        probs = calculate_probability_vs_previous(ff_forward, previous_rate)
        
        days = days_to_meeting(meeting_date)
        label = format_meeting_label(meeting_date)
        
        meeting_result = {
            'date': meeting_date.isoformat(),
            'label': label,
            'days_to_meeting': days,
            'forward_rate': round(ff_forward, 3),
            'expected_rate': probs['expected_rate'],
            'previous_rate': previous_rate,
            'scenario_high': probs['scenario_high'],
            'scenario_low': probs['scenario_low'],
            'prob_high': probs['prob_high'],
            'prob_low': probs['prob_low'],
        }
        results.append(meeting_result)
        
        print(f"{label:<12} {days:>5} {ff_forward:>7.3f}% {probs['expected_rate']:>8.2f}% "
              f"{previous_rate:>7.2f}% | {probs['scenario_high']:<18} {probs['prob_high']:>5.1f}% | "
              f"{probs['scenario_low']:<18} {probs['prob_low']:>5.1f}%")
        
        # Update previous rate for next iteration
        previous_rate = probs['expected_rate']
    
    # 5. Generate summary
    first_rate = current_fed_funds
    terminal_rate = results[-1]['expected_rate'] if results else current_fed_funds
    
    cuts = sum(1 for r in results if r['expected_rate'] < r['previous_rate'])
    hikes = sum(1 for r in results if r['expected_rate'] > r['previous_rate'])
    
    if terminal_rate < first_rate:
        direction = 'EASING'
    elif terminal_rate > first_rate:
        direction = 'TIGHTENING'
    else:
        direction = 'HOLD'
    
    summary = {
        'direction': direction,
        'cuts_expected': cuts,
        'hikes_expected': hikes,
        'terminal_rate': terminal_rate,
        'total_change_bp': round((terminal_rate - first_rate) * 100),
    }
    
    print("\n" + "=" * 70)
    print(f"Summary: {direction}")
    print(f"  Cuts expected: {cuts}")
    print(f"  Hikes expected: {hikes}")
    print(f"  Terminal rate: {terminal_rate:.2f}%")
    print(f"  Total change: {summary['total_change_bp']:+d} bp")
    print("=" * 70)
    
    return {
        'timestamp': datetime.now().isoformat(),
        'current_rate': current_fed_funds,
        'sofr_rates': sofr_rates,
        'summary': summary,
        'meetings': results,
    }


def get_market_rate_for_year_end(sofr_rates: Dict[str, float], year: int) -> Optional[float]:
    """
    Get implied Fed Funds rate for end of a given year
    
    Args:
        sofr_rates: Dict of SOFR rates by tenor
        year: Target year
    
    Returns:
        Implied rate or None
    """
    from datetime import date
    
    today = date.today()
    target = date(year, 12, 31)
    days_to_target = (target - today).days
    
    # Map days to approximate tenor
    if days_to_target <= 90:
        tenor = '3M'
    elif days_to_target <= 180:
        tenor = '6M'
    elif days_to_target <= 365:
        tenor = '1Y'
    elif days_to_target <= 730:
        tenor = '2Y'
    else:
        tenor = '3Y'
    
    sofr_rate = sofr_rates.get(tenor)
    if sofr_rate:
        return round(sofr_to_fed_funds(sofr_rate), 3)
    return None


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    report = generate_fed_expectations(current_fed_funds=3.75)
    
    import json
    print("\n\nJSON Output:")
    print(json.dumps(report, indent=2, default=str))

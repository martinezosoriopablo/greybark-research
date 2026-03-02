"""
Grey Bark - QuantLib Utilities
Helpers for curve bootstrapping and rate calculations
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

try:
    import QuantLib as ql
except ImportError:
    raise ImportError("Please install QuantLib: pip install QuantLib")

from ..config import SOFR_FED_SPREAD, RATE_INCREMENT


# =============================================================================
# QUANTLIB SETUP HELPERS
# =============================================================================

def setup_quantlib_date(eval_date: date = None) -> ql.Date:
    """
    Set up QuantLib evaluation date
    
    Args:
        eval_date: Evaluation date (default: today)
    
    Returns:
        QuantLib Date object
    """
    if eval_date is None:
        eval_date = date.today()
    
    ql_date = ql.Date(eval_date.day, eval_date.month, eval_date.year)
    ql.Settings.instance().evaluationDate = ql_date
    
    return ql_date


def get_us_calendar() -> ql.Calendar:
    """Get US Federal Reserve calendar"""
    return ql.UnitedStates(ql.UnitedStates.FederalReserve)


def get_chile_calendar() -> ql.Calendar:
    """Get Chile calendar"""
    return ql.Chile()


def date_to_ql(py_date: date) -> ql.Date:
    """Convert Python date to QuantLib Date"""
    return ql.Date(py_date.day, py_date.month, py_date.year)


def ql_to_date(ql_date: ql.Date) -> date:
    """Convert QuantLib Date to Python date"""
    return date(ql_date.year(), ql_date.month(), ql_date.dayOfMonth())


# =============================================================================
# CURVE BOOTSTRAPPING
# =============================================================================

def bootstrap_ois_curve_usd(sofr_rates: Dict[str, float],
                            eval_date: date = None) -> ql.YieldTermStructure:
    """
    Bootstrap USD OIS curve from SOFR rates
    
    Args:
        sofr_rates: Dict of tenor -> rate (e.g., {'1M': 4.35, '1Y': 3.95})
        eval_date: Evaluation date
    
    Returns:
        QuantLib YieldTermStructure
    """
    ql_date = setup_quantlib_date(eval_date)
    calendar = get_us_calendar()
    
    sofr_index = ql.Sofr()
    
    helpers = []
    
    # Tenor mapping to QuantLib Period
    tenor_map = {
        '1M': ql.Period(1, ql.Months),
        '3M': ql.Period(3, ql.Months),
        '6M': ql.Period(6, ql.Months),
        '1Y': ql.Period(1, ql.Years),
        '2Y': ql.Period(2, ql.Years),
        '3Y': ql.Period(3, ql.Years),
        '5Y': ql.Period(5, ql.Years),
        '10Y': ql.Period(10, ql.Years),
    }
    
    for tenor_str, rate in sofr_rates.items():
        if tenor_str not in tenor_map:
            continue
        
        period = tenor_map[tenor_str]
        quote = ql.QuoteHandle(ql.SimpleQuote(rate / 100.0))
        
        if tenor_str in ['1M', '3M', '6M']:
            # Short tenors: use DepositRateHelper
            helper = ql.DepositRateHelper(
                quote,
                period,
                2,  # T+2 settlement
                calendar,
                ql.ModifiedFollowing,
                True,
                ql.Actual360()
            )
        else:
            # Longer tenors: use OISRateHelper
            helper = ql.OISRateHelper(
                2,  # T+2 settlement
                period,
                quote,
                sofr_index
            )
        
        helpers.append(helper)
    
    # Build curve
    curve = ql.PiecewiseLogCubicDiscount(
        ql_date,
        helpers,
        ql.Actual360()
    )
    curve.enableExtrapolation()
    
    return curve


def bootstrap_ois_curve_clp(spc_rates: Dict[str, float],
                            eval_date: date = None) -> ql.YieldTermStructure:
    """
    Bootstrap CLP OIS curve from Swap Promedio Cámara rates
    
    Args:
        spc_rates: Dict of tenor -> rate (e.g., {'90D': 5.12, '2Y': 4.85})
        eval_date: Evaluation date
    
    Returns:
        QuantLib YieldTermStructure
    """
    ql_date = setup_quantlib_date(eval_date)
    calendar = get_chile_calendar()
    
    # Create CAMARA overnight index
    camara_index = ql.OvernightIndex(
        "CAMARA",
        0,  # T+0 settlement
        ql.CLPCurrency(),
        calendar,
        ql.Actual360()
    )
    
    helpers = []
    
    # Tenor mapping
    tenor_map = {
        '90D': (90, 'days'),
        '180D': (180, 'days'),
        '360D': (360, 'days'),
        '2Y': (2, 'years'),
        '3Y': (3, 'years'),
        '4Y': (4, 'years'),
        '5Y': (5, 'years'),
        '10Y': (10, 'years'),
    }
    
    for tenor_str, rate in spc_rates.items():
        if tenor_str not in tenor_map:
            continue
        
        value, unit = tenor_map[tenor_str]
        
        if unit == 'days':
            period = ql.Period(value, ql.Days)
        else:
            period = ql.Period(value, ql.Years)
        
        quote = ql.QuoteHandle(ql.SimpleQuote(rate / 100.0))
        
        if unit == 'days':
            # Short tenors: use DepositRateHelper (zero coupon)
            helper = ql.DepositRateHelper(
                quote,
                period,
                0,  # T+0 settlement for Chile
                calendar,
                ql.ModifiedFollowing,
                True,
                ql.Actual360()
            )
        else:
            # Longer tenors: use OISRateHelper (bullet swaps)
            helper = ql.OISRateHelper(
                0,  # T+0 settlement
                period,
                quote,
                camara_index
            )
        
        helpers.append(helper)
    
    # Build curve
    curve = ql.PiecewiseLogCubicDiscount(
        ql_date,
        helpers,
        ql.Actual360()
    )
    curve.enableExtrapolation()
    
    return curve


# =============================================================================
# FORWARD RATE EXTRACTION
# =============================================================================

def get_forward_rate(curve: ql.YieldTermStructure,
                     start_date: date,
                     end_date: date = None,
                     day_count: ql.DayCounter = None) -> float:
    """
    Extract forward rate from curve
    
    Args:
        curve: QuantLib yield curve
        start_date: Forward start date
        end_date: Forward end date (default: start + 1 day for overnight)
        day_count: Day count convention
    
    Returns:
        Forward rate as percentage
    """
    if day_count is None:
        day_count = ql.Actual360()
    
    ql_start = date_to_ql(start_date)
    
    if end_date is None:
        ql_end = ql_start + ql.Period(1, ql.Days)
    else:
        ql_end = date_to_ql(end_date)
    
    forward = curve.forwardRate(
        ql_start,
        ql_end,
        day_count,
        ql.Simple
    ).rate()
    
    return forward * 100.0  # Convert to percentage


def get_forward_at_meeting(curve: ql.YieldTermStructure,
                           meeting_date: date) -> float:
    """
    Get overnight forward rate at a meeting date
    
    Args:
        curve: QuantLib yield curve
        meeting_date: Meeting date
    
    Returns:
        Forward rate as percentage
    """
    return get_forward_rate(curve, meeting_date)


# =============================================================================
# PROBABILITY CALCULATIONS (CME FedWatch Style)
# =============================================================================

def round_to_nearest_quarter(rate: float) -> float:
    """
    Round rate to nearest 0.25%
    
    Args:
        rate: Rate in percentage (e.g., 4.38)
    
    Returns:
        Rounded rate (e.g., 4.50)
    """
    return round(rate * 4) / 4


def calculate_probability_vs_previous(forward: float, 
                                       previous: float) -> Dict:
    """
    Calculate probability of HOLD vs CHANGE relative to previous rate
    
    CME FedWatch methodology:
    - forward = rate_high * p + rate_low * (1-p)
    - Solve for p
    
    Args:
        forward: Forward rate from curve
        previous: Previous meeting's expected rate
    
    Returns:
        Dict with scenario probabilities
    """
    expected = round_to_nearest_quarter(forward)
    
    # Determine scenarios
    if expected < previous:
        # Market expects a CUT
        rate_high = previous  # HOLD
        rate_low = previous - RATE_INCREMENT  # CUT
        action_high = f"HOLD ({rate_high:.2f}%)"
        action_low = f"CUT ({rate_low:.2f}%)"
    elif expected > previous:
        # Market expects a HIKE
        rate_low = previous  # HOLD
        rate_high = previous + RATE_INCREMENT  # HIKE
        action_high = f"HIKE ({rate_high:.2f}%)"
        action_low = f"HOLD ({rate_low:.2f}%)"
    else:
        # Market expects HOLD
        return {
            'expected_rate': expected,
            'scenario_high': f"HOLD ({previous:.2f}%)",
            'scenario_low': f"HOLD ({previous:.2f}%)",
            'rate_high': previous,
            'rate_low': previous,
            'prob_high': 100.0,
            'prob_low': 0.0,
        }
    
    # Calculate probabilities
    # forward = rate_high * p + rate_low * (1-p)
    # forward = rate_high * p + rate_low - rate_low * p
    # forward - rate_low = p * (rate_high - rate_low)
    # p = (forward - rate_low) / (rate_high - rate_low)
    
    if rate_high == rate_low:
        prob_high = 1.0
    else:
        prob_high = (forward - rate_low) / (rate_high - rate_low)
    
    # Clamp to [0, 1]
    prob_high = max(0.0, min(1.0, prob_high))
    prob_low = 1.0 - prob_high
    
    return {
        'expected_rate': expected,
        'scenario_high': action_high,
        'scenario_low': action_low,
        'rate_high': rate_high,
        'rate_low': rate_low,
        'prob_high': round(prob_high * 100, 1),
        'prob_low': round(prob_low * 100, 1),
    }


def sofr_to_fed_funds(sofr_rate: float) -> float:
    """
    Convert SOFR rate to Fed Funds equivalent
    
    Args:
        sofr_rate: SOFR rate in percentage
    
    Returns:
        Fed Funds equivalent
    """
    return sofr_rate + SOFR_FED_SPREAD

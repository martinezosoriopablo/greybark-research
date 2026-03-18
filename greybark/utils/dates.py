"""
Grey Bark - Date Utilities
Calendarios de reuniones FOMC y BCCh
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple


# =============================================================================
# FOMC MEETING DATES
# =============================================================================

FOMC_2025 = [
    date(2025, 1, 29),
    date(2025, 3, 19),
    date(2025, 5, 7),
    date(2025, 6, 18),
    date(2025, 7, 30),
    date(2025, 9, 17),
    date(2025, 10, 29),
    date(2025, 12, 17),
]

FOMC_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]

FOMC_2027 = [
    date(2027, 1, 27),
    date(2027, 3, 17),
    date(2027, 5, 5),
    date(2027, 6, 16),
    date(2027, 7, 28),
    date(2027, 9, 22),
    date(2027, 11, 3),
    date(2027, 12, 15),
]

ALL_FOMC_MEETINGS = FOMC_2025 + FOMC_2026 + FOMC_2027


# =============================================================================
# BCCh MEETING DATES
# =============================================================================

BCCH_2025 = [
    date(2025, 1, 30),
    date(2025, 2, 27),
    date(2025, 3, 27),
    date(2025, 4, 29),
    date(2025, 5, 29),
    date(2025, 6, 26),
    date(2025, 7, 31),
    date(2025, 8, 28),
    date(2025, 9, 25),
    date(2025, 10, 30),
    date(2025, 11, 27),
    date(2025, 12, 18),
]

BCCH_2026 = [
    date(2026, 1, 27),
    date(2026, 3, 24),
    date(2026, 4, 28),
    date(2026, 6, 16),
    date(2026, 7, 28),
    date(2026, 9, 8),
    date(2026, 10, 27),
    date(2026, 12, 15),
]

BCCH_2027 = [
    date(2027, 1, 26),
    date(2027, 3, 30),
    date(2027, 5, 4),
    date(2027, 6, 15),
    date(2027, 7, 27),
    date(2027, 9, 7),
    date(2027, 10, 26),
    date(2027, 12, 14),
]

ALL_BCCH_MEETINGS = BCCH_2025 + BCCH_2026 + BCCH_2027


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_future_fomc_meetings(from_date: date = None, count: int = 12) -> List[date]:
    """
    Get list of future FOMC meeting dates
    
    Args:
        from_date: Start date (default: today)
        count: Number of meetings to return
    
    Returns:
        List of meeting dates
    """
    if from_date is None:
        from_date = date.today()
    
    future_meetings = [d for d in ALL_FOMC_MEETINGS if d > from_date]
    return future_meetings[:count]


def get_future_bcch_meetings(from_date: date = None, count: int = 12) -> List[date]:
    """
    Get list of future BCCh meeting dates
    
    Args:
        from_date: Start date (default: today)
        count: Number of meetings to return
    
    Returns:
        List of meeting dates
    """
    if from_date is None:
        from_date = date.today()
    
    future_meetings = [d for d in ALL_BCCH_MEETINGS if d > from_date]
    return future_meetings[:count]


def get_next_fomc_meeting(from_date: date = None) -> Optional[date]:
    """Get the next FOMC meeting date"""
    meetings = get_future_fomc_meetings(from_date, count=1)
    return meetings[0] if meetings else None


def get_next_bcch_meeting(from_date: date = None) -> Optional[date]:
    """Get the next BCCh meeting date"""
    meetings = get_future_bcch_meetings(from_date, count=1)
    return meetings[0] if meetings else None


def days_to_meeting(meeting_date: date, from_date: date = None) -> int:
    """Calculate days until a meeting"""
    if from_date is None:
        from_date = date.today()
    return (meeting_date - from_date).days


def format_meeting_label(meeting_date: date) -> str:
    """Format meeting date as label (e.g., 'Jan 2026')"""
    return meeting_date.strftime('%b %Y')


def get_year_end_date(year: int) -> date:
    """Get December 31 of a given year"""
    return date(year, 12, 31)


def get_meetings_in_range(meetings: List[date], 
                          start_date: date, 
                          end_date: date) -> List[date]:
    """Get meetings within a date range"""
    return [d for d in meetings if start_date <= d <= end_date]


# =============================================================================
# SETTLEMENT DATE HELPERS
# =============================================================================

def add_business_days(start_date: date, days: int, calendar: str = 'US') -> date:
    """
    Add business days to a date (simple implementation)
    
    Args:
        start_date: Starting date
        days: Number of business days to add
        calendar: 'US' or 'CL' (Chile)
    
    Returns:
        Date after adding business days
    """
    current = start_date
    added = 0
    
    while added < days:
        current += timedelta(days=1)
        # Simple weekend check (doesn't include holidays)
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            added += 1
    
    return current


def get_settlement_date(trade_date: date, settlement_days: int = 2, 
                        calendar: str = 'US') -> date:
    """
    Calculate settlement date
    
    Args:
        trade_date: Trade date
        settlement_days: T+N settlement (default T+2)
        calendar: 'US' or 'CL'
    
    Returns:
        Settlement date
    """
    return add_business_days(trade_date, settlement_days, calendar)

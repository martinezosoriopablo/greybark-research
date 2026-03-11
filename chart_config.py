# -*- coding: utf-8 -*-
"""
Greybark Research - Chart Configuration
=========================================

Centralized color scheme for all chart generators.
Derives colors from client branding dict for white-label support.

Usage:
    from chart_config import get_chart_colors

    # Default (Greybark):
    colors = get_chart_colors()

    # Client branding:
    colors = get_chart_colors(branding={'primary_color': '#1B3A5C', 'accent_color': '#C9963B'})
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# GREYBARK DEFAULTS
# =============================================================================

_DEFAULT_PRIMARY = '#1a1a1a'
_DEFAULT_ACCENT = '#dd6b20'
_DEFAULT_POSITIVE = '#276749'
_DEFAULT_NEGATIVE = '#c53030'
_DEFAULT_NEUTRAL = '#744210'


@dataclass
class ChartColorScheme:
    """Color scheme for charts, derived from branding."""

    # Core colors
    primary: str = _DEFAULT_PRIMARY
    accent: str = _DEFAULT_ACCENT
    positive: str = _DEFAULT_POSITIVE
    negative: str = _DEFAULT_NEGATIVE
    neutral: str = _DEFAULT_NEUTRAL

    # Background and text
    bg_light: str = '#f7f7f7'
    text_dark: str = _DEFAULT_PRIMARY
    text_medium: str = '#4a4a4a'
    text_light: str = '#718096'

    # Series colors (for multi-line/bar charts)
    series: List[str] = field(default_factory=lambda: [
        '#1a365d', '#dd6b20', '#276749', '#c53030',
        '#805ad5', '#d69e2e', '#319795', '#e53e3e',
    ])

    # DM/EM country colors (for international bond/rate charts)
    dm_colors: Dict[str, str] = field(default_factory=lambda: {
        'fed': '#1a365d', 'ecb': '#2b6cb0', 'boj': '#4299e1',
        'boe': '#63b3ed', 'usa': '#1a365d', 'germany': '#2b6cb0',
        'uk': '#4299e1', 'japan': '#63b3ed',
    })
    em_colors: Dict[str, str] = field(default_factory=lambda: {
        'bcb': '#c05621', 'banxico': '#dd6b20', 'pboc': '#ed8936',
        'tpm': '#f6ad55', 'brazil': '#c05621', 'mexico': '#dd6b20',
        'colombia': '#ed8936', 'peru': '#f6ad55',
    })

    def to_dict(self) -> Dict[str, str]:
        """Return flat COLORS dict (backward compatible with chart_generator.py)."""
        return {
            'primary': self.primary,
            'primary_blue': self.primary,    # alias for chart_generator.py
            'secondary_blue': self.text_medium,
            'accent': self.accent,
            'accent_orange': self.accent,    # alias for chart_generator.py
            'positive': self.positive,
            'negative': self.negative,
            'neutral': self.neutral,
            'bg_light': self.bg_light,
            'text_dark': self.text_dark,
            'text_medium': self.text_medium,
            'text_light': self.text_light,
        }


def _darken(hex_color: str, factor: float = 0.3) -> str:
    """Darken a hex color by a factor (0=unchanged, 1=black)."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        return f'#{r:02x}{g:02x}{b:02x}'
    except (ValueError, IndexError):
        return hex_color


def _lighten(hex_color: str, factor: float = 0.3) -> str:
    """Lighten a hex color by a factor (0=unchanged, 1=white)."""
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f'#{r:02x}{g:02x}{b:02x}'
    except (ValueError, IndexError):
        return hex_color


def get_chart_colors(branding: Optional[Dict[str, Any]] = None) -> ChartColorScheme:
    """Build a ChartColorScheme from a branding dict.

    Args:
        branding: Client branding dict with keys like 'primary_color',
                  'accent_color', 'green_color', 'red_color'.
                  If None, returns Greybark defaults.

    Returns:
        ChartColorScheme instance.
    """
    if not branding:
        return ChartColorScheme()

    primary = branding.get('primary_color', _DEFAULT_PRIMARY)
    accent = branding.get('accent_color', _DEFAULT_ACCENT)
    positive = branding.get('green_color', _DEFAULT_POSITIVE)
    negative = branding.get('red_color', _DEFAULT_NEGATIVE)

    # Derive series colors from primary and accent
    series = [
        _darken(primary, 0.0),      # Primary
        accent,                       # Accent
        positive,                     # Positive
        negative,                     # Negative
        _lighten(primary, 0.4),       # Light primary
        _darken(accent, 0.2),         # Dark accent
        '#319795',                    # Teal (neutral, always)
        _lighten(accent, 0.3),        # Light accent
    ]

    # Derive DM colors from primary gradient
    dm = {
        'fed': primary, 'ecb': _lighten(primary, 0.2),
        'boj': _lighten(primary, 0.4), 'boe': _lighten(primary, 0.55),
        'usa': primary, 'germany': _lighten(primary, 0.2),
        'uk': _lighten(primary, 0.4), 'japan': _lighten(primary, 0.55),
    }

    # Derive EM colors from accent gradient
    em = {
        'bcb': _darken(accent, 0.2), 'banxico': accent,
        'pboc': _lighten(accent, 0.15), 'tpm': _lighten(accent, 0.35),
        'brazil': _darken(accent, 0.2), 'mexico': accent,
        'colombia': _lighten(accent, 0.15), 'peru': _lighten(accent, 0.35),
    }

    return ChartColorScheme(
        primary=primary,
        accent=accent,
        positive=positive,
        negative=negative,
        neutral=_darken(accent, 0.35),
        bg_light='#f7f7f7',
        text_dark=primary,
        text_medium=_lighten(primary, 0.3),
        text_light='#718096',
        series=series,
        dm_colors=dm,
        em_colors=em,
    )


# =============================================================================
# CHART FAILURE TRACKER
# =============================================================================

class ChartFailureTracker:
    """Track chart generation failures for reporting."""

    def __init__(self):
        self.failures: List[Dict[str, str]] = []

    def record(self, chart_name: str, error: str, fallback_used: bool = False):
        """Record a chart failure."""
        self.failures.append({
            'chart': chart_name,
            'error': str(error)[:200],
            'fallback_used': fallback_used,
        })
        logger.warning("Chart failed: %s — %s", chart_name, error)

    def clear(self):
        """Clear all recorded failures."""
        self.failures = []

    @property
    def count(self) -> int:
        return len(self.failures)

    def summary(self) -> str:
        """Return a summary of failures."""
        if not self.failures:
            return "All charts generated successfully"
        lines = [f"{len(self.failures)} chart(s) failed:"]
        for f in self.failures:
            fb = " (fallback table used)" if f['fallback_used'] else ""
            lines.append(f"  - {f['chart']}: {f['error']}{fb}")
        return "\n".join(lines)


# Module-level tracker
_tracker = ChartFailureTracker()


def get_failure_tracker() -> ChartFailureTracker:
    """Get the module-level chart failure tracker."""
    return _tracker


# =============================================================================
# HTML TABLE FALLBACK
# =============================================================================

def chart_fallback_table(title: str, data: List[Dict[str, str]],
                         branding: Optional[Dict[str, str]] = None) -> str:
    """Generate a simple HTML table as fallback when a chart fails.

    Args:
        title: Chart title.
        data: List of dicts, each dict is a row {col_name: value}.
        branding: Optional branding dict for colors.

    Returns:
        HTML string with a styled table.
    """
    import html as html_mod

    if not data:
        return ''

    scheme = get_chart_colors(branding)
    primary = scheme.primary
    accent = scheme.accent
    bg = scheme.bg_light

    columns = list(data[0].keys())

    rows_html = []
    for row in data:
        cells = ''.join(
            f'<td style="padding:6px 10px;border-bottom:1px solid #e2e8f0;">'
            f'{html_mod.escape(str(row.get(c, "")))}</td>'
            for c in columns
        )
        rows_html.append(f'<tr>{cells}</tr>')

    header = ''.join(
        f'<th style="padding:6px 10px;background:{primary};color:white;'
        f'text-align:left;font-size:11px;">{html_mod.escape(c)}</th>'
        for c in columns
    )

    return (
        f'<div style="margin:12px 0;border:1px solid {accent};border-radius:4px;overflow:hidden;">'
        f'<div style="background:{bg};padding:8px 12px;font-weight:bold;font-size:12px;'
        f'color:{primary};border-bottom:2px solid {accent};">{html_mod.escape(title)}'
        f' <span style="font-weight:normal;color:#718096;font-size:10px;">(chart unavailable)</span></div>'
        f'<table style="width:100%;border-collapse:collapse;font-size:11px;">'
        f'<thead><tr>{header}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table></div>'
    )

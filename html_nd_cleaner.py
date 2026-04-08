"""
html_nd_cleaner.py — Strips residual N/D placeholders from final HTML output.

Used by all report renderers to clean up cells where data was unavailable.
"""

import re


def clean_nd(html: str) -> str:
    """Remove standalone 'N/D' text from HTML table cells and spans.

    Replaces patterns like:
      <td>N/D</td>  ->  <td>—</td>
      <span>N/D</span>  ->  <span>—</span>
      Standalone N/D in text  ->  —

    Returns cleaned HTML string.
    """
    if not html:
        return html

    # Replace N/D inside table cells with empty (cleaner look than em-dash)
    html = re.sub(r'(<td[^>]*>)\s*N/D\s*(</td>)', r'\1\2', html)

    # Replace N/D inside spans
    html = re.sub(r'(<span[^>]*>)\s*N/D\s*(</span>)', r'\1\2', html)

    # Replace N/D that appears as the sole content of any tag
    html = re.sub(r'(>)\s*N/D\s*(<)', r'\1\2', html)

    return html

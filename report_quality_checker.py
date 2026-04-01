# -*- coding: utf-8 -*-
"""
Greybark Research — Report Quality Checker
============================================

Post-render validation: scans generated HTML reports for empty cells,
placeholder text, and data quality issues. Runs after each report is
generated and prints a summary.

Usage:
    from report_quality_checker import check_report_quality
    issues = check_report_quality(html_string, report_name='aa')
    # Returns list of issues; empty = clean report
"""

import re
from typing import List, Dict


def check_report_quality(html: str, report_name: str = '') -> List[Dict]:
    """Scan HTML report for empty data indicators.

    Returns list of issues, each with:
        - type: 'empty_cell' | 'placeholder' | 'raw_data'
        - count: number of occurrences
        - severity: 'high' | 'medium' | 'low'
        - detail: description
    """
    if not html:
        return [{'type': 'empty_report', 'count': 1, 'severity': 'high',
                 'detail': 'Report HTML is empty'}]

    issues = []

    # 1. Count em-dash cells (data was N/D, cleaned to —)
    dash_cells = len(re.findall(r'<td[^>]*>\s*—\s*</td>', html))
    if dash_cells > 0:
        severity = 'high' if dash_cells > 15 else ('medium' if dash_cells > 5 else 'low')
        issues.append({
            'type': 'empty_cell',
            'count': dash_cells,
            'severity': severity,
            'detail': f'{dash_cells} celdas con "—" (datos no disponibles)',
        })

    # 2. Residual N/D that escaped the cleaner
    nd_count = len(re.findall(r'(?<=>)\s*N/D\s*(?=<)', html))
    if nd_count > 0:
        issues.append({
            'type': 'placeholder',
            'count': nd_count,
            'severity': 'medium',
            'detail': f'{nd_count} instancias residuales de "N/D"',
        })

    # 3. Template placeholders not replaced ({{something}})
    placeholders = re.findall(r'\{\{[^}]+\}\}', html)
    if placeholders:
        issues.append({
            'type': 'placeholder',
            'count': len(placeholders),
            'severity': 'high',
            'detail': f'{len(placeholders)} placeholders sin reemplazar: {placeholders[:3]}',
        })

    # 4. Raw Python/numpy types leaked into HTML
    raw_patterns = [
        (r'np\.float64\(', 'numpy float64'),
        (r"'error':", 'error dict'),
        (r'\{\'value\':', 'raw dict'),
        (r'nan%|nan<', 'NaN value'),
        (r'None%|None<', 'None value'),
    ]
    for pattern, label in raw_patterns:
        count = len(re.findall(pattern, html, re.IGNORECASE))
        if count > 0:
            issues.append({
                'type': 'raw_data',
                'count': count,
                'severity': 'high',
                'detail': f'{count} instancias de {label} en HTML',
            })

    return issues


def print_quality_report(issues: List[Dict], report_name: str = ''):
    """Print a formatted quality summary."""
    prefix = f'[{report_name.upper()}] ' if report_name else ''

    if not issues:
        print(f"  {prefix}Quality check: CLEAN — 0 issues")
        return

    total = sum(i['count'] for i in issues)
    high = sum(i['count'] for i in issues if i['severity'] == 'high')

    status = 'WARN' if high == 0 else 'ALERT'
    print(f"  {prefix}Quality check: {status} — {total} issues found:")
    for issue in issues:
        icon = '!!' if issue['severity'] == 'high' else '⚠' if issue['severity'] == 'medium' else '·'
        print(f"    {icon} {issue['detail']}")

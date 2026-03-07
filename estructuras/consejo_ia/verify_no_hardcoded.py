# -*- coding: utf-8 -*-
"""
Verify No Hardcoded Data — Scanner
====================================

Scans the 4 content generators for suspicious hardcoded data patterns.
Run after modifications to ensure no fabricated data remains.

Usage:
    python verify_no_hardcoded.py
"""

import re
import ast
import sys
from pathlib import Path
from typing import List, Tuple


# Files to scan
GENERATORS = [
    'macro_content_generator.py',
    'rv_content_generator.py',
    'rf_content_generator.py',
    'asset_allocation_content_generator.py',
]

# Patterns that suggest hardcoded market data
SUSPICIOUS_PATTERNS = [
    # Percentage values in strings that look like market data
    (r"'[+-]?\d+\.\d+%'", "Hardcoded percentage in string"),
    (r"'\d+\.\d+% a/a'", "Hardcoded YoY percentage"),
    (r"'\d+\.\d+% t/t'", "Hardcoded QoQ percentage"),
    # Dollar amounts in strings
    (r"'\$\d+[BbKkMm]?'", "Hardcoded dollar amount"),
    (r"'\$\d+\.\d+/", "Hardcoded price"),
    # Specific market data patterns
    (r"'[+-]\d+\.\d+pp'", "Hardcoded basis point change"),
    (r"'\d+K tons'", "Hardcoded inventory"),
    (r"'CNY \d+\.\d+T'", "Hardcoded CNY amount"),
]

# Known OK patterns (format strings, labels, etc.)
SAFE_PATTERNS = [
    r"f['\"]",           # f-strings (computed)
    r"\.format\(",       # .format() calls
    r"self\._fmt\(",     # Using _fmt helper
    r"self\._fc_pct\(",  # Using forecast accessor
    r"'N/D'",            # Proper fallback
    r"# ",               # Comments
    r"__doc__",          # Docstrings
    r"def ",             # Function definitions
    r"class ",           # Class definitions
    r"'%",               # Format specifiers
    r"\.1f",             # Format specifiers
    r"\.2f",             # Format specifiers
]

# Patterns for OW/UW that should come from parser
OW_UW_PATTERNS = [
    (r"'(OW|UW|OVERWEIGHT|UNDERWEIGHT)'", "Hardcoded OW/UW view — should use self.parser"),
    (r"'vista':\s*'(OW|UW|Overweight|Underweight)'", "Hardcoded vista value"),
]

# Dict patterns — large dicts with numeric values suggest hardcoded tables
DICT_NUMERIC_PATTERN = re.compile(
    r"'[^']+'\s*:\s*'[+-]?\d+\.?\d*%?'",
)


def scan_file(filepath: Path) -> List[Tuple[int, str, str]]:
    """Scan a single file for suspicious patterns.

    Returns:
        List of (line_number, line_content, description) tuples.
    """
    warnings = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return [(0, '', f'Could not read file: {e}')]

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments, empty lines, docstrings
        if not stripped or stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        # Skip lines with known safe patterns
        is_safe = False
        for safe in SAFE_PATTERNS:
            if re.search(safe, line):
                is_safe = True
                break
        if is_safe:
            continue

        # Check suspicious patterns
        for pattern, desc in SUSPICIOUS_PATTERNS:
            matches = re.findall(pattern, stripped)
            if matches:
                # Filter out format strings and computed values
                if 'f"' in line or "f'" in line or '.format(' in line:
                    continue
                if 'self._fmt(' in line or 'self._fc(' in line:
                    continue
                warnings.append((i, stripped[:120], desc))

        # Check OW/UW patterns
        for pattern, desc in OW_UW_PATTERNS:
            if re.search(pattern, stripped):
                # OK if it comes from parser
                if 'parser' in line or 'council' in line.lower():
                    continue
                # OK if it's in a condition/comparison
                if 'if ' in line or '==' in line or 'in [' in line or 'in (' in line:
                    continue
                # OK if it's a mapping dict (translating parser output to standard format)
                if '_map' in line or 'view_map' in line or 'fx_map' in line:
                    continue
                # OK if it's conditional assignment (v = 'OW' inside if/elif)
                if stripped.startswith('v =') or stripped.startswith('ig_view =') or stripped.startswith('hy_view ='):
                    continue
                # OK if it's in a text-scanning loop (row['view'] = 'OW' after keyword check)
                if "row['view']" in line:
                    continue
                # OK if it's a signal mapping (view = 'OVERWEIGHT' after signal check)
                if stripped.startswith('view =') and ('OVERWEIGHT' in stripped or 'UNDERWEIGHT' in stripped):
                    continue
                warnings.append((i, stripped[:120], desc))

        # Check for large hardcoded dicts (>3 numeric values in same dict)
        numeric_matches = DICT_NUMERIC_PATTERN.findall(stripped)
        if len(numeric_matches) >= 3:
            warnings.append((i, stripped[:120], f"Dict with {len(numeric_matches)} hardcoded numeric values"))

    return warnings


def scan_for_fabricated_functions(filepath: Path) -> List[Tuple[int, str, str]]:
    """Scan for functions that return dicts without any self.data/self.parser calls."""
    warnings = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception:
        return []

    # Find function boundaries
    func_starts = []
    for i, line in enumerate(lines):
        if re.match(r'\s+def _(?!_)', line):  # Private methods
            func_starts.append(i)

    for idx, start in enumerate(func_starts):
        end = func_starts[idx + 1] if idx + 1 < len(func_starts) else len(lines)
        func_body = '\n'.join(lines[start:end])
        func_name = re.match(r'\s+def (\w+)', lines[start])
        if not func_name:
            continue
        name = func_name.group(1)

        # Skip known helpers
        if name in ('_get_spanish_month', '_fmt', '_fc', '_fc_pct', '_extract_from_panel',
                     '_panel', '_final', '_cio', '_md_to_html', '_has_council',
                     '_get_chile_latest', '_get_usa_latest', '_get_europe_latest',
                     '_get_china_latest', '_nested_get', '_has_data', '_val',
                     '_q', '_has_q', '_fmt_pct', '_fmt_bp', '_v',
                     '_build_taylor_rule', '_build_fed_meetings', '_load_previous_forecast',
                     '_build_cpi_components', '_build_latam_table', '_get_bloomberg_pmi'):
            continue

        # Check if function uses any data source
        has_data_source = any(p in func_body for p in [
            'self.data', 'self.parser', 'self.council', 'self.quant',
            'self.forecast', 'self.bloomberg', 'self._fc(',
            'self._get_', 'self._q(', 'self._has_q(', 'self._val(',
            'self._has_data(', 'self._panel(', 'self._final(',
            'generate_narrative', 'narrative_engine', "'N/D'",
        ])

        # Check if function returns hardcoded data
        has_return_dict = 'return {' in func_body or "return [" in func_body
        has_numeric_strings = len(re.findall(r"'\d+\.?\d*%'", func_body)) >= 3

        if has_return_dict and has_numeric_strings and not has_data_source:
            num_count = len(re.findall(r"'\d+\.?\d*%'", func_body))
            warnings.append((
                start + 1,
                f"def {name}()",
                f"Function returns dict with {num_count} "
                f"hardcoded values and no data source calls"
            ))

    return warnings


def main():
    base = Path(__file__).parent
    total_warnings = 0

    print("=" * 70)
    print("VERIFY NO HARDCODED DATA — Scanner")
    print("=" * 70)
    print()

    for filename in GENERATORS:
        filepath = base / filename
        if not filepath.exists():
            print(f"[SKIP] {filename} — file not found")
            continue

        print(f"[SCAN] {filename}")

        # Pattern scan
        warnings = scan_file(filepath)
        # Function scan
        func_warnings = scan_for_fabricated_functions(filepath)
        all_warnings = sorted(warnings + func_warnings, key=lambda x: x[0])

        if not all_warnings:
            print(f"  [OK] No suspicious hardcoded data found")
        else:
            for line_no, content, desc in all_warnings:
                print(f"  [WARN] L{line_no}: {desc}")
                print(f"         {content.encode('ascii', 'replace').decode()}")
            total_warnings += len(all_warnings)

        print()

    print("=" * 70)
    if total_warnings == 0:
        print(f"RESULT: PASS — No suspicious hardcoded data detected")
    else:
        print(f"RESULT: {total_warnings} warning(s) found — review manually")
    print("=" * 70)

    return 0 if total_warnings == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

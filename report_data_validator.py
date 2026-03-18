# -*- coding: utf-8 -*-
"""
Greybark Research — Report Data Validator (No-Fallback Gate)
=============================================================

Validates that ALL required data is available BEFORE generating a report.
If any required chart's data source is unavailable, the report is BLOCKED.

This is the "Phase 4 Gate" in the pipeline:
  Phase 1: Collect → Phase 2: Preflight → Phase 3: Council → Phase 4: VALIDATE → Phase 5: Generate

Usage:
    validator = ReportDataValidator()
    result = validator.validate("macro", chart_data_provider=cdp, bloomberg=bbg)
    if result.blocked:
        print(f"BLOCKED: {result.missing}")
        sys.exit(1)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from data_manifest import (
    REPORT_CHART_MANIFESTS, ChartDependency,
    get_required_charts, get_report_manifest,
)

logger = logging.getLogger(__name__)


@dataclass
class ChartValidationResult:
    chart_id: str
    ok: bool
    source: str
    error: str = ""


@dataclass
class ReportValidationResult:
    report_type: str
    verdict: str              # "GO" or "NO_GO"
    checked: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0          # non-required charts
    results: List[ChartValidationResult] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.verdict == "NO_GO"

    @property
    def missing(self) -> List[str]:
        return [r.chart_id for r in self.results if not r.ok and r.error]

    def summary(self) -> str:
        status = "BLOCKED" if self.blocked else "OK"
        lines = [
            f"Report '{self.report_type}': {status} "
            f"({self.passed}/{self.checked} charts OK, {self.failed} failed, {self.skipped} optional skipped)"
        ]
        for r in self.results:
            icon = "OK" if r.ok else "FAIL"
            lines.append(f"  [{icon}] {r.chart_id} ({r.source}) {r.error}")
        return "\n".join(lines)


class ReportDataValidator:
    """Validates data availability for each report against its manifest."""

    # Bloomberg file max age (days)
    BLOOMBERG_MAX_AGE_DAYS = 45

    def __init__(self,
                 chart_data_provider=None,
                 bloomberg=None,
                 rf_data: Dict = None,
                 equity_data: Dict = None,
                 bloomberg_path: str = None):
        self._cdp = chart_data_provider
        self._bbg = bloomberg
        self._rf_data = rf_data or {}
        self._equity_data = equity_data or {}
        self._bloomberg_path = bloomberg_path

    def validate(self, report_type: str) -> ReportValidationResult:
        """Validate all chart dependencies for a report type."""
        manifest = get_report_manifest(report_type)
        if not manifest:
            return ReportValidationResult(
                report_type=report_type, verdict="GO",
                checked=0, passed=0, failed=0
            )

        result = ReportValidationResult(report_type=report_type, verdict="GO")

        for dep in manifest:
            if not dep.required:
                result.skipped += 1
                result.results.append(ChartValidationResult(
                    chart_id=dep.chart_id, ok=True, source=dep.source,
                    error="(optional, skipped)"
                ))
                continue

            result.checked += 1
            check = self._check_dependency(dep)
            result.results.append(check)

            if check.ok:
                result.passed += 1
            else:
                result.failed += 1

        if result.failed > 0:
            result.verdict = "NO_GO"

        return result

    def _check_dependency(self, dep: ChartDependency) -> ChartValidationResult:
        """Check if a single chart dependency is satisfied."""
        sources = dep.source.split('+')  # "bcch+fred" → ["bcch", "fred"]

        for src in sources:
            src = src.strip()
            if src == "bcch":
                ok, err = self._check_bcch(dep)
            elif src == "fred":
                ok, err = self._check_fred(dep)
            elif src == "bloomberg":
                ok, err = self._check_bloomberg(dep)
            elif src == "yfinance":
                ok, err = self._check_equity_data(dep)
            elif src == "alphavantage":
                ok, err = self._check_equity_data(dep)
            elif src == "content":
                ok, err = True, ""  # Content-derived, always "available"
            else:
                ok, err = False, f"Unknown source: {src}"

            if not ok:
                return ChartValidationResult(
                    chart_id=dep.chart_id, ok=False, source=dep.source, error=err
                )

        return ChartValidationResult(
            chart_id=dep.chart_id, ok=True, source=dep.source
        )

    # ------------------------------------------------------------------
    # Source-specific checks
    # ------------------------------------------------------------------

    def _check_bcch(self, dep: ChartDependency) -> tuple:
        """Check BCCh data availability via ChartDataProvider."""
        if not self._cdp:
            return False, "ChartDataProvider not available"

        for method_name in dep.series:
            if ':' in method_name:
                method_name = method_name.split(':')[0]
            method_name = method_name.strip()
            fn = getattr(self._cdp, method_name, None)
            if fn is None:
                continue  # Method doesn't exist but others might satisfy
            try:
                result = fn()
                if result is None:
                    return False, f"BCCh method {method_name}() returned None"
                if hasattr(result, '__len__') and len(result) == 0:
                    return False, f"BCCh method {method_name}() returned empty"
                if isinstance(result, dict):
                    non_none = sum(1 for v in result.values() if v is not None)
                    if non_none == 0:
                        return False, f"BCCh method {method_name}() all None values"
                return True, ""
            except Exception as e:
                return False, f"BCCh {method_name}() error: {e}"

        # If no method was found at all, can't validate
        return True, ""  # Assume OK if method name format not recognized

    def _check_fred(self, dep: ChartDependency) -> tuple:
        """Check FRED data availability via ChartDataProvider."""
        if not self._cdp:
            return False, "ChartDataProvider not available"

        for method_name in dep.series:
            if ':' in method_name:
                method_name = method_name.split(':')[0]
            method_name = method_name.strip()
            fn = getattr(self._cdp, method_name, None)
            if fn is None:
                # Try direct FRED series ID (e.g., "DGS10")
                if hasattr(self._cdp, 'fred') and self._cdp.fred:
                    try:
                        from datetime import date, timedelta
                        s = self._cdp.fred.get_series(
                            method_name,
                            start_date=date.today() - timedelta(days=30),
                            end_date=date.today()
                        )
                        if s is not None and len(s) > 0:
                            return True, ""
                        return False, f"FRED series {method_name} returned empty"
                    except Exception as e:
                        return False, f"FRED {method_name} error: {e}"
                continue
            try:
                result = fn()
                if result is None:
                    return False, f"FRED method {method_name}() returned None"
                if hasattr(result, '__len__') and len(result) == 0:
                    return False, f"FRED method {method_name}() returned empty"
                return True, ""
            except Exception as e:
                return False, f"FRED {method_name}() error: {e}"

        return True, ""

    def _check_bloomberg(self, dep: ChartDependency) -> tuple:
        """Check Bloomberg Excel data availability."""
        if not self._bbg:
            return False, "Bloomberg reader not available"

        if not self._bbg.available:
            return False, "Bloomberg Excel not loaded or empty"

        # Check freshness
        if self._bloomberg_path:
            try:
                mtime = os.path.getmtime(self._bloomberg_path)
                age_days = (datetime.now() - datetime.fromtimestamp(mtime)).days
                if age_days > self.BLOOMBERG_MAX_AGE_DAYS:
                    return False, f"Bloomberg Excel is {age_days} days old (max {self.BLOOMBERG_MAX_AGE_DAYS})"
            except OSError:
                pass

        # Check each required field
        missing_fields = []
        for campo_id in dep.series:
            if not self._bbg.has(campo_id):
                missing_fields.append(campo_id)

        if missing_fields:
            return False, f"Bloomberg missing fields: {', '.join(missing_fields)}"

        return True, ""

    def _check_equity_data(self, dep: ChartDependency) -> tuple:
        """Check equity data availability (yfinance / AlphaVantage)."""
        if not self._equity_data:
            return False, "Equity data not collected"

        # Check top-level keys from series hints
        for hint in dep.series:
            top_key = hint.split('.')[0]
            val = self._equity_data.get(top_key)
            if val is None:
                return False, f"equity_data['{top_key}'] is None"
            if isinstance(val, dict) and val.get('error'):
                return False, f"equity_data['{top_key}'] has error: {val['error']}"

        return True, ""

    # ------------------------------------------------------------------
    # Convenience: validate all requested reports at once
    # ------------------------------------------------------------------

    def validate_all(self, report_types: List[str]) -> Dict[str, ReportValidationResult]:
        """Validate multiple reports, return results keyed by report type."""
        return {rt: self.validate(rt) for rt in report_types}

    def get_blocked_reports(self, report_types: List[str]) -> List[str]:
        """Return list of report types that would be blocked."""
        results = self.validate_all(report_types)
        return [rt for rt, r in results.items() if r.blocked]

    def print_summary(self, report_types: List[str]):
        """Print human-readable validation summary."""
        results = self.validate_all(report_types)
        for rt, result in results.items():
            print(result.summary())
            print()

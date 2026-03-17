# -*- coding: utf-8 -*-
"""
coherence_validator.py — Deterministic Numeric Coherence Validator
==================================================================

Validates that shared numeric metrics are consistent across the 4 reports
(Macro, RV, RF, Asset Allocation).

Unlike report_auditor.py (LLM-based qualitative audit), this module does
purely deterministic comparisons with defined tolerances.

Usage:
    from coherence_validator import validate_coherence

    result = validate_coherence(
        source_data={'quant_data': {...}, 'rf_data': {...}, 'equity_data': {...}},
        report_contents={'macro': {...}, 'rv': {...}, 'rf': {...}, 'aa': {...}}
    )
    print(format_coherence_report(result))
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Metric Definitions + Tolerances
# ─────────────────────────────────────────────

SHARED_METRICS = [
    {
        "id": "fed_funds",
        "name": "Fed Funds Rate",
        "tolerance_abs": 0.25,  # 25bps
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "quant_data.macro_usa.fed_funds"),
            "macro": lambda c: _extract_rate(c, "estados_unidos.política_monetaria.tasas.actual"),
            "aa": lambda c: _search_indicator(c, "resumen_ejecutivo.key_points", r"Fed\s+Funds?\s*(?:en\s+)?(\d+[\.,]\d+)"),
            "rf": lambda c: _extract_from_yields(c, "ambiente_tasas.yields_globales", "USA", "fed_funds"),
        },
    },
    {
        "id": "ust_10y",
        "name": "UST 10Y Yield",
        "tolerance_abs": 0.15,  # 15bps
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "rf_data.yield_curve.current_curve.10Y")
                or _deep_get(d, "rf_data.international_yields.usa.10Y.last"),
            "macro": lambda c: _search_number(
                _deep_get(c, "estados_unidos.política_monetaria.narrativa", ""),
                r"(?:UST|Treasury|10Y|10\s*a[ñn]os).*?(\d+[\.,]\d+)%"),
            "rf": lambda c: _extract_from_yields(c, "ambiente_tasas.yields_globales", "USA", "y10"),
            "aa": lambda c: _search_number(
                _deep_get(c, "asset_classes.renta_fija.view_tasas", ""),
                r"(?:UST|Treasury|10Y).*?(\d+[\.,]\d+)%"),
        },
    },
    {
        "id": "core_cpi",
        "name": "Core CPI YoY",
        "tolerance_abs": 0.20,  # 20bps
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "quant_data.macro_usa.cpi_core_yoy")
                or _deep_get(d, "quant_data.inflation.core_cpi_yoy"),
            "macro": lambda c: _extract_indicator(c, "estados_unidos.inflación.datos", "Core CPI"),
            "aa": lambda c: _search_number(
                str(_deep_get(c, "mes_en_revision.economia_global", {})),
                r"(?:Core\s+CPI|PCE\s+core|inflaci[óo]n\s+subyacente).*?(\d+[\.,]\d+)%"),
        },
    },
    {
        "id": "sp500_pe",
        "name": "S&P 500 P/E Forward",
        "tolerance_pct": 10.0,  # 10% relative
        "unit": "x",
        "extractors": {
            "source": lambda d: _deep_get(d, "equity_data.valuations.us.pe")
                or _deep_get(d, "equity_data.valuations.us.pe_forward"),
            "rv": lambda c: _extract_pe(c, "valorizaciones.multiples_region", "S&P 500"),
            "aa": lambda c: _search_number(
                str(_deep_get(c, "asset_classes.renta_variable", {})),
                r"P/?E.*?(\d+[\.,]\d+)"),
        },
    },
    {
        "id": "ig_spread",
        "name": "IG Credit Spread",
        "tolerance_abs": 15.0,  # 15bps
        "unit": "bps",
        "extractors": {
            "source": lambda d: _get_ig_spread(d),
            "rf": lambda c: _extract_spread(c, "credito.investment_grade.spread_actual"),
            "aa": lambda c: _search_number(
                str(_deep_get(c, "asset_classes.renta_fija", {})),
                r"IG.*?(\d+)\s*bps"),
        },
    },
    {
        "id": "tpm_chile",
        "name": "TPM Chile",
        "tolerance_abs": 0.25,  # 25bps
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "quant_data.chile.tpm")
                or _deep_get(d, "rf_data.chile_rates.tpm.current"),
            "macro": lambda c: _extract_rate(c, "chile_latam.chile_política_monetaria.tasas.tpm_actual"),
            "rf": lambda c: _search_number(
                str(_deep_get(c, "chile", {})),
                r"TPM\s+(\d+[\.,]\d+)%"),
        },
    },
    # ── New metrics (7) ──
    {
        "id": "vix",
        "name": "VIX",
        "tolerance_abs": 1.5,
        "unit": "",
        "extractors": {
            "source": lambda d: _deep_get(d, "equity_data.risk.vix.current"),
            "rv": lambda c: _search_number(str(c), r"VIX.*?(\d+[\.,]\d+)"),
            "macro": lambda c: _search_number(str(c), r"VIX.*?(\d+[\.,]\d+)"),
        },
    },
    {
        "id": "wti",
        "name": "WTI Crude",
        "tolerance_abs": 2.0,
        "unit": "USD/bbl",
        "extractors": {
            "source": lambda d: _deep_get(d, "equity_data.bcch_indices.oil_wti.value"),
            "macro": lambda c: _search_number(
                str(_deep_get(c, "temas_clave", {})),
                r"(?:WTI|petr[óo]leo).*?(\d+[\.,]\d+)"),
            "aa": lambda c: _search_number(
                str(_deep_get(c, "asset_classes", {})),
                r"(?:WTI|petr[óo]leo).*?(\d+[\.,]\d+)"),
        },
    },
    {
        "id": "copper",
        "name": "Cobre",
        "tolerance_abs": 0.10,
        "unit": "USD/lb",
        "extractors": {
            "source": lambda d: _deep_get(d, "equity_data.bcch_indices.copper.value")
                or _deep_get(d, "quant_data.chile.copper_price"),
            "macro": lambda c: _search_number(
                str(_deep_get(c, "chile_latam", {})),
                r"[Cc]obre.*?(\d+[\.,]\d+)"),
            "aa": lambda c: _search_number(
                str(_deep_get(c, "asset_classes", {})),
                r"[Cc]obre.*?(\d+[\.,]\d+)"),
        },
    },
    {
        "id": "breakeven_5y",
        "name": "Breakeven 5Y",
        "tolerance_abs": 0.05,
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "rf_data.inflation.breakeven_5y")
                or _deep_get(d, "quant_data.inflation.breakeven_5y"),
            "rf": lambda c: _search_number(
                str(_deep_get(c, "inflación", {})),
                r"[Bb]reakeven\s*5[Yy].*?(\d+[\.,]\d+)%"),
            "macro": lambda c: _search_number(
                str(_deep_get(c, "estados_unidos", {})),
                r"[Bb]reakeven\s*5[Yy].*?(\d+[\.,]\d+)%"),
        },
    },
    {
        "id": "breakeven_10y",
        "name": "Breakeven 10Y",
        "tolerance_abs": 0.05,
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "rf_data.inflation.breakeven_10y")
                or _deep_get(d, "quant_data.inflation.breakeven_10y"),
            "rf": lambda c: _search_number(
                str(_deep_get(c, "inflación", {})),
                r"[Bb]reakeven\s*10[Yy].*?(\d+[\.,]\d+)%"),
            "macro": lambda c: _search_number(
                str(_deep_get(c, "estados_unidos", {})),
                r"[Bb]reakeven\s*10[Yy].*?(\d+[\.,]\d+)%"),
        },
    },
    {
        "id": "tips_10y",
        "name": "TIPS 10Y Yield",
        "tolerance_abs": 0.05,
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "rf_data.inflation.tips_10y")
                or _deep_get(d, "equity_data.real_rates.current.tips_10y"),
            "rf": lambda c: _search_number(
                str(_deep_get(c, "inflación", {})),
                r"TIPS\s*10[Yy].*?(\d+[\.,]\d+)%"),
        },
    },
    {
        "id": "selic",
        "name": "SELIC Brasil",
        "tolerance_abs": 0.25,
        "unit": "%",
        "extractors": {
            "source": lambda d: _deep_get(d, "rf_data.chile_rates.intl_policy_rates.bcb"),
            "rf": lambda c: _search_number(
                str(_deep_get(c, "latam", {})),
                r"SELIC.*?(\d+[\.,]\d+)%"),
            "macro": lambda c: _search_number(
                str(_deep_get(c, "chile_latam", {})),
                r"SELIC.*?(\d+[\.,]\d+)%"),
        },
    },
]


# ─────────────────────────────────────────────
# Value Extraction Helpers
# ─────────────────────────────────────────────

def _deep_get(obj: Any, path: str, default=None) -> Any:
    """Navigate nested dicts with dot-separated path."""
    if obj is None:
        return default
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return default
        else:
            return default
    return current


def _parse_number(val: Any) -> Optional[float]:
    """Parse a number from various formats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Clean common formatting
        s = val.strip().replace(",", ".").replace("%", "").replace("bps", "").strip()
        try:
            return float(s)
        except ValueError:
            # Try extracting first number
            m = re.search(r"(\d+[\.,]?\d*)", s)
            if m:
                return float(m.group(1).replace(",", "."))
    return None


def _search_number(text: str, pattern: str) -> Optional[float]:
    """Search text with regex and extract a number."""
    if not text:
        return None
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return _parse_number(m.group(1))
    return None


def _extract_rate(content: Dict, path: str) -> Optional[float]:
    """Extract a rate value from content dict."""
    val = _deep_get(content, path)
    return _parse_number(val)


def _extract_indicator(content: Dict, path: str, indicator_name: str) -> Optional[float]:
    """Extract a specific indicator from a datos list."""
    datos = _deep_get(content, path, [])
    if not isinstance(datos, list):
        return None
    for d in datos:
        if isinstance(d, dict):
            name = d.get("indicador", "")
            if indicator_name.lower() in name.lower():
                return _parse_number(d.get("valor"))
    return None


def _extract_pe(content: Dict, path: str, market_name: str) -> Optional[float]:
    """Extract P/E from multiples table."""
    data = _deep_get(content, path, [])
    if not isinstance(data, list):
        return None
    for d in data:
        if isinstance(d, dict):
            name = d.get("mercado", "")
            if market_name.lower() in name.lower():
                return _parse_number(d.get("pe_fwd", d.get("pe_actual")))
    return None


def _extract_spread(content: Dict, path: str) -> Optional[float]:
    """Extract a spread value (may be in bps string format)."""
    val = _deep_get(content, path)
    if val is None:
        return None
    n = _parse_number(val)
    # If value looks like percentage (< 10), convert to bps
    if n is not None and n < 10:
        n = n * 100
    return n


def _extract_from_yields(content: Dict, path: str, market: str, field: str) -> Optional[float]:
    """Extract a yield value from yields_globales list."""
    data = _deep_get(content, path, [])
    if not isinstance(data, list):
        return None
    for d in data:
        if isinstance(d, dict):
            name = d.get("mercado", "")
            if market.lower() in name.lower():
                return _parse_number(d.get(field))
    return None


def _search_indicator(content: Dict, path: str, pattern: str) -> Optional[float]:
    """Search for a number in a list of strings (key_points, key_calls, etc.)."""
    data = _deep_get(content, path, [])
    if isinstance(data, list):
        for item in data:
            val = _search_number(str(item), pattern)
            if val is not None:
                return val
    return None


def _get_ig_spread(source_data: Dict) -> Optional[float]:
    """Get IG spread from source data."""
    # Try rf_data first
    ig = _deep_get(source_data, "rf_data.credit_spreads.ig_breakdown.total.current_bps")
    if ig is not None:
        return _parse_number(ig)
    # Try quant_data
    ig = _deep_get(source_data, "quant_data.credit_spreads.ig_oas_bps")
    return _parse_number(ig) if ig else None


# ─────────────────────────────────────────────
# Core Validation Logic
# ─────────────────────────────────────────────

def validate_coherence(
    source_data: Dict[str, Any],
    report_contents: Dict[str, Dict],
) -> Dict[str, Any]:
    """
    Validate numeric coherence across reports.

    Parameters
    ----------
    source_data : dict
        Raw data used to generate reports. Keys: 'quant_data', 'rf_data', 'equity_data'
    report_contents : dict
        Content dicts from the 4 generators. Keys: 'macro', 'rv', 'rf', 'aa'

    Returns
    -------
    dict with:
        - metrics: list of metric check results
        - coherence_score: 0.0-1.0
        - flags: list of discrepancy flags
        - summary: text summary
    """
    results = []
    flags = []

    for metric_def in SHARED_METRICS:
        metric_id = metric_def["id"]
        metric_name = metric_def["name"]
        tolerance_abs = metric_def.get("tolerance_abs")
        tolerance_pct = metric_def.get("tolerance_pct")
        unit = metric_def.get("unit", "")

        # Extract values from all sources
        values = {}
        for source_name, extractor in metric_def["extractors"].items():
            try:
                if source_name == "source":
                    val = extractor(source_data)
                else:
                    content = report_contents.get(source_name, {})
                    if content:
                        val = extractor(content)
                    else:
                        val = None
                values[source_name] = _parse_number(val) if not isinstance(val, (int, float, type(None))) else val
            except Exception as e:
                logger.debug("Error extracting %s from %s: %s", metric_id, source_name, e)
                values[source_name] = None

        # Filter non-None values
        available = {k: v for k, v in values.items() if v is not None}

        if len(available) < 2:
            results.append({
                "metric": metric_name,
                "id": metric_id,
                "status": "INSUFFICIENT",
                "values": values,
                "message": f"Only {len(available)} source(s) available — cannot compare",
            })
            continue

        # Compare all pairs
        source_val = available.get("source")
        discrepancies = []

        available_list = list(available.items())
        for i in range(len(available_list)):
            for j in range(i + 1, len(available_list)):
                name_a, val_a = available_list[i]
                name_b, val_b = available_list[j]

                diff = abs(val_a - val_b)
                is_ok = True

                if tolerance_abs is not None:
                    if diff > tolerance_abs:
                        is_ok = False
                elif tolerance_pct is not None:
                    ref = max(abs(val_a), abs(val_b), 0.01)
                    if (diff / ref * 100) > tolerance_pct:
                        is_ok = False

                if not is_ok:
                    discrepancies.append({
                        "pair": (name_a, name_b),
                        "values": (val_a, val_b),
                        "diff": diff,
                    })

        status = "OK" if not discrepancies else "DISCREPANCY"
        results.append({
            "metric": metric_name,
            "id": metric_id,
            "status": status,
            "values": values,
            "discrepancies": discrepancies,
        })

        for disc in discrepancies:
            severity = "high" if _is_critical(metric_id) else "medium"
            a_name, b_name = disc["pair"]
            a_val, b_val = disc["values"]
            flags.append({
                "severity": severity,
                "type": "data",
                "metric": metric_name,
                "reports": [a_name, b_name],
                "issue": (
                    f"{metric_name}: {a_name}={a_val:.2f}{unit} vs "
                    f"{b_name}={b_val:.2f}{unit} (diff={disc['diff']:.2f}{unit})"
                ),
                "suggestion": (
                    f"Verify {metric_name} source — ensure both reports "
                    f"read from same data snapshot"
                ),
            })

    # Compute score
    total = len([r for r in results if r["status"] != "INSUFFICIENT"])
    ok = len([r for r in results if r["status"] == "OK"])
    score = ok / max(total, 1)

    if score < 0.75:
        disc_ids = [r['id'] for r in results if r['status'] == 'DISCREPANCY']
        logger.warning(
            f"COHERENCE ALERT: score={score:.2f} < 0.75. "
            f"Discrepant metrics: {disc_ids}"
        )

    return {
        "status": "completed",
        "metrics": results,
        "coherence_score": round(score, 2),
        "flags": flags,
        "summary": _build_summary(results, flags),
    }


def _is_critical(metric_id: str) -> bool:
    """Determine if a metric discrepancy is critical."""
    return metric_id in ("fed_funds", "tpm_chile", "core_cpi", "vix", "wti")


def _build_summary(results: List[Dict], flags: List[Dict]) -> str:
    """Build a human-readable summary."""
    total = len([r for r in results if r["status"] != "INSUFFICIENT"])
    ok = len([r for r in results if r["status"] == "OK"])
    disc = len([r for r in results if r["status"] == "DISCREPANCY"])
    insuf = len([r for r in results if r["status"] == "INSUFFICIENT"])

    high = len([f for f in flags if f["severity"] == "high"])

    if disc == 0:
        return f"All {total} shared metrics are coherent across reports."
    return (
        f"{ok}/{total} metrics coherent, {disc} discrepancies "
        f"({high} critical). {insuf} metrics had insufficient data."
    )


# ─────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────

def format_coherence_report(result: Dict[str, Any], verbose: bool = True) -> str:
    """Format coherence validation result for console output."""
    lines = []

    if result.get("status") != "completed":
        lines.append(f"  [SKIP] Coherence validation: {result.get('reason', 'unknown')}")
        return "\n".join(lines)

    score = result["coherence_score"]
    bar_len = 20
    filled = int(score * bar_len)
    bar = "#" * filled + "-" * (bar_len - filled)
    label = "OK" if score >= 0.8 else ("WARN" if score >= 0.5 else "FAIL")

    lines.append(f"  Numeric coherence: [{bar}] {score:.0%}  ({label})")
    lines.append(f"  {result['summary']}")

    if verbose:
        for m in result["metrics"]:
            status = m["status"]
            icon = "OK" if status == "OK" else ("!!" if status == "DISCREPANCY" else "--")
            vals = {k: f"{v:.2f}" for k, v in m["values"].items() if v is not None}
            vals_str = ", ".join(f"{k}={v}" for k, v in vals.items())
            lines.append(f"    [{icon}] {m['metric']}: {vals_str}")

        if result["flags"]:
            lines.append("")
            for f in result["flags"]:
                sev = f["severity"].upper()
                lines.append(f"    [{sev}] {f['issue']}")

    return "\n".join(lines)

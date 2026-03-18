# -*- coding: utf-8 -*-
"""
api_health_checker.py — Greybark Research API Health Monitor
=============================================================

Validates connectivity and data freshness for all API sources
before running the monthly pipeline.

Usage:
    python api_health_checker.py          # Full check
    python api_health_checker.py --quick  # Quick (skip slow sources)

From code:
    from api_health_checker import check_all_apis, format_health_report
    result = check_all_apis()
    print(format_health_report(result))
"""

import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Individual API Checks
# ─────────────────────────────────────────────

def _check_fred() -> Dict[str, Any]:
    """Check FRED API connectivity and data freshness."""
    try:
        from greybark.config import config
        from fredapi import Fred

        api_key = config.fred.api_key
        if not api_key:
            return {"status": "FAIL", "reason": "FRED_API_KEY not set"}

        fred = Fred(api_key=api_key)
        # Quick test: fetch latest Fed Funds rate
        s = fred.get_series("DFF", observation_start=date.today() - timedelta(days=10))
        if s is None or len(s) == 0:
            return {"status": "WARN", "reason": "FRED returned empty for DFF"}

        latest_date = s.dropna().index[-1].strftime("%Y-%m-%d")
        latest_val = float(s.dropna().iloc[-1])
        return {
            "status": "OK",
            "latest_date": latest_date,
            "sample": f"Fed Funds = {latest_val:.2f}%",
            "series_count": "60+",
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_bcch() -> Dict[str, Any]:
    """Check BCCh API connectivity."""
    try:
        from greybark.config import config
        from greybark.data_sources.bcch_client import BCChClient

        user = config.bcch.user
        pwd = config.bcch.password
        if not user or not pwd:
            return {"status": "FAIL", "reason": "BCCH_USER/BCCH_PASSWORD not set"}

        client = BCChClient()
        # Quick test: fetch TPM (last 30 days)
        data = client.get_series("F022.TPM.TIN.D001.NO.Z.D", days_back=30)
        if data is None or (hasattr(data, '__len__') and len(data) == 0):
            return {"status": "WARN", "reason": "BCCh returned empty for TPM"}

        latest = float(data.iloc[-1]) if len(data) > 0 else None
        return {
            "status": "OK",
            "sample": f"TPM = {latest}%" if latest else "TPM series accessible",
            "series_count": "93+",
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_alphavantage() -> Dict[str, Any]:
    """Check AlphaVantage API connectivity."""
    try:
        from greybark.config import config

        api_key = config.alphavantage.api_key
        if not api_key:
            return {"status": "FAIL", "reason": "ALPHAVANTAGE_API_KEY not set"}

        import requests
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={api_key}"
        resp = requests.get(url, timeout=15)
        data = resp.json()

        if "Global Quote" in data:
            price = data["Global Quote"].get("05. price", "N/D")
            return {"status": "OK", "sample": f"SPY = ${price}"}
        elif "Note" in data:
            return {"status": "WARN", "reason": "Rate limited (5 calls/min free tier)"}
        else:
            return {"status": "WARN", "reason": "Unexpected response format"}

    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_nyfed() -> Dict[str, Any]:
    """Check NY Fed API (free, no key)."""
    try:
        from greybark.data_sources.nyfed_client import NYFedClient
        client = NYFedClient()
        rates = client.get_reference_rates()
        if not rates:
            return {"status": "WARN", "reason": "NY Fed returned empty"}

        sofr = rates.get("sofr", {})
        return {
            "status": "OK",
            "sample": f"SOFR = {sofr.get('rate', 'N/D')}%",
            "date": sofr.get("date", "N/D"),
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_imf() -> Dict[str, Any]:
    """Check IMF WEO DataMapper API (free, no key)."""
    try:
        from imf_weo_client import IMFWEOClient
        client = IMFWEOClient()
        data = client.fetch_consensus()
        if not data or data.get("error"):
            return {"status": "WARN", "reason": data.get("error", "Empty response")}

        gdp_usa = data.get("gdp", {}).get("usa")
        return {
            "status": "OK",
            "sample": f"USA GDP forecast = {gdp_usa}%",
            "source": data.get("source", "IMF WEO"),
        }
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_yfinance() -> Dict[str, Any]:
    """Check yfinance connectivity."""
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY")
        info = spy.info
        price = info.get("regularMarketPrice") or info.get("previousClose")
        if price:
            return {"status": "OK", "sample": f"SPY = ${price:.2f}"}
        return {"status": "WARN", "reason": "yfinance returned no price"}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_bea() -> Dict[str, Any]:
    """Check BEA API connectivity."""
    try:
        from greybark.config import config
        api_key = getattr(getattr(config, 'bea', None), 'api_key', None)
        if not api_key:
            api_key = os.environ.get("BEA_API_KEY")
        if not api_key:
            return {"status": "SKIP", "reason": "BEA_API_KEY not set (optional)"}

        from greybark.data_sources.bea_client import BEAClient
        client = BEAClient()
        gdp = client.get_gdp_components()
        if gdp and gdp.get("gdp_total") is not None:
            return {"status": "OK", "sample": f"GDP QoQ = {gdp['gdp_total']}%"}
        return {"status": "WARN", "reason": "BEA returned empty GDP"}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_anthropic() -> Dict[str, Any]:
    """Check Anthropic API key is set (no actual call to save cost)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            from greybark.config import CLAUDE_API_KEY
            api_key = CLAUDE_API_KEY or ""
        except Exception:
            pass
    if not api_key:
        return {"status": "FAIL", "reason": "ANTHROPIC_API_KEY not set (env nor greybark.config)"}
    if api_key.startswith("sk-ant-"):
        return {"status": "OK", "sample": f"Key: sk-ant-...{api_key[-4:]}"}
    return {"status": "OK", "sample": f"Key present ({len(api_key)} chars)"}


def _check_ecb() -> Dict[str, Any]:
    """Check ECB API connectivity (free, no key)."""
    try:
        from ecb_client import ECBClient
        client = ECBClient()
        data = client.fetch_euro_macro()
        if not data:
            return {"status": "WARN", "reason": "ECB returned empty"}
        dfr = data.get("ecb_dfr")
        sample = f"DFR = {dfr}%" if dfr is not None else "Connected"
        return {"status": "OK", "sample": sample}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_bcrp() -> Dict[str, Any]:
    """Check BCRP EMBI API connectivity (free, no key)."""
    try:
        from bcrp_embi_client import BCRPEmbiClient
        client = BCRPEmbiClient()
        series = client.fetch_embi_series()
        if not series:
            return {"status": "WARN", "reason": "BCRP returned empty"}
        # Count available series
        n = sum(1 for v in series.values() if v is not None and len(v) > 0)
        return {"status": "OK", "sample": f"{n} EMBI series loaded"}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_bloomberg() -> Dict[str, Any]:
    """Check Bloomberg Excel data availability (local file)."""
    try:
        from bloomberg_reader import BloombergData
        bbg = BloombergData()
        if not bbg.available:
            return {"status": "SKIP", "reason": "bloomberg_data.xlsx not found or empty"}
        n_series = len(bbg.campo_ids) if hasattr(bbg, 'campo_ids') else 0
        n_sheets = len(bbg.sheets) if hasattr(bbg, 'sheets') else 0
        return {"status": "OK", "sample": f"{n_series} series, {n_sheets} sheets"}
    except Exception as e:
        return {"status": "SKIP", "reason": str(e)[:200]}


def _check_oecd() -> Dict[str, Any]:
    """Check OECD API connectivity (free, no key)."""
    try:
        from greybark.data_sources.oecd_client import OECDClient
        client = OECDClient()
        # Quick test: fetch CLI for USA
        data = client.get_cli()
        if not data:
            return {"status": "WARN", "reason": "OECD returned empty"}
        usa_cli = data.get("USA", {}).get("latest")
        return {"status": "OK", "sample": f"USA CLI = {usa_cli}" if usa_cli else "CLI data accessible"}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_akshare() -> Dict[str, Any]:
    """Check AKShare (China data) connectivity."""
    try:
        from greybark.data_sources.akshare_client import AKShareClient
        client = AKShareClient()
        data = client.get_china_monthly()
        if not data:
            return {"status": "WARN", "reason": "AKShare returned empty"}
        pmi = data.get("pmi_mfg", {})
        val = pmi.get("value") if isinstance(pmi, dict) else pmi
        sample = f"PMI Mfg = {val}" if val else "Connected"
        return {"status": "OK", "sample": sample}
    except ImportError:
        return {"status": "SKIP", "reason": "akshare not installed"}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


def _check_commloan() -> Dict[str, Any]:
    """Check CommLoan SOFR scraper connectivity."""
    try:
        from greybark.data_sources.commloan_scraper import CommLoanScraper
        scraper = CommLoanScraper()
        rates = scraper.get_sofr_forwards()
        if not rates:
            return {"status": "WARN", "reason": "CommLoan returned empty"}
        tenor_1y = rates.get("1Y", rates.get("12M"))
        sample = f"SOFR 1Y = {tenor_1y}%" if tenor_1y else f"{len(rates)} tenors"
        return {"status": "OK", "sample": sample}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)[:200]}


# ─────────────────────────────────────────────
# API Registry (14 APIs)
# ─────────────────────────────────────────────

API_CHECKS = {
    # Critical (pipeline aborts if these fail)
    "Anthropic (Claude)":   {"fn": _check_anthropic,     "critical": True,  "slow": False},
    "FRED":                 {"fn": _check_fred,           "critical": True,  "slow": False},
    "BCCh":                 {"fn": _check_bcch,           "critical": True,  "slow": False},
    # Important (reports degrade but still run)
    "AlphaVantage":         {"fn": _check_alphavantage,   "critical": False, "slow": False},
    "NY Fed":               {"fn": _check_nyfed,          "critical": False, "slow": False},
    "IMF WEO":              {"fn": _check_imf,            "critical": False, "slow": False},
    "ECB":                  {"fn": _check_ecb,            "critical": False, "slow": False},
    "BCRP (EMBI)":          {"fn": _check_bcrp,           "critical": False, "slow": False},
    "CommLoan (SOFR)":      {"fn": _check_commloan,       "critical": False, "slow": False},
    # Optional (tested in all modes)
    "yfinance":             {"fn": _check_yfinance,       "critical": False, "slow": False},
    "BEA":                  {"fn": _check_bea,            "critical": False, "slow": False},
    "OECD":                 {"fn": _check_oecd,           "critical": False, "slow": False},
    "Bloomberg (Excel)":    {"fn": _check_bloomberg,      "critical": False, "slow": False},
    # Slow (skip in quick mode — known timeouts)
    "AKShare (China)":      {"fn": _check_akshare,        "critical": False, "slow": True},
}


# ─────────────────────────────────────────────
# Main Check Function
# ─────────────────────────────────────────────

def check_all_apis(quick: bool = False) -> Dict[str, Any]:
    """
    Run health checks on all configured APIs.

    Args:
        quick: If True, skip slow sources (yfinance, BEA)

    Returns:
        Dict with per-API results, overall verdict, and summary.
    """
    results = {}
    start = time.time()

    for name, spec in API_CHECKS.items():
        if quick and spec["slow"]:
            results[name] = {"status": "SKIP", "reason": "Skipped (quick mode)"}
            continue

        t0 = time.time()
        try:
            result = spec["fn"]()
        except Exception as e:
            result = {"status": "FAIL", "reason": str(e)[:200]}
        result["elapsed_ms"] = int((time.time() - t0) * 1000)
        result["critical"] = spec["critical"]
        results[name] = result

    elapsed = time.time() - start

    # Compute verdict
    critical_fails = [
        name for name, r in results.items()
        if r.get("critical") and r.get("status") == "FAIL"
    ]
    all_fails = [name for name, r in results.items() if r.get("status") == "FAIL"]
    all_warns = [name for name, r in results.items() if r.get("status") == "WARN"]

    if critical_fails:
        verdict = "NO_GO"
    elif all_fails or all_warns:
        verdict = "CAUTION"
    else:
        verdict = "GO"

    return {
        "timestamp": datetime.now().isoformat(),
        "elapsed_s": round(elapsed, 1),
        "verdict": verdict,
        "critical_fails": critical_fails,
        "results": results,
    }


# ─────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────

def format_health_report(result: Dict[str, Any]) -> str:
    """Format health check results for console output."""
    lines = []
    verdict = result["verdict"]
    icon = {"GO": "OK", "CAUTION": "WARN", "NO_GO": "FAIL"}[verdict]

    lines.append(f"  API Health Check: [{icon}] {verdict} ({result['elapsed_s']}s)")
    lines.append("")

    for name, r in result["results"].items():
        status = r.get("status", "?")
        ms = r.get("elapsed_ms", 0)
        critical = " *" if r.get("critical") else ""

        if status == "OK":
            sample = r.get("sample", "")
            lines.append(f"    [OK]   {name}{critical} ({ms}ms) — {sample}")
        elif status == "WARN":
            lines.append(f"    [WARN] {name}{critical} ({ms}ms) — {r.get('reason', '')}")
        elif status == "FAIL":
            lines.append(f"    [FAIL] {name}{critical} ({ms}ms) — {r.get('reason', '')}")
        elif status == "SKIP":
            lines.append(f"    [SKIP] {name}")

    if result["critical_fails"]:
        lines.append("")
        lines.append(f"  CRITICAL: {', '.join(result['critical_fails'])} failed — pipeline may not run correctly")

    lines.append("")
    lines.append("  (* = critical for pipeline)")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Greybark API Health Checker")
    parser.add_argument("--quick", action="store_true", help="Skip slow sources")
    args = parser.parse_args()

    # Load env
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass

    print("\n" + "=" * 50)
    print("GREYBARK RESEARCH — API HEALTH CHECK")
    print("=" * 50 + "\n")

    result = check_all_apis(quick=args.quick)
    print(format_health_report(result))


if __name__ == "__main__":
    main()

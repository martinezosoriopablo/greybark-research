"""
Curvas Soberanas — Greybark Research AI Investment Council

Fetches sovereign yield curves from two central banks:
  - Germany (ECB Data Portal API, AAA Svensson spot rates)
  - Japan (Ministry of Finance, JGB benchmark yields)

Both APIs are public and require no authentication.
"""

import io
import json
import logging
import time
from datetime import date
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 15  # seconds

# ECB Data Portal — AAA-rated Svensson spot rates
ECB_BASE = "https://data-api.ecb.europa.eu/service/data/YC"
ECB_SERIES = {
    1:  "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y",
    2:  "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    3:  "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3Y",
    5:  "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_5Y",
    7:  "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_7Y",
    10: "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
    15: "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_15Y",
    20: "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_20Y",
    30: "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_30Y",
}

# Ministry of Finance Japan — JGB benchmark yields
MOF_URL = "https://www.mof.go.jp/english/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
MOF_TENORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 25, 30, 40]

# Cache
CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_FILE = CACHE_DIR / "yield_curves_cache.json"


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def _fetch_ecb() -> Optional[Dict]:
    """Fetch German sovereign curve from ECB Data Portal API."""
    datos: Dict[int, float] = {}
    as_of = None

    for tenor, series_key in ECB_SERIES.items():
        url = f"{ECB_BASE}/{series_key}?format=csvdata&lastNObservations=1"
        try:
            resp = requests.get(
                url,
                headers={"Accept": "text/csv"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty or "OBS_VALUE" not in df.columns:
                logger.warning("ECB: empty response for tenor %dY", tenor)
                continue
            val = df["OBS_VALUE"].dropna().iloc[-1]
            if pd.notna(val):
                datos[tenor] = round(float(val), 4)
                if as_of is None and "TIME_PERIOD" in df.columns:
                    as_of = str(df["TIME_PERIOD"].iloc[-1])
        except Exception as exc:
            logger.warning("ECB: failed to fetch %dY: %s", tenor, exc)

    if not datos:
        return None

    spreads = {}
    if 2 in datos and 10 in datos:
        spreads["2s10s"] = round(datos[10] - datos[2], 4)
    if 5 in datos and 30 in datos:
        spreads["5s30s"] = round(datos[30] - datos[5], 4)

    return {
        "fuente": "ECB Data Portal API",
        "tipo": "AAA-rated spot rate (Svensson)",
        "as_of": as_of,
        "datos": datos,
        "spreads": spreads,
    }


def _fetch_mof() -> Optional[Dict]:
    """Fetch JGB curve from Ministry of Finance Japan."""
    try:
        resp = requests.get(MOF_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        # Skip first row (description), second row is header
        df = pd.read_csv(io.StringIO(resp.text), skiprows=1)
    except Exception as exc:
        logger.warning("MoF Japan: request failed: %s", exc)
        return None

    if df.empty:
        logger.warning("MoF Japan: empty CSV")
        return None

    # Last row = most recent
    last = df.iloc[-1]
    as_of = str(last.iloc[0]) if pd.notna(last.iloc[0]) else None

    datos: Dict[int, float] = {}
    # Columns after Date: 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 15Y, 20Y, 25Y, 30Y, 40Y
    for i, tenor in enumerate(MOF_TENORS):
        col_idx = i + 1  # skip date column
        if col_idx >= len(last):
            break
        val = last.iloc[col_idx]
        try:
            fval = float(val)
            if pd.notna(fval):
                datos[tenor] = round(fval, 4)
        except (ValueError, TypeError):
            continue

    if not datos:
        return None

    spreads = {}
    if 2 in datos and 10 in datos:
        spreads["2s10s"] = round(datos[10] - datos[2], 4)
    if 10 in datos and 30 in datos:
        spreads["10s30s"] = round(datos[30] - datos[10], 4)

    return {
        "fuente": "Ministry of Finance Japan",
        "tipo": "JGB benchmark yield",
        "as_of": as_of,
        "datos": datos,
        "spreads": spreads,
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _normalize_keys(data: Dict) -> Dict:
    """Restore integer keys in datos/spreads after JSON round-trip."""
    for key in ("alemania", "japon"):
        curve = data.get(key)
        if not curve or not isinstance(curve, dict):
            continue
        if "datos" in curve:
            curve["datos"] = {int(k): v for k, v in curve["datos"].items()}
    return data


def _read_cache() -> Optional[Dict]:
    """Read cached data if it exists."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return _normalize_keys(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(data: Dict) -> None:
    """Write data to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["_cache_ts"] = time.time()
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except OSError as exc:
        logger.warning("Cache write failed: %s", exc)


def _cache_valid(cached: Dict, cache_hours: int) -> bool:
    """Check if cache is still valid."""
    ts = cached.get("_cache_ts", 0)
    return (time.time() - ts) < cache_hours * 3600


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

def _classify_shape(datos: Dict[int, float]) -> str:
    """Classify curve shape from yield data."""
    tenors = sorted(datos.keys())
    if len(tenors) < 3:
        return "Datos insuficientes"

    short = datos.get(2, datos.get(1, None))
    mid = datos.get(5, datos.get(3, None))
    long_end = datos.get(10, datos.get(7, None))

    if short is None or long_end is None:
        return "Datos insuficientes"

    spread_2s10s = long_end - short
    if spread_2s10s < -0.1:
        if mid and mid > short and mid > long_end:
            return "Invertida con humped"
        return "Invertida"
    elif spread_2s10s < 0.15:
        return "Plana"
    elif spread_2s10s < 0.80:
        return "Normal moderada"
    else:
        return "Normal empinada"


def _build_narrative(data: Dict) -> str:
    """Generate narrative summary from curve data."""
    fecha = data.get("fecha_consulta", "N/D")
    parts = [f"Curvas soberanas al {fecha}."]

    for key, label in [("alemania", "Alemania (Bund)"), ("japon", "Japón (JGB)")]:
        curve = data.get(key)
        if not curve:
            parts.append(f"{label}: datos no disponibles.")
            continue

        datos = curve["datos"]
        spreads = curve.get("spreads", {})
        forma = _classify_shape(datos)

        y10 = datos.get(10)
        y10_str = f"{y10:.2f}%" if y10 is not None else "N/D"

        spread_2s10s = spreads.get("2s10s")
        s_str = f"{int(round(spread_2s10s * 100))} pb" if spread_2s10s is not None else "N/D"

        parts.append(f"{label}: {forma.lower()}, 2s10s = {'+' if spread_2s10s and spread_2s10s > 0 else ''}{s_str}, 10Y en {y10_str}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def get_yield_curves(use_cache: bool = True, cache_hours: int = 4) -> Dict:
    """
    Fetch sovereign yield curves from ECB and MoF Japan.

    Args:
        use_cache: Whether to use cached data if available and fresh.
        cache_hours: Cache TTL in hours.

    Returns:
        Dict with keys: fecha_consulta, alemania, japon, resumen_narrativo.

    Raises:
        RuntimeError: If all sources fail and no cache is available.
    """
    # Check cache
    if use_cache:
        cached = _read_cache()
        if cached and _cache_valid(cached, cache_hours):
            logger.info("Using cached yield curves (age: %.1f hours)",
                        (time.time() - cached.get("_cache_ts", 0)) / 3600)
            cached["desde_cache"] = True
            return cached

    # Fetch from both sources
    logger.info("Fetching sovereign yield curves...")
    alemania = _fetch_ecb()
    if alemania:
        logger.info("  ECB (Alemania): %d tenors", len(alemania["datos"]))
    else:
        logger.warning("  ECB (Alemania): FAILED")

    japon = _fetch_mof()
    if japon:
        logger.info("  MoF (Japón): %d tenors", len(japon["datos"]))
    else:
        logger.warning("  MoF (Japón): FAILED")

    # If all failed, try stale cache
    if not alemania and not japon:
        if use_cache:
            cached = _read_cache()
            if cached:
                logger.warning("All sources failed — returning stale cache")
                cached["desde_cache"] = True
                cached["stale"] = True
                return cached
        raise RuntimeError(
            "All sovereign yield curve sources failed and no cache available. "
            "Check network connectivity and API availability."
        )

    result = {
        "fecha_consulta": date.today().isoformat(),
        "alemania": alemania,
        "japon": japon,
        "desde_cache": False,
    }
    result["resumen_narrativo"] = _build_narrative(result)

    # Update cache
    _write_cache(result)

    return result


# ---------------------------------------------------------------------------
# Council prompt formatter
# ---------------------------------------------------------------------------

def format_for_council_prompt(data: Dict) -> str:
    """
    Format yield curves as a text block for injection into
    AI Council agent system prompts.
    """
    fecha = data.get("fecha_consulta", "N/D")
    lines = [f"=== CURVAS SOBERANAS ({fecha}) ===", ""]

    configs = [
        ("alemania", "ALEMANIA (Bund, AAA, Svensson)", [1, 2, 5, 10, 30], ["2s10s", "5s30s"]),
        ("japon", "JAPÓN (JGB Benchmark, MoF)", [1, 2, 5, 10, 30], ["2s10s", "10s30s"]),
    ]

    for key, label, display_tenors, spread_keys in configs:
        curve = data.get(key)
        if not curve:
            lines.append(f"{label}:")
            lines.append("  Datos no disponibles")
            lines.append("")
            continue

        datos = curve["datos"]
        spreads = curve.get("spreads", {})
        forma = _classify_shape(datos)

        # Yields line
        yield_parts = []
        for t in display_tenors:
            val = datos.get(t) or datos.get(str(t))
            if val is not None:
                yield_parts.append(f"{t}Y: {val:.2f}%")
        yields_str = " | ".join(yield_parts)

        # Spreads line
        spread_parts = []
        for sk in spread_keys:
            sv = spreads.get(sk)
            if sv is not None:
                bps = int(round(sv * 100))
                sign = "+" if bps > 0 else ""
                spread_parts.append(f"Spread {sk}: {sign}{bps} pb")
        spreads_str = " | ".join(spread_parts) if spread_parts else "N/D"

        lines.append(f"{label}:")
        lines.append(f"  {yields_str}")
        lines.append(f"  {spreads_str}")
        lines.append(f"  Forma: {forma}")
        lines.append("")

    lines.append("=== FIN CURVAS ===")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    data = get_yield_curves(use_cache=False)
    print(format_for_council_prompt(data))
    print()
    print("Narrativo:", data.get("resumen_narrativo", ""))

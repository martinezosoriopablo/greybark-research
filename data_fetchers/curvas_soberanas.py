# -*- coding: utf-8 -*-
"""
Curvas Soberanas — Greybark Research AI Investment Council

Fetches sovereign yield curves from two central banks:
  - ECB Data Portal API (German/Euro AAA Svensson curve)
  - Ministry of Finance Japan (JGB benchmark yields)

Usage:
    from data_fetchers.curvas_soberanas import get_yield_curves, format_for_council_prompt

    data = get_yield_curves(use_cache=True, cache_hours=4)
    text = format_for_council_prompt(data)
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

REQUEST_TIMEOUT = 30

# ---------------------------------------------------------------------------
# ECB Data Portal — Euro area AAA sovereign yield curve (Svensson model)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# MoF Japan — JGB benchmark yields
# ---------------------------------------------------------------------------
MOF_URL = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"
MOF_TENORS = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 40]

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / "cache"
CACHE_FILE = CACHE_DIR / "yield_curves_cache.json"


# ===================================================================
#  ECB
# ===================================================================
def _fetch_ecb() -> Dict:
    """Fetch German sovereign curve from ECB Data Portal API."""
    import time as _time

    datos = {}
    fecha = None
    session = requests.Session()
    session.headers.update({"Accept": "text/csv"})

    for i, (tenor, series_key) in enumerate(ECB_SERIES.items()):
        try:
            # Small delay between requests to avoid rate limiting
            if i > 0:
                _time.sleep(0.5)
            url = f"{ECB_BASE}/{series_key}?format=csvdata&lastNObservations=1"
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))

            if df.empty or "OBS_VALUE" not in df.columns:
                logger.warning("ECB: empty response for tenor %dY", tenor)
                continue

            row = df.dropna(subset=["OBS_VALUE"]).iloc[-1]
            if pd.notna(row["OBS_VALUE"]):
                datos[tenor] = round(float(row["OBS_VALUE"]), 4)
                if fecha is None and "TIME_PERIOD" in df.columns:
                    fecha = str(row["TIME_PERIOD"])
        except Exception as e:
            logger.warning("ECB: failed to fetch %dY: %s", tenor, e)

    # Spreads
    spreads = {}
    if 2 in datos and 10 in datos:
        spreads["2s10s"] = round(datos[10] - datos[2], 2)
    if 5 in datos and 30 in datos:
        spreads["5s30s"] = round(datos[30] - datos[5], 2)

    return {
        "datos": datos,
        "spreads": spreads,
        "fecha": fecha,
        "fuente": "ECB Data Portal API",
        "tipo": "AAA-rated spot rate (Svensson)",
    }


# ===================================================================
#  MoF Japan
# ===================================================================
def _fetch_mof() -> Dict:
    """Fetch JGB curve from Ministry of Finance Japan."""
    try:
        resp = requests.get(MOF_URL, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("MoF Japan: request failed: %s", e)
        return {"datos": {}, "spreads": {}}

    try:
        # Skip first row (descriptive title), second row is header
        df = pd.read_csv(io.StringIO(resp.text), skiprows=1)
    except Exception as e:
        logger.warning("MoF Japan: CSV parse failed: %s", e)
        return {"datos": {}, "spreads": {}}

    if df.empty:
        logger.warning("MoF Japan: empty CSV")
        return {"datos": {}, "spreads": {}}

    # Last row = most recent
    row = df.iloc[-1]
    fecha = str(row.iloc[0]) if pd.notna(row.iloc[0]) else None

    # Map column names to tenors
    # Columns: Date, 1Y, 2Y, 3Y, 4Y, 5Y, 6Y, 7Y, 8Y, 9Y, 10Y, 15Y, 20Y, 25Y, 30Y, 40Y
    datos = {}
    for i, tenor in enumerate(MOF_TENORS):
        col_name = f"{tenor}Y"
        if col_name in df.columns:
            val = row.get(col_name)
            if pd.notna(val):
                try:
                    datos[tenor] = round(float(val), 4)
                except (ValueError, TypeError):
                    pass

    # Spreads
    spreads = {}
    if 2 in datos and 10 in datos:
        spreads["2s10s"] = round(datos[10] - datos[2], 3)
    if 10 in datos and 30 in datos:
        spreads["10s30s"] = round(datos[30] - datos[10], 3)

    return {
        "datos": datos,
        "spreads": spreads,
        "fecha": fecha,
        "fuente": "Ministry of Finance Japan",
        "tipo": "JGB benchmark yield",
    }


# ===================================================================
#  Helpers
# ===================================================================
def _normalize_keys(data: Dict) -> Dict:
    """Restore integer keys in datos/spreads after JSON round-trip."""
    for country in ("alemania", "japon"):
        block = data.get(country)
        if not isinstance(block, dict):
            continue
        for sub in ("datos",):
            d = block.get(sub, {})
            if isinstance(d, dict):
                block[sub] = {int(k): v for k, v in d.items()}
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
            json.dump(data, f, default=str)
    except OSError as e:
        logger.warning("Cache write failed: %s", e)


def _cache_valid(data: Dict, cache_hours: float) -> bool:
    """Check if cache is still valid."""
    ts = data.get("_cache_ts")
    if ts is None:
        return False
    return (time.time() - ts) < cache_hours * 3600


def _classify_shape(datos: Dict[int, float]) -> str:
    """Classify curve shape from yield data."""
    tenors = sorted(datos.keys())
    if len(tenors) < 3:
        return "Datos insuficientes"

    short = datos.get(2, datos.get(1))
    mid = datos.get(5, datos.get(7))
    long = datos.get(10, datos.get(30))

    if short is None or long is None:
        return "Datos insuficientes"

    diff = long - short

    # Check for hump
    if mid is not None and mid > long and mid > short:
        return "Invertida con humped"

    if diff < -0.1:
        return "Invertida"
    elif diff < 0.2:
        return "Plana"
    elif diff < 1.0:
        return "Normal moderada"
    else:
        return "Normal empinada"


def _build_narrative(data: Dict) -> str:
    """Generate narrative summary from curve data."""
    parts = []
    fecha = data.get("fecha_consulta", "N/D")
    parts.append(f"Curvas soberanas al {fecha}:")

    for key, label in [("alemania", "Alemania (Bund AAA)"), ("japon", "Japon (JGB)")]:
        block = data.get(key)
        if not block or not block.get("datos"):
            parts.append(f"  {label}: datos no disponibles.")
            continue

        shape = _classify_shape(block["datos"])
        y10 = block["datos"].get(10)
        spread_2s10s = block.get("spreads", {}).get("2s10s")

        line = f"  {label}: forma {shape.lower()}"
        if y10 is not None:
            line += f", 10Y en {round(y10, 2)}%"
        if spread_2s10s is not None:
            line += f", 2s10s = {int(round(spread_2s10s * 100))}bps"
        parts.append(line)

    return " ".join(parts)


# ===================================================================
#  Public API
# ===================================================================
def get_yield_curves(use_cache: bool = True, cache_hours: float = 4.0) -> Dict:
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
    # Check cache first
    cached = _read_cache() if use_cache else None
    if cached and _cache_valid(cached, cache_hours):
        age_h = (time.time() - cached.get("_cache_ts", 0)) / 3600
        logger.info("Using cached yield curves (age: %.1f hours)", age_h)
        cached["desde_cache"] = True
        return cached

    logger.info("Fetching sovereign yield curves...")

    # Fetch from APIs
    ecb_data = _fetch_ecb()
    mof_data = _fetch_mof()

    ecb_ok = len(ecb_data.get("datos", {})) > 0
    mof_ok = len(mof_data.get("datos", {})) > 0

    if ecb_ok:
        logger.info("  ECB (Alemania): %d tenors", len(ecb_data["datos"]))
    else:
        logger.warning("  ECB (Alemania): FAILED")

    if mof_ok:
        logger.info("  MoF (Japon): %d tenors", len(mof_data["datos"]))
    else:
        logger.warning("  MoF (Japon): FAILED")

    # If both failed, try stale cache
    if not ecb_ok and not mof_ok:
        if cached:
            logger.warning("All sources failed — returning stale cache")
            cached["stale"] = True
            return cached
        raise RuntimeError(
            "All sovereign yield curve sources failed and no cache available. "
            "Check network connectivity and API availability."
        )

    result = {
        "fecha_consulta": date.today().isoformat(),
        "alemania": ecb_data,
        "japon": mof_data,
    }
    result["resumen_narrativo"] = _build_narrative(result)

    # Write cache
    _write_cache(result)

    return result


def format_for_council_prompt(data: Dict) -> str:
    """
    Format yield curves as a text block for injection into
    AI Council agent system prompts.
    """
    fecha = data.get("fecha_consulta", "N/D")
    lines = [f"=== CURVAS SOBERANAS ({fecha}) ==="]

    for key, label in [
        ("alemania", "ALEMANIA (Bund, AAA, Svensson)"),
        ("japon", "JAPON (JGB Benchmark, MoF)"),
    ]:
        lines.append("")
        block = data.get(key)
        if not block or not block.get("datos"):
            lines.append(f"  {label}")
            lines.append("  Datos no disponibles")
            continue

        shape = _classify_shape(block["datos"])
        lines.append(f"  {label} — Forma: {shape}")

        # Yields by tenor
        datos = block["datos"]
        for tenor in sorted(datos.keys()):
            lines.append(f"    {tenor}Y: {round(datos[tenor], 2)}%")

        # Spreads
        spreads = block.get("spreads", {})
        for skey in ("2s10s", "5s30s", "10s30s"):
            if skey in spreads:
                bps = int(round(spreads[skey] * 100))
                lines.append(f"    Spread {skey}: {bps}bps")

    return "\n".join(lines)


# ===================================================================
#  CLI test
# ===================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    data = get_yield_curves(use_cache=False)
    print(format_for_council_prompt(data))
    print()
    print("Narrativo:", data.get("resumen_narrativo", ""))

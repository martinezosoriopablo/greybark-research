# -*- coding: utf-8 -*-
"""
Greybark Research — BCRP EMBI Client
=====================================

Descarga spreads EMBIG desde la API pública del Banco Central
de Reserva del Perú (BCRP).  Datos mensuales desde 2006.

API docs: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api

Usage standalone:
    python bcrp_embi_client.py

Usage programático:
    from bcrp_embi_client import BCRPEmbiClient
    client = BCRPEmbiClient()
    series = client.fetch_embi_series()   # Dict[campo_id, pd.Series]
"""

import sys
from datetime import datetime
from typing import Dict, Optional

sys.stdout.reconfigure(encoding='utf-8')

try:
    import requests
except ImportError:
    requests = None

try:
    import pandas as pd
except ImportError:
    pd = None


# BCRP series codes → Bloomberg-compatible campo_id
BCRP_EMBI_MAP = {
    'PN01138XM': 'embi_total',       # Emergentes composite
    'PN01131XM': 'embi_brasil',
    'PN01135XM': 'embi_mexico',
    'PN01133XM': 'embi_colombia',
    'PN01132XM': 'embi_chile',
    'PN01129XM': 'embi_peru',
    'PN01130XM': 'embi_argentina',
    'PN01137XM': 'embi_latam',
}

# Human-readable descriptions for metadata
EMBI_DESCRIPTIONS = {
    'embi_total':     'EMBIG Emergentes Composite',
    'embi_brasil':    'EMBIG Brasil',
    'embi_mexico':    'EMBIG México',
    'embi_colombia':  'EMBIG Colombia',
    'embi_chile':     'EMBIG Chile',
    'embi_peru':      'EMBIG Perú',
    'embi_argentina': 'EMBIG Argentina',
    'embi_latam':     'EMBIG LatAm',
}

BASE_URL = 'https://estadisticas.bcrp.gob.pe/estadisticas/series/api'
TIMEOUT = 15


class BCRPEmbiClient:
    """Client for BCRP public REST API — EMBI Global spreads."""

    def __init__(self, start_year: int = 2006):
        self.start_year = start_year

    def fetch_embi_series(self) -> Dict[str, 'pd.Series']:
        """
        Fetch all EMBIG series from BCRP.

        Returns:
            Dict mapping campo_id (e.g. 'embi_peru') to pd.Series
            with monthly DatetimeIndex and float values (bps).
            Empty dict on failure.
        """
        if not requests or not pd:
            print("  [BCRP] requests o pandas no instalado")
            return {}

        codes = list(BCRP_EMBI_MAP.keys())
        codes_str = '-'.join(codes)

        start = f'{self.start_year}-1'
        now = datetime.now()
        end = f'{now.year}-{now.month}'

        url = f'{BASE_URL}/{codes_str}/json/{start}/{end}/ing'

        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [BCRP] Error fetching EMBI: {e}")
            return {}

        return self._parse_response(data, codes)

    def _parse_response(
        self, data: dict, codes: list
    ) -> Dict[str, 'pd.Series']:
        """Parse BCRP JSON response into dict of pd.Series.

        The API returns series sorted by code number (ascending),
        regardless of the order in the URL.  We use positional mapping
        based on sorted codes.
        """
        config_series = data.get('config', {}).get('series', [])
        periods = data.get('periods', [])

        if not periods:
            print("  [BCRP] Sin períodos en respuesta")
            return {}

        # API returns series sorted by code — build positional mapping
        sorted_codes = sorted(c for c in codes if c in BCRP_EMBI_MAP)
        if len(sorted_codes) != len(config_series):
            print(f"  [BCRP] Warning: {len(sorted_codes)} codes vs "
                  f"{len(config_series)} series in response")

        idx_to_campo: Dict[int, str] = {}
        for i, code in enumerate(sorted_codes):
            idx_to_campo[i] = BCRP_EMBI_MAP[code]

        result: Dict[str, 'pd.Series'] = {}

        # Collect dates + values per series
        series_data: Dict[str, tuple] = {
            campo: ([], []) for campo in BCRP_EMBI_MAP.values()
        }

        for period in periods:
            name = period.get('name', '')  # e.g. "Jan.2024"
            dt = self._parse_period(name)
            if dt is None:
                continue

            values = period.get('values', [])
            for idx, campo in idx_to_campo.items():
                if idx >= len(values):
                    continue
                raw = values[idx]
                if raw is None or raw == '' or raw == 'n.d.':
                    continue
                try:
                    val = float(raw)
                except (ValueError, TypeError):
                    continue
                series_data[campo][0].append(dt)
                series_data[campo][1].append(val)

        for campo, (dates, vals) in series_data.items():
            if dates:
                s = pd.Series(vals, index=pd.DatetimeIndex(dates), name=campo)
                s = s.sort_index()
                result[campo] = s

        return result

    @staticmethod
    def _parse_period(name: str) -> Optional[datetime]:
        """Parse BCRP period string like 'Jan.06' or 'Feb.24' to datetime."""
        # Formats seen: "Jan.06", "Feb.24", "Dec.99"
        for fmt in ('%b.%y', '%b.%Y'):
            try:
                return datetime.strptime(name, fmt)
            except ValueError:
                continue
        return None


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("BCRP EMBI Client — Test\n")
    client = BCRPEmbiClient()
    series = client.fetch_embi_series()

    if not series:
        print("ERROR: No se obtuvieron series")
        sys.exit(1)

    for campo, s in sorted(series.items()):
        last = s.iloc[-1]
        prev = s.iloc[-2] if len(s) > 1 else None
        rng = f"{s.index[0].strftime('%Y-%m')} → {s.index[-1].strftime('%Y-%m')}"
        chg = ''
        if prev is not None:
            diff = last - prev
            chg = f"  chg: {'+' if diff >= 0 else ''}{diff:.0f}"
        print(f"  {campo:20s}: {last:7.0f} bps  ({len(s)} obs, {rng}){chg}")

    print(f"\nTotal: {len(series)} series OK")

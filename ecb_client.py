# -*- coding: utf-8 -*-
"""
Greybark Research — ECB Client
================================

Descarga series macro de la API REST pública del BCE (SDMX 2.1).
Provee datos únicos no disponibles en BCCh: HICP, DFR, M3, EUR/USD, EA 10Y.

API: https://data-api.ecb.europa.eu (CSV format, sin auth)

Usage standalone:
    python ecb_client.py

Usage programático:
    from ecb_client import ECBClient
    client = ECBClient()
    data = client.fetch_euro_macro()   # Dict[str, float | None]
"""

import sys
import csv
import io
from typing import Dict, Optional

sys.stdout.reconfigure(encoding='utf-8')

try:
    import requests
except ImportError:
    requests = None


BASE_URL = 'https://data-api.ecb.europa.eu/service/data'
TIMEOUT = 15

# Series confirmadas funcionando — (dataset, key, last_n, description)
ECB_SERIES = {
    'ecb_dfr': {
        'dataset': 'FM',
        'key': 'B.U2.EUR.4F.KR.DFR.LEV',
        'last_n': 3,
        'description': 'ECB Deposit Facility Rate',
        'unit': '%',
    },
    'hicp_euro_yoy': {
        'dataset': 'ICP',
        'key': 'M.U2.N.000000.4.ANR',
        'last_n': 3,
        'description': 'Euro Area HICP YoY',
        'unit': '%',
    },
    'ea_10y_yield': {
        'dataset': 'FM',
        'key': 'M.U2.EUR.4F.BB.U2_10Y.YLD',
        'last_n': 3,
        'description': 'Euro Area 10Y Govt Yield',
        'unit': '%',
    },
    'eur_usd': {
        'dataset': 'EXR',
        'key': 'M.USD.EUR.SP00.A',
        'last_n': 3,
        'description': 'EUR/USD',
        'unit': '',
        'invert': True,  # API returns EUR per USD → invert for EUR/USD
    },
    'm3_euro_stock': {
        'dataset': 'BSI',
        'key': 'M.U2.N.V.M30.X.1.U2.2300.Z01.E',
        'last_n': 3,
        'description': 'Euro Area M3 (EUR mn)',
        'unit': 'EUR mn',
    },
}

# Human-readable descriptions for metadata injection
ECB_DESCRIPTIONS = {k: v['description'] for k, v in ECB_SERIES.items()}


class ECBClient:
    """Client for ECB SDMX REST API — Euro macro series (CSV format)."""

    def fetch_euro_macro(self) -> Dict[str, Optional[float]]:
        """
        Fetch all ECB series and return latest values.

        Returns:
            Dict mapping campo_id → latest float value (or None on error).
        """
        if not requests:
            print("  [ECB] requests no instalado")
            return {}

        result: Dict[str, Optional[float]] = {}

        for campo_id, spec in ECB_SERIES.items():
            val = self._fetch_one(
                dataset=spec['dataset'],
                key=spec['key'],
                last_n=spec['last_n'],
                invert=spec.get('invert', False),
            )
            result[campo_id] = val

        return result

    def _fetch_one(
        self, dataset: str, key: str, last_n: int = 3, invert: bool = False
    ) -> Optional[float]:
        """Fetch one series from ECB CSV API, return last observation."""
        url = f'{BASE_URL}/{dataset}/{key}'
        params = {
            'lastNObservations': last_n,
            'format': 'csvdata',
        }

        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
        except Exception:
            return None

        return self._parse_csv(resp.text, invert=invert)

    @staticmethod
    def _parse_csv(text: str, invert: bool = False) -> Optional[float]:
        """Parse ECB CSV response, return most recent OBS_VALUE."""
        reader = csv.DictReader(io.StringIO(text))

        last_time = None
        last_val = None

        for row in reader:
            time_period = row.get('TIME_PERIOD', '')
            obs_value = row.get('OBS_VALUE', '')
            if not obs_value:
                continue
            try:
                val = float(obs_value)
            except (ValueError, TypeError):
                continue

            # Keep the row with the latest TIME_PERIOD
            if last_time is None or time_period >= last_time:
                last_time = time_period
                last_val = val

        if last_val is None:
            return None

        if invert and last_val != 0:
            last_val = round(1.0 / last_val, 4)
        else:
            last_val = round(last_val, 4)

        return last_val


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("ECB Client — Test\n")
    client = ECBClient()
    data = client.fetch_euro_macro()

    if not data:
        print("ERROR: No se obtuvieron series")
        sys.exit(1)

    ok = 0
    for campo, val in sorted(data.items()):
        spec = ECB_SERIES.get(campo, {})
        desc = spec.get('description', campo)
        unit = spec.get('unit', '')
        if val is not None:
            print(f"  {campo:20s}: {val:>10.4f} {unit:5s}  ({desc})")
            ok += 1
        else:
            print(f"  {campo:20s}: {'FAIL':>10s}        ({desc})")

    print(f"\nTotal: {ok}/{len(data)} series OK")

# -*- coding: utf-8 -*-
"""
Greybark Research - IMF WEO Client
====================================

Cliente para la API pública del IMF DataMapper (World Economic Outlook).
Obtiene consensus forecasts de GDP e inflación por país.

API: https://www.imf.org/external/datamapper/api/v1/{indicator}/{countries}?periods=2025,2026
Indicadores: NGDP_RPCH (GDP real), PCPIPCH (CPI)
Gratis, sin API key.
"""

import requests
from datetime import datetime
from typing import Dict, Any

BASE_URL = "https://www.imf.org/external/datamapper/api/v1"

# ISO codes usados por IMF DataMapper
COUNTRY_MAP = {
    'usa': 'USA',
    'eurozone': 'EURO',
    'china': 'CHN',
    'chile': 'CHL',
}

INDICATORS = {
    'gdp': 'NGDP_RPCH',
    'inflation': 'PCPIPCH',
}


class IMFWEOClient:
    """Cliente para IMF WEO DataMapper API."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_consensus(self, year: int = 2026) -> Dict[str, Any]:
        """
        Obtiene consensus GDP e inflación del WEO para el año indicado.

        Returns:
            Dict con 'gdp', 'inflation', 'source', 'timestamp'.
            Si falla: {'error': str}.
        """
        try:
            countries = ','.join(COUNTRY_MAP.values())
            periods = f"{year - 1},{year}"
            result = {
                'gdp': {},
                'inflation': {},
                'source': f'IMF WEO {datetime.now().strftime("%B %Y")}',
                'timestamp': datetime.now().isoformat(),
            }

            for category, indicator in INDICATORS.items():
                url = f"{BASE_URL}/{indicator}/{countries}?periods={periods}"
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()

                values = data.get('values', {}).get(indicator, {})
                for local_key, imf_code in COUNTRY_MAP.items():
                    country_data = values.get(imf_code, {})
                    val = country_data.get(str(year))
                    if val is not None:
                        result[category][local_key] = round(float(val), 1)

            return result

        except Exception as e:
            return {'error': str(e)}


if __name__ == "__main__":
    client = IMFWEOClient()
    data = client.fetch_consensus()
    import json
    print(json.dumps(data, indent=2, ensure_ascii=False))

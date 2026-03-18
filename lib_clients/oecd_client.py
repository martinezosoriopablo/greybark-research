# -*- coding: utf-8 -*-
"""
Greybark Research — OECD SDMX API Client
==========================================

OECD Key Economic Indicators (KEI) via SDMX REST API.
Free, no API key required. Rate limited (~10 req/min).

Provides (58 countries incl. CHL, USA, CHN, EA20, G20):
- Composite Leading Indicator (CLI)
- Consumer Confidence Index (CCI)
- Business Confidence Index (BCI)
- Unemployment Rate
- GDP Growth QoQ and YoY
- CPI Inflation YoY
- Short-term interest rates (3-month interbank)
- Long-term interest rates (10Y govt bond)
- Industrial Production YoY

Usage:
    from greybark.data_sources.oecd_client import OECDClient

    oecd = OECDClient()
    cli = oecd.get_cli()
    rates = oecd.get_interest_rates()
    dash = oecd.get_full_dashboard()
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_URL = "https://sdmx.oecd.org/public/rest/data"

# KEI dataflow: OECD.SDD.STES,DSD_KEI@DF_KEI
KEI_FLOW = "OECD.SDD.STES,DSD_KEI@DF_KEI,"

# CLI dedicated dataflow (more adjustments available)
CLI_FLOW = "OECD.SDD.STES,DSD_STES@DF_CLI,"

# Default countries for our pipeline
DEFAULT_COUNTRIES = "CHL+USA+CHN+EA20+DEU+GBR+JPN+BRA+MEX+COL"

# KEI dimension order: REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION
# Series definitions: (measure, unit, activity, adjustment, transformation, frequency)
KEI_SERIES = {
    'cli':           ('LI',     'IX',    '_T', 'AA', '_Z', 'M'),
    'cci':           ('CCICP',  'PB',    '_Z', '_Z', '_Z', 'M'),
    'bci':           ('BCICP',  'PB',    '_Z', '_Z', '_Z', 'M'),
    'unemployment':  ('UNEMP',  'PT_LF', '_T', 'Y',  '_Z', 'M'),
    'gdp_yoy':       ('RS',     'GR',    '_Z', '_Z', 'GY', 'Q'),
    'gdp_qoq':       ('RS',     'GR',    '_Z', '_Z', 'G1', 'Q'),
    'cpi_yoy':       ('CP',     'GR',    '_Z', '_Z', 'GY', 'M'),
    'short_rate':    ('IR3TIB', 'PA',    '_Z', '_Z', '_Z', 'M'),
    'long_rate':     ('IRLT',   'PA',    '_Z', '_Z', '_Z', 'M'),
    'ind_prod_yoy':  ('PRVM',   'GR',    '_T', 'Y',  'GY', 'M'),
}

# Minimum seconds between API calls to avoid 429
RATE_LIMIT_DELAY = 3.0


class OECDClient:
    """Client for OECD SDMX REST API (KEI dataflow)."""

    def __init__(self, countries: str = None):
        self.countries = countries or DEFAULT_COUNTRIES
        self._last_call = 0.0

    def _rate_limit(self):
        """Enforce minimum delay between API calls."""
        elapsed = time.time() - self._last_call
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call = time.time()

    def _fetch_kei(
        self,
        series_key: str,
        start_period: str = None,
        countries: str = None,
    ) -> List[Dict]:
        """Fetch a KEI series from the OECD SDMX API.

        Args:
            series_key: Key from KEI_SERIES dict (e.g. 'cli', 'unemployment')
            start_period: Start period (e.g. '2025-01', '2024-Q1')
            countries: Override country list (e.g. 'CHL+USA')

        Returns:
            List of {country, value, period} dicts.
        """
        if series_key not in KEI_SERIES:
            logger.error(f"Unknown OECD series: {series_key}")
            return []

        measure, unit, activity, adj, trans, freq = KEI_SERIES[series_key]
        ctry = countries or self.countries

        if start_period is None:
            if freq == 'Q':
                # Last 10 years for quarterly (full business cycle)
                y = datetime.now().year - 10
                start_period = f"{y}-Q1"
            else:
                # Last 10 years for monthly
                y = datetime.now().year - 10
                m = datetime.now().month
                start_period = f"{y}-{m:02d}"

        # Build key: REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION
        key = f"{ctry}.{freq}.{measure}.{unit}.{activity}.{adj}.{trans}"
        url = f"{BASE_URL}/{KEI_FLOW}/{key}?startPeriod={start_period}"

        self._rate_limit()

        try:
            resp = requests.get(
                url,
                headers={'Accept': 'application/vnd.sdmx.data+json'},
                timeout=30,
            )
            if resp.status_code == 429:
                logger.warning("OECD rate limited, waiting 10s...")
                time.sleep(10)
                resp = requests.get(
                    url,
                    headers={'Accept': 'application/vnd.sdmx.data+json'},
                    timeout=30,
                )

            if resp.status_code != 200:
                logger.error(f"OECD API error {resp.status_code} for {series_key}")
                return []

            return self._parse_response(resp.json())

        except Exception as e:
            logger.error(f"OECD API error for {series_key}: {e}")
            return []

    def _parse_response(self, data: Dict) -> List[Dict]:
        """Parse SDMX-JSON response into flat list of ALL observations."""
        results = []
        try:
            ds = data['data']['dataSets'][0]
            structs = data['data']['structures'][0]
            sdims = structs['dimensions']['series']
            odims = structs['dimensions']['observation']
            time_values = odims[0]['values']

            for sk, sv in ds.get('series', {}).items():
                parts = sk.split(':')
                country = sdims[0]['values'][int(parts[0])]['id']

                obs = sv.get('observations', {})
                if not obs:
                    continue

                # Extract ALL observations, sorted by time index
                for obs_idx in sorted(obs.keys(), key=int):
                    tidx = int(obs_idx)
                    val = obs[obs_idx][0]
                    period = time_values[tidx]['id'] if tidx < len(time_values) else None

                    results.append({
                        'country': country,
                        'value': val,
                        'period': period,
                    })
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"OECD parse error: {e}")

        return results

    def _to_country_dict(self, observations: List[Dict]) -> Dict[str, Any]:
        """Convert list of observations to {country: {latest, history}} dict.

        Returns:
            {country: {value, period, history: [{period, value}, ...]}} dict
            History is sorted chronologically (oldest first).
        """
        # Group by country
        by_country: Dict[str, List[Dict]] = {}
        for obs in observations:
            c = obs['country']
            if c not in by_country:
                by_country[c] = []
            by_country[c].append({'period': obs['period'], 'value': obs['value']})

        result = {}
        for country, series in by_country.items():
            # Sort chronologically
            series.sort(key=lambda x: x['period'] or '')
            latest = series[-1]
            result[country] = {
                'value': latest['value'],
                'period': latest['period'],
                'history': series,
            }
        return result

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def get_cli(self) -> Dict[str, Dict]:
        """Composite Leading Indicator (amplitude adjusted, monthly).

        Note: CLI not available for CHL. Available for ~35 OECD countries.
        >100 = expanding, <100 = contracting.

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('cli')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:LI'
        return result

    def get_consumer_confidence(self) -> Dict[str, Dict]:
        """Consumer Confidence Index (monthly, percentage balance).

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('cci')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:CCICP'
        return result

    def get_business_confidence(self) -> Dict[str, Dict]:
        """Business Confidence Index (monthly, percentage balance).

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('bci')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:BCICP'
        return result

    def get_unemployment(self) -> Dict[str, Dict]:
        """Unemployment Rate (monthly, % of labour force, seasonally adj).

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('unemployment')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:UNEMP'
        return result

    def get_gdp_growth(self) -> Dict[str, Any]:
        """GDP Growth QoQ and YoY (quarterly, %).

        Returns:
            {country: {qoq, yoy, period, qoq_history, yoy_history}} dict
        """
        qoq_obs = self._fetch_kei('gdp_qoq')
        yoy_obs = self._fetch_kei('gdp_yoy')

        qoq_dict = self._to_country_dict(qoq_obs)
        yoy_dict = self._to_country_dict(yoy_obs)

        result = {}
        all_countries = set(list(qoq_dict.keys()) + list(yoy_dict.keys())) - {'_source'}
        for c in all_countries:
            entry = {'qoq': None, 'yoy': None, 'period': None,
                     'qoq_history': [], 'yoy_history': []}
            if c in qoq_dict:
                entry['qoq'] = qoq_dict[c]['value']
                entry['period'] = qoq_dict[c]['period']
                entry['qoq_history'] = qoq_dict[c].get('history', [])
            if c in yoy_dict:
                entry['yoy'] = yoy_dict[c]['value']
                if not entry['period']:
                    entry['period'] = yoy_dict[c]['period']
                entry['yoy_history'] = yoy_dict[c].get('history', [])
            result[c] = entry

        result['_source'] = 'OECD:KEI:RS'
        return result

    def get_cpi_inflation(self) -> Dict[str, Dict]:
        """CPI Inflation YoY (monthly, growth rate %).

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('cpi_yoy')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:CP'
        return result

    def get_interest_rates(self) -> Dict[str, Any]:
        """Short-term (3M interbank) and long-term (10Y bond) interest rates.

        Returns:
            {country: {short_rate, long_rate, spread, period,
                       short_history, long_history}} dict
        """
        short_obs = self._fetch_kei('short_rate')
        long_obs = self._fetch_kei('long_rate')

        short_dict = self._to_country_dict(short_obs)
        long_dict = self._to_country_dict(long_obs)

        result = {}
        all_countries = set(list(short_dict.keys()) + list(long_dict.keys())) - {'_source'}
        for c in all_countries:
            entry = {'short_rate': None, 'long_rate': None, 'spread': None,
                     'period': None, 'short_history': [], 'long_history': []}
            if c in short_dict:
                entry['short_rate'] = round(short_dict[c]['value'], 2)
                entry['period'] = short_dict[c]['period']
                entry['short_history'] = short_dict[c].get('history', [])
            if c in long_dict:
                entry['long_rate'] = round(long_dict[c]['value'], 2)
                if not entry['period']:
                    entry['period'] = long_dict[c]['period']
                entry['long_history'] = long_dict[c].get('history', [])
            if entry['short_rate'] is not None and entry['long_rate'] is not None:
                entry['spread'] = round(entry['long_rate'] - entry['short_rate'], 2)
            result[c] = entry

        result['_source'] = 'OECD:KEI:IR3TIB+IRLT'
        return result

    def get_industrial_production(self) -> Dict[str, Dict]:
        """Industrial Production YoY (monthly, growth rate %, seasonally adj).

        Returns:
            {country: {value, period}} dict
        """
        obs = self._fetch_kei('ind_prod_yoy')
        result = self._to_country_dict(obs)
        result['_source'] = 'OECD:KEI:PRVM'
        return result

    def get_full_dashboard(self) -> Dict[str, Any]:
        """Fetch all OECD data in one call (10 API calls, ~30s with rate limiting).

        Returns:
            Dict with all sections.
        """
        return {
            'cli': self.get_cli(),
            'cci': self.get_consumer_confidence(),
            'bci': self.get_business_confidence(),
            'unemployment': self.get_unemployment(),
            'gdp_growth': self.get_gdp_growth(),
            'cpi_inflation': self.get_cpi_inflation(),
            'interest_rates': self.get_interest_rates(),
            'industrial_production': self.get_industrial_production(),
        }

    def get_country_snapshot(self, country: str = 'CHL') -> Dict[str, Any]:
        """Get all available indicators for a single country.

        Args:
            country: ISO 3-letter code (e.g. 'CHL', 'USA')

        Returns:
            Dict with all indicators for that country.
        """
        dashboard = self.get_full_dashboard()
        snapshot = {}
        for key, data in dashboard.items():
            if isinstance(data, dict) and country in data:
                snapshot[key] = data[country]
        snapshot['_country'] = country
        snapshot['_source'] = 'OECD:KEI'
        return snapshot


def main():
    """Test OECD client."""
    client = OECDClient(countries='CHL+USA+CHN+EA20')

    print("=== CLI ===")
    cli = client.get_cli()
    for c, v in cli.items():
        if c != '_source':
            print(f"  {c}: {v}")

    print("\n=== Interest Rates ===")
    rates = client.get_interest_rates()
    for c, v in rates.items():
        if c != '_source':
            print(f"  {c}: short={v.get('short_rate')}, long={v.get('long_rate')}, spread={v.get('spread')}")

    print("\n=== Unemployment ===")
    unemp = client.get_unemployment()
    for c, v in unemp.items():
        if c != '_source':
            print(f"  {c}: {v}")

    print("\n=== Chile Snapshot ===")
    snap = client.get_country_snapshot('CHL')
    for k, v in snap.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

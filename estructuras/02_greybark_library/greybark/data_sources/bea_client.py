# -*- coding: utf-8 -*-
"""
Greybark Research — BEA API Client
====================================

Bureau of Economic Analysis (U.S. Department of Commerce)
https://apps.bea.gov/api/

Provides:
- Real GDP QoQ with components (PCE, investment, govt, trade)
- PCE Price Index monthly (headline, goods, services, durable, nondurable)
- PCE inflation % change MoM
- Personal income, disposable income, saving rate (monthly)
- Corporate profits by sector (quarterly)
- Federal government receipts & expenditures (quarterly)

Usage:
    from greybark.data_sources.bea_client import BEAClient

    bea = BEAClient()
    gdp = bea.get_gdp_components()
    pce = bea.get_pce_inflation()
    profits = bea.get_corporate_profits()
"""

import os
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

BASE_URL = "https://apps.bea.gov/api/data/"

# Key NIPA tables
TABLES = {
    'gdp_real':          'T10101',   # Real GDP % change QoQ (SAAR)
    'gdp_deflator':      'T10104',   # GDP Price Indexes
    'pce_price_index':   'T20804',   # PCE Price Indexes, Monthly
    'pce_pct_change':    'T20807',   # PCE Price % Change MoM
    'personal_income':   'T20600',   # Personal Income and Disposition, Monthly
    'corporate_profits': 'T61600D',  # Corporate Profits by Industry, Quarterly
    'govt_federal':      'T30200',   # Federal Govt Receipts & Expenditures, Quarterly
    'saving_investment': 'T50100',   # Saving and Investment by Sector, Quarterly
}

# Line numbers for key series within each table
LINE_MAP = {
    'gdp_real': {
        1: 'gdp_total',
        2: 'pce_total',
        3: 'pce_goods',
        5: 'pce_services',
        7: 'gross_private_investment',
        8: 'fixed_investment',
        13: 'residential',
        19: 'govt_total',
        20: 'federal',
        24: 'state_local',
        26: 'net_exports',
        27: 'exports',
        30: 'imports',
    },
    'pce_price_index': {
        1: 'pce_headline',
        2: 'pce_goods',
        3: 'pce_durable',
        4: 'pce_nondurable',
        5: 'pce_services',
    },
    'pce_pct_change': {
        1: 'pce_headline_mom',
        2: 'pce_goods_mom',
        5: 'pce_services_mom',
    },
    'personal_income': {
        1: 'personal_income',
        27: 'disposable_income',
        29: 'pce_expenditures',
        34: 'personal_saving',
    },
    'corporate_profits': {
        1: 'profits_total',
        2: 'profits_domestic',
        3: 'profits_financial',
        4: 'profits_nonfinancial',
    },
    'govt_federal': {
        1: 'federal_receipts',
        24: 'federal_expenditures',
        43: 'federal_total_expenditures',
        49: 'federal_net_lending',
    },
}


class BEAClient:
    """Client for BEA REST API (NIPA tables)."""

    def __init__(self, api_key: str = None):
        if api_key:
            self.api_key = api_key
        else:
            try:
                from ..config import config
                self.api_key = config.bea.api_key
            except Exception:
                self.api_key = os.environ.get('BEA_API_KEY', '')
        if not self.api_key:
            logger.warning("BEA_API_KEY not set")

    def _fetch_table(
        self,
        table_name: str,
        frequency: str = 'Q',
        years: str = None,
    ) -> List[Dict]:
        """Fetch a NIPA table from BEA API.

        Args:
            table_name: NIPA table ID (e.g. 'T10101')
            frequency: 'A' (annual), 'Q' (quarterly), 'M' (monthly)
            years: Comma-separated years or 'LAST5', 'ALL'. Default: last 3 years.

        Returns:
            List of data row dicts from BEA API.
        """
        if not self.api_key:
            logger.error("BEA API key not configured")
            return []

        if years is None:
            current_year = datetime.now().year
            years = ','.join(str(y) for y in range(current_year - 10, current_year + 1))

        params = {
            'UserID': self.api_key,
            'method': 'GetData',
            'DatasetName': 'NIPA',
            'TableName': table_name,
            'Frequency': frequency,
            'Year': years,
            'ResultFormat': 'JSON',
        }

        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get('BEAAPI', {}).get('Results', {}).get('Data', [])
        except Exception as e:
            logger.error(f"BEA API error for {table_name}: {e}")
            return []

    def _extract_latest(
        self,
        rows: List[Dict],
        line_map: Dict[int, str],
    ) -> Dict[str, Optional[float]]:
        """Extract the latest value for each mapped line number.

        Args:
            rows: Raw API data rows.
            line_map: {line_number: field_name} mapping.

        Returns:
            Dict with field_name → latest value.
        """
        result = {name: None for name in line_map.values()}

        # Group by line number, find latest period
        by_line = {}
        for row in rows:
            try:
                ln = int(row.get('LineNumber', 0))
            except (ValueError, TypeError):
                continue
            if ln in line_map:
                period = row.get('TimePeriod', '')
                val_str = row.get('DataValue', '').replace(',', '')
                try:
                    val = float(val_str)
                except (ValueError, TypeError):
                    continue
                name = line_map[ln]
                if name not in by_line or period > by_line[name][0]:
                    by_line[name] = (period, val)

        for name, (period, val) in by_line.items():
            result[name] = val

        return result

    def _extract_latest_with_period(
        self,
        rows: List[Dict],
        line_map: Dict[int, str],
    ) -> Dict[str, Dict]:
        """Like _extract_latest but also returns the period string."""
        result = {name: {'value': None, 'period': None} for name in line_map.values()}

        by_line = {}
        for row in rows:
            try:
                ln = int(row.get('LineNumber', 0))
            except (ValueError, TypeError):
                continue
            if ln in line_map:
                period = row.get('TimePeriod', '')
                val_str = row.get('DataValue', '').replace(',', '')
                try:
                    val = float(val_str)
                except (ValueError, TypeError):
                    continue
                name = line_map[ln]
                if name not in by_line or period > by_line[name][0]:
                    by_line[name] = (period, val)

        for name, (period, val) in by_line.items():
            result[name] = {'value': val, 'period': period}

        return result

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def get_gdp_components(self) -> Dict[str, Optional[float]]:
        """Real GDP QoQ % change with components.

        Returns dict with keys:
            gdp_total, pce_total, pce_goods, pce_services,
            gross_private_investment, fixed_investment, residential,
            govt_total, federal, state_local,
            net_exports, exports, imports
        """
        rows = self._fetch_table(TABLES['gdp_real'], frequency='Q')
        result = self._extract_latest(rows, LINE_MAP['gdp_real'])
        result['_source'] = 'BEA:NIPA:T10101'
        return result

    def get_pce_inflation(self) -> Dict[str, Optional[float]]:
        """PCE Price Index levels (monthly) + MoM % change.

        Returns dict with keys:
            pce_headline, pce_goods, pce_durable, pce_nondurable, pce_services (index levels)
            pce_headline_mom, pce_goods_mom, pce_services_mom (% change MoM)
        """
        # Price index levels
        rows_idx = self._fetch_table(TABLES['pce_price_index'], frequency='M')
        levels = self._extract_latest(rows_idx, LINE_MAP['pce_price_index'])

        # MoM % change
        rows_chg = self._fetch_table(TABLES['pce_pct_change'], frequency='M')
        changes = self._extract_latest(rows_chg, LINE_MAP['pce_pct_change'])

        # Compute YoY from index (current vs 12 months ago)
        yoy = self._compute_pce_yoy(rows_idx)

        result = {**levels, **changes, **yoy}
        result['_source'] = 'BEA:NIPA:T20804+T20807'
        return result

    def _compute_pce_yoy(self, rows: List[Dict]) -> Dict[str, Optional[float]]:
        """Compute PCE YoY % from price index levels."""
        result = {
            'pce_headline_yoy': None,
            'pce_goods_yoy': None,
            'pce_services_yoy': None,
        }

        line_to_yoy = {1: 'pce_headline_yoy', 2: 'pce_goods_yoy', 5: 'pce_services_yoy'}

        for ln, name in line_to_yoy.items():
            # Get all values for this line sorted by period
            vals = []
            for row in rows:
                try:
                    row_ln = int(row.get('LineNumber', 0))
                except (ValueError, TypeError):
                    continue
                if row_ln != ln:
                    continue
                period = row.get('TimePeriod', '')
                val_str = row.get('DataValue', '').replace(',', '')
                try:
                    val = float(val_str)
                    vals.append((period, val))
                except (ValueError, TypeError):
                    continue

            vals.sort(key=lambda x: x[0])
            if len(vals) >= 13:
                current = vals[-1][1]
                year_ago = vals[-13][1]
                if year_ago > 0:
                    result[name] = round((current / year_ago - 1) * 100, 2)

        return result

    def get_personal_income(self) -> Dict[str, Optional[float]]:
        """Personal income, disposable income, PCE, saving (monthly, billions SAAR).

        Returns dict with keys:
            personal_income, disposable_income, pce_expenditures, personal_saving
            saving_rate (computed as saving / disposable_income * 100)
        """
        rows = self._fetch_table(TABLES['personal_income'], frequency='M')
        result = self._extract_latest(rows, LINE_MAP['personal_income'])

        # Compute saving rate
        saving = result.get('personal_saving')
        disp = result.get('disposable_income')
        if saving is not None and disp and disp > 0:
            result['saving_rate'] = round(saving / disp * 100, 1)
        else:
            result['saving_rate'] = None

        result['_source'] = 'BEA:NIPA:T20600'
        return result

    def get_corporate_profits(self) -> Dict[str, Optional[float]]:
        """Corporate profits with IVA + CCAdj by sector (quarterly, billions SAAR).

        Returns dict with keys:
            profits_total, profits_domestic, profits_financial, profits_nonfinancial
            profits_yoy (total YoY % change, computed)
        """
        current_year = datetime.now().year
        years = ','.join(str(y) for y in range(current_year - 10, current_year + 1))
        rows = self._fetch_table(TABLES['corporate_profits'], frequency='Q', years=years)
        result = self._extract_latest_with_period(rows, LINE_MAP['corporate_profits'])

        # Flatten to just values
        flat = {}
        for name, info in result.items():
            flat[name] = info['value']

        # Compute YoY for total profits
        total_vals = []
        for row in rows:
            try:
                ln = int(row.get('LineNumber', 0))
            except (ValueError, TypeError):
                continue
            if ln != 1:
                continue
            period = row.get('TimePeriod', '')
            val_str = row.get('DataValue', '').replace(',', '')
            try:
                val = float(val_str)
                total_vals.append((period, val))
            except (ValueError, TypeError):
                continue

        total_vals.sort(key=lambda x: x[0])
        if len(total_vals) >= 5:
            current = total_vals[-1][1]
            year_ago = total_vals[-5][1]  # 4 quarters back
            if year_ago > 0:
                flat['profits_yoy'] = round((current / year_ago - 1) * 100, 1)
            else:
                flat['profits_yoy'] = None
        else:
            flat['profits_yoy'] = None

        flat['_source'] = 'BEA:NIPA:T61600D'
        return flat

    def get_federal_fiscal(self) -> Dict[str, Optional[float]]:
        """Federal government receipts and expenditures (quarterly, billions SAAR).

        Returns dict with keys:
            federal_receipts, federal_expenditures, federal_deficit (computed)
        """
        rows = self._fetch_table(TABLES['govt_federal'], frequency='Q')
        result = self._extract_latest(rows, LINE_MAP['govt_federal'])

        # federal_net_lending is already deficit (negative = deficit)
        # Also compute from receipts - current expenditures
        receipts = result.get('federal_receipts')
        expenditures = result.get('federal_expenditures')
        if receipts is not None and expenditures is not None:
            result['federal_current_deficit'] = round(receipts - expenditures, 1)
        else:
            result['federal_current_deficit'] = None

        result['_source'] = 'BEA:NIPA:T30200'
        return result

    def get_gdp_deflator(self) -> Dict[str, Optional[float]]:
        """GDP Price Index (quarterly).

        Returns dict with key:
            gdp_deflator (index level, latest quarter)
        """
        rows = self._fetch_table(TABLES['gdp_deflator'], frequency='Q')
        # Line 1 is GDP price index
        result = self._extract_latest(rows, {1: 'gdp_deflator'})
        result['_source'] = 'BEA:NIPA:T10104'
        return result

    def get_full_dashboard(self) -> Dict[str, Any]:
        """Fetch all BEA data in one call.

        Returns dict with all sections:
            gdp, pce_inflation, personal_income, corporate_profits, fiscal, gdp_deflator
        """
        return {
            'gdp': self.get_gdp_components(),
            'pce_inflation': self.get_pce_inflation(),
            'personal_income': self.get_personal_income(),
            'corporate_profits': self.get_corporate_profits(),
            'fiscal': self.get_federal_fiscal(),
            'gdp_deflator': self.get_gdp_deflator(),
        }


def main():
    """Test BEA client."""
    import json
    client = BEAClient()

    print("=== GDP Components ===")
    gdp = client.get_gdp_components()
    for k, v in gdp.items():
        print(f"  {k}: {v}")

    print("\n=== PCE Inflation ===")
    pce = client.get_pce_inflation()
    for k, v in pce.items():
        print(f"  {k}: {v}")

    print("\n=== Personal Income ===")
    inc = client.get_personal_income()
    for k, v in inc.items():
        print(f"  {k}: {v}")

    print("\n=== Corporate Profits ===")
    prof = client.get_corporate_profits()
    for k, v in prof.items():
        print(f"  {k}: {v}")

    print("\n=== Federal Fiscal ===")
    fisc = client.get_federal_fiscal()
    for k, v in fisc.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

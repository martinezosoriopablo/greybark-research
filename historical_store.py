# -*- coding: utf-8 -*-
"""
Greybark Research — Historical Data Store
===========================================

Saves key metrics from each pipeline run and provides previous-period
values for "anterior" columns in reports.

Usage:
    from historical_store import HistoricalStore

    store = HistoricalStore()

    # After data collection, save snapshot
    store.save_snapshot(quant_data, forecast_data)

    # Before rendering, get previous values
    prev = store.get_previous()
    # prev = {'gdp_us': 2.5, 'cpi_core': 2.8, 'tpm': 4.5, ...} or {} if first run
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


STORE_DIR = Path(__file__).parent / "output" / "historical"


def _safe_float(val, default=None):
    """Extract float from value, dict, or nested structure."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        for key in ('value', 'current', 'rate'):
            if key in val and val[key] is not None:
                try:
                    return float(val[key])
                except (ValueError, TypeError):
                    pass
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class HistoricalStore:
    """Manages historical snapshots of key metrics between pipeline runs."""

    # Metrics to extract from quant_data and their paths
    METRIC_PATHS = {
        # USA Macro
        'gdp_us': [('macro_usa', 'gdp')],
        'gdp_us_qoq': [('macro_usa', 'gdp', 'qoq_change')],
        'cpi_headline': [('inflation', 'cpi_all_yoy')],
        'cpi_core': [('inflation', 'cpi_core_yoy')],
        'cpi_services': [('inflation', 'cpi_services_yoy')],
        'pce_core': [('macro_usa', 'pce_core_yoy'), ('inflation', 'pce_core_yoy')],
        'nfp': [('macro_usa', 'payrolls')],
        'unemployment': [('macro_usa', 'unemployment')],
        'retail_sales_yoy': [('macro_usa', 'retail_sales', 'yoy')],
        'initial_claims': [('macro_usa', 'initial_claims'), ('leading_indicators', 'initial_claims')],
        'ism_mfg': [('leading_indicators', 'ism_manufacturing')],
        'ism_services': [('leading_indicators', 'ism_services')],

        # Rates & Yields
        'fed_funds': [('rates', 'fed_funds', 'current'), ('chile_rates', 'fed_funds')],
        'ust_2y': [('yield_curve', 'current_curve', '2Y'), ('chile_rates', 'ust_2y')],
        'ust_10y': [('yield_curve', 'current_curve', '10Y'), ('chile_rates', 'ust_10y')],
        'ig_spread': [('credit_spreads', 'ig_breakdown', 'total', 'current_bps')],
        'hy_spread': [('credit_spreads', 'hy_breakdown', 'total', 'current_bps')],

        # Chile
        'tpm': [('chile', 'tpm'), ('chile_rates', 'tpm')],
        'ipc_chile': [('chile', 'ipc_yoy')],
        'usdclp': [('chile', 'usd_clp'), ('equity', 'bcch_indices', 'usd_clp', 'value')],

        # Commodities
        'copper': [('equity', 'bcch_indices', 'copper', 'value')],
        'gold': [('equity', 'bcch_indices', 'gold', 'value')],
        'oil_wti': [('equity', 'bcch_indices', 'oil_wti', 'value')],

        # Risk
        'vix': [('risk', 'vix')],

        # Breakevens
        'breakeven_5y': [('inflation', 'breakeven_5y'), ('inflation', 'breakeven_inflation', 'current', 'breakeven_5y')],
        'breakeven_10y': [('inflation', 'breakeven_10y')],

        # Europe
        'gdp_eurozone': [('europe', 'gdp_qoq'), ('international', 'eurozone', 'gdp')],

        # China
        'gdp_china': [('china', 'gdp_yoy'), ('international', 'china', 'gdp')],

        # EM
        'selic': [('chile_rates', 'policy_rates', 'bcb')],
    }

    def __init__(self, store_dir: Path = None):
        self.store_dir = store_dir or STORE_DIR
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _extract_value(self, data: Dict, paths: list) -> Optional[float]:
        """Try multiple paths to extract a float value from nested data."""
        for path in paths:
            d = data
            for key in path:
                if not isinstance(d, dict) or key not in d:
                    d = None
                    break
                d = d[key]
            val = _safe_float(d)
            if val is not None:
                return val
        return None

    def save_snapshot(self, quant_data: Dict, forecast_data: Dict = None):
        """Save current metrics as a historical snapshot."""
        snapshot = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
        }

        # Merge quant + forecast for extraction
        combined = dict(quant_data) if quant_data else {}
        if forecast_data and isinstance(forecast_data, dict):
            combined['forecast'] = forecast_data

        for metric_id, paths in self.METRIC_PATHS.items():
            val = self._extract_value(combined, paths)
            if val is not None:
                snapshot['metrics'][metric_id] = round(val, 4)

        # Save with date stamp
        date_str = datetime.now().strftime('%Y%m%d')
        filepath = self.store_dir / f"snapshot_{date_str}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        n = len(snapshot['metrics'])
        print(f"  [OK] Historical snapshot: {n} metrics saved to {filepath.name}")
        return filepath

    def get_previous(self) -> Dict[str, float]:
        """Load the most recent PREVIOUS snapshot (not today's).

        Returns dict of metric_id → float value, or empty dict if no history.
        """
        files = sorted(self.store_dir.glob("snapshot_*.json"), reverse=True)

        today = datetime.now().strftime('%Y%m%d')
        for f in files:
            # Skip today's snapshot — we want the PREVIOUS run
            if today in f.name:
                continue
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                metrics = data.get('metrics', {})
                if metrics:
                    print(f"  [OK] Historical prev: {len(metrics)} metrics from {f.name}")
                    return metrics
            except (json.JSONDecodeError, KeyError):
                continue

        print("  [INFO] Historical prev: no previous snapshot found (first run)")
        return {}

    def get_direction(self, metric_id: str, current: float, prev: Dict) -> str:
        """Calculate direction arrow from current vs previous."""
        prev_val = prev.get(metric_id)
        if prev_val is None or current is None:
            return ''
        diff = current - prev_val
        if abs(diff) < 0.001:
            return '→'
        return '↑' if diff > 0 else '↓'

    def inject_prev_into_data(self, quant_data: Dict, prev: Dict) -> Dict:
        """Inject previous-period values into quant_data dicts.

        Content generators look for keys like 'cpi_core_yoy_prev', 'gdp_prev', etc.
        This method adds those keys from the historical snapshot so "anterior"
        columns fill automatically without modifying content generators.
        """
        if not prev or not quant_data:
            return quant_data

        # Map: historical metric_id → (quant_data path, prev key name)
        INJECT_MAP = {
            'cpi_headline': ('inflation', 'cpi_headline_yoy_prev'),
            'cpi_core': ('inflation', 'cpi_core_yoy_prev'),
            'pce_core': ('inflation', 'pce_core_yoy_prev'),
            'cpi_services': ('inflation', 'cpi_services_yoy_prev'),
            'gdp_us': ('macro_usa', 'gdp_prev'),
            'retail_sales_yoy': ('macro_usa', 'retail_sales_prev'),
            'unemployment': ('macro_usa', 'unemployment_prev'),
            'nfp': ('macro_usa', 'nfp_prev'),
            'initial_claims': ('macro_usa', 'initial_claims_prev'),
            'ism_mfg': ('leading_indicators', 'ism_manufacturing_prev'),
            'ism_services': ('leading_indicators', 'ism_services_prev'),
            'vix': ('risk', 'vix_prev'),
            'tpm': ('chile', 'tpm_prev'),
            'ipc_chile': ('chile', 'ipc_yoy_prev'),
            'usdclp': ('chile', 'usd_clp_prev'),
            'copper': ('chile', 'copper_prev'),
            'gdp_eurozone': ('europe', 'gdp_qoq_prev'),
            'gdp_china': ('china', 'gdp_yoy_prev'),
            'fed_funds': ('rates', 'fed_funds_prev'),
            'ust_10y': ('yield_curve', 'ust_10y_prev'),
            'ig_spread': ('credit_spreads', 'ig_spread_prev'),
            'hy_spread': ('credit_spreads', 'hy_spread_prev'),
            'breakeven_5y': ('inflation', 'breakeven_5y_prev'),
            'selic': ('chile_rates', 'selic_prev'),
        }

        injected = 0
        for metric_id, (target_dict, prev_key) in INJECT_MAP.items():
            val = prev.get(metric_id)
            if val is None:
                continue
            # Ensure target dict exists
            if target_dict not in quant_data:
                quant_data[target_dict] = {}
            if isinstance(quant_data[target_dict], dict):
                if prev_key not in quant_data[target_dict]:
                    quant_data[target_dict][prev_key] = val
                    injected += 1

        if injected:
            print(f"  [OK] Historical: {injected} prev values injected into quant_data")
        return quant_data

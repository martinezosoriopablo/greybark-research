"""
Greybark Research - Macro Dashboard Consolidado
Consolida datos macro de US, Chile y China

Integra:
- US Macro (FRED): GDP, Unemployment, Payrolls, Retail Sales, etc.
- Inflation Analytics: Breakeven, Real Rates, CPI decomposition
- Chile Analytics: TPM, IPC, IMACEC, USD/CLP, curves
- China Credit: EPU, commodity demand proxies, ETFs

Author: Greybark Research
Date: February 2026
"""

from datetime import datetime
from typing import Dict, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import data source
try:
    from data_sources.fred_client import FREDClient
except ImportError:
    from greybark.data_sources.fred_client import FREDClient

# Import analytics modules
try:
    from analytics.macro.inflation_analytics import InflationAnalytics
    from analytics.chile.chile_analytics import ChileAnalytics
    from analytics.china.china_credit import ChinaCreditAnalytics
except ImportError:
    try:
        from greybark.analytics.macro.inflation_analytics import InflationAnalytics
        from greybark.analytics.chile.chile_analytics import ChileAnalytics
        from greybark.analytics.china.china_credit import ChinaCreditAnalytics
    except ImportError:
        # Fallback - modules may not all be available
        InflationAnalytics = None
        ChileAnalytics = None
        ChinaCreditAnalytics = None


class MacroDashboard:
    """
    Consolidated Macro Dashboard

    Combines US, Chile, and China macro analytics into a single view.

    Usage:
        dashboard = MacroDashboard()

        # Get full dashboard
        data = dashboard.get_full_macro_dashboard()

        # Get specific regions
        us_data = dashboard.get_us_macro()
        chile_data = dashboard.get_chile_macro()
        china_data = dashboard.get_china_macro()
    """

    def __init__(self,
                 fred_api_key: str = None,
                 bcch_user: str = None,
                 bcch_password: str = None):
        """
        Initialize with API credentials

        Args:
            fred_api_key: FRED API key (default from config)
            bcch_user: BCCh API user
            bcch_password: BCCh API password
        """
        self.fred_api_key = fred_api_key
        self.bcch_user = bcch_user
        self.bcch_password = bcch_password

        # Initialize clients lazily
        self._fred = None
        self._inflation = None
        self._chile = None
        self._china = None

    @property
    def fred(self) -> FREDClient:
        """Lazy initialization of FRED client"""
        if self._fred is None:
            self._fred = FREDClient(api_key=self.fred_api_key)
        return self._fred

    @property
    def inflation(self) -> Optional[Any]:
        """Lazy initialization of Inflation Analytics"""
        if self._inflation is None and InflationAnalytics is not None:
            try:
                self._inflation = InflationAnalytics(api_key=self.fred_api_key)
            except Exception as e:
                print(f"[MacroDashboard] Could not init InflationAnalytics: {e}")
        return self._inflation

    @property
    def chile(self) -> Optional[Any]:
        """Lazy initialization of Chile Analytics"""
        if self._chile is None and ChileAnalytics is not None:
            try:
                self._chile = ChileAnalytics(
                    bcch_user=self.bcch_user,
                    bcch_password=self.bcch_password,
                    fred_api_key=self.fred_api_key
                )
            except Exception as e:
                print(f"[MacroDashboard] Could not init ChileAnalytics: {e}")
        return self._chile

    @property
    def china(self) -> Optional[Any]:
        """Lazy initialization of China Analytics"""
        if self._china is None and ChinaCreditAnalytics is not None:
            try:
                self._china = ChinaCreditAnalytics(
                    bcch_user=self.bcch_user,
                    bcch_password=self.bcch_password,
                    fred_api_key=self.fred_api_key
                )
            except Exception as e:
                print(f"[MacroDashboard] Could not init ChinaCreditAnalytics: {e}")
        return self._china

    # =========================================================================
    # INDIVIDUAL REGION METHODS
    # =========================================================================

    def get_us_macro(self) -> Dict[str, Any]:
        """
        Get US macro dashboard from FRED

        Returns:
            Dict with GDP, unemployment, payrolls, retail, industrial, housing, durables
        """
        print("\n" + "=" * 60)
        print("US MACRO DASHBOARD")
        print("=" * 60)

        return self.fred.get_us_macro_dashboard()

    def get_us_inflation(self) -> Dict[str, Any]:
        """
        Get US inflation dashboard

        Returns:
            Dict with breakeven, real rates, CPI decomposition, wage analysis
        """
        print("\n" + "=" * 60)
        print("US INFLATION DASHBOARD")
        print("=" * 60)

        if self.inflation is None:
            return {'error': 'InflationAnalytics not available'}

        try:
            return self.inflation.get_inflation_dashboard()
        except Exception as e:
            return {'error': str(e)}

    def get_chile_macro(self) -> Dict[str, Any]:
        """
        Get Chile macro dashboard

        Returns:
            Dict with TPM, IPC, IMACEC, USD/CLP, swap curve, breakeven
        """
        print("\n" + "=" * 60)
        print("CHILE MACRO DASHBOARD")
        print("=" * 60)

        if self.chile is None:
            return {'error': 'ChileAnalytics not available'}

        try:
            return self.chile.get_chile_dashboard()
        except Exception as e:
            return {'error': str(e)}

    def get_china_macro(self) -> Dict[str, Any]:
        """
        Get China macro/credit dashboard

        Returns:
            Dict with EPU, commodity demand, trade, credit impulse proxy
        """
        print("\n" + "=" * 60)
        print("CHINA MACRO DASHBOARD")
        print("=" * 60)

        if self.china is None:
            return {'error': 'ChinaCreditAnalytics not available'}

        try:
            return self.china.get_china_dashboard()
        except Exception as e:
            return {'error': str(e)}

    # =========================================================================
    # CONSOLIDATED DASHBOARD
    # =========================================================================

    def get_full_macro_dashboard(self,
                                  include_us: bool = True,
                                  include_inflation: bool = True,
                                  include_chile: bool = True,
                                  include_china: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive macro dashboard across all regions

        Args:
            include_us: Include US macro data (GDP, unemployment, etc.)
            include_inflation: Include US inflation analysis
            include_chile: Include Chile macro data
            include_china: Include China credit/macro data

        Returns:
            Dict with all requested macro data and summary
        """
        print("\n" + "=" * 70)
        print("GREY BARK - CONSOLIDATED MACRO DASHBOARD")
        print("=" * 70)

        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'regions': {}
        }

        # US Macro
        if include_us:
            try:
                dashboard['regions']['us_macro'] = self.get_us_macro()
            except Exception as e:
                dashboard['regions']['us_macro'] = {'error': str(e)}

        # US Inflation
        if include_inflation:
            try:
                dashboard['regions']['us_inflation'] = self.get_us_inflation()
            except Exception as e:
                dashboard['regions']['us_inflation'] = {'error': str(e)}

        # Chile
        if include_chile:
            try:
                dashboard['regions']['chile'] = self.get_chile_macro()
            except Exception as e:
                dashboard['regions']['chile'] = {'error': str(e)}

        # China
        if include_china:
            try:
                dashboard['regions']['china'] = self.get_china_macro()
            except Exception as e:
                dashboard['regions']['china'] = {'error': str(e)}

        # Generate summary
        dashboard['summary'] = self._generate_summary(dashboard)

        return dashboard

    def _generate_summary(self, dashboard: Dict) -> Dict:
        """Generate executive summary from all regions"""
        summary = {
            'key_metrics': {},
            'signals': [],
            'cross_region_themes': []
        }

        regions = dashboard.get('regions', {})

        # US Macro summary
        us_macro = regions.get('us_macro', {})
        if not us_macro.get('error'):
            gdp = us_macro.get('gdp', {})
            if gdp:
                summary['key_metrics']['us_gdp'] = gdp.get('value')

            unemp = us_macro.get('unemployment', {})
            if unemp:
                summary['key_metrics']['us_unemployment'] = unemp.get('value')
                if unemp.get('trend') == 'rising':
                    summary['signals'].append("US: Unemployment trending higher - watch labor market")

        # US Inflation summary
        us_inflation = regions.get('us_inflation', {})
        if not us_inflation.get('error'):
            inf_summary = us_inflation.get('summary', {})
            if inf_summary.get('regime'):
                summary['key_metrics']['us_inflation_regime'] = inf_summary['regime']

        # Chile summary
        chile = regions.get('chile', {})
        if not chile.get('error'):
            chile_macro = chile.get('macro', {})
            if chile_macro:
                summary['key_metrics']['chile_tpm'] = chile_macro.get('tpm')
                summary['key_metrics']['chile_ipc'] = chile_macro.get('ipc')

                stance = chile_macro.get('policy_stance')
                if stance:
                    summary['signals'].append(f"Chile: Policy stance is {stance}")

        # China summary
        china = regions.get('china', {})
        if not china.get('error'):
            china_impulse = china.get('credit_impulse', {})
            if china_impulse:
                signal = china_impulse.get('impulse_signal')
                summary['key_metrics']['china_credit_impulse'] = signal

                if signal == 'expansion':
                    summary['signals'].append("China: Credit impulse positive - bullish EM/commodities")
                elif signal == 'contraction':
                    summary['signals'].append("China: Credit impulse negative - cautious EM/commodities")

        # Cross-region themes
        if summary['key_metrics'].get('us_unemployment') and summary['key_metrics'].get('chile_tpm'):
            summary['cross_region_themes'].append(
                "Monitor US-Chile rate differential for carry trade"
            )

        if summary['key_metrics'].get('china_credit_impulse') == 'expansion':
            summary['cross_region_themes'].append(
                "China credit expansion positive for copper/Chile"
            )

        return summary

    # =========================================================================
    # QUICK SUMMARY
    # =========================================================================

    def get_quick_summary(self) -> Dict[str, Any]:
        """
        Get a quick summary of key macro indicators

        Fetches only essential metrics for a fast overview.

        Returns:
            Dict with key metrics only
        """
        print("[MacroDashboard] Fetching quick summary...")

        summary = {
            'timestamp': datetime.now().isoformat(),
            'us': {},
            'chile': {},
            'china': {}
        }

        # US quick metrics
        try:
            us_macro = self.fred.get_us_macro_dashboard()
            summary['us'] = {
                'gdp_qoq': us_macro.get('gdp', {}).get('value'),
                'unemployment': us_macro.get('unemployment', {}).get('value'),
                'payrolls_k': us_macro.get('payrolls', {}).get('value')
            }
        except Exception as e:
            summary['us'] = {'error': str(e)}

        # Chile quick metrics
        if self.chile:
            try:
                chile_macro = self.chile.get_macro_snapshot()
                summary['chile'] = {
                    'tpm': chile_macro.get('tpm'),
                    'ipc_yoy': chile_macro.get('ipc'),
                    'usd_clp': chile_macro.get('usd_clp')
                }
            except Exception as e:
                summary['chile'] = {'error': str(e)}

        # China quick metrics
        if self.china:
            try:
                china_impulse = self.china.get_credit_impulse_proxy()
                summary['china'] = {
                    'credit_impulse': china_impulse.get('impulse_signal')
                }
            except Exception as e:
                summary['china'] = {'error': str(e)}

        return summary


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def get_full_macro_dashboard(fred_api_key: str = None,
                             bcch_user: str = None,
                             bcch_password: str = None) -> Dict[str, Any]:
    """
    Convenience function to get full macro dashboard

    Args:
        fred_api_key: FRED API key
        bcch_user: BCCh API user
        bcch_password: BCCh API password

    Returns:
        Complete macro dashboard with US, Chile, China data
    """
    dashboard = MacroDashboard(
        fred_api_key=fred_api_key,
        bcch_user=bcch_user,
        bcch_password=bcch_password
    )
    return dashboard.get_full_macro_dashboard()


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("GREY BARK - MACRO DASHBOARD TEST")
    print("=" * 70)

    # Test initialization
    dashboard = MacroDashboard()

    print("\n--- Available Methods ---")
    print("  • get_us_macro() - US macro indicators from FRED")
    print("  • get_us_inflation() - US inflation analytics")
    print("  • get_chile_macro() - Chile macro dashboard")
    print("  • get_china_macro() - China credit/macro")
    print("  • get_full_macro_dashboard() - Consolidated all regions")
    print("  • get_quick_summary() - Key metrics only")

    print("\n--- Testing US Macro ---")
    try:
        us_data = dashboard.get_us_macro()
        print(f"\n✓ US Macro fetched:")
        print(f"  GDP: {us_data.get('gdp', {}).get('value')}% ({us_data.get('gdp', {}).get('period')})")
        print(f"  Unemployment: {us_data.get('unemployment', {}).get('value')}%")
        print(f"  Payrolls: {us_data.get('payrolls', {}).get('value')}K")
        print(f"  Retail Sales: {us_data.get('retail_sales', {}).get('value')}% MoM")
        print(f"  Industrial Prod: {us_data.get('industrial_prod', {}).get('value')}% MoM")
        print(f"  Housing Starts: {us_data.get('housing_starts', {}).get('value')}M")
        print(f"  Durable Goods: {us_data.get('durable_goods', {}).get('value')}% MoM")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "=" * 70)
    print("✅ Macro Dashboard module loaded successfully")

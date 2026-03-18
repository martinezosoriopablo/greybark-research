"""
Grey Bark - Inflation Analytics
Breakeven Inflation, Real Rates, and Inflation Decomposition

Uses FRED API for all data (free)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False
    print("[Inflation] ⚠ fredapi not installed. Run: pip install fredapi")

# Import config
try:
    from ...config import config
    FRED_API_KEY = config.fred.api_key
except:
    FRED_API_KEY = os.getenv('FRED_API_KEY', '')


class InflationAnalytics:
    """
    Comprehensive Inflation Analysis for Greybark Research
    
    Features:
    - Breakeven Inflation (market expectations)
    - Real Rates (TIPS yields)
    - CPI Decomposition (services vs goods)
    - Wage-Price Spiral analysis
    - Inflation regime classification
    
    Usage:
        analytics = InflationAnalytics()
        
        # Get breakeven inflation
        breakeven = analytics.get_breakeven_inflation()
        
        # Get real rates
        real_rates = analytics.get_real_rates()
        
        # Full inflation dashboard
        dashboard = analytics.get_inflation_dashboard()
    """
    
    # FRED Series IDs
    SERIES = {
        # Breakeven Inflation
        'breakeven_5y': 'T5YIE',
        'breakeven_10y': 'T10YIE',
        'breakeven_30y': 'T30YIEM',  # Monthly
        
        # Real Rates (TIPS Yields)
        'tips_5y': 'DFII5',
        'tips_10y': 'DFII10',
        'tips_20y': 'DFII20',
        'tips_30y': 'DFII30',
        
        # Nominal Yields (for comparison)
        'treasury_5y': 'DGS5',
        'treasury_10y': 'DGS10',
        'treasury_30y': 'DGS30',
        
        # CPI Components
        'cpi_all': 'CPIAUCSL',          # All Items
        'cpi_core': 'CPILFESL',          # Less Food & Energy
        'cpi_services': 'CUSR0000SAS',   # Services
        'cpi_goods': 'CUSR0000SAC',      # Commodities (Goods)
        'cpi_shelter': 'CUSR0000SAH1',   # Shelter
        'cpi_food': 'CPIUFDSL',          # Food
        'cpi_energy': 'CPIENGSL',        # Energy
        
        # PCE (Fed's preferred measure)
        'pce_all': 'PCEPI',
        'pce_core': 'PCEPILFE',
        
        # Wages
        'avg_hourly_earnings': 'CES0500000003',  # All private
        'employment_cost_index': 'ECIWAG',        # ECI Wages
        
        # Inflation Expectations (Michigan Survey)
        'michigan_1y': 'MICH',
        'michigan_5y': 'EXPINF5YR',  # 5Y expected
    }
    
    # Thresholds for interpretation
    THRESHOLDS = {
        'breakeven_high': 2.8,      # Above Fed target + buffer
        'breakeven_low': 1.5,       # Deflation concern
        'breakeven_anchored': (2.0, 2.5),  # Well-anchored range
        'real_rate_restrictive': 1.5,  # Restrictive monetary policy
        'real_rate_accommodative': -0.5,  # Accommodative
        'wage_inflation_spiral': 1.0,  # Wages growing faster than CPI by this much
    }
    
    def __init__(self, api_key: str = None):
        """Initialize with FRED API key"""
        if not FRED_AVAILABLE:
            raise ImportError("fredapi required: pip install fredapi")
        
        self.api_key = api_key or FRED_API_KEY
        self.fred = Fred(api_key=self.api_key)
        print("[Inflation] ✓ Connected to FRED")
    
    def _get_series(self, series_id: str, start_date: str = None) -> pd.Series:
        """Fetch a FRED series"""
        try:
            start = start_date or '2020-01-01'
            data = self.fred.get_series(series_id, observation_start=start)
            return data.dropna()
        except Exception as e:
            print(f"[Inflation] ✗ Error fetching {series_id}: {e}")
            return pd.Series()
    
    def _calculate_yoy(self, series: pd.Series) -> pd.Series:
        """Calculate Year-over-Year change"""
        return series.pct_change(periods=12) * 100
    
    # =========================================================================
    # BREAKEVEN INFLATION
    # =========================================================================
    
    def get_breakeven_inflation(self) -> Dict:
        """
        Get breakeven inflation rates (market's inflation expectations)
        
        Breakeven = Nominal Yield - TIPS Yield
        
        Returns:
            Dict with breakeven rates and analysis
        """
        print("[Inflation] Fetching breakeven inflation...")
        
        # Fetch data
        be_5y = self._get_series(self.SERIES['breakeven_5y'])
        be_10y = self._get_series(self.SERIES['breakeven_10y'])
        
        if be_5y.empty or be_10y.empty:
            return {'error': 'Unable to fetch breakeven data'}
        
        # Latest values
        latest_5y = be_5y.iloc[-1]
        latest_10y = be_10y.iloc[-1]
        
        # 1-month change
        change_5y_1m = latest_5y - be_5y.iloc[-22] if len(be_5y) > 22 else 0
        change_10y_1m = latest_10y - be_10y.iloc[-22] if len(be_10y) > 22 else 0
        
        # Historical context (percentile over 5 years)
        hist_5y = be_5y.tail(252 * 5)
        hist_10y = be_10y.tail(252 * 5)
        
        pct_5y = (hist_5y < latest_5y).sum() / len(hist_5y) * 100
        pct_10y = (hist_10y < latest_10y).sum() / len(hist_10y) * 100
        
        # Term structure (5y5y forward)
        # 5y5y = (10y * 10 - 5y * 5) / 5
        forward_5y5y = (latest_10y * 10 - latest_5y * 5) / 5
        
        # Interpretation
        if latest_10y > self.THRESHOLDS['breakeven_high']:
            status = 'ELEVATED'
            interpretation = 'Market expects inflation above Fed target'
            risk_signal = 'BEARISH for bonds'
        elif latest_10y < self.THRESHOLDS['breakeven_low']:
            status = 'LOW'
            interpretation = 'Deflation concerns or recession expectations'
            risk_signal = 'Watch for disinflation'
        elif self.THRESHOLDS['breakeven_anchored'][0] <= latest_10y <= self.THRESHOLDS['breakeven_anchored'][1]:
            status = 'WELL_ANCHORED'
            interpretation = 'Inflation expectations near Fed target'
            risk_signal = 'Neutral'
        else:
            status = 'MODERATE'
            interpretation = 'Slightly above target but manageable'
            risk_signal = 'Monitor'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current': {
                'breakeven_5y': round(latest_5y, 2),
                'breakeven_10y': round(latest_10y, 2),
                'forward_5y5y': round(forward_5y5y, 2)
            },
            'change_1m': {
                'breakeven_5y': round(change_5y_1m, 2),
                'breakeven_10y': round(change_10y_1m, 2)
            },
            'percentile_5y': {
                'breakeven_5y': round(pct_5y, 0),
                'breakeven_10y': round(pct_10y, 0)
            },
            'status': status,
            'interpretation': interpretation,
            'risk_signal': risk_signal,
            'fed_target': 2.0
        }
    
    # =========================================================================
    # REAL RATES
    # =========================================================================
    
    def get_real_rates(self) -> Dict:
        """
        Get real interest rates (TIPS yields)
        
        Real Rate = Nominal Yield - Expected Inflation
        
        Positive real rates = restrictive policy
        Negative real rates = accommodative policy
        
        Returns:
            Dict with real rates analysis
        """
        print("[Inflation] Fetching real rates...")
        
        # Fetch TIPS yields
        tips_5y = self._get_series(self.SERIES['tips_5y'])
        tips_10y = self._get_series(self.SERIES['tips_10y'])
        
        # Fetch nominal for comparison
        nom_5y = self._get_series(self.SERIES['treasury_5y'])
        nom_10y = self._get_series(self.SERIES['treasury_10y'])
        
        if tips_10y.empty:
            return {'error': 'Unable to fetch TIPS data'}
        
        # Latest values
        latest_tips_5y = tips_5y.iloc[-1] if not tips_5y.empty else None
        latest_tips_10y = tips_10y.iloc[-1]
        latest_nom_10y = nom_10y.iloc[-1] if not nom_10y.empty else None
        
        # 1-month and 1-year changes
        change_1m = latest_tips_10y - tips_10y.iloc[-22] if len(tips_10y) > 22 else 0
        change_1y = latest_tips_10y - tips_10y.iloc[-252] if len(tips_10y) > 252 else 0
        
        # Historical percentile
        hist = tips_10y.tail(252 * 5)
        percentile = (hist < latest_tips_10y).sum() / len(hist) * 100
        
        # Policy stance interpretation
        if latest_tips_10y > self.THRESHOLDS['real_rate_restrictive']:
            stance = 'RESTRICTIVE'
            interpretation = 'Real rates high - monetary policy tight'
            implication = 'Headwind for growth and risk assets'
        elif latest_tips_10y < self.THRESHOLDS['real_rate_accommodative']:
            stance = 'ACCOMMODATIVE'
            interpretation = 'Real rates negative - monetary policy loose'
            implication = 'Supportive for growth and risk assets'
        else:
            stance = 'NEUTRAL'
            interpretation = 'Real rates moderate - policy neutral'
            implication = 'Mixed signals'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current': {
                'tips_5y': round(latest_tips_5y, 2) if latest_tips_5y else None,
                'tips_10y': round(latest_tips_10y, 2),
                'nominal_10y': round(latest_nom_10y, 2) if latest_nom_10y else None
            },
            'change': {
                '1_month': round(change_1m, 2),
                '1_year': round(change_1y, 2)
            },
            'percentile_5y': round(percentile, 0),
            'policy_stance': stance,
            'interpretation': interpretation,
            'implication': implication
        }
    
    # =========================================================================
    # CPI DECOMPOSITION
    # =========================================================================
    
    def get_cpi_decomposition(self) -> Dict:
        """
        Decompose CPI into components
        
        Key insight: Services inflation is "stickier" than goods
        
        Returns:
            Dict with CPI component analysis
        """
        print("[Inflation] Fetching CPI decomposition...")
        
        # Fetch series
        cpi_all = self._get_series(self.SERIES['cpi_all'])
        cpi_core = self._get_series(self.SERIES['cpi_core'])
        cpi_services = self._get_series(self.SERIES['cpi_services'])
        cpi_goods = self._get_series(self.SERIES['cpi_goods'])
        cpi_shelter = self._get_series(self.SERIES['cpi_shelter'])
        
        # Calculate YoY
        yoy_all = self._calculate_yoy(cpi_all)
        yoy_core = self._calculate_yoy(cpi_core)
        yoy_services = self._calculate_yoy(cpi_services)
        yoy_goods = self._calculate_yoy(cpi_goods)
        yoy_shelter = self._calculate_yoy(cpi_shelter)
        
        # Latest values
        latest = {
            'cpi_all': round(yoy_all.iloc[-1], 2) if not yoy_all.empty else None,
            'cpi_core': round(yoy_core.iloc[-1], 2) if not yoy_core.empty else None,
            'cpi_services': round(yoy_services.iloc[-1], 2) if not yoy_services.empty else None,
            'cpi_goods': round(yoy_goods.iloc[-1], 2) if not yoy_goods.empty else None,
            'cpi_shelter': round(yoy_shelter.iloc[-1], 2) if not yoy_shelter.empty else None,
        }
        
        # Previous month for trend
        prev = {
            'cpi_all': round(yoy_all.iloc[-2], 2) if len(yoy_all) > 1 else None,
            'cpi_core': round(yoy_core.iloc[-2], 2) if len(yoy_core) > 1 else None,
            'cpi_services': round(yoy_services.iloc[-2], 2) if len(yoy_services) > 1 else None,
            'cpi_goods': round(yoy_goods.iloc[-2], 2) if len(yoy_goods) > 1 else None,
        }
        
        # Services vs Goods spread
        services_goods_spread = latest['cpi_services'] - latest['cpi_goods'] if latest['cpi_services'] and latest['cpi_goods'] else 0
        
        # Interpretation
        if latest['cpi_services'] and latest['cpi_services'] > 4.0:
            services_status = 'STICKY_HIGH'
            services_note = 'Services inflation remains elevated - harder to bring down'
        elif latest['cpi_services'] and latest['cpi_services'] > 3.0:
            services_status = 'ELEVATED'
            services_note = 'Services inflation above target'
        else:
            services_status = 'MODERATING'
            services_note = 'Services inflation coming down'
        
        if latest['cpi_goods'] and latest['cpi_goods'] < 0:
            goods_status = 'DEFLATION'
            goods_note = 'Goods prices falling - supply chain normalization'
        elif latest['cpi_goods'] and latest['cpi_goods'] < 2:
            goods_status = 'NORMALIZED'
            goods_note = 'Goods inflation back to normal'
        else:
            goods_status = 'ELEVATED'
            goods_note = 'Goods inflation still high'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'yoy_percent': latest,
            'previous_month': prev,
            'services_goods_spread': round(services_goods_spread, 2),
            'analysis': {
                'services': {
                    'status': services_status,
                    'note': services_note
                },
                'goods': {
                    'status': goods_status,
                    'note': goods_note
                }
            },
            'fed_target': 2.0,
            'key_insight': 'Services inflation is sticky; goods disinflation helps but not enough if services stay high'
        }
    
    # =========================================================================
    # WAGE-PRICE SPIRAL
    # =========================================================================
    
    def get_wage_inflation_analysis(self) -> Dict:
        """
        Analyze wage growth vs inflation for spiral risk
        
        Wage-Price Spiral: Wages ↑ → Costs ↑ → Prices ↑ → Workers demand higher wages → repeat
        
        Returns:
            Dict with wage-inflation analysis
        """
        print("[Inflation] Analyzing wage-price dynamics...")
        
        # Fetch data
        wages = self._get_series(self.SERIES['avg_hourly_earnings'])
        cpi = self._get_series(self.SERIES['cpi_all'])
        
        # Calculate YoY
        wage_yoy = self._calculate_yoy(wages)
        cpi_yoy = self._calculate_yoy(cpi)
        
        if wage_yoy.empty or cpi_yoy.empty:
            return {'error': 'Unable to fetch wage/CPI data'}
        
        # Align series
        combined = pd.DataFrame({
            'wage_growth': wage_yoy,
            'cpi': cpi_yoy
        }).dropna()
        
        if combined.empty:
            return {'error': 'No overlapping data'}
        
        # Latest values
        latest_wage = combined['wage_growth'].iloc[-1]
        latest_cpi = combined['cpi'].iloc[-1]
        
        # Real wage growth
        real_wage_growth = latest_wage - latest_cpi
        
        # Historical average spread
        hist_spread = (combined['wage_growth'] - combined['cpi']).tail(60)  # 5 years
        avg_spread = hist_spread.mean()
        
        # Spiral risk
        wage_cpi_diff = latest_wage - latest_cpi
        
        if wage_cpi_diff > self.THRESHOLDS['wage_inflation_spiral']:
            spiral_risk = 'HIGH'
            interpretation = 'Wages growing faster than inflation - spiral risk elevated'
            implication = 'Fed likely to stay hawkish'
        elif wage_cpi_diff > 0.5:
            spiral_risk = 'MODERATE'
            interpretation = 'Wages slightly outpacing inflation'
            implication = 'Monitor for persistence'
        elif wage_cpi_diff > 0:
            spiral_risk = 'LOW'
            interpretation = 'Wages keeping pace with inflation'
            implication = 'Real wages stable'
        else:
            spiral_risk = 'NONE'
            interpretation = 'Inflation outpacing wages'
            implication = 'Real wages declining - consumer pressure'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current': {
                'wage_growth_yoy': round(latest_wage, 2),
                'cpi_yoy': round(latest_cpi, 2),
                'real_wage_growth': round(real_wage_growth, 2)
            },
            'wage_cpi_spread': round(wage_cpi_diff, 2),
            'historical_avg_spread': round(avg_spread, 2),
            'spiral_risk': spiral_risk,
            'interpretation': interpretation,
            'implication': implication
        }
    
    # =========================================================================
    # INFLATION EXPECTATIONS (SURVEYS)
    # =========================================================================
    
    def get_inflation_expectations(self) -> Dict:
        """
        Get consumer inflation expectations from Michigan Survey
        
        Returns:
            Dict with survey-based expectations
        """
        print("[Inflation] Fetching inflation expectations...")
        
        mich_1y = self._get_series(self.SERIES['michigan_1y'])
        
        if mich_1y.empty:
            return {'error': 'Unable to fetch Michigan survey data'}
        
        latest = mich_1y.iloc[-1]
        prev_month = mich_1y.iloc[-2] if len(mich_1y) > 1 else latest
        prev_year = mich_1y.iloc[-12] if len(mich_1y) > 12 else latest
        
        # Historical percentile
        hist = mich_1y.tail(60)  # 5 years
        percentile = (hist < latest).sum() / len(hist) * 100
        
        if latest > 4.0:
            status = 'ELEVATED'
            note = 'Consumer inflation expectations high - may become self-fulfilling'
        elif latest > 3.0:
            status = 'ABOVE_NORMAL'
            note = 'Expectations above historical average'
        else:
            status = 'ANCHORED'
            note = 'Expectations well-anchored'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'michigan_1y_ahead': {
                'current': round(latest, 1),
                'previous_month': round(prev_month, 1),
                'previous_year': round(prev_year, 1),
                'change_yoy': round(latest - prev_year, 1)
            },
            'percentile_5y': round(percentile, 0),
            'status': status,
            'note': note
        }
    
    # =========================================================================
    # COMPREHENSIVE DASHBOARD
    # =========================================================================
    
    def get_inflation_dashboard(self) -> Dict:
        """
        Generate comprehensive inflation dashboard
        
        Returns:
            Dict with full inflation analysis
        """
        print("\n" + "="*70)
        print("INFLATION ANALYTICS DASHBOARD")
        print("="*70)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'breakeven_inflation': self.get_breakeven_inflation(),
            'real_rates': self.get_real_rates(),
            'cpi_decomposition': self.get_cpi_decomposition(),
            'wage_analysis': self.get_wage_inflation_analysis(),
            'expectations': self.get_inflation_expectations()
        }
        
        # Overall assessment
        be = dashboard['breakeven_inflation']
        rr = dashboard['real_rates']
        cpi = dashboard['cpi_decomposition']
        wage = dashboard['wage_analysis']
        
        # Score components (higher = more inflationary)
        score = 0
        factors = []
        
        if be.get('status') == 'ELEVATED':
            score += 2
            factors.append(f"Breakeven elevated at {be['current']['breakeven_10y']}%")
        elif be.get('status') in ['MODERATE', 'WELL_ANCHORED']:
            score += 1
        
        if cpi.get('analysis', {}).get('services', {}).get('status') == 'STICKY_HIGH':
            score += 2
            factors.append(f"Services inflation sticky at {cpi['yoy_percent']['cpi_services']}%")
        elif cpi.get('analysis', {}).get('services', {}).get('status') == 'ELEVATED':
            score += 1
        
        if wage.get('spiral_risk') == 'HIGH':
            score += 2
            factors.append(f"Wage-price spiral risk: wages {wage['current']['wage_growth_yoy']}% vs CPI {wage['current']['cpi_yoy']}%")
        elif wage.get('spiral_risk') == 'MODERATE':
            score += 1
        
        # Determine regime
        if score >= 5:
            regime = 'HIGH_INFLATION'
            recommendation = 'Underweight duration, favor TIPS, commodities as hedge'
        elif score >= 3:
            regime = 'MODERATING_INFLATION'
            recommendation = 'Neutral duration, some TIPS allocation'
        else:
            regime = 'LOW_INFLATION'
            recommendation = 'Overweight duration, nominal bonds preferred'
        
        dashboard['summary'] = {
            'inflation_score': score,
            'max_score': 6,
            'regime': regime,
            'key_factors': factors,
            'recommendation': recommendation
        }
        
        # Print summary
        print(f"\nInflation Score: {score}/6 → {regime}")
        print(f"Recommendation: {recommendation}")
        if factors:
            print("Key Factors:")
            for f in factors:
                print(f"  • {f}")
        
        return dashboard
    
    # =========================================================================
    # TIPS vs NOMINAL ALLOCATION
    # =========================================================================
    
    def get_tips_allocation_signal(self) -> Dict:
        """
        Generate signal for TIPS vs Nominal bond allocation
        
        Returns:
            Dict with allocation recommendation
        """
        be = self.get_breakeven_inflation()
        rr = self.get_real_rates()
        
        if 'error' in be or 'error' in rr:
            return {'error': 'Unable to generate signal'}
        
        breakeven_10y = be['current']['breakeven_10y']
        real_rate_10y = rr['current']['tips_10y']
        
        # Logic:
        # - High breakeven + low real rates → TIPS attractive
        # - Low breakeven + high real rates → Nominals attractive
        
        if breakeven_10y > 2.5 and real_rate_10y < 2.0:
            signal = 'OVERWEIGHT_TIPS'
            allocation = {'tips': 60, 'nominal': 40}
            rationale = 'High breakeven suggests inflation risk; TIPS provide protection'
        elif breakeven_10y < 2.0 and real_rate_10y > 2.0:
            signal = 'OVERWEIGHT_NOMINAL'
            allocation = {'tips': 20, 'nominal': 80}
            rationale = 'Low breakeven and high real rates favor nominal bonds'
        elif real_rate_10y > 2.0:
            signal = 'NEUTRAL_LEAN_TIPS'
            allocation = {'tips': 50, 'nominal': 50}
            rationale = 'High real rates attractive; balanced approach'
        else:
            signal = 'NEUTRAL'
            allocation = {'tips': 40, 'nominal': 60}
            rationale = 'No strong signal; slight preference for nominals'
        
        return {
            'timestamp': datetime.now().isoformat(),
            'inputs': {
                'breakeven_10y': breakeven_10y,
                'real_rate_10y': real_rate_10y
            },
            'signal': signal,
            'recommended_allocation': allocation,
            'rationale': rationale
        }


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    analytics = InflationAnalytics()
    
    # Full dashboard
    dashboard = analytics.get_inflation_dashboard()
    
    # Print detailed results
    print("\n" + "="*70)
    print("BREAKEVEN INFLATION")
    print("="*70)
    be = dashboard['breakeven_inflation']
    print(f"5Y Breakeven: {be['current']['breakeven_5y']}%")
    print(f"10Y Breakeven: {be['current']['breakeven_10y']}%")
    print(f"5Y5Y Forward: {be['current']['forward_5y5y']}%")
    print(f"Status: {be['status']} - {be['interpretation']}")
    
    print("\n" + "="*70)
    print("REAL RATES (TIPS)")
    print("="*70)
    rr = dashboard['real_rates']
    print(f"10Y TIPS Yield: {rr['current']['tips_10y']}%")
    print(f"Policy Stance: {rr['policy_stance']}")
    print(f"Implication: {rr['implication']}")
    
    print("\n" + "="*70)
    print("CPI DECOMPOSITION (YoY %)")
    print("="*70)
    cpi = dashboard['cpi_decomposition']
    print(f"All Items: {cpi['yoy_percent']['cpi_all']}%")
    print(f"Core: {cpi['yoy_percent']['cpi_core']}%")
    print(f"Services: {cpi['yoy_percent']['cpi_services']}% ({cpi['analysis']['services']['status']})")
    print(f"Goods: {cpi['yoy_percent']['cpi_goods']}% ({cpi['analysis']['goods']['status']})")
    
    print("\n" + "="*70)
    print("WAGE-PRICE DYNAMICS")
    print("="*70)
    wage = dashboard['wage_analysis']
    print(f"Wage Growth: {wage['current']['wage_growth_yoy']}%")
    print(f"CPI: {wage['current']['cpi_yoy']}%")
    print(f"Real Wage Growth: {wage['current']['real_wage_growth']}%")
    print(f"Spiral Risk: {wage['spiral_risk']}")
    
    # TIPS allocation signal
    print("\n" + "="*70)
    print("TIPS vs NOMINAL ALLOCATION")
    print("="*70)
    tips = analytics.get_tips_allocation_signal()
    print(f"Signal: {tips['signal']}")
    print(f"Allocation: TIPS {tips['recommended_allocation']['tips']}% / Nominal {tips['recommended_allocation']['nominal']}%")
    print(f"Rationale: {tips['rationale']}")

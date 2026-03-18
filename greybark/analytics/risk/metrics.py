"""
GREYBARK RESEARCH - Risk Metrics Module
=========================================
VaR calculation, stress testing, drawdown analysis.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import yfinance as yf


class RiskMetrics:
    """Comprehensive risk metrics calculator."""
    
    def __init__(self, returns: pd.DataFrame, weights: Dict[str, float] = None):
        self.returns = returns
        self.assets = returns.columns.tolist()
        
        if weights is None:
            n = len(self.assets)
            self.weights = {asset: 1/n for asset in self.assets}
        else:
            self.weights = weights
        
        weight_array = np.array([self.weights.get(a, 0) for a in self.assets])
        self.portfolio_returns = (returns * weight_array).sum(axis=1)
    
    def var_historical(self, confidence: float = 0.95) -> float:
        """VaR using historical simulation."""
        percentile = (1 - confidence) * 100
        return -np.percentile(self.portfolio_returns, percentile)
    
    def var_parametric(self, confidence: float = 0.95) -> float:
        """VaR using parametric method."""
        mu = self.portfolio_returns.mean()
        sigma = self.portfolio_returns.std()
        z = stats.norm.ppf(1 - confidence)
        return -(mu + z * sigma)
    
    def expected_shortfall(self, confidence: float = 0.95) -> float:
        """CVaR - average loss beyond VaR."""
        var = -self.var_historical(confidence)
        losses = self.portfolio_returns[self.portfolio_returns <= var]
        return -losses.mean() if len(losses) > 0 else self.var_historical(confidence)
    
    def calculate_all_var(self) -> Dict:
        """Calculate all VaR metrics."""
        var_95 = self.var_historical(0.95)
        var_99 = self.var_historical(0.99)
        
        return {
            'var_95_daily': var_95,
            'var_99_daily': var_99,
            'var_95_monthly': var_95 * np.sqrt(21),
            'var_99_monthly': var_99 * np.sqrt(21),
            'es_95': self.expected_shortfall(0.95),
            'es_99': self.expected_shortfall(0.99),
        }
    
    def max_drawdown(self) -> float:
        """Maximum drawdown."""
        cumulative = (1 + self.portfolio_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return -drawdown.min()
    
    def current_drawdown(self) -> float:
        """Current drawdown from peak."""
        cumulative = (1 + self.portfolio_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        return -drawdown.iloc[-1]
    
    def drawdown_analysis(self) -> Dict:
        """Comprehensive drawdown analysis."""
        cumulative = (1 + self.portfolio_returns).cumprod()
        running_max = cumulative.cummax()
        dd_series = (cumulative - running_max) / running_max
        
        return {
            'current_drawdown': self.current_drawdown(),
            'max_drawdown': self.max_drawdown(),
            'avg_drawdown': -dd_series[dd_series < 0].mean() if (dd_series < 0).any() else 0,
            'time_underwater_pct': (dd_series < 0).mean() * 100,
        }
    
    def correlation_matrix(self) -> pd.DataFrame:
        """Asset correlation matrix."""
        return self.returns.corr()
    
    def diversification_score(self) -> float:
        """Diversification score (0-1)."""
        corr = self.correlation_matrix()
        mask = ~np.eye(corr.shape[0], dtype=bool)
        avg_corr = np.abs(corr.values[mask]).mean()
        return 1 - avg_corr
    
    def portfolio_stats(self) -> Dict:
        """Portfolio statistics."""
        returns = self.portfolio_returns
        ann_factor = 252
        
        mean_return = returns.mean() * ann_factor
        volatility = returns.std() * np.sqrt(ann_factor)
        sharpe = mean_return / volatility if volatility > 0 else 0
        
        return {
            'annualized_return': mean_return,
            'annualized_volatility': volatility,
            'sharpe_ratio': sharpe,
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis(),
        }


class StressTester:
    """Stress testing framework."""
    
    HISTORICAL_SCENARIOS = {
        'COVID Crash (Feb-Mar 2020)': {
            'SPY': -33.9, 'QQQ': -30.1, 'EEM': -31.2,
            'TLT': +15.0, 'HYG': -20.5, 'GLD': +3.2, 'ECH': -40.0,
        },
        '2022 Rate Shock': {
            'SPY': -25.4, 'QQQ': -34.1, 'EEM': -22.0,
            'TLT': -31.0, 'HYG': -14.0, 'GLD': -1.0, 'ECH': -15.0,
        },
        'GFC 2008-2009': {
            'SPY': -56.8, 'QQQ': -52.0, 'EEM': -62.0,
            'TLT': +33.0, 'HYG': -35.0, 'GLD': +25.0, 'ECH': -55.0,
        },
    }
    
    HYPOTHETICAL_SCENARIOS = {
        'Fed +100bp Shock': {
            'SPY': -10.0, 'QQQ': -12.0, 'EEM': -12.0,
            'TLT': -15.0, 'HYG': -6.0, 'GLD': -3.0, 'ECH': -10.0,
        },
        'Mild Recession': {
            'SPY': -18.0, 'QQQ': -22.0, 'EEM': -20.0,
            'TLT': +8.0, 'HYG': -12.0, 'GLD': +5.0, 'ECH': -18.0,
        },
        'Severe Recession': {
            'SPY': -35.0, 'QQQ': -40.0, 'EEM': -40.0,
            'TLT': +15.0, 'HYG': -25.0, 'GLD': +15.0, 'ECH': -35.0,
        },
        'China Hard Landing': {
            'SPY': -8.0, 'QQQ': -10.0, 'EEM': -25.0,
            'TLT': +5.0, 'HYG': -8.0, 'GLD': +5.0, 'ECH': -30.0,
        },
        'Stagflation': {
            'SPY': -22.0, 'QQQ': -25.0, 'EEM': -18.0,
            'TLT': -18.0, 'HYG': -15.0, 'GLD': +20.0, 'ECH': -15.0,
        },
    }
    
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights
    
    def run_scenario(self, scenario: Dict[str, float]) -> float:
        """Calculate portfolio impact from scenario."""
        impact = 0.0
        for asset, weight in self.weights.items():
            impact += weight * scenario.get(asset, 0)
        return impact
    
    def run_all_scenarios(self) -> Dict:
        """Run all scenarios."""
        results = {}
        
        for name, scenario in {**self.HISTORICAL_SCENARIOS, **self.HYPOTHETICAL_SCENARIOS}.items():
            impact = self.run_scenario(scenario)
            results[name] = {
                'portfolio_impact': impact,
                'worst_asset': min(scenario.items(), key=lambda x: x[1]),
                'best_asset': max(scenario.items(), key=lambda x: x[1]),
            }
        
        return results
    
    def worst_case_loss(self) -> Tuple[str, float]:
        """Find worst case scenario."""
        results = self.run_all_scenarios()
        worst = min(results.items(), key=lambda x: x[1]['portfolio_impact'])
        return worst[0], worst[1]['portfolio_impact']


class LiquidityMonitor:
    """Monitor market liquidity."""
    
    def get_vix(self) -> Dict:
        """Get VIX level and status."""
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="5d")
            current = hist['Close'].iloc[-1]
            
            if current < 20: status = 'NORMAL'
            elif current < 25: status = 'ELEVATED'
            elif current < 35: status = 'HIGH'
            else: status = 'EXTREME'
            
            return {'current': current, 'status': status}
        except:
            return {'error': 'Could not fetch VIX'}
    
    def calculate_liquidity_score(self, vix_data: Dict, illiquid_pct: float = 0) -> float:
        """Calculate liquidity score (1-10)."""
        score = 10.0
        
        if 'current' in vix_data:
            vix = vix_data['current']
            if vix > 35: score -= 3
            elif vix > 25: score -= 2
            elif vix > 20: score -= 1
        
        score -= illiquid_pct / 10
        return max(1, min(10, score))


class RiskScorecard:
    """Consolidated risk scorecard."""
    
    WEIGHTS = {
        'market_risk': 0.25,
        'credit_risk': 0.20,
        'liquidity_risk': 0.15,
        'interest_rate_risk': 0.15,
        'concentration_risk': 0.10,
        'geopolitical_risk': 0.15,
    }
    
    def __init__(self):
        self.scores = {}
        self.trends = {}
    
    def set_score(self, factor: str, score: float, trend: str = '→'):
        self.scores[factor] = max(1, min(10, score))
        self.trends[factor] = trend
    
    def calculate_overall_score(self) -> float:
        total = sum(self.scores.get(f, 5) * w for f, w in self.WEIGHTS.items())
        return total
    
    def get_status(self) -> str:
        score = self.calculate_overall_score()
        if score <= 3: return 'LOW'
        elif score <= 6: return 'MODERATE'
        elif score <= 8: return 'ELEVATED'
        else: return 'HIGH'
    
    def generate_report(self) -> Dict:
        return {
            'overall_score': self.calculate_overall_score(),
            'status': self.get_status(),
            'factor_scores': self.scores.copy(),
            'timestamp': datetime.now().isoformat(),
        }


def fetch_returns(symbols: List[str], period: str = '5y') -> pd.DataFrame:
    """Fetch historical returns."""
    data = yf.download(symbols, period=period, progress=False)
    # Handle different yfinance versions (some use MultiIndex columns)
    if isinstance(data.columns, pd.MultiIndex):
        # Try 'Adj Close' first, fall back to 'Close'
        if 'Adj Close' in data.columns.get_level_values(0):
            data = data['Adj Close']
        elif 'Close' in data.columns.get_level_values(0):
            data = data['Close']
        else:
            # Use first level
            data = data[data.columns.get_level_values(0)[0]]
    else:
        # Single level columns
        if 'Adj Close' in data.columns:
            data = data['Adj Close']
        elif 'Close' in data.columns:
            data = data['Close']
    return data.pct_change().dropna()


def generate_risk_dashboard(weights: Dict[str, float], portfolio_value: float = 1000000) -> Dict:
    """Generate complete risk dashboard."""
    symbols = list(weights.keys())
    returns = fetch_returns(symbols, period='5y')
    
    risk_metrics = RiskMetrics(returns, weights)
    stress_tester = StressTester(weights)
    liquidity_monitor = LiquidityMonitor()
    scorecard = RiskScorecard()
    
    var_metrics = risk_metrics.calculate_all_var()
    drawdown = risk_metrics.drawdown_analysis()
    stats = risk_metrics.portfolio_stats()
    stress_results = stress_tester.run_all_scenarios()
    worst_case = stress_tester.worst_case_loss()
    vix_data = liquidity_monitor.get_vix()
    liquidity_score = liquidity_monitor.calculate_liquidity_score(vix_data)
    
    scorecard.set_score('market_risk', min(10, 5 + stats['annualized_volatility'] * 20))
    scorecard.set_score('liquidity_risk', 10 - liquidity_score)
    
    return {
        'timestamp': datetime.now().isoformat(),
        'portfolio_value': portfolio_value,
        'var': {**var_metrics, 'var_95_usd': var_metrics['var_95_daily'] * portfolio_value},
        'drawdown': drawdown,
        'portfolio_stats': stats,
        'correlations': {'diversification_score': risk_metrics.diversification_score()},
        'stress_testing': {'scenarios': stress_results, 'worst_case': worst_case},
        'liquidity': {'vix': vix_data, 'score': liquidity_score},
        'scorecard': scorecard.generate_report(),
    }

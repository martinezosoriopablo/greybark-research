"""
Greybark Research - Factor Analysis Module
Mejora #7 del AI Council

Provides factor-based equity analysis:
- Value factors (P/E, P/B, EV/EBITDA, Dividend Yield)
- Growth factors (Revenue growth, EPS growth, ROE)
- Momentum factors (Price momentum, RSI, relative strength)
- Quality factors (ROE, Debt/Equity, margins)
- Factor scoring and stock screening

Data Sources:
- AlphaVantage (fundamentals, technical indicators)
- Yahoo Finance (prices, basic fundamentals)

Author: Greybark Research
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from data_sources.alphavantage_client import AlphaVantageClient
except ImportError:
    from greybark.data_sources.alphavantage_client import AlphaVantageClient


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class FactorStyle(Enum):
    """Investment factor styles"""
    VALUE = "value"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    QUALITY = "quality"
    LOW_VOLATILITY = "low_volatility"
    SIZE = "size"


@dataclass
class FactorScore:
    """Individual factor score"""
    factor: str
    raw_value: float
    percentile: float  # 0-100
    z_score: float
    signal: str  # STRONG, MODERATE, WEAK, NEUTRAL


@dataclass
class StockFactorProfile:
    """Complete factor profile for a stock"""
    ticker: str
    value_score: float
    growth_score: float
    momentum_score: float
    quality_score: float
    composite_score: float
    factor_tilt: str  # Primary factor exposure
    details: Dict[str, FactorScore]


# =============================================================================
# FACTOR DEFINITIONS
# =============================================================================

# Value metrics (lower is better for most)
VALUE_METRICS = {
    'pe_ratio': {'source': 'PERatio', 'lower_better': True, 'weight': 0.25},
    'pb_ratio': {'source': 'PriceToBookRatio', 'lower_better': True, 'weight': 0.20},
    'ps_ratio': {'source': 'PriceToSalesRatioTTM', 'lower_better': True, 'weight': 0.15},
    'ev_ebitda': {'source': 'EVToEBITDA', 'lower_better': True, 'weight': 0.20},
    'dividend_yield': {'source': 'DividendYield', 'lower_better': False, 'weight': 0.20},
}

# Growth metrics (higher is better)
GROWTH_METRICS = {
    'revenue_growth': {'source': 'QuarterlyRevenueGrowthYOY', 'weight': 0.30},
    'eps_growth': {'source': 'QuarterlyEarningsGrowthYOY', 'weight': 0.30},
    'peg_ratio': {'source': 'PEGRatio', 'lower_better': True, 'weight': 0.20},
    'analyst_target_upside': {'source': 'AnalystTargetPrice', 'weight': 0.20},
}

# Quality metrics (higher is better for most)
QUALITY_METRICS = {
    'roe': {'source': 'ReturnOnEquityTTM', 'weight': 0.25},
    'roa': {'source': 'ReturnOnAssetsTTM', 'weight': 0.20},
    'profit_margin': {'source': 'ProfitMargin', 'weight': 0.20},
    'operating_margin': {'source': 'OperatingMarginTTM', 'weight': 0.15},
    'debt_to_equity': {'source': 'DebtToEquity', 'lower_better': True, 'weight': 0.20},
}

# Momentum lookback periods (days)
MOMENTUM_PERIODS = {
    '1M': 21,
    '3M': 63,
    '6M': 126,
    '12M': 252,
}


# =============================================================================
# MAIN CLASS
# =============================================================================

class FactorAnalytics:
    """
    Factor-based equity analysis
    
    Calculates and scores stocks on:
    - Value: P/E, P/B, EV/EBITDA, Dividend Yield
    - Growth: Revenue growth, EPS growth, PEG
    - Momentum: Price returns, RSI, relative strength
    - Quality: ROE, ROA, margins, leverage
    
    Usage:
        analytics = FactorAnalytics()
        
        # Single stock analysis
        profile = analytics.get_factor_profile('AAPL')
        
        # Screen stocks by factor
        value_stocks = analytics.screen_by_factor(['AAPL', 'MSFT', 'GOOGL'], 'value')
        
        # Multi-factor scoring
        ranked = analytics.rank_stocks(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])
    """
    
    def __init__(self, alphavantage_api_key: Optional[str] = None):
        """Initialize with API key"""
        self.av = AlphaVantageClient(api_key=alphavantage_api_key)
        self._cache = {}
    
    # =========================================================================
    # FUNDAMENTAL DATA FETCHING
    # =========================================================================
    
    def _get_company_overview(self, ticker: str) -> Optional[Dict]:
        """Fetch company fundamentals from AlphaVantage"""
        try:
            return self.av.get_company_overview(ticker)
        except Exception as e:
            print(f"  ✗ Error fetching overview for {ticker}: {e}")
            return None
    
    def _get_price_history(self, ticker: str, days: int = 252) -> Optional[pd.DataFrame]:
        """Fetch price history via yfinance"""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1y')
            return hist if len(hist) > 0 else None
        except Exception as e:
            print(f"  ✗ Error fetching prices for {ticker}: {e}")
            return None
    
    # =========================================================================
    # VALUE FACTOR
    # =========================================================================
    
    def calculate_value_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate value factor score
        
        Metrics: P/E, P/B, P/S, EV/EBITDA, Dividend Yield
        """
        overview = self._get_company_overview(ticker)
        
        if not overview:
            return {'error': f'Could not fetch data for {ticker}'}
        
        metrics = {}
        scores = []
        
        for metric_name, config in VALUE_METRICS.items():
            raw_value = overview.get(config['source'])
            
            if raw_value and raw_value != 'None' and raw_value != '-':
                try:
                    value = float(raw_value)
                    
                    # Normalize and score (0-100)
                    # Using typical market ranges
                    if metric_name == 'pe_ratio':
                        score = max(0, min(100, 100 - (value - 10) * 3))
                    elif metric_name == 'pb_ratio':
                        score = max(0, min(100, 100 - (value - 1) * 20))
                    elif metric_name == 'ps_ratio':
                        score = max(0, min(100, 100 - (value - 1) * 15))
                    elif metric_name == 'ev_ebitda':
                        score = max(0, min(100, 100 - (value - 8) * 5))
                    elif metric_name == 'dividend_yield':
                        score = min(100, value * 100 * 20)  # 5% yield = 100
                    else:
                        score = 50
                    
                    metrics[metric_name] = {
                        'raw': value,
                        'score': round(score, 1)
                    }
                    scores.append(score * config['weight'])
                    
                except (ValueError, TypeError):
                    pass
        
        composite = sum(scores) / sum(VALUE_METRICS[m]['weight'] for m in metrics) if metrics else 0
        
        return {
            'ticker': ticker,
            'factor': 'VALUE',
            'composite_score': round(composite, 1),
            'metrics': metrics,
            'signal': self._score_to_signal(composite),
            'interpretation': self._interpret_value_score(composite)
        }
    
    # =========================================================================
    # GROWTH FACTOR
    # =========================================================================
    
    def calculate_growth_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate growth factor score
        
        Metrics: Revenue growth, EPS growth, PEG ratio
        """
        overview = self._get_company_overview(ticker)
        
        if not overview:
            return {'error': f'Could not fetch data for {ticker}'}
        
        metrics = {}
        scores = []
        
        # Revenue growth
        rev_growth = overview.get('QuarterlyRevenueGrowthYOY')
        if rev_growth and rev_growth != 'None':
            try:
                value = float(rev_growth) * 100  # Convert to percentage
                score = max(0, min(100, 50 + value * 2))  # 25% growth = 100
                metrics['revenue_growth'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.30)
            except (ValueError, TypeError):
                pass
        
        # EPS growth
        eps_growth = overview.get('QuarterlyEarningsGrowthYOY')
        if eps_growth and eps_growth != 'None':
            try:
                value = float(eps_growth) * 100
                score = max(0, min(100, 50 + value * 2))
                metrics['eps_growth'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.30)
            except (ValueError, TypeError):
                pass
        
        # PEG ratio (lower is better for growth at reasonable price)
        peg = overview.get('PEGRatio')
        if peg and peg != 'None':
            try:
                value = float(peg)
                score = max(0, min(100, 100 - (value - 1) * 30))  # PEG 1 = 100
                metrics['peg_ratio'] = {'raw': round(value, 2), 'score': round(score, 1)}
                scores.append(score * 0.20)
            except (ValueError, TypeError):
                pass
        
        # Analyst target upside
        target = overview.get('AnalystTargetPrice')
        price = overview.get('50DayMovingAverage')
        if target and price and target != 'None' and price != 'None':
            try:
                upside = (float(target) / float(price) - 1) * 100
                score = max(0, min(100, 50 + upside * 2))
                metrics['analyst_upside'] = {'raw': round(upside, 1), 'score': round(score, 1)}
                scores.append(score * 0.20)
            except (ValueError, TypeError):
                pass
        
        total_weight = sum([0.30 if 'revenue_growth' in metrics else 0,
                           0.30 if 'eps_growth' in metrics else 0,
                           0.20 if 'peg_ratio' in metrics else 0,
                           0.20 if 'analyst_upside' in metrics else 0])
        
        composite = sum(scores) / total_weight if total_weight > 0 else 0
        
        return {
            'ticker': ticker,
            'factor': 'GROWTH',
            'composite_score': round(composite, 1),
            'metrics': metrics,
            'signal': self._score_to_signal(composite),
            'interpretation': self._interpret_growth_score(composite)
        }
    
    # =========================================================================
    # MOMENTUM FACTOR
    # =========================================================================
    
    def calculate_momentum_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate momentum factor score
        
        Metrics: 1M, 3M, 6M, 12M returns, RSI
        """
        prices = self._get_price_history(ticker)
        
        if prices is None or len(prices) < 30:
            return {'error': f'Insufficient price data for {ticker}'}
        
        metrics = {}
        scores = []
        
        current_price = prices['Close'].iloc[-1]
        
        # Price momentum at different horizons
        weights = {'1M': 0.20, '3M': 0.25, '6M': 0.25, '12M': 0.15}
        
        for period, days in MOMENTUM_PERIODS.items():
            if len(prices) >= days:
                past_price = prices['Close'].iloc[-days]
                ret = (current_price / past_price - 1) * 100
                
                # Score: 0% = 50, +20% = 100, -20% = 0
                score = max(0, min(100, 50 + ret * 2.5))
                
                metrics[f'return_{period.lower()}'] = {
                    'raw': round(ret, 1),
                    'score': round(score, 1)
                }
                scores.append(score * weights.get(period, 0.15))
        
        # RSI (14-day)
        if len(prices) >= 14:
            delta = prices['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # RSI scoring: 50 = neutral, >70 overbought, <30 oversold
            # For momentum, we want 50-70 range
            if 50 <= current_rsi <= 70:
                rsi_score = 80  # Strong momentum
            elif 30 <= current_rsi < 50:
                rsi_score = 50  # Building momentum
            elif current_rsi > 70:
                rsi_score = 40  # Overbought, may reverse
            else:
                rsi_score = 30  # Oversold, negative momentum
            
            metrics['rsi_14'] = {'raw': round(current_rsi, 1), 'score': rsi_score}
            scores.append(rsi_score * 0.15)
        
        total_weight = sum(weights.values()) + 0.15  # Including RSI
        composite = sum(scores) / total_weight if scores else 0
        
        return {
            'ticker': ticker,
            'factor': 'MOMENTUM',
            'composite_score': round(composite, 1),
            'metrics': metrics,
            'signal': self._score_to_signal(composite),
            'interpretation': self._interpret_momentum_score(composite)
        }
    
    # =========================================================================
    # QUALITY FACTOR
    # =========================================================================
    
    def calculate_quality_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate quality factor score
        
        Metrics: ROE, ROA, Profit margin, Operating margin, Debt/Equity
        """
        overview = self._get_company_overview(ticker)
        
        if not overview:
            return {'error': f'Could not fetch data for {ticker}'}
        
        metrics = {}
        scores = []
        
        # ROE
        roe = overview.get('ReturnOnEquityTTM')
        if roe and roe != 'None':
            try:
                value = float(roe) * 100
                score = max(0, min(100, value * 4))  # 25% ROE = 100
                metrics['roe'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.25)
            except (ValueError, TypeError):
                pass
        
        # ROA
        roa = overview.get('ReturnOnAssetsTTM')
        if roa and roa != 'None':
            try:
                value = float(roa) * 100
                score = max(0, min(100, value * 6.67))  # 15% ROA = 100
                metrics['roa'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.20)
            except (ValueError, TypeError):
                pass
        
        # Profit margin
        margin = overview.get('ProfitMargin')
        if margin and margin != 'None':
            try:
                value = float(margin) * 100
                score = max(0, min(100, value * 4))  # 25% margin = 100
                metrics['profit_margin'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.20)
            except (ValueError, TypeError):
                pass
        
        # Operating margin
        op_margin = overview.get('OperatingMarginTTM')
        if op_margin and op_margin != 'None':
            try:
                value = float(op_margin) * 100
                score = max(0, min(100, value * 3.33))  # 30% margin = 100
                metrics['operating_margin'] = {'raw': round(value, 1), 'score': round(score, 1)}
                scores.append(score * 0.15)
            except (ValueError, TypeError):
                pass
        
        # Debt/Equity (lower is better)
        de = overview.get('DebtToEquity')
        if de and de != 'None':
            try:
                value = float(de)
                score = max(0, min(100, 100 - value * 50))  # 0 D/E = 100, 2 D/E = 0
                metrics['debt_to_equity'] = {'raw': round(value, 2), 'score': round(score, 1)}
                scores.append(score * 0.20)
            except (ValueError, TypeError):
                pass
        
        total_weight = sum([0.25 if 'roe' in metrics else 0,
                           0.20 if 'roa' in metrics else 0,
                           0.20 if 'profit_margin' in metrics else 0,
                           0.15 if 'operating_margin' in metrics else 0,
                           0.20 if 'debt_to_equity' in metrics else 0])
        
        composite = sum(scores) / total_weight if total_weight > 0 else 0
        
        return {
            'ticker': ticker,
            'factor': 'QUALITY',
            'composite_score': round(composite, 1),
            'metrics': metrics,
            'signal': self._score_to_signal(composite),
            'interpretation': self._interpret_quality_score(composite)
        }
    
    # =========================================================================
    # COMPOSITE ANALYSIS
    # =========================================================================
    
    def get_factor_profile(self, ticker: str) -> Dict[str, Any]:
        """
        Get complete factor profile for a stock
        
        Returns all factor scores and composite ranking
        """
        print(f"[Factors] Analyzing {ticker}...")
        
        value = self.calculate_value_score(ticker)
        growth = self.calculate_growth_score(ticker)
        momentum = self.calculate_momentum_score(ticker)
        quality = self.calculate_quality_score(ticker)
        
        # Calculate composite (equal weighted)
        scores = []
        if 'composite_score' in value:
            scores.append(('VALUE', value['composite_score']))
        if 'composite_score' in growth:
            scores.append(('GROWTH', growth['composite_score']))
        if 'composite_score' in momentum:
            scores.append(('MOMENTUM', momentum['composite_score']))
        if 'composite_score' in quality:
            scores.append(('QUALITY', quality['composite_score']))
        
        composite = np.mean([s[1] for s in scores]) if scores else 0
        
        # Determine factor tilt (highest scoring factor)
        factor_tilt = max(scores, key=lambda x: x[1])[0] if scores else 'UNKNOWN'
        
        return {
            'ticker': ticker,
            'composite_score': round(composite, 1),
            'factor_tilt': factor_tilt,
            'factors': {
                'value': value,
                'growth': growth,
                'momentum': momentum,
                'quality': quality
            },
            'summary': {
                'value_score': value.get('composite_score', 0),
                'growth_score': growth.get('composite_score', 0),
                'momentum_score': momentum.get('composite_score', 0),
                'quality_score': quality.get('composite_score', 0),
            },
            'recommendation': self._generate_factor_recommendation(value, growth, momentum, quality),
            'as_of': datetime.now().isoformat()
        }
    
    def rank_stocks(self, tickers: List[str], 
                    weights: Dict[str, float] = None) -> List[Dict]:
        """
        Rank multiple stocks by factor scores
        
        Args:
            tickers: List of stock tickers
            weights: Optional factor weights (default equal)
        
        Returns:
            Sorted list of stocks with scores
        """
        if weights is None:
            weights = {'value': 0.25, 'growth': 0.25, 'momentum': 0.25, 'quality': 0.25}
        
        results = []
        
        for ticker in tickers:
            profile = self.get_factor_profile(ticker)
            
            if 'error' not in profile:
                weighted_score = (
                    profile['summary']['value_score'] * weights.get('value', 0.25) +
                    profile['summary']['growth_score'] * weights.get('growth', 0.25) +
                    profile['summary']['momentum_score'] * weights.get('momentum', 0.25) +
                    profile['summary']['quality_score'] * weights.get('quality', 0.25)
                )
                
                results.append({
                    'ticker': ticker,
                    'weighted_score': round(weighted_score, 1),
                    'factor_tilt': profile['factor_tilt'],
                    'value': profile['summary']['value_score'],
                    'growth': profile['summary']['growth_score'],
                    'momentum': profile['summary']['momentum_score'],
                    'quality': profile['summary']['quality_score']
                })
        
        # Sort by weighted score
        results.sort(key=lambda x: x['weighted_score'], reverse=True)
        
        # Add rank
        for i, r in enumerate(results):
            r['rank'] = i + 1
        
        return results
    
    def screen_by_factor(self, tickers: List[str], 
                         factor: str,
                         min_score: float = 60) -> List[Dict]:
        """
        Screen stocks by a specific factor
        
        Args:
            tickers: List to screen
            factor: 'value', 'growth', 'momentum', or 'quality'
            min_score: Minimum score threshold
        
        Returns:
            Filtered and sorted list
        """
        factor = factor.lower()
        results = []
        
        for ticker in tickers:
            if factor == 'value':
                score_data = self.calculate_value_score(ticker)
            elif factor == 'growth':
                score_data = self.calculate_growth_score(ticker)
            elif factor == 'momentum':
                score_data = self.calculate_momentum_score(ticker)
            elif factor == 'quality':
                score_data = self.calculate_quality_score(ticker)
            else:
                continue
            
            if 'composite_score' in score_data and score_data['composite_score'] >= min_score:
                results.append({
                    'ticker': ticker,
                    'factor': factor.upper(),
                    'score': score_data['composite_score'],
                    'signal': score_data['signal'],
                    'metrics': score_data.get('metrics', {})
                })
        
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _score_to_signal(self, score: float) -> str:
        """Convert score to signal"""
        if score >= 75:
            return 'STRONG'
        elif score >= 60:
            return 'MODERATE'
        elif score >= 40:
            return 'NEUTRAL'
        else:
            return 'WEAK'
    
    def _interpret_value_score(self, score: float) -> str:
        if score >= 70:
            return "Attractive valuation - stock appears undervalued"
        elif score >= 50:
            return "Fair valuation - reasonable entry point"
        else:
            return "Expensive valuation - limited margin of safety"
    
    def _interpret_growth_score(self, score: float) -> str:
        if score >= 70:
            return "Strong growth profile - expanding rapidly"
        elif score >= 50:
            return "Moderate growth - steady expansion"
        else:
            return "Limited growth - mature or declining"
    
    def _interpret_momentum_score(self, score: float) -> str:
        if score >= 70:
            return "Strong positive momentum - trend following favorable"
        elif score >= 50:
            return "Neutral momentum - no clear trend"
        else:
            return "Negative momentum - downtrend in place"
    
    def _interpret_quality_score(self, score: float) -> str:
        if score >= 70:
            return "High quality business - strong fundamentals"
        elif score >= 50:
            return "Average quality - acceptable fundamentals"
        else:
            return "Low quality - weak fundamentals or high leverage"
    
    def _generate_factor_recommendation(self, value, growth, momentum, quality) -> str:
        """Generate recommendation based on factor profile"""
        scores = {
            'value': value.get('composite_score', 0),
            'growth': growth.get('composite_score', 0),
            'momentum': momentum.get('composite_score', 0),
            'quality': quality.get('composite_score', 0)
        }
        
        avg = np.mean(list(scores.values()))
        
        # Check for specific patterns
        if scores['value'] > 70 and scores['quality'] > 60:
            return "Quality value play - consider for long-term portfolio"
        elif scores['growth'] > 70 and scores['momentum'] > 60:
            return "Growth with momentum - suitable for growth-oriented investors"
        elif scores['momentum'] > 70 and avg > 50:
            return "Strong momentum - potential tactical opportunity"
        elif avg > 65:
            return "Well-rounded stock - attractive across multiple factors"
        elif avg > 50:
            return "Average profile - selective entry recommended"
        else:
            return "Weak factor profile - caution advised"


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - FACTOR ANALYTICS TEST")
    print("=" * 60)
    
    analytics = FactorAnalytics()
    
    print("\n--- Available Methods ---")
    print("  • calculate_value_score(ticker)")
    print("  • calculate_growth_score(ticker)")
    print("  • calculate_momentum_score(ticker)")
    print("  • calculate_quality_score(ticker)")
    print("  • get_factor_profile(ticker)")
    print("  • rank_stocks(tickers, weights)")
    print("  • screen_by_factor(tickers, factor, min_score)")
    
    print("\n✅ Factor Analytics module loaded successfully")

"""
Grey Bark - Earnings Analytics
Comprehensive earnings analysis using AlphaVantage APIs

APIs Used:
- EARNINGS: Historical EPS + surprise data
- EARNINGS_ESTIMATES: Consensus estimates (coming quarters)
- OVERVIEW: Forward P/E, PEG, valuation metrics
- INSIDER_TRANSACTIONS: Smart money signals
- EARNINGS_CALENDAR: Upcoming earnings dates
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import time

# Import config
try:
    from ...config import config
    ALPHAVANTAGE_API_KEY = config.alphavantage.api_key
except:
    ALPHAVANTAGE_API_KEY = 'C4OH1WYEIX3P11BU'

BASE_URL = "https://www.alphavantage.co/query"


class EarningsAnalytics:
    """
    Comprehensive Earnings Analysis for Greybark Research
    
    Features:
    - EPS History & Surprise Analysis
    - Earnings Estimates & Revisions
    - Valuation Metrics (Forward P/E, PEG)
    - Insider Transactions (Smart Money)
    - Earnings Calendar
    - Sector-level aggregation
    
    Usage:
        analytics = EarningsAnalytics()
        
        # Single stock analysis
        report = analytics.get_earnings_report('AAPL')
        
        # S&P 500 sector analysis
        sector_report = analytics.get_sector_earnings_momentum()
        
        # Full dashboard
        dashboard = analytics.get_earnings_dashboard(['AAPL', 'MSFT', 'GOOGL'])
    """
    
    # S&P 500 sector representatives
    SECTOR_TICKERS = {
        'Technology': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META'],
        'Healthcare': ['JNJ', 'UNH', 'PFE', 'ABBV', 'MRK'],
        'Financials': ['JPM', 'BAC', 'WFC', 'GS', 'MS'],
        'Consumer Discretionary': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE'],
        'Consumer Staples': ['PG', 'KO', 'PEP', 'WMT', 'COST'],
        'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG'],
        'Industrials': ['CAT', 'BA', 'UNP', 'HON', 'GE'],
        'Materials': ['LIN', 'APD', 'ECL', 'SHW', 'NEM'],
        'Utilities': ['NEE', 'DUK', 'SO', 'D', 'AEP'],
        'Real Estate': ['AMT', 'PLD', 'CCI', 'EQIX', 'PSA'],
        'Communication Services': ['GOOGL', 'META', 'DIS', 'NFLX', 'VZ'],
    }
    
    # Thresholds
    THRESHOLDS = {
        'surprise_beat': 0.0,          # Beat if surprise > 0
        'surprise_strong_beat': 5.0,   # Strong beat if > 5%
        'surprise_miss': -5.0,         # Miss if < -5%
        'revision_positive': 0.5,      # Positive revision > 0.5%
        'revision_negative': -0.5,     # Negative revision < -0.5%
        'pe_expensive': 25,            # Forward P/E > 25 = expensive
        'pe_cheap': 15,                # Forward P/E < 15 = cheap
        'peg_attractive': 1.5,         # PEG < 1.5 = attractive
        'insider_bullish': 0.5,        # Net insider buying ratio
    }
    
    def __init__(self, api_key: str = None):
        """Initialize with AlphaVantage API key"""
        self.api_key = api_key or ALPHAVANTAGE_API_KEY
        self.cache = {}
        self.last_call = 0
        self.min_interval = 0.5  # 500ms between calls (premium allows 75/min)
        print("[Earnings] ✓ EarningsAnalytics initialized")
    
    def _rate_limit(self):
        """Respect API rate limits"""
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()
    
    def _api_call(self, function: str, **params) -> Dict:
        """Make API call with rate limiting"""
        self._rate_limit()
        
        params['function'] = function
        params['apikey'] = self.api_key
        
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
            data = response.json()
            
            if 'Error Message' in data:
                print(f"[Earnings] ✗ API Error: {data['Error Message']}")
                return {}
            if 'Note' in data:
                print(f"[Earnings] ⚠ Rate limit: {data['Note']}")
                return {}
                
            return data
        except Exception as e:
            print(f"[Earnings] ✗ Request failed: {e}")
            return {}
    
    # =========================================================================
    # EARNINGS HISTORY & SURPRISES
    # =========================================================================
    
    def get_earnings_history(self, symbol: str) -> Dict:
        """
        Get historical earnings data including surprises
        
        Returns:
            Dict with quarterly earnings history
        """
        print(f"[Earnings] Fetching earnings history for {symbol}...")
        
        data = self._api_call('EARNINGS', symbol=symbol)
        
        if not data or 'quarterlyEarnings' not in data:
            return {'error': f'No earnings data for {symbol}'}
        
        quarterly = data.get('quarterlyEarnings', [])
        annual = data.get('annualEarnings', [])
        
        if not quarterly:
            return {'error': 'No quarterly earnings data'}
        
        # Process quarterly data
        quarters = []
        beat_count = 0
        miss_count = 0
        total_surprise = 0
        
        for q in quarterly[:12]:  # Last 12 quarters (3 years)
            try:
                reported = float(q.get('reportedEPS', 0) or 0)
                estimated = float(q.get('estimatedEPS', 0) or 0)
                surprise_pct = float(q.get('surprisePercentage', 0) or 0)
                
                if estimated != 0:
                    calc_surprise = ((reported - estimated) / abs(estimated)) * 100
                else:
                    calc_surprise = surprise_pct
                
                quarters.append({
                    'fiscal_date': q.get('fiscalDateEnding'),
                    'reported_date': q.get('reportedDate'),
                    'reported_eps': reported,
                    'estimated_eps': estimated,
                    'surprise_pct': round(calc_surprise, 2),
                    'beat': calc_surprise > 0
                })
                
                if calc_surprise > 0:
                    beat_count += 1
                elif calc_surprise < 0:
                    miss_count += 1
                    
                total_surprise += calc_surprise
                
            except (ValueError, TypeError):
                continue
        
        # Calculate metrics
        num_quarters = len(quarters)
        beat_rate = (beat_count / num_quarters * 100) if num_quarters > 0 else 0
        avg_surprise = total_surprise / num_quarters if num_quarters > 0 else 0
        
        # Trend analysis (last 4 vs previous 4)
        if len(quarters) >= 8:
            recent_avg = np.mean([q['surprise_pct'] for q in quarters[:4]])
            prior_avg = np.mean([q['surprise_pct'] for q in quarters[4:8]])
            trend = 'IMPROVING' if recent_avg > prior_avg else 'DETERIORATING'
        else:
            trend = 'INSUFFICIENT_DATA'
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'quarters': quarters,
            'summary': {
                'beat_rate': round(beat_rate, 1),
                'miss_rate': round(100 - beat_rate, 1),
                'avg_surprise_pct': round(avg_surprise, 2),
                'consecutive_beats': self._count_consecutive_beats(quarters),
                'trend': trend
            },
            'signal': self._earnings_signal(beat_rate, avg_surprise, trend)
        }
    
    def _count_consecutive_beats(self, quarters: List[Dict]) -> int:
        """Count consecutive beats from most recent"""
        count = 0
        for q in quarters:
            if q.get('beat'):
                count += 1
            else:
                break
        return count
    
    def _earnings_signal(self, beat_rate: float, avg_surprise: float, trend: str) -> Dict:
        """Generate signal from earnings data"""
        score = 0
        factors = []
        
        if beat_rate >= 75:
            score += 2
            factors.append(f"Strong beat rate: {beat_rate}%")
        elif beat_rate >= 60:
            score += 1
            factors.append(f"Good beat rate: {beat_rate}%")
        elif beat_rate < 40:
            score -= 2
            factors.append(f"Poor beat rate: {beat_rate}%")
        
        if avg_surprise > 5:
            score += 2
            factors.append(f"Strong avg surprise: +{avg_surprise}%")
        elif avg_surprise > 0:
            score += 1
        elif avg_surprise < -5:
            score -= 2
            factors.append(f"Negative avg surprise: {avg_surprise}%")
        
        if trend == 'IMPROVING':
            score += 1
            factors.append("Trend improving")
        elif trend == 'DETERIORATING':
            score -= 1
            factors.append("Trend deteriorating")
        
        if score >= 3:
            signal = 'BULLISH'
        elif score >= 1:
            signal = 'NEUTRAL_POSITIVE'
        elif score <= -2:
            signal = 'BEARISH'
        else:
            signal = 'NEUTRAL'
        
        return {
            'signal': signal,
            'score': score,
            'factors': factors
        }
    
    # =========================================================================
    # EARNINGS ESTIMATES & REVISIONS
    # =========================================================================
    
    def get_earnings_estimates(self, symbol: str) -> Dict:
        """
        Get consensus earnings estimates and track revisions
        
        This is KEY for the Equity Strategist - revisions drive prices
        
        Returns:
            Dict with estimates for coming quarters
        """
        print(f"[Earnings] Fetching earnings estimates for {symbol}...")
        
        data = self._api_call('EARNINGS', symbol=symbol)
        
        if not data or 'quarterlyEarnings' not in data:
            return {'error': f'No estimates data for {symbol}'}
        
        # Get overview for forward estimates
        overview = self._api_call('OVERVIEW', symbol=symbol)
        
        quarterly = data.get('quarterlyEarnings', [])
        
        # Most recent reported quarter
        if quarterly:
            last_q = quarterly[0]
            last_reported = float(last_q.get('reportedEPS', 0) or 0)
            last_estimated = float(last_q.get('estimatedEPS', 0) or 0)
        else:
            last_reported = 0
            last_estimated = 0
        
        # Forward estimates from overview
        forward_pe = float(overview.get('ForwardPE', 0) or 0)
        trailing_pe = float(overview.get('TrailingPE', 0) or 0)
        eps_ttm = float(overview.get('EPS', 0) or 0)
        price = float(overview.get('50DayMovingAverage', 0) or 0)
        
        # Calculate implied forward EPS
        if forward_pe > 0 and price > 0:
            implied_forward_eps = price / forward_pe
        else:
            implied_forward_eps = None
        
        # EPS growth rate
        if trailing_pe > 0 and forward_pe > 0:
            # If Forward P/E < Trailing P/E, earnings are expected to grow
            implied_eps_growth = ((trailing_pe / forward_pe) - 1) * 100
        else:
            implied_eps_growth = None
        
        # Revision proxy: Compare current estimate vs actual from recent quarters
        # (Real revision data would need a time series of estimates)
        revisions_proxy = {
            'note': 'Revision tracking requires historical estimate snapshots',
            'current_ttm_eps': eps_ttm,
            'implied_forward_eps': round(implied_forward_eps, 2) if implied_forward_eps else None,
            'implied_eps_growth_pct': round(implied_eps_growth, 1) if implied_eps_growth else None
        }
        
        # Valuation context
        peg = float(overview.get('PEGRatio', 0) or 0)
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'last_quarter': {
                'reported_eps': last_reported,
                'estimated_eps': last_estimated,
                'surprise_pct': round(((last_reported - last_estimated) / abs(last_estimated) * 100) if last_estimated else 0, 2)
            },
            'forward_estimates': {
                'eps_ttm': eps_ttm,
                'implied_forward_eps': round(implied_forward_eps, 2) if implied_forward_eps else None,
                'implied_growth': round(implied_eps_growth, 1) if implied_eps_growth else None,
            },
            'valuation': {
                'forward_pe': forward_pe,
                'trailing_pe': trailing_pe,
                'peg_ratio': peg
            },
            'revisions_proxy': revisions_proxy,
            'signal': self._estimates_signal(forward_pe, peg, implied_eps_growth)
        }
    
    def _estimates_signal(self, forward_pe: float, peg: float, eps_growth: float) -> Dict:
        """Generate signal from estimates"""
        score = 0
        factors = []
        
        # P/E Analysis
        if forward_pe > 0:
            if forward_pe < self.THRESHOLDS['pe_cheap']:
                score += 2
                factors.append(f"Cheap forward P/E: {forward_pe:.1f}")
            elif forward_pe < 20:
                score += 1
                factors.append(f"Reasonable P/E: {forward_pe:.1f}")
            elif forward_pe > self.THRESHOLDS['pe_expensive']:
                score -= 1
                factors.append(f"Expensive P/E: {forward_pe:.1f}")
        
        # PEG Analysis
        if peg > 0:
            if peg < 1.0:
                score += 2
                factors.append(f"Attractive PEG: {peg:.2f}")
            elif peg < self.THRESHOLDS['peg_attractive']:
                score += 1
                factors.append(f"Reasonable PEG: {peg:.2f}")
            elif peg > 2.5:
                score -= 1
                factors.append(f"High PEG: {peg:.2f}")
        
        # Growth
        if eps_growth:
            if eps_growth > 15:
                score += 1
                factors.append(f"Strong EPS growth expected: +{eps_growth:.1f}%")
            elif eps_growth < 0:
                score -= 1
                factors.append(f"EPS decline expected: {eps_growth:.1f}%")
        
        if score >= 3:
            signal = 'BULLISH'
        elif score >= 1:
            signal = 'NEUTRAL_POSITIVE'
        elif score <= -2:
            signal = 'BEARISH'
        else:
            signal = 'NEUTRAL'
        
        return {
            'signal': signal,
            'score': score,
            'factors': factors
        }
    
    # =========================================================================
    # COMPANY OVERVIEW & VALUATION
    # =========================================================================
    
    def get_valuation_metrics(self, symbol: str) -> Dict:
        """
        Get comprehensive valuation metrics
        
        Returns:
            Dict with P/E, PEG, P/B, P/S, EV/EBITDA, etc.
        """
        print(f"[Earnings] Fetching valuation for {symbol}...")
        
        data = self._api_call('OVERVIEW', symbol=symbol)
        
        if not data or 'Symbol' not in data:
            return {'error': f'No overview data for {symbol}'}
        
        # Extract key metrics
        metrics = {
            'symbol': symbol,
            'name': data.get('Name'),
            'sector': data.get('Sector'),
            'industry': data.get('Industry'),
            'market_cap': float(data.get('MarketCapitalization', 0) or 0),
            'timestamp': datetime.now().isoformat(),
            
            'valuation': {
                'trailing_pe': float(data.get('TrailingPE', 0) or 0),
                'forward_pe': float(data.get('ForwardPE', 0) or 0),
                'peg_ratio': float(data.get('PEGRatio', 0) or 0),
                'price_to_book': float(data.get('PriceToBookRatio', 0) or 0),
                'price_to_sales': float(data.get('PriceToSalesRatioTTM', 0) or 0),
                'ev_to_ebitda': float(data.get('EVToEBITDA', 0) or 0),
                'ev_to_revenue': float(data.get('EVToRevenue', 0) or 0),
            },
            
            'profitability': {
                'profit_margin': float(data.get('ProfitMargin', 0) or 0),
                'operating_margin': float(data.get('OperatingMarginTTM', 0) or 0),
                'return_on_equity': float(data.get('ReturnOnEquityTTM', 0) or 0),
                'return_on_assets': float(data.get('ReturnOnAssetsTTM', 0) or 0),
            },
            
            'growth': {
                'revenue_growth_yoy': float(data.get('QuarterlyRevenueGrowthYOY', 0) or 0),
                'earnings_growth_yoy': float(data.get('QuarterlyEarningsGrowthYOY', 0) or 0),
            },
            
            'dividends': {
                'dividend_yield': float(data.get('DividendYield', 0) or 0),
                'dividend_per_share': float(data.get('DividendPerShare', 0) or 0),
                'payout_ratio': float(data.get('PayoutRatio', 0) or 0),
            },
            
            'analyst': {
                'target_price': float(data.get('AnalystTargetPrice', 0) or 0),
                'rating': data.get('AnalystRatingStrongBuy', 'N/A'),
            }
        }
        
        # Calculate valuation score
        metrics['valuation_signal'] = self._valuation_signal(metrics['valuation'], metrics['growth'])
        
        return metrics
    
    def _valuation_signal(self, valuation: Dict, growth: Dict) -> Dict:
        """Score valuation metrics"""
        score = 0
        factors = []
        
        forward_pe = valuation.get('forward_pe', 0)
        peg = valuation.get('peg_ratio', 0)
        ev_ebitda = valuation.get('ev_to_ebitda', 0)
        earnings_growth = growth.get('earnings_growth_yoy', 0)
        
        # Forward P/E
        if 0 < forward_pe < 15:
            score += 2
            factors.append(f"Low forward P/E: {forward_pe:.1f}")
        elif 0 < forward_pe < 20:
            score += 1
        elif forward_pe > 30:
            score -= 1
            factors.append(f"High forward P/E: {forward_pe:.1f}")
        
        # PEG
        if 0 < peg < 1:
            score += 2
            factors.append(f"Excellent PEG: {peg:.2f}")
        elif 0 < peg < 1.5:
            score += 1
        elif peg > 2.5:
            score -= 1
        
        # EV/EBITDA
        if 0 < ev_ebitda < 10:
            score += 1
            factors.append(f"Attractive EV/EBITDA: {ev_ebitda:.1f}")
        elif ev_ebitda > 20:
            score -= 1
        
        # Earnings growth
        if earnings_growth > 20:
            score += 1
            factors.append(f"Strong earnings growth: {earnings_growth:.1f}%")
        elif earnings_growth < -10:
            score -= 1
            factors.append(f"Earnings declining: {earnings_growth:.1f}%")
        
        if score >= 4:
            signal = 'UNDERVALUED'
        elif score >= 2:
            signal = 'FAIRLY_VALUED'
        elif score <= -1:
            signal = 'OVERVALUED'
        else:
            signal = 'NEUTRAL'
        
        return {
            'signal': signal,
            'score': score,
            'factors': factors
        }
    
    # =========================================================================
    # INSIDER TRANSACTIONS (SMART MONEY)
    # =========================================================================
    
    def get_insider_transactions(self, symbol: str) -> Dict:
        """
        Get insider buying/selling activity
        
        Smart money indicator - insiders know their company best
        
        Returns:
            Dict with recent insider transactions
        """
        print(f"[Earnings] Fetching insider transactions for {symbol}...")
        
        data = self._api_call('INSIDER_TRANSACTIONS', symbol=symbol)
        
        if not data or 'data' not in data:
            return {'error': f'No insider data for {symbol}'}
        
        transactions = data.get('data', [])
        
        if not transactions:
            return {'symbol': symbol, 'transactions': [], 'signal': {'signal': 'NO_DATA'}}
        
        # Analyze recent transactions (last 90 days)
        recent = []
        total_bought = 0
        total_sold = 0
        buy_count = 0
        sell_count = 0
        
        cutoff_date = datetime.now() - timedelta(days=90)
        
        for t in transactions[:50]:  # Last 50 transactions
            try:
                trans_date = datetime.strptime(t.get('transaction_date', ''), '%Y-%m-%d')
                if trans_date < cutoff_date:
                    continue
                    
                shares = float(t.get('shares', 0) or 0)
                acquisition = t.get('acquisition_or_disposition', '')
                
                recent.append({
                    'date': t.get('transaction_date'),
                    'executive': t.get('executive'),
                    'title': t.get('executive_title'),
                    'type': acquisition,
                    'shares': shares,
                    'value': t.get('value'),
                    'security_type': t.get('security_type')
                })
                
                if acquisition == 'A':  # Acquisition (buy)
                    total_bought += shares
                    buy_count += 1
                elif acquisition == 'D':  # Disposition (sell)
                    total_sold += shares
                    sell_count += 1
                    
            except (ValueError, TypeError):
                continue
        
        # Calculate net activity
        net_shares = total_bought - total_sold
        total_transactions = buy_count + sell_count
        
        if total_transactions > 0:
            buy_ratio = buy_count / total_transactions
        else:
            buy_ratio = 0.5
        
        # Generate signal
        if buy_ratio > self.THRESHOLDS['insider_bullish'] and net_shares > 0:
            signal = 'BULLISH'
            interpretation = 'Net insider buying - insiders are confident'
        elif buy_ratio < 0.3 and net_shares < 0:
            signal = 'BEARISH'
            interpretation = 'Net insider selling - potential concern'
        else:
            signal = 'NEUTRAL'
            interpretation = 'Mixed insider activity'
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'period': '90_days',
            'summary': {
                'buy_count': buy_count,
                'sell_count': sell_count,
                'total_bought_shares': total_bought,
                'total_sold_shares': total_sold,
                'net_shares': net_shares,
                'buy_ratio': round(buy_ratio, 2)
            },
            'recent_transactions': recent[:10],  # Top 10
            'signal': {
                'signal': signal,
                'interpretation': interpretation,
                'buy_ratio': round(buy_ratio, 2)
            }
        }
    
    # =========================================================================
    # EARNINGS CALENDAR
    # =========================================================================
    
    def get_earnings_calendar(self, horizon: str = '3month') -> Dict:
        """
        Get upcoming earnings dates
        
        Args:
            horizon: '3month' or '6month' or '12month'
            
        Returns:
            Dict with upcoming earnings
        """
        print(f"[Earnings] Fetching earnings calendar...")
        
        data = self._api_call('EARNINGS_CALENDAR', horizon=horizon)
        
        # This returns CSV, need to handle differently
        # For now, return placeholder
        return {
            'note': 'Earnings calendar returns CSV format',
            'horizon': horizon,
            'url': f"{BASE_URL}?function=EARNINGS_CALENDAR&horizon={horizon}&apikey=demo"
        }
    
    # =========================================================================
    # COMPREHENSIVE SINGLE STOCK REPORT
    # =========================================================================
    
    def get_earnings_report(self, symbol: str) -> Dict:
        """
        Generate comprehensive earnings report for a single stock
        
        Returns:
            Complete earnings analysis
        """
        print(f"\n{'='*70}")
        print(f"EARNINGS REPORT: {symbol}")
        print('='*70)
        
        report = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
        }
        
        # 1. Earnings History
        history = self.get_earnings_history(symbol)
        report['earnings_history'] = history
        
        # 2. Estimates & Valuation
        estimates = self.get_earnings_estimates(symbol)
        report['estimates'] = estimates
        
        # 3. Full Valuation
        valuation = self.get_valuation_metrics(symbol)
        report['valuation'] = valuation
        
        # 4. Insider Activity
        insiders = self.get_insider_transactions(symbol)
        report['insider_activity'] = insiders
        
        # 5. Composite Score
        report['composite'] = self._composite_score(history, estimates, valuation, insiders)
        
        return report
    
    def _composite_score(self, history: Dict, estimates: Dict, valuation: Dict, insiders: Dict) -> Dict:
        """Calculate composite earnings score"""
        score = 0
        factors = []
        
        # History component (max 3 points)
        if 'signal' in history and 'score' in history['signal']:
            hist_score = history['signal']['score']
            score += min(hist_score, 3)
            if hist_score >= 2:
                factors.append("Strong earnings track record")
        
        # Estimates component (max 3 points)
        if 'signal' in estimates and 'score' in estimates['signal']:
            est_score = estimates['signal']['score']
            score += min(est_score, 3)
            if est_score >= 2:
                factors.append("Attractive forward estimates")
        
        # Valuation component (max 3 points)
        if 'valuation_signal' in valuation and 'score' in valuation['valuation_signal']:
            val_score = valuation['valuation_signal']['score']
            score += min(val_score, 3)
            if val_score >= 2:
                factors.append("Attractive valuation")
        
        # Insider component (max 1 point)
        if 'signal' in insiders:
            if insiders['signal'].get('signal') == 'BULLISH':
                score += 1
                factors.append("Insider buying")
            elif insiders['signal'].get('signal') == 'BEARISH':
                score -= 1
                factors.append("Insider selling")
        
        # Determine overall signal
        if score >= 7:
            signal = 'STRONG_BUY'
            recommendation = 'Excellent earnings quality + attractive valuation'
        elif score >= 4:
            signal = 'BUY'
            recommendation = 'Good earnings quality and reasonable valuation'
        elif score >= 1:
            signal = 'HOLD'
            recommendation = 'Mixed signals - monitor for changes'
        elif score >= -2:
            signal = 'UNDERPERFORM'
            recommendation = 'Weak earnings or expensive valuation'
        else:
            signal = 'SELL'
            recommendation = 'Poor earnings quality and/or overvalued'
        
        return {
            'composite_score': score,
            'max_score': 10,
            'signal': signal,
            'recommendation': recommendation,
            'key_factors': factors
        }
    
    # =========================================================================
    # SECTOR ANALYSIS
    # =========================================================================
    
    def get_sector_earnings_momentum(self, sectors: List[str] = None) -> Dict:
        """
        Analyze earnings momentum across sectors
        
        Returns:
            Dict with sector-level earnings analysis
        """
        print("\n" + "="*70)
        print("SECTOR EARNINGS MOMENTUM")
        print("="*70)
        
        if sectors is None:
            sectors = list(self.SECTOR_TICKERS.keys())
        
        sector_results = {}
        
        for sector in sectors:
            tickers = self.SECTOR_TICKERS.get(sector, [])[:3]  # Top 3 per sector to save API calls
            
            if not tickers:
                continue
            
            print(f"\n[{sector}]")
            
            sector_data = {
                'tickers_analyzed': tickers,
                'avg_beat_rate': 0,
                'avg_surprise': 0,
                'avg_forward_pe': 0,
                'signals': []
            }
            
            beat_rates = []
            surprises = []
            forward_pes = []
            
            for ticker in tickers:
                try:
                    # Get earnings history
                    history = self.get_earnings_history(ticker)
                    if 'summary' in history:
                        beat_rates.append(history['summary']['beat_rate'])
                        surprises.append(history['summary']['avg_surprise_pct'])
                    
                    # Get estimates for forward P/E
                    estimates = self.get_earnings_estimates(ticker)
                    if 'valuation' in estimates:
                        fpe = estimates['valuation'].get('forward_pe', 0)
                        if fpe > 0:
                            forward_pes.append(fpe)
                    
                    # Collect signals
                    if 'signal' in history:
                        sector_data['signals'].append({
                            'ticker': ticker,
                            'signal': history['signal']['signal']
                        })
                        
                except Exception as e:
                    print(f"  ✗ Error with {ticker}: {e}")
                    continue
            
            # Calculate averages
            if beat_rates:
                sector_data['avg_beat_rate'] = round(np.mean(beat_rates), 1)
            if surprises:
                sector_data['avg_surprise'] = round(np.mean(surprises), 2)
            if forward_pes:
                sector_data['avg_forward_pe'] = round(np.mean(forward_pes), 1)
            
            # Sector signal
            bullish_count = sum(1 for s in sector_data['signals'] if 'BULLISH' in s['signal'])
            if bullish_count >= 2:
                sector_data['sector_signal'] = 'BULLISH'
            elif bullish_count == 0:
                sector_data['sector_signal'] = 'BEARISH'
            else:
                sector_data['sector_signal'] = 'NEUTRAL'
            
            sector_results[sector] = sector_data
            print(f"  Beat Rate: {sector_data['avg_beat_rate']}% | Surprise: {sector_data['avg_surprise']}% | Signal: {sector_data['sector_signal']}")
        
        # Rank sectors
        ranked = sorted(
            sector_results.items(),
            key=lambda x: (x[1]['avg_beat_rate'] + x[1]['avg_surprise']),
            reverse=True
        )
        
        return {
            'timestamp': datetime.now().isoformat(),
            'sectors': sector_results,
            'ranking': [{'sector': s[0], 'score': s[1]['avg_beat_rate'] + s[1]['avg_surprise']} for s in ranked],
            'top_sectors': [s[0] for s in ranked[:3]],
            'bottom_sectors': [s[0] for s in ranked[-3:]]
        }
    
    # =========================================================================
    # FULL DASHBOARD
    # =========================================================================
    
    def get_earnings_dashboard(self, symbols: List[str] = None) -> Dict:
        """
        Generate comprehensive earnings dashboard
        
        Args:
            symbols: List of symbols to analyze (default: major indices components)
            
        Returns:
            Complete earnings dashboard
        """
        if symbols is None:
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'JPM', 'JNJ', 'XOM', 'PG']
        
        print("\n" + "="*70)
        print("EARNINGS ANALYTICS DASHBOARD")
        print("="*70)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'symbols_analyzed': symbols,
            'reports': {},
            'summary': {}
        }
        
        # Individual reports
        bullish_count = 0
        bearish_count = 0
        
        for symbol in symbols:
            try:
                report = self.get_earnings_report(symbol)
                dashboard['reports'][symbol] = report
                
                if 'composite' in report:
                    sig = report['composite']['signal']
                    if sig in ['STRONG_BUY', 'BUY']:
                        bullish_count += 1
                    elif sig in ['SELL', 'UNDERPERFORM']:
                        bearish_count += 1
                        
            except Exception as e:
                print(f"[Earnings] ✗ Error analyzing {symbol}: {e}")
                continue
        
        # Summary
        total = len(symbols)
        dashboard['summary'] = {
            'bullish_pct': round(bullish_count / total * 100, 1) if total > 0 else 0,
            'bearish_pct': round(bearish_count / total * 100, 1) if total > 0 else 0,
            'market_breadth': 'POSITIVE' if bullish_count > bearish_count else 'NEGATIVE' if bearish_count > bullish_count else 'NEUTRAL',
            'top_picks': self._get_top_picks(dashboard['reports']),
            'avoid': self._get_avoid_list(dashboard['reports'])
        }
        
        return dashboard
    
    def _get_top_picks(self, reports: Dict) -> List[str]:
        """Get top picks based on composite scores"""
        scored = []
        for symbol, report in reports.items():
            if 'composite' in report:
                scored.append((symbol, report['composite']['composite_score']))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:3]]
    
    def _get_avoid_list(self, reports: Dict) -> List[str]:
        """Get avoid list based on composite scores"""
        scored = []
        for symbol, report in reports.items():
            if 'composite' in report:
                scored.append((symbol, report['composite']['composite_score']))
        
        scored.sort(key=lambda x: x[1])
        return [s[0] for s in scored[:3] if s[1] < 0]


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    analytics = EarningsAnalytics()
    
    # Test single stock
    print("\n" + "="*70)
    print("TESTING: AAPL")
    print("="*70)
    
    report = analytics.get_earnings_report('AAPL')
    
    if 'composite' in report:
        print(f"\nComposite Score: {report['composite']['composite_score']}/10")
        print(f"Signal: {report['composite']['signal']}")
        print(f"Recommendation: {report['composite']['recommendation']}")
        print("Key Factors:")
        for f in report['composite']['key_factors']:
            print(f"  • {f}")

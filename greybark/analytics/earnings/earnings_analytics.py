"""
Grey Bark - Earnings Analytics
Comprehensive earnings analysis using AlphaVantage Premium APIs

Features:
- Earnings History & Surprises
- Analyst Estimates & Revisions
- Forward P/E & Implied Growth
- Insider Transactions (Smart Money)
- Valuation Analysis
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests

# Import config
try:
    from ...config import config
    ALPHAVANTAGE_API_KEY = config.alphavantage.api_key
except (ImportError, AttributeError):
    ALPHAVANTAGE_API_KEY = os.environ.get('ALPHAVANTAGE_API_KEY', '')


class EarningsAnalytics:
    """
    Comprehensive Earnings Analysis for Greybark Research
    
    Features:
    - Earnings History (actual vs estimates, surprises)
    - Analyst Estimates (consensus, revisions)
    - Implied Growth from P/E ratios
    - Insider Transactions (smart money signals)
    - Valuation metrics (P/E, Forward P/E, PEG)
    
    Usage:
        analytics = EarningsAnalytics()
        
        # Full earnings report for a stock
        report = analytics.get_earnings_report('AAPL')
        
        # Implied growth analysis
        growth = analytics.get_implied_growth('AAPL')
        
        # Insider activity
        insiders = analytics.get_insider_activity('AAPL')
        
        # Sector-wide analysis
        sector = analytics.get_sector_earnings(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])
    """
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    # S&P 500 sector ETFs for benchmarking
    SECTOR_ETFS = {
        'technology': 'XLK',
        'healthcare': 'XLV',
        'financials': 'XLF',
        'consumer_discretionary': 'XLY',
        'consumer_staples': 'XLP',
        'industrials': 'XLI',
        'energy': 'XLE',
        'materials': 'XLB',
        'utilities': 'XLU',
        'real_estate': 'XLRE',
        'communication': 'XLC'
    }
    
    def __init__(self, api_key: str = None):
        """Initialize with AlphaVantage API key"""
        self.api_key = api_key or ALPHAVANTAGE_API_KEY
        print("[Earnings] ✓ EarningsAnalytics initialized")
    
    def _make_request(self, params: Dict) -> Dict:
        """Make API request to AlphaVantage"""
        params['apikey'] = self.api_key
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Earnings] ✗ API Error: {e}")
            return {}

    def _make_csv_request(self, params: Dict) -> List[Dict]:
        """Make API request that returns CSV (e.g., EARNINGS_CALENDAR)."""
        import csv
        import io
        params['apikey'] = self.api_key
        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            reader = csv.DictReader(io.StringIO(response.text))
            return list(reader)
        except Exception as e:
            print(f"[Earnings] ✗ CSV API Error: {e}")
            return []
    
    # =========================================================================
    # EARNINGS HISTORY & SURPRISES
    # =========================================================================
    
    def get_earnings_history(self, symbol: str) -> Dict:
        """
        Get quarterly earnings history with surprises
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            
        Returns:
            Dict with earnings history and surprise analysis
        """
        print(f"[Earnings] Fetching earnings history for {symbol}...")
        
        data = self._make_request({
            'function': 'EARNINGS',
            'symbol': symbol
        })
        
        if not data or 'quarterlyEarnings' not in data:
            return {'error': f'No earnings data for {symbol}'}
        
        quarterly = data.get('quarterlyEarnings', [])
        annual = data.get('annualEarnings', [])
        
        # Process quarterly earnings
        earnings_list = []
        beat_count = 0
        miss_count = 0
        total_surprise_pct = 0
        
        for q in quarterly[:12]:  # Last 12 quarters (3 years)
            reported = float(q.get('reportedEPS', 0) or 0)
            estimated = float(q.get('estimatedEPS', 0) or 0)
            surprise = float(q.get('surprise', 0) or 0)
            surprise_pct = float(q.get('surprisePercentage', 0) or 0)
            
            if estimated != 0:
                if reported > estimated:
                    beat_count += 1
                elif reported < estimated:
                    miss_count += 1
            
            total_surprise_pct += surprise_pct
            
            earnings_list.append({
                'date': q.get('fiscalDateEnding'),
                'reported_eps': reported,
                'estimated_eps': estimated,
                'surprise': surprise,
                'surprise_pct': surprise_pct,
                'beat': reported > estimated if estimated else None
            })
        
        # Calculate metrics
        beat_rate = beat_count / len(earnings_list) * 100 if earnings_list else 0
        avg_surprise = total_surprise_pct / len(earnings_list) if earnings_list else 0
        
        # EPS growth (YoY)
        if len(annual) >= 2:
            current_eps = float(annual[0].get('reportedEPS', 0) or 0)
            prior_eps = float(annual[1].get('reportedEPS', 0) or 0)
            eps_growth = ((current_eps - prior_eps) / abs(prior_eps) * 100) if prior_eps != 0 else 0
        else:
            eps_growth = None
            current_eps = None
        
        # Interpretation
        if beat_rate >= 75:
            track_record = 'EXCELLENT'
            note = 'Consistently beats estimates - management guidance conservative'
        elif beat_rate >= 50:
            track_record = 'GOOD'
            note = 'Generally beats estimates'
        elif beat_rate >= 25:
            track_record = 'MIXED'
            note = 'Inconsistent earnings delivery'
        else:
            track_record = 'POOR'
            note = 'Frequently misses estimates - execution concerns'
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'quarterly_earnings': earnings_list,
            'annual_eps': {
                'current': current_eps,
                'yoy_growth_pct': round(eps_growth, 2) if eps_growth else None
            },
            'track_record': {
                'beat_rate_pct': round(beat_rate, 1),
                'beats': beat_count,
                'misses': miss_count,
                'avg_surprise_pct': round(avg_surprise, 2),
                'assessment': track_record,
                'note': note
            }
        }
    
    # =========================================================================
    # ANALYST ESTIMATES & REVISIONS
    # =========================================================================
    
    def get_analyst_estimates(self, symbol: str) -> Dict:
        """
        Get analyst earnings estimates and track revisions
        
        This is KEY for the Equity Strategist's request:
        - Current consensus EPS estimates
        - Estimate revisions (upgrades vs downgrades)
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with analyst estimates and revision trends
        """
        print(f"[Earnings] Fetching analyst estimates for {symbol}...")
        
        data = self._make_request({
            'function': 'EARNINGS_ESTIMATES',  # AlphaVantage Premium
            'symbol': symbol
        })
        
        # EARNINGS_ESTIMATES returns data under 'estimates' key (not 'quarterlyEstimates')
        if not data or 'estimates' not in data:
            # Use OVERVIEW as fallback
            overview = self._make_request({
                'function': 'OVERVIEW',
                'symbol': symbol
            })

            if overview and 'ForwardPE' in overview:
                return self._parse_overview_estimates(symbol, overview)
            return {'error': f'No estimate data for {symbol}'}

        estimates_raw = data.get('estimates', [])

        # Parse by horizon for structured output
        # AV field names use snake_case: eps_estimate_average, eps_estimate_revision_up_trailing_30_days, etc.
        by_horizon = {}
        for est in estimates_raw:
            horizon = est.get('date', 'unknown')
            by_horizon[horizon] = {
                'date': est.get('date'),
                'horizon': est.get('horizon'),
                'eps_avg': self._safe_av_float(est.get('eps_estimate_average')),
                'eps_high': self._safe_av_float(est.get('eps_estimate_high')),
                'eps_low': self._safe_av_float(est.get('eps_estimate_low')),
                'num_analysts': self._safe_av_int(est.get('eps_estimate_analyst_count')),
                'revenue_avg': self._safe_av_float(est.get('revenue_estimate_average')),
                'revenue_high': self._safe_av_float(est.get('revenue_estimate_high')),
                'revenue_low': self._safe_av_float(est.get('revenue_estimate_low')),
                # Revision data (the most valuable part)
                'eps_7d_ago': self._safe_av_float(est.get('eps_estimate_average_7_days_ago')),
                'eps_30d_ago': self._safe_av_float(est.get('eps_estimate_average_30_days_ago')),
                'eps_60d_ago': self._safe_av_float(est.get('eps_estimate_average_60_days_ago')),
                'eps_90d_ago': self._safe_av_float(est.get('eps_estimate_average_90_days_ago')),
                'revision_up_7d': self._safe_av_int(est.get('eps_estimate_revision_up_trailing_7_days')),
                'revision_down_7d': self._safe_av_int(est.get('eps_estimate_revision_down_trailing_7_days')),
                'revision_up_30d': self._safe_av_int(est.get('eps_estimate_revision_up_trailing_30_days')),
                'revision_down_30d': self._safe_av_int(est.get('eps_estimate_revision_down_trailing_30_days')),
            }

        # Build revision summary from real data
        revision_summary = self._calculate_revision_summary_from_estimates(by_horizon)

        # Extract forward EPS — prefer "next fiscal year", then "current fiscal year"
        forward_eps = None
        for target_horizon in ['next fiscal year', 'current fiscal year']:
            for est in estimates_raw:
                if est.get('horizon') == target_horizon:
                    eps_val = self._safe_av_float(est.get('eps_estimate_average'))
                    if eps_val and eps_val > 0:
                        forward_eps = eps_val
                        break
            if forward_eps:
                break

        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'by_horizon': by_horizon,
            'forward_eps': forward_eps,
            'revision_summary': revision_summary,
            'source': 'EARNINGS_ESTIMATES',
        }
    
    def _parse_overview_estimates(self, symbol: str, overview: Dict) -> Dict:
        """Parse estimates from OVERVIEW endpoint (fallback)"""
        
        forward_pe = float(overview.get('ForwardPE', 0) or 0)
        trailing_pe = float(overview.get('TrailingPE', 0) or 0)
        eps = float(overview.get('EPS', 0) or 0)
        forward_eps = float(overview.get('ForwardEPS', 0) or 0) if 'ForwardEPS' in overview else None
        
        # If no forward EPS, estimate from forward P/E
        if not forward_eps and forward_pe > 0:
            price = float(overview.get('50DayMovingAverage', 0) or 0)
            if price > 0:
                forward_eps = price / forward_pe
        
        # Implied EPS growth
        if eps > 0 and forward_eps:
            implied_eps_growth = ((forward_eps - eps) / abs(eps)) * 100
        else:
            implied_eps_growth = None
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'estimates': {
                'trailing_eps': eps,
                'forward_eps': round(forward_eps, 2) if forward_eps else None,
                'implied_eps_growth_pct': round(implied_eps_growth, 2) if implied_eps_growth else None
            },
            'source': 'OVERVIEW (fallback)'
        }
    
    def _safe_av_float(self, val) -> Optional[float]:
        """Safely parse AlphaVantage value to float."""
        if val is None or val == '' or val == 'None' or val == '-':
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _safe_av_int(self, val) -> int:
        """Safely parse AlphaVantage value to int."""
        if val is None or val == '' or val == 'None' or val == '-':
            return 0
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    def _calculate_revision_summary(self, estimates: List) -> Dict:
        """Calculate estimate revision summary (legacy fallback)."""
        if not estimates:
            return {'status': 'NO_DATA'}
        return {'status': 'NO_DATA', 'note': 'Use EARNINGS_ESTIMATES for real revisions'}

    def _calculate_revision_summary_from_estimates(self, by_horizon: Dict) -> Dict:
        """Calculate real revision summary from EARNINGS_ESTIMATES data."""
        if not by_horizon:
            return {'status': 'NO_DATA'}

        total_up_7d = 0
        total_down_7d = 0
        total_up_30d = 0
        total_down_30d = 0
        eps_changes_30d = []

        for horizon, est in by_horizon.items():
            total_up_7d += est.get('revision_up_7d', 0)
            total_down_7d += est.get('revision_down_7d', 0)
            total_up_30d += est.get('revision_up_30d', 0)
            total_down_30d += est.get('revision_down_30d', 0)

            # Calculate EPS change vs 30 days ago
            eps_now = est.get('eps_avg')
            eps_30d = est.get('eps_30d_ago')
            if eps_now is not None and eps_30d is not None and eps_30d != 0:
                pct_change = ((eps_now - eps_30d) / abs(eps_30d)) * 100
                eps_changes_30d.append(pct_change)

        net_7d = total_up_7d - total_down_7d
        net_30d = total_up_30d - total_down_30d
        total_revisions_30d = total_up_30d + total_down_30d

        if total_revisions_30d > 0:
            upgrade_pct = round(total_up_30d / total_revisions_30d * 100, 1)
        else:
            upgrade_pct = 50.0

        avg_eps_change_30d = round(sum(eps_changes_30d) / len(eps_changes_30d), 2) if eps_changes_30d else None

        # Determine status
        if upgrade_pct >= 65:
            status = 'STRONG_UPGRADE'
        elif upgrade_pct >= 55:
            status = 'UPGRADING'
        elif upgrade_pct >= 45:
            status = 'STABLE'
        elif upgrade_pct >= 35:
            status = 'DOWNGRADING'
        else:
            status = 'STRONG_DOWNGRADE'

        return {
            'status': status,
            'upgrades_7d': total_up_7d,
            'downgrades_7d': total_down_7d,
            'net_7d': net_7d,
            'upgrades_30d': total_up_30d,
            'downgrades_30d': total_down_30d,
            'net_30d': net_30d,
            'upgrade_pct_30d': upgrade_pct,
            'avg_eps_change_30d_pct': avg_eps_change_30d,
        }
    
    # =========================================================================
    # IMPLIED GROWTH FROM P/E
    # =========================================================================
    
    def get_implied_growth(self, symbol: str) -> Dict:
        """
        Calculate implied earnings growth from P/E ratios
        
        KEY INSIGHT for Pablo:
        - If Trailing P/E = 25 and Forward P/E = 20
        - Implied EPS Growth = (25/20) - 1 = 25%
        
        Also uses PEG ratio:
        - PEG = P/E / Growth
        - Growth = P/E / PEG
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with implied growth analysis
        """
        print(f"[Earnings] Calculating implied growth for {symbol}...")
        
        overview = self._make_request({
            'function': 'OVERVIEW',
            'symbol': symbol
        })
        
        if not overview or 'TrailingPE' not in overview:
            return {'error': f'No valuation data for {symbol}'}
        
        # Extract metrics
        trailing_pe = float(overview.get('TrailingPE', 0) or 0)
        forward_pe = float(overview.get('ForwardPE', 0) or 0)
        peg_ratio = float(overview.get('PEGRatio', 0) or 0)
        eps = float(overview.get('EPS', 0) or 0)
        price = float(overview.get('50DayMovingAverage', 0) or 0)
        
        # Calculate implied growth metrics
        implied_growth = {}
        
        # Method 1: From P/E compression/expansion
        # Forward P/E < Trailing P/E implies growth
        if trailing_pe > 0 and forward_pe > 0:
            pe_implied_growth = ((trailing_pe / forward_pe) - 1) * 100
            implied_growth['from_pe_ratio'] = {
                'trailing_pe': round(trailing_pe, 2),
                'forward_pe': round(forward_pe, 2),
                'implied_eps_growth_pct': round(pe_implied_growth, 2),
                'interpretation': self._interpret_pe_growth(pe_implied_growth)
            }
        
        # Method 2: From PEG ratio
        # PEG = P/E / Growth => Growth = P/E / PEG
        if peg_ratio > 0 and trailing_pe > 0:
            peg_implied_growth = trailing_pe / peg_ratio
            implied_growth['from_peg'] = {
                'peg_ratio': round(peg_ratio, 2),
                'implied_growth_pct': round(peg_implied_growth, 2),
                'peg_assessment': self._assess_peg(peg_ratio)
            }
        
        # Method 3: Required growth to justify current P/E
        # Assuming fair P/E = 15-20 for market
        market_pe = 20  # S&P 500 average
        if trailing_pe > 0:
            premium_pct = ((trailing_pe / market_pe) - 1) * 100
            required_growth = premium_pct * 0.5  # Rule of thumb: 50% of premium
            implied_growth['vs_market'] = {
                'stock_pe': round(trailing_pe, 2),
                'market_pe': market_pe,
                'premium_pct': round(premium_pct, 2),
                'required_growth_to_justify': round(required_growth, 2),
                'interpretation': self._interpret_premium(premium_pct)
            }
        
        # Overall assessment
        avg_implied_growth = 0
        count = 0
        if 'from_pe_ratio' in implied_growth:
            avg_implied_growth += implied_growth['from_pe_ratio']['implied_eps_growth_pct']
            count += 1
        if 'from_peg' in implied_growth:
            avg_implied_growth += implied_growth['from_peg']['implied_growth_pct']
            count += 1
        
        avg_implied_growth = avg_implied_growth / count if count > 0 else 0
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'current_metrics': {
                'price': round(price, 2) if price else None,
                'eps': round(eps, 2) if eps else None,
                'trailing_pe': round(trailing_pe, 2) if trailing_pe else None,
                'forward_pe': round(forward_pe, 2) if forward_pe else None,
                'peg_ratio': round(peg_ratio, 2) if peg_ratio else None
            },
            'implied_growth': implied_growth,
            'summary': {
                'avg_implied_growth_pct': round(avg_implied_growth, 2),
                'growth_expectation': self._categorize_growth(avg_implied_growth),
                'valuation_signal': self._valuation_signal(trailing_pe, forward_pe, peg_ratio)
            }
        }
    
    def _interpret_pe_growth(self, growth: float) -> str:
        """Interpret PE-implied growth"""
        if growth > 30:
            return "HIGH GROWTH expected - stock priced for strong earnings acceleration"
        elif growth > 15:
            return "MODERATE GROWTH expected - reasonable expectations"
        elif growth > 5:
            return "LOW GROWTH expected - modest earnings improvement"
        elif growth > 0:
            return "MINIMAL GROWTH expected - near-flat earnings"
        else:
            return "NEGATIVE GROWTH expected - earnings decline priced in"
    
    def _assess_peg(self, peg: float) -> str:
        """Assess PEG ratio"""
        if peg < 1:
            return "UNDERVALUED - Growth not fully priced in"
        elif peg < 1.5:
            return "FAIRLY VALUED - Price reflects growth"
        elif peg < 2:
            return "SLIGHTLY EXPENSIVE - Premium for quality/growth"
        else:
            return "EXPENSIVE - High expectations embedded"
    
    def _interpret_premium(self, premium: float) -> str:
        """Interpret P/E premium vs market"""
        if premium > 50:
            return "SIGNIFICANT PREMIUM - Must deliver exceptional growth"
        elif premium > 20:
            return "MODERATE PREMIUM - Above-average growth expected"
        elif premium > 0:
            return "SLIGHT PREMIUM - Modest outperformance needed"
        elif premium > -20:
            return "IN-LINE with market"
        else:
            return "DISCOUNT - Low expectations or value play"
    
    def _categorize_growth(self, growth: float) -> str:
        """Categorize growth expectation"""
        if growth > 25:
            return "HIGH_GROWTH"
        elif growth > 10:
            return "GROWTH"
        elif growth > 0:
            return "SLOW_GROWTH"
        else:
            return "DECLINE"
    
    def _valuation_signal(self, trailing_pe: float, forward_pe: float, peg: float) -> str:
        """Generate valuation signal"""
        signals = []
        
        if forward_pe > 0 and forward_pe < trailing_pe:
            signals.append("PE_COMPRESSION_POSITIVE")
        
        if peg > 0 and peg < 1:
            signals.append("PEG_ATTRACTIVE")
        elif peg > 2:
            signals.append("PEG_EXPENSIVE")
        
        if trailing_pe > 30:
            signals.append("HIGH_PE_RISK")
        elif trailing_pe < 15:
            signals.append("LOW_PE_VALUE")
        
        if not signals:
            return "NEUTRAL"
        return ", ".join(signals)
    
    # =========================================================================
    # INSIDER TRANSACTIONS (SMART MONEY)
    # =========================================================================
    
    def get_insider_activity(self, symbol: str) -> Dict:
        """
        Get insider transaction activity
        
        Smart Money Signal:
        - Insiders BUY = Bullish (they know the company)
        - Insiders SELL = Can be neutral (diversification) or bearish
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with insider activity analysis
        """
        print(f"[Earnings] Fetching insider transactions for {symbol}...")
        
        data = self._make_request({
            'function': 'INSIDER_TRANSACTIONS',
            'symbol': symbol
        })
        
        if not data or 'data' not in data:
            return {'error': f'No insider data for {symbol}', 'note': 'Requires AlphaVantage Premium'}
        
        transactions = data.get('data', [])
        
        # Analyze recent transactions (last 90 days)
        recent = []
        total_bought = 0
        total_sold = 0
        buy_count = 0
        sell_count = 0
        
        cutoff_date = datetime.now() - timedelta(days=90)
        
        for tx in transactions[:50]:  # Last 50 transactions
            tx_date = datetime.strptime(tx.get('transactionDate', '2000-01-01'), '%Y-%m-%d')
            
            if tx_date >= cutoff_date:
                shares = int(tx.get('shares', 0) or 0)
                acquisition = tx.get('acquisitionOrDisposition', '')
                
                if acquisition == 'A':  # Acquisition (Buy)
                    total_bought += shares
                    buy_count += 1
                elif acquisition == 'D':  # Disposition (Sell)
                    total_sold += shares
                    sell_count += 1
                
                recent.append({
                    'date': tx.get('transactionDate'),
                    'insider': tx.get('insiderName', 'Unknown'),
                    'title': tx.get('insiderTitle', 'Unknown'),
                    'type': 'BUY' if acquisition == 'A' else 'SELL',
                    'shares': shares,
                    'value': float(tx.get('value', 0) or 0)
                })
        
        # Calculate net activity
        net_shares = total_bought - total_sold
        buy_sell_ratio = buy_count / sell_count if sell_count > 0 else float('inf') if buy_count > 0 else 0
        
        # Interpret
        if net_shares > 0 and buy_sell_ratio > 1:
            signal = 'BULLISH'
            interpretation = 'Net insider buying - smart money accumulating'
        elif net_shares < 0 and buy_sell_ratio < 0.5:
            signal = 'BEARISH'
            interpretation = 'Net insider selling - caution warranted'
        elif buy_count > 0 and sell_count > 0:
            signal = 'MIXED'
            interpretation = 'Mixed insider activity'
        else:
            signal = 'NEUTRAL'
            interpretation = 'Limited insider activity'
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'period': '90 days',
            'summary': {
                'total_bought_shares': total_bought,
                'total_sold_shares': total_sold,
                'net_shares': net_shares,
                'buy_transactions': buy_count,
                'sell_transactions': sell_count,
                'buy_sell_ratio': round(buy_sell_ratio, 2) if buy_sell_ratio != float('inf') else 'INF'
            },
            'signal': signal,
            'interpretation': interpretation,
            'recent_transactions': recent[:10]  # Top 10 recent
        }
    
    # =========================================================================
    # INCOME STATEMENT & FUNDAMENTALS
    # =========================================================================

    def get_income_statement(self, symbol: str) -> Dict:
        """
        Fetch quarterly income statement from AV INCOME_STATEMENT endpoint.
        Calculates margins and YoY revenue growth.

        Args:
            symbol: Stock ticker

        Returns:
            Dict with margins, revenue, and growth metrics
        """
        print(f"[Earnings] Fetching income statement for {symbol}...")

        data = self._make_request({
            'function': 'INCOME_STATEMENT',
            'symbol': symbol
        })

        if not data or 'quarterlyReports' not in data:
            return {'error': f'No income data for {symbol}'}

        quarterly = data['quarterlyReports'][:8]  # Last 8 quarters (2 years)
        if not quarterly:
            return {'error': f'Empty quarterly reports for {symbol}'}

        latest = quarterly[0]
        revenue = self._safe_av_float(latest.get('totalRevenue')) or 0
        gross_profit = self._safe_av_float(latest.get('grossProfit')) or 0
        op_income = self._safe_av_float(latest.get('operatingIncome')) or 0
        net_income = self._safe_av_float(latest.get('netIncome')) or 0
        ebitda = self._safe_av_float(latest.get('ebitda')) or 0

        # YoY revenue growth (Q0 vs Q4 if available)
        revenue_growth_yoy = None
        if len(quarterly) >= 5:
            prev_year_rev = self._safe_av_float(quarterly[4].get('totalRevenue'))
            if prev_year_rev and prev_year_rev > 0 and revenue > 0:
                revenue_growth_yoy = round(((revenue - prev_year_rev) / prev_year_rev) * 100, 1)

        return {
            'symbol': symbol,
            'fiscal_date': latest.get('fiscalDateEnding'),
            'gross_margin': round(gross_profit / revenue * 100, 1) if revenue else None,
            'operating_margin': round(op_income / revenue * 100, 1) if revenue else None,
            'net_margin': round(net_income / revenue * 100, 1) if revenue else None,
            'ebitda_margin': round(ebitda / revenue * 100, 1) if revenue and ebitda else None,
            'revenue': revenue,
            'revenue_growth_yoy': revenue_growth_yoy,
        }

    def get_fundamentals_summary(self, symbol: str) -> Dict:
        """
        Combine OVERVIEW endpoint for profitability + valuation + analyst data.

        Args:
            symbol: Stock ticker

        Returns:
            Dict with ROE, margins, analyst target, ratings
        """
        print(f"[Earnings] Fetching fundamentals summary for {symbol}...")

        overview = self._make_request({
            'function': 'OVERVIEW',
            'symbol': symbol
        })

        if not overview or 'Symbol' not in overview:
            return {'error': f'No overview data for {symbol}'}

        # Analyst ratings breakdown
        strong_buy = self._safe_av_int(overview.get('AnalystRatingStrongBuy'))
        buy = self._safe_av_int(overview.get('AnalystRatingBuy'))
        hold = self._safe_av_int(overview.get('AnalystRatingHold'))
        sell = self._safe_av_int(overview.get('AnalystRatingSell'))
        strong_sell = self._safe_av_int(overview.get('AnalystRatingStrongSell'))
        total_ratings = strong_buy + buy + hold + sell + strong_sell

        return {
            'symbol': symbol,
            'profit_margin': self._safe_av_float(overview.get('ProfitMargin')),
            'operating_margin': self._safe_av_float(overview.get('OperatingMarginTTM')),
            'roe': self._safe_av_float(overview.get('ReturnOnEquityTTM')),
            'roa': self._safe_av_float(overview.get('ReturnOnAssetsTTM')),
            'revenue_growth_yoy': self._safe_av_float(overview.get('QuarterlyRevenueGrowthYOY')),
            'earnings_growth_yoy': self._safe_av_float(overview.get('QuarterlyEarningsGrowthYOY')),
            'trailing_pe': self._safe_av_float(overview.get('TrailingPE')),
            'forward_pe': self._safe_av_float(overview.get('ForwardPE')),
            'analyst_target_price': self._safe_av_float(overview.get('AnalystTargetPrice')),
            'analyst_ratings': {
                'strong_buy': strong_buy,
                'buy': buy,
                'hold': hold,
                'sell': sell,
                'strong_sell': strong_sell,
                'total': total_ratings,
                'buy_pct': round((strong_buy + buy) / total_ratings * 100, 1) if total_ratings > 0 else None,
            },
        }

    # =========================================================================
    # COMPREHENSIVE COMPANY OVERVIEW
    # =========================================================================
    
    def get_company_overview(self, symbol: str) -> Dict:
        """
        Get comprehensive company fundamentals
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with full fundamental overview
        """
        print(f"[Earnings] Fetching company overview for {symbol}...")
        
        data = self._make_request({
            'function': 'OVERVIEW',
            'symbol': symbol
        })
        
        if not data or 'Symbol' not in data:
            return {'error': f'No overview data for {symbol}'}
        
        return {
            'symbol': data.get('Symbol'),
            'name': data.get('Name'),
            'sector': data.get('Sector'),
            'industry': data.get('Industry'),
            'market_cap': float(data.get('MarketCapitalization', 0) or 0),
            'valuation': {
                'pe_ratio': float(data.get('PERatio', 0) or 0),
                'forward_pe': float(data.get('ForwardPE', 0) or 0),
                'peg_ratio': float(data.get('PEGRatio', 0) or 0),
                'price_to_book': float(data.get('PriceToBookRatio', 0) or 0),
                'price_to_sales': float(data.get('PriceToSalesRatioTTM', 0) or 0),
                'ev_to_ebitda': float(data.get('EVToEBITDA', 0) or 0)
            },
            'profitability': {
                'profit_margin': float(data.get('ProfitMargin', 0) or 0),
                'operating_margin': float(data.get('OperatingMarginTTM', 0) or 0),
                'return_on_equity': float(data.get('ReturnOnEquityTTM', 0) or 0),
                'return_on_assets': float(data.get('ReturnOnAssetsTTM', 0) or 0)
            },
            'growth': {
                'revenue_growth_yoy': float(data.get('QuarterlyRevenueGrowthYOY', 0) or 0),
                'earnings_growth_yoy': float(data.get('QuarterlyEarningsGrowthYOY', 0) or 0)
            },
            'dividends': {
                'dividend_yield': float(data.get('DividendYield', 0) or 0),
                'dividend_per_share': float(data.get('DividendPerShare', 0) or 0),
                'payout_ratio': float(data.get('PayoutRatio', 0) or 0)
            },
            'analyst': {
                'target_price': float(data.get('AnalystTargetPrice', 0) or 0),
                'rating': data.get('AnalystRating', 'N/A')
            }
        }
    
    # =========================================================================
    # FULL EARNINGS REPORT
    # =========================================================================
    
    def get_earnings_report(self, symbol: str) -> Dict:
        """
        Generate comprehensive earnings report
        
        Combines all analyses into one report
        
        Args:
            symbol: Stock ticker
            
        Returns:
            Dict with full earnings analysis
        """
        print(f"\n{'='*70}")
        print(f"EARNINGS REPORT: {symbol}")
        print(f"{'='*70}")
        
        report = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'overview': self.get_company_overview(symbol),
            'earnings_history': self.get_earnings_history(symbol),
            'analyst_estimates': self.get_analyst_estimates(symbol),
            'implied_growth': self.get_implied_growth(symbol),
            'insider_activity': self.get_insider_activity(symbol)
        }
        
        # Generate overall assessment
        report['assessment'] = self._generate_assessment(report)
        
        return report
    
    def _generate_assessment(self, report: Dict) -> Dict:
        """Generate overall assessment from report components"""
        
        score = 0
        factors = []
        
        # Earnings track record
        track = report.get('earnings_history', {}).get('track_record', {})
        if track.get('beat_rate_pct', 0) >= 75:
            score += 2
            factors.append(f"Excellent beat rate: {track.get('beat_rate_pct')}%")
        elif track.get('beat_rate_pct', 0) >= 50:
            score += 1
        
        # Implied growth
        growth = report.get('implied_growth', {}).get('summary', {})
        if growth.get('avg_implied_growth_pct', 0) > 15:
            score += 1
            factors.append(f"Strong implied growth: {growth.get('avg_implied_growth_pct')}%")
        
        # PEG ratio
        peg = report.get('implied_growth', {}).get('current_metrics', {}).get('peg_ratio', 0)
        if 0 < peg < 1:
            score += 2
            factors.append(f"Attractive PEG: {peg}")
        elif 0 < peg < 1.5:
            score += 1
        
        # Insider activity
        insider = report.get('insider_activity', {}).get('signal', '')
        if insider == 'BULLISH':
            score += 2
            factors.append("Bullish insider activity")
        elif insider == 'BEARISH':
            score -= 1
            factors.append("Bearish insider activity")
        
        # Determine overall signal
        if score >= 5:
            signal = 'STRONG_BUY'
            recommendation = 'Attractive earnings profile with strong fundamentals'
        elif score >= 3:
            signal = 'BUY'
            recommendation = 'Positive earnings outlook'
        elif score >= 1:
            signal = 'HOLD'
            recommendation = 'Mixed signals - monitor closely'
        else:
            signal = 'CAUTIOUS'
            recommendation = 'Weak earnings profile - exercise caution'
        
        return {
            'earnings_score': score,
            'max_score': 7,
            'signal': signal,
            'recommendation': recommendation,
            'key_factors': factors
        }
    
    # =========================================================================
    # SECTOR ANALYSIS
    # =========================================================================
    
    def get_sector_earnings(self, symbols: List[str]) -> Dict:
        """
        Analyze earnings across multiple stocks (sector view)
        
        Args:
            symbols: List of stock tickers
            
        Returns:
            Dict with sector earnings comparison
        """
        print(f"[Earnings] Analyzing sector: {symbols}")
        
        results = []
        for symbol in symbols:
            growth = self.get_implied_growth(symbol)
            if 'error' not in growth:
                results.append({
                    'symbol': symbol,
                    'pe': growth.get('current_metrics', {}).get('trailing_pe'),
                    'forward_pe': growth.get('current_metrics', {}).get('forward_pe'),
                    'peg': growth.get('current_metrics', {}).get('peg_ratio'),
                    'implied_growth': growth.get('summary', {}).get('avg_implied_growth_pct')
                })
        
        if not results:
            return {'error': 'No data available'}
        
        # Calculate sector averages
        avg_pe = np.mean([r['pe'] for r in results if r['pe']])
        avg_forward_pe = np.mean([r['forward_pe'] for r in results if r['forward_pe']])
        avg_peg = np.mean([r['peg'] for r in results if r['peg']])
        avg_growth = np.mean([r['implied_growth'] for r in results if r['implied_growth']])
        
        # Rank by PEG (lower is better)
        sorted_by_peg = sorted([r for r in results if r['peg']], key=lambda x: x['peg'])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'symbols_analyzed': symbols,
            'sector_averages': {
                'avg_pe': round(avg_pe, 2) if avg_pe else None,
                'avg_forward_pe': round(avg_forward_pe, 2) if avg_forward_pe else None,
                'avg_peg': round(avg_peg, 2) if avg_peg else None,
                'avg_implied_growth': round(avg_growth, 2) if avg_growth else None
            },
            'individual_results': results,
            'best_peg': sorted_by_peg[:3] if sorted_by_peg else [],
            'worst_peg': sorted_by_peg[-3:] if len(sorted_by_peg) >= 3 else []
        }
    
    # =========================================================================
    # EARNINGS CALENDAR
    # =========================================================================
    
    def get_upcoming_earnings(self, horizon: str = '3month', filter_symbols: List[str] = None) -> Dict:
        """
        Get upcoming earnings announcements from EARNINGS_CALENDAR (CSV endpoint).

        Args:
            horizon: Time horizon ('3month', '6month', '12month')
            filter_symbols: Optional list of tickers to filter. If None, returns all.

        Returns:
            Dict with upcoming earnings calendar entries
        """
        print(f"[Earnings] Fetching earnings calendar ({horizon})...")

        rows = self._make_csv_request({
            'function': 'EARNINGS_CALENDAR',
            'horizon': horizon
        })

        if not rows:
            return {'error': 'Unable to fetch earnings calendar'}

        # Parse and optionally filter
        entries = []
        for row in rows:
            symbol = row.get('symbol', '')
            if filter_symbols and symbol not in filter_symbols:
                continue
            entries.append({
                'symbol': symbol,
                'name': row.get('name', ''),
                'report_date': row.get('reportDate', ''),
                'fiscal_date_ending': row.get('fiscalDateEnding', ''),
                'estimate': self._safe_av_float(row.get('estimate')),
                'currency': row.get('currency', 'USD'),
            })

        # Sort by report date
        entries.sort(key=lambda x: x.get('report_date', ''))

        return {
            'timestamp': datetime.now().isoformat(),
            'horizon': horizon,
            'total_entries': len(rows),
            'filtered_entries': len(entries),
            'entries': entries,
        }


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    analytics = EarningsAnalytics()
    
    # Test with Apple
    symbol = 'AAPL'
    
    print("\n" + "="*70)
    print("IMPLIED GROWTH ANALYSIS")
    print("="*70)
    growth = analytics.get_implied_growth(symbol)
    print(f"\nSymbol: {growth.get('symbol')}")
    
    metrics = growth.get('current_metrics', {})
    print(f"\nCurrent Metrics:")
    print(f"  Trailing P/E: {metrics.get('trailing_pe')}")
    print(f"  Forward P/E: {metrics.get('forward_pe')}")
    print(f"  PEG Ratio: {metrics.get('peg_ratio')}")
    
    implied = growth.get('implied_growth', {})
    if 'from_pe_ratio' in implied:
        pe = implied['from_pe_ratio']
        print(f"\nFrom P/E Ratio:")
        print(f"  Implied EPS Growth: {pe.get('implied_eps_growth_pct')}%")
        print(f"  Interpretation: {pe.get('interpretation')}")
    
    if 'from_peg' in implied:
        peg = implied['from_peg']
        print(f"\nFrom PEG Ratio:")
        print(f"  Implied Growth: {peg.get('implied_growth_pct')}%")
        print(f"  Assessment: {peg.get('peg_assessment')}")
    
    summary = growth.get('summary', {})
    print(f"\nSummary:")
    print(f"  Average Implied Growth: {summary.get('avg_implied_growth_pct')}%")
    print(f"  Growth Expectation: {summary.get('growth_expectation')}")
    print(f"  Valuation Signal: {summary.get('valuation_signal')}")

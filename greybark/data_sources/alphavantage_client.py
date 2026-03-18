"""
Grey Bark - AlphaVantage API Client
Fundamentals, Earnings, and Sentiment data
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..config import config


class AlphaVantageClient:
    """
    Client for AlphaVantage API (Premium)
    
    Usage:
        client = AlphaVantageClient()
        
        # Company overview
        overview = client.get_overview('AAPL')
        
        # Earnings
        earnings = client.get_earnings('NVDA')
        
        # Sector sentiment
        sentiment = client.get_sector_sentiment('technology')
    """
    
    def __init__(self, api_key: str = None):
        """Initialize AlphaVantage client"""
        self.api_key = api_key or config.alphavantage.api_key
        self.base_url = config.alphavantage.base_url
    
    def _request(self, params: Dict) -> Dict:
        """Make API request"""
        params['apikey'] = self.api_key
        
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[AlphaVantage] ✗ Error: {e}")
            raise
    
    # =========================================================================
    # FUNDAMENTALS
    # =========================================================================
    
    def get_overview(self, symbol: str) -> Dict:
        """
        Get company overview (fundamentals)
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
        
        Returns:
            Dict with P/E, Market Cap, etc.
        """
        params = {
            'function': 'OVERVIEW',
            'symbol': symbol
        }
        return self._request(params)
    
    def get_pe_ratio(self, symbol: str) -> Optional[float]:
        """Get P/E ratio for a symbol"""
        try:
            overview = self.get_overview(symbol)
            pe = overview.get('PERatio')
            return float(pe) if pe and pe != 'None' else None
        except:
            return None
    
    def get_multiple_pe_ratios(self, symbols: List[str]) -> Dict[str, Optional[float]]:
        """Get P/E ratios for multiple symbols"""
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_pe_ratio(symbol)
        return result
    
    # =========================================================================
    # EARNINGS
    # =========================================================================
    
    def get_earnings(self, symbol: str) -> Dict:
        """
        Get earnings data
        
        Args:
            symbol: Stock ticker
        
        Returns:
            Dict with quarterly and annual earnings
        """
        params = {
            'function': 'EARNINGS',
            'symbol': symbol
        }
        return self._request(params)
    
    def get_quarterly_eps(self, symbol: str, quarters: int = 4) -> List[Dict]:
        """
        Get quarterly EPS for a symbol
        
        Args:
            symbol: Stock ticker
            quarters: Number of quarters to return
        
        Returns:
            List of dicts with date and EPS
        """
        earnings = self.get_earnings(symbol)
        quarterly = earnings.get('quarterlyEarnings', [])
        
        result = []
        for q in quarterly[:quarters]:
            result.append({
                'date': q.get('fiscalDateEnding'),
                'reported_eps': float(q.get('reportedEPS', 0)),
                'estimated_eps': float(q.get('estimatedEPS', 0)) if q.get('estimatedEPS') else None,
                'surprise': float(q.get('surprise', 0)) if q.get('surprise') else None,
                'surprise_pct': float(q.get('surprisePercentage', 0)) if q.get('surprisePercentage') else None
            })
        
        return result
    
    # =========================================================================
    # SECTOR SENTIMENT
    # =========================================================================
    
    def get_sector_sentiment(self, 
                              topic: str,
                              days_back: int = 7,
                              limit: int = 200) -> Dict:
        """
        Get news sentiment for a sector/topic
        
        Args:
            topic: Sector topic (technology, finance, energy, healthcare, etc.)
            days_back: Days to look back
            limit: Max articles to analyze
        
        Returns:
            Dict with average sentiment and article count
        """
        time_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%dT0000')
        
        params = {
            'function': 'NEWS_SENTIMENT',
            'topics': topic,
            'time_from': time_from,
            'limit': limit
        }
        
        data = self._request(params)
        feed = data.get('feed', [])
        
        if not feed:
            return {
                'topic': topic,
                'avg_sentiment': 0,
                'article_count': 0,
                'sentiment_label': 'NEUTRAL'
            }
        
        # Calculate average sentiment
        scores = []
        for article in feed:
            score = article.get('overall_sentiment_score')
            if score:
                scores.append(float(score))
        
        avg_sentiment = sum(scores) / len(scores) if scores else 0
        
        # Determine label
        if avg_sentiment > 0.15:
            label = 'BULLISH'
        elif avg_sentiment < -0.15:
            label = 'BEARISH'
        else:
            label = 'NEUTRAL'
        
        return {
            'topic': topic,
            'avg_sentiment': round(avg_sentiment, 4),
            'article_count': len(scores),
            'sentiment_label': label
        }
    
    def get_all_sectors_sentiment(self, days_back: int = 7) -> Dict[str, Dict]:
        """
        Get sentiment for all major sectors
        
        Returns:
            Dict mapping sector to sentiment data
        """
        print("[AlphaVantage] Fetching sector sentiment...")
        
        topics = [
            'technology',
            'finance',
            'energy',
            'healthcare',
            'retail',
            'manufacturing',
            'real_estate'
        ]
        
        result = {}
        for topic in topics:
            try:
                sentiment = self.get_sector_sentiment(topic, days_back)
                result[topic] = sentiment
                print(f"  ✓ {topic:15} = {sentiment['avg_sentiment']:+.3f} ({sentiment['sentiment_label']})")
            except Exception as e:
                print(f"  ✗ {topic:15} - Error: {e}")
                result[topic] = {'avg_sentiment': 0, 'sentiment_label': 'ERROR'}
        
        print(f"[AlphaVantage] ✓ Fetched sentiment for {len(result)} sectors")
        return result
    
    def score_sentiment(self, sentiment: float) -> int:
        """
        Convert sentiment score to discrete score (-3 to +3)
        
        Args:
            sentiment: Raw sentiment score (-1 to +1)
        
        Returns:
            Discrete score from -3 to +3
        """
        if sentiment > 0.5:
            return 3
        elif sentiment > 0.3:
            return 2
        elif sentiment > 0.15:
            return 1
        elif sentiment > -0.15:
            return 0
        elif sentiment > -0.3:
            return -1
        elif sentiment > -0.5:
            return -2
        else:
            return -3

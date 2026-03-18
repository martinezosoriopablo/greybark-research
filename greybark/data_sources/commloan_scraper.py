"""
Grey Bark - CommLoan SOFR Scraper
Scrapes SOFR forward rates from CommLoan.com
"""

import requests
import pandas as pd
from typing import Dict, Optional

from ..config import config


class CommLoanScraper:
    """
    Scraper for SOFR forward rates from CommLoan
    
    Usage:
        scraper = CommLoanScraper()
        rates = scraper.get_sofr_forwards()
        
        # Returns:
        # {'1M': 4.35, '3M': 4.28, '6M': 4.15, '1Y': 3.95, '2Y': 3.75, ...}
    """
    
    def __init__(self, url: str = None):
        """Initialize CommLoan scraper"""
        self.url = url or config.commloan.url
        self.headers = {
            'User-Agent': config.commloan.user_agent
        }
    
    def get_sofr_forwards(self) -> Dict[str, float]:
        """
        Scrape SOFR forward rates from CommLoan
        
        Returns:
            Dict mapping tenor to rate (e.g., {'1M': 4.35, '1Y': 3.95})
        """
        print("[CommLoan] Fetching SOFR forwards...")
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            tables = pd.read_html(response.content)
            
            if not tables:
                raise ValueError("No tables found on page")
            
            swaps_table = tables[0]
            
            sofr_rates = {}
            
            tenor_mapping = {
                'SOFR 1 Month': '1M',
                'SOFR 3 Month': '3M',
                'SOFR 6 Month': '6M',
                'SOFR Swap 1 Year': '1Y',
                'SOFR Swap 2 Year': '2Y',
                'SOFR Swap 3 Year': '3Y',
                'SOFR Swap 5 Year': '5Y',
                'SOFR Swap 10 Year': '10Y',
            }
            
            for idx, row in swaps_table.iterrows():
                label = str(row.iloc[0]).strip()
                
                for comm_label, tenor in tenor_mapping.items():
                    if comm_label.lower() in label.lower():
                        try:
                            rate = float(row.iloc[1])
                            sofr_rates[tenor] = rate
                            print(f"  ✓ {tenor:4} = {rate:.3f}%")
                        except (ValueError, IndexError):
                            pass
                        break
            
            if len(sofr_rates) < 5:
                raise ValueError(f"Insufficient SOFR rates found: {len(sofr_rates)}")
            
            print(f"[CommLoan] ✓ Extracted {len(sofr_rates)} SOFR forward rates")
            return sofr_rates
            
        except Exception as e:
            print(f"[CommLoan] ✗ Error fetching SOFR forwards: {e}")
            raise
    
    def get_sofr_rate(self, tenor: str) -> Optional[float]:
        """
        Get SOFR rate for a specific tenor
        
        Args:
            tenor: Rate tenor (e.g., '1M', '1Y', '5Y')
        
        Returns:
            Rate as float, or None if not found
        """
        rates = self.get_sofr_forwards()
        return rates.get(tenor)
    
    def get_fed_expectations_12m(self, current_fed_funds: float = None) -> float:
        """
        Calculate Fed Funds expectations for next 12 months
        
        Args:
            current_fed_funds: Current Fed Funds rate (default: estimates from 1M SOFR)
        
        Returns:
            Implied Fed Funds in 12 months
        """
        from ..config import SOFR_FED_SPREAD
        
        rates = self.get_sofr_forwards()
        
        sofr_1y = rates.get('1Y')
        if sofr_1y is None:
            raise ValueError("SOFR 1Y rate not available")
        
        # Convert SOFR to Fed Funds
        fed_funds_1y = sofr_1y + SOFR_FED_SPREAD
        
        return round(fed_funds_1y, 3)

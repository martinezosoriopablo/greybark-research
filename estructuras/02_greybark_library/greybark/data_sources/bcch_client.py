"""
Grey Bark - BCCh REST API Client
Banco Central de Chile

⚠️ IMPORTANTE: USAR SIEMPRE REST API, NUNCA SOAP
"""

import requests
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

from ..config import config, BCChSeries, DEFAULT_LOOKBACK_DAYS


class BCChClient:
    """
    Client for Banco Central de Chile REST API
    
    ⚠️ IMPORTANTE: Este cliente usa la REST API (SieteRestWS.ashx)
    NO usar la SOAP API (SieteWS.asmx) - falla con error -5
    
    Usage:
        client = BCChClient()
        
        # Single series
        value = client.get_latest_value('F019.VIX.IND.90.D')
        
        # Series with history
        data = client.get_series('F074.TPM.PLG.N.D')
        
        # Swaps CAMARA
        swaps = client.get_spc_rates()
        
        # Encuesta Expectativas
        eee = client.get_encuesta_tpm()
    """
    
    def __init__(self, user: str = None, password: str = None):
        """Initialize BCCh REST client"""
        self.user = user or config.bcch.user
        self.password = password or config.bcch.password
        self.base_url = config.bcch.rest_url
    
    def get_series(self,
                   series_id: str,
                   start_date: date = None,
                   end_date: date = None,
                   days_back: int = DEFAULT_LOOKBACK_DAYS) -> Optional[pd.Series]:
        """
        Fetch a series from BCCh REST API
        
        Args:
            series_id: BCCh series ID (e.g., 'F074.TPM.PLG.N.D')
            start_date: Start date (default: days_back from today)
            end_date: End date (default: today)
            days_back: Days to look back if start_date not specified
        
        Returns:
            pandas Series with the data, or None if failed
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=days_back)
        
        params = {
            'user': self.user,
            'pass': self.password,
            'function': 'GetSeries',
            'timeseries': series_id,
            'firstdate': start_date.strftime('%Y-%m-%d'),
            'lastdate': end_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"[BCCh] ERR: HTTP error {response.status_code} for {series_id}")
                return None
            
            data = response.json()
            obs = data.get('Series', {}).get('Obs', [])
            
            if not obs:
                print(f"[BCCh] ERR: No data for {series_id}")
                return None
            
            # Convert to pandas Series
            dates = []
            values = []
            for observation in obs:
                date_str = observation.get('indexDateString', '')
                value_str = observation.get('value', '').strip()
                if date_str and value_str:
                    try:
                        dates.append(pd.to_datetime(date_str))
                        values.append(float(value_str))
                    except (ValueError, TypeError):
                        continue
            
            if dates and values:
                return pd.Series(values, index=dates, name=series_id)
            return None
            
        except Exception as e:
            print(f"[BCCh] ERR: Exception fetching {series_id}: {e}")
            return None
    
    def get_latest_value(self, 
                         series_id: str,
                         days_back: int = DEFAULT_LOOKBACK_DAYS) -> Optional[float]:
        """
        Get the most recent value for a series
        
        Args:
            series_id: BCCh series ID
            days_back: Days to look back
        
        Returns:
            Latest value as float, or None if not found
        """
        data = self.get_series(series_id, days_back=days_back)
        if data is not None and len(data) > 0:
            return float(data.iloc[-1])
        return None
    
    def get_latest_with_date(self,
                             series_id: str,
                             days_back: int = DEFAULT_LOOKBACK_DAYS) -> Tuple[Optional[float], Optional[str]]:
        """
        Get the most recent value and its date
        
        Returns:
            Tuple of (value, date_string) or (None, None)
        """
        data = self.get_series(series_id, days_back=days_back)
        if data is not None and len(data) > 0:
            return float(data.iloc[-1]), data.index[-1].strftime('%Y-%m-%d')
        return None, None
    
    # =========================================================================
    # SWAPS PROMEDIO CÁMARA (SPC)
    # =========================================================================
    
    def get_spc_rates(self) -> Dict[str, float]:
        """
        Fetch all Swap Promedio Cámara rates
        
        Returns:
            Dict mapping tenor to rate (e.g., {'90D': 5.12, '2Y': 4.85})
        """
        print("[BCCh] Fetching SPC rates...")
        
        spc_series = {
            '90D': BCChSeries.SPC_90D,
            '180D': BCChSeries.SPC_180D,
            '360D': BCChSeries.SPC_360D,
            '2Y': BCChSeries.SPC_2Y,
            '3Y': BCChSeries.SPC_3Y,
            '5Y': BCChSeries.SPC_5Y,
        }
        
        rates = {}
        for tenor, series_id in spc_series.items():
            value = self.get_latest_value(series_id)
            if value is not None:
                rates[tenor] = value
                print(f"  OK: {tenor:4} = {value:.3f}%")
            else:
                print(f"  ERR: {tenor:4} - No data")
        
        print(f"[BCCh] OK: Fetched {len(rates)} SPC rates")
        return rates
    
    def get_all_spc_series(self) -> Dict[str, str]:
        """Return dict of all SPC series IDs by tenor"""
        return {
            '90D': BCChSeries.SPC_90D,
            '180D': BCChSeries.SPC_180D,
            '360D': BCChSeries.SPC_360D,
            '2Y': BCChSeries.SPC_2Y,
            '3Y': BCChSeries.SPC_3Y,
            '4Y': BCChSeries.SPC_4Y,
            '5Y': BCChSeries.SPC_5Y,
            '10Y': BCChSeries.SPC_10Y,
        }
    
    # =========================================================================
    # ENCUESTA EXPECTATIVAS ECONÓMICAS (EEE)
    # =========================================================================
    
    def get_encuesta_tpm(self) -> Dict:
        """
        Fetch TPM expectations from Encuesta de Expectativas Económicas
        
        Returns:
            Dict with expectations by horizon
        """
        print("[BCCh] Fetching Encuesta Expectativas Económicas...")
        
        eee_series = {
            'next_meeting': {
                'id': BCChSeries.EEE_TPM_NEXT,
                'desc': 'Siguiente reunión',
                'months': 0
            },
            'subsequent': {
                'id': BCChSeries.EEE_TPM_SUBSEQUENT,
                'desc': 'Subsiguiente reunión',
                'months': 1
            },
            '2_months': {
                'id': BCChSeries.EEE_TPM_2M,
                'desc': '2 meses',
                'months': 2
            },
            '5_months': {
                'id': BCChSeries.EEE_TPM_5M,
                'desc': '5 meses',
                'months': 5
            },
            '11_months': {
                'id': BCChSeries.EEE_TPM_11M,
                'desc': '11 meses',
                'months': 11
            },
            '17_months': {
                'id': BCChSeries.EEE_TPM_17M,
                'desc': '17 meses',
                'months': 17
            },
            '23_months': {
                'id': BCChSeries.EEE_TPM_23M,
                'desc': '23 meses',
                'months': 23
            },
            '35_months': {
                'id': BCChSeries.EEE_TPM_35M,
                'desc': '35 meses',
                'months': 35
            },
        }
        
        expectations = {
            'by_horizon': {},
            'last_updated': None
        }
        
        for key, info in eee_series.items():
            value, obs_date = self.get_latest_with_date(info['id'])
            
            if value is not None:
                expectations['by_horizon'][key] = {
                    'rate': round(value, 3),
                    'description': info['desc'],
                    'months_ahead': info['months'],
                    'date': obs_date
                }
                
                if expectations['last_updated'] is None:
                    expectations['last_updated'] = obs_date
                
                print(f"  OK: {info['desc']:25} = {value:.2f}%")
            else:
                print(f"  ERR: {info['desc']:25} - No data")
        
        print(f"[BCCh] OK: Fetched {len(expectations['by_horizon'])} EEE horizons")
        return expectations
    
    # =========================================================================
    # REGIME CLASSIFICATION SERIES
    # =========================================================================
    
    def get_regime_indicators(self) -> Dict[str, Optional[float]]:
        """
        Fetch all BCCh series needed for regime classification
        
        Returns:
            Dict with MOVE, VIX, Copper, Gold, China EPU
        """
        indicators = {}
        
        series_map = {
            'move': BCChSeries.MOVE_INDEX,
            'vix': BCChSeries.VIX,
            'copper': BCChSeries.COPPER_PRICE,
            'gold': BCChSeries.GOLD_PRICE,
            'china_epu': BCChSeries.CHINA_EPU,
        }
        
        for name, series_id in series_map.items():
            indicators[name] = self.get_latest_value(series_id)
        
        return indicators
    
    # =========================================================================
    # MACRO CHILE
    # =========================================================================
    
    def get_tpm(self) -> Optional[float]:
        """Get current TPM (Tasa de Política Monetaria)"""
        return self.get_latest_value(BCChSeries.TPM)

    def get_usd_clp(self) -> Optional[float]:
        """Get current USD/CLP exchange rate"""
        return self.get_latest_value(BCChSeries.USD_CLP)

    def get_uf(self) -> Optional[float]:
        """Get current UF value"""
        return self.get_latest_value(BCChSeries.UF)

    def get_ipc_yoy(self) -> Optional[float]:
        """
        Get IPC YoY by summing last 12 monthly variations

        Returns:
            YoY inflation rate as percentage, or None
        """
        # Get 13+ months of data
        data = self.get_series(BCChSeries.IPC_VAR, days_back=400)
        if data is not None and len(data) >= 12:
            # Sum last 12 monthly variations
            last_12 = data.iloc[-12:].sum()
            return round(float(last_12), 1)
        return None

    def get_ipc_mom(self) -> Optional[float]:
        """Get latest IPC MoM variation"""
        return self.get_latest_value(BCChSeries.IPC_VAR)

    def get_imacec(self) -> Optional[float]:
        """Get latest IMACEC YoY"""
        return self.get_latest_value(BCChSeries.IMACEC_YOY)

    def get_ipc(self) -> Optional[float]:
        """Get IPC YoY (alias for get_ipc_yoy)"""
        return self.get_ipc_yoy()

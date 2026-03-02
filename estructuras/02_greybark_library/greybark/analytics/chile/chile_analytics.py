"""
Greybark Research - Chile Profundo Analytics
Mejora #6 del AI Council

Comprehensive Chile market analytics including:
- Macro dashboard (IMACEC, IPC, TPM, USD/CLP)
- UF/Breakeven inflation analysis
- Swap CÁMARA curve
- BCP/BCU bond yields
- Carry trade analysis
- IPSA sector analysis

Author: Greybark Research
Date: January 2026
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Import data source clients
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from data_sources.bcch_client import BCChClient
    from data_sources.fred_client import FREDClient
except ImportError:
    from greybark.data_sources.bcch_client import BCChClient
    from greybark.data_sources.fred_client import FREDClient


# =============================================================================
# BCCH SERIES CODES - CHILE PROFUNDO
# =============================================================================

class BCChSeriesChile:
    """
    BCCh REST API Series IDs para Chile Profundo
    
    IMPORTANTE: Estos códigos son de la API REST de BCCh
    Documentación: https://si3.bcentral.cl/estadisticas/Principal1/Web_Services/doc_es.htm
    """
    
    # =========================================================================
    # MACRO CHILE - UPDATED Feb 2026
    # =========================================================================

    # Actividad Económica - IMACEC (referencia 2018)
    IMACEC_YOY = "F032.IMC.V12.Z.Z.2018.Z.Z.0.M"           # IMACEC YoY
    IMACEC_NOMIN_YOY = "F032.IMC.V12.Z.Z.2018.N03.Z.0.M"   # IMACEC no minero YoY
    IMACEC_MOM_SA = "F032.IMC.VAR.Z.Z.2018.Z.Z.3.M"        # IMACEC MoM desest.
    IMACEC = "F032.IMC.V12.Z.Z.2018.Z.Z.0.M"               # Alias para compatibilidad

    # Precios - UPDATED
    IPC_VAR = "F074.IPC.VAR.Z.Z.C.M"                      # IPC variación mensual (FUNCIONA)
    IPC = "F074.IPC.VAR.Z.Z.C.M"                          # Alias para compatibilidad
    UF = "F073.UFF.PRE.Z.D"                               # Valor UF (FUNCIONA)
    UTM = "F073.UTM.PRE.Z.M"                              # Valor UTM

    # Tipo de Cambio
    USD_CLP = "F073.TCO.PRE.Z.D"                          # Tipo cambio observado (FUNCIONA)
    USD_CLP_ACUERDO = "F073.TCA.PRE.Z.D"                  # TC acuerdo
    EURO_CLP = "F072.CLP.EUR.N.O.D"                       # Euro/CLP

    # Política Monetaria - UPDATED
    TPM = "F022.TPM.TIN.D001.NO.Z.D"                      # TPM desde swap 1 día (FUNCIONA)
    
    # =========================================================================
    # CURVA SWAP CÁMARA (SPC)
    # =========================================================================
    
    # Zero Coupon
    SPC_30D = "F022.SPC.TPR.D030.NO.Z.D"
    SPC_60D = "F022.SPC.TPR.D060.NO.Z.D"
    SPC_90D = "F022.SPC.TPR.D090.NO.Z.D"
    SPC_180D = "F022.SPC.TPR.D180.NO.Z.D"
    SPC_270D = "F022.SPC.TPR.D270.NO.Z.D"
    SPC_360D = "F022.SPC.TPR.D360.NO.Z.D"
    
    # Bullet (años)
    SPC_2Y = "F022.SPC.TIN.AN02.NO.Z.D"
    SPC_3Y = "F022.SPC.TIN.AN03.NO.Z.D"
    SPC_4Y = "F022.SPC.TIN.AN04.NO.Z.D"
    SPC_5Y = "F022.SPC.TIN.AN05.NO.Z.D"
    SPC_7Y = "F022.SPC.TIN.AN07.NO.Z.D"
    SPC_10Y = "F022.SPC.TIN.AN10.NO.Z.D"
    
    # =========================================================================
    # TASAS DE BONOS - BCP (Pesos) y BCU (UF)
    # =========================================================================
    
    # BCP - Bonos Banco Central en Pesos (tasas de mercado)
    BCP_2Y = "F022.TMP.TIN.AN02.NO.P.D"                   # BCP 2 años
    BCP_5Y = "F022.TMP.TIN.AN05.NO.P.D"                   # BCP 5 años
    BCP_10Y = "F022.TMP.TIN.AN10.NO.P.D"                  # BCP 10 años
    
    # BCU - Bonos Banco Central en UF (tasas reales)
    BCU_2Y = "F022.TMP.TIN.AN02.NO.U.D"                   # BCU 2 años
    BCU_5Y = "F022.TMP.TIN.AN05.NO.U.D"                   # BCU 5 años
    BCU_10Y = "F022.TMP.TIN.AN10.NO.U.D"                  # BCU 10 años
    BCU_20Y = "F022.TMP.TIN.AN20.NO.U.D"                  # BCU 20 años
    BCU_30Y = "F022.TMP.TIN.AN30.NO.U.D"                  # BCU 30 años
    
    # =========================================================================
    # ENCUESTA EXPECTATIVAS ECONÓMICAS
    # =========================================================================
    
    # TPM esperada
    EEE_TPM_NEXT = "F089.TPM.TAS.11.M"                    # Siguiente reunión
    EEE_TPM_11M = "F089.TPM.TAS.14.M"                     # 11 meses
    EEE_TPM_23M = "F089.TPM.TAS.15.M"                     # 23 meses
    
    # Inflación esperada
    EEE_IPC_12M = "F089.IPC.V12.Z.M"                      # IPC 12 meses
    EEE_IPC_24M = "F089.IPC.V24.Z.M"                      # IPC 24 meses
    
    # Tipo de cambio esperado
    EEE_TC_12M = "F089.TCN.VAL.Z.M"                       # TC 12 meses
    
    # =========================================================================
    # FLUJOS E INDICADORES EXTERNOS
    # =========================================================================
    
    # Cobre
    COPPER_PRICE = "F019.PPB.PRE.40.M"                    # Precio cobre USD/lb
    
    # Riesgo país (EMBI Chile)
    EMBI_CHILE = "F019.EMBI.IND.CL.D"                     # EMBI Chile spread
    
    # VIX y MOVE
    VIX = "F019.VIX.IND.90.D"
    MOVE_INDEX = "F019.MOVE.IND.90.D"


# =============================================================================
# YAHOO FINANCE TICKERS - CHILE
# =============================================================================

class YahooTickersChile:
    """Yahoo Finance tickers for Chilean equities"""
    
    # IPSA Index (not directly available, use ETF or individual stocks)
    ECH = "ECH"                    # iShares MSCI Chile ETF
    
    # Major Chilean stocks (Santiago Exchange .SN suffix)
    STOCKS = {
        # Retail
        'CENCOSUD': 'CENCOSUD.SN',
        'FALABELLA': 'FALABELLA.SN',
        'RIPLEY': 'RIPLEY.SN',
        
        # Utilities
        'ENEL_CHILE': 'ENELCHILE.SN',
        'ENEL_AMERICAS': 'ENELAM.SN',
        'COLBUN': 'COLBUN.SN',
        'AES_ANDES': 'AESANDES.SN',
        
        # Banks
        'SANTANDER_CHILE': 'BSANTANDER.SN',
        'BCI': 'BCI.SN',
        'BANCO_CHILE': 'CHILE.SN',
        'ITAU_CHILE': 'ITAUCORP.SN',
        
        # Mining & Resources
        'SQM': 'SQM-B.SN',
        'CAP': 'CAP.SN',
        'COPEC': 'COPEC.SN',
        
        # Other
        'CCU': 'CCU.SN',
        'CMPC': 'CMPC.SN',
        'VAPORES': 'VAPORES.SN',
        'LATAM': 'LTM.SN',
    }
    
    # Sector mappings
    SECTORS = {
        'retail': ['CENCOSUD', 'FALABELLA', 'RIPLEY'],
        'utilities': ['ENEL_CHILE', 'ENEL_AMERICAS', 'COLBUN', 'AES_ANDES'],
        'banks': ['SANTANDER_CHILE', 'BCI', 'BANCO_CHILE', 'ITAU_CHILE'],
        'mining': ['SQM', 'CAP', 'COPEC'],
        'industrial': ['CCU', 'CMPC', 'VAPORES', 'LATAM'],
    }


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ChileMacroSnapshot:
    """Chile macro data snapshot"""
    tpm: float                    # Tasa de Política Monetaria
    ipc_yoy: float               # IPC YoY
    imacec_yoy: float            # IMACEC YoY
    usd_clp: float               # Tipo de cambio
    uf: float                    # Valor UF
    copper_price: float          # Precio cobre
    embi_spread: Optional[float] # Spread EMBI Chile
    as_of: str


@dataclass  
class ChileBreakevenData:
    """Chile breakeven inflation data"""
    bcp_5y: float                # BCP 5 años (nominal)
    bcu_5y: float                # BCU 5 años (real)
    breakeven_5y: float          # Breakeven inflación implícita
    bcp_10y: Optional[float]
    bcu_10y: Optional[float]
    breakeven_10y: Optional[float]
    uf_monthly_change: float     # Cambio mensual UF
    uf_annualized: float         # UF anualizada
    as_of: str


@dataclass
class ChileCarryTrade:
    """Chile carry trade analysis"""
    tpm_chile: float             # TPM Chile
    fed_funds_usa: float         # Fed Funds USA
    rate_differential: float     # TPM - Fed Funds
    usd_clp_spot: float
    usd_clp_1y_forward: Optional[float]
    implied_depreciation: Optional[float]
    carry_attractiveness: str    # HIGH, MEDIUM, LOW
    recommendation: str


# =============================================================================
# MAIN CLASS: CHILE PROFUNDO
# =============================================================================

class ChileAnalytics:
    """
    Chile Profundo Analytics
    
    Comprehensive analytics for Chilean markets including:
    - Macro dashboard (IMACEC, IPC, TPM, USD/CLP)
    - UF/Breakeven inflation
    - Swap CÁMARA curve
    - Carry trade analysis
    - Equity sector analysis
    
    Usage:
        analytics = ChileAnalytics()
        
        # Macro snapshot
        macro = analytics.get_macro_snapshot()
        
        # Breakeven inflation
        breakeven = analytics.get_breakeven_inflation()
        
        # Full dashboard
        dashboard = analytics.get_chile_dashboard()
    """
    
    def __init__(self, bcch_user: str = None, bcch_password: str = None,
                 fred_api_key: str = None):
        """Initialize with API credentials"""
        self.bcch = BCChClient(user=bcch_user, password=bcch_password)
        self.fred = FREDClient(api_key=fred_api_key)
        self._cache = {}
    
    # =========================================================================
    # MACRO CHILE
    # =========================================================================
    
    def get_macro_snapshot(self) -> Dict[str, Any]:
        """
        Get current Chile macro snapshot
        
        Returns:
            Dict with TPM, IPC, IMACEC, USD/CLP, UF, Copper
        """
        print("[Chile] Fetching macro snapshot...")
        
        # Fetch all macro series
        data = {
            'tpm': self.bcch.get_latest_value(BCChSeriesChile.TPM),
            'ipc': self._get_ipc_yoy(),
            'imacec': self._get_imacec_yoy(),
            'usd_clp': self.bcch.get_latest_value(BCChSeriesChile.USD_CLP),
            'uf': self.bcch.get_latest_value(BCChSeriesChile.UF),
            'copper': self.bcch.get_latest_value(BCChSeriesChile.COPPER_PRICE),
            'embi': self.bcch.get_latest_value(BCChSeriesChile.EMBI_CHILE),
        }
        
        # Calculate real policy rate
        if data['tpm'] and data['ipc']:
            data['real_tpm'] = data['tpm'] - data['ipc']
        else:
            data['real_tpm'] = None
        
        # Policy stance assessment
        data['policy_stance'] = self._assess_policy_stance(
            data.get('real_tpm'), 
            data.get('ipc')
        )
        
        data['as_of'] = datetime.now().isoformat()
        
        print(f"  OK: TPM: {data['tpm']}%")
        print(f"  OK: IPC YoY: {data['ipc']}%")
        print(f"  OK: IMACEC YoY: {data['imacec']}%")
        print(f"  OK: USD/CLP: {data['usd_clp']}")
        
        return data
    
    def _get_ipc_yoy(self) -> Optional[float]:
        """Calculate IPC YoY from monthly variations"""
        try:
            # IPC_VAR returns monthly % changes, sum last 12 for YoY
            series = self.bcch.get_series(
                BCChSeriesChile.IPC_VAR,
                days_back=400  # Need 13 months minimum
            )
            if series is not None and len(series) >= 12:
                # Sum last 12 monthly variations = YoY approximation
                yoy = series.iloc[-12:].sum()
                return round(float(yoy), 1)
        except Exception as e:
            print(f"  ERR: Error calculating IPC YoY: {e}")
        return None
    
    def _get_imacec_yoy(self) -> Optional[float]:
        """Get latest IMACEC YoY"""
        try:
            # Serie YoY directa (referencia 2018)
            value = self.bcch.get_latest_value(BCChSeriesChile.IMACEC_YOY)
            if value is not None:
                return round(float(value), 1)
        except Exception as e:
            print(f"  ERR: Error getting IMACEC: {e}")
        return None
    
    def _assess_policy_stance(self, real_tpm: float, ipc: float) -> str:
        """Assess monetary policy stance"""
        if real_tpm is None or ipc is None:
            return 'UNKNOWN'
        
        # Neutral real rate estimate for Chile: ~1.5%
        neutral_real = 1.5
        
        if real_tpm > neutral_real + 1.0:
            return 'RESTRICTIVE'
        elif real_tpm < neutral_real - 1.0:
            return 'ACCOMMODATIVE'
        else:
            return 'NEUTRAL'
    
    # =========================================================================
    # SWAP CÁMARA CURVE
    # =========================================================================
    
    def get_camara_curve(self) -> Dict[str, Any]:
        """
        Get full Swap CÁMARA curve
        
        Returns:
            Dict with rates by tenor and curve analysis
        """
        print("[Chile] Fetching Swap CÁMARA curve...")
        
        # Define tenors and series
        tenors = {
            '30D': BCChSeriesChile.SPC_30D,
            '60D': BCChSeriesChile.SPC_60D,
            '90D': BCChSeriesChile.SPC_90D,
            '180D': BCChSeriesChile.SPC_180D,
            '270D': BCChSeriesChile.SPC_270D,
            '360D': BCChSeriesChile.SPC_360D,
            '2Y': BCChSeriesChile.SPC_2Y,
            '3Y': BCChSeriesChile.SPC_3Y,
            '4Y': BCChSeriesChile.SPC_4Y,
            '5Y': BCChSeriesChile.SPC_5Y,
            '7Y': BCChSeriesChile.SPC_7Y,
            '10Y': BCChSeriesChile.SPC_10Y,
        }
        
        rates = {}
        for tenor, series_id in tenors.items():
            value = self.bcch.get_latest_value(series_id)
            if value is not None:
                rates[tenor] = round(value, 3)
                print(f"  OK: {tenor:5} = {value:.3f}%")
        
        # Get current TPM for comparison
        tpm = self.bcch.get_latest_value(BCChSeriesChile.TPM)
        
        # Calculate key spreads
        spreads = {}
        if '90D' in rates and tpm:
            spreads['90d_vs_tpm'] = round((rates['90D'] - tpm) * 100, 1)  # bps
        if '360D' in rates and '90D' in rates:
            spreads['360d_vs_90d'] = round((rates['360D'] - rates['90D']) * 100, 1)
        if '2Y' in rates and '360D' in rates:
            spreads['2y_vs_1y'] = round((rates['2Y'] - rates['360D']) * 100, 1)
        if '5Y' in rates and '2Y' in rates:
            spreads['5y_vs_2y'] = round((rates['5Y'] - rates['2Y']) * 100, 1)
        if '10Y' in rates and '5Y' in rates:
            spreads['10y_vs_5y'] = round((rates['10Y'] - rates['5Y']) * 100, 1)
        
        # Determine curve shape
        curve_shape = self._determine_curve_shape(rates, tpm)
        
        # Rate cut/hike expectations
        expectations = self._derive_rate_expectations(rates, tpm)
        
        return {
            'current_tpm': tpm,
            'curve': rates,
            'spreads_bps': spreads,
            'shape': curve_shape,
            'rate_expectations': expectations,
            'as_of': datetime.now().isoformat()
        }
    
    def _determine_curve_shape(self, rates: Dict, tpm: float) -> str:
        """Determine curve shape from rates"""
        if not rates or tpm is None:
            return 'UNKNOWN'
        
        # Compare short vs long
        short_rate = rates.get('90D', rates.get('180D'))
        long_rate = rates.get('5Y', rates.get('2Y'))
        
        if short_rate is None or long_rate is None:
            return 'INSUFFICIENT_DATA'
        
        slope = long_rate - short_rate
        
        if slope < -0.5:
            return 'DEEPLY_INVERTED'
        elif slope < 0:
            return 'INVERTED'
        elif slope < 0.25:
            return 'FLAT'
        elif slope < 1.0:
            return 'NORMAL'
        else:
            return 'STEEP'
    
    def _derive_rate_expectations(self, rates: Dict, tpm: float) -> Dict:
        """Derive rate cut/hike expectations from curve"""
        if not rates or tpm is None:
            return {}
        
        expectations = {}
        
        # 90D rate implies near-term expectations
        rate_90d = rates.get('90D')
        if rate_90d is not None:
            diff = rate_90d - tpm
            if diff < -0.20:
                expectations['near_term'] = f"Market expects {abs(diff*100):.0f}bps of cuts in 3 months"
            elif diff > 0.20:
                expectations['near_term'] = f"Market expects {diff*100:.0f}bps of hikes in 3 months"
            else:
                expectations['near_term'] = "Market expects TPM stable near-term"
        
        # 1Y rate implies 12-month expectations  
        rate_1y = rates.get('360D')
        if rate_1y is not None:
            diff = rate_1y - tpm
            cuts_25bps = int(diff / -0.25) if diff < 0 else 0
            hikes_25bps = int(diff / 0.25) if diff > 0 else 0
            
            if cuts_25bps > 0:
                expectations['one_year'] = f"~{cuts_25bps} cuts of 25bps priced for next 12 months"
            elif hikes_25bps > 0:
                expectations['one_year'] = f"~{hikes_25bps} hikes of 25bps priced for next 12 months"
            else:
                expectations['one_year'] = "TPM broadly stable over next 12 months"
        
        return expectations
    
    # =========================================================================
    # BREAKEVEN INFLATION (BCP vs BCU)
    # =========================================================================
    
    def get_breakeven_inflation(self) -> Dict[str, Any]:
        """
        Calculate Chile breakeven inflation from BCP vs BCU
        
        Breakeven = BCP (nominal) - BCU (real)
        
        Returns:
            Dict with breakeven rates by tenor
        """
        print("[Chile] Calculating breakeven inflation...")
        
        result = {
            'breakevens': {},
            'nominal_curve': {},
            'real_curve': {},
            'uf_analysis': {}
        }
        
        # Fetch BCP (nominal) and BCU (real) yields
        bcp_series = {
            '2Y': BCChSeriesChile.BCP_2Y,
            '5Y': BCChSeriesChile.BCP_5Y,
            '10Y': BCChSeriesChile.BCP_10Y,
        }
        
        bcu_series = {
            '2Y': BCChSeriesChile.BCU_2Y,
            '5Y': BCChSeriesChile.BCU_5Y,
            '10Y': BCChSeriesChile.BCU_10Y,
            '20Y': BCChSeriesChile.BCU_20Y,
            '30Y': BCChSeriesChile.BCU_30Y,
        }
        
        # Fetch nominal rates (BCP)
        for tenor, series_id in bcp_series.items():
            value = self.bcch.get_latest_value(series_id)
            if value is not None:
                result['nominal_curve'][tenor] = round(value, 3)
                print(f"  OK: BCP {tenor}: {value:.3f}%")
        
        # Fetch real rates (BCU)
        for tenor, series_id in bcu_series.items():
            value = self.bcch.get_latest_value(series_id)
            if value is not None:
                result['real_curve'][tenor] = round(value, 3)
                print(f"  OK: BCU {tenor}: {value:.3f}%")
        
        # Calculate breakevens where we have both
        for tenor in ['2Y', '5Y', '10Y']:
            bcp = result['nominal_curve'].get(tenor)
            bcu = result['real_curve'].get(tenor)
            
            if bcp is not None and bcu is not None:
                breakeven = round(bcp - bcu, 3)
                result['breakevens'][tenor] = breakeven
                print(f"  OK: Breakeven {tenor}: {breakeven:.2f}%")
        
        # UF analysis (realized inflation)
        result['uf_analysis'] = self._analyze_uf()
        
        # Assessment
        result['assessment'] = self._assess_inflation_expectations(result)
        
        result['as_of'] = datetime.now().isoformat()
        
        return result
    
    def _analyze_uf(self) -> Dict:
        """Analyze UF (inflation-linked unit) dynamics"""
        try:
            uf_series = self.bcch.get_series(BCChSeriesChile.UF, days_back=400)
            
            if uf_series is None or len(uf_series) < 30:
                return {}
            
            current_uf = uf_series.iloc[-1]
            
            # Monthly change (approx)
            uf_30d_ago = uf_series.iloc[-30] if len(uf_series) >= 30 else uf_series.iloc[0]
            monthly_change = (current_uf / uf_30d_ago - 1) * 100
            
            # YoY change
            uf_1y_ago = uf_series.iloc[-365] if len(uf_series) >= 365 else uf_series.iloc[0]
            yoy_change = (current_uf / uf_1y_ago - 1) * 100
            
            return {
                'current_uf': round(current_uf, 2),
                'monthly_change_pct': round(monthly_change, 2),
                'yoy_change_pct': round(yoy_change, 2),
                'annualized_monthly': round(monthly_change * 12, 2)
            }
            
        except Exception as e:
            print(f"  ERR: Error analyzing UF: {e}")
            return {}
    
    def _assess_inflation_expectations(self, data: Dict) -> Dict:
        """Assess inflation expectations vs target"""
        assessment = {}
        
        # BCCh inflation target: 3% +/- 1%
        target = 3.0
        tolerance = 1.0
        
        be_5y = data['breakevens'].get('5Y')
        if be_5y is not None:
            if be_5y > target + tolerance:
                assessment['5y_signal'] = 'ABOVE_TARGET'
                assessment['5y_interpretation'] = 'Market expects inflation above BCCh target'
            elif be_5y < target - tolerance:
                assessment['5y_signal'] = 'BELOW_TARGET'
                assessment['5y_interpretation'] = 'Market expects inflation below BCCh target'
            else:
                assessment['5y_signal'] = 'ON_TARGET'
                assessment['5y_interpretation'] = 'Market expects inflation near BCCh target'
        
        # Compare breakeven vs realized (UF)
        uf_yoy = data['uf_analysis'].get('yoy_change_pct')
        if be_5y is not None and uf_yoy is not None:
            diff = be_5y - uf_yoy
            if diff > 0.5:
                assessment['be_vs_realized'] = 'Market expects inflation to RISE'
            elif diff < -0.5:
                assessment['be_vs_realized'] = 'Market expects inflation to FALL'
            else:
                assessment['be_vs_realized'] = 'Market expects inflation to remain STABLE'
        
        return assessment
    
    # =========================================================================
    # CARRY TRADE ANALYSIS
    # =========================================================================
    
    def get_carry_trade_analysis(self) -> Dict[str, Any]:
        """
        Analyze Chile vs USA carry trade opportunity
        
        Returns:
            Dict with rate differential, FX, and carry assessment
        """
        print("[Chile] Analyzing carry trade...")
        
        # Get TPM Chile
        tpm_chile = self.bcch.get_latest_value(BCChSeriesChile.TPM)
        
        # Get Fed Funds USA (from FRED)
        fed_funds = self.fred.get_latest_value('DFF')
        
        # Get USD/CLP
        usd_clp = self.bcch.get_latest_value(BCChSeriesChile.USD_CLP)
        
        if tpm_chile is None or fed_funds is None:
            return {'error': 'Could not fetch rate data'}
        
        # Calculate differential
        rate_diff = tpm_chile - fed_funds
        
        # Get 1Y forward implied from swap curve
        spc_1y = self.bcch.get_latest_value(BCChSeriesChile.SPC_360D)
        
        # Assess carry attractiveness
        if rate_diff > 3.0:
            attractiveness = 'HIGH'
            recommendation = 'Attractive carry; consider long CLP position with hedge'
        elif rate_diff > 1.5:
            attractiveness = 'MEDIUM'
            recommendation = 'Moderate carry; selective opportunities'
        elif rate_diff > 0:
            attractiveness = 'LOW'
            recommendation = 'Limited carry; FX risk may not compensate'
        else:
            attractiveness = 'NEGATIVE'
            recommendation = 'Negative carry; avoid long CLP unhedged'
        
        # Historical context
        historical = self._get_historical_carry_context()
        
        result = {
            'rates': {
                'tpm_chile': tpm_chile,
                'fed_funds_usa': fed_funds,
                'differential_bps': round(rate_diff * 100, 0),
                'spc_1y_chile': spc_1y
            },
            'fx': {
                'usd_clp_spot': usd_clp,
            },
            'assessment': {
                'attractiveness': attractiveness,
                'recommendation': recommendation
            },
            'historical_context': historical,
            'as_of': datetime.now().isoformat()
        }
        
        print(f"  OK: TPM Chile: {tpm_chile}%")
        print(f"  OK: Fed Funds: {fed_funds}%")
        print(f"  OK: Differential: {rate_diff*100:.0f}bps")
        print(f"  OK: Attractiveness: {attractiveness}")
        
        return result
    
    def _get_historical_carry_context(self) -> Dict:
        """Get historical context for carry trade"""
        try:
            # Get historical TPM
            tpm_series = self.bcch.get_series(BCChSeriesChile.TPM, days_back=365*3)
            
            if tpm_series is not None and len(tpm_series) > 0:
                return {
                    'tpm_3y_high': round(tpm_series.max(), 2),
                    'tpm_3y_low': round(tpm_series.min(), 2),
                    'tpm_3y_avg': round(tpm_series.mean(), 2),
                    'current_vs_3y_avg': 'ABOVE' if tpm_series.iloc[-1] > tpm_series.mean() else 'BELOW'
                }
        except Exception:
            pass
        return {}
    
    # =========================================================================
    # IPSA SECTOR ANALYSIS (via Yahoo Finance)
    # =========================================================================
    
    def get_ipsa_sector_analysis(self) -> Dict[str, Any]:
        """
        Analyze Chilean equity sectors via Yahoo Finance
        
        Returns:
            Dict with sector performance and recommendations
        """
        print("[Chile] Analyzing IPSA sectors...")
        
        try:
            import yfinance as yf
        except ImportError:
            return {'error': 'yfinance not installed. pip install yfinance'}
        
        sectors = {}
        
        for sector_name, stocks in YahooTickersChile.SECTORS.items():
            sector_data = {
                'stocks': {},
                'avg_return_1m': None,
                'avg_return_ytd': None
            }
            
            returns_1m = []
            returns_ytd = []
            
            for stock_name in stocks:
                ticker = YahooTickersChile.STOCKS.get(stock_name)
                if ticker is None:
                    continue
                
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1y')
                    
                    if len(hist) > 0:
                        # Current price
                        current_price = hist['Close'].iloc[-1]
                        
                        # 1M return
                        if len(hist) >= 21:
                            price_1m = hist['Close'].iloc[-21]
                            ret_1m = (current_price / price_1m - 1) * 100
                            returns_1m.append(ret_1m)
                        else:
                            ret_1m = None
                        
                        # YTD return (approximate)
                        price_start = hist['Close'].iloc[0]
                        ret_ytd = (current_price / price_start - 1) * 100
                        returns_ytd.append(ret_ytd)
                        
                        sector_data['stocks'][stock_name] = {
                            'ticker': ticker,
                            'price': round(current_price, 0),
                            'return_1m': round(ret_1m, 1) if ret_1m else None,
                            'return_ytd': round(ret_ytd, 1)
                        }
                        
                        print(f"  OK: {stock_name}: ${current_price:.0f} ({ret_1m:+.1f}% 1M)" if ret_1m else f"  OK: {stock_name}: ${current_price:.0f}")
                        
                except Exception as e:
                    print(f"  ERR: {stock_name}: {e}")
            
            # Calculate sector averages
            if returns_1m:
                sector_data['avg_return_1m'] = round(np.mean(returns_1m), 1)
            if returns_ytd:
                sector_data['avg_return_ytd'] = round(np.mean(returns_ytd), 1)
            
            sectors[sector_name] = sector_data
        
        # Rank sectors
        sector_ranking = sorted(
            [(name, data['avg_return_1m']) for name, data in sectors.items() if data['avg_return_1m'] is not None],
            key=lambda x: x[1] if x[1] else -999,
            reverse=True
        )
        
        # Get ECH (Chile ETF) for comparison
        ech_data = None
        try:
            ech = yf.Ticker('ECH')
            ech_hist = ech.history(period='1y')
            if len(ech_hist) > 0:
                ech_current = ech_hist['Close'].iloc[-1]
                ech_1m = ech_hist['Close'].iloc[-21] if len(ech_hist) >= 21 else ech_hist['Close'].iloc[0]
                ech_data = {
                    'price': round(ech_current, 2),
                    'return_1m': round((ech_current / ech_1m - 1) * 100, 1)
                }
                print(f"  OK: ECH (Chile ETF): ${ech_current:.2f} ({ech_data['return_1m']:+.1f}% 1M)")
        except Exception:
            pass
        
        return {
            'sectors': sectors,
            'sector_ranking': sector_ranking,
            'ech_etf': ech_data,
            'as_of': datetime.now().isoformat()
        }
    
    # =========================================================================
    # COMPREHENSIVE DASHBOARD
    # =========================================================================
    
    def get_chile_dashboard(self) -> Dict[str, Any]:
        """
        Generate comprehensive Chile dashboard
        
        Returns:
            Dict with all Chile analytics
        """
        print("=" * 50)
        print("CHILE PROFUNDO - COMPREHENSIVE DASHBOARD")
        print("=" * 50)
        
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            
            # Macro
            'macro': self.get_macro_snapshot(),
            
            # Rates
            'camara_curve': self.get_camara_curve(),
            
            # Inflation
            'breakeven_inflation': self.get_breakeven_inflation(),
            
            # Carry
            'carry_trade': self.get_carry_trade_analysis(),
            
            # Summary
            'summary': {}
        }
        
        # Generate summary
        dashboard['summary'] = self._generate_summary(dashboard)
        
        return dashboard
    
    def _generate_summary(self, dashboard: Dict) -> Dict:
        """Generate executive summary from all data"""
        summary = {
            'key_metrics': {},
            'signals': [],
            'recommendations': []
        }
        
        # Key metrics
        macro = dashboard.get('macro', {})
        summary['key_metrics'] = {
            'tpm': macro.get('tpm'),
            'real_tpm': macro.get('real_tpm'),
            'ipc_yoy': macro.get('ipc'),
            'usd_clp': macro.get('usd_clp'),
            'policy_stance': macro.get('policy_stance')
        }
        
        # Signals
        be = dashboard.get('breakeven_inflation', {})
        if be.get('assessment', {}).get('5y_signal'):
            summary['signals'].append(
                f"Inflation expectations: {be['assessment']['5y_signal']}"
            )
        
        curve = dashboard.get('camara_curve', {})
        if curve.get('shape'):
            summary['signals'].append(f"Swap curve: {curve['shape']}")
        
        carry = dashboard.get('carry_trade', {})
        if carry.get('assessment', {}).get('attractiveness'):
            summary['signals'].append(
                f"Carry attractiveness: {carry['assessment']['attractiveness']}"
            )
        
        # Recommendations based on data
        policy = macro.get('policy_stance')
        if policy == 'RESTRICTIVE':
            summary['recommendations'].append(
                "Duration: Consider extending - policy likely to ease"
            )
        elif policy == 'ACCOMMODATIVE':
            summary['recommendations'].append(
                "Duration: Stay short - policy may tighten"
            )
        
        return summary


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GREY BARK - CHILE PROFUNDO TEST")
    print("=" * 60)
    
    # Test initialization
    analytics = ChileAnalytics()
    
    print("\n--- Testing Module Structure ---")
    print("OK: ChileAnalytics class loaded")
    print("OK: BCChSeriesChile constants defined")
    print("OK: YahooTickersChile constants defined")
    
    print("\n--- Available Methods ---")
    methods = [m for m in dir(analytics) if not m.startswith('_') and callable(getattr(analytics, m))]
    for method in methods:
        print(f"  • {method}()")
    
    print("\n✅ Chile Profundo module loaded successfully")
    print("\nNote: API calls require network access to BCCh and Yahoo Finance")

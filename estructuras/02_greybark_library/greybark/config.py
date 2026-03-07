# -*- coding: utf-8 -*-
"""
Greybark Research - Configuration
Credenciales y configuracion centralizada

ACTUALIZADO: Feb 2026 - 93+ series BCCh
Credentials loaded from .env file (never hardcoded).
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root (wealth/)
_env_path = Path(__file__).resolve().parents[3] / '.env'
load_dotenv(_env_path)


# =============================================================================
# API CONFIGURATIONS
# =============================================================================

@dataclass
class ClaudeConfig:
    """Anthropic Claude API Configuration"""
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4000

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv('ANTHROPIC_API_KEY', '')


CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')


@dataclass
class FREDConfig:
    """FRED API Configuration"""
    api_key: str = ""
    base_url: str = "https://fred.stlouisfed.org"

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv('FRED_API_KEY', '')


@dataclass
class BCChConfig:
    """Banco Central de Chile REST API Configuration"""
    user: str = ""
    password: str = ""
    rest_url: str = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

    def __post_init__(self):
        if not self.user:
            self.user = os.getenv('BCCH_USER', '')
        if not self.password:
            self.password = os.getenv('BCCH_PASSWORD', '')


@dataclass
class AlphaVantageConfig:
    """AlphaVantage API Configuration (Premium)"""
    api_key: str = ""
    base_url: str = "https://www.alphavantage.co/query"
    plan: str = "Premium"
    monthly_cost: float = 49.99

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv('ALPHAVANTAGE_API_KEY', '')


@dataclass
class BEAConfig:
    """Bureau of Economic Analysis API Configuration"""
    api_key: str = ""
    base_url: str = "https://apps.bea.gov/api/data/"

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv('BEA_API_KEY', '')


@dataclass
class CommLoanConfig:
    """CommLoan SOFR Scraper Configuration"""
    url: str = "https://www.commloan.com/research/rate-calculator/"
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class Config:
    """Main Configuration Class"""
    fred: FREDConfig = None
    bcch: BCChConfig = None
    alphavantage: AlphaVantageConfig = None
    bea: BEAConfig = None
    commloan: CommLoanConfig = None

    def __post_init__(self):
        self.fred = FREDConfig()
        self.bcch = BCChConfig()
        self.alphavantage = AlphaVantageConfig()
        self.bea = BEAConfig()
        self.commloan = CommLoanConfig()

    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables (default behavior)"""
        return cls()


config = Config()


# =============================================================================
# FRED SERIES IDs
# =============================================================================

class FREDSeries:
    """FRED Series IDs - US Data"""

    # Macro
    CORE_CPI = "CPILFESL"
    HEADLINE_CPI = "CPIAUCSL"
    UNEMPLOYMENT = "UNRATE"
    PAYROLLS = "PAYEMS"
    GDP = "GDPC1"
    FED_FUNDS = "DFF"
    TREASURY_2Y = "DGS2"
    TREASURY_10Y = "DGS10"
    TREASURY_30Y = "DGS30"

    # Regime Classification
    HY_SPREADS = "BAMLH0A0HYM2"
    CONSUMER_CONFIDENCE = "CSCICP03USM665S"
    ISM_NEW_ORDERS = "NEWORDER"
    M2_MONEY_SUPPLY = "M2SL"
    INITIAL_CLAIMS = "IC4WSA"

    # Fed Dots
    FED_DOTS_MEDIAN = "FEDTARMD"
    FED_DOTS_MEDIAN_LR = "FEDTARMDLR"
    FED_DOTS_RANGE_HIGH = "FEDTARRH"
    FED_DOTS_RANGE_LOW = "FEDTARRL"
    FED_DOTS_RANGE_HIGH_LR = "FEDTARRHLR"
    FED_DOTS_RANGE_LOW_LR = "FEDTARRLLR"

    # Extended US Macro
    BUILDING_PERMITS = "PERMIT"
    UMICH_SENTIMENT = "UMCSENT"
    LEADING_INDEX = "USSLIND"  # discontinued Feb 2020
    LEADING_INDEX_OECD = "USALOLITOAASTSAM"  # OECD CLI USA Amplitude Adjusted (active)
    LEADING_INDEX_EZ = "BSCICP02EZM460S"  # OECD Business Confidence Euro Area (leading proxy)
    CONSUMER_CONFIDENCE_EZ = "CSCICP02EZM460S"  # Consumer Confidence Euro Area
    CONTINUING_CLAIMS = "CCSA"
    JOB_OPENINGS = "JTSJOL"
    QUITS_RATE = "JTSQUR"
    CORE_PCE = "PCEPILFE"
    PPI = "PPIACO"
    PERSONAL_INCOME = "PI"
    PERSONAL_SPENDING = "PCE"
    NEW_HOME_SALES = "HSN1F"
    EXISTING_HOME_SALES = "EXHOSLUSM495S"
    CASE_SHILLER = "CSUSHPINSA"
    TRADE_BALANCE = "BOPGSTB"
    CHICAGO_FED_FCI = "NFCI"
    STL_FIN_STRESS = "STLFSI4"
    CONSUMER_CREDIT = "TOTALSL"
    COMMERCIAL_LOANS = "BUSLOANS"

    # Labor Market Extended
    U6_RATE = "U6RATE"
    AHE = "CES0500000003"            # Average Hourly Earnings
    CIVPART = "CIVPART"              # Labor Force Participation Rate
    PRIME_AGE_EPOP = "LNS12300060"   # Prime-Age (25-54) Employment-Population Ratio
    ECI_WAGES = "ECIWAG"             # Employment Cost Index - Wages

    # Treasury Curve (short end + mid)
    TREASURY_1MO = "DGS1MO"
    TREASURY_3MO = "DGS3MO"
    TREASURY_6MO = "DGS6MO"
    TREASURY_1Y = "DGS1"
    TREASURY_5Y = "DGS5"

    # Housing
    HOUSING_STARTS = "HOUST"

    # Forecast Engine — Expectations & Nowcasts
    GDPNOW = "GDPNOW"                   # Atlanta Fed GDP Nowcast (real-time)
    EXPINF1YR = "EXPINF1YR"             # Cleveland Fed 1Y expected inflation
    EXPINF10YR = "EXPINF10YR"           # Cleveland Fed 10Y expected inflation
    T10Y2Y = "T10Y2Y"                   # 10Y-2Y spread (direct)
    RECESSION_PROB = "RECPROUSM156N"    # Smoothed recession probability
    BREAKEVEN_5Y = "T5YIE"             # 5Y breakeven inflation
    BREAKEVEN_10Y = "T10YIE"           # 10Y breakeven inflation
    MICHIGAN_1Y = "MICH"               # Michigan 1Y inflation expectations

    # CPI Components (for detailed inflation breakdown)
    CPI_SHELTER = "CUSR0000SAH1"           # CPI Shelter YoY
    CPI_SERVICES_EX_ENERGY = "CUSR0000SASLE"  # CPI Services Less Energy Services
    CPI_COMMODITIES_EX_FOOD_ENERGY = "CUSR0000SACL1"  # CPI Commodities Less Food/Energy
    CPI_FOOD = "CPIUFDSL"                  # CPI Food
    CPI_ENERGY = "CPIENGSL"                # CPI Energy

    # US Fiscal
    DEFICIT_GDP = "FYFSGDA188S"            # Federal Surplus/Deficit % GDP
    DEBT_GDP = "GFDEGDQ188S"              # Federal Debt % GDP
    INTEREST_GDP = "FYOIGDA188S"            # Federal Outlays: Interest as % GDP (annual)

    # Financial Conditions
    # STL_FIN_STRESS already defined above as STLFSI4
    # LEADING_INDEX already defined above as USSLIND


# =============================================================================
# BCCh SERIES IDs - COMPREHENSIVE (93+ series)
# =============================================================================

class BCChSeries:
    """BCCh REST API Series IDs - Chile & International"""

    # =========================================================================
    # CHILE MACRO
    # =========================================================================

    # Politica Monetaria
    TPM = "F022.TPM.TIN.D001.NO.Z.D"

    # Precios
    IPC_VAR = "F074.IPC.VAR.Z.Z.C.M"          # IPC variacion mensual
    IPC_EXP = "F089.IPC.VAR.11.M"              # IPC expectativa EEE

    # EEE Forecasts (Encuesta de Expectativas Económicas)
    EEE_PIB_ACTUAL = "F089.PIB.VAR.Z.M"       # EEE PIB año actual
    EEE_PIB_SIGUIENTE = "F089.PIB.VAR.Z1.M"   # EEE PIB año siguiente
    EEE_IPC_12M = "F089.IPC.V12.Z.M"          # EEE IPC 12 meses
    EEE_IPC_24M = "F089.IPC.V24.Z.M"          # EEE IPC 24 meses
    EEE_TCN_12M = "F089.TCN.VAL.Z.M"          # EEE USD/CLP 12 meses

    # Actividad
    IMACEC_YOY = "F032.IMC.V12.Z.Z.2018.Z.Z.0.M"
    IMACEC_NOMIN_YOY = "F032.IMC.V12.Z.Z.2018.N03.Z.0.M"
    IMACEC_MOM_SA = "F032.IMC.VAR.Z.Z.2018.Z.Z.3.M"

    # Empleo
    DESEMPLEO = "F049.DES.TAS.INE.10.M"

    # Tipo de Cambio
    USD_CLP = "F073.TCO.PRE.Z.D"
    UF = "F073.UFF.PRE.Z.D"

    # Confianza
    IPEC = "F089.IPE.IND.75M2.M"               # Percepcion economia
    IMCE_TOTAL = "G089.IME.IND.A0.M"           # IMCE Total (confianza empresarial)
    IMCE_SIN_MINERIA = "G089.IME.IND.A04.M"    # IMCE Sin Mineria

    # IPC Detalle Chile (base 2023=100)
    IPC_SAE = "F074.IPCSAE.VAR.Z.2023.C.M"     # IPC sin alimentos y energia (core)
    IPC_SERVICIOS = "F074.IPCS.VAR.Z.2023.C.M" # IPC Servicios
    IPC_BIENES = "F074.IPCB.VAR.Z.2023.C.M"    # IPC Bienes
    IPC_ENERGIA = "F074.IPCE.VAR.Z.2023.C.M"   # IPC Energia

    # EEE Largo Plazo (parametros estructurales)
    EEE_IPC_LP = "F089.IPC.V12.LP.M"           # Inflacion promedio largo plazo
    EEE_TPM_LP = "F089.TPM.TAS.LP.M"           # TPM promedio largo plazo (tasa neutral)
    EEE_PIB_LP = "F089.PIB.V12.LP.M"           # PIB promedio largo plazo (crecimiento potencial)
    EEE_TCN_LP = "F089.TCN.V12.LP.M"           # Tipo cambio largo plazo

    # EEE Expectativas TPM por horizonte
    EEE_TPM_PROX_REUNION = "F089.TPM.TAS.11.M" # TPM siguiente reunion
    EEE_TPM_11M = "F089.TPM.TAS.14.M"          # TPM en 11 meses
    EEE_TPM_23M = "F089.TPM.TAS.15.M"          # TPM en 23 meses

    # EOF - Encuesta Operadores Financieros (mayor frecuencia)
    EOF_TPM_12M = "F089.EOF.TPM.12MS.D"         # TPM 12 meses (operadores)
    EOF_TPM_24M = "F089.EOF.TPM.24MS.D"         # TPM 24 meses (operadores)
    EOF_IPC_12M = "F089.EOF.VII.12MS.D"         # Inflacion 12 meses (operadores)
    EOF_BTP_5Y = "F089.EOF.RF_BTP_5Y.14D.D"    # Exp tasa BTP 5Y
    EOF_BTP_10Y = "F089.EOF.RF_BTP_10Y.14D.D"  # Exp tasa BTP 10Y
    EOF_BTU_5Y = "F089.EOF.RF_BTU_5Y.14D.D"    # Exp tasa BTU 5Y
    EOF_BTU_10Y = "F089.EOF.RF_BTU_10Y.14D.D"  # Exp tasa BTU 10Y
    EOF_TC_28D = "F089.EOF.TC.28DA.D"           # Exp USD/CLP 28 dias
    EOF_TC_3M = "F089.EOF.TC.7MA.D"             # Exp USD/CLP 3 meses

    # EEE Tipo de cambio
    EEE_TCN_11M = "F089.TCN.PRE.14.M"          # EEE USD/CLP 11 meses

    # =========================================================================
    # CHILE ACTIVIDAD SECTORIAL
    # =========================================================================

    PROD_INDUSTRIAL = "F034.PRN.IND.INE.2018.0.M"
    PROD_MANUFACTURA = "F034.PRM.IND.INE.2018.0.M"
    PROD_MINERIA = "F034.PMI.IND.INE.2018.0.M"
    PROD_ELECTRICIDAD = "F034.PEGA.IND.INE.2018.0.M"
    PROD_COBRE = "F034.PCUM.FLU.COCHILCO.Z.0.M"

    # =========================================================================
    # CHILE COMERCIO Y CONSUMO
    # =========================================================================

    VENTAS_COMERCIO_DIA = "F034.VDCM.IND.DBC.2018.0.D"
    VENTAS_COMERCIO_MES = "F034.VDCM.IND.DBC.2018.0.M"
    VENTAS_COMERCIO_YOY = "F034.VDCM.TAS12M.DBC.2018.0.M"
    VENTAS_AUTOS = "F034.VAN.FLU.ANAC.2011.0.M"

    # =========================================================================
    # CHILE COMERCIO EXTERIOR
    # =========================================================================

    EXPORTACIONES = "F068.B1.FLU.Z.0.C.N.Z.Z.Z.Z.6.0.M"
    IMPORTACIONES = "F068.B1.FLU.Z.0.D.N.0.T.Z.Z.6.0.M"
    IMP_CAPITAL = "F068.B1.FLU.Z.0.M.N.K.Z.Z.Z.6.0.M"

    # =========================================================================
    # CHILE CURVA SPC (Swap Promedio Camara)
    # =========================================================================

    SPC_30D = "F022.SPC.TPR.D030.NO.Z.D"
    SPC_90D = "F022.SPC.TPR.D090.NO.Z.D"
    SPC_180D = "F022.SPC.TPR.D180.NO.Z.D"
    SPC_360D = "F022.SPC.TPR.D360.NO.Z.D"
    SPC_2Y = "F022.SPC.TIN.AN02.NO.Z.D"
    SPC_3Y = "F022.SPC.TIN.AN03.NO.Z.D"
    SPC_5Y = "F022.SPC.TIN.AN05.NO.Z.D"
    SPC_10Y = "F022.SPC.TIN.AN10.NO.Z.D"

    # =========================================================================
    # CHILE TASAS SISTEMA FINANCIERO
    # =========================================================================

    TASA_CONSUMO = "F022.CON.TIP.Z.NO.Z.D"
    TASA_VIVIENDA = "F022.VIV.TIP.MA03.UF.Z.D"
    TASA_COMERCIAL_30D = "F022.COM.TIP.P30.NO.Z.D"

    # =========================================================================
    # CHILE COLOCACIONES (Stock de Credito)
    # =========================================================================

    COLOC_TOTAL = "F022.COL.PRO.Z.Z.CLP.D"
    COLOC_COMERCIAL = "F022.COLCOM.PRO.Z.Z.CLP.D"
    COLOC_CONSUMO = "F022.COLCONS.PRO.Z.Z.CLP.D"
    COLOC_VIVIENDA = "F022.COLVIV.PRO.Z.Z.CLP.D"

    # =========================================================================
    # COMMODITIES
    # =========================================================================

    COBRE = "F019.PPB.PRE.40.M"
    ORO = "F019.PPB.PRE.44B.M"
    PLATA = "F019.PPB.PRE.45B.M"
    WTI = "F019.PPB.PRE.41B.M"
    BRENT = "F019.PPB.PRE.41AB.M"
    LITIO = "F019.PPB.PRE.37.D"
    GAS_NATURAL = "F019.PPB.PRE.49B.M"
    DIESEL = "F019.PPB.PRE.35B.M"
    COBRE_DIARIO = "F019.PPB.PRE.100.D"
    ORO_DIARIO = "F019.PPB.PRE.44.D"

    # =========================================================================
    # VOLATILIDAD Y RIESGO
    # =========================================================================

    VIX = "F019.VIX.IND.90.D"
    MOVE = "F019.MOVE.IND.90.D"
    EPU_CHILE = "F019.EPU.IND.91.M"
    EPU_CHINA = "F019.EPU.IND.CHN.M"
    EPU_USA = "F019.EPU.IND.10.M"
    EPU_GLOBAL = "F019.EPU.IND.90.M"
    EPU_EUROPA = "F019.EPU.IND.94.M"
    EPU_UK = "F019.EPU.IND.UK.M"

    # =========================================================================
    # BOLSAS INTERNACIONALES
    # =========================================================================

    IPSA = "F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D"
    SP500 = "F019.IBC.IND.50.D"
    NASDAQ = "F019.IBC.IND.51.D"
    DAX = "F019.IBC.IND.55.D"
    SHANGHAI = "F019.IBC.IND.CHN.D"
    BOVESPA = "F019.IBC.IND.BRA.D"
    IPC_MEXICO = "F019.IBC.IND.MEX.D"

    # =========================================================================
    # INFLACION INTERNACIONAL (YoY)
    # =========================================================================

    IPC_INTL_USA = "F019.IPC.V12.10.M"
    IPC_INTL_EUROZONA = "F019.IPC.V12.20.M"
    IPC_INTL_CHINA = "F019.IPC.V12.31.M"
    IPC_INTL_JAPON = "F019.IPC.V12.30.M"
    IPC_INTL_UK = "F019.IPC.V12.UK.M"
    IPC_INTL_BRASIL = "F019.IPC.V12.12.M"
    IPC_INTL_MEXICO = "F019.IPC.V12.13.M"
    IPC_INTL_ARGENTINA = "F019.IPC.V12.ARG.M"
    IPC_INTL_PERU = "F019.IPC.V12.PER.M"
    IPC_INTL_COLOMBIA = "F019.IPC.V12.COL.M"

    # =========================================================================
    # INFLACION CORE INTERNACIONAL
    # =========================================================================

    CORE_INTL_USA = "F019.IPS.V12.10.M"
    CORE_INTL_EUROZONA = "F019.IPS.V12.20.M"
    CORE_INTL_CHINA = "F019.IPS.V12.CHN.M"
    CORE_INTL_JAPON = "F019.IPS.V12.30.M"
    CORE_INTL_UK = "F019.IPS.V12.UK.M"
    CORE_INTL_BRASIL = "F019.IPS.V12.BRA.M"
    CORE_INTL_MEXICO = "F019.IPS.V12.MEX.M"

    # =========================================================================
    # BONOS 10Y INTERNACIONAL
    # =========================================================================

    BOND10_USA = "F019.TBG.TAS.10.D"
    BOND10_EUROZONA = "F019.TBG.TAS.20.D"
    BOND10_JAPON = "F019.TBG.TAS.30.D"
    BOND10_UK = "F019.TBG.TAS.UK.D"
    BOND10_BRASIL = "F019.TBG.TAS.BRA.D"
    BOND10_MEXICO = "F019.TBG.TAS.MEX.D"
    BOND10_PERU = "F019.TBG.TAS.PER.D"
    BOND10_COLOMBIA = "F019.TBG.TAS.COL.D"
    BOND10_CHILE = "F022.BCLP.TIS.AN10.NO.Z.D"

    # =========================================================================
    # TPM INTERNACIONAL
    # =========================================================================

    TPM_USA = "F019.TPM.TIN.10.D"
    TPM_EUROZONA = "F019.TPM.TIN.GE.D"
    TPM_JAPON = "F019.TPM.TIN.30.D"
    TPM_UK = "F019.TPM.TIN.UK.D"
    TPM_CHINA = "F019.TPM.TIN.CHN.D"
    TPM_BRASIL = "F019.TPM.TIN.BRA.D"
    TPM_MEXICO = "F019.TPM.TIN.MEX.D"
    TPM_PERU = "F019.TPM.TIN.PER.D"
    TPM_COLOMBIA = "F019.TPM.TIN.COL.D"
    TPM_ARGENTINA = "F019.TPM.TIN.ARG.D"

    # =========================================================================
    # GDP INTERNACIONAL (QoQ %, trimestral)
    # =========================================================================

    GDP_EUROZONA = "F019.PIB.VAR.20.T"      # Eurozone GDP QoQ %
    GDP_ALEMANIA = "F019.PIB.VAR.GE.T"      # Germany GDP QoQ %
    GDP_FRANCIA = "F019.PIB.VAR.FR.T"       # France GDP QoQ %
    GDP_UK = "F019.PIB.VAR.UK.T"            # UK GDP QoQ %
    GDP_JAPON = "F019.PIB.VAR.30.T"         # Japan GDP QoQ %
    GDP_CHINA = "F019.PIB.VAR.CHN.T"        # China GDP QoQ %

    # =========================================================================
    # DESEMPLEO INTERNACIONAL (%, mensual)
    # =========================================================================

    DESEMP_EUROZONA = "F019.DES.TAS.20.M"   # Eurozone unemployment
    DESEMP_ALEMANIA = "F019.DES.TAS.GE.M"   # Germany unemployment
    DESEMP_UK = "F019.DES.TAS.UK.M"         # UK unemployment
    DESEMP_JAPON = "F019.DES.TAS.30.M"      # Japan unemployment
    DESEMP_CHINA = "F019.DES.TAS.CHN.M"     # China urban unemployment

    # =========================================================================
    # PPI INTERNACIONAL (YoY %, mensual)
    # =========================================================================

    PPI_EUROZONA = "F019.IPP.V12.20.M"      # Eurozone PPI YoY
    PPI_CHINA = "F019.IPP.V12.CHN.M"        # China PPI YoY

    # =========================================================================
    # TIPOS DE CAMBIO ADICIONALES
    # =========================================================================

    EUR_USD = "F072.EUR.USD.N.O.D"           # EUR/USD
    CNY_USD = "F072.CNY.USD.N.O.D"           # CNY/USD


# =============================================================================
# CONSTANTS
# =============================================================================

SOFR_FED_SPREAD = 0.08
RATE_INCREMENT = 0.25
DEFAULT_LOOKBACK_DAYS = 120          # For get_latest() — only need recent data
DEFAULT_HISTORY_DAYS = 3650          # ~10 years — for full time series
HISTORICAL_PERCENTILE_YEARS = 10     # For VIX/spread percentile calculations

# 2026 FOMC Schedule (public calendar — update annually)
FOMC_2026 = [
    ('Jan 28-29', 'Jan'),
    ('Mar 18-19', 'Mar'),
    ('May 6-7', 'May'),
    ('Jun 17-18', 'Jun'),
    ('Jul 29-30', 'Jul'),
    ('Sep 16-17', 'Sep'),
    ('Oct 28-29', 'Oct'),
    ('Dec 9-10', 'Dec'),
]

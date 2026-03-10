# -*- coding: utf-8 -*-
"""
Greybark Research - Data Manifest
==================================

Defines formally what data each agent needs, with 3 priority levels.
Used by data_completeness_validator.py to check field-by-field coverage
and by ai_council_runner.py to build structured data inventory prompts.

Each DataField specifies:
- path: dot-notation into agent_data (e.g. "macro_usa.gdp")
- label: human-readable name for prompts
- source: API source identifier
- unit: display unit
- priority: REQUIRED / IMPORTANT / OPTIONAL
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List


class FieldPriority(Enum):
    REQUIRED = "required"       # Agent cannot function without this
    IMPORTANT = "important"     # Significantly degrades if missing
    OPTIONAL = "optional"       # Nice-to-have


@dataclass
class DataField:
    path: str           # Dot-path in agent_data: "macro_usa.gdp"
    label: str          # Human-readable: "GDP USA Real QoQ"
    source: str         # API source: "FRED:GDPC1" or "BCCh:F032..." or "yfinance:SPY"
    unit: str           # "%", "bps", "level", "x", "index"
    priority: FieldPriority


# =============================================================================
# AGENT MANIFESTS
# =============================================================================

MACRO_MANIFEST: List[DataField] = [
    # --- REQUIRED ---
    DataField("regime.current_regime", "Regimen macro actual", "internal:regime_classification", "label", FieldPriority.REQUIRED),
    DataField("macro_usa.gdp", "GDP USA Real QoQ", "FRED:GDPC1", "%", FieldPriority.REQUIRED),
    DataField("macro_usa.unemployment", "Desempleo USA U3", "FRED:UNRATE", "%", FieldPriority.REQUIRED),
    DataField("inflation.cpi_core_yoy", "CPI Core USA YoY", "FRED:CPILFESL", "%", FieldPriority.REQUIRED),
    DataField("inflation.cpi_all_yoy", "CPI Headline USA YoY", "FRED:CPIAUCSL", "%", FieldPriority.REQUIRED),
    DataField("rates.terminal_rate", "Fed Funds Rate (terminal)", "internal:rate_expectations", "%", FieldPriority.REQUIRED),
    DataField("chile.tpm", "TPM Chile", "BCCh:TPM", "%", FieldPriority.REQUIRED),
    DataField("chile.imacec", "IMACEC Chile", "BCCh:IMACEC", "%", FieldPriority.REQUIRED),
    DataField("chile.ipc", "IPC Chile YoY", "BCCh:IPC", "%", FieldPriority.REQUIRED),
    # --- IMPORTANT ---
    DataField("inflation.breakeven_5y", "Breakeven 5Y USA", "FRED:T5YIE", "%", FieldPriority.IMPORTANT),
    DataField("inflation.breakeven_10y", "Breakeven 10Y USA", "FRED:T10YIE", "%", FieldPriority.IMPORTANT),
    DataField("macro_usa.ism_manufacturing", "ISM Manufacturing", "FRED:ISM/PMI", "index", FieldPriority.IMPORTANT),
    DataField("macro_usa.payrolls", "ADP/NFP Employment", "FRED:PAYEMS", "K", FieldPriority.IMPORTANT),
    DataField("macro_usa.jolts", "JOLTS Job Openings", "FRED:JTSJOL", "M", FieldPriority.IMPORTANT),
    DataField("rates.direction", "Expectativa de tasas Fed", "internal:rate_expectations", "label", FieldPriority.IMPORTANT),
    DataField("rates.cuts_expected", "Cortes esperados Fed", "internal:rate_expectations", "#", FieldPriority.IMPORTANT),
    DataField("fiscal.deficit_gdp", "Deficit fiscal USA (% GDP)", "FRED:fiscal", "%", FieldPriority.IMPORTANT),
    DataField("fiscal.debt_gdp", "Deuda publica USA (% GDP)", "FRED:fiscal", "%", FieldPriority.IMPORTANT),
    DataField("china.credit_impulse", "Impulso crediticio China", "internal:china_credit", "index", FieldPriority.IMPORTANT),
    DataField("china.epu_analysis.epu_level", "China EPU Index", "FRED:CHINAEPUINDXM", "index", FieldPriority.IMPORTANT),
    # EEE Expectations (BCCh Encuesta de Expectativas Economicas)
    DataField("chile_eee.ipc_12m", "Exp. inflacion Chile 12M (EEE)", "BCCh:F089.IPC.V12.Z.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.tpm_11m", "Exp. TPM 11 meses (EEE)", "BCCh:F089.TPM.TAS.14.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.tpm_lp", "Exp. TPM largo plazo (tasa neutral)", "BCCh:F089.TPM.TAS.LP.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.pib_actual", "Exp. PIB Chile año actual (EEE)", "BCCh:F089.PIB.VAR.Z.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.pib_lp", "Exp. PIB largo plazo (potencial)", "BCCh:F089.PIB.V12.LP.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.ipc_lp", "Exp. inflacion largo plazo (ancla)", "BCCh:F089.IPC.V12.LP.M", "%", FieldPriority.IMPORTANT),
    # IMCE Business Confidence (BCCh)
    DataField("chile_imce.imce_total", "IMCE Total (confianza empresarial)", "BCCh:G089.IME.IND.A0.M", "index", FieldPriority.IMPORTANT),
    DataField("chile_imce.imce_sin_mineria", "IMCE Sin Mineria", "BCCh:G089.IME.IND.A04.M", "index", FieldPriority.IMPORTANT),
    # IPC Detail Chile (BCCh)
    DataField("chile_ipc_detail.ipc_sae", "IPC SAE Chile (core)", "BCCh:F074.IPCSAE", "%", FieldPriority.IMPORTANT),
    DataField("chile_ipc_detail.ipc_servicios", "IPC Servicios Chile", "BCCh:F074.IPCS", "%", FieldPriority.IMPORTANT),
    # IMF WEO Consensus (via forecast_engine → imf_weo_client.py)
    DataField("forecasts.gdp.usa.consensus_imf", "Consenso IMF GDP USA", "IMF:WEO/NGDP_RPCH/USA", "%", FieldPriority.IMPORTANT),
    DataField("forecasts.gdp.chile.consensus_imf", "Consenso IMF GDP Chile", "IMF:WEO/NGDP_RPCH/CHL", "%", FieldPriority.IMPORTANT),
    DataField("forecasts.gdp.eurozone.consensus_imf", "Consenso IMF GDP Eurozona", "IMF:WEO/NGDP_RPCH/EURO", "%", FieldPriority.IMPORTANT),
    DataField("forecasts.gdp.china.consensus_imf", "Consenso IMF GDP China", "IMF:WEO/NGDP_RPCH/CHN", "%", FieldPriority.IMPORTANT),
    DataField("forecasts.inflation.usa.consensus_imf", "Consenso IMF Inflacion USA", "IMF:WEO/PCPIPCH/USA", "%", FieldPriority.IMPORTANT),
    DataField("forecasts.inflation.chile.consensus_imf", "Consenso IMF Inflacion Chile", "IMF:WEO/PCPIPCH/CHL", "%", FieldPriority.IMPORTANT),
    # ECB data (via bloomberg_reader → ecb_client.py, inside bloomberg_context string)
    DataField("bloomberg_context", "Bloomberg + ECB macro (PMI, ECB DFR, HICP, EA 10Y, EUR/USD, M3)", "Bloomberg+ECB:macro", "text", FieldPriority.IMPORTANT),
    # IPC Detail Chile (secondary components)
    DataField("chile_ipc_detail.ipc_bienes", "IPC Bienes Chile", "BCCh:F074.IPCB", "%", FieldPriority.IMPORTANT),
    DataField("chile_ipc_detail.ipc_energia", "IPC Energia Chile", "BCCh:F074.IPCE", "%", FieldPriority.IMPORTANT),
    # EEE additional horizons
    DataField("chile_eee.ipc_24m", "Exp. inflacion Chile 24M (EEE)", "BCCh:F089.IPC.V24.Z.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.tpm_23m", "Exp. TPM 23 meses (EEE)", "BCCh:F089.TPM.TAS.15.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.tpm_prox_reunion", "Exp. TPM prox reunion (EEE)", "BCCh:F089.TPM.TAS.11.M", "%", FieldPriority.IMPORTANT),
    DataField("chile_eee.tcn_12m", "Exp. USD/CLP 12M (EEE)", "BCCh:F089.TCN.VAL.Z.M", "CLP", FieldPriority.IMPORTANT),
    # Leading Economic Indicators (FRED)
    DataField("leading_indicators.lei_usa", "LEI USA (OECD CLI)", "FRED:USALOLITOAASTSAM", "index", FieldPriority.IMPORTANT),
    DataField("leading_indicators.lei_eurozone", "LEI Eurozone (Biz Confidence)", "FRED:BSCICP02EZM460S", "index", FieldPriority.IMPORTANT),
    DataField("leading_indicators.cfnai", "Chicago Fed Nat Activity Index", "FRED:CFNAI", "index", FieldPriority.IMPORTANT),
    DataField("leading_indicators.umich_sentiment", "U.Michigan Consumer Sentiment", "FRED:UMCSENT", "index", FieldPriority.OPTIONAL),
    DataField("leading_indicators.consumer_confidence_ez", "Consumer Confidence Euro Area", "FRED:CSCICP02EZM460S", "index", FieldPriority.OPTIONAL),
    # BEA (Bureau of Economic Analysis)
    DataField("bea_gdp.gdp_total", "Real GDP QoQ % (BEA)", "BEA:NIPA:T10101", "%", FieldPriority.IMPORTANT),
    DataField("bea_gdp.pce_total", "PCE contribution to GDP QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.IMPORTANT),
    DataField("bea_gdp.gross_private_investment", "Gross Private Investment QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.IMPORTANT),
    DataField("bea_gdp.net_exports", "Net Exports contribution QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.IMPORTANT),
    DataField("bea_pce.pce_headline_yoy", "PCE Headline Inflation YoY %", "BEA:NIPA:T20804", "%", FieldPriority.IMPORTANT),
    DataField("bea_pce.pce_services_yoy", "PCE Services Inflation YoY %", "BEA:NIPA:T20804", "%", FieldPriority.IMPORTANT),
    DataField("bea_pce.pce_headline_mom", "PCE Headline MoM %", "BEA:NIPA:T20807", "%", FieldPriority.IMPORTANT),
    DataField("bea_income.saving_rate", "Personal Saving Rate %", "BEA:NIPA:T20600", "%", FieldPriority.IMPORTANT),
    DataField("bea_profits.profits_total", "Corporate Profits (USD bn SAAR)", "BEA:NIPA:T61600D", "USD bn", FieldPriority.IMPORTANT),
    DataField("bea_profits.profits_yoy", "Corporate Profits YoY %", "BEA:NIPA:T61600D", "%", FieldPriority.IMPORTANT),
    # --- OPTIONAL ---
    DataField("bea_gdp.pce_goods", "PCE Goods QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.OPTIONAL),
    DataField("bea_gdp.pce_services", "PCE Services QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.OPTIONAL),
    DataField("bea_gdp.residential", "Residential Investment QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.OPTIONAL),
    DataField("bea_gdp.govt_total", "Govt Spending QoQ %", "BEA:NIPA:T10101", "%", FieldPriority.OPTIONAL),
    DataField("bea_pce.pce_goods_yoy", "PCE Goods Inflation YoY %", "BEA:NIPA:T20804", "%", FieldPriority.OPTIONAL),
    DataField("bea_pce.pce_services_mom", "PCE Services MoM %", "BEA:NIPA:T20807", "%", FieldPriority.OPTIONAL),
    DataField("bea_income.personal_income", "Personal Income (USD bn SAAR)", "BEA:NIPA:T20600", "USD bn", FieldPriority.OPTIONAL),
    DataField("bea_profits.profits_financial", "Financial Sector Profits (USD bn)", "BEA:NIPA:T61600D", "USD bn", FieldPriority.OPTIONAL),
    DataField("bea_profits.profits_nonfinancial", "Nonfinancial Sector Profits (USD bn)", "BEA:NIPA:T61600D", "USD bn", FieldPriority.OPTIONAL),
    DataField("bea_fiscal.federal_net_lending", "Federal Net Lending (deficit, USD bn)", "BEA:NIPA:T30200", "USD bn", FieldPriority.OPTIONAL),
    DataField("china.commodity_demand", "China commodity demand signals", "internal:china_credit", "text", FieldPriority.OPTIONAL),
    DataField("latam_macro", "LatAm GDP + macro", "BCCh:international", "dict", FieldPriority.OPTIONAL),
    DataField("international.gdp", "GDP internacional", "BCCh:international", "dict", FieldPriority.OPTIONAL),
    DataField("forecasts.gdp.world.consensus_imf", "Consenso IMF GDP Mundial", "IMF:WEO/NGDP_RPCH/WEOWORLD", "%", FieldPriority.OPTIONAL),
    DataField("forecasts.inflation.eurozone.consensus_imf", "Consenso IMF Inflacion Eurozona", "IMF:WEO/PCPIPCH/EURO", "%", FieldPriority.OPTIONAL),
    DataField("forecasts.inflation.china.consensus_imf", "Consenso IMF Inflacion China", "IMF:WEO/PCPIPCH/CHN", "%", FieldPriority.OPTIONAL),
    # OECD KEI
    DataField("oecd_cli", "OECD Composite Leading Indicator (multi-country)", "OECD:KEI:LI", "index", FieldPriority.IMPORTANT),
    DataField("oecd_cci", "OECD Consumer Confidence (multi-country)", "OECD:KEI:CCICP", "index", FieldPriority.OPTIONAL),
    DataField("oecd_bci", "OECD Business Confidence (multi-country)", "OECD:KEI:BCICP", "index", FieldPriority.OPTIONAL),
    DataField("oecd_unemployment", "OECD Unemployment Rate (multi-country)", "OECD:KEI:UNEMP", "%", FieldPriority.OPTIONAL),
    DataField("oecd_cpi", "OECD CPI YoY (multi-country)", "OECD:KEI:CP", "%", FieldPriority.OPTIONAL),
    # NY Fed
    DataField("nyfed_rstar", "R-star (Natural Rate of Interest)", "NYFed:Rstar", "%", FieldPriority.IMPORTANT),
    DataField("nyfed_gscpi", "Global Supply Chain Pressure Index", "NYFed:GSCPI", "index", FieldPriority.IMPORTANT),
    DataField("nyfed_term_premia", "ACM Treasury Term Premia", "FRED:ACMTermPremia", "%", FieldPriority.IMPORTANT),
]

RV_MANIFEST: List[DataField] = [
    # --- REQUIRED ---
    DataField("regime.current_regime", "Regimen macro actual", "internal:regime_classification", "label", FieldPriority.REQUIRED),
    DataField("indices", "Indices equity internacionales", "BCCh:stock_indices", "dict", FieldPriority.REQUIRED),
    DataField("breadth.pct_above_50ma", "% acciones sobre 50MA", "yfinance:breadth", "%", FieldPriority.REQUIRED),
    DataField("breadth.breadth_signal", "Senal de breadth", "yfinance:breadth", "label", FieldPriority.REQUIRED),
    DataField("breadth.cyclical_defensive_spread", "Spread ciclicos vs defensivos", "yfinance:breadth", "%", FieldPriority.REQUIRED),
    # --- IMPORTANT ---
    DataField("equity_data.valuations.us.pe_trailing", "P/E trailing S&P 500", "yfinance:SPY", "x", FieldPriority.IMPORTANT),
    DataField("equity_data.valuations.europe.pe_trailing", "P/E trailing STOXX 600", "yfinance:VGK", "x", FieldPriority.IMPORTANT),
    DataField("equity_data.valuations.em.pe_trailing", "P/E trailing MSCI EM", "yfinance:EEM", "x", FieldPriority.IMPORTANT),
    DataField("equity_data.valuations.chile.pe_trailing", "P/E trailing IPSA", "yfinance:ECH", "x", FieldPriority.IMPORTANT),
    DataField("equity_data.valuations.us.pe_fwd", "P/E forward S&P 500", "yfinance:SPY", "x", FieldPriority.IMPORTANT),
    DataField("equity_data.earnings", "Earnings data (beat rate, revisions)", "AlphaVantage/yfinance", "dict", FieldPriority.IMPORTANT),
    DataField("equity_data.factors", "Factor returns (value, growth, momentum)", "yfinance:factors", "dict", FieldPriority.IMPORTANT),
    DataField("equity_data.sectors", "Sector returns (11 GICS)", "yfinance:sectors", "dict", FieldPriority.IMPORTANT),
    DataField("rates.terminal_rate", "Fed Funds Rate (terminal)", "internal:rate_expectations", "%", FieldPriority.IMPORTANT),
    # --- OPTIONAL ---
    DataField("bloomberg_context", "Bloomberg valuaciones 10Y avg", "Bloomberg:valuations", "text", FieldPriority.OPTIONAL),
    DataField("equity_data.market_movers", "Market movers AlphaVantage", "AlphaVantage:movers", "dict", FieldPriority.OPTIONAL),
    DataField("equity_data.news_sentiment", "News sentiment AlphaVantage", "AlphaVantage:sentiment", "dict", FieldPriority.OPTIONAL),
]

RF_MANIFEST: List[DataField] = [
    # --- REQUIRED ---
    DataField("regime.current_regime", "Regimen macro actual", "internal:regime_classification", "label", FieldPriority.REQUIRED),
    DataField("rf_data.yield_curve", "Curva UST (2Y/5Y/10Y/30Y)", "FRED:DGS*", "dict", FieldPriority.REQUIRED),
    DataField("rates.fed_expectations", "Expectativas Fed", "internal:rate_expectations", "dict", FieldPriority.REQUIRED),
    DataField("rf_data.credit_spreads", "IG spread + HY spread", "FRED:BAMLC0A0CM/HY", "bps", FieldPriority.REQUIRED),
    DataField("chile_extended.spc_curve", "BCP + BCU curva Chile", "BCCh:SPC", "dict", FieldPriority.REQUIRED),
    DataField("chile.tpm", "TPM Chile", "BCCh:TPM", "%", FieldPriority.REQUIRED),
    # --- IMPORTANT ---
    DataField("inflation.breakeven_5y", "Breakeven 5Y USA", "FRED:T5YIE", "%", FieldPriority.IMPORTANT),
    DataField("inflation.breakeven_10y", "Breakeven 10Y USA", "FRED:T10YIE", "%", FieldPriority.IMPORTANT),
    DataField("inflation.real_rate_10y", "TIPS real yield 10Y", "FRED:DFII10", "%", FieldPriority.IMPORTANT),
    DataField("rf_data.inflation", "Inflation analytics RF", "FRED:inflation", "dict", FieldPriority.IMPORTANT),
    DataField("bonds_intl", "Bonos 10Y internacionales", "BCCh:international_bonds", "dict", FieldPriority.IMPORTANT),
    DataField("fiscal.deficit_gdp", "Deficit fiscal USA", "FRED:fiscal", "%", FieldPriority.IMPORTANT),
    # BCRP EMBI + Bloomberg curves (via bloomberg_reader → bcrp_embi_client.py + Bloomberg)
    DataField("bloomberg_context", "EMBI spreads (BCRP) + Bund/Gilt/JGB curvas + EM credit", "BCRP:EMBI+Bloomberg:intl_curves", "text", FieldPriority.IMPORTANT),
    # EOF Bond Expectations (BCCh Encuesta Operadores Financieros)
    DataField("chile_extended.eof_expectations.btp_5y", "Exp. tasa BTP 5Y (EOF)", "BCCh:F089.EOF.RF_BTP_5Y", "%", FieldPriority.IMPORTANT),
    DataField("chile_extended.eof_expectations.btp_10y", "Exp. tasa BTP 10Y (EOF)", "BCCh:F089.EOF.RF_BTP_10Y", "%", FieldPriority.IMPORTANT),
    DataField("chile_extended.eof_expectations.btu_5y", "Exp. tasa BTU 5Y (EOF)", "BCCh:F089.EOF.RF_BTU_5Y", "%", FieldPriority.IMPORTANT),
    DataField("chile_extended.eof_expectations.btu_10y", "Exp. tasa BTU 10Y (EOF)", "BCCh:F089.EOF.RF_BTU_10Y", "%", FieldPriority.IMPORTANT),
    DataField("chile_extended.eof_expectations.tpm_12m", "Exp. TPM 12M (EOF operadores)", "BCCh:F089.EOF.TPM.12MS", "%", FieldPriority.IMPORTANT),
    DataField("chile_extended.eof_expectations.ipc_12m", "Exp. inflacion 12M (EOF operadores)", "BCCh:F089.EOF.VII.12MS", "%", FieldPriority.IMPORTANT),
    # IPC Detail Chile for RF (services inflation matters for rates)
    DataField("chile_extended.ipc_detail.ipc_sae", "IPC SAE Chile (core) para RF", "BCCh:F074.IPCSAE", "%", FieldPriority.IMPORTANT),
    # NY Fed / OECD for RF
    DataField("nyfed_rates.sofr.rate", "SOFR (Secured Overnight Financing Rate)", "NYFed:SOFR", "%", FieldPriority.IMPORTANT),
    DataField("nyfed_rates.effr.rate", "EFFR (Effective Federal Funds Rate)", "NYFed:EFFR", "%", FieldPriority.IMPORTANT),
    DataField("nyfed_term_premia.tp_10y", "ACM Term Premium 10Y", "FRED:THREEFYTP10", "%", FieldPriority.IMPORTANT),
    DataField("nyfed_term_premia.tp_2y", "ACM Term Premium 2Y", "FRED:THREEFYTP2", "%", FieldPriority.OPTIONAL),
    DataField("nyfed_rstar.value", "R-star (Natural Rate of Interest)", "NYFed:Rstar", "%", FieldPriority.IMPORTANT),
    DataField("oecd_rates", "OECD Interest Rates (multi-country)", "OECD:KEI:IR3TIB+IRLT", "dict", FieldPriority.OPTIONAL),
    # Bloomberg structured data
    DataField("bbg_sofr_curve", "SOFR Swap Curve (19 tenors)", "Bloomberg:SOFR_Swaps", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_credit_spreads", "OAS IG + HY por sector (Bloomberg)", "Bloomberg:OAS_Sector", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_cds", "CDS Soberanos 5Y (14 paises)", "Bloomberg:CDS", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_intl_curves", "Bund/Gilt/JGB curvas", "Bloomberg:Intl_Curves", "dict", FieldPriority.OPTIONAL),
    # --- OPTIONAL ---
    DataField("rf_data.tpm_expectations", "Expectativas TPM Chile", "internal:tpm_expectations", "dict", FieldPriority.OPTIONAL),
    DataField("chile_extended.eof_expectations.tc_28d", "Exp. USD/CLP 28 dias (EOF)", "BCCh:F089.EOF.TC.28DA", "CLP", FieldPriority.OPTIONAL),
    DataField("chile_extended.eof_expectations.tc_3m", "Exp. USD/CLP 3 meses (EOF)", "BCCh:F089.EOF.TC.7MA", "CLP", FieldPriority.OPTIONAL),
]

RIESGO_MANIFEST: List[DataField] = [
    # --- REQUIRED ---
    DataField("regime.current_regime", "Regimen macro actual", "internal:regime_classification", "label", FieldPriority.REQUIRED),
    DataField("risk.vix", "VIX actual", "yfinance:^VIX", "index", FieldPriority.REQUIRED),
    DataField("risk.scorecard", "Risk scorecard (percentiles)", "internal:risk_metrics", "dict", FieldPriority.REQUIRED),
    DataField("risk.max_drawdown", "Max drawdown portfolio", "internal:risk_metrics", "%", FieldPriority.REQUIRED),
    DataField("risk.current_drawdown", "Drawdown actual", "internal:risk_metrics", "%", FieldPriority.REQUIRED),
    # --- IMPORTANT ---
    DataField("equity_risk", "Equity risk metrics", "yfinance:equity_risk", "dict", FieldPriority.IMPORTANT),
    DataField("equity_credit", "Credit spread metrics", "yfinance/FRED:credit", "dict", FieldPriority.IMPORTANT),
    DataField("rf_credit", "RF credit spreads (IG/HY)", "FRED:credit_spreads", "dict", FieldPriority.IMPORTANT),
    DataField("risk.diversification_score", "Score de diversificacion", "internal:risk_metrics", "score", FieldPriority.IMPORTANT),
    DataField("china.epu_analysis", "China EPU analysis", "FRED:CHINAEPUINDXM", "dict", FieldPriority.IMPORTANT),
    DataField("volatility_epu.vix", "VIX (BCCh)", "BCCh:F019.VIX.IND.90.D", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.move", "MOVE Index (BCCh)", "BCCh:F019.MOVE.IND.90.D", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_usa", "EPU USA", "BCCh:F019.EPU.IND.10.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_global", "EPU Global", "BCCh:F019.EPU.IND.90.M", "index", FieldPriority.IMPORTANT),
    # --- OPTIONAL ---
    DataField("volatility_epu.epu_chile", "EPU Chile", "BCCh:F019.EPU.IND.91.M", "index", FieldPriority.OPTIONAL),
    DataField("volatility_epu.epu_china", "EPU China", "BCCh:F019.EPU.IND.CHN.M", "index", FieldPriority.OPTIONAL),
    DataField("volatility_epu.epu_europa", "EPU Europa", "BCCh:F019.EPU.IND.94.M", "index", FieldPriority.OPTIONAL),
    DataField("volatility_epu.epu_uk", "EPU UK", "BCCh:F019.EPU.IND.UK.M", "index", FieldPriority.OPTIONAL),
    DataField("nyfed_gscpi.value", "GSCPI Supply Chain Pressure", "NYFed:GSCPI", "index", FieldPriority.IMPORTANT),
    DataField("oecd_cli", "OECD CLI (cycle turning points)", "OECD:KEI:LI", "dict", FieldPriority.OPTIONAL),
    DataField("bloomberg_context", "Bloomberg CDS + positioning + EMBI (BCRP)", "Bloomberg+BCRP:risk", "text", FieldPriority.OPTIONAL),
    # Bloomberg structured data
    DataField("bbg_cds", "CDS Soberanos 5Y (Bloomberg)", "Bloomberg:CDS", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_credit_spreads", "OAS IG/HY sectorial (Bloomberg)", "Bloomberg:OAS_Sector", "dict", FieldPriority.IMPORTANT),
    DataField("rf_duration", "Duration metrics", "FRED:duration", "dict", FieldPriority.OPTIONAL),
]

GEO_MANIFEST: List[DataField] = [
    # --- REQUIRED ---
    DataField("daily_context", "Contexto de reportes diarios", "internal:daily_reports", "dict", FieldPriority.REQUIRED),
    DataField("commodities", "Commodities (cobre, petroleo, oro)", "BCCh:commodities", "dict", FieldPriority.REQUIRED),
    DataField("regime.current_regime", "Regimen macro actual", "internal:regime_classification", "label", FieldPriority.REQUIRED),
    # --- IMPORTANT ---
    DataField("epu", "EPU Index (USA, China)", "FRED:EPU", "dict", FieldPriority.IMPORTANT),
    DataField("leading_indicators.lei_usa", "LEI USA (OECD CLI)", "FRED:USALOLITOAASTSAM", "index", FieldPriority.IMPORTANT),
    DataField("leading_indicators.lei_eurozone", "LEI Eurozone (Biz Confidence)", "FRED:BSCICP02EZM460S", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_chile", "EPU Chile", "BCCh:F019.EPU.IND.91.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_usa", "EPU USA", "BCCh:F019.EPU.IND.10.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_china", "EPU China", "BCCh:F019.EPU.IND.CHN.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_europa", "EPU Europa", "BCCh:F019.EPU.IND.94.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_global", "EPU Global", "BCCh:F019.EPU.IND.90.M", "index", FieldPriority.IMPORTANT),
    DataField("volatility_epu.epu_uk", "EPU UK", "BCCh:F019.EPU.IND.UK.M", "index", FieldPriority.OPTIONAL),
    DataField("international", "Datos internacionales", "BCCh:international", "dict", FieldPriority.IMPORTANT),
    DataField("intelligence_themes", "Temas de inteligencia", "internal:intelligence_digest", "dict", FieldPriority.IMPORTANT),
    # BCRP EMBI LatAm (via bloomberg_reader → bcrp_embi_client.py)
    DataField("bloomberg_context", "EMBI LatAm (BCRP: Chile/Peru/Brasil/Mexico/Colombia/Argentina) + CDS", "BCRP:EMBI+Bloomberg:geo", "text", FieldPriority.IMPORTANT),
    # OECD + NY Fed
    DataField("oecd_cli", "OECD CLI multi-country", "OECD:KEI:LI", "dict", FieldPriority.IMPORTANT),
    DataField("oecd_cci", "OECD Consumer Confidence multi-country", "OECD:KEI:CCICP", "dict", FieldPriority.OPTIONAL),
    DataField("nyfed_gscpi.value", "GSCPI Supply Chain Pressure", "NYFed:GSCPI", "index", FieldPriority.IMPORTANT),
    # Bloomberg structured data
    DataField("bbg_cds", "CDS Soberanos 5Y (Bloomberg)", "Bloomberg:CDS", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_embi", "EMBI spreads (Bloomberg/BCRP)", "Bloomberg:EMBI", "dict", FieldPriority.IMPORTANT),
    DataField("bbg_china_extended", "China datos extendidos (Bloomberg)", "Bloomberg:China", "dict", FieldPriority.OPTIONAL),
    # --- OPTIONAL ---
    DataField("forecast_summary", "Resumen de pronosticos", "internal:forecast_engine", "dict", FieldPriority.OPTIONAL),
]


# =============================================================================
# AGENT MANIFEST REGISTRY
# =============================================================================

AGENT_MANIFESTS: Dict[str, List[DataField]] = {
    'macro': MACRO_MANIFEST,
    'rv': RV_MANIFEST,
    'rf': RF_MANIFEST,
    'riesgo': RIESGO_MANIFEST,
    'geo': GEO_MANIFEST,
}


def get_manifest(agent: str) -> List[DataField]:
    """Get the data manifest for a specific agent."""
    return AGENT_MANIFESTS.get(agent, [])


def get_all_agents() -> List[str]:
    """Get list of all agents with manifests."""
    return list(AGENT_MANIFESTS.keys())


def get_fields_by_priority(agent: str, priority: FieldPriority) -> List[DataField]:
    """Get fields of a specific priority for an agent."""
    return [f for f in get_manifest(agent) if f.priority == priority]

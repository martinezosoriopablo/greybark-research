# Fuentes de Datos — Macro Report Mensual

## APIs Integradas

| API | Cliente | Frecuencia |
|---|---|---|
| BCCh REST | `bcch_client.py` | Diaria/Mensual |
| FRED | `fred_client.py` | Diaria/Mensual |

Capa de datos centralizada: `chart_data_provider.py` (ChartDataProvider)

---

## Datos por Seccion

### Chile (BCCh API)

| Variable | Serie BCCh | Metodo Provider |
|---|---|---|
| IMACEC YoY | `F032.IMC.V12.Z.Z.2018.Z.Z.0.M` | `get_chile_dashboard()` |
| IPC YoY | `F074.IPC.VAR.Z.Z.C.M` (rolling 12m) | `compute_yoy_from_monthly_var()` |
| Desempleo | `F049.DES.TAS.INE.10.M` | `get_chile_dashboard()` |
| USD/CLP | `F073.TCO.PRE.Z.D` | `get_chile_dashboard()` |
| TPM | `F022.TPM.TIN.D001.NO.Z.D` | `get_chile_latest()` |
| UF | `F073.UFF.PRE.Z.D` | `get_chile_latest()` |
| Exportaciones | `F068.B1.FLU.Z.0.C.N.Z.Z.Z.Z.6.0.M` | `get_chile_external()` |
| Importaciones | `F068.B1.FLU.Z.0.D.N.0.T.Z.Z.6.0.M` | `get_chile_external()` |
| Cobre | `F019.PPB.PRE.40.M` | `get_commodities()` |

### USA (FRED API)

| Variable | Serie FRED | Metodo Provider |
|---|---|---|
| Unemployment U3 | `UNRATE` | `get_usa_unemployment()` |
| Unemployment U6 | `U6RATE` | `get_usa_unemployment()` |
| Non-Farm Payrolls | `PAYEMS` (diff) | `get_usa_nfp()` |
| AHE YoY | `CES0500000003` (pct_change 12) | `get_usa_wages()` |
| ECI YoY | `ECIWAG` (pct_change 4) | `get_usa_wages()` |
| LFPR | `CIVPART` | `get_usa_wages()` |
| Prime-Age Participation | `LNS12300060` | `get_usa_wages()` |
| CPI Headline YoY | `CPIAUCSL` (pct_change 12) | `get_usa_cpi()` |
| CPI Core YoY | `CPILFESL` (pct_change 12) | `get_usa_cpi()` |
| PCE Core YoY | `PCEPILFE` (pct_change 12) | `get_usa_cpi()` |
| Fed Funds | `DFF` | `get_usa_latest()` |
| Fed Dots Median | `FEDTARMD` | `fred.get_fed_dots()` |
| Treasury 1M-30Y | `DGS1MO`...`DGS30` | `get_yield_curve_current()` |
| Yield Spreads | `DGS2`, `DGS10`, `DGS3MO` | `get_yield_spreads()` |
| ISM New Orders | `NEWORDER` | `get_usa_leading()` |
| Housing Starts | `HOUST` | `get_usa_leading()` |
| Consumer Confidence | `CSCICP03USM665S` | `get_usa_leading()` |
| UMich Sentiment | `UMCSENT` | `get_usa_leading()` |
| JOLTS Openings | `JTSJOL` | `get_usa_jolts()` |
| Quits Rate | `JTSQUR` | `get_usa_jolts()` |
| GDP Real | `GDPC1` (QoQ annualized) | `get_usa_latest()` |
| Initial Claims | `IC4WSA` | `get_usa_latest()` |
| Continuing Claims | `CCSA` | `get_usa_latest()` |

### Internacional (BCCh API)

| Variable | Series |
|---|---|
| Inflacion 10 paises | `BCChSeries.IPC_INTL_*` (USA, Eurozona, China, Japon, UK, Brasil, Mexico, Argentina, Peru, Colombia) |
| Inflacion Core 7 paises | `BCChSeries.CORE_INTL_*` |
| Tasas de politica 10 BC | `BCChSeries.TPM_*` |
| Bonos 10Y 8 paises | `BCChSeries.BOND10_*` |
| Commodities | Brent, WTI, Cobre, Oro, Gas Natural, Litio (BCCh) |
| Volatilidad | VIX, MOVE, EPU (BCCh) |
| Bolsas | IPSA, S&P500, NASDAQ, DAX, Shanghai (BCCh) |

### Europa (BCCh API) — Fase 3

| Variable | Serie BCCh | Metodo Provider |
|---|---|---|
| GDP Eurozona (QoQ) | `F019.PIB.VAR.20.T` | `get_europe_latest()` |
| GDP Alemania (QoQ) | `F019.PIB.VAR.GE.T` | `get_europe_latest()` |
| GDP Francia (QoQ) | `F019.PIB.VAR.FR.T` | `get_europe_latest()` |
| GDP UK (QoQ) | `F019.PIB.VAR.UK.T` | `get_europe_latest()` |
| CPI Eurozona (YoY) | `F019.IPC.V12.20.M` | `get_europe_dashboard()` / `get_europe_latest()` |
| Core CPI Eurozona | `F019.IPC.V12.SA.20.M` | `get_europe_dashboard()` / `get_europe_latest()` |
| PPI Eurozona (YoY) | `F019.IPP.V12.20.M` | `get_europe_latest()` |
| Desempleo Eurozona | `F019.DES.TAS.20.M` | `get_europe_dashboard()` / `get_europe_latest()` |
| Tasa ECB | `F019.TPM.TIN.GE.D` | `get_europe_latest()` |
| Bund 10Y | `F019.TBG.TAS.20.D` | `get_europe_latest()` |
| EUR/USD | `F072.EUR.USD.N.O.D` | (config, no usado en charts aun) |

**Contenido migrado**: `europe_growth`, `europe_inflation`, `ecb_policy` (3 metodos)

### China (BCCh API) — Fase 3

| Variable | Serie BCCh | Metodo Provider |
|---|---|---|
| GDP China (QoQ) | `F019.PIB.VAR.CHN.T` | `get_china_dashboard_data()` / `get_china_latest()` |
| CPI China (YoY) | `F019.IPC.V12.CHN.M` | `get_china_dashboard_data()` / `get_china_latest()` |
| Core CPI China | `F019.IPC.V12.SA.CHN.M` | `get_china_latest()` |
| PPI China (YoY) | `F019.IPP.V12.CHN.M` | `get_china_dashboard_data()` / `get_china_latest()` |
| Desempleo China | `F019.DES.TAS.CHN.M` | `get_china_dashboard_data()` / `get_china_latest()` |
| Tasa PBOC | `F019.TPM.TIN.CHN.D` | `get_china_latest()` |
| Shanghai Composite | `F019.IBC.IND.SHG.D` | `get_china_latest()` |
| CNY/USD | `F072.CNY.USD.N.O.D` | `get_china_latest()` |

**Chart migrado**: `china_dashboard` (GDP, CPI, PPI, Desempleo)
**Contenido migrado**: `china_growth`, `pboc_policy` (2 metodos)

---

## Equity Data Collector (Reporte RV)

Orquestador: `equity_data_collector.py` (EquityDataCollector)

### 1. Valuaciones Regionales (yfinance)

| ETF | Region | Datos |
|---|---|---|
| SPY | S&P 500 | P/E, P/B, div yield, retornos 1M/3M/6M/1Y/YTD |
| EFA | EAFE (Europa/Japon) | idem |
| EEM | Mercados Emergentes | idem |
| EWJ | Japon | idem |
| MCHI | China | idem |
| ILF | LatAm 40 | idem |
| ECH | Chile | idem |
| EWZ | Brasil | idem |

### 2. Datos Sectoriales (yfinance + breadth)

| ETF | Sector | Datos |
|---|---|---|
| XLK-XLP | 11 SPDR sectors | Retornos 1M/3M/YTD/1Y |
| MarketBreadthAnalytics | Breadth | % > 50MA, risk appetite, cyclical/defensive, size |

Modulo: `greybark.analytics.breadth.market_breadth`

### 3. Correlaciones y Riesgo (risk/metrics)

| Activo | Tipo | Uso |
|---|---|---|
| SPY, EFA, EEM, EWJ, ECH, EWZ, MCHI, GLD, TLT, HYG | 10 activos | Matriz correlacion 6M rolling |
| Portfolio equity | VaR/CVaR | VaR 95%, 99%, Expected Shortfall |
| Drawdown analysis | Max/Current DD | Drawdown maximo y actual |

Modulo: `greybark.analytics.risk.metrics` (RiskMetrics, fetch_returns)

### 4. Earnings (AlphaVantage Premium) — Actualizado 2026-02-11

| Grupo | Tickers | Datos |
|---|---|---|
| US Mega | AAPL, MSFT, AMZN, NVDA, GOOGL, META, JPM, UNH | Beat rate, surprise %, EPS growth YoY, estimates, margins, ROE |
| Europe | ASML, SAP, NVO | idem |
| Chile | SQM, BSAC, BCH, LTM, CCU | idem |

**5 endpoints AV Premium por ticker:**

| Endpoint | Datos extraídos | Tickers |
|---|---|---|
| `EARNINGS` | beat_rate_pct, avg_surprise_pct, EPS history (12Q), annual EPS growth YoY | 13 tickers |
| `EARNINGS_ESTIMATES` | consensus EPS (forward), revision_up/down 7d/30d, EPS change % 30d, upgrade_pct | 13 tickers |
| `OVERVIEW` | ProfitMargin, OperatingMarginTTM, ReturnOnEquityTTM, TrailingPE, ForwardPE, AnalystTargetPrice, analyst ratings (StrongBuy/Buy/Hold/Sell/StrongSell) | 13 tickers |
| `INCOME_STATEMENT` | gross/operating/net/EBITDA margins, revenue growth YoY (quarterly) | 5 tickers (AAPL, MSFT, ASML, SQM) |
| `EARNINGS_CALENDAR` | CSV: symbol, name, reportDate, estimate, currency (9,872 entries filtradas a tickers monitoreados) | 1 call global |

**Agregados por grupo:**
- `avg_beat_rate`, `avg_surprise_pct`, `avg_eps_growth_yoy`
- `avg_upgrade_pct_30d`, `avg_eps_change_30d_pct`
- `avg_profit_margin`, `avg_operating_margin`, `avg_roe`
- `avg_trailing_pe`, `avg_forward_pe`

**Bugs corregidos (2026-02-11):**
- `EARNINGS_ESTIMATES`: key era `'estimates'` no `'quarterlyEstimates'`
- Field names: snake_case (`eps_estimate_average`, `eps_estimate_revision_up_trailing_30_days`)
- `collect_earnings_data()`: extracción usaba `report.get('beat_rate')` → ahora `report['track_record']['beat_rate_pct']`
- `EARNINGS_CALENDAR`: retorna CSV, no JSON — nuevo `_make_csv_request()` parser
- `_calculate_revision_summary()`: era stub hardcoded → ahora calcula de datos reales

**Presupuesto API:** ~45 calls por ejecución (13 EARNINGS + 13 ESTIMATES + 13 OVERVIEW + 5 INCOME + 1 CALENDAR)
Rate limit: 75 calls/min (Premium) → ~36 segundos

Modulo: `greybark.analytics.earnings.earnings_analytics` (EarningsAnalytics)
Secciones RV que usan estos datos: `_generate_earnings_growth()`, `_generate_revision_trends()`, `_generate_margins_roe()`, `_generate_earnings_calendar()`, `_generate_earnings_narrative()`
Todas con fallback a defaults estáticos si datos no disponibles.

### 5. Factor Analysis (AlphaVantage + yfinance)

| ETF | Factores | Escala |
|---|---|---|
| SPY, EFA, EEM, EWJ, ECH | Value, Growth, Momentum, Quality | 0-100 cada factor |

Modulo: `greybark.analytics.factors.factor_analytics` (FactorAnalytics)

### 6. Tasas Reales y ERP (FRED)

| Variable | Serie FRED | Uso |
|---|---|---|
| Breakeven 5Y | T5YIE | Expectativas inflacion |
| Breakeven 10Y | T10YIE | Expectativas inflacion |
| TIPS 5Y (real rate) | DFII5 | Real rate |
| TIPS 10Y (real rate) | DFII10 | ERP = Earnings Yield - Real Rate |

Modulo: `greybark.analytics.macro.inflation_analytics` (InflationAnalytics)

### 7. Credit Spreads (FRED)

| Variable | Serie FRED | Uso |
|---|---|---|
| IG Total OAS | BAMLC0A0CM | Indicador riesgo equity |
| IG AAA/AA/A/BBB | BAMLC0A1CAAA-BBB | Breakdown por rating |
| HY Total OAS | BAMLH0A0HYM2 | Indicador riesgo equity |
| HY BB/B/CCC | BAMLH0A1HYBB-CCC | Breakdown por rating |

Modulo: `greybark.analytics.credit.credit_spreads` (CreditSpreadAnalytics)

### 8. Style Data (yfinance)

| ETF | Estilo | Datos |
|---|---|---|
| IWF | Russell 1000 Growth | Retornos 1M/3M/YTD |
| IWD | Russell 1000 Value | idem |
| IWB | Russell 1000 (Large) | idem |
| IWM | Russell 2000 (Small) | idem |

Calcula: Growth/Value spread, Large/Small spread, senales estilo

### 9. Diario Financiero Intelligence

| Fuente | Path | Datos |
|---|---|---|
| Claude Vision summaries | `df_data/resumen_df_*.txt` | Keywords: IPSA, TPM, cobre, SQM mentions |

### 10. Indices BCCh (BCCh API)

| Variable | Serie BCCh | Datos |
|---|---|---|
| IPSA | `F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D` | Nivel + retornos 1M/3M/1Y/YTD |
| IGPA | `F013.IBG.IND.N.7.LAC.CL.CLP.BLO.D` | idem |
| S&P 500 | `F019.IBC.IND.51.D` | idem |
| Euro Stoxx 50 | `F019.IBC.IND.ZE.D` | idem |
| Nikkei 225 | `F019.IBC.IND.52.D` | idem |
| CSI 300 | `F019.IBC.IND.CHN.D` | idem |
| USD/CLP | `F073.TCO.PRE.Z.D` | Nivel + retornos |
| Cobre | `F019.PPB.PRE.100.D` | USc/lb + retornos |
| Oro | `F019.PPB.PRE.44.D` | USD/oz + retornos |
| WTI | `F019.PPB.PRE.41B.D` | USD/bbl + retornos |
| Litio | `F019.PPB.PRE.37.D` | USD/ton + retornos |

### 11. Chile Top Picks (yfinance ADRs) — Nuevo 2026-02-12

| Ticker | Empresa | Datos |
|---|---|---|
| BCH | Banco de Chile | PE trailing, PE forward, dividend yield, precio, 52w high |
| BSAC | Santander Chile | idem |
| SQM | SQM | idem |
| LTM | LATAM Airlines | idem |
| CCU | CCU | idem |

ENIC omitido (PE distorsionado ~106x).
**Nota:** yfinance `dividendYield` para ADRs chilenos devuelve % directo (4.52 = 4.52%), no decimal. Sanity check: si >1, no multiplicar por 100.

---

### RV Charts (rv_chart_generator.py) — 12 charts (2026-02-12)

| # | Chart ID | Tipo | Datos | Seccion Template |
|---|---|---|---|---|
| 1 | `rv_regional_performance` | Horizontal grouped bar | valuations returns | S1 |
| 2 | `rv_pe_valuations` | Vertical bar | valuations PE trailing | S2 |
| 3 | `rv_sector_heatmap` | Heatmap | sectors returns | S4 |
| 4 | `rv_earnings_beat` | Grouped bar | earnings beat_rate + growth | S3 |
| 5 | `rv_style_box` | 2-panel bar | style growth/value/size | S5 |
| 6 | `rv_correlation` | Triangular heatmap | risk correlation_matrix | S7 |
| 7 | `rv_vix_range` | Bullet/gauge | risk VIX | S7 |
| 8 | `rv_chile_ipsa_copper` | Grouped bar | bcch_indices IPSA+cobre | S6 |
| 9 | `rv_credit_risk` | 2-panel bar | credit IG/HY + risk VIX | S7 |
| 10 | `rv_drawdown` | Horizontal bar | risk drawdown/VaR | S8 |
| 11 | `rv_factor_radar` | Grouped horizontal bar | factors scores | S5 |
| 12 | `rv_earnings_revisions` | Grouped bar | earnings upgrades/downgrades | S3 |

**Nota:** `rv_factor_radar` muestra placeholder porque FactorAnalytics falla para ETFs (solo momentum funciona).

---

### Modelos Cuantitativos (Biblioteca Greybark)

| Modulo | Ubicacion | Funcion | API |
|---|---|---|---|
| EarningsAnalytics | `greybark/analytics/earnings/` | Beat rates, EPS growth, estimates/revisions, margins, income, calendar | AlphaVantage (5 endpoints) |
| FactorAnalytics | `greybark/analytics/factors/` | Value/Growth/Momentum/Quality scores (0-100) | AV + yfinance |
| MarketBreadthAnalytics | `greybark/analytics/breadth/` | Sector breadth, risk appetite, cycle position | yfinance |
| RiskMetrics | `greybark/analytics/risk/` | VaR, CVaR, drawdowns, correlaciones | yfinance |
| InflationAnalytics | `greybark/analytics/macro/` | Breakeven, real rates, CPI decomposition | FRED |
| CreditSpreadAnalytics | `greybark/analytics/credit/` | IG/HY spreads, quality rotation | FRED |
| ChinaCreditAnalytics | `greybark/analytics/china/` | Credit impulse proxy, EPU, commodity demand | FRED |
| RegimeClassification | `greybark/analytics/macro/` | VIX+yield curve regime classification | FRED |

---

---

## Forecast Engine (forecast_engine.py + econometric_models.py)

Motor de pronosticos cuantitativos con arquitectura de 2 capas.

### Capa 1: Surveys / Market (forecast_engine.py)

| Modulo | Fuentes | Pesos |
|---|---|---|
| **Inflacion USA** | Breakeven 5Y (T5YIE) + Michigan (MICH) + Cleveland Fed (EXPINF1YR) | 40/30/30 |
| **Inflacion Chile** | BCCh EEE IPC 12M (F089.IPC.V12.Z.M) + Breakeven BCP/BCU | 60/40 |
| **Inflacion Eurozona** | BCCh IPC intl (F019.IPC.V12.20.M) + Target ECB 2% | 50/50 |
| **GDP USA** | GDPNow (GDPNOW) + LEI (USSLIND) + Yield curve (T10Y2Y) | 40/30/30 |
| **GDP Chile** | BCCh EEE PIB (F089.PIB.VAR.Z.M) + IMACEC tendencia | 70/30 |
| **GDP China** | BCCh GDP QoQ (F019.PIB.VAR.CHN.T) + Credit impulse + Commodities | 50/30/20 |
| **GDP Eurozona** | BCCh GDP QoQ (F019.PIB.VAR.20.T) + Desempleo (F019.DES.TAS.20.M) | 60/40 |
| **Tasas Fed** | SOFR forwards (usd_expectations.py) | Mercado |
| **Tasas TPM** | SPC forwards (clp_expectations.py) | Mercado |
| **Tasas ECB** | Modelo inflation gap vs target 2% | Modelo |
| **Equity Targets** | 5-modelo ensemble (ver detalle abajo) | Ponderado |

### Capa 2: Modelos Econometricos (econometric_models.py)

| Modelo | Variables | Datos | Horizonte |
|---|---|---|---|
| **ARIMA** (pmdarima auto_arima) | CPI USA, CPI Chile, GDP USA, Unemployment, Fed Funds | FRED 20Y + BCCh | 12M (mensual) / 4Q (trimestral) |
| **VAR** (statsmodels) | GDP_growth + CPI_YoY + Fed_Funds + Unemployment (sistema 4 variables) | FRED 20Y, trimestral, lag AIC | 4 trimestres |
| **Taylor Rule** | Fed: r*+π+0.5(π-π*)+0.5(y-y*) con inertia | FRED (PCE, UNRATE, DFF) | 12M |
| **Taylor Rule Chile** | TPM: idem con meta 3%, r*=1%, IMACEC como output gap | BCCh (CPI, IMACEC, TPM) | 12M |
| **Taylor Rule ECB** | ECB: idem con meta 2%, r*=0%, NAIRU=6.5% | BCCh (IPC EZ, Desempleo EZ) | 12M |
| **Phillips Curve** | OLS: π = α + β(u-u*) con lag 6M | FRED (CPILFESL, UNRATE) 20Y | Assessment + forecast |

### Blending (2 capas → forecast final)

| Variable | Survey (Capa 1) | ARIMA | VAR | Structural | Total |
|---|---|---|---|---|---|
| **Inflacion USA** | 40% | 20% | 20% (CPI_YoY) | 20% (Phillips) | 100% |
| **Inflacion Chile** | 60% | 40% | — | — | 100% |
| **GDP USA** | 50% | 25% | 25% (GDP_growth) | — | 100% |
| **Fed Funds** | 40% | 20% | 20% (Fed_Funds) | 20% (Taylor) | 100% |
| **TPM Chile** | 60% | — | — | 40% (Taylor) | 100% |
| **ECB** | 60% | — | — | 40% (Taylor) | 100% |

Si un modelo no esta disponible, su peso se redistribuye proporcionalmente.

### Equity Target Ensemble (5 modelos)

| # | Modelo | Peso | Datos | Logica |
|---|---|---|---|---|
| 1 | Earnings Yield + Growth | 30% | yfinance (forward PE) + AV (EPS growth) | Return = E/P + g_forward |
| 2 | Fair Value PE (ERP) | 25% | FRED (TIPS 10Y) + ERP regional | Fair PE = 1/(real_rate + ERP); Target = Fair PE × Fwd EPS |
| 3 | PE Mean-Reversion | 20% | yfinance (5Y history) | PE percentil vs 5Y → ajuste retorno |
| 4 | Consenso Analistas | 15% | AV (AnalystTargetPrice top 4 holdings) | Promedio ponderado targets |
| 5 | Regimen Historico | 10% | RegimeClassifier + retornos historicos | Retorno 12M promedio en regimen actual |

**Indices cubiertos:** SPY (S&P 500), FEZ (EuroStoxx), EWJ (Nikkei), MCHI (China), ECH (Chile), EWZ (Brasil)
**ERP por region:** US 4%, Europa/Japon 4.5%, EM 6%
**Senales:** OW >8%, N 3-8%, UW <3%
**Confianza:** HIGH (spread <5%), MEDIUM (5-15%), LOW (>15%)

### Series FRED agregadas para Forecast Engine

| Serie | Descripcion | Modulo |
|---|---|---|
| `GDPNOW` | Atlanta Fed GDP Nowcast | GDP USA (Capa 1) |
| `EXPINF1YR` | Cleveland Fed Expected Inflation 1Y | Inflacion USA (Capa 1) |
| `EXPINF10YR` | Cleveland Fed Expected Inflation 10Y | Referencia |
| `T10Y2Y` | Treasury Spread 10Y-2Y | GDP USA (Capa 1) |
| `T5YIE` | Breakeven Inflation 5Y | Inflacion USA (Capa 1) |
| `T10YIE` | Breakeven Inflation 10Y | Referencia |
| `MICH` | Michigan Consumer Inflation Expectations 1Y | Inflacion USA (Capa 1) |
| `RECPROUSM156N` | Recession Probability | Referencia |
| `CPIAUCSL` | CPI All Items (20Y) | ARIMA CPI, VAR |
| `CPILFESL` | Core CPI (20Y) | Phillips Curve |
| `PCEPILFE` | Core PCE (2Y) | Taylor Rule Fed |
| `GDPC1` | Real GDP Quarterly (20Y) | ARIMA GDP, VAR |
| `UNRATE` | Unemployment Rate (20Y) | ARIMA, VAR, Taylor, Phillips |
| `DFF` | Fed Funds Daily (20Y) | ARIMA Fed Funds, VAR |
| `USSLIND` | Leading Economic Index | GDP USA (Capa 1) |
| `DFII10` | 10Y TIPS Real Rate | Fair PE model |

### Series BCCh agregadas para Forecast Engine

| Serie | Descripcion | Modulo |
|---|---|---|
| `F089.PIB.VAR.Z.M` | EEE PIB ano actual | GDP Chile (Capa 1) |
| `F089.PIB.VAR.Z1.M` | EEE PIB ano siguiente | GDP Chile (Capa 1 fallback) |
| `F089.IPC.V12.Z.M` | EEE IPC 12M | Inflacion Chile (Capa 1) |
| `F089.IPC.V24.Z.M` | EEE IPC 24M | Referencia |
| `F089.TCN.VAL.Z.M` | EEE USD/CLP 12M | Referencia |
| `F074.IPC.VAR.Z.Z.C.M` | IPC Chile variacion mensual | ARIMA Chile (rolling product → YoY), Taylor Chile |

### Output

Archivo: `output/forecasts/forecast_YYYYMMDD_HHMMSS.json`

Estructura:
- `metadata`: timestamp, horizon, modules_ok, econometric_models (run/ok)
- `equity_targets`: 6 indices con current_price, target_12m, return_pct, signal, confidence, models
- `inflation_forecasts`: 3 regiones con current, forecast_12m (blended), forecast_12m_survey, econometric {arima, var, phillips}
- `gdp_forecasts`: 4 regiones con current, forecast_12m (blended), forecast_12m_survey, econometric {arima, var}
- `rate_forecasts`: 3 tasas con current, forecast_6m, forecast_12m (blended), forecast_12m_market, econometric {arima, var, taylor}
- `econometric_detail`: resultado completo de EconometricSuite.run_all()

---

### Sin API libre (hardcoded con caveats)

| Variable | Razon |
|---|---|
| PMI Europa/China (S&P Global) | Datos propietarios S&P Global — no disponible en BCCh |
| China Property (ventas, starts, precios) | Sin serie en catalogo BCCh |
| China Credit (TSF, credit impulse, M2) | Sin serie en catalogo BCCh |
| China Trade (exportaciones/importaciones totales) | BCCh solo tiene comercio Chile-China, no China total |
| Europe PMI chart | PMI propietario |
| China trade chart | Sin datos BCCh de comercio total |
| PMI global chart | PMI propietario |
| CPI subcomponents USA (Shelter, Services ex-Housing) | Series complejas, sin FRED simple |
| Componentes IPC Chile | Series no configuradas en BCCh |
| LPR, RRR China | Sin serie en BCCh |
| Salarios negociados Europa | Sin serie en BCCh |
| Escenarios (probabilidades) | Juicio del analista (forecasts ahora via Forecast Engine) |

---

## Patron de Fallback

Todos los charts y tablas siguen el patron:
1. Si `data_provider` disponible → datos reales de API
2. Si API falla → fallback a `_interp()` (datos interpolados) o valores hardcoded
3. Titulo indica "(datos FRED)", "(datos BCCh)" o "(datos reales BCCh)" cuando usa datos reales

---

## Fases de Migracion

| Fase | Estado | Fuente |
|---|---|---|
| Fase 1: Chile + Internacional | Completada | BCCh API |
| Fase 2: USA + Yield Curve | Completada | FRED API |
| Fase 3: Europa/China | **Completada** | BCCh API (GDP, CPI, PPI, desempleo, tasas, FX) |

### Fase 3 — Detalle

| Area | Estado | Fuente |
|---|---|---|
| Europa charts (europe_pmi) | Hardcoded | PMI propietario |
| Europa contenido (3/4 metodos) | **REAL** | BCCh API |
| Europa contenido (europe_risks) | Hardcoded | Analisis cualitativo |
| China chart (china_dashboard) | **REAL** | BCCh API |
| China chart (china_trade) | Hardcoded | Sin datos comercio total |
| China contenido (2/5 metodos) | **REAL** | BCCh API |
| China contenido (property, credit, trade) | Hardcoded | Sin series BCCh |
| PMI global chart | Hardcoded | PMI propietario |

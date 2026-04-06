# Greybark Research — AI Council: Resumen Completo del Sistema

> Última actualización: 2026-03-27 (125+ bugs/mejoras, 24 sprints, 3 clientes en producción)
> Pipeline: 5 reportes mensuales en español para comité de inversiones
> Estado: 15/17 módulos OK, portal multi-cliente live, mejora continua activa

## Arquitectura General

El sistema genera **5 reportes mensuales de inversión** en español usando un consejo de inversiones con inteligencia artificial (multi-agente). Recopila datos reales de mercado, los procesa a través de un council deliberativo de 8 agentes, y renderiza reportes HTML profesionales con charts y narrativas.

```
FASE 1: Recopilación de Datos (44+ módulos, 13 APIs)
    ↓
FASE 2: Preflight (validación GO / CAUTION / NO_GO)
    ↓
FASE 2.5: Intelligence Briefing (44 charts, datos verificados)
    ↓
FASE 3: AI Council (5 panelistas + CIO + Contrarian + Refinador)
    ↓
FASE 4: 4 Reportes HTML (Macro, RV, RF, Asset Allocation)
    ↓
FASE 5: Resumen + Entrega por cliente
```

---

## 1. Fuentes de Datos (13 APIs, 300+ métricas)

### 1.1 Datos Macro (council_data_collector.py — 20+ módulos)

| Módulo | Métricas | Fuente API |
|--------|----------|------------|
| **Macro USA** | GDP, desempleo, NFP, ISM PMI, retail sales, housing, claims, consumer confidence, JOLTS | FRED |
| **Leading Indicators** | ISM New Orders, Claims, Stock Market, Yield Curve 2s10s, HY Spread | FRED |
| **Inflación** | Breakeven 5Y/10Y, forward 5Y5Y, real rate TIPS, CPI all/core/services YoY | FRED |
| **Chile** | TPM, UF, desempleo, GDP, IPC, wage growth, crédito, CLF | BCCh |
| **Chile Extended** | Macro dashboard, SPC curve, crédito, commodities, EEE/EOF expectations, IMCE | BCCh Extended |
| **China** | Credit impulse, shadow credit, policy tone, GDP signal | Analytics interno |
| **Rate Expectations** | Fed Funds path (8 reuniones), TPM path (8 reuniones), terminal rates | NY Fed + BCCh SPC |
| **Risk Metrics** | VaR/CVaR 95%, drawdown, correlaciones, volatilidad, Sharpe | yfinance + statsmodels |
| **Breadth** | % stocks > 50MA/200MA, McClellan oscillator, divergencia breadth | yfinance |
| **Internacional** | Inflación, core inflation, bonos 10Y, policy rates, GDP, desempleo por país | BCCh |
| **Bloomberg** | PMI, CDS, sector spreads, SOFR curve, EPFR flows, EMBI, China extended, valuations, factor returns | Excel (95 series, 272K datapoints) |
| **CPI Components** | CPI headline, core, shelter, services, goods, energy YoY | FRED (ChartDataProvider) |
| **Fiscal** | Déficit federal, revenue, spending, debt/GDP | FRED/Treasury |
| **BEA** | GDP por componente, PCE breakdown, corporate profits, fiscal stance | BEA REST API |
| **OECD** | CLI, Consumer Confidence, Business Confidence, desempleo, CPI, tasas | OECD KEI API |
| **AKShare China** | Calendario económico, crédito TSF, yuan, commodities | AKShare |
| **IMF WEO** | GDP growth consensus, inflación consensus por país/región | IMF WEO API |
| **NY Fed** | SOFR implied rates, terminal rate distribution, tail risks | NY Fed API |
| **Soberano** | Yield curves USA, Alemania, Japón, UK, Canadá, Australia, México | BCCh + ECB + MoF Japan |
| **AlphaVantage** | Earnings calendar, analyst sentiment, top gainers/losers | AlphaVantage |

### 1.2 Datos Equity (equity_data_collector.py — 11 módulos)

| Módulo | Métricas | Fuente |
|--------|----------|--------|
| **Valuaciones Regionales** | P/E trailing/forward, P/B, dividend yield, returns (1M-1Y), 52w high/low para SPY, EFA, EEM, EWJ, MCHI, ECH | yfinance |
| **Sectores** | Returns 11 sectores US (XLK, XLE, XLF, etc.), P/E, breadth %, risk appetite | yfinance |
| **Risk** | Correlación 6 activos, VaR/CVaR, drawdown, volatilidad rolling, Sharpe, diversificación | yfinance + statsmodels |
| **Earnings** | Beat rates, surprise avg, EPS growth YoY, revisiones (upgrades/downgrades), márgenes, ROE — 65+ stocks en 5 grupos | AlphaVantage Premium |
| **Factores** | Value, Growth, Momentum, Quality scores (0-100) por ticker | AlphaVantage + yfinance |
| **Real Rates** | TIPS 5Y/10Y, breakeven inflation, Equity Risk Premium por región | FRED + yfinance |
| **Crédito** | IG/HY spread, percentiles 5Y, quality rotation, market stress | FRED OAS |
| **Style** | Growth vs Value (IWF/IWD), Large vs Small (IWB/IWM), spreads, señales | yfinance |
| **DF Intelligence** | Headlines Diario Financiero, temas IPSA, TPM mentions, corporate news | Claude Vision summaries |
| **BCCh Indices** | IPSA, IGPA, índices internacionales, USD/CLP, commodities | BCCh |
| **Chile Picks** | Top ADRs chilenos (SQM, CAP, COPEC, BCI, Entel): precios, returns, P/E | yfinance |

### 1.3 Datos Renta Fija (rf_data_collector.py — 13 módulos)

| Módulo | Métricas | Fuente |
|--------|----------|--------|
| **Duration** | Yield curve slopes (2s5s, 2s10s, 5s30s), duration targeting, señal | FRED |
| **Yield Curve** | UST por tenor (2Y-30Y), slopes, shape, trend, inversión risk | FRED |
| **Credit Spreads** | IG por rating (AAA-BBB), HY por rating (BB-CCC), percentiles, migración | FRED ICE BofA OAS |
| **Inflación** | Breakevens (5Y-30Y), real rates TIPS, CPI decomposition, wages, TIPS signal | FRED |
| **Fed Expectations** | Fed Funds path 8 reuniones, probabilidades cut/hold/hike, terminal rate | SOFR forwards + QuantLib |
| **TPM Expectations** | TPM path 8 reuniones BCCh, probabilidades, terminal rate | SPC curve + QuantLib |
| **Fed Dots** | Market implied vs FOMC dot plot, divergencia, implicancias | CommLoan + FRED |
| **BCCh Encuesta** | Market implied TPM vs EEE survey, divergencia | BCCh SPC + EEE |
| **Credit Duration** | Spreads por bucket (0-3Y, 3-5Y, 5-10Y, 10Y+), carry vs price | Analytics |
| **International Yields** | Bonos 10Y: USA, Alemania, UK, Japón, Brasil, México, Colombia, Perú + spreads | BCCh |
| **Chile Yields** | BCP (nominal), BCU (real), SPC (swap) — curvas completas, breakevens, slopes | BCCh |
| **Chile Rates** | TPM, DAP, interbancaria, tasas préstamo, VIX, MOVE, policy rates internacionales | BCCh |
| **Sovereign Curves** | Curvas Alemania (Bund) y Japón (JGB) con tenors y spreads | ECB + MoF Japan |

### 1.4 Forecasts (forecast_engine.py — 5 módulos)

| Módulo | Qué pronostica | Metodología |
|--------|----------------|-------------|
| **Econometric Models** | Series macro (ARIMA, VAR, GARCH, Prophet) | statsmodels + pmdarima |
| **Inflación** | 12M outlook USA, Chile, Eurozona | 40% Breakeven + 30% Michigan Survey + 30% Cleveland Fed |
| **Tasas** | Terminal rates Fed, TPM, ECB | SOFR forwards + SPC bootstrap + guidance |
| **GDP** | 12M growth USA, Chile, China, Eurozona | 40% GDPNow + 30% LEI + 30% Yield curve |
| **Equity Targets** | S&P500, EAFE, Nikkei, CSI300, IPSA, Bovespa — 12M | Ensemble 5 modelos (Earnings Yield, Fair Value PE, Mean Reversion, Consensus, Regime) |

---

## 2. AI Council (3 Capas, 8 Agentes)

### Capa 1 — Panel Horizontal (5 agentes en paralelo, claude-sonnet)

Cada agente recibe datos cuantitativos filtrados por su expertise + directivas del usuario + intelligence briefing.

| Agente | Expertise | Bloques que produce |
|--------|-----------|---------------------|
| **IAS Macro** | Crecimiento, inflación, bancos centrales, escenarios | `ESCENARIOS`, `POSTURA_MACRO` |
| **IAS RV** | Valuaciones, earnings, sectores, factores, regiones | `EQUITY_VIEWS`, `SECTOR_VIEWS`, `FACTOR_VIEWS` |
| **IAS RF** | Duration, crédito, EM debt, Chile RF | `FI_POSITIONING`, `DURATION` |
| **IAS Riesgo** | VaR, tail risks, correlaciones, hedges | `RISK_MATRIX`, `CORRELACIONES` |
| **IAS Geo** | Geopolítica, sanciones, elecciones, commodities | `GEO_RISKS` |

### Capa 2 — Síntesis Vertical (secuencial, claude-opus)

| Agente | Input | Output |
|--------|-------|--------|
| **CIO** | 5 outputs del panel + datos originales + coherence warnings | Síntesis integrada + `ALLOCATION`, `FX_VIEWS`, `CAUSAL_TREE` |
| **Contrarian** | Síntesis CIO + panel | Desafío a la tesis, supuesto más peligroso, desafío a raíz del árbol causal, ajustes recomendados |
| **Refinador** | CIO + Contrarian + panel + datos | Documento final (8K palabras) con todos los bloques + CAUSAL_TREE preservados |

### Capa 3 — Parser Estructurado (council_parser.py)

Extrae 12 bloques tipados `[BLOQUE: X]` + 1 bloque especial del output del council:

| Bloque | Contenido | Usado por |
|--------|-----------|-----------|
| `POSTURA_MACRO` | CONSTRUCTIVO / CAUTELOSO / NEUTRAL / AGRESIVO | Macro, AA |
| `ESCENARIOS` | Escenarios con probabilidades (suman 100%) | Macro, AA |
| `EQUITY_VIEWS` | Views regionales OW/N/UW con convicción | RV, AA |
| `SECTOR_VIEWS` | Views sectoriales OW/N/UW | RV |
| `FACTOR_VIEWS` | Quality, Momentum, Value, Growth, Size | RV |
| `FI_POSITIONING` | Segmentos RF: view, duration, rationale | RF, AA |
| `DURATION` | Stance + benchmark + recomendación (años) | RF, AA |
| `RISK_MATRIX` | Riesgos: probabilidad %, impacto, horizonte | Macro, RF, AA |
| `GEO_RISKS` | Riesgos geopolíticos con probabilidad | Macro, AA |
| `ALLOCATION` | Pesos regionales vs benchmark | AA |
| `FX_VIEWS` | Pares: ALCISTA/BAJISTA/NEUTRAL | AA |
| `CORRELACIONES` | Métricas correlación actual/1Y/5Y | (prosa al CIO) |
| `CAUSAL_TREE` | JSON: root → L1 (canales) → L2 (efectos) → 5 outcomes con probabilidades. Delimitadores: `[CAUSAL_TREE_START]...[CAUSAL_TREE_END]` | AA (sección 10, visualización HTML) |

---

## 3. Reportes Generados

### 3.1 Reporte Macro (~25-30 páginas, 23 charts)

| Sección | Contenido |
|---------|-----------|
| Resumen Ejecutivo | Postura macro (badge), key takeaways, tabla forecasts GDP/inflación/tasas |
| Pronóstico Ponderado | Escenarios con probabilidades, weighted forecasts, implicancia |
| vs Pronóstico Anterior | Track record: aciertos y errores del mes anterior |
| Estados Unidos | Crecimiento (leading indicators), laboral (NFP, JOLTS, wages), inflación (CPI decomposition), Fed policy (Taylor rule, reuniones), fiscal |
| Europa | GDP, PMI, inflación HICP, ECB policy |
| China | Crecimiento, inmobiliario, impulso crediticio, comercio exterior, PBOC |
| Chile y LatAm | IMACEC, IPC, BCCh TPM path, cuentas externas, commodities, tabla LatAm |
| Temas Macro Clave | 3-4 temas temáticos, calendario de eventos |
| Escenarios y Riesgos | Pie chart escenarios, risk matrix |

**23 Charts:** Inflación global (120m), desempleo U3/U6, NFP barras, JOLTS, salarios, heatmap CPI, CPI componentes, PMI global, commodities (Brent/Cobre/Oro), energía/alimentos, tasas 6 bancos centrales, USA leading indicators, Europe dashboard, Europe PMI, bolsas globales, China dashboard, China trade, Chile dashboard, Chile IPC componentes, Chile cuentas externas, tasas LatAm, EPU geopolítica, yield curve + spreads recesión.

### 3.2 Reporte Renta Variable (~15-20 páginas, 12 charts)

| Sección | Contenido |
|---------|-----------|
| Resumen Ejecutivo | Postura global OW/N/UW, tabla resumen por mercado |
| Valorizaciones | Múltiplos regionales P/E/P/B/div yield, vs promedio 10Y, ERP |
| Earnings | EPS growth, beat rates, revisiones por región, calendario |
| Sectores | Matriz 11 sectores, preferidos/evitar, catalizadores |
| Style & Factors | Growth vs Value, Large vs Small, factor scores radar |
| Regiones | Views: USA, Europa, Japón, EM, Chile (IPSA + top picks) |
| Flujos y Posicionamiento | Fund flows, put/call, VIX, short interest |
| Riesgos y Catalizadores | Top risks + hedge, catalizadores positivos |
| Resumen Posicionamiento | Tabla final OW/N/UW, mensaje clave |

**12 Charts:** Performance regional, P/E valuaciones, heatmap sectorial, earnings beat + EPS, Growth/Value + Large/Small, correlación 10 activos, VIX gauge, IPSA vs Cobre, crédito para equity, drawdown/riesgo, factor radar, revisiones earnings.

### 3.3 Reporte Renta Fija (~12-15 páginas, 8 charts)

| Sección | Contenido |
|---------|-----------|
| Resumen Ejecutivo | Postura global, duration/credit stance, tabla por segmento |
| Ambiente de Tasas | Yield curve, forward guidance, real rates, breakevens |
| Duration | View global, por mercado, trades recomendados (entry/target/stop) |
| Crédito | IG (spreads por rating, sectores), HY (spreads, default risk) |
| EM Debt | EMBI spreads, por país, hard vs local currency |
| Chile RF | Soberanos (curva BCP/BCU), corporativos, money market |
| Riesgos y Oportunidades | Top risks, trades tácticos |

**8 Charts:** Curvas soberanas UST/Bund/JGB, credit spreads (bullet chart 7 ratings), breakevens/tasas reales, curvas Chile BCP/BCU, policy rates 8+ bancos centrales, Fed expectations (mercado vs dots), TPM expectations, yields 10Y globales.

### 3.4 Reporte Asset Allocation (~10-12 páginas, tablas)

| Sección | Contenido |
|---------|-----------|
| Resumen Ejecutivo | Postura comité, régimen actual, métricas clave |
| Dashboard Posicionamiento | Equity, RF, commodities, FX, cash — pesos vs benchmark, OW/N/UW |
| Mes en Revisión | Economía global, mercados, geopolítica, Chile |
| Escenarios | Base/upside/downside/stagflation con probabilidades y targets |
| Views Regionales | USA, Europa, Japón, EM, Chile — argumentos favor/contra |
| Asset Classes | Equity (regiones, sectores), RF (duration, crédito, Chile), Commodities (oro, petróleo, cobre), FX (USD, pares, EM) |
| Riesgos | Top 5: probabilidad, impacto, señal temprana, hedge |
| Portafolios Modelo | 5 perfiles (Conservador → Agresivo) — pesos exactos suman 100% |

### 3.5 Intelligence Briefing (~15-20 páginas, 44 charts)

Documento pre-council con datos verificados:
- Dashboard completitud (APIs OK, cobertura %)
- Régimen actual + probabilidades
- USA, Europa, China, Chile, LatAm — secciones con datos y charts
- Inflación detallada, commodities, geopolítica
- 44 charts embebidos base64

---

## 4. Controles de Calidad

| Control | Qué hace |
|---------|----------|
| **Preflight Validator** | Gate GO/CAUTION/NO_GO — verifica completitud de datos |
| **Coherence Validator** | 13 métricas cruzadas entre los 4 reportes |
| **Anti-fabricación** | 8 prompts con `INTEGRIDAD DE DATOS`: prohibido inventar números |
| **None-safe** | VaR/CVaR None-safe, EPS growth capped ±500% |
| **Fallback pattern** | Council → API → hardcoded defaults (nunca celdas vacías para datos actuales) |
| **Deep merge** | AA report fusiona RF + macro_quant a nivel de sub-keys (evita colisiones, ej: `inflation`) |
| **Quality checker** | `report_quality_checker.py` — escanea HTML post-render, cuenta celdas "—", alerta en log |
| **Badge consistency** | Parser estructurado priorizado sobre text mining |

### Historical data store (columnas "anterior")

`historical_store.py` guarda ~30 métricas clave por run en `output/historical/snapshot_{date}.json`.
En el siguiente run, carga snapshot anterior e inyecta `_prev` values en quant_data.
Primera ejecución: "anterior" vacío (sin historia). Segunda en adelante: datos del run previo.
`chart_data_provider.get_usa_latest()` también calcula CPI/PCE prev directamente desde FRED series.

---

## 5. Infraestructura

| Componente | Detalle |
|-----------|---------|
| **Servidor** | Hetzner CPX11 Ashburn, VA — `87.99.133.124` |
| **Container** | Docker (python:3.11-slim) + FastAPI portal |
| **Portal** | Multi-client: login JWT, branding personalizable, directivas per-client |
| **Clientes** | MBI Inversiones, Vantrust Capital, BVC Asset Management |
| **Volúmenes Docker** | output/, input/, layout/, daily_reports/, df_data/, research/ |
| **API Keys** | ANTHROPIC, FRED, ALPHAVANTAGE, BCCH_USER/PASSWORD |

---

## Resumen Numérico

| Dimensión | Cantidad |
|-----------|----------|
| APIs/fuentes de datos | 14+ (13 originales + TAA model) |
| Métricas únicas recolectadas | 320+ |
| Módulos data collection | 45+ (44 originales + taa_data_collector) |
| Agentes AI Council | 8 (5 panel + 3 síntesis) |
| Bloques estructurados | 12 |
| Reportes generados | 5 (Macro, RV, RF, AA con sección TAA, Briefing) |
| Charts totales | 47 (43 originales + 4 TAA en AA) |
| Modelos forecast | 6 (5 originales + TAA MOM_MACRO) |
| Herramientas cuantitativas | 1 (TAA: 24 ETFs, 16 FRED series, IR 0.40) |
| Tiempo pipeline completo | 36-51 min (+30s TAA) |
| Costo por run (API Claude) | ~$3-5 |

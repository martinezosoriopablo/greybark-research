# Greybark Research — AI Council System: Descripción Completa

> Última actualización: 2026-03-25 (111 bugs/mejoras resueltos, 16 sprints, pipeline 4/4 OK, prompt audit completado, deploy Hetzner Ashburn live)
> Pipeline: 4 reportes mensuales en español para comité de inversiones
> Estado: 10/10 fuentes de datos OK, 0 módulos faltantes, mejora continua activa

---

## 1. Qué Es

Plataforma automatizada de research de inversiones que genera **4 reportes mensuales profesionales** usando una arquitectura multi-agente (AI Council). El sistema recopila datos reales de mercado desde 12+ APIs, ejecuta deliberación a través de Claude (5 analistas panel + 3 capas de síntesis), y renderiza reportes HTML listos para impresión.

**Reportes generados:**
| # | Reporte | Template | Secciones | Charts | Tamaño |
|---|---------|----------|-----------|--------|--------|
| 1 | **Macro** | `macro_report_professional.html` | 8 (Resumen, USA, Europa, China, Chile/LatAm, Temas, Escenarios, Conclusiones) | 28 | ~2.7 MB |
| 2 | **Renta Variable** | `rv_report_professional.html` | 7 (Valuaciones, Sectores, Earnings, Riesgo, Factores, Chile, Posicionamiento) | 12 | ~1.5 MB |
| 3 | **Renta Fija** | `rf_report_professional.html` | 8 (Tasas, Inflación, Crédito, Duración, Chile, LatAm, Posicionamiento) | 8 | ~1.2 MB |
| 4 | **Asset Allocation** | `asset_allocation_professional.html` | 9 (Dashboard, Escenarios, Regiones, Asset Classes, Riesgos, Portafolios, Focus List) | 0 (tablas) | ~800 KB |

---

## 2. Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    run_monthly.py (orquestador)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  FASE 1: RECOPILACIÓN DE DATOS                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ council_data  │  │ equity_data  │  │  rf_data     │          │
│  │ _collector    │  │ _collector   │  │ _collector   │          │
│  │ (10 módulos)  │  │ (11 módulos) │  │ (12 módulos) │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐          │
│  │ forecast_    │  │ intelligence │  │ research_    │           │
│  │ engine (4+1) │  │ _digest      │  │ analyzer     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  FASE 2: PRE-COUNCIL PACKAGE                                    │
│  ┌──────────────────────────────────────────────────┐           │
│  │ pre_council_package.py                            │           │
│  │  → Genera 48+ charts con datos reales             │           │
│  │  → Valida completitud por reporte                 │           │
│  │  → Genera briefing de inteligencia (LLM)          │           │
│  │  → Gate: bloquea reportes con >3 charts faltantes │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  FASE 3: PREFLIGHT GATE                                         │
│  ┌──────────────────────────────────────────────────┐           │
│  │ council_preflight_validator.py                     │           │
│  │  → Verifica módulos críticos: regime, macro, chile │           │
│  │  → Veredicto: GO / CAUTION / NO_GO                │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  FASE 4: AI COUNCIL (3 capas)                                   │
│  ┌──────────────────────────────────────────────────┐           │
│  │ ai_council_runner.py                              │           │
│  │                                                    │           │
│  │  CAPA 1 — Panel Horizontal (paralelo, Sonnet)     │           │
│  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌─────┐│           │
│  │  │ MACRO │ │  RV   │ │  RF   │ │RIESGO │ │ GEO ││           │
│  │  └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘ └──┬──┘│           │
│  │      └─────────┴─────────┴─────────┴────────┘    │           │
│  │                      ↓                            │           │
│  │  CAPA 2 — Síntesis Vertical (secuencial, Opus)    │           │
│  │  ┌─────────┐   ┌────────────┐   ┌───────────┐   │           │
│  │  │   CIO   │ → │ CONTRARIAN │ → │ REFINADOR │   │           │
│  │  │(síntesis│   │ (desafío)  │   │  (final)  │   │           │
│  │  └─────────┘   └────────────┘   └───────────┘   │           │
│  │                                                    │           │
│  │  CAPA 3 — Output Estructurado                     │           │
│  │  → [BLOQUE: EQUITY_VIEWS], [BLOQUE: ESCENARIOS]  │           │
│  │  → council_parser.py extrae bloques               │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  FASE 5: GENERACIÓN DE REPORTES                                 │
│  ┌──────────────────────────────────────────────────┐           │
│  │ 4 renderers (macro/rv/rf/aa_report_renderer.py)   │           │
│  │  → content_generator combina council + datos API  │           │
│  │  → narrative_engine genera prosa (anti-fabricación)│           │
│  │  → Jinja2 template rendering → HTML               │           │
│  │  → coherence_validator (13 métricas cross-report) │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  FASE 6: RESUMEN                                                │
│  → Timing, errores, rutas de archivos                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Fuentes de Datos — Inventario Completo

### 3.1 APIs con Autenticación

| API | Cliente | Auth | Datos Principales | Series | Frecuencia |
|-----|---------|------|-------------------|--------|------------|
| **FRED** | `greybark/data_sources/fred_client.py` | API Key (`FRED_API_KEY`) | Macro USA, yields, spreads, inflation, empleo, fiscal | 50+ series | Diaria/Mensual |
| **BCCh REST** | `greybark/data_sources/bcch_client.py` | User+Pass (`BCCH_USER/PASSWORD`) | Chile macro, tasas, FX, commodities, internacional | 93+ series | Diaria/Mensual |
| **BCCh Extended** | `greybark/data_sources/bcch_extended.py` | User+Pass (mismo) | Chile sectorial, comercio, crédito, EEE/EOF encuestas | 90+ series adicionales | Mensual |
| **AlphaVantage** | `greybark/data_sources/alphavantage_client.py` | API Key (`ALPHAVANTAGE_API_KEY`) | Earnings (EPS, beat rates, estimaciones, calendar) | ~45 calls/run | Trimestral |
| **BEA** | `lib_clients/bea_client.py` | API Key (`BEA_API_KEY`) | GDP componentes, PCE inflación, corporate profits, fiscal | 6 NIPA tables | Trimestral |
| **Anthropic** | via `anthropic` SDK | API Key (`ANTHROPIC_API_KEY`) | Council deliberation + narrativas | 8+ LLM calls/run | Por ejecución |

### 3.2 APIs Públicas (Sin Auth)

| API | Cliente | Datos | Frecuencia |
|-----|---------|-------|------------|
| **IMF WEO** | `imf_weo_client.py` | Consenso GDP/CPI (USA, Eurozona, China, Chile) | Semestral |
| **ECB SDMX** | `ecb_client.py` | DFR, HICP, EA 10Y yield, EUR/USD, M3 | Diaria/Mensual |
| **ECB Data Portal** | `data_fetchers/curvas_soberanas.py` | Euro AAA Svensson curve (9 tenors: 1Y–30Y) | Diaria |
| **MoF Japan** | `data_fetchers/curvas_soberanas.py` | JGB benchmark yields (11 tenors: 1Y–40Y) | Diaria |
| **AKShare (NBS)** | `greybark/data_sources/akshare_client.py` | China PMI, CPI, PPI, M2, TSF, LPR, RRR, Trade, Property | Mensual |
| **BCRP** | `bcrp_embi_client.py` | EMBIG spreads LatAm (8 países) | Mensual |
| **NY Fed** | `greybark/data_sources/nyfed_client.py` | SOFR, EFFR, GSCPI, R-star, term premia | Diaria |
| **OECD KEI** | `greybark/data_sources/oecd_client.py` | CLI, confianza, desempleo, GDP, CPI (58 países) | Mensual |
| **yfinance** | directo (sin cliente) | ETF valuaciones, retornos, VIX, drawdown | Real-time |
| **CommLoan** | `greybark/data_sources/commloan_scraper.py` | SOFR forwards (1M–10Y) para FedWatch | Diaria |

### 3.3 Fuentes Locales

| Fuente | Archivo | Contenido |
|--------|---------|-----------|
| **Bloomberg Excel** | `input/bloomberg_data.xlsx` | 22 hojas: PMI, CDS, SOFR, Credit Spreads, EPFR, Positioning, etc. (95 series, ~272K datapoints) |
| **Research Bancos** | `input/research/*.txt` | Goldman, JPMorgan, Morgan Stanley — extractos manuales |
| **Directivas Usuario** | `input/user_directives.txt` | Foco, preguntas, contexto del mes |
| **Reportes Diarios** | `html_out/daily_report_*.html` | AM/PM reports (finanzas + no-finanzas) para intelligence digest |

### 3.4 Módulos de Recopilación

**Council Data Collector** (`council_data_collector.py`) — 10+ módulos:
1. Regime Classification (interno)
2. Macro USA (FRED: GDP, empleo, NFP, retail)
3. Leading Indicators (FRED: claims, sentiment, new orders, permits)
4. Inflation (FRED+BCCh: CPI, PCE, breakevens, real rates)
5. Chile (BCCh: TPM, IPC, IMACEC, desempleo, FX)
6. Chile Extended (BCCh: 90+ series sectoriales)
7. China (FRED+IMF: GDP, PMI, CPI, credit impulse)
8. Rates (FRED+BCCh: UST curve, SOFR swaps, BCP/BCU)
9. Risk (yfinance+FRED: VIX, spreads IG/HY, VaR)
10. International (OECD+ECB+BCCh: macro global)
- Plus: BEA, OECD, NY Fed, Bloomberg, Intelligence Digest, Research

**Equity Data Collector** (`equity_data_collector.py`) — 11 módulos:
1. Regional Valuations (yfinance: P/E, P/B, Div Yield — 6 regiones)
2. Sector Data (yfinance: 11 GICS sectors)
3. Risk/Correlations (yfinance: VaR, Sharpe, drawdown)
4. Earnings (AlphaVantage: beat rates, estimaciones, calendar)
5. Factor Data (AlphaVantage: value, growth, quality, momentum)
6. Real Rates (FRED: TIPS, breakevens)
7. Credit Spreads (FRED/ICE: IG/HY OAS)
8. Style Data (factor returns decomposition)
9. DF Intelligence (7-day sentiment)
10. BCCh Indices (IPSA/IGPA, índices intl, FX, commodities)
11. Chile Top Picks (yfinance ADRs: BCH, BSAC, SQM, LTM, CCU)

**RF Data Collector** (`rf_data_collector.py`) — 13 módulos:
1. Duration analytics
2. Yield Curve (UST: 2Y, 5Y, 10Y + spreads)
3. Credit Spreads (IG/HY OAS + momentum)
4. Inflation (CPI, breakevens, TIPS)
5. Fed Expectations (dots + futuros)
6. TPM Expectations (BCCh encuesta)
7. Fed Dots (FOMC SEP)
8. BCCh Encuesta (EOF/EEE)
9. Credit Duration
10. International Yields (8 países via BCCh)
11. Chile Yields (BCP 1Y-10Y, BCU 5Y-30Y, breakevens, slopes)
12. Chile Rates (TPM, DAP, interbancaria, consumo/comercial/vivienda, intl policy rates)
13. Sovereign Curves (Bund 9T via ECB + JGB 11T via MoF Japan)

**Forecast Engine** (`forecast_engine.py`) — 4 módulos + IMF:
1. **Inflation** (3 regiones): Breakevens 40% + ARIMA 20% + Phillips 20% + IMF 20%
2. **Rates** (3 bancos centrales): Futures 40% + ARIMA 20% + Taylor Rule 20% + Forward Guidance 20%
3. **GDP** (4 regiones): GDPNow 40% + ARIMA 20% + VAR 20% + IMF 20%
4. **Equity Targets** (6 índices): EYG 30% + Fair PE 25% + PE Reversion 20% + Consensus 15% + Regime 10%
5. **IMF WEO**: GDP + CPI consensus (4 regiones)

**Modelos Econométricos** (`econometric_models.py`):
- ARIMAForecaster: pmdarima auto_arima, lookback 20Y (2003-hoy)
- VARForecaster: 4-variable USA [GDP, CPI, Fed Funds, Unemployment]
- TaylorRule: Fed + TPM Chile + ECB (con inercia)
- PhillipsCurve: OLS π = α + β(u-u*) con lag 6M

---

## 4. AI Council — Detalle

### 4.1 Agentes Panel (Capa 1)

| Agente | Modelo | Max Tokens | Ve | Prompt |
|--------|--------|------------|-----|--------|
| **MACRO** | claude-sonnet-4-6 | 6000 | regime, macro_usa, inflation, chile, china, rates, leading indicators | `prompts/ias_macro.txt` |
| **RV** | claude-sonnet-4-6 | 6000 | valuations, sectors, earnings, factors, risk (VIX, breadth) | `prompts/ias_rv.txt` |
| **RF** | claude-sonnet-4-6 | 6000 | duration, yield_curve, credit_spreads, inflation, rates, expectations | `prompts/ias_rf.txt` |
| **RIESGO** | claude-sonnet-4-6 | 6000 | risk scorecard (VIX, VaR, drawdown), breadth, EPU, credit | `prompts/ias_riesgo.txt` |
| **GEO** | claude-sonnet-4-6 | 6000 | chile, china, international, commodities, intelligence themes | `prompts/ias_geo.txt` |

### 4.2 Síntesis (Capa 2)

| Agente | Modelo | Recibe | Produce |
|--------|--------|--------|---------|
| **CIO** | claude-opus | 5 paneles + research + Bloomberg context | Síntesis coherente (~800 words) |
| **CONTRARIAN** | claude-opus | CIO síntesis + 5 paneles | Crítica + supuesto más peligroso + analogías históricas (~600-800 words) |
| **REFINADOR** | claude-opus | CIO + Contrarian + council_input completo | Documento final con `[BLOQUE: X]` (~8000 words) |

### 4.3 Output Estructurado (Capa 3)

El Refinador produce bloques delimitados que `council_parser.py` extrae:
- `[BLOQUE: EQUITY_VIEWS]` → OW/N/UW por región con convicción
- `[BLOQUE: FI_POSITIONING]` → Duración, crédito, curva
- `[BLOQUE: ESCENARIOS]` → Base/Bull/Bear con probabilidades
- `[BLOQUE: RISK_MATRIX]` → Top 5 riesgos con prob/impacto/equity%/RF bps/análogo
- `[BLOQUE: CORRELACIONES]` → Equity-bonds, cross-asset, Gold-USD (actual/1Y/5Y)
- `[BLOQUE: SECTOR_VIEWS]` → 11 GICS con OW/N/UW
- `[BLOQUE: FX_VIEWS]` → USD/CLP, EUR/USD, etc.
- `[BLOQUE: REGIONAL_ALLOCATION]` → Pesos por región vs benchmark

### 4.4 Filtros Anti-Fabricación

1. `narrative_engine.validate_narrative()` — extrae números del LLM, compara vs datos verificados, reemplaza fabricaciones
2. `council_parser.py` — prioriza datos estructurados sobre text-mining
3. `coherence_validator.py` — 13 métricas cross-report con tolerancias definidas
4. `_check_panel_coherence()` — detecta contradicciones entre agentes post-panel

---

## 5. Sistema de Reportes

### 5.1 Design System (compartido)

- **Marca**: Greybark Research (NUNCA "Advisors" — legal)
- **Header**: Split layout — "GREYBARK RESEARCH" (Archio Black, uppercase, izq) + fecha (der)
- **Colores**: Orange accent `#dd6b20`, body negro/gris, tablas `#1a1a1a` header
- **Badges**: OW=verde `#276749`, N=warm-neutral `#744210`, UW=rojo `#c53030`
- **Tipografía**: Archio Black (títulos), Segoe UI 10pt (body)
- **Layout**: 1000px max-width, print-ready con `page-break-inside: avoid`
- **Charts**: Base64-encoded PNG inline (sin dependencias externas)

### 5.2 Flujo por Reporte

```
council_result + market_data + charts
         ↓
  *_content_generator.py     ← combina council + API data + fallbacks
         ↓
  narrative_engine.py        ← genera prosa (Claude Sonnet) + valida números
         ↓
  *_report_renderer.py       ← Jinja2 template rendering
         ↓
  output/reports/*.html      ← reporte final
```

### 5.3 Charts por Reporte

**Macro (28 charts)**:
- BCCh (13): inflation_evolution, inflation_heatmap, commodity_prices, energy_food, fed_vs_ecb_bcch, europe_dashboard, global_equities, china_dashboard, chile_dashboard, chile_inflation_components, chile_external, latam_rates, epu_geopolitics
- FRED (9): labor_unemployment, labor_nfp, labor_jolts, labor_wages, usa_leading_indicators, yield_curve, yield_spreads, inflation_components_ts (ahora FRED), + otros
- Content-derived (2): gdp_comparison, scenarios_pie
- Bloomberg Excel (3, OK): pmi_global, europe_pmi, china_trade
- Otros: risk_matrix

**RV (12 charts)**: regional_performance, pe_valuations, sector_heatmap, earnings_beat, style_box, correlation, vix_range, chile_ipsa_copper, credit_risk, drawdown, factor_radar (yfinance fallback), earnings_revisions

**RF (8 charts)**: yield_curve, credit_spreads, breakevens, chile_curves, policy_rates, fed_expectations, tpm_expectations, intl_yields

**AA (0 charts)**: solo tablas y badges (Dashboard 2x2, Portafolios Modelo 5×9, Focus List ETFs)

---

## 6. Gaps y Problemas Conocidos

### 6.1 Módulos Resueltos (2026-03-18)

Todos los módulos previamente faltantes han sido implementados:
- ✅ `AKShareClient` — China NBS data (38 campos: PMI, CPI, PPI, M2, TSF, LPR, RRR, Trade, Property, Activity)
- ✅ `curvas_soberanas` — ECB Data Portal + MoF Japan (9+11 tenors, cache 4h, stale fallback)
- ✅ `AlphaVantageClient.get_top_gainers_losers()` — Market movers
- ✅ `BCChExtendedClient` — EEE/EOF/IMCE/GDP intl (depende de disponibilidad BCCh API)
- ✅ Breadth timezone bug — Fixed: `year_start` now preserves tz-awareness from index

### 6.2 Charts PMI (Bloomberg Excel — Operativos)

Los 3 charts PMI **no están bloqueados** — funcionan via `input/bloomberg_data.xlsx`:
- ✅ `pmi_global` — ISM Mfg/Svc + Euro PMI + China PMI
- ✅ `europe_pmi` — Euro PMI composite
- ✅ `china_trade` — China trade balance

### 6.3 Bugs Resueltos (2026-03-19 — Auditoría Completa)

| Bug | Ubicación | Fix | Commit |
|-----|-----------|-----|--------|
| Credit spreads 1bp (FRED OAS sin ×100) | `credit_spreads.py:_fetch_spread_series()` | ×100 en fuente → 77bp correcto | `5210d3e` |
| Dividend yields 106%/308% | `equity_data_collector.py:175` | Condicional: solo ×100 si valor <1 | `5210d3e` |
| TPM `{'current': 4.5}` raw dict en HTML | `asset_allocation_content_generator.py:_q()` | Unwrap 'current' key junto con 'value' | `5210d3e` |
| SELIC None% | `asset_allocation_content_generator.py:602` | Guard con format None → 'N/D' | `5210d3e` |
| IMACEC "expansión de -0.5%" | `macro_content_generator.py:1728` | Dinámico: expansión/contracción según signo | `5210d3e` |
| Council markdown leak en commodity table | `macro_content_generator.py:_commodity_outlook()` | Strip `#` headers y `**bold**` antes de text-mine | `5210d3e` |
| Calendario con fechas pasadas | `macro_content_generator.py:2160` | Prompt filtrado: solo eventos futuros | `5210d3e` |
| CLP/USD dirección contradictoria | `asset_allocation_content_generator.py` + prompts | `CLP_USD_DIRECTIVE` inyectado en 4 prompts Chile | `d037cd5` |
| TPM narrativa contradice tendencia | `asset_allocation_content_generator.py` | Tendencia computada ANTES de narrativa LLM | `f4b3dc9` |
| max_tokens truncación de textos | `ai_council_runner.py` + 4 content generators | Panel 4000, Refinador 12000, narrativas 300-500 | `472835d` |
| RV stance NEUTRAL cuando council dice UW | `rv_content_generator.py:316-337` | Agregado 'subponder'/'UW'/'OW' al extractor | `72a3fa0` |
| S&P/IPSA P/E swap en Key Calls | `rv_content_generator.py:_generate_key_calls()` | Pass verified_data → anti-fabricación corrige | `72a3fa0` |
| Chile IPC YoY "---" en AA | `rf_data_collector.py` + `aa_content_gen` | IPC YoY calculado desde BCCh + fallback `chile_rates.ipc_yoy` | `72a3fa0` |
| EM country drivers copy-paste | `rf_content_generator.py:_generate_em_by_country()` | Per-country drivers con yields reales + contexto local | `72a3fa0` |
| USD/CLP targets inconsistentes (820 vs 880) | `asset_allocation_content_generator.py` | Target programático pasado como binding context a LLM | `72a3fa0` |
| HY B rating commentary idéntico a BB | `rf_content_generator.py:1645` | Fallback diferenciado por rating | Sprint 1 |
| Señal temprana duplica horizonte en risk cards | `macro_content_generator.py:2236` | Lee `early_signal`/`monitoring` | Sprint 1 |
| Risk card horizonte/señal mezclados en HTML | `macro_report_renderer.py:565` | Campos separados con labels | Sprint 1 |
| EV/EBITDA columna vacía en RV | `rv_report_renderer.py:211` + template | Columna oculta si todos N/D | Sprint 1 |
| Missing accents en 4 templates HTML (~50) | 4 templates HTML | Comité, Crédito, Región, Recomendación, glosarios, disclaimers | Sprint 1 |
| US Fiscal section N/D (sin fuente FRED) | `chart_data_provider.py` + `macro_content_generator.py` | `get_usa_fiscal()` con 3 FRED series | `6f55067` |
| China Trade chart 190 pts sin trim | `chart_generator.py:1764` | Trim a 120 meses consistente | `6f55067` |
| `fed_rate` regex false positive | `narrative_engine.py:170` | Regex requiere "Funds"/"rate"/"tasa fed" | Sprint 2 |
| Panel agents truncados (4000 tokens) | `ai_council_runner.py:54` | MAX_TOKENS 4000→6000 | Sprint 2 |
| Oil fabricado sin corrección | `narrative_engine.py` | oil/WTI/Brent pattern + KEY_SOURCE_MAP | Sprint 2 |
| Badge CSS solo inglés | `rf/rv/aa_report_renderer.py` | Sobreponderar/Subponderar acepta | Sprint 2 |
| BCCh commodity data stale (3-7 semanas) | `chart_data_provider.py` | `_append_spot_if_stale()` yfinance | Sprint 3 |
| S&P 500 +21.8% (2/5 modelos) | `forecast_engine.py` | PE key fallback + derive from trailing | Sprint 3 |
| Consensus 79.5% (50DMA) | `forecast_engine.py` | yfinance current price + ±30% cap | Sprint 3 |
| Regime "UNKNOWN" | `council_data_collector.py:78` | `classification` key fix | Sprint 3 |
| EuroStoxx FEZ≠EFA | `forecast_engine.py:65` | FEZ→EFA en EQUITY_UNIVERSE | Sprint 3 |
| Factor Performance "sin scores" | `rv_chart_generator.py` | yfinance factor fallback | Sprint 4 |
| 24 acentos glosario RV | `templates/rv_report_professional.html` | Todos corregidos | Sprint 4 |
| RF acentos: Crédito, Inflación, País, Centésimas | `rf_content_generator.py` + template | 6 correcciones | Sprint 5 |
| EM badge hardcoded `badge-ow` para NEUTRAL | `rf_report_renderer.py` + template | Dynamic `{{em_hc_class}}`/`{{em_lc_class}}` | Sprint 5 |
| AA acentos: Política, Geopolítica, Términos, etc. | `templates/asset_allocation_professional.html` | 7 correcciones | Sprint 5 |
| AA PE siempre N/D (key `pe` → `pe_forward`) | `asset_allocation_content_generator.py` | Lookup chain: pe_forward→pe_trailing→pe | Sprint 5 |
| AA VIX N/D (dict not unwrapped) | `asset_allocation_content_generator.py` | `.get('current')` unwrap | Sprint 5 |
| AA TPM N/D (dict not unwrapped) | `asset_allocation_content_generator.py` | `.get('current')` unwrap + canon fallback | Sprint 5 |
| AA UST yields N/D (wrong path) | `asset_allocation_content_generator.py` | `yield_curve.current_curve.2Y/10Y` | Sprint 5 |
| AA SELIC N/D (wrong key) | `asset_allocation_content_generator.py` | `chile_rates.policy_rates.bcb` | Sprint 5 |
| AA breakeven N/D (wrong path) | `asset_allocation_content_generator.py` | `inflation.breakeven_inflation.current.breakeven_5y` | Sprint 5 |
| Calendar table 4 cols vs 3 header cols | `table_builder.py` | Removed orphan `impacto` column | Sprint 5 |
| TPM expectations start at 5.0% (actual 4.5%) | `rf_data_collector.py` | Auto-fetch from BCCh API at init | Sprint 6 |
| Fed Funds default 4.50% (actual EFFR 3.64%) | `rf_data_collector.py` | Auto-fetch from FRED DFF at init | Sprint 6 |
| 6 standalone rate defaults stale | `rate_expectations/*.py` | TPM 5.00→4.50, Fed 4.50→3.75 | Sprint 6 |
| BCCh dates DD-MM swapped (day<=12) | `bcch_client.py:98` | `dayfirst=True` — fixes WTI +50%, commodity returns | Sprint 7 |
| RV earnings headers EPS→Beat Rate/P/E | `rv_report_professional.html` | Headers match actual data | Sprint 7 |
| AA scenarios sum 90% | `asset_allocation_content_generator.py` | Auto-add residual scenario | Sprint 7 |
| AA 3 copper prices incoherent | `asset_allocation_content_generator.py` | Canon value first in all 3 methods | Sprint 7 |
| AA MODERATE_GROWTH raw code visible | `asset_allocation_content_generator.py` | `_REGIME_LABELS` dict mapping | Sprint 7 |
| AA Focus List 18 rationales in English | `asset_allocation_content_generator.py` | All translated to Spanish | Sprint 7 |
| RV truncation marker visible | `narrative_engine.py:1089` | Marker removed from output | Sprint 7 |
| RF trades duplicados S3/S7 | `templates/rf_report_professional.html` | Removed duplicate S3 | Sprint 8 |
| RF FAIR_VALUE/EXPENSIVE raw enum | `rf_content_generator.py` | `_translate_signal()` → español | Sprint 8 |
| RF HY badge siempre neutral | `rf_report_renderer.py` + template | Dynamic `{{hy_badge_class}}` | Sprint 8 |
| RV narrativas garbled | `rv_content_generator.py` | `_truncate_at_sentence()` helper | Sprint 8 |
| AA macro indicators vacía | `asset_allocation_content_generator.py` | Keys: gdp_qoq, cpi_core_yoy | Sprint 8 |
| AA dashboard flechas todas → | `asset_allocation_content_generator.py` | `_arrow_from_view()` | Sprint 8 |
| ~95 acentos faltantes 4 reportes | 12 archivos (templates + generators + renderers) | Sprint 9 |
| ~20 labels inglés → español | templates + content generators | Sprint 9 |
| Litio USD/ton (incorrecto) | 4 archivos | → USD/kg | Sprint 9 |

### 6.4 Bugs Conocidos (Activos)

| Bug | Ubicación | Impacto | Estado |
|-----|-----------|---------|--------|
| BCU 2Y sin datos | BCCh API `F022.BUF.TIS.AN02.UF.Z.D` | Serie vacía → skip | Permanente (BCCh no publica) |
| EMBI Chile sin datos | BCCh API `F019.EMBI.IND.CL.D` | Sin spread Chile directo | Usar BCRP client como fallback |
| ~~CPI subcomponents chart vacío~~ | `chart_data_provider.py` | **RESUELTO** — FRED 5 series OK, chart genera 78KB | Sprint 10 |
| ~~Raw markdown leak en RF HTML~~ | `rf_report_renderer.py` | **RESUELTO** — `_md_to_html()` en 12 campos | Sprint 10 |

### 6.5 Datos Hardcodeados (Sin API)

| Dato | Razón | Fallback Actual |
|------|-------|-----------------|
| CDS Soberanos | Propietario (Bloomberg) | Bloomberg Excel si disponible |
| EPFR Fund Flows | Propietario | Bloomberg Excel |
| Positioning (CFTC-like) | Propietario | Bloomberg Excel |
| BTP 20Y/30Y Chile nominal | BCCh no publica BTP largo | BCU + breakeven implícito |
| Euro/UK real yields | No hay serie directa pública | Nominal - breakeven estimado |
| Refinancing calendar | Manual | Hardcoded en content generator |
| Credit by sector detail | API limitada | Totales IG/HY solamente |

### 6.6 Dependencias Bloomberg

El archivo `input/bloomberg_data.xlsx` (22 hojas, 95 series) provee datos que **no tienen alternativa pública gratuita**:

| Hoja | Datos | Prioridad en Manifest |
|------|-------|-----------------------|
| PMI | ISM Mfg/Svc, Euro PMI, China PMI | IMPORTANT (macro, rv) |
| CDS | Soberanos 5Y (14 países) | IMPORTANT (rf, riesgo, geo) |
| Credit_Spreads | OAS IG/HY por sector | IMPORTANT (rf, riesgo) |
| SOFR | SOFR Swap Curve 19 tenors | IMPORTANT (rf) |
| EPFR_Flows | Fund flows por región/asset class | OPTIONAL |
| Positioning | Net speculative positions | OPTIONAL |
| CPI_Componentes | Shelter, Services ex-Housing | REPLACED (ahora FRED) |

### 6.7 Test Coverage

**Estado actual: Mínimo**
- `test_charts.py` — test manual de chart generation
- `tests/__pycache__/test_curvas_soberanas.cpython-311-pytest` — cache huérfano, sin source
- **Sin tests**: collectors (10+11+12 módulos), forecast engine, council parser, coherence validator, content generators, renderers

---

## 7. Estructura de Archivos

```
consejo_ia/
├── run_monthly.py                    # Entry point — pipeline completo
├── run_monthly.bat                   # Windows launcher
│
├── # ---- FASE 1: Recopilación ----
├── council_data_collector.py         # 10+ módulos macro quant
├── equity_data_collector.py          # 11 módulos equity
├── rf_data_collector.py              # 13 módulos renta fija
├── forecast_engine.py                # 4 módulos + IMF
├── econometric_models.py             # ARIMA, VAR, Taylor, Phillips
├── imf_weo_client.py                 # IMF WEO consensus
├── ecb_client.py                     # ECB SDMX
├── bcrp_embi_client.py              # BCRP EMBI LatAm
├── bloomberg_reader.py               # Bloomberg Excel loader
├── daily_intelligence_digest.py      # Digest de reportes diarios
├── research_analyzer.py              # Análisis research externo (LLM)
│
├── # ---- FASE 2: Pre-Council ----
├── pre_council_package.py            # Charts + validación + briefing
├── antecedentes_briefing_generator.py # Libro de antecedentes HTML
├── council_preflight_validator.py    # Gate GO/CAUTION/NO_GO
├── data_manifest.py                  # Manifest formal de datos + charts
│
├── # ---- FASE 3: AI Council ----
├── ai_council_runner.py              # 3-layer council executor
├── council_parser.py                 # Extractor [BLOQUE: X]
├── coherence_validator.py            # 13 métricas cross-report
├── narrative_engine.py               # LLM narrativas + anti-fabricación
│
├── # ---- FASE 4: Reportes ----
├── macro_report_renderer.py          # Renderer Macro
├── macro_content_generator.py        # Content Macro
├── rv_report_renderer.py             # Renderer RV
├── rv_content_generator.py           # Content RV
├── rf_report_renderer.py             # Renderer RF
├── rf_content_generator.py           # Content RF
├── asset_allocation_renderer.py      # Renderer AA
├── asset_allocation_content_generator.py # Content AA
│
├── # ---- Charts ----
├── chart_generator.py                # Macro charts (28)
├── rv_chart_generator.py             # RV charts (12)
├── rf_chart_generator.py             # RF charts (8)
├── chart_data_provider.py            # BCCh + FRED real data layer
│
├── # ---- Utilidades ----
├── api_health_checker.py             # Health check de APIs
├── # dashboard.py ELIMINADO          # Era Streamlit, reemplazado por deploy/app.py
├── html_nd_cleaner.py                # Limpieza N/D en HTML
│
├── # ---- Library ----
├── greybark/
│   ├── config.py                     # FREDSeries, BCChSeries, API configs
│   ├── data_sources/
│   │   ├── bcch_client.py            # BCCh REST API
│   │   ├── bcch_extended.py          # BCCh Extended (90+ series)
│   │   ├── fred_client.py            # FRED API
│   │   ├── alphavantage_client.py    # AlphaVantage (+ market movers)
│   │   ├── akshare_client.py         # AKShare — China NBS/Eastmoney (38 campos)
│   │   ├── nyfed_client.py           # NY Fed
│   │   ├── oecd_client.py            # OECD KEI
│   │   ├── bea_client.py             # BEA (Bureau of Economic Analysis)
│   │   └── commloan_scraper.py       # SOFR forwards
│   └── analytics/
│       ├── regime_classification/    # Regime classifier (expansion/recession/etc)
│       ├── risk/                     # VaR, CVaR, drawdown
│       ├── breadth/                  # Market breadth (tz-aware)
│       ├── chile/                    # Chile analytics
│       ├── china/                    # China credit impulse
│       ├── credit/                   # Credit spreads
│       ├── earnings/                 # Earnings analytics
│       ├── factors/                  # Factor analytics
│       ├── fixed_income/             # Duration analytics
│       └── macro/                    # Inflation, macro dashboard
│
├── prompts/                          # System prompts (8 agentes)
│   ├── ias_macro.txt
│   ├── ias_rv.txt
│   ├── ias_rf.txt
│   ├── ias_riesgo.txt
│   ├── ias_geo.txt
│   ├── ias_cio.txt
│   ├── ias_contrarian.txt
│   └── refinador.txt
│
├── templates/                        # HTML templates (4 reportes)
│   ├── macro_report_professional.html
│   ├── rv_report_professional.html
│   ├── rf_report_professional.html
│   └── asset_allocation_professional.html
│
├── data_fetchers/                    # Módulos de datos especializados
│   ├── __init__.py
│   └── curvas_soberanas.py           # ECB Data Portal + MoF Japan (20 tenors)
│
├── input/                            # Inputs manuales
│   ├── bloomberg_data.xlsx           # Bloomberg time series
│   ├── user_directives.txt           # Foco del mes
│   ├── research/                     # Bank research extracts
│   └── logos/                        # Branding assets
│
└── output/                           # Generado (gitignored)
    ├── reports/                      # HTML reportes finales
    ├── council/                      # Council results JSON
    ├── equity_data/                  # Equity data JSON
    ├── rf_data/                      # RF data JSON
    ├── forecasts/                    # Forecast JSON
    └── pre_council/                  # Pre-council package JSON
```

---

## 8. Variables de Entorno Requeridas

```bash
# Obligatorias
ANTHROPIC_API_KEY=sk-ant-...    # Claude API (council + narrativas)
FRED_API_KEY=...                 # FRED (macro USA, yields, spreads)
BCCH_USER=...                    # BCCh REST (Chile + internacional)
BCCH_PASSWORD=...                # BCCh REST

# Importantes
ALPHAVANTAGE_API_KEY=...         # Earnings data (plan Premium $49.99/mo)
BEA_API_KEY=...                  # GDP components, PCE, profits

# Opcionales (sin key = módulo skip silencioso)
# No se necesitan keys para: IMF WEO, ECB, BCRP, NY Fed, OECD, yfinance, CommLoan
```

---

## 9. Cómo Ejecutar

```bash
cd estructuras/consejo_ia

# Pipeline completo (recopila + council + 4 reportes)
python run_monthly.py --no-confirm

# Reusar datos, solo council + reportes
python run_monthly.py --skip-collect --no-confirm

# Solo reportes específicos
python run_monthly.py --skip-collect --no-confirm --reports rv rf

# Dry run (solo recopilación, sin council ni reportes)
python run_monthly.py --dry-run

# Costo estimado: ~$2-3 USD por ejecución (8 llamadas Claude)
# Tiempo estimado: ~15-20 min (collect ~5min, council ~7min, reports ~6min)
```

---

## 10. Resumen de Cobertura de Datos

### Por Fuente
| Fuente | Series Activas | Status | Costo |
|--------|---------------|--------|-------|
| FRED | 50+ | ✅ OK | Gratis |
| BCCh REST | 93+ | ✅ OK (algunos gaps en Extended) | Gratis |
| yfinance | ~30 tickers | ✅ OK | Gratis |
| AlphaVantage | ~45 calls/run | ✅ OK | $49.99/mo |
| BEA | 6 tablas NIPA | ✅ OK | Gratis |
| IMF WEO | 8 series (4 regiones × 2) | ✅ OK | Gratis |
| ECB SDMX | 5 series | ✅ OK | Gratis |
| BCRP | 8 EMBIG spreads | ✅ OK | Gratis |
| NY Fed | 5 módulos | ✅ OK | Gratis |
| OECD KEI | 4-6 indicadores × 58 países | ✅ OK | Gratis |
| CommLoan | 7 SOFR forwards | ✅ OK (scraper) | Gratis |
| Bloomberg Excel | 95 series / 22 hojas | ⚠️ Manual refresh | Terminal |
| AKShare (NBS) | 38 campos China | ✅ OK | Gratis |
| ECB Data Portal | 9 tenors EUR AAA | ✅ OK | Gratis |
| MoF Japan | 11 tenors JGB | ✅ OK | Gratis |

### Por Reporte — % Datos Reales
| Reporte | Charts Reales | Charts Estimados | % Real |
|---------|--------------|-----------------|--------|
| Macro | 28/28 | 0 (PMI via Bloomberg Excel) | 100% |
| RV | 12/12 | 0 | 100% |
| RF | 8/8 | 0 | 100% |
| AA | n/a (tablas) | n/a | ~90% (depende de council) |

### Datos Solo Bloomberg (Sin Alternativa Pública)
- CDS Soberanos — requiere Bloomberg Terminal
- EPFR Fund Flows — requiere suscripción EPFR
- Positioning (CFTC-style) — requiere Bloomberg Terminal
- PMI (ISM/Markit) — disponible en `bloomberg_data.xlsx`

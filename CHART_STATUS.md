# Chart Data Sources — Greybark Research

Last updated: 2026-03-27

## Summary

| Report | Total Charts | 100% Real | Partial Real | Fallback/Estimated |
|--------|-------------|-----------|-------------|-------------------|
| Macro  | 23          | 17        | 3           | 3                 |
| RV     | 12          | 12        | 0           | 0                 |
| RF     | 8           | 8         | 0           | 0                 |
| Briefing | 44        | 44        | 0           | 0                 |
| **Total** | **87**   | **81**    | **3**       | **3**             |

Real data percentage: **93%** (81/87)

### Recent Changes (Sprint 18-24)
- risk_matrix chart fix: extract `riesgos` list from nested dict (was crashing)
- inflation_components_ts: Bloomberg fallback when FRED incomplete
- RF yield_curve: 8/8 charts generating on server (was blocked by ChartDataProvider init)
- Briefing: 44 charts all base64 embedded, verified clean on production
- All RV/RF charts verified generating correctly on Hetzner server (matplotlib Agg backend)

## Macro Report Charts (22)

### 100% Real API Data (15)
| Chart | Source | API |
|-------|--------|-----|
| inflation_evolution | BCCh API | USA PCE, Euro HICP, Chile IPC YoY |
| labor_unemployment | FRED API | UNRATE (U3) + U6RATE |
| labor_nfp | FRED API | PAYEMS (Non-Farm Payrolls) |
| labor_jolts | FRED API | JTSJOL, JTSTSRR |
| labor_wages | FRED API | CES0500000003 (Avg Hourly Earnings) |
| inflation_heatmap | BCCh API | 24-month CPI by component |
| commodity_prices | BCCh API | Brent, Copper, Gold |
| energy_food | BCCh + FRED | WTI, Natural Gas (FRED) |
| fed_vs_ecb_bcch | BCCh API | 6 central bank policy rates |
| usa_leading_indicators | FRED API | ISM, Housing, Consumer Confidence |
| chile_dashboard | BCCh API | GDP, CPI, TPM, IMACEC |
| chile_inflation_components | BCCh API | 13 COICOP divisions (F074.IPC) |
| latam_rates | BCCh API | LatAm policy rates |
| yield_curve / yield_spreads | FRED API | UST curve 1M-30Y |
| inflation_components_ts | FRED API | CPI Shelter/Services/Goods/Food/Energy YoY |

### Partial Real + Latest Override (3)
| Chart | Historical | Latest Point | Source |
|-------|-----------|-------------|--------|
| pmi_global | Interpolated pattern | Bloomberg/AKShare latest | ISM/Markit proprietary |
| europe_pmi | Interpolated pattern | Bloomberg latest | Markit proprietary |
| china_dashboard | BCCh if available | BCCh/AKShare | BCCh F019 + NBS |

### Fully Estimated Fallback (4)
| Chart | Reason | Notes |
|-------|--------|-------|
| europe_dashboard | Euro GDP by country not in BCCh/FRED | Would need Eurostat API |
| china_trade | China exports/imports proprietary | Would need NBS/Customs |
| chile_external | Chile trade balance from BCCh (partial) | Exports+Imports+Copper+Balance |
| epu_geopolitics | Economic Policy Uncertainty Index proprietary | FRED has EPU but incomplete |

## RV Report Charts (12)
All 12 charts use real data from `EquityDataCollector`:
- yfinance: ETF valuations, sector returns, style factors
- AlphaVantage: earnings data
- FRED: credit spreads, real rates
- BCCh: IPSA, copper, international indices

## RF Report Charts (8)
All 8 charts use real data:
- BCCh API: Chile BCP/BCU curves, international yields, TPM
- FRED API: UST yield curve, credit spreads, breakevens, Fed expectations
- ECB Data Portal + MoF Japan: Bund (9T) + JGB (11T) overlaid on yield curve chart

## Dynamic Benchmarks

| Benchmark | Source | Fallback |
|-----------|--------|----------|
| NAIRU (unemployment) | FRED `NROU` (CBO quarterly) | 4.2% |
| Inflation target | Policy-defined | 2.0% (Fed/ECB), 3.0% (BCCh) |
| PMI threshold | Fixed | 50.0 (expansion/contraction) |

## How to Improve Coverage

1. **Eurostat API** → Europe GDP by country, HICP detailed, employment
2. **NBS/CEIC** → China trade, industrial production time series
3. **FRED EPU** → Economic Policy Uncertainty (partial, delayed)
4. **ISM subscription** → USA PMI Manufacturing (paid, ~$500/yr)
5. **Bloomberg Terminal** → Full PMI + CDS + proprietary indices (current Excel approach works)

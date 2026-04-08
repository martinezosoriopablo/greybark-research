# Greybark Research — AI Council System

## What This Is
Automated investment research platform that generates 4 monthly reports using an AI Council (multi-agent architecture with 5 panel analysts + 3 synthesis layers). All reports are in Spanish. The system collects real market data from APIs, runs deliberation through Claude, and renders professional HTML reports.

## Branding (CRITICAL — Legal Requirement)
- Name: **Greybark Research** (NEVER "Advisors" — legal)
- Design: Archio Black font, orange accent `#dd6b20`, Segoe UI body, black/grey scale

## Repository Structure
```
estructuras/
  consejo_ia/              # Main codebase (all Python)
    run_monthly.py         # Entry point — runs full pipeline
    council_data_collector.py  # Phase 1: collects quant data (10 modules)
    equity_data_collector.py   # Phase 1: equity data (11 modules)
    rf_data_collector.py       # Phase 1: fixed income data (12 modules)
    forecast_engine.py         # Phase 1: quantitative forecasts
    council_preflight_validator.py  # Phase 2: GO/CAUTION/NO_GO gate
    ai_council_runner.py       # Phase 3: 3-layer AI council
    macro_report_renderer.py   # Phase 4: Macro report (29 charts)
    rv_report_renderer.py      # Phase 4: Renta Variable report (12 charts)
    rf_report_renderer.py      # Phase 4: Renta Fija report
    asset_allocation_renderer.py   # Phase 4: Asset Allocation report
    *_content_generator.py     # Content generation for each report
    chart_data_provider.py     # Real data layer (BCCh + FRED APIs)
    chart_generator.py         # Matplotlib chart generation
    narrative_engine.py        # Claude-powered narrative generation
    council_parser.py          # Structured extraction from council output
    coherence_validator.py     # Cross-report numeric consistency (13 metrics)
    crisis_reference.py        # 8 verified historical crisis episodes for agents
    historical_store.py        # Saves/loads metrics between runs for "anterior" columns
    report_quality_checker.py  # Post-render empty cell detection
    causal_tree_renderer.py    # SVG renderer for CIO's causal tree
    analyst_calls_reader.py    # Reads analyst calls from greybark-intelligence
    taa_data_collector.py      # Quantitative TAA model collector
    taa_report_section.py      # TAA section HTML renderer for AA report
    templates/                 # HTML templates for each report
    output/                    # Generated reports (gitignored)
    input/                     # User directives, research, logos
    prompts/                   # Agent prompt templates
  02_greybark_library/         # Shared analytics library
    greybark/
      data_sources/            # API clients (BCCh, FRED, AlphaVantage)
      analytics/               # Risk, earnings, breadth, credit modules
      config.py                # Series codes, API keys config
```

## How to Run
```bash
cd estructuras/consejo_ia

# Full pipeline (collects data + council + 4 reports)
python run_monthly.py --no-confirm

# Skip data collection (reuse cached data)
python run_monthly.py --skip-collect --no-confirm

# Only specific reports
python run_monthly.py --skip-collect --no-confirm --reports rv rf

# Dry run (collect only, no council/reports)
python run_monthly.py --dry-run
```

## Pipeline Phases
1. **Collect** — Macro (10 modules), Equity (11), RF (12), Forecasts (4), Intelligence, Research
2. **Preflight** — Validates data completeness, verdict: GO / CAUTION / NO_GO
3. **Council** — 5 panel agents (macro/rv/rf/riesgo/geo) -> CIO synthesis -> Contrarian -> Refinador
4. **Reports** — 4 HTML reports with real data + council narratives + charts
5. **Summary** — Pipeline status report

## Data Sources
- **BCCh API** (Banco Central de Chile): Chilean macro, rates, FX, commodities, international indices
- **FRED API** (Federal Reserve): US macro, yields, spreads, inflation
- **AlphaVantage**: Earnings, fundamentals, analyst estimates
- **yfinance**: ETF valuations, returns, VIX, risk metrics
- **IMF WEO API**: GDP/inflation consensus forecasts
- **greybark-intelligence**: Analyst calls from Telegram + Substack (BUY/SELL with thesis, conviction)
- **TAA Model**: Quantitative tactical asset allocation (24 ETFs, 16 FRED series, IR 0.40)

## Environment Requirements
- Python 3.10+
- `ANTHROPIC_API_KEY` — Claude API (for council + narratives)
- `FRED_API_KEY` — FRED data
- `ALPHAVANTAGE_API_KEY` — Earnings data
- `BCCH_USER` + `BCCH_PASSWORD` — Banco Central de Chile API
- Dependencies: anthropic, pandas, matplotlib, yfinance, pmdarima, statsmodels, requests, jinja2

## Architecture Notes

### PRINCIPIO CRÍTICO: Máxima Información al Council
El AI Council toma mejores decisiones con MÁS datos, no menos. NUNCA limitar arbitrariamente
la información que llega a los agentes. Si un preflight limit bloquea datos válidos, SUBIR el
límite — no truncar los datos. Sprint 45 documentó un caso donde un `DAILY_CONTEXT_LIMIT=4000`
abortó el council porque el intelligence digest (13K chars) era "demasiado grande", causando
reportes con datos inventados/stale. El límite se subió a 15000.

### Datos que recibe el AI Council
Cada agente recibe TODA esta información en su prompt:
1. **Datos cuantitativos** — 25 módulos (FRED, BCCh, yfinance, Bloomberg, BEA, OECD, NY Fed, IMF)
2. **Reportes diarios** — Intelligence digest de ~13K chars (41+ reportes, 23+ temas, 49+ ideas tácticas, sentimiento semanal)
3. **Analyst calls** — Recomendaciones de analistas de Telegram/Substack (~35 calls/semana con BUY/SELL, thesis, conviction)
4. **Señales TAA** — Modelo cuantitativo de asset allocation (24 ETFs, 16 FRED series, IR 0.40, stress score, tilts)
5. **Bloomberg** — 95 series históricas con percentiles 5Y (`p5Y: XX` en cada línea)
6. **Episodios de crisis** — 8 episodios verificados (GFC, COVID, Taper, SVB, etc.) con impactos cuantificados
7. **Research externo** — PDFs de Goldman Sachs, Vanguard, etc. sintetizados por Claude
8. **Directivas del usuario** — Instrucciones específicas del comité

### AI Council (3-Layer)
- **Layer 1 (Panel)**: 5 specialist agents in parallel, each sees filtered data by expertise + daily intelligence + analyst calls + TAA signals + crisis reference
- **Layer 2 (Synthesis)**: CIO synthesizes + generates CAUSAL_TREE -> Contrarian challenges with verified data -> Refinador produces final output
- **Layer 3 (Output)**: Structured blocks parsed by `council_parser.py`
- **Coherence**: Panel conflicts detected and passed to Refinador

### CRÍTICO: Datos Inventados y Tablas Vacías
Si el council NO corre (preflight NO_GO, API error, timeout), el narrative_engine genera texto
genérico con datos STALE de su entrenamiento — NO de las APIs reales. Esto produce reportes
con información INCORRECTA (ej: "fed funds 5.25%" cuando el real es 3.64%).

Para prevenir esto:
- **NUNCA** bajar preflight limits que bloqueen datos válidos
- **SIEMPRE** verificar que `council_result.final_recommendation` tiene >0 chars antes de renderizar
- **report_quality_checker.py** detecta celdas vacías ("—") post-render en los 4 reportes
- **historical_store.py** guarda métricas entre runs para columnas "anterior"
- **deep merge** (Sprint 39) evita colisiones de datos entre RF y macro_quant

### Content Generation
- Each report has a `*_content_generator.py` that combines council output + real API data
- `narrative_engine.py` calls Claude for narrative sections with anti-fabrication filters
- Anti-fabrication threshold: 2bp for rates, catches discrepancies between LLM output and verified data
- Fallback pattern: council data -> API data -> defaults. If council is empty, narratives are GENERIC — this is a known degradation mode

### Key Patterns
- All modules fail silently: `{'error': str(e)}` — downstream checks before using data
- `_has_data()` / `_has_council()` guards everywhere
- Coherence validator checks 13 shared metrics with strict tolerances (NEVER relax them)
- Bloomberg percentiles: `get_percentile(campo, 5)` adds `p5Y: XX` to every data line

### Report Design System
- All 4 reports share: header (split layout), orange accent, Segoe UI body, black tables
- Section 10 (AA): CAUSAL_TREE SVG visualization
- Section 11 (AA): TAA quantitative tool (stress gauge, tilts, track record)
- Footer: "— = dato no disponible en las fuentes consultadas para este período"
- Print-ready: `page-break-inside: avoid`

## Common Tasks

### Adding a new data source
1. Add API call in the relevant `*_data_collector.py`
2. Add series codes to `greybark/config.py` if BCCh/FRED
3. Wire into content generator with `_has_data()` guard
4. Add to coherence validator if cross-report metric
5. Add to `_prepare_agent_specific_data()` for relevant agents — MORE data is BETTER

### Fixing empty cells in reports
1. Check `council_result.final_recommendation` — if empty, council didn't run (check preflight)
2. Check which `{{placeholder}}` is empty in the template
3. Trace to the content generator method that produces it
4. **Quality checker** runs post-render in all 4 renderers — shows count of "—" cells in pipeline log
5. If council didn't run, narratives will be GENERIC — fix the council, don't fix the narrative

### Historical data store (for "anterior" columns)
`historical_store.py` saves ~30 key metrics per run to `output/historical/snapshot_{date}.json`.
On next run, loads previous snapshot and injects `_prev` values into quant_data before rendering.
`chart_data_provider.get_usa_latest()` also calculates CPI/PCE prev directly from FRED series.

### Modifying council behavior
- Agent prompts: `prompts/ias_*.txt`
- Panel composition: `ai_council_runner.py`
- Output structure: `council_parser.py` (block extraction patterns)
- **NEVER** reduce data limits, token budgets, or tolerances — always increase if needed

### MEJORA CRÍTICA: Datos recolectados que no llegaban a los renderers
**Patrón sistémico** encontrado en 3 reportes: los datos SE RECOLECTAN correctamente pero NO SE
PASAN al renderer porque `run_monthly.py` no los inyecta en el dict de datos del renderer.

| Reporte | Dato faltante | Dónde existía | Dónde faltaba | Fix |
|---------|--------------|---------------|---------------|-----|
| **AA** | macro_quant completo (GDP, CPI, TPM, VIX, etc.) | `council_input.quantitative` | `aa_data` (renderer) | Sprint 37: persist `council_input`, Sprint 39: deep merge |
| **AA** | CPI core (colisión RF vs macro_quant) | `macro_quant.inflation.cpi_core_yoy` | `aa_data.inflation` (RF overwrote it) | Sprint 39: deep merge sub-keys |
| **RF** | sovereign_curves (Bund, JGB) | `macro_quant.sovereign_curves` | `rf_data` (renderer) | Sprint 45d: inject from macro_quant |

**Regla:** Cuando un renderer necesita datos que no están en su JSON cacheado (rf_data, equity_data),
`run_monthly.py._generate_single_report()` debe inyectarlos desde `self.data['macro_quant']`.
Verificar SIEMPRE que los datos llegan al renderer, no solo que se recolectan.

### BUG CRÓNICO RESUELTO: rf_yield_curve (Sprint 45c)
El chart de yield curve del RF report fallaba recurrentemente (Sprints 11, 23, 45c).
**Causa raíz DOBLE:**
1. `rf_chart_generator.py:279` buscaba `cdata['tenors']` pero los datos están en `cdata['datos']`
2. `run_monthly.py` no inyectaba `sovereign_curves` al RF renderer — datos solo en `macro_quant`

**Fixes:** (1) Chart busca en AMBOS `tenors` OR `datos` con parsing robusto. (2) `run_monthly.py` inyecta `sovereign_curves` en `rf_data` antes de pasar al renderer.
**Prevención:** Siempre testear charts CON sovereign_curves inyectadas. Siempre verificar que `run_monthly.py` pasa TODOS los datos al renderer.

### Preflight/Completeness NO_GO bugs (Sprints 45, 45b)
- `DAILY_CONTEXT_LIMIT` debe ser >=15000 (intelligence digest genera 12-14K chars)
- `data_completeness_validator` NO_GO threshold debe ser 60% (no 95%) — 78% de datos es suficiente
- `data_manifest.py`: keys deben coincidir EXACTAMENTE con lo que produce el collector (chile.imacec_yoy, no chile.imacec)
- **PRINCIPIO:** Un council parcial es INFINITAMENTE mejor que reportes con datos inventados

### Roadmap hacia reportes perfectos (Goldman Sachs quality)
**Tier 1 (bugs, fixeados Sprint 47):** HTML roto en narrativas, secciones vacías ocultas, "Puntos Clave" en español, RF probabilidades obligatorias
**Tier 2 (implementados Sprint 48):** "Qué Cambió" tabla, "Qué Está Priceado", conviction ★★★, cross-asset matrix, "Dónde Podemos Estar Equivocados", "Foco del Período" (tema dominante del mes), copper sensitivity Chile, callout boxes (4 tipos)
**Tier 2 (pendiente):** quant signal dashboard, z-score table, expected value table por escenario
**Tier 3 (implementados Sprint 48f):** Traffic-light conviction grid, pull quote CIO, sparkline SVG helper
**Tier 3 (implementado Sprint 48g):** Annotated charts — 7 market events como líneas verticales en todos los time-series charts (>24 meses). `ChartGenerator.annotate_events()` + `MARKET_EVENTS` list. Integrado en RF yield curve + Macro multi-panel.

## Recent Changes (2026-04-08)
### Sprint 47: Report Quality — Tier 1 Fixes
1. `_esc_narrative()` in 3 renderers — preserves HTML tags in council narratives (fixes `&lt;strong&gt;` rendering as text)
2. Empty "Aciertos/Errores" section hidden when no data (was showing empty `<ul>`)
3. "Key Takeaways" → "Puntos Clave" (Spanish consistency)
4. RF risk probabilities now MANDATORY — prompt changed from "NO inventes" to "OBLIGATORIO: estima rango"

### Ciclo 9: Herramienta Cuantitativa TAA (Sprint 42)
1. New module: `taa_data_collector.py` — runs quantitative TAA model (MOM_MACRO: momentum 12-1 + macro signals + stress circuit breaker) and packages results for council
2. TAA data injected into all 5 panel agents + CIO via `taa_context` in agent_data (formatted text blocks per agent)
3. New section "11. Herramienta Cuantitativa — Señales TAA" in Asset Allocation report: stress gauge, regime badge, tilts chart, track record table, leading indicators, concordance table
4. Files: `taa_report_section.py` (HTML renderer), `taa_data_collector.py` (data collection)
5. Modified: `run_monthly.py` (Phase 1 + Phase 3 injection), `council_data_collector.py` (_taa_data attr + agent distribution), `ai_council_runner.py` (panel + CIO prompt injection), `asset_allocation_renderer.py` (_render_quant_tool method), `templates/asset_allocation_professional.html` (section 11)
6. All 5 panel prompts + CIO prompt updated with `## HERRAMIENTA CUANTITATIVA TAA` section explaining it's an additional input, not a directive
7. TAA project lives at `greybark-asset-allocation/` (sibling of `Wealth/`). Model: 24 ETFs, 16 FRED series, IR 0.40, 168 months backtest. Runs in ~30s using cached data.
8. Bug fix: `taa_data_collector.py` now loads data once (was 4x). NEWORDER series correctly displayed as $B with YoY change (was showing raw $M as if PMI). Added `save()` method for cache/audit (outputs `taa_data_{date}.json`).
9. Analyst calls: `analyst_calls_reader.py` reads analyst recommendations from `greybark-intelligence/data/` (Telegram + Substack). 22 calls/week with BUY/SELL direction, asset, thesis, conviction. Distributed to agents by asset_class, CIO gets full summary.
10. TAA data injection: `run_monthly.py` now passes `self.data['taa']` to AA renderer via `aa_data['taa']`
11. RV Chile rationale: 21 stocks now have sector-specific rationale (was 5 ADRs only)
12. ECB GDP: Added Germany, France, Eurozone GDP QoQ from ECB/Eurostat MNA dataset
13. Council deliberation: "0/25 Módulos OK" fixed — renderer now correctly counts string list as all-OK
9. Bug fix: `feature_engineering.py` NEWORDER changed from absolute level to `pct_change(12)` (YoY). `optimizer.py` stress score NEWORDER component uses YoY decline >5% threshold (was comparing $M value vs 50).

### Ciclo 8: AI Council Quality (Sprint 41)
1. Contrarian now receives verified data inventory (same as CIO) for fact-checking panelist claims
2. Contrarian prompt reinforces 6 obligatory sections: SUPUESTO MÁS PELIGROSO, RAÍZ DEL ÁRBOL, ESCENARIOS NO CONSIDERADOS, CÓMO PUEDE FALLAR, AJUSTES RECOMENDADOS, VEREDICTO
3. Token budgets: CIO 6K→8K (room for CAUSAL_TREE), Contrarian 6K→7K (room for structured sections)
4. Agent data enrichment: RV gets +6 modules (inflation, fiscal, risk, leading, BEA, china), Riesgo +5 (rates, inflation, macro, breadth, term_premia), RF +2 (macro, leading)
5. Bloomberg percentiles: `get_percentile(campo, years=5)` + `p5Y: XX` in every formatted line
6. Crisis reference: `crisis_reference.py` with 8 verified episodes (GFC/COVID/Taper/SVB/Vol/2022/Euro/Q4-2018) injected into all agent prompts
7. Chile equity: 5 ADRs → 21 stocks (+ 16 Santiago Exchange .SN tickers with sector labels)
5. Chile data dedup: Module 4 derives from Module 5 (chile_extended.macro) — eliminates ~5 duplicate BCCh API calls
6. Footer legend: "— = dato no disponible" added to all 4 report templates

### Ciclo 7: Security + Pipeline + Coherence + CAUSAL_TREE + Data Fix (Sprints 26-40)
1. Security: API key removed from source → env var, exec() → importlib, shell=True → webbrowser.open, JWT warning
2. Pipeline: dynamic report_type for council, exit code includes self.errors, IPC Chile param fix
3. Data robustness: `_clean_float()` NaN/inf guard, `.dropna()` aligned, timeouts 30s (FRED/BCCh/yfinance)
4. AI quality: anti-hallucination threshold 5bp→2bp, block cache duplicate warning
5. HTML escaping: `_esc()` helper in 4 renderers (33+ instances), `_md_to_html` in RF also escapes, rate-limit retry with backoff
6. Coherence: panel conflict warnings now passed to Refinador via `council_input['coherence_warnings']`
7. CAUSAL_TREE: CIO generates JSON causal tree (root→L1→L2→5 outcomes), Contrarian challenges root, Refinador preserves, `council_parser.get_causal_tree()` extracts, `causal_tree_renderer.py` generates SVG visualization in AA section 10
8. AA data fix: `council_input` quantitative data now persisted via `runner._last_council_input` → `self.data['macro_quant']` + saved as `council_input_*.json` for cache. Fixes ~55 empty cells (GDP, CPI, TPM, copper, etc.)
9. Report quality checker: `report_quality_checker.py` scans post-render HTML for empty cells ("—"), residual N/D, raw types. Integrated in all 4 renderers after `clean_nd()`
10. Deep merge fix: AA data merge now does deep merge (RF + macro_quant dicts fused at sub-key level). Fixes CPI core and other data lost in key collisions. World GDP fallback from region average.

### Previous (2026-03-30)
1. Renderer hardening: 28 crash points → 0 (all `dict['key']` → `.get('key', default)`)
2. Narrative engine dotenv: `load_dotenv()` added to `narrative_engine.py` — fixes empty narratives
3. Council deliberation report: new `council_deliberation_renderer.py` — "Acta del Comité"
4. Helper methods null-safe: `_get_view_class`, `_get_valuation_class`, `_get_vs_class`, `_get_trend_class`
5. Macro CPI components crash: `_sf()` helper for Series-safe formatting in `_build_cpi_components()`
6. LatAm inflation table: fetch BCCh IPC_INTL series (Brasil/Mexico/Colombia) — was hardcoded N/D
7. China property table: search AKShare quant_data first, fallback to ChartDataProvider
8. Chile IPC SAE: add BCCh series `F074.IPCSAE.V12.Z.2018.C.M` → 4.1% a/a (was hardcoded N/D)

### Previous (2026-03-27)
1. RF report KeyError `'impacto'` -> `.get()` with alias fallbacks (severidad/mitigacion)
2. Macro crash `Series.__format__` -> `_build_latam_table()` extracts `.iloc[-1]` from pd.Series
3. Briefing numpy/dict raw display -> unwrap dict values + convert np.float64 to float
4. Reports not copied on partial failure -> `_copy_reports_to_client()` always runs
5. Per-client directives -> each client reads/writes own `directives.txt`
6. Docker volumes: `/app/consejo_ia/output` + `/app/consejo_ia/input` now persistent
7. Multi-client onboarding: MBI, Vantrust, BVC with `product_ai_council=True`

### Previous (2026-03-25)
1. risk_matrix chart crash: `'str' object has no .get()` -> extract `riesgos` list from nested dict
2. YTD timezone mismatch: yfinance tz-aware index vs naive string -> `pd.Timestamp.tz_localize()`
3. CPI method mismatch: `get_usa_cpi_components()` -> `get_usa_cpi_breakdown()` (3 callers)
4. LatAm method mismatch: `get_latam_macro()` -> `get_latam_rates()`
5. Intelligence digest: `format_for_council()` called as classmethod -> instantiate first
6. ChartDataProvider silent failure -> now logs actual exception
7. Dashboard robustness: thread-safe _jobs, fallback context for missing client data
8. run_monthly.py: `--client` flag for report sync to Layout/output/{client_id}/{date}/

### Previous (2026-03-17)
1. VaR=0.0% silent failure -> None-safe with sanity check
2. OW/UW badge inconsistency -> structured parser before text mining
3. EPS growth >500% outlier -> capped to None
4. Narrative truncation -> max_tokens raised + truncation logging
5. Coherence validator -> expanded from 6 to 13 metrics
6. Calendar past dates -> filtered
7. Chart/text spot desync -> injected_spot mechanism

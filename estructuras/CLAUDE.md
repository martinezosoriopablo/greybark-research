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

## Environment Requirements
- Python 3.10+
- `ANTHROPIC_API_KEY` — Claude API (for council + narratives)
- `FRED_API_KEY` — FRED data
- `ALPHAVANTAGE_API_KEY` — Earnings data
- `BCCH_USER` + `BCCH_PASSWORD` — Banco Central de Chile API
- Dependencies: anthropic, pandas, matplotlib, yfinance, pmdarima, statsmodels, requests, jinja2

## Architecture Notes

### AI Council (3-Layer)
- **Layer 1 (Panel)**: 5 specialist agents analyze in parallel, each sees filtered data by expertise
- **Layer 2 (Synthesis)**: CIO synthesizes + generates CAUSAL_TREE -> Contrarian challenges (incl. tree root) -> Refinador produces final output (preserves CAUSAL_TREE JSON)
- **Layer 3 (Output)**: Structured blocks (EQUITY_VIEWS, FI_POSITIONING, CAUSAL_TREE, etc.) parsed by `council_parser.py`
- **Coherence**: Panel conflicts detected by `_check_panel_coherence()` and passed to Refinador via `council_input['coherence_warnings']`

### Content Generation
- Each report has a `*_content_generator.py` that combines council output + real API data
- `narrative_engine.py` calls Claude for narrative sections with anti-fabrication filters
- Fallback pattern: council data -> API data -> hardcoded defaults (never empty cells)

### Key Patterns
- All modules fail silently: `{'error': str(e)}` — downstream checks before using data
- `_has_data()` / `_has_council()` guards everywhere
- Spanish text with proper accents (accented dict keys: `inflaci{o'}n`, `pol{i'}tica_monetaria`)
- VaR/CVaR values are None-safe (not 0.0) with sanity range [0.01%, 15.0%]
- EPS growth capped at +/-500% (low-base outlier protection)
- Earnings calendar filters past dates automatically
- Coherence validator checks 13 shared metrics across all 4 reports

### Report Design System
- All 4 reports share: header (split layout), orange accent, Segoe UI body, black tables
- Badges: OW=green `#276749`, N=warm-neutral `#744210`, UW=red `#c53030`
- Print-ready: `page-break-inside: avoid`

## Common Tasks

### Adding a new data source
1. Add API call in the relevant `*_data_collector.py`
2. Add series codes to `greybark/config.py` if BCCh/FRED
3. Wire into content generator with `_has_data()` guard
4. Add to coherence validator if cross-report metric

### Fixing empty cells in reports
1. Check which `{{placeholder}}` is empty in the template
2. Trace to the content generator method that produces it
3. Usually: API returned None, need fallback or new data source

### Modifying council behavior
- Agent prompts: `prompts/ias_*.txt`
- Panel composition: `ai_council_runner.py`
- Output structure: `council_parser.py` (block extraction patterns)

## Recent Changes (2026-03-31)
### Ciclo 7: Security + Pipeline + Coherence + CAUSAL_TREE (Sprints 26-33)
1. Security: API key removed from source → env var, exec() → importlib, shell=True → webbrowser.open, JWT warning
2. Pipeline: dynamic report_type for council, exit code includes self.errors, IPC Chile param fix
3. Data robustness: `_clean_float()` NaN/inf guard, `.dropna()` aligned, timeouts 30s (FRED/BCCh/yfinance)
4. AI quality: anti-hallucination threshold 5bp→2bp, block cache duplicate warning
5. HTML escaping: `_esc()` helper in 3 renderers (33 instances), rate-limit retry with backoff
6. Coherence: panel conflict warnings now passed to Refinador via `council_input['coherence_warnings']`
7. CAUSAL_TREE: CIO generates JSON causal tree (root→L1→L2→5 outcomes), Contrarian challenges root, Refinador preserves, `council_parser.get_causal_tree()` extracts, AA renderer visualizes as HTML section 10

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

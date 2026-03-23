# Greybark Research — Registro de Mejoras Continuas

> Este archivo documenta cada ciclo de auditoría → fix → validación del pipeline.
> Ordenado de más reciente a más antiguo.

---

## Ciclo 5 — 2026-03-19: Auditoría Completa 4 Reportes

**Trigger:** Revisión manual post-pipeline detectó reportes con datos incorrectos.

### Auditoría (4 reportes en paralelo)

| Reporte | Críticos | Altos | Medios | Total |
|---------|----------|-------|--------|-------|
| Macro | 7 | 7 | 9 | 23 |
| RV | 5 | 3 | 5 | 13 |
| RF | 4 | 5 | 6 | 15 |
| AA | 3 | 3 | 4 | 10 |
| **Total** | **19** | **18** | **24** | **61** |

### Fixes Aplicados (commit `5210d3e`)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 1 | FRED OAS spreads en pct points (0.77) mostrados como "1bp" | `greybark/analytics/credit/credit_spreads.py` | ×100 en `_fetch_spread_series()` — arregla RV+RF+AA |
| 2 | Dividend yields ×100 sobre valores ya en % (Stoxx 3.08→308%) | `equity_data_collector.py:175` | Solo ×100 si valor < 1 |
| 3 | TPM dict `{'current': 4.5}` leakeado como string en HTML | `asset_allocation_content_generator.py:_q()` | Unwrap key 'current' además de 'value' |
| 4 | `SELIC None%` — None no manejado | `asset_allocation_content_generator.py:602` | Guard: format con None check → "N/D" |
| 5 | IMACEC "expansión de -0.5%" — hardcoded positivo | `macro_content_generator.py:1728` | Dinámico según signo: expansión/contracción |
| 6 | Council markdown header leakeado en commodity table | `macro_content_generator.py:_commodity_outlook()` | Strip `#` headers y `**bold**` antes de text-mining |
| 7 | Calendario incluye fechas pasadas | `macro_content_generator.py:2160` | Prompt pide solo eventos futuros |

### Fixes Adicionales (commit `72a3fa0`)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 8 | RV stance NEUTRAL cuando council dice UW | `rv_content_generator.py` | Agregado 'subponder'/'UW'/'OW' al extractor de stance |
| 9 | S&P/IPSA P/E swap en Key Calls | `rv_content_generator.py` | Pass verified_data a key_calls → anti-fabricación corrige |
| 10 | Chile IPC YoY "---" (macro chile module falla) | `rf_data_collector.py` + `aa_content_gen` | IPC YoY calculado en chile_rates + fallback path |
| 11 | EM country drivers copy-paste | `rf_content_generator.py` | Per-country drivers con yields reales + contexto local |
| 12 | USD/CLP dual targets (820 vs 880) | `asset_allocation_content_generator.py` | Target programático pasado como contexto binding a LLM |

### Sprint 1 Fixes (5 P2 cerrados)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 13 | HY B rating commentary igual a BB | `rf_content_generator.py:1645` | Fallback diferenciado: "selectividad por emisor" |
| 14 | Señal temprana duplica horizonte en risk cards | `macro_content_generator.py:2236` | Lee `early_signal`/`monitoring` en vez de `horizon` |
| 15 | Risk card horizonte y señal temprana mezclados | `macro_report_renderer.py:565` | Campos separados con labels |
| 16 | EV/EBITDA columna vacía en RV | `rv_report_renderer.py:211` + template | Columna oculta si todos los valores son N/D |
| 17 | Missing accents en 4 templates HTML | 4 templates | ~50 correcciones: Comité, Crédito, Región, Recomendación, etc. |

### Revisión Visual Macro (2026-03-20)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 18 | US Fiscal section triple N/D | `chart_data_provider.py` + `macro_content_generator.py` | Nuevo `get_usa_fiscal()` con 3 FRED series (deficit -5.8%, deuda 122.5%, intereses 3.2%) |
| 19 | China Trade chart datos cortados (190 pts sin trim) | `chart_generator.py:1764` | Trim a 120 meses consistente con otros charts |

### Sprint 2 — Fixes Sistémicos (2026-03-21)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 20 | `fed_rate` regex matchea "Fed" solo → false positive en OAS/inflación | `narrative_engine.py:170` | Regex requiere "Funds"/"rate"/"tasa fed" explícito |
| 21 | Panel agents truncados (max_tokens=4000 insuficiente) | `ai_council_runner.py:54` | MAX_TOKENS 4000→6000 para panelistas |
| 22 | Oil $100 fabricado sin corrección (sin pattern WTI/Brent) | `narrative_engine.py` _LABEL_PATTERNS | Agregado oil/WTI/Brent/petróleo + KEY_SOURCE_MAP + verified builders |
| 23 | Badge CSS: OW/UW solo inglés, council output en español | `rf_report_renderer.py`, `rv_report_renderer.py`, `asset_allocation_renderer.py` | `_get_view_class()` acepta Sobreponderar/Subponderar + `_sanitize_css_class` mapea español |

### Sprint 3 — Forecast Engine + Commodity Data (2026-03-22)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 24 | BCCh commodity data 3-7 semanas stale (oil $70 vs real $106) | `chart_data_provider.py` | `_append_spot_if_stale()` agrega yfinance spot si BCCh >35 días |
| 25 | S&P 500 retorno esperado +21.8% (solo 2/5 modelos) | `forecast_engine.py` | PE keys forward_pe→pe_forward fallback + derive from trailing |
| 26 | Consensus model usa 50DMA en vez de precio actual → +79.5% | `forecast_engine.py` | `_get_etf_price()` via yfinance + sanity cap ±30% |
| 27 | Regime siempre "UNKNOWN" (key mismatch collector→classifier) | `council_data_collector.py:78` | `regime.get('regime')` → `regime.get('classification')` |
| 28 | EuroStoxx ticker FEZ no matchea equity_data EFA | `forecast_engine.py:65` | EQUITY_UNIVERSE eurostoxx ticker FEZ→EFA |

**Resultado:** S&P 500 ahora +2.4% con 5/5 modelos (era +21.8% con 2/5)

### Sprint 4 — Revisión Visual RV (2026-03-22)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 29 | Factor Performance "sin scores" (AV falla para ETFs) | `rv_chart_generator.py` | `_compute_yf_factor_scores()` fallback via yfinance (momentum, value, quality, growth) |
| 30 | 24 acentos faltantes en glosario RV | `templates/rv_report_professional.html` | sobreponderación, índice, relación, acción, etc. |
| 31 | Título "Analisis Sectorial" sin acento | `templates/rv_report_professional.html` | → "Análisis Sectorial" |
| 32 | "Que cambiaria:" sin acentos ni signos | `rv_report_renderer.py:358` | → "¿Qué cambiaría?" |

**Resultado:** RV ahora 12/12 charts, 0 placeholders, glosario correcto

### Bugs Pendientes

| Prioridad | Bug | Impacto |
|-----------|-----|---------|
| P1 | CPI subcomponents vacío (sin fuente FRED simple) | Macro chart vacío |
| P1 | Raw markdown leak en RF HTML (`**bold**`, `## headers`) | Formato roto |
| P1 | Tabla de escenarios vacía en AA | Sección crítica sin contenido |
| P2 | Acentos faltantes en contenido dinámico LLM (no template) | Cosmético |

### Validación — Pipeline 2026-03-22 (post Sprint 4 RV visual)
- [x] Forecast engine: 5/5 modelos S&P 500 OK (+2.4%, era +21.8%)
- [x] Regime: MODERATE_GROWTH (era UNKNOWN)
- [x] Europa ticker EFA match equity_data (era FEZ mismatch)
- [x] Consensus model: yfinance price + ±30% cap (era 50DMA → +79.5%)
- [x] Commodity data: yfinance spot enrichment para BCCh stale >35d
- [x] RV: **12/12 charts**, 0 placeholders, retornos S&P +2.4%, Europa +6.9%, Chile +9.8%
- [x] RV glosario: 24 acentos corregidos + título sección + "¿Qué cambiaría?"
- [x] AA report regenerado con forecasts corregidos
- [x] Macro: 24 charts (2.8MB)
- [x] Pipeline: 4/4 reportes OK (34.9 min)
- [ ] Revisión visual pendiente: RF, AA

### Validación — Pipeline 2026-03-21 (post Sprint 2 sistémicos)
- [x] Re-run pipeline completo con datos frescos — **4/4 reportes OK** (43.6 min)
- [x] Anti-fabricación: S&P P/E 500→25.73, UST 10Y 4.00→4.25, IG spread 110→90bp, TPM 4.0→4.5%
- [x] Consistency fixes: VIX→26.8, Focus GLD NEUTRAL→N, RF curva OW→N
- [x] Panel agents: 4435-8636 chars (antes ~3500-4000) — **max_tokens=6000 OK**
- [x] Coherence check: 1 conflicto (TPM macro=2.2 vs rf=4.5)
- [x] Macro: 28 charts, 19/25 módulos OK
- [x] RV: 11/12 charts, 11/11 módulos OK
- [x] RF: 8/8 charts, 11/12 módulos OK
- [x] AA: reporte completo con narrativas
- [x] Pre-council: 44 charts, 0 fallidos, 4/4 reportes validados
- [ ] Revisión visual pendiente: 4 reportes

### Validación — Pipeline 2026-03-20 (post Sprint 1)
- [x] Re-run pipeline completo con datos frescos — **4/4 reportes OK** (41 min)
- [x] Verificar spreads muestran ~77bp IG / ~350bp HY — **IG=91bps, HY=320bps** (correcto)
- [x] Credit spreads: AAA 41bp, AA 57bp, A 76bp, BBB 113bp, BB 200bp, B 351bp, CCC 964bp
- [x] Dividend yields < 10% — SPY 1.3%, EFA 3.1%, EEM 2.5% (correcto)
- [x] Macro: 28 charts generados, 19/25 módulos datos OK
- [x] RV: 11/12 charts con datos reales, 11/11 módulos equity OK
- [x] RF: 8/8 charts con datos reales, 11/12 módulos RF OK
- [x] AA: reporte generado con narrativas + tablas completas
- [x] Anti-fabricación: 10 correcciones aplicadas (fed_rate, hy_spread, tpm, oil, etc.)
- [x] Pre-council: 44 charts, 0 fallidos, 4/4 reportes validados
- [x] US Fiscal: datos reales FRED (deficit -5.8%, deuda 122.5%, intereses 3.2% GDP)
- [x] China Trade: trim 120m aplicado
- [x] PMI Global: datos reales Bloomberg (USA 52.4, Euro 50.8, China 49.0)
- [x] CPI Contribution: datos reales confirmados
- [ ] Revisión visual pendiente: RV, RF, AA

---

## Ciclo 4 — 2026-03-18: CLP/USD + TPM + max_tokens

**Trigger:** Usuario identificó contradicciones en informe AA Chile.

### Fixes Aplicados

| # | Bug | Commit |
|---|-----|--------|
| 1 | CLP/USD dirección contradictoria (alcista Chile con target > spot) | `d037cd5` |
| 2 | TPM tendencia computada DESPUÉS de narrativa → inconsistencia | `f4b3dc9` |
| 3 | Textos truncados por max_tokens bajo | `472835d` |
| 4 | AA sin datos IPC (key 'quant' → 'macro_quant') | `7d62015` |
| 5 | .env no cargado en run_monthly.py | `472835d` |
| 6 | API key revocada (expuesta en GitHub público) | Manual — nueva key |

### Lecciones
- **CLP/USD convención**: SUBE = peso deprecia = MALO para Chile. Directiva inyectada en 4 prompts.
- **max_tokens**: Panel 2500→4000, Refinador 2500→12000, narrativas 100-250→200-500.
- **NUNCA** commitear .env o API keys a repo público.

---

## Ciclo 3 — 2026-03-17: Coherence + VaR + Earnings

**Trigger:** Auditoría de calidad post-primera generación completa.

### Fixes Aplicados

| # | Bug | Descripción |
|---|-----|-------------|
| 1 | VaR=0.0% silent failure | None-safe con sanity check [0.01%, 15%] |
| 2 | OW/UW badge inconsistency | Structured parser antes de text mining |
| 3 | EPS growth >500% outlier | Capped a None |
| 4 | Narrativa truncada | max_tokens raised + truncation logging |
| 5 | Coherence validator | Expandido de 6 a 13 métricas |
| 6 | Calendar past dates | Filtro automático |
| 7 | Chart/text spot desync | injected_spot mechanism |

---

## Ciclo 2 — 2026-03-12: Greybark Library Migration

**Trigger:** Necesidad de tener todas las dependencias en un solo repo.

### Cambios
- Migración de `02_greybark_library/` a `consejo_ia/greybark/`
- Pre-council package: 48+ charts con datos reales
- Pipeline mejorado: 5 fases (collect → preflight → council → reports → summary)
- Módulos nuevos: AKShare (China NBS), ECB Data Portal, MoF Japan

---

## Ciclo 1 — 2026-02-07 a 2026-02-12: Setup Inicial

### Hitos
- 2026-02-07: Preflight validator creado
- 2026-02-08: BCCh + FRED integration para charts reales
- 2026-02-09: Council parser + macro report con narrativas
- 2026-02-10: AA report + RF report creados
- 2026-02-11: Forecast engine (ARIMA/VAR/Taylor/Phillips) + IMF WEO
- 2026-02-12: RV report + equity data collector completo

---

## Cómo Usar Este Log

1. **Antes de correr el pipeline**: revisar "Bugs Pendientes" del último ciclo
2. **Después de correr**: auditar reportes contra los checks del último ciclo
3. **Al encontrar bugs nuevos**: agregar al log con prioridad y archivo afectado
4. **Al fixear**: mover de "Pendientes" a "Fixes Aplicados" con commit hash
5. **Meta**: llegar a 0 bugs P0 y P1 antes de entregar reportes a clientes

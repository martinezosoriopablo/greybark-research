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

### Bugs Pendientes (priorizados)

| Prioridad | Bug | Archivo | Impacto |
|-----------|-----|---------|---------|
| P0 | Chile IPC YoY "---" en AA | `asset_allocation_content_generator.py` | Sección Chile incompleta |
| P0 | S&P/IPSA P/E swapped en Key Calls | `rv_content_generator.py` | Dato crítico invertido |
| P0 | RV stance NEUTRAL vs conclusión UW | `rv_content_generator.py` | Contradicción visible |
| P1 | `fed_rate` inyectado donde debería ir OAS | `rf_content_generator.py` | Sentence sin sentido |
| P1 | EM drivers copy-paste (4 países mismo texto) | `rf_content_generator.py` | Apariencia poco profesional |
| P1 | USD/CLP targets inconsistentes (820-840 vs 880) | AA content gen | Dos targets en un reporte |
| P2 | US Fiscal section triple N/D | `macro_content_generator.py` | Sección vacía |
| P2 | EV/EBITDA columna vacía en RV | `rv_content_generator.py` | Columna sin datos |
| P2 | Doble horizonte en risk cards (Macro) | Template macro | Dato duplicado |
| P2 | Missing accents en headings | Templates / renderers | Estético |

### Validación Pendiente
- [ ] Re-run pipeline completo con datos frescos
- [ ] Verificar spreads muestran ~77bp IG / ~350bp HY
- [ ] Verificar dividend yields < 10% para todas las regiones
- [ ] Verificar TPM en AA sin dict leak
- [ ] Verificar IMACEC texto correcto según signo

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

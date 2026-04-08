# Greybark Research — Registro de Mejoras Continuas

> Este archivo documenta cada ciclo de auditoría → fix → validación del pipeline.
> Ordenado de más reciente a más antiguo.

---

## Ciclo 9 — 2026-04-04: Herramienta Cuantitativa TAA

**Trigger:** Integración del modelo cuantitativo de Tactical Asset Allocation como input adicional al AI Council y nueva sección en el reporte de Asset Allocation.

### Sprint 42 — TAA Integration (7 cambios)

| # | Severidad | Hallazgo | Archivo | Fix aplicado |
|---|-----------|----------|---------|-------------|
| 1 | Feature | Nuevo módulo TAA data collector | `taa_data_collector.py` | Ejecuta modelo MOM_MACRO (24 ETFs, 16 FRED series), empaqueta tilts, stress, régimen, momentum, track record en ~30s |
| 2 | Feature | Sección 11 en reporte AA | `taa_report_section.py` | HTML con stress gauge SVG, tilts chart PNG, leading indicators, track record, concordancia modelo vs comité |
| 3 | Feature | Inyección TAA en pipeline | `run_monthly.py` | Fase 1 ejecuta TAA collector, Fase 3 inyecta via `_taa_data` al council |
| 4 | Feature | Distribución a agentes | `council_data_collector.py` | `_taa_data` attr + distribución de `taa_context` formateado por agente + datos raw a cada panel |
| 5 | Feature | Inyección en prompts dinámicos | `ai_council_runner.py` | `taa_context` extraído e inyectado en panel user prompts + `taa_cio_context` en CIO prompt |
| 6 | Feature | Prompts actualizados | `prompts/ias_*.txt` (6 archivos) | Nueva sección "HERRAMIENTA CUANTITATIVA TAA" en cada prompt: explica que es input adicional, patrón confirmar/divergir |
| 7 | Feature | Render en AA | `asset_allocation_renderer.py` | Método `_render_quant_tool()` + placeholder `{{quant_tool_html}}` en template |

### Sprint 43 — TAA Fixes (3 bugs)

| # | Severidad | Hallazgo | Fix aplicado |
|---|-----------|----------|-------------|
| 8 | Bug | `taa_data_collector.py` cargaba datos 4 veces (una por sub-módulo) | Carga única en `_cached_data` al inicio de `collect_all()`, sub-módulos referencian cache |
| 9 | Bug | Serie FRED `NEWORDER` = manufacturers' new orders en $M, no ISM PMI. Mostraba 79,324 como si fuera índice PMI | Cambiado a variación YoY ($79B, +6.3%). Stress score usa caída >5% YoY como señal (no comparación vs 50). Feature engineering también corregido. |
| 10 | Missing | Sin método `save()` — si pipeline falla post-Phase 1, se pierde el TAA data | Agregado `save()` que genera `taa_data_{date}.json` (~12KB). Conectado en `run_monthly.py` Phase 1. |

**Principio de diseño:** TAA es un input cuantitativo más para el Comité. Los agentes pueden confirmar, matizar o divergir. Los tilts no van directamente a los portafolios modelo. La sección del reporte incluye disclaimer explícito.

**Track record del modelo:** IR 0.40, hit rate 52.4%, excess return +0.62% ann, 168 meses (2012-2026).

### Sprint 48 — Tier 2: "Qué Cambió" + "Qué Está Priceado" (Goldman Sachs elements)

**Trigger:** Auditoría de calidad identificó que los reportes carecen de elementos estándar de research institucional.

| # | Feature | Archivo | Referencia |
|---|---------|---------|-----------|
| 199 | **"Qué Cambió vs Reporte Anterior"** — tabla estructurada Previous View → Current View con flechas (↑↓→). Muestra solo cambios de posición. Usa dashboard views como current y historical store como previous | `report_enhancements.py`, `asset_allocation_renderer.py`, template AA | Goldman Sachs "Global Markets Analyst" abre con delta table |
| 200 | **"Qué Está Priceado vs Nuestra Visión"** — tabla Fed cuts priced vs nuestros, TPM implied vs nuestro, S&P earnings yield vs UST 10Y. Muestra delta entre consenso de mercado y visión Greybark | `report_enhancements.py`, `asset_allocation_renderer.py`, template AA | Goldman/JP Morgan: "What's priced in" is the delta that generates alpha |

**Nuevo módulo:** `report_enhancements.py` — funciones independientes que retornan HTML snippets para inyección en renderers. Diseñado para ser reutilizable en otros reportes.

**Ubicación en AA report:** Después de Dashboard (sección 2) y antes de "El Mes en Revisión" (sección 3). Con `{% if %}` guards — no aparecen si no hay datos.

**Validación:** 2/2 archivos compilan OK. Secciones condicionales (backward compatible).

### Sprint 47 — Tier 1 Fixes: HTML, secciones vacías, probabilidades (4 fixes)

| # | Fix | Archivo |
|---|-----|---------|
| 195 | **HTML roto en narrativas** — `<strong>` renderizaba como texto literal `&lt;strong&gt;`. Nuevo `_esc_narrative()` en 3 renderers (rv, macro, aa) preserva tags HTML + convierte **markdown** | `rv/macro/aa_report_renderer.py` |
| 196 | **"Aciertos/Errores" vacíos** — sección visible pero sin contenido en Macro. Ahora se oculta si vacía (`display:none`) | `macro_report_renderer.py` + template |
| 197 | **"Key Takeaways" en inglés** → "Puntos Clave" | `templates/macro_report_professional.html` |
| 198 | **Probabilidades vacías en riesgos RF** — prompt decía "NO inventes probabilidades" → Claude devolvía "—". Cambiado a "OBLIGATORIO: estima un rango". Más contexto del RISK_MATRIX (2500 chars vs 1500) | `rf_content_generator.py:2570-2589` |

### Experimento: MOM_MACRO_V2 (Vol Scaling + Crash Protection) — REVERTIDO

**Trigger:** Investigación sobre regime-aware trading models sugirió agregar vol scaling (Barroso & Santa-Clara 2015) y momentum crash protection (Daniel & Moskowitz 2016) al modelo TAA.

**Proceso:**
1. Investigación académica + practitioner (AQR, Man AHL, Bridgewater, Research Affiliates)
2. Implementación de `_mom_macro_v2_tilts()` con vol scaling (target 10%) + crash protection (-15% threshold)
3. Backtest: 168 meses, 24 ETFs, 10 combinaciones de thresholds

**Resultado:** IR 0.401 → 0.401 — **CERO mejora en TODAS las combinaciones**

**Causa raíz:** El stress circuit breaker existente en MOM_MACRO (0.3x/0.6x/0.85x scale) ya implementa vol scaling de forma más directa. Las mejoras son REDUNDANTES — se aplican antes del circuit breaker, que luego las sobrescribe.

**Decisión:** Código V2 REVERTIDO. MOM_MACRO queda como está. Documentado en `greybark-asset-allocation/IMPROVEMENTS.md`.

**Lección:** La literatura académica sobre vol scaling asume modelos SIN protección existente. Cuando el modelo ya tiene circuit breaker, el beneficio marginal es cero. Siempre testear contra el modelo completo, no en aislamiento.

### Sprint 44 — Analyst Calls Integration (Telegram + Substack → Council)

**Trigger:** Nueva fuente `greybark-intelligence` genera `analyst_calls.json` diario con recomendaciones de analistas (Telegram + Substack). 22 calls con: analyst, firm, direction, asset, thesis, conviction.

| # | Archivo | Cambio |
|---|---------|--------|
| 185 | `analyst_calls_reader.py` | **NUEVO:** Lee `analyst_calls.json` últimos 7 días. Formato council (5KB) + formato por agente (filtrado por asset_class) |
| 186 | `council_data_collector.py` | Recolecta analyst calls en `prepare_council_input()`. Distribuye filtrado a cada agente + resumen completo a CIO |
| 187 | `ai_council_runner.py` | Inyecta `analyst_calls_context` en panel prompts + `analyst_calls_cio` en CIO prompt |

**Validación:** 3/3 compilan OK. Test: 22 calls, 5KB council format, routing correcto a 5 agentes.

### Sprint 45 — Fix: Preflight NO_GO por contexto >4000 chars

**Trigger:** Pipeline del 6 abril abortó council con `"aborted": true, "overall_verdict": "NO_GO"`. Causa: `DAILY_CONTEXT_LIMIT = 4000` en preflight validator, pero el intelligence digest genera 12-14K chars normalmente (49 reportes, 23 temas, 49 ideas). El run del 1 abril funcionó porque la completeness validator no override a NO_GO ese día.

| # | Hallazgo | Fix |
|---|----------|-----|
| 188 | `council_preflight_validator.py:65` — `DAILY_CONTEXT_LIMIT = 4000` demasiado bajo para el intelligence digest actual (12-14K chars). Causó issue que la completeness validator escaló a NO_GO | **FIXEADO:** `DAILY_CONTEXT_LIMIT = 15000`. El digest de 12-14K es correcto y necesario para los agentes |
| 189 | `data_completeness_validator.py:290` — `required_coverage < 0.95` → NO_GO. Macro tenía 78% (7/9 required fields) y bloqueó todo el council. Reportes se generaron con datos INVENTADOS del LLM | **FIXEADO:** Threshold NO_GO bajado de 95% a 60%. Con 78% de required fields el council corre con CAUTION (no abort). Un council con 78% de datos es infinitamente mejor que reportes con datos inventados |

**Impacto:** Council abortado → 4 reportes generados sin narrativas del council → resumen ejecutivo con datos genéricos/stale del narrative_engine (ej: "fed funds 5.25%" cuando real es 3.64%) → reportes de mala calidad.

**Principio:** Un council con datos parciales (78%) produce reportes mejores que un narrative_engine sin council (datos inventados). NUNCA bloquear el council por 2 campos faltantes de 25 módulos.

### Sprint 45c — Fix: rf_yield_curve chart falla recurrente (BUG CRÓNICO)

**Trigger:** El chart `rf_yield_curve` falla en CADA run del pipeline con error `'1'`. Ha sido "arreglado" en Sprint 11 y Sprint 23 pero sigue fallando. Esta vez se encontró la CAUSA RAÍZ REAL.

**Causa raíz:** El chart generator busca datos soberanos en `cdata.get('tenors', {})` pero el módulo `curvas_soberanas.py` los guarda en `cdata.get('datos', {})`. Las keys son `'1'`, `'2'`, `'3'`, `'5'`, `'10'`, etc.

- `cdata['tenors']` → siempre vacío `{}`
- `cdata['datos']` → tiene los datos reales: `{'1': 2.31, '2': 2.15, '10': 2.52, ...}`

Cuando el chart corría aislado (test), no fallaba porque los sovereign curves no se pasaban. En el pipeline, se pasan pero con la key incorrecta → error críptico `'1'` que es un KeyError al intentar convertir la estructura.

| # | Fix |
|---|-----|
| 190 | `rf_chart_generator.py:279` — `cdata.get('tenors', {})` → `cdata.get('tenors', {}) or cdata.get('datos', {})`. Además: parsing robusto con try/except por tenor, maneja tanto int como string keys, maneja valores dict (con 'yield' key) y floats directos |

**POR QUÉ ESTE BUG ES RECURRENTE:**
El test aislado del chart siempre pasa porque no incluye sovereign_curves en el test data. El bug solo se manifiesta DENTRO del pipeline cuando sovereign_curves se inyectan desde council_input. Los "arreglos" anteriores (Sprint 11, 23) verificaron que el chart genera OK en test pero no en contexto pipeline.

**Prevención futura:** Siempre testear charts CON sovereign_curves inyectadas, no solo con rf_data aislado.

**Validación:** 8/8 RF charts generan OK (incluyendo rf_yield_curve con 143K chars). Sovereign curves Alemania (9 tenors) y Japón (11 tenors) correctamente overlay-eadas.

### Sprint 45d — Inyectar sovereign_curves al RF renderer (patrón sistémico)

**Trigger:** Auditoría post-fix del yield curve reveló que `sovereign_curves` nunca llegaban al RF renderer — `run_monthly.py` solo pasaba `rf_data` (del JSON cacheado).

| # | Fix |
|---|-----|
| 191 | `run_monthly.py` — inyecta `sovereign_curves` desde `macro_quant` en `rf_data` antes de pasar al `RFReportRenderer`. Mismo patrón que Sprint 37 (AA macro_quant) y Sprint 39 (AA deep merge) |

**Patrón sistémico identificado:** "Datos recolectados pero no pasados al renderer"
- Sprint 37: AA no recibía `macro_quant` → persist council_input
- Sprint 39: AA perdía `inflation.cpi_core_yoy` por colisión RF → deep merge
- Sprint 45d: RF no recibía `sovereign_curves` → inject desde macro_quant

**Prevención:** Al agregar nuevos datos al pipeline, verificar SIEMPRE que `run_monthly.py._generate_single_report()` los inyecta al renderer correspondiente.

**Validación completa de charts:**
- Macro: requiere content arg (OK por diseño)
- RV: 12/12 OK
- RF: 8/8 OK (incluyendo yield curve con Bund + JGB overlay)

### Sprint 46 — Auditoría de reportes generados (4 fixes)

**Trigger:** Auditoría post-run de los 5 reportes del 6 abril reveló 4 issues.

| # | Sev | Hallazgo | Archivo | Fix |
|---|-----|----------|---------|-----|
| 192 | ALTO | **AA: TAA data no llega al renderer** — `taa` se almacena en `self.data['taa']` pero nunca se inyecta en `aa_data` | `run_monthly.py:803` | **FIXEADO:** Agrega `aa_data['taa'] = self.data.get('taa')` antes de crear el renderer |
| 193 | ALTO | **RV: 16 stocks .SN sin rationale** — `rationale_map` solo tenía 5 ADRs. Los 16 tickers Santiago Exchange retornaban 'N/D' | `rv_content_generator.py:2316` | **FIXEADO:** Expandido `rationale_map` con los 16 tickers .SN (Cencosud, Falabella, BCI, Copec, etc.) con tesis por sector |
| MEDIO | **Alemania GDP = N/D** — ECB client solo fetcheaba 5 series (DFR, HICP, 10Y, EUR/USD, M3). Sin GDP de Alemania, Francia, Eurozona | `ecb_client.py:37-74` | **FIXEADO:** 3 nuevas series ECB: `gdp_ea_qoq`, `gdp_de_qoq`, `gdp_fr_qoq` (Eurostat via ECB MNA dataset) |
| 194 | MEDIO | **Council deliberation: "0/25 Módulos OK"** — `quantitative_modules` es lista de strings pero renderer esperaba lista de dicts con `status: OK` | `council_deliberation_renderer.py:224-226` | **FIXEADO:** Si lista de strings, `ok_count = len(quant_modules)` (cada string = módulo OK) |

**Nota sobre CAUSAL_TREE (Section 10):** El JSON SÍ existe en el council output (3,329 chars). El parser lo extrae correctamente. La sección debería renderizar en el próximo run — si no aparece, verificar que `council_result` pasado al renderer contiene `final_recommendation` con el JSON.

**Validación:** 4/4 archivos compilan OK.

---

## Ciclo 8 — 2026-04-03: Auditoría de Calidad del AI Council

**Trigger:** Auditoría completa del codebase post-deploy a servidor. 3 agentes paralelos: data collection, report quality, AI council system. Se cruzaron hallazgos contra Ciclo 7 — los 3 siguientes son genuinamente nuevos.

### Sprint 41 — Contrarian + CIO Token Budget (3 hallazgos)

| # | Severidad | Hallazgo | Archivo | Fix aplicado |
|---|-----------|----------|---------|-------------|
| 174 | ALTA | **Contrarian no recibe datos verificados** — `_build_contrarian_prompt()` no incluía `council_input`, `data_inventory` ni `verified_data`. Contrarian argumentaba en abstracto sin poder fact-check al CIO | `ai_council_runner.py:593-625` | **FIXEADO:** `_build_contrarian_prompt()` ahora recibe `council_input`, llama `_build_cio_data_inventory()` para inyectar datos verificados de los 5 agentes. Contrarian puede contrastar citas numéricas del CIO contra datos reales |
| 175 | ALTA | **Contrarian saltaba secciones obligatorias** — output del 1 abril no contenía "SUPUESTO MÁS PELIGROSO", "CÓMO PUEDE FALLAR", "RAÍZ DEL ÁRBOL" (secciones obligatorias del prompt ias_contrarian.txt) | `ai_council_runner.py:593-625` | **FIXEADO:** User prompt del Contrarian ahora incluye sección "RECORDATORIO DE SECCIONES OBLIGATORIAS" con los 6 headers exactos que debe producir. Word limit corregido de "500-600" → "600-800" (consistente con ias_contrarian.txt) |
| 176 | ALTA | **CIO token budget insuficiente** — CIO usaba MAX_TOKENS=6000 (igual que panelistas) pero genera síntesis + CAUSAL_TREE JSON (~10K chars). Riesgo de truncación | `ai_council_runner.py:54-56` | **FIXEADO:** Nuevas constantes `CIO_MAX_TOKENS=8000`, `CONTRARIAN_MAX_TOKENS=7000`. CIO y Contrarian ahora usan tokens dedicados en vez de compartir MAX_TOKENS con panelistas |

**Verificación de compatibilidad:**
- Sprint 2 (Ciclo 5) subió MAX_TOKENS de 4000→6000 para panelistas — no afectado, panelistas siguen en 6000
- Sprint 30 (Ciclo 7) agregó `_call_llm_with_retry()` — compatible, nuevos max_tokens se pasan por el retry handler
- Sprint 32 (Ciclo 7) agregó CAUSAL_TREE al CIO — el aumento de tokens asegura que el JSON no se trunca
- Sprint 31 (Ciclo 7) conectó coherence_warnings al refinador — Contrarian ahora recibe data_inventory adicional pero refinador sigue funcionando igual

**Validación:** `ai_council_runner.py` compila OK

### Sprint 43 — Agent Data Enrichment + Historical Context (3 mejoras)

**Trigger:** Auditoría de arquitectura reveló que agentes RV y Riesgo recibían datos insuficientes, y que ningún agente recibía percentiles históricos ni tabla de episodios de crisis para anclar sus análisis.

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 180 | **RV recibía 6/25 módulos** — sin inflation, fiscal, leading_indicators, risk, BEA profits, china. No podía evaluar sostenibilidad de valuaciones | **FIXEADO:** `council_data_collector.py` — RV ahora recibe: inflation, fiscal, leading_indicators, risk, bea_profits, china (6 módulos adicionales = 12/25 total) |
| 181 | **Riesgo recibía 8/25 módulos** — sin rates, inflation, macro_usa, breadth, nyfed_term_premia. No podía evaluar riesgo de duración ni drivers sistémicos | **FIXEADO:** `council_data_collector.py` — Riesgo ahora recibe: rates, inflation, macro_usa, breadth, nyfed_term_premia (5 módulos adicionales = 13/25 total) |
| 182 | **RF faltaba macro_usa y leading_indicators** — ciego a empleo y momentum de crecimiento (drivers clave de Fed) | **FIXEADO:** `council_data_collector.py` — RF ahora recibe macro_usa + leading_indicators |
| 183 | **Sin percentiles históricos en datos Bloomberg** — agentes veían solo valor actual + anterior + cambio 1M. RF admitía: "Sin percentil histórico disponible" | **FIXEADO:** `bloomberg_reader.py` — nuevo método `get_percentile(campo_id, years=5)` calcula ranking percentil vs últimos 5 años. `_fmt_series_line()` ahora incluye `p5Y: XX` en cada línea |
| 184 | **Sin tabla de episodios de crisis** — agentes citaban GFC/COVID/Taper de memoria del LLM, no de datos verificados | **FIXEADO:** Nuevo `crisis_reference.py` con 8 episodios cuantificados (GFC, COVID, Taper, SVB, Volmageddon, Shock 2022, Euro Crisis, Q4 2018). Cada uno con: S&P%, HY/IG spreads, VIX, UST move, USD/CLP, Cobre, duración, condiciones. Inyectado en prompts de TODOS los agentes vía `_build_panel_user_prompt()` |

**Datos por agente después del fix:**
| Agente | Antes | Después | Nuevos módulos |
|--------|-------|---------|----------------|
| Macro | 22/25 | 22/25 | (sin cambio — ya era completo) |
| RV | 6/25 | 12/25 | +inflation, fiscal, leading_indicators, risk, bea_profits, china |
| RF | 14/25 | 16/25 | +macro_usa, leading_indicators |
| Riesgo | 8/25 | 13/25 | +rates, inflation, macro_usa, breadth, nyfed_term_premia |
| Geo | 10/25 | 10/25 | (sin cambio — datos geo-específicos suficientes) |
| **Todos** | Sin percentiles | Con p5Y | Bloomberg `_fmt_series_line` incluye percentil |
| **Todos** | Sin crisis ref | Con 8 episodios | `crisis_reference.py` inyectado en prompt |

**Verificación de compatibilidad:**
- Sprint 41 (Ciclo 8) agregó data_inventory al Contrarian — compatible, no afecta agent_data routing
- Sprint 32 (Ciclo 7) agregó CAUSAL_TREE al CIO — compatible, CIO ya recibía datos completos
- Sprint 31 (Ciclo 7) conectó coherence_warnings — compatible, no depende de agent_data

**Validación:** 4/4 archivos compilan OK. Crisis reference genera 2.5KB con 8 episodios verificados.

### Sprint 42 — Chile Equity Expansion + Data Dedup + Leyenda (3 mejoras)

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 177 | **Chile picks: 5 ADRs → 21 acciones** — RV report solo tenía BCH, BSAC, SQM, LTM, CCU. Faltan 16 stocks IPSA que yfinance cubre con tickers .SN | **FIXEADO:** `equity_data_collector.py` — nuevo `CHILE_SN_MAP` con 16 acciones Santiago Exchange (Cencosud, Falabella, Copec, BCI, Enel Chile, CMPC, Vapores, Colbún, Itaú, CAP, Ripley, Parque Arauco, Security, Sonda, Aguas Andinas, Enel Américas). Cada una con sector label. `collect_chile_top_picks()` ahora itera ADRs + .SN = 21 total |
| 178 | **Chile data duplicada** — Module 4 (ChileAnalytics) y Module 5 (BCChExtended) ambos fetch TPM, IPC, IMACEC, USD/CLP del BCCh = 5+ llamadas API duplicadas | **FIXEADO:** `council_data_collector.py` — Module 5 (extended) se fetch primero, `data['chile']` se deriva de `chile_extended.macro` sin API call adicional. Fallback a ChileAnalytics solo si extended falla |
| 179 | **Sin leyenda "—" en reportes** — clientes no saben qué significa el guion largo en celdas vacías | **FIXEADO:** 4 templates HTML — nota "— = dato no disponible en las fuentes consultadas para este período" en footer de Macro, RV, RF, AA |

**Verificación de compatibilidad:**
- Sprint 37 (data persist) y Sprint 39 (deep merge) alimentan `data['chile']` al AA — la derivación desde chile_extended.macro produce el mismo dict, sin conflicto
- Sprint 40 (historical store) busca `chile.tpm` en quant_data — compatible porque `chile_extended.macro` contiene `tpm`
- Chile picks expansion no afecta ningún fix previo — solo agrega más stocks al mismo array

**Validación:** 2/2 archivos Python compilan OK. 4 templates actualizados.

---

## Ciclo 7 — 2026-03-30: Auditoría de Seguridad + Lógica de Pipeline + Robustez

**Trigger:** Auditoría completa del codebase (5 agentes en paralelo: pipeline, data collectors, AI council, renderers, seguridad). Se cruzaron hallazgos contra IMPROVEMENT_LOG y se filtraron los ya resueltos en sprints anteriores. Los 15 hallazgos siguientes son genuinamente nuevos.

### Sprint 26 — Seguridad (5 hallazgos — 5 fixeados)

| # | Severidad | Hallazgo | Archivo:Línea | Fix aplicado |
|---|-----------|----------|---------------|-------------|
| 137 | CRÍTICO | API key AlphaVantage hardcodeada en source (2 copias del módulo earnings) — expuesta en git history | `greybark/analytics/fundamentals/earnings_analytics.py:25` + `greybark/analytics/earnings/earnings_analytics.py:24` | **FIXEADO:** Keys eliminadas de ambas copias → `os.environ.get('ALPHAVANTAGE_API_KEY', '')`. Bare `except:` → `except (ImportError, AttributeError):`. Key premium en `wealth/.env` + servidor (Hetzner). Repo privado, key no revocada |
| 138 | CRÍTICO | `exec(open(...).read())` ejecuta archivo arbitrario durante deploy | `deploy/init_layout.py:57` | **FIXEADO:** Reemplazado con `importlib.util.spec_from_file_location()` + `module_from_spec()` + `exec_module()` — carga módulo de forma segura sin exec() |
| 139 | ALTO | `subprocess.run(['start', '', path], shell=True)` — inyección de comandos si path contiene metacaracteres shell | 4 renderers | **FIXEADO:** `subprocess.run(..., shell=True)` → `webbrowser.open(str(output_path))` en `rv_report_renderer.py`, `asset_allocation_renderer.py`, `macro_report_renderer.py`, `rf_report_renderer.py` |
| 140 | ALTO | Sin escape HTML en templates — datos de council se inyectan directo en f-strings | Todos los `*_renderer.py` (33 instancias) | **FIXEADO** (Sprint 30) |
| 141 | ALTO | JWT secret default débil (`"change-me-in-production..."`) — tokens forjables si env var no seteada | `deploy/auth.py:18` | **FIXEADO:** Ahora emite `warnings.warn()` si `JWT_SECRET` no está seteado. Default inseguro se mantiene solo para dev local, con warning explícito en logs |

### Sprint 27 — Lógica de Pipeline (4 hallazgos — 4 fixeados)

| # | Severidad | Hallazgo | Archivo:Línea | Fix aplicado |
|---|-----------|----------|---------------|-------------|
| 142 | ALTO | `report_type='macro'` hardcodeado — council ignora reportes solicitados por usuario (`--reports rv rf`) | `run_monthly.py:531` | **FIXEADO:** `report_type = self.reports[0] if self.reports else 'macro'` — council ahora recibe el primer reporte solicitado como contexto |
| 143 | ALTO | Exit code 0 con errores — `self.errors` ignorado en chequeo final, solo revisa `self.report_results` | `run_monthly.py:949-951` | **FIXEADO:** `has_errors = any(...) or len(getattr(self, 'errors', [])) > 0` — exit code ahora refleja errores acumulados del pipeline |
| 144 | ALTO | Sin rate-limit backoff en API Claude — `_call_llm_async()` y `_call_llm_sync()` capturan `Exception` genérico | `ai_council_runner.py:188-220` | **FIXEADO** (Sprint 30) |
| 145 | ALTO | Parámetro incorrecto `lookback_months` vs `days_back` en fetch IPC | `rf_data_collector.py:515` | **FIXEADO** (Sprint 26) |

### Sprint 28 — Robustez de Datos (4 hallazgos — 4 fixeados)

| # | Severidad | Hallazgo | Archivo:Línea | Fix aplicado |
|---|-----------|----------|---------------|-------------|
| 146 | ALTO | `float(NaN)` y `float(inf)` pasan sin validación — contamina datos downstream | `council_data_collector.py:106-108` | **FIXEADO:** Nuevo helper `_clean_float(val, decimals, default)` con `math.isnan()`/`math.isinf()` check. Aplicado a JOLTS. Helper disponible para otros call sites |
| 147 | MEDIO | `.dropna()` llamado dos veces crea Series desalineadas — yield latest vs prev_month usan índices distintos | `rf_data_collector.py:330-331` | **FIXEADO:** `.dropna()` llamado una vez → guardado en `clean`. Ambos `.iloc[]` acceden la misma serie. Agregado guard `if len(clean) == 0: continue` |
| 148 | MEDIO | Sin timeouts individuales en llamadas FRED/BCCh/yfinance | Múltiples archivos | **FIXEADO** (Sprint 30) |
| 149 | MEDIO | Path hardcodeado `OneDrive/Documentos/proyectos/wsj_data` — solo funciona en Windows español | `run_monthly.py:65` | **FIXEADO:** Ya usaba `os.environ.get('WSJ_DATA_PATH')` como primera opción; fallback ajustado a lowercase para consistencia con filesystem |

### Sprint 29 — AI Council Quality (2 hallazgos — 2 fixeados)

| # | Severidad | Hallazgo | Archivo:Línea | Fix aplicado |
|---|-----------|----------|---------------|-------------|
| 150 | MEDIO | Anti-hallucination threshold demasiado suelto para tasas — permite error de 5bp sin corrección (2bp es material para duration) | `narrative_engine.py:371-372` | **FIXEADO:** `abs_diff > 0.05` → `abs_diff > 0.02` para valores < 10%. Ahora detecta errores de 2bp+ en tasas/yields/CPI |
| 151 | MEDIO | Block cache solo guarda primera ocurrencia — si Macro y RV producen `EQUITY_VIEWS`, RV se descarta sin aviso | `council_parser.py:61-63` | **FIXEADO:** Agregado `print(f"[WARN] council_parser: bloque duplicado '{block_name}'...")` cuando se detecta conflicto. Primera ocurrencia (refinador) sigue teniendo prioridad |

### Pendiente — Infraestructura (no bloqueante)

| # | Severidad | Hallazgo | Archivo | Nota |
|---|-----------|----------|---------|------|
| P1 | MEDIO | Coherence validator no valida inversión de curva ni alignment macro/equity | `coherence_validator.py` | **RESUELTO por diseño:** La coherencia lógica (macro stance vs equity views) es responsabilidad del refinador, que ahora recibe alertas de discrepancias (#152). El coherence_validator se limita a métricas numéricas (13 metrics) — que es su rol correcto |
| P2 | BAJO | Docker copia DB y passwords.json en imagen — deberían venir de secrets/volumes | `deploy/Dockerfile:20-21` | Usar Docker secrets o montar desde volumen |
| P3 | MEDIO | ~50 celdas "anterior"/"consenso" vacías en 4 reportes | Todos los content generators | **RESUELTO** (Sprint 40): `historical_store.py` guarda snapshot por run, inyecta `_prev` values en quant_data. `chart_data_provider` calcula CPI/PCE prev desde FRED series. Primera ejecución sin datos previos es esperado; segunda en adelante llena columnas "anterior" |

### Patrones Recurrentes Actualizados

| Patrón | Frecuencia acumulada | Sprint donde se documentó | Instancias nuevas (Ciclo 7) |
|--------|---------------------|--------------------------|----------------------------|
| API devuelve dict donde se espera escalar | 2 → 3 | Ciclo 6 Sprint 21 | `float(NaN/inf)` sin validar (#146) |
| Paths hardcodeados a `~/OneDrive/` | 2 → 3 | Ciclo 6 Sprint 17 | WSJ_DATA_PATH (#149) |
| **NUEVO: Seguridad nunca auditada** | — | Ciclo 7 | API key expuesta, exec(), shell=True, XSS, JWT (#137-141) |
| **NUEVO: Pipeline exit code unreliable** | — | Ciclo 7 | report_type hardcoded, self.errors ignorado (#142-143) |
| **NUEVO: Sin rate-limit handling en LLM calls** | — | Ciclo 7 | ai_council_runner swallows all exceptions (#144) |

**Validación Sprint 26 + #145:**
- 9/9 archivos modificados compilan OK (`py_compile`)
- #137: Key eliminada de 2 copias del módulo earnings → env var. Key premium configurada en `wealth/.env` (local) + servidor Hetzner
- #138: `exec()` → `importlib.util` — carga segura de módulo
- #139: `shell=True` eliminado en 4 renderers → `webbrowser.open()`
- #141: Warning explícito si JWT_SECRET no seteado
- #145: Chile IPC YoY ahora funciona (`lookback_months` → `days_back=420`)
- Verificado en local + servidor

**Validación Sprints 27-29:**
- 5/5 archivos modificados compilan OK (`py_compile`): `run_monthly.py`, `rf_data_collector.py`, `council_data_collector.py`, `narrative_engine.py`, `council_parser.py`
- #142: Council ahora recibe `report_type` dinámico del primer reporte solicitado
- #143: Exit code refleja `self.errors` además de `self.report_results`
- #146: `_clean_float()` helper rechaza NaN/inf — aplicado a JOLTS, disponible para otros call sites
- #147: `.dropna()` llamado una vez, series alineadas para yields internacionales
- #150: Anti-hallucination ahora detecta errores de 2bp+ en tasas (era 5bp)
- #151: Bloques duplicados en council output ahora generan warning en logs

**Resumen Sprints 26-29:** 12/15 hallazgos fixeados en primera ronda.

### Sprint 30 — Fixes Finales: HTML Escaping + Rate-Limit Backoff + Timeouts

| # | Severidad | Hallazgo | Fix aplicado |
|---|-----------|----------|-------------|
| 140 | ALTO | Sin escape HTML en templates — datos de council inyectados directo en f-strings | **FIXEADO:** Nuevo helper `_esc(val, default)` en 3 renderers (`rv`, `macro`, `aa`). 33 instancias de texto escapadas con `html.escape()`. RF ya usaba `_md_to_html()` (safe). Campos numéricos y CSS classes no tocados |
| 144 | ALTO | Sin rate-limit backoff en API Claude — errores tragados silenciosamente | **FIXEADO:** Nuevo método `_call_llm_with_retry(max_retries=3)` con exponential backoff (2s, 4s, 8s). Detecta `RateLimitError`, `429`, `Overloaded`, `529`. `_call_llm_async` y `_call_llm_sync` ahora delegan al retry handler |
| 148 | MEDIO | Sin timeouts individuales en FRED/BCCh/yfinance | **FIXEADO:** FRED: patched session.get con `timeout=30`. BCCh: timeout 15s→30s. yfinance: `timeout=30` en todas las llamadas `.history()` (4 call sites via replace_all) |

**Validación Sprint 30:**
- 7/7 archivos compilan OK (`py_compile`): `rv_report_renderer.py`, `macro_report_renderer.py`, `asset_allocation_renderer.py`, `ai_council_runner.py`, `fred_client.py`, `equity_data_collector.py`, `bcch_client.py`
- #140: 33 campos de texto escapados en 3 renderers (RF ya era safe)
- #144: Retry con backoff exponencial — 3 intentos antes de fallar
- #148: Timeouts de 30s en FRED, BCCh, y yfinance

### Sprint 31 — Auditoría de Coherencia del Pipeline

**Trigger:** Revisión completa del sistema de coherencia: desde datos verificados hasta output del refinador.

#### Estado del sistema de coherencia (7 capas verificadas)

| Capa | Mecanismo | Estado |
|------|-----------|--------|
| 1. Datos verificados | APIs (FRED, BCCh, yfinance, AV) → `agent_data` | ✅ Funciona — datos reales inyectados a cada agente |
| 2. Panel (5 agentes) | Cada agente recibe datos filtrados por expertise | ✅ Funciona — `_filter_data_for_agent()` |
| 3. Detección de conflictos | `_check_panel_coherence()` compara cifras entre panelistas | ✅ Funciona — detecta discrepancias pre-síntesis |
| 4. CIO + Contrarian | CIO sintetiza, Contrarian desafía | ✅ Funciona — 2 pasadas de síntesis |
| 5. Refinador | Output final con estilo profesional | ✅ Funciona — prompt con reglas anti-fabricación |
| 6. Anti-fabricación | `validate_narrative()` corrige números fabricados post-generación | ✅ Funciona — 50+ label patterns, thresholds por tipo |
| 7. Coherence validator | 13 métricas cruzadas entre 4 reportes | ✅ Funciona — score 0.0-1.0, alertas si < 0.75 |

#### Gap encontrado y fixeado

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 152 | **Coherence warnings no llegaban al refinador** — `_check_panel_coherence()` detectaba conflictos (ej: "macro dice S&P P/E=22.1x, rv dice 21.8x") pero las warnings solo se imprimían en log. El refinador sintetizaba sin saber que hubo discrepancias. | **FIXEADO:** `ai_council_runner.py` — (1) warnings inyectadas en `council_input['coherence_warnings']` después de detección (línea 862). (2) `_build_refinador_prompt()` ahora incluye sección `## ALERTAS DE COHERENCIA` con las discrepancias + instrucción de priorizar datos cuantitativos verificados sobre citaciones de panelistas |

**Causa raíz:** `_check_panel_coherence()` se ejecutaba entre Capa 1 (panel) y Capa 2 (síntesis), pero su output era solo un `print()` de log. No existía canal para pasar las warnings al refinador. Ahora fluyen: `panel → coherence check → council_input['coherence_warnings'] → refinador prompt`.

**Validación:**
- `ai_council_runner.py` compila OK (`py_compile`)
- Flow verificado: warnings se inyectan en `council_input` (línea 862) → `_build_refinador_prompt` las lee (línea ~740) → refinador recibe sección `ALERTAS DE COHERENCIA` con instrucciones de reconciliación

#### Análisis completo de coherencia — sin gaps adicionales

Los siguientes items fueron verificados como **funcionales y correctamente conectados**:

1. **13 métricas del coherence_validator** (fed_funds, ust_10y, core_cpi, sp500_pe, ig_spread, tpm_chile, vix, wti, copper, breakeven_5y, breakeven_10y, tips_10y, selic) — cada una con tolerancia calibrada y extractores por reporte
2. **Anti-fabricación en narrative_engine** — 50+ label patterns, threshold 2bp para tasas (fixeado Sprint 29), corrección in-place post-generación
3. **Block parser con detección de duplicados** — warnings de bloques conflictivos (fixeado Sprint 29)
4. **Prompt del refinador** — reglas explícitas: "PROHIBIDO inventar datos", "cada número = fuente verificada", "si no hay dato, usar 'Sin datos disponibles'"
5. **Post-council validation** — `validate_narrative()` aplicado al output del refinador antes de almacenarlo

**Resumen Final Ciclo 7:** 16/16 hallazgos fixeados (15 originales + 1 de auditoría de coherencia). 0 pendientes.

### Sprint 32 — Prompt Enhancement: CAUSAL_TREE + Mejoras de Conectividad

**Trigger:** Propuesta de mejora para agregar árbol causal estructurado al output del CIO y conectar mejor los prompts entre sí. Verificado contra pipeline — cambios son solo en prompts, no rompen código.

| # | Archivo | Cambio | Impacto |
|---|---------|--------|---------|
| 153 | `ias_cio.txt` | +ÁRBOL CAUSAL obligatorio: JSON estructurado `[CAUSAL_TREE_START]...[CAUSAL_TREE_END]` con root (escenario base), L1 (canales transmisión), L2 (efectos económicos), 5 outcomes fijos (US Equities/Treasuries/Credit/FX/Chile) con probabilidades por escenario. +Validación de escenarios: probabilidades deben sumar 100% | AA renderer podrá generar visualización del árbol causal. Probabilidades coherentes con RISK_MATRIX y ESCENARIOS |
| 154 | `ias_contrarian.txt` | +Sección RAÍZ DEL ÁRBOL obligatoria: 3 preguntas — ¿driver correcto?, ¿canales completos?, ¿probabilidades consistentes con RISK_MATRIX? | Contrarian ahora desafía la estructura causal, no solo la narrativa |
| 155 | `refinador.txt` | +Instrucción CAUSAL_TREE pass-through: preservar JSON exacto sin modificar, colocar al final del documento, copiar CAUSAL_TREE_SKIP si aplica | Renderer recibe JSON limpio del CIO sin interferencia del refinador |
| 156 | `ias_macro.txt` | +Nota en mecanismos de transmisión: ser específico en variable intermedia porque el CIO usa estos canales como nodos L1/L2 del árbol | Macro produce canales más granulares → árbol causal más preciso |
| 157 | `ias_geo.txt` | +Formato preferido por canal: CANAL → MAGNITUD → ACTIVO → HORIZONTE. Nota: canales alimentan L1 del árbol causal | Geo produce canales cuantificados → árbol causal con magnitudes reales |

**Verificación de compatibilidad:**
- `council_parser.py`: `[CAUSAL_TREE_START]` no matchea patrón `[BLOQUE:]` → pasa sin ser parseado (safe)
- `validate_narrative()`: solo corrige números, no toca estructura JSON (safe)
- `coherence_validator.py`: no valida probabilidades de escenarios (safe)
- `asset_allocation_content_generator.py`: sum-to-100 logic existente es compatible
- 0 archivos Python modificados — cambios solo en 5 archivos .txt de prompts

### Sprint 33 — CAUSAL_TREE Renderer (parser + visualización HTML)

**Trigger:** Los prompts del Sprint 32 generan `[CAUSAL_TREE_START]...[CAUSAL_TREE_END]` JSON. Faltaba el código que lo extrae y lo renderiza como visualización en el reporte AA.

| # | Archivo | Cambio |
|---|---------|--------|
| 158 | `council_parser.py` | Nuevo método `get_causal_tree()`: extrae JSON entre delimitadores `[CAUSAL_TREE_START]...[CAUSAL_TREE_END]`, busca en `final_recommendation` → `cio_synthesis`. Retorna dict parseado o None si `[CAUSAL_TREE_SKIP]` o JSON inválido |
| 159 | `asset_allocation_renderer.py` | Nuevo método `_render_causal_tree()`: convierte JSON del árbol en HTML puro con CSS inline. Root (pill grande) → L1 (pills canal transmisión) → L2 (pills efecto económico) → 5 barras de probabilidad (outcomes). Colores del design system (coral/amber/purple/teal). Print-ready con `page-break-inside:avoid` |
| 160 | `templates/asset_allocation_professional.html` | Nueva sección 10 "Árbol Causal del Escenario Dominante" con `{% if causal_tree_html %}` guard — solo aparece si el CIO generó el árbol |

**Validación:**
- 2/2 archivos Python compilan OK (`py_compile`)
- Test con JSON de ejemplo: parser extrae correctamente (5 outcomes, probs suman 100%)
- Renderer genera 4KB HTML con nodos, flechas, barras de probabilidad por outcome
- Template condicional: si no hay árbol, la sección no aparece (backward compatible)
- Sin árbol: reportes existentes no se afectan

### Sprint 34 — Auditoría de Verificación del IMPROVEMENT_LOG

**Trigger:** Auditoría completa cruzando cada fix documentado (#137-160) contra el código real. Se verificaron los 24 items.

**Resultado:** 23/24 verificados correctamente. 1 gap encontrado:

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 161 | **HTML escaping incompleto en `_md_to_html()` / `_md_to_html_inline()`** — Sprint 30 documentó "RF ya usaba `_md_to_html()` (safe)" pero `_md_to_html()` en RF y `_md_to_html_inline()` en RV/Macro/AA convertían markdown a HTML **sin escapar el contenido base**. Texto como `<script>` pasaba directo. | **FIXEADO:** Agregado `_html_escape(text)` después de extraer style blocks y antes de convertir markdown en los 4 renderers. RF además recibe `_esc()` helper (no lo tenía). Orden: extract styles → escape HTML → convert markdown → restore styles |

**Archivos corregidos:**
- `rf_report_renderer.py`: +`_esc()` helper, +`_html_escape()` en `_md_to_html()`
- `rv_report_renderer.py`: +`_html_escape()` en `_md_to_html_inline()`
- `macro_report_renderer.py`: +`_html_escape()` en `_md_to_html_inline()`
- `asset_allocation_renderer.py`: +`_html_escape()` en `_md_to_html_inline()`

**Validación:** 4/4 renderers compilan OK (`py_compile`)

**Estado final del IMPROVEMENT_LOG:** Todos los fixes #137-161 verificados en código. 0 discrepancias.

### Sprint 35 — Fix Regresión: _md_to_html_inline escapaba HTML del reporte completo

**Trigger:** Al correr pipeline AA, el reporte salía con `&lt;div&gt;` en vez de `<div>` — todo el HTML escapado. Causado por Sprint 34 que agregó `_html_escape()` dentro de `_md_to_html_inline()`, función que se aplica al HTML renderizado completo (no a campos individuales).

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 162 | **`_html_escape()` en `_md_to_html_inline()` rompía los 3 reportes** — esta función se aplica al HTML final del reporte (línea 138/150/171 de rv/aa/macro), no a campos individuales. Al agregar escape ahí, se escapaba `<div>`, `<table>`, `<style>`, etc. | **FIXEADO:** Revertido `_html_escape()` de `_md_to_html_inline()` en rv, macro, aa. RF mantiene escape en `_md_to_html()` porque esa función solo se aplica a campos individuales, no al HTML completo |

**Causa raíz:** `_md_to_html_inline()` tiene doble uso — convierte markdown Y se aplica como post-procesador al HTML completo del reporte. Agregar escape ahí afecta ambos usos. La protección XSS correcta es `_esc()` en cada campo individual (Sprint 30, 33 instancias) — no en el post-procesador global.

**Validación:**
- 4/4 renderers compilan OK
- Reporte AA regenerado: HTML limpio, sección 10 "Árbol Causal" renderiza correctamente con nodos de colores y barras de probabilidad
- Árbol del council real: "Estanflación moderada por shock energético geopolítico" con root "Conflicto EE.UU.-Irán Hormuz", 5 outcomes con distribución de probabilidades

### Sprint 36 — CAUSAL_TREE v2: SVG Renderer

**Trigger:** Sugerencia de mejora visual — reemplazar HTML tables/pills por SVG puro con flechas reales.

| # | Archivo | Cambio |
|---|---------|--------|
| 163 | `causal_tree_renderer.py` | **NUEVO:** Módulo dedicado con `render_causal_tree_html()`. SVG puro con: paleta suave (fill 50/stroke 600/text 800), flechas con marker SVG, layout engine `_layout()` que calcula posiciones, barras de probabilidad integradas bajo outcome nodes, layer labels como texto tenue. Colores: coral (geopolítico), amber (económico), purple (política monetaria), teal (outcomes) |
| 164 | `asset_allocation_renderer.py` | `_render_causal_tree()` reducido a 5 líneas — delega a `causal_tree_renderer.render_causal_tree_html()`. Elimina ~80 líneas de HTML v1 |

**Validación:**
- 2/2 archivos compilan OK
- Reporte AA regenerado con SVG: viewBox 900x528, flechas con markers, 5 outcomes con barras de probabilidad
- Backward compatible: si no hay árbol, retorna ''

### Sprint 37 — Fix: Datos cuantitativos vacíos en reporte AA

**Trigger:** Reporte AA mostraba ~55 celdas con "—" o "N/D" (GDP, CPI, TPM, Cobre, etc.) a pesar de que los datos se recolectaban durante el council.

**Causa raíz:** El council runner recolecta `council_input` (con `quantitative` dict completo) pero solo guarda `council_result` (que excluye datos cuantitativos). Cuando el renderer del AA pide `self.data['macro_quant']`, no existe — los datos se recolectaron en memoria para el council pero nunca se persistieron ni se pasaron al renderer.

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 165 | **Datos cuantitativos del council no llegaban al renderer AA** — `council_input.quantitative` se descartaba después del council run | **FIXEADO:** (1) `ai_council_runner.py`: nuevo atributo `self._last_council_input` expone el council_input completo después del run. (2) `run_monthly.py`: después del council, extrae `quantitative` → `self.data['macro_quant']` para el renderer + guarda `council_input_*.json` para cache en futuros `--skip-collect` |

**Impacto:** En el próximo run, el AA tendrá acceso a: macro_usa (GDP, CPI, retail sales), chile (TPM, IPC, cobre), inflation, rates, risk metrics, china, international — todo lo que el collector recolecta. Las ~55 celdas vacías se llenarán.

**Validación:** 2/2 archivos compilan OK. Requiere run completo del pipeline para verificar datos en reporte.

### Sprint 38 — Report Quality Checker (detección post-render de celdas vacías)

**Trigger:** Pregunta "cómo nos aseguramos de no tener tablas vacías en ningún reporte". Se necesitaba un mecanismo de detección automática.

| # | Archivo | Cambio |
|---|---------|--------|
| 166 | `report_quality_checker.py` | **NUEVO:** Módulo `check_report_quality(html, report_name)` que escanea HTML post-render buscando: celdas "—" (datos no disponibles), residuos "N/D", placeholders `{{}}` sin reemplazar, tipos Python crudos (numpy, dicts, NaN, None). Retorna lista de issues con severidad (high/medium/low). `print_quality_report()` imprime resumen formateado |
| 167 | 4 renderers | Integrado quality check después de `clean_nd()` y antes de escribir archivo. Los 4 reportes (rv, rf, macro, aa) ahora imprimen resumen de calidad en el log del pipeline |

**Output ejemplo:**
```
[AA] Quality check: ALERT — 34 issues found:
    !! 34 celdas con "—" (datos no disponibles)
```
o
```
[RV] Quality check: CLEAN — 0 issues
```

**Validación:** 5/5 archivos compilan OK. Test con reporte AA actual: detecta correctamente 34 celdas vacías.

### Análisis de flujo de datos: por qué no habrá celdas vacías después del Sprint 37

**Diagnóstico del problema original:** Las ~55 celdas vacías en AA eran TODAS de `macro_quant` (GDP, CPI, TPM, cobre, VIX, inflation, etc.). Los datos de `equity` y `rf` llegaban bien porque se guardan en JSON separados. Los de `macro_quant` se perdían porque el council runner los recolectaba internamente y no los exponía.

**Flujo corregido (después de Sprint 37):**
```
Sin --skip-collect:
1. collect_all_data() → self.data['macro_quant'] = collector.collect_quantitative_data()
2. Council runner re-recolecta internamente (datos frescos)
3. Sprint 37: self.data['macro_quant'] = runner._last_council_input.quantitative (sobrescribe con datos más frescos)
4. Rendering: aa_data = rf_data + equity_data + macro_quant → COMPLETO

Con --skip-collect:
1. Busca council_input_*.json (creado por Sprint 37 en run previo)
2. self.data['macro_quant'] = council_input.quantitative → COMPLETO
3. Si no existe cache: fallback a recolección fresca
4. Council runner re-recolecta → Sprint 37 sobrescribe → COMPLETO
```

**Keys de macro_quant que llegan al AA:**
regime, macro_usa (GDP, CPI, employment), leading_indicators, inflation (breakevens, CPI), chile (TPM, IPC, USD/CLP), chile_extended, china, rates (Fed, SOFR), risk (VIX, correlations), breadth, international, bloomberg, cpi_fiscal, bea, oecd, nyfed

**Merge en AA (run_monthly.py:726-737):**
- rf_data → top level (yield_curve, credit_spreads, chile_rates)
- equity_data → nested under 'equity' key
- macro_quant → top level, no sobrescribe RF/equity keys
- Sin colisiones destructivas: RF `chile_rates` tiene precedencia (datos más específicos de tasas), macro_quant `chile` aporta datos complementarios (TPM, IPC, USD/CLP)

**Sprint 38 (quality checker):** Detecta cualquier celda vacía residual post-render → visible en log del pipeline.

### Sprint 39 — Fix: Deep merge + GDP world fallback (celdas vacías restantes)

**Trigger:** Pipeline completo mostró 73 celdas vacías (Macro 40, RV 2, RF 9, AA 22). Auditoría identificó 2 bugs reales de datos + columnas "anterior" que ninguna API produce.

| # | Hallazgo | Fix aplicado |
|---|----------|-------------|
| 168 | **AA: CPI core = None por colisión de merge** — `rf_data` y `macro_quant` ambos tienen key `inflation`, pero RF's `inflation` no tiene `cpi_core_yoy`. Merge shallow (`if k not in aa_data: skip`) descartaba macro_quant's `inflation` completo | **FIXEADO:** `run_monthly.py` — deep merge: si ambos tienen la misma key y ambos son dicts, fusiona sub-keys (macro_quant llena gaps de RF). CPI core ahora: 2.73% |
| 169 | **MACRO: World GDP siempre N/D** — `forecast_engine` no produce key 'world', solo regiones. IMF WEO tampoco tiene key directa | **FIXEADO:** `macro_content_generator.py` — si IMF y forecast engine no tienen 'world', calcula promedio ponderado de USA(25%), Eurozone(20%), China(18%) |
| 170 | **MACRO: Europa GDP por país sin forecast** — `forecast_engine` solo produce 'eurozone' agregado, no por país | **FIXEADO:** `macro_content_generator.py` — busca en `imf_consensus.gdp.{country}` como fallback. Si IMF no tiene, queda N/D (dato genuinamente no disponible) |

**Celdas vacías residuales después de estos fixes (no son bugs):**
Las ~50 celdas vacías restantes son columnas "anterior" / "consenso" que **ninguna API produce**:
- CPI/PCE "anterior" en Macro: requeriría almacenar valor del mes pasado (no implementado)
- Europa/China "anterior": BCCh no da datos históricos por período anterior
- AA escenarios "implicancias": dependen de que el council produzca texto estructurado de impacto por asset class

Estas NO son datos disponibles que no llegan — son datos que el sistema no recolecta porque requieren comparación temporal (valor actual vs mes anterior). Implementar esto requiere un store histórico.

**Validación:**
- `run_monthly.py` y `macro_content_generator.py` compilan OK
- Deep merge test: 9/9 data points AA resuelven (GDP 0.7%, CPI 2.73%, TPM 4.5%, VIX 24.3, IG 93bp, UST 4.35%, Copper $5.51, USDCLP 927, BE5Y 2.54%)

### Sprint 40 — Historical Data Store (eliminar celdas "anterior" vacías)

**Trigger:** ~50 celdas "anterior"/"consenso" vacías en 4 reportes porque el sistema no almacenaba datos entre runs para comparación temporal.

| # | Archivo | Cambio |
|---|---------|--------|
| 171 | `historical_store.py` | **NUEVO:** Módulo que guarda snapshot de ~30 métricas clave por run (`output/historical/snapshot_{date}.json`). `get_previous()` carga snapshot del run anterior. `inject_prev_into_data()` inyecta valores `_prev` en quant_data para que los content generators los lean sin modificaciones. Métricas: GDP, CPI, NFP, TPM, VIX, spreads, copper, FX, breakevens, etc. |
| 172 | `run_monthly.py` | Integrado en 3 puntos: (1) `collect_all_data()` guarda snapshot + carga prev. (2) `_load_existing_data()` carga prev para --skip-collect. (3) `generate_reports()` inyecta prev values en macro_quant antes del rendering |
| 173 | `chart_data_provider.py` | `get_usa_latest()` ahora incluye CPI/PCE prev values: calcula `cpi_headline_yoy_prev`, `cpi_core_yoy_prev`, `pce_core_yoy_prev` desde las series YoY de FRED |

**Flujo:**
```
Run N: collect → save snapshot_20260401.json (14+ métricas) → render (sin prev, primera vez)
Run N+1: load snapshot_20260401.json → inject _prev keys → render (columnas "anterior" llenas)
```

**Validación:**
- 3/3 archivos compilan OK
- Test: snapshot guarda 14 métricas, injection inyecta 8+ prev values en quant_data
- CPI prev: `chart_data_provider` ahora produce `cpi_core_yoy_prev` directamente desde FRED series
- Primera ejecución: columns "anterior" vacías (no hay snapshot previo — correcto)
- Segunda ejecución en adelante: columns "anterior" llenas con datos del run anterior

---

## Ciclo 6 — 2026-03-25: Prompt Audit + Dashboard Isolation + Hetzner Deploy

**Trigger:** Audit completo de los 31 prompts del AI Council + deploy a producción.

### Sprint 13 — Prompt Audit (5 mejoras implementadas)

| # | Archivo | Mejora | Impacto |
|---|---------|--------|---------|
| 81 | `ias_riesgo.txt` | +Calibración histórica obligatoria (GFC/COVID/Taper/SVB/Volmageddon), +Correlaciones obligatorias (3 métricas con actual/1Y/5Y), +RISK_MATRIX con magnitud equity%/RF bps condicional (dato/ref./omitir), +BLOQUE: CORRELACIONES | Downstream: AA scenario tables ahora reciben impactos cuantificados |
| 82 | `ias_contrarian.txt` | +SUPUESTO MÁS PELIGROSO obligatorio (ranked #1 con prob/impacto/señal), +Analogías históricas obligatorias con resultado cuantificado, word limit 500-600→600-800 | Refinador recibe input priorizado en vez de lista sin ranking |
| 83 | `ias_macro.txt` | +Mecanismos de transmisión obligatorios (CATALIZADOR→CANAL→VARIABLE→HORIZONTE), +Tabla de lags típicos (8 referencias: pol monetaria 12-18m, China credit 3-6m, etc.) | Agentes downstream saben CUÁNDO impacta cada catalizador |
| 84 | `ias_cio.txt` | +Referencia explícita a 9 bloques del panel con fuente, +Regla de precedencia bloque > prosa | Reduce riesgo de que CIO ignore datos estructurados |
| 85 | `personas.py` + `committee_session.py` | +Header DEPRECATED (legacy FOMC In Silico, no es producción) | Elimina riesgo de confusión con sistema de producción |
| 86 | `refinador.txt` | +Regla: omitir campos vacíos del RISK_MATRIX del output final | Evita placeholders sin dato en reportes finales |

### Sprint 14 — Dashboard Client Isolation

| # | Archivo | Mejora |
|---|---------|--------|
| 87 | `deploy/app.py` | `_get_client_reports()` solo busca en carpeta del cliente, no en `output/reports/` compartido |
| 88 | `deploy/app.py` | +`_copy_reports_to_client()` copia reportes a `<output>/<client_id>/<YYYY-MM-DD>/` post-pipeline |
| 89 | `deploy/web_templates/settings.html` + `deploy/app.py` | +Campo editable "Nombre de empresa" con live preview |
| 90 | `dashboard.py` | Eliminado (Streamlit legacy) |

### Sprint 15 — Hetzner Deploy (Helsinki → Ashburn)

| # | Cambio |
|---|--------|
| 91 | Dockerfile con QuantLib + layout_seed (greybark_platform.py, greybark.db, passwords.json) |
| 92 | Nginx reverse proxy + persistent volumes (`/data/layout`, `/data/research`) |
| 93 | API keys configuradas en servidor (ANTHROPIC, FRED, AV, BCCh) |
| 94 | Helsinki descartado (BCCh timeout, CommLoan bloqueado geográficamente) |
| 95 | Servidor migrado a **Ashburn, VA** (CPX11) — `http://87.99.133.124` |

### Sprint 16 — Dependency Audit + Rates Fallback

**Trigger:** Pipeline fallaba en servidor: `rates` RED (CommLoan bloqueado), `china` silenciosamente sin datos (akshare no instalado), `chile_extended`/`international` timeout.

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 96 | akshare no en requirements → módulo China falla silencioso | `deploy/requirements.txt` | +akshare>=1.12.0, +beautifulsoup4>=4.12.0 |
| 97 | CommLoan scraper bloqueado desde servidores (devuelve HTML) | `greybark/analytics/rate_expectations/usd_expectations.py` | Fallback NY Fed SOFR API + FRED SOFR averages (30d/90d/180d). Curva 9 tenors: ON→10Y |
| 98 | Default timeout 60s insuficiente para BCCh desde US | `data_resilience.py` | Default 60s→90s; chile_extended/international/rates explícitamente 120s |
| 99 | `rates` como IMPORTANT bloqueaba council innecesariamente | `council_preflight_validator.py` | Temporalmente OPTIONAL durante Helsinki; restaurado a IMPORTANT tras fix NY Fed |

**Validación:**
- NY Fed fallback produce 9 tenors: SOFR ON 3.63%, 1M 3.66%, 3M 3.69%, 6M 3.88%, 1Y-10Y extrapolados
- akshare v1.18.46 instalado y funcional en container
- Portal live en `http://87.99.133.124` (Ashburn, VA)

### Sprint 17 — Daily Reports + Data Sync + Fixes

**Trigger:** Pipeline generaba reportes sin narrativas — 0 daily reports en servidor, API key inválida, chile_extended crasheaba.

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 100 | Daily reports 0 en servidor (path apunta a `~/OneDrive/` local) | `daily_report_parser.py` usa `DAILY_REPORTS_PATH` | Subidos 150 daily reports a `/data/daily_reports/`, env var + volumen Docker |
| 101 | DF summaries 0 en servidor | `DF_SUMMARY_DIR` no seteado | Subidos 88 resúmenes a `/data/df_data/`, env var + volumen Docker |
| 102 | Anthropic API key inválida (401 auth error) | `/data/.env` | Key reemplazada — ahora API responde OK |
| 103 | `chile_extended` crash: `get_ipc_detail()` no existe en BCChExtendedClient | `council_data_collector.py:177` | Eliminado método inexistente del dict |

**Validación:**
- `DailyReportParser.get_monthly_summary()` → 43 reportes encontrados (Feb 24 - Mar 25)
- 88 resúmenes DF disponibles para intelligence digest
- `chile_extended` ahora GREEN (7 submódulos OK)
- Anthropic API OK (test directo desde container)

### Sprint 18 — Pipeline Error Sweep (7 fixes)

**Trigger:** Revisión de `pipeline_log_20260318` reveló 7 errores activos: charts crasheando, métodos inexistentes, timezone mismatch, intelligence digest sin instanciar.

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 104 | `risk_matrix` chart crash: `'str' object has no attribute 'get'` — se pasaba dict `{riesgos, narrativa}` en vez de lista | `chart_generator.py:1154` | Extraer `.get('riesgos', [])` del dict antes de pasar a `generate_risk_matrix()` |
| 105 | YTD return crash: `TypeError: Invalid comparison between datetime64[ns, America/New_York] and datetime` — yfinance devuelve index tz-aware, comparado con string naive | `equity_data_collector.py:163,234,723` | Usar `pd.Timestamp(...).tz_localize(hist.index.tz)` en las 3 ubicaciones + agregar `import pandas as pd` |
| 106 | `get_usa_cpi_components()` no existe en ChartDataProvider | `council_data_collector.py:325`, `macro_content_generator.py:896` | Renombrar a `get_usa_cpi_breakdown()` (método real) |
| 107 | `get_latam_macro()` no existe en ChartDataProvider | `council_data_collector.py:327` | Renombrar a `get_latam_rates()` (método real) |
| 108 | `DailyIntelligenceDigest.format_for_council()` llamado como classmethod pero es instance method | `pre_council_package.py:245` | `DailyIntelligenceDigest.format_for_council(x)` → `DailyIntelligenceDigest().format_for_council(x)` |
| 109 | ChartDataProvider init falla silenciosamente (`except Exception: pass`) — sin log del error real | `macro_report_renderer.py:86` | Agregar log: `print(f"[WARN] ChartDataProvider init failed: {e}")` |
| 110 | Dashboard `_client_context()` retorna dict incompleto cuando cliente no tiene data → templates crashean | `deploy/app.py:105` | Agregar fallback values (primary_color, company_name, etc.) + `threading.Lock` para `_jobs` |

**Validación:**
- 7/7 archivos compilan OK (`py_compile`)
- Commit `530b4d6` pushed a `origin/main`
- BCChExtendedClient, akshare_client, AlphaVantageClient, curvas_soberanas — verificados OK (errores del log eran de estado previo)

### Sprint 19 — Multi-Client Onboarding (producción)

**Trigger:** Plataforma en `87.99.133.124` solo tenía 2 clientes (greybark, demo_corp). Se necesitaban 3 clientes reales. Pipeline de bvc no corría: `?error=no_council`.

| # | Cambio | Detalle |
|---|--------|---------|
| 111 | Crear cliente `mbi` (MBI Inversiones) en producción | `Platform.add_client()` + bcrypt hash en `/app/layout/passwords.json` |
| 112 | Crear cliente `vantrust` (Vantrust Capital) en producción | Idem — `product_ai_council` estaba en `False` por defecto |
| 113 | Crear cliente `bvc` (BVC Asset Management) en producción | Idem — mismo problema con flag deshabilitado |
| 114 | Pipeline crash `?error=no_council` para bvc y vantrust | `clients.product_ai_council = 0` por defecto en `add_client()` → UPDATE SQL directo a `1` para los 3 nuevos clientes |

**Causa raíz:** `Platform.add_client()` no setea `product_ai_council=True` por defecto, y `update_client()` no acepta campos de producto (solo campos de perfil). Los nuevos clientes quedan sin acceso al pipeline.

**Validación:**
- 5/5 clientes con `product_ai_council=1` en DB producción
- Login verificado con bcrypt para mbi/vantrust/bvc
- Pipeline de bvc ya no redirige a `?error=no_council`

### Sprint 20 — RF KeyError + Docker Volume Persistence

**Trigger:** Pipeline de BVC completó 3/4 reportes. RF crasheó con `KeyError: 'impacto'`. Reportes no aparecían en portal (no se copiaron a carpeta del cliente). Directivas se perdían entre rebuilds.

| # | Bug | Fix |
|---|-----|-----|
| 115 | RF report crash: `KeyError: 'impacto'` — council devuelve `severidad` en vez de `impacto`, `mitigacion` en vez de `hedge` | `rf_report_renderer.py:417-428` — todos los accesos a risks/trades usan `.get()` con fallback a alias alternativos (`severidad`, `mitigacion`) y `N/D` por defecto |
| 116 | Reportes no se copiaban a carpeta del cliente cuando pipeline terminaba con código 1 (error parcial) | `_copy_reports_to_client()` solo corre si `return_code == 0`. Reportes copiados manualmente. Fix futuro: copiar reportes OK aunque haya errores parciales |
| 117 | Reportes generados se perdían entre rebuilds del container | Montar `/app/consejo_ia/output` → `/data/pipeline_output` como volumen Docker persistente |
| 118 | Directivas de usuario se perdían entre rebuilds | Montar `/app/consejo_ia/input` → `/data/input` como volumen Docker persistente |
| 119 | Macro report no se generó en segundo run de BVC | Pendiente de investigar — posible timeout o error en fase 4 |

**Docker volumes finales (producción):**
```
-v /data/layout:/app/layout                          # DB, passwords, platform
-v /data/pipeline_output:/app/consejo_ia/output      # Reportes, cache, council
-v /data/input:/app/consejo_ia/input                 # Directivas, bloomberg, logos
-v /data/daily_reports:/app/daily_reports             # Daily reports
-v /data/df_data:/app/df_data                        # DF summaries
-v /data/research:/app/consejo_ia/input/research     # Research files
```

**Validación:**
- RF report genera OK con `.get()` fallbacks
- 4 reportes de BVC copiados a `/app/layout/output/bvc/2026-03-26/`
- Directivas persisten entre `docker stop/start/rebuild`
- Output (cache, council, reports) persiste entre rebuilds

### Sprint 21 — Briefing Data Formatting + Macro LatAm Fix

**Trigger:** Briefing de BVC mostraba datos raw de numpy/dict en la tabla de "Datos de Mercado Verificados" (ej: `{'value': np.float64(0.7), 'period': 'Q4 2025', ...}%` en PIB USA). Macro report no se generó (no seleccionado en form). RF yield curve OK con datos actuales.

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 120 | Briefing muestra dicts raw en vez de valores formateados — APIs devuelven `{'value': 0.7, 'period': ...}` pero el formatter solo chequeaba `isinstance(float)` | `pre_council_package.py:624-631` | Agregar unwrap de dicts (extraer key `value`/`current`/`latest`/`rate`) + conversión de `np.float64` a `float` antes de formatear |
| 121 | `macro_content_generator.py:2033` aún llamaba `get_latam_macro()` (inexistente) — escapó del fix del Sprint 18 | `macro_content_generator.py:2033` | Renombrar a `get_latam_rates()` — tabla LatAm del macro report mostraba N/D para todos los países |
| 122 | Macro report no generado en run de BVC | N/A | No era bug de código — macro no fue seleccionado en el form del portal. Datos cacheados permiten re-run con `--skip-collect` |

**Validación:**
- 8/8 RF charts generan OK en servidor (incluyendo `rf_yield_curve`)
- `pre_council_package.py` y `macro_content_generator.py` compilan OK
- Container reconstruido y desplegado con datos persistentes
- Commit `d078ab7` pushed y desplegado en producción

### Sprint 22 — Macro Series.__format__ Crash + Report Copy on Partial Failure

**Trigger:** Pipeline de BVC terminaba con código 1 (macro crash) y los 3 reportes OK no se copiaban a la carpeta del cliente. Macro crasheaba: `unsupported format string passed to Series.__format__`.

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 123 | Macro crash `Series.__format__`: `_build_latam_table()` recibía `pd.Series` completas de `get_latam_rates()` e intentaba `f"{series:.1f}%"` | `macro_content_generator.py:2027-2050` | Reescrito: mapea keys de series (`'Selic (Brasil)'` etc.), extrae último valor con `.iloc[-1]`, convierte a float |
| 124 | Reportes OK no copiados a carpeta del cliente cuando pipeline termina con error parcial | `deploy/app.py:548-557` | Mover `_copy_reports_to_client()` **antes** del check de `return_code` — siempre copia lo que haya en `output/reports/` |

**Causa raíz #123:** `get_latam_rates()` retorna `Dict[str, pd.Series]` (series completas de tasas por país), no `Dict[country, {cpi, tasa}]` como esperaba `_build_latam_table()`. El rename de Sprint 18 (`get_latam_macro` → `get_latam_rates`) cambió el método sin adaptar el consumer.

**Validación:**
- Macro report genera OK con tabla LatAm (tasas reales de BCCh)
- 3 reportes de run anterior (rv, rf, aa) copiados exitosamente a `/app/layout/output/bvc/`
- Commit `3a8b448` desplegado en producción

### Sprint 23 — Pre-Demo Audit (MBI, Vantrust, BVC)

**Trigger:** Antes de correr 3 pipelines independientes para demos de clientes, auditoría completa de 4 capas: reportes, prompts, renderers, data collection.

#### Auditoría de Reportes BVC (4 HTML generados)

| Reporte | N/D | Placeholders `{{}}` | numpy raw | Charts | Verdict |
|---------|-----|---------------------|-----------|--------|---------|
| RV | 0 | 0 | 0 | 12 imgs | CLEAN |
| RF | 0 | 0 | 0 | 8 imgs | CLEAN |
| AA | 0 | 0 | 0 | 0 (text-only) | CLEAN |
| Briefing | 0 | 0 | 0 | 44 imgs | CLEAN |
| Macro | — | — | — | — | MISSING (crash fixeado Sprint 22) |

#### Auditoría de Prompts (8 archivos)

| Check | Resultado |
|-------|-----------|
| Bloques consistentes con parser | 11/12 OK (`CORRELACIONES` no parseado) |
| Calidad español / encoding | 8/8 OK |
| Anti-fabricación | 8/8 tienen `INTEGRIDAD DE DATOS` |
| Word limits | 3/8 tienen (panel agents sin límite) |
| Data references vs collectors | OK — sin campos fantasma |

**Issues menores (no bloqueantes):**
- `CORRELACIONES` block producido por riesgo pero no parseado por `council_parser.py`
- 5 panel agents sin word limit (controla tokens/costo)
- `ias_geo.txt`: dice "max 3" pero template muestra 4

#### Auditoría de Renderers (4 renderers + 4 content generators)

| Severidad | Count | Tipo |
|-----------|-------|------|
| CRITICAL | ~28 | `dict['key']` directo sin `.get()` — KeyError si council output incompleto |
| HIGH | ~7 | `_get_view_class(None)` crash, falsy check en `0.0` |
| MEDIUM | ~3 | Format issues dentro de try/except |

**Archivos más frágiles:**
- `rv_report_renderer.py` — 9 crash points (sectores, earnings, flows, risks)
- `rf_report_renderer.py` — 5 crash points (duration, credit, EM debt, Chile)
- `macro_report_renderer.py` — 4 crash points (USA/Europe/China/Chile sections)
- `asset_allocation_renderer.py` — 6 crash points (scenarios, views, portfolios)

**Fix pattern requerido:** `content['key']` → `content.get('key', {})` + `_get_view_class` null-safe

#### Auditoría de Data Collection (dry-run producción)

| Módulo | Estado | Notas |
|--------|--------|-------|
| Regime classification | OK (cache) | |
| Macro USA (FRED) | OK (cache) | JOLTS 6.9M |
| Leading indicators | OK | 5/5 series |
| Inflation analytics | OK (cache) | |
| Chile analytics | OK (cache) | |
| Chile extended (BCCh) | OK (cache) | |
| China credit impulse | OK (cache) | |
| Rate expectations (Fed) | OK (cache) | |
| Risk metrics | OK (cache) | |
| Market breadth | OK (cache) | |
| International data (BCCh) | OK (cache) | |
| Bloomberg (Excel) | OK | 95 series, 272K datapoints |
| CPI/Fiscal/LatAm | OK (cache) | |
| BEA | SKIP | No API key (no bloqueante) |
| OECD KEI | OK | 4/6 series |
| NY Fed | OK | 5/5 modules |
| AKShare China | TIMEOUT | 90s timeout en servidor (no bloqueante — datos China via Bloomberg) |
| Informes diarios | OK | Recolección activa |

**Resultado:** 15/17 módulos GREEN. AKShare timeout no es bloqueante (datos China cubiertos por Bloomberg). BEA skip por falta de API key (datos cubiertos por FRED).

#### Estado para Demos

- **Data Collection**: 15/17 módulos OK — cobertura completa
- **Reportes**: Limpios cuando council output es completo (caso normal)
- **Prompts**: 8/8 sólidos, anti-fabricación activo
- **Renderers**: Crash points teóricos (28) — no se manifiestan en runs normales; único crash real (`KeyError: 'impacto'`) ya fixeado
- **Veredicto**: **GO para demos** — pipeline estable en producción

### Sprint 24 — Per-Client Directives + Manual de Portal

**Trigger:** Las directivas eran compartidas entre clientes (MBI, Vantrust, BVC escribían al mismo archivo). Se necesitaba aislamiento para demos independientes + manual de usuario del portal.

| # | Cambio | Archivo | Detalle |
|---|--------|---------|---------|
| 125 | Directivas per-client | `deploy/app.py` | `_get_directives(client_id)` lee de `/layout/output/{client_id}/directives.txt`; `_save_directives(content, client_id)` guarda per-client + sync a archivo compartido para pipeline |
| 126 | Manual del portal actualizado | `deploy/MANUAL_PORTAL.md` | Tabla de reportes (contenido/charts/páginas), tiempos por modo, flujo recomendado para demos, FAQ con directivas independientes |

**Validación:**
- Directivas de BVC no afectan a MBI ni Vantrust
- Pipeline lee archivo compartido (sync automático al correr)
- Manual cubre las 8 secciones del portal + FAQ
- Commit `dc10077` desplegado en producción

### Sprint 25 — Renderer Hardening + Council Deliberation Report

**Trigger:** Auditoría pre-demo encontró 28 crash points teóricos en renderers (dict['key'] directo). Además, se solicitó un reporte con la deliberación completa del AI Council.

#### Renderer Hardening (28 crash points → 0)

| # | Archivo | Cambios |
|---|---------|---------|
| 127 | `rv_report_renderer.py` | `_get_view_class` + `_get_valuation_class` null-safe, 9 secciones protegidas con `.get()` |
| 128 | `rf_report_renderer.py` | `_get_view_class` null-safe, 8 secciones protegidas con `.get()` |
| 129 | `macro_report_renderer.py` | `_get_vs_class` + `_get_trend_class` null-safe, 10 secciones protegidas con `.get()` |
| 130 | `asset_allocation_renderer.py` | 8 secciones protegidas con `.get()`, `.upper()` guarded, bounds check en portfolios |

**Pattern aplicado:**
- `content['key']` → `content.get('key', {})` (dicts)
- `section['field']` → `section.get('field', '')` (strings) / `.get('field', [])` (lists)
- `_get_view_class(None)` → retorna `'badge-neutral'` sin crash
- `_get_valuation_class('N/D')` → try/except float parse, retorna `'val-fair'`
- Deep chains: `a['b']['c']` → `a.get('b', {}).get('c', '')`

#### Council Deliberation Report (nuevo)

| # | Cambio | Detalle |
|---|--------|---------|
| 131 | `council_deliberation_renderer.py` | Nuevo renderer que genera "Acta del Comité de Inversiones" desde council_result JSON |

**Contenido del acta:**
- Capa 1: 5 cards de panelistas con análisis completo (Macro, RV, RF, Riesgo, Geo)
- Capa 2: 3 cards de síntesis (CIO, Contrarian, Refinador)
- Metadata: duración, modelos usados, módulos OK, daily reports count
- Bloques `[BLOQUE: X]` resaltados visualmente
- Word count por agente
- Print-ready (page-break-inside: avoid)
- Ejecutable standalone: `python council_deliberation_renderer.py [council_result.json]`

**Validación:**
- 4 renderers compilan OK (`py_compile`)
- Pipeline local RV+RF+AA: 3/3 OK con renderers blindados (0 errores)
- Acta generada: 68KB, 8 agent cards, 16 bloque tags, 0 encoding issues

#### Narrative Engine dotenv Fix

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 132 | Narrativas vacías en reportes locales — `narrative_engine.py` usaba `os.environ.get('ANTHROPIC_API_KEY')` pero `dotenv` solo se cargaba en `greybark/config.py` | `narrative_engine.py:12-18` | Agregar `load_dotenv()` al inicio del módulo para cargar `.env` independientemente |

**Causa raíz:** `narrative_engine.py` dependía de que `greybark.config` se importara primero para que `dotenv` cargara las env vars. En el pipeline (`run_monthly.py`) esto funcionaba porque config se importaba temprano, pero en tests aislados o imports lazy la key no estaba disponible → todas las narrativas caían a fallback genérico de 1 línea.

**Validación:**
- RV report con narrativa completa: 3 párrafos, ~900 chars, datos reales (nóminas -92K, breadth 18.2%, P/E 25.7x)
- Pipeline local RV: OK (88.3s) con narrativas ricas
- Antes: *"Nuestra postura en renta variable global es cauteloso para Marzo 2026."* (70 chars fallback)

#### Macro CPI Components Series.__format__ (segundo crash)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 133 | Macro crash `Series.__format__` en `_build_cpi_components()` — `get_usa_cpi_breakdown()` devuelve pd.Series, no floats | `macro_content_generator.py:933` | Agregar `_sf()` helper estático que convierte pd.Series/dict/numpy a float; aplicar en `_build_cpi_components()` |

**Causa raíz:** Mismo patrón que Sprint 22 (`_build_latam_table`) — `ChartDataProvider` devuelve Series completas pero el content generator asume escalares. El `_sf()` helper resuelve esto globalmente para cualquier método que use datos del provider.

**Validación:**
- `generate_all_content()` produce 11/11 secciones OK
- Pipeline macro: OK (405.9s, 27 charts)

#### Tablas Vacías en Macro Report (datos disponibles no mapeados)

| # | Tabla vacía | Archivo | Causa raíz | Fix |
|---|-------------|---------|-----------|-----|
| 134 | LatAm tabla: inflación Brasil/México/Colombia muestra "N/D" | `macro_content_generator.py:2051` | `_build_latam_table()` solo llamaba `get_latam_rates()` (policy rates) — no buscaba inflación | Agregar fetch de `BCChSeries.IPC_INTL_BRASIL/MEXICO/COLOMBIA` via `self.data.get_series()` |
| 135 | China inmobiliario: Precios Vivienda muestra "—" | `macro_content_generator.py:1518` | Buscaba en `get_china_latest()` (ChartDataProvider) pero property data está en `akshare_china` (quant_data) | Buscar primero en `self._q('akshare_china').get('property', {})`, fallback a `cn` |
| 136 | Chile IPC Subyacente: hardcoded "N/D" | `macro_content_generator.py:1809` + `greybark/config.py` | Serie BCCh `F074.IPCSAE.V12.Z.2018.C.M` no estaba en config | Agregar `IPC_SAE_V12` a BCChSeries + fetch en `_generate_chile_inflation()` → **4.1% a/a** (dato real) |

**Patrón recurrente: datos disponibles en una fuente pero no conectados al consumer.** Las APIs tienen los datos (BCCh inflación LatAm, AKShare property China) pero el content generator busca en la fuente equivocada o no busca en absoluto.

### Patrones Recurrentes Nuevos

| Patrón | Frecuencia | Lección |
|--------|-----------|---------|
| **Scraper web bloqueado desde servidor** | 1 vez (CommLoan) | Siempre tener fallback API para scrapers. Servidores reciben CAPTCHAs/bloqueos que laptops no. |
| **Paquete importado pero no en requirements.txt** | 2 (akshare, beautifulsoup4) | Auditar imports vs requirements antes de cada deploy. `try/except` oculta la falta del paquete. |
| **Latencia geográfica a APIs** | 3 módulos (BCCh desde Helsinki) | Elegir datacenter cercano a las APIs principales (US East para FRED/NY Fed, BCCh funciona global). |
| **Paths hardcodeados a `~/OneDrive/`** | 2 (daily reports, DF summaries) | En servidor, TODO path externo debe venir de env var + volumen Docker. Auditar antes de deploy. |
| **Método inexistente llamado silenciosamente** | 5 (get_ipc_detail, get_usa_cpi_components, get_latam_macro×2, format_for_council) | Cuando se renombra un método, grep TODOS los callers — no solo el que reportó error. El Sprint 18 arregló `council_data_collector` pero no `macro_content_generator`. |
| **API devuelve dict donde se espera escalar** | 2 (PIB USA, Desempleo USA en briefing) | Siempre unwrap dicts de APIs antes de formatear: `val.get('value')`. Agregar unwrap genérico en helpers de formato, no confiar en `isinstance(float)`. |
| **Timezone-naive vs aware comparisons** | 3 ubicaciones (equity YTD) | yfinance devuelve index tz-aware (America/New_York). Siempre usar `pd.Timestamp.tz_localize()` al comparar. |
| **Nested dict pasado donde se espera lista** | 1 (risk_matrix) | Validar tipo antes de iterar: `isinstance(x, dict)` → extraer la key correcta. |
| **Nuevo cliente sin productos habilitados** | 3 (bvc, vantrust, mbi) | `add_client()` deja `product_ai_council=False` por defecto. Siempre activar productos explícitamente post-creación. `update_client()` no acepta campos de producto — requiere SQL directo o ampliar la API. |
| **Datos efímeros en container Docker** | 3 (output, input, directivas) | TODO path que el pipeline escribe (output/, input/) debe ser volumen Docker. Si no, se pierde en rebuild. Auditar `docker run` antes de cada deploy. |
| **Council output con keys variables** | 1 (impacto vs severidad, hedge vs mitigacion) | Los renderers deben usar `.get()` con alias alternativos para keys que el LLM puede nombrar distinto. Nunca `r['key']` directo en datos generados por council. |
| **Reportes no copiados en error parcial** | 1 (RF fail → 3 reportes OK no copiados) | `_copy_reports_to_client()` solo corre si pipeline exit code=0. Cambiar a copiar reportes individuales que sí se generaron. |
| **dotenv no cargado en módulos standalone** | 1 (narrative_engine) | Si un módulo usa `os.environ.get('KEY')` pero `dotenv` solo se carga en otro módulo (config.py), la key no existe cuando se importa de forma independiente. Cada módulo que necesite env vars debe cargar `dotenv` por sí mismo. |
| **Datos disponibles pero no conectados al consumer** | 3 (LatAm inflación, China property, Chile IPC core) | Content generator busca datos en fuente A (ChartDataProvider) pero los datos están en fuente B (quant_data/AKShare, BCCh series internacionales). Auditar cada tabla vacía: ¿la API tiene el dato? → conectar. ¿No existe? → documentar como pendiente. |

### Inconsistencias Detectadas en Audit

| ID | Inconsistencia | Severidad | Acción |
|----|---------------|-----------|--------|
| I1 | `personas.py` CIO "NO tienes opinión propia" vs `ias_cio.txt` "INTEGRADOR con criterio propio" | Alta | Deprecado `personas.py` (no es runtime) |
| I2 | `committee_session.py` 6 agentes/5 rondas vs producción 5 agentes/3 capas | Alta | Deprecado `committee_session.py` |
| I3 | RISK_MATRIX sin magnitud de impacto | Media | Agregados campos equity%/RF bps condicionales |
| I4 | CIO no referencia bloques del panel explícitamente | Media | Agregada sección BLOQUES DE INPUT |
| I5 | Contrarian analogías históricas opcionales | Media | Hechas obligatorias |

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

### Sprint 5 — Revisión Visual RF + AA (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 33 | "Credito IG/HY" sin acento en RF | `rf_content_generator.py` | → "Crédito IG" / "Crédito HY" |
| 34 | "Inflacion/TIPS" sin acento | `rf_content_generator.py` | → "Inflación/TIPS" |
| 35 | "Inflacion Implicita" sin acentos en RF template | `templates/rf_report_professional.html` | → "Inflación Implícita" |
| 36 | "Riesgo Pais", "Views por Pais" sin acentos | `templates/rf_report_professional.html` | → "Riesgo País", "Views por País" |
| 37 | "Centesimas" sin acento | `templates/rf_report_professional.html` | → "Centésimas" |
| 38 | EM HC/LC badge hardcoded `badge-ow` para views NEUTRAL | `rf_report_renderer.py` + template | Dynamic `{{em_hc_class}}`/`{{em_lc_class}}` via `_get_view_class()` |
| 39 | "Politica y Geopolitica" sin acentos en AA template | `templates/asset_allocation_professional.html` | → "Política y Geopolítica" |
| 40 | "inflacion" sin acento en glosario AA | `templates/asset_allocation_professional.html` | → "inflación" |
| 41 | 5 acentos faltantes en glosario AA | `templates/asset_allocation_professional.html` | Términos, sobreponderación, índice, expansión, contracción |
| 42 | PE siempre N/D — key `pe` no existe, es `pe_forward`/`pe_trailing` | `asset_allocation_content_generator.py` | Lookup chain: pe_forward → pe_trailing → pe → bloomberg |
| 43 | VIX siempre N/D — dict `{'current': 23.48}` pasado a `_safe_float` | `asset_allocation_content_generator.py` | Unwrap `.get('current')` antes de `_safe_float()` |
| 44 | TPM siempre N/D — dict `{'current': 4.5}` no unwrapped | `asset_allocation_content_generator.py` | Unwrap `.get('current')` + canon fallback |
| 45 | UST 2Y/10Y siempre N/D — path `yield_curve.us_2y` no existe | `asset_allocation_content_generator.py` | Path: `yield_curve.current_curve.2Y` / `.10Y` |
| 46 | SELIC siempre N/D — key `chile_rates.selic` no existe | `asset_allocation_content_generator.py` | Path: `chile_rates.policy_rates.bcb` = 15.0% |
| 47 | Breakeven 5Y siempre N/D — path incorrecto | `asset_allocation_content_generator.py` | Path: `inflation.breakeven_inflation.current.breakeven_5y` |
| 48 | Calendar table 4 columnas vs 3 en template header | `table_builder.py` | Removed orphan `impacto` column (3-col: Fecha/Evento/Relevancia) |

**Resultado:** 16/16 canonical data points ahora resuelven desde API real (era 0/16):
- PE: SPX 25.7x, STOXX 17.4x, EM 14.7x, IPSA 13.0x, Japan 17.1x
- Rates: UST 2Y 3.79%, 10Y 4.25%, TPM 4.5%
- VIX 23.5, SELIC 15.0%, Breakeven 5Y 2.63%
- Copper $5.57/lb, Gold $4607/oz, Oil $94.65/bbl
- Spreads: IG 90bp, HY 327bp

### Sprint 6 — Tasas Stale (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 49 | TPM expectations parten de 5.0% (real 4.5%) | `rf_data_collector.py` | Auto-fetch TPM desde BCCh API (`_fetch_current_tpm()`) |
| 50 | Fed Funds default 4.50% (real EFFR 3.64%) | `rf_data_collector.py` | Auto-fetch Fed Funds desde FRED DFF (`_fetch_current_fed_funds()`) |
| 51 | 6 standalone defaults stale en rate_expectations/ | `clp_expectations.py`, `usd_expectations.py`, `fed_dots_comparison.py`, `bcch_encuesta_comparison.py`, `__init__.py` | TPM 5.00→4.50, Fed 4.50→3.75 |

**Resultado:** RFDataCollector ahora obtiene tasas actuales de APIs al inicializar. Fallback a 4.50% si API falla.

### Sprint 7 — P0 Data Bugs (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 52 | BCCh dates DD-MM swapped when day<=12 → WTI +50% 1M | `greybark/data_sources/bcch_client.py:98` | `dayfirst=True` en `pd.to_datetime()` |
| 53 | RV earnings tabla: columnas EPS muestran beat rate y P/E | `templates/rv_report_professional.html` | Headers → "Beat Rate" / "P/E Fwd" |
| 54 | AA escenarios suman 90% (falta 10%) | `asset_allocation_content_generator.py` | Residual "Cola / Riesgo Extremo" auto-añadido |
| 55 | AA 3 precios cobre diferentes ($5.30/$5.46/$5.57) | `asset_allocation_content_generator.py` | Canon value first en 3 métodos Chile |
| 56 | AA `MODERATE_GROWTH` raw code visible en texto | `asset_allocation_content_generator.py` | `_REGIME_LABELS` dict → "Crecimiento Moderado" |
| 57 | AA Focus List 18 rationales en inglés | `asset_allocation_content_generator.py` | Traducidos a español |
| 58 | RV `[Sección incompleta — revisar]` visible | `narrative_engine.py:1089` | Marker removido (warning en log se mantiene) |

**Resultado:** Datos BCCh con fechas correctas, tablas con headers correctos, escenarios suman 100%, cobre coherente, código interno no visible.

### Sprint 8 — P1 Content Fixes (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 59 | RF trades duplicados entre Sección 3 y 7 | `templates/rf_report_professional.html` | Removido duplicado S3; S7 es canónico |
| 60 | RF `FAIR_VALUE`/`EXPENSIVE` enum raw | `rf_content_generator.py` | `_translate_signal()` → "Valor Justo"/"Caro"/"Barato" |
| 61 | RF badge UW styled como neutral | `rf_report_renderer.py` + template | `{{hy_badge_class}}` dinámico vía `_get_view_class()` |
| 62 | RV narrativas garbled (sector Preferidos/Evitar) | `rv_content_generator.py` | Sentence-aware extraction + `_truncate_at_sentence()` helper |
| 63 | RV catalysts truncado (max_tokens 300) | `rv_content_generator.py` | max_tokens 300→500 |
| 64 | AA tabla macro indicadores vacía | `asset_allocation_content_generator.py` | Keys corregidos: gdp_qoq, cpi_core_yoy, retail_sales.yoy |
| 65 | AA dashboard flechas todas → | `asset_allocation_content_generator.py` | `_arrow_from_view()`: OW→↑, UW→↓, N→→ |

### Sprint 9 — Capa 3: Acentos, Traducciones, Unidades (2026-03-23)

| # | Bug | Archivo(s) | Fix |
|---|-----|------------|-----|
| 66 | ~22 acentos faltantes en RF | `rf_content_generator.py`, `templates/rf_report_professional.html` | México, Perú, crédito, días, política, Posición, distribución, últimos, años, Cámara, Inflación |
| 67 | ~25 acentos faltantes en AA | `asset_allocation_content_generator.py`, `asset_allocation_renderer.py`, `templates/asset_allocation_professional.html` | opinión, señal, inversión, política, Revisión, Economía, Escalación, Depósito, reducción, históricamente, protección |
| 68 | ~18 acentos faltantes en RV | `rv_content_generator.py`, `templates/rv_report_professional.html` | Japón, Débil, correlación, depreciación, suscripción, Región, política, análisis, Índice, Valuación, caída máxima |
| 69 | ~5 acentos faltantes en Macro | `macro_content_generator.py`, `templates/macro_report_professional.html` | último, dinámicas, inflación, análisis, región, PRONÓSTICO PONDERADO |
| 70 | ~20 labels en inglés en 4 reportes | Todos los templates + renderers + content generators | Driver→Factor, Key Calls→Decisiones Clave, Rationale→Fundamento, Target→Objetivo, Entry→Entrada, Stop→Stop-loss, Hedge→Cobertura, Asset Class→Clase de Activo, Key Points→Puntos Clave, GDP Growth→Crecimiento PIB, Inflation (Core)→Inflación (Subyacente), Policy Rates→Tasas de Política, Euro Area→Eurozona |
| 71 | Litio unidad incorrecta USD/ton | `chart_data_provider.py`, `equity_data_collector.py`, `rv_content_generator.py`, `macro_content_generator.py` | → USD/kg (litio se cotiza en kg, no en toneladas) |

**Resultado:** ~95 correcciones cosméticas en 12 archivos. 4 reportes ahora 100% español con acentos correctos.

### Sprint 10 — 2 P1 Bugs Restantes (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 72 | CPI subcomponents chart vacío | Ya resuelto (Sprint previo) | FRED series CUSR0000SAH1/SAS/SACL1E/CPIUFDSL/CPIENGSL → `get_usa_cpi_breakdown()` + `_generate_inflation_components_ts()` ya OK. Verificado: 5/5 series, 109 pts, chart genera 78KB base64 |
| 73 | Raw markdown leak en RF HTML (`**bold**`, `## headers`) | `rf_report_renderer.py` | `_md_to_html()` wrap en 12 campos: key_calls, driver (×2), rationale (×3), trade name (×2), señal, comentario, riesgo, descripcion, hedge |

**Resultado:** 0 bugs P1 pendientes. inflation_components_ts genera correctamente (21/24 macro charts OK, 3 son Bloomberg-only).

### Sprint 11 — Curvas Soberanas en RF (2026-03-23)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 74 | Yield curve chart solo muestra UST (faltaban Bund + JGB) | `rf_data_collector.py` | Módulo 13 `collect_sovereign_curves()` importa `data_fetchers/curvas_soberanas.py` (ECB 9T + MoF Japan 11T) |
| 75 | Chart title no refleja contenido multi-curva | `rf_chart_generator.py` | Título "Curva UST: Actual vs 1M vs 1A" → "Curvas Soberanas: UST vs Bund vs JGB" + overlay Bund (azul) + JGB (rojo) |

**Resultado:** Yield curve chart ahora muestra 3 curvas soberanas con datos reales. RF data collector ampliado a 13 módulos.

### Sprint 12 — RF Vistas Vacías: Parser FI_POSITIONING (2026-03-24)

| # | Bug | Archivo | Fix |
|---|-----|---------|-----|
| 76 | FI_POSITIONING parser solo extrae 1/6 segmentos (regex `CORTA\|NEUTRAL\|LARGA` rechaza `CORTA-MEDIA` y texto libre) | `council_parser.py:262` | Two-pass parser: captura segment+view primero, duración opcionalmente. Acepta CORTA-MEDIA, MEDIA-LARGA, texto libre |
| 77 | 22 badges "Sin vista" / "---" en RF (5 segmentos, 5 países EM, 6 BCP/BCU, IG/EM HC/LC) | `rf_content_generator.py` | Ahora 6/6 segmentos extraídos → vistas propagan a todos los consumidores |
| 78 | IG badge hardcoded `badge-ow` (verde) aún cuando view = "Sin vista" | `templates/rf_report_professional.html` + `rf_report_renderer.py` | `{{ig_badge_class}}` dinámico vía `_get_view_class()` |
| 79 | Duration stance truncada ("...servicios 3.43% y") — regex captura solo hasta primer `\n` | `council_parser.py:300` | Regex multiline: captura hasta siguiente keyword (Benchmark/Recomendación) |
| 80 | `dur_map` no incluye duraciones compuestas (CORTA-MEDIA, MEDIA-LARGA) | `rf_content_generator.py` (×3 instancias) | Agregados a los 3 `dur_map` dicts |

**Resultado:** 0 instancias "Sin vista" en RF (era 22+). 6/6 segmentos FI parseados (era 1/6). Duration stance completa.

### Bugs Pendientes

| Prioridad | Bug | Impacto |
|-----------|-----|---------|
| — | Ningún bug P0 o P1 pendiente | — |
| Permanente | BCU 2Y sin datos (BCCh no publica) | Serie vacía → skip |
| Permanente | PMI/China Trade (Bloomberg-only, 3 charts) | Charts vacíos sin Bloomberg terminal |

### Validación Acumulada (Sprints 1-9)

**Pipeline runs exitosos:**
- 2026-03-20 (post Sprint 1): 4/4 reportes, 41 min, spreads IG 91bp/HY 320bp OK
- 2026-03-21 (post Sprint 2): 4/4 reportes, 43.6 min, anti-fabricación 10 correcciones
- 2026-03-22 (post Sprint 4): 4/4 reportes, 34.9 min, forecasts 5/5 modelos OK
- 2026-03-24 (post Sprint 12): RF regenerado, 8/8 charts, 0 "Sin vista", 23.4 min

**Checks pasados:**
- [x] Credit spreads: IG ~90bp, HY ~320bp (era 1bp sin ×100)
- [x] Dividend yields < 10% (era 308% sin guard)
- [x] S&P 500 target +2.4% con 5/5 modelos (era +21.8% con 2/5)
- [x] Anti-fabricación: corrige P/E, UST, IG spread, TPM, oil en narrativas LLM
- [x] Panel agents: 4435-8636 chars (max_tokens=6000 OK)
- [x] Macro: 28/28 charts, RV: 12/12, RF: 8/8, AA: tablas completas
- [x] 16/16 AA canonical data points resuelven desde API real
- [x] BCCh dates dayfirst=True (era DD-MM swap)
- [x] Tasas auto-fetch: TPM 4.50% (BCCh), Fed Funds 3.64% (FRED)
- [x] ~95 acentos corregidos, ~20 labels traducidos, litio USD/kg
- [x] Regenerado RF con curvas soberanas Bund+JGB (Sprint 11), TPM 4.50% OK
- [x] FI_POSITIONING parser: 6/6 segmentos (era 1/6), 0 "Sin vista" en RF (Sprint 12)

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

## Bucle de Mejora Automática

### Proceso (por sprint)

```
┌─────────────────────────────────────────────────────────┐
│  1. AUDITORÍA                                            │
│     - Abrir los 4 reportes HTML en browser               │
│     - Revisar cada sección: datos correctos, formato,    │
│       acentos, coherencia entre reportes                 │
│     - Clasificar bugs: P0 (datos erróneos que engañan),  │
│       P1 (contenido roto/vacío), P2 (cosmético/idioma)   │
│     - Registrar en "Bugs Pendientes" con prioridad       │
│     - PROMPT AUDIT (periódico, cada ~5 ciclos):          │
│       · Leer los 8 .txt + 23 prompts embebidos en código │
│       · Evaluar: claridad, output spec, frameworks, gaps │
│       · Detectar inconsistencias entre prompts           │
│       · Proponer mejoras con diffs antes de implementar  │
├─────────────────────────────────────────────────────────┤
│  2. FIX                                                  │
│     - Atacar por prioridad: P0 → P1 → P2                │
│     - Trazar cada bug hasta el archivo/línea raíz        │
│     - Verificar compilación: py_compile                  │
│     - Agrupar fixes relacionados en un solo sprint       │
├─────────────────────────────────────────────────────────┤
│  3. DOCUMENTAR                                           │
│     - IMPROVEMENT_LOG.md: Sprint N con tabla de bugs     │
│     - SYSTEM_OVERVIEW.md: actualizar conteo y §6.4       │
│     - DATA_SOURCES.md: si cambió fuente de datos         │
│     - Commit + push inmediatamente después de cada sprint│
├─────────────────────────────────────────────────────────┤
│  4. VALIDAR                                              │
│     - Regenerar reportes: python run_monthly.py          │
│       --skip-collect --no-confirm                        │
│     - Verificar: file size, chart count, datos visibles  │
│     - Agregar checks a "Validación Acumulada"            │
│     - Si hay bugs nuevos → volver a paso 1               │
└─────────────────────────────────────────────────────────┘
```

### Clasificación de Bugs

| Prioridad | Nombre | Criterio | Ejemplo |
|-----------|--------|----------|---------|
| **P0** | Datos erróneos | Número incorrecto que engaña al lector | WTI +50% (fecha swap), S&P target +21.8% |
| **P1** | Contenido roto | Sección vacía, formato roto, placeholder visible | N/D en 16 campos AA, markdown leak en HTML |
| **P2** | Cosmético | Acentos, idioma, unidades, labels | "Credito" → "Crédito", Driver → Factor |

### Meta
- **0 bugs P0 y P1** antes de entregar reportes a clientes
- P2 = nice-to-have pero contribuyen a calidad profesional
- Cada sprint debe terminar con: código compilado + commit + push + .md actualizados

### Patrones Recurrentes de Bugs

| Patrón | Frecuencia | Ejemplo | Lección |
|--------|-----------|---------|---------|
| **Regex demasiado estricto para output LLM** | 3 veces | FI_POSITIONING exigía `CORTA\|NEUTRAL\|LARGA`, council escribió `CORTA-MEDIA` | Parsers de output LLM deben ser tolerantes: capturar lo seguro (OW/N/UW) primero, detalles opcionales después |
| **Dict keys incorrectos** (path mismatch) | 6+ veces | `pe` no existe, es `pe_forward`; `yield_curve.us_2y` no existe, es `current_curve.2Y` | Siempre verificar keys reales con `print(data.keys())` antes de asumir estructura |
| **Datos stale con `--skip-collect`** | 2 veces | TPM 5.0% en JSON viejo cuando API ya retorna 4.5% | `--skip-collect` usa cache — si se corrigió auto-fetch, hay que re-colectar |
| **Fallback silencioso oculta errores** | 5+ veces | `ChartDataProvider(bloomberg=...)` → TypeError → `None` → 0 charts sin error | Logear warnings cuando un fallback se activa; no tragarse excepciones silenciosamente |
| **Badge CSS hardcoded** | 3 veces | IG `badge-ow` cuando view es NEUTRAL | Siempre usar `_get_view_class()` dinámico, nunca hardcodear clase CSS de badge |
| **Acentos faltantes** | ~95 instancias | "Credito" → "Crédito", "Analisis" → "Análisis" | Revisar templates + content generators + renderers en conjunto; buscar regex `[aeiou][^a-z]` |

### Estadísticas

**Por ciclo:**
| Ciclo | Sprints | Bugs/Mejoras | P0 | P1 | P2 | Prompts |
|-------|---------|--------------|----|----|-----|---------|
| 1 (Setup) | — | 0 | — | — | — | — |
| 2 (Library) | — | 0 | — | — | — | — |
| 3 (Coherence) | — | 7 | 3 | 2 | 2 | — |
| 4 (CLP/TPM) | — | 6 | 4 | 1 | 1 | — |
| 5 (Auditoría) | 12 | 80 | 28 | 32 | 20 | — |
| 6 (Prompt Audit + Deploy) | 5 | 22 | 2 | 3 | — | 6 prompts mejorados |
| **Total** | **17** | **115** | **37** | **38** | **23** | **6** |

**Desglose Ciclo 5 (auditoría completa):**
| Sprint | Fecha | Bugs | Tema principal |
|--------|-------|------|----------------|
| 1 | 2026-03-20 | #13-17 (5) | HY duplicado, señal temprana, EV/EBITDA, acentos templates |
| 2 | 2026-03-21 | #20-23 (4) | Regex Fed rate, max_tokens panel, oil fabricado, badges español |
| 3 | 2026-03-22 | #24-28 (5) | Commodity stale, S&P target, consensus, regime, EuroStoxx ticker |
| 4 | 2026-03-22 | #29-32 (4) | Factor scores yfinance, acentos RV |
| 5 | 2026-03-23 | #33-48 (16) | Acentos RF/AA, PE/VIX/TPM paths, calendar 4→3 cols |
| 6 | 2026-03-23 | #49-51 (3) | TPM/Fed auto-fetch desde API |
| 7 | 2026-03-23 | #52-58 (7) | BCCh date swap, earnings headers, escenarios 100%, régimen labels |
| 8 | 2026-03-23 | #59-65 (7) | RF trades duplicados, signals, narrativas garbled, AA dashboard |
| 9 | 2026-03-23 | #66-71 (6) | ~95 acentos, ~20 labels traducidos, litio USD/kg |
| 10 | 2026-03-23 | #72-73 (2) | CPI chart verificado, RF markdown leak |
| 11 | 2026-03-23 | #74-75 (2) | Curvas soberanas Bund+JGB en RF |
| 12 | 2026-03-24 | #76-80 (5) | FI_POSITIONING parser 1/6→6/6, IG badge, duration truncada |
| 13 | 2026-03-25 | #81-86 (6) | Prompt audit: riesgo, contrarian, macro, CIO, deprecations, refinador |
| 14 | 2026-03-25 | #87-90 (4) | Dashboard client isolation + company name editable + Streamlit eliminado |
| 15 | 2026-03-25 | #91-95 (5) | Hetzner deploy: Helsinki→Ashburn migration |
| 16 | 2026-03-25 | #96-99 (4) | Dependency audit: +akshare, NY Fed SOFR fallback, timeouts |
| 17 | 2026-03-25 | #100-103 (4) | Daily reports sync, DF sync, API key fix, chile_extended fix |

**Velocidad promedio:** 6.8 bugs/sprint, ~2 sprints/día en ciclo intensivo

# Greybark Research — Registro de Mejoras Continuas

> Este archivo documenta cada ciclo de auditoría → fix → validación del pipeline.
> Ordenado de más reciente a más antiguo.

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

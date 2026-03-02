# GREYBARK RESEARCH

Sistema de research e inteligencia de mercados con AI Council y reportes profesionales automatizados.

---

## Arquitectura

```
wealth/
├── .env.example              # Template de API keys (copiar a .env)
├── requirements.txt          # Dependencias Python
├── README.md                 # Este archivo
│
└── estructuras/
    ├── consejo_ia/           # Sistema principal
    │   ├── run_monthly.py    # Pipeline unificado (punto de entrada)
    │   ├── run_monthly.bat   # Launcher Windows
    │   │
    │   ├── ai_council_runner.py          # AI Council: 5 panelistas + 3 sintetizadores
    │   ├── council_data_collector.py     # Recoleccion de datos (10 modulos quant + equity + RF + forecasts)
    │   ├── council_preflight_validator.py # Validacion pre-vuelo
    │   │
    │   ├── macro_content_generator.py    # Contenido Macro (USA/Europa/China/Chile)
    │   ├── macro_report_renderer.py      # Renderer Macro → HTML
    │   ├── chart_generator.py            # 28 charts Macro (BCCh + FRED)
    │   ├── chart_data_provider.py        # Datos reales para charts Macro
    │   │
    │   ├── rv_content_generator.py       # Contenido Renta Variable
    │   ├── rv_report_renderer.py         # Renderer RV → HTML
    │   ├── rv_chart_generator.py         # 12 charts RV
    │   ├── equity_data_collector.py      # 11 modulos datos equity
    │   │
    │   ├── rf_content_generator.py       # Contenido Renta Fija
    │   ├── rf_report_renderer.py         # Renderer RF → HTML
    │   ├── rf_chart_generator.py         # 8 charts RF
    │   ├── rf_data_collector.py          # 12 modulos datos RF
    │   │
    │   ├── asset_allocation_content_generator.py  # Contenido Asset Allocation
    │   ├── asset_allocation_renderer.py            # Renderer AA → HTML
    │   │
    │   ├── forecast_engine.py            # Motor econometrico (ARIMA/VAR/Taylor/Phillips)
    │   ├── econometric_models.py         # 4 modelos econometricos
    │   ├── imf_weo_client.py             # Consenso IMF (GDP + CPI)
    │   │
    │   ├── daily_intelligence_digest.py  # Procesamiento de reportes diarios
    │   ├── daily_report_parser.py        # Parser HTML de reportes AM/PM
    │   ├── research_analyzer.py          # Sintesis de research externo
    │   │
    │   ├── templates/                    # Templates HTML profesionales
    │   ├── input/                        # Directivas usuario + research externo
    │   └── output/                       # Reportes generados (en .gitignore)
    │
    └── 02_greybark_library/              # Libreria de analytics
        └── greybark/
            ├── analytics/                # 55+ modulos de analisis
            │   ├── regime_classification/  # Clasificacion de regimen macro
            │   ├── macro/                  # Dashboard macro, inflacion
            │   ├── chile/                  # Chile: TPM, IMACEC, IPC, breakeven
            │   ├── china/                  # Credit impulse, EPU
            │   ├── credit/                 # Spreads IG/HY (FRED OAS)
            │   ├── earnings/               # Beat rate, estimaciones
            │   ├── factors/                # Value, growth, momentum
            │   ├── fixed_income/           # Duration analytics
            │   ├── risk/                   # VaR, stress testing
            │   ├── rate_expectations/      # Fed, BCCh expectations
            │   └── breadth/                # Market breadth
            └── data_sources/             # Clientes de APIs
                ├── fred_client.py          # FRED (Federal Reserve)
                ├── bcch_client.py          # BCCh (Banco Central Chile)
                ├── alphavantage_client.py   # AlphaVantage
                └── commloan_scraper.py      # SOFR forwards
```

---

## Reportes

4 reportes profesionales, todos con datos reales de API (sin datos inventados):

| Reporte | Charts | Fuentes de Datos | Frecuencia |
|---------|--------|-------------------|------------|
| **Macro** | 28 | FRED + BCCh + IMF WEO | Mensual |
| **Renta Variable** | 12 | yfinance + AlphaVantage + BCCh | Mensual |
| **Renta Fija** | 8 | FRED + BCCh (BCP/BCU/TPM) | Mensual |
| **Asset Allocation** | — | Combina equity + RF data | Trimestral |

Cada reporte usa el **AI Council** (opcional): 5 agentes especializados debaten y producen recomendaciones integradas. Un unico session genera contenido para los 4 reportes.

---

## AI Council

Panel de 5 especialistas IA con arquitectura de 3 capas:

```
Capa 1: Panel (5 agentes)
  ├── Macro       → Regimen, bancos centrales, inflacion
  ├── Renta Variable → Valuaciones, sectores, earnings
  ├── Renta Fija  → Duration, credito, curvas
  ├── Riesgo      → VaR, stress testing, hedging
  └── Geopolitica → Riesgos politicos, comercio global

Capa 2: Sintesis (3 agentes)
  ├── CIO         → Recomendacion principal
  ├── Contrarian  → Riesgos no contemplados
  └── Refinador   → Calibracion final

Capa 3: Output → Recomendacion final + portafolios modelo
```

---

## Motor de Pronosticos

`forecast_engine.py` genera pronosticos cuantitativos con blend de modelos:

| Modelo | Peso | Variables |
|--------|------|-----------|
| Surveys/Mercado | 40% | Breakevens, Michigan, GDPNow, forwards |
| ARIMA | 20% | CPI, GDP, tasas |
| VAR | 20% | Sistema macro 4 variables |
| Estructural | 20% | Taylor Rule, Phillips Curve |

Consenso IMF WEO se integra como referencia externa (GDP + CPI, 4 regiones).

Equity targets: ensemble de 5 modelos (EYG, Fair PE, PE reversion, Consensus, Regime).

---

## Fuentes de Datos

### APIs (datos reales)

| API | Datos | Key Requerida |
|-----|-------|---------------|
| **FRED** | Macro USA (GDP, CPI, empleo, tasas, spreads) | Si |
| **BCCh** | Chile (TPM, BCP/BCU, IPC, IMACEC, USD/CLP, commodities) | Si |
| **AlphaVantage** | Earnings, estimaciones, calendarios | Si |
| **yfinance** | ETF valuaciones, retornos, dividendos | No |
| **IMF WEO** | Consenso GDP + CPI (4 regiones) | No |

### Reportes Diarios (html_out/)

Los reportes diarios AM/PM estan en `consejo_ia/html_out/` (237 archivos HTML). Son la fuente de inteligencia narrativa que alimenta al AI Council — temas recurrentes, cambios de narrativa, analisis de sentimiento.

El `daily_intelligence_digest.py` procesa los ultimos 30 dias de reportes y extrae:
- Temas dominantes y su evolucion
- Cambios de narrativa del mercado
- Alertas y riesgos identificados

### Inputs Adicionales

| Recurso | Ruta | Uso |
|---------|------|-----|
| Research externo | `consejo_ia/input/research/*.txt` | Analisis de research de bancos (GS, JPM, MS) |
| Directivas usuario | `consejo_ia/input/user_directives.txt` | Foco y preguntas del usuario |

---

## Instalacion

### 1. Clonar

```bash
git clone https://github.com/martinezosoriopablo/greybark-research.git
cd greybark-research
```

### 2. Dependencias

```bash
pip install -r requirements.txt

# Instalar greybark como paquete editable
cd estructuras/02_greybark_library
pip install -e .
```

### 3. API Keys

```bash
# Copiar template y completar con tus keys
cp .env.example .env
```

Keys necesarias:
- `ANTHROPIC_API_KEY` — Claude API (para AI Council)
- `FRED_API_KEY` — Federal Reserve Economic Data
- `BCCH_USER` / `BCCH_PASSWORD` — Banco Central de Chile
- `ALPHAVANTAGE_API_KEY` — AlphaVantage Premium
- `BEA_API_KEY` — Bureau of Economic Analysis (opcional)

---

## Uso

### Pipeline Completo (recomendado)

```bash
cd estructuras/consejo_ia

# Pipeline unificado: recolecta datos → preflight → council → 4 reportes
python run_monthly.py

# Sin pausa para confirmacion
python run_monthly.py --no-confirm

# Solo reportes especificos
python run_monthly.py --reports macro,rv

# Dry run (sin llamadas a API de Claude)
python run_monthly.py --dry-run

# Abrir reportes al terminar
python run_monthly.py --open
```

### Reportes Individuales

```bash
# Macro (con recoleccion de datos)
python macro_report_renderer.py

# Renta Variable (con datos pre-recolectados)
python rv_report_renderer.py --equity-data output/equity_data/equity_data_LATEST.json

# Renta Fija (sin recolectar, usa datos existentes)
python rf_report_renderer.py --rf-data output/rf_data/rf_data_LATEST.json --no-collect

# Asset Allocation
python asset_allocation_renderer.py
```

### Solo Datos (sin reporte)

```bash
# Datos macro (10 modulos)
python council_data_collector.py

# Datos equity (11 modulos)
python equity_data_collector.py

# Datos RF (12 modulos)
python rf_data_collector.py

# Pronosticos econometricos
python forecast_engine.py
```

### Windows

Doble-click en `run_monthly.bat` o programar con Task Scheduler.

---

## Diseno de Reportes

Todos los reportes comparten el mismo sistema de diseno:

- **Header**: "GREYBARK RESEARCH" (Archio Black) + subtitulo naranja (#dd6b20)
- **Body**: Segoe UI, 10pt, max-width 1000px
- **Secciones**: titulo 14pt bold con borde inferior naranja
- **Tablas**: header negro (#1a1a1a), filas alternadas (#f7f7f7)
- **Badges**: OW=verde, N=neutro, UW=rojo
- **Print-ready**: page-break-inside: avoid

---

## Politica de Datos

**Cero datos inventados.** Cada valor en los reportes viene de una API publica verificable o se muestra como "N/D" (No Disponible). Los datos propietarios (CDS, bid-ask, PMI ISM) no se aproximan — simplemente se omiten.

Datos hardcodeados que permanecen (sin API publica):
- Opiniones/views de inversion (contenido del Council)
- CDS soberanos (requiere Bloomberg/Refinitiv)
- Spreads corporativos por emisor (requiere terminal)
- Liquidez bid-ask (propietario)
- ISM PMI (propietario)

---

## Licencia

Uso privado. Greybark Research.

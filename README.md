# Greybark Research - Sistema de Reportes de Inversion
## Version 4.1 | Marzo 2026

> **Nota**: Este modulo es parte del sistema Greybark Research.
> Para documentacion completa del proyecto, ver el [README principal](../README.md).

## Descripcion General

Sistema automatizado de generacion de reportes de inversion para Greybark Research.
Genera reportes profesionales estilo Goldman Sachs / JPMorgan para clientes institucionales.
Incluye integracion opcional con el AI Council (panel de 5 especialistas IA).

---

## Arquitectura del Sistema

```
consejo_ia/
│
├── run_monthly.py              # Pipeline mensual unificado (5 fases)
│
├── MOTOR DE PRONOSTICOS (Forecast Engine)
│   ├── forecast_engine.py               # 2-capa: Surveys + Econometrico
│   └── econometric_models.py            # ARIMA, VAR, Taylor Rule, Phillips Curve
│
├── RECOPILACION DE DATOS (Data Collectors)
│   ├── council_data_collector.py         # 10 modulos macro cuantitativos
│   ├── equity_data_collector.py          # 10 modulos equity (yfinance/AV/BCCh)
│   ├── rf_data_collector.py              # 13 modulos renta fija (FRED/BCCh/ECB/MoF)
│   ├── daily_intelligence_digest.py      # Digesto de reportes diarios (30d)
│   └── research_analyzer.py              # Sintesis research externo (LLM)
│
├── GENERADORES DE CONTENIDO (Content Generators)
│   ├── macro_content_generator.py        # Contenido Macro (acepta forecast_data)
│   ├── asset_allocation_content_generator.py  # Contenido AA (acepta forecast_data)
│   ├── rv_content_generator.py           # Contenido RV (acepta forecast_data)
│   └── rf_content_generator.py           # Contenido RF (acepta forecast_data)
│
├── RENDERIZADORES (Renderers)
│   ├── macro_report_renderer.py          # Renderiza Macro a HTML
│   ├── asset_allocation_renderer.py      # Renderiza AA a HTML
│   ├── rv_report_renderer.py             # Renderiza RV a HTML
│   └── rf_report_renderer.py             # Renderiza RF a HTML
│
├── CHARTS Y DATOS REALES
│   ├── chart_data_provider.py            # Capa datos reales (BCCh + FRED)
│   └── chart_generator.py               # Generador de charts matplotlib
│
├── AI COUNCIL
│   ├── ai_council_runner.py              # 3 capas: Panel (5) → Sintesis (3) → Output
│   ├── council_preflight_validator.py    # Pre-flight checks GO/CAUTION/NO_GO
│   └── daily_report_parser.py            # Parser reportes diarios HTML
│
├── TEMPLATES HTML
│   └── templates/
│       ├── macro_report_professional.html
│       ├── asset_allocation_professional.html
│       ├── rv_report_professional.html
│       └── rf_report_professional.html
│
├── INPUT
│   ├── input/user_directives.txt         # Directivas del usuario
│   └── input/research/*.txt              # Extractos research bancos
│
├── DOCUMENTACION
│   ├── README.md                         # Este archivo
│   └── DATA_SOURCES.md                   # Documentacion de todas las fuentes de datos
│
└── OUTPUT
    └── output/
        ├── reports/                      # Reportes HTML generados
        ├── council/                      # Resultados del AI Council
        ├── forecasts/                    # Pronosticos del Forecast Engine
        ├── equity_data/                  # Datos equity recopilados
        └── rf_data/                      # Datos renta fija recopilados
```

---

## Tipos de Reportes

| Reporte | Frecuencia | Contenido |
|---------|------------|-----------|
| **Macro** | Mensual | Perspectivas economicas globales (USA, Europa, China, Chile) |
| **Asset Allocation** | Trimestral | Posicionamiento estrategico por asset class y region |
| **Renta Variable** | Mensual | Equity strategy, sectores, valuaciones, top picks |
| **Renta Fija** | Mensual | Fixed income, duration, credito, curvas, Chile RF |

---

## Uso del Sistema

### Comandos Principales

```bash
# Pipeline completo (recopila datos + council + 4 reportes)
python run_monthly.py

# Solo reportes especificos
python run_monthly.py --reports macro rv

# Sin recopilacion de datos (usa datos previos)
python run_monthly.py --skip-collect

# Preview sin ejecutar council (solo datos)
python run_monthly.py --dry-run

# Sin confirmacion interactiva
python run_monthly.py --no-confirm

# Abrir reportes al terminar
python run_monthly.py --open
```

### Calendario de Generacion

| Reporte | Dias del Mes | Meses |
|---------|--------------|-------|
| Macro | 1-7 | Todos |
| Asset Allocation | 1-7 | Ene, Abr, Jul, Oct |
| Renta Variable | 1-7 | Todos |
| Renta Fija | 1-7 | Todos |

---

## Flujo de Generacion de Reportes

```
┌─────────────────────────────────────────────────────────────────┐
│           PIPELINE MENSUAL UNIFICADO (run_monthly.py)          │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼  Fase 1: RECOPILACION
┌─────────────────────────────────────────────────────────────────┐
│  DATA COLLECTORS                                                │
│                                                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  Macro (10)  │ │ Equity (10)  │ │  RF (13)     │           │
│  │  council_    │ │ equity_data_ │ │ rf_data_     │           │
│  │  data_coll.  │ │ collector    │ │ collector    │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                 │
│  + Intelligence Digest + Research Analyzer                      │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼  Fase 1d: PRONOSTICOS
┌─────────────────────────────────────────────────────────────────┐
│  FORECAST ENGINE (forecast_engine.py)                          │
│                                                                 │
│  Capa 1 (Survey/Market):     Capa 2 (Econometrico):           │
│  - Breakevens, Michigan      - ARIMA (5 series, 20Y data)     │
│  - GDPNow, LEI, yield curve  - VAR (4-var USA, 87 quarters)   │
│  - SOFR/SPC forwards         - Taylor Rule (Fed/TPM/ECB)      │
│  - EEE BCCh, targets AV      - Phillips Curve (OLS)           │
│                                                                 │
│  → Blended: Survey 40% + ARIMA 20% + VAR 20% + Struct 20%    │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼  Fase 2: PREFLIGHT + Fase 3: AI COUNCIL
┌─────────────────────────────────────────────────────────────────┐
│  AI COUNCIL (ai_council_runner.py)                             │
│                                                                 │
│  Panel (5 agentes):  Macro | RV | RF | Riesgo | Geo           │
│  Sintesis (3):       CIO | Contrarian | Refinador             │
│  → Recibe: quant + equity + RF + forecasts + intelligence     │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼  Fase 4: REPORTES
┌─────────────────────────────────────────────────────────────────┐
│  CONTENT GENERATORS → RENDERERS → HTML                         │
│                                                                 │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                  │
│  │ Macro  │ │   AA   │ │   RV   │ │   RF   │                  │
│  └────────┘ └────────┘ └────────┘ └────────┘                  │
│  Todos reciben: council_result + market_data + forecast_data   │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼  OUTPUT
┌─────────────────────────────────────────────────────────────────┐
│  output/                                                        │
│  ├── reports/    → 4 reportes HTML profesionales               │
│  ├── council/    → council_result_*.json                       │
│  ├── forecasts/  → forecast_YYYYMMDD_HHMMSS.json              │
│  ├── equity_data/→ equity_data_*.json                          │
│  └── rf_data/    → rf_data_*.json                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Contenido de Cada Reporte

### Reporte Macro

1. **Resumen Ejecutivo**
   - Key takeaways
   - Tabla de forecasts (GDP, Inflacion, Tasas)
   - Pronostico ponderado por escenarios

2. **Estados Unidos**
   - Crecimiento economico
   - Mercado laboral
   - Inflacion (CPI, PCE, componentes)
   - Politica monetaria Fed
   - Politica fiscal

3. **Europa**
   - GDP por pais
   - Inflacion HICP
   - Politica monetaria BCE

4. **China**
   - Crecimiento
   - Sector inmobiliario
   - Impulso crediticio
   - Comercio exterior

5. **Chile y LatAm**
   - IMACEC, inflacion, TPM
   - Cuentas externas
   - Commodities (cobre, litio) con inventarios y break-even costs
   - Contexto regional (Brasil, Mexico, Colombia)

6. **Escenarios y Riesgos**
   - Soft Landing / No Landing / Hard Landing
   - Top 3 riesgos con probabilidad e impacto

### Reporte Asset Allocation

1. **Resumen Ejecutivo**
   - Postura del comite
   - Key points

2. **Performance del Mes Anterior**
   - Atribucion por asset class
   - Calls acertados y errados

3. **Escenarios Macro**
   - Goldilocks / Inflationary Growth / Recession / Stagflation
   - Probabilidades y que comprar en cada uno

4. **Views Regionales**
   - USA, Europa, China, Chile, Brasil, Mexico
   - Argumentos a favor y en contra
   - Triggers de cambio

5. **Views por Asset Class**
   - Renta Variable
   - Renta Fija
   - Monedas
   - Commodities
   - **Acciones Tacticas** (nuevo)
   - **Hedge Ratios** (nuevo) - % del portfolio por tipo de hedge

6. **Riesgos**
   - Top risks con hedges
   - Triggers de reconvocatoria

### Reporte Renta Variable

1. **Resumen Ejecutivo**
   - Postura global equity
   - Tabla resumen por mercado

2. **Escenarios de Mercado** (nuevo)
   - Bull/Base/Bear con targets
   - Expected value ponderado

3. **Matriz de Correlacion** (nuevo)
   - Correlaciones entre mercados
   - Implicancias para diversificacion

4. **Valorizaciones**
   - Multiples por region (P/E, EV/EBITDA, P/B)
   - Equity Risk Premium
   - Valuacion relativa

5. **Earnings**
   - Crecimiento EPS
   - Tendencias de revisiones
   - Margenes y ROE

6. **Analisis Sectorial**
   - Matriz de 11 sectores
   - Sectores preferidos y a evitar

7. **Style & Factors**
   - Growth vs Value
   - Factor performance
   - Large vs Small

8. **Views Regionales**
   - USA, Europa, EM, Japon, Chile
   - Top picks Chile con **ESG scoring** (nuevo)
   - **Sensibilidad USD/CLP** (nuevo)

### Reporte Renta Fija

1. **Resumen Ejecutivo**
   - Postura global
   - Duration stance
   - Credit stance

2. **Ambiente de Tasas**
   - Yields globales
   - Analisis de curvas
   - Tasas reales

3. **Duration Positioning**
   - View por mercado
   - Trades recomendados (steepeners, etc)

4. **Credito**
   - Investment Grade
   - High Yield
   - Por sector
   - **CDS Spreads 5Y** (nuevo) - 14 paises
   - **Bid-Ask Spreads** (nuevo) - liquidez por segmento
   - **Calendario de Refinanciamiento** (nuevo)

5. **Mercados Emergentes**
   - Hard currency
   - Local currency
   - Por pais

6. **Chile Renta Fija**
   - Soberanos (BCP, BCU)
   - Corporativos
   - Money Market
   - UF vs Pesos

7. **Inflacion**
   - Breakevens globales
   - **Breakeven vs Realizado** (nuevo)
   - TIPS view

---

## Caracteristicas Avanzadas

### Pronostico Ponderado por Escenarios

El sistema calcula pronosticos ponderados usando:
```
GDP_weighted = Σ(Probabilidad_i × GDP_i)
```

Ejemplo:
- Soft Landing (55%): GDP 2.2%
- No Landing (20%): GDP 2.8%
- Hard Landing (25%): GDP 0.5%
- **Ponderado: 1.9%**

### Track Record

Cada reporte incluye comparacion vs el mes anterior:
- Cambios en forecasts con razones
- Aciertos y errores del reporte previo

### Hedge Ratios Detallados

Estructura de hedges con:
- Porcentaje del portfolio
- Instrumento especifico
- Costo estimado
- Trigger de activacion
- Implementacion

### ESG Scoring (Chile)

Para top picks de Chile:
- Score general (A+, A, BBB, etc)
- Desglose E/S/G
- Comentario especifico

---

## Dependencias

- Python 3.11+
- **Data**: yfinance, fredapi, requests
- **Analytics**: pandas, numpy, scipy
- **Econometrics**: statsmodels, pmdarima
- **AI Council**: anthropic (Claude API)
- **Charts**: matplotlib
- Standard: pathlib, json, datetime, glob

---

## Estructura de Archivos de Salida

```
output/
├── reports/
│   ├── macro_report_YYYY-MM-DD.html
│   ├── asset_allocation_report_YYYY-MM-DD.html
│   ├── rv_report_YYYY-MM-DD.html
│   └── rf_report_YYYY-MM-DD.html
│
└── council/
    └── council_YYYY-MM-DD.json
```

---

## Estilos de Reportes

Los reportes usan un estilo profesional inspirado en:
- Goldman Sachs Global Investment Research
- JPMorgan Asset Management
- BlackRock Investment Institute
- PIMCO Investment Outlook

Caracteristicas:
- Colores corporativos (azul primario, naranja acento)
- Tablas profesionales con alternancia de colores
- Cards para secciones importantes
- Indicadores visuales (trend up/down)
- Responsive design
- Print-friendly

---

## Mantenimiento

### Pipeline Mensual (Recomendado)

```bash
# Ejecutar pipeline completo (recopila datos → forecasts → council → reportes)
python run_monthly.py

# Solo reportes especificos
python run_monthly.py --reports macro,rv

# Sin council (solo datos + forecasts → reportes con fallback)
python run_monthly.py --skip-collect

# Dry run (verifica sin ejecutar council)
python run_monthly.py --dry-run
```

Los datos se recopilan automaticamente de APIs (FRED, BCCh, yfinance, AlphaVantage).
Los forecasts se generan automaticamente por el Forecast Engine (surveys + econometrico).
Solo los escenarios y probabilidades requieren juicio del analista (via AI Council o manual).

### Agregar Nuevo Tipo de Reporte

1. Crear `nuevo_content_generator.py`
2. Crear `nuevo_renderer.py`
3. Crear `templates/nuevo_professional.html`
4. Agregar caso en `run_monthly.py` fase de reportes
5. Agregar configuracion en la funcion correspondiente

---

## Integracion con el Sistema Greybark Research

Este modulo (`consejo_ia/`) se integra con:

- **Libreria Greybark** (`../02_greybark_library/`): Modulos de analytics y data sources
- **AI Council**: Panel de 5 especialistas IA para generar recomendaciones
- **Research PDFs** (`../pdf/`): Documentos de referencia de GS, JPM, Vanguard, Wellington

Para mas informacion sobre la arquitectura completa, ver el [README principal](../README.md).

---

## Contacto

Greybark Research
Sistema de Reportes de Inversion v4.0
Febrero 2026

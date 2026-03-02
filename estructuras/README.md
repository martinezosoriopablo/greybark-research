# GREYBARK RESEARCH - Sistema de Research e Inteligencia de Mercados
## Version 4.0 | Febrero 2026

---

## Vision General

Greybark Research es un sistema completo de research financiero que combina:
- **AI Council**: Panel de 5 especialistas IA que debaten para producir recomendaciones robustas
- **Libreria Greybark**: 55+ modulos Python para analytics financiero
- **Sistema de Reportes**: Generacion automatizada de reportes profesionales estilo Goldman Sachs/JPMorgan

**Propuesta de Valor**: "Acceso a un departamento de research completo con especialistas que procesan informacion global y debaten para darte mejores decisiones."

---

## Estructura del Proyecto

```
estructuras/
|
|-- README.md                    # Este archivo
|-- 01_master_index.yaml         # Arquitectura AI Council + definicion de reportes
|-- 03_CREDENTIALS.yaml          # API keys (FRED, AlphaVantage, etc.)
|-- 04_GUIA_TECNICA.yaml         # Referencia tecnica
|-- ESTADO_SISTEMA_2026-02-04.md # Estado de validacion del sistema
|
|-- 02_greybark_library/         # Libreria Python principal
|   |-- greybark/
|       |-- config.py            # Configuracion de series y APIs
|       |-- __init__.py
|       |
|       |-- ai_council/          # Sistema de AI Council
|       |   |-- agents/          # Personas de los 5 IAS
|       |   |-- deliberation/    # Logica de debate del comite
|       |   |-- data_integration/# Integracion de datos para AI Council
|       |   |-- output/          # Formateo de resultados
|       |
|       |-- analytics/           # Modulos de analisis
|       |   |-- breadth/         # Market breadth (A-D line, new highs/lows)
|       |   |-- chile/           # Chile analytics (TPM, IMACEC, breakeven)
|       |   |-- china/           # China credit impulse, EPU
|       |   |-- credit/          # Credit spreads (IG, HY)
|       |   |-- earnings/        # Beat rate, insider activity
|       |   |-- factors/         # Factor analysis (value, growth, momentum)
|       |   |-- fixed_income/    # Duration analytics
|       |   |-- fundamentals/    # Earnings revision analysis
|       |   |-- macro/           # Macro dashboard, inflation analytics
|       |   |-- rate_expectations/ # Fed, BCCh expectations
|       |   |-- regime_classification/ # Clasificacion de regimen macro
|       |   |-- risk/            # VaR, stress testing, LSTM predictions
|       |
|       |-- data_sources/        # Clientes de datos
|       |   |-- fred_client.py   # Federal Reserve (FRED API)
|       |   |-- bcch_client.py   # Banco Central de Chile
|       |   |-- bcch_extended.py # BCCh con series adicionales
|       |   |-- alphavantage_client.py # AlphaVantage Premium
|       |   |-- commloan_scraper.py    # SOFR forwards
|       |
|       |-- tracking/            # Sistema de track record
|       |-- utils/               # Utilidades (fechas, QuantLib helpers)
|       |-- reports/             # Utilidades para reportes
|
|-- consejo_ia/                  # Sistema de generacion de reportes
|   |-- master_orchestrator.py   # Orquestador principal - PUNTO DE ENTRADA
|   |
|   |-- CONTENT GENERATORS
|   |   |-- macro_content_generator.py
|   |   |-- asset_allocation_content_generator.py
|   |   |-- rv_content_generator.py
|   |   |-- rf_content_generator.py
|   |
|   |-- RENDERERS
|   |   |-- macro_report_renderer.py
|   |   |-- asset_allocation_renderer.py
|   |   |-- rv_report_renderer.py
|   |   |-- rf_report_renderer.py
|   |
|   |-- templates/               # Templates HTML profesionales
|   |-- output/                  # Reportes generados
|   |-- ai_council_runner.py     # Ejecutor del AI Council
|   |-- council_data_collector.py # Recolector de datos para AI Council
|
|-- pdf/                         # Research de referencia (GS, JPM, Vanguard, Wellington)
|-- sessions/                    # Resultados de sesiones del AI Council
|-- reports/                     # Reportes adicionales
|-- docs/                        # Documentacion adicional
```

---

## AI Council - El Diferenciador Clave

El AI Council replica la dinamica de un comite de inversiones profesional. 5 Intelligent Analyst Specialists (IAS) procesan informacion y **DEBATEN** para producir recomendaciones mas robustas.

### Los 5 Especialistas

| IAS | Expertise | Output |
|-----|-----------|--------|
| **IAS Macro** | Regimenes economicos, bancos centrales, China credit | Contexto macro, clasificacion de regimen |
| **IAS Renta Variable** | Earnings, valuaciones, sectores, factores | Recomendaciones equity, sectores |
| **IAS Renta Fija** | Duration, credit spreads, curvas, Chile profundo | Duration, credit allocation |
| **IAS Riesgo** | VaR, stress testing, correlaciones, LSTM | Metricas de riesgo, hedging |
| **IAS Asset Allocation** | Construccion de portafolio, 5 perfiles, tactical | Portafolios modelo, cambios tacticos |

### Dinamica de Debate

```
Ejemplo: Fed mas hawkish de lo esperado

IAS Macro      --> "Regimen --> SLOWDOWN, probabilidad recesion sube"
IAS Renta Fija --> "Extender duracion, pero cuidado con credito HY"
IAS Renta Var  --> "Rotar a Quality y Defensivos, reducir Cyclicals"
IAS Riesgo     --> "VaR sube 15%, activar hedge con puts"
IAS Asset Alloc --> "Consenso: reducir equity 5%. Disenso: timing del hedge"

Output: Recomendacion integra todas las perspectivas + documenta disenso
```

### Valor del AI Council
- Evita sesgo de un solo analista
- Identifica blind spots
- Documenta disensos (no solo consenso)
- Recomendaciones mas robustas

---

## Sistema de Reportes

### Tipos de Reportes

| Reporte | Frecuencia | Dia | Contenido |
|---------|------------|-----|-----------|
| **Macro** | Mensual | 1-7 | USA, Europa, China, Chile, escenarios, riesgos |
| **Renta Variable** | Mensual | 1-7 | Valuaciones, sectores, earnings, factores |
| **Renta Fija** | Mensual | 1-7 | Duration, credit, curvas, Chile RF |
| **Asset Allocation** | Trimestral | 1-7 (Ene/Abr/Jul/Oct) | Portafolios modelo, tactical views |

### Uso del Sistema

```bash
# Navegar al directorio
cd "C:\Users\I7 8700\OneDrive\Documentos\Wealth\estructuras\consejo_ia"

# Ver estado del calendario
python master_orchestrator.py status

# Generar reportes individuales
python master_orchestrator.py macro
python master_orchestrator.py rv
python master_orchestrator.py rf
python master_orchestrator.py asset_allocation

# Generar todos los reportes
python master_orchestrator.py all

# Generar solo los programados para hoy
python master_orchestrator.py scheduled

# Con AI Council (panel de agentes)
python master_orchestrator.py all --with-council

# Preview sin generar archivos
python master_orchestrator.py all --dry-run

# Output en formato JSON
python master_orchestrator.py all --json
```

### Caracteristicas de los Reportes

**Macro Report:**
- Pronosticos ponderados por probabilidad de escenarios
- Comparacion vs pronostico anterior (track record)
- Commodities con inventarios, dias de consumo, break-even costs

**Asset Allocation Report:**
- Acciones tacticas por asset class
- Hedge ratios especificos (% portfolio, costo, trigger)
- Performance del mes anterior
- Brasil y Mexico expandidos

**Renta Variable Report:**
- Escenarios bull/base/bear con targets
- Matriz de correlacion entre mercados
- ESG scoring para top picks Chile
- Sensibilidad a USD/CLP

**Renta Fija Report:**
- Tabla CDS 5Y para 14 paises
- Analisis de liquidez (bid-ask spreads)
- Calendario de refinanciamiento
- Breakeven inflation vs realizado

---

## Modulos de Analytics

### Clasificacion de Regimen
```python
from greybark.analytics.regime_classification import RegimeClassifier

classifier = RegimeClassifier()
regime = classifier.classify()  # RECESSION/SLOWDOWN/MODERATE/EXPANSION/LATE_CYCLE
```

Indicadores utilizados:
- Financial (40%): Credit spreads, yield curve, VIX
- Expectations (25%): Consumer confidence, PMI, sentiment
- Monetary (20%): Fed funds, SOFR forwards, TPM
- Real (15%): GDP, employment, retail sales

### Chile Analytics
```python
from greybark.analytics.chile import ChileAnalytics

chile = ChileAnalytics()
dashboard = chile.get_dashboard()
# TPM real, policy stance, IMACEC, IPC, breakeven Chile
```

### China Credit
```python
from greybark.analytics.china import ChinaCreditAnalytics

china = ChinaCreditAnalytics()
impulse = china.get_credit_impulse()  # % GDP
epu = china.get_epu_signal()  # Economic Policy Uncertainty
```

### Risk Metrics
```python
from greybark.analytics.risk import RiskMetrics

risk = RiskMetrics()
var_95 = risk.calculate_var(0.95)
stress = risk.stress_test(['2008_crisis', 'covid', 'rate_shock'])
```

---

## Fuentes de Datos

### APIs Primarias

| Fuente | Datos | Modulo |
|--------|-------|--------|
| **FRED** | Macro US (GDP, CPI, employment, rates) | `fred_client.py` |
| **BCCh** | Chile (TPM, IPC, IMACEC, USD/CLP, UF) | `bcch_client.py` |
| **AlphaVantage** | Earnings, sentiment, insider activity | `alphavantage_client.py` |
| **CommLoan** | SOFR forwards | `commloan_scraper.py` |

### Fuentes Diferenciadas

El sistema procesa multiples perspectivas globales:

**Tradicionales:**
- Wall Street Journal, Financial Times, Bloomberg, Reuters

**Globales Diferenciadas (DIFERENCIADOR UNICO):**
- Rusia: TASS, RT Business
- China: Xinhua, SCMP, Caixin
- Medio Oriente: Al Jazeera Business
- LatAm: Valor Economico (Brasil), El Economista (Mexico)

**Alternativas:**
- Telegram: Canales de analisis, breaking news
- Polymarket: Probabilidades implicitas de eventos

---

## Estado del Sistema

### Modulos Validados (9/9 OK)

| Modulo | Status | Ultima Validacion |
|--------|--------|-------------------|
| Regime Classification | EXPANSION (0.80) | 2026-02-04 |
| US Macro Dashboard | OK | 2026-02-04 |
| Inflation Analytics | BE 5Y: 2.53% | 2026-02-04 |
| Chile Analytics | OK | 2026-02-04 |
| China Credit | Contraction | 2026-02-04 |
| Market Breadth | OK | 2026-02-04 |
| Risk Metrics | VaR 95%: 0.77% | 2026-02-04 |
| Rate Expectations | 3 cuts, terminal 3.25% | 2026-02-04 |
| Macro Dashboard | OK | 2026-02-04 |

### Validacion de Datos

```bash
cd "C:\Users\I7 8700\OneDrive\Documentos\Wealth\estructuras"
python test_all_macro_data.py
```

---

## Instalacion

### Requisitos
- Python 3.8+
- Dependencias en `requirements.txt`

### Instalacion

```bash
# 1. Navegar al directorio
cd "C:\Users\I7 8700\OneDrive\Documentos\Wealth\estructuras\02_greybark_library"

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Instalar greybark como paquete editable
pip install -e .

# 4. Configurar API keys en 03_CREDENTIALS.yaml
```

### Dependencias Principales
- `pandas`, `numpy`: Manipulacion de datos
- `requests`: Llamadas a APIs
- `anthropic`: API de Claude para AI Council
- `jinja2`: Templates HTML
- Standard library para funcionalidad basica

---

## Research de Referencia

El directorio `pdf/` contiene research de instituciones lider:

| Fuente | Archivos |
|--------|----------|
| **Goldman Sachs** | Macro Outlook, Equity Strategy, Top of Mind series |
| **JPMorgan** | Global Outlook |
| **Vanguard** | Asset Allocation Report |
| **Wellington** | Economic Outlook, Bond Market, Credit, Geopolitics |

Estos documentos sirven como referencia para el estilo y profundidad de los reportes generados.

---

## Segmentos de Cliente

| Segmento | Audiencia | Tono |
|----------|-----------|------|
| **Sell Side** | Clientes wealth, alto patrimonio | Accesible, sin jerga |
| **Buy Side** | Gestores profesionales, AFPs | Tecnico, profundo |
| **Semi-pro** | Gerentes finanzas de empresas | Simple, FX-focused |

Cada segmento recibe versiones adaptadas del contenido.

---

## Diferenciadores Unicos

1. **AI Council con 5 especialistas que debaten** - Evita sesgo de un solo analista
2. **Multiples perspectivas globales** - No solo WSJ/FT, incluye TASS, Xinhua, Al Jazeera
3. **Chile Profundo** - Swap CAMARA, breakeven Chile, carry trade analysis
4. **Clasificacion de Regimen** - Dashboard con 11 indicadores lideres
5. **Track Record con accountability** - Documenta aciertos y errores
6. **China Credit Impulse** - Unico en Chile
7. **Pronosticos ponderados por escenarios** - No solo punto medio

---

## Calendario de Publicacion

### Reportes Diarios
- **AM**: Pre-apertura Chile (~7:00)
- **PM**: Post-cierre US (~18:00 Chile)

### Reportes Mensuales
- **Dia 1-7**: Macro, Renta Variable, Renta Fija

### Reportes Trimestrales
- **Dia 1-7**: Asset Allocation (Enero, Abril, Julio, Octubre)

---

## Workflow de Generacion

```
1. REGIME CLASSIFICATION
   |-- Ejecutar regime_classification.py
   |-- Output: regime_classification.json

2. DATA FETCH
   |-- FRED, BCCh, AlphaVantage
   |-- Output: DataFrames con series

3. AI COUNCIL DEBATE (opcional)
   |-- 5 IAS procesan datos
   |-- Output: Consenso + disensos

4. CONTENT GENERATION
   |-- *_content_generator.py
   |-- Output: Contenido estructurado

5. RENDERING
   |-- *_renderer.py + templates/
   |-- Output: HTML profesional

6. OUTPUT
   |-- consejo_ia/output/reports/
   |-- Archivos: *_report_YYYY-MM-DD.html
```

---

## Mantenimiento

### Actualizar Datos
1. Editar content generators con nuevos datos
2. Ejecutar `python master_orchestrator.py all`

### Agregar Nuevo Tipo de Reporte
1. Crear `nuevo_content_generator.py`
2. Crear `nuevo_renderer.py`
3. Crear template HTML
4. Agregar en `master_orchestrator.py`

### Actualizar Series BCCh
Ver `ESTADO_SISTEMA_2026-02-04.md` para mapeo de series antiguas a nuevas.

---

## Contacto

Greybark Research
Sistema de Research e Inteligencia de Mercados v4.0
Febrero 2026

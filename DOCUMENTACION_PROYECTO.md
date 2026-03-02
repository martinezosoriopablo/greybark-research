# DOCUMENTACIÓN - SISTEMA DE REPORTES GREY BARK ADVISORS

## Descripción General

Sistema automatizado de generación y distribución de reportes de mercados financieros. Recopila datos de múltiples fuentes, los procesa con IA, genera reportes profesionales y los distribuye por email.

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FLUJO DE DATOS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. RECOLECCIÓN              2. PROCESAMIENTO         3. GENERACIÓN          │
│  ─────────────               ───────────────          ────────────           │
│  daily_market_snapshot.py    newsletter_curator.py    generate_daily_report.py│
│       │                           │                        │                 │
│       ├─ Yahoo Finance           │                        │                 │
│       ├─ Alpha Vantage      Categoriza con IA         Sintetiza con         │
│       ├─ BCCh (IPSA)                                  Claude/Anthropic       │
│       ├─ Email IMAP                                        │                 │
│       ├─ RSS feeds                                         │                 │
│       └─ WSJ PDF                                           ▼                 │
│                                                                              │
│  4. FORMATEO                 5. DISTRIBUCIÓN          6. ALMACENAMIENTO      │
│  ───────────                 ─────────────            ─────────────          │
│  html_formatter.py           send_email_report.py     database_setup.py      │
│       │                           │                   client_manager.py      │
│       ▼                           ▼                                          │
│  HTML/PDF                    SMTP Gmail                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Archivos Principales

### 1. `daily_market_snapshot.py`
**Propósito:** Recolector principal de datos de mercado.

**Qué hace:**
- Descarga precios de 100+ activos (Yahoo Finance)
- Obtiene noticias con sentimiento (Alpha Vantage)
- Descarga newsletters por IMAP (WSJ, FT, Bloomberg, etc.)
- Parsea RSS feeds de noticias
- Extrae contenido de WSJ PDF
- Calcula sentimiento del mercado
- Genera JSON con todo el snapshot

**Output:** `daily_market_snapshot.json`

**Uso:**
```bash
python daily_market_snapshot.py        # Auto-detecta AM/PM
python daily_market_snapshot.py AM     # Forzar modo AM
python daily_market_snapshot.py PM     # Forzar modo PM
```

---

### 2. `generate_daily_report.py`
**Propósito:** Generador de reportes con IA.

**Qué hace:**
- Lee el snapshot JSON
- Construye dashboard compacto (IPSA, S&P, Petróleo, Cobre, USD/CLP)
- Genera narrativa profesional usando Claude (Anthropic)
- Incluye tablas detalladas de todos los activos
- Crea dos versiones: `finanzas` (profesional) y `no_finanzas` (general)

**Output:**
- `daily_report_AM_finanzas_YYYY-MM-DD.md`
- `daily_report_AM_no_finanzas_YYYY-MM-DD.md`

**Uso:**
```bash
python generate_daily_report.py                              # Auto-detecta
python generate_daily_report.py daily_market_snapshot.json AM  # Específico
```

---

### 3. `html_formatter.py`
**Propósito:** Convierte reportes MD/JSON a HTML profesional.

**Qué hace:**
- Aplica template HTML con branding Grey Bark
- Genera diseño responsivo para email
- Opcionalmente genera PDF (requiere wkhtmltopdf)

**Output:** `html_out/daily_report_*.html`

---

### 4. `send_email_report_improved.py`
**Propósito:** Distribuye reportes por email.

**Qué hace:**
- Lee base de datos de clientes
- Identifica destinatarios según tipo de reporte
- Envía HTML por SMTP (Gmail)

**Tipos de reporte:**
- `AM_pro` → Profesionales, reporte AM
- `AM_general` → Retail, reporte AM
- `PM_pro` → Profesionales, reporte PM
- `PM_general` → Retail, reporte PM
- `weekly_quant` → Reporte semanal cuantitativo

---

## Módulos de Soporte

### `alphavantage_integration.py`
- Conexión a Alpha Vantage API
- Noticias con sentimiento cuantificado
- Indicadores económicos US (CPI, Unemployment, Treasury)

### `alphavantage_global_expansion.py`
- Treasury Yields (2Y, 5Y, 10Y, 30Y)
- Índices globales (Asia, Europa, LatAm)
- Sentiment sectorial (Tech, Financials, Energy, etc.)

### `ipsa_integration.py`
- IPSA desde Banco Central de Chile (BCCh)
- Calcula MTD, YTD con días hábiles correctos
- Respeta feriados bancarios chilenos

### `chile_timezone.py`
- Conversión de zonas horarias UTC ↔ Chile
- Parse de fechas de emails
- Detección automática AM/PM según hora Chile

### `chile_business_days.py`
- Feriados fijos de Chile (13)
- Feriados móviles (Semana Santa)
- Validación de días hábiles bancarios

### `newsletter_curator.py`
- Categoriza noticias con IA (Anthropic)
- Prioriza: Activos financieros > Macro > Geopolítica > Tech/IA
- Detecta temas repetidos entre newsletters

### `wsj_pdf_parser.py`
- Extrae texto de PDFs del WSJ
- Busca automáticamente en carpeta de descargas

### `client_manager.py`
- Base de datos JSON de clientes
- Tipos: professional, retail, internal
- Gestiona suscripciones a reportes

### `database_setup.py`
- SQLite para historial de reportes
- Registra envíos y estados de entrega

---

## Variables de Entorno (.env)

```env
# Alpha Vantage (datos de mercado y noticias)
ALPHAVANTAGE_API_KEY=tu_api_key

# Anthropic (generación de reportes con IA)
ANTHROPIC_API_KEY=tu_api_key

# Email IMAP (lectura de newsletters)
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_USERNAME=tu_email@gmail.com
EMAIL_PASSWORD=tu_app_password

# Email SMTP (envío de reportes)
EMAIL_SENDER_USERNAME=tu_email@gmail.com
EMAIL_SENDER_PASSWORD=tu_app_password

# Banco Central Chile (IPSA oficial)
BCCH_USER=tu_usuario
BCCH_PASS=tu_password

# NewsAPI (opcional)
NEWSAPI_KEY=tu_api_key

# OpenAI (análisis de sentimiento, opcional)
OPENAI_API_KEY=tu_api_key

# WSJ PDF (opcional, default: Downloads)
WSJ_PDF_DIR=C:/Users/marti/Downloads

# Resumen Diario Financiero
DF_RESUMEN_DIR=C:/Users/marti/OneDrive/Documentos/df/df_data
```

---

## Ejecución Típica

### Generar reporte completo (AM):
```bash
# 1. Recolectar datos
python daily_market_snapshot.py AM

# 2. Generar reporte
python generate_daily_report.py daily_market_snapshot_AM.json AM

# 3. Convertir a HTML
python html_formatter.py

# 4. Enviar por email
python send_email_report_improved.py AM_pro
python send_email_report_improved.py AM_general
```

---

## Estructura de Carpetas

```
proyectos/
├── *.py                          # Scripts principales
├── .env                          # Variables de entorno (NO commitear)
├── clients_database.json         # Base de datos de clientes
├── daily_market_snapshot.json    # Último snapshot
├── daily_report_*.md             # Reportes generados
├── html_out/                     # HTMLs generados
│   └── daily_report_*.html
├── history/                      # Histórico de snapshots
│   └── daily_market_snapshot_YYYY-MM-DD_AM.json
└── sentiment_history.json        # Historial de sentimiento
```

---

## Tipos de Reportes

| Tipo | Audiencia | Contenido | Horario |
|------|-----------|-----------|---------|
| AM_finanzas | Profesionales | Técnico, completo | Pre-apertura (~7:30 AM) |
| AM_no_finanzas | General | Accesible, resumido | Pre-apertura |
| PM_finanzas | Profesionales | Cierre de mercado | Post-cierre (~18:00) |
| PM_no_finanzas | General | Resumen del día | Post-cierre |
| weekly_quant | Todos | Análisis cuantitativo semanal | Viernes/Sábado |

---

## Activos Cubiertos

### Índices
- **US:** S&P 500, Nasdaq, Dow Jones, Russell 2000
- **Europa:** STOXX 50, FTSE 100, DAX, CAC 40
- **Asia:** Nikkei 225, Hang Seng, Shanghai
- **LatAm:** Bovespa, IPC México, IPSA Chile

### Renta Fija
- US Treasuries (2Y, 5Y, 10Y, 30Y)
- AGG (Bonos agregados)
- HYG (High Yield)
- VIX (Volatilidad)

### Divisas
- DXY (Índice dólar)
- USD/CLP (Dólar observado BCCh)
- EUR/USD, USD/JPY, USD/MXN, USD/BRL

### Commodities
- Petróleo WTI y Brent
- Oro, Plata
- Cobre (crítico para Chile)

### Chile Específico
- IPSA (índice bursátil)
- Dólar observado (BCCh)
- UF
- TPM (Tasa de Política Monetaria)

---

## Newsletters Integradas

| Newsletter | Fuente | Prioridad |
|------------|--------|-----------|
| WSJ Markets A.M. | Email | CRITICAL |
| WSJ Markets P.M. | Email | CRITICAL |
| WSJ The 10-Point | Email | CRITICAL |
| WSJ AI & Business | Email | HIGH |
| FT Markets Morning | Email | HIGH |
| FT Commodities Note | Email | MEDIUM |
| Bloomberg Línea | Email | HIGH |
| Morning Brew | Email | HIGH |
| DF Primer Click | Email | HIGH |
| WSJ PDF | Descarga manual | HIGH |

---

## Notas Técnicas

### Rate Limiting
- Alpha Vantage: 75 req/min (Premium), 1 seg entre requests
- Yahoo Finance: Sin límite oficial, usar con moderación
- BCCh: Sin límite documentado

### Días Hábiles Chile
El sistema considera:
- Fines de semana (Sáb/Dom)
- 13 feriados fijos
- Feriados móviles (Viernes y Sábado Santo)
- 31 de diciembre (feriado bancario)

### Detección AM/PM
- Antes de 14:00 Chile → Modo AM
- Después de 14:00 Chile → Modo PM

---

## Troubleshooting

### Error: "DF_RESUMEN_DIR no configurado"
Verificar que la variable `DF_RESUMEN_DIR` en `.env` apunte a la carpeta correcta.

### Error: "BCCh no disponible"
Las credenciales del Banco Central pueden haber expirado. Renovar en si3.bcentral.cl

### Error: "Newsletter no encontrada"
Verificar credenciales IMAP y que el email haya llegado en la ventana de tiempo correcta (AM: 19:00 ayer - 10:00 hoy, PM: 10:00 - 20:00 hoy).

### Error: "Día de la semana incorrecto"
El script ahora incluye la fecha explícita en el prompt. Si persiste, verificar que `DIAS_SEMANA` y `get_fecha_completa()` estén definidos.

---

*Última actualización: 16 de enero de 2026*

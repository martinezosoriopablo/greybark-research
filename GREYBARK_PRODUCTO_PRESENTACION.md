# GREYBARK RESEARCH — Documento de Producto para Presentación Comercial

## Para usar con Claude Chat para generar la presentación de ventas.

---

## 1. QUÉ ES GREYBARK RESEARCH

Greybark Research es una **plataforma de inteligencia financiera automatizada** que cada mañana — sin intervención humana — recolecta datos de mercado de más de 50 fuentes globales, los analiza con inteligencia artificial (Claude de Anthropic), y genera reportes profesionales de mercado, briefings de inteligencia y podcasts de audio, distribuyéndolos automáticamente a clientes segmentados por email.

**En una frase:** Un analista de research senior que trabaja 24/7, nunca se enferma, y entrega a las 7:00 AM un briefing que normalmente tomaría 3-4 horas a un equipo humano.

---

## 2. PIPELINE COMPLETO — ARQUITECTURA

```
┌─────────────────────────────────────────────────────────────────────┐
│                    GREYBARK RESEARCH PIPELINE                       │
│                    7 pasos automatizados                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  PASO 1  │───>│  PASO 2  │───>│   PASO 3     │───>│  PASO 4  │  │
│  │  DATA    │    │ REPORTES │    │ INTELLIGENCE │    │   HTML    │  │
│  │ CAPTURE  │    │    MD    │    │  BRIEFING    │    │          │  │
│  └──────────┘    └──────────┘    └──────────────┘    └──────────┘  │
│       │                                                    │        │
│       │          ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│       │          │  PASO 5  │───>│  PASO 6  │───>│  PASO 7  │      │
│       └─────────>│ PODCAST  │    │  EMAIL   │    │ ARCHIVO  │      │
│                  │  AUDIO   │    │ DELIVERY │    │          │      │
│                  └──────────┘    └──────────┘    └──────────┘      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Paso 1 — Captura de Datos (daily_market_snapshot.py)
**Fuentes cuantitativas (~100+ tickers):**
- Yahoo Finance: S&P 500, NASDAQ, Dow Jones, FTSE, DAX, Nikkei, índices globales
- Alpha Vantage API: Sentiment sectorial, indicadores económicos, Treasury yields
- Banco Central de Chile (BCCh): IPSA, TPM, dólar observado, UF
- IMAP Email: Newsletters de WSJ, FT, Bloomberg, Diario Financiero
- RSS Feeds: 12+ medios internacionales
- WSJ PDF: Descarga automática de edición print con Selenium
- Crypto: Bitcoin, Ethereum, precios y cambios

**Output:** `daily_market_snapshot.json` — dataset completo del día

### Paso 2 — Generación de Reportes (generate_daily_report.py)
- Claude API genera **2 versiones** del reporte:
  - **Profesional** (gestores, AFPs, institucionales): lenguaje técnico, métricas avanzadas
  - **General** (clientes retail, inversionistas individuales): lenguaje accesible
- QA Review automático: segunda pasada de Claude verifica coherencia datos vs narrativa
- Incluye: Dashboard, Resumen Ejecutivo, Economía, Geopolítica, IA/Tech, Chile/LatAm, Mercados por Activo, Sentimiento

### Paso 3 — Intelligence Briefing (greybark-intelligence/)
**Fuentes cualitativas (~27 fuentes externas):**
- **15 Substacks** de analistas top: Chartbook (Adam Tooze), Fed Guy (Joseph Wang), Apricitas, Doomberg, China Talk, etc.
- **7 canales de Telegram**: Bloomberg, Financial Times, The Economist, etc.
- **5 feeds RSS de medios**: Bloomberg Markets, FT, WSJ, Reuters

**Proceso:**
1. Recolección automática de ~85-100 items/día
2. Limpieza HTML, deduplicación, normalización
3. Claude AI clasifica cada item: categoría, relevancia, señal de inversión, resumen en español
4. Genera briefing estructurado por secciones temáticas
5. Se inyecta en el reporte diario

### Paso 4 — Conversión HTML (html_formatter.py)
- Convierte markdown a HTML profesional con branding Grey Bark Advisors
- Dashboard visual, tablas con colores (verde ganancias, rojo pérdidas)
- Compatible con Gmail, Outlook, Apple Mail

### Paso 5 — Podcast de Audio (generar_podcast.py)
- Claude convierte el reporte en guion conversacional en español chileno
- Edge TTS genera audio MP3 con voz chilena (es-CL-CatalinaNeural)
- Duración: 4-6 minutos
- "Buenos días, soy Camila, tu analista de Greybark Research..."

### Paso 6 — Distribución por Email (send_email_report_improved.py)
- Base de datos de clientes con segmentación automática
- Reportes profesionales → gestores, AFPs
- Reportes generales → clientes retail
- SMTP desde dominio propio (pmartinez@greybark.com)

### Paso 7 — Archivado
- Reportes MD y HTML archivados por fecha
- Datos crudos del intelligence pipeline guardados por día
- Historial de snapshots de mercado en JSON

---

## 3. NÚMEROS Y MÉTRICAS

### Volumen de datos procesados diariamente
| Métrica | Valor |
|---------|-------|
| Tickers de mercado monitoreados | 100+ |
| Fuentes de inteligencia cualitativa | 27 |
| Items de inteligencia recolectados/día | 85-100 |
| Items clasificados como alta relevancia | ~30/día |
| Versiones de reporte generadas | 4 (2 AM + 2 PM) |
| Podcasts generados | 2/día (AM + PM) |
| Llamadas a IA por ejecución | ~8-10 |

### Comparación con alternativas tradicionales
| Servicio | Costo mensual | Tiempo entrega |
|----------|--------------|----------------|
| Analista de research junior (Chile) | $1,500-2,500 USD | 3-4 horas/día |
| Bloomberg Terminal | $2,000 USD | N/A (solo datos crudos) |
| Servicio de research tercerizado | $3,000-10,000 USD | Variable |
| **Greybark Research** | **Fracción del costo** | **~12 minutos, automático** |

---

## 4. STACK TECNOLÓGICO

| Componente | Tecnología |
|-----------|------------|
| Lenguaje | Python 3.11 |
| IA / LLM | Claude Sonnet 4.5 (Anthropic API) |
| Datos de mercado | Yahoo Finance, Alpha Vantage, BCCh API |
| Newsletters | IMAP (Gmail) + feedparser |
| Intelligence | feedparser (RSS), telethon (Telegram) |
| Audio/Podcast | Neural TTS (Microsoft Azure) |
| Web scraping | Selenium + ChromeDriver (WSJ PDF) |
| Distribución | SMTP (Gmail + dominio propio) |
| Automatización | Windows Task Scheduler + batch script |
| Versionamiento | Git + GitHub |

---

## 5. FORTALEZAS COMPETITIVAS

### 5.1 Automatización total
- **Zero-touch**: desde captura de datos hasta entrega al cliente, sin intervención humana
- Corre a las 7:00 AM antes de apertura de mercados
- Si un componente falla, el pipeline continúa (fault-tolerant)

### 5.2 Escalabilidad extrema
- Agregar un cliente nuevo tiene costo marginal prácticamente cero
- Escalar de 5 a 500 clientes: mismo pipeline de generación
- Infraestructura cloud-ready, sin dependencia de hardware dedicado

### 5.3 Inteligencia cualitativa + cuantitativa
- No solo datos de mercado: también el análisis de los mejores analistas del mundo
- Substacks de Adam Tooze, Joseph Wang (ex Fed), Joey Politano, Michael Burry
- Telegram de Bloomberg, FT, The Economist en tiempo real
- Todo clasificado por relevancia y señal de inversión

### 5.4 Multi-formato, multi-audiencia
- Mismo pipeline genera: HTML profesional, markdown, audio podcast
- Segmentación automática: profesional vs retail
- Cada cliente recibe lo que necesita, en el formato que prefiere

### 5.5 Modular y extensible
- Agregar una fuente nueva = 1 línea en sources.yaml
- Agregar un módulo nuevo = 1 archivo Python
- Cada componente es independiente y testeable por separado

### 5.6 Historial y trazabilidad
- Todos los datos crudos se archivan por fecha
- Reportes archivados desde enero 2026
- Base para backtesting y análisis de tendencias

---

## 6. OPORTUNIDADES DE MEJORA

### 6.1 Corto plazo (1-3 meses)
- **Más fuentes de inteligencia**: agregar X/Twitter feeds, Reddit r/wallstreetbets, Seeking Alpha
- **Dashboard web en tiempo real**: Flask/Streamlit para visualizar briefing online
- **Alertas intraday**: monitoreo continuo con notificaciones push ante eventos críticos
- **Mejores feeds RSS**: algunos feeds (Reuters, FRED) tienen problemas de parsing, buscar alternativas

### 6.2 Mediano plazo (3-6 meses)
- **App móvil**: notificaciones push + podcast integrado
- **Análisis de sentimiento temporal**: tracking de cómo evoluciona el sentimiento por tema/sector
- **Backtesting de señales**: validar si las señales bullish/bearish del briefing predicen movimientos
- **Multi-idioma**: generar reportes en inglés para clientes internacionales
- **API pública**: exponer el intelligence briefing como API para integradores

### 6.3 Largo plazo (6-12 meses)
- **Agentes autónomos**: agente que monitorea portafolio del cliente y genera alertas personalizadas
- **Integración con brokers**: conectar con APIs de corredoras para sugerencias de trading
- **Modelos propietarios**: fine-tuning de modelos con datos históricos de Greybark
- **Plataforma SaaS**: portal web completo con login, personalización, historiales

---

## 7. SUB-PRODUCTOS COMERCIALIZABLES

### 7.1 Intelligence Briefing as a Service
**Producto:** Suscripción al briefing diario de inteligencia
**Target:** Family offices, gestores de patrimonio, AFPs, corredoras de bolsa
**Precio sugerido:** $200-500 USD/mes
**Diferenciador:** 27 fuentes curadas, clasificadas por IA, en español, a las 7 AM

### 7.2 Podcast Financiero Automatizado
**Producto:** Podcast diario de mercados "con voz de analista"
**Target:** Inversionistas individuales, asesores financieros
**Precio sugerido:** $50-100 USD/mes o freemium con ads
**Diferenciador:** Generado automáticamente, en español chileno, listo antes de apertura

### 7.3 Reportes White-Label
**Producto:** Pipeline de reportes automatizados con marca del cliente
**Target:** Corredoras de bolsa, bancos, fintech que necesitan content de research
**Precio sugerido:** $1,000-5,000 USD/mes setup + $500/mes operación
**Diferenciador:** Customizable por audiencia, con branding propio del cliente

### 7.4 API de Inteligencia Financiera
**Producto:** API REST que entrega items clasificados con señales de inversión
**Target:** Fintech, robo-advisors, plataformas de trading
**Precio sugerido:** $500-2,000 USD/mes por volumen
**Diferenciador:** Datos estructurados (JSON) con categoría, relevancia, señal, activos afectados

### 7.5 Plataforma de Monitoreo para Equipos de Inversión
**Producto:** Dashboard web con briefing, alertas, historial, búsqueda
**Target:** Equipos de inversión de bancos, family offices, fondos
**Precio sugerido:** $2,000-10,000 USD/mes por equipo
**Diferenciador:** Reemplaza horas de lectura matutina del equipo

### 7.6 Data as a Service — Historial de Sentimiento
**Producto:** Base de datos histórica de sentimiento por tema/sector/región
**Target:** Quant funds, académicos, data scientists
**Precio sugerido:** $1,000-3,000 USD/mes
**Diferenciador:** Sentimiento clasificado por IA desde 27+ fuentes, trazable a la fuente original

---

## 8. MODELO DE NEGOCIO POTENCIAL

### Tier 1: Suscripción Individual ($99-299/mes)
- Reporte diario AM + PM (HTML + email)
- Intelligence Briefing
- Podcast audio
- Acceso a archivo histórico

### Tier 2: Profesional ($499-999/mes)
- Todo Tier 1
- API de datos estructurados
- Alertas intraday
- Reportes customizables por sector/región
- Soporte prioritario

### Tier 3: Enterprise ($2,000-10,000/mes)
- Todo Tier 2
- White-label con marca propia
- Dashboard web para equipos
- Integración con sistemas internos
- SLA garantizado
- Onboarding dedicado

### Proyección (conservadora)
| Métrica | Año 1 | Año 2 | Año 3 |
|---------|-------|-------|-------|
| Clientes Tier 1 | 20 | 80 | 200 |
| Clientes Tier 2 | 5 | 15 | 40 |
| Clientes Tier 3 | 1 | 3 | 8 |
| MRR | $5,500 | $22,000 | $62,000 |
| ARR | $66,000 | $264,000 | $744,000 |
| Margen bruto | >90% | >90% | >90% |

---

## 9. PROCESO DIARIO — FLUJO VISUAL

```
06:55 AM  ┌─────────────────────────────────┐
          │  Windows Task Scheduler trigger  │
          └──────────────┬──────────────────┘
                         │
07:00 AM  ┌──────────────▼──────────────────┐
          │  PASO 1: Captura de datos        │
          │  Yahoo Finance, BCCh, Alpha      │
          │  Vantage, Newsletters, WSJ PDF   │
          │  (~100 tickers, 12 newsletters)  │  ⏱ ~3 min
          └──────────────┬──────────────────┘
                         │
07:03 AM  ┌──────────────▼──────────────────┐
          │  PASO 2: Generación de reportes  │
          │  Claude AI genera 2 versiones    │
          │  + QA review automático          │  ⏱ ~2 min
          └──────────────┬──────────────────┘
                         │
07:05 AM  ┌──────────────▼──────────────────┐
          │  PASO 3: Intelligence Briefing   │
          │  27 fuentes → 85 items → Claude  │
          │  clasifica → Briefing inyectado  │  ⏱ ~3.5 min
          └──────────────┬──────────────────┘
                         │
07:09 AM  ┌──────────────▼──────────────────┐
          │  PASO 4: HTML + PASO 5: Podcast  │
          │  Branding profesional + MP3      │  ⏱ ~2 min
          └──────────────┬──────────────────┘
                         │
07:11 AM  ┌──────────────▼──────────────────┐
          │  PASO 6: Email a clientes        │
          │  Segmentado: PRO + General       │  ⏱ ~1 min
          └──────────────┬──────────────────┘
                         │
07:12 AM  ┌──────────────▼──────────────────┐
          │  ✅ LISTO                         │
          │  Clientes reciben reporte +      │
          │  briefing + podcast antes de     │
          │  apertura de mercados            │
          └─────────────────────────────────┘

          TIEMPO TOTAL: ~12 minutos
```

---

## 10. RESUMEN EJECUTIVO PARA INVERSIONISTAS

Greybark Research es un sistema de inteligencia financiera automatizado que transforma la forma en que los gestores de patrimonio consumen información de mercados.

**El problema:** Un gestor de inversiones gasta 2-4 horas cada mañana leyendo Bloomberg, FT, newsletters, y reportes para estar al día antes de tomar decisiones. Este tiempo es costoso, inconsistente, y dependiente de una sola persona.

**La solución:** Greybark automatiza todo ese proceso. Cada mañana a las 7 AM, el sistema:
- Captura datos de 100+ instrumentos financieros
- Lee y clasifica 85+ artículos de los mejores analistas del mundo
- Genera reportes profesionales personalizados por audiencia
- Produce un podcast de audio para escuchar en el auto
- Lo entrega todo por email, listo para consumir

**La propuesta de valor:** Inteligencia de mercado de clase mundial, en español, entregada antes de apertura, a una fracción del costo de un equipo de research tradicional.

**La visión:** Ser el "Bloomberg Terminal" accesible para el wealth management latinoamericano.

---

*Documento preparado para presentación comercial — Greybark Research 2026*
*Stack: Python + Claude AI (Anthropic) + 50+ fuentes de datos*
*Contacto: Pablo Martínez — pmartinez@greybark.com*

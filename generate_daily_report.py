# -*- coding: utf-8 -*-
"""
GENERATE DAILY REPORT V4 ULTIMATE
- Dashboard compacto al inicio (con sentiment sectorial)
- Contenido RICO del código antiguo
- Tablas detalladas al final
- Treasuries con basis points correctos
- Auto-detección AM/PM por hora Chile
"""

# Proteccion de encoding para Windows
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import json
import os
from datetime import date
from typing import Any, Dict, List, Set
from collections import defaultdict

# Mapeo de días de la semana en español
DIAS_SEMANA = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo"
}

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def get_fecha_completa() -> str:
    """Retorna la fecha en formato: 'Viernes 16 de enero de 2026'"""
    hoy = date.today()
    dia_semana = DIAS_SEMANA[hoy.weekday()]
    mes = MESES[hoy.month]
    return f"{dia_semana} {hoy.day} de {mes} de {hoy.year}"


def get_ultimo_dia_habil() -> date:
    """
    Retorna el último día hábil de mercado (Lunes-Viernes).
    Si hoy es Lunes, retorna el Viernes pasado.
    Si hoy es Martes-Viernes, retorna ayer.
    Si hoy es Sábado, retorna Viernes.
    Si hoy es Domingo, retorna Viernes.
    """
    from datetime import timedelta
    hoy = date.today()
    weekday = hoy.weekday()

    if weekday == 0:  # Lunes -> Viernes pasado
        return hoy - timedelta(days=3)
    elif weekday == 6:  # Domingo -> Viernes
        return hoy - timedelta(days=2)
    elif weekday == 5:  # Sábado -> Viernes
        return hoy - timedelta(days=1)
    else:  # Martes-Viernes -> Ayer
        return hoy - timedelta(days=1)


def get_contexto_temporal(mode: str = "AM") -> str:
    """
    Genera contexto temporal para el prompt.
    AM: los datos son del cierre ANTERIOR (ayer o viernes).
    PM: los datos son de la sesión de HOY.
    """
    hoy = date.today()
    weekday = hoy.weekday()
    ultimo_habil = get_ultimo_dia_habil()
    dia_ultimo = DIAS_SEMANA[ultimo_habil.weekday()]
    dia_hoy = DIAS_SEMANA[weekday]

    if mode == "PM":
        # PM: las tablas del dashboard y cierre son de HOY
        if weekday in (5, 6):  # Sábado/Domingo
            return f"""**CONTEXTO TEMPORAL IMPORTANTE:**
- Hoy es {dia_hoy.upper()}. Los mercados están cerrados.
- El último día de trading fue el VIERNES {ultimo_habil.day} de {MESES[ultimo_habil.month]}.
- Los datos corresponden al cierre del viernes."""
        else:
            return f"""**CONTEXTO TEMPORAL (REPORTE PM - CIERRE DEL DÍA):**
- Las tablas de mercado (dashboard, índices, commodities, divisas) contienen datos de HOY {dia_hoy} {hoy.day} de {MESES[hoy.month]}.
- Cuando describas un precio, nivel o variación que aparece en las tablas, usa "hoy" (son cierres de hoy).
  Correcto: "El IPSA cerró hoy en 10,495 (+2.40%)"
  Incorrecto: "El IPSA experimentó ayer una jornada con avance de +2.40%"
- Puedes usar "ayer" para referirte a EVENTOS o NOTICIAS que ocurrieron el día anterior.
  Correcto: "Tras los datos de empleo publicados ayer, los mercados reaccionaron hoy con alzas"
- Regla simple: si mencionas un NÚMERO de las tablas → "hoy". Si describes un evento pasado sin citar datos de hoy → "ayer" es válido."""

    # AM o default
    if weekday == 0:  # Lunes
        return f"""**CONTEXTO TEMPORAL IMPORTANTE:**
- Hoy es LUNES. Los mercados estuvieron cerrados el fin de semana.
- Los datos de cierre en las tablas corresponden al VIERNES {ultimo_habil.day} de {MESES[ultimo_habil.month]}.
- Cuando describas precios y cierres de las tablas, di "el viernes" NO "ayer".
- Puedes usar "hoy" para mercados asiáticos/europeos si ya abrieron."""

    elif weekday == 5:  # Sábado
        return f"""**CONTEXTO TEMPORAL IMPORTANTE:**
- Hoy es SÁBADO. Los mercados están cerrados.
- El último día de trading fue AYER VIERNES {ultimo_habil.day} de {MESES[ultimo_habil.month]}.
- Este es un resumen de la semana que terminó."""

    elif weekday == 6:  # Domingo
        return f"""**CONTEXTO TEMPORAL IMPORTANTE:**
- Hoy es DOMINGO. Los mercados están cerrados.
- El último día de trading fue el VIERNES {ultimo_habil.day} de {MESES[ultimo_habil.month]}.
- Cuando menciones el cierre, di "el viernes" NO "ayer"."""

    else:  # Martes a Viernes (AM)
        return f"""**CONTEXTO TEMPORAL (REPORTE AM - PRE-APERTURA):**
- Los datos de cierre en las tablas (EE.UU., Chile) corresponden a AYER {dia_ultimo} {ultimo_habil.day} de {MESES[ultimo_habil.month]}.
- Cuando describas precios de cierre de las tablas, usa "ayer".
- Puedes usar "hoy" para mercados asiáticos/europeos que ya operaron esta mañana.
- Puedes usar "hoy" para eventos o noticias publicadas esta mañana."""


from dotenv import load_dotenv
from anthropic import Anthropic

# Import content deduplication from daily_market_snapshot
try:
    from daily_market_snapshot import get_am_used_content
    DEDUP_AVAILABLE = True
except ImportError:
    print("[WARN] get_am_used_content not available - deduplication disabled")
    DEDUP_AVAILABLE = False

load_dotenv()

# Configuración
INPUT_JSON = "daily_market_snapshot.json"
USE_ANTHROPIC = True

SYSTEM_PROMPT = """Eres un estratega de mercados globales con foco en Chile y experiencia en gestión de portafolios institucionales.

ESTILO:
- Profesional pero accesible
- Técnico sin ser excesivamente académico
- Similar a reportes de research de bancos de inversión (JPM, Goldman, BTG)
- Español claro y preciso

PROHIBIDO:
- Emojis
- Lenguaje comercial o marketing
- Recomendaciones específicas de compra/venta
- Promesas sobre el futuro
- Opiniones personales no fundamentadas
- Inventar o mencionar datos que no están en las tablas del contexto

ENFOQUE:
- Prioriza ACTIVOS FINANCIEROS sobre noticias generales
- Conecta macro con impacto en portafolios
- Identifica tendencias que afectan valuaciones
- Proporciona contexto para decisiones de inversión

VALIDACIÓN DE DATOS (CRÍTICO):
- Usa SOLO datos de las tablas detalladas al final del contexto
- NO inventes precios o porcentajes
- Si un activo no aparece en la tabla, NO lo menciones
- Si un cambio es NEGATIVO (-X%), NO digas "máximos" o "récords"
- Reporta SIEMPRE precios de CIERRE, no intradía (salvo que aclares)

SENTIMIENTO SECTORIAL (MUY IMPORTANTE):
- El "Sentimiento de Noticias por Sector" es un ÍNDICE DE SENTIMIENTO basado en análisis de noticias
- Escala de -1 (muy negativo) a +1 (muy positivo), NO son retornos ni ganancias de índices sectoriales
- "Optimista" o "Bullish" significa que las NOTICIAS del sector tienen tono positivo
- NUNCA interpretes el sentimiento como rentabilidad, ganancia o retorno de un sector
- Ejemplo correcto: "El sentimiento en tecnología es optimista"
- Ejemplo INCORRECTO: "El sector tecnológico lidera ganancias con +29%" (ESTO ESTÁ MAL)

DIVISAS Y TIPO DE CAMBIO (CRÍTICO):
- El CLP (peso chileno) NO es un activo de inversión. Es la MONEDA LOCAL.
- Si USD/CLP SUBE (+X%), el peso se DEPRECIÓ = se DEBILITÓ. Esto es NEGATIVO para Chile.
  NUNCA uses "beneficiándose", "avanzó", "ganó" para describir depreciación del peso.
  Correcto: "El peso se depreció +1.41% frente al dólar, cerrando en $895"
  Incorrecto: "El dólar avanzó beneficiándose del apetito por activos de riesgo"
- Si USD/CLP BAJA (-X%), el peso se APRECIÓ = se FORTALECIÓ. Esto es POSITIVO para Chile.
- El tipo de cambio se reporta desde la perspectiva del PESO, no del dólar.
  El dólar no se "beneficia" — el peso se debilita o fortalece.
- Misma lógica para USD/MXN. EUR/USD es inverso (sube = euro fuerte, dólar débil).

SIGLAS EN CONTEXTO CHILENO:
- CFA = Consejo Fiscal Autónomo (organismo fiscal chileno), NO la certificación CFA Institute.
- BCCh = Banco Central de Chile
- CMF = Comisión para el Mercado Financiero
- TPM = Tasa de Política Monetaria
- IPC = Índice de Precios al Consumidor (Chile)
- IPSA = Índice de Precios Selectivo de Acciones"""


def detect_report_mode() -> str:
    """
    Detecta automáticamente AM/PM según hora de Chile
    Antes de 14:00 → AM, después → PM
    """
    try:
        from chile_timezone import get_chile_now
        now_chile = get_chile_now()
        hour = now_chile.hour
        mode = "AM" if hour < 14 else "PM"
        print(f"[INFO] Hora Chile: {now_chile.strftime('%H:%M')} → Modo: {mode}")
        return mode
    except Exception as e:
        print(f"[WARN] No se pudo usar chile_timezone: {e}")
        from datetime import datetime
        hour = datetime.now().hour
        return "AM" if hour < 14 else "PM"


def load_dataset(path: str) -> Dict[str, Any]:
    """Carga el dataset JSON"""
    print(f"[INFO] Cargando JSON desde {path}...")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("[INFO] JSON cargado correctamente.")
    return data


def build_compact_dashboard(dataset: Dict[str, Any]) -> str:
    """Dashboard compacto: 6 indicadores + sentiment sectorial"""

    SENTIMENT_MAP = {
        "Somewhat-Bullish": "Optimista",
        "Somewhat Bullish": "Optimista",
        "Bullish": "Muy Optimista",
        "Neutral": "Neutral",
        "Somewhat-Bearish": "Pesimista",
        "Somewhat Bearish": "Pesimista",
        "Bearish": "Muy Pesimista"
    }

    parts = []
    parts.append("```")
    parts.append("=" * 90)
    parts.append("DASHBOARD DIARIO (Variación Diaria)")
    parts.append("=" * 90)

    # Datos
    chile_ipsa = dataset.get("chile", {}).get("ipsa", {})
    sp500 = dataset.get("equity", {}).get("^GSPC", {})
    oil = dataset.get("commodities", {}).get("CL=F", {})
    copper = dataset.get("commodities", {}).get("HG=F", {})
    usdclp = dataset.get("fx", {}).get("CLP=X", {})
    bitcoin = dataset.get("crypto", {}).get("BTC", {})  # 🆕 Bitcoin

    headers = ["IPSA", "S&P-500", "PETRÓLEO", "COBRE", "USD/CLP", "BITCOIN"]

    changes = []
    for data in [chile_ipsa, sp500, oil, copper, usdclp, bitcoin]:
        change = data.get("change_1d") if data else None
        changes.append(f"{change:+.2f}%" if isinstance(change, (int, float)) else "N/A")

    closes = []
    closes.append(f"{chile_ipsa.get('close'):,.0f}" if chile_ipsa.get('close') else "N/A")
    closes.append(f"{sp500.get('close'):,.0f}" if sp500.get('close') else "N/A")
    oil_price = (oil.get("close") or oil.get("price")) if oil else None
    closes.append(f"${oil_price:.2f}" if isinstance(oil_price, (int, float)) else "N/A")
    copper_price = (copper.get("close") or copper.get("price")) if copper else None
    closes.append(f"${copper_price:.2f}" if isinstance(copper_price, (int, float)) else "N/A")
    usd_rate = (usdclp.get("close") or usdclp.get("rate")) if usdclp else None
    closes.append(f"${usd_rate:.2f}" if isinstance(usd_rate, (int, float)) else "N/A")
    btc_price = bitcoin.get("close") if bitcoin else None
    closes.append(f"${btc_price:,.0f}" if isinstance(btc_price, (int, float)) else "N/A")

    col_width = 15
    parts.append("".join([f"{h:^{col_width}}" for h in headers]))
    parts.append("".join([f"{c:^{col_width}}" for c in changes]))
    parts.append("".join([f"{cl:^{col_width}}" for cl in closes]))
    parts.append("=" * 90)
    parts.append("")
    
    # Sentiment Sectorial (NO son ganancias, son índices de sentimiento de noticias)
    alphavantage_global = dataset.get("alphavantage_global", {})
    sector_sentiment = alphavantage_global.get("sector_sentiment", {})

    if sector_sentiment:
        parts.append("SENTIMIENTO DE NOTICIAS POR SECTOR (escala -1 a +1, NO son retornos)")
        parts.append("=" * 90)

        sect_headers = ["TECNOLOGÍA", "FINANCIERO", "ENERGÍA", "SALUD", "CONSUMO"]
        sect_keys = ["technology", "financials", "energy", "healthcare", "consumer"]

        bars = []
        sentiments = []

        for key in sect_keys:
            data = sector_sentiment.get(key, {})
            score = data.get("score")
            label = data.get("label", "")

            # Barra visual: score va de -1 a +1, normalizar a 0-6 bloques
            if isinstance(score, (int, float)):
                # score de -1 a +1 -> 0 a 6 bloques
                blocks = int((score + 1) * 3)  # -1->0, 0->3, +1->6
                blocks = max(0, min(6, blocks))
                bar = "█" * blocks + "░" * (6 - blocks)
            else:
                bar = "N/A"
            bars.append(bar)

            sentiment_es = SENTIMENT_MAP.get(label, label)
            sentiments.append(sentiment_es)

        col_width = 13
        parts.append("".join([f"{h:^{col_width}}" for h in sect_headers]))
        parts.append("".join([f"{b:^{col_width}}" for b in bars]))
        parts.append("".join([f"{st:^{col_width}}" for st in sentiments]))

    parts.append("=" * 90)
    parts.append("```")
    parts.append("")

    return "\n".join(parts)


def build_news_context(dataset: Dict[str, Any], mode: str = "AM") -> str:
    """
    Construye el contexto RICO de noticias (del código antiguo)
    Con TODO el detalle necesario para que Claude genere buen contenido

    Args:
        dataset: Dataset con todas las noticias
        mode: "AM" o "PM" - si es PM, filtra duplicados del AM
    """
    parts = []

    # 🆕 Cargar contenido usado en AM para deduplicación (solo en modo PM)
    am_headlines: Set[str] = set()
    am_keywords: Set[str] = set()
    duplicate_count = 0

    if mode == "PM" and DEDUP_AVAILABLE:
        today_str = date.today().isoformat()
        am_content = get_am_used_content(today_str)
        am_headlines = set(am_content.get("headlines", []))
        am_keywords = set(kw.lower() for kw in am_content.get("keywords", []))
        print(f"[DEDUP] Cargado contenido AM: {len(am_headlines)} headlines, {len(am_keywords)} keywords")

    news_curated = dataset.get("news_curated", {})

    if news_curated:
        parts.append("\n# NOTICIAS CURADAS\n")

        # Hot Topics
        hot_topics = news_curated.get("cross_newsletter_insights", {}).get("hot_topics", {})
        if hot_topics:
            parts.append("## HOT TOPICS (mencionados 3+ veces):")
            for topic, count in sorted(hot_topics.items(), key=lambda x: x[1], reverse=True)[:5]:
                parts.append(f"- **{topic}**: {count} menciones")

        # Noticias por categoría con DETALLE COMPLETO
        curated_newsletters = news_curated.get("curated_newsletters", {})

        # Recopilar todas las noticias
        all_news = []
        for newsletter_key, newsletter_data in curated_newsletters.items():
            if "curated" not in newsletter_data:
                continue

            source = newsletter_data.get("source", newsletter_key)
            for news in newsletter_data["curated"].get("key_news", []):
                news["_source"] = source

                # 🆕 Marcar duplicados (modo PM)
                if mode == "PM" and am_headlines:
                    headline = news.get("headline", "")
                    news_keywords = set(kw.lower() for kw in news.get("keywords", []))

                    # Verificar si es duplicado
                    is_duplicate = False
                    if headline in am_headlines:
                        is_duplicate = True
                    elif news_keywords and len(news_keywords & am_keywords) >= 2:
                        # Si comparte 2+ keywords con AM, es probable duplicado
                        is_duplicate = True

                    if is_duplicate:
                        news["_is_am_duplicate"] = True
                        news["importance"] = "Low"  # Reducir importancia
                        duplicate_count += 1

                all_news.append(news)

        if mode == "PM" and duplicate_count > 0:
            parts.append(f"\n**Nota PM:** {duplicate_count} noticias ya reportadas en AM (marcadas como Low)\n")
        
        # Separar por importancia
        high_news = [n for n in all_news if n.get("importance") == "High"]
        medium_news = [n for n in all_news if n.get("importance") == "Medium"]
        low_news = [n for n in all_news if n.get("importance") == "Low"]
        
        # CATEGORÍAS CLAVE del reporte (siempre deben tener contenido si hay noticias)
        key_categories = ["Tech/IA", "Macro", "Geopolítica", "Chile", "Corporativo"]
        
        # Agrupar HIGH por categoría
        high_by_category = defaultdict(list)
        for news in high_news:
            cat = news.get("category", "Otros")
            high_by_category[cat].append(news)
        
        # Para cada categoría clave, agregar Medium/Low si no hay suficientes HIGH
        for key_cat in key_categories:
            # Buscar noticias Medium/Low de esta categoría
            medium_cat = [n for n in medium_news if key_cat in n.get("category", "")]
            low_cat = [n for n in low_news if key_cat in n.get("category", "")]
            
            # Si hay Medium o Low, agregarlas
            if medium_cat or low_cat:
                # Buscar la categoría exacta (puede ser "Macro", "Geopolítica", etc.)
                matching_categories = [cat for cat in high_by_category.keys() if key_cat in cat]
                
                if not matching_categories:
                    # Si no existe la categoría, buscar la primera que coincida en las noticias
                    for cat_name in [n.get("category", "") for n in medium_cat + low_cat]:
                        if key_cat in cat_name:
                            high_by_category[cat_name] = []
                            matching_categories = [cat_name]
                            break
                
                # Agregar Medium primero, luego Low
                for matching_cat in matching_categories[:1]:  # Solo la primera coincidencia
                    high_by_category[matching_cat].extend(medium_cat)
                    high_by_category[matching_cat].extend(low_cat[:3])  # Máximo 3 Low
        
        parts.append(f"\n## NOTICIAS HIGH IMPORTANCE ({len(high_news)} total):\n")
        parts.append("(Incluye noticias Medium/Low de categorías clave del reporte)\n")
        
        # Orden de prioridad
        priority_order = [
            "Mercados/RV", "Mercados/RF", "Mercados/FX", "Mercados/Crypto",
            "Commodities", "Macro", "Geopolítica", "Corporativo", "Tech/IA"
        ]
        
        for category in priority_order:
            if category in high_by_category:
                parts.append(f"### {category}:")
                for news in high_by_category[category][:5]:
                    headline = news.get("headline", "")
                    summary = news.get("summary", "")
                    data_points = news.get("data_points", [])
                    boosted = " 🔥" if news.get("boosted") else ""
                    
                    parts.append(f"- **{headline}**{boosted}")
                    if summary:
                        parts.append(f"  {summary}")
                    if data_points:
                        parts.append(f"  Datos: {', '.join(data_points[:3])}")
                    parts.append("")
        
        # Estadísticas
        stats = news_curated.get("statistics", {})
        if stats:
            parts.append(f"\n## Estadísticas:")
            parts.append(f"- Total noticias: {stats.get('total_news', 0)}")
            parts.append(f"- High importance: {stats.get('high_importance_news', 0)}")
            
            categories = stats.get("categories", {})
            if categories:
                parts.append(f"- Por categoría: {', '.join([f'{k} ({v})' for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]])}")
    
    # Sentiment
    sentiment = dataset.get("sentiment", {})
    if sentiment:
        sentiment_label = sentiment.get("sentiment", "N/A")
        parts.append(f"\n## Sentiment general: {sentiment_label}")
    
    return "\n".join(parts)


def build_detailed_tables(dataset: Dict[str, Any]) -> str:
    """Tablas detalladas para el FINAL (con Treasuries en basis points correctos)"""
    
    context_parts = []
    alphavantage_global = dataset.get("alphavantage_global", {})
    
    context_parts.append("```")
    context_parts.append("=" * 80)
    context_parts.append("ÍNDICES PRINCIPALES")
    context_parts.append("=" * 80)
    context_parts.append("")
    context_parts.append(f"{'ÍNDICE':<15} {'CIERRE':>12} {'1D':>10} {'MTD':>10} {'YTD':>10}")
    context_parts.append("-" * 80)
    
    # Equity
    equity = dataset.get("equity", {})
    priority_indices = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^STOXX50E", "^FTSE", "^N225"]
    
    name_map = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "DOW JONES",
        "^RUT": "RUSSELL 2000",
        "^STOXX50E": "STOXX 50",
        "^FTSE": "FTSE 100",
        "^N225": "NIKKEI 225"
    }
    
    for idx in priority_indices:
        data = equity.get(idx, {})
        if data and isinstance(data, dict):
            close = data.get("close")
            if close is None:
                continue
            
            name = name_map.get(idx, idx)
            change_1d = data.get("change_1d")
            change_mtd = data.get("change_mtd")
            change_ytd = data.get("change_ytd")
            
            close_str = f"{close:,.2f}"
            change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
            change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
            change_ytd_str = f"{change_ytd:+.2f}%" if isinstance(change_ytd, (int, float)) else "N/A"
            
            context_parts.append(f"{name:<15} {close_str:>12} {change_1d_str:>10} {change_mtd_str:>10} {change_ytd_str:>10}")
    
    # Chile
    chile_data = dataset.get("chile", {}).get("ipsa", {})
    if chile_data:
        context_parts.append("")
        context_parts.append("CHILE")
        context_parts.append("-" * 80)
        
        close = chile_data.get("close")
        change_1d = chile_data.get("change_1d")
        change_mtd = chile_data.get("change_mtd")
        change_ytd = chile_data.get("change_ytd")
        
        if close is not None:
            close_str = f"{close:,.2f}"
            change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
            change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
            change_ytd_str = f"{change_ytd:+.2f}%" if isinstance(change_ytd, (int, float)) else "N/A"
            
            context_parts.append(f"{'IPSA':<15} {close_str:>12} {change_1d_str:>10} {change_mtd_str:>10} {change_ytd_str:>10}")
    
    # Renta Fija - CON BASIS POINTS CORRECTOS
    treasury_data = alphavantage_global.get("treasury_yields", {}).get("yields", {})
    rates = dataset.get("rates_bonds", {})
    
    has_data = bool(rates) or bool(treasury_data)
    
    if has_data:
        context_parts.append("")
        context_parts.append("=" * 80)
        context_parts.append("RENTA FIJA / VOLATILIDAD")
        context_parts.append("=" * 80)
        context_parts.append("")
        context_parts.append(f"{'INSTRUMENTO':<20} {'YIELD/CIERRE':>12} {'1D':>10} {'MTD':>10}")
        context_parts.append("-" * 80)
        
        # Treasuries - mostrar nivel, calcular cambios solo si hay datos históricos
        if treasury_data:
            treasury_order = ["2year", "10year", "30year"]
            treasury_names = {
                "2year": "US Treasury 2Y",
                "10year": "US Treasury 10Y",
                "30year": "US Treasury 30Y"
            }
            
            for key in treasury_order:
                t_data = treasury_data.get(key, {})
                if t_data and isinstance(t_data, dict):
                    value = t_data.get("value")
                    if value is not None:
                        name = treasury_names.get(key, key)
                        yield_str = f"{value:.2f}%"
                        
                        # Calcular cambios en basis points SOLO SI HAY DATOS
                        prev = (t_data.get("previous") or {}).get("value") if isinstance(t_data.get("previous"), dict) else None
                        mstart = (t_data.get("month_start") or {}).get("value") if isinstance(t_data.get("month_start"), dict) else None
                        
                        def _bps(delta_pct_points):
                            return f"{delta_pct_points * 100:+.0f}bp"
                        
                        chg_1d_str = _bps(value - prev) if isinstance(prev, (int, float)) else "N/A"
                        chg_mtd_str = _bps(value - mstart) if isinstance(mstart, (int, float)) else "N/A"
                        
                        context_parts.append(f"{name:<20} {yield_str:>12} {chg_1d_str:>10} {chg_mtd_str:>10}")
        
        # ETFs y VIX
        rates_map = {
            "AGG": "AGG (Bonos)",
            "HYG": "HYG (High Yield)",
            "^VIX": "VIX (Volatilidad)"
        }
        
        for key, name in rates_map.items():
            data = rates.get(key, {})
            if data and isinstance(data, dict) and not data.get("error"):
                close = data.get("close")
                if close is None:
                    continue
                
                change_1d = data.get("change_1d")
                change_mtd = data.get("change_mtd")
                
                close_str = f"{close:.2f}"
                change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
                change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
                
                context_parts.append(f"{name:<20} {close_str:>12} {change_1d_str:>10} {change_mtd_str:>10}")
    
    # Commodities
    commodities = dataset.get("commodities", {})
    if commodities:
        context_parts.append("")
        context_parts.append("=" * 80)
        context_parts.append("COMMODITIES")
        context_parts.append("=" * 80)
        context_parts.append("")
        context_parts.append(f"{'COMMODITY':<20} {'PRECIO':>12} {'1D':>10} {'MTD':>10}")
        context_parts.append("-" * 80)
        
        commodity_map = {
            "GC=F": "Oro (oz)",
            "SI=F": "Plata (oz)",
            "HG=F": "Cobre (lb)",
            "CL=F": "Petróleo WTI (bbl)"
        }
        
        for key, name in commodity_map.items():
            data = commodities.get(key, {})
            if data and isinstance(data, dict):
                price = data.get("price") or data.get("close")
                if price is None:
                    continue
                
                change_1d = data.get("change_1d")
                change_mtd = data.get("change_mtd")
                
                price_str = f"${price:,.2f}"
                change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
                change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
                
                context_parts.append(f"{name:<20} {price_str:>12} {change_1d_str:>10} {change_mtd_str:>10}")
    
    # FX
    fx = dataset.get("fx", {})
    if fx:
        context_parts.append("")
        context_parts.append("=" * 80)
        context_parts.append("DIVISAS")
        context_parts.append("=" * 80)
        context_parts.append("")
        context_parts.append(f"{'PAR':<20} {'TIPO CAMBIO':>15} {'1D':>10} {'MTD':>10}")
        context_parts.append("-" * 80)
        
        fx_map = {
            "CLP=X": "USD/CLP",
            "EURUSD=X": "EUR/USD",
            "JPY=X": "USD/JPY",
            "MXN=X": "USD/MXN"
        }
        
        for key, name in fx_map.items():
            data = fx.get(key, {})
            if data and isinstance(data, dict):
                rate = data.get("rate") or data.get("close")
                if rate is None or data.get("error"):
                    continue
                
                change_1d = data.get("change_1d")
                change_mtd = data.get("change_mtd")
                
                rate_str = f"{rate:,.4f}"
                change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
                change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
                
                context_parts.append(f"{name:<20} {rate_str:>15} {change_1d_str:>10} {change_mtd_str:>10}")

    # 🆕 CRIPTOMONEDAS
    crypto = dataset.get("crypto", {})
    if crypto and (crypto.get("BTC") or crypto.get("ETH")):
        context_parts.append("")
        context_parts.append("=" * 80)
        context_parts.append("CRIPTOMONEDAS")
        context_parts.append("=" * 80)
        context_parts.append("")
        context_parts.append(f"{'CRIPTO':<20} {'PRECIO':>15} {'1D':>10} {'MTD':>10} {'YTD':>10}")
        context_parts.append("-" * 80)

        crypto_map = {
            "BTC": "Bitcoin (BTC)",
            "ETH": "Ethereum (ETH)",
        }

        for key, name in crypto_map.items():
            data = crypto.get(key, {})
            if data and isinstance(data, dict):
                price = data.get("close")
                if price is None:
                    continue

                change_1d = data.get("change_1d")
                change_mtd = data.get("change_mtd")
                change_ytd = data.get("change_ytd")

                price_str = f"${price:,.2f}"
                change_1d_str = f"{change_1d:+.2f}%" if isinstance(change_1d, (int, float)) else "N/A"
                change_mtd_str = f"{change_mtd:+.2f}%" if isinstance(change_mtd, (int, float)) else "N/A"
                change_ytd_str = f"{change_ytd:+.2f}%" if isinstance(change_ytd, (int, float)) else "N/A"

                context_parts.append(f"{name:<20} {price_str:>15} {change_1d_str:>10} {change_mtd_str:>10} {change_ytd_str:>10}")

        # Noticias crypto (si hay)
        crypto_news = crypto.get("news", [])
        if crypto_news and len(crypto_news) > 0:
            context_parts.append("")
            context_parts.append("Noticias crypto relevantes:")
            for news in crypto_news[:3]:  # Máximo 3 noticias
                title = news.get("title", "")
                sentiment = news.get("sentiment_label", "")
                if title:
                    context_parts.append(f"  - {title} [{sentiment}]")

    context_parts.append("=" * 80)
    context_parts.append("```")
    context_parts.append("")

    # Sentiment Sectorial Detallado
    sector_sentiment = alphavantage_global.get("sector_sentiment", {})
    if sector_sentiment:
        context_parts.append("```")
        context_parts.append("=" * 80)
        context_parts.append("SENTIMENT SECTORIAL (AlphaVantage)")
        context_parts.append("=" * 80)
        context_parts.append("")
        context_parts.append(f"{'SECTOR':<20} {'SCORE':>12} {'SENTIMENT':>20}")
        context_parts.append("-" * 80)
        
        sector_order = ["technology", "financials", "energy", "healthcare", "consumer"]
        
        for key in sector_order:
            data = sector_sentiment.get(key, {})
            if data and isinstance(data, dict):
                name = data.get("name", key)
                score = data.get("score")
                label = data.get("label", "")
                
                if score is not None:
                    score_str = f"{score:+.3f}"
                    context_parts.append(f"{name:<20} {score_str:>12} {label:>20}")
        
        context_parts.append("-" * 80)
        context_parts.append("Nota: Score > +0.25 = Muy Optimista | +0.15 a +0.25 = Optimista")
        context_parts.append("      -0.15 a +0.15 = Neutral | -0.25 a -0.15 = Pesimista | < -0.25 = Muy Pesimista")
        context_parts.append("=" * 80)
        context_parts.append("```")
        context_parts.append("")
    
    return "\n".join(context_parts)


def build_curated_context(dataset: Dict[str, Any], mode: str = "AM") -> str:
    """
    Construye contexto completo:
    1. Dashboard compacto (inicio)
    2. Noticias ricas (medio) - con deduplicación en PM
    3. Las tablas detalladas se agregan al FINAL después del texto de Claude
    """
    parts = []

    # Dashboard compacto
    parts.append(build_compact_dashboard(dataset))

    # Contenido rico de noticias (con deduplicación en modo PM)
    parts.append(build_news_context(dataset, mode))

    return "\n".join(parts)


def get_default_prompt(mode: str, audience: str) -> str:
    """Prompts por defecto"""

    # Obtener fecha actual con día de la semana
    fecha_hoy = get_fecha_completa()
    contexto_temporal = get_contexto_temporal(mode)

    if audience == "finanzas":
        return f"""Genera un reporte ejecutivo de mercados para gestores profesionales.

**FECHA DEL REPORTE: {fecha_hoy}** (Reporte {mode})

{contexto_temporal}

**IMPORTANTE:** El dashboard compacto ya está incluido al inicio. NO lo reproduzcas.

⚠️ REGLAS CRÍTICAS PARA DATOS NUMÉRICOS ⚠️

1. FUENTE ÚNICA DE VERDAD: Las tablas detalladas al final del contexto
   - SOLO menciona precios y porcentajes que aparezcan en esas tablas
   - Si un dato NO está en la tabla → NO lo menciones
   - NO inventes datos de índices que no aparecen (ej: si Dow Jones no está, no lo menciones)

2. VALIDACIÓN DE SIGNOS Y DIRECCIÓN:
   - Si tabla muestra cambio NEGATIVO (-X%) → El activo CAYÓ, NO alcanzó "máximos" ni "récords"
   - Si tabla muestra cambio POSITIVO (+X%) → El activo SUBIÓ
   - NO uses palabras como "récords intradía" o "máximos históricos" si el cierre es NEGATIVO

3. PRECIOS INTRADÍA vs CIERRE:
   - Las noticias pueden mencionar precios intradía diferentes
   - TÚ solo reportas CIERRES que aparecen en las tablas
   - Si quieres mencionar intradía: "tocó máximos intradía pero cerró en..." (usando precio de tabla)

4. ANTES DE ESCRIBIR CUALQUIER NÚMERO:
   a) Busca el número EXACTO en la tabla al final
   b) Verifica que coincida
   c) Si no coincide o no existe → NO lo escribas

5. LENGUAJE PROFESIONAL PARA CLIENTES:
   ❌ NUNCA digas: "El dataset no incluye...", "No hay información en el dataset...", "El dataset disponible..."
   ✅ SIEMPRE usa: "No se registraron desarrollos significativos...", "La sesión no presentó novedades destacadas...", "No hubo anuncios relevantes..."
   
   Si hay pocas noticias pero existen: Escribe un párrafo breve con lo que hay
   Si NO hay noticias de un tema: "La sesión no presentó desarrollos destacados en [tema]"

6. COMPLETAR TODAS LAS SECCIONES DEL REPORTE:
   - Economía
   - Política y Geopolítica  
   - Inteligencia Artificial y Tecnología
   - Chile y LatAm
   - Mercados por Activo
   
   IMPORTANTE: Si hay noticias de una categoría (aunque sean Medium o Low importance), 
   DEBES escribir sobre ellas. El contexto incluye noticias Medium/Low de categorías clave 
   precisamente para que NUNCA dejes una sección vacía o con "no hay información".

EJEMPLO CORRECTO:
"El oro cerró en $4,594.40 (-0.22%) tras volatilidad intradía"

EJEMPLO INCORRECTO:
"El oro alcanzó máximos de $4,604" (si tabla dice $4,594.40 con cambio negativo)

Estructura:
1. Resumen Ejecutivo (bullets)
2. Economía
3. Política y Geopolítica
4. Inteligencia Artificial y Tecnología
5. Chile y LatAm
6. Mercados por Activo
7. Sentimiento y Volatilidad
8. Agenda
9. Lectura / Idea Táctica
10. Glosario

Las tablas detalladas se agregarán automáticamente al final.

TONO: Profesional, técnico, directo. Sin emojis excepto 🔥 para hot topics."""
    
    else:
        return f"""Genera un resumen de mercados accesible para audiencia general.

**FECHA DEL REPORTE: {fecha_hoy}** (Reporte {mode})

{contexto_temporal}

**IMPORTANTE:** El dashboard compacto ya está incluido al inicio. NO lo reproduzcas.

⚠️ REGLAS CRÍTICAS PARA DATOS NUMÉRICOS ⚠️

1. FUENTE ÚNICA DE VERDAD: Las tablas detalladas al final del contexto
   - SOLO menciona precios y porcentajes que aparezcan en esas tablas
   - Si un dato NO está en la tabla → NO lo menciones

2. VALIDACIÓN DE SIGNOS:
   - Si tabla muestra cambio NEGATIVO (-X%) → El activo CAYÓ
   - Si tabla muestra cambio POSITIVO (+X%) → El activo SUBIÓ  
   - NO digas "máximos" o "récords" si el cambio es NEGATIVO

3. USA LOS PRECIOS DE CIERRE DE LAS TABLAS:
   - Las noticias pueden mencionar precios diferentes (intradía)
   - TÚ solo reportas los precios de CIERRE que están en las tablas

4. Si no estás seguro de un número → NO lo menciones

5. LENGUAJE PROFESIONAL:
   ❌ NUNCA: "El dataset no incluye...", "No hay información en el dataset..."
   ✅ SIEMPRE: "No hubo noticias destacadas sobre...", "La sesión no presentó novedades en..."
   
   Si hay pocas noticias: Escribe lo que hay, aunque sea breve
   Si NO hay noticias: "No hubo desarrollos destacados en [tema] durante la sesión"

6. ESCRIBIR TODAS LAS SECCIONES:
   Economía, Política, IA y Tecnología, Chile y LatAm, Mercados
   
   Si hay noticias de un tema (aunque sean pocas), escríbelas.
   El sistema te proporciona noticias de categorías importantes para que nunca 
   dejes una sección vacía.

Estructura:
1. Resumen Ejecutivo
2. Economía (lenguaje simple)
3. Política y Geopolítica
4. Inteligencia Artificial y Tecnología
5. Chile y LatAm
6. Mercados por Activo (breve)
7. Sentimiento y Volatilidad
8. Agenda
9. Idea Táctica
10. Glosario

Las tablas detalladas se agregarán automáticamente al final.

TONO: Claro, accesible, informativo."""


def load_external_prompt(mode: str, audience: str) -> str:
    """Carga prompt desde archivo externo si existe, agregando fecha y contexto temporal"""
    filename = f"prompt_{audience}_{mode}.txt"

    # Obtener fecha y contexto temporal (siempre se agregan)
    fecha_hoy = get_fecha_completa()
    contexto_temporal = get_contexto_temporal(mode)

    # Header con fecha y contexto que se agrega a cualquier prompt
    header_temporal = f"""**FECHA DEL REPORTE: {fecha_hoy}** (Reporte {mode})

{contexto_temporal}

"""

    if os.path.exists(filename):
        print(f"[INFO] Usando prompt externo: {filename}")
        with open(filename, "r", encoding="utf-8") as f:
            prompt_externo = f.read()
        # Agregar header temporal al inicio del prompt externo
        return header_temporal + prompt_externo

    print(f"[INFO] Usando prompt por defecto ({mode}, {audience})")
    return get_default_prompt(mode, audience)


def generate_report_with_anthropic(context: str, prompt: str, mode: str, system_prompt: str = None) -> str:
    """Genera reporte usando Anthropic Claude"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no encontrada")

    client = Anthropic(api_key=api_key)

    print(f"[INFO] Generando reporte con Anthropic Claude (modo: {mode})...")

    sys_prompt = system_prompt or SYSTEM_PROMPT

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        system=sys_prompt,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\nCONTEXTO:\n{context}"
            }
        ]
    )

    return response.content[0].text


def review_report(report_text: str, dataset: Dict[str, Any], detailed_tables: str, mode: str = "AM") -> str:
    """
    QA Review: Verifica coherencia entre narrativa y datos.

    Args:
        report_text: Reporte generado por Claude (sin tablas finales)
        dataset: Dataset original con todos los datos
        detailed_tables: Tablas detalladas que se agregarán al final
        mode: "AM" o "PM" — para verificar coherencia temporal

    Returns:
        Reporte corregido (o igual si no hay errores)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no encontrada")

    client = Anthropic(api_key=api_key)

    print("[QA] Iniciando revisión de coherencia...")

    # Extraer datos clave del dataset para validación
    validation_data = _extract_validation_data(dataset)

    qa_system_prompt = f"""Eres un revisor QA especializado en reportes financieros de mercado.

Tu trabajo es verificar que el reporte sea COHERENTE, PRECISO y PROFESIONAL.

TIPO DE REPORTE: {mode}

REGLAS GENERALES:
1. Sé CONSERVADOR: solo corrige errores CLAROS y OBJETIVOS
2. NO reescribas el estilo ni mejores la redacción
3. NO agregues información nueva ni inventes datos
4. NO elimines contenido correcto
5. Mantén el formato markdown exacto (incluido el dashboard entre ```)

═══════════════════════════════════════════════════════════════
ERRORES A DETECTAR Y CORREGIR (16 reglas)
═══════════════════════════════════════════════════════════════

── DATOS VS NARRATIVA ──

1. DIRECCIÓN INCORRECTA: Si dice "subió"/"avanzó"/"rally" pero el cambio es negativo (o viceversa).
   Verificar: subió/avanzó/repuntó/rally → dato positivo. Cayó/retrocedió/bajó → dato negativo.

2. PRECIOS INEXISTENTES: Si menciona un precio, nivel o porcentaje que NO está en los datos de referencia.
   Si el dato no existe → eliminarlo o reemplazar con lenguaje genérico.

3. DASHBOARD ↔ TEXTO: Los números citados en la narrativa DEBEN coincidir EXACTAMENTE con el dashboard y las tablas.
   Incorrecto: Dashboard dice IPSA +2.40% pero texto dice "+2.5%" o "+2.4%" (falta el cero).
   Correcto: Usar exactamente "+2.40%" como aparece en la tabla.

4. MAGNITUD ABSURDA: Verificar que los valores estén en rangos razonables:
   - IPSA: 4,000–15,000 pts
   - S&P 500: 3,000–8,000 pts
   - Oro: $1,500–$6,000/oz
   - Petróleo WTI: $40–$150/bbl
   - Cobre: $2.50–$7.00/lb
   - USD/CLP: $700–$1,100
   - Bitcoin: $15,000–$200,000
   - VIX: 8–80
   Si un valor cae fuera de estos rangos, verificar contra las tablas. Si la tabla lo confirma, dejarlo.

── LÓGICA FINANCIERA ──

5. SIGNO VS DIRECCIÓN CAMBIARIA Y TONO:
   Si USD/CLP sube (+X%), el peso se DEBILITÓ/DEPRECIÓ (no se apreció). Esto es NEGATIVO.
   Si USD/CLP baja (-X%), el peso se FORTALECIÓ/APRECIÓ. Esto es POSITIVO.
   Error frecuente: "el peso se apreció" cuando USD/CLP subió → corregir a "el peso se depreció".
   PROHIBIDO usar lenguaje positivo para depreciación del peso:
   - "beneficiándose", "avanzó", "ganó", "impulsado" → NO cuando el peso se deprecia.
   - El CLP NO es un activo. Depreciación = debilitamiento = negativo para Chile.
   - Correcto: "El peso se depreció 1.41% frente al dólar, reflejando presión sobre la moneda local"
   - Incorrecto: "El dólar avanzó beneficiándose del apetito por riesgo"
   Misma lógica para USD/MXN. EUR/USD es inverso (sube = euro fuerte, dólar débil).

6. VIX INVERTIDO: VIX baja = MENOS miedo/volatilidad (positivo para mercados).
   VIX sube = MÁS miedo/volatilidad (negativo para mercados).
   Error: "El VIX bajó, reflejando mayor nerviosismo" → corregir a "menor nerviosismo".

7. BASIS POINTS VS PORCENTAJE: Los yields de bonos se mueven en BASIS POINTS (bp), no en porcentaje.
   1bp = 0.01 puntos porcentuales. "El Treasury subió 4bp" = subió 0.04pp (de 4.02% a 4.06%).
   Error: "El yield subió 4%" → significaría de 4% a 8%, absurdo. Corregir a "+4bp".

8. MTD/YTD CONTRADICE NARRATIVA: Si 1D es positivo pero MTD es muy negativo, no decir "rally sostenido"
   ni "tendencia alcista". Un día positivo dentro de un mes negativo es un "repunte" o "recuperación parcial".

── COHERENCIA TEMPORAL ──

9. TEMPORALIDAD DATOS VS REPORTE:
   Las tablas contienen precios/cierres/variaciones. La regla: si una frase cita un DATO NUMÉRICO
   de las tablas, la referencia temporal debe ser coherente con el tipo de reporte.

   Si el reporte es PM:
   - Las tablas tienen cierres de HOY → frases que citan esos datos deben decir "hoy", no "ayer".
   - INCORRECTO: "El IPSA experimentó ayer un avance de +2.40%" (dato de la tabla de hoy)
   - CORRECTO: "El IPSA avanzó hoy +2.40%"
   - PERO "ayer" es válido para EVENTOS pasados sin citar datos de las tablas:
     OK: "Tras los datos de empleo publicados ayer, los mercados reaccionaron hoy con alzas"

   Si el reporte es AM:
   - Las tablas tienen cierres de la sesión ANTERIOR → frases que citan esos datos usan "ayer" (o "el viernes" si lunes).
   - PERO "hoy" es válido para Asia/Europa que ya operaron, o eventos de esta mañana.

   NO hagas reemplazos ciegos. Evalúa frase por frase: ¿cita un dato de las tablas? → verificar coherencia.

── COMPLETITUD Y ESTRUCTURA ──

10. SECCIONES FALTANTES: El reporte DEBE contener estas secciones (verificar que existan):
    - Resumen Ejecutivo
    - Economía
    - Política y Geopolítica
    - Inteligencia Artificial y Tecnología
    - Chile y LatAm
    - Mercados por Activo
    - Sentimiento y Volatilidad
    - Agenda
    - Lectura / Idea Táctica
    - Glosario
    Si falta una sección, NO la inventes. Solo reporta el error dejando el reporte como está.

11. CRYPTO FALTANTE: Si los datos incluyen Bitcoin/ETH con precios válidos, DEBEN mencionarse
    en la sección "Mercados por Activo" bajo un sub-apartado de Criptomonedas.

── LENGUAJE PROFESIONAL ──

12. LENGUAJE PROHIBIDO (para clientes): Detectar y reemplazar:
    - "El dataset no incluye..." → "No se registraron desarrollos significativos en..."
    - "No hay datos en el JSON..." → "La sesión no presentó novedades destacadas en..."
    - "No hay información en el dataset..." → "No hubo anuncios relevantes sobre..."
    - "El dataset disponible..." → eliminar referencia al dataset
    - "según el contexto proporcionado..." → eliminar
    Cualquier mención a "dataset", "JSON", "contexto proporcionado", "datos disponibles" como fuente
    visible debe eliminarse. El reporte es para CLIENTES, no para ingenieros.

13. MONEDA CONFUSA: En contexto de Chile, "$" sin especificar = pesos chilenos (CLP), NO dólares.
    - "$256 mil millones" en noticia de Chile = CLP 256 mil millones
    - Solo usar "USD" si la fuente dice explícitamente "USD", "dólares estadounidenses" o "US$"
    - NO convertir montos entre monedas por cuenta propia
    Si el texto dice "USD X" para un monto local sin fuente que lo respalde → corregir a "CLP" o "$X (CLP)".

── COHERENCIA INTERNA ──

14. CONTRADICCIONES ENTRE SECCIONES: Si una sección dice "mercados optimistas" y otra dice
    "aversión al riesgo generalizada" sobre el MISMO día → resolver la contradicción usando los datos.

15. DOBLE REPORTE: Si el mismo hecho se repite VERBATIM o casi idéntico en 2+ secciones,
    mantenerlo solo en la sección más relevante y eliminar la repetición innecesaria.
    Excepciones: el Resumen Ejecutivo puede resumir lo que se detalla después — eso es válido.

16. CAUSALIDAD INVENTADA: Si el texto atribuye un movimiento de precio a una causa específica,
    verificar que esa causa esté mencionada en las noticias/datos proporcionados.
    Si no hay evidencia → suavizar: "posiblemente influenciado por" en vez de "impulsado por".

17. SIGLAS CHILENAS: En contexto de Chile y LatAm, verificar uso correcto de siglas:
    - CFA = Consejo Fiscal Autónomo (organismo fiscal chileno), NO CFA Institute/certificación.
    - BCCh = Banco Central de Chile (no "BCC" ni "BC")
    - CMF = Comisión para el Mercado Financiero
    - TPM = Tasa de Política Monetaria
    - Si el texto usa "CFA" refiriéndose a la certificación financiera en contexto chileno → corregir.

═══════════════════════════════════════════════════════════════

FORMATO DE RESPUESTA:
- Si HAY errores: Devuelve el reporte COMPLETO con TODAS las correcciones aplicadas
- Si NO hay errores: Devuelve exactamente "SIN_ERRORES"

NO incluyas comentarios, explicaciones ni notas. Solo el reporte corregido o "SIN_ERRORES"."""

    qa_prompt = f"""REPORTE A REVISAR (tipo: {mode}):
---
{report_text}
---

DATOS DE REFERENCIA (fuente de verdad):
---
{validation_data}
---

TABLAS DETALLADAS (referencia adicional):
---
{detailed_tables}
---

Aplica las 16 reglas de validación. Corrige TODOS los errores encontrados.
Si todo está correcto, responde exactamente: SIN_ERRORES"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        system=qa_system_prompt,
        messages=[
            {
                "role": "user",
                "content": qa_prompt
            }
        ]
    )

    result = response.content[0].text.strip()

    if result == "SIN_ERRORES":
        print("[QA] ✓ Reporte sin errores detectados")
        return report_text
    else:
        print("[QA] ⚠ Se aplicaron correcciones al reporte")
        return result


def _extract_validation_data(dataset: Dict[str, Any]) -> str:
    """Extrae datos clave del dataset para validación QA con dirección explícita"""
    parts = []

    def _dir(change):
        """Retorna dirección textual del cambio"""
        if not isinstance(change, (int, float)): return "sin dato"
        if change > 0: return "SUBIÓ"
        if change < 0: return "BAJÓ"
        return "sin cambio"

    def _fmt_change(change):
        """Formatea cambio con signo explícito"""
        if isinstance(change, (int, float)):
            return f"{change:+.2f}%"
        return "N/A"

    # Equity
    equity = dataset.get("equity", {})
    name_map = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "DOW JONES",
                "^RUT": "RUSSELL 2000", "^STOXX50E": "STOXX 50", "^FTSE": "FTSE 100", "^N225": "NIKKEI 225"}
    if equity:
        parts.append("ÍNDICES (fuente de verdad para precios):")
        for idx, data in equity.items():
            if isinstance(data, dict) and data.get("close"):
                change = data.get("change_1d")
                name = name_map.get(idx, idx)
                parts.append(f"  {name}: cierre={data['close']:,.2f}, 1D={_fmt_change(change)} ({_dir(change)})")

    # Chile
    chile_ipsa = dataset.get("chile", {}).get("ipsa", {})
    if chile_ipsa and chile_ipsa.get("close"):
        change = chile_ipsa.get("change_1d")
        parts.append(f"\nIPSA: cierre={chile_ipsa['close']:,.2f}, 1D={_fmt_change(change)} ({_dir(change)})")
        mtd = chile_ipsa.get("change_mtd")
        ytd = chile_ipsa.get("change_ytd")
        if isinstance(mtd, (int, float)) or isinstance(ytd, (int, float)):
            parts.append(f"  MTD={_fmt_change(mtd)}, YTD={_fmt_change(ytd)}")

    # Commodities
    commodities = dataset.get("commodities", {})
    commodity_names = {"GC=F": "Oro", "SI=F": "Plata", "HG=F": "Cobre", "CL=F": "Petróleo WTI"}
    if commodities:
        parts.append("\nCOMMODITIES:")
        for key, data in commodities.items():
            if isinstance(data, dict):
                price = data.get("price") or data.get("close")
                change = data.get("change_1d")
                if price:
                    name = commodity_names.get(key, key)
                    parts.append(f"  {name}: precio=${price:,.2f}, 1D={_fmt_change(change)} ({_dir(change)})")

    # FX — con interpretación cambiaria explícita
    fx = dataset.get("fx", {})
    if fx:
        parts.append("\nDIVISAS (ATENCIÓN: dirección cambiaria):")
        for key, data in fx.items():
            if isinstance(data, dict) and not data.get("error"):
                rate = data.get("rate") or data.get("close")
                change = data.get("change_1d")
                if rate:
                    fx_dir = _dir(change)
                    # Interpretación cambiaria explícita
                    if key == "CLP=X":
                        if isinstance(change, (int, float)):
                            peso_dir = "peso DEPRECIÓ (se debilitó)" if change > 0 else "peso APRECIÓ (se fortaleció)"
                        else:
                            peso_dir = ""
                        parts.append(f"  USD/CLP: rate={rate:,.2f}, 1D={_fmt_change(change)} → {peso_dir}")
                    elif key == "MXN=X":
                        if isinstance(change, (int, float)):
                            mxn_dir = "peso MXN DEPRECIÓ" if change > 0 else "peso MXN APRECIÓ"
                        else:
                            mxn_dir = ""
                        parts.append(f"  USD/MXN: rate={rate:,.4f}, 1D={_fmt_change(change)} → {mxn_dir}")
                    elif key == "EURUSD=X":
                        if isinstance(change, (int, float)):
                            eur_dir = "euro SUBIÓ / dólar BAJÓ" if change > 0 else "euro BAJÓ / dólar SUBIÓ"
                        else:
                            eur_dir = ""
                        parts.append(f"  EUR/USD: rate={rate:,.4f}, 1D={_fmt_change(change)} → {eur_dir}")
                    else:
                        parts.append(f"  {key}: rate={rate:,.4f}, 1D={_fmt_change(change)} ({fx_dir})")

    # Crypto
    crypto = dataset.get("crypto", {})
    if crypto:
        parts.append("\nCRIPTOMONEDAS (DEBEN mencionarse si hay datos):")
        for key, data in crypto.items():
            if isinstance(data, dict) and data.get("close"):
                change = data.get("change_1d")
                parts.append(f"  {key}: cierre=${data['close']:,.2f}, 1D={_fmt_change(change)} ({_dir(change)})")

    # Treasury yields
    treasury = dataset.get("alphavantage_global", {}).get("treasury_yields", {}).get("yields", {})
    if treasury:
        parts.append("\nTREASURIES (movimientos en BASIS POINTS, no %):")
        treasury_names = {"2year": "UST 2Y", "10year": "UST 10Y", "30year": "UST 30Y"}
        for key, data in treasury.items():
            if isinstance(data, dict) and data.get("value"):
                name = treasury_names.get(key, key)
                value = data["value"]
                prev = (data.get("previous") or {}).get("value") if isinstance(data.get("previous"), dict) else None
                if isinstance(prev, (int, float)):
                    bp_change = (value - prev) * 100
                    parts.append(f"  {name}: yield={value:.2f}%, cambio={bp_change:+.0f}bp")
                else:
                    parts.append(f"  {name}: yield={value:.2f}%")

    # VIX
    rates = dataset.get("rates_bonds", {})
    vix_data = rates.get("^VIX", {})
    if isinstance(vix_data, dict) and vix_data.get("close"):
        vix_close = vix_data["close"]
        vix_change = vix_data.get("change_1d")
        vix_interp = ""
        if isinstance(vix_change, (int, float)):
            vix_interp = "→ MENOS miedo/volatilidad" if vix_change < 0 else "→ MÁS miedo/volatilidad"
        parts.append(f"\nVIX: {vix_close:.2f}, 1D={_fmt_change(vix_change)} {vix_interp}")

    return "\n".join(parts)


def generate_for_client(json_path: str, mode: str, system_prompt: str = None, output_dir=None) -> str:
    """Genera reporte para un cliente. Retorna path al .md."""
    dataset = load_dataset(json_path)
    context = build_curated_context(dataset, mode)
    detailed_tables = build_detailed_tables(dataset)

    prompt = load_external_prompt(mode, "finanzas")
    report_text = generate_report_with_anthropic(context, prompt, mode, system_prompt=system_prompt)
    report_text = review_report(report_text, dataset, detailed_tables, mode)
    full_report = report_text + "\n\n" + detailed_tables

    today = date.today()
    filename = f"daily_report_{mode}_{today.strftime('%Y-%m-%d')}.md"
    out_path = Path(output_dir) / filename if output_dir else Path(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_report)
    print(f"[OK] Guardado: {out_path}")
    return str(out_path)


def main():
    """Función principal"""
    import sys

    # Argumentos
    if len(sys.argv) < 2:
        json_path = INPUT_JSON
    else:
        json_path = sys.argv[1]

    # Detectar modo (AM/PM)
    if len(sys.argv) >= 3:
        mode = sys.argv[2].upper()
    else:
        mode = detect_report_mode()
    
    print(f"[INFO] Modo: {mode}")
    
    # Cargar dataset
    dataset = load_dataset(json_path)
    
    # Construir contexto (dashboard + noticias ricas, con deduplicación en PM)
    context = build_curated_context(dataset, mode)
    
    # Construir tablas detalladas (una sola vez, se reutilizan)
    detailed_tables = build_detailed_tables(dataset)

    # Generar reportes
    for audience in ["finanzas", "no_finanzas"]:
        print(f"\n[INFO] Generando reporte {mode} - {audience}...")

        prompt = load_external_prompt(mode, audience)
        report_text = generate_report_with_anthropic(context, prompt, mode)

        # QA Review: verificar coherencia datos vs narrativa + temporal
        report_text = review_report(report_text, dataset, detailed_tables, mode)

        # Agregar tablas detalladas al FINAL (después del QA review)
        full_report = report_text + "\n\n" + detailed_tables

        # Guardar
        today = date.today()
        filename = f"daily_report_{mode}_{audience}_{today.strftime('%Y-%m-%d')}.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(full_report)

        print(f"[OK] Guardado: {filename}")
    
    print("\n[OK] ¡Reportes generados exitosamente!")


if __name__ == "__main__":
    main()

# Proteccion de encoding para Windows (evita errores con emojis en consola)
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import json
from datetime import date, timedelta, datetime, time
from typing import Dict, List, Any, Optional
import requests
import imaplib
import email
from email.header import decode_header
from html import unescape
import re
import yfinance as yf
import feedparser
from openai import OpenAI
from dotenv import load_dotenv

# WSJ PDF Parser (coloca wsj_pdf_parser.py en el mismo directorio)
try:
    from wsj_pdf_parser import load_wsj_pdf_content
    WSJ_PDF_AVAILABLE = True
except ImportError:
    print("[WARN] wsj_pdf_parser.py no encontrado - WSJ PDF deshabilitado")
    WSJ_PDF_AVAILABLE = False

# AlphaVantage Integration (coloca alphavantage_integration.py en el mismo directorio)
try:
    from alphavantage_integration import (
        fetch_all_alphavantage_data,
        fetch_crypto_prices,
        fetch_crypto_news,
        # 🆕 Nuevas funciones de noticias mejoradas
        fetch_news_by_portfolio,
        fetch_news_categorized,
        fetch_news_with_sentiment_summary,
        calculate_sentiment_summary,
        DEFAULT_NEWS_TOPICS,
        DEFAULT_PORTFOLIO_TICKERS
    )
    ALPHAVANTAGE_AVAILABLE = True
except ImportError:
    print("[WARN] alphavantage_integration.py no encontrado - AlphaVantage deshabilitado")
    ALPHAVANTAGE_AVAILABLE = False

# AlphaVantage Global Expansion (coloca alphavantage_global_expansion.py en el mismo directorio)
try:
    from alphavantage_global_expansion import fetch_global_expansion_data
    ALPHAVANTAGE_GLOBAL_AVAILABLE = True
except ImportError:
    print("[WARN] alphavantage_global_expansion.py no encontrado - Expansión global deshabilitada")
    ALPHAVANTAGE_GLOBAL_AVAILABLE = False

# IPSA Integration (coloca ipsa_integration.py en el mismo directorio)
try:
    from ipsa_integration import calculate_ipsa_complete
    IPSA_INTEGRATION_AVAILABLE = True
except ImportError:
    print("[WARN] ipsa_integration.py no encontrado - IPSA integration deshabilitada")
    IPSA_INTEGRATION_AVAILABLE = False

# Newsletter Curator Enhanced (coloca newsletter_curator.py en el mismo directorio)
try:
    from newsletter_curator import curate_all_newsletters_enhanced
    NEWSLETTER_CURATOR_AVAILABLE = True
except ImportError:
    print("[WARN] newsletter_curator.py no encontrado - Newsletter curation deshabilitada")
    NEWSLETTER_CURATOR_AVAILABLE = False

# Chile Timezone (coloca chile_timezone.py en el mismo directorio)
try:
    from chile_timezone import parse_email_date_to_chile, get_chile_now, get_chile_datetime_str
    CHILE_TIMEZONE_AVAILABLE = True
except ImportError:
    print("[WARN] chile_timezone.py no encontrado - Usando timezone local sin conversión")
    CHILE_TIMEZONE_AVAILABLE = False

print(f"[DEBUG] Python en uso: {sys.version}")

# Cargar variables de entorno desde .env (si existe)
load_dotenv()

# ------------------ LÍMITES DE TEXTO PARA OPTIMIZAR CONTEXTO ----------------
MAX_NEWSLETTER_CHARS = 12000  # ~3000 tokens por newsletter
MAX_DF_RESUMEN_CHARS = 20000  # ~5000 tokens para el resumen completo
MAX_RSS_ITEMS = 5  # Limitar noticias RSS
MAX_NEWSAPI_ITEMS = 5  # Limitar noticias NewsAPI

# ------------------ SENTIMENT ANALYSIS KEYWORDS ------------------------------

POSITIVE_KEYWORDS = {
    # Español - Mercados
    'subió', 'sube', 'suben', 'alza', 'alzas', 'rally', 'ganancias', 'ganancia',
    'avance', 'avances', 'récord', 'record', 'máximo', 'maximos', 'optimismo',
    'optimista', 'recuperación', 'recupera', 'crecimiento', 'crece', 'expansión',
    'aumentó', 'aumenta', 'aumentan', 'fortalece', 'fortalecimiento', 'impulsa',
    'impulso', 'repunta', 'repunte', 'mejora', 'mejoran', 'positivo', 'positiva',
    'favorable', 'favorables', 'sólido', 'solida', 'robusto', 'robusta',
    # Inglés - Markets
    'gains', 'gain', 'rally', 'rallies', 'surge', 'surges', 'advance', 'advances',
    'growth', 'grows', 'recovery', 'recovers', 'optimism', 'optimistic',
    'strengthens', 'strength', 'rises', 'rise', 'climbs', 'climb', 'jumps', 'jump',
    'soars', 'soar', 'positive', 'upbeat', 'robust', 'solid', 'strong', 'improvement',
    'improved', 'improves', 'higher', 'peak', 'record',
}

NEGATIVE_KEYWORDS = {
    # Español - Mercados
    'cayó', 'cae', 'caen', 'caída', 'caidas', 'baja', 'bajas', 'bajan',
    'pérdidas', 'perdida', 'retroceso', 'retroceden', 'desplome', 'desploma',
    'mínimo', 'minimos', 'crisis', 'recesión', 'recesion', 'contracción',
    'temores', 'temor', 'preocupación', 'preocupacion', 'preocupa',
    'disminuyó', 'disminuye', 'disminuyen', 'debilita', 'debilitamiento',
    'presiona', 'presión', 'presion', 'cede', 'ceden', 'deterioro', 'deteriora',
    'negativo', 'negativa', 'adverso', 'adversa', 'débil', 'debil',
    # Inglés - Markets
    'falls', 'fall', 'decline', 'declines', 'losses', 'loss', 'drop', 'drops',
    'tumbles', 'tumble', 'plunges', 'plunge', 'plummets', 'plummet',
    'crisis', 'recession', 'concerns', 'concern', 'fears', 'fear', 'worried',
    'weakens', 'weakness', 'slides', 'slide', 'negative', 'adverse', 'weak',
    'lower', 'decreased', 'decreases', 'worse', 'worsen', 'deteriorate',
}

# Archivo para guardar historial de sentiment
SENTIMENT_HISTORY_FILE = "sentiment_history.json"

# ------------------ CONFIG MERCADO -------------------------------------------

EQUITY_TICKERS: Dict[str, str] = {
    # US
    "^GSPC": "S&P 500 Index",
    "^DJI": "Dow Jones Industrial Average",  # AGREGADO
    "^IXIC": "Nasdaq Composite",
    # Europa
    "^STOXX50E": "Euro Stoxx 50",
    "^FTSE": "FTSE 100 (UK)",
    "^GDAXI": "DAX (Alemania)",
    "^FCHI": "CAC 40 (Francia)",
    # Asia
    "^N225": "Nikkei 225 (Japón)",
    "^HSI": "Hang Seng (Hong Kong)",
    "000001.SS": "Shanghai Composite (China)",
    # LatAm
    "^BVSP": "Bovespa (Brasil)",
    "^MXX": "IPC (México)",
    # Chile
    "^IPSA": "IPSA Chile",
    # Emerging Markets
    "EEM": "MSCI Emerging Markets ETF",
}

BOND_VOL_TICKERS: Dict[str, str] = {
    "AGG": "US Aggregate Bond ETF",
    "HYG": "US High Yield Bond ETF",
    "^VIX": "Volatility Index (VIX)",
}

FX_TICKERS: Dict[str, str] = {
    "DXY": "US Dollar Index",
    "EURUSD=X": "EUR/USD",
    "JPY=X": "USD/JPY",
    "MXN=X": "USD/MXN",
    "BRL=X": "USD/BRL",
    "CLP=X": "USD/CLP (mercado spot)",  # Este es el dólar de MERCADO
}


COMMODITY_TICKERS: Dict[str, str] = {
    "CL=F": "WTI Crude Oil (futuro)",
    "BZ=F": "Brent Crude Oil (futuro)",
    "GC=F": "Gold (Oro, futuro)",
    "HG=F": "Copper (Cobre, futuro)",  # CRÍTICO para Chile y IA
    "CPER": "United States Copper Index Fund (ETF cobre)",
}

BCCH_BDE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

# Series del Banco Central de Chile
BCCH_SERIES: Dict[str, str] = {
    "tpm": "F022.TPM.TIN.D001.NO.Z.D",   # Tasa de política monetaria diaria
    "dolar_obs": "F073.TCO.PRE.Z.D",     # Dólar observado (diario)
    "uf": "F073.UFF.PRE.Z.D",            # UF diaria
    "ipsa": "F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D",  # IPSA - Nivel (índice diario)
}

RSS_FEEDS: Dict[str, str] = {
    # === US/GLOBAL ===
    "Reuters Top News": "https://feeds.reuters.com/reuters/topNews",
    "Reuters Markets": "https://feeds.reuters.com/reuters/financialnews",
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "FT World": "https://www.ft.com/rss/world",
    "CNBC Top News": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Investing.com News": "https://www.investing.com/rss/news.rss",
    "Investing.com Market Overview": "https://www.investing.com/rss/market_overview.rss",
    # === LATAM ===
    "Diario Financiero": "https://www.df.cl/noticias/site/tax/port/all/rss_4_1__1.xml",
    # === ASIA ===
    "SCMP Business": "https://www.scmp.com/rss/5/feed",
    "Asia Times": "https://asiatimes.com/feed/",
    "Channel News Asia": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511",
    # === RUSSIA/MIDDLE EAST ===
    "TASS Economy": "https://tass.com/rss/v2.xml",
    "Al Jazeera Business": "https://www.aljazeera.com/xml/rss/all.xml",
}

# ------------------ CONFIG EMAIL / GMAIL -------------------------------------

EMAIL_IMAP_HOST = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FOLDER = os.getenv("EMAIL_FOLDER", "INBOX")

DF_ONECLICK_SENDER = os.getenv("DF_ONECLICK_SENDER", "titulares@df.cl")
DF_ONECLICK_SUBJECT_CONTAINS = os.getenv("DF_ONECLICK_SUBJECT_CONTAINS", "Primer Click")

# ------------------ CONFIG RESUMEN DIARIO FINANCIERO (TXT EN CARPETA) -------

DF_RESUMEN_DIR = os.getenv(
    "DF_RESUMEN_DIR",
    r"C:\Users\I7 8700\OneDrive\Documentos\df\df_data"
)

# ------------------ NEWSLETTERS GENERALES (FROM + SUBJECT opcional) ---------

NEWSLETTER_SPECS = [
    # ========================================================================
    # WSJ - CORE (3 newsletters) - CRÍTICOS
    # ========================================================================
    {
        "key": "wsj_markets_pm",
        "display_name": "WSJ Markets P.M.",
        "from_addr": "access@interactive.wsj.com",
        "subject_contains": None,
        "from_name_contains": "WSJ Markets P.M.",
        "priority": "CRITICAL",
    },
    {
        "key": "wsj_markets_am",
        "display_name": "WSJ Markets A.M.",
        "from_addr": "access@interactive.wsj.com",
        "subject_contains": None,
        "from_name_contains": "Markets A.M.",
        "priority": "CRITICAL",
    },
    {
        "key": "wsj_10_point",
        "display_name": "WSJ The 10-Point",
        "from_addr": "access@interactive.wsj.com",
        "subject_contains": None,
        "from_name_contains": "Emma Tucker",
        "priority": "CRITICAL",
    },
    
    # ========================================================================
    # WSJ - ESPECIALIZADO (1 newsletter) - IA/TECH CRÍTICO
    # ========================================================================
    {
        "key": "wsj_ai_business",
        "display_name": "WSJ AI & Business",
        "from_addr": "access@interactive.wsj.com",
        "subject_contains": None,
        "from_name_contains": "AI & Business",
        "priority": "HIGH",
    },
    
    # ========================================================================
    # FT - SELECCIÓN (2 newsletters)
    # ========================================================================
    {
        "key": "ft_markets_morning",
        "display_name": "FT Markets Morning Briefing",
        "from_addr": "FT@news-alerts.ft.com",
        "subject_contains": "Markets morning briefing",
        "priority": "HIGH",
    },
    {
        "key": "ft_commodities_note",
        "display_name": "FT Commodities Note",
        "from_addr": "FT@news-alerts.ft.com",
        "subject_contains": "Commodities Note",
        "priority": "MEDIUM",
    },
    
    # ========================================================================
    # BLOOMBERG - LATAM (1 newsletter) - ÚNICO CON FOCO REGIONAL
    # ========================================================================
    {
        "key": "bloomberg_linea",
        "display_name": "Bloomberg Línea",
        "from_addr": "news@bloomberglinea.com",
        "subject_contains": None,
        "priority": "HIGH",
    },
    
    # ========================================================================
    # MORNING BREW (1 newsletter) - NUEVO ✨
    # ========================================================================
    {
        "key": "morning_brew",
        "display_name": "Morning Brew",
        "from_addr": "crew@morningbrew.com",
        "subject_contains": None,
        "from_name_contains": "Morning Brew",
        "skip_time_filter": False,
        "priority": "HIGH",
    },
]

# NOTAS SOBRE OPTIMIZACIÓN:
# - Reducción: 10 → 8 newsletters (20% menos)
# - Eliminados: FT International Morning, FT Markets Afternoon, WSJ What's News
# - Agregados: Morning Brew (business/tech), WSJ PDF (manual)
# - Nueva sección en reportes: "INTELIGENCIA ARTIFICIAL Y TECNOLOGÍA"

# ------------------ HELPER: TRUNCAR TEXTO -----------------------------------

def truncate_text(text: str, max_chars: int) -> str:
    """Trunca texto si excede max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... contenido truncado para optimizar tokens ...]"

# ------------------ SENTIMENT ANALYSIS --------------------------------------

def calculate_sentiment_score(dataset: dict) -> dict:
    """
    Calcula el sentiment basado en conteo de palabras positivas vs negativas.
    Retorna dict con sentiment, ratio, counts y confidence.
    """
    print("[SENTIMENT] Calculando sentiment del día...")
    
    positive_count = 0
    negative_count = 0
    
    # Juntar todo el texto relevante
    all_text = ""
    
    # Newsletters
    for key, newsletter in dataset.get('newsletters', {}).items():
        if newsletter and 'raw_text' in newsletter:
            all_text += " " + newsletter['raw_text'].lower()
    
    # Resumen DF
    if dataset.get('df_resumen_diario') and 'raw_text' in dataset['df_resumen_diario']:
        all_text += " " + dataset['df_resumen_diario']['raw_text'].lower()
    
    # Noticias RSS
    for news_item in dataset.get('news', {}).get('rss', []):
        if news_item.get('title'):
            all_text += " " + news_item['title'].lower()
    
    # Contar palabras positivas y negativas
    for word in POSITIVE_KEYWORDS:
        positive_count += all_text.count(word)
    
    for word in NEGATIVE_KEYWORDS:
        negative_count += all_text.count(word)
    
    # Calcular ratio y sentiment
    total = positive_count + negative_count
    
    if total == 0:
        sentiment = "Neutral"
        ratio = 1.0
        confidence = "Baja"
    else:
        if negative_count == 0:
            ratio = float('inf') if positive_count > 0 else 1.0
            sentiment = "Positivo"
            confidence = "Alta"
        else:
            ratio = positive_count / negative_count
            
            if ratio > 1.3:
                sentiment = "Positivo"
                confidence = "Alta" if ratio > 1.5 else "Media"
            elif ratio < 0.7:
                sentiment = "Negativo"
                confidence = "Alta" if ratio < 0.5 else "Media"
            else:
                sentiment = "Neutral"
                confidence = "Media" if 0.85 <= ratio <= 1.15 else "Baja"
    
    # Calcular score numérico (-10 a +10)
    if ratio == float('inf'):
        score = 10.0
    elif ratio == 0:
        score = -10.0
    else:
        # Mapear ratio a score: ratio=2.0 -> score=+5, ratio=0.5 -> score=-5
        score = (ratio - 1.0) * 10
        score = max(-10, min(10, score))  # Clamp entre -10 y +10
    
    result = {
        "sentiment": sentiment,
        "positive_words": positive_count,
        "negative_words": negative_count,
        "ratio": round(ratio, 2) if ratio != float('inf') else 999,
        "score": round(score, 1),
        "confidence": confidence,
        "total_words_analyzed": total,
    }
    
    print(f"[SENTIMENT] Resultado: {sentiment} (score: {result['score']}, ratio: {result['ratio']})")
    print(f"[SENTIMENT] Palabras: {positive_count} positivas, {negative_count} negativas")
    
    return result


def load_sentiment_history() -> dict:
    """Carga el historial de sentiment desde archivo JSON."""
    if os.path.exists(SENTIMENT_HISTORY_FILE):
        try:
            with open(SENTIMENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SENTIMENT] Error cargando historial: {e}")
            return {}
    return {}


def save_sentiment_history(history: dict) -> None:
    """Guarda el historial de sentiment en archivo JSON."""
    try:
        with open(SENTIMENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"[SENTIMENT] Historial guardado en {SENTIMENT_HISTORY_FILE}")
    except Exception as e:
        print(f"[SENTIMENT] Error guardando historial: {e}")


def update_sentiment_history(today_date: str, sentiment_data: dict) -> dict:
    """
    Actualiza el historial de sentiment con el dato de hoy.
    Retorna el historial completo.
    """
    history = load_sentiment_history()
    
    history[today_date] = {
        "sentiment": sentiment_data["sentiment"],
        "score": sentiment_data["score"],
        "ratio": sentiment_data["ratio"],
        "positive_words": sentiment_data["positive_words"],
        "negative_words": sentiment_data["negative_words"],
        "confidence": sentiment_data["confidence"],
    }
    
    save_sentiment_history(history)
    return history


def get_recent_sentiment_trend(history: dict, days: int = 7) -> List[dict]:
    """
    Obtiene los últimos N días de sentiment del historial.
    Retorna lista de {date, sentiment, score} ordenada por fecha desc.
    """
    sorted_dates = sorted(history.keys(), reverse=True)
    recent = []
    
    for date_str in sorted_dates[:days]:
        data = history[date_str]
        recent.append({
            "date": date_str,
            "sentiment": data["sentiment"],
            "score": data.get("score", 0),
            "ratio": data.get("ratio", 1.0),
        })
    
    return recent


# ------------------ CONTENT TRACKING (AM/PM DEDUPLICATION) ------------------

USED_CONTENT_REGISTRY_FILE = "used_content_registry.json"


def extract_headlines_and_keywords(news_curated: dict) -> dict:
    """
    Extrae headlines y keywords de las noticias curadas para tracking.
    """
    headlines = set()
    keywords = set()

    if not news_curated or "curated_newsletters" not in news_curated:
        return {"headlines": list(headlines), "keywords": list(keywords)}

    curated_newsletters = news_curated.get("curated_newsletters", {})

    for newsletter_key, newsletter_data in curated_newsletters.items():
        if not newsletter_data or "curated" not in newsletter_data:
            continue

        curated = newsletter_data.get("curated", {})
        key_news = curated.get("key_news", [])

        for news_item in key_news:
            headline = news_item.get("headline", "")
            if headline:
                headlines.add(headline)

            item_keywords = news_item.get("keywords", [])
            for kw in item_keywords:
                if kw:
                    keywords.add(kw.lower())

    return {
        "headlines": list(headlines),
        "keywords": list(keywords)
    }


def load_used_content_registry() -> dict:
    """Carga el registro de contenido usado desde archivo JSON."""
    if os.path.exists(USED_CONTENT_REGISTRY_FILE):
        try:
            with open(USED_CONTENT_REGISTRY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[CONTENT_TRACK] Error cargando registro: {e}")
            return {}
    return {}


def save_used_content_registry(registry: dict) -> None:
    """Guarda el registro de contenido usado en archivo JSON."""
    try:
        with open(USED_CONTENT_REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        print(f"[CONTENT_TRACK] Registro guardado en {USED_CONTENT_REGISTRY_FILE}")
    except Exception as e:
        print(f"[CONTENT_TRACK] Error guardando registro: {e}")


def save_used_content_for_mode(today_date: str, mode: str, news_curated: dict) -> None:
    """
    Guarda el contenido usado para un modo específico (AM/PM).
    Solo guarda si mode == "AM" para que PM pueda filtrar duplicados.
    """
    if mode != "AM":
        return

    print(f"[CONTENT_TRACK] Guardando contenido usado para {mode}...")

    content = extract_headlines_and_keywords(news_curated)

    registry = load_used_content_registry()

    if today_date not in registry:
        registry[today_date] = {}

    registry[today_date][mode] = {
        "headlines": content["headlines"],
        "keywords": content["keywords"],
        "timestamp": datetime.now().isoformat(),
        "headlines_count": len(content["headlines"]),
        "keywords_count": len(content["keywords"])
    }

    save_used_content_registry(registry)

    print(f"[CONTENT_TRACK] Guardado: {len(content['headlines'])} headlines, {len(content['keywords'])} keywords")

    # Limpieza: eliminar entradas más antiguas de 7 días
    cleanup_used_content_registry(registry)


def cleanup_used_content_registry(registry: dict) -> None:
    """Elimina entradas del registro más antiguas de 7 días."""
    cutoff = (datetime.now() - timedelta(days=7)).date()
    dates_to_remove = []

    for date_str in registry.keys():
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if entry_date < cutoff:
                dates_to_remove.append(date_str)
        except:
            continue

    for date_str in dates_to_remove:
        del registry[date_str]

    if dates_to_remove:
        save_used_content_registry(registry)
        print(f"[CONTENT_TRACK] Eliminadas {len(dates_to_remove)} entradas antiguas")


def get_am_used_content(today_date: str) -> dict:
    """
    Obtiene el contenido usado en AM para el día especificado.
    Usado por generate_daily_report.py para filtrar duplicados en PM.
    """
    registry = load_used_content_registry()

    if today_date in registry and "AM" in registry[today_date]:
        return registry[today_date]["AM"]

    return {"headlines": [], "keywords": []}


# ------------------ HELPERS MERCADO -----------------------------------------


def percent_change(new: float, old: Optional[float]) -> Optional[float]:
    if old is None or old == 0:
        return None
    return (new / old - 1.0) * 100.0


def get_yfinance_metrics(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Descarga datos de un ticker usando yfinance.
    Para IPSA, intenta primero ticker.info (más confiable).
    Para otros, usa history como antes.
    """
    print(f"[INFO] Descargando datos de {ticker}...")
    
    # ESTRATEGIA ESPECIAL PARA IPSA
    if ticker == "^IPSA":
        try:
            t = yf.Ticker(ticker)
            info = t.info
            
            # Verificar si tiene los campos necesarios
            if info and 'regularMarketPrice' in info:
                current_price = info.get('regularMarketPrice')
                prev_close = info.get('regularMarketPreviousClose')
                change_pct = info.get('regularMarketChangePercent')
                
                # Si no viene change_pct, calcularlo
                if change_pct is None and current_price and prev_close and prev_close != 0:
                    change_pct = ((current_price / prev_close) - 1) * 100
                
                print(f"[OK] {ticker} desde ticker.info: close={current_price}, change={change_pct}")
                
                return {
                    "symbol": ticker,
                    "close": round(current_price, 2) if current_price else None,
                    "change_1d": round(change_pct, 2) if change_pct else None,
                    "change_mtd": None,  # No disponible en info
                    "change_ytd": None,  # No disponible en info
                    "last_date": date.today().isoformat(),
                    "source": "ticker.info"
                }
        except Exception as e:
            print(f"[WARN] {ticker}: ticker.info falló ({e}), intentando con history...")
    
    # ESTRATEGIA NORMAL (history) - para todos los demás o si IPSA.info falló
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo", interval="1d", auto_adjust=False)
    except Exception as e:
        print(f"[ERROR] {ticker}: fallo al descargar datos: {e}")
        return None

    print(f"[INFO] {ticker}: filas descargadas = {len(hist)}, columnas = {list(hist.columns)}")

    if hist.empty:
        print(f"[WARN] {ticker}: DataFrame vacío.")
        return None

    close_col = None
    for candidate in ["Close", "Adj Close", "close", "adjclose"]:
        if candidate in hist.columns:
            close_col = candidate
            break

    if close_col is None:
        print(f"[WARN] {ticker}: no se encontró columna de cierre en {list(hist.columns)}")
        return None

    hist = hist.dropna(subset=[close_col]).sort_index()
    
    # CAMBIO: Aceptar 1 día de datos (útil para IPSA)
    if len(hist) < 1:
        print(f"[WARN] {ticker}: sin datos válidos en {close_col}.")
        return None

    today = hist.index[-1]
    last_close = float(hist[close_col].iloc[-1])
    
    # Si tenemos 2+ días, calcular cambio 1D
    change_1d = None
    if len(hist) >= 2:
        prev_close = float(hist[close_col].iloc[-2])
        change_1d = percent_change(last_close, prev_close)
    else:
        print(f"[INFO] {ticker}: solo 1 día de datos, change_1d será None")

    today_d = today.date()
    month_mask = (hist.index.year == today_d.year) & (hist.index.month == today_d.month)
    month_data = hist.loc[month_mask]
    change_mtd = None
    if not month_data.empty:
        first_m = float(month_data[close_col].iloc[0])
        change_mtd = percent_change(last_close, first_m)

    year_mask = hist.index.year == today_d.year
    year_data = hist.loc[year_mask]
    change_ytd = None
    if not year_data.empty:
        first_y = float(year_data[close_col].iloc[0])
        change_ytd = percent_change(last_close, first_y)

    metrics = {
        "symbol": ticker,
        "close": round(last_close, 4),
        "change_1d": round(change_1d, 2) if change_1d is not None else None,
        "change_mtd": round(change_mtd, 2) if change_mtd is not None else None,
        "change_ytd": round(change_ytd, 2) if change_ytd is not None else None,
        "last_date": today_d.isoformat(),
    }

    print(f"[OK] {ticker}: {metrics}")
    return metrics


def fetch_bcch_series_last_value(
    series_id: str,
    days_back: int = 120,
) -> Optional[Dict[str, Any]]:
    """
    Devuelve las dos últimas observaciones válidas (latest y previous)
    de una serie del BCCh.
    REQUIERE credenciales en .env: BCCH_USER y BCCH_PASS
    """
    # Obtener credenciales desde .env
    bcch_user = os.getenv("BCCH_USER")
    bcch_pass = os.getenv("BCCH_PASS")
    
    if not bcch_user or not bcch_pass:
        print(f"[ERROR] BCCh: Credenciales no configuradas en .env (BCCH_USER, BCCH_PASS)")
        return None
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    # La API ahora usa GET con parámetros en la URL (no POST)
    params = {
        "user": bcch_user,
        "pass": bcch_pass,
        "firstdate": start_date.strftime("%Y-%m-%d"),
        "lastdate": end_date.strftime("%Y-%m-%d"),
        "timeseries": series_id,
        "function": "GetSeries",
    }

    try:
        print(f"[BCCh] Consultando {series_id}...")
        r = requests.get(BCCH_BDE_URL, params=params, timeout=15)
        print(f"[BCCh] {series_id}: Status {r.status_code}")
        r.raise_for_status()
        
        # Intentar parsear JSON
        try:
            data = r.json()
            print(f"[BCCh] JSON OK - {series_id}")
        except json.JSONDecodeError as je:
            print(f"[ERROR] BCCh {series_id}: La respuesta NO es JSON válido")
            print(f"[ERROR] Primeros 500 chars de respuesta: {r.text[:500]}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] BCCh series {series_id}: Error de conexión: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] BCCh series {series_id}: {e}")
        return None

    series_obj = data.get("Series", {}).get("Obs")
    if not series_obj or len(series_obj) == 0:
        print(f"[WARN] BCCh series {series_id}: sin observaciones.")
        return None

    valid_obs: List[Dict[str, Any]] = []
    for obs in series_obj:
        val_str = obs.get("value", "").strip()
        if not val_str:
            continue
        try:
            val = float(val_str)
            obs_date_str = obs.get("indexDateString")
            valid_obs.append({"value": val, "date": obs_date_str})
        except ValueError:
            continue

    if len(valid_obs) == 0:
        print(f"[WARN] BCCh series {series_id}: sin observaciones válidas tras filtrar.")
        return None

    latest_obs = valid_obs[-1]

    prev_obs = None
    change_pct = None
    if len(valid_obs) >= 2:
        prev_obs = valid_obs[-2]
        prev_val = prev_obs["value"]
        lat_val = latest_obs["value"]
        if prev_val != 0:
            change_pct = ((lat_val / prev_val) - 1.0) * 100.0

    result = {
        "latest": latest_obs,
        "previous": prev_obs,
        "change_pct": change_pct,
        "all_obs": valid_obs,  # Agregar todas las observaciones para cálculos adicionales
    }

    print(f"[OK] BCCh series {series_id}: Latest={latest_obs['value']} ({latest_obs['date']})")
    return result


def calculate_ipsa_returns_from_bcch(bcch_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calcula retornos del IPSA (1D, MTD, YTD) usando niveles históricos del BCCh
    
    El BCCh entrega NIVELES del índice, NO cambios porcentuales.
    Por eso calculamos: retorno% = (nivel_hoy / nivel_pasado - 1) * 100
    
    Args:
        bcch_data: Resultado de fetch_bcch_series_last_value() con observaciones
    
    Returns:
        Dict con: close, date, change_1d, change_mtd, change_ytd
    """
    if not bcch_data or "all_obs" not in bcch_data:
        print("[ERROR] IPSA: No hay datos históricos para calcular retornos")
        return {}
    
    observations = bcch_data["all_obs"]
    if not observations:
        print("[ERROR] IPSA: Lista de observaciones vacía")
        return {}
    
    # Valor más reciente (nivel de hoy)
    latest = observations[-1]
    latest_value = latest["value"]
    latest_date_str = latest["date"]
    
    print(f"[IPSA] Nivel más reciente: {latest_value:.2f} ({latest_date_str})")
    print(f"[IPSA] Total observaciones disponibles: {len(observations)}")
    
    try:
        latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d").date()
    except:
        print(f"[ERROR] No se pudo parsear fecha IPSA: {latest_date_str}")
        return {}
    
    # ========================================================================
    # CAMBIO 1D (vs día anterior)
    # ========================================================================
    change_1d = None
    if len(observations) >= 2:
        prev_value = observations[-2]["value"]
        prev_date = observations[-2]["date"]
        if prev_value != 0:
            change_1d = ((latest_value / prev_value) - 1.0) * 100.0
            print(f"[IPSA] 1D: {latest_value:.2f} / {prev_value:.2f} = {change_1d:+.2f}% ({prev_date} → {latest_date_str})")
    else:
        print("[WARN] IPSA: No hay suficientes datos para calcular cambio 1D")
    
    # ========================================================================
    # CAMBIO MTD (desde primer día del mes actual)
    # ========================================================================
    change_mtd = None
    first_day_of_month = latest_date.replace(day=1)
    print(f"[IPSA] Buscando nivel desde inicio de mes: {first_day_of_month.isoformat()}")
    
    month_start_obs = None
    for obs in observations:
        try:
            obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
            if obs_date >= first_day_of_month:
                # Primera observación del mes actual
                month_start_obs = obs
                break
        except:
            continue
    
    if month_start_obs:
        month_start_value = month_start_obs["value"]
        month_start_date = month_start_obs["date"]
        if month_start_value != 0:
            change_mtd = ((latest_value / month_start_value) - 1.0) * 100.0
            print(f"[IPSA] MTD: {latest_value:.2f} / {month_start_value:.2f} = {change_mtd:+.2f}% ({month_start_date} → {latest_date_str})")
    else:
        print(f"[WARN] IPSA: No se encontró nivel de inicio de mes {first_day_of_month.isoformat()}")
    
    # ========================================================================
    # CAMBIO YTD (desde primer día del año actual)
    # ========================================================================
    change_ytd = None
    first_day_of_year = latest_date.replace(month=1, day=1)
    print(f"[IPSA] Buscando nivel desde inicio de año: {first_day_of_year.isoformat()}")
    
    year_start_obs = None
    for obs in observations:
        try:
            obs_date = datetime.strptime(obs["date"], "%Y-%m-%d").date()
            if obs_date >= first_day_of_year:
                # Primera observación del año actual
                year_start_obs = obs
                break
        except:
            continue
    
    if year_start_obs:
        year_start_value = year_start_obs["value"]
        year_start_date = year_start_obs["date"]
        if year_start_value != 0:
            change_ytd = ((latest_value / year_start_value) - 1.0) * 100.0
            print(f"[IPSA] YTD: {latest_value:.2f} / {year_start_value:.2f} = {change_ytd:+.2f}% ({year_start_date} → {latest_date_str})")
    else:
        print(f"[WARN] IPSA: No se encontró nivel de inicio de año {first_day_of_year.isoformat()}")
    
    result = {
        "close": round(latest_value, 2),
        "date": latest_date_str,
        "change_1d": round(change_1d, 2) if change_1d is not None else None,
        "change_mtd": round(change_mtd, 2) if change_mtd is not None else None,
        "change_ytd": round(change_ytd, 2) if change_ytd is not None else None,
    }
    
    print(f"[OK] IPSA resumen: Close={result['close']}, 1D={result['change_1d']}%, MTD={result['change_mtd']}%, YTD={result['change_ytd']}%")
    
    return result


def build_asset_block(ticker_map: Dict[str, str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for ticker, label in ticker_map.items():
        metrics = get_yfinance_metrics(ticker)
        if metrics:
            result[ticker] = metrics
        else:
            result[ticker] = {
                "symbol": ticker,
                "label": label,
                "error": "No data",
            }
    return result


# ------------------ EMAIL / GMAIL HELPERS -----------------------------------

def safe_imap_logout(mail) -> None:
    """Cierra conexión IMAP de forma segura, ignorando errores SSL/socket."""
    try:
        safe_imap_logout(mail)
    except Exception as e:
        # Ignorar errores de logout - la conexión se cerrará de todos modos
        print(f"[DEBUG] IMAP logout warning (ignorable): {type(e).__name__}")


def decode_email_subject(subj_raw: str) -> str:
    """Decodifica asunto del email (RFC 2047)."""
    decoded_parts = decode_header(subj_raw)
    result = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            if enc:
                try:
                    result.append(part.decode(enc))
                except:
                    result.append(part.decode("utf-8", errors="ignore"))
            else:
                result.append(part.decode("utf-8", errors="ignore"))
        else:
            result.append(str(part))
    return "".join(result)


def decode_email_from(from_raw: str) -> str:
    """Decodifica el campo FROM (puede contener nombre + mail)."""
    decoded_parts = decode_header(from_raw)
    result = []
    for part, enc in decoded_parts:
        if isinstance(part, bytes):
            if enc:
                try:
                    result.append(part.decode(enc))
                except:
                    result.append(part.decode("utf-8", errors="ignore"))
            else:
                result.append(part.decode("utf-8", errors="ignore"))
        else:
            result.append(str(part))
    return "".join(result)


def extract_text_from_email(msg: email.message.Message) -> str:
    """Extrae el cuerpo de texto plano del email."""
    text_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    text_parts.append(payload.decode("utf-8", errors="ignore"))
    else:
        ct = msg.get_content_type()
        if ct == "text/plain":
            payload = msg.get_payload(decode=True)
            if payload:
                text_parts.append(payload.decode("utf-8", errors="ignore"))

    return "\n".join(text_parts)


def extract_html_from_email(msg: email.message.Message) -> str:
    """Extrae el cuerpo de HTML del email."""
    html_parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    html_parts.append(payload.decode("utf-8", errors="ignore"))
    else:
        ct = msg.get_content_type()
        if ct == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                html_parts.append(payload.decode("utf-8", errors="ignore"))

    return "\n".join(html_parts)


def html_to_text(html_str: str) -> str:
    """Convierte HTML a texto plano básico."""
    no_tags = re.sub(r"<[^>]+>", " ", html_str)
    txt = unescape(no_tags)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def clean_df_oneclick_text(raw_text: str) -> str:
    """Limpia el texto del email."""
    lines = raw_text.split("\n")
    cleaned_lines = []
    
    # Flag para detectar bloques de CSS
    in_css_block = False
    
    for line in lines:
        line = line.strip()
        
        # Detectar inicio de bloque CSS
        if '{' in line or 'color-scheme:' in line or '@media' in line or 'font-face' in line:
            in_css_block = True
            continue
        
        # Detectar fin de bloque CSS
        if '}' in line:
            in_css_block = False
            continue
        
        # Saltar si estamos en bloque CSS
        if in_css_block:
            continue
        
        # Saltar líneas vacías, URLs, etc.
        if not line or len(line) < 10:
            continue
        if line.startswith("http"):
            continue
        if "unsubscribe" in line.lower():
            continue
        if line.startswith("src:") or line.startswith("url("):
            continue
            
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)


def clean_generic_newsletter_text(raw_text: str) -> str:
    """
    Limpieza para newsletters en general (FT, WSJ, Bloomberg, Scotiabank, etc.).
    Intenta eliminar CSS/boilerplate típico de plantillas de email, pero manteniendo
    titulares y párrafos legibles.
    """
    if not raw_text:
        return ""

    lines = raw_text.split("\n")
    cleaned_lines: list[str] = []
    in_css_block = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower = line.lower()

        # --- Detectar y saltar bloques de CSS ---
        if not in_css_block and (
            line.startswith((":root", "@media", "@font-face", "@-ms-viewport"))
            or (line.startswith((".", "#")) and "{" in line)
        ):
            in_css_block = True
            continue
            
        if in_css_block:
            if "}" in line:
                in_css_block = False
            continue

        # Encabezados o enlaces genéricos poco útiles
        if lower.startswith("view in browser"):
            continue
        if "unsubscribe" in lower:
            continue

        # Líneas claras de CSS / fuentes / media queries / clases, etc.
        if (
            line.startswith((":root", "@media", "@font-face", "@-ms-viewport"))
            or line.startswith((".ReadMsgBody", ".ExternalClass", ".size", ".bodyText"))
            or "font-family" in lower
            or "font-weight" in lower
            or "font-style" in lower
            or "font-size:" in lower
            or "line-height:" in lower
            or "color-scheme" in lower
            or "background-color" in lower
            or "border-top" in lower
            or "border-bottom" in lower
            or "mso-" in lower
            or 'format("woff"' in lower
            or "https://email.news-alerts.ft.com" in lower
            or "!important" in lower
        ):
            continue

        # Líneas que parecen reglas CSS (contienen ; y { o })
        if (";" in line and "{" in line) or (";" in line and "}" in line):
            continue
        
        # Reglas tipo "p a[href] { color: #275e86!important; }"
        if any(ch in line for ch in "{};") and any(ch in line for ch in ":,"):
            continue

        # Líneas sueltas de llaves
        if line in ("{", "}", "};"):
            continue
        
        if line.endswith("{"):
            continue

        # --- NUEVO: Filtrar líneas de solo caracteres especiales ---
        # Líneas con muchos espacios invisibles (NBSP, zero-width, etc.)
        if lower.count("‌") > 5 or lower.count(" ") > len(line) * 0.5:
            continue
        
        # Líneas muy cortas que no aportan (menos de 20 chars)
        if len(line) < 20 and not any(word in lower for word in ['summary', 'briefing', 'headlines', 'note']):
            continue
        
        # Si la línea empieza con "‌ ‌ ‌" (muchos espacios invisibles)
        if line.startswith("‌"):
            continue
        
        # Headers repetitivos de newsletters
        skip_phrases = [
            "all newsletters",
            "read in browser",
            "follow the ft",
            "my account",
            "manage portfolio",
            "privacy policy",
            "about us",
            "help",
            "all rights reserved",
            "you have received this email because",
            "registered in england and wales",
            "rss |",
            "© the financial times ltd",
            "this email was sent by a company owned by financial times",
            "if this email is difficult to read",
            "the markets news you need",
            "the latest commodities headlines",
            "markets, world news, companies",
        ]
        
        if any(phrase in lower for phrase in skip_phrases):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def extract_text_from_email_message(msg: email.message.Message) -> str:
    """Extrae texto de un mensaje de email, priorizando texto plano."""
    body_text = extract_text_from_email(msg)
    if body_text.strip():
        return body_text
    
    # Si no hay texto plano, convertir HTML
    body_html = extract_html_from_email(msg)
    if body_html.strip():
        return html_to_text(body_html)
    
    return ""


def fetch_latest_newsletter(spec: Dict[str, Any], mode: str = "AM") -> Optional[Dict[str, Any]]:
    """
    Busca el último correo que coincida con FROM (y opcionalmente SUBJECT).
    
    Args:
        spec: Especificación de la newsletter
        mode: "AM" o "PM" - filtra emails por horario de recepción
    """
    display_name = spec.get("display_name", "Newsletter")
    from_addr = spec.get("from_addr")
    subject_contains = spec.get("subject_contains")
    
    print(f"[NEWSLETTER {display_name}] Buscando para reporte {mode}...")

    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print(f"[NEWSLETTER {display_name}] EMAIL_USERNAME/EMAIL_PASSWORD no definidos. Se omite.")
        return None
    
    # Definir ventanas de tiempo EN TIMEZONE CHILE
    if CHILE_TIMEZONE_AVAILABLE:
        from chile_timezone import CHILE_TZ
        import pytz
        
        # Obtener hora actual en Chile
        now_chile = get_chile_now()
        today_10am_chile = now_chile.replace(hour=10, minute=0, second=0, microsecond=0)
        today_8pm_chile = now_chile.replace(hour=20, minute=0, second=0, microsecond=0)
        yesterday_7pm_chile = (now_chile - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        
        if mode == "AM":
            time_start = yesterday_7pm_chile
            time_end = today_10am_chile  # AMPLIADO: antes era 08:00, ahora 10:00
        else:  # PM
            time_start = today_10am_chile  # AMPLIADO: antes era 08:00, ahora 10:00
            time_end = today_8pm_chile    # AMPLIADO: antes era 19:00, ahora 20:00
        
        print(f"[INFO] Ventana de tiempo (Chile): {time_start.strftime('%Y-%m-%d %H:%M %Z')} a {time_end.strftime('%Y-%m-%d %H:%M %Z')}")
    else:
        # Fallback: usar hora local sin timezone (comportamiento anterior)
        now = datetime.now()
        today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
        today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
        yesterday_7pm = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        
        if mode == "AM":
            time_start = yesterday_7pm
            time_end = today_10am  # AMPLIADO: antes era 08:00, ahora 10:00
        else:  # PM
            time_start = today_10am  # AMPLIADO: antes era 08:00, ahora 10:00
            time_end = today_8pm    # AMPLIADO: antes era 19:00, ahora 20:00
        
        print(f"[WARN] Chile timezone no disponible, usando hora local")

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_HOST, EMAIL_IMAP_PORT)
        mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)
    except Exception as e:
        print(f"[NEWSLETTER {display_name}] Error conectando a IMAP: {e}")
        return None

    try:
        status, _ = mail.select(EMAIL_FOLDER)
        print(f"[NEWSLETTER {display_name}] Carpeta seleccionada: {EMAIL_FOLDER} (status={status})")
    except Exception as e:
        print(f"[NEWSLETTER {display_name}] Error seleccionando carpeta {EMAIL_FOLDER}: {e}")
        safe_imap_logout(mail)
        return None

    def do_search(*criteria: str):
        """Asegura que los valores de FROM/SUBJECT estén entre comillas dobles para IMAP."""
        quoted_criteria: list[str] = []
        i = 0
        while i < len(criteria):
            field = criteria[i]
            quoted_criteria.append(field)
            i += 1

            if i < len(criteria):
                value = criteria[i]
                if not (value.startswith('"') and value.endswith('"')):
                    value = f'"{value}"'
                quoted_criteria.append(value)
                i += 1

        print(f"[NEWSLETTER {display_name}] Criterios IMAP a enviar: {quoted_criteria}")
        return mail.search(None, *quoted_criteria)

    status = None
    data = None

    if from_addr and subject_contains:
        try:
            status, data = do_search("FROM", from_addr, "SUBJECT", subject_contains)
        except Exception as e:
            print(f"[NEWSLETTER {display_name}] Error en búsqueda (FROM+SUBJ): {e}")
            safe_imap_logout(mail)
            return None

        msg_ids = data[0].split() if data and data[0] else []
        print(f"[NEWSLETTER {display_name}] Mensajes (FROM+SUBJ): {len(msg_ids)}")

        if not msg_ids:
            print(f"[NEWSLETTER {display_name}] Reintentando sólo FROM...")
            try:
                status, data = do_search("FROM", from_addr)
            except Exception as e:
                print(f"[NEWSLETTER {display_name}] Error en búsqueda (solo FROM): {e}")
                safe_imap_logout(mail)
                return None

    elif from_addr:
        try:
            status, data = do_search("FROM", from_addr)
        except Exception as e:
            print(f"[NEWSLETTER {display_name}] Error en búsqueda (solo FROM): {e}")
            safe_imap_logout(mail)
            return None
    elif subject_contains:
        try:
            status, data = do_search("SUBJECT", subject_contains)
        except Exception as e:
            print(f"[NEWSLETTER {display_name}] Error en búsqueda (solo SUBJECT): {e}")
            safe_imap_logout(mail)
            return None
    else:
        try:
            status, data = do_search("ALL")
        except Exception as e:
            print(f"[NEWSLETTER {display_name}] Error en búsqueda (ALL): {e}")
            safe_imap_logout(mail)
            return None

    if status != "OK":
        print(f"[NEWSLETTER {display_name}] Búsqueda IMAP no OK: {status}")
        safe_imap_logout(mail)
        return None

    msg_ids = data[0].split() if data and data[0] else []
    print(f"[NEWSLETTER {display_name}] Mensajes encontrados iniciales: {len(msg_ids)}")

    if not msg_ids:
        print(f"[NEWSLETTER {display_name}] No se encontraron correos.")
        safe_imap_logout(mail)
        return None
    
    # Si hay filtro de from_name_contains, filtrar los mensajes
    from_name_contains = spec.get("from_name_contains")
    skip_time_filter = spec.get("skip_time_filter", False)
    
    if from_name_contains:
        print(f"[NEWSLETTER {display_name}] Aplicando filtro adicional: FROM name debe contener '{from_name_contains}'")
        filtered_ids = []
        
        # Revisar los últimos 20 mensajes para encontrar coincidencias
        recent_ids = msg_ids[-20:] if len(msg_ids) > 20 else msg_ids
        
        for msg_id in reversed(recent_ids):  # Del más reciente al más antiguo
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                from_raw = msg.get("From", "")
                from_decoded = decode_email_from(from_raw)
                
                # Verificar si el nombre del remitente contiene el texto buscado
                if from_name_contains.lower() in from_decoded.lower():
                    
                    # Si skip_time_filter=True, NO verificar horario (para WSJ con timezones mal)
                    if skip_time_filter:
                        filtered_ids.append(msg_id)
                        print(f"[NEWSLETTER {display_name}] Coincidencia encontrada en FROM: {from_decoded}")
                        print(f"[NEWSLETTER {display_name}] Filtro de horario omitido (skip_time_filter=True)")
                        break  # Tomar el primero (más reciente) que coincida
                    
                    # Verificar horario del email
                    date_str = msg.get("Date", "")
                    try:
                        if CHILE_TIMEZONE_AVAILABLE:
                            # Parsear y convertir a timezone Chile
                            email_datetime = parse_email_date_to_chile(date_str)
                            if email_datetime is None:
                                print(f"[NEWSLETTER {display_name}] Error parseando fecha: {date_str}")
                                # Si no se puede parsear, aceptar el email
                                filtered_ids.append(msg_id)
                                print(f"[NEWSLETTER {display_name}] Coincidencia encontrada (sin validar horario): {from_decoded}")
                                break
                        else:
                            # Fallback: comportamiento anterior
                            from email.utils import parsedate_to_datetime
                            email_datetime = parsedate_to_datetime(date_str)
                            if email_datetime.tzinfo is not None:
                                email_datetime = email_datetime.replace(tzinfo=None)
                        
                        # Filtrar por ventana de tiempo
                        if time_start <= email_datetime <= time_end:
                            filtered_ids.append(msg_id)
                            print(f"[NEWSLETTER {display_name}] Coincidencia encontrada en FROM: {from_decoded}")
                            if CHILE_TIMEZONE_AVAILABLE:
                                print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile) dentro de ventana {mode}")
                            else:
                                print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M')} dentro de ventana {mode}")
                            break  # Tomar el primero (más reciente) que coincida
                        else:
                            if CHILE_TIMEZONE_AVAILABLE:
                                print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile) fuera de ventana {mode}")
                            else:
                                print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M')} fuera de ventana {mode}")
                    except Exception as e:
                        print(f"[NEWSLETTER {display_name}] Error parseando fecha: {e}")
                        # Si no se puede parsear fecha, aceptar el email
                        filtered_ids.append(msg_id)
                        print(f"[NEWSLETTER {display_name}] Coincidencia encontrada en FROM (sin validar horario): {from_decoded}")
                        break
                    
            except Exception as e:
                print(f"[NEWSLETTER {display_name}] Error verificando msg_id {msg_id}: {e}")
                continue
        
        if not filtered_ids:
            print(f"[NEWSLETTER {display_name}] No se encontraron mensajes con FROM name conteniendo '{from_name_contains}' en ventana {mode}")
            safe_imap_logout(mail)
            return None
        
        msg_ids = filtered_ids
        print(f"[NEWSLETTER {display_name}] Mensajes tras filtros: {len(msg_ids)}")
    
    else:
        # Si no hay filtro from_name_contains, aplicar solo filtro de horario
        print(f"[NEWSLETTER {display_name}] Aplicando filtro de horario para ventana {mode}")
        filtered_ids = []
        
        recent_ids = msg_ids[-20:] if len(msg_ids) > 20 else msg_ids
        
        for msg_id in reversed(recent_ids):
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                date_str = msg.get("Date", "")
                try:
                    if CHILE_TIMEZONE_AVAILABLE:
                        # Parsear y convertir a timezone Chile
                        email_datetime = parse_email_date_to_chile(date_str)
                        if email_datetime is None:
                            print(f"[NEWSLETTER {display_name}] Error parseando fecha, usando sin filtro horario")
                            filtered_ids.append(msg_id)
                            break
                    else:
                        # Fallback: comportamiento anterior
                        from email.utils import parsedate_to_datetime
                        email_datetime = parsedate_to_datetime(date_str)
                        if email_datetime.tzinfo is not None:
                            email_datetime = email_datetime.replace(tzinfo=None)
                    
                    if time_start <= email_datetime <= time_end:
                        filtered_ids.append(msg_id)
                        if CHILE_TIMEZONE_AVAILABLE:
                            print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile) dentro de ventana {mode}")
                        else:
                            print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M')} dentro de ventana {mode}")
                        break
                    else:
                        if CHILE_TIMEZONE_AVAILABLE:
                            print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile) fuera de ventana {mode}")
                        else:
                            print(f"[NEWSLETTER {display_name}] Email de {email_datetime.strftime('%Y-%m-%d %H:%M')} fuera de ventana {mode}")
                        
                except Exception as e:
                    print(f"[NEWSLETTER {display_name}] Error parseando fecha: {e}, usando sin filtro horario")
                    filtered_ids.append(msg_id)
                    break
                    
            except Exception as e:
                print(f"[NEWSLETTER {display_name}] Error: {e}")
                continue
        
        if filtered_ids:
            msg_ids = filtered_ids
            print(f"[NEWSLETTER {display_name}] Mensajes tras filtro horario: {len(msg_ids)}")
        else:
            print(f"[NEWSLETTER {display_name}] No se encontraron emails en ventana {mode}, usando el más reciente sin filtro")
            # Si no hay emails en la ventana, usar el más reciente disponible

    latest_id = msg_ids[-1] if isinstance(msg_ids[-1], bytes) else msg_ids[-1]
    print(f"[NEWSLETTER {display_name}] Usando mensaje ID: {latest_id}")

    status, msg_data = mail.fetch(latest_id, "(RFC822)")
    if status != "OK":
        print(f"[NEWSLETTER {display_name}] Error en fetch: {status}")
        safe_imap_logout(mail)
        return None

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    raw_subject = msg.get("Subject", "")
    decoded_subject, enc = decode_header(raw_subject)[0]
    if isinstance(decoded_subject, bytes):
        try:
            subject = decoded_subject.decode(enc or "utf-8", errors="replace")
        except Exception:
            subject = decoded_subject.decode("utf-8", errors="replace")
    else:
        subject = decoded_subject

    email_date = msg.get("Date", "")

    raw_text = extract_text_from_email_message(msg)
    # Limpieza suave para newsletters genéricos (FT, WSJ, Bloomberg, Scotia, etc.)
    clean_text = clean_generic_newsletter_text(raw_text)

    # LIMITAR TAMAÑO DEL TEXTO
    clean_text = truncate_text(clean_text, MAX_NEWSLETTER_CHARS)

    safe_imap_logout(mail)

    if not clean_text:
        print(f"[NEWSLETTER {display_name}] Texto vacío tras limpieza, se omite.")
        return None

    return {
        "source": display_name,
        "subject": subject,
        "email_date": email_date,
        "raw_text": clean_text,
    }


def fetch_latest_df_oneclick_email(mode: str = "AM") -> Optional[Dict[str, Any]]:
    """
    Descarga el email más reciente de Diario Financiero 'Primer Click'.
    
    Args:
        mode: "AM" o "PM" - filtra emails por horario de recepción
              AM: emails entre 6:00 PM ayer y 8:00 AM hoy
              PM: emails entre 8:00 AM hoy y 5:00 PM hoy
    """
    print(f"[INFO] Buscando email de DF Primer Click para reporte {mode}...")

    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("[WARN] Credenciales de email no configuradas. Saltando DF Primer Click.")
        return None
    
    # Definir ventanas de tiempo EN TIMEZONE CHILE
    # Cierre NYSE: 4:00 PM EST = 6:00 PM Chile
    # Reportes USA llegan: 4:30-5:00 PM EST = 6:30-7:00 PM Chile
    
    if CHILE_TIMEZONE_AVAILABLE:
        from chile_timezone import CHILE_TZ
        import pytz
        
        # Obtener hora actual en Chile
        now_chile = get_chile_now()
        today_10am_chile = now_chile.replace(hour=10, minute=0, second=0, microsecond=0)
        today_8pm_chile = now_chile.replace(hour=20, minute=0, second=0, microsecond=0)
        yesterday_7pm_chile = (now_chile - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        
        if mode == "AM":
            time_start = yesterday_7pm_chile  # Desde 7 PM ayer (incluye reportes de cierre USA)
            time_end = today_10am_chile  # AMPLIADO: antes 08:00, ahora 10:00
            print(f"[INFO] Buscando emails entre {time_start.strftime('%Y-%m-%d %H:%M %Z')} y {time_end.strftime('%Y-%m-%d %H:%M %Z')}")
        else:  # PM
            time_start = today_10am_chile  # AMPLIADO: antes 08:00, ahora 10:00
            time_end = today_8pm_chile  # AMPLIADO: antes 19:00, ahora 20:00 (incluye reportes de cierre USA)
            print(f"[INFO] Buscando emails entre {time_start.strftime('%Y-%m-%d %H:%M %Z')} y {time_end.strftime('%Y-%m-%d %H:%M %Z')}")
    else:
        # Fallback: usar hora local sin timezone
        now = datetime.now()
        today_10am = now.replace(hour=10, minute=0, second=0, microsecond=0)
        today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
        yesterday_7pm = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        
        if mode == "AM":
            time_start = yesterday_7pm
            time_end = today_10am  # AMPLIADO: antes 08:00, ahora 10:00
            print(f"[INFO] Buscando emails entre {time_start.strftime('%Y-%m-%d %H:%M')} y {time_end.strftime('%Y-%m-%d %H:%M')}")
        else:  # PM
            time_start = today_10am  # AMPLIADO: antes 08:00, ahora 10:00
            time_end = today_8pm  # AMPLIADO: antes 19:00, ahora 20:00
            print(f"[INFO] Buscando emails entre {time_start.strftime('%Y-%m-%d %H:%M')} y {time_end.strftime('%Y-%m-%d %H:%M')}")
        
        print(f"[WARN] Chile timezone no disponible, usando hora local")

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_HOST, EMAIL_IMAP_PORT)
        mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        mail.select(EMAIL_FOLDER)
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a IMAP: {e}")
        return None

    try:
        search_criteria = f'(FROM "{DF_ONECLICK_SENDER}")'
        _, msg_nums = mail.search(None, search_criteria)

        if not msg_nums or not msg_nums[0]:
            print(f"[INFO] No se encontraron emails de {DF_ONECLICK_SENDER}.")
            safe_imap_logout(mail)
            return None

        ids_list = msg_nums[0].split()
        last_20 = ids_list[-20:]  # Aumentar a 20 para cubrir más horarios

        for msg_id in reversed(last_20):
            try:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subj_raw = msg.get("Subject", "")
                subj = decode_email_subject(subj_raw)

                if DF_ONECLICK_SUBJECT_CONTAINS.lower() not in subj.lower():
                    continue

                # NUEVO: Extraer fecha del email y filtrar por horario
                date_str = msg.get("Date", "")
                try:
                    if CHILE_TIMEZONE_AVAILABLE:
                        # Parsear y convertir a timezone Chile
                        email_datetime = parse_email_date_to_chile(date_str)
                        if email_datetime is None:
                            print(f"[WARN] No se pudo parsear fecha del email: {date_str}")
                            # Si no se puede parsear la fecha, continuar sin filtrar
                        else:
                            # Filtrar por ventana de tiempo
                            if not (time_start <= email_datetime <= time_end):
                                print(f"[DEBUG] Email de {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile) fuera de ventana {mode}")
                                continue
                            
                            print(f"[OK] Email encontrado dentro de ventana {mode}: {email_datetime.strftime('%Y-%m-%d %H:%M %Z')} (Chile)")
                    else:
                        # Fallback: comportamiento anterior
                        from email.utils import parsedate_to_datetime
                        email_datetime = parsedate_to_datetime(date_str)
                        
                        # Convertir a timezone-naive para comparar
                        if email_datetime.tzinfo is not None:
                            email_datetime = email_datetime.replace(tzinfo=None)
                        
                        # Filtrar por ventana de tiempo
                        if not (time_start <= email_datetime <= time_end):
                            print(f"[DEBUG] Email de {email_datetime.strftime('%Y-%m-%d %H:%M')} fuera de ventana {mode}")
                            continue
                        
                        print(f"[OK] Email encontrado dentro de ventana {mode}: {email_datetime.strftime('%Y-%m-%d %H:%M')}")
                    
                except Exception as e:
                    print(f"[WARN] No se pudo parsear fecha del email: {date_str} - {e}")
                    # Si no se puede parsear la fecha, continuar sin filtrar
                    pass

                from_raw = msg.get("From", "")
                from_decoded = decode_email_from(from_raw)

                body_text = extract_text_from_email_message(msg)
                clean_text = clean_df_oneclick_text(body_text)
                
                # LIMITAR TAMAÑO
                clean_text = truncate_text(clean_text, MAX_NEWSLETTER_CHARS)

                result = {
                    "from": from_decoded,
                    "subject": subj,
                    "date": date_str,
                    "raw_text": clean_text,
                }

                safe_imap_logout(mail)
                print(f"[OK] DF Primer Click encontrado para {mode}: subject={subj}")
                return result

            except Exception as e:
                print(f"[WARN] Error al procesar msg_id={msg_id}: {e}")
                continue

        safe_imap_logout(mail)
        print(f"[INFO] No se encontró email de DF Primer Click en ventana {mode}.")
        return None

    except Exception as e:
        print(f"[ERROR] Al buscar DF Primer Click: {e}")
        safe_imap_logout(mail)
        return None


# ------------------ RESUMEN DF (PDF → TXT) ----------------------------------

def find_latest_df_resumen_file(directory: str) -> Optional[str]:
    """Busca el archivo resumen_df_*.txt más reciente."""
    if not os.path.isdir(directory):
        print(f"[DF_RESUMEN] No existe el directorio: {directory}")
        return None

    files = os.listdir(directory)
    pattern = re.compile(r"resumen_df_\d{8}_\d{6}\.txt")
    candidatos = [f for f in files if pattern.match(f)]

    if not candidatos:
        print(f"[DF_RESUMEN] No se encontraron archivos resumen_df_*.txt en {directory}")
        return None

    candidatos.sort()
    latest = candidatos[-1]
    full_path = os.path.join(directory, latest)
    print(f"[DF_RESUMEN] Último archivo detectado: {full_path}")
    return full_path


def load_latest_df_resumen() -> Optional[Dict[str, Any]]:
    """Carga el último resumen del Diario Financiero desde DF_RESUMEN_DIR."""
    if not DF_RESUMEN_DIR:
        print("[DF_RESUMEN] DF_RESUMEN_DIR no está configurado.")
        return None

    latest_path = find_latest_df_resumen_file(DF_RESUMEN_DIR)
    if not latest_path:
        return None

    filename = os.path.basename(latest_path)

    try:
        base = filename.replace("resumen_df_", "").replace(".txt", "")
        date_str, time_str = base.split("_")
        file_date = datetime.strptime(date_str, "%Y%m%d").date()
        edition_date = file_date + timedelta(days=1)
    except Exception as e:
        print(f"[DF_RESUMEN] No se pudo parsear fecha desde '{filename}': {e}")
        edition_date = None

    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        print(f"[DF_RESUMEN] Error leyendo archivo {latest_path}: {e}")
        return None

    clean_text = clean_df_oneclick_text(raw_text)
    
    # LIMITAR TAMAÑO DEL RESUMEN
    clean_text = truncate_text(clean_text, MAX_DF_RESUMEN_CHARS)

    if not clean_text:
        print("[DF_RESUMEN] Texto vacío tras limpieza, se omite.")
        return None

    return {
        "source": "DF Diario completo (PDF procesado)",
        "file_path": latest_path,
        "edition_date": edition_date.isoformat() if edition_date else None,
        "raw_text": clean_text,
    }


# ------------------ NOTICIAS ------------------------------------------------

def fetch_news_from_newsapi(api_key: str, page_size: int = MAX_NEWSAPI_ITEMS) -> list[dict]:
    """Llama al endpoint /v2/top-headlines de NewsAPI."""
    if not api_key:
        print("NEWSAPI_KEY no definido.")
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "country": "us",
        "pageSize": page_size,
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[ERROR] NewsAPI: {e}")
        return []

    articles = data.get("articles", [])
    cleaned = []
    for art in articles:
        cleaned.append({
            "source": art.get("source", {}).get("name"),
            "title": art.get("title"),
            "description": art.get("description"),
            "url": art.get("url"),
            "published_at": art.get("publishedAt"),
        })
    
    print(f"[INFO] Noticias NewsAPI: {len(cleaned)} artículos.")
    return cleaned


def fetch_news_from_rss(limit_per_feed: int = 2) -> List[Dict[str, Any]]:
    """Obtiene noticias desde feeds RSS, limitando cantidad."""
    result: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()

    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"RSS error {source_name}: {e}")
            continue

        count = 0
        for entry in feed.entries:
            if count >= limit_per_feed:
                break
                
            title = getattr(entry, "title", None)
            if not title or title in seen_titles:
                continue

            seen_titles.add(title)
            result.append({
                "source": source_name,
                "title": title,
                "url": getattr(entry, "link", None),
                "published": getattr(entry, "published", None),
            })
            count += 1

        # Limitar total de noticias RSS
        if len(result) >= MAX_RSS_ITEMS:
            break

    print(f"[INFO] Noticias RSS: {len(result)} artículos.")
    return result


# ------------------ DATASET DIARIO -----------------------------------------

def build_daily_dataset(mode: str = "AM") -> dict:
    today = date.today()
    print(f"[INFO] Construyendo dataset diario para {today} - Modo: {mode}...")

    equity_block = build_asset_block(EQUITY_TICKERS)
    rates_block = build_asset_block(BOND_VOL_TICKERS)
    fx_block = build_asset_block(FX_TICKERS)
    commodities_block = build_asset_block(COMMODITY_TICKERS)

    # Chile: TPM, dólar observado, UF
    chile_info: Dict[str, Any] = {}
    
    for key, series_id in BCCH_SERIES.items():
        if not series_id or series_id.startswith("<"):
            if key == "dolar_obs":
                chile_info["dolar_observado"] = None
            else:
                chile_info[key] = None
            continue

        # Para IPSA, pedir más días históricos (necesitamos YTD)
        days_back = 400 if key == "ipsa" else 120
        bcch_data = fetch_bcch_series_last_value(series_id, days_back=days_back)
        
        # Si BCentral falla, NO usar fallback
        # (El dólar observado ≠ dólar de mercado)
        if bcch_data is None:
            if key == "dolar_obs":
                chile_info["dolar_observado"] = {
                    "value": None,
                    "error": "BCentral no disponible",
                    "note": "Dólar observado es promedio ponderado del día anterior publicado por BCCh. No equivale al tipo de cambio de mercado (CLP=X)."
                }
                print("[WARN] Dólar observado no disponible desde BCentral (sin fallback - observado ≠ mercado)")
            elif key == "ipsa":
                # Para IPSA, intentar fallback con Yahoo Finance (solo close y 1D)
                print("[WARN] IPSA no disponible desde BCentral, usando Yahoo Finance como fallback")
                ipsa_yahoo = equity_block.get("^IPSA", {})
                chile_info["ipsa"] = {
                    "close": ipsa_yahoo.get("close"),
                    "change_1d": ipsa_yahoo.get("change_pct"),
                    "change_mtd": None,
                    "change_ytd": None,
                    "date": None,
                    "source": "Yahoo Finance (fallback)",
                    "note": "MTD/YTD no disponibles sin datos BCCh"
                }
            else:
                chile_info[key] = None
            continue

        latest = bcch_data["latest"]

        if key == "ipsa":
            # ================================================================
            # IPSA con integración nueva: Yahoo + BCCh + días hábiles
            # ================================================================
            if IPSA_INTEGRATION_AVAILABLE:
                print("[IPSA] Usando ipsa_integration.py (Yahoo + BCCh + días hábiles bancarios)")
                chile_info["ipsa"] = calculate_ipsa_complete()
            else:
                # Fallback: Yahoo Finance solo
                print("[WARN] ipsa_integration.py no disponible, usando Yahoo Finance fallback")
                ipsa_yahoo = equity_block.get("^IPSA", {})
                chile_info["ipsa"] = {
                    "close": ipsa_yahoo.get("close"),
                    "date": ipsa_yahoo.get("last_date"),
                    "change_1d": ipsa_yahoo.get("change_pct"),
                    "change_mtd": None,
                    "change_ytd": None,
                    "source": "Yahoo Finance (fallback)",
                    "note": "MTD/YTD no disponibles sin ipsa_integration.py"
                }
            continue
        
        elif key == "dolar_obs":
            previous = bcch_data.get("previous")
            change_pct = bcch_data.get("change_pct")

            peso_direction: Optional[str] = None
            if change_pct is not None:
                if change_pct > 0:
                    peso_direction = "depreciación"
                elif change_pct < 0:
                    peso_direction = "apreciación"

            chile_info["dolar_observado"] = {
                "value": latest["value"],
                "prev_value": previous["value"] if previous else None,
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "peso_direction": peso_direction,
                "date": latest["date"],
                "prev_date": previous["date"] if previous else None,
            }
        else:
            chile_info[key] = {
                "value": latest["value"],
                "date": latest["date"],
            }

    rss_news = fetch_news_from_rss()
    newsapi_key = os.getenv("NEWSAPI_KEY")
    newsapi_news = fetch_news_from_newsapi(newsapi_key)

    news_block = {
        "rss": rss_news,
        "newsapi": newsapi_news,
    }

    # Newsletters (filtradas por modo AM/PM)
    newsletters_block: Dict[str, Any] = {}

    df_oneclick_data = fetch_latest_df_oneclick_email(mode)
    newsletters_block["df_primer_click"] = df_oneclick_data

    for spec in NEWSLETTER_SPECS:
        nl_data = fetch_latest_newsletter(spec, mode)  # Agregar parámetro mode
        newsletters_block[spec["key"]] = nl_data

    # WSJ PDF (descargado manualmente)
    if WSJ_PDF_AVAILABLE:
        try:
            print("[INFO] Intentando cargar WSJ PDF...")
            wsj_pdf_data = load_wsj_pdf_content()
            if wsj_pdf_data:
                newsletters_block["wsj_pdf"] = wsj_pdf_data
                print(f"[OK] WSJ PDF cargado: {wsj_pdf_data['num_pages']} páginas, {wsj_pdf_data['char_count']:,} caracteres")
            else:
                print("[WARN] WSJ PDF no encontrado - continuando sin él")
                newsletters_block["wsj_pdf"] = None
        except Exception as e:
            print(f"[ERROR] Error cargando WSJ PDF: {e}")
            newsletters_block["wsj_pdf"] = None
    else:
        print("[INFO] WSJ PDF parser no disponible")
        newsletters_block["wsj_pdf"] = None

    # AlphaVantage Data (Premium API) - MEJORADO con más topics y sentiment summary
    alphavantage_block: Dict[str, Any] = {}
    if ALPHAVANTAGE_AVAILABLE:
        try:
            print("[INFO] Fetching AlphaVantage data (enhanced)...")
            av_data = fetch_all_alphavantage_data(
                include_news=True,              # News con sentiment
                include_economic=True,          # Indicadores económicos US
                include_forex=False,            # USD/CLP (opcional, ya tenemos Yahoo)
                include_news_summary=True,      # 🆕 Resumen de sentiment por fuente
                news_hours_back=24,             # Noticias últimas 24h
                news_limit=200                  # 🆕 Aumentado a 200 (API Premium)
                # news_topics usa DEFAULT_NEWS_TOPICS automáticamente:
                # financial_markets, economy_macro, economy_monetary,
                # technology, earnings, energy_transportation, mergers_acquisitions
            )
            alphavantage_block = av_data

            # Resumen mejorado
            news_count = len(av_data.get("news_sentiment", [])) if av_data.get("news_sentiment") else 0
            econ_count = sum(1 for v in av_data.get("economic_indicators", {}).values() if v)
            summary = av_data.get("news_summary", {}).get("global", {})
            sentiment_label = summary.get("label", "N/A") if summary else "N/A"
            sentiment_score = summary.get("avg_score", 0) if summary else 0
            print(f"[OK] AlphaVantage: {news_count} news, {econ_count} economic indicators")
            print(f"[OK] News Sentiment: {sentiment_label} (score: {sentiment_score:.3f})")
            
        except Exception as e:
            print(f"[ERROR] Error fetching AlphaVantage data: {e}")
            import traceback
            traceback.print_exc()
            alphavantage_block = {}
    else:
        print("[INFO] AlphaVantage integration no disponible")
        alphavantage_block = {}

    # AlphaVantage Global Expansion (Treasury, DXY, Sector Sentiment, Forex)
    alphavantage_global: Dict[str, Any] = {}
    if ALPHAVANTAGE_GLOBAL_AVAILABLE:
        try:
            print("[INFO] Fetching AlphaVantage Global Expansion...")
            global_data = fetch_global_expansion_data()
            alphavantage_global = global_data
            
            # Resumen
            treasuries = 1 if global_data.get("treasury_yields") else 0
            dxy = 1 if global_data.get("dxy") else 0
            sectors = len(global_data.get("sector_sentiment", {}))
            forex = len([v for v in global_data.get("forex_expanded", {}).values() if v])
            print(f"[OK] Global Expansion: Treasuries={treasuries}, DXY={dxy}, Sectors={sectors}, Forex={forex}")
            
        except Exception as e:
            print(f"[ERROR] Error fetching Global Expansion data: {e}")
            import traceback
            traceback.print_exc()
            alphavantage_global = {}
    else:
        print("[INFO] AlphaVantage Global Expansion no disponible")
        alphavantage_global = {}

    # Resumen Diario Financiero PDF → txt
    df_resumen_data = load_latest_df_resumen()

    # 🆕 CRYPTO DATA (AlphaVantage + fallback yfinance)
    crypto_block: Dict[str, Any] = {}
    if ALPHAVANTAGE_AVAILABLE:
        try:
            print("\n" + "="*80)
            print("CRYPTO DATA FETCH - STARTING")
            print("="*80)

            # Precios de BTC y ETH
            crypto_prices = fetch_crypto_prices(["BTC", "ETH"])
            crypto_block = crypto_prices

            # Noticias crypto
            crypto_news = fetch_crypto_news(hours_back=24, limit=20)
            crypto_block["news"] = crypto_news

            print(f"[OK] Crypto data: BTC={'OK' if crypto_block.get('BTC') else 'None'}, "
                  f"ETH={'OK' if crypto_block.get('ETH') else 'None'}, "
                  f"news={len(crypto_news) if crypto_news else 0}")

        except Exception as e:
            print(f"[ERROR] Crypto data fetch failed: {e}")
            import traceback
            traceback.print_exc()

    # Fallback con yfinance si AlphaVantage no tiene datos
    if not crypto_block.get("BTC"):
        print("[INFO] Using yfinance fallback for BTC...")
        btc_yf = get_yfinance_metrics("BTC-USD")
        if btc_yf:
            crypto_block["BTC"] = btc_yf

    if not crypto_block.get("ETH"):
        print("[INFO] Using yfinance fallback for ETH...")
        eth_yf = get_yfinance_metrics("ETH-USD")
        if eth_yf:
            crypto_block["ETH"] = eth_yf

    dataset = {
        "date": today.isoformat(),
        "equity": equity_block,
        "rates_bonds": rates_block,
        "fx": fx_block,
        "commodities": commodities_block,
        "crypto": crypto_block,                          # 🆕 Cryptocurrencies (BTC, ETH)
        "chile": chile_info,
        "news": news_block,
        "newsletters": newsletters_block,
        "df_resumen_diario": df_resumen_data,
        "alphavantage": alphavantage_block,              # AlphaVantage base (news + economic)
        "alphavantage_global": alphavantage_global,      # Global expansion
    }

    # 🆕 CURATE NEWSLETTERS (Enhanced V2 - Cross-newsletter analysis)
    if NEWSLETTER_CURATOR_AVAILABLE and newsletters_block:
        print("\n" + "="*80)
        print("NEWSLETTER CURATION - STARTING")
        print("="*80)
        
        try:
            # Pasar newsletters + DF Resumen
            curation_result = curate_all_newsletters_enhanced(
                newsletters_block, 
                df_resumen_data  # Agregar DF Resumen también
            )
            dataset["news_curated"] = curation_result
            
            # Stats
            stats = curation_result.get("statistics", {})
            high_count = stats.get("high_importance_news", 0)
            total_count = stats.get("total_news", 0)
            hot_topics = curation_result.get("cross_newsletter_insights", {}).get("hot_topics", {})
            
            print(f"\n[OK] Newsletter curation complete:")
            print(f"  • {total_count} news items processed")
            print(f"  • {high_count} high importance items ({high_count/total_count*100:.0f}%)" if total_count > 0 else "")
            if hot_topics:
                top_topics = sorted(hot_topics.items(), key=lambda x: x[1], reverse=True)[:3]
                print(f"  • Top topics: {', '.join([f'{t[0]} ({t[1]})' for t in top_topics])}")
        
        except Exception as e:
            print(f"[ERROR] Newsletter curation failed: {e}")
            import traceback
            traceback.print_exc()
            dataset["news_curated"] = {"error": str(e)}
    else:
        if not NEWSLETTER_CURATOR_AVAILABLE:
            print("[INFO] Newsletter curator not available - skipping curation")
        if not newsletters_block:
            print("[INFO] No newsletters to curate")

    # CALCULAR SENTIMENT
    sentiment_data = calculate_sentiment_score(dataset)
    dataset["sentiment"] = sentiment_data
    
    # ACTUALIZAR HISTORIAL
    sentiment_history = update_sentiment_history(today.isoformat(), sentiment_data)
    recent_trend = get_recent_sentiment_trend(sentiment_history, days=7)
    dataset["sentiment_history_7d"] = recent_trend

    # 🆕 GUARDAR CONTENIDO USADO PARA DEDUPLICACIÓN AM/PM
    if "news_curated" in dataset and "error" not in dataset.get("news_curated", {}):
        save_used_content_for_mode(today.isoformat(), mode, dataset["news_curated"])

    print(
        f"[RESUMEN DATA] equity={len(equity_block)}, "
        f"rates={len(rates_block)}, fx={len(fx_block)}, "
        f"commodities={len(commodities_block)}, "
        f"crypto={'OK' if crypto_block.get('BTC') else 'None'}, "
        f"rss_news={len(rss_news)}, newsapi={len(newsapi_news)}, "
        f"newsletters={len(newsletters_block)}, "
        f"news_curated={'OK' if 'news_curated' in dataset and 'error' not in dataset['news_curated'] else 'None'}, "
        f"df_resumen_diario={'OK' if df_resumen_data else 'None'}, "
        f"alphavantage={'OK' if alphavantage_block else 'None'}, "
        f"alphavantage_global={'OK' if alphavantage_global else 'None'}, "
        f"sentiment={sentiment_data['sentiment']}"
    )

    return dataset


# ------------------ MODO AM / PM -------------------------------------------

# ------------------ MAIN ----------------------------------------------------

def detect_report_mode() -> str:
    """Detecta si es AM o PM basado en la hora actual EN CHILE"""
    if CHILE_TIMEZONE_AVAILABLE:
        now_chile = get_chile_now()
        now_time = now_chile.time()
    else:
        now_time = datetime.now().time()
    
    if now_time < time(12, 0):
        return "AM"
    else:
        return "PM"


def main(output_path: str = None, mode: Optional[str] = None) -> None:
    """
    Recopila datos de mercados y los guarda en JSON.
    La generación de reportes se hace por separado con generate_daily_report.py
    
    Args:
        output_path: Ruta donde guardar el JSON principal
        mode: "AM" o "PM" (si no se especifica, se detecta automáticamente)
    """
    if mode is None:
        mode = detect_report_mode()
        if CHILE_TIMEZONE_AVAILABLE:
            now_chile = get_chile_now()
            print(f"[INFO] Modo detectado automáticamente: {mode} (hora Chile: {now_chile.strftime('%H:%M %Z')})")
        else:
            print(f"[INFO] Modo detectado automáticamente: {mode}")
    
    dataset = build_daily_dataset(mode)
    
    # Guardar archivo principal (se sobrescribe cada vez)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Dataset diario guardado en {output_path}")
    
    # Guardar copia con fecha en carpeta history (para reporte semanal)
    history_dir = "history"
    os.makedirs(history_dir, exist_ok=True)
    
    today = date.today().isoformat()
    history_filename = f"daily_market_snapshot_{today}_{mode}.json"
    history_path = os.path.join(history_dir, history_filename)
    
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Copia histórica guardada en {history_path}")
    print(f"[INFO] Este archivo será usado para el reporte cuantitativo semanal")
    
    # Limpieza: Eliminar archivos más antiguos de 30 días
    try:
        cutoff_date = date.today() - timedelta(days=30)
        deleted_count = 0
        
        for filename in os.listdir(history_dir):
            if filename.startswith("daily_market_snapshot_") and filename.endswith(".json"):
                # Extraer fecha del nombre: daily_market_snapshot_2025-12-16_AM.json
                try:
                    date_part = filename.split("_")[3]  # "2025-12-16"
                    file_date = date.fromisoformat(date_part)
                    
                    if file_date < cutoff_date:
                        file_path = os.path.join(history_dir, filename)
                        os.remove(file_path)
                        deleted_count += 1
                except:
                    continue
        
        if deleted_count > 0:
            print(f"[INFO] Limpieza: {deleted_count} archivos antiguos eliminados (>30 días)")
    except Exception as e:
        print(f"[WARN] Error en limpieza de archivos históricos: {e}")


if __name__ == "__main__":
    import sys
    # Permitir especificar modo desde línea de comandos
    # Uso: python daily_market_snapshot.py [AM|PM]
    mode = sys.argv[1].upper() if len(sys.argv) > 1 else None
    
    # Siempre usar el mismo nombre de archivo (el modo solo afecta la ventana de captura)
    output_file = "daily_market_snapshot.json"
    
    main(output_file, mode)


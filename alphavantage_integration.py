# -*- coding: utf-8 -*-
"""
ALPHAVANTAGE INTEGRATION MODULE
Grey Bark Advisors - Premium API Integration

CONFIGURACIÓN:
API Key debe estar en .env como: ALPHAVANTAGE_API_KEY=tu_key_aqui
Premium: 75 requests/min

ENDPOINTS IMPLEMENTADOS:
1. NEWS_SENTIMENT - Noticias con sentiment cuantificado
2. ECONOMIC_INDICATORS - Datos macro US (Fed, CPI, Unemployment, Treasury)
3. FOREX (opcional) - USD/CLP más preciso
4. DIGITAL_CURRENCY_DAILY - Precios crypto (BTC, ETH)
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import time

# API Configuration
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Rate limiting (75 req/min premium = 1 request cada 0.8 segundos)
# Dejamos margen de seguridad: 1 request cada 1 segundo
REQUEST_DELAY = 1.0  # segundos entre requests

# Topics disponibles en Alpha Vantage NEWS_SENTIMENT
ALL_NEWS_TOPICS = [
    "technology",           # Tech stocks y tendencias
    "financial_markets",    # Mercados financieros general
    "economy_macro",        # Economía macro
    "economy_fiscal",       # Política fiscal
    "economy_monetary",     # Política monetaria (Fed, tasas)
    "earnings",             # Reportes de ganancias corporativas
    "ipo",                  # Salidas a bolsa
    "mergers_acquisitions", # Fusiones y adquisiciones
    "energy_transportation",# Energía y commodities
    "finance",              # Sector financiero/bancos
    "life_sciences",        # Pharma/Biotech
    "manufacturing",        # Manufactura
    "real_estate",          # Bienes raíces
    "retail_wholesale"      # Retail
]

# Topics principales para el reporte diario (balanceado)
DEFAULT_NEWS_TOPICS = [
    "financial_markets",    # Core: mercados
    "economy_macro",        # Core: macro
    "economy_monetary",     # Core: política monetaria
    "technology",           # Importante: tech
    "earnings",             # Importante: earnings
    "energy_transportation",# Importante: commodities
    "mergers_acquisitions"  # Importante: M&A
]

# Tickers de portafolio típico para filtrar noticias relevantes
DEFAULT_PORTFOLIO_TICKERS = [
    # US Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    # US Financials
    "JPM", "BAC", "GS", "MS",
    # Índices (ETFs proxy)
    "SPY", "QQQ", "EEM",
    # Commodities relacionados
    "XLE", "XLF", "GLD", "USO"
]


def get_api_key() -> Optional[str]:
    """
    Obtiene la API key de AlphaVantage desde variables de entorno
    """
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("[ERROR] ALPHAVANTAGE_API_KEY no encontrada en variables de entorno")
        print("[TIP] Agregar a .env: ALPHAVANTAGE_API_KEY=tu_key_aqui")
    return api_key


# ==============================================================================
# 1. NEWS & SENTIMENT API
# ==============================================================================

def fetch_alphavantage_news_sentiment(
    topics: List[str] = None,
    tickers: List[str] = None,
    hours_back: int = 24,
    limit: int = 50,
    sort: str = "RELEVANCE"
) -> Optional[List[Dict[str, Any]]]:
    """
    Obtiene noticias con sentiment de AlphaVantage
    
    Args:
        topics: Lista de topics a filtrar (ej: ['technology', 'financial_markets'])
        tickers: Lista de tickers a filtrar (ej: ['AAPL', 'MSFT'])
        hours_back: Horas hacia atrás para buscar noticias
        limit: Número máximo de noticias (max 1000)
        sort: 'RELEVANCE' o 'LATEST'
    
    Topics disponibles:
        - technology
        - financial_markets
        - economy_macro
        - economy_fiscal
        - economy_monetary
        - earnings
        - ipo
        - mergers_acquisitions
        - energy_transportation
        - finance
        - life_sciences
        - manufacturing
        - real_estate
        - retail_wholesale
    
    Returns:
        Lista de noticias con sentiment, o None si falla
    """
    api_key = get_api_key()
    if not api_key:
        return None
    
    # Calcular time_from (últimas N horas)
    time_from = (datetime.now() - timedelta(hours=hours_back)).strftime("%Y%m%dT%H%M")
    
    # Construir parámetros
    params = {
        "function": "NEWS_SENTIMENT",
        "apikey": api_key,
        "sort": sort,
        "limit": limit,
        "time_from": time_from
    }
    
    # Agregar topics si se especificaron
    if topics:
        params["topics"] = ",".join(topics)
    
    # Agregar tickers si se especificaron
    if tickers:
        params["tickers"] = ",".join(tickers)
    
    try:
        print(f"[INFO] Fetching AlphaVantage news (last {hours_back}h, limit={limit})...")
        
        response = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Verificar si hay error
        if "Error Message" in data or "Note" in data:
            print(f"[ERROR] AlphaVantage API error: {data}")
            return None
        
        # Parsear feed de noticias
        feed = data.get("feed", [])
        
        if not feed:
            print("[WARN] No news found in AlphaVantage response")
            return []
        
        # Estructurar noticias
        news = []
        for item in feed:
            news.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "time_published": item.get("time_published", ""),
                "sentiment_score": float(item.get("overall_sentiment_score", 0)),
                "sentiment_label": item.get("overall_sentiment_label", "Neutral"),
                "relevance_score": float(item.get("relevance_score", 0)) if "relevance_score" in item else None,
                "ticker_sentiment": item.get("ticker_sentiment", [])
            })
        
        print(f"[OK] AlphaVantage news: {len(news)} articles fetched")
        
        # Rate limiting delay
        time.sleep(REQUEST_DELAY)
        
        return news
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] AlphaVantage news request failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] AlphaVantage news parsing error: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_news_by_topic(
    topic: str,
    hours_back: int = 24,
    limit: int = 30
) -> Optional[List[Dict[str, Any]]]:
    """
    Obtiene noticias filtradas por un topic específico

    Args:
        topic: Topic a filtrar (ej: 'earnings', 'mergers_acquisitions')
        hours_back: Horas hacia atrás
        limit: Límite de noticias

    Returns:
        Lista de noticias del topic específico
    """
    return fetch_alphavantage_news_sentiment(
        topics=[topic],
        hours_back=hours_back,
        limit=limit,
        sort="LATEST"
    )


def fetch_news_by_portfolio(
    tickers: List[str] = None,
    hours_back: int = 24,
    limit: int = 50
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Obtiene noticias relevantes para tickers específicos del portafolio

    Args:
        tickers: Lista de tickers (default: DEFAULT_PORTFOLIO_TICKERS)
        hours_back: Horas hacia atrás
        limit: Límite total de noticias

    Returns:
        Dict con noticias organizadas por ticker
    """
    if tickers is None:
        tickers = DEFAULT_PORTFOLIO_TICKERS

    print(f"[INFO] Fetching portfolio news for {len(tickers)} tickers...")

    # Obtener todas las noticias de los tickers
    all_news = fetch_alphavantage_news_sentiment(
        tickers=tickers,
        hours_back=hours_back,
        limit=limit,
        sort="RELEVANCE"
    )

    if not all_news:
        return {}

    # Organizar por ticker
    news_by_ticker = {ticker: [] for ticker in tickers}
    news_by_ticker["_general"] = []  # Noticias sin ticker específico

    for article in all_news:
        ticker_sentiments = article.get("ticker_sentiment", [])

        if ticker_sentiments:
            # Asignar a cada ticker mencionado
            for ts in ticker_sentiments:
                ticker = ts.get("ticker", "")
                if ticker in news_by_ticker:
                    # Agregar relevance del ticker específico
                    article_copy = article.copy()
                    article_copy["ticker_relevance"] = float(ts.get("relevance_score", 0))
                    article_copy["ticker_sentiment_score"] = float(ts.get("ticker_sentiment_score", 0))
                    article_copy["ticker_sentiment_label"] = ts.get("ticker_sentiment_label", "Neutral")
                    news_by_ticker[ticker].append(article_copy)
        else:
            news_by_ticker["_general"].append(article)

    # Contar resultados
    total = sum(len(v) for v in news_by_ticker.values())
    tickers_with_news = sum(1 for k, v in news_by_ticker.items() if v and k != "_general")

    print(f"[OK] Portfolio news: {total} articles for {tickers_with_news} tickers")

    return news_by_ticker


def fetch_news_categorized(
    topics: List[str] = None,
    hours_back: int = 24,
    limit_per_topic: int = 30
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Obtiene noticias organizadas por categoría/topic

    Args:
        topics: Lista de topics (default: DEFAULT_NEWS_TOPICS)
        hours_back: Horas hacia atrás
        limit_per_topic: Límite por cada topic

    Returns:
        Dict con noticias organizadas por topic
    """
    if topics is None:
        topics = DEFAULT_NEWS_TOPICS

    print(f"[INFO] Fetching categorized news for {len(topics)} topics...")

    result = {}

    for topic in topics:
        print(f"  → {topic}...")
        news = fetch_news_by_topic(topic, hours_back, limit_per_topic)
        result[topic] = news if news else []
        time.sleep(REQUEST_DELAY)  # Rate limiting entre topics

    # Stats
    total = sum(len(v) for v in result.values())
    topics_with_news = sum(1 for v in result.values() if v)

    print(f"[OK] Categorized news: {total} articles across {topics_with_news} topics")

    return result


def calculate_sentiment_summary(news_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcula resumen de sentiment para una lista de noticias

    Args:
        news_list: Lista de noticias con sentiment_score

    Returns:
        Dict con métricas de sentiment agregadas
    """
    if not news_list:
        return {
            "count": 0,
            "avg_score": None,
            "label": "No Data",
            "bullish_count": 0,
            "bearish_count": 0,
            "neutral_count": 0,
            "bullish_pct": 0,
            "bearish_pct": 0
        }

    scores = [n.get("sentiment_score", 0) for n in news_list if n.get("sentiment_score") is not None]
    labels = [n.get("sentiment_label", "Neutral") for n in news_list]

    bullish = sum(1 for l in labels if l in ["Bullish", "Somewhat-Bullish"])
    bearish = sum(1 for l in labels if l in ["Bearish", "Somewhat-Bearish"])
    neutral = sum(1 for l in labels if l == "Neutral")

    total = len(news_list)
    avg_score = sum(scores) / len(scores) if scores else 0

    # Determinar label agregado
    if avg_score >= 0.15:
        agg_label = "Bullish"
    elif avg_score >= 0.05:
        agg_label = "Somewhat-Bullish"
    elif avg_score <= -0.15:
        agg_label = "Bearish"
    elif avg_score <= -0.05:
        agg_label = "Somewhat-Bearish"
    else:
        agg_label = "Neutral"

    return {
        "count": total,
        "avg_score": round(avg_score, 4),
        "label": agg_label,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "bullish_pct": round((bullish / total) * 100, 1) if total > 0 else 0,
        "bearish_pct": round((bearish / total) * 100, 1) if total > 0 else 0
    }


def fetch_news_with_sentiment_summary(
    topics: List[str] = None,
    hours_back: int = 24,
    limit: int = 200,
    fallback_no_topics: bool = True
) -> Dict[str, Any]:
    """
    Obtiene noticias con resumen de sentiment por categoría

    Args:
        topics: Lista de topics (None = sin filtro, obtiene todas las noticias)
        hours_back: Horas hacia atrás
        limit: Límite total de noticias
        fallback_no_topics: Si True y no hay resultados con topics, intenta sin filtro

    Returns:
        Dict con noticias, resumen global y resumen por categoría
    """
    print(f"[INFO] Fetching news with sentiment summary...")

    # Obtener todas las noticias (sin filtro de topics para mayor cobertura)
    all_news = fetch_alphavantage_news_sentiment(
        topics=topics,  # None = sin filtro
        hours_back=hours_back,
        limit=limit,
        sort="RELEVANCE"
    )

    # Fallback: si no hay noticias con topics, intentar sin filtro
    if (not all_news or len(all_news) == 0) and topics is not None and fallback_no_topics:
        print(f"[INFO] No news with topics filter, trying without filter...")
        all_news = fetch_alphavantage_news_sentiment(
            topics=None,
            hours_back=hours_back,
            limit=limit,
            sort="RELEVANCE"
        )

    if not all_news:
        return {
            "news": [],
            "summary_global": calculate_sentiment_summary([]),
            "summary_by_source": {},
            "top_bullish": [],
            "top_bearish": []
        }

    # Resumen global
    summary_global = calculate_sentiment_summary(all_news)

    # Resumen por fuente (source)
    news_by_source = {}
    for article in all_news:
        source = article.get("source", "Unknown")
        if source not in news_by_source:
            news_by_source[source] = []
        news_by_source[source].append(article)

    summary_by_source = {
        source: calculate_sentiment_summary(articles)
        for source, articles in news_by_source.items()
    }

    # Top bullish y bearish
    sorted_by_sentiment = sorted(all_news, key=lambda x: x.get("sentiment_score", 0), reverse=True)
    top_bullish = sorted_by_sentiment[:5]
    top_bearish = sorted_by_sentiment[-5:][::-1]

    print(f"[OK] News summary: {len(all_news)} articles, avg sentiment: {summary_global['avg_score']:.3f} ({summary_global['label']})")

    return {
        "news": all_news,
        "summary_global": summary_global,
        "summary_by_source": summary_by_source,
        "top_bullish": top_bullish,
        "top_bearish": top_bearish
    }


# ==============================================================================
# 2. ECONOMIC INDICATORS API
# ==============================================================================

def fetch_economic_indicator(indicator: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un indicador económico de US desde AlphaVantage
    
    Args:
        indicator: Nombre del indicador (ej: 'FEDERAL_FUNDS_RATE', 'CPI', etc)
    
    Returns:
        Dict con valor y fecha del último dato, o None si falla
    """
    api_key = get_api_key()
    if not api_key:
        return None
    
    params = {
        "function": indicator,
        "apikey": api_key
    }
    
    # Para TREASURY_YIELD necesitamos maturity
    if indicator == "TREASURY_YIELD":
        params["maturity"] = "10year"
    
    try:
        print(f"[INFO] Fetching {indicator}...")
        
        response = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Verificar error
        if "Error Message" in data or "Note" in data:
            print(f"[ERROR] AlphaVantage {indicator} error: {data}")
            return None
        
        # Extraer último valor
        data_list = data.get("data", [])
        
        if not data_list:
            print(f"[WARN] No data found for {indicator}")
            return None
        
        latest = data_list[0]
        
        result = {
            "indicator": indicator,
            "value": latest.get("value"),
            "date": latest.get("date"),
            "name": data.get("name", indicator),
            "unit": data.get("unit", "")
        }
        
        print(f"[OK] {indicator}: {result['value']} ({result['date']})")
        
        # Rate limiting delay
        time.sleep(REQUEST_DELAY)
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] AlphaVantage {indicator} request failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] AlphaVantage {indicator} parsing error: {e}")
        return None


def fetch_us_economic_indicators() -> Dict[str, Any]:
    """
    Obtiene los indicadores económicos clave de US
    
    Indicadores:
    - Fed Funds Rate (tasa de interés Fed)
    - CPI (inflación)
    - Unemployment Rate
    - Treasury Yield 10Y
    
    Returns:
        Dict con todos los indicadores, o valores None si fallan
    """
    print("[INFO] Fetching US economic indicators from AlphaVantage...")
    
    indicators = {
        "fed_rate": "FEDERAL_FUNDS_RATE",
        "cpi": "CPI",
        "unemployment": "UNEMPLOYMENT",
        "treasury_10y": "TREASURY_YIELD"
    }
    
    results = {}
    
    for key, function in indicators.items():
        data = fetch_economic_indicator(function)
        results[key] = data
    
    print(f"[OK] US economic indicators: {sum(1 for v in results.values() if v)} of {len(indicators)} fetched")
    
    return results


# ==============================================================================
# 3. FOREX API (OPCIONAL)
# ==============================================================================

def fetch_forex_rate(from_currency: str = "USD", to_currency: str = "CLP") -> Optional[Dict[str, Any]]:
    """
    Obtiene tipo de cambio actualizado de AlphaVantage
    
    Args:
        from_currency: Moneda origen (default: USD)
        to_currency: Moneda destino (default: CLP)
    
    Returns:
        Dict con tipo de cambio y metadata, o None si falla
    """
    api_key = get_api_key()
    if not api_key:
        return None
    
    params = {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency,
        "to_currency": to_currency,
        "apikey": api_key
    }
    
    try:
        print(f"[INFO] Fetching {from_currency}/{to_currency} exchange rate...")
        
        response = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Verificar error
        if "Error Message" in data or "Note" in data:
            print(f"[ERROR] AlphaVantage forex error: {data}")
            return None
        
        # Extraer datos
        rate_data = data.get("Realtime Currency Exchange Rate", {})
        
        if not rate_data:
            print(f"[WARN] No forex data found for {from_currency}/{to_currency}")
            return None
        
        result = {
            "from_currency": rate_data.get("1. From_Currency Code"),
            "to_currency": rate_data.get("3. To_Currency Code"),
            "exchange_rate": float(rate_data.get("5. Exchange Rate", 0)),
            "last_refreshed": rate_data.get("6. Last Refreshed"),
            "time_zone": rate_data.get("7. Time Zone"),
            "bid_price": float(rate_data.get("8. Bid Price", 0)),
            "ask_price": float(rate_data.get("9. Ask Price", 0))
        }
        
        print(f"[OK] {from_currency}/{to_currency}: {result['exchange_rate']:.2f}")
        
        # Rate limiting delay
        time.sleep(REQUEST_DELAY)
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] AlphaVantage forex request failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] AlphaVantage forex parsing error: {e}")
        return None


# ==============================================================================
# 4. CRYPTOCURRENCY API
# ==============================================================================

def fetch_crypto_daily(symbol: str = "BTC", market: str = "USD") -> Optional[Dict[str, Any]]:
    """
    Obtiene datos diarios de una criptomoneda usando DIGITAL_CURRENCY_DAILY

    Args:
        symbol: Símbolo de la cripto (BTC, ETH, etc)
        market: Moneda de mercado (default: USD)

    Returns:
        Dict con precio actual, cambios 1D/MTD/YTD, o None si falla
    """
    api_key = get_api_key()
    if not api_key:
        return None

    params = {
        "function": "DIGITAL_CURRENCY_DAILY",
        "symbol": symbol,
        "market": market,
        "apikey": api_key
    }

    try:
        print(f"[INFO] Fetching {symbol}/{market} crypto data...")

        response = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        # Verificar error
        if "Error Message" in data or "Note" in data:
            print(f"[ERROR] AlphaVantage crypto error: {data}")
            return None

        # Extraer serie temporal
        time_series = data.get("Time Series (Digital Currency Daily)", {})

        if not time_series:
            print(f"[WARN] No crypto data found for {symbol}")
            return None

        # Obtener fechas ordenadas (más reciente primero)
        dates = sorted(time_series.keys(), reverse=True)

        if len(dates) < 2:
            print(f"[WARN] Insufficient data for {symbol}")
            return None

        # Datos de hoy y ayer
        today_date = dates[0]
        yesterday_date = dates[1]

        today_data = time_series[today_date]
        yesterday_data = time_series[yesterday_date]

        # Extraer precios (close en USD)
        close_key = f"4a. close ({market})"
        today_close = float(today_data.get(close_key, 0))
        yesterday_close = float(yesterday_data.get(close_key, 0))

        # Calcular cambio 1D
        change_1d = ((today_close / yesterday_close) - 1) * 100 if yesterday_close > 0 else None

        # Calcular MTD (inicio del mes)
        current_month = today_date[:7]  # YYYY-MM
        month_start_price = None
        for d in reversed(dates):
            if d.startswith(current_month):
                month_start_price = float(time_series[d].get(close_key, 0))
                break

        change_mtd = ((today_close / month_start_price) - 1) * 100 if month_start_price and month_start_price > 0 else None

        # Calcular YTD (inicio del año)
        current_year = today_date[:4]
        year_start_price = None
        for d in reversed(dates):
            if d.startswith(current_year):
                year_start_price = float(time_series[d].get(close_key, 0))
                break

        change_ytd = ((today_close / year_start_price) - 1) * 100 if year_start_price and year_start_price > 0 else None

        result = {
            "symbol": symbol,
            "close": round(today_close, 2),
            "change_1d": round(change_1d, 2) if change_1d is not None else None,
            "change_mtd": round(change_mtd, 2) if change_mtd is not None else None,
            "change_ytd": round(change_ytd, 2) if change_ytd is not None else None,
            "date": today_date,
            "market": market,
            "source": "AlphaVantage"
        }

        print(f"[OK] {symbol}: ${result['close']:,.2f} ({result['change_1d']:+.2f}% 1D)")

        # Rate limiting delay
        time.sleep(REQUEST_DELAY)

        return result

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] AlphaVantage crypto request failed: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] AlphaVantage crypto parsing error: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_crypto_prices(symbols: List[str] = None) -> Dict[str, Any]:
    """
    Obtiene precios de múltiples criptomonedas

    Args:
        symbols: Lista de símbolos (default: ["BTC", "ETH"])

    Returns:
        Dict con datos de cada cripto
    """
    if symbols is None:
        symbols = ["BTC", "ETH"]

    print(f"[INFO] Fetching crypto prices for: {', '.join(symbols)}")

    result = {}

    for symbol in symbols:
        data = fetch_crypto_daily(symbol)
        result[symbol] = data

    success = sum(1 for v in result.values() if v is not None)
    print(f"[OK] Crypto prices: {success}/{len(symbols)} fetched")

    return result


def fetch_crypto_news(hours_back: int = 24, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
    """
    Obtiene noticias relacionadas con criptomonedas

    Args:
        hours_back: Horas hacia atrás para buscar
        limit: Número máximo de noticias

    Returns:
        Lista de noticias crypto con sentiment
    """
    print(f"[INFO] Fetching crypto news (last {hours_back}h)...")

    # Usar tickers relacionados con crypto
    # COIN = Coinbase, también buscar por topic blockchain
    news = fetch_alphavantage_news_sentiment(
        tickers=["COIN", "MSTR", "RIOT", "MARA"],  # Crypto-related stocks
        hours_back=hours_back,
        limit=limit,
        sort="LATEST"
    )

    if news:
        # Filtrar solo noticias que mencionan crypto keywords
        crypto_keywords = ["bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain", "coinbase"]
        crypto_news = []

        for article in news:
            title_lower = article.get("title", "").lower()
            summary_lower = article.get("summary", "").lower()

            # Verificar si menciona crypto
            if any(kw in title_lower or kw in summary_lower for kw in crypto_keywords):
                crypto_news.append(article)

        print(f"[OK] Crypto news: {len(crypto_news)} articles (filtered from {len(news)})")
        return crypto_news

    return news


# ==============================================================================
# WRAPPER FUNCTION - TODO EN UNO
# ==============================================================================

def fetch_all_alphavantage_data(
    include_news: bool = True,
    include_economic: bool = True,
    include_forex: bool = False,
    include_news_summary: bool = True,
    news_hours_back: int = 24,
    news_limit: int = 200,
    news_topics: List[str] = None
) -> Dict[str, Any]:
    """
    Wrapper para obtener todos los datos de AlphaVantage en una sola llamada

    Args:
        include_news: Incluir noticias con sentiment
        include_economic: Incluir indicadores económicos US
        include_forex: Incluir USD/CLP (opcional)
        include_news_summary: Incluir resumen de sentiment (recomendado)
        news_hours_back: Horas hacia atrás para noticias
        news_limit: Límite de noticias (default 200 para API pagada)
        news_topics: Lista de topics (default: DEFAULT_NEWS_TOPICS)

    Returns:
        Dict con todos los datos solicitados
    """
    # No forzamos topics por defecto - sin filtro obtiene más noticias
    # El usuario puede pasar topics específicos si lo desea

    print("="*80)
    print("ALPHAVANTAGE DATA FETCH - STARTING")
    print("="*80)

    result = {}

    # 1. News & Sentiment (mejorado con summary)
    if include_news:
        if include_news_summary:
            # Usar la nueva función con resumen
            news_data = fetch_news_with_sentiment_summary(
                topics=news_topics,  # None = todas las noticias sin filtro
                hours_back=news_hours_back,
                limit=news_limit,
                fallback_no_topics=True
            )
            result["news_sentiment"] = news_data.get("news", [])
            result["news_summary"] = {
                "global": news_data.get("summary_global", {}),
                "by_source": news_data.get("summary_by_source", {}),
                "top_bullish": news_data.get("top_bullish", []),
                "top_bearish": news_data.get("top_bearish", [])
            }
        else:
            # Fallback al método anterior
            news = fetch_alphavantage_news_sentiment(
                topics=news_topics,
                hours_back=news_hours_back,
                limit=news_limit
            )
            result["news_sentiment"] = news

    # 2. Economic Indicators
    if include_economic:
        economic = fetch_us_economic_indicators()
        result["economic_indicators"] = economic

    # 3. Forex (opcional)
    if include_forex:
        forex = fetch_forex_rate("USD", "CLP")
        result["forex_usdclp"] = forex

    print("="*80)
    print("ALPHAVANTAGE DATA FETCH - COMPLETE")
    print("="*80)

    return result


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("="*80)
    print("ALPHAVANTAGE MODULE - TEST")
    print("="*80)
    
    # Verificar API key
    api_key = get_api_key()
    if not api_key:
        print("\n[ERROR] No API key found. Add to .env:")
        print("ALPHAVANTAGE_API_KEY=your_key_here")
        exit(1)
    
    print(f"\n✓ API Key found: {api_key[:10]}...")
    
    # Test 1: News & Sentiment
    print("\n" + "="*80)
    print("TEST 1: NEWS & SENTIMENT")
    print("="*80)
    
    news = fetch_alphavantage_news_sentiment(
        topics=["technology", "financial_markets"],
        hours_back=24,
        limit=10
    )
    
    if news:
        print(f"\n✓ Found {len(news)} news articles")
        print("\nFirst 3 articles:")
        for i, article in enumerate(news[:3], 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Source: {article['source']}")
            print(f"   Sentiment: {article['sentiment_label']} ({article['sentiment_score']:.3f})")
            print(f"   Time: {article['time_published']}")
    else:
        print("\n✗ News fetch failed")
    
    # Test 2: Economic Indicators
    print("\n" + "="*80)
    print("TEST 2: ECONOMIC INDICATORS")
    print("="*80)
    
    economic = fetch_us_economic_indicators()
    
    if economic:
        print("\n✓ Economic indicators:")
        for key, data in economic.items():
            if data:
                print(f"  {key}: {data['value']} ({data['date']})")
            else:
                print(f"  {key}: Failed")
    else:
        print("\n✗ Economic indicators fetch failed")
    
    # Test 3: Forex (opcional)
    print("\n" + "="*80)
    print("TEST 3: FOREX USD/CLP (opcional)")
    print("="*80)
    
    forex = fetch_forex_rate("USD", "CLP")
    
    if forex:
        print(f"\n✓ USD/CLP: {forex['exchange_rate']:.2f}")
        print(f"  Last updated: {forex['last_refreshed']}")
    else:
        print("\n✗ Forex fetch failed")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

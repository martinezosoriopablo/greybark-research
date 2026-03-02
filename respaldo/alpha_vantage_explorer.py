"""
ALPHA VANTAGE - EXPLORADOR COMPLETO
Muestra todas las capacidades de Alpha Vantage API
"""

import requests
import json
from datetime import datetime

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

API_KEY = "demo"  # Reemplaza con tu API key
BASE_URL = "https://www.alphavantage.co/query"


def make_request(params):
    """Hace request a Alpha Vantage y retorna JSON"""
    params['apikey'] = API_KEY
    try:
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        # Check for API limit
        if "Note" in data:
            print(f"⚠️  API LIMIT: {data['Note']}")
            return None
        
        if "Error Message" in data:
            print(f"❌ ERROR: {data['Error Message']}")
            return None
            
        return data
    except Exception as e:
        print(f"❌ Request error: {e}")
        return None


# ============================================================================
# 1. STOCK DATA (DATOS DE ACCIONES)
# ============================================================================

def explore_stock_data():
    """Explora datos de acciones"""
    print("\n" + "="*80)
    print("1. STOCK DATA (DATOS DE ACCIONES)")
    print("="*80)
    
    symbol = "AAPL"  # Puedes cambiar a cualquier ticker
    
    # 1A. TIME SERIES INTRADAY (cada 5min)
    print(f"\n📈 1A. INTRADAY (cada 5 min) - {symbol}")
    params = {
        'function': 'TIME_SERIES_INTRADAY',
        'symbol': symbol,
        'interval': '5min',
        'outputsize': 'compact'  # compact = últimos 100 puntos, full = 30 días
    }
    data = make_request(params)
    if data:
        ts_key = 'Time Series (5min)'
        if ts_key in data:
            latest = list(data[ts_key].items())[0]
            print(f"   Última actualización: {latest[0]}")
            print(f"   Open: ${latest[1]['1. open']}")
            print(f"   High: ${latest[1]['2. high']}")
            print(f"   Low: ${latest[1]['3. low']}")
            print(f"   Close: ${latest[1]['4. close']}")
            print(f"   Volume: {latest[1]['5. volume']}")
    
    # 1B. TIME SERIES DAILY (diario)
    print(f"\n📊 1B. DAILY (histórico diario) - {symbol}")
    params = {
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'outputsize': 'compact'  # últimos 100 días
    }
    data = make_request(params)
    if data and 'Time Series (Daily)' in data:
        latest = list(data['Time Series (Daily)'].items())[0]
        print(f"   Fecha: {latest[0]}")
        print(f"   Close: ${latest[1]['4. close']}")
        print(f"   Volume: {latest[1]['5. volume']}")
    
    # 1C. QUOTE ENDPOINT (precio actual)
    print(f"\n💰 1C. QUOTE (precio actual en tiempo real) - {symbol}")
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol
    }
    data = make_request(params)
    if data and 'Global Quote' in data:
        quote = data['Global Quote']
        print(f"   Precio: ${quote['05. price']}")
        print(f"   Cambio: {quote['09. change']} ({quote['10. change percent']})")
        print(f"   Volume: {quote['06. volume']}")
        print(f"   Última actualización: {quote['07. latest trading day']}")


# ============================================================================
# 2. FOREX (DIVISAS)
# ============================================================================

def explore_forex():
    """Explora datos de divisas"""
    print("\n" + "="*80)
    print("2. FOREX (DIVISAS)")
    print("="*80)
    
    # 2A. EXCHANGE RATE (tasa de cambio actual)
    print("\n💱 2A. EXCHANGE RATE (tasa actual)")
    params = {
        'function': 'CURRENCY_EXCHANGE_RATE',
        'from_currency': 'USD',
        'to_currency': 'CLP'
    }
    data = make_request(params)
    if data and 'Realtime Currency Exchange Rate' in data:
        rate = data['Realtime Currency Exchange Rate']
        print(f"   {rate['2. From_Currency Name']} → {rate['4. To_Currency Name']}")
        print(f"   Tasa: {rate['5. Exchange Rate']}")
        print(f"   Última actualización: {rate['6. Last Refreshed']}")
        print(f"   Zona horaria: {rate['7. Time Zone']}")
    
    # 2B. FOREX INTRADAY (histórico intradiario)
    print("\n📉 2B. FOREX INTRADAY (EUR/USD cada 5min)")
    params = {
        'function': 'FX_INTRADAY',
        'from_symbol': 'EUR',
        'to_symbol': 'USD',
        'interval': '5min',
        'outputsize': 'compact'
    }
    data = make_request(params)
    if data:
        ts_key = 'Time Series FX (5min)'
        if ts_key in data:
            latest = list(data[ts_key].items())[0]
            print(f"   Última actualización: {latest[0]}")
            print(f"   Open: {latest[1]['1. open']}")
            print(f"   Close: {latest[1]['4. close']}")
    
    # 2C. FOREX DAILY (histórico diario)
    print("\n📊 2C. FOREX DAILY (USD/CLP histórico)")
    params = {
        'function': 'FX_DAILY',
        'from_symbol': 'USD',
        'to_symbol': 'CLP',
        'outputsize': 'compact'
    }
    data = make_request(params)
    if data:
        ts_key = 'Time Series FX (Daily)'
        if ts_key in data:
            latest = list(data[ts_key].items())[0]
            print(f"   Fecha: {latest[0]}")
            print(f"   Close: {latest[1]['4. close']}")


# ============================================================================
# 3. CRYPTOCURRENCIES (CRIPTOMONEDAS)
# ============================================================================

def explore_crypto():
    """Explora datos de criptomonedas"""
    print("\n" + "="*80)
    print("3. CRYPTOCURRENCIES (CRIPTOMONEDAS)")
    print("="*80)
    
    # 3A. CRYPTO RATING
    print("\n⭐ 3A. CRYPTO RATING (calificación)")
    params = {
        'function': 'CRYPTO_RATING',
        'symbol': 'BTC'
    }
    data = make_request(params)
    if data and 'Crypto Rating (FCAS)' in data:
        rating = data['Crypto Rating (FCAS)']
        print(f"   Symbol: {rating['1. symbol']}")
        print(f"   Name: {rating['2. name']}")
        print(f"   Rating: {rating['3. fcas rating']}")
        print(f"   Score: {rating['4. fcas score']}")
    
    # 3B. CRYPTO INTRADAY
    print("\n₿ 3B. CRYPTO INTRADAY (BTC cada 5min)")
    params = {
        'function': 'CRYPTO_INTRADAY',
        'symbol': 'BTC',
        'market': 'USD',
        'interval': '5min'
    }
    data = make_request(params)
    if data:
        ts_key = 'Time Series Crypto (5min)'
        if ts_key in data:
            latest = list(data[ts_key].items())[0]
            print(f"   Última actualización: {latest[0]}")
            print(f"   Close: ${latest[1]['4. close']}")
            print(f"   Volume: {latest[1]['5. volume']}")


# ============================================================================
# 4. TECHNICAL INDICATORS (INDICADORES TÉCNICOS)
# ============================================================================

def explore_technical_indicators():
    """Explora indicadores técnicos"""
    print("\n" + "="*80)
    print("4. TECHNICAL INDICATORS (INDICADORES TÉCNICOS)")
    print("="*80)
    
    symbol = "AAPL"
    
    # 4A. SMA (Simple Moving Average)
    print(f"\n📊 4A. SMA (Media Móvil Simple) - {symbol}")
    params = {
        'function': 'SMA',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 50,
        'series_type': 'close'
    }
    data = make_request(params)
    if data and 'Technical Analysis: SMA' in data:
        latest = list(data['Technical Analysis: SMA'].items())[0]
        print(f"   Fecha: {latest[0]}")
        print(f"   SMA(50): {latest[1]['SMA']}")
    
    # 4B. RSI (Relative Strength Index)
    print(f"\n📈 4B. RSI (Índice de Fuerza Relativa) - {symbol}")
    params = {
        'function': 'RSI',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': 14,
        'series_type': 'close'
    }
    data = make_request(params)
    if data and 'Technical Analysis: RSI' in data:
        latest = list(data['Technical Analysis: RSI'].items())[0]
        rsi = float(latest[1]['RSI'])
        print(f"   Fecha: {latest[0]}")
        print(f"   RSI(14): {rsi:.2f}")
        if rsi > 70:
            print(f"   Estado: SOBRECOMPRADO 🔴")
        elif rsi < 30:
            print(f"   Estado: SOBREVENDIDO 🟢")
        else:
            print(f"   Estado: NEUTRAL 🟡")
    
    # 4C. MACD
    print(f"\n📉 4C. MACD (Convergencia/Divergencia) - {symbol}")
    params = {
        'function': 'MACD',
        'symbol': symbol,
        'interval': 'daily',
        'series_type': 'close'
    }
    data = make_request(params)
    if data and 'Technical Analysis: MACD' in data:
        latest = list(data['Technical Analysis: MACD'].items())[0]
        print(f"   Fecha: {latest[0]}")
        print(f"   MACD: {latest[1]['MACD']}")
        print(f"   Signal: {latest[1]['MACD_Signal']}")
        print(f"   Histogram: {latest[1]['MACD_Hist']}")
    
    # Otros indicadores disponibles:
    print("\n📋 OTROS INDICADORES DISPONIBLES:")
    indicators = [
        "EMA - Exponential Moving Average",
        "WMA - Weighted Moving Average",
        "BBANDS - Bollinger Bands",
        "STOCH - Stochastic Oscillator",
        "ADX - Average Directional Index",
        "CCI - Commodity Channel Index",
        "AROON - Aroon Indicator",
        "ATR - Average True Range",
        "OBV - On Balance Volume",
    ]
    for ind in indicators:
        print(f"   - {ind}")


# ============================================================================
# 5. FUNDAMENTAL DATA (DATOS FUNDAMENTALES)
# ============================================================================

def explore_fundamental_data():
    """Explora datos fundamentales de empresas"""
    print("\n" + "="*80)
    print("5. FUNDAMENTAL DATA (DATOS FUNDAMENTALES)")
    print("="*80)
    
    symbol = "AAPL"
    
    # 5A. COMPANY OVERVIEW
    print(f"\n🏢 5A. COMPANY OVERVIEW - {symbol}")
    params = {
        'function': 'OVERVIEW',
        'symbol': symbol
    }
    data = make_request(params)
    if data and 'Symbol' in data:
        print(f"   Nombre: {data.get('Name', 'N/A')}")
        print(f"   Sector: {data.get('Sector', 'N/A')}")
        print(f"   Industria: {data.get('Industry', 'N/A')}")
        print(f"   Market Cap: ${data.get('MarketCapitalization', 'N/A')}")
        print(f"   P/E Ratio: {data.get('PERatio', 'N/A')}")
        print(f"   Dividend Yield: {data.get('DividendYield', 'N/A')}")
        print(f"   52 Week High: ${data.get('52WeekHigh', 'N/A')}")
        print(f"   52 Week Low: ${data.get('52WeekLow', 'N/A')}")
    
    # 5B. EARNINGS
    print(f"\n💼 5B. EARNINGS (Ganancias trimestrales) - {symbol}")
    params = {
        'function': 'EARNINGS',
        'symbol': symbol
    }
    data = make_request(params)
    if data and 'quarterlyEarnings' in data:
        latest = data['quarterlyEarnings'][0]
        print(f"   Fecha reporte: {latest['fiscalDateEnding']}")
        print(f"   EPS reportado: ${latest['reportedEPS']}")
        print(f"   EPS estimado: ${latest.get('estimatedEPS', 'N/A')}")
        print(f"   Sorpresa: {latest.get('surprise', 'N/A')}")
    
    # 5C. INCOME STATEMENT
    print(f"\n📊 5C. INCOME STATEMENT (Estado de resultados) - {symbol}")
    params = {
        'function': 'INCOME_STATEMENT',
        'symbol': symbol
    }
    data = make_request(params)
    if data and 'annualReports' in data:
        latest = data['annualReports'][0]
        print(f"   Año fiscal: {latest['fiscalDateEnding']}")
        print(f"   Revenue: ${int(latest['totalRevenue']):,}")
        print(f"   Gross Profit: ${int(latest['grossProfit']):,}")
        print(f"   Operating Income: ${int(latest['operatingIncome']):,}")
        print(f"   Net Income: ${int(latest['netIncome']):,}")


# ============================================================================
# 6. ECONOMIC INDICATORS (INDICADORES ECONÓMICOS)
# ============================================================================

def explore_economic_indicators():
    """Explora indicadores económicos macro"""
    print("\n" + "="*80)
    print("6. ECONOMIC INDICATORS (INDICADORES ECONÓMICOS)")
    print("="*80)
    
    # 6A. REAL GDP
    print("\n🌍 6A. REAL GDP (PIB Real de USA)")
    params = {
        'function': 'REAL_GDP',
        'interval': 'quarterly'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Valor: ${latest['value']} billion")
    
    # 6B. CPI (Inflation)
    print("\n📈 6B. CPI (Índice de Precios al Consumidor - Inflación)")
    params = {
        'function': 'CPI',
        'interval': 'monthly'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        previous = data['data'][1]
        print(f"   Fecha: {latest['date']}")
        print(f"   CPI: {latest['value']}")
        change = ((float(latest['value']) - float(previous['value'])) / float(previous['value'])) * 100
        print(f"   Cambio mensual: {change:.2f}%")
    
    # 6C. UNEMPLOYMENT
    print("\n👥 6C. UNEMPLOYMENT (Tasa de Desempleo)")
    params = {
        'function': 'UNEMPLOYMENT'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Tasa: {latest['value']}%")
    
    # 6D. FEDERAL FUNDS RATE
    print("\n💰 6D. FEDERAL FUNDS RATE (Tasa de Interés FED)")
    params = {
        'function': 'FEDERAL_FUNDS_RATE',
        'interval': 'monthly'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Tasa: {latest['value']}%")
    
    print("\n📋 OTROS INDICADORES DISPONIBLES:")
    indicators = [
        "TREASURY_YIELD - Rendimiento bonos del tesoro",
        "INFLATION - Inflación",
        "RETAIL_SALES - Ventas minoristas",
        "DURABLES - Bienes duraderos",
        "CONSUMER_SENTIMENT - Sentimiento del consumidor",
        "NONFARM_PAYROLL - Nóminas no agrícolas",
    ]
    for ind in indicators:
        print(f"   - {ind}")


# ============================================================================
# 7. COMMODITIES (MATERIAS PRIMAS)
# ============================================================================

def explore_commodities():
    """Explora datos de commodities"""
    print("\n" + "="*80)
    print("7. COMMODITIES (MATERIAS PRIMAS)")
    print("="*80)
    
    # 7A. WTI (Petróleo)
    print("\n🛢️  7A. WTI (Petróleo Crudo)")
    params = {
        'function': 'WTI',
        'interval': 'daily'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Precio: ${latest['value']}/barril")
    
    # 7B. BRENT
    print("\n🛢️  7B. BRENT (Petróleo Brent)")
    params = {
        'function': 'BRENT',
        'interval': 'daily'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Precio: ${latest['value']}/barril")
    
    # 7C. NATURAL GAS
    print("\n⚡ 7C. NATURAL GAS (Gas Natural)")
    params = {
        'function': 'NATURAL_GAS',
        'interval': 'daily'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Precio: ${latest['value']}/MMBtu")
    
    # 7D. COPPER
    print("\n🟫 7D. COPPER (Cobre) - ¡IMPORTANTE PARA CHILE!")
    params = {
        'function': 'COPPER',
        'interval': 'monthly'
    }
    data = make_request(params)
    if data and 'data' in data:
        latest = data['data'][0]
        print(f"   Fecha: {latest['date']}")
        print(f"   Precio: ${latest['value']}/ton")
    
    print("\n📋 OTROS COMMODITIES DISPONIBLES:")
    commodities = [
        "WHEAT - Trigo",
        "CORN - Maíz",
        "COTTON - Algodón",
        "SUGAR - Azúcar",
        "COFFEE - Café",
        "ALUMINUM - Aluminio",
    ]
    for comm in commodities:
        print(f"   - {comm}")


# ============================================================================
# 8. SENTIMENT & NEWS (SENTIMIENTO Y NOTICIAS)
# ============================================================================

def explore_sentiment():
    """Explora análisis de sentimiento y noticias"""
    print("\n" + "="*80)
    print("8. SENTIMENT & NEWS (SENTIMIENTO Y NOTICIAS)")
    print("="*80)
    
    # 8A. NEWS SENTIMENT
    print("\n📰 8A. NEWS SENTIMENT (Sentimiento de noticias)")
    params = {
        'function': 'NEWS_SENTIMENT',
        'tickers': 'AAPL',
        'limit': 5
    }
    data = make_request(params)
    if data and 'feed' in data:
        print(f"   Total noticias: {data.get('items', 'N/A')}")
        for i, article in enumerate(data['feed'][:3], 1):
            print(f"\n   Noticia {i}:")
            print(f"   Título: {article['title'][:80]}...")
            print(f"   Fuente: {article['source']}")
            print(f"   Fecha: {article['time_published']}")
            if 'overall_sentiment_score' in article:
                score = float(article['overall_sentiment_score'])
                sentiment = "POSITIVO 🟢" if score > 0.15 else "NEGATIVO 🔴" if score < -0.15 else "NEUTRAL 🟡"
                print(f"   Sentimiento: {score:.3f} ({sentiment})")


# ============================================================================
# MAIN - EJECUTAR TODAS LAS EXPLORACIONES
# ============================================================================

def main():
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "ALPHA VANTAGE - EXPLORADOR COMPLETO" + " "*23 + "║")
    print("╚" + "="*78 + "╝")
    print(f"\nAPI Key: {API_KEY}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n⚠️  NOTA: Usando API key 'demo' que tiene datos limitados.")
    print("   Consigue tu propia key gratis en: https://www.alphavantage.co/support/#api-key")
    
    # Ejecutar todas las exploraciones
    try:
        explore_stock_data()
        print("\n⏸️  Pausa 12 segundos (rate limit)...")
        # time.sleep(12)  # Descomenta si tienes API key real
        
        explore_forex()
        # time.sleep(12)
        
        explore_crypto()
        # time.sleep(12)
        
        explore_technical_indicators()
        # time.sleep(12)
        
        explore_fundamental_data()
        # time.sleep(12)
        
        explore_economic_indicators()
        # time.sleep(12)
        
        explore_commodities()
        # time.sleep(12)
        
        explore_sentiment()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Exploración interrumpida por el usuario")
    
    print("\n" + "="*80)
    print("EXPLORACIÓN COMPLETADA")
    print("="*80)
    print("\n💡 PRÓXIMOS PASOS:")
    print("   1. Consigue tu API key gratis")
    print("   2. Reemplaza API_KEY = 'demo' con tu key")
    print("   3. Descomenta los time.sleep() para respetar rate limits")
    print("   4. Integra los endpoints que necesites en tu sistema")


if __name__ == "__main__":
    main()

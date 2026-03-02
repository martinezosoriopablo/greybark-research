"""
QUANTITATIVE DATA COLLECTOR
Recolecta datos de Alpha Vantage para reporte semanal
Ejecutar: Viernes 6:00 PM (después del reporte diario PM)
"""

import os
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURACIÓN DE RED (para evitar problemas de proxy)
# ============================================================================

# Deshabilitar proxies que puedan causar problemas
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# Configurar requests para no usar proxy
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL = "https://www.alphavantage.co/query"

if not API_KEY:
    raise RuntimeError("ALPHA_VANTAGE_API_KEY no encontrada en .env")

# Contador de calls (para no exceder 25/día)
API_CALLS_MADE = 0
MAX_CALLS = 25

# ============================================================================
# HELPERS
# ============================================================================

def make_api_call(params: dict, description: str = "") -> Optional[dict]:
    """Hace una llamada a Alpha Vantage con control de rate limit"""
    global API_CALLS_MADE
    
    if API_CALLS_MADE >= MAX_CALLS:
        print(f"[WARN] Límite de {MAX_CALLS} llamadas alcanzado")
        return None
    
    params['apikey'] = API_KEY
    
    try:
        print(f"[API Call {API_CALLS_MADE + 1}/{MAX_CALLS}] {description}")
        
        # Configurar sesión sin proxy
        session = requests.Session()
        session.trust_env = False  # No usar variables de entorno de proxy
        
        response = session.get(BASE_URL, params=params, timeout=15)
        data = response.json()
        
        # Check for errors
        if "Note" in data:
            print(f"   [WARN] Rate limit: {data['Note']}")
            return None
        
        if "Error Message" in data:
            print(f"   [ERROR] {data['Error Message']}")
            return None
        
        if "Information" in data:
            print(f"   [INFO] {data['Information']}")
            return None
        
        API_CALLS_MADE += 1
        print(f"   [OK] Datos recibidos")
        
        # Rate limit: 5 calls/min para plan gratuito
        time.sleep(12)  # Esperar 12 segundos entre llamadas
        
        return data
        
    except requests.exceptions.ProxyError as e:
        print(f"   [ERROR] Problema de proxy: {e}")
        print(f"   [INFO] Intenta desactivar proxy en Windows:")
        print(f"          Settings → Network → Proxy → Desactivar")
        return None
        
    except Exception as e:
        print(f"   [ERROR] Request failed: {e}")
        return None


def get_quote(symbol: str) -> Optional[dict]:
    """Obtiene quote actual de un símbolo"""
    params = {
        'function': 'GLOBAL_QUOTE',
        'symbol': symbol
    }
    
    data = make_api_call(params, f"Quote: {symbol}")
    
    if data and 'Global Quote' in data:
        quote = data['Global Quote']
        return {
            'symbol': symbol,
            'price': float(quote.get('05. price', 0)),
            'change': float(quote.get('09. change', 0)),
            'change_pct': float(quote.get('10. change percent', '0').replace('%', '')),
            'volume': int(quote.get('06. volume', 0)),
            'latest_trading_day': quote.get('07. latest trading day', '')
        }
    
    return None


def get_rsi(symbol: str, time_period: int = 14) -> Optional[float]:
    """Obtiene RSI de un símbolo"""
    params = {
        'function': 'RSI',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': time_period,
        'series_type': 'close'
    }
    
    data = make_api_call(params, f"RSI: {symbol}")
    
    if data and 'Technical Analysis: RSI' in data:
        latest = list(data['Technical Analysis: RSI'].items())[0]
        return float(latest[1]['RSI'])
    
    return None


def get_sma(symbol: str, time_period: int) -> Optional[float]:
    """Obtiene SMA de un símbolo"""
    params = {
        'function': 'SMA',
        'symbol': symbol,
        'interval': 'daily',
        'time_period': time_period,
        'series_type': 'close'
    }
    
    data = make_api_call(params, f"SMA{time_period}: {symbol}")
    
    if data and 'Technical Analysis: SMA' in data:
        latest = list(data['Technical Analysis: SMA'].items())[0]
        return float(latest[1]['SMA'])
    
    return None


# ============================================================================
# NIVEL 1: PANORAMA MACRO
# ============================================================================

def collect_macro_data() -> dict:
    """Recolecta datos macro principales"""
    print("\n" + "="*80)
    print("NIVEL 1: PANORAMA MACRO")
    print("="*80)
    
    macro_data = {
        'equity_indices': {},
        'volatility': {},
        'fixed_income': {},
        'commodities': {},
        'forex': {}
    }
    
    # A. EQUITY INDICES
    print("\n[1A] EQUITY INDICES")
    equity_symbols = ['SPY', 'QQQ', 'IWM', 'DIA', 'EFA', 'EEM']
    
    for symbol in equity_symbols:
        quote = get_quote(symbol)
        if quote:
            macro_data['equity_indices'][symbol] = quote
    
    # B. VOLATILITY
    print("\n[1B] VOLATILITY")
    vol_symbols = ['^VIX', 'VXX']
    
    for symbol in vol_symbols:
        quote = get_quote(symbol)
        if quote:
            macro_data['volatility'][symbol] = quote
    
    # C. FIXED INCOME
    print("\n[1C] FIXED INCOME")
    bond_symbols = ['SHY', 'IEF', 'TLT', 'LQD', 'HYG']
    
    for symbol in bond_symbols:
        quote = get_quote(symbol)
        if quote:
            macro_data['fixed_income'][symbol] = quote
    
    # D. COMMODITIES
    print("\n[1D] COMMODITIES")
    commodity_symbols = ['USO', 'GLD', 'SLV', 'CPER']
    
    for symbol in commodity_symbols:
        quote = get_quote(symbol)
        if quote:
            macro_data['commodities'][symbol] = quote
    
    # E. FOREX
    print("\n[1E] FOREX")
    forex_symbols = ['UUP', 'FXE', 'FXY']
    
    for symbol in forex_symbols:
        quote = get_quote(symbol)
        if quote:
            macro_data['forex'][symbol] = quote
    
    return macro_data


# ============================================================================
# NIVEL 2: SECTORES S&P500
# ============================================================================

def collect_sector_data() -> dict:
    """Recolecta datos de los 11 sectores del S&P500"""
    print("\n" + "="*80)
    print("NIVEL 2: SECTORES S&P500")
    print("="*80)
    
    sectors = {
        'XLK': {'name': 'Technology', 'weight': 29.0, 'type': 'growth'},
        'XLF': {'name': 'Financials', 'weight': 13.0, 'type': 'cyclical'},
        'XLV': {'name': 'Health Care', 'weight': 12.0, 'type': 'defensive'},
        'XLY': {'name': 'Consumer Discretionary', 'weight': 10.0, 'type': 'cyclical'},
        'XLC': {'name': 'Communication Services', 'weight': 9.0, 'type': 'growth'},
        'XLI': {'name': 'Industrials', 'weight': 8.0, 'type': 'cyclical'},
        'XLP': {'name': 'Consumer Staples', 'weight': 6.0, 'type': 'defensive'},
        'XLE': {'name': 'Energy', 'weight': 4.0, 'type': 'cyclical'},
        'XLU': {'name': 'Utilities', 'weight': 2.5, 'type': 'defensive'},
        'XLRE': {'name': 'Real Estate', 'weight': 2.5, 'type': 'defensive'},
        'XLB': {'name': 'Materials', 'weight': 2.0, 'type': 'cyclical'},
    }
    
    sector_data = {}
    
    for symbol, info in sectors.items():
        print(f"\n[{symbol}] {info['name']}")
        
        # Quote
        quote = get_quote(symbol)
        if not quote:
            continue
        
        # RSI
        rsi = get_rsi(symbol)
        
        sector_data[symbol] = {
            'name': info['name'],
            'weight': info['weight'],
            'type': info['type'],
            'price': quote['price'],
            'change_pct': quote['change_pct'],
            'rsi': rsi
        }
    
    return sector_data


# ============================================================================
# ANÁLISIS DERIVADO
# ============================================================================

def calculate_sector_rotation(sector_data: dict) -> dict:
    """Calcula indicadores de rotación sectorial"""
    print("\n[ANALYSIS] Calculando rotación sectorial...")
    
    cyclical_performance = []
    defensive_performance = []
    growth_performance = []
    
    for symbol, data in sector_data.items():
        perf = data['change_pct']
        sector_type = data['type']
        
        if sector_type == 'cyclical':
            cyclical_performance.append(perf)
        elif sector_type == 'defensive':
            defensive_performance.append(perf)
        elif sector_type == 'growth':
            growth_performance.append(perf)
    
    avg_cyclical = sum(cyclical_performance) / len(cyclical_performance) if cyclical_performance else 0
    avg_defensive = sum(defensive_performance) / len(defensive_performance) if defensive_performance else 0
    avg_growth = sum(growth_performance) / len(growth_performance) if growth_performance else 0
    
    # Ratio cíclicos/defensivos (>1 = Risk On, <1 = Risk Off)
    cyc_def_ratio = avg_cyclical / avg_defensive if avg_defensive != 0 else 0
    
    rotation = {
        'avg_cyclical': round(avg_cyclical, 2),
        'avg_defensive': round(avg_defensive, 2),
        'avg_growth': round(avg_growth, 2),
        'cyclical_defensive_ratio': round(cyc_def_ratio, 2),
        'market_regime': 'RISK ON' if cyc_def_ratio > 1.1 else 'RISK OFF' if cyc_def_ratio < 0.9 else 'NEUTRAL'
    }
    
    print(f"   Cíclicos: {rotation['avg_cyclical']:+.2f}%")
    print(f"   Defensivos: {rotation['avg_defensive']:+.2f}%")
    print(f"   Growth: {rotation['avg_growth']:+.2f}%")
    print(f"   Ratio C/D: {rotation['cyclical_defensive_ratio']:.2f}")
    print(f"   Régimen: {rotation['market_regime']}")
    
    return rotation


def calculate_volatility_metrics(macro_data: dict) -> dict:
    """Calcula métricas de volatilidad"""
    print("\n[ANALYSIS] Calculando métricas de volatilidad...")
    
    vix_data = macro_data['volatility'].get('^VIX', {})
    
    if not vix_data:
        return {}
    
    vix_level = vix_data.get('price', 0)
    vix_change = vix_data.get('change_pct', 0)
    
    # Interpretación del VIX
    if vix_level < 15:
        vix_regime = 'COMPLACENCIA'
        vix_signal = 'Mercado tranquilo, baja volatilidad esperada'
    elif vix_level < 20:
        vix_regime = 'NORMAL'
        vix_signal = 'Volatilidad típica del mercado'
    elif vix_level < 30:
        vix_regime = 'ELEVADA'
        vix_signal = 'Preocupación moderada en el mercado'
    else:
        vix_regime = 'PÁNICO'
        vix_signal = 'Estrés significativo en el mercado'
    
    metrics = {
        'vix_level': round(vix_level, 2),
        'vix_change_pct': round(vix_change, 2),
        'vix_regime': vix_regime,
        'vix_signal': vix_signal
    }
    
    print(f"   VIX: {metrics['vix_level']} ({metrics['vix_change_pct']:+.2f}%)")
    print(f"   Régimen: {metrics['vix_regime']}")
    print(f"   Señal: {metrics['vix_signal']}")
    
    return metrics


# ============================================================================
# MAIN - RECOLECCIÓN COMPLETA
# ============================================================================

def collect_all_data() -> dict:
    """Recolecta todos los datos para el reporte semanal"""
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "QUANTITATIVE WEEKLY REPORT - DATA COLLECTION" + " "*18 + "║")
    print("╚" + "="*78 + "╝")
    print(f"\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Key: {'*' * 20}{API_KEY[-4:]}")
    print(f"Max API Calls: {MAX_CALLS}")
    
    dataset = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'report_week_ending': datetime.now().strftime('%Y-%m-%d'),
            'api_calls_used': 0
        },
        'macro': {},
        'sectors': {},
        'analysis': {}
    }
    
    # Nivel 1: Macro
    dataset['macro'] = collect_macro_data()
    
    # Nivel 2: Sectores
    dataset['sectors'] = collect_sector_data()
    
    # Análisis derivado
    dataset['analysis']['sector_rotation'] = calculate_sector_rotation(dataset['sectors'])
    dataset['analysis']['volatility_metrics'] = calculate_volatility_metrics(dataset['macro'])
    
    # Actualizar metadata
    dataset['metadata']['api_calls_used'] = API_CALLS_MADE
    
    print("\n" + "="*80)
    print("RECOLECCIÓN COMPLETADA")
    print("="*80)
    print(f"API Calls utilizadas: {API_CALLS_MADE}/{MAX_CALLS}")
    print(f"Sectores recopilados: {len(dataset['sectors'])}")
    
    return dataset


def save_dataset(dataset: dict, output_path: str = "quantitative_weekly_data.json"):
    """Guarda el dataset en JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Dataset guardado en: {output_path}")


def main():
    """Función principal"""
    try:
        # Recolectar datos
        dataset = collect_all_data()
        
        # Guardar
        output_file = f"quantitative_weekly_data_{datetime.now().strftime('%Y%m%d')}.json"
        save_dataset(dataset, output_file)
        
        print("\n" + "="*80)
        print("PROCESO COMPLETADO EXITOSAMENTE")
        print("="*80)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

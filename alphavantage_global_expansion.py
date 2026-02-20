# -*- coding: utf-8 -*-
"""
ALPHAVANTAGE GLOBAL MARKETS MODULE
Grey Bark Advisors - Expansión de Cobertura Global

COBERTURA EXPANDIDA:
1. Índices Asia: Nikkei, Hang Seng, Shanghai
2. Índices Europa: FTSE, DAX, CAC (complementa Euro Stoxx)
3. Índices LatAm: Bovespa, IPC México
4. Treasury Yields: 3m, 2y, 10y, 30y + Spreads
5. Forex expandido: DXY (arreglado), GBP, AUD, CNY
6. Sentiment por sector: Tech, Financials, Energy, Healthcare, Consumer
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import time

# API Configuration
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"
REQUEST_DELAY = 1.0  # 1 segundo entre requests


def get_api_key() -> Optional[str]:
    """Obtiene API key desde variables de entorno"""
    return os.getenv("ALPHAVANTAGE_API_KEY")


# ==============================================================================
# 1. TREASURY YIELDS - CURVA COMPLETA
# ==============================================================================

def fetch_treasury_yields() -> Dict[str, Any]:
    """
    Obtiene Treasury yields de US desde Alpha Vantage (TREASURY_YIELD) y calcula
    puntos clave para cada maturity:

      - latest: último dato disponible
      - previous: dato inmediatamente anterior (último día hábil previo con dato)
      - month_start: último dato del mes anterior (base para MTD)
      - month_ago: dato en o antes de (latest - ~30 días) (referencia rápida)
      - last_bd_prev_year: último dato del año calendario anterior (último día hábil con dato)
      - year_ago: dato en o antes de (latest - 1 año)

    Nota:
      - Alpha Vantage TREASURY_YIELD soporta maturities como: 3month, 2year, 5year,
        7year, 10year, 30year. Aquí usamos: 2y, 5y, 10y, 30y (sin 20y).

    Returns:
        Dict con yields por maturity y spreads calculados.
    """
    print("[INFO] Fetching US Treasury yields from Alpha Vantage (TREASURY_YIELD).")

    api_key = get_api_key()
    if not api_key:
        print("[WARN] ALPHAVANTAGE_API_KEY no encontrado. Treasuries deshabilitados.")
        return {"yields": {}, "spreads": {}}

    maturities = ["2year", "5year", "10year", "30year"]
    yields: Dict[str, Any] = {}

    def _fetch_series(maturity: str) -> Optional[List[Dict[str, Any]]]:
        """Devuelve lista de observaciones ordenada por fecha ascendente: [{date, value}, ...]"""
        try:
            params = {
                "function": "TREASURY_YIELD",
                "interval": "daily",
                "maturity": maturity,
                "apikey": api_key,
            }
            r = requests.get(ALPHAVANTAGE_BASE_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            # Errores típicos de Alpha Vantage
            if "Error Message" in data:
                raise RuntimeError(data["Error Message"])
            if "Note" in data:
                raise RuntimeError(data["Note"])
            if "Information" in data:
                raise RuntimeError(data["Information"])

            rows = data.get("data", [])
            if not rows:
                return None

            obs: List[Dict[str, Any]] = []
            for row in rows:
                d = row.get("date")
                v = row.get("value")
                if not d or v in (None, ""):
                    continue
                try:
                    obs.append({"date": d, "value": float(v)})
                except Exception:
                    continue

            # Alpha Vantage suele venir desc por fecha; normalizamos asc
            obs.sort(key=lambda x: x["date"])
            return obs or None

        except Exception as e:
            print(f"  ✗ {maturity}: error fetching series: {e}")
            return None
        finally:
            time.sleep(REQUEST_DELAY)

    def _pick_on_or_before(obs: List[Dict[str, Any]], target_date_str: str) -> Optional[Dict[str, Any]]:
        # obs está ascendente por date 'YYYY-MM-DD' => comparación lexicográfica funciona
        candidates = [o for o in obs if o["date"] <= target_date_str]
        return candidates[-1] if candidates else None

    def _pick_last_before(obs: List[Dict[str, Any]], cutoff_date_str: str) -> Optional[Dict[str, Any]]:
        # último dato estrictamente < cutoff_date_str
        candidates = [o for o in obs if o["date"] < cutoff_date_str]
        return candidates[-1] if candidates else None

    for mty in maturities:
        obs = _fetch_series(mty)
        if not obs or len(obs) < 1:
            print(f"  ✗ {mty}: No data")
            yields[mty] = None
            continue

        latest = obs[-1]
        previous = obs[-2] if len(obs) >= 2 else None

        latest_dt = datetime.strptime(latest["date"], "%Y-%m-%d").date()

        # Base MTD = último dato del mes anterior (último obs < primer día del mes)
        first_day_of_month = latest_dt.replace(day=1)
        month_start = _pick_last_before(obs, first_day_of_month.strftime("%Y-%m-%d"))

        # Referencia "hace 1 mes" (dato en o antes, ~30 días atrás)
        month_ago_dt = latest_dt - timedelta(days=30)
        month_ago = _pick_on_or_before(obs, month_ago_dt.strftime("%Y-%m-%d"))

        # 1 año atrás (dato en o antes)
        year_ago_dt = latest_dt.replace(year=latest_dt.year - 1)
        year_ago = _pick_on_or_before(obs, year_ago_dt.strftime("%Y-%m-%d"))

        # último día hábil del año anterior: último dato cuyo año == latest_year-1
        prev_year = latest_dt.year - 1
        prev_year_obs = [o for o in obs if int(o["date"][:4]) == prev_year]
        last_bd_prev_year = prev_year_obs[-1] if prev_year_obs else None

        # Construir salida (manteniendo compatibilidad: value/date = latest)
        yields[mty] = {
            "maturity": mty,
            "source": "AlphaVantage",
            "value": round(float(latest["value"]), 3),
            "date": latest["date"],
            "latest": {"date": latest["date"], "value": round(float(latest["value"]), 3)},
            "previous": {"date": previous["date"], "value": round(float(previous["value"]), 3)} if previous else None,
            "month_start": {"date": month_start["date"], "value": round(float(month_start["value"]), 3)} if month_start else None,
            "month_ago": {"date": month_ago["date"], "value": round(float(month_ago["value"]), 3)} if month_ago else None,
            "last_bd_prev_year": {
                "date": last_bd_prev_year["date"],
                "value": round(float(last_bd_prev_year["value"]), 3),
            } if last_bd_prev_year else None,
            "year_ago": {"date": year_ago["date"], "value": round(float(year_ago["value"]), 3)} if year_ago else None,
        }

        print(f"  ✓ {mty}: {yields[mty]['value']:.3f}% ({yields[mty]['date']})")

    # Calcular spreads importantes usando 'value' (latest)
    spreads: Dict[str, Any] = {}

    if yields.get("10year") and yields.get("2year"):
        spread_10y_2y = yields["10year"]["value"] - yields["2year"]["value"]
        spreads["10y_2y"] = {
            "value": round(spread_10y_2y, 3),
            "inverted": spread_10y_2y < 0,
            "note": "Inversión de curva predice recesión" if spread_10y_2y < 0 else "Curva normal",
        }
        print(f"  ✓ Spread 10Y-2Y: {spread_10y_2y:.3f}% {'⚠️ INVERTIDA' if spread_10y_2y < 0 else '✓'}")

    return {"yields": yields, "spreads": spreads}


def fetch_dxy_from_alphavantage() -> Optional[Dict[str, Any]]:
    """
    Obtiene DXY desde AlphaVantage (alternativa a Yahoo que falla)
    
    DXY no está directamente en AlphaVantage, pero podemos calcularlo
    aproximado desde los principales pares forex
    
    DXY Formula (aproximada):
    50.14348112 × EUR/USD^-0.576 × USD/JPY^0.136 × GBP/USD^-0.119 
    × USD/CAD^0.091 × USD/SEK^0.042 × USD/CHF^0.036
    
    Returns:
        Dict con DXY estimado o None
    """
    api_key = get_api_key()
    if not api_key:
        return None
    
    print("[INFO] Fetching DXY components...")
    
    # Obtener pares principales
    pairs = {
        "EURUSD": ("EUR", "USD"),
        "USDJPY": ("USD", "JPY"),
        "GBPUSD": ("GBP", "USD"),
        "USDCAD": ("USD", "CAD"),
    }
    
    rates = {}
    
    for pair, (from_curr, to_curr) in pairs.items():
        try:
            url = f"{ALPHAVANTAGE_BASE_URL}"
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_curr,
                "to_currency": to_curr,
                "apikey": api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if "Realtime Currency Exchange Rate" in data:
                rate_data = data["Realtime Currency Exchange Rate"]
                rates[pair] = float(rate_data["5. Exchange Rate"])
                print(f"  ✓ {pair}: {rates[pair]:.4f}")
            
            time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"  ✗ Error fetching {pair}: {e}")
            return None
    
    # Cálculo simplificado de DXY (aproximado)
    if len(rates) >= 4:
        try:
            dxy_approx = (
                50.14348112 
                * (rates["EURUSD"] ** -0.576)
                * (rates["USDJPY"] ** 0.136)
                * (rates["GBPUSD"] ** -0.119)
                * (rates["USDCAD"] ** 0.091)
            )
            
            print(f"  ✓ DXY (estimated): {dxy_approx:.2f}")
            
            return {
                "value": round(dxy_approx, 2),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "AlphaVantage (calculated)",
                "note": "DXY calculado desde EUR/USD, USD/JPY, GBP/USD, USD/CAD"
            }
        except Exception as e:
            print(f"  ✗ Error calculating DXY: {e}")
            return None
    
    return None


# ==============================================================================
# 3. SENTIMENT POR SECTOR
# ==============================================================================

def fetch_sector_sentiment(hours_back: int = 24) -> Dict[str, Any]:
    """
    Obtiene sentiment cuantificado por sector usando AlphaVantage News
    
    VERSIÓN CORREGIDA: Usa TOPICS en vez de múltiples tickers
    
    Args:
        hours_back: Horas hacia atrás (parámetro ignorado, topics no filtran por tiempo)
    
    Returns:
        Dict con sentiment por sector
    """
    api_key = get_api_key()
    if not api_key:
        print("  ✗ No API key found")
        return {}
    
    print(f"[INFO] Fetching sector sentiment...")
    
    # Sectores usando TOPICS (más confiable que múltiples tickers)
    sectors = {
        "technology": {
            "name": "Tecnología",
            "topic": "technology"
        },
        "financials": {
            "name": "Financiero",
            "topic": "finance"
        },
        "energy": {
            "name": "Energía",
            "topic": "energy_transportation"
        },
        "healthcare": {
            "name": "Salud",
            "topic": "life_sciences"
        },
        "consumer": {
            "name": "Consumo",
            "topic": "retail_wholesale"
        }
    }
    
    results = {}
    
    for sector_key, sector_info in sectors.items():
        try:
            print(f"  Fetching {sector_info['name']} (topic: {sector_info['topic']})...")
            
            url = f"{ALPHAVANTAGE_BASE_URL}"
            params = {
                "function": "NEWS_SENTIMENT",
                "topics": sector_info["topic"],
                "limit": 50,
                "apikey": api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            # Check for rate limit
            if "Note" in data:
                print(f"  ✗ {sector_info['name']}: Rate limited")
                results[sector_key] = {
                    "name": sector_info["name"],
                    "score": 0,
                    "label": "Rate Limited",
                    "news_count": 0
                }
                time.sleep(5)
                continue
            
            # Si hay feed
            if "feed" in data and data["feed"]:
                # Calcular sentiment promedio
                sentiments = []
                for article in data["feed"]:
                    score = article.get("overall_sentiment_score", 0)
                    if score != 0:
                        sentiments.append(float(score))
                
                if sentiments:
                    avg_sentiment = sum(sentiments) / len(sentiments)
                    
                    # Clasificar sentiment
                    if avg_sentiment >= 0.35:
                        label = "Bullish"
                    elif avg_sentiment >= 0.15:
                        label = "Somewhat Bullish"
                    elif avg_sentiment >= -0.15:
                        label = "Neutral"
                    elif avg_sentiment >= -0.35:
                        label = "Somewhat Bearish"
                    else:
                        label = "Bearish"
                    
                    results[sector_key] = {
                        "name": sector_info["name"],
                        "score": round(avg_sentiment, 3),
                        "label": label,
                        "news_count": len(data["feed"])
                    }
                    
                    print(f"  ✓ {sector_info['name']}: {label} ({avg_sentiment:.3f}) - {len(data['feed'])} news")
                else:
                    print(f"  ✗ {sector_info['name']}: Feed sin sentiment scores")
                    results[sector_key] = {
                        "name": sector_info["name"],
                        "score": 0,
                        "label": "No Data",
                        "news_count": 0
                    }
            else:
                print(f"  ✗ {sector_info['name']}: No feed data")
                results[sector_key] = {
                    "name": sector_info["name"],
                    "score": 0,
                    "label": "No Data",
                    "news_count": 0
                }
            
            time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"  ✗ Error fetching {sector_key}: {e}")
            results[sector_key] = {
                "name": sector_info["name"],
                "score": 0,
                "label": "Error",
                "news_count": 0
            }
    
    return results



# ==============================================================================
# 4. FOREX EXPANDIDO
# ==============================================================================

def fetch_forex_expanded() -> Dict[str, Any]:
    """
    Obtiene pares forex adicionales importantes
    
    Returns:
        Dict con pares forex expandidos
    """
    api_key = get_api_key()
    if not api_key:
        return {}
    
    print("[INFO] Fetching expanded forex pairs...")
    
    pairs = {
        "GBPUSD": ("GBP", "USD", "Libra Esterlina"),
        "AUDUSD": ("AUD", "USD", "Dólar Australiano"),
        "USDCAD": ("USD", "CAD", "Dólar Canadiense"),
        "USDCNY": ("USD", "CNY", "Yuan Chino"),
        "USDCHF": ("USD", "CHF", "Franco Suizo"),
    }
    
    results = {}
    
    for pair_key, (from_curr, to_curr, name) in pairs.items():
        try:
            url = f"{ALPHAVANTAGE_BASE_URL}"
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_curr,
                "to_currency": to_curr,
                "apikey": api_key
            }
            
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            if "Realtime Currency Exchange Rate" in data:
                rate_data = data["Realtime Currency Exchange Rate"]
                results[pair_key] = {
                    "pair": f"{from_curr}/{to_curr}",
                    "name": name,
                    "rate": float(rate_data["5. Exchange Rate"]),
                    "bid": float(rate_data.get("8. Bid Price", 0)),
                    "ask": float(rate_data.get("9. Ask Price", 0)),
                    "last_refreshed": rate_data["6. Last Refreshed"]
                }
                print(f"  ✓ {from_curr}/{to_curr}: {results[pair_key]['rate']:.4f}")
            else:
                print(f"  ✗ {from_curr}/{to_curr}: No data")
                results[pair_key] = None
            
            time.sleep(REQUEST_DELAY)
            
        except Exception as e:
            print(f"  ✗ Error fetching {pair_key}: {e}")
            results[pair_key] = None
    
    return results


# ==============================================================================
# WRAPPER - EXPANSION COMPLETA
# ==============================================================================

def fetch_global_expansion_data() -> Dict[str, Any]:
    """
    Wrapper para obtener toda la expansión global en una llamada
    
    Returns:
        Dict con todos los datos expandidos
    """
    print("="*80)
    print("GLOBAL MARKETS EXPANSION - ALPHAVANTAGE")
    print("="*80)
    
    result = {}
    
    # 1. Treasury Yields + Spreads
    print("\n1. US TREASURY YIELDS:")
    print("-"*80)
    result["treasury_yields"] = fetch_treasury_yields()
    
    # 2. DXY Arreglado
    print("\n2. DXY (US DOLLAR INDEX):")
    print("-"*80)
    result["dxy"] = fetch_dxy_from_alphavantage()
    
    # 3. Sentiment por Sector
    print("\n3. SECTOR SENTIMENT:")
    print("-"*80)
    result["sector_sentiment"] = fetch_sector_sentiment(hours_back=24)
    
    # 4. Forex Expandido
    print("\n4. FOREX EXPANDED:")
    print("-"*80)
    result["forex_expanded"] = fetch_forex_expanded()
    
    print("\n" + "="*80)
    print("GLOBAL EXPANSION DATA - COMPLETE")
    print("="*80)
    
    return result


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*80)
    print("GLOBAL MARKETS EXPANSION - TEST")
    print("="*80)
    
    api_key = get_api_key()
    if not api_key:
        print("\n[ERROR] ALPHAVANTAGE_API_KEY not found in .env")
        exit(1)
    
    print(f"\n✓ API Key: {api_key[:10]}...\n")
    
    # Fetch all expansion data
    data = fetch_global_expansion_data()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    if data.get("treasury_yields"):
        yields = data["treasury_yields"]["yields"]
        print(f"\n✓ Treasury Yields: {sum(1 for v in yields.values() if v)} of 5")
        if data["treasury_yields"]["spreads"].get("10y_2y"):
            spread = data["treasury_yields"]["spreads"]["10y_2y"]
            print(f"  Spread 10Y-2Y: {spread['value']}% {'⚠️ INVERTED' if spread['inverted'] else '✓'}")
    
    if data.get("dxy"):
        print(f"\n✓ DXY: {data['dxy']['value']}")
    
    if data.get("sector_sentiment"):
        sectors = data["sector_sentiment"]
        print(f"\n✓ Sector Sentiment: {len(sectors)} sectors")
        for sector, info in sectors.items():
            if info:
                print(f"  {info['name']}: {info['label']} ({info['score']:.3f})")
    
    if data.get("forex_expanded"):
        fx = data["forex_expanded"]
        print(f"\n✓ Forex Expanded: {sum(1 for v in fx.values() if v)} pairs")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

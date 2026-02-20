# -*- coding: utf-8 -*-
"""
IPSA FIX SIMPLIFICADO
Yahoo: close + change_1d (tal cual)
BCCh: niveles históricos para calcular MTD y YTD
"""

import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional
import yfinance as yf

# Importar días hábiles
from chile_business_days import (
    get_month_start_business_day,
    get_year_end_business_day
)

# BCCh Config
BCCH_BDE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
BCCH_SERIES_IPSA = "F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D"  # IPSA - Serie correcta


def fetch_bcch_ipsa_level(date: datetime, api_user: str, api_pass: str) -> Optional[float]:
    """
    Obtiene nivel del IPSA desde BCCh para una fecha específica
    
    Args:
        date: Fecha a consultar
        api_user: Usuario BCCh
        api_pass: Password BCCh
    
    Returns:
        Nivel del IPSA o None
    """
    try:
        date_str = date.strftime("%Y-%m-%d")
        
        params = {
            "user": api_user,
            "pass": api_pass,
            "firstdate": date_str,
            "lastdate": date_str,
            "timeseries": BCCH_SERIES_IPSA,
            "function": "GetSeries"
        }
        
        response = requests.get(BCCH_BDE_URL, params=params, timeout=30)
        
        print(f"    BCCh response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"    ✗ BCCh returned status {response.status_code}")
            return None
        
        # Parsear como JSON (no XML!)
        try:
            data = response.json()
        except Exception as e:
            print(f"    ✗ JSON parse error: {e}")
            return None
        
        # Verificar respuesta exitosa
        if data.get("Codigo") != 0:
            print(f"    ✗ BCCh error: {data.get('Descripcion', 'Unknown error')}")
            return None
        
        # Extraer valor de la serie
        series = data.get("Series", {})
        obs_list = series.get("Obs", [])
        
        if not obs_list:
            print(f"    ✗ No observations found for {date_str}")
            return None
        
        # Tomar primera observación
        obs = obs_list[0]
        value_str = obs.get("value")
        
        if not value_str:
            print(f"    ✗ No value in observation")
            return None
        
        # Convertir a float
        value = float(value_str.replace(',', '.'))
        
        # Validar rango (IPSA típicamente entre 3000-20000)
        if not (3000 < value < 20000):
            print(f"    ⚠️ Value {value} outside expected range")
        
        print(f"    ✓ Found value: {value} (date: {obs.get('indexDateString')})")
        return value
        
    except Exception as e:
        print(f"    ✗ Error fetching BCCh IPSA for {date_str}: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_ipsa_simple() -> Dict[str, Any]:
    """
    Calcula IPSA de forma simple:
    - Yahoo: close + change_1d (mantener)
    - BCCh: solo para calcular MTD y YTD
    
    Returns:
        Dict con IPSA completo
    """
    print("[INFO] Calculating IPSA...")
    
    # 1. Obtener datos actuales de Yahoo (close + change_1d)
    try:
        ticker = yf.Ticker("^IPSA")
        
        # Obtener info del ticker (tiene regularMarketChange, regularMarketChangePercent)
        info = ticker.info
        
        # Obtener histórico para el close actual
        hist = ticker.history(period="2d")
        
        if hist.empty:
            print("  ✗ No Yahoo data")
            return {"error": "No Yahoo data"}
        
        # Close actual
        close_today = float(hist['Close'].iloc[-1])
        date_today = hist.index[-1]
        
        # Change 1D: Viene directo en ticker.info
        change_1d_yahoo = None
        
        # Intentar obtener de info
        if 'regularMarketChangePercent' in info and info['regularMarketChangePercent']:
            change_1d_yahoo = float(info['regularMarketChangePercent'])
            print(f"  ✓ Yahoo - Close: {close_today:.2f}, Change 1D: {change_1d_yahoo:.2f}% (from info)")
        # Si no está en info, calcular de historical como backup
        elif len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            curr_close = float(hist['Close'].iloc[-1])
            change_1d_yahoo = ((curr_close - prev_close) / prev_close) * 100
            print(f"  ✓ Yahoo - Close: {close_today:.2f}, Change 1D: {change_1d_yahoo:.2f}% (calculated)")
        else:
            print(f"  ✓ Yahoo - Close: {close_today:.2f}, Change 1D: N/A")
        
    except Exception as e:
        print(f"  ✗ Yahoo error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    
    # 2. Obtener credenciales BCCh
    # Intentar diferentes nombres de variables
    bcch_user = os.getenv("BCCH_API_USER") or os.getenv("BCCH_USER")
    bcch_pass = os.getenv("BCCH_API_PASS") or os.getenv("BCCH_PASS") or os.getenv("BCCH_PASSWORD")
    
    print(f"  → BCCh user: {'✓' if bcch_user else '✗'}")
    print(f"  → BCCh pass: {'✓' if bcch_pass else '✗'}")
    
    if not bcch_user or not bcch_pass:
        print("  ⚠️ No BCCh credentials - MTD/YTD will be null")
        print("     Verificar .env tiene: BCCH_API_USER y BCCH_API_PASS")
        return {
            "close": round(close_today, 2),
            "date": date_today.strftime("%Y-%m-%d"),
            "change_1d": round(change_1d_yahoo, 2) if change_1d_yahoo else None,
            "change_mtd": None,
            "change_ytd": None,
            "source_close": "Yahoo Finance",
            "source_1d": "Yahoo Finance",
            "note": "MTD/YTD no disponibles sin credenciales BCCh"
        }
    
    # 3. Calcular fechas base con días hábiles
    today_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Primer día hábil del mes actual
    first_business_day_month = get_month_start_business_day(today_dt.year, today_dt.month)
    
    # Último día hábil del año anterior (para YTD)
    last_business_day_prev_year = get_year_end_business_day(today_dt.year - 1)
    
    print(f"  → MTD base (primer día hábil mes): {first_business_day_month.strftime('%Y-%m-%d')}")
    print(f"  → YTD base (último día hábil {today_dt.year-1}): {last_business_day_prev_year.strftime('%Y-%m-%d')}")
    
    # 4. Fetch niveles desde BCCh
    level_mtd_base = fetch_bcch_ipsa_level(first_business_day_month, bcch_user, bcch_pass)
    level_ytd_base = fetch_bcch_ipsa_level(last_business_day_prev_year, bcch_user, bcch_pass)
    
    if level_mtd_base:
        print(f"  ✓ BCCh - MTD base level: {level_mtd_base:.2f}")
    else:
        print(f"  ⚠️ BCCh - No MTD base level")
    
    if level_ytd_base:
        print(f"  ✓ BCCh - YTD base level: {level_ytd_base:.2f}")
    else:
        print(f"  ⚠️ BCCh - No YTD base level")
    
    # 5. Calcular cambios MTD y YTD
    change_mtd = None
    change_ytd = None
    
    if level_mtd_base:
        change_mtd = ((close_today - level_mtd_base) / level_mtd_base) * 100
        print(f"  ✓ Change MTD: {change_mtd:.2f}%")
    
    if level_ytd_base:
        change_ytd = ((close_today - level_ytd_base) / level_ytd_base) * 100
        print(f"  ✓ Change YTD: {change_ytd:.2f}%")
    
    # 6. Construir resultado
    result = {
        "close": round(close_today, 2),
        "date": date_today.strftime("%Y-%m-%d"),
        "change_1d": round(change_1d_yahoo, 2) if change_1d_yahoo else None,
        "change_mtd": round(change_mtd, 2) if change_mtd else None,
        "change_ytd": round(change_ytd, 2) if change_ytd else None,
        "mtd_base_date": first_business_day_month.strftime("%Y-%m-%d"),
        "ytd_base_date": last_business_day_prev_year.strftime("%Y-%m-%d"),
        "source_close": "Yahoo Finance",
        "source_1d": "Yahoo Finance",
        "source_historical": "Banco Central de Chile",
        "note": "Close/1D de Yahoo Finance + MTD/YTD calculados con niveles BCCh (días hábiles bancarios)"
    }
    
    return result


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*80)
    print("TEST - IPSA FIX SIMPLIFICADO")
    print("="*80)
    print("\nESTRATEGIA:")
    print("  Yahoo: close + change_1d (tal cual)")
    print("  BCCh: niveles históricos para MTD/YTD")
    print("  Días hábiles: 31-dic = feriado bancario")
    print("="*80)
    
    result = calculate_ipsa_simple()
    
    print("\n" + "="*80)
    print("RESULTADO")
    print("="*80)
    
    if "error" not in result:
        print(f"\n✓ Close:      {result['close']:>10.2f}  (Yahoo)")
        
        if result['change_1d'] is not None:
            print(f"✓ Change 1D:  {result['change_1d']:>9.2f}%  (Yahoo)")
        else:
            print(f"✗ Change 1D:  {'N/A':>10}  (Yahoo - insuficientes datos)")
        
        if result['change_mtd'] is not None:
            print(f"✓ Change MTD: {result['change_mtd']:>9.2f}%  (BCCh calculado)")
        else:
            print(f"✗ Change MTD: {'None':>10}  (BCCh no disponible)")
        
        if result['change_ytd'] is not None:
            print(f"✓ Change YTD: {result['change_ytd']:>9.2f}%  (BCCh calculado)")
        else:
            print(f"✗ Change YTD: {'None':>10}  (BCCh no disponible)")
        
        print(f"\nFechas base:")
        print(f"  MTD: {result.get('mtd_base_date', 'N/A')} (primer día hábil del mes)")
        print(f"  YTD: {result.get('ytd_base_date', 'N/A')} (último día hábil año anterior)")
        
        print(f"\n{result['note']}")
        
        # Validación
        print("\n" + "="*80)
        print("VALIDACIÓN")
        print("="*80)
        
        all_good = True
        
        if result['change_1d'] is not None:
            print("✓ Change 1D: OK")
        else:
            print("✗ Change 1D: NULL")
            all_good = False
        
        if result['change_mtd'] is not None:
            print("✓ Change MTD: OK")
        else:
            print("⚠️ Change MTD: NULL (verificar BCCh)")
            all_good = False
        
        if result['change_ytd'] is not None:
            print("✓ Change YTD: OK")
        else:
            print("⚠️ Change YTD: NULL (verificar BCCh)")
            all_good = False
        
        # Verificar fecha YTD base
        if result['ytd_base_date'] == "2025-12-30":
            print("✓ YTD base date: CORRECTO (30-dic-2025, no 31)")
        elif result['ytd_base_date'] == "2025-12-31":
            print("✗ YTD base date: ERROR (es 31-dic, debe ser 30-dic)")
            all_good = False
        else:
            print(f"? YTD base date: {result['ytd_base_date']}")
        
        if all_good:
            print("\n🎉 TODO CORRECTO!")
        else:
            print("\n⚠️ Revisar campos NULL")
        
    else:
        print(f"\n✗ Error: {result.get('error')}")
    
    print("\n" + "="*80)

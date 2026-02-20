# -*- coding: utf-8 -*-
"""
IPSA INTEGRATION - Para daily_market_snapshot.py
Combina Yahoo Finance + BCCh con días hábiles bancarios correctos
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import yfinance as yf

# ==============================================================================
# DÍAS HÁBILES BANCARIOS CHILE
# ==============================================================================

# Feriados fijos
FERIADOS_FIJOS = {
    (1, 1): "Año Nuevo",
    (5, 1): "Día del Trabajo",
    (5, 21): "Día de las Glorias Navales",
    (6, 20): "Día Nacional de los Pueblos Indígenas",
    (7, 16): "Día de la Virgen del Carmen",
    (8, 15): "Asunción de la Virgen",
    (9, 18): "Día de la Independencia Nacional",
    (9, 19): "Día de las Glorias del Ejército",
    (10, 12): "Encuentro de Dos Mundos",
    (10, 31): "Día de las Iglesias Evangélicas y Protestantes",
    (11, 1): "Día de Todos los Santos",
    (12, 8): "Inmaculada Concepción",
    (12, 25): "Navidad",
}

# Feriados bancarios (no son feriados nacionales pero bancos cierran)
FERIADOS_BANCARIOS = {
    (12, 31): "Feriado Bancario - Fin de Año",
}


def is_dia_habil_bancario(date: datetime) -> bool:
    """Verifica si es día hábil bancario en Chile"""
    # Fin de semana
    if date.weekday() in [5, 6]:
        return False
    
    # Feriado fijo
    key = (date.month, date.day)
    if key in FERIADOS_FIJOS or key in FERIADOS_BANCARIOS:
        return False
    
    return True


def get_month_start_business_day(year: int, month: int) -> datetime:
    """Obtiene el primer día hábil del mes"""
    date = datetime(year, month, 1)
    
    while not is_dia_habil_bancario(date):
        date = date + timedelta(days=1)
    
    return date


def get_year_end_business_day(year: int) -> datetime:
    """Obtiene el último día hábil del año (31-dic es feriado bancario!)"""
    date = datetime(year, 12, 31)
    
    while not is_dia_habil_bancario(date):
        date = date - timedelta(days=1)
    
    return date


def get_prev_month_end_business_day(today: datetime) -> datetime:
    """Obtiene el último día hábil bancario del mes anterior (base correcta para MTD).

    Ejemplo: si estamos en enero, esto devuelve el cierre hábil de diciembre (normalmente coincide con base YTD).
    """
    first_day_this_month = datetime(today.year, today.month, 1)
    date = first_day_this_month - timedelta(days=1)
    while not is_dia_habil_bancario(date):
        date = date - timedelta(days=1)
    return date


# ==============================================================================
# IPSA - BANCO CENTRAL CHILE
# ==============================================================================

BCCH_BDE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
BCCH_SERIES_IPSA = "F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D"  # IPSA


def fetch_bcch_ipsa_level(date: datetime, api_user: str, api_pass: str) -> Optional[float]:
    """
    Obtiene nivel del IPSA desde BCCh para una fecha específica
    
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
        
        if response.status_code != 200:
            return None
        
        # BCCh devuelve JSON (no XML)
        data = response.json()
        
        # Verificar respuesta exitosa
        if data.get("Codigo") != 0:
            return None
        
        # Extraer valor
        series = data.get("Series", {})
        obs_list = series.get("Obs", [])
        
        if not obs_list:
            return None
        
        obs = obs_list[0]
        value_str = obs.get("value")
        
        if not value_str:
            return None
        
        value = float(value_str.replace(',', '.'))
        
        return value
        
    except Exception as e:
        print(f"[WARN] Error fetching BCCh IPSA for {date_str}: {e}")
        return None


# ==============================================================================
# FUNCIÓN PRINCIPAL PARA DAILY_MARKET_SNAPSHOT
# ==============================================================================

def calculate_ipsa_complete() -> Dict[str, Any]:
    """
    Calcula IPSA completo para daily_market_snapshot.py
    
    ESTRATEGIA:
    - Yahoo Finance: close + change_1d (tiempo real)
    - BCCh: niveles históricos para calcular MTD y YTD
    - Días hábiles bancarios: para fechas base correctas
    
    Returns:
        Dict con close, date, change_1d, change_mtd, change_ytd
    """
    print("[INFO] Calculating IPSA (Yahoo + BCCh + días hábiles)...")
    
    # 1. Yahoo Finance (close + change_1d)
    try:
        ticker = yf.Ticker("^IPSA")
        info = ticker.info
        hist = ticker.history(period="2d")
        
        if hist.empty:
            print("[ERROR] IPSA: No Yahoo data")
            return {"error": "No Yahoo data"}
        
        close_today = float(hist['Close'].iloc[-1])
        date_today = hist.index[-1]
        
        # Change 1D de Yahoo
        change_1d_yahoo = None
        if 'regularMarketChangePercent' in info and info['regularMarketChangePercent']:
            change_1d_yahoo = float(info['regularMarketChangePercent'])
        elif len(hist) >= 2:
            prev_close = float(hist['Close'].iloc[-2])
            change_1d_yahoo = ((close_today - prev_close) / prev_close) * 100
        
        print(f"[IPSA] Yahoo - Close: {close_today:.2f}, Change 1D: {change_1d_yahoo:.2f}%")
        
    except Exception as e:
        print(f"[ERROR] IPSA Yahoo: {e}")
        return {"error": str(e)}
    
    # 2. BCCh credentials
    bcch_user = os.getenv("BCCH_API_USER") or os.getenv("BCCH_USER")
    bcch_pass = os.getenv("BCCH_API_PASS") or os.getenv("BCCH_PASS")
    
    if not bcch_user or not bcch_pass:
        print("[WARN] IPSA: No BCCh credentials - MTD/YTD will be null")
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
    today_dt = date_today.replace(hour=0, minute=0, second=0, microsecond=0)

    
    mtd_base_date = get_prev_month_end_business_day(today_dt)
    last_business_day_prev_year = get_year_end_business_day(today_dt.year - 1)

    print(f"[IPSA] MTD base (prev month close): {mtd_base_date.strftime('%Y-%m-%d')}")
    print(f"[IPSA] YTD base (prev year close): {last_business_day_prev_year.strftime('%Y-%m-%d')}")

    # 4. Fetch niveles desde BCCh
    level_mtd_base = fetch_bcch_ipsa_level(mtd_base_date, bcch_user, bcch_pass)
    level_ytd_base = fetch_bcch_ipsa_level(last_business_day_prev_year, bcch_user, bcch_pass)
    
    # 5. Calcular cambios
    change_mtd = None
    change_ytd = None
    
    if level_mtd_base:
        change_mtd = ((close_today - level_mtd_base) / level_mtd_base) * 100
        print(f"[IPSA] MTD: {change_mtd:.2f}% (base: {level_mtd_base:.2f})")
    else:
        print("[WARN] IPSA: No BCCh MTD base level")
    
    if level_ytd_base:
        change_ytd = ((close_today - level_ytd_base) / level_ytd_base) * 100
        print(f"[IPSA] YTD: {change_ytd:.2f}% (base: {level_ytd_base:.2f})")
    else:
        print("[WARN] IPSA: No BCCh YTD base level")
    
    # 6. Resultado
    result = {
        "close": round(close_today, 2),
        "date": date_today.strftime("%Y-%m-%d"),
        "change_1d": round(change_1d_yahoo, 2) if change_1d_yahoo else None,
        "change_mtd": round(change_mtd, 2) if change_mtd else None,
        "change_ytd": round(change_ytd, 2) if change_ytd else None,
        "mtd_base_date": mtd_base_date.strftime("%Y-%m-%d"),
        "ytd_base_date": last_business_day_prev_year.strftime("%Y-%m-%d"),
        "source_close": "Yahoo Finance",
        "source_1d": "Yahoo Finance",
        "source_historical": "Banco Central de Chile",
        "note": "Close/1D de Yahoo Finance + MTD/YTD calculados con niveles BCCh (días hábiles bancarios)"
    }
    
    print(f"[OK] IPSA: Close={result['close']}, 1D={result['change_1d']}%, MTD={result['change_mtd']}%, YTD={result['change_ytd']}%")
    
    return result

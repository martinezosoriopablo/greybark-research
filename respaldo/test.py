# -*- coding: utf-8 -*-
"""
TEST IPSA HÍBRIDO - VERSIÓN CORREGIDA
Combina Yahoo Finance (close/1D) + Banco Central (MTD/YTD)

CORRECCIONES:
1. BCCh usa formato dd-mm-yyyy (no yyyy-mm-dd)
2. Para YTD, buscar último día hábil del año anterior (no 1 de enero)
"""

import os
import requests
import yfinance as yf
from datetime import date, datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("TEST IPSA - ESTRATEGIA HÍBRIDA (CORREGIDO)")
print("="*80)
print()

# ============================================================================
# PASO 1: Obtener CLOSE y 1D desde YAHOO FINANCE
# ============================================================================

print("PASO 1: OBTENER DATOS ACTUALES DESDE YAHOO FINANCE")
print("-"*80)

ticker = yf.Ticker("^IPSA")

try:
    hist = ticker.history(period="5d")
    
    if hist.empty or len(hist) < 1:
        print("❌ ERROR: Yahoo Finance no devolvió datos")
        exit(1)
    
    print(f"✓ Yahoo Finance devolvió {len(hist)} días de datos")
    print()
    print("Últimos 5 días:")
    print(hist[['Close']].tail())
    print()
    
    yahoo_close = float(hist['Close'].iloc[-1])
    yahoo_date = hist.index[-1].strftime('%Y-%m-%d')
    
    if len(hist) >= 2:
        prev_close = float(hist['Close'].iloc[-2])
        yahoo_change_1d = ((yahoo_close / prev_close) - 1.0) * 100.0
    else:
        yahoo_change_1d = None
    
    print(f"✓ YAHOO FINANCE:")
    print(f"  Close:     {yahoo_close:,.2f}")
    print(f"  Fecha:     {yahoo_date}")
    print(f"  Change 1D: {yahoo_change_1d:+.2f}%" if yahoo_change_1d else "  Change 1D: N/A")
    print()

except Exception as e:
    print(f"❌ ERROR en Yahoo Finance: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# ============================================================================
# PASO 2: Obtener NIVELES HISTÓRICOS desde BANCO CENTRAL
# ============================================================================

print("PASO 2: OBTENER NIVELES HISTÓRICOS DESDE BANCO CENTRAL DE CHILE")
print("-"*80)

BCCH_BDE_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
IPSA_SERIES = "F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D"

bcch_user = os.getenv("BCCH_USER")
bcch_pass = os.getenv("BCCH_PASS")

if not bcch_user or not bcch_pass:
    print("❌ ERROR: Credenciales BCCh no configuradas en .env")
    exit(1)

print(f"✓ Credenciales BCCh: {bcch_user[:3]}***")
print()

end_date = date.today()
start_date = end_date - timedelta(days=400)

params = {
    "user": bcch_user,
    "pass": bcch_pass,
    "firstdate": start_date.strftime("%Y-%m-%d"),
    "lastdate": end_date.strftime("%Y-%m-%d"),
    "timeseries": IPSA_SERIES,
    "function": "GetSeries",
}

print(f"Consultando BCCh desde {start_date} hasta {end_date}...")

try:
    response = requests.get(BCCH_BDE_URL, params=params, timeout=30)
    
    if response.status_code != 200:
        print(f"❌ ERROR: Status code {response.status_code}")
        exit(1)
    
    data = response.json()
    series_obj = data.get("Series", {}).get("Obs")
    
    if not series_obj:
        print("❌ ERROR: No hay observaciones")
        exit(1)
    
    # ========================================================================
    # CORRECCIÓN 1: BCCh usa formato dd-mm-yyyy
    # ========================================================================
    observations = []
    for obs in series_obj:
        val_str = obs.get("value", "").strip()
        
        # Saltar valores vacíos o nan
        if not val_str or val_str.lower() == 'nan':
            continue
        
        try:
            val = float(val_str)
            obs_date_str = obs.get("indexDateString")
            
            # BCCh usa dd-mm-yyyy, convertir a objeto date
            try:
                obs_date = datetime.strptime(obs_date_str, "%d-%m-%Y").date()
            except:
                # Fallback por si acaso usa otro formato
                obs_date = datetime.strptime(obs_date_str, "%Y-%m-%d").date()
            
            observations.append({
                "value": val,
                "date": obs_date.strftime("%Y-%m-%d"),  # Guardar en formato ISO
                "date_obj": obs_date  # Para comparaciones
            })
        except Exception as e:
            continue
    
    print(f"✓ BCCh devolvió {len(observations)} observaciones válidas")
    print()
    print("Últimas 10 observaciones:")
    for obs in observations[-10:]:
        print(f"  {obs['date']}: {obs['value']:,.2f}")
    print()

except Exception as e:
    print(f"❌ ERROR consultando BCCh: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# ============================================================================
# PASO 3: CALCULAR MTD y YTD
# ============================================================================

print("PASO 3: CALCULAR MTD Y YTD")
print("-"*80)

today = date.today()

# ============================================================================
# MTD: Primer día hábil del mes actual
# ============================================================================
first_day_month = today.replace(day=1)
print(f"Buscando nivel MTD desde: {first_day_month.isoformat()} (inicio mes)")

month_start_value = None
month_start_date = None

for obs in observations:
    if obs["date_obj"] >= first_day_month:
        month_start_value = obs["value"]
        month_start_date = obs["date"]
        break

if month_start_value:
    print(f"✓ Nivel inicio mes ({month_start_date}): {month_start_value:,.2f}")
    mtd = ((yahoo_close / month_start_value) - 1.0) * 100.0
    print(f"✓ MTD = ({yahoo_close:,.2f} / {month_start_value:,.2f} - 1) × 100")
    print(f"✓ MTD = {mtd:+.2f}%")
else:
    print("❌ No se encontró nivel de inicio de mes")
    mtd = None

print()

# ============================================================================
# CORRECCIÓN 2: YTD = Último día hábil del año ANTERIOR
# ============================================================================
# En vez de buscar 01-01-2025 (feriado), buscar último día hábil de 2024
last_day_prev_year = date(today.year - 1, 12, 31)
print(f"Buscando nivel YTD desde: {last_day_prev_year.isoformat()} (último día {today.year-1}) hacia atrás")

year_start_value = None
year_start_date = None

# Buscar hacia atrás desde 31-dic del año anterior
for obs in reversed(observations):
    if obs["date_obj"] <= last_day_prev_year:
        year_start_value = obs["value"]
        year_start_date = obs["date"]
        print(f"✓ Encontrado último día hábil de {today.year-1}: {year_start_date}")
        break

if year_start_value:
    print(f"✓ Nivel cierre {today.year-1} ({year_start_date}): {year_start_value:,.2f}")
    ytd = ((yahoo_close / year_start_value) - 1.0) * 100.0
    print(f"✓ YTD = ({yahoo_close:,.2f} / {year_start_value:,.2f} - 1) × 100")
    print(f"✓ YTD = {ytd:+.2f}%")
else:
    print("❌ No se encontró nivel de cierre año anterior")
    ytd = None

print()

# ============================================================================
# PASO 4: CONSOLIDAR RESULTADO
# ============================================================================

print("="*80)
print("RESULTADO FINAL - IPSA HÍBRIDO")
print("="*80)

result = {
    "close": round(yahoo_close, 2),
    "date": yahoo_date,
    "change_1d": round(yahoo_change_1d, 2) if yahoo_change_1d else None,
    "change_mtd": round(mtd, 2) if mtd is not None else None,
    "change_ytd": round(ytd, 2) if ytd is not None else None,
    "source_close": "Yahoo Finance",
    "source_historical": "Banco Central de Chile",
    "note": f"YTD calculado desde cierre {today.year-1} ({year_start_date if year_start_date else 'N/A'})"
}

print()
print("JSON resultado:")
print("-"*80)
import json
print(json.dumps(result, indent=2, ensure_ascii=False))
print()

print("="*80)
print("✅ TEST COMPLETADO EXITOSAMENTE")
print("="*80)
print()
print(f"IPSA:")
print(f"  Close:      {result['close']:,.2f}  (Yahoo Finance)")
print(f"  Fecha:      {result['date']}")
print(f"  Change 1D:  {result['change_1d']:+.2f}%  (Yahoo)" if result['change_1d'] else "  Change 1D:  N/A")
print(f"  Change MTD: {result['change_mtd']:+.2f}%  (BCCh desde {month_start_date if month_start_date else 'N/A'})" if result['change_mtd'] else "  Change MTD: N/A")
print(f"  Change YTD: {result['change_ytd']:+.2f}%  (BCCh desde {year_start_date if year_start_date else 'N/A'})" if result['change_ytd'] else "  Change YTD: N/A")
print()

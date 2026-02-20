# -*- coding: utf-8 -*-
"""
TIMEZONE UTILITIES - CHILE
Manejo correcto de zonas horarias para newsletters y datos
"""

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Optional
import pytz

# Timezone Chile
CHILE_TZ = pytz.timezone('America/Santiago')

def get_chile_now() -> datetime:
    """
    Obtiene fecha/hora actual en Chile
    
    Returns:
        datetime con timezone Chile (GMT-3 o GMT-4 según DST)
    """
    return datetime.now(CHILE_TZ)


def parse_email_date_to_chile(email_date_str: str) -> Optional[datetime]:
    """
    Parsea fecha de email y convierte a timezone Chile
    
    Args:
        email_date_str: String de fecha de email
                       Ej: "Fri, 09 Jan 2026 08:40:45 +1100"
    
    Returns:
        datetime en timezone Chile, o None si falla
    """
    try:
        # Parsear fecha del email (viene con timezone)
        dt = parsedate_to_datetime(email_date_str)
        
        # Convertir a timezone Chile
        dt_chile = dt.astimezone(CHILE_TZ)
        
        return dt_chile
    except Exception as e:
        print(f"  ✗ Error parsing email date '{email_date_str}': {e}")
        return None


def format_chile_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """
    Formatea datetime en timezone Chile
    
    Args:
        dt: datetime a formatear
        format_str: String de formato
    
    Returns:
        String formateado
    """
    if dt.tzinfo is None:
        # Si no tiene timezone, asumimos UTC y convertimos a Chile
        dt = dt.replace(tzinfo=timezone.utc).astimezone(CHILE_TZ)
    else:
        # Convertir a Chile
        dt = dt.astimezone(CHILE_TZ)
    
    return dt.strftime(format_str)


def get_chile_date_str(dt: Optional[datetime] = None) -> str:
    """
    Obtiene fecha en formato DD-MM-YYYY (Chile)
    
    Args:
        dt: datetime opcional, si None usa now()
    
    Returns:
        String "DD-MM-YYYY"
    """
    if dt is None:
        dt = get_chile_now()
    else:
        dt = dt.astimezone(CHILE_TZ)
    
    return dt.strftime("%d-%m-%Y")


def get_chile_time_str(dt: Optional[datetime] = None) -> str:
    """
    Obtiene hora en formato HH:MM (Chile)
    
    Args:
        dt: datetime opcional, si None usa now()
    
    Returns:
        String "HH:MM"
    """
    if dt is None:
        dt = get_chile_now()
    else:
        dt = dt.astimezone(CHILE_TZ)
    
    return dt.strftime("%H:%M")


def get_chile_datetime_str(dt: Optional[datetime] = None) -> str:
    """
    Obtiene fecha y hora en formato completo (Chile)
    
    Args:
        dt: datetime opcional, si None usa now()
    
    Returns:
        String "DD-MM-YYYY HH:MM"
    """
    if dt is None:
        dt = get_chile_now()
    else:
        dt = dt.astimezone(CHILE_TZ)
    
    return dt.strftime("%d-%m-%Y %H:%M")


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("="*80)
    print("TEST - TIMEZONE CHILE")
    print("="*80)
    
    # 1. Hora actual Chile
    print("\n1. HORA ACTUAL:")
    print("-"*80)
    now_chile = get_chile_now()
    print(f"Fecha/Hora Chile: {format_chile_datetime(now_chile)}")
    print(f"Fecha (DD-MM-YYYY): {get_chile_date_str()}")
    print(f"Hora (HH:MM): {get_chile_time_str()}")
    print(f"Completo: {get_chile_datetime_str()}")
    
    # 2. Parsear fechas de emails
    print("\n2. PARSEO DE FECHAS DE EMAIL:")
    print("-"*80)
    
    test_email_dates = [
        "Fri, 09 Jan 2026 08:40:45 +1100",  # Australia (GMT+11)
        "Thu, 08 Jan 2026 22:07:31 +1100",  # Australia
        "Fri, 09 Jan 2026 10:00:04 +0000",  # UTC
        "Fri, 9 Jan 2026 07:31:51 -0400",   # Chile/Venezuela (GMT-4)
    ]
    
    for email_date in test_email_dates:
        dt_chile = parse_email_date_to_chile(email_date)
        if dt_chile:
            print(f"\nEmail date: {email_date}")
            print(f"  → Chile: {format_chile_datetime(dt_chile)}")
            print(f"  → Fecha: {get_chile_date_str(dt_chile)}")
            print(f"  → Hora: {get_chile_time_str(dt_chile)}")
    
    # 3. Comparación de zonas horarias
    print("\n3. COMPARACIÓN ZONAS HORARIAS:")
    print("-"*80)
    
    # Crear datetime UTC
    dt_utc = datetime(2026, 1, 9, 12, 0, 0, tzinfo=timezone.utc)
    print(f"UTC:       {dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Convertir a Chile
    dt_chile = dt_utc.astimezone(CHILE_TZ)
    print(f"Chile:     {dt_chile.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Diferencia
    offset = dt_chile.utcoffset()
    print(f"Offset:    {offset} ({offset.total_seconds()/3600:.0f} horas)")
    
    print("\n" + "="*80)
    print("NOTA: Chile usa GMT-3 en verano (DST) y GMT-4 en invierno")
    print("="*80)

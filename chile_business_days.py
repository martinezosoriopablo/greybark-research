# -*- coding: utf-8 -*-
"""
DÍAS HÁBILES BANCARIOS - CHILE
Considera feriados oficiales + feriados bancarios
"""

from datetime import datetime, timedelta
from typing import List, Optional

# Feriados fijos Chile
FERIADOS_FIJOS = {
    (1, 1): "Año Nuevo",
    (5, 1): "Día del Trabajo",
    (5, 21): "Día de las Glorias Navales",
    (6, 20): "Día Nacional de los Pueblos Indígenas",  # Desde 2021
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

# Feriados bancarios adicionales (no son feriados nacionales pero bancos cierran)
FERIADOS_BANCARIOS = {
    (12, 31): "Feriado Bancario - Fin de Año",
}

# Feriados móviles (calcular cada año)
def get_feriados_moviles(year: int) -> dict:
    """
    Calcula feriados móviles para un año específico
    
    Feriados móviles en Chile:
    - Viernes Santo (viernes antes de Pascua)
    - Sábado Santo (sábado antes de Pascua)
    - Censo (cuando aplique)
    - Elecciones (cuando aplique)
    """
    feriados = {}
    
    # Calcular Semana Santa (Pascua)
    # Pascua = primer domingo después de la primera luna llena después del equinoccio de primavera
    # Aproximación: usar tabla conocida
    pascua_dates = {
        2024: datetime(2024, 3, 31),
        2025: datetime(2025, 4, 20),
        2026: datetime(2026, 4, 5),
        2027: datetime(2027, 3, 28),
        2028: datetime(2028, 4, 16),
    }
    
    if year in pascua_dates:
        pascua = pascua_dates[year]
        viernes_santo = pascua - timedelta(days=2)
        sabado_santo = pascua - timedelta(days=1)
        
        feriados[(viernes_santo.month, viernes_santo.day)] = "Viernes Santo"
        feriados[(sabado_santo.month, sabado_santo.day)] = "Sábado Santo"
    
    return feriados


def is_feriado_chile(date: datetime) -> tuple[bool, Optional[str]]:
    """
    Verifica si una fecha es feriado en Chile
    
    Returns:
        (is_feriado, nombre_feriado)
    """
    # Sábado o Domingo
    if date.weekday() in [5, 6]:
        return (True, "Fin de semana")
    
    # Feriado fijo
    key = (date.month, date.day)
    if key in FERIADOS_FIJOS:
        return (True, FERIADOS_FIJOS[key])
    
    # Feriado bancario
    if key in FERIADOS_BANCARIOS:
        return (True, FERIADOS_BANCARIOS[key])
    
    # Feriado móvil
    feriados_moviles = get_feriados_moviles(date.year)
    if key in feriados_moviles:
        return (True, feriados_moviles[key])
    
    return (False, None)


def is_dia_habil_bancario(date: datetime) -> bool:
    """
    Verifica si es día hábil bancario en Chile
    
    Args:
        date: Fecha a verificar
    
    Returns:
        True si es día hábil bancario, False si no
    """
    is_feriado, _ = is_feriado_chile(date)
    return not is_feriado


def get_previous_business_day(date: datetime, days_back: int = 1) -> datetime:
    """
    Obtiene el día hábil bancario anterior
    
    Args:
        date: Fecha de referencia
        days_back: Cantidad de días hábiles hacia atrás
    
    Returns:
        Fecha del día hábil anterior
    """
    current = date
    count = 0
    
    while count < days_back:
        current = current - timedelta(days=1)
        if is_dia_habil_bancario(current):
            count += 1
    
    return current


def get_next_business_day(date: datetime, days_forward: int = 1) -> datetime:
    """
    Obtiene el siguiente día hábil bancario
    
    Args:
        date: Fecha de referencia
        days_forward: Cantidad de días hábiles hacia adelante
    
    Returns:
        Fecha del siguiente día hábil
    """
    current = date
    count = 0
    
    while count < days_forward:
        current = current + timedelta(days=1)
        if is_dia_habil_bancario(current):
            count += 1
    
    return current


def get_month_start_business_day(year: int, month: int) -> datetime:
    """
    Obtiene el primer día hábil del mes
    
    Args:
        year: Año
        month: Mes
    
    Returns:
        Primer día hábil del mes
    """
    date = datetime(year, month, 1)
    
    if is_dia_habil_bancario(date):
        return date
    else:
        return get_next_business_day(date)


def get_year_start_business_day(year: int) -> datetime:
    """
    Obtiene el primer día hábil del año
    
    IMPORTANTE: En Chile, 1-ene siempre es feriado
    Típicamente el primer día hábil es 2 o 3 de enero
    
    Args:
        year: Año
    
    Returns:
        Primer día hábil del año
    """
    return get_month_start_business_day(year, 1)


def get_year_end_business_day(year: int) -> datetime:
    """
    Obtiene el último día hábil del año
    
    IMPORTANTE: En Chile, 31-dic es FERIADO BANCARIO
    Típicamente el último día hábil es 30-dic o antes
    
    Args:
        year: Año
    
    Returns:
        Último día hábil del año
    """
    date = datetime(year, 12, 31)
    
    # Retroceder hasta encontrar día hábil
    while not is_dia_habil_bancario(date):
        date = date - timedelta(days=1)
    
    return date


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("="*80)
    print("TEST - DÍAS HÁBILES BANCARIOS CHILE")
    print("="*80)
    
    # Test casos específicos
    test_cases = [
        datetime(2026, 1, 1),   # Año Nuevo
        datetime(2025, 12, 31), # Feriado Bancario
        datetime(2026, 1, 2),   # Primer día hábil 2026
        datetime(2025, 12, 30), # Último día hábil 2025
        datetime(2026, 1, 9),   # Viernes normal
        datetime(2026, 1, 10),  # Sábado
        datetime(2026, 1, 11),  # Domingo
        datetime(2026, 4, 5),   # Pascua 2026 (domingo)
        datetime(2026, 4, 3),   # Viernes Santo 2026
    ]
    
    print("\n1. VERIFICACIÓN DE FERIADOS:")
    print("-"*80)
    for date in test_cases:
        is_feriado, nombre = is_feriado_chile(date)
        is_habil = is_dia_habil_bancario(date)
        
        status = "❌ FERIADO" if is_feriado else "✅ HÁBIL"
        print(f"{date.strftime('%Y-%m-%d %A'):30} {status:15} {nombre or ''}")
    
    # Test primer/último día hábil
    print("\n2. DÍAS HÁBILES IMPORTANTES:")
    print("-"*80)
    
    # 2025
    first_2025 = get_year_start_business_day(2025)
    last_2025 = get_year_end_business_day(2025)
    print(f"Primer día hábil 2025: {first_2025.strftime('%Y-%m-%d %A')}")
    print(f"Último día hábil 2025: {last_2025.strftime('%Y-%m-%d %A')}")
    
    # 2026
    first_2026 = get_year_start_business_day(2026)
    last_2026 = get_year_end_business_day(2026)
    print(f"\nPrimer día hábil 2026: {first_2026.strftime('%Y-%m-%d %A')}")
    print(f"Último día hábil 2026: {last_2026.strftime('%Y-%m-%d %A')}")
    
    # Test navegación
    print("\n3. NAVEGACIÓN DE DÍAS HÁBILES:")
    print("-"*80)
    
    today = datetime(2026, 1, 9)
    print(f"Hoy: {today.strftime('%Y-%m-%d %A')}")
    
    prev = get_previous_business_day(today)
    print(f"Día hábil anterior: {prev.strftime('%Y-%m-%d %A')}")
    
    next_day = get_next_business_day(today)
    print(f"Siguiente día hábil: {next_day.strftime('%Y-%m-%d %A')}")
    
    # Test casos críticos
    print("\n4. CASOS CRÍTICOS:")
    print("-"*80)
    
    # 31-dic-2025 (feriado bancario)
    dec31 = datetime(2025, 12, 31)
    is_habil_dec31 = is_dia_habil_bancario(dec31)
    print(f"31-dic-2025 es hábil: {is_habil_dec31} ({'✅' if not is_habil_dec31 else '❌ ERROR'})")
    
    # Día hábil anterior a 1-ene-2026
    prev_to_nye = get_previous_business_day(datetime(2026, 1, 1))
    print(f"Día hábil antes de 1-ene-2026: {prev_to_nye.strftime('%Y-%m-%d')} (debe ser 30-dic-2025)")
    
    print("\n" + "="*80)

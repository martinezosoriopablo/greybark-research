# -*- coding: utf-8 -*-
"""
GREYBARK INTELLIGENCE PIPELINE - Orquestador Principal
Ejecuta el pipeline completo: collectors → processor → analyzer → integrator.

Uso:
    python greybark-intelligence/main.py             # Pipeline completo (24h)
    python greybark-intelligence/main.py --hours 48  # Ampliar ventana
    python greybark-intelligence/main.py --mode AM   # Inyectar en reporte AM
    python greybark-intelligence/main.py --no-inject  # Solo generar briefing standalone
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import json
import argparse
import asyncio
from datetime import datetime, date

# Agregar paths para imports
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "collectors"))
sys.path.insert(0, os.path.join(BASE_DIR, "processors"))
sys.path.insert(0, os.path.join(BASE_DIR, "analyzer"))
sys.path.insert(0, os.path.join(BASE_DIR, "integrator"))

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

from substack_collector import SubstackCollector
from telegram_collector import TelegramCollector
from rss_collector import RssCollector
from content_processor import process_items
from claude_analyzer import analyze_items
from report_integrator import generate_briefing, save_standalone_briefing, inject_into_report, find_latest_report


def run_collectors(hours_back: int = 24) -> list:
    """Ejecuta todos los collectors y combina resultados."""
    all_items = []

    # Substack
    print("\n" + "=" * 60)
    print("PASO 1/4: RECOLECCIÓN")
    print("=" * 60)

    try:
        substack = SubstackCollector(hours_back=hours_back)
        items = substack.collect()
        all_items.extend(items)
    except Exception as e:
        print(f"[ERROR] Substack collector falló: {e}")

    # Telegram
    try:
        telegram = TelegramCollector(hours_back=hours_back)
        items = telegram.collect()
        all_items.extend(items)
    except Exception as e:
        print(f"[ERROR] Telegram collector falló: {e}")

    # RSS Medios
    try:
        rss = RssCollector(hours_back=hours_back)
        items = rss.collect()
        all_items.extend(items)
    except Exception as e:
        print(f"[ERROR] RSS collector falló: {e}")

    print(f"\n[INFO] Total recolectado: {len(all_items)} items")
    return all_items


def run_pipeline(hours_back: int = 24, mode: str = "AM", inject: bool = True):
    """Ejecuta el pipeline completo."""
    start_time = datetime.now()
    today = date.today().strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"GREYBARK INTELLIGENCE PIPELINE - {today}")
    print(f"Ventana: {hours_back}h | Modo: {mode} | Inyectar: {'Sí' if inject else 'No'}")
    print("=" * 60)

    # --- Paso 1: Recolección ---
    raw_items = run_collectors(hours_back)
    if not raw_items:
        print("[ERROR] No se recolectaron items. Abortando.")
        return

    # Guardar datos crudos
    data_dir = os.path.join(BASE_DIR, "data", today)
    os.makedirs(data_dir, exist_ok=True)
    raw_path = os.path.join(data_dir, "raw_items.json")
    with open(raw_path, 'w', encoding='utf-8') as f:
        json.dump(raw_items, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Datos crudos guardados: {raw_path}")

    # --- Paso 2: Procesamiento ---
    print("\n" + "=" * 60)
    print("PASO 2/4: PROCESAMIENTO")
    print("=" * 60)

    processed_items = process_items(raw_items, hours_back)
    if not processed_items:
        print("[ERROR] No quedaron items después del procesamiento. Abortando.")
        return

    processed_path = os.path.join(data_dir, "processed_items.json")
    with open(processed_path, 'w', encoding='utf-8') as f:
        json.dump(processed_items, f, ensure_ascii=False, indent=2)

    # --- Paso 3: Análisis con Claude ---
    print("\n" + "=" * 60)
    print("PASO 3/4: ANÁLISIS CON CLAUDE")
    print("=" * 60)

    analyzed_items = analyze_items(processed_items)
    analyzed_path = os.path.join(data_dir, "analyzed_items.json")
    with open(analyzed_path, 'w', encoding='utf-8') as f:
        json.dump(analyzed_items, f, ensure_ascii=False, indent=2)

    # --- Paso 4: Generación del Briefing ---
    print("\n" + "=" * 60)
    print("PASO 4/4: GENERACIÓN DEL BRIEFING")
    print("=" * 60)

    briefing_md = generate_briefing(analyzed_items)

    # Guardar briefing standalone
    briefing_path = save_standalone_briefing(briefing_md, data_dir)

    # Inyectar en reporte diario si corresponde
    if inject:
        report_path = find_latest_report(mode, os.path.join(BASE_DIR, ".."))
        if report_path:
            inject_into_report(report_path, briefing_md)
        else:
            print(f"[WARN] No se encontró reporte {mode} para inyectar. Briefing guardado standalone.")

    # --- Resumen Final ---
    elapsed = (datetime.now() - start_time).total_seconds()
    high = sum(1 for i in analyzed_items if i.get('relevance') == 'alta')
    medium = sum(1 for i in analyzed_items if i.get('relevance') == 'media')

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETADO")
    print("=" * 60)
    print(f"  Items recolectados: {len(raw_items)}")
    print(f"  Items procesados:   {len(processed_items)}")
    print(f"  Items analizados:   {len(analyzed_items)}")
    print(f"  Alta relevancia:    {high}")
    print(f"  Media relevancia:   {medium}")
    print(f"  Tiempo total:       {elapsed:.1f}s")
    print(f"  Briefing:           {briefing_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Greybark Intelligence Pipeline")
    parser.add_argument("--hours", type=int, default=24,
                        help="Ventana de recolección en horas (default: 24)")
    parser.add_argument("--mode", type=str, default="AM", choices=["AM", "PM"],
                        help="Modo del reporte para inyección (default: AM)")
    parser.add_argument("--no-inject", action="store_true",
                        help="No inyectar en reporte, solo generar briefing standalone")

    args = parser.parse_args()
    run_pipeline(hours_back=args.hours, mode=args.mode, inject=not args.no_inject)


if __name__ == "__main__":
    main()

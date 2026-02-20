# -*- coding: utf-8 -*-
"""
Test script para probar la función review_report()
Usa un reporte existente y su snapshot correspondiente
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import json
from generate_daily_report import (
    review_report,
    build_detailed_tables,
    load_dataset,
    _extract_validation_data
)

# Archivos de prueba
SNAPSHOT_PATH = "history/daily_market_snapshot_2026-01-30_AM.json"
REPORT_PATH = "daily_report_AM_finanzas_2026-01-30.md"


def extract_report_text(full_report: str) -> str:
    """Extrae solo el texto del reporte (sin las tablas detalladas del final)"""
    # Las tablas empiezan con "```" seguido de "="*80 y "ÍNDICES PRINCIPALES"
    marker = "```\n" + "=" * 80 + "\nÍNDICES PRINCIPALES"

    if marker in full_report:
        return full_report.split(marker)[0].strip()

    # Fallback: buscar el primer bloque de código con tablas
    lines = full_report.split('\n')
    in_table_section = False
    cut_index = len(lines)

    for i, line in enumerate(lines):
        if '=' * 80 in line and i > 0 and lines[i-1].strip() == '```':
            cut_index = i - 1
            break

    return '\n'.join(lines[:cut_index]).strip()


def main():
    print("=" * 60)
    print("TEST: Función review_report()")
    print("=" * 60)

    # 1. Cargar dataset
    print(f"\n[1] Cargando snapshot: {SNAPSHOT_PATH}")
    try:
        dataset = load_dataset(SNAPSHOT_PATH)
        print("    ✓ Dataset cargado")
    except FileNotFoundError:
        print(f"    ✗ No se encontró {SNAPSHOT_PATH}")
        return

    # 2. Cargar reporte existente
    print(f"\n[2] Cargando reporte: {REPORT_PATH}")
    try:
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            full_report = f.read()
        print(f"    ✓ Reporte cargado ({len(full_report)} chars)")
    except FileNotFoundError:
        print(f"    ✗ No se encontró {REPORT_PATH}")
        return

    # 3. Extraer solo el texto (sin tablas finales)
    report_text = extract_report_text(full_report)
    print(f"    → Texto extraído: {len(report_text)} chars")

    # 4. Construir tablas detalladas
    print("\n[3] Construyendo tablas detalladas...")
    detailed_tables = build_detailed_tables(dataset)
    print(f"    ✓ Tablas construidas ({len(detailed_tables)} chars)")

    # 5. Mostrar datos de validación (para debug)
    print("\n[4] Datos de validación extraídos:")
    print("-" * 40)
    validation_data = _extract_validation_data(dataset)
    # Mostrar solo las primeras líneas
    for line in validation_data.split('\n')[:15]:
        print(f"    {line}")
    print("    ...")
    print("-" * 40)

    # 6. Ejecutar QA Review
    print("\n[5] Ejecutando QA Review...")
    print("=" * 60)

    reviewed_report = review_report(report_text, dataset, detailed_tables)

    print("=" * 60)

    # 7. Comparar resultados
    if reviewed_report == report_text:
        print("\n[RESULTADO] El reporte no fue modificado (sin errores detectados)")
    else:
        print("\n[RESULTADO] El reporte fue MODIFICADO por QA")
        print(f"    Original: {len(report_text)} chars")
        print(f"    Revisado: {len(reviewed_report)} chars")

        # Guardar versión revisada para comparación
        output_path = REPORT_PATH.replace(".md", "_QA_REVIEWED.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(reviewed_report + "\n\n" + detailed_tables)
        print(f"\n    → Guardado en: {output_path}")
        print("    → Compara ambos archivos para ver las diferencias")


if __name__ == "__main__":
    main()

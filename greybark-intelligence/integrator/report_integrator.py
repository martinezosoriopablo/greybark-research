# -*- coding: utf-8 -*-
"""
REPORT INTEGRATOR - Genera la sección "Intelligence Briefing" e inyecta
en el reporte diario existente.
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
import glob
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from collections import defaultdict


# Mapeo de categorías a secciones del briefing
SECTION_MAP = {
    "macro": "Macro Global",
    "geopolitica": "Macro Global",
    "fed_bancos_centrales": "Macro Global",
    "equity": "Mercados y Activos",
    "riesgo": "Mercados y Activos",
    "commodities": "Commodities y Energía",
    "latam": "LatAm / Chile",
    "chile": "LatAm / Chile",
}

# Orden de secciones en el briefing
SECTION_ORDER = [
    "Macro Global",
    "Mercados y Activos",
    "LatAm / Chile",
    "Commodities y Energía",
]

# Emojis de señal (usados internamente, el briefing es profesional)
SIGNAL_ICONS = {
    "bullish": "▲",
    "bearish": "▼",
    "neutral": "─",
    "N/A": "─",
}


def generate_briefing(analyzed_items: List[Dict[str, Any]],
                      report_date: Optional[str] = None) -> str:
    """
    Genera el Intelligence Briefing en formato markdown.

    Args:
        analyzed_items: Items analizados por claude_analyzer
        report_date: Fecha del reporte (default: hoy)

    Returns:
        String markdown con el briefing completo
    """
    if not analyzed_items:
        return ""

    if report_date is None:
        report_date = date.today().strftime("%d %b %Y")

    # Separar por relevancia
    high = [i for i in analyzed_items if i.get('relevance') == 'alta']
    medium = [i for i in analyzed_items if i.get('relevance') == 'media']

    # Agrupar por sección
    sections = defaultdict(list)
    for item in high + medium:
        section_name = SECTION_MAP.get(item.get('category', 'macro'), 'Macro Global')
        sections[section_name].append(item)

    # Construir markdown
    lines = []
    lines.append(f"## GREYBARK INTELLIGENCE BRIEFING - {report_date}")
    lines.append("")

    # --- Señales Clave del Día ---
    lines.append("### Señales Clave del Día")
    lines.append("")

    if high:
        for item in high[:8]:  # Top 8 señales clave
            signal = SIGNAL_ICONS.get(item.get('investment_signal', 'neutral'), '─')
            summary = item.get('summary_es', '')
            source = item.get('source_name', '')
            category = item.get('category', '')
            assets = ", ".join(item.get('asset_classes_affected', []))

            lines.append(f"- **{signal} [{category.upper()}]** {summary} *({source})*")
            if assets:
                lines.append(f"  - Activos: {assets}")
        lines.append("")
    else:
        lines.append("*Sin señales de alta relevancia hoy.*")
        lines.append("")

    # --- Secciones temáticas ---
    for section_name in SECTION_ORDER:
        items = sections.get(section_name, [])
        if not items:
            continue

        lines.append(f"### {section_name}")
        lines.append("")

        # Items de alta relevancia primero, luego media
        for item in items:
            signal = SIGNAL_ICONS.get(item.get('investment_signal', 'neutral'), '─')
            summary = item.get('summary_es', '')
            source = item.get('source_name', '')
            relevance = item.get('relevance', '')

            if relevance == 'alta':
                lines.append(f"- **{signal}** {summary} *({source})*")
            else:
                lines.append(f"- {signal} {summary} *({source})*")

        lines.append("")

    # --- Fuentes Consultadas ---
    sources = set()
    for item in analyzed_items:
        sources.add(item.get('source_name', 'Unknown'))

    lines.append("### Fuentes Consultadas Hoy")
    lines.append("")
    # Agrupar por tipo
    substack_sources = sorted(s for s in sources if not s.startswith("@") and s not in
                              ["Reuters Business", "Bloomberg Markets", "WSJ Markets", "FT Home", "FRED Releases"])
    telegram_sources = sorted(s for s in sources if s.startswith("@"))
    rss_sources = sorted(s for s in sources if s in
                         ["Reuters Business", "Bloomberg Markets", "WSJ Markets", "FT Home", "FRED Releases"])

    if substack_sources:
        lines.append(f"**Substack:** {', '.join(substack_sources)}")
    if telegram_sources:
        lines.append(f"**Telegram:** {', '.join(telegram_sources)}")
    if rss_sources:
        lines.append(f"**Medios:** {', '.join(rss_sources)}")

    lines.append("")
    lines.append(f"*Intelligence Briefing generado automáticamente - {len(analyzed_items)} fuentes analizadas, {len(high)} señales de alta relevancia.*")
    lines.append("")

    return "\n".join(lines)


def inject_into_report(report_path: str, briefing_md: str) -> str:
    """
    Inyecta el briefing en un reporte diario existente.
    Lo inserta ANTES de las tablas detalladas (antes del bloque que empieza con
    "## Detalle por Activo" o "---" final).

    Args:
        report_path: Path al archivo .md del reporte
        briefing_md: Markdown del briefing a inyectar

    Returns:
        Path del archivo modificado
    """
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Buscar punto de inserción: antes de las tablas detalladas
    # Las tablas detalladas suelen empezar con "## Detalle" o "---\n## Detalle"
    insertion_markers = [
        "\n## Detalle por Activo",
        "\n## Tablas Detalladas",
        "\n## Detalle Completo",
        "\n---\n## Detalle",
    ]

    insert_pos = len(content)  # Default: al final
    for marker in insertion_markers:
        pos = content.find(marker)
        if pos != -1 and pos < insert_pos:
            insert_pos = pos

    # Insertar briefing con separador
    separator = "\n---\n\n"
    new_content = content[:insert_pos] + separator + briefing_md + content[insert_pos:]

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"[INFO] [integrator] Briefing inyectado en: {report_path}")
    return report_path


def save_standalone_briefing(briefing_md: str, output_dir: str = None) -> str:
    """
    Guarda el briefing como archivo markdown independiente.

    Returns:
        Path del archivo guardado
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(output_dir, exist_ok=True)

    today = date.today().strftime("%Y-%m-%d")
    filename = f"intelligence_briefing_{today}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(briefing_md)

    print(f"[INFO] [integrator] Briefing guardado: {filepath}")
    return filepath


def find_latest_report(mode: str = "AM", base_dir: str = None) -> Optional[str]:
    """
    Encuentra el reporte diario más reciente para inyectar el briefing.
    Busca primero en la raíz del proyecto, luego en archivo_reportes/md/.
    """
    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(__file__), "..", "..")

    today = date.today().strftime("%Y-%m-%d")

    # Buscar en raíz del proyecto primero (reportes frescos)
    pattern_root = os.path.join(base_dir, f"daily_report_{mode}_finanzas_{today}.md")
    matches = glob.glob(pattern_root)
    if matches:
        return matches[0]

    # Buscar en archivo
    pattern_archive = os.path.join(base_dir, "archivo_reportes", "md",
                                   f"daily_report_{mode}_finanzas_{today}.md")
    matches = glob.glob(pattern_archive)
    if matches:
        return matches[0]

    print(f"[WARN] [integrator] No se encontró reporte {mode} finanzas para {today}")
    return None


if __name__ == "__main__":
    print("=" * 60)
    print("REPORT INTEGRATOR - Test independiente")
    print("=" * 60)

    # Cargar items analizados
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    input_path = os.path.join(data_dir, "analyzed_items.json")

    if not os.path.exists(input_path):
        print(f"[ERROR] No encontrado: {input_path}")
        print("Corre primero claude_analyzer.py")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    print(f"[INFO] Cargados {len(items)} items analizados")

    # Generar briefing
    briefing = generate_briefing(items)

    # Guardar standalone
    filepath = save_standalone_briefing(briefing)

    # Mostrar preview
    print(f"\n{'=' * 60}")
    print("PREVIEW DEL BRIEFING")
    print("=" * 60)
    print(briefing[:3000])
    if len(briefing) > 3000:
        print(f"\n... ({len(briefing)} caracteres total)")

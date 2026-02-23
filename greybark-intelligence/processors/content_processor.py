# -*- coding: utf-8 -*-
"""
CONTENT PROCESSOR - Limpia, deduplica y normaliza items recolectados.
Prepara los items para ser enviados al analizador Claude.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any
from bs4 import BeautifulSoup
from dateutil import parser as dateparser


# Límite de caracteres por item para no explotar el contexto de Claude
MAX_CONTENT_LENGTH = 2000


def clean_html(text: str) -> str:
    """Remueve tags HTML y normaliza espacios."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    clean = soup.get_text(separator=" ")
    # Normalizar espacios múltiples y newlines
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def truncate(text: str, max_length: int = MAX_CONTENT_LENGTH) -> str:
    """Trunca texto a max_length caracteres, cortando en palabra completa."""
    if not text or len(text) <= max_length:
        return text
    truncated = text[:max_length]
    # Cortar en el último espacio para no cortar una palabra
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.8:
        truncated = truncated[:last_space]
    return truncated + "..."


def deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Elimina duplicados por título o URL.
    Si un artículo aparece en múltiples fuentes (ej: FT en Telegram y RSS),
    mantiene el que tiene más contenido.
    """
    seen_titles = {}
    seen_urls = {}
    unique_items = []

    for item in items:
        title_key = item.get('title', '').strip().lower()[:80]
        url_key = item.get('url', '').strip()

        # Verificar duplicado por URL
        if url_key and url_key in seen_urls:
            existing_idx = seen_urls[url_key]
            # Mantener el que tiene más contenido
            if len(item.get('content', '')) > len(unique_items[existing_idx].get('content', '')):
                unique_items[existing_idx] = item
            continue

        # Verificar duplicado por título (fuzzy: primeros 80 chars lowercase)
        if title_key and title_key in seen_titles:
            existing_idx = seen_titles[title_key]
            if len(item.get('content', '')) > len(unique_items[existing_idx].get('content', '')):
                unique_items[existing_idx] = item
            continue

        # Item nuevo
        idx = len(unique_items)
        if title_key:
            seen_titles[title_key] = idx
        if url_key:
            seen_urls[url_key] = idx
        unique_items.append(item)

    return unique_items


def filter_by_date(items: List[Dict[str, Any]], hours_back: int = 24) -> List[Dict[str, Any]]:
    """Filtra items que estén dentro de la ventana de tiempo."""
    # Lunes: ampliar a 72h para cubrir fin de semana
    if datetime.now().weekday() == 0:
        hours_back = max(hours_back, 72)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    filtered = []

    for item in items:
        pub_date = item.get('published_at', '')
        if not pub_date:
            filtered.append(item)  # Sin fecha -> incluir por defecto
            continue
        try:
            dt = dateparser.parse(pub_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt >= cutoff:
                filtered.append(item)
        except Exception:
            filtered.append(item)  # Fecha no parseable -> incluir

    return filtered


def process_items(items: List[Dict[str, Any]], hours_back: int = 24) -> List[Dict[str, Any]]:
    """
    Pipeline completo de procesamiento:
    1. Filtrar por fecha
    2. Limpiar HTML del contenido
    3. Truncar contenido largo
    4. Deduplicar por título/URL
    """
    print(f"[INFO] [processor] Items recibidos: {len(items)}")

    # 1. Filtrar por fecha
    items = filter_by_date(items, hours_back)
    print(f"[INFO] [processor] Después de filtro temporal ({hours_back}h): {len(items)}")

    # 2. Limpiar HTML y truncar
    for item in items:
        item['content'] = clean_html(item.get('content', ''))
        item['title'] = clean_html(item.get('title', ''))
        item['content'] = truncate(item['content'])

    # 3. Deduplicar
    items = deduplicate(items)
    print(f"[INFO] [processor] Después de deduplicación: {len(items)}")

    # 4. Descartar items sin título ni contenido útil
    items = [i for i in items if i.get('title') or len(i.get('content', '')) > 50]
    print(f"[INFO] [processor] Items finales procesados: {len(items)}")

    return items


if __name__ == "__main__":
    import json
    import os

    print("=" * 60)
    print("CONTENT PROCESSOR - Test independiente")
    print("=" * 60)

    # Cargar datos de test de los collectors
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    all_items = []

    for filename in ["test_substack.json", "test_telegram.json", "test_rss.json"]:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                items = json.load(f)
                print(f"[INFO] Cargados {len(items)} items de {filename}")
                all_items.extend(items)
        else:
            print(f"[WARN] No encontrado: {filename}")

    if not all_items:
        print("[ERROR] No hay datos de test. Corre primero los collectors.")
    else:
        processed = process_items(all_items, hours_back=168)

        print(f"\n{'=' * 60}")
        print(f"RESULTADOS: {len(processed)} items procesados")
        print("=" * 60)

        for item in processed[:5]:
            print(f"\n[{item['source_type']}] [{item['source_name']}] {item['title'][:80]}")
            print(f"  Contenido ({len(item['content'])} chars): {item['content'][:120]}...")

        # Guardar
        output_path = os.path.join(data_dir, "processed_items.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=2)
        print(f"\nResultados guardados en: {output_path}")

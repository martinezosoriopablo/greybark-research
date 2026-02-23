# -*- coding: utf-8 -*-
"""
CLAUDE ANALYZER - Clasifica y resume items usando la API de Claude.
Envía items en batches y retorna análisis estructurado en JSON.
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
from typing import Dict, List, Any
from anthropic import Anthropic
from dotenv import load_dotenv

# Cargar .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Configuración
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 8192
BATCH_SIZE = 20  # Items por llamada a Claude

SYSTEM_PROMPT = """Eres un analista senior de Greybark Research, una firma chilena de wealth management.
Tu trabajo es clasificar y resumir noticias y análisis financieros para el equipo de inversión.

Para cada item numerado que recibas, proporciona un análisis con los siguientes campos:

1. **category**: Exactamente una de:
   macro | geopolitica | fed_bancos_centrales | commodities | equity | latam | chile | riesgo

2. **relevance**: Relevancia para Greybark y sus clientes:
   alta | media | baja

3. **summary_es**: Resumen de 1-2 oraciones EN ESPAÑOL. Conciso y orientado a inversión.

4. **investment_signal**: Señal de inversión implícita:
   bullish | bearish | neutral | N/A

5. **asset_classes_affected**: Lista de clases de activos afectadas:
   Posibles valores: renta_variable, renta_fija, fx, commodities, crypto, alternativas
   Puede ser una lista vacía si no aplica.

PRIORIDADES 2026 para clasificación:
- Geopolítica (aranceles Trump, conflictos, sanciones) → impacto directo en mercados
- IA/Tech → solo si afecta valuaciones o productividad macro
- Política monetaria (Fed, BCE, BCCh) → señales de tasas
- LatAm/Chile → cualquier cosa que impacte mercados locales

Responde SIEMPRE en JSON válido con esta estructura exacta:
{
  "analyses": [
    {
      "item_id": 1,
      "category": "macro",
      "relevance": "alta",
      "summary_es": "Resumen en español...",
      "investment_signal": "bearish",
      "asset_classes_affected": ["renta_variable", "fx"]
    }
  ]
}"""


def get_client() -> Anthropic:
    """Obtiene cliente de Anthropic."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no encontrada en .env")
    return Anthropic(api_key=api_key)


def format_items_for_prompt(items: List[Dict[str, Any]]) -> str:
    """Formatea items como texto numerado para el prompt."""
    lines = []
    for i, item in enumerate(items, 1):
        source = item.get('source_name', 'Unknown')
        source_type = item.get('source_type', '')
        title = item.get('title', 'Sin título')
        content = item.get('content', '')
        url = item.get('url', '')
        date = item.get('published_at', '')

        block = f"--- ITEM {i} ---\n"
        block += f"Fuente: {source} ({source_type})\n"
        block += f"Título: {title}\n"
        if date:
            block += f"Fecha: {date}\n"
        if content:
            block += f"Contenido: {content}\n"
        if url:
            block += f"URL: {url}\n"
        lines.append(block)

    return "\n".join(lines)


def analyze_batch(client: Anthropic, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analiza un batch de items con Claude."""
    prompt_text = format_items_for_prompt(items)
    user_msg = f"Analiza los siguientes {len(items)} items de inteligencia financiera:\n\n{prompt_text}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )

    # Extraer texto de la respuesta
    response_text = response.content[0].text

    # Parsear JSON de la respuesta
    # Claude a veces envuelve el JSON en ```json ... ```
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        # Remover fences de código
        lines = clean_text.split('\n')
        lines = [l for l in lines if not l.strip().startswith("```")]
        clean_text = '\n'.join(lines)

    result = json.loads(clean_text)
    analyses = result.get('analyses', [])

    # Reportar uso de tokens
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    # Sonnet 4.5: $3/M input, $15/M output
    cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
    print(f"[INFO] [analyzer] Tokens: {input_tokens} in / {output_tokens} out | Costo: ${cost:.4f}")

    return analyses


def analyze_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Analiza todos los items en batches.
    Retorna la lista de items enriquecidos con los campos de análisis.
    """
    if not items:
        print("[WARN] [analyzer] No hay items para analizar")
        return []

    client = get_client()
    total_cost = 0.0

    # Dividir en batches
    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    print(f"[INFO] [analyzer] {len(items)} items en {len(batches)} batch(es) de hasta {BATCH_SIZE}")

    all_analyzed = []

    for batch_idx, batch in enumerate(batches):
        print(f"[INFO] [analyzer] Procesando batch {batch_idx + 1}/{len(batches)} ({len(batch)} items)...")

        try:
            analyses = analyze_batch(client, batch)

            # Mapear análisis a items originales
            analysis_map = {a['item_id']: a for a in analyses}

            for i, item in enumerate(batch, 1):
                analysis = analysis_map.get(i, {})
                item['category'] = analysis.get('category', 'macro')
                item['relevance'] = analysis.get('relevance', 'baja')
                item['summary_es'] = analysis.get('summary_es', '')
                item['investment_signal'] = analysis.get('investment_signal', 'neutral')
                item['asset_classes_affected'] = analysis.get('asset_classes_affected', [])
                all_analyzed.append(item)

        except json.JSONDecodeError as e:
            print(f"[ERROR] [analyzer] Error parseando JSON de Claude en batch {batch_idx + 1}: {e}")
            # Agregar items sin análisis
            for item in batch:
                item['category'] = 'macro'
                item['relevance'] = 'baja'
                item['summary_es'] = '[Error de análisis]'
                item['investment_signal'] = 'neutral'
                item['asset_classes_affected'] = []
                all_analyzed.append(item)

        except Exception as e:
            print(f"[ERROR] [analyzer] Error en batch {batch_idx + 1}: {e}")
            for item in batch:
                item['category'] = 'macro'
                item['relevance'] = 'baja'
                item['summary_es'] = '[Error de análisis]'
                item['investment_signal'] = 'neutral'
                item['asset_classes_affected'] = []
                all_analyzed.append(item)

    # Resumen
    high = sum(1 for i in all_analyzed if i.get('relevance') == 'alta')
    medium = sum(1 for i in all_analyzed if i.get('relevance') == 'media')
    low = sum(1 for i in all_analyzed if i.get('relevance') == 'baja')
    print(f"[INFO] [analyzer] Análisis completo: {high} alta, {medium} media, {low} baja relevancia")

    return all_analyzed


if __name__ == "__main__":
    print("=" * 60)
    print("CLAUDE ANALYZER - Test independiente")
    print("=" * 60)

    # Cargar items procesados
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    input_path = os.path.join(data_dir, "processed_items.json")

    if not os.path.exists(input_path):
        print(f"[ERROR] No encontrado: {input_path}")
        print("Corre primero content_processor.py para generar processed_items.json")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8') as f:
        items = json.load(f)

    print(f"[INFO] Cargados {len(items)} items procesados")

    # Analizar
    analyzed = analyze_items(items)

    print(f"\n{'=' * 60}")
    print(f"RESULTADOS: {len(analyzed)} items analizados")
    print("=" * 60)

    # Mostrar items de alta relevancia
    high_relevance = [i for i in analyzed if i.get('relevance') == 'alta']
    print(f"\n--- ALTA RELEVANCIA ({len(high_relevance)} items) ---")
    for item in high_relevance:
        print(f"\n[{item['category']}] [{item['investment_signal']}] {item['source_name']}")
        print(f"  {item['summary_es']}")
        print(f"  Activos: {', '.join(item.get('asset_classes_affected', []))}")

    # Guardar
    output_path = os.path.join(data_dir, "analyzed_items.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analyzed, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: {output_path}")

# -*- coding: utf-8 -*-
"""
RSS COLLECTOR - Recolecta noticias de medios tradicionales vía RSS.
Usa feedparser para parsear feeds de Reuters, Bloomberg, FT, WSJ, FRED.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import yaml
import feedparser
from typing import Dict, List, Any
from base_collector import BaseCollector


class RssCollector(BaseCollector):
    """Recolecta noticias de medios tradicionales vía feeds RSS."""

    def __init__(self, config_path: str = None, hours_back: int = 24):
        super().__init__(source_type="rss", hours_back=hours_back)
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "sources.yaml")
        self.config_path = os.path.abspath(config_path)
        self.sources = self._load_sources()

    def _load_sources(self) -> List[Dict[str, Any]]:
        """Carga la lista de feeds RSS desde sources.yaml."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            sources = config.get('rss_feeds', [])
            self.log("INFO", f"Cargadas {len(sources)} fuentes RSS de medios")
            return sources
        except Exception as e:
            self.log("ERROR", f"No se pudo cargar sources.yaml: {e}")
            return []

    def collect(self) -> List[Dict[str, Any]]:
        """Recolecta noticias de todos los feeds RSS de medios configurados."""
        items = []

        for source in self.sources:
            name = source.get('name', 'Unknown')
            feed_url = source.get('feed', '')
            if not feed_url:
                self.log("WARN", f"Feed URL vacía para {name}, saltando")
                continue

            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo and not feed.entries:
                    self.log("WARN", f"{name}: feed con error - {feed.bozo_exception}")
                    continue

                count = 0
                for entry in feed.entries:
                    published = getattr(entry, 'published', '') or getattr(entry, 'updated', '')
                    if not self.is_within_window(published):
                        continue

                    title = getattr(entry, 'title', '') or ''
                    # En medios tradicionales, summary suele ser el snippet
                    content = getattr(entry, 'summary', '') or ''
                    if not content:
                        content_list = getattr(entry, 'content', [])
                        if content_list:
                            content = content_list[0].get('value', '')

                    url = getattr(entry, 'link', '') or ''

                    item = self.make_item(
                        source_name=name,
                        title=title,
                        content=content,
                        url=url,
                        published_at=self.parse_date(published).isoformat() if self.parse_date(published) else None
                    )
                    items.append(item)
                    count += 1

                if count > 0:
                    self.log("INFO", f"{name}: {count} artículos recolectados")
                else:
                    self.log("INFO", f"{name}: sin artículos nuevos en ventana de {self.hours_back}h")

            except Exception as e:
                self.log("ERROR", f"{name}: error al procesar feed - {e}")
                continue

        self.log("INFO", f"Total RSS Medios: {len(items)} artículos recolectados")
        return items


if __name__ == "__main__":
    import json
    print("=" * 60)
    print("RSS COLLECTOR (MEDIOS) - Test independiente")
    print("=" * 60)

    # Para testing: ampliar ventana a 7 días para ver resultados
    collector = RssCollector(hours_back=168)
    items = collector.collect()

    print(f"\n{'=' * 60}")
    print(f"RESULTADOS: {len(items)} artículos")
    print("=" * 60)

    for item in items[:5]:  # Mostrar primeros 5
        print(f"\n[{item['source_name']}] {item['title']}")
        print(f"  URL: {item['url']}")
        print(f"  Fecha: {item['published_at']}")
        print(f"  Contenido: {item['content'][:150]}...")

    # Guardar resultado completo
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "test_rss.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: {output_path}")

# -*- coding: utf-8 -*-
"""
TELEGRAM COLLECTOR - Recolecta mensajes de canales públicos de Telegram.
Usa telethon para conectar a la API de Telegram.

IMPORTANTE: La primera ejecución requiere autenticación interactiva.
- Te pedirá tu número de teléfono (con código país, ej: +56912345678)
- Te llegará un código por Telegram (en la app del celular)
- Ingresa ese código en la consola
- Después de eso, se guarda un archivo .session y ya no pide más.

Requiere en .env:
  TELEGRAM_API_ID=tu_api_id
  TELEGRAM_API_HASH=tu_api_hash
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import asyncio
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Any
from dotenv import load_dotenv

from base_collector import BaseCollector

# Cargar variables de entorno
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


class TelegramCollector(BaseCollector):
    """Recolecta mensajes de canales públicos de Telegram usando telethon."""

    def __init__(self, config_path: str = None, hours_back: int = 24):
        super().__init__(source_type="telegram", hours_back=hours_back)
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "sources.yaml")
        self.config_path = os.path.abspath(config_path)

        # Credenciales de Telegram desde .env
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")

        # Archivo de sesión (se guarda junto a la config)
        session_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        self.session_path = os.path.join(os.path.abspath(session_dir), "greybark_telegram")

        self.channels = self._load_channels()

    def _load_channels(self) -> List[Dict[str, Any]]:
        """Carga la lista de canales desde sources.yaml."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            channels = config.get('telegram_channels', [])
            self.log("INFO", f"Cargados {len(channels)} canales Telegram")
            return channels
        except Exception as e:
            self.log("ERROR", f"No se pudo cargar sources.yaml: {e}")
            return []

    def _validate_credentials(self) -> bool:
        """Verifica que las credenciales de Telegram estén configuradas."""
        if not self.api_id or not self.api_hash:
            self.log("ERROR", "Credenciales Telegram no configuradas en .env")
            self.log("ERROR", "Agrega TELEGRAM_API_ID y TELEGRAM_API_HASH al archivo .env")
            return False
        return True

    async def _collect_async(self) -> List[Dict[str, Any]]:
        """Lógica async de recolección usando telethon."""
        from telethon import TelegramClient

        items = []
        client = TelegramClient(self.session_path, int(self.api_id), self.api_hash)

        try:
            await client.start()
            self.log("INFO", "Conectado a Telegram")

            for channel_config in self.channels:
                name = channel_config.get('name', 'Unknown')
                handle = channel_config.get('handle', '')
                max_msgs = channel_config.get('max_messages_per_day', 20)

                if not handle:
                    self.log("WARN", f"Handle vacío para {name}, saltando")
                    continue

                try:
                    entity = await client.get_entity(handle)
                    messages = await client.get_messages(
                        entity,
                        limit=max_msgs,
                        offset_date=datetime.now(timezone.utc)
                    )

                    count = 0
                    for msg in messages:
                        # Solo mensajes de texto
                        if not msg.text:
                            continue

                        # Filtrar por ventana de tiempo
                        msg_date = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
                        if msg_date < self.cutoff_time:
                            continue

                        item = self.make_item(
                            source_name=f"@{handle}",
                            title=msg.text[:100].replace('\n', ' '),  # Primeros 100 chars como título
                            content=msg.text,
                            url=f"https://t.me/{handle}/{msg.id}",
                            published_at=msg_date.isoformat()
                        )
                        items.append(item)
                        count += 1

                    if count > 0:
                        self.log("INFO", f"{name} (@{handle}): {count} mensajes recolectados")
                    else:
                        self.log("INFO", f"{name} (@{handle}): sin mensajes nuevos")

                except Exception as e:
                    self.log("ERROR", f"{name} (@{handle}): error - {e}")
                    continue

                # Rate limiting: esperar entre canales para evitar FloodWaitError
                await asyncio.sleep(1)

        except Exception as e:
            self.log("ERROR", f"Error de conexión Telegram: {e}")
        finally:
            await client.disconnect()

        self.log("INFO", f"Total Telegram: {len(items)} mensajes recolectados")
        return items

    def collect(self) -> List[Dict[str, Any]]:
        """Recolecta mensajes de todos los canales Telegram configurados."""
        if not self._validate_credentials():
            return []

        try:
            return asyncio.run(self._collect_async())
        except Exception as e:
            self.log("ERROR", f"Error ejecutando collector Telegram: {e}")
            return []


if __name__ == "__main__":
    import json
    print("=" * 60)
    print("TELEGRAM COLLECTOR - Test independiente")
    print("=" * 60)
    print("\nNOTA: La primera ejecución pedirá autenticación por SMS.")
    print("Después de eso, la sesión queda guardada.\n")

    collector = TelegramCollector(hours_back=48)
    items = collector.collect()

    print(f"\n{'=' * 60}")
    print(f"RESULTADOS: {len(items)} mensajes")
    print("=" * 60)

    for item in items[:10]:  # Mostrar primeros 10
        print(f"\n[{item['source_name']}] {item['title']}")
        print(f"  URL: {item['url']}")
        print(f"  Fecha: {item['published_at']}")
        print(f"  Contenido: {item['content'][:150]}...")

    # Guardar resultado completo
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "test_telegram.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en: {output_path}")

# -*- coding: utf-8 -*-
"""
SETUP TELEGRAM - Autenticación inicial de Telegram.
Corre este script UNA VEZ desde tu terminal para crear la sesión.

Uso:
    python greybark-intelligence/setup_telegram.py

Te pedirá:
  1. Tu número de teléfono (con código país, ej: +56912345678)
  2. Un código que te llegará por Telegram (en la app del celular)

Después de eso, se guarda el archivo .session y no vuelve a pedir.
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
from dotenv import load_dotenv
from telethon import TelegramClient

# Cargar .env desde la raíz del proyecto
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_PATH = os.path.join(os.path.dirname(__file__), "config", "greybark_telegram")


async def main():
    print("=" * 60)
    print("GREYBARK INTELLIGENCE - Setup Telegram")
    print("=" * 60)

    if not API_ID or not API_HASH:
        print("\n[ERROR] No se encontraron TELEGRAM_API_ID y TELEGRAM_API_HASH en .env")
        return

    print(f"\nAPI ID: {API_ID}")
    print(f"Sesión se guardará en: {os.path.abspath(SESSION_PATH)}.session")
    print("\nSe te pedirá tu número de teléfono y un código de verificación.\n")

    client = TelegramClient(SESSION_PATH, int(API_ID), API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"\n[OK] Autenticado como: {me.first_name} (@{me.username or 'sin username'})")
    print(f"[OK] Sesión guardada. No necesitas volver a autenticarte.")

    # Test rápido: verificar acceso a un canal
    print("\n--- Test rápido: leyendo últimos mensajes de @Bloomberg ---")
    try:
        entity = await client.get_entity("Bloomberg")
        messages = await client.get_messages(entity, limit=3)
        for msg in messages:
            if msg.text:
                print(f"  [{msg.date.strftime('%H:%M')}] {msg.text[:100]}...")
        print("\n[OK] Conexión a canales funciona correctamente.")
    except Exception as e:
        print(f"\n[WARN] No se pudo leer @Bloomberg: {e}")
        print("Puede que necesites unirte al canal primero.")

    await client.disconnect()
    print("\n[LISTO] Setup completado. Ya puedes correr telegram_collector.py")


if __name__ == "__main__":
    asyncio.run(main())

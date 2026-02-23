# -*- coding: utf-8 -*-
"""
BASE COLLECTOR - Clase base para todos los collectors del Intelligence Pipeline.
Define el formato estándar de items y helpers comunes.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from dateutil import parser as dateparser


# Formato estándar que retorna cada collector
ITEM_TEMPLATE = {
    "source_type": "",      # "substack" | "telegram" | "rss"
    "source_name": "",      # "Fed Guy" | "@Bloomberg" | "Reuters"
    "title": "",            # Título del artículo o mensaje
    "content": "",          # Texto completo o resumen disponible
    "url": "",              # URL del artículo (si aplica)
    "published_at": "",     # ISO 8601 (ej: 2026-02-23T08:00:00Z)
    "collected_at": "",     # ISO 8601 timestamp de recolección
    "category": None        # Se llena en fase de análisis (Fase 2)
}


class BaseCollector(ABC):
    """Clase base para collectors del Intelligence Pipeline."""

    def __init__(self, source_type: str, hours_back: int = 24):
        self.source_type = source_type
        self.hours_back = hours_back
        # Si es lunes, recoger contenido del fin de semana (72h)
        if datetime.now().weekday() == 0:  # 0 = lunes
            self.hours_back = max(hours_back, 72)
            print(f"[INFO] Lunes detectado: ampliando ventana a {self.hours_back}h")
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.hours_back)

    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """Recolecta items de la fuente. Debe ser implementado por cada subclase."""
        pass

    def make_item(self, source_name: str, title: str, content: str,
                  url: str = "", published_at: Optional[str] = None) -> Dict[str, Any]:
        """Crea un item con el formato estándar."""
        return {
            "source_type": self.source_type,
            "source_name": source_name,
            "title": title.strip() if title else "",
            "content": content.strip() if content else "",
            "url": url or "",
            "published_at": published_at or datetime.now(timezone.utc).isoformat(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "category": None
        }

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Parsea una fecha string a datetime UTC. Retorna None si falla."""
        if not date_str:
            return None
        try:
            dt = dateparser.parse(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def is_within_window(self, date_str: str) -> bool:
        """Verifica si una fecha está dentro de la ventana de recolección."""
        dt = self.parse_date(date_str)
        if dt is None:
            return True  # Si no podemos parsear la fecha, incluir por defecto
        return dt >= self.cutoff_time

    def log(self, level: str, msg: str):
        """Log con formato consistente."""
        prefix = {"INFO": "[INFO]", "WARN": "[WARN]", "ERROR": "[ERROR]"}
        print(f"{prefix.get(level, '[INFO]')} [{self.source_type}] {msg}")

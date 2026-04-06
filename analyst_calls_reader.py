# -*- coding: utf-8 -*-
"""
Greybark Research — Analyst Calls Reader
==========================================

Reads analyst_calls.json from greybark-intelligence pipeline and formats
for AI Council agents. Each call has: analyst, firm, direction (BUY/SELL),
asset, asset_class, price_target, thesis, conviction, timeframe.

Sources: Telegram channels, Substack newsletters, financial media.

Usage:
    from analyst_calls_reader import AnalystCallsReader

    reader = AnalystCallsReader()
    calls = reader.get_recent_calls(days=7)
    text = reader.format_for_council(calls)
    agent_text = reader.format_for_agent(calls, 'rv')
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# Default path — can be overridden via env var
DEFAULT_PATH = Path(os.environ.get(
    'GREYBARK_INTELLIGENCE_PATH',
    str(Path.home() / "OneDrive/Documentos/proyectos/greybark-intelligence/data")
))


class AnalystCallsReader:
    """Reads and formats analyst calls from greybark-intelligence pipeline."""

    # Map asset_class from calls → agent routing
    AGENT_MAP = {
        'renta_variable': ['rv', 'riesgo', 'cio'],
        'renta_fija': ['rf', 'riesgo', 'cio'],
        'commodities': ['geo', 'macro', 'cio'],
        'fx': ['macro', 'geo', 'cio'],
        'crypto': ['riesgo', 'cio'],
        'alternativas': ['riesgo', 'cio'],
        'macro': ['macro', 'rv', 'rf', 'riesgo', 'geo', 'cio'],
    }

    def __init__(self, data_path: Path = None, verbose: bool = True):
        self.data_path = data_path or DEFAULT_PATH
        self.verbose = verbose

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def get_recent_calls(self, days: int = 7) -> List[Dict]:
        """Load analyst calls from the last N days."""
        if not self.data_path.exists():
            self._print(f"  [WARN] Analyst calls path not found: {self.data_path}")
            return []

        calls = []
        cutoff = datetime.now() - timedelta(days=days)

        # Iterate date folders in reverse (newest first)
        date_dirs = sorted(self.data_path.iterdir(), reverse=True)
        for d in date_dirs:
            if not d.is_dir() or not d.name.startswith('202'):
                continue
            try:
                dir_date = datetime.strptime(d.name, '%Y-%m-%d')
                if dir_date < cutoff:
                    break
            except ValueError:
                continue

            calls_file = d / 'analyst_calls.json'
            if not calls_file.exists():
                continue

            try:
                with open(calls_file, 'r', encoding='utf-8') as f:
                    day_calls = json.load(f)
                if isinstance(day_calls, list):
                    for c in day_calls:
                        c['_date'] = d.name
                    calls.extend(day_calls)
            except (json.JSONDecodeError, IOError) as e:
                self._print(f"  [WARN] Error reading {calls_file}: {e}")

        self._print(f"  [OK] Analyst calls: {len(calls)} calls from last {days} days")
        return calls

    def format_for_council(self, calls: List[Dict]) -> str:
        """Format all calls as a council-level summary."""
        if not calls:
            return ''

        # Group by asset class
        by_class = {}
        for c in calls:
            for ac in c.get('asset_classes_affected', [c.get('asset_class', 'macro')]):
                by_class.setdefault(ac, []).append(c)

        lines = [
            "## ANALYST CALLS — CONSENSO DE MERCADO EXTERNO (últimos 7 días)",
            f"Fuente: Telegram + Substack + medios financieros ({len(calls)} calls)",
            "Usa estas opiniones para CONTRASTAR tu análisis. Si coincides, cita como confirmación.",
            "Si diverges, explica por qué con datos.",
            ""
        ]

        # Summary table
        buy_count = sum(1 for c in calls if c.get('direction', '').upper() in ('BUY', 'LONG'))
        sell_count = sum(1 for c in calls if c.get('direction', '').upper() in ('SELL', 'SHORT'))
        lines.append(f"Resumen: {buy_count} BUY vs {sell_count} SELL (de {len(calls)} calls)")
        lines.append("")

        # High conviction calls first
        high_conv = [c for c in calls if c.get('conviction', '').lower() == 'high']
        if high_conv:
            lines.append("### Calls Alta Convicción")
            for c in high_conv:
                pt = f" (PT: {c['price_target']})" if c.get('price_target') else ''
                lines.append(
                    f"- **{c.get('direction', '?')} {c.get('asset', '?')}**{pt} — "
                    f"{c.get('analyst', '?')} ({c.get('firm', '?')}): "
                    f"{c.get('thesis', '')[:150]}"
                )
            lines.append("")

        # By asset class
        for ac_name, ac_calls in sorted(by_class.items()):
            if not ac_calls:
                continue
            lines.append(f"### {ac_name.replace('_', ' ').title()}")
            for c in ac_calls[:8]:  # Cap at 8 per class
                pt = f" PT:{c['price_target']}" if c.get('price_target') else ''
                conv = f" [{c.get('conviction', '?')}]" if c.get('conviction') else ''
                lines.append(
                    f"- {c.get('direction', '?')} {c.get('asset', '?')}{pt}{conv} — "
                    f"{c.get('analyst', '?')}: {c.get('thesis', '')[:120]}"
                )
            lines.append("")

        return "\n".join(lines)

    def format_for_agent(self, calls: List[Dict], agent: str) -> str:
        """Format calls filtered for a specific agent."""
        if not calls:
            return ''

        # Filter calls relevant to this agent
        relevant = []
        for c in calls:
            asset_classes = c.get('asset_classes_affected', [c.get('asset_class', 'macro')])
            if isinstance(asset_classes, str):
                asset_classes = [asset_classes]
            for ac in asset_classes:
                agents_for_ac = self.AGENT_MAP.get(ac, ['cio'])
                if agent in agents_for_ac:
                    relevant.append(c)
                    break

        if not relevant:
            return ''

        lines = [
            f"## ANALYST CALLS para {agent.upper()} ({len(relevant)} relevantes)",
            ""
        ]

        for c in relevant[:10]:  # Cap at 10 per agent
            pt = f" (PT: {c['price_target']})" if c.get('price_target') else ''
            lines.append(
                f"- {c.get('direction', '?')} {c.get('asset', '?')}{pt} "
                f"[{c.get('conviction', '?')}] — "
                f"{c.get('analyst', '?')} ({c.get('firm', '?')}): "
                f"{c.get('thesis', '')[:150]}"
            )

        return "\n".join(lines)

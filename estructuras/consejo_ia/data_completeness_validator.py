# -*- coding: utf-8 -*-
"""
Greybark Research - Data Completeness Validator
=================================================

Field-by-field validation of council input data against the data manifest.
Replaces the module-level preflight with granular per-field checks.

Gate logic:
- Required coverage < 80% for ANY agent → NO_GO (abort)
- Required coverage < 100% → CAUTION (continue but document)
- Important coverage < 50% → CAUTION
- Else → GO
"""

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from data_manifest import (
    AGENT_MANIFESTS, DataField, FieldPriority,
    get_manifest, get_all_agents,
)


# =============================================================================
# RESULT DATA CLASSES
# =============================================================================

@dataclass
class FieldStatus:
    """Status of a single data field."""
    field: DataField
    status: str          # PRESENT, MISSING, ERROR
    value: Any = None    # Actual value if present
    timestamp: str = ""  # ISO timestamp if available


@dataclass
class AgentCompleteness:
    """Completeness result for one agent."""
    agent: str
    fields: List[FieldStatus]

    @property
    def required_total(self) -> int:
        return sum(1 for f in self.fields if f.field.priority == FieldPriority.REQUIRED)

    @property
    def required_present(self) -> int:
        return sum(1 for f in self.fields
                   if f.field.priority == FieldPriority.REQUIRED and f.status == 'PRESENT')

    @property
    def required_coverage(self) -> float:
        total = self.required_total
        return self.required_present / total if total > 0 else 1.0

    @property
    def important_total(self) -> int:
        return sum(1 for f in self.fields if f.field.priority == FieldPriority.IMPORTANT)

    @property
    def important_present(self) -> int:
        return sum(1 for f in self.fields
                   if f.field.priority == FieldPriority.IMPORTANT and f.status == 'PRESENT')

    @property
    def important_coverage(self) -> float:
        total = self.important_total
        return self.important_present / total if total > 0 else 1.0

    @property
    def optional_total(self) -> int:
        return sum(1 for f in self.fields if f.field.priority == FieldPriority.OPTIONAL)

    @property
    def optional_present(self) -> int:
        return sum(1 for f in self.fields
                   if f.field.priority == FieldPriority.OPTIONAL and f.status == 'PRESENT')

    @property
    def missing_required(self) -> List[DataField]:
        return [f.field for f in self.fields
                if f.field.priority == FieldPriority.REQUIRED and f.status != 'PRESENT']

    @property
    def missing_important(self) -> List[DataField]:
        return [f.field for f in self.fields
                if f.field.priority == FieldPriority.IMPORTANT and f.status != 'PRESENT']

    @property
    def present_fields(self) -> List[FieldStatus]:
        return [f for f in self.fields if f.status == 'PRESENT']


@dataclass
class CompletenessResult:
    """Full completeness validation result."""
    timestamp: str
    agents: Dict[str, AgentCompleteness]
    verdict: str  # GO, CAUTION, NO_GO
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        result = {
            'timestamp': self.timestamp,
            'verdict': self.verdict,
            'issues': self.issues,
            'agents': {},
        }
        for agent_name, ac in self.agents.items():
            agent_dict = {
                'required': f"{ac.required_present}/{ac.required_total}",
                'required_coverage': round(ac.required_coverage * 100, 1),
                'important': f"{ac.important_present}/{ac.important_total}",
                'important_coverage': round(ac.important_coverage * 100, 1),
                'optional': f"{ac.optional_present}/{ac.optional_total}",
                'missing_required': [f.label for f in ac.missing_required],
                'missing_important': [f.label for f in ac.missing_important],
                'fields': [],
            }
            for fs in ac.fields:
                field_dict = {
                    'path': fs.field.path,
                    'label': fs.field.label,
                    'source': fs.field.source,
                    'unit': fs.field.unit,
                    'priority': fs.field.priority.value,
                    'status': fs.status,
                }
                if fs.status == 'PRESENT' and fs.value is not None:
                    # Store scalar values directly, truncate complex types
                    if isinstance(fs.value, (int, float, str, bool)):
                        field_dict['value'] = fs.value
                    elif isinstance(fs.value, dict):
                        field_dict['value'] = f"<dict:{len(fs.value)} keys>"
                    elif isinstance(fs.value, list):
                        field_dict['value'] = f"<list:{len(fs.value)} items>"
                    else:
                        field_dict['value'] = str(fs.value)[:100]
                agent_dict['fields'].append(field_dict)
            result['agents'][agent_name] = agent_dict
        return result


# =============================================================================
# VALIDATOR
# =============================================================================

class DataCompletenessValidator:
    """Validates council input data against the manifest field by field."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _resolve_path(self, data: Dict, path: str) -> Any:
        """Resolve a dot-path like 'macro_usa.gdp' against a dict.

        Returns the value if found, or a sentinel _MISSING if not.
        """
        parts = path.split('.')
        current = data
        for part in parts:
            if not isinstance(current, dict):
                return _MISSING
            if part not in current:
                return _MISSING
            current = current[part]
        return current

    def _is_present(self, value: Any) -> bool:
        """Check if a resolved value counts as present (not empty/error)."""
        if value is _MISSING:
            return False
        if value is None:
            return False
        if isinstance(value, dict) and 'error' in value:
            return False
        if isinstance(value, dict) and len(value) == 0:
            return False
        if isinstance(value, str) and value.strip() == '':
            return False
        return True

    def validate_agent(self, agent: str, agent_data: Dict) -> AgentCompleteness:
        """Validate completeness for one agent."""
        manifest = get_manifest(agent)
        field_statuses = []

        for df in manifest:
            value = self._resolve_path(agent_data, df.path)
            is_ok = self._is_present(value)

            if is_ok:
                status = 'PRESENT'
                stored_value = value
            elif value is _MISSING:
                status = 'MISSING'
                stored_value = None
            else:
                status = 'ERROR'
                stored_value = None

            field_statuses.append(FieldStatus(
                field=df,
                status=status,
                value=stored_value if status == 'PRESENT' else None,
            ))

        return AgentCompleteness(agent=agent, fields=field_statuses)

    def validate(self, agent_data_map: Dict[str, Dict]) -> CompletenessResult:
        """Validate completeness for all agents.

        Args:
            agent_data_map: Dict mapping agent name to their specific data dict.
                This is typically council_input['agent_data'].

        Returns:
            CompletenessResult with per-agent details and global verdict.
        """
        self._print("\n[DataCompleteness] Validando completitud campo por campo...")

        agents = {}
        issues = []

        for agent_name in get_all_agents():
            data = agent_data_map.get(agent_name, {})
            ac = self.validate_agent(agent_name, data)
            agents[agent_name] = ac

            # Log per-agent status
            self._print(
                f"  {agent_name.upper():>8}: "
                f"REQ {ac.required_present}/{ac.required_total} ({ac.required_coverage*100:.0f}%) | "
                f"IMP {ac.important_present}/{ac.important_total} ({ac.important_coverage*100:.0f}%) | "
                f"OPT {ac.optional_present}/{ac.optional_total}"
            )

            if ac.missing_required:
                for mf in ac.missing_required:
                    issues.append(f"{agent_name}: REQUIRED faltante — {mf.label} [{mf.source}]")

            if ac.missing_important:
                for mf in ac.missing_important:
                    issues.append(f"{agent_name}: IMPORTANT faltante — {mf.label} [{mf.source}]")

        # Determine verdict
        verdict = 'GO'

        for agent_name, ac in agents.items():
            if ac.required_coverage < 0.80:
                verdict = 'NO_GO'
                self._print(f"  [NO_GO] {agent_name}: required coverage {ac.required_coverage*100:.0f}% < 80%")
                break
            if ac.required_coverage < 1.0:
                if verdict != 'NO_GO':
                    verdict = 'CAUTION'
            if ac.important_coverage < 0.50:
                if verdict != 'NO_GO':
                    verdict = 'CAUTION'

        self._print(f"  Veredicto completitud: {verdict}")
        if issues:
            self._print(f"  {len(issues)} campos faltantes detectados")

        return CompletenessResult(
            timestamp=datetime.now().isoformat(),
            agents=agents,
            verdict=verdict,
            issues=issues,
        )

    def print_report(self, result: CompletenessResult):
        """Print a formatted completeness report."""
        print(f"\n{'='*70}")
        print("DATA COMPLETENESS REPORT")
        print(f"{'='*70}")
        print(f"  Timestamp: {result.timestamp}")
        print(f"  Verdict: [{result.verdict}]")

        for agent_name, ac in result.agents.items():
            print(f"\n  --- {agent_name.upper()} ---")
            print(f"  Required:  {ac.required_present}/{ac.required_total} ({ac.required_coverage*100:.0f}%)")
            print(f"  Important: {ac.important_present}/{ac.important_total} ({ac.important_coverage*100:.0f}%)")
            print(f"  Optional:  {ac.optional_present}/{ac.optional_total}")

            if ac.missing_required:
                print(f"  Missing REQUIRED:")
                for mf in ac.missing_required:
                    print(f"    - {mf.label} [{mf.source}]")
            if ac.missing_important:
                print(f"  Missing IMPORTANT:")
                for mf in ac.missing_important:
                    print(f"    - {mf.label} [{mf.source}]")

        if result.issues:
            print(f"\n  Total issues: {len(result.issues)}")

        print(f"{'='*70}\n")

    def build_data_inventory(
        self,
        agent: str,
        agent_data: Dict,
    ) -> str:
        """Build structured data inventory text for an agent's prompt.

        Returns formatted text with two sections:
        - DATOS DISPONIBLES: fields that are present with value and source
        - DATOS NO DISPONIBLES: fields that are missing

        Args:
            agent: agent name
            agent_data: the agent's specific data dict

        Returns:
            Formatted inventory string for injection into prompts.
        """
        ac = self.validate_agent(agent, agent_data)

        available_lines = []
        unavailable_lines = []

        for fs in ac.fields:
            if fs.status == 'PRESENT':
                # Format the value for display
                display_val = self._format_value(fs.value, fs.field.unit)
                available_lines.append(
                    f"- {fs.field.label}: {display_val} [fuente: {fs.field.source}]"
                )
            else:
                unavailable_lines.append(
                    f"- {fs.field.label} — NO DISPONIBLE [{fs.field.source}]"
                )

        sections = []

        sections.append("## DATOS DISPONIBLES (usa SOLO estos)")
        if available_lines:
            sections.extend(available_lines)
        else:
            sections.append("- (sin datos disponibles)")

        sections.append("")
        sections.append("## DATOS NO DISPONIBLES (NO mencionar en tu analisis)")
        if unavailable_lines:
            sections.extend(unavailable_lines)
        else:
            sections.append("- (todos los datos disponibles)")

        sections.append("")
        sections.append("## REGLA ESTRICTA DE DATOS")
        sections.append(
            "Solo puedes citar numeros que aparecen EXPLICITAMENTE en DATOS DISPONIBLES.\n"
            "Si un dato NO esta en la lista, NO lo menciones, NO lo estimes, NO lo extrapoles.\n"
            "Prefiere \"no tenemos visibilidad sobre X\" a inventar un numero.\n"
            "Las probabilidades y estimaciones que TU generas (ej: \"prob recesion 35%\")\n"
            "deben marcarse claramente como tu juicio analitico, no como datos."
        )

        return "\n".join(sections)

    def _format_value(self, value: Any, unit: str) -> str:
        """Format a data value for display in the inventory."""
        if isinstance(value, float):
            if unit == '%':
                return f"{value:.2f}%"
            elif unit == 'x':
                return f"{value:.1f}x"
            elif unit == 'bps':
                return f"{int(round(value))}bps"
            elif unit == 'index':
                return f"{value:.1f}"
            else:
                return f"{value:.2f}"
        elif isinstance(value, int):
            return str(value)
        elif isinstance(value, str):
            if len(value) > 100:
                return f"{value[:100]}..."
            return value
        elif isinstance(value, dict):
            # For dicts, show key count and scalar values
            scalar_items = {k: v for k, v in value.items()
                          if isinstance(v, (int, float, str)) and k != 'error'}
            if len(scalar_items) <= 5:
                parts = []
                for k, v in list(scalar_items.items())[:5]:
                    if isinstance(v, float):
                        parts.append(f"{k}={v:.2f}")
                    else:
                        parts.append(f"{k}={v}")
                return "{" + ", ".join(parts) + "}"
            return f"<{len(value)} campos>"
        elif isinstance(value, list):
            return f"<{len(value)} items>"
        return str(value)[:80]


# Sentinel for missing values
class _MissingSentinel:
    def __repr__(self):
        return '<MISSING>'

_MISSING = _MissingSentinel()

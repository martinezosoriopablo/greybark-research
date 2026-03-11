"""
table_builder.py — Greybark Research Reusable Table Library

Centralizes HTML table generation across all 4 reports (Macro, RV, RF, AA).
Ensures consistent styling, badges, arrows, number formatting.

Usage:
    from table_builder import TableBuilder, Badge, Trend, fmt_pct, fmt_bps

    tb = TableBuilder(columns=["Mercado", "View", "Yield", "Spread"])
    tb.add_row(["USA", Badge.ow("OW"), fmt_pct(4.25), fmt_bps(85, vs_prev=-5)])
    html = tb.render()
"""

from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# Badge System (OW/N/UW + variants)
# ─────────────────────────────────────────────

class Badge:
    """Inline badge spans for views, signals, relevancia."""

    @staticmethod
    def _badge(text: str, css_class: str) -> str:
        return f'<span class="view-badge {css_class}">{text}</span>'

    # ── Core view badges ──
    @staticmethod
    def ow(text: str = "OW") -> str:
        return Badge._badge(text, "badge-ow")

    @staticmethod
    def neutral(text: str = "N") -> str:
        return Badge._badge(text, "badge-neutral")

    @staticmethod
    def uw(text: str = "UW") -> str:
        return Badge._badge(text, "badge-uw")

    @staticmethod
    def from_view(view: str, display: str = "") -> str:
        """Auto-detect badge from view string (OW/OVERWEIGHT/N/NEUTRAL/UW/UNDERWEIGHT)."""
        v = (view or "").strip().upper()
        label = display or view or "N"
        if v in ("OW", "OVERWEIGHT", "SOBREPONDERAR"):
            return Badge.ow(label)
        elif v in ("UW", "UNDERWEIGHT", "SUBPONDERAR"):
            return Badge.uw(label)
        else:
            return Badge.neutral(label)

    # ── RF-specific badges ──
    @staticmethod
    def long(text: str = "LONG") -> str:
        return Badge._badge(text, "badge-long")

    @staticmethod
    def short(text: str = "SHORT") -> str:
        return Badge._badge(text, "badge-short")

    @staticmethod
    def from_duration(view: str, display: str = "") -> str:
        v = (view or "").strip().upper()
        label = display or view or "NEUTRAL"
        if v in ("LONG", "LARGA"):
            return Badge.long(label)
        elif v in ("SHORT", "CORTA"):
            return Badge.short(label)
        else:
            return Badge.neutral(label)

    # ── Valuation badges ──
    @staticmethod
    def cheap(text: str = "Barato") -> str:
        return f'<span class="val-cheap">{text}</span>'

    @staticmethod
    def expensive(text: str = "Caro") -> str:
        return f'<span class="val-expensive">{text}</span>'

    @staticmethod
    def fair(text: str = "Justo") -> str:
        return f'<span class="val-fair">{text}</span>'

    @staticmethod
    def from_valuation(pct_vs_avg: float, text: str = "") -> str:
        """Badge based on % vs historical average. >+10% = expensive, <0% = cheap."""
        if pct_vs_avg > 10:
            return Badge.expensive(text or f"+{pct_vs_avg:.0f}%")
        elif pct_vs_avg < 0:
            return Badge.cheap(text or f"{pct_vs_avg:.0f}%")
        else:
            return Badge.fair(text or f"+{pct_vs_avg:.0f}%")

    # ── Relevancia badges ──
    @staticmethod
    def relevancia(level: str) -> str:
        lvl = (level or "").strip().lower()
        if lvl == "alta":
            return f'<span class="relevancia-alta">{level}</span>'
        elif lvl == "media":
            return f'<span class="relevancia-media">{level}</span>'
        return level


# ─────────────────────────────────────────────
# Trend / Direction Indicators
# ─────────────────────────────────────────────

class Trend:
    """Trend arrows and direction indicators."""

    @staticmethod
    def up(text: str = "") -> str:
        arrow = "&#9650;"  # ▲
        label = f" {text}" if text else ""
        return f'<span class="trend-up">{arrow}{label}</span>'

    @staticmethod
    def down(text: str = "") -> str:
        arrow = "&#9660;"  # ▼
        label = f" {text}" if text else ""
        return f'<span class="trend-down">{arrow}{label}</span>'

    @staticmethod
    def flat(text: str = "") -> str:
        arrow = "&#9654;"  # ▶
        label = f" {text}" if text else ""
        return f'<span class="trend-neutral">{arrow}{label}</span>'

    @staticmethod
    def from_direction(direction: str, text: str = "") -> str:
        """Auto-detect from keywords: RISING/HIKING/UP → up, FALLING/EASING/DOWN → down."""
        d = (direction or "").strip().upper()
        if d in ("RISING", "HIKING", "UP", "SUBIENDO", "AL ALZA"):
            return Trend.up(text)
        elif d in ("FALLING", "EASING", "DOWN", "BAJANDO", "A LA BAJA"):
            return Trend.down(text)
        return Trend.flat(text)

    @staticmethod
    def from_value(current: float, previous: float, text: str = "") -> str:
        """Determine trend from numeric comparison."""
        if current > previous * 1.001:
            return Trend.up(text)
        elif current < previous * 0.999:
            return Trend.down(text)
        return Trend.flat(text)

    # ── Portfolio arrows (triangles for allocation changes) ──
    @staticmethod
    def portfolio_arrow(direction: str) -> str:
        """Small triangle for portfolio allocation changes: ↑/↓/→ or up/down/flat."""
        d = (direction or "").strip()
        if d in ("↑", "up", "UP"):
            return '<span class="pct-change-up">&#9650;</span>'
        elif d in ("↓", "down", "DOWN"):
            return '<span class="pct-change-down">&#9660;</span>'
        return ""


# ─────────────────────────────────────────────
# Number Formatting Helpers
# ─────────────────────────────────────────────

def fmt_pct(value: Any, decimals: int = 1, with_sign: bool = False,
            color: bool = False, na: str = "N/D") -> str:
    """Format a number as percentage. Color-codes if requested."""
    if value is None or value == "N/D" or value == "":
        return na
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    sign = "+" if (with_sign and v > 0) else ""
    text = f"{sign}{v:.{decimals}f}%"
    if color:
        if v > 0:
            return f'<span class="vs-positive">{text}</span>'
        elif v < 0:
            return f'<span class="vs-negative">{text}</span>'
        return f'<span class="vs-neutral">{text}</span>'
    return text


def fmt_bps(value: Any, vs_prev: float = None, na: str = "N/D") -> str:
    """Format basis points with optional vs-previous coloring."""
    if value is None or value == "N/D":
        return na
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    text = f"{v:.0f} bps"
    if vs_prev is not None:
        sign = "+" if vs_prev > 0 else ""
        delta = f" ({sign}{vs_prev:.0f})"
        if vs_prev > 0:
            return f'{text}<span class="vs-negative">{delta}</span>'
        elif vs_prev < 0:
            return f'{text}<span class="vs-positive">{delta}</span>'
        return text
    return text


def fmt_num(value: Any, decimals: int = 2, bold: bool = False,
            color: bool = False, na: str = "N/D") -> str:
    """Format a number with optional bold and color."""
    if value is None or value == "N/D" or value == "":
        return na
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    text = f"{v:,.{decimals}f}"
    if color:
        if v > 0:
            text = f'<span class="vs-positive">{text}</span>'
        elif v < 0:
            text = f'<span class="vs-negative">{text}</span>'
    if bold:
        text = f"<strong>{text}</strong>"
    return text


def fmt_change(value: Any, decimals: int = 1, na: str = "N/D") -> str:
    """Format a change value with +/- sign and green/red coloring."""
    if value is None or value == "N/D" or value == "":
        return na
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    sign = "+" if v > 0 else ""
    text = f"{sign}{v:.{decimals}f}%"
    if v > 0:
        return f'<span style="color:#48bb78;font-weight:600">{text}</span>'
    elif v < 0:
        return f'<span style="color:#f56565;font-weight:600">{text}</span>'
    return f'<span style="color:#718096">{text}</span>'


def fmt_currency(value: Any, symbol: str = "$", decimals: int = 0, na: str = "N/D") -> str:
    """Format as currency."""
    if value is None or value == "N/D":
        return na
    try:
        v = float(value)
    except (ValueError, TypeError):
        return str(value)
    return f"{symbol}{v:,.{decimals}f}"


def fmt_small(text: str, size: str = "8pt") -> str:
    """Wrap text in small font span."""
    return f'<span style="font-size:{size};color:#718096">{text}</span>'


def fmt_bold(text: str) -> str:
    """Wrap text in strong tag."""
    return f"<strong>{text}</strong>"


# ─────────────────────────────────────────────
# Column Alignment Configuration
# ─────────────────────────────────────────────

@dataclass
class Column:
    """Column definition for TableBuilder."""
    name: str
    align: str = "left"      # left, center, right
    min_width: str = ""       # e.g. "80px"
    max_width: str = ""       # e.g. "200px"

    @staticmethod
    def left(name: str) -> 'Column':
        return Column(name=name, align="left")

    @staticmethod
    def center(name: str) -> 'Column':
        return Column(name=name, align="center")

    @staticmethod
    def right(name: str) -> 'Column':
        return Column(name=name, align="right")


# ─────────────────────────────────────────────
# TableBuilder — Main Class
# ─────────────────────────────────────────────

class TableBuilder:
    """
    Reusable HTML table builder for Greybark Research reports.

    Usage:
        tb = TableBuilder(["Mercado", Column.center("Yield"), Column.center("Spread")])
        tb.add_row(["USA", fmt_pct(4.25), fmt_bps(85)])
        tb.add_section_header("Europa")
        tb.add_row(["Alemania", fmt_pct(2.50), fmt_bps(45)])
        html = tb.render()
    """

    def __init__(self, columns: List[Union[str, Column]], css_class: str = "data-table"):
        self.columns: List[Column] = []
        for c in columns:
            if isinstance(c, str):
                self.columns.append(Column(name=c))
            else:
                self.columns.append(c)
        self.css_class = css_class
        self.rows: List[Dict] = []  # {'type': 'data'|'section', 'cells': [...], 'css': ''}

    def add_row(self, cells: List[str], row_css: str = "") -> 'TableBuilder':
        """Add a data row. Cells should be pre-formatted strings (use fmt_* helpers)."""
        self.rows.append({"type": "data", "cells": cells, "css": row_css})
        return self

    def add_section_header(self, title: str, colspan: int = 0) -> 'TableBuilder':
        """Add a section divider row spanning all columns (e.g. region headers in forecast tables)."""
        span = colspan or len(self.columns)
        self.rows.append({"type": "section", "title": title, "colspan": span})
        return self

    def add_rows_from_dicts(self, data: List[Dict], key_map: Dict[str, str],
                            formatters: Dict[str, callable] = None) -> 'TableBuilder':
        """
        Bulk add rows from list of dicts.

        key_map: {column_name: dict_key} mapping
        formatters: {column_name: callable} optional per-column formatter

        Example:
            tb.add_rows_from_dicts(
                data=earnings_data,
                key_map={"Region": "region", "EPS": "eps", "Growth": "growth"},
                formatters={"Growth": lambda v: fmt_pct(v, color=True)}
            )
        """
        formatters = formatters or {}
        for item in data:
            cells = []
            for col in self.columns:
                key = key_map.get(col.name, col.name.lower())
                raw = item.get(key, "N/D")
                if col.name in formatters:
                    cells.append(formatters[col.name](raw))
                else:
                    cells.append(str(raw) if raw is not None else "N/D")
            self.add_row(cells)
        return self

    def render(self, compact: bool = False) -> str:
        """Render the table as HTML string."""
        nl = "" if compact else "\n"
        indent = "" if compact else "  "

        parts = []
        parts.append(f'<table class="{self.css_class}">')

        # ── Header ──
        parts.append(f"{indent}<thead><tr>")
        for col in self.columns:
            style_parts = []
            if col.align != "left":
                style_parts.append(f"text-align:{col.align}")
            if col.min_width:
                style_parts.append(f"min-width:{col.min_width}")
            if col.max_width:
                style_parts.append(f"max-width:{col.max_width}")
            style = f' style="{";".join(style_parts)}"' if style_parts else ""
            parts.append(f"{indent}{indent}<th{style}>{col.name}</th>")
        parts.append(f"{indent}</tr></thead>")

        # ── Body ──
        parts.append(f"{indent}<tbody>")
        for row in self.rows:
            if row["type"] == "section":
                parts.append(
                    f'{indent}{indent}<tr class="region-header">'
                    f'<td colspan="{row["colspan"]}" '
                    f'style="background:#2d2d2d;color:white;font-weight:700;padding:8px">'
                    f'{row["title"]}</td></tr>'
                )
            else:
                css = f' class="{row["css"]}"' if row.get("css") else ""
                parts.append(f"{indent}{indent}<tr{css}>")
                for i, cell in enumerate(row["cells"]):
                    col = self.columns[i] if i < len(self.columns) else Column("")
                    style = f' style="text-align:{col.align}"' if col.align != "left" else ""
                    parts.append(f"{indent}{indent}{indent}<td{style}>{cell}</td>")
                parts.append(f"{indent}{indent}</tr>")
        parts.append(f"{indent}</tbody>")
        parts.append("</table>")

        return nl.join(parts)

    def render_rows(self) -> str:
        """
        Render ONLY the <tr> rows (no <table>, <thead>, <tbody> wrappers).
        Use this when injecting rows into existing template tables.
        """
        parts = []
        for row in self.rows:
            if row["type"] == "section":
                parts.append(
                    f'<tr class="region-header">'
                    f'<td colspan="{row["colspan"]}" '
                    f'style="background:#2d2d2d;color:white;font-weight:700;padding:8px">'
                    f'{row["title"]}</td></tr>'
                )
            else:
                css = f' class="{row["css"]}"' if row.get("css") else ""
                cells_html = ""
                for i, cell in enumerate(row["cells"]):
                    col = self.columns[i] if i < len(self.columns) else Column("")
                    style = f' style="text-align:{col.align}"' if col.align != "left" else ""
                    cells_html += f"<td{style}>{cell}</td>"
                parts.append(f"<tr{css}>{cells_html}</tr>")
        return "\n".join(parts)

    def render_empty(self, message: str = "Sin datos disponibles") -> str:
        """Render table header with a single 'no data' row."""
        self.rows = []
        self.add_row([f'<em style="color:#a0aec0">{message}</em>'] +
                     [""] * (len(self.columns) - 1))
        return self.render()


# ─────────────────────────────────────────────
# Quick Table Builders (common patterns)
# ─────────────────────────────────────────────

def quick_table(headers: List[str], rows: List[List[str]],
                center_cols: List[int] = None) -> str:
    """
    One-liner table from headers + rows.

    quick_table(
        ["País", "GDP", "Inflación"],
        [["USA", "2.5%", "3.1%"], ["Chile", "1.8%", "4.2%"]],
        center_cols=[1, 2]
    )
    """
    center_cols = set(center_cols or [])
    columns = []
    for i, h in enumerate(headers):
        if i in center_cols:
            columns.append(Column.center(h))
        else:
            columns.append(Column.left(h))

    tb = TableBuilder(columns)
    for row in rows:
        tb.add_row(row)
    return tb.render()


def indicator_table(data: List[Dict], value_key: str = "valor",
                    prev_key: str = "anterior", trend_key: str = "tendencia",
                    name_key: str = "indicador") -> str:
    """
    Standard indicator table: Indicador | Valor | Anterior | Tendencia
    Used across macro, chile, fiscal sections.
    """
    tb = TableBuilder([
        Column.left("Indicador"),
        Column.center("Valor"),
        Column.center("Anterior"),
        Column.center("Tendencia"),
    ])
    for item in data:
        name = item.get(name_key, "")
        val = item.get(value_key, "N/D")
        prev = item.get(prev_key, "N/D")
        trend = item.get(trend_key, "")
        trend_html = Trend.from_direction(trend, trend)
        tb.add_row([fmt_bold(name), str(val), str(prev), trend_html])
    return tb.render()


def view_table(data: List[Dict], name_key: str = "mercado",
               view_key: str = "view", extra_cols: List[str] = None) -> str:
    """
    Table with view badges: Mercado | View | [extra columns...]
    Used in RV summary, RF summary, AA equity/RF views.
    """
    columns = [Column.left(name_key.title()), Column.center("View")]
    extra_cols = extra_cols or []
    for ec in extra_cols:
        columns.append(Column.center(ec))

    tb = TableBuilder(columns)
    for item in data:
        name = fmt_bold(item.get(name_key, ""))
        view_str = item.get(view_key, "N")
        badge = Badge.from_view(view_str, view_str)
        cells = [name, badge]
        for ec in extra_cols:
            cells.append(str(item.get(ec.lower(), "N/D")))
        tb.add_row(cells)
    return tb.render()


def forecast_table(data: List[Dict], sections: Dict[str, List[int]] = None) -> str:
    """
    Forecast/projection table with section headers.
    Columns: Variable | Actual | 12M Fwd | Consenso | Rango | Tend.

    sections: {"Region Name": [row_indices]} for inserting section headers
    """
    tb = TableBuilder([
        Column.left("Variable"),
        Column.center("Actual"),
        Column.center("12M Fwd"),
        Column.center("Consenso"),
        Column.center("Rango"),
        Column.center("Tend."),
    ])

    if sections:
        idx = 0
        for section_name, items_in_section in sections.items():
            tb.add_section_header(section_name)
            for item in items_in_section:
                trend_html = Trend.from_direction(item.get("tendencia", ""), "")
                tb.add_row([
                    item.get("variable", ""),
                    str(item.get("actual", "N/D")),
                    str(item.get("forward", "N/D")),
                    str(item.get("consenso", "N/D")),
                    str(item.get("rango", "N/D")),
                    trend_html,
                ])
    else:
        for item in data:
            trend_html = Trend.from_direction(item.get("tendencia", ""), "")
            tb.add_row([
                item.get("variable", ""),
                str(item.get("actual", "N/D")),
                str(item.get("forward", "N/D")),
                str(item.get("consenso", "N/D")),
                str(item.get("rango", "N/D")),
                trend_html,
            ])
    return tb.render()


def scenario_table(scenarios: List[Dict]) -> str:
    """
    Scenario probability table with asset impact columns.
    Input: [{'nombre': ..., 'probabilidad': 30, 'equities': '+', 'bonds': '-', ...}]
    """
    impact_map = {
        "+": '<span style="color:#48bb78;font-weight:600">+</span>',
        "++": '<span style="color:#276749;font-weight:700">++</span>',
        "-": '<span style="color:#f56565;font-weight:600">−</span>',
        "--": '<span style="color:#c53030;font-weight:700">−−</span>',
        "flat": '<span style="color:#718096">→</span>',
        "mixed": '<span style="color:#744210">±</span>',
    }

    tb = TableBuilder([
        Column.left("Escenario"),
        Column.center("Prob."),
        Column.center("Equities"),
        Column.center("Bonds"),
        Column.center("USD"),
        Column.center("Commodities"),
    ])

    for s in scenarios:
        prob = f"{s.get('probabilidad', 0)}%"
        tb.add_row([
            fmt_bold(s.get("nombre", "")),
            f"<strong>{prob}</strong>",
            impact_map.get(s.get("equities", "flat"), s.get("equities", "")),
            impact_map.get(s.get("bonds", "flat"), s.get("bonds", "")),
            impact_map.get(s.get("usd", "flat"), s.get("usd", "")),
            impact_map.get(s.get("commodities", "flat"), s.get("commodities", "")),
        ])
    return tb.render()


def portfolio_table(profiles: List[Dict], asset_classes: List[str]) -> str:
    """
    Portfolio allocation table with arrows for changes.
    profiles: [{'name': 'Conservador', 'allocations': {'Renta Fija Local': {'pct': 40, 'change': '↑'}}}]
    """
    columns = [Column.left("Clase de Activo")]
    for p in profiles:
        columns.append(Column.center(p["name"]))

    tb = TableBuilder(columns)
    for ac in asset_classes:
        cells = [fmt_bold(ac)]
        for p in profiles:
            alloc = p.get("allocations", {}).get(ac, {})
            pct = alloc.get("pct", 0)
            change = alloc.get("change", "")
            arrow = Trend.portfolio_arrow(change)
            cells.append(f"{pct}%{' ' + arrow if arrow else ''}")
        tb.add_row(cells)
    return tb.render()


def calendar_table(events: List[Dict]) -> str:
    """
    Calendar/events table with relevancia badges.
    Input: [{'fecha': '15-Mar', 'evento': 'FOMC', 'relevancia': 'Alta', 'impacto': '...'}]
    """
    tb = TableBuilder([
        Column.left("Fecha"),
        Column.left("Evento"),
        Column.center("Relevancia"),
        Column.left("Impacto Potencial"),
    ])
    for ev in events:
        rel = Badge.relevancia(ev.get("relevancia", ""))
        tb.add_row([
            fmt_bold(ev.get("fecha", "")),
            ev.get("evento", ""),
            rel,
            fmt_small(ev.get("impacto", "")),
        ])
    return tb.render()


def commodity_table(commodities: List[Dict]) -> str:
    """
    Commodities performance table with color-coded changes.
    Input: [{'nombre': 'Cobre', 'valor': 4.25, 'unidad': 'USD/lb', '1m': 2.3, '3m': -1.5, '1y': 8.2}]
    """
    tb = TableBuilder([
        Column.left("Commodity"),
        Column.center("Valor Actual"),
        Column.center("Unidad"),
        Column.center("1M"),
        Column.center("3M"),
        Column.center("1Y"),
    ])
    for c in commodities:
        tb.add_row([
            fmt_bold(c.get("nombre", "")),
            fmt_num(c.get("valor"), decimals=2),
            fmt_small(c.get("unidad", "")),
            fmt_change(c.get("1m")),
            fmt_change(c.get("3m")),
            fmt_change(c.get("1y")),
        ])
    return tb.render()


def focus_list_table(items: List[Dict]) -> str:
    """
    Focus list / ETF picks table with view badges.
    Input: [{'ticker': 'SPY', 'instrumento': 'S&P 500 ETF', 'view': 'OW', 'rationale': '...'}]
    """
    tb = TableBuilder([
        Column.left("Ticker"),
        Column.left("Instrumento"),
        Column.center("View"),
        Column.left("Rationale"),
    ])
    for item in items:
        ticker = f'<span class="focus-ticker">{item.get("ticker", "")}</span>'
        name = f'<span class="focus-name">{item.get("instrumento", "")}</span>'
        badge = Badge.from_view(item.get("view", "N"))
        rationale = fmt_small(item.get("rationale", ""))
        tb.add_row([ticker, name, badge, rationale])
    return tb.render()


def credit_table(data: List[Dict], type_label: str = "IG") -> str:
    """
    Credit spreads table (IG or HY breakdown).
    Input: [{'rating': 'AAA', 'spread': 45, 'percentil': 25, 'señal': 'Tight'}]
    """
    tb = TableBuilder([
        Column.left("Rating"),
        Column.center("Spread (bps)"),
        Column.center("Percentil"),
        Column.center("Señal"),
    ])
    for item in data:
        spread_val = item.get("spread", "N/D")
        spread = fmt_bps(spread_val) if spread_val != "N/D" else "N/D"
        pct = item.get("percentil", "N/D")
        pct_str = f"{pct}%" if pct != "N/D" else "N/D"
        tb.add_row([
            fmt_bold(item.get("rating", "")),
            spread,
            pct_str,
            item.get("señal", "N/D"),
        ])
    return tb.render()


def yield_curve_table(data: List[Dict]) -> str:
    """
    Yield curve table: Mercado | 2Y | 5Y | 10Y | 30Y | Curva 2-10 | Vs 1M
    """
    tb = TableBuilder([
        Column.left("Mercado"),
        Column.center("2Y"),
        Column.center("5Y"),
        Column.center("10Y"),
        Column.center("30Y"),
        Column.center("Curva 2-10"),
        Column.center("Vs 1M"),
    ])
    for item in data:
        tb.add_row([
            fmt_bold(item.get("mercado", "")),
            fmt_pct(item.get("y2"), decimals=2) if item.get("y2") else "—",
            fmt_pct(item.get("y5"), decimals=2) if item.get("y5") else "—",
            fmt_pct(item.get("y10"), decimals=2) if item.get("y10") else "—",
            fmt_pct(item.get("y30"), decimals=2) if item.get("y30") else "—",
            fmt_bps(item.get("slope_2_10")),
            fmt_change(item.get("vs_1m")),
        ])
    return tb.render()


# ─────────────────────────────────────────────
# Summary / Final Tables (th/td pattern)
# ─────────────────────────────────────────────

def summary_kv_table(items: List[Dict], key_label: str = "Dimensión",
                     value_label: str = "Recomendación") -> str:
    """
    Key-value summary table (th-td pattern used at end of reports).
    Input: [{'key': 'Postura', 'value': 'Cautelosa constructiva'}]
    """
    tb = TableBuilder([Column.left(key_label), Column.left(value_label)])
    for item in items:
        tb.add_row([
            f"<th style='background:#f7f7f7;font-weight:600;padding:8px'>{item.get('key', '')}</th>",
            item.get("value", ""),
        ])
    # Custom render for th/td pattern
    parts = ['<table class="data-table">']
    for item in items:
        parts.append(f'<tr><th style="background:#f7f7f7;font-weight:600;padding:10px;'
                     f'text-align:left;width:30%">{item.get("key", "")}</th>'
                     f'<td style="padding:10px">{item.get("value", "")}</td></tr>')
    parts.append("</table>")
    return "\n".join(parts)


# ─────────────────────────────────────────────
# Row Builders (for template injection)
# ─────────────────────────────────────────────
# These produce ONLY <tr> strings for injection into
# existing <table> elements in templates.

def build_indicator_rows(data: List[Dict], name_key: str = "indicador",
                         value_key: str = "valor", prev_key: str = "anterior",
                         trend_key: str = "tendencia") -> str:
    """
    Build indicator rows: Indicador | Valor | Anterior | Tendencia
    Most common pattern in macro/chile/fiscal sections.
    """
    rows = ""
    for d in data:
        trend = d.get(trend_key, "")
        trend_html = Trend.from_direction(trend, trend) if trend else ""
        rows += (f"<tr><td>{d.get(name_key, '')}</td>"
                 f"<td style='text-align:center'>{d.get(value_key, 'N/D')}</td>"
                 f"<td style='text-align:center'>{d.get(prev_key, 'N/D')}</td>"
                 f"<td style='text-align:center'>{trend_html}</td></tr>\n")
    return rows


def build_view_rows(data: List[Dict], name_key: str = "mercado",
                    view_key: str = "view", extra_keys: List[str] = None) -> str:
    """
    Build rows with view badges: Name | View Badge | [extra columns...]
    Common in RV/RF/AA summary tables.
    """
    rows = ""
    for d in data:
        view = d.get(view_key, "N")
        badge = Badge.from_view(view, view)
        extras = ""
        for k in (extra_keys or []):
            val = d.get(k, "N/D")
            extras += f"<td style='text-align:center'>{val}</td>"
        rows += (f"<tr><td><strong>{d.get(name_key, '')}</strong></td>"
                 f"<td style='text-align:center'>{badge}</td>{extras}</tr>\n")
    return rows


def build_forecast_rows(data: List[Dict], vs_class_fn=None) -> str:
    """
    Build forecast rows: Region | Actual | Forecast | Consenso | Vs Anterior
    Used in macro forecasts (GDP, inflation, rates).

    vs_class_fn: function(vs_anterior_str) → CSS class string
    """
    rows = ""
    for f in data:
        vs = f.get("vs_anterior", "")
        css = ""
        if vs_class_fn:
            css = f' class="{vs_class_fn(vs)}"'
        elif isinstance(vs, str):
            if vs.startswith("+") or vs.startswith("↑"):
                css = ' class="vs-positive"'
            elif vs.startswith("-") or vs.startswith("↓"):
                css = ' class="vs-negative"'

        # Support both 'region'/'banco' as first column
        name = f.get("region", f.get("banco", ""))
        actual = f.get("actual_2025", f.get("actual", "N/D"))
        forecast = f.get("forecast_2026", "N/D")
        consenso = f.get("consenso", "N/D")

        rows += (f"<tr><td>{name}</td>"
                 f"<td style='text-align:center'>{actual}</td>"
                 f"<td style='text-align:center'><strong>{forecast}</strong></td>"
                 f"<td style='text-align:center'>{consenso}</td>"
                 f"<td style='text-align:center'{css}>{vs}</td></tr>\n")
    return rows


def build_calendar_rows(events: List[Dict]) -> str:
    """
    Build calendar rows: Fecha | Evento | Relevancia | Impacto
    Used in all 4 reports.
    """
    rows = ""
    for e in events:
        rel = e.get("relevancia", "")
        rel_class = "relevancia-alta" if rel == "Alta" else "relevancia-media" if rel == "Media" else ""
        css = f' class="{rel_class}"' if rel_class else ""
        impacto = e.get("impacto_potencial", e.get("impacto", ""))
        rows += (f"<tr><td>{fmt_bold(e.get('fecha', ''))}</td>"
                 f"<td>{e.get('evento', '')}</td>"
                 f"<td{css} style='text-align:center'>{rel}</td>"
                 f"<td>{impacto}</td></tr>\n")
    return rows


def build_summary_rows(items: List[Dict], key_field: str = "categoria",
                       value_field: str = "recomendacion") -> str:
    """
    Build th/td summary rows: Key (th) | Value (td)
    Used at end of RV/RF/AA reports.
    """
    rows = ""
    for s in items:
        rows += (f"<tr><th style='background:#f7f7f7;font-weight:600;"
                 f"padding:10px;text-align:left'>{s.get(key_field, '')}</th>"
                 f"<td style='padding:10px'>{s.get(value_field, '')}</td></tr>\n")
    return rows


def build_commodity_rows(commodities: List[Dict]) -> str:
    """
    Build commodity rows with color-coded changes.
    Used in macro commodities performance table.
    """
    rows = ""
    for c in commodities:
        val = c.get("actual", c.get("valor", 0))
        try:
            v = float(val)
            if v >= 1000:
                val_str = f"{v:,.0f}"
            elif v >= 10:
                val_str = f"{v:.1f}"
            else:
                val_str = f"{v:.2f}"
        except (ValueError, TypeError):
            val_str = str(val)

        rows += (f"<tr><td><strong>{c.get('nombre', '')}</strong></td>"
                 f"<td>{val_str}</td>"
                 f"<td>{fmt_small(c.get('unidad', ''))}</td>"
                 f"<td>{fmt_change(c.get('chg_1m', c.get('1m')))}</td>"
                 f"<td>{fmt_change(c.get('chg_3m', c.get('3m')))}</td>"
                 f"<td>{fmt_change(c.get('chg_1y', c.get('1y')))}</td></tr>\n")
    return rows

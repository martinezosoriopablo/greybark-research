# -*- coding: utf-8 -*-
"""
Greybark Research — Causal Tree SVG Renderer
=============================================

Renders the CIO's CAUSAL_TREE JSON as an SVG flow diagram.
Called by asset_allocation_renderer.py.

Features:
- SVG pure (no HTML tables)
- Real arrows with marker heads
- Soft palette (fill 50, stroke 600, text 800)
- Probability bars integrated in outcome nodes
- Layer labels as faint text between layers
"""

from typing import Optional, Dict, List, Tuple

# ── PALETA ────────────────────────────────────────────────────────────────────
COLORS = {
    "coral":  {"fill": "#FAECE7", "stroke": "#993C1D", "text": "#712B13"},
    "amber":  {"fill": "#FAEEDA", "stroke": "#854F0B", "text": "#633806"},
    "purple": {"fill": "#EEEDFE", "stroke": "#534AB7", "text": "#3C3489"},
    "teal":   {"fill": "#E1F5EE", "stroke": "#0F6E56", "text": "#085041"},
    "blue":   {"fill": "#E6F1FB", "stroke": "#185FA5", "text": "#0C447C"},
    "gray":   {"fill": "#F1EFE8", "stroke": "#5F5E5A", "text": "#444441"},
    "green":  {"fill": "#EAF3DE", "stroke": "#3B6D11", "text": "#27500A"},
    "red":    {"fill": "#FCEBEB", "stroke": "#A32D2D", "text": "#791F1F"},
}

SCENARIO_BAR_COLORS = {
    "green":  "#1D9E75",
    "gray":   "#B4B2A9",
    "amber":  "#BA7517",
    "red":    "#D85A30",
}

# ── LAYOUT CONSTANTS ──────────────────────────────────────────────────────────
SVG_W        = 900
NODE_H       = 44
NODE_R       = 7
ROOT_W       = 220
LAYER_W      = 170
OUTCOME_W    = 140
GAP_X        = 16
LAYER_GAP_Y  = 72
BAR_H        = 10
BAR_GAP      = 5
BAR_LABEL_W  = 72
BAR_PCT_W    = 32
FONT         = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"


def _c(color_name: str) -> dict:
    return COLORS.get(color_name, COLORS["gray"])


def _node_svg(cx: float, y: float, w: float, h: float,
              label: str, color: str) -> str:
    c = _c(color)
    x = cx - w / 2
    lines = label.split("\n")

    svg = (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" rx="{NODE_R}" '
        f'fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="0.8"/>'
    )

    if len(lines) == 1:
        text_y = y + h / 2
        svg += (
            f'<text x="{cx:.1f}" y="{text_y:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="{FONT}" '
            f'font-size="12" font-weight="600" fill="{c["text"]}">'
            f'{lines[0]}</text>'
        )
    else:
        text_y1 = y + h / 2 - 8
        text_y2 = y + h / 2 + 8
        svg += (
            f'<text x="{cx:.1f}" y="{text_y1:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="{FONT}" '
            f'font-size="12" font-weight="600" fill="{c["text"]}">{lines[0]}</text>'
            f'<text x="{cx:.1f}" y="{text_y2:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="{FONT}" '
            f'font-size="11" font-weight="400" fill="{c["text"]}" opacity="0.85">'
            f'{lines[1]}</text>'
        )
    return svg


def _arrow_svg(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="#C8C6BE" stroke-width="1.2" '
        f'marker-end="url(#ct-arrowhead)"/>'
    )


def _layer_label_svg(y: float, text: str) -> str:
    return (
        f'<text x="{SVG_W/2:.1f}" y="{y:.1f}" text-anchor="middle" '
        f'font-family="{FONT}" font-size="10" fill="#B4B2A9" '
        f'letter-spacing="0.04em">{text.upper()}</text>'
    )


def _outcome_bars_svg(cx: float, y_start: float, w: float,
                      scenarios: list) -> Tuple[str, float]:
    if not scenarios:
        return "", 0

    svg_parts = []
    y = y_start + 10
    bar_max_w = w - BAR_LABEL_W - BAR_PCT_W - 8
    x_left = cx - w / 2

    for sc in scenarios:
        prob = sc.get("prob", 0)
        bar_w = max(2, (prob / 100) * bar_max_w)
        bar_color = SCENARIO_BAR_COLORS.get(sc.get("color", "gray"), "#B4B2A9")
        label = sc.get("label", "")

        svg_parts.append(
            f'<text x="{x_left:.1f}" y="{y + BAR_H/2:.1f}" '
            f'dominant-baseline="central" font-family="{FONT}" '
            f'font-size="9.5" fill="#6B6A63">{label}</text>'
        )
        bar_x = x_left + BAR_LABEL_W
        svg_parts.append(
            f'<rect x="{bar_x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
            f'height="{BAR_H}" rx="2" fill="{bar_color}" opacity="0.88"/>'
        )
        pct_x = cx + w / 2
        svg_parts.append(
            f'<text x="{pct_x:.1f}" y="{y + BAR_H/2:.1f}" '
            f'text-anchor="end" dominant-baseline="central" '
            f'font-family="{FONT}" font-size="9.5" fill="#6B6A63">'
            f'{prob:.0f}%</text>'
        )
        y += BAR_H + BAR_GAP

    total_h = len(scenarios) * (BAR_H + BAR_GAP) + 10
    return "\n".join(svg_parts), total_h


def _layout(tree: dict) -> dict:
    pos = {}

    root = tree["root"]
    pos["root"] = {
        "cx": SVG_W / 2, "y": 24,
        "w": ROOT_W, "h": NODE_H,
        "label": root["label"],
        "color": root.get("color", "coral"),
    }

    y_cursor = 24 + NODE_H + LAYER_GAP_Y

    for layer in tree.get("layers", []):
        nodes = layer["nodes"]
        n = len(nodes)
        total_w = n * LAYER_W + (n - 1) * GAP_X
        start_cx = SVG_W / 2 - total_w / 2 + LAYER_W / 2

        for i, node in enumerate(nodes):
            cx = start_cx + i * (LAYER_W + GAP_X)
            pos[node["id"]] = {
                "cx": cx, "y": y_cursor,
                "w": LAYER_W, "h": NODE_H,
                "label": node["label"],
                "color": node.get("color", "amber"),
                "parent_ids": node.get("parent_ids", []),
                "layer_id": layer["id"],
            }

        y_cursor += NODE_H + LAYER_GAP_Y

    outcomes = tree.get("outcomes", [])
    n = len(outcomes)
    total_w = n * OUTCOME_W + (n - 1) * GAP_X
    start_cx = SVG_W / 2 - total_w / 2 + OUTCOME_W / 2

    for i, out in enumerate(outcomes):
        cx = start_cx + i * (OUTCOME_W + GAP_X)
        pos[out["id"]] = {
            "cx": cx, "y": y_cursor,
            "w": OUTCOME_W, "h": NODE_H,
            "label": out["label"],
            "color": out.get("color", "teal"),
            "parent_ids": out.get("parent_ids", []),
            "scenarios": out.get("scenarios", []),
            "is_outcome": True,
        }

    return pos


def render_causal_tree_html(tree: dict) -> str:
    """Generate self-contained HTML with SVG causal tree diagram."""
    if not tree:
        return ""

    pos = _layout(tree)
    title = tree.get("title", "Árbol Causal del Escenario Dominante")

    max_y = 0
    for nid, p in pos.items():
        bottom = p["y"] + p["h"]
        if p.get("scenarios"):
            bottom += len(p["scenarios"]) * (BAR_H + BAR_GAP) + 20
        max_y = max(max_y, bottom)
    svg_h = max_y + 32

    parts = []

    parts.append(f'''<svg width="100%" viewBox="0 0 {SVG_W} {svg_h:.0f}"
 xmlns="http://www.w3.org/2000/svg" style="display:block;overflow:visible">
<defs>
  <marker id="ct-arrowhead" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="7" markerHeight="7" orient="auto-start-reverse">
    <path d="M2 2 L8 5 L2 8" fill="none" stroke="#C8C6BE"
          stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>''')

    # Layer labels
    seen_layers = {}
    for nid, p in pos.items():
        if nid == "root" or p.get("is_outcome"):
            continue
        lid = p.get("layer_id", "")
        if lid and lid not in seen_layers:
            label_y = p["y"] - LAYER_GAP_Y / 2 + 6
            layer_data = next((l for l in tree.get("layers", [])
                               if l["id"] == lid), {})
            layer_label = layer_data.get("label", lid)
            parts.append(_layer_label_svg(label_y, layer_label))
            seen_layers[lid] = True

    # Outcomes label
    if any(p.get("is_outcome") for p in pos.values()):
        out_nodes = [p for p in pos.values() if p.get("is_outcome")]
        if out_nodes:
            first_out_y = min(p["y"] for p in out_nodes)
            parts.append(_layer_label_svg(
                first_out_y - LAYER_GAP_Y / 2 + 6,
                "Distribución por activo"
            ))

    # Arrows (drawn before nodes to stay behind)
    for nid, p in pos.items():
        if nid == "root":
            continue
        for pid in p.get("parent_ids", []):
            if pid not in pos:
                continue
            src = pos[pid]
            parts.append(_arrow_svg(src["cx"], src["y"] + src["h"],
                                    p["cx"], p["y"]))

    # Nodes
    for nid, p in pos.items():
        parts.append(_node_svg(
            cx=p["cx"], y=p["y"], w=p["w"], h=p["h"],
            label=p["label"], color=p["color"],
        ))

    # Outcome bars
    for nid, p in pos.items():
        if p.get("is_outcome") and p.get("scenarios"):
            bars_svg, _ = _outcome_bars_svg(
                cx=p["cx"], y_start=p["y"] + p["h"],
                w=p["w"], scenarios=p["scenarios"],
            )
            parts.append(bars_svg)

    parts.append("</svg>")

    svg_content = "\n".join(parts)

    html = f'''
<div style="
    margin: 28px 0 32px;
    padding: 0;
    border-left: 3px solid #1D9E75;
    padding-left: 0;
    page-break-inside: avoid;
">
  <div style="
      padding: 20px 24px 0;
      background: #FAFAF8;
      border: 0.5px solid #D3D1C7;
      border-radius: 8px;
      border-left: none;
  ">
    <div style="
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 20px;
    ">
      <div>
        <p style="
            font-size: 10px;
            color: #9C9A92;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin: 0 0 3px;
            font-family: {FONT};
        ">AI Council — Escenario dominante</p>
        <h3 style="
            font-size: 14px;
            font-weight: 600;
            color: #1A2332;
            margin: 0;
            font-family: {FONT};
        ">{title}</h3>
      </div>
      <span style="
          font-size: 10px;
          color: #B4B2A9;
          background: #EDEBE3;
          padding: 3px 9px;
          border-radius: 4px;
          font-family: {FONT};
          white-space: nowrap;
      ">CIO Agent · Asset Allocation</span>
    </div>

    <div style="overflow-x: auto; padding-bottom: 20px;">
      {svg_content}
    </div>

  </div>
</div>
'''
    return html

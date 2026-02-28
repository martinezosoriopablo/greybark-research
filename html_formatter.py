# -*- coding: utf-8 -*-

# Proteccion de encoding para Windows (evita errores con emojis)
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

from pathlib import Path
from datetime import datetime
import re

# INTENTAMOS IMPORTAR PDFKIT
try:
    import pdfkit
    # ==============================================================================
    # CONFIGURACIÓN IMPORTANTE PARA PDF
    # Si instalaste wkhtmltopdf en otra ruta, cámbiala aquí:
    # ==============================================================================
    PATH_WKHTMLTOPDF = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    
    # Verificamos si existe el ejecutable
    if Path(PATH_WKHTMLTOPDF).exists():
        PDF_CONFIG = pdfkit.configuration(wkhtmltopdf=PATH_WKHTMLTOPDF)
        HAS_PDFKIT = True
    else:
        print(f"[AVISO] No se encontró wkhtmltopdf en: {PATH_WKHTMLTOPDF}")
        print("        El PDF no se generará, solo el HTML.")
        HAS_PDFKIT = False
except ImportError:
    HAS_PDFKIT = False
    print("[AVISO] Instala 'pip install pdfkit' para generar PDFs.")

try:
    import markdown
except ImportError:
    markdown = None

INPUT_DIR = Path(".")
OUTPUT_DIR = Path("html_out")
OUTPUT_DIR.mkdir(exist_ok=True)

# Paleta Greybark Research (unificada con reportes mensuales)
PRIMARY_BLACK = "#1a1a1a"
ACCENT_ORANGE = "#dd6b20"
GREEN_TEXT = "#276749"
RED_TEXT = "#c53030"
TEXT_MEDIUM = "#4a4a4a"
TEXT_LIGHT = "#717171"
BG_EVEN = "#f7f7f7"
BORDER_COLOR = "#e0e0e0"
WHITE = "#ffffff"

# Plantilla Greybark Research (unificada con reportes mensuales)
HTML_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="es">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style type="text/css">
    body {{ margin: 0; padding: 0; -webkit-text-size-adjust: 100%; font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; color: #4a4a4a; }}
    table {{ border-collapse: collapse; }}
    @media print {{
        div, table, tr, td, th {{
            page-break-inside: avoid !important;
        }}
        body {{ background-color: #ffffff !important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background-color:#ffffff;">
  <div style="width:100%; max-width:1000px; margin:0 auto; background-color:#ffffff;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#ffffff;">
      <tr>
        <td style="padding:20px 40px;">

          <!-- HEADER -->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-bottom:3px solid #1a1a1a; padding-bottom:15px; margin-bottom:25px;">
            <tr>
              <td valign="bottom">
                <div style="font-family:'Arial Black','Segoe UI',sans-serif; font-size:20pt; font-weight:900; color:#1a1a1a; text-transform:uppercase; letter-spacing:1px; line-height:1.1;">
                  GREYBARK RESEARCH
                </div>
                <div style="font-size:12pt; color:#dd6b20; font-weight:500; margin-top:2px;">
                  Reporte Diario de Mercados
                  <span style="display:inline-block; padding:3px 10px; border-radius:4px; font-size:10px; font-weight:900; text-transform:uppercase; margin-left:8px; {badge_style}">
                    {report_type}
                  </span>
                </div>
              </td>
              <td valign="bottom" style="text-align:right;">
                <div style="font-size:11pt; font-weight:600; color:#1a1a1a;">{date_str}</div>
                <div style="font-size:9pt; color:#717171;">Perspectivas de Mercado</div>
              </td>
            </tr>
          </table>

          <!-- CONTENT -->
          <div style="font-size:10pt; line-height:1.6; color:#4a4a4a;">
            {content_html}
          </div>

          <!-- FOOTER -->
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:40px; border-top:2px solid #1a1a1a; padding-top:15px;">
            <tr>
              <td style="text-align:center; font-size:8pt; color:#717171;">
                <div>GREYBARK RESEARCH | Reporte Diario | {date_str}</div>
                <div style="margin-top:10px; padding:10px; background:#f7f7f7; border-radius:5px; font-size:7pt; line-height:1.4;">
                  Este documento es solo para fines informativos y no constituye una recomendacion de inversion.
                  Las proyecciones y estimaciones contenidas en este reporte estan basadas en supuestos que pueden no materializarse.
                  El desempeno pasado no garantiza resultados futuros. Consulte a su asesor financiero antes de tomar decisiones de inversion.
                </div>
              </td>
            </tr>
          </table>

        </td>
      </tr>
    </table>
  </div>
</body>
</html>
"""

def detect_report_type_from_name(name: str) -> str:
    lower = name.lower()
    if "weekly" in lower or "semanal" in lower or "semana_" in lower: return "SEMANAL"
    if "_am" in lower or " am" in lower: return "AM"
    if "_pm" in lower or " pm" in lower: return "PM"
    return "General"

def format_date_from_stem(stem: str) -> str:
    try:
        parts = stem.split('_')
        date_str = parts[-1]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        date_obj = datetime.now()

    date_formatted = date_obj.strftime("%d de %B de %Y")
    meses = {'January':'enero','February':'febrero','March':'marzo','April':'abril','May':'mayo','June':'junio','July':'julio','August':'agosto','September':'septiembre','October':'octubre','November':'noviembre','December':'diciembre'}
    for eng, esp in meses.items():
        date_formatted = date_formatted.replace(eng, esp)
    return date_formatted

# ==========================================
# FUNCIONES DE TABLA 
# ==========================================
# (Se mantienen iguales para asegurar el estilo inline)

def convert_dashboard_to_html(lines):
    s_table = f"width:100%; margin:14px 0; background:{WHITE}; border:1px solid {BORDER_COLOR}; border-radius:8px; border-collapse:separate; border-spacing:0; overflow:hidden; page-break-inside:avoid;"
    s_td_base = f"padding:9px 8px; text-align:center; font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; line-height:1.15; border-bottom:1px solid {BORDER_COLOR};"
    s_header = f"background:{PRIMARY_BLACK}; color:{WHITE}; font-size:9pt; font-weight:700; text-transform:uppercase;"
    s_val = f"background:{WHITE}; color:{TEXT_MEDIUM}; font-size:9pt; font-weight:600;"

    html_parts = [f'<table style="{s_table}" cellpadding="0" cellspacing="0" border="0">']
    data_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('=') and 'DASHBOARD' not in l.upper()]

    if len(data_lines) >= 3:
        headers = [h.strip() for h in data_lines[0].split() if h.strip()]
        changes = [c.strip() for c in data_lines[1].split() if c.strip()]
        values  = [v.strip() for v in data_lines[2].split() if v.strip()]

        html_parts.append('<tr>' + ''.join(f'<td style="{s_td_base} {s_header}">{h}</td>' for h in headers[:6]) + '</tr>')

        row_cells = []
        for c in changes[:6]:
            color = PRIMARY_BLACK
            if '%' in c:
                if '+' in c: color = GREEN_TEXT
                elif '-' in c: color = RED_TEXT
            s_change = f"background:{WHITE}; color:{color}; font-size:12pt; font-weight:900;"
            row_cells.append(f'<td style="{s_td_base} {s_change}">{c}</td>')
        html_parts.append('<tr>' + ''.join(row_cells) + '</tr>')
        html_parts.append('<tr>' + ''.join(f'<td style="{s_td_base} {s_val}">{v}</td>' for v in values[:6]) + '</tr>')

    html_parts.append('</table>')
    return "\n".join(html_parts)

_SPLIT_COLS = re.compile(r"\s{2,}")
def split_cols(line: str):
    s = line.strip()
    if not s or s.startswith('=') or s.startswith('-') or s.startswith('Nota:'): return []
    return [p.strip() for p in _SPLIT_COLS.split(s) if p.strip()]

def normalize_row(parts, expected_cols: int):
    if expected_cols <= 0: return parts
    if len(parts) == expected_cols: return parts
    if len(parts) < expected_cols: return parts + [""] * (expected_cols - len(parts))
    overflow = len(parts) - expected_cols
    return [" ".join(parts[:overflow+1])] + parts[overflow+1:]

_HEADER_FIRST_COLS = {"ÍNDICE", "INDICE", "INSTRUMENTO", "COMMODITY", "PAR", "SECTOR"}
def is_header_line(s: str) -> bool:
    parts = split_cols(s)
    if not parts: return False
    return parts[0].strip().upper() in _HEADER_FIRST_COLS

def infer_block_cols(lines, default_cols=5) -> int:
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith('=') or s.startswith('-') or s.startswith('Nota:'): continue
        if is_header_line(s):
            parts = split_cols(s)
            if parts: return len(parts)
    return default_cols

def convert_market_table_to_html(lines):
    s_table = f"width:100%; margin:14px 0; font-family:'Segoe UI','Helvetica Neue',Arial,sans-serif; font-size:9pt; border:1px solid {BORDER_COLOR}; border-radius:8px; border-collapse:separate; border-spacing:0; overflow:hidden; page-break-inside:avoid;"
    s_th = f"background:{PRIMARY_BLACK}; color:{WHITE}; padding:10px 8px; font-weight:700; font-size:9pt; border-bottom:1px solid {PRIMARY_BLACK}; white-space:nowrap;"
    s_td = f"padding:8px 8px; border-bottom:1px solid {BORDER_COLOR}; font-size:9pt; color:{PRIMARY_BLACK}; white-space:nowrap;"
    s_section = f"background:{PRIMARY_BLACK}; color:{WHITE}; text-align:center; font-weight:700; padding:10px; text-transform:uppercase; letter-spacing:0.45px; font-size:9pt; border-bottom:0;"
    s_sub = f"background:{PRIMARY_BLACK}; color:{WHITE}; font-weight:700; font-size:9pt; padding:9px 10px;"

    html_parts = [f'<table style="{s_table}" cellpadding="0" cellspacing="0">']

    current_cols = infer_block_cols(lines, default_cols=5)
    expected_cols = 0; header_seen = False; row_count = 0

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith('=') or s.startswith('-') or s.startswith('Nota:'): continue
        up = s.upper()

        vix_parts = []
        if 'VIX' in up and ('(' in up or 'VOLATILIDAD' in up):
             m = re.match(r'^(VIX.*?\))\s*([0-9\.]+)\s*([+\-0-9\.]+%)\s*([+\-0-9\.]+%)\s*$', s, re.IGNORECASE)
             if m: vix_parts = [m.group(1), m.group(2), m.group(3), m.group(4)]

        if not vix_parts and any(k in up for k in ['ÍNDICES', 'INDICES', 'RENTA FIJA', 'VOLATILIDAD', 'COMMODITIES', 'DIVISAS', 'SENTIMENT']):
            expected_cols = 0; header_seen = False
            html_parts.append(f'<tr><td colspan="{current_cols}" style="{s_section}">{s}</td></tr>')
            continue

        if s == 'CHILE':
            expected_cols = 0; header_seen = False
            html_parts.append(f'<tr><td colspan="{current_cols}" style="{s_sub} text-align:left; padding-left:12px;">CHILE</td></tr>')            
            continue

        if is_header_line(s):
            parts = split_cols(s)
            if parts:
                expected_cols = len(parts); header_seen = True; current_cols = expected_cols
                th_cells = []
                for i, p in enumerate(parts):
                    align = "left" if i == 0 else "right"
                    th_cells.append(f'<th style="{s_th} text-align: {align};">{p}</th>')
                html_parts.append('<tr>' + ''.join(th_cells) + '</tr>')
            continue

        parts = vix_parts if vix_parts else split_cols(s)
        if not parts: continue
        if header_seen and expected_cols and not vix_parts: parts = normalize_row(parts, expected_cols)

        bg_color = WHITE if row_count % 2 == 0 else BG_EVEN
        row_count += 1

        tds = []
        for i, p in enumerate(parts):
            color_style = ""
            if ('%' in p or 'bp' in p) and ('+' in p or '-' in p):
                color_style = f"color: {GREEN_TEXT}; font-weight: 900;" if '+' in p else f"color: {RED_TEXT}; font-weight: 900;"
            align = "right" if i > 0 else "left"
            weight = "font-weight: 800;" if (i == 0 or vix_parts) else ""
            tds.append(f'<td style="{s_td} background-color: {bg_color}; text-align: {align}; {color_style} {weight}">{p}</td>')
            
        html_parts.append('<tr>' + ''.join(tds) + '</tr>')

    html_parts.append('</table>')
    return "\n".join(html_parts)

def process_markdown_content(text):
    lines = text.split("\n"); result = []
    
    def is_eq_line(s): return len(s.strip()) >= 10 and all(ch == '=' for ch in s.strip())
    def classify_block(bl): 
        up = "\n".join(bl).upper()
        if "DASHBOARD DIARIO" in up: return "dashboard"
        if any(k in up for k in ["ÍNDICES", "RENTA FIJA", "COMMODITIES", "DIVISAS", "SENTIMENT"]): return "market"
        return None

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            i += 1; block = []
            while i < len(lines) and not lines[i].strip().startswith("```"): block.append(lines[i]); i += 1
            kind = classify_block(block)
            if kind == "dashboard": result.append(convert_dashboard_to_html(block))
            elif kind == "market": result.append(convert_market_table_to_html(block))
            else: result.append("```\n" + "\n".join(block) + "\n```")
            if i < len(lines) and lines[i].strip().startswith("```"): i += 1
            continue

        if is_eq_line(line):
            block = [line]; i += 1
            while i < len(lines):
                curr = lines[i]; block.append(curr)
                if is_eq_line(curr):
                    possible_sandwich = False
                    if len(block) <= 4 and i + 1 < len(lines):
                        nxt = lines[i+1].strip()
                        if nxt and not is_eq_line(nxt): possible_sandwich = True
                    if possible_sandwich: i += 1; continue
                    else: i += 1; break
                i += 1
            kind = classify_block(block)
            if kind == "dashboard": result.append(convert_dashboard_to_html(block))
            elif kind == "market": result.append(convert_market_table_to_html(block))
            else: result.extend(block)
            continue

        if re.match(r'^\s*#*\s*INFORME\s+DIARIO\b', line, flags=re.IGNORECASE): i += 1; continue
        result.append(line); i += 1
    return "\n".join(result)

def apply_inline_styles(html):
    """Inyecta estilos Greybark en tags generados por markdown.markdown()."""
    # h2 — section title: 14pt, orange bottom border
    html = re.sub(
        r'<h2>(.*?)</h2>',
        r'<h2 style="font-size:14pt; font-weight:700; color:#1a1a1a; border-bottom:2px solid #dd6b20; padding-bottom:8px; margin:25px 0 15px 0;">\1</h2>',
        html
    )
    # h3 — subsection: 11pt, orange left border
    html = re.sub(
        r'<h3>(.*?)</h3>',
        r'<h3 style="font-size:11pt; font-weight:600; color:#3a3a3a; margin:15px 0 10px 0; padding-left:10px; border-left:3px solid #dd6b20;">\1</h3>',
        html
    )
    # h1 — keep large for report title
    html = re.sub(
        r'<h1>(.*?)</h1>',
        r'<h1 style="font-size:16pt; font-weight:700; color:#1a1a1a; margin:20px 0 10px 0;">\1</h1>',
        html
    )
    # p — body text
    html = re.sub(
        r'<p>',
        '<p style="font-size:10pt; color:#4a4a4a; line-height:1.6; margin:8px 0;">',
        html
    )
    # li — list items
    html = re.sub(
        r'<li>',
        '<li style="font-size:10pt; color:#4a4a4a; margin-bottom:5px;">',
        html
    )
    # strong — bold in primary black
    html = re.sub(
        r'<strong>',
        '<strong style="color:#1a1a1a;">',
        html
    )
    # Resumen Ejecutivo — wrap in orange-bordered box
    html = re.sub(
        r'(<h2[^>]*>.*?Resumen Ejecutivo.*?</h2>)(.*?)(?=<h2|$)',
        lambda m: m.group(1) + '<div style="background:#f7f7f7; border-left:4px solid #dd6b20; padding:15px; border-radius:5px; margin-bottom:20px;">' + m.group(2) + '</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    return html


def build_files(md_path: Path):
    text = md_path.read_text(encoding="utf-8", errors="replace")
    title = "Reporte de Mercados"
    for line in text.splitlines():
        if line.startswith("# "): title = line.replace("#", "").strip(); break

    report_type = detect_report_type_from_name(md_path.stem)
    if report_type == "AM":
        badge_style = f"background-color:{ACCENT_ORANGE}; color:{WHITE};"
    elif report_type == "PM":
        badge_style = f"background-color:{PRIMARY_BLACK}; color:{WHITE};"
    elif report_type == "SEMANAL":
        badge_style = f"background-color:{GREEN_TEXT}; color:{WHITE};"
    else:
        badge_style = f"background-color:{TEXT_LIGHT}; color:{WHITE};"

    processed = process_markdown_content(text)
    if markdown:
        content_html = markdown.markdown(processed, extensions=["extra", "nl2br", "sane_lists"])
    else:
        content_html = processed.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

    content_html = apply_inline_styles(content_html)

    final_html = HTML_TEMPLATE.format(
        title=title, date_str=format_date_from_stem(md_path.stem),
        report_type=report_type, badge_style=badge_style, content_html=content_html
    )

    # 1. Guardar HTML
    out_html = OUTPUT_DIR / (md_path.stem + ".html")
    out_html.write_text(final_html, encoding="utf-8", errors="replace")
    print(f"[OK] HTML generado: {out_html.name}")

    # 2. Generar PDF (Si está configurado)
    if HAS_PDFKIT:
        out_pdf = OUTPUT_DIR / (md_path.stem + ".pdf")
        options = {
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'no-outline': None
        }
        try:
            pdfkit.from_string(final_html, str(out_pdf), configuration=PDF_CONFIG, options=options)
            print(f"[OK] PDF generado:  {out_pdf.name}")
        except Exception as e:
            print(f"[ERROR] Falló PDF: {e}")

def main():
    # Buscar reportes diarios Y semanales
    daily_files = sorted(INPUT_DIR.glob("daily_report_*.md"))
    weekly_files = sorted(INPUT_DIR.glob("weekly_report_*.md"))
    md_files = daily_files + weekly_files

    if not md_files:
        print("[WARN] No se encontraron archivos .md (daily_report_*.md o weekly_report_*.md)")
        return

    print(f"[INFO] Procesando {len(md_files)} archivos...")
    print(f"       - Diarios: {len(daily_files)}")
    print(f"       - Semanales: {len(weekly_files)}\n")

    for md in md_files:
        try:
            build_files(md)
        except Exception as e:
            print(f"[ERROR] {md.name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n[OK] Revisa la carpeta: {OUTPUT_DIR}/")

if __name__ == "__main__":
    main()
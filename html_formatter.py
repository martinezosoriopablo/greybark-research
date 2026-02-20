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

LOGO_URL = "https://i.imgur.com/kYvSADf.png"

# Colores globales
BLACK_BAR = "#0b1220"
WHITE_ON_BLACK = "#ffffff"
GREEN_TEXT = "#059669"
RED_TEXT = "#dc2626"
GRAY_TEXT = "#374151"
BG_ODD = "#ffffff"
BG_EVEN = "#fbfdff"

# Plantilla con CSS extra para impresión (PDF)
HTML_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="es">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style type="text/css">
    body {{ margin: 0; padding: 0; -webkit-text-size-adjust: 100%; font-family: sans-serif; }}
    table {{ border-collapse: collapse; }}
    
    /* ESTILOS ESPECÍFICOS PARA PDF / IMPRESIÓN */
    @media print {{
        div, table, tr, td, th {{
            page-break-inside: avoid !important; /* Evita cortar tablas a la mitad */
        }}
        body {{ 
            background-color: #ffffff !important; 
        }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background-color:#f3f4f6;">
  <div style="width: 100%; max-width: 800px; margin: 0 auto; background-color: #ffffff;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#ffffff;">
        <tr>
          <td align="center" style="padding:20px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-radius:12px; overflow:hidden;">
              
              <tr>
                <td style="background-color:#000000; padding:22px 26px;">
                  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                      <td valign="middle" width="110">
                        <img src="{logo_url}" alt="Grey Bark Advisors" width="84" height="84" style="display:block; width:84px; height:auto;" />
                      </td>
                      <td valign="middle" style="padding-left:16px;">
                        <div style="color:#ffffff; font-size:26px; font-weight:900; line-height:1.15;">
                          Reporte de Mercados
                        </div>
                        <div style="color:#d1d5db; font-size:14px; margin-top:8px;">
                          {date_str}
                          <span style="display:inline-block; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:900; text-transform:uppercase; margin-left:8px; {badge_style}">
                            {report_type}
                          </span>
                        </div>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>

              <tr>
                <td style="padding:26px; font-size:14px; line-height:1.6; color:#111827;">
                  {content_html}
                </td>
              </tr>

              <tr>
                <td style="background-color:#f9fafb; padding:18px 26px; border-top:1px solid #e5e7eb;">
                  <div style="text-align:center; color:#6b7280; font-size:12px;">
                    <strong style="color:#111827;">Grey Bark Advisors</strong> • Reporte Automatizado<br/>
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
    s_table = "width: 100%; margin: 14px 0; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; border-collapse: separate; border-spacing: 0; overflow: hidden; page-break-inside: avoid;"
    s_td_base = "padding: 9px 8px; text-align: center; font-family: sans-serif; line-height: 1.15; border-bottom: 1px solid #eef2f7;"
    s_header = f"background: {BLACK_BAR}; color: {WHITE_ON_BLACK}; font-size: 14px; font-weight: 900; text-transform: uppercase; text-align: left; padding-left: 12px;"
    s_val = f"background: #ffffff; color: {GRAY_TEXT}; font-size: 11px; font-weight: 600;"

    html_parts = [f'<table style="{s_table}" cellpadding="0" cellspacing="0" border="0">']
    data_lines = [l.strip() for l in lines if l.strip() and not l.strip().startswith('=') and 'DASHBOARD' not in l.upper()]

    if len(data_lines) >= 3:
        headers = [h.strip() for h in data_lines[0].split() if h.strip()]
        changes = [c.strip() for c in data_lines[1].split() if c.strip()]
        values  = [v.strip() for v in data_lines[2].split() if v.strip()]

        html_parts.append('<tr>' + ''.join(f'<td style="{s_td_base} {s_header}">{h}</td>' for h in headers[:5]) + '</tr>')
        
        row_cells = []
        for c in changes[:5]:
            color = "#111827"
            if '%' in c:
                if '+' in c: color = GREEN_TEXT
                elif '-' in c: color = RED_TEXT
            s_change = f"background: #ffffff; color: {color}; font-size: 14px; font-weight: 900;"
            row_cells.append(f'<td style="{s_td_base} {s_change}">{c}</td>')
        html_parts.append('<tr>' + ''.join(row_cells) + '</tr>')
        html_parts.append('<tr>' + ''.join(f'<td style="{s_td_base} {s_val}">{v}</td>' for v in values[:5]) + '</tr>')

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
    # Agregamos page-break-inside: avoid para el PDF
    s_table = "width: 100%; margin: 14px 0; font-family: sans-serif; font-size: 11px; border: 1px solid #e5e7eb; border-radius: 12px; border-collapse: separate; border-spacing: 0; overflow: hidden; page-break-inside: avoid;"
    s_th = f"background: {BLACK_BAR}; color: {WHITE_ON_BLACK}; padding: 9px 10px; font-weight: 900; font-size: 11px; border-bottom: 1px solid #111827; white-space: nowrap;"
    s_td = "padding: 8px 10px; border-bottom: 1px solid #eef2f7; font-size: 11px; color: #111827; white-space: nowrap;"
    s_section = f"background: {BLACK_BAR}; color: {WHITE_ON_BLACK}; text-align: center; font-weight: 900; padding: 10px; text-transform: uppercase; letter-spacing: 0.45px; font-size: 11px; border-bottom: 0;"
    s_sub = f"background: {BLACK_BAR}; color: {WHITE_ON_BLACK}; font-weight: 900; font-size: 11px; padding: 9px 10px;"

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

        bg_color = BG_ODD if row_count % 2 == 0 else BG_EVEN
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

def build_files(md_path: Path):
    text = md_path.read_text(encoding="utf-8", errors="replace")
    title = "Reporte de Mercados"
    for line in text.splitlines():
        if line.startswith("# "): title = line.replace("#", "").strip(); break

    report_type = detect_report_type_from_name(md_path.stem)
    if report_type == "AM":
        badge_style = "background-color:#facc15; color:#000000;"
    elif report_type == "PM":
        badge_style = "background-color:#2563eb; color:#ffffff;"
    elif report_type == "SEMANAL":
        badge_style = "background-color:#059669; color:#ffffff;"  # Verde para semanal
    else:
        badge_style = "background-color:#6b7280; color:#ffffff;"

    processed = process_markdown_content(text)
    if markdown:
        content_html = markdown.markdown(processed, extensions=["extra", "nl2br", "sane_lists"])
    else:
        content_html = processed.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")

    final_html = HTML_TEMPLATE.format(
        title=title, logo_url=LOGO_URL, date_str=format_date_from_stem(md_path.stem),
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
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
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
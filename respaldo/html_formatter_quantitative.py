"""
HTML FORMATTER - QUANTITATIVE WEEKLY REPORT
Convierte el reporte cuantitativo markdown a HTML optimizado para email
"""

import base64
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import markdown
except ImportError:
    markdown = None
    print("[WARN] Paquete 'markdown' no encontrado")
    print("       Instala con: pip install markdown")

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

OUTPUT_DIR = Path("html_out")
OUTPUT_DIR.mkdir(exist_ok=True)

# Logo
LOGO_URL = "https://i.imgur.com/kYvSADf.png"
USE_LOGO_URL = True

# ============================================================================
# TEMPLATE HTML PARA REPORTE CUANTITATIVO
# ============================================================================

HTML_TEMPLATE = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="es">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>{title}</title>
    <style type="text/css">
        body {{
            margin: 0 !important;
            padding: 0 !important;
            -webkit-text-size-adjust: 100% !important;
            -ms-text-size-adjust: 100% !important;
            -webkit-font-smoothing: antialiased !important;
        }}
        img {{
            border: 0 !important;
            outline: none !important;
        }}
        table {{
            border-collapse: collapse !important;
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #f3f4f6;">
    
    <!-- Main container -->
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: #f3f4f6;">
        <tr>
            <td align="center" style="padding: 20px 10px;">
                
                <!-- Content table -->
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="800" style="max-width: 800px; background-color: #ffffff; border-radius: 8px;">
                    
                    <!-- Header -->
                    <tr>
                        <td style="background-color: #000000; padding: 30px 40px;">
                            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                                <tr>
                                    <td valign="middle" width="100">
                                        {logo_html}
                                    </td>
                                    <td valign="middle" style="padding-left: 25px;">
                                        <div style="color: #ffffff; font-size: 32px; font-weight: bold; line-height: 1.2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; letter-spacing: -0.5px;">
                                            Reporte Cuantitativo Semanal
                                        </div>
                                        <div style="color: #d1d5db; font-size: 16px; margin-top: 10px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                                            {date_str}
                                            <span style="display: inline-block; padding: 5px 12px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; margin-left: 10px; background-color: #10b981; color: #ffffff;">
                                                SEMANAL
                                            </span>
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #111827;">
                            {content}
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 25px 40px; text-align: center; font-size: 12px; color: #6b7280; border-top: 1px solid #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
                            <p style="margin: 0 0 10px 0; font-weight: 600;">Grey Bark Advisors - Research Quantitative Team</p>
                            <p style="margin: 0 0 8px 0;">Reporte generado automaticamente el {generated_at}</p>
                            <p style="margin: 0; font-size: 11px; line-height: 1.5; color: #9ca3af;">
                                Este documento contiene analisis cuantitativo con fines informativos unicamente.
                                No constituye asesoria de inversion ni recomendacion especifica de compra o venta de activos.
                                Los datos pasados no garantizan resultados futuros.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>"""


# ============================================================================
# FUNCIONES
# ============================================================================

def md_to_html_content(md_text: str) -> str:
    """Convierte markdown a HTML con estilos inline optimizados para tablas"""
    
    if markdown is not None:
        html = markdown.markdown(md_text, extensions=["extra", "tables"])
    else:
        paragraphs = [p.strip() for p in md_text.split("\n\n") if p.strip()]
        html = "".join("<p>" + p.replace("\n", "<br>") + "</p>" for p in paragraphs)
    
    # Estilos para headers
    html = html.replace('<h1>', '<h1 style="color: #1e3a8a; font-size: 28px; font-weight: bold; margin: 30px 0 15px 0; padding-bottom: 10px; border-bottom: 3px solid #3b82f6;">')
    html = html.replace('<h2>', '<h2 style="color: #1e40af; font-size: 22px; font-weight: bold; margin: 25px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid #60a5fa;">')
    html = html.replace('<h3>', '<h3 style="color: #1e40af; font-size: 18px; font-weight: bold; margin: 20px 0 10px 0; padding-bottom: 6px; border-bottom: 1px solid #93c5fd;">')
    html = html.replace('<h4>', '<h4 style="color: #3b82f6; font-size: 16px; font-weight: bold; margin: 16px 0 8px 0;">')
    
    # Estilos para párrafos
    html = html.replace('<p>', '<p style="margin: 0 0 14px 0; color: #111827; font-size: 15px; line-height: 1.7;">')
    
    # Estilos para listas
    html = html.replace('<ul>', '<ul style="margin: 0 0 16px 0; padding-left: 25px;">')
    html = html.replace('<ol>', '<ol style="margin: 0 0 16px 0; padding-left: 25px;">')
    html = html.replace('<li>', '<li style="margin: 0 0 8px 0; color: #111827; line-height: 1.7;">')
    
    # Estilos para énfasis
    html = html.replace('<strong>', '<strong style="color: #1e40af; font-weight: 700;">')
    html = html.replace('<em>', '<em style="color: #3b82f6; font-weight: 500; font-style: normal;">')
    
    # Estilos para tablas (CRÍTICO para reporte cuantitativo)
    html = html.replace(
        '<table>',
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
        'style="margin: 20px 0; font-size: 13px; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden;">'
    )
    html = html.replace(
        '<thead>',
        '<thead style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);">'
    )
    html = html.replace(
        '<th>',
        '<th style="background-color: transparent; color: #ffffff; padding: 12px 10px; '
        'text-align: left; font-weight: 700; font-size: 12px; text-transform: uppercase; '
        'letter-spacing: 0.5px; border-right: 1px solid rgba(255,255,255,0.2);">'
    )
    html = html.replace(
        '<tbody>',
        '<tbody style="background-color: #ffffff;">'
    )
    html = html.replace(
        '<tr>',
        '<tr style="border-bottom: 1px solid #f3f4f6;">'
    )
    html = html.replace(
        '<td>',
        '<td style="padding: 12px 10px; border-right: 1px solid #f3f4f6; color: #374151; font-weight: 500;">'
    )
    
    # Blockquotes
    html = html.replace(
        '<blockquote>',
        '<blockquote style="border-left: 4px solid #3b82f6; background-color: #eff6ff; '
        'padding: 15px 20px; margin: 20px 0; border-radius: 0 6px 6px 0; font-style: italic;">'
    )
    
    # Code blocks
    html = html.replace(
        '<code>',
        '<code style="background-color: #f3f4f6; padding: 2px 6px; border-radius: 3px; '
        'font-family: monospace; font-size: 13px; color: #dc2626;">'
    )
    
    return html


def build_html_from_md(md_path: Path) -> Path:
    """Convierte markdown a HTML del reporte cuantitativo"""
    
    text = md_path.read_text(encoding="utf-8")
    
    # Extraer título
    first_line = text.splitlines()[0].strip() if text.strip() else "Reporte Cuantitativo Semanal"
    title = first_line.replace('#', '').strip() if first_line else "Reporte Cuantitativo Semanal"
    
    # Logo
    if USE_LOGO_URL:
        logo_html = (
            f'<img src="{LOGO_URL}" '
            f'alt="Grey Bark Advisors" width="90" height="90" '
            f'style="display: block; width: 90px; height: auto; border: 0;" />'
        )
        print(f"[INFO] Usando logo desde URL")
    else:
        logo_html = (
            '<div style="'
            'width: 90px; height: 90px; '
            'background-color: #ffffff; '
            'border-radius: 50%; '
            'display: flex; align-items: center; justify-content: center; '
            'font-family: Arial, sans-serif; '
            'font-weight: bold; font-size: 13px; color: #1e40af; '
            'text-align: center; line-height: 1.2; '
            'border: 3px solid #ffffff; '
            'box-shadow: 0 4px 12px rgba(30, 58, 138, 0.3);'
            '">'
            '<div style="letter-spacing: 0.5px;">'
            'GREY<br>BARK<br>'
            '<span style="font-size: 9px; font-weight: normal;">ADVISORS</span>'
            '</div>'
            '</div>'
        )
    
    # Convertir contenido
    content_html = md_to_html_content(text)
    
    # Fecha en español
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    now = datetime.now()
    today_str = f"Semana terminada: {now.day} de {meses[now.month]} de {now.year}"
    generated_at = now.strftime("%d-%m-%Y %H:%M")
    
    # Construir HTML final
    html = HTML_TEMPLATE.format(
        title=title,
        date_str=today_str,
        content=content_html,
        generated_at=generated_at,
        logo_html=logo_html,
    )
    
    # Guardar
    out_name = md_path.stem + ".html"
    out_path = OUTPUT_DIR / out_name
    out_path.write_text(html, encoding="utf-8")
    
    print(f"[OK] {md_path.name} -> {out_path}")
    return out_path


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("HTML FORMATTER - QUANTITATIVE WEEKLY REPORT")
    print("="*80)
    
    # Verificar si se pasó un archivo específico
    if len(sys.argv) > 1:
        md_file = Path(sys.argv[1])
        if not md_file.exists():
            print(f"[ERROR] Archivo no encontrado: {md_file}")
            return 1
        
        print(f"\n[INFO] Procesando archivo: {md_file}")
        build_html_from_md(md_file)
    
    else:
        # Buscar archivos automáticamente
        print("\n[INFO] Buscando reportes cuantitativos...")
        
        md_files = sorted(
            Path(".").glob("quantitative_weekly_report_*.md"),
            reverse=True  # Más reciente primero
        )
        
        if not md_files:
            print("[ERROR] No se encontraron reportes cuantitativos")
            print("        Busca archivos: quantitative_weekly_report_*.md")
            return 1
        
        # Procesar el más reciente
        latest = md_files[0]
        print(f"[INFO] Procesando reporte más reciente: {latest}")
        build_html_from_md(latest)
    
    print("\n[OK] Conversion completada")
    print(f"[INFO] Archivos HTML en: {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    exit(main())

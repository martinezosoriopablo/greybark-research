"""
GREY BARK ADVISORS - EMAIL SENDER V2
Envía reportes usando la base de datos de clientes
"""

# Proteccion de encoding para Windows
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from client_manager import get_recipients_for_report, load_database

load_dotenv()

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

EMAIL_SENDER_USERNAME = os.getenv("EMAIL_SENDER_USERNAME")
EMAIL_SENDER_PASSWORD = os.getenv("EMAIL_SENDER_PASSWORD")
EMAIL_SENDER_NAME = os.getenv("EMAIL_SENDER_NAME", "Grey Bark Advisors Research")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ============================================================================
# MAPEO DE REPORTES
# ============================================================================

REPORT_CONFIG = {
    "AM_pro": {
        "subject_template": "Grey Bark - Reporte Matutino {date}",
        "html_pattern": "html_out/daily_report_AM_finanzas_*.html"
    },
    "AM_general": {
        "subject_template": "Grey Bark - Reporte Matutino {date}",
        "html_pattern": "html_out/daily_report_AM_no_finanzas_*.html"
    },
    "PM_pro": {
        "subject_template": "Grey Bark - Reporte Vespertino {date}",
        "html_pattern": "html_out/daily_report_PM_finanzas_*.html"
    },
    "PM_general": {
        "subject_template": "Grey Bark - Reporte Vespertino {date}",
        "html_pattern": "html_out/daily_report_PM_no_finanzas_*.html"
    },
    "weekly_quant": {
        "subject_template": "Grey Bark - Reporte Cuantitativo Semanal {date}",
        "html_pattern": "html_out/quantitative_weekly_report_*.html"
    }
}

# ============================================================================
# FUNCIONES
# ============================================================================

def find_latest_html(pattern: str) -> Path:
    """Encuentra el archivo HTML más reciente que coincida con el patrón"""
    import glob
    
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No se encontró ningún archivo que coincida con: {pattern}")
    
    # Ordenar por fecha de modificación (más reciente primero)
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    latest = Path(files[0])
    print(f"[INFO] HTML más reciente encontrado: {latest}")
    
    return latest


def send_report_email(report_type: str, html_file: Path = None):
    """
    Envía un reporte por email a los destinatarios correspondientes
    
    Args:
        report_type: Tipo de reporte ("AM_pro", "AM_general", "PM_pro", "PM_general", "weekly_quant")
        html_file: Ruta al archivo HTML (opcional, se busca automáticamente si no se provee)
    """
    
    if report_type not in REPORT_CONFIG:
        print(f"[ERROR] Tipo de reporte inválido: {report_type}")
        print(f"Tipos válidos: {list(REPORT_CONFIG.keys())}")
        return False
    
    # Obtener destinatarios de la base de datos
    recipients = get_recipients_for_report(report_type)
    
    if not recipients:
        print(f"[WARN] No hay destinatarios para {report_type}")
        return False
    
    print(f"\n{'='*80}")
    print(f"ENVIANDO REPORTE: {report_type}")
    print(f"{'='*80}")
    print(f"Destinatarios: {len(recipients)}")
    for r in recipients:
        print(f"  - {r['name']} <{r['email']}>")
    
    # Buscar archivo HTML
    if html_file is None:
        config = REPORT_CONFIG[report_type]
        html_file = find_latest_html(config["html_pattern"])
    
    if not html_file.exists():
        print(f"[ERROR] Archivo HTML no encontrado: {html_file}")
        return False
    
    # Leer contenido HTML
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Preparar subject
    today = datetime.now().strftime("%d-%m-%Y")
    config = REPORT_CONFIG[report_type]
    subject = config["subject_template"].format(date=today)
    
    # Conectar a SMTP
    try:
        print(f"\n[INFO] Conectando a {SMTP_SERVER}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER_USERNAME, EMAIL_SENDER_PASSWORD)
        print("[OK] Conexión SMTP establecida")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a SMTP: {e}")
        return False
    
    # Enviar email a cada destinatario
    sent_count = 0
    failed = []
    
    for recipient in recipients:
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{EMAIL_SENDER_NAME} <{EMAIL_SENDER_USERNAME}>"
            msg['To'] = recipient['email']
            msg['Subject'] = subject
            
            # Adjuntar HTML
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Enviar
            server.send_message(msg)
            sent_count += 1
            print(f"[OK] Enviado a: {recipient['name']} <{recipient['email']}>")
            
        except Exception as e:
            print(f"[ERROR] Fallo al enviar a {recipient['email']}: {e}")
            failed.append(recipient['email'])
    
    server.quit()
    
    # Resumen
    print(f"\n{'='*80}")
    print(f"RESUMEN DE ENVÍO")
    print(f"{'='*80}")
    print(f"Exitosos: {sent_count}/{len(recipients)}")
    if failed:
        print(f"Fallidos: {len(failed)}")
        for email in failed:
            print(f"  - {email}")
    print(f"{'='*80}\n")
    
    return sent_count > 0


def send_all_pending_reports():
    """Envía todos los reportes pendientes del día"""
    import glob
    from datetime import datetime
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n{'='*80}")
    print(f"ENVÍO AUTOMÁTICO DE REPORTES - {today}")
    print(f"{'='*80}\n")
    
    # Determinar qué reportes enviar según la hora
    current_hour = datetime.now().hour
    
    if current_hour < 12:
        # Mañana: enviar reportes AM
        reports_to_send = ["AM_pro", "AM_general"]
        print("[INFO] Modo: MAÑANA - Enviando reportes AM\n")
    else:
        # Tarde: enviar reportes PM
        reports_to_send = ["PM_pro", "PM_general"]
        print("[INFO] Modo: TARDE - Enviando reportes PM\n")
    
    # Si es viernes tarde, también enviar reporte semanal
    if datetime.now().weekday() == 4 and current_hour >= 18:  # Viernes después de las 6 PM
        reports_to_send.append("weekly_quant")
        print("[INFO] ¡Es viernes! También se enviará reporte cuantitativo semanal\n")
    
    # Enviar cada reporte
    for report_type in reports_to_send:
        try:
            send_report_email(report_type)
        except Exception as e:
            print(f"[ERROR] Error enviando {report_type}: {e}")
        
        print()  # Línea en blanco entre reportes


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal con CLI"""
    
    if len(sys.argv) < 2:
        print("\n" + "="*80)
        print("GREY BARK ADVISORS - EMAIL SENDER")
        print("="*80)
        print("\nUso:")
        print("  python send_email.py <report_type>")
        print("  python send_email.py auto")
        print("\nTipos de reporte:")
        print("  AM_pro       - Reporte Matutino (Profesionales)")
        print("  AM_general   - Reporte Matutino (General)")
        print("  PM_pro       - Reporte Vespertino (Profesionales)")
        print("  PM_general   - Reporte Vespertino (General)")
        print("  weekly_quant - Reporte Cuantitativo Semanal")
        print("  auto         - Envía reportes según la hora actual")
        print("\nEjemplos:")
        print("  python send_email.py AM_pro")
        print("  python send_email.py PM_general")
        print("  python send_email.py auto")
        print("="*80 + "\n")
        return 1
    
    report_type = sys.argv[1]

    if report_type.lower() == "auto":
        send_all_pending_reports()
    elif report_type in REPORT_CONFIG:
        # Tipo exacto (AM_pro, PM_general, etc.)
        send_report_email(report_type)
    elif report_type.upper() in ["AM_PRO", "AM_GENERAL", "PM_PRO", "PM_GENERAL", "WEEKLY_QUANT"]:
        # Mapeo de mayusculas a formato correcto
        mapping = {
            "AM_PRO": "AM_pro", "AM_GENERAL": "AM_general",
            "PM_PRO": "PM_pro", "PM_GENERAL": "PM_general",
            "WEEKLY_QUANT": "weekly_quant"
        }
        send_report_email(mapping[report_type.upper()])
    else:
        print(f"[ERROR] Tipo de reporte invalido: {report_type}")
        print(f"Tipos validos: {list(REPORT_CONFIG.keys())}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

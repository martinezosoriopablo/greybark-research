import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

def get_env_list(var_name: str):
    value = os.getenv(var_name, "").strip()
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]

def build_html_path(audience: str, report_date: date) -> str:
    """
    Espera archivo:
      weekly_report_{audience}_{YYYY-MM-DD}.html
    """
    date_str = report_date.isoformat()
    filename = f"weekly_report_{audience}_{date_str}.html"
    REPORT_FOLDER = r"C:\Users\I7 8700\OneDrive\Documentos\proyectos\html_out"
    return os.path.join(REPORT_FOLDER, filename)

def load_html(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo HTML: {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()

def send_email_html(subject: str, html_body: str):
    sender_email = os.getenv("EMAIL_SENDER_USERNAME")
    sender_name = os.getenv("EMAIL_SENDER_NAME", sender_email)
    password = os.getenv("EMAIL_SENDER_PASSWORD")
    if not sender_email or not password:
        raise RuntimeError("EMAIL_SENDER_USERNAME o EMAIL_SENDER_PASSWORD no definidos en .env")

    to_list = get_env_list("EMAIL_RECIPIENTS")
    cc_list = get_env_list("EMAIL_CC")
    bcc_list = get_env_list("EMAIL_BCC")
    if not to_list:
        raise RuntimeError("No hay destinatarios en EMAIL_RECIPIENTS")

    all_recipients = to_list + cc_list + bcc_list

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)

    text_version = "Informe semanal de mercados (HTML). Si no puedes ver el contenido, usa un cliente que soporte HTML."
    msg.attach(MIMEText(text_version, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, all_recipients, msg.as_string())
    print(f"[OK] Correo enviado a: {', '.join(all_recipients)}")

def parse_args():
    """
    Uso:
      python send_email_weekly.py finanzas
      python send_email_weekly.py no_finanzas
      python send_email_weekly.py finanzas 2025-12-19
    """
    if len(sys.argv) < 2:
        print("Uso: python send_email_weekly.py [finanzas|no_finanzas] [YYYY-MM-DD opcional]")
        sys.exit(1)
    audience = sys.argv[1].lower()
    if audience not in ("finanzas", "no_finanzas"):
        print("audience debe ser finanzas o no_finanzas")
        sys.exit(1)
    report_date = date.today()
    if len(sys.argv) >= 3:
        report_date = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    return audience, report_date

def main():
    audience, report_date = parse_args()
    html_path = build_html_path(audience, report_date)
    html_body = load_html(html_path)

    subject_date_str = report_date.strftime("%d-%m-%Y")
    if audience == "finanzas":
        subject = f"Informe Semanal GreyBark - Profesionales - {subject_date_str}"
    else:
        subject = f"Informe Semanal GreyBark - {subject_date_str}"

    send_email_html(subject, html_body)

if __name__ == "__main__":
    main()

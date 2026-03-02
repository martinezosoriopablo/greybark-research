"""
Script maestro: Genera, formatea, guarda en DB y envía reportes automáticamente
Uso: python master_report_pipeline.py [AM|PM]
"""

import sys
import os
from datetime import date
from pathlib import Path

# Importar módulos locales
from database_setup import ReportDatabase
from html_formatter import ReportHTMLFormatter
from report_sender import (
    EmailSender, 
    WhatsAppSender, 
    ReportDistributor,
    generate_whatsapp_summary
)


def run_complete_pipeline(report_type: str):
    """
    Pipeline completo:
    1. Genera datos (daily_market_snapshot.py)
    2. Genera reporte MD (generate_daily_report.py)
    3. Convierte a HTML
    4. Guarda en base de datos
    5. Envía por email y WhatsApp
    """
    
    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETO - REPORTE {report_type}")
    print(f"{'='*60}\n")
    
    today = date.today().isoformat()
    
    # ==========================================
    # PASO 1: Recopilar datos de mercados
    # ==========================================
    print("[1/6] Recopilando datos de mercados...")
    
    import subprocess
    result = subprocess.run(
        ["python", "daily_market_snapshot.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"[ERROR] Error recopilando datos:\n{result.stderr}")
        return False
    
    print("[OK] Datos recopilados")
    
    # ==========================================
    # PASO 2: Generar reporte Markdown
    # ==========================================
    print(f"\n[2/6] Generando reporte {report_type}...")
    
    result = subprocess.run(
        ["python", "generate_daily_report.py", report_type],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"[ERROR] Error generando reporte:\n{result.stderr}")
        return False
    
    md_file = f"daily_report_{report_type}_{today}.md"
    
    if not Path(md_file).exists():
        print(f"[ERROR] No se generó el archivo: {md_file}")
        return False
    
    print(f"[OK] Reporte generado: {md_file}")
    
    # ==========================================
    # PASO 3: Convertir a HTML
    # ==========================================
    print(f"\n[3/6] Formateando a HTML...")
    
    formatter = ReportHTMLFormatter()
    html_file = formatter.markdown_to_html(md_file)
    
    if not Path(html_file).exists():
        print(f"[ERROR] No se generó el HTML: {html_file}")
        return False
    
    print(f"[OK] HTML generado: {html_file}")
    
    # ==========================================
    # PASO 4: Guardar en base de datos
    # ==========================================
    print(f"\n[4/6] Guardando en base de datos...")
    
    db = ReportDatabase()
    report_id = db.save_report(
        date=today,
        report_type=report_type,
        file_path=md_file,
        html_path=html_file
    )
    
    print(f"[OK] Guardado en DB (ID: {report_id})")
    
    # ==========================================
    # PASO 5: Preparar distribución
    # ==========================================
    print(f"\n[5/6] Preparando distribución...")
    
    # Obtener destinatarios activos para este tipo de reporte
    recipients = db.get_active_recipients(report_type=report_type)
    
    if not recipients:
        print("[AVISO]  No hay destinatarios activos configurados")
        print("   Usa database_setup.py para agregar destinatarios")
        return True  # No es un error, solo no hay a quién enviar
    
    print(f"[OK] {len(recipients)} destinatarios activos")
    
    # ==========================================
    # PASO 6: Enviar reportes
    # ==========================================
    print(f"\n[6/6] Enviando reportes...\n")
    
    # Inicializar senders (solo si están configurados)
    email_sender = None
    whatsapp_sender = None
    
    # Intentar configurar email
    try:
        email_sender = EmailSender(provider="gmail")
        print("  [OK] Email sender configurado (Gmail)")
    except Exception as e:
        print(f"  [AVISO]  Email no disponible: {e}")
    
    # Intentar configurar WhatsApp
    try:
        whatsapp_sender = WhatsAppSender(method="twilio")
        print("  [OK] WhatsApp sender configurado (Twilio)")
    except Exception as e:
        try:
            whatsapp_sender = WhatsAppSender(method="callmebot")
            print("  [OK] WhatsApp sender configurado (CallMeBot)")
        except Exception as e2:
            print(f"  [AVISO]  WhatsApp no disponible: {e2}")
    
    print()
    
    # Si no hay ningún sender configurado, avisar
    if not email_sender and not whatsapp_sender:
        print("[AVISO]  No hay canales de envío configurados")
        print("   Configura EMAIL o WhatsApp en variables de entorno")
        print("   Ver: report_sender.py para instrucciones")
        return True
    
    # Generar resumen para WhatsApp
    whatsapp_summary = None
    if whatsapp_sender:
        with open(md_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        whatsapp_summary = generate_whatsapp_summary(md_content)
    
    # Distribuir
    distributor = ReportDistributor(
        email_sender=email_sender,
        whatsapp_sender=whatsapp_sender
    )
    
    date_formatted = date.today().strftime('%d/%m/%Y')
    
    stats = distributor.distribute_report(
        html_path=html_file,
        report_type=report_type,
        date_str=date_formatted,
        recipients=recipients,
        summary=whatsapp_summary
    )
    
    # Registrar envíos en DB
    for recipient in recipients:
        # Email
        if recipient.get('email') and email_sender:
            status = 'sent' if stats['email_sent'] > 0 else 'failed'
            db.log_delivery(report_id, recipient['id'], 'email', status)
        
        # WhatsApp
        if recipient.get('phone') and whatsapp_sender:
            status = 'sent' if stats['whatsapp_sent'] > 0 else 'failed'
            db.log_delivery(report_id, recipient['id'], 'whatsapp', status)
    
    # Mostrar estadísticas
    print("\n" + "="*60)
    print("  ESTADÍSTICAS DE ENVÍO")
    print("="*60)
    print(f"  Emails enviados:    {stats['email_sent']}")
    print(f"  Emails fallidos:    {stats['email_failed']}")
    print(f"  WhatsApp enviados:  {stats['whatsapp_sent']}")
    print(f"  WhatsApp fallidos:  {stats['whatsapp_failed']}")
    print("="*60 + "\n")
    
    print("✅ PIPELINE COMPLETADO EXITOSAMENTE\n")
    return True


def main():
    """Punto de entrada principal."""
    
    if len(sys.argv) < 2:
        print("Error: Debes especificar el modo (AM o PM)")
        print("Uso: python master_report_pipeline.py [AM|PM]")
        sys.exit(1)
    
    report_type = sys.argv[1].upper()
    
    if report_type not in ["AM", "PM"]:
        print(f"Error: Modo inválido '{report_type}'. Usa AM o PM.")
        sys.exit(1)
    
    success = run_complete_pipeline(report_type)
    
    if not success:
        print("\n❌ Pipeline falló. Revisa los logs para más detalles.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

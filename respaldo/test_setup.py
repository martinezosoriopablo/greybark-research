"""
Script de prueba para verificar configuración de Email y WhatsApp
Ejecuta este script ANTES de correr el pipeline completo
"""

import os
import sys


def test_email_config():
    """Verifica configuración de Gmail."""
    print("\n" + "="*60)
    print("  TEST 1: CONFIGURACIÓN DE EMAIL (Gmail)")
    print("="*60)
    
    email = os.getenv("EMAIL_ADDRESS")
    password = os.getenv("EMAIL_PASSWORD")
    
    if not email:
        print("❌ EMAIL_ADDRESS no configurado")
        print("   Ejecuta: setx EMAIL_ADDRESS \"tu-email@gmail.com\"")
        return False
    
    if not password:
        print("❌ EMAIL_PASSWORD no configurado")
        print("   Ejecuta: setx EMAIL_PASSWORD \"tu-app-password\"")
        return False
    
    print(f"✓ EMAIL_ADDRESS: {email}")
    print(f"✓ EMAIL_PASSWORD: {'*' * len(password)} (configurado)")
    
    # Intentar conectar
    print("\nProbando conexión con Gmail...")
    try:
        from report_sender import EmailSender
        sender = EmailSender(provider="gmail")
        print("✓ Conexión con Gmail OK")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_whatsapp_config():
    """Verifica configuración de CallMeBot."""
    print("\n" + "="*60)
    print("  TEST 2: CONFIGURACIÓN DE WHATSAPP (CallMeBot)")
    print("="*60)
    
    phone = os.getenv("CALLMEBOT_PHONE")
    api_key = os.getenv("CALLMEBOT_API_KEY")
    
    if not phone:
        print("❌ CALLMEBOT_PHONE no configurado")
        print("   Ejecuta: setx CALLMEBOT_PHONE \"+56912345678\"")
        return False
    
    if not api_key:
        print("❌ CALLMEBOT_API_KEY no configurado")
        print("   Ejecuta: setx CALLMEBOT_API_KEY \"tu-api-key\"")
        return False
    
    print(f"✓ CALLMEBOT_PHONE: {phone}")
    print(f"✓ CALLMEBOT_API_KEY: {'*' * len(api_key)} (configurado)")
    
    print("\nProbando conexión con CallMeBot...")
    try:
        from report_sender import WhatsAppSender
        sender = WhatsAppSender(method="callmebot")
        print("✓ Configuración de CallMeBot OK")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_database():
    """Verifica base de datos."""
    print("\n" + "="*60)
    print("  TEST 3: BASE DE DATOS")
    print("="*60)
    
    try:
        from database_setup import ReportDatabase
        
        db = ReportDatabase()
        print("✓ Base de datos inicializada")
        
        recipients = db.get_active_recipients()
        print(f"✓ Destinatarios activos: {len(recipients)}")
        
        if len(recipients) == 0:
            print("\n⚠️  No hay destinatarios configurados")
            print("   Edita database_setup.py y ejecuta:")
            print("   python database_setup.py")
            return False
        
        for r in recipients:
            print(f"   - {r['name']}: {r['email']} | {r['phone']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_dependencies():
    """Verifica que estén instaladas las dependencias."""
    print("\n" + "="*60)
    print("  TEST 4: DEPENDENCIAS PYTHON")
    print("="*60)
    
    missing = []
    
    try:
        import markdown
        print("✓ markdown instalado")
    except ImportError:
        print("❌ markdown NO instalado")
        missing.append("markdown")
    
    try:
        import requests
        print("✓ requests instalado")
    except ImportError:
        print("❌ requests NO instalado")
        missing.append("requests")
    
    if missing:
        print(f"\nInstala con: pip install {' '.join(missing)}")
        return False
    
    return True


def send_test_email():
    """Envía un email de prueba."""
    print("\n" + "="*60)
    print("  TEST 5: ENVÍO DE EMAIL DE PRUEBA")
    print("="*60)
    
    try:
        from report_sender import EmailSender
        from database_setup import ReportDatabase
        
        db = ReportDatabase()
        recipients = db.get_active_recipients()
        
        if not recipients:
            print("❌ No hay destinatarios para probar")
            return False
        
        sender = EmailSender(provider="gmail")
        
        test_html = """
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h2 style="color: #0066cc;">✅ Test Email - Daily Reports</h2>
            <p>Si recibes este email, la configuración está correcta.</p>
            <p><strong>Sistema:</strong> Daily Market Reports</p>
            <p><strong>Fecha:</strong> {date}</p>
            <hr>
            <p style="font-size: 12px; color: #666;">
                Este es un email de prueba. El sistema está listo para enviar reportes.
            </p>
        </body>
        </html>
        """.format(date="2025-12-05")
        
        recipient = recipients[0]
        print(f"\nEnviando email de prueba a: {recipient['email']}...")
        
        success = sender.send_report(
            to_emails=[recipient['email']],
            subject="✅ Test - Daily Market Reports",
            html_body=test_html
        )
        
        if success:
            print("✓ Email de prueba enviado correctamente")
            print("  Revisa tu bandeja de entrada (o spam)")
            return True
        else:
            print("❌ Falló el envío del email de prueba")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_test_whatsapp():
    """Envía un WhatsApp de prueba."""
    print("\n" + "="*60)
    print("  TEST 6: ENVÍO DE WHATSAPP DE PRUEBA")
    print("="*60)
    
    try:
        from report_sender import WhatsAppSender
        
        sender = WhatsAppSender(method="callmebot")
        phone = os.getenv("CALLMEBOT_PHONE")
        
        print(f"\nEnviando WhatsApp de prueba a: {phone}...")
        
        success = sender.send_report_summary(
            to_number=phone,
            report_type="TEST",
            summary="✅ Test exitoso. El sistema de WhatsApp está funcionando correctamente."
        )
        
        if success:
            print("✓ WhatsApp de prueba enviado correctamente")
            print("  Revisa tu WhatsApp")
            return True
        else:
            print("❌ Falló el envío del WhatsApp de prueba")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests."""
    print("\n" + "="*60)
    print("  VERIFICACIÓN DE CONFIGURACIÓN - DAILY REPORTS")
    print("="*60)
    
    results = []
    
    # Tests básicos
    results.append(("Dependencias", test_dependencies()))
    results.append(("Email Config", test_email_config()))
    results.append(("WhatsApp Config", test_whatsapp_config()))
    results.append(("Base de Datos", test_database()))
    
    # Tests de envío (solo si los básicos pasaron)
    if all(r[1] for r in results):
        print("\n✓ Configuración básica OK. Probando envíos...")
        
        response = input("\n¿Enviar email de prueba? (s/n): ")
        if response.lower() == 's':
            results.append(("Email Test", send_test_email()))
        
        response = input("\n¿Enviar WhatsApp de prueba? (s/n): ")
        if response.lower() == 's':
            results.append(("WhatsApp Test", send_test_whatsapp()))
    
    # Resumen final
    print("\n" + "="*60)
    print("  RESUMEN DE TESTS")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("="*60)
    
    if all(r[1] for r in results):
        print("\n🎉 TODO OK! El sistema está listo para usar.")
        print("\nPróximo paso:")
        print("  python master_report_pipeline.py AM")
    else:
        print("\n⚠️  Algunos tests fallaron. Revisa la configuración.")
        print("\nPasos siguientes:")
        print("  1. Configura las variables de entorno faltantes")
        print("  2. Reinicia tu terminal")
        print("  3. Vuelve a ejecutar: python test_setup.py")


if __name__ == "__main__":
    main()

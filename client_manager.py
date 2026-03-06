# -*- coding: utf-8 -*-
import sys
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

"""
GREY BARK ADVISORS - CLIENT DATABASE
Sistema de gestión de clientes y distribución de reportes
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DATABASE_FILE = "clients_database.json"

# Tipos de reportes disponibles
AVAILABLE_REPORTS = {
    "AM_pro": "Reporte Matutino (Profesionales)",
    "AM_general": "Reporte Matutino (General)",
    "PM_pro": "Reporte Vespertino (Profesionales)",
    "PM_general": "Reporte Vespertino (General)",
    "weekly_quant": "Reporte Cuantitativo Semanal"
}

# Tipos de cliente
CLIENT_TYPES = ["professional", "retail", "internal"]

# ============================================================================
# FUNCIONES
# ============================================================================

def create_default_database():
    """Crea base de datos inicial con clientes actuales"""
    default_db = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "version": "1.0"
        },
        "clients": [
            {
                "id": 1,
                "name": "Pablo Martínez",
                "email": "pabloalfonsomartinezosorio@gmail.com",
                "type": "internal",
                "reports": ["AM_pro", "PM_pro", "weekly_quant"],
                "active": True,
                "notes": "Fundador - recibe todos los reportes"
            },
            {
                "id": 2,
                "name": "Nicolas Guinez",
                "email": "nicolas.guinezt@gmail.com",
                "type": "professional",
                "reports": ["AM_pro", "PM_pro", "weekly_quant"],
                "active": True,
                "notes": ""
            },
            {
                "id": 3,
                "name": "José Navarrete",
                "email": "josemnavarrete85@gmail.com",
                "type": "professional",
                "reports": ["AM_pro", "PM_pro"],
                "active": True,
                "notes": ""
            },
            {
                "id": 4,
                "name": "Felipe Wilson",
                "email": "fwilson@sfc.cl",
                "type": "professional",
                "reports": ["AM_pro", "PM_pro", "weekly_quant"],
                "active": True,
                "notes": "SFC Capital"
            },
            {
                "id": 5,
                "name": "Test - General",
                "email": "martinezosoriopablo@gmail.com",
                "type": "retail",
                "reports": ["AM_general"],
                "active": True,
                "notes": "Cliente de prueba - versión general"
            }
        ]
    }
    
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(default_db, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Base de datos creada: {DATABASE_FILE}")
    return default_db


def load_database() -> Dict[str, Any]:
    """Carga la base de datos de clientes"""
    if not os.path.exists(DATABASE_FILE):
        print(f"[INFO] No existe {DATABASE_FILE}, creando...")
        return create_default_database()
    
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(db: Dict[str, Any]):
    """Guarda la base de datos"""
    db["metadata"]["last_updated"] = datetime.now().isoformat()
    
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Base de datos guardada")


def get_recipients_for_report(report_type: str) -> List[Dict[str, str]]:
    """
    Obtiene lista de destinatarios para un tipo de reporte específico
    
    Args:
        report_type: "AM_pro", "AM_general", "PM_pro", "PM_general", "weekly_quant"
    
    Returns:
        Lista de diccionarios con name y email
    """
    db = load_database()
    recipients = []
    
    for client in db["clients"]:
        if client["active"] and report_type in client["reports"]:
            recipients.append({
                "name": client["name"],
                "email": client["email"],
                "podcast": bool(client.get("podcast", False))
            })
    
    return recipients


def add_client(name: str, email: str, client_type: str, reports: List[str], notes: str = "", podcast: bool = False) -> bool:
    """Agrega un nuevo cliente"""
    db = load_database()
    
    # Verificar que el email no exista
    for client in db["clients"]:
        if client["email"].lower() == email.lower():
            print(f"[ERROR] Email {email} ya existe en la base de datos")
            return False
    
    # Generar nuevo ID
    max_id = max([c["id"] for c in db["clients"]], default=0)
    
    new_client = {
        "id": max_id + 1,
        "name": name,
        "email": email,
        "type": client_type,
        "reports": reports,
        "active": True,
        "podcast": podcast,
        "notes": notes
    }
    
    db["clients"].append(new_client)
    save_database(db)
    
    print(f"[OK] Cliente agregado: {name} ({email})")
    return True


def remove_client(email: str) -> bool:
    """Elimina un cliente (marca como inactivo)"""
    db = load_database()
    
    for client in db["clients"]:
        if client["email"].lower() == email.lower():
            client["active"] = False
            save_database(db)
            print(f"[OK] Cliente desactivado: {client['name']} ({email})")
            return True
    
    print(f"[ERROR] Cliente no encontrado: {email}")
    return False


def update_client_reports(email: str, reports: List[str], podcast: bool = None) -> bool:
    """Actualiza los reportes (y opcionalmente podcast) de un cliente"""
    db = load_database()

    for client in db["clients"]:
        if client["email"].lower() == email.lower():
            client["reports"] = reports
            if podcast is not None:
                client["podcast"] = podcast
            save_database(db)
            print(f"[OK] Reportes actualizados para: {client['name']}")
            return True

    print(f"[ERROR] Cliente no encontrado: {email}")
    return False


def list_all_clients():
    """Lista todos los clientes"""
    db = load_database()
    
    print("\n" + "="*80)
    print("CLIENTES GREY BARK ADVISORS")
    print("="*80)
    
    active = [c for c in db["clients"] if c["active"]]
    inactive = [c for c in db["clients"] if not c["active"]]
    
    print(f"\nCLIENTES ACTIVOS: {len(active)}")
    print("-"*80)
    
    for client in active:
        print(f"\nID: {client['id']}")
        print(f"Nombre: {client['name']}")
        print(f"Email: {client['email']}")
        print(f"Tipo: {client['type']}")
        print(f"Reportes: {', '.join(client['reports'])}")
        if client['notes']:
            print(f"Notas: {client['notes']}")
    
    if inactive:
        print(f"\n\nCLIENTES INACTIVOS: {len(inactive)}")
        print("-"*80)
        for client in inactive:
            print(f"- {client['name']} ({client['email']})")
    
    print("\n" + "="*80)


def export_to_env_format():
    """Exporta destinatarios en formato .env (backup/legacy)"""
    db = load_database()
    
    recipients = []
    cc = []
    bcc = []
    
    for client in db["clients"]:
        if not client["active"]:
            continue
        
        email = client["email"]
        recipients.append(email)
        
        # Lógica de CC/BCC según necesidad
        if client["type"] == "internal":
            bcc.append(email)
    
    print("\n# Copia esto a tu .env si necesitas formato legacy:")
    print(f"EMAIL_RECIPIENTS={', '.join(recipients)}")
    if cc:
        print(f"EMAIL_CC={', '.join(cc)}")
    if bcc:
        print(f"EMAIL_BCC={', '.join(bcc)}")


# ============================================================================
# CLI INTERACTIVA
# ============================================================================

def main_menu():
    """Menú principal"""
    while True:
        print("\n" + "="*80)
        print("GREY BARK ADVISORS - GESTIÓN DE CLIENTES")
        print("="*80)
        print("1. Listar todos los clientes")
        print("2. Agregar nuevo cliente")
        print("3. Desactivar cliente")
        print("4. Actualizar reportes de cliente")
        print("5. Ver destinatarios por tipo de reporte")
        print("6. Exportar a formato .env")
        print("7. Salir")
        print("="*80)
        
        choice = input("\nSelecciona una opción: ").strip()
        
        if choice == "1":
            list_all_clients()
        
        elif choice == "2":
            print("\n--- AGREGAR NUEVO CLIENTE ---")
            name = input("Nombre completo: ").strip()
            email = input("Email: ").strip()
            
            print("\nTipo de cliente:")
            for i, t in enumerate(CLIENT_TYPES, 1):
                print(f"{i}. {t}")
            type_choice = input("Selecciona (1-3): ").strip()
            client_type = CLIENT_TYPES[int(type_choice) - 1]
            
            print("\nReportes disponibles:")
            for i, (key, desc) in enumerate(AVAILABLE_REPORTS.items(), 1):
                print(f"{i}. {desc} ({key})")
            
            reports_input = input("Selecciona reportes (ej: 1,2,5): ").strip()
            report_indices = [int(x.strip()) for x in reports_input.split(",")]
            reports = [list(AVAILABLE_REPORTS.keys())[i-1] for i in report_indices]
            
            notes = input("Notas (opcional): ").strip()
            
            add_client(name, email, client_type, reports, notes)
        
        elif choice == "3":
            email = input("\nEmail del cliente a desactivar: ").strip()
            remove_client(email)
        
        elif choice == "4":
            email = input("\nEmail del cliente: ").strip()
            print("\nReportes disponibles:")
            for i, (key, desc) in enumerate(AVAILABLE_REPORTS.items(), 1):
                print(f"{i}. {desc} ({key})")
            
            reports_input = input("Nuevos reportes (ej: 1,2,5): ").strip()
            report_indices = [int(x.strip()) for x in reports_input.split(",")]
            reports = [list(AVAILABLE_REPORTS.keys())[i-1] for i in report_indices]
            
            update_client_reports(email, reports)
        
        elif choice == "5":
            print("\n--- DESTINATARIOS POR REPORTE ---")
            for report_type, desc in AVAILABLE_REPORTS.items():
                recipients = get_recipients_for_report(report_type)
                print(f"\n{desc} ({report_type}):")
                if recipients:
                    for r in recipients:
                        print(f"  - {r['name']} <{r['email']}>")
                else:
                    print("  (sin destinatarios)")
        
        elif choice == "6":
            export_to_env_format()
        
        elif choice == "7":
            print("\n¡Hasta pronto!")
            break
        
        else:
            print("\n[ERROR] Opción inválida")


if __name__ == "__main__":
    # Si no existe la DB, crearla
    if not os.path.exists(DATABASE_FILE):
        create_default_database()
    
    # Iniciar menú
    main_menu()

"""
Base de datos SQLite para Daily Market Reports
- Almacena historial de reportes
- Gestiona destinatarios
- Registra envíos
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any


class ReportDatabase:
    def __init__(self, db_path: str = "market_reports.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Crea las tablas necesarias si no existen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabla de reportes generados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                report_type TEXT NOT NULL,  -- 'AM' o 'PM'
                file_path TEXT NOT NULL,
                html_path TEXT,
                pdf_path TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, report_type)
            )
        """)
        
        # Tabla de destinatarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,  -- Para WhatsApp
                active INTEGER DEFAULT 1,  -- 1=activo, 0=inactivo
                receive_am INTEGER DEFAULT 1,  -- Recibe reporte AM
                receive_pm INTEGER DEFAULT 1,  -- Recibe reporte PM
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(email)
            )
        """)
        
        # Tabla de envíos realizados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                delivery_method TEXT NOT NULL,  -- 'email' o 'whatsapp'
                status TEXT NOT NULL,  -- 'sent', 'failed', 'pending'
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES reports (id),
                FOREIGN KEY (recipient_id) REFERENCES recipients (id)
            )
        """)
        
        # Índices para optimizar consultas
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_date 
            ON reports(date, report_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_report 
            ON deliveries(report_id, status)
        """)
        
        conn.commit()
        conn.close()
        print(f"[OK] Base de datos inicializada: {self.db_path}")
    
    def save_report(self, date: str, report_type: str, file_path: str, 
                   html_path: str = None, pdf_path: str = None) -> int:
        """Guarda un reporte generado."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO reports 
            (date, report_type, file_path, html_path, pdf_path)
            VALUES (?, ?, ?, ?, ?)
        """, (date, report_type, file_path, html_path, pdf_path))
        
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"[OK] Reporte guardado: {report_type} - {date} (ID: {report_id})")
        return report_id
    
    def add_recipient(self, name: str, email: str = None, phone: str = None,
                     receive_am: bool = True, receive_pm: bool = True) -> int:
        """Agrega un nuevo destinatario."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO recipients 
                (name, email, phone, receive_am, receive_pm)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, phone, int(receive_am), int(receive_pm)))
            
            recipient_id = cursor.lastrowid
            conn.commit()
            print(f"[OK] Destinatario agregado: {name} (ID: {recipient_id})")
            return recipient_id
        except sqlite3.IntegrityError:
            print(f"[ERROR] El email {email} ya existe")
            return None
        finally:
            conn.close()
    
    def get_active_recipients(self, report_type: str = None) -> List[Dict[str, Any]]:
        """Obtiene destinatarios activos, opcionalmente filtrados por tipo de reporte."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM recipients WHERE active = 1"
        
        if report_type == "AM":
            query += " AND receive_am = 1"
        elif report_type == "PM":
            query += " AND receive_pm = 1"
        
        cursor.execute(query)
        recipients = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return recipients
    
    def log_delivery(self, report_id: int, recipient_id: int, 
                    method: str, status: str, error: str = None):
        """Registra un intento de envío."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO deliveries 
            (report_id, recipient_id, delivery_method, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (report_id, recipient_id, method, status, error))
        
        conn.commit()
        conn.close()
    
    def get_report_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """Obtiene el historial de reportes de los últimos N días."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM reports 
            WHERE date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC, report_type
        """, (days,))
        
        reports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return reports
    
    def get_delivery_stats(self, report_id: int) -> Dict[str, int]:
        """Obtiene estadísticas de envío para un reporte."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                delivery_method,
                status,
                COUNT(*) as count
            FROM deliveries
            WHERE report_id = ?
            GROUP BY delivery_method, status
        """, (report_id,))
        
        stats = {}
        for row in cursor.fetchall():
            method, status, count = row
            key = f"{method}_{status}"
            stats[key] = count
        
        conn.close()
        return stats


def setup_initial_recipients():
    """Función helper para agregar destinatarios iniciales."""
    db = ReportDatabase()
    
    print("\n=== AGREGAR DESTINATARIOS INICIALES ===\n")
    
    # EDITA AQUÍ TUS DESTINATARIOS
    recipients = [
        {
            "name": "Pablo",
            "email": "tu-email@gmail.com",  # ← CAMBIA ESTO
            "phone": "+56912345678",         # ← CAMBIA ESTO (mismo del CallMeBot)
            "receive_am": True,              # ¿Recibe reporte AM?
            "receive_pm": True               # ¿Recibe reporte PM?
        },
        # AGREGA MÁS DESTINATARIOS AQUÍ:
        # {
        #     "name": "Cliente 1",
        #     "email": "cliente@ejemplo.com",
        #     "phone": "+56987654321",
        #     "receive_am": True,
        #     "receive_pm": False
        # },
    ]
    
    for recipient in recipients:
        db.add_recipient(**recipient)
    
    print("\n[OK] Destinatarios iniciales configurados")


if __name__ == "__main__":
    # Inicializar base de datos
    db = ReportDatabase()
    
    # Mostrar estadísticas
    print("\n=== ESTADÍSTICAS ===")
    recipients = db.get_active_recipients()
    print(f"Destinatarios activos: {len(recipients)}")
    
    reports = db.get_report_history(days=7)
    print(f"Reportes últimos 7 días: {len(reports)}")
    
    # Ejecutar SOLO LA PRIMERA VEZ para agregar destinatarios
    # Luego comenta esta línea para no duplicar
    setup_initial_recipients()

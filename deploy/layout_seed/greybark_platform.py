"""
greybark_platform.py — Sistema Multi-Cliente Escalable
=======================================================
Base de datos SQLite (migrable a PostgreSQL), admin CRUD,
queue de generación, tracking de uso, y billing.

Estructura:
    1. Database models (SQLite)
    2. Client CRUD (crear, editar, activar/desactivar)
    3. Product registry (qué productos existen)
    4. Job queue (cola de trabajos por cliente)
    5. Usage tracking (logs de cada corrida)
    6. Billing helpers (facturación mensual)
    7. Pipeline runner (orquesta todo)

Uso:
    from greybark_platform import Platform
    
    platform = Platform()  # inicializa DB
    platform.add_client(...)
    platform.run_daily_pipeline()
    platform.get_usage_report("agf_capital", "2026-03")
"""

import sqlite3
import json
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

_PLATFORM_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("GREYBARK_DB", os.path.join(_PLATFORM_DIR, "greybark.db"))
OUTPUT_BASE = os.environ.get("GREYBARK_OUTPUT", os.path.join(_PLATFORM_DIR, "output"))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("greybark")


# ══════════════════════════════════════════════════════════════
# DATA MODELS
# ══════════════════════════════════════════════════════════════

@dataclass
class Branding:
    logo_path: str = ""
    primary_color: str = "#1B3A5C"
    accent_color: str = "#C9963B"
    font_family: str = "Georgia"
    footer_text: str = ""
    email_header_html: str = ""  # HTML personalizado para header de emails

@dataclass
class AIPrompts:
    tone: str = ""
    audience: str = ""
    focus: str = ""
    podcast_intro: str = ""
    podcast_outro: str = ""
    report_disclaimer: str = ""  # Disclaimer legal del cliente
    custom_instructions: str = ""  # Instrucciones adicionales libres

@dataclass
class DeliveryConfig:
    email_to: List[str] = field(default_factory=list)
    email_cc: List[str] = field(default_factory=list)
    email_bcc: List[str] = field(default_factory=list)
    email_from_name: str = "Research"
    email_reply_to: str = ""
    webhook_url: str = ""  # Para integraciones (Slack, Teams, etc.)
    schedule: str = "am_pm"  # am_only, pm_only, am_pm

@dataclass
class ClientRecord:
    """Registro completo de un cliente en la plataforma."""
    client_id: str
    company_name: str
    active: bool = True
    
    # Productos contratados
    product_daily_am: bool = True
    product_daily_pm: bool = True
    product_ai_council: bool = False
    product_podcast: bool = True
    product_intel_briefing: bool = False
    
    # Configuraciones
    branding: Branding = field(default_factory=Branding)
    ai_prompts: AIPrompts = field(default_factory=AIPrompts)
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)
    
    # Plan y billing
    plan: str = "starter"  # starter, profesional, enterprise, custom
    monthly_fee: float = 500.0
    currency: str = "USD"
    billing_email: str = ""
    
    # Metadata
    start_date: str = ""
    contact_name: str = ""
    contact_phone: str = ""
    notes: str = ""
    
    # Timestamps (auto)
    created_at: str = ""
    updated_at: str = ""


# ══════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- Clientes
CREATE TABLE IF NOT EXISTS clients (
    client_id       TEXT PRIMARY KEY,
    company_name    TEXT NOT NULL,
    active          INTEGER DEFAULT 1,
    
    -- Productos (flags individuales)
    product_daily_am      INTEGER DEFAULT 1,
    product_daily_pm      INTEGER DEFAULT 1,
    product_ai_council    INTEGER DEFAULT 0,
    product_podcast       INTEGER DEFAULT 1,
    product_intel_briefing INTEGER DEFAULT 0,
    
    -- Configs (JSON blobs para flexibilidad)
    branding_json   TEXT DEFAULT '{}',
    ai_prompts_json TEXT DEFAULT '{}',
    delivery_json   TEXT DEFAULT '{}',
    
    -- Plan
    plan            TEXT DEFAULT 'starter',
    monthly_fee     REAL DEFAULT 500.0,
    currency        TEXT DEFAULT 'USD',
    billing_email   TEXT DEFAULT '',
    
    -- Metadata
    start_date      TEXT DEFAULT '',
    contact_name    TEXT DEFAULT '',
    contact_phone   TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- Jobs: cada ejecución de un producto para un cliente
CREATE TABLE IF NOT EXISTS jobs (
    job_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       TEXT NOT NULL,
    product         TEXT NOT NULL,  -- 'daily_am', 'daily_pm', 'ai_council', 'podcast', 'intel_briefing'
    status          TEXT DEFAULT 'pending',  -- pending, running, completed, failed, skipped
    
    -- Timing
    queued_at       TEXT DEFAULT (datetime('now')),
    started_at      TEXT,
    completed_at    TEXT,
    duration_secs   REAL,
    
    -- Results
    output_path     TEXT,
    error_message   TEXT,
    retry_count     INTEGER DEFAULT 0,
    
    -- Trigger info
    triggered_by    TEXT DEFAULT 'scheduler',  -- scheduler, manual, dashboard
    trigger_meta    TEXT DEFAULT '{}',  -- JSON con contexto (ej: directrices del council)
    
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Usage: resumen mensual por cliente (para billing)
CREATE TABLE IF NOT EXISTS usage_monthly (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       TEXT NOT NULL,
    month           TEXT NOT NULL,  -- '2026-03'
    
    -- Contadores
    daily_am_count  INTEGER DEFAULT 0,
    daily_pm_count  INTEGER DEFAULT 0,
    ai_council_count INTEGER DEFAULT 0,
    podcast_count   INTEGER DEFAULT 0,
    intel_count     INTEGER DEFAULT 0,
    
    -- Costos estimados
    api_cost_usd    REAL DEFAULT 0.0,
    
    -- Timestamps
    updated_at      TEXT DEFAULT (datetime('now')),
    
    UNIQUE(client_id, month),
    FOREIGN KEY (client_id) REFERENCES clients(client_id)
);

-- Audit log: cambios importantes
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT DEFAULT (datetime('now')),
    action          TEXT NOT NULL,  -- 'client_created', 'client_updated', 'job_completed', etc.
    client_id       TEXT,
    details         TEXT DEFAULT '{}'
);

-- Índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_queued ON jobs(queued_at);
CREATE INDEX IF NOT EXISTS idx_usage_month ON usage_monthly(client_id, month);
CREATE INDEX IF NOT EXISTS idx_audit_client ON audit_log(client_id, timestamp);
"""


class Database:
    """Wrapper SQLite con context manager y helpers."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            logger.info(f"Database initialized: {self.db_path}")
    
    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════
# PLATFORM: API PRINCIPAL
# ══════════════════════════════════════════════════════════════

class Platform:
    """
    API principal de la plataforma Greybark.
    
    Uso:
        p = Platform()
        p.add_client("agf", "AGF Capital", plan="profesional", monthly_fee=1500)
        p.set_products("agf", daily_am=True, ai_council=True, podcast=True)
        p.set_branding("agf", primary_color="#1B3A5C", logo_path="logos/agf.png")
        p.set_ai_prompts("agf", tone="Técnico institucional", audience="PM y CIO")
        p.set_delivery("agf", email_to=["pm@agf.cl"], email_from_name="AGF Research")
        
        # Correr pipeline
        p.run_daily_pipeline("am")  # genera para TODOS los clientes activos con daily_am
        
        # O correr para un cliente específico
        p.run_ai_council("agf", directives="Evaluar bonos AAA...")
    """
    
    def __init__(self, db_path: str = DB_PATH):
        self.db = Database(db_path)
        self.output_base = Path(OUTPUT_BASE)
        self.output_base.mkdir(parents=True, exist_ok=True)
    
    # ── CLIENT CRUD ──────────────────────────────────────────
    
    def add_client(
        self,
        client_id: str,
        company_name: str,
        plan: str = "starter",
        monthly_fee: float = 500.0,
        contact_name: str = "",
        contact_phone: str = "",
        billing_email: str = "",
        notes: str = "",
    ) -> ClientRecord:
        """Crear un nuevo cliente."""
        now = datetime.now().isoformat()
        
        with self.db.connect() as conn:
            conn.execute("""
                INSERT INTO clients (
                    client_id, company_name, plan, monthly_fee,
                    contact_name, contact_phone, billing_email, notes,
                    start_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                client_id, company_name, plan, monthly_fee,
                contact_name, contact_phone, billing_email, notes,
                now[:10], now, now
            ))
            
            self._audit(conn, "client_created", client_id, {
                "company_name": company_name, "plan": plan
            })
        
        logger.info(f"✅ Cliente creado: {company_name} ({client_id}) — {plan} ${monthly_fee}/mes")
        return self.get_client(client_id)
    
    def get_client(self, client_id: str) -> Optional[ClientRecord]:
        """Obtener un cliente por ID."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        
        if not row:
            return None
        return self._row_to_client(row)
    
    def list_clients(self, active_only: bool = True) -> List[ClientRecord]:
        """Listar clientes."""
        with self.db.connect() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM clients WHERE active = 1 ORDER BY company_name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM clients ORDER BY active DESC, company_name"
                ).fetchall()
        
        return [self._row_to_client(r) for r in rows]
    
    def update_client(self, client_id: str, **kwargs) -> ClientRecord:
        """
        Actualizar campos del cliente.
        
        Uso:
            p.update_client("agf", company_name="AGF Capital SA", plan="enterprise")
        """
        allowed = {
            'company_name', 'active', 'plan', 'monthly_fee', 'currency',
            'billing_email', 'contact_name', 'contact_phone', 'notes'
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        
        if not updates:
            raise ValueError(f"No valid fields to update. Allowed: {allowed}")
        
        updates['updated_at'] = datetime.now().isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [client_id]
        
        with self.db.connect() as conn:
            conn.execute(
                f"UPDATE clients SET {set_clause} WHERE client_id = ?", values
            )
            self._audit(conn, "client_updated", client_id, updates)
        
        logger.info(f"📝 Cliente actualizado: {client_id} — {updates}")
        return self.get_client(client_id)
    
    def deactivate_client(self, client_id: str):
        """Desactivar un cliente (no lo borra)."""
        return self.update_client(client_id, active=False)
    
    def activate_client(self, client_id: str):
        """Reactivar un cliente."""
        return self.update_client(client_id, active=True)
    
    # ── PRODUCTS ─────────────────────────────────────────────
    
    def set_products(self, client_id: str, **products):
        """
        Configurar qué productos tiene un cliente.
        
        Uso:
            p.set_products("agf",
                daily_am=True, daily_pm=True,
                ai_council=True, podcast=True,
                intel_briefing=False
            )
        """
        mapping = {
            'daily_am': 'product_daily_am',
            'daily_pm': 'product_daily_pm',
            'ai_council': 'product_ai_council',
            'podcast': 'product_podcast',
            'intel_briefing': 'product_intel_briefing',
        }
        
        updates = {}
        for k, v in products.items():
            if k in mapping:
                updates[mapping[k]] = 1 if v else 0
        
        if updates:
            updates['updated_at'] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [client_id]
            
            with self.db.connect() as conn:
                conn.execute(
                    f"UPDATE clients SET {set_clause} WHERE client_id = ?", values
                )
                self._audit(conn, "products_updated", client_id, products)
        
        logger.info(f"📦 Productos actualizados: {client_id} — {products}")
    
    # ── BRANDING ─────────────────────────────────────────────
    
    def set_branding(self, client_id: str, **branding_kwargs):
        """
        Configurar branding de un cliente.
        
        Uso:
            p.set_branding("agf",
                logo_path="logos/agf.png",
                primary_color="#1B3A5C",
                accent_color="#C9963B",
                font_family="Georgia",
                footer_text="AGF Capital — Investigación Propietaria"
            )
        """
        self._update_json_field(client_id, "branding_json", branding_kwargs)
        logger.info(f"🎨 Branding actualizado: {client_id}")
    
    def get_branding(self, client_id: str) -> Branding:
        """Obtener branding de un cliente."""
        data = self._get_json_field(client_id, "branding_json")
        return Branding(**{k: v for k, v in data.items() if hasattr(Branding, k)})
    
    # ── AI PROMPTS ───────────────────────────────────────────
    
    def set_ai_prompts(self, client_id: str, **prompt_kwargs):
        """
        Configurar prompts de IA para un cliente.
        
        Uso:
            p.set_ai_prompts("agf",
                tone="Técnico institucional",
                audience="Portfolio managers y CIO",
                focus="Renta fija local y LatAm",
                podcast_intro="Buenos días equipo de AGF...",
                custom_instructions="Siempre mencionar TPM y UF"
            )
        """
        self._update_json_field(client_id, "ai_prompts_json", prompt_kwargs)
        logger.info(f"🤖 AI Prompts actualizados: {client_id}")
    
    def get_ai_prompts(self, client_id: str) -> AIPrompts:
        """Obtener prompts de un cliente."""
        data = self._get_json_field(client_id, "ai_prompts_json")
        return AIPrompts(**{k: v for k, v in data.items() if hasattr(AIPrompts, k)})
    
    def build_system_prompt(self, client_id: str, base_prompt: str) -> str:
        """
        Construir el system prompt completo para un cliente.
        Inyecta tono, audiencia, foco e instrucciones custom.
        """
        prompts = self.get_ai_prompts(client_id)
        additions = []
        
        if prompts.tone:
            additions.append(f"Tono de escritura: {prompts.tone}")
        if prompts.audience:
            additions.append(f"Audiencia objetivo: {prompts.audience}")
        if prompts.focus:
            additions.append(f"Foco temático: {prompts.focus}")
        if prompts.custom_instructions:
            additions.append(f"Instrucciones adicionales: {prompts.custom_instructions}")
        
        if additions:
            return (
                base_prompt
                + "\n\n--- Configuración del cliente ---\n"
                + "\n".join(f"• {a}" for a in additions)
            )
        return base_prompt
    
    # ── DELIVERY ─────────────────────────────────────────────
    
    def set_delivery(self, client_id: str, **delivery_kwargs):
        """
        Configurar entrega para un cliente.
        
        Uso:
            p.set_delivery("agf",
                email_to=["pm@agf.cl", "cio@agf.cl"],
                email_cc=["research@agf.cl"],
                email_from_name="AGF Research",
                schedule="am_pm"
            )
        """
        self._update_json_field(client_id, "delivery_json", delivery_kwargs)
        logger.info(f"📧 Delivery actualizado: {client_id}")
    
    def get_delivery(self, client_id: str) -> DeliveryConfig:
        """Obtener config de entrega."""
        data = self._get_json_field(client_id, "delivery_json")
        return DeliveryConfig(**{k: v for k, v in data.items() if hasattr(DeliveryConfig, k)})
    
    # ── JOB QUEUE ────────────────────────────────────────────
    
    def queue_job(
        self,
        client_id: str,
        product: str,
        triggered_by: str = "scheduler",
        trigger_meta: dict = None,
    ) -> int:
        """Encolar un trabajo para un cliente."""
        with self.db.connect() as conn:
            cursor = conn.execute("""
                INSERT INTO jobs (client_id, product, triggered_by, trigger_meta)
                VALUES (?, ?, ?, ?)
            """, (client_id, product, triggered_by, json.dumps(trigger_meta or {})))
            job_id = cursor.lastrowid
        
        logger.debug(f"📋 Job encolado: #{job_id} {client_id}/{product}")
        return job_id
    
    def start_job(self, job_id: int):
        """Marcar un job como iniciado."""
        with self.db.connect() as conn:
            conn.execute("""
                UPDATE jobs SET status = 'running', started_at = datetime('now')
                WHERE job_id = ?
            """, (job_id,))
    
    def complete_job(self, job_id: int, output_path: str = ""):
        """Marcar un job como completado."""
        with self.db.connect() as conn:
            conn.execute("""
                UPDATE jobs SET
                    status = 'completed',
                    completed_at = datetime('now'),
                    output_path = ?,
                    duration_secs = (
                        julianday(datetime('now')) - julianday(started_at)
                    ) * 86400
                WHERE job_id = ?
            """, (output_path, job_id))
    
    def fail_job(self, job_id: int, error: str):
        """Marcar un job como fallido."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT retry_count FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            
            conn.execute("""
                UPDATE jobs SET
                    status = 'failed',
                    completed_at = datetime('now'),
                    error_message = ?,
                    retry_count = retry_count + 1
                WHERE job_id = ?
            """, (error, job_id))
        
        logger.error(f"❌ Job #{job_id} falló: {error}")
    
    def get_pending_jobs(self, product: str = None) -> List[dict]:
        """Obtener jobs pendientes."""
        with self.db.connect() as conn:
            if product:
                rows = conn.execute("""
                    SELECT j.*, c.company_name FROM jobs j
                    JOIN clients c ON j.client_id = c.client_id
                    WHERE j.status = 'pending' AND j.product = ?
                    ORDER BY j.queued_at
                """, (product,)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT j.*, c.company_name FROM jobs j
                    JOIN clients c ON j.client_id = c.client_id
                    WHERE j.status = 'pending'
                    ORDER BY j.queued_at
                """).fetchall()
        
        return [dict(r) for r in rows]
    
    # ── PIPELINE RUNNERS ─────────────────────────────────────
    
    def run_daily_pipeline(self, period: str = "am"):
        """
        Corre el pipeline diario para todos los clientes activos.
        
        Llamar desde el .bat:
            python -c "from greybark_platform import Platform; Platform().run_daily_pipeline('am')"
        
        O más simple, crear run_daily.py:
            from greybark_platform import Platform
            import sys
            Platform().run_daily_pipeline(sys.argv[1])  # 'am' o 'pm'
        """
        product_field = f"product_daily_{period}"
        
        logger.info(f"{'='*60}")
        logger.info(f"  GREYBARK DAILY PIPELINE — {period.upper()}")
        logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")
        
        # 1. Obtener clientes activos con este producto
        clients = self._get_clients_with_product(product_field)
        logger.info(f"📋 {len(clients)} clientes activos con daily_{period}")
        
        if not clients:
            logger.info("No hay clientes para procesar. Saliendo.")
            return
        
        # 2. Encolar jobs
        job_ids = []
        for client in clients:
            job_id = self.queue_job(client.client_id, f"daily_{period}")
            job_ids.append((job_id, client))
        
        # 3. Procesar cada cliente
        results = {"completed": 0, "failed": 0, "skipped": 0}
        
        for job_id, client in job_ids:
            try:
                self.start_job(job_id)
                logger.info(f"  🔄 Procesando: {client.company_name}...")
                output_dir = self._ensure_output_dir(client.client_id)

                from pipeline_steps import (
                    generate_report, format_html, generate_podcast,
                    send_email, build_branding_dict, get_base_system_prompt
                )

                # 1. Report .md con prompt personalizado
                system_prompt = self.build_system_prompt(
                    client.client_id, get_base_system_prompt())
                data_path = os.environ.get(
                    "GREYBARK_DATA_JSON", "daily_market_snapshot.json")
                md_path = generate_report(
                    data_path, period.upper(), system_prompt, str(output_dir))

                # 2. HTML con branding del cliente
                branding = build_branding_dict(client)
                html_path = format_html(
                    md_path, branding=branding, output_dir=str(output_dir))

                # 3. Podcast (solo si contratado)
                podcast_path = None
                if client.product_podcast:
                    intro = client.ai_prompts.podcast_intro or None
                    outro = client.ai_prompts.podcast_outro or None
                    podcast_path = generate_podcast(
                        html_path, period.upper(), intro, outro, str(output_dir))
                    if podcast_path:
                        self._increment_usage(client.client_id, "podcast")

                # 4. Email
                if client.delivery.email_to:
                    today_str = datetime.now().strftime("%d-%m-%Y")
                    label = "Matutino" if period == "am" else "Vespertino"
                    subject = f"{client.company_name} - Reporte {label} {today_str}"
                    recipients = [{"name": "", "email": e}
                                  for e in client.delivery.email_to]
                    send_email(html_path, recipients,
                               client.delivery.email_from_name, subject,
                               podcast_path)

                self.complete_job(job_id, str(output_dir))
                self._increment_usage(client.client_id, f"daily_{period}")
                results["completed"] += 1
                logger.info(f"  ✅ {client.company_name} — OK")
                
            except Exception as e:
                self.fail_job(job_id, str(e))
                results["failed"] += 1
                logger.error(f"  ❌ {client.company_name} — {e}")
                # Continuar con el siguiente cliente (no detener pipeline)
                continue
        
        # 4. Resumen
        logger.info(f"\n{'─'*40}")
        logger.info(f"  Resumen: ✅ {results['completed']} | ❌ {results['failed']} | ⏭️ {results['skipped']}")
        logger.info(f"{'─'*40}\n")
    
    def run_ai_council(
        self,
        client_id: str,
        directives: str = "",
        vision: str = "",
        horizon: str = "3-6 meses",
        triggered_by: str = "dashboard",
    ) -> dict:
        """
        Correr el AI Council para un cliente específico.
        Llamado desde el dashboard Streamlit.
        
        Returns:
            dict con paths a los 5 reportes generados
        """
        client = self.get_client(client_id)
        if not client:
            raise ValueError(f"Cliente no encontrado: {client_id}")
        
        if not client.product_ai_council:
            raise ValueError(f"Cliente {client_id} no tiene AI Council contratado")
        
        meta = {
            "directives": directives,
            "vision": vision,
            "horizon": horizon,
        }
        
        job_id = self.queue_job(client_id, "ai_council", triggered_by, meta)
        self.start_job(job_id)
        
        try:
            output_dir = self._ensure_output_dir(client_id)

            from council_steps import (
                run_council_pipeline, build_council_branding, build_client_prompts
            )

            # Build client customization
            branding = build_council_branding(client)
            client_prompts = build_client_prompts(client)

            # Combine directives with vision/horizon context
            full_directives = directives or ""
            if vision:
                full_directives += f"\n\nVisión del cliente: {vision}"
            if horizon:
                full_directives += f"\nHorizonte de inversión: {horizon}"

            # Run the full pipeline
            result = run_council_pipeline(
                directives=full_directives,
                branding=branding,
                output_dir=str(output_dir),
                client_prompts=client_prompts,
            )

            reports = result.get("report_paths", {})

            self.complete_job(job_id, str(output_dir))
            self._increment_usage(client_id, "ai_council")

            logger.info(f"✅ AI Council completado: {client.company_name}")
            return reports

        except Exception as e:
            self.fail_job(job_id, str(e))
            raise
    
    # ── USAGE & BILLING ──────────────────────────────────────
    
    def get_usage(self, client_id: str, month: str = None) -> dict:
        """
        Obtener uso de un cliente para un mes.
        
        Uso:
            p.get_usage("agf", "2026-03")
            p.get_usage("agf")  # mes actual
        """
        if not month:
            month = datetime.now().strftime("%Y-%m")
        
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM usage_monthly WHERE client_id = ? AND month = ?",
                (client_id, month)
            ).fetchone()
        
        if row:
            return dict(row)
        return {
            "client_id": client_id, "month": month,
            "daily_am_count": 0, "daily_pm_count": 0,
            "ai_council_count": 0, "podcast_count": 0,
            "intel_count": 0, "api_cost_usd": 0.0
        }
    
    def get_billing_summary(self, month: str = None) -> List[dict]:
        """Resumen de billing para todos los clientes en un mes."""
        if not month:
            month = datetime.now().strftime("%Y-%m")
        
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT 
                    c.client_id,
                    c.company_name,
                    c.plan,
                    c.monthly_fee,
                    c.currency,
                    COALESCE(u.daily_am_count, 0) as daily_am_count,
                    COALESCE(u.daily_pm_count, 0) as daily_pm_count,
                    COALESCE(u.ai_council_count, 0) as ai_council_count,
                    COALESCE(u.podcast_count, 0) as podcast_count,
                    COALESCE(u.api_cost_usd, 0) as api_cost_usd
                FROM clients c
                LEFT JOIN usage_monthly u ON c.client_id = u.client_id AND u.month = ?
                WHERE c.active = 1
                ORDER BY c.monthly_fee DESC
            """, (month,)).fetchall()
        
        return [dict(r) for r in rows]
    
    # ── DASHBOARD HELPERS (para Streamlit) ───────────────────
    
    def get_client_for_dashboard(self, client_id: str) -> dict:
        """
        Paquete completo para renderizar el dashboard de un cliente.
        Retorna todo lo necesario en una sola llamada.
        """
        client = self.get_client(client_id)
        if not client:
            return None
        
        branding = self.get_branding(client_id)
        prompts = self.get_ai_prompts(client_id)
        delivery = self.get_delivery(client_id)
        usage = self.get_usage(client_id)
        
        # Últimos jobs
        with self.db.connect() as conn:
            recent_jobs = conn.execute("""
                SELECT product, status, completed_at, output_path
                FROM jobs WHERE client_id = ?
                ORDER BY queued_at DESC LIMIT 10
            """, (client_id,)).fetchall()
        
        return {
            "client": client,
            "branding": branding,
            "prompts": prompts,
            "delivery": delivery,
            "usage": usage,
            "recent_jobs": [dict(j) for j in recent_jobs],
            "css_vars": self._generate_css(branding),
        }
    
    def authenticate_token(self, token: str) -> Optional[str]:
        """
        Validar un token de acceso y retornar el client_id.
        
        Para producción: reemplazar con JWT o API keys hasheadas.
        Por ahora: el token es simplemente el client_id (simple pero funcional para 5 clientes).
        """
        # TODO: Implementar auth real cuando escales
        # Por ahora: token = client_id
        client = self.get_client(token)
        if client and client.active:
            return client.client_id
        return None
    
    # ── ADMIN HELPERS ────────────────────────────────────────
    
    def get_dashboard_stats(self) -> dict:
        """Stats para un panel admin."""
        with self.db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM clients WHERE active=1").fetchone()[0]
            mrr = conn.execute("SELECT COALESCE(SUM(monthly_fee),0) FROM clients WHERE active=1").fetchone()[0]
            
            today = datetime.now().strftime("%Y-%m-%d")
            jobs_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE date(queued_at) = ?", (today,)
            ).fetchone()[0]
            failed_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE date(queued_at) = ? AND status='failed'",
                (today,)
            ).fetchone()[0]
        
        return {
            "total_clients": total,
            "active_clients": active,
            "mrr_usd": mrr,
            "jobs_today": jobs_today,
            "failed_today": failed_today,
        }
    
    def get_failed_jobs(self, days: int = 7) -> List[dict]:
        """Jobs fallidos en los últimos N días."""
        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT j.*, c.company_name FROM jobs j
                JOIN clients c ON j.client_id = c.client_id
                WHERE j.status = 'failed'
                AND j.queued_at > datetime('now', ?)
                ORDER BY j.queued_at DESC
            """, (f"-{days} days",)).fetchall()
        
        return [dict(r) for r in rows]
    
    def retry_failed_jobs(self, client_id: str = None):
        """Re-encolar jobs fallidos."""
        with self.db.connect() as conn:
            if client_id:
                rows = conn.execute("""
                    SELECT * FROM jobs WHERE status = 'failed' AND client_id = ?
                """, (client_id,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM jobs WHERE status = 'failed' AND retry_count < 3"
                ).fetchall()
        
        count = 0
        for row in rows:
            self.queue_job(
                row['client_id'], row['product'],
                triggered_by="retry",
                trigger_meta=json.loads(row['trigger_meta'])
            )
            count += 1
        
        logger.info(f"🔄 {count} jobs re-encolados")
        return count
    
    # ── EXPORT / IMPORT (migración) ──────────────────────────
    
    def export_client_json(self, client_id: str) -> dict:
        """Exportar un cliente como JSON (compatible con el formato anterior)."""
        client = self.get_client(client_id)
        branding = self.get_branding(client_id)
        prompts = self.get_ai_prompts(client_id)
        delivery = self.get_delivery(client_id)
        
        return {
            "client_id": client.client_id,
            "company_name": client.company_name,
            "active": client.active,
            "branding": asdict(branding),
            "ai_prompts": asdict(prompts),
            "products": {
                "daily_am": client.product_daily_am,
                "daily_pm": client.product_daily_pm,
                "ai_council": client.product_ai_council,
                "podcast": client.product_podcast,
                "intelligence_briefing": client.product_intel_briefing,
            },
            "delivery": asdict(delivery),
            "plan": client.plan,
            "monthly_fee": client.monthly_fee,
            "start_date": client.start_date,
        }
    
    def import_client_json(self, data: dict):
        """Importar un cliente desde JSON (compatible con formato anterior)."""
        cid = data["client_id"]
        
        self.add_client(
            client_id=cid,
            company_name=data.get("company_name", ""),
            plan=data.get("plan", "starter"),
            monthly_fee=data.get("monthly_fee", 500),
        )
        
        if "products" in data:
            self.set_products(cid, **data["products"])
        if "branding" in data:
            self.set_branding(cid, **data["branding"])
        if "ai_prompts" in data:
            self.set_ai_prompts(cid, **data["ai_prompts"])
        if "delivery" in data:
            self.set_delivery(cid, **data["delivery"])
        
        logger.info(f"📥 Cliente importado: {cid}")
    
    # ── PRIVATE HELPERS ──────────────────────────────────────
    
    def _row_to_client(self, row) -> ClientRecord:
        """Convertir row SQLite a ClientRecord."""
        branding_data = json.loads(row["branding_json"] or "{}")
        prompts_data = json.loads(row["ai_prompts_json"] or "{}")
        delivery_data = json.loads(row["delivery_json"] or "{}")
        
        return ClientRecord(
            client_id=row["client_id"],
            company_name=row["company_name"],
            active=bool(row["active"]),
            product_daily_am=bool(row["product_daily_am"]),
            product_daily_pm=bool(row["product_daily_pm"]),
            product_ai_council=bool(row["product_ai_council"]),
            product_podcast=bool(row["product_podcast"]),
            product_intel_briefing=bool(row["product_intel_briefing"]),
            branding=Branding(**{k: v for k, v in branding_data.items() if hasattr(Branding, k)}),
            ai_prompts=AIPrompts(**{k: v for k, v in prompts_data.items() if hasattr(AIPrompts, k)}),
            delivery=DeliveryConfig(**{k: v for k, v in delivery_data.items() if hasattr(DeliveryConfig, k)}),
            plan=row["plan"],
            monthly_fee=row["monthly_fee"],
            currency=row["currency"],
            billing_email=row["billing_email"],
            start_date=row["start_date"],
            contact_name=row["contact_name"],
            contact_phone=row["contact_phone"],
            notes=row["notes"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    
    def _get_clients_with_product(self, product_field: str) -> List[ClientRecord]:
        """Obtener clientes activos que tienen un producto específico."""
        with self.db.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM clients WHERE active = 1 AND {product_field} = 1 ORDER BY company_name"
            ).fetchall()
        return [self._row_to_client(r) for r in rows]
    
    def _update_json_field(self, client_id: str, field: str, new_data: dict):
        """Merge JSON field (no sobrescribe, hace merge)."""
        with self.db.connect() as conn:
            row = conn.execute(
                f"SELECT {field} FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
            
            existing = json.loads(row[field] or "{}") if row else {}
            existing.update(new_data)
            
            conn.execute(
                f"UPDATE clients SET {field} = ?, updated_at = datetime('now') WHERE client_id = ?",
                (json.dumps(existing, ensure_ascii=False), client_id)
            )
            self._audit(conn, f"{field}_updated", client_id, new_data)
    
    def _get_json_field(self, client_id: str, field: str) -> dict:
        """Leer un JSON field."""
        with self.db.connect() as conn:
            row = conn.execute(
                f"SELECT {field} FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        
        if row:
            return json.loads(row[field] or "{}")
        return {}
    
    def _ensure_output_dir(self, client_id: str) -> Path:
        """Crear directorio de output para un cliente + fecha."""
        today = datetime.now().strftime("%Y-%m-%d")
        output_dir = self.output_base / client_id / today
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def _increment_usage(self, client_id: str, product: str):
        """Incrementar contador de uso mensual."""
        month = datetime.now().strftime("%Y-%m")
        field_map = {
            "daily_am": "daily_am_count",
            "daily_pm": "daily_pm_count",
            "ai_council": "ai_council_count",
            "podcast": "podcast_count",
            "intel_briefing": "intel_count",
        }
        field = field_map.get(product)
        if not field:
            return
        
        with self.db.connect() as conn:
            conn.execute(f"""
                INSERT INTO usage_monthly (client_id, month, {field})
                VALUES (?, ?, 1)
                ON CONFLICT(client_id, month)
                DO UPDATE SET {field} = {field} + 1, updated_at = datetime('now')
            """, (client_id, month))
    
    def _generate_css(self, branding: Branding) -> str:
        """Generar CSS custom para un cliente."""
        return f"""
        <style>
            :root {{
                --gb-primary: {branding.primary_color};
                --gb-accent: {branding.accent_color};
                --gb-font: '{branding.font_family}', serif;
            }}
            .stApp {{ font-family: var(--gb-font); }}
            .main-header {{ color: var(--gb-primary); }}
            .stButton > button {{
                background-color: var(--gb-accent) !important;
                color: white !important;
            }}
            .stButton > button:hover {{
                opacity: 0.85;
            }}
        </style>
        """
    
    def _audit(self, conn, action: str, client_id: str, details: dict):
        """Registrar acción en audit log."""
        conn.execute(
            "INSERT INTO audit_log (action, client_id, details) VALUES (?, ?, ?)",
            (action, client_id, json.dumps(details, ensure_ascii=False, default=str))
        )


# ══════════════════════════════════════════════════════════════
# CLI / DEMO
# ══════════════════════════════════════════════════════════════

def demo():
    """Demostración del sistema completo."""
    import tempfile
    
    # Usar DB temporal para demo
    db_path = os.path.join(tempfile.gettempdir(), "greybark_demo.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    
    p = Platform(db_path)
    
    print("\n" + "=" * 60)
    print("  GREYBARK PLATFORM — Demo")
    print("=" * 60)
    
    # Crear clientes
    print("\n📋 Creando clientes...")
    
    p.add_client("agf_capital", "AGF Capital Advisors",
                 plan="profesional", monthly_fee=1500,
                 contact_name="Juan Pérez", billing_email="billing@agf.cl")
    
    p.add_client("fo_andino", "Family Office Andino",
                 plan="enterprise", monthly_fee=5000,
                 contact_name="María González")
    
    p.add_client("corredora_sur", "Corredora del Sur",
                 plan="starter", monthly_fee=500,
                 contact_name="Pedro López")
    
    # Configurar productos
    print("\n📦 Configurando productos...")
    
    p.set_products("agf_capital",
                   daily_am=True, daily_pm=True,
                   ai_council=True, podcast=True)
    
    p.set_products("fo_andino",
                   daily_am=True, daily_pm=True,
                   ai_council=True, podcast=True,
                   intel_briefing=True)
    
    p.set_products("corredora_sur",
                   daily_am=True, daily_pm=False,
                   ai_council=False, podcast=True)
    
    # Branding
    print("\n🎨 Configurando branding...")
    
    p.set_branding("agf_capital",
                   primary_color="#1B3A5C", accent_color="#C9963B",
                   font_family="Georgia",
                   footer_text="AGF Capital — Investigación Propietaria")
    
    p.set_branding("fo_andino",
                   primary_color="#2D5A27", accent_color="#D4AF37",
                   font_family="Palatino",
                   footer_text="Family Office Andino — Confidencial")
    
    p.set_branding("corredora_sur",
                   primary_color="#8B0000", accent_color="#FFD700",
                   font_family="Helvetica")
    
    # AI Prompts
    print("\n🤖 Configurando AI prompts...")
    
    p.set_ai_prompts("agf_capital",
                     tone="Técnico institucional, sin jerga coloquial",
                     audience="Portfolio managers y comité de inversiones",
                     focus="Sesgo hacia renta fija local y LatAm",
                     podcast_intro="Buenos días, equipo de AGF Capital.")
    
    p.set_ai_prompts("fo_andino",
                     tone="Ejecutivo y conciso, con datos específicos",
                     audience="Familia y asesores patrimoniales",
                     focus="Preservación de capital, oportunidades globales",
                     podcast_intro="Buenos días, les presentamos el análisis de hoy.",
                     custom_instructions="Siempre incluir sección de riesgos geopolíticos")
    
    p.set_ai_prompts("corredora_sur",
                     tone="Lenguaje no muy técnico, accesible",
                     audience="Asesores de inversión retail",
                     focus="Acciones locales y fondos mutuos",
                     podcast_intro="Hola, aquí el resumen de mercado del día.")
    
    # Delivery
    print("\n📧 Configurando delivery...")
    
    p.set_delivery("agf_capital",
                   email_to=["pm@agfcapital.cl", "cio@agfcapital.cl"],
                   email_from_name="AGF Research")
    
    p.set_delivery("fo_andino",
                   email_to=["familia@andino.cl"],
                   email_cc=["asesor@andino.cl"],
                   email_from_name="Andino Investment Office")
    
    p.set_delivery("corredora_sur",
                   email_to=["mesa@corredorasur.cl"],
                   email_from_name="Corredora del Sur Research")
    
    # Listar
    print("\n" + "─" * 60)
    print("  CLIENTES ACTIVOS")
    print("─" * 60)
    
    for c in p.list_clients():
        products = []
        if c.product_daily_am: products.append("AM")
        if c.product_daily_pm: products.append("PM")
        if c.product_ai_council: products.append("Council")
        if c.product_podcast: products.append("Podcast")
        if c.product_intel_briefing: products.append("Intel")
        
        print(f"  {c.company_name}")
        print(f"    Plan: {c.plan} (${c.monthly_fee}/mes)")
        print(f"    Productos: {' · '.join(products)}")
        print(f"    Tono IA: {c.ai_prompts.tone[:50]}...")
        print()
    
    # Stats
    stats = p.get_dashboard_stats()
    print("─" * 60)
    print(f"  📊 {stats['active_clients']} clientes activos")
    print(f"  💰 MRR: ${stats['mrr_usd']:,.0f} USD")
    print("─" * 60)
    
    # Simular pipeline
    print("\n⚡ Simulando daily pipeline AM...")
    p.run_daily_pipeline("am")
    
    # Export
    print("\n📤 Export JSON de agf_capital:")
    exported = p.export_client_json("agf_capital")
    print(json.dumps(exported, indent=2, ensure_ascii=False)[:500] + "...")
    
    # Cleanup
    os.remove(db_path)
    print("\n✅ Demo completada!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo()
    elif len(sys.argv) > 1 and sys.argv[1] == "daily":
        period = sys.argv[2] if len(sys.argv) > 2 else "am"
        Platform().run_daily_pipeline(period)
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = Platform().get_dashboard_stats()
        for k, v in stats.items():
            print(f"  {k}: {v}")
    else:
        print("Uso:")
        print("  python greybark_platform.py demo     — Correr demo")
        print("  python greybark_platform.py daily am  — Pipeline diario AM")
        print("  python greybark_platform.py daily pm  — Pipeline diario PM")
        print("  python greybark_platform.py stats     — Ver estadísticas")

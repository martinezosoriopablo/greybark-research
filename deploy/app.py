"""
app.py — FastAPI Client Portal
===============================
Professional client-facing portal replacing Streamlit dashboard.
Routes: login, dashboard, pipeline, settings, reports, historico, system status.
"""

import os
import sys
import json
import uuid
import shutil
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import (
    FastAPI, Request, Depends, Form, BackgroundTasks,
    UploadFile, File, Query,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from deploy.auth import (
    create_access_token, decode_token, get_current_client,
    hash_password, verify_password, COOKIE_NAME,
)

# ── Logging ───────────────────────────────────────────────

logger = logging.getLogger("portal")

# ── Platform import ───────────────────────────────────────

# Support running from consejo_ia/ or from Docker /app/
_layout_dir = os.environ.get("GREYBARK_LAYOUT_DIR")
if not _layout_dir:
    # Local dev: deploy/app.py -> consejo_ia/deploy/ -> 4 levels up -> documentos/Layout
    _app_path = Path(__file__).resolve()
    try:
        _layout_dir = str(_app_path.parents[4] / "Layout")
    except IndexError:
        _layout_dir = str(_app_path.parent.parent / "layout")
if _layout_dir not in sys.path:
    sys.path.insert(0, _layout_dir)

from greybark_platform import Platform  # noqa: E402

# ── App setup ─────────────────────────────────────────────

app = FastAPI(title="Greybark Research Portal", docs_url=None, redoc_url=None)

_deploy_dir = Path(__file__).resolve().parent
_consejo_dir = _deploy_dir.parent  # consejo_ia/

app.mount("/static", StaticFiles(directory=str(_deploy_dir / "static")), name="static")

templates = Jinja2Templates(directory=str(_deploy_dir / "web_templates"))

# In-memory job tracker (job_id → status dict)
_jobs: Dict[str, dict] = {}

# Passwords file: JSON {client_id: bcrypt_hash}
_PASSWORDS_FILE = os.environ.get(
    "GREYBARK_PASSWORDS", str(Path(_layout_dir) / "passwords.json")
)

# Key directories inside consejo_ia/
_RESEARCH_DIR = _consejo_dir / "input" / "research"
_DIRECTIVES_FILE = _consejo_dir / "input" / "user_directives.txt"
_COUNCIL_DIR = _consejo_dir / "output" / "council"
_REPORTS_DIR = _consejo_dir / "output" / "reports"

# Font options (mirrors dashboard.py)
FONT_OPTIONS = [
    "Georgia", "'Segoe UI', sans-serif", "Arial, sans-serif",
    "'Times New Roman', serif", "Helvetica, sans-serif",
    "Verdana, sans-serif", "'Roboto', sans-serif", "'Open Sans', sans-serif",
]
FONT_LABELS = [
    "Georgia", "Segoe UI", "Arial", "Times New Roman",
    "Helvetica", "Verdana", "Roboto", "Open Sans",
]


def _load_passwords() -> dict:
    if os.path.exists(_PASSWORDS_FILE):
        with open(_PASSWORDS_FILE) as f:
            return json.load(f)
    return {}


def _get_platform() -> Platform:
    return Platform()


# ── Helpers ───────────────────────────────────────────────

def _client_context(request: Request, client_id: str, platform: Platform, **extra) -> dict:
    """Build template context with client branding."""
    data = platform.get_client_for_dashboard(client_id)
    if not data:
        return {"request": request, "client": None}

    client = data["client"]
    branding = data["branding"]

    logo_url = ""
    if branding.logo_path:
        if os.path.isabs(branding.logo_path) or ":" in branding.logo_path:
            logo_url = f"/logo/{client_id}"
        else:
            logo_url = f"/static/{branding.logo_path}"

    ctx = {
        "request": request,
        "client": client,
        "branding": branding,
        "usage": data["usage"],
        "recent_jobs": data["recent_jobs"],
        "primary_color": branding.primary_color,
        "accent_color": branding.accent_color,
        "font_family": branding.font_family,
        "company_name": client.company_name,
        "logo_path": logo_url,
    }
    ctx.update(extra)
    return ctx


def _get_client_reports(client_id: str, platform: Platform) -> list:
    """Discover HTML reports for a client with type detection.

    Only searches the client-specific output dir so each client sees
    only their own reports.
    """
    output_base = os.environ.get("GREYBARK_OUTPUT", str(Path(_layout_dir) / "output"))
    client_dir = Path(output_base) / client_id

    if not client_dir.exists():
        return []

    reports = []
    seen = set()

    # Collect all HTML files from client dir
    all_files = []
    for html_file in client_dir.rglob("*.html"):
        all_files.append((html_file, client_dir))

    all_files.sort(key=lambda pair: pair[0].stat().st_mtime, reverse=True)

    for html_file, search_dir in all_files:
        if html_file.name in seen:
            continue
        seen.add(html_file.name)

        stat = html_file.stat()
        name_lower = html_file.name.lower()
        report_type = "otro"
        if "intelligence_briefing" in name_lower:
            report_type = "briefing"
        elif "macro" in name_lower:
            report_type = "macro"
        elif "rv_" in name_lower:
            report_type = "rv"
        elif "rf_" in name_lower:
            report_type = "rf"
        elif "asset_allocation" in name_lower:
            report_type = "aa"
        elif "daily_report" in name_lower:
            report_type = "daily"

        reports.append({
            "name": html_file.name,
            "path": str(html_file),
            "rel_path": html_file.relative_to(search_dir).as_posix(),
            "source_dir": str(search_dir),
            "size": stat.st_size,
            "size_fmt": _format_size(stat.st_size),
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "date_folder": html_file.parent.name,
            "type": report_type,
        })

    return reports[:50]


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _get_research_files() -> List[dict]:
    """List research files in input/research/."""
    files = []
    _RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("*.txt", "*.md", "*.pdf"):
        for f in sorted(_RESEARCH_DIR.glob(ext)):
            if f.name.upper().startswith("README"):
                continue
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "size_fmt": _format_size(f.stat().st_size),
                "modified": datetime.fromtimestamp(f.stat().st_mtime),
            })
    return files


def _get_directives() -> str:
    """Read current user directives (without comment lines)."""
    if _DIRECTIVES_FILE.exists():
        text = _DIRECTIVES_FILE.read_text(encoding="utf-8")
        lines = [l.rstrip() for l in text.split("\n")
                 if l.strip() and not l.strip().startswith("#")]
        return "\n".join(lines)
    return ""


def _save_directives(content: str):
    """Save directives preserving standard header."""
    header = """# =============================================================
# DIRECTIVAS DEL USUARIO PARA EL AI COUNCIL
# =============================================================
#
# Edita este archivo ANTES de correr el consejo IA.
# Todo lo que escribas aqui sera leido por TODOS los agentes
# del panel y por el CIO/Refinador.
#
# Las lineas que empiezan con # son ignoradas.
# =============================================================

"""
    _DIRECTIVES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DIRECTIVES_FILE.write_text(header + content, encoding="utf-8")


def _get_recent_council_results(client_id: str = None) -> List[dict]:
    """List recent council session results."""
    results = []
    _COUNCIL_DIR.mkdir(parents=True, exist_ok=True)

    if client_id:
        patterns = [f"{client_id}_council_*.json", "council_result_*.json"]
    else:
        patterns = ["council_result_*.json"]

    all_files = []
    for pat in patterns:
        all_files.extend(_COUNCIL_DIR.glob(pat))
    all_files = sorted(set(all_files), key=lambda f: f.stat().st_mtime, reverse=True)

    if client_id:
        filtered = []
        for f in all_files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                meta = data.get("metadata", {})
                if meta.get("client") == client_id or f.name.startswith(f"{client_id}_"):
                    filtered.append(f)
            except Exception:
                continue
        all_files = filtered[:10]
    else:
        all_files = all_files[:10]

    for f in all_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            meta = data.get("metadata", {})
            results.append({
                "file": f.name,
                "timestamp": meta.get("timestamp", ""),
                "duration": meta.get("duration_seconds", 0),
                "report_type": meta.get("report_type", ""),
                "aborted": data.get("aborted", False),
            })
        except Exception:
            continue
    return results


def _dir_size(path: Path) -> int:
    total = 0
    if path.exists():
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total


def _copy_reports_to_client(client_id: str):
    """Copy newly generated reports from shared output/reports/ to the client folder."""
    output_base = os.environ.get("GREYBARK_OUTPUT", str(Path(_layout_dir) / "output"))
    client_dir = Path(output_base) / client_id
    shared_reports = _consejo_dir / "output" / "reports"

    if not shared_reports.exists():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    dest_dir = client_dir / today
    dest_dir.mkdir(parents=True, exist_ok=True)

    for html_file in shared_reports.glob("*.html"):
        try:
            shutil.copy2(str(html_file), str(dest_dir / html_file.name))
        except Exception as e:
            logger.warning(f"Could not copy {html_file.name} to client {client_id}: {e}")


def _run_system_checks() -> List[dict]:
    """Run system health checks (API keys, packages, disk)."""
    checks = []

    # API Keys
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    try:
        from greybark.config import config as gbk_config, CLAUDE_API_KEY
        has_anthropic = has_anthropic or bool(CLAUDE_API_KEY)
        has_fred = bool(getattr(gbk_config.fred, "api_key", "")) or bool(os.environ.get("FRED_API_KEY"))
        has_bcch = bool(getattr(gbk_config.bcch, "user", "")) and bool(getattr(gbk_config.bcch, "password", ""))
        has_av = bool(getattr(gbk_config.alphavantage, "api_key", ""))
    except Exception:
        has_fred = bool(os.environ.get("FRED_API_KEY"))
        has_bcch = False
        has_av = False

    checks.append({"name": "Anthropic API Key", "ok": has_anthropic, "detail": "Council + Research"})
    checks.append({"name": "FRED API Key", "ok": has_fred, "detail": "Datos macro USA"})
    checks.append({"name": "BCCh API", "ok": has_bcch, "detail": "Datos Chile"})
    checks.append({"name": "AlphaVantage API", "ok": has_av, "detail": "Earnings, factors"})

    # Platform
    try:
        p = _get_platform()
        checks.append({"name": "Platform DB", "ok": True, "detail": "Conectada"})
    except Exception:
        checks.append({"name": "Platform DB", "ok": False, "detail": "Error"})

    # Python packages
    packages = ["anthropic", "yfinance", "pdfplumber", "pandas", "matplotlib"]
    for pkg in packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, "__version__", "?")
            checks.append({"name": f"Python: {pkg}", "ok": True, "detail": f"v{ver}"})
        except ImportError:
            checks.append({"name": f"Python: {pkg}", "ok": False, "detail": "No instalado"})

    return checks


def _get_disk_usage() -> List[dict]:
    """Get disk usage for key directories."""
    dirs = [
        ("output/council/", _COUNCIL_DIR),
        ("output/reports/", _REPORTS_DIR),
        ("input/research/", _RESEARCH_DIR),
    ]
    usage = []
    for label, path in dirs:
        size = _dir_size(path)
        n_files = len(list(path.glob("*"))) if path.exists() else 0
        usage.append({"label": label, "size_fmt": _format_size(size), "n_files": n_files})
    return usage


# ── Routes: Auth ──────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
    })


@app.post("/login")
async def login_submit(
    request: Request,
    client_id: str = Form(...),
    password: str = Form(...),
):
    platform = _get_platform()

    client = platform.get_client(client_id)
    if not client or not client.active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Cliente no encontrado o inactivo.",
        })

    passwords = _load_passwords()
    stored_hash = passwords.get(client_id)

    if stored_hash:
        if not verify_password(password, stored_hash):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Credenciales incorrectas.",
            })
    else:
        if password != client_id:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Credenciales incorrectas.",
            })

    token = create_access_token(client_id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=8 * 3600,
    )
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Routes: Dashboard ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, client_id: str = Depends(get_current_client)):
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)
    ctx = _client_context(request, client_id, platform, reports=reports[:5])
    return templates.TemplateResponse("dashboard.html", ctx)


# ── Routes: Pipeline ──────────────────────────────────────

def _run_pipeline_task(
    job_id: str,
    client_id: str,
    directives: str,
    reports: List[str],
    dry_run: bool = False,
    skip_collect: bool = False,
):
    """Background task: run AI Council pipeline as subprocess."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["progress"] = 5
    _jobs[job_id]["message"] = "Iniciando pipeline..."
    _jobs[job_id]["phases"] = {
        "fase_1": "pending", "fase_2": "pending", "fase_2_5": "pending",
        "fase_3": "pending", "fase_4": "pending", "fase_5": "pending",
    }

    try:
        cmd = [
            sys.executable,
            str(_consejo_dir / "run_monthly.py"),
            "--no-confirm",
        ]
        if dry_run:
            cmd.append("--dry-run")
        if skip_collect:
            cmd.append("--skip-collect")
        if reports:
            cmd.extend(["--reports"] + reports)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(_consejo_dir),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        log_lines = []
        phases = _jobs[job_id]["phases"]

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.rstrip()
                log_lines.append(line)
                _jobs[job_id]["log"] = log_lines[-100:]

                # Phase detection (same logic as dashboard.py)
                upper = line.upper()
                if "[FASE 1]" in line or "RECOPILACION" in upper or "CARGANDO DATOS" in upper:
                    phases["fase_1"] = "running"
                    _jobs[job_id]["progress"] = 10
                    _jobs[job_id]["message"] = "Fase 1: Recopilacion de datos..."
                elif "[FASE 2]" in line or "PREFLIGHT" in upper:
                    phases["fase_1"] = "done"
                    phases["fase_2"] = "running"
                    _jobs[job_id]["progress"] = 25
                    _jobs[job_id]["message"] = "Fase 2: Preflight check..."
                elif "INTELLIGENCE BRIEFING" in upper:
                    phases["fase_2"] = "done"
                    phases["fase_2_5"] = "running"
                    _jobs[job_id]["progress"] = 35
                    _jobs[job_id]["message"] = "Fase 2.5: Intelligence Briefing..."
                elif "[FASE 3]" in line or "AI COUNCIL SESSION" in line:
                    phases["fase_2"] = "done"
                    phases["fase_2_5"] = "done"
                    phases["fase_3"] = "running"
                    _jobs[job_id]["progress"] = 50
                    _jobs[job_id]["message"] = "Fase 3: AI Council en sesion..."
                elif "[FASE 4]" in line or "GENERACION DE REPORTES" in upper:
                    phases["fase_3"] = "done"
                    phases["fase_4"] = "running"
                    _jobs[job_id]["progress"] = 75
                    _jobs[job_id]["message"] = "Fase 4: Generando reportes..."
                elif "[FASE 5]" in line or "RESUMEN DEL PIPELINE" in upper:
                    phases["fase_4"] = "done"
                    phases["fase_5"] = "running"
                    _jobs[job_id]["progress"] = 90
                    _jobs[job_id]["message"] = "Fase 5: Resumen..."
                elif "PIPELINE COMPLETADO" in upper:
                    phases["fase_5"] = "done"

        return_code = process.returncode

        if return_code == 0:
            for k in phases:
                if phases[k] == "running":
                    phases[k] = "done"
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = "Pipeline completado exitosamente."

            # Copy generated reports to client-specific folder
            _copy_reports_to_client(client_id)
        else:
            for k in phases:
                if phases[k] == "running":
                    phases[k] = "error"
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = f"Pipeline termino con errores (codigo {return_code})"

        _jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        logger.exception(f"Pipeline failed for {client_id}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["message"] = f"Error: {str(e)[:200]}"
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()


@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page(
    request: Request,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    research_files = _get_research_files()
    directives = _get_directives()
    ctx = _client_context(
        request, client_id, platform,
        research_files=research_files,
        directives=directives,
    )
    return templates.TemplateResponse("pipeline.html", ctx)


@app.post("/pipeline/upload-research")
async def upload_research(
    request: Request,
    files: List[UploadFile] = File(...),
    client_id: str = Depends(get_current_client),
):
    _RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in (".pdf", ".txt", ".md"):
            continue
        if f.size and f.size > 50 * 1024 * 1024:
            continue
        dest = _RESEARCH_DIR / f.filename
        content = await f.read()
        dest.write_bytes(content)
        saved += 1

    return RedirectResponse(url=f"/pipeline?uploaded={saved}", status_code=303)


@app.post("/pipeline/delete-research/{filename}")
async def delete_research(
    filename: str,
    client_id: str = Depends(get_current_client),
):
    target = _RESEARCH_DIR / filename
    if target.exists() and target.parent.resolve() == _RESEARCH_DIR.resolve():
        target.unlink()
    return RedirectResponse(url="/pipeline", status_code=303)


@app.post("/pipeline/save-directives")
async def save_directives_route(
    client_id: str = Depends(get_current_client),
    directives: str = Form(""),
):
    _save_directives(directives)
    return RedirectResponse(url="/pipeline?saved=1", status_code=303)


@app.post("/pipeline/run")
async def run_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
    directives: str = Form(""),
    reports: List[str] = Form(default=[]),
    dry_run: bool = Form(default=False),
    skip_collect: bool = Form(default=False),
):
    platform = _get_platform()
    client = platform.get_client(client_id)

    if not client or not client.product_ai_council:
        return RedirectResponse(url="/?error=no_council", status_code=303)

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "client_id": client_id,
        "job_type": "council",
        "status": "queued",
        "progress": 0,
        "message": "En cola...",
        "phases": {},
        "log": [],
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }

    # Save directives before running
    if directives.strip():
        _save_directives(directives)

    background_tasks.add_task(
        _run_pipeline_task, job_id, client_id, directives,
        reports=reports, dry_run=dry_run, skip_collect=skip_collect,
    )

    return RedirectResponse(url=f"/status/{job_id}", status_code=303)


# Keep old POST endpoint for backward compat (dashboard.html form)
@app.post("/run-pipeline")
async def run_pipeline_legacy(
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
    directives: str = Form(""),
):
    platform = _get_platform()
    client = platform.get_client(client_id)

    if not client or not client.product_ai_council:
        return RedirectResponse(url="/?error=no_council", status_code=303)

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "client_id": client_id,
        "job_type": "council",
        "status": "queued",
        "progress": 0,
        "message": "En cola...",
        "phases": {},
        "log": [],
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }

    background_tasks.add_task(
        _run_pipeline_task, job_id, client_id, directives,
        reports=["macro", "rv", "rf"],
    )

    return RedirectResponse(url=f"/status/{job_id}", status_code=303)


_COUNCIL_PHASES = [
    ("fase_1", "Recopilacion de datos"),
    ("fase_2", "Preflight check"),
    ("fase_2_5", "Intelligence Briefing"),
    ("fase_3", "AI Council"),
    ("fase_4", "Generacion de reportes"),
    ("fase_5", "Resumen"),
]

_DAILY_PHASES = [
    ("daily_1", "Recopilacion de datos"),
    ("daily_2", "Generacion de reporte"),
    ("daily_3", "Formato HTML"),
    ("daily_4", "Podcast"),
    ("daily_5", "Email"),
]


@app.get("/status/{job_id}", response_class=HTMLResponse)
async def status_page(
    request: Request,
    job_id: str,
    client_id: str = Depends(get_current_client),
):
    job = _jobs.get(job_id)
    if not job or job["client_id"] != client_id:
        return RedirectResponse(url="/", status_code=303)

    job_type = job.get("job_type", "council")
    if job_type == "daily":
        phases_config = _DAILY_PHASES
        back_url = "/daily"
    else:
        phases_config = _COUNCIL_PHASES
        back_url = "/pipeline"

    platform = _get_platform()
    ctx = _client_context(
        request, client_id, platform,
        job=job, phases_config=phases_config, back_url=back_url,
    )
    return templates.TemplateResponse("status.html", ctx)


@app.get("/status/{job_id}/poll")
async def status_poll(
    job_id: str,
    client_id: str = Depends(get_current_client),
):
    job = _jobs.get(job_id)
    if not job or job["client_id"] != client_id:
        return JSONResponse({"error": "not_found"}, status_code=404)

    return JSONResponse({
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "phases": job.get("phases", {}),
        "log": job.get("log", [])[-30:],
    })


# ── Routes: Daily Pipeline ────────────────────────────────

def _run_daily_task(
    job_id: str,
    client_id: str,
    period: str,
    include_podcast: bool = False,
    send_email: bool = False,
    skip_collect: bool = False,
    dry_run: bool = False,
):
    """Background task: run daily report pipeline as subprocess."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["progress"] = 5
    _jobs[job_id]["message"] = "Iniciando pipeline diario..."
    _jobs[job_id]["phases"] = {
        "daily_1": "pending", "daily_2": "pending", "daily_3": "pending",
        "daily_4": "pending", "daily_5": "pending",
    }

    try:
        cmd = [
            sys.executable,
            str(Path(_layout_dir) / "run_daily_single.py"),
            client_id,
            period,
        ]
        if include_podcast:
            cmd.append("--podcast")
        if send_email:
            cmd.append("--send-email")
        if skip_collect:
            cmd.append("--skip-collect")
        if dry_run:
            cmd.append("--dry-run")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(Path(_layout_dir)),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )

        log_lines = []
        phases = _jobs[job_id]["phases"]

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.rstrip()
                log_lines.append(line)
                _jobs[job_id]["log"] = log_lines[-100:]

                if "[DAILY_PHASE_1]" in line:
                    phases["daily_1"] = "running"
                    _jobs[job_id]["progress"] = 10
                    _jobs[job_id]["message"] = "Recopilando datos de mercado..."
                elif "[DAILY_PHASE_2]" in line:
                    phases["daily_1"] = "done"
                    phases["daily_2"] = "running"
                    _jobs[job_id]["progress"] = 30
                    _jobs[job_id]["message"] = "Generando reporte markdown..."
                elif "[DAILY_PHASE_3]" in line:
                    phases["daily_2"] = "done"
                    phases["daily_3"] = "running"
                    _jobs[job_id]["progress"] = 55
                    _jobs[job_id]["message"] = "Formateando HTML..."
                elif "[DAILY_PHASE_4]" in line:
                    phases["daily_3"] = "done"
                    phases["daily_4"] = "running"
                    _jobs[job_id]["progress"] = 70
                    _jobs[job_id]["message"] = "Generando podcast..."
                elif "[DAILY_PHASE_5]" in line:
                    phases["daily_4"] = "done"
                    phases["daily_5"] = "running"
                    _jobs[job_id]["progress"] = 85
                    _jobs[job_id]["message"] = "Enviando email..."
                elif "[DAILY_COMPLETED]" in line:
                    phases["daily_5"] = "done"

        return_code = process.returncode

        if return_code == 0:
            for k in phases:
                if phases[k] == "running":
                    phases[k] = "done"
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = "Reporte diario completado exitosamente."
        else:
            for k in phases:
                if phases[k] == "running":
                    phases[k] = "error"
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["progress"] = 100
            _jobs[job_id]["message"] = f"Pipeline diario termino con errores (codigo {return_code})"

        _jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        logger.exception(f"Daily pipeline failed for {client_id}")
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["message"] = f"Error: {str(e)[:200]}"
        _jobs[job_id]["completed_at"] = datetime.now().isoformat()


@app.get("/daily", response_class=HTMLResponse)
async def daily_page(
    request: Request,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    all_reports = _get_client_reports(client_id, platform)
    daily_reports = [r for r in all_reports if r["type"] == "daily"][:20]
    ctx = _client_context(request, client_id, platform, daily_reports=daily_reports)
    return templates.TemplateResponse("daily.html", ctx)


@app.post("/daily/run")
async def run_daily(
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
    period: str = Form("am"),
    include_podcast: bool = Form(default=False),
    send_email: bool = Form(default=False),
    skip_collect: bool = Form(default=False),
    dry_run: bool = Form(default=False),
):
    platform = _get_platform()
    client = platform.get_client(client_id)

    if not client:
        return RedirectResponse(url="/?error=not_found", status_code=303)

    product_field = f"product_daily_{period}"
    if not getattr(client, product_field, False):
        return RedirectResponse(url="/daily?error=no_product", status_code=303)

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "job_id": job_id,
        "client_id": client_id,
        "job_type": "daily",
        "status": "queued",
        "progress": 0,
        "message": "En cola...",
        "phases": {},
        "log": [],
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "result": None,
    }

    background_tasks.add_task(
        _run_daily_task, job_id, client_id, period,
        include_podcast=include_podcast,
        send_email=send_email,
        skip_collect=skip_collect,
        dry_run=dry_run,
    )

    return RedirectResponse(url=f"/status/{job_id}", status_code=303)


@app.get("/download-podcast/{path:path}")
async def download_podcast(
    path: str,
    client_id: str = Depends(get_current_client),
):
    output_base = os.environ.get("GREYBARK_OUTPUT", str(Path(_layout_dir) / "output"))
    full_path = Path(output_base) / client_id / path

    if not full_path.exists() or not full_path.suffix.lower() == ".mp3":
        return RedirectResponse(url="/reports", status_code=303)

    # Ensure path is within client's output dir
    try:
        full_path.resolve().relative_to(Path(output_base).resolve() / client_id)
    except ValueError:
        return RedirectResponse(url="/reports", status_code=303)

    return FileResponse(
        str(full_path),
        filename=full_path.name,
        media_type="audio/mpeg",
    )


# ── Routes: Settings ─────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    client_id: str = Depends(get_current_client),
    saved: str = "",
):
    platform = _get_platform()
    branding = platform.get_branding(client_id)
    prompts = platform.get_ai_prompts(client_id)
    ctx = _client_context(
        request, client_id, platform,
        current_branding=branding,
        current_prompts=prompts,
        font_options=list(zip(FONT_OPTIONS, FONT_LABELS)),
        saved=saved,
    )
    return templates.TemplateResponse("settings.html", ctx)


@app.post("/settings/branding")
async def save_branding(
    request: Request,
    client_id: str = Depends(get_current_client),
    primary_color: str = Form(...),
    accent_color: str = Form(...),
    font_family: str = Form(...),
    footer_text: str = Form(""),
    email_header_html: str = Form(""),
):
    platform = _get_platform()
    platform.set_branding(
        client_id,
        primary_color=primary_color,
        accent_color=accent_color,
        font_family=font_family,
        footer_text=footer_text,
        email_header_html=email_header_html,
    )
    return RedirectResponse(url="/settings?saved=branding", status_code=303)


@app.post("/settings/logo")
async def upload_logo(
    request: Request,
    logo: UploadFile = File(...),
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()

    ext = Path(logo.filename).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".svg"):
        return RedirectResponse(url="/settings?saved=logo_error_type", status_code=303)

    content = await logo.read()
    if len(content) > 2 * 1024 * 1024:
        return RedirectResponse(url="/settings?saved=logo_error_size", status_code=303)

    output_base = Path(os.environ.get("GREYBARK_OUTPUT", str(Path(_layout_dir) / "output")))
    logo_dir = output_base / client_id
    logo_dir.mkdir(parents=True, exist_ok=True)

    # Remove old logos
    for old in logo_dir.glob("logo.*"):
        old.unlink()

    dest = logo_dir / f"logo{ext}"
    dest.write_bytes(content)

    platform.set_branding(client_id, logo_path=str(dest))
    return RedirectResponse(url="/settings?saved=logo", status_code=303)


@app.post("/settings/logo/delete")
async def delete_logo(
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    branding = platform.get_branding(client_id)
    if branding.logo_path and os.path.exists(branding.logo_path):
        try:
            Path(branding.logo_path).unlink(missing_ok=True)
        except Exception:
            pass
    platform.set_branding(client_id, logo_path="")
    return RedirectResponse(url="/settings?saved=logo_deleted", status_code=303)


@app.post("/settings/prompts")
async def save_prompts(
    client_id: str = Depends(get_current_client),
    tone: str = Form(""),
    audience: str = Form(""),
    focus: str = Form(""),
    custom_instructions: str = Form(""),
    podcast_intro: str = Form(""),
    podcast_outro: str = Form(""),
    report_disclaimer: str = Form(""),
):
    platform = _get_platform()
    platform.set_ai_prompts(
        client_id,
        tone=tone,
        audience=audience,
        focus=focus,
        custom_instructions=custom_instructions,
        podcast_intro=podcast_intro,
        podcast_outro=podcast_outro,
        report_disclaimer=report_disclaimer,
    )
    return RedirectResponse(url="/settings?saved=prompts", status_code=303)


# ── Routes: Reports ───────────────────────────────────────

@app.get("/reports", response_class=HTMLResponse)
async def reports_list(
    request: Request,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)
    ctx = _client_context(request, client_id, platform, reports=reports)
    return templates.TemplateResponse("reports.html", ctx)


@app.get("/reports/raw/{filename:path}", response_class=HTMLResponse)
async def report_raw(
    filename: str,
    client_id: str = Depends(get_current_client),
):
    """Serve raw HTML for iframe embedding."""
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)

    report = None
    for r in reports:
        if r["rel_path"] == filename or r["name"] == filename:
            report = r
            break

    if not report or not os.path.exists(report["path"]):
        return HTMLResponse("<p>Reporte no encontrado</p>", status_code=404)

    with open(report["path"], "r", encoding="utf-8") as f:
        html_content = f.read()

    return HTMLResponse(content=html_content)


@app.get("/reports/{filename:path}", response_class=HTMLResponse)
async def report_view(
    request: Request,
    filename: str,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)

    report = None
    for r in reports:
        if r["rel_path"] == filename or r["name"] == filename:
            report = r
            break

    if not report or not os.path.exists(report["path"]):
        return RedirectResponse(url="/reports", status_code=303)

    ctx = _client_context(
        request, client_id, platform,
        report=report,
        embed_url=f"/reports/raw/{report['rel_path']}",
    )
    return templates.TemplateResponse("report_view.html", ctx)


@app.get("/download/{filename:path}")
async def report_download(
    filename: str,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)

    report = None
    for r in reports:
        if r["rel_path"] == filename or r["name"] == filename:
            report = r
            break

    if not report or not os.path.exists(report["path"]):
        return RedirectResponse(url="/reports", status_code=303)

    return FileResponse(
        report["path"],
        filename=report["name"],
        media_type="text/html",
    )


# ── Routes: Historico ─────────────────────────────────────

@app.get("/historico", response_class=HTMLResponse)
async def historico_page(
    request: Request,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    reports = _get_client_reports(client_id, platform)

    # Group by date folder
    by_date = {}
    for r in reports:
        dk = r["date_folder"]
        if dk not in by_date:
            by_date[dk] = []
        by_date[dk].append(r)

    sorted_dates = sorted(by_date.keys(), reverse=True)

    council_results = _get_recent_council_results(client_id)

    ctx = _client_context(
        request, client_id, platform,
        reports_by_date=by_date,
        sorted_dates=sorted_dates,
        total_reports=len(reports),
        council_results=council_results,
    )
    return templates.TemplateResponse("historico.html", ctx)


# ── Routes: System Status ────────────────────────────────

@app.get("/system-status", response_class=HTMLResponse)
async def system_status_page(
    request: Request,
    client_id: str = Depends(get_current_client),
):
    platform = _get_platform()
    checks = _run_system_checks()
    disk_usage = _get_disk_usage()
    ctx = _client_context(
        request, client_id, platform,
        checks=checks,
        disk_usage=disk_usage,
    )
    return templates.TemplateResponse("system_status.html", ctx)


# ── Routes: Logo ──────────────────────────────────────────

@app.get("/logo/{client_id}")
async def client_logo(client_id: str):
    """Serve client logo — no auth required (public asset)."""
    platform = _get_platform()
    branding = platform.get_branding(client_id)
    if branding.logo_path and os.path.exists(branding.logo_path):
        return FileResponse(branding.logo_path)
    return HTMLResponse("", status_code=404)

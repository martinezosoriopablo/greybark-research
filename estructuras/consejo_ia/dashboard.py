# -*- coding: utf-8 -*-
"""
Greybark Research - Pipeline Dashboard (Multi-tenant)
=====================================================

Dashboard Streamlit con autenticacion por cliente.
Carga branding, prompts y config desde Platform.

Uso:
    streamlit run dashboard.py
    streamlit run dashboard.py -- --token=greybark
    Abrir en browser: http://localhost:8501/?token=greybark
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Fix Windows encoding before anything else
if sys.platform == 'win32':
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8:replace')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

import streamlit as st

# Paths
BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input"
RESEARCH_DIR = INPUT_DIR / "research"
DIRECTIVES_FILE = INPUT_DIR / "user_directives.txt"
OUTPUT_DIR = BASE_DIR / "output"
COUNCIL_DIR = OUTPUT_DIR / "council"
REPORTS_DIR = OUTPUT_DIR / "reports"
EQUITY_DIR = OUTPUT_DIR / "equity_data"
RF_DATA_DIR = OUTPUT_DIR / "rf_data"

# Add paths for imports
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR.parent / "02_greybark_library"))

# Platform path (layout/)
LAYOUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "layout"
sys.path.insert(0, str(LAYOUT_DIR))

# Ensure dirs exist
for d in [RESEARCH_DIR, COUNCIL_DIR, REPORTS_DIR, EQUITY_DIR, RF_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# =========================================================================
# GREYBARK DEFAULTS (fallback when no client authenticated)
# =========================================================================

GREYBARK_DEFAULTS = {
    'primary_color': '#1a1a1a',
    'accent_color': '#dd6b20',
    'green_color': '#276749',
    'red_color': '#c53030',
    'font_family': "'Segoe UI', sans-serif",
    'company_name': 'GREYBARK RESEARCH',
    'sidebar_bg': '#1a1a1a',
}


# =========================================================================
# PLATFORM INTEGRATION
# =========================================================================

@st.cache_resource
def get_platform():
    """Singleton Platform instance."""
    try:
        from greybark_platform import Platform
        return Platform()
    except Exception as e:
        st.error(f"Error cargando Platform: {e}")
        return None


def _get_platform_dataclasses():
    """Import Branding/AIPrompts from platform, with fallback stubs."""
    try:
        from greybark_platform import Branding, AIPrompts
        return Branding, AIPrompts
    except ImportError:
        from dataclasses import dataclass as _dc

        @_dc
        class _Branding:
            logo_path: str = ""
            primary_color: str = "#1a1a1a"
            accent_color: str = "#dd6b20"
            font_family: str = "'Segoe UI', sans-serif"
            footer_text: str = ""
            email_header_html: str = ""

        @_dc
        class _AIPrompts:
            tone: str = ""
            audience: str = ""
            focus: str = ""
            podcast_intro: str = ""
            podcast_outro: str = ""
            report_disclaimer: str = ""
            custom_instructions: str = ""

        return _Branding, _AIPrompts


Branding, AIPrompts = _get_platform_dataclasses()


def authenticate(token: str) -> Optional[str]:
    """Validate token and return client_id or None."""
    p = get_platform()
    if not p:
        return None
    return p.authenticate_token(token)


def load_client_config(client_id: str) -> Optional[dict]:
    """Load full client config for dashboard rendering."""
    p = get_platform()
    if not p:
        return None
    return p.get_client_for_dashboard(client_id)


def get_theme(config: Optional[dict] = None) -> dict:
    """Extract theme colors from client config or use defaults."""
    if config and config.get('branding'):
        b = config['branding']
        return {
            'primary_color': b.primary_color or GREYBARK_DEFAULTS['primary_color'],
            'accent_color': b.accent_color or GREYBARK_DEFAULTS['accent_color'],
            'font_family': b.font_family or GREYBARK_DEFAULTS['font_family'],
            'company_name': config['client'].company_name if config.get('client') else 'GREYBARK RESEARCH',
            'logo_path': b.logo_path or '',
            'sidebar_bg': b.primary_color or GREYBARK_DEFAULTS['sidebar_bg'],
        }
    return dict(GREYBARK_DEFAULTS)


# =========================================================================
# PAGE CONFIG
# =========================================================================

st.set_page_config(
    page_title="Research Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================================
# AUTH GATE
# =========================================================================

def show_login_page():
    """Show login form when no token is provided."""
    st.markdown(f"""
    <style>
        .login-box {{
            max-width: 400px;
            margin: 100px auto;
            padding: 40px;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            text-align: center;
        }}
        .login-title {{
            font-size: 24px;
            font-weight: 900;
            color: {GREYBARK_DEFAULTS['primary_color']};
            letter-spacing: 2px;
            margin-bottom: 5px;
        }}
        .login-subtitle {{
            color: {GREYBARK_DEFAULTS['accent_color']};
            font-size: 13px;
            margin-bottom: 30px;
        }}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-title">RESEARCH DASHBOARD</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">Pipeline AI Council</div>', unsafe_allow_html=True)
    st.markdown("---")

    token = st.text_input("Token de acceso", type="password", key="login_token")
    if st.button("Ingresar", type="primary", use_container_width=True):
        client_id = authenticate(token)
        if client_id:
            st.session_state.client_id = client_id
            st.rerun()
        else:
            st.error("Token invalido")


# Check auth: query param > session state > login form
if 'client_id' not in st.session_state:
    token = st.query_params.get("token", "")
    if token:
        client_id = authenticate(token)
        if client_id:
            st.session_state.client_id = client_id
        else:
            show_login_page()
            st.stop()
    else:
        show_login_page()
        st.stop()

# Authenticated — load client config
CLIENT_ID = st.session_state.client_id
CLIENT_CONFIG = load_client_config(CLIENT_ID)
THEME = get_theme(CLIENT_CONFIG)


# =========================================================================
# DYNAMIC CSS (uses client branding)
# =========================================================================

_primary = THEME['primary_color']
_accent = THEME['accent_color']
_font = THEME['font_family']
_sidebar_bg = THEME.get('sidebar_bg', _primary)

st.markdown(f"""
<style>
    /* Header */
    .main-header {{
        font-family: {_font};
        font-size: 28px;
        font-weight: 900;
        letter-spacing: 2px;
        color: {_primary};
        border-bottom: 3px solid {_accent};
        padding-bottom: 8px;
        margin-bottom: 5px;
    }}
    .main-subtitle {{
        color: {_accent};
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 25px;
    }}
    .client-logo {{
        max-height: 50px;
        margin-bottom: 10px;
    }}

    /* Cards */
    .status-card {{
        background: #f7f7f7;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 4px solid {_accent};
    }}
    .status-ok {{ border-left-color: #276749; }}
    .status-warn {{ border-left-color: #d69e2e; }}
    .status-err {{ border-left-color: #c53030; }}

    /* File list */
    .file-item {{
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
    }}
    .file-item .name {{ font-weight: 600; }}
    .file-item .size {{ color: #718096; font-size: 11px; }}

    /* Phase progress */
    .phase-box {{
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
    }}
    .phase-done {{ background: #f0fff4; border-color: #276749; }}
    .phase-running {{ background: #fffff0; border-color: #d69e2e; }}
    .phase-error {{ background: #fff5f5; border-color: #c53030; }}

    /* Section headers */
    .section-header {{
        font-size: 16px;
        font-weight: 700;
        color: {_primary};
        border-bottom: 2px solid {_accent};
        padding-bottom: 6px;
        margin: 20px 0 12px 0;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {_sidebar_bg};
    }}
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown li,
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {{
        color: #e2e8f0;
    }}
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p,
    [data-testid="stSidebar"] span {{
        color: #ffffff !important;
    }}

    /* Buttons */
    .stButton > button[kind="primary"] {{
        background-color: {_accent} !important;
        color: white !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        opacity: 0.85;
    }}

    /* Hide streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

# Inject Platform CSS vars if available
if CLIENT_CONFIG and CLIENT_CONFIG.get('css_vars'):
    st.markdown(CLIENT_CONFIG['css_vars'], unsafe_allow_html=True)


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def get_research_files() -> List[Dict]:
    """Lista archivos de research actuales."""
    files = []
    for ext in ('*.txt', '*.md', '*.pdf'):
        for f in sorted(RESEARCH_DIR.glob(ext)):
            if f.name.upper().startswith('README'):
                continue
            files.append({
                'name': f.name,
                'size': f.stat().st_size,
                'modified': datetime.fromtimestamp(f.stat().st_mtime),
                'path': f,
            })
    return files


def get_directives() -> str:
    """Lee las directivas actuales."""
    if DIRECTIVES_FILE.exists():
        text = DIRECTIVES_FILE.read_text(encoding='utf-8')
        lines = [l.rstrip() for l in text.split('\n')
                 if l.strip() and not l.strip().startswith('#')]
        return '\n'.join(lines)
    return ''


def get_directives_full() -> str:
    """Lee el archivo completo de directivas (con comentarios)."""
    if DIRECTIVES_FILE.exists():
        return DIRECTIVES_FILE.read_text(encoding='utf-8')
    return ''


def save_directives(content: str):
    """Guarda directivas preservando el header de comentarios."""
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
    DIRECTIVES_FILE.write_text(header + content, encoding='utf-8')


def get_recent_council_results() -> List[Dict]:
    """Lista resultados de council recientes."""
    results = []
    for f in sorted(COUNCIL_DIR.glob("council_result_*.json"), reverse=True)[:5]:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            meta = data.get('metadata', {})
            results.append({
                'file': f.name,
                'path': f,
                'timestamp': meta.get('timestamp', ''),
                'duration': meta.get('duration_seconds', 0),
                'report_type': meta.get('report_type', ''),
                'aborted': data.get('aborted', False),
            })
        except Exception:
            continue
    return results


def get_recent_reports() -> List[Dict]:
    """Lista reportes HTML recientes."""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.html"), reverse=True)[:10]:
        report_type = 'otro'
        if 'intelligence_briefing' in f.name:
            report_type = 'briefing'
        elif 'macro' in f.name:
            report_type = 'macro'
        elif 'rv_' in f.name:
            report_type = 'rv'
        elif 'rf_' in f.name:
            report_type = 'rf'
        elif 'asset_allocation' in f.name:
            report_type = 'aa'
        reports.append({
            'name': f.name,
            'path': f,
            'type': report_type,
            'size': f.stat().st_size,
            'modified': datetime.fromtimestamp(f.stat().st_mtime),
        })
    return reports


def get_client_reports(client_id: str) -> List[Dict]:
    """Lista reportes del directorio output/ del cliente en Platform."""
    p = get_platform()
    if not p:
        return []
    client_output = p.output_base / client_id
    if not client_output.exists():
        return []

    reports = []
    for html_file in sorted(client_output.rglob("*.html"), reverse=True):
        report_type = 'otro'
        name_lower = html_file.name.lower()
        if 'intelligence_briefing' in name_lower:
            report_type = 'briefing'
        elif 'macro' in name_lower:
            report_type = 'macro'
        elif 'rv_' in name_lower:
            report_type = 'rv'
        elif 'rf_' in name_lower:
            report_type = 'rf'
        elif 'asset_allocation' in name_lower:
            report_type = 'aa'
        elif 'daily_report' in name_lower:
            report_type = 'daily'

        # Extract date from parent folder name (YYYY-MM-DD)
        date_folder = html_file.parent.name
        reports.append({
            'name': html_file.name,
            'path': html_file,
            'type': report_type,
            'size': html_file.stat().st_size,
            'modified': datetime.fromtimestamp(html_file.stat().st_mtime),
            'date_folder': date_folder,
        })
    return reports


def format_size(size_bytes: int) -> str:
    """Formatea bytes a human-readable."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_elapsed(seconds: float) -> str:
    """Formatea segundos a mm:ss."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def render_header():
    """Render header with logo and company name."""
    logo_path = THEME.get('logo_path', '')
    company = THEME['company_name']

    if logo_path and os.path.exists(logo_path):
        col_logo, col_title = st.columns([1, 5])
        with col_logo:
            st.image(logo_path, width=80)
        with col_title:
            st.markdown(f'<div class="main-header">{company}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="main-header">{company}</div>', unsafe_allow_html=True)


# =========================================================================
# SIDEBAR
# =========================================================================

with st.sidebar:
    company_name = THEME['company_name']
    st.markdown(f"### {company_name}")
    st.markdown("*Pipeline Dashboard*")
    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navegacion",
        ["Pipeline", "Reportes", "Historico", "Configuracion", "Estado"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Quick status
    research_files = get_research_files()
    directives = get_directives()
    recent_results = get_recent_council_results()

    st.markdown("**Estado Actual**")
    st.markdown(f"- Research: **{len(research_files)}** archivos")
    st.markdown(f"- Directivas: **{'si' if directives else 'no'}**")
    st.markdown(f"- Council runs: **{len(recent_results)}**")

    if CLIENT_CONFIG and CLIENT_CONFIG.get('usage'):
        usage = CLIENT_CONFIG['usage']
        st.markdown(f"- AI Council: **{usage.get('ai_council_count', 0)}** este mes")

    st.markdown("---")

    # Logout
    if st.button("Cerrar sesion"):
        del st.session_state.client_id
        st.rerun()

    st.markdown(f"*{datetime.now().strftime('%d %b %Y %H:%M')}*")


# =========================================================================
# PAGE: PIPELINE
# =========================================================================

if page == "Pipeline":

    render_header()
    st.markdown('<div class="main-subtitle">Pipeline Mensual Unificado</div>', unsafe_allow_html=True)

    # Two columns layout
    col_research, col_directives = st.columns([1, 1])

    # ---- RESEARCH FILES ----
    with col_research:
        st.markdown('<div class="section-header">Research Files</div>', unsafe_allow_html=True)

        uploaded_files = st.file_uploader(
            "Subir research (PDF o TXT)",
            type=['pdf', 'txt', 'md'],
            accept_multiple_files=True,
            key="research_upload",
            label_visibility="collapsed",
        )

        if uploaded_files:
            for uf in uploaded_files:
                dest = RESEARCH_DIR / uf.name
                dest.write_bytes(uf.getbuffer())
            st.success(f"{len(uploaded_files)} archivo(s) subido(s)")
            st.rerun()

        research_files = get_research_files()
        if research_files:
            for rf in research_files:
                c1, c2, c3 = st.columns([6, 2, 1])
                with c1:
                    icon = "📄" if rf['name'].endswith('.pdf') else "📝"
                    st.markdown(f"{icon} **{rf['name']}**")
                with c2:
                    st.caption(format_size(rf['size']))
                with c3:
                    if st.button("✕", key=f"del_{rf['name']}", help="Eliminar"):
                        rf['path'].unlink()
                        st.rerun()
        else:
            st.info("Sin archivos de research. Sube PDFs o TXT arriba.")

    # ---- DIRECTIVES ----
    with col_directives:
        st.markdown('<div class="section-header">Directivas del Comite</div>', unsafe_allow_html=True)

        current_directives = get_directives()
        new_directives = st.text_area(
            "Tus opiniones, foco, preguntas para el council",
            value=current_directives,
            height=200,
            key="directives_input",
            label_visibility="collapsed",
            placeholder="Ej: Foco en impacto aranceles en Chile\nCreo que BCCh mantiene TPM\nHay valor en Europa?",
        )

        if new_directives != current_directives:
            save_directives(new_directives)
            st.success("Directivas guardadas")

    st.markdown("---")

    # ---- PIPELINE CONFIG ----
    st.markdown('<div class="section-header">Configuracion del Pipeline</div>', unsafe_allow_html=True)

    col_reports, col_options, col_run = st.columns([2, 2, 1])

    with col_reports:
        st.markdown("**Reportes a generar**")
        rep_macro = st.checkbox("Macro Report", value=True, key="rep_macro")
        rep_rv = st.checkbox("RV Report (Renta Variable)", value=True, key="rep_rv")
        rep_rf = st.checkbox("RF Report (Renta Fija)", value=True, key="rep_rf")
        rep_aa = st.checkbox("AA Report (Asset Allocation)", value=False, key="rep_aa")

    with col_options:
        st.markdown("**Opciones**")
        opt_dry_run = st.checkbox("Dry Run (solo recopilar, sin council)", key="opt_dry")
        opt_skip_collect = st.checkbox("Saltar recopilacion (usar datos existentes)", key="opt_skip")
        opt_open = st.checkbox("Abrir reportes al finalizar", value=True, key="opt_open")

    with col_run:
        st.markdown("&nbsp;")
        st.markdown("&nbsp;")

        reports = []
        if rep_macro:
            reports.append('macro')
        if rep_rv:
            reports.append('rv')
        if rep_rf:
            reports.append('rf')
        if rep_aa:
            reports.append('aa')

        can_run = len(reports) > 0 or opt_dry_run
        run_clicked = st.button(
            "Ejecutar Pipeline",
            type="primary",
            disabled=not can_run,
            use_container_width=True,
        )

    # ---- PIPELINE EXECUTION ----
    if run_clicked:
        st.markdown("---")
        st.markdown('<div class="section-header">Ejecucion del Pipeline</div>', unsafe_allow_html=True)

        # Build command — run_monthly.py as subprocess for streaming output
        cmd = [sys.executable, str(BASE_DIR / "run_monthly.py"), "--no-confirm"]

        if opt_dry_run:
            cmd.append("--dry-run")
        if opt_skip_collect:
            cmd.append("--skip-collect")
        if opt_open:
            cmd.append("--open")
        if reports:
            cmd.extend(["--reports"] + reports)

        # Progress area
        progress_area = st.empty()
        log_expander = st.expander("Log completo", expanded=True)
        log_area = log_expander.empty()

        full_log = []
        phase_status = {
            'fase_1': 'pending',
            'fase_2': 'pending',
            'fase_2_5': 'pending',
            'fase_3': 'pending',
            'fase_4': 'pending',
            'fase_5': 'pending',
        }

        def update_progress():
            phases_display = ""
            icons = {'pending': '⬜', 'running': '🔄', 'done': '✅', 'error': '❌'}
            names = {
                'fase_1': 'Recopilacion de datos',
                'fase_2': 'Preflight check',
                'fase_2_5': 'Intelligence Briefing',
                'fase_3': 'AI Council',
                'fase_4': 'Generacion de reportes',
                'fase_5': 'Resumen',
            }
            for key, name in names.items():
                icon = icons.get(phase_status[key], '⬜')
                phases_display += f"{icon} **{name}**  \n"
            progress_area.markdown(phases_display)

        update_progress()

        # Run the pipeline as subprocess
        start_time = time.time()

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=str(BASE_DIR),
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
            )

            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    line = line.rstrip()
                    full_log.append(line)

                    # Detect phase changes
                    if '[FASE 1]' in line or 'RECOPILACIÓN' in line.upper() or 'CARGANDO DATOS' in line.upper():
                        phase_status['fase_1'] = 'running'
                    elif '[FASE 2]' in line or 'PREFLIGHT' in line.upper():
                        phase_status['fase_1'] = 'done'
                        phase_status['fase_2'] = 'running'
                    elif 'INTELLIGENCE BRIEFING' in line.upper():
                        phase_status['fase_2'] = 'done'
                        phase_status['fase_2_5'] = 'running'
                    elif '[FASE 3]' in line or 'AI COUNCIL SESSION' in line:
                        phase_status['fase_2'] = 'done'
                        phase_status['fase_2_5'] = 'done'
                        phase_status['fase_3'] = 'running'
                    elif '[FASE 4]' in line or 'GENERACIÓN DE REPORTES' in line.upper():
                        phase_status['fase_3'] = 'done'
                        phase_status['fase_4'] = 'running'
                    elif '[FASE 5]' in line or 'RESUMEN DEL PIPELINE' in line.upper():
                        phase_status['fase_4'] = 'done'
                        phase_status['fase_5'] = 'running'
                    elif 'PIPELINE COMPLETADO' in line.upper():
                        phase_status['fase_5'] = 'done'

                    update_progress()
                    log_area.code('\n'.join(full_log[-50:]), language=None)

            elapsed = time.time() - start_time
            return_code = process.returncode

            if return_code == 0:
                for k in phase_status:
                    if phase_status[k] == 'running':
                        phase_status[k] = 'done'
                update_progress()
                st.success(f"Pipeline completado en {format_elapsed(elapsed)}")
            else:
                for k in phase_status:
                    if phase_status[k] == 'running':
                        phase_status[k] = 'error'
                update_progress()
                st.error(f"Pipeline termino con errores (codigo {return_code})")

        except Exception as e:
            st.error(f"Error ejecutando pipeline: {e}")

        # Show generated reports
        st.markdown("---")
        st.markdown('<div class="section-header">Reportes Generados</div>', unsafe_allow_html=True)

        recent = get_recent_reports()
        today = datetime.now().strftime('%Y-%m-%d')
        today_reports = [r for r in recent if today in r['name']]

        if today_reports:
            for r in today_reports:
                c1, c2, c3 = st.columns([5, 2, 2])
                with c1:
                    type_icons = {'macro': '🌍', 'rv': '📈', 'rf': '📉', 'aa': '💼', 'briefing': '🔍'}
                    icon = type_icons.get(r['type'], '📄')
                    st.markdown(f"{icon} **{r['name']}**")
                with c2:
                    st.caption(format_size(r['size']))
                with c3:
                    if st.button("Abrir", key=f"open_{r['name']}"):
                        os.startfile(str(r['path']))
        else:
            st.info("No hay reportes generados hoy.")


# =========================================================================
# PAGE: REPORTES
# =========================================================================

elif page == "Reportes":

    render_header()
    st.markdown('<div class="main-subtitle">Reportes Generados</div>', unsafe_allow_html=True)

    recent = get_recent_reports()

    if not recent:
        st.info("No hay reportes generados todavia.")
    else:
        by_date = {}
        for r in recent:
            date_key = r['modified'].strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(r)

        for date_key, date_reports in by_date.items():
            st.markdown(f"### {date_key}")

            for r in date_reports:
                c1, c2, c3, c4 = st.columns([5, 2, 2, 2])
                type_labels = {'macro': 'Macro', 'rv': 'Renta Variable', 'rf': 'Renta Fija', 'aa': 'Asset Allocation', 'briefing': 'Intelligence Briefing'}
                type_icons = {'macro': '🌍', 'rv': '📈', 'rf': '📉', 'aa': '💼', 'briefing': '🔍'}

                with c1:
                    icon = type_icons.get(r['type'], '📄')
                    label = type_labels.get(r['type'], r['type'])
                    st.markdown(f"{icon} **{label}** — `{r['name']}`")
                with c2:
                    st.caption(format_size(r['size']))
                with c3:
                    st.caption(r['modified'].strftime('%H:%M'))
                with c4:
                    if st.button("Abrir", key=f"view_{r['name']}"):
                        os.startfile(str(r['path']))

    # Council results
    st.markdown("---")
    st.markdown('<div class="section-header">Council Results</div>', unsafe_allow_html=True)

    council_results = get_recent_council_results()
    if council_results:
        for cr in council_results:
            c1, c2, c3 = st.columns([5, 2, 2])
            with c1:
                status = "❌ Abortado" if cr['aborted'] else "✅ Completado"
                st.markdown(f"{status} — `{cr['file']}`")
            with c2:
                if cr['duration']:
                    st.caption(f"{cr['duration']:.0f}s")
            with c3:
                st.caption(cr['report_type'])
    else:
        st.info("No hay resultados de council.")


# =========================================================================
# PAGE: HISTORICO (NEW — client-specific report archive)
# =========================================================================

elif page == "Historico":

    render_header()
    st.markdown('<div class="main-subtitle">Historico de Reportes</div>', unsafe_allow_html=True)

    client_reports = get_client_reports(CLIENT_ID)

    if not client_reports:
        st.info("No hay reportes en el historico de este cliente.")
        st.caption(f"Los reportes generados via Platform se guardan en output/{CLIENT_ID}/")
    else:
        # Group by date folder
        by_date = {}
        for r in client_reports:
            dk = r['date_folder']
            if dk not in by_date:
                by_date[dk] = []
            by_date[dk].append(r)

        type_labels = {
            'macro': 'Macro', 'rv': 'Renta Variable', 'rf': 'Renta Fija',
            'aa': 'Asset Allocation', 'briefing': 'Intelligence Briefing',
            'daily': 'Reporte Diario', 'otro': 'Otro',
        }
        type_icons = {
            'macro': '🌍', 'rv': '📈', 'rf': '📉', 'aa': '💼',
            'briefing': '🔍', 'daily': '📊', 'otro': '📄',
        }

        for date_key in sorted(by_date.keys(), reverse=True):
            date_reports = by_date[date_key]
            st.markdown(f"### {date_key}")

            for r in date_reports:
                c1, c2, c3, c4 = st.columns([5, 2, 2, 2])
                with c1:
                    icon = type_icons.get(r['type'], '📄')
                    label = type_labels.get(r['type'], r['type'])
                    st.markdown(f"{icon} **{label}** — `{r['name']}`")
                with c2:
                    st.caption(format_size(r['size']))
                with c3:
                    st.caption(r['modified'].strftime('%H:%M'))
                with c4:
                    if st.button("Abrir", key=f"hist_{r['date_folder']}_{r['name']}"):
                        os.startfile(str(r['path']))

        st.markdown("---")
        st.caption(f"Total: {len(client_reports)} reportes")

    # Usage stats
    if CLIENT_CONFIG and CLIENT_CONFIG.get('usage'):
        st.markdown("---")
        st.markdown('<div class="section-header">Uso del Mes</div>', unsafe_allow_html=True)
        usage = CLIENT_CONFIG['usage']
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Daily AM", usage.get('daily_am_count', 0))
        with c2:
            st.metric("Daily PM", usage.get('daily_pm_count', 0))
        with c3:
            st.metric("AI Council", usage.get('ai_council_count', 0))
        with c4:
            st.metric("Podcasts", usage.get('podcast_count', 0))

    # Recent jobs
    if CLIENT_CONFIG and CLIENT_CONFIG.get('recent_jobs'):
        st.markdown("---")
        st.markdown('<div class="section-header">Jobs Recientes</div>', unsafe_allow_html=True)
        for job in CLIENT_CONFIG['recent_jobs'][:5]:
            status_icon = "✅" if job['status'] == 'completed' else "❌" if job['status'] == 'failed' else "🔄"
            st.markdown(
                f"{status_icon} **{job['product']}** — {job.get('completed_at', 'en progreso')}"
            )


# =========================================================================
# PAGE: CONFIGURACION (self-service branding + AI prompts)
# =========================================================================

elif page == "Configuracion":

    render_header()
    st.markdown('<div class="main-subtitle">Configuracion de Marca</div>', unsafe_allow_html=True)

    p = get_platform()

    # Load current values
    current_branding = p.get_branding(CLIENT_ID) if p else Branding()
    current_prompts = p.get_ai_prompts(CLIENT_ID) if p else AIPrompts()

    col_form, col_preview = st.columns([1, 1])

    # ---- LEFT COLUMN: Form ----
    with col_form:
        st.markdown('<div class="section-header">Branding</div>', unsafe_allow_html=True)

        # Logo upload
        logo_path = current_branding.logo_path or ''
        if logo_path and os.path.exists(logo_path):
            st.image(logo_path, width=120, caption="Logo actual")
            if st.button("Eliminar logo", key="cfg_del_logo"):
                try:
                    Path(logo_path).unlink(missing_ok=True)
                except Exception:
                    pass
                p.set_branding(CLIENT_ID, logo_path="")
                st.cache_resource.clear()
                st.rerun()

        uploaded_logo = st.file_uploader(
            "Subir logo (PNG, JPG o SVG, max 2 MB)",
            type=['png', 'jpg', 'jpeg', 'svg'],
            key="cfg_logo_upload",
        )

        # Colors
        cfg_primary = st.color_picker(
            "Color primario (sidebar, headers)",
            value=current_branding.primary_color or '#1a1a1a',
            key="cfg_primary",
        )
        cfg_accent = st.color_picker(
            "Color accent (bordes, botones, highlights)",
            value=current_branding.accent_color or '#dd6b20',
            key="cfg_accent",
        )

        # Font
        FONT_OPTIONS = [
            "Georgia", "'Segoe UI', sans-serif", "Arial, sans-serif",
            "'Times New Roman', serif", "Helvetica, sans-serif",
            "Verdana, sans-serif", "'Roboto', sans-serif", "'Open Sans', sans-serif",
        ]
        FONT_LABELS = [
            "Georgia", "Segoe UI", "Arial", "Times New Roman",
            "Helvetica", "Verdana", "Roboto", "Open Sans",
        ]
        current_font = current_branding.font_family or "'Segoe UI', sans-serif"
        font_idx = 0
        for i, f in enumerate(FONT_OPTIONS):
            if f == current_font:
                font_idx = i
                break
        cfg_font_label = st.selectbox(
            "Tipografia",
            FONT_LABELS,
            index=font_idx,
            key="cfg_font",
        )
        cfg_font = FONT_OPTIONS[FONT_LABELS.index(cfg_font_label)]

        # Footer
        cfg_footer = st.text_input(
            "Texto de footer (pie de reportes)",
            value=current_branding.footer_text or '',
            key="cfg_footer",
        )

        # Email header (advanced)
        with st.expander("Avanzado: HTML header de emails"):
            cfg_email_header = st.text_area(
                "HTML custom para header de emails",
                value=current_branding.email_header_html or '',
                height=100,
                key="cfg_email_header",
            )

        # ---- SAVE BRANDING ----
        if st.button("Guardar cambios de marca", type="primary", use_container_width=True, key="cfg_save_branding"):
            if p:
                # Save logo if uploaded
                saved_logo = logo_path
                if uploaded_logo:
                    ext = Path(uploaded_logo.name).suffix.lower()
                    if uploaded_logo.size > 2 * 1024 * 1024:
                        st.error("El logo no puede superar 2 MB")
                        st.stop()
                    logo_dir = p.output_base / CLIENT_ID
                    logo_dir.mkdir(parents=True, exist_ok=True)
                    for old in logo_dir.glob("logo.*"):
                        old.unlink()
                    dest = logo_dir / f"logo{ext}"
                    dest.write_bytes(uploaded_logo.getbuffer())
                    saved_logo = str(dest)

                p.set_branding(
                    CLIENT_ID,
                    logo_path=saved_logo,
                    primary_color=cfg_primary,
                    accent_color=cfg_accent,
                    font_family=cfg_font,
                    footer_text=cfg_footer,
                    email_header_html=cfg_email_header,
                )
                st.cache_resource.clear()
                st.success("Branding guardado")
                st.rerun()

        # ---- AI PROMPTS SECTION ----
        st.markdown("---")
        st.markdown('<div class="section-header">AI Prompts</div>', unsafe_allow_html=True)

        cfg_tone = st.text_input(
            "Tono",
            value=current_prompts.tone or '',
            placeholder="Ej: Formal y conservador",
            key="cfg_tone",
        )
        cfg_audience = st.text_input(
            "Audiencia",
            value=current_prompts.audience or '',
            placeholder="Ej: Directorio y gerencia",
            key="cfg_audience",
        )
        cfg_focus = st.text_input(
            "Foco tematico",
            value=current_prompts.focus or '',
            placeholder="Ej: Renta fija Chile",
            key="cfg_focus",
        )
        cfg_custom_instructions = st.text_area(
            "Instrucciones custom",
            value=current_prompts.custom_instructions or '',
            height=80,
            placeholder="Instrucciones adicionales para los agentes IA",
            key="cfg_custom_inst",
        )
        cfg_podcast_intro = st.text_input(
            "Podcast intro",
            value=current_prompts.podcast_intro or '',
            placeholder="Buenos dias, bienvenidos al reporte de {fecha}...",
            key="cfg_podcast_intro",
        )
        cfg_podcast_outro = st.text_input(
            "Podcast outro",
            value=current_prompts.podcast_outro or '',
            placeholder="Esto fue el reporte de {fecha}. Hasta manana.",
            key="cfg_podcast_outro",
        )
        cfg_disclaimer = st.text_area(
            "Disclaimer de reportes",
            value=current_prompts.report_disclaimer or '',
            height=60,
            key="cfg_disclaimer",
        )

        if st.button("Guardar prompts", type="primary", use_container_width=True, key="cfg_save_prompts"):
            if p:
                p.set_ai_prompts(
                    CLIENT_ID,
                    tone=cfg_tone,
                    audience=cfg_audience,
                    focus=cfg_focus,
                    custom_instructions=cfg_custom_instructions,
                    podcast_intro=cfg_podcast_intro,
                    podcast_outro=cfg_podcast_outro,
                    report_disclaimer=cfg_disclaimer,
                )
                st.success("Prompts guardados")
                st.rerun()

    # ---- RIGHT COLUMN: Live Preview ----
    with col_preview:
        st.markdown('<div class="section-header">Vista previa</div>', unsafe_allow_html=True)

        # Use form values (reactive) for preview
        _pv_primary = cfg_primary
        _pv_accent = cfg_accent
        _pv_font = cfg_font
        _pv_footer = cfg_footer
        _pv_company = THEME['company_name']
        _pv_logo = ''

        # Show uploaded logo in preview if available, else current
        if uploaded_logo:
            import base64 as _b64
            _logo_bytes = uploaded_logo.getvalue()
            _logo_ext = Path(uploaded_logo.name).suffix.lower().lstrip('.')
            if _logo_ext == 'svg':
                _logo_mime = 'image/svg+xml'
            elif _logo_ext in ('jpg', 'jpeg'):
                _logo_mime = 'image/jpeg'
            else:
                _logo_mime = 'image/png'
            _pv_logo = f'<img src="data:{_logo_mime};base64,{_b64.b64encode(_logo_bytes).decode()}" style="max-height:50px;margin-bottom:8px;" /><br/>'
        elif logo_path and os.path.exists(logo_path):
            import base64 as _b64
            _ext = Path(logo_path).suffix.lower().lstrip('.')
            if _ext == 'svg':
                _logo_mime = 'image/svg+xml'
            elif _ext in ('jpg', 'jpeg'):
                _logo_mime = 'image/jpeg'
            else:
                _logo_mime = 'image/png'
            _pv_logo = f'<img src="data:{_logo_mime};base64,{_b64.b64encode(Path(logo_path).read_bytes()).decode()}" style="max-height:50px;margin-bottom:8px;" /><br/>'

        _preview_date = datetime.now().strftime('%d %b %Y')

        _footer_html = f'<div style="margin-top:16px;padding-top:10px;border-top:1px solid #e2e8f0;font-size:11px;color:#a0aec0;">{_pv_footer}</div>' if _pv_footer else ''
        _preview_html = (
            f'<div style="border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;font-family:{_pv_font};">'
            f'<div style="background:{_pv_primary};color:#fff;padding:14px 18px;font-size:13px;letter-spacing:1px;font-weight:700;">{_pv_company}</div>'
            f'<div style="padding:20px;">'
            f'{_pv_logo}'
            f'<div style="font-size:22px;font-weight:900;color:{_pv_primary};letter-spacing:1px;font-family:{_pv_font};">{_pv_company}</div>'
            f'<div style="height:3px;background:{_pv_accent};margin:8px 0 16px 0;width:60%;"></div>'
            f'<div style="font-size:14px;color:{_pv_accent};font-weight:600;margin-bottom:12px;">Reporte Diario &mdash; {_preview_date}</div>'
            f'<div style="font-size:12px;color:#718096;line-height:1.6;">Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</div>'
            f'{_footer_html}'
            f'</div></div>'
        )
        st.markdown(_preview_html, unsafe_allow_html=True)

        # Prompt preview summary
        st.markdown("---")
        st.markdown('<div class="section-header">Resumen AI Prompts</div>', unsafe_allow_html=True)

        _prompt_items = [
            ("Tono", cfg_tone),
            ("Audiencia", cfg_audience),
            ("Foco", cfg_focus),
            ("Instrucciones", cfg_custom_instructions),
            ("Podcast intro", cfg_podcast_intro),
            ("Podcast outro", cfg_podcast_outro),
            ("Disclaimer", cfg_disclaimer),
        ]
        for _label, _val in _prompt_items:
            if _val:
                st.markdown(f"**{_label}:** {_val[:80]}{'...' if len(_val) > 80 else ''}")
        if not any(v for _, v in _prompt_items):
            st.caption("Sin prompts configurados")


# =========================================================================
# PAGE: ESTADO
# =========================================================================

elif page == "Estado":

    render_header()
    st.markdown('<div class="main-subtitle">Estado del Sistema</div>', unsafe_allow_html=True)

    # Data sources check
    st.markdown('<div class="section-header">Fuentes de Datos</div>', unsafe_allow_html=True)

    checks = []

    # Load config from greybark
    try:
        from greybark.config import config as gbk_config, CLAUDE_API_KEY
        has_config = True
    except Exception:
        gbk_config = None
        CLAUDE_API_KEY = None
        has_config = False

    # Check ANTHROPIC_API_KEY
    has_api_key = bool(os.environ.get('ANTHROPIC_API_KEY') or CLAUDE_API_KEY)
    checks.append(('Anthropic API Key', has_api_key, 'Council + Research Analyzer'))

    # Check FRED API
    has_fred = False
    if gbk_config:
        has_fred = bool(getattr(gbk_config.fred, 'api_key', ''))
    has_fred = has_fred or bool(os.environ.get('FRED_API_KEY'))
    checks.append(('FRED API Key', has_fred, 'Datos macro USA, tasas, credit spreads'))

    # Check BCCh API
    has_bcch = False
    if gbk_config:
        has_bcch = bool(getattr(gbk_config.bcch, 'user', '')) and bool(getattr(gbk_config.bcch, 'password', ''))
    checks.append(('BCCh API (Banco Central)', has_bcch, 'Datos Chile, commodities, tasas internacionales'))

    # Check AlphaVantage API
    has_av = False
    if gbk_config:
        has_av = bool(getattr(gbk_config.alphavantage, 'api_key', ''))
    checks.append(('AlphaVantage API', has_av, 'Earnings, factor analysis'))

    # Check daily reports
    _local_html = Path(__file__).resolve().parent / "html_out"
    _legacy_html = Path.home() / "OneDrive/Documentos/proyectos/html_out"
    html_out = Path(os.environ.get('DAILY_REPORTS_PATH', str(_local_html if _local_html.exists() else _legacy_html)))
    if html_out.exists():
        recent_reports = list(html_out.glob("*.html"))
        n_recent = len([f for f in recent_reports
                       if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days < 7])
        checks.append(('Daily Reports (html_out/)', n_recent > 0,
                       f'{len(recent_reports)} reportes, {n_recent} de la ultima semana'))
    else:
        checks.append(('Daily Reports (html_out/)', False, 'Carpeta no encontrada'))

    # Check DF summaries
    df_path = Path(os.environ.get('DF_DATA_PATH', str(Path.home() / "OneDrive/Documentos/df/df_data")))
    if df_path.exists():
        df_files = list(df_path.glob("resumen_df_*.txt"))
        checks.append(('Diario Financiero', len(df_files) > 0, f'{len(df_files)} resumenes'))
    else:
        checks.append(('Diario Financiero', False, 'Carpeta no encontrada'))

    # Check research
    checks.append(('Research Files', len(research_files) > 0,
                   f'{len(research_files)} archivos en input/research/'))

    # Check directives
    checks.append(('User Directives', bool(directives),
                   f'{len(directives)} chars' if directives else 'Vacio'))

    # Check Platform
    p = get_platform()
    checks.append(('Platform', p is not None, 'Conectada' if p else 'Error'))

    # Check Python packages
    packages = ['anthropic', 'yfinance', 'pdfplumber', 'pandas', 'matplotlib']
    for pkg in packages:
        try:
            mod = __import__(pkg)
            ver = getattr(mod, '__version__', '?')
            checks.append((f'Python: {pkg}', True, f'v{ver}'))
        except ImportError:
            checks.append((f'Python: {pkg}', False, 'No instalado'))

    # Display
    for name, ok, detail in checks:
        icon = "✅" if ok else "❌"
        st.markdown(f"{icon} **{name}** — {detail}")

    # Disk usage
    st.markdown("---")
    st.markdown('<div class="section-header">Espacio en Disco</div>', unsafe_allow_html=True)

    def dir_size(path):
        total = 0
        if path.exists():
            for f in path.rglob('*'):
                if f.is_file():
                    total += f.stat().st_size
        return total

    dirs_to_check = [
        ('output/council/', COUNCIL_DIR),
        ('output/reports/', REPORTS_DIR),
        ('output/equity_data/', EQUITY_DIR),
        ('output/rf_data/', RF_DATA_DIR),
        ('input/research/', RESEARCH_DIR),
    ]

    for label, path in dirs_to_check:
        size = dir_size(path)
        n_files = len(list(path.glob('*'))) if path.exists() else 0
        st.markdown(f"📁 **{label}** — {format_size(size)} ({n_files} archivos)")

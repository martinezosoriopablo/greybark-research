# -*- coding: utf-8 -*-
"""
Greybark Research - Pipeline Dashboard
=======================================

Dashboard Streamlit para configurar y ejecutar el pipeline mensual.

Uso:
    streamlit run dashboard.py
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

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

# Ensure dirs exist
for d in [RESEARCH_DIR, COUNCIL_DIR, REPORTS_DIR, EQUITY_DIR, RF_DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Add paths for imports
sys.path.insert(0, str(BASE_DIR))


# =========================================================================
# PAGE CONFIG
# =========================================================================

st.set_page_config(
    page_title="Greybark Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================================
# CUSTOM CSS
# =========================================================================

st.markdown("""
<style>
    /* Header */
    .main-header {
        font-family: 'Segoe UI', sans-serif;
        font-size: 28px;
        font-weight: 900;
        letter-spacing: 2px;
        color: #1a1a1a;
        border-bottom: 3px solid #dd6b20;
        padding-bottom: 8px;
        margin-bottom: 5px;
    }
    .main-subtitle {
        color: #dd6b20;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 25px;
    }

    /* Cards */
    .status-card {
        background: #f7f7f7;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 4px solid #dd6b20;
    }
    .status-ok { border-left-color: #276749; }
    .status-warn { border-left-color: #d69e2e; }
    .status-err { border-left-color: #c53030; }

    /* File list */
    .file-item {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 13px;
    }
    .file-item .name { font-weight: 600; }
    .file-item .size { color: #718096; font-size: 11px; }

    /* Phase progress */
    .phase-box {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 6px 0;
    }
    .phase-done { background: #f0fff4; border-color: #276749; }
    .phase-running { background: #fffff0; border-color: #d69e2e; }
    .phase-error { background: #fff5f5; border-color: #c53030; }

    /* Section headers */
    .section-header {
        font-size: 16px;
        font-weight: 700;
        color: #1a1a1a;
        border-bottom: 2px solid #dd6b20;
        padding-bottom: 6px;
        margin: 20px 0 12px 0;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown li,
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] label p,
    [data-testid="stSidebar"] span {
        color: #ffffff !important;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


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
        # Return only non-comment lines
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
        if 'macro' in f.name:
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


# =========================================================================
# SIDEBAR
# =========================================================================

with st.sidebar:
    st.markdown("### GREYBARK RESEARCH")
    st.markdown("*Pipeline Dashboard*")
    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navegacion",
        ["Pipeline", "Reportes", "Estado"],
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

    st.markdown("---")
    st.markdown(f"*{datetime.now().strftime('%d %b %Y %H:%M')}*")


# =========================================================================
# PAGE: PIPELINE
# =========================================================================

if page == "Pipeline":

    # Header
    st.markdown('<div class="main-header">GREYBARK RESEARCH</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Pipeline Mensual Unificado</div>', unsafe_allow_html=True)

    # Three columns layout
    col_research, col_directives = st.columns([1, 1])

    # ---- RESEARCH FILES ----
    with col_research:
        st.markdown('<div class="section-header">Research Files</div>', unsafe_allow_html=True)

        # Upload
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

        # List current files
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
            placeholder="Ej: Foco en impacto aranceles en Chile\nCreo que BCCh mantiene TPM\n¿Hay valor en Europa?",
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

        # Build reports list
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

        # Build command
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
                    elif '[FASE 3]' in line or 'AI COUNCIL SESSION' in line:
                        phase_status['fase_2'] = 'done'
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

            # Mark remaining as done or error
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
                    type_icons = {'macro': '🌍', 'rv': '📈', 'rf': '📉', 'aa': '💼'}
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

    st.markdown('<div class="main-header">GREYBARK RESEARCH</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-subtitle">Reportes Generados</div>', unsafe_allow_html=True)

    recent = get_recent_reports()

    if not recent:
        st.info("No hay reportes generados todavia.")
    else:
        # Group by date
        by_date = {}
        for r in recent:
            date_key = r['modified'].strftime('%Y-%m-%d')
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(r)

        for date_key, reports in by_date.items():
            st.markdown(f"### {date_key}")

            for r in reports:
                c1, c2, c3, c4 = st.columns([5, 2, 2, 2])
                type_labels = {'macro': 'Macro', 'rv': 'Renta Variable', 'rf': 'Renta Fija', 'aa': 'Asset Allocation'}
                type_icons = {'macro': '🌍', 'rv': '📈', 'rf': '📉', 'aa': '💼'}

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
# PAGE: ESTADO
# =========================================================================

elif page == "Estado":

    st.markdown('<div class="main-header">GREYBARK RESEARCH</div>', unsafe_allow_html=True)
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
    html_out = Path(os.environ.get('DAILY_REPORTS_PATH', str(Path.home() / "OneDrive/Documentos/proyectos/archivo_reportes/html")))
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

# -*- coding: utf-8 -*-
"""
WSJ Print Edition PDF Downloader
Descarga automáticamente el PDF del WSJ Print Edition usando Selenium.

Usa un perfil dedicado de Chrome persistente. La primera vez que se ejecuta,
abre Chrome visible para que hagas login con Google manualmente.
Después de eso, el perfil queda logueado y funciona automáticamente.

Uso:
    python download_wsj_pdf.py          # Descarga normal
    python download_wsj_pdf.py --setup  # Forzar modo setup (login manual)
"""

import os
import sys
import time
import glob
import shutil
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================================
# CONFIGURACION
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = r"C:\Users\I7 8700\Downloads"
SCREENSHOTS_DIR = os.path.join(SCRIPT_DIR, "logs")

# Perfil fuera de OneDrive para evitar conflictos de sync/lock
WSJ_PROFILE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", r"C:\Users\I7 8700\AppData\Local"), "wsj_chrome_profile")

# Ruta antigua (dentro de OneDrive) - para migración automática
_OLD_PROFILE_DIR = os.path.join(SCRIPT_DIR, "wsj_chrome_profile")

WSJ_PRINT_URL = "https://www.wsj.com/print-edition"
WSJ_LOGIN_URL = "https://www.wsj.com"

# ============================================================================
# HELPERS
# ============================================================================

def log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{level}] {ts} - {msg}")


def take_screenshot(driver, name):
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOTS_DIR, f"wsj_debug_{name}.png")
    try:
        driver.save_screenshot(path)
        log("INFO", f"Screenshot: {path}")
    except Exception:
        pass


def expected_pdf_name():
    today = datetime.now().strftime("%Y%m%d")
    return f"wallstreetjournal_{today}_TheWallStreetJournal.pdf"


def pdf_already_exists():
    target = os.path.join(DOWNLOAD_DIR, expected_pdf_name())
    return os.path.exists(target)


def migrate_profile_if_needed():
    """Migra el perfil de Chrome de OneDrive a AppData/Local si es necesario."""
    if os.path.exists(_OLD_PROFILE_DIR) and not os.path.exists(WSJ_PROFILE_DIR):
        log("INFO", f"Migrando perfil Chrome de OneDrive a {WSJ_PROFILE_DIR}...")
        try:
            shutil.copytree(_OLD_PROFILE_DIR, WSJ_PROFILE_DIR)
            log("OK", "Perfil migrado exitosamente")
        except Exception as e:
            log("WARN", f"Error migrando perfil (se creará uno nuevo): {e}")


def cleanup_lock_files():
    """Elimina lock files que Chrome deja al crashear, impidiendo nuevas sesiones."""
    lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
    for fname in lock_files:
        fpath = os.path.join(WSJ_PROFILE_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                log("INFO", f"Lock file eliminado: {fname}")
            except Exception:
                pass


def is_profile_setup():
    """Check if the dedicated profile has been set up (has cookies/login data)."""
    cookies_path = os.path.join(WSJ_PROFILE_DIR, "Default", "Network", "Cookies")
    login_data = os.path.join(WSJ_PROFILE_DIR, "Default", "Login Data")
    return os.path.exists(cookies_path) or os.path.exists(login_data)


# ============================================================================
# DRIVER
# ============================================================================

def create_driver(headless=False):
    """Create Chrome WebDriver with dedicated persistent profile."""
    os.makedirs(WSJ_PROFILE_DIR, exist_ok=True)
    cleanup_lock_files()

    options = Options()
    options.add_argument(f"--user-data-dir={WSJ_PROFILE_DIR}")

    # PDF download settings
    options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "profile.default_content_settings.popups": 0,
    })

    # Suppress automation flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-extensions")

    # Robustness flags para evitar crashes en Task Scheduler
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if headless:
        options.add_argument("--headless=new")

    # Auto-detect ChromeDriver version matching installed Chrome
    chromedriver_path = ChromeDriverManager().install()
    # webdriver-manager 4.x bug: puede devolver THIRD_PARTY_NOTICES en vez del .exe
    if not chromedriver_path.endswith(".exe"):
        chromedriver_path = os.path.join(os.path.dirname(chromedriver_path), "chromedriver.exe")
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1400, 900)

    log("INFO", "Chrome WebDriver iniciado")
    return driver


# ============================================================================
# SETUP (first-time login)
# ============================================================================

def run_setup():
    """Open Chrome for manual Google/WSJ login. Profile persists after close."""
    log("INFO", "=== MODO SETUP: Login manual requerido ===")
    log("INFO", f"Perfil se guardará en: {WSJ_PROFILE_DIR}")
    print()
    print("  INSTRUCCIONES:")
    print("  1. Se abrirá Chrome en wsj.com")
    print("  2. Haz click en 'Sign In'")
    print("  3. Loguéate con tu cuenta Google (martinezosoriopablo@gmail.com)")
    print("  4. Verifica que quedas logueado en WSJ")
    print("  5. Cierra Chrome manualmente o presiona Enter aquí")
    print()

    driver = create_driver(headless=False)

    try:
        driver.get(WSJ_LOGIN_URL)
        log("INFO", "Chrome abierto en wsj.com - haz login manualmente...")

        input(">>> Presiona ENTER cuando hayas terminado el login... ")

        # Verify login
        driver.get(WSJ_PRINT_URL)
        time.sleep(3)
        take_screenshot(driver, "setup_verify")

        page_source = driver.page_source.lower()
        if "sign in" in page_source and "sign out" not in page_source:
            log("WARN", "Parece que no estás logueado aún. Verifica el screenshot.")
        else:
            log("OK", "Login verificado correctamente")

    finally:
        driver.quit()
        log("INFO", "Chrome cerrado. Perfil guardado.")

    log("OK", "Setup completado. Ejecuta de nuevo sin --setup para descargar.")


# ============================================================================
# CHECK LOGIN STATUS
# ============================================================================

def check_logged_in(driver):
    """Check if we're logged into WSJ by looking at the page."""
    try:
        # Look for "Sign In" button (means NOT logged in)
        sign_in_buttons = driver.find_elements(By.XPATH,
            "//a[text()='Sign In'] | //button[text()='Sign In']")
        if sign_in_buttons:
            return False
        return True
    except Exception:
        return True  # assume logged in if check fails


# ============================================================================
# DOWNLOAD FLOW
# ============================================================================

def wait_for_pdf_download(timeout=120):
    log("INFO", f"Esperando descarga del PDF (timeout: {timeout}s)...")
    target_name = expected_pdf_name()
    target_path = os.path.join(DOWNLOAD_DIR, target_name)

    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(target_path):
            time.sleep(2)
            if os.path.exists(target_path):
                size = os.path.getsize(target_path)
                log("OK", f"PDF descargado: {target_name} ({size:,} bytes)")
                return True

        crdownload = glob.glob(os.path.join(DOWNLOAD_DIR, "wallstreetjournal_*.crdownload"))
        if crdownload:
            log("INFO", "Descarga en progreso...")

        time.sleep(3)

    log("ERROR", f"Timeout esperando PDF: {target_name}")
    return False


def download_wsj_pdf():
    """Main download flow."""
    driver = None

    try:
        # Check if already downloaded
        if pdf_already_exists():
            log("OK", f"PDF de hoy ya existe: {expected_pdf_name()}")
            return True

        # Check if profile needs setup
        if not is_profile_setup():
            log("ERROR", "Perfil no configurado. Ejecuta: python download_wsj_pdf.py --setup")
            return False

        # Create driver with persistent profile
        driver = create_driver(headless=False)

        # Go directly to the eReader
        EREADER_URL = "http://ereader.wsj.net/?editionStart=The+Wall+Street+Journal"
        log("INFO", f"Navegando al eReader WSJ...")
        driver.get(EREADER_URL)
        time.sleep(10)

        take_screenshot(driver, "step1_ereader_loaded")

        # Navigate through nested iframes: iframe1 -> iframe2 -> mainframe
        log("INFO", "Entrando a iframes del eReader...")
        try:
            iframe1 = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            driver.switch_to.frame(iframe1)
            log("INFO", "  -> iframe 1")

            iframe2 = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            driver.switch_to.frame(iframe2)
            log("INFO", "  -> iframe 2")

            mainframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "mainframe"))
            )
            driver.switch_to.frame(mainframe)
            log("INFO", "  -> mainframe")
        except TimeoutException:
            take_screenshot(driver, "step2_iframe_fail")
            log("ERROR", "No se pudo navegar los iframes del eReader")
            return False

        # Wait for content to fully load inside mainframe
        log("INFO", "Esperando carga del contenido del mainframe...")
        time.sleep(10)

        # Buscar link de descarga con multiples selectores (el texto varía)
        download_links = driver.find_elements(By.LINK_TEXT, "Download Edition")
        if not download_links:
            download_links = driver.find_elements(By.PARTIAL_LINK_TEXT, "Download")
        if not download_links:
            download_links = driver.find_elements(By.XPATH,
                "//*[contains(text(),'Download') and (contains(text(),'Edition') or contains(text(),'Full'))]")
        if not download_links:
            # Verificar si la función JS existe directamente
            has_func = driver.execute_script("return typeof downloadFullEdi === 'function'")
            if not has_func:
                log("ERROR", "No estás logueado o no se cargó el eReader. Ejecuta: python download_wsj_pdf.py --setup")
                take_screenshot(driver, "step3_no_download_link")
                return False
            log("INFO", "Link no encontrado pero función downloadFullEdi() existe")

        log("OK", "eReader cargado correctamente")

        # Click "Download Edition" via JavaScript
        # downloadFullEdi() shows a confirm() dialog which blocks JS execution,
        # so we call it asynchronously via setTimeout
        log("INFO", "Iniciando descarga via downloadFullEdi()...")
        driver.execute_script("setTimeout(function(){ downloadFullEdi(); }, 100);")

        # The eReader shows a JS confirm dialog: "Are you sure you want to download this edition?"
        time.sleep(2)
        try:
            alert = WebDriverWait(driver, 10).until(EC.alert_is_present())
            log("INFO", f"Aceptando diálogo: {alert.text[:60]}")
            alert.accept()
            log("OK", "Diálogo aceptado, descarga iniciada")
        except TimeoutException:
            log("INFO", "No hay diálogo de confirmación (OK)")

        take_screenshot(driver, "step4_after_download")

        # Wait for PDF
        if wait_for_pdf_download(timeout=120):
            return True
        else:
            today = datetime.now().strftime("%Y%m%d")
            alt_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*wallstreetjournal*{today}*.pdf"))
            if alt_files:
                log("OK", f"PDF encontrado: {os.path.basename(alt_files[0])}")
                return True
            take_screenshot(driver, "step7_timeout")
            return False

    except WebDriverException as e:
        log("ERROR", f"Error Selenium: {e}")
        if driver:
            take_screenshot(driver, "exception")
        return False
    except Exception as e:
        log("ERROR", f"Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if driver:
            try:
                driver.quit()
                log("INFO", "Chrome cerrado")
            except Exception:
                pass


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("WSJ PRINT EDITION PDF DOWNLOADER")
    print("=" * 70)
    print()

    if "--setup" in sys.argv:
        migrate_profile_if_needed()
        run_setup()
        sys.exit(0)

    # Migrar perfil de OneDrive a AppData si es la primera vez
    migrate_profile_if_needed()

    # Auto-detect if setup is needed
    if not is_profile_setup():
        log("INFO", "Primera ejecución detectada - iniciando setup...")
        run_setup()
        print()
        log("INFO", "Ahora intentando descarga...")
        print()

    success = download_wsj_pdf()

    print()
    if success:
        print("=" * 70)
        log("OK", "Descarga completada exitosamente")
        print("=" * 70)
        sys.exit(0)
    else:
        print("=" * 70)
        log("ERROR", "No se pudo descargar el PDF del WSJ")
        print("=" * 70)
        sys.exit(1)

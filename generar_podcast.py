# -*- coding: utf-8 -*-
"""
Generador de Podcast - Grey Bark Advisors
Convierte reportes HTML de mercados en archivos MP3 de podcast.

Pipeline:
1. Lee el reporte HTML más reciente (o uno específico)
2. Extrae texto limpio del HTML
3. Llama a Claude (Sonnet 4.5) para generar guión conversacional
4. Genera audio MP3 con Edge TTS (voz chilena)

Uso:
    python generar_podcast.py                              # Reporte más reciente
    python generar_podcast.py --reporte path/al/reporte.html
    python generar_podcast.py --turno AM                   # Forzar turno AM/PM
"""

import os
import sys
import glob
import argparse
import asyncio
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

import anthropic
from bs4 import BeautifulSoup
import edge_tts

# ============================================================================
# CONFIGURACION
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_HTML_DIR = os.path.join(SCRIPT_DIR, "archivo_reportes", "html")
HTML_OUT_DIR = os.path.join(SCRIPT_DIR, "html_out")
PODCAST_OUT_DIR = os.path.join(SCRIPT_DIR, "podcasts")

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
TTS_VOICE = "es-CL-CatalinaNeural"
TTS_RATE = "+10%"
MAX_GUION_CHARS = 10000

# ============================================================================
# HELPERS
# ============================================================================

def log(level, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{level}] {ts} - {msg}")


def detectar_turno():
    """Detecta AM/PM según la hora actual (Chile)."""
    hora = datetime.now().hour
    return "AM" if hora < 14 else "PM"


def buscar_reporte_html(turno=None):
    """Busca el reporte HTML finanzas más reciente."""
    if turno is None:
        turno = detectar_turno()

    # Buscar primero en html_out (reportes del día aún no archivados)
    pattern_out = os.path.join(HTML_OUT_DIR, f"daily_report_{turno}_finanzas_*.html")
    # Luego en archivo_reportes/html
    pattern_arch = os.path.join(ARCHIVO_HTML_DIR, f"daily_report_{turno}_finanzas_*.html")

    files = glob.glob(pattern_out) + glob.glob(pattern_arch)

    if not files:
        # Intentar sin filtro de turno
        pattern_any_out = os.path.join(HTML_OUT_DIR, "daily_report_*_finanzas_*.html")
        pattern_any_arch = os.path.join(ARCHIVO_HTML_DIR, "daily_report_*_finanzas_*.html")
        files = glob.glob(pattern_any_out) + glob.glob(pattern_any_arch)

    if not files:
        return None

    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0]


def extraer_texto_html(html_path):
    """Extrae texto limpio del HTML, eliminando tags y tablas de datos crudos."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # Extraer fecha y turno del header
    fecha_text = ""
    turno_text = ""
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        if "de 2026" in text or "de 2025" in text:
            fecha_text = text
            break

    # Extraer contenido principal (h2 + p), ignorando tablas de datos
    sections = []
    for tag in soup.find_all(["h2", "p"]):
        text = tag.get_text(strip=True)
        if not text:
            continue
        if tag.name == "h2":
            sections.append(f"\n## {text}\n")
        else:
            sections.append(text)

    content = "\n".join(sections)

    # Extraer datos del dashboard (primera tabla)
    dashboard = ""
    first_table = soup.find("table", style=lambda s: s and "border-radius" in s)
    if first_table:
        rows = first_table.find_all("tr")
        if len(rows) >= 3:
            headers = [td.get_text(strip=True) for td in rows[0].find_all("td")]
            changes = [td.get_text(strip=True) for td in rows[1].find_all("td")]
            values = [td.get_text(strip=True) for td in rows[2].find_all("td")]
            dashboard_parts = []
            for h, c, v in zip(headers, changes, values):
                dashboard_parts.append(f"{h}: {v} ({c})")
            dashboard = "Dashboard: " + " | ".join(dashboard_parts)

    return fecha_text, dashboard, content


def generar_guion_claude(fecha, dashboard, contenido, turno="AM", intro=None, outro=None):
    """Llama a Claude para convertir el reporte en guión de podcast."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log("ERROR", "Variable de entorno ANTHROPIC_API_KEY no configurada")
        return None, None

    client = anthropic.Anthropic(api_key=api_key)

    # Adaptar saludo y despedida: custom (intro/outro) o defaults Greybark
    if intro:
        saludo = intro.replace("{fecha}", fecha) if "{fecha}" in intro else intro
    elif turno == "PM":
        saludo = f"Buenas tardes, soy Camila, tu analista de Greybark Research y esto es tu Reporte de Cierre de Mercados del {fecha}"
    else:
        saludo = f"Buenos días, soy Camila, tu analista de Greybark Research y esto es tu Reporte de Mercados del {fecha}"

    if outro:
        despedida = outro
    elif turno == "PM":
        despedida = "Esto ha sido tu Reporte de Cierre de Mercados de Greybark Research. Que tengas una excelente tarde."
    else:
        despedida = "Esto ha sido tu Reporte de Mercados de Greybark Research. Que tengas un excelente día."

    prompt = f"""Convierte este reporte de mercados en un guión de podcast hablado en español chileno.

DATOS DEL DÍA:
{dashboard}

CONTENIDO DEL REPORTE:
{contenido}

INSTRUCCIONES:
- Formato conversacional en español chileno (natural, profesional pero cercano)
- Reemplaza TODOS los símbolos y números por texto hablado:
  - "-0.51%" → "medio punto porcentual a la baja" o "cayó medio por ciento"
  - "+0.36%" → "subió un tercio de punto"
  - "$66.13" → "66 dólares con 13 centavos"
  - "US$5.76" → "5 dólares con 76 centavos"
  - "10,809" → "diez mil ochocientos nueve"
  - "6,862" → "seis mil ochocientos sesenta y dos"
  - "US$901.5B" → "901 mil quinientos millones de dólares"
  - No uses siglas como "Q4", di "cuarto trimestre"
  - No uses "/" ni "&", escribe las palabras completas
- PRONUNCIACIÓN DE TÉRMINOS EN INGLÉS: El audio se genera con voz en español, por lo que los términos en inglés deben escribirse de forma fonética para que suenen naturales:
  - "S&P 500" → "ese and pi quinientos"
  - "NASDAQ" → "násdaq"
  - "Dow Jones" → "dau yons"
  - "yield" → "yield"
  - "spread" → "espred"
  - "rally" → "rali"
  - "sell-off" → "sel of"
  - "VIX" → "vix"
  - "ETF" → "e te efe"
  - "Fed" → "fed"
  - "FOMC" → "efe o eme ce"
  - Para otros términos en inglés, escríbelos fonéticamente en español
- Elimina tablas y datos redundantes
- Agrega transiciones naturales entre secciones ("Pasando a...", "En cuanto a...", "Ahora bien...")
- NO uses markdown, asteriscos, ni formato especial - solo texto plano para ser leído
- Comienza exactamente con: "{saludo}"
- Termina exactamente con: "{despedida}"
- Duración objetivo: 4-6 minutos de lectura (~4000-6000 caracteres). Cubre TODOS los temas del reporte sin omitir ninguno
- No incluyas emojis ni caracteres especiales

Escribe SOLO el guión, sin explicaciones ni comentarios."""

    log("INFO", f"Llamando a Claude ({CLAUDE_MODEL})...")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        guion = response.content[0].text
        usage = response.usage

        # Calcular costo aproximado (Sonnet 4.5: $3/$15 por 1M tokens)
        input_cost = usage.input_tokens * 3.0 / 1_000_000
        output_cost = usage.output_tokens * 15.0 / 1_000_000
        total_cost = input_cost + output_cost

        log("OK", f"Guión generado: {len(guion):,} caracteres")
        log("INFO", f"Tokens: {usage.input_tokens:,} input + {usage.output_tokens:,} output = {usage.input_tokens + usage.output_tokens:,} total")
        log("INFO", f"Costo aproximado: ${total_cost:.4f} USD")

        # Recortar si excede el máximo
        if len(guion) > MAX_GUION_CHARS:
            log("WARN", f"Guión excede {MAX_GUION_CHARS} chars ({len(guion)}), recortando...")
            # Buscar el último punto antes del límite
            cut_point = guion[:MAX_GUION_CHARS].rfind(".")
            if cut_point > MAX_GUION_CHARS * 0.7:
                guion = guion[:cut_point + 1]
                guion += "\n\n" + despedida
            else:
                guion = guion[:MAX_GUION_CHARS]
            log("INFO", f"Guión recortado a {len(guion):,} caracteres")

        return guion, total_cost

    except anthropic.AuthenticationError:
        log("ERROR", "API key inválida. Verifica ANTHROPIC_API_KEY")
        return None, None
    except anthropic.RateLimitError:
        log("ERROR", "Rate limit alcanzado. Intenta de nuevo en unos minutos")
        return None, None
    except anthropic.APIStatusError as e:
        log("ERROR", f"Error API Claude: {e.status_code} - {e.message}")
        return None, None
    except Exception as e:
        log("ERROR", f"Error inesperado llamando a Claude: {e}")
        return None, None


async def generar_audio_tts(guion, output_path):
    """Genera MP3 usando Edge TTS con voz chilena."""
    log("INFO", f"Generando audio con {TTS_VOICE} (rate: {TTS_RATE})...")

    communicate = edge_tts.Communicate(guion, TTS_VOICE, rate=TTS_RATE)
    await communicate.save(output_path)

    size = os.path.getsize(output_path)
    log("OK", f"Audio generado: {os.path.basename(output_path)} ({size:,} bytes)")


def inferir_turno_de_archivo(filepath):
    """Infiere AM/PM del nombre del archivo."""
    basename = os.path.basename(filepath).lower()
    if "_am_" in basename:
        return "AM"
    elif "_pm_" in basename:
        return "PM"
    return detectar_turno()


def inferir_fecha_de_archivo(filepath):
    """Infiere la fecha del nombre del archivo (formato YYYY-MM-DD)."""
    import re
    basename = os.path.basename(filepath)
    match = re.search(r"(\d{4}-\d{2}-\d{2})", basename)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


# ============================================================================
# CLIENT PIPELINE ENTRY POINT
# ============================================================================

def generate_podcast_for_client(html_path, turno, intro=None, outro=None, output_dir=None):
    """Genera podcast para un cliente. Retorna path al .mp3 o None."""
    fecha_texto, dashboard, contenido = extraer_texto_html(html_path)
    fecha = inferir_fecha_de_archivo(html_path)
    if not fecha_texto:
        fecha_texto = fecha

    guion, costo = generar_guion_claude(fecha_texto, dashboard, contenido, turno, intro=intro, outro=outro)
    if not guion:
        return None

    out_dir = output_dir or PODCAST_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    txt_path = os.path.join(out_dir, f"podcast_{fecha}_{turno}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(guion)

    mp3_path = os.path.join(out_dir, f"podcast_{fecha}_{turno}.mp3")
    asyncio.run(generar_audio_tts(guion, mp3_path))
    log("OK", f"Podcast cliente: {mp3_path}")
    return mp3_path


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generador de Podcast - Grey Bark Advisors")
    parser.add_argument("--reporte", type=str, help="Path al reporte HTML específico")
    parser.add_argument("--turno", type=str, choices=["AM", "PM"], help="Turno AM o PM")
    args = parser.parse_args()

    print("=" * 70)
    print("GREY BARK ADVISORS - GENERADOR DE PODCAST")
    print("=" * 70)
    print()

    # 1. Encontrar reporte HTML
    if args.reporte:
        html_path = args.reporte
        if not os.path.exists(html_path):
            log("ERROR", f"Archivo no encontrado: {html_path}")
            sys.exit(1)
    else:
        html_path = buscar_reporte_html(args.turno)
        if not html_path:
            log("ERROR", "No se encontró ningún reporte HTML")
            log("INFO", f"Buscado en: {HTML_OUT_DIR}")
            log("INFO", f"           {ARCHIVO_HTML_DIR}")
            sys.exit(1)

    turno = args.turno or inferir_turno_de_archivo(html_path)
    fecha = inferir_fecha_de_archivo(html_path)

    log("OK", f"Reporte: {os.path.basename(html_path)}")
    log("INFO", f"Turno: {turno} | Fecha: {fecha}")
    print()

    # 2. Extraer texto del HTML
    log("INFO", "Extrayendo texto del HTML...")
    fecha_texto, dashboard, contenido = extraer_texto_html(html_path)
    if not fecha_texto:
        fecha_texto = fecha
    log("OK", f"Texto extraído: {len(contenido):,} caracteres")

    # 3. Generar guión con Claude
    guion, costo = generar_guion_claude(fecha_texto, dashboard, contenido, turno)
    if not guion:
        log("ERROR", "No se pudo generar el guión")
        sys.exit(1)

    # 4. Guardar guión como .txt
    os.makedirs(PODCAST_OUT_DIR, exist_ok=True)
    txt_filename = f"podcast_greybark_{fecha}_{turno}.txt"
    txt_path = os.path.join(PODCAST_OUT_DIR, txt_filename)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(guion)
    log("OK", f"Guión guardado: {txt_filename}")

    # 5. Generar audio MP3
    mp3_filename = f"podcast_greybark_{fecha}_{turno}.mp3"
    mp3_path = os.path.join(PODCAST_OUT_DIR, mp3_filename)

    asyncio.run(generar_audio_tts(guion, mp3_path))

    # Resumen
    print()
    print("=" * 70)
    log("OK", "Podcast generado exitosamente")
    print("=" * 70)
    print(f"  Guión: {txt_path}")
    print(f"  Audio: {mp3_path}")
    print(f"  Costo: ${costo:.4f} USD")
    print()


if __name__ == "__main__":
    main()

"""
QUANTITATIVE WEEKLY REPORT GENERATOR
Genera el reporte semanal cuantitativo usando datos de Alpha Vantage
"""

import os
import json
import sys
from datetime import datetime, date
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

PROMPT_FILE = "prompt_quantitative_weekly.txt"
INPUT_JSON_PATTERN = "quantitative_weekly_data_*.json"

SYSTEM_PROMPT = (
    "Eres un estratega cuantitativo senior especializado en análisis de mercados. "
    "Produces reportes semanales altamente cuantitativos para inversionistas institucionales. "
    "Tu análisis es riguroso, objetivo y basado exclusivamente en datos. "
    "No especulas ni haces predicciones sin fundamento cuantitativo. "
    "Usas tablas, métricas y análisis técnico profesional."
)


# ============================================================================
# FUNCIONES
# ============================================================================

def find_latest_data_file() -> str:
    """Encuentra el archivo de datos más reciente"""
    import glob
    
    files = glob.glob(INPUT_JSON_PATTERN)
    
    if not files:
        raise FileNotFoundError(
            f"No se encontró ningún archivo que coincida con el patrón: {INPUT_JSON_PATTERN}\n"
            "Ejecuta primero: python quantitative_data_collector.py"
        )
    
    # Ordenar por fecha en el nombre del archivo
    files.sort(reverse=True)
    latest = files[0]
    
    print(f"[INFO] Usando archivo de datos: {latest}")
    return latest


def load_prompt_template() -> str:
    """Carga el template del prompt"""
    if not os.path.exists(PROMPT_FILE):
        raise FileNotFoundError(f"No se encontró el archivo: {PROMPT_FILE}")
    
    print(f"[INFO] Cargando prompt desde: {PROMPT_FILE}")
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        return f.read()


def load_dataset(json_path: str) -> dict:
    """Carga el dataset JSON"""
    print(f"[INFO] Cargando dataset desde: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[OK] Dataset cargado correctamente")
    return data


def generate_report(dataset: dict, prompt_template: str) -> str:
    """Genera el reporte usando OpenAI API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY no está definido en .env")
    
    client = OpenAI(api_key=api_key)
    
    # Preparar el JSON para el prompt
    json_payload = json.dumps(dataset, ensure_ascii=False, indent=2)
    
    user_prompt = prompt_template + "\n\n" + "="*80 + "\n"
    user_prompt += "DATASET JSON DE LA SEMANA:\n\n" + json_payload
    
    print("[INFO] Generando reporte cuantitativo semanal...")
    print("[INFO] Llamando a OpenAI API (esto puede tomar 30-60 segundos)...")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Usar gpt-4o para mejor análisis cuantitativo
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Más bajo para ser más objetivo/cuantitativo
        )
        
        content = response.choices[0].message.content
        print("[OK] Reporte generado correctamente")
        
        return content
        
    except Exception as e:
        print(f"[ERROR] Error al llamar a OpenAI API: {e}")
        raise


def save_report(content: str, output_file: str):
    """Guarda el reporte en markdown"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[OK] Reporte guardado en: {output_file}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("QUANTITATIVE WEEKLY REPORT GENERATOR")
    print("="*80)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # 1. Encontrar archivo de datos más reciente
        data_file = find_latest_data_file()
        
        # 2. Cargar prompt template
        prompt_template = load_prompt_template()
        
        # 3. Cargar dataset
        dataset = load_dataset(data_file)
        
        # 4. Generar reporte
        report_content = generate_report(dataset, prompt_template)
        
        # 5. Guardar reporte
        today = date.today().isoformat()
        output_file = f"quantitative_weekly_report_{today}.md"
        save_report(report_content, output_file)
        
        print("\n" + "="*80)
        print("PROCESO COMPLETADO EXITOSAMENTE")
        print("="*80)
        print(f"\nReporte generado: {output_file}")
        print(f"Tamaño: {len(report_content):,} caracteres")
        print()
        
        return 0
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

# -*- coding: utf-8 -*-
"""
WSJ PDF PARSER
Extrae contenido del WSJ PDF descargado manualmente

CONFIGURACIÓN:
Por defecto busca en C:/Users/marti/Downloads
Puedes cambiar esto:
1. Al llamar la función: load_wsj_pdf_content("C:/otra/ruta")
2. Variable de entorno: WSJ_PDF_DIR
3. Editar DEFAULT_PDF_DIR abajo
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import PyPDF2
from datetime import datetime

# CONFIGURACIÓN DEFAULT
DEFAULT_PDF_DIR = "C:/Users/I7 8700/Downloads"

def get_pdf_directory() -> str:
    """
    Obtiene el directorio donde buscar PDFs del WSJ
    Prioridad: 1) Variable de entorno, 2) DEFAULT_PDF_DIR
    """
    return os.environ.get('WSJ_PDF_DIR', DEFAULT_PDF_DIR)

def parse_wsj_pdf(pdf_path: str) -> Optional[Dict[str, Any]]:
    """
    Parsea un PDF del WSJ y extrae texto estructurado
    
    Args:
        pdf_path: Ruta al archivo PDF del WSJ
    
    Returns:
        Dict con contenido estructurado o None si falla
    """
    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF no encontrado: {pdf_path}")
        return None
    
    try:
        print(f"[INFO] Parseando WSJ PDF: {pdf_path}")
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            print(f"[INFO] WSJ PDF: {num_pages} páginas")
            
            # Extraer texto de todas las páginas
            full_text = ""
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                full_text += page.extract_text() + "\n\n"
            
            # Metadata del archivo
            file_date = datetime.fromtimestamp(os.path.getmtime(pdf_path))
            
            result = {
                "source": "WSJ PDF",
                "date": file_date.strftime("%Y-%m-%d"),
                "num_pages": num_pages,
                "full_text": full_text,
                "char_count": len(full_text),
                "file_path": pdf_path
            }
            
            print(f"[OK] WSJ PDF parseado: {len(full_text):,} caracteres")
            
            return result
            
    except Exception as e:
        print(f"[ERROR] Error parseando WSJ PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_latest_wsj_pdf(pdf_dir: Optional[str] = None) -> Optional[str]:
    """
    Busca el PDF del WSJ más reciente en un directorio
    
    El WSJ PDF sigue este patrón de nombre:
    wallstreetjournal_YYYYMMDD_TheWallStreetJournal.pdf
    Ejemplo: wallstreetjournal_20260108_TheWallStreetJournal.pdf
    
    Args:
        pdf_dir: Directorio donde buscar PDFs (None = usa configuración default)
    
    Returns:
        Ruta al PDF más reciente o None
    """
    import glob
    
    # Si no se especifica directorio, usar configuración
    if pdf_dir is None:
        pdf_dir = get_pdf_directory()
    
    print(f"[INFO] Buscando WSJ PDF en: {pdf_dir}")
    
    # Verificar que el directorio exista
    if not os.path.exists(pdf_dir):
        print(f"[ERROR] Directorio no existe: {pdf_dir}")
        print(f"[TIP] Verifica la ruta o configura WSJ_PDF_DIR en variables de entorno")
        return None
    
    # Buscar archivos con el patrón exacto del WSJ
    pattern = os.path.join(pdf_dir, "wallstreetjournal_*_TheWallStreetJournal.pdf")
    
    files = glob.glob(pattern)
    
    if not files:
        print(f"[WARN] No se encontraron PDFs del WSJ en: {pdf_dir}")
        print(f"[WARN] Buscando patrón: wallstreetjournal_YYYYMMDD_TheWallStreetJournal.pdf")
        return None
    
    # Ordenar por fecha de modificación (más reciente primero)
    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    latest = files[0]
    print(f"[INFO] WSJ PDF más reciente: {os.path.basename(latest)}")
    
    return latest


# INTEGRACIÓN CON daily_market_snapshot.py

def load_wsj_pdf_content(pdf_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Función para integrar en daily_market_snapshot.py
    
    Busca y parsea el PDF del WSJ más reciente
    
    Args:
        pdf_dir: Directorio donde buscar (None = usa C:/Users/marti/Downloads)
    
    Returns:
        Dict con contenido del PDF o None si no se encuentra
    """
    pdf_path = find_latest_wsj_pdf(pdf_dir)
    
    if not pdf_path:
        return None
    
    return parse_wsj_pdf(pdf_path)


if __name__ == "__main__":
    # TEST
    print("="*80)
    print("WSJ PDF PARSER - TEST")
    print("="*80)
    
    print(f"\nDirectorio configurado: {get_pdf_directory()}")
    print(f"Para cambiar, edita DEFAULT_PDF_DIR en este archivo\n")
    
    # Buscar PDF
    pdf_path = find_latest_wsj_pdf()
    
    if pdf_path:
        # Parsear
        result = parse_wsj_pdf(pdf_path)
        
        if result:
            print("\n" + "="*80)
            print("RESULTADO")
            print("="*80)
            print(f"Fecha: {result['date']}")
            print(f"Páginas: {result['num_pages']}")
            print(f"Caracteres: {result['char_count']:,}")
            print(f"\nPrimeros 500 caracteres:")
            print("-"*80)
            print(result['full_text'][:500])
            print("...")
    else:
        print("\n" + "="*80)
        print("[ERROR] No se encontró ningún PDF del WSJ")
        print("="*80)
        print("\n¿Qué hacer?")
        print("1. Verifica que descargaste el PDF del WSJ hoy")
        print(f"2. Verifica que está en: {get_pdf_directory()}")
        print("3. Verifica que el nombre es: wallstreetjournal_YYYYMMDD_TheWallStreetJournal.pdf")
        print("\nEjemplo: wallstreetjournal_20260108_TheWallStreetJournal.pdf")
        print("\nPara cambiar el directorio de búsqueda:")
        print("  - Opción 1: Edita DEFAULT_PDF_DIR en la línea 17 de este archivo")
        print("  - Opción 2: Variable de entorno WSJ_PDF_DIR")

"""
Greybark Research - Research Processing Script
================================================

Script para procesar PDFs de research institucional.

USO:
    1. Coloca tus PDFs en la carpeta 'research/'
    2. Ejecuta: python process_research.py
    3. El digest se guarda en 'research_digest.json'

FUENTES SOPORTADAS:
    - JPMorgan Guide to the Markets
    - Goldman Sachs Top of Mind
    - Bank of America Fund Manager Survey
    - PIMCO Cyclical Outlook
    - Cualquier otro PDF de research financiero

EJEMPLO:
    python process_research.py --pdf "mi_reporte.pdf"
    python process_research.py --folder research/
    python process_research.py --pdf "jpm_guide_q1_2026.pdf" --source jpm_guide
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Agregar greybark al path
greybark_path = Path(__file__).parent / "02_greybark_library"
sys.path.insert(0, str(greybark_path))

from greybark.ai_council.data_integration import ResearchCollector, RESEARCH_SOURCES


def main():
    parser = argparse.ArgumentParser(
        description='Procesar PDFs de research institucional',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python process_research.py --pdf "jpm_guide.pdf"
  python process_research.py --folder research/
  python process_research.py --pdf "report.pdf" --source bofa_fms

Fuentes soportadas: jpm_guide, gs_top_of_mind, bofa_fms, pimco_outlook, generic
        """
    )

    parser.add_argument('--pdf', help='PDF individual a procesar')
    parser.add_argument('--folder', default='pdf', help='Carpeta con PDFs (default: pdf/)')
    parser.add_argument('--output', default='research_digest.json', help='Archivo de salida')
    parser.add_argument('--source', choices=list(RESEARCH_SOURCES.keys()),
                       help='Forzar tipo de fuente (auto-detecta si no se especifica)')
    parser.add_argument('--list-sources', action='store_true', help='Listar fuentes soportadas')

    args = parser.parse_args()

    # Listar fuentes
    if args.list_sources:
        print("\n" + "=" * 60)
        print("FUENTES DE RESEARCH SOPORTADAS")
        print("=" * 60)
        for key, config in RESEARCH_SOURCES.items():
            print(f"\n  {key}:")
            print(f"    {config['name']}")
            print(f"    Publisher: {config['publisher']}")
            print(f"    Frecuencia: {config['frequency']}")
        print()
        return

    # Verificar API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\nERROR: Necesitas configurar tu API key de Anthropic")
        print("\nOpciones:")
        print("  1. export ANTHROPIC_API_KEY='sk-ant-...'")
        print("  2. set ANTHROPIC_API_KEY=sk-ant-... (Windows)")
        return

    print("\n" + "=" * 60)
    print("GREY BARK - RESEARCH PROCESSOR")
    print("=" * 60)

    # Inicializar collector
    collector = ResearchCollector(api_key=api_key, verbose=True)

    # Procesar PDF individual
    if args.pdf:
        if not os.path.exists(args.pdf):
            print(f"\nERROR: No se encontro el archivo: {args.pdf}")
            return

        result = collector.process_pdf(args.pdf, source=args.source)

        # Guardar resultado individual
        output_file = args.pdf.replace('.pdf', '_processed.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n[OK] Resultado guardado en: {output_file}")

        # Mostrar resumen
        if result.get('parse_success'):
            print(f"\nRESUMEN:")
            print(f"  Fuente: {result.get('source', 'Unknown')}")
            print(f"  Tesis: {result.get('main_thesis', 'N/A')[:100]}...")
            print(f"  Relevancia: {result.get('relevance_score', 'N/A')}%")

    # Procesar carpeta
    else:
        folder = args.folder

        if not os.path.exists(folder):
            print(f"\nCarpeta '{folder}' no existe. Creandola...")
            os.makedirs(folder)
            print(f"\nColoca tus PDFs de research en: {os.path.abspath(folder)}/")
            print("\nEjemplo de archivos:")
            print("  - jpm_guide_to_markets_q1_2026.pdf")
            print("  - gs_top_of_mind_jan_2026.pdf")
            print("  - bofa_fund_manager_survey_jan.pdf")
            return

        # Verificar que hay PDFs
        pdfs = list(Path(folder).glob('*.pdf'))
        if not pdfs:
            print(f"\nNo se encontraron PDFs en: {os.path.abspath(folder)}/")
            print("\nColoca tus PDFs de research ahi y vuelve a ejecutar.")
            return

        print(f"\nEncontrados {len(pdfs)} PDFs en {folder}/")

        # Procesar todos
        collector.process_folder(folder)

        # Guardar digest
        collector.save_digest(args.output)

        print(f"\n[OK] Digest guardado en: {args.output}")

        # Mostrar resumen
        digest = collector.get_research_digest()
        print(f"\nRESUMEN:")
        print(f"  Reportes procesados: {digest['metadata']['reports_processed']}")
        print(f"  Fuentes: {', '.join(digest['metadata']['sources'])}")


if __name__ == "__main__":
    main()

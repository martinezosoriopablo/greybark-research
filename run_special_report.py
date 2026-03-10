# -*- coding: utf-8 -*-
"""
Greybark Research — Special Thematic Report
============================================

Runs the AI Council focused on a specific topic using uploaded articles
as the dominant research input.

Usage:
    python run_special_report.py --topic "Impacto aranceles en LatAm" --articles ./input/special/aranceles/
    python run_special_report.py -t "AI y semiconductores" -a ./input/special/ai_chips/ --no-modules
"""

import argparse
import sys
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from research_analyzer import ResearchAnalyzer
from ai_council_runner import AICouncilRunner


def read_articles(folder: Path, verbose: bool = True) -> str:
    """Read PDFs/text files from a custom folder using ResearchAnalyzer internals."""
    analyzer = ResearchAnalyzer(verbose=verbose)
    parts = []

    for ext in ('*.txt', '*.md'):
        for fp in sorted(folder.glob(ext)):
            try:
                content = fp.read_text(encoding='utf-8').strip()
                if content:
                    parts.append(f"=== {fp.name} ===\n{content}")
                    if verbose:
                        print(f"  [OK] {fp.name} ({len(content)} chars)")
            except Exception:
                continue

    for fp in sorted(folder.glob('*.pdf')):
        content = analyzer._read_pdf(fp)
        if content:
            parts.append(f"=== {fp.name} ===\n{content}")

    return '\n\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description='Greybark Special Thematic Report')
    parser.add_argument('--topic', '-t', required=True, help='Tema del reporte especial')
    parser.add_argument('--articles', '-a', required=True, help='Carpeta con artículos (PDF/TXT/MD)')
    parser.add_argument('--output', '-o', help='Archivo de salida JSON')
    parser.add_argument('--no-modules', action='store_true', help='Skip analytics modules')
    parser.add_argument('--no-daily', action='store_true', default=True,
                        help='Suppress daily reports (default: True)')
    parser.add_argument('--with-daily', action='store_true', help='Include daily reports as background context')
    parser.add_argument('--lang', default='es', choices=['es', 'en'], help='Output language (default: es)')
    parser.add_argument('--extra', default='', help='Extra directives appended to agent instructions')

    args = parser.parse_args()

    articles_dir = Path(args.articles)
    if not articles_dir.exists():
        print(f"[ERROR] Carpeta no encontrada: {articles_dir}")
        sys.exit(1)

    # --- Read articles ---
    print("=" * 60)
    print(f"REPORTE ESPECIAL: {args.topic}")
    print("=" * 60)
    print(f"\nLeyendo artículos de: {articles_dir}")

    raw_articles = read_articles(articles_dir)
    if not raw_articles:
        print("[ERROR] No se encontraron artículos en la carpeta")
        sys.exit(1)

    article_count = raw_articles.count('===') // 2
    print(f"\n  {article_count} artículos leídos ({len(raw_articles)} chars)")

    # --- Synthesize articles with Claude ---
    print("\nSintetizando artículos con Claude...")
    analyzer = ResearchAnalyzer(verbose=True)
    if analyzer.api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=analyzer.api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=(
                "Eres un analista de research. Sintetiza los siguientes artículos "
                f"enfocándote en el tema: {args.topic}. Extrae las tesis principales, "
                "datos clave, puntos de consenso y disenso entre los artículos. "
                "Escribe en español profesional. 1500-2000 palabras."
            ),
            messages=[{"role": "user", "content": raw_articles[:80000]}]
        )
        synthesized = response.content[0].text
        print(f"  Síntesis: {len(synthesized)} chars")
    else:
        synthesized = raw_articles[:15000]
        print("  [WARN] Sin API key — usando texto crudo")

    # --- Build directives ---
    if args.lang == 'en':
        lang_instruction = "LANGUAGE: Write the ENTIRE report in English. All analysis, conclusions, and recommendations must be in English."
    else:
        lang_instruction = ""

    directives = (
        f"REPORTE ESPECIAL TEMÁTICO: {args.topic}\n\n"
        "Este es un reporte especial enfocado en un tema específico, NO un comité regular.\n"
        "Tu análisis DEBE centrarse en este tema. Usa los datos cuantitativos y módulos "
        "solo en la medida que sean relevantes para este tema.\n"
        "Los artículos de research proporcionados son el input principal — analízalos en profundidad.\n"
        f"{lang_instruction}\n"
        f"{args.extra}"
    )

    # --- Create runner and patch council_input ---
    runner = AICouncilRunner(verbose=True)
    runner.refinador_max_tokens = 4000
    suppress_daily = not args.with_daily

    original_prepare = runner.data_collector.prepare_council_input

    def patched_prepare(report_type):
        ci = original_prepare(report_type)
        ci['external_research'] = synthesized
        ci['user_directives'] = directives
        if suppress_daily:
            ci['daily_context'] = ''
            ci['intelligence_briefing'] = ''
        return ci

    runner.data_collector.prepare_council_input = patched_prepare

    # --- Optionally skip modules ---
    if args.no_modules:
        # Patch run_session to skip module block
        original_run = runner.run_session

        async def patched_run(report_type='macro'):
            result = await original_run(report_type)
            return result

        # Simpler: just set a flag the module block checks
        runner._skip_modules = True

    # --- Run council session ---
    print(f"\nEjecutando AI Council enfocado en: {args.topic}\n")
    result = runner.run_session_sync(report_type='macro')

    # Tag the result
    result['metadata']['special_report'] = True
    result['metadata']['topic'] = args.topic
    result['metadata']['article_count'] = article_count
    result['metadata']['articles_folder'] = str(articles_dir)

    # --- Save ---
    if args.output:
        runner.save_result(result, args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_dir = Path(__file__).parent / 'output' / 'special_reports'
        out_dir.mkdir(parents=True, exist_ok=True)
        outpath = out_dir / f'special_{timestamp}.json'
        runner.save_result(result, str(outpath))

    # --- Preview ---
    print("\n" + "=" * 60)
    print(f"REPORTE ESPECIAL: {args.topic}")
    print("=" * 60)
    print(result['final_recommendation'][:3000])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        traceback.print_exc()

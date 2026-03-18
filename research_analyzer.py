# -*- coding: utf-8 -*-
"""
Greybark Research - Research Analyzer
======================================

Analiza reportes de bancos de inversión usando un LLM para extraer:
- Temas principales de cada fuente
- Consenso del sell-side (en qué coinciden)
- Discrepancias clave (dónde divergen)
- Implicancias tácticas para el portafolio

El output reemplaza el texto crudo — es más conciso y útil para
los agentes del AI Council.

Uso:
    analyzer = ResearchAnalyzer()
    result = analyzer.analyze()  # Lee input/research/ y sintetiza
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Agregar greybark al path para acceder a config
GREYBARK_PATH = Path(__file__).parent
sys.path.insert(0, str(GREYBARK_PATH))

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

INPUT_DIR = Path(__file__).parent / "input"

# Modelo rápido y barato para síntesis
ANALYSIS_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000

SYNTHESIS_PROMPT = """Eres un analista senior de inversiones. Tu tarea es sintetizar los reportes de research de bancos de inversión que recibes.

Analiza los reportes y produce un resumen estructurado EN ESPAÑOL con las siguientes secciones:

## FUENTES ANALIZADAS
- Lista cada fuente con su fecha y foco principal (1 línea cada una)

## TEMAS PRINCIPALES
- Los 3-5 temas macro más relevantes que emergen del research
- Para cada tema: qué dicen los bancos, con qué convicción

## CONSENSO DEL SELL-SIDE
- Puntos donde la mayoría de los bancos coinciden
- Nivel de convicción (alto/medio/bajo)

## DISCREPANCIAS CLAVE
- Puntos donde los bancos divergen significativamente
- Quién dice qué y por qué

## IMPLICANCIAS PARA EL PORTAFOLIO
- 3-5 conclusiones accionables que emergen del research
- Distinguir entre visión de corto plazo (1-3 meses) y mediano plazo (6-12 meses)

## RIESGOS IDENTIFICADOS
- Riesgos que los bancos mencionan y su probabilidad implícita

Sé conciso, directo, y prioriza la información accionable. Máximo 800 palabras."""


class ResearchAnalyzer:
    """Analiza research externo de bancos de inversión con LLM."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.api_key = self._get_api_key()

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _get_api_key(self) -> Optional[str]:
        """Busca API key de Anthropic."""
        key = os.environ.get('ANTHROPIC_API_KEY')
        if not key:
            try:
                from greybark.config import CLAUDE_API_KEY
                key = CLAUDE_API_KEY
            except ImportError:
                pass
        return key

    def read_research_files(self) -> str:
        """Lee todos los archivos de research de input/research/ (TXT, MD, PDF)."""
        research_dir = INPUT_DIR / "research"
        if not research_dir.exists():
            return ''

        parts = []

        # Text files
        for ext in ('*.txt', '*.md'):
            for filepath in sorted(research_dir.glob(ext)):
                if filepath.name.upper().startswith('README'):
                    continue
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    if content and not content.startswith('#'):
                        parts.append(f"=== {filepath.name} ===\n{content}")
                except Exception:
                    continue

        # PDF files
        for filepath in sorted(research_dir.glob('*.pdf')):
            try:
                content = self._read_pdf(filepath)
                if content:
                    parts.append(f"=== {filepath.name} ===\n{content}")
            except Exception as e:
                self._print(f"  [WARN] No se pudo leer {filepath.name}: {e}")
                continue

        return '\n\n'.join(parts)

    def _read_pdf(self, filepath: Path) -> str:
        """Extrae texto de un PDF usando pdfplumber (fallback: PyPDF2)."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            text = '\n'.join(text_parts).strip()
            if text:
                self._print(f"  [OK] PDF: {filepath.name} ({len(text)} chars, {len(text_parts)} páginas)")
                return text
        except Exception:
            pass

        # Fallback: PyPDF2
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(filepath))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = '\n'.join(text_parts).strip()
            if text:
                self._print(f"  [OK] PDF (PyPDF2): {filepath.name} ({len(text)} chars)")
                return text
        except Exception:
            pass

        return ''

    def analyze(self) -> str:
        """
        Lee los archivos de research y los analiza con Claude.

        Returns:
            Síntesis estructurada del research. Si no hay API o no hay
            archivos, retorna el texto crudo o vacío.
        """
        raw_research = self.read_research_files()

        if not raw_research:
            self._print("[ResearchAnalyzer] Sin archivos de research")
            return ''

        file_count = raw_research.count('===') // 2
        self._print(f"[ResearchAnalyzer] {file_count} archivos de research ({len(raw_research)} chars)")

        # Si no hay API key, retornar texto crudo
        if not HAS_ANTHROPIC or not self.api_key:
            self._print("[ResearchAnalyzer] Sin API key — retornando texto crudo")
            return raw_research

        # Llamar a Claude para sintetizar
        self._print("[ResearchAnalyzer] Analizando research con Claude...")

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=ANALYSIS_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYNTHESIS_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Aquí están los reportes de research para analizar:\n\n{raw_research}"
                }]
            )
            synthesis = response.content[0].text
            self._print(f"[ResearchAnalyzer] Síntesis generada: {len(synthesis)} chars")
            return synthesis

        except Exception as e:
            self._print(f"[ResearchAnalyzer] Error en LLM: {e} — retornando texto crudo")
            return raw_research


def main():
    """Test del Research Analyzer."""
    print("=" * 60)
    print("RESEARCH ANALYZER - TEST")
    print("=" * 60)

    analyzer = ResearchAnalyzer(verbose=True)

    # Leer archivos
    raw = analyzer.read_research_files()
    if raw:
        print(f"\nResearch crudo: {len(raw)} chars")
        print(f"Preview:\n{raw[:500]}...\n")

    # Analizar
    print("--- Analizando con LLM ---")
    result = analyzer.analyze()
    print(f"\nSíntesis: {len(result)} chars")
    print("\n" + result)


if __name__ == "__main__":
    main()

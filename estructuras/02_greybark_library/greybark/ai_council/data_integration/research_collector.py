"""
Greybark Research - Research PDF Collector
============================================

Modulo para ingerir y estructurar research institucional de Wall Street.

Soporta:
- JPMorgan Guide to the Markets
- Goldman Sachs Top of Mind
- Bank of America Fund Manager Survey
- PIMCO Cyclical Outlook
- Morgan Stanley Sunday Start
- Vanguard Economic Outlook
- Cualquier PDF de research financiero

Uso:
    from greybark.ai_council.data_integration.research_collector import ResearchCollector

    collector = ResearchCollector(api_key='your-anthropic-key')

    # Procesar un PDF
    result = collector.process_pdf('path/to/jpm_guide.pdf', source='jpm_guide')

    # Procesar carpeta completa
    results = collector.process_folder('research_pdfs/')

    # Obtener digest para el AI Council
    digest = collector.get_research_digest()
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


# =============================================================================
# RESEARCH SOURCE DEFINITIONS
# =============================================================================

RESEARCH_SOURCES = {
    'jpm_guide': {
        'name': 'JPMorgan Guide to the Markets',
        'publisher': 'JPMorgan Asset Management',
        'frequency': 'quarterly',
        'focus': 'Multi-asset overview with extensive charts',
        'key_sections': [
            'equity_valuations',
            'fixed_income_yields',
            'economic_indicators',
            'asset_class_returns',
            'sector_performance',
            'global_markets'
        ],
        'extraction_prompt': """
Extrae la informacion clave de este JPMorgan Guide to the Markets:

1. EQUITY VALUATIONS
   - S&P 500 P/E forward actual
   - P/E vs promedio historico
   - Earnings growth esperado
   - Sectores mas/menos caros

2. FIXED INCOME
   - Yields actuales por duration
   - Credit spreads IG y HY
   - Expectativas de tasas

3. ECONOMIC INDICATORS
   - GDP growth
   - Inflacion
   - Desempleo
   - Leading indicators

4. KEY CHARTS
   - Los 3-5 charts mas importantes y su mensaje

5. MAIN CONCLUSIONS
   - Tesis principal del reporte
   - Asset allocation implicita
"""
    },

    'gs_top_of_mind': {
        'name': 'Goldman Sachs Top of Mind',
        'publisher': 'Goldman Sachs Research',
        'frequency': 'weekly',
        'focus': 'Deep dive on single macro topic',
        'key_sections': [
            'main_thesis',
            'key_arguments',
            'market_implications',
            'trade_ideas',
            'risks'
        ],
        'extraction_prompt': """
Extrae la informacion clave de este Goldman Sachs Top of Mind:

1. TEMA PRINCIPAL
   - Cual es el tema que analizan
   - Por que es relevante ahora

2. TESIS PRINCIPAL
   - Argumento central de GS
   - Datos que lo sustentan

3. IMPLICACIONES DE MERCADO
   - Que asset classes se ven afectadas
   - Direccion esperada

4. TRADE IDEAS
   - Recomendaciones especificas
   - Posiciones sugeridas

5. RIESGOS
   - Que podria salir mal
   - Escenarios alternativos
"""
    },

    'bofa_fms': {
        'name': 'Bank of America Fund Manager Survey',
        'publisher': 'Bank of America Global Research',
        'frequency': 'monthly',
        'focus': 'Institutional positioning and sentiment',
        'key_sections': [
            'cash_levels',
            'most_crowded_trade',
            'biggest_tail_risk',
            'regional_allocation',
            'sector_allocation',
            'asset_allocation'
        ],
        'extraction_prompt': """
Extrae la informacion clave de este BofA Fund Manager Survey:

1. CASH LEVELS
   - Nivel actual de cash de los managers
   - Comparacion vs historico (bullish si alto, bearish si bajo)

2. MOST CROWDED TRADE
   - Cual es la posicion mas consensuada
   - Esto es un riesgo contrarian

3. BIGGEST TAIL RISK
   - Que temen mas los managers
   - Probabilidad implicita

4. ALLOCATIONS
   - Regiones: overweight/underweight US, Europe, EM, Japan
   - Sectores: overweight/underweight Tech, Financials, Energy, etc.
   - Asset classes: equities vs bonds vs cash

5. SENTIMENT INDICATORS
   - Bull/Bear ratio
   - Risk appetite
   - Recession expectations
"""
    },

    'pimco_outlook': {
        'name': 'PIMCO Cyclical Outlook',
        'publisher': 'PIMCO',
        'frequency': 'quarterly',
        'focus': 'Fixed income and macro outlook',
        'key_sections': [
            'economic_outlook',
            'inflation_view',
            'rates_forecast',
            'credit_view',
            'duration_recommendation',
            'regional_views'
        ],
        'extraction_prompt': """
Extrae la informacion clave de este PIMCO Cyclical Outlook:

1. ECONOMIC OUTLOOK
   - View sobre crecimiento global
   - Recession probability
   - Ciclo economico actual

2. INFLATION VIEW
   - Expectativas de inflacion
   - Transitory vs persistent
   - Implicaciones para TIPS

3. RATES FORECAST
   - Donde ven las tasas en 6-12 meses
   - Fed path esperado
   - Curve shape

4. CREDIT VIEW
   - IG vs HY preference
   - Sectores favoritos en credit
   - Default expectations

5. DURATION RECOMMENDATION
   - Corta/Neutral/Larga
   - Donde en la curva

6. REGIONAL VIEWS
   - US vs Europe vs EM
   - Currency views
"""
    },

    'generic': {
        'name': 'Generic Research Report',
        'publisher': 'Unknown',
        'frequency': 'variable',
        'focus': 'General financial research',
        'key_sections': [
            'main_thesis',
            'key_data',
            'recommendations',
            'risks'
        ],
        'extraction_prompt': """
Extrae la informacion clave de este reporte de research financiero:

1. TITULO Y FUENTE
   - Nombre del reporte
   - Quien lo publica
   - Fecha

2. TESIS PRINCIPAL
   - Cual es el argumento central
   - Datos que lo sustentan

3. DATOS CLAVE
   - Numeros importantes mencionados
   - Graficos o tablas relevantes

4. RECOMENDACIONES
   - Que sugiere hacer
   - Asset classes afectadas

5. RIESGOS
   - Que podria invalidar la tesis
   - Escenarios alternativos

6. RELEVANCIA PARA PORTFOLIO
   - Como afecta esto la asset allocation
   - Implicaciones tacticas
"""
    }
}


class ResearchCollector:
    """
    Collector de Research Institucional.

    Procesa PDFs de research de Wall Street y los estructura
    en JSON para consumo del AI Council.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        verbose: bool = True,
        research_folder: Optional[str] = None
    ):
        """
        Inicializa el collector.

        Args:
            api_key: Anthropic API key. Si None, busca en env.
            model: Modelo de Claude a usar
            verbose: Si True, imprime progreso
            research_folder: Carpeta donde buscar PDFs
        """
        if not HAS_PDFPLUMBER:
            raise ImportError("pdfplumber required. Install with: pip install pdfplumber")

        if not HAS_ANTHROPIC:
            raise ImportError("anthropic required. Install with: pip install anthropic")

        # API Key
        if api_key is None:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key is None:
            try:
                from greybark.config import CLAUDE_API_KEY
                api_key = CLAUDE_API_KEY
            except ImportError:
                pass

        if api_key is None:
            raise ValueError("API key required")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.verbose = verbose
        self.research_folder = research_folder

        # Cache de reportes procesados
        self.processed_reports: List[Dict] = []

    def _print(self, msg: str):
        """Print if verbose."""
        if self.verbose:
            print(msg)

    def extract_text_from_pdf(self, pdf_path: str, max_pages: int = 50) -> str:
        """
        Extrae texto de un PDF.

        Args:
            pdf_path: Ruta al PDF
            max_pages: Maximo de paginas a procesar

        Returns:
            Texto extraido concatenado
        """
        self._print(f"  -> Extracting text from {Path(pdf_path).name}...")

        text_parts = []

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = min(len(pdf.pages), max_pages)

            for i, page in enumerate(pdf.pages[:max_pages]):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"\n--- PAGE {i+1} ---\n{page_text}")

                # Progress
                if self.verbose and (i + 1) % 10 == 0:
                    print(f"     Processed {i+1}/{total_pages} pages")

        full_text = "\n".join(text_parts)
        self._print(f"  -> Extracted {len(full_text):,} characters from {total_pages} pages")

        return full_text

    def detect_source(self, text: str, filename: str) -> str:
        """
        Detecta automaticamente la fuente del research.

        Args:
            text: Texto del PDF
            filename: Nombre del archivo

        Returns:
            Key del source detectado
        """
        text_lower = text.lower()
        filename_lower = filename.lower()

        # Deteccion por contenido
        if 'guide to the markets' in text_lower or 'jpm' in filename_lower:
            return 'jpm_guide'
        elif 'top of mind' in text_lower or 'goldman' in text_lower:
            return 'gs_top_of_mind'
        elif 'fund manager survey' in text_lower or 'fms' in filename_lower:
            return 'bofa_fms'
        elif 'pimco' in text_lower or 'cyclical outlook' in text_lower:
            return 'pimco_outlook'
        else:
            return 'generic'

    def structure_with_llm(
        self,
        text: str,
        source_key: str,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Usa Claude para estructurar el texto en JSON.

        Args:
            text: Texto del PDF
            source_key: Key del source en RESEARCH_SOURCES
            custom_prompt: Prompt personalizado (opcional)

        Returns:
            Dict estructurado con la informacion extraida
        """
        source_config = RESEARCH_SOURCES.get(source_key, RESEARCH_SOURCES['generic'])

        extraction_prompt = custom_prompt or source_config['extraction_prompt']

        # Truncar texto si es muy largo (Claude tiene limite de contexto)
        max_chars = 100000  # ~25k tokens aproximadamente
        if len(text) > max_chars:
            self._print(f"  -> Truncating text from {len(text):,} to {max_chars:,} chars")
            text = text[:max_chars] + "\n\n[... TRUNCATED ...]"

        prompt = f"""
Eres un analista financiero senior. Tu trabajo es extraer y estructurar
la informacion clave de reportes de research institucional.

## TEXTO DEL REPORTE
```
{text}
```

## INSTRUCCIONES
{extraction_prompt}

## FORMATO DE RESPUESTA
Responde SOLO con un JSON valido (sin markdown code blocks) con la siguiente estructura:
{{
    "source": "{source_config['name']}",
    "publisher": "{source_config['publisher']}",
    "extracted_date": "fecha del reporte si la encuentras",
    "processed_date": "{datetime.now().isoformat()}",
    "summary": "resumen ejecutivo en 2-3 oraciones",
    "key_data": {{
        // datos numericos importantes
    }},
    "main_thesis": "tesis principal del reporte",
    "recommendations": [
        // lista de recomendaciones
    ],
    "risks": [
        // lista de riesgos mencionados
    ],
    "market_implications": {{
        "equities": "implicacion para acciones",
        "fixed_income": "implicacion para bonos",
        "currencies": "implicacion para divisas",
        "commodities": "implicacion para commodities"
    }},
    "sections": {{
        // secciones especificas segun el tipo de reporte
    }},
    "relevance_score": 0-100,  // que tan relevante es para decisiones de inversion
    "confidence_in_extraction": 0-100  // que tan seguro estas de la extraccion
}}
"""

        self._print(f"  -> Structuring with Claude ({self.model})...")

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # Intentar parsear JSON
        try:
            # Limpiar posibles markdown code blocks
            clean_text = response_text.strip()
            if clean_text.startswith('```'):
                clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
                clean_text = re.sub(r'\s*```$', '', clean_text)

            result = json.loads(clean_text)
            result['parse_success'] = True

        except json.JSONDecodeError as e:
            self._print(f"  -> WARNING: JSON parse error: {e}")
            result = {
                'raw_response': response_text,
                'parse_success': False,
                'parse_error': str(e)
            }

        return result

    def process_pdf(
        self,
        pdf_path: str,
        source: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Procesa un PDF completo: extrae texto y estructura con LLM.

        Args:
            pdf_path: Ruta al PDF
            source: Key del source (auto-detecta si None)
            custom_prompt: Prompt personalizado

        Returns:
            Dict con la informacion estructurada
        """
        self._print(f"\n{'='*60}")
        self._print(f"PROCESSING: {Path(pdf_path).name}")
        self._print('='*60)

        # Verificar que existe
        if not os.path.exists(pdf_path):
            return {'error': f'File not found: {pdf_path}'}

        # Extraer texto
        text = self.extract_text_from_pdf(pdf_path)

        if not text or len(text) < 100:
            return {'error': 'Could not extract meaningful text from PDF'}

        # Detectar fuente
        if source is None:
            source = self.detect_source(text, Path(pdf_path).name)
            self._print(f"  -> Auto-detected source: {source}")

        # Estructurar con LLM
        result = self.structure_with_llm(text, source, custom_prompt)

        # Agregar metadata
        result['file_path'] = str(pdf_path)
        result['file_name'] = Path(pdf_path).name
        result['source_key'] = source
        result['text_length'] = len(text)

        # Guardar en cache
        self.processed_reports.append(result)

        self._print(f"  -> Processing complete. Relevance: {result.get('relevance_score', 'N/A')}")

        return result

    def process_folder(
        self,
        folder_path: Optional[str] = None,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Procesa todos los PDFs en una carpeta.

        Args:
            folder_path: Carpeta con PDFs (usa self.research_folder si None)
            recursive: Si True, busca en subcarpetas

        Returns:
            Lista de resultados
        """
        folder = folder_path or self.research_folder

        if folder is None:
            raise ValueError("No folder specified")

        folder = Path(folder)

        if not folder.exists():
            raise ValueError(f"Folder not found: {folder}")

        # Encontrar PDFs
        if recursive:
            pdf_files = list(folder.rglob('*.pdf'))
        else:
            pdf_files = list(folder.glob('*.pdf'))

        self._print(f"\nFound {len(pdf_files)} PDF files in {folder}")

        results = []
        for pdf_path in pdf_files:
            result = self.process_pdf(str(pdf_path))
            results.append(result)

        return results

    def get_research_digest(self) -> Dict[str, Any]:
        """
        Genera un digest consolidado de todos los reportes procesados.
        Ideal para alimentar al AI Council.

        Returns:
            Dict con el digest consolidado
        """
        if not self.processed_reports:
            return {
                'status': 'no_reports',
                'message': 'No research reports have been processed yet'
            }

        # Filtrar reportes exitosos
        successful = [r for r in self.processed_reports if r.get('parse_success', False)]

        if not successful:
            return {
                'status': 'no_successful_parses',
                'total_attempted': len(self.processed_reports)
            }

        # Consolidar informacion
        digest = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'reports_processed': len(successful),
                'sources': list(set(r.get('source_key', 'unknown') for r in successful))
            },
            'reports': []
        }

        # Agregar resumen de cada reporte
        for report in successful:
            digest['reports'].append({
                'source': report.get('source', 'Unknown'),
                'file_name': report.get('file_name', 'Unknown'),
                'summary': report.get('summary', ''),
                'main_thesis': report.get('main_thesis', ''),
                'recommendations': report.get('recommendations', []),
                'risks': report.get('risks', []),
                'market_implications': report.get('market_implications', {}),
                'relevance_score': report.get('relevance_score', 0)
            })

        # Consolidar temas comunes
        all_risks = []
        all_recommendations = []

        for report in successful:
            all_risks.extend(report.get('risks', []))
            all_recommendations.extend(report.get('recommendations', []))

        digest['consolidated'] = {
            'common_risks': all_risks[:10],  # Top 10
            'common_recommendations': all_recommendations[:10]
        }

        return digest

    def save_digest(self, filepath: str = 'research_digest.json') -> str:
        """
        Guarda el digest como JSON.

        Args:
            filepath: Ruta donde guardar

        Returns:
            Ruta del archivo guardado
        """
        digest = self.get_research_digest()

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(digest, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"\n[OK] Research digest saved to {filepath}")

        return filepath


# =============================================================================
# INTEGRATION WITH UNIFIED DATA PACKET
# =============================================================================

def get_research_data_for_packet(
    research_folder: Optional[str] = None,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Funcion helper para integrar con UnifiedDataPacketBuilder.

    Args:
        research_folder: Carpeta con PDFs de research
        api_key: Anthropic API key

    Returns:
        Dict con research digest para el data packet
    """
    if research_folder is None:
        # Buscar carpeta por defecto
        default_paths = [
            'research',
            'research_pdfs',
            '../research',
            os.path.expanduser('~/Documents/research')
        ]

        for path in default_paths:
            if os.path.exists(path):
                research_folder = path
                break

    if research_folder is None or not os.path.exists(research_folder):
        return {
            'status': 'no_research_folder',
            'message': 'Create a folder called "research" with PDF files',
            'expected_sources': list(RESEARCH_SOURCES.keys())
        }

    try:
        collector = ResearchCollector(
            api_key=api_key,
            research_folder=research_folder,
            verbose=True
        )

        collector.process_folder()
        return collector.get_research_digest()

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Process research PDFs')
    parser.add_argument('--pdf', help='Single PDF to process')
    parser.add_argument('--folder', help='Folder with PDFs')
    parser.add_argument('--output', default='research_digest.json', help='Output file')
    parser.add_argument('--source', help='Force source type (jpm_guide, gs_top_of_mind, bofa_fms, pimco_outlook)')
    args = parser.parse_args()

    collector = ResearchCollector(verbose=True)

    if args.pdf:
        result = collector.process_pdf(args.pdf, source=args.source)
        print(json.dumps(result, indent=2, default=str))

    elif args.folder:
        collector.process_folder(args.folder)
        collector.save_digest(args.output)

    else:
        print("Usage: python research_collector.py --pdf <file.pdf> OR --folder <folder/>")
        print("\nSupported sources:")
        for key, config in RESEARCH_SOURCES.items():
            print(f"  {key}: {config['name']}")

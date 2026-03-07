# -*- coding: utf-8 -*-
"""
Greybark Research - AI Council Runner
======================================

Orquestador principal del AI Investment Council.
Implementa arquitectura de 3 capas:

CAPA 1 - PANEL HORIZONTAL (5 agentes en paralelo):
    IAS Macro | IAS RV | IAS RF | IAS Riesgo | IAS Geo

CAPA 2 - SÍNTESIS VERTICAL (secuencial):
    CIO (sintetiza) → Contrarian (critica) → Refinador (output final)

CAPA 3 - OUTPUT FINAL:
    Documento estructurado para el cliente

Uso:
    runner = AICouncilRunner()
    result = await runner.run_session(report_type='macro')

    # O sincrónico:
    result = runner.run_session_sync(report_type='macro')
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import traceback

# Agregar paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "02_greybark_library"))

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from council_data_collector import CouncilDataCollector


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DEFAULT_MODEL = "claude-sonnet-4-6"          # Panel (5 agentes)
SYNTHESIS_MODEL = "claude-opus-4-6"          # CIO + Contrarian + Refinador
MAX_TOKENS = 2000
PROMPTS_DIR = Path(__file__).parent / "prompts"


# =============================================================================
# AI COUNCIL RUNNER
# =============================================================================

class AICouncilRunner:
    """
    Ejecuta una sesión completa del AI Investment Council.

    Arquitectura de 3 capas:
    1. Panel horizontal: 5 agentes especializados en paralelo
    2. Síntesis vertical: CIO → Contrarian → Refinador
    3. Output: Documento estructurado
    """

    # Agentes del Panel (Capa 1)
    PANEL_AGENTS = ['macro', 'rv', 'rf', 'riesgo', 'geo']

    # Agentes de Síntesis (Capa 2)
    SYNTHESIS_AGENTS = ['cio', 'contrarian', 'refinador']

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        verbose: bool = True,
        client_prompts: Optional[Dict[str, str]] = None,
    ):
        """
        Inicializa el runner.

        Args:
            api_key: API key de Anthropic. Si None, busca en env.
            model: Modelo de Claude a usar
            verbose: Si True, imprime progreso
            client_prompts: Dict con tone, audience, focus, custom_instructions
                para inyectar en los system prompts de los agentes.
        """
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package required. Install: pip install anthropic")

        # Buscar API key (env var > config file > parameter)
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            # Try to get from config file
            try:
                from greybark.config import CLAUDE_API_KEY
                self.api_key = CLAUDE_API_KEY
            except ImportError:
                pass
        if not self.api_key:
            raise ValueError("API key required. Set ANTHROPIC_API_KEY env var.")

        self.model = model
        self.verbose = verbose
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.data_collector = CouncilDataCollector(verbose=verbose)

        # Session state
        self.session_log = []
        self.panel_outputs = {}
        self.synthesis_outputs = {}
        self.refinador_max_tokens = MAX_TOKENS

        # Cargar prompts
        self.prompts = self._load_prompts()

        # Inyectar personalizaciones del cliente en system prompts
        self.client_prompts = client_prompts or {}
        if self.client_prompts:
            self._inject_client_prompts()

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _load_prompts(self) -> Dict[str, str]:
        """Carga los system prompts desde archivos .txt"""
        prompts = {}
        prompt_files = {
            'macro': 'ias_macro.txt',
            'rv': 'ias_rv.txt',
            'rf': 'ias_rf.txt',
            'riesgo': 'ias_riesgo.txt',
            'geo': 'ias_geo.txt',
            'cio': 'ias_cio.txt',
            'contrarian': 'ias_contrarian.txt',
            'refinador': 'refinador.txt'
        }

        for agent, filename in prompt_files.items():
            filepath = PROMPTS_DIR / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    prompts[agent] = f.read()
            else:
                self._print(f"[WARN] Prompt no encontrado: {filepath}")
                prompts[agent] = f"Eres el agente {agent} del AI Council."

        return prompts

    def _inject_client_prompts(self):
        """Append client-specific instructions to all agent system prompts."""
        additions = []
        if self.client_prompts.get('tone'):
            additions.append(f"Tono de escritura: {self.client_prompts['tone']}")
        if self.client_prompts.get('audience'):
            additions.append(f"Audiencia objetivo: {self.client_prompts['audience']}")
        if self.client_prompts.get('focus'):
            additions.append(f"Foco tematico: {self.client_prompts['focus']}")
        if self.client_prompts.get('custom_instructions'):
            additions.append(f"Instrucciones adicionales: {self.client_prompts['custom_instructions']}")

        if not additions:
            return

        suffix = "\n\n--- Configuracion del cliente ---\n" + "\n".join(additions)
        for agent in list(self.prompts.keys()):
            self.prompts[agent] += suffix
        self._print(f"[OK] Client prompts inyectados en {len(self.prompts)} agentes")

    # =========================================================================
    # LLAMADAS A LLM
    # =========================================================================

    async def _call_llm_async(self, system_prompt: str, user_prompt: str,
                              model: str = None, max_tokens: int = None) -> str:
        """Llama a Claude API de forma asíncrona."""
        use_model = model or self.model
        use_tokens = max_tokens or MAX_TOKENS
        try:
            # Anthropic SDK es sincrónico, lo envolvemos
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.messages.create(
                    model=use_model,
                    max_tokens=use_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )
            )
            return response.content[0].text
        except Exception as e:
            self._print(f"[ERR] LLM call failed: {e}")
            return f"Error: {str(e)}"

    def _call_llm_sync(self, system_prompt: str, user_prompt: str,
                       model: str = None) -> str:
        """Llama a Claude API de forma sincrónica."""
        use_model = model or self.model
        try:
            response = self.client.messages.create(
                model=use_model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            return response.content[0].text
        except Exception as e:
            self._print(f"[ERR] LLM call failed: {e}")
            return f"Error: {str(e)}"

    # =========================================================================
    # CAPA 1: PANEL HORIZONTAL
    # =========================================================================

    async def _run_panel_async(self, council_input: Dict) -> Dict[str, str]:
        """Ejecuta los 5 agentes del panel en paralelo."""
        self._print("\n" + "=" * 60)
        self._print("CAPA 1: PANEL HORIZONTAL (5 agentes en paralelo)")
        self._print("=" * 60)

        tasks = []
        for agent in self.PANEL_AGENTS:
            task = self._run_panel_agent_async(agent, council_input)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        panel_outputs = {}
        for agent, result in zip(self.PANEL_AGENTS, results):
            panel_outputs[agent] = result

        return panel_outputs

    async def _run_panel_agent_async(self, agent: str, council_input: Dict) -> str:
        """Ejecuta un agente del panel."""
        self._print(f"  -> IAS {agent.upper()} analizando...")

        system_prompt = self.prompts.get(agent, '')
        user_prompt = self._build_panel_user_prompt(agent, council_input)

        response = await self._call_llm_async(system_prompt, user_prompt)

        self._print(f"  <- IAS {agent.upper()} completado ({len(response)} chars)")
        return response

    def _build_panel_user_prompt(self, agent: str, council_input: Dict) -> str:
        """Construye el user prompt para un agente del panel."""
        agent_data = dict(council_input.get('agent_data', {}).get(agent, {}))
        daily_context = council_input.get('daily_context', '')
        intelligence_briefing = council_input.get('intelligence_briefing', '')
        user_directives = council_input.get('user_directives', '')
        external_research = council_input.get('external_research', '')

        # Usar intelligence briefing (~2K) si existe, sino daily_context truncado (~10K)
        context_for_agents = intelligence_briefing if intelligence_briefing else daily_context[:10000]

        # Extraer bloomberg_context ANTES de serializar a JSON
        bloomberg_context = agent_data.pop('bloomberg_context', '')

        # Build structured data inventory (DATOS DISPONIBLES / NO DISPONIBLES)
        data_inventory = self._build_data_inventory(agent, agent_data)

        # Also keep a compact JSON of complex structures the inventory can't fully show
        data_json = json.dumps(agent_data, indent=2, ensure_ascii=False, default=str)
        if len(data_json) > 6000:
            data_json = data_json[:6000] + "\n... [truncado]"

        prompt = f"""
Aquí tienes la información para tu análisis:

{data_inventory}

## DATOS CUANTITATIVOS COMPLETOS (referencia — los datos clave ya están arriba)
```json
{data_json}
```

## INTELLIGENCE BRIEFING (Contexto de Reportes Diarios)
{context_for_agents}
"""

        # Bloomberg: sección dedicada y prominente
        if bloomberg_context:
            prompt += f"""
## DATOS DE BLOOMBERG (Series Históricas de Mercado)
Los siguientes datos provienen directamente de Bloomberg Terminal.
Úsalos para fundamentar tu análisis con datos de mercado reales.

{bloomberg_context}
"""

        # Inyectar research externo si existe
        if external_research:
            prompt += f"""
## RESEARCH EXTERNO (Bancos de Inversión)
{external_research[:3000]}
"""

        # Inyectar analytics modules
        module_outputs = council_input.get('module_outputs', '')
        if module_outputs:
            prompt += f"""
## ANALYTICS MODULES (Señales Cuantitativas)
{module_outputs}
"""

        # Inyectar directivas del usuario — siempre prominente
        if user_directives:
            prompt += f"""
## DIRECTIVAS DEL COMITÉ (IMPORTANTE — priorizar estos temas)
{user_directives}
"""

        prompt += """
## ESTACIONALIDAD
Considera siempre los patrones estacionales de los datos que analizas.
Ejemplos: efecto enero en equity, estacionalidad del CPI (ropa, energía),
window dressing de fin de trimestre, patrón "sell in May", estacionalidad
del cobre (construcción china Q1), ciclo fiscal USA (abril refunds),
efecto base interanual en inflación. Si un dato parece fuerte o débil,
pregúntate si es el patrón estacional o un cambio genuino de tendencia.

## ESTILO DE ESCRITURA — IMPORTANTE
Tu output será procesado por capas superiores para producir un documento
de research profesional. Escribe como un analista senior, no como un
modelo de lenguaje.

Reglas de estilo:
- Sé DIRECTO. "Los breakevens caen" no "Se observa una tendencia
  descendente en los breakevens".
- Sé ESPECÍFICO. Cita el dato. "PCE core en 2,8% con servicios en
  3,6%" es mejor que "la inflación subyacente muestra persistencia".
- Sé CONCISO. No repitas la misma idea con diferentes palabras.
- EVITA adjetivos grandilocuentes: "extraordinario", "dramáticamente",
  "inequívoco", "abrumador", "transformador", "crucial". Si el dato
  es fuerte, preséntalo y deja que hable.
- EVITA frases de relleno: "Es importante señalar que", "Cabe destacar",
  "En este contexto", "Es crucial mencionar", "Vale la pena notar".
  Ve directo al punto.
- EVITA la estructura "por tres vías/razones/factores" seguida de
  enumeración. Desarrolla las ideas con transiciones naturales.
- USA "creemos", "vemos", "nuestra lectura" — primera persona plural.
  NUNCA "se observa", "se identifica", "cabe señalar".

Idioma: español profesional. Términos en inglés SOLO cuando son convención
de mercado (risk-on/off, spread, steepener, flattener, carry, roll-down,
drawdown, VaR, put/call, OW/N/UW, ETF, CDS, TIPS, P/E, forward guidance,
earnings, beat rate). Traduce todo lo demás: "valuaciones", "sobreponderar",
"rendimiento" (no yield), "recorte de tasas", "perspectiva", "impulso",
"amplitud", "cobertura".

## TU TAREA
Proporciona tu análisis siguiendo tu metodología y formato de output especificado.
Sé directo, específico, y cita datos cuando sea posible.
Limita tu respuesta a 400-500 palabras máximo.
"""
        return prompt

    def _build_cio_data_inventory(self, council_input: Dict) -> str:
        """Build a consolidated data inventory for the CIO to cross-check panel claims.

        Includes data from ALL 5 panel agents so CIO can verify panelist numbers.
        """
        try:
            from data_completeness_validator import DataCompletenessValidator
            validator = DataCompletenessValidator(verbose=False)
            agent_data_map = council_input.get('agent_data', {})
            sections = [
                "## DATOS VERIFICADOS DE TODAS LAS FUENTES (para validar citas de panelistas)",
                "Usa esta referencia para verificar que los números citados por los panelistas son correctos.",
                ""
            ]
            for agent_name in ['macro', 'rv', 'rf', 'riesgo', 'geo']:
                data = agent_data_map.get(agent_name, {})
                ac = validator.validate_agent(agent_name, data)
                present = ac.present_fields
                if present:
                    sections.append(f"### {agent_name.upper()}")
                    for fs in present:
                        display = validator._format_value(fs.value, fs.field.unit)
                        sections.append(f"- {fs.field.label}: {display} [{fs.field.source}]")
                    sections.append("")
            return "\n".join(sections)
        except Exception as e:
            self._print(f"  [WARN] CIO data inventory fallback: {e}")
            return ""

    def _build_data_inventory(self, agent: str, agent_data: Dict) -> str:
        """Build structured DATOS DISPONIBLES / NO DISPONIBLES inventory for an agent.

        Uses DataCompletenessValidator to check manifest fields against actual data
        and formats as a human-readable inventory for the agent prompt.
        """
        try:
            from data_completeness_validator import DataCompletenessValidator
            validator = DataCompletenessValidator(verbose=False)
            return validator.build_data_inventory(agent, agent_data)
        except Exception as e:
            self._print(f"  [WARN] Data inventory fallback for {agent}: {e}")
            # Fallback: simple list of top-level keys with values
            lines = ["## DATOS DISPONIBLES"]
            for k, v in agent_data.items():
                if isinstance(v, (int, float)):
                    lines.append(f"- {k}: {v}")
                elif isinstance(v, str) and len(v) < 100:
                    lines.append(f"- {k}: {v}")
                elif isinstance(v, dict) and 'error' not in v:
                    lines.append(f"- {k}: <disponible>")
            lines.append("\n## REGLA ESTRICTA DE DATOS")
            lines.append("Solo cita numeros que aparecen en tu input. No inventes datos.")
            return "\n".join(lines)

    # =========================================================================
    # CAPA 2: SÍNTESIS VERTICAL
    # =========================================================================

    async def _run_synthesis_async(
        self,
        panel_outputs: Dict[str, str],
        council_input: Dict
    ) -> Dict[str, str]:
        """Ejecuta la síntesis vertical: CIO → Contrarian → Refinador."""
        self._print("\n" + "=" * 60)
        self._print("CAPA 2: SÍNTESIS VERTICAL (secuencial)")
        self._print("=" * 60)

        synthesis_outputs = {}

        # Paso 1: CIO sintetiza (Opus 4.6)
        self._print(f"\n  -> IAS CIO sintetizando opiniones del panel... [{SYNTHESIS_MODEL}]")
        cio_prompt = self._build_cio_prompt(panel_outputs, council_input)
        cio_output = await self._call_llm_async(self.prompts['cio'], cio_prompt, model=SYNTHESIS_MODEL)
        synthesis_outputs['cio'] = cio_output
        self._print(f"  <- IAS CIO completado ({len(cio_output)} chars)")

        # Paso 2: Contrarian critica (Opus 4.6)
        self._print(f"\n  -> IAS CONTRARIAN desafiando síntesis... [{SYNTHESIS_MODEL}]")
        contrarian_prompt = self._build_contrarian_prompt(cio_output, panel_outputs)
        contrarian_output = await self._call_llm_async(self.prompts['contrarian'], contrarian_prompt, model=SYNTHESIS_MODEL)
        synthesis_outputs['contrarian'] = contrarian_output
        self._print(f"  <- IAS CONTRARIAN completado ({len(contrarian_output)} chars)")

        # Paso 3: Refinador produce output final (Opus 4.6)
        self._print(f"\n  -> REFINADOR generando output final... [{SYNTHESIS_MODEL}]")
        refinador_prompt = self._build_refinador_prompt(cio_output, contrarian_output, council_input)
        refinador_output = await self._call_llm_async(self.prompts['refinador'], refinador_prompt, model=SYNTHESIS_MODEL, max_tokens=self.refinador_max_tokens)
        synthesis_outputs['refinador'] = refinador_output
        self._print(f"  <- REFINADOR completado ({len(refinador_output)} chars)")

        return synthesis_outputs

    def _build_cio_prompt(
        self,
        panel_outputs: Dict[str, str],
        council_input: Dict
    ) -> str:
        """Construye el prompt para el CIO."""
        opinions = []
        for agent, output in panel_outputs.items():
            opinions.append(f"### Opinión IAS {agent.upper()}\n{output}")

        user_directives = council_input.get('user_directives', '')
        external_research = council_input.get('external_research', '')

        # Build consolidated data inventory for CIO cross-checking
        data_inventory_cio = self._build_cio_data_inventory(council_input)

        prompt = f"""
Aquí tienes las opiniones del panel de especialistas:

{chr(10).join(opinions)}

{data_inventory_cio}
"""

        if external_research:
            prompt += f"""
## RESEARCH EXTERNO (Bancos de Inversión)
Considera estas perspectivas externas en tu síntesis:
{external_research[:4000]}
"""

        # Inyectar analytics modules
        module_outputs = council_input.get('module_outputs', '')
        if module_outputs:
            prompt += f"""
## ANALYTICS MODULES (Señales Cuantitativas)
{module_outputs}
"""

        if user_directives:
            prompt += f"""
## DIRECTIVAS DEL COMITÉ (IMPORTANTE)
El comité solicita foco especial en:
{user_directives}
"""

        prompt += """
## ESTACIONALIDAD
Al sintetizar, verifica si las opiniones del panel consideran estacionalidad.
Si un agente señala un dato como señal sin mencionar el patrón estacional,
cuestiónalo en tu síntesis.

## ESTILO DE ESCRITURA — IMPORTANTE
Tu síntesis será la base del documento final de Greybark Research.
Escribe como un CIO real dictando su lectura de mercado, no como un modelo
de lenguaje resumiendo inputs.

Reglas de estilo:
- Sé DIRECTO. "Los datos macro apuntan a desaceleración" no "Se observa
  una tendencia hacia la desaceleración en los indicadores macro".
- Sé ESPECÍFICO. Cita el dato, no hables de "los datos".
- Sé CONCISO. Cada frase debe ganarse su lugar.
- EVITA adjetivos grandilocuentes: "extraordinario", "dramáticamente",
  "inequívoco", "abrumador". Si algo es importante, el dato habla solo.
- EVITA frases de relleno: "es importante señalar", "cabe destacar",
  "en este contexto", "resulta relevante".
- USA "creemos", "vemos", "nuestra lectura" — primera persona plural.
  NUNCA "se observa", "se identifica", "cabe señalar".

Idioma: español profesional. Términos en inglés SOLO cuando son convención
de mercado (risk-on/off, spread, steepener, flattener, carry, roll-down,
drawdown, VaR, put/call, OW/N/UW, ETF, CDS, TIPS, P/E, forward guidance,
earnings, beat rate). Traduce todo lo demás: "valuaciones", "sobreponderar",
"recorte de tasas", "perspectiva", "cobertura", "amplitud de mercado", etc.

## TU TAREA
Sintetiza estas opiniones y produce tu recomendación preliminar.
Sé claro en consensos vs disensos.
Si hay directivas del comité, asegúrate de abordarlas explícitamente.
Si hay research externo, contrasta las opiniones del panel con las visiones externas.
600-800 palabras máximo.
"""
        return prompt

    def _build_contrarian_prompt(self, cio_output: str, panel_outputs: Dict) -> str:
        """Construye el prompt para el Contrarian."""
        panel_summary = "\n".join([f"- {k}: {v[:200]}..." for k, v in panel_outputs.items()])

        return f"""
<sintesis_cio>
{cio_output}
</sintesis_cio>

<resumen_opiniones_panel>
{panel_summary}
</resumen_opiniones_panel>

## ESTILO DE ESCRITURA — IMPORTANTE
Tu output es interno pero debe ser claro y profesional. Escribe como un
analista senior cuestionando una tesis, no como un modelo listando objeciones.

Reglas de estilo:
- Sé DIRECTO y ESPECÍFICO. Cada cuestionamiento debe apuntar a un dato
  o supuesto concreto.
- EVITA relleno: "es importante considerar", "cabe señalar", "en este contexto".
- EVITA adjetivos grandilocuentes: "dramáticamente", "inequívocamente".
- Cuantifica cuando sea posible. "Las reservas chinas cubren ~80 días" es
  mejor que "las reservas podrían amortiguar el impacto".

Idioma: español profesional. Términos en inglés SOLO cuando son convención
de mercado (risk-on/off, spread, carry, ETF, VaR, CDS, TIPS, P/E, etc.).
Traduce todo lo demás al español.

## TU TAREA
Desafía la síntesis del CIO. Encuentra las fallas. Propón mejoras.
500-600 palabras máximo.
"""

    def _build_refinador_prompt(
        self,
        cio_output: str,
        contrarian_output: str,
        council_input: Dict
    ) -> str:
        """Construye el prompt para el Refinador."""
        user_directives = council_input.get('user_directives', '')
        meta = council_input.get('metadata', {})

        prompt = f"""
<sintesis_cio>
{cio_output}
</sintesis_cio>

<critica_contrarian>
{contrarian_output}
</critica_contrarian>

## METADATA
- Fecha del comité: {datetime.now().strftime('%Y-%m-%d')}
- Tipo de reporte: {meta.get('report_type', 'general')}
- Reportes diarios analizados: {meta.get('daily_reports_count', 0)}
- Temas de inteligencia: {meta.get('intelligence_themes', 0)}
"""

        # Inyectar analytics modules
        module_outputs = council_input.get('module_outputs', '')
        if module_outputs:
            prompt += f"""
## ANALYTICS MODULES (Señales Cuantitativas)
{module_outputs}
"""

        if user_directives:
            prompt += f"""
## DIRECTIVAS DEL COMITÉ (IMPORTANTE)
El documento final DEBE abordar explícitamente:
{user_directives}
"""

        prompt += """
## ESTACIONALIDAD
El documento final debe mencionar factores estacionales relevantes cuando
afecten la interpretación de datos clave (inflación, empleo, earnings, etc.).

## ESTILO DE ESCRITURA — CRÍTICO
El documento final es para clientes. Debe sonar como si lo escribió un
equipo senior de research, no un proceso de múltiples capas ni un modelo
de lenguaje.

Reglas de estilo (además de las de tu system prompt):
- NUNCA expongas el proceso interno. Prohibido: "el comité", "el panel",
  "los especialistas", "el contrarian señala", "se identificó", "fue cuestionado".
- Sé DIRECTO. "Vemos riesgo de..." no "Podría existir riesgo de..."
- Sé SECO. No uses "extraordinario", "dramáticamente", "inequívoco",
  "transformador". Si algo es importante, el dato habla solo.
- Sé CONCISO. Cada frase debe ganarse su lugar.
- NO enumeres todo. El análisis va en PROSA. Bullets solo para datos puntuales.
- EVITA frases de relleno: "es importante señalar", "cabe destacar",
  "en este contexto", "resulta relevante mencionar".
- USA "creemos", "vemos", "nuestra lectura" — primera persona plural.
  NUNCA "se observa", "se identifica", "cabe señalar".

Idioma: español profesional ÍNTEGRO. Términos en inglés SOLO cuando son
convención de mercado sin equivalente práctico:
  Aceptables: risk-on, risk-off, spread, steepener, flattener, carry,
  roll-down, drawdown, VaR, put/call, OW/N/UW, ETF, CDS, TIPS, P/E,
  forward guidance, earnings, beat rate.
  Traducir siempre: "valuaciones" (no valuations), "sobreponderar" (no
  overweight, salvo en tablas), "rendimiento" (no yield, salvo yield curve),
  "recorte" (no cut), "perspectiva" (no outlook), "cobertura" (no hedge),
  "impulso" (no momentum salvo como factor), "amplitud" (no breadth),
  "desempeño" (no performance), "activos" (no assets), "plazo" (no duration
  salvo como concepto RF).

## TU TAREA
Produce el documento final del Comité de Inversiones.
Sigue la estructura EXACTA indicada en tu system prompt.
El output debe ser profesional y listo para el cliente.
"""
        return prompt

    # =========================================================================
    # SESIÓN COMPLETA
    # =========================================================================

    async def run_session(self, report_type: str = 'macro') -> Dict[str, Any]:
        """
        Ejecuta una sesión completa del AI Council (async).

        Args:
            report_type: 'macro' | 'rv' | 'rf' | 'aa'

        Returns:
            Dict con resultados completos
        """
        start_time = datetime.now()

        self._print("\n" + "=" * 70)
        self._print("AI COUNCIL SESSION - GREYBARK RESEARCH")
        self._print("=" * 70)
        self._print(f"Inicio: {start_time.isoformat()}")
        self._print(f"Modelo panel: {self.model}")
        self._print(f"Modelo síntesis: {SYNTHESIS_MODEL}")
        self._print(f"Tipo de reporte: {report_type}")

        # Recopilar datos
        council_input = self.data_collector.prepare_council_input(report_type)

        # Run analytics modules
        self._print("\n  Ejecutando analytics modules...")
        try:
            from modules import run_all_modules
            module_results = run_all_modules(verbose=self.verbose)
            module_texts = []
            for name, out in module_results.items():
                instance = out.get('_instance')
                if instance:
                    module_texts.append(instance.get_council_input())
            council_input['module_outputs'] = "\n\n".join(module_texts)
            self._print(f"  -> {len(module_results)} analytics modules OK")
        except Exception as e:
            self._print(f"  [WARN] Analytics modules failed: {e}")
            council_input['module_outputs'] = ''

        # Preflight gate: NO-GO aborta la sesión
        preflight = council_input.get('preflight', {})
        if preflight.get('overall_verdict') == 'NO_GO':
            self._print("\n[PREFLIGHT] NO-GO: Datos críticos faltantes. Abortando sesión.")
            for issue in preflight.get('issues', []):
                self._print(f"  - {issue}")
            end_time = datetime.now()
            return {
                'aborted': True,
                'preflight': preflight,
                'metadata': {
                    'timestamp': start_time.isoformat(),
                    'duration_seconds': (end_time - start_time).total_seconds(),
                    'model': self.model,
                    'report_type': report_type,
                    'abort_reason': 'PREFLIGHT_NO_GO'
                }
            }

        # Capa 1: Panel horizontal
        self.panel_outputs = await self._run_panel_async(council_input)

        # Capa 2: Síntesis vertical
        self.synthesis_outputs = await self._run_synthesis_async(self.panel_outputs, council_input)

        # Compilar resultado
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result = {
            'metadata': {
                'timestamp': start_time.isoformat(),
                'duration_seconds': duration,
                'model_panel': self.model,
                'model_synthesis': SYNTHESIS_MODEL,
                'model': self.model,  # backward compat
                'report_type': report_type
            },
            'panel_outputs': self.panel_outputs,
            'cio_synthesis': self.synthesis_outputs.get('cio', ''),
            'contrarian_critique': self.synthesis_outputs.get('contrarian', ''),
            'final_recommendation': self.synthesis_outputs.get('refinador', ''),
            'preflight': council_input.get('preflight', {}),
            'council_input_summary': {
                'quantitative_modules': list(council_input.get('quantitative', {}).keys()),
                'daily_reports_count': council_input.get('metadata', {}).get('daily_reports_count', 0)
            }
        }

        self._print("\n" + "=" * 70)
        self._print("SESSION COMPLETE")
        self._print("=" * 70)
        self._print(f"Duración: {duration:.1f} segundos")
        self._print(f"Panel outputs: {len(self.panel_outputs)}")
        self._print(f"Final recommendation: {len(result['final_recommendation'])} chars")

        return result

    def run_session_sync(self, report_type: str = 'macro') -> Dict[str, Any]:
        """Versión sincrónica de run_session."""
        return asyncio.run(self.run_session(report_type))

    def save_result(self, result: Dict, filepath: str = None) -> str:
        """Guarda el resultado en JSON."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = Path(__file__).parent / 'output' / 'council' / f'council_result_{timestamp}.json'

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[Council] Resultado guardado en: {filepath}")
        return str(filepath)


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI para ejecutar el AI Council."""
    import argparse

    parser = argparse.ArgumentParser(description='AI Council Runner')
    parser.add_argument('--type', '-t', default='macro',
                       choices=['macro', 'rv', 'rf', 'aa'],
                       help='Tipo de reporte')
    parser.add_argument('--dry-run', action='store_true',
                       help='Solo prepara datos, no llama a la API')
    parser.add_argument('--output', '-o', help='Archivo de salida')

    args = parser.parse_args()

    if args.dry_run:
        print("=" * 60)
        print("AI COUNCIL - DRY RUN")
        print("=" * 60)

        collector = CouncilDataCollector(verbose=True)
        council_input = collector.prepare_council_input(args.type)

        print("\n--- Datos recopilados ---")
        print(f"Módulos cuantitativos: {list(council_input.get('quantitative', {}).keys())}")
        print(f"Reportes diarios: {council_input['metadata'].get('daily_reports_count', 0)}")
        print(f"Preflight: {council_input.get('preflight', {}).get('overall_verdict', 'N/A')}")

        # Mostrar prompts que se usarían
        print("\n--- Prompts cargados ---")
        runner = AICouncilRunner.__new__(AICouncilRunner)
        runner.verbose = True
        runner._print = lambda x: print(x)
        prompts = runner._load_prompts()
        for agent, prompt in prompts.items():
            print(f"  {agent}: {len(prompt)} chars")

        print("\n[DRY RUN] No se llamó a la API de Anthropic")
        return

    # Ejecución real
    try:
        runner = AICouncilRunner(verbose=True)
        result = runner.run_session_sync(report_type=args.type)

        if args.output:
            runner.save_result(result, args.output)
        else:
            runner.save_result(result)

        # Mostrar resumen
        print("\n" + "=" * 60)
        print("FINAL RECOMMENDATION PREVIEW")
        print("=" * 60)
        print(result['final_recommendation'][:2000])

    except Exception as e:
        print(f"\n[ERROR] {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

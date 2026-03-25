"""
DEPRECATED: Legacy "FOMC In Silico" deliberation architecture.
The production system uses ai_council_runner.py with a 3-layer process
(Panel → CIO+Contrarian → Refinador) and prompts from prompts/*.txt.
This file is retained for reference only. Do NOT modify prompts here.

Greybark Research - AI Council Committee Session
=================================================

Motor de deliberación del AI Council.
Implementa el proceso de 5 rondas del paper "FOMC In Silico":

1. Opinion Formation: Cada agente forma su opinión inicial
2. Presentations: Cada agente presenta su visión al comité
3. Cross-Critique: Agentes critican las posiciones de otros
4. Refinement: Agentes refinan sus posiciones basado en críticas
5. CIO Synthesis: El CIO sintetiza y propone allocation final
6. Voting: Votación final con tracking de disenso

Uso:
    from greybark.ai_council import AICouncilSession
    
    council = AICouncilSession(api_key='your-claude-api-key')
    result = council.run_full_session()
    
    # Ver resultado
    print(result['final_result']['final_allocation'])
    print(result['final_result']['dissents'])
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import os

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from ..agents.personas import (
    AGENT_PERSONAS, 
    CIO_PERSONA, 
    get_agent_system_prompt,
    get_all_agent_keys,
    get_agent_data_focus
)
from ..data_integration.unified_data_packet import UnifiedDataPacketBuilder


class AICouncilSession:
    """
    Ejecuta una sesión completa del AI Council.
    
    Attributes:
        client: Cliente de Anthropic
        model: Modelo a usar (default: claude-sonnet-4-20250514)
        data_builder: Builder del data packet
        session_log: Log de toda la sesión
        agent_opinions: Opiniones de cada agente
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        verbose: bool = True
    ):
        """
        Inicializa la sesión.
        
        Args:
            api_key: API key de Anthropic. Si None, busca en env o config.
            model: Modelo de Claude a usar
            verbose: Si True, imprime progreso
        """
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        
        # Buscar API key
        if api_key is None:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key is None:
            try:
                from greybark.config import CLAUDE_API_KEY
                api_key = CLAUDE_API_KEY
            except ImportError:
                pass
        
        if api_key is None:
            raise ValueError(
                "API key required. Provide api_key parameter, "
                "set ANTHROPIC_API_KEY env var, or add CLAUDE_API_KEY to greybark/config.py"
            )
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.verbose = verbose
        self.data_builder = UnifiedDataPacketBuilder(verbose=verbose)
        
        # Session state
        self.session_log = []
        self.agent_opinions = {}
        self.data_packet = None
    
    def run_full_session(self) -> Dict[str, Any]:
        """
        Ejecuta sesión completa de 5 rondas.
        
        Returns:
            Dict con:
                - timestamp
                - data_packet_summary
                - initial_opinions
                - presentations
                - critiques
                - refined_opinions
                - cio_proposal
                - final_result
                - session_log
        """
        start_time = datetime.now()
        
        self._print_header("AI COUNCIL SESSION - GREYBARK RESEARCH")
        self._print(f"Started: {start_time.isoformat()}")
        self._print(f"Model: {self.model}")
        
        # =====================================================================
        # FASE 1: Construir Data Packet
        # =====================================================================
        self._print_header("FASE 1: Building Data Packet", char="-")
        self.data_packet = self.data_builder.build_packet()
        
        # =====================================================================
        # FASE 2: Opinion Formation
        # =====================================================================
        self._print_header("FASE 2: Individual Opinion Formation", char="-")
        initial_opinions = self._round1_opinion_formation()
        
        # =====================================================================
        # FASE 3a: Presentations
        # =====================================================================
        self._print_header("FASE 3a: Presentations", char="-")
        presentations = self._round2_presentations(initial_opinions)
        
        # =====================================================================
        # FASE 3b: Cross-Critique
        # =====================================================================
        self._print_header("FASE 3b: Cross-Critique", char="-")
        critiques = self._round3_cross_critique(presentations)
        
        # =====================================================================
        # FASE 3c: Refinement
        # =====================================================================
        self._print_header("FASE 3c: Opinion Refinement", char="-")
        refined_opinions = self._round4_refinement(initial_opinions, critiques)
        
        # =====================================================================
        # FASE 4: CIO Synthesis
        # =====================================================================
        self._print_header("FASE 4: CIO Synthesis", char="-")
        cio_proposal = self._round5_cio_synthesis(refined_opinions)
        
        # =====================================================================
        # FASE 5: Voting
        # =====================================================================
        self._print_header("FASE 5: Final Vote", char="-")
        final_result = self._round6_voting(cio_proposal, refined_opinions)
        
        # =====================================================================
        # Compilar resultado
        # =====================================================================
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = {
            'metadata': {
                'timestamp': start_time.isoformat(),
                'duration_seconds': duration,
                'model': self.model
            },
            'data_packet_summary': self._summarize_packet(),
            'initial_opinions': initial_opinions,
            'presentations': presentations,
            'critiques': critiques,
            'refined_opinions': refined_opinions,
            'cio_proposal': cio_proposal,
            'final_result': final_result,
            'session_log': self.session_log
        }
        
        self._print_header("SESSION COMPLETE")
        self._print(f"Duration: {duration:.1f} seconds")
        self._print(f"Final Allocation: {json.dumps(final_result.get('final_allocation', {}), indent=2)}")
        self._print(f"Conviction: {final_result.get('conviction_score', 'N/A')}%")
        self._print(f"Approval Rate: {final_result.get('approval_rate', 0)*100:.1f}%")
        self._print(f"Dissents: {len(final_result.get('dissents', []))}")
        
        return result
    
    # =========================================================================
    # ROUND 1: Opinion Formation
    # =========================================================================
    
    def _round1_opinion_formation(self) -> Dict[str, Any]:
        """
        Cada agente forma su opinión inicial basada en el data packet.
        """
        opinions = {}
        
        for agent_key in get_all_agent_keys():
            persona = AGENT_PERSONAS[agent_key]
            self._print(f"  -> {persona['name']} forming opinion...")
            
            # Filtrar data packet para este agente
            relevant_data = self._filter_data_for_agent(agent_key)
            
            # Construir prompt
            system_prompt = get_agent_system_prompt(agent_key)
            user_prompt = self._build_opinion_user_prompt(persona, relevant_data)
            
            # Llamar LLM
            response = self._call_llm(system_prompt, user_prompt)
            
            # Parsear respuesta
            opinion = self._parse_json_response(response)
            
            opinions[agent_key] = {
                'agent_name': persona['name'],
                'agent_title': persona['title'],
                'opinion': opinion,
                'timestamp': datetime.now().isoformat()
            }
            
            self._log_event('opinion_formation', agent_key, opinion)
        
        return opinions
    
    def _build_opinion_user_prompt(self, persona: Dict, data: Dict) -> str:
        """Construye el user prompt para formación de opinión."""
        return f"""
Aquí tienes los datos actuales del mercado para tu análisis:

## DATOS
```json
{json.dumps(data, indent=2, default=str)[:12000]}
```

## TU TAREA
Analiza los datos desde tu perspectiva como {persona['title']}.
Genera tu recomendación siguiendo el formato especificado.

Sé directo, específico, y cita datos cuando sea posible.
Responde SOLO con un JSON válido, sin texto adicional.
        """.strip()
    
    # =========================================================================
    # ROUND 2: Presentations
    # =========================================================================
    
    def _round2_presentations(self, opinions: Dict) -> Dict[str, Any]:
        """
        Cada agente presenta su visión al comité.
        """
        presentations = {}
        
        for agent_key, opinion_data in opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            self._print(f"  -> {persona['name']} presenting...")
            
            prompt = f"""
Estás en la reunión del comité de inversión de Greybark Research.
Tu opinión inicial es:

```json
{json.dumps(opinion_data['opinion'], indent=2, default=str)}
```

Presenta tu análisis al comité en 2-3 párrafos:
1. Tu visión principal del mercado desde tu área de expertise
2. Tu recomendación clave y por qué
3. Los riesgos que más te preocupan

Habla en primera persona, como si estuvieras en la reunión.
Sé directo y convincente. No uses formato JSON.
            """.strip()
            
            system = f"Eres {persona['name']}, {persona['title']}. {persona['philosophy'][:200]}"
            presentation = self._call_llm(system, prompt)
            
            presentations[agent_key] = {
                'agent_name': persona['name'],
                'presentation': presentation
            }
            
            self._log_event('presentation', agent_key, presentation)
        
        return presentations
    
    # =========================================================================
    # ROUND 3: Cross-Critique
    # =========================================================================
    
    def _round3_cross_critique(self, presentations: Dict) -> Dict[str, Any]:
        """
        Agentes critican las posiciones de otros.
        """
        critiques = {}
        
        for agent_key in get_all_agent_keys():
            persona = AGENT_PERSONAS[agent_key]
            self._print(f"  -> {persona['name']} critiquing others...")
            
            # Formatear presentaciones de otros
            other_presentations = self._format_other_presentations(agent_key, presentations)
            
            prompt = f"""
Has escuchado las presentaciones de tus colegas:

{other_presentations}

Desde tu expertise como {persona['title']}:

1. ¿Qué riesgo están SUBESTIMANDO tus colegas?
2. ¿Qué oportunidad están IGNORANDO?
3. ¿Dónde crees que su análisis está SESGADO?

Sé específico y constructivo pero directo. 
Menciona a cada colega por nombre cuando critiques.
2-3 párrafos máximo.
            """.strip()
            
            system = f"Eres {persona['name']}, {persona['title']}. Tu rol es identificar blind spots en los análisis de otros."
            critique = self._call_llm(system, prompt)
            
            critiques[agent_key] = {
                'agent_name': persona['name'],
                'critique': critique
            }
            
            self._log_event('critique', agent_key, critique)
        
        return critiques
    
    # =========================================================================
    # ROUND 4: Refinement
    # =========================================================================
    
    def _round4_refinement(self, initial_opinions: Dict, critiques: Dict) -> Dict[str, Any]:
        """
        Agentes refinan sus posiciones después de las críticas.
        Implementa "Bayesian updating" del paper FOMC.
        """
        refined = {}
        
        for agent_key, opinion_data in initial_opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            self._print(f"  -> {persona['name']} refining opinion...")
            
            # Obtener críticas recibidas
            received_critiques = self._get_critiques_about_agent(agent_key, critiques)
            
            prompt = f"""
Tu posición inicial era:

```json
{json.dumps(opinion_data['opinion'], indent=2, default=str)}
```

Has recibido estas críticas de tus colegas:

{received_critiques}

Considerando las críticas:
1. ¿Cambias tu posición? ¿Por qué sí o por qué no?
2. ¿Tu nivel de convicción sube o baja?
3. ¿Qué ajustes específicos harías a tu recomendación?

Responde en JSON:
{{
    "position_changed": true/false,
    "change_description": "descripción del cambio si aplica",
    "new_conviction": "high/medium/low",
    "refined_recommendation": {{ ... }},
    "response_to_critiques": "tu respuesta a las críticas"
}}
            """.strip()
            
            system = get_agent_system_prompt(agent_key)
            response = self._call_llm(system, prompt)
            
            refined_opinion = self._parse_json_response(response)
            
            refined[agent_key] = {
                'agent_name': persona['name'],
                'original_opinion': opinion_data['opinion'],
                'refined_opinion': refined_opinion
            }
            
            self._log_event('refinement', agent_key, refined_opinion)
        
        return refined
    
    # =========================================================================
    # ROUND 5: CIO Synthesis
    # =========================================================================
    
    def _round5_cio_synthesis(self, refined_opinions: Dict) -> Dict[str, Any]:
        """
        El CIO sintetiza las visiones y propone allocation final.
        """
        self._print("  -> CIO synthesizing committee views...")
        
        # Formatear opiniones para el CIO
        opinions_summary = self._format_opinions_for_cio(refined_opinions)
        
        # Incluir régimen actual
        regime_info = json.dumps(
            self.data_packet.get('regime_classification', {}),
            indent=2,
            default=str
        )
        
        prompt = f"""
## POSICIONES DEL COMITÉ

{opinions_summary}

## RÉGIMEN ECONÓMICO ACTUAL

```json
{regime_info}
```

## TU TAREA

Como Chief Investment Strategist, sintetiza las visiones del comité:

1. Identifica los puntos de CONSENSO
2. Documenta los DISENSOS importantes (no los escondas)
3. Propón una ALLOCATION FINAL que balancee las perspectivas
4. Explica tu rationale

Responde en JSON:
{{
    "consensus_points": ["punto 1", "punto 2", "punto 3"],
    "dissenting_views": [
        {{"agent": "nombre", "view": "su visión", "merit": "por qué tiene mérito"}}
    ],
    "final_allocation": {{
        "us_equity": 0-50,
        "international_equity_developed": 0-30,
        "emerging_markets": 0-20,
        "fixed_income_government": 0-40,
        "fixed_income_credit": 0-20,
        "cash": 0-20,
        "alternatives": 0-15
    }},
    "conviction_score": 0-100,
    "key_risks": ["riesgo 1", "riesgo 2", "riesgo 3"],
    "rebalancing_triggers": ["trigger 1", "trigger 2"],
    "rationale": "explicación de 2-3 párrafos"
}}

IMPORTANTE: Las allocations deben sumar 100.
        """.strip()
        
        system = CIO_PERSONA['system_prompt']
        response = self._call_llm(system, prompt)
        
        proposal = self._parse_json_response(response)
        # Validar que sume 100 si no hay error
        if 'final_allocation' in proposal and not proposal.get('parse_error'):
            total = sum(proposal['final_allocation'].values())
            if abs(total - 100) > 1:
                # Normalizar
                for k in proposal['final_allocation']:
                    proposal['final_allocation'][k] = round(
                        proposal['final_allocation'][k] * 100 / total, 1
                    )
        
        self._log_event('cio_synthesis', 'cio', proposal)
        
        return proposal
    
    # =========================================================================
    # ROUND 6: Voting
    # =========================================================================
    
    def _round6_voting(self, cio_proposal: Dict, refined_opinions: Dict) -> Dict[str, Any]:
        """
        Votación final del comité con tracking de disenso.
        """
        votes = {}
        dissents = []
        
        for agent_key, opinion_data in refined_opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            self._print(f"  -> {persona['name']} voting...")
            
            prompt = f"""
El CIO ha propuesto esta allocation final:

```json
{json.dumps(cio_proposal.get('final_allocation', {}), indent=2)}
```

Rationale del CIO:
{cio_proposal.get('rationale', 'No disponible')}

Tu posición refinada era:
```json
{json.dumps(opinion_data.get('refined_opinion', {}), indent=2, default=str)}
```

VOTA:
- AGREE: Apoyas la propuesta
- DISAGREE: Tienes una objeción material importante
- ABSTAIN: No tienes opinión fuerte

Responde en JSON:
{{
    "vote": "AGREE/DISAGREE/ABSTAIN",
    "reason": "razón breve de tu voto",
    "dissent_severity": "minor/moderate/major" (solo si DISAGREE),
    "suggested_amendment": "tu sugerencia" (solo si DISAGREE)
}}
            """.strip()
            
            system = f"Eres {persona['name']}. Vota honestamente basado en tu análisis."
            response = self._call_llm(system, prompt)
            
            vote = self._parse_json_response(response)
            if vote.get('parse_error'):
                vote = {'vote': 'ABSTAIN', 'reason': 'Parse error', 'raw': response}
            
            votes[agent_key] = {
                'agent_name': persona['name'],
                'vote': vote
            }
            
            if vote.get('vote') == 'DISAGREE':
                dissents.append({
                    'agent': persona['name'],
                    'reason': vote.get('reason', ''),
                    'severity': vote.get('dissent_severity', 'moderate'),
                    'amendment': vote.get('suggested_amendment', '')
                })
            
            self._log_event('vote', agent_key, vote)
        
        # Calcular resultado
        vote_counts = {'AGREE': 0, 'DISAGREE': 0, 'ABSTAIN': 0}
        for v in votes.values():
            vote_type = v['vote'].get('vote', 'ABSTAIN')
            vote_counts[vote_type] = vote_counts.get(vote_type, 0) + 1
        
        total_votes = len(votes)
        approval_rate = vote_counts['AGREE'] / total_votes if total_votes > 0 else 0
        
        return {
            'final_allocation': cio_proposal.get('final_allocation', {}),
            'conviction_score': cio_proposal.get('conviction_score', 0),
            'rationale': cio_proposal.get('rationale', ''),
            'consensus_points': cio_proposal.get('consensus_points', []),
            'key_risks': cio_proposal.get('key_risks', []),
            'rebalancing_triggers': cio_proposal.get('rebalancing_triggers', []),
            'vote_counts': vote_counts,
            'approval_rate': approval_rate,
            'votes': votes,
            'dissents': dissents,
            'passed': approval_rate >= 0.5
        }
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Hace una llamada al LLM.
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=system_prompt
        )
        return message.content[0].text

    def _extract_json(self, response: str) -> str:
        """
        Extrae JSON de una respuesta que puede estar envuelta en markdown code blocks.
        """
        import re
        # Try to extract JSON from markdown code block
        pattern = r'```(?:json)?\s*([\s\S]*?)```'
        match = re.search(pattern, response)
        if match:
            return match.group(1).strip()
        return response.strip()

    def _parse_json_response(self, response: str) -> dict:
        """
        Parsea una respuesta JSON, manejando markdown code blocks.
        """
        try:
            # First try direct parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Try extracting from markdown
            extracted = self._extract_json(response)
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                return {'raw_response': response, 'parse_error': True}
    
    def _filter_data_for_agent(self, agent_key: str) -> Dict:
        """
        Filtra el data packet para incluir solo lo relevante para un agente.
        """
        if self.data_packet is None:
            return {}
        
        data_focus = get_agent_data_focus(agent_key)
        filtered = {'metadata': self.data_packet.get('metadata', {})}
        
        for key in data_focus:
            if key in self.data_packet:
                filtered[key] = self.data_packet[key]
        
        return filtered
    
    def _format_other_presentations(self, current_agent: str, presentations: Dict) -> str:
        """
        Formatea las presentaciones de otros agentes.
        """
        lines = []
        for agent_key, data in presentations.items():
            if agent_key != current_agent:
                lines.append(f"### {data['agent_name']}")
                lines.append(data['presentation'])
                lines.append("")
        return "\n".join(lines)
    
    def _get_critiques_about_agent(self, agent_key: str, critiques: Dict) -> str:
        """
        Obtiene críticas relevantes para un agente.
        Por ahora retorna todas las críticas de otros.
        En una implementación más sofisticada, filtraría por menciones.
        """
        agent_name = AGENT_PERSONAS[agent_key]['name']
        lines = []
        
        for other_key, data in critiques.items():
            if other_key != agent_key:
                # Buscar si mencionan a este agente
                critique_text = data['critique']
                if agent_name.split()[-1] in critique_text:  # Busca apellido
                    lines.append(f"**{data['agent_name']}** dice sobre ti:")
                    lines.append(critique_text)
                    lines.append("")
        
        if not lines:
            # Si no hay críticas específicas, incluir todas
            for other_key, data in critiques.items():
                if other_key != agent_key:
                    lines.append(f"**{data['agent_name']}**:")
                    lines.append(data['critique'][:500] + "...")
                    lines.append("")
        
        return "\n".join(lines) if lines else "No se recibieron críticas específicas."
    
    def _format_opinions_for_cio(self, refined_opinions: Dict) -> str:
        """
        Formatea las opiniones refinadas para el CIO.
        """
        lines = []
        for agent_key, data in refined_opinions.items():
            lines.append(f"### {data['agent_name']}")
            
            refined = data.get('refined_opinion', {})
            if isinstance(refined, dict) and 'refined_recommendation' in refined:
                lines.append(f"Cambió posición: {refined.get('position_changed', 'N/A')}")
                lines.append(f"Conviction: {refined.get('new_conviction', 'N/A')}")
                lines.append(f"Recomendación: {json.dumps(refined.get('refined_recommendation', {}), indent=2)}")
            else:
                lines.append(f"Opinión: {json.dumps(refined, indent=2, default=str)[:500]}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _summarize_packet(self) -> Dict:
        """
        Resume el data packet para el output.
        """
        if self.data_packet is None:
            return {}
        
        return {
            'timestamp': self.data_packet.get('metadata', {}).get('timestamp'),
            'regime': self.data_packet.get('regime_classification', {}).get('classification'),
            'regime_score': self.data_packet.get('regime_classification', {}).get('score'),
            'modules_used': self.data_packet.get('metadata', {}).get('modules_used', [])
        }
    
    def _log_event(self, phase: str, agent: str, content: Any):
        """
        Agrega un evento al log de la sesión.
        """
        self.session_log.append({
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'agent': agent,
            'content': content
        })
    
    def _print(self, msg: str):
        """Print if verbose."""
        if self.verbose:
            print(msg)
    
    def _print_header(self, title: str, char: str = "="):
        """Print a header."""
        if self.verbose:
            print(f"\n{char * 70}")
            print(title)
            print(char * 70)
    
    def save_session(self, filepath: str = 'council_session.json') -> None:
        """
        Guarda el resultado de la sesión en un archivo.
        """
        # Esta función requiere que run_full_session haya sido ejecutado
        # El resultado completo debería guardarse desde el return de run_full_session
        pass


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run AI Council Session')
    parser.add_argument('--api-key', help='Anthropic API key')
    parser.add_argument('--output', default='council_session.json', help='Output file')
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    args = parser.parse_args()
    
    council = AICouncilSession(
        api_key=args.api_key,
        verbose=not args.quiet
    )
    
    result = council.run_full_session()
    
    # Guardar resultado
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str, ensure_ascii=False)
    
    print(f"\n[OK] Session saved to {args.output}")

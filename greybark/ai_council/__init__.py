"""
Greybark Research - AI Council Module
======================================

Sistema multi-agente para decisiones de inversión.
Basado en el framework "FOMC In Silico" (Kazinnik & Sinclair, 2025).

Uso:
    from greybark.ai_council import AICouncilSession
    
    council = AICouncilSession()
    result = council.run_full_session()

Componentes:
    - agents/: Definición de los 6 agentes especializados
    - deliberation/: Motor de debate y consenso
    - data_integration/: Construcción del Data Packet
    - output/: Generación de reportes
"""

from .deliberation.committee_session import AICouncilSession
from .data_integration.unified_data_packet import UnifiedDataPacketBuilder

__all__ = [
    'AICouncilSession',
    'UnifiedDataPacketBuilder'
]

__version__ = '1.0.0'

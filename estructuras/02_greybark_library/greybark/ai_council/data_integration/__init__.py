"""
AI Council Data Integration
============================

Integra todos los modulos de greybark.analytics en un Data Packet unificado.
Incluye ingestion de research institucional en PDF.
"""

from .unified_data_packet import UnifiedDataPacketBuilder
from .research_collector import ResearchCollector, RESEARCH_SOURCES, get_research_data_for_packet

__all__ = [
    'UnifiedDataPacketBuilder',
    'ResearchCollector',
    'RESEARCH_SOURCES',
    'get_research_data_for_packet'
]

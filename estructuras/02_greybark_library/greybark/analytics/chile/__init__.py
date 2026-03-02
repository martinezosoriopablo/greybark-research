"""
Greybark Research - Chile Analytics Module
Mejora #6 del AI Council: Chile Profundo

Comprehensive analytics for Chilean markets:
- Macro dashboard (IMACEC, IPC, TPM, USD/CLP)
- UF/Breakeven inflation analysis
- Swap CÁMARA curve
- BCP/BCU bond yields
- Carry trade analysis
- IPSA sector analysis
"""

from .chile_analytics import (
    ChileAnalytics,
    BCChSeriesChile,
    YahooTickersChile,
    ChileMacroSnapshot,
    ChileBreakevenData,
    ChileCarryTrade,
)

__all__ = [
    'ChileAnalytics',
    'BCChSeriesChile',
    'YahooTickersChile',
    'ChileMacroSnapshot',
    'ChileBreakevenData',
    'ChileCarryTrade',
]

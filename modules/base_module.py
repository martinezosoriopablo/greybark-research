# -*- coding: utf-8 -*-
"""
Greybark Research - Analytics Module Base Class
================================================
Abstract base class for all analytics modules.
Provides: logging, chart generation, error handling, module interface.
"""

import sys
import os
import io
import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import warnings

# Fix Windows console encoding
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Add paths for imports
_MODULE_DIR = Path(__file__).parent
_CONSEJO_DIR = _MODULE_DIR.parent
_LIB_DIR = _CONSEJO_DIR.parent / "02_greybark_library"

for _p in [str(_CONSEJO_DIR), str(_LIB_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

warnings.filterwarnings('ignore')

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

logger = logging.getLogger("greybark.modules")


class AnalyticsModuleBase(ABC):
    """
    Abstract base class for all analytics modules.

    Subclasses must implement:
        _collect_data()       -> Dict
        _compute()            -> Dict
        _generate_chart()     -> str  (base64 PNG data URI)
        get_report_section()  -> str  (HTML)
        get_council_input()   -> str  (plain text)
    """

    MODULE_NAME: str = "base"

    def __init__(self, verbose: bool = True, dpi: int = 100, branding: Dict = None):
        self.verbose = verbose
        self.dpi = dpi
        self._data: Dict = {}
        self._result: Dict = {}
        self._chart: Optional[str] = None
        self._errors: list = []
        self._timestamp: Optional[str] = None
        # Derive colors from branding (or use Greybark defaults)
        try:
            from chart_config import get_chart_colors
            scheme = get_chart_colors(branding)
            self.COLORS = {
                'primary': scheme.primary, 'accent': scheme.accent,
                'positive': scheme.positive, 'negative': scheme.negative,
                'neutral': scheme.neutral, 'bg_light': scheme.bg_light,
                'text_dark': scheme.text_dark, 'text_medium': scheme.text_medium,
                'text_light': scheme.text_light,
            }
            self.SERIES_COLORS = scheme.series
        except ImportError:
            # Fallback if chart_config not available
            self.COLORS = {
                'primary': '#1a1a1a', 'accent': '#dd6b20',
                'positive': '#276749', 'negative': '#c53030',
                'neutral': '#744210', 'bg_light': '#f7f7f7',
                'text_dark': '#1a1a1a', 'text_medium': '#4a4a4a',
                'text_light': '#718096',
            }
            self.SERIES_COLORS = [
                '#1a365d', '#dd6b20', '#276749', '#c53030',
                '#805ad5', '#d69e2e', '#319795', '#e53e3e',
            ]
        if HAS_MPL:
            self._setup_matplotlib()

    # ── Logging ─────────────────────────────────────────────

    def _print(self, msg: str):
        if self.verbose:
            print(f"[{self.MODULE_NAME}] {msg}")

    # ── Matplotlib helpers ──────────────────────────────────

    def _setup_matplotlib(self):
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Segoe UI', 'Arial', 'Helvetica'],
            'font.size': 9,
            'axes.titlesize': 11,
            'axes.labelsize': 9,
            'axes.titleweight': 'bold',
            'axes.spines.top': False,
            'axes.spines.right': False,
            'figure.facecolor': 'white',
            'axes.facecolor': 'white',
            'axes.grid': True,
            'grid.alpha': 0.3,
            'grid.linestyle': '--',
        })

    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 PNG data URI."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{b64}"

    def _create_placeholder(self, title: str) -> str:
        """HTML placeholder when chart is unavailable."""
        return (
            f'<div style="background:#f7fafc;border:2px dashed #e2e8f0;'
            f'border-radius:8px;padding:40px;text-align:center;'
            f'color:#718096;margin:15px 0;">'
            f'<div style="font-size:14pt;margin-bottom:10px;">{title}</div>'
            f'<div style="font-size:10pt;">Chart no disponible</div></div>'
        )

    # ── Data helpers ────────────────────────────────────────

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        """Safely convert to float."""
        if val is None:
            return default
        s = str(val).replace('%', '').replace('+', '').strip()
        if not s or s in ('N/D', 'N/A', '-', '--'):
            return default
        try:
            return float(s)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _z_score_to_0_100(value: float, mean: float, std: float,
                          invert: bool = False) -> float:
        """
        Convert value to 0-100 scale using z-score.
        Z ∈ [-2, +2] maps to [0, 100]. Clamped.
        If invert=True, low raw value = high score.
        """
        if std == 0:
            return 50.0
        z = (value - mean) / std
        if invert:
            z = -z
        normalized = (z + 2) / 4 * 100
        return max(0.0, min(100.0, normalized))

    # ── Output directory ────────────────────────────────────

    @property
    def _output_dir(self) -> Path:
        d = _CONSEJO_DIR / "output" / "modules"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── Module interface ────────────────────────────────────

    def run(self) -> Dict[str, Any]:
        """
        Full execution: collect → compute → chart.
        Returns dict with result, chart, errors, elapsed.
        """
        self._print("Starting...")
        self._errors = []
        start = datetime.now()
        self._timestamp = start.isoformat()

        # Step 1: Collect
        try:
            self._data = self._collect_data()
            self._print(f"  Data collected ({len(self._data)} keys)")
        except Exception as e:
            self._errors.append(f"collect: {e}")
            self._print(f"  [ERR] Data collection: {e}")
            self._data = {}

        # Step 2: Compute
        try:
            self._result = self._compute()
            self._print(f"  Computation complete")
        except Exception as e:
            self._errors.append(f"compute: {e}")
            self._print(f"  [ERR] Computation: {e}")
            self._result = {'error': str(e)}

        # Step 3: Chart
        try:
            self._chart = self._generate_chart()
            self._print(f"  Chart generated")
        except Exception as e:
            self._errors.append(f"chart: {e}")
            self._print(f"  [ERR] Chart: {e}")
            self._chart = None

        elapsed = (datetime.now() - start).total_seconds()
        self._print(f"  Done in {elapsed:.1f}s")

        return {
            'module': self.MODULE_NAME,
            'timestamp': self._timestamp,
            'result': self._result,
            'chart': self._chart,
            'errors': self._errors,
            'elapsed_seconds': round(elapsed, 1),
        }

    @abstractmethod
    def _collect_data(self) -> Dict:
        ...

    @abstractmethod
    def _compute(self) -> Dict:
        ...

    @abstractmethod
    def _generate_chart(self) -> str:
        ...

    @abstractmethod
    def get_report_section(self) -> str:
        ...

    @abstractmethod
    def get_council_input(self) -> str:
        ...

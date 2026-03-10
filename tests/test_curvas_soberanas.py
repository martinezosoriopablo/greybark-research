"""Tests for curvas_soberanas module."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_fetchers.curvas_soberanas import (
    _build_narrative,
    _classify_shape,
    format_for_council_prompt,
    get_yield_curves,
    CACHE_FILE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_DATA = {
    "fecha_consulta": "2026-03-09",
    "alemania": {
        "fuente": "ECB Data Portal API",
        "tipo": "AAA-rated spot rate (Svensson)",
        "as_of": "2026-03-07",
        "datos": {1: 2.15, 2: 2.22, 3: 2.35, 5: 2.55, 7: 2.70, 10: 2.86, 15: 3.10, 20: 3.28, 30: 3.44},
        "spreads": {"2s10s": 0.64, "5s30s": 0.89},
    },
    "japon": {
        "fuente": "Ministry of Finance Japan",
        "tipo": "JGB benchmark yield",
        "as_of": "2026-03-07",
        "datos": {1: 0.78, 2: 0.95, 3: 1.10, 5: 1.40, 7: 1.70, 10: 2.10, 15: 2.60, 20: 2.85, 30: 3.35, 40: 3.65},
        "spreads": {"2s10s": 1.15, "10s30s": 1.25},
    },
    "desde_cache": False,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCurveShapeClassification:
    def test_normal_steep(self):
        datos = {2: 2.0, 5: 2.5, 10: 3.2, 30: 4.0}
        assert "empinada" in _classify_shape(datos).lower()

    def test_normal_moderate(self):
        datos = {2: 3.0, 5: 3.2, 10: 3.5, 30: 3.8}
        assert "normal" in _classify_shape(datos).lower()

    def test_inverted(self):
        datos = {2: 5.0, 5: 4.5, 10: 4.2, 30: 4.0}
        assert "invertida" in _classify_shape(datos).lower()

    def test_flat(self):
        datos = {2: 3.0, 5: 3.05, 10: 3.10}
        assert "plana" in _classify_shape(datos).lower()


class TestNarrative:
    def test_narrative_has_both(self):
        narrative = _build_narrative(MOCK_DATA)
        assert "Alemania" in narrative
        assert "Japón" in narrative

    def test_narrative_has_spreads(self):
        narrative = _build_narrative(MOCK_DATA)
        assert "pb" in narrative
        assert "10Y" in narrative

    def test_narrative_handles_missing(self):
        data = {
            "fecha_consulta": "2026-03-09",
            "alemania": MOCK_DATA["alemania"],
            "japon": None,
        }
        narrative = _build_narrative(data)
        assert "no disponible" in narrative.lower()
        assert "Alemania" in narrative


class TestFormatForCouncil:
    def test_output_has_structure(self):
        text = format_for_council_prompt(MOCK_DATA)
        assert "=== CURVAS SOBERANAS" in text
        assert "=== FIN CURVAS ===" in text
        assert "ALEMANIA" in text
        assert "JAPÓN" in text

    def test_output_has_yields(self):
        text = format_for_council_prompt(MOCK_DATA)
        assert "10Y: 2.86%" in text  # Alemania
        assert "10Y: 2.10%" in text  # Japon

    def test_output_has_spreads(self):
        text = format_for_council_prompt(MOCK_DATA)
        assert "+64 pb" in text  # Alemania 2s10s

    def test_output_has_shape(self):
        text = format_for_council_prompt(MOCK_DATA)
        assert "Forma:" in text

    def test_missing_curve(self):
        data = {**MOCK_DATA, "japon": None}
        text = format_for_council_prompt(data)
        assert "no disponible" in text.lower()


class TestCache:
    def test_cache_round_trip(self, tmp_path):
        from data_fetchers import curvas_soberanas as mod

        cache_file = tmp_path / "test_cache.json"
        original_cache = mod.CACHE_FILE
        mod.CACHE_FILE = cache_file
        mod.CACHE_DIR = tmp_path

        try:
            # Write
            mod._write_cache(MOCK_DATA.copy())
            assert cache_file.exists()

            # Read
            cached = mod._read_cache()
            assert cached is not None
            assert cached["alemania"]["datos"][10] == 2.86
            assert mod._cache_valid(cached, cache_hours=4)

            # Invalidate
            cached["_cache_ts"] = time.time() - 5 * 3600
            assert not mod._cache_valid(cached, cache_hours=4)
        finally:
            mod.CACHE_FILE = original_cache


class TestGetYieldCurvesOutput:
    """Test the output structure (mocking all fetchers)."""

    @patch("data_fetchers.curvas_soberanas._fetch_mof")
    @patch("data_fetchers.curvas_soberanas._fetch_ecb")
    def test_has_two_curves(self, mock_ecb, mock_mof):
        mock_ecb.return_value = MOCK_DATA["alemania"]
        mock_mof.return_value = MOCK_DATA["japon"]

        result = get_yield_curves(use_cache=False)
        assert "alemania" in result
        assert "japon" in result
        assert "resumen_narrativo" in result
        assert result["desde_cache"] is False

    @patch("data_fetchers.curvas_soberanas._fetch_mof")
    @patch("data_fetchers.curvas_soberanas._fetch_ecb")
    def test_partial_failure(self, mock_ecb, mock_mof):
        mock_ecb.return_value = MOCK_DATA["alemania"]
        mock_mof.return_value = None

        result = get_yield_curves(use_cache=False)
        assert result["alemania"] is not None
        assert result["japon"] is None

    @patch("data_fetchers.curvas_soberanas._fetch_mof")
    @patch("data_fetchers.curvas_soberanas._fetch_ecb")
    def test_all_fail_no_cache_raises(self, mock_ecb, mock_mof):
        mock_ecb.return_value = None
        mock_mof.return_value = None

        with pytest.raises(RuntimeError, match="All sovereign"):
            get_yield_curves(use_cache=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

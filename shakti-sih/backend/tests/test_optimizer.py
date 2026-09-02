"""Tests for the optimizer endpoint and grid-search engine.

Verifies safe-limit enforcement, scoring formula correctness, and
explanation generation.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.data_service import load_data, get_dataframe
from app.services.optimizer import composite_score, _normalise, optimise

load_data()
client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for optimizer helpers
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_perfect_scenario(self):
        """Max production, zero SOR/energy/risk → score near 1.0."""
        score = composite_score(
            oil_bpd=220.0, sor=0.0, energy_kwh=20.0, risk_score=0.0
        )
        prod = _normalise(220.0, 220.0)
        energy_pen = 0.25 * _normalise(20.0, 140.0)
        expected = prod - 0 - energy_pen - 0
        assert abs(score - round(expected, 4)) < 0.01

    def test_worst_scenario(self):
        """Zero production, max SOR/energy/risk → strongly negative."""
        score = composite_score(
            oil_bpd=0.0, sor=50.0, energy_kwh=140.0, risk_score=100.0
        )
        assert score < -0.5

    def test_production_is_positive(self):
        """Higher oil should increase the score."""
        s_low = composite_score(50.0, 5.0, 80.0, 50.0)
        s_high = composite_score(200.0, 5.0, 80.0, 50.0)
        assert s_high > s_low

    def test_risk_penalty_weight(self):
        """Doubling risk should decrease score by ~0.50 * delta_risk_norm."""
        s1 = composite_score(100.0, 5.0, 80.0, 20.0)
        s2 = composite_score(100.0, 5.0, 80.0, 60.0)
        risk_delta = _normalise(60.0, 100.0) - _normalise(20.0, 100.0)
        expected_diff = -0.50 * risk_delta
        actual_diff = s2 - s1
        assert abs(actual_diff - expected_diff) < 0.01


class TestSafeLimits:
    def test_optimise_returns_results(self):
        """Grid search should find at least one candidate."""
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
        )
        assert "best_option" in result
        assert result["alternatives_evaluated"] > 0

    def test_best_option_within_ranges(self):
        """Best SPM/VFD/steam should be within the search ranges."""
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
        )
        best = result["best_option"]
        assert 4.0 <= best["spm"] <= 10.0
        assert 30.0 <= best["vfd_frequency_hz"] <= 50.0
        assert 100.0 <= best["steam_volume_tonnes"] <= 260.0

    def test_custom_ranges_respected(self):
        """User-constrained ranges should narrow the search."""
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
            spm_range=(5.0, 7.0),
        )
        best = result["best_option"]
        assert 5.0 <= best["spm"] <= 7.0

    def test_explanation_generated(self):
        """The explanation string should be non-empty."""
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
        )
        assert len(result["explanation"]) > 20

    def test_score_breakdown_sum(self):
        """Score breakdown fields should relate to the composite score."""
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
        )
        bd = result["score_breakdown"]
        expected_composite = (
            bd["production_score"] - bd["sor_penalty"] - bd["energy_penalty"] - bd["risk_penalty"]
        )
        assert abs(bd["composite"] - round(expected_composite, 4)) < 0.01


# ---------------------------------------------------------------------------
# Integration tests for POST /api/optimize/{well_id}
# ---------------------------------------------------------------------------

class TestOptimizeAPI:
    def test_returns_200(self):
        """Endpoint should return HTTP 200 for a valid well."""
        resp = client.post("/api/optimize/BGW-01")
        assert resp.status_code == 200

    def test_404_for_unknown_well(self):
        """Unknown well ID should return 404."""
        resp = client.post("/api/optimize/NOPE-99")
        assert resp.status_code == 404

    def test_response_structure(self):
        """Response should have all required fields."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "well_id" in data
        assert "current" in data
        assert "best_option" in data
        assert "alternatives_evaluated" in data
        assert "explanation" in data
        assert "score_breakdown" in data

    def test_best_option_fields(self):
        """Best option should have all expected fields."""
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        expected_fields = {
            "spm", "vfd_frequency_hz", "steam_volume_tonnes",
            "projected_oil_bpd", "projected_energy_kwh", "projected_sor",
            "risk_score", "risk_label", "composite_score", "contributing_factors",
        }
        assert expected_fields.issubset(set(best.keys()))

    def test_alternatives_count(self):
        """Should evaluate a reasonable number of alternatives (> 50)."""
        data = client.post("/api/optimize/BGW-01").json()
        assert data["alternatives_evaluated"] >= 50

    def test_risk_in_range(self):
        """Risk score should be 0–100."""
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        assert 0 <= best["risk_score"] <= 100
        assert best["risk_label"] in ("Low", "Medium", "High")

    def test_with_custom_ranges(self):
        """Optional body should narrow the search."""
        resp = client.post(
            "/api/optimize/BGW-01",
            json={"spm_range": [5.0, 7.0]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert 5.0 <= data["best_option"]["spm"] <= 7.0

    def test_data_note_present(self):
        """Response should include the synthetic data disclaimer."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "synthetic" in data["data_note"].lower()

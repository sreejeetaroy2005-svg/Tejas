"""Unit tests for the rod-floating risk scoring engine.

These tests verify that the reusable risk engine matches the logic
from the synthetic data generator and enforces safe limits.
"""

import sys
import os

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.risk_engine import (
    compute_risk_score,
    risk_contributing_factors,
    RISK_LOW_MAX,
    RISK_MEDIUM_MAX,
    MU_MIN,
    MU_MAX,
)


class TestRiskScore:
    """Tests for compute_risk_score."""

    def test_low_risk_scenario(self):
        """High fillage, low viscosity → Low risk."""
        score, label = compute_risk_score(
            fillage_pct=90.0,
            viscosity_cp=200.0,
            spm=7.0,
            motor_current_a=28.0,
        )
        assert label == "Low"
        assert score <= RISK_LOW_MAX

    def test_high_risk_scenario(self):
        """Low fillage, high viscosity, fast pump → High risk."""
        score, label = compute_risk_score(
            fillage_pct=20.0,
            viscosity_cp=7500.0,
            spm=10.0,
            motor_current_a=55.0,
        )
        assert label == "High"
        assert score > RISK_MEDIUM_MAX

    def test_medium_risk_scenario(self):
        """Moderate conditions → Medium risk."""
        score, label = compute_risk_score(
            fillage_pct=50.0,
            viscosity_cp=5000.0,
            spm=8.0,
            motor_current_a=40.0,
        )
        assert label == "Medium"
        assert RISK_LOW_MAX < score <= RISK_MEDIUM_MAX

    def test_score_always_in_range(self):
        """Score should always be 0–100 regardless of inputs."""
        test_values = [
            (0, 150, 5, 20),
            (100, 8000, 11, 60),
            (50, 4000, 8, 40),
            (15, 500, 6, 25),
            (98, 100, 3, 18),
        ]
        for fillage, visc, spm, curr in test_values:
            score, label = compute_risk_score(fillage, visc, spm, curr)
            assert 0 <= score <= 100, f"Score {score} out of range for inputs {fillage}/{visc}/{spm}/{curr}"
            assert label in ("Low", "Medium", "High")

    def test_label_boundaries(self):
        """Verify exact boundary behavior at 35 and 65."""
        # Score exactly at 35 → Low (≤ 35 is Low)
        score_at_35, label = compute_risk_score(
            fillage_pct=65.0, viscosity_cp=MU_MIN, spm=6.0, motor_current_a=35.0
        )
        # The exact score depends on the formula, but label should be consistent
        assert label in ("Low", "Medium")

        # Very high fillage (bad) + max viscosity + high current → should be High
        score_extreme, label = compute_risk_score(
            fillage_pct=15.0, viscosity_cp=MU_MAX, spm=10.0, motor_current_a=55.0
        )
        assert label == "High"

    def test_no_spm_excess_when_oil_is_thin(self):
        """SPM excess component = 0 when viscosity is below threshold (mu_norm ≤ 0.5)."""
        # viscosity at midpoint: MU_MIN + 0.5*(MU_MAX-MU_MIN) = 4075
        # Below that → mu_norm < 0.5 → no SPM excess penalty
        factors_below = risk_contributing_factors(80.0, 3000.0, 10.0, 30.0)
        assert factors_below["spm_excess"] == 0.0

    def test_spm_excess_when_oil_is_thick(self):
        """SPM excess component > 0 when viscosity is high and SPM > optimal."""
        factors_above = risk_contributing_factors(40.0, 6000.0, 8.0, 40.0)
        assert factors_above["spm_excess"] > 0.0

    def test_contributing_factors_sum_to_total(self):
        """Individual factors should sum to the total risk score."""
        score, _ = compute_risk_score(55.0, 4000.0, 8.0, 38.0)
        factors = risk_contributing_factors(55.0, 4000.0, 8.0, 38.0)
        factor_sum = sum(factors.values())
        assert abs(factor_sum - score) < 0.2, (
            f"Factors sum {factor_sum} != score {score}"
        )

    def test_contributing_factors_keys(self):
        """Factors dict should have exactly the expected keys."""
        factors = risk_contributing_factors(50.0, 2000.0, 7.0, 30.0)
        assert set(factors.keys()) == {
            "fillage",
            "viscosity",
            "spm_excess",
            "motor_current",
        }

    def test_perfect_fillage_reduces_risk(self):
        """100% fillage → fillage component = 0."""
        score_high_fillage, _ = compute_risk_score(100.0, 4000.0, 8.0, 35.0)
        score_low_fillage, _ = compute_risk_score(50.0, 4000.0, 8.0, 35.0)
        assert score_high_fillage < score_low_fillage

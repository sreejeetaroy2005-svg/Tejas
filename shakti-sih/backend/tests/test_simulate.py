"""Tests for the simulate endpoint and simulator engine.

Verifies input validation, projection logic, and risk integration.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.data_service import load_data
from app.services.simulator import (
    compute_viscosity,
    compute_fillage,
    compute_motor_current,
    compute_energy,
    project_temperature,
    simulate_next_day,
)

load_data()
client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for simulator helper functions
# ---------------------------------------------------------------------------

class TestViscosity:
    def test_hot_oil_is_thin(self):
        """At peak temperature, viscosity should be near MU_MIN (150 cP)."""
        mu = compute_viscosity(125.0)
        assert mu < 200, f"Expected low viscosity at peak temp, got {mu}"

    def test_cold_oil_is_thick(self):
        """At baseline temperature, viscosity should be near MU_MAX (8000 cP)."""
        mu = compute_viscosity(45.0)
        assert mu > 7000, f"Expected high viscosity at baseline, got {mu}"

    def test_monotonic(self):
        """Viscosity should decrease monotonically with temperature."""
        temps = [45, 60, 80, 100, 125]
        viscosities = [compute_viscosity(t) for t in temps]
        for i in range(len(viscosities) - 1):
            assert viscosities[i] > viscosities[i + 1], (
                f"Viscosity should decrease: {viscosities[i]} at {temps[i]} "
                f"<= {viscosities[i + 1]} at {temps[i + 1]}"
            )


class TestFillage:
    def test_high_viscosity_reduces_fillage(self):
        """Thicker oil → lower fillage."""
        fillage_thin = compute_fillage(0.1, 7.0)
        fillage_thick = compute_fillage(0.9, 7.0)
        assert fillage_thin > fillage_thick

    def test_high_spm_reduces_fillage_when_thick(self):
        """Faster pump + thick oil → lower fillage (SPM excess penalty)."""
        fillage_slow = compute_fillage(0.8, 5.0)
        fillage_fast = compute_fillage(0.8, 10.0)
        assert fillage_slow > fillage_fast

    def test_no_spm_penalty_when_oil_thin(self):
        """SPM excess shouldn't penalise when mu_norm <= 0.5."""
        # mu_norm=0.4 (thin) — SPM shouldn't matter
        f1 = compute_fillage(0.4, 7.0)
        f2 = compute_fillage(0.4, 10.0)
        # Small difference is OK from the viscosity coeff, but no SPM excess
        assert abs(f1 - f2) < 1.0


class TestTemperatureProjection:
    def test_injection_rises(self):
        """Temperature should rise during injection."""
        t = project_temperature(80.0, "injection")
        assert t > 80.0

    def test_production_decays(self):
        """Temperature should decay during production."""
        t = project_temperature(80.0, "production")
        assert t < 80.0

    def test_soak_slight_rise(self):
        """Temperature should rise slightly during soak."""
        t = project_temperature(90.0, "soak")
        assert t > 90.0


# ---------------------------------------------------------------------------
# Integration tests for POST /api/simulate
# ---------------------------------------------------------------------------

class TestSimulateAPI:
    def test_returns_200_with_empty_body(self):
        """Endpoint should work with no overrides."""
        resp = client.post("/api/simulate", json={})
        assert resp.status_code == 200

    def test_response_structure(self):
        """Response should have all required fields."""
        data = client.post("/api/simulate", json={}).json()
        assert "well_id" in data
        assert "projected" in data
        assert "risk_score" in data
        assert "risk_label" in data
        assert "risk_factors" in data
        assert "explanation" in data
        assert "data_note" in data

    def test_projected_fields(self):
        """Projected dict should have all expected keys."""
        data = client.post("/api/simulate", json={}).json()
        proj = data["projected"]
        expected = {
            "reservoir_temperature_c",
            "viscosity_cp",
            "oil_bpd",
            "water_bpd",
            "estimated_fillage_pct",
            "motor_current_a",
            "vfd_frequency_hz",
            "energy_kwh",
            "sor",
        }
        assert expected.issubset(set(proj.keys()))

    def test_with_spm_override(self):
        """SPM override should be reflected in the projection."""
        resp = client.post("/api/simulate", json={"spm": 5.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["overrides"]["spm"] == 5.0

    def test_with_vfd_override(self):
        """VFD override should be accepted."""
        resp = client.post("/api/simulate", json={"vfd_frequency_hz": 35.0})
        assert resp.status_code == 200
        assert resp.json()["overrides"]["vfd_frequency_hz"] == 35.0

    def test_risk_in_valid_range(self):
        """Risk score should always be 0–100."""
        data = client.post("/api/simulate", json={"spm": 6.0}).json()
        assert 0 <= data["risk_score"] <= 100
        assert data["risk_label"] in ("Low", "Medium", "High")

    def test_rejects_spm_below_minimum(self):
        """SPM below 4.0 should be rejected with 422."""
        resp = client.post("/api/simulate", json={"spm": 2.0})
        assert resp.status_code == 422

    def test_rejects_spm_above_maximum(self):
        """SPM above 10.0 should be rejected with 422."""
        resp = client.post("/api/simulate", json={"spm": 12.0})
        assert resp.status_code == 422

    def test_rejects_vfd_out_of_range(self):
        """VFD outside 30–50 should be rejected with 422."""
        resp = client.post("/api/simulate", json={"vfd_frequency_hz": 20.0})
        assert resp.status_code == 422

    def test_rejects_steam_out_of_range(self):
        """Steam outside 100–260 should be rejected with 422."""
        resp = client.post("/api/simulate", json={"steam_volume_tonnes": 50.0})
        assert resp.status_code == 422

    def test_rejects_soak_days_out_of_range(self):
        """Soak days outside 3–6 should be rejected with 422."""
        resp = client.post("/api/simulate", json={"soak_time_days": 1})
        assert resp.status_code == 422

    def test_data_note_present(self):
        """Response should include the synthetic data disclaimer."""
        data = client.post("/api/simulate", json={}).json()
        assert "synthetic" in data["data_note"].lower()

"""Integration tests for the wells API endpoints.

Uses FastAPI's TestClient to test without starting a real server.
"""

import sys
import os

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.services.data_service import load_data

# Load data once for all tests in this module
load_data()

client = TestClient(app)


class TestListWells:
    """Tests for GET /api/wells."""

    def test_returns_200(self):
        """Endpoint should return HTTP 200."""
        response = client.get("/api/wells")
        assert response.status_code == 200

    def test_returns_array(self):
        """Response should contain a 'wells' array."""
        data = response.json() if False else client.get("/api/wells").json()
        assert "wells" in data
        assert isinstance(data["wells"], list)

    def test_contains_bgw01(self):
        """Should list BGW-01."""
        data = client.get("/api/wells").json()
        well_ids = [w["well_id"] for w in data["wells"]]
        assert "BGW-01" in well_ids

    def test_well_summary_fields(self):
        """Each well should have all required fields."""
        data = client.get("/api/wells").json()
        required_fields = {
            "well_id",
            "well_name",
            "field",
            "status",
            "current_css_cycle",
            "current_css_stage",
            "risk_score",
            "risk_label",
            "oil_bpd",
            "reservoir_temperature_c",
            "last_updated",
        }
        for well in data["wells"]:
            missing = required_fields - set(well.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_status_values(self):
        """Status should be one of the known CSS stages."""
        data = client.get("/api/wells").json()
        valid_statuses = {"injecting", "soaking", "producing"}
        for well in data["wells"]:
            assert well["status"] in valid_statuses, (
                f"Unexpected status: {well['status']}"
            )

    def test_risk_label_values(self):
        """Risk label should be Low, Medium, or High."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert well["risk_label"] in ("Low", "Medium", "High")

    def test_risk_score_in_range(self):
        """Risk score should be between 0 and 100."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert 0 <= well["risk_score"] <= 100

    def test_data_note_present(self):
        """Response should include the synthetic data disclaimer."""
        data = client.get("/api/wells").json()
        assert "data_note" in data
        assert "synthetic" in data["data_note"].lower()

    def test_total_matches_wells_count(self):
        """'total' field should match the length of the wells array."""
        data = client.get("/api/wells").json()
        assert data["total"] == len(data["wells"])

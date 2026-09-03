"""Tests for the 7-day forecast endpoint.

Uses FastAPI's TestClient to test without starting a real server.
All data is synthetic demonstration data.
"""

import sys
import os

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.services.data_service import load_data
from app.services.forecast_service import _load_models

# Load data and models once for all tests in this module
load_data()
_load_models()

client = TestClient(app)


class TestForecastEndpoint:
    """Tests for GET /api/wells/{well_id}/forecast."""

    def test_returns_200(self):
        """Endpoint should return HTTP 200 for a valid well."""
        response = client.get("/api/wells/BGW-01/forecast")
        assert response.status_code == 200

    def test_returns_7_days_by_default(self):
        """Response should contain exactly 7 forecast entries by default."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        assert "forecast" in data
        assert isinstance(data["forecast"], list)
        assert len(data["forecast"]) == 7

    def test_custom_days(self):
        """Should respect custom days parameter."""
        data = client.get("/api/wells/BGW-01/forecast?days=5").json()
        assert data["days"] == 5
        assert len(data["forecast"]) == 5

    def test_forecast_entry_fields(self):
        """Each entry should have date, predicted_temperature_c, predicted_oil_bpd."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        required_fields = {"date", "predicted_temperature_c", "predicted_oil_bpd"}
        for entry in data["forecast"]:
            missing = required_fields - set(entry.keys())
            assert not missing, f"Missing fields in forecast entry: {missing}"

    def test_temperature_physically_plausible(self):
        """Temperature predictions should be in a plausible range (30–300 °C)."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        for entry in data["forecast"]:
            temp = entry["predicted_temperature_c"]
            assert 30 <= temp <= 300, (
                f"Temperature {temp} °C outside plausible range on {entry['date']}"
            )

    def test_production_non_negative(self):
        """Oil production predictions should be >= 0."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        for entry in data["forecast"]:
            assert entry["predicted_oil_bpd"] >= 0, (
                f"Negative production {entry['predicted_oil_bpd']} on {entry['date']}"
            )

    def test_mae_present_and_positive(self):
        """Response should include temperature_mae and production_mae > 0."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        assert "temperature_mae" in data
        assert "production_mae" in data
        assert data["temperature_mae"] > 0
        assert data["production_mae"] > 0

    def test_well_id_matches(self):
        """well_id in response should match the request."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        assert data["well_id"] == "BGW-01"

    def test_data_note_present(self):
        """Response should include the synthetic data disclaimer."""
        data = client.get("/api/wells/BGW-01/forecast").json()
        assert "data_note" in data
        assert "synthetic" in data["data_note"].lower()

    def test_returns_404_for_missing_well(self):
        """Non-existent well should return HTTP 404."""
        response = client.get("/api/wells/NONEXISTENT-01/forecast")
        assert response.status_code == 404

    def test_forecast_dates_are_sequential(self):
        """Forecast dates should be consecutive days starting from the day after last data."""
        data = client.get("/api/wells/BGW-01/forecast?days=5").json()
        dates = [entry["date"] for entry in data["forecast"]]
        from datetime import datetime, timedelta

        parsed = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        for i in range(1, len(parsed)):
            assert parsed[i] - parsed[i - 1] == timedelta(days=1), (
                f"Dates not sequential: {dates[i - 1]} → {dates[i]}"
            )

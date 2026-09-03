"""Tests for the dynamometer card classifier endpoints.

Uses FastAPI's TestClient to test without starting a real server.
All data is synthetic demonstration data.
"""

import sys
import os
import ast

# Ensure the backend app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.services.data_service import load_data
from app.services.dynacard_service import _load_model

# Load data and models once for all tests in this module
load_data()
_load_model()

client = TestClient(app)

# Load one example card for use in classify tests
_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "data", "dynacards_synthetic_v1.csv"))
_example_row = _df.iloc[0]
_example_position = ast.literal_eval(_example_row["position"])
_example_load = ast.literal_eval(_example_row["load"])
_CLASSIFY_BODY = {
    "position": _example_position,
    "load": _example_load,
    "spm": float(_example_row["SPM"]),
    "stroke_length": float(_example_row["stroke_length"]),
    "temperature": float(_example_row["temperature"]),
    "viscosity": float(_example_row["viscosity"]),
    "fluid_level": float(_example_row["fluid_level"]),
    "pump_depth": float(_example_row["pump_depth"]),
    "production_rate": float(_example_row["production_rate"]),
}


class TestDynacardExamples:
    """Tests for GET /api/dynacards/examples."""

    def test_returns_200(self):
        response = client.get("/api/dynacards/examples")
        assert response.status_code == 200

    def test_returns_four_conditions(self):
        data = client.get("/api/dynacards/examples").json()
        assert isinstance(data, list)
        assert len(data) == 4

    def test_conditions_are_distinct(self):
        data = client.get("/api/dynacards/examples").json()
        labels = {card["condition_label"] for card in data}
        assert labels == {"Normal", "Rod Floating", "Fluid Pound", "Gas Interference"}

    def test_entry_fields(self):
        data = client.get("/api/dynacards/examples").json()
        required = {"card_id", "well_id", "position", "load", "condition_label", "risk_level"}
        for card in data:
            missing = required - set(card.keys())
            assert not missing, f"Missing fields: {missing}"

    def test_position_load_are_arrays(self):
        data = client.get("/api/dynacards/examples").json()
        for card in data:
            assert isinstance(card["position"], list)
            assert isinstance(card["load"], list)
            assert len(card["position"]) == 200
            assert len(card["load"]) == 200


class TestDynacardClassify:
    """Tests for POST /api/dynacards/classify."""

    def test_returns_200(self):
        response = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY)
        assert response.status_code == 200

    def test_response_fields(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        required = {
            "predicted_condition",
            "confidence",
            "top_features",
            "explanation",
            "recommended_action",
        }
        missing = required - set(data.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_predicted_condition_valid(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        valid = {"Normal", "Rod Floating", "Fluid Pound", "Gas Interference"}
        assert data["predicted_condition"] in valid

    def test_confidence_in_range(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        assert 0 <= data["confidence"] <= 1

    def test_top_features_count(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        assert isinstance(data["top_features"], list)
        assert len(data["top_features"]) == 3

    def test_explanation_nonempty(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        assert isinstance(data["explanation"], str)
        assert len(data["explanation"]) > 10

    def test_recommended_action_nonempty(self):
        data = client.post("/api/dynacards/classify", json=_CLASSIFY_BODY).json()
        assert isinstance(data["recommended_action"], str)
        assert len(data["recommended_action"]) > 5

    def test_rejects_empty_position(self):
        body = {**_CLASSIFY_BODY, "position": []}
        response = client.post("/api/dynacards/classify", json=body)
        assert response.status_code == 422

    def test_rejects_negative_spm(self):
        body = {**_CLASSIFY_BODY, "spm": -1}
        response = client.post("/api/dynacards/classify", json=body)
        assert response.status_code == 422

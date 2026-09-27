"""Integration tests asserting that real-well status endpoints now source
condition labels from the ML classifier, not solely from the rule-based formula.

These tests verify the core architectural wiring added in the diagnosis
unification work:
  - GET /api/wells returns ML classifier fields alongside rule-based risk.
  - GET /api/wells/{well_id} returns ML classifier fields.
  - POST /api/optimize/{well_id} includes ml_diagnosis_warning and
    current_ml_condition from the ML cross-check.
  - BestOption.risk_source is always "rule_based_projection" (optimizer
    cannot classify hypothetical candidates).
  - diagnosis_source distinguishes "ml_classifier" from "rule_based_projection".

All data is synthetic demonstration data.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.services.data_service import load_data
from app.services.dynacard_service import _load_model

# Load data and ML model once for all tests
load_data()
_load_model()

client = TestClient(app)


# ---------------------------------------------------------------------------
# ML fields in /api/wells
# ---------------------------------------------------------------------------

class TestWellsMLFields:
    """GET /api/wells should carry ML classifier output in each well summary."""

    def test_returns_200(self):
        resp = client.get("/api/wells")
        assert resp.status_code == 200

    def test_diagnosis_source_present(self):
        """Each well should have a diagnosis_source field."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert "diagnosis_source" in well, (
                f"Well {well['well_id']} missing diagnosis_source"
            )

    def test_diagnosis_source_is_ml_classifier(self):
        """With model loaded, diagnosis_source should be 'ml_classifier'."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert well["diagnosis_source"] == "ml_classifier", (
                f"Expected ml_classifier, got {well['diagnosis_source']!r}"
            )

    def test_ml_condition_present_and_valid(self):
        """ml_condition should be one of the 4 classifier labels (or low-conf variant)."""
        valid_conditions = {
            "Normal",
            "Rod Floating",
            "Fluid Pound",
            "Gas Interference",
            "Gas Interference (low confidence)",
        }
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert well["ml_condition"] is not None, (
                f"Well {well['well_id']} has null ml_condition despite diagnosis_source=ml_classifier"
            )
            assert well["ml_condition"] in valid_conditions, (
                f"Unexpected ml_condition: {well['ml_condition']!r}"
            )

    def test_ml_confidence_in_range(self):
        """ml_confidence should be 0–1."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            conf = well.get("ml_confidence")
            if conf is not None:
                assert 0.0 <= conf <= 1.0, f"ml_confidence {conf} out of range"

    def test_ml_gi_probability_in_range(self):
        """ml_gi_probability should be 0–1 when present."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            gi_prob = well.get("ml_gi_probability")
            if gi_prob is not None:
                assert 0.0 <= gi_prob <= 1.0, f"ml_gi_probability {gi_prob} out of range"

    def test_ml_condition_is_not_rule_based_score(self):
        """ml_condition must be a string condition label, not a float risk score."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            if well.get("ml_condition") is not None:
                # Should be a string, not a number
                assert isinstance(well["ml_condition"], str), (
                    f"ml_condition should be a string label, got {type(well['ml_condition'])}"
                )

    def test_rule_based_fields_still_present(self):
        """Rule-based risk_score and risk_label must still be present (backward compat)."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            assert "risk_score" in well
            assert "risk_label" in well
            assert 0 <= well["risk_score"] <= 100
            assert well["risk_label"] in ("Low", "Medium", "High")

    def test_ml_match_note_present(self):
        """ml_match_note should describe how the card was selected."""
        data = client.get("/api/wells").json()
        for well in data["wells"]:
            if well["diagnosis_source"] == "ml_classifier":
                note = well.get("ml_match_note")
                assert note is not None, "ml_match_note should be non-None for ml_classifier source"
                assert "synthetic" in note.lower() or "card" in note.lower(), (
                    f"ml_match_note does not look like a provenance note: {note!r}"
                )


# ---------------------------------------------------------------------------
# ML fields in /api/wells/{well_id}
# ---------------------------------------------------------------------------

class TestGetWellMLFields:
    """GET /api/wells/{well_id} should carry same ML fields as the list endpoint."""

    def test_returns_ml_condition(self):
        resp = client.get("/api/wells/BGW-01")
        assert resp.status_code == 200
        data = resp.json()
        assert "ml_condition" in data
        assert "diagnosis_source" in data

    def test_diagnosis_source_ml_classifier(self):
        data = client.get("/api/wells/BGW-01").json()
        assert data["diagnosis_source"] == "ml_classifier"

    def test_ml_condition_string(self):
        data = client.get("/api/wells/BGW-01").json()
        assert isinstance(data["ml_condition"], str)
        assert len(data["ml_condition"]) > 0

    def test_not_found_still_works(self):
        resp = client.get("/api/wells/NONEXISTENT-01")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# ML cross-check fields in /api/optimize/{well_id}
# ---------------------------------------------------------------------------

class TestOptimizeMLCrossCheck:
    """POST /api/optimize/{well_id} should carry ML cross-check fields."""

    def test_returns_200(self):
        resp = client.post("/api/optimize/BGW-01")
        assert resp.status_code == 200

    def test_current_ml_condition_field_present(self):
        """current_ml_condition should be in the optimize response."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "current_ml_condition" in data

    def test_ml_diagnosis_warning_field_present(self):
        """ml_diagnosis_warning should be in the optimize response (may be None)."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "ml_diagnosis_warning" in data

    def test_current_ml_condition_is_valid_or_none(self):
        """If current_ml_condition is non-None, it should be a valid condition label."""
        data = client.post("/api/optimize/BGW-01").json()
        cond = data.get("current_ml_condition")
        if cond is not None:
            valid = {
                "Normal", "Rod Floating", "Fluid Pound",
                "Gas Interference", "Gas Interference (low confidence)",
            }
            assert cond in valid, f"Unexpected current_ml_condition: {cond!r}"

    def test_ml_diagnosis_warning_is_string_or_none(self):
        """ml_diagnosis_warning must be a non-empty string or None."""
        data = client.post("/api/optimize/BGW-01").json()
        warning = data.get("ml_diagnosis_warning")
        if warning is not None:
            assert isinstance(warning, str) and len(warning) > 10

    def test_best_option_risk_source_is_rule_based(self):
        """best_option.risk_source must always be 'rule_based_projection'."""
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        assert best.get("risk_source") == "rule_based_projection", (
            f"Expected 'rule_based_projection', got {best.get('risk_source')!r}"
        )

    def test_vfd_is_fixed_value(self):
        """All candidates should have the same fixed VFD (not grid-searched)."""
        from app.services.optimizer import DEFAULT_VFD_FIXED_HZ
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        assert abs(best["vfd_frequency_hz"] - DEFAULT_VFD_FIXED_HZ) < 0.01, (
            f"Expected fixed VFD {DEFAULT_VFD_FIXED_HZ}, got {best['vfd_frequency_hz']}"
        )

    def test_alternatives_still_reasonable(self):
        """With VFD collapsed, alternatives should still be > 0 (SPM × steam)."""
        data = client.post("/api/optimize/BGW-01").json()
        # SPM range 4.0–10.0 step 0.5 = 13 values; steam 100–260 step 20 = 9 values
        # → 13 × 9 = 117 candidates minimum
        assert data["alternatives_evaluated"] >= 50


# ---------------------------------------------------------------------------
# Ensure ML and rule-based are clearly separated (no silent blending)
# ---------------------------------------------------------------------------

class TestDiagnosisSeparation:
    """Verify ML condition and rule-based score are distinct, labelled fields."""

    def test_ml_condition_not_same_as_risk_label(self):
        """ml_condition is a pump-failure label; risk_label is Low/Med/High — different namespaces."""
        data = client.get("/api/wells/BGW-01").json()
        risk_labels = {"Low", "Medium", "High"}
        ml_condition = data.get("ml_condition")
        if ml_condition is not None:
            # ml_condition should NOT be a plain risk label
            assert ml_condition not in risk_labels, (
                f"ml_condition should not be a risk label like 'Low'/'High', got: {ml_condition!r}"
            )

    def test_both_sources_present_simultaneously(self):
        """Both rule-based and ML fields should coexist in the response."""
        data = client.get("/api/wells/BGW-01").json()
        # Rule-based fields
        assert "risk_score" in data
        assert "risk_label" in data
        # ML fields
        assert "ml_condition" in data
        assert "diagnosis_source" in data

    def test_optimize_risk_score_is_not_ml_score(self):
        """The risk_score in best_option is rule-based; it should still be 0–100 float."""
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        rs = best["risk_score"]
        assert isinstance(rs, (int, float)), "risk_score should be numeric"
        assert 0 <= rs <= 100

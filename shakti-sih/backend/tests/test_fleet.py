"""Tests for fleet ranking logic and fleet API endpoints.

Covers:
  - _urgency_score() ranking formula
  - _viscosity_trend_3d() computation
  - _build_reason() produces non-empty text from real values
  - GET /api/fleet/priority returns 200, is sorted by urgency, has required fields
  - GET /api/fleet/summary returns 200, totals sum correctly
  - All 12 wells are present in priority response
  - BGW-01 history/wells endpoints still work (regression check)
"""

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Unit tests for fleet ranking helpers
# ---------------------------------------------------------------------------

class TestUrgencyScore:
    def test_high_risk_scores_above_low_risk(self):
        from app.routers.fleet import _urgency_score
        high = _urgency_score(70.0, 0.0, "Normal")
        low  = _urgency_score(20.0, 0.0, "Normal")
        assert high > low

    def test_fault_condition_adds_bonus(self):
        from app.routers.fleet import _urgency_score
        with_fault    = _urgency_score(40.0, 0.0, "Rod Floating")
        without_fault = _urgency_score(40.0, 0.0, "Normal")
        assert with_fault > without_fault

    def test_rising_viscosity_adds_bonus(self):
        from app.routers.fleet import _urgency_score
        rising = _urgency_score(40.0, 20.0, "Normal")   # 20% up
        flat   = _urgency_score(40.0,  0.0, "Normal")
        assert rising > flat

    def test_falling_viscosity_no_bonus(self):
        from app.routers.fleet import _urgency_score
        falling = _urgency_score(40.0, -20.0, "Normal")
        flat    = _urgency_score(40.0,   0.0, "Normal")
        # no penalty for falling viscosity — urgency should be <= flat
        assert falling <= flat + 0.1

    def test_none_condition_treated_as_normal(self):
        from app.routers.fleet import _urgency_score
        none_cond = _urgency_score(40.0, 0.0, None)
        normal    = _urgency_score(40.0, 0.0, "Normal")
        assert abs(none_cond - normal) < 0.01


class TestViscosityTrend:
    def test_rising_viscosity_positive(self):
        from app.routers.fleet import _viscosity_trend_3d
        df = pd.DataFrame({"viscosity_cp": [1000, 1100, 1200, 1400]})
        trend = _viscosity_trend_3d(df)
        assert trend > 0

    def test_falling_viscosity_negative(self):
        from app.routers.fleet import _viscosity_trend_3d
        df = pd.DataFrame({"viscosity_cp": [1400, 1200, 1100, 1000]})
        trend = _viscosity_trend_3d(df)
        assert trend < 0

    def test_flat_viscosity_near_zero(self):
        from app.routers.fleet import _viscosity_trend_3d
        df = pd.DataFrame({"viscosity_cp": [1000.0, 1000.0, 1000.0, 1000.0]})
        trend = _viscosity_trend_3d(df)
        assert abs(trend) < 0.01

    def test_short_series_returns_zero(self):
        from app.routers.fleet import _viscosity_trend_3d
        df = pd.DataFrame({"viscosity_cp": [1000, 1100]})
        assert _viscosity_trend_3d(df) == 0.0


class TestBuildReason:
    def _make_row(self, risk=30.0, label="Low", fillage=75.0, spm=8.0, visc=2000.0):
        return pd.Series({
            "rod_floating_risk_score": risk,
            "rod_floating_risk_label": label,
            "estimated_fillage_pct": fillage,
            "spm": spm,
            "viscosity_cp": visc,
        })

    def test_high_risk_mentioned(self):
        from app.routers.fleet import _build_reason
        row = self._make_row(risk=72.0, label="High")
        reason = _build_reason(row, 0.0, "Normal", "stable")
        assert "High" in reason

    def test_fault_condition_mentioned(self):
        from app.routers.fleet import _build_reason
        row = self._make_row(risk=45.0, label="Medium")
        reason = _build_reason(row, 0.0, "Rod Floating", "stable")
        assert "Rod Floating" in reason

    def test_rising_viscosity_mentioned(self):
        from app.routers.fleet import _build_reason
        row = self._make_row()
        reason = _build_reason(row, 15.0, "Normal", "stable")
        assert "viscosity" in reason.lower()

    def test_declining_forecast_mentioned(self):
        from app.routers.fleet import _build_reason
        row = self._make_row()
        reason = _build_reason(row, 0.0, "Normal", "declining")
        assert "declining" in reason.lower()

    def test_low_fillage_mentioned(self):
        from app.routers.fleet import _build_reason
        row = self._make_row(fillage=42.0)
        reason = _build_reason(row, 0.0, "Normal", "stable")
        assert "fillage" in reason.lower()

    def test_always_non_empty(self):
        from app.routers.fleet import _build_reason
        row = self._make_row()
        reason = _build_reason(row, 0.0, "Normal", "stable")
        assert len(reason) > 5


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestFleetPriorityEndpoint:
    def test_returns_200(self):
        r = client.get("/api/fleet/priority")
        assert r.status_code == 200

    def test_has_wells_list(self):
        r = client.get("/api/fleet/priority")
        body = r.json()
        assert "wells" in body
        assert isinstance(body["wells"], list)
        assert len(body["wells"]) > 0

    def test_all_12_wells_present(self):
        r = client.get("/api/fleet/priority")
        well_ids = {w["well_id"] for w in r.json()["wells"]}
        for i in range(1, 13):
            assert f"BGW-{i:02d}" in well_ids, f"BGW-{i:02d} missing from priority"

    def test_sorted_by_urgency_descending(self):
        r = client.get("/api/fleet/priority")
        scores = [w["urgency_score"] for w in r.json()["wells"]]
        assert scores == sorted(scores, reverse=True), "Priority not sorted descending"

    def test_required_fields_per_well(self):
        r = client.get("/api/fleet/priority")
        for well in r.json()["wells"]:
            for field in ("well_id", "risk_score", "risk_label", "urgency_score",
                          "css_stage", "oil_bpd", "estimated_fillage_pct",
                          "viscosity_trend_3d_pct", "forecast_trend", "reason"):
                assert field in well, f"Fleet priority item missing field: {field}"

    def test_reason_is_non_empty(self):
        r = client.get("/api/fleet/priority")
        for well in r.json()["wells"]:
            assert len(well["reason"]) > 5, f"{well['well_id']} has empty reason"

    def test_data_note_present(self):
        r = client.get("/api/fleet/priority")
        assert "data_note" in r.json()
        assert "synthetic" in r.json()["data_note"].lower()


class TestFleetSummaryEndpoint:
    def test_returns_200(self):
        r = client.get("/api/fleet/summary")
        assert r.status_code == 200

    def test_total_wells_is_12(self):
        r = client.get("/api/fleet/summary")
        assert r.json()["total_wells"] == 12

    def test_risk_counts_sum_to_total(self):
        r = client.get("/api/fleet/summary")
        body = r.json()
        total = body["wells_high_risk"] + body["wells_medium_risk"] + body["wells_low_risk"]
        assert total == body["total_wells"], "Risk counts don't sum to total_wells"

    def test_stage_counts_sum_to_total(self):
        r = client.get("/api/fleet/summary")
        body = r.json()
        total = body["wells_producing"] + body["wells_injecting"] + body["wells_soaking"]
        assert total == body["total_wells"]

    def test_total_oil_positive(self):
        r = client.get("/api/fleet/summary")
        assert r.json()["total_oil_bpd"] > 0

    def test_avg_risk_in_range(self):
        r = client.get("/api/fleet/summary")
        avg = r.json()["avg_risk_score"]
        assert 0 <= avg <= 100

    def test_data_note_present(self):
        r = client.get("/api/fleet/summary")
        assert "synthetic" in r.json()["data_note"].lower()


class TestExistingWellsUnbroken:
    """Regression: BGW-01 endpoints must still work after multi-well data was loaded."""

    def test_get_bgw01_returns_200(self):
        r = client.get("/api/wells/BGW-01")
        assert r.status_code == 200

    def test_bgw01_history_still_works(self):
        r = client.get("/api/wells/BGW-01/history?days=30")
        assert r.status_code == 200
        assert len(r.json()["records"]) > 0

    def test_unknown_well_still_404(self):
        r = client.get("/api/wells/NONEXISTENT-99")
        assert r.status_code == 404

    def test_all_12_wells_reachable(self):
        for i in range(1, 13):
            wid = f"BGW-{i:02d}"
            r = client.get(f"/api/wells/{wid}")
            assert r.status_code == 200, f"{wid} returned {r.status_code}"

    def test_wells_list_contains_all_12(self):
        r = client.get("/api/wells")
        body = r.json()
        assert body["total"] == 12
        well_ids = {w["well_id"] for w in body["wells"]}
        for i in range(1, 13):
            assert f"BGW-{i:02d}" in well_ids

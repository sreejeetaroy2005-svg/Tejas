"""Tests for the backtest script logic and the GET /api/backtest endpoint.

Covers:
  - run_backtest() returns structurally correct data
  - aggregate metric relationships that must always hold
  - _cycle_prod_progress() helper
  - GET /api/backtest returns 200 with correct shape when JSON exists
  - GET /api/backtest returns 404 with useful message when JSON is missing
"""

import json
import os
import tempfile

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "backtest_results.json"
)


def _results_exist() -> bool:
    return os.path.exists(_RESULTS_PATH)


# ---------------------------------------------------------------------------
# Unit tests for backtest logic
# ---------------------------------------------------------------------------

class TestCycleProdProgress:
    """Tests for the _cycle_prod_progress() helper."""

    def test_production_rows_are_fraction(self):
        from scripts.backtest import _cycle_prod_progress
        data = {
            "css_cycle_no": [1, 1, 1, 1],
            "css_stage": ["production", "production", "production", "production"],
            "days_since_steam_injection": [0, 10, 20, 40],
        }
        df = pd.DataFrame(data)
        p = _cycle_prod_progress(df)
        assert p.iloc[0] == pytest.approx(0.0, abs=0.01)
        assert p.iloc[-1] == pytest.approx(1.0, abs=0.01)

    def test_injection_rows_are_zero(self):
        from scripts.backtest import _cycle_prod_progress
        data = {
            "css_cycle_no": [1, 1],
            "css_stage": ["injection", "injection"],
            "days_since_steam_injection": [0, 1],
        }
        df = pd.DataFrame(data)
        p = _cycle_prod_progress(df)
        assert (p == 0.0).all()

    def test_clamped_to_0_1(self):
        from scripts.backtest import _cycle_prod_progress
        data = {
            "css_cycle_no": [1],
            "css_stage": ["production"],
            "days_since_steam_injection": [100],  # max_per_cycle = 100
        }
        df = pd.DataFrame(data)
        p = _cycle_prod_progress(df)
        assert 0.0 <= float(p.iloc[0]) <= 1.0


class TestBacktestStructure:
    """Tests for run_backtest() output structure."""

    @pytest.fixture(scope="class")
    def results(self):
        """Run the backtest once and cache."""
        from scripts.backtest import run_backtest
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return run_backtest(verbose=False)

    def test_has_required_top_level_keys(self, results):
        for key in ("baseline", "tejas", "delta_tejas_minus_baseline",
                    "method", "limitation", "energy_note",
                    "date_range", "n_days", "assumptions",
                    "daily_baseline", "daily_tejas"):
            assert key in results, f"Missing key: {key}"

    def test_n_days_is_180(self, results):
        assert results["n_days"] == 180

    def test_daily_arrays_length_matches_n_days(self, results):
        assert len(results["daily_baseline"]) == results["n_days"]
        assert len(results["daily_tejas"]) == results["n_days"]

    def test_risk_day_counts_sum_to_n_days(self, results):
        for arm in ("baseline", "tejas"):
            total = (
                results[arm]["high_risk_days"]
                + results[arm]["medium_risk_days"]
                + results[arm]["low_risk_days"]
            )
            assert total == results["n_days"], f"{arm}: risk day counts don't sum to n_days"

    def test_tejas_high_risk_not_greater_than_baseline(self, results):
        """Optimizer cannot increase High-risk days vs baseline on the same simulator."""
        assert results["tejas"]["high_risk_days"] <= results["baseline"]["high_risk_days"]

    def test_delta_keys_present(self, results):
        for key in ("high_risk_days", "avg_risk_score", "total_oil_bbl",
                    "total_energy_kwh", "avg_sor"):
            assert key in results["delta_tejas_minus_baseline"]

    def test_delta_is_tejas_minus_baseline(self, results):
        d = results["delta_tejas_minus_baseline"]
        b = results["baseline"]
        t = results["tejas"]
        assert d["high_risk_days"] == t["high_risk_days"] - b["high_risk_days"]
        assert abs(d["avg_risk_score"] - (t["avg_risk_score"] - b["avg_risk_score"])) < 0.01

    def test_total_oil_is_non_negative(self, results):
        assert results["baseline"]["total_oil_bbl"] >= 0
        assert results["tejas"]["total_oil_bbl"] >= 0

    def test_limitation_is_non_empty(self, results):
        assert len(results["limitation"]) > 20

    def test_daily_row_has_required_fields(self, results):
        row = results["daily_baseline"][0]
        for field in ("date", "css_stage", "spm_used", "steam_used",
                      "oil_bpd", "energy_kwh", "sor", "risk_score", "risk_label"):
            assert field in row, f"daily_baseline row missing field: {field}"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestBacktestEndpoint:

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated — run scripts/backtest.py first",
    )
    def test_returns_200(self):
        r = client.get("/api/backtest")
        assert r.status_code == 200

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated",
    )
    def test_response_has_baseline_and_tejas(self):
        r = client.get("/api/backtest")
        body = r.json()
        assert "baseline" in body
        assert "tejas" in body

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated",
    )
    def test_n_days_is_180(self):
        r = client.get("/api/backtest")
        assert r.json()["n_days"] == 180

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated",
    )
    def test_baseline_fields_present(self):
        r = client.get("/api/backtest")
        arm = r.json()["baseline"]
        for f in ("high_risk_days", "avg_risk_score", "total_oil_bbl",
                  "total_energy_kwh", "avg_sor"):
            assert f in arm

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated",
    )
    def test_data_note_present(self):
        r = client.get("/api/backtest")
        assert "data_note" in r.json()

    @pytest.mark.skipif(
        not _results_exist(),
        reason="backtest_results.json not generated",
    )
    def test_delta_is_in_response(self):
        r = client.get("/api/backtest")
        assert "delta_tejas_minus_baseline" in r.json()

    def test_returns_404_when_file_missing(self):
        """Patch the path so the endpoint thinks the file is missing."""
        import app.routers.backtest as bt_router
        original = bt_router._RESULTS_PATH
        bt_router._RESULTS_PATH = "/nonexistent/path/backtest_results.json"
        try:
            r = client.get("/api/backtest")
            assert r.status_code == 404
            assert "backtest.py" in r.json()["detail"]
        finally:
            bt_router._RESULTS_PATH = original

    def test_404_message_mentions_run_command(self):
        import app.routers.backtest as bt_router
        original = bt_router._RESULTS_PATH
        bt_router._RESULTS_PATH = "/nonexistent/path/backtest_results.json"
        try:
            r = client.get("/api/backtest")
            detail = r.json()["detail"]
            assert "scripts/backtest.py" in detail or "backtest.py" in detail
        finally:
            bt_router._RESULTS_PATH = original

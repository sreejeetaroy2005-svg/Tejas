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

    def test_spm_diagnostics_present(self, results):
        assert "spm_diagnostics" in results
        diag = results["spm_diagnostics"]
        for key in ("min", "max", "mean", "unique_values", "days_at_minimum_spm", "distribution"):
            assert key in diag, f"spm_diagnostics missing key: {key}"

    def test_tejas_spm_varies_across_days(self, results):
        """After the SPM-oil coupling fix, the optimizer must NOT always pick the same SPM."""
        t_spm = [r["spm_used"] for r in results["daily_tejas"]]
        unique_spms = set(t_spm)
        assert len(unique_spms) > 1, (
            f"Optimizer picked identical SPM={t_spm[0]} on every day — "
            "SPM-oil coupling may not be active."
        )

    def test_both_arms_use_same_simulator_oil_check(self, results):
        """On a day where Tejas picks the same SPM as baseline, oil must be equal."""
        for b_row, t_row in zip(results["daily_baseline"], results["daily_tejas"]):
            if abs(b_row["spm_used"] - t_row["spm_used"]) < 0.01:
                assert abs(b_row["oil_bpd"] - t_row["oil_bpd"]) < 1.0, (
                    f"Same SPM {b_row['spm_used']} on {b_row['date']} but oil differs: "
                    f"baseline={b_row['oil_bpd']}, tejas={t_row['oil_bpd']}"
                )


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestSimulatorSpmCoupling:
    """Tests that SPM is now a genuine trade-off in the simulator."""

    def test_oil_falls_at_very_low_spm_hot_well(self):
        """Hot well: pump-limited at low SPM → oil decreases below crossover."""
        from app.services.simulator import simulate_next_day
        # Hot well — reservoir inflow is high, pump becomes the bottleneck at low SPM
        high_spm = simulate_next_day(110.0, "production", 0.2, 9.0, 42.0, 0.3)
        low_spm  = simulate_next_day(110.0, "production", 0.2, 4.0, 42.0, 0.3)
        assert low_spm["oil_bpd"] < high_spm["oil_bpd"], (
            f"Expected oil to fall at low SPM on hot well: "
            f"SPM=4→{low_spm['oil_bpd']:.1f}, SPM=9→{high_spm['oil_bpd']:.1f}"
        )

    def test_oil_identical_at_sufficient_spm(self):
        """Cold well: reservoir-limited → changing SPM above the crossover doesn't gain oil."""
        from app.services.simulator import simulate_next_day
        # Cold well — low inflow regardless of SPM
        mid  = simulate_next_day(55.0, "production", 0.5, 6.5, 42.0, 0.3)
        high = simulate_next_day(55.0, "production", 0.5, 9.0, 42.0, 0.3)
        # Oil should be equal (both above pump crossover for cold inflow)
        assert abs(mid["oil_bpd"] - high["oil_bpd"]) < 2.0, (
            f"Cold well oil should be reservoir-limited: SPM=6.5→{mid['oil_bpd']:.1f}, "
            f"SPM=9→{high['oil_bpd']:.1f}"
        )

    def test_risk_rises_at_high_spm_thick_oil(self):
        """Thick oil + high SPM → excess-SPM risk component activates."""
        from app.services.simulator import simulate_next_day
        low_spm  = simulate_next_day(55.0, "production", 0.5, 5.0, 42.0, 0.3)
        high_spm = simulate_next_day(55.0, "production", 0.5, 9.0, 42.0, 0.3)
        assert high_spm["risk_score"] > low_spm["risk_score"], (
            f"Risk should rise at high SPM with thick oil: "
            f"SPM=5→{low_spm['risk_score']:.1f}, SPM=9→{high_spm['risk_score']:.1f}"
        )

    def test_energy_increases_monotonically_with_spm(self):
        """Energy always increases as SPM increases (energy = 9*SPM + 0.15*current)."""
        from app.services.simulator import simulate_next_day
        prev_energy = 0.0
        for spm in [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]:
            r = simulate_next_day(80.0, "production", 0.3, spm, 42.0, 0.3)
            assert r["energy_kwh"] >= prev_energy - 0.1, (
                f"Energy should increase with SPM: SPM={spm} gives {r['energy_kwh']:.1f}"
            )
            prev_energy = r["energy_kwh"]

    def test_compute_pump_capacity_scales_with_spm(self):
        """pump_capacity_bpd is proportional to SPM."""
        from app.services.simulator import compute_pump_capacity
        cap4 = compute_pump_capacity(4.0, 80.0)
        cap8 = compute_pump_capacity(8.0, 80.0)
        assert abs(cap8 / cap4 - 2.0) < 0.01, (
            f"Pump capacity should double when SPM doubles: {cap4:.1f} → {cap8:.1f}"
        )

    def test_spm_below_floor_raises(self):
        """compute_pump_capacity must raise ValueError below SPM_MIN_OPERATIONAL."""
        from app.services.simulator import compute_pump_capacity, SPM_MIN_OPERATIONAL
        import pytest
        with pytest.raises(ValueError, match="SPM_MIN_OPERATIONAL"):
            compute_pump_capacity(SPM_MIN_OPERATIONAL - 0.5, 80.0)

    def test_spm_floor_matches_api_minimum(self):
        """SPM_MIN_OPERATIONAL in simulator must equal the ge= bound in SimulateRequest."""
        from app.services.simulator import SPM_MIN_OPERATIONAL
        from app.models import SimulateRequest
        import pydantic
        # The field metadata ge value must equal SPM_MIN_OPERATIONAL
        field = SimulateRequest.model_fields["spm"]
        # Pydantic v2: constraints are in field.metadata
        ge_value = None
        for constraint in field.metadata:
            if hasattr(constraint, "ge"):
                ge_value = constraint.ge
                break
        assert ge_value is not None, "SimulateRequest.spm missing ge constraint"
        assert ge_value == SPM_MIN_OPERATIONAL, (
            f"API spm minimum ({ge_value}) does not match SPM_MIN_OPERATIONAL ({SPM_MIN_OPERATIONAL})"
        )

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

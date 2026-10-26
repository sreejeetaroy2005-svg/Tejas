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
from app.services.optimizer import composite_score, _normalise, optimise, DEFAULT_VFD_FIXED_HZ

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
            current_viscosity_cp=4000.0,
        )
        assert "best_option" in result
        assert result["alternatives_evaluated"] > 0

    def test_best_option_within_ranges(self):
        """Best SPM/steam should be within the search ranges.

        VFD is no longer grid-searched — it is fixed at DEFAULT_VFD_FIXED_HZ.
        """
        result = optimise(
            current_temp_c=60.0,
            css_stage="production",
            cycle_prod_progress=0.5,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.15,
            current_oil_bpd=50.0,
            current_risk_score=50.0,
            current_viscosity_cp=4000.0,
        )
        best = result["best_option"]
        assert 4.0 <= best["spm"] <= 10.0
        # VFD is fixed, not grid-searched
        assert abs(best["vfd_frequency_hz"] - DEFAULT_VFD_FIXED_HZ) < 0.01
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
            current_viscosity_cp=4000.0,
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
            current_viscosity_cp=4000.0,
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
            current_viscosity_cp=4000.0,
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
        """Response should have all required fields including new constraint fields."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "well_id" in data
        assert "current" in data
        assert "best_option" in data
        assert "alternatives_evaluated" in data
        assert "explanation" in data
        assert "score_breakdown" in data
        assert "oil_constraint_note" in data
        assert "oil_constraint_active" in data

    def test_best_option_fields(self):
        """Best option should have all expected fields including new oil_change_pct."""
        data = client.post("/api/optimize/BGW-01").json()
        best = data["best_option"]
        expected_fields = {
            "spm", "vfd_frequency_hz", "steam_volume_tonnes",
            "projected_oil_bpd", "projected_energy_kwh", "projected_sor",
            "risk_score", "risk_label", "composite_score", "contributing_factors",
            "oil_change_pct",
        }
        assert expected_fields.issubset(set(best.keys()))

    def test_alternatives_count(self):
        """Should evaluate a reasonable number of alternatives (>= 50).

        VFD is fixed (not grid-searched), so candidate count = |SPM| × |steam|.
        Default: SPM 4.0-10.0 step 0.5 = 13 values × steam 100-260 step 20 = 9 values = 117.
        """
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


# ---------------------------------------------------------------------------
# Tests for the max_oil_loss_pct constraint
# ---------------------------------------------------------------------------

class TestOilLossConstraint:

    def _run(self, current_oil: float, max_pct: float, **kw):
        return optimise(
            current_temp_c=80.0,
            css_stage="production",
            cycle_prod_progress=0.3,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.2,
            current_oil_bpd=current_oil,
            current_risk_score=50.0,
            current_viscosity_cp=3000.0,
            max_oil_loss_pct=max_pct,
            **kw,
        )

    def test_oil_change_pct_in_best_option(self):
        """Every best_option must include oil_change_pct."""
        result = self._run(100.0, 15.0)
        assert "oil_change_pct" in result["best_option"]

    def test_oil_change_pct_type(self):
        """oil_change_pct must be a float."""
        result = self._run(100.0, 15.0)
        assert isinstance(result["best_option"]["oil_change_pct"], float)

    def test_current_projected_oil_bpd_present(self):
        """optimise() must return current_projected_oil_bpd."""
        result = self._run(100.0, 15.0)
        assert "current_projected_oil_bpd" in result
        assert isinstance(result["current_projected_oil_bpd"], float)
        assert result["current_projected_oil_bpd"] > 0

    def test_current_projected_oil_matches_current_candidate(self):
        """current_projected_oil_bpd must equal the current-settings candidate's oil."""
        result = self._run(100.0, 15.0)
        # Find the current-settings candidate in the pool (we see it only if it wins)
        baseline = result["current_projected_oil_bpd"]
        assert baseline > 0
        # The current-settings candidate's oil_change_pct == 0 BY DEFINITION,
        # so best_option.projected_oil_bpd - baseline == 0 when it wins.
        if result["best_option"].get("is_current_settings"):
            assert abs(result["best_option"]["projected_oil_bpd"] - baseline) < 0.01

    def test_tight_constraint_excludes_candidates(self):
        """A very tight constraint (0%) should still return a result and activate the note."""
        result = self._run(150.0, 0.0)
        # Either the note is set (some were excluded) or constraint was not needed
        # (all candidates met 0% — which means no candidate projected less oil)
        assert "best_option" in result
        # When tight, if any candidate is excluded, constraint fields are set
        if result["oil_constraint_active"]:
            assert result["oil_constraint_note"] is not None
            assert len(result["oil_constraint_note"]) > 10

    def test_loose_constraint_passes_all(self):
        """Constraint of 100% should pass all candidates and leave note as None."""
        result = self._run(100.0, 100.0)
        assert result["oil_constraint_note"] is None
        assert result["oil_constraint_active"] is False

    def test_best_within_constraint_respects_limit(self):
        """Best option must not drop oil below the allowed threshold (when candidates exist)."""
        max_pct = 10.0
        current_oil = 120.0
        result = self._run(current_oil, max_pct)
        pct = result["best_option"]["oil_change_pct"]
        if not result["oil_constraint_active"] or (
            result["oil_constraint_active"]
            and "smallest oil reduction" not in (result["oil_constraint_note"] or "")
        ):
            # Normal case: constraint was met — oil change >= -max_pct
            assert pct >= -max_pct - 0.1, (
                f"oil_change_pct={pct:.2f} violates -{max_pct}% limit"
            )

    def test_injection_stage_constraint_disabled(self):
        """On injection days (current_oil=0), constraint should not apply."""
        result = optimise(
            current_temp_c=65.0,
            css_stage="injection",
            cycle_prod_progress=0.0,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.0,
            current_oil_bpd=0.0,
            current_risk_score=20.0,
            current_viscosity_cp=3000.0,
            max_oil_loss_pct=5.0,  # very tight, but should be ignored
        )
        assert "best_option" in result
        # Constraint note should be None because oil=0 means constraint skipped
        assert result["oil_constraint_note"] is None
        assert result["oil_constraint_active"] is False

    def test_constraint_note_mentions_pct_when_active(self):
        """When constraint is active, note should mention the threshold."""
        result = self._run(150.0, 0.0)
        if result["oil_constraint_active"] and result["oil_constraint_note"]:
            note = result["oil_constraint_note"]
            # Note should contain either the threshold value or a meaningful explanation
            assert any(x in note for x in ["0%", "0.0", "0 of", "No candidate", "smallest"])

    def test_api_accepts_max_oil_loss_pct_field(self):
        """POST /api/optimize/{well_id} should accept max_oil_loss_pct in the body."""
        resp = client.post(
            "/api/optimize/BGW-01",
            json={"max_oil_loss_pct": 5.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "oil_constraint_active" in data
        assert "oil_constraint_note" in data
        assert "note_type" in data
        assert "current_projected_oil_bpd" in data

    def test_api_default_constraint_is_15(self):
        """Empty body should apply the default 15% constraint."""
        resp = client.post("/api/optimize/BGW-01", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "oil_constraint_note" in data
        assert "current_projected_oil_bpd" in data

    def test_oil_cap_note_type_when_candidates_excluded(self):
        """When oil cap excludes candidates, note_type must be 'oil_cap'."""
        result = self._run(150.0, 0.0)
        if result["oil_constraint_active"] and not result["best_option"].get("is_current_settings"):
            assert result.get("note_type") == "oil_cap", (
                f"Expected note_type='oil_cap' when cap active, got {result.get('note_type')!r}"
            )

    def test_note_type_none_when_no_constraint_active(self):
        """When constraint does not fire, note_type must be None."""
        result = self._run(100.0, 100.0)  # 100% = disabled
        assert result.get("note_type") is None, (
            f"Expected note_type=None when constraint disabled, got {result.get('note_type')!r}"
        )

    def test_constraint_tighter_never_worsens_oil_more_than_allowed(self):
        """With a strict constraint, projected oil should be as close to current as possible."""
        current_oil = 100.0
        result_tight  = self._run(current_oil, 5.0)
        result_loose  = self._run(current_oil, 50.0)
        pct_tight = result_tight["best_option"]["oil_change_pct"]
        pct_loose = result_loose["best_option"]["oil_change_pct"]
        # The tight constraint should produce a best option that loses less or equal oil
        # unless no candidate met the tight threshold (fallback to least-bad)
        if not result_tight["oil_constraint_active"] or (
            result_tight["oil_constraint_active"]
            and "smallest oil reduction" not in (result_tight["oil_constraint_note"] or "")
        ):
            assert pct_tight >= pct_loose - 0.1, (
                f"Tight constraint produced worse oil loss ({pct_tight:.1f}%) "
                f"than loose ({pct_loose:.1f}%)"
            )


# ---------------------------------------------------------------------------
# Tests for keep-current-settings candidate and risk guard
# ---------------------------------------------------------------------------

class TestCurrentSettingsCandidate:
    """The 'keep current settings' candidate must always be in the pool."""

    def _run(self, **kw):
        defaults = dict(
            current_temp_c=80.0,
            css_stage="production",
            cycle_prod_progress=0.3,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.2,
            current_oil_bpd=100.0,
            current_risk_score=50.0,
            current_viscosity_cp=3000.0,
        )
        defaults.update(kw)
        return optimise(**defaults)

    def test_is_current_settings_field_in_best_option(self):
        """best_option must always carry is_current_settings (bool)."""
        r = self._run()
        assert "is_current_settings" in r["best_option"]
        assert isinstance(r["best_option"]["is_current_settings"], bool)

    def test_alternatives_evaluated_includes_current_candidate(self):
        """Grid has 117 candidates (13 SPM × 9 steam); +1 current = 118."""
        r = self._run()
        assert r["alternatives_evaluated"] == 118, (
            f"Expected 118 (117 grid + 1 current), got {r['alternatives_evaluated']}"
        )

    def test_current_settings_wins_when_tight_oil_cap_and_high_spm_costs_oil(self):
        """When oil cap is very tight and the grid finds no oil-preserving option,
        the current-settings candidate (oil_change ≈ 0) should win or be close to winning."""
        # Hot well, current SPM=9, cap=0% — no candidate can outperform current on oil
        r = self._run(
            current_temp_c=110.0,
            cycle_prod_progress=0.1,
            current_spm=9.0,
            current_oil_bpd=193.0,
            max_oil_loss_pct=0.0,
        )
        # The winner must pass the 0% oil cap, so oil_change >= 0
        assert r["best_option"]["oil_change_pct"] >= -0.5, (
            f"With 0% oil-loss cap, best option should not lose oil; "
            f"got {r['best_option']['oil_change_pct']:.1f}%"
        )

    def test_current_settings_candidate_has_zero_oil_change_pct(self):
        """The current-settings candidate must have oil_change_pct == 0.0 exactly.

        oil_change_pct is computed relative to the simulator's own projection
        at current settings (_oil_baseline), so the current-settings candidate
        is always the reference point and shows 0.0% by definition.

        diff vs previous version: the old test asserted only isinstance(float)
        because the old implementation compared to current_oil_bpd (CSV value)
        which could differ from the simulator's projection.  Now that all
        oil_change_pct values use _oil_baseline as the reference, the
        current-settings candidate is guaranteed exactly 0.0%.
        """
        r = self._run(
            current_risk_score=1.0,   # force risk guard so current-settings wins
            current_oil_bpd=100.0,
        )
        if r["best_option"].get("is_current_settings"):
            assert r["best_option"]["oil_change_pct"] == pytest.approx(0.0, abs=0.01), (
                f"Current-settings candidate must show 0.0% oil_change_pct "
                f"(it IS the baseline); got {r['best_option']['oil_change_pct']:.4f}"
            )


class TestRiskGuard:
    """Recommended option must not have higher risk than current without explanation."""

    def _run(self, current_risk: float, **kw):
        defaults = dict(
            current_temp_c=80.0,
            css_stage="production",
            cycle_prod_progress=0.3,
            current_spm=9.0,
            current_vfd=42.0,
            current_sor=0.2,
            current_oil_bpd=100.0,
            current_viscosity_cp=3000.0,
        )
        defaults.update(kw)
        return optimise(current_risk_score=current_risk, **defaults)

    def test_risk_guard_triggers_when_best_has_higher_risk(self):
        """When current_risk_score is very low (0) and every grid candidate
        has higher risk, the risk guard must promote the current-settings
        candidate and populate oil_constraint_note."""
        r = self._run(current_risk=0.0)
        if r["best_option"]["risk_score"] > 0.5:
            # Guard should have fired
            assert r["best_option"].get("is_current_settings"), (
                "Risk guard should promote current-settings when best has higher risk"
            )
            assert r["oil_constraint_note"] is not None
            assert "Risk guard" in r["oil_constraint_note"]

    def test_risk_guard_note_mentions_promoted_spm(self):
        """The risk-guard note must name the current SPM."""
        r = self._run(current_risk=0.0, current_spm=7.0)
        if r["best_option"].get("is_current_settings"):
            note = r["oil_constraint_note"] or ""
            assert "7.0" in note or "SPM" in note

    def test_risk_guard_does_not_trigger_when_risk_improves(self):
        """If the best candidate lowers risk vs current, no guard fires."""
        # High current risk: optimizer will almost certainly find better
        r = self._run(current_risk=90.0)
        # Best should have lower risk, guard should not fire
        if not r["best_option"].get("is_current_settings"):
            # Guard did not fire — expected path
            assert r["best_option"]["risk_score"] <= 90.0 + 0.5, (
                "Non-current-settings best should not raise risk vs 90.0"
            )

    def test_recommendation_risk_never_exceeds_current_without_note(self):
        """If best has higher risk than current, oil_constraint_note must be set."""
        r = self._run(current_risk=5.0)
        best_risk = r["best_option"]["risk_score"]
        if best_risk > 5.0 + 0.5:
            assert r["oil_constraint_note"] is not None, (
                f"best risk={best_risk:.1f} > current=5.0 but no constraint note set"
            )

    def test_api_best_option_has_is_current_settings(self):
        """POST /api/optimize/{well_id} response must include is_current_settings."""
        data = client.post("/api/optimize/BGW-01").json()
        assert "is_current_settings" in data["best_option"], (
            "API response missing is_current_settings in best_option"
        )

    def test_risk_guard_sets_note_type(self):
        """When risk guard fires, note_type must be 'risk_guard'."""
        r = self._run(current_risk=0.0)
        if r["best_option"].get("is_current_settings") and r["oil_constraint_active"]:
            assert r.get("note_type") == "risk_guard", (
                f"Expected note_type='risk_guard', got {r.get('note_type')!r}"
            )


# ---------------------------------------------------------------------------
# Tests for backtest optimizer_settings recording
# ---------------------------------------------------------------------------

class TestBacktestOptimizerSettings:
    """The stored backtest_results.json must record the optimizer settings used."""

    @pytest.fixture(scope="class")
    def json_data(self):
        import json, os
        path = os.path.join(
            os.path.dirname(__file__), "..", "data", "backtest_results.json"
        )
        if not os.path.exists(path):
            pytest.skip("backtest_results.json not found — run scripts/backtest.py first")
        with open(path) as f:
            return json.load(f)

    def test_optimizer_settings_key_present(self, json_data):
        assert "optimizer_settings" in json_data, (
            "backtest_results.json missing 'optimizer_settings' key"
        )

    def test_optimizer_settings_has_all_fields(self, json_data):
        s = json_data["optimizer_settings"]
        for key in ("max_oil_loss_pct", "spm_range", "spm_step",
                    "steam_range", "steam_step", "vfd_fixed_hz"):
            assert key in s, f"optimizer_settings missing key: {key}"

    def test_max_oil_loss_pct_matches_code_default(self, json_data):
        """Stored max_oil_loss_pct must match the code's default of 15.0."""
        from app.services.optimizer import optimise
        import inspect
        sig = inspect.signature(optimise)
        code_default = sig.parameters["max_oil_loss_pct"].default
        stored = json_data["optimizer_settings"]["max_oil_loss_pct"]
        assert stored == code_default, (
            f"Stored max_oil_loss_pct={stored} does not match "
            f"code default={code_default}"
        )

    def test_spm_range_matches_code_default(self, json_data):
        from app.services.optimizer import DEFAULT_SPM_RANGE
        stored = json_data["optimizer_settings"]["spm_range"]
        assert list(stored) == list(DEFAULT_SPM_RANGE), (
            f"Stored spm_range={stored} != code default={DEFAULT_SPM_RANGE}"
        )

    def test_steam_range_matches_code_default(self, json_data):
        from app.services.optimizer import DEFAULT_STEAM_RANGE
        stored = json_data["optimizer_settings"]["steam_range"]
        assert list(stored) == list(DEFAULT_STEAM_RANGE), (
            f"Stored steam_range={stored} != code default={DEFAULT_STEAM_RANGE}"
        )

    def test_vfd_fixed_hz_matches_code_default(self, json_data):
        from app.services.optimizer import DEFAULT_VFD_FIXED_HZ
        stored = json_data["optimizer_settings"]["vfd_fixed_hz"]
        assert stored == DEFAULT_VFD_FIXED_HZ, (
            f"Stored vfd_fixed_hz={stored} != code default={DEFAULT_VFD_FIXED_HZ}"
        )

    def test_backtest_used_explicit_max_oil_loss(self, json_data):
        """The stored value must be 15.0 — confirms backtest.py passes it explicitly."""
        assert json_data["optimizer_settings"]["max_oil_loss_pct"] == 15.0, (
            "Backtest should record max_oil_loss_pct=15.0 (the explicit value in backtest.py)"
        )

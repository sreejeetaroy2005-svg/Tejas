"""Backtest: do Tejas recommendations beat the recorded baseline?

Replays 180 days of bgw_01_daily.csv through the same simulator used by
the optimizer, comparing two arms:

  Baseline  — the recorded SPM / steam settings as-they-were.
  Tejas     — the optimizer is run on each day's state; its recommended
              SPM / steam are then evaluated by the same simulator.

Both arms pass their settings through the SAME simulate_next_day() function,
so the comparison is symmetric and no parameter is tuned in Tejas' favour.

Key limitation (stated explicitly in the output JSON)
-----------------------------------------------------
The optimizer's objective function IS the simulator, so Tejas can never
appear worse on simulated metrics than the baseline — both arms are scored
by the same deterministic model that the optimizer already knows.  Any
improvement shown here is within-model and optimistic; real field behaviour
would differ because the simulator is a simplified physics approximation,
not a calibrated field model.  This is a proof-of-concept, not a field trial.

Usage:
    cd backend
    python scripts/backtest.py

Outputs:
    data/backtest_results.json
    ../docs/img/backtest.png
"""

import json
import os
import sys
import warnings

# Suppress sklearn joblib parallel warnings — they fire per-tree per optimise()
# call (180 days × 300 trees = 54,000 lines) and swamp the terminal.
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", category=UserWarning, module="xgboost")

import numpy as np
import pandas as pd

# Make sure we can import app modules even when run from scripts/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.simulator import simulate_next_day
from app.services.optimizer import (
    optimise,
    DEFAULT_SPM_RANGE,
    DEFAULT_SPM_STEP,
    DEFAULT_STEAM_RANGE,
    DEFAULT_STEAM_STEP,
    DEFAULT_VFD_FIXED_HZ,
)

# ---------------------------------------------------------------------------
# Optimizer settings used in this backtest run — recorded in the output JSON
# so the stored file is self-documenting and tests can verify consistency.
# ---------------------------------------------------------------------------
BACKTEST_MAX_OIL_LOSS_PCT: float = 15.0  # matches optimise() default

BACKTEST_OPTIMIZER_SETTINGS = {
    "max_oil_loss_pct":   BACKTEST_MAX_OIL_LOSS_PCT,
    "spm_range":          list(DEFAULT_SPM_RANGE),
    "spm_step":           DEFAULT_SPM_STEP,
    "steam_range":        list(DEFAULT_STEAM_RANGE),
    "steam_step":         DEFAULT_STEAM_STEP,
    "vfd_fixed_hz":       DEFAULT_VFD_FIXED_HZ,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_PATH   = os.path.join(_SCRIPT_DIR, "..", "data", "bgw_01_daily.csv")
_OUT_JSON    = os.path.join(_SCRIPT_DIR, "..", "data", "backtest_results.json")
_OUT_IMG     = os.path.join(_SCRIPT_DIR, "..", "..", "docs", "img", "backtest.png")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cycle_prod_progress(df: pd.DataFrame) -> pd.Series:
    """Fraction (0–1) through the production stage for each row.

    Uses days_since_steam_injection divided by the max value within that
    CSS cycle.  Clamped to [0, 1].  Rows in injection/soak stages use 0.0
    because the production decline factor is irrelevant there (oil_bpd=0).
    """
    max_per_cycle = df.groupby("css_cycle_no")["days_since_steam_injection"].transform("max")
    # Avoid division by zero for single-day cycles
    max_per_cycle = max_per_cycle.replace(0, 1)
    progress = (df["days_since_steam_injection"] / max_per_cycle).clip(0.0, 1.0)
    # Injection rows: progress is meaningless for production decline, zero it
    progress = progress.where(df["css_stage"] == "production", 0.0)
    return progress


def _eval_day(row: pd.Series, spm: float, steam: float, progress: float) -> dict:
    """Evaluate one day's settings through simulate_next_day.

    Returns the simulator output dict.
    steam is only used for SOR estimation during injection; for non-injection
    days the simulator ignores it.
    """
    steam_arg = steam if (row["css_stage"] == "injection" and steam > 0) else None
    inj_pressure = (
        float(row["injection_pressure_psi"])
        if row["css_stage"] == "injection" and pd.notna(row["injection_pressure_psi"])
        else None
    )
    return simulate_next_day(
        current_temp_c       = float(row["reservoir_temperature_c"]),
        css_stage            = str(row["css_stage"]),
        cycle_prod_progress  = float(progress),
        spm                  = float(spm),
        vfd_hz               = float(row["vfd_frequency_hz"]),
        current_sor          = float(row["sor"]),
        steam_volume_tonnes  = steam_arg,
        injection_pressure_psi = inj_pressure,
    )


def _tejas_settings(row: pd.Series, progress: float) -> tuple[float, float]:
    """Run the optimizer on this day's state; return (recommended_spm, recommended_steam)."""
    result = optimise(
        current_temp_c       = float(row["reservoir_temperature_c"]),
        css_stage            = str(row["css_stage"]),
        cycle_prod_progress  = float(progress),
        current_spm          = float(row["spm"]),
        current_vfd          = float(row["vfd_frequency_hz"]),
        current_sor          = float(row["sor"]),
        current_oil_bpd      = float(row["oil_bpd"]),
        current_risk_score   = float(row["rod_floating_risk_score"]),
        current_viscosity_cp = float(row["viscosity_cp"]),
        max_oil_loss_pct     = BACKTEST_MAX_OIL_LOSS_PCT,  # explicit, not default
    )
    best = result["best_option"]
    return float(best["spm"]), float(best["steam_volume_tonnes"])


# ---------------------------------------------------------------------------
# Main backtest loop
# ---------------------------------------------------------------------------

def run_backtest(verbose: bool = True) -> dict:
    """Run the full 180-day backtest.  Returns the results dict."""
    df = pd.read_csv(_DATA_PATH)
    progress = _cycle_prod_progress(df)

    baseline_rows: list[dict] = []
    tejas_rows:    list[dict] = []

    n = len(df)
    for i, (_, row) in enumerate(df.iterrows()):
        if verbose and i % 20 == 0:
            print(f"  Day {i+1}/{n}  {row['date']}  stage={row['css_stage']}")

        prog = float(progress.iloc[i])

        # --- Baseline: recorded settings ---
        b_out = _eval_day(row, spm=row["spm"], steam=row["steam_volume_tonnes"], progress=prog)
        baseline_rows.append({
            "date":       str(row["date"]),
            "css_stage":  str(row["css_stage"]),
            "spm_used":   round(float(row["spm"]), 2),
            "steam_used": round(float(row["steam_volume_tonnes"]), 1),
            **{k: b_out[k] for k in ("oil_bpd","energy_kwh","sor","risk_score","risk_label")},
        })

        # --- Tejas: optimizer-recommended settings, re-evaluated by same simulator ---
        t_spm, t_steam = _tejas_settings(row, prog)
        t_out = _eval_day(row, spm=t_spm, steam=t_steam, progress=prog)
        tejas_rows.append({
            "date":       str(row["date"]),
            "css_stage":  str(row["css_stage"]),
            "spm_used":   round(t_spm, 2),
            "steam_used": round(t_steam, 1),
            **{k: t_out[k] for k in ("oil_bpd","energy_kwh","sor","risk_score","risk_label")},
        })

    # ---------------------------------------------------------------------------
    # Aggregate metrics
    # ---------------------------------------------------------------------------
    def agg(rows: list[dict]) -> dict:
        risk_scores = [r["risk_score"] for r in rows]
        labels      = [r["risk_label"]  for r in rows]
        oil         = [r["oil_bpd"]     for r in rows]
        energy      = [r["energy_kwh"]  for r in rows]
        sor_vals    = [r["sor"]          for r in rows if r["sor"] > 0]
        return {
            "high_risk_days":   int(sum(1 for l in labels if l == "High")),
            "medium_risk_days": int(sum(1 for l in labels if l == "Medium")),
            "low_risk_days":    int(sum(1 for l in labels if l == "Low")),
            "avg_risk_score":   round(float(np.mean(risk_scores)), 2),
            "total_oil_bbl":    round(float(sum(oil)), 1),
            "total_energy_kwh": round(float(sum(energy)), 1),
            "avg_sor":          round(float(np.mean(sor_vals)), 4) if sor_vals else 0.0,
        }

    b_agg = agg(baseline_rows)
    t_agg = agg(tejas_rows)

    # Delta (Tejas minus Baseline; negative = improvement for risk/energy/SOR)
    delta = {
        "high_risk_days":   t_agg["high_risk_days"]   - b_agg["high_risk_days"],
        "avg_risk_score":   round(t_agg["avg_risk_score"]   - b_agg["avg_risk_score"],   2),
        "total_oil_bbl":    round(t_agg["total_oil_bbl"]    - b_agg["total_oil_bbl"],    1),
        "total_energy_kwh": round(t_agg["total_energy_kwh"] - b_agg["total_energy_kwh"], 1),
        "avg_sor":          round(t_agg["avg_sor"]          - b_agg["avg_sor"],          4),
    }

    # SPM variation diagnostics
    from collections import Counter
    t_spm_vals = [r["spm_used"] for r in tejas_rows]
    spm_counts = Counter(t_spm_vals)
    spm_min = round(float(min(t_spm_vals)), 2)
    spm_max = round(float(max(t_spm_vals)), 2)
    spm_mean = round(float(sum(t_spm_vals) / len(t_spm_vals)), 2)
    spm_unique = sorted(spm_counts.keys())
    spm_at_minimum = int(spm_counts.get(spm_min, 0))

    results = {
        "method": (
            "Both arms evaluated with the same simulate_next_day() function. "
            "Baseline uses recorded CSV settings. Tejas arm calls optimise() "
            "on each day's state and re-evaluates the recommended settings with "
            "the same simulator."
        ),
        "limitation": (
            "The optimizer's objective function IS the simulator, so Tejas "
            "cannot appear worse on simulated metrics. Any improvement is "
            "within-model and optimistic — not a real field result. "
            "All data is synthetic."
        ),
        "energy_note": (
            f"SPM now affects production (min of reservoir inflow and pump capacity). "
            f"The optimizer chooses SPM={spm_min}-{spm_max} (mean {spm_mean}). "
            f"On {spm_at_minimum}/{n} days it still picks SPM={spm_min} — these are "
            f"cold high-viscosity days where reservoir inflow is already low and the "
            f"pump is never the bottleneck at any SPM. "
            f"On hotter days it raises SPM to avoid oil loss from pump-limitation. "
            f"The energy reduction is real within the model but optimistic as a "
            f"field prediction."
        ),
        "spm_diagnostics": {
            "min": spm_min,
            "max": spm_max,
            "mean": spm_mean,
            "unique_values": spm_unique,
            "days_at_minimum_spm": spm_at_minimum,
            "distribution": {str(k): int(v) for k, v in sorted(spm_counts.items())},
        },
        "optimizer_settings": BACKTEST_OPTIMIZER_SETTINGS,
        "date_range":   {"start": str(df["date"].iloc[0]), "end": str(df["date"].iloc[-1])},
        "n_days":       n,
        "assumptions": {
            "cycle_prod_progress": "days_since_steam_injection / max(days_since_steam_injection per cycle), clamped 0-1, zero on non-production days",
            "vfd":                 "Both arms use the recorded vfd_frequency_hz (optimizer holds VFD fixed at 42 Hz during grid search but the evaluation call uses the row's actual VFD)",
            "injection_pressure":  "Passed to simulator only on injection days; NaN rows treated as None",
        },
        "baseline":  b_agg,
        "tejas":     t_agg,
        "delta_tejas_minus_baseline": delta,
        "daily_baseline": baseline_rows,
        "daily_tejas":    tejas_rows,
    }
    return results


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def save_chart(results: dict, out_path: str) -> None:
    """Save a before/after bar chart to out_path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    b = results["baseline"]
    t = results["tejas"]

    metrics = [
        ("High-risk days",      b["high_risk_days"],   t["high_risk_days"],   "days",    True),
        ("Avg risk score",      b["avg_risk_score"],   t["avg_risk_score"],   "",        True),
        ("Total energy (kWh)",  b["total_energy_kwh"], t["total_energy_kwh"], "kWh",     True),
        ("Total oil (bbl)",     b["total_oil_bbl"],    t["total_oil_bbl"],    "bbl",     False),
        ("Avg SOR",             b["avg_sor"],           t["avg_sor"],          "t/bbl",   True),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(16, 5))
    fig.suptitle(
        "Tejas Backtest: Baseline vs Recommended Settings\n"
        "(Synthetic data — same simulator used for both arms)",
        fontsize=11, y=1.02,
    )

    for ax, (label, bval, tval, unit, lower_is_better) in zip(axes, metrics):
        colors = []
        for val, ref in [(bval, tval), (tval, bval)]:
            if bval == tval:
                colors.append("#94a3b8")  # slate — no change
            elif lower_is_better:
                colors.append("#ef4444" if val > ref else "#22c55e")
            else:
                colors.append("#22c55e" if val > ref else "#ef4444")

        bars = ax.bar(["Baseline", "Tejas"], [bval, tval], color=colors, width=0.5, edgecolor="white")
        ax.set_title(label, fontsize=9, fontweight="bold")
        ax.set_ylabel(unit, fontsize=8)
        ax.tick_params(axis="both", labelsize=8)

        # Annotate bars
        for bar, val in zip(bars, [bval, tval]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{val:,.1f}" if isinstance(val, float) else str(val),
                ha="center", va="bottom", fontsize=8, fontweight="bold",
            )

        # Padding so annotations aren't clipped
        ax.set_ylim(0, max(bval, tval) * 1.25 + 0.01)

    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Chart saved → {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Tejas Backtest")
    print("=" * 60)

    print("\nRunning 180-day replay …")
    results = run_backtest(verbose=True)

    print("\n--- Baseline ---")
    for k, v in results["baseline"].items():
        print(f"  {k:22s}: {v}")

    print("\n--- Tejas ---")
    for k, v in results["tejas"].items():
        print(f"  {k:22s}: {v}")

    print("\n--- Delta (Tejas − Baseline; negative = improvement for risk/energy/SOR) ---")
    for k, v in results["delta_tejas_minus_baseline"].items():
        sign = "↓" if v < 0 else ("↑" if v > 0 else "=")
        print(f"  {k:22s}: {v:+.2f}  {sign}")

    print(f"\n⚠  Limitation: {results['limitation']}")

    # Save JSON (without the per-day arrays for the summary print; keep them in file)
    os.makedirs(os.path.dirname(os.path.abspath(_OUT_JSON)), exist_ok=True)
    with open(_OUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nJSON saved → {_OUT_JSON}")

    # Save chart
    try:
        save_chart(results, _OUT_IMG)
    except ImportError:
        print("matplotlib not available — skipping chart. pip install matplotlib to enable.")


if __name__ == "__main__":
    main()

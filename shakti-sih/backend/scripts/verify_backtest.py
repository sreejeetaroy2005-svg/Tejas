"""Backtest verification — no model changes, diagnostics only.

Run:  cd backend && python scripts/verify_backtest.py
"""
import json, sys, os, warnings
warnings.filterwarnings("ignore")

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

RESULTS = os.path.join(_BACKEND, "data", "backtest_results.json")
CSV_PATH = os.path.join(_BACKEND, "data", "bgw_01_daily.csv")

# ---------------------------------------------------------------------------
# 1. Per-day oil comparison
# ---------------------------------------------------------------------------
print("=" * 65)
print("1. PER-DAY OIL COMPARISON")
print("=" * 65)

with open(RESULTS) as f:
    r = json.load(f)

baseline = r["daily_baseline"]
tejas    = r["daily_tejas"]

diffs   = []
nonzero = []
for i, (b, t) in enumerate(zip(baseline, tejas)):
    d = round(t["oil_bpd"] - b["oil_bpd"], 4)
    diffs.append(d)
    if abs(d) > 0.05:
        nonzero.append((i + 1, b, t, d))

print(f"  Total days          : {len(diffs)}")
print(f"  Max |difference|    : {max(abs(d) for d in diffs):.4f} bbl/day")
print(f"  Days non-zero(>0.05): {len(nonzero)}")
print(f"  Sum of differences  : {sum(diffs):.4f} bbl")
print()

if nonzero:
    print(f"  {'Day':>4}  {'Date':>12}  {'Stage':>10}  "
          f"{'B_spm':>5}  {'T_spm':>5}  "
          f"{'B_oil':>8}  {'T_oil':>8}  {'diff':>8}")
    for i, b, t, d in nonzero:
        print(f"  {i:>4}  {b['date']:>12}  {b['css_stage']:>10}  "
              f"{b['spm_used']:>5.1f}  {t['spm_used']:>5.1f}  "
              f"{b['oil_bpd']:>8.1f}  {t['oil_bpd']:>8.1f}  {d:>+8.3f}")
else:
    print("  All days: oil difference == 0.0 for every row.")

# ---------------------------------------------------------------------------
# 2. Explain zero delta vs the previous -1.1 bbl
# ---------------------------------------------------------------------------
print()
print("=" * 65)
print("2. WHY IS TOTAL OIL DELTA NOW 0.0?")
print("=" * 65)

# Before the fix: oil_change_pct was computed relative to current_oil_bpd
# (recorded CSV value).  A hot-well day where current_oil_bpd=120 but the
# simulator projected 150+ at current SPM would pass the 15% cap and pick
# a low-SPM candidate that projected 119 — 1 bbl below CSV.  That -1 bbl
# was a pure artefact of the inconsistent baseline.

# Now: oil_change_pct is relative to _oil_baseline = simulator(current_spm).
# Any candidate that used to look like a -1% loss is now at exactly 0% or
# positive, because the comparison is within the same model.

# Verify: check if any Tejas day picks lower SPM than baseline AND has equal oil
differing_spm = [(i+1, b, t) for i,(b,t) in enumerate(zip(baseline, tejas))
                 if abs(t["spm_used"] - b["spm_used"]) > 0.2]
equal_oil_when_spm_differs = [(i,b,t) for i,b,t in differing_spm
                               if abs(t["oil_bpd"] - b["oil_bpd"]) < 0.5]

print(f"  Days where Tejas SPM differs from baseline : {len(differing_spm)}")
print(f"  Of those, days with equal oil (<0.5 diff)  : {len(equal_oil_when_spm_differs)}")
print()
print("  Pre-fix: oil_change_pct used CSV current_oil_bpd as denominator.")
print("  When the simulator projected more oil at current SPM than the CSV")
print("  recorded, a candidate projecting slightly less than that projection")
print("  looked like it violated the 15% cap, so the current-settings candidate")
print("  won — but it added +0 to Tejas and the baseline kept its CSV oil,")
print("  causing a net -1.1 bbl artefact over 180 days.")
print("  Post-fix: both candidates share _oil_baseline = simulator(current_spm),")
print("  so the current-settings candidate is always 0.0% and no artefact occurs.")

# ---------------------------------------------------------------------------
# 3. Chosen-SPM distribution with the cap on
# ---------------------------------------------------------------------------
print()
print("=" * 65)
print("3. CHOSEN-SPM DISTRIBUTION (Tejas arm, cap=15%)")
print("=" * 65)

from collections import Counter
spm_dist = Counter(t["spm_used"] for t in tejas)
spm_diag = r.get("spm_diagnostics", {})
print(f"  From spm_diagnostics: min={spm_diag.get('min')} max={spm_diag.get('max')} "
      f"mean={spm_diag.get('mean')} days_at_min={spm_diag.get('days_at_minimum_spm')}")
print()
for spm, cnt in sorted(spm_dist.items()):
    bar = "#" * (cnt // 2)
    print(f"  SPM={spm:>4.1f} : {cnt:>3d} days  {bar}")

# ---------------------------------------------------------------------------
# 4. BGW-04 diagnostic
# ---------------------------------------------------------------------------
print()
print("=" * 65)
print("4. BGW-04 DIAGNOSTIC")
print("=" * 65)

from app.services.data_service import load_data, get_dataframe
from app.services.simulator import simulate_next_day
from app.services.optimizer import optimise

load_data()
df = get_dataframe()
well_df = df[df["well_id"] == "BGW-04"]
latest  = well_df.iloc[-1]

recorded_oil  = float(latest["oil_bpd"])
recorded_temp = float(latest["reservoir_temperature_c"])
recorded_spm  = float(latest["spm"])
recorded_visc = float(latest["viscosity_cp"])
css_stage     = str(latest["css_stage"])
days_since_inj = int(latest["days_since_steam_injection"])

# Cycle production progress
prod_rows = well_df[
    (well_df["css_cycle_no"] == latest["css_cycle_no"]) &
    (well_df["css_stage"] == "production")
]
total_prod_days = max(len(prod_rows), 1)
prog = days_since_inj / total_prod_days if css_stage == "production" else 0.0

# Simulator projection at current settings
mid_steam = 180.0
proj_current = simulate_next_day(
    current_temp_c=recorded_temp,
    css_stage=css_stage,
    cycle_prod_progress=prog,
    spm=recorded_spm,
    vfd_hz=float(latest["vfd_frequency_hz"]),
    current_sor=float(latest["sor"]),
    steam_volume_tonnes=mid_steam,
)
projected_oil = proj_current["oil_bpd"]

# Optimizer recommendation
result = optimise(
    current_temp_c=recorded_temp,
    css_stage=css_stage,
    cycle_prod_progress=prog,
    current_spm=recorded_spm,
    current_vfd=float(latest["vfd_frequency_hz"]),
    current_sor=float(latest["sor"]),
    current_oil_bpd=recorded_oil,
    current_risk_score=float(latest["rod_floating_risk_score"]),
    current_viscosity_cp=recorded_visc,
)
best = result["best_option"]

pct_gap = (projected_oil - recorded_oil) / max(recorded_oil, 1) * 100

print(f"  Well:              BGW-04 ({latest['well_id']})")
print(f"  Stage:             {css_stage}")
print(f"  Last date:         {latest['date']}")
print(f"  Recorded temp:     {recorded_temp:.1f} °C")
print(f"  Recorded viscosity:{recorded_visc:.0f} cP")
print(f"  Recorded SPM:      {recorded_spm:.2f}")
print(f"  Recorded oil:      {recorded_oil:.1f} bbl/day")
print(f"  Projected oil:     {projected_oil:.1f} bbl/day  ({pct_gap:+.1f}% vs recorded)")
print()
print(f"  Recommended SPM:   {best['spm']:.1f}")
print(f"  Recommended oil:   {best['projected_oil_bpd']:.1f} bbl/day")
print(f"  oil_change_pct:    {best['oil_change_pct']:+.1f}%")
print(f"  Recommended risk:  {best['risk_score']:.1f} ({best['risk_label']})")
print(f"  Current risk:      {latest['rod_floating_risk_score']:.1f} ({latest['rod_floating_risk_label']})")
print()
print(f"  Gap explanation: BGW-04 profile has water_cut=0.60 (vs 0.35 for BGW-01).")
print(f"  The synthetic generator for BGW-04 uses different viscosity/temperature")
print(f"  trajectories and different SPM_SETPOINT. The simulator uses OIL_MAX=220×")
print(f"  (viscosity_factor)×(decline_factor) where viscosity_factor depends on")
print(f"  current temperature — not on water_cut. The recorded CSV oil for BGW-04")
print(f"  was generated with stochastic noise; the deterministic simulator matches")
print(f"  a different (noiseless) trajectory.")

if abs(pct_gap) > 25:
    print(f"\n  ⚠  Gap = {pct_gap:+.1f}% — calibration note will be shown in Overview.")
else:
    print(f"\n  Gap = {pct_gap:+.1f}% — within 25% threshold, no calibration note.")

print()
print("Done.")

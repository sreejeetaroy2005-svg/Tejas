"""Generate synthetic daily data for BGW-02 through BGW-12.

Each well has documented, distinct parameters so the fleet shows
genuinely different operating conditions.  BGW-01 is untouched.

Well profiles
-------------
BGW-02  Shallow, good sand — fast temperature recovery, low risk baseline
BGW-03  Deep well — slow injection, high initial pressure, slow decay
BGW-04  High water-cut field — water cut 0.60 vs 0.35 for BGW-01
BGW-05  Pump wear — fillage cap reduced to 65% (worn valves/plunger)
BGW-06  Early cycle (just started injection) — high temp, low risk
BGW-07  Late production — well nearly depleted, high viscosity, High risk
BGW-08  Gas-prone — gas_mscfd 3× base, erratic fillage
BGW-09  Fluid-pound prone — spm setpoint 9.5, risk elevated
BGW-10  Freshly worked-over — reset cycle, good fillage, low risk
BGW-11  Rod floating risk scenario — SPM too high for current viscosity
BGW-12  Maintenance due — motor current elevated, medium-high risk

All data is explicitly synthetic — not real Oil India field data.

Usage:
    cd backend
    python scripts/generate_fleet.py

Output:
    data/fleet_daily.csv  (11 wells × 180 rows = 1 980 rows)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Shared constants (same physics as synthetic_data_generator.py)
# ---------------------------------------------------------------------------
N_DAYS = 180
START_DATE = datetime(2025, 1, 1)

T_BASELINE = 45.0
T_PEAK = 125.0
PRODUCTION_DECAY_TAU = 10.0
MU_MAX = 8000.0
MU_MIN = 150.0
_MU_K = np.log(MU_MAX / MU_MIN) / (T_PEAK - T_BASELINE)
OIL_MAX_BPD = 220.0

W_FILLAGE   = 0.35
W_VISCOSITY = 0.30
W_SPM_EXCESS = 0.20
W_CURRENT   = 0.15
RISK_LOW_MAX    = 35
RISK_MEDIUM_MAX = 65
OPTIMAL_SPM     = 6.5

# ---------------------------------------------------------------------------
# Well parameter table
# Each dict overrides only the parameters that differ from the BGW-01 baseline.
# ---------------------------------------------------------------------------
WELL_PROFILES = {
    "BGW-02": dict(
        label="Shallow fast-recovery",
        seed=2,
        decay_tau=6.0,          # faster cooling — shallower reservoir
        oil_max=200.0,
        spm_setpoint=8.5,
        water_cut=0.30,
        fillage_cap=98.0,       # good pump
        motor_base=26.0,
        initial_stage="production", # mid-cycle when data starts
        initial_day_in_prod=20,
        inject_days_range=(2, 3),
        soak_days_range=(3, 4),
        prod_days_range=(28, 45),
    ),
    "BGW-03": dict(
        label="Deep high-pressure",
        seed=3,
        decay_tau=14.0,         # slower cooling — deeper reservoir
        oil_max=180.0,
        spm_setpoint=8.0,
        water_cut=0.40,
        fillage_cap=95.0,
        motor_base=30.0,
        initial_stage="production",
        initial_day_in_prod=5,
        inject_days_range=(3, 4),
        soak_days_range=(4, 6),
        prod_days_range=(35, 55),
    ),
    "BGW-04": dict(
        label="High water-cut",
        seed=4,
        decay_tau=10.0,
        oil_max=160.0,
        spm_setpoint=9.0,
        water_cut=0.60,         # ← key differentiator
        fillage_cap=98.0,
        motor_base=29.0,
        initial_stage="production",
        initial_day_in_prod=12,
        inject_days_range=(2, 4),
        soak_days_range=(3, 5),
        prod_days_range=(30, 50),
    ),
    "BGW-05": dict(
        label="Worn pump",
        seed=5,
        decay_tau=10.0,
        oil_max=190.0,
        spm_setpoint=9.0,
        water_cut=0.35,
        fillage_cap=65.0,       # ← worn valves cap fillage
        motor_base=32.0,
        initial_stage="production",
        initial_day_in_prod=30,
        inject_days_range=(2, 4),
        soak_days_range=(3, 6),
        prod_days_range=(30, 55),
    ),
    "BGW-06": dict(
        label="Early cycle / fresh injection",
        seed=6,
        decay_tau=10.0,
        oil_max=220.0,
        spm_setpoint=9.0,
        water_cut=0.33,
        fillage_cap=98.0,
        motor_base=28.0,
        initial_stage="injection", # data starts at injection — hot and fresh
        initial_day_in_prod=0,
        inject_days_range=(2, 4),
        soak_days_range=(3, 6),
        prod_days_range=(30, 55),
    ),
    "BGW-07": dict(
        label="Late depleted production",
        seed=7,
        decay_tau=8.0,          # faster decay — reservoir more depleted
        oil_max=130.0,          # lower max — depleted
        spm_setpoint=9.5,       # operator hasn't reduced SPM
        water_cut=0.50,
        fillage_cap=80.0,
        motor_base=33.0,
        initial_stage="production",
        initial_day_in_prod=45, # deep into production
        inject_days_range=(2, 3),
        soak_days_range=(3, 4),
        prod_days_range=(25, 40),
    ),
    "BGW-08": dict(
        label="Gas-prone",
        seed=8,
        decay_tau=10.0,
        oil_max=200.0,
        spm_setpoint=9.0,
        water_cut=0.35,
        fillage_cap=85.0,
        motor_base=28.0,
        gas_multiplier=3.0,     # ← high gas
        initial_stage="production",
        initial_day_in_prod=8,
        inject_days_range=(2, 4),
        soak_days_range=(3, 6),
        prod_days_range=(30, 55),
    ),
    "BGW-09": dict(
        label="Fluid-pound prone",
        seed=9,
        decay_tau=10.0,
        oil_max=200.0,
        spm_setpoint=9.5,       # SPM intentionally too high → fluid pound
        water_cut=0.35,
        fillage_cap=98.0,
        motor_base=31.0,
        initial_stage="production",
        initial_day_in_prod=15,
        inject_days_range=(2, 4),
        soak_days_range=(3, 6),
        prod_days_range=(30, 55),
    ),
    "BGW-10": dict(
        label="Recently worked-over",
        seed=10,
        decay_tau=9.0,
        oil_max=210.0,
        spm_setpoint=8.5,
        water_cut=0.32,
        fillage_cap=97.0,       # fresh after workover
        motor_base=27.0,
        initial_stage="production",
        initial_day_in_prod=3,  # fresh cycle
        inject_days_range=(2, 4),
        soak_days_range=(4, 6),
        prod_days_range=(35, 55),
    ),
    "BGW-11": dict(
        label="Rod floating risk",
        seed=11,
        decay_tau=9.0,
        oil_max=195.0,
        spm_setpoint=10.0,      # SPM very high vs viscosity → rod floating risk
        water_cut=0.38,
        fillage_cap=90.0,
        motor_base=30.0,
        initial_stage="production",
        initial_day_in_prod=22,
        inject_days_range=(2, 4),
        soak_days_range=(3, 6),
        prod_days_range=(30, 55),
    ),
    "BGW-12": dict(
        label="Maintenance due",
        seed=12,
        decay_tau=10.0,
        oil_max=175.0,
        spm_setpoint=9.0,
        water_cut=0.42,
        fillage_cap=75.0,
        motor_base=36.0,        # elevated motor current → nearing fault
        initial_stage="production",
        initial_day_in_prod=35,
        inject_days_range=(2, 4),
        soak_days_range=(3, 5),
        prod_days_range=(30, 50),
    ),
}


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def _build_schedule(rng, n_days, inject_range, soak_range, prod_range,
                    initial_stage, initial_day_in_prod):
    """Return list of (stage, cycle_no, day_in_stage, days_since_inj) tuples."""
    schedule = []
    cycle_no = 1

    if initial_stage == "production" and initial_day_in_prod > 0:
        # Start mid-production
        days_already = initial_day_in_prod
        prod_total = int(rng.integers(*prod_range, endpoint=True))
        for d in range(days_already, prod_total):
            schedule.append(("production", cycle_no, d,
                             int(rng.integers(*inject_range, endpoint=True)) +
                             int(rng.integers(*soak_range, endpoint=True)) + d))
            if len(schedule) >= n_days:
                return schedule[:n_days]
        cycle_no += 1

    while len(schedule) < n_days:
        inj  = int(rng.integers(*inject_range, endpoint=True))
        soak = int(rng.integers(*soak_range, endpoint=True))
        prod = int(rng.integers(*prod_range, endpoint=True))
        for d in range(inj):
            schedule.append(("injection", cycle_no, d, d))
        for d in range(soak):
            schedule.append(("soak", cycle_no, d, inj + d))
        for d in range(prod):
            schedule.append(("production", cycle_no, d, inj + soak + d))
        cycle_no += 1

    return schedule[:n_days]


def _generate_well(well_id: str, profile: dict) -> pd.DataFrame:
    p = profile
    rng = np.random.default_rng(p["seed"])

    decay_tau       = p.get("decay_tau", 10.0)
    oil_max         = p.get("oil_max", OIL_MAX_BPD)
    spm_set         = p.get("spm_setpoint", 9.0)
    water_cut       = p.get("water_cut", 0.35)
    fillage_cap     = p.get("fillage_cap", 98.0)
    motor_base      = p.get("motor_base", 28.0)
    gas_mult        = p.get("gas_multiplier", 1.0)

    schedule = _build_schedule(
        rng, N_DAYS,
        p.get("inject_days_range", (2, 4)),
        p.get("soak_days_range", (3, 6)),
        p.get("prod_days_range", (30, 55)),
        p.get("initial_stage", "production"),
        p.get("initial_day_in_prod", 0),
    )

    rows = []
    t_state = T_BASELINE
    cum_steam = 0.0
    cum_oil   = 0.0

    for i, (stage, cycle_no, day_in_stage, days_since_inj) in enumerate(schedule):
        date = START_DATE + timedelta(days=i)

        # Temperature
        if stage == "injection":
            step = (T_PEAK - T_BASELINE) / max(p.get("inject_days_range", (2, 4))[1], 1)
            t_state = min(T_PEAK, t_state + step + rng.normal(0, 1.0))
        elif stage == "soak":
            t_state = min(T_PEAK + 3, t_state + rng.normal(0.3, 0.8))
        else:
            t_state = T_BASELINE + (t_state - T_BASELINE) * np.exp(-1.0 / decay_tau)
            t_state += rng.normal(0, 0.6)
        t_state = float(np.clip(t_state, T_BASELINE - 2, T_PEAK + 5))

        mu = float(np.clip(MU_MAX * np.exp(-_MU_K * (t_state - T_BASELINE)),
                           MU_MIN * 0.9, MU_MAX * 1.05))
        mu_norm = float(np.clip((mu - MU_MIN) / (MU_MAX - MU_MIN), 0, 1))

        # Steam
        steam_vol = 0.0
        inj_pressure = None
        steam_quality = None
        if stage == "injection":
            steam_vol     = float(np.clip(rng.normal(180, 20), 100, 260))
            inj_pressure  = float(np.clip(rng.normal(1400, 80), 1000, 1700))
            steam_quality = float(np.clip(rng.normal(0.75, 0.05), 0.6, 0.9))
            cum_steam    += steam_vol

        prod_range_max = p.get("prod_days_range", (30, 55))[1]
        cycle_prog = (day_in_stage / prod_range_max) if stage == "production" else 0.0
        decline    = 1.0 - 0.45 * cycle_prog
        oil_bpd    = 0.0
        if stage != "injection":
            visc_factor = 1.0 - mu_norm
            oil_bpd = float(np.clip(
                oil_max * visc_factor * decline + rng.normal(0, 5),
                5, oil_max))
        cum_oil += oil_bpd

        water_bpd = float(np.clip(
            oil_bpd * (water_cut / (1 - water_cut)) + rng.normal(0, 3), 0, None))
        gas_mscfd = float(np.clip(oil_bpd * 0.4 * gas_mult + rng.normal(0, 4), 0, None))
        sor = float(cum_steam / cum_oil) if cum_oil > 1 else 0.0

        res_pressure = float(np.clip(1800 - 4*(t_state - T_BASELINE) + rng.normal(0, 15), 1200, 2000))

        spm = float(np.clip(spm_set + rng.normal(0, 0.3), 4, 11))
        vfd_hz = float(np.clip(42.0 + rng.normal(0, 1.5), 30, 50))

        spm_excess = max(0.0, spm - OPTIMAL_SPM) if mu_norm > 0.5 else 0.0
        fillage = 96 - 55 * mu_norm - 6 * spm_excess + rng.normal(0, 3)
        fillage = float(np.clip(fillage, 15, fillage_cap))

        fillage_def = max(0.0, (70 - fillage) / 70)
        motor_current = float(np.clip(
            motor_base + 10 * mu_norm + 12 * fillage_def + rng.normal(0, 1.2),
            20, 60))
        rod_load = float(np.clip(45 + 20*mu_norm + 25*fillage_def + rng.normal(0, 2), 30, 110))
        energy_kwh = float(np.clip(9*spm + 0.15*motor_current + rng.normal(0, 2), 20, 140))

        fill_comp = (1 - fillage/100) * 100
        visc_comp = mu_norm * 100
        spm_comp  = min(spm_excess * 15, 100)
        curr_comp = min(max(0, motor_current - 35) * 2.5, 100)
        risk_score = float(np.clip(
            W_FILLAGE*fill_comp + W_VISCOSITY*visc_comp + W_SPM_EXCESS*spm_comp + W_CURRENT*curr_comp,
            0, 100))
        risk_label = "Low" if risk_score <= RISK_LOW_MAX else ("Medium" if risk_score <= RISK_MEDIUM_MAX else "High")

        rows.append({
            "day": i,
            "date": date.strftime("%Y-%m-%d"),
            "well_id": well_id,
            "css_cycle_no": cycle_no,
            "css_stage": stage,
            "days_since_steam_injection": days_since_inj,
            "steam_volume_tonnes": round(steam_vol, 1),
            "injection_pressure_psi": round(inj_pressure, 1) if inj_pressure else None,
            "steam_quality": round(steam_quality, 3) if steam_quality else None,
            "soak_time_days": p.get("soak_days_range", (3, 6))[1] if stage == "soak" else None,
            "reservoir_temperature_c": round(t_state, 2),
            "reservoir_pressure_psi": round(res_pressure, 1),
            "viscosity_cp": round(mu, 1),
            "oil_bpd": round(oil_bpd, 1),
            "water_bpd": round(water_bpd, 1),
            "gas_mscfd": round(gas_mscfd, 1),
            "sor": round(sor, 3),
            "energy_kwh": round(energy_kwh, 1),
            "spm": round(spm, 2),
            "vfd_frequency_hz": round(vfd_hz, 2),
            "motor_current_a": round(motor_current, 2),
            "estimated_fillage_pct": round(fillage, 1),
            "rod_load_kn": round(rod_load, 2),
            "rod_floating_risk_score": round(risk_score, 1),
            "rod_floating_risk_label": risk_label,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dfs = []
    for well_id, profile in WELL_PROFILES.items():
        df = _generate_well(well_id, profile)
        dfs.append(df)
        latest = df.iloc[-1]
        print(f"{well_id} ({profile['label']:30s})  "
              f"stage={latest['css_stage']:10s}  "
              f"risk={latest['rod_floating_risk_label']:6s}  "
              f"oil={latest['oil_bpd']:6.1f}")

    combined = pd.concat(dfs, ignore_index=True)
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "fleet_daily.csv")
    combined.to_csv(out_path, index=False)
    print(f"\nWrote {len(combined)} rows ({len(dfs)} wells) → {os.path.abspath(out_path)}")
    print("All data is synthetic — not real Oil India field data.")


if __name__ == "__main__":
    main()

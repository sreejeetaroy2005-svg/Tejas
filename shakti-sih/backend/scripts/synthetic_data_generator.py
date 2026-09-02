"""
Tejas — Synthetic Data Generator
==================================
Generates 180 days of daily, single-well (BGW-01) synthetic data for the
Tejas digital twin prototype.

This data is SIMULATED and does NOT represent real Oil India field data.
All numeric relationships below are simplified, explainable approximations
chosen to produce a plausible demo story, not validated engineering models.

Physical story encoded here:
  1. Steam injection raises reservoir temperature.
  2. Soak lets heat spread; temperature stays near peak.
  3. During production, temperature decays back toward baseline (heat loss).
  4. Lower temperature -> higher oil viscosity (thicker oil).
  5. Higher viscosity -> lower pump fillage (oil can't flow into the pump
     fast enough) and lower oil production.
  6. Low fillage + high viscosity + unchanged (relatively high) SPM ->
     rod-floating / impact-loading risk rises over the production stage,
     motivating the "reduce SPM" or "start next CSS cycle" recommendation.

Run:
    python scripts/synthetic_data_generator.py

Output:
    backend/data/bgw_01_daily.csv
    docs/assumptions.md (appended with a data-generation summary)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Config / assumptions (kept explicit and tunable on purpose)
# ---------------------------------------------------------------------------

SEED = 42
N_DAYS = 180
START_DATE = datetime(2025, 1, 1)
WELL_ID = "BGW-01"

# CSS cycle timing (days)
INJECTION_DAYS_RANGE = (2, 4)
SOAK_DAYS_RANGE = (3, 6)
PRODUCTION_DAYS_RANGE = (30, 55)

# Temperature model (deg C)
T_BASELINE = 45.0      # cold reservoir temperature before/long after steam
T_PEAK = 125.0         # temperature reached after a full injection stage
PRODUCTION_DECAY_TAU = 10.0  # days; controls how fast temp decays during production
# (tuned so temperature meaningfully approaches baseline before the cycle ends —
#  this is what lets viscosity/fillage/risk visibly worsen late in production,
#  which is the "story" the dashboard needs to tell)

# Viscosity model (cP) — exponential decay with temperature
MU_MAX = 8000.0   # viscosity at baseline (cold) temperature
MU_MIN = 150.0    # viscosity at peak temperature
_MU_K = np.log(MU_MAX / MU_MIN) / (T_PEAK - T_BASELINE)

# Production model
OIL_MAX_BPD = 220.0    # theoretical max oil rate right after a good soak
WATER_CUT_BASE = 0.35  # fraction of liquid that is water, roughly constant

# Pump operating setpoints (operator does NOT proactively change these,
# which is exactly what creates rising risk during late production stage —
# that gap is what the recommendation engine is meant to catch)
SPM_SETPOINT = 9.0          # strokes per minute
VFD_SETPOINT_HZ = 42.0
OPTIMAL_SPM_AT_HIGH_VISCOSITY = 6.5  # what SPM *should* drop to when oil is thick

# Risk scoring weights (demo assumptions — put in config, tune with domain experts)
W_FILLAGE = 0.35
W_VISCOSITY = 0.30
W_SPM_EXCESS = 0.20
W_CURRENT = 0.15

RISK_LOW_MAX = 35
RISK_MEDIUM_MAX = 65

rng = np.random.default_rng(SEED)


def build_cycle_schedule(n_days):
    """Return a list of (stage, cycle_no, day_in_stage, days_since_injection_start)
    for each day 0..n_days-1. Stage is one of 'injection','soak','production'."""
    schedule = []
    day = 0
    cycle_no = 1
    while day < n_days:
        inj = int(rng.integers(*INJECTION_DAYS_RANGE, endpoint=True))
        soak = int(rng.integers(*SOAK_DAYS_RANGE, endpoint=True))
        prod = int(rng.integers(*PRODUCTION_DAYS_RANGE, endpoint=True))

        for d in range(inj):
            schedule.append(("injection", cycle_no, d, d))
        for d in range(soak):
            schedule.append(("soak", cycle_no, d, inj + d))
        for d in range(prod):
            schedule.append(("production", cycle_no, d, inj + soak + d))

        day += inj + soak + prod
        cycle_no += 1

    return schedule[:n_days]


def temperature_for_day(stage, day_in_stage, t_prev, days_since_injection_start):
    """Evolve reservoir temperature one day at a time based on CSS stage."""
    if stage == "injection":
        # Ramp up toward T_PEAK over the injection window
        step = (T_PEAK - T_BASELINE) / max(INJECTION_DAYS_RANGE[1], 1)
        t_new = min(T_PEAK, t_prev + step + rng.normal(0, 1.0))
    elif stage == "soak":
        # Slight further rise then plateau near peak (heat spreading, no more input)
        t_new = t_prev + rng.normal(0.3, 0.8)
        t_new = min(T_PEAK + 3, t_new)
    else:  # production — exponential decay toward baseline
        t_new = T_BASELINE + (t_prev - T_BASELINE) * np.exp(-1.0 / PRODUCTION_DECAY_TAU)
        t_new += rng.normal(0, 0.6)

    return float(np.clip(t_new, T_BASELINE - 2, T_PEAK + 5))


def viscosity_for_temperature(temp_c):
    """Simple explainable exponential decay: hotter oil -> much lower viscosity."""
    mu = MU_MAX * np.exp(-_MU_K * (temp_c - T_BASELINE))
    return float(np.clip(mu, MU_MIN * 0.9, MU_MAX * 1.05))


def normalized_viscosity(mu):
    """0 = thinnest (best case), 1 = thickest (worst case)."""
    return float(np.clip((mu - MU_MIN) / (MU_MAX - MU_MIN), 0, 1))


def main():
    schedule = build_cycle_schedule(N_DAYS)

    rows = []
    t_state = T_BASELINE
    cumulative_steam = 0.0
    cumulative_oil = 0.0

    for i, (stage, cycle_no, day_in_stage, days_since_inj_start) in enumerate(schedule):
        date = START_DATE + timedelta(days=i)

        # --- Temperature & viscosity ---
        t_state = temperature_for_day(stage, day_in_stage, t_state, days_since_inj_start)
        viscosity = viscosity_for_temperature(t_state)
        mu_norm = normalized_viscosity(viscosity)

        # --- CSS-specific fields ---
        steam_volume = 0.0
        injection_pressure = 0.0
        steam_quality = None
        if stage == "injection":
            steam_volume = float(np.clip(rng.normal(180, 20), 100, 260))
            injection_pressure = float(np.clip(rng.normal(1400, 80), 1000, 1700))
            steam_quality = float(np.clip(rng.normal(0.75, 0.05), 0.6, 0.9))
            cumulative_steam += steam_volume

        soak_time_days = SOAK_DAYS_RANGE[1] if stage == "soak" else None

        # --- Production capability driven by viscosity + natural decline ---
        # Natural decline within the production stage (reservoir energy depleting)
        cycle_prod_progress = 0.0
        if stage == "production":
            cycle_prod_progress = day_in_stage / PRODUCTION_DAYS_RANGE[1]
        decline_factor = 1.0 - 0.45 * cycle_prod_progress

        viscosity_factor = 1.0 - mu_norm  # 1 = easy to flow, 0 = very hard to flow
        oil_bpd = 0.0
        if stage != "injection":
            oil_bpd = OIL_MAX_BPD * viscosity_factor * decline_factor
            oil_bpd = float(np.clip(oil_bpd + rng.normal(0, 5), 5, OIL_MAX_BPD))

        water_bpd = float(oil_bpd * (WATER_CUT_BASE / (1 - WATER_CUT_BASE)) + rng.normal(0, 3))
        water_bpd = float(np.clip(water_bpd, 0, None))
        gas_mscfd = float(np.clip(oil_bpd * 0.4 + rng.normal(0, 4), 0, None))

        cumulative_oil += oil_bpd

        # SOR = steam-oil ratio, computed on a trailing basis to avoid divide-by-zero early on
        sor = float(cumulative_steam / cumulative_oil) if cumulative_oil > 1 else 0.0

        reservoir_pressure = float(np.clip(1800 - 4 * (t_state - T_BASELINE) + rng.normal(0, 15), 1200, 2000))

        # --- SRP / pump fields ---
        # Operator does not proactively reduce SPM as viscosity rises — this gap
        # is intentional: it's what the risk engine and optimizer should catch.
        spm = float(np.clip(SPM_SETPOINT + rng.normal(0, 0.3), 6, 11))
        vfd_hz = float(np.clip(VFD_SETPOINT_HZ + rng.normal(0, 1.5), 30, 50))

        # Fillage drops as viscosity rises (oil can't flow into pump fast enough)
        # and drops further if SPM is running faster than the well can supply.
        spm_excess = max(0.0, spm - OPTIMAL_SPM_AT_HIGH_VISCOSITY) if mu_norm > 0.5 else 0.0
        fillage_pct = 96 - (55 * mu_norm) - (6 * spm_excess) + rng.normal(0, 3)
        fillage_pct = float(np.clip(fillage_pct, 15, 98))

        # Motor current and rod load rise with viscosity and spike when fillage is low
        # (fluid pound / impact loading causes current and load spikes)
        fillage_deficit = max(0.0, (70 - fillage_pct) / 70)
        motor_current = 28 + 10 * mu_norm + 12 * fillage_deficit + rng.normal(0, 1.2)
        motor_current = float(np.clip(motor_current, 20, 60))

        rod_load = 45 + 20 * mu_norm + 25 * fillage_deficit + rng.normal(0, 2)
        rod_load = float(np.clip(rod_load, 30, 110))

        energy_kwh = float(np.clip(9 * spm + 0.15 * motor_current + rng.normal(0, 2), 20, 140))

        # --- Rule-based rod-floating risk score (0-100), explainable by construction ---
        fillage_component = (1 - fillage_pct / 100) * 100
        viscosity_component = mu_norm * 100
        spm_component = min(spm_excess * 15, 100)
        current_component = min(max(0, motor_current - 35) * 2.5, 100)

        risk_score = (
            W_FILLAGE * fillage_component
            + W_VISCOSITY * viscosity_component
            + W_SPM_EXCESS * spm_component
            + W_CURRENT * current_component
        )
        risk_score = float(np.clip(risk_score, 0, 100))

        if risk_score <= RISK_LOW_MAX:
            risk_label = "Low"
        elif risk_score <= RISK_MEDIUM_MAX:
            risk_label = "Medium"
        else:
            risk_label = "High"

        rows.append({
            "day": i,
            "date": date.strftime("%Y-%m-%d"),
            "well_id": WELL_ID,
            "css_cycle_no": cycle_no,
            "css_stage": stage,
            "days_since_steam_injection": days_since_inj_start,
            "steam_volume_tonnes": round(steam_volume, 1),
            "injection_pressure_psi": round(injection_pressure, 1) if injection_pressure else None,
            "steam_quality": round(steam_quality, 3) if steam_quality else None,
            "soak_time_days": soak_time_days,
            "reservoir_temperature_c": round(t_state, 2),
            "reservoir_pressure_psi": round(reservoir_pressure, 1),
            "viscosity_cp": round(viscosity, 1),
            "oil_bpd": round(oil_bpd, 1),
            "water_bpd": round(water_bpd, 1),
            "gas_mscfd": round(gas_mscfd, 1),
            "sor": round(sor, 3),
            "energy_kwh": round(energy_kwh, 1),
            "spm": round(spm, 2),
            "vfd_frequency_hz": round(vfd_hz, 2),
            "motor_current_a": round(motor_current, 2),
            "estimated_fillage_pct": round(fillage_pct, 1),
            "rod_load_kn": round(rod_load, 2),
            "rod_floating_risk_score": round(risk_score, 1),
            "rod_floating_risk_label": risk_label,
        })

    df = pd.DataFrame(rows)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bgw_01_daily.csv")
    df.to_csv(out_path, index=False)

    print(f"Wrote {len(df)} rows to {os.path.abspath(out_path)}")
    print("\nStage counts:")
    print(df["css_stage"].value_counts())
    print("\nRisk label counts:")
    print(df["rod_floating_risk_label"].value_counts())
    print("\nSample rows:")
    print(df[["date", "css_stage", "reservoir_temperature_c", "viscosity_cp",
               "oil_bpd", "estimated_fillage_pct", "rod_floating_risk_label"]].head(10))


if __name__ == "__main__":
    main()

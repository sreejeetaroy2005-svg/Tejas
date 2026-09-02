"""Deterministic simulation engine for "what-if" projections.

Uses the same formulas as the synthetic data generator (without random noise)
to project one day forward given current state and operator overrides.

All data is SYNTHETIC DEMONSTRATION DATA — not calibrated to real wells.
"""

import math

from app.services.risk_engine import (
    MU_MAX,
    MU_MIN,
    OPTIMAL_SPM_AT_HIGH_VISCOSITY,
    compute_risk_score,
    risk_contributing_factors,
)

# ---------------------------------------------------------------------------
# Physical model constants (matching synthetic_data_generator.py exactly)
# ---------------------------------------------------------------------------
T_BASELINE = 45.0  # °C — cold reservoir temperature
T_PEAK = 125.0  # °C — temperature after full injection
PRODUCTION_DECAY_TAU = 10.0  # days — exponential decay time constant

# Viscosity model: mu = MU_MAX * exp(-_MU_K * (T - T_BASELINE))
_MU_K = math.log(MU_MAX / MU_MIN) / (T_PEAK - T_BASELINE)

# Production model
OIL_MAX_BPD = 220.0
WATER_CUT_BASE = 0.35

# Pump fillage model
FILLAGE_INTERCEPT = 96.0
FILLAGE_VISCOSITY_COEFF = 55.0
FILLAGE_SPM_COEFF = 6.0

# Motor current model
CURRENT_BASE = 28.0
CURRENT_VISCOSITY_COEFF = 10.0
CURRENT_FILLAGE_COEFF = 12.0

# Energy model
ENERGY_SPM_COEFF = 9.0
ENERGY_CURRENT_COEFF = 0.15

# Injection stage: per-day temperature rise
INJECTION_STEP = (T_PEAK - T_BASELINE) / 4.0

# Soak stage: per-day temperature drift
SOAK_DRIFT = 0.3


def compute_viscosity(temp_c: float) -> float:
    """Viscosity from temperature — exact same formula as the generator."""
    mu = MU_MAX * math.exp(-_MU_K * (temp_c - T_BASELINE))
    return max(MU_MIN * 0.9, min(MU_MAX * 1.05, mu))


def compute_fillage(mu_norm: float, spm: float) -> float:
    """Pump fillage from viscosity normalised and SPM."""
    spm_excess = (
        max(0.0, spm - OPTIMAL_SPM_AT_HIGH_VISCOSITY) if mu_norm > 0.5 else 0.0
    )
    fillage = FILLAGE_INTERCEPT - FILLAGE_VISCOSITY_COEFF * mu_norm - FILLAGE_SPM_COEFF * spm_excess
    return max(15.0, min(98.0, fillage))


def compute_motor_current(mu_norm: float, fillage_pct: float) -> float:
    """Motor current from viscosity and fillage deficit."""
    fillage_deficit = max(0.0, (70 - fillage_pct) / 70)
    current = CURRENT_BASE + CURRENT_VISCOSITY_COEFF * mu_norm + CURRENT_FILLAGE_COEFF * fillage_deficit
    return max(20.0, min(60.0, current))


def compute_energy(spm: float, motor_current_a: float) -> float:
    """Energy consumption from SPM and motor current."""
    energy = ENERGY_SPM_COEFF * spm + ENERGY_CURRENT_COEFF * motor_current_a
    return max(20.0, min(140.0, energy))


def project_temperature(temp_c: float, css_stage: str) -> float:
    """Project one-day-forward reservoir temperature based on CSS stage."""
    if css_stage == "injection":
        t_new = min(T_PEAK, temp_c + INJECTION_STEP)
    elif css_stage == "soak":
        t_new = temp_c + SOAK_DRIFT
    else:  # production — exponential decay toward baseline
        t_new = T_BASELINE + (temp_c - T_BASELINE) * math.exp(-1.0 / PRODUCTION_DECAY_TAU)

    return max(T_BASELINE - 2, min(T_PEAK + 5, t_new))


def simulate_next_day(
    current_temp_c: float,
    css_stage: str,
    cycle_prod_progress: float,
    spm: float,
    vfd_hz: float,
    current_sor: float,
    steam_volume_tonnes: float | None = None,
) -> dict:
    """Project the next day's operating values (deterministic, no noise).

    Args:
        current_temp_c: Current reservoir temperature (°C).
        css_stage: Current CSS stage ("injection", "soak", "production").
        cycle_prod_progress: How far through the production stage (0.0–1.0).
        spm: Strokes per minute (after override).
        vfd_hz: VFD frequency (Hz) — logged but not used in production formula
                (kept for future pump-curve modelling).
        current_sor: Trailing steam-oil ratio from the latest data row.
        steam_volume_tonnes: Override steam volume (only used for SOR estimate
                             during injection).

    Returns:
        Dict with projected values and risk assessment.
    """
    # 1. Temperature
    t_new = project_temperature(current_temp_c, css_stage)

    # 2. Viscosity
    mu = compute_viscosity(t_new)
    mu_norm = max(0.0, min(1.0, (mu - MU_MIN) / (MU_MAX - MU_MIN)))

    # 3. Production
    viscosity_factor = 1.0 - mu_norm
    decline_factor = 1.0 - 0.45 * cycle_prod_progress

    oil_bpd = 0.0
    if css_stage != "injection":
        oil_bpd = OIL_MAX_BPD * viscosity_factor * decline_factor
        oil_bpd = max(5.0, min(OIL_MAX_BPD, oil_bpd))

    water_bpd = max(0.0, oil_bpd * (WATER_CUT_BASE / (1 - WATER_CUT_BASE)))

    # 4. SOR estimate
    if css_stage == "injection" and steam_volume_tonnes and oil_bpd > 0:
        sor = steam_volume_tonnes / oil_bpd
    elif oil_bpd > 0 and current_sor > 0:
        sor = current_sor  # carry forward trailing SOR in production/soak
    else:
        sor = 0.0

    # 5. Pump behaviour
    fillage_pct = compute_fillage(mu_norm, spm)
    motor_current = compute_motor_current(mu_norm, fillage_pct)
    energy_kwh = compute_energy(spm, motor_current)

    # 6. Risk
    risk_score, risk_label = compute_risk_score(fillage_pct, mu, spm, motor_current)
    risk_factors = risk_contributing_factors(fillage_pct, mu, spm, motor_current)

    return {
        "reservoir_temperature_c": round(t_new, 2),
        "viscosity_cp": round(mu, 1),
        "oil_bpd": round(oil_bpd, 1),
        "water_bpd": round(water_bpd, 1),
        "estimated_fillage_pct": round(fillage_pct, 1),
        "motor_current_a": round(motor_current, 2),
        "vfd_frequency_hz": round(vfd_hz, 2),
        "energy_kwh": round(energy_kwh, 1),
        "sor": round(sor, 3),
        "risk_score": risk_score,
        "risk_label": risk_label,
        "risk_factors": risk_factors,
    }

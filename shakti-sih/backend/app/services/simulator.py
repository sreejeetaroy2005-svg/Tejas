"""Deterministic simulation engine for "what-if" projections.

Uses the same formulas as the synthetic data generator (without random noise)
to project one day forward given current state and operator overrides.

SPM → oil production coupling (v2)
------------------------------------
Previously oil production depended only on viscosity and natural decline,
making SPM irrelevant and causing the optimizer to always pick SPM=4.0
(minimum energy with no oil cost).

Now oil is the MINIMUM of two terms:
  1. reservoir_inflow  — what the reservoir can deliver given viscosity/decline
  2. pump_capacity     — what the pump can physically lift at this SPM+fillage

    pump_capacity_bpd = SPM × 1440 min/day × STROKE_VOLUME_BBL × (fillage_pct / 100)

STROKE_VOLUME_BBL derivation (see comment block below).  This means:
  - At high SPM and good fillage, pump_capacity > inflow → reservoir-limited
    (same result as before for high-SPM operation)
  - At low SPM or poor fillage, pump_capacity < inflow → pump-limited
    (oil falls — SPM now has a real cost)

The crossover SPM is approximately 6.5–7.5 depending on viscosity.  At that
point, reducing SPM saves energy but starts leaving oil in the reservoir.
The optimizer must now trade these off genuinely.

VFD modelling note
------------------
The synthetic bgw_01_daily.csv shows near-zero correlation (r = 0.008)
between vfd_frequency_hz and motor_current_a, because the VFD varies only
over a narrow band (38.5–45.7 Hz) in the synthetic data.  The physical
relationship is real: at lower VFD the motor runs slower and draws less
current.  We implement a simple linear adjustment:

    current_vfd_factor = 1 + VFD_CURRENT_HZ_COEFF * (vfd_hz - VFD_NOMINAL_HZ)

where VFD_CURRENT_HZ_COEFF = +0.004 A/Hz and VFD_NOMINAL_HZ = 42 Hz (the
midpoint of the observed range).  At 50 Hz this adds +3.2% to computed
current; at 30 Hz it subtracts −4.8%.  The relationship is documented as
APPROXIMATE — it is not calibrated from real data and should be tuned with
domain experts before any real field deployment.

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

# VFD → motor current: simple linear adjustment around the nominal frequency.
VFD_NOMINAL_HZ = 42.0          # midpoint of observed VFD range
VFD_CURRENT_HZ_COEFF = 0.004   # fraction of current change per Hz above/below nominal

# Injection stage: per-day temperature rise
INJECTION_STEP = (T_PEAK - T_BASELINE) / 4.0
OPTIMAL_INJECTION_PRESSURE = 1400.0

# Soak stage: per-day temperature drift
SOAK_DRIFT = 0.3

# ---------------------------------------------------------------------------
# Pump capacity constants  (makes SPM a genuine production lever)
# ---------------------------------------------------------------------------
#
# STROKE_VOLUME_BBL — barrels displaced per stroke at 100% volumetric efficiency.
#
# bgw_01_daily.csv does not contain stroke_length or bore diameter, so we
# cannot compute this per-row.  We use a single calibrated representative value.
#
# Calibration (not first-principles — stated explicitly):
#   We choose STROKE_VOLUME_BBL so that at the reference operating point
#   (SPM = OPTIMAL_SPM_AT_HIGH_VISCOSITY = 6.5, fillage = 80%) the pump
#   capacity exactly equals OIL_MAX_BPD (220 bbl/day).  This means the pump
#   is never the bottleneck at "optimal" SPM, but becomes limiting when SPM
#   drops significantly below that reference.
#
#     pump_cap = SPM × MINUTES_PER_DAY × STROKE_VOL × (fillage / 100)
#     220 = 6.5 × 1440 × STROKE_VOL × 0.80
#     STROKE_VOL = 220 / (6.5 × 1440 × 0.80)
#     STROKE_VOL = 220 / 7488 = 0.02938 bbl/stroke
#
# Cross-check against pump geometry (plausibility only, not derivation):
#   0.02938 bbl/stroke × 9702 in³/bbl ≈ 285 in³/stroke
#   A 3-inch plunger bore, 40-inch stroke: π/4 × 3² × 40 = 283 in³ — consistent
#   with a small shallow heavy-oil SRP.  The geometry check is approximate;
#   the constant is defined by the calibration equation above, not by the geometry.
#
# Do NOT change this to make the backtest look better.
#
STROKE_VOLUME_BBL = 0.02938   # bbl/stroke — calibrated so pump_cap = OIL_MAX at SPM=6.5, fillage=80%
MINUTES_PER_DAY   = 1440       # 24 × 60

# ---------------------------------------------------------------------------
# Minimum SPM constraint — wax deposition / gas-lock floor
# ---------------------------------------------------------------------------
#
# Physical basis:
#   Heavy crude (viscosity > ~800 cP, typical of late-production BGW-01) has a
#   wax appearance temperature well above reservoir temperature during the
#   cool-down phase of CSS.  At very low pump speeds the fluid residence time
#   in the tubing increases, wax deposits accumulate on the tubing wall, and
#   the pump eventually fails to clear each stroke — a condition called
#   incomplete barrel filling or gas lock when dissolved gas breaks out.
#
#   Industry practice for heavy-oil CSS SRP:  operators typically enforce a
#   minimum of 3–4 SPM to maintain sufficient fluid velocity to prevent wax
#   deposition and to ensure the pump barrel fully clears each stroke.
#   (Reference: Takacs, "Sucker-Rod Pumping Handbook", 2015, Chapter 7;
#   PDHPE course material on heavy-oil artificial lift.)
#
#   This simulator does not model wax deposition or gas-lock directly.
#   Instead it enforces the operational floor as a hard constraint:
#   any call to simulate_next_day() or compute_pump_capacity() with
#   spm < SPM_MIN_OPERATIONAL raises a ValueError.  The optimizer's grid
#   lower bound (DEFAULT_SPM_RANGE) and the API's Pydantic validation
#   (SimulateRequest) must both respect this floor.
#
#   Value chosen: 4.0 SPM — the lower end of the published 3-4 SPM range,
#   rounded to the nearest 0.5 to align with the optimizer's grid step.
#   This is a conservative operational floor, not a performance optimum.
#
SPM_MIN_OPERATIONAL = 4.0  # strokes/min — minimum safe SPM for heavy-oil CSS SRP


def compute_viscosity(temp_c: float) -> float:
    """Viscosity from temperature — exact same formula as the generator."""
    mu = MU_MAX * math.exp(-_MU_K * (temp_c - T_BASELINE))
    return max(MU_MIN * 0.9, min(MU_MAX * 1.05, mu))


def compute_fillage(mu_norm: float, spm: float, fillage_cap: float = 98.0) -> float:
    """Pump fillage from viscosity normalised and SPM.

    fillage_cap (default 98%) models pump condition: worn valves/plunger
    reduce the maximum achievable fillage.  Read from well_params.json.
    """
    spm_excess = (
        max(0.0, spm - OPTIMAL_SPM_AT_HIGH_VISCOSITY) if mu_norm > 0.5 else 0.0
    )
    fillage = FILLAGE_INTERCEPT - FILLAGE_VISCOSITY_COEFF * mu_norm - FILLAGE_SPM_COEFF * spm_excess
    return max(15.0, min(fillage_cap, fillage))


def compute_pump_capacity(spm: float, fillage_pct: float) -> float:
    """Maximum oil the pump can physically lift at this SPM and fillage.

    pump_capacity_bpd = SPM × MINUTES_PER_DAY × STROKE_VOLUME_BBL × (fillage_pct / 100)

    Raises ValueError if spm < SPM_MIN_OPERATIONAL — see SPM_MIN_OPERATIONAL
    docblock for the physical justification (wax deposition / gas-lock floor).
    """
    if spm < SPM_MIN_OPERATIONAL - 1e-9:
        raise ValueError(
            f"spm={spm:.2f} is below the operational minimum "
            f"SPM_MIN_OPERATIONAL={SPM_MIN_OPERATIONAL}.  "
            "Operating below this floor risks wax deposition and gas lock "
            "in heavy-oil CSS wells.  See simulator.py SPM_MIN_OPERATIONAL comment."
        )
    return spm * MINUTES_PER_DAY * STROKE_VOLUME_BBL * (fillage_pct / 100.0)


def compute_motor_current(
    mu_norm: float,
    fillage_pct: float,
    vfd_hz: float = VFD_NOMINAL_HZ,
    motor_base_amps: float = CURRENT_BASE,
) -> float:
    """Motor current from viscosity, fillage deficit, VFD frequency, and motor baseline.

    motor_base_amps varies per well (worn or high-load wells draw more
    baseline current).  Read from well_params.json.
    """
    fillage_deficit = max(0.0, (70 - fillage_pct) / 70)
    base_current = motor_base_amps + CURRENT_VISCOSITY_COEFF * mu_norm + CURRENT_FILLAGE_COEFF * fillage_deficit
    vfd_factor = 1.0 + VFD_CURRENT_HZ_COEFF * (vfd_hz - VFD_NOMINAL_HZ)
    vfd_factor = max(0.80, min(1.20, vfd_factor))
    current = base_current * vfd_factor
    return max(20.0, min(60.0, current))


def compute_energy(spm: float, motor_current_a: float) -> float:
    """Energy consumption from SPM and motor current."""
    energy = ENERGY_SPM_COEFF * spm + ENERGY_CURRENT_COEFF * motor_current_a
    return max(20.0, min(140.0, energy))


def project_temperature(temp_c: float, css_stage: str, injection_pressure_psi: float | None = None) -> float:
    """Project one-day-forward reservoir temperature based on CSS stage."""
    if css_stage == "injection":
        step = INJECTION_STEP
        if injection_pressure_psi is not None:
            # Empirical approximation: optimal heating at ~1400 psi.
            # Diminishing returns/breakthrough at higher pressures, poor penetration at lower.
            diff_norm = (injection_pressure_psi - OPTIMAL_INJECTION_PRESSURE) / 100.0
            multiplier = max(0.4, 1.2 - 0.2 * (diff_norm ** 2))
            step = step * multiplier
        t_new = min(T_PEAK, temp_c + step)
    elif css_stage == "soak":
        t_new = temp_c + SOAK_DRIFT
    else:  # production — exponential decay toward baseline
        t_new = T_BASELINE + (temp_c - T_BASELINE) * math.exp(-1.0 / PRODUCTION_DECAY_TAU)

    return max(T_BASELINE - 2, min(T_PEAK + 5, t_new))


def _project_temperature_with_tau(
    temp_c: float,
    css_stage: str,
    decay_tau: float,
    injection_pressure_psi: float | None = None,
) -> float:
    """Like project_temperature() but uses the supplied decay_tau.

    This is the internal helper called by simulate_next_day() so that
    per-well decay constants are honoured.  The public project_temperature()
    function still uses the BGW-01 module constant for backward compatibility.
    """
    if css_stage == "injection":
        step = INJECTION_STEP
        if injection_pressure_psi is not None:
            diff_norm = (injection_pressure_psi - OPTIMAL_INJECTION_PRESSURE) / 100.0
            multiplier = max(0.4, 1.2 - 0.2 * (diff_norm ** 2))
            step = step * multiplier
        t_new = min(T_PEAK, temp_c + step)
    elif css_stage == "soak":
        t_new = temp_c + SOAK_DRIFT
    else:  # production — use per-well decay_tau
        t_new = T_BASELINE + (temp_c - T_BASELINE) * math.exp(-1.0 / decay_tau)
    return max(T_BASELINE - 2, min(T_PEAK + 5, t_new))


def simulate_next_day(
    current_temp_c: float,
    css_stage: str,
    cycle_prod_progress: float,
    spm: float,
    vfd_hz: float,
    current_sor: float,
    steam_volume_tonnes: float | None = None,
    injection_pressure_psi: float | None = None,
    # ----------------------------------------------------------------
    # Per-well physics parameters (optional — default to BGW-01 values)
    # ----------------------------------------------------------------
    # These are the five parameters that vary across fleet wells.
    # Pass get_well_params(well_id) values here for accurate per-well
    # simulation.  Omitting them preserves exact BGW-01 behaviour.
    oil_max_bpd:     float = OIL_MAX_BPD,
    water_cut:       float = WATER_CUT_BASE,
    decay_tau:       float = PRODUCTION_DECAY_TAU,
    fillage_cap:     float = 98.0,
    motor_base_amps: float = CURRENT_BASE,
    prod_days_max:   int   = 55,
) -> dict:
    """Project the next day's operating values (deterministic, no noise).

    Args:
        current_temp_c: Current reservoir temperature (°C).
        css_stage: Current CSS stage ("injection", "soak", "production").
        cycle_prod_progress: How far through the production stage (0.0–1.0).
        spm: Strokes per minute (after override).
        vfd_hz: VFD frequency (Hz).
        current_sor: Trailing steam-oil ratio from the latest data row.
        steam_volume_tonnes: Override steam volume (only used for SOR estimate
                             during injection).
        injection_pressure_psi: Steam injection pressure (psi).
        oil_max_bpd: Maximum reservoir inflow (bpd). Default: BGW-01 value (220).
        water_cut: Fraction of produced liquid that is water (0–1). Default: 0.35.
        decay_tau: Production cooling time constant (days). Default: BGW-01 value (10).
        fillage_cap: Upper bound on pump fillage (%). Default: 98 (good pump).
        motor_base_amps: Baseline motor current (A). Default: BGW-01 value (28).
        prod_days_max: Denominator for cycle_prod_progress calculation. Must match
            the generator's PRODUCTION_DAYS_RANGE[1] for the well (default 55,
            BGW-01 value). The generator computes cycle_prod_progress as
            days_since_injection / prod_days_range[1] (fixed constant), NOT as
            days_since_injection / observed_cycle_length. Using the wrong value
            here causes systematic under-prediction (D1 bias).

    Returns:
        Dict with projected values and risk assessment.
    """
    # 1. Temperature — use per-well decay_tau for the production cool-down
    t_new = _project_temperature_with_tau(current_temp_c, css_stage, decay_tau, injection_pressure_psi)

    # 2. Viscosity
    mu = compute_viscosity(t_new)
    mu_norm = max(0.0, min(1.0, (mu - MU_MIN) / (MU_MAX - MU_MIN)))

    # 3. Production
    viscosity_factor = 1.0 - mu_norm
    decline_factor = 1.0 - 0.45 * cycle_prod_progress

    oil_bpd = 0.0
    if css_stage != "injection":
        # Reservoir inflow: what the formation can deliver given viscosity + decline
        reservoir_inflow = oil_max_bpd * viscosity_factor * decline_factor
        reservoir_inflow = max(5.0, min(oil_max_bpd, reservoir_inflow))

        # Pump capacity: what the pump can physically lift at this SPM + fillage
        _fillage_for_cap = compute_fillage(mu_norm, spm, fillage_cap=fillage_cap)
        pump_cap = compute_pump_capacity(spm, _fillage_for_cap)

        oil_bpd = min(reservoir_inflow, pump_cap)
        oil_bpd = max(5.0, min(oil_max_bpd, oil_bpd))

    water_bpd = max(0.0, oil_bpd * (water_cut / (1 - water_cut)))

    # 4. SOR estimate
    if css_stage == "injection" and steam_volume_tonnes and oil_bpd > 0:
        sor = steam_volume_tonnes / oil_bpd
    elif oil_bpd > 0 and current_sor > 0:
        sor = current_sor  # carry forward trailing SOR in production/soak
    else:
        sor = 0.0

    # 5. Pump behaviour — use per-well fillage_cap and motor_base_amps
    fillage_pct = compute_fillage(mu_norm, spm, fillage_cap=fillage_cap)
    motor_current = compute_motor_current(mu_norm, fillage_pct, vfd_hz, motor_base_amps=motor_base_amps)
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

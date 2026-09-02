"""Rod-floating risk scoring engine.

Transparent, rule-based weighted score (0-100) for rod-floating / fluid-pound
risk.  Extracted from the synthetic data generator for reuse across the API
(endpoints, simulation, optimization).

All weights and thresholds are demo assumptions — they are NOT derived from
failure data and should be tuned with domain experts for any real deployment.

Formula:
    risk = 0.35 * fillage_component
         + 0.30 * viscosity_component
         + 0.20 * spm_excess_component
         + 0.15 * motor_current_component

Labels: Low ≤ 35, Medium 36–65, High > 65.
"""

# ---------------------------------------------------------------------------
# Risk scoring weights (matching synthetic_data_generator.py exactly)
# ---------------------------------------------------------------------------
W_FILLAGE = 0.35
W_VISCOSITY = 0.30
W_SPM_EXCESS = 0.20
W_CURRENT = 0.15

# Risk label thresholds
RISK_LOW_MAX = 35
RISK_MEDIUM_MAX = 65

# Viscosity normalization bounds (centipoise)
MU_MIN = 150.0
MU_MAX = 8000.0

# Optimal SPM reference for excess calculation
OPTIMAL_SPM_AT_HIGH_VISCOSITY = 6.5


def _normalize_viscosity(viscosity_cp: float) -> float:
    """0 = thinnest (best case), 1 = thickest (worst case)."""
    return max(0.0, min(1.0, (viscosity_cp - MU_MIN) / (MU_MAX - MU_MIN)))


def compute_risk_score(
    fillage_pct: float,
    viscosity_cp: float,
    spm: float,
    motor_current_a: float,
) -> tuple[float, str]:
    """Compute the rod-floating risk score and label.

    Args:
        fillage_pct: Pump fillage percentage (0–100).
        viscosity_cp: Oil viscosity in centipoise.
        spm: Current strokes per minute.
        motor_current_a: Motor current in amps.

    Returns:
        (risk_score, risk_label) — score is 0–100, label is Low/Medium/High.
    """
    mu_norm = _normalize_viscosity(viscosity_cp)

    # SPM excess: only penalises when oil is thick enough to matter
    spm_excess = (
        max(0.0, spm - OPTIMAL_SPM_AT_HIGH_VISCOSITY) if mu_norm > 0.5 else 0.0
    )

    # Component scores (each 0–100)
    fillage_component = (1 - fillage_pct / 100) * 100
    viscosity_component = mu_norm * 100
    spm_component = min(spm_excess * 15, 100)
    current_component = min(max(0, motor_current_a - 35) * 2.5, 100)

    risk_score = (
        W_FILLAGE * fillage_component
        + W_VISCOSITY * viscosity_component
        + W_SPM_EXCESS * spm_component
        + W_CURRENT * current_component
    )
    risk_score = max(0.0, min(100.0, risk_score))

    if risk_score <= RISK_LOW_MAX:
        risk_label = "Low"
    elif risk_score <= RISK_MEDIUM_MAX:
        risk_label = "Medium"
    else:
        risk_label = "High"

    return round(risk_score, 1), risk_label


def risk_contributing_factors(
    fillage_pct: float,
    viscosity_cp: float,
    spm: float,
    motor_current_a: float,
) -> dict[str, float]:
    """Return individual weighted component contributions for explainability.

    Each value is the component score multiplied by its weight, so the
    dict values sum to the total risk score.
    """
    mu_norm = _normalize_viscosity(viscosity_cp)
    spm_excess = (
        max(0.0, spm - OPTIMAL_SPM_AT_HIGH_VISCOSITY) if mu_norm > 0.5 else 0.0
    )

    fillage_component = (1 - fillage_pct / 100) * 100
    viscosity_component = mu_norm * 100
    spm_component = min(spm_excess * 15, 100)
    current_component = min(max(0, motor_current_a - 35) * 2.5, 100)

    return {
        "fillage": round(W_FILLAGE * fillage_component, 1),
        "viscosity": round(W_VISCOSITY * viscosity_component, 1),
        "spm_excess": round(W_SPM_EXCESS * spm_component, 1),
        "motor_current": round(W_CURRENT * current_component, 1),
    }

"""Grid-search optimizer for well operating parameters.

Evaluates combinations of SPM and steam volume across configured safe ranges,
scores each with a composite objective, and returns the best option with a
plain-language explanation.

VFD search note
---------------
The optimizer's grid search no longer iterates over VFD values.  Reason:

1. The synthetic bgw_01_daily.csv shows near-zero correlation (r = 0.008)
   between vfd_frequency_hz and motor_current_a — VFD varies only in a narrow
   band (38.5–45.7 Hz) in the synthetic dataset.
2. The VFD→motor-current relationship added to simulator.py (coefficient 0.004
   A/Hz) is approximate and deliberately small.  Grid-searching 11 VFD values
   per SPM/steam pair would generate thousands of near-duplicate candidates
   that differ only trivially in projected current, wasting search budget and
   implying VFD is a first-class optimisation lever when it isn't — at least
   not in this synthetic regime.
3. The optimizer instead uses a single representative VFD value
   (DEFAULT_VFD_FIXED_HZ = 42.0 Hz, the midpoint of the observed range) for
   all projections.  The best_option result still includes vfd_frequency_hz
   for display; operators should consult actual VFD control guides for real
   adjustments.

Risk score provenance
---------------------
The risk_score in every candidate (and in best_option) comes from
risk_engine.compute_risk_score() — the rule-based formula:

    risk = 0.35 * fillage + 0.30 * viscosity + 0.20 * spm_excess + 0.15 * current

This is a PROXY OBJECTIVE for ranking hypothetical candidates.  Hypothetical
SPM/steam/VFD combinations do not have a real dynacard to feed the ML
classifier.  The risk_source field in BestOption is set to
"rule_based_projection" to make this explicit.

After the best candidate is selected, the optimizer runs the ML classifier
against the well's current observed state (nearest-neighbour card match) and
emits ml_diagnosis_warning if the classifier's current condition disagrees
substantially with the rule-based projection.

All weights, thresholds, and ranges are demo assumptions — not derived from
field data or economic models.
"""

from app.services.simulator import simulate_next_day

# ---------------------------------------------------------------------------
# Search-space defaults (matching generator clipping ranges)
# ---------------------------------------------------------------------------
DEFAULT_SPM_RANGE = (4.0, 10.0)
DEFAULT_SPM_STEP = 0.5

# VFD: fixed representative value — no longer grid-searched (see module docstring)
DEFAULT_VFD_FIXED_HZ = 42.0

DEFAULT_STEAM_RANGE = (100.0, 260.0)
DEFAULT_STEAM_STEP = 20.0

# ---------------------------------------------------------------------------
# Scoring weights — composite = prod - 0.35*sor - 0.25*energy - 0.50*risk
# ---------------------------------------------------------------------------
W_SOR = 0.35
W_ENERGY = 0.25
W_RISK = 0.50

# Normalisation ceilings
OIL_MAX_BPD = 220.0
SOR_CEILING = 15.0  # values above this are clamped to 1.0
ENERGY_CEILING = 140.0

# ML cross-check thresholds
# Conditions that indicate a fault (anything other than Normal)
_FAULT_CONDITIONS = {"Rod Floating", "Fluid Pound", "Gas Interference",
                     "Gas Interference (low confidence)"}
# Rule-based risk below this is considered "projected safe" by the optimizer
_RULE_BASED_LOW_RISK_MAX = 40.0
# ML confidence above this is considered a "high-confidence" diagnosis
_ML_HIGH_CONFIDENCE = 0.65


def _normalise(value: float, ceiling: float) -> float:
    """Clamp value/ceiling to [0, 1]."""
    return max(0.0, min(1.0, value / ceiling))


def composite_score(
    oil_bpd: float,
    sor: float,
    energy_kwh: float,
    risk_score: float,
) -> float:
    """Compute the composite optimisation score.

    Higher is better.  production_score is positive; penalties for SOR,
    energy, and risk are subtracted.

    risk_score is from the rule-based risk_engine formula — a proxy for
    ranking hypothetical candidates (see module docstring).
    """
    prod = _normalise(oil_bpd, OIL_MAX_BPD)
    sor_n = _normalise(sor, SOR_CEILING) if sor > 0 else 0.0
    energy_n = _normalise(energy_kwh, ENERGY_CEILING)
    risk_n = _normalise(risk_score, 100.0)

    return round(prod - W_SOR * sor_n - W_ENERGY * energy_n - W_RISK * risk_n, 4)


def _build_explanation(
    best: dict,
    current_spm: float,
    current_vfd: float,
    current_oil: float,
    current_risk: float,
) -> str:
    """Generate a plain-language explanation of why this option won."""
    parts: list[str] = []

    # Compare SPM
    spm_diff = best["spm"] - current_spm
    if abs(spm_diff) >= 0.3:
        direction = "Increase" if spm_diff > 0 else "Reduce"
        parts.append(
            f"{direction} SPM from {current_spm:.1f} to {best['spm']:.1f}"
        )

    # Note VFD is fixed (not grid-searched)
    parts.append(
        f"VFD held at {DEFAULT_VFD_FIXED_HZ:.0f} Hz (not grid-searched — "
        "see optimizer note for why)"
    )

    # Production improvement
    oil_change = best["projected_oil_bpd"] - current_oil
    if abs(oil_change) > 1.0:
        pct = (oil_change / max(current_oil, 0.1)) * 100
        parts.append(
            f"Projected oil production: {best['projected_oil_bpd']:.1f} bpd "
            f"({'+'if oil_change >=0 else ''}{pct:.0f}% vs current)"
        )

    # Risk improvement (rule-based proxy)
    risk_drop = current_risk - best["risk_score"]
    if risk_drop > 1.0:
        parts.append(
            f"Rule-based risk proxy drops from {current_risk:.1f} ({_risk_label(current_risk)}) "
            f"to {best['risk_score']:.1f} ({best['risk_label']}) [rule-based projection]"
        )
    elif abs(risk_drop) <= 1.0:
        parts.append(
            f"Rule-based risk proxy remains {best['risk_score']:.1f} ({best['risk_label']}) "
            "[rule-based projection]"
        )

    # Key contributors
    factors = best.get("contributing_factors", {})
    top = sorted(factors.items(), key=lambda kv: kv[1], reverse=True)
    if top:
        names = {"fillage": "fillage", "viscosity": "oil viscosity",
                 "spm_excess": "excess SPM", "motor_current": "motor current"}
        top_name = names.get(top[0][0], top[0][0])
        parts.append(f"Largest risk contributor: {top_name} ({top[0][1]:.1f})")

    parts.append(
        f"Composite score: {best['composite_score']:.3f} "
        f"(production - {W_SOR}*SOR - {W_ENERGY}*energy - {W_RISK}*risk_proxy)"
    )
    return ". ".join(parts) + "."


def _risk_label(score: float) -> str:
    if score <= 35:
        return "Low"
    if score <= 65:
        return "Medium"
    return "High"


def _ml_cross_check(
    current_spm: float,
    current_viscosity_cp: float,
    current_oil_bpd: float,
    current_temp_c: float,
    best_risk_score: float,
) -> tuple[str | None, str | None]:
    """Run ML classifier on the well's current state and cross-check against
    the rule-based projected risk score of the best candidate.

    Returns:
        (ml_condition, warning_text) where warning_text is non-None if there
        is a substantial disagreement between the ML diagnosis and the
        rule-based projection.
    """
    try:
        from app.services.dynacard_lookup import get_ml_diagnosis_for_well
        ml = get_ml_diagnosis_for_well(
            spm=current_spm,
            viscosity_cp=current_viscosity_cp,
            oil_bpd=current_oil_bpd,
            reservoir_temperature_c=current_temp_c,
        )
        ml_condition = ml["predicted_condition"]
        ml_confidence = ml["confidence"]

        # Cross-check: does the ML diagnosis agree with the rule-based projection?
        projected_safe = best_risk_score <= _RULE_BASED_LOW_RISK_MAX
        ml_fault = ml_condition in _FAULT_CONDITIONS
        high_confidence = ml_confidence >= _ML_HIGH_CONFIDENCE

        warning = None
        if projected_safe and ml_fault and high_confidence:
            warning = (
                f"⚠ Diagnosis mismatch: the rule-based optimizer projects "
                f"Low risk (score {best_risk_score:.1f}) for the recommended "
                f"operating point, but the ML classifier currently diagnoses "
                f"this well as '{ml_condition}' with {ml_confidence:.0%} "
                f"confidence.  These are different signals: the rule-based "
                f"score reflects hypothetical scalar projections; the ML "
                f"condition is from a real card shape matched to current "
                f"operating state.  Investigate before applying this "
                f"recommendation."
            )
        elif not projected_safe and not ml_fault:
            warning = (
                f"⚠ Diagnosis mismatch: the rule-based optimizer projects "
                f"elevated risk (score {best_risk_score:.1f}) for the best "
                f"operating point, but the ML classifier currently diagnoses "
                f"this well as '{ml_condition}' (no active failure mode).  "
                f"The rule-based formula may be penalising viscosity/fillage "
                f"more than the card shape warrants.  Review conditions before "
                f"applying this recommendation."
            )

        return ml_condition, warning

    except Exception as exc:
        # ML cross-check is best-effort — never block the optimizer result
        return None, None


def optimise(
    current_temp_c: float,
    css_stage: str,
    cycle_prod_progress: float,
    current_spm: float,
    current_vfd: float,
    current_sor: float,
    current_oil_bpd: float,
    current_risk_score: float,
    current_viscosity_cp: float = 4000.0,
    spm_range: tuple[float, float] | None = None,
    vfd_range: tuple[float, float] | None = None,  # kept for API compat; ignored
    steam_range: tuple[float, float] | None = None,
) -> dict:
    """Run grid search and return the best operating point.

    Grid-searches SPM and steam volume only (VFD is fixed at
    DEFAULT_VFD_FIXED_HZ — see module docstring for why VFD is no longer
    grid-searched).

    After selecting the best candidate, runs the ML classifier on the well's
    current observed state and emits ml_diagnosis_warning if the classifier's
    condition disagrees substantially with the rule-based risk projection.

    Args:
        current_viscosity_cp: Current oil viscosity (cP), used for ML
            cross-check.  Defaults to 4000 if not provided by the caller.
        vfd_range: Accepted for backward API compatibility but ignored
            (VFD is no longer grid-searched — see module docstring).

    Returns a dict with best_option, alternatives_evaluated, explanation,
    contributing_factors, ml_diagnosis_warning, and current_ml_condition.
    """
    spm_lo, spm_hi = spm_range or DEFAULT_SPM_RANGE
    steam_lo, steam_hi = steam_range or DEFAULT_STEAM_RANGE

    # VFD fixed at representative value — not grid-searched
    vfd_val = DEFAULT_VFD_FIXED_HZ

    candidates: list[dict] = []

    spm_val = spm_lo
    while spm_val <= spm_hi + 1e-9:
        steam_val = steam_lo
        while steam_val <= steam_hi + 1e-9:
            projected = simulate_next_day(
                current_temp_c=current_temp_c,
                css_stage=css_stage,
                cycle_prod_progress=cycle_prod_progress,
                spm=spm_val,
                vfd_hz=vfd_val,
                current_sor=current_sor,
                steam_volume_tonnes=steam_val,
            )
            score = composite_score(
                oil_bpd=projected["oil_bpd"],
                sor=projected["sor"],
                energy_kwh=projected["energy_kwh"],
                risk_score=projected["risk_score"],
            )
            candidates.append({
                "spm": round(spm_val, 2),
                "vfd_frequency_hz": round(vfd_val, 2),
                "steam_volume_tonnes": round(steam_val, 1),
                "projected_oil_bpd": projected["oil_bpd"],
                "projected_energy_kwh": projected["energy_kwh"],
                "projected_sor": projected["sor"],
                "risk_score": projected["risk_score"],
                "risk_label": projected["risk_label"],
                "risk_source": "rule_based_projection",
                "composite_score": score,
                "contributing_factors": projected["risk_factors"],
            })
            steam_val += DEFAULT_STEAM_STEP
        spm_val += DEFAULT_SPM_STEP

    if not candidates:
        return {"error": "No valid candidates found."}

    # Sort by composite score descending
    candidates.sort(key=lambda c: c["composite_score"], reverse=True)
    best = candidates[0]

    explanation = _build_explanation(
        best=best,
        current_spm=current_spm,
        current_vfd=current_vfd,
        current_oil=current_oil_bpd,
        current_risk=current_risk_score,
    )

    # ML cross-check: compare ML classifier's current diagnosis with the
    # rule-based projected risk of the best candidate
    ml_condition, ml_warning = _ml_cross_check(
        current_spm=current_spm,
        current_viscosity_cp=current_viscosity_cp,
        current_oil_bpd=current_oil_bpd,
        current_temp_c=current_temp_c,
        best_risk_score=best["risk_score"],
    )

    # Production score breakdown for explainability
    prod_factor = round(_normalise(best["projected_oil_bpd"], OIL_MAX_BPD), 3)
    sor_factor = round(
        _normalise(best["projected_sor"], SOR_CEILING) if best["projected_sor"] > 0 else 0.0, 3
    )
    energy_factor = round(_normalise(best["projected_energy_kwh"], ENERGY_CEILING), 3)
    risk_factor = round(_normalise(best["risk_score"], 100.0), 3)

    return {
        "best_option": best,
        "alternatives_evaluated": len(candidates),
        "explanation": explanation,
        "ml_diagnosis_warning": ml_warning,
        "current_ml_condition": ml_condition,
        "score_breakdown": {
            "production_score": prod_factor,
            "sor_penalty": round(W_SOR * sor_factor, 4),
            "energy_penalty": round(W_ENERGY * energy_factor, 4),
            "risk_penalty": round(W_RISK * risk_factor, 4),
            "composite": best["composite_score"],
        },
    }
# ---------------------------------------------------------------------------
# Cycle-level Optimization
# ---------------------------------------------------------------------------

DEFAULT_PRESSURE_RANGE = (1200.0, 1600.0)
DEFAULT_PRESSURE_STEP = 50.0

DEFAULT_SOAK_RANGE = (3, 6)

CUTOFF_MIN_OIL_BPD = 15.0
CUTOFF_MAX_SOR = 0.35

def should_cutoff_production(oil_bpd: float, cumulative_steam: float, cumulative_oil: float, min_oil: float = CUTOFF_MIN_OIL_BPD, max_sor: float = CUTOFF_MAX_SOR) -> bool:
    """Evaluate if a production period should end based on economic thresholds."""
    current_sor = cumulative_steam / cumulative_oil if cumulative_oil > 0 else 0.0
    return oil_bpd < min_oil and current_sor > max_sor

def optimize_css_cycle(
    current_temp_c: float,
    current_spm: float,
    current_vfd: float,
    steam_range: tuple[float, float] | None = None,
    pressure_range: tuple[float, float] | None = None,
    soak_range: tuple[int, int] | None = None,
) -> dict:
    """Optimize a full CSS cycle (injection, soak, and production to cutoff).
    
    Grid-searches steam volume, injection pressure, and soak duration to maximize
    cumulative oil recovery over the cycle, terminating when production becomes
    uneconomic (should_cutoff_production).
    """
    steam_lo, steam_hi = steam_range or DEFAULT_STEAM_RANGE
    pressure_lo, pressure_hi = pressure_range or DEFAULT_PRESSURE_RANGE
    soak_lo, soak_hi = soak_range or DEFAULT_SOAK_RANGE
    
    INJECTION_DAYS = 3
    MAX_PROD_DAYS = 120
    
    candidates = []
    
    steam_val = steam_lo
    while steam_val <= steam_hi + 1e-9:
        pressure_val = pressure_lo
        while pressure_val <= pressure_hi + 1e-9:
            for soak_days in range(soak_lo, soak_hi + 1):
                t_state = current_temp_c
                cum_steam = steam_val
                cum_oil = 0.0
                
                # Injection phase
                for _ in range(INJECTION_DAYS):
                    proj = simulate_next_day(
                        current_temp_c=t_state,
                        css_stage="injection",
                        cycle_prod_progress=0.0,
                        spm=current_spm,
                        vfd_hz=current_vfd,
                        current_sor=0.0,
                        steam_volume_tonnes=steam_val / INJECTION_DAYS,
                        injection_pressure_psi=pressure_val,
                    )
                    t_state = proj["reservoir_temperature_c"]
                    
                # Soak phase
                for _ in range(soak_days):
                    proj = simulate_next_day(
                        current_temp_c=t_state,
                        css_stage="soak",
                        cycle_prod_progress=0.0,
                        spm=current_spm,
                        vfd_hz=current_vfd,
                        current_sor=0.0,
                    )
                    t_state = proj["reservoir_temperature_c"]
                    
                # Production phase
                prod_days = 0
                while prod_days < MAX_PROD_DAYS:
                    # Note: we need an assumed production length for decline calculation
                    progress = prod_days / 55.0 
                    
                    proj = simulate_next_day(
                        current_temp_c=t_state,
                        css_stage="production",
                        cycle_prod_progress=progress,
                        spm=current_spm,
                        vfd_hz=current_vfd,
                        current_sor=cum_steam / cum_oil if cum_oil > 0 else 0.0,
                    )
                    t_state = proj["reservoir_temperature_c"]
                    oil = proj["oil_bpd"]
                    cum_oil += oil
                    prod_days += 1
                    
                    if prod_days > 5 and should_cutoff_production(oil, cum_steam, cum_oil):
                        break
                        
                final_sor = cum_steam / cum_oil if cum_oil > 0 else 0.0
                score = cum_oil - 100 * final_sor # simple objective to rank candidates
                
                candidates.append({
                    "steam_volume_tonnes": round(steam_val, 1),
                    "injection_pressure_psi": round(pressure_val, 1),
                    "soak_time_days": soak_days,
                    "production_days": prod_days,
                    "cumulative_oil_bbl": round(cum_oil, 1),
                    "final_sor": round(final_sor, 3),
                    "cycle_score": round(score, 2),
                    "cutoff_trigger": f"oil < {CUTOFF_MIN_OIL_BPD} and SOR > {CUTOFF_MAX_SOR}"
                })
                
            pressure_val += DEFAULT_PRESSURE_STEP
        steam_val += DEFAULT_STEAM_STEP
        
    if not candidates:
        return {"error": "No valid candidates found."}
        
    candidates.sort(key=lambda c: c["cycle_score"], reverse=True)
    best = candidates[0]
    
    explanation = (
        f"Optimal cycle parameters: {best['steam_volume_tonnes']} tonnes steam at "
        f"{best['injection_pressure_psi']} psi, followed by {best['soak_time_days']} days soak. "
        f"Production should continue for approximately {best['production_days']} days until "
        f"oil rate < {CUTOFF_MIN_OIL_BPD} and SOR > {CUTOFF_MAX_SOR}."
    )
    
    return {
        "best_cycle_option": best,
        "alternatives_evaluated": len(candidates),
        "explanation": explanation,
    }


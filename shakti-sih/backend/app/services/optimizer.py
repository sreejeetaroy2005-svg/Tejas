"""Grid-search optimizer for well operating parameters.

Evaluates combinations of SPM, VFD, and steam volume across configured
safe ranges, scores each with a composite objective, and returns the best
option with a plain-language explanation.

All weights, thresholds, and ranges are demo assumptions — not derived from
field data or economic models.
"""

from app.services.simulator import simulate_next_day

# ---------------------------------------------------------------------------
# Search-space defaults (matching generator clipping ranges)
# ---------------------------------------------------------------------------
DEFAULT_SPM_RANGE = (4.0, 10.0)
DEFAULT_SPM_STEP = 0.5

DEFAULT_VFD_RANGE = (30.0, 50.0)
DEFAULT_VFD_STEP = 2.0

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

    # Compare VFD
    vfd_diff = best["vfd_frequency_hz"] - current_vfd
    if abs(vfd_diff) >= 1.0:
        direction = "Increase" if vfd_diff > 0 else "Reduce"
        parts.append(
            f"{direction} VFD from {current_vfd:.1f} to {best['vfd_frequency_hz']:.1f} Hz"
        )

    # Production improvement
    oil_change = best["projected_oil_bpd"] - current_oil
    if abs(oil_change) > 1.0:
        pct = (oil_change / max(current_oil, 0.1)) * 100
        parts.append(
            f"Projected oil production: {best['projected_oil_bpd']:.1f} bpd "
            f"({'+'if oil_change >=0 else ''}{pct:.0f}% vs current)"
        )

    # Risk improvement
    risk_drop = current_risk - best["risk_score"]
    if risk_drop > 1.0:
        parts.append(
            f"Risk drops from {current_risk:.1f} ({_risk_label(current_risk)}) "
            f"to {best['risk_score']:.1f} ({best['risk_label']})"
        )
    elif abs(risk_drop) <= 1.0:
        parts.append(f"Risk remains {best['risk_score']:.1f} ({best['risk_label']})")

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
        f"(production - {W_SOR}*SOR - {W_ENERGY}*energy - {W_RISK}*risk)"
    )
    return ". ".join(parts) + "."


def _risk_label(score: float) -> str:
    if score <= 35:
        return "Low"
    if score <= 65:
        return "Medium"
    return "High"


def optimise(
    current_temp_c: float,
    css_stage: str,
    cycle_prod_progress: float,
    current_spm: float,
    current_vfd: float,
    current_sor: float,
    current_oil_bpd: float,
    current_risk_score: float,
    spm_range: tuple[float, float] | None = None,
    vfd_range: tuple[float, float] | None = None,
    steam_range: tuple[float, float] | None = None,
) -> dict:
    """Run grid search and return the best operating point.

    Returns a dict with best_option, alternatives_evaluated, explanation,
    and contributing_factors.
    """
    spm_lo, spm_hi = spm_range or DEFAULT_SPM_RANGE
    vfd_lo, vfd_hi = vfd_range or DEFAULT_VFD_RANGE
    steam_lo, steam_hi = steam_range or DEFAULT_STEAM_RANGE

    candidates: list[dict] = []

    spm_val = spm_lo
    while spm_val <= spm_hi + 1e-9:
        vfd_val = vfd_lo
        while vfd_val <= vfd_hi + 1e-9:
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
                    "composite_score": score,
                    "contributing_factors": projected["risk_factors"],
                })
                steam_val += DEFAULT_STEAM_STEP
            vfd_val += DEFAULT_VFD_STEP
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
        "score_breakdown": {
            "production_score": prod_factor,
            "sor_penalty": round(W_SOR * sor_factor, 4),
            "energy_penalty": round(W_ENERGY * energy_factor, 4),
            "risk_penalty": round(W_RISK * risk_factor, 4),
            "composite": best["composite_score"],
        },
    }

"""Fleet router — multi-well aggregation endpoints.

All data is synthetic demonstration data, not real Oil India field data.

GET /api/fleet/priority
    Ranks all wells by urgency using:
      1. risk_score (0-100, higher = more urgent)
      2. 3-day viscosity trend (rising = more urgent)
      3. ml_condition (fault conditions add urgency)
    Returns one plain-English reason per well derived from real CSV values.
    No text is invented — every phrase is built from measured numbers.

GET /api/fleet/summary
    Fleet-level aggregates: total oil, wells per risk level, total energy,
    average risk score.
"""

import logging
from collections import Counter

from fastapi import APIRouter

from app.models import FleetPriorityItem, FleetPriorityResponse, FleetSummaryResponse
from app.services.data_service import get_dataframe

logger = logging.getLogger(__name__)
router = APIRouter(tags=["fleet"])

# ---------------------------------------------------------------------------
# ML diagnosis helper (reused from wells router pattern)
# ---------------------------------------------------------------------------

def _ml_condition_for(latest) -> tuple[str | None, float | None]:
    """Return (condition_label, confidence) for a well's latest state, or (None, None)."""
    try:
        from app.services.dynacard_lookup import get_ml_diagnosis_for_well
        ml = get_ml_diagnosis_for_well(
            spm=float(latest["spm"]),
            viscosity_cp=float(latest["viscosity_cp"]),
            oil_bpd=float(latest["oil_bpd"]),
            reservoir_temperature_c=float(latest["reservoir_temperature_c"]),
        )
        return ml["predicted_condition"], ml["confidence"]
    except Exception as exc:
        logger.debug("ML unavailable for fleet: %s", exc)
        return None, None


# ---------------------------------------------------------------------------
# Urgency scoring
# ---------------------------------------------------------------------------

# Fault conditions treated as urgent regardless of numeric risk score
_FAULT_CONDITIONS = {"Rod Floating", "Fluid Pound", "Gas Interference",
                     "Gas Interference (low confidence)"}

# Per-condition urgency bonus (added to raw risk_score for ranking only)
_CONDITION_BONUS = {
    "Rod Floating": 15.0,
    "Fluid Pound": 12.0,
    "Gas Interference": 8.0,
    "Gas Interference (low confidence)": 4.0,
    "Normal": 0.0,
}


def _viscosity_trend_3d(well_df) -> float:
    """% change in viscosity over the last 3 rows.  Positive = rising."""
    if len(well_df) < 4:
        return 0.0
    recent = float(well_df["viscosity_cp"].iloc[-1])
    prev   = float(well_df["viscosity_cp"].iloc[-4])
    if prev == 0:
        return 0.0
    return round((recent - prev) / prev * 100, 1)


def _urgency_score(risk_score: float, visc_trend_pct: float,
                   condition: str | None) -> float:
    """Composite urgency for fleet ranking (higher = needs attention sooner)."""
    cond_bonus = _CONDITION_BONUS.get(condition or "Normal", 0.0)
    trend_bonus = max(0.0, visc_trend_pct * 0.3)  # rising viscosity adds urgency
    return risk_score + cond_bonus + trend_bonus


def _build_reason(latest, visc_trend_pct: float, condition: str | None,
                  forecast_trend: str) -> str:
    """Build a one-line plain-English reason from real measured values.

    Every word is derived from numbers in the dataset — nothing invented.
    """
    parts: list[str] = []

    risk = float(latest["rod_floating_risk_score"])
    risk_label = str(latest["rod_floating_risk_label"])
    fillage = float(latest["estimated_fillage_pct"])
    spm = float(latest["spm"])
    visc = float(latest["viscosity_cp"])

    if risk_label == "High":
        parts.append(f"Risk {risk:.0f}/100 (High)")
    elif risk_label == "Medium":
        parts.append(f"Risk {risk:.0f}/100 (Medium)")

    if condition and condition in _FAULT_CONDITIONS:
        parts.append(f"classifier: {condition}")

    if abs(visc_trend_pct) >= 5:
        direction = "up" if visc_trend_pct > 0 else "down"
        parts.append(f"viscosity {direction} {abs(visc_trend_pct):.0f}% in 3 days")

    if fillage < 50:
        parts.append(f"fillage {fillage:.0f}% (low)")
    elif fillage < 65:
        parts.append(f"fillage {fillage:.0f}%")

    if forecast_trend == "declining":
        parts.append("forecast declining")

    if not parts:
        if risk_label == "Low":
            parts.append(f"risk {risk:.0f}/100 — monitoring")
        else:
            parts.append(f"spm {spm:.1f}, visc {visc:.0f} cP")

    return "; ".join(parts) + "."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/fleet/priority", response_model=FleetPriorityResponse)
def get_fleet_priority() -> FleetPriorityResponse:
    """Rank all wells by operational urgency.

    Urgency = risk_score + ML-condition bonus + viscosity-trend bonus.
    Returns a one-line reason per well built from real measured values.
    """
    df = get_dataframe()
    well_ids = sorted(df["well_id"].unique())

    items: list[FleetPriorityItem] = []

    for wid in well_ids:
        well_df = df[df["well_id"] == wid].copy()
        latest  = well_df.iloc[-1]

        condition, confidence = _ml_condition_for(latest)
        visc_trend = _viscosity_trend_3d(well_df)
        urgency    = _urgency_score(
            float(latest["rod_floating_risk_score"]), visc_trend, condition
        )

        # Simple forecast trend: compare last row oil to 7-row-ago oil
        forecast_trend = "stable"
        if len(well_df) >= 8:
            recent_oil = float(well_df["oil_bpd"].iloc[-1])
            older_oil  = float(well_df["oil_bpd"].iloc[-8])
            if older_oil > 5 and (recent_oil - older_oil) / older_oil < -0.10:
                forecast_trend = "declining"

        reason = _build_reason(latest, visc_trend, condition, forecast_trend)

        items.append(FleetPriorityItem(
            well_id=str(latest["well_id"]),
            risk_score=float(latest["rod_floating_risk_score"]),
            risk_label=str(latest["rod_floating_risk_label"]),
            urgency_score=round(urgency, 2),
            css_stage=str(latest["css_stage"]),
            days_since_steam_injection=int(latest["days_since_steam_injection"]),
            oil_bpd=float(latest["oil_bpd"]),
            estimated_fillage_pct=float(latest["estimated_fillage_pct"]),
            viscosity_cp=float(latest["viscosity_cp"]),
            viscosity_trend_3d_pct=visc_trend,
            ml_condition=condition,
            ml_confidence=confidence,
            forecast_trend=forecast_trend,
            reason=reason,
        ))

    # Sort: highest urgency first
    items.sort(key=lambda x: x.urgency_score, reverse=True)

    return FleetPriorityResponse(
        wells=items,
        total=len(items),
        data_note="Synthetic demonstration data — not real Oil India field data.",
    )


@router.get("/fleet/summary", response_model=FleetSummaryResponse)
def get_fleet_summary() -> FleetSummaryResponse:
    """Fleet-level aggregate statistics across all wells."""
    df = get_dataframe()
    well_ids = df["well_id"].unique()

    total_oil    = 0.0
    total_energy = 0.0
    risk_counts: dict[str, int] = {"Low": 0, "Medium": 0, "High": 0}
    risk_scores: list[float] = []
    producing    = 0
    injecting    = 0
    soaking      = 0

    for wid in well_ids:
        latest = df[df["well_id"] == wid].iloc[-1]
        total_oil    += float(latest["oil_bpd"])
        total_energy += float(latest["energy_kwh"])
        lbl = str(latest["rod_floating_risk_label"])
        risk_counts[lbl] = risk_counts.get(lbl, 0) + 1
        risk_scores.append(float(latest["rod_floating_risk_score"]))
        stage = str(latest["css_stage"])
        if stage == "production":   producing += 1
        elif stage == "injection":  injecting += 1
        else:                       soaking   += 1

    avg_risk = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0

    return FleetSummaryResponse(
        total_wells=len(well_ids),
        wells_producing=producing,
        wells_injecting=injecting,
        wells_soaking=soaking,
        total_oil_bpd=round(total_oil, 1),
        total_energy_kwh=round(total_energy, 1),
        avg_risk_score=avg_risk,
        wells_high_risk=risk_counts.get("High", 0),
        wells_medium_risk=risk_counts.get("Medium", 0),
        wells_low_risk=risk_counts.get("Low", 0),
        data_note="Synthetic demonstration data — not real Oil India field data.",
    )

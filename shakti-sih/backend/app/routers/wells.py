"""Wells router — endpoints for well listing and status.

All data is synthetic demonstration data, not real Oil India field data.

Diagnosis source policy
-----------------------
GET /api/wells and GET /api/wells/{well_id} now include ML classifier output
alongside the rule-based risk score from the CSV.  The ML diagnosis is obtained
by nearest-neighbour matching from the synthetic dynacard library against the
well's current operating state (SPM, viscosity, production rate).

The response carries:
  diagnosis_source = "ml_classifier" when the classifier ran successfully.
  diagnosis_source = "rule_based_projection" when it failed (model not loaded,
      etc.) — the rule-based CSV values are still returned in risk_score/label.

Both sources are always present: risk_score/risk_label come from the CSV
(rule-based) and ml_condition/ml_confidence come from the classifier.
They are clearly distinguished so the frontend can label them separately.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models import WellSummary, WellsResponse, DailyRecord, HistoryResponse, ForecastResponse
from app.services.data_service import get_dataframe
from app.services.forecast_service import forecast_7_days

logger = logging.getLogger(__name__)

router = APIRouter(tags=["wells"])

# CSS stage → human-readable status
_STAGE_MAP = {
    "injection": "injecting",
    "soak": "soaking",
    "production": "producing",
}


def _get_ml_diagnosis(latest) -> dict:
    """Run ML classifier on the well's current state.

    Returns a dict of extra kwargs to pass into WellSummary construction.
    Falls back silently to empty dict on any error (model not loaded, etc.).
    """
    try:
        from app.services.dynacard_lookup import get_ml_diagnosis_for_well
        ml = get_ml_diagnosis_for_well(
            spm=float(latest["spm"]),
            viscosity_cp=float(latest["viscosity_cp"]),
            oil_bpd=float(latest["oil_bpd"]),
            reservoir_temperature_c=float(latest["reservoir_temperature_c"]),
        )
        return {
            "ml_condition": ml["predicted_condition"],
            "ml_confidence": ml["confidence"],
            "ml_gi_probability": ml["gi_probability"],
            "diagnosis_source": "ml_classifier",
            "ml_match_note": ml["match_note"],
        }
    except Exception as exc:
        logger.warning("ML diagnosis unavailable for well status: %s", exc)
        return {
            "diagnosis_source": "rule_based_projection",
        }


@router.get("/wells", response_model=WellsResponse)
def list_wells() -> WellsResponse:
    """List all wells with their current top-level status.

    Returns a summary for each well using the most recent day's data
    from the synthetic dataset. Currently only BGW-01 exists.

    The response includes both:
      - risk_score / risk_label  — rule-based formula from the CSV
      - ml_condition / ml_confidence — ML classifier output (diagnosis_source
        is "ml_classifier" when the classifier ran, "rule_based_projection"
        otherwise).

    All data is synthetic demonstration data.
    """
    df = get_dataframe()
    well_ids = sorted(df["well_id"].unique())

    wells = []
    for wid in well_ids:
        well_df = df[df["well_id"] == wid]
        latest = well_df.iloc[-1]

        stage = str(latest["css_stage"])
        ml_kwargs = _get_ml_diagnosis(latest)

        wells.append(
            WellSummary(
                well_id=str(latest["well_id"]),
                well_name=str(latest["well_id"]),
                field="Baghewala",
                status=_STAGE_MAP.get(stage, stage),
                current_css_cycle=int(latest["css_cycle_no"]),
                current_css_stage=stage,
                risk_score=float(latest["rod_floating_risk_score"]),
                risk_label=str(latest["rod_floating_risk_label"]),
                oil_bpd=float(latest["oil_bpd"]),
                reservoir_temperature_c=float(latest["reservoir_temperature_c"]),
                last_updated=str(latest["date"]),
                **ml_kwargs,
            )
        )

    return WellsResponse(wells=wells, total=len(wells))


@router.get("/wells/{well_id}", response_model=WellSummary)
def get_well(well_id: str) -> WellSummary:
    """Get top-level status of a single well.

    The response includes both rule-based risk_score/label and ML classifier
    output.  See GET /api/wells for the diagnosis_source policy.
    """
    df = get_dataframe()
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise HTTPException(status_code=404, detail="Well not found")

    latest = well_df.iloc[-1]
    stage = str(latest["css_stage"])
    ml_kwargs = _get_ml_diagnosis(latest)

    return WellSummary(
        well_id=str(latest["well_id"]),
        well_name=str(latest["well_id"]),
        field="Baghewala",
        status=_STAGE_MAP.get(stage, stage),
        current_css_cycle=int(latest["css_cycle_no"]),
        current_css_stage=stage,
        risk_score=float(latest["rod_floating_risk_score"]),
        risk_label=str(latest["rod_floating_risk_label"]),
        oil_bpd=float(latest["oil_bpd"]),
        reservoir_temperature_c=float(latest["reservoir_temperature_c"]),
        last_updated=str(latest["date"]),
        **ml_kwargs,
    )


@router.get("/wells/{well_id}/history", response_model=HistoryResponse)
def get_well_history(well_id: str, days: int = 90) -> HistoryResponse:
    """Get the last N days of daily records for a single well."""
    df = get_dataframe()
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise HTTPException(status_code=404, detail="Well not found")

    history_df = well_df.tail(days)

    records = []
    for _, row in history_df.iterrows():
        records.append(
            DailyRecord(
                date=str(row["date"]),
                css_stage=str(row["css_stage"]),
                reservoir_temperature_c=float(row["reservoir_temperature_c"]),
                viscosity_cp=float(row["viscosity_cp"]),
                oil_bpd=float(row["oil_bpd"]),
                water_bpd=float(row["water_bpd"]),
                sor=float(row["sor"]),
                energy_kwh=float(row["energy_kwh"]),
                spm=float(row["spm"]),
                vfd_frequency_hz=float(row["vfd_frequency_hz"]),
                motor_current_a=float(row["motor_current_a"]),
                estimated_fillage_pct=float(row["estimated_fillage_pct"]),
                rod_floating_risk_score=float(row["rod_floating_risk_score"]),
                rod_floating_risk_label=str(row["rod_floating_risk_label"]),
            )
        )

    return HistoryResponse(
        well_id=well_id,
        days=days,
        records=records
    )


@router.get("/wells/{well_id}/forecast", response_model=ForecastResponse)
def get_well_forecast(well_id: str, days: int = 7) -> ForecastResponse:
    """Get a 7-day (or N-day) forecast of reservoir temperature and oil production.

    Uses two XGBoost regressors trained on the synthetic dataset.
    Each day's prediction is fed forward recursively as lag input
    for the next day.

    All data is synthetic demonstration data.
    """
    # Validate well exists
    df = get_dataframe()
    if well_id not in df["well_id"].values:
        raise HTTPException(status_code=404, detail="Well not found")

    result = forecast_7_days(well_id, days)
    return ForecastResponse(**result)

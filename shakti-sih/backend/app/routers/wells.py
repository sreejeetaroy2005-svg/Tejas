"""Wells router — endpoints for well listing and status.

All data is synthetic demonstration data, not real Oil India field data.
"""

from fastapi import APIRouter, HTTPException

from app.models import WellSummary, WellsResponse, DailyRecord, HistoryResponse
from app.services.data_service import get_dataframe

router = APIRouter(tags=["wells"])

# CSS stage → human-readable status
_STAGE_MAP = {
    "injection": "injecting",
    "soak": "soaking",
    "production": "producing",
}


@router.get("/wells", response_model=WellsResponse)
def list_wells() -> WellsResponse:
    """List all wells with their current top-level status.

    Returns a summary for each well using the most recent day's data
    from the synthetic dataset. Currently only BGW-01 exists.

    All data is synthetic demonstration data.
    """
    df = get_dataframe()
    well_ids = sorted(df["well_id"].unique())

    wells = []
    for wid in well_ids:
        well_df = df[df["well_id"] == wid]
        latest = well_df.iloc[-1]

        stage = str(latest["css_stage"])
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
            )
        )

    return WellsResponse(wells=wells, total=len(wells))


@router.get("/wells/{well_id}", response_model=WellSummary)
def get_well(well_id: str) -> WellSummary:
    """Get top-level status of a single well."""
    df = get_dataframe()
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise HTTPException(status_code=404, detail="Well not found")
        
    latest = well_df.iloc[-1]
    stage = str(latest["css_stage"])
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

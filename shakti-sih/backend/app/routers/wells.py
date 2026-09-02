"""Wells router — endpoints for well listing and status.

All data is synthetic demonstration data, not real Oil India field data.
"""

from fastapi import APIRouter

from app.models import WellSummary, WellsResponse
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

"""Optimize router — POST /api/optimize/{well_id} for grid-search recommendations.

All data is synthetic demonstration data.
"""

from fastapi import APIRouter, HTTPException

from app.models import BestOption, OptimizeRequest, OptimizeResponse
from app.services.data_service import get_dataframe
from app.services.optimizer import optimise

router = APIRouter(tags=["optimize"])


@router.post("/optimize/{well_id}", response_model=OptimizeResponse)
def optimize_well(well_id: str, req: OptimizeRequest | None = None) -> OptimizeResponse:
    """Find the best operating parameters via grid search.

    Searches across safe ranges of SPM, VFD, and steam volume, scoring
    each candidate with:

        composite = production_score - 0.35*SOR - 0.25*energy - 0.50*risk

    Returns the highest-scoring option with a plain-language explanation
    of why it was chosen.

    Optional body fields let you constrain the search space.  If omitted,
    the full default ranges are used (SPM 4–10, VFD 30–50, steam 100–260).
    """
    df = get_dataframe()

    # Validate well exists
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise HTTPException(status_code=404, detail=f"Well '{well_id}' not found.")

    latest = well_df.iloc[-1]

    current_temp = float(latest["reservoir_temperature_c"])
    css_stage = str(latest["css_stage"])
    current_spm = float(latest["spm"])
    current_vfd = float(latest["vfd_frequency_hz"])
    current_sor = float(latest["sor"])
    current_oil = float(latest["oil_bpd"])
    current_risk = float(latest["rod_floating_risk_score"])

    # Production progress
    cycle_prod_progress = 0.0
    if css_stage == "production":
        day_in_stage = int(latest["days_since_steam_injection"])
        prod_rows = well_df[
            (well_df["css_cycle_no"] == latest["css_cycle_no"])
            & (well_df["css_stage"] == "production")
        ]
        total_prod_days = max(len(prod_rows), 1)
        cycle_prod_progress = day_in_stage / total_prod_days

    result = optimise(
        current_temp_c=current_temp,
        css_stage=css_stage,
        cycle_prod_progress=cycle_prod_progress,
        current_spm=current_spm,
        current_vfd=current_vfd,
        current_sor=current_sor,
        current_oil_bpd=current_oil,
        current_risk_score=current_risk,
        spm_range=req.spm_range if req else None,
        vfd_range=req.vfd_range if req else None,
        steam_range=req.steam_range if req else None,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    best_raw = result["best_option"]

    return OptimizeResponse(
        well_id=well_id,
        current={
            "spm": current_spm,
            "vfd_frequency_hz": current_vfd,
            "steam_volume_tonnes": float(latest["steam_volume_tonnes"]),
            "oil_bpd": current_oil,
            "risk_score": current_risk,
            "risk_label": str(latest["rod_floating_risk_label"]),
            "reservoir_temperature_c": current_temp,
            "css_stage": css_stage,
        },
        best_option=BestOption(**best_raw),
        alternatives_evaluated=result["alternatives_evaluated"],
        score_breakdown=result["score_breakdown"],
        explanation=result["explanation"],
    )

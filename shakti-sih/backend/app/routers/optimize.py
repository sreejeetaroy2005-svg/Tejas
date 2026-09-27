"""Optimize router — POST /api/optimize/{well_id} for grid-search recommendations.

All data is synthetic demonstration data.

Risk score note
---------------
The risk_score in best_option is from the rule-based risk_engine formula
(a proxy objective for ranking hypothetical SPM/steam candidates).  The
optimizer's grid search does NOT run the ML classifier per-candidate — there
is no real dynacard to classify for a hypothetical operating point.

After the best candidate is selected, the optimizer runs the ML classifier
against the well's current observed state and emits ml_diagnosis_warning in
the response if the two systems disagree substantially.  See OptimizeResponse
in models.py for the semantics.
"""

from fastapi import APIRouter, HTTPException

from app.models import BestOption, OptimizeRequest, OptimizeResponse
from app.services.data_service import get_dataframe
from app.services.optimizer import optimise, optimize_css_cycle

router = APIRouter(tags=["optimize"])


@router.post("/optimize/{well_id}", response_model=OptimizeResponse)
def optimize_well(well_id: str, req: OptimizeRequest | None = None) -> OptimizeResponse:
    """Find the best operating parameters via grid search.

    Searches across safe ranges of SPM and steam volume (VFD is fixed at a
    representative value — see optimizer.py for why VFD is no longer
    grid-searched), scoring each candidate with:

        composite = production_score - 0.35*SOR - 0.25*energy - 0.50*risk_proxy

    The risk_proxy is from risk_engine.compute_risk_score() applied to each
    hypothetical candidate.  It is labeled as "rule_based_projection" in the
    response (best_option.risk_source) to distinguish it from the ML-classified
    condition shown on real-well status pages.

    After selecting the best candidate, the optimizer runs the ML classifier
    against the well's current observed state.  If the ML classifier's current
    diagnosis disagrees substantially with the rule-based projection,
    ml_diagnosis_warning will be non-None.

    Returns the highest-scoring option with a plain-language explanation.
    Optional body fields let you constrain the SPM and steam search space.
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
    current_viscosity = float(latest["viscosity_cp"])

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
        current_viscosity_cp=current_viscosity,
        spm_range=req.spm_range if req else None,
        vfd_range=req.vfd_range if req else None,
        steam_range=req.steam_range if req else None,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    # Run multi-day cycle optimization
    cycle_result = optimize_css_cycle(
        current_temp_c=current_temp,
        current_spm=current_spm,
        current_vfd=current_vfd,
        steam_range=req.steam_range if req else None,
    )

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
        ml_diagnosis_warning=result.get("ml_diagnosis_warning"),
        current_ml_condition=result.get("current_ml_condition"),
        cycle_recommendation=cycle_result.get("best_cycle_option"),
    )

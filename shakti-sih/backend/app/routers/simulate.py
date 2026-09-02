"""Simulate router — POST /api/simulate for what-if projections.

All data is synthetic demonstration data.
"""

from fastapi import APIRouter, HTTPException

from app.models import (
    ProjectedValues,
    SimulateRequest,
    SimulateResponse,
)
from app.services.data_service import get_dataframe
from app.services.simulator import simulate_next_day

router = APIRouter(tags=["simulate"])


@router.post("/simulate", response_model=SimulateResponse)
def run_simulation(req: SimulateRequest) -> SimulateResponse:
    """Project one day forward given operator overrides.

    Uses the same deterministic formulas as the synthetic data generator
    (no random noise) to produce reproducible what-if estimates.

    All fields in the request body are optional — omitted fields use the
    well's most recent values from the dataset.

    Input limits are enforced:
    - steam_volume_tonnes: 100–260
    - soak_time_days: 3–6
    - spm: 4.0–10.0
    - vfd_frequency_hz: 30.0–50.0

    Returns projected production, energy, SOR, risk score, and a
    plain-language explanation of the key drivers.
    """
    df = get_dataframe()
    latest = df.iloc[-1]

    # Current state from latest row
    current_temp = float(latest["reservoir_temperature_c"])
    css_stage = str(latest["css_stage"])
    current_spm = float(latest["spm"])
    current_vfd = float(latest["vfd_frequency_hz"])
    current_sor = float(latest["sor"])

    # Compute production progress within the current cycle (0–1)
    cycle_prod_progress = 0.0
    if css_stage == "production":
        day_in_stage = int(latest["days_since_steam_injection"])
        # Estimate total production days from the data
        prod_rows = df[
            (df["well_id"] == latest["well_id"])
            & (df["css_cycle_no"] == latest["css_cycle_no"])
            & (df["css_stage"] == "production")
        ]
        total_prod_days = max(len(prod_rows), 1)
        cycle_prod_progress = day_in_stage / max(total_prod_days, 1)

    # Apply overrides
    spm = req.spm if req.spm is not None else current_spm
    vfd = req.vfd_frequency_hz if req.vfd_frequency_hz is not None else current_vfd
    steam = req.steam_volume_tonnes  # None means not overridden

    # Run simulation
    result = simulate_next_day(
        current_temp_c=current_temp,
        css_stage=css_stage,
        cycle_prod_progress=cycle_prod_progress,
        spm=spm,
        vfd_hz=vfd,
        current_sor=current_sor,
        steam_volume_tonnes=steam,
    )

    # Build explanation
    overrides_applied: dict = {}
    if req.steam_volume_tonnes is not None:
        overrides_applied["steam_volume_tonnes"] = req.steam_volume_tonnes
    if req.soak_time_days is not None:
        overrides_applied["soak_time_days"] = req.soak_time_days
    if req.spm is not None:
        overrides_applied["spm"] = req.spm
    if req.vfd_frequency_hz is not None:
        overrides_applied["vfd_frequency_hz"] = req.vfd_frequency_hz

    explanation_parts: list[str] = []
    if req.spm is not None and req.spm != current_spm:
        direction = "Reduced" if req.spm < current_spm else "Increased"
        explanation_parts.append(
            f"{direction} SPM from {current_spm:.1f} to {req.spm:.1f}"
        )
    if req.vfd_frequency_hz is not None and req.vfd_frequency_hz != current_vfd:
        direction = "Reduced" if req.vfd_frequency_hz < current_vfd else "Increased"
        explanation_parts.append(
            f"{direction} VFD from {current_vfd:.1f} to {req.vfd_frequency_hz:.1f} Hz"
        )

    explanation_parts.append(
        f"Projected oil production: {result['oil_bpd']:.1f} bpd, "
        f"risk score: {result['risk_score']:.1f} ({result['risk_label']})"
    )

    # Top risk contributor
    factors = result["risk_factors"]
    top_factor = max(factors, key=factors.get)
    explanation_parts.append(
        f"Largest risk contributor: {top_factor} ({factors[top_factor]:.1f})"
    )

    return SimulateResponse(
        well_id=str(latest["well_id"]),
        current_stage=css_stage,
        overrides=overrides_applied,
        projected=ProjectedValues(**{
            k: result[k] for k in ProjectedValues.model_fields
        }),
        risk_score=result["risk_score"],
        risk_label=result["risk_label"],
        risk_factors=result["risk_factors"],
        explanation=". ".join(explanation_parts) + ".",
    )

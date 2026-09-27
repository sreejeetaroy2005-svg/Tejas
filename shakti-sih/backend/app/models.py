"""Pydantic request/response models for the Tejas API.

All models use strict typing and are designed for JSON serialization.
All data is synthetic demonstration data.

Diagnosis source tags
---------------------
diagnosis_source = "ml_classifier"
    Risk and condition data come from classify_card() via the trained
    RandomForest, fed a nearest-neighbour card from the synthetic dynacard
    library matched to the well's current operating state.

diagnosis_source = "rule_based_projection"
    Risk score is the rule-based formula from risk_engine.py, used for
    scoring hypothetical (unobserved) SPM/VFD/steam candidates in the
    optimizer's grid search.  This proxy is NOT the same metric as the
    ML-classified condition shown on real-well status pages.
"""

from typing import Optional

from pydantic import BaseModel, Field


class WellSummary(BaseModel):
    """Top-level status of a single well — used by GET /api/wells."""

    well_id: str = Field(..., description="Unique well identifier, e.g. BGW-01")
    well_name: str = Field(..., description="Human-readable well name")
    field: str = Field(..., description="Oil field name")
    status: str = Field(
        ...,
        description="Current operational status: injecting, soaking, or producing",
    )
    current_css_cycle: int = Field(..., description="Current CSS cycle number")
    current_css_stage: str = Field(..., description="Current CSS stage name")
    risk_score: float = Field(
        ..., ge=0, le=100, description="Rod-floating risk score (0–100)"
    )
    risk_label: str = Field(
        ..., description="Risk level: Low, Medium, or High"
    )
    oil_bpd: float = Field(
        ..., ge=0, description="Current oil production rate (barrels per day)"
    )
    reservoir_temperature_c: float = Field(
        ..., description="Current reservoir temperature (°C)"
    )
    last_updated: str = Field(
        ..., description="Date of most recent data point (YYYY-MM-DD)"
    )

    # --- ML classifier fields (present when a dynacard match is available) ---
    ml_condition: Optional[str] = Field(
        default=None,
        description=(
            "Pump condition predicted by the trained ML classifier: "
            "Normal / Rod Floating / Fluid Pound / Gas Interference, "
            "or 'Gas Interference (low confidence)' when GI probability "
            "is below threshold.  None when classifier was not run."
        ),
    )
    ml_confidence: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Classifier confidence for ml_condition (0–1).",
    )
    ml_gi_probability: Optional[float] = Field(
        default=None,
        ge=0,
        le=1,
        description="Raw Gas Interference class probability (0–1).",
    )
    diagnosis_source: str = Field(
        default="rule_based_projection",
        description=(
            "'ml_classifier' — condition from trained RandomForest on a "
            "nearest-neighbour dynacard. "
            "'rule_based_projection' — fallback formula from risk_engine.py."
        ),
    )
    ml_match_note: Optional[str] = Field(
        default=None,
        description="Provenance note describing how the nearest-neighbour card was selected.",
    )


class WellsResponse(BaseModel):
    """Response wrapper for the wells list endpoint."""

    wells: list[WellSummary]
    total: int
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
        description="Disclaimer about the data source",
    )


class DailyRecord(BaseModel):
    """Daily record of a well's parameters."""
    date: str
    css_stage: str
    reservoir_temperature_c: float
    viscosity_cp: float
    oil_bpd: float
    water_bpd: float
    sor: float
    energy_kwh: float
    spm: float
    vfd_frequency_hz: float
    motor_current_a: float
    estimated_fillage_pct: float
    rod_floating_risk_score: float
    rod_floating_risk_label: str


class HistoryResponse(BaseModel):
    """Historical data for a single well."""
    well_id: str
    days: int
    records: list[DailyRecord]
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# POST /api/simulate models
# ---------------------------------------------------------------------------


class SimulateRequest(BaseModel):
    """Override values for a what-if simulation.

    All fields are optional — omitted fields use the well's current values.
    """

    steam_volume_tonnes: float | None = Field(
        None,
        ge=100,
        le=260,
        description="Steam injection volume override (tonnes). Valid range: 100–260.",
    )
    soak_time_days: int | None = Field(
        None,
        ge=3,
        le=6,
        description="Soak duration override (days). Valid range: 3–6.",
    )
    spm: float | None = Field(
        None,
        ge=4.0,
        le=10.0,
        description="Strokes per minute override. Valid range: 4.0–10.0.",
    )
    vfd_frequency_hz: float | None = Field(
        None,
        ge=30.0,
        le=50.0,
        description="VFD frequency override (Hz). Valid range: 30.0–50.0.",
    )


class ProjectedValues(BaseModel):
    """Projected operating values for the next day."""

    reservoir_temperature_c: float
    viscosity_cp: float
    oil_bpd: float
    water_bpd: float
    estimated_fillage_pct: float
    motor_current_a: float
    vfd_frequency_hz: float
    energy_kwh: float
    sor: float


class SimulateResponse(BaseModel):
    """Response from POST /api/simulate."""

    well_id: str
    current_stage: str
    overrides: dict
    projected: ProjectedValues
    risk_score: float = Field(..., ge=0, le=100)
    risk_label: str
    risk_factors: dict[str, float]
    explanation: str
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# POST /api/optimize/{well_id} models
# ---------------------------------------------------------------------------


class OptimizeRequest(BaseModel):
    """Optional constraints for the optimisation grid search."""

    spm_range: tuple[float, float] | None = Field(
        None, description="(min, max) SPM range override"
    )
    vfd_range: tuple[float, float] | None = Field(
        None, description="(min, max) VFD range override"
    )
    steam_range: tuple[float, float] | None = Field(
        None, description="(min, max) steam volume range override"
    )


class BestOption(BaseModel):
    """The highest-scoring operating point from the grid search.

    risk_score and risk_label here are from the rule-based projection formula
    (risk_engine.py), NOT from the ML classifier.  They are used as a proxy
    objective for ranking hypothetical candidates that have no real dynacard.
    See risk_source for the tag that makes this explicit.
    """

    spm: float
    vfd_frequency_hz: float
    steam_volume_tonnes: float
    projected_oil_bpd: float
    projected_energy_kwh: float
    projected_sor: float
    risk_score: float
    risk_label: str
    composite_score: float
    contributing_factors: dict[str, float]
    risk_source: str = Field(
        default="rule_based_projection",
        description=(
            "Always 'rule_based_projection' for grid-search candidates — "
            "the rule-based formula scores hypothetical operating points that "
            "have no real dynacard to classify."
        ),
    )


class CycleRecommendation(BaseModel):
    """The highest-scoring cycle-level operating point."""
    steam_volume_tonnes: float
    injection_pressure_psi: float
    soak_time_days: int
    production_days: int
    cumulative_oil_bbl: float
    final_sor: float
    cutoff_trigger: str

class OptimizeResponse(BaseModel):
    """Response from POST /api/optimize/{well_id}.

    The optimizer's risk_score is a rule-based proxy used to rank hypothetical
    SPM/VFD/steam combinations during grid search.  If the well has a recent
    ML-classified dynacard reading, ml_diagnosis_warning will be non-None when
    the ML classifier's condition disagrees substantially with the rule-based
    projection — e.g. the rule-based score says Low but the ML classifier found
    high-confidence Rod Floating.  Operators should investigate before acting.
    """

    well_id: str
    current: dict
    best_option: BestOption
    alternatives_evaluated: int
    score_breakdown: dict
    explanation: str
    ml_diagnosis_warning: Optional[str] = Field(
        default=None,
        description=(
            "Non-None when the ML classifier's current diagnosis for this well "
            "disagrees substantially with the rule-based risk projection used "
            "by the optimizer.  Operators should investigate before applying "
            "the recommendation."
        ),
    )
    current_ml_condition: Optional[str] = Field(
        default=None,
        description="ML classifier's current condition for this well (if available).",
    )
    cycle_recommendation: Optional[CycleRecommendation] = Field(
        default=None,
        description="Recommended parameters for the next full CSS cycle.",
    )
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# GET /api/wells/{well_id}/forecast models
# ---------------------------------------------------------------------------


class ForecastDay(BaseModel):
    """A single day's forecast values."""

    date: str
    predicted_temperature_c: float
    predicted_oil_bpd: float


class ForecastResponse(BaseModel):
    """Response from GET /api/wells/{well_id}/forecast."""

    well_id: str
    days: int
    temperature_mae: float = Field(
        ...,
        description="Model's test-set MAE for temperature (°C) — for ±uncertainty display",
    )
    production_mae: float = Field(
        ...,
        description="Model's test-set MAE for production (bbl/day) — for ±uncertainty display",
    )
    forecast: list[ForecastDay]
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# GET /api/dynacards/examples models
# ---------------------------------------------------------------------------


class ExampleCard(BaseModel):
    """A single example dynacard for frontend plotting."""

    card_id: str
    well_id: str
    position: list[float]
    load: list[float]
    condition_label: str
    risk_level: str


# ---------------------------------------------------------------------------
# POST /api/dynacards/classify models
# ---------------------------------------------------------------------------


class DynacardClassifyRequest(BaseModel):
    """Request body for classifying a dynamometer card."""

    position: list[float] = Field(..., description="Position values (200-point array)")
    load: list[float] = Field(..., description="Load values (200-point array)")
    spm: float = Field(..., gt=0, description="Strokes per minute")
    stroke_length: float = Field(..., gt=0, description="Stroke length (inches)")
    temperature: float = Field(..., description="Temperature (°F)")
    viscosity: float = Field(..., gt=0, description="Viscosity (cP)")
    fluid_level: float = Field(..., ge=0, description="Fluid level (ft)")
    pump_depth: float = Field(..., gt=0, description="Pump depth (ft)")
    production_rate: float = Field(..., ge=0, description="Production rate (bbl/day)")


class DynacardClassification(BaseModel):
    """Response from POST /api/dynacards/classify."""

    predicted_condition: str = Field(
        ...,
        description=(
            "Predicted condition: Normal, Rod Floating, Fluid Pound, Gas Interference, "
            "or 'Gas Interference (low confidence)' when the model's GI probability is "
            "below the confidence threshold."
        ),
    )
    confidence: float = Field(..., ge=0, le=1, description="Classification confidence (0–1)")
    gi_probability: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description=(
            "Raw predicted probability for Gas Interference class (0–1). "
            "Useful for dashboards even when the top prediction is a different class."
        ),
    )
    top_features: list[str] = Field(..., description="Top 3 most important features for this prediction")
    explanation: str = Field(..., description="Plain-language explanation of the condition")
    recommended_action: str = Field(..., description="Suggested corrective action")

"""Pydantic request/response models for the Tejas API.

All models use strict typing and are designed for JSON serialization.
All data is synthetic demonstration data.
"""

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
    """The highest-scoring operating point from the grid search."""

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


class OptimizeResponse(BaseModel):
    """Response from POST /api/optimize/{well_id}."""

    well_id: str
    current: dict
    best_option: BestOption
    alternatives_evaluated: int
    score_breakdown: dict
    explanation: str
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
        description="Predicted condition: Normal, Rod Floating, Fluid Pound, or Gas Interference",
    )
    confidence: float = Field(..., ge=0, le=1, description="Classification confidence (0–1)")
    top_features: list[str] = Field(..., description="Top 3 most important features for this prediction")
    explanation: str = Field(..., description="Plain-language explanation of the condition")
    recommended_action: str = Field(..., description="Suggested corrective action")

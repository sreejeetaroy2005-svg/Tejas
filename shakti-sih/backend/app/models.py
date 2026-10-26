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
    spm lower bound matches SPM_MIN_OPERATIONAL in simulator.py (4.0 SPM —
    the wax-deposition / gas-lock floor for heavy-oil CSS SRP).
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
        description=(
            "Strokes per minute override. Valid range: 4.0–10.0. "
            "Lower bound is the operational wax-deposition / gas-lock floor "
            "(SPM_MIN_OPERATIONAL in simulator.py)."
        ),
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
    max_oil_loss_pct: float = Field(
        default=15.0,
        ge=0.0,
        le=100.0,
        description=(
            "Maximum acceptable oil production loss relative to current, as a "
            "percentage (0–100).  Candidates whose projected oil is lower than "
            "current by more than this fraction are excluded before ranking.  "
            "Default: 15.0 (allow up to 15% loss).  "
            "Set to 100 to disable the constraint entirely.  "
            "On injection/soak days where current oil_bpd == 0 the constraint "
            "is skipped automatically."
        ),
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
    oil_change_pct: float = Field(
        default=0.0,
        description=(
            "Projected oil change vs the simulator's baseline at current settings, "
            "as a percentage (signed).  Negative = oil loss vs current settings; "
            "positive = oil gain.  The current-settings candidate always has 0.0.  "
            "Zero when _oil_baseline == 0 (injection/soak stage)."
        ),
    )
    is_current_settings: bool = Field(
        default=False,
        description=(
            "True when this option represents keeping the current operating "
            "settings unchanged.  Set when the risk guard or oil-loss cap "
            "caused every other candidate to be rejected."
        ),
    )
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
    oil_constraint_note: Optional[str] = Field(
        default=None,
        description=(
            "Non-None when the oil-loss constraint (max_oil_loss_pct) was active "
            "and affected which candidates were considered, or when the risk guard fired."
        ),
    )
    oil_constraint_active: bool = Field(
        default=False,
        description=(
            "True when the oil-loss constraint excluded at least one candidate "
            "or when no candidate met the constraint threshold."
        ),
    )
    note_type: Optional[str] = Field(
        default=None,
        description=(
            "'oil_cap' when candidates were excluded by the max_oil_loss_pct filter.  "
            "'risk_guard' when the risk guard promoted the current-settings candidate.  "
            "None when neither triggered."
        ),
    )
    current_projected_oil_bpd: float = Field(
        default=0.0,
        description=(
            "The simulator's projected oil production at the current (recorded) SPM "
            "settings.  This is the baseline used for all oil_change_pct comparisons.  "
            "Distinct from current.oil_bpd (the recorded CSV value)."
        ),
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


# ---------------------------------------------------------------------------
# GET /api/backtest models
# ---------------------------------------------------------------------------


class BacktestArm(BaseModel):
    """Aggregate metrics for one arm of the backtest (baseline or Tejas)."""

    high_risk_days: int = Field(..., description="Days with risk_label == 'High'")
    medium_risk_days: int = Field(..., description="Days with risk_label == 'Medium'")
    low_risk_days: int = Field(..., description="Days with risk_label == 'Low'")
    avg_risk_score: float = Field(..., description="Mean risk score across all 180 days")
    total_oil_bbl: float = Field(..., description="Sum of daily oil_bpd across all 180 days (bbl)")
    total_energy_kwh: float = Field(..., description="Sum of daily energy_kwh across all 180 days")
    avg_sor: float = Field(..., description="Mean steam-oil ratio on days where SOR > 0")


class BacktestDelta(BaseModel):
    """Tejas minus Baseline for each headline metric.

    Negative = improvement for risk / energy / SOR.
    Positive = improvement for oil.
    """

    high_risk_days: int
    avg_risk_score: float
    total_oil_bbl: float
    total_energy_kwh: float
    avg_sor: float


class BacktestDailyRow(BaseModel):
    """One day's result for either arm."""

    date: str
    css_stage: str
    spm_used: float
    steam_used: float
    oil_bpd: float
    energy_kwh: float
    sor: float
    risk_score: float
    risk_label: str


class BacktestResponse(BaseModel):
    """Response from GET /api/backtest."""

    method: str = Field(..., description="Plain-English description of the comparison method")
    limitation: str = Field(..., description="Key limitation — both arms scored by the same simulator")
    energy_note: str = Field(
        ...,
        description="SPM variation summary and explanation of energy/oil trade-off.",
    )
    date_range: dict = Field(..., description="{'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}")
    n_days: int = Field(..., description="Number of days replayed (180)")
    assumptions: dict = Field(..., description="Key modelling assumptions")
    spm_diagnostics: dict = Field(
        default_factory=dict,
        description="SPM distribution chosen by optimizer: min, max, mean, distribution per value.",
    )
    optimizer_settings: dict = Field(
        default_factory=dict,
        description=(
            "Optimizer settings used in this backtest run: max_oil_loss_pct, "
            "spm_range, spm_step, steam_range, steam_step, vfd_fixed_hz."
        ),
    )
    baseline: BacktestArm
    tejas: BacktestArm
    delta_tejas_minus_baseline: BacktestDelta
    daily_baseline: list[BacktestDailyRow]
    daily_tejas: list[BacktestDailyRow]
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# GET /api/fleet/priority models
# ---------------------------------------------------------------------------


class FleetPriorityItem(BaseModel):
    """Urgency summary for one well in the fleet priority list."""

    well_id: str
    risk_score: float = Field(..., ge=0, le=100)
    risk_label: str
    urgency_score: float = Field(
        ...,
        description="Composite urgency = risk_score + ML-condition bonus + viscosity-trend bonus",
    )
    css_stage: str
    days_since_steam_injection: int
    oil_bpd: float
    estimated_fillage_pct: float
    viscosity_cp: float
    viscosity_trend_3d_pct: float = Field(
        ..., description="% change in viscosity over last 3 days (positive = rising)"
    )
    ml_condition: Optional[str] = None
    ml_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    forecast_trend: str = Field(
        default="stable",
        description="'declining' when oil fell >10% in last 7 days, else 'stable'",
    )
    reason: str = Field(
        ...,
        description="One-line plain-English reason derived from real measured values",
    )


class FleetPriorityResponse(BaseModel):
    """Response from GET /api/fleet/priority."""

    wells: list[FleetPriorityItem]
    total: int
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )


# ---------------------------------------------------------------------------
# GET /api/fleet/summary models
# ---------------------------------------------------------------------------


class FleetSummaryResponse(BaseModel):
    """Fleet-level aggregate statistics."""

    total_wells: int
    wells_producing: int
    wells_injecting: int
    wells_soaking: int
    total_oil_bpd: float
    total_energy_kwh: float
    avg_risk_score: float
    wells_high_risk: int
    wells_medium_risk: int
    wells_low_risk: int
    data_note: str = Field(
        default="Synthetic demonstration data — not real Oil India field data.",
    )

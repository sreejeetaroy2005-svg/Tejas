// ---------------------------------------------------------------------------
// Types matching the backend Pydantic models — do not guess field names.
// Source of truth: backend/app/models.py
// ---------------------------------------------------------------------------

// GET /api/wells
export interface WellSummary {
  well_id: string;
  well_name: string;
  field: string;
  status: string;
  current_css_cycle: number;
  current_css_stage: string;
  risk_score: number;
  risk_label: string;
  oil_bpd: number;
  reservoir_temperature_c: number;
  last_updated: string;
}

export interface WellsResponse {
  wells: WellSummary[];
  total: number;
  data_note: string;
}

// POST /api/simulate
export interface SimulateRequest {
  steam_volume_tonnes?: number;
  soak_time_days?: number;
  spm?: number;
  vfd_frequency_hz?: number;
}

export interface ProjectedValues {
  reservoir_temperature_c: number;
  viscosity_cp: number;
  oil_bpd: number;
  water_bpd: number;
  estimated_fillage_pct: number;
  motor_current_a: number;
  vfd_frequency_hz: number;
  energy_kwh: number;
  sor: number;
}

export interface SimulateResponse {
  well_id: string;
  current_stage: string;
  overrides: Record<string, number>;
  projected: ProjectedValues;
  risk_score: number;
  risk_label: string;
  risk_factors: Record<string, number>;
  explanation: string;
  data_note: string;
}

// POST /api/optimize/{well_id}
export interface BestOption {
  spm: number;
  vfd_frequency_hz: number;
  steam_volume_tonnes: number;
  projected_oil_bpd: number;
  projected_energy_kwh: number;
  projected_sor: number;
  risk_score: number;
  risk_label: string;
  composite_score: number;
  contributing_factors: Record<string, number>;
}

export interface OptimizeResponse {
  well_id: string;
  current: Record<string, number | string>;
  best_option: BestOption;
  alternatives_evaluated: number;
  score_breakdown: Record<string, number>;
  explanation: string;
  data_note: string;
}

// ---------------------------------------------------------------------------
// Extended types for frontend-only features (mock data / charts)
// ---------------------------------------------------------------------------

export interface HistoryPoint {
  date: string;
  oil_bpd: number;
  water_bpd: number;
  reservoir_temperature_c: number;
  reservoir_pressure_psi: number;
  viscosity_cp: number;
  sor: number;
  spm: number;
  vfd_frequency_hz: number;
  motor_current_a: number;
  estimated_fillage_pct: number;
  risk_score: number;
  risk_label: string;
  css_stage: string;
}

export interface ExtendedWellSummary extends WellSummary {
  reservoir_pressure_psi: number;
  sor: number;
  spm: number;
  vfd_frequency_hz: number;
  motor_current_a: number;
  estimated_fillage_pct: number;
  risk_factors: Record<string, number>;
}

// GET /api/dynacards/examples
export interface DynacardExample {
  card_id: string;
  well_id: string;
  position: number[];
  load: number[];
  condition_label: string;
  risk_level: string;
}

// POST /api/dynacards/classify
export interface DynacardClassifyRequest {
  position: number[];
  load: number[];
  spm: number;
  stroke_length: number;
  temperature: number;
  viscosity: number;
  fluid_level: number;
  pump_depth: number;
  production_rate: number;
}

export interface DynacardClassification {
  predicted_condition: string;
  confidence: number;
  top_features: string[];
  explanation: string;
  recommended_action: string;
}

// Forecast types
export interface ForecastDay {
  date: string;
  predicted_temperature_c: number;
  predicted_oil_bpd: number;
}

export interface ForecastResponse {
  well_id: string;
  days: number;
  temperature_mae: number;
  production_mae: number;
  forecast: ForecastDay[];
  data_note: string;
}

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

export interface DailyRecord {
  date: string;
  css_stage: string;
  reservoir_temperature_c: number;
  viscosity_cp: number;
  oil_bpd: number;
  water_bpd: number;
  sor: number;
  energy_kwh: number;
  spm: number;
  vfd_frequency_hz: number;
  motor_current_a: number;
  estimated_fillage_pct: number;
  rod_floating_risk_score: number;
  rod_floating_risk_label: string;
}

export interface HistoryResponse {
  well_id: string;
  days: number;
  records: DailyRecord[];
  data_note: string;
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

export interface SimulateRequest {
  steam_volume_tonnes?: number;
  soak_time_days?: number;
  spm?: number;
  vfd_frequency_hz?: number;
}

export interface SimulateResponse {
  well_id: string;
  current_stage: string;
  overrides: Record<string, any>;
  projected: ProjectedValues;
  risk_score: number;
  risk_label: string;
  risk_factors: Record<string, number>;
  explanation: string;
  data_note: string;
}

export interface OptimizeRequest {
  spm_range?: [number, number];
  vfd_range?: [number, number];
  steam_range?: [number, number];
}

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
  current: Record<string, any>;
  best_option: BestOption;
  alternatives_evaluated: number;
  score_breakdown: Record<string, any>;
  explanation: string;
  data_note: string;
}

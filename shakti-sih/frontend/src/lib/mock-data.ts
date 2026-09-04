/**
 * Mock data for all API endpoints — used automatically when the backend is
 * unreachable. Matches the exact shapes of backend Pydantic models.
 *
 * All data is synthetic demonstration data — not real Oil India field data.
 */

import {
  WellSummary,
  WellsResponse,
  ExtendedWellSummary,
  HistoryPoint,
  SimulateResponse,
  OptimizeResponse,
  DynacardExample,
  DynacardClassification,
  ForecastResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Well summary (GET /api/wells + GET /api/wells/{well_id})
// ---------------------------------------------------------------------------
export const mockWellSummary: WellSummary = {
  well_id: "BGW-01",
  well_name: "BGW-01",
  field: "Baghewala",
  status: "producing",
  current_css_cycle: 3,
  current_css_stage: "production",
  risk_score: 42.0,
  risk_label: "Medium",
  oil_bpd: 110.5,
  reservoir_temperature_c: 125.0,
  last_updated: new Date().toISOString().split("T")[0],
};

export const mockWellsResponse: WellsResponse = {
  wells: [mockWellSummary],
  total: 1,
  data_note: "MOCK DATA — API Unreachable",
};

// Extended well used by dashboard and SRP pages (frontend-only extras)
export const mockExtendedWell: ExtendedWellSummary = {
  ...mockWellSummary,
  reservoir_pressure_psi: 1420,
  sor: 2.85,
  spm: 8.8,
  vfd_frequency_hz: 45.3,
  motor_current_a: 38.2,
  estimated_fillage_pct: 72.0,
  risk_factors: {
    fillage: 18.5,
    viscosity: 12.3,
    spm_excess: 7.2,
    motor_current: 4.0,
  },
};

// ---------------------------------------------------------------------------
// History (GET /api/wells/{well_id}/history)
// 90 simulated days: 30 injection → 10 soak → 50 production
// ---------------------------------------------------------------------------
const CSS_STAGES = (i: number) =>
  i < 30 ? "injection" : i < 40 ? "soak" : "production";

export const mockHistory: HistoryPoint[] = Array.from({ length: 90 }).map(
  (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (90 - i));
    const isProducing = i >= 40;
    const dayInProd = i - 40;
    // Reservoir cools during production, heats during injection
    const tempBase =
      i < 30
        ? 115 + i * 0.5
        : i < 40
          ? 130 - (i - 30) * 0.3
          : 128 - dayInProd * 0.6;
    const temp = tempBase + (Math.random() - 0.5) * 2;
    const visc = Math.max(300, 12000 * Math.exp(-0.025 * temp));
    const oilRate = isProducing
      ? Math.max(40, 140 * Math.exp(-0.018 * dayInProd) + (Math.random() - 0.5) * 5)
      : 0;
    const riskScore = isProducing
      ? Math.min(95, 25 + dayInProd * 0.4 + (Math.random() - 0.5) * 4)
      : 15;

    return {
      date: d.toISOString().split("T")[0],
      css_stage: CSS_STAGES(i),
      reservoir_temperature_c: Math.round(temp * 10) / 10,
      viscosity_cp: Math.round(visc),
      oil_bpd: Math.round(oilRate * 10) / 10,
      water_bpd: isProducing ? Math.round((oilRate * 0.45 + Math.random() * 3) * 10) / 10 : 0,
      sor: isProducing ? Math.round((2.4 + dayInProd * 0.02 + Math.random() * 0.15) * 100) / 100 : 0,
      energy_kwh: isProducing ? Math.round((480 + oilRate * 0.8 + (Math.random() - 0.5) * 20) * 10) / 10 : 0,
      spm: isProducing ? Math.round((8.8 - dayInProd * 0.02 + (Math.random() - 0.5) * 0.2) * 10) / 10 : 0,
      vfd_frequency_hz: isProducing ? 45.3 - dayInProd * 0.05 + (Math.random() - 0.5) * 0.5 : 0,
      motor_current_a: isProducing ? Math.round((36 + dayInProd * 0.06 + (Math.random() - 0.5) * 1.5) * 10) / 10 : 0,
      estimated_fillage_pct: isProducing ? Math.max(40, Math.round((82 - dayInProd * 0.4 + (Math.random() - 0.5) * 2) * 10) / 10) : 0,
      risk_score: Math.round(riskScore * 10) / 10,
      risk_label: riskScore <= 35 ? "Low" : riskScore <= 65 ? "Medium" : "High",
      reservoir_pressure_psi: Math.round((1500 - i * 0.8 + (Math.random() - 0.5) * 20) * 10) / 10,
    };
  }
);

// ---------------------------------------------------------------------------
// Simulate (POST /api/simulate)
// ---------------------------------------------------------------------------
export const mockSimulateResponse: SimulateResponse = {
  well_id: "BGW-01",
  current_stage: "production",
  overrides: {},
  projected: {
    reservoir_temperature_c: 126.0,
    viscosity_cp: 1400,
    oil_bpd: 115.0,
    water_bpd: 52.0,
    estimated_fillage_pct: 79.5,
    motor_current_a: 37.0,
    vfd_frequency_hz: 44.0,
    energy_kwh: 510.0,
    sor: 2.4,
  },
  risk_score: 32.0,
  risk_label: "Low",
  risk_factors: {
    fillage: 12.5,
    viscosity: 10.2,
    spm_excess: 6.8,
    motor_current: 2.5,
  },
  explanation:
    "Reducing SPM to 8.0 and VFD to 44 Hz improves pump fillage from 72% to ~79%, " +
    "reducing rod-floating risk. Reservoir temperature is expected to stabilise at 126 °C " +
    "with current steam parameters, keeping viscosity manageable at ~1 400 cP.",
  data_note: "MOCK DATA — API Unreachable",
};

// ---------------------------------------------------------------------------
// Optimize (POST /api/optimize/{well_id})
// ---------------------------------------------------------------------------
export const mockOptimizeResponse: OptimizeResponse = {
  well_id: "BGW-01",
  current: {
    spm: 8.8,
    vfd_frequency_hz: 45.3,
    steam_volume_tonnes: 150,
    css_stage: "production",
    oil_bpd: 110.5,
    risk_score: 42.0,
    risk_label: "Medium",
  },
  best_option: {
    spm: 7.5,
    vfd_frequency_hz: 42.0,
    steam_volume_tonnes: 165,
    projected_oil_bpd: 122.4,
    projected_energy_kwh: 538.0,
    projected_sor: 2.18,
    risk_score: 29.5,
    risk_label: "Low",
    composite_score: 91.3,
    contributing_factors: {
      fillage: 6.5,
      viscosity: 9.8,
      spm_excess: 3.2,
      motor_current: 10.0,
    },
  },
  alternatives_evaluated: 24,
  score_breakdown: {
    production_score: 0.612,
    sor_penalty: 0.076,
    energy_penalty: 0.135,
    risk_penalty: 0.148,
    composite: 0.913,
  },
  explanation:
    "Lowering SPM from 8.8 to 7.5 and VFD from 45.3 Hz to 42 Hz gives the pump " +
    "more time to refill each stroke, raising estimated fillage to ~84% and reducing " +
    "rod-floating risk from Medium (42) to Low (29.5). Increasing steam volume by " +
    "15 tonnes in the next injection cycle is projected to boost daily oil to 122 bbl " +
    "while keeping SOR below 2.2 t/bbl.",
  data_note: "MOCK DATA — API Unreachable",
};

// ---------------------------------------------------------------------------
// Dynacards (GET /api/dynacards/examples + POST /api/dynacards/classify)
// ---------------------------------------------------------------------------

// Generate synthetic position/load curves for each condition type
function generateCardCurve(
  type: "Normal" | "Rod Floating" | "Fluid Pound" | "Gas Interference",
  noise = 0.05
): { position: number[]; load: number[] } {
  const n = 200;
  const position: number[] = [];
  const load: number[] = [];

  for (let i = 0; i < n; i++) {
    const t = (i / (n - 1)) * 2 * Math.PI;
    position.push(Math.round((i / (n - 1)) * 100) / 100);

    let baseLoad: number;
    switch (type) {
      case "Normal":
        baseLoad = 15000 + 5000 * Math.sin(t) + 2000 * Math.cos(t * 2);
        break;
      case "Rod Floating":
        baseLoad = 8000 + 2000 * Math.sin(t) + 500 * Math.cos(t * 2);
        break;
      case "Fluid Pound":
        baseLoad =
          i < n * 0.4
            ? 14000 + 3000 * Math.sin(t)
            : 6000 + 4000 * Math.sin(t);
        break;
      case "Gas Interference":
        baseLoad = 12000 + 3000 * Math.sin(t) + 2000 * Math.random();
        break;
    }
    load.push(Math.round(baseLoad * (1 + (Math.random() - 0.5) * noise)));
  }
  return { position, load };
}

const normalCurve = generateCardCurve("Normal");
const floatingCurve = generateCardCurve("Rod Floating");
const poundCurve = generateCardCurve("Fluid Pound");
const gasCurve = generateCardCurve("Gas Interference");

export const mockDynacardExamples: DynacardExample[] = [
  {
    card_id: "MOCK-NORMAL-01",
    well_id: "BGW-01",
    position: normalCurve.position,
    load: normalCurve.load,
    condition_label: "Normal",
    risk_level: "Low",
  },
  {
    card_id: "MOCK-FLOATING-01",
    well_id: "BGW-01",
    position: floatingCurve.position,
    load: floatingCurve.load,
    condition_label: "Rod Floating",
    risk_level: "High",
  },
  {
    card_id: "MOCK-POUND-01",
    well_id: "BGW-01",
    position: poundCurve.position,
    load: poundCurve.load,
    condition_label: "Fluid Pound",
    risk_level: "Medium",
  },
  {
    card_id: "MOCK-GAS-01",
    well_id: "BGW-01",
    position: gasCurve.position,
    load: gasCurve.load,
    condition_label: "Gas Interference",
    risk_level: "Medium",
  },
];

// ---------------------------------------------------------------------------
// Forecast (GET /api/wells/{well_id}/forecast)
// ---------------------------------------------------------------------------
function generateMockForecast(): ForecastResponse {
  const today = new Date();
  const forecast = [];
  let temp = 52.0;
  let oil = 55.0;
  for (let i = 0; i < 7; i++) {
    const d = new Date(today);
    d.setDate(d.getDate() + i + 1);
    temp += -(0.5 + Math.random() * 0.8);
    oil += -(3 + Math.random() * 5);
    forecast.push({
      date: d.toISOString().split("T")[0],
      predicted_temperature_c: Math.round(temp * 100) / 100,
      predicted_oil_bpd: Math.max(5, Math.round(oil * 100) / 100),
    });
  }
  return {
    well_id: "BGW-01",
    days: 7,
    temperature_mae: 1.53,
    production_mae: 8.81,
    forecast,
    data_note: "MOCK DATA — API Unreachable",
  };
}

export const mockForecastResponse: ForecastResponse = generateMockForecast();

export const mockDynacardClassification: DynacardClassification = {
  predicted_condition: "Normal",
  confidence: 0.87,
  top_features: ["enclosed_area", "min_load", "load_range"],
  explanation:
    "This card shows a full, smooth loop characteristic of normal pump operation. " +
    "The plunger is filling properly on the upstroke and the rod loads are balanced.",
  recommended_action:
    "No corrective action needed. Continue current SRP settings and monitor.",
};

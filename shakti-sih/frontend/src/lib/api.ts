/**
 * API client for the Tejas backend (FastAPI on http://127.0.0.1:8000).
 *
 * Every function returns { data: T; isMock: boolean }.
 * If the backend is unreachable the mock fallback is used automatically
 * and isMock is set to true so the UI can show an "API Offline" badge.
 */

import {
  WellsResponse,
  WellSummary,
  HistoryPoint,
  SimulateRequest,
  SimulateResponse,
  OptimizeResponse,
  DynacardExample,
  DynacardClassifyRequest,
  DynacardClassification,
  ForecastResponse,
} from "@/types";

import {
  mockWellsResponse,
  mockWellSummary,
  mockHistory,
  mockSimulateResponse,
  mockOptimizeResponse,
  mockDynacardExamples,
  mockDynacardClassification,
  mockForecastResponse,
} from "./mock-data";

const API_BASE = "http://127.0.0.1:8000/api";

type Result<T> = { data: T; isMock: boolean };

// ---------------------------------------------------------------------------
// GET /api/wells
// ---------------------------------------------------------------------------
export async function fetchWells(): Promise<Result<WellsResponse>> {
  try {
    const res = await fetch(`${API_BASE}/wells`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] fetchWells failed — using mock data");
    return { data: mockWellsResponse, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// GET /api/wells/{well_id}
// ---------------------------------------------------------------------------
export async function fetchWell(wellId: string): Promise<Result<WellSummary>> {
  try {
    const res = await fetch(`${API_BASE}/wells/${wellId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] fetchWell failed — using mock data");
    return { data: mockWellSummary, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// GET /api/wells/{well_id}/history?days=N
// Maps backend DailyRecord → HistoryPoint (same fields, aliasing risk fields)
// ---------------------------------------------------------------------------
export async function fetchHistory(
  wellId: string,
  days = 90
): Promise<Result<HistoryPoint[]>> {
  try {
    const res = await fetch(`${API_BASE}/wells/${wellId}/history?days=${days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const body: { records: any[] } = await res.json();
    // Map backend field names → HistoryPoint
    const points: HistoryPoint[] = body.records.map((r) => ({
      date: r.date,
      css_stage: r.css_stage,
      oil_bpd: r.oil_bpd,
      water_bpd: r.water_bpd,
      reservoir_temperature_c: r.reservoir_temperature_c,
      reservoir_pressure_psi: 0, // not in backend; keep 0
      viscosity_cp: r.viscosity_cp,
      sor: r.sor,
      spm: r.spm,
      vfd_frequency_hz: r.vfd_frequency_hz,
      motor_current_a: r.motor_current_a,
      estimated_fillage_pct: r.estimated_fillage_pct,
      risk_score: r.rod_floating_risk_score,
      risk_label: r.rod_floating_risk_label,
    }));
    return { data: points, isMock: false };
  } catch {
    console.warn("[api] fetchHistory failed — using mock data");
    return { data: mockHistory, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// POST /api/simulate
// ---------------------------------------------------------------------------
export async function runSimulation(
  req: SimulateRequest
): Promise<Result<SimulateResponse>> {
  try {
    const res = await fetch(`${API_BASE}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] runSimulation failed — using mock data");
    return { data: mockSimulateResponse, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// POST /api/optimize/{well_id}
// ---------------------------------------------------------------------------
export async function runOptimization(
  wellId: string
): Promise<Result<OptimizeResponse>> {
  try {
    const res = await fetch(`${API_BASE}/optimize/${wellId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] runOptimization failed — using mock data");
    return { data: mockOptimizeResponse, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// GET /api/dynacards/examples
// ---------------------------------------------------------------------------
export async function fetchDynacardExamples(): Promise<Result<DynacardExample[]>> {
  try {
    const res = await fetch(`${API_BASE}/dynacards/examples`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] fetchDynacardExamples failed — using mock data");
    return { data: mockDynacardExamples, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// POST /api/dynacards/classify
// ---------------------------------------------------------------------------
export async function classifyDynacard(
  req: DynacardClassifyRequest
): Promise<Result<DynacardClassification>> {
  try {
    const res = await fetch(`${API_BASE}/dynacards/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] classifyDynacard failed — using mock data");
    return { data: mockDynacardClassification, isMock: true };
  }
}

// ---------------------------------------------------------------------------
// GET /api/wells/{well_id}/forecast?days=N
// ---------------------------------------------------------------------------
export async function fetchForecast(
  wellId: string,
  days = 7
): Promise<Result<ForecastResponse>> {
  try {
    const res = await fetch(`${API_BASE}/wells/${wellId}/forecast?days=${days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { data: await res.json(), isMock: false };
  } catch {
    console.warn("[api] fetchForecast failed — using mock data");
    return { data: mockForecastResponse, isMock: true };
  }
}

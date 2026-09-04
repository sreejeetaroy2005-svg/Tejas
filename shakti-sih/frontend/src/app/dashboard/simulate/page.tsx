"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Beaker,
  Thermometer,
  Droplets,
  Gauge,
  GaugeCircle,
  ShieldAlert,
  Zap,
  Snowflake,
  WifiOff,
  Calendar,
  RotateCcw,
  type LucideIcon,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/info-tooltip";
import { runSimulation, fetchWells } from "@/lib/api";
import { mockExtendedWell, mockSimulateResponse } from "@/lib/mock-data";
import { TOOLTIPS } from "@/lib/tooltips";
import type { SimulateResponse, ExtendedWellSummary } from "@/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Defaults — matching backend safe limits
// ---------------------------------------------------------------------------
const DEFAULTS = {
  spm: 8.8,
  vfd_frequency_hz: 45.3,
  steam_volume_tonnes: 180,
  soak_time_days: 4,
};

// ---------------------------------------------------------------------------
// Risk label helper
// ---------------------------------------------------------------------------
function riskSeverity(label: string): "safe" | "attention" | "danger" {
  if (label === "Low") return "safe";
  if (label === "Medium") return "attention";
  return "danger";
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SimulatePage() {
  const [well, setWell] = useState<ExtendedWellSummary>(mockExtendedWell);
  const [overrides, setOverrides] = useState({
    spm: DEFAULTS.spm,
    vfd_frequency_hz: DEFAULTS.vfd_frequency_hz,
    steam_volume_tonnes: DEFAULTS.steam_volume_tonnes,
    soak_time_days: DEFAULTS.soak_time_days,
  });
  const [result, setResult] = useState<SimulateResponse>(mockSimulateResponse);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [apiDown, setApiDown] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load well data once
  useEffect(() => {
    async function load() {
      const wellsResult = await fetchWells();
      if (!wellsResult.isMock && wellsResult.data.wells[0]) {
        const base = wellsResult.data.wells[0];
        setWell({
          ...base,
          reservoir_pressure_psi: mockExtendedWell.reservoir_pressure_psi,
          sor: mockExtendedWell.sor,
          spm: mockExtendedWell.spm,
          vfd_frequency_hz: mockExtendedWell.vfd_frequency_hz,
          motor_current_a: mockExtendedWell.motor_current_a,
          estimated_fillage_pct: mockExtendedWell.estimated_fillage_pct,
          risk_factors: mockExtendedWell.risk_factors,
        });
      }
      setLoading(false);
    }
    load();
  }, []);

  // Debounced simulation call
  const runSim = useCallback(
    async (overrides: typeof DEFAULTS) => {
      setSimulating(true);
      try {
        const simResult = await runSimulation(overrides);
        if (!simResult.isMock) {
          setResult(simResult.data);
          setApiDown(false);
        } else {
          setResult(mockSimulateResponse);
          setApiDown(true);
        }
      } catch {
        setResult(mockSimulateResponse);
        setApiDown(true);
      }
      setSimulating(false);
    },
    [],
  );

  const handleChange = (key: string, value: number) => {
    const next = { ...overrides, [key]: value };
    setOverrides(next);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSim(next), 400);
  };

  const handleReset = () => {
    setOverrides(DEFAULTS);
    runSim(DEFAULTS);
  };

  // Current values for comparison
  const current = {
    oil_bpd: well.oil_bpd,
    temperature_c: well.reservoir_temperature_c,
    risk_score: well.risk_score,
    risk_label: well.risk_label === "Low" ? "Low" : well.risk_label === "Medium" ? "Medium" : "High",
    fillage: well.estimated_fillage_pct,
    motor_current: well.motor_current_a,
    spm: well.spm,
    vfd: well.vfd_frequency_hz,
    sor: well.sor,
  };

  const proj = result.projected;

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">What-If Simulator</h2>
          <p className="text-sm text-muted-foreground">
            Adjust operating parameters for {well.well_id} and see projected
            impact on production, risk, and energy
          </p>
        </div>
        <div className="flex items-center gap-3">
          {apiDown && (
            <Badge variant="attention" className="gap-1">
              <WifiOff className="h-3 w-3" />
              API Offline — Mock Data
            </Badge>
          )}
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: sliders */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="bg-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Operating Parameters
              </CardTitle>
              <p className="text-[11px] text-muted-foreground">
                Adjust these values to see how they&apos;d affect production, risk, and energy before applying them.
              </p>
            </CardHeader>
            <CardContent className="space-y-5">
              <SimSlider
                label={<>SPM<InfoTooltip text={TOOLTIPS.spm} /></>}
                value={overrides.spm}
                min={4.0}
                max={10.0}
                step={0.5}
                unit="SPM"
                icon={Gauge}
                onChange={(v) => handleChange("spm", v)}
              />
              <SimSlider
                label={<>VFD Frequency<InfoTooltip text={TOOLTIPS.vfd} /></>}
                value={overrides.vfd_frequency_hz}
                min={30}
                max={50}
                step={1}
                unit="Hz"
                icon={GaugeCircle}
                onChange={(v) => handleChange("vfd_frequency_hz", v)}
              />
              <SimSlider
                label={<>Steam Volume<InfoTooltip text={TOOLTIPS.steamVolume} /></>}
                value={overrides.steam_volume_tonnes}
                min={100}
                max={260}
                step={10}
                unit="tonnes"
                icon={Thermometer}
                onChange={(v) => handleChange("steam_volume_tonnes", v)}
              />
              <SimSlider
                label={<>Soak Time<InfoTooltip text={TOOLTIPS.soakTime} /></>}
                value={overrides.soak_time_days}
                min={3}
                max={6}
                step={1}
                unit="days"
                icon={Calendar}
                onChange={(v) => handleChange("soak_time_days", v)}
              />
            </CardContent>
          </Card>

          {/* Current baseline card */}
          <Card className="bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Current Baseline
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5 text-xs">
              <BaselineRow label="SPM" value={`${current.spm.toFixed(1)}`} />
              <BaselineRow label="VFD" value={`${current.vfd.toFixed(1)} Hz`} />
              <BaselineRow label="Temp" value={`${current.temperature_c.toFixed(1)} °C`} />
              <BaselineRow label="Oil" value={`${current.oil_bpd.toFixed(1)} bbl/day`} />
              <BaselineRow label="Risk" value={`${current.risk_score.toFixed(1)} (${current.risk_label})`} />
            </CardContent>
          </Card>
        </div>

        {/* Right column: results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Simulating indicator */}
          {simulating && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div className="h-2 w-2 rounded-full bg-accent animate-pulse" />
              Computing projection...
            </div>
          )}

          {/* KPI before / after */}
          <Card className="bg-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">
                Before → After Comparison
              </CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-muted-foreground uppercase tracking-wide border-b border-border">
                    <th className="text-left pb-2 font-medium">Metric</th>
                    <th className="text-right pb-2 font-medium">Current</th>
                    <th className="text-center pb-2 w-8" />
                    <th className="text-right pb-2 font-medium">Projected</th>
                    <th className="text-right pb-2 font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  <ResultRow
                    icon={Droplets}
                    label={<>Oil Production<InfoTooltip text={TOOLTIPS.oilProduction} /></>}
                    currentVal={current.oil_bpd}
                    projVal={proj.oil_bpd}
                    unit="bbl/day"
                    higherIsBetter
                  />
                  <ResultRow
                    icon={Thermometer}
                    label={<>Reservoir Temp<InfoTooltip text={TOOLTIPS.temperature} /></>}
                    currentVal={current.temperature_c}
                    projVal={proj.reservoir_temperature_c}
                    unit="°C"
                    higherIsBetter
                  />
                  <ResultRow
                    icon={Snowflake}
                    label={<>Viscosity<InfoTooltip text={TOOLTIPS.viscosity} /></>}
                    currentVal={0}
                    projVal={proj.viscosity_cp}
                    unit="cP"
                    higherIsBetter={false}
                    hideCurrent
                  />
                  <ResultRow
                    icon={Gauge}
                    label={<>Fillage<InfoTooltip text={TOOLTIPS.fillage} /></>}
                    currentVal={current.fillage}
                    projVal={proj.estimated_fillage_pct}
                    unit="%"
                    higherIsBetter
                  />
                  <ResultRow
                    icon={GaugeCircle}
                    label={<>Motor Current<InfoTooltip text={TOOLTIPS.motorCurrent} /></>}
                    currentVal={current.motor_current}
                    projVal={proj.motor_current_a}
                    unit="A"
                    higherIsBetter={false}
                  />
                  <ResultRow
                    icon={Zap}
                    label={<>Energy<InfoTooltip text={TOOLTIPS.energy} /></>}
                    currentVal={0}
                    projVal={proj.energy_kwh}
                    unit="kWh"
                    higherIsBetter={false}
                    hideCurrent
                  />
                  <ResultRow
                    icon={ShieldAlert}
                    label={<>Risk Score<InfoTooltip text={TOOLTIPS.rodFloatingRisk} /></>}
                    currentVal={current.risk_score}
                    projVal={result.risk_score}
                    unit="/ 100"
                    higherIsBetter={false}
                    currentExtra={current.risk_label}
                    projExtra={result.risk_label}
                    isRisk
                  />
                </tbody>
              </table>
            </CardContent>
          </Card>

          {/* Risk gauge + factors */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="bg-card">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                  Risk Assessment
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <span className="text-3xl font-bold font-mono">
                    {result.risk_score.toFixed(1)}
                  </span>
                  <div className="flex items-center gap-2">
                    <Badge variant={riskSeverity(result.risk_label) as "safe" | "attention" | "danger"}>
                      {result.risk_label}
                    </Badge>
                    <span className="text-xs text-muted-foreground">/ 100</span>
                  </div>
                </div>
                {/* Gauge bar */}
                <div className="h-3 rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      result.risk_score <= 35
                        ? "bg-safe"
                        : result.risk_score <= 65
                          ? "bg-attention"
                          : "bg-danger",
                    )}
                    style={{ width: `${Math.min(100, result.risk_score)}%` }}
                  />
                </div>
                {/* Factors */}
                <div className="space-y-1.5 pt-1">
                  {Object.entries(result.risk_factors)
                    .sort((a, b) => b[1] - a[1])
                    .map(([key, value]) => {
                      const labels: Record<string, string> = {
                        fillage: "Pump Fillage",
                        viscosity: "Oil Viscosity",
                        spm_excess: "Excess SPM",
                        motor_current: "Motor Current",
                      };
                      return (
                        <div key={key} className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground w-28 shrink-0">
                            {labels[key] ?? key}
                          </span>
                          <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                value > 15 ? "bg-danger" : value > 8 ? "bg-attention" : "bg-safe",
                              )}
                              style={{ width: `${Math.min(100, (value / 35) * 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-muted-foreground w-10 text-right">
                            {value.toFixed(1)}
                          </span>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>

            {/* Explanation */}
            <Card className="bg-card border-accent/20">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-accent">
                  <Beaker className="h-4 w-4" />
                  Simulation Result
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed text-foreground">
                  {result.explanation}
                </p>
                <p className="text-[11px] text-muted-foreground mt-4">
                  Overrides applied: SPM {overrides.spm.toFixed(1)}, VFD{" "}
                  {overrides.vfd_frequency_hz.toFixed(0)} Hz, Steam{" "}
                  {overrides.steam_volume_tonnes.toFixed(0)} tonnes, Soak{" "}
                  {overrides.soak_time_days} days
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="rounded-md border border-border bg-muted/30 px-4 py-2 text-center">
        <p className="text-[11px] text-muted-foreground">
          Predicted outcomes are based on synthetic well model. Real field performance requires operator validation.
        </p>
      </div>
      <p className="text-[11px] text-muted-foreground text-center pb-4">
        All data is synthetic demonstration data — not real Oil India field
        data.
      </p>
      </div>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SimSlider({
  label,
  value,
  min,
  max,
  step,
  unit,
  icon: Icon,
  onChange,
}: {
  label: React.ReactNode;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  icon: LucideIcon;
  onChange: (v: number) => void;
}) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs font-medium">{label}</span>
        </div>
        <span className="text-sm font-mono font-bold text-foreground">
          {Number.isInteger(step) ? value.toFixed(0) : value.toFixed(1)}{" "}
          <span className="text-xs font-normal text-muted-foreground">
            {unit}
          </span>
        </span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-muted
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-accent
            [&::-webkit-slider-thumb]:border-2
            [&::-webkit-slider-thumb]:border-accent-foreground
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:shadow-md
            [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:w-4
            [&::-moz-range-thumb]:rounded-full
            [&::-moz-range-thumb]:bg-accent
            [&::-moz-range-thumb]:border-2
            [&::-moz-range-thumb]:border-accent-foreground
            [&::-moz-range-thumb]:cursor-pointer"
          style={{
            background: `linear-gradient(to right, #f59e0b ${pct}%, #1e293b ${pct}%)`,
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

function BaselineRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono">{value}</span>
    </div>
  );
}

function ResultRow({
  icon: Icon,
  label,
  currentVal,
  projVal,
  unit,
  higherIsBetter,
  hideCurrent = false,
  currentExtra,
  projExtra,
  isRisk = false,
}: {
  icon: LucideIcon;
  label: React.ReactNode;
  currentVal: number;
  projVal: number;
  unit: string;
  higherIsBetter: boolean;
  hideCurrent?: boolean;
  currentExtra?: string;
  projExtra?: string;
  isRisk?: boolean;
}) {
  const diff = projVal - currentVal;
  const improved = higherIsBetter ? diff > 0 : diff < 0;
  const pctChange = currentVal !== 0 ? Math.abs(diff / currentVal) * 100 : null;

  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="py-2.5 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5" />
          {label}
        </div>
      </td>
      <td className="py-2.5 text-right">
        {hideCurrent ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : (
          <span className="text-sm font-mono">{currentVal.toFixed(1)}</span>
        )}
        {currentExtra && (
          <Badge
            variant={riskSeverity(currentExtra) as "safe" | "attention" | "danger"}
            className="ml-1 text-[10px]"
          >
            {currentExtra}
          </Badge>
        )}
      </td>
      <td className="py-2.5 text-center">
        <span className="text-muted-foreground text-xs">→</span>
      </td>
      <td className="py-2.5 text-right">
        <span
          className={cn(
            "text-sm font-mono font-medium",
            isRisk
              ? riskSeverity(projExtra ?? "") === "safe"
                ? "text-safe"
                : riskSeverity(projExtra ?? "") === "attention"
                  ? "text-attention"
                  : "text-danger"
              : "text-foreground",
          )}
        >
          {projVal.toFixed(1)}
        </span>
        {projExtra && (
          <Badge
            variant={riskSeverity(projExtra) as "safe" | "attention" | "danger"}
            className="ml-1 text-[10px]"
          >
            {projExtra}
          </Badge>
        )}
      </td>
      <td className="py-2.5 text-right">
        {diff !== 0 && !hideCurrent && (
          <span
            className={cn(
              "text-xs font-mono",
              improved ? "text-safe" : "text-danger",
            )}
          >
            {pctChange !== null
              ? `${pctChange.toFixed(0)}%`
              : diff > 0
                ? `+${diff.toFixed(1)}`
                : diff.toFixed(1)}
          </span>
        )}
        {(diff === 0 || hideCurrent) && (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

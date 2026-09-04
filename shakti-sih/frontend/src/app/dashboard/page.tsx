"use client";

import { useEffect, useState } from "react";
import {
  Thermometer,
  Gauge,
  Droplets,
  GaugeCircle,
  ShieldAlert,
  WifiOff,
  Calendar,
  RefreshCw,
} from "lucide-react";
import { KpiCard } from "@/components/kpi-card";
import { RiskAlert } from "@/components/risk-alert";
import { RecommendationSummary } from "@/components/recommendation-summary";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/info-tooltip";
import { IntroBanner } from "@/components/intro-banner";
import { fetchWells, runOptimization } from "@/lib/api";
import { mockExtendedWell, mockOptimizeResponse } from "@/lib/mock-data";
import { TOOLTIPS } from "@/lib/tooltips";
import type { WellsResponse, OptimizeResponse, ExtendedWellSummary } from "@/types";

function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    injection: "Steam Injecting",
    soak: "Soaking",
    production: "Producing",
  };
  return map[stage] ?? stage;
}

function riskSeverity(label: string): "safe" | "attention" | "danger" {
  if (label === "High") return "danger";
  if (label === "Medium") return "attention";
  return "safe";
}

export default function DashboardPage() {
  const [wellsData, setWellsData] = useState<WellsResponse | null>(null);
  const [well, setWell] = useState<ExtendedWellSummary>(mockExtendedWell);
  const [optimizeData, setOptimizeData] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiDown, setApiDown] = useState(false);

  async function loadData() {
    setLoading(true);
    const wellsResult = await fetchWells();
    if (!wellsResult.isMock) {
      setWellsData(wellsResult.data);
      const base = wellsResult.data.wells[0];
      if (base) {
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
      setApiDown(false);
    } else {
      setApiDown(true);
      setWell(mockExtendedWell);
    }
    const optResult = await runOptimization("BGW-01");
    setOptimizeData(optResult.isMock ? mockOptimizeResponse : optResult.data);
    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleReset = () => loadData();

  return (
    <TooltipProvider>
      <div className="space-y-6">
        <IntroBanner message="Tejas predicts pump risk and recommends safe CSS/SRP settings — hover any metric label for an explanation. All recommendations require operator approval before field action." />
        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight">Overview</h2>
            <p className="text-sm text-muted-foreground">
              Real-time status for well {well.well_id} — {well.field} field
            </p>
          </div>
          <div className="flex items-center gap-3">
            {apiDown && (
              <Badge variant="attention" className="gap-1">
                <WifiOff className="h-3 w-3" />
                Running offline—using demo data
              </Badge>
            )}
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              title="Reset Demo — reload latest data from the API"
            >
              <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
              Reset Demo
            </button>
            <Badge variant="secondary" className="gap-1">
              <Calendar className="h-3 w-3" />
              Updated {well.last_updated}
            </Badge>
          </div>
        </div>

        {/* Well status bar */}
        <div className="flex items-center gap-3 flex-wrap">
          <Badge
            variant={
              well.status === "producing"
                ? "safe"
                : well.status === "injecting"
                  ? "attention"
                  : "secondary"
            }
          >
            {stageLabel(well.current_css_stage)}
          </Badge>
          <span className="text-xs text-muted-foreground">
            Cycle {well.current_css_cycle}
          </span>
          <span className="text-xs text-muted-foreground">•</span>
          <span className="text-xs text-muted-foreground">{well.field}</span>
        </div>

        {/* KPI Cards — 5 across */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiCard
            title={<>Reservoir Temp<InfoTooltip text={TOOLTIPS.temperature} /></>}
            value={well.reservoir_temperature_c}
            unit="°C"
            icon={Thermometer}
            loading={loading}
            severity={
              well.reservoir_temperature_c > 80
                ? "safe"
                : well.reservoir_temperature_c > 50
                  ? "attention"
                  : "danger"
            }
            subtitle="Reservoir temperature"
          />
          <KpiCard
            title={<>Pressure<InfoTooltip text={TOOLTIPS.pressure} /></>}
            value={well.reservoir_pressure_psi}
            unit="psi"
            icon={Gauge}
            loading={loading}
            severity="neutral"
            subtitle="Reservoir pressure"
          />
          <KpiCard
            title={<>Oil Production<InfoTooltip text={TOOLTIPS.oilProduction} /></>}
            value={well.oil_bpd}
            unit="bbl/day"
            icon={Droplets}
            loading={loading}
            severity={
              well.oil_bpd > 100
                ? "safe"
                : well.oil_bpd > 30
                  ? "attention"
                  : "danger"
            }
            subtitle={<>SOR {well.sor.toFixed(3)}<InfoTooltip text={TOOLTIPS.sor} /></>}
          />
          <KpiCard
            title={<>Risk Score<InfoTooltip text={TOOLTIPS.rodFloatingRisk} /></>}
            value={well.risk_score}
            unit="/ 100"
            icon={ShieldAlert}
            loading={loading}
            severity={riskSeverity(well.risk_label)}
            subtitle={`Label: ${well.risk_label}`}
          />
          <KpiCard
            title={<>Motor Current<InfoTooltip text={TOOLTIPS.motorCurrent} /></>}
            value={well.motor_current_a}
            unit="A"
            icon={GaugeCircle}
            loading={loading}
            severity={
              well.motor_current_a > 45
                ? "danger"
                : well.motor_current_a > 35
                  ? "attention"
                  : "safe"
            }
            subtitle={<>Fillage {well.estimated_fillage_pct.toFixed(0)}%<InfoTooltip text={TOOLTIPS.fillage} /></>}
          />
        </div>

        {/* Risk Alert + Recommendation — side by side */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <RiskAlert
            riskScore={well.risk_score}
            riskLabel={well.risk_label}
            riskFactors={well.risk_factors}
            loading={loading}
          />
          <RecommendationSummary
            data={optimizeData}
            loading={loading}
            error={false}
          />
        </div>

        {/* Quick stats footer */}
        <Card className="bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Current Operating Parameters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold">{well.spm.toFixed(1)}</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">SPM<InfoTooltip text={TOOLTIPS.spm} /></p>
              </div>
              <div>
                <p className="text-2xl font-bold">{well.vfd_frequency_hz.toFixed(1)}</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">VFD (Hz)<InfoTooltip text={TOOLTIPS.vfd} /></p>
              </div>
              <div>
                <p className="text-2xl font-bold">{well.estimated_fillage_pct.toFixed(0)}%</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">Fillage<InfoTooltip text={TOOLTIPS.fillage} /></p>
              </div>
              <div>
                <p className="text-2xl font-bold">{well.reservoir_pressure_psi.toFixed(0)}</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">Pressure (psi)<InfoTooltip text={TOOLTIPS.pressure} /></p>
              </div>
              <div>
                <p className="text-2xl font-bold">{well.sor.toFixed(3)}</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">SOR<InfoTooltip text={TOOLTIPS.sor} /></p>
              </div>
              <div>
                <p className="text-2xl font-bold">{well.risk_score.toFixed(1)}</p>
                <p className="text-[11px] text-muted-foreground flex items-center justify-center">Risk<InfoTooltip text={TOOLTIPS.rodFloatingRisk} /></p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Disclaimer */}
        <p className="text-[11px] text-muted-foreground text-center pb-4">
          All data is synthetic demonstration data — not real Oil India field data.
        </p>
      </div>
    </TooltipProvider>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Flame, Snowflake, Droplets, Activity, WifiOff, Calendar, Brain } from "lucide-react";
import { ProductionChart } from "@/components/charts/production-chart";
import { TemperatureChart } from "@/components/charts/temperature-chart";
import { ForecastChart } from "@/components/charts/forecast-chart";
import { CssStageTimeline } from "@/components/css-stage-timeline";
import { ThermalStatCard } from "@/components/thermal-stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/info-tooltip";
import { fetchHistory, fetchWells, fetchForecast } from "@/lib/api";
import { mockHistory, mockExtendedWell } from "@/lib/mock-data";
import { TOOLTIPS } from "@/lib/tooltips";
import type { HistoryPoint, ExtendedWellSummary, ForecastDay } from "@/types";

export default function ProductionPage() {
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [well, setWell] = useState<ExtendedWellSummary>(mockExtendedWell);
  const [loading, setLoading] = useState(true);
  const [apiDown, setApiDown] = useState(false);
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [temperatureMae, setTemperatureMae] = useState(0);
  const [productionMae, setProductionMae] = useState(0);
  const [forecastLoading, setForecastLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);

      const historyResult = await fetchHistory("BGW-01", 90);
      setHistory(historyResult.data);
      setApiDown(historyResult.isMock);

      const forecastResult = await fetchForecast("BGW-01", 7);
      setForecast(forecastResult.data.forecast);
      setTemperatureMae(forecastResult.data.temperature_mae);
      setProductionMae(forecastResult.data.production_mae);
      setForecastLoading(false);

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

  // Compute summary stats from history
  const latestPoint = history.length > 0 ? history[history.length - 1] : null;
  const avgOil =
    history.length > 0
      ? history.reduce((s, p) => s + p.oil_bpd, 0) / history.length
      : 0;
  const avgTemp =
    history.length > 0
      ? history.reduce((s, p) => s + p.reservoir_temperature_c, 0) /
        history.length
      : 0;
  const avgVisc =
    history.length > 0
      ? history.reduce((s, p) => s + p.viscosity_cp, 0) / history.length
      : 0;

  // Find peak oil rate
  const peakOil =
    history.length > 0
      ? Math.max(...history.map((p) => p.oil_bpd))
      : 0;

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">
            Production &amp; Thermal
          </h2>
          <p className="text-sm text-muted-foreground">
            Oil rate trends, reservoir thermal profile, and CSS cycle tracking
            for {well.well_id}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {apiDown && (
            <Badge variant="attention" className="gap-1">
              <WifiOff className="h-3 w-3" />
              API Offline — Mock Data
            </Badge>
          )}
          <Badge variant="secondary" className="gap-1">
            <Calendar className="h-3 w-3" />
            {history.length} days
          </Badge>
        </div>
      </div>

      {/* Summary stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <ThermalStatCard
          label={<>Current Temp<InfoTooltip text={TOOLTIPS.temperature} /></>}
          value={latestPoint?.reservoir_temperature_c ?? well.reservoir_temperature_c}
          unit="°C"
          icon={Flame}
          loading={loading}
          severity={
            (latestPoint?.reservoir_temperature_c ?? well.reservoir_temperature_c) > 80
              ? "safe"
              : (latestPoint?.reservoir_temperature_c ?? well.reservoir_temperature_c) > 50
                ? "attention"
                : "danger"
          }
          subtitle="Reservoir temperature"
        />
        <ThermalStatCard
          label={<>Avg Oil Rate<InfoTooltip text={TOOLTIPS.oilProduction} /></>}
          value={avgOil}
          unit="bbl/day"
          icon={Droplets}
          loading={loading}
          severity={
            avgOil > 100 ? "safe" : avgOil > 30 ? "attention" : "danger"
          }
          subtitle={`Peak: ${peakOil.toFixed(1)} bbl/day`}
        />
        <ThermalStatCard
          label={<>Avg Viscosity<InfoTooltip text={TOOLTIPS.viscosity} /></>}
          value={avgVisc}
          unit="cP"
          icon={Snowflake}
          loading={loading}
          severity={
            avgVisc > 5000
              ? "danger"
              : avgVisc > 2000
                ? "attention"
                : "safe"
          }
          subtitle="Oil resistance estimate"
        />
        <ThermalStatCard
          label={<>Avg Reservoir Temp<InfoTooltip text={TOOLTIPS.temperature} /></>}
          value={avgTemp}
          unit="°C"
          icon={Activity}
          loading={loading}
          severity={
            avgTemp > 80 ? "safe" : avgTemp > 50 ? "attention" : "danger"
          }
          subtitle="Thermal energy level"
        />
      </div>

      {/* CSS Stage Timeline */}
      <CssStageTimeline data={history} loading={loading} />

      {/* 7-Day Forecast */}
      {forecast.length > 0 && (
        <ForecastChart
          history={history}
          forecast={forecast}
          temperatureMae={temperatureMae}
          productionMae={productionMae}
          loading={forecastLoading}
        />
      )}

      {/* Charts side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ProductionChart data={history} loading={loading} />
        <TemperatureChart data={history} loading={loading} />
      </div>

      {/* Thermal insights */}
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Thermal Insights
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div className="rounded-md border border-border p-3">
              <p className="text-[11px] text-muted-foreground mb-1">
                Temperature–Viscosity Relationship
              </p>
              <p className="text-xs">
                Oil viscosity is inversely exponential to temperature. A{" "}
                <span className="text-danger font-medium">10°C drop</span> can
                increase viscosity by{" "}
                <span className="text-danger font-medium">~2×</span>, making
                pump lift significantly harder.
              </p>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-[11px] text-muted-foreground mb-1">
                CSS Cycle Effect
              </p>
              <p className="text-xs">
                Steam injection raises reservoir temperature, thinning heavy
                oil. During production, temperature decays exponentially — the
                window of high production is the first{" "}
                <span className="text-attention font-medium">2–3 weeks</span>{" "}
                after soak.
              </p>
            </div>
            <div className="rounded-md border border-border p-3">
              <p className="text-[11px] text-muted-foreground mb-1">
                Current Phase
              </p>
              <p className="text-xs">
                Stage:{" "}
                <span className="text-foreground font-medium capitalize">
                  {latestPoint?.css_stage ?? well.current_css_stage}
                </span>
                {latestPoint?.css_stage === "production" && (
                  <>
                    {" "}— production rate typically{" "}
                    <span className="text-attention font-medium">decays</span>{" "}
                    as reservoir cools. Monitor temperature trend for
                    re-injection timing.
                  </>
                )}
                {latestPoint?.css_stage === "injection" && (
                  <>
                    {" "}— steam is being injected to{" "}
                    <span className="text-safe font-medium">reheat</span>{" "}
                    the reservoir. SPM should be{" "}
                    <span className="text-safe font-medium">reduced</span>{" "}
                    during this phase.
                  </>
                )}
                {latestPoint?.css_stage === "soak" && (
                  <>
                    {" "}— allow heat to{" "}
                    <span className="text-safe font-medium">diffuse</span>{" "}
                    into the formation. No production during soak.
                  </>
                )}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Disclaimer */}
      <p className="text-[11px] text-muted-foreground text-center pb-4">
        All data is synthetic demonstration data — not real Oil India field
        data.
      </p>
      </div>
    </TooltipProvider>
  );
}

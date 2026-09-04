"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Gauge,
  GaugeCircle,
  Settings2,
  WifiOff,
  Calendar,
  Cpu,
  ScanLine,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { SrpTrendChart } from "@/components/charts/srp-trend-chart";
import { MotorCurrentChart } from "@/components/charts/motor-current-chart";
import { FillageGauge } from "@/components/fillage-gauge";
import { RiskAlert } from "@/components/risk-alert";
import { KpiCard } from "@/components/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/info-tooltip";
import { fetchHistory, fetchWells, fetchDynacardExamples } from "@/lib/api";
import { mockHistory, mockExtendedWell } from "@/lib/mock-data";
import { TOOLTIPS } from "@/lib/tooltips";
import type { HistoryPoint, ExtendedWellSummary, DynacardExample } from "@/types";

// Condition → color mapping (consistent with dashboard theme)
const CONDITION_COLORS: Record<string, string> = {
  Normal: "#22c55e",
  "Rod Floating": "#ef4444",
  "Fluid Pound": "#f59e0b",
  "Gas Interference": "#f97316",
};

const CONDITION_RISK: Record<string, "safe" | "attention" | "danger"> = {
  Normal: "safe",
  "Rod Floating": "danger",
  "Fluid Pound": "attention",
  "Gas Interference": "attention",
};

const CONDITION_EXPLANATIONS: Record<string, string> = {
  Normal:
    "Full, smooth loop — the pump barrel fills properly on each upstroke. Rod loads are balanced, indicating good pump-to-well matching.",
  "Rod Floating":
    "Narrow, compressed loop — the pump barrel only partially fills, causing the rod to 'float' on fluid during the downstroke. The plunger never fully loads.",
  "Fluid Pound":
    "Sharp dip on the downstroke — the plunger hits a partial fluid column, creating a mechanical shock (fluid pound). High risk of equipment damage.",
  "Gas Interference":
    "Jagged, irregular pattern — gas bubbles compress in the pump barrel, reducing fillage and creating erratic rod loads.",
};

const CONDITION_ACTIONS: Record<string, string> = {
  Normal:
    "No corrective action needed. Continue current SRP settings and monitor fillage trend.",
  "Rod Floating":
    "Reduce SPM immediately to match inflow rate. Enable pump-off control if available. Consider increasing steam injection to improve oil mobility.",
  "Fluid Pound":
    "Reduce SPM to slow the pump stroke. Check standing valve for leaks. If persistent, shut down and inspect the pump for worn components.",
  "Gas Interference":
    "Install or check gas separator. Reduce SPM to allow more fill time. Consider gas anchors or improved gas handling equipment.",
};

export default function SrpHealthPage() {
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [well, setWell] = useState<ExtendedWellSummary>(mockExtendedWell);
  const [loading, setLoading] = useState(true);
  const [apiDown, setApiDown] = useState(false);

  // Dynacard state
  const [dynacardExamples, setDynacardExamples] = useState<DynacardExample[]>([]);
  const [selectedCondition, setSelectedCondition] = useState("Normal");
  const [dynacardLoading, setDynacardLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);

      const historyResult = await fetchHistory("BGW-01", 90);
      setHistory(historyResult.data);
      setApiDown(historyResult.isMock);

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

      // Load dynacard examples
      setDynacardLoading(true);
      const { data: examples } = await fetchDynacardExamples();
      setDynacardExamples(examples);
      setDynacardLoading(false);
    }
    load();
  }, []);

  // Current values from latest data point or mock
  const latestPoint =
    history.length > 0 ? history[history.length - 1] : null;
  const currentSpm = latestPoint?.spm ?? well.spm;
  const currentVfd = latestPoint?.vfd_frequency_hz ?? well.vfd_frequency_hz;
  const currentMotor = latestPoint?.motor_current_a ?? well.motor_current_a;
  const currentFillage =
    latestPoint?.estimated_fillage_pct ?? well.estimated_fillage_pct;
  const currentRisk = latestPoint?.risk_score ?? well.risk_score;
  const currentRiskLabel = latestPoint?.risk_label ?? well.risk_label;

  // Compute 7-day trend direction
  const recentProduction = history
    .filter((p) => p.css_stage === "production")
    .slice(-7);
  const prevProduction = history
    .filter((p) => p.css_stage === "production")
    .slice(-14, -7);

  function avgOf(points: HistoryPoint[], key: keyof HistoryPoint) {
    if (points.length === 0) return 0;
    return points.reduce((s, p) => s + (p[key] as number), 0) / points.length;
  }

  const avgSpmRecent = avgOf(recentProduction, "spm");
  const avgSpmPrev = avgOf(prevProduction, "spm");
  const avgVfdRecent = avgOf(recentProduction, "vfd_frequency_hz");
  const avgVfdPrev = avgOf(prevProduction, "vfd_frequency_hz");
  const avgMotorRecent = avgOf(recentProduction, "motor_current_a");
  const avgMotorPrev = avgOf(prevProduction, "motor_current_a");

  function trendLabel(current: number, prev: number) {
    if (prev === 0) return "";
    const diff = current - prev;
    const pct = Math.abs(diff / prev) / 100;
    if (pct < 0.01) return "— stable";
    return diff > 0 ? `↑ ${(pct * 100).toFixed(1)}%` : `↓ ${(pct * 100).toFixed(1)}%`;
  }

  // Selected dynacard card
  const selectedCard = dynacardExamples.find(
    (c) => c.condition_label === selectedCondition
  );

  // Transform card data for Recharts (position → x-axis 0–180, load → y-axis)
  const cardChartData = selectedCard
    ? selectedCard.position.map((pos, i) => ({
        position: Math.round(pos * 180),
        load: selectedCard.load[i],
      }))
    : [];

  const cardColor = CONDITION_COLORS[selectedCondition] ?? "#888";

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold tracking-tight">SRP Health</h2>
            <p className="text-sm text-muted-foreground">
              Sucker Rod Pump diagnostics, motor performance, and rod-floating
              risk for {well.well_id}
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

        {/* 4 KPI cards — current values with trend */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            title={<>SPM<InfoTooltip text={TOOLTIPS.spm} /></>}
            value={currentSpm}
            unit="SPM"
            icon={Activity}
            loading={loading}
            severity={
              currentSpm > 9
                ? "danger"
                : currentSpm > 7
                  ? "attention"
                  : "safe"
            }
            subtitle={`7d avg: ${avgSpmRecent.toFixed(1)} ${trendLabel(avgSpmRecent, avgSpmPrev)}`}
          />
          <KpiCard
            title={<>VFD<InfoTooltip text={TOOLTIPS.vfd} /></>}
            value={currentVfd}
            unit="Hz"
            icon={Settings2}
            loading={loading}
            severity={
              currentVfd > 47
                ? "danger"
                : currentVfd > 40
                  ? "attention"
                  : "safe"
            }
            subtitle={`7d avg: ${avgVfdRecent.toFixed(1)} ${trendLabel(avgVfdRecent, avgVfdPrev)}`}
          />
          <KpiCard
            title={<>Motor Current<InfoTooltip text={TOOLTIPS.motorCurrent} /></>}
            value={currentMotor}
            unit="A"
            icon={GaugeCircle}
            loading={loading}
            severity={
              currentMotor > 45
                ? "danger"
                : currentMotor > 35
                  ? "attention"
                  : "safe"
            }
            subtitle={`7d avg: ${avgMotorRecent.toFixed(1)} ${trendLabel(avgMotorRecent, avgMotorPrev)}`}
          />
          <KpiCard
            title={<>Fillage<InfoTooltip text={TOOLTIPS.fillage} /></>}
            value={currentFillage}
            unit="%"
            icon={Gauge}
            loading={loading}
            severity={
              currentFillage >= 60
                ? "safe"
                : currentFillage >= 40
                  ? "attention"
                  : "danger"
            }
            subtitle={
              currentFillage >= 60
                ? "Good pump fill"
                : currentFillage >= 40
                  ? "Low — check pump"
                  : "Pump-off condition"
            }
          />
        </div>

        {/* Risk assessment — full width */}
        <RiskAlert
          riskScore={currentRisk}
          riskLabel={currentRiskLabel}
          riskFactors={well.risk_factors}
          loading={loading}
        />

        {/* ─── Dynamometer Card Analysis ─── */}
        <Card className="bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <ScanLine className="h-4 w-4 text-muted-foreground" />
              Dynamometer Card
              <InfoTooltip text="A dynamometer card is a closed-loop graph of rod load vs plunger position over one complete pump stroke. The shape reveals the pump's health — different failure modes produce distinctly different card shapes." />
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              Interactive card visualization from the trained RandomForest
              classifier (80% accuracy on 400 synthetic pump cards).
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Condition toggle buttons */}
            <div className="flex flex-wrap gap-2">
              {["Normal", "Rod Floating", "Fluid Pound", "Gas Interference"].map(
                (condition) => (
                  <button
                    key={condition}
                    onClick={() => setSelectedCondition(condition)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all border ${
                      selectedCondition === condition
                        ? "border-accent bg-accent/10 text-accent-foreground"
                        : "border-border text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    }`}
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-full mr-1.5"
                      style={{
                        backgroundColor: CONDITION_COLORS[condition],
                      }}
                    />
                    {condition}
                  </button>
                )
              )}
            </div>

            {/* Chart + classification results side by side */}
            <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
              {/* Chart */}
              <div className="lg:col-span-3">
                {dynacardLoading ? (
                  <Skeleton className="h-[300px] rounded-lg" />
                ) : (
                  <div className="rounded-lg border border-border bg-background/50 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-medium text-foreground">
                          Position
                          <InfoTooltip text="Normalized plunger position (0 = bottom of stroke, 1 = top). The card traces a closed loop as the plunger moves up and down." />
                        </span>
                        <span>→</span>
                        <span className="font-medium text-foreground">
                          Load
                          <InfoTooltip text="Rod load in pounds-force (lbf) measured at the surface. Higher loads indicate the pump is pulling against viscous oil or mechanical resistance." />
                        </span>
                      </div>
                      <Badge
                        variant={CONDITION_RISK[selectedCondition]}
                        className="text-[10px]"
                      >
                        {selectedCondition === "Normal"
                          ? "Low Risk"
                          : selectedCondition === "Rod Floating"
                            ? "High Risk"
                            : "Medium Risk"}
                      </Badge>
                    </div>
                    <ResponsiveContainer width="100%" height={280}>
                      <LineChart
                        data={cardChartData}
                        margin={{ top: 5, right: 20, bottom: 25, left: 10 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(255,255,255,0.06)"
                        />
                        <XAxis
                          dataKey="position"
                          type="number"
                          domain={[0, 180]}
                          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                          axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                          label={{
                            value: "Position (degrees)",
                            position: "bottom",
                            offset: 10,
                            style: {
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 11,
                            },
                          }}
                        />
                        <YAxis
                          dataKey="load"
                          type="number"
                          tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                          axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                          label={{
                            value: "Load (lbf)",
                            angle: -90,
                            position: "insideLeft",
                            offset: 5,
                            style: {
                              fill: "hsl(var(--muted-foreground))",
                              fontSize: 11,
                            },
                          }}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "hsl(var(--card))",
                            border: "1px solid hsl(var(--border))",
                            borderRadius: 8,
                            fontSize: 12,
                          }}
                          formatter={(value, name) => {
                            const numValue = typeof value === "number" ? value : Number(value);
                            return name === "position"
                              ? [`${numValue}\u00b0`, "Position"]
                              : [`${numValue.toLocaleString()} lbf`, "Load"];
                          }}
                        />
                        <Line
                          type="monotone"
                          dataKey="load"
                          stroke={cardColor}
                          strokeWidth={2.5}
                          dot={false}
                          activeDot={{ r: 4, fill: cardColor }}
                          isAnimationActive={true}
                          animationDuration={600}
                        />
                        {/* Reference lines for typical load thresholds */}
                        <ReferenceLine
                          y={6000}
                          stroke="rgba(255,255,255,0.08)"
                          strokeDasharray="4 4"
                          label={{
                            value: "Min load",
                            position: "right",
                            fill: "hsl(var(--muted-foreground))",
                            fontSize: 10,
                          }}
                        />
                        <ReferenceLine
                          y={12000}
                          stroke="rgba(255,255,255,0.08)"
                          strokeDasharray="4 4"
                          label={{
                            value: "Max load",
                            position: "right",
                            fill: "hsl(var(--muted-foreground))",
                            fontSize: 10,
                          }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              {/* Classification results */}
              <div className="lg:col-span-2 space-y-3">
                {dynacardLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-16 w-full" />
                  </div>
                ) : (
                  <>
                    {/* Condition badge + risk */}
                    <div className="rounded-lg border border-border bg-background/50 p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-muted-foreground">
                          Detected Condition
                        </span>
                        <Badge
                          variant={CONDITION_RISK[selectedCondition]}
                        >
                          {selectedCondition}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {CONDITION_EXPLANATIONS[selectedCondition]}
                      </p>
                    </div>

                    {/* Top features */}
                    <div className="rounded-lg border border-border bg-background/50 p-3">
                      <h4 className="text-xs font-medium text-muted-foreground mb-2">
                        Top Contributing Features
                      </h4>
                      <div className="space-y-1.5">
                        {[
                          {
                            name: "Enclosed Area",
                            desc: "Area inside the closed loop — strongest signal of pump efficiency",
                            value:
                              selectedCondition === "Normal"
                                ? "High (full loop)"
                                : selectedCondition === "Rod Floating"
                                  ? "Low (compressed)"
                                  : selectedCondition === "Fluid Pound"
                                    ? "Medium (partial dip)"
                                    : "Medium (erratic)",
                          },
                          {
                            name: "Min Load",
                            desc: "Lowest rod load during stroke — fluid pound shows sharp drop",
                            value:
                              selectedCondition === "Fluid Pound"
                                ? "Abnormally low"
                                : selectedCondition === "Rod Floating"
                                  ? "Very low"
                                  : "Normal range",
                          },
                          {
                            name: "Load Range",
                            desc: "Spread between max and min load — normal cards have wide range",
                            value:
                              selectedCondition === "Normal"
                                ? "Wide (healthy)"
                                : selectedCondition === "Rod Floating"
                                  ? "Narrow (weak)"
                                  : "Variable",
                          },
                        ].map((feature) => (
                          <div
                            key={feature.name}
                            className="flex items-start gap-2 text-xs"
                          >
                            <span
                              className="inline-block w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                              style={{ backgroundColor: cardColor }}
                            />
                            <div>
                              <span className="text-foreground font-medium">
                                {feature.name}
                              </span>{" "}
                              <span className="text-muted-foreground">
                                — {feature.value}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recommended action */}
                    <div className="rounded-lg border border-border bg-background/50 p-3">
                      <h4 className="text-xs font-medium text-muted-foreground mb-1">
                        Recommended Action
                      </h4>
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {CONDITION_ACTIONS[selectedCondition]}
                      </p>
                    </div>

                    {/* Data note */}
                    <p className="text-[10px] text-muted-foreground text-center pt-1">
                      Example cards from synthetic dynacard dataset (400 real
                      pump card shapes, 20 wells). Classifier trained on
                      condition labels: Normal / Rod Floating / Fluid Pound /
                      Gas Interference.
                    </p>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Charts row: SPM/VFD trend + Motor current */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SrpTrendChart data={history} loading={loading} />
          <MotorCurrentChart data={history} loading={loading} />
        </div>

        {/* Fillage gauge + SRP context */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1">
            <FillageGauge value={currentFillage} loading={loading} />
          </div>
          <div className="lg:col-span-2">
            <Card className="bg-card h-full">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                  SRP Operating Context
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs text-muted-foreground">
                <div className="rounded-md border border-border p-3">
                  <p className="text-foreground font-medium mb-1">
                    Why fillage matters
                  </p>
                  <p>
                    Fillage below <span className="text-attention font-medium">60%</span> means
                    the pump barrel isn&apos;t filling completely each stroke. This
                    wastes energy and accelerates rod wear. The optimizer will
                    recommend reducing SPM to improve fillage.
                  </p>
                </div>
                <div className="rounded-md border border-border p-3">
                  <p className="text-foreground font-medium mb-1">
                    Motor current interpretation
                  </p>
                  <p>
                    Current above <span className="text-danger font-medium">45A</span> indicates
                    the pump may be fighting viscous oil or mechanical
                    resistance. Combined with low fillage, this strongly
                    suggests the pump speed (SPM) is too high for current
                    reservoir conditions.
                  </p>
                </div>
                <div className="rounded-md border border-border p-3">
                  <p className="text-foreground font-medium mb-1">
                    SPM / VFD relationship
                  </p>
                  <p>
                    SPM controls pump strokes per minute. VFD controls motor
                    speed (Hz). Both should be reduced together when fillage is
                    low — the optimizer&apos;s composite scoring accounts for
                    this coupling.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-[11px] text-muted-foreground text-center pb-4">
          All data is synthetic demonstration data — not real Oil India field
          data.
        </p>
      </div>
    </TooltipProvider>
  );
}

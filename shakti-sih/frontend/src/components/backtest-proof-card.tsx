"use client";

/**
 * BacktestProofCard
 *
 * Displays a before/after comparison of Baseline vs Tejas recommendations
 * over the 180-day synthetic history, rendered as a Recharts bar chart plus
 * three headline numbers.
 *
 * Data comes from GET /api/backtest (falls back to mock data if offline).
 */

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { AlertTriangle, FlaskConical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function Headline({
  label,
  baseline,
  tejas,
  unit,
  lowerIsBetter,
}: {
  label: string;
  baseline: number;
  tejas: number;
  unit: string;
  lowerIsBetter: boolean;
}) {
  const improved = lowerIsBetter ? tejas < baseline : tejas > baseline;
  const same = tejas === baseline;
  const pct =
    baseline !== 0
      ? Math.abs(((tejas - baseline) / baseline) * 100).toFixed(0)
      : "—";
  const arrow = same ? "=" : improved ? "↓" : "↑";
  const color = same
    ? "text-muted-foreground"
    : improved
      ? "text-green-400"
      : "text-red-400";

  return (
    <div className="flex flex-col items-center gap-0.5 min-w-[120px]">
      <span className="text-xs text-muted-foreground text-center">{label}</span>
      <span className="text-lg font-bold">
        {typeof baseline === "number" && !Number.isInteger(baseline)
          ? baseline.toFixed(1)
          : baseline}
        <span className="text-xs font-normal text-muted-foreground ml-0.5">
          {unit}
        </span>
      </span>
      <span className={`text-sm font-semibold ${color}`}>
        {arrow} {same ? "no change" : `${pct}% ${improved ? "better" : "worse"}`}
      </span>
      <span className="text-xs text-muted-foreground">
        Tejas:{" "}
        {typeof tejas === "number" && !Number.isInteger(tejas)
          ? tejas.toFixed(1)
          : tejas}{" "}
        {unit}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart data builder
// ---------------------------------------------------------------------------

function buildChartData(data: BacktestResponse) {
  return [
    {
      metric: "High-risk days",
      Baseline: data.baseline.high_risk_days,
      Tejas: data.tejas.high_risk_days,
    },
    {
      metric: "Avg risk score",
      Baseline: parseFloat(data.baseline.avg_risk_score.toFixed(1)),
      Tejas: parseFloat(data.tejas.avg_risk_score.toFixed(1)),
    },
    {
      metric: "Energy (×100 kWh)",
      Baseline: parseFloat((data.baseline.total_energy_kwh / 100).toFixed(1)),
      Tejas: parseFloat((data.tejas.total_energy_kwh / 100).toFixed(1)),
    },
    {
      metric: "Oil (×100 bbl)",
      Baseline: parseFloat((data.baseline.total_oil_bbl / 100).toFixed(1)),
      Tejas: parseFloat((data.tejas.total_oil_bbl / 100).toFixed(1)),
    },
  ];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function BacktestProofCard() {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [isMock, setIsMock] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBacktest().then(({ data: d, isMock: m }) => {
      setData(d);
      setIsMock(m);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Loading backtest results…
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const chartData = buildChartData(data);

  return (
    <Card className="w-full border-amber-500/30">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <FlaskConical className="h-4 w-4 text-amber-400" />
          <CardTitle className="text-base">
            Proof: Tejas vs Recorded Baseline — 180-day Replay
          </CardTitle>
          {isMock && (
            <Badge variant="attention" className="text-xs">
              Offline — using stored numbers
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Both arms scored by the same simulator. Dates:{" "}
          {data.date_range.start} → {data.date_range.end} ({data.n_days} days)
        </p>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Headline numbers */}
        <div className="flex flex-wrap justify-around gap-4 py-2 border rounded-md border-border/50 bg-muted/30 px-4">
          <Headline
            label="High-risk days"
            baseline={data.baseline.high_risk_days}
            tejas={data.tejas.high_risk_days}
            unit="days"
            lowerIsBetter
          />
          <Headline
            label="Avg risk score"
            baseline={data.baseline.avg_risk_score}
            tejas={data.tejas.avg_risk_score}
            unit="/100"
            lowerIsBetter
          />
          <Headline
            label="Total energy"
            baseline={data.baseline.total_energy_kwh}
            tejas={data.tejas.total_energy_kwh}
            unit="kWh"
            lowerIsBetter
          />
        </div>

        {/* Bar chart */}
        <ResponsiveContainer width="100%" height={200}>
          <BarChart
            data={chartData}
            margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
            barCategoryGap="30%"
            barGap={4}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="hsl(var(--border))"
              opacity={0.4}
            />
            <XAxis
              dataKey="metric"
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <Tooltip
              contentStyle={{
                background: "hsl(var(--popover))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                fontSize: 12,
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              iconType="square"
            />
            <Bar dataKey="Baseline" fill="#64748b" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Tejas" fill="#f59e0b" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        {/* Honest disclaimer */}
        <div className="flex gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/80">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-300">
              Estimated on synthetic data — not field results.
            </p>
            <p>{data.limitation}</p>
            <p className="text-amber-200/60">{data.energy_note}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

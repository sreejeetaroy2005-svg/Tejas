"use client";

/**
 * BacktestProofCard
 *
 * Before/after comparison of Baseline vs Tejas recommendations over the
 * 180-day synthetic history.
 *
 * Design changes (v2):
 *  - No green "X% better" badges — they implied certainty that isn't warranted.
 *    Instead, Baseline / Tejas values are shown side-by-side with a plain delta.
 *  - Added 180-day SPM line chart to show the optimizer adapts rather than
 *    picking a flat value.
 *  - Disclaimer shortened to 2 lines.
 *
 * Data comes from GET /api/backtest (falls back to mock data if offline).
 */

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { AlertTriangle, FlaskConical } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/types";

// ---------------------------------------------------------------------------
// Neutral delta cell — no colour coding, just numbers
// ---------------------------------------------------------------------------

function MetricRow({
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
  const delta = tejas - baseline;
  const sign = delta > 0.001 ? "+" : delta < -0.001 ? "" : "±";
  // Only colour the delta: green = direction consistent with lowerIsBetter goal
  const deltaColor =
    Math.abs(delta) < 0.001
      ? "text-muted-foreground"
      : (lowerIsBetter ? delta < 0 : delta > 0)
        ? "text-green-400"
        : "text-red-400";

  const fmt = (v: number) =>
    Math.abs(v) >= 1000
      ? v.toLocaleString("en-US", { maximumFractionDigits: 0 })
      : v.toFixed(Math.abs(v) < 10 ? 2 : 1);

  return (
    <div className="grid grid-cols-4 gap-2 text-xs py-1 border-b border-border/30 last:border-0">
      <span className="text-muted-foreground col-span-1">{label}</span>
      <span className="text-right font-mono">{fmt(baseline)} <span className="text-muted-foreground">{unit}</span></span>
      <span className="text-right font-mono">{fmt(tejas)} <span className="text-muted-foreground">{unit}</span></span>
      <span className={`text-right font-mono font-semibold ${deltaColor}`}>
        {sign}{fmt(delta)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bar chart data
// ---------------------------------------------------------------------------

function buildBarData(data: BacktestResponse) {
  return [
    {
      metric: "High-risk days",
      Baseline: data.baseline.high_risk_days,
      Tejas: data.tejas.high_risk_days,
    },
    {
      metric: "Avg risk",
      Baseline: parseFloat(data.baseline.avg_risk_score.toFixed(1)),
      Tejas: parseFloat(data.tejas.avg_risk_score.toFixed(1)),
    },
    {
      metric: "Energy (/100 kWh)",
      Baseline: parseFloat((data.baseline.total_energy_kwh / 100).toFixed(1)),
      Tejas: parseFloat((data.tejas.total_energy_kwh / 100).toFixed(1)),
    },
    {
      metric: "Oil (/100 bbl)",
      Baseline: parseFloat((data.baseline.total_oil_bbl / 100).toFixed(1)),
      Tejas: parseFloat((data.tejas.total_oil_bbl / 100).toFixed(1)),
    },
  ];
}

// ---------------------------------------------------------------------------
// SPM line chart data — sample every 3rd day to keep the chart readable
// ---------------------------------------------------------------------------

function buildSpmData(data: BacktestResponse) {
  return data.daily_tejas
    .filter((_, i) => i % 3 === 0)
    .map((row, i) => ({
      day: i * 3 + 1,
      "Tejas SPM": row.spm_used,
      "Baseline SPM": data.daily_baseline[i * 3]?.spm_used ?? null,
    }));
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

  const barData = buildBarData(data);
  const spmData = buildSpmData(data);
  const hasSpmData = data.daily_tejas.length > 0;
  const spm = data.spm_diagnostics;

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
              Offline — stored numbers
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-1">
          Both arms scored by the same simulator ·{" "}
          {data.date_range.start} → {data.date_range.end} · {data.n_days} days
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Metric table — neutral delta, no green % badges */}
        <div>
          <div className="grid grid-cols-4 gap-2 text-xs text-muted-foreground pb-1 border-b border-border/50 mb-1">
            <span>Metric</span>
            <span className="text-right">Baseline</span>
            <span className="text-right">Tejas</span>
            <span className="text-right">Delta</span>
          </div>
          <MetricRow label="High-risk days" baseline={data.baseline.high_risk_days} tejas={data.tejas.high_risk_days} unit="days" lowerIsBetter />
          <MetricRow label="Avg risk score" baseline={data.baseline.avg_risk_score} tejas={data.tejas.avg_risk_score} unit="/100" lowerIsBetter />
          <MetricRow label="Total oil" baseline={data.baseline.total_oil_bbl} tejas={data.tejas.total_oil_bbl} unit="bbl" lowerIsBetter={false} />
          <MetricRow label="Total energy" baseline={data.baseline.total_energy_kwh} tejas={data.tejas.total_energy_kwh} unit="kWh" lowerIsBetter />
          <div className="text-[10px] text-muted-foreground/60 pt-1">
            Avg SOR omitted — SOR depends on steam volume and well state, not pump SPM settings, so it is not a meaningful outcome of this comparison.
          </div>
        </div>

        {/* Two charts side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Bar chart */}
          <div>
            <p className="text-xs text-muted-foreground mb-1">Before / After</p>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={barData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }} barCategoryGap="28%" barGap={3}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.35} />
                <XAxis dataKey="metric" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={28} />
                <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: 11 }} />
                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 4 }} iconType="square" />
                <Bar dataKey="Baseline" fill="#64748b" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Tejas" fill="#f59e0b" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* SPM line chart */}
          <div>
            <p className="text-xs text-muted-foreground mb-1">
              Recommended SPM over 180 days
              {spm && (
                <span className="ml-1 text-amber-400/80">
                  (range {spm.min}–{spm.max}, mean {spm.mean})
                </span>
              )}
            </p>
            {hasSpmData ? (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={spmData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.35} />
                  <XAxis dataKey="day" tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} label={{ value: "Day", position: "insideBottomRight", offset: -4, fontSize: 9, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis domain={[3.5, 10.5]} tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} tickLine={false} axisLine={false} width={28} />
                  <Tooltip contentStyle={{ background: "hsl(var(--popover))", border: "1px solid hsl(var(--border))", borderRadius: "6px", fontSize: 11 }} />
                  <Legend wrapperStyle={{ fontSize: 10, paddingTop: 4 }} iconType="plainline" />
                  <ReferenceLine y={6.5} stroke="#94a3b8" strokeDasharray="4 4" strokeWidth={1} label={{ value: "optimal", position: "right", fontSize: 8, fill: "#94a3b8" }} />
                  <Line type="monotone" dataKey="Baseline SPM" stroke="#64748b" dot={false} strokeWidth={1.5} />
                  <Line type="monotone" dataKey="Tejas SPM" stroke="#f59e0b" dot={false} strokeWidth={1.5} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[180px] flex items-center justify-center text-xs text-muted-foreground">
                Run scripts/backtest.py to populate daily SPM data
              </div>
            )}
          </div>
        </div>

        {/* Honest disclaimer — 2 lines */}
        <div className="flex gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/80">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-300">
              Synthetic in-model projection — not a field result.
            </p>
            <p className="mt-0.5">{data.limitation}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

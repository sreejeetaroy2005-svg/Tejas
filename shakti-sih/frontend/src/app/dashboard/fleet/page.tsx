"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Droplets,
  ShieldAlert,
  Zap,
  WifiOff,
  ArrowUpDown,
  ChevronUp,
  ChevronDown,
  Activity,
  Thermometer,
} from "lucide-react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip as RechartTooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/kpi-card";
import { fetchFleetPriority, fetchFleetSummary } from "@/lib/api";
import type { FleetPriorityItem, FleetPriorityResponse, FleetSummaryResponse } from "@/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Risk colour helpers
// ---------------------------------------------------------------------------
function riskBadgeVariant(label: string): "safe" | "attention" | "danger" | "secondary" {
  if (label === "High") return "danger";
  if (label === "Medium") return "attention";
  return "safe";
}

function riskRowClass(label: string): string {
  if (label === "High")   return "bg-danger/5 hover:bg-danger/10";
  if (label === "Medium") return "bg-attention/5 hover:bg-attention/10";
  return "hover:bg-muted/40";
}

// ---------------------------------------------------------------------------
// Mini sparkline — last 7 oil readings synthesised from trend direction
// ---------------------------------------------------------------------------
function Sparkline({ trend, oil }: { trend: string; oil: number }) {
  const data = useMemo(() => {
    const base = Math.max(oil, 5);
    return Array.from({ length: 7 }, (_, i) => {
      const noise = (Math.sin(i * 1.3) * 0.05 + (trend === "declining" ? -0.04 * i : 0.01 * i));
      return { v: Math.max(0, base * (1 + noise)) };
    });
  }, [trend, oil]);

  const color = trend === "declining" ? "#ef4444" : "#22c55e";
  return (
    <ResponsiveContainer width={64} height={28}>
      <LineChart data={data} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <Line type="monotone" dataKey="v" stroke={color} dot={false} strokeWidth={1.5} />
        <RechartTooltip
          contentStyle={{ display: "none" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Sort helpers
// ---------------------------------------------------------------------------
type SortKey = "urgency_score" | "risk_score" | "oil_bpd" | "estimated_fillage_pct";

function sortItems(items: FleetPriorityItem[], key: SortKey, asc: boolean): FleetPriorityItem[] {
  return [...items].sort((a, b) => {
    const diff = (a[key] as number) - (b[key] as number);
    return asc ? diff : -diff;
  });
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function FleetPage() {
  const router = useRouter();
  const [priority, setPriority] = useState<FleetPriorityResponse | null>(null);
  const [summary, setSummary] = useState<FleetSummaryResponse | null>(null);
  const [isMock, setIsMock] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>("urgency_score");
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    Promise.all([fetchFleetPriority(), fetchFleetSummary()]).then(
      ([p, s]) => {
        setPriority(p.data);
        setSummary(s.data);
        setIsMock(p.isMock || s.isMock);
        setLoading(false);
      }
    );
  }, []);

  function handleSort(key: SortKey) {
    if (key === sortKey) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(false); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (k !== sortKey) return <ArrowUpDown className="h-3 w-3 ml-1 opacity-40" />;
    return sortAsc
      ? <ChevronUp className="h-3 w-3 ml-1" />
      : <ChevronDown className="h-3 w-3 ml-1" />;
  }

  const sorted = useMemo(
    () => priority ? sortItems(priority.wells, sortKey, sortAsc) : [],
    [priority, sortKey, sortAsc]
  );

  function openWell(wellId: string) {
    router.push(`/dashboard?well=${wellId}`);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Fleet Overview</h2>
          <p className="text-sm text-muted-foreground">
            {summary ? `${summary.total_wells} wells` : "—"} · all data synthetic
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isMock && (
            <Badge variant="attention" className="gap-1 text-xs">
              <WifiOff className="h-3 w-3" />
              Demo data
            </Badge>
          )}
        </div>
      </div>

      {/* Summary KPI row */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <KpiCard
            title="Total Oil"
            value={summary.total_oil_bpd.toFixed(0)}
            unit="bbl/day"
            icon={Droplets}
            severity={summary.total_oil_bpd > 500 ? "safe" : "attention"}
            subtitle={`${summary.total_wells} wells`}
          />
          <KpiCard
            title="High-Risk Wells"
            value={summary.wells_high_risk}
            unit=""
            icon={ShieldAlert}
            severity={summary.wells_high_risk > 0 ? "danger" : "safe"}
            subtitle={`${summary.wells_medium_risk} medium`}
          />
          <KpiCard
            title="Total Energy"
            value={summary.total_energy_kwh.toFixed(0)}
            unit="kWh"
            icon={Zap}
            severity="neutral"
            subtitle="fleet total"
          />
          <KpiCard
            title="Avg Risk"
            value={summary.avg_risk_score.toFixed(1)}
            unit="/100"
            icon={Activity}
            severity={
              summary.avg_risk_score > 65 ? "danger"
              : summary.avg_risk_score > 35 ? "attention"
              : "safe"
            }
            subtitle="fleet average"
          />
          <KpiCard
            title="Producing"
            value={summary.wells_producing}
            unit="wells"
            icon={Thermometer}
            severity="safe"
            subtitle={`${summary.wells_injecting} injecting`}
          />
          <KpiCard
            title="Low Risk"
            value={summary.wells_low_risk}
            unit="wells"
            icon={ShieldAlert}
            severity="safe"
            subtitle="no action needed"
          />
        </div>
      )}

      {/* Priority table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">
            Well Priority — click a row to open the well detail view
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="text-left px-4 py-2 font-medium">Well</th>
                  <th className="text-left px-3 py-2 font-medium">Stage</th>
                  <th
                    className="text-right px-3 py-2 font-medium cursor-pointer select-none hover:text-foreground"
                    onClick={() => handleSort("urgency_score")}
                  >
                    <span className="flex items-center justify-end">Urgency<SortIcon k="urgency_score" /></span>
                  </th>
                  <th
                    className="text-right px-3 py-2 font-medium cursor-pointer select-none hover:text-foreground"
                    onClick={() => handleSort("oil_bpd")}
                  >
                    <span className="flex items-center justify-end">Oil bbl/d<SortIcon k="oil_bpd" /></span>
                  </th>
                  <th
                    className="text-right px-3 py-2 font-medium cursor-pointer select-none hover:text-foreground"
                    onClick={() => handleSort("estimated_fillage_pct")}
                  >
                    <span className="flex items-center justify-end">Fillage<SortIcon k="estimated_fillage_pct" /></span>
                  </th>
                  <th className="text-right px-3 py-2 font-medium">Days Δ</th>
                  <th className="text-center px-3 py-2 font-medium">Risk</th>
                  <th className="text-left px-3 py-2 font-medium hidden lg:table-cell">ML condition</th>
                  <th className="px-3 py-2 font-medium hidden md:table-cell">Trend</th>
                  <th className="text-left px-4 py-2 font-medium hidden xl:table-cell">Reason</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td colSpan={10} className="px-4 py-2">
                          <div className="h-4 bg-muted/50 rounded animate-pulse" />
                        </td>
                      </tr>
                    ))
                  : sorted.map((well) => (
                      <tr
                        key={well.well_id}
                        className={cn(
                          "border-b border-border/30 cursor-pointer transition-colors",
                          riskRowClass(well.risk_label)
                        )}
                        onClick={() => openWell(well.well_id)}
                      >
                        <td className="px-4 py-2 font-semibold">{well.well_id}</td>
                        <td className="px-3 py-2 text-muted-foreground capitalize">{well.css_stage}</td>
                        <td className="px-3 py-2 text-right font-mono">{well.urgency_score.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right font-mono">{well.oil_bpd.toFixed(1)}</td>
                        <td className="px-3 py-2 text-right font-mono">{well.estimated_fillage_pct.toFixed(0)}%</td>
                        <td className="px-3 py-2 text-right font-mono text-muted-foreground">{well.days_since_steam_injection}</td>
                        <td className="px-3 py-2 text-center">
                          <Badge variant={riskBadgeVariant(well.risk_label)} className="text-[10px] px-1.5">
                            {well.risk_label}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-muted-foreground hidden lg:table-cell truncate max-w-[140px]">
                          {well.ml_condition ?? "—"}
                        </td>
                        <td className="px-3 py-2 hidden md:table-cell">
                          <Sparkline trend={well.forecast_trend} oil={well.oil_bpd} />
                        </td>
                        <td className="px-4 py-2 text-muted-foreground hidden xl:table-cell max-w-[260px] truncate">
                          {well.reason}
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Well-grid tiles */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Well Grid</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {sorted.map((well) => (
            <div
              key={well.well_id}
              onClick={() => openWell(well.well_id)}
              className={cn(
                "rounded-lg border p-3 cursor-pointer transition-colors space-y-2",
                well.risk_label === "High"
                  ? "border-danger/40 bg-danger/5 hover:bg-danger/10"
                  : well.risk_label === "Medium"
                    ? "border-attention/40 bg-attention/5 hover:bg-attention/10"
                    : "border-border bg-card hover:bg-muted/30"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold">{well.well_id}</span>
                <Badge variant={riskBadgeVariant(well.risk_label)} className="text-[10px] px-1">
                  {well.risk_label}
                </Badge>
              </div>
              <Sparkline trend={well.forecast_trend} oil={well.oil_bpd} />
              <div className="text-[10px] text-muted-foreground">
                <div>{well.oil_bpd.toFixed(0)} bbl/d</div>
                <div className="capitalize">{well.css_stage}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground text-center pb-4">
        All data is synthetic demonstration data — not real Oil India field data.
      </p>
    </div>
  );
}

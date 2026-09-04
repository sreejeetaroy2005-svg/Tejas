"use client";

import { useEffect, useState } from "react";
import {
  Settings2,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Minus,
  WifiOff,
  Calendar,
  Target,
  Zap,
  Droplets,
  ShieldCheck,
  Lightbulb,
  type LucideIcon,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { TooltipProvider } from "@/components/ui/tooltip";
import { InfoTooltip } from "@/components/info-tooltip";
import { runOptimization } from "@/lib/api";
import { mockOptimizeResponse } from "@/lib/mock-data";
import { TOOLTIPS } from "@/lib/tooltips";
import type { OptimizeResponse } from "@/types";
import { cn } from "@/lib/utils";

export default function OptimizePage() {
  const [data, setData] = useState<OptimizeResponse>(mockOptimizeResponse);
  const [loading, setLoading] = useState(true);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const result = await runOptimization("BGW-01");
      if (!result.isMock) {
        setData(result.data);
        setApiDown(false);
      } else {
        setData(mockOptimizeResponse);
        setApiDown(true);
      }
      setLoading(false);
    }
    load();
  }, []);

  const current = data.current;
  const best = data.best_option;

  // Delta helpers
  function delta(current: number, recommended: number) {
    return recommended - current;
  }

  const cssAction = (stage: string) => {
    const map: Record<string, string> = {
      injection: "Continue injection",
      soak: "Continue soak",
      production: "Schedule next steam injection",
    };
    return map[stage] ?? stage;
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Optimization</h2>
          <p className="text-sm text-muted-foreground">
            Grid-search recommendation for {data.well_id} — evaluated{" "}
            <span className="text-foreground font-medium">
              {data.alternatives_evaluated.toLocaleString()}
            </span>{" "}
            operating points
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
            Composite: {best.composite_score.toFixed(2)}
          </Badge>
        </div>
      </div>

      {/* Settings comparison — side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Current settings */}
        <Card className="bg-card">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Settings2 className="h-4 w-4 text-muted-foreground" />
              Current Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <SettingRow
                label={<>SPM<InfoTooltip text={TOOLTIPS.spm} /></>}
                value={Number(current.spm)}
                unit="SPM"
                loading={loading}
              />
              <SettingRow
                label={<>VFD<InfoTooltip text={TOOLTIPS.vfd} /></>}
                value={Number(current.vfd_frequency_hz)}
                unit="Hz"
                loading={loading}
              />
              <SettingRow
                label={<>Steam Volume<InfoTooltip text={TOOLTIPS.steamVolume} /></>}
                value={Number(current.steam_volume_tonnes)}
                unit="tonnes"
                loading={loading}
              />
              <div className="pt-2 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    CSS Stage
                  </span>
                  <Badge variant="secondary" className="capitalize text-xs">
                    {String(current.css_stage)}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  {cssAction(String(current.css_stage))}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recommended settings */}
        <Card className="bg-card border-safe/20">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-medium text-safe">
              <Target className="h-4 w-4" />
              Recommended Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <SettingRow
                label={<>SPM<InfoTooltip text={TOOLTIPS.spm} /></>}
                value={best.spm}
                unit="SPM"
                loading={loading}
                highlight
                delta={delta(Number(current.spm), best.spm)}
                deltaUnit=""
              />
              <SettingRow
                label={<>VFD<InfoTooltip text={TOOLTIPS.vfd} /></>}
                value={best.vfd_frequency_hz}
                unit="Hz"
                loading={loading}
                highlight
                delta={delta(Number(current.vfd_frequency_hz), best.vfd_frequency_hz)}
                deltaUnit=""
              />
              <SettingRow
                label={<>Steam Volume<InfoTooltip text={TOOLTIPS.steamVolume} /></>}
                value={best.steam_volume_tonnes}
                unit="tonnes"
                loading={loading}
                highlight
                delta={
                  best.steam_volume_tonnes > 0
                    ? delta(Number(current.steam_volume_tonnes), best.steam_volume_tonnes)
                    : undefined
                }
                deltaUnit=""
              />
              <div className="pt-2 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">
                    Next CSS Action
                  </span>
                  <Badge variant="safe" className="text-xs">
                    Schedule injection
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Inject {best.steam_volume_tonnes} tonnes at optimal SPM/VFD
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* KPI comparison table */}
      <Card className="bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Expected KPI Comparison
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Current performance vs projected results after applying recommended
            settings
          </p>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] text-muted-foreground uppercase tracking-wide border-b border-border">
                    <th className="text-left pb-2 font-medium">Metric</th>
                    <th className="text-right pb-2 font-medium">Current</th>
                    <th className="text-center pb-2 font-medium w-8" />
                    <th className="text-right pb-2 font-medium">Recommended</th>
                    <th className="text-right pb-2 font-medium">Change</th>
                  </tr>
                </thead>
                <tbody>
                  <KpiRow
                    icon={Droplets}
                    label={<>Oil Production<InfoTooltip text={TOOLTIPS.oilProduction} /></>}
                    current={Number(current.oil_bpd)}
                    recommended={best.projected_oil_bpd}
                    unit="bbl/day"
                    higherIsBetter
                  />
                  <KpiRow
                    icon={Zap}
                    label={<>Energy<InfoTooltip text={TOOLTIPS.energy} /></>}
                    current={0}
                    recommended={best.projected_energy_kwh}
                    unit="kWh"
                    higherIsBetter={false}
                    hideCurrent
                  />
                  <KpiRow
                    icon={Droplets}
                    label={<>Steam-Oil Ratio<InfoTooltip text={TOOLTIPS.sor} /></>}
                    current={Number(current.oil_bpd) > 0 ? 0 : 0}
                    recommended={best.projected_sor}
                    unit="t/bbl"
                    higherIsBetter={false}
                    hideCurrent
                  />
                  <KpiRow
                    icon={ShieldCheck}
                    label={<>Risk Score<InfoTooltip text={TOOLTIPS.rodFloatingRisk} /></>}
                    current={Number(current.risk_score)}
                    recommended={best.risk_score}
                    unit="/ 100"
                    higherIsBetter={false}
                    isRisk
                    currentLabel={String(current.risk_label)}
                    recommendedLabel={best.risk_label}
                  />
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Composite score breakdown */}
      <Card className="bg-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">
            Score Breakdown
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            How the composite score is calculated:{" "}
            <span className="text-foreground">
              production − 0.35×SOR − 0.25×energy − 0.50×risk
            </span>
          </p>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <ScoreCard
                label={<>Production<InfoTooltip text={TOOLTIPS.productionScore} /></>}
                value={Number(data.score_breakdown.production_score)}
                weight=""
                positive
              />
              <ScoreCard
                label={<>SOR Penalty<InfoTooltip text={TOOLTIPS.sorPenalty} /></>}
                value={Number(data.score_breakdown.sor_penalty)}
                weight="× 0.35"
                positive={false}
              />
              <ScoreCard
                label={<>Energy Penalty<InfoTooltip text={TOOLTIPS.energyPenalty} /></>}
                value={Number(data.score_breakdown.energy_penalty)}
                weight="× 0.25"
                positive={false}
              />
              <ScoreCard
                label={<>Risk Penalty<InfoTooltip text={TOOLTIPS.riskPenalty} /></>}
                value={Number(data.score_breakdown.risk_penalty)}
                weight="× 0.50"
                positive={false}
              />
              <div className="rounded-lg border border-safe/30 bg-safe/5 p-3 text-center">
                <p className="text-[11px] text-muted-foreground mb-1 flex justify-center items-center">
                  Composite<InfoTooltip text={TOOLTIPS.compositeScore} />
                </p>
                <p className="text-xl font-bold text-safe font-mono">
                  {Number(data.score_breakdown.composite).toFixed(3)}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Why? explanation panel */}
      <Card className="bg-card border-accent/20">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-accent">
            <Lightbulb className="h-4 w-4" />
            Why this recommendation?
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : (
            <div className="space-y-3">
              <p className="text-sm leading-relaxed text-foreground">
                {data.explanation}
              </p>
              <div className="rounded-md border border-border p-3">
                <p className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium mb-2">
                  Contributing Factors to Risk Reduction
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(best.contributing_factors)
                    .sort((a, b) => b[1] - a[1])
                    .map(([key, value]) => {
                      const labels: Record<string, string> = {
                        fillage: "Pump Fillage",
                        viscosity: "Oil Viscosity",
                        spm_excess: "Excess SPM",
                        motor_current: "Motor Current",
                      };
                      return (
                        <div key={key} className="text-center">
                          <p className="text-xs text-muted-foreground">
                            {labels[key] ?? key}
                          </p>
                          <p
                            className={cn(
                              "text-lg font-bold font-mono",
                              value > 15
                                ? "text-danger"
                                : value > 8
                                  ? "text-attention"
                                  : "text-safe",
                            )}
                          >
                            {value.toFixed(1)}
                          </p>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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

function riskLabel(label: string): "safe" | "attention" | "danger" {
  if (label === "Low") return "safe";
  if (label === "Medium") return "attention";
  return "danger";
}

function SettingRow({
  label,
  value,
  unit,
  loading,
  highlight = false,
  delta,
  deltaUnit,
}: {
  label: React.ReactNode;
  value: number;
  unit: string;
  loading: boolean;
  highlight?: boolean;
  delta?: number;
  deltaUnit?: string;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-5 w-24" />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "text-lg font-bold font-mono",
            highlight ? "text-safe" : "text-foreground",
          )}
        >
          {value.toFixed(1)}
        </span>
        <span className="text-xs text-muted-foreground">{unit}</span>
        {delta !== undefined && delta !== 0 && (
          <span
            className={cn(
              "text-[11px] font-mono px-1.5 py-0.5 rounded",
              delta < 0
                ? "bg-safe/10 text-safe"
                : "bg-danger/10 text-danger",
            )}
          >
            {delta > 0 ? "+" : ""}
            {delta.toFixed(1)}
            {deltaUnit}
          </span>
        )}
      </div>
    </div>
  );
}

function KpiRow({
  icon: Icon,
  label,
  current,
  recommended,
  unit,
  higherIsBetter,
  isRisk = false,
  hideCurrent = false,
  currentLabel,
  recommendedLabel,
}: {
  icon: LucideIcon;
  label: React.ReactNode;
  current: number;
  recommended: number;
  unit: string;
  higherIsBetter: boolean;
  isRisk?: boolean;
  hideCurrent?: boolean;
  currentLabel?: string;
  recommendedLabel?: string;
}) {
  const diff = recommended - current;
  const improved =
    higherIsBetter ? diff > 0 : diff < 0;
  const pctChange = current !== 0 ? Math.abs(diff / current) * 100 : null;

  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="py-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5" />
          {label}
        </div>
      </td>
      <td className="py-3 text-right">
        {hideCurrent ? (
          <span className="text-xs text-muted-foreground">—</span>
        ) : (
          <span className="text-sm font-mono">
            {current.toFixed(isRisk ? 1 : 2)}
          </span>
        )}
        {currentLabel && (
          <Badge
            variant={riskLabel(currentLabel) as "safe" | "attention" | "danger"}
            className="ml-1 text-[10px]"
          >
            {currentLabel}
          </Badge>
        )}
      </td>
      <td className="py-3 text-center">
        <ArrowRight className="h-3 w-3 text-muted-foreground mx-auto" />
      </td>
      <td className="py-3 text-right">
        <span
          className={cn(
            "text-sm font-mono font-medium",
            isRisk
              ? riskLabel(recommendedLabel ?? "") === "safe"
                ? "text-safe"
                : riskLabel(recommendedLabel ?? "") === "attention"
                  ? "text-attention"
                  : "text-danger"
              : "text-foreground",
          )}
        >
          {recommended.toFixed(isRisk ? 1 : 2)}
        </span>
        {recommendedLabel && (
          <Badge
            variant={
              riskLabel(recommendedLabel) as "safe" | "attention" | "danger"
            }
            className="ml-1 text-[10px]"
          >
            {recommendedLabel}
          </Badge>
        )}
      </td>
      <td className="py-3 text-right">
        {diff !== 0 && !hideCurrent && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-xs font-mono",
              improved ? "text-safe" : "text-danger",
            )}
          >
            {improved ? (
              <TrendingUp className="h-3 w-3" />
            ) : (
              <TrendingDown className="h-3 w-3" />
            )}
            {pctChange !== null
              ? `${pctChange.toFixed(0)}%`
              : diff > 0
                ? `+${diff.toFixed(1)}`
                : diff.toFixed(1)}
          </span>
        )}
        {(diff === 0 || hideCurrent) && (
          <Minus className="h-3 w-3 text-muted-foreground mx-auto" />
        )}
      </td>
    </tr>
  );
}

function ScoreCard({
  label,
  value,
  weight,
  positive,
}: {
  label: React.ReactNode;
  value: number;
  weight: string;
  positive: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3 text-center",
        positive ? "border-safe/20 bg-safe/5" : "border-danger/20 bg-danger/5",
      )}
    >
      <p className="text-[11px] text-muted-foreground mb-1">{label}</p>
      <p
        className={cn(
          "text-lg font-bold font-mono",
          positive ? "text-safe" : "text-danger",
        )}
      >
        {positive ? "+" : "−"}
        {value.toFixed(3)}
      </p>
      {weight && (
        <p className="text-[10px] text-muted-foreground mt-0.5">{weight}</p>
      )}
    </div>
  );
}

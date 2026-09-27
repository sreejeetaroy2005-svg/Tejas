"use client";

import { AlertTriangle, ShieldCheck, ShieldAlert } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/info-tooltip";
import { TOOLTIPS } from "@/lib/tooltips";
import { cn } from "@/lib/utils";

interface RiskAlertProps {
  riskScore: number;
  riskLabel: string;
  riskFactors: Record<string, number>;
  loading?: boolean;
  mlCondition?: string;
  mlConfidence?: number;
  diagnosisSource?: string;
  mlMatchNote?: string;
}

const FACTOR_LABELS: Record<string, string> = {
  fillage: "Pump Fillage",
  viscosity: "Oil Viscosity",
  spm_excess: "Excess SPM",
  motor_current: "Motor Current",
};

const FACTOR_TOOLTIPS: Record<string, string> = {
  fillage: TOOLTIPS.fillage,
  viscosity: TOOLTIPS.viscosity,
  spm_excess: TOOLTIPS.spm,
  motor_current: TOOLTIPS.motorCurrent,
};

function riskColor(label: string) {
  if (label === "Low" || label === "Normal") return "safe";
  if (label === "Medium" || label === "Fluid Pound" || label === "Gas Interference" || label === "Gas Interference (low confidence)") return "attention";
  return "danger";
}

function RiskGauge({ score }: { score: number }) {
  const color =
    score <= 35 ? "bg-safe" : score <= 65 ? "bg-attention" : "bg-danger";

  return (
    <div className="relative h-3 w-full rounded-full bg-muted overflow-hidden">
      <div
        className={cn("h-full rounded-full transition-all duration-500", color)}
        style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
      />
    </div>
  );
}

export function RiskAlert({
  riskScore,
  riskLabel,
  riskFactors,
  loading = false,
  mlCondition,
  mlConfidence,
  diagnosisSource,
  mlMatchNote,
}: RiskAlertProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader>
          <CardTitle>
            <Skeleton className="h-5 w-40" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-4 w-32" />
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  const hasMl = diagnosisSource === "ml_classifier" && mlCondition;
  const primaryLabel = hasMl ? mlCondition : riskLabel;
  const color = riskColor(primaryLabel);
  const Icon = (primaryLabel === "Low" || primaryLabel === "Normal") ? ShieldCheck : AlertTriangle;
  const sortedFactors = Object.entries(riskFactors).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <Card className="bg-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Icon
            className={cn(
              "h-5 w-5",
              color === "safe" && "text-safe",
              color === "attention" && "text-attention",
              color === "danger" && "text-danger",
            )}
          />
          {hasMl ? "ML Diagnosis" : "Risk Assessment"}
          <Badge variant={color as "safe" | "attention" | "danger"}>
            {primaryLabel}
          </Badge>
          {hasMl && (
            <Badge variant="secondary" className="ml-1 text-[10px] uppercase">
              ML
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score + gauge */}
        <div>
          <div className="flex items-baseline justify-between mb-1">
            <span className="text-3xl font-bold">{riskScore.toFixed(1)}</span>
            <span className="text-xs text-muted-foreground">/ 100</span>
          </div>
          <RiskGauge score={riskScore} />
        </div>

        {/* Contributing factors */}
        <div>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Contributing Factors
          </h4>
          <div className="space-y-2">
            {sortedFactors.map(([key, value]) => (
              <div key={key} className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground w-32 shrink-0 flex items-center">
                  {FACTOR_LABELS[key] ?? key}
                  <InfoTooltip text={FACTOR_TOOLTIPS[key] ?? ""} />
                </span>
                <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      value > 15 ? "bg-danger" : value > 8 ? "bg-attention" : "bg-safe",
                    )}
                    style={{ width: `${Math.min(100, (value / 35) * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-muted-foreground w-10 text-right">
                  {value.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Info note */}
        <div className="space-y-1.5 pt-2 border-t border-border">
          {hasMl && (
            <p className="text-[11px] text-muted-foreground leading-relaxed">
              <span className="font-medium text-foreground">Source: ML Classifier</span> — 
              {' '}Condition detected from nearest-neighbour dynacard match ({mlConfidence ? `${(mlConfidence * 100).toFixed(0)}% confidence` : 'matched'})
              {mlMatchNote && (
                <span className="block mt-0.5 opacity-80 text-[10px]">{mlMatchNote}</span>
              )}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            <span className="font-medium text-foreground">Rule-based proxy score: {riskScore.toFixed(1)}/100 ({riskLabel})</span>. 
            Weights: fillage 35%, viscosity 30%, excess SPM 20%, motor current 15%.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

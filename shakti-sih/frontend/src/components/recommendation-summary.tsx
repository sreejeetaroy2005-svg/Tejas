"use client";

import { Lightbulb, ArrowRight, Loader2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/info-tooltip";
import { TOOLTIPS } from "@/lib/tooltips";
import type { OptimizeResponse } from "@/types";

interface RecommendationSummaryProps {
  data: OptimizeResponse | null;
  loading?: boolean;
  error?: boolean;
}

export function RecommendationSummary({
  data,
  loading = false,
  error = false,
}: RecommendationSummaryProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Skeleton className="h-5 w-5" />
            <Skeleton className="h-5 w-48" />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card className="bg-card border-danger/30">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-muted-foreground">
            <Lightbulb className="h-5 w-5" />
            Latest Recommendation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Optimization data unavailable. Start the backend to get
            recommendations.
          </p>
        </CardContent>
      </Card>
    );
  }

  const best = data.best_option;
  const current = data.current;

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Lightbulb className="h-5 w-5 text-attention" />
          Latest Recommendation
          <Badge variant="secondary">
            {data.alternatives_evaluated.toLocaleString()} options evaluated
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key parameter changes */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-muted p-3">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wide flex items-center">
              SPM<InfoTooltip text={TOOLTIPS.spm} />
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm font-mono">
                {Number(current.spm).toFixed(1)}
              </span>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm font-mono font-bold text-safe">
                {best.spm.toFixed(1)}
              </span>
            </div>
          </div>
          <div className="rounded-lg bg-muted p-3">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wide flex items-center">
              VFD<InfoTooltip text={TOOLTIPS.vfd} />
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm font-mono">
                {Number(current.vfd_frequency_hz).toFixed(1)} Hz
              </span>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm font-mono font-bold text-safe">
                {best.vfd_frequency_hz.toFixed(1)} Hz
              </span>
            </div>
          </div>
          <div className="rounded-lg bg-muted p-3">
            <p className="text-[11px] text-muted-foreground uppercase tracking-wide flex items-center">
              Risk<InfoTooltip text={TOOLTIPS.rodFloatingRisk} />
            </p>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm font-mono">
                {Number(current.risk_score).toFixed(1)}
              </span>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm font-mono font-bold text-safe">
                {best.risk_score.toFixed(1)}
              </span>
            </div>
          </div>
        </div>

        {/* Explanation */}
        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-sm text-foreground leading-relaxed">
            {data.explanation}
          </p>
        </div>

        <p className="text-[11px] text-muted-foreground">
          {data.data_note}
        </p>
      </CardContent>
    </Card>
  );
}

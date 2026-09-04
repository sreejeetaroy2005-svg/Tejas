"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTooltip } from "@/components/info-tooltip";
import { cn } from "@/lib/utils";

interface FillageGaugeProps {
  value: number; // 0–100
  loading?: boolean;
}

function getSeverity(pct: number): "safe" | "attention" | "danger" {
  if (pct >= 60) return "safe";
  if (pct >= 40) return "attention";
  return "danger";
}

function getSeverityColor(severity: "safe" | "attention" | "danger") {
  if (severity === "safe") return "#22c55e";
  if (severity === "attention") return "#f59e0b";
  return "#ef4444";
}

function getLabel(pct: number): string {
  if (pct >= 80) return "Excellent fillage";
  if (pct >= 60) return "Good fillage";
  if (pct >= 40) return "Low fillage — pump undersized or gas interference";
  return "Critical — severe pump-off condition";
}

export function FillageGauge({ value, loading = false }: FillageGaugeProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-40" />
        </CardHeader>
        <CardContent className="flex justify-center">
          <Skeleton className="h-[140px] w-[200px]" />
        </CardContent>
      </Card>
    );
  }

  const severity = getSeverity(value);
  const color = getSeverityColor(severity);
  const label = getLabel(value);

  // SVG arc gauge — 180° semicircle
  const radius = 70;
  const strokeWidth = 14;
  const cx = 90;
  const cy = 80;
  const circumference = Math.PI * radius; // half-circle arc length
  const offset = circumference - (value / 100) * circumference;

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium flex items-center">Pump Fillage<InfoTooltip text="How full the pump barrel gets each stroke — low fillage wastes energy and wears rods faster." /></CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Percentage of pump barrel filled with fluid each stroke
        </p>
      </CardHeader>
      <CardContent className="flex flex-col items-center">
        <svg width="180" height="110" viewBox="0 0 180 110">
          {/* Background arc */}
          <path
            d="M 10 80 A 70 70 0 0 1 170 80"
            fill="none"
            stroke="#1e293b"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Value arc */}
          <path
            d="M 10 80 A 70 70 0 0 1 170 80"
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-700 ease-out"
          />
          {/* Center text */}
          <text
            x={cx}
            y={cy - 8}
            textAnchor="middle"
            className="fill-foreground"
            fontSize="28"
            fontWeight="bold"
            fontFamily="var(--font-geist-mono), monospace"
          >
            {value.toFixed(0)}%
          </text>
          <text
            x={cx}
            y={cy + 12}
            textAnchor="middle"
            className="fill-muted-foreground"
            fontSize="10"
          >
            fillage
          </text>
        </svg>
        <p
          className={cn(
            "text-xs text-center mt-1 max-w-[200px]",
            severity === "safe" && "text-safe",
            severity === "attention" && "text-attention",
            severity === "danger" && "text-danger",
          )}
        >
          {label}
        </p>
        {/* Threshold markers */}
        <div className="flex items-center gap-3 mt-3 text-[10px] text-muted-foreground">
          <div className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full bg-danger" />
            <span>&lt; 40%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full bg-attention" />
            <span>40–60%</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full bg-safe" />
            <span>&gt; 60%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

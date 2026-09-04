"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface ThermalStatCardProps {
  label: React.ReactNode;
  value: number;
  unit: string;
  icon: LucideIcon;
  loading?: boolean;
  severity?: "safe" | "attention" | "danger" | "neutral";
  subtitle?: React.ReactNode;
}

export function ThermalStatCard({
  label,
  value,
  unit,
  icon: Icon,
  loading = false,
  severity = "neutral",
  subtitle,
}: ThermalStatCardProps) {
  const severityColors = {
    safe: "text-safe",
    attention: "text-attention",
    danger: "text-danger",
    neutral: "text-foreground",
  };

  const severityBorders = {
    safe: "border-safe/20",
    attention: "border-attention/20",
    danger: "border-danger/20",
    neutral: "border-border",
  };

  if (loading) {
    return (
      <Card className="bg-card p-4">
        <Skeleton className="h-4 w-24 mb-2" />
        <Skeleton className="h-8 w-20 mb-1" />
        <Skeleton className="h-3 w-16" />
      </Card>
    );
  }

  return (
    <Card
      className={cn(
        "bg-card p-4 border transition-colors",
        severityBorders[severity],
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] text-muted-foreground uppercase tracking-wide font-medium">
          {label}
        </span>
        <Icon className={cn("h-3.5 w-3.5", severityColors[severity])} />
      </div>
      <p className={cn("text-2xl font-bold font-mono", severityColors[severity])}>
        {value >= 1000
          ? `${(value / 1000).toFixed(1)}k`
          : value.toFixed(value % 1 === 0 ? 0 : 1)}
        <span className="text-xs font-normal text-muted-foreground ml-1">{unit}</span>
      </p>
      {subtitle && (
        <p className="text-[10px] text-muted-foreground mt-1">{subtitle}</p>
      )}
    </Card>
  );
}

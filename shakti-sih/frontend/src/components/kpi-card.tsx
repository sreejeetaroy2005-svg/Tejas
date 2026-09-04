"use client";

import { type LucideIcon } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: React.ReactNode;
  value: number | string;
  unit: string;
  icon: LucideIcon;
  loading?: boolean;
  /** Visual severity: safe (green), attention (amber), danger (red) */
  severity?: "safe" | "attention" | "danger" | "neutral";
  /** Optional subtitle text below the value */
  subtitle?: React.ReactNode;
}

const severityColors = {
  safe: "text-safe",
  attention: "text-attention",
  danger: "text-danger",
  neutral: "text-foreground",
};

export function KpiCard({
  title,
  value,
  unit,
  icon: Icon,
  loading = false,
  severity = "neutral",
  subtitle,
}: KpiCardProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-4 w-20" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-24 mb-1" />
          <Skeleton className="h-3 w-16" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className={cn("text-2xl font-bold", severityColors[severity])}>
          {typeof value === "number" ? value.toLocaleString() : value}
          <span className="text-sm font-normal text-muted-foreground ml-1.5">
            {unit}
          </span>
        </div>
        {subtitle && (
          <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

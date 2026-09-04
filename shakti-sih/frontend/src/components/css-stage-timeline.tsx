"use client";

import type { HistoryPoint } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface CssStageTimelineProps {
  data: HistoryPoint[];
  loading: boolean;
}

const STAGE_CONFIG: Record<string, { color: string; label: string; bgClass: string }> = {
  injection: {
    color: "#3b82f6",
    label: "Injection",
    bgClass: "bg-blue-500",
  },
  soak: {
    color: "#a855f7",
    label: "Soak",
    bgClass: "bg-purple-500",
  },
  production: {
    color: "#f59e0b",
    label: "Production",
    bgClass: "bg-amber-500",
  },
};

interface PhaseBlock {
  stage: string;
  startDate: string;
  endDate: string;
  days: number;
}

function aggregateStages(data: HistoryPoint[]): PhaseBlock[] {
  if (!data.length) return [];
  const blocks: PhaseBlock[] = [];
  let current = data[0];
  let count = 1;

  for (let i = 1; i < data.length; i++) {
    if (data[i].css_stage === current.css_stage) {
      count++;
    } else {
      blocks.push({
        stage: current.css_stage,
        startDate: current.date,
        endDate: data[i - 1].date,
        days: count,
      });
      current = data[i];
      count = 1;
    }
  }
  blocks.push({
    stage: current.css_stage,
    startDate: current.date,
    endDate: data[data.length - 1].date,
    days: count,
  });
  return blocks;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function CssStageTimeline({ data, loading }: CssStageTimelineProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-12 w-full" />
        </CardContent>
      </Card>
    );
  }

  const blocks = aggregateStages(data);
  const totalDays = blocks.reduce((sum, b) => sum + b.days, 0);

  return (
    <Card className="bg-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">
          CSS Stage Timeline
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Cyclic Steam Stimulation phases over the last {totalDays} days
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Timeline bar */}
        <div className="flex h-8 rounded-lg overflow-hidden border border-border">
          {blocks.map((block, i) => {
            const config = STAGE_CONFIG[block.stage] ?? {
              color: "#64748b",
              label: block.stage,
              bgClass: "bg-gray-500",
            };
            const pct = (block.days / totalDays) * 100;
            return (
              <div
                key={i}
                className={`${config.bgClass} relative group flex items-center justify-center transition-opacity hover:opacity-90`}
                style={{ width: `${pct}%` }}
              >
                {pct > 8 && (
                  <span className="text-[10px] font-medium text-white/90 truncate px-1">
                    {config.label}
                  </span>
                )}
                {/* Tooltip on hover */}
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 hidden group-hover:block z-10">
                  <div className="rounded-md border border-border bg-card px-2 py-1 shadow-lg text-[10px] whitespace-nowrap">
                    <p className="font-medium">{config.label}</p>
                    <p className="text-muted-foreground">
                      {block.days}d · {formatDate(block.startDate)} →{" "}
                      {formatDate(block.endDate)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-[11px] text-muted-foreground">
          {Object.entries(STAGE_CONFIG).map(([key, config]) => {
            const total = blocks
              .filter((b) => b.stage === key)
              .reduce((s, b) => s + b.days, 0);
            return (
              <div key={key} className="flex items-center gap-1.5">
                <div
                  className="h-2.5 w-2.5 rounded-sm"
                  style={{ backgroundColor: config.color }}
                />
                <span>
                  {config.label}: {total} days
                </span>
              </div>
            );
          })}
        </div>

        {/* Phase details table */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {blocks.map((block, i) => {
            const config = STAGE_CONFIG[block.stage] ?? {
              color: "#64748b",
              label: block.stage,
            };
            return (
              <div
                key={i}
                className="rounded-md border border-border p-2 flex items-center gap-2"
              >
                <div
                  className="h-8 w-1 rounded-full flex-shrink-0"
                  style={{ backgroundColor: config.color }}
                />
                <div className="min-w-0">
                  <p className="text-xs font-medium truncate">{config.label}</p>
                  <p className="text-[10px] text-muted-foreground">
                    {block.days} days · {formatDate(block.startDate)} –{" "}
                    {formatDate(block.endDate)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

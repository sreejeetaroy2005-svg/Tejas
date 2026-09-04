"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { HistoryPoint } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface SrpTrendChartProps {
  data: HistoryPoint[];
  loading: boolean;
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg text-xs">
      <p className="font-medium text-foreground mb-1">{label}</p>
      {payload.map((entry: any) => (
        <p
          key={entry.name}
          style={{ color: entry.color }}
          className="flex justify-between gap-4"
        >
          <span>{entry.name}:</span>
          <span className="font-mono font-medium">
            {typeof entry.value === "number"
              ? entry.value.toFixed(1)
              : entry.value}{" "}
            {entry.name === "SPM" ? "SPM" : "Hz"}
          </span>
        </p>
      ))}
    </div>
  );
}

export function SrpTrendChart({ data, loading }: SrpTrendChartProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[260px] w-full" />
        </CardContent>
      </Card>
    );
  }

  // Filter out injection/soak days where SPM and VFD are 0
  const srpData = data.filter((p) => p.css_stage === "production");

  const chartData = srpData.map((p) => ({
    date: p.date,
    SPM: p.spm,
    VFD: p.vfd_frequency_hz,
  }));

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          SPM &amp; VFD Frequency Trend
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Pump speed and drive frequency during production phases — {srpData.length} days shown
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
            />
            <YAxis
              yAxisId="spm"
              orientation="left"
              stroke="#f59e0b"
              fontSize={10}
              tickLine={false}
              domain={[3, 11]}
              label={{
                value: "SPM",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#f59e0b", fontSize: 10 },
              }}
            />
            <YAxis
              yAxisId="vfd"
              orientation="right"
              stroke="#3b82f6"
              fontSize={10}
              tickLine={false}
              domain={[28, 52]}
              label={{
                value: "Hz",
                angle: 90,
                position: "insideRight",
                style: { fill: "#3b82f6", fontSize: 10 },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              iconType="circle"
              iconSize={6}
            />
            <Line
              yAxisId="spm"
              type="monotone"
              dataKey="SPM"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#f59e0b" }}
            />
            <Line
              yAxisId="vfd"
              type="monotone"
              dataKey="VFD"
              stroke="#3b82f6"
              strokeWidth={1.5}
              dot={false}
              strokeDasharray="5 3"
              activeDot={{ r: 3, fill: "#3b82f6" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

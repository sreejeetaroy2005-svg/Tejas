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

interface ProductionChartProps {
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
        <p key={entry.name} style={{ color: entry.color }} className="flex justify-between gap-4">
          <span>{entry.name}:</span>
          <span className="font-mono font-medium">
            {typeof entry.value === "number" ? entry.value.toFixed(1) : entry.value}{" "}
            {entry.name === "Oil Rate" ? "bbl/day" : "bbl/day"}
          </span>
        </p>
      ))}
    </div>
  );
}

export function ProductionChart({ data, loading }: ProductionChartProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[280px] w-full" />
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((p) => ({
    date: p.date,
    "Oil Rate": p.oil_bpd,
    "Water Rate": p.water_bpd,
  }));

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          Production Rate Trend
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Oil and water production over the last {data.length} days
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
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
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
              label={{
                value: "bbl/day",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#64748b", fontSize: 10 },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              iconType="circle"
              iconSize={6}
            />
            <Line
              type="monotone"
              dataKey="Oil Rate"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#f59e0b" }}
            />
            <Line
              type="monotone"
              dataKey="Water Rate"
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

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

interface TemperatureChartProps {
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
      {payload.map((entry: any) => {
        const unit = entry.name === "Temperature" ? "°C" : "cP";
        const val =
          entry.name === "Viscosity" && entry.value > 1000
            ? `${(entry.value / 1000).toFixed(1)}k`
            : typeof entry.value === "number"
              ? entry.value.toFixed(1)
              : entry.value;
        return (
          <p key={entry.name} style={{ color: entry.color }} className="flex justify-between gap-4">
            <span>{entry.name}:</span>
            <span className="font-mono font-medium">
              {val} {unit}
            </span>
          </p>
        );
      })}
    </div>
  );
}

function formatViscosity(value: number) {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toFixed(0);
}

export function TemperatureChart({ data, loading }: TemperatureChartProps) {
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
    Temperature: p.reservoir_temperature_c,
    Viscosity: p.viscosity_cp,
  }));

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          Reservoir Temperature &amp; Viscosity
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Temperature drives viscosity — lower temp = higher oil resistance
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 5, right: 40, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              stroke="#64748b"
              fontSize={10}
              tickLine={false}
            />
            <YAxis
              yAxisId="temp"
              orientation="left"
              stroke="#ef4444"
              fontSize={10}
              tickLine={false}
              label={{
                value: "°C",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#ef4444", fontSize: 10 },
              }}
            />
            <YAxis
              yAxisId="visc"
              orientation="right"
              stroke="#a855f7"
              fontSize={10}
              tickLine={false}
              tickFormatter={formatViscosity}
              label={{
                value: "cP",
                angle: 90,
                position: "insideRight",
                style: { fill: "#a855f7", fontSize: 10 },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              iconType="circle"
              iconSize={6}
            />
            <Line
              yAxisId="temp"
              type="monotone"
              dataKey="Temperature"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: "#ef4444" }}
            />
            <Line
              yAxisId="visc"
              type="monotone"
              dataKey="Viscosity"
              stroke="#a855f7"
              strokeWidth={1.5}
              dot={false}
              strokeDasharray="5 3"
              activeDot={{ r: 3, fill: "#a855f7" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

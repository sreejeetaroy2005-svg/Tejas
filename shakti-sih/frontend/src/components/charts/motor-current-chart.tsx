"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import type { HistoryPoint } from "@/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface MotorCurrentChartProps {
  data: HistoryPoint[];
  loading: boolean;
}

const HIGH_THRESHOLD = 45;
const ATTENTION_THRESHOLD = 35;

function formatDate(dateStr: string) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const value = payload[0]?.value as number;
  const level =
    value > HIGH_THRESHOLD ? "danger" : value > ATTENTION_THRESHOLD ? "attention" : "safe";
  const levelText =
    value > HIGH_THRESHOLD ? "HIGH" : value > ATTENTION_THRESHOLD ? "ELEVATED" : "NORMAL";

  return (
    <div className="rounded-lg border border-border bg-card p-3 shadow-lg text-xs">
      <p className="font-medium text-foreground mb-1">{label}</p>
      <p className="flex justify-between gap-4">
        <span>Motor Current:</span>
        <span className="font-mono font-medium">
          {value.toFixed(1)} A
        </span>
      </p>
      <p
        className={
          level === "danger"
            ? "text-danger"
            : level === "attention"
              ? "text-attention"
              : "text-safe"
        }
      >
        {levelText}
      </p>
    </div>
  );
}

export function MotorCurrentChart({ data, loading }: MotorCurrentChartProps) {
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

  // Filter to production days only (motor off during injection/soak)
  const srpData = data.filter((p) => p.css_stage === "production");

  const chartData = srpData.map((p) => ({
    date: p.date,
    current: p.motor_current_a,
  }));

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">
          Motor Current Trend
        </CardTitle>
        <p className="text-[11px] text-muted-foreground">
          Stator current draw — high current signals pump strain.{" "}
          <span className="text-danger">Red line</span> = {HIGH_THRESHOLD}A
          threshold
        </p>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="motorGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
            </defs>
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
              domain={[20, 55]}
              label={{
                value: "Amperes",
                angle: -90,
                position: "insideLeft",
                style: { fill: "#64748b", fontSize: 10 },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              yAxisId={0}
              y={HIGH_THRESHOLD}
              stroke="#ef4444"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{
                value: `${HIGH_THRESHOLD}A`,
                position: "right",
                style: { fill: "#ef4444", fontSize: 10 },
              }}
            />
            <ReferenceLine
              yAxisId={0}
              y={ATTENTION_THRESHOLD}
              stroke="#f59e0b"
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{
                value: `${ATTENTION_THRESHOLD}A`,
                position: "right",
                style: { fill: "#f59e0b", fontSize: 10 },
              }}
            />
            <Area
              type="monotone"
              dataKey="current"
              stroke="#f59e0b"
              strokeWidth={2}
              fill="url(#motorGradient)"
              dot={false}
              activeDot={{ r: 4, fill: "#f59e0b" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

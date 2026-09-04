"use client";

import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface DynacardCurveProps {
  /** Multiple curves to overlay, each with a label and color */
  curves: {
    label: string;
    position: number[];
    load: number[];
    color: string;
  }[];
  /** Height of the chart container */
  height?: number;
  /** Show the enclosed area hint */
  showArea?: boolean;
}

/**
 * Renders one or more dynamometer card curves (position vs load).
 * Each curve is a closed loop — the shape indicates pump health.
 */
export function DynacardCurve({
  curves,
  height = 360,
  showArea = false,
}: DynacardCurveProps) {
  // Transform to scatter format: [{x, y, series}]
  const allData = curves.flatMap((curve) =>
    curve.position.map((pos, i) => ({
      x: pos,
      y: curve.load[i],
      series: curve.label,
    }))
  );

  const uniqueSeries = [...new Set(curves.map((c) => c.label))];
  const colorMap = Object.fromEntries(curves.map((c) => [c.label, c.color]));

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.06)"
          />
          <XAxis
            dataKey="x"
            type="number"
            name="Position"
            domain={[0, 1]}
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            label={{
              value: "Position (normalized)",
              position: "bottom",
              offset: -2,
              style: {
                fill: "hsl(var(--muted-foreground))",
                fontSize: 11,
              },
            }}
          />
          <YAxis
            dataKey="y"
            type="number"
            name="Load"
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            label={{
              value: "Load (lbf)",
              angle: -90,
              position: "insideLeft",
              offset: 10,
              style: {
                fill: "hsl(var(--muted-foreground))",
                fontSize: 11,
              },
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value, name) => {
              const numValue = typeof value === "number" ? value : Number(value);
              return [
                name === "x"
                  ? `${(numValue * 100).toFixed(0)}%`
                  : `${numValue.toLocaleString()} lbf`,
                name === "x" ? "Position" : "Load",
              ];
            }}
          />
          {uniqueSeries.length > 1 && (
            <Legend
              wrapperStyle={{ fontSize: 12, color: "hsl(var(--muted-foreground))" }}
            />
          )}
          {curves.map((curve) => (
            <Scatter
              key={curve.label}
              name={curve.label}
              data={curve.position.map((pos, i) => ({
                x: pos,
                y: curve.load[i],
              }))}
              fill={curve.color}
              line={{ stroke: curve.color, strokeWidth: 2 }}
              lineType="joint"
              legendType="line"
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

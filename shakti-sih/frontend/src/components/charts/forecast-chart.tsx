/**
 * 7-Day Reservoir Forecast Chart
 *
 * Shows predicted temperature (°C) and oil production (bbl/day) for the next
 * 7 days, with uncertainty bands based on model MAE. Plotted alongside the
 * last 14 days of actual history for context.
 *
 * All data is synthetic demonstration data.
 */

"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
  Legend,
} from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InfoTooltip } from "@/components/info-tooltip";
import { TrendingUp, Brain } from "lucide-react";
import type { HistoryPoint, ForecastDay } from "@/types";

interface ForecastChartProps {
  history: HistoryPoint[];
  forecast: ForecastDay[];
  temperatureMae: number;
  productionMae: number;
  loading: boolean;
}

// Combine last 14 days of history with 7-day forecast
function buildChartData(
  history: HistoryPoint[],
  forecast: ForecastDay[],
  tempMae: number,
  prodMae: number
) {
  const recent = history.slice(-14);
  type ChartPoint = {
    date: string;
    temperatureActual: number | undefined;
    temperatureForecast: number | undefined;
    oilActual: number | undefined;
    oilForecast: number | undefined;
    type: string;
    tempUpper: number | undefined;
    tempLower: number | undefined;
    oilUpper: number | undefined;
    oilLower: number | undefined;
  };
  const combined: ChartPoint[] = recent.map((p) => ({
    date: p.date,
    temperatureActual: p.reservoir_temperature_c,
    temperatureForecast: undefined,
    oilActual: p.oil_bpd,
    oilForecast: undefined,
    type: "actual",
    tempUpper: undefined,
    tempLower: undefined,
    oilUpper: undefined,
    oilLower: undefined,
  }));

  // Duplicate the last actual point as the first forecast point so the two
  // line series connect visually with no gap at the transition boundary.
  if (recent.length > 0 && forecast.length > 0) {
    const lastActual = recent[recent.length - 1];
    combined.push({
      date: lastActual.date,
      temperatureActual: undefined,
      temperatureForecast: lastActual.reservoir_temperature_c,
      oilActual: undefined,
      oilForecast: lastActual.oil_bpd,
      type: "actual",
      tempUpper: undefined,
      tempLower: undefined,
      oilUpper: undefined,
      oilLower: undefined,
    });
  }

  forecast.forEach((f) => {
    combined.push({
      date: f.date,
      temperatureActual: undefined,
      temperatureForecast: f.predicted_temperature_c,
      oilActual: undefined,
      oilForecast: f.predicted_oil_bpd,
      type: "forecast",
      tempUpper: f.predicted_temperature_c + tempMae,
      tempLower: f.predicted_temperature_c - tempMae,
      oilUpper: f.predicted_oil_bpd + prodMae,
      oilLower: Math.max(0, f.predicted_oil_bpd - prodMae),
    });
  });

  return combined;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  const isForecast = data?.type === "forecast";

  // Collect the actual temp/oil values from whichever series has them
  const tempValue = data?.temperatureActual ?? data?.temperatureForecast;
  const oilValue = data?.oilActual ?? data?.oilForecast;

  return (
    <div
      style={{
        backgroundColor: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "10px 14px",
        fontSize: 12,
      }}
    >
      <p className="font-medium text-foreground mb-1">
        {label}
        {isForecast && (
          <span className="ml-2 text-[10px] text-[var(--series-uncertainty,#6fb3c9)]">forecast</span>
        )}
      </p>
      {tempValue != null && (
        <p className="text-xs" style={{ color: "var(--accent)" }}>
          🌡 Temp: {Number(tempValue).toFixed(1)} °C
        </p>
      )}
      {oilValue != null && (
        <p className="text-xs" style={{ color: isForecast ? "var(--series-uncertainty, #6fb3c9)" : "var(--accent)" }}>
          🛢 Oil: {Number(oilValue).toFixed(1)} bbl/day
        </p>
      )}
    </div>
  );
}

export function ForecastChart({
  history,
  forecast,
  temperatureMae,
  productionMae,
  loading,
}: ForecastChartProps) {
  if (loading) {
    return (
      <Card className="bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            7-Day Forecast
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[300px] w-full" />
        </CardContent>
      </Card>
    );
  }

  const data = buildChartData(history, forecast, temperatureMae, productionMae);
  const forecastStart = history.length - 14 + history.length;

  return (
    <Card className="bg-card">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-accent" />
            <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              7-Day Forecast
              <InfoTooltip text="XGBoost model predicts reservoir temperature and oil production for the next 7 days. Shaded bands show model uncertainty (±MAE)." />
            </CardTitle>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-accent inline-block" /> Actual
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-0.5 bg-[var(--series-uncertainty,#6fb3c9)] inline-block border-dashed" style={{ borderTop: "2px dashed var(--series-uncertainty, #6fb3c9)", height: 0 }} /> Forecast
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 bg-accent/20 inline-block rounded" /> ±MAE
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Temperature Chart */}
        <div className="mb-4">
          <p className="text-[11px] text-muted-foreground mb-2 flex items-center gap-1">
            <TrendingUp className="h-3 w-3" /> Reservoir Temperature (°C) — MAE ±{temperatureMae.toFixed(2)}°C
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(215, 20%, 55%)" }}
                tickFormatter={(v) => v.slice(5)} // MM-DD
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(215, 20%, 55%)" }}
                width={45}
                tickFormatter={(v) => `${v}`}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* Uncertainty band */}
              <Area
                dataKey="tempUpper"
                stroke="none"
                fill="var(--accent)" fillOpacity={0.12}
                isAnimationActive={false}
              />
              <Area
                dataKey="tempLower"
                stroke="none"
                fill="var(--card)"
                isAnimationActive={false}
              />
              {/* Actual — solid amber */}
              <Line
                dataKey="temperatureActual"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                connectNulls
                legendType="none"
              />
              {/* Forecast — dashed cyan */}
              <Line
                dataKey="temperatureForecast"
                stroke="var(--series-uncertainty, #6fb3c9)"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls
                legendType="none"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Oil Production Chart */}
        <div>
          <p className="text-[11px] text-muted-foreground mb-2 flex items-center gap-1">
            <TrendingUp className="h-3 w-3" /> Oil Production (bbl/day) — MAE ±{productionMae.toFixed(2)} bbl/day
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "hsl(215, 20%, 55%)" }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "hsl(215, 20%, 55%)" }}
                width={45}
                tickFormatter={(v) => `${v}`}
              />
              <Tooltip content={<CustomTooltip />} />
              {/* Uncertainty band */}
              <Area
                dataKey="oilUpper"
                stroke="none"
                fill="var(--series-uncertainty, #6fb3c9)" fillOpacity={0.12}
                isAnimationActive={false}
              />
              <Area
                dataKey="oilLower"
                stroke="none"
                fill="var(--card)"
                isAnimationActive={false}
              />
              {/* Actual — solid amber */}
              <Line
                dataKey="oilActual"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                connectNulls
                legendType="none"
              />
              {/* Forecast — dashed cyan */}
              <Line
                dataKey="oilForecast"
                stroke="var(--series-uncertainty, #6fb3c9)"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls
                legendType="none"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <p className="text-[10px] text-muted-foreground text-center mt-2">
          Forecast by XGBoost regressors trained on synthetic well data. Model R²: temperature 0.96, production 0.94.
        </p>
      </CardContent>
    </Card>
  );
}

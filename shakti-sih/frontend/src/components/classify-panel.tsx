"use client";

import { useState } from "react";
import { DynacardClassifyRequest } from "@/types";
import { classifyDynacard } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DynacardCurve } from "@/components/charts/dynacard-curve";
import { AlertTriangle, CheckCircle, Info, Zap } from "lucide-react";

const DEFAULT_PARAMS: DynacardClassifyRequest = {
  position: [],
  load: [],
  spm: 8.0,
  stroke_length: 48,
  temperature: 120,
  viscosity: 2000,
  fluid_level: 800,
  pump_depth: 3000,
  production_rate: 80,
};

interface ClassifyPanelProps {
  /** Example cards to select from for quick testing */
  exampleCards?: {
    label: string;
    position: number[];
    load: number[];
  }[];
}

/**
 * Interactive classify panel — user can select an example card or enter
 * parameters, then classify to get predicted condition + explanation.
 */
export function ClassifyPanel({ exampleCards = [] }: ClassifyPanelProps) {
  const [params, setParams] = useState<DynacardClassifyRequest>({
    ...DEFAULT_PARAMS,
    position: exampleCards[0]?.position ?? [],
    load: exampleCards[0]?.load ?? [],
  });
  const [selectedExample, setSelectedExample] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    predicted_condition: string;
    confidence: number;
    top_features: string[];
    explanation: string;
    recommended_action: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectExample = (idx: number) => {
    setSelectedExample(idx);
    if (exampleCards[idx]) {
      setParams((p) => ({
        ...p,
        position: exampleCards[idx].position,
        load: exampleCards[idx].load,
      }));
    }
  };

  const handleClassify = async () => {
    if (params.position.length === 0) {
      setError("Select an example card or enter position/load data first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { data } = await classifyDynacard(params);
      setResult(data);
    } catch {
      setError("Classification failed. Check the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  const conditionColor = (condition: string) => {
    switch (condition) {
      case "Normal":
        return "text-emerald-400";
      case "Rod Floating":
        return "text-red-400";
      case "Fluid Pound":
        return "text-amber-400";
      case "Gas Interference":
        return "text-orange-400";
      default:
        return "text-muted-foreground";
    }
  };

  return (
    <div className="space-y-4">
      {/* Quick-select example cards */}
      {exampleCards.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground self-center mr-1">
            Quick select:
          </span>
          {exampleCards.map((card, idx) => (
            <Button
              key={card.label}
              variant={selectedExample === idx ? "default" : "outline"}
              size="sm"
              onClick={() => selectExample(idx)}
              className="text-xs"
            >
              {card.label}
            </Button>
          ))}
        </div>
      )}

      {/* Input parameters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { key: "spm" as const, label: "SPM", unit: "SPM", min: 4, max: 10, step: 0.1 },
          { key: "stroke_length" as const, label: "Stroke Length", unit: "in", min: 24, max: 72, step: 1 },
          { key: "temperature" as const, label: "Temperature", unit: "°F", min: 80, max: 200, step: 1 },
          { key: "viscosity" as const, label: "Viscosity", unit: "cP", min: 100, max: 10000, step: 100 },
          { key: "fluid_level" as const, label: "Fluid Level", unit: "ft", min: 0, max: 1500, step: 50 },
          { key: "pump_depth" as const, label: "Pump Depth", unit: "ft", min: 1000, max: 5000, step: 100 },
          { key: "production_rate" as const, label: "Production", unit: "bbl/day", min: 0, max: 200, step: 5 },
        ].map((field) => (
          <div key={field.key} className="space-y-1">
            <label className="text-xs text-muted-foreground">
              {field.label}
            </label>
            <div className="relative">
              <input
                type="number"
                value={params[field.key]}
                onChange={(e) =>
                  setParams((p) => ({
                    ...p,
                    [field.key]: Number(e.target.value),
                  }))
                }
                min={field.min}
                max={field.max}
                step={field.step}
                className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              />
              <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground">
                {field.unit}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Classify button */}
      <div className="flex items-center gap-3">
        <Button
          onClick={handleClassify}
          disabled={loading || params.position.length === 0}
          className="bg-accent hover:bg-accent/90 text-accent-foreground"
        >
          {loading ? (
            <>
              <Zap className="h-4 w-4 animate-spin mr-2" />
              Classifying...
            </>
          ) : (
            <>
              <Zap className="h-4 w-4 mr-2" />
              Classify Card
            </>
          )}
        </Button>
        <span className="text-xs text-muted-foreground">
          {params.position.length} data points loaded
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 rounded-md px-3 py-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <Card className="border-accent/30 bg-accent/5">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Classification Result</CardTitle>
              <Badge
                variant={
                  result.predicted_condition === "Normal"
                    ? "safe"
                    : result.predicted_condition === "Rod Floating"
                      ? "danger"
                      : "attention"
                }
              >
                {result.predicted_condition}
              </Badge>
            </div>
            <div className="flex items-center gap-4 mt-1">
              <div className="flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                <span className="text-xs text-muted-foreground">
                  Confidence:{" "}
                  <span className="text-foreground font-medium">
                    {(result.confidence * 100).toFixed(1)}%
                  </span>
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Confidence bar */}
            <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${result.confidence * 100}%` }}
              />
            </div>

            {/* Top features */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-1">
                Top Contributing Features
              </h4>
              <div className="flex gap-2 flex-wrap">
                {result.top_features.map((f, i) => (
                  <Badge key={f} variant="outline" className="text-xs">
                    #{i + 1} {f.replace(/_/g, " ")}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Explanation */}
            <div className="flex items-start gap-2 text-sm">
              <Info className="h-4 w-4 text-accent shrink-0 mt-0.5" />
              <p className="text-muted-foreground">{result.explanation}</p>
            </div>

            {/* Recommended action */}
            <div className="flex items-start gap-2 text-sm">
              <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-muted-foreground">
                <span className="text-foreground font-medium">
                  Recommended action:
                </span>{" "}
                {result.recommended_action}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Card preview */}
      {params.position.length > 0 && (
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-xs text-muted-foreground">
              Card Preview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DynacardCurve
              curves={[
                {
                  label: exampleCards[selectedExample]?.label ?? "Card",
                  position: params.position,
                  load: params.load,
                  color: "hsl(var(--accent))",
                },
              ]}
              height={240}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

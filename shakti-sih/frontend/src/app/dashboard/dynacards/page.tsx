"use client";

import { useState, useEffect } from "react";
import { fetchDynacardExamples } from "@/lib/api";
import { DynacardExample } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { DynacardCurve } from "@/components/charts/dynacard-curve";
import { ClassifyPanel } from "@/components/classify-panel";
import {
  Activity,
  AlertTriangle,
  Info,
  BarChart3,
} from "lucide-react";

const CONDITION_COLORS: Record<string, string> = {
  Normal: "#22c55e",
  "Rod Floating": "#ef4444",
  "Fluid Pound": "#f59e0b",
  "Gas Interference": "#f97316",
};

const CONDITION_ICONS: Record<string, string> = {
  Normal: "✅",
  "Rod Floating": "🔴",
  "Fluid Pound": "⚠️",
  "Gas Interference": "🟠",
};

const CONDITION_DESCRIPTIONS: Record<string, string> = {
  Normal:
    "Full, smooth loop — pump filling properly on each stroke. Rod loads are balanced and the plunger is sealing well.",
  "Rod Floating":
    "Narrow, compressed loop — the rod is not fully loading on the downstroke. Indicates the pump barrel is only partially filling, causing the rod to 'float' on fluid.",
  "Fluid Pound":
    "Sharp dip on the downstroke — the plunger hits a partial fluid column, causing a mechanical shock. High risk of equipment damage.",
  "Gas Interference":
    "Jagged, irregular pattern — gas bubbles are compressing in the pump barrel, reducing fillage and creating erratic loads.",
};

export default function DynacardsPage() {
  const [examples, setExamples] = useState<DynacardExample[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMock, setIsMock] = useState(false);
  const [selectedCard, setSelectedCard] = useState<number | null>(null);

  useEffect(() => {
    async function load() {
      const { data, isMock: mock } = await fetchDynacardExamples();
      setExamples(data);
      setIsMock(mock);
      setLoading(false);
    }
    load();
  }, []);

  // Separate by condition
  const byCondition = examples.reduce(
    (acc, card) => {
      if (!acc[card.condition_label]) acc[card.condition_label] = [];
      acc[card.condition_label].push(card);
      return acc;
    },
    {} as Record<string, DynacardExample[]>
  );

  const conditionOrder = [
    "Normal",
    "Rod Floating",
    "Fluid Pound",
    "Gas Interference",
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight">
            Dynamometer Card Classifier
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            ML-powered pump condition diagnosis from dynacard shape analysis
          </p>
        </div>
        {isMock && (
          <Badge variant="outline" className="text-xs border-amber-500/30 text-amber-400">
            API Offline — Mock Data
          </Badge>
        )}
      </div>

      {/* Reference cards gallery */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">
          Reference Card Gallery
        </h3>
        {loading ? (
          <div className="grid grid-cols-2 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-64 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            {conditionOrder.map((condition) => {
              const card = byCondition[condition]?.[0];
              if (!card) return null;
              const color = CONDITION_COLORS[condition] ?? "#888";
              return (
                <Card
                  key={condition}
                  className={`cursor-pointer transition-all ${
                    selectedCard === examples.indexOf(card)
                      ? "border-accent ring-1 ring-accent"
                      : "hover:border-border/80"
                  }`}
                  onClick={() => setSelectedCard(examples.indexOf(card))}
                >
                  <CardHeader className="pb-1">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <span>{CONDITION_ICONS[condition]}</span>
                        {condition}
                      </CardTitle>
                      <Badge
                        variant={
                          card.risk_level === "Low"
                            ? "safe"
                            : card.risk_level === "High"
                              ? "danger"
                              : "attention"
                        }
                        className="text-[10px]"
                      >
                        {card.risk_level} Risk
                      </Badge>
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-relaxed">
                      {CONDITION_DESCRIPTIONS[condition]}
                    </p>
                  </CardHeader>
                  <CardContent>
                    <DynacardCurve
                      curves={[
                        {
                          label: condition,
                          position: card.position,
                          load: card.load,
                          color,
                        },
                      ]}
                      height={200}
                    />
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Comparison overlay */}
      {examples.length > 0 && (
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-accent" />
              All Conditions — Overlay Comparison
            </CardTitle>
            <p className="text-[11px] text-muted-foreground">
              Normal cards enclose the most area (high pump efficiency). Fluid
              pound and rod floating enclose less — the classifier uses this
              geometric signal as its primary feature.
            </p>
          </CardHeader>
          <CardContent>
            <DynacardCurve
              curves={conditionOrder
                .map((cond) => {
                  const card = byCondition[cond]?.[0];
                  if (!card) return null;
                  return {
                    label: cond,
                    position: card.position,
                    load: card.load,
                    color: CONDITION_COLORS[cond] ?? "#888",
                  };
                })
                .filter(Boolean) as {
                label: string;
                position: number[];
                load: number[];
                color: string;
              }[]}
              height={380}
            />
          </CardContent>
        </Card>
      )}

      {/* Classifier section */}
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">
          Card Classifier
        </h3>
        <ClassifyPanel
          exampleCards={examples.map((card) => ({
            label: card.condition_label,
            position: card.position,
            load: card.load,
          }))}
        />
      </div>

      {/* How it works */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Info className="h-4 w-4 text-accent" />
            How the Classifier Works
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div className="space-y-1.5">
              <h4 className="font-medium text-foreground">1. Feature Extraction</h4>
              <p className="text-muted-foreground leading-relaxed">
                From the 200-point position/load curve, we compute 6 geometric
                features: max_load, min_load, load_range, mean_load, std_load,
                and enclosed_area (trapezoidal integration).
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="font-medium text-foreground">2. Context Features</h4>
              <p className="text-muted-foreground leading-relaxed">
                Combined with 7 operating parameters: SPM, stroke_length,
                temperature, viscosity, fluid_level, pump_depth, production_rate
                — 13 features total.
              </p>
            </div>
            <div className="space-y-1.5">
              <h4 className="font-medium text-foreground">3. RandomForest</h4>
              <p className="text-muted-foreground leading-relaxed">
                A RandomForest classifier trained on 320 cards (80/20 stratified
                split) predicts the condition with 80% accuracy. The model
                identifies the top 3 features driving the decision.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2 bg-muted/30 rounded-md px-3 py-2 mt-2">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <p className="text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">Note:</span> This
              classifier is trained on synthetic demonstration data — not real Oil
              India field data. Gas Interference detection is lower accuracy (21%
              recall) due to class overlap with Normal cards. In production, a
              larger labeled dataset would significantly improve performance.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

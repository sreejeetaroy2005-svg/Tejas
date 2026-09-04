/**
 * Centralized tooltip texts for all technical metrics in Tejas.
 * Single source of truth — import from here, not hardcoded strings.
 *
 * All data is synthetic demonstration data.
 */

export const TOOLTIPS = {
  sor: "Barrels of steam injected per barrel of oil produced. Lower is better—indicates efficient recovery.",
  fillage: "Percentage of each pump stroke actually filled with fluid. Low fillage (below 50%) indicates rod floating risk.",
  rodFloatingRisk:
    "Risk of the sucker rod losing contact with the fluid, causing impact loading and equipment damage.",
  spm: "Strokes per minute—pump speed. Higher SPM requires better fillage to avoid floating.",
  vfd: "Variable frequency drive speed in Hz. Controls motor speed and pump rate.",
  viscosity:
    "Oil thickness in centipoise. Rises as temperature drops, increases pump work and floating risk.",
  energy: "Daily electrical energy consumed by the pump motor.",
  temperature:
    "Temperature of the underground oil reservoir—hotter means thinner oil and easier pumping.",
  pressure:
    "Reservoir pressure that helps push oil to the surface. Higher pressure aids production.",
  motorCurrent:
    "Electrical current drawn by the pump motor. Spikes signal the pump is fighting viscous oil or mechanical resistance.",
  oilProduction: "Barrels of oil produced per day from this well.",
  riskScore:
    "Risk of the sucker rod losing contact with the fluid, causing impact loading and equipment damage.",
  steamVolume:
    "Tonnes of steam injected into the reservoir to heat the oil and reduce viscosity.",
  soakTime:
    "Days the well sits after steam injection, letting heat spread through the reservoir.",
  cssStage:
    "Current phase of the Cyclic Steam Injection cycle: injection, soak, or production.",
  compositeScore:
    "Single number combining production gain, SOR penalty, energy cost, and risk—higher is better.",
  productionScore: "Score contribution from daily oil production.",
  sorPenalty:
    "Score deduction for high steam usage per barrel of oil produced.",
  energyPenalty:
    "Score deduction for high electricity consumption during pumping.",
  riskPenalty: "Score deduction for elevated pump failure risk.",
} as const;

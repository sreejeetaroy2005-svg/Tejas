"""Generate synthetic dynamometer card data.

Produces physically-motivated sucker-rod-pump dynacard shapes for four
conditions:

  Normal           — clean parallelogram-like loop, sharp corners
  Rod Floating     — flattened/compressed bottom (rod outruns fluid)
  Fluid Pound      — sharp sudden load drop mid-downstroke (impact loading)
  Gas Interference — delayed, rounded load pickup on upstroke

Design principle (v3)
---------------------
Each condition's distinguishing shape parameters are drawn as *continuous
functions of severity* so that:
  - At low severity the distribution overlaps substantially with Normal.
  - At high severity the distributions are clearly separated.
  - Amplitude noise scales with (1 - severity) so low-severity cards carry
    more sensor/process noise, making them genuinely harder to classify.

This removes the disjoint fixed rng.uniform() ranges from v2 that made
every card trivially separable regardless of severity.

pickup_delay_frac and corner_radius_frac are retained as *diagnostic/
debugging CSV columns* but are NEVER model features — the model must only
use features derivable from the raw position/load arrays at inference time.

Output schema (drop-in replacement for dynacards_synthetic_v1.csv):
  card_id, well_id, timestamp, position, load, SPM, stroke_length,
  temperature, viscosity, fluid_level, pump_depth, production_rate,
  condition_label, risk_level, recommended_action, severity, data_source,
  pickup_delay_frac, corner_radius_frac

All data is explicitly synthetic — not real field measurements.

Usage:
    cd backend
    python scripts/generate_dynacards.py [--n-per-class N] [--seed S] [--out PATH]

Defaults: 200 cards per class (800 total), seed=42,
          out=data/dynacards_synthetic_v1.csv
"""

import argparse
import os
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WELL_IDS = [f"WELL-{i:03d}" for i in range(1, 11)]
N_POINTS = 200          # points per card (upstroke + downstroke)
N_HALF   = N_POINTS // 2

SPM_RANGE        = (4.5,   9.5)
STROKE_LEN_RANGE = (96.0,  168.0)   # inches
TEMP_RANGE       = (110.0, 185.0)   # °F
VISC_RANGE       = (250.0, 950.0)   # cP
FLUID_LVL_RANGE  = (800.0, 4500.0)  # ft
PUMP_DEPTH_RANGE = (3500.0, 6500.0) # ft
PROD_RATE_RANGE  = (35.0,  115.0)   # bbl/day

BASE_MIN_LOAD = 5500.0  # lbs
BASE_MAX_LOAD = 12500.0 # lbs

SEVERITY_RANGES = {
    "Normal":           (0.0,  0.0),
    "Rod Floating":     (0.10, 1.00),   # extended low end so some low-sev RF exists
    "Fluid Pound":      (0.10, 0.80),
    "Gas Interference": (0.10, 0.70),   # extended range; low end overlaps Normal
}

# Normal upstroke logistic sharpness range — all other conditions reference this
NORMAL_SHARPNESS_LO = 16.0
NORMAL_SHARPNESS_HI = 28.0
NORMAL_NOISE        = 0.025   # fraction of load_range


def _risk_level(condition: str, severity: float) -> str:
    if condition == "Normal":        return "Low"
    if condition == "Rod Floating":  return "High" if severity > 0.5 else "Medium"
    if severity >= 0.5:              return "High"
    if severity >= 0.3:              return "Medium"
    return "Low"


RECOMMENDED_ACTIONS = {
    "Normal":           "Continue current operating parameters.",
    "Rod Floating":     "Reduce SPM / adjust VFD; evaluate CSS timing.",
    "Fluid Pound":      "Reduce SPM to match inflow; check pump-off control.",
    "Gas Interference": "Install or check gas separator; reduce SPM; consider gas anchor.",
}


# ---------------------------------------------------------------------------
# Noise helper
# ---------------------------------------------------------------------------

def _noise_scale(severity: float, base: float = 0.025, extra: float = 0.065) -> float:
    """Noise amplitude as a fraction of load_range.

    At sev=0: base + extra (maximum noise, most ambiguous).
    At sev=1: base        (minimum noise, clearest signal).
    The extra term means low-severity cards are noisier than Normal, making
    them genuinely harder to classify.
    """
    return base + extra * (1.0 - severity)


# ---------------------------------------------------------------------------
# Normal card
# ---------------------------------------------------------------------------

def _make_normal_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Clean parallelogram-like loop with sharp corners."""
    t = np.linspace(0.0, 1.0, N_HALF)

    sharpness = rng.uniform(NORMAL_SHARPNESS_LO, NORMAL_SHARPNESS_HI)
    upstroke   = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness * (t - 0.08)))
    downstroke = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness * ((1.0 - t) - 0.08)))

    load_arr = np.concatenate([upstroke, downstroke])
    pos_arr  = np.concatenate([t * stroke_length, (1.0 - t) * stroke_length])

    load_arr += rng.normal(0, NORMAL_NOISE * (max_load - min_load), N_POINTS)
    return pos_arr.round(3).tolist(), load_arr.round(3).tolist(), 0.0, 0.0


# ---------------------------------------------------------------------------
# Gas Interference card
# ---------------------------------------------------------------------------

def _make_gas_interference_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Delayed, rounded load pickup due to gas compression.

    Sharpness blends continuously from the Normal range at sev=0 to clearly
    rounded at sev=1.  Pickup delay also starts near zero and grows with sev.

    sharpness = Normal_mean - severity * 18  + draw_noise
      At sev=0.0: sharpness ~ N(22, 3) — entirely inside Normal's 16-28 range
      At sev=0.4: sharpness ~ N(14.8, 3) — partially outside Normal
      At sev=0.7: sharpness ~ N(9.4, 3) — clearly lower than Normal

    pickup_delay starts at 0 and grows linearly with severity, so low-sev
    cards have almost no pickup delay (indistinct from Normal).
    """
    t = np.linspace(0.0, 1.0, N_HALF)

    # Sharpness: at sev=0 it's entirely inside Normal's 16-28 range (mean=22).
    # At sev=0.7 mean drops to ~6 — clearly lower than Normal's floor of 16.
    # Wide draw noise (std=4) ensures genuine overlap at mid-low severity.
    sharpness_mean = (NORMAL_SHARPNESS_LO + NORMAL_SHARPNESS_HI) / 2.0 - severity * 22.0
    sharpness_mean = max(sharpness_mean, 2.5)
    sharpness = float(np.clip(rng.normal(sharpness_mean, 4.0), 2.0, NORMAL_SHARPNESS_HI))

    # Pickup delay: near-zero at low severity, grows nonlinearly.
    # At sev=0.10: ~0.01-0.04 (barely distinct from Normal's 0.0 offset)
    # At sev=0.70: ~0.22-0.30 (clearly delayed)
    pickup_delay = (severity ** 1.8) * 0.42 * float(rng.uniform(0.5, 1.5))
    pickup_delay = float(np.clip(pickup_delay, 0.0, 0.45))

    # Downstroke early-drop (rounded top-right corner), also severity-gated
    early_drop = (severity ** 1.5) * 0.22 * float(rng.uniform(0.4, 1.6))
    sharpness_down_mean = sharpness_mean
    sharpness_down = float(np.clip(rng.normal(sharpness_down_mean, 4.0), 2.0, NORMAL_SHARPNESS_HI))

    upstroke   = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness * (t - 0.08 - pickup_delay)))
    downstroke = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness_down * ((1.0 - t) - early_drop - 0.05)))

    load_arr = np.concatenate([upstroke, downstroke])
    pos_arr  = np.concatenate([t * stroke_length, (1.0 - t) * stroke_length])

    ns = _noise_scale(severity)
    load_arr += rng.normal(0, ns * (max_load - min_load), N_POINTS)

    return (
        pos_arr.round(3).tolist(),
        load_arr.round(3).tolist(),
        round(float(pickup_delay), 4),
        round(float(early_drop), 4),
    )


# ---------------------------------------------------------------------------
# Rod Floating card
# ---------------------------------------------------------------------------

def _make_rod_floating_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Compressed bottom section — rod outrunning fluid.

    The distinguishing feature is a Gaussian dip on the downstroke.
    At low severity the dip depth is close to zero (indistinguishable from
    Normal noise); it grows continuously with severity.

    dip_depth = severity^1.3 * load_range * U(0.35, 0.75)
    The ^1.3 exponent keeps low-severity RF very close to Normal.
    """
    t = np.linspace(0.0, 1.0, N_HALF)

    # Upstroke: same sharpness range as Normal (upstroke looks normal)
    sharpness = rng.uniform(NORMAL_SHARPNESS_LO, NORMAL_SHARPNESS_HI)
    upstroke   = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness * (t - 0.08)))
    base_down  = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness * ((1.0 - t) - 0.08)))

    # Dip: depth is zero at sev=0, grows with severity
    # ^1.8 exponent keeps low-sev RF very close to Normal
    dip_depth  = (severity ** 1.8) * (max_load - min_load) * float(rng.uniform(0.35, 0.75))
    dip_center = float(rng.uniform(0.30, 0.70))
    # Width also scales with severity so low-sev dips are narrow and shallow
    dip_width  = float(rng.uniform(0.06, 0.15)) + severity * 0.20
    floor_load = min_load * max(0.0, 1.0 - 0.90 * severity)

    dip = dip_depth * np.exp(-0.5 * ((t - dip_center) / (dip_width + 1e-6)) ** 2)
    downstroke = np.maximum(base_down - dip, floor_load)

    load_arr = np.concatenate([upstroke, downstroke])
    pos_arr  = np.concatenate([t * stroke_length, (1.0 - t) * stroke_length])

    ns = _noise_scale(severity)
    load_arr += rng.normal(0, ns * (max_load - min_load), N_POINTS)

    return pos_arr.round(3).tolist(), load_arr.round(3).tolist(), 0.0, 0.0


# ---------------------------------------------------------------------------
# Fluid Pound card
# ---------------------------------------------------------------------------

def _make_fluid_pound_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Sharp sudden load drop partway through the downstroke (impact loading).

    At low severity the drop is shallow and hard to distinguish from noise.
    At high severity it becomes a prominent cliff.

    drop_depth = severity^1.2 * load_range * U(0.25, 0.65)
    sharpness_drop blends: at sev=0 it's gentle (~ Normal sharpness);
    at sev=1 it's very steep.
    """
    t = np.linspace(0.0, 1.0, N_HALF)

    sharpness_up = rng.uniform(NORMAL_SHARPNESS_LO, NORMAL_SHARPNESS_HI)
    upstroke   = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness_up * (t - 0.08)))
    base_down  = min_load + (max_load - min_load) / (1.0 + np.exp(-sharpness_up * ((1.0 - t) - 0.08)))

    impact_t   = float(rng.uniform(0.20, 0.65))
    drop_depth = (severity ** 1.6) * (max_load - min_load) * float(rng.uniform(0.25, 0.65))
    # Drop sharpness: at sev=0 → gentle (~Normal); at sev=1 → very steep
    sharpness_drop = NORMAL_SHARPNESS_LO + severity * 90.0 + float(rng.normal(0, 8))
    sharpness_drop = max(sharpness_drop, NORMAL_SHARPNESS_LO)

    drop_curve = drop_depth / (1.0 + np.exp(-sharpness_drop * (t - impact_t)))
    downstroke = base_down - drop_curve

    # Post-impact oscillation only appears at moderate-high severity
    if severity > 0.45:
        osc_amp   = float(rng.uniform(0.02, 0.07)) * (max_load - min_load) * severity
        osc_freq  = float(rng.uniform(6, 14))
        osc_decay = 12.0
        osc = osc_amp * np.exp(-osc_decay * np.maximum(t - impact_t, 0)) * np.sin(
            2 * np.pi * osc_freq * (t - impact_t)
        )
        downstroke += osc

    load_arr = np.concatenate([upstroke, downstroke])
    pos_arr  = np.concatenate([t * stroke_length, (1.0 - t) * stroke_length])

    ns = _noise_scale(severity)
    load_arr += rng.normal(0, ns * (max_load - min_load), N_POINTS)

    return pos_arr.round(3).tolist(), load_arr.round(3).tolist(), 0.0, 0.0


# ---------------------------------------------------------------------------
# Card dispatcher
# ---------------------------------------------------------------------------

_GENERATORS = {
    "Normal":           _make_normal_card,
    "Rod Floating":     _make_rod_floating_card,
    "Fluid Pound":      _make_fluid_pound_card,
    "Gas Interference": _make_gas_interference_card,
}


def _generate_one_card(
    condition: str,
    rng: np.random.Generator,
    base_ts: datetime,
    card_index: int,
) -> dict:
    sev_lo, sev_hi = SEVERITY_RANGES[condition]
    severity = float(rng.uniform(sev_lo, sev_hi)) if sev_hi > 0 else 0.0

    well_id        = rng.choice(WELL_IDS)
    stroke_length  = float(rng.uniform(*STROKE_LEN_RANGE))
    spm            = float(rng.uniform(*SPM_RANGE))
    temperature    = float(rng.uniform(*TEMP_RANGE))
    viscosity      = float(rng.uniform(*VISC_RANGE))
    fluid_level    = float(rng.uniform(*FLUID_LVL_RANGE))
    pump_depth     = float(rng.uniform(*PUMP_DEPTH_RANGE))
    production_rate = float(rng.uniform(*PROD_RATE_RANGE))

    min_load = float(rng.uniform(BASE_MIN_LOAD * 0.85, BASE_MIN_LOAD * 1.15))
    max_load = float(rng.uniform(BASE_MAX_LOAD * 0.85, BASE_MAX_LOAD * 1.15))
    if max_load < min_load + 2000:
        max_load = min_load + 2000.0

    gen_fn = _GENERATORS[condition]
    if condition == "Normal":
        position, load, pdf, crf = gen_fn(stroke_length, min_load, max_load, rng)
    else:
        position, load, pdf, crf = gen_fn(stroke_length, min_load, max_load, severity, rng)

    ts = base_ts + timedelta(hours=card_index * 6)

    return {
        "card_id":           uuid.uuid4().hex[:8],
        "well_id":           well_id,
        "timestamp":         ts.isoformat(),
        "position":          str(position),
        "load":              str(load),
        "SPM":               round(spm, 2),
        "stroke_length":     round(stroke_length, 1),
        "temperature":       round(temperature, 1),
        "viscosity":         round(viscosity, 1),
        "fluid_level":       round(fluid_level, 1),
        "pump_depth":        round(pump_depth, 1),
        "production_rate":   round(production_rate, 1),
        "condition_label":   condition,
        "risk_level":        _risk_level(condition, severity),
        "recommended_action": RECOMMENDED_ACTIONS[condition],
        "severity":          round(severity, 3),
        "data_source":       "synthetic_physics_v3",
        # Diagnostic columns — NOT model features (not in FEATURE_COLS)
        "pickup_delay_frac": round(pdf, 4),
        "corner_radius_frac": round(crf, 4),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate(n_per_class: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate a balanced synthetic dynacard dataset."""
    rng      = np.random.default_rng(seed)
    base_ts  = datetime(2026, 1, 1)
    rows     = []
    conditions = ["Normal", "Rod Floating", "Fluid Pound", "Gas Interference"]

    for condition in conditions:
        for i in range(n_per_class):
            rows.append(_generate_one_card(condition, rng, base_ts, len(rows)))

    df = pd.DataFrame(rows)
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic dynacard data.")
    parser.add_argument("--n-per-class", type=int, default=200)
    parser.add_argument("--seed",        type=int, default=42)
    parser.add_argument("--out",         type=str, default=None)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path   = args.out or os.path.join(script_dir, "..", "data", "dynacards_synthetic_v1.csv")

    print("=" * 60)
    print("Synthetic Dynacard Generator (v3 — severity-continuous)")
    print("=" * 60)
    print(f"Cards per class : {args.n_per_class}")
    print(f"Total cards     : {args.n_per_class * 4}")
    print(f"Random seed     : {args.seed}")
    print(f"Output path     : {out_path}")
    print()

    df = generate(n_per_class=args.n_per_class, seed=args.seed)

    print("Class distribution:")
    print(df["condition_label"].value_counts().to_string())
    print()
    print("Severity stats per class:")
    print(df.groupby("condition_label")["severity"].describe().round(3).to_string())
    print()
    print("GI pickup_delay_frac by severity tercile:")
    gi = df[df["condition_label"] == "Gas Interference"].copy()
    gi["tercile"] = pd.qcut(gi["severity"], 3, labels=["Low", "Mid", "High"])
    print(gi.groupby("tercile", observed=True)["pickup_delay_frac"].describe().round(4).to_string())
    print()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()

"""Generate synthetic dynamometer card data.

Produces physically-motivated sucker-rod-pump dynacard shapes for four
conditions:

  Normal           — clean parallelogram-like loop, sharp corners
  Rod Floating     — flattened/compressed bottom (rod outruns fluid)
  Fluid Pound      — sharp sudden load drop mid-downstroke (impact loading)
  Gas Interference — delayed, rounded load pickup on upstroke caused by gas
                     compression. Shape is encoded via two explicit parameters:
                       pickup_delay_frac  — fraction of upstroke before fluid is
                                            actually picked up (0 = Normal,
                                            0.1-0.5 = GI depending on severity)
                       corner_radius_frac — fractional rounding of the card
                                            corners (0 = sharp, >0 = rounded)
                     These parameters ALSO appear as columns in the CSV so they
                     can be used directly as engineered features at training time.

Output schema (drop-in replacement for dynacards_synthetic_v1.csv):
  card_id, well_id, timestamp, position, load, SPM, stroke_length,
  temperature, viscosity, fluid_level, pump_depth, production_rate,
  condition_label, risk_level, recommended_action, severity, data_source,
  pickup_delay_frac, corner_radius_frac

The last two columns are new shape-parameter columns.  dynacard_service.py
feature engineering and train_dynacard_classifier.py both read the same CSV,
so both will pick them up automatically via the updated feature lists.

All data is explicitly synthetic — not real field measurements.

Usage:
    cd backend
    python scripts/generate_dynacards.py [--n-per-class N] [--seed S] [--out PATH]

Defaults: 200 cards per class (800 total), seed=42,
          out=data/dynacards_synthetic_v1.csv
"""

import argparse
import ast
import json
import os
import sys
import uuid
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants matching existing CSV ranges
# ---------------------------------------------------------------------------
WELL_IDS = [f"WELL-{i:03d}" for i in range(1, 11)]  # 10 wells
N_POINTS = 200  # points per card (upstroke + downstroke = full loop)

# Operating-parameter ranges (match the existing CSV)
SPM_RANGE = (4.5, 9.5)           # strokes per minute
STROKE_LEN_RANGE = (96.0, 168.0)  # inches
TEMP_RANGE = (110.0, 185.0)       # °F
VISC_RANGE = (250.0, 950.0)       # cP
FLUID_LVL_RANGE = (800.0, 4500.0) # ft
PUMP_DEPTH_RANGE = (3500.0, 6500.0)# ft
PROD_RATE_RANGE = (35.0, 115.0)   # bbl/day

# Base rod/fluid load bounds
BASE_MIN_LOAD = 5500.0   # lbs (buoyant rod weight at BDC)
BASE_MAX_LOAD = 12500.0  # lbs (rod + fluid at TDC)

# Severity ranges by condition
SEVERITY_RANGES = {
    "Normal":           (0.0,  0.0),
    "Rod Floating":     (0.80, 1.00),
    "Fluid Pound":      (0.28, 0.70),
    "Gas Interference": (0.15, 0.55),
}

# Risk level thresholds
def _risk_level(condition: str, severity: float) -> str:
    if condition == "Normal":
        return "Low"
    if condition == "Rod Floating":
        return "High"
    if severity >= 0.5:
        return "High"
    if severity >= 0.3:
        return "Medium"
    return "Low"

RECOMMENDED_ACTIONS = {
    "Normal":           "Continue current operating parameters.",
    "Rod Floating":     "Reduce SPM / adjust VFD; evaluate CSS timing.",
    "Fluid Pound":      "Reduce SPM to match inflow; check pump-off control.",
    "Gas Interference": "Install or check gas separator; reduce SPM; consider gas anchor.",
}


# ---------------------------------------------------------------------------
# Card shape generators
# ---------------------------------------------------------------------------

def _make_normal_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    rng: np.random.Generator,
    noise_scale: float = 0.015,
) -> tuple[list[float], list[float], float, float]:
    """Sharp parallelogram-like loop with small noise.

    Returns (position, load, pickup_delay_frac=0.0, corner_radius_frac=0.0).
    """
    t = np.linspace(0.0, 1.0, N_POINTS // 2)  # 100-pt half-stroke

    # Upstroke: load rises sharply near position=0 and stays near max_load
    # Using a logistic-style ramp over the first ~10% of stroke
    sharpness = rng.uniform(18, 28)
    upstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness * (t - 0.08))
    )

    # Downstroke (reversed position): load drops sharply near position=stroke_length
    downstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness * ((1.0 - t) - 0.08))
    )

    load_arr = np.concatenate([upstroke_load, downstroke_load])
    pos_up = t * stroke_length
    pos_down = (1.0 - t) * stroke_length
    pos_arr = np.concatenate([pos_up, pos_down])

    noise = rng.normal(0, noise_scale * (max_load - min_load), N_POINTS)
    load_arr = load_arr + noise

    return (
        pos_arr.round(3).tolist(),
        load_arr.round(3).tolist(),
        0.0,   # pickup_delay_frac
        0.0,   # corner_radius_frac
    )


def _make_rod_floating_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Compressed bottom section — rod outrunning fluid.

    The downstroke load falls toward near-zero for the middle portion,
    creating a pinched/compressed bottom of the card. Severity controls
    how flattened the bottom becomes.

    Returns (position, load, pickup_delay_frac=0.0, corner_radius_frac=0.0).
    """
    t = np.linspace(0.0, 1.0, N_POINTS // 2)

    sharpness = rng.uniform(18, 28)
    upstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness * (t - 0.08))
    )

    # Downstroke: load is compressed toward zero in the middle
    # floor_load approaches zero as severity → 1
    floor_load = min_load * (1.0 - 0.95 * severity)
    # Gaussian dip in the middle of the downstroke
    dip_center = rng.uniform(0.35, 0.65)
    dip_width = rng.uniform(0.15, 0.30) * severity
    dip_depth = severity * (max_load - min_load) * rng.uniform(0.55, 0.75)
    base_down = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness * ((1.0 - t) - 0.08))
    )
    dip = dip_depth * np.exp(-0.5 * ((t - dip_center) / (dip_width + 1e-6)) ** 2)
    downstroke_load = np.maximum(base_down - dip, floor_load)

    load_arr = np.concatenate([upstroke_load, downstroke_load])
    pos_up = t * stroke_length
    pos_down = (1.0 - t) * stroke_length
    pos_arr = np.concatenate([pos_up, pos_down])

    noise = rng.normal(0, 0.015 * (max_load - min_load), N_POINTS)
    load_arr = load_arr + noise

    return (
        pos_arr.round(3).tolist(),
        load_arr.round(3).tolist(),
        0.0,
        0.0,
    )


def _make_fluid_pound_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Sharp sudden load drop partway through the downstroke (impact loading).

    The upstroke looks normal; the downstroke has a cliff edge at a random
    impact position. Severity controls the magnitude of the drop and whether
    there is a secondary oscillation after impact.

    Returns (position, load, pickup_delay_frac=0.0, corner_radius_frac=0.0).
    """
    t = np.linspace(0.0, 1.0, N_POINTS // 2)

    sharpness_up = rng.uniform(18, 28)
    upstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness_up * (t - 0.08))
    )

    # Downstroke: normal descent until impact, then cliff drop
    impact_t = rng.uniform(0.25, 0.60)  # fraction into downstroke
    drop_depth = severity * (max_load - min_load) * rng.uniform(0.50, 0.80)
    sharpness_drop = rng.uniform(60, 120)  # very sharp cliff
    base_down = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness_up * ((1.0 - t) - 0.08))
    )
    # Sigmoid drop centred at impact_t
    drop_curve = drop_depth / (1.0 + np.exp(-sharpness_drop * (t - impact_t)))
    downstroke_load = base_down - drop_curve

    # Optional post-impact oscillation (physical ringing)
    if severity > 0.4:
        osc_amp = rng.uniform(0.03, 0.08) * (max_load - min_load) * severity
        osc_freq = rng.uniform(8, 16)
        osc_decay = 15.0
        osc = osc_amp * np.exp(-osc_decay * np.maximum(t - impact_t, 0)) * np.sin(
            2 * np.pi * osc_freq * (t - impact_t)
        )
        downstroke_load = downstroke_load + osc

    load_arr = np.concatenate([upstroke_load, downstroke_load])
    pos_up = t * stroke_length
    pos_down = (1.0 - t) * stroke_length
    pos_arr = np.concatenate([pos_up, pos_down])

    noise = rng.normal(0, 0.012 * (max_load - min_load), N_POINTS)
    load_arr = load_arr + noise

    return (
        pos_arr.round(3).tolist(),
        load_arr.round(3).tolist(),
        0.0,
        0.0,
    )


def _make_gas_interference_card(
    stroke_length: float,
    min_load: float,
    max_load: float,
    severity: float,
    rng: np.random.Generator,
) -> tuple[list[float], list[float], float, float]:
    """Delayed, rounded load pickup due to gas compression.

    Physical signature:
    - Upstroke: load does NOT rise sharply at BDC. Instead there is a long
      shallow compression phase until the gas is compressed enough for the
      traveling valve to open. After pickup, load rises to max.
    - Downstroke: starts normally then the standing valve opens early
      (gas expands) creating a rounded top-right corner.
    - Both corners are visibly rounded compared to Normal.

    Key shape parameters encoded explicitly:
      pickup_delay_frac  — position fraction (of full stroke) before fluid load
                           is actually picked up. Min = 0.08 even at severity=0
                           so it is ALWAYS distinct from Normal (which has ~0.08
                           purely from the logistic ramp — GI minimum is 0.15).
      corner_radius_frac — fractional rounding applied to the top corners.

    These become engineered features. Even at minimum severity the values are
    non-zero and qualitatively distinct from Normal.
    """
    t = np.linspace(0.0, 1.0, N_POINTS // 2)

    # Pickup delay: fraction of upstroke before fluid load begins
    # Even at min severity (0.15) this is 0.12; at max (0.55) it's 0.38
    pickup_delay_frac = 0.10 + severity * 0.52
    # Corner rounding: scales with severity, never zero for GI
    corner_radius_frac = 0.05 + severity * 0.45

    # --------------- Upstroke ---------------
    # Phase 1: gas compression (flat, near min_load)
    # Phase 2: actual fluid pickup (logistic ramp to max_load)
    # Transition sharpness is LOWER than Normal (rounded pickup)
    sharpness = rng.uniform(6, 12)  # Normal uses 18-28 — this is the rounding
    upstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness * (t - pickup_delay_frac))
    )

    # --------------- Downstroke ---------------
    # Top-right corner: gas expands before the standing valve closes,
    # so the load starts dropping early and rounds the top-right corner.
    # Modelled as a low-sharpness logistic on the REVERSED t.
    # The expansion start position (as fraction from TDC) scales with severity.
    early_drop_start = corner_radius_frac * 0.50  # earlier start = more rounded
    sharpness_down = rng.uniform(5, 11)  # also rounded
    downstroke_load = min_load + (max_load - min_load) / (
        1.0 + np.exp(-sharpness_down * ((1.0 - t) - early_drop_start - 0.05))
    )

    load_arr = np.concatenate([upstroke_load, downstroke_load])
    pos_up = t * stroke_length
    pos_down = (1.0 - t) * stroke_length
    pos_arr = np.concatenate([pos_up, pos_down])

    # Slightly higher noise (gas causes erratic loading)
    noise = rng.normal(0, (0.02 + 0.015 * severity) * (max_load - min_load), N_POINTS)
    load_arr = load_arr + noise

    return (
        pos_arr.round(3).tolist(),
        load_arr.round(3).tolist(),
        round(float(pickup_delay_frac), 4),
        round(float(corner_radius_frac), 4),
    )


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
    """Generate a single synthetic dynacard row."""
    sev_lo, sev_hi = SEVERITY_RANGES[condition]
    severity = float(rng.uniform(sev_lo, sev_hi)) if sev_hi > 0 else 0.0

    well_id = rng.choice(WELL_IDS)
    stroke_length = float(rng.uniform(*STROKE_LEN_RANGE))
    spm = float(rng.uniform(*SPM_RANGE))
    temperature = float(rng.uniform(*TEMP_RANGE))
    viscosity = float(rng.uniform(*VISC_RANGE))
    fluid_level = float(rng.uniform(*FLUID_LVL_RANGE))
    pump_depth = float(rng.uniform(*PUMP_DEPTH_RANGE))
    production_rate = float(rng.uniform(*PROD_RATE_RANGE))

    # Base load magnitudes — vary per card, not fixed constants
    min_load = float(rng.uniform(BASE_MIN_LOAD * 0.85, BASE_MIN_LOAD * 1.15))
    max_load = float(rng.uniform(BASE_MAX_LOAD * 0.85, BASE_MAX_LOAD * 1.15))
    if max_load < min_load + 2000:
        max_load = min_load + 2000.0  # ensure meaningful range

    gen_fn = _GENERATORS[condition]

    # Normal and the others have different signatures — handle
    if condition == "Normal":
        position, load, pdf, crf = gen_fn(
            stroke_length, min_load, max_load, rng
        )
    else:
        position, load, pdf, crf = gen_fn(
            stroke_length, min_load, max_load, severity, rng
        )

    ts = base_ts + timedelta(hours=card_index * 6)
    card_id = uuid.uuid4().hex[:8]

    return {
        "card_id": card_id,
        "well_id": well_id,
        "timestamp": ts.isoformat(),
        "position": str(position),
        "load": str(load),
        "SPM": round(spm, 2),
        "stroke_length": round(stroke_length, 1),
        "temperature": round(temperature, 1),
        "viscosity": round(viscosity, 1),
        "fluid_level": round(fluid_level, 1),
        "pump_depth": round(pump_depth, 1),
        "production_rate": round(production_rate, 1),
        "condition_label": condition,
        "risk_level": _risk_level(condition, severity),
        "recommended_action": RECOMMENDED_ACTIONS[condition],
        "severity": round(severity, 3),
        "data_source": "synthetic_physics_v2",
        "pickup_delay_frac": round(pdf, 4),
        "corner_radius_frac": round(crf, 4),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate(n_per_class: int = 200, seed: int = 42) -> pd.DataFrame:
    """Generate a balanced synthetic dynacard dataset.

    Args:
        n_per_class: Number of cards per condition class.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with all generated cards, shuffled.
    """
    rng = np.random.default_rng(seed)
    base_ts = datetime(2026, 1, 1)

    rows = []
    conditions = ["Normal", "Rod Floating", "Fluid Pound", "Gas Interference"]
    for condition in conditions:
        for i in range(n_per_class):
            card_index = len(rows)
            row = _generate_one_card(condition, rng, base_ts, card_index)
            rows.append(row)

    df = pd.DataFrame(rows)
    # Shuffle so conditions aren't in blocks
    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic dynacard data.")
    parser.add_argument(
        "--n-per-class", type=int, default=200,
        help="Number of cards per condition class (default: 200)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--out", type=str, default=None,
        help="Output CSV path (default: data/dynacards_synthetic_v1.csv)",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.join(script_dir, "..", "data", "dynacards_synthetic_v1.csv")
    out_path = args.out if args.out else default_out

    print("=" * 60)
    print("Synthetic Dynacard Generator")
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
    print("Shape parameter stats (Gas Interference only):")
    gi = df[df["condition_label"] == "Gas Interference"]
    print(gi[["pickup_delay_frac", "corner_radius_frac"]].describe().round(4).to_string())
    print()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Saved {len(df)} rows to {out_path}")
    print("Done.")


if __name__ == "__main__":
    main()

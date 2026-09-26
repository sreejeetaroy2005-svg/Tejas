"""Dynamometer Card Classifier Service.

Loads a trained RandomForest classifier and provides:
  - classify_card() — predict condition from a single card's features
  - get_example_cards() — one example card per condition for frontend plotting

All data is synthetic demonstration data, not real Oil India field data.
"""

import os
import ast
import json

import numpy as np
import pandas as pd
import joblib
from scipy.integrate import trapezoid
from scipy.spatial import ConvexHull

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "dynacard_classifier.pkl")
_META_PATH  = os.path.join(_MODEL_DIR, "dynacard_features.json")
_DATA_PATH  = os.path.join(_MODEL_DIR, "..", "data", "dynacards_synthetic_v1.csv")

# Confidence threshold below which a Gas Interference prediction is flagged
# as uncertain.  Chosen conservatively so borderline cards are surfaced.
_GI_CONFIDENCE_THRESHOLD = 0.50

# Condition → plain-language explanation
_CONDITION_EXPLANATIONS = {
    "Normal":
        "Pump is operating normally — the card shape indicates proper filling and lifting.",
    "Rod Floating":
        "The rod string is floating on fluid — SPM is too low or fluid level is too high, "
        "causing incomplete rod loading.",
    "Fluid Pound":
        "The pump barrel is not filling completely — the plunger is hitting fluid partway "
        "through the downstroke, causing mechanical shock.",
    "Gas Interference":
        "Gas is entering the pump barrel — compressible gas delays fluid pickup and "
        "produces a rounded, shifted card shape with erratic loading patterns.",
    "Gas Interference (low confidence)":
        "Gas Interference is the most likely condition, but classifier confidence is below "
        "threshold. Gas compression may be mild or early-stage. Monitor closely.",
}

# Condition → recommended action
_CONDITION_ACTIONS = {
    "Normal":
        "Continue current operating parameters.",
    "Rod Floating":
        "Increase SPM to match inflow rate; check pump-off controller settings.",
    "Fluid Pound":
        "Reduce SPM to match inflow; check pump-off control and fluid level.",
    "Gas Interference":
        "Install or check gas separator; reduce SPM; consider gas anchor.",
    "Gas Interference (low confidence)":
        "Install or check gas separator; reduce SPM; consider gas anchor. "
        "Increase monitoring frequency to confirm diagnosis.",
}

# ---------------------------------------------------------------------------
# Lazy-loaded state
# ---------------------------------------------------------------------------
_clf = None
_feature_cols: list[str] = None   # type: ignore[assignment]
_classes: list[str] = None        # type: ignore[assignment]
_raw_df: pd.DataFrame | None = None


def _load_model() -> None:
    """Load model, metadata, and raw CSV.  Called once, cached globally."""
    global _clf, _feature_cols, _classes, _raw_df

    if _clf is not None:
        return

    for path in [_MODEL_PATH, _META_PATH, _DATA_PATH]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required file not found: {path}. "
                "Run scripts/train_dynacard_classifier.py first."
            )

    _clf = joblib.load(_MODEL_PATH)
    with open(_META_PATH) as f:
        meta = json.load(f)
        _feature_cols = meta["feature_columns"]
        _classes      = meta["classes"]

    _raw_df = pd.read_csv(_DATA_PATH)


# ---------------------------------------------------------------------------
# Shape feature helpers  (must match train_dynacard_classifier.py exactly)
# ---------------------------------------------------------------------------

def _load_pickup_pos(position: np.ndarray, load: np.ndarray) -> float:
    """Fraction of full stroke where upstroke load first exceeds 50% of max."""
    n_half = len(position) // 2
    upstroke_load = load[:n_half]
    upstroke_pos  = position[:n_half]
    stroke = float(np.max(position) - np.min(position))
    if stroke < 1e-6:
        return 0.0
    threshold = float(np.min(load)) + 0.5 * (float(np.max(load)) - float(np.min(load)))
    above = np.where(upstroke_load >= threshold)[0]
    if len(above) == 0:
        return 1.0
    return float(np.clip(upstroke_pos[above[0]] / stroke, 0.0, 1.0))


def _hull_fill_ratio(position: np.ndarray, load: np.ndarray) -> float:
    """Enclosed area / convex-hull area.  Rounded cards score below 1.0."""
    pts = np.column_stack([position, load])
    try:
        hull = ConvexHull(pts)
        hull_area = hull.volume  # ConvexHull.volume is area in 2-D
    except Exception:
        return 1.0
    enclosed = abs(trapezoid(load, position))
    if hull_area < 1e-6:
        return 1.0
    return float(np.clip(enclosed / hull_area, 0.0, 1.0))


def _top_curvature(load: np.ndarray) -> float:
    """RMS second-derivative near the top 20% of load values."""
    threshold = float(np.percentile(load, 80))
    top_load = load[load >= threshold]
    if len(top_load) < 3:
        return 0.0
    d2 = np.diff(np.diff(top_load.astype(float)))
    return float(np.sqrt(np.mean(d2 ** 2)))


# ---------------------------------------------------------------------------
# Feature engineering  (same logic as training script)
# ---------------------------------------------------------------------------

def _compute_geometric_features(
    position: list[float], load: list[float]
) -> dict:
    """Compute the 6 base geometric features from a position/load card."""
    load_arr = np.array(load)
    pos_arr  = np.array(position)

    max_load    = float(np.max(load_arr))
    min_load    = float(np.min(load_arr))
    load_range  = max_load - min_load
    mean_load   = float(np.mean(load_arr))
    std_load    = float(np.std(load_arr))
    enclosed_area = float(abs(trapezoid(load_arr, pos_arr)))

    return {
        "max_load":      max_load,
        "min_load":      min_load,
        "load_range":    load_range,
        "mean_load":     mean_load,
        "std_load":      std_load,
        "enclosed_area": enclosed_area,
    }


def _build_feature_vector(
    position: list[float],
    load: list[float],
    spm: float,
    stroke_length: float,
    temperature: float,
    viscosity: float,
    fluid_level: float,
    pump_depth: float,
    production_rate: float,
    # Shape parameters: caller supplies these when known (e.g. from the CSV).
    # At live-inference time they are computed from the position/load arrays.
    pickup_delay_frac: float | None = None,
    corner_radius_frac: float | None = None,
) -> np.ndarray:
    """Build a feature vector from card data + operating params.

    The vector order must exactly match FEATURE_COLS in the training script.
    """
    pos_arr  = np.array(position)
    load_arr = np.array(load)

    geom = _compute_geometric_features(position, load)

    # Shape features — at inference time we derive from the curve
    pdf = pickup_delay_frac  if pickup_delay_frac  is not None else 0.0
    crf = corner_radius_frac if corner_radius_frac is not None else 0.0
    lpp = _load_pickup_pos(pos_arr, load_arr)
    hfr = _hull_fill_ratio(pos_arr, load_arr)
    tc  = _top_curvature(load_arr)

    feature_dict = {
        **geom,
        "pickup_delay_frac":  pdf,
        "corner_radius_frac": crf,
        "load_pickup_pos":    lpp,
        "hull_fill_ratio":    hfr,
        "top_curvature":      tc,
        "SPM":             spm,
        "stroke_length":   stroke_length,
        "temperature":     temperature,
        "viscosity":       viscosity,
        "fluid_level":     fluid_level,
        "pump_depth":      pump_depth,
        "production_rate": production_rate,
    }

    return np.array([[feature_dict[col] for col in _feature_cols]], dtype=float)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_card(
    position: list[float],
    load: list[float],
    spm: float,
    stroke_length: float,
    temperature: float,
    viscosity: float,
    fluid_level: float,
    pump_depth: float,
    production_rate: float,
) -> dict:
    """Classify a dynamometer card.

    Returns a dict with:
        predicted_condition  — one of the 4 condition labels, or the special
                               "Gas Interference (low confidence)" label when
                               the model predicts GI but confidence < threshold
        confidence           — float 0–1, probability of the predicted class
        gi_probability       — float 0–1, raw Gas Interference class probability
                               (always present, useful for dashboards)
        top_features         — list[str], top 3 feature names by importance
        explanation          — plain-language explanation
        recommended_action   — suggested corrective action
    """
    _load_model()

    if len(position) < 2 or len(load) < 2:
        raise ValueError("position and load must each contain at least 2 points.")
    if len(position) != len(load):
        raise ValueError("position and load must have the same length.")

    X = _build_feature_vector(
        position, load, spm, stroke_length,
        temperature, viscosity, fluid_level, pump_depth, production_rate,
    )

    raw_predicted = _clf.predict(X)[0]
    proba         = _clf.predict_proba(X)[0]
    confidence    = float(np.max(proba))

    # Raw GI probability (index of "Gas Interference" in sorted class list)
    gi_prob = 0.0
    if "Gas Interference" in _clf.classes_:
        gi_idx  = list(_clf.classes_).index("Gas Interference")
        gi_prob = float(proba[gi_idx])

    # Confidence gating for Gas Interference
    if raw_predicted == "Gas Interference" and confidence < _GI_CONFIDENCE_THRESHOLD:
        predicted_condition = "Gas Interference (low confidence)"
    else:
        predicted_condition = raw_predicted

    # Top 3 features by global importance
    importances = _clf.feature_importances_
    top_idx     = np.argsort(importances)[::-1][:3]
    top_features = [_feature_cols[i] for i in top_idx]

    return {
        "predicted_condition": predicted_condition,
        "confidence":          round(confidence, 4),
        "gi_probability":      round(gi_prob, 4),
        "top_features":        top_features,
        "explanation":         _CONDITION_EXPLANATIONS.get(
                                   predicted_condition,
                                   _CONDITION_EXPLANATIONS.get(raw_predicted, "Unknown condition.")
                               ),
        "recommended_action":  _CONDITION_ACTIONS.get(
                                   predicted_condition,
                                   _CONDITION_ACTIONS.get(raw_predicted, "Review manually.")
                               ),
    }


def get_example_cards() -> list[dict]:
    """Return one example card per condition_label for frontend plotting.

    Returns:
        List of dicts with card_id, well_id, position, load, condition_label,
        risk_level.
    """
    _load_model()

    examples = []
    for label in _classes:
        row = _raw_df[_raw_df["condition_label"] == label].iloc[0]
        examples.append({
            "card_id":         str(row["card_id"]),
            "well_id":         str(row["well_id"]),
            "position":        ast.literal_eval(row["position"]),
            "load":            ast.literal_eval(row["load"]),
            "condition_label": str(row["condition_label"]),
            "risk_level":      str(row["risk_level"]),
        })

    return examples

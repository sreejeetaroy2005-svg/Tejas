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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "dynacard_classifier.pkl")
_META_PATH = os.path.join(_MODEL_DIR, "dynacard_features.json")
_DATA_PATH = os.path.join(_MODEL_DIR, "..", "data", "dynacards_synthetic_v1.csv")

# Condition → plain-language explanation
_CONDITION_EXPLANATIONS = {
    "Normal": "Pump is operating normally — the card shape indicates proper filling and lifting.",
    "Rod Floating": "The rod string is floating on fluid — SPM is too low or fluid level is too high, causing incomplete rod loading.",
    "Fluid Pound": "The pump barrel is not filling completely — the plunger is hitting fluid partway through the downstroke, causing mechanical shock.",
    "Gas Interference": "Gas is entering the pump barrel — compressible gas reduces fillage and causes erratic loading patterns.",
}

# Condition → recommended action
_CONDITION_ACTIONS = {
    "Normal": "Continue current operating parameters.",
    "Rod Floating": "Increase SPM to match inflow rate; check pump-off controller settings.",
    "Fluid Pound": "Reduce SPM to match inflow; check pump-off control and fluid level.",
    "Gas Interference": "Install or check gas separator; reduce SPM; consider gas anchor.",
}

# ---------------------------------------------------------------------------
# Lazy-loaded state
# ---------------------------------------------------------------------------
_clf = None
_feature_cols: list[str] = None  # type: ignore[assignment]
_classes: list[str] = None  # type: ignore[assignment]
_raw_df: pd.DataFrame | None = None


def _load_model() -> None:
    """Load model, metadata, and raw CSV. Called once, cached globally."""
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
        _classes = meta["classes"]

    _raw_df = pd.read_csv(_DATA_PATH)


# ---------------------------------------------------------------------------
# Feature engineering (same as training script)
# ---------------------------------------------------------------------------

def _compute_geometric_features(position: list[float], load: list[float]) -> dict:
    """Compute the 6 geometric features from a position/load card."""
    load_arr = np.array(load)
    pos_arr = np.array(position)

    max_load = float(np.max(load_arr))
    min_load = float(np.min(load_arr))
    load_range = max_load - min_load
    mean_load = float(np.mean(load_arr))
    std_load = float(np.std(load_arr))
    enclosed_area = float(abs(trapezoid(load_arr, pos_arr)))

    return {
        "max_load": max_load,
        "min_load": min_load,
        "load_range": load_range,
        "mean_load": mean_load,
        "std_load": std_load,
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
) -> np.ndarray:
    """Build a 13-feature vector from card data + operating params."""
    geom = _compute_geometric_features(position, load)

    feature_dict = {
        **geom,
        "SPM": spm,
        "stroke_length": stroke_length,
        "temperature": temperature,
        "viscosity": viscosity,
        "fluid_level": fluid_level,
        "pump_depth": pump_depth,
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

    Returns:
        dict with predicted_condition, confidence, top_features, explanation,
        recommended_action.
    """
    _load_model()

    # Validate arrays
    if len(position) < 2 or len(load) < 2:
        raise ValueError("position and load must each contain at least 2 points.")
    if len(position) != len(load):
        raise ValueError("position and load must have the same length.")

    X = _build_feature_vector(
        position, load, spm, stroke_length,
        temperature, viscosity, fluid_level, pump_depth, production_rate,
    )

    predicted = _clf.predict(X)[0]
    proba = _clf.predict_proba(X)[0]
    confidence = float(np.max(proba))

    # Top 3 features by importance
    importances = _clf.feature_importances_
    top_idx = np.argsort(importances)[::-1][:3]
    top_features = [_feature_cols[i] for i in top_idx]

    return {
        "predicted_condition": predicted,
        "confidence": round(confidence, 4),
        "top_features": top_features,
        "explanation": _CONDITION_EXPLANATIONS.get(predicted, "Unknown condition."),
        "recommended_action": _CONDITION_ACTIONS.get(predicted, "Review manually."),
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
            "card_id": str(row["card_id"]),
            "well_id": str(row["well_id"]),
            "position": ast.literal_eval(row["position"]),
            "load": ast.literal_eval(row["load"]),
            "condition_label": str(row["condition_label"]),
            "risk_level": str(row["risk_level"]),
        })

    return examples

"""Train the dynamometer card classifier.

Classifies pump cards into: Normal, Rod Floating, Fluid Pound, Gas Interference.

Usage:
    cd backend
    python scripts/train_dynacard_classifier.py

All data is synthetic demonstration data, not real Oil India field data.
"""

import os
import sys
import ast
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from scipy.integrate import trapezoid

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "..", "data", "dynacards_synthetic_v1.csv")
MODEL_DIR = os.path.join(SCRIPT_DIR, "..", "models")

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer 13 features per dynacard row."""
    df = df.copy()

    # Parse position/load arrays from string format
    df["position_parsed"] = df["position"].apply(ast.literal_eval)
    df["load_parsed"] = df["load"].apply(ast.literal_eval)

    # --- 6 geometric features from the card curve ---
    df["max_load"] = df["load_parsed"].apply(max)
    df["min_load"] = df["load_parsed"].apply(min)
    df["load_range"] = df["max_load"] - df["min_load"]
    df["mean_load"] = df["load_parsed"].apply(np.mean)
    df["std_load"] = df["load_parsed"].apply(np.std)

    # Enclosed area via trapezoidal integration over the closed loop
    # A full dynacard is a closed loop; area = integral of load over position
    # (both upstroke and downstroke). We compute the net enclosed area.
    def enclosed_area(row):
        pos = np.array(row["position_parsed"])
        load = np.array(row["load_parsed"])
        # The card is already a closed loop (first and last points match)
        # Area = integral of load d(position) for the full cycle
        area = abs(trapezoid(load, pos))
        return area

    df["enclosed_area"] = df.apply(enclosed_area, axis=1)

    # --- 7 operating parameter features ---
    # SPM, stroke_length, temperature, viscosity, fluid_level, pump_depth, production_rate
    # (SPM is already in the dataframe as 'SPM')

    return df


# Column names for the 13 features
GEOMETRIC_FEATURES = [
    "max_load", "min_load", "load_range", "mean_load", "std_load", "enclosed_area",
]
OPERATING_FEATURES = [
    "SPM", "stroke_length", "temperature", "viscosity",
    "fluid_level", "pump_depth", "production_rate",
]
FEATURE_COLS = GEOMETRIC_FEATURES + OPERATING_FEATURES
TARGET_COL = "condition_label"


def main() -> None:
    print("=" * 60)
    print("Training Dynamometer Card Classifier")
    print("=" * 60)

    # Load data
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH}")
    print(f"Classes:\n{df[TARGET_COL].value_counts().to_string()}\n")

    # Engineer features
    df = engineer_features(df)
    print(f"Engineered {len(FEATURE_COLS)} features: {FEATURE_COLS}\n")

    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df[TARGET_COL].to_numpy(dtype=str)

    # Stratified 80/20 split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}\n")

    # Train RandomForestClassifier
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # Evaluate
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print("--- Results ---")
    print(f"\nAccuracy: {acc:.4f} ({acc*100:.1f}%)\n")

    labels = sorted(df[TARGET_COL].unique())
    print("Classification Report:")
    print(classification_report(y_test, y_pred, target_names=labels))

    print("Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    # Pretty-print
    header = "".join(f"{name:>18}" for name in labels)
    print(f"{'':>18}{header}")
    for i, row_label in enumerate(labels):
        row_str = "".join(f"{cm[i][j]:>18}" for j in range(len(labels)))
        print(f"{row_label:>18}{row_str}")
    print()

    # Feature importances
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("Top 10 Feature Importances:")
    for rank, idx in enumerate(sorted_idx[:10]):
        print(f"  {rank+1:>2}. {FEATURE_COLS[idx]:>20s}  {importances[idx]:.4f}")
    print()

    # Save model + metadata
    os.makedirs(MODEL_DIR, exist_ok=True)

    import joblib
    model_path = os.path.join(MODEL_DIR, "dynacard_classifier.pkl")
    meta_path = os.path.join(MODEL_DIR, "dynacard_features.json")

    joblib.dump(clf, model_path)
    with open(meta_path, "w") as f:
        json.dump({
            "feature_columns": FEATURE_COLS,
            "classes": labels,
            "accuracy": round(acc, 4),
        }, f, indent=2)

    print(f"Saved model to {model_path}")
    print(f"Saved metadata to {meta_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()

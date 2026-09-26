"""Train the dynamometer card classifier.

Classifies pump cards into: Normal, Rod Floating, Fluid Pound, Gas Interference.

Changes vs v1
-------------
* Feature set expanded from 13 → 18:
    - pickup_delay_frac   (from CSV, encodes GI delayed pickup directly)
    - corner_radius_frac  (from CSV, encodes GI rounded corners directly)
    - load_pickup_pos     (computed: position fraction where load first exceeds
                          50% of max_load on the upstroke)
    - hull_fill_ratio     (computed: card enclosed area / convex-hull area;
                          rounded GI cards fill less of their hull than Normal)
    - top_curvature       (computed: RMS of load second-derivative near the
                          top portion of the card — high for sharp corners,
                          low for rounded ones)
* 5-fold stratified cross-validation replaces the single 80/20 split.
* Macro-F1 reported as headline metric alongside accuracy.
* Severity-stratified breakdown for Gas Interference (low/mid/high tercile).
* Full metadata (CV scores, severity breakdown, feature importances) written
  into models/dynacard_features.json.

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
from scipy.integrate import trapezoid
from scipy.spatial import ConvexHull
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
    f1_score,
)
import joblib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "..", "data", "dynacards_synthetic_v1.csv")
MODEL_DIR = os.path.join(SCRIPT_DIR, "..", "models")

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

# Column names — keep in sync with dynacard_service.py
GEOMETRIC_FEATURES = [
    "max_load", "min_load", "load_range", "mean_load", "std_load", "enclosed_area",
]
SHAPE_FEATURES = [
    # Direct shape parameters from generator (zero for non-GI cards)
    "pickup_delay_frac",
    "corner_radius_frac",
    # Computed shape features that can also be derived at inference time from
    # the raw position/load arrays (no dependency on CSV columns):
    "load_pickup_pos",   # fraction of upstroke where load exceeds 50% of max
    "hull_fill_ratio",   # enclosed_area / convex_hull_area (1.0 = sharp card)
    "top_curvature",     # RMS second-derivative near top of card
]
OPERATING_FEATURES = [
    "SPM", "stroke_length", "temperature", "viscosity",
    "fluid_level", "pump_depth", "production_rate",
]
FEATURE_COLS = GEOMETRIC_FEATURES + SHAPE_FEATURES + OPERATING_FEATURES
TARGET_COL = "condition_label"


# ---------------------------------------------------------------------------
# Computed shape feature helpers
# ---------------------------------------------------------------------------

def _load_pickup_pos(position: np.ndarray, load: np.ndarray) -> float:
    """Fraction of full stroke at which upstroke load first exceeds 50% of max.

    For a Normal card this happens very early (~0.05-0.12).
    For a Gas Interference card it happens later (~0.20-0.45) because the
    pump barrel is full of gas that must compress before fluid load builds.
    """
    n_half = len(position) // 2
    upstroke_load = load[:n_half]
    upstroke_pos = position[:n_half]
    stroke = float(np.max(position) - np.min(position))
    if stroke < 1e-6:
        return 0.0
    threshold = float(np.min(load)) + 0.5 * (float(np.max(load)) - float(np.min(load)))
    above = np.where(upstroke_load >= threshold)[0]
    if len(above) == 0:
        return 1.0
    pickup_pos = upstroke_pos[above[0]]
    return float(np.clip(pickup_pos / stroke, 0.0, 1.0))


def _hull_fill_ratio(position: np.ndarray, load: np.ndarray) -> float:
    """Ratio of card's enclosed loop area to its convex-hull area.

    A sharp-cornered Normal card fills close to 1.0 of its bounding hull.
    A rounded Gas Interference card leaves more empty space in the hull
    corners, giving a ratio measurably below 1.0.
    """
    pts = np.column_stack([position, load])
    # Need at least 3 non-collinear points for a hull
    try:
        hull = ConvexHull(pts)
        hull_area = hull.volume  # ConvexHull.volume = area in 2-D
    except Exception:
        return 1.0
    # Enclosed loop area via trapezoidal rule on the closed curve
    enclosed = abs(trapezoid(load, position))
    if hull_area < 1e-6:
        return 1.0
    return float(np.clip(enclosed / hull_area, 0.0, 1.0))


def _top_curvature(load: np.ndarray) -> float:
    """RMS of load second-derivative near the top 20% of load values.

    Sharp corners produce high local curvature; rounded GI corners produce
    low curvature near the top of the card.
    """
    threshold = float(np.percentile(load, 80))
    top_mask = load >= threshold
    top_load = load[top_mask]
    if len(top_load) < 3:
        return 0.0
    d2 = np.diff(np.diff(top_load.astype(float)))
    return float(np.sqrt(np.mean(d2 ** 2)))


# ---------------------------------------------------------------------------
# Main feature engineering
# ---------------------------------------------------------------------------

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer all 18 features per dynacard row."""
    df = df.copy()

    # Parse position/load arrays
    df["position_parsed"] = df["position"].apply(ast.literal_eval)
    df["load_parsed"] = df["load"].apply(ast.literal_eval)

    # --- 6 geometric features ---
    df["max_load"]     = df["load_parsed"].apply(max)
    df["min_load"]     = df["load_parsed"].apply(min)
    df["load_range"]   = df["max_load"] - df["min_load"]
    df["mean_load"]    = df["load_parsed"].apply(np.mean)
    df["std_load"]     = df["load_parsed"].apply(np.std)
    df["enclosed_area"] = df.apply(
        lambda r: float(abs(trapezoid(r["load_parsed"], r["position_parsed"]))),
        axis=1,
    )

    # --- shape features: pickup_delay_frac, corner_radius_frac ---
    # If already present as CSV columns (generated data), use them directly.
    # If not (e.g. old CSV without shape columns), fall back to 0.
    if "pickup_delay_frac" not in df.columns:
        df["pickup_delay_frac"] = 0.0
    if "corner_radius_frac" not in df.columns:
        df["corner_radius_frac"] = 0.0
    df["pickup_delay_frac"] = df["pickup_delay_frac"].fillna(0.0).astype(float)
    df["corner_radius_frac"] = df["corner_radius_frac"].fillna(0.0).astype(float)

    # --- computed shape features ---
    def _lpp(row):
        return _load_pickup_pos(
            np.array(row["position_parsed"]), np.array(row["load_parsed"])
        )

    def _hfr(row):
        return _hull_fill_ratio(
            np.array(row["position_parsed"]), np.array(row["load_parsed"])
        )

    def _tc(row):
        return _top_curvature(np.array(row["load_parsed"]))

    df["load_pickup_pos"] = df.apply(_lpp, axis=1)
    df["hull_fill_ratio"] = df.apply(_hfr, axis=1)
    df["top_curvature"]   = df.apply(_tc, axis=1)

    return df


# ---------------------------------------------------------------------------
# Severity tercile helper
# ---------------------------------------------------------------------------

def _severity_tercile(s: float) -> str:
    """Map a severity value to Low / Mid / High tercile label."""
    if s < 0.267:
        return "Low"
    if s < 0.383:
        return "Mid"
    return "High"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 65)
    print("Training Dynamometer Card Classifier")
    print("=" * 65)

    # ------------------------------------------------------------------ load
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH}")
    print(f"\nClass distribution:\n{df[TARGET_COL].value_counts().to_string()}\n")

    # -------------------------------------------------------- feature engineering
    print("Engineering features …")
    df = engineer_features(df)
    print(f"Feature set ({len(FEATURE_COLS)} features): {FEATURE_COLS}\n")

    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df[TARGET_COL].to_numpy(dtype=str)
    labels = sorted(df[TARGET_COL].unique())

    # -------------------------------------------------------- 5-fold stratified CV
    print("Running 5-fold stratified cross-validation …")
    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # Collect per-fold metrics
    fold_acc = []
    fold_macro_f1 = []
    fold_gi_precision = []
    fold_gi_recall = []
    fold_gi_f1 = []

    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]
        clf.fit(X_tr, y_tr)
        y_pred = clf.predict(X_te)
        acc = accuracy_score(y_te, y_pred)
        mf1 = f1_score(y_te, y_pred, average="macro", zero_division=0)
        fold_acc.append(acc)
        fold_macro_f1.append(mf1)
        # Per-class for GI
        from sklearn.metrics import precision_score, recall_score
        gi_p = precision_score(y_te, y_pred, labels=["Gas Interference"],
                               average="macro", zero_division=0)
        gi_r = recall_score(y_te, y_pred, labels=["Gas Interference"],
                            average="macro", zero_division=0)
        gi_f = f1_score(y_te, y_pred, labels=["Gas Interference"],
                        average="macro", zero_division=0)
        fold_gi_precision.append(gi_p)
        fold_gi_recall.append(gi_r)
        fold_gi_f1.append(gi_f)
        print(f"  Fold {fold}: acc={acc:.4f}  macro-F1={mf1:.4f}  "
              f"GI p={gi_p:.4f} r={gi_r:.4f} f1={gi_f:.4f}")

    print()
    print("--- 5-Fold CV Summary ---")
    print(f"  Accuracy  : {np.mean(fold_acc):.4f} ± {np.std(fold_acc):.4f}")
    print(f"  Macro-F1  : {np.mean(fold_macro_f1):.4f} ± {np.std(fold_macro_f1):.4f}")
    print(f"  GI Precision: {np.mean(fold_gi_precision):.4f} ± {np.std(fold_gi_precision):.4f}")
    print(f"  GI Recall   : {np.mean(fold_gi_recall):.4f} ± {np.std(fold_gi_recall):.4f}")
    print(f"  GI F1       : {np.mean(fold_gi_f1):.4f} ± {np.std(fold_gi_f1):.4f}")
    print()

    # ------------------------------------------------------ full classification report
    # cross_val_predict gives out-of-fold predictions across the full dataset
    y_oof = cross_val_predict(clf, X, y, cv=skf, n_jobs=-1)

    print("--- Full Out-of-Fold Classification Report ---")
    print(classification_report(y, y_oof, target_names=labels, zero_division=0))

    print("Confusion Matrix (rows=actual, cols=predicted):")
    cm = confusion_matrix(y, y_oof, labels=labels)
    header = "".join(f"{name:>18}" for name in labels)
    print(f"{'':>18}{header}")
    for i, row_label in enumerate(labels):
        row_str = "".join(f"{cm[i][j]:>18}" for j in range(len(labels)))
        print(f"{row_label:>18}{row_str}")
    print()

    # ---------------------------------------------------- severity-stratified breakdown
    gi_mask = df[TARGET_COL] == "Gas Interference"
    gi_df = df[gi_mask].copy()
    gi_df["tercile"] = gi_df["severity"].apply(_severity_tercile)
    gi_df["oof_pred"] = y_oof[gi_mask]

    print("--- Gas Interference: Severity-Stratified Breakdown ---")
    severity_breakdown = {}
    for tercile in ["Low", "Mid", "High"]:
        t_df = gi_df[gi_df["tercile"] == tercile]
        if len(t_df) == 0:
            continue
        t_true = [TARGET_COL] * len(t_df)  # placeholder — use arrays below
        t_true = np.array(["Gas Interference"] * len(t_df))
        t_pred = t_df["oof_pred"].to_numpy()
        n_correct = int((t_pred == "Gas Interference").sum())
        prec = precision_score(t_true, t_pred, labels=["Gas Interference"],
                               average="macro", zero_division=0)
        rec  = recall_score(t_true, t_pred, labels=["Gas Interference"],
                            average="macro", zero_division=0)
        f1   = f1_score(t_true, t_pred, labels=["Gas Interference"],
                        average="macro", zero_division=0)
        sev_range = (float(t_df["severity"].min()), float(t_df["severity"].max()))
        print(f"  {tercile:>4s} severity (sev={sev_range[0]:.2f}–{sev_range[1]:.2f}, "
              f"n={len(t_df):>3d}): "
              f"precision={prec:.3f}  recall={rec:.3f}  f1={f1:.3f}  "
              f"correct={n_correct}/{len(t_df)}")
        severity_breakdown[tercile] = {
            "n": len(t_df),
            "severity_range": sev_range,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "correct": n_correct,
        }
    print()

    # ------------------------------------------- fit final model on full dataset
    print("Fitting final model on full dataset …")
    clf.fit(X, y)

    # Feature importances
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("Top 10 Feature Importances:")
    for rank, idx in enumerate(sorted_idx[:10]):
        print(f"  {rank+1:>2}. {FEATURE_COLS[idx]:>22s}  {importances[idx]:.4f}")
    print()

    # ------------------------------------------------------------------- save
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "dynacard_classifier.pkl")
    meta_path  = os.path.join(MODEL_DIR, "dynacard_features.json")

    joblib.dump(clf, model_path)

    meta = {
        "feature_columns": FEATURE_COLS,
        "classes": labels,
        # CV aggregate metrics
        "cv_accuracy_mean":    round(float(np.mean(fold_acc)), 4),
        "cv_accuracy_std":     round(float(np.std(fold_acc)), 4),
        "cv_macro_f1_mean":    round(float(np.mean(fold_macro_f1)), 4),
        "cv_macro_f1_std":     round(float(np.std(fold_macro_f1)), 4),
        "cv_gi_precision_mean": round(float(np.mean(fold_gi_precision)), 4),
        "cv_gi_recall_mean":    round(float(np.mean(fold_gi_recall)), 4),
        "cv_gi_f1_mean":        round(float(np.mean(fold_gi_f1)), 4),
        # Severity breakdown for Gas Interference
        "gi_severity_breakdown": severity_breakdown,
        # Feature importances
        "feature_importances": {
            FEATURE_COLS[i]: round(float(importances[i]), 6)
            for i in range(len(FEATURE_COLS))
        },
        "top_features_ranked": [FEATURE_COLS[i] for i in sorted_idx],
        # Backward-compat: single accuracy value (CV mean)
        "accuracy": round(float(np.mean(fold_acc)), 4),
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"Saved model    → {model_path}")
    print(f"Saved metadata → {meta_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()

"""Train 7-day reservoir temperature and production forecast models.

Two XGBoost regressors that predict next-day values recursively:
  - temperature_model → predicts reservoir_temperature_c
  - production_model  → predicts oil_bpd

Usage:
    cd backend
    python scripts/train_forecast_model.py

All data is synthetic demonstration data, not real Oil India field data.
"""

import os
import sys
import json

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SCRIPT_DIR, "..", "data", "bgw_01_daily.csv")
MODEL_DIR = os.path.join(SCRIPT_DIR, "..", "models")

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

# Columns used as lag features (previous row's values)
LAG_COLS = ["reservoir_temperature_c", "viscosity_cp", "oil_bpd"]

# Columns used as static context (current row)
CONTEXT_COLS = ["days_since_steam_injection", "spm", "vfd_frequency_hz"]

# Label encoding for css_stage
_STAGE_ENCODE = {"injection": 0, "soak": 1, "production": 2}


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag and context features to the dataframe."""
    df = df.copy()

    # Label-encode css_stage
    df["css_stage_enc"] = df["css_stage"].map(_STAGE_ENCODE).fillna(2).astype(int)

    # Lag features: previous row's values
    for col in LAG_COLS:
        df[f"lag_1_{col}"] = df[col].shift(1)

    # Context features (current row, held constant in recursive forecast)
    df["context_days_since_injection"] = df["days_since_steam_injection"]
    df["context_spm"] = df["spm"]
    df["context_vfd"] = df["vfd_frequency_hz"]
    df["context_css_stage_enc"] = df["css_stage_enc"]

    return df


def get_feature_columns() -> list[str]:
    """Return the ordered list of feature column names."""
    return (
        [f"lag_1_{col}" for col in LAG_COLS]
        + [
            "context_days_since_injection",
            "context_spm",
            "context_vfd",
            "context_css_stage_enc",
        ]
    )


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("Training 7-Day Forecast Models")
    print("=" * 60)

    # Load data
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} rows from {DATA_PATH}")

    # Engineer features
    df = engineer_features(df)

    # Drop first row (no lag available)
    df = df.dropna(subset=[f"lag_1_{LAG_COLS[0]}"]).reset_index(drop=True)
    print(f"After dropping rows with no lag: {len(df)} rows")

    # Feature / target columns
    feature_cols = get_feature_columns()
    temp_target = "reservoir_temperature_c"
    prod_target = "oil_bpd"

    X = df[feature_cols].values
    y_temp = df[temp_target].values
    y_prod = df[prod_target].values

    # Time-based split: last 25 rows = test, rest = train
    split_idx = len(df) - 25
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_temp_train, y_temp_test = y_temp[:split_idx], y_temp[split_idx:]
    y_prod_train, y_prod_test = y_prod[:split_idx], y_prod[split_idx:]

    print(f"Train: {len(X_train)} rows, Test: {len(X_test)} rows")

    # Train temperature model
    print("\n--- Temperature Model ---")
    temp_model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    temp_model.fit(X_train, y_temp_train)
    y_temp_pred = temp_model.predict(X_test)
    temp_mae = mean_absolute_error(y_temp_test, y_temp_pred)
    temp_r2 = r2_score(y_temp_test, y_temp_pred)
    print(f"  MAE:  {temp_mae:.3f} °C")
    print(f"  R²:   {temp_r2:.4f}")

    # Train production model
    print("\n--- Production Model ---")
    prod_model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    prod_model.fit(X_train, y_prod_train)
    y_prod_pred = prod_model.predict(X_test)
    prod_mae = mean_absolute_error(y_prod_test, y_prod_pred)
    prod_r2 = r2_score(y_prod_test, y_prod_pred)
    print(f"  MAE:  {prod_mae:.3f} bbl/day")
    print(f"  R²:   {prod_r2:.4f}")

    # Save models and metadata
    os.makedirs(MODEL_DIR, exist_ok=True)

    temp_model_path = os.path.join(MODEL_DIR, "temperature_model.pkl")
    prod_model_path = os.path.join(MODEL_DIR, "production_model.pkl")
    temp_meta_path = os.path.join(MODEL_DIR, "temperature_features.json")
    prod_meta_path = os.path.join(MODEL_DIR, "production_features.json")

    temp_model.save_model(temp_model_path)
    prod_model.save_model(prod_model_path)

    # Save feature columns and MAE as metadata
    meta = {"feature_columns": feature_cols}
    with open(temp_meta_path, "w") as f:
        json.dump({**meta, "mae": round(temp_mae, 4), "r2": round(temp_r2, 4)}, f, indent=2)
    with open(prod_meta_path, "w") as f:
        json.dump({**meta, "mae": round(prod_mae, 4), "r2": round(prod_r2, 4)}, f, indent=2)

    print(f"\nSaved models to {MODEL_DIR}/")
    print(f"  {temp_model_path}")
    print(f"  {prod_model_path}")
    print(f"  {temp_meta_path}")
    print(f"  {prod_meta_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()

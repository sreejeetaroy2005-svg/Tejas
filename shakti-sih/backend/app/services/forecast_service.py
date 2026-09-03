"""7-Day Reservoir Temperature & Production Forecast Service.

Loads two XGBoost regressors (trained by scripts/train_forecast_model.py)
and recursively predicts forward day-by-day.

Models are loaded once at first call (lazy + cached).
If models haven't been trained, a clear error is raised.

All data is synthetic demonstration data, not real Oil India field data.
"""

import os
import json

import numpy as np
import pandas as pd
import xgboost as xgb

from app.services.data_service import get_dataframe

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "models"
)

_TEMP_MODEL_PATH = os.path.join(_MODEL_DIR, "temperature_model.pkl")
_PROD_MODEL_PATH = os.path.join(_MODEL_DIR, "production_model.pkl")
_TEMP_META_PATH = os.path.join(_MODEL_DIR, "temperature_features.json")
_PROD_META_PATH = os.path.join(_MODEL_DIR, "production_features.json")

# Label encoding for css_stage (must match training script)
_STAGE_ENCODE = {"injection": 0, "soak": 1, "production": 2}

# ---------------------------------------------------------------------------
# Lazy-loaded model state
# ---------------------------------------------------------------------------
_temp_model: xgb.XGBRegressor | None = None
_prod_model: xgb.XGBRegressor | None = None
_feature_cols: list[str] | None = None
_temp_mae: float = 0.0
_prod_mae: float = 0.0


def _load_models() -> None:
    """Load models from disk. Called once, cached globally."""
    global _temp_model, _prod_model, _feature_cols, _temp_mae, _prod_mae

    if _temp_model is not None:
        return  # Already loaded

    for path in [_TEMP_MODEL_PATH, _PROD_MODEL_PATH, _TEMP_META_PATH, _PROD_META_PATH]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Forecast model not found at {path}. "
                "Run scripts/train_forecast_model.py first."
            )

    _temp_model = xgb.XGBRegressor()
    _temp_model.load_model(_TEMP_MODEL_PATH)

    _prod_model = xgb.XGBRegressor()
    _prod_model.load_model(_PROD_MODEL_PATH)

    with open(_TEMP_META_PATH) as f:
        temp_meta = json.load(f)
        _feature_cols = temp_meta["feature_columns"]
        _temp_mae = temp_meta["mae"]

    with open(_PROD_META_PATH) as f:
        prod_meta = json.load(f)
        _prod_mae = prod_meta["mae"]


# ---------------------------------------------------------------------------
# Feature engineering (single-row, for recursive prediction)
# ---------------------------------------------------------------------------

def _build_feature_row(
    lag_temp: float,
    lag_visc: float,
    lag_oil: float,
    days_since_injection: float,
    spm: float,
    vfd: float,
    css_stage: str,
) -> np.ndarray:
    """Build a single feature vector from lag + context values."""
    stage_enc = _STAGE_ENCODE.get(css_stage, 2)
    row = [
        lag_temp,
        lag_visc,
        lag_oil,
        days_since_injection,
        spm,
        vfd,
        stage_enc,
    ]
    return np.array([row], dtype=np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def forecast_7_days(
    well_id: str,
    days: int = 7,
) -> dict:
    """Generate a recursive 7-day forecast for temperature and oil production.

    Args:
        well_id: Well identifier (e.g. "BGW-01").
        days: Number of days to forecast (default 7).

    Returns:
        dict with well_id, days, temperature_mae, production_mae,
        forecast (list of day dicts), data_note.
    """
    _load_models()

    df = get_dataframe()
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise ValueError(f"Well '{well_id}' not found.")

    # Get the most recent row as the starting point
    latest = well_df.iloc[-1]

    # Seed values from the latest actual data
    lag_temp = float(latest["reservoir_temperature_c"])
    lag_visc = float(latest["viscosity_cp"])
    lag_oil = float(latest["oil_bpd"])
    days_since_inj = float(latest["days_since_steam_injection"])
    spm = float(latest["spm"])
    vfd = float(latest["vfd_frequency_hz"])
    css_stage = str(latest["css_stage"])

    # Generate forecast dates
    last_date = pd.to_datetime(latest["date"])
    forecast_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1), periods=days, freq="D"
    )

    forecast = []
    for i, fdate in enumerate(forecast_dates):
        # Build feature row
        X = _build_feature_row(
            lag_temp, lag_visc, lag_oil,
            days_since_inj, spm, vfd, css_stage,
        )

        # Predict
        pred_temp = float(_temp_model.predict(X)[0])
        pred_oil = float(_prod_model.predict(X)[0])

        # Clamp to physically plausible ranges
        pred_temp = max(30.0, min(300.0, pred_temp))
        pred_oil = max(0.0, pred_oil)

        forecast.append({
            "date": fdate.strftime("%Y-%m-%d"),
            "predicted_temperature_c": round(pred_temp, 2),
            "predicted_oil_bpd": round(pred_oil, 2),
        })

        # Update lag values for next step (recursive)
        lag_temp = pred_temp
        lag_oil = pred_oil
        # Viscosity is derived from temperature in the synthetic model;
        # approximate it with the same exponential formula for the next lag
        mu_k = 0.049707
        lag_visc = 8000.0 * np.exp(-mu_k * (pred_temp - 45.0))
        days_since_inj += 1

    return {
        "well_id": well_id,
        "days": days,
        "temperature_mae": _temp_mae,
        "production_mae": _prod_mae,
        "forecast": forecast,
        "data_note": "Synthetic demonstration data — not real Oil India field data.",
    }

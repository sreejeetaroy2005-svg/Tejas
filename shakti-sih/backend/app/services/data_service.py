"""Data service — loads the synthetic BGW-01 CSV once at startup.

All data is synthetic demonstration data, not real Oil India field data.
"""

import os

import pandas as pd

_DF: pd.DataFrame | None = None

# Relative path to the CSV from this file's location
_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "bgw_01_daily.csv"
)


def load_data() -> pd.DataFrame:
    """Load the synthetic daily CSV into memory.

    Called once during app startup via the FastAPI lifespan context manager.
    Returns the loaded DataFrame for convenience.
    """
    global _DF
    resolved = os.path.abspath(_CSV_PATH)
    if not os.path.exists(resolved):
        raise FileNotFoundError(
            f"Synthetic data CSV not found at {resolved}. "
            "Run scripts/synthetic_data_generator.py first."
        )
    _DF = pd.read_csv(resolved)
    return _DF


def get_dataframe() -> pd.DataFrame:
    """Return the loaded DataFrame.

    Raises RuntimeError if load_data() hasn't been called yet.
    """
    if _DF is None:
        raise RuntimeError("Data not loaded. Call load_data() first.")
    return _DF


def get_latest_row_for_well(well_id: str) -> pd.Series:
    """Return the most recent row for a given well."""
    df = get_dataframe()
    well_df = df[df["well_id"] == well_id]
    if well_df.empty:
        raise ValueError(f"Well '{well_id}' not found in dataset.")
    return well_df.iloc[-1]


def get_well_ids() -> list[str]:
    """Return sorted unique well IDs in the dataset."""
    df = get_dataframe()
    return sorted(df["well_id"].unique().tolist())

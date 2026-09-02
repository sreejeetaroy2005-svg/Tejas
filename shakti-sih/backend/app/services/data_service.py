"""Data service — loads data from Supabase with a local CSV fallback.

All data is synthetic demonstration data, not real Oil India field data.
"""

import os
import logging

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

_DF: pd.DataFrame | None = None

# Relative path to the CSV from this file's location
_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "bgw_01_daily.csv"
)

def _load_csv_fallback() -> pd.DataFrame:
    """Load the synthetic daily CSV as a fallback."""
    resolved = os.path.abspath(_CSV_PATH)
    if not os.path.exists(resolved):
        raise FileNotFoundError(
            f"Synthetic data CSV not found at {resolved}. "
            "Run scripts/synthetic_data_generator.py first."
        )
    return pd.read_csv(resolved)

def get_supabase_client() -> Client | None:
    """Create and return a Supabase client if env vars are present."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        logging.warning(f"Failed to create Supabase client: {e}")
        return None

def fetch_supabase_data(well_id: str | None = None) -> pd.DataFrame:
    """Query the well_daily_data table, optionally filtered by well_id."""
    client = get_supabase_client()
    if not client:
        raise ValueError("Supabase configuration missing or invalid.")
    
    query = client.table("well_daily_data").select("*")
    if well_id:
        query = query.eq("well_id", well_id)
        
    response = query.execute()
    
    if not response.data:
        raise ValueError("No data returned from Supabase well_daily_data table.")
        
    df = pd.DataFrame(response.data)
    
    # Ensure types match the expected CSV shapes
    df = df.infer_objects()
    return df

def load_data() -> pd.DataFrame:
    """Load the daily data into memory.

    Called once during app startup via the FastAPI lifespan context manager.
    Returns the loaded DataFrame for convenience.
    """
    global _DF
    try:
        _DF = fetch_supabase_data()
        print("INFO: Successfully loaded data from Supabase.")
    except Exception as e:
        print(f"WARNING: Failed to fetch from Supabase ({e}) — falling back to CSV.")
        _DF = _load_csv_fallback()
        
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

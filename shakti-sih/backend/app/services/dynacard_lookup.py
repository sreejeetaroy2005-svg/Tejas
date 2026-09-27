"""Dynacard lookup — find the closest matching card for a well's current state.

Because the synthetic dynacard dataset (dynacards_synthetic_v1.csv) uses
generic WELL-xxx IDs that do not correspond directly to BGW-01, this module
selects the card whose operating parameters most closely match the well's
current scalar values (SPM, viscosity, production_rate) and passes it to
classify_card() for an ML-based condition reading.

This is clearly labeled in all API responses as:
    diagnosis_source = "ml_classifier"
with a note that the card was selected by nearest-neighbour matching from
the synthetic dynacard library, not captured live from BGW-01.

All data is SYNTHETIC DEMONSTRATION DATA.
"""

import os
import ast

import numpy as np
import pandas as pd

from app.services.dynacard_service import classify_card, _load_model, _raw_df

# Path to the dynacard CSV (shared with dynacard_service.py)
_DYNACARD_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "dynacards_synthetic_v1.csv"
)


def _ensure_loaded() -> pd.DataFrame:
    """Ensure the dynacard model and raw data are loaded; return the raw df."""
    _load_model()
    # _raw_df is populated by _load_model()
    from app.services.dynacard_service import _raw_df as df
    if df is None:
        raise RuntimeError("Dynacard model not loaded — call _load_model() first.")
    return df


def get_ml_diagnosis_for_well(
    spm: float,
    viscosity_cp: float,
    oil_bpd: float,
    reservoir_temperature_c: float = 80.0,
) -> dict:
    """Return an ML diagnosis for a well by nearest-neighbour card matching.

    Selects the card from the dynacard library whose SPM and viscosity most
    closely match the provided well state, then classifies that card via the
    trained RandomForest classifier.

    Args:
        spm: Current strokes per minute of the well's SRP.
        viscosity_cp: Current oil viscosity (centipoise).
        oil_bpd: Current oil production rate (bbl/day), used as production_rate.
        reservoir_temperature_c: Current reservoir temperature (°C), converted
            to Fahrenheit for the classifier's temperature feature.

    Returns:
        Dict from classify_card() plus extra provenance fields:
            diagnosis_source       — always "ml_classifier"
            matched_card_id        — card_id of the selected nearest card
            matched_well_id        — well_id of the selected nearest card
            match_note             — human-readable provenance note
    """
    df = _ensure_loaded()

    # Nearest-neighbour matching on SPM and log-viscosity
    # (log-viscosity keeps the heavy-oil range from dominating Euclidean dist)
    spm_std = df["SPM"].std() or 1.0
    log_visc = np.log1p(viscosity_cp)
    log_visc_col = np.log1p(df["viscosity"].values)
    log_visc_std = log_visc_col.std() or 1.0

    dist = np.sqrt(
        ((df["SPM"].values - spm) / spm_std) ** 2
        + ((log_visc_col - log_visc) / log_visc_std) ** 2
    )
    best_idx = int(np.argmin(dist))
    row = df.iloc[best_idx]

    position = ast.literal_eval(row["position"])
    load = ast.literal_eval(row["load"])

    # Temperature: the dynacard CSV stores it in °F; convert reservoir °C → °F
    temp_f = reservoir_temperature_c * 9.0 / 5.0 + 32.0

    result = classify_card(
        position=position,
        load=load,
        spm=spm,
        stroke_length=float(row["stroke_length"]),
        temperature=temp_f,
        viscosity=viscosity_cp,
        fluid_level=float(row["fluid_level"]),
        pump_depth=float(row["pump_depth"]),
        production_rate=oil_bpd,
    )

    result["diagnosis_source"] = "ml_classifier"
    result["matched_card_id"] = str(row["card_id"])
    result["matched_well_id"] = str(row["well_id"])
    result["match_note"] = (
        f"Card selected by nearest-neighbour match on SPM/viscosity from "
        f"synthetic dynacard library ({len(df)} cards). "
        f"Matched card: {row['card_id']} (SPM={row['SPM']:.1f}, "
        f"visc={row['viscosity']:.0f} cP, "
        f"true label={row['condition_label']})."
    )

    return result

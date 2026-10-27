"""Per-well physics parameter service.

Loads backend/data/well_params.json once and exposes get_well_params().
This is the single source of truth for the five parameters that differ
between the fleet generator and the simulator — keeping both in sync
without hard-coding values in multiple places.

See data/well_params.json for the schema and values.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

# Module-level simulator defaults — these are the BGW-01 constants that
# every other part of the code used to hard-code.  They are reproduced here
# so callers that already work with BGW-01 can simply omit the well_id.
DEFAULT_OIL_MAX_BPD     = 220.0
DEFAULT_WATER_CUT       = 0.35
DEFAULT_DECAY_TAU       = 10.0
DEFAULT_FILLAGE_CAP     = 98.0
DEFAULT_MOTOR_BASE_AMPS = 28.0

_PARAMS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "well_params.json"
)


@dataclass(frozen=True)
class WellParams:
    """Immutable per-well physics parameters.

    All values default to the BGW-01 / simulator baseline so any code path
    that does not look up a well still produces the same output as before.
    """
    oil_max_bpd:     float = DEFAULT_OIL_MAX_BPD
    water_cut:       float = DEFAULT_WATER_CUT
    decay_tau:       float = DEFAULT_DECAY_TAU
    fillage_cap:     float = DEFAULT_FILLAGE_CAP
    motor_base_amps: float = DEFAULT_MOTOR_BASE_AMPS
    prod_days_max:   int   = 55   # BGW-01 PRODUCTION_DAYS_RANGE[1]


@lru_cache(maxsize=1)
def _load_params_file() -> dict[str, WellParams]:
    """Load and cache the well_params.json file.  Called at most once."""
    path = os.path.abspath(_PARAMS_PATH)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"well_params.json not found at {path}.  "
            "This file is required for per-well simulation accuracy."
        )
    with open(path) as f:
        raw = json.load(f)

    result: dict[str, WellParams] = {}
    for well_id, values in raw.items():
        if well_id.startswith("_"):  # skip _comment, _schema keys
            continue
        result[well_id] = WellParams(
            oil_max_bpd     = float(values["oil_max_bpd"]),
            water_cut       = float(values["water_cut"]),
            decay_tau       = float(values["decay_tau"]),
            fillage_cap     = float(values["fillage_cap"]),
            motor_base_amps = float(values["motor_base_amps"]),
            prod_days_max   = int(values.get("prod_days_max", 55)),
        )
    return result


def get_well_params(well_id: str) -> WellParams:
    """Return the WellParams for the given well_id.

    Falls back to BGW-01 defaults if the well_id is not in the file,
    so the API never hard-errors on an unknown well.

    Args:
        well_id: e.g. "BGW-04"

    Returns:
        WellParams with the well's oil_max_bpd, water_cut, etc.
    """
    params = _load_params_file()
    return params.get(well_id, WellParams())


def get_all_well_ids() -> list[str]:
    """Return the list of well IDs defined in well_params.json."""
    return sorted(_load_params_file().keys())

"""Backtest router — GET /api/backtest.

Returns the pre-computed backtest results from data/backtest_results.json.
Run scripts/backtest.py to regenerate the file.

All data is synthetic demonstration data.
"""

import json
import os

from fastapi import APIRouter, HTTPException

from app.models import BacktestResponse

router = APIRouter(tags=["backtest"])

_RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "backtest_results.json"
)


@router.get(
    "/backtest",
    response_model=BacktestResponse,
    summary="Backtest results — Tejas vs baseline",
)
def get_backtest() -> BacktestResponse:
    """Return the pre-computed backtest comparing Tejas recommendations
    against the recorded baseline settings over all 180 days.

    Returns 404 if the results file has not been generated yet.
    Run ``python scripts/backtest.py`` from the backend directory to create it.
    """
    path = os.path.abspath(_RESULTS_PATH)
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=(
                "Backtest results not found. "
                "Run `python scripts/backtest.py` from the backend directory "
                "to generate data/backtest_results.json."
            ),
        )
    with open(path) as f:
        raw = json.load(f)

    return BacktestResponse(**raw)

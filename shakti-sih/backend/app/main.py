"""Tejas — Decision-Support Digital Twin for Heavy-Oil Well Operations.

This application provides API endpoints for monitoring and optimizing
Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP) operations
on heavy-oil wells.

All data is SYNTHETIC DEMONSTRATION DATA and does NOT represent real
Oil India field data.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import wells, simulate, optimize, dynacards, backtest, fleet
from app.services.data_service import load_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load synthetic CSV data once at startup."""
    load_data()
    yield


app = FastAPI(
    title="Tejas — Heavy-Oil Digital Twin",
    description=(
        "Decision-support API for CSS/SRP operations on heavy-oil wells. "
        "All data is synthetic demonstration data. "
        "SIH 2025 · BMS College of Engineering, Bangalore · PS SIH26120."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — restrict to configured origins in production.
# Set the ALLOWED_ORIGINS environment variable to a comma-separated list,
# e.g. "https://tejas-navy.vercel.app,http://localhost:3000".
# Falls back to localhost-only if the variable is absent.
# ---------------------------------------------------------------------------
_raw_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
_allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(wells.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")
app.include_router(dynacards.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(fleet.router, prefix="/api")


# ---------------------------------------------------------------------------
# Root / health endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"], summary="API root")
def root() -> dict:
    """Returns a brief description and links to docs."""
    return {
        "project": "Tejas — Decision-Support Digital Twin for Heavy-Oil Wells",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "data_note": "Synthetic demonstration data — not real Oil India field data.",
        "sih": "SIH 2025 · BMS College of Engineering, Bangalore · PS SIH26120",
    }


@app.get("/health", tags=["meta"], summary="Health check")
def health() -> dict:
    """Lightweight liveness probe — returns 200 when the server is up."""
    return {"status": "ok"}

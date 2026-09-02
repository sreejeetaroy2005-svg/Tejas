"""Tejas — Decision-Support Digital Twin for Heavy-Oil Well Operations.

This application provides API endpoints for monitoring and optimizing
Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP) operations
on heavy-oil wells.

All data is SYNTHETIC DEMONSTRATION DATA and does NOT represent real
Oil India field data.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import wells, simulate, optimize
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
        "All data is synthetic demonstration data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(wells.router, prefix="/api")
app.include_router(simulate.router, prefix="/api")
app.include_router(optimize.router, prefix="/api")

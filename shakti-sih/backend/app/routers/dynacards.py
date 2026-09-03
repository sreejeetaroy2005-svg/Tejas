"""Dynacards router — endpoints for dynamometer card classification.

All data is synthetic demonstration data, not real Oil India field data.
"""

from fastapi import APIRouter, HTTPException

from app.models import (
    ExampleCard,
    DynacardClassifyRequest,
    DynacardClassification,
)
from app.services.dynacard_service import classify_card, get_example_cards

router = APIRouter(tags=["dynacards"])


@router.get("/dynacards/examples", response_model=list[ExampleCard])
def list_example_cards() -> list[ExampleCard]:
    """Return one example dynacard per condition label.

    Used by the frontend to show reference card shapes for
    Normal, Rod Floating, Fluid Pound, and Gas Interference.

    All data is synthetic demonstration data.
    """
    examples = get_example_cards()
    return [ExampleCard(**ex) for ex in examples]


@router.post("/dynacards/classify", response_model=DynacardClassification)
def classify_dynacard(req: DynacardClassifyRequest) -> DynacardClassification:
    """Classify a dynamometer card into a condition category.

    Accepts a position/load curve (200-point arrays) plus operating
    parameters, engineers features, and returns the predicted condition
    with confidence, top contributing features, and a plain-language
    explanation.

    All data is synthetic demonstration data.
    """
    try:
        result = classify_card(
            position=req.position,
            load=req.load,
            spm=req.spm,
            stroke_length=req.stroke_length,
            temperature=req.temperature,
            viscosity=req.viscosity,
            fluid_level=req.fluid_level,
            pump_depth=req.pump_depth,
            production_rate=req.production_rate,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return DynacardClassification(**result)

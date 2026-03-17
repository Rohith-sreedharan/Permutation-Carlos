"""Internal Distribution Governance API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.distribution_governance_service import get_distribution_governance_service


router = APIRouter(tags=["distribution"])


class DistributionEvaluateRequest(BaseModel):
    decision_id: str
    trace_id: str


@router.post("/internal/distribution/evaluate")
async def evaluate_distribution(payload: DistributionEvaluateRequest):
    service = get_distribution_governance_service()

    try:
        result = service.evaluate(decision_id=payload.decision_id, trace_id=payload.trace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        if "decision lookup failed" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=500, detail=message) from exc

    response = {
        "distribution_id": result.distribution_id,
        "decision_id": result.decision_id,
        "distribution_category": result.distribution_category,
        "rule_applied": result.rule_applied,
        "withheld_reason": result.withheld_reason,
        "evaluated_at_utc": result.evaluated_at_utc,
    }

    if result.already_exists:
        raise HTTPException(status_code=409, detail=response)

    return response

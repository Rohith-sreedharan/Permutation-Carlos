"""Internal Integrity Sentinel API routes."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.integrity_sentinel import get_integrity_sentinel


router = APIRouter(tags=["integrity"])


class RunIntegrityCheckRequest(BaseModel):
    enforce_actions: bool = Field(default=True)


@router.post("/internal/integrity/check")
async def run_integrity_check(payload: RunIntegrityCheckRequest):
    sentinel = get_integrity_sentinel()
    return sentinel.run_check_cycle(enforce_actions=payload.enforce_actions)


@router.get("/internal/integrity/latest")
async def get_latest_integrity_status():
    sentinel = get_integrity_sentinel()
    return {"status": sentinel.get_latest_status()}
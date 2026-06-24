"""
Phase 4E – Replay Routes
GET /api/phase4/replay/{decision_id}
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from services.phase4_replay_harness import build_replay_bundle, build_replay_bundles_for_run

router = APIRouter(prefix="/api/phase4/replay", tags=["phase4-replay"])


@router.get("/{decision_id}", summary="Get deterministic replay bundle")
def get_replay_bundle(
    decision_id: str = Path(..., description="Phase-4 decision_id"),
    force_rebuild: bool = False,
):
    """
    Return a deterministic replay bundle for a given decision_id.

    The bundle includes:
    - inputs (odds snapshot, injury snapshot, weather snapshot)
    - decision_output (phase4_decision_class, probabilities, edge)
    - reason_codes (why this classification was assigned)
    - integrity_flags (data quality, calibration status)

    READ-ONLY: never mutates any truth table or decision record.
    """
    bundle = build_replay_bundle(decision_id, force_rebuild=force_rebuild)
    if not bundle:
        raise HTTPException(
            status_code=404,
            detail=f"Decision '{decision_id}' not found or replay unavailable",
        )
    return bundle


@router.get("/run/{run_id}", summary="Get replay bundles for an entire run")
def get_run_replay_bundles(
    run_id: str = Path(..., description="Simulation run_id"),
):
    """
    Return replay bundles for all decisions in a simulation run.
    Useful for CI gate E validation.
    """
    bundles = build_replay_bundles_for_run(run_id)
    return {"run_id": run_id, "count": len(bundles), "bundles": bundles}

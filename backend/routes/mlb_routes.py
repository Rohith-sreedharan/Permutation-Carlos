from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from backend.services.mlb_edge_evaluator import (
    MLBEdgeEvaluator,
    GameContext,
    SimulationOutput,
    EvaluationResponse,
    EdgeState,
    DistributionFlag,
    PitcherStatus,
    BullpenStatus,
    ParkFactor,
)
from db.mongo import db

router = APIRouter(prefix="/mlb", tags=["MLB Edge Evaluator"])


def get_service():
    return MLBEdgeEvaluator(db=db)


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_game(payload: dict, service: MLBEdgeEvaluator = Depends(get_service)):
    try:
        game_context = GameContext(**payload["game_context"])
        simulation = SimulationOutput(**payload["simulation"])
        return await service.evaluate_game(game_context.game_id, game_context, simulation)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/slate")
async def evaluate_slate(payload: dict, service: MLBEdgeEvaluator = Depends(get_service)):
    try:
        date = payload.get("date")
        if not date:
            raise HTTPException(status_code=400, detail="date is required")
        games = payload.get("games", [])
        return await service.evaluate_slate(date, games)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recent")
async def recent(limit: int = 20, state: Optional[str] = None, service: MLBEdgeEvaluator = Depends(get_service)):
    return await service.get_recent_evaluations(limit=limit, state_filter=state)


@router.get("/evaluation/{game_id}")
async def get_evaluation(game_id: str, service: MLBEdgeEvaluator = Depends(get_service)):
    evaluation = await service.get_evaluation(game_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.get("/health")
async def health(service: MLBEdgeEvaluator = Depends(get_service)):
    return await service.health_check()


@router.get("/metadata")
async def metadata():
    return {
        "service": "MLB Edge Evaluator",
        "compression_factor": 0.82,
        "markets": ["moneyline", "totals"],
        "defaults": {
            "favor": "NO_PLAY",
            "expected_edges": "1-2 per slate",
        },
    }

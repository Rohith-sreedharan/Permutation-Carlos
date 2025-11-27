"""
Parlay Builder Routes
API endpoints for parlay construction and analysis
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from db.mongo import client, db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parlay", tags=["parlay"])


class ParlayLeg(BaseModel):
    """Single leg of a parlay"""
    event_id: str
    bet_type: str  # moneyline, spread, total
    team: Optional[str] = None
    side: Optional[str] = None  # over/under for totals
    line: Optional[float] = None
    odds: int  # American odds


class ParlayBuildRequest(BaseModel):
    """Request to build/analyze parlay"""
    legs: List[ParlayLeg]


class ParlayBuildResponse(BaseModel):
    """Response with parlay analysis"""
    combined_probability: float
    correlation_score: float
    risk_score: str
    expected_value: float
    parlay_odds: float
    recommendation: str
    legs: List[Dict[str, Any]]
    suggested_bet_amount: Optional[float] = None
    max_bet_amount: Optional[float] = None


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    """Extract user ID from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    # Token format: "user:<id>"
    if not token.startswith("user:"):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    return token.replace("user:", "")


@router.post("/build", response_model=ParlayBuildResponse)
async def build_parlay(
    request: ParlayBuildRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Build and analyze parlay
    
    This endpoint:
    1. Publishes to parlay.requests topic
    2. Parlay Agent analyzes legs (EV, correlation)
    3. Risk Agent provides guidance
    4. AI Coach formats response
    5. Returns analysis synchronously (waits for agent response)
    
    In production, this could be async with WebSocket for real-time updates
    """
    try:
        user_id = _get_user_id_from_auth(authorization)
        
        # Convert legs to dict format
        legs_data = [
            {
                "event_id": leg.event_id,
                "bet_type": leg.bet_type,
                "team": leg.team,
                "side": leg.side,
                "line": leg.line,
                "odds": leg.odds
            }
            for leg in request.legs
        ]
        
        # Get orchestrator and request analysis
        from backend.core.agent_orchestrator import get_orchestrator
        from backend.db.mongo import client, db
        orchestrator = await get_orchestrator(client)
        
        # Publish to event bus
        await orchestrator.request_parlay_analysis(user_id, legs_data)
        
        # For now, return synchronous mock response
        # In production, would wait for agent response or use WebSocket
        
        # Quick calculation for immediate response
        from backend.core.agents.parlay_agent import ParlayAgent
        from backend.core.event_bus import get_event_bus
        
        bus = await get_event_bus()
        parlay_agent = ParlayAgent(bus)
        
        # Analyze legs
        analyzed_legs = []
        for leg_data in legs_data:
            leg_analysis = await parlay_agent._analyze_leg(leg_data)
            analyzed_legs.append(leg_analysis)
            
        # Calculate correlation
        correlation = await parlay_agent._calculate_correlation(analyzed_legs)
        
        # Calculate combined probability
        combined_prob = await parlay_agent._calculate_combined_probability(
            analyzed_legs,
            correlation
        )
        
        # Risk score
        risk_score = await parlay_agent._calculate_risk_score(analyzed_legs, correlation)
        
        # Parlay odds
        parlay_odds = parlay_agent._calculate_parlay_odds(legs_data)
        
        # Expected value
        ev = (combined_prob * parlay_odds) - (1 - combined_prob)
        
        # Recommendation
        recommendation = parlay_agent._get_recommendation(ev, risk_score)
        
        # Get bet sizing from risk agent
        from backend.core.agents.risk_agent import RiskAgent
        risk_agent = RiskAgent(bus, client)
        
        guidance = await risk_agent._generate_risk_guidance(user_id, {
            "combined_probability": combined_prob * 100,
            "parlay_odds": parlay_odds,
            "expected_value": ev * 100,
            "risk_score": risk_score
        })
        
        # Log parlay analysis
        db_instance = client["beatvegas_db"]
        parlay_log = {
            "user_id": user_id,
            "legs": analyzed_legs,
            "combined_probability": combined_prob,
            "correlation_score": correlation,
            "risk_score": risk_score,
            "expected_value": ev,
            "parlay_odds": parlay_odds,
            "recommendation": recommendation,
            "bet_amount": None,
            "outcome": None,
            "created_at": datetime.utcnow(),
            "settled_at": None
        }
        db_instance.parlay_logs.insert_one(parlay_log)
        
        return ParlayBuildResponse(
            combined_probability=round(combined_prob * 100, 2),
            correlation_score=round(correlation, 3),
            risk_score=risk_score,
            expected_value=round(ev * 100, 2),
            parlay_odds=round(parlay_odds, 2),
            recommendation=recommendation,
            legs=analyzed_legs,
            suggested_bet_amount=guidance.get("suggested_bet_amount"),
            max_bet_amount=guidance.get("max_recommended_amount")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parlay build error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_parlay_history(
    authorization: Optional[str] = Header(None),
    limit: int = 20
):
    """Get user's parlay history"""
    try:
        user_id = _get_user_id_from_auth(authorization)
        
        db = client["beatvegas_db"]
        
        parlays = list(
            db.parlay_logs
            .find({"user_id": user_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        
        # Convert ObjectId to string
        for parlay in parlays:
            parlay["_id"] = str(parlay["_id"])
            
        return {"parlays": parlays}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parlay history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_parlay_stats(
    authorization: Optional[str] = Header(None)
):
    """Get user's parlay statistics"""
    try:
        user_id = _get_user_id_from_auth(authorization)
        
        db = client["beatvegas_db"]
        
        # Get all settled parlays
        settled = list(db.parlay_logs.find({
            "user_id": user_id,
            "outcome": {"$ne": None}
        }))
        
        if not settled:
            return {
                "total_parlays": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0,
                "avg_odds": 0,
                "roi": 0
            }
            
        wins = sum(1 for p in settled if p.get("outcome") == "win")
        losses = sum(1 for p in settled if p.get("outcome") == "loss")
        
        # Calculate ROI if bet amounts recorded
        total_wagered = sum(p.get("bet_amount", 0) for p in settled if p.get("bet_amount"))
        total_won = sum(
            p.get("bet_amount", 0) * p.get("parlay_odds", 1)
            for p in settled
            if p.get("outcome") == "win" and p.get("bet_amount")
        )
        roi = ((total_won - total_wagered) / total_wagered * 100) if total_wagered > 0 else 0
        
        return {
            "total_parlays": len(settled),
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / len(settled)) * 100, 2),
            "avg_odds": round(sum(p.get("parlay_odds", 1) for p in settled) / len(settled), 2),
            "roi": round(roi, 2),
            "total_wagered": round(total_wagered, 2),
            "total_won": round(total_won, 2),
            "profit_loss": round(total_won - total_wagered, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Parlay stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

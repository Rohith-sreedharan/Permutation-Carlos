"""
Edge Analysis Routes
Exposes edge_analysis.py service via REST API
Compares user bets vs BeatVegas AI predictions
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from ..services.edge_analysis import generate_coaching_report, analyze_bet_vs_model
from ..db.mongo import db
from bson import ObjectId
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/edge-analysis", tags=["edge_analysis"])


async def get_current_user(token: str = Depends(lambda: None)) -> Dict[str, Any]:
    """Extract user from JWT token (placeholder - integrate with auth)"""
    # TODO: Replace with actual JWT validation
    # For now, return mock user - integrate with auth_routes.py get_current_user
    return {"_id": ObjectId(), "user_id": "user_123"}


@router.get("")
async def get_edge_analysis_summary(
    days: int = 7,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GET /api/edge-analysis
    Returns 7-day summary of user bets vs AI predictions
    
    Response:
    {
        "total_bets": 12,
        "total_conflicts": 5,
        "total_aligned": 7,
        "ev_lost": -62.50,
        "coaching_message": "🚨 EDGE ALERT: You've gone against the model 5 times..."
    }
    """
    try:
        user_id = current_user.get("user_id") or str(current_user["_id"])
        
        report = await generate_coaching_report(user_id, days=days)
        
        return report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate edge analysis: {str(e)}")


@router.get("/bet/{bet_id}")
async def get_bet_edge_analysis(
    bet_id: str,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GET /api/edge-analysis/bet/{bet_id}
    Returns detailed edge analysis for a specific bet
    
    Response:
    {
        "is_aligned": false,
        "ev_cost": -12.50,
        "message": "⚠️ You bet OVER, but our model predicted UNDER (75% confidence)...",
        "model_prediction": {
            "sport": "NBA",
            "event_id": "abc123",
            "prediction_type": "total",
            "predicted_value": 218.5,
            "confidence": 0.75,
            "ev": 2.50
        }
    }
    """
    try:
        user_id = current_user.get("user_id") or str(current_user["_id"])
        
        # Fetch bet
        bet = db.user_bets.find_one({
            "_id": ObjectId(bet_id),
            "user_id": user_id
        })
        
        if not bet:
            raise HTTPException(status_code=404, detail="Bet not found")
        
        # Analyze bet vs model
        analysis = await analyze_bet_vs_model(bet)
        
        return analysis
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze bet: {str(e)}")


@router.get("/recent-conflicts")
async def get_recent_conflicts(
    limit: int = 10,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GET /api/edge-analysis/recent-conflicts
    Returns recent bets where user went against model
    
    Response:
    {
        "conflicts": [
            {
                "bet_id": "...",
                "selection": "Lakers -5",
                "stake": 50.0,
                "ev_cost": -12.50,
                "message": "⚠️ Fighting the math...",
                "created_at": "2024-11-22T..."
            }
        ],
        "total_conflicts": 5,
        "total_ev_lost": -62.50
    }
    """
    try:
        user_id = current_user.get("user_id") or str(current_user["_id"])
        
        # Get recent bets
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        bets = list(db.user_bets.find({
            "user_id": user_id,
            "created_at": {"$gte": seven_days_ago}
        }).sort("created_at", -1).limit(50))
        
        conflicts = []
        total_ev_lost = 0.0
        
        for bet in bets:
            analysis = await analyze_bet_vs_model(bet)
            
            if not analysis["is_aligned"]:
                conflicts.append({
                    "bet_id": str(bet["_id"]),
                    "selection": bet["selection"],
                    "stake": bet["stake"],
                    "ev_cost": analysis["ev_cost"],
                    "message": analysis["message"],
                    "created_at": bet["created_at"].isoformat()
                })
                
                total_ev_lost += analysis["ev_cost"]
                
                if len(conflicts) >= limit:
                    break
        
        return {
            "conflicts": conflicts,
            "total_conflicts": len(conflicts),
            "total_ev_lost": round(total_ev_lost, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch conflicts: {str(e)}")


@router.get("/aligned-bets")
async def get_aligned_bets(
    limit: int = 10,
    current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GET /api/edge-analysis/aligned-bets
    Returns recent bets where user aligned with model
    
    Response:
    {
        "aligned_bets": [
            {
                "bet_id": "...",
                "selection": "Over 220.5",
                "stake": 50.0,
                "ev_boost": 3.75,
                "message": "✅ Aligned with model...",
                "created_at": "2024-11-22T..."
            }
        ],
        "total_aligned": 7,
        "total_ev_captured": 26.25
    }
    """
    try:
        user_id = current_user.get("user_id") or str(current_user["_id"])
        
        # Get recent bets
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        bets = list(db.user_bets.find({
            "user_id": user_id,
            "created_at": {"$gte": seven_days_ago}
        }).sort("created_at", -1).limit(50))
        
        aligned_bets = []
        total_ev_captured = 0.0
        
        for bet in bets:
            analysis = await analyze_bet_vs_model(bet)
            
            if analysis["is_aligned"]:
                aligned_bets.append({
                    "bet_id": str(bet["_id"]),
                    "selection": bet["selection"],
                    "stake": bet["stake"],
                    "ev_boost": analysis["ev_cost"],  # Positive for aligned bets
                    "message": analysis["message"],
                    "created_at": bet["created_at"].isoformat()
                })
                
                total_ev_captured += analysis["ev_cost"]
                
                if len(aligned_bets) >= limit:
                    break
        
        return {
            "aligned_bets": aligned_bets,
            "total_aligned": len(aligned_bets),
            "total_ev_captured": round(total_ev_captured, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch aligned bets: {str(e)}")

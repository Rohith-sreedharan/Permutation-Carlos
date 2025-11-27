from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from db.mongo import db

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/clv")
async def get_clv_data(
    user_id: str = Query(...),
    range: str = Query("30d", regex="^(7d|30d|90d|all)$")
):
    """Get CLV tracking data"""
    # Calculate date range
    now = datetime.now(timezone.utc)
    if range == "7d":
        start_date = now - timedelta(days=7)
    elif range == "30d":
        start_date = now - timedelta(days=30)
    elif range == "90d":
        start_date = now - timedelta(days=90)
    else:  # all
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    # Fetch AI picks with CLV data
    picks = list(db.ai_picks.find(
        {
            "user_id": user_id,
            "created_at": {"$gte": start_date.isoformat()}
        },
        {"_id": 0}
    ).sort("created_at", -1))
    
    if not picks:
        return {
            "picks": [],
            "stats": {
                "average_clv": 0.0,
                "total_picks": 0,
                "positive_clv_picks": 0,
                "clv_trend": "stable",
                "last_30_days_avg": 0.0
            }
        }
    
    # Calculate CLV statistics
    total_clv = sum(pick.get("clv", 0.0) for pick in picks)
    average_clv = total_clv / len(picks) if picks else 0.0
    positive_clv_picks = sum(1 for pick in picks if pick.get("clv", 0.0) > 0)
    
    # Calculate 30-day trend
    thirty_days_ago = now - timedelta(days=30)
    recent_picks = [p for p in picks if datetime.fromisoformat(p["created_at"]) >= thirty_days_ago]
    last_30_days_avg = sum(p.get("clv", 0.0) for p in recent_picks) / len(recent_picks) if recent_picks else 0.0
    
    # Determine trend
    if len(picks) > 10:
        first_half = picks[len(picks)//2:]
        second_half = picks[:len(picks)//2]
        first_half_avg = sum(p.get("clv", 0.0) for p in first_half) / len(first_half) if first_half else 0.0
        second_half_avg = sum(p.get("clv", 0.0) for p in second_half) / len(second_half) if second_half else 0.0
        
        if second_half_avg > first_half_avg * 1.1:
            clv_trend = "improving"
        elif second_half_avg < first_half_avg * 0.9:
            clv_trend = "declining"
        else:
            clv_trend = "stable"
    else:
        clv_trend = "stable"
    
    # Format picks for response
    formatted_picks = [
        {
            "event_id": pick.get("event_id"),
            "pick_date": pick.get("created_at"),
            "sport": pick.get("sport", "unknown"),
            "team": pick.get("team", "N/A"),
            "predicted_prob": pick.get("predicted_probability", 0.0),
            "market_prob": pick.get("market_probability", 0.0),
            "clv": pick.get("clv", 0.0),
            "outcome": pick.get("outcome", "pending")
        }
        for pick in picks
    ]
    
    return {
        "picks": formatted_picks,
        "stats": {
            "average_clv": average_clv,
            "total_picks": len(picks),
            "positive_clv_picks": positive_clv_picks,
            "clv_trend": clv_trend,
            "last_30_days_avg": last_30_days_avg
        }
    }


@router.get("/report")
async def get_performance_report(
    user_id: str = Query(...),
    range: str = Query("30d", regex="^(7d|30d|90d|season)$")
):
    """Get comprehensive performance metrics report"""
    # Find most recent performance report
    report = db.performance_reports.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )
    
    if report:
        report.pop("_id", None)
        return report
    
    # Generate basic report if none exists
    picks = list(db.ai_picks.find({"user_id": user_id}))
    
    if not picks:
        return {
            "brier_score": 0.0,
            "log_loss": 0.0,
            "roi": 0.0,
            "clv": 0.0,
            "total_picks": 0,
            "winning_picks": 0,
            "win_rate": 0.0,
            "avg_odds": 0.0,
            "profit_loss": 0.0,
            "market_breakdown": {}
        }
    
    # Calculate basic metrics
    total_picks = len([p for p in picks if p.get("outcome") in ["win", "loss"]])
    winning_picks = len([p for p in picks if p.get("outcome") == "win"])
    win_rate = (winning_picks / total_picks * 100) if total_picks > 0 else 0.0
    
    # Simple P&L calculation
    profit_loss = sum(
        100 * (p.get("odds", 2.0) - 1) if p.get("outcome") == "win" else -100
        for p in picks if p.get("outcome") in ["win", "loss"]
    )
    
    total_invested = total_picks * 100
    roi = (profit_loss / total_invested * 100) if total_invested > 0 else 0.0
    
    avg_clv = sum(p.get("clv", 0.0) for p in picks) / len(picks) if picks else 0.0
    avg_odds = sum(p.get("odds", 2.0) for p in picks) / len(picks) if picks else 0.0
    
    # Market breakdown
    market_breakdown = {}
    sports = set(p.get("sport") for p in picks if p.get("sport"))
    
    for sport in sports:
        sport_picks = [p for p in picks if p.get("sport") == sport and p.get("outcome") in ["win", "loss"]]
        if sport_picks:
            sport_wins = len([p for p in sport_picks if p.get("outcome") == "win"])
            sport_win_rate = (sport_wins / len(sport_picks) * 100) if sport_picks else 0.0
            
            sport_pl = sum(
                100 * (p.get("odds", 2.0) - 1) if p.get("outcome") == "win" else -100
                for p in sport_picks
            )
            sport_roi = (sport_pl / (len(sport_picks) * 100) * 100) if sport_picks else 0.0
            sport_clv = sum(p.get("clv", 0.0) for p in sport_picks) / len(sport_picks) if sport_picks else 0.0
            
            market_breakdown[sport] = {
                "picks": len(sport_picks),
                "win_rate": sport_win_rate,
                "roi": sport_roi,
                "clv": sport_clv
            }
    
    return {
        "brier_score": 0.20,  # Placeholder - needs actual calculation
        "log_loss": 0.60,  # Placeholder
        "roi": roi,
        "clv": avg_clv,
        "total_picks": total_picks,
        "winning_picks": winning_picks,
        "win_rate": win_rate,
        "avg_odds": avg_odds,
        "profit_loss": profit_loss,
        "market_breakdown": market_breakdown
    }

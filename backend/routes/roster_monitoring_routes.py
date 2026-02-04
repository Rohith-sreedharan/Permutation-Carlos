"""
Roster Availability Monitoring Endpoints
=========================================
Provides operational visibility into roster governance system.

KPIs exposed:
- Roster availability rate (last 24h)
- Currently blocked simulations count
- Blocked simulations by league
- Alert history

For institutional investors, ops teams, and monitoring dashboards.
"""

from fastapi import APIRouter, Query
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from core.roster_governance import roster_governance
from core.simulation_context import SimulationStatus
from db.mongo import db

router = APIRouter(prefix="/api/roster", tags=["roster-monitoring"])


@router.get("/metrics")
async def get_roster_metrics(league: Optional[str] = Query(None)):
    """
    Get roster availability metrics for monitoring.
    
    Returns KPIs:
    - Roster availability rate (percentage)
    - Total checks in last 24h
    - Currently blocked simulations
    - Breakdown by league (if requested)
    
    Query params:
        league: Optional league filter (NBA, NCAAB, NFL, etc.)
    
    Returns:
        Metrics dict with availability stats
    """
    metrics = roster_governance.get_roster_metrics(league=league)
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "status": "healthy" if metrics["last_24h"]["availability_rate"] >= 90 else "degraded"
    }


@router.get("/blocked-simulations")
async def get_blocked_simulations(
    league: Optional[str] = Query(None),
    limit: int = Query(50, le=500)
):
    """
    Get list of currently blocked simulations.
    
    Useful for ops to see which games are unavailable and why.
    
    Query params:
        league: Optional league filter
        limit: Max results (default 50, max 500)
    
    Returns:
        List of blocked simulations with event details
    """
    now = datetime.now(timezone.utc)
    
    query = {
        "status": SimulationStatus.BLOCKED,
        "retry_after": {"$gt": now}  # Still in cooldown
    }
    
    if league:
        query["league"] = league
    
    blocked_sims = list(
        roster_governance.blocked_simulations_collection
        .find(query)
        .sort("blocked_at", -1)
        .limit(limit)
    )
    
    # Enrich with event data
    enriched = []
    for sim in blocked_sims:
        event_id = sim.get("event_id")
        event = db.events.find_one({"event_id": event_id}) if event_id else None
        
        enriched.append({
            "event_id": event_id,
            "team_name": sim.get("team_name"),
            "league": sim.get("league"),
            "blocked_reason": sim.get("blocked_reason"),
            "blocked_at": sim.get("blocked_at").isoformat() if sim.get("blocked_at") else None,
            "retry_after": sim.get("retry_after").isoformat() if sim.get("retry_after") else None,
            "event_details": {
                "home_team": event.get("home_team") if event else None,
                "away_team": event.get("away_team") if event else None,
                "commence_time": event.get("commence_time") if event else None
            } if event else None
        })
    
    return {
        "total": len(enriched),
        "blocked_simulations": enriched,
        "query": {
            "league": league,
            "limit": limit
        }
    }


@router.get("/availability-history")
async def get_availability_history(
    team_name: str = Query(..., description="Team name to check history for"),
    league: str = Query(..., description="League (NBA, NCAAB, etc.)"),
    hours: int = Query(24, le=168, description="Hours to look back (max 7 days)")
):
    """
    Get roster availability check history for a specific team.
    
    Shows:
    - When roster was checked
    - Whether it was available
    - If simulation was blocked
    
    Query params:
        team_name: Team to check
        league: League identifier
        hours: Hours to look back (max 168 = 7 days)
    
    Returns:
        List of historical roster checks
    """
    lookback = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    checks = list(
        roster_governance.roster_checks_collection
        .find({
            "team_name": team_name,
            "league": league,
            "checked_at": {"$gte": lookback}
        })
        .sort("checked_at", -1)
    )
    
    # Format for response
    history = []
    for check in checks:
        history.append({
            "checked_at": check.get("checked_at").isoformat() if check.get("checked_at") else None,
            "roster_available": check.get("roster_available", False),
            "blocked": check.get("blocked", False),
            "ops_alerted": check.get("ops_alerted", False)
        })
    
    # Calculate availability rate for this team
    total_checks = len(checks)
    available_checks = sum(1 for c in checks if c.get("roster_available"))
    availability_rate = (available_checks / total_checks * 100) if total_checks > 0 else 100.0
    
    return {
        "team_name": team_name,
        "league": league,
        "hours_analyzed": hours,
        "total_checks": total_checks,
        "availability_rate": round(availability_rate, 2),
        "history": history
    }


@router.get("/health")
async def roster_system_health():
    """
    Health check for roster governance system.
    
    Returns:
        System health status with key metrics
    """
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    
    # Get metrics for all leagues
    all_metrics = roster_governance.get_roster_metrics()
    
    # Count currently blocked
    currently_blocked = roster_governance.blocked_simulations_collection.count_documents({
        "status": SimulationStatus.BLOCKED,
        "retry_after": {"$gt": now}
    })
    
    # Count recent checks
    recent_checks = roster_governance.roster_checks_collection.count_documents({
        "checked_at": {"$gte": last_24h}
    })
    
    # Determine health status
    availability_rate = all_metrics["last_24h"]["availability_rate"]
    if availability_rate >= 95:
        health_status = "healthy"
    elif availability_rate >= 85:
        health_status = "degraded"
    else:
        health_status = "critical"
    
    return {
        "status": health_status,
        "timestamp": now.isoformat(),
        "metrics": {
            "availability_rate_24h": availability_rate,
            "currently_blocked": currently_blocked,
            "checks_last_24h": recent_checks,
            "total_unavailable_24h": all_metrics["last_24h"]["unavailable"]
        },
        "system_version": "1.0.0",
        "governance_active": True
    }

"""
A/B Test Event Tracking Routes
Track user behavior across test variants
"""
from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel
from db.mongo import db


router = APIRouter(prefix="/api/ab-test", tags=["A/B Testing"])


class EventTrackRequest(BaseModel):
    """Request body for tracking A/B test events"""
    event: str  # view_landing, click_cta, start_trial, subscribe_paid, churn
    page_url: Optional[str] = None
    meta: Optional[dict] = None


@router.post("/track")
async def track_event(request: Request, body: EventTrackRequest):
    """
    Track A/B test event
    
    Events:
    - view_landing: User lands on homepage
    - click_cta: User clicks CTA button
    - start_trial: User starts trial
    - subscribe_paid: User converts to paid (triggered by Stripe webhook)
    - churn: User cancels subscription
    """
    # Get session data from middleware
    session_id = getattr(request.state, "session_id", None)
    variant = getattr(request.state, "variant", None)
    ref = getattr(request.state, "ref", None)
    
    if not session_id or not variant:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    # Build event document
    event_doc = {
        "event": body.event,
        "variant": variant,
        "session_id": session_id,
        "ref": ref,
        "ts": datetime.now(timezone.utc).isoformat(),
        "meta": body.meta or {}
    }
    
    # Add page_url to meta if provided
    if body.page_url:
        event_doc["meta"]["page_url"] = body.page_url
    
    # Add IP and User-Agent
    event_doc["meta"]["ip"] = request.client.host if request.client else None
    event_doc["meta"]["ua"] = request.headers.get("user-agent")
    
    # Insert into MongoDB
    result = db["ab_test_events"].insert_one(event_doc)
    
    return {
        "status": "ok",
        "event_id": str(result.inserted_id),
        "variant": variant,
        "session_id": session_id
    }


@router.get("/session")
async def get_session(request: Request):
    """
    Get current session info (variant assignment)
    Used by frontend to render appropriate variant
    """
    session_id = getattr(request.state, "session_id", None)
    variant = getattr(request.state, "variant", None)
    ref = getattr(request.state, "ref", None)
    
    if not session_id or not variant:
        raise HTTPException(status_code=400, detail="Session not initialized")
    
    return {
        "session_id": session_id,
        "variant": variant,
        "ref": ref
    }


@router.get("/analytics")
async def get_analytics(
    variant: Optional[Literal["A", "B", "C", "D", "E"]] = None,
    event: Optional[str] = None,
    limit: int = 100
):
    """
    Get A/B test analytics (admin only)
    Query event data for analysis
    """
    query = {}
    if variant:
        query["variant"] = variant
    if event:
        query["event"] = event
    
    events = list(
        db["ab_test_events"]
        .find(query)
        .sort("ts", -1)
        .limit(limit)
    )
    
    # Convert ObjectId to string
    for e in events:
        e["_id"] = str(e["_id"])
    
    # Calculate basic stats
    total_events = db["ab_test_events"].count_documents(query)
    
    # Funnel analysis by variant
    funnel_stats = {}
    for var in ["A", "B", "C", "D", "E"]:
        var_query = {"variant": var}
        
        views = db["ab_test_events"].count_documents({**var_query, "event": "view_landing"})
        clicks = db["ab_test_events"].count_documents({**var_query, "event": "click_cta"})
        trials = db["ab_test_events"].count_documents({**var_query, "event": "start_trial"})
        conversions = db["ab_test_events"].count_documents({**var_query, "event": "subscribe_paid"})
        
        funnel_stats[var] = {
            "views": views,
            "clicks": clicks,
            "trials": trials,
            "conversions": conversions,
            "click_rate": clicks / views if views > 0 else 0,
            "trial_rate": trials / clicks if clicks > 0 else 0,
            "conversion_rate": conversions / views if views > 0 else 0
        }
    
    return {
        "status": "ok",
        "total_events": total_events,
        "events": events,
        "funnel_stats": funnel_stats
    }

"""
Community Routes
Handle Discord-style community messages and picks
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel
import uuid
from db.mongo import db
from services.nlp_parser import nlp_parser
from services.reputation_engine import reputation_engine
from services.moderation_service import validate_content  # COMPLIANCE FILTER


router = APIRouter(prefix="/api/community", tags=["Community"])


class PostMessageRequest(BaseModel):
    """Post a message to community channel"""
    thread_type: str  # 'daily', 'parlay', 'game'
    game_id: Optional[str] = None  # Required for 'game' threads
    message: str
    user_id: Optional[str] = None  # Optional, will get from auth


class SettlePickRequest(BaseModel):
    """Settle a community pick (admin/automated)"""
    submission_id: str
    outcome: Literal["win", "loss", "push", "void"]


@router.post("/message")
async def post_message(request: Request, body: PostMessageRequest):
    """
    Post a message to community channel with COMPLIANCE moderation
    Automatically blocks prohibited betting language (Insights, Not Bets)
    """
    from core.websocket_manager import manager
    
    # 🔒 COMPLIANCE MODERATION: Enforce "Insights, Not Bets" rule
    is_compliant, error_msg, violations = validate_content(body.message)
    
    if not is_compliant:
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    
    # Get user from token (if not provided)
    user_id = body.user_id or "anonymous"
    
    # Create message document
    message_id = str(uuid.uuid4())
    
    # Get user reputation for ELO
    reputation = db["user_reputation"].find_one({"user_id": user_id})
    user_elo = reputation.get("elo_score") if reputation else 1500
    
    message_doc = {
        "id": message_id,
        "thread_type": body.thread_type,
        "game_id": body.game_id,
        "user_id": user_id,
        "message": body.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent")
        },
        "user_elo": user_elo,
        "moderated": True,
        "compliance_checked": True  # Mark as passing compliance
    }
    
    # Insert message
    db["community_messages"].insert_one(message_doc)
    
    # Broadcast to WebSocket subscribers
    await manager.broadcast_to_channel("community", {
        "type": "NEW_MESSAGE",
        "payload": {
            "id": message_id,
            "thread_type": body.thread_type,
            "game_id": body.game_id,
            "user_id": user_id,
            "message": body.message,
            "timestamp": message_doc["timestamp"],
            "user_elo": user_elo
        }
    })
    
    # Auto-parse for structured picks (future enhancement)
    parse_result = None
    # if user has premium plan:
    #     parse_result = nlp_parser.parse_message(...)
    
    return {
        "status": "ok",
        "message_id": message_id,
        "message": body.message,
        "timestamp": message_doc["timestamp"]
    }


@router.post("/messages")
async def post_message_simple(request: Request, body: dict):
    """
    Simplified message posting endpoint
    Accepts: { "message": str, "channel": str }
    """
    from core.websocket_manager import manager
    
    message = body.get("message", "").strip()
    channel = body.get("channel", "general")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # SERVER-SIDE MODERATION
    prohibited_terms = ['lock', 'guaranteed', '100%', 'cant lose', 'easy money', 'sure thing']
    message_lower = message.lower()
    
    for term in prohibited_terms:
        if term in message_lower:
            raise HTTPException(
                status_code=400,
                detail=f"Message contains prohibited language: '{term}'. Please rephrase."
            )
    
    # Extract user from auth header (simplified)
    auth_header = request.headers.get("authorization", "")
    user_id = "anonymous"
    if auth_header.startswith("Bearer user:"):
        user_id = auth_header.split(":", 2)[1]
    
    message_id = str(uuid.uuid4())
    message_doc = {
        "id": message_id,
        "channel": channel,
        "user_id": user_id,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc)
    }
    
    db["community_messages"].insert_one(message_doc)
    
    # Broadcast via WebSocket
    try:
        await manager.broadcast_to_channel("community", {
            "type": "NEW_MESSAGE",
            "payload": message_doc
        })
    except Exception:
        pass  # WebSocket manager may not be initialized
    
    return {"status": "ok", "message_id": message_id}


@router.get("/messages")
async def get_messages(
    thread_type: Optional[str] = None,
    game_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50
):
    """
    Get community messages by thread
    
    Args:
        thread_type: 'daily', 'parlay', or 'game'
        game_id: For game threads
        user_id: Filter by user
        limit: Max messages
    """
    query = {}
    if thread_type:
        query["thread_type"] = thread_type
    if game_id:
        query["game_id"] = game_id
    if user_id:
        query["user_id"] = user_id
    
    messages = list(
        db["community_messages"]
        .find(query)
        .sort("timestamp", -1)
        .limit(limit)
    )
    
    # Convert ObjectId and format
    formatted = []
    for msg in messages:
        formatted.append({
            "id": msg["id"],
            "user_id": msg["user_id"],
            "message": msg["message"],
            "timestamp": msg["timestamp"],
            "thread_type": msg.get("thread_type"),
            "game_id": msg.get("game_id"),
            "user_elo": msg.get("user_elo", 1500)
        })
    
    return {
        "status": "ok",
        "count": len(formatted),
        "messages": formatted
    }


@router.get("/picks")
async def get_community_picks(
    user_id: Optional[str] = None,
    event_id: Optional[str] = None,
    limit: int = 50
):
    """
    Get structured community picks
    """
    query = {}
    if user_id:
        query["user_id"] = user_id
    if event_id:
        query["event_id"] = event_id
    
    picks = list(
        db["community_picks"]
        .find(query)
        .sort("submitted_at", -1)
        .limit(limit)
    )
    
    # Convert ObjectId and enrich with user reputation
    for pick in picks:
        pick["_id"] = str(pick["_id"])
        
        # Add user ELO
        reputation = db["user_reputation"].find_one({"user_id": pick["user_id"]})
        if reputation:
            pick["user_elo"] = reputation["elo_score"]
            pick["user_weight"] = reputation["weight_multiplier"]
    
    return {
        "status": "ok",
        "count": len(picks),
        "picks": picks
    }


@router.post("/settle-pick")
async def settle_pick(body: SettlePickRequest):
    """
    Settle a community pick and update user ELO
    Called by automated settlement system or admin
    """
    # Get pick
    pick = db["community_picks"].find_one({"submission_id": body.submission_id})
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    
    # Update pick outcome
    db["community_picks"].update_one(
        {"submission_id": body.submission_id},
        {
            "$set": {
                "outcome": body.outcome,
                "settled_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # Update user ELO (skip for push/void)
    elo_result = None
    if body.outcome in ["win", "loss"]:
        elo_result = reputation_engine.update_elo(
            user_id=pick["user_id"],
            outcome=body.outcome
        )
    
    return {
        "status": "ok",
        "submission_id": body.submission_id,
        "outcome": body.outcome,
        "elo_updated": elo_result is not None,
        "elo_result": elo_result
    }


@router.get("/consensus/{event_id}")
async def get_sharp_consensus(event_id: str):
    """
    Get weighted community consensus for an event
    Returns the sharp_weighted_consensus feature for AI model
    """
    consensus = reputation_engine.calculate_sharp_weighted_consensus(event_id)
    
    # Get pick breakdown
    picks = list(db["community_picks"].find({"event_id": event_id}))
    
    # Count by sentiment
    bullish = sum(1 for p in picks if db["community_messages"].find_one({"id": p["message_id"]}, {"parsed_sentiment": {"$gt": 0}}))
    bearish = sum(1 for p in picks if db["community_messages"].find_one({"id": p["message_id"]}, {"parsed_sentiment": {"$lt": 0}}))
    
    return {
        "status": "ok",
        "event_id": event_id,
        "sharp_weighted_consensus": consensus,
        "total_picks": len(picks),
        "bullish_count": bullish,
        "bearish_count": bearish
    }


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 100):
    """
    Get community leaderboard by ELO
    """
    leaderboard = reputation_engine.get_leaderboard(limit=limit)
    
    return {
        "status": "ok",
        "leaderboard": leaderboard
    }


@router.get("/reputation/{user_id}")
async def get_user_reputation(user_id: str):
    """
    Get user reputation stats
    """
    reputation = db["user_reputation"].find_one({"user_id": user_id})
    if not reputation:
        raise HTTPException(status_code=404, detail="User reputation not found")
    
    reputation["_id"] = str(reputation["_id"])
    
    return {
        "status": "ok",
        "reputation": reputation
    }

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


router = APIRouter(prefix="/api/community", tags=["Community"])


class PostMessageRequest(BaseModel):
    """Post a message to community channel"""
    channel_id: str
    text: str
    user_id: str
    user_plan: Literal["free", "pro", "elite"]


class SettlePickRequest(BaseModel):
    """Settle a community pick (admin/automated)"""
    submission_id: str
    outcome: Literal["win", "loss", "push", "void"]


@router.post("/message")
async def post_message(request: Request, body: PostMessageRequest):
    """
    Post a message to community channel
    Automatically triggers NLP parsing for Pro/Elite users
    """
    # Create message document
    message_id = str(uuid.uuid4())
    
    # Get user reputation for ELO
    reputation = db["user_reputation"].find_one({"user_id": body.user_id})
    user_elo = reputation.get("elo_score") if reputation else None
    
    message_doc = {
        "id": message_id,
        "channel_id": body.channel_id,
        "user_id": body.user_id,
        "text": body.text,
        "ts": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "ip": request.client.host if request.client else None,
            "ua": request.headers.get("user-agent")
        },
        "user_plan": body.user_plan,
        "user_elo": user_elo
    }
    
    # Insert message
    db["community_messages"].insert_one(message_doc)
    
    # Auto-parse for Pro/Elite users
    parse_result = None
    if body.user_plan in ["pro", "elite"]:
        parse_result = nlp_parser.parse_message(
            message_id=message_id,
            text=body.text,
            user_plan=body.user_plan,
            user_elo=user_elo
        )
    
    return {
        "status": "ok",
        "message_id": message_id,
        "parsed": parse_result is not None,
        "parse_result": parse_result
    }


@router.get("/messages")
async def get_messages(
    channel_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 50
):
    """
    Get community messages
    """
    query = {}
    if channel_id:
        query["channel_id"] = channel_id
    if user_id:
        query["user_id"] = user_id
    
    messages = list(
        db["community_messages"]
        .find(query)
        .sort("ts", -1)
        .limit(limit)
    )
    
    # Convert ObjectId
    for msg in messages:
        msg["_id"] = str(msg["_id"])
    
    return {
        "status": "ok",
        "count": len(messages),
        "messages": messages
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

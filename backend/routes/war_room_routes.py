"""
War Room Routes
Endpoints for game rooms, market threads, posts, moderation
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid
from db.mongo import db
from services.war_room_service import WarRoomService, RankEngine, LeaderboardEngine
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/war-room", tags=["War Room"])


# ============================================================================
# REQUEST MODELS
# ============================================================================

class CreateGameRoomRequest(BaseModel):
    """Auto-created daily, but exposed for manual trigger"""
    sport: str
    game_id: str
    home_team: str
    away_team: str
    commence_time: str


class MarketCalloutRequest(BaseModel):
    """Market callout post submission"""
    thread_id: str
    game_matchup: str
    market_type: str  # spread, total, moneyline, prop
    line: str
    confidence: str  # low, med, high
    reason: str
    played_this: bool = False
    receipt_url: Optional[str] = None
    signal_id: Optional[str] = None


class ReceiptRequest(BaseModel):
    """Receipt submission"""
    thread_id: str
    screenshot_url: str
    market: str
    line: str
    result: str  # W, L, P


class ParlayBuildRequest(BaseModel):
    """Parlay build submission"""
    thread_id: str
    leg_count: int
    legs: List[Dict[str, Any]]
    risk_profile: str  # balanced, high_vol
    reasoning: str


class QuestionRequest(BaseModel):
    """Question submission (Beginner/General)"""
    channel_id: str
    question_text: str
    tags: List[str] = []


class ModerationRequest(BaseModel):
    """Moderation action"""
    action: str  # delete, lock, mute, flag, warn
    target_id: str
    reason: Optional[str] = None
    duration_hours: Optional[int] = None


# ============================================================================
# GAME ROOMS
# ============================================================================

@router.post("/game-rooms/create")
async def create_game_room(request: CreateGameRoomRequest, current_user=Depends(get_current_user)):
    """Create a game room (admin only)"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    
    room_id = f"{request.sport}_{request.game_id}_{datetime.now().strftime('%Y%m%d')}"
    
    game_room = {
        "room_id": room_id,
        "sport": request.sport,
        "game_id": request.game_id,
        "home_team": request.home_team,
        "away_team": request.away_team,
        "commence_time": request.commence_time,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl_hours": 6
    }
    
    result = db["war_room_game_rooms"].insert_one(game_room)
    
    # Auto-create market threads
    market_types = ["spread", "total", "moneyline", "props"]
    for market_type in market_types:
        thread = {
            "thread_id": f"{room_id}_{market_type}",
            "room_id": room_id,
            "market_type": market_type,
            "market_key": f"{request.game_id}_{market_type}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "post_count": 0,
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "is_locked": False
        }
        db["war_room_market_threads"].insert_one(thread)
    
    return {"room_id": room_id, "status": "created"}


@router.get("/game-rooms")
async def list_game_rooms(status: str = "scheduled", limit: int = 20):
    """List game rooms by status"""
    rooms = list(db["war_room_game_rooms"].find(
        {"status": status},
        {"_id": 0}
    ).sort("commence_time", -1).limit(limit))
    
    return {"rooms": rooms, "count": len(rooms)}


@router.get("/game-rooms/{room_id}")
async def get_game_room(room_id: str):
    """Get game room details with threads"""
    room = db["war_room_game_rooms"].find_one({"room_id": room_id}, {"_id": 0})
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    threads = list(db["war_room_market_threads"].find(
        {"room_id": room_id},
        {"_id": 0}
    ))
    
    return {
        "room": room,
        "threads": threads
    }


# ============================================================================
# MARKET THREADS & POSTS
# ============================================================================

@router.post("/posts/market-callout")
async def post_market_callout(
    request: MarketCalloutRequest,
    current_user=Depends(get_current_user)
):
    """Post a market callout with validation"""
    user_id = current_user["user_id"]
    user_tier = current_user.get("subscription_tier", "free")
    username = current_user["username"]
    
    # Check rate limits
    allowed, reason = await WarRoomService.check_rate_limit(
        user_id, user_tier, "live_sports", "market_callout"
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    # Check duplicate within 30 minutes
    allowed, reason = await WarRoomService.check_duplicate_market_callout(
        user_id, request.market_type, 30
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    # Validate template compliance
    from db.schemas.war_room_schemas import MarketCalloutPost
    from typing import cast, Literal
    
    callout_data = MarketCalloutPost(
        post_id=str(uuid.uuid4()),
        thread_id=request.thread_id,
        user_id=user_id,
        username=username,
        game_matchup=request.game_matchup,
        market_type=cast(Literal["spread", "total", "moneyline", "prop"], request.market_type),
        line=request.line,
        confidence=cast(Literal["low", "med", "high"], request.confidence),
        reason=request.reason,
        played_this=request.played_this,
        receipt_url=request.receipt_url,
        signal_id=request.signal_id
    )
    
    is_valid, error_msg = WarRoomService.validate_market_callout(callout_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Get model context if signal_id provided
    model_context = None
    if request.signal_id:
        model_context = db["simulations"].find_one(
            {"simulation_id": request.signal_id},
            {"_id": 0, "prediction": 1, "volatility_index": 1}
        )
    
    # Create post document
    post = {
        "post_id": str(uuid.uuid4()),
        "thread_id": request.thread_id,
        "user_id": user_id,
        "username": username,
        "post_type": "market_callout",
        "game_matchup": request.game_matchup,
        "market_type": request.market_type,
        "line": request.line,
        "confidence": request.confidence,
        "reason": request.reason,
        "played_this": request.played_this,
        "receipt_url": request.receipt_url,
        "signal_id": request.signal_id,
        "model_context": model_context,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_deleted": False,
        "flag_count": 0,
        "views": 0,
        "replies": 0,
        "moderation_status": "approved",
        "user_rank": current_user.get("rank", "rookie")
    }
    
    result = db["war_room_posts"].insert_one(post)
    
    # Update thread post count
    db["war_room_market_threads"].update_one(
        {"thread_id": request.thread_id},
        {
            "$inc": {"post_count": 1},
            "$set": {"last_activity": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Record rate limit
    await WarRoomService.record_post(user_id, user_tier, "market_callout")
    
    # Update user rank
    await RankEngine.update_user_rank(user_id)
    
    return {
        "post_id": post["post_id"],
        "status": "posted",
        "model_context_attached": model_context is not None
    }


@router.post("/posts/receipt")
async def post_receipt(request: ReceiptRequest, current_user=Depends(get_current_user)):
    """Post a winning/losing receipt"""
    user_id = current_user["user_id"]
    
    # Check rate limits
    allowed, reason = await WarRoomService.check_rate_limit(user_id, current_user.get("tier", "free"), "showcase")
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    post = {
        "post_id": str(uuid.uuid4()),
        "thread_id": request.thread_id,
        "user_id": user_id,
        "username": current_user["username"],
        "post_type": "receipt",
        "screenshot_url": request.screenshot_url,
        "market": request.market,
        "line": request.line,
        "result": request.result,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "verified": False,
        "is_deleted": False,
        "views": 0,
        "replies": 0,
        "user_rank": current_user.get("rank", "rookie")
    }
    
    db["war_room_posts"].insert_one(post)
    
    # Update thread
    db["war_room_market_threads"].update_one(
        {"thread_id": request.thread_id},
        {"$inc": {"post_count": 1}}
    )
    
    # Update user rank (graded pick)
    await RankEngine.update_user_rank(user_id)
    
    return {"post_id": post["post_id"], "status": "posted"}


@router.post("/posts/parlay-build")
async def post_parlay_build(request: ParlayBuildRequest, current_user=Depends(get_current_user)):
    """Post a parlay build"""
    user_id = current_user["user_id"]
    user_tier = current_user.get("subscription_tier", "free")
    
    # Check rate limits
    allowed, reason = await WarRoomService.check_rate_limit(user_id, user_tier, "parlay_factory")
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)
    
    post = {
        "post_id": str(uuid.uuid4()),
        "thread_id": request.thread_id,
        "user_id": user_id,
        "username": current_user["username"],
        "post_type": "parlay_build",
        "leg_count": request.leg_count,
        "legs": request.legs,
        "risk_profile": request.risk_profile,
        "reasoning": request.reasoning,
        "volatility_badges": ["high_vol"] if request.risk_profile == "high_vol" else [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_deleted": False,
        "views": 0,
        "replies": 0,
        "user_rank": current_user.get("rank", "rookie")
    }
    
    db["war_room_posts"].insert_one(post)
    
    # Update thread
    db["war_room_market_threads"].update_one(
        {"thread_id": request.thread_id},
        {"$inc": {"post_count": 1}}
    )
    
    await WarRoomService.record_post(user_id, user_tier, "parlay_build")
    
    return {"post_id": post["post_id"], "status": "posted"}


@router.get("/threads/{thread_id}/posts")
async def get_thread_posts(thread_id: str, limit: int = 50, skip: int = 0):
    """Get posts in a market thread"""
    posts = list(db["war_room_posts"].find(
        {"thread_id": thread_id, "is_deleted": False},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit))
    
    return {
        "posts": posts,
        "count": len(posts)
    }


# ============================================================================
# MODERATION
# ============================================================================

@router.post("/moderation/action")
async def moderate_post(request: ModerationRequest, current_user=Depends(get_current_user)):
    """Moderation action (mods only)"""
    if not current_user.get("is_mod"):
        raise HTTPException(status_code=403, detail="Mod only")
    
    result = await WarRoomService.moderate_post(
        request.target_id,
        request.action,
        current_user["user_id"],
        request.reason,
        request.duration_hours
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ============================================================================
# LEADERBOARD & RANKS
# ============================================================================

@router.get("/leaderboard")
async def get_leaderboard(limit: int = 50):
    """Get risk-adjusted leaderboard"""
    entries = await WarRoomService.get_leaderboard(limit)
    
    return {
        "leaderboard": entries,
        "count": len(entries)
    }


@router.get("/users/{user_id}/rank")
async def get_user_rank(user_id: str):
    """Get user rank and stats"""
    rank_data = db["war_room_user_ranks"].find_one({"user_id": user_id}, {"_id": 0})
    
    if not rank_data:
        return {"rank": "rookie", "rank_points": 0, "total_posts": 0}
    
    return rank_data


# ============================================================================
# ENGAGEMENT TRACKING
# ============================================================================

@router.post("/engagement/view")
async def track_view(post_id: str, current_user=Depends(get_current_user)):
    """Track post view"""
    db["war_room_posts"].update_one(
        {"post_id": post_id},
        {"$inc": {"views": 1}}
    )
    
    # Log engagement event
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "view",
        "user_id": current_user["user_id"],
        "target_type": "post",
        "target_id": post_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    db["war_room_engagement_events"].insert_one(event)
    
    return {"status": "tracked"}


@router.post("/engagement/reply")
async def track_reply(post_id: str, current_user=Depends(get_current_user)):
    """Track post reply"""
    db["war_room_posts"].update_one(
        {"post_id": post_id},
        {"$inc": {"replies": 1}}
    )
    
    return {"status": "tracked"}


# ============================================================================
# AUTO-MAINTENANCE
# ============================================================================

@router.post("/maintenance/archive-game")
async def archive_game_room(room_id: str, current_user=Depends(get_current_user)):
    """Manually trigger archiving (admin only)"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    
    await WarRoomService.auto_archive_threads(room_id)
    
    return {"status": "archived"}


@router.post("/maintenance/refresh-leaderboard")
async def refresh_leaderboard(current_user=Depends(get_current_user)):
    """Refresh leaderboard calculations (admin only)"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    
    await LeaderboardEngine.refresh_leaderboard()
    
    return {"status": "refreshed"}

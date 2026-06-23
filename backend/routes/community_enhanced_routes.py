"""
Community Bot & Identity API Routes
Manages automated content generation, user ranks, badges, and engagement
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.community_bot import community_bot
from services.user_identity import user_identity_service, BadgeType
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/community", tags=["community"])

INTERNAL_EMAIL_BLOCKLIST = {
    "beatvegasapp@gmail.com",
}
INTERNAL_PREFIX_BLOCKLIST = (
    "phase9_",
    "p11_",
    "ev_",
    "audit_",
)
INTERNAL_NAME_BLOCKLIST = {
    "probe",
}
INTERNAL_STATUS_BLOCKLIST = {
    "deleted",
    "test",
    "internal",
}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_internal_identity(doc: Dict[str, Any]) -> bool:
    email = _norm(doc.get("email"))
    username = _norm(doc.get("username"))
    user_id = _norm(doc.get("user_id"))
    name = _norm(doc.get("name") or doc.get("display_name"))
    status = _norm(doc.get("status") or doc.get("account_status") or doc.get("user_status"))

    identifiers = [email, username, user_id, name]

    if email in INTERNAL_EMAIL_BLOCKLIST:
        return True
    if status in INTERNAL_STATUS_BLOCKLIST:
        return True
    if any(value in INTERNAL_NAME_BLOCKLIST for value in identifiers if value):
        return True
    if any(value.startswith(INTERNAL_PREFIX_BLOCKLIST) for value in identifiers if value):
        return True

    return False


# === Request/Response Models ===

class PostMessageRequest(BaseModel):
    channel: str
    content: str

class InjuryAlertRequest(BaseModel):
    player: str
    team: str
    status: str
    sport: str = "NBA"


class LineMovementRequest(BaseModel):
    game: str
    market: str
    old_line: float
    new_line: float
    movement_pct: float


class MonteCarloAlertRequest(BaseModel):
    game: str
    edge_type: str
    pick: str
    line: str
    win_prob: float
    ev: float
    channel: str = "general"


class VolatilityAlertRequest(BaseModel):
    game: str
    market: str
    old_value: float
    new_value: float
    time_window: str


# === Bot Content Generation Routes ===

@router.post("/bot/game-threads")
async def generate_game_threads(user: Dict[str, Any] = Depends(get_current_user)):
    """Generate daily game threads for all sports (Admin only)"""
    # TODO: Add admin check
    threads = community_bot.generate_daily_game_threads()
    count = community_bot.post_messages(threads)
    return {"success": True, "threads_posted": count}


@router.post("/bot/daily-prompt")
async def generate_daily_prompt(user: Dict[str, Any] = Depends(get_current_user)):
    """Generate daily engagement prompt (Admin only)"""
    prompt = community_bot.generate_daily_prompt()
    success = community_bot.post_message(prompt)
    return {"success": success, "content": prompt["content"]}


@router.post("/bot/injury-alert")
async def post_injury_alert(
    alert: InjuryAlertRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Post injury alert (Admin only)"""
    message = community_bot.generate_injury_alert(
        player=alert.player,
        team=alert.team,
        status=alert.status,
        sport=alert.sport
    )
    success = community_bot.post_message(message)
    return {"success": success, "message_id": message["message_id"]}


@router.post("/bot/line-movement")
async def post_line_movement(
    movement: LineMovementRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Post line movement alert (Admin only)"""
    message = community_bot.generate_line_movement_alert(
        game=movement.game,
        market=movement.market,
        old_line=movement.old_line,
        new_line=movement.new_line,
        movement_pct=movement.movement_pct
    )
    success = community_bot.post_message(message)
    return {"success": success, "message_id": message["message_id"]}


@router.post("/bot/monte-carlo-alert")
async def post_monte_carlo_alert(
    alert: MonteCarloAlertRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Post Monte Carlo simulation alert"""
    message = community_bot.generate_monte_carlo_alert(
        game=alert.game,
        edge_type=alert.edge_type,
        pick=alert.pick,
        line=alert.line,
        win_prob=alert.win_prob,
        ev=alert.ev,
        channel=alert.channel
    )
    success = community_bot.post_message(message)
    return {"success": success, "message_id": message["message_id"]}


@router.post("/bot/volatility-alert")
async def post_volatility_alert(
    alert: VolatilityAlertRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Post volatility alert"""
    message = community_bot.generate_volatility_alert(
        game=alert.game,
        market=alert.market,
        old_value=alert.old_value,
        new_value=alert.new_value,
        time_window=alert.time_window
    )
    success = community_bot.post_message(message)
    return {"success": success, "message_id": message["message_id"]}


# === User Identity Routes ===

@router.get("/identity/me")
async def get_my_identity(user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's identity profile"""
    user_id = str(user.get("sub") or user.get("email") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    profile = user_identity_service.get_user_identity(user_id)
    return profile


@router.get("/identity/{target_user_id}")
async def get_user_identity(target_user_id: str):
    """Get any user's identity profile (public)"""
    profile = user_identity_service.get_user_identity(target_user_id)
    return profile


@router.post("/identity/login")
async def record_daily_login(user: Dict[str, Any] = Depends(get_current_user)):
    """Record daily login and update streak"""
    user_id = str(user.get("sub") or user.get("email") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    result = user_identity_service.update_daily_login(user_id)
    return result


@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = "xp",
    limit: int = 100
):
    """
    Get leaderboard sorted by metric
    Metrics: xp, win_rate, profit, streak
    """
    profiles = user_identity_service.get_leaderboard(limit=max(limit * 5, 100), metric=metric)
    profiles = [profile for profile in profiles if not _is_internal_identity(profile)][:limit]
    return {"metric": metric, "count": len(profiles), "leaderboard": profiles}


@router.get("/badges")
async def list_all_badges():
    """List all available badges and their requirements"""
    badges = []
    for badge_type in BadgeType:
        info = user_identity_service.get_badge_info(badge_type)
        info["badge_id"] = badge_type.value
        badges.append(info)
    return {"badges": badges}


@router.get("/channels")
async def list_channels():
    """List all available community channels"""
    channels = [
        {
            "id": "general",
            "name": "General Discussion",
            "emoji": "💬",
            "description": "Main community discussion"
        },
        {
            "id": "nba-live",
            "name": "NBA Live",
            "emoji": "🏀",
            "description": "NBA game threads and picks"
        },
        {
            "id": "nfl-live",
            "name": "NFL Live",
            "emoji": "🏈",
            "description": "NFL game threads and picks"
        },
        {
            "id": "ncaab-live",
            "name": "NCAAB Live",
            "emoji": "🎓",
            "description": "College basketball discussion"
        },
        {
            "id": "ncaaf-live",
            "name": "NCAAF Live",
            "emoji": "🏟️",
            "description": "College football discussion"
        },
        {
            "id": "nhl-live",
            "name": "NHL Live",
            "emoji": "🏒",
            "description": "NHL game threads and picks"
        },
        {
            "id": "mlb-live",
            "name": "MLB Live",
            "emoji": "⚾",
            "description": "MLB game threads and picks"
        },
        {
            "id": "winning-tickets",
            "name": "Winning Tickets",
            "emoji": "🎟️",
            "description": "Celebrate your wins!"
        },
        {
            "id": "props-only",
            "name": "Props Only",
            "emoji": "🎯",
            "description": "Player props discussion"
        },
        {
            "id": "parlay-factory",
            "name": "Parlay Factory",
            "emoji": "🎰",
            "description": "Build and share parlays"
        },
        {
            "id": "beginner-questions",
            "name": "Beginner Questions",
            "emoji": "❓",
            "description": "Ask anything - we're here to help"
        },
        {
            "id": "community-challenges",
            "name": "Community Challenges",
            "emoji": "🏆",
            "description": "Weekly challenges and competitions"
        }
    ]
    return {"channels": channels}


@router.get("/messages")
async def get_channel_messages(
    channel: str = "general",
    limit: int = 50
):
    """Get recent messages from a channel"""
    from db.mongo import db
    
    messages = list(
        db["community_messages"]
        .find({"channel_id": channel})
        .sort("ts", -1)
        .limit(limit)
    )
    
    filtered_messages = []

    # Convert ObjectId to string and hide internal/test accounts from public community feed
    for msg in messages:
        if "_id" in msg:
            msg["_id"] = str(msg["_id"])
        if _is_internal_identity(msg):
            continue
        filtered_messages.append(msg)
    
    return {"channel": channel, "count": len(filtered_messages), "messages": list(reversed(filtered_messages))}


@router.post("/messages")
async def post_user_message(
    request: PostMessageRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Post a user message to a channel"""
    from db.mongo import db
    from utils.timezone import now_utc
    import random
    
    user_id = str(user.get("sub") or user.get("email") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # Get user profile for username
    profile = user_identity_service.get_user_identity(user_id)
    
    # Award XP for posting
    user_identity_service.award_xp(user_id, "message_posted")
    
    message = {
        "message_id": f"user_{now_utc().timestamp()}_{random.randint(1000, 9999)}",
        "channel_id": request.channel,
        "user_id": user_id,
        "username": profile.get("username", user_id),  # TODO: Get from subscribers table
        "content": request.content,
        "ts": now_utc().isoformat(),
        "message_type": "user_message",
        "is_bot": False,
        "reactions": [],
        "reply_count": 0,
        "user_rank": profile.get("rank", "bronze"),
        "user_badges": profile.get("badges", [])
    }
    
    db["community_messages"].insert_one(message)
    
    return {"success": True, "message_id": message["message_id"]}

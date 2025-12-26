"""
War Room Database Schemas
Community intelligence workspace with structured threading
"""
from datetime import datetime, timezone
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field


class GameRoom(BaseModel):
    """Game Room - Auto-created daily for each scheduled game"""
    room_id: str = Field(..., description="Unique room identifier (game_id)")
    sport: str = Field(..., description="Sport key (NBA, NFL, MLB, NHL)")
    game_id: str = Field(..., description="External game identifier")
    home_team: str
    away_team: str
    commence_time: datetime
    status: Literal["scheduled", "live", "completed", "archived"] = "scheduled"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: Optional[datetime] = None
    ttl_hours: int = Field(default=6, description="Hours after game end before archive")
    
    class Config:
        json_schema_extra = {
            "example": {
                "room_id": "nba_lal_gsw_20251223",
                "sport": "basketball_nba",
                "game_id": "abc123",
                "home_team": "Los Angeles Lakers",
                "away_team": "Golden State Warriors",
                "commence_time": "2025-12-23T19:00:00Z",
                "status": "scheduled"
            }
        }


class MarketThread(BaseModel):
    """Market Thread - Organized discussion within a game room"""
    thread_id: str
    room_id: str = Field(..., description="Parent game room")
    market_type: Literal["spread", "total", "moneyline", "props"] = Field(..., description="Market category")
    market_key: str = Field(..., description="Specific market identifier")
    line: Optional[float] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    post_count: int = Field(default=0)
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_locked: bool = Field(default=False, description="Mods can lock threads")
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "nba_lal_gsw_spread",
                "room_id": "nba_lal_gsw_20251223",
                "market_type": "spread",
                "market_key": "lakers_spread",
                "line": -5.5,
                "post_count": 12
            }
        }


class PostTemplate(BaseModel):
    """Base class for structured post templates"""
    post_id: str
    thread_id: str
    user_id: str
    username: str
    post_type: Literal["market_callout", "receipt", "parlay_build", "question", "message"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    edited_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    flag_count: int = 0
    user_rank: Optional[str] = None
    user_badges: List[str] = Field(default_factory=list)
    
    # Engagement metrics
    views: int = 0
    replies: int = 0
    
    # Moderation
    is_flagged: bool = False
    moderation_status: Optional[str] = None


class MarketCalloutPost(PostTemplate):
    """Market Callout - Structured pick discussion with validation"""
    post_type: Literal["market_callout", "receipt", "parlay_build", "question", "message"] = "market_callout"
    
    # Required fields (enforced by template)
    game_matchup: str = Field(..., description="Auto-selected from game room")
    market_type: Literal["spread", "total", "moneyline", "prop"]
    line: str = Field(..., description="Validated numeric line + side")
    confidence: Literal["low", "med", "high"]
    reason: str = Field(..., max_length=240, description="Brief explanation")
    
    # Optional receipt toggle
    played_this: bool = False
    receipt_url: Optional[str] = None
    
    # Attached BeatVegas context (signal_id snapshot)
    signal_id: Optional[str] = None
    model_context: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "game_matchup": "Lakers vs Warriors",
                "market_type": "spread",
                "line": "Lakers -5.5",
                "confidence": "high",
                "reason": "Lakers home dominance + Warriors injuries",
                "played_this": True,
                "signal_id": "sim_abc123"
            }
        }


class ReceiptPost(PostTemplate):
    """Receipt - Winning/losing ticket proof"""
    post_type: Literal["market_callout", "receipt", "parlay_build", "question", "message"] = "receipt"
    
    # Required fields
    screenshot_url: str = Field(..., description="Required upload")
    market: str
    line: str
    result: Literal["W", "L", "P"] = Field(..., description="Win/Loss/Push")
    posted_within_hours: int = Field(default=48, description="Time since game end")
    
    # Verified by system
    verified: bool = False
    verification_status: Optional[str] = None


class ParlayBuildPost(PostTemplate):
    """Parlay Build - Multi-leg construction with volatility awareness"""
    post_type: Literal["market_callout", "receipt", "parlay_build", "question", "message"] = "parlay_build"
    
    # Required fields
    leg_count: int = Field(..., ge=2, le=15)
    legs: List[Dict[str, Any]] = Field(..., description="Must reference existing markets")
    risk_profile: Literal["balanced", "high_vol"]
    reasoning: str = Field(..., max_length=300, description="Why these legs?")
    
    # Auto-calculated
    volatility_badges: List[str] = Field(default_factory=list)
    combined_probability: Optional[float] = None


class QuestionPost(PostTemplate):
    """Question - Education-focused posts (Beginner + General)"""
    post_type: Literal["market_callout", "receipt", "parlay_build", "question", "message"] = "question"
    
    question_text: str = Field(..., max_length=500)
    tags: List[str] = Field(default_factory=list)
    is_answered: bool = False
    accepted_answer_id: Optional[str] = None


class UserRank(BaseModel):
    """User rank and reputation in War Room"""
    user_id: str
    username: str
    
    # Rank progression
    rank: Literal["rookie", "contributor", "verified", "elite", "mod"] = "rookie"
    rank_points: int = 0
    
    # Graded history (optional receipts)
    total_posts: int = 0
    template_compliance_rate: float = 1.0
    graded_picks: int = 0
    graded_win_rate: Optional[float] = None
    volatility_adjusted_score: Optional[float] = None
    max_drawdown: Optional[float] = None
    
    # Behavior metrics
    flag_count: int = 0
    warning_count: int = 0
    mute_count: int = 0
    
    # Badges
    badges: List[str] = Field(default_factory=list)
    is_verified_track_record: bool = False
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RateLimitTracker(BaseModel):
    """Rate limit tracking per user"""
    user_id: str
    tier: Literal["free", "paid", "verified", "elite"] = "free"
    
    # Daily limits
    posts_today: int = 0
    market_callouts_today: int = 0
    last_post_timestamp: Optional[datetime] = None
    
    # Duplicate detection
    recent_market_callouts: List[str] = Field(default_factory=list, description="Last 60 min market keys")
    
    # Spam detection
    is_shadow_muted: bool = False
    mute_expires_at: Optional[datetime] = None
    
    reset_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModerationEvent(BaseModel):
    """Moderation action log"""
    event_id: str
    event_type: Literal["delete", "lock", "mute", "unmute", "flag", "warn", "slow_mode"]
    target_type: Literal["post", "user", "thread"]
    target_id: str
    
    moderator_id: str
    moderator_username: str
    
    reason: Optional[str] = None
    duration_hours: Optional[int] = None  # For mutes
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChannelConfig(BaseModel):
    """Channel configuration with TTL and rules"""
    channel_id: str
    channel_name: str
    channel_type: Literal["live_sport", "discussion", "education", "showcase", "factory"]
    
    # Rules
    allowed_post_types: List[str]
    requires_template: bool = True
    ttl_days: int = Field(..., description="Auto-archive after N days")
    
    # Rate limits
    slow_mode: bool = False
    slow_mode_seconds: int = 30
    
    # Banner content
    banner_what_belongs: str
    banner_what_removed: str
    banner_required_format: str
    banner_cleanup_rules: str
    
    # Tier access
    free_tier_access: Literal["read_only", "limited_post", "full_post"] = "read_only"
    paid_tier_access: Literal["full_post"] = "full_post"


class LeaderboardEntry(BaseModel):
    """Risk-adjusted leaderboard entry"""
    user_id: str
    username: str
    rank: str
    
    # Performance metrics
    units: Optional[float] = None
    win_rate: Optional[float] = None
    sample_size: int = 0
    volatility_adjusted_score: float = 0.0
    max_drawdown: Optional[float] = None
    template_compliance_pct: float = 100.0
    
    # Badges
    has_verified_track_record: bool = False
    badges: List[str] = Field(default_factory=list)
    
    # Ranking
    leaderboard_position: int
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EngagementEvent(BaseModel):
    """Engagement tracking for analytics"""
    event_id: str
    event_type: Literal["view", "reply", "follow", "share", "upvote", "flag"]
    user_id: str
    target_type: Literal["post", "thread", "room", "user"]
    target_id: str
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Context
    session_id: Optional[str] = None
    referrer: Optional[str] = None


# MongoDB Collection Names
COLLECTIONS = {
    "game_rooms": "war_room_game_rooms",
    "market_threads": "war_room_market_threads",
    "posts": "war_room_posts",
    "user_ranks": "war_room_user_ranks",
    "rate_limits": "war_room_rate_limits",
    "moderation_events": "war_room_moderation_events",
    "channel_configs": "war_room_channel_configs",
    "leaderboard": "war_room_leaderboard",
    "engagement_events": "war_room_engagement_events"
}

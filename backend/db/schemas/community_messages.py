"""
Community Message Schema
Raw event for NLP Parser and Reputation Engine
"""
from datetime import datetime, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
import uuid


class CommunityMessage(BaseModel):
    """
    User-generated content in Discord-style community
    Purpose: Raw data for NLP parsing to extract picks, news, sentiment
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Message UUID")
    channel_id: str = Field(..., description="Channel/room ID (e.g., nba-picks, mlb-injuries)")
    user_id: str = Field(..., description="User UUID")
    text: str = Field(..., description="Message content (raw text)")
    
    # Timestamps
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 UTC timestamp")
    
    # Metadata
    meta: dict = Field(default_factory=dict, description="IP, User-Agent, client info")
    
    # User context (for weighting)
    user_plan: Literal["free", "pro", "elite"] = Field(..., description="User subscription tier")
    user_elo: Optional[float] = Field(default=None, description="User's reputation ELO (accuracy-weighted)")
    
    # NLP Parser output (populated asynchronously)
    parsed_intent: Optional[Literal["pick", "news", "injury", "analysis", "chat"]] = None
    parsed_entities: Optional[dict] = Field(default=None, description="Extracted teams, players, markets")
    parsed_sentiment: Optional[float] = Field(default=None, description="Sentiment score -1 (bearish) to +1 (bullish)")
    parsed_confidence: Optional[float] = Field(default=None, description="Parser confidence 0-1")
    parsed_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_abc123",
                "channel_id": "nba-picks",
                "user_id": "usr_xyz789",
                "text": "Lakers -5.5 is FREE MONEY. LeBron healthy, Celtics on back-to-back. Hammering 3u.",
                "ts": "2025-11-10T17:45:00.000Z",
                "meta": {
                    "ip": "192.168.1.1",
                    "ua": "Mozilla/5.0..."
                },
                "user_plan": "elite",
                "user_elo": 1847.3,
                "parsed_intent": "pick",
                "parsed_entities": {
                    "teams": ["Los Angeles Lakers", "Boston Celtics"],
                    "market": "spreads",
                    "side": "Lakers -5.5",
                    "stake": "3u"
                },
                "parsed_sentiment": 0.85,
                "parsed_confidence": 0.92,
                "parsed_at": "2025-11-10T17:45:03.123Z"
            }
        }


class CommunityPickSubmission(BaseModel):
    """
    Structured pick submission derived from NLP parsing
    Purpose: Feed Reputation Engine with trackable picks
    """
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message_id: str = Field(..., description="Source message ID")
    user_id: str = Field(..., description="User UUID")
    
    # Pick details (normalized)
    event_id: Optional[str] = Field(default=None, description="Matched sports event ID")
    market: str = Field(..., description="Market type")
    side: str = Field(..., description="Pick side")
    odds: Optional[float] = Field(default=None, description="Odds claimed by user (decimal)")
    stake_units: Optional[float] = Field(default=None, description="Stake in units")
    
    # Outcome tracking (for ELO calculation)
    outcome: Optional[Literal["win", "loss", "push", "void"]] = None
    settled_at: Optional[str] = None
    
    # Timestamps
    submitted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "submission_id": "sub_abc123",
                "message_id": "msg_abc123",
                "user_id": "usr_xyz789",
                "event_id": "evt_nba_lakers_celtics",
                "market": "spreads",
                "side": "Lakers -5.5",
                "odds": 1.91,
                "stake_units": 3.0,
                "submitted_at": "2025-11-10T17:45:00.000Z"
            }
        }


class UserReputation(BaseModel):
    """
    User reputation tracking (ELO system)
    Purpose: Weight user sentiment in AI model
    """
    user_id: str = Field(..., description="User UUID")
    elo_score: float = Field(default=1500.0, description="ELO rating (starts at 1500)")
    
    # Performance stats
    total_picks: int = Field(default=0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    pushes: int = Field(default=0)
    win_rate: float = Field(default=0.0, description="Win rate (wins / (wins + losses))")
    roi: float = Field(default=0.0, description="Lifetime ROI %")
    
    # CLV tracking
    avg_clv: Optional[float] = Field(default=None, description="Average CLV % across all picks")
    
    # Plan-based multipliers (for sharp_weighted_consensus)
    plan: Literal["free", "pro", "elite"] = Field(..., description="Subscription tier")
    weight_multiplier: float = Field(default=1.0, description="Sentiment weight: free=0.5, pro=1.0, elite=2.0")
    
    # Timestamps
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "usr_xyz789",
                "elo_score": 1847.3,
                "total_picks": 247,
                "wins": 142,
                "losses": 98,
                "pushes": 7,
                "win_rate": 59.17,
                "roi": 12.4,
                "avg_clv": 2.3,
                "plan": "elite",
                "weight_multiplier": 2.0,
                "updated_at": "2025-11-10T18:00:00.000Z"
            }
        }

"""
Telegram Integration & Signal Distribution Schemas
BeatVegas-centric identity and entitlements system
"""
from datetime import datetime, timezone
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field


# ============================================================================
# TELEGRAM INTEGRATION
# ============================================================================

class TelegramIntegration(BaseModel):
    """User's Telegram account link"""
    user_id: str = Field(..., description="BeatVegas user ID (source of truth)")
    provider: Literal["telegram"] = "telegram"
    external_user_id: str = Field(..., description="Telegram user ID")
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None
    linked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    link_token: Optional[str] = None  # One-time token for linking
    link_token_expires_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "usr_abc123",
                "provider": "telegram",
                "external_user_id": "123456789",
                "telegram_username": "johndoe",
                "linked_at": "2025-12-23T10:00:00Z"
            }
        }


class TelegramSubscription(BaseModel):
    """Telegram-only subscription ($39/month standalone product)"""
    subscription_id: str
    user_id: str
    stripe_subscription_id: str
    source: Literal["telegram_stripe"] = "telegram_stripe"
    tier: Literal["telegram_only"] = "telegram_only"
    status: Literal["active", "past_due", "canceled", "incomplete"]
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ENTITLEMENTS (CORE ACCESS CONTROL)
# ============================================================================

class UserEntitlements(BaseModel):
    """
    Computed entitlements based on subscriptions
    Single source of truth for access control
    """
    user_id: str
    
    # Core entitlements
    telegram_signals: bool = False
    telegram_premium: bool = False  # Future: $89.99+ tier
    
    # Derived from
    beatvegas_tier: Optional[Literal["free", "25k", "50k", "100k"]] = "free"
    beatvegas_subscription_active: bool = False
    telegram_only_subscription_active: bool = False
    
    # Metadata
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_computed_reason: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "usr_abc123",
                "telegram_signals": True,
                "telegram_premium": False,
                "beatvegas_tier": "50k",
                "beatvegas_subscription_active": True,
                "telegram_only_subscription_active": False,
                "updated_at": "2025-12-23T10:00:00Z",
                "last_computed_reason": "beatvegas_tier=50k, active=true"
            }
        }


# ============================================================================
# TELEGRAM CHANNEL MEMBERSHIP
# ============================================================================

class TelegramMembership(BaseModel):
    """Tracks Telegram channel membership status"""
    membership_id: str
    telegram_user_id: str
    user_id: str  # BeatVegas user ID
    channel_id: str  # Telegram channel ID
    channel_name: str  # signals, premium, etc
    
    status: Literal["granted", "revoked", "pending"]
    
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    
    # Metadata
    granted_by: Optional[str] = None  # system, admin, etc
    revoke_reason: Optional[str] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# ACCESS CHANGE EVENTS (USER NOTIFICATIONS)
# ============================================================================

class AccessChangeEvent(BaseModel):
    """
    Access change notifications for users
    Shown in-app and via Telegram DM
    """
    event_id: str
    user_id: str
    
    event_type: Literal[
        "telegram_granted",
        "telegram_revoked", 
        "telegram_paused",
        "subscription_upgraded",
        "subscription_downgraded"
    ]
    
    # User-facing content
    message_title: str
    message_body: str
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None
    
    # Metadata
    is_read: bool = False
    sent_telegram_dm: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_123",
                "user_id": "usr_abc",
                "event_type": "telegram_revoked",
                "message_title": "Telegram alerts paused",
                "message_body": "You're on the 25k plan. Telegram alerts require the 50k plan ($49.99).",
                "cta_url": "/billing/upgrade",
                "cta_text": "Upgrade to 50k",
                "is_read": False
            }
        }


# ============================================================================
# SIGNAL GENERATION & DISTRIBUTION
# ============================================================================

class SignalState(BaseModel):
    """Signal state machine (locked enum)"""
    # Public states
    QUALIFIED = "QUALIFIED"  # Actionable, posts to Telegram
    LEAN = "LEAN"  # NO PLAY, platform only
    NO_PLAY = "NO_PLAY"  # Market state update
    
    # Internal states
    PENDING = "PENDING"
    INVALIDATED_LINE_MOVED = "INVALIDATED_LINE_MOVED"
    INVALIDATED_GAME_STARTED = "INVALIDATED_GAME_STARTED"
    INVALIDATED_DATA_MISSING = "INVALIDATED_DATA_MISSING"
    POSTED = "POSTED"
    CLOSED = "CLOSED"


class SharpSideAction(BaseModel):
    """Sharp side action states (spreads only)"""
    CONFIRMED = "CONFIRMED"  # Market aligns with model on recommended side
    ABSENT = "ABSENT"  # Model edge exists, market neutral
    CONTRARIAN = "CONTRARIAN"  # Market opposes public, aligns with model
    CONFLICTED = "CONFLICTED"  # Market contradicts model (disallowed for Qualified)


class Signal(BaseModel):
    """
    BeatVegas signal with qualification logic
    Powered by simulation engine
    """
    signal_id: str
    
    # Game context
    sport: str
    game_id: str
    home_team: str
    away_team: str
    game_commence_time: datetime
    
    # Market
    market_type: Literal["spread", "total", "moneyline", "prop"]
    market_line_vegas: float  # Current market line
    model_line: float  # BeatVegas model prediction
    
    # Edge metrics
    edge: float  # Difference (pts/units)
    win_prob: float  # 0.0 - 1.0
    variance: Literal["low", "medium", "high"]
    volatility_score: Optional[float] = None
    
    # Simulation data
    sim_count_internal: int  # Actual sim count
    sim_count_display: int = 100000  # Always 100k for Telegram
    
    # Signal qualification
    state: str  # From SignalState enum
    sharp_side_state: Optional[str] = None  # From SharpSideAction (spreads only)
    sharp_side_target: Optional[str] = None  # "Team A +8" (explicit side + line)
    
    # Metadata
    reason_code: Optional[str] = None  # Why qualified/invalidated
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    posted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # Simulation reference
    simulation_id: Optional[str] = None


class SignalQualificationThresholds(BaseModel):
    """Configurable thresholds (v1 defaults)"""
    # Qualified Signal
    edge_min_qualified: float = 7.0
    prob_min_qualified: float = 0.56
    variance_max_qualified: Literal["low", "medium"] = "medium"
    
    # Lean (NO PLAY)
    edge_min_lean: float = 4.0
    prob_min_lean: float = 0.53
    variance_max_lean: Literal["low", "medium", "high"] = "high"
    
    # Line movement invalidation
    line_move_tolerance_spread: float = 1.0
    line_move_tolerance_total: float = 2.0
    
    # Daily caps
    max_qualified_per_day: int = 3
    max_leans_per_day: int = 4


# ============================================================================
# TELEGRAM DELIVERY
# ============================================================================

class TelegramDeliveryLog(BaseModel):
    """Audit log for Telegram message delivery"""
    delivery_id: str
    signal_id: str
    channel_id: str
    channel_name: str
    
    telegram_message_id: Optional[str] = None
    
    status: Literal["success", "failed", "skipped"]
    error_payload: Optional[Dict[str, Any]] = None
    
    message_content: str  # Full message text sent
    posted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelegramChannel(BaseModel):
    """Telegram channel configuration"""
    channel_id: str  # Telegram channel ID (negative number)
    channel_name: str  # signals, premium, public
    channel_type: Literal["public", "private_signals", "private_premium"]
    
    # Access control
    requires_entitlement: bool = True
    entitlement_field: Optional[str] = "telegram_signals"  # Field in UserEntitlements
    
    # Bot settings
    bot_is_admin: bool = True
    join_requests_enabled: bool = True
    
    # Metadata
    invite_link: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# AUDIT EVENTS
# ============================================================================

class AuditEvent(BaseModel):
    """System-wide audit trail"""
    event_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    event_type: Literal[
        "entitlement_granted",
        "entitlement_revoked",
        "entitlement_denied",
        "signal_posted",
        "webhook_received",
        "telegram_link_completed",
        "telegram_join_approved",
        "telegram_join_denied",
        "telegram_member_removed",
        "reconciliation_run"
    ]
    
    user_id: Optional[str] = None
    signal_id: Optional[str] = None
    
    payload_snapshot: Dict[str, Any] = Field(default_factory=dict)
    
    # Context
    triggered_by: Optional[str] = None  # webhook, reconciliation, admin, etc
    related_entity_id: Optional[str] = None


# ============================================================================
# MONGODB COLLECTION NAMES
# ============================================================================

COLLECTIONS = {
    "telegram_integrations": "telegram_integrations",
    "telegram_subscriptions": "telegram_subscriptions",
    "user_entitlements": "user_entitlements",
    "telegram_memberships": "telegram_memberships",
    "access_change_events": "access_change_events",
    "signals": "signals",
    "telegram_delivery_log": "telegram_delivery_log",
    "telegram_channels": "telegram_channels",
    "audit_events": "telegram_audit_events",
    "signal_thresholds": "signal_qualification_thresholds"
}

"""
Telegram Publishing System - Database Schemas
Status: LOCKED - INSTITUTIONAL GRADE

Schemas for:
- telegram_queue_item: Eligible posts awaiting publishing
- telegram_post_log: Audit trail of all publish attempts
- telegram_template: Template definitions
- feature_flags: Runtime control (kill switches)
- lkg_config: Last known good version registry

CRITICAL: All published data must be traceable to canonical prediction_log
"""

from datetime import datetime
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


# ==================== TELEGRAM QUEUE ITEM ====================
class TelegramConstraints(BaseModel):
    """Constraints affecting the pick (downgrades, fallbacks, uncertainties)"""
    mode: Literal["none", "constrained"]
    reason_codes: List[str] = Field(default_factory=list)
    # Examples: OVERRIDE_DOWNGRADED, MISSING_ODDS_FALLBACK, 
    # INJURY_UNCERTAIN, VOLATILITY_HIGH, DIVERGENCE_NEAR_LIMIT


class TelegramSelection(BaseModel):
    """Canonical selection data - MUST be present for publishing"""
    selection_id: str = Field(..., description="REQUIRED - canonical selection identifier")
    team_id: str = Field(..., description="REQUIRED - canonical team identifier")
    team_name: str = Field(..., description="REQUIRED - display name for team")
    side: Literal["HOME", "AWAY", "OVER", "UNDER", "DOG", "FAV"]
    line: Optional[float] = Field(None, description="Spread/total line (required for SPREAD/TOTAL)")
    american_odds: Optional[int] = Field(None, description="American odds (required for ML, optional for others)")


class TelegramPricing(BaseModel):
    """Model vs market pricing - ALL required for publishing"""
    model_prob: float = Field(..., ge=0.0, le=1.0, description="Model probability")
    market_prob: float = Field(..., ge=0.0, le=1.0, description="Market implied probability (vig removed)")
    prob_edge: float = Field(..., description="Probability edge (model - market)")
    ev: Optional[float] = Field(None, description="Expected value (optional, omit if not calculated)")


class TelegramDisplay(BaseModel):
    """Display/publishing metadata"""
    allowed: bool = Field(..., description="Whether this post is allowed (passed all gates)")
    template_id: str = Field(..., description="Template to use for rendering")
    cta_url: str = Field(default="https://t.me/BEATVEGASAPP", description="Call-to-action link")
    posted_at: Optional[datetime] = Field(None, description="When actually posted (if posted)")
    telegram_message_id: Optional[str] = Field(None, description="Telegram message ID (if posted)")


class TelegramQueueItem(BaseModel):
    """
    Single eligible post awaiting publishing.
    
    HARD RULE: All fields here must come from canonical prediction_log.
    No inference, no computation, no guessing allowed.
    
    MongoDB Collection: telegram_queue
    Indexes:
    - {queue_id: 1} UNIQUE
    - {prediction_log_id: 1}
    - {event_id: 1, market_type: 1}
    - {created_at: 1}
    - {tier: 1, created_at: -1}
    - {display.allowed: 1, created_at: 1}
    """
    queue_id: str = Field(..., description="Unique queue item ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Event identification (REQUIRED)
    event_id: str = Field(..., description="Canonical event ID")
    league: str = Field(..., description="League (nba, nfl, mlb, etc)")
    market_type: Literal["SPREAD", "MONEYLINE", "TOTAL"] = Field(..., description="Market type")
    
    # Canonical reference (REQUIRED - audit trail)
    prediction_log_id: str = Field(..., description="Prediction log ID - source of truth")
    snapshot_hash: str = Field(..., description="Market snapshot hash - immutability proof")
    model_version: str = Field(..., description="Model version used")
    sim_count: int = Field(..., description="Number of simulations run")
    generated_at: datetime = Field(..., description="When prediction was generated")
    
    # Classification (REQUIRED)
    tier: Literal["EDGE", "LEAN", "MARKET_ALIGNED", "NO_ACTION", "BLOCKED"] = Field(
        ..., 
        description="Tier classification - determines posting eligibility"
    )
    constraints: TelegramConstraints = Field(..., description="Constraints affecting the pick")
    
    # Selection data (REQUIRED - all fields validated before queuing)
    selection: TelegramSelection = Field(..., description="Selection data - must include selection_id")
    
    # Pricing data (REQUIRED)
    pricing: TelegramPricing = Field(..., description="Model vs market pricing")
    
    # Display metadata
    display: TelegramDisplay = Field(..., description="Display/publishing metadata")
    
    # Event metadata (for scheduling/display)
    home_team: str = Field(..., description="Home team name")
    away_team: str = Field(..., description="Away team name")
    start_time: datetime = Field(..., description="Game start time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "queue_id": "q_abc123",
                "created_at": "2026-02-02T10:00:00Z",
                "event_id": "evt_nba_bos_gs_20260202",
                "league": "nba",
                "market_type": "SPREAD",
                "prediction_log_id": "pred_xyz789",
                "snapshot_hash": "snap_a1b2c3",
                "model_version": "v2.1.0",
                "sim_count": 100000,
                "generated_at": "2026-02-02T09:55:00Z",
                "tier": "EDGE",
                "constraints": {
                    "mode": "none",
                    "reason_codes": []
                },
                "selection": {
                    "selection_id": "sel_bos_spread_minus3.5",
                    "team_id": "team_bos",
                    "team_name": "Boston Celtics",
                    "side": "AWAY",
                    "line": -3.5,
                    "american_odds": -110
                },
                "pricing": {
                    "model_prob": 0.602,
                    "market_prob": 0.502,
                    "prob_edge": 0.100,
                    "ev": 0.145
                },
                "display": {
                    "allowed": True,
                    "template_id": "TG_EDGE_V1",
                    "cta_url": "https://t.me/BEATVEGASAPP"
                },
                "home_team": "Golden State Warriors",
                "away_team": "Boston Celtics",
                "start_time": "2026-02-02T19:00:00Z"
            }
        }


# ==================== TELEGRAM POST LOG ====================
class ValidatorReport(BaseModel):
    """Detailed validation results"""
    passed: bool
    failure_reason: Optional[str] = None
    numeric_tokens_validated: int = 0
    missing_fields: List[str] = Field(default_factory=list)
    forbidden_phrases_detected: List[str] = Field(default_factory=list)
    id_mismatches: List[str] = Field(default_factory=list)
    details: Dict = Field(default_factory=dict)


class TelegramPostLog(BaseModel):
    """
    Audit log of all Telegram publishing attempts.
    
    CRITICAL: This is append-only, never update.
    Every publish attempt (success or failure) must be logged.
    
    MongoDB Collection: telegram_post_log
    Indexes:
    - {log_id: 1} UNIQUE
    - {queue_id: 1}
    - {prediction_log_id: 1}
    - {posted: 1, created_at: -1}
    - {validation_failed: 1, created_at: -1}
    - {created_at: -1}
    """
    log_id: str = Field(..., description="Unique log entry ID")
    queue_id: str = Field(..., description="Queue item ID")
    prediction_log_id: str = Field(..., description="Prediction log ID - audit trail")
    
    # Outcome (REQUIRED)
    posted: bool = Field(..., description="Whether post was successfully published")
    validation_failed: bool = Field(..., description="Whether validation failed")
    failure_reason: Optional[str] = Field(None, description="Reason for failure if failed")
    
    # Rendered output (REQUIRED - what would have been/was posted)
    rendered_text: str = Field(..., description="Final rendered text (validated or failed)")
    template_id_used: str = Field(..., description="Template ID used")
    
    # Validation details (REQUIRED)
    validator_report: ValidatorReport = Field(..., description="Detailed validation results")
    
    # Agent metadata (if LLM used)
    agent_version: Optional[str] = Field(None, description="Agent version if LLM used")
    agent_model: Optional[str] = Field(None, description="LLM model used (e.g., gpt-4)")
    
    # Telegram metadata (if posted)
    telegram_message_id: Optional[str] = Field(None, description="Telegram message ID if posted")
    telegram_chat_id: Optional[str] = Field(None, description="Telegram chat ID if posted")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    posted_at: Optional[datetime] = Field(None, description="When actually posted")
    
    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "log_abc123",
                "queue_id": "q_abc123",
                "prediction_log_id": "pred_xyz789",
                "posted": True,
                "validation_failed": False,
                "failure_reason": None,
                "rendered_text": "📊 NBA — SPREAD\nBoston Celtics -3.5 (-110)\nModel Prob: 60.2%\nMarket Prob: 50.2%\nProb Edge: +10.0%\nEV: +14.5%\nClassification: EDGE\n\n🔗 https://t.me/BEATVEGASAPP",
                "template_id_used": "TG_EDGE_V1",
                "validator_report": {
                    "passed": True,
                    "numeric_tokens_validated": 6,
                    "missing_fields": [],
                    "forbidden_phrases_detected": [],
                    "id_mismatches": [],
                    "details": {}
                },
                "agent_version": "v1.0.0",
                "telegram_message_id": "12345",
                "telegram_chat_id": "-1001234567890",
                "created_at": "2026-02-02T10:05:00Z",
                "posted_at": "2026-02-02T10:05:01Z"
            }
        }


# ==================== TELEGRAM TEMPLATES ====================
class TelegramTemplate(BaseModel):
    """
    Template definition for Telegram posts.
    
    HARD RULE: Templates are locked. No dynamic templates allowed.
    Every template must be reviewed and approved before use.
    
    MongoDB Collection: telegram_templates
    Indexes:
    - {template_id: 1} UNIQUE
    - {tier: 1, constraints_mode: 1}
    """
    template_id: str = Field(..., description="Unique template ID")
    tier: Literal["EDGE", "LEAN", "MARKET_ALIGNED"]
    constraints_mode: Literal["none", "constrained"]
    
    # Template definition (Jinja2 or similar)
    template_text: str = Field(..., description="Template text with placeholders")
    
    # Allowed fields (validation)
    required_fields: List[str] = Field(..., description="Fields that must be present in payload")
    optional_fields: List[str] = Field(default_factory=list, description="Fields that may be omitted")
    
    # Forbidden phrases (for constrained templates)
    forbidden_phrases: List[str] = Field(default_factory=list)
    
    # Metadata
    version: str = Field(..., description="Template version")
    approved_by: str = Field(..., description="Who approved this template")
    approved_at: datetime = Field(..., description="When approved")
    active: bool = Field(default=True, description="Whether template is active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "TG_EDGE_V1",
                "tier": "EDGE",
                "constraints_mode": "none",
                "template_text": "📊 {{league|upper}} — {{market_type}}\n{{team_name}} {{line}} ({{american_odds}})\nModel Prob: {{model_prob|pct}}\nMarket Prob: {{market_prob|pct}}\nProb Edge: {{prob_edge|pct_signed}}\n{% if ev %}EV: {{ev|pct_signed}}\n{% endif %}Classification: EDGE\n\n🔗 {{cta_url}}",
                "required_fields": ["league", "market_type", "team_name", "line", "american_odds", "model_prob", "market_prob", "prob_edge", "cta_url"],
                "optional_fields": ["ev"],
                "forbidden_phrases": [],
                "version": "1.0.0",
                "approved_by": "system_admin",
                "approved_at": "2026-02-01T00:00:00Z",
                "active": True
            }
        }


# ==================== FEATURE FLAGS ====================
class FeatureFlag(BaseModel):
    """
    Runtime feature flags for kill switches and gradual rollout.
    
    CRITICAL: These control production behavior. Changes must be audited.
    
    MongoDB Collection: feature_flags
    Indexes:
    - {flag_name: 1} UNIQUE
    - {enabled: 1}
    """
    flag_name: str = Field(..., description="Unique flag name")
    enabled: bool = Field(..., description="Whether flag is enabled")
    
    # Context/conditions (optional)
    conditions: Dict = Field(default_factory=dict, description="Conditions for enabling (e.g., tenant_id whitelist)")
    
    # Metadata
    description: str = Field(..., description="What this flag controls")
    changed_by: str = Field(..., description="Who last changed this flag")
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str = Field(..., description="Reason for last change")
    
    class Config:
        json_schema_extra = {
            "example": {
                "flag_name": "FEATURE_TELEGRAM_AUTOPUBLISH",
                "enabled": False,
                "conditions": {},
                "description": "Enable automatic Telegram publishing (kill switch for integrity issues)",
                "changed_by": "ops_admin",
                "changed_at": "2026-02-02T10:00:00Z",
                "reason": "Initial deployment - enable after validation"
            }
        }


# ==================== LKG (LAST KNOWN GOOD) CONFIG ====================
class LKGConfig(BaseModel):
    """
    Last Known Good version registry for rapid rollback.
    
    CRITICAL: This enables 1-minute rollback to stable state.
    
    MongoDB Collection: lkg_config
    Indexes:
    - {config_id: 1} UNIQUE
    - {updated_at: -1}
    """
    config_id: str = Field(default="lkg_current", description="Config ID (usually singleton 'lkg_current')")
    
    # Version identifiers (REQUIRED for rollback)
    lkg_backend_image: str = Field(..., description="Docker image tag for backend")
    lkg_frontend_build: str = Field(..., description="Build ID for frontend")
    lkg_classifier_commit: str = Field(..., description="Git commit hash for classifier")
    lkg_model_version: str = Field(..., description="Model version")
    
    # Metadata
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = Field(..., description="Who updated LKG")
    reason: str = Field(..., description="Reason for LKG update")
    
    # Rollback history
    previous_lkg: Optional[Dict] = Field(None, description="Previous LKG config (for undo)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "config_id": "lkg_current",
                "lkg_backend_image": "backend:2026-02-01.1",
                "lkg_frontend_build": "web:2026-02-01.1",
                "lkg_classifier_commit": "abc123def456",
                "lkg_model_version": "v2.1.0",
                "updated_at": "2026-02-01T12:00:00Z",
                "updated_by": "deploy_bot",
                "reason": "Validated deployment - all metrics stable for 2 hours"
            }
        }


# ==================== MONGODB INDEX DEFINITIONS ====================
TELEGRAM_QUEUE_INDEXES = [
    {"keys": [("queue_id", 1)], "unique": True},
    {"keys": [("prediction_log_id", 1)]},
    {"keys": [("event_id", 1), ("market_type", 1)]},
    {"keys": [("created_at", 1)]},
    {"keys": [("tier", 1), ("created_at", -1)]},
    {"keys": [("display.allowed", 1), ("created_at", 1)]},
]

TELEGRAM_POST_LOG_INDEXES = [
    {"keys": [("log_id", 1)], "unique": True},
    {"keys": [("queue_id", 1)]},
    {"keys": [("prediction_log_id", 1)]},
    {"keys": [("posted", 1), ("created_at", -1)]},
    {"keys": [("validation_failed", 1), ("created_at", -1)]},
    {"keys": [("created_at", -1)]},
]

TELEGRAM_TEMPLATES_INDEXES = [
    {"keys": [("template_id", 1)], "unique": True},
    {"keys": [("tier", 1), ("constraints_mode", 1)]},
]

FEATURE_FLAGS_INDEXES = [
    {"keys": [("flag_name", 1)], "unique": True},
    {"keys": [("enabled", 1)]},
]

LKG_CONFIG_INDEXES = [
    {"keys": [("config_id", 1)], "unique": True},
    {"keys": [("updated_at", -1)]},
]


def create_telegram_indexes(db):
    """Create all Telegram-related indexes"""
    # Telegram queue
    for index_spec in TELEGRAM_QUEUE_INDEXES:
        db.telegram_queue.create_index(
            index_spec["keys"],
            unique=index_spec.get("unique", False)
        )
    
    # Telegram post log
    for index_spec in TELEGRAM_POST_LOG_INDEXES:
        db.telegram_post_log.create_index(
            index_spec["keys"],
            unique=index_spec.get("unique", False)
        )
    
    # Templates
    for index_spec in TELEGRAM_TEMPLATES_INDEXES:
        db.telegram_templates.create_index(
            index_spec["keys"],
            unique=index_spec.get("unique", False)
        )
    
    # Feature flags
    for index_spec in FEATURE_FLAGS_INDEXES:
        db.feature_flags.create_index(
            index_spec["keys"],
            unique=index_spec.get("unique", False)
        )
    
    # LKG config
    for index_spec in LKG_CONFIG_INDEXES:
        db.lkg_config.create_index(
            index_spec["keys"],
            unique=index_spec.get("unique", False)
        )
    
    print("✅ Created all Telegram system indexes")


if __name__ == "__main__":
    # For standalone execution (index creation)
    import os
    from pymongo import MongoClient
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    create_telegram_indexes(db)
    
    print(f"✅ Telegram system schemas initialized for database: {db_name}")

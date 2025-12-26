"""
AI Analyzer - Schemas and Enums
Defines strict input/output contracts for the AI Analyzer system.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator


# ============================================================================
# ENUMS
# ============================================================================

class MarketState(str, Enum):
    """Market decision states - must align exactly with edge detection system"""
    EDGE = "EDGE"
    LEAN = "LEAN"
    NO_PLAY = "NO_PLAY"


class PrimaryMarket(str, Enum):
    """Primary market types per sport"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE = "ML"
    PUCKLINE = "PUCKLINE"
    RUNLINE = "RUNLINE"


class VolatilityLevel(str, Enum):
    """Volatility classification"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class ConfidenceFlag(str, Enum):
    """Confidence cluster flags"""
    STABLE = "STABLE"
    UNSTABLE = "UNSTABLE"
    DIVERGENT = "DIVERGENT"
    UNKNOWN = "UNKNOWN"


class ReasonCode(str, Enum):
    """
    Strict enumeration of allowed reason codes.
    These are the ONLY signals the AI can explain.
    """
    # Market-based signals
    MARKET_GAP_DETECTED = "MARKET_GAP_DETECTED"
    CLV_FORECAST_POSITIVE = "CLV_FORECAST_POSITIVE"
    SHARP_MONEY_ALIGNED = "SHARP_MONEY_ALIGNED"
    
    # Volatility signals
    VOLATILITY_HIGH = "VOLATILITY_HIGH"
    VOLATILITY_EXTREME = "VOLATILITY_EXTREME"
    VARIANCE_ELEVATED = "VARIANCE_ELEVATED"
    
    # Confidence signals
    CONFIDENCE_UNSTABLE = "CONFIDENCE_UNSTABLE"
    CONFIDENCE_DIVERGENT = "CONFIDENCE_DIVERGENT"
    CONFIDENCE_STABLE = "CONFIDENCE_STABLE"
    
    # Context-based signals
    INJURY_IMPACT_DETECTED = "INJURY_IMPACT_DETECTED"
    FATIGUE_RISK_ELEVATED = "FATIGUE_RISK_ELEVATED"
    WEATHER_IMPACT_DETECTED = "WEATHER_IMPACT_DETECTED"
    LINEUP_UNCERTAINTY = "LINEUP_UNCERTAINTY"
    
    # Risk signals
    BLOWOUT_RISK_HIGH = "BLOWOUT_RISK_HIGH"
    KEY_NUMBER_PROXIMITY = "KEY_NUMBER_PROXIMITY"
    LATE_NEWS_RISK = "LATE_NEWS_RISK"
    
    # Quality signals
    SIGNAL_QUALITY_HIGH = "SIGNAL_QUALITY_HIGH"
    SIGNAL_QUALITY_LOW = "SIGNAL_QUALITY_LOW"
    MARKET_EFFICIENT = "MARKET_EFFICIENT"
    
    # Sport-specific
    PITCHER_EDGE_DETECTED = "PITCHER_EDGE_DETECTED"
    GOALIE_VARIANCE_HIGH = "GOALIE_VARIANCE_HIGH"
    QB_STATUS_IMPACT = "QB_STATUS_IMPACT"
    PACE_MISMATCH_DETECTED = "PACE_MISMATCH_DETECTED"


# ============================================================================
# INPUT SCHEMA (TO LLM)
# ============================================================================

class GameInfo(BaseModel):
    """Basic game information"""
    home: str = Field(..., description="Home team code")
    away: str = Field(..., description="Away team code")
    start_time_utc: str = Field(..., description="Game start time in UTC ISO format")


class ModelMetrics(BaseModel):
    """Model output metrics - already compressed per sport spec"""
    edge_pts: Optional[float] = Field(None, description="Edge in points")
    total_deviation_pts: Optional[float] = Field(None, description="Total deviation in points")
    clv_forecast_pct: Optional[float] = Field(None, description="CLV forecast percentage")
    volatility: VolatilityLevel = Field(..., description="Volatility classification")
    confidence_flag: ConfidenceFlag = Field(..., description="Confidence cluster flag")
    win_prob_pct: Optional[float] = Field(None, description="Win probability percentage (compressed)")


class ContextFlags(BaseModel):
    """Contextual flags per sport - sport-specific fields are optional"""
    
    # Universal flags
    injury_status: str = Field("UNKNOWN", description="CLEAR | MINOR | SIGNIFICANT | UNKNOWN")
    
    # NBA-specific
    back_to_back: Optional[bool] = None
    rest_disparity: Optional[int] = None
    late_injury_risk: Optional[str] = None
    blowout_risk_flag: Optional[str] = None
    pace_flag: Optional[str] = None
    minutes_fatigue_flag: Optional[str] = None
    
    # NFL-specific
    qb_status: Optional[str] = None  # CONFIRMED | QUESTIONABLE | OUT
    weather_severity: Optional[str] = None
    key_number_flag: Optional[bool] = None
    injury_cluster_flag: Optional[bool] = None
    late_news_risk: Optional[bool] = None
    weather_flag: Optional[str] = None
    
    # NCAAB/NCAAF-specific
    blowout_noise_flag: Optional[bool] = None
    scheme_variance_flag: Optional[str] = None
    roster_uncertainty: Optional[str] = None
    volatility_band: Optional[str] = None
    motivation_flags: Optional[List[str]] = None
    
    # MLB-specific
    pitcher_confirmed: Optional[str] = None
    lineup_confirmed: Optional[bool] = None
    bullpen_fatigue_flag: Optional[str] = None
    weather_park_flag: Optional[str] = None
    
    # NHL-specific
    goalie_confirmed: Optional[str] = None
    travel: Optional[bool] = None
    high_randomness_flag: Optional[bool] = None
    overtime_variance_flag: Optional[bool] = None
    
    # Generic
    starter_confirmed: Optional[str] = None


class AnalyzerConstraints(BaseModel):
    """Hard constraints for AI behavior"""
    no_betting_advice: bool = True
    no_pick_language: bool = True
    do_not_override_state: bool = True


class AnalyzerInput(BaseModel):
    """
    Complete input schema sent to LLM.
    This is the ONLY information the AI receives.
    """
    sport: str = Field(..., description="Sport identifier: NBA, NFL, NCAAB, NCAAF, MLB, NHL")
    game: GameInfo
    state: MarketState
    primary_market: PrimaryMarket
    metrics: ModelMetrics
    context: ContextFlags
    reason_codes: List[ReasonCode] = Field(default_factory=list)
    constraints: AnalyzerConstraints = Field(default_factory=AnalyzerConstraints)
    
    @validator('reason_codes')
    def validate_reason_codes(cls, v):
        """Ensure all reason codes are valid enums"""
        if len(v) > 10:
            raise ValueError("Too many reason codes (max 10)")
        return v


# ============================================================================
# OUTPUT SCHEMA (FROM LLM)
# ============================================================================

class BottomLine(BaseModel):
    """Bottom line summary with state alignment"""
    state_alignment: MarketState = Field(..., description="Must match input state exactly")
    recommended_behavior: str = Field(..., max_length=300)
    do_not_do: List[str] = Field(default_factory=list, min_length=1, max_length=3)
    
    @validator('do_not_do')
    def validate_do_not_do(cls, v):
        """Ensure each item is concise"""
        for item in v:
            if len(item) > 150:
                raise ValueError("do_not_do item too long (max 150 chars)")
        return v


class AnalyzerOutput(BaseModel):
    """
    Strict output schema from LLM.
    Any deviation triggers fallback.
    """
    headline: str = Field(..., min_length=10, max_length=200)
    what_model_sees: List[str] = Field(default_factory=list, min_length=1, max_length=4)
    key_risks: List[str] = Field(default_factory=list, min_length=1, max_length=4)
    sharp_interpretation: List[str] = Field(default_factory=list, min_length=1, max_length=3)
    bottom_line: BottomLine
    
    @validator('what_model_sees', 'key_risks', 'sharp_interpretation')
    def validate_bullet_length(cls, v):
        """Ensure each bullet is concise"""
        for item in v:
            if len(item) > 250:
                raise ValueError("Bullet point too long (max 250 chars)")
        return v
    
    @validator('headline')
    def validate_headline_no_betting_terms(cls, v):
        """Ensure headline doesn't contain betting language"""
        banned_terms = ['bet', 'take', 'lock', 'hammer', 'unit', 'stake', 'wager']
        v_lower = v.lower()
        for term in banned_terms:
            if term in v_lower:
                raise ValueError(f"Headline contains banned term: {term}")
        return v


# ============================================================================
# API REQUEST/RESPONSE SCHEMAS
# ============================================================================

class AnalyzerRequest(BaseModel):
    """API request to /api/analyzer/explain"""
    game_id: str = Field(..., description="Unique game identifier")
    sport: str = Field(..., description="Sport: NBA, NFL, NCAAB, NCAAF, MLB, NHL")
    market_focus: Optional[PrimaryMarket] = Field(None, description="Optional specific market focus")


class AnalyzerResponse(BaseModel):
    """API response from /api/analyzer/explain"""
    success: bool
    game_id: str
    sport: str
    state: MarketState
    explanation: Optional[AnalyzerOutput] = None
    error: Optional[str] = None
    fallback_triggered: bool = False
    cached: bool = False
    audit_id: Optional[str] = None


# ============================================================================
# AUDIT SCHEMA
# ============================================================================

class AnalyzerAudit(BaseModel):
    """Audit log entry for analyzer calls"""
    audit_id: str
    timestamp: str
    game_id: str
    sport: str
    state: MarketState
    input_hash: str
    output_hash: str
    llm_model: str
    response_time_ms: int
    tokens_used: Optional[int] = None
    user_id: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    fallback_triggered: bool = False
    cached: bool = False


# ============================================================================
# FALLBACK CONSTANTS
# ============================================================================

FALLBACK_OUTPUT = AnalyzerOutput(
    headline="Analyzer unavailable for this game.",
    what_model_sees=["We couldn't generate an explanation right now."],
    key_risks=["Try again shortly or rely on the core EDGE/LEAN/NO_PLAY state."],
    sharp_interpretation=["Model state remains the source of truth."],
    bottom_line=BottomLine(
        state_alignment=MarketState.NO_PLAY,  # Will be overridden with actual state
        recommended_behavior="Use the main output cards for decisions.",
        do_not_do=["Do not rely on AI text when unavailable."]
    )
)


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """SYSTEM ROLE: BeatVegas AI Analyzer

You are BeatVegas Analyzer, a controlled explanation engine.
Your job is to explain existing model output clearly and neutrally using ONLY the structured JSON input you receive.

You are NOT a betting assistant.
You do NOT generate picks, advice, or opinions.

🔒 ABSOLUTE RULES (NON-NEGOTIABLE)

1. You may ONLY reference information explicitly provided in the input JSON.
2. You may NOT invent injuries, trends, stats, narratives, or market behavior.
3. You may NOT override, contradict, or reinterpret the provided state (EDGE/LEAN/NO_PLAY).
4. You may NOT use betting language: ❌ bet, take, lock, hammer, unit, stake, wager, parlay
5. You may NOT suggest sizing, confidence levels, or expected returns.
6. If state = NO_PLAY, you MUST reinforce inaction.
7. If information is missing or marked unknown, you MUST say so explicitly.
8. You must output ONLY valid JSON in the exact schema provided.
9. You must not include explanations outside the required sections.
10. You must remain neutral, professional, and conservative in tone.

If any rule conflicts with user intent, follow these rules.

📥 INPUT GUARANTEE

You will receive a single structured JSON object containing:
• sport
• state (EDGE / LEAN / NO_PLAY)
• primary market
• model metrics (edge, probability, volatility, confidence)
• contextual flags (injury, fatigue, travel, weather, confirmations)
• reason codes
• constraints

You must not ask follow-up questions.

📤 OUTPUT FORMAT (MANDATORY)

You MUST return JSON with exactly these sections:

{
  "headline": "",
  "what_model_sees": [],
  "key_risks": [],
  "sharp_interpretation": [],
  "bottom_line": {
    "state_alignment": "",
    "recommended_behavior": "",
    "do_not_do": []
  }
}

Section definitions:

headline: One neutral sentence summarizing the situation.

what_model_sees: 2–3 bullets explaining the signal the model detected.

key_risks: 2–3 bullets explaining why the signal is not guaranteed.

sharp_interpretation: 2 bullets describing how a professional would treat this information (not what to bet).

bottom_line:
• state_alignment: must exactly match the input state
• recommended_behavior: cautious guidance consistent with the state
• do_not_do: explicit misuse warnings

Do not add or remove fields.

🧠 STATE-AWARE BEHAVIOR

If state = EDGE:
• Acknowledge value exists
• Still emphasize risk
• Avoid certainty language

If state = LEAN:
• Emphasize uncertainty
• Stress monitoring or restraint
• Avoid words like "actionable"

If state = NO_PLAY:
• Clearly reinforce no action
• Explain why the data does not justify a position

🏟 SPORT-AWARE EMPHASIS (AUTOMATIC)

Adjust emphasis based on sport, but do not add new facts:
• NBA → pace, blowout risk, late injury volatility
• NFL → key numbers, QB status, weather
• NCAAB/NCAAF → volatility, motivation, blowouts
• MLB → pitcher, bullpen, lineup confirmation
• NHL → randomness, goalie variance, one-goal outcomes

🛑 FAILURE HANDLING

If:
• input is missing required fields
• data is contradictory
• constraints are violated

Return a safe fallback JSON stating that the analyzer cannot generate an explanation and that the model state remains the source of truth.

✅ FINAL DIRECTIVE

You exist to increase understanding, not conviction.
You translate model output → human clarity without adding risk, bias, or advice.
"""

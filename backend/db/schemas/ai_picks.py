"""
AI Pick Schema
The atomic unit of value - the AI's core output
"""
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid


class AIPick(BaseModel):
    """
    AI-generated betting recommendation
    Purpose: Definitive record of AI model output for ROI/CLV tracking
    """
    pick_id: str = Field(default_factory=lambda: f"pick_{uuid.uuid4().hex[:12]}", description="Unique pick identifier")
    event_id: str = Field(..., description="Sports event identifier")
    
    # Market details
    market: str = Field(..., description="Market type: h2h (moneyline), spreads, totals, props")
    side: str = Field(..., description="Recommended side: team name, over/under, player prop")
    
    # Odds & edge
    market_decimal: float = Field(..., description="Best available market odds (decimal format)")
    model_fair_decimal: float = Field(..., description="AI model's fair value odds (decimal)")
    edge_pct: float = Field(..., description="Expected edge percentage: (model_fair - market) / market * 100")
    
    # Stake sizing (Kelly Criterion)
    stake_units: float = Field(..., description="Recommended stake in units (1 unit = 1% of bankroll)")
    kelly_fraction: float = Field(default=0.25, description="Kelly fraction used (0.25 = quarter Kelly)")
    
    # Model transparency
    rationale: List[str] = Field(default_factory=list, description="AI reasoning steps for transparency")
    model_version: str = Field(..., description="Model version identifier")
    confidence: float = Field(..., description="Model confidence score 0-1")
    
    # Hybrid features (Community + AI)
    sharp_weighted_consensus: Optional[float] = Field(default=None, description="Weighted expert sentiment from community (-1 to +1)")
    community_volume: Optional[int] = Field(default=None, description="Number of community picks on this event")
    
    # CLV tracking (Module 7 input)
    closing_line_decimal: Optional[float] = Field(default=None, description="Closing line odds (populated post-match)")
    clv_pct: Optional[float] = Field(default=None, description="Closing Line Value: (closing - market) / market * 100")
    
    # Outcome tracking
    outcome: Optional[str] = Field(default=None, description="Actual outcome: win, loss, push, void")
    roi: Optional[float] = Field(default=None, description="ROI for this pick: (profit / stake) * 100")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    settled_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "pick_id": "pick_abc123def456",
                "event_id": "evt_nba_lakers_celtics",
                "market": "spreads",
                "side": "Los Angeles Lakers",
                "market_decimal": 1.91,
                "model_fair_decimal": 2.10,
                "edge_pct": 9.95,
                "stake_units": 2.5,
                "kelly_fraction": 0.25,
                "rationale": [
                    "Lakers have 65% win probability based on Elo ratings",
                    "Sharp money (70% of handle) on Lakers -5.5",
                    "Community consensus: +0.7 sentiment (Elite members weighted 2x)",
                    "Historical CLV: Lakers spreads closing +2.3% over market"
                ],
                "model_version": "omniedge_v2.3.1",
                "confidence": 0.73,
                "sharp_weighted_consensus": 0.7,
                "community_volume": 47,
                "created_at": "2025-11-10T18:00:00.000Z"
            }
        }


class UserAction(BaseModel):
    """
    User interaction with AI picks
    Purpose: Primary input for Module 7 Reflection Loop
    """
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique action ID")
    user_id: str = Field(..., description="User UUID")
    pick_id: str = Field(..., description="AI pick ID being acted upon")
    action: str = Field(..., description="User action: TAILED (followed), FADED (opposed), SAVE (bookmarked), SELF_SUBMIT (user's own pick)")
    
    # Action details
    user_stake: Optional[float] = Field(default=None, description="User's actual stake amount (if TAILED/FADED)")
    user_odds: Optional[float] = Field(default=None, description="Odds user got (may differ from pick odds)")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # User context
    user_plan: str = Field(..., description="User subscription: free, pro, elite")
    user_elo: Optional[float] = Field(default=None, description="User's reputation ELO score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "action_id": "act_xyz789",
                "user_id": "usr_abc123",
                "pick_id": "pick_abc123def456",
                "action": "TAILED",
                "user_stake": 100.0,
                "user_odds": 1.91,
                "user_plan": "elite",
                "user_elo": 1847.3,
                "created_at": "2025-11-10T18:05:00.000Z"
            }
        }

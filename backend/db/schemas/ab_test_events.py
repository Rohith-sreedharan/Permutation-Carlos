"""
A/B Test Event Schema
Tracks all user interactions for A/B test performance analysis
"""
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ABTestEvent(BaseModel):
    """
    Event tracking for A/B test variants
    Purpose: Track user behavior across 5 concurrent test variants over 90-day lifecycle
    """
    id: Optional[str] = Field(default=None, description="Auto-generated MongoDB _id")
    event: str = Field(..., description="Event type: view_landing, click_cta, start_trial, subscribe_paid, churn")
    variant: Literal["A", "B", "C", "D", "E"] = Field(..., description="Test variant: A=Control, B=Urgency, C=SocialProof, D=Simplified, E=Challenger")
    ref: Optional[str] = Field(default=None, description="Affiliate referral ID from ?ref= parameter")
    user_id: Optional[str] = Field(default=None, description="User UUID if authenticated")
    session_id: str = Field(..., description="Anonymous session ID from bv_var cookie")
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO 8601 timestamp")
    
    # Additional context
    meta: Optional[dict] = Field(default_factory=dict, description="Additional metadata: ip, ua, page_url, etc.")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event": "view_landing",
                "variant": "B",
                "ref": "AFF_12345",
                "session_id": "sess_abc123",
                "ts": "2025-11-10T12:00:00.000Z",
                "meta": {
                    "ip": "192.168.1.1",
                    "ua": "Mozilla/5.0...",
                    "page_url": "https://beatvegas.app/?ref=AFF_12345"
                }
            }
        }


class ABTestVariantConfig(BaseModel):
    """
    Configuration for each A/B test variant
    """
    variant: Literal["A", "B", "C", "D", "E"]
    name: str
    description: str
    hypothesis: str
    features: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "variant": "B",
                "name": "Urgency",
                "description": "Tests time-pressure tactics",
                "hypothesis": "Countdown timer + scarcity messaging increases conversion by 15%",
                "features": {
                    "countdown_timer": True,
                    "spots_remaining": True,
                    "urgency_copy": "Only 3 spots left today!"
                }
            }
        }


# Variant definitions per spec
VARIANT_CONFIGS = {
    "A": ABTestVariantConfig(
        variant="A",
        name="Control",
        description="Expertise & Accuracy",
        hypothesis="Sharp bettors value accuracy metrics and technical expertise",
        features={
            "expertise_focus": True,
            "accuracy_metrics": True,
            "technical_jargon": True,
            "three_tier_pricing": True
        }
    ),
    "B": ABTestVariantConfig(
        variant="B",
        name="Urgency",
        description="Time Pressure & Scarcity",
        hypothesis="Countdown timers and limited spots drive impulse conversions",
        features={
            "countdown_timer": True,
            "spots_remaining_counter": True,
            "urgency_copy": True,
            "three_tier_pricing": True
        }
    ),
    "C": ABTestVariantConfig(
        variant="C",
        name="Social Proof",
        description="Testimonials & Activity",
        hypothesis="Live testimonials and member activity build trust and FOMO",
        features={
            "testimonial_carousel": True,
            "member_activity_feed": True,
            "social_proof_stats": True,
            "three_tier_pricing": True
        }
    ),
    "D": ABTestVariantConfig(
        variant="D",
        name="Simplified",
        description="Mass Market Appeal",
        hypothesis="Removing technical jargon and simplifying to single plan increases mass market adoption",
        features={
            "simplified_copy": True,
            "no_jargon": True,
            "single_plan": True,
            "three_tier_pricing": False
        }
    ),
    "E": ABTestVariantConfig(
        variant="E",
        name="Challenger",
        description="Anti-Establishment Brand",
        hypothesis="'Beat the house' narrative resonates with contrarian bettors",
        features={
            "anti_establishment_narrative": True,
            "rebel_branding": True,
            "underdog_positioning": True,
            "three_tier_pricing": True
        }
    )
}

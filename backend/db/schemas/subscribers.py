"""
Subscriber Schema
Links affiliate IDs to users throughout the funnel lifecycle
"""
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr
import uuid


class Subscriber(BaseModel):
    """
    Tracks user from initial landing to conversion
    Purpose: Link affiliate ID to user email for commission attribution
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="User UUID")
    email: EmailStr = Field(..., description="User email address")
    ref: Optional[str] = Field(default=None, description="Affiliate referral ID from ?ref= parameter")
    status: Literal["pending", "trial", "converted", "churned"] = Field(default="pending", description="Funnel status")
    variant: Optional[Literal["A", "B", "C", "D", "E"]] = Field(default=None, description="A/B test variant assigned")
    
    # Stripe integration
    stripe_customer_id: Optional[str] = Field(default=None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(default=None, description="Stripe subscription ID")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trial_started_at: Optional[str] = None
    converted_at: Optional[str] = None
    churned_at: Optional[str] = None
    
    # Subscription details
    plan: Optional[Literal["starter", "pro", "sharps_room", "founder"]] = Field(
        default=None,
        description="Subscription tier: starter (basic sims), pro, sharps_room (CLV tracker + advanced dashboards), founder (limited exclusive)"
    )
    monthly_value: Optional[float] = Field(default=None, description="Monthly subscription value in USD")
    
    # Feature access controls
    access_monte_carlo: bool = Field(default=False, description="Access to full Monte Carlo simulations")
    access_clv_tracker: bool = Field(default=False, description="Access to CLV tracking and analysis")
    access_advanced_dashboards: bool = Field(default=False, description="Access to advanced analytics dashboards")
    access_prop_mispricing: bool = Field(default=False, description="Access to prop mispricing alerts")
    access_parlay_correlation: bool = Field(default=False, description="Access to parlay correlation engine")
    max_picks_per_day: int = Field(default=5, description="Maximum picks user can access per day")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "usr_abc123",
                "email": "user@example.com",
                "ref": "AFF_12345",
                "status": "converted",
                "variant": "B",
                "stripe_customer_id": "cus_xyz789",
                "stripe_subscription_id": "sub_abc456",
                "plan": "sharps_room",
                "monthly_value": 99.99,
                "access_monte_carlo": True,
                "access_clv_tracker": True,
                "access_advanced_dashboards": True,
                "access_prop_mispricing": True,
                "access_parlay_correlation": True,
                "max_picks_per_day": 20,
                "created_at": "2025-11-01T12:00:00.000Z",
                "converted_at": "2025-11-05T15:30:00.000Z"
            }
        }

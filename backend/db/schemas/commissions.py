"""
Commission Schema
Definitive record for affiliate ledger and payouts
"""
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid


class CommissionEarned(BaseModel):
    """
    Affiliate commission record
    Purpose: Track all commissions for payout processing
    """
    commission_id: str = Field(default_factory=lambda: f"comm_{uuid.uuid4().hex[:12]}", description="Commission UUID")
    affiliate_id: str = Field(..., description="Affiliate referral ID")
    user_id: str = Field(..., description="Converted user UUID")
    
    # Commission calculation
    basis: float = Field(..., description="Subscription amount used for commission (USD)")
    commission_rate: float = Field(default=0.20, description="Commission rate (20-40% based on tier)")
    amount: float = Field(..., description="Commission amount in USD")
    tier: Optional[str] = Field(default=None, description="Subscription tier of converted user")
    
    # Commission type
    commission_type: Literal["first_payment", "recurring", "bonus"] = Field(..., description="Commission trigger")
    
    # Status tracking
    status: Literal["pending", "approved", "paid", "disputed"] = Field(default="pending")
    
    # Stripe reference
    stripe_subscription_id: Optional[str] = None
    stripe_invoice_id: Optional[str] = None
    
    # Timestamps
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Commission earned timestamp")
    approved_at: Optional[str] = None
    paid_at: Optional[str] = None
    
    # Payout details
    payout_method: Optional[Literal["stripe_connect", "paypal", "wire"]] = None
    payout_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "commission_id": "comm_abc123def456",
                "affiliate_id": "AFF_12345",
                "user_id": "usr_xyz789",
                "basis": 49.99,
                "commission_rate": 0.20,
                "amount": 10.00,
                "commission_type": "first_payment",
                "status": "approved",
                "stripe_subscription_id": "sub_abc456",
                "stripe_invoice_id": "in_xyz789",
                "ts": "2025-11-05T15:30:00.000Z",
                "approved_at": "2025-11-05T15:35:00.000Z"
            }
        }


class AffiliateAccount(BaseModel):
    """
    Affiliate account and performance tracking
    """
    affiliate_id: str = Field(..., description="Unique affiliate ID (e.g., AFF_12345)")
    
    # Account details
    name: str = Field(..., description="Affiliate name or company")
    email: str = Field(..., description="Payout email")
    payout_method: Literal["stripe_connect", "paypal", "wire"] = Field(default="stripe_connect")
    payout_details: dict = Field(default_factory=dict, description="Payment method details (encrypted)")
    
    # Performance metrics
    total_referrals: int = Field(default=0, description="Total users referred")
    converted_referrals: int = Field(default=0, description="Users who converted to paid")
    conversion_rate: float = Field(default=0.0, description="Conversion rate %")
    
    # Commission totals
    total_earned: float = Field(default=0.0, description="Total commissions earned (USD)")
    total_paid: float = Field(default=0.0, description="Total commissions paid out (USD)")
    balance: float = Field(default=0.0, description="Current balance pending payout (USD)")
    
    # Status
    status: Literal["active", "paused", "suspended"] = Field(default="active")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_payout_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "affiliate_id": "AFF_12345",
                "name": "Bettor Network",
                "email": "payouts@bettornetwork.com",
                "payout_method": "stripe_connect",
                "total_referrals": 347,
                "converted_referrals": 89,
                "conversion_rate": 25.6,
                "total_earned": 4450.00,
                "total_paid": 4000.00,
                "balance": 450.00,
                "status": "active",
                "created_at": "2025-01-01T00:00:00.000Z",
                "last_payout_at": "2025-11-01T00:00:00.000Z"
            }
        }

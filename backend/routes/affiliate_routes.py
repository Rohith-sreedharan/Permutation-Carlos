"""
Affiliate System Routes
Handle referral tracking and commission management
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr
import uuid
from db.mongo import db
from db.schemas.subscribers import Subscriber
from db.schemas.commissions import CommissionEarned, AffiliateAccount


router = APIRouter(prefix="/api/affiliate", tags=["Affiliate"])


class RegisterSubscriberRequest(BaseModel):
    """Register new subscriber with affiliate ref"""
    email: EmailStr
    ref: Optional[str] = None
    variant: Optional[Literal["A", "B", "C", "D", "E"]] = None


class ConversionWebhookRequest(BaseModel):
    """Stripe webhook payload (simplified)"""
    customer_id: str
    subscription_id: str
    invoice_id: str
    amount: float  # Subscription amount in USD
    plan: Literal["pro", "elite"]


@router.post("/register")
async def register_subscriber(request: Request, body: RegisterSubscriberRequest):
    """
    Register a new subscriber with affiliate tracking
    Called when user signs up (before payment)
    """
    # Check if email already exists
    existing = db["subscribers"].find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Get session data from middleware (if available)
    session_variant = getattr(request.state, "variant", body.variant)
    session_ref = getattr(request.state, "ref", body.ref)
    
    # Validate variant
    valid_variant: Optional[Literal["A", "B", "C", "D", "E"]] = None
    if session_variant in ["A", "B", "C", "D", "E"]:
        valid_variant = session_variant  # type: ignore
    
    # Create subscriber document
    subscriber = Subscriber(
        email=body.email,
        ref=session_ref,
        variant=valid_variant,
        status="pending"
    )
    
    # Insert into MongoDB
    db["subscribers"].insert_one(subscriber.dict())
    
    # Track event
    db["ab_test_events"].insert_one({
        "event": "subscriber_registered",
        "variant": session_variant,
        "ref": session_ref,
        "session_id": getattr(request.state, "session_id", None),
        "ts": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "email": body.email,
            "ip": request.client.host if request.client else None
        }
    })
    
    return {
        "status": "ok",
        "subscriber_id": subscriber.id,
        "ref": session_ref
    }


@router.post("/webhook/stripe")
async def stripe_webhook(body: ConversionWebhookRequest):
    """
    Handle Stripe webhook for subscription.paid events
    This triggers commission calculation and attribution
    
    In production, verify Stripe webhook signature!
    """
    # Find subscriber by Stripe customer ID or create new record
    subscriber = db["subscribers"].find_one({"stripe_customer_id": body.customer_id})
    
    if not subscriber:
        # If not found, this might be a direct purchase without ref
        # Create minimal subscriber record
        subscriber_id = str(uuid.uuid4())
        db["subscribers"].insert_one({
            "id": subscriber_id,
            "email": "unknown@stripe.com",  # Would be populated from Stripe
            "ref": None,
            "status": "converted",
            "stripe_customer_id": body.customer_id,
            "stripe_subscription_id": body.subscription_id,
            "plan": body.plan,
            "monthly_value": body.amount,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "converted_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        # Update existing subscriber
        subscriber_id = subscriber["id"]
        db["subscribers"].update_one(
            {"id": subscriber_id},
            {
                "$set": {
                    "status": "converted",
                    "stripe_customer_id": body.customer_id,
                    "stripe_subscription_id": body.subscription_id,
                    "plan": body.plan,
                    "monthly_value": body.amount,
                    "converted_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    # Get ref for commission attribution
    ref = subscriber.get("ref") if subscriber else None
    commission_amount = 0.0
    
    # If there's an affiliate ref, create commission
    if ref:
        # Default commission: 20% of first payment
        commission_rate = 0.20
        commission_amount = body.amount * commission_rate
        
        commission = CommissionEarned(
            affiliate_id=ref,
            user_id=subscriber_id,
            basis=body.amount,
            commission_rate=commission_rate,
            amount=commission_amount,
            commission_type="first_payment",
            status="pending",
            stripe_subscription_id=body.subscription_id,
            stripe_invoice_id=body.invoice_id
        )
        
        db["commissions"].insert_one(commission.dict())
        
        # Update affiliate account balance
        db["affiliate_accounts"].update_one(
            {"affiliate_id": ref},
            {
                "$inc": {
                    "total_earned": commission_amount,
                    "balance": commission_amount,
                    "converted_referrals": 1
                }
            },
            upsert=False
        )
    
    # Track conversion event
    db["ab_test_events"].insert_one({
        "event": "subscribe_paid",
        "variant": subscriber.get("variant") if subscriber else None,
        "ref": ref,
        "session_id": None,  # No session at this point
        "user_id": subscriber_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "plan": body.plan,
            "amount": body.amount,
            "stripe_subscription_id": body.subscription_id
        }
    })
    
    return {
        "status": "ok",
        "subscriber_id": subscriber_id,
        "commission_created": ref is not None,
        "commission_amount": commission_amount if ref else 0
    }


@router.get("/dashboard/{affiliate_id}")
async def get_affiliate_dashboard(affiliate_id: str):
    """
    Get affiliate performance dashboard
    Used by partners.beatvegas.io
    """
    # Get affiliate account
    affiliate = db["affiliate_accounts"].find_one({"affiliate_id": affiliate_id})
    if not affiliate:
        raise HTTPException(status_code=404, detail="Affiliate not found")
    
    # Get commission history
    commissions = list(
        db["commissions"]
        .find({"affiliate_id": affiliate_id})
        .sort("ts", -1)
        .limit(100)
    )
    
    # Convert ObjectId
    for c in commissions:
        c["_id"] = str(c["_id"])
    
    # Get referral stats
    total_referrals = db["subscribers"].count_documents({"ref": affiliate_id})
    converted = db["subscribers"].count_documents({"ref": affiliate_id, "status": "converted"})
    
    # Calculate conversion rate
    conversion_rate = (converted / total_referrals * 100) if total_referrals > 0 else 0
    
    affiliate["_id"] = str(affiliate["_id"])
    
    return {
        "status": "ok",
        "affiliate": affiliate,
        "stats": {
            "total_referrals": total_referrals,
            "converted_referrals": converted,
            "conversion_rate": round(conversion_rate, 2)
        },
        "commissions": commissions
    }


@router.post("/create-account")
async def create_affiliate_account(
    name: str,
    email: EmailStr,
    payout_method: Literal["stripe_connect", "paypal", "wire"] = "stripe_connect"
):
    """
    Create new affiliate account
    Returns unique affiliate_id for referral tracking
    """
    # Check if email already exists
    existing = db["affiliate_accounts"].find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate unique affiliate ID
    affiliate_id = f"AFF_{uuid.uuid4().hex[:8].upper()}"
    
    account = AffiliateAccount(
        affiliate_id=affiliate_id,
        name=name,
        email=email,
        payout_method=payout_method
    )
    
    db["affiliate_accounts"].insert_one(account.dict())
    
    return {
        "status": "ok",
        "affiliate_id": affiliate_id,
        "referral_link": f"https://beatvegas.app/?ref={affiliate_id}"
    }


@router.get("/leaderboard")
async def get_affiliate_leaderboard(limit: int = 50):
    """
    Get top affiliates by earnings (for gamification)
    """
    affiliates = list(
        db["affiliate_accounts"]
        .find({"status": "active"})
        .sort("total_earned", -1)
        .limit(limit)
    )
    
    # Anonymize for privacy
    leaderboard = []
    for i, aff in enumerate(affiliates):
        leaderboard.append({
            "rank": i + 1,
            "name": aff["name"][:3] + "***",  # Anonymize
            "total_earned": aff["total_earned"],
            "converted_referrals": aff["converted_referrals"],
            "conversion_rate": aff.get("conversion_rate", 0)
        })
    
    return {
        "status": "ok",
        "leaderboard": leaderboard
    }

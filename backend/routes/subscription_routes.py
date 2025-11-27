"""
Subscription Routes - Fix for /api/subscription/* endpoints
This module provides subscription status endpoints separate from payment routes
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from db.mongo import db
from bson import ObjectId
import stripe
import os

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    """Extract user_id from Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = parts[1]
    if not token.startswith('user:'):
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    user_id = token.split(':', 1)[1]
    return user_id


@router.get("/status")
async def get_subscription_status(authorization: Optional[str] = Header(None)):
    """
    Get user's current subscription status
    Returns tier, renewal date, payment method, and subscription status
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Default response for users without active subscription
    response = {
        "tier": user.get("tier", "starter"),
        "renewalDate": None,
        "paymentMethod": None,
        "status": "active" if user.get("tier") == "starter" else "inactive"
    }
    
    # If user has Stripe subscription, fetch live status
    if user.get("stripe_subscription_id"):
        try:
            subscription = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            
            # Safely handle timestamp
            renewal_date = None
            if subscription.get("current_period_end"):
                try:
                    renewal_date = datetime.fromtimestamp(
                        int(subscription["current_period_end"]), 
                        tz=timezone.utc
                    ).isoformat()
                except (ValueError, TypeError):
                    pass
            
            response = {
                "tier": user.get("tier", "starter"),
                "renewalDate": renewal_date,
                "status": subscription.get("status", "unknown"),
                "paymentMethod": None  # Would need to fetch payment method separately
            }
            
            # Add payment method details if available
            if subscription.get("default_payment_method"):
                try:
                    pm = stripe.PaymentMethod.retrieve(subscription["default_payment_method"])
                    if pm.get("card"):
                        response["paymentMethod"] = {
                            "last4": pm["card"].get("last4", "****"),
                            "brand": pm["card"].get("brand", "unknown").capitalize()
                        }
                except Exception as e:
                    print(f"Error fetching payment method: {e}")
        
        except Exception as e:
            print(f"Stripe error fetching subscription: {e}")
            # Return user's stored tier info even if Stripe call fails
    
    return response


@router.get("/usage")
async def get_subscription_usage(authorization: Optional[str] = Header(None)):
    """
    Get user's subscription usage (simulations run, daily limits, etc.)
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    tier = user.get("tier", "starter")
    
    # Tier limits
    tier_limits = {
        "starter": {"sims_per_day": 2, "name": "Starter (Free)"},
        "pro": {"sims_per_day": 15, "name": "Pro"},
        "sharps_room": {"sims_per_day": 60, "name": "Sharps Room"},
        "founder": {"sims_per_day": 300, "name": "Founder"}
    }
    
    limits = tier_limits.get(tier, tier_limits["starter"])
    
    # Get usage from simulations collection (simplified - in production track daily usage)
    usage = user.get("usage", {})
    sims_used_today = usage.get("sims_used_today", 0)
    last_reset = usage.get("last_reset", datetime.now(timezone.utc).isoformat())
    
    return {
        "tier": tier,
        "tier_name": limits["name"],
        "sims_per_day": limits["sims_per_day"],
        "sims_used_today": sims_used_today,
        "sims_remaining": max(0, limits["sims_per_day"] - sims_used_today),
        "last_reset": last_reset
    }

"""
Subscription Routes - Fix for /api/subscription/* endpoints
This module provides subscription status endpoints separate from payment routes
"""
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import RedirectResponse
from typing import Optional
from datetime import datetime, timezone
from db.mongo import db
from bson import ObjectId
import stripe
import os

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])
stripe_router = APIRouter(prefix="/api/stripe", tags=["Stripe"])

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
    Returns canonical entitlement state, billing period metadata, and payment status.
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    billing_state = db["billing_state"].find_one({"user_id": user_id}) or {}

    raw_status = str(billing_state.get("status", "inactive")).lower()
    if raw_status == "active":
        normalized_status = "active"
    elif raw_status in {"past_due", "past-due"}:
        normalized_status = "past_due"
    else:
        normalized_status = "canceled"

    response = {
        "plan_id": billing_state.get("plan_id"),
        "platform_access": bool(billing_state.get("platform_access", False)),
        "telegram_access": bool(billing_state.get("telegram_access", False)),
        "engine_cycles_limit": int(billing_state.get("engine_cycles_limit", 0) or 0),
        "engine_cycles_remaining": int(billing_state.get("engine_cycles_remaining", 0) or 0),
        "parlay_tokens_remaining": int(billing_state.get("parlay_tokens_remaining", 0) or 0),
        "overage_charges_current_period": float(billing_state.get("overage_charges_current_period", 0) or 0),
        "billing_period_end": billing_state.get("billing_period_end") or billing_state.get("next_billing_date"),
        "renewalDate": billing_state.get("next_billing_date"),
        "paymentMethod": None,
        "status": normalized_status,
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
                "plan_id": response.get("plan_id"),
                "platform_access": response.get("platform_access", False),
                "telegram_access": response.get("telegram_access", False),
                "engine_cycles_limit": response.get("engine_cycles_limit", 0),
                "engine_cycles_remaining": response.get("engine_cycles_remaining", 0),
                "parlay_tokens_remaining": response.get("parlay_tokens_remaining", 0),
                "overage_charges_current_period": response.get("overage_charges_current_period", 0),
                "billing_period_end": response.get("billing_period_end"),
                "renewalDate": renewal_date,
                "status": "active" if subscription.get("status") in {"active", "trialing"} else "past_due" if subscription.get("status") == "past_due" else "canceled",
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
    Get user's canonical entitlement usage snapshot.
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    billing_state = db["billing_state"].find_one({"user_id": user_id}) or {}

    return {
        "plan_id": billing_state.get("plan_id"),
        "platform_access": bool(billing_state.get("platform_access", False)),
        "telegram_access": bool(billing_state.get("telegram_access", False)),
        "engine_cycles_limit": int(billing_state.get("engine_cycles_limit", 0) or 0),
        "engine_cycles_remaining": int(billing_state.get("engine_cycles_remaining", 0) or 0),
        "parlay_tokens_remaining": int(billing_state.get("parlay_tokens_remaining", 0) or 0),
        "billing_period_end": billing_state.get("billing_period_end") or billing_state.get("next_billing_date"),
    }


# ========================================================================
# STRIPE CUSTOMER PORTAL
# ========================================================================

@stripe_router.get("/customer-portal")
async def get_customer_portal(authorization: Optional[str] = Header(None)):
    """
    Get Stripe Customer Portal URL for subscription management
    Returns JSON with portal URL instead of redirecting
    Allows users to update payment methods, view invoices, cancel subscription
    """
    user_id = _get_user_id_from_auth(authorization)
    
    try:
        user = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    stripe_customer_id = user.get("stripe_customer_id")
    
    if not stripe_customer_id:
        raise HTTPException(
            status_code=400, 
            detail="No Stripe customer found. Please subscribe first."
        )
    
    try:
        # Create portal session
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{os.getenv('FRONTEND_URL', 'http://127.0.0.1:3000')}/settings/billing"
        )
        
        # Return portal URL as JSON for frontend to handle redirect
        return {"url": session.url}
        
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating portal session: {str(e)}")

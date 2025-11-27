"""
Payment Routes - Stripe Integration
Handles subscription checkout sessions and webhook events
"""
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timezone
import os
import stripe
import hmac
import hashlib
from db.mongo import db


router = APIRouter(prefix="/api/payment", tags=["Payment"])

# Initialize Stripe with secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


class CreateCheckoutRequest(BaseModel):
    """Request to create Stripe checkout session"""
    tier_id: Literal["pro", "sharps_room", "founder"]
    user_id: Optional[str] = None


class CreateMicroChargeRequest(BaseModel):
    """Request to create one-time micro-transaction"""
    product_id: str  # e.g., 'parlay_3_leg', 'parlay_6_leg'
    user_id: str
    parlay_id: Optional[str] = None  # For tracking which parlay was purchased


# Pricing configuration (in cents)
TIER_PRICES = {
    "pro": {
        "price": 1999,  # $19.99/month
        "name": "Pro Plan",
        "description": "Advanced analytics and AI picks"
    },
    "sharps_room": {
        "price": 4999,  # $49.99/month
        "name": "Sharps Room",
        "description": "Elite CLV tracking, Brier Score, and volatility indices"
    },
    "founder": {
        "price": 9999,  # $99.99/month
        "name": "Founder",
        "description": "Lifetime access to all features + exclusive insights"
    }
}

# Micro-transaction pricing (one-time purchases)
MICRO_TRANSACTION_PRICES = {
    "parlay_3_leg": {
        "price": 499,  # $4.99
        "elite_price": 399,  # $3.99 Elite discount
        "name": "AI Parlay (3-4 Legs)",
        "description": "Optimized 3-4 leg parlay with correlation analysis"
    },
    "parlay_5_leg": {
        "price": 999,  # $9.99
        "elite_price": 799,  # $7.99 Elite discount
        "name": "AI Parlay (5-6 Legs)",
        "description": "High-volatility 5-6 leg parlay with simulation data"
    }
}


@router.post("/create-checkout-session")
async def create_checkout_session(body: CreateCheckoutRequest):
    """
    Create Stripe checkout session for subscription upgrade
    
    Returns:
        checkout_url: Redirect user to this URL to complete payment
        session_id: Stripe session ID for tracking
    """
    if body.tier_id not in TIER_PRICES:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {body.tier_id}")
    
    tier_config = TIER_PRICES[body.tier_id]
    user_id = body.user_id or "anonymous"
    
    try:
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": tier_config["name"],
                        "description": tier_config["description"],
                    },
                    "unit_amount": tier_config["price"],
                    "recurring": {
                        "interval": "month"
                    }
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + f"/settings?success=true&tier={body.tier_id}",
            cancel_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/settings?canceled=true",
            metadata={
                "user_id": user_id,
                "tier_id": body.tier_id
            }
        )
        
        return {
            "status": "ok",
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post("/create-micro-charge")
async def create_micro_charge(body: CreateMicroChargeRequest):
    """
    Create one-time Stripe checkout for micro-transactions (AI Parlay Architect)
    
    Pricing:
    - Standard: $4.99 - $9.99 depending on product
    - Elite Tier: Discounted price
    
    Returns:
        checkout_url: Redirect user to complete payment
        session_id: Stripe session ID
    """
    if body.product_id not in MICRO_TRANSACTION_PRICES:
        raise HTTPException(status_code=400, detail=f"Invalid product_id: {body.product_id}")
    
    product_config = MICRO_TRANSACTION_PRICES[body.product_id]
    
    # Check if user is Elite tier for discount
    user = db.users.find_one({"user_id": body.user_id})
    subscription = db.subscriptions.find_one(
        {"user_id": body.user_id},
        sort=[("created_at", -1)]
    ) if user else None
    
    user_tier = subscription.get("tier", "free").lower() if subscription else "free"
    
    # Apply Elite discount
    price = product_config["elite_price"] if user_tier == "elite" else product_config["price"]
    
    try:
        # Create one-time payment checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": product_config["name"],
                        "description": product_config["description"],
                    },
                    "unit_amount": price,
                },
                "quantity": 1,
            }],
            mode="payment",  # One-time payment
            success_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + f"/architect?success=true&parlay_id={body.parlay_id}",
            cancel_url=os.getenv("FRONTEND_URL", "http://localhost:3000") + "/architect?canceled=true",
            metadata={
                "user_id": body.user_id,
                "product_id": body.product_id,
                "parlay_id": body.parlay_id or "",
                "transaction_type": "micro_charge"
            }
        )
        
        return {
            "status": "ok",
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "price": price,
            "discount_applied": user_tier == "elite"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """
    Stripe webhook handler
    
    Handles events:
    - checkout.session.completed: Upgrade user tier when payment succeeds
    - customer.subscription.deleted: Downgrade user when subscription cancels
    - invoice.payment_failed: Handle failed payments
    """
    payload = await request.body()
    
    # Verify webhook signature
    if not STRIPE_WEBHOOK_SECRET:
        print("⚠️ STRIPE_WEBHOOK_SECRET not set, skipping signature verification (INSECURE)")
    else:
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing stripe-signature header")
        
        try:
            stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")
    
    # Parse event
    import json
    event = json.loads(payload)
    event_type = event["type"]
    
    print(f"📬 Received Stripe webhook: {event_type}")
    
    # Handle checkout.session.completed
    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        transaction_type = session["metadata"].get("transaction_type")
        
        # Handle micro-transactions separately
        if transaction_type == "micro_charge":
            product_id = session["metadata"].get("product_id")
            parlay_id = session["metadata"].get("parlay_id")
            payment_intent_id = session.get("payment_intent")
            
            if not user_id or not product_id:
                print(f"⚠️ Missing metadata in micro-charge session: {session['id']}")
                return {"status": "ok"}
            
            # Record micro-transaction purchase
            db.parlay_architect_purchases.insert_one({
                "user_id": user_id,
                "product_id": product_id,
                "parlay_id": parlay_id,
                "payment_intent_id": payment_intent_id,
                "session_id": session["id"],
                "amount_paid": session.get("amount_total", 0),
                "purchased_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Auto-unlock the parlay if parlay_id provided
            if parlay_id:
                db.parlay_architect_unlocks.insert_one({
                    "parlay_id": parlay_id,
                    "user_id": user_id,
                    "user_tier": "paid",
                    "payment_method": "micro_transaction",
                    "payment_intent_id": payment_intent_id,
                    "unlocked_at": datetime.now(timezone.utc).isoformat()
                })
            
            print(f"✅ Micro-charge completed: {user_id} purchased {product_id}")
            return {"status": "ok"}
        
        # Handle subscription upgrades
        tier_id = session["metadata"].get("tier_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        
        if not user_id or not tier_id:
            print(f"⚠️ Missing metadata in session: {session['id']}")
            return {"status": "ok"}
        
        # Update user tier in MongoDB
        result = db["users"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "tier": tier_id,
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "upgraded_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        print(f"✓ User {user_id} upgraded to {tier_id}")
        
        # Log payment event
        db["payment_events"].insert_one({
            "user_id": user_id,
            "tier_id": tier_id,
            "event_type": "subscription_created",
            "stripe_session_id": session["id"],
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "amount": session.get("amount_total"),
            "currency": session.get("currency"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    # Handle subscription cancellation
    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        subscription_id = subscription["id"]
        
        # Find user by subscription ID and downgrade
        user = db["users"].find_one({"stripe_subscription_id": subscription_id})
        if user:
            db["users"].update_one(
                {"user_id": user["user_id"]},
                {
                    "$set": {
                        "tier": "starter",  # Downgrade to free tier
                        "downgraded_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            print(f"✓ User {user['user_id']} downgraded to starter (subscription canceled)")
            
            # Log event
            db["payment_events"].insert_one({
                "user_id": user["user_id"],
                "event_type": "subscription_canceled",
                "stripe_subscription_id": subscription_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    # Handle failed payment
    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        
        # Find user by customer ID
        user = db["users"].find_one({"stripe_customer_id": customer_id})
        if user:
            print(f"⚠️ Payment failed for user {user['user_id']}")
            
            # Log failed payment
            db["payment_events"].insert_one({
                "user_id": user["user_id"],
                "event_type": "payment_failed",
                "stripe_customer_id": customer_id,
                "stripe_invoice_id": invoice.get("id"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # TODO: Send email notification to user
    
    return {"status": "ok"}


@router.get("/subscription-status")
async def get_subscription_status(user_id: str):
    """
    Get user's current subscription status
    """
    user = db["users"].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # If user has Stripe subscription, fetch live status
    if user.get("stripe_subscription_id"):
        try:
            subscription = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            
            return {
                "status": "ok",
                "tier": user.get("tier", "starter"),
                "stripe_status": subscription.get("status"),
                "current_period_end": subscription.get("current_period_end"),
                "cancel_at_period_end": subscription.get("cancel_at_period_end")
            }
        except Exception as e:
            print(f"Error fetching subscription: {e}")
    
    # No active subscription
    return {
        "status": "ok",
        "tier": user.get("tier", "starter"),
        "stripe_status": None
    }


@router.post("/cancel-subscription")
async def cancel_subscription(user_id: str):
    """
    Cancel user's subscription (will remain active until period end)
    """
    user = db["users"].find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription_id = user.get("stripe_subscription_id")
    if not subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    
    try:
        # Cancel at period end (user keeps access until billing cycle ends)
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        return {
            "status": "ok",
            "message": "Subscription will cancel at period end",
            "current_period_end": subscription.get("current_period_end")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

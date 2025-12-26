"""
Enhanced Stripe Webhook Handler
Triggers entitlement recomputation on subscription changes
"""
from fastapi import APIRouter, Request, HTTPException
import stripe
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

load_dotenv()

from backend.services.entitlements_service import EntitlementsEngine, EntitlementNotifier
from backend.services.telegram_bot_service import TelegramBotService
from backend.db.schemas.telegram_schemas import COLLECTIONS


router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")


# Async database connection helper
async def get_db() -> AsyncIOMotorDatabase:
    """Get async MongoDB database connection"""
    mongodb_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "beatvegas")
    client = AsyncIOMotorClient(mongodb_uri)
    return client[database_name]


@router.post("/stripe")
async def stripe_webhook_handler(request: Request):
    """
    Enhanced Stripe webhook handler
    Triggers entitlement recomputation and Telegram access management
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle subscription events
    entitlements_engine = EntitlementsEngine(db)
    notifier = EntitlementNotifier(db)
    telegram_service = TelegramBotService(db)
    if event["type"] in [
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted"
    ]:
        subscription = event["data"]["object"]
        
        # Get user_id from subscription metadata
        user_id = subscription.get("metadata", {}).get("user_id")
        
        if not user_id:
            # Try to find user by customer ID
            customer_id = subscription.get("customer")
            user_doc = await db["users"].find_one({"stripe_customer_id": customer_id})
            if user_doc:
                user_id = user_doc["user_id"]
        
        if not user_id:
            return {"status": "skipped", "reason": "no_user_id"}
        
        # Determine subscription type
        price_id = subscription["items"]["data"][0]["price"]["id"]
        
        # Check if it's a Telegram-only subscription
        telegram_price_id = os.getenv("STRIPE_TELEGRAM_PRICE_ID")  # $39/month
        
        if price_id == telegram_price_id:
            # Handle Telegram-only subscription
            await handle_telegram_subscription_event(
                db, user_id, event["type"], subscription
            )
        else:
            # Handle BeatVegas platform subscription
            await handle_platform_subscription_event(
                db, user_id, event["type"], subscription
            )
        
        # Recompute entitlements
        old_ent = await entitlements_engine.get_entitlements(user_id)
        old_access = old_ent.telegram_signals if old_ent else False
        
        new_ent, access_changed = await entitlements_engine.handle_subscription_change(
            user_id=user_id,
            event_type=event["type"].replace("customer.subscription.", "subscription_"),
            subscription_data=subscription
        )
        
        # Handle access changes
        if access_changed:
            if new_ent.telegram_signals and not old_access:
                # Grant access
                await telegram_service.grant_channel_access(
                    user_id=user_id,
                    channel_name="signals"
                )
                
                await notifier.create_access_change_event(
                    user_id=user_id,
                    event_type="telegram_granted",
                    context={"tier": new_ent.beatvegas_tier}
                )
                
            elif not new_ent.telegram_signals and old_access:
                # Revoke access
                await telegram_service.revoke_channel_access(
                    user_id=user_id,
                    channel_name="signals",
                    reason="subscription_downgraded"
                )
                
                await notifier.create_access_change_event(
                    user_id=user_id,
                    event_type="telegram_revoked",
                    context={"tier": new_ent.beatvegas_tier}
                )
    
    # Handle payment failures
    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        
        # Find user
        user_doc = await db["users"].find_one({"stripe_customer_id": customer_id})
        if user_doc:
            user_id = user_doc["user_id"]
            
            # Create notification
            await notifier.create_access_change_event(
                user_id=user_id,
                event_type="telegram_paused",
                context={"reason": "payment_failed"}
            )
    
    return {"status": "processed", "event_type": event["type"]}


async def handle_platform_subscription_event(
    db,
    user_id: str,
    event_type: str,
    subscription: dict
):
    """Handle BeatVegas platform subscription changes"""
    # Update subscriptions collection
    tier_map = {
        os.getenv("STRIPE_25K_PRICE_ID"): "25k",
        os.getenv("STRIPE_50K_PRICE_ID"): "50k",
        os.getenv("STRIPE_100K_PRICE_ID"): "100k",
        os.getenv("STRIPE_PRO_PRICE_ID"): "pro"
    }
    
    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = tier_map.get(price_id, "free")
    
    if event_type == "customer.subscription.deleted":
        # Mark subscription as canceled
        await db["subscriptions"].update_one(
            {"stripe_subscription_id": subscription["id"]},
            {
                "$set": {
                    "status": "canceled",
                    "canceled_at": datetime.now(timezone.utc)
                }
            }
        )
    else:
        # Upsert subscription
        await db["subscriptions"].update_one(
            {"stripe_subscription_id": subscription["id"]},
            {
                "$set": {
                    "user_id": user_id,
                    "tier": tier,
                    "status": subscription["status"],
                    "current_period_start": datetime.fromtimestamp(
                        subscription["current_period_start"], tz=timezone.utc
                    ),
                    "current_period_end": datetime.fromtimestamp(
                        subscription["current_period_end"], tz=timezone.utc
                    ),
                    "updated_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )


async def handle_telegram_subscription_event(
    db,
    user_id: str,
    event_type: str,
    subscription: dict
):
    """Handle Telegram-only subscription ($39) changes"""
    from backend.db.schemas.telegram_schemas import TelegramSubscription
    
    if event_type == "customer.subscription.deleted":
        # Mark as canceled
        await db[COLLECTIONS["telegram_subscriptions"]].update_one(
            {"stripe_subscription_id": subscription["id"]},
            {
                "$set": {
                    "status": "canceled",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    else:
        # Upsert Telegram subscription
        telegram_sub = TelegramSubscription(
            subscription_id=subscription["id"],
            user_id=user_id,
            stripe_subscription_id=subscription["id"],
            tier="telegram_only",
            status=subscription["status"],
            current_period_start=datetime.fromtimestamp(
                subscription["current_period_start"], tz=timezone.utc
            ),
            current_period_end=datetime.fromtimestamp(
                subscription["current_period_end"], tz=timezone.utc
            )
        )
        
        await db[COLLECTIONS["telegram_subscriptions"]].update_one(
            {"stripe_subscription_id": subscription["id"]},
            {"$set": telegram_sub.dict()},
            upsert=True
        )

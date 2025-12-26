"""
Telegram Integration API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

load_dotenv()

from services.entitlements_service import EntitlementsEngine, EntitlementNotifier
from services.telegram_bot_service import TelegramBotService
from services.signal_generation_service import SignalGenerationEngine
from services.signal_posting_service import SignalPostingService
from middleware.auth import get_current_user  # Assumes existing auth


router = APIRouter(prefix="/api/telegram", tags=["telegram"])


# Async database connection helper
async def get_db() -> AsyncIOMotorDatabase:
    """Get async MongoDB database connection"""
    mongodb_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "beatvegas")
    client = AsyncIOMotorClient(mongodb_uri)
    return client[database_name]


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LinkTelegramRequest(BaseModel):
    """Request to generate link token"""
    pass


class LinkTelegramResponse(BaseModel):
    """Response with link token"""
    link_token: str
    expires_in: int  # seconds
    instructions: str


class CompleteLinkRequest(BaseModel):
    """Complete Telegram link (called by bot)"""
    link_token: str
    telegram_user_id: str
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None


class TelegramStatusResponse(BaseModel):
    """User's Telegram connection status"""
    linked: bool
    telegram_username: Optional[str] = None
    telegram_user_id: Optional[str] = None
    has_access: bool
    channels: List[str] = Field(default_factory=list)
    entitlements: Dict


class JoinRequestWebhook(BaseModel):
    """Telegram join request webhook payload"""
    chat_id: str
    user_id: str
    username: Optional[str] = None


class AccessChangeNotification(BaseModel):
    """Access change event for user"""
    event_id: str
    event_type: str
    title: str
    message: str
    cta_url: Optional[str] = None
    cta_text: Optional[str] = None
    created_at: datetime
    is_read: bool


# ============================================================================
# ACCOUNT LINKING ENDPOINTS
# ============================================================================

@router.post("/link", response_model=LinkTelegramResponse)
async def generate_link_token(
    request: Request,
    user = Depends(get_current_user)
):
    """
    Generate one-time link token for Telegram account linking
    
    User flow:
    1. User clicks "Link Telegram" in settings
    2. Receives 6-character code (e.g., "A3F9K2")
    3. Opens Telegram bot
    4. Sends /link A3F9K2 to bot
    5. Bot calls /api/telegram/link/complete
    """
    db = await get_db()
    telegram_service = TelegramBotService(db)
    
    user_id = str(user["_id"])  # Convert ObjectId to string
    token = await telegram_service.generate_link_token(user_id)
    
    return LinkTelegramResponse(
        link_token=token,
        expires_in=3600,  # 1 hour
        instructions=(
            f"1. Open Telegram and search for @BeatVegasBot\n"
            f"2. Send: /link {token}\n"
            f"3. Bot will confirm your account is linked"
        )
    )


@router.post("/link/complete")
async def complete_telegram_link(
    payload: CompleteLinkRequest,
    request: Request
):
    """
    Complete Telegram account linking (called by bot)
    
    Protected by bot token verification
    """
    # Verify request is from Telegram bot
    bot_token = request.headers.get("X-Telegram-Bot-Token")
    if bot_token != os.getenv("TELEGRAM_BOT_TOKEN"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = await get_db()
    telegram_service = TelegramBotService(db)
    entitlements_engine = EntitlementsEngine(db)
    
    # Link account
    integration = await telegram_service.link_telegram_account(
        link_token=payload.link_token,
        telegram_user_id=payload.telegram_user_id,
        telegram_username=payload.telegram_username,
        telegram_first_name=payload.telegram_first_name
    )
    
    if not integration:
        raise HTTPException(status_code=400, detail="Invalid or expired link token")
    
    # Recompute entitlements
    entitlements = await entitlements_engine.compute_entitlements(
        integration.user_id,
        recompute_reason="telegram_linked"
    )
    
    # Grant channel access if entitled
    if entitlements.telegram_signals:
        await telegram_service.grant_channel_access(
            user_id=integration.user_id,
            channel_name="signals"
        )
    
    return {"status": "linked", "user_id": integration.user_id}


@router.get("/status", response_model=TelegramStatusResponse)
async def get_telegram_status(user = Depends(get_current_user)):
    """Get user's Telegram connection and entitlement status"""
    try:
        user_id = str(user["_id"])  # Convert ObjectId to string
        db = await get_db()
        telegram_service = TelegramBotService(db)
        entitlements_engine = EntitlementsEngine(db)
        
        # Get integration
        integration = await telegram_service.get_telegram_integration(user_id)
        
        # Get entitlements
        entitlements = await entitlements_engine.get_entitlements(user_id)
        
        if not entitlements:
            entitlements = await entitlements_engine.compute_entitlements(
                user_id,
                recompute_reason="status_check"
            )
        
        # Get active channels
        channels = []
        if integration and entitlements.telegram_signals:
            channels.append("signals")
        if integration and entitlements.telegram_premium:
            channels.append("premium")
        
        return TelegramStatusResponse(
            linked=integration is not None,
            telegram_username=integration.telegram_username if integration else None,
            telegram_user_id=integration.external_user_id if integration else None,
            has_access=entitlements.telegram_signals,
            channels=channels,
            entitlements=entitlements.dict()
        )
    except Exception as e:
        print(f"Error in get_telegram_status: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get Telegram status: {str(e)}")


@router.delete("/unlink")
async def unlink_telegram(user = Depends(get_current_user)):
    """Unlink Telegram account"""
    user_id = str(user["_id"])  # Convert ObjectId to string
    db = await get_db()
    telegram_service = TelegramBotService(db)
    
    # Get integration
    integration = await telegram_service.get_telegram_integration(user_id)
    
    if not integration:
        raise HTTPException(status_code=404, detail="No Telegram account linked")
    
    # Revoke channel access
    await telegram_service.revoke_channel_access(
        user_id=user_id,
        channel_name="signals",
        reason="user_unlinked"
    )
    
    # Delete integration
    from db.schemas.telegram_schemas import COLLECTIONS
    await db[COLLECTIONS["telegram_integrations"]].delete_one({
        "user_id": user_id
    })
    
    return {"status": "unlinked"}


# ============================================================================
# TELEGRAM WEBHOOKS
# ============================================================================

@router.post("/webhook/join-request")
async def handle_join_request_webhook(
    payload: JoinRequestWebhook,
    request: Request
):
    """
    Handle Telegram join request webhook
    
    Telegram sends this when user requests to join private channel
    """
    # Verify webhook signature
    # TODO: Implement Telegram webhook signature verification
    
    db = await get_db()
    telegram_service = TelegramBotService(db)
    
    approved = await telegram_service.handle_join_request(
        telegram_user_id=payload.user_id,
        channel_id=payload.chat_id
    )
    
    return {
        "status": "approved" if approved else "denied",
        "user_id": payload.user_id
    }


@router.post("/webhook/bot-updates")
async def handle_bot_updates(request: Request):
    """
    Handle Telegram bot updates webhook
    
    Receives all bot messages, commands, etc.
    """
    # Verify webhook
    # TODO: Implement webhook verification
    
    update = await request.json()
    
    # Handle different update types
    if "message" in update:
        message = update["message"]
        
        # Handle /link command
        if message.get("text", "").startswith("/link"):
            # Extract link token
            parts = message["text"].split()
            if len(parts) == 2:
                link_token = parts[1]
                
                # Complete linking
                db = await get_db()
                telegram_service = TelegramBotService(db)
                
                integration = await telegram_service.link_telegram_account(
                    link_token=link_token,
                    telegram_user_id=str(message["from"]["id"]),
                    telegram_username=message["from"].get("username"),
                    telegram_first_name=message["from"].get("first_name")
                )
                
                if integration:
                    await telegram_service.send_dm(
                        str(message["from"]["id"]),
                        "✅ Account linked successfully!\n\n"
                        "You can now join BeatVegas signal channels."
                    )
                else:
                    await telegram_service.send_dm(
                        str(message["from"]["id"]),
                        "❌ Invalid or expired link code.\n\n"
                        "Generate a new code at beatvegas.com/settings"
                    )
    
    return {"status": "ok"}


# ============================================================================
# USER NOTIFICATIONS
# ============================================================================

@router.get("/notifications", response_model=List[AccessChangeNotification])
async def get_access_notifications(user = Depends(get_current_user)):
    """Get access change notifications for user"""
    try:
        user_id = str(user["_id"])  # Convert ObjectId to string
        db = await get_db()
        from db.schemas.telegram_schemas import COLLECTIONS
        
        cursor = db[COLLECTIONS["access_change_events"]].find({
            "user_id": user_id
        }).sort("created_at", -1).limit(20)
        
        notifications = []
        async for doc in cursor:
            notifications.append(AccessChangeNotification(
                event_id=doc["event_id"],
                event_type=doc["event_type"],
                title=doc["message_title"],
                message=doc["message_body"],
                cta_url=doc.get("cta_url"),
                cta_text=doc.get("cta_text"),
                created_at=doc["created_at"],
                is_read=doc.get("is_read", False)
            ))
        
        return notifications
    except Exception as e:
        print(f"Error in get_access_notifications: {e}")
        import traceback
        traceback.print_exc()
        # Return empty list instead of error to not break UI
        return []


@router.post("/notifications/{event_id}/read")
async def mark_notification_read(
    event_id: str,
    user = Depends(get_current_user)
):
    """Mark notification as read"""
    user_id = str(user["_id"])  # Convert ObjectId to string
    db = await get_db()
    from db.schemas.telegram_schemas import COLLECTIONS
    
    await db[COLLECTIONS["access_change_events"]].update_one(
        {"event_id": event_id, "user_id": user_id},
        {"$set": {"is_read": True}}
    )
    
    return {"status": "marked_read"}


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@router.post("/admin/recompute-entitlements")
async def admin_recompute_all_entitlements(user = Depends(get_current_user)):
    """Admin: Recompute all user entitlements (nightly reconciliation)"""
    # TODO: Add admin role check
    
    db = await get_db()
    entitlements_engine = EntitlementsEngine(db)
    
    stats = await entitlements_engine.recompute_all_entitlements()
    
    return {"status": "completed", "stats": stats}


@router.get("/admin/entitlements/{target_user_id}")
async def admin_explain_entitlements(
    target_user_id: str,
    user = Depends(get_current_user)
):
    """Admin: Explain entitlements for a user (diagnostic)"""
    # TODO: Add admin role check
    
    db = await get_db()
    entitlements_engine = EntitlementsEngine(db)
    
    explanation = await entitlements_engine.explain_entitlements(target_user_id)
    
    return explanation


@router.post("/admin/signals/post-daily")
async def admin_post_daily_signals(user = Depends(get_current_user)):
    """Admin: Manually trigger daily signal posting"""
    # TODO: Add admin role check
    
    db = await get_db()
    telegram_service = TelegramBotService(db)
    posting_service = SignalPostingService(db, telegram_service)
    
    stats = await posting_service.post_daily_signals()
    
    return {"status": "completed", "stats": stats}


@router.post("/admin/signals/{signal_id}/retract")
async def admin_retract_signal(
    signal_id: str,
    reason: str = "line_moved",
    user = Depends(get_current_user)
):
    """Admin: Retract a posted signal"""
    # TODO: Add admin role check
    
    db = await get_db()
    telegram_service = TelegramBotService(db)
    posting_service = SignalPostingService(db, telegram_service)
    
    success = await posting_service.retract_signal(signal_id, reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Signal not found or not posted")
    
    return {"status": "retracted", "signal_id": signal_id}

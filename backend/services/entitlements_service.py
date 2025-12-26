"""
Entitlements Engine
Rule-based access control system (BeatVegas as source of truth)
"""
from typing import Optional, Literal, Dict, List, Tuple
from datetime import datetime, timezone
from pymongo.database import Database
from pydantic import BaseModel

from backend.db.schemas.telegram_schemas import (
    UserEntitlements,
    TelegramIntegration,
    TelegramSubscription,
    COLLECTIONS
)


class SubscriptionContext(BaseModel):
    """Aggregated subscription data for entitlement computation"""
    user_id: str
    
    # BeatVegas platform subscription
    beatvegas_tier: Optional[Literal["free", "25k", "50k", "100k"]] = "free"
    beatvegas_active: bool = False
    beatvegas_stripe_sub_id: Optional[str] = None
    
    # Telegram-only subscription ($39/month)
    telegram_only_active: bool = False
    telegram_stripe_sub_id: Optional[str] = None
    
    # Integration status
    telegram_linked: bool = False
    telegram_user_id: Optional[str] = None


class EntitlementsEngine:
    """
    Core entitlements engine
    Implements tier-based access rules
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    # ========================================================================
    # CORE ENTITLEMENT COMPUTATION
    # ========================================================================
    
    async def compute_entitlements(
        self,
        user_id: str,
        recompute_reason: str = "manual"
    ) -> UserEntitlements:
        """
        Compute user entitlements from scratch
        
        Rules:
        1. BeatVegas $25k (free): NO Telegram
        2. BeatVegas $50k ($29.99): NO Telegram  
        3. BeatVegas $100k ($49.99): Telegram signals
        4. BeatVegas Pro ($89.99): Telegram signals + premium
        5. Telegram-only ($39): Telegram signals (no platform access)
        
        Returns:
            UserEntitlements with computed access
        """
        # Fetch subscription context
        ctx = await self._get_subscription_context(user_id)
        
        # Default: no access
        telegram_signals = False
        telegram_premium = False
        
        # Rule evaluation
        if ctx.telegram_only_active:
            # $39 standalone Telegram product
            telegram_signals = True
            telegram_premium = False
        elif ctx.beatvegas_active:
            # BeatVegas platform subscriptions
            if ctx.beatvegas_tier == "100k":  # $49.99
                telegram_signals = True
                telegram_premium = False
            elif ctx.beatvegas_tier == "pro":  # $89.99 (future)
                telegram_signals = True
                telegram_premium = True
            else:
                # Free, 25k, 50k: no Telegram access
                telegram_signals = False
                telegram_premium = False
        
        # Construct entitlements
        entitlements = UserEntitlements(
            user_id=user_id,
            telegram_signals=telegram_signals,
            telegram_premium=telegram_premium,
            beatvegas_tier=ctx.beatvegas_tier,
            beatvegas_subscription_active=ctx.beatvegas_active,
            telegram_only_subscription_active=ctx.telegram_only_active,
            updated_at=datetime.now(timezone.utc),
            last_computed_reason=recompute_reason
        )
        
        # Persist
        await self._save_entitlements(entitlements)
        
        return entitlements
    
    async def _get_subscription_context(self, user_id: str) -> SubscriptionContext:
        """Aggregate all subscription data for a user"""
        ctx = SubscriptionContext(user_id=user_id)
        
        # Check BeatVegas platform subscription
        # (Assumes existing subscriptions collection with tier/status)
        bv_sub = self.db[COLLECTIONS["subscriptions"]].find_one({
            "user_id": user_id,
            "status": {"$in": ["active", "trialing"]}
        })
        
        if bv_sub:
            ctx.beatvegas_active = True
            ctx.beatvegas_tier = bv_sub.get("tier", "free")
            ctx.beatvegas_stripe_sub_id = bv_sub.get("stripe_subscription_id")
        
        # Check Telegram-only subscription
        tg_sub = self.db[COLLECTIONS["telegram_subscriptions"]].find_one({
            "user_id": user_id,
            "status": "active"
        })
        
        if tg_sub:
            ctx.telegram_only_active = True
            ctx.telegram_stripe_sub_id = tg_sub["stripe_subscription_id"]
        
        # Check Telegram integration
        tg_link = self.db[COLLECTIONS["telegram_integrations"]].find_one({
            "user_id": user_id
        })
        
        if tg_link:
            ctx.telegram_linked = True
            ctx.telegram_user_id = tg_link["external_user_id"]
        
        return ctx
    
    async def _save_entitlements(self, entitlements: UserEntitlements):
        """Upsert entitlements to database"""
        self.db[COLLECTIONS["user_entitlements"]].update_one(
            {"user_id": entitlements.user_id},
            {"$set": entitlements.dict()},
            upsert=True
        )
    
    # ========================================================================
    # ENTITLEMENT QUERIES
    # ========================================================================
    
    async def get_entitlements(self, user_id: str) -> Optional[UserEntitlements]:
        """Get cached entitlements (does not recompute)"""
        doc = self.db[COLLECTIONS["user_entitlements"]].find_one(
            {"user_id": user_id}
        )
        return UserEntitlements(**doc) if doc else None
    
    async def has_telegram_access(self, user_id: str) -> bool:
        """Check if user has Telegram signals access"""
        ent = await self.get_entitlements(user_id)
        if not ent:
            # Compute on-the-fly if missing
            ent = await self.compute_entitlements(user_id, "access_check")
        return ent.telegram_signals
    
    async def has_telegram_premium_access(self, user_id: str) -> bool:
        """Check if user has premium Telegram access ($89.99+ tier)"""
        ent = await self.get_entitlements(user_id)
        if not ent:
            ent = await self.compute_entitlements(user_id, "access_check")
        return ent.telegram_premium
    
    # ========================================================================
    # ENTITLEMENT UPDATES (WEBHOOKS)
    # ========================================================================
    
    async def handle_subscription_change(
        self,
        user_id: str,
        event_type: Literal[
            "subscription_created",
            "subscription_updated",
            "subscription_deleted",
            "subscription_paused"
        ],
        subscription_data: Dict
    ) -> Tuple[UserEntitlements, bool]:
        """
        Handle Stripe webhook subscription changes
        
        Returns:
            (entitlements, access_changed)
        """
        # Fetch old entitlements
        old_ent = await self.get_entitlements(user_id)
        old_access = old_ent.telegram_signals if old_ent else False
        
        # Recompute entitlements
        new_ent = await self.compute_entitlements(
            user_id,
            recompute_reason=f"webhook_{event_type}"
        )
        
        # Detect access change
        access_changed = old_access != new_ent.telegram_signals
        
        return new_ent, access_changed
    
    async def handle_telegram_subscription_created(
        self,
        user_id: str,
        telegram_sub_data: Dict
    ) -> UserEntitlements:
        """Handle Telegram-only subscription ($39) purchase"""
        # Store Telegram subscription
        telegram_sub = TelegramSubscription(
            subscription_id=telegram_sub_data["id"],
            user_id=user_id,
            stripe_subscription_id=telegram_sub_data["stripe_subscription_id"],
            tier="telegram_only",
            status=telegram_sub_data.get("status", "active"),
            current_period_start=telegram_sub_data["current_period_start"],
            current_period_end=telegram_sub_data["current_period_end"]
        )
        
        self.db[COLLECTIONS["telegram_subscriptions"]].insert_one(
            telegram_sub.dict()
        )
        
        # Recompute entitlements
        return await self.compute_entitlements(
            user_id,
            recompute_reason="telegram_subscription_created"
        )
    
    # ========================================================================
    # BULK OPERATIONS
    # ========================================================================
    
    async def recompute_all_entitlements(self) -> Dict[str, int]:
        """
        Nightly reconciliation: recompute all user entitlements
        
        Returns:
            Statistics: {total: int, changed: int, errors: int}
        """
        stats = {"total": 0, "changed": 0, "errors": 0}
        
        # Get all users with subscriptions or integrations
        user_ids = set()
        
        # Users with BeatVegas subscriptions
        for sub in list(self.db["subscriptions"].find()):
            user_ids.add(sub["user_id"])
        
        # Users with Telegram subscriptions
        for tg_sub in list(self.db[COLLECTIONS["telegram_subscriptions"]].find()):
            user_ids.add(tg_sub["user_id"])
        
        # Users with Telegram integrations
        for tg_link in list(self.db[COLLECTIONS["telegram_integrations"]].find()):
            user_ids.add(tg_link["user_id"])
        
        # Recompute for each user
        for user_id in user_ids:
            try:
                old_ent = await self.get_entitlements(user_id)
                old_access = old_ent.telegram_signals if old_ent else False
                
                new_ent = await self.compute_entitlements(
                    user_id,
                    recompute_reason="nightly_reconciliation"
                )
                
                stats["total"] += 1
                
                if old_access != new_ent.telegram_signals:
                    stats["changed"] += 1
                    
            except Exception as e:
                print(f"Error recomputing entitlements for {user_id}: {e}")
                stats["errors"] += 1
        
        return stats
    
    # ========================================================================
    # DIAGNOSTICS
    # ========================================================================
    
    async def explain_entitlements(self, user_id: str) -> Dict:
        """
        Diagnostic: explain why user has/doesn't have access
        
        Returns:
            Human-readable explanation with rule evaluation
        """
        ctx = await self._get_subscription_context(user_id)
        ent = await self.get_entitlements(user_id)
        
        explanation = {
            "user_id": user_id,
            "telegram_signals_access": ent.telegram_signals if ent else False,
            "telegram_premium_access": ent.telegram_premium if ent else False,
            "context": {
                "beatvegas_tier": ctx.beatvegas_tier,
                "beatvegas_active": ctx.beatvegas_active,
                "telegram_only_active": ctx.telegram_only_active,
                "telegram_linked": ctx.telegram_linked
            },
            "rules_evaluated": []
        }
        
        # Rule evaluation breakdown
        if ctx.telegram_only_active:
            explanation["rules_evaluated"].append({
                "rule": "Telegram-only subscription ($39)",
                "result": "GRANT telegram_signals"
            })
        elif ctx.beatvegas_active:
            if ctx.beatvegas_tier == "100k":
                explanation["rules_evaluated"].append({
                    "rule": "BeatVegas 100k tier ($49.99)",
                    "result": "GRANT telegram_signals"
                })
            elif ctx.beatvegas_tier in ["free", "25k", "50k"]:
                explanation["rules_evaluated"].append({
                    "rule": f"BeatVegas {ctx.beatvegas_tier} tier",
                    "result": "DENY telegram_signals (requires 100k tier)"
                })
        else:
            explanation["rules_evaluated"].append({
                "rule": "No active subscriptions",
                "result": "DENY all access"
            })
        
        if not ctx.telegram_linked:
            explanation["rules_evaluated"].append({
                "rule": "Telegram not linked",
                "result": "Cannot provision channel access (no external_user_id)"
            })
        
        return explanation


class EntitlementNotifier:
    """Creates access change events for user notifications"""
    
    def __init__(self, db: Database):
        self.db = db
    
    async def create_access_change_event(
        self,
        user_id: str,
        event_type: Literal[
            "telegram_granted",
            "telegram_revoked",
            "telegram_paused"
        ],
        context: Dict
    ):
        """Create in-app notification for access change"""
        from backend.db.schemas.telegram_schemas import AccessChangeEvent
        import uuid
        
        # Generate user-facing message
        if event_type == "telegram_granted":
            title = "Telegram alerts activated!"
            body = "You now have access to BeatVegas Telegram signals."
            cta_url = "/settings/telegram"
            cta_text = "View Telegram settings"
        elif event_type == "telegram_revoked":
            tier = context.get("tier", "25k")
            title = "Telegram alerts paused"
            body = f"You're on the {tier} plan. Telegram requires the 100k plan ($49.99)."
            cta_url = "/billing/upgrade"
            cta_text = "Upgrade to 100k"
        elif event_type == "telegram_paused":
            title = "Telegram subscription paused"
            body = "Your Telegram subscription is past due. Update payment to restore access."
            cta_url = "/billing"
            cta_text = "Update payment"
        else:
            title = "Access updated"
            body = "Your Telegram access has changed."
            cta_url = None
            cta_text = None
        
        event = AccessChangeEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            event_type=event_type,
            message_title=title,
            message_body=body,
            cta_url=cta_url,
            cta_text=cta_text
        )
        
        self.db[COLLECTIONS["access_change_events"]].insert_one(
            event.dict()
        )
        
        return event

"""
Nightly Reconciliation Job
Ensures entitlements and Telegram access are in sync
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "beatvegas")

from backend.services.entitlements_service import EntitlementsEngine
from backend.services.telegram_bot_service import TelegramBotService
from backend.services.signal_generation_service import SignalGenerationEngine
from backend.db.schemas.telegram_schemas import COLLECTIONS, AuditEvent
import uuid


async def reconciliation_job():
    """
    Nightly reconciliation ensures system consistency
    
    Tasks:
    1. Recompute all user entitlements
    2. Sync Telegram channel memberships
    3. Invalidate signals for started games
    4. Archive old signals
    5. Generate reconciliation report
    """
    print(f"[{datetime.now(timezone.utc)}] Starting nightly reconciliation...")
    
    # Connect to database
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    entitlements_engine = EntitlementsEngine(db)
    telegram_service = TelegramBotService(db)
    signal_engine = SignalGenerationEngine(db)
    
    report = {
        "timestamp": datetime.now(timezone.utc),
        "entitlements_recomputed": 0,
        "entitlements_changed": 0,
        "access_granted": 0,
        "access_revoked": 0,
        "signals_invalidated": 0,
        "signals_archived": 0,
        "errors": []
    }
    
    # ========================================================================
    # STEP 1: Recompute all entitlements
    # ========================================================================
    print("Step 1: Recomputing entitlements...")
    try:
        stats = await entitlements_engine.recompute_all_entitlements()
        report["entitlements_recomputed"] = stats["total"]
        report["entitlements_changed"] = stats["changed"]
        print(f"  ✓ Recomputed {stats['total']} users, {stats['changed']} changed")
    except Exception as e:
        report["errors"].append(f"Entitlements recomputation failed: {str(e)}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # STEP 2: Sync Telegram channel memberships
    # ========================================================================
    print("Step 2: Syncing Telegram memberships...")
    try:
        sync_stats = await sync_telegram_memberships(
            db, entitlements_engine, telegram_service
        )
        report["access_granted"] = sync_stats["granted"]
        report["access_revoked"] = sync_stats["revoked"]
        print(f"  ✓ Granted: {sync_stats['granted']}, Revoked: {sync_stats['revoked']}")
    except Exception as e:
        report["errors"].append(f"Telegram sync failed: {str(e)}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # STEP 3: Invalidate signals for started games
    # ========================================================================
    print("Step 3: Invalidating signals for started games...")
    try:
        invalidated = await signal_engine.invalidate_signals_for_started_games()
        report["signals_invalidated"] = invalidated
        print(f"  ✓ Invalidated {invalidated} signals")
    except Exception as e:
        report["errors"].append(f"Signal invalidation failed: {str(e)}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # STEP 4: Archive old signals (30 days)
    # ========================================================================
    print("Step 4: Archiving old signals...")
    try:
        archived = await archive_old_signals(db, days=30)
        report["signals_archived"] = archived
        print(f"  ✓ Archived {archived} signals")
    except Exception as e:
        report["errors"].append(f"Signal archiving failed: {str(e)}")
        print(f"  ✗ Error: {e}")
    
    # ========================================================================
    # STEP 5: Log reconciliation audit event
    # ========================================================================
    audit_event = AuditEvent(
        event_id=f"aud_{uuid.uuid4().hex[:12]}",
        event_type="reconciliation_run",
        payload_snapshot=report,
        triggered_by="cron"
    )
    
    db[COLLECTIONS["audit_events"]].insert_one(audit_event.dict())
    
    print(f"[{datetime.now(timezone.utc)}] Reconciliation complete!")
    print(f"Report: {report}")
    
    # Close database connection
    client.close()
    
    return report


async def sync_telegram_memberships(
    db,
    entitlements_engine: EntitlementsEngine,
    telegram_service: TelegramBotService
) -> Dict[str, int]:
    """
    Sync Telegram channel memberships with entitlements
    
    Logic:
    - If user has telegram_signals=True but no granted membership → grant
    - If user has telegram_signals=False but has granted membership → revoke
    
    Returns:
        {granted: int, revoked: int}
    """
    stats = {"granted": 0, "revoked": 0}
    
    # Get all users with entitlements
    cursor = db[COLLECTIONS["user_entitlements"]].find()
    
    async for ent_doc in cursor:
        user_id = ent_doc["user_id"]
        should_have_access = ent_doc.get("telegram_signals", False)
        
        # Check if user has Telegram linked
        integration = await telegram_service.get_telegram_integration(user_id)
        if not integration:
            continue  # Can't grant/revoke if not linked
        
        # Check current membership status
        membership = await db[COLLECTIONS["telegram_memberships"]].find_one({
            "user_id": user_id,
            "channel_name": "signals",
            "status": "granted"
        })
        
        has_access = membership is not None
        
        # Sync access
        if should_have_access and not has_access:
            # Grant access
            await telegram_service.grant_channel_access(
                user_id=user_id,
                channel_name="signals"
            )
            stats["granted"] += 1
            
        elif not should_have_access and has_access:
            # Revoke access
            await telegram_service.revoke_channel_access(
                user_id=user_id,
                channel_name="signals",
                reason="reconciliation_entitlement_lost"
            )
            stats["revoked"] += 1
    
    return stats


async def archive_old_signals(db, days: int = 30) -> int:
    """Archive signals older than X days"""
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    result = await db[COLLECTIONS["signals"]].update_many(
        {
            "created_at": {"$lt": cutoff},
            "state": {"$in": ["CLOSED", "INVALIDATED_GAME_STARTED", "INVALIDATED_LINE_MOVED"]}
        },
        {
            "$set": {"archived": True}
        }
    )
    
    return result.modified_count


if __name__ == "__main__":
    # Run reconciliation
    asyncio.run(reconciliation_job())

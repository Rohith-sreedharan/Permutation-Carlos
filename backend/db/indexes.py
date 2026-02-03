"""
Database Index Definitions
===========================

Critical indexes for query performance and uniqueness constraints.

Add new indexes here and apply with:
    python backend/db/indexes.py
"""

from typing import List, Dict
from pymongo import ASCENDING, DESCENDING, IndexModel
from backend.db.mongo import db
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# INDEX DEFINITIONS
# ============================================================================

def get_events_indexes() -> List[IndexModel]:
    """Events collection indexes"""
    return [
        # Unique event ID (existing)
        IndexModel(
            [("event_id", ASCENDING)],
            unique=True,
            name="event_id_unique"
        ),
        
        # OddsAPI event ID for exact score lookup (NEW - CRITICAL)
        IndexModel(
            [("provider_event_map.oddsapi.event_id", ASCENDING)],
            sparse=True,  # Some events may not have OddsAPI mapping yet
            name="oddsapi_event_id"
        ),
        
        # Sport + commence time for queries
        IndexModel(
            [("sport_key", ASCENDING), ("commence_time", ASCENDING)],
            name="sport_commence"
        ),
        
        # Active events query
        IndexModel(
            [("completed", ASCENDING), ("commence_time", ASCENDING)],
            name="active_events"
        )
    ]


def get_ai_picks_indexes() -> List[IndexModel]:
    """AI picks collection indexes"""
    return [
        # Unique pick ID (existing)
        IndexModel(
            [("pick_id", ASCENDING)],
            unique=True,
            name="pick_id_unique"
        ),
        
        # Event ID for pick lookup
        IndexModel(
            [("event_id", ASCENDING)],
            name="event_id"
        ),
        
        # User tier for filtering
        IndexModel(
            [("tier", ASCENDING)],
            name="tier"
        ),
        
        # Published picks query
        IndexModel(
            [("published", ASCENDING), ("created_at", DESCENDING)],
            name="published_picks"
        ),
        
        # User picks query
        IndexModel(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            sparse=True,
            name="user_picks"
        )
    ]


def get_grading_indexes() -> List[IndexModel]:
    """Grading collection indexes (NEW - CRITICAL)"""
    return [
        # Unique idempotency key (CRITICAL - v2.0)
        # Format: SHA256(pick_id|grade_source|settlement_rules_version|clv_rules_version)
        IndexModel(
            [("grading_idempotency_key", ASCENDING)],
            unique=True,
            name="grading_idempotency_key_unique"
        ),
        
        # Pick ID for lookup (not unique - can have multiple grades with different rules)
        IndexModel(
            [("pick_id", ASCENDING)],
            name="pick_id"
        ),
        
        # Event ID for bulk grading
        IndexModel(
            [("event_id", ASCENDING)],
            name="event_id"
        ),
        
        # Grading status query
        IndexModel(
            [("settlement_status", ASCENDING), ("graded_at", DESCENDING)],
            name="settlement_status"
        ),
        
        # User performance query
        IndexModel(
            [("user_id", ASCENDING), ("graded_at", DESCENDING)],
            sparse=True,
            name="user_performance"
        ),
        
        # Admin override audit
        IndexModel(
            [("admin_override", ASCENDING)],
            sparse=True,
            name="admin_overrides"
        ),
        
        # Rules versioning queries (for historical replay)
        IndexModel(
            [("settlement_rules_version", ASCENDING), ("clv_rules_version", ASCENDING)],
            name="rules_versions"
        )
    ]


def get_users_indexes() -> List[IndexModel]:
    """Users collection indexes"""
    return [
        # Unique user ID
        IndexModel(
            [("user_id", ASCENDING)],
            unique=True,
            name="user_id_unique"
        ),
        
        # Email lookup
        IndexModel(
            [("email", ASCENDING)],
            unique=True,
            sparse=True,
            name="email_unique"
        ),
        
        # Telegram ID lookup
        IndexModel(
            [("telegram_user_id", ASCENDING)],
            unique=True,
            sparse=True,
            name="telegram_user_id_unique"
        ),
        
        # Subscription tier
        IndexModel(
            [("subscription_tier", ASCENDING)],
            name="subscription_tier"
        )
    ]


def get_simulations_indexes() -> List[IndexModel]:
    """Monte Carlo simulations collection indexes"""
    return [
        # Event ID for simulation lookup
        IndexModel(
            [("event_id", ASCENDING)],
            name="event_id"
        ),
        
        # Created timestamp for recent simulations
        IndexModel(
            [("created_at", DESCENDING)],
            name="created_at"
        ),
        
        # Market type query
        IndexModel(
            [("market_type", ASCENDING), ("created_at", DESCENDING)],
            name="market_type"
        )
    ]


# ============================================================================
# INDEX APPLICATION
# ============================================================================

INDEX_DEFINITIONS = {
    "events": get_events_indexes(),
    "ai_picks": get_ai_picks_indexes(),
    "grading": get_grading_indexes(),
    "users": get_users_indexes(),
    "monte_carlo_simulations": get_simulations_indexes()
}


async def apply_all_indexes(drop_existing: bool = False):
    """
    Apply all index definitions to database.
    
    Args:
        drop_existing: If True, drop existing indexes before creating new ones
                      (DANGEROUS - use only for fresh deploys)
    """
    from backend.db.mongo import db
    
    logger.info("=" * 70)
    logger.info("APPLYING DATABASE INDEXES")
    logger.info("=" * 70)
    
    for collection_name, indexes in INDEX_DEFINITIONS.items():
        logger.info(f"\n📦 Collection: {collection_name}")
        
        collection = db[collection_name]
        
        # Drop existing indexes if requested
        if drop_existing:
            logger.warning(f"  ⚠️  Dropping existing indexes...")
            collection.drop_indexes()
        
        # Create indexes
        logger.info(f"  Creating {len(indexes)} indexes...")
        
        try:
            result = collection.create_indexes(indexes)
            logger.info(f"  ✅ Created indexes: {result}")
        
        except Exception as e:
            logger.error(f"  ❌ Failed to create indexes: {e}")
    
    logger.info("\n" + "=" * 70)
    logger.info("INDEX APPLICATION COMPLETE")
    logger.info("=" * 70)


async def list_all_indexes():
    """List all existing indexes"""
    from backend.db.mongo import db
    
    logger.info("=" * 70)
    logger.info("CURRENT DATABASE INDEXES")
    logger.info("=" * 70)
    
    for collection_name in INDEX_DEFINITIONS.keys():
        logger.info(f"\n📦 Collection: {collection_name}")
        
        collection = db[collection_name]
        indexes = list(collection.list_indexes())
        
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
            if idx.get('unique'):
                logger.info(f"    (UNIQUE)")
            if idx.get('sparse'):
                logger.info(f"    (SPARSE)")


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import asyncio
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage database indexes")
    parser.add_argument("--apply", action="store_true", help="Apply all indexes")
    parser.add_argument("--list", action="store_true", help="List existing indexes")
    parser.add_argument("--drop", action="store_true", help="Drop existing indexes before applying (DANGEROUS)")
    
    args = parser.parse_args()
    
    if args.apply:
        asyncio.run(apply_all_indexes(drop_existing=args.drop))
    elif args.list:
        asyncio.run(list_all_indexes())
    else:
        parser.print_help()

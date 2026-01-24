"""
Cleanup Service - Version-Based Purge
======================================
Deletes simulations by sim_version/build_id, NOT by time.

This prevents:
- "Why is my sim showing old logic?"
- "I fixed the bug but old results still appear"
- Manual database cleanup confusion

Run this after deploying new sim logic.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timezone
from db.mongo import db
from core.sim_integrity import CURRENT_SIM_VERSION, ENGINE_BUILD_ID

logger = logging.getLogger(__name__)


def purge_old_version_simulations(dry_run: bool = True) -> dict:
    """
    Delete simulations from previous engine versions.
    
    Args:
        dry_run: If True, only count without deleting
    
    Returns:
        {
            "deleted_count": int,
            "current_version": int,
            "current_build": str,
            "dry_run": bool
        }
    """
    logger.info(f"🔍 Checking for old-version simulations...")
    logger.info(f"   Current version: {CURRENT_SIM_VERSION}")
    logger.info(f"   Current build: {ENGINE_BUILD_ID}")
    
    # Find simulations with old versions
    query = {
        "$or": [
            # Missing metadata (very old sims)
            {"sim_metadata": {"$exists": False}},
            # Old version number
            {"sim_metadata.sim_version": {"$lt": CURRENT_SIM_VERSION}},
            # Different build ID (optional - commented out for safety)
            # {"sim_metadata.engine_build_id": {"$ne": ENGINE_BUILD_ID}}
        ]
    }
    
    # Count how many would be deleted
    count = db["monte_carlo_simulations"].count_documents(query)
    logger.info(f"📊 Found {count} old-version simulations")
    
    if dry_run:
        logger.info("🔒 DRY RUN MODE - No deletions performed")
        return {
            "deleted_count": 0,
            "found_count": count,
            "current_version": CURRENT_SIM_VERSION,
            "current_build": ENGINE_BUILD_ID,
            "dry_run": True
        }
    
    # Actually delete
    if count > 0:
        logger.warning(f"⚠️ DELETING {count} old-version simulations...")
        result = db["monte_carlo_simulations"].delete_many(query)
        deleted = result.deleted_count
        logger.info(f"✅ Deleted {deleted} old-version simulations")
    else:
        deleted = 0
        logger.info("✅ No old-version simulations to delete")
    
    return {
        "deleted_count": deleted,
        "found_count": count,
        "current_version": CURRENT_SIM_VERSION,
        "current_build": ENGINE_BUILD_ID,
        "dry_run": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def purge_by_build_id(target_build_id: str, dry_run: bool = True) -> dict:
    """
    Delete simulations from a specific engine build.
    
    Use this when rolling back to a previous version.
    
    Args:
        target_build_id: Build ID to delete (e.g., "v1.9.0")
        dry_run: If True, only count without deleting
    
    Returns:
        {
            "deleted_count": int,
            "target_build_id": str,
            "dry_run": bool
        }
    """
    logger.info(f"🔍 Checking for simulations with build_id={target_build_id}")
    
    query = {"sim_metadata.engine_build_id": target_build_id}
    count = db["monte_carlo_simulations"].count_documents(query)
    logger.info(f"📊 Found {count} simulations with build_id={target_build_id}")
    
    if dry_run:
        logger.info("🔒 DRY RUN MODE - No deletions performed")
        return {
            "deleted_count": 0,
            "found_count": count,
            "target_build_id": target_build_id,
            "dry_run": True
        }
    
    # Actually delete
    if count > 0:
        logger.warning(f"⚠️ DELETING {count} simulations with build_id={target_build_id}...")
        result = db["monte_carlo_simulations"].delete_many(query)
        deleted = result.deleted_count
        logger.info(f"✅ Deleted {deleted} simulations")
    else:
        deleted = 0
        logger.info("✅ No matching simulations to delete")
    
    return {
        "deleted_count": deleted,
        "found_count": count,
        "target_build_id": target_build_id,
        "dry_run": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def get_version_distribution() -> dict:
    """
    Show distribution of sim versions in database.
    Useful for understanding cleanup impact.
    
    Returns:
        {
            "total_simulations": int,
            "by_version": {
                "1": count,
                "2": count,
                "missing": count
            },
            "by_build": {
                "v1.9.0": count,
                "v2.0.0-integrity-layer": count,
                "missing": count
            }
        }
    """
    total = db["monte_carlo_simulations"].count_documents({})
    
    # Count by version
    version_pipeline = [
        {
            "$group": {
                "_id": "$sim_metadata.sim_version",
                "count": {"$sum": 1}
            }
        }
    ]
    version_results = list(db["monte_carlo_simulations"].aggregate(version_pipeline))
    by_version = {str(r["_id"]): r["count"] for r in version_results if r["_id"] is not None}
    
    # Count missing metadata
    missing_metadata = db["monte_carlo_simulations"].count_documents({"sim_metadata": {"$exists": False}})
    if missing_metadata > 0:
        by_version["missing"] = missing_metadata
    
    # Count by build ID
    build_pipeline = [
        {
            "$group": {
                "_id": "$sim_metadata.engine_build_id",
                "count": {"$sum": 1}
            }
        }
    ]
    build_results = list(db["monte_carlo_simulations"].aggregate(build_pipeline))
    by_build = {str(r["_id"]): r["count"] for r in build_results if r["_id"] is not None}
    
    if missing_metadata > 0:
        by_build["missing"] = missing_metadata
    
    return {
        "total_simulations": total,
        "current_version": CURRENT_SIM_VERSION,
        "current_build": ENGINE_BUILD_ID,
        "by_version": by_version,
        "by_build": by_build,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Purge old-version simulations")
    parser.add_argument("--execute", action="store_true", help="Actually delete (default is dry-run)")
    parser.add_argument("--stats", action="store_true", help="Show version distribution")
    parser.add_argument("--build-id", type=str, help="Delete specific build ID")
    
    args = parser.parse_args()
    
    if args.stats:
        print("\n📊 SIMULATION VERSION DISTRIBUTION\n")
        stats = get_version_distribution()
        print(f"Total simulations: {stats['total_simulations']}")
        print(f"Current version: {stats['current_version']}")
        print(f"Current build: {stats['current_build']}")
        print("\nBy version:")
        for version, count in sorted(stats['by_version'].items()):
            print(f"  v{version}: {count}")
        print("\nBy build:")
        for build, count in sorted(stats['by_build'].items()):
            print(f"  {build}: {count}")
    
    elif args.build_id:
        print(f"\n🗑️  PURGE BY BUILD ID: {args.build_id}\n")
        result = purge_by_build_id(args.build_id, dry_run=not args.execute)
        print(f"Found: {result['found_count']}")
        print(f"Deleted: {result['deleted_count']}")
        print(f"Dry run: {result['dry_run']}")
    
    else:
        print("\n🗑️  PURGE OLD-VERSION SIMULATIONS\n")
        result = purge_old_version_simulations(dry_run=not args.execute)
        print(f"Current version: {result['current_version']}")
        print(f"Current build: {result['current_build']}")
        print(f"Found: {result['found_count']}")
        print(f"Deleted: {result['deleted_count']}")
        print(f"Dry run: {result['dry_run']}")
        
        if result['dry_run'] and result['found_count'] > 0:
            print("\n⚠️  To actually delete, run with --execute flag")

#!/usr/bin/env python3
"""
Initialize Logging & Calibration System Database
=================================================
Creates all collections and indexes for the logging and calibration system.

Run this once after deployment or when setting up a new environment.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
from db.schemas.logging_calibration_schemas import create_all_indexes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_database():
    """
    Initialize all collections and indexes
    """
    logger.info("=" * 60)
    logger.info("INITIALIZING LOGGING & CALIBRATION SYSTEM DATABASE")
    logger.info("=" * 60)
    
    # Create indexes
    logger.info("\n📦 Creating indexes...")
    create_all_indexes(db)
    
    # Verify collections
    collections = db.list_collection_names()
    
    expected_collections = [
        "events",
        "odds_snapshots",
        "injury_snapshots",
        "sim_runs",
        "sim_run_inputs",
        "predictions",
        "published_predictions",
        "event_results",
        "grading",
        "calibration_versions",
        "calibration_segments",
        "performance_rollups"
    ]
    
    logger.info("\n📊 Verifying collections:")
    for coll in expected_collections:
        exists = coll in collections
        status = "✅" if exists else "⚠️  (will be created on first write)"
        logger.info(f"  {status} {coll}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ DATABASE INITIALIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. Start capturing odds snapshots")
    logger.info("2. Create sim_runs when running simulations")
    logger.info("3. Publish predictions via publishing_service")
    logger.info("4. Grade completed predictions via grading_service")
    logger.info("5. Run weekly calibration jobs via calibration_service")
    logger.info("")


if __name__ == "__main__":
    try:
        initialize_database()
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        sys.exit(1)

"""
Database initialization script for Reality Check Layer (RCL)
Creates indexes for sim_audit and league_total_stats collections
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_rcl_collections():
    """
    Initialize RCL collections and indexes
    """
    logger.info("🔧 Initializing Reality Check Layer (RCL) collections...")
    
    # Create sim_audit indexes
    logger.info("Creating sim_audit indexes...")
    db["sim_audit"].create_index("sim_audit_id", unique=True)
    db["sim_audit"].create_index([("event_id", 1), ("created_at", -1)])
    db["sim_audit"].create_index("simulation_id")
    db["sim_audit"].create_index([("rcl_passed", 1)])
    db["sim_audit"].create_index([("edge_eligible", 1)])
    db["sim_audit"].create_index([("league_code", 1), ("created_at", -1)])
    logger.info("✅ sim_audit indexes created")
    
    # Create league_total_stats indexes
    logger.info("Creating league_total_stats indexes...")
    db["league_total_stats"].create_index("league_code", unique=True)
    db["league_total_stats"].create_index([("updated_at", -1)])
    logger.info("✅ league_total_stats indexes created")
    
    # Verify collections exist
    collections = db.list_collection_names()
    logger.info(f"📊 Available collections: {', '.join(collections)}")
    
    if "sim_audit" in collections:
        count = db["sim_audit"].count_documents({})
        logger.info(f"sim_audit: {count} documents")
    
    if "league_total_stats" in collections:
        count = db["league_total_stats"].count_documents({})
        logger.info(f"league_total_stats: {count} documents")
    
    logger.info("✅ RCL collections initialized successfully")


if __name__ == "__main__":
    init_rcl_collections()

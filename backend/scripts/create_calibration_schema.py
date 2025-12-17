"""
Database Schema for Calibration System
Run this to create required collections and indexes
"""
from db.mongo import db


def create_calibration_collections():
    """
    Create collections for calibration logging
    """
    # Collection 1: pick_audit (every pick decision logged)
    if "pick_audit" not in db.list_collection_names():
        db.create_collection("pick_audit")
        
        # Indexes
        db.pick_audit.create_index([("game_id", 1)])
        db.pick_audit.create_index([("sport", 1), ("timestamp", -1)])
        db.pick_audit.create_index([("market_type", 1)])
        db.pick_audit.create_index([("publish_decision", 1)])
        
        print("✅ Created pick_audit collection")
    
    # Collection 2: calibration_daily (daily aggregate metrics)
    if "calibration_daily" not in db.list_collection_names():
        db.create_collection("calibration_daily")
        
        # Indexes
        db.calibration_daily.create_index([("sport", 1), ("date", -1)])
        db.calibration_daily.create_index([("date", -1)])
        
        print("✅ Created calibration_daily collection")
    
    print("🎯 Calibration database schema ready")


if __name__ == "__main__":
    create_calibration_collections()

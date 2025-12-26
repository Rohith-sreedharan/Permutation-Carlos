"""
Initialize V0 Audit Tables

Convenience script to create audit collections with schemas and indexes.
Safe to run multiple times (idempotent).

Usage:
    python -m scripts.init_audit_tables
    
Environment:
    Requires MONGODB_URI in .env or environment variables
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db
from db.audit_schemas import initialize_audit_collections, verify_audit_collections


def main():
    """Initialize audit tables and verify"""
    print("=" * 80)
    print("V0 AUDIT TABLES INITIALIZATION")
    print("=" * 80)
    print()
    
    # Initialize collections
    print("📦 Creating collections with schemas and indexes...")
    status = initialize_audit_collections(db)
    
    print()
    print("RESULTS:")
    print("-" * 80)
    
    for coll_name, success in status.items():
        icon = "✅" if success else "❌"
        print(f"{icon} {coll_name:25} {'SUCCESS' if success else 'FAILED'}")
    
    print()
    
    # Verify collections
    print("🔍 Verifying collections...")
    verification = verify_audit_collections(db)
    
    print()
    print("VERIFICATION:")
    print("-" * 80)
    
    for coll_name, info in verification.items():
        if info['exists']:
            print(f"✅ {coll_name:25} {info['count']:5} records   {info['indexes']} indexes")
        else:
            print(f"❌ {coll_name:25} DOES NOT EXIST")
    
    print()
    
    # Summary
    success_count = sum(1 for v in status.values() if v)
    total_count = len(status)
    
    print("=" * 80)
    print(f"SUMMARY: {success_count}/{total_count} collections initialized successfully")
    
    if success_count == total_count:
        print("✅ All audit tables ready for logging")
        print()
        print("NEXT STEPS:")
        print("1. Restart backend server to initialize audit logger")
        print("2. Run simulations to test logging")
        print("3. Check collections in MongoDB:")
        print("   db.sim_audit.find().sort({timestamp: -1}).limit(1)")
        print("   db.rcl_log.find().sort({timestamp: -1}).limit(5)")
        print("4. Run weekly calibration after grading:")
        print("   python -m scripts.weekly_calibration --weeks-back 1")
    else:
        print("⚠️  Some collections failed to initialize")
        print("   Check logs above for errors")
        return 1
    
    print("=" * 80)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

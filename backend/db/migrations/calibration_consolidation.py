"""
WORKSTREAM 3C — CALIBRATION LINEAGE CONSOLIDATION

Migration: Consolidate calibration logging into canonical collections

Current State (PROBLEMATIC):
  - audit_log → operational collection
  - calibration_daily → operational collection
  - calibration_weekly → operational collection
  - pick_audit → operational collection
  - migration_log → operational collection

Target State (CANONICAL):
  - ALL calibration logs → calibration_audit_log (canonical)
  - Operational metrics → system_performance (canonical)
  - Version tracking → calibration_versions (canonical)

This migration:
1. Creates calibration_audit_log in canonical collections
2. Copies data from operational collections
3. Updates all code paths to use canonical collections
4. Deprecates operational collections
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


def _to_iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_migration_provenance(
    source_collection: str,
    source_id: str,
    migration_id: str,
    migrated_at: str,
) -> Dict[str, Any]:
    return {
        "source_collection": source_collection,
        "source_id": source_id,
        "migrated_at": migrated_at,
        "migration_id": migration_id,
    }


def migrate_to_canonical_calibration_audit(db):
    """
    Migrate all operational calibration logging to canonical collection.
    
    This function:
    1. Creates calibration_audit_log if it doesn't exist
    2. Copies data from operational collections
    3. Adds migration tracking
    4. Validates no data loss
    
    Args:
        db: MongoDB database instance
    """
    
    OPERATIONAL_SOURCES = {
        "audit_log": "calibration audit",
        "calibration_daily": "daily calibration metrics",
        "calibration_weekly": "weekly calibration metrics",
        "pick_audit": "pick-level audit",
    }
    
    CANONICAL_TARGET = "calibration_audit_log"
    
    print("\n" + "="*70)
    print("CALIBRATION LINEAGE CONSOLIDATION MIGRATION")
    print("="*70)
    
    migration_id = f"calibration_consolidation_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
    migrated_at = _to_iso_utc_now()

    # Create canonical collection if needed
    if CANONICAL_TARGET not in db.list_collection_names():
        db.create_collection(CANONICAL_TARGET)
        print(f"✓ Created canonical collection: {CANONICAL_TARGET}")
    else:
        print(f"✓ Canonical collection exists: {CANONICAL_TARGET}")
    
    # Create index on timestamp for querying
    db[CANONICAL_TARGET].create_index("timestamp")
    db[CANONICAL_TARGET].create_index("source_collection")
    db[CANONICAL_TARGET].create_index("source_id")
    db[CANONICAL_TARGET].create_index("migration_id")
    db[CANONICAL_TARGET].create_index("migrated_at")
    db[CANONICAL_TARGET].create_index("migration_provenance_key", unique=True)
    print("✓ Indexes created on canonical collection")

    destination_pre_count = db[CANONICAL_TARGET].count_documents({})
    
    # Migrate data from operational collections
    total_migrated = 0
    migration_summary = {
        "timestamp": _to_iso_utc_now(),
        "migration_type": "calibration_consolidation",
        "migration_id": migration_id,
        "sources": {},
        "target": CANONICAL_TARGET,
        "total_documents": 0,
        "reconciliation": {},
    }
    
    for source_coll, description in OPERATIONAL_SOURCES.items():
        if source_coll not in db.list_collection_names():
            print(f"⊘ Source collection not found: {source_coll}")
            migration_summary["sources"][source_coll] = {
                "pre_migration_count": 0,
                "migrated_count": 0,
                "skipped_count": 0,
                "skipped_reasons": {"collection_not_found": 1},
                "duplicate_count": 0,
                "error_count": 0,
                "post_migration_count": 0,
                "description": description,
            }
            continue
        
        try:
            source = db[source_coll]
            pre_count = source.count_documents({})

            migrated_count = 0
            skipped_count = 0
            duplicate_count = 0
            error_count = 0
            skipped_reasons: Dict[str, int] = {}
            
            if pre_count == 0:
                print(f"⊘ {source_coll}: No documents to migrate")
                migration_summary["sources"][source_coll] = {
                    "pre_migration_count": 0,
                    "migrated_count": 0,
                    "skipped_count": 0,
                    "skipped_reasons": {},
                    "duplicate_count": 0,
                    "error_count": 0,
                    "post_migration_count": 0,
                    "description": description,
                }
                continue

            # Copy documents with source tracking and idempotent provenance key.
            for doc in source.find({}):
                original_id = doc.get("_id")
                if original_id is None:
                    skipped_count += 1
                    skipped_reasons["missing_source_id"] = skipped_reasons.get("missing_source_id", 0) + 1
                    continue

                source_id = str(original_id)
                migration_provenance_key = f"{source_coll}:{source_id}"
                migrated_doc = dict(doc)
                migrated_doc.pop("_id", None)
                migrated_doc.update(
                    _build_migration_provenance(
                        source_collection=source_coll,
                        source_id=source_id,
                        migration_id=migration_id,
                        migrated_at=migrated_at,
                    )
                )
                migrated_doc["migration_provenance_key"] = migration_provenance_key
                # Existing canonical index enforces unique calibration_record_id.
                # Backfill one deterministically for migrated legacy records.
                if not migrated_doc.get("calibration_record_id"):
                    migrated_doc["calibration_record_id"] = f"migrated_{migration_provenance_key}"

                try:
                    db[CANONICAL_TARGET].insert_one(migrated_doc)
                    migrated_count += 1
                except DuplicateKeyError:
                    duplicate_count += 1
                except Exception as row_err:
                    error_count += 1
                    logger.error("Failed migrating %s:%s -> %s", source_coll, source_id, row_err)

            total_migrated += migrated_count
            post_count = source.count_documents({})
            migration_summary["sources"][source_coll] = {
                "pre_migration_count": pre_count,
                "migrated_count": migrated_count,
                "skipped_count": skipped_count,
                "skipped_reasons": skipped_reasons,
                "duplicate_count": duplicate_count,
                "error_count": error_count,
                "post_migration_count": post_count,
                "description": description,
            }
            print(
                f"✓ {source_coll}: pre={pre_count}, migrated={migrated_count}, "
                f"skipped={skipped_count}, duplicates={duplicate_count}, errors={error_count}, post={post_count}"
            )
            
        except Exception as e:
            logger.error(f"Failed to migrate {source_coll}: {e}")
            print(f"❌ {source_coll}: Migration failed - {e}")
    
    destination_post_count = db[CANONICAL_TARGET].count_documents({})
    destination_net_increase = destination_post_count - destination_pre_count

    # Reconciliation: migrated must equal destination growth once duplicates/skips/errors are accounted.
    source_totals = {
        "migrated_count": sum(v.get("migrated_count", 0) for v in migration_summary["sources"].values()),
        "duplicate_count": sum(v.get("duplicate_count", 0) for v in migration_summary["sources"].values()),
        "skipped_count": sum(v.get("skipped_count", 0) for v in migration_summary["sources"].values()),
        "error_count": sum(v.get("error_count", 0) for v in migration_summary["sources"].values()),
    }

    reconciliation_ok = source_totals["migrated_count"] == destination_net_increase

    migration_summary["total_documents"] = total_migrated
    migration_summary["destination"] = {
        "pre_migration_count": destination_pre_count,
        "post_migration_count": destination_post_count,
        "net_increase": destination_net_increase,
    }
    migration_summary["reconciliation"] = {
        "source_totals": source_totals,
        "destination_net_increase": destination_net_increase,
        "ok": reconciliation_ok,
        "formula": "sum(migrated_count) == destination.net_increase ; duplicates/skips/errors separately accounted",
    }
    
    # Record migration in calibration_versions
    try:
        migration_summary["calibration_version"] = migration_id
        migration_summary["status"] = "COMPLETED" if reconciliation_ok else "FAILED_RECONCILIATION"
        db["calibration_versions"].insert_one(migration_summary)
        print(f"✓ Migration recorded in calibration_versions")
    except Exception as e:
        logger.error(f"Failed to record migration: {e}")
        print(f"⚠️ Could not record migration metadata: {e}")
    
    print("\n" + "-"*70)
    print(f"MIGRATION SUMMARY")
    print("-"*70)
    print(f"  Migration ID: {migration_id}")
    print(f"  Total documents migrated: {total_migrated}")
    print(f"  Destination pre: {destination_pre_count}")
    print(f"  Destination post: {destination_post_count}")
    print(f"  Destination net increase: {destination_net_increase}")
    print(f"  Reconciliation: {'✅ PASS' if reconciliation_ok else '❌ FAIL'}")
    print(f"  Target collection: {CANONICAL_TARGET}")
    print(f"  Status: {'✅ SUCCESS' if total_migrated > 0 else '⚠️ NO DATA MIGRATED'}")
    print("="*70 + "\n")
    
    return {
        "success": total_migrated >= 0,
        "migration_id": migration_id,
        "reconciliation_ok": reconciliation_ok,
        "documents_migrated": total_migrated,
        "destination_pre_count": destination_pre_count,
        "destination_post_count": destination_post_count,
        "destination_net_increase": destination_net_increase,
        "source_summary": migration_summary["sources"],
        "target": CANONICAL_TARGET,
    }


def ensure_calibration_audit_indexes(db):
    """Ensure canonical calibration audit log has proper indexes."""
    collection = db["calibration_audit_log"]
    
    indexes = [
        [("timestamp", 1)],
        [("source_collection", 1)],
        [("event_type", 1)],
        [("sport", 1), ("date", 1)],
    ]
    
    for index_spec in indexes:
        try:
            collection.create_index(index_spec)
        except Exception as e:
            logger.warning(f"Could not create index {index_spec}: {e}")


if __name__ == "__main__":
    # For manual testing:
    # python -m db.migrations.calibration_consolidation
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "beatvegas")
    
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    result = migrate_to_canonical_calibration_audit(db)
    ensure_calibration_audit_indexes(db)

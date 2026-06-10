"""
Phase 4C – Migration: Create truth_dataset_v1 MongoDB View
===========================================================
AC-7 requirement: truth_dataset_v1 view must exist in MongoDB.
The view is the ONLY authorised source for all rollups and calibration
training – no feature may query the raw grading / predictions / events
collections directly for aggregate statistics.

Run this once on a live MongoDB connection:

    python -m backend.db.migrations.phase4_001_truth_dataset_v1_view

Or call  create_view()  programmatically during app startup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# View definition
# ---------------------------------------------------------------------------

VIEW_NAME = "truth_dataset_v1"

# Aggregate pipeline attached to the view.
# Base collection: grading   (one doc per graded publish_id)
PIPELINE: list[dict] = [
    # ── 1. Join published_predictions ──────────────────────────────────────
    {
        "$lookup": {
            "from": "published_predictions",
            "localField": "publish_id",
            "foreignField": "publish_id",
            "as": "_pub",
        }
    },
    {"$unwind": {"path": "$_pub", "preserveNullAndEmptyArrays": False}},
    # Only official publishes count in the truth dataset
    {"$match": {"_pub.is_official": True}},
    # ── 2. Join predictions for model metadata ──────────────────────────────
    {
        "$lookup": {
            "from": "predictions",
            "localField": "_pub.prediction_id",
            "foreignField": "prediction_id",
            "as": "_pred",
        }
    },
    {"$unwind": {"path": "$_pred", "preserveNullAndEmptyArrays": True}},
    # ── 3. Join events for league / teams ───────────────────────────────────
    {
        "$lookup": {
            "from": "events",
            "localField": "_pub.event_id",
            "foreignField": "event_id",
            "as": "_event",
        }
    },
    {"$unwind": {"path": "$_event", "preserveNullAndEmptyArrays": True}},
    # ── 4. Join phase4_decision_records for phase4 classification ───────────
    {
        "$lookup": {
            "from": "phase4_decision_records",
            "localField": "_pub.event_id",
            "foreignField": "event_id",
            "as": "_p4dr",
        }
    },
    # Take first phase4 record if multiple exist (most recent)
    {
        "$addFields": {
            "_p4dr_first": {"$arrayElemAt": ["$_p4dr", 0]}
        }
    },
    # ── 5. Project canonical fields only ────────────────────────────────────
    {
        "$project": {
            "_id": 0,
            "graded_id": 1,
            "publish_id": 1,
            "event_id": "$_pub.event_id",
            # League from event, fallback to published_predictions.league
            "league": {
                "$ifNull": ["$_event.league", "$_pub.league"]
            },
            "market_key": {
                "$ifNull": ["$_pred.market_key", None]
            },
            # recommendation_state: prefer phase4 classification, then prediction field
            "recommendation_state": {
                "$ifNull": [
                    "$_p4dr_first.phase4_decision_class",
                    "$_pred.recommendation_state",
                ]
            },
            "result_code": 1,
            "unit_return": 1,
            # CLV: model_probability - closing_line_implied_probability  (Phase 4 locked formula)
            "clv": 1,
            "brier_score": 1,
            "logloss": 1,
            "calibration_version_used": 1,
            "graded_at": 1,
            "p_win": {"$ifNull": ["$_pred.p_win", None]},
            "p_cover": {"$ifNull": ["$_pred.p_cover", None]},
            "p_over": {"$ifNull": ["$_pred.p_over", None]},
            "edge_points": {"$ifNull": ["$_pred.edge_points", None]},
            "ev_units": {"$ifNull": ["$_pred.ev_units", None]},
            "published_at_utc": "$_pub.published_at_utc",
            "publish_type": "$_pub.publish_type",
            "is_official": "$_pub.is_official",
            # Phase 4 specific classification
            "phase4_decision_class": {
                "$ifNull": ["$_p4dr_first.phase4_decision_class", None]
            },
            "phase4_block_reasons": {
                "$ifNull": ["$_p4dr_first.block_reasons", []]
            },
            # Sim lineage
            "sim_run_id": {"$ifNull": ["$_pred.sim_run_id", None]},
            "calibration_version_applied": {
                "$ifNull": ["$_pred.calibration_version_applied", None]
            },
        }
    },
]


# ---------------------------------------------------------------------------
# Create / replace the view
# ---------------------------------------------------------------------------

def create_view(db=None) -> bool:
    """
    Create (or replace) the truth_dataset_v1 MongoDB view.

    Returns True on success, False if already exists and was left intact.
    Raises on unexpected errors.
    """
    if db is None:
        from db.mongo import db as _db
        db = _db

    # Drop the old view if it exists so we can recreate with latest pipeline
    existing = db.list_collection_names()
    if VIEW_NAME in existing:
        try:
            db.drop_collection(VIEW_NAME)
            logger.info(f"Dropped existing view '{VIEW_NAME}' for recreation")
        except Exception as exc:
            logger.warning(f"Could not drop view '{VIEW_NAME}': {exc}")

    try:
        db.create_collection(
            VIEW_NAME,
            viewOn="grading",
            pipeline=PIPELINE,
        )
        logger.info(f"✅ MongoDB view '{VIEW_NAME}' created successfully")

        # Record migration in migration log
        db["migration_log"].update_one(
            {"migration": "phase4_001_truth_dataset_v1_view"},
            {
                "$setOnInsert": {
                    "migration": "phase4_001_truth_dataset_v1_view",
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                    "view_name": VIEW_NAME,
                    "base_collection": "grading",
                }
            },
            upsert=True,
        )
        return True

    except Exception as exc:
        logger.error(f"❌ Failed to create view '{VIEW_NAME}': {exc}")
        raise


def verify_view(db=None) -> bool:
    """Return True if truth_dataset_v1 exists as a view."""
    if db is None:
        from db.mongo import db as _db
        db = _db

    names = db.list_collection_names()
    if VIEW_NAME not in names:
        return False

    # Confirm it is actually a view (not a regular collection)
    info = db.command("listCollections", filter={"name": VIEW_NAME})
    batch = info.get("cursor", {}).get("firstBatch", [])
    if not batch:
        return False
    return batch[0].get("type") == "view"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_view()
    if verify_view():
        print(f"✅ View '{VIEW_NAME}' verified.")
    else:
        print(f"❌ View '{VIEW_NAME}' NOT verified – check logs.")

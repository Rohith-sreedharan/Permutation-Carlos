"""
No-Touch Production System - Database Schema v2.0
==================================================

Complete schema for BeatVegas production platform.
Implements multi-tenant isolation, entitlements, canonical mapping,
immutable snapshots, pick lifecycle, governance layer.

Author: System
Date: 2026-02-02
Version: v2.0.0 (No-Touch Production)

Schema Conventions:
- All IDs are UUIDs
- All timestamps are UTC
- tenant_id on every tenant-scoped table
- Immutable tables: market_snapshot, raw_payload_blob, audit_log
- Idempotency: billing_ledger.idempotency_key, pick.idempotency_key (UNIQUE)
"""

from pymongo import IndexModel, ASCENDING, DESCENDING
from datetime import datetime
from typing import List, Dict, Any


# ============================================================================
# CORE ENTITIES
# ============================================================================

def get_tenant_indexes() -> List[IndexModel]:
    """
    Tenant table - multi-tenant isolation root
    
    Fields:
    - tenant_id (UUID, PK)
    - name (string)
    - type (CONSUMER | AFFILIATE | B2B | INTERNAL)
    - status (ACTIVE | SUSPENDED)
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("tenant_id", ASCENDING)], unique=True, name="tenant_id_unique"),
        IndexModel([("type", ASCENDING), ("status", ASCENDING)], name="tenant_type_status"),
        IndexModel([("status", ASCENDING)], name="tenant_status")
    ]


def get_user_indexes() -> List[IndexModel]:
    """
    User table - supports both email and Telegram-only users
    
    Fields:
    - user_id (UUID, PK)
    - tenant_id (UUID, FK)
    - email (string, nullable if telegram-only)
    - telegram_user_id (string, nullable, required if email is null)
    - created_at_utc (datetime)
    - status (ACTIVE | SUSPENDED | DELETED)
    
    Constraints:
    - At least one of email or telegram_user_id must be present
    """
    return [
        IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("user_id", ASCENDING)], name="tenant_user"),
        IndexModel([("email", ASCENDING)], unique=True, sparse=True, name="email_unique"),
        IndexModel([("telegram_user_id", ASCENDING)], unique=True, sparse=True, name="telegram_user_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING)], name="tenant_status")
    ]


def get_entitlement_indexes() -> List[IndexModel]:
    """
    Entitlement table (FINAL) - defines access + billing model
    
    Fields:
    - entitlement_id (UUID, PK)
    - tenant_id (UUID, FK)
    - user_id (UUID, FK, nullable if tenant-level)
    - entitlement_type (PAY_PER_USE_BASIC | PAY_PER_USE_PRO | PAY_PER_USE_ADVANCED |
                        SUBSCRIPTION_100K_SIM | B2B_CONTRACT)
    - billing_mode (PAY_PER_USE | SUBSCRIPTION | CONTRACT)
    - included_sim_allowance (int, NULL except 100000 for SUBSCRIPTION_100K_SIM)
    - features (array: must include PARLAY_ARCHITECT for all tiers)
    - starts_at_utc (datetime)
    - ends_at_utc (datetime, nullable for perpetual)
    - source (STRIPE | MANUAL | AFFILIATE | INVOICE)
    - status (ACTIVE | EXPIRED | CANCELED | SUSPENDED)
    """
    return [
        IndexModel([("entitlement_id", ASCENDING)], unique=True, name="entitlement_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("user_id", ASCENDING), ("status", ASCENDING)], 
                   name="tenant_user_status"),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="user_status"),
        IndexModel([("status", ASCENDING), ("ends_at_utc", ASCENDING)], name="status_expiry"),
        IndexModel([("entitlement_type", ASCENDING)], name="entitlement_type")
    ]


def get_rate_limit_policy_indexes() -> List[IndexModel]:
    """
    Rate limit policy - per-tier limits
    
    Fields:
    - policy_id (UUID, PK)
    - tenant_id (UUID, nullable for global defaults)
    - entitlement_type (string)
    - max_requests_per_min (int)
    - max_sim_runs_per_day (int)
    - max_pick_history_days_visible (int)
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("policy_id", ASCENDING)], unique=True, name="policy_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("entitlement_type", ASCENDING)], 
                   unique=True, name="tenant_entitlement_type_unique"),
        IndexModel([("entitlement_type", ASCENDING)], name="entitlement_type")
    ]


def get_billing_ledger_indexes() -> List[IndexModel]:
    """
    Billing ledger - source of truth for charges/allowance
    
    CRITICAL: No action executes unless billing_ledger write succeeds (idempotent).
              If write fails: reject action + emit BILLING_WRITE_FAIL alert.
    
    Fields:
    - ledger_id (UUID, PK)
    - tenant_id (UUID, FK)
    - user_id (UUID, FK)
    - action_type (SIM_RUN | PARLAY_GEN | REFRESH | DIAGNOSTIC | EXPORT | OTHER)
    - pick_id (UUID, nullable)
    - event_id (UUID, nullable)
    - amount_credits (int, for PAY_PER_USE tiers)
    - amount_allowance (int, for SUBSCRIPTION tiers)
    - currency (string, nullable)
    - price_cents (int, nullable)
    - idempotency_key (string, UNIQUE)
    - status (APPLIED | REVERSED | FAILED)
    - created_at_utc (datetime)
    - metadata_json (JSON)
    """
    return [
        IndexModel([("ledger_id", ASCENDING)], unique=True, name="ledger_id_unique"),
        IndexModel([("idempotency_key", ASCENDING)], unique=True, name="ledger_idempotency_key_unique"),
        IndexModel([("tenant_id", ASCENDING), ("user_id", ASCENDING), ("created_at_utc", DESCENDING)],
                   name="tenant_user_created"),
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING), ("created_at_utc", DESCENDING)],
                   name="user_status_created"),
        IndexModel([("action_type", ASCENDING), ("status", ASCENDING)], name="action_status"),
        IndexModel([("pick_id", ASCENDING)], sparse=True, name="pick_id")
    ]


# ============================================================================
# CANONICAL MAPPING (Sports Data)
# ============================================================================

def get_team_indexes() -> List[IndexModel]:
    """
    Team table - canonical team records
    
    Fields:
    - team_id (UUID, PK)
    - league (string: NBA, NFL, MLB, NHL, etc.)
    - team_name (string)
    - abbreviation (string)
    - source_team_map (JSON: {source: source_team_id})
    - created_at_utc (datetime)
    - updated_at_utc (datetime)
    """
    return [
        IndexModel([("team_id", ASCENDING)], unique=True, name="team_id_unique"),
        IndexModel([("league", ASCENDING), ("team_name", ASCENDING)], unique=True, name="league_team_unique"),
        IndexModel([("league", ASCENDING), ("abbreviation", ASCENDING)], name="league_abbrev"),
        IndexModel([("source_team_map.oddsapi", ASCENDING)], sparse=True, name="oddsapi_team_id")
    ]


def get_event_indexes() -> List[IndexModel]:
    """
    Event table - canonical game records
    
    CRITICAL: Must store provider IDs for deterministic grading.
              oddsapi_event_id is REQUIRED when OddsAPI is active.
    
    Fields:
    - event_id (UUID, PK)
    - league (string)
    - home_team_id (UUID, FK to team)
    - away_team_id (UUID, FK to team)
    - start_time_utc (datetime)
    - status (SCHEDULED | LIVE | FINAL | POSTPONED | CANCELED)
    - source_event_map (JSON: {source: source_event_id})
    - oddsapi_event_id (string, required for OddsAPI)
    - created_at_utc (datetime)
    - updated_at_utc (datetime)
    """
    return [
        IndexModel([("event_id", ASCENDING)], unique=True, name="event_id_unique"),
        IndexModel([("league", ASCENDING), ("start_time_utc", ASCENDING)], name="league_start_time"),
        IndexModel([("status", ASCENDING), ("start_time_utc", ASCENDING)], name="status_start_time"),
        IndexModel([("oddsapi_event_id", ASCENDING)], unique=True, sparse=True, name="oddsapi_event_id_unique"),
        IndexModel([("source_event_map.oddsapi", ASCENDING)], sparse=True, name="oddsapi_event_map"),
        IndexModel([("home_team_id", ASCENDING)], name="home_team_id"),
        IndexModel([("away_team_id", ASCENDING)], name="away_team_id")
    ]


def get_selection_indexes() -> List[IndexModel]:
    """
    Selection table - canonical bettable sides (prevents inversion)
    
    Deterministic selection creation:
    - SPREAD: HOME, AWAY
    - ML: HOME, AWAY
    - TOTAL: OVER, UNDER
    - PROP: Player prop sides (future)
    
    Fields:
    - selection_id (UUID, PK)
    - event_id (UUID, FK)
    - market_type (SPREAD | ML | TOTAL | PROP)
    - team_id (UUID, FK, nullable for totals)
    - side (HOME | AWAY | OVER | UNDER | PLAYER_PROP_SIDE)
    - label_template (string: "{team} {line}" / "Over {line}")
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("selection_id", ASCENDING)], unique=True, name="selection_id_unique"),
        IndexModel([("event_id", ASCENDING), ("market_type", ASCENDING), ("side", ASCENDING)],
                   unique=True, name="event_market_side_unique"),
        IndexModel([("event_id", ASCENDING), ("market_type", ASCENDING)], name="event_market"),
        IndexModel([("team_id", ASCENDING)], sparse=True, name="team_id")
    ]


# ============================================================================
# MARKET DATA & SNAPSHOTS (Immutable)
# ============================================================================

def get_market_snapshot_indexes() -> List[IndexModel]:
    """
    Market snapshot - IMMUTABLE market state
    
    CRITICAL: Never update. Create new snapshot instead.
    
    Fields:
    - snapshot_id (UUID, PK)
    - source (ODDSAPI | BETFAIR | SPORTRADAR | SPORTSDATAIO | CUSTOM)
    - league (string)
    - event_id (UUID, FK)
    - source_event_id (string, vendor ID)
    - market_type (SPREAD | ML | TOTAL | PROP)
    - selection_id (UUID, FK)
    - book_key (string, nullable)
    - exchange_market_id (string, nullable)
    - line (float, nullable)
    - odds_american (int)
    - timestamp_utc (datetime)
    - staleness_seconds (int)
    - consensus_line (float, nullable)
    - consensus_odds_american (int, nullable)
    - raw_payload_ref (string, FK to raw_payload_blob)
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("snapshot_id", ASCENDING)], unique=True, name="snapshot_id_unique"),
        IndexModel([("event_id", ASCENDING), ("market_type", ASCENDING), ("timestamp_utc", DESCENDING)],
                   name="event_market_time"),
        IndexModel([("selection_id", ASCENDING), ("timestamp_utc", DESCENDING)], name="selection_time"),
        IndexModel([("source", ASCENDING), ("league", ASCENDING), ("created_at_utc", DESCENDING)],
                   name="source_league_created"),
        IndexModel([("raw_payload_ref", ASCENDING)], name="raw_payload_ref"),
        IndexModel([("staleness_seconds", ASCENDING)], name="staleness")
    ]


def get_raw_payload_blob_indexes() -> List[IndexModel]:
    """
    Raw payload blob - IMMUTABLE vendor payloads (for replay/backfill)
    
    Fields:
    - raw_payload_ref (string, PK)
    - source (ODDSAPI | etc.)
    - payload_json (JSON blob)
    - captured_at_utc (datetime)
    """
    return [
        IndexModel([("raw_payload_ref", ASCENDING)], unique=True, name="raw_payload_ref_unique"),
        IndexModel([("source", ASCENDING), ("captured_at_utc", DESCENDING)], name="source_captured")
    ]


# ============================================================================
# SIMULATION & MODEL OUTPUTS
# ============================================================================

def get_simulation_run_indexes() -> List[IndexModel]:
    """
    Simulation run - model execution metadata
    
    Fields:
    - sim_run_id (UUID, PK)
    - tenant_id (UUID, FK)
    - league (string)
    - event_id (UUID, FK)
    - market_type (string)
    - model_version (string)
    - data_version (string)
    - sim_config_hash (string)
    - sim_count (int: 100K public / 1M internal)
    - run_at_utc (datetime)
    - outputs_ref (string, blob ref)
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("sim_run_id", ASCENDING)], unique=True, name="sim_run_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("event_id", ASCENDING), ("market_type", ASCENDING)],
                   name="tenant_event_market"),
        IndexModel([("event_id", ASCENDING), ("model_version", ASCENDING), ("data_version", ASCENDING)],
                   name="event_version_boundary"),
        IndexModel([("model_version", ASCENDING), ("data_version", ASCENDING), ("sim_config_hash", ASCENDING)],
                   name="version_boundary")
    ]


def get_market_evaluation_indexes() -> List[IndexModel]:
    """
    Market evaluation - model output vs snapshot
    
    Fields:
    - eval_id (UUID, PK)
    - sim_run_id (UUID, FK)
    - snapshot_id (UUID, FK)
    - fair_line (float, nullable)
    - fair_odds_american (int, nullable)
    - edge_points (float)
    - edge_prob (float)
    - volatility_score (float)
    - confidence_score (float)
    - risk_flags (array)
    - created_at_utc (datetime)
    """
    return [
        IndexModel([("eval_id", ASCENDING)], unique=True, name="eval_id_unique"),
        IndexModel([("sim_run_id", ASCENDING), ("snapshot_id", ASCENDING)], 
                   unique=True, name="sim_snapshot_unique"),
        IndexModel([("snapshot_id", ASCENDING)], name="snapshot_id")
    ]


# ============================================================================
# PICKS (Single Source of Truth)
# ============================================================================

def get_pick_indexes() -> List[IndexModel]:
    """
    Pick table - SINGLE SOURCE OF TRUTH for recommendations
    
    CRITICAL:
    - UI and Telegram output MUST be generated from pick_id only
    - model_preference.selection_id MUST equal model_direction.selection_id
    - If mismatch: reject + emit DIRECTION_MISMATCH alert
    
    State machine (enforced):
    PROPOSED → PUBLISHED → (MOVED | INVALIDATED | REFRESH_RECOMMENDED) → GRADED
    
    Fields:
    - pick_id (UUID, PK)
    - tenant_id (UUID, FK)
    - event_id (UUID, FK)
    - market_type (string)
    - selection_id (UUID, FK)
    - market_snapshot_id (UUID, FK, publish snapshot)
    - model_version (string)
    - data_version (string)
    - sim_config_hash (string)
    - config_version_id (UUID, FK)
    - tier (EDGE | LEAN | MARKET_ALIGNED | BLOCKED)
    - status (PROPOSED | PUBLISHED | MOVED | INVALIDATED | REFRESH_RECOMMENDED | GRADED)
    - validity_state (VALID | MOVED_BUT_OK | INVALIDATED | REFRESH_RECOMMENDED)
    - validity_reason (enum string)
    - edge_points (float)
    - edge_prob (float)
    - confidence_score (float)
    - volatility_score (float)
    - risk_flags (array)
    - published_to (APP | TELEGRAM | BOTH | NONE)
    - published_at_utc (datetime, nullable)
    - expires_at_utc (datetime, nullable)
    - idempotency_key (string, UNIQUE)
    - pick_version (int, default 1)
    - supersedes_pick_id (UUID, nullable)
    - telegram_message_id (string, nullable)
    - ui_contract_version (string)
    - created_at_utc (datetime)
    - updated_at_utc (datetime)
    """
    return [
        IndexModel([("pick_id", ASCENDING)], unique=True, name="pick_id_unique"),
        IndexModel([("idempotency_key", ASCENDING)], unique=True, name="pick_idempotency_key_unique"),
        IndexModel([("tenant_id", ASCENDING), ("status", ASCENDING), ("published_at_utc", DESCENDING)],
                   name="tenant_status_published"),
        IndexModel([("event_id", ASCENDING), ("market_type", ASCENDING), ("status", ASCENDING)],
                   name="event_market_status"),
        IndexModel([("tier", ASCENDING), ("status", ASCENDING)], name="tier_status"),
        IndexModel([("status", ASCENDING), ("validity_state", ASCENDING)], name="status_validity"),
        IndexModel([("supersedes_pick_id", ASCENDING)], sparse=True, name="supersedes"),
        IndexModel([("telegram_message_id", ASCENDING)], sparse=True, name="telegram_message_id"),
        IndexModel([("model_version", ASCENDING), ("data_version", ASCENDING), ("sim_config_hash", ASCENDING)],
                   name="version_boundary")
    ]


def get_pick_line_tracking_indexes() -> List[IndexModel]:
    """
    Pick line tracking - CLV computation
    
    Fields:
    - pick_id (UUID, PK/FK)
    - open_snapshot_id (UUID, FK)
    - best_snapshot_id (UUID, FK)
    - close_snapshot_id (UUID, FK)
    - open_line (float)
    - open_odds_american (int)
    - best_line (float)
    - best_odds_american (int)
    - close_line (float)
    - close_odds_american (int)
    - clv_value (float)
    - clv_direction (FAVORABLE | UNFAVORABLE | NEUTRAL)
    - updated_at_utc (datetime)
    """
    return [
        IndexModel([("pick_id", ASCENDING)], unique=True, name="pick_id_unique"),
        IndexModel([("clv_direction", ASCENDING), ("clv_value", DESCENDING)], name="clv_direction_value")
    ]


def get_grading_indexes() -> List[IndexModel]:
    """
    Grading table - pick outcomes
    
    Note: This integrates with existing unified_grading_service_v2
    
    Fields:
    - pick_id (UUID, PK/FK)
    - result (WIN | LOSS | PUSH | VOID)
    - score_home (int)
    - score_away (int)
    - grade_source (enum)
    - graded_at_utc (datetime)
    - reconciliation_flags (array)
    """
    return [
        IndexModel([("pick_id", ASCENDING)], unique=True, name="pick_id_unique"),
        IndexModel([("result", ASCENDING), ("graded_at_utc", DESCENDING)], name="result_graded"),
        IndexModel([("graded_at_utc", DESCENDING)], name="graded_at")
    ]


# ============================================================================
# GOVERNANCE & AUDIT
# ============================================================================

def get_audit_log_indexes() -> List[IndexModel]:
    """
    Audit log - APPEND-ONLY immutable trail
    
    Fields:
    - audit_id (UUID, PK)
    - entity_type (PICK | SNAPSHOT | GRADING | ENTITLEMENT | CONFIG | FLAG | BILLING_LEDGER)
    - entity_id (UUID)
    - action (CREATE | UPDATE | SUPERSEDE | INVALIDATE | GRADE | DISABLE | ENABLE | APPLY | REVERSE)
    - before_state_hash (string, nullable)
    - after_state_hash (string)
    - actor (SYSTEM | USER | ADMIN | JOB)
    - reason_code (string)
    - timestamp_utc (datetime)
    """
    return [
        IndexModel([("audit_id", ASCENDING)], unique=True, name="audit_id_unique"),
        IndexModel([("entity_type", ASCENDING), ("entity_id", ASCENDING), ("timestamp_utc", DESCENDING)],
                   name="entity_timeline"),
        IndexModel([("actor", ASCENDING), ("timestamp_utc", DESCENDING)], name="actor_timeline"),
        IndexModel([("timestamp_utc", DESCENDING)], name="timestamp")
    ]


def get_config_version_indexes() -> List[IndexModel]:
    """
    Config version - version league configs
    
    Fields:
    - config_version_id (UUID, PK)
    - tenant_id (UUID, nullable for global)
    - league (string)
    - effective_from_utc (datetime)
    - config_hash (string)
    - previous_config_version_id (UUID, nullable)
    - config_json (JSON)
    """
    return [
        IndexModel([("config_version_id", ASCENDING)], unique=True, name="config_version_id_unique"),
        IndexModel([("tenant_id", ASCENDING), ("league", ASCENDING), ("effective_from_utc", DESCENDING)],
                   name="tenant_league_effective"),
        IndexModel([("config_hash", ASCENDING)], name="config_hash")
    ]


def get_ops_alert_indexes() -> List[IndexModel]:
    """
    Ops alert - operational monitoring
    
    Required types:
    - FEED_STALE, SIM_FAIL, PUBLISH_DUPLICATE, GRADING_LAG
    - DIRECTION_MISMATCH, MAPPING_DRIFT, ROI_ANOMALY, CALIBRATION_DRIFT
    - BILLING_WRITE_FAIL, INTEGRITY_VIOLATION, etc.
    
    Fields:
    - alert_id (UUID, PK)
    - severity (INFO | WARN | CRIT)
    - type (enum)
    - tenant_id (UUID, nullable)
    - payload_json (JSON)
    - created_at_utc (datetime)
    - ack_at_utc (datetime, nullable)
    """
    return [
        IndexModel([("alert_id", ASCENDING)], unique=True, name="alert_id_unique"),
        IndexModel([("severity", ASCENDING), ("created_at_utc", DESCENDING)], name="severity_created"),
        IndexModel([("type", ASCENDING), ("created_at_utc", DESCENDING)], name="type_created"),
        IndexModel([("ack_at_utc", ASCENDING)], sparse=True, name="ack_at"),
        IndexModel([("tenant_id", ASCENDING), ("created_at_utc", DESCENDING)], name="tenant_created")
    ]


def get_feature_flag_indexes() -> List[IndexModel]:
    """
    Feature flag - runtime behavior control
    
    Required flags:
    - PUBLISH_ENABLED_GLOBAL, PUBLISH_ENABLED_TELEGRAM, PUBLISH_ENABLED_APP
    - GRADING_ENABLED, SIM_ENABLED
    - LEAGUE_ENABLED_{league}, MARKET_ENABLED_{market}
    
    Fields:
    - flag_key (string, PK)
    - scope (GLOBAL | TENANT | LEAGUE | MARKET)
    - scope_id (string, nullable)
    - enabled (bool)
    - updated_at_utc (datetime)
    """
    return [
        IndexModel([("flag_key", ASCENDING)], unique=True, name="flag_key_unique"),
        IndexModel([("scope", ASCENDING), ("scope_id", ASCENDING)], name="scope_id"),
        IndexModel([("enabled", ASCENDING)], name="enabled")
    ]


# ============================================================================
# ANALYTICS & DATA MOAT
# ============================================================================

def get_analytics_event_fact_indexes() -> List[IndexModel]:
    """
    Analytics event fact - daily rollups
    
    Fields:
    - date (date)
    - league (string)
    - market_type (string)
    - tier (string)
    - bet_count (int)
    - win_rate (float)
    - roi_units (float)
    - avg_edge_points (float)
    - avg_edge_prob (float)
    - avg_clv (float)
    - clv_hit_rate (float)
    - invalidation_rate (float)
    - refresh_rate (float)
    - calibration_brier (float)
    - calibration_bins (JSON)
    """
    return [
        IndexModel([("date", DESCENDING), ("league", ASCENDING), ("market_type", ASCENDING)],
                   unique=True, name="date_league_market_unique"),
        IndexModel([("tier", ASCENDING), ("date", DESCENDING)], name="tier_date"),
        IndexModel([("league", ASCENDING), ("date", DESCENDING)], name="league_date")
    ]


def get_data_products_catalog_indexes() -> List[IndexModel]:
    """
    Data products catalog - B2B data products
    
    Fields:
    - dataset_id (UUID, PK)
    - name (string)
    - description (string)
    - access_level_required (string)
    - query_templates (JSON)
    - materialized_pointers (JSON)
    """
    return [
        IndexModel([("dataset_id", ASCENDING)], unique=True, name="dataset_id_unique"),
        IndexModel([("access_level_required", ASCENDING)], name="access_level")
    ]


# ============================================================================
# COLLECTION DEFINITIONS
# ============================================================================

COLLECTIONS = {
    # Core entities
    "tenant": get_tenant_indexes(),
    "user": get_user_indexes(),
    "entitlement": get_entitlement_indexes(),
    "rate_limit_policy": get_rate_limit_policy_indexes(),
    "billing_ledger": get_billing_ledger_indexes(),
    
    # Canonical mapping
    "team": get_team_indexes(),
    "event": get_event_indexes(),
    "selection": get_selection_indexes(),
    
    # Market data & snapshots
    "market_snapshot": get_market_snapshot_indexes(),
    "raw_payload_blob": get_raw_payload_blob_indexes(),
    
    # Simulation & model
    "simulation_run": get_simulation_run_indexes(),
    "market_evaluation": get_market_evaluation_indexes(),
    
    # Picks
    "pick": get_pick_indexes(),
    "pick_line_tracking": get_pick_line_tracking_indexes(),
    "grading": get_grading_indexes(),
    
    # Governance & ops
    "audit_log": get_audit_log_indexes(),
    "config_version": get_config_version_indexes(),
    "ops_alert": get_ops_alert_indexes(),
    "feature_flag": get_feature_flag_indexes(),
    
    # Analytics
    "analytics_event_fact": get_analytics_event_fact_indexes(),
    "data_products_catalog": get_data_products_catalog_indexes()
}


def create_all_indexes(db):
    """
    Create all indexes for No-Touch Production System
    
    Usage:
        from backend.db.mongo import get_db
        from backend.db.schema_v2 import create_all_indexes
        
        db = get_db()
        create_all_indexes(db)
    """
    for collection_name, indexes in COLLECTIONS.items():
        print(f"Creating indexes for {collection_name}...")
        db[collection_name].create_indexes(indexes)
        print(f"✅ {collection_name}: {len(indexes)} indexes created")
    
    print(f"\n✅ Total: {len(COLLECTIONS)} collections indexed")


def drop_all_indexes(db):
    """Drop all non-_id indexes (for migration rollback)"""
    for collection_name in COLLECTIONS.keys():
        print(f"Dropping indexes for {collection_name}...")
        db[collection_name].drop_indexes()
        print(f"✅ {collection_name}: indexes dropped")


if __name__ == "__main__":
    from backend.db.mongo import db
    
    print("=" * 60)
    print("NO-TOUCH PRODUCTION SYSTEM - Schema v2.0")
    print("=" * 60)
    print()
    
    create_all_indexes(db)
    
    print()
    print("=" * 60)
    print("Schema deployment complete ✅")
    print("=" * 60)

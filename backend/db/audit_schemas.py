"""
BeatVegas Audit Table Schemas — FINAL APPROVED SPECIFICATION

Version: Final | Retention: 7 Years | Audit Ready: Yes

Defines MongoDB collection schemas and indexes for regulatory compliance and audit logging.
These tables accumulate historical data for transparency, grading, and legal audits.

Collections:
- sim_audit: Every simulation batch for transparency, grading, and audits (7-year retention)
- bet_history: User bets, CLV, and profitability tracking (7-year retention)
- rcl_log: Reality Check Logic evaluation logs (7-year retention)
- calibration_weekly: Weekly model calibration metrics (7-year retention)

Compliance Requirements:
- 7-year cold storage retention (all tables)
- Immutable audit logs (no destructive updates)
- JSON logging compatibility
- Index on: game_id, sport, timestamp

Developer Handoff Document Approved: December 20, 2025
"""

from typing import Dict, Any
from datetime import datetime, timezone
from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING, IndexModel
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

def get_sim_audit_schema() -> Dict[str, Any]:
    """
    Schema for simulation audit trail
    
    Purpose: Stores every simulation batch for transparency, grading, and audits.
    Retention: 7 years
    Audit-Ready: YES
    
    Fields:
    - game_id (STRING) — Unique game identifier
    - sport (STRING) — nba / nfl / ncaaf / ncaab / mlb / nhl
    - sim_count (INT) — Number of simulations run (10K–100K)
    - vegas_line (FLOAT) — Sportsbook line at time of simulation
    - model_total (FLOAT) — Model projected median/mean total or spread
    - stddev (FLOAT) — Simulation distribution standard deviation
    - rcl_passed (BOOLEAN) — Whether Reality Check Logic passed
    - edge_flagged (BOOLEAN) — Whether mispricing was detected
    - actual_result (FLOAT) — Final game result for grading
    """
    return {
        'validator': {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['game_id', 'sport', 'sim_count', 'vegas_line', 'model_total', 'stddev', 'rcl_passed', 'edge_flagged'],
                'properties': {
                    # Required fields
                    'game_id': {
                        'bsonType': 'string',
                        'description': 'Unique game identifier'
                    },
                    'sport': {
                        'bsonType': 'string',
                        'enum': ['nba', 'nfl', 'ncaaf', 'ncaab', 'mlb', 'nhl'],
                        'description': 'Sport key'
                    },
                    'sim_count': {
                        'bsonType': 'int',
                        'minimum': 10000,
                        'maximum': 100000,
                        'description': 'Number of simulations run (10K-100K)'
                    },
                    'vegas_line': {
                        'bsonType': 'double',
                        'description': 'Sportsbook line at time of simulation'
                    },
                    'model_total': {
                        'bsonType': 'double',
                        'description': 'Model projected median/mean total or spread'
                    },
                    'stddev': {
                        'bsonType': 'double',
                        'description': 'Simulation distribution standard deviation'
                    },
                    'rcl_passed': {
                        'bsonType': 'bool',
                        'description': 'Whether Reality Check Logic passed'
                    },
                    'edge_flagged': {
                        'bsonType': 'bool',
                        'description': 'Whether mispricing was detected'
                    },
                    
                    # Grading field (populated after game ends)
                    'actual_result': {
                        'bsonType': 'double',
                        'description': 'Final game result for grading (populated post-game)'
                    },
                    
                    # Metadata for compliance
                    'timestamp': {
                        'bsonType': 'date',
                        'description': 'Simulation creation timestamp'
                    },
                    'retention_date': {
                        'bsonType': 'date',
                        'description': '7-year retention expiration date'
                    },
                    'immutable': {
                        'bsonType': 'bool',
                        'description': 'Audit log immutability flag (always true)'
                    }
                }
            }
        }
    }


def get_bet_history_schema() -> Dict[str, Any]:
    """
    Schema for bet history tracking
    
    Purpose: Tracks user bets, CLV, and profitability.
    Retention: 7 years
    Audit-Ready: YES
    
    Fields:
    - user_id (STRING) — Internal BeatVegas user identifier
    - game_id (STRING) — Linked game
    - odds (FLOAT) — Odds at bet time
    - closing_odds (FLOAT) — Closing sportsbook odds
    - clv (FLOAT) — Closing Line Value (closing_odds - odds)
    - profit (FLOAT) — Profit or loss from bet
    """
    return {
        'validator': {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['user_id', 'game_id', 'odds', 'closing_odds', 'clv', 'profit'],
                'properties': {
                    # Required fields
                    'user_id': {
                        'bsonType': 'string',
                        'description': 'Internal BeatVegas user identifier'
                    },
                    'game_id': {
                        'bsonType': 'string',
                        'description': 'Linked game identifier'
                    },
                    'odds': {
                        'bsonType': 'double',
                        'description': 'Odds at bet placement time (American odds)'
                    },
                    'closing_odds': {
                        'bsonType': 'double',
                        'description': 'Closing sportsbook odds'
                    },
                    'clv': {
                        'bsonType': 'double',
                        'description': 'Closing Line Value (closing_odds - odds)'
                    },
                    'profit': {
                        'bsonType': 'double',
                        'description': 'Profit or loss from bet'
                    },
                    
                    # Metadata for compliance
                    'timestamp': {
                        'bsonType': 'date',
                        'description': 'Bet placement timestamp'
                    },
                    'sport': {
                        'bsonType': 'string',
                        'description': 'Sport key for indexing'
                    },
                    'retention_date': {
                        'bsonType': 'date',
                        'description': '7-year retention expiration date'
                    },
                    'immutable': {
                        'bsonType': 'bool',
                        'description': 'Audit log immutability flag (always true)'
                    }
                }
            }
        }
    }


def get_rcl_log_schema() -> Dict[str, Any]:
    """
    Schema for RCL (Reality Check Logic) logs
    
    Purpose: Logs every Reality Check Logic evaluation for transparency and debugging.
    Retention: 7 years
    Audit-Ready: YES
    
    Fields:
    - game_id (STRING) — Game evaluated
    - rcl_passed (BOOLEAN) — Pass/fail status
    - rcl_reason (TEXT) — Explanation for the evaluation result
    - timestamp (TIMESTAMP) — When RCL was evaluated
    """
    return {
        'validator': {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['game_id', 'rcl_passed', 'rcl_reason', 'timestamp'],
                'properties': {
                    # Required fields
                    'game_id': {
                        'bsonType': 'string',
                        'description': 'Game evaluated'
                    },
                    'rcl_passed': {
                        'bsonType': 'bool',
                        'description': 'Pass/fail status'
                    },
                    'rcl_reason': {
                        'bsonType': 'string',
                        'description': 'Explanation for the evaluation result'
                    },
                    'timestamp': {
                        'bsonType': 'date',
                        'description': 'When RCL was evaluated'
                    },
                    
                    # Additional metadata
                    'sport': {
                        'bsonType': 'string',
                        'description': 'Sport key for indexing'
                    },
                    'retention_date': {
                        'bsonType': 'date',
                        'description': '7-year retention expiration date'
                    },
                    'immutable': {
                        'bsonType': 'bool',
                        'description': 'Audit log immutability flag (always true)'
                    }
                }
            }
        }
    }


def get_calibration_weekly_schema() -> Dict[str, Any]:
    """
    Schema for weekly calibration metrics
    
    Purpose: Stores weekly model calibration metrics.
    Retention: 7 years
    Audit-Ready: YES
    
    Fields:
    - sport (STRING) — nba / nfl / etc.
    - win_rate (FLOAT) — Weekly accuracy percent
    - brier_score (FLOAT) — Calibration score (lower = better)
    - std_dev (FLOAT) — Distribution deviation
    - n_games (INT) — Number of games in calibration sample
    """
    return {
        'validator': {
            '$jsonSchema': {
                'bsonType': 'object',
                'required': ['sport', 'win_rate', 'brier_score', 'std_dev', 'n_games'],
                'properties': {
                    # Required fields
                    'sport': {
                        'bsonType': 'string',
                        'enum': ['nba', 'nfl', 'ncaaf', 'ncaab', 'mlb', 'nhl'],
                        'description': 'Sport key'
                    },
                    'win_rate': {
                        'bsonType': 'double',
                        'minimum': 0.0,
                        'maximum': 1.0,
                        'description': 'Weekly accuracy percent (0.0 - 1.0)'
                    },
                    'brier_score': {
                        'bsonType': 'double',
                        'description': 'Calibration score (lower = better)'
                    },
                    'std_dev': {
                        'bsonType': 'double',
                        'description': 'Distribution deviation'
                    },
                    'n_games': {
                        'bsonType': 'int',
                        'minimum': 0,
                        'description': 'Number of games in calibration sample'
                    },
                    
                    # Metadata
                    'week_start': {
                        'bsonType': 'date',
                        'description': 'Week start date'
                    },
                    'week_end': {
                        'bsonType': 'date',
                        'description': 'Week end date'
                    },
                    'timestamp': {
                        'bsonType': 'date',
                        'description': 'Calibration calculation timestamp'
                    },
                    'retention_date': {
                        'bsonType': 'date',
                        'description': '7-year retention expiration date'
                    },
                    'immutable': {
                        'bsonType': 'bool',
                        'description': 'Audit log immutability flag (always true)'
                    }
                }
            }
        }
    }


# ============================================================================
# INDEX DEFINITIONS
# ============================================================================

def get_sim_audit_indexes() -> list:
    """
    Indexes for sim_audit collection
    
    Required indexes per specification:
    - game_id (primary lookup)
    - sport (filtering)
    - timestamp (time-series queries)
    """
    return [
        IndexModel([('game_id', ASCENDING)], unique=True),
        IndexModel([('sport', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('timestamp', DESCENDING)]),
        IndexModel([('sport', ASCENDING), ('rcl_passed', ASCENDING)]),
        IndexModel([('sport', ASCENDING), ('edge_flagged', ASCENDING)]),
        IndexModel([('retention_date', ASCENDING)]),  # For 7-year retention cleanup
    ]


def get_bet_history_indexes() -> list:
    """
    Indexes for bet_history collection
    
    Required indexes per specification:
    - game_id (linking to games)
    - user_id (user lookups)
    - sport (filtering)
    - timestamp (time-series queries)
    """
    return [
        IndexModel([('user_id', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('game_id', ASCENDING)]),
        IndexModel([('sport', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('timestamp', DESCENDING)]),
        IndexModel([('user_id', ASCENDING), ('sport', ASCENDING)]),
        IndexModel([('retention_date', ASCENDING)]),  # For 7-year retention cleanup
    ]


def get_rcl_log_indexes() -> list:
    """
    Indexes for rcl_log collection
    
    Required indexes per specification:
    - game_id (linking to games)
    - sport (filtering)
    - timestamp (time-series queries)
    """
    return [
        IndexModel([('game_id', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('sport', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('timestamp', DESCENDING)]),
        IndexModel([('rcl_passed', ASCENDING)]),
        IndexModel([('retention_date', ASCENDING)]),  # For 7-year retention cleanup
    ]


def get_calibration_weekly_indexes() -> list:
    """
    Indexes for calibration_weekly collection
    
    Required indexes per specification:
    - sport (filtering)
    - timestamp (time-series queries)
    """
    return [
        IndexModel([('sport', ASCENDING), ('week_start', DESCENDING)]),
        IndexModel([('sport', ASCENDING), ('timestamp', DESCENDING)]),
        IndexModel([('timestamp', DESCENDING)]),
        IndexModel([('retention_date', ASCENDING)]),  # For 7-year retention cleanup
    ]


# ============================================================================
# INITIALIZATION
# ============================================================================

def initialize_audit_collections(db: Database) -> Dict[str, bool]:
    """
    Create audit collections with schemas and indexes
    
    Safe to run multiple times (idempotent).
    Returns status dict with success/failure for each collection.
    """
    results = {}
    
    collections = {
        'sim_audit': (get_sim_audit_schema, get_sim_audit_indexes),
        'bet_history': (get_bet_history_schema, get_bet_history_indexes),
        'rcl_log': (get_rcl_log_schema, get_rcl_log_indexes),
        'calibration_weekly': (get_calibration_weekly_schema, get_calibration_weekly_indexes),
    }
    
    for coll_name, (schema_fn, indexes_fn) in collections.items():
        try:
            # Create collection if not exists
            if coll_name not in db.list_collection_names():
                db.create_collection(coll_name, **schema_fn())
                logger.info(f"Created collection: {coll_name}")
            
            # Create indexes
            collection = db[coll_name]
            indexes = indexes_fn()
            if indexes:
                collection.create_indexes(indexes)
                logger.info(f"Created {len(indexes)} indexes for {coll_name}")
            
            results[coll_name] = True
            
        except Exception as e:
            logger.error(f"Failed to initialize {coll_name}: {e}")
            results[coll_name] = False
    
    return results


def verify_audit_collections(db: Database) -> Dict[str, Any]:
    """
    Verify audit collections exist and have correct indexes
    
    Returns status dict with collection stats.
    """
    status = {}
    
    for coll_name in ['sim_audit', 'bet_history', 'rcl_log', 'calibration_weekly']:
        if coll_name in db.list_collection_names():
            collection = db[coll_name]
            status[coll_name] = {
                'exists': True,
                'count': collection.count_documents({}),
                'indexes': len(list(collection.list_indexes())),
            }
        else:
            status[coll_name] = {
                'exists': False,
                'count': 0,
                'indexes': 0,
            }
    
    return status

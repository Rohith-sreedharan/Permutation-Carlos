"""
Simulation Stability System - Database Schemas
==============================================
MongoDB schemas for simulation context, results, and market monitoring.
"""

from pymongo import IndexModel, ASCENDING, DESCENDING


def create_simulation_indexes(db):
    """
    Create indexes for simulation stability collections.
    
    Collections:
    - simulation_contexts: Immutable context snapshots
    - simulation_results: Official simulation outputs
    - market_movements: Market price movement events
    - pm_mode_executions: PM Mode execution history
    """
    
    # ==========================================
    # simulation_contexts
    # ==========================================
    db["simulation_contexts"].create_indexes([
        IndexModel([("context_hash", ASCENDING)], unique=True),
        IndexModel([("game_id", ASCENDING), ("created_at_utc", DESCENDING)]),
        IndexModel([("model_version", ASCENDING)]),
        IndexModel([("created_at_utc", DESCENDING)]),
    ])
    
    # ==========================================
    # simulation_results
    # ==========================================
    db["simulation_results"].create_indexes([
        IndexModel([("context_hash", ASCENDING), ("game_id", ASCENDING), ("market_type", ASCENDING)], unique=True),
        IndexModel([("game_id", ASCENDING), ("market_type", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("is_valid_play", ASCENDING)]),
        IndexModel([("created_at_utc", DESCENDING)]),
        IndexModel([("edge_percent", DESCENDING)]),
    ])
    
    # ==========================================
    # market_movements
    # ==========================================
    db["market_movements"].create_indexes([
        IndexModel([("game_id", ASCENDING), ("market_type", ASCENDING), ("timestamp_utc", DESCENDING)]),
        IndexModel([("event_type", ASCENDING)]),
        IndexModel([("timestamp_utc", DESCENDING)]),
    ])
    
    # ==========================================
    # pm_mode_executions
    # ==========================================
    db["pm_mode_executions"].create_indexes([
        IndexModel([("context_hash", ASCENDING)]),
        IndexModel([("game_id", ASCENDING), ("market_type", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("executed_at_utc", DESCENDING)]),
    ])
    
    # ==========================================
    # stability_tests
    # ==========================================
    db["stability_tests"].create_indexes([
        IndexModel([("context_hash", ASCENDING)]),
        IndexModel([("game_id", ASCENDING), ("market_type", ASCENDING)]),
        IndexModel([("stability_score", DESCENDING)]),
        IndexModel([("created_at_utc", DESCENDING)]),
    ])


# Example document structures (for reference)

SIMULATION_CONTEXT_EXAMPLE = {
    "_id": "ctx_uuid",
    "context_hash": "sha256:abc123...",
    "game_id": "nba_20260119_lal_bos",
    "sport": "NBA",
    "league": "NBA",
    "home_team": "BOS",
    "away_team": "LAL",
    "game_time_utc": "2026-01-19T20:00:00Z",
    
    "model_version": "v3.2.1",
    "engine_version": "v2.1.0",
    "data_feed_version": "odds_api_v4",
    
    "market": {
        "market_type": "SPREAD",
        "selection": "away +7.5",
        "line": 7.5,
        "american_odds": -110,
        "decimal_odds": 1.909,
        "implied_prob": 0.5238,
        "devig_prob": 0.5120,
        "book_id": "draftkings",
        "timestamp_utc": "2026-01-19T15:30:00Z",
    },
    
    "injuries": [
        {
            "player_id": "lebron_james",
            "player_name": "LeBron James",
            "status": "PROBABLE",
            "minutes_projection": 34.0,
            "confidence": 0.85,
        }
    ],
    
    "pace_projection": 102.5,
    "fatigue_factors": {"LAL": 0.98, "BOS": 1.02},
    "weather": None,
    
    "n_simulations": 10000,
    "random_seed_base": None,
    
    "created_at_utc": "2026-01-19T15:30:00Z",
    "created_by": "simulation_cron",
    
    "deterministic_seed": 1234567890,
}


SIMULATION_RESULT_EXAMPLE = {
    "_id": "result_uuid",
    "context_hash": "sha256:abc123...",
    "game_id": "nba_20260119_lal_bos",
    "market_type": "SPREAD",
    "selection": "away +7.5",
    
    "model_probability": 0.5450,
    "confidence_interval": {
        "lower": 0.5350,
        "upper": 0.5550,
        "half_width": 0.0100,
        "confidence_level": 0.95,
    },
    
    "devig_market_probability": 0.5120,
    "raw_edge": 0.0330,
    "edge_percent": 3.30,
    
    "meets_edge_threshold": True,  # 3.30% >= 2.0%
    "meets_uncertainty_gate": True,  # 0.0330 >= 2 * 0.0100
    "is_valid_play": True,
    
    "playable_line_min": 7.0,
    "playable_line_max": 8.0,
    "playable_odds_min": -120,
    
    "n_simulations_run": 10000,
    "convergence_achieved": True,
    "random_seed_used": 1234567890,
    
    "created_at_utc": "2026-01-19T15:30:05Z",
    "status": "COMPLETED",
    
    # Full context stored for audit
    "context": SIMULATION_CONTEXT_EXAMPLE,
}


MARKET_MOVEMENT_EXAMPLE = {
    "_id": "movement_uuid",
    "game_id": "nba_20260119_lal_bos",
    "market_type": "SPREAD",
    "event_type": "GUARDRAIL_BREACHED",
    
    "violations": [
        "line_above_max:8.5>8.0"
    ],
    
    "current_line": 8.5,
    "current_odds": -110,
    
    "timestamp_utc": "2026-01-19T16:45:00Z",
}


PM_MODE_EXECUTION_EXAMPLE = {
    "_id": "pm_exec_uuid",
    "context_hash": "sha256:abc123...",
    "game_id": "nba_20260119_lal_bos",
    "market_type": "SPREAD",
    
    "pm_status": "ELIGIBLE",
    "edge_percent": 3.30,
    "stability_score": 0.75,
    
    "recommended_position_size_usd": 250.0,
    "actual_position_size_usd": 250.0,
    
    "polymarket_market_id": "pm_market_xyz",
    "polymarket_liquidity_usd": 12000.0,
    
    "execution_status": "EXECUTED",
    "execution_price": 0.545,
    "execution_timestamp_utc": "2026-01-19T16:00:00Z",
    
    "thresholds_used": {
        "min_edge_percent": 3.0,
        "max_ci_half_width": 0.008,
        "min_stability_score": 0.70,
    },
    
    "created_at_utc": "2026-01-19T15:30:10Z",
}


STABILITY_TEST_EXAMPLE = {
    "_id": "stability_uuid",
    "context_hash": "sha256:abc123...",
    "game_id": "nba_20260119_lal_bos",
    "market_type": "SPREAD",
    
    "n_perturbations": 100,
    "perturbation_magnitude": 0.05,
    
    "base_edge_percent": 3.30,
    "survival_count": 75,
    "survival_rate": 0.75,
    "stability_score": 0.75,
    
    "perturbation_details": [
        {
            "perturbation_id": 1,
            "pace_delta": -0.03,
            "minutes_deltas": {"lebron_james": -0.02},
            "survived": True,
            "edge_percent": 3.15,
        },
        # ... 99 more
    ],
    
    "created_at_utc": "2026-01-19T15:35:00Z",
}

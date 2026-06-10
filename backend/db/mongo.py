import os
import sys
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import logging
from config.phase10_tenant_shell import PHASE10_AUDIT_COLLECTIONS

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import now_utc, now_est, parse_iso_to_est, format_est_date

load_dotenv()

logger = logging.getLogger(__name__)

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "beatvegas")
MONGO_MAX_POOL_SIZE = int(os.getenv("MONGO_MAX_POOL_SIZE", "50"))

# Initialize MongoDB client — lazy connection (no blocking ping at import time).
# pymongo MongoClient is non-blocking at construction; the first actual operation
# triggers the connection. The blocking `admin.command('ping')` has been removed
# from module-level code to prevent hanging the FastAPI event loop at startup.
# Connection health is verified in the async startup handler via run_in_executor.
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000,
    socketTimeoutMS=10000,
    maxPoolSize=MONGO_MAX_POOL_SIZE,
)
db = client[DB_NAME]
logger.info(
    "MongoDB client initialised (lazy connection — not yet pinged, maxPoolSize=%s)",
    MONGO_MAX_POOL_SIZE,
)


def ensure_indexes() -> None:
    """
    Create core indexes for collections used by the backend.
    
    NOTE: In production, ensure MongoDB user has sufficient privileges:
    - readWrite role on the database
    - Or dbAdmin role to create indexes
    
    If you get "Command createIndexes requires authentication" errors:
    1. Check MONGO_URI includes username:password
    2. Verify user has dbAdmin or readWrite role
    3. Example: mongodb://user:pass@host:port/dbname?authSource=admin
    """
    try:
        # Original indexes
        db["events"].create_index("event_id", unique=True)
        db["normalized_data"].create_index([("timestamp", -1)])
        db["predictions"].create_index([("event_id", 1)])
        db["logs_core_ai"].create_index([("module", 1), ("timestamp", -1)])
        
        # A/B Test Event indexes
        db["ab_test_events"].create_index([("session_id", 1), ("ts", -1)])
        db["ab_test_events"].create_index([("variant", 1), ("event", 1)])
        db["ab_test_events"].create_index([("ref", 1)])
        db["ab_test_events"].create_index([("ts", -1)])
        
        # Subscriber indexes
        db["subscribers"].create_index("email", unique=True)
        db["subscribers"].create_index([("ref", 1)])
        db["subscribers"].create_index([("status", 1)])
        db["subscribers"].create_index("stripe_customer_id", unique=True, sparse=True)
        db["subscribers"].create_index([("tier", 1)])  # NEW: For tier-based queries
        
        # AI Pick indexes
        db["ai_picks"].create_index("pick_id", unique=True)
        db["ai_picks"].create_index([("event_id", 1)])
        db["ai_picks"].create_index([("created_at", -1)])
        db["ai_picks"].create_index([("outcome", 1)])  # For ROI analysis
        db["ai_picks"].create_index([("clv_pct", 1)])  # For CLV tracking
        db["ai_picks"].create_index([("settled_at", -1)])  # NEW: For performance reports
        
        # User Action indexes (Module 7 input)
        db["user_actions"].create_index([("pick_id", 1)])
        db["user_actions"].create_index([("user_id", 1), ("created_at", -1)])
        db["user_actions"].create_index([("action", 1)])
        
        # Community Message indexes
        db["community_messages"].create_index([("channel_id", 1), ("ts", -1)])
        db["community_messages"].create_index([("user_id", 1), ("ts", -1)])
        db["community_messages"].create_index([("parsed_intent", 1)])
        db["community_messages"].create_index([("ts", -1)])
        db["community_messages"].create_index([("message_type", 1)])  # NEW: For bot messages
        
        # NEW: User Identity indexes
        db["user_identity"].create_index("user_id", unique=True)
        db["user_identity"].create_index([("xp", -1)])  # Leaderboard by XP
        db["user_identity"].create_index([("rank", 1)])
        db["user_identity"].create_index([("total_profit", -1)])  # Leaderboard by profit
        db["user_identity"].create_index([("longest_streak", -1)])  # Leaderboard by streak
        db["user_identity"].create_index([("winning_picks", -1)])  # Leaderboard by wins
        
        # Community Pick Submission indexes
        db["community_picks"].create_index([("user_id", 1)])
        db["community_picks"].create_index([("event_id", 1)])
        db["community_picks"].create_index([("submitted_at", -1)])
        db["community_picks"].create_index([("outcome", 1)])
        
        # User Reputation indexes
        db["user_reputation"].create_index("user_id", unique=True)
        db["user_reputation"].create_index([("elo_score", -1)])  # Leaderboard
        db["user_reputation"].create_index([("roi", -1)])  # Performance ranking
        
        # Commission indexes
        db["commissions"].create_index("commission_id", unique=True)
        db["commissions"].create_index([("affiliate_id", 1), ("ts", -1)])
        db["commissions"].create_index([("user_id", 1)])
        db["commissions"].create_index([("status", 1)])
        db["commissions"].create_index("stripe_subscription_id", sparse=True)
        
        # Affiliate Account indexes
        db["affiliate_accounts"].create_index("affiliate_id", unique=True)
        db["affiliate_accounts"].create_index("email", unique=True)
        db["affiliate_accounts"].create_index([("status", 1)])
        
        # NEW: Monte Carlo Simulation indexes
        db["monte_carlo_simulations"].create_index("simulation_id", unique=True)
        db["monte_carlo_simulations"].create_index([("event_id", 1), ("created_at", -1)])
        db["monte_carlo_simulations"].create_index([("created_at", -1)])
        db["monte_carlo_simulations"].create_index([("confidence_score", -1)])
        
        # NEW: Multi-Agent System indexes
        db["agent_events"].create_index([("event_id", 1)])
        db["agent_events"].create_index([("event_type", 1), ("timestamp", -1)])
        db["agent_events"].create_index([("correlation_id", 1)])  # Track related events
        db["agent_events"].create_index([("source_agent", 1), ("timestamp", -1)])
        db["agent_events"].create_index([("status", 1)])
        
        # NEW: Performance Report indexes
        db["performance_reports"].create_index("report_id", unique=True)
        db["performance_reports"].create_index([("generated_at", -1)])
        
        # NEW: Recalibration Recommendation indexes
        db["recalibration_recommendations"].create_index("recommendation_id", unique=True)
        db["recalibration_recommendations"].create_index([("status", 1), ("generated_at", -1)])
        db["recalibration_recommendations"].create_index([("based_on_report", 1)])
        
        # NEW: Live Event Trigger indexes
        db["live_triggers"].create_index([("event_id", 1), ("trigger_time", -1)])
        db["live_triggers"].create_index([("trigger_type", 1)])
        db["live_triggers"].create_index([("processed", 1), ("trigger_time", -1)])
        
        # NEW: Prop Mispricing Detection indexes
        db["prop_mispricings"].create_index([("event_id", 1)])
        db["prop_mispricings"].create_index([("edge_pct", -1)])  # Sort by biggest edges
        db["prop_mispricings"].create_index([("detected_at", -1)])

        # NEW: Sport Edge Evaluation indexes
        db["nhl_evaluations"].create_index("game_id", unique=True)
        db["nhl_evaluations"].create_index([("updated_at", -1)])
        db["mlb_evaluations"].create_index("game_id", unique=True)
        db["mlb_evaluations"].create_index([("updated_at", -1)])
        
        # NEW: Parlay Architect indexes
        db["parlay_generation_audit"].create_index([("created_at_utc", -1)])
        db["parlay_generation_audit"].create_index([("request.profile", 1), ("result.status", 1)])
        db["parlay_generation_audit"].create_index([("result.status", 1)])
        
        db["parlay_claim"].create_index([("created_at_utc", -1)])
        db["parlay_claim"].create_index([("attempt_id", 1)])
        db["parlay_claim"].create_index([("profile_used", 1)])
        db["parlay_claim"].create_index([("parlay_fingerprint", 1)], unique=True, sparse=True)
        
        db["parlay_fail_event"].create_index([("created_at_utc", -1)])
        db["parlay_fail_event"].create_index([("attempt_id", 1)])
        db["parlay_fail_event"].create_index([("reason_code", 1)])
        
        # NEW: vFinal.1 Multi-Sport Patch - Simulation market indexes
        # Per spec Section 5.2: Add sport_market_index for efficient multi-sport queries
        db["simulations"].create_index([
            ("sport", 1),
            ("market_type", 1),
            ("market_settlement", 1)
        ], name="sport_market_index", background=True)

        # Phase 1+ persistence indexes: canonical decision bundles
        db["decision_records"].create_index("identity_key", unique=True)
        db["decision_records"].create_index("record_id", unique=True)
        db["decision_records"].create_index([("game_id", 1), ("created_at", -1)])

        # Distribution Governance indexes (Operational Architecture v1.0.0)
        db["distribution_decision_log"].create_index("distribution_id", unique=True)
        db["distribution_decision_log"].create_index("decision_id", unique=True)
        db["distribution_decision_log"].create_index([("event_id", 1)])
        db["distribution_decision_log"].create_index([("calendar_day", 1)])
        db["distribution_decision_log"].create_index([("distribution_category", 1), ("calendar_day", 1)])
        db["distribution_decision_log"].create_index([("market_type", 1), ("calendar_day", 1)])
        db["distribution_decision_log"].create_index([("trace_id", 1)])

        # Lifecycle + assertion support indexes used by governance services
        db["prediction_lifecycle_log"].create_index([("decision_id", 1), ("timestamp", -1)])
        db["prediction_lifecycle_log"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["prediction_lifecycle_log"].create_index([("snapshot_hash", 1), ("timestamp", -1)])
        db["prediction_lifecycle_log"].create_index([("stage", 1), ("timestamp", -1)])
        db["assertion_failure_log"].create_index([("code", 1), ("created_at_utc", -1)])

        # Phase 2 observability indexes (append-only)
        db["decision_audit_log"].create_index([("audit_id", 1)], unique=True)
        db["decision_audit_log"].create_index([("event_id", 1), ("timestamp", -1)])
        db["decision_audit_log"].create_index([("decision_id", 1), ("timestamp", -1)])
        db["decision_audit_log"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["decision_audit_log"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        db["decision_settlement_metrics"].create_index([("metrics_id", 1)], unique=True)
        db["decision_settlement_metrics"].create_index([("graded_id", 1), ("timestamp", -1)])
        db["decision_settlement_metrics"].create_index([("publish_id", 1), ("timestamp", -1)])
        db["decision_settlement_metrics"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["decision_settlement_metrics"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        db["truth_dataset"].create_index([("truth_row_id", 1)], unique=True)
        db["truth_dataset"].create_index([("event_id", 1), ("timestamp", -1)])
        db["truth_dataset"].create_index([("prediction_id", 1), ("timestamp", -1)])
        db["truth_dataset"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["truth_dataset"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        db["clv_capture_log"].create_index([("clv_capture_id", 1)], unique=True)
        db["clv_capture_log"].create_index([("event_id", 1), ("timestamp", -1)])
        db["clv_capture_log"].create_index([("prediction_id", 1), ("timestamp", -1)])
        db["clv_capture_log"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["clv_capture_log"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        db["calibration_records"].create_index([("calibration_record_id", 1)], unique=True)
        db["calibration_records"].create_index([("calibration_version", 1), ("timestamp", -1)])
        db["calibration_records"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["calibration_records"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        db["drift_detection_log"].create_index([("drift_id", 1)], unique=True)
        db["drift_detection_log"].create_index([("drift_detected", 1), ("timestamp", -1)])
        db["drift_detection_log"].create_index([("trace_id", 1), ("timestamp", -1)])
        db["drift_detection_log"].create_index([("snapshot_hash", 1), ("timestamp", -1)])

        # Billing + parlay execution observability indexes (Spec v2.0.1)
        db["billing_state"].create_index([("user_id", 1)], unique=True)
        db["billing_state"].create_index([("plan_id", 1)])
        db["billing_state"].create_index([("status", 1)])
        db["billing_state"].create_index([("next_billing_date", 1)])

        db["billing_state_change_log"].create_index([("change_id", 1)], unique=True)
        db["billing_state_change_log"].create_index([("user_id", 1)])
        db["billing_state_change_log"].create_index([("trace_id", 1)])
        db["billing_state_change_log"].create_index([("field_changed", 1)])
        db["billing_state_change_log"].create_index([("created_at_utc", -1)])

        db["parlay_execution_log"].create_index([("event_id", 1)], unique=True)
        db["parlay_execution_log"].create_index([("run_id", 1)])
        db["parlay_execution_log"].create_index([("user_id", 1)])
        db["parlay_execution_log"].create_index([("trace_id", 1)])
        db["parlay_execution_log"].create_index([("decision_id", 1)])
        db["parlay_execution_log"].create_index([("event_type", 1)])
        db["parlay_execution_log"].create_index([("created_at_utc", -1)])

        db["parlay_overage_charge_log"].create_index([("charge_id", 1)], unique=True)
        db["parlay_overage_charge_log"].create_index([("parlay_run_id", 1)], unique=True)
        db["parlay_overage_charge_log"].create_index([("user_id", 1)])
        db["parlay_overage_charge_log"].create_index([("trace_id", 1)])
        db["parlay_overage_charge_log"].create_index([("billing_period_start", 1)])
        db["parlay_overage_charge_log"].create_index([("created_at_utc", -1)])

        # Phase 9 compliance indexes (append-only legal logs)
        db["self_exclusion_log"].create_index([("exclusion_id", 1)], unique=True)
        db["self_exclusion_log"].create_index([("user_id", 1), ("requested_at_utc", -1)])
        db["self_exclusion_log"].create_index([("trace_id", 1)])

        db["self_exclusion_reinstatement_queue"].create_index([("request_id", 1)], unique=True)
        db["self_exclusion_reinstatement_queue"].create_index([("user_id", 1), ("requested_at_utc", -1)])
        db["self_exclusion_reinstatement_queue"].create_index([("status", 1), ("requested_at_utc", -1)])

        db["data_deletion_log"].create_index([("request_id", 1)])
        db["data_deletion_log"].create_index([("user_id", 1), ("requested_at_utc", -1)])
        db["data_deletion_log"].create_index([("status", 1), ("requested_at_utc", -1)])
        db["data_deletion_log"].create_index([("trace_id", 1)])

        # Phase 10 B2B shell: tenant table and tenant-scoped audit readiness.
        db["tenants"].create_index([("tenant_id", 1)], unique=True)
        db["tenants"].create_index([("tenant_type", 1), ("status", 1)])
        db["tenants"].create_index([("entitlement_type", 1), ("status", 1)])

        for collection in PHASE10_AUDIT_COLLECTIONS:
            db[collection].create_index([("tenant_id", 1)])

        # Phase 11 affiliate acquisition engine indexes
        db["affiliate_invites"].create_index([("invite_id", 1)], unique=True)
        db["affiliate_invites"].create_index([("affiliate_id", 1), ("status", 1)])
        db["affiliate_invites"].create_index([("expires_at_utc", 1)])

        db["affiliate_clicks"].create_index([("click_id", 1)], unique=True)
        db["affiliate_clicks"].create_index([("affiliate_id", 1), ("clicked_at_utc", -1)])
        db["affiliate_clicks"].create_index([("is_converted", 1), ("clicked_at_utc", -1)])

        db["affiliate_attributions"].create_index([("attribution_id", 1)], unique=True)
        db["affiliate_attributions"].create_index([("user_id", 1)], unique=True)
        db["affiliate_attributions"].create_index([("affiliate_id", 1), ("locked_at_utc", -1)])

        db["affiliate_commission_log"].create_index([("commission_id", 1)])
        db["affiliate_commission_log"].create_index([("affiliate_id", 1), ("created_at_utc", -1)])
        db["affiliate_commission_log"].create_index([("status", 1), ("net_30_date", 1)])
        db["affiliate_commission_log"].create_index([("trace_id", 1)])

        db["affiliate_payout_log"].create_index([("payout_id", 1)], unique=True)
        db["affiliate_payout_log"].create_index([("affiliate_id", 1), ("created_at_utc", -1)])
        db["affiliate_payout_log"].create_index([("status", 1), ("created_at_utc", -1)])

        db["affiliate_payout_batches"].create_index([("batch_id", 1)], unique=True)
        db["affiliate_payout_batches"].create_index([("run_date_utc", -1)])
        
        logger.info("✅ Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to create indexes: {e}")
        logger.error("   Possible causes:")
        logger.error("   1. MongoDB user lacks dbAdmin or readWrite role")
        logger.error("   2. MONGO_URI doesn't include authentication credentials")
        logger.error("   3. authSource parameter missing in connection string")
        # Don't raise - allow app to continue without indexes
        # Indexes improve performance but aren't required for basic operation


def insert_many(collection: str, data: List[Dict[str, Any]]) -> Optional[List[Any]]:
    if not data:
        return None
    result = db[collection].insert_many(data)
    return result.inserted_ids


def fetch_all(collection: str, filter: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[Dict[str, Any]]:
    return list(db[collection].find(filter or {}).limit(limit))


def upsert_events(collection: str, events: List[Dict[str, Any]]):
    """Upsert a list of event dicts into `collection` using event_id as unique key.

    Each event dict is expected to contain an `event_id` key.
    """
    if not events:
        return 0

    ops = []
    for ev in events:
        ev = ev.copy()
        ev.setdefault("created_at", now_utc().isoformat())
        event_id = ev.get("event_id") or ev.get("id")
        if not event_id:
            # skip malformed
            continue
        ev["event_id"] = event_id
        # Remove raw Mongo _id if present
        ev.pop("_id", None)
        ops.append(
            UpdateOne({"event_id": ev["event_id"]}, {"$set": ev}, upsert=True)
        )

    if not ops:
        return 0

    result = db[collection].bulk_write(ops, ordered=False)
    # return total upserted/modified count (approx)
    return (result.upserted_count or 0) + (result.modified_count or 0)


def find_events(collection: str, filter: Optional[Dict[str, Any]] = None, limit: int = 50):
    docs = list(db[collection].find(filter or {}).limit(limit))
    # Convert ObjectId to string for JSON serialization
    for doc in docs:
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
        
        # Ensure 'id' field exists for frontend compatibility
        # Frontend expects event.id, but we store event_id
        if 'event_id' in doc and 'id' not in doc:
            doc['id'] = doc['event_id']
        
        # Transform bookmakers data into bets array for frontend compatibility
        if 'bookmakers' in doc and doc['bookmakers']:
            bets = []
            top_prop_bet = None
            
            # Extract h2h (moneyline) odds from first bookmaker
            for bookmaker in doc['bookmakers']:
                for market in bookmaker.get('markets', []):
                    if market['key'] == 'h2h':
                        normalized_outcomes = _extract_canonical_h2h_outcomes(
                            market=market,
                            home_team=doc.get('home_team', ''),
                            away_team=doc.get('away_team', ''),
                        )
                        for outcome_name, american_odds in normalized_outcomes:
                            formatted_price = f"+{american_odds}" if american_odds > 0 else str(american_odds)
                            bets.append({
                                'type': 'Moneyline',
                                'pick': outcome_name,
                                'value': formatted_price
                            })
                    elif market['key'] == 'spreads' and not top_prop_bet:
                        # Use first spread as top prop bet
                        outcomes = market.get('outcomes', [])
                        if outcomes:
                            top_prop_bet = f"{outcomes[0]['name']} {outcomes[0].get('point', '')} @ {outcomes[0]['price']}"
                
                # Only use first bookmaker for simplicity
                if bets:
                    break
            
            doc['bets'] = bets
            doc['top_prop_bet'] = top_prop_bet
    
    return docs


def _extract_canonical_h2h_outcomes(
    market: Dict[str, Any],
    home_team: str,
    away_team: str,
) -> List[Tuple[str, int]]:
    """Return strict 2-way moneyline outcomes for card rendering."""
    outcomes = market.get('outcomes', []) or []
    team_names = {home_team.strip().lower(), away_team.strip().lower()}

    team_outcomes: List[Tuple[str, float]] = []
    for outcome in outcomes:
        name = str(outcome.get('name', '')).strip()
        if not name or name.lower() not in team_names:
            continue
        price = _to_numeric(outcome.get('price'))
        if price is None:
            continue
        team_outcomes.append((name, price))

    # Normalize all team-vs-team outcomes to no-vig 2-way probabilities.
    # This handles both native 2-way h2h and draw-inclusive 3-way h2h consistently.
    if len(team_outcomes) == 2:
        team_a_name, team_a_price = team_outcomes[0]
        team_b_name, team_b_price = team_outcomes[1]

        team_a_prob = _price_to_implied_probability(team_a_price)
        team_b_prob = _price_to_implied_probability(team_b_price)
        denom = team_a_prob + team_b_prob

        if denom > 0:
            team_a_prob_2way = team_a_prob / denom
            team_b_prob_2way = team_b_prob / denom
            team_a_american, team_b_american = _to_polarized_two_way_american(
                team_a_prob_2way,
                team_b_prob_2way,
            )
            return [
                (team_a_name, team_a_american),
                (team_b_name, team_b_american),
            ]

    return [(name, _price_to_american(price)) for name, price in team_outcomes[:2]]


def _is_draw_like_name(name: str) -> bool:
    return name.strip().lower() in {'draw', 'tie', 'x'}


def _to_numeric(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price_to_american(price: float) -> int:
    # Odds API payloads can be decimal (< 50) or American (>= 50 magnitude)
    if abs(price) >= 50:
        return int(round(price))

    if price <= 1.0:
        return 100
    if price >= 2.0:
        return int(round((price - 1.0) * 100.0))
    return int(round(-100.0 / (price - 1.0)))


def _price_to_implied_probability(price: float) -> float:
    if abs(price) >= 50:
        if price > 0:
            return 100.0 / (price + 100.0)
        return abs(price) / (abs(price) + 100.0)

    if price <= 1.0:
        return 0.0
    return 1.0 / price


def _implied_probability_to_american(probability: float) -> int:
    p = max(0.0001, min(0.9999, probability))
    if p >= 0.5:
        return int(round(-(p / (1.0 - p)) * 100.0))
    return int(round(((1.0 - p) / p) * 100.0))


def _to_polarized_two_way_american(probability_a: float, probability_b: float) -> Tuple[int, int]:
    """
    Convert two complementary probabilities to opposite-sign American odds for display.
    """
    if abs(probability_a - probability_b) < 1e-9:
        return -100, 100

    odds_a = _implied_probability_to_american(probability_a)
    odds_b = _implied_probability_to_american(probability_b)

    # Enforce opposite polarity for card display consistency.
    if (odds_a > 0 and odds_b > 0) or (odds_a < 0 and odds_b < 0):
        if probability_a > probability_b:
            odds_a = -abs(odds_a)
            odds_b = abs(odds_b)
        else:
            odds_b = -abs(odds_b)
            odds_a = abs(odds_a)

    return odds_a, odds_b


def insert_log_entry(entry: Dict[str, Any]):
    return db["logs_core_ai"].insert_one(entry)


def find_logs(module: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if module:
        query["module"] = module
    return list(db["logs_core_ai"].find(query).sort("timestamp", -1).limit(limit))

import os
import sys
from pymongo import MongoClient, UpdateOne
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import now_utc, now_est, parse_iso_to_est, format_est_date

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "beatvegas")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


def ensure_indexes() -> None:
    """Create core indexes for collections used by the backend."""
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
                        for outcome in market.get('outcomes', [])[:2]:  # Home and Away
                            price = outcome['price']
                            # Convert decimal odds to American format if needed
                            if abs(price) < 50:  # Likely decimal odds (e.g., 1.02, 2.5)
                                if price >= 2.0:
                                    american_odds = int((price - 1) * 100)
                                elif price > 1.0:  # Prevent division by zero
                                    american_odds = int(-100 / (price - 1))
                                else:
                                    # Handle edge case: price = 1.0 or invalid
                                    american_odds = 100
                                formatted_price = f"+{american_odds}" if american_odds > 0 else str(american_odds)
                            else:  # Already American odds
                                formatted_price = f"+{int(price)}" if price > 0 else str(int(price))
                            
                            bets.append({
                                'type': 'Moneyline',
                                'pick': outcome['name'],
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


def insert_log_entry(entry: Dict[str, Any]):
    return db["logs_core_ai"].insert_one(entry)


def find_logs(module: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    query: Dict[str, Any] = {}
    if module:
        query["module"] = module
    return list(db["logs_core_ai"].find(query).sort("timestamp", -1).limit(limit))

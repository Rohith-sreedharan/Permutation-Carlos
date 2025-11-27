"""
User Bets Collection Schema
============================

This module defines the MongoDB schema for the user_bets collection.
This collection stores all betting activity for creator marketplace tracking.

Schema Fields:
--------------
- _id: ObjectId - MongoDB primary key
- user_id: str - User ID (links to users collection)
- slip_id: str - Unique slip identifier
- event_id: str - Event ID from odds API
- sport: str - Sport category (NBA, NFL, MLB, NHL)
- pick_type: str - Type of bet (single, parlay, prop)
- selection: str - Team/player name selected
- line: float - Betting line (spread/total)
- odds: float - Decimal odds (e.g., 2.10 = +110)
- stake: float - Amount wagered in dollars
- num_legs: int - Number of legs (for parlays, 1 for singles)
- outcome: str - Result status (pending, win, loss, push)
- profit: float - Profit/loss in dollars (negative for losses)
- created_at: datetime - Timestamp when bet was placed
- settled_at: datetime - Timestamp when bet was settled (null if pending)

Indexes:
--------
1. user_id + settled_at (DESC) - Fast creator stats queries
2. outcome - Filter by win/loss for badge calculations
3. pick_type - Query parlays vs singles
4. user_id + outcome + settled_at - Complex badge logic
"""

from datetime import datetime, timezone
from pymongo import ASCENDING, DESCENDING

def create_indexes(db):
    """
    Create indexes for the user_bets collection.
    
    This function should be called during application startup to ensure
    all required indexes exist for optimal query performance.
    
    Args:
        db: MongoDB database instance
    """
    user_bets = db['user_bets']
    
    # Index 1: User ID + Settled At (DESC)
    # Used for: Creator stats queries, recent slips endpoint
    # Query: db.user_bets.find({'user_id': user_id}).sort('settled_at', -1).limit(10)
    user_bets.create_index([
        ('user_id', ASCENDING),
        ('settled_at', DESCENDING)
    ])
    
    # Index 2: Outcome
    # Used for: Badge calculations (filter wins/losses)
    # Query: db.user_bets.find({'outcome': {'$in': ['win', 'loss']}})
    user_bets.create_index([
        ('outcome', ASCENDING)
    ])
    
    # Index 3: Pick Type
    # Used for: Parlay Master badge (filter 3+ leg parlays)
    # Query: db.user_bets.find({'pick_type': 'parlay', 'num_legs': {'$gte': 3}})
    user_bets.create_index([
        ('pick_type', ASCENDING)
    ])
    
    # Index 4: User ID + Outcome + Settled At (DESC)
    # Used for: Hot Streak badge (last 5 consecutive wins)
    # Query: db.user_bets.find({'user_id': user_id, 'outcome': 'win'}).sort('settled_at', -1).limit(5)
    user_bets.create_index([
        ('user_id', ASCENDING),
        ('outcome', ASCENDING),
        ('settled_at', DESCENDING)
    ])
    
    # Index 5: User ID + Created At (DESC)
    # Used for: Volume King badge (count bets in last 30 days)
    # Query: db.user_bets.find({'user_id': user_id, 'created_at': {'$gte': thirty_days_ago}})
    user_bets.create_index([
        ('user_id', ASCENDING),
        ('created_at', DESCENDING)
    ])
    
    print("✅ user_bets indexes created successfully")


def example_documents():
    """
    Return example documents for the user_bets collection.
    These examples show the expected schema structure.
    """
    return [
        {
            # Single NBA bet (won)
            "_id": "ObjectId('507f1f77bcf86cd799439011')",
            "user_id": "507f191e810c19729de860ea",
            "slip_id": "slip_abc123",
            "event_id": "nba_lakers_celtics_20240115",
            "sport": "NBA",
            "pick_type": "single",
            "selection": "Los Angeles Lakers",
            "line": -5.5,  # Lakers -5.5
            "odds": 1.91,  # -110 in American odds
            "stake": 100.0,
            "num_legs": 1,
            "outcome": "win",
            "profit": 91.0,  # Won $91 ($100 stake + $91 profit = $191 total return)
            "created_at": datetime(2024, 1, 15, 19, 30, 0, tzinfo=timezone.utc),
            "settled_at": datetime(2024, 1, 15, 22, 45, 0, tzinfo=timezone.utc)
        },
        {
            # 3-leg cross-sport parlay (pending)
            "_id": "ObjectId('507f1f77bcf86cd799439012')",
            "user_id": "507f191e810c19729de860ea",
            "slip_id": "slip_def456",
            "event_id": "parlay_3_legs",  # Composite event
            "sport": "Multi-Sport",  # NBA + NFL + MLB
            "pick_type": "parlay",
            "selection": "Lakers ML / Chiefs -3 / Yankees Over 8.5",
            "line": 0.0,  # No line for parlays (stored per leg)
            "odds": 6.50,  # +550 parlay odds
            "stake": 50.0,
            "num_legs": 3,
            "outcome": "pending",
            "profit": 0.0,  # Not settled yet
            "created_at": datetime(2024, 1, 16, 14, 20, 0, tzinfo=timezone.utc),
            "settled_at": None  # Still pending
        },
        {
            # Single MLB bet (lost)
            "_id": "ObjectId('507f1f77bcf86cd799439013')",
            "user_id": "507f191e810c19729de860ea",
            "slip_id": "slip_ghi789",
            "event_id": "mlb_yankees_redsox_20240420",
            "sport": "MLB",
            "pick_type": "single",
            "selection": "New York Yankees",
            "line": 0.0,  # Moneyline (no line)
            "odds": 1.75,  # -133 in American odds
            "stake": 75.0,
            "num_legs": 1,
            "outcome": "loss",
            "profit": -75.0,  # Lost $75 stake
            "created_at": datetime(2024, 4, 20, 18, 10, 0, tzinfo=timezone.utc),
            "settled_at": datetime(2024, 4, 20, 21, 30, 0, tzinfo=timezone.utc)
        }
    ]


# Schema validation (PyMongo 4.x validator)
user_bets_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "slip_id", "event_id", "sport", "pick_type", 
                     "selection", "odds", "stake", "num_legs", "outcome", "created_at"],
        "properties": {
            "user_id": {
                "bsonType": "string",
                "description": "User ID (links to users collection)"
            },
            "slip_id": {
                "bsonType": "string",
                "description": "Unique slip identifier"
            },
            "event_id": {
                "bsonType": "string",
                "description": "Event ID from odds API"
            },
            "sport": {
                "enum": ["NBA", "NFL", "MLB", "NHL", "Multi-Sport"],
                "description": "Sport category"
            },
            "pick_type": {
                "enum": ["single", "parlay", "prop"],
                "description": "Type of bet"
            },
            "selection": {
                "bsonType": "string",
                "description": "Team/player name selected"
            },
            "line": {
                "bsonType": "double",
                "description": "Betting line (spread/total, 0.0 for moneylines)"
            },
            "odds": {
                "bsonType": "double",
                "minimum": 1.01,
                "description": "Decimal odds (must be > 1.0)"
            },
            "stake": {
                "bsonType": "double",
                "minimum": 0.01,
                "description": "Amount wagered in dollars (must be positive)"
            },
            "num_legs": {
                "bsonType": "int",
                "minimum": 1,
                "description": "Number of legs (1 for singles, 2+ for parlays)"
            },
            "outcome": {
                "enum": ["pending", "win", "loss", "push"],
                "description": "Result status"
            },
            "profit": {
                "bsonType": "double",
                "description": "Profit/loss in dollars (negative for losses)"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Timestamp when bet was placed"
            },
            "settled_at": {
                "bsonType": ["date", "null"],
                "description": "Timestamp when bet was settled (null if pending)"
            }
        }
    }
}

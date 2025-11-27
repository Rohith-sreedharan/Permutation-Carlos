"""
API Keys Collection Schema
===========================

This module defines the MongoDB schema for the api_keys collection.
This collection stores enterprise API keys for B2B customers.

Schema Fields:
--------------
- _id: ObjectId - MongoDB primary key
- key: str - Unique API key (UUID format)
- customer_id: str - Customer identifier
- customer_name: str - Company/organization name
- tier: str - Subscription tier (starter, growth, enterprise)
- allowed_sports: List[str] - Sports accessible (NBA, NFL, MLB, NHL)
- rate_limit: int - Requests per second
- daily_limit: int - Max requests per day (null for unlimited)
- active: bool - Whether key is active
- created_at: datetime - Key creation timestamp
- expires_at: datetime - Key expiration timestamp

Indexes:
--------
1. key (UNIQUE) - Fast lookup for authentication
2. customer_id - Query all keys for a customer
3. active + expires_at - Find expired keys for cleanup

Tier Pricing:
-------------
- Starter ($50K/year): 5 req/s, 1 sport, 10K requests/day
- Growth ($150K/year): 10 req/s, 2 sports, 50K requests/day
- Enterprise ($500K/year): 25 req/s, all sports, unlimited requests
"""

from datetime import datetime, timezone, timedelta
from pymongo import ASCENDING, DESCENDING
import uuid

def create_indexes(db):
    """
    Create indexes for the api_keys collection.
    
    Args:
        db: MongoDB database instance
    """
    api_keys = db['api_keys']
    
    # Index 1: Unique key for fast authentication
    api_keys.create_index([('key', ASCENDING)], unique=True)
    
    # Index 2: Customer ID for customer queries
    api_keys.create_index([('customer_id', ASCENDING)])
    
    # Index 3: Active + Expires At for cleanup jobs
    api_keys.create_index([
        ('active', ASCENDING),
        ('expires_at', ASCENDING)
    ])
    
    print("✅ api_keys indexes created successfully")


def generate_api_key() -> str:
    """
    Generate a new API key (UUID v4 format).
    
    Returns:
        32-character hex string (e.g., 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6')
    """
    return uuid.uuid4().hex


def create_starter_key(db, customer_name: str, customer_id: str) -> str:
    """
    Create a new Starter tier API key.
    
    Args:
        db: MongoDB database instance
        customer_name: Company/organization name
        customer_id: Unique customer identifier
    
    Returns:
        Generated API key string
    """
    api_keys = db['api_keys']
    
    key = generate_api_key()
    
    key_doc = {
        'key': key,
        'customer_id': customer_id,
        'customer_name': customer_name,
        'tier': 'starter',
        'allowed_sports': ['NBA'],  # Starter tier: NBA only
        'rate_limit': 5,  # 5 req/s
        'daily_limit': 10000,  # 10K requests/day
        'active': True,
        'created_at': datetime.now(timezone.utc),
        'expires_at': datetime.now(timezone.utc) + timedelta(days=365)  # 1 year
    }
    
    api_keys.insert_one(key_doc)
    print(f"✅ Created Starter API key for {customer_name}: {key}")
    
    return key


def create_growth_key(db, customer_name: str, customer_id: str) -> str:
    """
    Create a new Growth tier API key.
    
    Args:
        db: MongoDB database instance
        customer_name: Company/organization name
        customer_id: Unique customer identifier
    
    Returns:
        Generated API key string
    """
    api_keys = db['api_keys']
    
    key = generate_api_key()
    
    key_doc = {
        'key': key,
        'customer_id': customer_id,
        'customer_name': customer_name,
        'tier': 'growth',
        'allowed_sports': ['NBA', 'NFL'],  # Growth tier: NBA + NFL
        'rate_limit': 10,  # 10 req/s
        'daily_limit': 50000,  # 50K requests/day
        'active': True,
        'created_at': datetime.now(timezone.utc),
        'expires_at': datetime.now(timezone.utc) + timedelta(days=365)  # 1 year
    }
    
    api_keys.insert_one(key_doc)
    print(f"✅ Created Growth API key for {customer_name}: {key}")
    
    return key


def create_enterprise_key(db, customer_name: str, customer_id: str) -> str:
    """
    Create a new Enterprise tier API key.
    
    Args:
        db: MongoDB database instance
        customer_name: Company/organization name
        customer_id: Unique customer identifier
    
    Returns:
        Generated API key string
    """
    api_keys = db['api_keys']
    
    key = generate_api_key()
    
    key_doc = {
        'key': key,
        'customer_id': customer_id,
        'customer_name': customer_name,
        'tier': 'enterprise',
        'allowed_sports': ['NBA', 'NFL', 'MLB', 'NHL'],  # Enterprise tier: All sports
        'rate_limit': 25,  # 25 req/s
        'daily_limit': None,  # Unlimited requests
        'active': True,
        'created_at': datetime.now(timezone.utc),
        'expires_at': datetime.now(timezone.utc) + timedelta(days=365)  # 1 year
    }
    
    api_keys.insert_one(key_doc)
    print(f"✅ Created Enterprise API key for {customer_name}: {key}")
    
    return key


def revoke_api_key(db, key: str) -> bool:
    """
    Revoke an API key (set active=False).
    
    Args:
        db: MongoDB database instance
        key: API key to revoke
    
    Returns:
        True if key was revoked, False if not found
    """
    api_keys = db['api_keys']
    
    result = api_keys.update_one(
        {'key': key},
        {'$set': {'active': False}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Revoked API key: {key}")
        return True
    else:
        print(f"❌ API key not found: {key}")
        return False


def example_documents():
    """
    Return example documents for the api_keys collection.
    """
    return [
        {
            # Starter tier - Small sportsbook
            "_id": "ObjectId('507f1f77bcf86cd799439011')",
            "key": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
            "customer_id": "cust_betsharp_inc",
            "customer_name": "BetSharp Inc.",
            "tier": "starter",
            "allowed_sports": ["NBA"],
            "rate_limit": 5,
            "daily_limit": 10000,
            "active": True,
            "created_at": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        },
        {
            # Growth tier - Regional sportsbook
            "_id": "ObjectId('507f1f77bcf86cd799439012')",
            "key": "z9y8x7w6v5u4t3s2r1q0p9o8n7m6l5k4",
            "customer_id": "cust_caesars_sports",
            "customer_name": "Caesars Sportsbook",
            "tier": "growth",
            "allowed_sports": ["NBA", "NFL"],
            "rate_limit": 10,
            "daily_limit": 50000,
            "active": True,
            "created_at": datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        },
        {
            # Enterprise tier - National sportsbook
            "_id": "ObjectId('507f1f77bcf86cd799439013')",
            "key": "f1e2d3c4b5a6978665544332211000ff",
            "customer_id": "cust_draftkings",
            "customer_name": "DraftKings",
            "tier": "enterprise",
            "allowed_sports": ["NBA", "NFL", "MLB", "NHL"],
            "rate_limit": 25,
            "daily_limit": None,  # Unlimited
            "active": True,
            "created_at": datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2025, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        }
    ]


# Schema validation (PyMongo 4.x validator)
api_keys_validator = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["key", "customer_id", "customer_name", "tier", "allowed_sports", 
                     "rate_limit", "active", "created_at"],
        "properties": {
            "key": {
                "bsonType": "string",
                "description": "Unique API key (UUID hex format)"
            },
            "customer_id": {
                "bsonType": "string",
                "description": "Unique customer identifier"
            },
            "customer_name": {
                "bsonType": "string",
                "description": "Company/organization name"
            },
            "tier": {
                "enum": ["starter", "growth", "enterprise"],
                "description": "Subscription tier"
            },
            "allowed_sports": {
                "bsonType": "array",
                "items": {
                    "enum": ["NBA", "NFL", "MLB", "NHL"]
                },
                "description": "Sports accessible with this key"
            },
            "rate_limit": {
                "bsonType": "int",
                "minimum": 1,
                "description": "Requests per second"
            },
            "daily_limit": {
                "bsonType": ["int", "null"],
                "description": "Max requests per day (null for unlimited)"
            },
            "active": {
                "bsonType": "bool",
                "description": "Whether key is active"
            },
            "created_at": {
                "bsonType": "date",
                "description": "Key creation timestamp"
            },
            "expires_at": {
                "bsonType": "date",
                "description": "Key expiration timestamp"
            }
        }
    }
}

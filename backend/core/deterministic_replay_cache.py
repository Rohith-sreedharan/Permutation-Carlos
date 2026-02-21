"""
Deterministic Replay Cache for Decision Engine
Section 15 - ENGINE LOCK Specification Compliance

Ensures: Identical inputs → Identical outputs + Identical decision_version

Caching Strategy:
- Key: (event_id, inputs_hash, market_type, decision_version)
- Value: Complete MarketDecision response
- TTL: No expiration (determinism records persist indefinitely)
- Backend: MongoDB collection 'deterministic_replay_cache'

Guarantees:
1. Same inputs always return byte-identical outputs (excluding timestamp fields)
2. decision_version is stable for cached inputs
3. Replay verification available for testing/auditing
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
import json
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError


class DeterministicReplayCache:
    """
    Manages deterministic replay cache for decision engine.
    
    Ensures identical inputs produce identical outputs.
    Critical for Section 15 compliance and testing.
    """
    
    def __init__(self, mongo_uri: Optional[str] = None):
        """
        Initialize deterministic replay cache.
        
        Args:
            mongo_uri: MongoDB connection string (defaults to localhost)
        """
        if mongo_uri is None:
            mongo_uri = "mongodb://localhost:27017/"
        
        self.client = MongoClient(mongo_uri)
        self.db = self.client["beatvegas"]
        self.collection = self.db["deterministic_replay_cache"]
        
        self._ensure_indexes()
    
    def _ensure_indexes(self) -> None:
        """Create indexes for efficient cache lookups."""
        try:
            # Primary lookup index: (event_id, inputs_hash, market_type, decision_version)
            self.collection.create_index([
                ("event_id", ASCENDING),
                ("inputs_hash", ASCENDING),
                ("market_type", ASCENDING),
                ("decision_version", ASCENDING)
            ], name="cache_lookup", unique=True)
            
            # Secondary index: inputs_hash for debugging
            self.collection.create_index([
                ("inputs_hash", ASCENDING)
            ], name="inputs_hash_idx")
            
            # Timestamp index for monitoring
            self.collection.create_index([
                ("cached_at", ASCENDING)
            ], name="cached_at_idx")
            
        except PyMongoError as e:
            print(f"[WARNING] Failed to create indexes for deterministic_replay_cache: {e}")
    
    def _compute_cache_key(
        self,
        event_id: str,
        inputs_hash: str,
        market_type: str,
        decision_version: str
    ) -> str:
        """
        Compute cache key from inputs.
        
        Args:
            event_id: Event identifier
            inputs_hash: Hash of input parameters
            market_type: "spread" or "total"
            decision_version: Current decision version
        
        Returns:
            str: Cache key (SHA256 hash)
        """
        key_data = f"{event_id}|{inputs_hash}|{market_type}|{decision_version}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get_cached_decision(
        self,
        event_id: str,
        inputs_hash: str,
        market_type: str,
        decision_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached decision if exists.
        
        Args:
            event_id: Event identifier
            inputs_hash: Hash of input parameters
            market_type: "spread" or "total"
            decision_version: Current decision version
        
        Returns:
            dict: Cached decision response or None if cache miss
        """
        try:
            cache_key = self._compute_cache_key(
                event_id, inputs_hash, market_type, decision_version
            )
            
            cached = self.collection.find_one({
                "cache_key": cache_key,
                "event_id": event_id,
                "inputs_hash": inputs_hash,
                "market_type": market_type,
                "decision_version": decision_version
            })
            
            if cached:
                # Return the cached decision payload
                decision = cached.get("decision_payload")
                if decision:
                    print(f"[CACHE HIT] Deterministic replay: {event_id} | {market_type}")
                    return decision
            
            return None
        
        except PyMongoError as e:
            print(f"[ERROR] Cache lookup failed: {e}")
            return None
    
    def cache_decision(
        self,
        event_id: str,
        inputs_hash: str,
        market_type: str,
        decision_version: str,
        decision_payload: Dict[str, Any]
    ) -> bool:
        """
        Cache decision for deterministic replay.
        
        Args:
            event_id: Event identifier
            inputs_hash: Hash of input parameters
            market_type: "spread" or "total"
            decision_version: Current decision version
            decision_payload: Complete MarketDecision response
        
        Returns:
            bool: True if cached successfully, False otherwise
        """
        try:
            cache_key = self._compute_cache_key(
                event_id, inputs_hash, market_type, decision_version
            )
            
            cache_entry = {
                "cache_key": cache_key,
                "event_id": event_id,
                "inputs_hash": inputs_hash,
                "market_type": market_type,
                "decision_version": decision_version,
                "decision_payload": decision_payload,
                "cached_at": datetime.now(timezone.utc),
                "cache_ttl": None  # No expiration (determinism records persist)
            }
            
            # Upsert: insert if new, replace if exists
            self.collection.replace_one(
                {
                    "cache_key": cache_key,
                    "event_id": event_id,
                    "inputs_hash": inputs_hash,
                    "market_type": market_type,
                    "decision_version": decision_version
                },
                cache_entry,
                upsert=True
            )
            
            return True
        
        except PyMongoError as e:
            print(f"[ERROR] Failed to cache decision: {e}")
            return False
    
    def verify_determinism(
        self,
        event_id: str,
        inputs_hash: str,
        market_type: str,
        decision_version: str,
        current_decision: Dict[str, Any],
        exclude_fields: Optional[list] = None
    ) -> tuple[bool, list]:
        """
        Verify that current decision matches cached decision.
        
        Used for determinism testing and auditing.
        
        Args:
            event_id: Event identifier
            inputs_hash: Hash of input parameters
            market_type: "spread" or "total"
            decision_version: Current decision version
            current_decision: Current decision output
            exclude_fields: Fields to exclude from comparison (e.g., timestamps)
        
        Returns:
            tuple: (is_deterministic: bool, differences: list)
        """
        if exclude_fields is None:
            # Default: exclude timestamp fields from comparison
            exclude_fields = ["timestamp", "trace_id", "cached_at"]
        
        cached = self.get_cached_decision(
            event_id, inputs_hash, market_type, decision_version
        )
        
        if cached is None:
            return False, ["No cached decision found"]
        
        # Compare decisions excluding specified fields
        differences = []
        
        def compare_dicts(d1, d2, path=""):
            """Recursively compare two dictionaries."""
            for key in set(list(d1.keys()) + list(d2.keys())):
                if key in exclude_fields:
                    continue
                
                current_path = f"{path}.{key}" if path else key
                
                if key not in d1:
                    differences.append(f"{current_path}: missing in current")
                elif key not in d2:
                    differences.append(f"{current_path}: missing in cached")
                elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    compare_dicts(d1[key], d2[key], current_path)
                elif d1[key] != d2[key]:
                    differences.append(
                        f"{current_path}: current={d1[key]} vs cached={d2[key]}"
                    )
        
        compare_dicts(current_decision, cached)
        
        is_deterministic = len(differences) == 0
        return is_deterministic, differences
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.
        
        Returns:
            dict: Cache statistics (count, size, etc.)
        """
        try:
            total_entries = self.collection.count_documents({})
            
            # Count by market type
            spread_count = self.collection.count_documents({"market_type": "spread"})
            total_count = self.collection.count_documents({"market_type": "total"})
            
            # Get oldest and newest entries
            oldest = self.collection.find_one(sort=[("cached_at", ASCENDING)])
            newest = self.collection.find_one(sort=[("cached_at", -1)])
            
            return {
                "total_entries": total_entries,
                "spread_decisions": spread_count,
                "total_decisions": total_count,
                "oldest_entry": oldest.get("cached_at") if oldest else None,
                "newest_entry": newest.get("cached_at") if newest else None,
                "cache_ttl_policy": "no_expiration"
            }
        
        except PyMongoError as e:
            print(f"[ERROR] Failed to get cache statistics: {e}")
            return {"error": str(e)}
    
    def clear_cache(self, confirm: bool = False) -> bool:
        """
        Clear all cache entries.
        
        WARNING: Only use for testing. Production cache should never be cleared.
        
        Args:
            confirm: Must be True to actually clear cache
        
        Returns:
            bool: True if cleared successfully
        """
        if not confirm:
            print("[WARNING] clear_cache() requires confirm=True to proceed")
            return False
        
        try:
            result = self.collection.delete_many({})
            print(f"[CACHE] Cleared {result.deleted_count} entries")
            return True
        except PyMongoError as e:
            print(f"[ERROR] Failed to clear cache: {e}")
            return False


# Singleton instance
_replay_cache_instance: Optional[DeterministicReplayCache] = None


def get_replay_cache(mongo_uri: Optional[str] = None) -> DeterministicReplayCache:
    """
    Get singleton replay cache instance.
    
    Args:
        mongo_uri: MongoDB connection string (optional)
    
    Returns:
        DeterministicReplayCache: Singleton instance
    """
    global _replay_cache_instance
    if _replay_cache_instance is None:
        _replay_cache_instance = DeterministicReplayCache(mongo_uri)
    return _replay_cache_instance

"""
Feature Flags Service - Runtime Control & Kill Switches
Status: LOCKED - INSTITUTIONAL GRADE

Manages feature flags for:
- Gradual rollout (canary deployments)
- Kill switches (instant disable on issues)
- A/B testing (future)
- Tenant-specific overrides (future)

CRITICAL FLAGS:
- FEATURE_TELEGRAM_AUTOPUBLISH: Master kill switch for Telegram publishing
- FEATURE_LLM_COPY_AGENT: Enable LLM for template rendering vs deterministic
- FEATURE_INTEGRITY_SENTINEL: Enable monitoring (should always be ON)
- FEATURE_AUTOROLLBACK_ON_INTEGRITY: Auto-rollback on integrity failures
"""

import logging
from typing import Dict, Optional
from datetime import datetime
from pymongo.database import Database


logger = logging.getLogger(__name__)


class FeatureFlagService:
    """
    Feature flag management and runtime enforcement.
    
    Flags are stored in MongoDB for immediate effect across all instances.
    No restart required - flags checked on every request.
    """
    
    # Default flag states (used if not in DB)
    DEFAULT_FLAGS = {
        "FEATURE_TELEGRAM_AUTOPUBLISH": {
            "enabled": False,  # Default OFF until validated
            "description": "Enable automatic Telegram publishing (kill switch for integrity issues)",
        },
        "FEATURE_LLM_COPY_AGENT": {
            "enabled": False,  # Default OFF - use deterministic templates
            "description": "Enable LLM for Telegram copy generation (vs deterministic templates)",
        },
        "FEATURE_INTEGRITY_SENTINEL": {
            "enabled": True,  # Default ON - always monitor
            "description": "Enable IntegritySentinel monitoring and kill switches",
        },
        "FEATURE_AUTOROLLBACK_ON_INTEGRITY": {
            "enabled": True,  # Default ON - auto-rollback on issues
            "description": "Automatically rollback to LKG on integrity failures",
        },
        "FEATURE_PARLAY_ARCHITECT": {
            "enabled": True,  # Default ON
            "description": "Enable Parlay Architect feature",
        },
        "FEATURE_UI_SELECTION_ID_ENFORCEMENT": {
            "enabled": True,  # Default ON - critical for correctness
            "description": "Enforce selection_id-only rendering in UI (no inference)",
        },
        "FEATURE_UNIVERSAL_TIER_CLASSIFIER": {
            "enabled": True,  # Default ON
            "description": "Enable universal tier classifier",
        },
    }
    
    def __init__(self, db: Database):
        self.db = db
        self._cache: Dict[str, bool] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 10  # Cache flags for 10 seconds
    
    def is_enabled(self, flag_name: str, default: Optional[bool] = None) -> bool:
        """
        Check if feature flag is enabled.
        
        Args:
            flag_name: Flag name (e.g., "FEATURE_TELEGRAM_AUTOPUBLISH")
            default: Default value if flag not found (overrides DEFAULT_FLAGS)
        
        Returns:
            True if enabled, False otherwise
        """
        # Check cache first
        if self._is_cache_valid():
            if flag_name in self._cache:
                return self._cache[flag_name]
        
        # Fetch from DB
        flag_doc = self.db.feature_flags.find_one({"flag_name": flag_name})
        
        if flag_doc:
            enabled = flag_doc.get("enabled", False)
        else:
            # Use provided default or DEFAULT_FLAGS
            if default is not None:
                enabled = default
            else:
                enabled = self.DEFAULT_FLAGS.get(flag_name, {}).get("enabled", False)
        
        # Update cache
        self._cache[flag_name] = enabled
        self._cache_timestamp = datetime.utcnow()
        
        return enabled
    
    def set_flag(
        self,
        flag_name: str,
        enabled: bool,
        changed_by: str,
        reason: str
    ) -> bool:
        """
        Set feature flag value.
        
        Args:
            flag_name: Flag name
            enabled: True to enable, False to disable
            changed_by: Who made the change (user, service, etc.)
            reason: Reason for change
        
        Returns:
            True if successful
        """
        # Get default description if exists
        description = self.DEFAULT_FLAGS.get(flag_name, {}).get("description", "")
        
        # Upsert flag
        self.db.feature_flags.update_one(
            {"flag_name": flag_name},
            {
                "$set": {
                    "enabled": enabled,
                    "changed_by": changed_by,
                    "changed_at": datetime.utcnow(),
                    "reason": reason,
                },
                "$setOnInsert": {
                    "description": description,
                }
            },
            upsert=True
        )
        
        # Invalidate cache
        self._invalidate_cache()
        
        logger.info(
            f"Feature flag {flag_name} set to {enabled} by {changed_by} (reason: {reason})"
        )
        
        return True
    
    def get_all_flags(self) -> Dict[str, Dict]:
        """
        Get all feature flags with their current state.
        
        Returns:
            Dict of flag_name -> flag data
        """
        flags = {}
        
        # Fetch all from DB
        for flag_doc in self.db.feature_flags.find():
            flag_name = flag_doc["flag_name"]
            flags[flag_name] = {
                "enabled": flag_doc.get("enabled", False),
                "description": flag_doc.get("description", ""),
                "changed_by": flag_doc.get("changed_by", ""),
                "changed_at": flag_doc.get("changed_at"),
                "reason": flag_doc.get("reason", ""),
            }
        
        # Add defaults for flags not in DB
        for flag_name, flag_default in self.DEFAULT_FLAGS.items():
            if flag_name not in flags:
                flags[flag_name] = {
                    "enabled": flag_default["enabled"],
                    "description": flag_default["description"],
                    "changed_by": "default",
                    "changed_at": None,
                    "reason": "Default value",
                }
        
        return flags
    
    def initialize_defaults(self):
        """
        Initialize all default flags in database (if not exists).
        
        Run this on first deployment.
        """
        for flag_name, flag_data in self.DEFAULT_FLAGS.items():
            existing = self.db.feature_flags.find_one({"flag_name": flag_name})
            
            if not existing:
                self.db.feature_flags.insert_one({
                    "flag_name": flag_name,
                    "enabled": flag_data["enabled"],
                    "description": flag_data["description"],
                    "changed_by": "system_init",
                    "changed_at": datetime.utcnow(),
                    "reason": "Initial setup",
                })
                logger.info(f"Initialized flag {flag_name} = {flag_data['enabled']}")
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        if self._cache_timestamp is None:
            return False
        
        age_seconds = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return age_seconds < self._cache_ttl_seconds
    
    def _invalidate_cache(self):
        """Invalidate cache (after flag changes)"""
        self._cache = {}
        self._cache_timestamp = None


# ==================== CONTEXT MANAGER FOR FEATURE GATES ====================

class FeatureGate:
    """
    Context manager for feature-gated code blocks.
    
    Usage:
        with FeatureGate(flags, "FEATURE_TELEGRAM_AUTOPUBLISH") as enabled:
            if enabled:
                # Feature code
            else:
                # Fallback code
    """
    
    def __init__(self, flag_service: FeatureFlagService, flag_name: str):
        self.flag_service = flag_service
        self.flag_name = flag_name
        self.enabled = False
    
    def __enter__(self):
        self.enabled = self.flag_service.is_enabled(self.flag_name)
        return self.enabled
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# ==================== DECORATOR FOR FEATURE GATES ====================

def feature_flag_required(flag_name: str, flag_service: FeatureFlagService):
    """
    Decorator to require feature flag to be enabled.
    
    Usage:
        @feature_flag_required("FEATURE_TELEGRAM_AUTOPUBLISH", flags)
        def publish_to_telegram():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not flag_service.is_enabled(flag_name):
                logger.warning(
                    f"Feature {flag_name} disabled - skipping {func.__name__}"
                )
                return None
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test feature flags
    import os
    from pymongo import MongoClient
    
    # Connect to DB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Create service
    flags = FeatureFlagService(db)
    
    # Initialize defaults
    flags.initialize_defaults()
    
    # Test flag checks
    print("=== Feature Flags ===")
    all_flags = flags.get_all_flags()
    for flag_name, flag_data in all_flags.items():
        status = "✅ ENABLED" if flag_data["enabled"] else "❌ DISABLED"
        print(f"{flag_name}: {status}")
        print(f"  Description: {flag_data['description']}")
        print(f"  Changed by: {flag_data['changed_by']} ({flag_data['reason']})")
        print()
    
    # Test flag change
    print("=== Testing Flag Change ===")
    flags.set_flag(
        "FEATURE_TELEGRAM_AUTOPUBLISH",
        enabled=True,
        changed_by="test_script",
        reason="Testing flag change"
    )
    
    enabled = flags.is_enabled("FEATURE_TELEGRAM_AUTOPUBLISH")
    print(f"FEATURE_TELEGRAM_AUTOPUBLISH: {enabled}")
    
    # Test context manager
    print("\n=== Testing Feature Gate ===")
    with FeatureGate(flags, "FEATURE_TELEGRAM_AUTOPUBLISH") as enabled:
        if enabled:
            print("✅ Feature is enabled - executing feature code")
        else:
            print("❌ Feature is disabled - using fallback")

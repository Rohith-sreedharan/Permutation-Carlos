"""
BeatVegas Kill Switch — Emergency Circuit Breaker

ONE flag to:
1. Freeze new simulations
2. Serve last-known-good results
3. Disable posting automation
4. NO manual intervention required

Usage:
    from backend.core.kill_switch import KillSwitch
    
    # Check if operations allowed
    if not KillSwitch.is_active():
        # Normal operation
        run_simulation()
    else:
        # Serve cached results
        serve_last_known_good()
"""
import os
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class KillSwitch:
    """
    Global kill switch for emergency shutdown
    
    Activated by environment variable or manual override file
    """
    
    # Environment variable to activate kill switch
    ENV_VAR = "BEATVEGAS_KILL_SWITCH"
    
    # Manual override file (presence = activated)
    OVERRIDE_FILE = "/tmp/beatvegas_kill_switch.lock"
    
    # Last known state
    _cached_state: Optional[bool] = None
    _cached_at: Optional[datetime] = None
    _cache_ttl_seconds = 10  # Re-check every 10 seconds
    
    @classmethod
    def is_active(cls) -> bool:
        """
        Check if kill switch is active
        
        Returns True if:
        1. Environment variable BEATVEGAS_KILL_SWITCH=1
        2. Override file exists at /tmp/beatvegas_kill_switch.lock
        
        Uses 10-second cache to avoid filesystem/env checks on every request
        """
        now = datetime.now(timezone.utc)
        
        # Use cache if fresh
        if cls._cached_state is not None and cls._cached_at is not None:
            age_seconds = (now - cls._cached_at).total_seconds()
            if age_seconds < cls._cache_ttl_seconds:
                return cls._cached_state
        
        # Check activation sources
        active = cls._check_activation()
        
        # Update cache
        cls._cached_state = active
        cls._cached_at = now
        
        if active:
            logger.warning("🔴 KILL SWITCH ACTIVE - Operations frozen")
        
        return active
    
    @classmethod
    def _check_activation(cls) -> bool:
        """Internal: Check all activation sources"""
        # 1. Environment variable
        if os.environ.get(cls.ENV_VAR) == "1":
            logger.warning(f"🔴 Kill switch activated via {cls.ENV_VAR}=1")
            return True
        
        # 2. Override file
        if os.path.exists(cls.OVERRIDE_FILE):
            logger.warning(f"🔴 Kill switch activated via {cls.OVERRIDE_FILE}")
            return True
        
        return False
    
    @classmethod
    def activate(cls, reason: str = "Manual activation") -> None:
        """
        Manually activate kill switch
        
        Creates override file and logs reason
        """
        try:
            with open(cls.OVERRIDE_FILE, 'w') as f:
                f.write(f"ACTIVATED: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"REASON: {reason}\n")
            
            # Clear cache to force immediate activation
            cls._cached_state = None
            cls._cached_at = None
            
            logger.critical(f"🔴 KILL SWITCH ACTIVATED: {reason}")
        except Exception as e:
            logger.error(f"Failed to activate kill switch: {e}")
    
    @classmethod
    def deactivate(cls) -> None:
        """
        Deactivate kill switch
        
        Removes override file (environment variable must be cleared manually)
        """
        try:
            if os.path.exists(cls.OVERRIDE_FILE):
                os.remove(cls.OVERRIDE_FILE)
                logger.info("✅ Kill switch deactivated (override file removed)")
            
            # Clear cache
            cls._cached_state = None
            cls._cached_at = None
            
        except Exception as e:
            logger.error(f"Failed to deactivate kill switch: {e}")
    
    @classmethod
    def get_status(cls) -> dict:
        """
        Get detailed kill switch status
        
        Returns:
            {
                "active": bool,
                "sources": {
                    "env_var": bool,
                    "override_file": bool
                },
                "activated_at": str | None,
                "reason": str | None
            }
        """
        env_active = os.environ.get(cls.ENV_VAR) == "1"
        file_active = os.path.exists(cls.OVERRIDE_FILE)
        
        activated_at = None
        reason = None
        
        if file_active:
            try:
                with open(cls.OVERRIDE_FILE, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        if line.startswith("ACTIVATED:"):
                            activated_at = line.split(":", 1)[1].strip()
                        if line.startswith("REASON:"):
                            reason = line.split(":", 1)[1].strip()
            except Exception:
                pass
        
        return {
            "active": env_active or file_active,
            "sources": {
                "env_var": env_active,
                "override_file": file_active
            },
            "activated_at": activated_at,
            "reason": reason
        }


# ============================================================================
# KILL SWITCH DECORATORS
# ============================================================================

def require_operations_enabled(fallback_value=None):
    """
    Decorator to prevent function execution when kill switch is active
    
    Usage:
        @require_operations_enabled(fallback_value={"error": "Service unavailable"})
        def run_simulation():
            # ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if KillSwitch.is_active():
                logger.warning(f"🔴 {func.__name__} blocked by kill switch")
                return fallback_value
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# LAST-KNOWN-GOOD CACHE
# ============================================================================

class LastKnownGoodCache:
    """
    Cache for serving last-known-good simulation results when kill switch active
    
    Stores results in-memory with TTL
    """
    
    _cache: dict = {}
    _cache_ttl_seconds = 3600  # 1 hour
    
    @classmethod
    def set(cls, event_id: str, simulation: dict) -> None:
        """Store simulation in cache"""
        cls._cache[event_id] = {
            "simulation": simulation,
            "cached_at": datetime.now(timezone.utc)
        }
    
    @classmethod
    def get(cls, event_id: str) -> Optional[dict]:
        """
        Get cached simulation if fresh
        
        Returns None if:
        - Not in cache
        - Older than TTL
        """
        if event_id not in cls._cache:
            return None
        
        entry = cls._cache[event_id]
        age_seconds = (datetime.now(timezone.utc) - entry["cached_at"]).total_seconds()
        
        if age_seconds > cls._cache_ttl_seconds:
            # Expired - remove from cache
            del cls._cache[event_id]
            return None
        
        return entry["simulation"]
    
    @classmethod
    def clear(cls) -> None:
        """Clear all cached simulations"""
        cls._cache.clear()
        logger.info("🗑️ Last-known-good cache cleared")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
EXAMPLE 1: Check before simulation
-----------------------------------
from backend.core.kill_switch import KillSwitch, LastKnownGoodCache

def get_simulation(event_id: str):
    if KillSwitch.is_active():
        # Serve cached result
        cached = LastKnownGoodCache.get(event_id)
        if cached:
            return {
                "simulation": cached,
                "source": "last_known_good",
                "warning": "Kill switch active - serving cached result"
            }
        return {
            "error": "Service temporarily unavailable",
            "kill_switch_active": True
        }
    
    # Normal operation
    simulation = run_monte_carlo(event_id)
    LastKnownGoodCache.set(event_id, simulation)
    return simulation


EXAMPLE 2: Telegram posting guard
----------------------------------
from backend.core.kill_switch import require_operations_enabled

@require_operations_enabled(fallback_value=None)
def post_to_telegram(pick: dict):
    # Only runs if kill switch is inactive
    send_telegram_message(pick)


EXAMPLE 3: Manual activation (SSH or admin panel)
--------------------------------------------------
from backend.core.kill_switch import KillSwitch

# Activate
KillSwitch.activate(reason="High error rate detected - freezing operations")

# Check status
status = KillSwitch.get_status()
print(status)
# {
#     "active": True,
#     "sources": {"env_var": False, "override_file": True},
#     "activated_at": "2026-02-02T10:30:00Z",
#     "reason": "High error rate detected - freezing operations"
# }

# Deactivate
KillSwitch.deactivate()


EXAMPLE 4: FastAPI endpoint
----------------------------
from fastapi import HTTPException
from backend.core.kill_switch import KillSwitch

@app.get("/api/simulations/{event_id}")
async def get_simulation(event_id: str):
    if KillSwitch.is_active():
        # Return cached result or 503
        cached = LastKnownGoodCache.get(event_id)
        if cached:
            return {
                "simulation": cached,
                "source": "cache",
                "kill_switch_active": True
            }
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable - kill switch active"
        )
    
    # Normal operation
    ...
"""

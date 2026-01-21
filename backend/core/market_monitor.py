"""
Market Movement Monitor - Execution Guardrails
==============================================
Tracks live market prices and auto-invalidates plays when guardrails breached.

Key Features:
- Continuous market monitoring post-publication
- Auto-update to PRICE_MOVED status
- Optional user notifications
- Playable limit enforcement
"""

from __future__ import annotations
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone
from enum import Enum
import logging

from .simulation_context import SimulationResult, SimulationStatus

logger = logging.getLogger(__name__)


class MarketMovementEvent(str, Enum):
    """Types of market movement events"""
    LINE_MOVED = "LINE_MOVED"
    ODDS_MOVED = "ODDS_MOVED"
    MARKET_SUSPENDED = "MARKET_SUSPENDED"
    GUARDRAIL_BREACHED = "GUARDRAIL_BREACHED"


class MarketMonitor:
    """
    Monitor live market prices and enforce execution guardrails.
    
    Automatically invalidates plays when:
    - Line moves past playable_line_min/max
    - Odds move past playable_odds_min
    - Market suspends
    """
    
    def __init__(
        self,
        db_simulation_results,
        db_market_movements,
        notification_callback: Optional[Callable] = None,
    ):
        """
        Args:
            db_simulation_results: MongoDB collection for simulation results
            db_market_movements: MongoDB collection for market movement events
            notification_callback: Optional function to notify users of invalidations
        """
        self.db_results = db_simulation_results
        self.db_movements = db_market_movements
        self.notify = notification_callback
    
    def check_market_movement(
        self,
        game_id: str,
        market_type: str,
        current_line: Optional[float],
        current_odds: Optional[int],
    ) -> Dict[str, Any]:
        """
        Check if current market prices are still playable.
        
        Returns:
            {
                "is_playable": bool,
                "violations": List[str],
                "action_taken": Optional[str],
            }
        """
        # Get active simulation result for this market
        result_doc = self.db_results.find_one({
            "game_id": game_id,
            "market_type": market_type,
            "status": {"$in": ["COMPLETED", "CACHED"]},
        })
        
        if result_doc is None:
            return {
                "is_playable": False,
                "violations": ["no_active_result"],
                "action_taken": None,
            }
        
        # Reconstruct result object (simplified)
        playable_line_min = result_doc.get("playable_line_min")
        playable_line_max = result_doc.get("playable_line_max")
        playable_odds_min = result_doc.get("playable_odds_min")
        
        violations = []
        
        # Check line guardrails
        if current_line is not None:
            if playable_line_min is not None and current_line < playable_line_min:
                violations.append(f"line_below_min:{current_line}<{playable_line_min}")
            
            if playable_line_max is not None and current_line > playable_line_max:
                violations.append(f"line_above_max:{current_line}>{playable_line_max}")
        
        # Check odds guardrails
        if current_odds is not None:
            if playable_odds_min is not None and current_odds < playable_odds_min:
                violations.append(f"odds_below_min:{current_odds}<{playable_odds_min}")
        
        is_playable = len(violations) == 0
        
        # Take action if guardrails breached
        action_taken = None
        if not is_playable:
            action_taken = self._invalidate_result(
                game_id,
                market_type,
                violations,
                current_line,
                current_odds,
            )
        
        return {
            "is_playable": is_playable,
            "violations": violations,
            "action_taken": action_taken,
        }
    
    def _invalidate_result(
        self,
        game_id: str,
        market_type: str,
        violations: List[str],
        current_line: Optional[float],
        current_odds: Optional[int],
    ) -> str:
        """
        Mark simulation result as PRICE_MOVED.
        
        Logs movement event and optionally notifies users.
        """
        # Update result status
        self.db_results.update_one(
            {
                "game_id": game_id,
                "market_type": market_type,
                "status": {"$in": ["COMPLETED", "CACHED"]},
            },
            {
                "$set": {
                    "status": SimulationStatus.PRICE_MOVED.value,
                    "invalidated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "invalidation_reason": violations,
                },
            },
        )
        
        # Log movement event
        event_doc = {
            "game_id": game_id,
            "market_type": market_type,
            "event_type": MarketMovementEvent.GUARDRAIL_BREACHED.value,
            "violations": violations,
            "current_line": current_line,
            "current_odds": current_odds,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.db_movements.insert_one(event_doc)
        
        logger.warning(
            f"GUARDRAIL BREACHED: game={game_id}, market={market_type}, "
            f"violations={violations}"
        )
        
        # Notify users if callback provided
        if self.notify:
            try:
                self.notify(
                    game_id=game_id,
                    market_type=market_type,
                    reason="PRICE_MOVED",
                    details=violations,
                )
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")
        
        return "result_invalidated"
    
    def monitor_all_active_results(
        self,
        current_markets: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Batch check all active simulation results against current market prices.
        
        Args:
            current_markets: {
                "game_id:market_type": {
                    "line": Optional[float],
                    "odds": Optional[int],
                },
                ...
            }
        
        Returns:
            {
                "total_checked": int,
                "still_playable": int,
                "invalidated": int,
                "violations": List[Dict],
            }
        """
        active_results = self.db_results.find({
            "status": {"$in": ["COMPLETED", "CACHED"]},
        })
        
        total_checked = 0
        still_playable = 0
        invalidated = 0
        violations_list = []
        
        for result_doc in active_results:
            game_id = result_doc["game_id"]
            market_type = result_doc["market_type"]
            
            market_key = f"{game_id}:{market_type}"
            current_market = current_markets.get(market_key)
            
            if current_market is None:
                # Market not found in feed (suspended?)
                continue
            
            total_checked += 1
            
            check_result = self.check_market_movement(
                game_id=game_id,
                market_type=market_type,
                current_line=current_market.get("line"),
                current_odds=current_market.get("odds"),
            )
            
            if check_result["is_playable"]:
                still_playable += 1
            else:
                invalidated += 1
                violations_list.append({
                    "game_id": game_id,
                    "market_type": market_type,
                    "violations": check_result["violations"],
                })
        
        logger.info(
            f"Market monitor: checked={total_checked}, "
            f"playable={still_playable}, invalidated={invalidated}"
        )
        
        return {
            "total_checked": total_checked,
            "still_playable": still_playable,
            "invalidated": invalidated,
            "violations": violations_list,
        }


class RerunEligibilityChecker:
    """
    Enforce rerun eligibility rules.
    
    Prevents manual rerun spam by checking if context has materially changed.
    """
    
    def __init__(self, db_simulation_results):
        """
        Args:
            db_simulation_results: MongoDB collection for simulation results
        """
        self.db_results = db_simulation_results
    
    def is_rerun_allowed(
        self,
        game_id: str,
        market_type: str,
        new_context_hash: str,
    ) -> Dict[str, Any]:
        """
        Check if rerun is allowed for this game/market.
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "last_context_hash": Optional[str],
            }
        """
        # Get most recent simulation for this game/market
        last_result = self.db_results.find_one(
            {
                "game_id": game_id,
                "market_type": market_type,
            },
            sort=[("created_at_utc", -1)],
        )
        
        if last_result is None:
            # No prior simulation, rerun allowed (actually first run)
            return {
                "allowed": True,
                "reason": "first_run",
                "last_context_hash": None,
            }
        
        last_context_hash = last_result["context_hash"]
        
        if last_context_hash == new_context_hash:
            # Context unchanged, rerun NOT allowed
            return {
                "allowed": False,
                "reason": "context_unchanged",
                "last_context_hash": last_context_hash,
            }
        
        # Context changed, rerun allowed
        return {
            "allowed": True,
            "reason": "context_changed",
            "last_context_hash": last_context_hash,
        }

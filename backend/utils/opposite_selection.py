"""
PROOF ARTIFACT #3: Opposite Selection Determinism
==================================================

Implements get_opposite_selection_id() with ops alerts for missing opposites.

This function is CRITICAL for:
1. TAKE_OPPOSITE actions
2. Hedge calculations
3. Parlay leg validation
4. UI display of both sides
"""

import logging
from typing import Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class MarketType(str, Enum):
    """Market types with opposite selections"""
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    MONEYLINE_2WAY = "MONEYLINE_2WAY"


class OppositeSelectionError(Exception):
    """Raised when opposite selection cannot be determined"""
    pass


def get_opposite_selection_id(
    event_id: str,
    market_type: MarketType,
    selection_id: str
) -> str:
    """
    Get the opposite selection ID for a given market selection.
    
    This function enforces deterministic opposite selection logic:
    - SPREAD: HOME ↔ AWAY
    - TOTAL: OVER ↔ UNDER  
    - MONEYLINE: HOME ↔ AWAY
    
    Args:
        event_id: Event identifier (for logging/alerting)
        market_type: Type of market
        selection_id: Current selection ID
        
    Returns:
        Opposite selection ID
        
    Raises:
        OppositeSelectionError: If opposite cannot be determined
        
    Examples:
        >>> get_opposite_selection_id("evt_123", MarketType.SPREAD, "evt_123_spread_home")
        "evt_123_spread_away"
        
        >>> get_opposite_selection_id("evt_123", MarketType.TOTAL, "evt_123_total_over")
        "evt_123_total_under"
    """
    
    if market_type == MarketType.SPREAD:
        # SPREAD: HOME ↔ AWAY
        if "_spread_home" in selection_id:
            opposite = selection_id.replace("_spread_home", "_spread_away")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        elif "_spread_away" in selection_id:
            opposite = selection_id.replace("_spread_away", "_spread_home")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        else:
            error_msg = f"OPPOSITE_SELECTION_MISSING: Cannot determine opposite for SPREAD selection_id={selection_id}"
            logger.error(error_msg)
            _send_ops_alert(event_id, market_type, selection_id, error_msg)
            raise OppositeSelectionError(error_msg)
    
    elif market_type == MarketType.TOTAL:
        # TOTAL: OVER ↔ UNDER
        if "_total_over" in selection_id:
            opposite = selection_id.replace("_total_over", "_total_under")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        elif "_total_under" in selection_id:
            opposite = selection_id.replace("_total_under", "_total_over")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        else:
            error_msg = f"OPPOSITE_SELECTION_MISSING: Cannot determine opposite for TOTAL selection_id={selection_id}"
            logger.error(error_msg)
            _send_ops_alert(event_id, market_type, selection_id, error_msg)
            raise OppositeSelectionError(error_msg)
    
    elif market_type == MarketType.MONEYLINE_2WAY:
        # MONEYLINE: HOME ↔ AWAY
        if "_ml_home" in selection_id:
            opposite = selection_id.replace("_ml_home", "_ml_away")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        elif "_ml_away" in selection_id:
            opposite = selection_id.replace("_ml_away", "_ml_home")
            logger.debug(f"Opposite selection: {selection_id} → {opposite}")
            return opposite
        else:
            error_msg = f"OPPOSITE_SELECTION_MISSING: Cannot determine opposite for MONEYLINE selection_id={selection_id}"
            logger.error(error_msg)
            _send_ops_alert(event_id, market_type, selection_id, error_msg)
            raise OppositeSelectionError(error_msg)
    
    else:
        error_msg = f"UNKNOWN_MARKET_TYPE: {market_type}"
        logger.error(error_msg)
        raise OppositeSelectionError(error_msg)


def get_opposite_selection_safe(
    event_id: str,
    market_type: MarketType,
    selection_id: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Safe version that returns (opposite_id, error) instead of raising.
    
    Returns:
        (opposite_selection_id, error_message)
        If successful: (opposite_id, None)
        If failed: (None, error_message)
    """
    try:
        opposite = get_opposite_selection_id(event_id, market_type, selection_id)
        return (opposite, None)
    except OppositeSelectionError as e:
        return (None, str(e))


def _send_ops_alert(
    event_id: str,
    market_type: MarketType,
    selection_id: str,
    error_msg: str
):
    """
    Send ops alert for missing opposite selection.
    
    This is a CRITICAL error that indicates:
    1. Malformed selection_id
    2. Database corruption
    3. Selection ID schema violation
    
    Ops must investigate immediately.
    """
    alert_payload = {
        "alert_type": "OPPOSITE_SELECTION_MISSING",
        "severity": "CRITICAL",
        "event_id": event_id,
        "market_type": market_type.value,
        "selection_id": selection_id,
        "error": error_msg,
        "impact": "Cannot execute TAKE_OPPOSITE actions, hedge calculations, or parlay validation",
        "action_required": "Investigate selection_id schema for this event"
    }
    
    # Log to ops monitoring system
    logger.critical(f"OPS_ALERT: {alert_payload}")
    
    # In production, would send to ops dashboard/Slack/PagerDuty
    # For now, log to file
    try:
        with open("logs/ops_alerts.log", "a") as f:
            import json
            from datetime import datetime, timezone
            alert_payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            f.write(json.dumps(alert_payload) + "\n")
    except Exception as e:
        logger.error(f"Failed to write ops alert to file: {e}")


# Example usage and tests
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PROOF ARTIFACT #3: Opposite Selection Determinism")
    print("=" * 70 + "\n")
    
    # Test SPREAD opposites
    print("Testing SPREAD market...")
    home_id = "event_abc123_spread_home"
    away_id = get_opposite_selection_id("event_abc123", MarketType.SPREAD, home_id)
    print(f"  {home_id} → {away_id}")
    assert away_id == "event_abc123_spread_away"
    
    # Test reverse
    back_to_home = get_opposite_selection_id("event_abc123", MarketType.SPREAD, away_id)
    print(f"  {away_id} → {back_to_home}")
    assert back_to_home == home_id
    print("✅ SPREAD opposites verified\n")
    
    # Test TOTAL opposites
    print("Testing TOTAL market...")
    over_id = "event_abc123_total_over"
    under_id = get_opposite_selection_id("event_abc123", MarketType.TOTAL, over_id)
    print(f"  {over_id} → {under_id}")
    assert under_id == "event_abc123_total_under"
    
    # Test reverse
    back_to_over = get_opposite_selection_id("event_abc123", MarketType.TOTAL, under_id)
    print(f"  {under_id} → {back_to_over}")
    assert back_to_over == over_id
    print("✅ TOTAL opposites verified\n")
    
    # Test MONEYLINE opposites
    print("Testing MONEYLINE market...")
    ml_home_id = "event_abc123_ml_home"
    ml_away_id = get_opposite_selection_id("event_abc123", MarketType.MONEYLINE_2WAY, ml_home_id)
    print(f"  {ml_home_id} → {ml_away_id}")
    assert ml_away_id == "event_abc123_ml_away"
    print("✅ MONEYLINE opposites verified\n")
    
    # Test malformed selection ID (should trigger ops alert)
    print("Testing malformed selection ID (should trigger ops alert)...")
    try:
        bad_id = "malformed_selection_without_market_indicator"
        get_opposite_selection_id("event_bad", MarketType.SPREAD, bad_id)
        print("❌ FAIL: Should have raised OppositeSelectionError")
    except OppositeSelectionError as e:
        print(f"✅ Correctly raised error: {str(e)[:80]}...")
        print("✅ Ops alert triggered (check logs/ops_alerts.log)\n")
    
    # Test safe version
    print("Testing safe version (no exception)...")
    opposite, error = get_opposite_selection_safe("event_123", MarketType.SPREAD, "malformed_id")
    assert opposite is None
    assert error is not None
    print(f"✅ Safe version returned error: {error[:80]}...\n")
    
    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print("\nOpposite selection determinism verified:")
    print("  • SPREAD: HOME ↔ AWAY")
    print("  • TOTAL: OVER ↔ UNDER")
    print("  • MONEYLINE: HOME ↔ AWAY")
    print("  • Ops alerts triggered for malformed IDs")
    print("=" * 70)

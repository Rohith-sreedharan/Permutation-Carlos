"""
Selection ID Generator - Deterministic hash-based IDs for market selections

CRITICAL: Selection IDs must be:
1. Deterministic (same inputs = same ID)
2. Unique per selection
3. Stable across refreshes
4. Market-scoped (spread/ML/total)
"""
import hashlib
from typing import Dict, Any, Optional


def generate_selection_id(
    event_id: str,
    market_type: str,  # "spread", "moneyline", "total"
    side_key: str,  # "home", "away", "over", "under"
    normalized_line: Optional[float] = None,
    book_key: str = "consensus"
) -> str:
    """
    Generate deterministic selection_id
    
    Args:
        event_id: Event identifier
        market_type: "spread", "moneyline", "total"
        side_key: "home", "away", "over", "under"
        normalized_line: Line value (None for ML)
        book_key: Bookmaker key (default "consensus")
    
    Returns:
        16-character hex hash (e.g., "a3f7c21b8e9d4f05")
    
    Examples:
        >>> generate_selection_id("evt_123", "spread", "home", -5.5)
        "a3f7c21b8e9d4f05"
        
        >>> generate_selection_id("evt_123", "moneyline", "away", None)
        "d8e2a5f1c3b7a4e9"
    """
    # Normalize line for hashing
    if normalized_line is None:
        line_str = "ML"
    else:
        line_str = f"{normalized_line:+.1f}"
    
    # Build hash input
    hash_input = f"{event_id}|{market_type}|{side_key}|{line_str}|{book_key}"
    
    # Generate SHA-256 hash and return first 16 chars
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def generate_spread_selections(
    event_id: str,
    home_team: str,
    away_team: str,
    market_spread_home: float,
    book_key: str = "consensus"
) -> Dict[str, Any]:
    """
    Generate spread market selection objects
    
    Returns:
        {
            "home": {
                "selection_id": "...",
                "team_name": "Knicks",
                "side": "home",
                "line": -5.5,
                "market_type": "spread"
            },
            "away": {
                "selection_id": "...",
                "team_name": "Nuggets",
                "side": "away",
                "line": +5.5,
                "market_type": "spread"
            }
        }
    """
    market_spread_away = -market_spread_home
    
    return {
        "home": {
            "selection_id": generate_selection_id(event_id, "spread", "home", market_spread_home, book_key),
            "team_name": home_team,
            "side": "home",
            "line": market_spread_home,
            "market_type": "spread"
        },
        "away": {
            "selection_id": generate_selection_id(event_id, "spread", "away", market_spread_away, book_key),
            "team_name": away_team,
            "side": "away",
            "line": market_spread_away,
            "market_type": "spread"
        }
    }


def generate_moneyline_selections(
    event_id: str,
    home_team: str,
    away_team: str,
    book_key: str = "consensus"
) -> Dict[str, Any]:
    """Generate moneyline market selection objects"""
    return {
        "home": {
            "selection_id": generate_selection_id(event_id, "moneyline", "home", None, book_key),
            "team_name": home_team,
            "side": "home",
            "line": None,
            "market_type": "moneyline"
        },
        "away": {
            "selection_id": generate_selection_id(event_id, "moneyline", "away", None, book_key),
            "team_name": away_team,
            "side": "away",
            "line": None,
            "market_type": "moneyline"
        }
    }


def generate_total_selections(
    event_id: str,
    total_line: float,
    book_key: str = "consensus"
) -> Dict[str, Any]:
    """Generate total market selection objects"""
    return {
        "over": {
            "selection_id": generate_selection_id(event_id, "total", "over", total_line, book_key),
            "team_name": "OVER",
            "side": "over",
            "line": total_line,
            "market_type": "total"
        },
        "under": {
            "selection_id": generate_selection_id(event_id, "total", "under", total_line, book_key),
            "team_name": "UNDER",
            "side": "under",
            "line": total_line,
            "market_type": "total"
        }
    }


def validate_selection_consistency(
    selections: Dict[str, Any],
    model_preference_selection_id: Optional[str],
    model_direction_selection_id: Optional[str]
) -> tuple[bool, list[str]]:
    """
    Validate selection consistency
    
    Checks:
    1. All selections have valid IDs
    2. model_preference_selection_id matches one selection
    3. model_direction_selection_id matches model_preference_selection_id
    4. No duplicate IDs
    
    Returns:
        (is_valid, errors)
    """
    errors = []
    
    # Check all selections have IDs
    selection_ids = set()
    for key, selection in selections.items():
        if not selection.get("selection_id"):
            errors.append(f"MISSING_SELECTION_ID: {key}")
        else:
            selection_ids.add(selection["selection_id"])
    
    # Check for duplicates
    if len(selection_ids) != len(selections):
        errors.append("DUPLICATE_SELECTION_IDS")
    
    # Check model_preference_selection_id points to valid selection
    if model_preference_selection_id and model_preference_selection_id not in ["NO_EDGE", "INVALID"]:
        if model_preference_selection_id not in selection_ids:
            errors.append(f"INVALID_PREFERENCE_ID: {model_preference_selection_id} not in {selection_ids}")
    
    # Check model_direction matches preference
    if model_direction_selection_id and model_preference_selection_id:
        if model_direction_selection_id != model_preference_selection_id:
            errors.append(
                f"DIRECTION_PREFERENCE_MISMATCH: direction={model_direction_selection_id}, "
                f"preference={model_preference_selection_id}"
            )
    
    return len(errors) == 0, errors

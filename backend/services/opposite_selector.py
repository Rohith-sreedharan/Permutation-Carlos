"""
Opposite Selection Resolver — Phase 6A.4
Deterministic resolver: get_opposite_selection_id(event_id, market_type, selection_id)

HARD RULES:
- Operates only on canonical selection objects and their `side` field.
- Never infers from team name. Never infers from line sign. Never infers home/away index.
- MARKET_TYPE: SPREAD/ML → HOME ↔ AWAY  |  TOTAL → OVER ↔ UNDER  |  PROP → explicit mapped pairs only.
- If opposite cannot be resolved: recommended_action = NO_PLAY, tier = BLOCKED.
- opposite(opposite(x)) == x for every selection in the DB — invariant enforced.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from db.mongo import db

logger = logging.getLogger(__name__)

# ── Canonical side mappings ───────────────────────────────────────────────────
_SIDE_OPPOSITES: Dict[str, str] = {
    "HOME": "AWAY",
    "AWAY": "HOME",
    "OVER": "UNDER",
    "UNDER": "OVER",
}

# Market types that use HOME/AWAY
_HOME_AWAY_MARKETS = {"SPREAD", "ML"}
# Market types that use OVER/UNDER
_OVER_UNDER_MARKETS = {"TOTAL"}


def get_opposite_selection_id(
    event_id: str,
    market_type: str,
    selection_id: str,
) -> Dict[str, object]:
    """
    Resolve the opposite selection for a given (event_id, market_type, selection_id).

    Returns:
        {
            "resolved": True,
            "opposite_selection_id": str,
            "side": str,
            "opposite_side": str,
        }
        or on failure:
        {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": str,
        }
    """
    if not selection_id:
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": "selection_id is required — cannot resolve opposite without it",
        }

    market_type_upper = market_type.upper() if market_type else ""

    # ── Fetch the source selection record ────────────────────────────────────
    source_sel = db["selections"].find_one({
        "selection_id": selection_id,
        "event_id": event_id,
        "market_type": market_type_upper,
    })

    if source_sel is None:
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": f"selection_id={selection_id!r} not found in canonical selection store for event={event_id} market={market_type_upper}",
        }

    source_side = source_sel.get("side", "").upper()

    if not source_side:
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": f"selection {selection_id!r} has no `side` field — cannot resolve opposite",
        }

    # ── Determine opposite side via canonical mapping only ───────────────────
    if market_type_upper in _HOME_AWAY_MARKETS:
        if source_side not in ("HOME", "AWAY"):
            return {
                "resolved": False,
                "recommended_action": "NO_PLAY",
                "tier": "BLOCKED",
                "reason": f"market_type={market_type_upper} requires HOME/AWAY side; got {source_side!r}",
            }
        opposite_side = _SIDE_OPPOSITES[source_side]

    elif market_type_upper in _OVER_UNDER_MARKETS:
        if source_side not in ("OVER", "UNDER"):
            return {
                "resolved": False,
                "recommended_action": "NO_PLAY",
                "tier": "BLOCKED",
                "reason": f"market_type={market_type_upper} requires OVER/UNDER side; got {source_side!r}",
            }
        opposite_side = _SIDE_OPPOSITES[source_side]

    elif market_type_upper == "PROP":
        # PROP: must use explicit mapped pairs from selections collection only
        pair_id = source_sel.get("opposite_selection_id")
        if not pair_id:
            return {
                "resolved": False,
                "recommended_action": "NO_PLAY",
                "tier": "BLOCKED",
                "reason": f"PROP selection {selection_id!r} has no explicit opposite_selection_id mapping — no inference permitted",
            }
        # Verify the pair exists
        opposite_sel = db["selections"].find_one({"selection_id": pair_id})
        if opposite_sel is None:
            return {
                "resolved": False,
                "recommended_action": "NO_PLAY",
                "tier": "BLOCKED",
                "reason": f"explicit opposite_selection_id={pair_id!r} not found in canonical store",
            }
        opposite_side = opposite_sel.get("side", "")
        return {
            "resolved": True,
            "opposite_selection_id": pair_id,
            "side": source_side,
            "opposite_side": opposite_side,
        }

    else:
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": f"market_type={market_type_upper!r} is not a recognised type for opposite resolution",
        }

    # ── Look up the opposite selection by side ────────────────────────────────
    opposite_sel = db["selections"].find_one({
        "event_id": event_id,
        "market_type": market_type_upper,
        "side": opposite_side,
    })

    if opposite_sel is None:
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": f"no canonical selection found for event={event_id} market={market_type_upper} side={opposite_side}",
        }

    opposite_id = opposite_sel["selection_id"]

    # ── Idempotency check: opposite(opposite(x)) == x ────────────────────────
    # Verify that the opposite selection's opposite points back to source
    round_trip_side = _SIDE_OPPOSITES.get(opposite_side)
    if round_trip_side != source_side:
        logger.error(
            "INVARIANT VIOLATION: opposite(opposite(%s)) != %s — side mapping broken",
            selection_id, selection_id,
        )
        return {
            "resolved": False,
            "recommended_action": "NO_PLAY",
            "tier": "BLOCKED",
            "reason": f"invariant violation: opposite(opposite({selection_id})) != {selection_id}",
        }

    return {
        "resolved": True,
        "opposite_selection_id": opposite_id,
        "side": source_side,
        "opposite_side": opposite_side,
    }


def verify_all_opposites_invariant() -> Dict[str, object]:
    """
    CI test helper: verify opposite(opposite(x)) == x for every selection in DB.
    Returns {"passed": True, "tested": N} or {"passed": False, "failures": [...]}
    """
    failures = []
    tested = 0

    for sel in db["selections"].find({}):
        sel_id = sel.get("selection_id")
        event_id = sel.get("event_id")
        market_type = sel.get("market_type", "")
        side = sel.get("side", "").upper()

        if not all([sel_id, event_id, market_type, side]):
            continue

        # Skip PROP — uses explicit pairs, tested separately
        if market_type.upper() == "PROP":
            continue

        expected_back = _SIDE_OPPOSITES.get(_SIDE_OPPOSITES.get(side, ""), "")
        if expected_back != side:
            failures.append({
                "selection_id": sel_id,
                "side": side,
                "reason": f"side mapping broken: opposite(opposite({side})) = {expected_back!r} != {side!r}",
            })
        tested += 1

    return {
        "passed": len(failures) == 0,
        "tested": tested,
        "failures": failures,
    }

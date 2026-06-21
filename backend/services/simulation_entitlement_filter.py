"""Canonical simulation payload entitlement filter.

Applies a single, centralized redaction policy for non-Platform tiers.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

PLATFORM_INTELLIGENCE_TIERS = {
    "platform",
    "beatvegas_platform",
}

# Fields that expose Platform-tier intelligence in raw simulation payloads.
NON_PLATFORM_REDACTED_TOP_LEVEL_FIELDS = {
    "market_views",
    "sharp_analysis",
    "distribution_curve",
    "total_distribution",
    "spread_distribution",
    "injury_summary",
    "injury_impact",
    "injury_impact_weighted",
    "top_props",
    "confidence_score",
    "confidence_tier",
    "volatility_index",
    "volatility_score",
    "variance",
    "variance_total",
}


def has_platform_intelligence_access(user_tier: str) -> bool:
    return str(user_tier or "free").strip().lower() in PLATFORM_INTELLIGENCE_TIERS


def apply_simulation_entitlement_filter(simulation: Dict[str, Any], user_tier: str) -> Dict[str, Any]:
    """Return payload filtered to the caller's entitlement level."""
    if has_platform_intelligence_access(user_tier):
        return simulation

    filtered = deepcopy(simulation)

    for key in NON_PLATFORM_REDACTED_TOP_LEVEL_FIELDS:
        filtered.pop(key, None)

    # Keep basic market context but remove 1H intelligence-specific line hints.
    market_context = filtered.get("market_context")
    if isinstance(market_context, dict):
        market_context.pop("bookmaker_1h_line", None)
        market_context.pop("bookmaker_1h_source", None)

    filtered["entitlement_redaction"] = {
        "applied": True,
        "tier": str(user_tier or "free").lower(),
        "scope": "non_platform_simulation_boundary",
    }
    return filtered

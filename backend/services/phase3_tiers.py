"""
Phase 3 Tier Definitions — Source of Truth
Purchasable tiers as per Phase 3A.4 directive + PF-5 SimSports API schema.

Intelligence Preview  — $0/month  — track record only, zero intelligence outputs
Syndicate             — $39/month — Telegram channel access only, no web platform
Platform              — $97/month — full platform + Parlay Architect, all features
SimSports API         — not marketed externally — schema defined per spec requirement
"""

from __future__ import annotations

import os
from typing import Any, Dict

# ─────────────────────────────────────────────────────────────────────────────
# Canonical tier registry
# ─────────────────────────────────────────────────────────────────────────────

TIERS: Dict[str, Dict[str, Any]] = {
    "intelligence_preview": {
        "display_name": "Intelligence Preview",
        "price_monthly_usd": 0.00,
        "stripe_product_id": None,           # free — no Stripe product
        "stripe_price_id": None,
        "features": {
            "web_platform": False,
            "intelligence_outputs": False,    # zero intelligence outputs
            "track_record": True,             # track record surface only
            "telegram_signals": False,
            "parlay_architect": False,
            "api_access": False,
        },
        "description": "Track record surface only. Zero intelligence outputs. Entitlement record in DB required.",
    },
    "syndicate": {
        "display_name": "Syndicate",
        "price_monthly_usd": 39.00,
        "stripe_product_id": "prod_syndicate",   # resolved from env on server
        "stripe_price_id": os.getenv("STRIPE_PRICE_ID_SYNDICATE", ""),
        "features": {
            "web_platform": False,            # no web platform access
            "intelligence_outputs": True,
            "track_record": True,
            "telegram_signals": True,         # Telegram channel access gated
            "parlay_architect": False,
            "api_access": False,
        },
        "description": "Telegram channel access gated. No web platform access.",
    },
    "platform": {
        "display_name": "Platform",
        "price_monthly_usd": 97.00,
        "stripe_product_id": "prod_platform",
        "stripe_price_id": os.getenv("STRIPE_PRICE_ID_PLATFORM", ""),
        "features": {
            "web_platform": True,             # full platform
            "intelligence_outputs": True,
            "track_record": True,
            "telegram_signals": True,
            "parlay_architect": True,         # Parlay Architect included
            "api_access": True,
            "simsports_api_access": False,
        },
        "description": "Full platform. Parlay Architect included. All features. No holdbacks.",
    },
    "simsports_api": {
        "display_name": "SimSports API",
        "price_monthly_usd": 0.00,
        "stripe_product_id": None,            # not marketed externally
        "stripe_price_id": None,
        "features": {
            "web_platform": False,
            "intelligence_outputs": True,
            "track_record": True,
            "telegram_signals": False,
            "parlay_architect": False,
            "api_access": True,
            "simsports_api_access": True,     # direct SimSports API access
        },
        "description": "SimSports API entitlement. Schema required by spec. Not marketed to end users.",
    },
}

# Ordered from lowest to highest access
TIER_ORDER = ["intelligence_preview", "syndicate", "platform"]


def get_tier(tier_key: str) -> Dict[str, Any]:
    """Return tier definition. Raises KeyError for unknown tier."""
    return TIERS[tier_key]


def tier_has_feature(tier_key: str, feature: str) -> bool:
    """Return True if the named tier grants the given feature."""
    tier = TIERS.get(tier_key, {})
    return bool(tier.get("features", {}).get(feature, False))


def is_intelligence_tier(tier_key: str) -> bool:
    """Return True if the tier has web platform + intelligence outputs."""
    return tier_has_feature(tier_key, "web_platform") and tier_has_feature(tier_key, "intelligence_outputs")

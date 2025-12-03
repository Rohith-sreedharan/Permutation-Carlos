"""
BeatVegas Pricing Configuration
NEW 6-TIER SYSTEM: STARTER, BRONZE, SILVER, PLATINUM, FOUNDER, INTERNAL
Universal parlay pricing + tier-based simulation power
"""

from typing import Dict, Any

# UNIVERSAL PARLAY PRICING (Same for all tiers)
PARLAY_PRICING = {
    "3_leg": 999,   # $9.99 in cents
    "4_leg": 799,   # $7.99
    "5_leg": 599,   # $5.99
    "6_leg": 399    # $3.99
}

# SIMULATION POWER PER TIER
SIMULATION_POWER = {
    "starter": 10_000,
    "bronze": 25_000,
    "silver": 50_000,
    "platinum": 100_000,
    "founder": 100_000,
    "internal": 1_000_000
}

# PARLAY ACCESS LEVELS
PARLAY_ACCESS = {
    "starter": "blur_only",
    "bronze": "full",
    "silver": "full",
    "platinum": "full",
    "founder": "full",
    "internal": "full"
}

# Tier Configuration
TIER_CONFIG = {
    "starter": {
        "name": "Starter",
        "price_monthly": 0,
        "simulations": 10_000,
        "parlay_access": "blur_only",
        "features": ["10K simulations", "Blurred parlay preview"],
    },
    "bronze": {
        "name": "Bronze",
        "price_monthly": 19,
        "simulations": 25_000,
        "parlay_access": "full",
        "features": ["25K simulations", "Full parlay generation"],
    },
    "silver": {
        "name": "Silver",
        "price_monthly": 39,
        "simulations": 50_000,
        "parlay_access": "full",
    },
    "platinum": {
        "name": "Platinum",
        "price_monthly": 79,
        "simulations": 100_000,
        "parlay_access": "full",
    },
    "founder": {
        "name": "Founder",
        "simulations": 100_000,
        "parlay_access": "full",
        "lifetime_discount": True,
    },
    "internal": {
        "name": "Internal",
        "simulations": 1_000_000,
        "parlay_access": "full",
    }
}


def get_parlay_price(leg_count: int, tier: str = "starter") -> int:
    """Get parlay price in cents (universal pricing)"""
    # FOUNDER and INTERNAL tiers get free parlays
    if tier.lower() in ["founder", "internal"]:
        return 0
    return PARLAY_PRICING.get(f"{leg_count}_leg", 999)


def get_simulation_iterations(tier: str = "starter") -> int:
    """Get Monte Carlo iterations for tier"""
    return SIMULATION_POWER.get(tier.lower(), 10_000)


def should_blur_parlay(tier: str = "starter") -> bool:
    """Check if parlays should be blurred (Starter only)"""
    return PARLAY_ACCESS.get(tier.lower(), "blur_only") == "blur_only"


def get_tier_config(tier: str) -> Dict[str, Any]:
    """Get tier configuration"""
    return TIER_CONFIG.get(tier.lower(), TIER_CONFIG["starter"]).copy()

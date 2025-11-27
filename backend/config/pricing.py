"""
BeatVegas Pricing Configuration
4-Tier System: STARTER, EXPLORER, PRO, ELITE
Source: BeatVegas_Master_Implementation_and_Pricing_Spec_FINAL.pdf
"""

from enum import Enum
from typing import Dict, Any

class SubscriptionTier(str, Enum):
    STARTER = "STARTER"
    EXPLORER = "EXPLORER"
    PRO = "PRO"
    ELITE = "ELITE"
    FOUNDER = "FOUNDER"  # Special tier for first 300 users

# Tier Configuration
TIER_CONFIG: Dict[SubscriptionTier, Dict[str, Any]] = {
    SubscriptionTier.STARTER: {
        "name": "Starter",
        "price_monthly": 0,
        "price_annual": 0,
        "stripe_price_id": None,
        "simulations_per_day": 2,
        "simulations_per_month": 30,
        "iterations": 2000,
        "features": [
            "Basic Monte Carlo simulations",
            "Win probability analysis",
            "Spread distribution",
            "Community access (read-only)"
        ],
        "description": "Get started with basic sports analytics"
    },
    SubscriptionTier.EXPLORER: {
        "name": "Explorer",
        "price_monthly": 19,
        "price_annual": 190,  # ~17% discount
        "stripe_price_id": "price_explorer_monthly",
        "simulations_per_day": 15,
        "simulations_per_month": 450,
        "iterations": 10000,
        "features": [
            "Advanced Monte Carlo simulations",
            "Volatility scoring",
            "Prop bet analysis (Top 5)",
            "Creator Marketplace access",
            "Community participation",
            "Email support"
        ],
        "description": "Advanced analytics for serious sports enthusiasts",
        "founder_price_monthly": 13,  # Discounted for first 300 users
        "founder_price_annual": 130
    },
    SubscriptionTier.PRO: {
        "name": "Pro",
        "price_monthly": 39,
        "price_annual": 390,  # ~17% discount
        "stripe_price_id": "price_pro_monthly",
        "simulations_per_day": 60,
        "simulations_per_month": 1800,
        "iterations": 35000,
        "features": [
            "Premium Monte Carlo simulations",
            "Full Decision Command Center",
            "Parlay Correlation Engine",
            "Cross-sport analysis",
            "Injury impact analysis",
            "Line movement tracking",
            "Creator Intelligence Marketplace",
            "Priority support (24/7)"
        ],
        "description": "Professional-grade analytics suite",
        "founder_price_monthly": 29,  # Discounted for first 300 users
        "founder_price_annual": 290
    },
    SubscriptionTier.ELITE: {
        "name": "Elite",
        "price_monthly": 89,
        "price_annual": 890,  # ~17% discount
        "stripe_price_id": "price_elite_monthly",
        "simulations_per_day": 300,
        "simulations_per_month": 9000,
        "iterations": 100000,
        "features": [
            "Elite Monte Carlo simulations (100K iterations)",
            "Real-time model performance tracking",
            "API access (programmatic)",
            "Custom simulation parameters",
            "Advanced parlay optimization",
            "Multi-sport portfolio analysis",
            "White-glove support (dedicated account manager)",
            "Early access to new features",
            "Quarterly performance reviews"
        ],
        "description": "Ultimate analytics platform for professionals",
        "founder_price_monthly": 69,  # Discounted for first 300 users
        "founder_price_annual": 690
    }
}

# Founder Tier Logic
FOUNDER_TIER_LIMIT = 300  # First 300 users get founder pricing
FOUNDER_TIER_REDIS_KEY = "beatvegas:founder_count"

# Stripe Configuration
STRIPE_CONFIG = {
    "webhook_secret": "whsec_...",  # Set via environment variable
    "customer_portal_url": "/api/stripe/customer-portal",
    "checkout_success_url": "/dashboard?payment=success",
    "checkout_cancel_url": "/billing?payment=cancelled"
}

# Creator Marketplace Revenue Split
CREATOR_REVENUE_SPLIT = {
    "creator_percentage": 70,
    "platform_percentage": 30
}

# Subscription & Report Pricing Limits
CREATOR_PRICING_LIMITS = {
    "subscription_min": 15,
    "subscription_max": 75,
    "report_min": 5,
    "report_max": 50
}

# Compliance: Prohibited Terms
PROHIBITED_TERMS = [
    "bet",
    "wager",
    "guaranteed win",
    "lock",
    "sure thing",
    "can't lose",
    "guaranteed money",
    "betting",
    "gamble",
    "gambling"
]

# Allowed Terms
ALLOWED_TERMS = [
    "forecast",
    "analysis",
    "insight",
    "projection",
    "prediction",
    "outlook",
    "intelligence",
    "assessment"
]

def get_tier_config(tier: SubscriptionTier, is_founder: bool = False) -> Dict[str, Any]:
    """Get tier configuration with optional founder pricing"""
    config = TIER_CONFIG[tier].copy()
    
    if is_founder and tier != SubscriptionTier.STARTER:
        if "founder_price_monthly" in config:
            config["price_monthly"] = config["founder_price_monthly"]
        if "founder_price_annual" in config:
            config["price_annual"] = config["founder_price_annual"]
    
    return config

def validate_content(content: str) -> tuple[bool, str]:
    """
    Validate creator content for compliance.
    Returns (is_valid, error_message)
    """
    content_lower = content.lower()
    
    # Check for prohibited terms
    for term in PROHIBITED_TERMS:
        if term in content_lower:
            return False, f"Compliance Error: We sell analysis, not {term}s. Please rephrase your content."
    
    return True, ""

def get_tier_limits(tier: SubscriptionTier) -> Dict[str, int]:
    """Get simulation limits for a tier"""
    config = TIER_CONFIG[tier]
    return {
        "daily_limit": config["simulations_per_day"],
        "monthly_limit": config["simulations_per_month"],
        "iterations": config["iterations"]
    }

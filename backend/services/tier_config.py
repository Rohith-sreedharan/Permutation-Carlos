"""
Subscription Tier Configuration
Defines features and pricing for each tier
"""
from typing import Dict, Any


SUBSCRIPTION_TIERS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "name": "Starter",
        "price_monthly": 29.99,
        "description": "Perfect for casual bettors - basic Monte Carlo simulations",
        "features": {
            "access_monte_carlo": True,
            "access_clv_tracker": False,
            "access_advanced_dashboards": False,
            "access_prop_mispricing": False,
            "access_parlay_correlation": False,
            "max_picks_per_day": 5,
            "simulation_iterations": 10000,  # Basic simulations
            "support_level": "community"
        },
        "display_features": [
            "5 AI picks per day",
            "10K iteration Monte Carlo sims",
            "Basic win probability analysis",
            "Community access"
        ]
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 49.99,
        "description": "For serious bettors - full simulations + prop analysis",
        "features": {
            "access_monte_carlo": True,
            "access_clv_tracker": True,
            "access_advanced_dashboards": False,
            "access_prop_mispricing": True,
            "access_parlay_correlation": True,
            "max_picks_per_day": 15,
            "simulation_iterations": 50000,  # Standard simulations
            "support_level": "email"
        },
        "display_features": [
            "15 AI picks per day",
            "50K iteration Monte Carlo sims",
            "CLV tracking & analysis",
            "Prop mispricing alerts",
            "Parlay correlation engine",
            "Email support"
        ]
    },
    "sharps_room": {
        "name": "Sharps Room",
        "price_monthly": 99.99,
        "description": "Elite tier for sharps - maximum simulations + advanced tools",
        "features": {
            "access_monte_carlo": True,
            "access_clv_tracker": True,
            "access_advanced_dashboards": True,
            "access_prop_mispricing": True,
            "access_parlay_correlation": True,
            "max_picks_per_day": 999,  # Unlimited
            "simulation_iterations": 100000,  # Maximum simulations
            "support_level": "priority"
        },
        "display_features": [
            "Unlimited AI picks",
            "100K iteration Monte Carlo sims",
            "Full CLV tracker with history",
            "Advanced analytics dashboards",
            "All prop tools & correlations",
            "Real-time line movement alerts",
            "Priority support"
        ]
    },
    "founder": {
        "name": "Founder (Limited)",
        "price_monthly": 199.99,
        "description": "Exclusive lifetime access - limited to first 100 members",
        "features": {
            "access_monte_carlo": True,
            "access_clv_tracker": True,
            "access_advanced_dashboards": True,
            "access_prop_mispricing": True,
            "access_parlay_correlation": True,
            "max_picks_per_day": 999,
            "simulation_iterations": 100000,
            "support_level": "concierge",
            "lifetime_access": True,
            "founder_badge": True,
            "early_feature_access": True
        },
        "display_features": [
            "Everything in Sharps Room",
            "Lifetime access guarantee",
            "Founder badge & recognition",
            "Early access to new features",
            "Concierge support",
            "Input on product roadmap"
        ],
        "max_subscribers": 100,
        "is_limited": True
    }
}


def get_tier_config(tier_name: str) -> Dict[str, Any]:
    """Get configuration for a subscription tier"""
    return SUBSCRIPTION_TIERS.get(tier_name, SUBSCRIPTION_TIERS["starter"])


def get_tier_features(tier_name: str) -> Dict[str, Any]:
    """Get feature flags for a subscription tier"""
    config = get_tier_config(tier_name)
    return config.get("features", {})


def check_feature_access(tier_name: str, feature: str) -> bool:
    """Check if a tier has access to a specific feature"""
    features = get_tier_features(tier_name)
    return features.get(feature, False)


def get_commission_rate(tier_name: str) -> float:
    """
    Get affiliate commission rate for a tier
    Higher tiers = higher commission to incentivize promotion
    """
    commission_rates = {
        "starter": 0.20,  # 20%
        "pro": 0.30,  # 30%
        "sharps_room": 0.40,  # 40%
        "founder": 0.40  # 40%
    }
    return commission_rates.get(tier_name, 0.20)


def upgrade_user_tier(user_id: str, new_tier: str) -> Dict[str, Any]:
    """
    Upgrade a user to a new subscription tier
    Updates feature flags in database
    """
    from db.mongo import db
    
    tier_config = get_tier_config(new_tier)
    features = tier_config.get("features", {})
    
    # Update subscriber with new tier and features
    update_result = db["subscribers"].update_one(
        {"id": user_id},
        {
            "$set": {
                "plan": new_tier,
                "monthly_value": tier_config["price_monthly"],
                **features
            }
        }
    )
    
    if update_result.modified_count > 0:
        return {
            "status": "success",
            "user_id": user_id,
            "new_tier": new_tier,
            "features": features
        }
    else:
        return {
            "status": "error",
            "message": "User not found or tier unchanged"
        }

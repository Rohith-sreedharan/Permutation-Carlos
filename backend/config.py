"""
BeatVegas Platform Configuration
Master constants for simulation tiers, revenue splits, and compliance
"""

# ============================================================================
# SIMULATION TIER CONSTANTS - "Compute as a Service"
# ============================================================================

# Public Tier Limits
SIM_TIER_FREE = 10000        # Fast, low-cost baseline
SIM_TIER_EXPLORER = 25000    # Better stability for entry users
SIM_TIER_PRO = 50000         # Standard high-quality analysis
SIM_TIER_ELITE = 100000      # HARD CAP for public users - institutional quality

# Internal "House Edge" Tier
SIM_TIER_INTERNAL = 500000   # Private engine for admin/model tuning
                             # This data grades the public models (Trust Loop)

# Tier Mapping (matches subscription tier names)
SIMULATION_TIERS = {
    "free": SIM_TIER_FREE,
    "explorer": SIM_TIER_EXPLORER,
    "pro": SIM_TIER_PRO,
    "elite": SIM_TIER_ELITE,
    "admin": SIM_TIER_INTERNAL,
}

# Precision Level Labels (for frontend display)
PRECISION_LABELS = {
    SIM_TIER_FREE: "STANDARD",
    SIM_TIER_EXPLORER: "ENHANCED",
    SIM_TIER_PRO: "HIGH",
    SIM_TIER_ELITE: "INSTITUTIONAL",
    SIM_TIER_INTERNAL: "HOUSE_EDGE",
}


# ============================================================================
# REVENUE & FOUNDER LOGIC
# ============================================================================

# Creator Revenue Split (from PDF - locked at 70/30)
CREATOR_PAYOUT_PCT = 70      # Creator receives 70%
PLATFORM_REVENUE_PCT = 30    # BeatVegas retains 30%

# Founder Tier Cap (first 300 users only)
FOUNDER_CAP = 300
FOUNDER_TIER_NAME = "founder"


# ============================================================================
# COMPLIANCE & MODERATION
# ============================================================================

# Prohibited Terms (Insights, Not Bets - PDF Page 3)
# Block any creator content containing these words
PROHIBITED_TERMS = [
    "bet",
    "bets",
    "betting",
    "wager",
    "wagers",
    "wagering",
    "guaranteed win",
    "guaranteed",
    "lock",
    "locks",
    "sure thing",
    "can't lose",
    "bookie",
    "bookies",
    "units",
    "unit",
    "put money on",
    "cash out",
    "winnings",
    "payout",
    "stake",
    "stakes",
]

# Approved Alternative Terms (suggest to creators)
APPROVED_TERMS = [
    "forecast",
    "forecasts",
    "projection",
    "projections",
    "insight",
    "insights",
    "analysis",
    "model",
    "simulation",
    "edge",
    "confidence",
    "probability",
    "expectation",
    "value",
]

# Compliance Error Message
COMPLIANCE_ERROR_MSG = (
    "Compliance Error: BeatVegas sells analysis, not bets. "
    "Please use terms like 'Forecast', 'Insight', or 'Projection'."
)


# ============================================================================
# VERIFICATION & TRUST LOOP
# ============================================================================

# Rolling metric windows for model accuracy tracking
TRUST_WINDOWS = [7, 30, 90]  # Days

# Public Ledger: Top N most accurate forecasts
PUBLIC_LEDGER_SIZE = 10

# Outcome verification states
FORECAST_STATUS = {
    "PENDING": "pending",
    "CORRECT": "correct",
    "INCORRECT": "incorrect",
    "PUSH": "push",  # Tie/draw scenarios
}


# ============================================================================
# ADMIN & SUPER-ADMIN
# ============================================================================

# Super-admin user IDs (hardcode initially, move to DB later)
SUPER_ADMIN_IDS = [
    # Add your admin user IDs here
]


# ============================================================================
# CONFIDENCE INTERVALS & UX
# ============================================================================

# Confidence interval width by tier (for visualization)
CONFIDENCE_INTERVALS = {
    SIM_TIER_FREE: 0.15,        # Wide, fuzzy range (15% spread)
    SIM_TIER_EXPLORER: 0.10,    # Moderate range (10% spread)
    SIM_TIER_PRO: 0.06,         # Tight range (6% spread)
    SIM_TIER_ELITE: 0.03,       # Very tight range (3% spread)
    SIM_TIER_INTERNAL: 0.01,    # Ultra-precise (1% spread)
}


# ============================================================================
# UPSELL MESSAGING
# ============================================================================

UPSELL_MESSAGES = {
    "free_to_explorer": "View with 2.5x Precision? Upgrade to Explorer.",
    "free_to_pro": "View with 5x Precision? Upgrade to Pro.",
    "explorer_to_pro": "View with 2x Precision? Upgrade to Pro.",
    "pro_to_elite": "View with 2x Precision? Upgrade to Elite for Institutional-Quality Analysis.",
}

"""
BeatVegas Platform Configuration
Master constants for simulation tiers, revenue splits, and compliance
"""

# ============================================================================
# SIMULATION TIER CONSTANTS - "Compute as a Service"
# ============================================================================
# 
# Tiered pricing model with differentiated compute power
# Higher tiers get more Monte Carlo iterations = higher precision forecasts
#

# Public Tier Limits - Differentiated compute power by subscription level
SIM_TIER_FREE = 10000        # Free tier - 10K iterations (limited precision)
SIM_TIER_STARTER = 25000     # $29.99/mo - 25K iterations (entry precision)
SIM_TIER_CORE = 35000        # $39.99/mo - 35K iterations (core precision)
SIM_TIER_PRO = 50000         # $49.99/mo - 50K iterations (pro precision)
SIM_TIER_ELITE = 100000      # $79.99/mo - 100K iterations (elite precision)
SIM_TIER_SHARPS_ROOM = 100000  # $99.99/mo - 100K iterations (max public tier)
SIM_TIER_FOUNDER = 100000    # $199.99/mo - 100K iterations (founding member)

# Internal "House Edge" Tier - Calibration Engine (NOT user facing)
SIM_TIER_INTERNAL = 1000000  # 1M+ simulations for Reflexive Learning Loop
                             # Feeds calibration data only

# Tier Mapping (matches subscription tier names)
SIMULATION_TIERS = {
    "free": SIM_TIER_FREE,
    "starter": SIM_TIER_STARTER,     # $29.99/mo
    "core": SIM_TIER_CORE,           # $39.99/mo
    "pro": SIM_TIER_PRO,             # $49.99/mo
    "elite": SIM_TIER_ELITE,         # $79.99/mo
    "sharps_room": SIM_TIER_SHARPS_ROOM,  # $99.99/mo
    "founder": SIM_TIER_FOUNDER,     # $199.99/mo
    "admin": SIM_TIER_INTERNAL,
}

# Precision Level Labels (for frontend display)
PRECISION_LABELS = {
    10000: "BASIC",                  # 10K iterations (free tier)
    25000: "STANDARD",               # 25K iterations (starter)
    35000: "ENHANCED",               # 35K iterations (core)
    50000: "PROFESSIONAL",           # 50K iterations (pro)
    100000: "INSTITUTIONAL",         # 100K iterations (elite/sharps/founder)
    SIM_TIER_INTERNAL: "HOUSE_EDGE", # 1M+ internal calibration
}

# Tier Colors (for frontend badges)
TIER_COLORS = {
    "free": "#9CA3AF",         # Gray
    "starter": "#3B82F6",      # Blue
    "pro": "#8B5CF6",          # Purple
    "sharps_room": "#F59E0B",  # Amber/Gold
    "founder": "#EF4444",      # Red
    "admin": "#EF4444",        # Red
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
    SIM_TIER_FREE: 0.20,        # Wide, fuzzy range (20% spread)
    SIM_TIER_STARTER: 0.15,     # Moderate range (15% spread)
    SIM_TIER_PRO: 0.06,         # Tight range (6% spread)
    SIM_TIER_SHARPS_ROOM: 0.03,  # Very tight range (3% spread)
    SIM_TIER_FOUNDER: 0.03,     # Very tight range (3% spread)
    SIM_TIER_INTERNAL: 0.01,    # Ultra-precise (1% spread)
}


# ============================================================================
# UPSELL MESSAGING
# ============================================================================

UPSELL_MESSAGES = {
    "free_to_starter": "View with 2.5x Precision? Upgrade to Starter ($19.99/mo).",
    "free_to_pro": "View with 5x Precision? Upgrade to Pro ($39.99/mo).",
    "starter_to_pro": "View with 2x Precision? Upgrade to Pro ($39.99/mo).",
    "pro_to_elite": "View with 1.5x Precision? Upgrade to Elite ($89/mo) for Institutional-Quality Analysis.",
}

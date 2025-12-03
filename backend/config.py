"""
BeatVegas Platform Configuration
Master constants for simulation tiers, revenue splits, and compliance
"""

# ============================================================================
# SIMULATION TIER CONSTANTS - "Compute as a Service"
# ============================================================================
#
# SPEC REQUIREMENT (Section 1): Public Engine MUST use 100,000 simulations
# per game. Never fallback below 100K. Hard error if 100K fails.
#

# Public Tier Limits - ALL TIERS USE 100K FOR SINGLE GAME ANALYSIS
SIM_TIER_FREE = 100000       # Free tier - 100K iterations (spec requirement)
SIM_TIER_STARTER = 100000    # Starter tier - 100K iterations (spec requirement)
SIM_TIER_CORE = 100000       # Core tier - 100K iterations (spec requirement)
SIM_TIER_PRO = 100000        # Pro tier - 100K iterations (spec requirement)
SIM_TIER_ELITE = 100000      # Elite tier - 100K iterations (spec requirement)
SIM_TIER_SHARPS_ROOM = 100000  # Sharps Room tier - 100K iterations (spec requirement)
SIM_TIER_FOUNDER = 100000    # Founder tier - 100K iterations (spec requirement)

# Internal "House Edge" Tier - Calibration Engine (NOT user facing)
SIM_TIER_INTERNAL = 1000000  # 1M+ simulations for Reflexive Learning Loop
                             # Feeds calibration data only

# Tier Mapping (matches subscription tier names)
SIMULATION_TIERS = {
    "free": SIM_TIER_FREE,
    "starter": SIM_TIER_STARTER,
    "core": SIM_TIER_CORE,
    "pro": SIM_TIER_PRO,
    "elite": SIM_TIER_ELITE,
    "sharps_room": SIM_TIER_SHARPS_ROOM,
    "founder": SIM_TIER_FOUNDER,
    "admin": SIM_TIER_INTERNAL,
}

# Precision Level Labels (for frontend display)
PRECISION_LABELS = {
    100000: "INSTITUTIONAL",         # 100K iterations (all public tiers)
    SIM_TIER_INTERNAL: "HOUSE_EDGE", # 1M+ internal calibration
}

# Tier Colors (for frontend badges)
TIER_COLORS = {
    "free": "#9CA3AF",         # Gray
    "starter": "#3B82F6",      # Blue
    "core": "#06B6D4",         # Cyan
    "pro": "#8B5CF6",          # Purple
    "elite": "#F59E0B",        # Gold
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

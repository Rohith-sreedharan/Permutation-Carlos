"""
API Polling Configuration
Control polling intervals for different scenarios to optimize API quota usage
"""

# STANDARD POLLING INTERVALS (in minutes)
POLLING_INTERVALS = {
    "standard": 15,          # Default: Every 15 minutes (conservative)
    "aggressive": 5,         # Near game time: Every 5 minutes
    "live": 2,              # During live games: Every 2 minutes
    "off_season": 360,      # Off-season: Every 6 hours
}

# SPORT-SPECIFIC OVERRIDES
# Use this to disable off-season sports or adjust intervals
SPORT_INTERVALS = {
    "basketball_nba": POLLING_INTERVALS["standard"],
    "americanfootball_nfl": POLLING_INTERVALS["standard"],
    "baseball_mlb": POLLING_INTERVALS["off_season"],  # MLB off-season
    "icehockey_nhl": POLLING_INTERVALS["standard"],
    "basketball_ncaab": POLLING_INTERVALS["standard"],
    "americanfootball_ncaaf": POLLING_INTERVALS["standard"],
}

# API QUOTA LIMITS (adjust based on your plan)
API_QUOTA = {
    "daily_limit": 500,      # Requests per day
    "monthly_limit": 10000,  # Requests per month
    "remaining": None,       # Track remaining quota (pulled from API headers)
}

# ADAPTIVE POLLING: Automatically adjust based on game proximity
ADAPTIVE_POLLING_ENABLED = True

# Time thresholds (in hours before game start)
ADAPTIVE_THRESHOLDS = {
    "far_future": {         # > 24 hours: Use standard interval
        "hours": 24,
        "interval": POLLING_INTERVALS["standard"]
    },
    "approaching": {        # 2-24 hours: Use aggressive interval
        "hours": 2,
        "interval": POLLING_INTERVALS["aggressive"]
    },
    "imminent": {          # < 2 hours: Use live interval
        "hours": 0,
        "interval": POLLING_INTERVALS["live"]
    }
}

# QUOTA SAFETY: Stop polling if quota falls below this percentage
QUOTA_SAFETY_THRESHOLD = 0.20  # Stop at 20% remaining

def get_polling_interval(sport_key: str, hours_until_game: float | None = None) -> int:
    """
    Get optimal polling interval for a sport
    
    Args:
        sport_key: Sport identifier (e.g., 'basketball_nba')
        hours_until_game: Hours until next game (None = use standard)
    
    Returns:
        Polling interval in minutes
    """
    if not ADAPTIVE_POLLING_ENABLED or hours_until_game is None:
        return SPORT_INTERVALS.get(sport_key, POLLING_INTERVALS["standard"])
    
    # Adaptive polling based on game proximity
    if hours_until_game > ADAPTIVE_THRESHOLDS["far_future"]["hours"]:
        return ADAPTIVE_THRESHOLDS["far_future"]["interval"]
    elif hours_until_game > ADAPTIVE_THRESHOLDS["approaching"]["hours"]:
        return ADAPTIVE_THRESHOLDS["approaching"]["interval"]
    else:
        return ADAPTIVE_THRESHOLDS["imminent"]["interval"]

def calculate_daily_requests(intervals: dict = SPORT_INTERVALS) -> dict:
    """
    Calculate expected daily API requests
    
    Returns:
        Dictionary with request calculations
    """
    total_requests = 0
    breakdown = {}
    
    for sport, interval_minutes in intervals.items():
        requests_per_day = (24 * 60) / interval_minutes
        breakdown[sport] = requests_per_day
        total_requests += requests_per_day
    
    return {
        "total_daily": int(total_requests),
        "total_monthly": int(total_requests * 30),
        "breakdown": breakdown,
        "within_quota": total_requests <= API_QUOTA["daily_limit"]
    }

if __name__ == "__main__":
    # Print current configuration
    print("📊 Current Polling Configuration")
    print("=" * 50)
    
    calc = calculate_daily_requests()
    print(f"\n📈 Expected API Usage:")
    print(f"   Daily Requests: {calc['total_daily']}")
    print(f"   Monthly Requests: {calc['total_monthly']}")
    print(f"   Within Quota: {'✅ Yes' if calc['within_quota'] else '❌ No'}")
    
    print(f"\n🏀 Sport Breakdown:")
    for sport, requests in calc['breakdown'].items():
        interval = SPORT_INTERVALS[sport]
        print(f"   {sport}: {int(requests)} requests/day ({interval}m interval)")
    
    print(f"\n💡 Quota Status:")
    print(f"   Daily Limit: {API_QUOTA['daily_limit']}")
    print(f"   Monthly Limit: {API_QUOTA['monthly_limit']}")
    print(f"   Safety Threshold: {int(QUOTA_SAFETY_THRESHOLD * 100)}%")

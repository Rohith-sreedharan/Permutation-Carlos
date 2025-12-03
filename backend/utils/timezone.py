"""
Timezone Utility Module
Ensures all datetime operations use EST (America/New_York) as the product timezone
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# Product timezone: EST (America/New_York)
EST_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def now_est() -> datetime:
    """Get current datetime in EST timezone."""
    return datetime.now(EST_TZ)


def now_utc() -> datetime:
    """Get current datetime in UTC timezone."""
    return datetime.now(UTC_TZ)


def to_est(dt: datetime) -> datetime:
    """Convert any datetime to EST timezone."""
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(EST_TZ)


def to_utc(dt: datetime) -> datetime:
    """Convert any datetime to UTC timezone."""
    if dt.tzinfo is None:
        # Assume EST if naive
        dt = dt.replace(tzinfo=EST_TZ)
    return dt.astimezone(UTC_TZ)


def parse_iso_to_est(iso_string: str) -> Optional[datetime]:
    """Parse ISO string to EST datetime.
    
    Args:
        iso_string: ISO format datetime string (e.g., '2025-11-29T18:00:00Z')
    
    Returns:
        datetime object in EST timezone or None if parsing fails
    """
    if not iso_string:
        return None
    
    try:
        # Handle 'Z' suffix for UTC
        iso_string = iso_string.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_string)
        return to_est(dt)
    except Exception:
        return None


def format_est_date(dt: datetime) -> str:
    """Format datetime as EST date string (YYYY-MM-DD)."""
    est_dt = to_est(dt)
    return est_dt.strftime("%Y-%m-%d")


def format_est_datetime(dt: datetime) -> str:
    """Format datetime as EST ISO string."""
    est_dt = to_est(dt)
    return est_dt.isoformat()


def get_est_date_today() -> str:
    """Get today's date in EST as YYYY-MM-DD string."""
    return now_est().strftime("%Y-%m-%d")

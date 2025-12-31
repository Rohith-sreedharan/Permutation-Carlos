"""
Automatic Odds Refresh Service
Attempts to fetch fresh odds when stale data is detected
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import logging

from integrations.odds_api import fetch_odds, normalize_event, OddsApiError
from db.mongo import db

logger = logging.getLogger(__name__)


async def attempt_odds_refresh(
    event_id: str,
    sport_key: str,
    current_event: Dict[str, Any]
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Attempt to refresh odds for an event from the odds API
    
    Args:
        event_id: Event identifier
        sport_key: Sport key for API call
        current_event: Current event data from database
    
    Returns:
        (success, updated_event, error_message)
        - success: True if fresh odds were fetched and saved
        - updated_event: Updated event dict if successful, None otherwise
        - error_message: Error description if failed, None if successful
    """
    try:
        logger.info(f"🔄 Attempting automatic odds refresh for {event_id} ({sport_key})")
        
        # Fetch fresh odds from API
        fresh_data = fetch_odds(
            sport=sport_key,
            region="us",
            markets="h2h,spreads,totals,totals_1h",  # Include 1H markets
            odds_format="american"
        )
        
        if not fresh_data:
            return False, None, "No data returned from odds API"
        
        # Find matching event in fresh data
        home_team = current_event.get("home_team", "")
        away_team = current_event.get("away_team", "")
        
        matching_event = None
        for api_event in fresh_data:
            # Match by team names
            if (api_event.get("home_team") == home_team and 
                api_event.get("away_team") == away_team):
                matching_event = api_event
                break
        
        if not matching_event:
            logger.warning(f"⚠️ No matching event found in fresh API data for {home_team} vs {away_team}")
            return False, None, "Event not found in fresh odds data"
        
        # Normalize and update event
        normalized = normalize_event(matching_event)
        
        # Check if odds are actually fresher
        current_timestamp = current_event.get("odds_timestamp")
        new_timestamp = normalized.get("odds_timestamp")
        
        if current_timestamp and new_timestamp:
            try:
                current_time = datetime.fromisoformat(current_timestamp.replace('Z', '+00:00'))
                new_time = datetime.fromisoformat(new_timestamp.replace('Z', '+00:00'))
                
                if new_time <= current_time:
                    logger.info(f"ℹ️ Fresh data is not newer than current data ({new_timestamp} <= {current_timestamp})")
                    return False, None, "Fresh data not newer than current data"
            except:
                pass  # If timestamp parsing fails, proceed with update anyway
        
        # Update database with fresh odds
        db["events"].update_one(
            {"event_id": event_id},
            {
                "$set": {
                    "bookmakers": normalized.get("bookmakers", []),
                    "odds_timestamp": new_timestamp,
                    "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
                    "auto_refresh_count": current_event.get("auto_refresh_count", 0) + 1
                }
            }
        )
        
        # Merge updated odds into current event
        updated_event = current_event.copy()
        updated_event["bookmakers"] = normalized.get("bookmakers", [])
        updated_event["odds_timestamp"] = new_timestamp
        updated_event["last_refreshed_at"] = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"✅ Successfully refreshed odds for {event_id}: {current_timestamp} → {new_timestamp}")
        
        # Track refresh in observability
        db["odds_refresh_log"].insert_one({
            "event_id": event_id,
            "sport_key": sport_key,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "old_timestamp": current_timestamp,
            "new_timestamp": new_timestamp,
            "success": True
        })
        
        return True, updated_event, None
        
    except OddsApiError as e:
        error_msg = f"Odds API error: {str(e)}"
        logger.error(f"❌ Failed to refresh odds for {event_id}: {error_msg}")
        
        # Log failed refresh attempt
        db["odds_refresh_log"].insert_one({
            "event_id": event_id,
            "sport_key": sport_key,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": error_msg
        })
        
        return False, None, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"❌ Failed to refresh odds for {event_id}: {error_msg}")
        return False, None, error_msg


def log_stale_odds_occurrence(
    event_id: str,
    sport_key: str,
    odds_age_hours: float,
    bookmaker_source: Optional[str],
    integrity_status: str
):
    """
    Log stale odds occurrence for observability/alerting
    
    Args:
        event_id: Event identifier
        sport_key: Sport key
        odds_age_hours: How old the odds are in hours
        bookmaker_source: Which bookmaker provided the stale odds
        integrity_status: Integrity status (stale_line, ok, etc.)
    """
    try:
        db["stale_odds_metrics"].insert_one({
            "event_id": event_id,
            "sport_key": sport_key,
            "odds_age_hours": odds_age_hours,
            "bookmaker_source": bookmaker_source,
            "integrity_status": integrity_status,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        })
    except Exception as e:
        logger.error(f"Failed to log stale odds metric: {e}")

"""
Backfill OddsAPI Event IDs — Migration Script
==============================================

This script backfills provider_event_map.oddsapi.event_id for existing events.

Strategy (FUZZY MATCHING ALLOWED ONLY IN THIS SCRIPT):
1. Fetch all events from events collection without OddsAPI mapping
2. For each event, fetch OddsAPI events by sport + date range
3. Match by team names + commence_time (±300 seconds tolerance)
4. Update event with oddsapi_event_id

⚠️ IMPORTANT: After backfill, production code must use EXACT ID lookup only.

Usage:
    python backend/scripts/backfill_oddsapi_ids.py [--dry-run] [--limit N]
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db.mongo import db
from backend.integrations.odds_api import fetch_odds
from dateutil.parser import parse as parse_datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OddsAPIBackfillService:
    """Backfill OddsAPI event IDs for historical events"""
    
    def __init__(self, db, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.stats = {
            "total_events": 0,
            "already_mapped": 0,
            "matched": 0,
            "no_match_found": 0,
            "errors": 0
        }
    
    async def backfill_all(self, limit: Optional[int] = None):
        """
        Backfill all events missing OddsAPI mapping
        
        Args:
            limit: Max number of events to process (None = all)
        """
        logger.info("=" * 70)
        logger.info("ODDSAPI EVENT ID BACKFILL")
        logger.info("=" * 70)
        logger.info(f"Dry run: {self.dry_run}")
        logger.info(f"Limit: {limit if limit else 'None (process all)'}")
        
        # Find events without OddsAPI mapping
        query = {
            "$or": [
                {"provider_event_map.oddsapi.event_id": {"$exists": False}},
                {"provider_event_map.oddsapi.event_id": None}
            ]
        }
        
        events_cursor = self.db["events"].find(query)
        if limit:
            events_cursor = events_cursor.limit(limit)
        
        events = list(events_cursor)
        self.stats["total_events"] = len(events)
        
        logger.info(f"\nFound {len(events)} events to backfill\n")
        
        for idx, event in enumerate(events, 1):
            logger.info(f"[{idx}/{len(events)}] Processing {event.get('event_id')}...")
            
            # Check if already has mapping (race condition protection)
            if self._has_oddsapi_mapping(event):
                logger.info(f"  ✅ Already mapped (skipping)")
                self.stats["already_mapped"] += 1
                continue
            
            try:
                # Attempt to match and update
                matched = await self._match_and_update(event)
                
                if matched:
                    logger.info(f"  ✅ Matched and updated")
                    self.stats["matched"] += 1
                else:
                    logger.warning(f"  ❌ No match found")
                    self.stats["no_match_found"] += 1
            
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                self.stats["errors"] += 1
        
        # Print summary
        self._print_summary()
    
    def _has_oddsapi_mapping(self, event: Dict[str, Any]) -> bool:
        """Check if event already has OddsAPI mapping"""
        provider_map = event.get("provider_event_map", {})
        oddsapi_map = provider_map.get("oddsapi", {})
        return bool(oddsapi_map.get("event_id"))
    
    async def _match_and_update(self, event: Dict[str, Any]) -> bool:
        """
        Match event to OddsAPI event and update
        
        Returns:
            True if matched and updated, False otherwise
        """
        event_id = event.get("event_id")
        sport_key = event.get("sport_key")
        home_team = event.get("home_team")
        away_team = event.get("away_team")
        commence_time = event.get("commence_time")
        
        if not all([sport_key, home_team, away_team, commence_time]):
            logger.warning(f"  Missing required fields for matching")
            return False
        
        # Parse commence time
        try:
            if not commence_time:
                raise ValueError("commence_time is required")
            commence_dt = parse_datetime(commence_time)
        except Exception as e:
            logger.error(f"  Failed to parse commence_time: {e}")
            return False
        
        # Fetch OddsAPI events for date range
        date_str = commence_dt.strftime("%Y-%m-%d")
        
        try:
            if not sport_key:
                raise ValueError("sport_key is required")
            oddsapi_events = await self._fetch_oddsapi_events(sport_key, commence_dt)
        except Exception as e:
            logger.error(f"  Failed to fetch OddsAPI events: {e}")
            return False
        
        if not oddsapi_events:
            logger.warning(f"  No OddsAPI events found for {sport_key} on {date_str}")
            return False
        
        # Match by team names + commence_time
        if not home_team or not away_team:
            logger.error(f"  Missing team names")
            return False
        matched_event = self._find_matching_event(
            oddsapi_events=oddsapi_events,
            home_team=home_team,
            away_team=away_team,
            commence_time=commence_dt
        )
        
        if not matched_event:
            return False
        
        # Extract OddsAPI ID
        oddsapi_event_id = matched_event.get("id")
        if not oddsapi_event_id:
            logger.error(f"  Matched event missing 'id' field")
            return False
        
        # Update event (if not dry run)
        if not self.dry_run:
            if not event_id:
                logger.error(f"  Missing event_id")
                return False
            self._update_event_mapping(event_id, oddsapi_event_id, matched_event)
        else:
            logger.info(f"  [DRY RUN] Would update with OddsAPI ID: {oddsapi_event_id}")
        
        return True
    
    async def _fetch_oddsapi_events(
        self,
        sport_key: str,
        commence_dt: datetime
    ) -> list:
        """
        Fetch OddsAPI events for sport + date
        
        Note: This is a simplified version. Your actual implementation
        may need to call the OddsAPI /sports/{sport}/odds endpoint.
        """
        # For backfill, we fetch events from a date range around commence_time
        # This is a placeholder - you'll need to implement actual OddsAPI fetch
        
        # Example: Call your existing fetch_odds function
        # You may need to modify it to support historical lookups
        try:
            # Placeholder: fetch from OddsAPI scores endpoint
            # Note: This requires proper OddsAPI integration
            # For now, return empty list to avoid import errors
            logger.warning(f"OddsAPI fetch not fully implemented for backfill")
            return []
            
            # Try scores endpoint first (for completed games)
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores"
            params = {
                "apiKey": client.api_key,
                "daysFrom": 3  # Look back 3 days
            }
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            
            return []
        
        except Exception as e:
            logger.error(f"Failed to fetch OddsAPI events: {e}")
            return []
    
    def _find_matching_event(
        self,
        oddsapi_events: list,
        home_team: str,
        away_team: str,
        commence_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Find matching OddsAPI event by team names + commence_time
        
        Matching criteria:
        - Exact team name match (case-insensitive)
        - Commence time within ±300 seconds
        """
        for oddsapi_event in oddsapi_events:
            oddsapi_home = oddsapi_event.get("home_team", "").strip().lower()
            oddsapi_away = oddsapi_event.get("away_team", "").strip().lower()
            oddsapi_commence = oddsapi_event.get("commence_time")
            
            # Check team match
            if (oddsapi_home == home_team.strip().lower() and
                oddsapi_away == away_team.strip().lower()):
                
                # Check time match (within ±300 seconds)
                if oddsapi_commence:
                    try:
                        oddsapi_dt = parse_datetime(oddsapi_commence)
                        time_diff = abs((oddsapi_dt - commence_time).total_seconds())
                        
                        if time_diff <= 300:  # 5 minutes tolerance
                            logger.info(f"    Match found: {oddsapi_event.get('id')}")
                            logger.info(f"    Teams: {oddsapi_home} vs {oddsapi_away}")
                            logger.info(f"    Time diff: {time_diff:.0f} seconds")
                            return oddsapi_event
                    except Exception as e:
                        logger.warning(f"    Failed to parse OddsAPI commence_time: {e}")
                        continue
        
        return None
    
    def _update_event_mapping(
        self,
        event_id: str,
        oddsapi_event_id: str,
        matched_event: Dict[str, Any]
    ):
        """Update event with OddsAPI mapping"""
        update_doc = {
            "$set": {
                "provider_event_map.oddsapi": {
                    "event_id": oddsapi_event_id,
                    "raw_payload": matched_event,
                    "backfilled_at": datetime.now(timezone.utc).isoformat()
                }
            }
        }
        
        self.db["events"].update_one(
            {"event_id": event_id},
            update_doc
        )
    
    def _print_summary(self):
        """Print backfill summary"""
        logger.info("\n" + "=" * 70)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total events processed:  {self.stats['total_events']}")
        logger.info(f"Already mapped:          {self.stats['already_mapped']}")
        logger.info(f"Matched and updated:     {self.stats['matched']}")
        logger.info(f"No match found:          {self.stats['no_match_found']}")
        logger.info(f"Errors:                  {self.stats['errors']}")
        logger.info("=" * 70)
        
        if self.dry_run:
            logger.info("\n⚠️  DRY RUN - No changes were made to the database")
        else:
            logger.info("\n✅ Backfill complete")


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backfill OddsAPI event IDs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (no updates)")
    parser.add_argument("--limit", type=int, help="Max events to process")
    
    args = parser.parse_args()
    
    # Run backfill
    service = OddsAPIBackfillService(db, dry_run=args.dry_run)
    await service.backfill_all(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())

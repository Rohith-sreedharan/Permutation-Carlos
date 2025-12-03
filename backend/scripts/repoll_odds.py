#!/usr/bin/env python3
"""
Repoll OddsAPI and populate events database
This script fetches fresh events from OddsAPI for all major sports and stores them in MongoDB
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from integrations.odds_api import fetch_odds, normalize_event, OddsApiError
from db.mongo import db, upsert_events, ensure_indexes
from utils.timezone import now_est, get_est_date_today

# Sports to poll
SPORTS = [
    "basketball_nba",
    "basketball_ncaab",          # NCAA Basketball
    "americanfootball_nfl",
    "americanfootball_ncaaf",    # NCAA Football
    "baseball_mlb",
    "icehockey_nhl",
]


def repoll_all_sports():
    """Fetch fresh odds for all major sports and store in database."""
    print(f"🔄 Repolling OddsAPI at {now_est().strftime('%Y-%m-%d %H:%M:%S EST')}")
    print(f"📅 Today's EST date: {get_est_date_today()}\n")
    
    # Ensure indexes exist
    print("🔧 Ensuring database indexes...")
    ensure_indexes()
    
    total_events = 0
    
    for sport in SPORTS:
        print(f"\n📡 Fetching {sport}...")
        try:
            # Fetch from multiple regions
            regions = ["us", "us2", "uk", "eu"]
            all_events = []
            
            for region in regions:
                try:
                    raw_events = fetch_odds(
                        sport=sport,
                        region=region,
                        markets="h2h,spreads,totals",
                        odds_format="decimal"
                    )
                    all_events.extend(raw_events)
                    print(f"  ✓ {region}: {len(raw_events)} events")
                except OddsApiError as e:
                    print(f"  ⚠️ {region}: {str(e)}")
            
            # Normalize and upsert
            if all_events:
                normalized = [normalize_event(ev) for ev in all_events]
                count = upsert_events("events", normalized)
                total_events += count
                print(f"  ✅ Upserted {count} unique events for {sport}")
            else:
                print(f"  ⚠️ No events found for {sport}")
                
        except Exception as e:
            print(f"  ❌ Error fetching {sport}: {str(e)}")
    
    print(f"\n✨ Repoll complete! Total events: {total_events}")
    
    # Show summary by sport
    print(f"\n📊 Database summary:")
    for sport in SPORTS:
        count = db["events"].count_documents({"sport_key": sport})
        print(f"  {sport}: {count} events")
    
    total_db = db["events"].count_documents({})
    print(f"  TOTAL: {total_db} events in database")


def clear_and_repoll():
    """Clear existing events and repoll from scratch."""
    print("🗑️  Clearing existing events...")
    result = db["events"].delete_many({})
    print(f"  Deleted {result.deleted_count} events\n")
    repoll_all_sports()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Repoll OddsAPI and populate events database")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing events before repolling"
    )
    
    args = parser.parse_args()
    
    if args.clear:
        clear_and_repoll()
    else:
        repoll_all_sports()

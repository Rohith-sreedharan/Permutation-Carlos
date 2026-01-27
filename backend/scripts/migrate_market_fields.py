#!/usr/bin/env python3
"""
MongoDB Migration: Add market_type and market_settlement fields to simulations collection
vFinal.1 Multi-Sport Patch - Phase 2

Per specification Section 3.1:
- Adds market_type: "SPREAD" | "TOTAL" | "MONEYLINE_2WAY" | "MONEYLINE_3WAY"
- Adds market_settlement: "FULL_GAME" | "REGULATION"
- Infers values from existing 'market' field
- Uses sport-specific defaults from SportConfig

CRITICAL: Run this BEFORE updating API routes
"""
import os
import sys
from pymongo import MongoClient
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sport_config import get_sport_config, MarketType, MarketSettlement

load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "beatvegas")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


def migrate_add_market_fields(dry_run: bool = True):
    """
    Add market_type and market_settlement fields to existing documents.
    
    Args:
        dry_run: If True, only prints what would be done without modifying database
    """
    print("=" * 80)
    print("MongoDB Migration: market_type + market_settlement fields")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    print("=" * 80)
    print()
    
    # Find simulations that need migration (don't have new fields)
    query = {"market_type": {"$exists": False}}
    total_to_migrate = db.simulations.count_documents(query)
    
    print(f"📊 Simulations to migrate: {total_to_migrate}")
    
    if total_to_migrate == 0:
        print("✅ No simulations need migration. All documents already have market_type field.")
        return (0, 0)  # Return tuple for consistency
    
    print()
    
    # Sample first few documents for preview
    sample_docs = list(db.simulations.find(query).limit(5))
    if sample_docs:
        print("📋 Sample documents (first 5):")
        for i, doc in enumerate(sample_docs, 1):
            print(f"  {i}. game_id: {doc.get('game_id', 'N/A')}, "
                  f"market: {doc.get('market', 'N/A')}, "
                  f"sport_key: {doc.get('sport_key', 'N/A')}")
        print()
    
    if dry_run:
        print("🔍 DRY RUN: Simulating migration logic...")
        print()
    
    # Process documents in batches
    batch_size = 100
    migrated_count = 0
    error_count = 0
    
    # Group by unique combinations for efficiency
    migration_stats = {
        'SPREAD': 0,
        'TOTAL': 0,
        'MONEYLINE_2WAY': 0,
        'MONEYLINE_3WAY': 0,
        'errors': []
    }
    
    cursor = db.simulations.find(query)
    
    for sim in cursor:
        try:
            # Extract sport code from sport_key (e.g., "basketball_nba" -> "NBA")
            sport_key = sim.get('sport_key', '')
            sport_code = extract_sport_code(sport_key)
            
            # Get market from legacy 'market' field
            market = sim.get('market', '')
            
            # Get sport config for defaults
            config = get_sport_config(sport_code)
            
            # Infer market_type from legacy 'market' field
            if market == 'spread':
                market_type = MarketType.SPREAD.value
            elif market == 'total':
                market_type = MarketType.TOTAL.value
            elif market == 'moneyline':
                # Use sport's default moneyline type
                market_type = config.default_ml_type.value
            else:
                raise ValueError(f"Unknown market: {market}")
            
            # Default to FULL_GAME settlement (spec Section 3.1)
            market_settlement = config.default_ml_settlement.value
            
            # Update document
            if not dry_run:
                db.simulations.update_one(
                    {"_id": sim["_id"]},
                    {
                        "$set": {
                            "market_type": market_type,
                            "market_settlement": market_settlement,
                            "migrated_at": datetime.now(timezone.utc)
                        }
                    }
                )
            
            migrated_count += 1
            migration_stats[market_type] += 1
            
            # Progress indicator
            if migrated_count % batch_size == 0:
                print(f"  ⏳ Processed {migrated_count}/{total_to_migrate}...")
        
        except Exception as e:
            error_count += 1
            error_info = {
                'game_id': sim.get('game_id', 'unknown'),
                'market': sim.get('market', 'unknown'),
                'sport_key': sim.get('sport_key', 'unknown'),
                'error': str(e)
            }
            migration_stats['errors'].append(error_info)
            print(f"  ❌ Error migrating {sim.get('game_id', 'unknown')}: {e}")
    
    # Summary
    print()
    print("=" * 80)
    print("Migration Summary")
    print("=" * 80)
    print(f"✅ Successfully migrated: {migrated_count}")
    print(f"❌ Errors: {error_count}")
    print()
    print("Market Type Distribution:")
    print(f"  SPREAD: {migration_stats['SPREAD']}")
    print(f"  TOTAL: {migration_stats['TOTAL']}")
    print(f"  MONEYLINE_2WAY: {migration_stats['MONEYLINE_2WAY']}")
    print(f"  MONEYLINE_3WAY: {migration_stats['MONEYLINE_3WAY']}")
    print()
    
    if migration_stats['errors']:
        print("Errors encountered:")
        for error in migration_stats['errors'][:10]:  # Show first 10 errors
            print(f"  - {error['game_id']}: {error['error']}")
        if len(migration_stats['errors']) > 10:
            print(f"  ... and {len(migration_stats['errors']) - 10} more")
        print()
    
    if dry_run:
        print("⚠️  This was a DRY RUN. No changes were made to the database.")
        print("   Run with --live flag to apply changes.")
    else:
        print("✅ Migration complete. Database has been updated.")
    
    print()
    return (migrated_count, error_count)


def extract_sport_code(sport_key: str) -> str:
    """
    Extract sport code from sport_key.
    
    Examples:
        basketball_nba -> NBA
        americanfootball_nfl -> NFL
        icehockey_nhl -> NHL
        basketball_ncaab -> NCAAB
    """
    # Map sport_key patterns to sport codes
    sport_mappings = {
        'basketball_nba': 'NBA',
        'americanfootball_nfl': 'NFL',
        'icehockey_nhl': 'NHL',
        'basketball_ncaab': 'NCAAB',
        'americanfootball_ncaaf': 'NCAAF',
        'baseball_mlb': 'MLB',
    }
    
    # Try exact match first
    if sport_key in sport_mappings:
        return sport_mappings[sport_key]
    
    # Fallback: extract suffix
    if '_' in sport_key:
        suffix = sport_key.split('_')[1].upper()
        if suffix in ['NBA', 'NFL', 'NHL', 'NCAAB', 'NCAAF', 'MLB']:
            return suffix
    
    # Default to NBA if unknown
    print(f"⚠️  Unknown sport_key '{sport_key}', defaulting to NBA")
    return 'NBA'


def verify_migration():
    """Verify migration was successful."""
    print("=" * 80)
    print("Verification")
    print("=" * 80)
    print()
    
    # Check if any documents still lack new fields
    missing_fields = db.simulations.count_documents({
        "$or": [
            {"market_type": {"$exists": False}},
            {"market_settlement": {"$exists": False}}
        ]
    })
    
    if missing_fields == 0:
        print("✅ All simulations have market_type and market_settlement fields")
    else:
        print(f"⚠️  {missing_fields} simulations still missing new fields")
    
    # Show distribution
    total = db.simulations.count_documents({})
    print(f"\nTotal simulations: {total}")
    
    if total > 0:
        print("\nMarket Type Distribution:")
        for market_type in ['SPREAD', 'TOTAL', 'MONEYLINE_2WAY', 'MONEYLINE_3WAY']:
            count = db.simulations.count_documents({"market_type": market_type})
            percentage = (count / total) * 100
            print(f"  {market_type}: {count} ({percentage:.1f}%)")
        
        print("\nMarket Settlement Distribution:")
        for settlement in ['FULL_GAME', 'REGULATION']:
            count = db.simulations.count_documents({"market_settlement": settlement})
            percentage = (count / total) * 100
            print(f"  {settlement}: {count} ({percentage:.1f}%)")
    
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate simulations collection to add market_type and market_settlement fields"
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Apply changes to database (default is dry run)'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify migration results'
    )
    
    args = parser.parse_args()
    
    if args.verify:
        verify_migration()
    else:
        dry_run = not args.live
        migrated, errors = migrate_add_market_fields(dry_run=dry_run)
        
        if not dry_run and errors == 0:
            print("Running verification...")
            print()
            verify_migration()

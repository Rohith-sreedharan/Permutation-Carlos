"""
Seed script for league_total_stats
Populates historical total statistics for major leagues

Data sources:
- NBA: Historical averages from 2020-2024 seasons
- NCAAB: Historical averages from 2020-2024 seasons
- NFL: Historical averages from 2020-2024 seasons
- NCAAF: Historical averages from 2020-2024 seasons
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from db.mongo import db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Historical league statistics (based on recent seasons)
LEAGUE_STATS = {
    "NBA": {
        "league_code": "NBA",
        "sample_size": 5000,
        "mean_total": 224.5,
        "std_total": 12.8,
        "min_total": 180.0,
        "max_total": 280.0,
        "p25_total": 216.0,
        "p50_total": 224.0,
        "p75_total": 233.0,
    },
    "NCAAB": {
        "league_code": "NCAAB",
        "sample_size": 8000,
        "mean_total": 145.0,
        "std_total": 12.0,
        "min_total": 100.0,
        "max_total": 190.0,
        "p25_total": 137.0,
        "p50_total": 145.0,
        "p75_total": 153.0,
    },
    "WNBA": {
        "league_code": "WNBA",
        "sample_size": 800,
        "mean_total": 163.5,
        "std_total": 11.5,
        "min_total": 130.0,
        "max_total": 200.0,
        "p25_total": 156.0,
        "p50_total": 163.0,
        "p75_total": 171.0,
    },
    "NFL": {
        "league_code": "NFL",
        "sample_size": 2000,
        "mean_total": 45.5,
        "std_total": 10.5,
        "min_total": 16.0,
        "max_total": 90.0,
        "p25_total": 39.0,
        "p50_total": 45.0,
        "p75_total": 52.0,
    },
    "NCAAF": {
        "league_code": "NCAAF",
        "sample_size": 3000,
        "mean_total": 57.5,
        "std_total": 13.5,
        "min_total": 20.0,
        "max_total": 110.0,
        "p25_total": 48.0,
        "p50_total": 57.0,
        "p75_total": 67.0,
    },
    "NHL": {
        "league_code": "NHL",
        "sample_size": 2500,
        "mean_total": 6.2,
        "std_total": 1.8,
        "min_total": 2.0,
        "max_total": 13.0,
        "p25_total": 5.0,
        "p50_total": 6.0,
        "p75_total": 7.5,
    },
    "MLB": {
        "league_code": "MLB",
        "sample_size": 4000,
        "mean_total": 8.8,
        "std_total": 2.3,
        "min_total": 2.0,
        "max_total": 20.0,
        "p25_total": 7.0,
        "p50_total": 9.0,
        "p75_total": 11.0,
    },
}


def seed_league_stats():
    """
    Seed league_total_stats with historical data
    """
    logger.info("🌱 Seeding league_total_stats...")
    
    for league_code, stats in LEAGUE_STATS.items():
        # Add timestamp
        stats_with_timestamp = {
            **stats,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Upsert (insert or update)
        result = db["league_total_stats"].update_one(
            {"league_code": league_code},
            {"$set": stats_with_timestamp},
            upsert=True
        )
        
        if result.upserted_id:
            logger.info(f"✅ Inserted {league_code}: mean={stats['mean_total']:.1f}, std={stats['std_total']:.1f}")
        else:
            logger.info(f"🔄 Updated {league_code}: mean={stats['mean_total']:.1f}, std={stats['std_total']:.1f}")
    
    # Verify
    count = db["league_total_stats"].count_documents({})
    logger.info(f"✅ Seeded {count} leagues")
    
    # Display all leagues
    logger.info("\n📊 League Total Stats:")
    logger.info("-" * 80)
    logger.info(f"{'League':<10} {'Mean':<10} {'Std':<10} {'Min':<10} {'Max':<10} {'Sample Size':<15}")
    logger.info("-" * 80)
    
    for doc in db["league_total_stats"].find().sort("league_code", 1):
        logger.info(
            f"{doc['league_code']:<10} "
            f"{doc['mean_total']:<10.1f} "
            f"{doc['std_total']:<10.1f} "
            f"{doc['min_total']:<10.1f} "
            f"{doc['max_total']:<10.1f} "
            f"{doc['sample_size']:<15}"
        )
    
    logger.info("-" * 80)


def display_rcl_thresholds():
    """
    Display RCL thresholds for each league
    """
    from core.reality_check_layer import MAX_SIGMA
    
    logger.info("\n🛡️  RCL Thresholds (±2σ):")
    logger.info("-" * 80)
    logger.info(f"{'League':<10} {'Mean':<10} {'Min Allowed':<15} {'Max Allowed':<15}")
    logger.info("-" * 80)
    
    for doc in db["league_total_stats"].find().sort("league_code", 1):
        mean = doc['mean_total']
        std = doc['std_total']
        min_allowed = mean - (MAX_SIGMA * std)
        max_allowed = mean + (MAX_SIGMA * std)
        
        logger.info(
            f"{doc['league_code']:<10} "
            f"{mean:<10.1f} "
            f"{min_allowed:<15.1f} "
            f"{max_allowed:<15.1f}"
        )
    
    logger.info("-" * 80)
    logger.info(f"Any projection outside these bounds will be clamped or flagged.")


if __name__ == "__main__":
    seed_league_stats()
    display_rcl_thresholds()
    logger.info("\n✅ League stats seeding complete!")

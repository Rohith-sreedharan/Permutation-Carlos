#!/usr/bin/env python3
"""
Daily Calibration Job
Runs every night at 2 AM EST to compute calibration metrics for all sports

This script:
1. Fetches actual game results from ESPN
2. Compares model predictions vs actual outcomes
3. Computes bias, over_rate, win_rate metrics
4. Applies dampening factor if bias thresholds exceeded
5. Stores results in calibration_daily collection

Usage:
    python3 scripts/daily_calibration_job.py
    
Or via cron (runs at 2 AM EST daily):
    0 2 * * * cd /path/to/backend && source .venv/bin/activate && PYTHONPATH=/path/to/backend python3 scripts/daily_calibration_job.py >> logs/calibration.log 2>&1
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from core.calibration_logger import CalibrationLogger
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/calibration.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# All supported sports
SPORTS = [
    "americanfootball_nfl",
    "americanfootball_ncaaf",
    "basketball_nba",
    "basketball_ncaab",
    "baseball_mlb",
    "icehockey_nhl"
]

def run_daily_calibration():
    """Run daily calibration for all sports"""
    logger.info("=" * 80)
    logger.info("🎯 DAILY CALIBRATION JOB STARTED")
    logger.info("=" * 80)
    
    calibration_logger = CalibrationLogger()
    
    # Use yesterday's date (games that finished)
    target_date = datetime.now().date() - timedelta(days=1)
    
    results = {}
    for sport in SPORTS:
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 Processing {sport} for {target_date}")
            logger.info(f"{'='*60}")
            
            result = calibration_logger.compute_daily_calibration(
                sport=sport,
                date=target_date
            )
            
            results[sport] = result
            
            # Log summary
            if result:
                logger.info(f"✅ {sport} Calibration Complete:")
                logger.info(f"   Games Analyzed: {result.get('games_completed', 0)}")
                logger.info(f"   Bias vs Actual: {result.get('bias_vs_actual', 0):.2f} pts")
                logger.info(f"   Bias vs Market: {result.get('bias_vs_market', 0):.2f} pts")
                logger.info(f"   Over Rate: {result.get('over_rate', 0):.1%}")
                logger.info(f"   Win Rate: {result.get('win_rate', 0):.1%}")
                logger.info(f"   Damp Factor: {result.get('damp_factor', 1.0):.3f}")
                
                # Check if dampening triggered
                if result.get('damp_factor', 1.0) < 1.0:
                    logger.warning(f"⚠️  DAMPENING ACTIVE for {sport}: {result.get('damp_reason', 'Unknown')}")
            else:
                logger.info(f"ℹ️  No games to calibrate for {sport} on {target_date}")
                
        except Exception as e:
            logger.error(f"❌ Failed to process {sport}: {str(e)}", exc_info=True)
            results[sport] = {"error": str(e)}
    
    logger.info("\n" + "=" * 80)
    logger.info("🏁 DAILY CALIBRATION JOB COMPLETED")
    logger.info("=" * 80)
    
    # Summary
    successful = sum(1 for r in results.values() if r and not r.get('error'))
    failed = sum(1 for r in results.values() if r and r.get('error'))
    
    logger.info(f"\nSummary: {successful} sports processed successfully, {failed} failed")
    
    return results

if __name__ == "__main__":
    try:
        results = run_daily_calibration()
        
        # Exit with error code if any sport failed
        if any(r and r.get('error') for r in results.values()):
            sys.exit(1)
        else:
            sys.exit(0)
    except Exception as e:
        logger.error(f"💥 FATAL ERROR: {str(e)}", exc_info=True)
        sys.exit(1)

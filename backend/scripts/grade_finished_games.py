"""
Cron job script: Grade all finished games
Runs every 30 minutes to grade newly completed games

Usage:
    python scripts/grade_finished_games.py
    
Or via cron:
    */30 * * * * cd /path/to/backend && python scripts/grade_finished_games.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from services.post_game_grader import post_game_grader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    Grade all finished games from the last 48 hours
    """
    logger.info("🎯 Starting post-game grading job...")
    
    try:
        # Grade all finished games from last 48 hours
        summary = post_game_grader.grade_all_finished_games(hours_back=48)
        
        logger.info(f"✅ Grading complete: {summary}")
        
        # Log summary
        if summary["graded"] > 0:
            logger.info(f"✅ Graded {summary['graded']} new games")
        
        if summary["errors"] > 0:
            logger.warning(f"⚠️  {summary['errors']} games failed to grade")
        
        if summary["skipped"] > 0:
            logger.info(f"⏭️  Skipped {summary['skipped']} already-graded games")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Grading job failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

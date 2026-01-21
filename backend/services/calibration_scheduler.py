"""
Calibration Scheduler
=====================
Automated weekly calibration job scheduler.

Runs calibration job on schedule (weekly or twice-weekly).
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from services.calibration_service import calibration_service
from services.grading_service import grading_service
import logging

logger = logging.getLogger(__name__)


class CalibrationScheduler:
    """
    Manages scheduled calibration jobs
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        """
        Start the calibration scheduler
        
        Default schedule: Every Sunday at 3:00 AM UTC
        """
        # Weekly calibration job
        self.scheduler.add_job(
            func=self.run_weekly_calibration,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='weekly_calibration',
            name='Weekly Calibration Job',
            replace_existing=True
        )
        
        # Daily grading job (grade completed games)
        self.scheduler.add_job(
            func=self.run_daily_grading,
            trigger=CronTrigger(hour=4, minute=0),  # 4:00 AM UTC daily
            id='daily_grading',
            name='Daily Grading Job',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Calibration scheduler started")
        logger.info("  - Weekly calibration: Sundays at 3:00 AM UTC")
        logger.info("  - Daily grading: Every day at 4:00 AM UTC")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("🛑 Calibration scheduler stopped")
    
    def run_weekly_calibration(self):
        """
        Run weekly calibration job
        """
        logger.info("=" * 60)
        logger.info("🎯 STARTING WEEKLY CALIBRATION JOB")
        logger.info("=" * 60)
        
        try:
            calibration_version = calibration_service.run_calibration_job(
                training_days=30,
                method="isotonic"
            )
            
            if calibration_version:
                logger.info(f"✅ Calibration job completed: {calibration_version}")
            else:
                logger.warning("⚠️ Calibration job did not create a new version")
        
        except Exception as e:
            logger.error(f"❌ Error in weekly calibration job: {e}", exc_info=True)
    
    def run_daily_grading(self):
        """
        Run daily grading job (grade completed games)
        """
        logger.info("=" * 60)
        logger.info("📊 STARTING DAILY GRADING JOB")
        logger.info("=" * 60)
        
        try:
            stats = grading_service.grade_all_pending(lookback_hours=48)
            
            logger.info(
                f"✅ Grading job completed: "
                f"{stats['graded']} graded, "
                f"{stats['voided']} voided, "
                f"{stats['pending']} pending"
            )
        
        except Exception as e:
            logger.error(f"❌ Error in daily grading job: {e}", exc_info=True)
    
    def run_now(self, job_id: str):
        """
        Manually trigger a scheduled job
        """
        job = self.scheduler.get_job(job_id)
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return False
        
        job.func()
        return True


# Singleton instance
calibration_scheduler = CalibrationScheduler()


def start_calibration_scheduler():
    """
    Start the calibration scheduler (call from main.py)
    """
    calibration_scheduler.start()


def stop_calibration_scheduler():
    """
    Stop the calibration scheduler
    """
    calibration_scheduler.stop()

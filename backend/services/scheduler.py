"""
Background Scheduler
Runs scheduled jobs for odds polling and reflection loop
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import requests
import os
from db.mongo import db, upsert_events
from core.reflection_loop import reflection_loop
from services.logger import log_stage


scheduler = BackgroundScheduler()


def poll_odds_api(sport: str = "basketball_nba", markets: str = "h2h,spreads,totals"):
    """
    Poll Odds API for real-time data
    
    SLO: < 20s pre-match, < 10s in-play
    """
    try:
        api_key = os.getenv("ODDS_API_KEY")
        base_url = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4/")
        
        url = f"{base_url}sports/{sport}/odds"
        params = {
            "apiKey": api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": "decimal"
        }
        
        start_time = datetime.now(timezone.utc)
        response = requests.get(url, params=params, timeout=15)
        end_time = datetime.now(timezone.utc)
        
        latency_ms = (end_time - start_time).total_seconds() * 1000
        
        if response.status_code == 200:
            events = response.json()
            count = upsert_events("events", events)
            
            log_stage(
                "odds_polling",
                "success",
                input_payload={
                    "sport": sport,
                    "markets": markets
                },
                output_payload={
                    "count": count,
                    "latency_ms": latency_ms,
                    "slo_met": latency_ms < 20000  # 20s SLO
                }
            )
            
            print(f"✓ Polled {count} events for {sport} in {latency_ms:.0f}ms")
        else:
            log_stage(
                "odds_polling",
                "error",
                input_payload={
                    "sport": sport,
                    "status_code": response.status_code
                },
                output_payload={
                    "error": response.text
                },
                level="ERROR"
            )
            print(f"✗ Odds API error: {response.status_code}")
    
    except Exception as e:
        log_stage(
            "odds_polling",
            "exception",
            input_payload={"sport": sport},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception polling odds: {e}")


def run_reflection_loop():
    """
    Run weekly reflection loop
    Module 7: Self-improving AI
    """
    try:
        print("⟳ Running Module 7: Reflection Loop...")
        
        result = reflection_loop.run_weekly_reflection(auto_apply=False)  # Preview mode
        
        print(f"✓ Reflection Loop complete:")
        print(f"  - Performance: ROI {result['performance']['roi']}%, CLV {result['performance']['avg_clv']}%")
        print(f"  - Patches suggested: {len(result['patches'])}")
        
        if result['patches']:
            print("  - Suggested changes:")
            for patch in result['patches']:
                print(f"    • {patch['param']}: {patch['current']} → {patch['suggested']}")
                print(f"      Rationale: {patch['rationale']}")
    
    except Exception as e:
        log_stage(
            "reflection_loop",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception in reflection loop: {e}")


def start_scheduler():
    """
    Start background scheduler with all jobs
    """
    # Job 1: Poll NBA odds every 60 seconds (pre-match)
    scheduler.add_job(
        func=lambda: poll_odds_api("basketball_nba", "h2h,spreads,totals"),
        trigger=IntervalTrigger(seconds=60),
        id="poll_nba_odds",
        name="Poll NBA Odds (60s)",
        replace_existing=True
    )
    
    # Job 2: Poll NFL odds every 60 seconds
    scheduler.add_job(
        func=lambda: poll_odds_api("americanfootball_nfl", "h2h,spreads,totals"),
        trigger=IntervalTrigger(seconds=60),
        id="poll_nfl_odds",
        name="Poll NFL Odds (60s)",
        replace_existing=True
    )
    
    # Job 3: Poll MLB odds every 60 seconds
    scheduler.add_job(
        func=lambda: poll_odds_api("baseball_mlb", "h2h,spreads,totals"),
        trigger=IntervalTrigger(seconds=60),
        id="poll_mlb_odds",
        name="Poll MLB Odds (60s)",
        replace_existing=True
    )
    
    # Job 4: Run reflection loop weekly (Sundays at 2 AM)
    scheduler.add_job(
        func=run_reflection_loop,
        trigger="cron",
        day_of_week="sun",
        hour=2,
        minute=0,
        id="weekly_reflection",
        name="Weekly Reflection Loop",
        replace_existing=True
    )
    
    scheduler.start()
    print("✓ Scheduler started with jobs:")
    print("  - NBA odds polling (60s)")
    print("  - NFL odds polling (60s)")
    print("  - MLB odds polling (60s)")
    print("  - Weekly reflection loop (Sundays 2 AM)")


def stop_scheduler():
    """Stop background scheduler"""
    scheduler.shutdown()
    print("✓ Scheduler stopped")

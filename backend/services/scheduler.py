"""
Background Scheduler
Runs scheduled jobs for odds polling and reflection loop
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone
import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import now_utc
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
        base_url = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")
        
        # Fix: Remove trailing slash from base_url and add it explicitly
        url = f"{base_url.rstrip('/')}/sports/{sport}/odds"
        params = {
            "apiKey": api_key,
            "regions": "us",
            "markets": markets,
            "oddsFormat": "decimal"
        }
        
        start_time = now_utc()
        response = requests.get(url, params=params, timeout=15)
        end_time = now_utc()
        
        latency_ms = (end_time - start_time).total_seconds() * 1000
        
        if response.status_code == 200:
            events = response.json()
            
            # Normalize events to add EST date and other required fields
            from integrations.odds_api import normalize_event
            normalized_events = [normalize_event(event) for event in events]
            
            count = upsert_events("events", normalized_events)
            
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
        elif response.status_code == 404:
            # 404 typically means sport has no active games (out of season)
            print(f"ℹ️  No active games for {sport} (out of season or no events)")
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
            error_detail = response.text[:200] if response.text else "No error message"
            print(f"✗ Odds API error for {sport}: {response.status_code} - {error_detail}")
    
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


def grade_completed_games():
    """
    Grade completed game predictions against real results
    Runs every 2 hours to populate trust metrics with real data
    """
    try:
        import asyncio
        from services.result_grading import result_grading_service
        
        print("⏱️  Running result grading for completed games...")
        
        # Grade games from last 48 hours
        result = asyncio.run(result_grading_service.grade_completed_games(hours_back=48))
        
        log_stage(
            "result_grading",
            "success",
            input_payload={"hours_back": 48},
            output_payload=result
        )
        
        if result.get('graded_count', 0) > 0:
            print(f"✓ Graded {result['graded_count']} predictions:")
            print(f"  - Wins: {result['wins']}, Losses: {result['losses']}")
            print(f"  - Win Rate: {result['win_rate']}%")
            print(f"  - Units Won: {result['units_won']:+.2f}")
    
    except Exception as e:
        print(f"✗ Exception in result grading: {e}")
        log_stage(
            "result_grading",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )


def run_daily_brier_calculation():
    """
    Calculate Brier Scores for yesterday's completed games
    Runs daily at 4 AM to evaluate model calibration
    """
    try:
        from datetime import timedelta
        print("📊 Running daily Brier Score calculation...")
        
        # Get yesterday's date range
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Run reflection loop (it will analyze recent games)
        result = reflection_loop.run_weekly_reflection(auto_apply=False)
        
        log_stage(
            "daily_brier_calculation",
            "success",
            input_payload={"date": yesterday.strftime("%Y-%m-%d")},
            output_payload=result
        )
        
        print(f"✓ Brier Score calculation complete:")
        print(f"  - Brier Score: {result.get('performance', {}).get('brier_score', 'N/A')}")
        print(f"  - Log Loss: {result.get('performance', {}).get('log_loss', 'N/A')}")
        
    except Exception as e:
        log_stage(
            "daily_brier_calculation",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception in Brier calculation: {e}")


def run_auto_grading():
    """
    Grade completed predictions and calculate trust metrics.
    Runs daily at 4 AM EST.
    """
    try:
        import asyncio
        from services.result_service import result_service
        from services.trust_metrics import trust_metrics_service
        
        print("🎯 Running automated prediction grading...")
        
        # Grade predictions from last 24 hours
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        grading_result = loop.run_until_complete(
            result_service.grade_completed_games(hours_back=24)
        )
        
        print(f"✓ Grading complete: {grading_result['wins']}-{grading_result['losses']} ({grading_result['units_won']:+.2f} units)")
        
        # Calculate trust metrics
        print("📊 Calculating trust metrics...")
        metrics = loop.run_until_complete(
            trust_metrics_service.calculate_all_metrics()
        )
        
        print(f"✓ Trust metrics updated:")
        print(f"  - 7-day accuracy: {metrics['overall']['7day_accuracy']}%")
        print(f"  - 30-day ROI: {metrics['overall']['30day_roi']}%")
        
        loop.close()
        
        log_stage(
            "auto_grading",
            "success",
            input_payload={"hours_back": 24},
            output_payload={
                "grading": grading_result,
                "accuracy": metrics['overall']['7day_accuracy']
            }
        )
        
    except Exception as e:
        log_stage(
            "auto_grading",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception in auto-grading: {e}")


def generate_daily_community_content():
    """
    Generate automated community content: game threads, daily prompts, etc.
    Runs daily at 8 AM EST.
    """
    try:
        from services.community_bot import community_bot
        
        print("🤖 Generating daily community content...")
        
        # Generate game threads for all sports
        game_threads = community_bot.generate_daily_game_threads()
        if game_threads:
            count = community_bot.post_messages(game_threads)
            print(f"✓ Posted {count} game threads")
        
        # Generate daily engagement prompt
        prompt = community_bot.generate_daily_prompt()
        community_bot.post_message(prompt)
        print("✓ Posted daily prompt")
        
        log_stage(
            "community_content_generation",
            "success",
            input_payload={},
            output_payload={"game_threads": len(game_threads), "prompts": 1}
        )
        
    except Exception as e:
        log_stage(
            "community_content_generation",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception generating community content: {e}")


def poll_injury_updates():
    """
    Poll ESPN for injury updates
    NOTE: Injuries are now fetched on-demand via ESPN scraping in injury_api.py
    This function is deprecated but kept for potential real-time WebSocket updates
    """
    # DEPRECATED: We now use ESPN scraping on-demand instead of API-SPORTS polling
    # See: backend/integrations/injury_api.py -> fetch_espn_injuries()
    pass


def grade_picks():
    """
    Auto-grade completed picks against actual results
    """
    try:
        # TODO: Implement auto-grading logic
        print("Auto-grading picks...")
    except Exception as e:
        print(f"✗ Exception in auto-grading: {e}")


def poll_all_sports():
    """
    Poll all sports at once using the consolidated repoll logic.
    More efficient than individual sport calls.
    """
    try:
        from integrations.odds_api import fetch_odds, normalize_event
        from utils.timezone import now_est, get_est_date_today
        
        print(f"🔄 Polling all sports at {now_est().strftime('%Y-%m-%d %H:%M:%S EST')}")
        
        sports = [
            "basketball_nba",
            "basketball_ncaab",
            "americanfootball_nfl",
            "americanfootball_ncaaf",
            "baseball_mlb",
            "icehockey_nhl",
        ]
        
        total_events = 0
        
        for sport in sports:
            try:
                # Fetch from multiple regions for comprehensive coverage
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
                    except Exception as e:
                        # Silently skip individual region failures
                        pass
                
                # Normalize and upsert
                if all_events:
                    normalized = [normalize_event(ev) for ev in all_events]
                    count = upsert_events("events", normalized)
                    total_events += count
                    print(f"  ✅ {sport}: {count} events")
                    
            except Exception as e:
                print(f"  ⚠️ {sport}: {str(e)}")
        
        print(f"✓ Polled {total_events} total events across all sports")
        
        log_stage(
            "multi_sport_polling",
            "success",
            input_payload={"sports": sports},
            output_payload={"total_events": total_events}
        )
        
    except Exception as e:
        log_stage(
            "multi_sport_polling",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception polling all sports: {e}")


def run_initial_polls():
    """
    Run initial polls for all sports immediately on server startup.
    This ensures fresh data is available as soon as the server starts.
    """
    print("🔄 Running initial polls for all sports...")
    poll_all_sports()
    print("✓ Initial polls complete")


def start_scheduler():
    """
    Start background scheduler with all jobs
    
    AGGRESSIVE POLLING STRATEGY (PRODUCTION MODE):
    ----------------------------------------------
    • Fast interval: 5 minutes (real-time odds for betting)
    • Polls ALL sports at once instead of individually
    • 1 multi-sport job × 12 polls/hour × 24 hours = 288 requests/day
    • Each request fetches 6 sports from 4 regions = ~24 API calls per poll
    • Total: ~6,912 API calls/day (requires higher quota plan)
    
    Production optimization:
    • Off-season sports: Filter out dynamically
    • Live games: Already polling fast enough
    • Pre-game (<2 hours): 5min is optimal for line movement
    """
    # Run initial polls immediately on startup
    run_initial_polls()
    
    # CONSOLIDATED POLLING: All sports at once every 5 minutes
    scheduler.add_job(
        func=poll_all_sports,
        trigger=IntervalTrigger(minutes=5),
        id="poll_all_sports",
        name="Poll All Sports (5m)",
        replace_existing=True
    )
    
    # Job 2: Poll injury updates every 5 minutes
    scheduler.add_job(
        func=poll_injury_updates,
        trigger=IntervalTrigger(minutes=5),
        id="poll_injuries",
        name="Poll Injury Updates (5m)",
        replace_existing=True
    )
    
    # Job 3: Grade completed games every 2 hours (CRITICAL: Populates trust metrics)
    scheduler.add_job(
        func=grade_completed_games,
        trigger=IntervalTrigger(hours=2),
        id="grade_completed_games",
        name="Grade Completed Games (2h)",
        replace_existing=True
    )
    
    # Job 4: Run daily Brier Score calculation at 4 AM
    scheduler.add_job(
        func=run_daily_brier_calculation,
        trigger="cron",
        hour=4,
        minute=0,
        id="daily_brier",
        name="Daily Brier Score Calculation (4 AM)",
        replace_existing=True
    )
    
    # Job 5: Run automated grading at 4:15 AM (after Brier calculation)
    scheduler.add_job(
        func=run_auto_grading,
        trigger="cron",
        hour=4,
        minute=15,
        id="auto_grading",
        name="Automated Prediction Grading (4:15 AM)",
        replace_existing=True
    )
    
    # Job 6: Generate daily community content at 8 AM EST
    scheduler.add_job(
        func=generate_daily_community_content,
        trigger="cron",
        hour=8,
        minute=0,
        id="daily_community_content",
        name="Daily Community Content Generation (8 AM)",
        replace_existing=True
    )
    
    # Job 7: Run reflection loop weekly (Sundays at 2 AM)
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
    print("  - Multi-sport odds polling (5m) ⚡ FAST MODE - NBA, NFL, MLB, NHL, NCAAB, NCAAF")
    print("  - Injury updates (5m)")
    print("  - Grade completed games (2h)")
    print("  - Daily Brier Score calculation (4 AM)")
    print("  - Automated prediction grading (4:15 AM)")
    print("  - Daily community content generation (8 AM)")
    print("  - Weekly reflection loop (Sundays 2 AM)")
    print("🔄 Initial polls completed - fresh data available immediately")


def stop_scheduler():
    """Stop background scheduler"""
    scheduler.shutdown()
    print("✓ Scheduler stopped")

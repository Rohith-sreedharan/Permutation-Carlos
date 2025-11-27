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


def poll_injury_updates():
    """
    Poll API-SPORTS for injury updates
    Runs every 5 minutes to catch breaking injury news
    """
    try:
        import requests
        from core.websocket_manager import manager
        import asyncio
        
        api_key = os.getenv("APISPORTS_KEY")
        if not api_key:
            print("⚠️ APISPORTS_KEY not configured, skipping injury polling")
            return
        
        base_url = "https://v1.basketball.api-sports.io"
        
        # Poll NBA injuries
        response = requests.get(
            f"{base_url}/injuries",
            headers={"x-rapidapi-key": api_key},
            params={"league": "12", "season": "2024-2025"},  # NBA league ID
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            injuries = data.get("response", [])
            
            # Check for new injuries (compare with DB cache)
            new_injuries = []
            for injury in injuries:
                player_name = injury.get("player", {}).get("name")
                team = injury.get("team", {}).get("name")
                injury_type = injury.get("type")
                
                # Check if this is a new injury
                existing = db["injury_cache"].find_one({
                    "player_name": player_name,
                    "team": team
                })
                
                if not existing:
                    new_injuries.append({
                        "player_name": player_name,
                        "team": team,
                        "injury_type": injury_type,
                        "status": injury.get("status"),
                        "detected_at": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Cache injury
                    db["injury_cache"].insert_one({
                        "player_name": player_name,
                        "team": team,
                        "injury_type": injury_type,
                        "cached_at": datetime.now(timezone.utc).isoformat()
                    })
            
            # Broadcast new injuries via WebSocket
            if new_injuries:
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(manager.broadcast_to_channel("events", {
                        "type": "INJURY_UPDATE",
                        "payload": {
                            "count": len(new_injuries),
                            "injuries": new_injuries
                        }
                    }))
                except RuntimeError:
                    # No event loop running, create new one
                    asyncio.run(manager.broadcast_to_channel("events", {
                        "type": "INJURY_UPDATE",
                        "payload": {
                            "count": len(new_injuries),
                            "injuries": new_injuries
                        }
                    }))
                
                print(f"🏥 Detected {len(new_injuries)} new injuries, broadcasted via WebSocket")
            
            log_stage(
                "injury_polling",
                "success",
                input_payload={"source": "api-sports"},
                output_payload={"total_injuries": len(injuries), "new_injuries": len(new_injuries)}
            )
        else:
            print(f"✗ Injury API error: {response.status_code}")
            
    except Exception as e:
        log_stage(
            "injury_polling",
            "exception",
            input_payload={},
            output_payload={"error": str(e)},
            level="ERROR"
        )
        print(f"✗ Exception polling injuries: {e}")


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
    
    # Job 3: Poll MLB odds every 60 seconds (NEW - PHASE 7)
    scheduler.add_job(
        func=lambda: poll_odds_api("baseball_mlb", "h2h,spreads,totals"),
        trigger=IntervalTrigger(seconds=60),
        id="poll_mlb_odds",
        name="Poll MLB Odds (60s)",
        replace_existing=True
    )
    
    # Job 4: Poll NHL odds every 60 seconds (NEW - PHASE 7)
    scheduler.add_job(
        func=lambda: poll_odds_api("icehockey_nhl", "h2h,spreads,totals"),
        trigger=IntervalTrigger(seconds=60),
        id="poll_nhl_odds",
        name="Poll NHL Odds (60s)",
        replace_existing=True
    )
    
    # Job 5: Poll injury updates every 5 minutes
    scheduler.add_job(
        func=poll_injury_updates,
        trigger=IntervalTrigger(minutes=5),
        id="poll_injuries",
        name="Poll Injury Updates (5m)",
        replace_existing=True
    )
    
    # Job 6: Run daily Brier Score calculation at 4 AM
    scheduler.add_job(
        func=run_daily_brier_calculation,
        trigger="cron",
        hour=4,
        minute=0,
        id="daily_brier",
        name="Daily Brier Score Calculation (4 AM)",
        replace_existing=True
    )
    
    # Job 6: Run reflection loop weekly (Sundays at 2 AM)
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
    print("  - Injury updates (5m)")
    print("  - Daily Brier Score calculation (4 AM)")
    print("  - Weekly reflection loop (Sundays 2 AM)")


def stop_scheduler():
    """Stop background scheduler"""
    scheduler.shutdown()
    print("✓ Scheduler stopped")

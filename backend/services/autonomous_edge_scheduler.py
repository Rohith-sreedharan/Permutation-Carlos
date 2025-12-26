"""
Autonomous Edge Scheduler
Orchestrates three-wave simulation system automatically
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pymongo.database import Database
import logging

from backend.services.autonomous_edge_engine import AutonomousEdgeEngine
from backend.services.telegram_bot_service import TelegramBotService


logger = logging.getLogger(__name__)


class AutonomousEdgeScheduler:
    """
    Background scheduler for autonomous edge execution
    
    Automatically triggers:
    - Wave 1 scans (T-6h to T-4h)
    - Wave 2 scans (T-120 min)
    - Wave 3 scans (T-75 to T-60 min)
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.engine = AutonomousEdgeEngine(db)
        self.telegram_service = TelegramBotService(db)
        self.running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start the autonomous scheduler"""
        if self.running:
            logger.warning("Autonomous scheduler already running")
            return
        
        self.running = True
        logger.info("🚀 Autonomous Edge Scheduler started")
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._wave1_loop()))
        self._tasks.append(asyncio.create_task(self._wave2_loop()))
        self._tasks.append(asyncio.create_task(self._wave3_loop()))
    
    async def stop(self):
        """Stop the autonomous scheduler"""
        self.running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("🛑 Autonomous Edge Scheduler stopped")
    
    # ========================================================================
    # WAVE 1: PRIMARY SCAN LOOP
    # ========================================================================
    
    async def _wave1_loop(self):
        """
        Background loop for Wave 1 scans
        Runs every 30 minutes to catch T-6h to T-4h window
        """
        while self.running:
            try:
                await self._execute_wave1_scans()
            except Exception as e:
                logger.error(f"Wave 1 loop error: {e}", exc_info=True)
            
            # Wait 30 minutes before next scan
            await asyncio.sleep(1800)
    
    async def _execute_wave1_scans(self):
        """Execute Wave 1 scans for all eligible games"""
        now = datetime.now(timezone.utc)
        
        # Find games in T-6h to T-4h window
        wave1_start = now + timedelta(hours=4)
        wave1_end = now + timedelta(hours=6)
        
        # Get upcoming games from database
        games = list(self.db["games"].find({
            "commence_time": {
                "$gte": wave1_start.isoformat(),
                "$lte": wave1_end.isoformat()
            },
            "status": "scheduled"
        }).limit(100))
        
        logger.info(f"Wave 1: Found {len(games)} games in scan window")
        
        for game in games:
            try:
                # Check if already scanned
                existing = self.db["edge_candidates"].find_one({
                    "game_id": game["game_id"],
                    "wave": {"$gte": 1}
                })
                
                if existing:
                    continue  # Already scanned
                
                # Run simulation (mock - replace with real simulation service)
                simulation_output = await self._run_simulation(game)
                
                # Get market data
                market_data = await self._get_market_data(game["game_id"])
                
                if not market_data:
                    continue
                
                # Execute Wave 1 scan
                candidate_id = await self.engine.wave_1_primary_scan(
                    game_id=game["game_id"],
                    sport=game["sport"],
                    simulation_output=simulation_output,
                    market_data=market_data
                )
                
                if candidate_id:
                    logger.info(f"✅ Wave 1: Created candidate {candidate_id} for {game['game_id']}")
            
            except Exception as e:
                logger.error(f"Wave 1 scan error for {game.get('game_id')}: {e}")
    
    # ========================================================================
    # WAVE 2: STABILITY SCAN LOOP
    # ========================================================================
    
    async def _wave2_loop(self):
        """
        Background loop for Wave 2 scans
        Runs every 15 minutes to catch T-120 min window
        """
        while self.running:
            try:
                await self._execute_wave2_scans()
            except Exception as e:
                logger.error(f"Wave 2 loop error: {e}", exc_info=True)
            
            # Wait 15 minutes before next scan
            await asyncio.sleep(900)
    
    async def _execute_wave2_scans(self):
        """Execute Wave 2 scans for all Wave 1 candidates"""
        now = datetime.now(timezone.utc)
        
        # Find candidates ready for Wave 2 (T-120 min)
        wave2_target = now + timedelta(minutes=120)
        
        # Get games in Wave 2 window
        games = list(self.db["games"].find({
            "commence_time": {
                "$gte": (wave2_target - timedelta(minutes=10)).isoformat(),
                "$lte": (wave2_target + timedelta(minutes=10)).isoformat()
            },
            "status": "scheduled"
        }).limit(100))
        
        logger.info(f"Wave 2: Found {len(games)} games in validation window")
        
        for game in games:
            try:
                # Find Wave 1 candidate
                candidate = self.db["edge_candidates"].find_one({
                    "game_id": game["game_id"],
                    "wave": 1,
                    "state": "CANDIDATE_EDGE"
                })
                
                if not candidate:
                    continue
                
                # Re-run simulation
                simulation_output = await self._run_simulation(game)
                
                # Get updated market data
                market_data = await self._get_market_data(game["game_id"])
                
                if not market_data:
                    continue
                
                # Execute Wave 2 scan
                state = await self.engine.wave_2_stability_scan(
                    candidate_id=candidate["candidate_id"],
                    new_simulation_output=simulation_output,
                    market_data=market_data
                )
                
                logger.info(f"✅ Wave 2: Validated {candidate['candidate_id']} → {state}")
            
            except Exception as e:
                logger.error(f"Wave 2 scan error for {game.get('game_id')}: {e}")
    
    # ========================================================================
    # WAVE 3: FINAL LOCK SCAN LOOP
    # ========================================================================
    
    async def _wave3_loop(self):
        """
        Background loop for Wave 3 scans
        Runs every 5 minutes to catch T-75 to T-60 min window
        """
        while self.running:
            try:
                await self._execute_wave3_scans()
            except Exception as e:
                logger.error(f"Wave 3 loop error: {e}", exc_info=True)
            
            # Wait 5 minutes before next scan
            await asyncio.sleep(300)
    
    async def _execute_wave3_scans(self):
        """Execute Wave 3 scans for all Wave 2 confirmed candidates"""
        now = datetime.now(timezone.utc)
        
        # Find candidates ready for Wave 3 (T-75 to T-60 min)
        wave3_start = now + timedelta(minutes=60)
        wave3_end = now + timedelta(minutes=75)
        
        # Get games in Wave 3 window
        games = list(self.db["games"].find({
            "commence_time": {
                "$gte": wave3_start.isoformat(),
                "$lte": wave3_end.isoformat()
            },
            "status": "scheduled"
        }).limit(100))
        
        logger.info(f"Wave 3: Found {len(games)} games in publish window")
        
        for game in games:
            try:
                # Find Wave 2 confirmed candidate
                candidate = self.db["edge_candidates"].find_one({
                    "game_id": game["game_id"],
                    "wave": 2,
                    "state": {"$in": ["EDGE_CONFIRMED", "LEAN_CONFIRMED"]}
                })
                
                if not candidate:
                    continue
                
                # Final simulation run
                simulation_output = await self._run_simulation(game)
                
                # Get LIVE market data (critical - must be real-time)
                market_data = await self._get_live_market_data(game["game_id"])
                
                if not market_data:
                    logger.warning(f"No live market data for {game['game_id']}")
                    continue
                
                # Execute Wave 3 scan (THIS CAN PUBLISH)
                entry_snapshot = await self.engine.wave_3_final_lock_scan(
                    candidate_id=candidate["candidate_id"],
                    final_simulation_output=simulation_output,
                    live_market_data=market_data,
                    telegram_service=self.telegram_service
                )
                
                if entry_snapshot:
                    logger.info(f"🟢 Wave 3: PUBLISHED {candidate['candidate_id']} to Telegram")
                else:
                    logger.info(f"🔴 Wave 3: SILENCED {candidate['candidate_id']} (correct outcome)")
            
            except Exception as e:
                logger.error(f"Wave 3 scan error for {game.get('game_id')}: {e}")
    
    # ========================================================================
    # HELPER METHODS (MOCK - REPLACE WITH REAL SERVICES)
    # ========================================================================
    
    async def _run_simulation(self, game: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run 100K Monte Carlo simulation
        
        TODO: Replace with real simulation service
        """
        # Mock simulation output
        return {
            "model_spread": -12.5,
            "win_probability": 0.62,
            "volatility_bucket": "MEDIUM",
            "volatility_score": 0.45,
            "distribution_width": 8.5,
            "injury_impact": 0.02,
            "clv_estimate": 0.0025,
            "num_sims": 100000,
            "model_version": "v3.1"
        }
    
    async def _get_market_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get market data from odds API
        
        TODO: Replace with real odds service
        """
        # Mock market data
        game = self.db["games"].find_one({"game_id": game_id})
        
        if not game:
            return None
        
        return {
            "spread_line": -11.0,
            "spread_odds": -110,
            "commence_time": game["commence_time"]
        }
    
    async def _get_live_market_data(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Get LIVE market data (must be real-time)
        
        TODO: Replace with real-time odds API call
        """
        return await self._get_market_data(game_id)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_scheduler_instance = None


async def get_autonomous_scheduler(db: Database) -> AutonomousEdgeScheduler:
    """Get singleton scheduler instance"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        _scheduler_instance = AutonomousEdgeScheduler(db)
    
    return _scheduler_instance


async def start_autonomous_scheduler(db: Database):
    """Start the autonomous scheduler"""
    scheduler = await get_autonomous_scheduler(db)
    await scheduler.start()


async def stop_autonomous_scheduler():
    """Stop the autonomous scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance:
        await _scheduler_instance.stop()
        _scheduler_instance = None

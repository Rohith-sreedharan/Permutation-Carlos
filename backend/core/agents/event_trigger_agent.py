"""
Event Trigger Agent
Monitors live games for real-time alerts
"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class EventTriggerAgent:
    """
    Event Trigger Agent
    - Monitors live games for score changes
    - Triggers alerts for key moments
    - Detects garbage time, momentum shifts
    - Sends real-time notifications
    """
    
    def __init__(self, event_bus, db_client):
        self.bus = event_bus
        self.db = db_client
        self.active_games = {}
        
    async def start(self):
        """Start agent and begin monitoring"""
        logger.info("⚡ Event Trigger Agent started")
        
        # Start background monitoring
        asyncio.create_task(self._monitor_live_games())
        
    async def _monitor_live_games(self):
        """Background task to check live game scores"""
        while True:
            try:
                await self._check_live_games()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Live game monitoring error: {e}")
                await asyncio.sleep(30)
                
    async def _check_live_games(self):
        """Check all live games for triggers"""
        try:
            db = self.db["beatvegas_db"]
            
            # Get all live events
            live_events = list(db.events.find({
                "status": "live",
                "completed": False
            }))
            
            for event in live_events:
                await self._check_event_triggers(event)
                
        except Exception as e:
            logger.error(f"Error checking live games: {e}")
            
    async def _check_event_triggers(self, event: Dict[str, Any]):
        """Check single event for trigger conditions"""
        event_id = str(event.get("_id"))
        home_score = event.get("home_score", 0)
        away_score = event.get("away_score", 0)
        time_remaining = event.get("time_remaining", "")
        
        # Get previous state
        previous = self.active_games.get(event_id, {})
        prev_home = previous.get("home_score", 0)
        prev_away = previous.get("away_score", 0)
        
        # Detect score changes
        if home_score != prev_home or away_score != prev_away:
            await self._handle_score_change(event, prev_home, prev_away)
            
        # Check for garbage time
        if await self._is_garbage_time(event):
            await self._trigger_garbage_time_alert(event)
            
        # Update cache
        self.active_games[event_id] = {
            "home_score": home_score,
            "away_score": away_score,
            "last_check": datetime.utcnow()
        }
        
    async def _handle_score_change(self, event: Dict[str, Any], prev_home: int, prev_away: int):
        """Handle score change trigger"""
        event_id = str(event.get("_id"))
        
        alert = {
            "type": "score_change",
            "event_id": event_id,
            "event_name": f"{event.get('home_team')} vs {event.get('away_team')}",
            "home_score": event.get("home_score"),
            "away_score": event.get("away_score"),
            "previous_home": prev_home,
            "previous_away": prev_away,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("ui.updates", alert)
        
    async def _is_garbage_time(self, event: Dict[str, Any]) -> bool:
        """Detect if game is in garbage time"""
        home_score = event.get("home_score", 0)
        away_score = event.get("away_score", 0)
        margin = abs(home_score - away_score)
        
        # Simple heuristic: 20+ point lead in 4th quarter
        time_remaining = event.get("time_remaining", "")
        if "4th" in time_remaining or "Q4" in time_remaining:
            return margin >= 20
            
        return False
        
    async def _trigger_garbage_time_alert(self, event: Dict[str, Any]):
        """Send garbage time alert"""
        await self.bus.publish("ui.updates", {
            "type": "garbage_time",
            "event_id": str(event.get("_id")),
            "message": "⚠️ Garbage time detected - bet may be affected",
            "timestamp": datetime.utcnow().isoformat()
        })

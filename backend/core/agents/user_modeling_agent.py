"""
User Modeling Agent
Tracks user behavior and builds personalization profiles
"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class UserModelingAgent:
    """
    User Modeling Agent
    - Tracks user betting patterns and preferences
    - Builds behavioral profiles
    - Personalizes recommendations
    - Feeds data to feedback loop for model improvement
    """
    
    def __init__(self, event_bus, db_client):
        self.bus = event_bus
        self.db = db_client
        self.user_models = {}
        
    async def start(self):
        """Start agent and subscribe to topics"""
        await self.bus.subscribe("user.activity", self.handle_user_activity)
        await self.bus.subscribe("feedback.outcomes", self.handle_outcome)
        logger.info("👤 User Modeling Agent started")
        
    async def handle_user_activity(self, message: Dict[str, Any]):
        """Track all user activity"""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            activity_type = data.get("activity_type")
            
            if activity_type == "pick_made":
                await self._track_pick(user_id, data)
            elif activity_type == "page_view":
                await self._track_engagement(user_id, data)
            elif activity_type == "feature_used":
                await self._track_feature_usage(user_id, data)
                
        except Exception as e:
            logger.error(f"Error handling user activity: {e}")
            
    async def handle_outcome(self, message: Dict[str, Any]):
        """Update user model based on pick outcomes"""
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            pick_id = data.get("pick_id")
            outcome = data.get("outcome")  # "win" or "loss"
            
            await self._update_user_performance(user_id, pick_id, outcome)
            
        except Exception as e:
            logger.error(f"Error handling outcome: {e}")
            
    async def _track_pick(self, user_id: str, data: Dict[str, Any]):
        """Track user pick and update behavioral model"""
        try:
            db = self.db["beatvegas_db"]
            
            pick_record = {
                "user_id": user_id,
                "event_id": data.get("event_id"),
                "bet_type": data.get("bet_type"),
                "team": data.get("team"),
                "odds": data.get("odds"),
                "amount": data.get("amount"),
                "timestamp": datetime.utcnow(),
                "sport": data.get("sport"),
                "league": data.get("league")
            }
            
            result = db.user_behavior.insert_one(pick_record)
            
            # Update user preferences
            await self._update_preferences(user_id, data)
            
        except Exception as e:
            logger.error(f"Error tracking pick: {e}")
            
    async def _update_preferences(self, user_id: str, pick_data: Dict[str, Any]):
        """Update user's sport/bet type preferences"""
        try:
            db = self.db["beatvegas_db"]
            
            sport = pick_data.get("sport")
            bet_type = pick_data.get("bet_type")
            
            # Increment counters
            db.subscribers.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        f"preferences.sports.{sport}": 1,
                        f"preferences.bet_types.{bet_type}": 1,
                        "preferences.total_picks": 1
                    }
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            
    async def _track_engagement(self, user_id: str, data: Dict[str, Any]):
        """Track page views and engagement"""
        pass  # Implement if needed
        
    async def _track_feature_usage(self, user_id: str, data: Dict[str, Any]):
        """Track which features user engages with"""
        pass  # Implement if needed
        
    async def _update_user_performance(self, user_id: str, pick_id: str, outcome: str):
        """Update user's performance metrics after pick settles"""
        try:
            db = self.db["beatvegas_db"]
            
            # Update streak
            if outcome == "win":
                db.subscribers.update_one(
                    {"_id": user_id},
                    {
                        "$inc": {"score": 10, "streaks": 1},
                        "$set": {"recent_loss_streak": 0}
                    }
                )
            else:
                db.subscribers.update_one(
                    {"_id": user_id},
                    {
                        "$inc": {"recent_loss_streak": 1},
                        "$set": {"streaks": 0}
                    }
                )
                
            # Update pick record
            db.ai_picks.update_one(
                {"_id": pick_id},
                {"$set": {"outcome": outcome, "settled_at": datetime.utcnow()}}
            )
            
        except Exception as e:
            logger.error(f"Error updating user performance: {e}")
            
    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user behavioral profile"""
        try:
            db = self.db["beatvegas_db"]
            
            user = db.subscribers.find_one({"_id": user_id})
            if not user:
                return {}
                
            # Get betting history
            picks = list(db.user_behavior.find({"user_id": user_id}).sort("timestamp", -1).limit(100))
            
            # Calculate stats
            total_picks = len(picks)
            sports_breakdown = {}
            bet_type_breakdown = {}
            avg_odds = 0
            
            for pick in picks:
                sport = pick.get("sport", "unknown")
                bet_type = pick.get("bet_type", "unknown")
                sports_breakdown[sport] = sports_breakdown.get(sport, 0) + 1
                bet_type_breakdown[bet_type] = bet_type_breakdown.get(bet_type, 0) + 1
                avg_odds += pick.get("odds", -110)
                
            if total_picks > 0:
                avg_odds /= total_picks
                
            return {
                "user_id": user_id,
                "total_picks": total_picks,
                "favorite_sport": max(sports_breakdown.items(), key=lambda x: x[1])[0] if sports_breakdown else None,
                "favorite_bet_type": max(bet_type_breakdown.items(), key=lambda x: x[1])[0] if bet_type_breakdown else None,
                "sports_breakdown": sports_breakdown,
                "bet_type_breakdown": bet_type_breakdown,
                "avg_odds": round(avg_odds, 0),
                "score": user.get("score", 0),
                "streaks": user.get("streaks", 0)
            }
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {}

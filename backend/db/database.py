"""
MongoDB Database Connection

Uses existing MongoDB connection from db.mongo
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from db.mongo import db


class Database:
    """MongoDB database manager - wraps existing db.mongo connection"""
    
    def __init__(self):
        self.db = db
        
    @property
    def users(self):
        return self.db.users
    
    @property
    def games(self):
        return self.db.games
    
    @property
    def simulations(self):
        return self.db.simulations
    
    @property
    def signals(self):
        return self.db.signals
    
    @property
    def subscriptions(self):
        return self.db.subscriptions
    
    @property
    def sharp_pass_applications(self):
        return self.db.sharp_pass_applications
    
    @property
    def bet_history(self):
        return self.db.bet_history
    
    @property
    def community_channels(self):
        return self.db.community_channels
    
    @property
    def community_posts(self):
        return self.db.community_posts
    
    # Helper query methods for monitoring
    async def get_calibration_weekly(self, start_date: datetime) -> List[Dict]:
        """Get calibration data for last week"""
        return list(self.signals.find({
            "created_at": {"$gte": start_date},
            "status": "GRADED"
        }).sort("created_at", -1))
    
    async def get_graded_signals(self, start_date: datetime, edge_state: Optional[str] = None) -> List[Dict]:
        """Get graded signals"""
        query = {"created_at": {"$gte": start_date}, "status": "GRADED"}
        if edge_state:
            query["edge_state"] = edge_state
        return list(self.signals.find(query).sort("created_at", -1))
    
    async def get_recent_simulations(self, hours: Optional[int] = None, limit: Optional[int] = None) -> List[Dict]:
        """Get recent simulations"""
        query = {}
        if hours:
            query["created_at"] = {"$gte": datetime.now() - timedelta(hours=hours)}
        
        cursor = self.simulations.find(query).sort("created_at", -1)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)
    
    async def get_api_requests(self, minutes: int) -> List[Dict]:
        """Get recent API requests"""
        start_time = datetime.now() - timedelta(minutes=minutes)
        return list(self.db.api_logs.find({"timestamp": {"$gte": start_time}}))
    
    async def get_telegram_posts(self, hours: int) -> List[Dict]:
        """Get recent Telegram posts"""
        start_time = datetime.now() - timedelta(hours=hours)
        return list(self.db.telegram_posts.find({"sent_at": {"$gte": start_time}}))
    
    async def ping(self):
        """Ping database"""
        result = self.db.command("ping")
        if result.get("ok") != 1:
            raise Exception("Database ping failed")
    
    async def count_sharp_pass_applications(self, status: str) -> int:
        """Count Sharp Pass applications by status"""
        return self.sharp_pass_applications.count_documents({"status": status})
    
    async def get_simsports_api_requests(self, minutes: int) -> List[Dict]:
        """Get recent SimSports API requests"""
        start_time = datetime.now() - timedelta(minutes=minutes)
        return list(self.db.api_logs.find({
            "timestamp": {"$gte": start_time},
            "endpoint": {"$regex": "^/api/simsports"}
        }))


# Dependency for FastAPI
def get_database() -> Database:
    """Get database instance"""
    return Database()

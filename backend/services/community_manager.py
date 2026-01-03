"""
Community Manager

Manages War Room game threads and posts using MongoDB.
"""
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId

from ..db.database import Database


class CommunityManager:
    """Manage community War Room"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def create_game_channel(
        self,
        game_id: str,
        sport: str,
        home_team: str,
        away_team: str,
        game_time: datetime
    ) -> Dict:
        """Create new game channel"""
        slug = f"{sport}-{game_id}".lower()
        
        doc = {
            "slug": slug,
            "game_id": game_id,
            "sport": sport,
            "home_team": home_team,
            "away_team": away_team,
            "game_time": game_time,
            "created_at": datetime.now(),
            "expires_at": game_time + timedelta(hours=6)
        }
        
        self.db.community_channels.insert_one(doc)
        
        return {
            "slug": slug,
            "game_id": game_id,
            "sport": sport,
            "teams": f"{away_team} @ {home_team}"
        }
        
    async def create_post(
        self,
        slug: str,
        user_id: str,
        content: str,
        market_type: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> Dict:
        """Create community post"""
        doc = {
            "channel_slug": slug,
            "user_id": user_id,
            "content": content,
            "market_type": market_type,
            "parent_id": parent_id,
            "created_at": datetime.now()
        }
        
        result = self.db.community_posts.insert_one(doc)
        
        return {
            "id": str(result.inserted_id),
            "slug": slug,
            "content": content,
            "created_at": doc["created_at"]
        }
        
    async def get_channel_posts(
        self,
        slug: str,
        market_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get posts for a channel"""
        query = {"channel_slug": slug}
        
        if market_type:
            query["market_type"] = market_type
        
        posts = list(
            self.db.community_posts
            .find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        
        # Enrich with usernames
        for post in posts:
            user = self.db.users.find_one({"_id": ObjectId(post["user_id"])})
            post["username"] = user.get("username") if user else "Unknown"
        
        return posts
    
    async def get_channel_by_slug(self, slug: str) -> Optional[Dict]:
        """Get channel by slug"""
        return self.db.community_channels.find_one({"slug": slug})
    
    async def user_has_access(self, user_id: str, channel_id: str) -> bool:
        """Check if user has access to channel"""
        # For now, all authenticated users have access
        return True
    
    async def get_sub_threads(self, channel_id: str) -> List[Dict]:
        """Get market-specific sub-threads for a channel"""
        channel = self.db.community_channels.find_one({"_id": ObjectId(channel_id)})
        if not channel:
            return []
        
        pipeline = [
            {"$match": {"channel_slug": channel["slug"]}},
            {"$group": {
                "_id": "$market_type",
                "post_count": {"$sum": 1}
            }}
        ]
        
        return list(self.db.community_posts.aggregate(pipeline))
    
    async def react_to_post(self, post_id: str, user_id: str, reaction: str):
        """Add reaction to a post"""
        self.db.community_posts.update_one(
            {"_id": ObjectId(post_id)},
            {"$push": {"reactions": {
                "user_id": user_id,
                "reaction": reaction,
                "created_at": datetime.now()
            }}}
        )
    
    async def create_channel(self, game_id: str, sport: str, home_team: str, away_team: str, game_time: datetime) -> Dict:
        """Alias for create_game_channel"""
        return await self.create_game_channel(game_id, sport, home_team, away_team, game_time)
    
    async def get_channels(self, sport: Optional[str] = None, active_only: bool = True) -> List[Dict]:
        """Get channels with optional filtering"""
        query = {}
        
        if sport:
            query["sport"] = sport
        
        if active_only:
            query["expires_at"] = {"$gt": datetime.now()}
        
        return list(
            self.db.community_channels
            .find(query)
            .sort("game_time", 1)
        )

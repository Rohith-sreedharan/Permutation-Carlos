"""
User Identity & Badge System
Tracks user ranks, badges, streaks, XP, and achievements for community engagement
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
from db.mongo import db
from utils.timezone import now_utc


class UserRank(str, Enum):
    """User rank tiers based on performance and activity"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"
    LEGEND = "legend"


class BadgeType(str, Enum):
    """Available badge types"""
    # Performance badges
    VERIFIED_CAPPER = "verified_capper"  # 60%+ win rate over 50+ picks
    SHARP_BETTOR = "sharp_bettor"  # Positive CLV on 80%+ of picks
    STREAK_MASTER = "streak_master"  # 10+ winning streak
    PARLAY_KING = "parlay_king"  # 5+ parlay wins
    UNDERDOG_SPECIALIST = "underdog_specialist"  # 70%+ on underdogs
    FAVORITE_HUNTER = "favorite_hunter"  # 70%+ on favorites
    
    # Activity badges
    EARLY_ADOPTER = "early_adopter"  # First 1000 users
    DAILY_GRINDER = "daily_grinder"  # 30 day login streak
    COMMUNITY_LEADER = "community_leader"  # 100+ helpful messages
    
    # Achievement badges
    PERFECT_WEEK = "perfect_week"  # 7/7 week
    BIG_WIN = "big_win"  # Single bet profit > $1000
    MONTE_CARLO_MASTER = "monte_carlo_master"  # Followed 20+ AI picks with profit
    
    # Season badges
    NBA_EXPERT = "nba_expert"  # 65%+ NBA win rate
    NFL_EXPERT = "nfl_expert"  # 65%+ NFL win rate
    NCAAB_EXPERT = "ncaab_expert"  # 65%+ NCAAB win rate


class UserIdentityService:
    """Manages user ranks, badges, XP, and achievements"""
    
    # XP thresholds for rank advancement
    RANK_XP_THRESHOLDS = {
        UserRank.BRONZE: 0,
        UserRank.SILVER: 1000,
        UserRank.GOLD: 5000,
        UserRank.PLATINUM: 15000,
        UserRank.DIAMOND: 50000,
        UserRank.LEGEND: 150000
    }
    
    # XP rewards for actions
    XP_REWARDS = {
        "pick_win": 100,
        "pick_loss": 10,  # Small XP for participation
        "parlay_win": 250,
        "message_posted": 5,
        "helpful_message": 25,  # Upvoted/liked message
        "daily_login": 10,
        "streak_bonus": 50,  # Per day in streak
        "challenge_complete": 200,
        "referral": 500
    }
    
    def __init__(self):
        pass
    
    def get_user_identity(self, user_id: str) -> Dict[str, Any]:
        """Get user's complete identity profile"""
        profile = db["user_identity"].find_one({"user_id": user_id})
        
        if not profile:
            # Create new profile
            profile = self._create_default_profile(user_id)
            db["user_identity"].insert_one(profile)
        
        return profile
    
    def _create_default_profile(self, user_id: str) -> Dict[str, Any]:
        """Create default user identity profile"""
        return {
            "user_id": user_id,
            "rank": UserRank.BRONZE.value,
            "xp": 0,
            "badges": [],
            "achievements": [],
            "current_streak": 0,
            "longest_streak": 0,
            "total_picks": 0,
            "winning_picks": 0,
            "total_parlays": 0,
            "winning_parlays": 0,
            "total_profit": 0.0,
            "community_messages": 0,
            "helpful_messages": 0,
            "last_active": now_utc().isoformat(),
            "member_since": now_utc().isoformat(),
            "daily_login_streak": 0,
            "last_login_date": now_utc().strftime("%Y-%m-%d"),
            "sport_stats": {
                "NBA": {"picks": 0, "wins": 0, "roi": 0.0},
                "NFL": {"picks": 0, "wins": 0, "roi": 0.0},
                "NCAAB": {"picks": 0, "wins": 0, "roi": 0.0},
                "NCAAF": {"picks": 0, "wins": 0, "roi": 0.0},
                "NHL": {"picks": 0, "wins": 0, "roi": 0.0},
                "MLB": {"picks": 0, "wins": 0, "roi": 0.0}
            }
        }
    
    def calculate_rank(self, xp: int) -> str:
        """Calculate rank based on XP"""
        for rank in reversed(list(UserRank)):
            if xp >= self.RANK_XP_THRESHOLDS[rank]:
                return rank.value
        return UserRank.BRONZE.value
    
    def award_xp(self, user_id: str, action: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Award XP for an action and update rank if needed"""
        xp_amount = amount or self.XP_REWARDS.get(action, 0)
        
        profile = self.get_user_identity(user_id)
        old_xp = profile["xp"]
        old_rank = profile["rank"]
        
        new_xp = old_xp + xp_amount
        new_rank = self.calculate_rank(new_xp)
        
        # Update profile
        update = {
            "xp": new_xp,
            "rank": new_rank,
            "last_active": now_utc().isoformat()
        }
        
        db["user_identity"].update_one(
            {"user_id": user_id},
            {"$set": update}
        )
        
        # Check if rank changed
        rank_up = old_rank != new_rank
        
        return {
            "xp_awarded": xp_amount,
            "new_xp": new_xp,
            "old_rank": old_rank,
            "new_rank": new_rank,
            "rank_up": rank_up
        }
    
    def award_badge(self, user_id: str, badge: BadgeType) -> bool:
        """Award badge to user if not already earned"""
        profile = self.get_user_identity(user_id)
        
        if badge.value in profile.get("badges", []):
            return False  # Already has badge
        
        db["user_identity"].update_one(
            {"user_id": user_id},
            {
                "$addToSet": {"badges": badge.value},
                "$set": {"last_active": now_utc().isoformat()}
            }
        )
        
        # Award XP bonus for earning badge
        self.award_xp(user_id, "badge_earned", 500)
        
        return True
    
    def update_pick_stats(
        self,
        user_id: str,
        won: bool,
        profit: float,
        sport: str = "NBA",
        is_parlay: bool = False
    ) -> None:
        """Update user stats after pick is graded"""
        profile = self.get_user_identity(user_id)
        
        updates = {
            "last_active": now_utc().isoformat(),
            "total_picks": profile["total_picks"] + 1,
            "total_profit": profile["total_profit"] + profit
        }
        
        if won:
            updates["winning_picks"] = profile["winning_picks"] + 1
            updates["current_streak"] = profile["current_streak"] + 1
            
            # Update longest streak
            if updates["current_streak"] > profile["longest_streak"]:
                updates["longest_streak"] = updates["current_streak"]
            
            # Award XP
            if is_parlay:
                updates["total_parlays"] = profile.get("total_parlays", 0) + 1
                updates["winning_parlays"] = profile.get("winning_parlays", 0) + 1
                self.award_xp(user_id, "parlay_win")
            else:
                self.award_xp(user_id, "pick_win")
            
            # Streak bonus XP
            if updates["current_streak"] >= 5:
                self.award_xp(user_id, "streak_bonus", updates["current_streak"] * 10)
        
        else:
            updates["current_streak"] = 0  # Reset streak
            self.award_xp(user_id, "pick_loss")
            
            if is_parlay:
                updates["total_parlays"] = profile.get("total_parlays", 0) + 1
        
        # Update sport-specific stats
        sport_key = f"sport_stats.{sport}"
        sport_stats = profile.get("sport_stats", {}).get(sport, {"picks": 0, "wins": 0, "roi": 0.0})
        new_picks = sport_stats["picks"] + 1
        new_wins = sport_stats["wins"] + (1 if won else 0)
        new_roi = (profile["total_profit"] / new_picks) * 100 if new_picks > 0 else 0.0
        
        updates[f"{sport_key}.picks"] = new_picks
        updates[f"{sport_key}.wins"] = new_wins
        updates[f"{sport_key}.roi"] = new_roi
        
        db["user_identity"].update_one(
            {"user_id": user_id},
            {"$set": updates}
        )
        
        # Check for badge eligibility
        self._check_badge_eligibility(user_id)
    
    def _check_badge_eligibility(self, user_id: str) -> None:
        """Check if user qualifies for any badges"""
        profile = self.get_user_identity(user_id)
        
        total_picks = profile["total_picks"]
        winning_picks = profile["winning_picks"]
        win_rate = (winning_picks / total_picks * 100) if total_picks > 0 else 0
        current_streak = profile["current_streak"]
        winning_parlays = profile.get("winning_parlays", 0)
        total_profit = profile["total_profit"]
        
        # Verified Capper: 60%+ win rate over 50+ picks
        if total_picks >= 50 and win_rate >= 60:
            self.award_badge(user_id, BadgeType.VERIFIED_CAPPER)
        
        # Streak Master: 10+ winning streak
        if current_streak >= 10:
            self.award_badge(user_id, BadgeType.STREAK_MASTER)
        
        # Parlay King: 5+ parlay wins
        if winning_parlays >= 5:
            self.award_badge(user_id, BadgeType.PARLAY_KING)
        
        # Big Win: Single bet profit > $1000 (tracked elsewhere, but check total)
        if total_profit >= 1000:
            self.award_badge(user_id, BadgeType.BIG_WIN)
        
        # Sport-specific expert badges
        for sport, badge in [
            ("NBA", BadgeType.NBA_EXPERT),
            ("NFL", BadgeType.NFL_EXPERT),
            ("NCAAB", BadgeType.NCAAB_EXPERT)
        ]:
            sport_stats = profile.get("sport_stats", {}).get(sport, {})
            sport_picks = sport_stats.get("picks", 0)
            sport_wins = sport_stats.get("wins", 0)
            sport_win_rate = (sport_wins / sport_picks * 100) if sport_picks > 0 else 0
            
            if sport_picks >= 30 and sport_win_rate >= 65:
                self.award_badge(user_id, badge)
    
    def update_daily_login(self, user_id: str) -> Dict[str, Any]:
        """Update daily login streak"""
        profile = self.get_user_identity(user_id)
        
        today = now_utc().strftime("%Y-%m-%d")
        last_login = profile.get("last_login_date", "")
        
        if last_login == today:
            return {"streak": profile.get("daily_login_streak", 0), "new_login": False}
        
        # Check if yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        if last_login == yesterday:
            # Continue streak
            new_streak = profile.get("daily_login_streak", 0) + 1
        else:
            # Reset streak
            new_streak = 1
        
        db["user_identity"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "daily_login_streak": new_streak,
                    "last_login_date": today,
                    "last_active": now_utc().isoformat()
                }
            }
        )
        
        # Award XP
        self.award_xp(user_id, "daily_login")
        
        # Bonus XP for long streaks
        if new_streak >= 7:
            self.award_xp(user_id, "streak_bonus", new_streak * 5)
        
        # Award badge for 30 day streak
        if new_streak >= 30:
            self.award_badge(user_id, BadgeType.DAILY_GRINDER)
        
        return {"streak": new_streak, "new_login": True}
    
    def get_leaderboard(self, limit: int = 100, metric: str = "xp") -> List[Dict[str, Any]]:
        """Get leaderboard sorted by metric"""
        sort_field = {
            "xp": "xp",
            "win_rate": "winning_picks",
            "profit": "total_profit",
            "streak": "longest_streak"
        }.get(metric, "xp")
        
        profiles = list(
            db["user_identity"]
            .find({})
            .sort(sort_field, -1)
            .limit(limit)
        )
        
        # Calculate win rate for each
        for profile in profiles:
            total = profile.get("total_picks", 0)
            wins = profile.get("winning_picks", 0)
            profile["win_rate"] = (wins / total * 100) if total > 0 else 0
        
        return profiles
    
    def get_badge_info(self, badge: BadgeType) -> Dict[str, Any]:
        """Get badge display info"""
        badge_info = {
            BadgeType.VERIFIED_CAPPER: {
                "name": "Verified Capper",
                "emoji": "✅",
                "description": "60%+ win rate over 50+ picks"
            },
            BadgeType.SHARP_BETTOR: {
                "name": "Sharp Bettor",
                "emoji": "💎",
                "description": "Positive CLV on 80%+ of picks"
            },
            BadgeType.STREAK_MASTER: {
                "name": "Streak Master",
                "emoji": "🔥",
                "description": "10+ winning streak achieved"
            },
            BadgeType.PARLAY_KING: {
                "name": "Parlay King",
                "emoji": "👑",
                "description": "5+ parlay wins"
            },
            BadgeType.EARLY_ADOPTER: {
                "name": "Early Adopter",
                "emoji": "🌟",
                "description": "First 1000 users"
            },
            BadgeType.DAILY_GRINDER: {
                "name": "Daily Grinder",
                "emoji": "💪",
                "description": "30 day login streak"
            },
            BadgeType.COMMUNITY_LEADER: {
                "name": "Community Leader",
                "emoji": "🎤",
                "description": "100+ helpful messages"
            },
            BadgeType.PERFECT_WEEK: {
                "name": "Perfect Week",
                "emoji": "🎯",
                "description": "7/7 winning week"
            },
            BadgeType.BIG_WIN: {
                "name": "Big Win",
                "emoji": "💰",
                "description": "Single bet profit > $1000"
            },
            BadgeType.NBA_EXPERT: {
                "name": "NBA Expert",
                "emoji": "🏀",
                "description": "65%+ NBA win rate"
            },
            BadgeType.NFL_EXPERT: {
                "name": "NFL Expert",
                "emoji": "🏈",
                "description": "65%+ NFL win rate"
            },
            BadgeType.NCAAB_EXPERT: {
                "name": "NCAAB Expert",
                "emoji": "🎓",
                "description": "65%+ NCAAB win rate"
            }
        }
        
        return badge_info.get(badge, {
            "name": badge.value,
            "emoji": "🏅",
            "description": "Achievement unlocked"
        })


# Global service instance
user_identity_service = UserIdentityService()

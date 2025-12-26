"""
War Room Service Layer
Core business logic: threading, TTL archiving, anti-spam, rate limiting, rank engine
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from db.mongo import db
from db.schemas.war_room_schemas import (
    RateLimitTracker, ModerationEvent, UserRank, 
    MarketCalloutPost, ReceiptPost, ParlayBuildPost
)
import uuid
from pymongo import UpdateOne
import logging

logger = logging.getLogger(__name__)


class WarRoomService:
    """Main War Room service"""
    
    # Anti-spam phrase blocking (hard-coded)
    BLOCKED_PHRASES = {
        "lock": ["lock", "locked", "locking"],
        "guaranteed": ["guarantee", "guaranteed", "guarantees"],
        "free_money": ["free money", "freeroll", "free roll"],
        "cant_lose": ["can't lose", "cannot lose", "dont lose"]
    }
    
    # Rate limits by tier
    RATE_LIMITS = {
        "free": {
            "max_posts_per_day": 5,
            "max_market_callouts_per_day": 0,  # Not allowed
            "allowed_channels": ["beginner", "general"],
            "can_post_market_callout": False
        },
        "paid": {
            "max_posts_per_day": 25,
            "max_market_callouts_per_day": 5,
            "allowed_channels": ["all"],
            "can_post_market_callout": True
        },
        "verified": {
            "max_posts_per_day": 50,
            "max_market_callouts_per_day": 10,
            "allowed_channels": ["all"],
            "can_post_market_callout": True,
            "can_create_threads": True
        },
        "elite": {
            "max_posts_per_day": 100,
            "max_market_callouts_per_day": 20,
            "allowed_channels": ["all"],
            "can_post_market_callout": True,
            "can_create_threads": True
        }
    }
    
    @staticmethod
    def validate_market_callout(callout: MarketCalloutPost) -> Tuple[bool, Optional[str]]:
        """
        Validate market callout for compliance
        Returns: (is_valid, error_message)
        """
        # Check for blocked phrases
        content_to_check = f"{callout.reason} {callout.line}".lower()
        
        for phrase_type, phrases in WarRoomService.BLOCKED_PHRASES.items():
            for phrase in phrases:
                if phrase in content_to_check:
                    return False, f"Cannot use '{phrase}' in callouts. Be specific about edge, not hype."
        
        # Validate line format
        if not WarRoomService._validate_line_format(callout.line):
            return False, "Invalid line format. Expected: 'Team +/-X.X' or 'Over/Under X.X'"
        
        # Confidence must be valid
        if callout.confidence not in ["low", "med", "high"]:
            return False, "Confidence must be low, med, or high"
        
        # Reason must be substantive
        if len(callout.reason.strip()) < 10:
            return False, "Reason must be at least 10 characters"
        
        return True, None
    
    @staticmethod
    def _validate_line_format(line: str) -> bool:
        """Validate line format"""
        # Basic check: should contain +, -, or Over/Under
        valid_formats = ["+", "-", "over", "under", "o/u"]
        return any(fmt in line.lower() for fmt in valid_formats)
    
    @staticmethod
    async def check_rate_limit(
        user_id: str,
        user_tier: str,
        channel_id: str,
        post_type: str = "message"
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user can post
        Returns: (allowed, reason_if_blocked)
        """
        limits = WarRoomService.RATE_LIMITS.get(user_tier, WarRoomService.RATE_LIMITS["free"])
        
        # Get or create rate limit tracker
        tracker = db["war_room_rate_limits"].find_one({"user_id": user_id})
        
        if not tracker:
            tracker = {
                "user_id": user_id,
                "tier": user_tier,
                "posts_today": 0,
                "market_callouts_today": 0,
                "last_post_timestamp": None,
                "recent_market_callouts": [],
                "is_shadow_muted": False,
                "reset_at": datetime.now(timezone.utc) + timedelta(days=1)
            }
            db["war_room_rate_limits"].insert_one(tracker)
        
        # Check if muted
        if tracker.get("is_shadow_muted"):
            mute_expires = tracker.get("mute_expires_at")
            # Ensure mute_expires is timezone-aware for comparison
            if mute_expires:
                if isinstance(mute_expires, str):
                    mute_expires = datetime.fromisoformat(mute_expires.replace('Z', '+00:00'))
                elif mute_expires.tzinfo is None:
                    mute_expires = mute_expires.replace(tzinfo=timezone.utc)
            if mute_expires and datetime.now(timezone.utc) < mute_expires:
                return False, "You are temporarily muted"
            else:
                # Unmute
                db["war_room_rate_limits"].update_one(
                    {"user_id": user_id},
                    {"$set": {"is_shadow_muted": False, "mute_expires_at": None}}
                )
        
        # Reset if new day
        reset_at = tracker.get("reset_at")
        # Ensure reset_at is timezone-aware for comparison
        if reset_at:
            if isinstance(reset_at, str):
                reset_at = datetime.fromisoformat(reset_at.replace('Z', '+00:00'))
            elif reset_at.tzinfo is None:
                reset_at = reset_at.replace(tzinfo=timezone.utc)
        if reset_at and datetime.now(timezone.utc) > reset_at:
            tracker["posts_today"] = 0
            tracker["market_callouts_today"] = 0
            tracker["recent_market_callouts"] = []
            tracker["reset_at"] = datetime.now(timezone.utc) + timedelta(days=1)
        
        # Check daily post limit
        if tracker["posts_today"] >= limits["max_posts_per_day"]:
            return False, f"Daily post limit reached ({limits['max_posts_per_day']})"
        
        # Check market callout limit
        if post_type == "market_callout":
            if not limits.get("can_post_market_callout", False):
                return False, "Your tier cannot post market callouts. Upgrade to Paid tier"
            
            if tracker["market_callouts_today"] >= limits["max_market_callouts_per_day"]:
                return False, f"Daily market callout limit reached ({limits['max_market_callouts_per_day']})"
        
        # Check channel access
        if limits["allowed_channels"] != ["all"] and channel_id not in limits["allowed_channels"]:
            return False, f"Your tier cannot access {channel_id}"
        
        return True, None
    
    @staticmethod
    async def check_duplicate_market_callout(
        user_id: str,
        market_key: str,
        within_minutes: int = 30
    ) -> Tuple[bool, Optional[str]]:
        """Check if user posted same market recently"""
        tracker = db["war_room_rate_limits"].find_one({"user_id": user_id})
        
        if not tracker:
            return True, None  # No duplicate
        
        recent = tracker.get("recent_market_callouts", [])
        
        # Check if market in recent list
        if market_key in recent:
            return False, f"You posted this market in the last 30 minutes. Wait before reposting"
        
        return True, None
    
    @staticmethod
    async def record_post(
        user_id: str,
        user_tier: str,
        post_type: str
    ) -> None:
        """Update rate limits and recent history after successful post"""
        db["war_room_rate_limits"].update_one(
            {"user_id": user_id},
            {
                "$inc": {
                    "posts_today": 1,
                    "market_callouts_today": 1 if post_type == "market_callout" else 0
                },
                "$set": {"last_post_timestamp": datetime.now(timezone.utc)}
            },
            upsert=True
        )
    
    @staticmethod
    async def auto_archive_threads(
        game_room_id: str,
        ttl_hours: int = 6
    ) -> None:
        """Auto-archive threads after game end + TTL hours"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        
        game_room = db["war_room_game_rooms"].find_one({"room_id": game_room_id})
        
        if game_room and game_room.get("status") == "completed":
            game_end = game_room.get("game_end_time")
            
            # Ensure game_end datetime is timezone-aware for comparison
            if game_end:
                if isinstance(game_end, str):
                    game_end_dt = datetime.fromisoformat(game_end.replace('Z', '+00:00'))
                else:
                    game_end_dt = game_end if game_end.tzinfo else game_end.replace(tzinfo=timezone.utc)
                
                if game_end_dt < cutoff_time:
                    # Archive the room
                    db["war_room_game_rooms"].update_one(
                        {"room_id": game_room_id},
                        {
                            "$set": {
                                "status": "archived",
                                "archived_at": datetime.now(timezone.utc).isoformat()
                            }
                        }
                    )
                    
                    # Mark threads as read-only
                    db["war_room_market_threads"].update_many(
                        {"room_id": game_room_id},
                        {"$set": {"is_locked": True}}
                    )
                    
                    logger.info(f"Archived game room {game_room_id}")
    
    @staticmethod
    async def calculate_user_rank(user_id: str) -> Dict[str, Any]:
        """
        Calculate user rank based on:
        - Template compliance
        - Pick record (if receipts provided)
        - Community behavior
        - Flag/warning count
        """
        user_posts = list(db["war_room_posts"].find(
            {"user_id": user_id, "is_deleted": False}
        ))
        
        total_posts = len(user_posts)
        
        if total_posts == 0:
            return {
                "rank": "rookie",
                "rank_points": 0,
                "explanation": "No activity yet"
            }
        
        # Template compliance
        compliant_posts = sum(1 for p in user_posts if p.get("moderation_status") != "flagged")
        compliance_rate = compliant_posts / total_posts if total_posts > 0 else 0
        
        # Graded picks (receipts)
        receipt_posts = [p for p in user_posts if p.get("post_type") == "receipt"]
        graded_picks = len(receipt_posts)
        
        wins = sum(1 for p in receipt_posts if p.get("result") == "W")
        win_rate = (wins / graded_picks) if graded_picks > 0 else None
        
        # Behavior
        user_rank = db["war_room_user_ranks"].find_one({"user_id": user_id})
        warnings = user_rank.get("warning_count", 0) if user_rank else 0
        
        # Calculate rank
        rank = "rookie"
        rank_points = 0
        
        if total_posts >= 10 and compliance_rate >= 0.95 and warnings == 0:
            rank = "contributor"
            rank_points = 100
        
        if graded_picks >= 20 and win_rate is not None and win_rate >= 0.52 and compliance_rate >= 0.98:
            rank = "verified"
            rank_points = 300
        
        if rank == "verified" and graded_picks >= 50 and win_rate is not None and win_rate >= 0.55:
            rank = "elite"
            rank_points = 500
        
        return {
            "rank": rank,
            "rank_points": rank_points,
            "total_posts": total_posts,
            "template_compliance_rate": compliance_rate,
            "graded_picks": graded_picks,
            "win_rate": win_rate,
            "warnings": warnings
        }
    
    @staticmethod
    async def get_leaderboard(limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get risk-adjusted leaderboard
        Sorts by: volatility_adjusted_score (no likes/ego metrics)
        """
        entries = list(db["war_room_leaderboard"].find(
            {},
            {"_id": 0}
        ).sort("volatility_adjusted_score", -1).limit(limit))
        
        # Add position
        for i, entry in enumerate(entries):
            entry["leaderboard_position"] = i + 1
        
        return entries
    
    @staticmethod
    async def moderate_post(
        post_id: str,
        action: str,
        moderator_id: str,
        reason: Optional[str] = None,
        duration_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Moderation actions: delete, lock, mute, flag, warn
        Returns moderation event
        """
        post = db["war_room_posts"].find_one({"post_id": post_id})
        
        if not post:
            return {"error": "Post not found"}
        
        user_id = post.get("user_id")
        event_id = str(uuid.uuid4())
        
        if action == "delete":
            db["war_room_posts"].update_one(
                {"post_id": post_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "moderation_status": "deleted"
                    }
                }
            )
        
        elif action == "lock":
            db["war_room_market_threads"].update_one(
                {"thread_id": post.get("thread_id")},
                {"$set": {"is_locked": True}}
            )
        
        elif action == "mute":
            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours or 24)
            db["war_room_rate_limits"].update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "is_shadow_muted": True,
                        "mute_expires_at": expires_at.isoformat()
                    }
                },
                upsert=True
            )
        
        elif action == "flag":
            db["war_room_posts"].update_one(
                {"post_id": post_id},
                {
                    "$set": {"is_flagged": True},
                    "$inc": {"flag_count": 1}
                }
            )
        
        elif action == "warn":
            db["war_room_user_ranks"].update_one(
                {"user_id": user_id},
                {
                    "$inc": {"warning_count": 1}
                },
                upsert=True
            )
        
        # Record moderation event
        mod_event = {
            "event_id": event_id,
            "event_type": action,
            "target_type": "post",
            "target_id": post_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "duration_hours": duration_hours,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        db["war_room_moderation_events"].insert_one(mod_event)
        
        return mod_event


class RankEngine:
    """Rank calculation and progression"""
    
    @staticmethod
    async def update_user_rank(user_id: str) -> None:
        """Update user rank after posts/receipts"""
        rank_data = await WarRoomService.calculate_user_rank(user_id)
        
        db["war_room_user_ranks"].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "rank": rank_data["rank"],
                    "rank_points": rank_data["rank_points"],
                    "total_posts": rank_data["total_posts"],
                    "template_compliance_rate": rank_data["template_compliance_rate"],
                    "graded_picks": rank_data["graded_picks"],
                    "graded_win_rate": rank_data.get("win_rate"),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )


class LeaderboardEngine:
    """Leaderboard calculation with risk-adjusted metrics"""
    
    @staticmethod
    async def calculate_volatility_adjusted_score(user_id: str) -> float:
        """
        Calculate volatility-adjusted score
        Score = (Win Rate * Sample Size - Volatility Penalty)
        """
        user_rank = db["war_room_user_ranks"].find_one({"user_id": user_id})
        
        if not user_rank:
            return 0.0
        
        win_rate = user_rank.get("graded_win_rate", 0) or 0
        sample_size = user_rank.get("graded_picks", 0)
        max_drawdown = user_rank.get("max_drawdown", 0.2)
        
        if sample_size < 10:
            return 0.0  # Minimum 10 graded picks
        
        # Volatility penalty: higher drawdown = lower score
        volatility_penalty = max_drawdown * 100
        
        score = (win_rate * 100) + (sample_size * 0.5) - volatility_penalty
        
        return max(0.0, score)
    
    @staticmethod
    async def refresh_leaderboard() -> None:
        """Recalculate entire leaderboard"""
        users = db["war_room_user_ranks"].find({})
        
        updates = []
        for user in users:
            user_id = user["user_id"]
            score = await LeaderboardEngine.calculate_volatility_adjusted_score(user_id)
            
            updates.append(UpdateOne(
                {"user_id": user_id},
                {"$set": {"volatility_adjusted_score": score}}
            ))
        
        if updates:
            db["war_room_leaderboard"].bulk_write(updates)

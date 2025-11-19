"""
Reputation Engine (User ELO System)
Assigns accuracy-weighted reputation scores to Pro/Elite members
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from db.mongo import db
from services.logger import log_stage


class ReputationEngine:
    """
    Calculate User ELO scores based on pick accuracy
    
    This creates the "weight multiplier" for sharp_weighted_consensus:
    - Free users: 0.5x weight
    - Pro users: 1.0x weight  
    - Elite users: 2.0x weight (plus ELO bonus)
    
    The "Pay-to-Influence" model in action
    """
    
    def __init__(self):
        self.k_factor = 32  # ELO K-factor (standard chess value)
        self.base_elo = 1500  # Starting ELO
    
    def calculate_expected_score(self, elo_a: float, elo_b: float) -> float:
        """
        Calculate expected win probability
        Standard ELO formula
        """
        return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400))
    
    def update_elo(self, user_id: str, outcome: str, opponent_elo: Optional[float] = None) -> Dict[str, Any]:
        """
        Update user ELO based on pick outcome
        
        Args:
            user_id: User UUID
            outcome: "win", "loss", "push"
            opponent_elo: Market consensus ELO (default 1500)
        
        Returns:
            Updated ELO and stats
        """
        if outcome not in ["win", "loss"]:
            return {"status": "skip", "reason": "Push/void outcomes don't affect ELO"}
        
        # Get or create user reputation
        reputation = db["user_reputation"].find_one({"user_id": user_id})
        
        if not reputation:
            # Initialize new user
            reputation = {
                "user_id": user_id,
                "elo_score": self.base_elo,
                "total_picks": 0,
                "wins": 0,
                "losses": 0,
                "pushes": 0,
                "win_rate": 0.0,
                "roi": 0.0,
                "plan": "free",
                "weight_multiplier": 0.5,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            db["user_reputation"].insert_one(reputation)
        
        # Current ELO
        current_elo = reputation["elo_score"]
        opponent_elo = opponent_elo or self.base_elo  # Market consensus = 1500
        
        # Calculate expected score
        expected = self.calculate_expected_score(current_elo, opponent_elo)
        
        # Actual score (1 = win, 0 = loss)
        actual = 1.0 if outcome == "win" else 0.0
        
        # Update ELO
        new_elo = current_elo + self.k_factor * (actual - expected)
        
        # Update stats
        new_stats = {
            "elo_score": round(new_elo, 2),
            "total_picks": reputation["total_picks"] + 1,
            "wins": reputation["wins"] + (1 if outcome == "win" else 0),
            "losses": reputation["losses"] + (1 if outcome == "loss" else 0),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Recalculate win rate
        total_decisive = new_stats["wins"] + new_stats["losses"]
        if total_decisive > 0:
            new_stats["win_rate"] = round((new_stats["wins"] / total_decisive) * 100, 2)
        
        # Calculate weight multiplier based on plan + ELO bonus
        plan_weights = {"free": 0.5, "pro": 1.0, "elite": 2.0}
        base_weight = plan_weights.get(reputation["plan"], 1.0)
        
        # ELO bonus: +10% per 100 ELO above 1500
        elo_bonus = max(0, (new_elo - self.base_elo) / 1000)
        new_stats["weight_multiplier"] = round(base_weight * (1 + elo_bonus), 2)
        
        # Update database
        db["user_reputation"].update_one(
            {"user_id": user_id},
            {"$set": new_stats}
        )
        
        log_stage(
            "reputation_engine",
            "elo_updated",
            input_payload={
                "user_id": user_id,
                "outcome": outcome,
                "old_elo": current_elo
            },
            output_payload={
                "new_elo": new_elo,
                "elo_change": new_elo - current_elo,
                "weight_multiplier": new_stats["weight_multiplier"]
            }
        )
        
        return {
            "status": "ok",
            "old_elo": current_elo,
            "new_elo": new_elo,
            "elo_change": round(new_elo - current_elo, 2),
            "weight_multiplier": new_stats["weight_multiplier"]
        }
    
    def calculate_sharp_weighted_consensus(self, event_id: str) -> float:
        """
        Calculate weighted consensus sentiment for an event
        
        This is the HYBRID FEATURE that combines:
        - Hard data (odds, lines)
        - Soft data (weighted expert sentiment)
        
        Returns sentiment score -1 to +1 weighted by user ELO and plan
        """
        # Get all community picks for this event
        picks = list(db["community_picks"].find({"event_id": event_id}))
        
        if not picks:
            return 0.0  # Neutral if no community data
        
        weighted_sentiments = []
        
        for pick in picks:
            user_id = pick["user_id"]
            
            # Get user reputation
            reputation = db["user_reputation"].find_one({"user_id": user_id})
            if not reputation:
                continue
            
            # Get sentiment from original message
            message = db["community_messages"].find_one({"id": pick["message_id"]})
            if not message or message.get("parsed_sentiment") is None:
                continue
            
            sentiment = message["parsed_sentiment"]
            weight = reputation.get("weight_multiplier", 1.0)
            
            weighted_sentiments.append(sentiment * weight)
        
        if not weighted_sentiments:
            return 0.0
        
        # Average weighted sentiment
        consensus = sum(weighted_sentiments) / len(weighted_sentiments)
        
        return round(consensus, 2)
    
    def get_leaderboard(self, limit: int = 100) -> list:
        """
        Get top users by ELO score
        Used for community gamification
        """
        users = list(
            db["user_reputation"]
            .find({})
            .sort("elo_score", -1)
            .limit(limit)
        )
        
        leaderboard = []
        for i, user in enumerate(users):
            leaderboard.append({
                "rank": i + 1,
                "user_id": user["user_id"][:8] + "***",  # Anonymize
                "elo_score": user["elo_score"],
                "win_rate": user["win_rate"],
                "total_picks": user["total_picks"],
                "plan": user["plan"]
            })
        
        return leaderboard


# Singleton instance
reputation_engine = ReputationEngine()

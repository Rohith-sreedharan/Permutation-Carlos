"""
Verification Service - Outcome Resolution & Trust Loop
Automatically verifies creator forecasts against real game results
Builds public ledger of accuracy for radical transparency
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from db.mongo import db
from legacy_config import TRUST_WINDOWS, PUBLIC_LEDGER_SIZE, FORECAST_STATUS
import logging

logger = logging.getLogger(__name__)


class VerificationService:
    """
    Automated outcome verification for creator forecasts and AI predictions
    Powers the "Trust & Performance Loop"
    """
    
    def __init__(self):
        self.db = db
    
    def verify_outcomes(self, lookback_hours: int = 24) -> Dict[str, int]:
        """
        Main cron job function - runs every 24 hours
        Resolves all forecasts for events that have completed in the last N hours
        
        Args:
            lookback_hours: How far back to check for completed events
        
        Returns:
            Statistics: {"verified": X, "correct": Y, "incorrect": Z, "push": W}
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Find all events that have completed (commence_time + 4 hours is a safe estimate)
        completed_events = list(self.db["events"].find({
            "commence_time": {
                "$lt": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
            },
            "commence_time": {
                "$gte": cutoff_time.isoformat()
            }
        }))
        
        stats = {"verified": 0, "correct": 0, "incorrect": 0, "push": 0}
        
        for event in completed_events:
            event_id = event.get("event_id") or event.get("id")
            if not event_id:
                continue
            
            # Get actual result (would integrate with sports data API)
            actual_result = self._fetch_actual_result(event_id)
            if not actual_result:
                logger.warning(f"Could not fetch result for event {event_id}")
                continue
            
            # Verify all forecasts for this event
            self._verify_event_forecasts(event_id, actual_result, stats)
            
            # Verify AI predictions
            self._verify_ai_predictions(event_id, actual_result, stats)
        
        logger.info(f"Verification complete: {stats}")
        return stats
    
    def _fetch_actual_result(self, event_id: str) -> Optional[Dict]:
        """
        Fetch actual game result from sports data provider
        
        In production, integrate with:
        - The Odds API (they provide scores)
        - ESPN API
        - SportsRadar
        
        Returns:
            {
                "home_score": 108,
                "away_score": 102,
                "winner": "home",  # or "away" or "tie"
                "total": 210,
                "margin": 6
            }
        """
        # TODO: Implement actual API integration
        # For now, return None (no result available)
        
        # Placeholder logic - check if we have cached results
        cached_result = self.db["game_results"].find_one({"event_id": event_id})
        return cached_result
    
    def _verify_event_forecasts(self, event_id: str, actual_result: Dict, stats: Dict):
        """
        Verify all creator forecasts for a specific event
        Updates forecast documents with verification status
        """
        forecasts = list(self.db["ai_picks"].find({
            "event_id": event_id,
            "verification_status": FORECAST_STATUS["PENDING"]
        }))
        
        for forecast in forecasts:
            is_correct, status = self._check_forecast_accuracy(forecast, actual_result)
            
            # Update forecast with verification
            self.db["ai_picks"].update_one(
                {"_id": forecast["_id"]},
                {
                    "$set": {
                        "verification_status": status,
                        "verified_at": datetime.now(timezone.utc).isoformat(),
                        "actual_result": actual_result
                    }
                }
            )
            
            # Update creator accuracy stats
            self._update_creator_stats(forecast.get("creator_id"), status)
            
            stats["verified"] += 1
            if status == FORECAST_STATUS["CORRECT"]:
                stats["correct"] += 1
            elif status == FORECAST_STATUS["INCORRECT"]:
                stats["incorrect"] += 1
            elif status == FORECAST_STATUS["PUSH"]:
                stats["push"] += 1
    
    def _verify_ai_predictions(self, event_id: str, actual_result: Dict, stats: Dict):
        """
        Verify AI model predictions for trust loop metrics
        """
        predictions = list(self.db["predictions"].find({
            "event_id": event_id,
            "verification_status": FORECAST_STATUS["PENDING"]
        }))
        
        for pred in predictions:
            is_correct, status = self._check_prediction_accuracy(pred, actual_result)
            
            self.db["predictions"].update_one(
                {"_id": pred["_id"]},
                {
                    "$set": {
                        "verification_status": status,
                        "verified_at": datetime.now(timezone.utc).isoformat(),
                        "actual_result": actual_result
                    }
                }
            )
            
            stats["verified"] += 1
            if status == FORECAST_STATUS["CORRECT"]:
                stats["correct"] += 1
            elif status == FORECAST_STATUS["INCORRECT"]:
                stats["incorrect"] += 1
    
    def _check_forecast_accuracy(self, forecast: Dict, actual: Dict) -> Tuple[bool, str]:
        """
        Determine if a forecast was correct
        
        Handles different bet types:
        - Moneyline: Did predicted team win?
        - Spread: Did team cover the spread?
        - Total: Did game go over/under?
        """
        market_type = forecast.get("market_type", "").lower()
        selection = forecast.get("selection", "").lower()
        
        if "moneyline" in market_type or "h2h" in market_type:
            predicted_winner = "home" if "home" in selection else "away"
            is_correct = predicted_winner == actual.get("winner")
            return is_correct, FORECAST_STATUS["CORRECT"] if is_correct else FORECAST_STATUS["INCORRECT"]
        
        elif "spread" in market_type:
            # Check if team covered spread
            spread_line = forecast.get("line", 0)
            margin = actual.get("margin", 0)
            
            if "home" in selection:
                covered = margin > spread_line
            else:
                covered = margin < spread_line
            
            if abs(margin - spread_line) < 0.5:  # Push condition
                return False, FORECAST_STATUS["PUSH"]
            
            return covered, FORECAST_STATUS["CORRECT"] if covered else FORECAST_STATUS["INCORRECT"]
        
        elif "total" in market_type or "over_under" in market_type:
            total_line = forecast.get("line", 0)
            actual_total = actual.get("total", 0)
            
            if abs(actual_total - total_line) < 0.5:  # Push
                return False, FORECAST_STATUS["PUSH"]
            
            if "over" in selection:
                is_correct = actual_total > total_line
            else:
                is_correct = actual_total < total_line
            
            return is_correct, FORECAST_STATUS["CORRECT"] if is_correct else FORECAST_STATUS["INCORRECT"]
        
        # Unknown market type - cannot verify
        return False, FORECAST_STATUS["PENDING"]
    
    def _check_prediction_accuracy(self, prediction: Dict, actual: Dict) -> Tuple[bool, str]:
        """
        Verify AI model prediction accuracy
        Similar to forecast checking but for AI predictions
        """
        recommended_bet = prediction.get("recommended_bet", "")
        if not recommended_bet:
            return False, FORECAST_STATUS["PENDING"]
        
        # Parse recommended_bet string (e.g., "Home ML +120" or "Over 215.5")
        if "home" in recommended_bet.lower():
            is_correct = actual.get("winner") == "home"
        elif "away" in recommended_bet.lower():
            is_correct = actual.get("winner") == "away"
        elif "over" in recommended_bet.lower():
            total_line = float(recommended_bet.split()[-1]) if recommended_bet.split() else 0
            is_correct = actual.get("total", 0) > total_line
        elif "under" in recommended_bet.lower():
            total_line = float(recommended_bet.split()[-1]) if recommended_bet.split() else 0
            is_correct = actual.get("total", 0) < total_line
        else:
            return False, FORECAST_STATUS["PENDING"]
        
        return is_correct, FORECAST_STATUS["CORRECT"] if is_correct else FORECAST_STATUS["INCORRECT"]
    
    def _update_creator_stats(self, creator_id: str, status: str):
        """
        Update creator's rolling accuracy statistics
        """
        if not creator_id or status == FORECAST_STATUS["PUSH"]:
            return
        
        increment = {"total_forecasts": 1}
        if status == FORECAST_STATUS["CORRECT"]:
            increment["correct_forecasts"] = 1
        elif status == FORECAST_STATUS["INCORRECT"]:
            increment["incorrect_forecasts"] = 1
        
        self.db["users"].update_one(
            {"_id": creator_id},
            {"$inc": increment}
        )
    
    def get_model_accuracy(self, days: int = 7) -> Dict[str, float]:
        """
        Calculate AI model accuracy over rolling window
        Powers the Trust Loop display
        
        Args:
            days: Window size (7, 30, or 90)
        
        Returns:
            {
                "accuracy": 0.64,
                "total_verified": 120,
                "correct": 77,
                "incorrect": 43,
                "win_rate": 0.64
            }
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        verified_predictions = list(self.db["predictions"].find({
            "verified_at": {"$gte": cutoff.isoformat()},
            "verification_status": {"$in": [FORECAST_STATUS["CORRECT"], FORECAST_STATUS["INCORRECT"]]}
        }))
        
        total = len(verified_predictions)
        correct = len([p for p in verified_predictions if p.get("verification_status") == FORECAST_STATUS["CORRECT"]])
        incorrect = total - correct
        
        accuracy = correct / total if total > 0 else 0.0
        
        return {
            "accuracy": round(accuracy, 3),
            "win_rate": round(accuracy, 3),
            "total_verified": total,
            "correct": correct,
            "incorrect": incorrect,
            "window_days": days
        }
    
    def get_public_ledger(self, limit: int = PUBLIC_LEDGER_SIZE) -> List[Dict]:
        """
        Get top N most accurate forecasts from the previous week
        Public transparency leaderboard
        
        Returns:
            [
                {
                    "creator_id": "...",
                    "creator_name": "SharpAnalyst",
                    "forecast": "Warriors -5.5",
                    "confidence": 0.78,
                    "result": "CORRECT",
                    "event": "Warriors vs Lakers",
                    "verified_at": "2025-11-24T..."
                },
                ...
            ]
        """
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Get all verified correct forecasts from last week with high confidence
        top_forecasts = list(self.db["ai_picks"].find({
            "verified_at": {"$gte": one_week_ago.isoformat()},
            "verification_status": FORECAST_STATUS["CORRECT"],
            "confidence": {"$gte": 0.60}  # Only high-confidence picks
        }).sort("confidence", -1).limit(limit))
        
        # Enrich with creator and event data
        ledger = []
        for forecast in top_forecasts:
            creator_id = forecast.get("creator_id")
            event_id = forecast.get("event_id")
            
            creator = self.db["users"].find_one({"_id": creator_id})
            event = self.db["events"].find_one({"event_id": event_id})
            
            ledger.append({
                "creator_id": str(creator_id) if creator_id else "AI Model",
                "creator_name": creator.get("username", "AI Model") if creator else "AI Model",
                "forecast": forecast.get("selection", "N/A"),
                "confidence": forecast.get("confidence", 0),
                "result": forecast.get("verification_status"),
                "event": f"{event.get('away_team')} @ {event.get('home_team')}" if event else "N/A",
                "verified_at": forecast.get("verified_at"),
                "sport": event.get("sport_key") if event else "N/A"
            })
        
        return ledger


# Singleton instance
verification_service = VerificationService()


# Convenience functions for route usage
def verify_recent_outcomes(hours: int = 24) -> Dict[str, int]:
    """Run verification for events completed in last N hours"""
    return verification_service.verify_outcomes(hours)


def get_trust_metrics(days: int = 7) -> Dict[str, float]:
    """Get model accuracy for trust loop display"""
    return verification_service.get_model_accuracy(days)


def get_accuracy_ledger(limit: int = PUBLIC_LEDGER_SIZE) -> List[Dict]:
    """Get public ledger of top verified forecasts"""
    return verification_service.get_public_ledger(limit)

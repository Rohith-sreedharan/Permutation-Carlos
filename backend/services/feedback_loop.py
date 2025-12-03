"""
Behavioral Feedback Loop - THE MOAT + CLV Tracking
Logs predictions vs outcomes and continuously improves the model

PHASE 18 ADDITION: Closing Line Value (CLV) logging for model validation
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import logging
import statistics
from core.numerical_accuracy import ClosingLineValue
from core.post_game_recap import PredictionRecord, FeedbackLogger as RecapLogger

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    Behavioral Feedback Loop (MOAT Layer 4)
    
    Core Learning System:
    1. Log every pick: Model prediction + User decision + Market odds
    2. Record outcome: Win/Loss/Push
    3. Calculate Error Delta: |Predicted Probability - Actual Result|
    4. Feed back to agents: Adjust simulation parameters
    
    This creates a self-improving system that gets smarter with every pick
    """
    
    def __init__(self, db_client, event_bus):
        self.db = db_client
        self.bus = event_bus
        
    async def start(self):
        """Start feedback loop listener"""
        await self.bus.subscribe("feedback.outcomes", self.handle_outcome)
        logger.info("🔄 Feedback Loop started - THE MOAT is active")
        
    async def log_prediction(
        self,
        user_id: str,
        event_id: str,
        pick_data: Dict[str, Any],
        model_probability: float,
        market_odds: float
    ) -> str:
        """
        Log a pick with model prediction for future comparison
        
        Args:
            user_id: User making the pick
            event_id: Event being bet on
            pick_data: Bet details (team, type, line, etc.)
            model_probability: Model's true probability (from simulation)
            market_odds: Market implied probability
            
        Returns:
            pick_id for tracking
        """
        try:
            db = self.db["beatvegas_db"]
            
            record = {
                "user_id": user_id,
                "event_id": event_id,
                "pick_data": pick_data,
                "model_probability": model_probability,
                "market_probability": self._odds_to_probability(float(market_odds)),
                "market_odds": market_odds,
                "timestamp": datetime.utcnow(),
                "outcome": None,
                "settled": False,
                "error_delta": None
            }
            
            result = db.prediction_outcomes.insert_one(record)
            pick_id = str(result.inserted_id)
            
            logger.info(f"📝 Logged prediction: {pick_id} | Model: {model_probability:.2%} | Market: {self._odds_to_probability(market_odds):.2%}")
            
            return pick_id
            
        except Exception as e:
            logger.error(f"Error logging prediction: {e}")
            return ""
            
    async def handle_outcome(self, message: Dict[str, Any]):
        """
        Handle pick outcome and calculate error delta
        Triggered when game finishes
        """
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            pick_id = data.get("pick_id")
            outcome = data.get("outcome")  # "win", "loss", "push"
            
            await self._record_outcome(pick_id, outcome)
            
            # Calculate error and feed back to model
            error_delta = await self._calculate_error_delta(pick_id, outcome)
            
            if error_delta is not None:
                await self._update_model_parameters(pick_id, error_delta)
                
            logger.info(f"✅ Outcome recorded: {pick_id} | Result: {outcome} | Error: {error_delta:.3f if error_delta else 'N/A'}")
            
        except Exception as e:
            logger.error(f"Error handling outcome: {e}")
            
    async def _record_outcome(self, pick_id: str, outcome: str):
        """Record the actual outcome of a pick"""
        try:
            db = self.db["beatvegas_db"]
            
            db.prediction_outcomes.update_one(
                {"_id": pick_id},
                {
                    "$set": {
                        "outcome": outcome,
                        "settled": True,
                        "settled_at": datetime.utcnow()
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error recording outcome: {e}")
            
    async def _calculate_error_delta(self, pick_id: str, outcome: str) -> Optional[float]:
        """
        Calculate Error Delta: How wrong was our model?
        
        Error Delta = |Model Probability - Actual Result|
        - Actual Result: 1.0 if win, 0.0 if loss, 0.5 if push
        - Lower error = better calibration
        
        This is the KEY METRIC for model improvement
        """
        try:
            db = self.db["beatvegas_db"]
            
            record = db.prediction_outcomes.find_one({"_id": pick_id})
            if not record:
                return None
                
            model_prob = record.get("model_probability")
            if model_prob is None:
                return None
                
            # Convert outcome to actual result
            actual_result = {
                "win": 1.0,
                "loss": 0.0,
                "push": 0.5
            }.get(outcome)
            
            if actual_result is None:
                return None
                
            # Calculate error
            error_delta = abs(model_prob - actual_result)
            
            # Store error
            db.prediction_outcomes.update_one(
                {"_id": pick_id},
                {"$set": {"error_delta": error_delta}}
            )
            
            return error_delta
            
        except Exception as e:
            logger.error(f"Error calculating error delta: {e}")
            return None
            
    async def _update_model_parameters(self, pick_id: str, error_delta: float):
        """
        Feed error delta back to simulation parameters
        This is WHERE THE MAGIC HAPPENS - the moat gets deeper
        
        If model consistently over/underestimates:
        - Adjust injury impact weights
        - Tune home field advantage
        - Recalibrate volatility curves
        - Update rest day multipliers
        """
        try:
            db = self.db["beatvegas_db"]
            
            # Get pick details
            record = db.prediction_outcomes.find_one({"_id": pick_id})
            if not record:
                return
                
            event_id = record.get("event_id")
            pick_data = record.get("pick_data", {})
            sport = pick_data.get("sport")
            bet_type = pick_data.get("bet_type")
            
            # Get recent error trends for this sport/bet type
            recent_errors = await self._get_recent_errors(sport, bet_type, limit=100)
            
            if len(recent_errors) < 10:
                # Not enough data yet
                return
                
            avg_error = statistics.mean(recent_errors)
            
            # If average error is high, flag for parameter adjustment
            if avg_error > 0.15:  # More than 15% average error
                logger.warning(f"🔧 Model recalibration needed for {sport} {bet_type}: Avg error {avg_error:.2%}")
                
                # Store adjustment recommendation
                db.model_adjustments.insert_one({
                    "sport": sport,
                    "bet_type": bet_type,
                    "avg_error": avg_error,
                    "sample_size": len(recent_errors),
                    "timestamp": datetime.utcnow(),
                    "status": "pending",
                    "recommendation": self._generate_adjustment_recommendation(avg_error, recent_errors)
                })
                
        except Exception as e:
            logger.error(f"Error updating model parameters: {e}")
            
    async def _get_recent_errors(self, sport: str, bet_type: str, limit: int = 100) -> list:
        """Get recent error deltas for sport/bet type combination"""
        try:
            db = self.db["beatvegas_db"]
            
            recent = list(db.prediction_outcomes.find({
                "pick_data.sport": sport,
                "pick_data.bet_type": bet_type,
                "settled": True,
                "error_delta": {"$exists": True}
            }).sort("settled_at", -1).limit(limit))
            
            return [r["error_delta"] for r in recent if r.get("error_delta") is not None]
            
        except Exception as e:
            logger.error(f"Error getting recent errors: {e}")
            return []
            
    def _generate_adjustment_recommendation(self, avg_error: float, error_history: list) -> Dict[str, Any]:
        """
        Generate specific parameter adjustment recommendations
        This would interface with the Monte Carlo engine in production
        """
        # Calculate trend
        if len(error_history) >= 2:
            recent_avg = statistics.mean(error_history[:20])
            older_avg = statistics.mean(error_history[20:40]) if len(error_history) >= 40 else recent_avg
            trend = "improving" if recent_avg < older_avg else "worsening"
        else:
            trend = "stable"
            
        return {
            "avg_error": avg_error,
            "trend": trend,
            "suggested_actions": [
                "Review injury impact weights",
                "Adjust home field advantage multiplier",
                "Recalibrate volatility parameters"
            ] if avg_error > 0.20 else [
                "Fine-tune existing parameters",
                "Monitor for another 50 picks"
            ]
        }
        
    def _odds_to_probability(self, american_odds: float) -> float:
        """Convert American odds to probability"""
        if american_odds > 0:
            return 100 / (american_odds + 100)
        else:
            return abs(american_odds) / (abs(american_odds) + 100)
            
    async def get_model_performance_report(self, sport: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive model performance report
        Shows calibration quality and improvement over time
        """
        try:
            db = self.db["beatvegas_db"]
            
            query = {"settled": True, "error_delta": {"$exists": True}}
            if sport:
                query["pick_data.sport"] = sport
                
            all_outcomes = list(db.prediction_outcomes.find(query))
            
            if not all_outcomes:
                return {"error": "No settled picks yet"}
                
            errors = [o["error_delta"] for o in all_outcomes]
            
            # Calculate metrics
            avg_error = statistics.mean(errors)
            median_error = statistics.median(errors)
            min_error = min(errors)
            max_error = max(errors)
            
            # Calibration quality
            if avg_error < 0.10:
                calibration = "EXCELLENT"
            elif avg_error < 0.15:
                calibration = "GOOD"
            elif avg_error < 0.25:
                calibration = "FAIR"
            else:
                calibration = "NEEDS IMPROVEMENT"
                
            # Calculate by sport breakdown
            sport_breakdown = {}
            for outcome in all_outcomes:
                s = outcome.get("pick_data", {}).get("sport", "unknown")
                if s not in sport_breakdown:
                    sport_breakdown[s] = []
                sport_breakdown[s].append(outcome["error_delta"])
                
            sport_stats = {
                sport: {
                    "avg_error": statistics.mean(errors),
                    "sample_size": len(errors)
                }
                for sport, errors in sport_breakdown.items()
            }
            
            return {
                "total_predictions": len(all_outcomes),
                "avg_error": round(avg_error, 4),
                "median_error": round(median_error, 4),
                "min_error": round(min_error, 4),
                "max_error": round(max_error, 4),
                "calibration_quality": calibration,
                "sport_breakdown": sport_stats,
                "moat_status": "ACTIVE - Model learning from every pick"
            }
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return {"error": str(e)}
    
    async def log_clv_snapshot(
        self,
        event_id: str,
        model_projection: float,
        book_line_open: float,
        lean: str,
        prediction_type: str = 'total'
    ) -> str:
        """
        PHASE 18: Log Closing Line Value (CLV) snapshot
        
        Snapshot taken at prediction time with:
        - Model projection (e.g., 227.5 total points)
        - Opening book line (e.g., 225.5)
        - Our lean direction ('over', 'under', 'home', 'away')
        
        Later, when game starts, we log closing line to calculate CLV
        
        Args:
            event_id: Event identifier
            model_projection: Our model's projection
            book_line_open: Bookmaker's opening line
            lean: Our recommendation ('over', 'under', 'home', 'away')
            prediction_type: 'total' | 'spread' | 'ml'
            
        Returns:
            clv_id for later update
        """
        try:
            db = self.db["beatvegas_db"]
            
            clv_record = {
                "event_id": event_id,
                "prediction_timestamp": datetime.now(timezone.utc),
                "model_projection": model_projection,
                "book_line_open": book_line_open,
                "book_line_close": None,  # Update later
                "lean": lean,
                "prediction_type": prediction_type,
                "clv_favorable": None,  # Calculate after close
                "settled": False
            }
            
            result = db.clv_snapshots.insert_one(clv_record)
            clv_id = str(result.inserted_id)
            
            logger.info(f"📸 CLV Snapshot: {event_id} | Projection: {model_projection} | Open: {book_line_open} | Lean: {lean}")
            
            return clv_id
            
        except Exception as e:
            logger.error(f"Error logging CLV snapshot: {e}")
            return ""
    
    async def update_clv_closing(
        self,
        event_id: str,
        book_line_close: float
    ) -> bool:
        """
        PHASE 18: Update CLV with closing line
        
        Called when game is about to start (closing line is set)
        Calculates if line moved in our favor
        
        Args:
            event_id: Event identifier
            book_line_close: Bookmaker's closing line
            
        Returns:
            True if CLV was favorable
        """
        try:
            db = self.db["beatvegas_db"]
            
            # Find open CLV snapshot
            snapshot = db.clv_snapshots.find_one({
                "event_id": event_id,
                "settled": False
            })
            
            if not snapshot:
                logger.warning(f"No CLV snapshot found for event {event_id}")
                return False
            
            # Use ClosingLineValue calculator
            clv = ClosingLineValue(
                event_id=event_id,
                prediction_timestamp=snapshot["prediction_timestamp"],
                model_projection=snapshot["model_projection"],
                book_line_open=snapshot["book_line_open"],
                book_line_close=None,
                lean=snapshot["lean"]
            )
            
            # Calculate CLV
            clv_favorable = clv.calculate_clv(closing_line=book_line_close)
            
            # Update record
            db.clv_snapshots.update_one(
                {"_id": snapshot["_id"]},
                {
                    "$set": {
                        "book_line_close": book_line_close,
                        "clv_favorable": clv_favorable,
                        "settled": True,
                        "settled_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            status = "✅ FAVORABLE" if clv_favorable else "❌ UNFAVORABLE"
            logger.info(f"🎯 CLV Updated: {event_id} | {snapshot['book_line_open']} → {book_line_close} | {status}")
            
            return clv_favorable
            
        except Exception as e:
            logger.error(f"Error updating CLV closing: {e}")
            return False
    
    async def get_clv_performance(
        self,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        PHASE 18: Get CLV performance metrics
        
        Target: >= 63% favorable CLV rate over time
        This validates that our model is consistently beating the closing line
        
        Args:
            days_back: Number of days to analyze
            
        Returns:
            {
                'total_clv_records': 247,
                'clv_favorable_rate': 0.638,  # 63.8%
                'target_rate': 0.63,
                'meets_target': True,
                'by_prediction_type': {...},
                'recent_trend': [...]
            }
        """
        try:
            db = self.db["beatvegas_db"]
            
            # Get CLV records from last N days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            records = list(db.clv_snapshots.find({
                "settled": True,
                "prediction_timestamp": {"$gte": cutoff_date}
            }))
            
            if not records:
                return {
                    "total_clv_records": 0,
                    "clv_favorable_rate": 0,
                    "error": "No CLV data available"
                }
            
            total_records = len(records)
            favorable_count = sum(1 for r in records if r.get("clv_favorable") == True)
            clv_rate = favorable_count / total_records
            
            # Breakdown by prediction type
            by_type = {}
            for pred_type in ['total', 'spread', 'ml']:
                type_records = [r for r in records if r.get("prediction_type") == pred_type]
                if type_records:
                    type_favorable = sum(1 for r in type_records if r.get("clv_favorable") == True)
                    by_type[pred_type] = {
                        'count': len(type_records),
                        'favorable_rate': type_favorable / len(type_records)
                    }
            
            # Recent trend (last 7 days)
            recent_records = [r for r in records 
                            if r["prediction_timestamp"] >= (datetime.now(timezone.utc) - timedelta(days=7))]
            recent_favorable = sum(1 for r in recent_records if r.get("clv_favorable") == True)
            recent_rate = recent_favorable / len(recent_records) if recent_records else 0
            
            target_rate = 0.63
            meets_target = clv_rate >= target_rate
            
            return {
                'total_clv_records': total_records,
                'clv_favorable_rate': round(clv_rate, 3),
                'clv_favorable_count': favorable_count,
                'target_rate': target_rate,
                'meets_target': meets_target,
                'by_prediction_type': by_type,
                'recent_7day_rate': round(recent_rate, 3),
                'days_analyzed': days_back,
                'status': '✅ BEATING CLOSING LINE' if meets_target else '⚠️ BELOW TARGET'
            }
            
        except Exception as e:
            logger.error(f"Error getting CLV performance: {e}")
            return {"error": str(e)}


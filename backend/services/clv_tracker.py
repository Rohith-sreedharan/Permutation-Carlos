"""
Closing Line Value (CLV) Tracker
Logs all predictions and tracks performance vs closing lines

Per spec Section 4: CLV logging for model validation
Target: >= 63% of predictions on right side of closing move
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.mongo import db
import logging
from core.numerical_accuracy import ClosingLineValue

logger = logging.getLogger(__name__)


class CLVTracker:
    """
    Track all predictions and calculate CLV after games close
    
    This is critical for model validation - measures if our model
    predictions are "sharp" (ahead of market movements)
    """
    
    @staticmethod
    def log_prediction(
        event_id: str,
        model_projection: float,
        book_line_open: float,
        prediction_type: str,  # "total", "spread", "ml"
        lean: str,  # "over", "under", "home", "away"
        sim_count: int,
        confidence: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log a prediction at the time it's made
        
        Args:
            event_id: Unique game identifier
            model_projection: Our model's projected value
            book_line_open: Bookmaker's line when we made prediction
            prediction_type: Type of prediction
            lean: Which side we're leaning
            sim_count: Simulation tier used
            confidence: Confidence score (0-100)
            metadata: Additional context
            
        Returns:
            prediction_id for future reference
        """
        try:
            prediction_doc = {
                "event_id": event_id,
                "prediction_timestamp": datetime.now(timezone.utc),
                "model_projection": model_projection,
                "book_line_open": book_line_open,
                "prediction_type": prediction_type,
                "lean": lean,
                "sim_count": sim_count,
                "confidence": confidence,
                "metadata": metadata or {},
                "book_line_close": None,  # To be filled later
                "clv_favorable": None,
                "actual_result": None,
                "result_recorded": False
            }
            
            result = db.clv_predictions.insert_one(prediction_doc)
            logger.info(f"✅ CLV Prediction logged: {event_id} - {prediction_type} - {lean}")
            
            return str(result.inserted_id) if result else None
            
        except Exception as e:
            logger.error(f"❌ CLV logging failed: {e}")
            return None
    
    @staticmethod
    def update_closing_line(
        event_id: str,
        prediction_type: str,
        closing_line: float
    ) -> Dict[str, Any]:
        """
        Update with closing line and calculate CLV
        
        Call this when games close (typically 5-10 minutes before start)
        
        Returns:
            {
                "predictions_updated": 3,
                "favorable_clv_count": 2,
                "clv_percentage": 66.7
            }
        """
        try:
            # Find all predictions for this event & type
            predictions = list(db.clv_predictions.find({
                "event_id": event_id,
                "prediction_type": prediction_type,
                "book_line_close": None
            }).limit(100))
            
            if not predictions:
                logger.warning(f"No predictions found for {event_id} - {prediction_type}")
                return {"predictions_updated": 0}
            
            favorable_count = 0
            
            for pred in predictions:
                # Calculate CLV
                clv = ClosingLineValue(
                    event_id=event_id,
                    prediction_timestamp=pred["prediction_timestamp"],
                    model_projection=pred["model_projection"],
                    book_line_open=pred["book_line_open"],
                    book_line_close=None,
                    lean=pred["lean"]
                )
                
                clv_favorable = clv.calculate_clv(closing_line)
                
                # Update document
                db.clv_predictions.update_one(
                    {"_id": pred["_id"]},
                    {"$set": {
                        "book_line_close": closing_line,
                        "clv_favorable": clv_favorable,
                        "line_movement": closing_line - pred["book_line_open"]
                    }}
                )
                
                if clv_favorable:
                    favorable_count += 1
            
            clv_pct = (favorable_count / len(predictions)) * 100 if predictions else 0
            
            logger.info(f"✅ CLV Updated: {event_id} - {favorable_count}/{len(predictions)} favorable ({clv_pct:.1f}%)")
            
            return {
                "predictions_updated": len(predictions),
                "favorable_clv_count": favorable_count,
                "clv_percentage": round(clv_pct, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ CLV update failed: {e}")
            return {"predictions_updated": 0, "error": str(e)}
    
    @staticmethod
    def record_actual_result(
        event_id: str,
        actual_total: Optional[float] = None,
        actual_margin: Optional[float] = None,
        winner: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record actual game results for accuracy tracking
        
        Args:
            event_id: Game identifier
            actual_total: Final score total
            actual_margin: Final margin
            winner: "home" or "away"
        """
        try:
            # Update all predictions for this event
            result = db.clv_predictions.update_many(
                {"event_id": event_id},
                {"$set": {
                    "actual_total": actual_total,
                    "actual_margin": actual_margin,
                    "winner": winner,
                    "result_recorded": True,
                    "result_timestamp": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"✅ Result recorded: {event_id} - {result.modified_count} predictions updated")
            
            return {
                "predictions_updated": result.modified_count,
                "actual_total": actual_total,
                "actual_margin": actual_margin
            }
            
        except Exception as e:
            logger.error(f"❌ Result recording failed: {e}")
            return {"predictions_updated": 0, "error": str(e)}
    
    @staticmethod
    def get_clv_performance(
        days: int = 7,
        min_sim_count: int = 25000
    ) -> Dict[str, Any]:
        """
        Get CLV performance statistics
        
        Target: >= 63% favorable CLV rate
        
        Returns:
            {
                "total_predictions": 150,
                "favorable_count": 98,
                "favorable_percentage": 65.3,
                "by_tier": {...},
                "by_prediction_type": {...}
            }
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Get all predictions with CLV calculated
            predictions = list(db.clv_predictions.find({
                "prediction_timestamp": {"$gte": cutoff_date},
                "sim_count": {"$gte": min_sim_count},
                "clv_favorable": {"$ne": None}
            }).limit(1000))
            
            if not predictions:
                return {
                    "total_predictions": 0,
                    "favorable_count": 0,
                    "favorable_percentage": 0.0,
                    "message": "No predictions with CLV data"
                }
            
            favorable_count = sum(1 for p in predictions if p.get("clv_favorable"))
            total = len(predictions)
            favorable_pct = (favorable_count / total) * 100
            
            # Break down by tier
            by_tier = {}
            for sim_count in [25000, 50000, 100000]:
                tier_preds = [p for p in predictions if p["sim_count"] == sim_count]
                if tier_preds:
                    tier_favorable = sum(1 for p in tier_preds if p.get("clv_favorable"))
                    by_tier[f"{sim_count}"] = {
                        "count": len(tier_preds),
                        "favorable": tier_favorable,
                        "percentage": round((tier_favorable / len(tier_preds)) * 100, 1)
                    }
            
            # Break down by prediction type
            by_type = {}
            for pred_type in ["total", "spread", "ml"]:
                type_preds = [p for p in predictions if p["prediction_type"] == pred_type]
                if type_preds:
                    type_favorable = sum(1 for p in type_preds if p.get("clv_favorable"))
                    by_type[pred_type] = {
                        "count": len(type_preds),
                        "favorable": type_favorable,
                        "percentage": round((type_favorable / len(type_preds)) * 100, 1)
                    }
            
            return {
                "total_predictions": total,
                "favorable_count": favorable_count,
                "favorable_percentage": round(favorable_pct, 1),
                "target": 63.0,
                "meets_target": favorable_pct >= 63.0,
                "by_tier": by_tier,
                "by_prediction_type": by_type,
                "days": days
            }
            
        except Exception as e:
            logger.error(f"❌ CLV performance query failed: {e}")
            return {"error": str(e)}

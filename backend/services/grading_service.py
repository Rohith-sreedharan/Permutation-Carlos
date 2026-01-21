"""
Grading Service
===============
Grades published predictions against actual results.

CRITICAL PRINCIPLES:
1. Only grade published predictions (is_official=True)
2. Never grade internal/user reruns
3. Compute CLV against closing lines
4. Calculate Brier score and other metrics
5. Handle voids properly (postponed/cancelled games)
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from db.mongo import db
from db.schemas.logging_calibration_schemas import (
    Grading,
    BetStatus,
    ResultCode,
    EventStatus
)
import logging
import math

logger = logging.getLogger(__name__)


class GradingService:
    """
    Settles published predictions with CLV and scoring metrics
    """
    
    def __init__(self):
        self.grading_collection = db.grading
        self.published_collection = db.published_predictions
        self.predictions_collection = db.predictions
        self.event_results_collection = db.event_results
        self.odds_snapshots_collection = db.odds_snapshots
    
    def grade_published_prediction(
        self,
        publish_id: str,
        force_regrade: bool = False
    ) -> Optional[str]:
        """
        Grade a published prediction
        
        Args:
            publish_id: Published prediction to grade
            force_regrade: Allow regrading already graded predictions
        
        Returns:
            graded_id or None if cannot grade yet
        """
        # Check if already graded
        existing = self.grading_collection.find_one({"publish_id": publish_id})
        if existing and not force_regrade:
            logger.info(f"Prediction {publish_id} already graded")
            return existing["graded_id"]
        
        # Get published prediction
        published = self.published_collection.find_one({"publish_id": publish_id})
        if not published:
            logger.error(f"Published prediction {publish_id} not found")
            return None
        
        # Skip non-official predictions
        if not published.get("is_official", True):
            logger.info(f"Skipping non-official prediction {publish_id}")
            return None
        
        # Get prediction details
        prediction = self.predictions_collection.find_one({
            "prediction_id": published["prediction_id"]
        })
        
        if not prediction:
            logger.error(f"Prediction {published['prediction_id']} not found")
            return None
        
        # Get event result
        event_result = self.event_results_collection.find_one({
            "event_id": published["event_id"]
        })
        
        if not event_result:
            logger.info(f"Event result not available yet for {published['event_id']}")
            return None
        
        # Check event status
        event_status = event_result.get("status", EventStatus.SCHEDULED.value)
        
        if event_status == EventStatus.CANCELLED.value:
            return self._grade_as_void(publish_id, published, prediction, "CANCELLED")
        
        if event_status == EventStatus.POSTPONED.value:
            return self._grade_as_void(publish_id, published, prediction, "POSTPONED")
        
        if event_status != EventStatus.FINAL.value:
            logger.info(f"Event {published['event_id']} not final yet (status={event_status})")
            return None
        
        # Grade the prediction
        result_code = self._determine_result(
            prediction=prediction,
            event_result=event_result,
            ticket_terms=published.get("ticket_terms", {})
        )
        
        if result_code is None:
            logger.warning(f"Could not determine result for {publish_id}")
            return None
        
        # Calculate unit return
        unit_return = self._calculate_unit_return(
            result_code=result_code,
            ticket_terms=published.get("ticket_terms", {})
        )
        
        # Get closing line for CLV
        close_snapshot = self._get_closing_line_snapshot(
            event_id=published["event_id"],
            market_key=prediction["market_key"],
            selection=prediction["selection"]
        )
        
        clv = None
        close_snapshot_id = None
        
        if close_snapshot:
            close_snapshot_id = close_snapshot["snapshot_id"]
            clv = self._calculate_clv(
                prediction=prediction,
                close_snapshot=close_snapshot,
                ticket_terms=published.get("ticket_terms", {})
            )
        
        # Calculate Brier score
        brier = self._calculate_brier_score(
            prediction=prediction,
            result_code=result_code
        )
        
        # Calculate log loss
        logloss = self._calculate_logloss(
            prediction=prediction,
            result_code=result_code
        )
        
        # Build cohort tags
        cohort_tags = {
            "league": prediction.get("event_id", "").split("_")[0].upper(),
            "market": prediction.get("market_key"),
            "recommendation_state": prediction.get("recommendation_state"),
            "tier": prediction.get("tier"),
            "variance_bucket": prediction.get("variance_bucket"),
            "confidence_index": prediction.get("confidence_index")
        }
        
        # Create grading record
        graded_id = str(uuid.uuid4())
        
        grading = Grading(
            graded_id=graded_id,
            publish_id=publish_id,
            prediction_id=published["prediction_id"],
            event_id=published["event_id"],
            bet_status=BetStatus.SETTLED,
            result_code=result_code,
            units_returned=0.0,  # Will be calculated below
            clv_points=0.0,  # Will be calculated below
            brier=0.0,  # Will be calculated below
            unit_return=unit_return,
            close_snapshot_id=close_snapshot_id,
            clv=clv,
            brier_component=brier,
            logloss_component=logloss,
            cohort_tags=cohort_tags,
            graded_at=datetime.now(timezone.utc)
        )
        
        # Insert or update
        if existing and force_regrade:
            self.grading_collection.update_one(
                {"graded_id": existing["graded_id"]},
                {"$set": grading.model_dump()}
            )
            graded_id = existing["graded_id"]
        else:
            self.grading_collection.insert_one(grading.model_dump())
        
        clv_str = f"{clv:.2f}" if clv is not None else "0.00"
        brier_str = f"{brier:.4f}" if brier is not None else "0.0000"
        logger.info(
            f"✅ Graded prediction: {graded_id} "
            f"(result={result_code.value}, clv={clv_str}, "
            f"brier={brier_str})"
        )
        
        return graded_id
    
    def grade_all_pending(
        self,
        lookback_hours: int = 72
    ) -> Dict[str, int]:
        """
        Grade all pending published predictions from recent games
        
        Returns:
            {graded: X, voided: Y, pending: Z}
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        
        # Get published predictions not yet graded
        published_preds = list(self.published_collection.find({
            "is_official": True,
            "published_at_utc": {"$gte": cutoff}
        }))
        
        stats = {"graded": 0, "voided": 0, "pending": 0}
        
        for pub in published_preds:
            # Check if already graded
            existing = self.grading_collection.find_one({"publish_id": pub["publish_id"]})
            if existing:
                continue
            
            graded_id = self.grade_published_prediction(pub["publish_id"])
            
            if graded_id:
                grading = self.grading_collection.find_one({"graded_id": graded_id})
                if grading and grading["bet_status"] == BetStatus.VOID.value:
                    stats["voided"] += 1
                elif grading:
                    stats["graded"] += 1
                else:
                    stats["pending"] += 1
            else:
                stats["pending"] += 1
        
        logger.info(
            f"📊 Grading complete: {stats['graded']} graded, "
            f"{stats['voided']} voided, {stats['pending']} pending"
        )
        
        return stats
    
    def _grade_as_void(
        self,
        publish_id: str,
        published: Dict[str, Any],
        prediction: Dict[str, Any],
        reason: str
    ) -> str:
        """
        Grade a prediction as void
        """
        graded_id = str(uuid.uuid4())
        
        grading = Grading(
            graded_id=graded_id,
            publish_id=publish_id,
            prediction_id=published["prediction_id"],
            event_id=published["event_id"],
            bet_status=BetStatus.VOID,
            result_code=ResultCode.VOID,
            units_returned=1.0,  # Void returns stake
            unit_return=1.0,
            close_snapshot_id=None,
            clv_points=0.0,
            clv=0.0,
            brier_component=0.0,
            brier=0.0,
            cohort_tags={"void_reason": reason},
            graded_at=datetime.now(timezone.utc)
        )
        
        self.grading_collection.insert_one(grading.model_dump())
        
        logger.info(f"❌ Graded as VOID: {graded_id} ({reason})")
        
        return graded_id
    
    def _determine_result(
        self,
        prediction: Dict[str, Any],
        event_result: Dict[str, Any],
        ticket_terms: Dict[str, Any]
    ) -> Optional[ResultCode]:
        """
        Determine if prediction was WIN/LOSS/PUSH
        """
        market_key = prediction["market_key"]
        selection = prediction["selection"]
        
        # Extract scores
        home_score = event_result.get("home_score")
        away_score = event_result.get("away_score")
        total_score = event_result.get("total_score")
        margin = event_result.get("margin")
        
        if home_score is None or away_score is None:
            return None
        
        # Get line from ticket terms
        line = ticket_terms.get("line", prediction.get("model_line"))
        
        if line is None:
            logger.warning(f"No line available for {prediction['prediction_id']}")
            return None
        
        # Grade based on market type
        if "SPREAD" in market_key:
            return self._grade_spread(selection, line, margin)
        elif "TOTAL" in market_key:
            return self._grade_total(selection, line, total_score)
        elif "MONEYLINE" in market_key:
            return self._grade_moneyline(selection, margin)
        
        return None
    
    def _grade_spread(
        self,
        selection: str,
        line: float,
        margin: Optional[float]
    ) -> Optional[ResultCode]:
        """Grade spread bet"""
        if margin is None:
            return None
        
        # Determine if we're on home or away
        is_home = selection.upper() in ["HOME", "H"]
        
        # Adjust margin for away picks
        if not is_home:
            margin = -margin
        
        # Compare to line
        covered_by = margin + line
        
        if abs(covered_by) < 0.01:  # Push
            return ResultCode.PUSH
        elif covered_by > 0:
            return ResultCode.WIN
        else:
            return ResultCode.LOSS
    
    def _grade_total(
        self,
        selection: str,
        line: float,
        total_score: Optional[int]
    ) -> Optional[ResultCode]:
        """Grade total bet"""
        if total_score is None:
            return None
        
        is_over = selection.upper() in ["OVER", "O"]
        
        diff = total_score - line
        
        if abs(diff) < 0.01:  # Push
            return ResultCode.PUSH
        elif (is_over and diff > 0) or (not is_over and diff < 0):
            return ResultCode.WIN
        else:
            return ResultCode.LOSS
    
    def _grade_moneyline(
        self,
        selection: str,
        margin: Optional[float]
    ) -> Optional[ResultCode]:
        """Grade moneyline bet"""
        if margin is None:
            return None
        
        is_home = selection.upper() in ["HOME", "H"]
        
        if abs(margin) < 0.01:  # Tie (very rare)
            return ResultCode.PUSH
        elif (is_home and margin > 0) or (not is_home and margin < 0):
            return ResultCode.WIN
        else:
            return ResultCode.LOSS
    
    def _calculate_unit_return(
        self,
        result_code: ResultCode,
        ticket_terms: Dict[str, Any]
    ) -> float:
        """
        Calculate unit return from result and odds
        """
        if result_code == ResultCode.VOID or result_code == ResultCode.PUSH:
            return 0.0
        
        price_american = ticket_terms.get("price", -110)
        
        if result_code == ResultCode.WIN:
            if price_american > 0:
                return price_american / 100.0
            else:
                return 100.0 / abs(price_american)
        else:  # LOSS
            return -1.0
    
    def _get_closing_line_snapshot(
        self,
        event_id: str,
        market_key: str,
        selection: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get closing line snapshot
        """
        # Try to get marked closing line
        snapshot = self.odds_snapshots_collection.find_one({
            "event_id": event_id,
            "market_key": market_key,
            "selection": selection,
            "is_close_candidate": True
        })
        
        if snapshot:
            return snapshot
        
        # Fallback: get latest snapshot before game start
        event = db.events.find_one({"event_id": event_id})
        if not event:
            return None
        
        snapshot = self.odds_snapshots_collection.find_one(
            {
                "event_id": event_id,
                "market_key": market_key,
                "selection": selection,
                "timestamp_utc": {"$lte": event["start_time_utc"]}
            },
            sort=[("timestamp_utc", -1)]
        )
        
        return snapshot
    
    def _calculate_clv(
        self,
        prediction: Dict[str, Any],
        close_snapshot: Dict[str, Any],
        ticket_terms: Dict[str, Any]
    ) -> float:
        """
        Calculate Closing Line Value (CLV)
        
        Sign convention:
        - Positive CLV = we got better odds than closing line
        - Negative CLV = closing line was better
        """
        ticket_price = ticket_terms.get("price", prediction.get("price_american", -110))
        close_price = close_snapshot.get("price_american", -110)
        
        # Convert to decimal for comparison
        ticket_decimal = self._american_to_decimal(ticket_price)
        close_decimal = self._american_to_decimal(close_price)
        
        # CLV = (our_odds - close_odds) / close_odds * 100
        clv = ((ticket_decimal - close_decimal) / close_decimal) * 100.0
        
        return round(clv, 2)
    
    def _calculate_brier_score(
        self,
        prediction: Dict[str, Any],
        result_code: ResultCode
    ) -> Optional[float]:
        """
        Calculate Brier score
        
        Brier = (p - actual)^2
        Lower is better, 0 = perfect
        """
        if result_code == ResultCode.VOID or result_code == ResultCode.PUSH:
            return None
        
        # Get predicted probability
        p_win = prediction.get("p_win") or prediction.get("p_cover") or prediction.get("p_over")
        
        if p_win is None:
            return None
        
        # Actual outcome (1 for win, 0 for loss)
        actual = 1.0 if result_code == ResultCode.WIN else 0.0
        
        brier = (p_win - actual) ** 2
        
        return round(brier, 4)
    
    def _calculate_logloss(
        self,
        prediction: Dict[str, Any],
        result_code: ResultCode
    ) -> Optional[float]:
        """
        Calculate log loss
        
        LogLoss = -log(p) if win, -log(1-p) if loss
        Lower is better
        """
        if result_code == ResultCode.VOID or result_code == ResultCode.PUSH:
            return None
        
        p_win = prediction.get("p_win") or prediction.get("p_cover") or prediction.get("p_over")
        
        if p_win is None:
            return None
        
        # Clip probabilities to avoid log(0)
        p_win = max(0.001, min(0.999, p_win))
        
        if result_code == ResultCode.WIN:
            logloss = -math.log(p_win)
        else:
            logloss = -math.log(1 - p_win)
        
        return round(logloss, 4)
    
    def _american_to_decimal(self, american: int) -> float:
        """Convert American odds to decimal"""
        if american > 0:
            return (american / 100.0) + 1.0
        else:
            return (100.0 / abs(american)) + 1.0
    
    def get_grading_for_publish(
        self,
        publish_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get grading record for a published prediction"""
        return self.grading_collection.find_one({"publish_id": publish_id})
    
    def get_performance_summary(
        self,
        cohort_key: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get performance summary from grading records
        """
        query: Dict[str, Any] = {"bet_status": BetStatus.SETTLED.value}
        
        if cohort_key:
            query["cohort_tags.league"] = cohort_key
        
        if start_date or end_date:
            date_query: Dict[str, Any] = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["graded_at"] = date_query
        
        gradings = list(self.grading_collection.find(query))
        
        if not gradings:
            return {"error": "No graded predictions found"}
        
        wins = sum(1 for g in gradings if g.get("result_code") == ResultCode.WIN.value)
        losses = sum(1 for g in gradings if g.get("result_code") == ResultCode.LOSS.value)
        pushes = sum(1 for g in gradings if g.get("result_code") == ResultCode.PUSH.value)
        total = wins + losses + pushes
        
        total_units = sum(g.get("unit_return", 0) for g in gradings)
        
        avg_clv = sum(g.get("clv", 0) for g in gradings if g.get("clv") is not None) / max(1, len([g for g in gradings if g.get("clv") is not None]))
        
        brier_scores = [g.get("brier_component") for g in gradings if g.get("brier_component") is not None]
        avg_brier = sum(brier_scores) / len(brier_scores) if brier_scores else None
        
        return {
            "total_graded": total,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate": wins / max(1, wins + losses) * 100,
            "roi": (total_units / max(1, wins + losses)) * 100,
            "total_units": total_units,
            "avg_clv": round(avg_clv, 2),
            "avg_brier": round(avg_brier, 4) if avg_brier else None
        }


# Singleton instance
grading_service = GradingService()

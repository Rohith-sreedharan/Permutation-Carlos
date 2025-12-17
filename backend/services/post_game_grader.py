"""
Post-Game Grading Pipeline - Automated Model Performance Analysis

Automatically grades every finished game by:
1. Pulling pregame audit (model_total, vegas_total, rcl_passed)
2. Comparing against final result
3. Classifying variance type vs model fault
4. Storing grading record for weekly calibration

NO MANUAL INPUT REQUIRED - runs on cron every 30 minutes
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from db.mongo import db

logger = logging.getLogger(__name__)


# ===== CLASSIFICATION THRESHOLDS =====
BIG_MISS = 15       # 15+ points off = big miss
MEDIUM_MISS = 8     # 8-14 points off
NORMAL_VAR = 7      # ≤7 points off = normal variance


class PostGameGrader:
    """
    Automated post-game grading system
    Classifies model performance and variance patterns
    """
    
    def __init__(self):
        self.sim_audit_collection = db["sim_audit"]
        self.events_collection = db["events"]
        self.grade_log_collection = db["game_grade_log"]
    
    def grade_finished_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        """
        Grade a single finished game
        
        Returns:
            Grading record dict or None if cannot grade
        """
        try:
            # 1) Get pregame audit record
            audit = self._get_pregame_audit(game_id)
            if not audit:
                logger.warning(f"No pregame audit found for {game_id}")
                return None
            
            # 2) Get final result
            final = self._get_final_result(game_id)
            if not final:
                logger.warning(f"No final result found for {game_id}")
                return None
            
            # 3) Extract key metrics
            vegas_total = audit.get("vegas_total", audit.get("rcl_total", 0))
            model_total = audit.get("raw_total", audit.get("rcl_total", 0))  # Raw pre-RCL total
            rcl_passed = audit.get("rcl_passed", True)
            rcl_reason = audit.get("rcl_reason", "")
            
            final_total = final.get("total_points", 0)
            final_spread = final.get("spread", 0)
            
            if final_total == 0:
                logger.warning(f"Invalid final_total (0) for {game_id}")
                return None
            
            # 4) Compute deltas
            delta_model = abs(final_total - model_total)
            delta_vegas = abs(final_total - vegas_total)
            
            # 5) Classify outcome
            classification = self._classify_outcome(
                delta_model=delta_model,
                delta_vegas=delta_vegas,
                final_total=final_total,
                vegas_total=vegas_total,
                rcl_passed=rcl_passed
            )
            
            # 6) Build grading record
            grade_record = {
                "game_id": game_id,
                "event_id": final.get("event_id", game_id),
                
                # Pregame metrics
                "vegas_total_close": vegas_total,
                "model_total": model_total,
                "rcl_passed": rcl_passed,
                "rcl_reason": rcl_reason,
                
                # Final result
                "final_total": final_total,
                "final_spread": final_spread,
                "home_score": final.get("home_score", 0),
                "away_score": final.get("away_score", 0),
                
                # Deltas
                "delta_model": round(delta_model, 2),
                "delta_vegas": round(delta_vegas, 2),
                
                # Classification
                "variance_type": classification["variance_type"],
                "model_fault": classification["model_fault"],
                "confidence_retro": classification["confidence_retro"],
                "calibration_weight": classification["calibration_weight"],
                
                # Metadata
                "league": final.get("league", "unknown"),
                "sport_key": final.get("sport_key", "unknown"),
                "game_date": final.get("commence_time"),
                "graded_at": datetime.now(timezone.utc),
            }
            
            # 7) Store grading record
            self.grade_log_collection.update_one(
                {"game_id": game_id},
                {"$set": grade_record},
                upsert=True
            )
            
            logger.info(
                f"✅ Graded {game_id}: {classification['variance_type']} "
                f"(model_fault={classification['model_fault']}, "
                f"delta_model={delta_model:.1f}, delta_vegas={delta_vegas:.1f})"
            )
            
            return grade_record
            
        except Exception as e:
            logger.error(f"Failed to grade game {game_id}: {e}")
            return None
    
    def _classify_outcome(
        self,
        delta_model: float,
        delta_vegas: float,
        final_total: float,
        vegas_total: float,
        rcl_passed: bool
    ) -> Dict[str, Any]:
        """
        Classify outcome: variance vs model fault
        
        Returns:
            Dict with variance_type, model_fault, confidence_retro, calibration_weight
        """
        # Default values
        variance_type = "normal"
        model_fault = False
        confidence_retro = "moderate"
        calibration_weight = 1.0
        
        # SPECIAL CASE: RCL failed pregame → always model fault
        if not rcl_passed:
            return {
                "variance_type": "rcl_blocked_pre",
                "model_fault": True,
                "confidence_retro": "very_low",
                "calibration_weight": 1.5  # Strong correction
            }
        
        # CASE 1: Small miss (≤7 pts) → normal variance
        if delta_model <= NORMAL_VAR:
            variance_type = "normal"
            model_fault = False
            confidence_retro = "high"
            calibration_weight = 1.0
        
        # CASE 2: Medium miss (8-14 pts) → compare vs Vegas
        elif delta_model <= MEDIUM_MISS:
            if delta_model < delta_vegas:
                # Model closer than Vegas → variance, not fault
                variance_type = "variance_only"
                model_fault = False
                confidence_retro = "moderate"
                calibration_weight = 0.5
            else:
                # Vegas closer → mild model fault
                variance_type = "model_drift"
                model_fault = True
                confidence_retro = "low"
                calibration_weight = 0.75
        
        # CASE 3: Big miss (15+ pts) → check if extreme variance or model fault
        else:
            # Both model and Vegas wrong by a lot → extreme variance event
            if delta_model <= delta_vegas + 3:
                # Classify type of extreme variance
                if final_total > vegas_total + BIG_MISS:
                    variance_type = "upper_tail_scoring_burst"  # Spurs 132 type
                elif final_total < vegas_total - BIG_MISS:
                    variance_type = "lower_tail_brickfest"
                else:
                    variance_type = "high_variance_anomaly"
                
                model_fault = False
                confidence_retro = "moderate"
                calibration_weight = 0.25  # Low influence on calibration
            
            else:
                # Model significantly worse than Vegas → real model fault
                variance_type = "model_fault_heavy"
                model_fault = True
                confidence_retro = "very_low"
                calibration_weight = 1.5  # Stronger correction
        
        return {
            "variance_type": variance_type,
            "model_fault": model_fault,
            "confidence_retro": confidence_retro,
            "calibration_weight": calibration_weight
        }
    
    def _get_pregame_audit(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get pregame sim_audit record"""
        # Try to find by event_id
        audit = self.sim_audit_collection.find_one(
            {"event_id": game_id},
            sort=[("created_at", -1)]  # Get most recent if multiple
        )
        return audit
    
    def _get_final_result(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get final game result from events collection"""
        event = self.events_collection.find_one({"event_id": game_id})
        
        if not event:
            return None
        
        # Check if game is completed
        if event.get("status") != "completed":
            return None
        
        # Extract scores
        home_score = event.get("home_score", 0)
        away_score = event.get("away_score", 0)
        
        if home_score == 0 and away_score == 0:
            return None  # No valid scores
        
        total_points = home_score + away_score
        spread = home_score - away_score
        
        return {
            "event_id": game_id,
            "home_score": home_score,
            "away_score": away_score,
            "total_points": total_points,
            "spread": spread,
            "league": event.get("league"),
            "sport_key": event.get("sport_key"),
            "commence_time": event.get("commence_time"),
            "status": event.get("status")
        }
    
    def grade_all_finished_games(self, hours_back: int = 48) -> Dict[str, Any]:
        """
        Grade all finished games from the last N hours
        
        Args:
            hours_back: How many hours back to check (default: 48)
        
        Returns:
            Summary dict with counts
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        # Find all completed games
        completed_games = self.events_collection.find({
            "status": "completed",
            "commence_time": {"$gte": cutoff_time}
        })
        
        graded_count = 0
        skipped_count = 0
        error_count = 0
        
        for game in completed_games:
            game_id = game.get("event_id")
            
            # Check if already graded
            existing = self.grade_log_collection.find_one({"game_id": game_id})
            if existing:
                skipped_count += 1
                continue
            
            # Grade the game
            result = self.grade_finished_game(game_id)
            
            if result:
                graded_count += 1
            else:
                error_count += 1
        
        summary = {
            "graded": graded_count,
            "skipped": skipped_count,
            "errors": error_count,
            "total_processed": graded_count + skipped_count + error_count
        }
        
        logger.info(f"📊 Grading summary: {summary}")
        return summary
    
    def get_grading_stats(self, days_back: int = 7, sport_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Get grading statistics for the last N days
        
        Args:
            days_back: Number of days to look back
            sport_key: Optional filter by sport (e.g., 'basketball_nba')
        
        Returns:
            Stats dict with variance types, fault rates, etc.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        query = {"graded_at": {"$gte": cutoff_time}}
        if sport_key:
            query["sport_key"] = sport_key
        
        grades = list(self.grade_log_collection.find(query))
        
        if not grades:
            return {"error": "No graded games found"}
        
        total_games = len(grades)
        model_faults = sum(1 for g in grades if g.get("model_fault"))
        
        # Variance type distribution
        variance_types = {}
        for grade in grades:
            vtype = grade.get("variance_type", "unknown")
            variance_types[vtype] = variance_types.get(vtype, 0) + 1
        
        # Average deltas
        avg_delta_model = sum(g.get("delta_model", 0) for g in grades) / total_games
        avg_delta_vegas = sum(g.get("delta_vegas", 0) for g in grades) / total_games
        
        # Confidence distribution
        confidence_dist = {}
        for grade in grades:
            conf = grade.get("confidence_retro", "unknown")
            confidence_dist[conf] = confidence_dist.get(conf, 0) + 1
        
        return {
            "period": f"Last {days_back} days",
            "total_games": total_games,
            "model_faults": model_faults,
            "model_fault_rate": round(model_faults / total_games * 100, 1),
            "avg_delta_model": round(avg_delta_model, 2),
            "avg_delta_vegas": round(avg_delta_vegas, 2),
            "variance_types": variance_types,
            "confidence_distribution": confidence_dist,
            "model_beats_vegas": sum(
                1 for g in grades 
                if g.get("delta_model", 999) < g.get("delta_vegas", 999)
            ),
            "vegas_beats_model": sum(
                1 for g in grades 
                if g.get("delta_vegas", 999) < g.get("delta_model", 999)
            )
        }


# Singleton instance
post_game_grader = PostGameGrader()


# ===== WEEKLY CALIBRATION QUERY =====

def get_calibration_samples(days_back: int = 7) -> List[Dict[str, Any]]:
    """
    Get games for weekly calibration
    
    Only includes:
    - Games where model_fault = True (need correction)
    - OR small misses (≤10 pts) where model was close
    
    Returns:
        List of graded games with calibration_weight
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    grades = list(db["game_grade_log"].find({
        "graded_at": {"$gte": cutoff_time},
        "$or": [
            {"model_fault": True},
            {"delta_model": {"$lte": 10}}
        ]
    }))
    
    logger.info(f"📊 Found {len(grades)} games for calibration from last {days_back} days")
    
    return grades


def apply_weekly_calibration():
    """
    Weekly calibration job - adjusts model parameters based on graded games
    
    Uses calibration_weight to determine influence:
    - Normal variance (weight=1.0): full influence
    - Mild drift (weight=0.75): moderate influence
    - High variance (weight=0.25): minimal influence
    - Model fault (weight=1.5): stronger correction
    """
    samples = get_calibration_samples(days_back=7)
    
    if len(samples) < 10:
        logger.warning("Not enough samples for calibration (need 10+)")
        return
    
    # Group by sport/league for sport-specific calibration
    by_sport = {}
    for sample in samples:
        sport_key = sample.get("sport_key", "unknown")
        if sport_key not in by_sport:
            by_sport[sport_key] = []
        by_sport[sport_key].append(sample)
    
    calibration_results = {}
    
    for sport_key, sport_samples in by_sport.items():
        if len(sport_samples) < 5:
            continue  # Need minimum samples per sport
        
        # Calculate weighted average error
        weighted_errors = []
        weights = []
        
        for sample in sport_samples:
            error = sample.get("delta_model", 0)
            weight = sample.get("calibration_weight", 1.0)
            weighted_errors.append(error * weight)
            weights.append(weight)
        
        avg_weighted_error = sum(weighted_errors) / sum(weights)
        
        # Determine if systematic bias exists
        bias_direction = "over" if avg_weighted_error > 5 else "under" if avg_weighted_error < -5 else "none"
        
        calibration_results[sport_key] = {
            "sample_count": len(sport_samples),
            "avg_weighted_error": round(avg_weighted_error, 2),
            "bias_direction": bias_direction,
            "action": "adjust_pace_multiplier" if abs(avg_weighted_error) > 5 else "no_action"
        }
        
        logger.info(
            f"📊 {sport_key}: {len(sport_samples)} samples, "
            f"avg error={avg_weighted_error:.2f}, bias={bias_direction}"
        )
    
    # Store calibration results
    db["calibration_log"].insert_one({
        "run_at": datetime.now(timezone.utc),
        "results": calibration_results,
        "total_samples": len(samples)
    })
    
    return calibration_results

"""
Model Evaluation & Metrics System
Tracks Brier Score, Log Loss, CLV, and feeds metrics back for continuous recalibration
"""
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from db.mongo import db
from services.logger import log_stage


class ModelEvaluationEngine:
    """
    Advanced Model Evaluation Engine
    
    Metrics Tracked:
    1. CLV (Closing Line Value) - Are we beating the closing line?
    2. Brier Score - Calibration quality (0 = perfect, 1 = worst)
    3. Log Loss - Probabilistic accuracy
    4. ROI - Return on investment
    5. Win Rate - Simple hit rate
    
    These metrics feed back into the simulation engine for continuous improvement
    """
    
    def __init__(self):
        self.lookback_days = 30  # Default evaluation window
    
    def calculate_brier_score(self, picks: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate Brier Score for a set of picks
        
        Brier Score = (1/n) * Σ(predicted_prob - actual_outcome)²
        
        Lower is better (0 = perfect, 1 = worst)
        
        Example:
        - Predicted 70% win probability, team won → (0.7 - 1.0)² = 0.09
        - Predicted 60% win probability, team lost → (0.6 - 0.0)² = 0.36
        """
        if not picks:
            return None
        
        total_score = 0.0
        valid_picks = 0
        
        for pick in picks:
            outcome = pick.get("outcome")
            confidence = pick.get("confidence")
            
            if not outcome or not confidence:
                continue
            
            # Convert outcome to binary (1 = win, 0 = loss)
            actual = 1.0 if outcome == "win" else 0.0
            
            # Calculate squared error
            error_squared = (confidence - actual) ** 2
            total_score += error_squared
            valid_picks += 1
        
        if valid_picks == 0:
            return None
        
        brier_score = total_score / valid_picks
        return round(brier_score, 4)
    
    def calculate_log_loss(self, picks: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate Log Loss (Cross-Entropy Loss)
        
        Log Loss = -(1/n) * Σ[y*log(p) + (1-y)*log(1-p)]
        
        Lower is better (0 = perfect)
        
        Penalizes confident incorrect predictions heavily
        """
        if not picks:
            return None
        
        total_loss = 0.0
        valid_picks = 0
        
        for pick in picks:
            outcome = pick.get("outcome")
            confidence = pick.get("confidence")
            
            if not outcome or not confidence:
                continue
            
            # Convert outcome to binary
            actual = 1.0 if outcome == "win" else 0.0
            
            # Clamp probability to avoid log(0)
            p = max(0.0001, min(0.9999, confidence))
            
            # Calculate log loss
            if actual == 1.0:
                loss = -math.log(p)
            else:
                loss = -math.log(1 - p)
            
            total_loss += loss
            valid_picks += 1
        
        if valid_picks == 0:
            return None
        
        log_loss = total_loss / valid_picks
        return round(log_loss, 4)
    
    def calculate_average_clv(self, picks: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate Average CLV (Closing Line Value)
        
        CLV% = (closing_odds - opening_odds) / opening_odds * 100
        
        Positive CLV = beating the closing line (good!)
        Negative CLV = losing to the closing line (bad!)
        """
        if not picks:
            return None
        
        total_clv = 0.0
        valid_picks = 0
        
        for pick in picks:
            clv_pct = pick.get("clv_pct")
            
            if clv_pct is not None:
                total_clv += clv_pct
                valid_picks += 1
        
        if valid_picks == 0:
            return None
        
        avg_clv = total_clv / valid_picks
        return round(avg_clv, 2)
    
    def calculate_roi(self, picks: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        """
        Calculate ROI metrics
        
        ROI = (Total Profit / Total Staked) * 100
        """
        if not picks:
            return None
        
        total_staked = 0.0
        total_profit = 0.0
        wins = 0
        losses = 0
        
        for pick in picks:
            outcome = pick.get("outcome")
            stake = pick.get("stake_units", 1.0)
            odds = pick.get("market_decimal", 2.0)
            
            if not outcome:
                continue
            
            total_staked += stake
            
            if outcome == "win":
                profit = stake * (odds - 1.0)
                total_profit += profit
                wins += 1
            elif outcome == "loss":
                total_profit -= stake
                losses += 1
        
        if total_staked == 0:
            return None
        
        roi_pct = (total_profit / total_staked) * 100
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        
        return {
            "roi_pct": round(roi_pct, 2),
            "total_profit": round(total_profit, 2),
            "total_staked": round(total_staked, 2),
            "win_rate": round(win_rate, 2),
            "wins": wins,
            "losses": losses
        }
    
    def generate_performance_report(
        self,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report
        
        This is the data that feeds back into the reflection loop
        """
        if not days:
            days = self.lookback_days
        
        # Query settled picks from last N days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        picks = list(db["ai_picks"].find({
            "settled_at": {"$gte": cutoff_date.isoformat()},
            "outcome": {"$in": ["win", "loss", "push"]}
        }))
        
        # Filter out pushes for most metrics
        picks_no_push = [p for p in picks if p.get("outcome") != "push"]
        
        # Calculate all metrics
        brier_score = self.calculate_brier_score(picks_no_push)
        log_loss = self.calculate_log_loss(picks_no_push)
        avg_clv = self.calculate_average_clv(picks)
        roi_metrics = self.calculate_roi(picks)
        
        # Calculate metric by market type
        market_breakdown = {}
        for market in ["h2h", "spreads", "totals"]:
            market_picks = [p for p in picks if p.get("market") == market]
            if market_picks:
                market_breakdown[market] = {
                    "brier_score": self.calculate_brier_score(
                        [p for p in market_picks if p.get("outcome") != "push"]
                    ),
                    "avg_clv": self.calculate_average_clv(market_picks),
                    "roi": self.calculate_roi(market_picks)
                }
        
        report = {
            "report_id": f"perf_report_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "period_days": days,
            "total_picks": len(picks),
            "brier_score": brier_score,
            "log_loss": log_loss,
            "avg_clv": avg_clv,
            "roi_metrics": roi_metrics,
            "market_breakdown": market_breakdown,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store report
        db["performance_reports"].insert_one(report)
        
        log_stage(
            "model_evaluation",
            "performance_report_generated",
            input_payload={"days": days, "picks_analyzed": len(picks)},
            output_payload={
                "brier_score": brier_score,
                "avg_clv": avg_clv,
                "roi_pct": roi_metrics.get("roi_pct") if roi_metrics else None
            }
        )
        
        return report
    
    def generate_recalibration_recommendations(
        self,
        performance_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate parameter adjustment recommendations based on performance
        
        This feeds the reflection loop - automatically suggests config changes
        """
        recommendations = {
            "parameter_adjustments": [],
            "reasoning": []
        }
        
        brier_score = performance_report.get("brier_score")
        avg_clv = performance_report.get("avg_clv")
        roi_metrics = performance_report.get("roi_metrics", {})
        roi_pct = roi_metrics.get("roi_pct", 0)
        
        # Rule 1: High Brier Score = Poor calibration
        if brier_score and brier_score > 0.25:
            recommendations["parameter_adjustments"].append({
                "parameter": "min_confidence",
                "current": 0.45,
                "recommended": 0.60,
                "change": +0.15
            })
            recommendations["reasoning"].append(
                f"Brier Score {brier_score:.3f} indicates poor calibration. "
                "Increase confidence threshold to filter uncertain picks."
            )
        
        # Rule 2: Negative CLV = Losing to closing line
        if avg_clv and avg_clv < -2.0:
            recommendations["parameter_adjustments"].append({
                "parameter": "min_edge_threshold",
                "current": 0.05,
                "recommended": 0.08,
                "change": +0.03
            })
            recommendations["reasoning"].append(
                f"Average CLV {avg_clv:.2f}% indicates we're getting middled. "
                "Increase edge threshold to require stronger signals."
            )
        
        # Rule 3: Positive CLV but negative ROI = Good line detection, bad picks
        if avg_clv and avg_clv > 2.0 and roi_pct < 0:
            recommendations["parameter_adjustments"].append({
                "parameter": "sharp_consensus_weight",
                "current": 0.3,
                "recommended": 0.5,
                "change": +0.2
            })
            recommendations["reasoning"].append(
                f"Positive CLV {avg_clv:.2f}% but negative ROI {roi_pct:.2f}%. "
                "Increase community consensus weight for better pick selection."
            )
        
        # Rule 4: Great performance = Relax thresholds slightly
        if brier_score and brier_score < 0.15 and avg_clv and avg_clv > 5.0 and roi_pct > 10:
            recommendations["parameter_adjustments"].append({
                "parameter": "min_edge_threshold",
                "current": 0.08,
                "recommended": 0.06,
                "change": -0.02
            })
            recommendations["reasoning"].append(
                f"Excellent performance (Brier: {brier_score:.3f}, CLV: {avg_clv:.2f}%, ROI: {roi_pct:.2f}%). "
                "Can afford to slightly relax edge threshold for more volume."
            )
        
        # Rule 5: Low win rate but positive CLV = Stake sizing issue
        win_rate = roi_metrics.get("win_rate", 0)
        if win_rate < 48 and avg_clv and avg_clv > 3.0:
            recommendations["parameter_adjustments"].append({
                "parameter": "kelly_fraction",
                "current": 0.25,
                "recommended": 0.20,
                "change": -0.05
            })
            recommendations["reasoning"].append(
                f"Win rate {win_rate:.1f}% below expectations despite positive CLV. "
                "Reduce Kelly fraction for more conservative sizing."
            )
        
        # Store recommendations
        recommendation_doc = {
            "recommendation_id": f"recal_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "based_on_report": performance_report.get("report_id"),
            "recommendations": recommendations,
            "status": "pending_review",
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        db["recalibration_recommendations"].insert_one(recommendation_doc)
        
        log_stage(
            "model_evaluation",
            "recalibration_recommendations_generated",
            input_payload={"report_id": performance_report.get("report_id")},
            output_payload={"adjustments_count": len(recommendations["parameter_adjustments"])}
        )
        
        return recommendations
    
    def apply_recalibration(
        self,
        recommendation_id: str,
        auto_apply: bool = False
    ) -> Dict[str, Any]:
        """
        Apply recalibration recommendations to model config
        
        If auto_apply=True, updates immediately
        If auto_apply=False, returns preview for human approval
        """
        recommendation = db["recalibration_recommendations"].find_one({
            "recommendation_id": recommendation_id
        })
        
        if not recommendation:
            return {"status": "error", "message": "Recommendation not found"}
        
        adjustments = recommendation.get("recommendations", {}).get("parameter_adjustments", [])
        
        if auto_apply:
            # Update model config file
            import json
            config_path = "/Users/rohithaditya/Downloads/Permutation-Carlos/backend/core/model_config.json"
            
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                
                for adj in adjustments:
                    param = adj.get("parameter")
                    new_value = adj.get("recommended")
                    config[param] = new_value
                
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                
                # Mark as applied
                db["recalibration_recommendations"].update_one(
                    {"recommendation_id": recommendation_id},
                    {
                        "$set": {
                            "status": "applied",
                            "applied_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                log_stage(
                    "model_evaluation",
                    "recalibration_applied",
                    input_payload={"recommendation_id": recommendation_id},
                    output_payload={"adjustments": adjustments}
                )
                
                return {
                    "status": "applied",
                    "adjustments": adjustments,
                    "message": "Config updated successfully"
                }
            
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        else:
            # Return preview
            return {
                "status": "preview",
                "adjustments": adjustments,
                "message": "Review and approve to apply changes"
            }


# Singleton instance
model_evaluation_engine = ModelEvaluationEngine()

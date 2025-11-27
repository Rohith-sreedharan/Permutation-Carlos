"""
Module 7: Reflection Loop (Self-Improving AI)
Agentic component that computes ROI/CLV/Brier/LogLoss and suggests model improvements
Now integrated with advanced model evaluation engine
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import json
from db.mongo import db
from services.logger import log_stage


class ReflectionLoop:
    """
    The critical self-improving component of Omni Edge AI
    
    Responsibilities:
    1. Analyze user_action events to compute actual ROI/CLV
    2. Integrate with ModelEvaluationEngine for Brier Score and Log Loss
    3. Compare predicted edge vs actual outcomes
    4. Programmatically suggest JSON parameter patches
    5. Auto-apply or preview recalibration recommendations
    6. Self-improve model filters and thresholds weekly
    
    NEW: Enhanced with Brier Score, Log Loss, and automated recalibration
    """
    
    def __init__(self):
        self.model_config_path = "/Users/rohithaditya/Downloads/Permutation-Carlos/backend/core/model_config.json"
    
    def run_weekly_reflection(self, auto_apply: bool = False) -> Dict[str, Any]:
        """
        Main entry point for weekly reflection loop
        
        This is what runs every Sunday @ 2 AM
        
        NEW: Now uses ModelEvaluationEngine for comprehensive analysis
        """
        from core.model_evaluation import model_evaluation_engine
        
        log_stage(
            "reflection_loop",
            "weekly_reflection_started",
            input_payload={"auto_apply": auto_apply},
            output_payload={}
        )
        
        # Step 1: Generate comprehensive performance report
        performance_report = model_evaluation_engine.generate_performance_report(days=7)
        
        # Step 2: Generate recalibration recommendations
        recommendations = model_evaluation_engine.generate_recalibration_recommendations(
            performance_report
        )
        
        # Step 3: Apply or preview recommendations
        recommendation_id = f"recal_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        
        if auto_apply:
            apply_result = model_evaluation_engine.apply_recalibration(
                recommendation_id,
                auto_apply=True
            )
        else:
            apply_result = {
                "status": "preview",
                "message": "Review recommendations before applying"
            }
        
        log_stage(
            "reflection_loop",
            "weekly_reflection_completed",
            input_payload={"auto_apply": auto_apply},
            output_payload={
                "brier_score": performance_report.get("brier_score"),
                "avg_clv": performance_report.get("avg_clv"),
                "adjustments_count": len(recommendations.get("parameter_adjustments", [])),
                "applied": auto_apply
            }
        )
        
        return {
            "status": "completed",
            "performance_report": performance_report,
            "recommendations": recommendations,
            "apply_result": apply_result,
            "run_at": datetime.now(timezone.utc).isoformat()
        }
    
    def compute_pick_performance(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze pick performance over last N days
        Returns ROI, CLV, and win rate metrics
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        # Get all settled picks from the period
        picks = list(db["ai_picks"].find({
            "created_at": {"$gte": cutoff_date},
            "outcome": {"$in": ["win", "loss"]}  # Exclude push/void
        }))
        
        if not picks:
            return {
                "total_picks": 0,
                "roi": 0.0,
                "avg_clv": 0.0,
                "win_rate": 0.0
            }
        
        # Calculate metrics
        total_picks = len(picks)
        wins = sum(1 for p in picks if p["outcome"] == "win")
        win_rate = wins / total_picks
        
        # ROI calculation (assumes 1 unit stakes)
        total_profit = sum(
            (p.get("market_decimal", 2.0) - 1.0) if p["outcome"] == "win" else -1.0
            for p in picks
        )
        roi = (total_profit / total_picks) * 100
        
        # CLV calculation (only for picks with closing line data)
        picks_with_clv = [p for p in picks if p.get("clv_pct") is not None]
        avg_clv = sum(p["clv_pct"] for p in picks_with_clv) / len(picks_with_clv) if picks_with_clv else 0.0
        
        return {
            "total_picks": total_picks,
            "wins": wins,
            "losses": total_picks - wins,
            "win_rate": round(win_rate * 100, 2),
            "roi": round(roi, 2),
            "avg_clv": round(avg_clv, 2),
            "picks_with_clv": len(picks_with_clv)
        }
    
    def analyze_user_actions(self, days: int = 7) -> Dict[str, Any]:
        """
        Analyze how users interact with picks
        What do they tail/fade/save?
        """
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        actions = list(db["user_actions"].find({
            "created_at": {"$gte": cutoff_date}
        }))
        
        if not actions:
            return {
                "total_actions": 0,
                "tailed": 0,
                "faded": 0,
                "saved": 0
            }
        
        # Count action types
        action_counts = {
            "TAILED": sum(1 for a in actions if a["action"] == "TAILED"),
            "FADED": sum(1 for a in actions if a["action"] == "FADED"),
            "SAVE": sum(1 for a in actions if a["action"] == "SAVE"),
            "SELF_SUBMIT": sum(1 for a in actions if a["action"] == "SELF_SUBMIT")
        }
        
        # Analyze which picks get most tails (high confidence validation)
        tailed_picks = [a["pick_id"] for a in actions if a["action"] == "TAILED"]
        pick_popularity = {}
        for pick_id in tailed_picks:
            pick_popularity[pick_id] = pick_popularity.get(pick_id, 0) + 1
        
        # Get top 5 most tailed picks
        top_picks = sorted(pick_popularity.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_actions": len(actions),
            "action_counts": action_counts,
            "top_tailed_picks": [
                {"pick_id": pick_id, "tail_count": count}
                for pick_id, count in top_picks
            ]
        }
    
    def generate_parameter_patches(self, performance: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        The agentic core: Generate JSON patches to improve model
        
        This is what makes Module 7 "self-improving"
        Based on performance data, suggest concrete parameter changes
        """
        patches = []
        
        # Rule 1: If ROI < 5%, increase minimum edge threshold
        if performance["roi"] < 5.0:
            patches.append({
                "param": "min_edge_threshold",
                "current": 0.05,
                "suggested": 0.08,
                "rationale": f"ROI at {performance['roi']}% is below target. Increase edge threshold to filter low-quality picks."
            })
        
        # Rule 2: If CLV < 2%, the model is not beating closing lines
        if performance["avg_clv"] < 2.0:
            patches.append({
                "param": "sharp_consensus_weight",
                "current": 0.3,
                "suggested": 0.5,
                "rationale": f"CLV at {performance['avg_clv']}% indicates poor timing. Increase weight on sharp consensus."
            })
        
        # Rule 3: If win rate < 53% (breakeven for -110 odds), tighten confidence threshold
        if performance["win_rate"] < 53.0:
            patches.append({
                "param": "min_confidence",
                "current": 0.45,
                "suggested": 0.60,
                "rationale": f"Win rate at {performance['win_rate']}% is below breakeven. Increase minimum confidence."
            })
        
        # Rule 4: If ROI > 10%, we can be more aggressive (loosen thresholds)
        if performance["roi"] > 10.0:
            patches.append({
                "param": "min_edge_threshold",
                "current": 0.08,
                "suggested": 0.05,
                "rationale": f"ROI at {performance['roi']}% is strong. Can afford to loosen edge threshold for volume."
            })
        
        # Rule 5: If CLV > 3%, timing is good - can increase pick volume
        if performance["avg_clv"] > 3.0:
            patches.append({
                "param": "max_picks_per_day",
                "current": 10,
                "suggested": 15,
                "rationale": f"CLV at {performance['avg_clv']}% shows excellent line value. Increase pick volume."
            })
        
        return patches
    
    def apply_patches(self, patches: List[Dict[str, Any]], auto_apply: bool = False) -> Dict[str, Any]:
        """
        Apply parameter patches to model config
        
        If auto_apply=True, writes changes to disk
        If auto_apply=False, returns preview for human approval
        """
        if not patches:
            return {
                "status": "no_changes",
                "message": "Performance within acceptable ranges"
            }
        
        # Load current config
        try:
            with open(self.model_config_path, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            config = self._get_default_config()
        
        # Preview changes
        changes = []
        for patch in patches:
            param = patch["param"]
            current = config.get(param, patch["current"])
            suggested = patch["suggested"]
            
            changes.append({
                "param": param,
                "current": current,
                "suggested": suggested,
                "rationale": patch["rationale"]
            })
            
            if auto_apply:
                config[param] = suggested
        
        # Write to disk if auto_apply
        if auto_apply:
            with open(self.model_config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            log_stage(
                "reflection_loop",
                "config_updated",
                input_payload={"patches": len(patches)},
                output_payload={"changes": changes}
            )
        
        return {
            "status": "success" if auto_apply else "preview",
            "changes": changes,
            "auto_applied": auto_apply
        }
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Default model configuration"""
        return {
            "min_edge_threshold": 0.05,  # 5% minimum edge
            "min_confidence": 0.45,       # 45% minimum confidence
            "sharp_consensus_weight": 0.3,  # 30% weight on community
            "max_picks_per_day": 10,
            "kelly_fraction": 0.25,        # Quarter Kelly
            "markets": ["h2h", "spreads", "totals"]
        }


# Singleton instance
reflection_loop = ReflectionLoop()

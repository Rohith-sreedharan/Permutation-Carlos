"""
Post-Game Recap Generator
Auto-generates recaps after games end for feedback loop

Per spec Section 10: Auto recap per game with HIT/MISS tracking
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from db.mongo import db
import logging

logger = logging.getLogger(__name__)


class PostGameRecap:
    """
    Generate comprehensive post-game analysis comparing predictions to actual results
    
    This feeds the feedback loop and helps identify which modules are performing well
    """
    
    @staticmethod
    def generate_recap(
        event_id: str,
        game_data: Dict[str, Any],
        predictions: Dict[str, Any],
        actual_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate full post-game recap
        
        Args:
            event_id: Game identifier
            game_data: Original game data (teams, context)
            predictions: All predictions made (side, total, 1H, props)
            actual_results: Actual game results
            
        Returns:
            Comprehensive recap with HIT/MISS for all predictions
        """
        try:
            recap = {
                "event_id": event_id,
                "generated_at": datetime.now(timezone.utc),
                "game_info": {
                    "home_team": game_data.get("home_team", "Unknown"),
                    "away_team": game_data.get("away_team", "Unknown"),
                    "sport": game_data.get("sport", "Unknown"),
                    "final_score": {
                        "home": actual_results.get("home_score"),
                        "away": actual_results.get("away_score")
                    },
                    "actual_total": actual_results.get("total"),
                    "actual_margin": actual_results.get("margin")
                },
                "simulation_metadata": {
                    "sim_tier": predictions.get("sim_count", 10000),
                    "confidence_score": predictions.get("confidence", 0),
                    "volatility_flag": predictions.get("volatility", "UNKNOWN")
                },
                "predictions": {},
                "summary": {},
                "notes": []
            }
            
            # Analyze Side (Moneyline) Prediction
            if "side_prediction" in predictions:
                side_pred = predictions["side_prediction"]
                winner = actual_results.get("winner")  # "home" or "away"
                predicted_winner = side_pred.get("lean")  # "home" or "away"
                
                side_hit = (predicted_winner == winner)
                confidence = side_pred.get("confidence", 0)
                prob = side_pred.get("probability", 0.5)
                
                recap["predictions"]["side"] = {
                    "predicted_winner": predicted_winner,
                    "probability": f"{prob * 100:.1f}%",
                    "actual_winner": winner,
                    "result": "HIT" if side_hit else "MISS",
                    "confidence": f"{confidence}/100"
                }
                
                # Add context note
                if confidence < 60:
                    recap["notes"].append(f"Side prediction had low confidence ({confidence}/100) - model labeled as uncertain")
                elif side_hit and confidence >= 70:
                    recap["notes"].append(f"✅ High-confidence side prediction ({confidence}/100) hit successfully")
            
            # Analyze Total (Over/Under) Prediction
            if "total_prediction" in predictions:
                total_pred = predictions["total_prediction"]
                actual_total = actual_results.get("total")
                book_line = total_pred.get("book_line")
                lean = total_pred.get("lean")  # "over" or "under"
                
                if actual_total and book_line:
                    if lean == "over":
                        total_hit = (actual_total > book_line)
                    else:  # under
                        total_hit = (actual_total < book_line)
                    
                    prob = total_pred.get("probability", 0.5)
                    projected = total_pred.get("projected_total")
                    
                    recap["predictions"]["total"] = {
                        "lean": lean.upper(),
                        "book_line": book_line,
                        "projected_total": projected,
                        "actual_total": actual_total,
                        "probability": f"{prob * 100:.1f}%",
                        "result": "HIT" if total_hit else "MISS",
                        "margin": abs(actual_total - book_line)
                    }
                    
                    # Accuracy note
                    if projected:
                        projection_error = abs(projected - actual_total)
                        if projection_error <= 3.0:
                            recap["notes"].append(f"✅ Total projection highly accurate (within {projection_error:.1f} points)")
                        elif projection_error > 10.0:
                            recap["notes"].append(f"⚠️ Total projection missed by {projection_error:.1f} points - variance exceeded expectations")
            
            # Analyze 1H Total Prediction
            if "h1_prediction" in predictions and "h1_total" in actual_results:
                h1_pred = predictions["h1_prediction"]
                actual_h1 = actual_results.get("h1_total")
                h1_line = h1_pred.get("book_line")
                h1_lean = h1_pred.get("lean")
                
                if actual_h1 and h1_line:
                    if h1_lean == "over":
                        h1_hit = (actual_h1 > h1_line)
                    else:
                        h1_hit = (actual_h1 < h1_line)
                    
                    h1_projected = h1_pred.get("projected_h1_total")
                    
                    recap["predictions"]["first_half"] = {
                        "lean": h1_lean.upper() if h1_lean != "neutral" else "NO LEAN",
                        "book_line": h1_line,
                        "projected_h1_total": h1_projected,
                        "actual_h1_total": actual_h1,
                        "result": "HIT" if h1_hit else "MISS" if h1_lean != "neutral" else "N/A"
                    }
                    
                    if h1_lean == "neutral":
                        recap["notes"].append("1H labeled as neutral/coin-flip - no strong lean")
            
            # Analyze Props (if any)
            if "props" in predictions:
                props_results = []
                for prop in predictions["props"]:
                    prop_id = prop.get("prop_id")
                    actual_prop_result = actual_results.get("props", {}).get(prop_id)
                    
                    if actual_prop_result:
                        prop_hit = (actual_prop_result["result"] == "hit")
                        props_results.append({
                            "player": prop.get("player"),
                            "prop_type": prop.get("prop_type"),
                            "line": prop.get("line"),
                            "actual": actual_prop_result.get("actual_value"),
                            "result": "HIT" if prop_hit else "MISS"
                        })
                
                if props_results:
                    recap["predictions"]["props"] = props_results
            
            # Generate Summary
            recap["summary"] = PostGameRecap._generate_summary(recap)
            
            # Store recap in database
            db.post_game_recaps.insert_one(recap)
            logger.info(f"✅ Post-game recap generated: {event_id}")
            
            return recap
            
        except Exception as e:
            logger.error(f"❌ Recap generation failed: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def _generate_summary(recap: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics from recap"""
        predictions = recap.get("predictions", {})
        
        total_predictions = 0
        hits = 0
        
        for pred_type in ["side", "total", "first_half"]:
            if pred_type in predictions:
                pred = predictions[pred_type]
                if pred.get("result") in ["HIT", "MISS"]:
                    total_predictions += 1
                    if pred["result"] == "HIT":
                        hits += 1
        
        # Props
        if "props" in predictions:
            for prop in predictions["props"]:
                total_predictions += 1
                if prop["result"] == "HIT":
                    hits += 1
        
        hit_rate = (hits / total_predictions * 100) if total_predictions > 0 else 0
        
        confidence = recap["simulation_metadata"].get("confidence_score", 0)
        volatility = recap["simulation_metadata"].get("volatility_flag", "UNKNOWN")
        
        # Confidence categorization
        if confidence >= 70:
            confidence_label = "High"
        elif confidence >= 40:
            confidence_label = "Medium"
        else:
            confidence_label = "Low"
        
        summary = {
            "total_predictions": total_predictions,
            "hits": hits,
            "misses": total_predictions - hits,
            "hit_rate": round(hit_rate, 1),
            "confidence_label": confidence_label,
            "confidence_score": confidence,
            "volatility": volatility,
            "performance_grade": PostGameRecap._get_performance_grade(hit_rate, confidence)
        }
        
        return summary
    
    @staticmethod
    def _get_performance_grade(hit_rate: float, confidence: int) -> str:
        """
        Grade model performance considering hit rate AND confidence calibration
        
        A high-confidence prediction that misses is worse than a low-confidence miss
        """
        if hit_rate >= 75:
            return "A" if confidence >= 60 else "A-"
        elif hit_rate >= 60:
            return "B+" if confidence >= 60 else "B"
        elif hit_rate >= 50:
            return "B-" if confidence < 60 else "C+"  # Low confidence saves the grade
        elif hit_rate >= 40:
            return "C" if confidence < 60 else "D"  # High confidence on misses = bad
        else:
            return "D" if confidence < 60 else "F"  # High confidence + low accuracy = worst
    
    @staticmethod
    def get_recent_recaps(
        days: int = 7,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent post-game recaps for analysis"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            recaps = list(db.post_game_recaps.find({
                "generated_at": {"$gte": cutoff_date}
            }).sort("generated_at", -1).limit(limit))
            
            return recaps
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch recaps: {e}")
            return []
    
    @staticmethod
    def get_performance_trends(days: int = 30) -> Dict[str, Any]:
        """
        Analyze performance trends across multiple games
        
        Identifies which prediction types are performing well/poorly
        """
        try:
            recaps = PostGameRecap.get_recent_recaps(days=days, limit=500)
            
            if not recaps:
                return {"error": "No recaps found"}
            
            # Aggregate statistics
            side_stats = {"total": 0, "hits": 0}
            total_stats = {"total": 0, "hits": 0}
            h1_stats = {"total": 0, "hits": 0}
            
            high_confidence_stats = {"total": 0, "hits": 0}
            low_confidence_stats = {"total": 0, "hits": 0}
            
            for recap in recaps:
                preds = recap.get("predictions", {})
                conf = recap.get("simulation_metadata", {}).get("confidence_score", 0)
                
                # Side predictions
                if "side" in preds and preds["side"].get("result") in ["HIT", "MISS"]:
                    side_stats["total"] += 1
                    if preds["side"]["result"] == "HIT":
                        side_stats["hits"] += 1
                
                # Total predictions
                if "total" in preds and preds["total"].get("result") in ["HIT", "MISS"]:
                    total_stats["total"] += 1
                    if preds["total"]["result"] == "HIT":
                        total_stats["hits"] += 1
                
                # 1H predictions
                if "first_half" in preds and preds["first_half"].get("result") in ["HIT", "MISS"]:
                    h1_stats["total"] += 1
                    if preds["first_half"]["result"] == "HIT":
                        h1_stats["hits"] += 1
                
                # Confidence stratification
                if conf >= 60:
                    high_confidence_stats["total"] += 1
                    summary_hits = recap.get("summary", {}).get("hits", 0)
                    summary_total = recap.get("summary", {}).get("total_predictions", 1)
                    if summary_total > 0 and summary_hits / summary_total >= 0.5:
                        high_confidence_stats["hits"] += 1
                elif conf > 0:
                    low_confidence_stats["total"] += 1
                    summary_hits = recap.get("summary", {}).get("hits", 0)
                    summary_total = recap.get("summary", {}).get("total_predictions", 1)
                    if summary_total > 0 and summary_hits / summary_total >= 0.5:
                        low_confidence_stats["hits"] += 1
            
            return {
                "period_days": days,
                "total_games": len(recaps),
                "by_prediction_type": {
                    "side": {
                        "count": side_stats["total"],
                        "hit_rate": round((side_stats["hits"] / side_stats["total"] * 100), 1) if side_stats["total"] > 0 else 0
                    },
                    "total": {
                        "count": total_stats["total"],
                        "hit_rate": round((total_stats["hits"] / total_stats["total"] * 100), 1) if total_stats["total"] > 0 else 0
                    },
                    "first_half": {
                        "count": h1_stats["total"],
                        "hit_rate": round((h1_stats["hits"] / h1_stats["total"] * 100), 1) if h1_stats["total"] > 0 else 0
                    }
                },
                "by_confidence": {
                    "high_confidence_60_plus": {
                        "count": high_confidence_stats["total"],
                        "success_rate": round((high_confidence_stats["hits"] / high_confidence_stats["total"] * 100), 1) if high_confidence_stats["total"] > 0 else 0
                    },
                    "low_confidence": {
                        "count": low_confidence_stats["total"],
                        "success_rate": round((low_confidence_stats["hits"] / low_confidence_stats["total"] * 100), 1) if low_confidence_stats["total"] > 0 else 0
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Performance trends analysis failed: {e}")
            return {"error": str(e)}

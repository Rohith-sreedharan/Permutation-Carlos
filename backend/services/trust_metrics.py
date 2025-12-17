"""
Trust Metrics Service
=====================

Calculates model performance metrics for the Trust Loop including:
- Weekly calibration analysis
- Regime effectiveness tracking
- Confidence bucket validation
- Safety engine performance metrics

Metrics Tracked:
- 7-Day Accuracy (Win Rate)
- 30-Day ROI (Units Won)
- Brier Score (Calibration Quality)
- Confidence Calibration by Bucket
- Sport-Specific Accuracy
- Environment-Specific Performance (Regular Season vs Championship)
- Regime Adjustment Effectiveness
- Safety Engine Suppression Accuracy
- Last 10-Game Performance
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from db.mongo import db
from utils.timezone import now_utc
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENHANCED TRUST METRICS WITH CALIBRATION & REGIME TRACKING
# ============================================================================

class TrustMetricsService:
    """
    Aggregates historical prediction performance into trust metrics.
    
    Runs daily at 4 AM EST to calculate:
    - Overall accuracy
    - ROI by sport
    - Brier score trends
    - Confidence calibration
    """
    
    def __init__(self):
        self.db = db
    
    async def calculate_all_metrics(self) -> Dict:
        """
        Calculate comprehensive trust metrics.
        
        Returns:
            {
                "overall": {
                    "7day_accuracy": 65.2,
                    "30day_roi": 8.3,
                    "brier_score": 0.18,
                    "total_predictions": 127
                },
                "by_sport": {...},
                "confidence_calibration": {...},
                "recent_performance": [...]
            }
        """
        metrics = {}
        
        # Overall metrics
        metrics['overall'] = await self._calculate_overall_metrics()
        
        # Sport-specific metrics
        metrics['by_sport'] = await self._calculate_sport_metrics()
        
        # Confidence calibration
        metrics['confidence_calibration'] = await self._calculate_confidence_calibration()
        
        # Recent performance (last 10 games)
        metrics['recent_performance'] = await self._calculate_recent_performance()
        
        # Yesterday's performance
        metrics['yesterday'] = await self._calculate_yesterday_performance()
        
        # Save to database for fast retrieval
        self.db['system_performance'].insert_one({
            'metrics': metrics,
            'calculated_at': now_utc(),
            'period': 'daily'
        })
        
        return metrics
    
    async def _calculate_overall_metrics(self) -> Dict:
        """
        Calculate overall model performance.
        
        Returns:
            {
                "7day_accuracy": 65.2,
                "7day_record": "15-8",
                "30day_roi": 8.3,
                "30day_units": 4.7,
                "brier_score": 0.18,
                "total_predictions": 127
            }
        """
        # 7-day metrics (use ISO string for comparison)
        seven_days_ago = (now_utc() - timedelta(days=7)).isoformat()
        seven_day_preds = list(self.db['monte_carlo_simulations'].find({
            'graded_at': {'$gte': seven_days_ago},
            'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
        }))
        
        seven_day_wins = len([p for p in seven_day_preds if p.get('status') == 'WIN'])
        seven_day_total = len([p for p in seven_day_preds if p.get('status') in ['WIN', 'LOSS']])
        seven_day_accuracy = (seven_day_wins / seven_day_total * 100) if seven_day_total > 0 else 0
        
        # 30-day metrics (use ISO string for comparison)
        thirty_days_ago = (now_utc() - timedelta(days=30)).isoformat()
        thirty_day_preds = list(self.db['monte_carlo_simulations'].find({
            'graded_at': {'$gte': thirty_days_ago},
            'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
        }))
        
        thirty_day_units = sum([p.get('units_won', 0) for p in thirty_day_preds])
        thirty_day_total = len([p for p in thirty_day_preds if p.get('status') in ['WIN', 'LOSS']])
        thirty_day_roi = (thirty_day_units / thirty_day_total * 100) if thirty_day_total > 0 else 0
        
        # Brier score (lower is better, measures calibration)
        brier_score = await self._calculate_brier_score(thirty_day_preds)
        
        return {
            '7day_accuracy': round(seven_day_accuracy, 1),
            '7day_record': f"{seven_day_wins}-{seven_day_total - seven_day_wins}",
            '7day_units': round(sum([p.get('units_won', 0) for p in seven_day_preds]), 2),
            '30day_roi': round(thirty_day_roi, 1),
            '30day_units': round(thirty_day_units, 2),
            '30day_record': f"{len([p for p in thirty_day_preds if p.get('status') == 'WIN'])}-{len([p for p in thirty_day_preds if p.get('status') == 'LOSS'])}",
            'brier_score': round(brier_score, 3),
            'total_predictions': thirty_day_total
        }
    
    async def _calculate_sport_metrics(self) -> Dict:
        """
        Calculate accuracy by sport.
        
        Returns:
            {
                "NBA": {"accuracy": 68.5, "roi": 12.3, "record": "22-10"},
                "NFL": {"accuracy": 62.0, "roi": 5.8, "record": "18-11"},
                ...
            }
        """
        thirty_days_ago = (now_utc() - timedelta(days=30)).isoformat()
        sports = ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAB', 'NCAAF']
        
        sport_metrics = {}
        
        for sport in sports:
            sport_preds = list(self.db['monte_carlo_simulations'].find({
                'graded_at': {'$gte': thirty_days_ago},
                'sport': sport,
                'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
            }))
            
            if len(sport_preds) == 0:
                continue
            
            wins = len([p for p in sport_preds if p.get('status') == 'WIN'])
            losses = len([p for p in sport_preds if p.get('status') == 'LOSS'])
            total = wins + losses
            
            accuracy = (wins / total * 100) if total > 0 else 0
            units = sum([p.get('units_won', 0) for p in sport_preds])
            roi = (units / total * 100) if total > 0 else 0
            
            sport_metrics[sport] = {
                'accuracy': round(accuracy, 1),
                'roi': round(roi, 1),
                'units': round(units, 2),
                'record': f"{wins}-{losses}",
                'total_predictions': total
            }
        
        return sport_metrics
    
    async def _calculate_confidence_calibration(self) -> Dict:
        """
        Measure how well confidence scores match actual outcomes.
        
        Ideal: 75% confidence predictions should win 75% of the time.
        
        Returns:
            {
                "high_confidence": {"predicted": 0.80, "actual": 0.78, "count": 45},
                "medium_confidence": {"predicted": 0.65, "actual": 0.62, "count": 52},
                "low_confidence": {"predicted": 0.52, "actual": 0.51, "count": 30}
            }
        """
        thirty_days_ago = (now_utc() - timedelta(days=30)).isoformat()
        
        all_preds = list(self.db['monte_carlo_simulations'].find({
            'graded_at': {'$gte': thirty_days_ago},
            'status': {'$in': ['WIN', 'LOSS']}
        }))
        
        # Bucket by confidence level
        high_conf = [p for p in all_preds if p.get('confidence', 0) >= 0.75]
        medium_conf = [p for p in all_preds if 0.60 <= p.get('confidence', 0) < 0.75]
        low_conf = [p for p in all_preds if p.get('confidence', 0) < 0.60]
        
        def calc_calibration(preds):
            if len(preds) == 0:
                return {"predicted": 0, "actual": 0, "count": 0}
            
            avg_predicted = sum([p.get('confidence', 0) for p in preds]) / len(preds)
            wins = len([p for p in preds if p.get('status') == 'WIN'])
            actual_accuracy = wins / len(preds)
            
            return {
                "predicted": round(avg_predicted, 2),
                "actual": round(actual_accuracy, 2),
                "count": len(preds)
            }
        
        return {
            "high_confidence": calc_calibration(high_conf),
            "medium_confidence": calc_calibration(medium_conf),
            "low_confidence": calc_calibration(low_conf)
        }
    
    async def _calculate_recent_performance(self) -> List[Dict]:
        """
        Last 10 graded predictions.
        
        Returns:
            [
                {"game": "Lakers vs Celtics", "result": "WIN", "confidence": 0.72},
                ...
            ]
        """
        recent = list(self.db['monte_carlo_simulations'].find({
            'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
        }).sort('graded_at', -1).limit(10))
        
        results = []
        for pred in recent:
            event = self.db['events'].find_one({'event_id': pred.get('event_id')})
            if not event:
                continue
            
            graded_at = pred.get('graded_at')
            if graded_at and isinstance(graded_at, str):
                graded_at_str = graded_at
            elif graded_at:
                graded_at_str = graded_at.isoformat()
            else:
                graded_at_str = None
            
            results.append({
                'game': f"{event.get('away_team')} vs {event.get('home_team')}",
                'sport': pred.get('sport', 'NBA'),
                'result': pred.get('status'),
                'confidence': round(pred.get('confidence', 0), 2),
                'units_won': pred.get('units_won', 0),
                'graded_at': graded_at_str
            })
        
        return results
    
    async def _calculate_yesterday_performance(self) -> Dict:
        """
        Yesterday's daily performance for hero display.
        
        Returns:
            {
                "record": "4-1",
                "units": 3.2,
                "accuracy": 80.0,
                "message": "🎯 4-1 (+3.2 Units)"
            }
        """
        yesterday = now_utc() - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday_start + timedelta(days=1)
        
        yesterday_preds = list(self.db['monte_carlo_simulations'].find({
            'graded_at': {'$gte': yesterday_start, '$lt': yesterday_end},
            'status': {'$in': ['WIN', 'LOSS']}
        }))
        
        if len(yesterday_preds) == 0:
            return {
                'record': '0-0',
                'units': 0.0,
                'accuracy': 0.0,
                'message': 'No games graded yesterday'
            }
        
        wins = len([p for p in yesterday_preds if p.get('status') == 'WIN'])
        losses = len(yesterday_preds) - wins
        units = sum([p.get('units_won', 0) for p in yesterday_preds])
        accuracy = (wins / len(yesterday_preds) * 100)
        
        return {
            'record': f"{wins}-{losses}",
            'units': round(units, 2),
            'accuracy': round(accuracy, 1),
            'message': f"🎯 {wins}-{losses} ({units:+.1f} Units)"
        }
    
    async def _calculate_brier_score(self, predictions: List[Dict]) -> float:
        """
        Calculate Brier Score (0-1, lower is better).
        
        Formula: (1/N) * Σ(predicted_prob - actual_outcome)^2
        
        Measures how well calibrated probabilities are.
        """
        if len(predictions) == 0:
            return 0.0
        
        total_error = 0.0
        count = 0
        
        for pred in predictions:
            confidence = pred.get('confidence', 0.5)
            actual_outcome = 1.0 if pred.get('status') == 'WIN' else 0.0
            
            error = (confidence - actual_outcome) ** 2
            total_error += error
            count += 1
        
        return total_error / count if count > 0 else 0.0
    
    async def get_cached_metrics(self) -> Dict:
        """
        Retrieve most recent calculated metrics from cache.
        
        Falls back to live calculation if cache is stale.
        """
        # Get most recent metrics
        cached = self.db['system_performance'].find_one(
            {},
            sort=[('calculated_at', -1)]
        )
        
        if cached:
            # Check if cache is fresh (< 6 hours old)
            cache_age = (now_utc() - cached['calculated_at']).total_seconds() / 3600
            
            if cache_age < 6:
                return cached['metrics']
        
        # Cache is stale or doesn't exist, calculate now
        logger.info("Cache miss or stale, calculating trust metrics...")
        return await self.calculate_all_metrics()
    
    async def get_accuracy_trend(self, days: int = 7) -> List[Dict]:
        """
        Daily accuracy trend for sparkline chart.
        
        Returns:
            [
                {"date": "2024-11-22", "accuracy": 68.5, "units": 2.3},
                {"date": "2024-11-23", "accuracy": 71.2, "units": 1.8},
                ...
            ]
        """
        trend = []
        
        for i in range(days, 0, -1):
            day_start = (now_utc() - timedelta(days=i)).replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)
            
            day_preds = list(self.db['monte_carlo_simulations'].find({
                'graded_at': {'$gte': day_start, '$lt': day_end},
                'status': {'$in': ['WIN', 'LOSS']}
            }))
            
            if len(day_preds) > 0:
                wins = len([p for p in day_preds if p.get('status') == 'WIN'])
                accuracy = (wins / len(day_preds) * 100)
                units = sum([p.get('units_won', 0) for p in day_preds])
                
                trend.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'accuracy': round(accuracy, 1),
                    'units': round(units, 2),
                    'wins': wins,
                    'losses': len(day_preds) - wins
                })
        
        return trend
    
    # ========================================================================
    # COMPREHENSIVE WEEKLY ANALYSIS (PHASE 3)
    # ========================================================================
    
    async def aggregate_weekly_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate all graded predictions from the past week
        
        Computes:
        - Confidence calibration by bucket
        - Model error by environment (regular season vs championship)
        - Regime adjustment effectiveness
        - Safety engine suppression accuracy
        """
        # Default to last 7 days
        if not end_date:
            end_date = now_utc()
        if not start_date:
            start_date = end_date - timedelta(days=7)
        
        logger.info(f"Aggregating trust metrics from {start_date} to {end_date}")
        
        # Query all graded predictions in time range
        graded_predictions = list(self.db['monte_carlo_simulations'].find({
            "graded": True,
            "graded_at": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }))
        
        if not graded_predictions:
            logger.warning("No graded predictions found in time range")
            return self._empty_report()
        
        logger.info(f"Found {len(graded_predictions)} graded predictions")
        
        # Initialize accumulators
        overall_stats: Dict[str, Any] = {
            "total": 0,
            "correct": 0,
            "model_errors": [],
            "edge_accuracies": []
        }
        
        by_sport: Dict[str, Dict[str, Any]] = {}
        by_environment: Dict[str, Dict[str, Any]] = {}
        by_confidence_bucket: Dict[str, Dict[str, Any]] = {}
        regime_performance: Dict[str, Dict[str, Any]] = {}
        
        # Process each prediction
        for pred in graded_predictions:
            # Extract fields
            sport = pred.get("sport", "unknown")
            is_correct = pred.get("correct", False)
            model_error = pred.get("model_error", 0)
            edge_accuracy = pred.get("edge_accuracy", 0)
            confidence = pred.get("confidence", 0.5)
            
            # Get regime flags
            regime_flags = pred.get("regime_flags", {})
            environment_type = regime_flags.get("environment_type", "regular_season")
            adjustments_applied = regime_flags.get("adjustments_applied", [])
            
            # Confidence bucket (round to nearest 5%)
            confidence_bucket = round(confidence * 20) / 20  # 0.60, 0.65, 0.70, etc.
            bucket_label = f"{int(confidence_bucket*100)}-{int(confidence_bucket*100)+5}%"
            
            # Update overall stats
            overall_stats["total"] += 1
            if is_correct:
                overall_stats["correct"] += 1
            overall_stats["model_errors"].append(model_error)
            overall_stats["edge_accuracies"].append(edge_accuracy)
            
            # Update by sport
            if sport not in by_sport:
                by_sport[sport] = {
                    "total": 0, "correct": 0, "model_errors": [], "edge_accuracies": []
                }
            by_sport[sport]["total"] += 1
            if is_correct:
                by_sport[sport]["correct"] += 1
            by_sport[sport]["model_errors"].append(model_error)
            by_sport[sport]["edge_accuracies"].append(edge_accuracy)
            
            # Update by environment
            if environment_type not in by_environment:
                by_environment[environment_type] = {
                    "total": 0, "correct": 0, "model_errors": [], "edge_accuracies": []
                }
            by_environment[environment_type]["total"] += 1
            if is_correct:
                by_environment[environment_type]["correct"] += 1
            by_environment[environment_type]["model_errors"].append(model_error)
            by_environment[environment_type]["edge_accuracies"].append(edge_accuracy)
            
            # Update by confidence bucket
            if bucket_label not in by_confidence_bucket:
                by_confidence_bucket[bucket_label] = {
                    "total": 0, "correct": 0, "model_errors": [], "confidence_range": ""
                }
            by_confidence_bucket[bucket_label]["total"] += 1
            if is_correct:
                by_confidence_bucket[bucket_label]["correct"] += 1
            by_confidence_bucket[bucket_label]["model_errors"].append(model_error)
            by_confidence_bucket[bucket_label]["confidence_range"] = bucket_label
            
            # Update regime performance (track by adjustment types)
            if adjustments_applied:
                regime_key = ",".join(sorted(adjustments_applied))
                if regime_key not in regime_performance:
                    regime_performance[regime_key] = {
                        "total": 0, "correct": 0, "model_errors": [], "adjustments": []
                    }
                regime_performance[regime_key]["total"] += 1
                if is_correct:
                    regime_performance[regime_key]["correct"] += 1
                regime_performance[regime_key]["model_errors"].append(model_error)
                regime_performance[regime_key]["adjustments"] = adjustments_applied
        
        # Compute summary statistics
        def _compute_stats(data: Dict[str, Any]) -> Dict[str, Any]:
            """Helper to compute win rate and avg error"""
            total = data["total"]
            correct = data["correct"]
            errors = data["model_errors"]
            edge_accs = data.get("edge_accuracies", [])
            
            return {
                "total_predictions": total,
                "correct_predictions": correct,
                "win_rate": correct / total if total > 0 else 0,
                "avg_model_error": sum(errors) / len(errors) if errors else 0,
                "avg_edge_accuracy": sum(edge_accs) / len(edge_accs) if edge_accs else 0
            }
        
        # Build report
        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": (end_date - start_date).days
            },
            "overall": _compute_stats(overall_stats),
            "by_sport": {
                sport: _compute_stats(stats)
                for sport, stats in by_sport.items()
            },
            "by_environment": {
                env: _compute_stats(stats)
                for env, stats in by_environment.items()
            },
            "by_confidence_bucket": {
                bucket: _compute_stats(stats)
                for bucket, stats in by_confidence_bucket.items()
            },
            "regime_performance": {
                regime: {
                    **_compute_stats(stats),
                    "adjustments": stats["adjustments"]
                }
                for regime, stats in regime_performance.items()
            },
            "generated_at": now_utc().isoformat()
        }
        
        # Store report
        self.db["trust_metrics_weekly"].insert_one(report)
        
        logger.info(f"Trust metrics aggregated: {overall_stats['total']} predictions analyzed")
        
        return report
    
    def _empty_report(self) -> Dict[str, Any]:
        """Return empty report structure"""
        return {
            "overall": {"total_predictions": 0, "correct_predictions": 0, "win_rate": 0, "avg_model_error": 0},
            "by_sport": {},
            "by_environment": {},
            "by_confidence_bucket": {},
            "regime_performance": {}
        }
    
    async def analyze_calibration(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze confidence calibration
        
        Returns recommended adjustments if buckets are miscalibrated
        """
        calibration_issues = []
        adjustments = {}
        
        for bucket, stats in report.get("by_confidence_bucket", {}).items():
            expected_win_rate = float(bucket.split("-")[0]) / 100  # e.g., 0.60 from "60-65%"
            actual_win_rate = stats["win_rate"]
            total = stats["total_predictions"]
            
            # Need at least 10 samples to make calibration judgment
            if total < 10:
                continue
            
            # Check if calibration is off by >5%
            calibration_error = abs(actual_win_rate - expected_win_rate)
            
            if calibration_error > 0.05:
                issue = {
                    "bucket": bucket,
                    "expected_win_rate": expected_win_rate,
                    "actual_win_rate": actual_win_rate,
                    "calibration_error": calibration_error,
                    "sample_size": total
                }
                
                if actual_win_rate < expected_win_rate:
                    issue["diagnosis"] = "OVERCONFIDENT"
                    issue["recommendation"] = "Increase variance or lower confidence thresholds"
                else:
                    issue["diagnosis"] = "UNDERCONFIDENT"
                    issue["recommendation"] = "Decrease variance or raise confidence thresholds"
                
                calibration_issues.append(issue)
                adjustments[bucket] = issue["recommendation"]
        
        return {
            "calibration_issues": calibration_issues,
            "is_calibrated": len(calibration_issues) == 0,
            "recommended_adjustments": adjustments
        }
    
    async def analyze_regime_effectiveness(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze if regime adjustments (pace compression, RZ suppression, etc.) are working
        
        Returns performance comparison and recommendations
        """
        regime_analysis = []
        
        for regime_key, stats in report.get("regime_performance", {}).items():
            if stats["total_predictions"] < 5:
                continue  # Not enough data
            
            adjustments = stats.get("adjustments", [])
            
            analysis = {
                "regime": regime_key,
                "adjustments_applied": adjustments,
                "total_predictions": stats["total_predictions"],
                "win_rate": stats["win_rate"],
                "avg_model_error": stats["avg_model_error"],
            }
            
            # Compare to overall performance
            overall_error = report["overall"]["avg_model_error"]
            error_improvement = overall_error - stats["avg_model_error"]
            
            if error_improvement > 2:
                analysis["assessment"] = "EFFECTIVE"
                analysis["note"] = f"Regime reduced error by {error_improvement:.1f} points"
            elif error_improvement < -2:
                analysis["assessment"] = "INEFFECTIVE"
                analysis["note"] = f"Regime increased error by {abs(error_improvement):.1f} points"
                analysis["recommendation"] = "Consider adjusting or removing these regime rules"
            else:
                analysis["assessment"] = "NEUTRAL"
                analysis["note"] = "Regime impact is minimal"
            
            regime_analysis.append(analysis)
        
        return {
            "regime_analysis": regime_analysis
        }
    
    async def generate_weekly_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate comprehensive weekly trust loop report
        
        Returns:
            Full report with metrics, calibration analysis, and recommendations
        """
        end_date = now_utc()
        start_date = end_date - timedelta(days=days)
        
        # Aggregate metrics
        report = await self.aggregate_weekly_metrics(start_date, end_date)
        
        # Analyze calibration
        calibration = await self.analyze_calibration(report)
        report["calibration_analysis"] = calibration
        
        # Analyze regime effectiveness
        regime_effectiveness = await self.analyze_regime_effectiveness(report)
        report["regime_effectiveness"] = regime_effectiveness
        
        # Generate executive summary
        overall = report["overall"]
        executive_summary = f"""
Trust Loop Weekly Report
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}

Overall Performance:
- Total Predictions: {overall['total_predictions']}
- Win Rate: {overall['win_rate']:.1%}
- Avg Model Error: {overall['avg_model_error']:.1f} points
- Avg Edge Accuracy: {overall.get('avg_edge_accuracy', 0):.1%}

Calibration Status: {'✅ CALIBRATED' if calibration['is_calibrated'] else '⚠️ NEEDS ADJUSTMENT'}
"""
        
        if not calibration["is_calibrated"]:
            executive_summary += "\nCalibration Issues:\n"
            for issue in calibration["calibration_issues"]:
                executive_summary += f"  - {issue['bucket']}: {issue['diagnosis']} (expected {issue['expected_win_rate']:.0%}, actual {issue['actual_win_rate']:.0%})\n"
        
        report["executive_summary"] = executive_summary
        
        logger.info("=" * 80)
        logger.info(executive_summary)
        logger.info("=" * 80)
        
        return report


# Singleton instance
trust_metrics_service = TrustMetricsService()

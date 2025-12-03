"""
Trust Metrics Service
=====================

Calculates model performance metrics for the Trust Loop.

Metrics Tracked:
- 7-Day Accuracy (Win Rate)
- 30-Day ROI (Units Won)
- Brier Score (Calibration Quality)
- Confidence Calibration
- Sport-Specific Accuracy
- Last 10-Game Performance
"""
from typing import Dict, List
from datetime import datetime, timedelta
from db.mongo import db
from utils.timezone import now_utc
import logging

logger = logging.getLogger(__name__)


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
            
            results.append({
                'game': f"{event.get('away_team')} vs {event.get('home_team')}",
                'sport': pred.get('sport', 'NBA'),
                'result': pred.get('status'),
                'confidence': round(pred.get('confidence', 0), 2),
                'units_won': pred.get('units_won', 0),
                'graded_at': pred.get('graded_at').isoformat() if pred.get('graded_at') else None
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


# Singleton instance
trust_metrics_service = TrustMetricsService()

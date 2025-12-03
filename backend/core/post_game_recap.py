"""
Post-Game Recap & Feedback Loop
Auto-generate recaps after games end + log for model validation
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OutcomeResult(Enum):
    HIT = "HIT"
    MISS = "MISS"
    PUSH = "PUSH"
    PENDING = "PENDING"


@dataclass
class PredictionRecord:
    """Complete prediction record for feedback loop"""
    
    # Game identification
    game_id: str
    event_date: datetime
    prediction_timestamp: datetime
    
    # Simulation config
    sim_tier: str  # "Starter", "Core", "Pro", "Elite"
    sim_count: int  # 10000, 25000, 50000, 100000
    
    # Projections
    projected_total: float
    projected_h1_total: Optional[float]
    home_win_probability: float
    away_win_probability: float
    
    # Market data at prediction time
    book_total_open: Optional[float]
    book_total_close: Optional[float]
    book_ml_home_open: Optional[int]
    book_ml_home_close: Optional[int]
    
    # Model metrics
    confidence_score: int  # 0-100
    volatility: str  # LOW, MEDIUM, HIGH
    edge_classification: str  # EDGE, LEAN, NEUTRAL
    
    # Leans
    side_lean: Optional[str]  # "home", "away", "neutral"
    total_lean: Optional[str]  # "over", "under", "neutral"
    h1_total_lean: Optional[str]
    
    # Expected values
    ev_side: Optional[float]
    ev_total: Optional[float]
    
    # Injury impact
    injury_impact_score: float = 0.0
    
    # Results (populated after game)
    actual_total: Optional[float] = None
    actual_h1_total: Optional[float] = None
    actual_winner: Optional[str] = None
    
    side_result: OutcomeResult = OutcomeResult.PENDING
    total_result: OutcomeResult = OutcomeResult.PENDING
    h1_total_result: OutcomeResult = OutcomeResult.PENDING
    
    # CLV tracking
    clv_total_favorable: Optional[bool] = None
    clv_ml_favorable: Optional[bool] = None
    
    # Notes
    recap_notes: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.recap_notes is None:
            self.recap_notes = []
    
    def grade_predictions(self):
        """Grade predictions after game completes"""
        
        if self.actual_total is None or self.actual_winner is None:
            logger.warning(f"Cannot grade {self.game_id} - missing actual results")
            return
        
        # Initialize recap_notes if None
        if self.recap_notes is None:
            self.recap_notes = []
        
        # Grade side
        if self.side_lean and self.side_lean != "neutral":
            if self.actual_winner == self.side_lean:
                self.side_result = OutcomeResult.HIT
                self.recap_notes.append(f"✅ Side prediction HIT: {self.side_lean} ({self.home_win_probability:.1%} confidence)")
            else:
                self.side_result = OutcomeResult.MISS
                self.recap_notes.append(f"❌ Side prediction MISS: predicted {self.side_lean}, actual {self.actual_winner}")
        
        # Grade total
        if self.total_lean and self.book_total_close:
            if self.actual_total == self.book_total_close:
                self.total_result = OutcomeResult.PUSH
                self.recap_notes.append(f"⚪ Total PUSH at {self.book_total_close}")
            elif self.total_lean == "over":
                if self.actual_total > self.book_total_close:
                    self.total_result = OutcomeResult.HIT
                    self.recap_notes.append(f"✅ Over HIT: {self.actual_total} > {self.book_total_close}")
                else:
                    self.total_result = OutcomeResult.MISS
                    self.recap_notes.append(f"❌ Over MISS: {self.actual_total} < {self.book_total_close}")
            elif self.total_lean == "under":
                if self.actual_total < self.book_total_close:
                    self.total_result = OutcomeResult.HIT
                    self.recap_notes.append(f"✅ Under HIT: {self.actual_total} < {self.book_total_close}")
                else:
                    self.total_result = OutcomeResult.MISS
                    self.recap_notes.append(f"❌ Under MISS: {self.actual_total} > {self.book_total_close}")
        
        # Grade 1H total
        if self.h1_total_lean and self.actual_h1_total:
            # Similar logic for 1H
            pass
        
        # Add context notes
        if self.confidence_score < 40:
            self.recap_notes.append(f"ℹ️ Model labeled this as LOW CONFIDENCE ({self.confidence_score}/100) - high volatility expected")
        
        if self.volatility == "HIGH":
            self.recap_notes.append(f"⚠️ High volatility game - inherently swingy matchup")
        
        if self.edge_classification == "LEAN":
            self.recap_notes.append(f"ℹ️ Classified as LEAN (not strong edge) - for tracking purposes only")
        
        # CLV notes
        if self.clv_total_favorable is not None:
            clv_status = "✅ favorable" if self.clv_total_favorable else "❌ unfavorable"
            self.recap_notes.append(f"CLV: Line moved {clv_status} (open {self.book_total_open} → close {self.book_total_close})")
        
        # Projection accuracy
        if self.projected_total and self.actual_total:
            error = abs(self.projected_total - self.actual_total)
            error_pct = (error / self.actual_total) * 100
            self.recap_notes.append(f"Projection accuracy: {error:.1f} pts off ({error_pct:.1f}% error)")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage"""
        data = asdict(self)
        data['side_result'] = self.side_result.value
        data['total_result'] = self.total_result.value
        data['h1_total_result'] = self.h1_total_result.value
        return data


class FeedbackLogger:
    """Log all predictions for future model calibration"""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def log_prediction(self, record: PredictionRecord):
        """Store prediction record"""
        try:
            await self.db.predictions.insert_one(record.to_dict())
            logger.info(f"Logged prediction for {record.game_id} at {record.prediction_timestamp}")
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")
    
    async def update_results(self, game_id: str, actual_data: Dict[str, Any]):
        """Update prediction with actual results"""
        try:
            # Find prediction
            prediction = await self.db.predictions.find_one({"game_id": game_id})
            if not prediction:
                logger.warning(f"No prediction found for {game_id}")
                return
            
            # Create record and grade
            record = PredictionRecord(**prediction)
            record.actual_total = actual_data.get('total')
            record.actual_h1_total = actual_data.get('h1_total')
            record.actual_winner = actual_data.get('winner')
            
            record.grade_predictions()
            
            # Update in DB
            await self.db.predictions.update_one(
                {"game_id": game_id},
                {"$set": record.to_dict()}
            )
            
            logger.info(f"Updated results for {game_id}: {record.side_result.value}, {record.total_result.value}")
            
            return record
            
        except Exception as e:
            logger.error(f"Failed to update results for {game_id}: {e}")
    
    async def get_performance_stats(
        self,
        start_date: Optional[datetime] = None,
        min_confidence: int = 0,
        sim_tier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate performance metrics"""
        
        query = {
            "side_result": {"$ne": "PENDING"},
            "confidence_score": {"$gte": min_confidence}
        }
        
        if start_date:
            query["prediction_timestamp"] = {"$gte": start_date}
        
        if sim_tier:
            query["sim_tier"] = sim_tier
        
        predictions = await self.db.predictions.find(query).to_list(length=None)
        
        if not predictions:
            return {"error": "No graded predictions found"}
        
        # Calculate stats
        total_predictions = len(predictions)
        
        # Side accuracy
        side_hits = sum(1 for p in predictions if p.get('side_result') == 'HIT')
        side_total = sum(1 for p in predictions if p.get('side_result') in ['HIT', 'MISS'])
        side_accuracy = (side_hits / side_total * 100) if side_total > 0 else 0
        
        # Total accuracy
        total_hits = sum(1 for p in predictions if p.get('total_result') == 'HIT')
        total_total = sum(1 for p in predictions if p.get('total_result') in ['HIT', 'MISS'])
        total_accuracy = (total_hits / total_total * 100) if total_total > 0 else 0
        
        # EV+ hit rate
        ev_plus = [p for p in predictions if p.get('edge_classification') == 'EDGE']
        ev_plus_hits = sum(1 for p in ev_plus if p.get('side_result') == 'HIT' or p.get('total_result') == 'HIT')
        ev_plus_rate = (ev_plus_hits / len(ev_plus) * 100) if ev_plus else 0
        
        # CLV accuracy
        clv_favorable = sum(1 for p in predictions if p.get('clv_total_favorable') == True)
        clv_rate = (clv_favorable / total_predictions * 100)
        
        # Confidence-based breakdown
        high_conf = [p for p in predictions if p.get('confidence_score', 0) >= 70]
        high_conf_hits = sum(1 for p in high_conf if p.get('side_result') == 'HIT' or p.get('total_result') == 'HIT')
        high_conf_accuracy = (high_conf_hits / len(high_conf) * 100) if high_conf else 0
        
        return {
            "total_predictions": total_predictions,
            "side_accuracy": round(side_accuracy, 1),
            "total_accuracy": round(total_accuracy, 1),
            "ev_plus_hit_rate": round(ev_plus_rate, 1),
            "clv_favorable_rate": round(clv_rate, 1),
            "high_confidence_accuracy": round(high_conf_accuracy, 1),
            "high_confidence_count": len(high_conf),
            "date_range": {
                "start": min(p['prediction_timestamp'] for p in predictions),
                "end": max(p['prediction_timestamp'] for p in predictions)
            }
        }


def generate_recap_text(record: PredictionRecord) -> str:
    """Generate human-readable recap"""
    
    lines = [
        f"📊 Game Recap: {record.game_id}",
        f"Predicted: {record.prediction_timestamp.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Simulation Tier: {record.sim_tier} ({record.sim_count:,} iterations)",
        f"Confidence: {record.confidence_score}/100 ({get_confidence_label(record.confidence_score)})",
        f"Volatility: {record.volatility}",
        "",
        "📈 Predictions:",
    ]
    
    # Side
    if record.side_lean and record.side_lean != "neutral":
        result_emoji = "✅" if record.side_result == OutcomeResult.HIT else "❌"
        lines.append(f"  {result_emoji} Side: {record.side_lean.upper()} ({record.home_win_probability:.1%}) - {record.side_result.value}")
    
    # Total
    if record.total_lean and record.total_lean != "neutral":
        result_emoji = "✅" if record.total_result == OutcomeResult.HIT else "❌"
        lines.append(f"  {result_emoji} Total: {record.total_lean.upper()} {record.book_total_close} - {record.total_result.value}")
    
    lines.append("")
    lines.append("🎯 Actual Results:")
    lines.append(f"  Final Score: {record.actual_total} pts (projected {record.projected_total:.1f})")
    lines.append(f"  Winner: {record.actual_winner}")
    
    if record.recap_notes:
        lines.append("")
        lines.append("📝 Notes:")
        for note in record.recap_notes:
            lines.append(f"  • {note}")
    
    return "\n".join(lines)


def get_confidence_label(score: int) -> str:
    """Convert confidence score to label"""
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"

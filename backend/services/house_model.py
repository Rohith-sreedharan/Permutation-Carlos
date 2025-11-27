"""
House Model Service - The "Private Engine"
500k+ iteration simulations for internal use only
Creates the "House Edge" - Platform always has better data than users
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.monte_carlo_engine import MonteCarloEngine
from db.mongo import db
from config import SIM_TIER_INTERNAL, PRECISION_LABELS
import uuid


class HouseModelService:
    """
    Private simulation engine with institutional-grade precision
    
    Purpose:
    - Generate "Perfect Lines" for grading public model accuracy (Trust Loop)
    - Model tuning and calibration
    - Risk management and exposure analysis
    - Never exposed to users - Platform moat
    """
    
    def __init__(self):
        self.engine = MonteCarloEngine()
        self.internal_iterations = SIM_TIER_INTERNAL  # 500,000 iterations
    
    def run_house_simulation(
        self,
        event_id: str,
        team_a: Dict[str, Any],
        team_b: Dict[str, Any],
        market_context: Dict[str, Any],
        store_result: bool = True
    ) -> Dict[str, Any]:
        """
        Run ultra-high precision simulation for internal analysis
        
        Args:
            event_id: Event identifier
            team_a: Home team parameters
            team_b: Away team parameters
            market_context: Market data (spread, total, public betting %)
            store_result: Whether to store in house_models collection
        
        Returns:
            House simulation with 500k iterations and full distribution curves
        """
        print(f"🏠 Running HOUSE MODEL simulation for {event_id} ({self.internal_iterations} iterations)")
        
        try:
            # Run with maximum precision
            result = self.engine.run_simulation(
                event_id=event_id,
                team_a=team_a,
                team_b=team_b,
                market_context=market_context,
                iterations=self.internal_iterations,
                mode="full"
            )
            
            # Enrich with house metadata
            house_model = {
                "house_model_id": str(uuid.uuid4()),
                "event_id": event_id,
                "simulation": result,
                "iterations": self.internal_iterations,
                "precision_level": PRECISION_LABELS.get(self.internal_iterations, "HOUSE_EDGE"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model_version": "v1.0",
                "purpose": "internal_analysis",
                "access_level": "super_admin_only"
            }
            
            # Store in house_models collection (separate from public predictions)
            if store_result:
                db["house_models"].insert_one(house_model.copy())
                print(f"✓ House model stored for {event_id}")
            
            return house_model
            
        except Exception as e:
            print(f"✗ House model generation failed for {event_id}: {str(e)}")
            raise
    
    def get_house_model(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve existing house model for an event
        
        Returns:
            House model document or None
        """
        model = db["house_models"].find_one(
            {"event_id": event_id},
            sort=[("created_at", -1)]
        )
        
        if model:
            model["_id"] = str(model["_id"])
            return model
        
        return None
    
    def compare_public_vs_house(self, event_id: str) -> Dict[str, Any]:
        """
        Compare public model accuracy vs house model "perfect line"
        Used for Trust Loop grading
        
        Returns:
            Comparison metrics showing divergence and accuracy assessment
        """
        # Get house model (500k iterations)
        house_model = self.get_house_model(event_id)
        if not house_model:
            return {"error": "House model not found for this event"}
        
        # Get latest public prediction
        public_pred = db["predictions"].find_one(
            {"event_id": event_id},
            sort=[("created_at", -1)]
        )
        
        if not public_pred:
            return {"error": "No public prediction found for this event"}
        
        # Extract key metrics
        house_sim = house_model["simulation"]
        house_confidence = house_sim.get("confidence_score", 0)
        house_win_prob = house_sim.get("win_probability", {}).get("team_a", 0.5)
        
        public_confidence = public_pred.get("confidence", 0)
        public_win_prob = public_pred.get("win_probability", 0.5)
        
        # Calculate divergence
        confidence_divergence = abs(house_confidence - public_confidence)
        win_prob_divergence = abs(house_win_prob - public_win_prob)
        
        # Grade public model
        if confidence_divergence < 0.05 and win_prob_divergence < 0.03:
            grade = "EXCELLENT"
            color = "green"
        elif confidence_divergence < 0.10 and win_prob_divergence < 0.05:
            grade = "GOOD"
            color = "yellow"
        else:
            grade = "NEEDS_CALIBRATION"
            color = "red"
        
        return {
            "event_id": event_id,
            "house_model": {
                "confidence": house_confidence,
                "win_probability": house_win_prob,
                "iterations": self.internal_iterations
            },
            "public_model": {
                "confidence": public_confidence,
                "win_probability": public_win_prob,
                "iterations": public_pred.get("iterations", 50000)
            },
            "divergence": {
                "confidence": confidence_divergence,
                "win_probability": win_prob_divergence
            },
            "grade": grade,
            "grade_color": color,
            "recommendation": self._get_calibration_recommendation(grade)
        }
    
    def _get_calibration_recommendation(self, grade: str) -> str:
        """Get calibration recommendation based on grade"""
        recommendations = {
            "EXCELLENT": "Public model is well-calibrated. No action needed.",
            "GOOD": "Public model is acceptable. Monitor for drift over time.",
            "NEEDS_CALIBRATION": "Public model diverges significantly from house model. Consider recalibration or additional training data."
        }
        return recommendations.get(grade, "Unknown grade")
    
    def batch_generate_house_models(self, limit: int = 10) -> Dict[str, int]:
        """
        Generate house models for multiple events in batch
        Useful for overnight processing or pre-computation
        
        Returns:
            Statistics: {generated: X, failed: Y}
        """
        # Fetch upcoming events that don't have house models yet
        events = list(db["events"].find().limit(limit))
        
        stats = {"generated": 0, "failed": 0}
        
        for event in events:
            event_id = event.get("event_id") or event.get("id")
            if not event_id:
                continue
            
            # Check if house model already exists
            existing = self.get_house_model(event_id)
            if existing:
                print(f"⏭ Skipping {event_id} - house model already exists")
                continue
            
            try:
                # Generate house model with default team parameters
                self.run_house_simulation(
                    event_id=event_id,
                    team_a={
                        "name": event.get("home_team", "Team A"),
                        "recent_form": 0.55,
                        "home_advantage": 0.52,
                        "injury_impact": 1.0,
                        "fatigue_factor": 1.0,
                        "pace_factor": 1.0
                    },
                    team_b={
                        "name": event.get("away_team", "Team B"),
                        "recent_form": 0.50,
                        "home_advantage": 0.48,
                        "injury_impact": 1.0,
                        "fatigue_factor": 1.0,
                        "pace_factor": 1.0
                    },
                    market_context={
                        "current_spread": 0,
                        "total_line": 220,
                        "public_betting_pct": 0.50
                    },
                    store_result=True
                )
                stats["generated"] += 1
                
            except Exception as e:
                print(f"✗ Failed to generate house model for {event_id}: {str(e)}")
                stats["failed"] += 1
        
        print(f"📊 Batch generation complete: {stats}")
        return stats


# Singleton instance
house_model_service = HouseModelService()


# Convenience functions
def generate_house_model(event_id: str, team_a: Dict, team_b: Dict, market_context: Dict) -> Dict:
    """Generate single house model"""
    return house_model_service.run_house_simulation(event_id, team_a, team_b, market_context)


def get_house_model(event_id: str) -> Optional[Dict]:
    """Retrieve house model"""
    return house_model_service.get_house_model(event_id)


def compare_models(event_id: str) -> Dict:
    """Compare public vs house model"""
    return house_model_service.compare_public_vs_house(event_id)


def batch_generate(limit: int = 10) -> Dict:
    """Batch generate house models"""
    return house_model_service.batch_generate_house_models(limit)

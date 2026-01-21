"""
Simulation Run Tracking Service
================================
Tracks immutable simulation execution records with exact lineage.

Purpose:
- Record every simulation execution
- Track exact snapshots used as inputs
- Enable reproducibility
- Support version tracking (engine, model, calibration)
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from db.mongo import db
from db.schemas.logging_calibration_schemas import SimRun, SimRunInput
import logging
import subprocess

logger = logging.getLogger(__name__)


class SimRunTracker:
    """
    Tracks simulation runs with complete lineage
    """
    
    def __init__(self):
        self.sim_runs_collection = db.sim_runs
        self.sim_run_inputs_collection = db.sim_run_inputs
        self.predictions_collection = db.predictions
    
    def create_sim_run(
        self,
        event_id: str,
        trigger: str,
        sim_count: int,
        model_version: str,
        feature_set_version: str,
        decision_policy_version: str,
        calibration_version_applied: Optional[str] = None,
        seed_policy: str = "rolled",
        seed_value: Optional[int] = None
    ) -> str:
        """
        Create a new simulation run record
        
        Args:
            event_id: Event being simulated
            trigger: auto_internal, user_click, scheduled
            sim_count: Number of Monte Carlo iterations
            model_version: Model weights/config version
            feature_set_version: Feature engineering version
            decision_policy_version: Decision policy version
            calibration_version_applied: Calibration version (if any)
            seed_policy: fixed or rolled
            seed_value: Seed value if fixed
        
        Returns:
            sim_run_id
        """
        sim_run_id = str(uuid.uuid4())
        
        # Get engine version (git hash)
        engine_version = self._get_git_hash()
        
        sim_run = SimRun(
            sim_run_id=sim_run_id,
            event_id=event_id,
            created_at_utc=datetime.now(timezone.utc),
            trigger=trigger,  # type: ignore[arg-type]
            engine_version=engine_version,
            model_version=model_version,
            feature_set_version=feature_set_version,
            decision_policy_version=decision_policy_version,
            calibration_version_applied=calibration_version_applied,
            sim_count=sim_count,
            seed_policy=seed_policy,  # type: ignore[arg-type]
            seed_value=seed_value,
            status="SUCCESS"
        )
        
        self.sim_runs_collection.insert_one(sim_run.model_dump())
        
        logger.info(
            f"📊 Created sim_run: {sim_run_id} for {event_id} "
            f"({sim_count} iterations, trigger={trigger})"
        )
        
        return sim_run_id
    
    def record_sim_run_inputs(
        self,
        sim_run_id: str,
        snapshot_id: Optional[str] = None,
        injury_snapshot_id_home: Optional[str] = None,
        injury_snapshot_id_away: Optional[str] = None,
        weather_snapshot_id: Optional[str] = None
    ) -> None:
        """
        Record the exact snapshots used as inputs for a sim run
        
        This creates the lineage: sim_run → snapshots
        """
        sim_run_input = SimRunInput(
            sim_run_id=sim_run_id,
            snapshot_id=snapshot_id,
            injury_snapshot_id_home=injury_snapshot_id_home,
            injury_snapshot_id_away=injury_snapshot_id_away,
            weather_snapshot_id=weather_snapshot_id
        )
        
        self.sim_run_inputs_collection.insert_one(sim_run_input.model_dump())
        
        logger.info(
            f"🔗 Recorded inputs for sim_run: {sim_run_id} "
            f"(snapshot={snapshot_id})"
        )
    
    def create_prediction(
        self,
        sim_run_id: str,
        event_id: str,
        market_key: str,
        selection: str,
        market_snapshot_id_used: str,
        model_line: Optional[float],
        p_win: Optional[float],
        p_cover: Optional[float],
        p_over: Optional[float],
        ev_units: Optional[float],
        edge_points: Optional[float],
        uncertainty: Optional[float],
        distribution_summary: Dict[str, Any],
        rcl_gate_pass: bool,
        recommendation_state: str,
        tier: Optional[str],
        confidence_index: Optional[float],
        variance_bucket: Optional[str]
    ) -> str:
        """
        Create a prediction record linked to a sim run
        
        Returns:
            prediction_id
        """
        prediction_id = str(uuid.uuid4())
        
        prediction = {
            "prediction_id": prediction_id,
            "sim_run_id": sim_run_id,
            "event_id": event_id,
            "market_key": market_key,
            "selection": selection,
            "market_snapshot_id_used": market_snapshot_id_used,
            "model_line": model_line,
            "p_win": p_win,
            "p_cover": p_cover,
            "p_over": p_over,
            "ev_units": ev_units,
            "edge_points": edge_points,
            "uncertainty": uncertainty,
            "distribution_summary": distribution_summary,
            "rcl_gate_pass": rcl_gate_pass,
            "recommendation_state": recommendation_state,
            "tier": tier,
            "confidence_index": confidence_index,
            "variance_bucket": variance_bucket
        }
        
        self.predictions_collection.insert_one(prediction)
        
        logger.info(
            f"🎯 Created prediction: {prediction_id} for {event_id} "
            f"({market_key}, state={recommendation_state})"
        )
        
        return prediction_id
    
    def mark_sim_run_failed(
        self,
        sim_run_id: str,
        error_code: str,
        runtime_ms: Optional[int] = None
    ) -> None:
        """
        Mark a simulation run as failed
        """
        self.sim_runs_collection.update_one(
            {"sim_run_id": sim_run_id},
            {
                "$set": {
                    "status": "FAILED",
                    "error_code": error_code,
                    "runtime_ms": runtime_ms
                }
            }
        )
        
        logger.warning(f"❌ Sim run {sim_run_id} marked as FAILED: {error_code}")
    
    def mark_sim_run_timeout(
        self,
        sim_run_id: str,
        runtime_ms: int
    ) -> None:
        """
        Mark a simulation run as timed out
        """
        self.sim_runs_collection.update_one(
            {"sim_run_id": sim_run_id},
            {
                "$set": {
                    "status": "TIMEOUT",
                    "runtime_ms": runtime_ms
                }
            }
        )
        
        logger.warning(f"⏱️ Sim run {sim_run_id} timed out after {runtime_ms}ms")
    
    def complete_sim_run(
        self,
        sim_run_id: str,
        runtime_ms: int
    ) -> None:
        """
        Mark a simulation run as successfully completed
        """
        self.sim_runs_collection.update_one(
            {"sim_run_id": sim_run_id},
            {
                "$set": {
                    "status": "SUCCESS",
                    "runtime_ms": runtime_ms
                }
            }
        )
        
        logger.info(f"✅ Sim run {sim_run_id} completed in {runtime_ms}ms")
    
    def get_sim_run(self, sim_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a simulation run record
        """
        return self.sim_runs_collection.find_one({"sim_run_id": sim_run_id})
    
    def get_sim_run_inputs(self, sim_run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get inputs for a simulation run
        """
        return self.sim_run_inputs_collection.find_one({"sim_run_id": sim_run_id})
    
    def get_predictions_for_sim_run(self, sim_run_id: str) -> List[Dict[str, Any]]:
        """
        Get all predictions generated by a sim run
        """
        return list(self.predictions_collection.find({"sim_run_id": sim_run_id}))
    
    def get_sim_runs_for_event(
        self,
        event_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get simulation runs for an event (most recent first)
        """
        return list(
            self.sim_runs_collection
            .find({"event_id": event_id})
            .sort("created_at_utc", -1)
            .limit(limit)
        )
    
    def _get_git_hash(self) -> str:
        """
        Get current git commit hash for versioning
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not get git hash: {e}")
        
        return "unknown"


# Singleton instance
sim_run_tracker = SimRunTracker()

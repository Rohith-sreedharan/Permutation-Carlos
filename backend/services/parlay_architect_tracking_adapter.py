"""
Parlay Architect Integration Adapter
=====================================
Integrates the logging & calibration system with parlay_architect.py

This adapter wraps parlay generation to automatically:
1. Track sim_runs for each leg evaluation
2. Create predictions with lineage
3. Capture odds snapshots
4. Enable publishing with proper tracking
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.parlay_architect import (
    build_parlay,
    Leg,
    ParlayRequest,
    Tier,
    MarketType,
    derive_tier
)
from services.sim_run_tracker import sim_run_tracker
from services.snapshot_capture import snapshot_service
from services.publishing_service import publishing_service
import logging

logger = logging.getLogger(__name__)


class ParlayArchitectAdapter:
    """
    Adapter that integrates parlay_architect with logging system
    """
    
    def __init__(self):
        self.model_version = "v2.1.0"
        self.feature_set_version = "v1.5"
        self.decision_policy_version = "v1.0"
    
    def build_tracked_parlay(
        self,
        legs_data: List[Dict[str, Any]],
        profile: str,
        leg_count: int,
        allow_same_event: bool = False,
        allow_same_team: bool = True,
        seed: Optional[int] = None,
        include_props: bool = False,
        trigger: str = "user_click"
    ) -> Dict[str, Any]:
        """
        Build a parlay with full tracking integration
        
        Args:
            legs_data: List of candidate leg dictionaries with:
                - event_id, sport, league, start_time_utc
                - market_type, selection
                - confidence, clv, total_deviation, volatility, ev
                - canonical_state (for tier derivation)
                - simulation results, odds data, etc.
            profile: "premium", "balanced", "speculative"
            leg_count: 3-6 legs
            trigger: "user_click", "auto_internal", "scheduled"
            
        Returns:
            {
                "parlay_result": ParlayResult object,
                "sim_run_ids": [sim_run_ids for each leg],
                "prediction_ids": [prediction_ids for each leg],
                "ready_to_publish": bool
            }
        """
        logger.info(f"🎯 Building tracked parlay ({profile}, {leg_count} legs)")
        
        # Step 1: Capture odds snapshots and create sim_runs for each leg
        tracked_legs = []
        sim_run_ids = []
        snapshot_ids = []
        
        for leg_data in legs_data:
            # Capture odds snapshot
            snapshot_id = self._capture_leg_snapshot(leg_data)
            snapshot_ids.append(snapshot_id)
            
            # Create sim_run for this leg evaluation
            sim_run_id = sim_run_tracker.create_sim_run(
                event_id=leg_data["event_id"],
                trigger=trigger,
                sim_count=leg_data.get("sim_count", 100000),
                model_version=self.model_version,
                feature_set_version=self.feature_set_version,
                decision_policy_version=self.decision_policy_version,
                seed_policy="rolled"
            )
            
            # Record inputs
            sim_run_tracker.record_sim_run_inputs(
                sim_run_id=sim_run_id,
                snapshot_id=snapshot_id
            )
            
            sim_run_ids.append(sim_run_id)
            
            # Convert to Leg object for parlay_architect
            leg = self._convert_to_leg(leg_data)
            tracked_legs.append(leg)
        
        # Step 2: Run parlay builder
        request = ParlayRequest(
            profile=profile,
            legs=leg_count,
            allow_same_event=allow_same_event,
            allow_same_team=allow_same_team,
            seed=seed,
            include_props=include_props
        )
        
        parlay_result = build_parlay(tracked_legs, request)
        
        # Step 3: Create prediction records for selected legs (if successful)
        prediction_ids = []
        
        if parlay_result.status == "PARLAY":
            for i, leg in enumerate(parlay_result.legs_selected):
                # Find corresponding sim_run_id
                leg_index = tracked_legs.index(leg)
                sim_run_id = sim_run_ids[leg_index]
                snapshot_id = snapshot_ids[leg_index]
                
                # Create prediction
                prediction_id = sim_run_tracker.create_prediction(
                    sim_run_id=sim_run_id,
                    event_id=leg.event_id,
                    market_key=self._market_type_to_key(leg.market_type),
                    selection=self._extract_selection(leg.selection),
                    market_snapshot_id_used=snapshot_id,
                    model_line=None,  # Extract from simulation if available
                    p_win=None,
                    p_cover=leg.confidence / 100.0,  # Normalize to 0-1
                    p_over=None,
                    ev_units=leg.ev,
                    edge_points=leg.total_deviation,
                    uncertainty=None,
                    distribution_summary={},
                    rcl_gate_pass=True,  # Parlay legs passed gates
                    recommendation_state=leg.tier.value,
                    tier=leg.tier.value,
                    confidence_index=leg.confidence / 100.0,
                    variance_bucket=leg.volatility
                )
                
                prediction_ids.append(prediction_id)
                
                # Complete sim_run
                sim_run_tracker.complete_sim_run(sim_run_id, runtime_ms=0)
        
        return {
            "parlay_result": parlay_result,
            "sim_run_ids": sim_run_ids,
            "prediction_ids": prediction_ids,
            "snapshot_ids": snapshot_ids,
            "ready_to_publish": parlay_result.status == "PARLAY" and len(prediction_ids) > 0
        }
    
    def publish_parlay(
        self,
        parlay_data: Dict[str, Any],
        channel: str = "telegram",
        visibility: str = "premium",
        copy_template_id: Optional[str] = None
    ) -> List[str]:
        """
        Publish a parlay (publishes each leg)
        
        Args:
            parlay_data: Result from build_tracked_parlay()
            channel: telegram, app, web
            visibility: free, premium, truth
            
        Returns:
            List of publish_ids
        """
        if not parlay_data.get("ready_to_publish"):
            raise ValueError("Parlay not ready to publish")
        
        publish_ids = []
        parlay_result = parlay_data["parlay_result"]
        prediction_ids = parlay_data["prediction_ids"]
        
        for i, prediction_id in enumerate(prediction_ids):
            leg = parlay_result.legs_selected[i]
            
            publish_id = publishing_service.publish_prediction(
                prediction_id=prediction_id,
                channel=channel,
                visibility=visibility,
                decision_reason_codes=[
                    f"PARLAY_{parlay_result.profile.upper()}",
                    f"TIER_{leg.tier.value}",
                    f"CONFIDENCE_{int(leg.confidence)}"
                ],
                ticket_terms={
                    "selection": leg.selection,
                    "market_type": leg.market_type.value,
                    "tier": leg.tier.value
                },
                copy_template_id=copy_template_id,
                is_official=True
            )
            
            publish_ids.append(publish_id)
        
        logger.info(
            f"📢 Published parlay: {len(publish_ids)} legs "
            f"({parlay_result.profile}, channel={channel})"
        )
        
        return publish_ids
    
    def _capture_leg_snapshot(self, leg_data: Dict[str, Any]) -> str:
        """
        Capture odds snapshot for a leg
        """
        # Extract odds data
        odds = leg_data.get("odds", {})
        
        snapshot_id = snapshot_service.capture_odds_snapshot(
            event_id=leg_data["event_id"],
            provider=odds.get("provider", "OddsAPI"),
            book=odds.get("book", "consensus"),
            market_key=self._market_type_to_key(leg_data.get("market_type", "SPREAD")),
            selection=self._extract_selection(leg_data.get("selection", "HOME")),
            line=odds.get("line"),
            price_american=odds.get("price", -110),
            raw_payload=leg_data
        )
        
        return snapshot_id
    
    def _convert_to_leg(self, leg_data: Dict[str, Any]) -> Leg:
        """
        Convert leg data dict to Leg object
        """
        # Derive tier from canonical state
        tier = derive_tier(
            canonical_state=leg_data.get("canonical_state", "PICK"),
            confidence=leg_data.get("confidence", 55.0),
            ev=leg_data.get("ev", 0.0),
            sport=leg_data.get("sport")
        )
        
        return Leg(
            event_id=leg_data["event_id"],
            sport=leg_data.get("sport", "unknown"),
            league=leg_data.get("league", "unknown"),
            start_time_utc=leg_data.get("start_time_utc", datetime.now()),
            market_type=MarketType(leg_data.get("market_type", "SPREAD")),
            selection=leg_data.get("selection", "HOME"),
            tier=tier,
            confidence=leg_data.get("confidence", 55.0),
            clv=leg_data.get("clv", 0.0),
            total_deviation=leg_data.get("total_deviation", 0.0),
            volatility=leg_data.get("volatility", "MEDIUM"),
            ev=leg_data.get("ev", 0.0),
            di_pass=leg_data.get("di_pass", True),
            mv_pass=leg_data.get("mv_pass", True),
            is_locked=leg_data.get("is_locked", False),
            injury_stable=leg_data.get("injury_stable", True),
            team_key=leg_data.get("team_key"),
            canonical_state=leg_data.get("canonical_state")
        )
    
    def _market_type_to_key(self, market_type: str) -> str:
        """
        Convert market type to canonical market key
        """
        mapping = {
            "SPREAD": "SPREAD:FULL_GAME",
            "TOTAL": "TOTAL:FULL_GAME",
            "MONEYLINE": "MONEYLINE:FULL_GAME",
            "PROP": "PROP"
        }
        
        return mapping.get(market_type, "SPREAD:FULL_GAME")
    
    def _extract_selection(self, selection_str: str) -> str:
        """
        Extract clean selection (HOME/AWAY/OVER/UNDER)
        """
        selection_upper = selection_str.upper()
        
        if "HOME" in selection_upper or selection_upper.startswith("H"):
            return "HOME"
        elif "AWAY" in selection_upper or selection_upper.startswith("A"):
            return "AWAY"
        elif "OVER" in selection_upper or selection_upper.startswith("O"):
            return "OVER"
        elif "UNDER" in selection_upper or selection_upper.startswith("U"):
            return "UNDER"
        
        return selection_str


# Singleton instance
parlay_adapter = ParlayArchitectAdapter()

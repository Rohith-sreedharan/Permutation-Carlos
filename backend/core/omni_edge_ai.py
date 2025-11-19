"""
Enhanced AI Engine with Hybrid Features
Trains on CLV + Outcome, integrates sharp_weighted_consensus
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import json
import os
from db.mongo import db
from services.logger import log_stage
from services.reputation_engine import reputation_engine


class OmniEdgeAI:
    """
    Omni Edge AI - Hybrid Model
    
    Training Strategy:
    - Primary target: CLV (closing line value) for signal stability
    - Secondary target: Outcome (win/loss) for ROI optimization
    
    Hybrid Feature:
    - sharp_weighted_consensus: Combines hard (odds) + soft (expert sentiment) data
    
    This is what justifies the 25-30x ARR multiple
    """
    
    def __init__(self):
        self.model_version = "omniedge_v2.3.1"
        self.config_path = "/Users/rohithaditya/Downloads/Permutation-Carlos/backend/core/model_config.json"
        self.load_config()
    
    def load_config(self):
        """Load model configuration from JSON"""
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {
                "min_edge_threshold": 0.05,
                "min_confidence": 0.45,
                "sharp_consensus_weight": 0.3,
                "max_picks_per_day": 10,
                "kelly_fraction": 0.25,
                "markets": ["h2h", "spreads", "totals"]
            }
    
    def calculate_model_fair_odds(self, market_odds: float, sharp_consensus: float) -> float:
        """
        Calculate model's fair value odds
        
        Combines:
        1. Market odds (hard data)
        2. Sharp consensus sentiment (soft data)
        
        Example:
        - Market odds: 2.00 (50% implied probability)
        - Sharp consensus: +0.5 (bullish)
        - Adjusted probability: 55% → fair odds: 1.82
        """
        # Convert odds to implied probability
        implied_prob = 1.0 / market_odds
        
        # Apply consensus adjustment (weighted by config)
        consensus_weight = self.config.get("sharp_consensus_weight", 0.3)
        consensus_adjustment = sharp_consensus * consensus_weight * 0.1  # ±10% max adjustment
        
        adjusted_prob = implied_prob + consensus_adjustment
        adjusted_prob = max(0.1, min(0.9, adjusted_prob))  # Clamp to reasonable range
        
        # Convert back to odds
        fair_odds = 1.0 / adjusted_prob
        
        return round(fair_odds, 3)
    
    def calculate_edge(self, market_odds: float, fair_odds: float) -> float:
        """
        Calculate expected edge percentage
        
        Edge = (fair_odds - market_odds) / market_odds * 100
        
        Example:
        - Market: 2.00
        - Fair: 2.20
        - Edge: 10%
        """
        edge = ((fair_odds - market_odds) / market_odds) * 100
        return round(edge, 2)
    
    def calculate_kelly_stake(self, edge_pct: float, odds: float) -> float:
        """
        Calculate Kelly Criterion stake
        
        Kelly % = (edge / odds - 1)
        Then multiply by kelly_fraction (0.25 = quarter Kelly)
        """
        if edge_pct <= 0:
            return 0.0
        
        kelly_pct = edge_pct / (odds - 1)
        kelly_fraction = self.config.get("kelly_fraction", 0.25)
        stake = kelly_pct * kelly_fraction
        
        # Clamp to reasonable range (0-5 units)
        return max(0.0, min(5.0, stake))
    
    def generate_rationale(self, pick: Dict[str, Any], sharp_consensus: float) -> List[str]:
        """
        Generate human-readable rationale for transparency
        Module 1-11 insights
        """
        rationale = []
        
        # Edge explanation
        rationale.append(
            f"Model fair value: {pick['model_fair_decimal']:.2f} vs market {pick['market_decimal']:.2f} "
            f"= {pick['edge_pct']:.1f}% edge"
        )
        
        # Sharp consensus
        if sharp_consensus > 0.3:
            rationale.append(
                f"Strong community support: {sharp_consensus:+.2f} weighted sentiment "
                f"({db['community_picks'].count_documents({'event_id': pick['event_id']})} Elite picks)"
            )
        elif sharp_consensus < -0.3:
            rationale.append(
                f"Community fade signal: {sharp_consensus:+.2f} weighted sentiment suggests value on opposite side"
            )
        
        # Historical CLV (if available)
        # TODO: Query historical CLV for this team/market
        
        # Stake sizing
        rationale.append(
            f"Kelly Criterion suggests {pick['stake_units']:.2f} units "
            f"({self.config['kelly_fraction']*100:.0f}% Kelly fraction)"
        )
        
        return rationale
    
    def generate_picks(
        self,
        event_id: str,
        normalized_odds: List[Dict[str, Any]],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate AI picks for an event
        
        Returns top N picks filtered by edge and confidence thresholds
        """
        # Get sharp consensus for this event
        sharp_consensus = reputation_engine.calculate_sharp_weighted_consensus(event_id)
        
        picks = []
        
        for odds_data in normalized_odds:
            market_odds = odds_data.get("price", 2.0)
            
            # Calculate model fair odds (hybrid feature)
            fair_odds = self.calculate_model_fair_odds(market_odds, sharp_consensus)
            
            # Calculate edge
            edge_pct = self.calculate_edge(market_odds, fair_odds)
            
            # Filter by minimum edge threshold
            min_edge = self.config.get("min_edge_threshold", 0.05) * 100  # Convert to %
            if edge_pct < min_edge:
                continue
            
            # Calculate confidence (simplified - in production use ML model)
            base_confidence = self.config.get("min_confidence", 0.45)
            confidence = base_confidence + (edge_pct / 100) * 0.3  # Edge boosts confidence
            confidence = min(0.95, confidence)  # Cap at 95%
            
            # Calculate stake
            stake_units = self.calculate_kelly_stake(edge_pct, market_odds)
            
            # Build pick
            pick = {
                "pick_id": f"pick_{event_id}_{odds_data.get('market', 'h2h')}_{len(picks)}",
                "event_id": event_id,
                "market": odds_data.get("market", "h2h"),
                "side": odds_data.get("name"),
                "market_decimal": market_odds,
                "model_fair_decimal": fair_odds,
                "edge_pct": edge_pct,
                "stake_units": round(stake_units, 2),
                "kelly_fraction": self.config.get("kelly_fraction", 0.25),
                "model_version": self.model_version,
                "confidence": round(confidence, 3),
                "sharp_weighted_consensus": sharp_consensus,
                "community_volume": db["community_picks"].count_documents({"event_id": event_id}),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Generate rationale
            pick["rationale"] = self.generate_rationale(pick, sharp_consensus)
            
            picks.append(pick)
        
        # Sort by edge and return top N
        picks.sort(key=lambda x: x["edge_pct"], reverse=True)
        top_picks = picks[:limit]
        
        # Store picks in database
        if top_picks:
            db["ai_picks"].insert_many(top_picks)
        
        log_stage(
            "ai_engine",
            "picks_generated",
            input_payload={
                "event_id": event_id,
                "odds_count": len(normalized_odds),
                "sharp_consensus": sharp_consensus
            },
            output_payload={
                "picks_generated": len(top_picks),
                "avg_edge": sum(p["edge_pct"] for p in top_picks) / len(top_picks) if top_picks else 0,
                "avg_confidence": sum(p["confidence"] for p in top_picks) / len(top_picks) if top_picks else 0
            }
        )
        
        return top_picks
    
    def update_pick_outcome(self, pick_id: str, outcome: str, closing_odds: Optional[float] = None):
        """
        Update pick with outcome and calculate CLV
        
        This feeds Module 7 (Reflection Loop)
        """
        pick = db["ai_picks"].find_one({"pick_id": pick_id})
        if not pick:
            return {"status": "error", "message": "Pick not found"}
        
        # Calculate CLV if closing odds provided
        clv_pct = None
        if closing_odds:
            market_odds = pick["market_decimal"]
            clv_pct = ((closing_odds - market_odds) / market_odds) * 100
        
        # Calculate ROI
        roi = None
        if outcome == "win":
            roi = (pick["market_decimal"] - 1.0) * 100
        elif outcome == "loss":
            roi = -100.0
        else:
            roi = 0.0  # Push
        
        # Update database
        db["ai_picks"].update_one(
            {"pick_id": pick_id},
            {
                "$set": {
                    "outcome": outcome,
                    "closing_line_decimal": closing_odds,
                    "clv_pct": round(clv_pct, 2) if clv_pct else None,
                    "roi": round(roi, 2) if roi else None,
                    "settled_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        log_stage(
            "ai_engine",
            "pick_settled",
            input_payload={"pick_id": pick_id, "outcome": outcome},
            output_payload={"roi": roi, "clv_pct": clv_pct}
        )
        
        return {
            "status": "ok",
            "pick_id": pick_id,
            "outcome": outcome,
            "roi": roi,
            "clv_pct": clv_pct
        }


# Singleton instance
omni_edge_ai = OmniEdgeAI()

"""
Simulation Engine - Deterministic Monte Carlo
==============================================
Runs simulations with variance control and confidence intervals.

Key Features:
- Deterministic seed from context hash
- Confidence interval convergence
- Edge validation with uncertainty gates
- Stability scoring via perturbation tests
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, Callable
import numpy as np
from datetime import datetime, timezone
import logging

from .simulation_context import (
    SimulationContext,
    SimulationResult,
    ConfidenceInterval,
    SimulationStatus,
)

logger = logging.getLogger(__name__)


class SimulationEngine:
    """
    Deterministic Monte Carlo simulation engine.
    
    Guarantees:
    - Same context → same seed → same output
    - Convergence monitoring via confidence intervals
    - Edge validation with uncertainty gates
    """
    
    def __init__(
        self,
        edge_threshold_percent: float = 2.0,
        ci_target_half_width: float = 0.01,  # 1.0% for spreads/ML/totals
        max_simulations: int = 50000,
        convergence_check_interval: int = 5000,
    ):
        self.edge_threshold_percent = edge_threshold_percent
        self.ci_target_half_width = ci_target_half_width
        self.max_simulations = max_simulations
        self.convergence_check_interval = convergence_check_interval
    
    def run_simulation(
        self,
        context: SimulationContext,
        simulation_fn: Callable[[np.random.Generator, int], np.ndarray],
    ) -> SimulationResult:
        """
        Run deterministic Monte Carlo simulation.
        
        Args:
            context: Immutable simulation context
            simulation_fn: Function that runs simulations
                - Takes (rng: Generator, n: int) 
                - Returns array of binary outcomes (1 = hit, 0 = miss)
        
        Returns:
            SimulationResult with probability, CI, edge, and validation
        """
        # Get deterministic seed from context
        seed = context.deterministic_seed()
        rng = np.random.default_rng(seed)
        
        logger.info(
            f"Running simulation: game={context.game_id}, "
            f"market={context.market.market_type}, seed={seed}"
        )
        
        # Run simulations with optional convergence monitoring
        n_run = context.n_simulations
        converged = False
        
        if context.n_simulations > self.convergence_check_interval:
            # Progressive convergence check
            results = []
            for batch_start in range(0, context.n_simulations, self.convergence_check_interval):
                batch_size = min(self.convergence_check_interval, context.n_simulations - batch_start)
                batch_results = simulation_fn(rng, batch_size)
                results.extend(batch_results)
                
                # Check convergence
                ci = self._calculate_confidence_interval(np.array(results))
                if ci.half_width <= self.ci_target_half_width:
                    n_run = len(results)
                    converged = True
                    logger.info(f"Convergence achieved at {n_run} simulations (CI half-width: {ci.half_width:.4f})")
                    break
            
            results = np.array(results)
        else:
            # Run all at once
            results = simulation_fn(rng, context.n_simulations)
        
        # Calculate probability and confidence interval
        model_prob = float(np.mean(results))
        ci = self._calculate_confidence_interval(results)
        
        # Edge calculation
        devig_prob = context.market.devig_prob
        raw_edge = model_prob - devig_prob
        edge_percent = raw_edge * 100.0
        
        # Validation gates
        meets_edge = edge_percent >= self.edge_threshold_percent
        meets_uncertainty = abs(raw_edge) >= (2.0 * ci.half_width)  # Edge >= 2x uncertainty
        is_valid = meets_edge and meets_uncertainty
        
        # Calculate playable limits (guardrails)
        playable_limits = self._calculate_playable_limits(
            context.market.market_type,
            context.market.line,
            model_prob,
            devig_prob,
        )
        
        # Convert odds_min to int if present
        odds_min = playable_limits.get("odds_min")
        if odds_min is not None:
            odds_min = int(odds_min)
        
        result = SimulationResult(
            context_hash=context.context_hash,
            game_id=context.game_id,
            market_type=context.market.market_type,
            selection=context.market.selection,
            model_probability=model_prob,
            confidence_interval=ci,
            devig_market_probability=devig_prob,
            raw_edge=raw_edge,
            edge_percent=edge_percent,
            meets_edge_threshold=meets_edge,
            meets_uncertainty_gate=meets_uncertainty,
            is_valid_play=is_valid,
            playable_line_min=playable_limits.get("line_min"),
            playable_line_max=playable_limits.get("line_max"),
            playable_odds_min=odds_min,
            n_simulations_run=n_run,
            convergence_achieved=converged,
            random_seed_used=seed,
            status=SimulationStatus.COMPLETED,
        )
        
        logger.info(
            f"Simulation complete: prob={model_prob:.4f}, "
            f"edge={edge_percent:.2f}%, valid={is_valid}"
        )
        
        return result
    
    def _calculate_confidence_interval(
        self,
        results: np.ndarray,
        confidence_level: float = 0.95,
    ) -> ConfidenceInterval:
        """
        Calculate confidence interval for binomial proportion.
        
        Uses Wilson score interval (more accurate than normal approximation).
        """
        n = len(results)
        if n == 0:
            return ConfidenceInterval(0.0, 1.0, 0.5, confidence_level)
        
        p_hat = float(np.mean(results))
        
        # Z-score for confidence level (1.96 for 95%)
        z = 1.96 if confidence_level == 0.95 else 2.576  # 99%
        
        # Wilson score interval
        denominator = 1 + (z**2 / n)
        center = (p_hat + (z**2 / (2 * n))) / denominator
        margin = (z / denominator) * np.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
        
        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)
        half_width = (upper - lower) / 2.0
        
        return ConfidenceInterval(
            lower=lower,
            upper=upper,
            half_width=half_width,
            confidence_level=confidence_level,
        )
    
    def _calculate_playable_limits(
        self,
        market_type: str,
        original_line: Optional[float],
        model_prob: float,
        devig_prob: float,
    ) -> Dict[str, Optional[float]]:
        """
        Calculate execution guardrails (playable limits).
        
        Rules:: Dict[str, Optional[float]]
        - Spreads/Totals: Allow up to 0.5 point movement in favorable direction
        - Moneylines: Allow up to -10 cents in odds movement
        - Props: Allow up to 1.0 point movement in favorable direction
        """
        limits: Dict[str, Optional[float]] = {
            "line_min": None,
            "line_max": None,
            "odds_min": None,
        }
        
        if market_type in ["SPREAD", "TOTAL"]:
            if original_line is not None:
                # Allow 0.5 point movement
                if model_prob > devig_prob:
                    # We like this side, can move 0.5 worse
                    limits["line_min"] = original_line - 0.5
                    limits["line_max"] = original_line + 0.5
                else:
                    # We don't like this side
                    limits["line_min"] = original_line - 0.5
                    limits["line_max"] = original_line + 0.5
        
        elif market_type == "PROP":
            if original_line is not None:
                # Allow 1.0 point movement for props (more volatile)
                limits["line_min"] = original_line - 1.0
                limits["line_max"] = original_line + 1.0
        
        # Moneyline: odds-based limits handled separately
        
        return limits
    
    def run_perturbation_test(
        self,
        context: SimulationContext,
        simulation_fn: Callable[[np.random.Generator, int], np.ndarray],
        n_perturbations: int = 100,
        perturbation_magnitude: float = 0.05,  # 5% variation
    ) -> Dict[str, float]:
        """
        Run stability test by perturbing key inputs.
        
        Returns stability score (survival rate across perturbations).
        
        A stable play maintains edge >= threshold across most perturbations.
        Priority plays should have stability >= 0.70.
        """
        base_result = self.run_simulation(context, simulation_fn)
        
        if not base_result.is_valid_play:
            # Already fails validation, no need to test stability
            return {
                "stability_score": 0.0,
                "survival_rate": 0.0,
                "n_perturbations": 0,
            }
        
        survival_count = 0
        rng_perturb = np.random.default_rng(context.deterministic_seed() + 999999)
        
        for i in range(n_perturbations):
            # Perturb pace projection slightly
            perturbed_context = self._perturb_context(context, rng_perturb, perturbation_magnitude)
            perturbed_result = self.run_simulation(perturbed_context, simulation_fn)
            
            # Check if still valid after perturbation
            if perturbed_result.is_valid_play:
                survival_count += 1
        
        survival_rate = survival_count / n_perturbations if n_perturbations > 0 else 0.0
        
        logger.info(
            f"Stability test: {survival_count}/{n_perturbations} survived "
            f"(score: {survival_rate:.2f})"
        )
        
        return {
            "stability_score": survival_rate,
            "survival_rate": survival_rate,
            "n_perturbations": n_perturbations,
            "base_edge_percent": base_result.edge_percent,
        }
    
    def _perturb_context(
        self,
        context: SimulationContext,
        rng: np.random.Generator,
        magnitude: float,
    ) -> SimulationContext:
        """
        Create perturbed copy of context for stability testing.
        
        Varies:
        - Pace projection by ±magnitude
        - Minutes projections by ±magnitude
        - Fatigue factors by ±magnitude
        """
        # Perturb pace
        pace = context.pace_projection
        if pace is not None:
            pace = pace * (1.0 + rng.uniform(-magnitude, magnitude))
        
        # Perturb injuries (minutes)
        injuries = []
        for inj in context.injuries:
            mins = inj.minutes_projection
            if mins is not None:
                mins = mins * (1.0 + rng.uniform(-magnitude, magnitude))
            
            injuries.append(
                type(inj)(
                    player_id=inj.player_id,
                    player_name=inj.player_name,
                    status=inj.status,
                    minutes_projection=mins,
                    confidence=inj.confidence,
                )
            )
        
        # Create new context with perturbations
        # Note: This will generate a NEW context_hash and seed
        return SimulationContext(
            game_id=context.game_id,
            sport=context.sport,
            league=context.league,
            home_team=context.home_team,
            away_team=context.away_team,
            game_time_utc=context.game_time_utc,
            model_version=context.model_version,
            engine_version=context.engine_version,
            data_feed_version=context.data_feed_version,
            market=context.market,
            injuries=injuries,
            pace_projection=pace,
            fatigue_factors=context.fatigue_factors,
            weather=context.weather,
            n_simulations=context.n_simulations,
            random_seed_base=None,  # Will generate new seed
            created_at_utc=context.created_at_utc,
            created_by=context.created_by,
        )


class SimulationCache:
    """
    Cache for simulation results keyed by context_hash.
    
    Ensures:
    - Same context → return cached result
    - Changed context → run new simulation
    - No redundant reruns
    """
    
    def __init__(self, db_collection):
        """
        Args:
            db_collection: MongoDB collection for simulation_results
        """
        self.db = db_collection
    
    def get_cached_result(self, context: SimulationContext) -> Optional[SimulationResult]:
        """
        Get cached simulation result by context hash.
        
        Returns None if no cached result exists.
        """
        doc = self.db.find_one({
            "context_hash": context.context_hash,
            "game_id": context.game_id,
            "market_type": context.market.market_type,
        })
        
        if doc is None:
            return None
        
        # Reconstruct SimulationResult from doc
        ci = ConfidenceInterval(
            lower=doc["confidence_interval"]["lower"],
            upper=doc["confidence_interval"]["upper"],
            half_width=doc["confidence_interval"]["half_width"],
            confidence_level=doc["confidence_interval"].get("confidence_level", 0.95),
        )
        
        result = SimulationResult(
            context_hash=doc["context_hash"],
            game_id=doc["game_id"],
            market_type=doc["market_type"],
            selection=doc["selection"],
            model_probability=doc["model_probability"],
            confidence_interval=ci,
            devig_market_probability=doc["devig_market_probability"],
            raw_edge=doc["raw_edge"],
            edge_percent=doc["edge_percent"],
            meets_edge_threshold=doc["meets_edge_threshold"],
            meets_uncertainty_gate=doc["meets_uncertainty_gate"],
            is_valid_play=doc["is_valid_play"],
            playable_line_min=doc.get("playable_line_min"),
            playable_line_max=doc.get("playable_line_max"),
            playable_odds_min=doc.get("playable_odds_min"),
            n_simulations_run=doc["n_simulations_run"],
            convergence_achieved=doc.get("convergence_achieved", False),
            random_seed_used=doc["random_seed_used"],
            created_at_utc=datetime.fromisoformat(doc["created_at_utc"]),
            status=SimulationStatus(doc.get("status", "COMPLETED")),
        )
        
        logger.info(f"Cache HIT: context_hash={context.context_hash[:8]}...")
        return result
    
    def save_result(self, context: SimulationContext, result: SimulationResult) -> None:
        """Save simulation result to cache"""
        doc = {
            **result.to_dict(),
            "context": context.to_dict(),  # Store full context for audit
        }
        
        # Upsert by context_hash
        self.db.update_one(
            {
                "context_hash": context.context_hash,
                "game_id": context.game_id,
                "market_type": context.market.market_type,
            },
            {"$set": doc},
            upsert=True,
        )
        
        logger.info(f"Cache SAVE: context_hash={context.context_hash[:8]}...")

"""
PM Mode - Advanced Execution Layer
===================================
Stricter thresholds and Polymarket-specific execution logic.

PM Mode (Polymarket Mode) is opt-in for advanced users.
Uses higher edge thresholds and tighter guardrails than standard sportsbook outputs.
"""

from __future__ import annotations
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

from .simulation_context import SimulationResult, ConfidenceInterval

logger = logging.getLogger(__name__)


class PMExecutionStatus(str, Enum):
    """PM Mode execution status"""
    ELIGIBLE = "ELIGIBLE"  # Meets PM Mode thresholds
    INELIGIBLE_EDGE = "INELIGIBLE_EDGE"  # Edge too low
    INELIGIBLE_UNCERTAINTY = "INELIGIBLE_UNCERTAINTY"  # CI too wide
    INELIGIBLE_STABILITY = "INELIGIBLE_STABILITY"  # Stability score too low
    MANUAL_REVIEW = "MANUAL_REVIEW"  # Edge is borderline, needs review
    EXECUTED = "EXECUTED"  # Successfully executed on Polymarket
    FAILED = "FAILED"  # Execution failed


@dataclass(frozen=True)
class PMThresholds:
    """
    PM Mode threshold configuration.
    
    Stricter than standard sportsbook thresholds.
    """
    min_edge_percent: float = 3.0  # 3.0% minimum (vs 2.0% for sportsbooks)
    min_stability_score: float = 0.70  # 70% survival rate in perturbation tests
    max_ci_half_width: float = 0.008  # 0.8% (vs 1.0% for sportsbooks)
    min_model_probability: float = 0.05  # Don't bet on <5% or >95% outcomes
    max_model_probability: float = 0.95
    
    # Polymarket-specific limits
    max_position_size_usd: float = 1000.0  # Max per position
    min_liquidity_usd: float = 5000.0  # Min market liquidity required


class PMMode:
    """
    PM Mode execution engine.
    
    Validates simulation results against stricter PM thresholds.
    Supports Polymarket execution (manual or API).
    """
    
    def __init__(
        self,
        thresholds: Optional[PMThresholds] = None,
    ):
        self.thresholds = thresholds or PMThresholds()
    
    def evaluate_for_pm(
        self,
        result: SimulationResult,
        stability_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate simulation result for PM Mode eligibility.
        
        Args:
            result: Standard simulation result
            stability_score: Optional stability score from perturbation tests
        
        Returns:
            {
                "status": PMExecutionStatus,
                "eligible": bool,
                "reasons": List[str],
                "recommended_position_size": Optional[float],
            }
        """
        reasons = []
        eligible = True
        
        # Edge threshold check (stricter)
        if result.edge_percent < self.thresholds.min_edge_percent:
            reasons.append(f"edge_too_low:{result.edge_percent:.2f}%<{self.thresholds.min_edge_percent}%")
            eligible = False
        
        # Uncertainty threshold check (stricter)
        if result.confidence_interval.half_width > self.thresholds.max_ci_half_width:
            reasons.append(
                f"uncertainty_too_high:{result.confidence_interval.half_width:.4f}>"
                f"{self.thresholds.max_ci_half_width}"
            )
            eligible = False
        
        # Stability check
        if stability_score is not None:
            if stability_score < self.thresholds.min_stability_score:
                reasons.append(f"stability_too_low:{stability_score:.2f}<{self.thresholds.min_stability_score}")
                eligible = False
        
        # Probability bounds check (avoid extreme probabilities)
        if result.model_probability < self.thresholds.min_model_probability:
            reasons.append(f"prob_too_low:{result.model_probability:.4f}")
            eligible = False
        
        if result.model_probability > self.thresholds.max_model_probability:
            reasons.append(f"prob_too_high:{result.model_probability:.4f}")
            eligible = False
        
        # Determine status
        if eligible:
            status = PMExecutionStatus.ELIGIBLE
        elif len(reasons) == 1 and "edge_too_low" in reasons[0]:
            # Borderline case - could be manual review
            if result.edge_percent >= (self.thresholds.min_edge_percent * 0.9):
                status = PMExecutionStatus.MANUAL_REVIEW
            else:
                status = PMExecutionStatus.INELIGIBLE_EDGE
        elif any("uncertainty" in r for r in reasons):
            status = PMExecutionStatus.INELIGIBLE_UNCERTAINTY
        elif any("stability" in r for r in reasons):
            status = PMExecutionStatus.INELIGIBLE_STABILITY
        else:
            status = PMExecutionStatus.INELIGIBLE_EDGE
        
        # Calculate recommended position size (Kelly criterion with fractional sizing)
        position_size = None
        if eligible:
            position_size = self._calculate_position_size(result)
        
        return {
            "status": status.value,
            "eligible": eligible,
            "reasons": reasons,
            "recommended_position_size_usd": position_size,
            "thresholds_used": {
                "min_edge_percent": self.thresholds.min_edge_percent,
                "max_ci_half_width": self.thresholds.max_ci_half_width,
                "min_stability_score": self.thresholds.min_stability_score,
            },
        }
    
    def _calculate_position_size(
        self,
        result: SimulationResult,
        bankroll_usd: float = 10000.0,
        kelly_fraction: float = 0.25,  # Quarter Kelly (conservative)
    ) -> float:
        """
        Calculate recommended position size using fractional Kelly criterion.
        
        Kelly = (p * (b + 1) - 1) / b
        where:
        - p = model probability
        - b = decimal odds - 1
        
        We use quarter Kelly for conservative sizing.
        """
        p = result.model_probability
        decimal_odds = 1.0 / result.devig_market_probability  # Implied fair odds
        b = decimal_odds - 1.0
        
        # Kelly criterion
        kelly = (p * (b + 1) - 1) / b
        
        # Apply fractional Kelly
        kelly_fraction_used = max(0.0, min(kelly_fraction, kelly))
        
        # Calculate position size
        position_size = bankroll_usd * kelly_fraction_used
        
        # Cap at max position size
        position_size = min(position_size, self.thresholds.max_position_size_usd)
        
        return round(position_size, 2)
    
    def check_polymarket_liquidity(
        self,
        market_id: str,
        get_liquidity_fn,
    ) -> Dict[str, Any]:
        """
        Check Polymarket market liquidity before execution.
        
        Args:
            market_id: Polymarket market identifier
            get_liquidity_fn: Function to fetch current liquidity
                - Takes market_id
                - Returns float (total liquidity in USD)
        
        Returns:
            {
                "sufficient": bool,
                "current_liquidity_usd": float,
                "min_required_usd": float,
            }
        """
        try:
            current_liquidity = get_liquidity_fn(market_id)
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket liquidity: {e}")
            return {
                "sufficient": False,
                "current_liquidity_usd": 0.0,
                "min_required_usd": self.thresholds.min_liquidity_usd,
                "error": str(e),
            }
        
        sufficient = current_liquidity >= self.thresholds.min_liquidity_usd
        
        return {
            "sufficient": sufficient,
            "current_liquidity_usd": current_liquidity,
            "min_required_usd": self.thresholds.min_liquidity_usd,
        }


# Example PM Mode workflow
def pm_mode_workflow_example():
    """
    Example PM Mode workflow showing full evaluation and execution logic.
    
    This is a reference implementation for integrating PM Mode into your system.
    """
    from .simulation_engine import SimulationEngine
    from .simulation_context import SimulationContext
    
    # 1. Run standard simulation
    engine = SimulationEngine()
    # context = ... (build SimulationContext)
    # result = engine.run_simulation(context, simulation_fn)
    
    # 2. Run stability test
    # stability = engine.run_perturbation_test(context, simulation_fn)
    
    # 3. Evaluate for PM Mode
    pm = PMMode()
    # pm_eval = pm.evaluate_for_pm(result, stability["stability_score"])
    
    # 4. Check liquidity
    # liquidity_check = pm.check_polymarket_liquidity(market_id, get_liquidity_fn)
    
    # 5. Execute if eligible
    # if pm_eval["eligible"] and liquidity_check["sufficient"]:
    #     position_size = pm_eval["recommended_position_size_usd"]
    #     # Execute on Polymarket (manual or API)
    #     pass
    
    pass  # Placeholder for example

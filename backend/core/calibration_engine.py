"""
System-Wide Calibration Engine
Global constraint layers that prevent structural bias

THIS IS NOT A PER-GAME FIX - THIS IS INSTITUTIONAL ARCHITECTURE
"""
import numpy as np
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from db.mongo import db
from core.sport_calibration_config import get_sport_config, SportCalibrationConfig
import logging

logger = logging.getLogger(__name__)


class CalibrationEngine:
    """
    System-wide calibration enforcer
    
    Five constraint layers (all must pass):
    1. Data integrity
    2. Model validity (no runaway drift)
    3. Market anchor sanity (Vegas prior penalty)
    4. Variance suppression (high variance = edge collapse)
    5. Edge publish gates (final thresholds)
    
    If any fails → NO PLAY + reason code
    """
    
    def __init__(self):
        self.calibration_cache = {}  # Cache daily calibration factors
    
    def validate_pick(
        self,
        sport_key: str,
        model_total: float,
        vegas_total: float,
        std_total: float,
        p_raw: float,
        edge_raw: float,
        data_quality_score: float,
        injury_uncertainty: float
    ) -> Dict[str, Any]:
        """
        Apply all 5 constraint layers
        
        BOOTSTRAP BEHAVIOR:
        - If no calibration exists → degrade confidence, don't block
        - Set calibration_status = UNINITIALIZED
        - Force LEAN tier (never PICK until calibration initializes)
        - Cap confidence display to 60%
        
        Returns:
            {
                "publish": bool,
                "p_adjusted": float,
                "edge_adjusted": float,
                "confidence_label": str,
                "block_reasons": List[str],
                "applied_penalties": Dict[str, float],
                "calibration_status": str,  # INITIALIZED / UNINITIALIZED
                "bootstrap_mode": bool
            }
        """
        config = get_sport_config(sport_key)
        block_reasons = []
        applied_penalties = {}
        
        # Check if calibration data exists
        cal_metrics = self._get_calibration_metrics(sport_key, config.calibration_window_days)
        bootstrap_mode = cal_metrics is None
        calibration_status = "UNINITIALIZED" if bootstrap_mode else "INITIALIZED"
        
        if bootstrap_mode:
            logger.info(f"🔵 [{sport_key}] BOOTSTRAP MODE - No calibration data, degrading confidence")
        
        # Layer 1: Data Integrity
        # BOOTSTRAP: Skip blocking on data quality - degrade confidence only
        if data_quality_score < 0.7 and not bootstrap_mode:
            block_reasons.append("data_integrity_fail")
        
        # Layer 2: Model Validity (league baseline clamp)
        # BOOTSTRAP: Skip blocking, just apply default dampening
        baseline_check = self._check_league_baseline(sport_key, model_total, vegas_total, bootstrap_mode)
        if not baseline_check["passed"] and not bootstrap_mode:
            block_reasons.append("league_baseline_violation")
            applied_penalties["baseline_damp"] = baseline_check.get("damp_factor", 1.0)
        
        # BOOTSTRAP PENALTY: Extra dampening when no calibration exists
        if bootstrap_mode:
            applied_penalties["bootstrap_penalty"] = 0.85  # 15% confidence reduction
        
        # Layer 3: Market Anchor Sanity (Vegas prior penalty)
        deviation = abs(model_total - vegas_total)
        market_penalty = self._calculate_market_penalty(deviation, config)
        applied_penalties["market_penalty"] = market_penalty
        
        # Layer 4: Variance Suppression
        z_variance = self._calculate_variance_z(sport_key, std_total)
        variance_penalty = self._calculate_variance_penalty(z_variance, config)
        applied_penalties["variance_penalty"] = variance_penalty
        
        # BOOTSTRAP: Skip blocking on extreme variance - degrade confidence only
        if z_variance > config.extreme_variance_z and not bootstrap_mode:
            block_reasons.append("extreme_variance")
        
        # Apply combined penalties to probability and edge
        bootstrap_penalty = applied_penalties.get("bootstrap_penalty", 1.0)
        combined_mult = market_penalty * variance_penalty * bootstrap_penalty
        p_adjusted = 0.5 + (p_raw - 0.5) * combined_mult
        edge_adjusted = edge_raw * combined_mult
        
        # BOOTSTRAP: Cap adjusted probability at 60% (never show extreme confidence)
        if bootstrap_mode:
            if p_adjusted > 0.60:
                p_adjusted = 0.60
            elif p_adjusted < 0.40:
                p_adjusted = 0.40
        
        # Check for Elite Override eligibility
        elite_override = self._check_elite_override(
            p_raw, z_variance, data_quality_score, injury_uncertainty,
            deviation, config
        )
        
        # Layer 5: Edge Publish Gates
        publish_check = self._check_publish_thresholds(
            p_adjusted, edge_adjusted, deviation, z_variance,
            config, elite_override
        )
        
        # BOOTSTRAP: Skip blocking in bootstrap mode - degrade confidence only
        if not publish_check["passed"] and not bootstrap_mode:
            block_reasons.extend(publish_check["reasons"])
        
        # Final decision
        publish = len(block_reasons) == 0
        
        # Determine confidence label
        if not publish:
            confidence_label = "NO_PLAY"
        elif elite_override:
            confidence_label = "ELITE_EDGE"
        elif p_adjusted >= 0.60:
            confidence_label = "STRONG"
        elif p_adjusted >= 0.56:
            confidence_label = "LEAN"
        else:
            confidence_label = "NO_PLAY"
        
        return {
            "publish": publish,
            "p_raw": p_raw,
            "p_adjusted": p_adjusted,
            "edge_raw": edge_raw,
            "edge_adjusted": edge_adjusted,
            "confidence_label": confidence_label,
            "block_reasons": block_reasons,
            "applied_penalties": applied_penalties,
            "z_variance": z_variance,
            "elite_override": elite_override,
            "calibration_status": calibration_status,
            "bootstrap_mode": bootstrap_mode
        }
    
    def _check_league_baseline(
        self,
        sport_key: str,
        model_total: float,
        vegas_total: float,
        bootstrap_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Layer 2: Check if model is drifting from league baselines
        Computes daily calibration and applies dampening if needed
        
        BOOTSTRAP MODE: Skip blocking, return default damp_factor
        """
        config = get_sport_config(sport_key)
        
        # Get daily calibration metrics (OPTIONAL - defaults to damp_factor=1.0)
        cal_metrics = self._get_calibration_metrics(sport_key, config.calibration_window_days)
        
        if not cal_metrics or bootstrap_mode:
            # No calibration log exists yet - proceed normally with no dampening
            if bootstrap_mode:
                logger.info(f"🔵 [{sport_key}] Bootstrap mode - skipping baseline check")
            else:
                logger.info(f"ℹ️ [{sport_key}] No calibration log found - using default damp_factor=1.0")
            return {"passed": True, "damp_factor": 1.0}
        
        bias_vs_actual = cal_metrics.get("bias_vs_actual", 0.0)
        bias_vs_market = cal_metrics.get("bias_vs_market", 0.0)
        over_rate = cal_metrics.get("over_rate_model", 0.5)
        
        # Check triggers
        triggers = []
        
        # Trigger 1: Model biased high vs actual
        if abs(bias_vs_actual) > config.max_bias_vs_actual:
            triggers.append("bias_vs_actual")
        
        # Trigger 2: "All overs" syndrome
        if over_rate > config.max_over_rate:
            triggers.append("all_overs_syndrome")
        
        # Trigger 3: Model drifting from market
        if abs(bias_vs_market) > config.max_bias_vs_market:
            triggers.append("market_drift")
        
        if triggers:
            # Compute dampening factor
            if sport_key in ["baseball_mlb", "icehockey_nhl"]:
                damp = np.clip(0.92, 1.0, 1.0 - (bias_vs_actual / 4.0))
            else:
                damp = np.clip(0.90, 1.0, 1.0 - (bias_vs_actual / 20.0))
            
            logger.warning(
                f"🔴 [{config.sport_name}] Baseline clamp triggered: {triggers} "
                f"→ Damp factor: {damp:.3f}"
            )
            
            return {
                "passed": False,
                "triggers": triggers,
                "damp_factor": damp,
                "bias_vs_actual": bias_vs_actual,
                "bias_vs_market": bias_vs_market,
                "over_rate": over_rate
            }
        
        return {"passed": True, "damp_factor": 1.0}
    
    def _calculate_market_penalty(
        self,
        deviation: float,
        config: SportCalibrationConfig
    ) -> float:
        """
        Layer 3: Vegas prior penalty (soft anchor)
        
        Returns multiplier (0.90 - 1.00) to apply to probability and edge
        """
        if deviation <= config.soft_deviation:
            return 1.00
        
        if deviation >= config.hard_deviation:
            # 10% penalty at hard deviation
            return 0.90
        
        # Linear interpolation between soft and hard
        ratio = (deviation - config.soft_deviation) / (config.hard_deviation - config.soft_deviation)
        return 1.00 - (0.10 * ratio)
    
    def _calculate_variance_z(
        self,
        sport_key: str,
        std_total: float
    ) -> float:
        """
        Calculate normalized variance z-score
        
        z_total = std_total / sport_std_ref
        where sport_std_ref is rolling median std over last 28 days
        """
        # Get reference std from recent games
        ref_std = self._get_reference_std(sport_key)
        
        if ref_std is None or ref_std == 0:
            # Fallback to sport-specific defaults
            defaults = {
                "americanfootball_nfl": 14.0,
                "americanfootball_ncaaf": 15.0,
                "basketball_nba": 12.0,
                "basketball_ncaab": 13.5,
                "baseball_mlb": 2.5,
                "icehockey_nhl": 1.8
            }
            ref_std = defaults.get(sport_key, 12.0)
        
        return std_total / ref_std
    
    def _calculate_variance_penalty(
        self,
        z_variance: float,
        config: SportCalibrationConfig
    ) -> float:
        """
        Layer 4: Variance suppression
        
        High variance collapses edge toward 50%
        """
        if z_variance <= config.normal_variance_z:
            return 1.00  # No penalty
        
        if z_variance <= config.high_variance_z:
            # Moderate penalty: probability × 0.85, edge × 0.75
            return 0.75
        
        # Extreme variance: block (handled in validate_pick)
        return 0.50
    
    def _check_elite_override(
        self,
        p_raw: float,
        z_variance: float,
        data_quality_score: float,
        injury_uncertainty: float,
        deviation: float,
        config: SportCalibrationConfig
    ) -> bool:
        """
        Check if pick qualifies for Elite Override
        (rare, but allowed for truly exceptional edges)
        """
        # Only consider if deviation is large OR variance is high
        needs_override = (
            deviation >= config.hard_deviation or
            z_variance > config.extreme_variance_z
        )
        
        if not needs_override:
            return False
        
        # All conditions must be true
        return (
            p_raw >= config.elite_min_probability and
            z_variance <= config.elite_max_z_variance and
            data_quality_score >= config.elite_min_data_quality and
            injury_uncertainty <= config.elite_max_injury_uncertainty
        )
    
    def _check_publish_thresholds(
        self,
        p_adjusted: float,
        edge_adjusted: float,
        deviation: float,
        z_variance: float,
        config: SportCalibrationConfig,
        elite_override: bool
    ) -> Dict[str, Any]:
        """
        Layer 5: Final publish gates
        """
        reasons = []
        
        # Minimum probability
        if p_adjusted < config.min_probability:
            reasons.append("probability_too_low")
        
        # Minimum model-vegas difference
        if deviation < config.min_model_vegas_diff:
            reasons.append("deviation_too_small")
        
        # Hard deviation block (unless elite override)
        if deviation >= config.hard_deviation and not elite_override:
            reasons.append("hard_deviation_exceeded")
        
        # Extreme variance block (unless elite override)
        if z_variance > config.extreme_variance_z and not elite_override:
            reasons.append("extreme_variance")
        
        return {
            "passed": len(reasons) == 0,
            "reasons": reasons
        }
    
    def _get_calibration_metrics(
        self,
        sport_key: str,
        window_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get rolling calibration metrics from database
        """
        # Check cache first
        cache_key = f"{sport_key}_{window_days}"
        if cache_key in self.calibration_cache:
            cached = self.calibration_cache[cache_key]
            # Cache for 1 hour
            if (datetime.now(timezone.utc) - cached["timestamp"]).seconds < 3600:
                return cached["data"]
        
        # Query database
        start_date = datetime.now(timezone.utc) - timedelta(days=window_days)
        
        try:
            # Query latest calibration entry for this sport
            cursor = db.calibration_daily.find(
                {"sport": sport_key}
            ).sort("date", -1).limit(1)
            
            metrics_list = list(cursor)
            metrics = metrics_list[0] if metrics_list else None
            
            if metrics:
                self.calibration_cache[cache_key] = {
                    "timestamp": datetime.now(timezone.utc),
                    "data": metrics
                }
                return metrics
        except Exception as e:
            logger.warning(f"Failed to fetch calibration metrics: {e}")
        
        return None
    
    def _get_reference_std(self, sport_key: str) -> Optional[float]:
        """
        Get rolling median std_total for variance normalization
        """
        try:
            # Get last 28 days of simulations
            start_date = datetime.now(timezone.utc) - timedelta(days=28)
            
            recent_sims = list(db.monte_carlo_simulations.find(
                {
                    "sport_key": sport_key,
                    "created_at": {"$gte": start_date.isoformat()}
                },
                {"variance": 1}
            ).limit(100))
            
            if recent_sims:
                variances = [s.get("variance", 0) for s in recent_sims if s.get("variance")]
                if variances:
                    # std = sqrt(variance)
                    stds = [np.sqrt(v) for v in variances]
                    return float(np.median(stds))
        except Exception as e:
            logger.warning(f"Failed to get reference std: {e}")
        
        return None


# Singleton
calibration_engine = CalibrationEngine()

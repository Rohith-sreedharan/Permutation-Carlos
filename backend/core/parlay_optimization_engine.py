"""
Parlay Generation Engine — Portfolio Optimization with Fallback

CRITICAL CHANGE:
- Old: "Find N legs where each passes strict gates" (blocks everything)
- New: "Select N legs that maximize portfolio score under risk constraints" (always produces)

This engine NEVER returns "nothing" unless slate is literally empty.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import logging

from core.truth_mode_parlay import (
    TruthMode, RiskProfile, MarketType, PropRiskBand,
    ParlayWeight, PropIntegrityCheck, ParlayLegCandidate,
    RiskProfileConstraints, MIN_PARLAY_WEIGHT,
    calculate_parlay_weight, validate_prop_integrity
)

logger = logging.getLogger(__name__)


@dataclass
class ParlayGenerationResult:
    """Result of parlay generation attempt"""
    success: bool
    parlay_id: Optional[str]
    mode: TruthMode
    risk_profile_requested: RiskProfile
    risk_profile_used: RiskProfile
    leg_count_requested: int
    leg_count_used: int
    legs: List[Dict[str, Any]]  # Keep as Dict for flexibility
    portfolio_score: float
    expected_hit_rate: float
    expected_value_proxy: float
    fallback_steps_taken: List[str]
    fail_reason: Optional[str]
    generation_timestamp: str


@dataclass
class ParlayGenerationAudit:
    """Audit trail for generation attempts (for valuation-grade tracking)"""
    attempt_id: str
    mode: str
    risk_profile_requested: str
    risk_profile_used: str
    leg_count_requested: int
    leg_count_used: int
    candidates_total: int
    candidates_pick: int
    candidates_lean: int
    constraints_applied: Dict[str, Any]
    fallback_steps_taken: List[str]
    result_status: str  # SUCCESS/FAIL
    fail_reason_codes: List[str]
    timestamp: str


class ParlayOptimizationEngine:
    """
    Portfolio optimization engine for parlay generation
    
    NEVER blocks due to volatility/instability — uses penalties instead.
    Always attempts fallback ladder before returning failure.
    """
    
    def __init__(self, db=None):
        self.db = db
    
    def generate_parlay(
        self,
        candidates: List[Dict[str, Any]],
        mode: TruthMode = TruthMode.PARLAY,
        risk_profile: RiskProfile = RiskProfile.BALANCED,
        leg_count: int = 4,
        include_higher_risk_legs: bool = False,
        include_props: bool = True,
        include_game_lines: bool = True,
        dfs_mode: bool = False,
        allow_same_game: bool = False,
        allow_cross_sport: bool = True
    ) -> ParlayGenerationResult:
        """
        Generate optimized parlay with fallback ladder
        
        Args:
            candidates: List of simulation/prediction data
            mode: STRICT (PICK only) or PARLAY (PICK+LEAN with penalties)
            risk_profile: HIGH_CONFIDENCE / BALANCED / HIGH_VOLATILITY
            leg_count: Desired number of legs (3-8)
            include_higher_risk_legs: Allow LEAN state (overrides profile default)
            include_props: Include player props
            include_game_lines: Include spreads/totals/ML
            dfs_mode: DFS-specific constraints
            allow_same_game: Allow multiple legs from same game
            allow_cross_sport: Allow legs from different sports
        
        Returns:
            ParlayGenerationResult with legs or fallback path
        """
        attempt_id = f"parlay_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        fallback_steps = []
        
        logger.info(
            f"🎯 Parlay Generation: mode={mode.value}, profile={risk_profile.value}, "
            f"legs={leg_count}, candidates={len(candidates)}"
        )
        
        # Step 1: Build candidate pool with eligibility
        eligible_candidates = self._build_candidate_pool(
            candidates=candidates,
            mode=mode,
            include_props=include_props,
            include_game_lines=include_game_lines,
            dfs_mode=dfs_mode
        )
        
        if not eligible_candidates:
            logger.warning("🚫 No eligible candidates after DI+MV filtering")
            return self._fail_result(
                mode=mode,
                risk_profile_requested=risk_profile,
                leg_count_requested=leg_count,
                fail_reason="NO_ELIGIBLE_CANDIDATES_DI_MV_FAILED",
                fallback_steps=fallback_steps
            )
        
        # Step 2: Compute parlay weights for all candidates
        weighted_candidates = self._compute_weights(eligible_candidates, mode)
        
        # Step 3: Try generation with fallback ladder
        result = self._try_with_fallback_ladder(
            candidates=weighted_candidates,
            mode=mode,
            risk_profile_requested=risk_profile,
            leg_count_requested=leg_count,
            include_higher_risk_legs=include_higher_risk_legs,
            allow_same_game=allow_same_game,
            allow_cross_sport=allow_cross_sport,
            fallback_steps=fallback_steps
        )
        
        # Step 4: Log audit trail
        self._log_generation_audit(
            attempt_id=attempt_id,
            mode=mode,
            risk_profile_requested=risk_profile,
            risk_profile_used=result.risk_profile_used if result.success else risk_profile,
            leg_count_requested=leg_count,
            leg_count_used=result.leg_count_used if result.success else 0,
            candidates_total=len(candidates),
            candidates_pick=sum(1 for c in eligible_candidates if c.get('strict_state') == 'PICK'),
            candidates_lean=sum(1 for c in eligible_candidates if c.get('strict_state') == 'LEAN'),
            constraints_applied=RiskProfileConstraints.get_constraints(risk_profile),
            fallback_steps=fallback_steps,
            result_status='SUCCESS' if result.success else 'FAIL',
            fail_reason_codes=[result.fail_reason] if result.fail_reason else []
        )
        
        return result
    
    def _build_candidate_pool(
        self,
        candidates: List[Dict[str, Any]],
        mode: TruthMode,
        include_props: bool,
        include_game_lines: bool,
        dfs_mode: bool
    ) -> List[Dict[str, Any]]:
        """
        Build eligible candidate pool with DI+MV+Prop Integrity filtering
        
        🚨 FIX #4: Uses PARLAY_POOL thresholds, NOT single-pick thresholds
        
        STRICT MODE: Only PICK state
        PARLAY MODE: PICK + LEAN that pass PARLAY_POOL thresholds
        """
        from core.parlay_eligibility import check_parlay_pool_eligibility
        
        eligible = []
        
        for candidate in candidates:
            # Must have required fields
            if not self._has_required_fields(candidate):
                continue
            
            # Data Integrity + Model Validity (ALWAYS REQUIRED)
            if not self._passes_di_mv(candidate):
                continue
            
            # Strict state filtering
            strict_state = candidate.get('strict_state', 'NO_PLAY')
            
            if mode == TruthMode.STRICT:
                # STRICT: Only PICK state, must be parlay-eligible
                if strict_state != 'PICK':
                    continue
                if not candidate.get('can_parlay', False):
                    continue
            
            elif mode == TruthMode.PARLAY:
                # PARLAY MODE: Check with PARLAY_POOL thresholds (NOT single-pick)
                if strict_state == 'NO_PLAY':
                    continue
                
                # 🚨 NEW: Use PARLAY_POOL eligibility check (53%/1.5/50)
                probability = candidate.get('probability', 0) or candidate.get('win_probability', 0) or 0
                edge = candidate.get('edge', 0) or candidate.get('edge_points', 0) or 0
                confidence = candidate.get('confidence', 0) or candidate.get('confidence_score', 0) or 0
                variance_z = candidate.get('variance_z', 0) or 0
                
                parlay_check = check_parlay_pool_eligibility(
                    probability=probability,
                    edge=edge,
                    confidence=int(confidence),
                    variance_z=variance_z
                )
                
                if not parlay_check.is_eligible:
                    logger.debug(
                        f"❌ Candidate rejected by PARLAY_POOL thresholds: "
                        f"{parlay_check.failed_checks}"
                    )
                    continue
            
            # Market type filtering
            market_type = candidate.get('market_type', 'GAME_TOTAL')
            
            if market_type == 'PLAYER_PROP':
                if not include_props:
                    continue
                # Props must pass Prop Integrity Gate
                if not self._passes_prop_integrity(candidate):
                    continue
            else:
                if not include_game_lines:
                    continue
            
            # DFS mode: props only by default
            if dfs_mode and market_type != 'PLAYER_PROP':
                continue
            
            eligible.append(candidate)
        
        logger.info(f"✅ Eligible candidates: {len(eligible)} from {len(candidates)} total (using PARLAY_POOL thresholds)")
        return eligible
    
    def _compute_weights(
        self,
        candidates: List[Dict[str, Any]],
        mode: TruthMode
    ) -> List[Dict[str, Any]]:
        """Compute parlay weight for each candidate"""
        weighted = []
        
        for candidate in candidates:
            weight_result = calculate_parlay_weight(candidate, mode=mode)
            
            candidate['parlay_weight'] = weight_result.final_weight
            candidate['parlay_reason_codes'] = weight_result.reason_codes
            candidate['parlay_eligible'] = weight_result.final_weight >= MIN_PARLAY_WEIGHT
            
            weighted.append(candidate)
        
        return weighted
    
    def _try_with_fallback_ladder(
        self,
        candidates: List[Dict[str, Any]],
        mode: TruthMode,
        risk_profile_requested: RiskProfile,
        leg_count_requested: int,
        include_higher_risk_legs: bool,
        allow_same_game: bool,
        allow_cross_sport: bool,
        fallback_steps: List[str]
    ) -> ParlayGenerationResult:
        """
        Fallback ladder: NEVER return nothing unless slate is empty
        
        Fallback sequence:
        1. Try requested profile + leg count
        2. Try BALANCED (if was HIGH_CONFIDENCE)
        3. Try BALANCED with include_higher_risk_legs=ON
        4. Try HIGH_VOLATILITY
        5. Reduce leg_count by 1 (down to 3 minimum)
        6. Return best available with explicit warning
        """
        # Step 1: Try requested configuration
        result = self._select_legs(
            candidates=candidates,
            mode=mode,
            risk_profile=risk_profile_requested,
            leg_count=leg_count_requested,
            include_higher_risk_legs=include_higher_risk_legs,
            allow_same_game=allow_same_game,
            allow_cross_sport=allow_cross_sport
        )
        
        if result.success:
            return result
        
        # Step 2: Fallback to BALANCED if was HIGH_CONFIDENCE
        if risk_profile_requested == RiskProfile.HIGH_CONFIDENCE:
            fallback_steps.append('FALLBACK_TO_BALANCED')
            logger.info("⚠️ Fallback: HIGH_CONFIDENCE → BALANCED")
            
            result = self._select_legs(
                candidates=candidates,
                mode=mode,
                risk_profile=RiskProfile.BALANCED,
                leg_count=leg_count_requested,
                include_higher_risk_legs=False,
                allow_same_game=allow_same_game,
                allow_cross_sport=allow_cross_sport
            )
            
            if result.success:
                result.fallback_steps_taken = fallback_steps
                return result
        
        # Step 3: Try BALANCED with higher risk legs enabled
        if not include_higher_risk_legs:
            fallback_steps.append('ENABLE_HIGHER_RISK_LEGS')
            logger.info("⚠️ Fallback: Enable higher risk legs")
            
            result = self._select_legs(
                candidates=candidates,
                mode=mode,
                risk_profile=RiskProfile.BALANCED,
                leg_count=leg_count_requested,
                include_higher_risk_legs=True,
                allow_same_game=allow_same_game,
                allow_cross_sport=allow_cross_sport
            )
            
            if result.success:
                result.fallback_steps_taken = fallback_steps
                return result
        
        # Step 4: Try HIGH_VOLATILITY
        if risk_profile_requested != RiskProfile.HIGH_VOLATILITY:
            fallback_steps.append('FALLBACK_TO_HIGH_VOL')
            logger.info("⚠️ Fallback: → HIGH_VOLATILITY")
            
            result = self._select_legs(
                candidates=candidates,
                mode=mode,
                risk_profile=RiskProfile.HIGH_VOLATILITY,
                leg_count=leg_count_requested,
                include_higher_risk_legs=True,
                allow_same_game=allow_same_game,
                allow_cross_sport=allow_cross_sport
            )
            
            if result.success:
                result.fallback_steps_taken = fallback_steps
                return result
        
        # Step 5: Reduce leg count (down to 3 minimum)
        current_leg_count = leg_count_requested
        while current_leg_count > 3:
            current_leg_count -= 1
            fallback_steps.append(f'REDUCE_LEG_COUNT_TO_{current_leg_count}')
            logger.info(f"⚠️ Fallback: Reduce leg count to {current_leg_count}")
            
            result = self._select_legs(
                candidates=candidates,
                mode=mode,
                risk_profile=RiskProfile.HIGH_VOLATILITY,
                leg_count=current_leg_count,
                include_higher_risk_legs=True,
                allow_same_game=allow_same_game,
                allow_cross_sport=allow_cross_sport
            )
            
            if result.success:
                result.fallback_steps_taken = fallback_steps
                return result
        
        # Step 6: Complete failure (rare — indicates feed issue)
        logger.error("🚫 Complete fallback failure — no parlay possible")
        return self._fail_result(
            mode=mode,
            risk_profile_requested=risk_profile_requested,
            leg_count_requested=leg_count_requested,
            fail_reason="FALLBACK_EXHAUSTED_NO_VALID_LEGS",
            fallback_steps=fallback_steps
        )
    
    def _select_legs(
        self,
        candidates: List[Dict[str, Any]],
        mode: TruthMode,
        risk_profile: RiskProfile,
        leg_count: int,
        include_higher_risk_legs: bool,
        allow_same_game: bool,
        allow_cross_sport: bool
    ) -> ParlayGenerationResult:
        """
        Select top N legs based on risk profile constraints
        
        Algorithm:
        1. Filter by profile constraints (min win_prob, max high-vol, etc.)
        2. Sort by parlay_weight descending
        3. Select top N with diversification rules
        """
        constraints = RiskProfileConstraints.get_constraints(risk_profile)
        
        # Override allow_lean if user requested higher risk
        if include_higher_risk_legs:
            constraints['allow_lean'] = True
        
        # Filter by constraints
        filtered = self._apply_constraints(candidates, constraints)
        
        if len(filtered) < leg_count:
            return self._fail_result(
                mode=mode,
                risk_profile_requested=risk_profile,
                leg_count_requested=leg_count,
                fail_reason=f"INSUFFICIENT_LEGS_AFTER_CONSTRAINTS_{len(filtered)}_OF_{leg_count}",
                fallback_steps=[]
            )
        
        # Sort by parlay_weight descending
        sorted_candidates = sorted(filtered, key=lambda x: x.get('parlay_weight', 0), reverse=True)
        
        # Select top N with diversification
        selected = self._diversify_selection(
            candidates=sorted_candidates,
            leg_count=leg_count,
            allow_same_game=allow_same_game,
            allow_cross_sport=allow_cross_sport
        )
        
        if len(selected) < leg_count:
            return self._fail_result(
                mode=mode,
                risk_profile_requested=risk_profile,
                leg_count_requested=leg_count,
                fail_reason=f"INSUFFICIENT_LEGS_AFTER_DIVERSIFICATION_{len(selected)}_OF_{leg_count}",
                fallback_steps=[]
            )
        
        # Calculate portfolio metrics
        portfolio_score = sum(leg.get('parlay_weight', 0) for leg in selected)
        expected_hit_rate = self._calculate_expected_hit_rate(selected)
        expected_value_proxy = self._calculate_expected_value(selected)
        
        parlay_id = f"parlay_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
        
        return ParlayGenerationResult(
            success=True,
            parlay_id=parlay_id,
            mode=mode,
            risk_profile_requested=risk_profile,
            risk_profile_used=risk_profile,
            leg_count_requested=leg_count,
            leg_count_used=len(selected),
            legs=selected,
            portfolio_score=portfolio_score,
            expected_hit_rate=expected_hit_rate,
            expected_value_proxy=expected_value_proxy,
            fallback_steps_taken=[],
            fail_reason=None,
            generation_timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _apply_constraints(
        self,
        candidates: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply risk profile constraints to filter candidates"""
        filtered = []
        high_vol_count = 0
        unstable_count = 0
        prop_count = 0
        
        for candidate in candidates:
            # Check if parlay eligible
            if not candidate.get('parlay_eligible', False):
                continue
            
            # Min win probability
            if candidate.get('win_probability', 0) < constraints.get('min_win_prob', 0.5):
                continue
            
            # Min parlay weight
            if candidate.get('parlay_weight', 0) < constraints.get('min_parlay_weight', 0.5):
                continue
            
            # Check LEAN allowance
            if candidate.get('strict_state') == 'LEAN' and not constraints.get('allow_lean', False):
                continue
            
            # Track high-vol and unstable legs
            volatility_band = candidate.get('volatility_band', 'MED').upper()
            is_high_vol = volatility_band == 'HIGH'
            is_unstable = not candidate.get('distribution_stable', True)
            is_prop = candidate.get('market_type') == 'PLAYER_PROP'
            
            # Check constraints
            if is_high_vol and high_vol_count >= constraints.get('max_high_vol_legs', 0):
                continue
            if is_unstable and unstable_count >= constraints.get('max_unstable_legs', 0):
                continue
            if is_prop and prop_count >= constraints.get('max_prop_legs', 99):
                continue
            
            filtered.append(candidate)
            
            if is_high_vol:
                high_vol_count += 1
            if is_unstable:
                unstable_count += 1
            if is_prop:
                prop_count += 1
        
        return filtered
    
    def _diversify_selection(
        self,
        candidates: List[Dict[str, Any]],
        leg_count: int,
        allow_same_game: bool,
        allow_cross_sport: bool
    ) -> List[Dict[str, Any]]:
        """Select legs with diversification rules"""
        selected = []
        seen_events = set()
        seen_sports = set()
        
        for candidate in candidates:
            if len(selected) >= leg_count:
                break
            
            event_id = candidate.get('event_id')
            sport_key = candidate.get('sport_key', 'unknown')
            
            # Check same-game rule
            if not allow_same_game and event_id in seen_events:
                continue
            
            # Check cross-sport rule
            if not allow_cross_sport and seen_sports and sport_key not in seen_sports:
                continue
            
            selected.append(candidate)
            seen_events.add(event_id)
            seen_sports.add(sport_key)
        
        return selected
    
    def _calculate_expected_hit_rate(self, legs: List[Dict[str, Any]]) -> float:
        """Estimate parlay hit rate (independent assumption)"""
        product = 1.0
        for leg in legs:
            win_prob = leg.get('win_probability', 0.5)
            product *= win_prob
        return product
    
    def _calculate_expected_value(self, legs: List[Dict[str, Any]]) -> float:
        """Estimate EV proxy"""
        # Simplified: average edge * hit rate
        avg_edge = sum(leg.get('edge_points', 0) for leg in legs) / len(legs) if legs else 0
        hit_rate = self._calculate_expected_hit_rate(legs)
        return avg_edge * hit_rate
    
    def _has_required_fields(self, candidate: Dict[str, Any]) -> bool:
        """Check if candidate has required fields"""
        required = ['event_id', 'strict_state', 'win_probability']
        return all(field in candidate for field in required)
    
    def _passes_di_mv(self, candidate: Dict[str, Any]) -> bool:
        """Check Data Integrity + Model Validity (always required)"""
        # Placeholder — integrate with actual DI/MV validation
        di_pass = candidate.get('data_integrity_pass', True)
        mv_pass = candidate.get('model_validity_pass', True)
        return di_pass and mv_pass
    
    def _passes_prop_integrity(self, candidate: Dict[str, Any]) -> bool:
        """Check Prop Integrity Gate"""
        if candidate.get('market_type') != 'PLAYER_PROP':
            return True
        
        prop_check = validate_prop_integrity(candidate)
        candidate['prop_integrity'] = prop_check
        
        # Block if critical failures
        if not prop_check.player_status_pass:
            return False
        if prop_check.prop_risk_band == PropRiskBand.HIGH:
            return False
        
        return True
    
    def _fail_result(
        self,
        mode: TruthMode,
        risk_profile_requested: RiskProfile,
        leg_count_requested: int,
        fail_reason: str,
        fallback_steps: List[str]
    ) -> ParlayGenerationResult:
        """Create failure result"""
        return ParlayGenerationResult(
            success=False,
            parlay_id=None,
            mode=mode,
            risk_profile_requested=risk_profile_requested,
            risk_profile_used=risk_profile_requested,
            leg_count_requested=leg_count_requested,
            leg_count_used=0,
            legs=[],
            portfolio_score=0.0,
            expected_hit_rate=0.0,
            expected_value_proxy=0.0,
            fallback_steps_taken=fallback_steps,
            fail_reason=fail_reason,
            generation_timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    def _log_generation_audit(self, **kwargs):
        """Log generation audit for valuation tracking"""
        audit = ParlayGenerationAudit(**kwargs)
        
        if self.db:
            try:
                self.db['parlay_generation_audit'].insert_one(audit.__dict__)
            except Exception as e:
                logger.error(f"Failed to log parlay audit: {e}")
        
        logger.info(f"📊 Parlay Audit: {audit.result_status} | {audit.leg_count_used} legs | "
                   f"{len(audit.fallback_steps_taken)} fallbacks")

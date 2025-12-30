"""
Market State Registry Service
SINGLE SOURCE OF TRUTH for all market states

🚨 CRITICAL RULES:
1. This registry is the ONLY place market states should be written/read
2. All downstream features MUST use this service
3. States are immutable per evaluation cycle
4. No feature may infer state independently
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
import uuid
from pymongo.database import Database

from db.schemas.market_state_registry import (
    MarketStateRegistry,
    MarketState,
    MarketType,
    VolatilityFlag,
    ReasonCode,
    VisibilityFlags,
    ParlayEligibilityResult,
    PARLAY_THRESHOLDS,
    SINGLE_PICK_THRESHOLDS,
    MARKET_STATE_COLLECTION
)


class MarketStateRegistryService:
    """
    Central service for managing market states
    
    ALL downstream features must use this service:
    - Telegram posting
    - Parlay builder
    - War Room
    - Daily picks
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.collection = db[MARKET_STATE_COLLECTION]
    
    # ========================================================================
    # STATE REGISTRATION (WRITE)
    # ========================================================================
    
    async def register_market_state(
        self,
        game_id: str,
        sport: str,
        market_type: MarketType,
        state: MarketState,
        reason_codes: List[ReasonCode],
        probability: Optional[float] = None,
        edge_points: Optional[float] = None,
        confidence_score: Optional[int] = None,
        risk_score: Optional[float] = None,
        volatility_flag: VolatilityFlag = VolatilityFlag.MODERATE,
        selection: Optional[str] = None,
        line_value: Optional[float] = None,
        evaluation_cycle_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> MarketStateRegistry:
        """
        Register or update a market state
        
        This is the ONLY way to set market states.
        States are versioned and immutable per evaluation cycle.
        """
        # Compute state hash
        state_hash = MarketStateRegistry.compute_state_hash(
            game_id=game_id,
            market_type=market_type.value,
            state=state.value,
            probability=probability,
            edge_points=edge_points,
            confidence_score=confidence_score
        )
        
        # Create registry entry
        registry = MarketStateRegistry(
            registry_id=f"msr_{uuid.uuid4().hex[:12]}",
            game_id=game_id,
            sport=sport,
            market_type=market_type,
            state=state,
            reason_codes=reason_codes,
            probability=probability,
            edge_points=edge_points,
            confidence_score=confidence_score,
            risk_score=risk_score,
            volatility_flag=volatility_flag,
            selection=selection,
            line_value=line_value,
            state_version_hash=state_hash,
            evaluation_cycle_id=evaluation_cycle_id or f"cycle_{uuid.uuid4().hex[:8]}",
            updated_at=datetime.now(timezone.utc),
            expires_at=expires_at
        )
        
        # Compute visibility flags
        registry.visibility_flags = registry.compute_visibility_flags()
        
        # Upsert (replace existing for same game/market)
        self.collection.update_one(
            {
                "game_id": game_id,
                "market_type": market_type.value
            },
            {"$set": registry.model_dump()},
            upsert=True
        )
        
        return registry
    
    # ========================================================================
    # STATE QUERIES (READ)
    # ========================================================================
    
    async def get_market_state(
        self,
        game_id: str,
        market_type: MarketType
    ) -> Optional[MarketStateRegistry]:
        """
        Get current state for a specific market
        
        🚨 This is the ONLY way to check market state
        """
        doc = self.collection.find_one({
            "game_id": game_id,
            "market_type": market_type.value
        })
        
        if not doc:
            return None
        
        return self._doc_to_registry(doc)
    
    async def get_game_states(
        self,
        game_id: str
    ) -> List[MarketStateRegistry]:
        """Get all market states for a game"""
        cursor = self.collection.find({"game_id": game_id})
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    async def get_states_by_state(
        self,
        state: MarketState,
        sport: Optional[str] = None,
        limit: int = 100
    ) -> List[MarketStateRegistry]:
        """Get all markets in a specific state"""
        query: Dict[str, Any] = {"state": state.value}
        
        if sport:
            query["sport"] = sport
        
        cursor = self.collection.find(query).limit(limit)
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    # ========================================================================
    # FEATURE-SPECIFIC QUERIES (INTERNAL)
    # ========================================================================
    
    async def _get_telegram_eligible_internal(
        self,
        sport: Optional[str] = None
    ) -> List[MarketStateRegistry]:
        """
        Internal: Get markets eligible for Telegram posting
        
        Requirements: EDGE state + strict thresholds
        """
        query: Dict[str, Any] = {
            "visibility_flags.telegram_allowed": True,
            "state": MarketState.EDGE.value
        }
        
        if sport:
            query["sport"] = sport
        
        cursor = self.collection.find(query)
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    async def _get_parlay_eligible_internal(
        self,
        sport: Optional[str] = None,
        exclude_game_ids: Optional[List[str]] = None
    ) -> List[MarketStateRegistry]:
        """
        Internal: Get markets eligible for parlay inclusion
        
        Requirements: EDGE or LEAN + looser thresholds
        🚨 These thresholds are DIFFERENT from Telegram thresholds
        """
        query: Dict[str, Any] = {
            "visibility_flags.parlay_allowed": True,
            "state": {"$in": [MarketState.EDGE.value, MarketState.LEAN.value]}
        }
        
        if sport:
            query["sport"] = sport
        
        if exclude_game_ids:
            query["game_id"] = {"$nin": exclude_game_ids}
        
        cursor = self.collection.find(query)
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    async def _get_war_room_visible_internal(
        self,
        sport: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> List[MarketStateRegistry]:
        """
        Internal: Get markets visible in War Room
        
        Requirements: EDGE or LEAN (NOT NO_PLAY)
        🚨 War Room must NEVER depend on Telegram posting
        """
        query: Dict[str, Any] = {
            "visibility_flags.war_room_visible": True,
            "state": {"$in": [MarketState.EDGE.value, MarketState.LEAN.value]}
        }
        
        if sport:
            query["sport"] = sport
        
        # Filter by date if provided (games for that day)
        if date:
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            query["expires_at"] = {
                "$gte": start_of_day,
                "$lt": end_of_day
            }
        
        cursor = self.collection.find(query).sort("updated_at", -1)
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    async def get_daily_picks(
        self,
        sport: Optional[str] = None,
        limit: int = 3
    ) -> List[MarketStateRegistry]:
        """
        Get markets eligible for daily picks
        
        Requirements: Same as Telegram (EDGE + strict thresholds)
        """
        query: Dict[str, Any] = {
            "visibility_flags.daily_pick_allowed": True,
            "state": MarketState.EDGE.value
        }
        
        if sport:
            query["sport"] = sport
        
        # Sort by confidence descending
        cursor = self.collection.find(query).sort(
            "confidence_score", -1
        ).limit(limit)
        
        return [self._doc_to_registry(doc) for doc in cursor]
    
    # ========================================================================
    # PARLAY ELIGIBILITY CHECK (INTERNAL)
    # ========================================================================
    
    async def _check_parlay_eligibility_by_games(
        self,
        game_ids: List[str],
        requested_legs: int = 3
    ) -> ParlayEligibilityResult:
        """
        Internal: Check if a parlay can be built from given games
        
        🚨 PARLAY FAILURE IS NOT AN ERROR - it returns a structured response
        """
        passed_legs = []
        failed_legs = []
        reason_codes = []
        
        for game_id in game_ids:
            states = await self.get_game_states(game_id)
            
            # Find best eligible market for this game
            eligible_market = None
            for state in states:
                if self._is_parlay_eligible(state):
                    if not eligible_market or (state.confidence_score or 0) > (eligible_market.confidence_score or 0):
                        eligible_market = state
            
            if eligible_market:
                passed_legs.append({
                    "game_id": game_id,
                    "market_type": eligible_market.market_type.value,
                    "selection": eligible_market.selection,
                    "confidence": eligible_market.confidence_score
                })
            else:
                failed_legs.append(game_id)
                # Determine why it failed
                if states:
                    for state in states:
                        if state.state == MarketState.NO_PLAY:
                            reason_codes.append(f"{game_id}: NO_PLAY state")
                        elif (state.probability or 0) < PARLAY_THRESHOLDS.probability_min:
                            reason_codes.append(f"{game_id}: probability below {PARLAY_THRESHOLDS.probability_min}")
                        elif (state.edge_points or 0) < PARLAY_THRESHOLDS.edge_min:
                            reason_codes.append(f"{game_id}: edge below {PARLAY_THRESHOLDS.edge_min}")
                        elif (state.confidence_score or 0) < PARLAY_THRESHOLDS.confidence_min:
                            reason_codes.append(f"{game_id}: confidence below {PARLAY_THRESHOLDS.confidence_min}")
                else:
                    reason_codes.append(f"{game_id}: no market state registered")
        
        # Determine result state
        if len(passed_legs) >= requested_legs:
            return ParlayEligibilityResult(
                is_eligible=True,
                state="ELIGIBLE",
                passed_checks=[f"{len(passed_legs)} legs passed"],
                failed_checks=[],
                reason_codes=[],
                passed_legs=len(passed_legs),
                failed_legs=len(failed_legs),
                best_single_pick=None
            )
        elif len(passed_legs) > 0:
            # Some legs passed but not enough
            return ParlayEligibilityResult(
                is_eligible=False,
                state="INSUFFICIENT_LEGS",
                passed_checks=[f"{len(passed_legs)} legs passed"],
                failed_checks=[f"Need {requested_legs}, only have {len(passed_legs)}"],
                reason_codes=reason_codes,
                passed_legs=len(passed_legs),
                failed_legs=len(failed_legs),
                next_refresh_eta=datetime.now(timezone.utc) + timedelta(minutes=15),
                best_single_pick=None
            )
        else:
            # No legs passed
            return ParlayEligibilityResult(
                is_eligible=False,
                state="PARLAY_BLOCKED",
                passed_checks=[],
                failed_checks=["No eligible legs found"],
                reason_codes=reason_codes,
                passed_legs=0,
                failed_legs=len(failed_legs),
                next_refresh_eta=datetime.now(timezone.utc) + timedelta(minutes=15),
                best_single_pick=None
            )
    
    def _is_parlay_eligible(self, state: MarketStateRegistry) -> bool:
        """Check if a market state is parlay-eligible"""
        if state.state == MarketState.NO_PLAY:
            return False
        
        if state.state not in [MarketState.EDGE, MarketState.LEAN]:
            return False
        
        if (state.probability or 0) < PARLAY_THRESHOLDS.probability_min:
            return False
        
        if (state.edge_points or 0) < PARLAY_THRESHOLDS.edge_min:
            return False
        
        if (state.confidence_score or 0) < PARLAY_THRESHOLDS.confidence_min:
            return False
        
        if (state.risk_score or 0) > PARLAY_THRESHOLDS.risk_score_max:
            return False
        
        return True
    
    # ========================================================================
    # BULK OPERATIONS
    # ========================================================================
    
    async def register_simulation_results(
        self,
        simulation_results: List[Dict[str, Any]],
        evaluation_cycle_id: str
    ) -> Dict[str, int]:
        """
        Register multiple market states from simulation results
        
        This should be called after each simulation cycle.
        """
        stats = {"registered": 0, "edge": 0, "lean": 0, "no_play": 0}
        
        for result in simulation_results:
            # Determine state from simulation output
            state, reasons = self._determine_state_from_simulation(result)
            
            # Register state
            await self.register_market_state(
                game_id=result["game_id"],
                sport=result["sport"],
                market_type=MarketType(result.get("market_type", "SPREAD")),
                state=state,
                reason_codes=reasons,
                probability=result.get("win_prob"),
                edge_points=result.get("edge"),
                confidence_score=result.get("confidence"),
                risk_score=result.get("risk_score"),
                volatility_flag=self._get_volatility_flag(result),
                selection=result.get("selection"),
                line_value=result.get("line_value"),
                evaluation_cycle_id=evaluation_cycle_id,
                expires_at=result.get("game_commence_time")
            )
            
            stats["registered"] += 1
            stats[state.value.lower()] += 1
        
        return stats
    
    def _determine_state_from_simulation(
        self,
        result: Dict[str, Any]
    ) -> Tuple[MarketState, List[ReasonCode]]:
        """
        Determine market state from simulation result
        
        Applies the explicit threshold rules
        """
        reasons = []
        
        probability = result.get("win_prob", 0)
        edge = result.get("edge", 0)
        confidence = result.get("confidence", 0)
        risk_score = result.get("risk_score", 0)
        
        # Check for NO_PLAY conditions first
        if result.get("data_incomplete"):
            return MarketState.NO_PLAY, [ReasonCode.DATA_INCOMPLETE]
        
        if result.get("game_started"):
            return MarketState.NO_PLAY, [ReasonCode.GAME_STARTED]
        
        if result.get("market_suspended"):
            return MarketState.NO_PLAY, [ReasonCode.MARKET_SUSPENDED]
        
        if result.get("convergence_failed"):
            return MarketState.NO_PLAY, [ReasonCode.SIM_CONVERGENCE_FAILED]
        
        # Check EDGE thresholds (strict)
        if (
            probability >= SINGLE_PICK_THRESHOLDS.probability_min and
            edge >= SINGLE_PICK_THRESHOLDS.edge_min and
            confidence >= SINGLE_PICK_THRESHOLDS.confidence_min
        ):
            return MarketState.EDGE, [ReasonCode.EDGE_CONFIRMED, ReasonCode.STRONG_MODEL_SIGNAL]
        
        # Check LEAN thresholds (looser)
        if (
            probability >= PARLAY_THRESHOLDS.probability_min and
            edge >= PARLAY_THRESHOLDS.edge_min and
            confidence >= PARLAY_THRESHOLDS.confidence_min
        ):
            # Determine why not EDGE
            if probability < SINGLE_PICK_THRESHOLDS.probability_min:
                reasons.append(ReasonCode.PROBABILITY_BELOW_THRESHOLD)
            if edge < SINGLE_PICK_THRESHOLDS.edge_min:
                reasons.append(ReasonCode.EDGE_BELOW_THRESHOLD)
            if confidence < SINGLE_PICK_THRESHOLDS.confidence_min:
                reasons.append(ReasonCode.CONFIDENCE_BELOW_THRESHOLD)
            if risk_score > PARLAY_THRESHOLDS.risk_score_max:
                reasons.append(ReasonCode.RISK_SCORE_EXCEEDED)
            
            return MarketState.LEAN, reasons or [ReasonCode.PROBABILITY_BELOW_THRESHOLD]
        
        # Default to NO_PLAY
        reasons = []
        if probability < PARLAY_THRESHOLDS.probability_min:
            reasons.append(ReasonCode.PROBABILITY_BELOW_THRESHOLD)
        if edge < PARLAY_THRESHOLDS.edge_min:
            reasons.append(ReasonCode.EDGE_BELOW_THRESHOLD)
        if confidence < PARLAY_THRESHOLDS.confidence_min:
            reasons.append(ReasonCode.CONFIDENCE_BELOW_THRESHOLD)
        
        return MarketState.NO_PLAY, reasons or [ReasonCode.NO_MODEL_SIGNAL]
    
    def _get_volatility_flag(self, result: Dict[str, Any]) -> VolatilityFlag:
        """Determine volatility flag from simulation result"""
        variance = result.get("variance", "medium")
        
        if variance == "low":
            return VolatilityFlag.STABLE
        elif variance == "high":
            return VolatilityFlag.VOLATILE
        else:
            return VolatilityFlag.MODERATE
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    async def cleanup_expired_states(self) -> int:
        """Remove states for games that have started"""
        result = self.collection.delete_many({
            "expires_at": {"$lt": datetime.now(timezone.utc)}
        })
        return result.deleted_count
    
    # ========================================================================
    # API-COMPATIBLE METHODS
    # ========================================================================
    
    async def get_by_game(self, game_id: str) -> List[Dict[str, Any]]:
        """Get all market states for a game (API-friendly response)"""
        states = await self.get_game_states(game_id)
        return [self._registry_to_api_response(s) for s in states]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current registry statistics"""
        total = self.collection.count_documents({})
        edge = self.collection.count_documents({"state": MarketState.EDGE.value})
        lean = self.collection.count_documents({"state": MarketState.LEAN.value})
        no_play = self.collection.count_documents({"state": MarketState.NO_PLAY.value})
        telegram = self.collection.count_documents({"visibility_flags.telegram_allowed": True})
        parlay = self.collection.count_documents({"visibility_flags.parlay_allowed": True})
        war_room = self.collection.count_documents({"visibility_flags.war_room_visible": True})
        
        return {
            "total_markets": total,
            "edge_count": edge,
            "lean_count": lean,
            "no_play_count": no_play,
            "telegram_eligible": telegram,
            "parlay_eligible": parlay,
            "war_room_visible": war_room,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def _registry_to_api_response(self, registry: MarketStateRegistry) -> Dict[str, Any]:
        """Convert registry entry to API-friendly response"""
        return {
            "game_id": registry.game_id,
            "market_type": registry.market_type.value,
            "state": registry.state.value,
            "selection": registry.selection,
            "line_value": registry.line_value,
            "probability": registry.probability,
            "edge_points": registry.edge_points,
            "confidence_score": registry.confidence_score,
            "risk_score": registry.risk_score,
            "visibility_flags": {
                "telegram_allowed": registry.visibility_flags.telegram_allowed,
                "parlay_allowed": registry.visibility_flags.parlay_allowed,
                "war_room_visible": registry.visibility_flags.war_room_visible,
                "daily_pick_allowed": registry.visibility_flags.daily_pick_allowed
            } if registry.visibility_flags else {},
            "created_at": registry.created_at.isoformat() if registry.created_at else None,
            "updated_at": registry.updated_at.isoformat() if registry.updated_at else None
        }
    
    # Override for API route compatibility
    async def get_war_room_visible(
        self,
        sport_filter: Optional[str] = None,
        game_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Get markets visible in War Room (API-friendly)
        
        🚨 WAR ROOM VISIBILITY CONTRACT:
           - Shows: state IN (EDGE, LEAN)
           - Excludes: state == NO_PLAY
           - NEVER depends on Telegram posting
        """
        query: Dict[str, Any] = {
            "visibility_flags.war_room_visible": True,
            "state": {"$in": [MarketState.EDGE.value, MarketState.LEAN.value]}
        }
        
        if sport_filter:
            query["sport"] = sport_filter
        
        if game_id:
            query["game_id"] = game_id
        
        cursor = self.collection.find(query).sort("updated_at", -1)
        
        return [self._registry_to_api_response(self._doc_to_registry(doc)) for doc in cursor]
    
    async def get_telegram_eligible(
        self,
        sport_filter: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Get Telegram-eligible markets (API-friendly)"""
        query: Dict[str, Any] = {
            "visibility_flags.telegram_allowed": True,
            "state": MarketState.EDGE.value
        }
        
        if sport_filter:
            query["sport"] = sport_filter
        
        cursor = self.collection.find(query).sort("confidence_score", -1).limit(limit)
        
        return [self._registry_to_api_response(self._doc_to_registry(doc)) for doc in cursor]
    
    async def get_parlay_eligible(
        self,
        sport_filter: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Get parlay-eligible markets (API-friendly)"""
        query: Dict[str, Any] = {
            "visibility_flags.parlay_allowed": True,
            "state": {"$in": [MarketState.EDGE.value, MarketState.LEAN.value]}
        }
        
        if sport_filter:
            query["sport"] = sport_filter
        
        cursor = self.collection.find(query).sort("confidence_score", -1).limit(limit)
        
        return [self._registry_to_api_response(self._doc_to_registry(doc)) for doc in cursor]
    
    async def check_parlay_eligibility(
        self,
        requested_legs: int = 3,
        sport_filter: Optional[str] = None,
        style: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Check parlay eligibility (API-friendly response)
        
        🚨 PARLAY FAILURE UX:
           If eligible legs < requested legs:
           - Return structured response: status = PARLAY_BLOCKED
           - Include best_single_pick fallback
           - Include next_best_actions for user
           - NEVER hard-fail or show "Load failed"
        """
        # Get all parlay-eligible markets
        eligible = await self.get_parlay_eligible(sport_filter=sport_filter, limit=50)
        
        # Filter by style if provided
        if style == "conservative":
            eligible = [m for m in eligible if (m.get("confidence_score") or 0) >= 65]
        elif style == "aggressive":
            eligible = [m for m in eligible if (m.get("edge_points") or 0) >= 3.0]
        
        passed_legs = eligible[:requested_legs]
        failed_count = max(0, requested_legs - len(passed_legs))
        
        # Find best single pick (highest edge among EDGE markets)
        edge_markets = [m for m in eligible if m.get("state") == "EDGE"]
        best_single = edge_markets[0] if edge_markets else (passed_legs[0] if passed_legs else None)
        
        # Determine status
        if len(passed_legs) >= requested_legs:
            return {
                "status": "ELIGIBLE",
                "message": f"Found {len(passed_legs)} eligible legs for your parlay",
                "passed_legs": passed_legs,
                "failed_legs": [],
                "passed_count": len(passed_legs),
                "failed_count": 0,
                "requested_legs": requested_legs,
                "best_single_pick": best_single,
                "next_best_actions": []
            }
        elif len(passed_legs) > 0:
            return {
                "status": "INSUFFICIENT_LEGS",
                "message": f"Only {len(passed_legs)} legs available. Need {requested_legs} for your parlay.",
                "passed_legs": passed_legs,
                "failed_legs": [{"reason": f"Need {failed_count} more legs"}],
                "passed_count": len(passed_legs),
                "failed_count": failed_count,
                "requested_legs": requested_legs,
                "best_single_pick": best_single,
                "next_best_actions": [
                    f"Build a {len(passed_legs)}-leg parlay instead",
                    "Take the best single pick" if best_single else None,
                    "Wait 15 mins for more edges",
                    "Try a different sport" if sport_filter else None
                ]
            }
        else:
            return {
                "status": "PARLAY_BLOCKED",
                "message": "No eligible legs found for parlay construction right now.",
                "passed_legs": [],
                "failed_legs": [{"reason": "No markets meet parlay thresholds"}],
                "passed_count": 0,
                "failed_count": requested_legs,
                "requested_legs": requested_legs,
                "best_single_pick": best_single,
                "next_best_actions": [
                    "Check back in 15 minutes",
                    "Try a different sport",
                    "View the War Room for current leans"
                ]
            }
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def _doc_to_registry(self, doc: Dict[str, Any]) -> MarketStateRegistry:
        """Convert MongoDB document to MarketStateRegistry"""
        # Handle enum conversions
        doc["market_type"] = MarketType(doc["market_type"])
        doc["state"] = MarketState(doc["state"])
        doc["volatility_flag"] = VolatilityFlag(doc.get("volatility_flag", "MODERATE"))
        doc["reason_codes"] = [ReasonCode(rc) for rc in doc.get("reason_codes", [])]
        
        # Handle visibility flags
        if "visibility_flags" in doc and isinstance(doc["visibility_flags"], dict):
            doc["visibility_flags"] = VisibilityFlags(**doc["visibility_flags"])
        
        return MarketStateRegistry(**doc)

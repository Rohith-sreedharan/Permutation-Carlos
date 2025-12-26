"""
AI Analyzer Service
Main service orchestrating AI explanations with caching and audit logging.
"""

import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo.database import Database

from .ai_analyzer_schemas import (
    AnalyzerInput,
    AnalyzerOutput,
    AnalyzerRequest,
    AnalyzerResponse,
    GameInfo,
    ModelMetrics,
    MarketState,
    PrimaryMarket,
    VolatilityLevel,
    ConfidenceFlag,
    FALLBACK_OUTPUT
)
from .ai_analyzer_context import get_context_builder
from .ai_analyzer_llm import AnalyzerLLMClient
from .ai_analyzer_audit import AnalyzerAuditLogger


class AnalyzerService:
    """
    Main AI Analyzer service.
    
    Responsibilities:
    - Fetch game data from database
    - Build analyzer input with sport-specific context
    - Manage LLM calls with caching
    - Log all operations to audit trail
    - Enforce rate limits per user/session
    """
    
    def __init__(
        self,
        db: Database,
        llm_client: AnalyzerLLMClient,
        audit_logger: AnalyzerAuditLogger,
        cache_ttl_seconds: int = 300,  # 5 minutes
        rate_limit_per_user: int = 20,  # 20 requests per hour
        rate_limit_window_seconds: int = 3600
    ):
        """
        Initialize analyzer service.
        
        Args:
            db: MongoDB database instance
            llm_client: LLM client for explanations
            audit_logger: Audit logger
            cache_ttl_seconds: Cache time-to-live
            rate_limit_per_user: Max requests per user per window
            rate_limit_window_seconds: Rate limit window
        """
        self.db = db
        self.llm_client = llm_client
        self.audit_logger = audit_logger
        self.cache_ttl_seconds = cache_ttl_seconds
        self.rate_limit_per_user = rate_limit_per_user
        self.rate_limit_window_seconds = rate_limit_window_seconds
        
        # In-memory cache {input_hash: (output, timestamp)}
        self.cache: Dict[str, tuple] = {}
    
    def explain(
        self,
        request: AnalyzerRequest,
        user_id: Optional[str] = None
    ) -> AnalyzerResponse:
        """
        Generate explanation for a game.
        
        Args:
            request: Analyzer request with game_id and sport
            user_id: Optional user identifier for rate limiting
        
        Returns:
            AnalyzerResponse with explanation or fallback
        """
        start_time = time.time()
        
        # Step 1: Rate limit check
        if user_id and not self._check_rate_limit(user_id):
            return AnalyzerResponse(
                success=False,
                game_id=request.game_id,
                sport=request.sport,
                state=MarketState.NO_PLAY,
                error="Rate limit exceeded. Please try again later.",
                fallback_triggered=True,
                cached=False
            )
        
        try:
            # Step 2: Fetch game data
            game_data = self._fetch_game_data(request.game_id, request.sport)
            
            if not game_data:
                return AnalyzerResponse(
                    success=False,
                    game_id=request.game_id,
                    sport=request.sport,
                    state=MarketState.NO_PLAY,
                    error="Game not found",
                    fallback_triggered=False,
                    cached=False
                )
            
            # Step 3: Build analyzer input
            analyzer_input = self._build_analyzer_input(
                game_data,
                request.sport,
                request.market_focus
            )
            
            # Step 4: Check cache
            input_hash = AnalyzerLLMClient.compute_input_hash(analyzer_input)
            cached_output = self._get_from_cache(input_hash)
            
            if cached_output:
                return AnalyzerResponse(
                    success=True,
                    game_id=request.game_id,
                    sport=request.sport,
                    state=analyzer_input.state,
                    explanation=cached_output,
                    cached=True
                )
            
            # Step 5: Call LLM
            llm_result = self.llm_client.explain(analyzer_input)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Step 6: Store in cache
            if llm_result["success"]:
                self._store_in_cache(input_hash, llm_result["output"])
            
            # Step 7: Audit log
            audit_id = self.audit_logger.log(
                game_id=request.game_id,
                sport=request.sport,
                state=analyzer_input.state,
                input_hash=input_hash,
                output_hash=AnalyzerLLMClient.compute_output_hash(llm_result["output"]),
                llm_model=self.llm_client.model,
                response_time_ms=response_time_ms,
                tokens_used=llm_result.get("tokens_used"),
                user_id=user_id,
                blocked=llm_result.get("blocked", False),
                block_reason=llm_result.get("block_reason"),
                fallback_triggered=llm_result.get("fallback_triggered", False)
            )
            
            # Step 8: Return response
            return AnalyzerResponse(
                success=llm_result["success"],
                game_id=request.game_id,
                sport=request.sport,
                state=analyzer_input.state,
                explanation=llm_result["output"],
                fallback_triggered=llm_result.get("fallback_triggered", False),
                cached=False,
                audit_id=audit_id
            )
        
        except Exception as e:
            # Unexpected error - return safe fallback
            return AnalyzerResponse(
                success=False,
                game_id=request.game_id,
                sport=request.sport,
                state=MarketState.NO_PLAY,
                error=f"Service error: {str(e)}",
                fallback_triggered=True,
                cached=False
            )
    
    def _fetch_game_data(self, game_id: str, sport: str) -> Optional[Dict[str, Any]]:
        """
        Fetch game data from database.
        
        Args:
            game_id: Game identifier
            sport: Sport name
        
        Returns:
            Game data dict or None if not found
        """
        # Query autonomous_edge_waves collection
        game = self.db.autonomous_edge_waves.find_one({
            "game_id": game_id,
            "sport": sport
        })
        
        return game
    
    def _build_analyzer_input(
        self,
        game_data: Dict[str, Any],
        sport: str,
        market_focus: Optional[PrimaryMarket] = None
    ) -> AnalyzerInput:
        """
        Build AnalyzerInput from game data.
        
        Args:
            game_data: Game data from database
            sport: Sport name
            market_focus: Optional market focus
        
        Returns:
            AnalyzerInput ready for LLM
        """
        # Get sport-specific context builder
        context_builder = get_context_builder(sport)
        
        # Build game info
        game_info = GameInfo(
            home=game_data.get("home_team", "UNKNOWN"),
            away=game_data.get("away_team", "UNKNOWN"),
            start_time_utc=game_data.get("start_time_utc", datetime.utcnow().isoformat())
        )
        
        # Extract state
        state_str = game_data.get("state", "NO_PLAY")
        state = MarketState(state_str)
        
        # Determine primary market
        if market_focus:
            primary_market = market_focus
        else:
            primary_market = self._determine_primary_market(game_data, sport)
        
        # Build metrics
        metrics_data = game_data.get("metrics", {})
        metrics = ModelMetrics(
            edge_pts=metrics_data.get("edge_pts"),
            total_deviation_pts=metrics_data.get("total_deviation_pts"),
            clv_forecast_pct=metrics_data.get("clv_forecast_pct"),
            volatility=VolatilityLevel(metrics_data.get("volatility", "MEDIUM")),
            confidence_flag=ConfidenceFlag(metrics_data.get("confidence_flag", "UNKNOWN")),
            win_prob_pct=metrics_data.get("win_prob_pct")
        )
        
        # Build context flags
        context = context_builder.build_context(game_data)
        
        # Extract reason codes
        reason_codes = context_builder.extract_reason_codes(game_data, metrics_data)
        
        # Build complete input
        analyzer_input = AnalyzerInput(
            sport=sport,
            game=game_info,
            state=state,
            primary_market=primary_market,
            metrics=metrics,
            context=context,
            reason_codes=reason_codes
        )
        
        return analyzer_input
    
    def _determine_primary_market(
        self,
        game_data: Dict[str, Any],
        sport: str
    ) -> PrimaryMarket:
        """
        Determine primary market from game data.
        
        Args:
            game_data: Game data
            sport: Sport name
        
        Returns:
            PrimaryMarket enum
        """
        # Check if game data specifies primary market
        if "primary_market" in game_data:
            return PrimaryMarket(game_data["primary_market"])
        
        # Default by sport
        defaults = {
            "NBA": PrimaryMarket.SPREAD,
            "NFL": PrimaryMarket.SPREAD,
            "NCAAB": PrimaryMarket.SPREAD,
            "NCAAF": PrimaryMarket.SPREAD,
            "MLB": PrimaryMarket.RUNLINE,
            "NHL": PrimaryMarket.PUCKLINE
        }
        
        return defaults.get(sport, PrimaryMarket.SPREAD)
    
    def _check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user is within rate limit.
        
        Args:
            user_id: User identifier
        
        Returns:
            True if allowed, False if rate limited
        """
        # Query recent requests from audit log
        cutoff_time = datetime.utcnow() - timedelta(seconds=self.rate_limit_window_seconds)
        
        recent_count = self.db.analyzer_audit.count_documents({
            "user_id": user_id,
            "timestamp": {"$gte": cutoff_time.isoformat()}
        })
        
        return recent_count < self.rate_limit_per_user
    
    def _get_from_cache(self, input_hash: str) -> Optional[AnalyzerOutput]:
        """
        Get output from cache if not expired.
        
        Args:
            input_hash: Input hash
        
        Returns:
            Cached AnalyzerOutput or None
        """
        if input_hash in self.cache:
            output, timestamp = self.cache[input_hash]
            
            # Check if expired
            age_seconds = time.time() - timestamp
            if age_seconds < self.cache_ttl_seconds:
                return output
            else:
                # Expired - remove from cache
                del self.cache[input_hash]
        
        return None
    
    def _store_in_cache(self, input_hash: str, output: AnalyzerOutput):
        """
        Store output in cache.
        
        Args:
            input_hash: Input hash
            output: Output to cache
        """
        self.cache[input_hash] = (output, time.time())
        
        # Simple cache cleanup - remove oldest entries if cache too large
        if len(self.cache) > 1000:
            # Sort by timestamp and keep most recent 500
            sorted_items = sorted(
                self.cache.items(),
                key=lambda x: x[1][1],
                reverse=True
            )
            self.cache = dict(sorted_items[:500])
    
    def clear_cache(self):
        """Clear all cached outputs"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dict with cache stats and LLM stats
        """
        return {
            "cache_size": len(self.cache),
            "llm_stats": self.llm_client.get_stats()
        }

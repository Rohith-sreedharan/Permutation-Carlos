"""
Signal Generation Engine
Converts Monte Carlo simulations to qualified signals with state machine
"""
from typing import Optional, Literal, Dict, List, Tuple, Any
from datetime import datetime, timezone, timedelta
from pymongo.database import Database
import uuid

from db.schemas.telegram_schemas import (
    Signal,
    SignalState,
    SharpSideAction,
    SignalQualificationThresholds,
    COLLECTIONS
)


class SignalGenerationEngine:
    """
    Core signal qualification engine
    Converts simulation outputs to actionable signals
    """
    
    def __init__(self, db: Database):
        self.db = db
        self.thresholds = SignalQualificationThresholds()  # Default thresholds
    
    # ========================================================================
    # SIGNAL QUALIFICATION
    # ========================================================================
    
    async def qualify_signal(
        self,
        simulation_result: Dict
    ) -> Signal:
        """
        Qualify a simulation result into a signal
        
        Args:
            simulation_result: Output from Monte Carlo engine
                {
                    "simulation_id": str,
                    "sport": str,
                    "game_id": str,
                    "home_team": str,
                    "away_team": str,
                    "game_commence_time": datetime,
                    "market_type": "spread" | "total" | "moneyline",
                    "market_line_vegas": float,
                    "model_line": float,
                    "edge": float,
                    "win_prob": float,
                    "variance": "low" | "medium" | "high",
                    "sim_count": int
                }
        
        Returns:
            Signal with computed state
        """
        # Extract simulation data
        signal = Signal(
            signal_id=f"sig_{uuid.uuid4().hex[:12]}",
            sport=simulation_result["sport"],
            game_id=simulation_result["game_id"],
            home_team=simulation_result["home_team"],
            away_team=simulation_result["away_team"],
            game_commence_time=simulation_result["game_commence_time"],
            market_type=simulation_result["market_type"],
            market_line_vegas=simulation_result["market_line_vegas"],
            model_line=simulation_result["model_line"],
            edge=simulation_result["edge"],
            win_prob=simulation_result["win_prob"],
            variance=simulation_result["variance"],
            sim_count_internal=simulation_result["sim_count"],
            sim_count_display=100000,  # Always show 100k
            simulation_id=simulation_result.get("simulation_id"),
            state=SignalState.PENDING
        )
        
        # Determine signal state
        state, reason = self._compute_signal_state(signal)
        signal.state = state
        signal.reason_code = reason
        
        # For spreads: compute sharp side action
        if signal.market_type == "spread" and state == SignalState.QUALIFIED:
            sharp_state, sharp_target = await self._compute_sharp_side_action(signal)
            signal.sharp_side_state = sharp_state
            signal.sharp_side_target = sharp_target
            
            # Disallow QUALIFIED if sharp side is CONFLICTED
            if sharp_state == SharpSideAction.CONFLICTED:
                signal.state = SignalState.LEAN
                signal.reason_code = "sharp_side_conflicted"
        
        # Persist signal
        await self._save_signal(signal)
        
        return signal
    
    def _compute_signal_state(
        self,
        signal: Signal
    ) -> Tuple[str, str]:
        """
        Apply qualification thresholds
        
        Returns:
            (state, reason_code)
        """
        # Check game hasn't started
        time_to_game = (signal.game_commence_time - datetime.now(timezone.utc)).total_seconds()
        if time_to_game < 0:
            return SignalState.INVALIDATED_GAME_STARTED, "game_already_started"
        
        # Qualified thresholds
        if (
            signal.edge >= self.thresholds.edge_min_qualified
            and signal.win_prob >= self.thresholds.prob_min_qualified
            and signal.variance in ["low", "medium"]
        ):
            return SignalState.QUALIFIED, "meets_qualified_criteria"
        
        # Lean (NO PLAY) thresholds
        if (
            signal.edge >= self.thresholds.edge_min_lean
            and signal.win_prob >= self.thresholds.prob_min_lean
        ):
            return SignalState.LEAN, "meets_lean_criteria"
        
        # Below thresholds
        return SignalState.NO_PLAY, "below_thresholds"
    
    async def _compute_sharp_side_action(
        self,
        signal: Signal
    ) -> Tuple[str, str]:
        """
        Compute sharp side action for spread markets
        
        Returns:
            (sharp_side_state, sharp_target)
        """
        # Fetch sharp action data from integrations
        # (Assumes existing sharp action API integration)
        sharp_data = await self._fetch_sharp_action(
            signal.game_id,
            signal.market_type
        )
        
        if not sharp_data:
            return SharpSideAction.ABSENT, self._format_sharp_target(signal)
        
        # Determine model's recommended side
        model_recommends_home = signal.model_line > signal.market_line_vegas
        
        # Check if sharp action aligns with model
        sharp_on_home = sharp_data.get("sharp_on_home", False)
        sharp_on_away = sharp_data.get("sharp_on_away", False)
        
        if model_recommends_home and sharp_on_home:
            return SharpSideAction.CONFIRMED, self._format_sharp_target(signal)
        elif not model_recommends_home and sharp_on_away:
            return SharpSideAction.CONFIRMED, self._format_sharp_target(signal)
        elif (model_recommends_home and sharp_on_away) or (not model_recommends_home and sharp_on_home):
            return SharpSideAction.CONFLICTED, self._format_sharp_target(signal)
        elif sharp_data.get("contrarian", False):
            return SharpSideAction.CONTRARIAN, self._format_sharp_target(signal)
        else:
            return SharpSideAction.ABSENT, self._format_sharp_target(signal)
    
    def _format_sharp_target(self, signal: Signal) -> str:
        """Format sharp side target (e.g., 'Lakers +8')"""
        if signal.model_line > signal.market_line_vegas:
            # Model favors home team
            line_display = f"{signal.market_line_vegas:+.1f}"
            return f"{signal.home_team} {line_display}"
        else:
            # Model favors away team
            line_display = f"{-signal.market_line_vegas:+.1f}"
            return f"{signal.away_team} {line_display}"
    
    async def _fetch_sharp_action(
        self,
        game_id: str,
        market_type: str
    ) -> Optional[Dict]:
        """
        Fetch sharp action data from integrations
        
        Returns:
            {
                "sharp_on_home": bool,
                "sharp_on_away": bool,
                "contrarian": bool,
                "sharp_percentage": float
            }
        """
        # TODO: Integrate with OddsJam, Unabated, or internal sharp tracker
        # For now, return None (ABSENT sharp action)
        return None
    
    # ========================================================================
    # LINE MOVEMENT INVALIDATION
    # ========================================================================
    
    async def check_line_movement_invalidation(
        self,
        signal_id: str
    ) -> bool:
        """
        Check if signal should be invalidated due to line movement
        
        Returns:
            True if invalidated (line moved too much)
        """
        signal = await self.get_signal(signal_id)
        if not signal:
            return False
        
        # Only check QUALIFIED or LEAN signals
        if signal.state not in [SignalState.QUALIFIED, SignalState.LEAN]:
            return False
        
        # Fetch current market line
        current_line = await self._fetch_current_market_line(
            signal.game_id,
            signal.market_type
        )
        
        if current_line is None:
            return False
        
        # Check movement tolerance
        line_diff = abs(current_line - signal.market_line_vegas)
        
        if signal.market_type == "spread":
            tolerance = self.thresholds.line_move_tolerance_spread
        elif signal.market_type == "total":
            tolerance = self.thresholds.line_move_tolerance_total
        else:
            tolerance = 999  # No invalidation for moneyline
        
        if line_diff > tolerance:
            # Invalidate signal
            self.db[COLLECTIONS["signals"]].update_one(
                {"signal_id": signal_id},
                {
                    "$set": {
                        "state": SignalState.INVALIDATED_LINE_MOVED,
                        "reason_code": f"line_moved_{line_diff:.1f}pts",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return True
        
        return False
    
    async def _fetch_current_market_line(
        self,
        game_id: str,
        market_type: str
    ) -> Optional[float]:
        """Fetch current line from odds provider"""
        # TODO: Integrate with live odds feed
        # For now, return None (no invalidation)
        return None
    
    # ========================================================================
    # DAILY CAPS & FILTERING
    # ========================================================================
    
    async def get_qualified_signals_today(self) -> List[Signal]:
        """Get all QUALIFIED signals for today (respects daily cap)"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        cursor = self.db[COLLECTIONS["signals"]].find({
            "state": SignalState.QUALIFIED,
            "created_at": {"$gte": today_start}
        }).sort("created_at", 1)
        
        signals = []
        for doc in list(cursor):
            signals.append(Signal(**doc))
        
        # Enforce daily cap
        return signals[:self.thresholds.max_qualified_per_day]
    
    async def get_lean_signals_today(self) -> List[Signal]:
        """Get all LEAN signals for today (respects daily cap)"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        cursor = self.db[COLLECTIONS["signals"]].find({
            "state": SignalState.LEAN,
            "created_at": {"$gte": today_start}
        }).sort("created_at", 1)
        
        signals = []
        for doc in list(cursor):
            signals.append(Signal(**doc))
        
        return signals[:self.thresholds.max_leans_per_day]
    
    # ========================================================================
    # SIGNAL PERSISTENCE
    # ========================================================================
    
    async def _save_signal(self, signal: Signal):
        """Upsert signal to database"""
        self.db[COLLECTIONS["signals"]].update_one(
            {"signal_id": signal.signal_id},
            {"$set": signal.dict()},
            upsert=True
        )
    
    async def get_signal(self, signal_id: str) -> Optional[Signal]:
        """Retrieve signal by ID"""
        doc = self.db[COLLECTIONS["signals"]].find_one(
            {"signal_id": signal_id}
        )
        return Signal(**doc) if doc else None
    
    async def get_signals_by_game(
        self,
        game_id: str,
        states: Optional[List[str]] = None
    ) -> List[Signal]:
        """Get all signals for a specific game"""
        query: Dict[str, Any] = {"game_id": game_id}
        if states:
            query["state"] = {"$in": states}
        
        cursor = self.db[COLLECTIONS["signals"]].find(query)
        signals = []
        for doc in list(cursor):
            signals.append(Signal(**doc))
        
        return signals
    
    # ========================================================================
    # SIGNAL LIFECYCLE
    # ========================================================================
    
    async def mark_signal_posted(self, signal_id: str):
        """Mark signal as posted to Telegram"""
        self.db[COLLECTIONS["signals"]].update_one(
            {"signal_id": signal_id},
            {
                "$set": {
                    "state": SignalState.POSTED,
                    "posted_at": datetime.now(timezone.utc)
                }
            }
        )
    
    async def close_signal(self, signal_id: str):
        """Close signal (game finished)"""
        self.db[COLLECTIONS["signals"]].update_one(
            {"signal_id": signal_id},
            {
                "$set": {
                    "state": SignalState.CLOSED,
                    "closed_at": datetime.now(timezone.utc)
                }
            }
        )
    
    # ========================================================================
    # BATCH OPERATIONS
    # ========================================================================
    
    async def invalidate_signals_for_started_games(self) -> int:
        """Invalidate all signals for games that have started"""
        now = datetime.now(timezone.utc)
        
        result = self.db[COLLECTIONS["signals"]].update_many(
            {
                "state": {"$in": [SignalState.QUALIFIED, SignalState.LEAN, SignalState.PENDING]},
                "game_commence_time": {"$lt": now}
            },
            {
                "$set": {
                    "state": SignalState.INVALIDATED_GAME_STARTED,
                    "reason_code": "game_started",
                    "updated_at": now
                }
            }
        )
        
        return result.modified_count


class SignalFormatter:
    """Formats signals for Telegram distribution"""
    
    @staticmethod
    def format_telegram_message(signal: Signal) -> str:
        """
        Generate deterministic Telegram message
        
        Format:
            🔥 [SPORT] SIGNAL
            Game: Team A @ Team B
            Market: Spread
            Edge: +8.2 pts
            Win Prob: 58.4%
            Variance: Low
            
            💰 Sharp Side: Team A +8
            
            Simulations: 100,000
            🚨 QUALIFIED SIGNAL
        """
        # Header
        sport_emoji = {
            "NBA": "🏀",
            "NFL": "🏈",
            "MLB": "⚾",
            "NHL": "🏒"
        }.get(signal.sport, "🔥")
        
        lines = [
            f"{sport_emoji} {signal.sport.upper()} SIGNAL",
            f"Game: {signal.away_team} @ {signal.home_team}",
            f"Market: {signal.market_type.title()}",
            f"Edge: {signal.edge:+.1f} {'pts' if signal.market_type in ['spread', 'total'] else 'units'}",
            f"Win Prob: {signal.win_prob * 100:.1f}%",
            f"Variance: {signal.variance.title()}",
            ""
        ]
        
        # Sharp side action (spreads only)
        if signal.sharp_side_target and signal.sharp_side_state:
            sharp_emoji = {
                SharpSideAction.CONFIRMED: "✅",
                SharpSideAction.CONTRARIAN: "⚠️",
                SharpSideAction.ABSENT: "ℹ️"
            }.get(signal.sharp_side_state, "💰")
            
            lines.append(f"{sharp_emoji} Sharp Side: {signal.sharp_side_target}")
            lines.append("")
        
        # Simulations
        lines.append(f"Simulations: {signal.sim_count_display:,}")
        
        # State badge
        if signal.state == SignalState.QUALIFIED:
            lines.append("🚨 QUALIFIED SIGNAL")
        elif signal.state == SignalState.LEAN:
            lines.append("📊 LEAN (NO PLAY)")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_no_play_message(signal: Signal) -> str:
        """
        Format NO PLAY market update
        
        Format:
            📊 MARKET UPDATE
            Game: Team A @ Team B
            Market: Total
            Status: NO PLAY
            
            Edge below threshold (4.2 pts)
        """
        sport_emoji = {
            "NBA": "🏀",
            "NFL": "🏈",
            "MLB": "⚾",
            "NHL": "🏒"
        }.get(signal.sport, "📊")
        
        lines = [
            f"{sport_emoji} MARKET UPDATE",
            f"Game: {signal.away_team} @ {signal.home_team}",
            f"Market: {signal.market_type.title()}",
            f"Status: NO PLAY",
            "",
            f"Edge below threshold ({signal.edge:.1f} pts)"
        ]
        
        return "\n".join(lines)

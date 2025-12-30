"""
Signal Posting Service
Orchestrates signal distribution to Telegram channels

CRITICAL POSTING RULES (NON-NEGOTIABLE):
1. Only post LOCKED signals (passed confirmation window)
2. Post the FIRST signal that crossed threshold, NOT the latest
3. Never silently retract or replace signals
4. State changes (MONITORING, WEAKENED, INVALIDATED) require explicit posts
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from pymongo.database import Database

from db.schemas.telegram_schemas import (
    Signal,
    SignalState,
    TelegramChannel,
    COLLECTIONS
)
from services.telegram_bot_service import TelegramBotService
from services.signal_generation_service import SignalFormatter
from services.signal_locking_service import (
    SignalLockingService,
    LockedSignalRecord,
    LockedSignalState,
    LockedSignalFormatter,
    InvalidationReason
)


class SignalPostingService:
    """
    Manages signal distribution to Telegram channels
    
    WORKFLOW (CORRECT):
    1. SignalLockingService confirms and locks signals
    2. This service posts ONLY locked signals
    3. State changes trigger update posts, never silent deletions
    
    WHAT WE NEVER DO:
    - Delete signals
    - Replace them silently
    - Post opposite signal without explanation
    - Post the "latest" sim (we post the FIRST confirmed)
    """
    
    def __init__(
        self,
        db: Database,
        telegram_bot: TelegramBotService,
        locking_service: Optional[SignalLockingService] = None
    ):
        self.db = db
        self.telegram_bot = telegram_bot
        self.formatter = SignalFormatter()
        self.locked_formatter = LockedSignalFormatter()
        self.locking_service = locking_service or SignalLockingService(db)
    
    # ========================================================================
    # LOCKED SIGNAL POSTING (NEW - CORRECT APPROACH)
    # ========================================================================
    
    async def post_locked_signals(self) -> Dict[str, int]:
        """
        Post all locked signals that haven't been posted yet
        
        This is the CORRECT method for Telegram posting.
        Only posts signals that passed confirmation window.
        
        Returns:
            {posted: int, failed: int}
        """
        stats = {"posted": 0, "failed": 0}
        
        # Get signals ready to post
        signals_to_post = await self.locking_service.get_signals_to_post()
        
        for locked_signal in signals_to_post:
            try:
                await self.post_locked_signal(locked_signal)
                stats["posted"] += 1
            except Exception as e:
                print(f"Failed to post locked signal {locked_signal.locked_signal_id}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def post_locked_signal(
        self,
        locked_signal: LockedSignalRecord
    ) -> Dict[str, str]:
        """
        Post a single locked signal to Telegram
        
        CRITICAL: This posts the signal frozen at DECISION TIME.
        Not the latest simulation, not the freshest data.
        The FIRST confirmed signal is the source of truth.
        
        Returns:
            {channel_name: telegram_message_id}
        """
        if locked_signal.telegram_posted:
            return locked_signal.telegram_message_ids
        
        if locked_signal.state != LockedSignalState.ACTIVE_EDGE:
            raise ValueError(f"Can only post ACTIVE_EDGE signals, got {locked_signal.state}")
        
        # Format message using locked signal data (decision-time snapshot)
        message = self.locked_formatter.format_active_edge(locked_signal)
        
        # Get target channels
        channels = await self._get_channels_for_sport(locked_signal.sport)
        
        # Post to each channel
        posted = {}
        for channel in channels:
            message_id = await self.telegram_bot.send_channel_message(
                channel_id=channel.channel_id,
                message=message,
                signal_id=locked_signal.locked_signal_id
            )
            
            if message_id:
                posted[channel.channel_name] = message_id
        
        # Mark as posted
        await self.locking_service.mark_as_posted(
            locked_signal.locked_signal_id,
            posted
        )
        
        return posted
    
    async def post_state_updates(self) -> Dict[str, int]:
        """
        Post updates for signals whose state changed
        
        This handles:
        - MONITORING: "Still holding, no add"
        - WEAKENED: "Confidence dropped, reduce exposure"
        - INVALIDATED: Full explanation of why signal is void
        
        Returns:
            {updates_posted: int, failed: int}
        """
        stats = {"updates_posted": 0, "failed": 0}
        
        signals_needing_update = await self.locking_service.get_signals_needing_update()
        
        for signal in signals_needing_update:
            try:
                await self._post_state_update(signal)
                stats["updates_posted"] += 1
            except Exception as e:
                print(f"Failed to post update for {signal.locked_signal_id}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def _post_state_update(self, signal: LockedSignalRecord):
        """Post state update message"""
        message = self.locked_formatter.format_for_state(signal)
        
        # Reply to original message if possible
        for channel_name, original_msg_id in signal.telegram_message_ids.items():
            channel = await self._get_channel_by_name(channel_name)
            if channel:
                await self.telegram_bot.send_channel_message(
                    channel_id=channel.channel_id,
                    message=message,
                    reply_to_message_id=original_msg_id
                )
    
    # ========================================================================
    # LEGACY SIGNAL POSTING (DEPRECATED - FOR BACKWARDS COMPATIBILITY)
    # ========================================================================
    
    async def post_qualified_signal(self, signal: Signal) -> Dict[str, str]:
        """
        [DEPRECATED] Post QUALIFIED signal to Telegram channels
        
        WARNING: This method posts without confirmation window.
        Use post_locked_signal() instead for proper signal locking.
        
        Returns:
            {channel_name: telegram_message_id}
        """
        print("WARNING: post_qualified_signal is deprecated. Use post_locked_signal instead.")
        
        if signal.state != SignalState.QUALIFIED:
            raise ValueError(f"Cannot post signal with state {signal.state}")
        
        # Format message
        message = self.formatter.format_telegram_message(signal)
        
        # Get target channels
        channels = await self._get_channels_for_signal(signal)
        
        # Post to each channel
        posted = {}
        for channel in channels:
            message_id = await self.telegram_bot.send_channel_message(
                channel_id=channel.channel_id,
                message=message,
                signal_id=signal.signal_id
            )
            
            if message_id:
                posted[channel.channel_name] = message_id
        
        # Mark signal as posted
        self.db[COLLECTIONS["signals"]].update_one(
            {"signal_id": signal.signal_id},
            {
                "$set": {
                    "state": SignalState.POSTED,
                    "posted_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return posted
    
    async def post_lean_signal(self, signal: Signal) -> Dict[str, str]:
        """
        Post LEAN (NO PLAY) signal to platform only
        NOT posted to Telegram (internal use)
        
        Returns:
            Empty dict (no Telegram posting)
        """
        # LEAN signals stay on platform, not posted to Telegram
        return {}
    
    async def post_no_play_update(self, signal: Signal) -> Dict[str, str]:
        """
        Post NO PLAY market update (optional)
        
        Returns:
            {channel_name: telegram_message_id}
        """
        # Format NO PLAY message
        message = self.formatter.format_no_play_message(signal)
        
        # Get channels
        channels = await self._get_channels_for_signal(signal)
        
        # Post to each channel
        posted = {}
        for channel in channels:
            message_id = await self.telegram_bot.send_channel_message(
                channel_id=channel.channel_id,
                message=message,
                signal_id=signal.signal_id
            )
            
            if message_id:
                posted[channel.channel_name] = message_id
        
        return posted
    
    async def _get_channels_for_signal(self, signal: Signal) -> List[TelegramChannel]:
        """Get target channels based on signal tier"""
        cursor = self.db[COLLECTIONS["telegram_channels"]].find({
            "channel_name": "signals",
            "channel_type": "private_signals"
        })
        
        channels = []
        for doc in list(cursor):
            channels.append(TelegramChannel(**doc))
        
        return channels
    
    async def _get_channels_for_sport(self, sport: str) -> List[TelegramChannel]:
        """Get target channels for a sport"""
        # For v1: all signals go to main 'signals' channel
        cursor = self.db[COLLECTIONS["telegram_channels"]].find({
            "channel_name": "signals",
            "channel_type": "private_signals"
        })
        
        channels = []
        for doc in list(cursor):
            channels.append(TelegramChannel(**doc))
        
        return channels
    
    async def _get_channel_by_name(self, channel_name: str) -> Optional[TelegramChannel]:
        """Get channel config by name"""
        doc = self.db[COLLECTIONS["telegram_channels"]].find_one({
            "channel_name": channel_name
        })
        
        if doc:
            return TelegramChannel(**doc)
        return None
    
    # ========================================================================
    # BATCH POSTING (UPDATED TO USE LOCKING)
    # ========================================================================
    
    async def post_daily_signals(self) -> Dict[str, int]:
        """
        [UPDATED] Post all locked signals for today
        
        Now uses the proper locking system instead of posting latest signals.
        
        Returns:
            Statistics: {posted: int, failed: int, updates: int}
        """
        stats = {"posted": 0, "failed": 0, "updates": 0}
        
        # Step 1: Post new locked signals (FIRST confirmed, not latest)
        locked_stats = await self.post_locked_signals()
        stats["posted"] = locked_stats["posted"]
        stats["failed"] = locked_stats["failed"]
        
        # Step 2: Post state updates (MONITORING, WEAKENED, INVALIDATED)
        update_stats = await self.post_state_updates()
        stats["updates"] = update_stats["updates_posted"]
        
        return stats
    
    # ========================================================================
    # SIGNAL INVALIDATION (NOT SILENT RETRACTION)
    # ========================================================================
    
    async def invalidate_signal(
        self,
        locked_signal_id: str,
        reason: InvalidationReason,
        explanation: str
    ) -> bool:
        """
        Invalidate a locked signal with explicit explanation
        
        This is the ONLY correct way to void a signal.
        Posts an explanation to Telegram - never silently removes.
        
        Args:
            locked_signal_id: ID of the locked signal
            reason: Enum reason for invalidation
            explanation: Human-readable explanation
            
        Returns:
            True if invalidation successful
        """
        # Invalidate in database
        success = await self.locking_service.invalidate_signal(
            locked_signal_id,
            reason,
            explanation
        )
        
        if success:
            # Post invalidation notice to Telegram
            signal = await self.locking_service.get_locked_signal(locked_signal_id)
            if signal:
                message = self.locked_formatter.format_invalidated(signal)
                
                # Post to all channels where original was posted
                for channel_name in signal.telegram_message_ids.keys():
                    channel = await self._get_channel_by_name(channel_name)
                    if channel:
                        await self.telegram_bot.send_channel_message(
                            channel_id=channel.channel_id,
                            message=message
                        )
        
        return success
    
    async def retract_signal(
        self,
        signal_id: str,
        reason: str = "line_moved"
    ) -> bool:
        """
        [DEPRECATED] Use invalidate_signal() instead
        
        This method exists for backwards compatibility only.
        Silent retractions are NOT allowed in the new system.
        """
        print("WARNING: retract_signal is deprecated. Use invalidate_signal instead.")
        print("Silent retractions violate signal locking rules.")
        
        # Map old reason to new InvalidationReason
        reason_map = {
            "line_moved": InvalidationReason.LINE_MOVED_MATERIALLY,
            "injury": InvalidationReason.INJURY_UPDATE,
            "lineup": InvalidationReason.LINEUP_CHANGE,
            "suspended": InvalidationReason.MARKET_SUSPENSION
        }
        
        invalidation_reason = reason_map.get(
            reason,
            InvalidationReason.MANUAL_INVALIDATION
        )
        
        # Find the locked signal for this game
        signal_doc = self.db[COLLECTIONS["signals"]].find_one({"signal_id": signal_id})
        if not signal_doc:
            return False
        
        # Find corresponding locked signal
        from services.signal_locking_service import LOCKING_COLLECTIONS
        locked_doc = self.db[LOCKING_COLLECTIONS["locked_signals"]].find_one({
            "game_id": signal_doc.get("game_id"),
            "market_key": signal_doc.get("market_key", signal_doc.get("market_type", "").upper())
        })
        
        if locked_doc:
            return await self.invalidate_signal(
                locked_doc["locked_signal_id"],
                invalidation_reason,
                f"Signal invalidated: {reason}"
            )
        
        return False


class SignalScheduler:
    """
    Automated signal distribution scheduler
    
    UPDATED: Now uses proper signal locking workflow
    """
    
    def __init__(
        self,
        db: Database,
        posting_service: SignalPostingService,
        locking_service: Optional[SignalLockingService] = None
    ):
        self.db = db
        self.posting_service = posting_service
        self.locking_service = locking_service or SignalLockingService(db)
    
    async def run_signal_pipeline(self) -> Dict[str, int]:
        """
        Run complete signal pipeline with PROPER locking:
        
        1. Process new simulations through confirmation window
        2. Lock signals that pass N-of-M confirmation
        3. Post FIRST confirmed signal (not latest!)
        4. Post state updates (MONITORING, WEAKENED, INVALIDATED)
        5. Never silently retract or flip signals
        
        Returns:
            Statistics
        """
        from services.signal_generation_service import SignalGenerationEngine
        
        signal_engine = SignalGenerationEngine(self.db)
        stats = {
            "confirmed": 0,
            "rejected": 0,
            "already_locked": 0,
            "posted": 0,
            "updates": 0,
            "invalidated": 0
        }
        
        # Step 1: Process pending simulations through locking system
        # (This should be called after each simulation run)
        # The locking service handles N-of-M confirmation
        
        # Step 2: Post all ready signals (locked, not yet posted)
        post_stats = await self.posting_service.post_daily_signals()
        stats["posted"] = post_stats["posted"]
        stats["updates"] = post_stats.get("updates", 0)
        
        # Step 3: Check for games that started (auto-invalidate unpublished signals)
        # Note: Published signals stay published - we don't silently remove them
        from datetime import datetime, timezone
        from services.signal_locking_service import LOCKING_COLLECTIONS, LockedSignalState
        
        # Find locked signals for games that have started but weren't posted
        # (This handles edge case where confirmation took too long)
        cursor = self.db[LOCKING_COLLECTIONS["locked_signals"]].find({
            "telegram_posted": False,
            "state": LockedSignalState.ACTIVE_EDGE.value
        })
        
        for doc in list(cursor):
            # Check if game started (would need game data)
            # For now, leave this to manual invalidation
            pass
        
        return stats
    
    async def process_simulation_result(
        self,
        simulation_result: Dict
    ) -> Dict[str, str]:
        """
        Process a new simulation result through the locking pipeline
        
        THIS IS THE CORRECT ENTRY POINT for new simulations.
        
        Args:
            simulation_result: Output from Monte Carlo engine
            
        Returns:
            {status: str, locked_signal_id: Optional[str]}
        """
        # Extract required fields
        game_id = simulation_result["game_id"]
        market_key = simulation_result.get("market_type", "SPREAD").upper()
        sport = simulation_result["sport"]
        
        # Build selection string
        selection = self._build_selection_string(simulation_result)
        
        # Process through locking service
        status, locked_record = await self.locking_service.process_signal(
            signal_id=simulation_result.get("signal_id", f"sim_{game_id}_{market_key}"),
            game_id=game_id,
            market_key=market_key,
            sport=sport,
            selection=selection,
            line_value=simulation_result.get("market_line_vegas", 0),
            edge_points=simulation_result.get("edge", 0),
            win_prob=simulation_result.get("win_prob", 0.5),
            confidence_score=simulation_result.get("confidence", 0.5),
            sim_count=simulation_result.get("sim_count", 100000),
            sim_run_id=simulation_result.get("sim_run_id", ""),
            market_snapshot_id=simulation_result.get("market_snapshot_id", "")
        )
        
        result = {"status": status}
        
        if locked_record:
            result["locked_signal_id"] = locked_record.locked_signal_id
            
            # If just locked, post immediately
            if status == "LOCKED":
                await self.posting_service.post_locked_signal(locked_record)
        
        return result
    
    def _build_selection_string(self, sim_result: Dict) -> str:
        """Build human-readable selection string"""
        market_type = sim_result.get("market_type", "spread").lower()
        line = sim_result.get("market_line_vegas", 0)
        
        if market_type == "spread":
            team = sim_result.get("home_team", "Home")
            return f"{team} {line:+.1f}"
        elif market_type == "total":
            return f"{'Over' if sim_result.get('over', True) else 'Under'} {line:.1f}"
        else:
            return f"{sim_result.get('selection', 'Unknown')}"

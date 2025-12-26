"""
Signal Posting Service
Orchestrates signal distribution to Telegram channels
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from pymongo.database import Database

from backend.db.schemas.telegram_schemas import (
    Signal,
    SignalState,
    TelegramChannel,
    COLLECTIONS
)
from backend.services.telegram_bot_service import TelegramBotService
from backend.services.signal_generation_service import SignalFormatter


class SignalPostingService:
    """
    Manages signal distribution to Telegram channels
    Enforces posting rules and daily caps
    """
    
    def __init__(
        self,
        db: Database,
        telegram_bot: TelegramBotService
    ):
        self.db = db
        self.telegram_bot = telegram_bot
        self.formatter = SignalFormatter()
    
    # ========================================================================
    # SIGNAL POSTING
    # ========================================================================
    
    async def post_qualified_signal(self, signal: Signal) -> Dict[str, str]:
        """
        Post QUALIFIED signal to Telegram channels
        
        Returns:
            {channel_name: telegram_message_id}
        """
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
        # For v1: all qualified signals go to 'signals' channel
        # Future: premium signals to 'premium' channel
        
        cursor = self.db[COLLECTIONS["telegram_channels"]].find({
            "channel_name": "signals",
            "channel_type": "private_signals"
        })
        
        channels = []
        for doc in list(cursor):
            channels.append(TelegramChannel(**doc))
        
        return channels
    
    # ========================================================================
    # BATCH POSTING
    # ========================================================================
    
    async def post_daily_signals(self) -> Dict[str, int]:
        """
        Post all qualified signals for today (respects daily cap)
        
        Returns:
            Statistics: {posted: int, failed: int}
        """
        stats = {"posted": 0, "failed": 0}
        
        # Get today's qualified signals (not yet posted)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        cursor = self.db[COLLECTIONS["signals"]].find({
            "state": SignalState.QUALIFIED,
            "created_at": {"$gte": today_start},
            "posted_at": None
        }).sort("created_at", 1).limit(3)  # Max 3 per day
        
        for doc in list(cursor):
            signal = Signal(**doc)
            
            try:
                await self.post_qualified_signal(signal)
                stats["posted"] += 1
            except Exception as e:
                print(f"Failed to post signal {signal.signal_id}: {e}")
                stats["failed"] += 1
        
        return stats
    
    # ========================================================================
    # SIGNAL RETRACTION
    # ========================================================================
    
    async def retract_signal(
        self,
        signal_id: str,
        reason: str = "line_moved"
    ) -> bool:
        """
        Retract a posted signal (send correction message)
        
        Returns:
            True if retraction posted
        """
        signal = self.db[COLLECTIONS["signals"]].find_one(
            {"signal_id": signal_id}
        )
        
        if not signal or signal["state"] != SignalState.POSTED:
            return False
        
        # Get delivery records
        deliveries = []
        cursor = self.db[COLLECTIONS["telegram_delivery_log"]].find({
            "signal_id": signal_id,
            "status": "success"
        })
        
        for doc in list(cursor):
            deliveries.append(doc)
        
        # Post retraction message to each channel
        retraction_message = (
            f"⚠️ SIGNAL RETRACTION\n\n"
            f"Previous signal for {signal['away_team']} @ {signal['home_team']} "
            f"has been retracted.\n\n"
            f"Reason: {reason}\n\n"
            f"Line moved beyond acceptable threshold."
        )
        
        for delivery in deliveries:
            await self.telegram_bot.send_channel_message(
                channel_id=delivery["channel_id"],
                message=retraction_message
            )
        
        # Update signal state
        self.db[COLLECTIONS["signals"]].update_one(
            {"signal_id": signal_id},
            {
                "$set": {
                    "state": SignalState.INVALIDATED_LINE_MOVED,
                    "reason_code": f"retracted_{reason}"
                }
            }
        )
        
        return True


class SignalScheduler:
    """Automated signal distribution scheduler"""
    
    def __init__(
        self,
        db: Database,
        posting_service: SignalPostingService
    ):
        self.db = db
        self.posting_service = posting_service
    
    async def run_signal_pipeline(self) -> Dict[str, int]:
        """
        Run complete signal pipeline:
        1. Check for new simulations
        2. Qualify signals
        3. Check line movement invalidation
        4. Post qualified signals
        5. Invalidate signals for started games
        
        Returns:
            Statistics
        """
        from backend.services.signal_generation_service import SignalGenerationEngine
        
        signal_engine = SignalGenerationEngine(self.db)
        stats = {
            "qualified": 0,
            "lean": 0,
            "no_play": 0,
            "posted": 0,
            "invalidated": 0
        }
        
        # Step 1: Get pending simulations (assumes simulation engine)
        # TODO: Integrate with Monte Carlo engine
        
        # Step 2: Check line movement for existing signals
        pending_signals = []
        cursor = self.db[COLLECTIONS["signals"]].find({
            "state": {"$in": [SignalState.QUALIFIED, SignalState.LEAN]},
            "posted_at": None
        })
        
        for doc in list(cursor):
            pending_signals.append(Signal(**doc))
        
        for signal in pending_signals:
            invalidated = await signal_engine.check_line_movement_invalidation(
                signal.signal_id
            )
            if invalidated:
                stats["invalidated"] += 1
        
        # Step 3: Post qualified signals
        post_stats = await self.posting_service.post_daily_signals()
        stats["posted"] = post_stats["posted"]
        
        # Step 4: Invalidate signals for started games
        invalidated_count = await signal_engine.invalidate_signals_for_started_games()
        stats["invalidated"] += invalidated_count
        
        return stats

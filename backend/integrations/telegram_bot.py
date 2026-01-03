"""
Telegram Bot Integration

Automated signal distribution with scheduled posts.
Join request gating by subscription tier.
DM drip sequences for Sharp Pass users.
"""
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pyrogram import Client, filters  # type: ignore
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton  # type: ignore
from pyrogram.enums import ParseMode  # type: ignore

from ..core.signal_lifecycle import Signal, SignalStatus
from ..services.signal_manager import SignalManager
from ..db.database import Database


class TelegramBotManager:
    """Manages Telegram bot for BeatVegas signals"""
    
    def __init__(self, bot_token: str, db: Database):
        # Pyrogram Client
        api_id = os.getenv("TELEGRAM_API_ID", "0")
        api_hash = os.getenv("TELEGRAM_API_HASH", "")
        
        self.app = Client(
            "beatvegas_bot",
            bot_token=bot_token,
            api_id=int(api_id),
            api_hash=api_hash
        )
        self.db = db
        # Pass the underlying pymongo database to SignalManager
        self.signal_manager = SignalManager(db.db)
        
        # Channel IDs by tier
        self.channels = {
            "FREE": None,  # No free Telegram
            "STARTER": os.getenv("TELEGRAM_STARTER_CHANNEL_ID"),
            "PRO": os.getenv("TELEGRAM_PRO_CHANNEL_ID"),
            "ELITE": os.getenv("TELEGRAM_ELITE_CHANNEL_ID"),
            "SHARP_PASS": os.getenv("TELEGRAM_SHARP_PASS_CHANNEL_ID")
        }
        
        # Scheduled post times (ET)
        self.post_times = [
            ("10:00", "Morning Slate"),
            ("11:00", "MLB Early Games"),
            ("12:00", "Afternoon Update"),
            ("15:00", "Evening Slate"),
            ("18:00", "Prime Time"),
            ("19:00", "Night Games")
        ]
    
    
    async def post_signal_to_telegram(
        self,
        signal: Signal,
        tier: str
    ) -> Optional[str]:
        """
        Post signal to Telegram channel
        
        CRITICAL: Must match platform UI exactly
        
        Args:
            signal: Signal object
            tier: Subscription tier (STARTER, PRO, ELITE, SHARP_PASS)
        
        Returns: Telegram message ID
        """
        channel_id = self.channels.get(tier)
        if not channel_id:
            return None
        
        # Get latest simulation
        latest_sim = signal.simulation_runs[-1] if signal.simulation_runs else None
        if not latest_sim:
            return None
            
        # Format message
        message = self._format_signal_message(signal, latest_sim, tier)
        
        try:
            sent_message = await self.app.send_message(
                chat_id=int(channel_id),
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            # Log to database
            await self._log_telegram_post(
                signal_id=signal.signal_id,
                telegram_channel_id=channel_id,
                telegram_message_id=str(sent_message.id),
                message_text=message,
                tier=tier
            )
            
            return str(sent_message.id)
        
        except Exception as e:
            print(f"Error posting to Telegram: {e}")
            return None
    
    
    def _format_signal_message(
        self,
        signal: Signal,
        latest_sim,
        tier: str
    ) -> str:
        """
        Format signal message for Telegram
        
        MUST match platform UI exactly to prevent confusion
        """
        # Get game details
        game = latest_sim.result_data.get('game', {})
        
        # Header
        sport_emoji = {
            "MLB": "⚾",
            "NFL": "🏈",
            "NBA": "🏀",
            "NCAAB": "🏀",
            "NCAAF": "🏈",
            "NHL": "🏒"
        }
        
        emoji = sport_emoji.get(signal.sport, "🎯")
        
        # Edge badge
        edge_badge = ""
        if latest_sim.edge_state == "EDGE":
            edge_badge = "🔥 **EDGE**"
        elif latest_sim.edge_state == "LEAN":
            edge_badge = "⚡ **LEAN**"
        
        # Build message
        lines = [
            f"{emoji} **{signal.sport.upper()} SIGNAL** {edge_badge}",
            "",
            f"**Game:** {signal.team_a} vs {signal.team_b}",
            f"**Time:** {signal.game_time.strftime('%I:%M %p ET')}",
            "",
            f"**Sharp Side:** {latest_sim.sharp_side}",
            f"**Market:** {signal.entry_snapshot.market_type if signal.entry_snapshot else latest_sim.result_data.get('market_type', 'N/A')}",
        ]
        
        # Entry details
        if signal.entry_snapshot:
            if signal.entry_snapshot.entry_spread is not None:
                lines.append(f"**Entry:** {latest_sim.sharp_side} {signal.entry_snapshot.entry_spread:+.1f} ({signal.entry_snapshot.entry_odds:+d})")
            elif signal.entry_snapshot.entry_total is not None:
                lines.append(f"**Entry:** {latest_sim.sharp_side} {signal.entry_snapshot.entry_total} ({signal.entry_snapshot.entry_odds:+d})")
        
        lines.extend([
            "",
            f"**Edge:** {latest_sim.compressed_edge:.1f}%",
            f"**Volatility:** {latest_sim.volatility}",
            f"**Simulations:** {latest_sim.num_simulations:,}"
        ])
        
        # Tier-specific content
        if tier in ["ELITE", "SHARP_PASS"]:
            lines.extend([
                "",
                f"**Model:** {latest_sim.model_version}",
                f"**Distribution:** {latest_sim.distribution_flag}",
                f"**Points Side:** {latest_sim.points_side}"
            ])
        
        if tier == "SHARP_PASS":
            lines.extend([
                "",
                f"**Wave:** {latest_sim.wave}",
                f"**Sim ID:** `{latest_sim.sim_run_id}`"
            ])
        
        # Footer
        lines.extend([
            "",
            "📊 View full analysis on BeatVegas.app",
            "",
            "_Truth Mode verified. Edges are prices, not predictions._"
        ])
        
        return "\n".join(lines)
    
    
    async def scheduled_signal_batch_post(self):
        """
        Post batches of signals at scheduled times
        
        Runs every hour, checks for games starting in next window
        """
        current_time = datetime.now()
        
        # Get signals published in last hour
        signals = await self.signal_manager.get_signals_published_since(  # type: ignore
            since=current_time - timedelta(hours=1),
            status=SignalStatus.PUBLISHED
        )
        
        if not signals:
            return
        
        # Group by tier
        for tier in ["STARTER", "PRO", "ELITE", "SHARP_PASS"]:
            # Filter signals for this tier
            tier_signals = [
                s for s in signals
                if self._signal_accessible_to_tier(s, tier)
            ]
            
            if not tier_signals:
                continue
            
            # Format batch message
            batch_message = self._format_batch_message(tier_signals, tier)
            
            # Get channel ID for this tier
            channel_id = self.channels.get(tier)
            if channel_id:
                try:
                    await self.app.send_message(
                        chat_id=int(channel_id),
                        text=batch_message,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"Error posting batch to {tier}: {e}")
    
    
    def _format_batch_message(self, signals: List[Signal], tier: str) -> str:
        """Format batch of signals for Telegram"""
        time_slot = datetime.now().strftime("%I:%M %p ET")
        
        lines = [
            f"🎯 **{time_slot} SIGNAL UPDATE**",
            "",
            f"**{len(signals)} {'signal' if len(signals) == 1 else 'signals'} published**",
            ""
        ]
        
        for signal in signals:
            latest_sim = signal.simulation_runs[-1]
            edge_emoji = "🔥" if latest_sim.edge_state == "EDGE" else "⚡"
            
            lines.append(
                f"{edge_emoji} **{signal.team_a} vs {signal.team_b}** - "
                f"{latest_sim.sharp_side} ({latest_sim.compressed_edge:.1f}%)"
            )
        
        lines.extend([
            "",
            "📊 View details on BeatVegas.app"
        ])
        
        return "\n".join(lines)
    
    
    def _signal_accessible_to_tier(self, signal: Signal, tier: str) -> bool:
        """Check if signal is accessible to subscription tier"""
        tier_hierarchy = {
            "STARTER": 1,
            "PRO": 2,
            "ELITE": 3,
            "SHARP_PASS": 4
        }
        
        signal_tier = "STARTER"  # Default
        if signal.intent.value == "PARLAY_MODE":
            signal_tier = "PRO"
        elif signal.intent.value == "TRUTH_MODE":
            signal_tier = "SHARP_PASS"
        
        return tier_hierarchy.get(tier, 0) >= tier_hierarchy.get(signal_tier, 0)
    
    
    async def send_dm_sequence(
        self,
        user_telegram_id: str,
        sequence_type: str,
        user_data: Dict
    ):
        """
        Send DM drip sequence to user
        
        Sequences:
        - ONBOARDING: Welcome sequence
        - SHARP_PASS_APPROVED: Congratulations message
        - DAILY_SUMMARY: End of day results
        """
        messages = self._get_dm_sequence(sequence_type, user_data)
        
        for i, message_text in enumerate(messages):
            try:
                await self.app.send_message(
                    chat_id=int(user_telegram_id),
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Delay between messages
                if i < len(messages) - 1:
                    await asyncio.sleep(2)
            
            except Exception as e:
                print(f"Error sending DM to {user_telegram_id}: {e}")
                break
    
    
    def _get_dm_sequence(self, sequence_type: str, user_data: Dict) -> List[str]:
        """Get DM sequence messages"""
        if sequence_type == "ONBOARDING":
            return [
                f"👋 Welcome to BeatVegas, {user_data.get('display_name', 'there')}!",
                "",
                "You're now connected to our Telegram signal delivery.",
                "",
                "Signals will be posted throughout the day at:",
                "• 10 AM - Morning slate",
                "• 12 PM - Afternoon update",
                "• 3 PM - Evening slate",
                "• 6 PM - Prime time",
                "",
                "📊 View your dashboard: https://beatvegas.app/dashboard"
            ]
        
        elif sequence_type == "SHARP_PASS_APPROVED":
            return [
                "🔥 **SHARP PASS APPROVED!**",
                "",
                f"Congratulations, {user_data.get('display_name')}!",
                "",
                f"Your CLV edge: **{user_data.get('sharp_score', 0):.2f}%**",
                f"Verified bets: **{user_data.get('bet_count', 0)}**",
                "",
                "You now have access to:",
                "✅ Truth Mode (strict edge filters)",
                "✅ Wire Pro community",
                "✅ Priority signal delivery",
                "✅ Advanced analytics",
                "",
                "Welcome to the sharp side."
            ]
        
        elif sequence_type == "DAILY_SUMMARY":
            return [
                f"📊 **Daily Summary - {datetime.now().strftime('%b %d, %Y')}**",
                "",
                f"Signals today: **{user_data.get('signals_today', 0)}**",
                f"Win rate: **{user_data.get('win_rate', 0):.1f}%**",
                f"Average edge: **{user_data.get('avg_edge', 0):.1f}%**",
                "",
                "View full stats: https://beatvegas.app/analytics"
            ]
        
        return []
    
    
    async def handle_join_request(
        self,
        telegram_user_id: str,
        channel_id: str
    ):
        """
        Handle join request to gated channel
        
        Verify user subscription tier matches channel
        """
        # Get user from database
        user = self.db.users.find_one({"telegram_id": telegram_user_id})
        
        if not user:
            await self.app.send_message(
                chat_id=int(telegram_user_id),
                text="❌ No BeatVegas account found. Please connect your Telegram at https://beatvegas.app/settings"
            )
            return
        
        # Determine required tier for channel
        required_tier = None
        for tier, cid in self.channels.items():
            if cid == channel_id:
                required_tier = tier
                break
        
        # Check if user has access
        if required_tier == "SHARP_PASS":
            if user.get('sharp_pass_status') != "APPROVED":
                await self.app.send_message(
                    chat_id=int(telegram_user_id),
                    text="❌ Sharp Pass access required. Apply at https://beatvegas.app/sharp-pass"
                )
                return
        else:
            # Check subscription tier
            tier_hierarchy = {"FREE": 0, "STARTER": 1, "PRO": 2, "ELITE": 3}
            user_tier = user.get('subscription_tier', 'FREE')
            user_tier_level = tier_hierarchy.get(user_tier, 0)
            required_tier_level = tier_hierarchy.get(required_tier or "FREE", 0)
            
            if user_tier_level < required_tier_level:
                await self.app.send_message(
                    chat_id=int(telegram_user_id),
                    text=f"❌ {required_tier} subscription required. Upgrade at https://beatvegas.app/pricing"
                )
                return
        
        # Approve join request
        try:
            await self.app.approve_chat_join_request(
                chat_id=int(channel_id),
                user_id=int(telegram_user_id)
            )
            
            # Send welcome DM
            await self.send_dm_sequence(
                telegram_user_id,
                "ONBOARDING",
                user
            )
        
        except Exception as e:
            print(f"Error approving join request: {e}")
    
    
    async def _log_telegram_post(
        self,
        signal_id: str,
        telegram_channel_id: str,
        telegram_message_id: str,
        message_text: str,
        tier: str
    ):
        """Log Telegram post to MongoDB"""
        self.db.db.telegram_posts.insert_one({
            "signal_id": signal_id,
            "telegram_channel_id": telegram_channel_id,
            "telegram_message_id": telegram_message_id,
            "message_text": message_text,
            "tier": tier,
            "posted_at": datetime.now()
        })


# Scheduled job for batch posting
async def run_telegram_scheduler():
    """Run Telegram scheduler (call from cron/background task)"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        print("TELEGRAM_BOT_TOKEN not configured")
        return
        
    bot_manager = TelegramBotManager(
        bot_token=bot_token,
        db=Database()
    )
    
    # Start Pyrogram client
    await bot_manager.app.start()
    
    try:
        while True:
            try:
                await bot_manager.scheduled_signal_batch_post()
            except Exception as e:
                print(f"Telegram scheduler error: {e}")
            
            # Run every hour
            await asyncio.sleep(3600)
    finally:
        await bot_manager.app.stop()

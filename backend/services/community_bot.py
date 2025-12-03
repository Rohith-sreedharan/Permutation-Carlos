"""
Community Bot - Auto-generates engaging content for BeatVegas community
Keeps the community alive with game threads, alerts, AI commentary, and prompts
"""
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import random
from db.mongo import db
from utils.timezone import now_utc, now_est, format_est_datetime
from services.logger import log_stage


class CommunityBot:
    """
    Automatically generates community content to keep channels alive:
    - Daily game threads
    - Injury alerts
    - Line movement alerts
    - Parlay win celebrations
    - AI commentary
    - Daily engagement prompts
    """
    
    BOT_USER_ID = "system_bot"
    BOT_USERNAME = "BeatVegas AI"
    BOT_AVATAR = "🎯"
    
    DAILY_PROMPTS = [
        "What's your favorite pick tonight? 🏀",
        "Who's fading the public today? 👀",
        "Show me your best parlay for tonight 🎰",
        "Anyone riding a hot streak? Drop your record below 🔥",
        "What team are you NEVER betting on again? 😤",
        "First half or full game? What's your strategy? 🤔",
        "Who's got the sharp play of the day? 💎",
        "Unders or overs tonight? ⬇️⬆️",
        "Which underdog is going to surprise everyone? 🐕",
        "Road favorites or home dogs? Pick your poison 🎲"
    ]
    
    def __init__(self):
        pass
    
    def _create_message(
        self,
        channel: str,
        content: str,
        message_type: str = "bot_content",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a bot message document"""
        return {
            "message_id": f"bot_{now_utc().timestamp()}_{random.randint(1000, 9999)}",
            "channel_id": channel,
            "user_id": self.BOT_USER_ID,
            "username": self.BOT_USERNAME,
            "content": content,
            "ts": now_utc().isoformat(),
            "message_type": message_type,
            "metadata": metadata or {},
            "is_bot": True,
            "reactions": [],
            "reply_count": 0
        }
    
    def generate_daily_game_threads(self) -> List[Dict[str, Any]]:
        """
        Generate game threads for today's upcoming games
        Returns list of messages to insert
        """
        messages = []
        
        # Get today's games from events collection
        today_est = now_est().strftime("%Y-%m-%d")
        events = list(db["events"].find({"local_date_est": today_est}).limit(50))
        
        # Group by sport
        sport_map = {
            "basketball_nba": {"name": "NBA", "channel": "nba-live", "emoji": "🏀"},
            "americanfootball_nfl": {"name": "NFL", "channel": "nfl-live", "emoji": "🏈"},
            "basketball_ncaab": {"name": "NCAAB", "channel": "ncaab-live", "emoji": "🎓"},
            "americanfootball_ncaaf": {"name": "NCAAF", "channel": "ncaaf-live", "emoji": "🏟️"},
            "icehockey_nhl": {"name": "NHL", "channel": "nhl-live", "emoji": "🏒"},
            "baseball_mlb": {"name": "MLB", "channel": "mlb-live", "emoji": "⚾"}
        }
        
        sport_games = {}
        for event in events:
            sport_key = event.get("sport_key", "")
            if sport_key in sport_map:
                if sport_key not in sport_games:
                    sport_games[sport_key] = []
                sport_games[sport_key].append(event)
        
        # Create game thread for each sport
        for sport_key, games in sport_games.items():
            sport_info = sport_map[sport_key]
            game_count = len(games)
            
            # Create summary message
            content = f"{sport_info['emoji']} **{sport_info['name']} Game Thread - {now_est().strftime('%B %d, %Y')}**\n\n"
            content += f"{game_count} games on the board today!\n\n"
            
            # Add top 3-5 games
            for i, game in enumerate(games[:5]):
                away = game.get("away_team", "Away")
                home = game.get("home_team", "Home")
                commence = game.get("commence_time", "")
                
                # Format time
                try:
                    from utils.timezone import parse_iso_to_est
                    dt_est = parse_iso_to_est(commence)
                    time_str = dt_est.strftime("%I:%M %p ET") if dt_est else "TBD"
                except:
                    time_str = "TBD"
                
                content += f"**{away} @ {home}** - {time_str}\n"
            
            if game_count > 5:
                content += f"\n...and {game_count - 5} more games\n"
            
            content += "\n💬 Drop your picks below!"
            
            msg = self._create_message(
                channel=sport_info["channel"],
                content=content,
                message_type="game_thread",
                metadata={"sport": sport_key, "game_count": game_count, "date": today_est}
            )
            messages.append(msg)
        
        return messages
    
    def generate_injury_alert(self, player: str, team: str, status: str, sport: str = "NBA") -> Dict[str, Any]:
        """Generate injury alert message"""
        emoji_map = {
            "Out": "🚨",
            "Questionable": "⚠️",
            "Doubtful": "🤕",
            "Probable": "ℹ️"
        }
        emoji = emoji_map.get(status, "⚠️")
        
        content = f"{emoji} **INJURY UPDATE**\n\n"
        content += f"**{player}** ({team}) - **{status}**\n\n"
        content += "Lines may move. Check your bets! 📊"
        
        channel_map = {
            "NBA": "nba-live",
            "NFL": "nfl-live",
            "NCAAB": "ncaab-live",
            "NCAAF": "ncaaf-live",
            "NHL": "nhl-live"
        }
        
        return self._create_message(
            channel=channel_map.get(sport, "general"),
            content=content,
            message_type="injury_alert",
            metadata={"player": player, "team": team, "status": status, "sport": sport}
        )
    
    def generate_line_movement_alert(
        self,
        game: str,
        market: str,
        old_line: float,
        new_line: float,
        movement_pct: float
    ) -> Dict[str, Any]:
        """Generate line movement alert"""
        direction = "📈" if new_line > old_line else "📉"
        
        content = f"{direction} **LINE MOVEMENT ALERT**\n\n"
        content += f"**{game}**\n"
        content += f"{market}: {old_line} → **{new_line}**\n"
        content += f"Movement: {abs(movement_pct):.1f}%\n\n"
        
        if abs(movement_pct) > 5:
            content += "⚡ **SHARP MOVE** - Big money on this line!"
        else:
            content += "Public or injury news driving this move? 👀"
        
        return self._create_message(
            channel="general",
            content=content,
            message_type="line_movement",
            metadata={
                "game": game,
                "market": market,
                "old_line": old_line,
                "new_line": new_line,
                "movement_pct": movement_pct
            }
        )
    
    def generate_parlay_win_celebration(self, user: str, legs: int, odds: str, profit: float) -> Dict[str, Any]:
        """Celebrate user's parlay win"""
        emojis = ["🎰", "💰", "🔥", "💎", "🚀"]
        emoji = random.choice(emojis)
        
        content = f"{emoji * 3} **PARLAY HIT!** {emoji * 3}\n\n"
        content += f"Congrats **{user}**!\n"
        content += f"✅ {legs}-leg parlay\n"
        content += f"💵 {odds} odds\n"
        content += f"🏆 **+${profit:.2f}** profit\n\n"
        content += "Drop yours in the thread! 👇"
        
        return self._create_message(
            channel="winning-tickets",
            content=content,
            message_type="parlay_win",
            metadata={"user": user, "legs": legs, "odds": odds, "profit": profit}
        )
    
    def generate_ai_commentary(self, insight: str, confidence: float, game: str) -> Dict[str, Any]:
        """Generate AI analysis commentary"""
        confidence_emoji = "🔥" if confidence > 70 else "💡" if confidence > 55 else "🤔"
        
        content = f"{confidence_emoji} **AI INSIGHT**\n\n"
        content += f"**{game}**\n\n"
        content += f"{insight}\n\n"
        content += f"Confidence: **{confidence:.1f}%**\n"
        content += f"_Powered by Monte Carlo simulation (10K+ iterations)_"
        
        return self._create_message(
            channel="general",
            content=content,
            message_type="ai_commentary",
            metadata={"insight": insight, "confidence": confidence, "game": game}
        )
    
    def generate_daily_prompt(self) -> Dict[str, Any]:
        """Generate daily engagement prompt"""
        prompt = random.choice(self.DAILY_PROMPTS)
        
        content = f"💬 **Daily Question**\n\n{prompt}"
        
        return self._create_message(
            channel="general",
            content=content,
            message_type="daily_prompt"
        )
    
    def generate_monte_carlo_alert(
        self,
        game: str,
        edge_type: str,
        pick: str,
        line: str,
        win_prob: float,
        ev: float,
        channel: str = "general"
    ) -> Dict[str, Any]:
        """Generate Monte Carlo simulation alert"""
        content = f"🎯 **BEATVEGAS EDGE DETECTED**\n\n"
        content += f"**{game}**\n"
        content += f"Pick: **{pick} {line}**\n\n"
        content += f"📊 Win Probability: **{win_prob:.1f}%**\n"
        content += f"💰 Expected Value: **+{ev:.2f}%**\n\n"
        content += f"_{edge_type}_\n"
        content += f"_10,000 simulations · Updated {now_est().strftime('%I:%M %p ET')}_"
        
        return self._create_message(
            channel=channel,
            content=content,
            message_type="monte_carlo_alert",
            metadata={
                "game": game,
                "edge_type": edge_type,
                "pick": pick,
                "line": line,
                "win_prob": win_prob,
                "ev": ev
            }
        )
    
    def generate_volatility_alert(
        self,
        game: str,
        market: str,
        old_value: float,
        new_value: float,
        time_window: str
    ) -> Dict[str, Any]:
        """Generate volatility/rapid line movement alert"""
        change = abs(new_value - old_value)
        direction = "jumped" if new_value > old_value else "dropped"
        
        content = f"⚡ **VOLATILITY ALERT**\n\n"
        content += f"**{game}**\n"
        content += f"{market} {direction} from **{old_value}** → **{new_value}**\n"
        content += f"Time window: {time_window}\n\n"
        content += "Sharp action or breaking news? 🔍"
        
        return self._create_message(
            channel="general",
            content=content,
            message_type="volatility_alert",
            metadata={
                "game": game,
                "market": market,
                "old_value": old_value,
                "new_value": new_value,
                "time_window": time_window,
                "change": change
            }
        )
    
    def generate_top_public_pick(
        self,
        pick: str,
        game: str,
        percentage: float,
        total_users: int
    ) -> Dict[str, Any]:
        """Generate top public pick message"""
        content = f"📊 **TOP PUBLIC PICK**\n\n"
        content += f"**{game}**\n"
        content += f"Pick: **{pick}**\n\n"
        content += f"👥 {percentage:.1f}% of BeatVegas users ({total_users} users)\n\n"
        content += "Fade or follow? 🤔"
        
        return self._create_message(
            channel="general",
            content=content,
            message_type="public_pick",
            metadata={
                "pick": pick,
                "game": game,
                "percentage": percentage,
                "total_users": total_users
            }
        )
    
    def post_message(self, message: Dict[str, Any]) -> bool:
        """Insert message into community_messages collection"""
        try:
            db["community_messages"].insert_one(message)
            log_stage(
                "community_bot",
                "success",
                input_payload={"message_type": message.get("message_type")},
                output_payload={"channel": message.get("channel_id")}
            )
            return True
        except Exception as e:
            log_stage(
                "community_bot",
                "error",
                input_payload={"message_type": message.get("message_type")},
                output_payload={"error": str(e)},
                level="ERROR"
            )
            return False
    
    def post_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Bulk insert messages"""
        if not messages:
            return 0
        
        try:
            result = db["community_messages"].insert_many(messages)
            count = len(result.inserted_ids)
            log_stage(
                "community_bot",
                "success",
                input_payload={"count": count},
                output_payload={"inserted": count}
            )
            return count
        except Exception as e:
            log_stage(
                "community_bot",
                "error",
                input_payload={"count": len(messages)},
                output_payload={"error": str(e)},
                level="ERROR"
            )
            return 0


# Global bot instance
community_bot = CommunityBot()

"""
Market Movement Agent
Tracks line movements and identifies sharp money
"""
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class MarketAgent:
    """
    Market Movement Agent
    - Tracks line movements in real-time
    - Identifies sharp money (reverse line movement)
    - Detects steam moves (sudden line shifts)
    - Calculates closing line value (CLV)
    """
    
    def __init__(self, event_bus, db_client):
        self.bus = event_bus
        self.db = db_client
        self.line_history = {}  # Cache line movements
        
    async def start(self):
        """Start agent and subscribe to topics"""
        await self.bus.subscribe("market.movements", self.handle_line_movement)
        await self.bus.subscribe("user.activity", self.handle_user_pick)
        logger.info("📈 Market Agent started")
        
        # Start background task to monitor lines
        asyncio.create_task(self._monitor_lines())
        
    async def _monitor_lines(self):
        """Background task to poll for line movements"""
        while True:
            try:
                await self._check_all_lines()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Line monitoring error: {e}")
                await asyncio.sleep(60)
                
    async def _check_all_lines(self):
        """Check all active events for line movements"""
        try:
            db = self.db["beatvegas_db"]
            
            # Get all active events (games in next 48 hours)
            cutoff = datetime.utcnow() + timedelta(hours=48)
            events = list(db.events.find({
                "commence_time": {"$lte": cutoff},
                "completed": {"$ne": True}
            }))
            
            for event in events:
                await self._analyze_line_movement(event)
                
        except Exception as e:
            logger.error(f"Error checking lines: {e}")
            
    async def _analyze_line_movement(self, event: Dict[str, Any]):
        """Analyze line movement for single event"""
        event_id = str(event.get("_id"))
        current_lines = event.get("bookmakers", [])
        
        # Get historical lines
        previous_lines = self.line_history.get(event_id, {})
        
        for bookmaker in current_lines:
            book_name = bookmaker.get("key")
            markets = bookmaker.get("markets", [])
            
            for market in markets:
                market_type = market.get("key")  # h2h, spreads, totals
                
                for outcome in market.get("outcomes", []):
                    team = outcome.get("name")
                    current_price = outcome.get("price")
                    current_point = outcome.get("point")
                    
                    # Check for movement
                    key = f"{book_name}:{market_type}:{team}"
                    previous = previous_lines.get(key, {})
                    previous_price = previous.get("price")
                    previous_point = previous.get("point")
                    
                    if previous_price and current_price != previous_price:
                        await self._detect_movement(
                            event_id,
                            event,
                            market_type,
                            team,
                            previous_price,
                            current_price,
                            previous_point,
                            current_point
                        )
                        
                    # Update cache
                    if event_id not in self.line_history:
                        self.line_history[event_id] = {}
                    self.line_history[event_id][key] = {
                        "price": current_price,
                        "point": current_point,
                        "timestamp": datetime.utcnow()
                    }
                    
    async def _detect_movement(
        self,
        event_id: str,
        event: Dict[str, Any],
        market_type: str,
        team: str,
        old_price: float,
        new_price: float,
        old_point: Optional[float],
        new_point: Optional[float]
    ):
        """Detect type of line movement and publish alert"""
        from core.websocket_manager import manager
        
        # Calculate movement direction
        if market_type == "h2h":
            # Moneyline - lower odds = favorite getting stronger
            movement = "sharper" if new_price < old_price else "weaker"
        else:
            # Spread/Total - check point movement
            if new_point and old_point:
                if market_type == "spreads":
                    movement = "sharper" if new_point < old_point else "weaker"
                else:  # totals
                    movement = "higher" if new_point > old_point else "lower"
            else:
                movement = "adjusted"
                
        # Detect sharp money (reverse line movement)
        # Example: 70% of bets on Team A, but line moves toward Team B
        is_sharp_money = await self._detect_sharp_money(event_id, team, movement)
        
        # Detect steam move (sudden sharp movement)
        movement_size = abs(new_price - old_price) if market_type == "h2h" else abs(new_point - old_point) if new_point and old_point else 0
        is_steam = movement_size > self._get_steam_threshold(market_type)
        
        # Broadcast via WebSocket to all subscribers
        if is_sharp_money or is_steam or movement_size >= 1.5:
            await manager.broadcast_to_channel("events", {
                "type": "RECALCULATION",
                "payload": {
                    "event_id": event_id,
                    "event_name": f"{event.get('away_team')} @ {event.get('home_team')}",
                    "market_type": market_type,
                    "team": team,
                    "old_line": old_point or old_price,
                    "new_line": new_point or new_price,
                    "movement_size": movement_size,
                    "sharp_money": is_sharp_money,
                    "steam_move": is_steam,
                    "message": f"{'🚨 SHARP MONEY: ' if is_sharp_money else '📊 '}Line moved {movement_size:.1f} on {team}"
                }
            })
        
        alert = {
            "type": "line_movement",
            "event_id": event_id,
            "event_name": f"{event.get('home_team')} vs {event.get('away_team')}",
            "market_type": market_type,
            "team": team,
            "old_line": {"price": old_price, "point": old_point},
            "new_line": {"price": new_price, "point": new_point},
            "movement": movement,
            "is_sharp_money": is_sharp_money,
            "is_steam": is_steam,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("market.movements", alert)
        
        if is_sharp_money or is_steam:
            logger.info(f"🚨 {'SHARP MONEY' if is_sharp_money else 'STEAM MOVE'} detected: {team} {market_type}")
            
    async def _detect_sharp_money(self, event_id: str, team: str, movement: str) -> bool:
        """
        Detect reverse line movement (sharp money)
        Sharp money = Line moves AGAINST public betting percentage
        """
        try:
            # In production, would fetch betting percentages from sportsbook API
            # For now, use heuristic: if line moves without obvious reason
            
            # Check if line is moving contrary to expected direction
            # This would integrate with public betting data in production
            return False  # Placeholder
            
        except Exception as e:
            logger.error(f"Error detecting sharp money: {e}")
            return False
            
    def _get_steam_threshold(self, market_type: str) -> float:
        """Get movement threshold to qualify as steam"""
        if market_type == "h2h":
            return 15  # 15 cents in American odds
        elif market_type == "spreads":
            return 1.0  # 1 point
        elif market_type == "totals":
            return 1.5  # 1.5 points
        return 999
        
    async def handle_line_movement(self, message: Dict[str, Any]):
        """Handle line movement alerts from external sources"""
        # This would be triggered by webhooks from odds API
        pass
        
    async def handle_user_pick(self, message: Dict[str, Any]):
        """
        Track user picks and calculate CLV when game closes
        CLV = Closing Line Value = Price you got vs. closing price
        """
        try:
            data = message.get("data", {})
            if data.get("activity_type") != "pick_made":
                return
                
            user_id = data.get("user_id")
            event_id = data.get("event_id")
            pick_price = data.get("odds")
            team = data.get("team")
            market_type = data.get("market_type")
            
            # Store pick for CLV calculation later
            await self._store_pick_for_clv(user_id, event_id, team, market_type, pick_price)
            
        except Exception as e:
            logger.error(f"Error handling user pick: {e}")
            
    async def _store_pick_for_clv(
        self,
        user_id: str,
        event_id: str,
        team: str,
        market_type: str,
        pick_price: float
    ):
        """Store pick to calculate CLV when game closes"""
        try:
            db = self.db["beatvegas_db"]
            
            clv_record = {
                "user_id": user_id,
                "event_id": event_id,
                "team": team,
                "market_type": market_type,
                "pick_price": pick_price,
                "pick_timestamp": datetime.utcnow(),
                "closing_price": None,
                "clv_calculated": False
            }
            
            db.clv_tracking.insert_one(clv_record)
            
        except Exception as e:
            logger.error(f"Error storing CLV record: {e}")
            
    async def calculate_closing_line_value(self, event_id: str):
        """
        Calculate CLV for all picks on an event once it closes
        Called when game is about to start
        """
        try:
            db = self.db["beatvegas_db"]
            
            # Get event's closing lines
            event = db.events.find_one({"_id": event_id})
            if not event:
                return
                
            # Get all pending CLV calculations for this event
            pending_clvs = list(db.clv_tracking.find({
                "event_id": event_id,
                "clv_calculated": False
            }))
            
            for record in pending_clvs:
                team = record.get("team")
                market_type = record.get("market_type")
                pick_price = record.get("pick_price")
                
                # Find closing price
                closing_price = await self._get_closing_price(event, team, market_type)
                
                if closing_price:
                    # Calculate CLV
                    clv = self._calculate_clv(pick_price, closing_price, market_type)
                    
                    # Update record
                    db.clv_tracking.update_one(
                        {"_id": record["_id"]},
                        {"$set": {
                            "closing_price": closing_price,
                            "clv": clv,
                            "clv_calculated": True,
                            "calculated_at": datetime.utcnow()
                        }}
                    )
                    
                    # Publish CLV result
                    await self.bus.publish("market.movements", {
                        "type": "clv_calculated",
                        "user_id": record.get("user_id"),
                        "event_id": event_id,
                        "clv": clv,
                        "pick_price": pick_price,
                        "closing_price": closing_price,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error calculating CLV: {e}")
            
    async def _get_closing_price(self, event: Dict[str, Any], team: str, market_type: str) -> Optional[float]:
        """Extract closing price from event data"""
        bookmakers = event.get("bookmakers", [])
        
        # Use first available bookmaker (in production, use consensus closing line)
        if not bookmakers:
            return None
            
        for market in bookmakers[0].get("markets", []):
            if market.get("key") == market_type:
                for outcome in market.get("outcomes", []):
                    if outcome.get("name") == team:
                        return outcome.get("price")
                        
        return None
        
    def _calculate_clv(self, pick_price: float, closing_price: float, market_type: str) -> float:
        """
        Calculate Closing Line Value
        Positive CLV = You got better odds than closing
        Negative CLV = You got worse odds than closing
        """
        if market_type == "h2h":
            # American odds - more negative = better for favorite
            # More positive = better for underdog
            if pick_price < 0 and closing_price < 0:
                # Both favorites - more negative is better
                return closing_price - pick_price  # e.g., -110 vs -120 = +10 CLV
            elif pick_price > 0 and closing_price > 0:
                # Both underdogs - more positive is better
                return pick_price - closing_price  # e.g., +150 vs +140 = +10 CLV
            else:
                # Crossed zero - complex calculation
                return 0
        else:
            # Spread/Total - simple difference
            return pick_price - closing_price

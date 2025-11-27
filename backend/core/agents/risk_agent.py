"""
Risk Management Agent
Provides bankroll protection, unit sizing, and tilt detection
"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import math
import logging

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    Risk Management Agent
    - Monitors user betting activity
    - Provides volatility-adjusted unit sizing
    - Detects tilt behavior (betting 3x normal units)
    - Implements Kelly Criterion for optimal bet sizing
    - Alerts on high-risk parlays
    """
    
    def __init__(self, event_bus, db_client):
        self.bus = event_bus
        self.db = db_client
        self.user_profiles = {}  # Cache user risk profiles
        
    async def start(self):
        """Start agent and subscribe to topics"""
        await self.bus.subscribe("risk.alerts", self.handle_risk_check)
        await self.bus.subscribe("user.activity", self.handle_user_activity)
        await self.bus.subscribe("parlay.responses", self.handle_parlay_response)
        logger.info("🛡️ Risk Agent started")
        
    async def handle_risk_check(self, message: Dict[str, Any]):
        """
        Handle risk assessment requests
        Message types:
        - bet_size_check: Validate proposed bet size
        - parlay_risk_check: Assess parlay risk
        - bankroll_alert: Check bankroll health
        """
        try:
            data = message.get("data", {})
            check_type = data.get("type")
            user_id = data.get("user_id")
            
            if check_type == "bet_size_check":
                await self._check_bet_size(user_id, data)
            elif check_type == "parlay_risk_check":
                await self._check_parlay_risk(user_id, data)
            elif check_type == "bankroll_alert":
                await self._check_bankroll_health(user_id)
                
        except Exception as e:
            logger.error(f"❌ Risk check failed: {e}")
            
    async def handle_user_activity(self, message: Dict[str, Any]):
        """
        Monitor user betting activity for patterns
        Detects:
        - Increased bet frequency (tilt)
        - Higher than normal unit sizes
        - Chasing losses
        """
        try:
            data = message.get("data", {})
            user_id = data.get("user_id")
            activity_type = data.get("activity_type")
            
            if activity_type == "bet_placed":
                await self._analyze_bet_behavior(user_id, data)
            elif activity_type == "loss":
                await self._check_tilt_risk(user_id, data)
                
        except Exception as e:
            logger.error(f"❌ User activity monitoring failed: {e}")
            
    async def handle_parlay_response(self, message: Dict[str, Any]):
        """Provide risk guidance on parlay analysis"""
        try:
            data = message.get("data", {})
            if data.get("type") != "parlay_analysis":
                return
                
            user_id = data.get("user_id")
            risk_score = data.get("risk_score")
            ev = data.get("expected_value", 0)
            
            # Generate risk guidance
            guidance = await self._generate_risk_guidance(user_id, data)
            
            # Publish risk response
            await self.bus.publish("risk.responses", {
                "type": "parlay_risk_guidance",
                "user_id": user_id,
                "guidance": guidance,
                "timestamp": datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Parlay risk response failed: {e}")
            
    async def _check_bet_size(self, user_id: str, data: Dict[str, Any]):
        """
        Validate proposed bet size against user's profile
        Alerts if bet is abnormally large
        """
        proposed_amount = data.get("amount", 0)
        bet_type = data.get("bet_type", "single")
        
        # Get user's betting history
        profile = await self._get_user_profile(user_id)
        avg_bet = profile.get("avg_bet_size", 100)
        bankroll = profile.get("bankroll", 1000)
        
        # Calculate risk metrics
        bet_percentage = (proposed_amount / bankroll) * 100 if bankroll > 0 else 0
        size_multiplier = proposed_amount / avg_bet if avg_bet > 0 else 1
        
        alert_level = "SAFE"
        alerts = []
        
        # Tilt detection: Betting 3x+ normal size
        if size_multiplier >= 3.0:
            alert_level = "DANGER"
            alerts.append(f"⚠️ Bet is {size_multiplier:.1f}x your average - potential tilt behavior")
            
        # Bankroll % check
        if bet_percentage > 10:
            alert_level = "DANGER"
            alerts.append(f"⚠️ Betting {bet_percentage:.1f}% of bankroll - recommended max is 5%")
        elif bet_percentage > 5:
            alert_level = "WARNING"
            alerts.append(f"⚠️ Betting {bet_percentage:.1f}% of bankroll - approaching limit")
            
        # Kelly Criterion recommendation
        kelly_size = await self._calculate_kelly_size(user_id, data)
        if proposed_amount > kelly_size * 1.5:
            alerts.append(f"💡 Kelly Criterion suggests ${kelly_size:.2f} (you're betting ${proposed_amount:.2f})")
            
        response = {
            "type": "bet_size_assessment",
            "user_id": user_id,
            "alert_level": alert_level,
            "alerts": alerts,
            "recommended_size": kelly_size,
            "bankroll_percentage": round(bet_percentage, 2),
            "size_multiplier": round(size_multiplier, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("risk.responses", response)
        
        if alert_level == "DANGER":
            logger.warning(f"🚨 RISK ALERT for user {user_id}: {alerts}")
            
    async def _check_parlay_risk(self, user_id: str, data: Dict[str, Any]):
        """Assess risk of parlay construction"""
        parlay_data = data.get("parlay_data", {})
        combined_prob = parlay_data.get("combined_probability", 0) / 100
        num_legs = len(parlay_data.get("legs", []))
        correlation = parlay_data.get("correlation_score", 0)
        
        alerts = []
        risk_level = "MEDIUM"
        
        # Very low probability
        if combined_prob < 0.10:
            risk_level = "EXTREME"
            alerts.append("⚠️ Less than 10% chance of hitting - lottery ticket odds")
            
        # Too many legs
        if num_legs >= 5:
            risk_level = "EXTREME"
            alerts.append(f"⚠️ {num_legs}-leg parlay has exponentially lower odds")
            
        # High correlation risk
        if correlation > 0.8:
            alerts.append("⚠️ High correlation between legs reduces diversification")
            
        # Positive EV but low probability
        ev = parlay_data.get("expected_value", 0)
        if ev > 5 and combined_prob < 0.20:
            alerts.append("💡 High EV but low hit rate - variance will be extreme")
            
        response = {
            "type": "parlay_risk_assessment",
            "user_id": user_id,
            "risk_level": risk_level,
            "alerts": alerts,
            "recommended_action": self._get_parlay_recommendation(risk_level, ev),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("risk.responses", response)
        
    async def _check_bankroll_health(self, user_id: str):
        """Check overall bankroll status and trends"""
        profile = await self._get_user_profile(user_id)
        
        bankroll = profile.get("bankroll", 1000)
        starting_bankroll = profile.get("starting_bankroll", 1000)
        recent_loss_streak = profile.get("recent_loss_streak", 0)
        
        alerts = []
        health_status = "HEALTHY"
        
        # Bankroll drawdown
        drawdown = ((starting_bankroll - bankroll) / starting_bankroll * 100) if starting_bankroll > 0 else 0
        
        if drawdown > 50:
            health_status = "CRITICAL"
            alerts.append(f"🚨 Bankroll down {drawdown:.1f}% - consider taking a break")
        elif drawdown > 30:
            health_status = "WARNING"
            alerts.append(f"⚠️ Bankroll down {drawdown:.1f}% - reduce unit sizes")
        elif drawdown > 20:
            alerts.append(f"💡 Bankroll down {drawdown:.1f}% - stay disciplined")
            
        # Loss streak
        if recent_loss_streak >= 5:
            health_status = "WARNING"
            alerts.append(f"⚠️ {recent_loss_streak} straight losses - avoid emotional betting")
            
        response = {
            "type": "bankroll_health_check",
            "user_id": user_id,
            "health_status": health_status,
            "bankroll": bankroll,
            "drawdown_percentage": round(drawdown, 2),
            "alerts": alerts,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.bus.publish("risk.responses", response)
        
    async def _analyze_bet_behavior(self, user_id: str, data: Dict[str, Any]):
        """Analyze betting patterns for anomalies"""
        # Get recent bet history
        recent_bets = await self._get_recent_bets(user_id, hours=24)
        
        if len(recent_bets) >= 10:
            # High frequency - possible tilt
            await self.bus.publish("risk.responses", {
                "type": "tilt_warning",
                "user_id": user_id,
                "alert": "⚠️ 10+ bets in 24 hours - take a break to avoid emotional decisions",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    async def _check_tilt_risk(self, user_id: str, data: Dict[str, Any]):
        """Check for tilt behavior after losses"""
        profile = await self._get_user_profile(user_id)
        recent_loss_streak = profile.get("recent_loss_streak", 0)
        
        if recent_loss_streak >= 3:
            await self.bus.publish("risk.responses", {
                "type": "tilt_alert",
                "user_id": user_id,
                "alert": f"🛑 {recent_loss_streak} straight losses - emotional betting risk is high",
                "recommendation": "Take 24 hours off before next bet",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    async def _calculate_kelly_size(self, user_id: str, data: Dict[str, Any]) -> float:
        """
        Calculate optimal bet size using Kelly Criterion
        Formula: Kelly % = (bp - q) / b
        Where:
        - b = decimal odds - 1
        - p = probability of winning
        - q = probability of losing (1 - p)
        """
        profile = await self._get_user_profile(user_id)
        bankroll = profile.get("bankroll", 1000)
        
        # Get win probability (from simulation or historical)
        win_prob = data.get("win_probability", 0.52)  # Default slight edge
        odds = data.get("odds", -110)
        
        # Convert American odds to decimal
        if odds > 0:
            decimal_odds = (odds / 100) + 1
        else:
            decimal_odds = (100 / abs(odds)) + 1
            
        b = decimal_odds - 1
        p = win_prob
        q = 1 - p
        
        # Kelly %
        kelly_pct = (b * p - q) / b
        
        # Never bet more than 5% (fractional Kelly)
        kelly_pct = max(0, min(kelly_pct, 0.05))
        
        return bankroll * kelly_pct
        
    async def _generate_risk_guidance(self, user_id: str, parlay_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive risk guidance for parlay"""
        profile = await self._get_user_profile(user_id)
        bankroll = profile.get("bankroll", 1000)
        
        combined_prob = parlay_data.get("combined_probability", 0) / 100
        parlay_odds = parlay_data.get("parlay_odds", 1)
        ev = parlay_data.get("expected_value", 0) / 100
        
        # Suggested unit size (conservative)
        suggested_units = 0.5 if combined_prob > 0.3 else 0.25
        suggested_amount = (bankroll * 0.01) * suggested_units  # 1% = 1 unit
        
        return {
            "suggested_bet_amount": round(suggested_amount, 2),
            "suggested_units": suggested_units,
            "max_recommended_amount": round(bankroll * 0.03, 2),  # Never more than 3%
            "breakeven_needed": round(1 / parlay_odds, 4),
            "hits_needed_for_profit": math.ceil(1 / ev) if ev > 0 else None,
            "variance_warning": "High variance - prepare for long losing streaks" if combined_prob < 0.2 else None
        }
        
    def _get_parlay_recommendation(self, risk_level: str, ev: float) -> str:
        """Get recommendation based on risk and EV"""
        if risk_level == "EXTREME":
            return "AVOID - Risk too high for expected return"
        elif risk_level == "HIGH" and ev < 5:
            return "PASS - Risk outweighs potential reward"
        elif ev > 10:
            return "CONSIDER - Strong EV but manage position size"
        else:
            return "PROCEED WITH CAUTION - Use small unit size"
            
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get or create user risk profile"""
        if user_id in self.user_profiles:
            return self.user_profiles[user_id]
            
        # Fetch from database
        try:
            db = self.db["beatvegas_db"]
            user = db.subscribers.find_one({"_id": user_id})
            
            if user:
                profile = {
                    "bankroll": user.get("wallet", {}).get("balance", 1000),
                    "starting_bankroll": user.get("starting_bankroll", 1000),
                    "avg_bet_size": user.get("avg_bet_size", 100),
                    "recent_loss_streak": user.get("recent_loss_streak", 0),
                }
            else:
                # Default profile
                profile = {
                    "bankroll": 1000,
                    "starting_bankroll": 1000,
                    "avg_bet_size": 100,
                    "recent_loss_streak": 0,
                }
                
            self.user_profiles[user_id] = profile
            return profile
            
        except Exception as e:
            logger.error(f"Error fetching user profile: {e}")
            return {
                "bankroll": 1000,
                "starting_bankroll": 1000,
                "avg_bet_size": 100,
                "recent_loss_streak": 0,
            }
            
    async def _get_recent_bets(self, user_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get user's recent bets"""
        try:
            db = self.db["beatvegas_db"]
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            bets = list(db.ai_picks.find({
                "user_id": user_id,
                "timestamp": {"$gte": cutoff}
            }).sort("timestamp", -1))
            
            return bets
        except Exception as e:
            logger.error(f"Error fetching recent bets: {e}")
            return []

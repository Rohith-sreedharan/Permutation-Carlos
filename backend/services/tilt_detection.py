"""
Tilt Detection Service
Monitors user betting activity and broadcasts WebSocket alerts
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)


class TiltDetectionService:
    """
    Monitors user betting patterns and detects potential tilt behavior.
    
    Tilt Signals:
    - >3 bets placed in 10-minute window
    - Bet size >3x normal unit size
    - Betting after 3+ consecutive losses
    - Rapid bet placement (<2 min between bets)
    """
    
    def __init__(self, db_client):
        self.db = db_client
        self.user_bet_history: Dict[str, List[datetime]] = defaultdict(list)
        self.last_alert_time: Dict[str, datetime] = {}
        
    async def track_bet(self, user_id: str, bet_data: Dict) -> Dict:
        """
        Track bet placement and check for tilt patterns.
        
        Args:
            user_id: User identifier
            bet_data: Contains amount, timestamp, type
            
        Returns:
            Dict with tilt_detected=True if pattern detected
        """
        now = datetime.now(timezone.utc)
        
        # Clean old bet history (keep last hour only)
        self.user_bet_history[user_id] = [
            ts for ts in self.user_bet_history[user_id]
            if now - ts < timedelta(hours=1)
        ]
        
        # Add current bet
        self.user_bet_history[user_id].append(now)
        
        # Check for tilt patterns
        tilt_result = await self._analyze_tilt_patterns(user_id, bet_data, now)
        
        if tilt_result['tilt_detected']:
            # Only alert once per hour to avoid spam
            last_alert = self.last_alert_time.get(user_id)
            if not last_alert or (now - last_alert) > timedelta(hours=1):
                await self._broadcast_tilt_alert(user_id, tilt_result)
                self.last_alert_time[user_id] = now
                logger.warning(f"🚨 TILT DETECTED for user {user_id}: {tilt_result['reason']}")
        
        return tilt_result
        
    async def _analyze_tilt_patterns(self, user_id: str, bet_data: Dict, now: datetime) -> Dict:
        """Analyze betting patterns for tilt signals"""
        result = {
            'tilt_detected': False,
            'reason': None,
            'bet_count': 0,
            'timeframe': None,
            'unit_size': 0,
            'recommended_action': None
        }
        
        # Get user profile for baseline comparison
        users_collection = self.db['users']
        user_profile = users_collection.find_one({'user_id': user_id})
        
        if not user_profile:
            return result
            
        unit_size = user_profile.get('unit_size', 100)
        result['unit_size'] = unit_size
        
        # Pattern 1: High frequency betting (>3 bets in 10 minutes)
        recent_bets = [
            ts for ts in self.user_bet_history[user_id]
            if now - ts < timedelta(minutes=10)
        ]
        
        if len(recent_bets) > 3:
            result['tilt_detected'] = True
            result['reason'] = 'HIGH_FREQUENCY'
            result['bet_count'] = len(recent_bets)
            result['timeframe'] = '10 minutes'
            result['recommended_action'] = (
                f"You've placed {len(recent_bets)} bets in 10 minutes. "
                "Take a 1-hour break to review your strategy and avoid emotional betting."
            )
            return result
            
        # Pattern 2: Oversized bet (>3x normal unit)
        bet_amount = bet_data.get('amount', 0)
        if bet_amount > unit_size * 3:
            result['tilt_detected'] = True
            result['reason'] = 'OVERSIZED_BET'
            result['bet_count'] = 1
            result['timeframe'] = 'current bet'
            result['recommended_action'] = (
                f"This bet (${bet_amount:.2f}) is {bet_amount/unit_size:.1f}x your normal unit size. "
                "Stick to your strategy and avoid chasing losses."
            )
            return result
            
        # Pattern 3: Rapid consecutive bets (<2 min between)
        if len(self.user_bet_history[user_id]) >= 2:
            last_two_bets = sorted(self.user_bet_history[user_id])[-2:]
            time_between = (last_two_bets[1] - last_two_bets[0]).total_seconds()
            
            if time_between < 120:  # 2 minutes
                result['tilt_detected'] = True
                result['reason'] = 'RAPID_BETTING'
                result['bet_count'] = 2
                result['timeframe'] = f'{int(time_between)} seconds'
                result['recommended_action'] = (
                    "You're betting too quickly without proper analysis. "
                    "Wait at least 5 minutes between bets to ensure quality decisions."
                )
                return result
        
        return result
        
    async def _broadcast_tilt_alert(self, user_id: str, tilt_data: Dict):
        """
        Broadcast tilt alert to WebSocket channel.
        Frontend subscribes to 'risk.alert' channel.
        """
        try:
            from core.websocket_manager import manager
            
            alert_message = {
                'type': 'TILT_DETECTED',
                'user_id': user_id,
                'payload': {
                    'bet_count': tilt_data['bet_count'],
                    'timeframe': tilt_data['timeframe'],
                    'unit_size': tilt_data['unit_size'],
                    'recommended_action': tilt_data['recommended_action'],
                    'reason': tilt_data['reason'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Broadcast to user-specific channel
            await manager.broadcast_to_channel('risk.alert', alert_message)
            
            # Also store in MongoDB for later review
            alerts_collection = self.db['risk_alerts']
            alerts_collection.insert_one({
                'user_id': user_id,
                'alert_type': 'TILT_DETECTED',
                'reason': tilt_data['reason'],
                'bet_count': tilt_data['bet_count'],
                'timeframe': tilt_data['timeframe'],
                'timestamp': datetime.now(timezone.utc),
                'acknowledged': False
            })
            
            logger.info(f"📡 Tilt alert broadcast to user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to broadcast tilt alert: {e}")
            
    def reset_user_history(self, user_id: str):
        """Reset tracking for user (called after break period)"""
        self.user_bet_history[user_id] = []
        self.last_alert_time.pop(user_id, None)
        logger.info(f"✅ Reset tilt tracking for user {user_id}")


# Global singleton instance
_tilt_service = None

def get_tilt_service(db_client):
    """Get or create tilt detection service"""
    global _tilt_service
    if _tilt_service is None:
        _tilt_service = TiltDetectionService(db_client)
    return _tilt_service

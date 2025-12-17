"""
Notification Service
Handles push notifications, real-time alerts, and notification management
🛡️ TRUTH MODE v1.0: All pick notifications validated before sending
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from db.mongo import client
from middleware.truth_mode_enforcement import enforce_truth_mode_on_pick

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing user notifications and alerts"""
    
    def __init__(self):
        self.db = client["beatvegas_db"]
        self.notifications = self.db["notifications"]
        self.live_triggers = self.db["live_triggers"]
        
    def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        event_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> str:
        """
        Create a new notification for a user
        
        Args:
            user_id: Target user ID (or "all" for broadcast)
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            event_id: Associated event ID (optional)
            data: Additional context data
            priority: Priority level
            
        Returns:
            notification_id
        """
        from uuid import uuid4
        
        notification_id = f"notif_{uuid4().hex[:12]}"
        
        notification = {
            "notification_id": notification_id,
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "event_id": event_id,
            "data": data or {},
            "priority": priority,
            "read": False,
            "created_at": datetime.utcnow()
        }
        
        self.notifications.insert_one(notification)
        logger.info(f"📬 Created notification {notification_id} for user {user_id}")
        
        return notification_id
        
    def get_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user"""
        query: Dict[str, Any] = {"user_id": {"$in": [user_id, "all"]}}
        
        if unread_only:
            query["read"] = False
            
        notifications = list(self.notifications.find(query).sort("created_at", -1).limit(limit))
        
        return notifications
        
    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        result = self.notifications.update_one(
            {"notification_id": notification_id, "user_id": user_id},
            {"$set": {"read": True}}
        )
        
        return result.modified_count > 0
        
    def mark_all_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user"""
        result = self.notifications.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        
        return result.modified_count
        
    def create_recalculation_notification(
        self,
        user_id: str,
        event_id: str,
        event_name: str,
        old_probability: float,
        new_probability: float,
        trigger_reason: str
    ):
        """Create a notification for AI recalculation"""
        change = abs(new_probability - old_probability)
        direction = "increased" if new_probability > old_probability else "decreased"
        
        title = f"🔄 AI Recalculated: {event_name}"
        message = f"Win probability {direction} from {old_probability:.1%} to {new_probability:.1%} ({trigger_reason})"
        
        priority = "high" if change > 0.10 else "normal"
        
        self.create_notification(
            user_id=user_id,
            notification_type="recalculation",
            title=title,
            message=message,
            event_id=event_id,
            data={
                "old_probability": old_probability,
                "new_probability": new_probability,
                "change": change,
                "trigger": trigger_reason
            },
            priority=priority
        )
        
    def create_line_movement_notification(
        self,
        user_id: str,
        event_id: str,
        event_name: str,
        market: str,
        old_line: float,
        new_line: float
    ):
        """Create notification for significant line movement"""
        movement = new_line - old_line
        
        title = f"📊 Line Movement: {event_name}"
        message = f"{market} moved from {old_line:+.1f} to {new_line:+.1f}"
        
        self.create_notification(
            user_id=user_id,
            notification_type="line_movement",
            title=title,
            message=message,
            event_id=event_id,
            data={
                "market": market,
                "old_line": old_line,
                "new_line": new_line,
                "movement": movement
            },
            priority="normal"
        )
        
    def create_pick_notification(
        self,
        user_id: str,
        event_id: str,
        bet_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Create notification for a pick - validates through Truth Mode first
        Returns notification_id if valid, None if blocked
        """
        # Validate pick through Truth Mode
        validation_result = enforce_truth_mode_on_pick(
            event_id=event_id,
            bet_type=bet_type
        )
        
        if validation_result["status"] != "VALID":
            logger.warning(
                f"🛡️ [Truth Mode] Blocked pick notification for {event_id}: "
                f"{validation_result.get('block_reasons', [])}"
            )
            return None
        
        # Pick validated - send notification
        notification_data = data or {}
        notification_data["truth_mode_validated"] = True
        notification_data["confidence_score"] = validation_result.get("confidence_score", 0.0)
        
        return self.create_notification(
            user_id=user_id,
            notification_type="pick_alert",
            title=title,
            message=message,
            event_id=event_id,
            data=notification_data,
            priority=priority
        )
    
    def broadcast_notification(
        self,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal"
    ) -> str:
        """Broadcast notification to all users"""
        return self.create_notification(
            user_id="all",
            notification_type=notification_type,
            title=title,
            message=message,
            data=data,
            priority=priority
        )
        
    def create_live_trigger(
        self,
        event_id: str,
        trigger_type: str,
        description: str,
        severity: str,
        source: str = "system"
    ) -> str:
        """Create a live trigger for automated recalculation"""
        from uuid import uuid4
        
        trigger_id = f"trig_{uuid4().hex[:12]}"
        
        trigger = {
            "trigger_id": trigger_id,
            "event_id": event_id,
            "trigger_type": trigger_type,
            "description": description,
            "severity": severity,
            "source": source,
            "requires_recalculation": True,
            "processed": False,
            "created_at": datetime.utcnow(),
            "processed_at": None
        }
        
        self.live_triggers.insert_one(trigger)
        logger.info(f"🚨 Created live trigger {trigger_id} for event {event_id}: {description}")
        
        return trigger_id
        
    def get_pending_triggers(self) -> List[Dict[str, Any]]:
        """Get all unprocessed triggers requiring recalculation"""
        triggers = list(self.live_triggers.find({
            "processed": False,
            "requires_recalculation": True
        }).sort("created_at", 1).limit(100))
        
        return triggers
        
    def mark_trigger_processed(self, trigger_id: str):
        """Mark a trigger as processed"""
        self.live_triggers.update_one(
            {"trigger_id": trigger_id},
            {
                "$set": {
                    "processed": True,
                    "processed_at": datetime.utcnow()
                }
            }
        )


# Singleton instance
_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create NotificationService singleton"""
    global _service
    if _service is None:
        _service = NotificationService()
    return _service

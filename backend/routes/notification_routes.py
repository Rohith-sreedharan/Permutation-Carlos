"""
Notification Routes
API endpoints for push notifications and alerts
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
from pydantic import BaseModel
from services.notification_service import get_notification_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationPushRequest(BaseModel):
    """Request to push a notification"""
    user_id: str  # "all" for broadcast
    type: str
    title: str
    message: str
    event_id: Optional[str] = None
    data: dict = {}
    priority: str = "normal"


class LiveTriggerRequest(BaseModel):
    """Request to create a live trigger"""
    event_id: str
    trigger_type: str
    description: str
    severity: str
    source: str = "api"


def _get_user_id_from_auth(authorization: Optional[str]) -> str:
    """Extract user ID from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    
    token_parts = authorization.replace("Bearer ", "").split(":")
    if len(token_parts) != 2:
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    return token_parts[1]


def _check_admin(authorization: Optional[str]) -> bool:
    """Check if user is admin (simplified - should check DB)"""
    # TODO: Implement proper admin check from database
    return True  # For now, allow all authenticated users


@router.get("/list")
def list_notifications(
    authorization: Optional[str] = Header(None),
    unread_only: bool = False,
    limit: int = 50
):
    """Get user's notifications"""
    user_id = _get_user_id_from_auth(authorization)
    service = get_notification_service()
    
    notifications = service.get_user_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit
    )
    
    return {
        "count": len(notifications),
        "unread_count": sum(1 for n in notifications if not n.get("read")),
        "notifications": notifications
    }


@router.post("/push")
def push_notification(
    request: NotificationPushRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Push a notification (Admin only)
    Use user_id="all" for broadcast
    """
    if not _check_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    service = get_notification_service()
    
    notification_id = service.create_notification(
        user_id=request.user_id,
        notification_type=request.type,
        title=request.title,
        message=request.message,
        event_id=request.event_id,
        data=request.data,
        priority=request.priority
    )
    
    return {
        "success": True,
        "notification_id": notification_id,
        "message": f"Notification sent to {request.user_id}"
    }


@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    authorization: Optional[str] = Header(None)
):
    """Mark a notification as read"""
    user_id = _get_user_id_from_auth(authorization)
    service = get_notification_service()
    
    success = service.mark_as_read(notification_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"success": True}


@router.post("/mark-all-read")
def mark_all_notifications_read(
    authorization: Optional[str] = Header(None)
):
    """Mark all notifications as read"""
    user_id = _get_user_id_from_auth(authorization)
    service = get_notification_service()
    
    count = service.mark_all_read(user_id)
    
    return {
        "success": True,
        "marked_read": count
    }


@router.post("/triggers/create")
def create_live_trigger(
    request: LiveTriggerRequest,
    authorization: Optional[str] = Header(None)
):
    """Create a live trigger for automated recalculation (Admin only)"""
    if not _check_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    service = get_notification_service()
    
    trigger_id = service.create_live_trigger(
        event_id=request.event_id,
        trigger_type=request.trigger_type,
        description=request.description,
        severity=request.severity,
        source=request.source
    )
    
    return {
        "success": True,
        "trigger_id": trigger_id,
        "message": f"Live trigger created for event {request.event_id}"
    }


@router.get("/triggers/pending")
def get_pending_triggers(authorization: Optional[str] = Header(None)):
    """Get all pending triggers requiring recalculation (Admin only)"""
    if not _check_admin(authorization):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    service = get_notification_service()
    triggers = service.get_pending_triggers()
    
    return {
        "count": len(triggers),
        "triggers": triggers
    }

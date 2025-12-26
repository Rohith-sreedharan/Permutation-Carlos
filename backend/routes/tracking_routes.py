"""
Event Tracking Routes — Phase 1.2

Provides server-side endpoints for event tracking.

Client-side code fires these endpoints, which then propagate to:
- Internal analytics_events collection
- Meta Conversion API
- TikTok Events API
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from services.pixel_tracking import pixel_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tracking", tags=["tracking"])


class TrackEventRequest(BaseModel):
    """
    Event tracking request payload
    
    Required:
        event_name: One of ALLOWED_EVENTS
    
    Optional:
        user_id: Internal user ID
        email: User email (will be hashed)
        event_data: Event-specific payload
        event_id: Unique ID for deduplication
    """
    event_name: str = Field(..., description="Event name (WaitlistSubmit, DailyPreviewViewed, etc.)")
    user_id: Optional[str] = Field(default=None, description="Internal user ID")
    email: Optional[str] = Field(default=None, description="User email (hashed server-side)")
    event_data: Optional[Dict[str, Any]] = Field(default=None, description="Event-specific payload")
    event_id: Optional[str] = Field(default=None, description="Unique event ID (auto-generated if omitted)")


@router.post("/event", response_model=None)
async def track_event(request: TrackEventRequest, http_request: Request):
    """
    Track event server-side
    
    This endpoint receives events from client-side code and propagates them
    to Meta CAPI, TikTok Events API, and internal analytics.
    
    Usage:
        POST /api/tracking/event
        {
            "event_name": "WaitlistSubmit",
            "email": "user@example.com",
            "event_data": {
                "source": "landing",
                "page_url": "https://beatvegas.app"
            }
        }
    
    Response:
        {
            "success": true,
            "event_id": "uuid",
            "tracked_on": ["internal", "meta", "tiktok"]
        }
    """
    try:
        # Extract IP and User-Agent from request
        ip_address = http_request.client.host if http_request and http_request.client else None
        user_agent = http_request.headers.get('User-Agent') if http_request and http_request.headers else None
        
        # Track event
        result = pixel_tracker.track_event(
            event_name=request.event_name,
            user_id=request.user_id,
            email=request.email,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data=request.event_data or {},
            event_id=request.event_id
        )
        
        if not result['success']:
            logger.warning(f"Event tracking failed: {result['errors']}")
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'Event tracking failed',
                    'errors': result['errors']
                }
            )
        
        return {
            'success': True,
            'event_id': result['event_id'],
            'tracked_on': result['tracked_on'],
            'message': f"Event tracked successfully across {len(result['tracked_on'])} platforms"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Event tracking error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Tracking failed: {str(e)}")


# Convenience endpoints for specific events
@router.post("/waitlist-submit", response_model=None)
async def track_waitlist_submit(
    email: str,
    http_request: Request,
    source: str = "unknown",
    page_url: str = ""
):
    """
    Track waitlist submission
    
    Convenience endpoint for WaitlistSubmit event.
    """
    return await track_event(
        request=TrackEventRequest(
            event_name="WaitlistSubmit",
            email=email,
            event_data={
                'source': source,
                'page_url': page_url
            }
        ),
        http_request=http_request
    )


@router.post("/daily-preview-viewed", response_model=None)
async def track_daily_preview_viewed(
    game_id: str,
    sport: str,
    edge_state: str,
    confidence_band: str,
    http_request: Request,
    page_url: str = "",
    user_id: Optional[str] = None
):
    """
    Track daily preview view
    
    Convenience endpoint for DailyPreviewViewed event.
    """
    return await track_event(
        request=TrackEventRequest(
            event_name="DailyPreviewViewed",
            user_id=user_id,
            event_data={
                'game_id': game_id,
                'sport': sport,
                'edge_state': edge_state,
                'confidence_band': confidence_band,
                'page_url': page_url
            }
        ),
        http_request=http_request
    )


@router.post("/telegram-join-click", response_model=None)
async def track_telegram_join_click(
    http_request: Request,
    source: str = "unknown",
    page_url: str = "",
    user_id: Optional[str] = None
):
    """
    Track Telegram join CTA click
    
    Convenience endpoint for TelegramJoinClick event.
    """
    return await track_event(
        request=TrackEventRequest(
            event_name="TelegramJoinClick",
            user_id=user_id,
            event_data={
                'source': source,
                'page_url': page_url
            }
        ),
        http_request=http_request
    )


@router.post("/parlay-unlock-attempt", response_model=None)
async def track_parlay_unlock_attempt(
    lock_reason: str,
    http_request: Request,
    page_url: str = "",
    user_id: Optional[str] = None
):
    """
    Track parlay unlock attempt
    
    Convenience endpoint for ParlayUnlockAttempt event.
    """
    return await track_event(
        request=TrackEventRequest(
            event_name="ParlayUnlockAttempt",
            user_id=user_id,
            event_data={
                'lock_reason': lock_reason,
                'page_url': page_url
            }
        ),
        http_request=http_request
    )


@router.post("/sim-run-complete", response_model=None)
async def track_sim_run_complete(
    sim_count: int,
    market_type: str,
    http_request: Request,
    page_url: str = "",
    user_id: Optional[str] = None
):
    """
    Track simulation completion
    
    Convenience endpoint for SimRunComplete event.
    """
    return await track_event(
        request=TrackEventRequest(
            event_name="SimRunComplete",
            user_id=user_id,
            event_data={
                'sim_count': sim_count,
                'market_type': market_type,
                'page_url': page_url
            }
        ),
        http_request=http_request
    )

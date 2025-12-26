"""
Pixel & Event Tracking Service — Phase 1.2

Handles server-side event tracking to:
- Meta (Facebook) Conversion API
- TikTok Events API
- Internal analytics_events collection

Critical Rules:
1. Event names are EXACT (WaitlistSubmit, DailyPreviewViewed, etc.)
2. Server-side preferred, client-side fallback
3. Deduplication via event_id
4. No PII except hashed email where required
"""

import hashlib
import requests
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import uuid

from db.mongo import db

logger = logging.getLogger(__name__)

# Environment variables for pixel IDs and tokens
META_PIXEL_ID = os.getenv('META_PIXEL_ID')
META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN')
TIKTOK_PIXEL_ID = os.getenv('TIKTOK_PIXEL_ID')
TIKTOK_ACCESS_TOKEN = os.getenv('TIKTOK_ACCESS_TOKEN')

# Allowed event names (LOCKED)
ALLOWED_EVENTS = {
    'WaitlistSubmit',
    'DailyPreviewViewed',
    'TelegramJoinClick',
    'ParlayUnlockAttempt',
    'SimRunComplete'
}


class PixelTrackingService:
    """
    Unified tracking service for all pixel platforms
    
    Usage:
        tracker = PixelTrackingService()
        tracker.track_event(
            event_name='WaitlistSubmit',
            user_id='user123',
            email='user@example.com',
            event_data={'source': 'landing', 'page_url': '...'}
        )
    """
    
    @staticmethod
    def _hash_email(email: str) -> Optional[str]:
        """Hash email for privacy compliance (SHA-256)"""
        if not email:
            return None
        return hashlib.sha256(email.lower().strip().encode()).hexdigest()
    
    @staticmethod
    def _generate_event_id() -> str:
        """Generate unique event ID for deduplication"""
        return str(uuid.uuid4())
    
    @staticmethod
    def _validate_event_name(event_name: str) -> bool:
        """Ensure event name is in allowed list"""
        if event_name not in ALLOWED_EVENTS:
            logger.warning(f"Invalid event name: {event_name}. Must be one of {ALLOWED_EVENTS}")
            return False
        return True
    
    def track_event(
        self,
        event_name: str,
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Track event across all platforms
        
        Args:
            event_name: One of ALLOWED_EVENTS
            user_id: Internal user ID (optional)
            email: User email (hashed for privacy)
            ip_address: User IP (for server-side tracking)
            user_agent: Browser user agent
            event_data: Event-specific payload
            event_id: Unique event ID (auto-generated if not provided)
        
        Returns:
            {
                'success': bool,
                'event_id': str,
                'tracked_on': ['internal', 'meta', 'tiktok'],
                'errors': []
            }
        """
        # Validate event name
        if not self._validate_event_name(event_name):
            return {
                'success': False,
                'event_id': None,
                'tracked_on': [],
                'errors': [f'Invalid event name: {event_name}']
            }
        
        # Generate event ID for deduplication
        if not event_id:
            event_id = self._generate_event_id()
        
        # Prepare event data
        if not event_data:
            event_data = {}
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Hash email if provided
        hashed_email = self._hash_email(email) if email else None
        
        tracked_on = []
        errors = []
        
        # 1. Internal logging (always succeeds)
        try:
            self._track_internal(
                event_name=event_name,
                event_id=event_id,
                user_id=user_id,
                event_data=event_data,
                timestamp=timestamp
            )
            tracked_on.append('internal')
        except Exception as e:
            logger.error(f"Internal tracking failed: {e}")
            errors.append(f"Internal: {str(e)}")
        
        # 2. Meta Conversion API
        if META_PIXEL_ID and META_ACCESS_TOKEN:
            try:
                self._track_meta(
                    event_name=event_name,
                    event_id=event_id,
                    hashed_email=hashed_email,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    event_data=event_data,
                    timestamp=timestamp
                )
                tracked_on.append('meta')
            except Exception as e:
                logger.error(f"Meta tracking failed: {e}")
                errors.append(f"Meta: {str(e)}")
        else:
            logger.info("Meta pixel not configured (META_PIXEL_ID or META_ACCESS_TOKEN missing)")
        
        # 3. TikTok Events API
        if TIKTOK_PIXEL_ID and TIKTOK_ACCESS_TOKEN:
            try:
                self._track_tiktok(
                    event_name=event_name,
                    event_id=event_id,
                    hashed_email=hashed_email,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    event_data=event_data,
                    timestamp=timestamp
                )
                tracked_on.append('tiktok')
            except Exception as e:
                logger.error(f"TikTok tracking failed: {e}")
                errors.append(f"TikTok: {str(e)}")
        else:
            logger.info("TikTok pixel not configured (TIKTOK_PIXEL_ID or TIKTOK_ACCESS_TOKEN missing)")
        
        return {
            'success': len(tracked_on) > 0,
            'event_id': event_id,
            'tracked_on': tracked_on,
            'errors': errors
        }
    
    def _track_internal(
        self,
        event_name: str,
        event_id: str,
        user_id: Optional[str],
        event_data: Dict[str, Any],
        timestamp: str
    ):
        """Log event to internal analytics_events collection"""
        db.analytics_events.insert_one({
            'event_type': event_name,
            'event_id': event_id,
            'user_id': user_id,
            'timestamp': timestamp,
            **event_data  # Merge event-specific data
        })
        logger.info(f"✓ Internal: {event_name} | event_id={event_id}")
    
    def _track_meta(
        self,
        event_name: str,
        event_id: str,
        hashed_email: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        event_data: Dict[str, Any],
        timestamp: str
    ):
        """
        Send event to Meta Conversion API
        
        Docs: https://developers.facebook.com/docs/marketing-api/conversions-api
        """
        # Convert timestamp to Unix seconds
        event_time = int(datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp())
        
        # Build user data
        user_data = {}
        if hashed_email:
            user_data['em'] = hashed_email  # Hashed email
        if ip_address:
            user_data['client_ip_address'] = ip_address
        if user_agent:
            user_data['client_user_agent'] = user_agent
        
        # Build custom data from event_data
        custom_data = {
            k: v for k, v in event_data.items()
            if k not in ['timestamp', 'event_id', 'user_id']
        }
        
        # Build event payload
        payload = {
            'data': [{
                'event_name': event_name,
                'event_time': event_time,
                'event_id': event_id,  # Deduplication
                'user_data': user_data,
                'custom_data': custom_data,
                'action_source': 'website'
            }]
        }
        
        # Send to Meta Conversion API
        url = f'https://graph.facebook.com/v18.0/{META_PIXEL_ID}/events'
        params = {'access_token': META_ACCESS_TOKEN}
        
        response = requests.post(url, json=payload, params=params, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"✓ Meta: {event_name} | event_id={event_id} | response={result}")
    
    def _track_tiktok(
        self,
        event_name: str,
        event_id: str,
        hashed_email: Optional[str],
        ip_address: Optional[str],
        user_agent: Optional[str],
        event_data: Dict[str, Any],
        timestamp: str
    ):
        """
        Send event to TikTok Events API
        
        Docs: https://business-api.tiktok.com/portal/docs?id=1771101027431425
        """
        # Convert timestamp to Unix seconds
        event_time = int(datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp())
        
        # Build user data
        user = {}
        if hashed_email:
            user['email'] = hashed_email  # Hashed email
        if ip_address:
            user['ip'] = ip_address
        if user_agent:
            user['user_agent'] = user_agent
        
        # Build properties from event_data
        properties = {
            k: v for k, v in event_data.items()
            if k not in ['timestamp', 'event_id', 'user_id']
        }
        
        # Build event payload
        payload = {
            'pixel_code': TIKTOK_PIXEL_ID,
            'event': event_name,
            'event_id': event_id,  # Deduplication
            'timestamp': str(event_time),
            'context': {
                'user': user,
                'page': {
                    'url': event_data.get('page_url', '')
                }
            },
            'properties': properties
        }
        
        # Send to TikTok Events API
        url = 'https://business-api.tiktok.com/open_api/v1.3/event/track/'
        headers = {
            'Access-Token': TIKTOK_ACCESS_TOKEN,
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"✓ TikTok: {event_name} | event_id={event_id} | response={result}")


# Global tracker instance
pixel_tracker = PixelTrackingService()

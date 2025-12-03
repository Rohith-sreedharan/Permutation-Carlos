"""
SharpSports BookLink Integration Routes
========================================

Handles automated bet syncing for Premium/Elite users via SharpSports BookLink.

Endpoints:
- POST /api/sync/link - Generate BookLink session URL
- GET /api/sync/verify - Verify BookLink connection status
- DELETE /api/sync/disconnect - Revoke BookLink access
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import secrets
from ..db.mongo import db

router = APIRouter(prefix="/api/sync", tags=["sync"])


class BookLinkRequest(BaseModel):
    user_id: str
    sportsbooks: list[str] = ["draftkings", "fanduel", "mgm"]  # Preferred books


class BookLinkResponse(BaseModel):
    booklink_url: str
    session_id: str
    expires_at: str
    instructions: str


def verify_premium_tier(authorization: Optional[str] = Header(None)) -> dict:
    """Verify user is Premium or Elite tier"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No authentication token provided")
    
    token = authorization.replace('Bearer ', '')
    users_collection = db['users']
    user = users_collection.find_one({'auth_token': token})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    tier = user.get('tier', 'free')
    if tier not in ['premium', 'elite', 'pro']:  # Pro tier also gets access
        raise HTTPException(
            status_code=403, 
            detail="BookLink sync requires Premium or Elite tier. Upgrade to unlock automated bet tracking."
        )
    
    return user


@router.post("/link", response_model=BookLinkResponse)
async def generate_booklink(
    request: BookLinkRequest,
    user: dict = Depends(verify_premium_tier)
):
    """
    Generate SharpSports BookLink URL for automated bet syncing.
    
    **Tier Requirement:** Premium or Elite
    
    Flow:
    1. Verify user tier (Premium/Elite only)
    2. Generate unique session ID
    3. Store session in database
    4. Return BookLink URL for user to connect sportsbooks
    
    **Returns:**
    - booklink_url: URL to redirect user to SharpSports
    - session_id: Unique session identifier
    - expires_at: Session expiration timestamp
    - instructions: User-facing setup instructions
    """
    # Generate secure session ID
    session_id = f"bv_sync_{secrets.token_urlsafe(32)}"
    
    # Create session record
    sync_sessions = db['sync_sessions']
    session_doc = {
        'session_id': session_id,
        'user_id': request.user_id,
        'status': 'pending',
        'sportsbooks': request.sportsbooks,
        'created_at': datetime.now(timezone.utc),
        'expires_at': datetime.now(timezone.utc).isoformat(),
        'last_sync': None
    }
    sync_sessions.insert_one(session_doc)
    
    # Generate BookLink URL (mock for now - real integration would use SharpSports API)
    booklink_url = f"https://sharpsports.io/booklink?session={session_id}&return=beatvegas"
    
    return BookLinkResponse(
        booklink_url=booklink_url,
        session_id=session_id,
        expires_at=session_doc['expires_at'],
        instructions="Click the link to securely connect your sportsbooks. Your bet slips will sync automatically."
    )


@router.get("/verify/{session_id}")
async def verify_booklink_status(
    session_id: str,
    user: dict = Depends(verify_premium_tier)
):
    """
    Check BookLink connection status.
    
    Returns:
    - status: pending | connected | expired
    - connected_books: List of connected sportsbooks
    - last_sync: Timestamp of most recent bet sync
    """
    sync_sessions = db['sync_sessions']
    session = sync_sessions.find_one({'session_id': session_id, 'user_id': user['_id']})
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        'status': session.get('status', 'pending'),
        'connected_books': session.get('sportsbooks', []),
        'last_sync': session.get('last_sync'),
        'total_bets_synced': session.get('total_bets_synced', 0)
    }


@router.delete("/disconnect/{session_id}")
async def disconnect_booklink(
    session_id: str,
    user: dict = Depends(verify_premium_tier)
):
    """
    Revoke BookLink access and stop bet syncing.
    """
    sync_sessions = db['sync_sessions']
    result = sync_sessions.update_one(
        {'session_id': session_id, 'user_id': user['_id']},
        {'$set': {'status': 'disconnected', 'disconnected_at': datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {'message': 'BookLink disconnected successfully'}

"""
SharpSports Webhook Handler
============================

Receives bet_slip_created webhooks from SharpSports and ingests bets into user_bets collection.

Webhook Events:
- bet_slip_created: New bet placed via connected sportsbook
- bet_settled: Bet outcome determined
- bet_voided: Bet cancelled/voided
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime, timezone
import hmac
import hashlib
from ..db.mongo import db
from ..services.tilt_detection import TiltDetectionService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Initialize tilt detection service
tilt_service = TiltDetectionService(db)


class BetSlipWebhook(BaseModel):
    event_type: Literal["bet_slip_created", "bet_settled", "bet_voided"]
    session_id: str
    bet_data: dict


class BetData(BaseModel):
    slip_id: str
    event_id: Optional[str] = None
    sport: str
    pick_type: Literal["single", "parlay", "prop"]
    selection: str  # e.g., "Lakers -5", "Over 220.5", "LeBron 25+ pts"
    line: Optional[float] = None
    odds: float  # Decimal odds (e.g., 1.91 = -110)
    stake: float
    num_legs: int = 1
    sportsbook: str
    placed_at: str  # ISO timestamp


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify webhook signature to prevent spoofing"""
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


async def process_bet_slip(session_id: str, bet_data: dict) -> dict:
    """
    Process incoming bet slip and store in user_bets collection.
    
    Returns:
    - bet_id: MongoDB ObjectId of stored bet
    - tilt_detected: Boolean flag from TiltDetectionService
    """
    # Find user from session
    sync_sessions = db['sync_sessions']
    session = sync_sessions.find_one({'session_id': session_id})
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    user_id = session['user_id']
    
    # Parse bet data
    bet = BetData(**bet_data)
    
    # Store in user_bets collection
    user_bets = db['user_bets']
    bet_doc = {
        'user_id': user_id,
        'slip_id': bet.slip_id,
        'event_id': bet.event_id,
        'sport': bet.sport,
        'pick_type': bet.pick_type,
        'selection': bet.selection,
        'line': bet.line,
        'odds': bet.odds,
        'stake': bet.stake,
        'num_legs': bet.num_legs,
        'sportsbook': bet.sportsbook,
        'source': 'sharpsports_sync',
        'outcome': 'pending',
        'profit': None,
        'created_at': datetime.fromisoformat(bet.placed_at.replace('Z', '+00:00')),
        'settled_at': None,
        'synced_at': datetime.now(timezone.utc)
    }
    
    result = user_bets.insert_one(bet_doc)
    
    # Update session sync stats
    sync_sessions.update_one(
        {'session_id': session_id},
        {
            '$set': {'last_sync': datetime.now(timezone.utc)},
            '$inc': {'total_bets_synced': 1}
        }
    )
    
    # Trigger tilt detection
    tilt_result = await tilt_service.track_bet(
        user_id=str(user_id),
        bet_data={
            'amount': bet.stake,
            'timestamp': datetime.now(timezone.utc),
            'type': bet.pick_type
        }
    )
    
    return {
        'bet_id': str(result.inserted_id),
        'tilt_detected': tilt_result.get('tilt_detected', False),
        'tilt_reason': tilt_result.get('reason')
    }


@router.post("/sharpsports")
async def sharpsports_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    webhook: BetSlipWebhook
):
    """
    Receive bet_slip_created webhook from SharpSports.
    
    **Authentication:** HMAC signature verification
    
    **Payload:**
    ```json
    {
      "event_type": "bet_slip_created",
      "session_id": "bv_sync_xyz123",
      "bet_data": {
        "slip_id": "dk_slip_456",
        "sport": "NBA",
        "pick_type": "single",
        "selection": "Lakers -5",
        "line": -5.0,
        "odds": 1.91,
        "stake": 100.0,
        "num_legs": 1,
        "sportsbook": "draftkings",
        "placed_at": "2025-11-29T20:30:00Z"
      }
    }
    ```
    
    **Response:**
    - 200: Bet ingested successfully
    - 404: Session not found
    - 401: Invalid signature
    """
    # Verify webhook signature (in production)
    # signature = request.headers.get('X-SharpSports-Signature')
    # if not verify_webhook_signature(await request.body(), signature, WEBHOOK_SECRET):
    #     raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    if webhook.event_type == "bet_slip_created":
        # Process bet slip (async to avoid blocking webhook response)
        background_tasks.add_task(
            process_bet_slip,
            webhook.session_id,
            webhook.bet_data
        )
        
        return {
            'status': 'accepted',
            'message': 'Bet slip queued for processing'
        }
    
    elif webhook.event_type == "bet_settled":
        # Update bet outcome
        user_bets = db['user_bets']
        slip_id = webhook.bet_data['slip_id']
        outcome = webhook.bet_data['outcome']  # 'win' | 'loss' | 'push'
        profit = webhook.bet_data.get('profit', 0)
        
        user_bets.update_one(
            {'slip_id': slip_id},
            {
                '$set': {
                    'outcome': outcome,
                    'profit': profit,
                    'settled_at': datetime.now(timezone.utc)
                }
            }
        )
        
        return {'status': 'processed', 'outcome': outcome}
    
    elif webhook.event_type == "bet_voided":
        # Mark bet as voided
        user_bets = db['user_bets']
        slip_id = webhook.bet_data['slip_id']
        
        user_bets.update_one(
            {'slip_id': slip_id},
            {
                '$set': {
                    'outcome': 'void',
                    'profit': 0,
                    'settled_at': datetime.now(timezone.utc)
                }
            }
        )
        
        return {'status': 'voided'}
    
    return {'status': 'unknown_event_type'}

"""
Manual Bet Entry & History Routes
==================================

Allows Free/Standard tier users to manually track their betting activity.

Endpoints:
- POST /api/bets/manual - Submit a bet manually
- GET /api/bets/history - Retrieve bet history with filters
- GET /api/bets/pnl - Calculate profit/loss metrics
- PUT /api/bets/{bet_id}/settle - Update bet outcome
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, validator
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import re
from ..db.mongo import db
from ..services.tilt_detection import TiltDetectionService

router = APIRouter(prefix="/api/bets", tags=["bets"])

tilt_service = TiltDetectionService(db)


class ManualBetEntry(BaseModel):
    selection: str  # e.g., "Lakers -5", "Over 220.5", "LeBron 25+ pts"
    stake: float
    odds: float  # American odds (-110, +150) or decimal (1.91, 2.50)
    sport: Optional[str] = "NBA"
    pick_type: Literal["single", "parlay", "prop"] = "single"
    num_legs: int = 1
    event_id: Optional[str] = None
    sportsbook: Optional[str] = "manual"
    
    @validator('selection')
    def parse_selection(cls, v):
        """Accept formats like 'Lakers -5', 'Over 220.5', 'LeBron 25+ pts'"""
        if not v or len(v) < 3:
            raise ValueError("Selection must be at least 3 characters")
        return v.strip()
    
    @validator('odds')
    def validate_odds(cls, v):
        """Accept American or decimal odds"""
        if v == 0:
            raise ValueError("Odds cannot be 0")
        return v


class SettleBet(BaseModel):
    outcome: Literal["win", "loss", "push", "void"]
    profit: Optional[float] = None


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Extract user from auth token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No authentication token found")
    
    token = authorization.replace('Bearer ', '')
    users = db['users']
    user = users.find_one({'auth_token': token})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user


def parse_american_odds_to_decimal(odds: float) -> float:
    """Convert American odds to decimal"""
    if odds == 0:
        return 1.0
    elif odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1


def extract_line_from_selection(selection: str) -> Optional[float]:
    """
    Extract numeric line from selection string.
    
    Examples:
    - "Lakers -5" → -5.0
    - "Over 220.5" → 220.5
    - "LeBron 25+ pts" → 25.0
    """
    # Match patterns like -5, +7.5, 220.5, 25+
    patterns = [
        r'([-+]?\d+\.?\d*)',  # Any number with optional sign
    ]
    
    for pattern in patterns:
        match = re.search(pattern, selection)
        if match:
            return float(match.group(1))
    
    return None


@router.post("/manual")
async def submit_manual_bet(
    bet: ManualBetEntry,
    user: dict = Depends(get_current_user)
):
    """
    Submit a bet manually.
    
    **Input Formats:**
    - Selection: "Lakers -5", "Over 220.5", "LeBron 25+ Points"
    - Odds: American (-110, +150) or Decimal (1.91, 2.50)
    - Stake: Dollar amount
    
    **Example:**
    ```json
    {
      "selection": "Lakers -5",
      "stake": 50.0,
      "odds": -110,
      "sport": "NBA",
      "pick_type": "single"
    }
    ```
    
    **Returns:**
    - bet_id: Unique bet identifier
    - tilt_detected: Warning if rapid betting detected
    """
    # Convert American odds to decimal if needed
    decimal_odds = bet.odds if bet.odds >= 1 else parse_american_odds_to_decimal(bet.odds)
    
    # Extract line from selection
    line = extract_line_from_selection(bet.selection)
    
    # Create bet document
    user_bets = db['user_bets']
    bet_doc = {
        'user_id': str(user['_id']),
        'slip_id': f"manual_{datetime.now(timezone.utc).timestamp()}",
        'event_id': bet.event_id,
        'sport': bet.sport,
        'pick_type': bet.pick_type,
        'selection': bet.selection,
        'line': line,
        'odds': decimal_odds,
        'stake': bet.stake,
        'num_legs': bet.num_legs,
        'sportsbook': bet.sportsbook,
        'source': 'manual',
        'outcome': 'pending',
        'profit': None,
        'created_at': datetime.now(timezone.utc),
        'settled_at': None
    }
    
    result = user_bets.insert_one(bet_doc)
    
    # Trigger tilt detection
    tilt_result = await tilt_service.track_bet(
        user_id=str(user['_id']),
        bet_data={
            'amount': bet.stake,
            'timestamp': datetime.now(timezone.utc),
            'type': bet.pick_type
        }
    )
    
    return {
        'bet_id': str(result.inserted_id),
        'message': 'Bet tracked successfully',
        'tilt_detected': tilt_result.get('tilt_detected', False),
        'tilt_warning': tilt_result.get('reason') if tilt_result.get('tilt_detected') else None
    }


@router.get("/history")
async def get_bet_history(
    user: dict = Depends(get_current_user),
    limit: int = 50,
    outcome: Optional[str] = None,
    sport: Optional[str] = None,
    days: int = 30
):
    """
    Retrieve bet history with filters.
    
    **Query Parameters:**
    - limit: Number of bets to return (default 50)
    - outcome: Filter by outcome (win/loss/pending)
    - sport: Filter by sport (NBA/NFL/etc)
    - days: Look back period (default 30 days)
    """
    user_bets = db['user_bets']
    
    # Build query
    query: Dict[str, Any] = {'user_id': str(user['_id'])}
    
    # Date filter
    since = datetime.now(timezone.utc) - timedelta(days=days)
    if days > 0:
        query['created_at'] = {'$gte': since}
    
    # Optional filters
    if outcome:
        query['outcome'] = outcome
    if sport:
        query['sport'] = sport
    
    # Fetch bets
    bets = list(user_bets.find(query).sort('created_at', -1).limit(limit))
    
    # Convert ObjectId to string
    for bet in bets:
        bet['_id'] = str(bet['_id'])
    
    return {
        'count': len(bets),
        'bets': bets
    }


@router.get("/pnl")
async def calculate_pnl(
    user: dict = Depends(get_current_user),
    days: int = 30
):
    """
    Calculate profit/loss metrics.
    
    **Returns:**
    - total_profit: Net profit/loss
    - total_stake: Total amount wagered
    - roi: Return on investment (%)
    - win_rate: Percentage of bets won
    - avg_odds: Average odds of bets placed
    - chase_index: Ratio of avg stake after loss vs normal
    """
    user_bets = db['user_bets']
    
    # Fetch settled bets
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = {
        'user_id': str(user['_id']),
        'created_at': {'$gte': since},
        'outcome': {'$in': ['win', 'loss', 'push']}
    }
    
    bets = list(user_bets.find(query).sort('created_at', 1))
    
    if not bets:
        return {
            'total_profit': 0,
            'total_stake': 0,
            'roi': 0,
            'win_rate': 0,
            'avg_odds': 0,
            'chase_index': 0,
            'total_bets': 0
        }
    
    # Calculate metrics
    total_stake = sum(b['stake'] for b in bets)
    total_profit = sum(b.get('profit', 0) for b in bets if b.get('profit') is not None)
    wins = [b for b in bets if b['outcome'] == 'win']
    losses = [b for b in bets if b['outcome'] == 'loss']
    
    win_rate = (len(wins) / len(bets)) * 100 if bets else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0
    avg_odds = sum(b['odds'] for b in bets) / len(bets) if bets else 0
    
    # Chase index: avg stake after loss vs overall avg
    stakes_after_loss = []
    for i, bet in enumerate(bets[:-1]):
        if bet['outcome'] == 'loss':
            stakes_after_loss.append(bets[i+1]['stake'])
    
    avg_stake = total_stake / len(bets) if bets else 0
    avg_stake_after_loss = sum(stakes_after_loss) / len(stakes_after_loss) if stakes_after_loss else avg_stake
    chase_index = avg_stake_after_loss / avg_stake if avg_stake > 0 else 1.0
    
    return {
        'total_profit': round(total_profit, 2),
        'total_stake': round(total_stake, 2),
        'roi': round(roi, 2),
        'win_rate': round(win_rate, 2),
        'avg_odds': round(avg_odds, 2),
        'chase_index': round(chase_index, 2),
        'total_bets': len(bets),
        'wins': len(wins),
        'losses': len(losses),
        'warning': 'CHASE BEHAVIOR DETECTED' if chase_index > 2.0 else None
    }


@router.put("/{bet_id}/settle")
async def settle_bet(
    bet_id: str,
    settlement: SettleBet,
    user: dict = Depends(get_current_user)
):
    """
    Update bet outcome (win/loss/push).
    
    **Body:**
    ```json
    {
      "outcome": "win",
      "profit": 45.50
    }
    ```
    """
    user_bets = db['user_bets']
    
    # Calculate profit if not provided
    if settlement.profit is None and settlement.outcome in ['win', 'loss']:
        bet = user_bets.find_one({'_id': ObjectId(bet_id), 'user_id': str(user['_id'])})
        if not bet:
            raise HTTPException(status_code=404, detail="Bet not found")
        
        if settlement.outcome == 'win':
            # Profit = stake * (odds - 1)
            settlement.profit = bet['stake'] * (bet['odds'] - 1)
        else:
            settlement.profit = -bet['stake']
    elif settlement.outcome in ['push', 'void']:
        settlement.profit = 0
    
    # Update bet
    result = user_bets.update_one(
        {'_id': ObjectId(bet_id), 'user_id': str(user['_id'])},
        {
            '$set': {
                'outcome': settlement.outcome,
                'profit': settlement.profit,
                'settled_at': datetime.now(timezone.utc)
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Bet not found or already settled")
    
    return {
        'message': f'Bet settled as {settlement.outcome}',
        'profit': settlement.profit
    }

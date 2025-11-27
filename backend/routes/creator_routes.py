"""
Creator Marketplace V2 Routes
Public creator profiles, verified badges, and "Tail This" functionality
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from db.mongo import db

router = APIRouter(prefix="/api/creator", tags=["creator"])


class CreatorStats(BaseModel):
    username: str
    avatar_url: Optional[str] = None
    roi: float
    win_rate: float
    total_bets: int
    total_units_won: float
    sharpe_ratio: float
    avg_odds: float
    badges: List[str]


class RecentSlip(BaseModel):
    slip_id: str
    sport: str
    pick_type: str
    selection: str
    odds: float
    stake: float
    outcome: Optional[str] = None  # 'win', 'loss', 'pending'
    settled_at: Optional[str] = None
    profit: Optional[float] = None


@router.get("/{username}/stats", response_model=CreatorStats)
async def get_creator_stats(username: str):
    """
    Get creator's public profile stats
    
    Returns:
        - ROI (Return on Investment)
        - Win Rate
        - Total Bets
        - Total Units Won/Lost
        - Sharpe Ratio (risk-adjusted returns)
        - Verified Badges
    """
    try:
        # Find user by username
        users_collection = db['users']
        user = users_collection.find_one({'username': username})
        
        if not user:
            raise HTTPException(status_code=404, detail="Creator not found")
        
        user_id = user.get('_id')
        
        # Calculate stats from bet history
        bets_collection = db['user_bets']
        all_bets = list(bets_collection.find({'user_id': str(user_id)}))
        
        if not all_bets:
            # No betting history - return defaults
            return {
                'username': username,
                'avatar_url': user.get('avatar_url'),
                'roi': 0.0,
                'win_rate': 0.0,
                'total_bets': 0,
                'total_units_won': 0.0,
                'sharpe_ratio': 0.0,
                'avg_odds': 0.0,
                'badges': []
            }
        
        # Calculate statistics
        total_bets = len(all_bets)
        settled_bets = [b for b in all_bets if b.get('outcome') in ['win', 'loss']]
        wins = len([b for b in settled_bets if b.get('outcome') == 'win'])
        
        win_rate = (wins / len(settled_bets) * 100) if settled_bets else 0.0
        
        # Calculate ROI
        total_staked = sum(b.get('stake', 0) for b in settled_bets)
        total_profit = sum(b.get('profit', 0) for b in settled_bets)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0.0
        
        # Calculate total units won (assuming 1 unit = 1% of bankroll)
        total_units_won = total_profit
        
        # Calculate Sharpe Ratio (simplified - production would use actual volatility)
        bet_returns = [b.get('profit', 0) / b.get('stake', 1) for b in settled_bets if b.get('stake', 0) > 0]
        if bet_returns:
            import statistics
            avg_return = statistics.mean(bet_returns)
            std_return = statistics.stdev(bet_returns) if len(bet_returns) > 1 else 1.0
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Calculate average odds
        avg_odds = sum(b.get('odds', 0) for b in all_bets) / total_bets if total_bets > 0 else 0.0
        
        # Calculate verified badges
        badges = []
        
        # Certified Sharp: ROI > 10% over 50+ bets
        if roi > 10 and total_bets >= 50:
            badges.append('certified_sharp')
        
        # Volume King: 100+ bets this month
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_bets = [b for b in all_bets if b.get('created_at', datetime.min.replace(tzinfo=timezone.utc)) > thirty_days_ago]
        if len(recent_bets) >= 100:
            badges.append('volume_king')
        
        # Hot Streak: 5+ wins in a row
        last_5_outcomes = [b.get('outcome') for b in sorted(settled_bets, key=lambda x: x.get('settled_at', ''), reverse=True)[:5]]
        if last_5_outcomes == ['win'] * 5:
            badges.append('hot_streak')
        
        # Parlay Master: >60% win rate on parlays (3+ legs)
        parlay_bets = [b for b in settled_bets if b.get('pick_type') == 'parlay' and b.get('num_legs', 0) >= 3]
        if parlay_bets:
            parlay_wins = len([b for b in parlay_bets if b.get('outcome') == 'win'])
            parlay_win_rate = parlay_wins / len(parlay_bets)
            if parlay_win_rate > 0.6 and len(parlay_bets) >= 10:
                badges.append('parlay_master')
        
        return {
            'username': username,
            'avatar_url': user.get('avatar_url'),
            'roi': round(roi, 1),
            'win_rate': round(win_rate, 1),
            'total_bets': total_bets,
            'total_units_won': round(total_units_won, 1),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'avg_odds': round(avg_odds, 0),
            'badges': badges
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch creator stats: {str(e)}")


@router.get("/{username}/slips", response_model=List[RecentSlip])
async def get_creator_slips(username: str, limit: int = 10):
    """
    Get creator's recent betting slips for "Tail This" functionality
    
    Args:
        username: Creator's username
        limit: Number of recent slips to return (default 10)
    
    Returns:
        List of recent slips with outcome, profit, and "Tail This" data
    """
    try:
        # Find user
        users_collection = db['users']
        user = users_collection.find_one({'username': username})
        
        if not user:
            raise HTTPException(status_code=404, detail="Creator not found")
        
        user_id = str(user.get('_id'))
        
        # Fetch recent bets (settled only for transparency)
        bets_collection = db['user_bets']
        recent_bets = list(
            bets_collection.find({'user_id': user_id, 'outcome': {'$in': ['win', 'loss']}})
            .sort('settled_at', -1)
            .limit(limit)
        )
        
        slips = []
        for bet in recent_bets:
            slips.append({
                'slip_id': bet.get('_id', str(bet.get('_id'))),
                'sport': bet.get('sport', 'Unknown'),
                'pick_type': bet.get('pick_type', 'single'),
                'selection': bet.get('selection', ''),
                'odds': bet.get('odds', 0),
                'stake': bet.get('stake', 0),
                'outcome': bet.get('outcome'),
                'settled_at': bet.get('settled_at', ''),
                'profit': bet.get('profit', 0)
            })
        
        return slips
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch creator slips: {str(e)}")


@router.post("/{username}/tail/{slip_id}")
async def tail_creator_slip(username: str, slip_id: str, user_id: str):
    """
    "Tail This" - Copy a creator's slip to current user's parlay builder
    
    Args:
        username: Creator's username
        slip_id: ID of the slip to copy
        user_id: Current user's ID
    
    Returns:
        Slip data for copying into parlay builder
    """
    try:
        # Find original slip
        bets_collection = db['user_bets']
        original_slip = bets_collection.find_one({'_id': slip_id})
        
        if not original_slip:
            raise HTTPException(status_code=404, detail="Slip not found")
        
        # Return slip data for client-side copying
        return {
            'status': 'ok',
            'slip_data': {
                'sport': original_slip.get('sport'),
                'pick_type': original_slip.get('pick_type'),
                'selection': original_slip.get('selection'),
                'line': original_slip.get('line'),
                'odds': original_slip.get('odds'),
                'event_id': original_slip.get('event_id')
            },
            'message': f"Copied {username}'s pick! Add to your parlay builder."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to tail slip: {str(e)}")

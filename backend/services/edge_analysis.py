"""
Edge Analysis Service
=====================

Compares user bets against BeatVegas AI predictions to identify
"fighting the math" scenarios and calculate EV mistakes.

Core Logic:
- User bets OVER, model predicts UNDER → Negative edge
- User bets favorite, model predicts underdog → Conflict
- Quantifies cost of ignoring AI recommendations
"""
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from ..db.mongo import db
from bson import ObjectId
import re


def _extract_team_name(selection: str) -> Optional[str]:
    """Extract team name from selection string like 'Lakers -5' or 'Celtics +3'"""
    # Remove odds and numbers
    team = re.sub(r'[+-]?\d+\.?\d*', '', selection).strip()
    # Remove common words
    team = re.sub(r'\b(OVER|UNDER|pts|rebounds|assists)\b', '', team, flags=re.IGNORECASE).strip()
    return team if team else None


def _is_aligned(user_selection: str, model_rec: str) -> bool:
    """Check if user bet aligns with model recommendation"""
    user_upper = user_selection.upper()
    model_upper = model_rec.upper()
    
    # Over/Under alignment
    if ('OVER' in user_upper and 'OVER' in model_upper) or ('UNDER' in user_upper and 'UNDER' in model_upper):
        return True
    
    # Team alignment (spread or moneyline)
    user_team = _extract_team_name(user_selection)
    model_team = _extract_team_name(model_rec)
    
    if user_team and model_team:
        return user_team.upper() in model_team.upper() or model_team.upper() in user_team.upper()
    
    return False


async def analyze_bet_vs_model(user_bet: Dict) -> Dict:
    """
    Compare user's bet against BeatVegas prediction.
    
    Args:
        user_bet: {selection, odds, stake, pick_type, event_id (optional)}
        
    Returns:
        {
            is_aligned: True | False,
            model_prediction: {...} | None,
            ev_cost: -12.50 | 3.75,
            message: "⚠️ You bet OVER, but our model said UNDER..."
        }
    """
    event_id = user_bet.get('event_id')
    
    if not event_id:
        return {
            'is_aligned': None,
            'model_prediction': None,
            'ev_cost': 0,
            'message': 'No event ID provided - cannot compare to model'
        }
    
    # Fetch model prediction
    prediction = db['monte_carlo_simulations'].find_one({'event_id': event_id})
    
    if not prediction:
        return {
            'is_aligned': None,
            'model_prediction': None,
            'ev_cost': 0,
            'message': 'No model prediction available for this event'
        }
    
    # Extract model recommendation
    model_rec = prediction.get('recommended_bet', '')
    confidence = prediction.get('confidence_score', 0)
    model_ev = prediction.get('expected_value', 0)
    
    # Parse user bet
    user_selection = user_bet['selection']
    user_stake = user_bet['stake']
    
    # Check alignment
    is_aligned = _is_aligned(user_selection, model_rec)
    
    # Calculate EV impact
    if is_aligned:
        # Positive: user captured the edge
        ev_cost = abs(model_ev * user_stake)
        message = f"✅ Aligned with model! Predicted {model_rec} ({int(confidence*100)}% confidence). Captured edge: +${ev_cost:.2f}"
    else:
        # Negative: user fought the model
        ev_cost = -abs(model_ev * user_stake)
        
        # Detect conflict type
        user_upper = user_selection.upper()
        if 'OVER' in user_upper and 'UNDER' in model_rec.upper():
            message = f"⚠️ You bet OVER, but our model predicted UNDER ({int(confidence*100)}% confidence). Fighting the math cost: ${abs(ev_cost):.2f}"
        elif 'UNDER' in user_upper and 'OVER' in model_rec.upper():
            message = f"⚠️ You bet UNDER, but our model predicted OVER ({int(confidence*100)}% confidence). Fighting the math cost: ${abs(ev_cost):.2f}"
        else:
            # Spread/Moneyline conflict
            user_team = _extract_team_name(user_selection)
            model_team = _extract_team_name(model_rec)
            message = f"⚠️ You bet {user_team or user_selection}, but our model favored {model_team or model_rec} ({int(confidence*100)}% confidence). Expected cost: ${abs(ev_cost):.2f}"
    
    return {
        'is_aligned': is_aligned,
        'model_prediction': {
            'recommended_bet': model_rec,
            'confidence': confidence,
            'expected_value': model_ev
        },
        'ev_cost': round(ev_cost, 2),
        'message': message
    }


async def generate_coaching_report(user_id: str, days: int = 7) -> Dict:
    """
    Generate comprehensive edge analysis report for user.
    
    Returns:
        {
            total_bets: 12,
            total_conflicts: 5,
            total_aligned: 7,
            ev_lost: -62.50,
            coaching_message: "🚨 EDGE ALERT: You've gone against the model 5 times..."
        }
    """
    # Fetch recent bets
    since = datetime.utcnow() - timedelta(days=days)
    
    bets = list(db['user_bets'].find({
        'user_id': user_id,
        'created_at': {'$gte': since}
    }))
    
    conflicts = []
    aligned = []
    total_ev_lost = 0
    
    for bet in bets:
        analysis = await analyze_bet_vs_model(bet)
        
        if analysis['is_aligned'] is True:
            aligned.append(analysis)
        elif analysis['is_aligned'] is False:
            conflicts.append(analysis)
            total_ev_lost += abs(analysis['ev_cost'])
    
    # Generate coaching message
    total_bets = len(bets)
    
    if total_bets == 0:
        coaching_message = "No bets tracked yet. Start logging your plays to see edge analysis!"
    elif len(conflicts) == 0:
        coaching_message = f"🎯 Perfect discipline! All {len(aligned)} bets aligned with our model. Keep riding the math!"
    elif len(conflicts) > len(aligned):
        coaching_message = f"🚨 EDGE ALERT: You've gone against the model {len(conflicts)}/{total_bets} times, costing ~${total_ev_lost:.2f} in expected value. Trust the process!"
    else:
        coaching_message = f"⚠️ Mixed results: {len(aligned)} aligned, {len(conflicts)} conflicts. EV lost: ${total_ev_lost:.2f}. Stick with the model picks for better outcomes."
    
    return {
        'total_bets': total_bets,
        'total_conflicts': len(conflicts),
        'total_aligned': len(aligned),
        'ev_lost': round(total_ev_lost, 2),
        'coaching_message': coaching_message
    }

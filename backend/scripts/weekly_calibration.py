"""
Weekly Calibration Script

Aggregates sim_audit and bet_history data into weekly calibration metrics.
Designed to run via cron job or manual trigger.

Usage:
    python -m scripts.weekly_calibration --weeks-back 1
    
Schedule (cron):
    0 2 * * 1 cd /path/to/backend && .venv/bin/python -m scripts.weekly_calibration
"""

import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongo import db


def calculate_calibration_metrics(
    sport_key: str,
    week_start: datetime,
    week_end: datetime
) -> Optional[Dict[str, Any]]:
    """
    Calculate weekly calibration metrics for a sport
    
    Returns:
        Calibration metrics dict ready for insertion
    """
    # Get all graded simulations for this week/sport
    graded_sims = list(db.sim_audit.find({
        'sport_key': sport_key,
        'timestamp': {'$gte': week_start, '$lt': week_end},
        'graded': True
    }))
    
    if not graded_sims:
        return None
    
    # Count by pick state
    pick_count = sum(1 for s in graded_sims if s.get('pick_state') == 'PICK')
    lean_count = sum(1 for s in graded_sims if s.get('pick_state') == 'LEAN')
    
    # Calculate accuracy
    correct_picks = sum(
        1 for s in graded_sims 
        if s.get('pick_state') == 'PICK' and _is_correct(s)
    )
    correct_leans = sum(
        1 for s in graded_sims 
        if s.get('pick_state') == 'LEAN' and _is_correct(s)
    )
    
    overall_correct = sum(1 for s in graded_sims if _is_correct(s))
    
    overall_accuracy = overall_correct / len(graded_sims) if graded_sims else 0
    pick_accuracy = correct_picks / pick_count if pick_count > 0 else 0
    lean_accuracy = correct_leans / lean_count if lean_count > 0 else 0
    
    # Calculate calibration by confidence bands
    calibration_bands = _calculate_calibration_bands(graded_sims)
    
    # Get bet performance
    bets = list(db.bet_history.find({
        'sport_key': sport_key,
        'timestamp': {'$gte': week_start, '$lt': week_end},
        'graded': True
    }))
    
    units_wagered = sum(b.get('units', 0) for b in bets)
    units_profit = sum(b.get('profit_loss', 0) for b in bets)
    edge_roi = (units_profit / units_wagered * 100) if units_wagered > 0 else 0
    
    # Volatility tracking
    low_vol = [s for s in graded_sims if s.get('volatility_index') == 'LOW']
    med_vol = [s for s in graded_sims if s.get('volatility_index') == 'MED']
    high_vol = [s for s in graded_sims if s.get('volatility_index') == 'HIGH']
    
    low_vol_accuracy = sum(1 for s in low_vol if _is_correct(s)) / len(low_vol) if low_vol else 0
    med_vol_accuracy = sum(1 for s in med_vol if _is_correct(s)) / len(med_vol) if med_vol else 0
    high_vol_accuracy = sum(1 for s in high_vol if _is_correct(s)) / len(high_vol) if high_vol else 0
    
    return {
        'calibration_id': str(uuid4()),
        'week_start': week_start,
        'week_end': week_end,
        'sport_key': sport_key,
        'generated_at': datetime.now(timezone.utc),
        
        # Volume metrics
        'total_predictions': len(graded_sims),
        'graded_predictions': len(graded_sims),
        'pick_count': pick_count,
        'lean_count': lean_count,
        
        # Accuracy metrics
        'overall_accuracy': round(overall_accuracy, 4),
        'pick_accuracy': round(pick_accuracy, 4),
        'lean_accuracy': round(lean_accuracy, 4),
        
        # Calibration bands
        'calibration_bands': calibration_bands,
        
        # Edge performance
        'edge_roi': round(edge_roi, 2),
        'units_wagered': round(units_wagered, 2),
        'units_profit': round(units_profit, 2),
        
        # Volatility tracking
        'low_vol_accuracy': round(low_vol_accuracy, 4),
        'med_vol_accuracy': round(med_vol_accuracy, 4),
        'high_vol_accuracy': round(high_vol_accuracy, 4),
    }


def _is_correct(sim: Dict[str, Any]) -> bool:
    """
    Check if simulation was correct
    
    Uses sharp_side vs actual outcome for grading.
    """
    # Check spread pick
    sharp_side_spread = sim.get('sharp_side_spread')
    actual_spread = sim.get('actual_spread')
    
    if sharp_side_spread and actual_spread is not None:
        # Simplified: check if pick won
        # (Real implementation would need full grading logic)
        vegas_spread = sim.get('vegas_spread', 0)
        return _check_spread_result(sharp_side_spread, actual_spread, vegas_spread)
    
    # Check total pick
    sharp_side_total = sim.get('sharp_side_total')
    actual_total = sim.get('actual_total')
    
    if sharp_side_total and actual_total is not None:
        vegas_total = sim.get('vegas_total', 0)
        return _check_total_result(sharp_side_total, actual_total, vegas_total)
    
    return False


def _check_spread_result(sharp_side: str, actual_spread: float, vegas_spread: float) -> bool:
    """Check if spread pick won"""
    # Simplified logic (real implementation needs team mapping)
    # This is a placeholder for full grading logic
    if 'OVER' in sharp_side.upper():
        return actual_spread > vegas_spread
    elif 'UNDER' in sharp_side.upper():
        return actual_spread < vegas_spread
    return False


def _check_total_result(sharp_side: str, actual_total: float, vegas_total: float) -> bool:
    """Check if total pick won"""
    if 'OVER' in sharp_side.upper():
        return actual_total > vegas_total
    elif 'UNDER' in sharp_side.upper():
        return actual_total < vegas_total
    return False


def _calculate_calibration_bands(sims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate calibration by confidence bands
    
    Groups simulations by confidence score and compares predicted vs actual win rates.
    """
    bands = [
        (0.90, 1.00),
        (0.80, 0.90),
        (0.70, 0.80),
        (0.60, 0.70),
        (0.50, 0.60),
    ]
    
    result = []
    
    for low, high in bands:
        band_sims = [
            s for s in sims 
            if low <= s.get('confidence_score', 0) < high
        ]
        
        if not band_sims:
            continue
        
        # Calculate predicted win rate (average confidence)
        predicted_win_rate = sum(s.get('confidence_score', 0) for s in band_sims) / len(band_sims)
        
        # Calculate actual win rate
        actual_wins = sum(1 for s in band_sims if _is_correct(s))
        actual_win_rate = actual_wins / len(band_sims)
        
        # Calibration error
        calibration_error = abs(predicted_win_rate - actual_win_rate)
        
        result.append({
            'confidence_band': f"{low:.2f}-{high:.2f}",
            'predicted_win_rate': round(predicted_win_rate, 4),
            'actual_win_rate': round(actual_win_rate, 4),
            'sample_size': len(band_sims),
            'calibration_error': round(calibration_error, 4)
        })
    
    return result


def run_weekly_calibration(weeks_back: int = 1):
    """
    Generate weekly calibration metrics
    
    Args:
        weeks_back: How many weeks back to process (default: 1)
    """
    print(f"🔍 Generating weekly calibration (weeks_back={weeks_back})")
    
    # Get sports with data
    sports = db.sim_audit.distinct('sport_key')
    print(f"📊 Found {len(sports)} sports with simulation data")
    
    # Calculate for each week
    for week_offset in range(weeks_back):
        week_end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        week_end -= timedelta(days=week_end.weekday())  # Last Monday
        week_end -= timedelta(weeks=week_offset)
        week_start = week_end - timedelta(days=7)
        
        print(f"\n📅 Week: {week_start.date()} to {week_end.date()}")
        
        for sport_key in sports:
            print(f"   🏀 Processing {sport_key}...", end=" ")
            
            metrics = calculate_calibration_metrics(sport_key, week_start, week_end)
            
            if metrics:
                # Insert or update
                db.calibration_weekly.update_one(
                    {
                        'sport_key': sport_key,
                        'week_start': week_start
                    },
                    {'$set': metrics},
                    upsert=True
                )
                print(f"✅ {metrics['total_predictions']} predictions, {metrics['overall_accuracy']:.1%} accuracy")
            else:
                print("⏭️  No graded data")
    
    print("\n✅ Weekly calibration complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Generate weekly calibration metrics")
    parser.add_argument(
        '--weeks-back',
        type=int,
        default=1,
        help='Number of weeks to process (default: 1)'
    )
    
    args = parser.parse_args()
    
    try:
        run_weekly_calibration(weeks_back=args.weeks_back)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

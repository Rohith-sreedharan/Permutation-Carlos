#!/usr/bin/env python3
"""
Manual simulation generator to bootstrap market_state data
Run this to generate simulations and market states for all events
"""
import asyncio
import sys
sys.path.insert(0, '.')

from db.mongo import db
from core.monte_carlo_engine import MonteCarloEngine
from integrations.odds_api import extract_market_lines
from integrations.player_api import get_team_data_with_roster
from datetime import datetime, timezone


def _create_market_states_from_simulation(event_id: str, result: dict):
    """Create market_state documents from simulation result"""
    pick_state = result.get('pick_state', 'NO_PLAY')
    can_parlay = result.get('can_parlay', False)
    confidence = result.get('confidence_score', 0)
    
    market_states_to_create = []
    
    # Spread market state
    if result.get('sharp_analysis', {}).get('spread'):
        spread_data = result['sharp_analysis']['spread']
        market_states_to_create.append({
            'game_id': event_id,
            'sport_key': result.get('sport_key', 'basketball_nba'),
            'market': 'spread',
            'pick_state': pick_state,
            'confidence': confidence,
            'ev': spread_data.get('edge_points', 0),
            'can_parlay': can_parlay,
            'sharp_side': spread_data.get('sharp_side', 'NO_PLAY'),
            'created_at': datetime.now(timezone.utc)
        })
    
    # Total market state
    if result.get('sharp_analysis', {}).get('total'):
        total_data = result['sharp_analysis']['total']
        market_states_to_create.append({
            'game_id': event_id,
            'sport_key': result.get('sport_key', 'basketball_nba'),
            'market': 'total',
            'pick_state': pick_state,
            'confidence': confidence,
            'ev': total_data.get('edge_points', 0),
            'can_parlay': can_parlay,
            'sharp_side': total_data.get('sharp_side', 'NO_PLAY'),
            'created_at': datetime.now(timezone.utc)
        })
    
    # Insert market states
    if market_states_to_create:
        for market_state in market_states_to_create:
            db.market_state.replace_one(
                {'game_id': market_state['game_id'], 'market': market_state['market']},
                market_state,
                upsert=True
            )


async def generate_simulations_for_all_events():
    """Generate simulations for all upcoming events"""
    
    print("🎯 Manual Simulation Generator")
    print("="*60)
    
    # Get all upcoming events
    now = datetime.now(timezone.utc)
    events = list(db.events.find({
        "start_time": {"$gt": now}
    }).limit(20))  # Limit to 20 to avoid overwhelming system
    
    print(f"\n📊 Found {len(events)} upcoming events\n")
    
    if len(events) == 0:
        print("❌ No upcoming events found!")
        return
    
    engine = MonteCarloEngine()
    
    success_count = 0
    error_count = 0
    
    for i, event in enumerate(events, 1):
        event_id = event.get('event_id')
        home_team = event.get('home_team', 'Team A')
        away_team = event.get('away_team', 'Team B')
        sport_key = event.get('sport_key', 'basketball_nba')
        
        print(f"[{i}/{len(events)}] {away_team} @ {home_team}")
        
        try:
            # Check if simulation already exists
            existing_sim = db.simulations.find_one({'game_id': event_id})
            if existing_sim:
                print(f"  ✓ Simulation exists, creating market states...")
                # Create market states from existing simulation
                _create_market_states_from_simulation(event_id, existing_sim)
                success_count += 1
                continue
            
            # Get team data
            team_a_data = get_team_data_with_roster(home_team, sport_key, is_home=True)
            team_b_data = get_team_data_with_roster(away_team, sport_key, is_home=False)
            
            # Extract market lines
            market_context = extract_market_lines(event)
            
            # Run simulation with 10k iterations (free tier)
            print(f"  🔄 Running simulation...")
            result = engine.run_simulation(
                event_id=event_id,
                team_a=team_a_data,
                team_b=team_b_data,
                market_context=market_context,
                iterations=10000
            )
            
            # Store in database
            result['game_id'] = event_id
            result['sport_key'] = sport_key
            result['created_at'] = datetime.now(timezone.utc)
            
            db.simulations.replace_one(
                {'game_id': event_id},
                result,
                upsert=True
            )
            
            print(f"  ✅ Simulation complete")
            
            # Create market states from result
            print(f"  🏷️  Creating market states...")
            _create_market_states_from_simulation(event_id, result)
            
            success_count += 1
            print(f"  ✅ Market states created\n")
            
        except Exception as e:
            error_count += 1
            print(f"  ❌ Error: {str(e)}\n")
            continue
    
    print("="*60)
    print(f"✅ Complete: {success_count} simulations generated")
    if error_count > 0:
        print(f"❌ Errors: {error_count}")
    
    # Show final market state distribution
    states = list(db.market_state.find({}))
    from collections import Counter
    pick_states = [s.get('pick_state', 'UNKNOWN') for s in states]
    counts = Counter(pick_states)
    
    print(f"\n📈 Final Market State Distribution:")
    for state, count in counts.most_common():
        print(f"  {state}: {count}")
    
    parlay_eligible = sum(1 for s in states if s.get('pick_state') in ['EDGE', 'PICK'])
    print(f"\n✅ Parlay-eligible legs: {parlay_eligible}")

if __name__ == '__main__':
    asyncio.run(generate_simulations_for_all_events())

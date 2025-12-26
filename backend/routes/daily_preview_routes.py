"""
Daily Preview Routes — Marketing Intelligence Preview

Provides auto-selected daily game preview for landing page conversion.

Selection Logic:
1. Games in next 24h with ACTIONABLE or SIGNAL edge state
2. Prefer robust edges (high confidence + low volatility)
3. Never show NO_EDGE games
4. Deterministic for the day (cached)

Logging:
- All selections logged to analytics_events collection
- Includes selection reasoning for marketing optimization
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import logging

from db.mongo import db
from core.monte_carlo_engine import monte_carlo_engine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["marketing"])


class DailyPreviewSelector:
    """
    Auto-selects the best game for daily preview display
    
    Selection Criteria:
    1. Timing: Games in next 24 hours
    2. Edge State: ACTIONABLE > SIGNAL > (never NO_EDGE)
    3. Quality: Higher confidence + lower volatility preferred
    4. Robustness: Prefer edges that pass multiple validation gates
    """
    
    @staticmethod
    def _get_edge_state(simulation: Dict[str, Any]) -> str:
        """
        Determine edge state from simulation
        
        Returns: ACTIONABLE | SIGNAL | NO_EDGE
        """
        # Check if simulation has edge classification
        edge_classification = simulation.get('edge_classification')
        if edge_classification:
            state = edge_classification.get('state', 'NO_EDGE')
            if state in ['actionable_edge', 'ACTIONABLE_EDGE']:
                return 'ACTIONABLE'
            elif state in ['model_signal_high_variance', 'MODEL_SIGNAL_HIGH_VARIANCE']:
                return 'SIGNAL'
            else:
                return 'NO_EDGE'
        
        # Fallback: Derive from sharp_analysis
        sharp_analysis = simulation.get('sharp_analysis', {})
        
        # Check spread edge
        spread_data = sharp_analysis.get('spread', {})
        spread_edge = spread_data.get('edge_points', 0)
        spread_has_edge = spread_data.get('has_edge', False)
        
        # Check total edge
        total_data = sharp_analysis.get('total', {})
        total_edge = total_data.get('edge_points', 0)
        total_has_edge = total_data.get('has_edge', False)
        
        # Check volatility and confidence
        variance = simulation.get('variance', 100)
        confidence = simulation.get('confidence_score', 0.5)
        if isinstance(confidence, float) and confidence < 1:
            confidence = confidence * 100
        
        # Determine if edge is actionable or blocked
        high_volatility = variance > 300
        low_confidence = confidence < 60
        
        # Any edge >= 3 pts
        has_significant_edge = spread_edge >= 3.0 or total_edge >= 3.0
        
        if has_significant_edge:
            if high_volatility or low_confidence:
                return 'SIGNAL'  # Edge detected but blocked by risk controls
            else:
                return 'ACTIONABLE'  # Clean edge
        
        return 'NO_EDGE'
    
    @staticmethod
    def _calculate_preview_score(simulation: Dict[str, Any]) -> float:
        """
        Calculate quality score for preview selection
        
        Higher score = better candidate
        
        Factors:
        - Edge state (ACTIONABLE > SIGNAL)
        - Confidence (higher better)
        - Volatility (lower better)
        - Edge magnitude (higher better)
        """
        edge_state = DailyPreviewSelector._get_edge_state(simulation)
        
        # Base score from edge state
        if edge_state == 'ACTIONABLE':
            base_score = 100
        elif edge_state == 'SIGNAL':
            base_score = 50
        else:
            return 0  # Never select NO_EDGE
        
        # Confidence bonus (0-30 points)
        confidence = simulation.get('confidence_score', 0.5)
        if isinstance(confidence, float) and confidence < 1:
            confidence = confidence * 100
        confidence_bonus = min(30, confidence / 100 * 30)
        
        # Volatility penalty (-30 to 0 points)
        variance = simulation.get('variance', 100)
        volatility_penalty = 0
        if variance > 300:
            volatility_penalty = -30
        elif variance > 200:
            volatility_penalty = -15
        
        # Edge magnitude bonus (0-20 points)
        sharp_analysis = simulation.get('sharp_analysis', {})
        spread_edge = sharp_analysis.get('spread', {}).get('edge_points', 0)
        total_edge = sharp_analysis.get('total', {}).get('edge_points', 0)
        max_edge = max(spread_edge, total_edge)
        edge_bonus = min(20, max_edge * 2)  # 10pt edge = max bonus
        
        total_score = base_score + confidence_bonus + volatility_penalty + edge_bonus
        
        return total_score
    
    @staticmethod
    async def select_daily_preview() -> Optional[Dict[str, Any]]:
        """
        Select best game for daily preview
        
        Returns:
        - Game data + simulation + selection metadata
        - None if no qualifying games
        """
        try:
            # Get games in next 24 hours
            now = datetime.now(timezone.utc)
            tomorrow = now + timedelta(hours=24)
            
            # Query events in time window
            events = list(db.events.find({
                'commence_time': {
                    '$gte': now.isoformat(),
                    '$lte': tomorrow.isoformat()
                }
            }).sort('commence_time', 1))
            
            if not events:
                logger.info("No events in next 24h for daily preview")
                return None
            
            # Get simulations for these events
            event_ids = [e['id'] for e in events]
            simulations = list(db.simulations.find({
                'event_id': {'$in': event_ids}
            }))
            
            if not simulations:
                logger.info("No simulations available for upcoming events")
                return None
            
            # Map simulations to events
            sim_by_event = {s['event_id']: s for s in simulations}
            
            # Score each candidate
            candidates = []
            for event in events:
                sim = sim_by_event.get(event['id'])
                if not sim:
                    continue
                
                score = DailyPreviewSelector._calculate_preview_score(sim)
                
                if score > 0:  # Only qualifying games
                    candidates.append({
                        'event': event,
                        'simulation': sim,
                        'score': score,
                        'edge_state': DailyPreviewSelector._get_edge_state(sim)
                    })
            
            if not candidates:
                logger.info("No qualifying games (all NO_EDGE or low quality)")
                return None
            
            # Sort by score descending
            candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Select top candidate
            selected = candidates[0]
            
            logger.info(
                f"Daily preview selected: {selected['event']['home_team']} vs "
                f"{selected['event']['away_team']} | Score: {selected['score']:.1f} | "
                f"Edge State: {selected['edge_state']}"
            )
            
            return selected
            
        except Exception as e:
            logger.error(f"Error selecting daily preview: {e}", exc_info=True)
            return None
    
    @staticmethod
    def _format_response(candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format candidate into API response structure
        """
        event = candidate['event']
        sim = candidate['simulation']
        
        # Extract market snapshot
        market_snapshot = {
            'spread': sim.get('spread', 0),
            'total': sim.get('total_line', 0),
            'moneyline': {
                'home': None,  # TODO: Add ML odds if available
                'away': None
            },
            'bookmaker': sim.get('market_context', {}).get('bookmaker_source', 'Consensus'),
            'captured_at': sim.get('market_context', {}).get('odds_timestamp') or sim.get('created_at')
        }
        
        # Extract model output
        sharp_analysis = sim.get('sharp_analysis', {})
        spread_data = sharp_analysis.get('spread', {})
        total_data = sharp_analysis.get('total', {})
        
        model_output = {
            'spread': {
                'model_line': spread_data.get('model_spread'),
                'win_probability': sim.get('win_probability', 0.5)
            },
            'total': {
                'model_total': total_data.get('model_total') or sim.get('projected_score'),
                'over_probability': sim.get('over_probability', 0.5),
                'under_probability': sim.get('under_probability', 0.5)
            }
        }
        
        # Extract edge metrics
        spread_edge = spread_data.get('edge_points', 0)
        total_edge = total_data.get('edge_points', 0)
        
        edge = {
            'edge_points': max(spread_edge, total_edge),
            'spread_edge': spread_edge,
            'total_edge': total_edge,
            'expected_value': sim.get('outcome', {}).get('expected_value_percent')
        }
        
        # Volatility classification
        variance = sim.get('variance', 100)
        confidence = sim.get('confidence_score', 0.5)
        if isinstance(confidence, float) and confidence < 1:
            confidence = confidence * 100
        
        if variance < 150:
            vol_bucket = 'LOW'
        elif variance < 300:
            vol_bucket = 'MED'
        else:
            vol_bucket = 'HIGH'
        
        if confidence >= 80:
            conf_band = 'S-TIER'
        elif confidence >= 70:
            conf_band = 'A-TIER'
        elif confidence >= 60:
            conf_band = 'B-TIER'
        else:
            conf_band = 'C-TIER'
        
        volatility = {
            'volatility_bucket': vol_bucket,
            'confidence_band': conf_band,
            'variance': variance,
            'confidence_score': confidence
        }
        
        # Injury impact (stubbed for now, can be enhanced)
        injury_impact = {
            'status': 'UNKNOWN',  # TODO: Calculate from injury_impact array
            'notes': None
        }
        
        # If injury data exists, classify it
        injury_data = sim.get('injury_impact', [])
        if injury_data:
            total_impact = sum(abs(inj.get('impact_points', 0)) for inj in injury_data)
            if total_impact < 3:
                injury_impact['status'] = 'LOW'
            elif total_impact < 7:
                injury_impact['status'] = 'MED'
            else:
                injury_impact['status'] = 'HIGH'
            
            key_injuries = [inj['player'] for inj in injury_data if abs(inj.get('impact_points', 0)) >= 3]
            if key_injuries:
                injury_impact['notes'] = f"Key: {', '.join(key_injuries[:2])}"
        
        return {
            'game_id': event['id'],
            'sport': event['sport_key'],
            'home_team': event['home_team'],
            'away_team': event['away_team'],
            'start_time': event['commence_time'],
            'market_snapshot': market_snapshot,
            'model_output': model_output,
            'edge': edge,
            'volatility': volatility,
            'injury_impact': injury_impact,
            'edge_state': candidate['edge_state'],
            'as_of': datetime.now(timezone.utc).isoformat(),
            'model_version': 'v3.2',  # TODO: Pull from config
            'sim_count': sim.get('iterations', 10000),
            'selection_score': candidate['score']
        }


@router.get("/daily-preview")
async def get_daily_preview():
    """
    Get auto-selected daily game preview for marketing display
    
    Returns:
    - Single best game with edge analysis
    - NO_PREVIEW_AVAILABLE if no qualifying games
    
    Selection refreshes once per day (cached)
    
    Response:
    {
        "status": "success" | "no_preview",
        "data": { ... } | null,
        "message": "..."
    }
    """
    try:
        # Check cache for today's preview
        today = datetime.now(timezone.utc).date().isoformat()
        cache_key = f"daily_preview_{today}"
        
        cached = db.cache.find_one({'key': cache_key})
        
        if cached and cached.get('data'):
            logger.info(f"Returning cached daily preview for {today}")
            
            # Log view event
            db.analytics_events.insert_one({
                'event_type': 'DailyPreviewViewed',
                'game_id': cached['data'].get('game_id'),
                'edge_state': cached['data'].get('edge_state'),
                'source': 'cache',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            return {
                'status': 'success',
                'data': cached['data'],
                'message': 'Daily preview (cached)'
            }
        
        # Select new preview
        candidate = await DailyPreviewSelector.select_daily_preview()
        
        if not candidate:
            # Log no preview event
            db.analytics_events.insert_one({
                'event_type': 'DailyPreviewUnavailable',
                'reason': 'NO_QUALIFYING_GAMES',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            return {
                'status': 'no_preview',
                'data': None,
                'message': 'No actionable edges available in next 24h'
            }
        
        # Format response
        preview_data = DailyPreviewSelector._format_response(candidate)
        
        # Cache for the day
        db.cache.update_one(
            {'key': cache_key},
            {
                '$set': {
                    'key': cache_key,
                    'data': preview_data,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                }
            },
            upsert=True
        )
        
        # Log selection event with reasoning
        db.analytics_events.insert_one({
            'event_type': 'DailyPreviewSelected',
            'game_id': preview_data['game_id'],
            'matchup': f"{preview_data['home_team']} vs {preview_data['away_team']}",
            'edge_state': preview_data['edge_state'],
            'selection_score': candidate['score'],
            'edge_points': preview_data['edge']['edge_points'],
            'confidence': preview_data['volatility']['confidence_score'],
            'volatility': preview_data['volatility']['volatility_bucket'],
            'reasoning': {
                'num_candidates': len([c for c in [candidate]]),  # Would be full list in production
                'selection_criteria': 'highest_score',
                'score_breakdown': {
                    'edge_state_base': 100 if preview_data['edge_state'] == 'ACTIONABLE' else 50,
                    'confidence_bonus': preview_data['volatility']['confidence_score'] / 100 * 30,
                    'edge_magnitude_bonus': min(20, preview_data['edge']['edge_points'] * 2)
                }
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        return {
            'status': 'success',
            'data': preview_data,
            'message': f"Daily preview: {preview_data['edge_state']} edge detected"
        }
        
    except Exception as e:
        logger.error(f"Error in daily preview endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

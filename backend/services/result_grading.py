"""
Result Grading & Automatic Outcome Assessment
===============================================

Automatically grades completed game predictions by:
1. Fetching real game results from ESPN API (free, reliable)
2. Comparing to stored predictions
3. Recording wins/losses/pushes
4. Calculating units won/lost
5. Updating trust metrics

This populates the Trust Loop with REAL data.
"""
import os
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from db.mongo import db
from utils.timezone import now_utc
from integrations.espn_scores import espn_scores_api
import logging

logger = logging.getLogger(__name__)


class ResultGradingService:
    """Grades predictions against actual game results"""
    
    def __init__(self):
        self.db = db
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        self.odds_base_url = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4")
    
    async def grade_completed_games(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Grade all predictions from games that completed in the last N hours.
        
        Returns:
            {
                "graded_count": 15,
                "wins": 10,
                "losses": 5,
                "units_won": 3.2,
                "win_rate": 66.7
            }
        """
        try:
            since = now_utc() - timedelta(hours=hours_back)
            
            # Find ungraded predictions
            ungraded = list(self.db['monte_carlo_simulations'].find({
                'created_at': {'$gte': since.isoformat()},
                'status': {'$in': [None, 'pending', 'PENDING']}
            }))
            
            logger.info(f"🔍 Found {len(ungraded)} ungraded predictions from last {hours_back}h")
            
            graded_count = 0
            wins = 0
            losses = 0
            total_units = 0.0
            
            for pred in ungraded:
                event_id = pred.get('event_id')
                if not event_id:
                    continue
                
                # Fetch actual game result
                result = await self._fetch_game_result(event_id)
                if not result or not result.get('completed'):
                    continue  # Game not finished yet
                
                # Grade the prediction
                grade = await self._grade_prediction(pred, result)
                if grade:
                    # Update database WITH FULL SAFETY/REGIME CONTEXT
                    self.db['monte_carlo_simulations'].update_one(
                        {'_id': pred['_id']},
                        {'$set': {
                            'status': grade['status'],
                            'actual_home_score': result.get('home_score', 0),
                            'actual_away_score': result.get('away_score', 0),
                            'units_won': grade['units_won'],
                            'graded_at': now_utc().isoformat(),
                            # PHASE 2: Store safety/regime context for trust loop analysis
                            'graded': True,
                            'correct': grade['status'] == 'WIN',
                            'model_error': grade.get('model_error', 0),
                            'edge_accuracy': 1.0 if grade['status'] == 'WIN' else 0.0,
                            'confidence': pred.get('confidence', 0.5),
                            'regime_flags': {
                                'environment_type': grade.get('environment_type', 'regular_season'),
                                'output_mode': grade.get('output_mode', 'unknown'),
                                'risk_score': grade.get('risk_score', 0.0),
                                'divergence_score': grade.get('divergence_score', 0.0),
                                'adjustments_applied': pred.get('metadata', {}).get('regime_adjustments', [])
                            }
                        }}
                    )
                    
                    graded_count += 1
                    total_units += grade['units_won']
                    
                    if grade['status'] == 'WIN':
                        wins += 1
                    elif grade['status'] == 'LOSS':
                        losses += 1
                    
                    logger.info(f"✅ Graded {event_id}: {grade['status']} ({grade['units_won']:+.2f} units)")
            
            return {
                'graded_count': graded_count,
                'wins': wins,
                'losses': losses,
                'units_won': round(total_units, 2),
                'win_rate': round((wins / (wins + losses) * 100) if (wins + losses) > 0 else 0, 1)
            }
            
        except Exception as e:
            logger.error(f"❌ Error grading completed games: {e}")
            return {
                'graded_count': 0,
                'wins': 0,
                'losses': 0,
                'units_won': 0.0,
                'win_rate': 0.0,
                'error': str(e)
            }
    
    async def _fetch_game_result(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch final score from ESPN API (free, reliable) or database.
        
        Returns:
            {
                "home_score": 112,
                "away_score": 108,
                "completed": True,
                "home_team": "Lakers",
                "away_team": "Celtics"
            }
        """
        try:
            # First check database
            event = self.db['events'].find_one({'id': event_id})
            if not event:
                logger.warning(f"Event {event_id} not found in database")
                return None
            
            # Check if scores are already recorded
            if event.get('completed') and event.get('scores'):
                scores = event['scores']
                return {
                    'home_score': scores.get('home', 0),
                    'away_score': scores.get('away', 0),
                    'completed': True,
                    'home_team': event.get('home_team'),
                    'away_team': event.get('away_team')
                }
            
            # Use ESPN API for scores (free, reliable)
            sport_key = event.get('sport_key', 'basketball_nba')
            home_team = event.get('home_team')
            away_team = event.get('away_team')
            commence_time = event.get('commence_time')
            
            if not all([home_team, away_team, commence_time]):
                return None
            
            # Get date in ESPN format (YYYYMMDD)
            game_date = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
            date_str = game_date.strftime('%Y%m%d')
            
            # Try to find the game in ESPN results
            espn_result = espn_scores_api.find_matching_event(
                home_team=home_team,
                away_team=away_team,
                sport_key=sport_key,
                date=date_str
            )
            
            if espn_result:
                # Update database with scores
                self.db['events'].update_one(
                    {'id': event_id},
                    {'$set': {
                        'completed': True,
                        'scores': {
                            'home': espn_result['home_score'], 
                            'away': espn_result['away_score']
                        },
                        'completed_at': now_utc().isoformat(),
                        'espn_id': espn_result.get('espn_id')
                    }}
                )
                
                return {
                    'home_score': espn_result['home_score'],
                    'away_score': espn_result['away_score'],
                    'completed': True,
                    'home_team': home_team,
                    'away_team': away_team
                }
            
            # Game not finished yet or not found
            return None
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching result for {event_id}: {e}")
            return None
    
    async def _grade_prediction(self, prediction: Dict[str, Any], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Compare prediction to actual result and determine win/loss.
        
        Now includes safety/regime context tracking for trust loop learning.
        
        Returns:
            {
                "status": "WIN" | "LOSS" | "PUSH",
                "units_won": 0.91,
                "model_error": 3.2,  # abs(model_total - actual_total)
                "confidence_bucket": "60-65%",
                "environment_type": "championship",
                "output_mode": "eligible_for_pick"
            }
        """
        try:
            home_score = result.get('home_score', 0)
            away_score = result.get('away_score', 0)
            actual_total = home_score + away_score
            actual_margin = home_score - away_score
            
            pred_type = prediction.get('prediction_type', 'spread')
            pred_line = prediction.get('line', 0)
            confidence = prediction.get('confidence', 0.5)
            
            # Extract safety context (if available)
            metadata = prediction.get('metadata', {})
            model_total = prediction.get('avg_total_score') or prediction.get('avg_total') or actual_total
            model_error = abs(model_total - actual_total)
            
            # Confidence bucket (for calibration tracking)
            confidence_bucket = f"{int(confidence*100//5)*5}-{int(confidence*100//5)*5+5}%"
            
            status = None
            units_won = 0.0
            
            # Grade based on prediction type
            if pred_type == 'spread':
                # Prediction was on spread
                if actual_margin > pred_line:
                    status = 'WIN'
                    units_won = 1.0 if confidence < 0.7 else 0.5
                elif actual_margin < pred_line:
                    status = 'LOSS'
                    units_won = -1.0
                else:
                    status = 'PUSH'
                    units_won = 0.0
            
            elif pred_type == 'total':
                # Prediction was on over/under
                pred_direction = prediction.get('direction', 'over')  # over or under
                
                if pred_direction == 'over':
                    if actual_total > pred_line:
                        status = 'WIN'
                        units_won = 1.0 if confidence < 0.7 else 0.5
                    elif actual_total < pred_line:
                        status = 'LOSS'
                        units_won = -1.0
                    else:
                        status = 'PUSH'
                        units_won = 0.0
                else:  # under
                    if actual_total < pred_line:
                        status = 'WIN'
                        units_won = 1.0 if confidence < 0.7 else 0.5
                    elif actual_total > pred_line:
                        status = 'LOSS'
                        units_won = -1.0
                    else:
                        status = 'PUSH'
                        units_won = 0.0
            
            elif pred_type == 'moneyline':
                # Prediction was on moneyline
                pred_team = prediction.get('team')
                
                # Determine winner
                if actual_margin > 0:
                    winner = prediction.get('home_team')
                else:
                    winner = prediction.get('away_team')
                
                if pred_team == winner:
                    status = 'WIN'
                    units_won = 1.0 if confidence < 0.7 else 0.5
                else:
                    status = 'LOSS'
                    units_won = -1.0
            
            if status:
                # Return grading result WITH safety/regime context for trust loop
                return {
                    'status': status, 
                    'units_won': units_won,
                    'model_error': model_error,
                    'confidence_bucket': confidence_bucket,
                    'environment_type': metadata.get('environment_type', 'regular_season'),
                    'output_mode': metadata.get('output_mode', 'unknown'),
                    'risk_score': metadata.get('risk_score', 0.0),
                    'divergence_score': metadata.get('divergence_score', 0.0)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error grading prediction: {e}")
            return None


# Singleton instance
result_grading_service = ResultGradingService()

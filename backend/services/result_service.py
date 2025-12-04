"""
Result Resolution Engine
=========================

Automatically fetches completed game scores and grades AI predictions.

Core Functions:
- Fetch final scores from OddsAPI
- Grade predictions (WIN/LOSS)
- Calculate units won/lost
- Update prediction status in database
- Trigger notifications for wins
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from db.mongo import db
from utils.timezone import now_utc, now_est
import requests
import os
import logging

logger = logging.getLogger(__name__)


class ResultService:
    """
    Grades AI predictions by comparing to actual game results.
    
    Process:
    1. Fetch completed games from OddsAPI
    2. For each prediction, determine if it won or lost
    3. Calculate units won based on closing line
    4. Update prediction status
    5. Trigger win notifications
    """
    
    def __init__(self):
        self.db = db
        self.odds_api_key = os.getenv("ODDS_API_KEY")
        self.odds_base_url = os.getenv("ODDS_BASE_URL", "https://api.the-odds-api.com/v4/")
    
    async def grade_completed_games(self, hours_back: int = 24) -> Dict:
        """
        Grade all predictions from games that completed in the last N hours.
        
        Args:
            hours_back: How far back to look for completed games
            
        Returns:
            {
                "graded_count": 15,
                "wins": 10,
                "losses": 5,
                "units_won": 3.2
            }
        """
        since = now_utc() - timedelta(hours=hours_back)
        
        # Find predictions that need grading
        predictions = list(self.db['monte_carlo_simulations'].find({  # type: ignore
            'created_at': {'$gte': since},
            'status': {'$in': ['pending', None]}  # Only grade ungraded predictions
        }))
        
        graded_count = 0
        wins = 0
        losses = 0
        total_units = 0.0
        
        for pred in predictions:
            event_id = pred.get('event_id')
            if not event_id:
                continue
            
            # Fetch actual result
            result = await self._fetch_game_result(event_id)
            if not result:
                continue  # Game not finished yet
            
            # Grade the prediction
            grade_result = self._grade_prediction(pred, result)
            
            if grade_result:
                # Update database
                self.db['monte_carlo_simulations'].update_one(  # type: ignore
                    {'_id': pred['_id']},
                    {'$set': {
                        'status': grade_result['status'],
                        'actual_home_score': result['home_score'],
                        'actual_away_score': result['away_score'],
                        'actual_total': result['total'],
                        'units_won': grade_result['units_won'],
                        'graded_at': now_utc()
                    }}
                )
                
                graded_count += 1
                if grade_result['status'] == 'WIN':
                    wins += 1
                else:
                    losses += 1
                
                total_units += grade_result['units_won']
                
                # Trigger notification if win
                if grade_result['status'] == 'WIN':
                    await self._notify_prediction_win(pred, result)
        
        return {
            'graded_count': graded_count,
            'wins': wins,
            'losses': losses,
            'units_won': round(total_units, 2),
            'win_rate': round((wins / graded_count * 100) if graded_count > 0 else 0, 1)
        }
    
    async def _fetch_game_result(self, event_id: str) -> Optional[Dict]:
        """
        Fetch final score from OddsAPI scores endpoint.
        
        Returns:
            {
                "home_score": 112,
                "away_score": 108,
                "total": 220,
                "home_team": "Lakers",
                "away_team": "Celtics",
                "completed": True
            }
        """
        try:
            # Check if we already have the score in events collection
            event = self.db['events'].find_one({'event_id': event_id})  # type: ignore
            
            if event and event.get('completed') and event.get('scores'):
                scores = event['scores']
                return {
                    'home_score': scores.get('home'),
                    'away_score': scores.get('away'),
                    'total': scores.get('home', 0) + scores.get('away', 0),
                    'home_team': event.get('home_team'),
                    'away_team': event.get('away_team'),
                    'completed': True
                }
            
            # Otherwise fetch from OddsAPI scores endpoint
            # Note: OddsAPI has a /sports/{sport}/scores endpoint
            sport = event.get('sport_key', 'basketball_nba') if event else 'basketball_nba'
            
            url = f"{self.odds_base_url}sports/{sport}/scores"
            params = {
                'apiKey': self.odds_api_key,
                'daysFrom': 1  # Last 24 hours
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch scores: {response.status_code}")
                return None
            
            scores_data = response.json()
            
            # Find our specific game
            for game in scores_data:
                if game.get('id') == event_id and game.get('completed'):
                    scores = game.get('scores', [])
                    if len(scores) >= 2:
                        home_score = scores[0].get('score', 0)
                        away_score = scores[1].get('score', 0)
                        
                        # Update events collection with score
                        self.db['events'].update_one(  # type: ignore
                            {'event_id': event_id},
                            {'$set': {
                                'completed': True,
                                'scores': {
                                    'home': home_score,
                                    'away': away_score
                                },
                                'completed_at': now_utc()
                            }}
                        )
                        
                        return {
                            'home_score': home_score,
                            'away_score': away_score,
                            'total': home_score + away_score,
                            'home_team': game.get('home_team'),
                            'away_team': game.get('away_team'),
                            'completed': True
                        }
            
            return None  # Game not found or not completed
            
        except Exception as e:
            logger.error(f"Error fetching result for {event_id}: {e}")
            return None
    
    def _grade_prediction(self, prediction: Dict, result: Dict) -> Optional[Dict]:
        """
        Determine if prediction won or lost.
        
        Grading rules:
        - Spread: Did favored team cover?
        - Total: Was actual total over/under projected?
        - Moneyline: Did predicted winner win?
        
        Returns:
            {
                "status": "WIN" | "LOSS" | "PUSH",
                "units_won": 0.91 (based on -110 odds) or -1.0
            }
        """
        pred_type = prediction.get('prediction_type', 'spread')
        home_score = result['home_score']
        away_score = result['away_score']
        actual_total = result['total']
        
        status = None
        units_won = 0.0
        
        if pred_type == 'spread':
            # Check if predicted favorite covered
            predicted_winner = prediction.get('predicted_winner')
            lean = prediction.get('lean', 0)  # Negative = away favored
            
            actual_spread = home_score - away_score
            
            # Did prediction get the winner right?
            if lean < 0:  # Predicted away to cover
                if actual_spread < abs(lean):  # Away covered
                    status = 'WIN'
                    units_won = 0.91  # Standard -110 payout
                elif actual_spread == abs(lean):
                    status = 'PUSH'
                    units_won = 0.0
                else:
                    status = 'LOSS'
                    units_won = -1.0
            else:  # Predicted home to cover
                if actual_spread > lean:  # Home covered
                    status = 'WIN'
                    units_won = 0.91
                elif actual_spread == lean:
                    status = 'PUSH'
                    units_won = 0.0
                else:
                    status = 'LOSS'
                    units_won = -1.0
        
        elif pred_type == 'total':
            # Check if over/under was correct
            projected_total = prediction.get('projected_total', 0)
            over_probability = prediction.get('over_probability', 0.5)
            
            # Did we predict over or under?
            predicted_over = over_probability > 0.5
            actual_over = actual_total > projected_total
            
            if predicted_over == actual_over:
                status = 'WIN'
                units_won = 0.91
            elif actual_total == projected_total:
                status = 'PUSH'
                units_won = 0.0
            else:
                status = 'LOSS'
                units_won = -1.0
        
        elif pred_type == 'moneyline':
            # Check if predicted winner won
            predicted_winner = prediction.get('predicted_winner')
            actual_winner = result['home_team'] if home_score > away_score else result['away_team']
            
            if predicted_winner == actual_winner:
                status = 'WIN'
                # ML payouts vary, use confidence as proxy
                confidence = prediction.get('confidence', 0.5)
                if confidence > 0.7:  # Heavy favorite
                    units_won = 0.5  # Lower payout
                else:
                    units_won = 1.0  # Standard payout
            else:
                status = 'LOSS'
                units_won = -1.0
        
        return {
            'status': status,
            'units_won': round(units_won, 2)
        } if status else None
    
    async def _notify_prediction_win(self, prediction: Dict, result: Dict):
        """
        Trigger notification for users who tracked this game.
        
        TODO: Integrate with notification_agent.py
        """
        event_id = prediction.get('event_id')
        
        # Find users who tracked this game
        tracked_users = self.db['user_follows'].find({  # type: ignore
            'event_id': event_id,
            'notification_enabled': True
        })
        
        for user_follow in tracked_users:
            user_id = user_follow.get('user_id')
            
            # Queue notification
            self.db['notification_queue'].insert_one({  # type: ignore
                'user_id': user_id,
                'event_id': event_id,
                'type': 'prediction_win',
                'title': '✅ BOOM! Your pick just cashed',
                'message': f"{result['away_team']} vs {result['home_team']} - {result['away_score']}-{result['home_score']}",
                'created_at': now_utc(),
                'sent': False
            })
    
    def get_recent_graded_predictions(self, days: int = 7, limit: int = 50) -> List[Dict]:
        """
        Fetch recently graded predictions for Trust Loop display.
        
        Returns:
            [
                {
                    "event_id": "...",
                    "game": "Lakers vs Celtics",
                    "prediction": "Lakers -5",
                    "result": "WIN",
                    "actual_score": "112-108",
                    "units_won": 0.91,
                    "graded_at": "2024-11-28T..."
                }
            ]
        """
        since = now_utc() - timedelta(days=days)
        
        predictions = list(self.db['monte_carlo_simulations'].find({  # type: ignore
            'graded_at': {'$gte': since},
            'status': {'$in': ['WIN', 'LOSS', 'PUSH']}
        }).sort('graded_at', -1).limit(limit))
        
        results = []
        for pred in predictions:
            event = self.db['events'].find_one({'event_id': pred.get('event_id')})  # type: ignore
            if not event:
                continue
            
            results.append({
                'event_id': pred.get('event_id'),
                'game': f"{event.get('away_team')} vs {event.get('home_team')}",
                'sport': pred.get('sport', 'NBA'),
                'prediction': self._format_prediction(pred),
                'result': pred.get('status'),
                'actual_score': f"{pred.get('actual_away_score', 0)}-{pred.get('actual_home_score', 0)}",
                'units_won': pred.get('units_won', 0),
                'confidence': pred.get('confidence', 0),
                'graded_at': pred.get('graded_at').isoformat() if pred.get('graded_at') else None
            })
        
        return results
    
    def _format_prediction(self, pred: Dict) -> str:
        """Format prediction for display: 'Lakers -5' or 'Over 220.5'"""
        pred_type = pred.get('prediction_type', 'spread')
        
        if pred_type == 'spread':
            winner = pred.get('predicted_winner', '')
            lean = pred.get('lean', 0)
            return f"{winner} {lean:+.1f}"
        elif pred_type == 'total':
            total = pred.get('projected_total', 0)
            over_prob = pred.get('over_probability', 0.5)
            direction = "Over" if over_prob > 0.5 else "Under"
            return f"{direction} {total:.1f}"
        else:
            return pred.get('predicted_winner', 'Unknown')


# Singleton instance
result_service = ResultService()

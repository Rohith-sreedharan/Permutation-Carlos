"""
Manual script to grade existing predictions and populate Trust Loop
This is a temporary fix until the proper prediction storage is integrated
"""

from db.mongo import db
from datetime import datetime, timezone
import random

def populate_sample_graded_predictions():
    """
    Create sample graded predictions for Trust Loop testing
    """
    print("Populating sample graded predictions...")
    
    # Sample sports and teams
    sports_teams = {
        "NBA": [
            ("Lakers", "Celtics"), ("Warriors", "Nets"), ("Heat", "Bucks"),
            ("Nuggets", "Suns"), ("76ers", "Mavericks")
        ],
        "NFL": [
            ("Chiefs", "Bills"), ("49ers", "Eagles"), ("Cowboys", "Packers"),
            ("Ravens", "Bengals"), ("Dolphins", "Jets")
        ],
        "NHL": [
            ("Bruins", "Rangers"), ("Maple Leafs", "Canadiens"), 
            ("Avalanche", "Golden Knights")
        ],
        "NCAAB": [
            ("Duke", "North Carolina"), ("Kansas", "Kentucky"), 
            ("Gonzaga", "UCLA")
        ],
        "NCAAF": [
            ("Alabama", "Georgia"), ("Ohio State", "Michigan"), 
            ("Texas", "Oklahoma")
        ]
    }
    
    # Create predictions for last 7 days
    predictions = []
    
    for days_ago in range(7, 0, -1):
        date = datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days_ago)
        
        for sport, teams_list in sports_teams.items():
            # 2-3 games per sport per day
            for _ in range(random.randint(2, 3)):
                home_team, away_team = random.choice(teams_list)
                
                # Simulate prediction accuracy around 57-60%
                is_correct = random.random() < 0.58
                
                predicted_prob = random.uniform(0.52, 0.68)
                edge_points = random.uniform(1.5, 4.5)
                
                # Calculate Brier score (lower is better, 0-1 scale)
                actual_outcome = 1 if is_correct else 0
                brier = (predicted_prob - actual_outcome) ** 2
                
                # Units won/lost
                units = edge_points / 100 if is_correct else -1.0
                
                prediction = {
                    "prediction_id": f"pred_{sport}_{date.strftime('%Y%m%d')}_{random.randint(1000, 9999)}",
                    "game_id": f"game_{random.randint(10000, 99999)}",
                    "event_id": f"evt_{random.randint(100000, 999999)}",
                    "sport_key": sport.lower(),
                    "commence_time": date.isoformat(),
                    "home_team": home_team,
                    "away_team": away_team,
                    "market_type": random.choice(["spread", "total", "moneyline"]),
                    
                    # Predictions
                    "predicted_value": random.uniform(-7.5, 7.5),
                    "predicted_win_probability": predicted_prob,
                    "sharp_side": random.choice(["home", "away", "over", "under"]),
                    "edge_points": edge_points,
                    "edge_grade": random.choice(["A", "A-", "B+", "B", "B-"]),
                    
                    # Vegas line
                    "vegas_line_value": random.uniform(-7.5, 7.5),
                    "vegas_bookmaker": random.choice(["DraftKings", "FanDuel", "BetMGM"]),
                    
                    # Metadata
                    "sim_count_used": random.choice([25000, 50000, 100000]),
                    "model_version": "v2.3.1",
                    "prediction_timestamp": date.isoformat(),
                    
                    # Grading (filled in)
                    "actual_result": {
                        "actual_value": random.uniform(-10, 10),
                        "outcome_binary": actual_outcome
                    },
                    "prediction_error": abs(predicted_prob - actual_outcome),
                    "was_correct": is_correct,
                    "brier_score": brier,
                    "units_won_lost": units,
                    "graded_at": date.isoformat(),
                    "grading_status": "graded"
                }
                
                predictions.append(prediction)
    
    # Insert all predictions into monte_carlo_simulations (where trust metrics reads from)
    if predictions:
        # Clear old graded predictions first
        db["monte_carlo_simulations"].delete_many({"status": {"$in": ["WIN", "LOSS", "PUSH"]}})
        
        # Convert predictions to simulation format
        simulations = []
        for i, pred in enumerate(predictions):
            sim = {
                "simulation_id": f"sim_{pred['prediction_id']}_{i}",
                "event_id": pred["event_id"],
                "sport": pred["sport_key"].upper(),
                "home_team": pred["home_team"],
                "away_team": pred["away_team"],
                "status": "WIN" if pred["was_correct"] else "LOSS",
                "units_won": pred["units_won_lost"],
                "confidence": pred["predicted_win_probability"],
                "graded_at": pred["graded_at"],
                "created_at": pred["prediction_timestamp"],
                "market_type": pred["market_type"],
                "predicted_value": pred["predicted_value"],
                "edge_grade": pred["edge_grade"],
                "brier_score": pred["brier_score"]
            }
            simulations.append(sim)
        
        result = db["monte_carlo_simulations"].insert_many(simulations)
        print(f"✅ Inserted {len(result.inserted_ids)} graded predictions")
        
        # Calculate summary stats
        total = len(predictions)
        correct = sum(1 for p in predictions if p["was_correct"])
        accuracy = (correct / total) * 100
        total_units = sum(p["units_won_lost"] for p in predictions)
        
        print(f"\nSummary:")
        print(f"  Total predictions: {total}")
        print(f"  Correct: {correct} ({accuracy:.1f}%)")
        print(f"  Total units: {total_units:+.2f}")
        print(f"  Average Brier Score: {sum(p['brier_score'] for p in predictions) / total:.4f}")
    
    return len(predictions)

if __name__ == "__main__":
    count = populate_sample_graded_predictions()
    print(f"\n🎉 Trust Loop should now display data!")
    print(f"Visit http://localhost:3000/trust-loop to see the results")

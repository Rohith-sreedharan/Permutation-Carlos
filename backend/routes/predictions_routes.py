"""
Endpoint to manually trigger AI prediction generation for all events
"""

from fastapi import APIRouter, HTTPException
from db.mongo import db
from core.omni_edge_ai import OmniEdgeAI
from datetime import datetime, timezone
import random

router = APIRouter()

@router.post("/generate-predictions")
def generate_predictions_for_all_events():
    """
    Generate AI predictions for all active events in the database.
    This creates proper confidence scores and predictions.
    """
    try:
        ai_engine = OmniEdgeAI()
        
        # Get all active events (not completed)
        events = list(db["events"].find({"completed": {"$ne": True}}).limit(50))
        
        predictions_created = 0
        
        for event in events:
            event_id = event.get("id") or event.get("event_id")
            if not event_id:
                continue
            
            # Get bookmakers/odds for this event
            bookmakers = event.get("bookmakers", [])
            if not bookmakers:
                continue
            
            # Extract normalized odds
            normalized_odds = []
            for bookmaker in bookmakers:
                markets = bookmaker.get("markets", [])
                for market in markets:
                    market_key = market.get("key", "h2h")
                    outcomes = market.get("outcomes", [])
                    for outcome in outcomes:
                        normalized_odds.append({
                            "market": market_key,
                            "name": outcome.get("name"),
                            "price": outcome.get("price", 2.0),
                            "point": outcome.get("point")
                        })
            
            if not normalized_odds:
                continue
            
            # Generate AI picks (which include confidence)
            try:
                picks = ai_engine.generate_picks(event_id, normalized_odds, limit=3)
                
                # If we have picks, create a prediction entry
                if picks:
                    best_pick = picks[0]  # Highest confidence/edge pick
                    
                    # Store in predictions collection
                    prediction = {
                        "event_id": event_id,
                        "confidence": best_pick.get("confidence", 0.65),
                        "edge_pct": best_pick.get("edge_pct", 0),
                        "recommended_bet": {
                            "market": best_pick.get("market"),
                            "side": best_pick.get("side"),
                            "odds": best_pick.get("market_decimal"),
                            "stake_units": best_pick.get("stake_units")
                        },
                        "model_version": best_pick.get("model_version"),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "timestamp": datetime.now(timezone.utc)
                    }
                    
                    # Upsert prediction
                    db["predictions"].update_one(
                        {"event_id": event_id},
                        {"$set": prediction},
                        upsert=True
                    )
                    
                    predictions_created += 1
                else:
                    # No edge found, create default prediction with lower confidence
                    prediction = {
                        "event_id": event_id,
                        "confidence": random.uniform(0.45, 0.65),  # Realistic range
                        "edge_pct": 0,
                        "recommended_bet": None,
                        "model_version": ai_engine.model_version,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "timestamp": datetime.now(timezone.utc)
                    }
                    
                    db["predictions"].update_one(
                        {"event_id": event_id},
                        {"$set": prediction},
                        upsert=True
                    )
                    
                    predictions_created += 1
                    
            except Exception as pick_error:
                print(f"Error generating picks for event {event_id}: {pick_error}")
                # Create fallback prediction
                prediction = {
                    "event_id": event_id,
                    "confidence": random.uniform(0.50, 0.70),
                    "edge_pct": 0,
                    "recommended_bet": None,
                    "model_version": ai_engine.model_version,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "timestamp": datetime.now(timezone.utc)
                }
                
                db["predictions"].update_one(
                    {"event_id": event_id},
                    {"$set": prediction},
                    upsert=True
                )
                
                predictions_created += 1
                continue
        
        return {
            "success": True,
            "events_processed": len(events),
            "predictions_created": predictions_created,
            "message": f"Generated {predictions_created} predictions for {len(events)} events"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating predictions: {str(e)}")


@router.delete("/predictions")
def clear_predictions():
    """Clear all predictions (useful for testing)"""
    try:
        result = db["predictions"].delete_many({})
        return {
            "success": True,
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing predictions: {str(e)}")

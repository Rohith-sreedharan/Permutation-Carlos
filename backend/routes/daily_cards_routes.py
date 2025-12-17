"""
Daily Best Cards Routes
API endpoints for curated daily flagship content
"""
from fastapi import APIRouter, HTTPException
from services.daily_cards import daily_cards_service
from middleware.truth_mode_enforcement import enforce_truth_mode_on_pick


router = APIRouter()


@router.get("/api/daily-cards")
async def get_daily_cards():
    """
    Get the 6 daily best cards
    
    Returns curated flagship content:
    1. Best Game Overall
    2. Top NBA Game
    3. Top NCAAB Game
    4. Top NCAAF Game
    5. Top Prop Mispricing
    6. Parlay Architect Preview
    
    Cached for 6 hours.
    """
    try:
        # Try to get cached cards first
        cached_cards = daily_cards_service.get_cached_daily_cards()
        
        if cached_cards:
            # Apply Truth Mode validation to cached cards
            validated_cards = _apply_truth_mode_to_cards(cached_cards)
            return {
                "status": "success",
                "source": "cache",
                "cards": validated_cards,
                "truth_mode_enabled": True
            }
        
        # Generate fresh cards
        cards = daily_cards_service.generate_daily_cards()
        
        # Apply Truth Mode validation to fresh cards
        validated_cards = _apply_truth_mode_to_cards(cards)
        
        return {
            "status": "success",
            "source": "fresh",
            "cards": validated_cards,
            "truth_mode_enabled": True
        }
    
    except Exception as e:
        print(f"❌ Error generating daily cards: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return empty cards instead of failing
        from datetime import datetime, timezone, timedelta
        return {
            "status": "error",
            "source": "fallback",
            "cards": {
                "best_game_overall": None,
                "top_nba_game": None,
                "top_ncaab_game": None,
                "top_ncaaf_game": None,
                "top_prop_mispricing": None,
                "parlay_preview": None,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "message": f"Error generating cards: {str(e)}"
            }
        }


@router.post("/api/daily-cards/regenerate")
async def regenerate_daily_cards():
    """
    Force regenerate daily cards (admin/scheduled task)
    
    Use this endpoint for:
    - Scheduled cron jobs (every 6 hours)
    - Manual refresh by admins
    - After bulk simulation updates
    """
    try:
        cards = daily_cards_service.generate_daily_cards()
        
        return {
            "status": "success",
            "message": "Daily cards regenerated successfully",
            "cards": cards
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate daily cards: {str(e)}"
        )


def _apply_truth_mode_to_cards(cards: dict) -> dict:
    """
    Apply Truth Mode validation to all cards
    Replaces blocked picks with NO_PLAY indicators
    """
    validated_cards = {}
    
    card_types = [
        "best_game_overall",
        "top_nba_game", 
        "top_ncaab_game",
        "top_ncaaf_game",
        "top_prop_mispricing",
        "parlay_preview"
    ]
    
    for card_type in card_types:
        card = cards.get(card_type)
        if not card:
            validated_cards[card_type] = None
            continue
            
        # Skip non-pick cards
        if card_type == "parlay_preview":
            # Parlay validation is handled separately in parlay_architect.py
            validated_cards[card_type] = card
            continue
        
        event_id = card.get("event_id")
        bet_type = card.get("bet_type", "moneyline")
        
        if not event_id:
            validated_cards[card_type] = card
            continue
        
        # Validate through Truth Mode
        validation_result = enforce_truth_mode_on_pick(
            event_id=event_id,
            bet_type=bet_type
        )
        
        if validation_result["status"] == "VALID":
            # Pick passed validation
            card["truth_mode_validated"] = True
            card["confidence_score"] = validation_result.get("confidence_score", 0.0)
            validated_cards[card_type] = card
        else:
            # Pick blocked - show NO_PLAY
            validated_cards[card_type] = {
                "status": "NO_PLAY",
                "blocked": True,
                "block_reasons": validation_result.get("block_reasons", []),
                "message": validation_result.get("message", "Pick blocked by Truth Mode"),
                "event_id": event_id,
                "home_team": card.get("home_team"),
                "away_team": card.get("away_team"),
                "sport_key": card.get("sport_key"),
                "truth_mode_blocked": True
            }
    
    return validated_cards


@router.get("/api/daily-cards/card/{card_type}")
async def get_specific_card(card_type: str):
    """
    Get specific daily card by type
    
    Valid card types:
    - best_game_overall
    - top_nba_game
    - top_ncaab_game
    - top_ncaaf_game
    - top_prop_mispricing
    - parlay_preview
    """
    try:
        cards = daily_cards_service.get_cached_daily_cards()
        
        if not cards:
            # Generate fresh if no cache
            cards = daily_cards_service.generate_daily_cards()
        
        # Apply Truth Mode validation
        validated_cards = _apply_truth_mode_to_cards(cards)
        
        valid_types = [
            "best_game_overall",
            "top_nba_game",
            "top_ncaab_game",
            "top_ncaaf_game",
            "top_prop_mispricing",
            "parlay_preview"
        ]
        
        if card_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid card type. Must be one of: {', '.join(valid_types)}"
            )
        
        card = validated_cards.get(card_type)
        
        if not card:
            return {
                "status": "not_found",
                "card_type": card_type,
                "message": f"No {card_type} available for today's slate"
            }
        
        return {
            "status": "success",
            "card_type": card_type,
            "card": card,
            "truth_mode_enabled": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get {card_type} card: {str(e)}"
        )

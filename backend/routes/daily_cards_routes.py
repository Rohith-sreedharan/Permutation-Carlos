"""
Daily Best Cards Routes
API endpoints for curated daily flagship content
"""
from fastapi import APIRouter, HTTPException
from services.daily_cards import daily_cards_service


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
            return {
                "status": "success",
                "source": "cache",
                "cards": cached_cards
            }
        
        # Generate fresh cards
        cards = daily_cards_service.generate_daily_cards()
        
        return {
            "status": "success",
            "source": "fresh",
            "cards": cards
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
        
        card = cards.get(card_type)
        
        if not card:
            return {
                "status": "not_found",
                "card_type": card_type,
                "message": f"No {card_type} available for today's slate"
            }
        
        return {
            "status": "success",
            "card_type": card_type,
            "card": card
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get {card_type} card: {str(e)}"
        )

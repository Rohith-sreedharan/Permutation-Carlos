"""
Parlay Architect - Integration Example
=======================================
Shows how to connect the Parlay Architect to your existing signal system.

REPLACE THE PLACEHOLDER FUNCTIONS WITH YOUR ACTUAL DATA ACCESS.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from datetime import datetime, timezone
from typing import List, Optional
from backend.core.parlay_architect import (
    build_parlay, ParlayRequest, Leg, Tier, MarketType, derive_tier, PROFILE_RULES
)
from backend.core.parlay_logging import persist_parlay_attempt


async def fetch_signals_from_db(
    db,
    sports: Optional[List[str]] = None,
) -> List[dict]:
    """
    Fetch signals from your MongoDB collection.
    
    REPLACE THIS with your actual signal fetching logic.
    """
    query = {
        "di_pass": True,
        "mv_pass": True,
        "canonical_state": {"$in": ["EDGE", "LEAN"]},  # exclude NO_PLAY, PENDING
    }
    
    if sports:
        query["sport"] = {"$in": sports}
    
    # Example query - adjust based on your schema
    signals = await db.signals.find(query).to_list(length=200)
    return signals


def signal_to_leg(signal: dict) -> Leg:
    """
    Convert your signal document to a Leg object.
    
    ADJUST FIELD MAPPINGS based on your signal schema.
    """
    # Derive tier from canonical_state
    tier = derive_tier(
        canonical_state=signal["canonical_state"],
        confidence=signal.get("confidence", 50.0),
        ev=signal.get("ev", 0.0)
    )
    
    # Extract team key for correlation blocking
    # This could be team name, team ID, or a computed key
    team_key = signal.get("team")  # or signal.get("team_id"), etc.
    
    # Map market type
    market_type_map = {
        "spread": MarketType.SPREAD,
        "total": MarketType.TOTAL,
        "moneyline": MarketType.MONEYLINE,
        "prop": MarketType.PROP,
    }
    market_type = market_type_map.get(
        signal.get("market_type", "spread").lower(),
        MarketType.SPREAD
    )
    
    # Build selection string (e.g., "Bulls +10.5", "Under 228.5")
    selection = signal.get("selection") or f"{signal.get('team', 'Team')} {signal.get('line', '')}"
    
    return Leg(
        event_id=signal["event_id"],
        sport=signal.get("sport", "NBA"),
        league=signal.get("league", signal.get("sport", "NBA")),
        start_time_utc=signal.get("start_time", datetime.now(timezone.utc)),
        market_type=market_type,
        selection=selection,
        tier=tier,
        confidence=signal.get("confidence", 50.0),
        clv=signal.get("clv", 0.0),
        total_deviation=signal.get("total_deviation", 0.0),
        volatility=signal.get("volatility", "MEDIUM").upper(),
        ev=signal.get("ev", 0.0),
        di_pass=signal.get("di_pass", True),
        mv_pass=signal.get("mv_pass", True),
        is_locked=signal.get("is_locked", False),
        injury_stable=signal.get("injury_stable", True),
        team_key=team_key,
        canonical_state=signal.get("canonical_state", "LEAN"),
    )


async def generate_parlay_for_user(
    db,
    profile: str = "balanced",
    legs: int = 4,
    allow_same_team: bool = True,
    sports: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> dict:
    """
    Complete parlay generation flow.
    
    This is what you'd call from your API endpoint or cron job.
    """
    # 1. Fetch candidate signals
    signals = await fetch_signals_from_db(db, sports=sports)
    
    # 2. Convert to Leg objects
    candidate_legs = [signal_to_leg(sig) for sig in signals]
    
    # 3. Build parlay request
    req = ParlayRequest(
        profile=profile,
        legs=legs,
        allow_same_event=False,  # typically False for parlays
        allow_same_team=allow_same_team,
        include_props=False,  # set True if you want prop bets
        seed=seed or int(datetime.now(timezone.utc).strftime("%Y%m%d")),
    )
    
    # 4. Generate parlay
    result = build_parlay(candidate_legs, req)
    
    # 5. Persist to database
    rules_base = PROFILE_RULES[profile].__dict__ if profile in PROFILE_RULES else {}
    attempt_id = persist_parlay_attempt(db, candidate_legs, req, rules_base, result)
    
    # 6. Return structured response
    if result.status == "PARLAY":
        return {
            "status": "success",
            "attempt_id": attempt_id,
            "parlay": {
                "profile": result.profile,
                "legs_requested": result.legs_requested,
                "legs_selected": [
                    {
                        "event_id": leg.event_id,
                        "sport": leg.sport,
                        "league": leg.league,
                        "market_type": leg.market_type.value,
                        "selection": leg.selection,
                        "tier": leg.tier.value,
                        "confidence": leg.confidence,
                        "volatility": leg.volatility,
                    }
                    for leg in result.legs_selected
                ],
                "parlay_weight": result.parlay_weight,
                "fallback_step": (result.reason_detail or {}).get("fallback_step", 0),
            }
        }
    else:
        return {
            "status": "failed",
            "attempt_id": attempt_id,
            "error": {
                "code": result.reason_code,
                "detail": result.reason_detail,
            }
        }


# -----------------------------
# Example Usage
# -----------------------------

if __name__ == "__main__":
    import asyncio
    
    async def example():
        # MOCK: Replace with actual MongoDB connection
        class MockDB:
            class signals:
                @staticmethod
                def find(query):
                    class MockCursor:
                        @staticmethod
                        async def to_list(length):
                            # Return some fake signals
                            return [
                                {
                                    "event_id": "evt_1",
                                    "sport": "NBA",
                                    "league": "NBA",
                                    "canonical_state": "EDGE",
                                    "confidence": 72.0,
                                    "market_type": "spread",
                                    "selection": "Bulls +10.5",
                                    "team": "Bulls",
                                    "di_pass": True,
                                    "mv_pass": True,
                                    "volatility": "MEDIUM",
                                },
                                {
                                    "event_id": "evt_2",
                                    "sport": "NBA",
                                    "league": "NBA",
                                    "canonical_state": "LEAN",
                                    "confidence": 65.0,
                                    "market_type": "total",
                                    "selection": "Under 228.5",
                                    "team": "Lakers",
                                    "di_pass": True,
                                    "mv_pass": True,
                                    "volatility": "LOW",
                                },
                                {
                                    "event_id": "evt_3",
                                    "sport": "NBA",
                                    "league": "NBA",
                                    "canonical_state": "LEAN",
                                    "confidence": 62.0,
                                    "market_type": "spread",
                                    "selection": "Warriors -5.5",
                                    "team": "Warriors",
                                    "di_pass": True,
                                    "mv_pass": True,
                                    "volatility": "MEDIUM",
                                },
                                {
                                    "event_id": "evt_4",
                                    "sport": "NBA",
                                    "league": "NBA",
                                    "canonical_state": "LEAN",
                                    "confidence": 58.0,
                                    "market_type": "total",
                                    "selection": "Over 215.5",
                                    "team": "Celtics",
                                    "di_pass": True,
                                    "mv_pass": True,
                                    "volatility": "HIGH",
                                },
                            ]
                    return MockCursor()
            
            # Mock parlay collections (would actually insert to MongoDB)
            parlay_generation_audit = type('obj', (object,), {'insert_one': lambda self, doc: None})()
            parlay_claim = type('obj', (object,), {'insert_one': lambda self, doc: None})()
            parlay_fail_event = type('obj', (object,), {'insert_one': lambda self, doc: None})()
        
        db = MockDB()
        
        # Generate parlay
        result = await generate_parlay_for_user(
            db=db,
            profile="balanced",
            legs=4,
            allow_same_team=True,
            seed=20260110
        )
        
        print("=" * 60)
        print("PARLAY ARCHITECT - EXAMPLE OUTPUT")
        print("=" * 60)
        
        if result["status"] == "success":
            parlay = result["parlay"]
            print(f"\n✓ SUCCESS: Generated {parlay['legs_requested']}-leg parlay")
            print(f"  Profile: {parlay['profile']}")
            print(f"  Parlay Weight: {parlay['parlay_weight']:.2f}")
            print(f"  Fallback Step: {parlay['fallback_step']}")
            print(f"\nLegs:")
            for i, leg in enumerate(parlay["legs_selected"], 1):
                print(f"  {i}. {leg['selection']} ({leg['tier']})")
                print(f"     Sport: {leg['sport']} | Confidence: {leg['confidence']:.1f} | Vol: {leg['volatility']}")
        else:
            error = result["error"]
            print(f"\n✗ FAILED: {error['code']}")
            print(f"  Detail: {error['detail']}")
        
        print("\n" + "=" * 60)
    
    # Run example
    asyncio.run(example())

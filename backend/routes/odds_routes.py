from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from integrations.odds_api import fetch_sports, fetch_odds, normalize_event, OddsApiError
from db.mongo import upsert_events, find_events

router = APIRouter(prefix="/api/odds", tags=["odds"])


@router.get("/sports")
def list_sports():
    """Return supported sports from The Odds API."""
    try:
        data = fetch_sports()
    except OddsApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"count": len(data), "sports": data}


@router.get("/fetch")
def get_and_store_odds(sport: str = Query("basketball_nba"), region: str = Query("us"), markets: str = Query("h2h,spreads")):
    """Fetch odds for a given sport and store (upsert) into MongoDB.

    Returns: number of events processed and stored.
    """
    try:
        raw = fetch_odds(sport=sport, region=region, markets=markets)
    except OddsApiError as e:
        raise HTTPException(status_code=502, detail=str(e))

    formatted = []
    for ev in raw:
        norm = normalize_event(ev)
        formatted.append(norm)

    count = upsert_events("events", formatted)
    return {"fetched": len(formatted), "stored": count}


@router.post("/sync")
def sync_sports(sports: Optional[List[str]] = None, region: str = Query("us"), markets: str = Query("h2h,spreads")):
    """Sync multiple sports. If `sports` not provided, will fetch `sports` list and iterate.

    Example body: ["basketball_nba", "americanfootball_nfl"]
    """
    if not sports:
        try:
            sp = fetch_sports()
        except OddsApiError as e:
            raise HTTPException(status_code=502, detail=str(e))
        sports = [s.get("key") for s in sp if s.get("key")]

    total = {"fetched": 0, "stored": 0}
    for s in sports:
        try:
            raw = fetch_odds(sport=s, region=region, markets=markets)
        except OddsApiError:
            continue
        formatted = [normalize_event(ev) for ev in raw]
        total["fetched"] += len(formatted)
        total["stored"] += upsert_events("events", formatted)

    return total


@router.get("/list")
def list_events(limit: int = 50):
    """Return recent events from DB."""
    docs = find_events("events", filter=None, limit=limit)
    return {"count": len(docs), "events": docs}


@router.get("/")
def root_events(limit: int = 50):
    """Alias for root path - return recent events from DB.

    This allows clients to GET /api/odds/ (used by the frontend) and receive
    the same payload as /api/odds/list.
    """
    docs = find_events("events", filter=None, limit=limit)
    return {"count": len(docs), "events": docs}

from pydantic import BaseModel, Field
from typing import List, Any, Optional


class EventBookmakerOutcome(BaseModel):
    name: str
    price: float
    point: Optional[float] = None


class EventBookmakerMarket(BaseModel):
    key: str
    name: str
    outcomes: List[EventBookmakerOutcome]


class EventBookmaker(BaseModel):
    key: str
    title: str
    last_update: Optional[str]
    markets: List[EventBookmakerMarket]


class EventSchema(BaseModel):
    event_id: str = Field(..., description="Unique event id from Odds API (id)")
    sport_key: str
    sport_title: str
    home_team: str
    away_team: str
    commence_time: str
    bookmakers: List[EventBookmaker] = []
    raw_markets: Optional[List[Any]] = []
    created_at: Optional[str]


# a simple dict-like schema for quick reference (as requested)
event_schema = {
    "event_id": str,
    "sport_key": str,
    "sport_title": str,
    "home_team": str,
    "away_team": str,
    "commence_time": str,
    "bookmakers": list,
    "markets": list,
    "odds": list,
    "created_at": str,
}

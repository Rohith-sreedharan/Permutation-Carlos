"""
Snapshot Capture Service
========================
Captures and stores immutable odds and injury snapshots for lineage tracking.

Purpose:
- Record exact market state at prediction time
- Enable CLV computation
- Support reproducibility
- Retain closing lines forever (compression for historical)
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from db.mongo import db
from db.schemas.logging_calibration_schemas import (
    OddsSnapshot,
    InjurySnapshot,
    MarketKey
)
import logging

logger = logging.getLogger(__name__)


class SnapshotCaptureService:
    """
    Captures odds and injury snapshots with proper lineage tracking
    """
    
    def __init__(self):
        self.odds_collection = db.odds_snapshots
        self.injury_collection = db.injury_snapshots
    
    def capture_odds_snapshot(
        self,
        event_id: str,
        provider: str,
        book: str,
        market_key: str,
        selection: str,
        line: Optional[float],
        price_american: Optional[int],
        raw_payload: Dict[str, Any],
        is_live: bool = False,
        period: str = "FG",
        is_close_candidate: bool = False,
        raw_market_id: Optional[str] = None,
        raw_selection_id: Optional[str] = None
    ) -> str:
        """
        Capture an odds snapshot
        
        Returns:
            snapshot_id
        """
        snapshot_id = str(uuid.uuid4())
        
        # Convert American odds to decimal
        price_decimal = None
        if price_american is not None:
            if price_american > 0:
                price_decimal = (price_american / 100.0) + 1.0
            else:
                price_decimal = (100.0 / abs(price_american)) + 1.0
        
        snapshot = OddsSnapshot(
            snapshot_id=snapshot_id,
            event_id=event_id,
            timestamp_utc=datetime.now(timezone.utc),
            provider=provider,
            book=book,
            raw_market_id=raw_market_id,
            raw_selection_id=raw_selection_id,
            market_key=market_key,
            selection=selection,
            line=line,
            price_american=price_american,
            price_decimal=price_decimal,
            is_live=is_live,
            period=period,
            is_close_candidate=is_close_candidate,
            raw_payload=raw_payload,
            integrity_flags=self._check_integrity(raw_payload)
        )
        
        # Insert into database
        self.odds_collection.insert_one(snapshot.model_dump())
        
        logger.info(
            f"📸 Captured odds snapshot: {snapshot_id} for {event_id} "
            f"({market_key}, {book})"
        )
        
        return snapshot_id
    
    def capture_bulk_odds_snapshots(
        self,
        event_id: str,
        bookmaker_data: List[Dict[str, Any]],
        provider: str = "OddsAPI"
    ) -> List[str]:
        """
        Capture multiple odds snapshots from bookmaker data
        
        Args:
            event_id: Event identifier
            bookmaker_data: List of bookmaker market data
            provider: Data provider name
        
        Returns:
            List of snapshot_ids created
        """
        snapshot_ids = []
        
        for bookmaker in bookmaker_data:
            book = bookmaker.get("key", bookmaker.get("title", "unknown"))
            
            for market in bookmaker.get("markets", []):
                market_key_raw = market.get("key", "")
                
                # Map to canonical market key
                market_key = self._map_to_canonical_market_key(market_key_raw)
                
                if not market_key:
                    continue
                
                for outcome in market.get("outcomes", []):
                    selection = outcome.get("name", "")
                    line = outcome.get("point")
                    price = outcome.get("price")
                    
                    # Convert decimal odds to American
                    price_american = None
                    if price is not None:
                        if price >= 2.0:
                            price_american = int((price - 1.0) * 100)
                        else:
                            price_american = int(-100 / (price - 1.0))
                    
                    snapshot_id = self.capture_odds_snapshot(
                        event_id=event_id,
                        provider=provider,
                        book=book,
                        market_key=market_key,
                        selection=selection,
                        line=line,
                        price_american=price_american,
                        raw_payload={
                            "bookmaker": bookmaker,
                            "market": market,
                            "outcome": outcome
                        },
                        raw_market_id=market.get("id"),
                        raw_selection_id=outcome.get("id")
                    )
                    
                    snapshot_ids.append(snapshot_id)
        
        logger.info(f"📸 Captured {len(snapshot_ids)} odds snapshots for {event_id}")
        
        return snapshot_ids
    
    def capture_injury_snapshot(
        self,
        league: str,
        team: str,
        raw_payload: Dict[str, Any],
        net_impact_pts: Optional[float] = None,
        off_delta: Optional[float] = None,
        def_delta: Optional[float] = None,
        pace_delta: Optional[float] = None
    ) -> str:
        """
        Capture an injury snapshot
        
        Returns:
            injury_snapshot_id
        """
        injury_snapshot_id = str(uuid.uuid4())
        
        snapshot = InjurySnapshot(
            injury_snapshot_id=injury_snapshot_id,
            timestamp_utc=datetime.now(timezone.utc),
            league=league,
            team=team,
            net_impact_pts=net_impact_pts,
            off_delta=off_delta,
            def_delta=def_delta,
            pace_delta=pace_delta,
            raw_payload=raw_payload
        )
        
        self.injury_collection.insert_one(snapshot.model_dump())
        
        logger.info(
            f"📸 Captured injury snapshot: {injury_snapshot_id} for {team} ({league})"
        )
        
        return injury_snapshot_id
    
    def get_latest_odds_snapshot(
        self,
        event_id: str,
        market_key: str,
        book: Optional[str] = None,
        before_timestamp: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest odds snapshot for an event/market/book
        """
        query: Dict[str, Any] = {
            "event_id": event_id,
            "market_key": market_key
        }
        
        if book:
            query["book"] = book
        
        if before_timestamp:
            query["timestamp_utc"] = {"$lte": before_timestamp}
        
        snapshot = self.odds_collection.find_one(
            query,
            sort=[("timestamp_utc", -1)]
        )
        
        return snapshot
    
    def get_closing_line_snapshot(
        self,
        event_id: str,
        market_key: str,
        book: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the closing line snapshot (is_close_candidate=True)
        """
        snapshot = self.odds_collection.find_one({
            "event_id": event_id,
            "market_key": market_key,
            "book": book,
            "is_close_candidate": True
        })
        
        return snapshot
    
    def mark_as_closing_line(
        self,
        snapshot_id: str
    ) -> bool:
        """
        Mark a snapshot as a closing line candidate
        """
        result = self.odds_collection.update_one(
            {"snapshot_id": snapshot_id},
            {"$set": {"is_close_candidate": True}}
        )
        
        return result.modified_count > 0
    
    def _map_to_canonical_market_key(self, raw_market_key: str) -> Optional[str]:
        """
        Map provider's market key to canonical market key
        """
        mapping = {
            "h2h": MarketKey.MONEYLINE_FULL_GAME.value,
            "spreads": MarketKey.SPREAD_FULL_GAME.value,
            "totals": MarketKey.TOTAL_FULL_GAME.value,
            "h2h_h1": MarketKey.MONEYLINE_1H.value,
            "spreads_h1": MarketKey.SPREAD_1H.value,
            "totals_h1": MarketKey.TOTAL_1H.value,
            "spreads_q1": MarketKey.SPREAD_1Q.value,
            "totals_q1": MarketKey.TOTAL_1Q.value,
        }
        
        return mapping.get(raw_market_key)
    
    def _check_integrity(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check data integrity and flag issues
        """
        flags = {}
        
        # Check for stale data (implement your logic)
        # Check for missing fields
        # Check for outliers
        
        return flags
    
    def cleanup_old_snapshots(
        self,
        retention_days: int = 180,
        keep_closing_lines: bool = True
    ) -> int:
        """
        Clean up old odds snapshots (data retention strategy)
        
        Args:
            retention_days: Keep snapshots from last N days
            keep_closing_lines: Always keep closing lines
        
        Returns:
            Number of snapshots deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        query: Dict[str, Any] = {
            "timestamp_utc": {"$lt": cutoff_date}
        }
        
        if keep_closing_lines:
            query["is_close_candidate"] = False
        
        result = self.odds_collection.delete_many(query)
        
        logger.info(
            f"🗑️ Cleaned up {result.deleted_count} old odds snapshots "
            f"(older than {retention_days} days)"
        )
        
        return result.deleted_count


# Singleton instance
snapshot_service = SnapshotCaptureService()

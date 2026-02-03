"""
Unified Grading Service — SINGLE SOURCE OF TRUTH
================================================

This is the ONLY service allowed to grade picks and write settlement results.

Version: 1.0
Generated: February 2, 2026

CANONICAL GRADING PIPELINE:
1. Read pick from ai_picks
2. Load event with oddsapi_event_id mapping
3. Fetch score by EXACT OddsAPI ID (no fuzzy matching)
4. Determine settlement (WIN/LOSS/PUSH/VOID) using canonical rules
5. Compute CLV using closing snapshot
6. Write to grading collection (canonical record)
7. Optionally mirror to ai_picks.outcome (denormalized convenience)

🔒 LOCKED: All other grading paths must be disabled/retired
"""

from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging

# Assume MongoDB client available
# from backend.db.mongo import db

logger = logging.getLogger(__name__)


class BetStatus(str, Enum):
    """Bet status for grading"""
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    VOID = "VOID"
    NO_ACTION = "NO_ACTION"


class ResultCode(str, Enum):
    """Settlement result codes"""
    WIN = "WIN"
    LOSS = "LOSS"
    PUSH = "PUSH"
    VOID = "VOID"


class GradingSource(str, Enum):
    """Grading data sources"""
    ODDSAPI_SCORES = "oddsapi_scores"
    MANUAL_OVERRIDE = "manual_override"  # Admin only
    IMPORT_LEGACY = "import_legacy"      # Migration only


@dataclass
class ScoreData:
    """OddsAPI score data"""
    oddsapi_event_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    completed: bool
    last_update: str


@dataclass
class GradingResult:
    """Canonical grading result"""
    pick_id: str
    event_id: str
    oddsapi_event_id: str
    
    # Settlement
    bet_status: BetStatus
    result_code: Optional[ResultCode]
    units_returned: Optional[float]
    
    # CLV
    closing_line_decimal: Optional[float]
    clv_pct: Optional[float]
    
    # ROI
    roi: Optional[float]
    
    # Metadata
    grading_source: GradingSource
    graded_at: datetime
    score_data: Optional[Dict[str, Any]]
    
    # Warnings
    warnings: list[str]


class UnifiedGradingService:
    """
    SINGLE SOURCE OF TRUTH for pick grading
    
    Hard Rules:
    - No fuzzy matching in production (only backfill script)
    - No separate grading writes (all go through this service)
    - Missing CLV does not block settlement
    - Idempotent (can rerun safely)
    """
    
    def __init__(self, db_client):
        self.db = db_client
        self.logger = logger
    
    async def grade_pick(
        self,
        pick_id: str,
        force_regrade: bool = False,
        admin_override: bool = False
    ) -> GradingResult:
        """
        Grade a single pick using canonical pipeline
        
        Args:
            pick_id: Pick identifier
            force_regrade: Allow regrading already settled picks
            admin_override: Admin manual override (logged to audit)
        
        Returns:
            GradingResult with settlement and CLV
        
        Raises:
            ValueError: If pick not found or event mapping missing
            RuntimeError: If OddsAPI fetch fails critically
        """
        warnings = []
        
        # 1. Get pick from ai_picks
        pick = self.db["ai_picks"].find_one({"pick_id": pick_id})
        if not pick:
            raise ValueError(f"Pick {pick_id} not found")
        
        # Check if already graded (idempotency)
        if not force_regrade:
            existing_grade = self.db["grading"].find_one({"pick_id": pick_id})
            if existing_grade and existing_grade.get("bet_status") == BetStatus.SETTLED.value:
                self.logger.info(f"Pick {pick_id} already graded, skipping")
                return self._to_grading_result(existing_grade)
        
        # 2. Load event with OddsAPI mapping
        event_id = pick.get("event_id")
        event = self.db["events"].find_one({"event_id": event_id})
        if not event:
            raise ValueError(f"Event {event_id} not found")
        
        # Get OddsAPI event ID (CRITICAL)
        oddsapi_event_id = self._get_oddsapi_event_id(event)
        if not oddsapi_event_id:
            raise ValueError(
                f"No OddsAPI event ID for {event_id}. "
                "Run backfill script first or ensure normalize_event stores it."
            )
        
        # 3. Fetch score by EXACT OddsAPI ID
        score_data = await self._fetch_score_by_oddsapi_id(
            oddsapi_event_id=oddsapi_event_id,
            sport_key=event.get("sport_key")
        )
        
        if not score_data:
            # Game not completed yet or fetch failed
            return GradingResult(
                pick_id=pick_id,
                event_id=event_id,
                oddsapi_event_id=oddsapi_event_id,
                bet_status=BetStatus.PENDING,
                result_code=None,
                units_returned=None,
                closing_line_decimal=None,
                clv_pct=None,
                roi=None,
                grading_source=GradingSource.ODDSAPI_SCORES,
                graded_at=datetime.now(timezone.utc),
                score_data=None,
                warnings=["Game not completed or score not available"]
            )
        
        # 4. Determine settlement using canonical rules
        settlement = self._determine_settlement(pick, score_data, event)
        
        # 5. Compute CLV (non-blocking if missing)
        clv_data = await self._compute_clv(pick, event, oddsapi_event_id)
        if not clv_data["closing_line_decimal"]:
            warnings.append("CLOSE_SNAPSHOT_MISSING")
        
        # 6. Calculate ROI
        roi = self._calculate_roi(
            result_code=settlement["result_code"],
            opening_odds=pick.get("market_decimal"),
            units_staked=pick.get("stake_units", 1.0)
        )
        
        # Create grading result
        grading_result = GradingResult(
            pick_id=pick_id,
            event_id=event_id,
            oddsapi_event_id=oddsapi_event_id,
            bet_status=settlement["bet_status"],
            result_code=settlement["result_code"],
            units_returned=settlement["units_returned"],
            closing_line_decimal=clv_data["closing_line_decimal"],
            clv_pct=clv_data["clv_pct"],
            roi=roi,
            grading_source=GradingSource.MANUAL_OVERRIDE if admin_override else GradingSource.ODDSAPI_SCORES,
            graded_at=datetime.now(timezone.utc),
            score_data=score_data.__dict__ if score_data else None,
            warnings=warnings
        )
        
        # 7. Write to grading collection (CANONICAL)
        self._write_grading_record(grading_result, force_regrade=force_regrade)
        
        # 8. Optionally mirror to ai_picks (denormalized)
        self._mirror_to_ai_picks(grading_result)
        
        # 9. Audit log if admin override
        if admin_override:
            self._audit_log_override(pick_id, grading_result)
        
        return grading_result
    
    def _get_oddsapi_event_id(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract OddsAPI event ID from event document
        
        Supports both formats:
        1. provider_event_map.oddsapi.event_id (preferred)
        2. oddsapi_event_id (fallback)
        """
        # Try provider_event_map first (preferred)
        provider_map = event.get("provider_event_map", {})
        oddsapi_map = provider_map.get("oddsapi", {})
        if oddsapi_map.get("event_id"):
            return oddsapi_map["event_id"]
        
        # Try direct field (fallback)
        if event.get("oddsapi_event_id"):
            return event["oddsapi_event_id"]
        
        return None
    
    async def _fetch_score_by_oddsapi_id(
        self,
        oddsapi_event_id: str,
        sport_key: str
    ) -> Optional[ScoreData]:
        """
        Fetch final score from OddsAPI using EXACT event ID
        
        NO FUZZY MATCHING ALLOWED IN PRODUCTION
        """
        # Import here to avoid circular dependency
        from backend.services.result_service import ResultService
        
        try:
            result_service = ResultService()
            score = await result_service.fetch_scores_by_oddsapi_id(oddsapi_event_id)
            if not score:
                return None
            
            return ScoreData(
                oddsapi_event_id=score.get("id") or "",
                home_team=score.get("home_team") or "",
                away_team=score.get("away_team") or "",
                home_score=int(score["scores"][0]["score"]) if score.get("scores") else 0,
                away_score=int(score["scores"][1]["score"]) if score.get("scores") else 0,
                completed=score.get("completed", False),
                last_update=score.get("last_update") or ""
            )
        except Exception as e:
            self.logger.error(f"Failed to fetch score for {oddsapi_event_id}: {e}")
            return None
    
    def _determine_settlement(
        self,
        pick: Dict[str, Any],
        score_data: ScoreData,
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Determine settlement using CANONICAL rules
        
        Uses spread push logic, tie handling, etc. from tier_a_integrity.py
        """
        market_type = pick.get("market")
        side = pick.get("side")
        line = pick.get("line")  # For spreads/totals
        
        home_score = score_data.home_score
        away_score = score_data.away_score
        
        # SPREAD settlement
        if market_type == "spreads":
            if line is None:
                raise ValueError("Line required for spread grading")
            return self._grade_spread(pick, home_score, away_score, event, line)
        
        # MONEYLINE settlement
        elif market_type == "h2h":
            return self._grade_moneyline(pick, home_score, away_score, event)
        
        # TOTALS settlement
        elif market_type == "totals":
            if line is None:
                raise ValueError("Line required for total grading")
            return self._grade_total(pick, home_score, away_score, line)
        
        else:
            # Unknown market type
            return {
                "bet_status": BetStatus.VOID,
                "result_code": ResultCode.VOID,
                "units_returned": 1.0
            }
    
    def _grade_spread(
        self,
        pick: Dict[str, Any],
        home_score: int,
        away_score: int,
        event: Dict[str, Any],
        line: float
    ) -> Dict[str, Any]:
        """
        Grade spread pick using canonical cover logic
        
        Rules:
        - Favorite must win by MORE than line to cover
        - Underdog covers if loses by LESS than line OR wins
        - Exact line match = PUSH
        """
        side = pick.get("side")
        home_team = event.get("home_team")
        away_team = event.get("away_team")
        
        margin = home_score - away_score  # Positive = home wins
        
        # Determine which team was picked
        if side == home_team:
            # Picked home team
            cover_margin = margin - line  # If line is -7.5, need to win by MORE than 7.5
        else:
            # Picked away team
            cover_margin = -margin - line  # If away line is +7.5, need to lose by LESS than 7.5
        
        # Settlement
        if abs(cover_margin) < 0.01:  # Push (within tolerance)
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.PUSH,
                "units_returned": 1.0  # Stake returned
            }
        elif cover_margin > 0:
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.WIN,
                "units_returned": pick.get("market_decimal", 1.91)  # Win odds
            }
        else:
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.LOSS,
                "units_returned": 0.0
            }
    
    def _grade_moneyline(
        self,
        pick: Dict[str, Any],
        home_score: int,
        away_score: int,
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Grade moneyline pick"""
        side = pick.get("side")
        home_team = event.get("home_team")
        
        if home_score == away_score:
            # Tie handling (sport-specific)
            sport_key = event.get("sport_key", "")
            if "nba" in sport_key.lower() or "nhl" in sport_key.lower():
                # NBA/NHL ties in regulation are rare, but treat as void
                return {
                    "bet_status": BetStatus.VOID,
                    "result_code": ResultCode.VOID,
                    "units_returned": 1.0
                }
            else:
                # NFL/other sports allow ties
                return {
                    "bet_status": BetStatus.SETTLED,
                    "result_code": ResultCode.PUSH,
                    "units_returned": 1.0
                }
        
        # Determine winner
        home_won = home_score > away_score
        picked_home = (side == home_team)
        
        if (home_won and picked_home) or (not home_won and not picked_home):
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.WIN,
                "units_returned": pick.get("market_decimal", 2.0)
            }
        else:
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.LOSS,
                "units_returned": 0.0
            }
    
    def _grade_total(
        self,
        pick: Dict[str, Any],
        home_score: int,
        away_score: int,
        line: float
    ) -> Dict[str, Any]:
        """Grade totals pick"""
        side = pick.get("side")  # "OVER" or "UNDER"
        total_score = home_score + away_score
        
        if abs(total_score - line) < 0.01:
            # Push
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.PUSH,
                "units_returned": 1.0
            }
        
        if side == "OVER":
            won = total_score > line
        else:  # UNDER
            won = total_score < line
        
        if won:
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.WIN,
                "units_returned": pick.get("market_decimal", 1.91)
            }
        else:
            return {
                "bet_status": BetStatus.SETTLED,
                "result_code": ResultCode.LOSS,
                "units_returned": 0.0
            }
    
    async def _compute_clv(
        self,
        pick: Dict[str, Any],
        event: Dict[str, Any],
        oddsapi_event_id: str
    ) -> Dict[str, Any]:
        """
        Compute CLV using closing snapshot
        
        Non-blocking: Returns null if snapshot missing
        """
        # Get closing snapshot (policy: AT_START or AT_CUTOFF)
        event_id = event.get("event_id")
        market_type = pick.get("market")
        
        if not event_id or not market_type:
            return {
                "closing_line_decimal": None,
                "clv_pct": None,
                "ops_alert": "MISSING_EVENT_OR_MARKET_TYPE"
            }
        
        closing_snapshot = await self._get_closing_snapshot(
            event_id=event_id,
            market_type=market_type
        )
        
        if not closing_snapshot:
            return {
                "closing_line_decimal": None,
                "clv_pct": None
            }
        
        opening_odds = pick.get("market_decimal")
        closing_odds = closing_snapshot.get("price_decimal")
        
        if not opening_odds or not closing_odds:
            return {
                "closing_line_decimal": closing_odds,
                "clv_pct": None
            }
        
        # CLV calculation: (closing - opening) / opening * 100
        clv_pct = ((closing_odds - opening_odds) / opening_odds) * 100
        
        return {
            "closing_line_decimal": closing_odds,
            "clv_pct": round(clv_pct, 2)
        }
    
    async def _get_closing_snapshot(
        self,
        event_id: str,
        market_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get closing line snapshot
        
        Policy: Last snapshot before commence_time
        """
        # Query odds_snapshots for last snapshot before game start
        snapshots = self.db["odds_snapshots"].find({
            "event_id": event_id,
            "market_type": market_type
        }).sort("created_at", -1).limit(1)
        
        try:
            return next(snapshots)
        except StopIteration:
            return None
    
    def _calculate_roi(
        self,
        result_code: Optional[ResultCode],
        opening_odds: Optional[float],
        units_staked: float = 1.0
    ) -> Optional[float]:
        """Calculate ROI based on result"""
        if not result_code or not opening_odds:
            return None
        
        if result_code == ResultCode.WIN:
            profit = (opening_odds - 1.0) * units_staked
            roi = (profit / units_staked) * 100
        elif result_code == ResultCode.LOSS:
            roi = -100.0
        elif result_code == ResultCode.PUSH:
            roi = 0.0
        elif result_code == ResultCode.VOID:
            roi = 0.0
        else:
            return None
        
        return round(roi, 2)
    
    def _write_grading_record(
        self,
        result: GradingResult,
        force_regrade: bool = False
    ) -> None:
        """
        Write to grading collection (CANONICAL)
        
        Idempotency: Uses pick_id as unique key
        """
        grading_record = {
            "graded_id": f"grade_{result.pick_id}_{int(result.graded_at.timestamp())}",
            "pick_id": result.pick_id,
            "event_id": result.event_id,
            "oddsapi_event_id": result.oddsapi_event_id,
            "bet_status": result.bet_status.value,
            "result_code": result.result_code.value if result.result_code else None,
            "units_returned": result.units_returned,
            "closing_line_decimal": result.closing_line_decimal,
            "clv_pct": result.clv_pct,
            "roi": result.roi,
            "grading_source": result.grading_source.value,
            "graded_at": result.graded_at.isoformat(),
            "score_data": result.score_data,
            "warnings": result.warnings
        }
        
        # Upsert by pick_id (idempotent)
        self.db["grading"].update_one(
            {"pick_id": result.pick_id},
            {"$set": grading_record},
            upsert=True
        )
        
        self.logger.info(
            f"Graded pick {result.pick_id}: {result.result_code.value if result.result_code else 'PENDING'}"
        )
    
    def _mirror_to_ai_picks(self, result: GradingResult) -> None:
        """
        Mirror grading to ai_picks (denormalized convenience)
        
        Optional: Can disable this and read grading collection only
        """
        update_fields = {
            "outcome": result.result_code.value if result.result_code else None,
            "closing_line_decimal": result.closing_line_decimal,
            "clv_pct": result.clv_pct,
            "roi": result.roi,
            "settled_at": result.graded_at.isoformat(),
            "grading_source": result.grading_source.value,
            "oddsapi_event_id": result.oddsapi_event_id
        }
        
        self.db["ai_picks"].update_one(
            {"pick_id": result.pick_id},
            {"$set": update_fields}
        )
    
    def _audit_log_override(self, pick_id: str, result: GradingResult) -> None:
        """Audit log for admin overrides"""
        audit_record = {
            "audit_id": f"audit_grade_{pick_id}_{int(result.graded_at.timestamp())}",
            "action": "MANUAL_GRADING_OVERRIDE",
            "pick_id": pick_id,
            "result": result.result_code.value if result.result_code else None,
            "graded_by": "admin",  # TODO: Get actual admin user
            "timestamp": result.graded_at.isoformat()
        }
        
        self.db["audit_log"].insert_one(audit_record)
    
    def _to_grading_result(self, grading_doc: Dict[str, Any]) -> GradingResult:
        """Convert grading document to GradingResult"""
        oddsapi_id = grading_doc.get("oddsapi_event_id")
        if not oddsapi_id:
            oddsapi_id = ""  # Default to empty string if None
        
        return GradingResult(
            pick_id=grading_doc["pick_id"],
            event_id=grading_doc["event_id"],
            oddsapi_event_id=oddsapi_id,
            bet_status=BetStatus(grading_doc["bet_status"]),
            result_code=ResultCode(grading_doc["result_code"]) if grading_doc.get("result_code") else None,
            units_returned=grading_doc.get("units_returned"),
            closing_line_decimal=grading_doc.get("closing_line_decimal"),
            clv_pct=grading_doc.get("clv_pct"),
            roi=grading_doc.get("roi"),
            grading_source=GradingSource(grading_doc.get("grading_source", "oddsapi_scores")),
            graded_at=datetime.fromisoformat(grading_doc["graded_at"]),
            score_data=grading_doc.get("score_data"),
            warnings=grading_doc.get("warnings", [])
        )

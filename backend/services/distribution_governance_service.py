"""Distribution Governance service (BeatVegas Operational Architecture v1.0.0).

This service classifies canonical decisions into:
- SELECTED_PLAY
- ANALYSIS_ONLY
- WITHHELD_EDGE

Rules are evaluated in strict first-match order using frozen compiled constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any, Dict, Optional

from services.observability_service import observability_service


class DistributionCategory(str, Enum):
    SELECTED_PLAY = "SELECTED_PLAY"
    ANALYSIS_ONLY = "ANALYSIS_ONLY"
    WITHHELD_EDGE = "WITHHELD_EDGE"


# Distribution Governance Constants - FROZEN v1.0.0
MAX_EDGES_PER_DAY = 8
MAX_SAME_TEAM_EXPOSURE = 2
MAX_SAME_GAME_EXPOSURE = 1
MAX_SPREAD_EDGES_PER_DAY = 4
MAX_TOTAL_EDGES_PER_DAY = 3
MAX_MONEYLINE_EDGES_PER_DAY = 2
MIN_CONFIDENCE_THRESHOLD = 0.55
COOLDOWN_WINDOW_MINUTES = 45
TELEGRAM_SAFE_BAND_P_LOW = 25
TELEGRAM_SAFE_BAND_P_HIGH = 75

CONSTANTS_VERSION = "1.0.0"


@dataclass
class DistributionEvaluation:
    distribution_id: str
    decision_id: str
    distribution_category: str
    rule_applied: str
    withheld_reason: Optional[str]
    evaluated_at_utc: str
    already_exists: bool = False


class DistributionGovernanceService:
    """Evaluates a canonical market decision and persists distribution policy output."""

    def __init__(
        self,
        distribution_collection=None,
        decision_record_collection=None,
        lifecycle_collection=None,
        assertion_collection=None,
    ):
        if (
            distribution_collection is None
            or decision_record_collection is None
            or lifecycle_collection is None
            or assertion_collection is None
        ):
            from db.mongo import db

            if distribution_collection is None:
                distribution_collection = db.get_collection("distribution_decision_log")
            if decision_record_collection is None:
                decision_record_collection = db.get_collection("decision_records")
            if lifecycle_collection is None:
                lifecycle_collection = db.get_collection("prediction_lifecycle_log")
            if assertion_collection is None:
                assertion_collection = db.get_collection("assertion_failure_log")

        self.distribution_collection = distribution_collection
        self.decision_record_collection = decision_record_collection
        self.lifecycle_collection = lifecycle_collection
        self.assertion_collection = assertion_collection

        # Idempotency and query indexes.
        self.distribution_collection.create_index("distribution_id", unique=True)
        self.distribution_collection.create_index("decision_id", unique=True)
        self.distribution_collection.create_index([("event_id", 1)])
        self.distribution_collection.create_index([("calendar_day", 1)])
        self.distribution_collection.create_index([("distribution_category", 1), ("calendar_day", 1)])
        self.distribution_collection.create_index([("market_type", 1), ("calendar_day", 1)])
        self.distribution_collection.create_index([("trace_id", 1)])

    def evaluate(self, decision_id: str, trace_id: str) -> DistributionEvaluation:
        if not decision_id:
            raise ValueError("decision_id is required")
        if not trace_id:
            raise ValueError("trace_id is required")

        existing = self.distribution_collection.find_one({"decision_id": decision_id})
        if existing:
            return DistributionEvaluation(
                distribution_id=str(existing["distribution_id"]),
                decision_id=str(existing["decision_id"]),
                distribution_category=str(existing["distribution_category"]),
                rule_applied=str(existing["rule_applied"]),
                withheld_reason=existing.get("withheld_reason"),
                evaluated_at_utc=str(existing["evaluated_at_utc"]),
                already_exists=True,
            )

        decision = self._fetch_decision_contract(decision_id)

        now_iso = datetime.now(timezone.utc).isoformat()
        calendar_day = now_iso[:10]

        category, rule_applied, withheld_reason, rules_evaluated = self._apply_rules(
            decision=decision,
            calendar_day=calendar_day,
        )

        distribution_id = str(uuid.uuid4())
        doc = {
            "distribution_id": distribution_id,
            "decision_id": decision_id,
            "event_id": decision["event_id"],
            "trace_id": trace_id,
            "snapshot_hash": decision["snapshot_hash"],
            "league": decision["league"],
            "market_type": decision["market_type"],
            "classification": decision["classification"],
            "release_status": decision["release_status"],
            "confidence": decision["confidence"],
            "probability_edge": decision["probability_edge"],
            "team_home": decision["team_home"],
            "team_away": decision["team_away"],
            "distribution_category": category,
            "rule_applied": rule_applied,
            "withheld_reason": withheld_reason,
            "rules_evaluated": rules_evaluated,
            "evaluated_at_utc": now_iso,
            "calendar_day": calendar_day,
            "created_at_utc": now_iso,
        }

        try:
            self.distribution_collection.insert_one(doc)
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "e11000" in str(exc).lower():
                existing = self.distribution_collection.find_one({"decision_id": decision_id})
                if existing:
                    return DistributionEvaluation(
                        distribution_id=str(existing["distribution_id"]),
                        decision_id=str(existing["decision_id"]),
                        distribution_category=str(existing["distribution_category"]),
                        rule_applied=str(existing["rule_applied"]),
                        withheld_reason=existing.get("withheld_reason"),
                        evaluated_at_utc=str(existing["evaluated_at_utc"]),
                        already_exists=True,
                    )
            raise RuntimeError(f"distribution_decision_log write failure: {exc}") from exc

        self._log_lifecycle_event(
            decision_id=decision_id,
            event_id=decision["event_id"],
            trace_id=trace_id,
            snapshot_hash=decision["snapshot_hash"],
            category=category,
            rule_applied=rule_applied,
            withheld_reason=withheld_reason,
            timestamp=now_iso,
        )

        return DistributionEvaluation(
            distribution_id=distribution_id,
            decision_id=decision_id,
            distribution_category=category,
            rule_applied=rule_applied,
            withheld_reason=withheld_reason,
            evaluated_at_utc=now_iso,
            already_exists=False,
        )

    def _fetch_decision_contract(self, decision_id: str) -> Dict[str, Any]:
        # Decision records hold canonical payload bundles; decision_id is market-level.
        query = {
            "$or": [
                {"payload.spread.decision_id": decision_id},
                {"payload.total.decision_id": decision_id},
                {"payload.moneyline.decision_id": decision_id},
            ]
        }
        projection = {"payload": 1, "league": 1, "game_id": 1, "_id": 0}

        try:
            record = self.decision_record_collection.find_one(query, projection)
        except Exception as exc:
            raise RuntimeError(f"decision lookup failed: {exc}") from exc

        if not record:
            raise KeyError("decision_id not found")

        payload = record.get("payload") or {}
        spread = payload.get("spread")
        total = payload.get("total")
        moneyline = payload.get("moneyline")

        market_decision = None
        for candidate in (spread, total, moneyline):
            if candidate and candidate.get("decision_id") == decision_id:
                market_decision = candidate
                break

        if not market_decision:
            raise KeyError("decision_id not found")

        probability_edge = None
        edge = market_decision.get("edge") or {}
        if edge.get("edge_points") is not None:
            probability_edge = edge.get("edge_points")
        elif edge.get("edge_ev") is not None:
            probability_edge = edge.get("edge_ev")

        probabilities = market_decision.get("probabilities") or {}

        return {
            "event_id": record.get("game_id"),
            "snapshot_hash": payload.get("inputs_hash"),
            "league": record.get("league"),
            "market_type": market_decision.get("market_type"),
            "classification": market_decision.get("classification"),
            "release_status": market_decision.get("release_status"),
            "confidence": probabilities.get("model_prob") or 0.0,
            "probability_edge": probability_edge,
            "team_home": payload.get("home_team_name"),
            "team_away": payload.get("away_team_name"),
        }

    def _apply_rules(self, decision: Dict[str, Any], calendar_day: str):
        rules_evaluated = []

        release_status = str(decision["release_status"])
        classification = str(decision["classification"]) if decision.get("classification") else None
        market_type = str(decision["market_type"])
        confidence = float(decision.get("confidence") or 0.0)

        # RULE 1
        rules_evaluated.append("ELIGIBILITY_GATE")
        if release_status not in ("OFFICIAL", "INFO_ONLY"):
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "BLOCKED_RELEASE_STATUS",
                "BLOCKED_RELEASE_STATUS",
                rules_evaluated,
            )

        # RULE 2
        rules_evaluated.append("CONFIDENCE_THRESHOLD")
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            return (
                DistributionCategory.ANALYSIS_ONLY.value,
                "BELOW_CONFIDENCE_THRESHOLD",
                None,
                rules_evaluated,
            )

        counts = self._read_daily_counts_fail_closed(
            calendar_day=calendar_day,
            event_id=decision["event_id"],
            team_home=decision.get("team_home"),
            team_away=decision.get("team_away"),
        )
        if counts.get("_count_query_failed"):
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "DAILY_COUNT_QUERY_FAILED",
                "DAILY_COUNT_QUERY_FAILED",
                rules_evaluated,
            )

        # RULE 3
        rules_evaluated.append("DAILY_EDGE_CAP")
        if counts["total_selected_today"] >= MAX_EDGES_PER_DAY:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "DAILY_EDGE_CAP_REACHED",
                "DAILY_EDGE_CAP_REACHED",
                rules_evaluated,
            )

        # RULE 4
        rules_evaluated.append("MARKET_TYPE_CAP")
        if market_type == "SPREAD" and counts["spread_selected_today"] >= MAX_SPREAD_EDGES_PER_DAY:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "SPREAD_CAP_REACHED",
                "SPREAD_CAP_REACHED",
                rules_evaluated,
            )
        if market_type == "TOTAL" and counts["total_market_selected_today"] >= MAX_TOTAL_EDGES_PER_DAY:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "TOTAL_CAP_REACHED",
                "TOTAL_CAP_REACHED",
                rules_evaluated,
            )
        if market_type in ("MONEYLINE_2WAY", "MONEYLINE_3WAY") and counts["moneyline_selected_today"] >= MAX_MONEYLINE_EDGES_PER_DAY:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "MONEYLINE_CAP_REACHED",
                "MONEYLINE_CAP_REACHED",
                rules_evaluated,
            )

        # RULE 5
        rules_evaluated.append("SAME_GAME_EXPOSURE")
        if counts["same_game_selected_today"] >= MAX_SAME_GAME_EXPOSURE:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "SAME_GAME_CAP_REACHED",
                "SAME_GAME_CAP_REACHED",
                rules_evaluated,
            )

        # RULE 6
        rules_evaluated.append("SAME_TEAM_EXPOSURE")
        if counts["same_team_selected_today"] >= MAX_SAME_TEAM_EXPOSURE:
            return (
                DistributionCategory.WITHHELD_EDGE.value,
                "SAME_TEAM_CAP_REACHED",
                "SAME_TEAM_CAP_REACHED",
                rules_evaluated,
            )

        # RULE 7
        rules_evaluated.append("NO_ACTION_CLASSIFICATION")
        if classification == "NO_ACTION":
            return (
                DistributionCategory.ANALYSIS_ONLY.value,
                "NO_ACTION_CLASSIFICATION",
                None,
                rules_evaluated,
            )

        # RULE 8
        rules_evaluated.append("PASS_ALL_RULES")
        return (
            DistributionCategory.SELECTED_PLAY.value,
            "PASS_ALL_RULES",
            None,
            rules_evaluated,
        )

    def _read_daily_counts_fail_closed(
        self,
        calendar_day: str,
        event_id: str,
        team_home: Optional[str],
        team_away: Optional[str],
    ) -> Dict[str, Any]:
        selected_base = {
            "calendar_day": calendar_day,
            "distribution_category": DistributionCategory.SELECTED_PLAY.value,
        }

        try:
            total_selected_today = self.distribution_collection.count_documents(selected_base)
            spread_selected_today = self.distribution_collection.count_documents(
                {**selected_base, "market_type": "SPREAD"}
            )
            total_market_selected_today = self.distribution_collection.count_documents(
                {**selected_base, "market_type": "TOTAL"}
            )
            moneyline_selected_today = self.distribution_collection.count_documents(
                {**selected_base, "market_type": {"$in": ["MONEYLINE_2WAY", "MONEYLINE_3WAY"]}}
            )
            same_game_selected_today = self.distribution_collection.count_documents(
                {**selected_base, "event_id": event_id}
            )

            team_clauses = []
            if team_home:
                team_clauses.extend([
                    {"team_home": team_home},
                    {"team_away": team_home},
                ])
            if team_away:
                team_clauses.extend([
                    {"team_home": team_away},
                    {"team_away": team_away},
                ])

            same_team_selected_today = 0
            if team_clauses:
                same_team_selected_today = self.distribution_collection.count_documents(
                    {**selected_base, "$or": team_clauses}
                )

            return {
                "total_selected_today": total_selected_today,
                "spread_selected_today": spread_selected_today,
                "total_market_selected_today": total_market_selected_today,
                "moneyline_selected_today": moneyline_selected_today,
                "same_game_selected_today": same_game_selected_today,
                "same_team_selected_today": same_team_selected_today,
            }
        except Exception as exc:
            self._log_assertion_failure(
                code="DAILY_COUNT_QUERY_FAILED",
                message=f"Distribution count query failed: {exc}",
                metadata={"calendar_day": calendar_day, "event_id": event_id},
            )
            return {"_count_query_failed": True}

    def _log_lifecycle_event(
        self,
        decision_id: str,
        event_id: str,
        trace_id: str,
        snapshot_hash: str,
        category: str,
        rule_applied: str,
        withheld_reason: Optional[str],
        timestamp: str,
    ) -> None:
        try:
            observability_service.log_prediction_lifecycle(
                stage="DISTRIBUTION_GOVERNANCE",
                decision_id=decision_id,
                event_id=event_id,
                trace_id=trace_id,
                snapshot_hash=snapshot_hash,
                metadata={
                    "distribution_category": category,
                    "rule_applied": rule_applied,
                    "withheld_reason": withheld_reason,
                    "constants_version": CONSTANTS_VERSION,
                    "timestamp": timestamp,
                },
            )
        except Exception:
            # Lifecycle logging is best-effort here to avoid hiding successful distribution decisions.
            pass

    def _log_assertion_failure(self, code: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "assertion_id": str(uuid.uuid4()),
            "code": code,
            "message": message,
            "metadata": metadata or {},
            "created_at_utc": now_iso,
        }
        try:
            self.assertion_collection.insert_one(doc)
        except Exception:
            pass


_distribution_governance_service: Optional[DistributionGovernanceService] = None


def get_distribution_governance_service() -> DistributionGovernanceService:
    global _distribution_governance_service
    if _distribution_governance_service is None:
        _distribution_governance_service = DistributionGovernanceService()
    return _distribution_governance_service

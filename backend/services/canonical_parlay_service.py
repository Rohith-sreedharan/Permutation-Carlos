"""Canonical parlay data service.

All parlay candidates and execution legs are resolved from decision_records only.
No signals collection or client-provided probabilities/odds are used.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from db.mongo import db


_ALLOWED_CLASSIFICATIONS = {"EDGE", "LEAN"}
_ALLOWED_MARKETS = ("spread", "total", "moneyline")


class CanonicalParlayService:
    """Strict resolver for canonical decision-backed parlay legs."""

    def __init__(self, decision_records_collection=None) -> None:
        self._decision_records = decision_records_collection or db["decision_records"]

    def _selection_label(self, market_type: str, decision: Dict[str, Any], record: Dict[str, Any]) -> str:
        pick = decision.get("pick") or {}
        market = decision.get("market") or {}

        if market_type == "total":
            side = pick.get("side") or "UNKNOWN"
            line = market.get("line")
            return f"{side} {line}" if line is not None else str(side)

        if market_type == "moneyline":
            team_name = pick.get("team_name") or pick.get("team_id") or "UNKNOWN"
            return f"{team_name} ML"

        team_name = pick.get("team_name") or pick.get("team_id") or "UNKNOWN"
        line = market.get("line")
        return f"{team_name} {line}" if line is not None else str(team_name)

    def _to_candidate(self, record: Dict[str, Any], market_key: str, decision: Dict[str, Any]) -> Dict[str, Any]:
        snapshot_hash = (record.get("payload") or {}).get("inputs_hash")
        if not snapshot_hash:
            raise ValueError("missing snapshot_hash")

        if decision.get("release_status") != "OFFICIAL":
            raise ValueError("release_status not OFFICIAL")

        classification = str(decision.get("classification") or "")
        if classification not in _ALLOWED_CLASSIFICATIONS:
            raise ValueError("classification not allowed")

        if decision.get("di_pass") is not True:
            raise ValueError("di_pass must be true")

        if decision.get("mv_pass") is not True:
            raise ValueError("mv_pass must be true")

        decision_id = decision.get("decision_id")
        if not decision_id:
            raise ValueError("missing decision_id")

        probabilities = decision.get("probabilities") or {}
        canonical_probability = probabilities.get("model_prob")
        if canonical_probability is None:
            raise ValueError("missing canonical probability")

        market = decision.get("market") or {}
        canonical_odds = market.get("odds")
        if canonical_odds is None:
            raise ValueError("missing canonical odds")

        market_type = str(decision.get("market_type") or "").upper()
        if market_type.startswith("MONEYLINE"):
            pick_type = "moneyline"
        elif market_type == "TOTAL":
            pick_type = "total"
        else:
            pick_type = "spread"

        event_id = record.get("event_id") or record.get("game_id")
        if not event_id:
            raise ValueError("missing event_id")

        return {
            "decision_id": str(decision_id),
            "snapshot_hash": str(snapshot_hash),
            "canonical_state": classification,
            "event_id": str(event_id),
            "sport": str(record.get("league") or "UNKNOWN"),
            "league": str(record.get("league") or "UNKNOWN"),
            "pick_type": pick_type,
            "selection": self._selection_label(market_key, decision, record),
            "true_probability": float(canonical_probability),
            "american_odds": int(canonical_odds),
        }

    def _iter_market_decisions(self, record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        payload = record.get("payload") or {}
        for market_key in _ALLOWED_MARKETS:
            decision = payload.get(market_key)
            if decision:
                yield {"market_key": market_key, "decision": decision}

    def get_candidate_legs(self, sports: Optional[List[str]] = None, limit: int = 200) -> List[Dict[str, Any]]:
        """Return strict canonical candidates from decision_records only."""
        query: Dict[str, Any] = {
            "payload.inputs_hash": {"$exists": True, "$ne": None},
            "$or": [
                {
                    "payload.spread.release_status": "OFFICIAL",
                    "payload.spread.classification": {"$in": ["EDGE", "LEAN"]},
                    "payload.spread.di_pass": True,
                    "payload.spread.mv_pass": True,
                },
                {
                    "payload.total.release_status": "OFFICIAL",
                    "payload.total.classification": {"$in": ["EDGE", "LEAN"]},
                    "payload.total.di_pass": True,
                    "payload.total.mv_pass": True,
                },
                {
                    "payload.moneyline.release_status": "OFFICIAL",
                    "payload.moneyline.classification": {"$in": ["EDGE", "LEAN"]},
                    "payload.moneyline.di_pass": True,
                    "payload.moneyline.mv_pass": True,
                },
            ],
        }

        if sports:
            query["league"] = {"$in": sports}

        docs = list(self._decision_records.find(query).sort("created_at", -1).limit(limit))

        candidates: List[Dict[str, Any]] = []
        for record in docs:
            for market_item in self._iter_market_decisions(record):
                try:
                    candidate = self._to_candidate(
                        record=record,
                        market_key=market_item["market_key"],
                        decision=market_item["decision"],
                    )
                except ValueError:
                    continue
                candidates.append(candidate)

        return candidates

    def resolve_decision_ids(self, decision_ids: List[str]) -> List[Dict[str, Any]]:
        """Resolve canonical execution legs from decision IDs; fail fast on any invalid ID."""
        resolved: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for raw_decision_id in decision_ids:
            decision_id = str(raw_decision_id).strip()
            if not decision_id:
                raise ValueError("decision_id cannot be empty")
            if decision_id in seen:
                raise ValueError(f"duplicate decision_id: {decision_id}")
            seen.add(decision_id)

            query = {
                "$or": [
                    {"payload.spread.decision_id": decision_id},
                    {"payload.total.decision_id": decision_id},
                    {"payload.moneyline.decision_id": decision_id},
                ]
            }
            record = self._decision_records.find_one(query)
            if not record:
                raise KeyError(f"invalid decision_id: {decision_id}")

            payload = record.get("payload") or {}
            decision = None
            market_key = ""
            for key in _ALLOWED_MARKETS:
                candidate = payload.get(key)
                if candidate and candidate.get("decision_id") == decision_id:
                    decision = candidate
                    market_key = key
                    break

            if not decision:
                raise KeyError(f"invalid decision_id: {decision_id}")

            resolved.append(self._to_candidate(record=record, market_key=market_key, decision=decision))

        return resolved


canonical_parlay_service = CanonicalParlayService()

"""
Phase 7A - Public Trust Record Service (Canonical Lineage)

All metrics are sourced from canonical lineage collections only:
- grading
- decision_settlement_metrics
- system_performance (response audit log)

No legacy phase-7 lineage collections are read.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from db.mongo import db

logger = logging.getLogger(__name__)

# Locked thresholds
N_SEGMENT_MIN = 50
N_HOMEPAGE_MIN = 200
N_PROMOTION_MIN = 500

BUILDING_STATE = "Track record building - check back soon."
NO_DATA_STATE = "Simulation intelligence active. Track record begins accumulating as games settle."
DISCLAIMER_TEXT = (
    "Past performance does not guarantee future results. "
    "BeatVegas is a sports intelligence platform - not a sportsbook."
)
POWERED_BY = "Powered by agentic simulation"

_grading = db["grading"]
_settlement = db["decision_settlement_metrics"]
_perf_log = db["system_performance"]
_suppression_log = db["sentinel_event_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_suppression(segment_key: str, n_actual: int, n_required: int, context: str) -> None:
    _suppression_log.insert_one(
        {
            "event_id": str(uuid4()),
            "event_type": "SAMPLE_GATE_SUPPRESSION",
            "severity": "INFO",
            "agent_id": "agent.sentinel.v1",
            "segment_key": segment_key,
            "n_actual": n_actual,
            "n_required": n_required,
            "suppression_context": context,
            "timestamp": _now_iso(),
        }
    )


def _gate(segment_key: str, n_actual: int, n_required: int) -> Optional[str]:
    if n_actual < n_required:
        _log_suppression(segment_key, n_actual, n_required, "performance_api_call")
        return BUILDING_STATE
    return None


def _load_settled_grading() -> List[Dict[str, Any]]:
    rows = list(
        _grading.find(
            {"bet_status": "SETTLED"},
            {
                "_id": 0,
                "graded_id": 1,
                "decision_id": 1,
                "classification": 1,
                "league": 1,
                "market_type": 1,
                "result_code": 1,
                "outcome": 1,
            },
        )
    )
    for row in rows:
        result = str(row.get("result_code") or row.get("outcome") or "").upper()
        row["_normalized_result"] = result
    return rows


def _is_win_loss(result: str) -> bool:
    return result in {"WIN", "LOSS"}


def _is_win(result: str) -> bool:
    return result == "WIN"


def _win_rate_by_classification() -> Dict[str, Any]:
    rows = _load_settled_grading()
    results: Dict[str, Any] = {}
    for cls in ("EDGE", "LEAN"):
        seg = [r for r in rows if str(r.get("classification") or "").upper() == cls and _is_win_loss(r["_normalized_result"])]
        n = len(seg)
        if n == 0:
            results[cls] = {"value": NO_DATA_STATE, "n": 0, "source_table": "grading"}
            continue
        gated = _gate(f"win_rate_by_classification:{cls}", n, N_SEGMENT_MIN)
        if gated:
            results[cls] = {"value": gated, "n": n, "source_table": "grading"}
            continue
        wins = sum(1 for r in seg if _is_win(r["_normalized_result"]))
        sample_ids = [r.get("decision_id") or r.get("graded_id") for r in seg[:5]]
        results[cls] = {
            "value": round(wins / n * 100, 2),
            "unit": "%",
            "n": n,
            "wins": wins,
            "source_table": "grading",
            "sample_decision_ids": sample_ids,
        }
    return results


def _win_rate_by_league() -> Dict[str, Any]:
    rows = _load_settled_grading()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if not _is_win_loss(row["_normalized_result"]):
            continue
        key = str(row.get("league") or "UNKNOWN").upper()
        grouped.setdefault(key, []).append(row)

    results: Dict[str, Any] = {}
    for league, seg in grouped.items():
        n = len(seg)
        gated = _gate(f"win_rate_by_league:{league}", n, N_SEGMENT_MIN)
        if gated:
            results[league] = {"value": gated, "n": n, "source_table": "grading"}
            continue
        wins = sum(1 for r in seg if _is_win(r["_normalized_result"]))
        sample_ids = [r.get("decision_id") or r.get("graded_id") for r in seg[:5]]
        results[league] = {
            "value": round(wins / n * 100, 2),
            "unit": "%",
            "n": n,
            "wins": wins,
            "source_table": "grading",
            "sample_decision_ids": sample_ids,
        }
    return results


def _win_rate_by_market_type() -> Dict[str, Any]:
    rows = _load_settled_grading()
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if not _is_win_loss(row["_normalized_result"]):
            continue
        key = str(row.get("market_type") or "UNKNOWN").upper()
        grouped.setdefault(key, []).append(row)

    results: Dict[str, Any] = {}
    for market_type, seg in grouped.items():
        n = len(seg)
        gated = _gate(f"win_rate_by_market_type:{market_type}", n, N_SEGMENT_MIN)
        if gated:
            results[market_type] = {"value": gated, "n": n, "source_table": "grading"}
            continue
        wins = sum(1 for r in seg if _is_win(r["_normalized_result"]))
        sample_ids = [r.get("decision_id") or r.get("graded_id") for r in seg[:5]]
        results[market_type] = {
            "value": round(wins / n * 100, 2),
            "unit": "%",
            "n": n,
            "wins": wins,
            "source_table": "grading",
            "sample_decision_ids": sample_ids,
        }
    return results


def _windowed_settlement_rows(window_days: int) -> List[Dict[str, Any]]:
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    rows = list(
        _settlement.find(
            {"timestamp": {"$gte": since}},
            {
                "_id": 0,
                "decision_id": 1,
                "graded_id": 1,
                "brier": 1,
                "brier_component": 1,
                "logloss": 1,
                "logloss_component": 1,
                "p_predicted": 1,
                "actual_outcome": 1,
                "clv": 1,
            },
        )
    )
    return rows


def _mean_metric(window_days: int, primary_key: str, fallback_key: str, segment_key: str) -> Dict[str, Any]:
    rows = _windowed_settlement_rows(window_days)
    values: List[float] = []
    sample_ids: List[str] = []
    for row in rows:
        raw = row.get(primary_key)
        if raw is None:
            raw = row.get(fallback_key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
            sample_ids.append(str(row.get("decision_id") or row.get("graded_id") or ""))
        except (TypeError, ValueError):
            continue

    n = len(values)
    if n == 0:
        return {"value": NO_DATA_STATE, "n": 0, "window_days": window_days, "source_table": "decision_settlement_metrics"}

    gated = _gate(f"{segment_key}:{window_days}d", n, N_SEGMENT_MIN)
    if gated:
        return {"value": gated, "n": n, "window_days": window_days, "source_table": "decision_settlement_metrics"}

    return {
        "value": round(sum(values) / n, 6),
        "n": n,
        "window_days": window_days,
        "source_table": "decision_settlement_metrics",
        "sample_decision_ids": sample_ids[:5],
    }


def _brier_score(window_days: int) -> Dict[str, Any]:
    return _mean_metric(window_days, "brier", "brier_component", "brier_score")


def _log_loss(window_days: int) -> Dict[str, Any]:
    return _mean_metric(window_days, "logloss", "logloss_component", "log_loss")


def _ece_by_bucket() -> Dict[str, Any]:
    rows = _windowed_settlement_rows(3650)
    buckets: List[Dict[str, Any]] = []
    total_n = 0

    for i in range(10):
        low = round(i * 0.1, 1)
        high = round((i + 1) * 0.1, 1)
        seg = []
        for row in rows:
            p = row.get("p_predicted")
            y = row.get("actual_outcome")
            if p is None or y is None:
                continue
            try:
                p_val = float(p)
                y_val = float(y)
            except (TypeError, ValueError):
                continue
            if (low <= p_val < high) or (i == 9 and p_val == high):
                seg.append((p_val, y_val, str(row.get("decision_id") or row.get("graded_id") or "")))

        n = len(seg)
        if n == 0:
            buckets.append({"bucket": f"{low:.1f}-{high:.1f}", "value": NO_DATA_STATE, "n": 0})
            continue

        total_n += n
        gated = _gate(f"ece_bucket:{low:.1f}-{high:.1f}", n, N_SEGMENT_MIN)
        if gated:
            buckets.append({"bucket": f"{low:.1f}-{high:.1f}", "value": gated, "n": n})
            continue

        avg_prob = sum(p for p, _, _ in seg) / n
        avg_outcome = sum(y for _, y, _ in seg) / n
        calibration_error = abs(avg_prob - avg_outcome)
        sample_ids = [did for _, _, did in seg[:3]]
        buckets.append(
            {
                "bucket": f"{low:.1f}-{high:.1f}",
                "value": round(calibration_error, 6),
                "n": n,
                "avg_predicted_prob": round(avg_prob, 4),
                "avg_actual_outcome": round(avg_outcome, 4),
                "source_table": "decision_settlement_metrics",
                "sample_decision_ids": sample_ids,
            }
        )

    return {"buckets": buckets, "total_n": total_n}


def _clv_metrics() -> Dict[str, Any]:
    grading_rows = _load_settled_grading()
    by_class: Dict[str, List[str]] = {"EDGE": [], "LEAN": []}
    for row in grading_rows:
        cls = str(row.get("classification") or "").upper()
        if cls in by_class:
            gid = row.get("graded_id")
            if gid:
                by_class[cls].append(str(gid))

    results: Dict[str, Any] = {}
    for cls, graded_ids in by_class.items():
        if not graded_ids:
            results[cls] = {"avg_clv": NO_DATA_STATE, "beat_rate": NO_DATA_STATE, "n": 0, "source_table": "decision_settlement_metrics"}
            continue

        rows = list(
            _settlement.find(
                {"graded_id": {"$in": graded_ids}, "clv": {"$ne": None}},
                {"_id": 0, "clv": 1, "decision_id": 1, "graded_id": 1},
            )
        )
        vals = []
        sample_ids = []
        for row in rows:
            try:
                val = float(row.get("clv"))
            except (TypeError, ValueError):
                continue
            vals.append(val)
            sample_ids.append(str(row.get("decision_id") or row.get("graded_id") or ""))

        n = len(vals)
        if n == 0:
            results[cls] = {"avg_clv": NO_DATA_STATE, "beat_rate": NO_DATA_STATE, "n": 0, "source_table": "decision_settlement_metrics"}
            continue

        gated = _gate(f"clv:{cls}", n, N_SEGMENT_MIN)
        if gated:
            results[cls] = {"avg_clv": gated, "beat_rate": gated, "n": n, "source_table": "decision_settlement_metrics"}
            continue

        beats = sum(1 for v in vals if v > 0)
        results[cls] = {
            "avg_clv": round(sum(vals) / n, 4),
            "beat_rate": round(beats / n * 100, 2),
            "unit": "%",
            "n": n,
            "source_table": "decision_settlement_metrics",
            "sample_decision_ids": sample_ids[:5],
        }

    return results


def _total_decisions_graded() -> Dict[str, Any]:
    total = _grading.count_documents({"bet_status": "SETTLED"})
    return {"value": total, "source_table": "grading", "always_shown": True}


def _homepage_summary() -> Dict[str, Any]:
    rows = _load_settled_grading()
    seg = [r for r in rows if _is_win_loss(r["_normalized_result"])]
    n = len(seg)
    if n == 0:
        return {"value": NO_DATA_STATE, "n": 0}

    gated = _gate("homepage_summary", n, N_HOMEPAGE_MIN)
    if gated:
        return {"value": gated, "n": n, "source_table": "grading"}

    wins = sum(1 for r in seg if _is_win(r["_normalized_result"]))
    sample_ids = [r.get("decision_id") or r.get("graded_id") for r in seg[:5]]
    return {
        "overall_win_rate": round(wins / n * 100, 2),
        "total_graded": n,
        "n": n,
        "source_table": "grading",
        "sample_decision_ids": sample_ids,
    }


def _drill(obj: Any, key: str) -> Optional[Any]:
    parts = key.split(".", 1)
    if not isinstance(obj, dict):
        return None
    value = obj.get(parts[0])
    if len(parts) == 1:
        return value
    return _drill(value, parts[1])


def trace_metric(metric_key: str, response_hash: str) -> Dict[str, Any]:
    log_entry = _perf_log.find_one(
        {"metric_type": "phase7_performance_response", "response_hash": response_hash},
        {"_id": 0},
    )
    if not log_entry:
        return {"error": f"No phase7 performance log entry found for response_hash={response_hash!r}"}

    snapshot = log_entry.get("metrics_snapshot", {})
    metric_data = _drill(snapshot, metric_key)
    if metric_data is None:
        return {"error": f"metric_key={metric_key!r} not found in log entry"}

    decision_ids: List[str] = []
    if isinstance(metric_data, dict):
        decision_ids = [str(x) for x in metric_data.get("sample_decision_ids", []) if x]

    decision_records = []
    for did in decision_ids[:3]:
        rec = db["decision_records"].find_one(
            {"$or": [{"decision_id": did}, {"record_id": did}]},
            {"_id": 0, "decision_id": 1, "record_id": 1, "snapshot_hash": 1, "classification": 1, "market_type": 1},
        )
        if rec:
            decision_records.append(rec)

    return {
        "metric_key": metric_key,
        "response_hash": response_hash,
        "performance_log_entry": {
            "log_id": log_entry.get("log_id"),
            "logged_at_utc": log_entry.get("logged_at_utc"),
            "response_hash": response_hash,
            "collection": "system_performance",
        },
        "metric_data": metric_data,
        "source_table": metric_data.get("source_table") if isinstance(metric_data, dict) else "unknown",
        "decision_records": decision_records,
        "chain": "API response -> system_performance -> canonical source_table -> decision_records.snapshot_hash",
    }


def get_performance_metrics() -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "win_rate_by_classification": _win_rate_by_classification(),
        "win_rate_by_league": _win_rate_by_league(),
        "win_rate_by_market_type": _win_rate_by_market_type(),
        "brier_score": {"7d": _brier_score(7), "30d": _brier_score(30), "90d": _brier_score(90)},
        "log_loss": {"7d": _log_loss(7), "30d": _log_loss(30), "90d": _log_loss(90)},
        "ece_by_bucket": _ece_by_bucket(),
        "clv": _clv_metrics(),
        "total_decisions_graded": _total_decisions_graded(),
        "homepage_summary": _homepage_summary(),
        "disclosure": DISCLAIMER_TEXT,
        "powered_by": POWERED_BY,
        "sample_thresholds": {
            "N_SEGMENT_MIN": N_SEGMENT_MIN,
            "N_HOMEPAGE_MIN": N_HOMEPAGE_MIN,
            "N_PROMOTION_MIN": N_PROMOTION_MIN,
        },
    }

    hash_input = json.dumps(metrics, sort_keys=True, default=str)
    response_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    log_id = str(uuid4())
    _perf_log.insert_one(
        {
            "log_id": log_id,
            "metric_type": "phase7_performance_response",
            "response_hash": response_hash,
            "metrics_snapshot": metrics,
            "logged_at_utc": _now_iso(),
            "source": "phase7_trust_record.get_performance_metrics.canonical",
            "service_authority": "agent.performance.v1",
        }
    )

    return {
        "metrics": metrics,
        "response_hash": response_hash,
        "log_id": log_id,
        "generated_at_utc": _now_iso(),
        "disclosure": DISCLAIMER_TEXT,
        "powered_by": POWERED_BY,
    }

"""
Phase 7A — Public Trust Record Service

All metrics sourced exclusively from truth_dataset_v1, grading_records,
calibration_records, clv_records.  No manually entered data.  No estimates.
Every number has a traceable path back to an append-only log entry.

SAMPLE THRESHOLDS (LOCKED — operator-approved, hardcoded once here):
  N_SEGMENT_MIN  = 50   — no metric computed or displayed below this
  N_HOMEPAGE_MIN = 200  — homepage summary requires at least this many
  N_PROMOTION_MIN= 500  — calibration promotion eligibility threshold

These constants are referenced throughout this file.  They are not configurable
at runtime.  Do not move them to env vars.  Any change requires written
operator approval.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Sample thresholds (LOCKED — operator-approved) ────────────────────────────
# Hardcoded ONCE here.  Referenced everywhere else.  Not env-configurable.
N_SEGMENT_MIN   = 50    # Minimum N per segment before any metric is computed
N_HOMEPAGE_MIN  = 200   # Minimum N for homepage summary stats
N_PROMOTION_MIN = 500   # Minimum N for calibration promotion eligibility

# ── Canonical display strings ─────────────────────────────────────────────────
BUILDING_STATE  = "Track record building — check back soon."
NO_DATA_STATE   = "Simulation intelligence active. Track record begins accumulating as games settle."
DISCLAIMER_TEXT = (
    "Past performance does not guarantee future results. "
    "BeatVegas is a sports intelligence platform — not a sportsbook."
)
POWERED_BY      = "Powered by agentic simulation"

# ── DB collections ────────────────────────────────────────────────────────────
_truth          = db["truth_dataset_v1"]
_grading        = db["grading_records"]
_calibration    = db["calibration_records"]
_clv            = db["clv_records"]
_settlement     = db["decision_settlement_metrics"]
_perf_log       = db["performance_api_log"]
_suppression_log = db["sentinel_event_log"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_suppression(segment_key: str, n_actual: int, n_required: int, context: str) -> None:
    """Append-only suppression event log.  Called whenever a segment is below threshold."""
    _suppression_log.insert_one({
        "event_id": str(uuid4()),
        "event_type": "SAMPLE_GATE_SUPPRESSION",
        "severity": "INFO",
        "agent_id": "agent.sentinel.v1",
        "segment_key": segment_key,
        "n_actual": n_actual,
        "n_required": n_required,
        "suppression_context": context,
        "timestamp": _now_iso(),
    })
    logger.info("[phase7] Sample gate suppressed segment=%s n_actual=%d n_required=%d", segment_key, n_actual, n_required)


def _gate(segment_key: str, n_actual: int, n_required: int) -> Optional[str]:
    """
    Returns BUILDING_STATE and logs suppression if below threshold.
    Returns None if sample is sufficient (caller may proceed).
    """
    if n_actual < n_required:
        _log_suppression(segment_key, n_actual, n_required, "performance_api_call")
        return BUILDING_STATE
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Metric computations
# ─────────────────────────────────────────────────────────────────────────────

def _win_rate_by_classification() -> Dict[str, Any]:
    """Win rate per classification segment from grading_records."""
    results = {}
    for cls in ("EDGE", "LEAN"):
        pipeline = [
            {"$match": {"classification": cls, "outcome": {"$in": ["WIN", "LOSS"]}}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "wins": {"$sum": {"$cond": [{"$eq": ["$outcome", "WIN"]}, 1, 0]}},
                "decision_ids": {"$push": "$decision_id"},
            }},
        ]
        rows = list(_grading.aggregate(pipeline))
        if not rows:
            results[cls] = {"value": NO_DATA_STATE, "n": 0, "source_table": "grading_records"}
            continue
        row = rows[0]
        n = row["total"]
        gated = _gate(f"win_rate_by_classification:{cls}", n, N_SEGMENT_MIN)
        if gated:
            results[cls] = {"value": gated, "n": n, "source_table": "grading_records"}
        else:
            results[cls] = {
                "value": round(row["wins"] / n * 100, 2),
                "unit": "%",
                "n": n,
                "wins": row["wins"],
                "source_table": "grading_records",
                "sample_decision_ids": row["decision_ids"][:5],
            }
    return results


def _win_rate_by_league() -> Dict[str, Any]:
    """Win rate per league segment from grading_records."""
    pipeline = [
        {"$match": {"outcome": {"$in": ["WIN", "LOSS"]}, "league": {"$exists": True}}},
        {"$group": {
            "_id": "$league",
            "total": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$outcome", "WIN"]}, 1, 0]}},
            "decision_ids": {"$push": "$decision_id"},
        }},
    ]
    rows = list(_grading.aggregate(pipeline))
    results = {}
    for row in rows:
        league = row["_id"] or "UNKNOWN"
        n = row["total"]
        gated = _gate(f"win_rate_by_league:{league}", n, N_SEGMENT_MIN)
        if gated:
            results[league] = {"value": gated, "n": n, "source_table": "grading_records"}
        else:
            results[league] = {
                "value": round(row["wins"] / n * 100, 2),
                "unit": "%",
                "n": n,
                "wins": row["wins"],
                "source_table": "grading_records",
                "sample_decision_ids": row["decision_ids"][:5],
            }
    return results


def _win_rate_by_market_type() -> Dict[str, Any]:
    """Win rate per market type segment from grading_records."""
    pipeline = [
        {"$match": {"outcome": {"$in": ["WIN", "LOSS"]}, "market_type": {"$exists": True}}},
        {"$group": {
            "_id": "$market_type",
            "total": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$outcome", "WIN"]}, 1, 0]}},
            "decision_ids": {"$push": "$decision_id"},
        }},
    ]
    rows = list(_grading.aggregate(pipeline))
    results = {}
    for row in rows:
        mt = row["_id"] or "UNKNOWN"
        n = row["total"]
        gated = _gate(f"win_rate_by_market_type:{mt}", n, N_SEGMENT_MIN)
        if gated:
            results[mt] = {"value": gated, "n": n, "source_table": "grading_records"}
        else:
            results[mt] = {
                "value": round(row["wins"] / n * 100, 2),
                "unit": "%",
                "n": n,
                "wins": row["wins"],
                "source_table": "grading_records",
                "sample_decision_ids": row["decision_ids"][:5],
            }
    return results


def _brier_score(window_days: int) -> Dict[str, Any]:
    """Rolling Brier score from calibration_records for specified window."""
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    pipeline = [
        {"$match": {"graded_at": {"$gte": since}, "probability": {"$exists": True}, "outcome_binary": {"$exists": True}}},
        {"$project": {
            "sq_err": {"$pow": [{"$subtract": ["$probability", "$outcome_binary"]}, 2]},
            "decision_id": 1,
        }},
        {"$group": {"_id": None, "brier_sum": {"$sum": "$sq_err"}, "n": {"$sum": 1}, "decision_ids": {"$push": "$decision_id"}}},
    ]
    rows = list(_calibration.aggregate(pipeline))
    if not rows:
        return {"value": NO_DATA_STATE, "n": 0, "window_days": window_days, "source_table": "calibration_records"}
    row = rows[0]
    n = row["n"]
    gated = _gate(f"brier_score:{window_days}d", n, N_SEGMENT_MIN)
    if gated:
        return {"value": gated, "n": n, "window_days": window_days, "source_table": "calibration_records"}
    return {
        "value": round(row["brier_sum"] / n, 6),
        "n": n,
        "window_days": window_days,
        "source_table": "calibration_records",
        "sample_decision_ids": row["decision_ids"][:5],
    }


def _log_loss(window_days: int) -> Dict[str, Any]:
    """Rolling log loss from calibration_records."""
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    pipeline = [
        {"$match": {"graded_at": {"$gte": since}, "probability": {"$exists": True}, "outcome_binary": {"$exists": True}}},
        {"$project": {
            "ll": {"$cond": [
                {"$eq": ["$outcome_binary", 1]},
                {"$multiply": [-1, {"$ln": {"$max": ["$probability", 1e-15]}}]},
                {"$multiply": [-1, {"$ln": {"$max": [{"$subtract": [1, "$probability"]}, 1e-15]}}]},
            ]},
            "decision_id": 1,
        }},
        {"$group": {"_id": None, "ll_sum": {"$sum": "$ll"}, "n": {"$sum": 1}, "decision_ids": {"$push": "$decision_id"}}},
    ]
    rows = list(_calibration.aggregate(pipeline))
    if not rows:
        return {"value": NO_DATA_STATE, "n": 0, "window_days": window_days, "source_table": "calibration_records"}
    row = rows[0]
    n = row["n"]
    gated = _gate(f"log_loss:{window_days}d", n, N_SEGMENT_MIN)
    if gated:
        return {"value": gated, "n": n, "window_days": window_days, "source_table": "calibration_records"}
    return {
        "value": round(row["ll_sum"] / n, 6),
        "n": n,
        "window_days": window_days,
        "source_table": "calibration_records",
        "sample_decision_ids": row["decision_ids"][:5],
    }


def _ece_by_bucket() -> Dict[str, Any]:
    """Expected Calibration Error bucketed (10 buckets 0.0-1.0)."""
    bucket_size = 0.1
    buckets = []
    total_n = 0
    for i in range(10):
        low = round(i * bucket_size, 1)
        high = round((i + 1) * bucket_size, 1)
        pipeline = [
            {"$match": {"probability": {"$gte": low, "$lt": high}, "outcome_binary": {"$exists": True}}},
            {"$group": {
                "_id": None,
                "n": {"$sum": 1},
                "avg_prob": {"$avg": "$probability"},
                "avg_outcome": {"$avg": "$outcome_binary"},
                "decision_ids": {"$push": "$decision_id"},
            }},
        ]
        rows = list(_calibration.aggregate(pipeline))
        if not rows or rows[0]["n"] == 0:
            buckets.append({"bucket": f"{low:.1f}-{high:.1f}", "value": NO_DATA_STATE, "n": 0})
            continue
        row = rows[0]
        n = row["n"]
        total_n += n
        gated = _gate(f"ece_bucket:{low:.1f}-{high:.1f}", n, N_SEGMENT_MIN)
        if gated:
            buckets.append({"bucket": f"{low:.1f}-{high:.1f}", "value": gated, "n": n})
        else:
            calibration_error = abs(row["avg_prob"] - row["avg_outcome"])
            buckets.append({
                "bucket": f"{low:.1f}-{high:.1f}",
                "value": round(calibration_error, 6),
                "n": n,
                "avg_predicted_prob": round(row["avg_prob"], 4),
                "avg_actual_outcome": round(row["avg_outcome"], 4),
                "source_table": "calibration_records",
                "sample_decision_ids": row["decision_ids"][:3],
            })
    return {"buckets": buckets, "total_n": total_n}


def _clv_metrics() -> Dict[str, Any]:
    """CLV average and beat rate by classification from clv_records."""
    results = {}
    for cls in ("EDGE", "LEAN"):
        pipeline = [
            {"$match": {"classification": cls, "clv": {"$exists": True}}},
            {"$group": {
                "_id": None,
                "n": {"$sum": 1},
                "avg_clv": {"$avg": "$clv"},
                "beats": {"$sum": {"$cond": [{"$gt": ["$clv", 0]}, 1, 0]}},
                "decision_ids": {"$push": "$decision_id"},
            }},
        ]
        rows = list(_clv.aggregate(pipeline))
        if not rows:
            results[cls] = {"avg_clv": NO_DATA_STATE, "beat_rate": NO_DATA_STATE, "n": 0, "source_table": "clv_records"}
            continue
        row = rows[0]
        n = row["n"]
        gated = _gate(f"clv:{cls}", n, N_SEGMENT_MIN)
        if gated:
            results[cls] = {"avg_clv": gated, "beat_rate": gated, "n": n, "source_table": "clv_records"}
        else:
            results[cls] = {
                "avg_clv": round(row["avg_clv"], 4),
                "beat_rate": round(row["beats"] / n * 100, 2),
                "unit": "%",
                "n": n,
                "source_table": "clv_records",
                "sample_decision_ids": row["decision_ids"][:5],
            }
    return results


def _total_decisions_graded() -> Dict[str, Any]:
    """Total graded decisions — always shown, no sample gate."""
    total = _grading.count_documents({"outcome": {"$in": ["WIN", "LOSS", "PUSH", "NO_ACTION"]}})
    return {
        "value": total,
        "source_table": "grading_records",
        "always_shown": True,
    }


def _homepage_summary() -> Dict[str, Any]:
    """Summary stats for homepage — requires N >= N_HOMEPAGE_MIN."""
    pipeline = [
        {"$match": {"outcome": {"$in": ["WIN", "LOSS"]}}},
        {"$group": {
            "_id": None,
            "n": {"$sum": 1},
            "wins": {"$sum": {"$cond": [{"$eq": ["$outcome", "WIN"]}, 1, 0]}},
            "decision_ids": {"$push": "$decision_id"},
        }},
    ]
    rows = list(_grading.aggregate(pipeline))
    if not rows:
        return {"value": NO_DATA_STATE, "n": 0}
    row = rows[0]
    n = row["n"]
    gated = _gate("homepage_summary", n, N_HOMEPAGE_MIN)
    if gated:
        return {"value": gated, "n": n, "source_table": "grading_records"}
    return {
        "overall_win_rate": round(row["wins"] / n * 100, 2),
        "total_graded": n,
        "n": n,
        "source_table": "grading_records",
        "sample_decision_ids": row["decision_ids"][:5],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Traceability — resolve metric key back to source
# ─────────────────────────────────────────────────────────────────────────────

def trace_metric(metric_key: str, response_hash: str) -> Dict[str, Any]:
    """
    Given a metric_key and the response_hash it came from, resolve the full
    traceability chain:
      API response → performance_api_log → source table → decisions.snapshot_hash
    """
    log_entry = _perf_log.find_one({"response_hash": response_hash}, {"_id": 0})
    if not log_entry:
        return {"error": f"No performance_api_log entry found for response_hash={response_hash!r}"}

    # Find the metric in the logged snapshot
    snapshot = log_entry.get("metrics_snapshot", {})
    metric_data = _drill(snapshot, metric_key)
    if metric_data is None:
        return {"error": f"metric_key={metric_key!r} not found in log entry"}

    decision_ids = []
    if isinstance(metric_data, dict):
        decision_ids = metric_data.get("sample_decision_ids", [])

    # Resolve decision records with snapshot_hash
    decision_records = []
    for did in decision_ids[:3]:
        rec = db["decisions"].find_one({"decision_id": did}, {"_id": 0, "decision_id": 1, "snapshot_hash": 1, "classification": 1, "market_type": 1})
        if rec:
            decision_records.append(rec)

    return {
        "metric_key": metric_key,
        "response_hash": response_hash,
        "performance_api_log_entry": {
            "log_id": log_entry.get("log_id"),
            "logged_at_utc": log_entry.get("logged_at_utc"),
            "response_hash": response_hash,
        },
        "metric_data": metric_data,
        "source_table": metric_data.get("source_table") if isinstance(metric_data, dict) else "unknown",
        "decision_records": decision_records,
        "chain": "API response → performance_api_log → source_table → decisions.snapshot_hash",
    }


def _drill(obj: Any, key: str) -> Optional[Any]:
    """Recursive key drill into nested dict. Key format: 'win_rate_by_classification.EDGE'"""
    parts = key.split(".", 1)
    if not isinstance(obj, dict):
        return None
    val = obj.get(parts[0])
    if len(parts) == 1:
        return val
    return _drill(val, parts[1])


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def get_performance_metrics() -> Dict[str, Any]:
    """
    Main public performance endpoint.
    All metrics sample-gated.  Response hash logged to performance_api_log.
    Every returned metric includes source_table for traceability.
    """
    metrics: Dict[str, Any] = {
        "win_rate_by_classification": _win_rate_by_classification(),
        "win_rate_by_league": _win_rate_by_league(),
        "win_rate_by_market_type": _win_rate_by_market_type(),
        "brier_score": {
            "7d":  _brier_score(7),
            "30d": _brier_score(30),
            "90d": _brier_score(90),
        },
        "log_loss": {
            "7d":  _log_loss(7),
            "30d": _log_loss(30),
            "90d": _log_loss(90),
        },
        "ece_by_bucket": _ece_by_bucket(),
        "clv": _clv_metrics(),
        "total_decisions_graded": _total_decisions_graded(),
        "homepage_summary": _homepage_summary(),
        # Disclosure and agentic language — required on every response
        "disclosure": DISCLAIMER_TEXT,
        "powered_by": POWERED_BY,
        "sample_thresholds": {
            "N_SEGMENT_MIN": N_SEGMENT_MIN,
            "N_HOMEPAGE_MIN": N_HOMEPAGE_MIN,
            "N_PROMOTION_MIN": N_PROMOTION_MIN,
        },
    }

    # Response hash — covers all metrics, logged on every call
    hash_input = json.dumps(metrics, sort_keys=True, default=str)
    response_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    log_id = str(uuid4())
    _perf_log.insert_one({
        "log_id": log_id,
        "response_hash": response_hash,
        "metrics_snapshot": metrics,
        "logged_at_utc": _now_iso(),
        "source": "phase7_trust_record.get_performance_metrics",
    })

    return {
        "metrics": metrics,
        "response_hash": response_hash,
        "log_id": log_id,
        "generated_at_utc": _now_iso(),
        "disclosure": DISCLAIMER_TEXT,
        "powered_by": POWERED_BY,
    }

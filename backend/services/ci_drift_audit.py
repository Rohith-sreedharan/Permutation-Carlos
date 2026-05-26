"""
CI Drift Audit — Phase 6A.12
Daily automated job that validates Telegram post distribution health.

All 5 audit checks run sequentially. Any failure blocks deploy.
All thresholds sourced from AGENT_CONFIG — zero hardcoded values.

Checks:
1. Percentile Exposure Drift: >80% above P75 OR <10% below P25 over last 30 posts → FAIL
2. Market Type Skew: any single market_type > 70% over last 30 posts → FAIL
3. Classification Skew: EDGE classification > 80% over last 30 posts → FAIL
4. Volume Predictability: rolling 30-day avg posts/day variance below threshold → FLAG
5. Delay Pattern Detection: post delay distribution variance below threshold → FAIL
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Collection ────────────────────────────────────────────────────────────────
_drift_col = db["ci_drift_audit_log"]


def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("phase6", {}).get("drift_audit", {})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Audit Check 1 — Percentile Exposure Drift
# ─────────────────────────────────────────────────────────────────────────────

def _check_percentile_exposure_drift(posts: List[Dict]) -> Dict[str, Any]:
    """
    Over last 30 posts: >80% above P75 ev OR <10% below P25 ev → FAIL.
    """
    cfg = _cfg()
    p75_threshold = cfg.get("percentile_p75_max_pct", 80)
    p25_threshold = cfg.get("percentile_p25_min_pct", 10)

    evs = [float(p.get("ev", 0) or 0) for p in posts if p.get("ev") is not None]
    if len(evs) < 5:
        return {"check": "percentile_exposure_drift", "result": "SKIP", "reason": f"insufficient data: {len(evs)} ev values"}

    evs_sorted = sorted(evs)
    n = len(evs_sorted)
    p75 = evs_sorted[int(n * 0.75)]
    p25 = evs_sorted[int(n * 0.25)]

    above_p75_pct = (sum(1 for e in evs if e > p75) / n) * 100
    below_p25_pct = (sum(1 for e in evs if e < p25) / n) * 100

    if above_p75_pct > p75_threshold:
        return {
            "check": "percentile_exposure_drift", "result": "FAIL",
            "reason": f"{above_p75_pct:.1f}% above P75 (threshold {p75_threshold}%)",
            "above_p75_pct": above_p75_pct, "below_p25_pct": below_p25_pct,
        }
    if below_p25_pct < p25_threshold:
        return {
            "check": "percentile_exposure_drift", "result": "FAIL",
            "reason": f"{below_p25_pct:.1f}% below P25 (min {p25_threshold}%)",
            "above_p75_pct": above_p75_pct, "below_p25_pct": below_p25_pct,
        }
    return {
        "check": "percentile_exposure_drift", "result": "PASS",
        "above_p75_pct": above_p75_pct, "below_p25_pct": below_p25_pct,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Check 2 — Market Type Skew
# ─────────────────────────────────────────────────────────────────────────────

def _check_market_type_skew(posts: List[Dict]) -> Dict[str, Any]:
    """Any single market_type > 70% over last 30 posts → FAIL."""
    cfg = _cfg()
    skew_threshold = cfg.get("market_type_skew_max_pct", 70)

    if not posts:
        return {"check": "market_type_skew", "result": "SKIP", "reason": "no posts"}

    market_counts: Dict[str, int] = {}
    for p in posts:
        mt = str(p.get("market_type", "UNKNOWN")).upper()
        market_counts[mt] = market_counts.get(mt, 0) + 1

    n = len(posts)
    for mt, count in market_counts.items():
        pct = (count / n) * 100
        if pct > skew_threshold:
            return {
                "check": "market_type_skew", "result": "FAIL",
                "reason": f"{mt} is {pct:.1f}% of last {n} posts (threshold {skew_threshold}%)",
                "market_type": mt, "pct": pct, "distribution": market_counts,
            }

    return {
        "check": "market_type_skew", "result": "PASS",
        "distribution": {k: f"{(v/n)*100:.1f}%" for k, v in market_counts.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Check 3 — Classification Skew
# ─────────────────────────────────────────────────────────────────────────────

def _check_classification_skew(posts: List[Dict]) -> Dict[str, Any]:
    """EDGE classification > 80% over last 30 posts → FAIL."""
    cfg = _cfg()
    edge_max_pct = cfg.get("classification_edge_max_pct", 80)

    if not posts:
        return {"check": "classification_skew", "result": "SKIP", "reason": "no posts"}

    n = len(posts)
    edge_count = sum(1 for p in posts if str(p.get("classification", "")).upper() == "EDGE")
    edge_pct = (edge_count / n) * 100

    if edge_pct > edge_max_pct:
        return {
            "check": "classification_skew", "result": "FAIL",
            "reason": f"EDGE is {edge_pct:.1f}% of last {n} posts (threshold {edge_max_pct}%)",
            "edge_pct": edge_pct,
        }

    return {
        "check": "classification_skew", "result": "PASS",
        "edge_pct": edge_pct,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Check 4 — Volume Predictability
# ─────────────────────────────────────────────────────────────────────────────

def _check_volume_predictability(posts: List[Dict]) -> Dict[str, Any]:
    """
    Rolling 30-day avg posts/day variance below threshold → FLAG (not fail CI).
    Groups posts by day and checks variance in daily counts.
    """
    cfg = _cfg()
    min_variance_threshold = cfg.get("volume_variance_min", 0.5)

    if len(posts) < 10:
        return {"check": "volume_predictability", "result": "SKIP", "reason": "insufficient posts for variance analysis"}

    daily_counts: Dict[str, int] = {}
    for p in posts:
        ts = p.get("sent_at_utc") or p.get("created_at_utc") or ""
        if ts:
            day = ts[:10]
            daily_counts[day] = daily_counts.get(day, 0) + 1

    if len(daily_counts) < 3:
        return {"check": "volume_predictability", "result": "SKIP", "reason": "insufficient days"}

    counts = list(daily_counts.values())
    variance = statistics.variance(counts) if len(counts) > 1 else 0

    if variance < min_variance_threshold:
        return {
            "check": "volume_predictability", "result": "FLAG",
            "reason": f"daily post count variance={variance:.3f} is below threshold={min_variance_threshold} — possible randomness drift",
            "daily_counts": daily_counts, "variance": variance,
        }

    return {
        "check": "volume_predictability", "result": "PASS",
        "variance": variance, "daily_counts": daily_counts,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Check 5 — Delay Pattern Detection
# ─────────────────────────────────────────────────────────────────────────────

def _check_delay_pattern(posts: List[Dict]) -> Dict[str, Any]:
    """
    Post delay distribution variance below threshold → FAIL CI.
    Measures variance in inter-post delay (seconds between consecutive posts).
    """
    cfg = _cfg()
    min_delay_variance = cfg.get("delay_variance_min", 10.0)  # seconds^2

    timestamps = []
    for p in posts:
        ts_str = p.get("sent_at_utc") or p.get("created_at_utc") or ""
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                timestamps.append(ts)
            except ValueError:
                continue

    timestamps.sort()

    if len(timestamps) < 4:
        return {"check": "delay_pattern_detection", "result": "SKIP", "reason": "insufficient timestamped posts"}

    delays = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(len(timestamps) - 1)
        if (timestamps[i + 1] - timestamps[i]).total_seconds() < 86400  # ignore day boundaries
    ]

    if len(delays) < 3:
        return {"check": "delay_pattern_detection", "result": "SKIP", "reason": "insufficient inter-post delays"}

    variance = statistics.variance(delays)

    if variance < min_delay_variance:
        return {
            "check": "delay_pattern_detection", "result": "FAIL",
            "reason": f"delay variance={variance:.1f}s² below threshold={min_delay_variance}s² — suspicious regularity pattern",
            "variance_seconds_sq": variance,
        }

    return {
        "check": "delay_pattern_detection", "result": "PASS",
        "variance_seconds_sq": variance,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main audit runner
# ─────────────────────────────────────────────────────────────────────────────

def run_drift_audit(window_posts: int = 30) -> Dict[str, Any]:
    """
    Run all 5 drift audit checks. Log result to ci_drift_audit_log.
    Returns summary with individual check results.
    Any FAIL → overall_result = FAIL (blocks deploy).
    FLAG does not block deploy but is logged.
    """
    run_id = str(uuid4())
    run_at = _now_iso()

    # Pull last N successful posts from distribution_audit_log
    posts = list(
        db["distribution_audit_log"]
        .find({"delivered": True})
        .sort("sent_at_utc", -1)
        .limit(window_posts)
    )

    # Also enrich from decisions collection for classification/ev/market_type
    enriched = []
    for p in posts:
        decision_id = p.get("decision_id")
        if decision_id:
            dec = db["decisions"].find_one({"decision_id": decision_id}, {"classification": 1, "ev": 1, "market_type": 1})
            merged = {**p, **(dec or {})}
            enriched.append(merged)
        else:
            enriched.append(p)

    checks = [
        _check_percentile_exposure_drift(enriched),
        _check_market_type_skew(enriched),
        _check_classification_skew(enriched),
        _check_volume_predictability(enriched),
        _check_delay_pattern(enriched),
    ]

    # Determine overall result
    fail_checks = [c for c in checks if c["result"] == "FAIL"]
    flag_checks = [c for c in checks if c["result"] == "FLAG"]
    overall = "FAIL" if fail_checks else ("FLAG" if flag_checks else "PASS")

    result = {
        "run_id": run_id,
        "run_at_utc": run_at,
        "posts_analysed": len(enriched),
        "overall_result": overall,
        "checks": checks,
        "fail_count": len(fail_checks),
        "flag_count": len(flag_checks),
        "blocks_deploy": overall == "FAIL",
    }

    _drift_col.insert_one({**result, "_id_run_id": run_id})

    if overall == "FAIL":
        logger.error("[DriftAudit] FAIL — %d checks failed — deploy BLOCKED", len(fail_checks))
        for c in fail_checks:
            logger.error("[DriftAudit] FAIL check=%s reason=%s", c["check"], c.get("reason"))
    elif overall == "FLAG":
        logger.warning("[DriftAudit] FLAG — %d checks flagged", len(flag_checks))
    else:
        logger.info("[DriftAudit] PASS — all 5 checks passed. run_id=%s", run_id)

    return result

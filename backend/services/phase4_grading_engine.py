"""
Phase 4B – Grading Engine
==========================
AC-3 / AC-4 requirements.

Responsibilities:
  1. Results provider   – fetches settled game outcomes from OddsAPI scores API.
  2. Unified grader     – grades ALL 4 Phase-4 decision classes
                          (EDGE, LEAN, MARKET_ALIGNED, BLOCKED).
  3. Reconciliation     – detects ungraded EDGE/LEAN decisions after 24 h.
  4. CLV capture        – scheduled at T-5 min before close.
                          Formula (LOCKED): CLV = model_probability − closing_line_implied_probability
                          CLV_CAPTURE_FAILED sentinel fires on API failure.
  5. Drift detection    – computes rolling Brier score trends.
  6. Evidence pack      – stored at evidence/{YYYY-MM-DD}/{decision_id}.json,
                          90-day retention, never deleted within window.

decision_settlement_metrics is APPEND-ONLY – no UPDATE ever.
"""

from __future__ import annotations

import json
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level db reference (patchable in tests)
try:
    _db = _get_db()
except Exception:
    db = None  # type: ignore[assignment]


def _get_db():
    """Return module-level db, falling back to live import if None."""
    import services.phase4_grading_engine as _self
    if _self.db is not None:
        return _self.db
    _db = _get_db()
    return _db

# ── Constants ────────────────────────────────────────────────────────────────
GRADING_AGENT_ID          = "agent.grading.v1"       # used in all log entries
EVIDENCE_ROOT             = Path(os.getenv("PHASE4_EVIDENCE_DIR", "/tmp/evidence"))
EVIDENCE_RETENTION_DAYS   = 90
RECONCILE_AFTER_HOURS     = 24                        # flag ungraded after 24 h
CLV_CAPTURE_WINDOW_MINUTES = 5                        # T-5 min before close


# ============================================================================
# Results Provider
# ============================================================================

def fetch_game_result(event_id: str, sport_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the final score / result for a settled game from OddsAPI.

    Returns a normalised result dict or None if the game is not yet final.
    """
    try:
        from integrations.odds_api import fetch_scores, OddsApiError

        scores = fetch_scores(sport=sport_key)
        for game in scores:
            if game.get("id") == event_id:
                completed = game.get("completed", False)
                if not completed:
                    return None
                scores_list = game.get("scores", [])
                result = {"event_id": event_id, "completed": True, "scores": scores_list}
                # Determine winner
                home = game.get("home_team")
                away = game.get("away_team")
                home_score, away_score = None, None
                for s in scores_list:
                    if s.get("name") == home:
                        home_score = float(s.get("score", 0))
                    elif s.get("name") == away:
                        away_score = float(s.get("score", 0))
                if home_score is not None and away_score is not None:
                    result["home_score"]  = home_score
                    result["away_score"]  = away_score
                    result["home_won"]    = home_score > away_score
                    result["total_score"] = home_score + away_score
                return result
        return None
    except Exception as exc:
        logger.error(f"[{GRADING_AGENT_ID}] fetch_game_result error: {exc}")
        return None


# ============================================================================
# Result code determination
# ============================================================================

def _determine_result_code(decision: Dict, game_result: Dict) -> str:
    """
    Determine WIN / LOSS / PUSH / VOID for a Phase-4 decision record.
    Only EDGE and LEAN records have actionable outcomes.
    MARKET_ALIGNED and BLOCKED are always graded as VOID (no bet).
    """
    cls = decision.get("phase4_decision_class", "BLOCKED")
    if cls in ("MARKET_ALIGNED", "BLOCKED"):
        return "VOID"

    if not game_result.get("completed"):
        return "PENDING"

    home_won = game_result.get("home_won")
    if home_won is None:
        return "VOID"

    # Model prediction: model_probability > 0.5 → predicted home win
    model_p = decision.get("model_probability", 0.50)
    predicted_home_win = model_p > 0.50

    if predicted_home_win == home_won:
        return "WIN"
    return "LOSS"


# ============================================================================
# CLV Capture (T-5 minutes before close)
# ============================================================================

def capture_clv(
    decision_id: str,
    event_id: str,
    sport_key: str,
    home_team: str,
    model_probability: float,
) -> Optional[float]:
    """
    Capture CLV at T-5 minutes before game close.

    LOCKED formula:
        CLV = model_probability − closing_line_implied_probability

    Returns the CLV value or None on failure.
    On failure: fires CLV_CAPTURE_FAILED sentinel event.
    """
    closing_prob = _fetch_closing_line_probability(event_id, sport_key, home_team)
    if closing_prob is None:
        _log_clv_capture_failed(decision_id, event_id, "closing_line_unavailable")
        return None

    clv = model_probability - closing_prob
    logger.info(
        f"[{GRADING_AGENT_ID}] CLV captured: decision_id={decision_id} "
        f"model_p={model_probability:.4f} closing_p={closing_prob:.4f} CLV={clv:+.4f}"
    )
    return clv


def _fetch_closing_line_probability(
    event_id: str, sport_key: str, home_team: str
) -> Optional[float]:
    """Fetch the current/closing moneyline probability from OddsAPI."""
    try:
        from integrations.odds_api import fetch_odds, OddsApiError

        games = fetch_odds(
            sport=sport_key,
            region="us",
            markets="h2h",
            odds_format="american",
        )
        for game in games:
            if game.get("id") != event_id:
                continue
            for bk in game.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    for outcome in mkt.get("outcomes", []):
                        if outcome.get("name") == home_team:
                            price = outcome.get("price", 0)
                            if price == 0:
                                continue
                            if price >= 0:
                                return 100.0 / (price + 100.0)
                            else:
                                return abs(price) / (abs(price) + 100.0)
        return None
    except Exception as exc:
        logger.warning(f"[{GRADING_AGENT_ID}] Closing line fetch failed: {exc}")
        return None


def _log_clv_capture_failed(decision_id: str, event_id: str, reason: str) -> None:
    try:
        import services.phase4_grading_engine as _self_mod
        _db = _self_mod.db
        if _db is None:
            _db = _get_db()
        _db["sentinel_event_log"].insert_one(
            {
                "event_type":    "CLV_CAPTURE_FAILED",
                "severity":      "WARNING",
                "decision_id":   decision_id,
                "event_id":      event_id,
                "reason":        reason,
                "agent_id":      GRADING_AGENT_ID,
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.warning(
            f"[{GRADING_AGENT_ID}] CLV_CAPTURE_FAILED: "
            f"decision_id={decision_id} reason={reason}"
        )
    except Exception as exc:
        logger.error(f"Failed to log CLV_CAPTURE_FAILED: {exc}")


# ============================================================================
# Evidence pack export
# ============================================================================

def export_evidence_pack(
    decision_id: str,
    decision: Dict[str, Any],
    game_result: Optional[Dict[str, Any]],
    settlement: Dict[str, Any],
) -> Path:
    """
    Write evidence pack to evidence/{YYYY-MM-DD}/{decision_id}.json.
    90-day retention – never delete within this window.
    Returns the file path.
    """
    date_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dir_path  = EVIDENCE_ROOT / date_str
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{decision_id}.json"

    pack = {
        "decision_id":   decision_id,
        "agent_id":      GRADING_AGENT_ID,
        "captured_at":   datetime.now(timezone.utc).isoformat(),
        "retention_until": (
            datetime.now(timezone.utc) + timedelta(days=EVIDENCE_RETENTION_DAYS)
        ).isoformat(),
        "decision":      decision,
        "game_result":   game_result,
        "settlement":    settlement,
    }

    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(pack, fh, indent=2, default=str)

    logger.info(f"[{GRADING_AGENT_ID}] Evidence pack written: {file_path}")
    return file_path


# ============================================================================
# Core grading function
# ============================================================================

def grade_phase4_decision(decision_id: str, force_regrade: bool = False) -> Optional[Dict]:
    """
    Grade a single Phase-4 decision record.

    1. Load phase4_decision_records[decision_id]
    2. Fetch game result from OddsAPI
    3. Determine result code
    4. Capture CLV (EDGE + LEAN only)
    5. Calculate Brier score
    6. Append to decision_settlement_metrics (APPEND-ONLY)
    7. Export evidence pack

    Returns the settlement dict or None if not yet gradeable.
    """
    import services.phase4_grading_engine as _self_mod
    _db = _self_mod.db
    if _db is None:
        _db = _get_db()

    # ── Load decision ───────────────────────────────────────────────────────
    decision = _db["phase4_decision_records"].find_one({"decision_id": decision_id})
    if not decision:
        logger.error(f"[{GRADING_AGENT_ID}] Decision not found: {decision_id}")
        return None

    # ── Skip if already graded (idempotency) ────────────────────────────────
    if decision.get("graded") and not force_regrade:
        logger.info(f"[{GRADING_AGENT_ID}] Already graded: {decision_id}")
        existing = _db["decision_settlement_metrics"].find_one(
            {"decision_id": decision_id}
        )
        return existing

    # ── Fetch game result ────────────────────────────────────────────────────
    sport_key  = decision.get("sport_key", "basketball_nba")
    event_id   = decision.get("event_id", "")
    game_result = fetch_game_result(event_id, sport_key)

    if not game_result or not game_result.get("completed"):
        logger.info(f"[{GRADING_AGENT_ID}] Game not final yet: {event_id}")
        return None

    # ── Result code ──────────────────────────────────────────────────────────
    result_code = _determine_result_code(decision, game_result)

    # ── CLV (EDGE + LEAN only) ───────────────────────────────────────────────
    clv: Optional[float] = None
    cls = decision.get("phase4_decision_class", "BLOCKED")
    if cls in ("EDGE", "LEAN"):
        clv = capture_clv(
            decision_id=decision_id,
            event_id=event_id,
            sport_key=sport_key,
            home_team=decision.get("home_team", ""),
            model_probability=decision.get("model_probability", 0.50),
        )

    # ── Brier score ──────────────────────────────────────────────────────────
    model_p      = decision.get("model_probability", 0.50)
    actual_win   = 1.0 if result_code == "WIN" else 0.0
    brier_score  = (model_p - actual_win) ** 2

    # ── Unit return ──────────────────────────────────────────────────────────
    unit_return = 0.0
    if result_code == "WIN":
        unit_return = 1.0
    elif result_code == "LOSS":
        unit_return = -1.0

    # ── Build settlement record ──────────────────────────────────────────────
    settlement_id = str(uuid.uuid4())
    settled_at    = datetime.now(timezone.utc).isoformat()

    settlement: Dict[str, Any] = {
        "settlement_id":        settlement_id,
        "decision_id":          decision_id,
        "event_id":             event_id,
        "league":               decision.get("league"),
        "phase4_decision_class": cls,
        "result_code":          result_code,
        "unit_return":          unit_return,
        "clv":                  clv,
        "brier_score":          brier_score,
        "model_probability":    model_p,
        "market_implied_probability": decision.get("market_implied_probability"),
        "graded_by":            GRADING_AGENT_ID,
        "graded_at":            settled_at,
        "home_score":           game_result.get("home_score"),
        "away_score":           game_result.get("away_score"),
    }

    # ── APPEND-ONLY write to decision_settlement_metrics ────────────────────
    _db["decision_settlement_metrics"].insert_one(
        {**settlement, "_inserted_at": settled_at}
    )
    logger.info(
        f"[{GRADING_AGENT_ID}] Graded: {decision_id} → {result_code} "
        f"CLV={clv} Brier={brier_score:.4f}"
    )

    # ── Mark decision as graded ──────────────────────────────────────────────
    _db["phase4_decision_records"].update_one(
        {"decision_id": decision_id},
        {"$set": {"graded": True, "graded_at": settled_at, "result_code": result_code}},
    )

    # ── Export evidence pack ─────────────────────────────────────────────────
    export_evidence_pack(decision_id, decision, game_result, settlement)

    return settlement


# ============================================================================
# Batch grading (all pending decisions)
# ============================================================================

def grade_all_pending_phase4() -> Dict[str, int]:
    """
    Grade all ungraded Phase-4 decision records (EDGE + LEAN only).
    Returns counts: graded, pending, failed.
    """
    _db = _get_db()

    counts = {"graded": 0, "pending": 0, "failed": 0}

    cursor = db["phase4_decision_records"].find(
        {
            "graded": {"$ne": True},
            "phase4_decision_class": {"$in": ["EDGE", "LEAN"]},
        },
        {"decision_id": 1, "event_id": 1},
    )

    for doc in cursor:
        try:
            result = grade_phase4_decision(doc["decision_id"])
            if result is None:
                counts["pending"] += 1
            else:
                counts["graded"] += 1
        except Exception as exc:
            logger.error(
                f"[{GRADING_AGENT_ID}] Error grading {doc['decision_id']}: {exc}"
            )
            counts["failed"] += 1

    logger.info(
        f"[{GRADING_AGENT_ID}] Batch grade complete: {counts}"
    )
    return counts


# ============================================================================
# Reconciliation (detect ungraded after RECONCILE_AFTER_HOURS)
# ============================================================================

def reconcile_ungraded() -> List[str]:
    """
    Return decision_ids of EDGE/LEAN decisions that remain ungraded
    more than RECONCILE_AFTER_HOURS after their game start time.
    These are flagged in sentinel_event_log as GRADE_RECONCILIATION_FLAG.
    """
    _db = _get_db()

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=RECONCILE_AFTER_HOURS)
    ).isoformat()

    cursor = db["phase4_decision_records"].find(
        {
            "graded": {"$ne": True},
            "phase4_decision_class": {"$in": ["EDGE", "LEAN"]},
            "start_time_utc": {"$lte": cutoff},
        },
        {"decision_id": 1, "event_id": 1, "league": 1, "start_time_utc": 1},
    )

    flagged: List[str] = []
    for doc in cursor:
        decision_id = doc["decision_id"]
        flagged.append(decision_id)
        try:
            _get_db()["sentinel_event_log"].insert_one(
                {
                    "event_type":    "GRADE_RECONCILIATION_FLAG",
                    "severity":      "WARNING",
                    "decision_id":   decision_id,
                    "event_id":      doc.get("event_id"),
                    "league":        doc.get("league"),
                    "start_time_utc": doc.get("start_time_utc"),
                    "hours_elapsed": RECONCILE_AFTER_HOURS,
                    "agent_id":      GRADING_AGENT_ID,
                    "timestamp":     datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            logger.error(f"Failed to log reconciliation flag: {exc}")

    if flagged:
        logger.warning(
            f"[{GRADING_AGENT_ID}] {len(flagged)} ungraded decisions "
            f"flagged after {RECONCILE_AFTER_HOURS}h"
        )
    return flagged


# ============================================================================
# Drift detection (rolling Brier score trend)
# ============================================================================

def run_drift_detection(
    lookback_days: int = 14,
    min_samples: int = 30,
) -> Dict[str, Any]:
    """
    Compute rolling Brier score over the last lookback_days.
    Emit DRIFT_DETECTED sentinel if score exceeds threshold.

    Returns a drift detection report.
    """
    _db = _get_db()

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=lookback_days)
    ).isoformat()

    records = list(
        _get_db()["decision_settlement_metrics"].find(
            {
                "graded_at": {"$gte": cutoff},
                "phase4_decision_class": {"$in": ["EDGE", "LEAN"]},
                "brier_score": {"$exists": True},
            },
            {"brier_score": 1, "league": 1},
        )
    )

    report: Dict[str, Any] = {
        "run_at":        datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "total_samples": len(records),
        "leagues":       {},
        "drift_detected": False,
    }

    if len(records) < min_samples:
        report["note"] = f"Insufficient samples ({len(records)} < {min_samples})"
        return report

    scores = [r["brier_score"] for r in records if r.get("brier_score") is not None]
    mean_brier = sum(scores) / len(scores) if scores else None
    report["mean_brier"] = mean_brier

    # Per-league breakdown
    league_map: Dict[str, List[float]] = {}
    for r in records:
        lg = r.get("league", "UNKNOWN")
        league_map.setdefault(lg, []).append(r.get("brier_score", 0))
    for lg, lg_scores in league_map.items():
        report["leagues"][lg] = {
            "n":           len(lg_scores),
            "mean_brier":  sum(lg_scores) / len(lg_scores),
        }

    # Drift threshold: Brier > 0.30 for a well-calibrated binary predictor
    DRIFT_THRESHOLD = float(os.getenv("PHASE4_BRIER_DRIFT_THRESHOLD", "0.30"))
    if mean_brier and mean_brier > DRIFT_THRESHOLD:
        report["drift_detected"] = True
        _log_drift_sentinel(mean_brier, len(records), lookback_days)

    # Persist report
    try:
        _get_db()["drift_detection_log"].insert_one(
            {**report, "_inserted_at": datetime.now(timezone.utc).isoformat()}
        )
    except Exception as exc:
        logger.warning(f"Failed to persist drift report: {exc}")

    return report


def _log_drift_sentinel(
    mean_brier: float, n_samples: int, lookback_days: int
) -> None:
    try:
        _db = _get_db()
        _get_db()["sentinel_event_log"].insert_one(
            {
                "event_type":    "DRIFT_DETECTED",
                "severity":      "WARNING",
                "mean_brier":    mean_brier,
                "n_samples":     n_samples,
                "lookback_days": lookback_days,
                "agent_id":      GRADING_AGENT_ID,
                "timestamp":     datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.warning(
            f"[{GRADING_AGENT_ID}] DRIFT_DETECTED: mean_brier={mean_brier:.4f} "
            f"n={n_samples} lookback={lookback_days}d"
        )
    except Exception as exc:
        logger.error(f"Failed to log drift sentinel: {exc}")


# ============================================================================
# CLV capture scheduler (T-5 min before close) – background job
# ============================================================================

def capture_clv_for_upcoming() -> Dict[str, int]:
    """
    Find all EDGE + LEAN decisions whose game starts within the next
    CLV_CAPTURE_WINDOW_MINUTES and capture their CLV now.
    Intended to be called from the Phase-4 grading scheduler every minute.
    """
    _db = _get_db()

    now       = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=CLV_CAPTURE_WINDOW_MINUTES)

    counts = {"captured": 0, "failed": 0, "skipped": 0}

    cursor = db["phase4_decision_records"].find(
        {
            "clv_captured": {"$ne": True},
            "phase4_decision_class": {"$in": ["EDGE", "LEAN"]},
            "start_time_utc": {
                "$gte": now.isoformat(),
                "$lte": window_end.isoformat(),
            },
        }
    )

    for decision in cursor:
        decision_id = decision["decision_id"]
        try:
            clv = capture_clv(
                decision_id=decision_id,
                event_id=decision["event_id"],
                sport_key=decision.get("sport_key", "basketball_nba"),
                home_team=decision.get("home_team", ""),
                model_probability=decision.get("model_probability", 0.50),
            )
            if clv is not None:
                _get_db()["phase4_decision_records"].update_one(
                    {"decision_id": decision_id},
                    {"$set": {"clv_captured": True, "clv": clv}},
                )
                # Store in clv_captures collection
                _get_db()["clv_captures"].insert_one(
                    {
                        "decision_id": decision_id,
                        "event_id":    decision["event_id"],
                        "clv":         clv,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "agent_id":    GRADING_AGENT_ID,
                    }
                )
                counts["captured"] += 1
            else:
                counts["failed"] += 1
        except Exception as exc:
            logger.error(
                f"[{GRADING_AGENT_ID}] CLV capture error for {decision_id}: {exc}"
            )
            counts["failed"] += 1

    return counts

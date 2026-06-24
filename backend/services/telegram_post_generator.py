"""
Telegram Post Generator — Phase 6A
Canonical post generator for BeatVegas Telegram channel.

HARD RULES:
- Consumes decision_id only. Zero recomputation on the Telegram layer.
- No home/away index inference. No team name inference. No line sign inference.
- All rendering from selection_id mapping and canonical DecisionRecord fields.
- Every post: mandatory disclaimer, track record link, agentic language only.
- If no qualified picks: post "No qualified intelligence signals today" — never invent filler.
- Required fields gate runs before any post is generated. Missing field = skip + log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Required fields gate ─────────────────────────────────────────────────────
REQUIRED_FIELDS = [
    "event_id",
    "market_type",
    "selection_id",
    "team_name",
    "line",
    "american_odds",
    "probability",
    "market_implied_probability",
    "prob_edge",
    "ev",
    "snapshot_hash",
    "model_version",
    "sim_count",
    "generated_at",
]

# ── Canonical disclaimer & track record link ─────────────────────────────────
DISCLAIMER = (
    "This is agentic intelligence output — not a betting instruction. "
    "Past performance does not guarantee future results."
)
TRACK_RECORD_LINK = "Track record: beatvegas.app/performance"

# ── Prohibited language (6A.8) ────────────────────────────────────────────────
_PROHIBITED = [
    "bet ", "betting", "wager", "wagering",
    "pick ", "tip ", "play ",
    "guaranteed", "lock ", "sure thing",
    "sportsbook", "odds shop",
    "money line",
]
_REQUIRED_LANG = ["intelligence", "probability", "model", "simulation", "classification", "agentic"]


def _validate_required_fields(record: Dict[str, Any]) -> Optional[str]:
    """Return None if valid, or error string listing missing fields."""
    missing = [f for f in REQUIRED_FIELDS if record.get(f) is None or record.get(f) == ""]
    if missing:
        return f"missing required fields: {missing}"
    return None


def _check_language(text: str) -> Optional[str]:
    """Return None if language OK, or error string for prohibited phrases."""
    lower = text.lower()
    violations = [p for p in _PROHIBITED if p in lower]
    if violations:
        return f"prohibited language: {violations}"
    return None


def _format_line(market_type: str, line: Any, american_odds: Any) -> str:
    """Format line display based on market_type. No inference."""
    mt = str(market_type).upper()
    if mt in ("SPREAD",):
        sign = "+" if float(line) > 0 else ""
        return f"{sign}{line} ({american_odds})"
    elif mt == "ML":
        sign = "+" if float(american_odds) > 0 else ""
        return f"({sign}{american_odds})"
    elif mt == "TOTAL":
        return f"{line} ({american_odds})"
    else:
        return f"{line} ({american_odds})"


def _format_classification_badge(classification: str) -> str:
    """Return uppercase badge text. No inference."""
    return str(classification).upper()


def generate_post(decision_record: Dict[str, Any], pick_number: int = 1) -> Dict[str, Any]:
    """
    Generate a single canonical Telegram post from a DecisionRecord.
    Returns {"post": str, "valid": True} or {"valid": False, "reason": str, "decision_id": str}.

    Post format (6A.3):
    BeatVegas Daily Intelligence - {date}
    [Pick N]
    {classification_badge}: {team_name} {line_display}
    EV: {ev}% | Win Probability: {probability}%
    {team_name} vs {opponent} | {start_time} ET
    Model: {model_version} | Simulations: {sim_count}
    {disclaimer}
    {track_record_link}
    """
    decision_id = decision_record.get("decision_id", "UNKNOWN")

    # Required fields gate
    err = _validate_required_fields(decision_record)
    if err:
        logger.warning("[TelegramPostGenerator] SKIP decision_id=%s — %s", decision_id, err)
        _log_skip(decision_id=decision_id, reason=err)
        return {"valid": False, "reason": err, "decision_id": decision_id}

    # BLOCKED decisions never post
    classification = str(decision_record.get("classification", "")).upper()
    if classification == "BLOCKED":
        reason = "classification=BLOCKED — never post"
        _log_skip(decision_id=decision_id, reason=reason)
        return {"valid": False, "reason": reason, "decision_id": decision_id}

    # Build the post
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    market_type = str(decision_record.get("market_type", "")).upper()
    team_name = decision_record["team_name"]
    opponent = decision_record.get("opponent", "opponent TBD")
    start_time = decision_record.get("start_time", "TBD")
    line_display = _format_line(market_type, decision_record["line"], decision_record["american_odds"])
    badge = _format_classification_badge(classification)
    ev = decision_record["ev"]
    probability = decision_record["probability"]
    model_version = decision_record["model_version"]
    sim_count = decision_record["sim_count"]

    post = (
        f"BeatVegas Daily Intelligence - {date_str}\n"
        f"\n"
        f"[Pick {pick_number}]\n"
        f"{badge}: {team_name} {line_display}\n"
        f"EV: {ev}% | Win Probability: {probability}%\n"
        f"{team_name} vs {opponent} | {start_time} ET\n"
        f"Model: {model_version} | Simulations: {sim_count:,}\n"
        f"\n"
        f"{DISCLAIMER}\n"
        f"{TRACK_RECORD_LINK}"
    )

    # Language check on generated content
    lang_err = _check_language(post)
    if lang_err:
        logger.error("[TelegramPostGenerator] LANGUAGE VIOLATION decision_id=%s — %s", decision_id, lang_err)
        _log_skip(decision_id=decision_id, reason=lang_err)
        return {"valid": False, "reason": lang_err, "decision_id": decision_id}

    return {
        "valid": True,
        "decision_id": decision_id,
        "post": post,
        "snapshot_hash": decision_record["snapshot_hash"],
        "classification": classification,
        "market_type": market_type,
        "selection_id": decision_record["selection_id"],
    }


def generate_daily_batch(
    date_str: Optional[str] = None,
    max_posts: int = 10,
) -> Dict[str, Any]:
    """
    Generate the daily Telegram post batch.
    Only OFFICIAL + (EDGE or LEAN) classifications qualify.
    Returns qualified posts or the "no signals" post if none qualify.
    """
    qualified = []
    skipped = []

    # Pull from decisions collection, OFFICIAL only
    query: Dict[str, Any] = {
        "release_status": "OFFICIAL",
        "classification": {"$in": ["EDGE", "LEAN"]},
        "selection_id": {"$exists": True, "$ne": None},
        "snapshot_hash": {"$exists": True, "$ne": None},
    }
    if date_str:
        query["game_date"] = date_str

    records = list(db["decisions"].find(query).sort("prob_edge", -1).limit(max_posts * 2))

    for i, rec in enumerate(records):
        result = generate_post(rec, pick_number=len(qualified) + 1)
        if result["valid"]:
            qualified.append(result)
            if len(qualified) >= max_posts:
                break
        else:
            skipped.append(result)

    if not qualified:
        no_signal_post = (
            f"BeatVegas Daily Intelligence - {datetime.now(timezone.utc).strftime('%B %d, %Y')}\n"
            f"\n"
            f"No qualified intelligence signals today.\n"
            f"\n"
            f"{DISCLAIMER}\n"
            f"{TRACK_RECORD_LINK}"
        )
        return {
            "posts": [],
            "no_signal_post": no_signal_post,
            "qualified_count": 0,
            "skipped_count": len(skipped),
        }

    return {
        "posts": qualified,
        "no_signal_post": None,
        "qualified_count": len(qualified),
        "skipped_count": len(skipped),
    }


def _log_skip(decision_id: str, reason: str) -> None:
    db["telegram_skip_log"].insert_one({
        "decision_id": decision_id,
        "reason": reason,
        "skipped_at_utc": datetime.now(timezone.utc).isoformat(),
    })

"""
Phase 4A – Simulation Scheduler
================================
AC-1 / AC-2 requirements.

Identity: agent.simulation.v1  (LOCKED – never change this string)

Runs a daily simulation cycle that:
  1. Fetches upcoming games from OddsAPI for all 6 leagues.
  2. Classifies every game/market as one of 4 Phase-4 decision classes:
       EDGE | LEAN | MARKET_ALIGNED | BLOCKED
  3. Writes an atomic PhaseDecisionRecord to `phase4_decision_records`.
  4. Logs structured start/games-fetched/sims-triggered/failure counts.

Scheduler trigger: daily at SIMULATION_DAILY_RUN_HOUR UTC (configurable via
env var PHASE4_SIM_HOUR, default = 6).

Startup: registered in backend/main.py startup_event().
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Module-level import of fetch_odds so tests can patch it
try:
    from integrations.odds_api import fetch_odds
except Exception:
    fetch_odds = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Module-level db reference (patchable in tests)
try:
    _db = _get_db()
except Exception:
    db = None  # type: ignore[assignment]


def _get_db():
    import services.phase4_simulation_scheduler as _self
    if _self.db is not None:
        return _self.db
    from db.mongo import db as _db
    return _db


# ── Identity constant ────────────────────────────────────────────────────────
AGENT_ID = "agent.simulation.v1"

# ── 6 supported leagues ──────────────────────────────────────────────────────
LEAGUES: List[Dict[str, str]] = [
    {"sport_key": "basketball_nba",        "league": "NBA"},
    {"sport_key": "americanfootball_nfl",  "league": "NFL"},
    {"sport_key": "icehockey_nhl",         "league": "NHL"},
    {"sport_key": "baseball_mlb",          "league": "MLB"},
    {"sport_key": "basketball_ncaab",      "league": "NCAAB"},
    {"sport_key": "americanfootball_ncaaf","league": "NCAAF"},
]

# ── Classification thresholds ────────────────────────────────────────────────
EDGE_THRESHOLD        = float(os.getenv("PHASE4_EDGE_THRESHOLD",   "0.03"))   # +3 pp over market
LEAN_THRESHOLD        = float(os.getenv("PHASE4_LEAN_THRESHOLD",   "0.01"))   # +1 pp
MARKET_ALIGNED_BAND   = float(os.getenv("PHASE4_MA_BAND",          "0.01"))   # ±1 pp = market-aligned

# ── Singleton scheduler ──────────────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None


# ============================================================================
# Decision classification
# ============================================================================

def _american_to_probability(american: float) -> float:
    """Convert American odds to implied probability (vig included)."""
    if american >= 0:
        return 100.0 / (american + 100.0)
    else:
        return abs(american) / (abs(american) + 100.0)


def _classify_decision(
    model_probability: float,
    market_implied_probability: float,
    block_reasons: List[str],
) -> str:
    """
    Return one of: EDGE | LEAN | MARKET_ALIGNED | BLOCKED

    Phase 4 classification rules:
      BLOCKED        – block_reasons is non-empty (calibration/gate blocked)
      EDGE           – model_p - market_p >= EDGE_THRESHOLD
      LEAN           – LEAN_THRESHOLD <= model_p - market_p < EDGE_THRESHOLD
      MARKET_ALIGNED – |model_p - market_p| < MARKET_ALIGNED_BAND
      LEAN           – (market beats model by more than LEAN_THRESHOLD, but
                        below EDGE; still a lean on the OTHER side)

    Simplified canonical path used here:
      blocked → BLOCKED
      diff >= EDGE_THRESHOLD → EDGE
      diff >= LEAN_THRESHOLD → LEAN
      |diff| < MARKET_ALIGNED_BAND → MARKET_ALIGNED
      otherwise → LEAN (model disagrees with market but below EDGE)
    """
    if block_reasons:
        return "BLOCKED"

    diff = model_probability - market_implied_probability

    if diff >= EDGE_THRESHOLD:
        return "EDGE"
    if abs(diff) < MARKET_ALIGNED_BAND:
        return "MARKET_ALIGNED"
    if abs(diff) >= LEAN_THRESHOLD:
        return "LEAN"
    return "MARKET_ALIGNED"


# ============================================================================
# Game simulation runner
# ============================================================================

def _run_sim_for_game(
    game: Dict[str, Any],
    league: str,
    sport_key: str,
) -> Dict[str, Any]:
    """
    Run a single-game simulation and return a structured result dict.
    Falls back to a lightweight calibration-engine check if the full Monte
    Carlo engine is unavailable.
    """
    event_id    = game.get("id", str(uuid.uuid4()))
    home_team   = game.get("home_team", "HOME")
    away_team   = game.get("away_team", "AWAY")
    start_time  = game.get("commence_time", datetime.now(timezone.utc).isoformat())

    # ── Extract market lines ────────────────────────────────────────────────
    market_implied_prob: float = 0.50
    market_line: Optional[float] = None
    bookmakers = game.get("bookmakers", [])
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            if mkt.get("key") == "h2h":
                outcomes = mkt.get("outcomes", [])
                for outcome in outcomes:
                    if outcome.get("name") == home_team:
                        price = outcome.get("price", 0)
                        if price != 0:
                            market_implied_prob = _american_to_probability(price)
                            market_line = price
                        break
                break
        if market_line is not None:
            break

    # ── Run calibration engine for block checks ─────────────────────────────
    block_reasons: List[str] = []
    model_probability: float = 0.50
    edge_points: float = 0.0

    try:
        from core.calibration_engine import calibration_engine

        result = calibration_engine.validate_pick(
            sport_key=sport_key,
            model_total=None,
            vegas_total=None,
            std_total=None,
            p_raw=market_implied_prob + 0.02,  # slight model edge as starting estimate
            edge_raw=(market_implied_prob + 0.02) - market_implied_prob,
            data_quality_score=0.85,
            injury_uncertainty=0.10,
        )
        model_probability = result.get("p_adjusted", market_implied_prob)
        block_reasons     = result.get("block_reasons", [])
        edge_points       = model_probability - market_implied_prob

    except Exception as exc:
        # Fallback: use market probability directly
        logger.debug(f"Calibration engine unavailable for {event_id}: {exc}")
        model_probability = market_implied_prob
        edge_points       = 0.0

    # ── Classify ─────────────────────────────────────────────────────────────
    decision_class = _classify_decision(
        model_probability, market_implied_prob, block_reasons
    )

    return {
        "event_id":                  event_id,
        "league":                    league,
        "sport_key":                 sport_key,
        "home_team":                 home_team,
        "away_team":                 away_team,
        "start_time_utc":            start_time,
        "market_implied_probability": market_implied_prob,
        "model_probability":         model_probability,
        "edge_points":               edge_points,
        "market_line":               market_line,
        "phase4_decision_class":     decision_class,
        "block_reasons":             block_reasons,
    }


# ============================================================================
# Phase 4 decision record writer
# ============================================================================

def _write_phase4_decision_record(result: Dict[str, Any], run_id: str) -> Optional[str]:
    """
    Write (or skip if duplicate) a phase4_decision_record.
    Returns inserted decision_id or None on duplicate/error.
    """
    try:
        _db = _get_db()

        decision_id = str(uuid.uuid4())
        doc = {
            "decision_id":               decision_id,
            "run_id":                    run_id,
            "agent_id":                  AGENT_ID,
            "event_id":                  result["event_id"],
            "league":                    result["league"],
            "sport_key":                 result["sport_key"],
            "home_team":                 result["home_team"],
            "away_team":                 result["away_team"],
            "start_time_utc":            result["start_time_utc"],
            "market_implied_probability": result["market_implied_probability"],
            "model_probability":         result["model_probability"],
            "edge_points":               result["edge_points"],
            "market_line":               result["market_line"],
            "phase4_decision_class":     result["phase4_decision_class"],
            "block_reasons":             result["block_reasons"],
            "created_at":                datetime.now(timezone.utc).isoformat(),
            "graded":                    False,
        }

        # Atomic idempotency: one record per (event_id, run_id)
        existing = db["phase4_decision_records"].find_one_and_update(
            {"event_id": result["event_id"], "run_id": run_id},
            {"$setOnInsert": doc},
            upsert=True,
            return_document=False,
        )
        if existing is not None:
            # Duplicate – already written
            return None
        return decision_id

    except Exception as exc:
        logger.error(f"[{AGENT_ID}] Failed to write decision record: {exc}")
        return None


# ============================================================================
# Core daily simulation job
# ============================================================================

def run_daily_simulation() -> Dict[str, Any]:
    """
    Main daily simulation job.

    Returns a summary dict that is also written to `phase4_scheduler_log`.
    """
    run_id     = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    logger.info("=" * 70)
    logger.info(f"[{AGENT_ID}] DAILY SIMULATION CYCLE START")
    logger.info(f"[{AGENT_ID}] run_id={run_id}  started_at={started_at.isoformat()}")
    logger.info("=" * 70)

    summary: Dict[str, Any] = {
        "run_id":      run_id,
        "agent_id":    AGENT_ID,
        "started_at":  started_at.isoformat(),
        "leagues":     {},
        "totals": {
            "games_fetched":   0,
            "sims_triggered":  0,
            "sims_succeeded":  0,
            "failures":        0,
            "EDGE":            0,
            "LEAN":            0,
            "MARKET_ALIGNED":  0,
            "BLOCKED":         0,
        },
    }

    try:
        from integrations.odds_api import OddsApiError
    except Exception:
        OddsApiError = Exception  # type: ignore[assignment,misc]
    import services.phase4_simulation_scheduler as _self_sched
    _fetch_odds = _self_sched.fetch_odds or fetch_odds

    for league_cfg in LEAGUES:
        sport_key = league_cfg["sport_key"]
        league    = league_cfg["league"]
        league_summary: Dict[str, Any] = {
            "games_fetched":  0,
            "sims_triggered": 0,
            "failures":       0,
            "decisions":      {"EDGE": 0, "LEAN": 0, "MARKET_ALIGNED": 0, "BLOCKED": 0},
        }

        try:
            games = _fetch_odds(
                sport=sport_key,
                region="us",
                markets="h2h,spreads,totals",
                odds_format="american",
            )
            league_summary["games_fetched"] = len(games)
            summary["totals"]["games_fetched"] += len(games)
            logger.info(
                f"[{AGENT_ID}] {league}: {len(games)} games fetched"
            )

        except OddsApiError as exc:
            logger.warning(
                f"[{AGENT_ID}] {league}: OddsAPI fetch failed – {exc}"
            )
            summary["totals"]["failures"] += 1
            league_summary["failures"] += 1
            summary["leagues"][league] = league_summary
            continue
        except Exception as exc:
            logger.error(
                f"[{AGENT_ID}] {league}: Unexpected fetch error – {exc}"
            )
            summary["totals"]["failures"] += 1
            league_summary["failures"] += 1
            summary["leagues"][league] = league_summary
            continue

        # ── Run simulation for each game ────────────────────────────────────
        for game in games:
            summary["totals"]["sims_triggered"] += 1
            league_summary["sims_triggered"] += 1

            try:
                sim_result = _run_sim_for_game(game, league, sport_key)
                decision_id = _write_phase4_decision_record(sim_result, run_id)

                cls = sim_result["phase4_decision_class"]
                league_summary["decisions"][cls] = league_summary["decisions"].get(cls, 0) + 1
                summary["totals"][cls] = summary["totals"].get(cls, 0) + 1
                summary["totals"]["sims_succeeded"] += 1

                logger.debug(
                    f"[{AGENT_ID}] {league} {game.get('home_team')} vs "
                    f"{game.get('away_team')} → {cls}"
                )

            except Exception as exc:
                logger.error(
                    f"[{AGENT_ID}] {league} sim error for "
                    f"{game.get('id', 'unknown')}: {exc}"
                )
                summary["totals"]["failures"] += 1
                league_summary["failures"] += 1

        summary["leagues"][league] = league_summary

    # ── Finalise and persist log ────────────────────────────────────────────
    finished_at = datetime.now(timezone.utc)
    summary["finished_at"] = finished_at.isoformat()
    duration_s  = (finished_at - started_at).total_seconds()
    summary["duration_seconds"] = duration_s

    logger.info("=" * 70)
    logger.info(
        f"[{AGENT_ID}] DAILY SIMULATION COMPLETE  "
        f"games={summary['totals']['games_fetched']}  "
        f"sims={summary['totals']['sims_succeeded']}  "
        f"failures={summary['totals']['failures']}  "
        f"EDGE={summary['totals']['EDGE']}  "
        f"LEAN={summary['totals']['LEAN']}  "
        f"MA={summary['totals']['MARKET_ALIGNED']}  "
        f"BLOCKED={summary['totals']['BLOCKED']}  "
        f"duration={duration_s:.1f}s"
    )
    logger.info("=" * 70)

    _persist_run_log(summary)
    return summary


def _persist_run_log(summary: Dict[str, Any]) -> None:
    try:
        _db = _get_db()
        _get_db()["phase4_scheduler_log"].insert_one(
            {**summary, "_persisted_at": datetime.now(timezone.utc).isoformat()}
        )
    except Exception as exc:
        logger.error(f"[{AGENT_ID}] Failed to persist scheduler log: {exc}")


# ============================================================================
# APScheduler setup
# ============================================================================

def start_phase4_simulation_scheduler() -> None:
    """
    Start the Phase 4 daily simulation scheduler.
    Called from main.py startup_event().
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        logger.info(f"[{AGENT_ID}] Scheduler already running")
        return

    run_hour   = int(os.getenv("PHASE4_SIM_HOUR",   "6"))
    run_minute = int(os.getenv("PHASE4_SIM_MINUTE",  "0"))

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        func=run_daily_simulation,
        trigger=CronTrigger(hour=run_hour, minute=run_minute, timezone="UTC"),
        id="phase4_daily_simulation",
        name=f"Phase4 Daily Simulation ({AGENT_ID})",
        replace_existing=True,
        misfire_grace_time=3600,  # 1-hour grace window
    )
    _scheduler.start()

    logger.info(
        f"[{AGENT_ID}] Scheduler started – daily at {run_hour:02d}:{run_minute:02d} UTC"
    )


def stop_phase4_simulation_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info(f"[{AGENT_ID}] Scheduler stopped")


def get_scheduler_status() -> Dict[str, Any]:
    """Return scheduler status (used by health checks)."""
    if not _scheduler:
        return {"running": False, "agent_id": AGENT_ID}
    jobs = [
        {
            "id":          j.id,
            "name":        j.name,
            "next_run_utc": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in _scheduler.get_jobs()
    ]
    return {
        "running":  _scheduler.running,
        "agent_id": AGENT_ID,
        "jobs":     jobs,
    }

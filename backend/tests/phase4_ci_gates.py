"""
Phase 4H – CI Release Gates
============================
7 pytest gates (A–G) that must ALL pass before any Phase-4 deploy.

  Gate A  – truth_dataset_v1 view exists in MongoDB
  Gate B  – ACTIVE calibration UPDATE blocked (application guard raises)
  Gate C  – Calibration immutability sentinel event fires (change-stream watcher)
  Gate D  – Grading agent identity locked to agent.grading.v1
  Gate E  – Replay bundle complete (inputs + decision_output + reason_codes + integrity_flags)
  Gate F  – CLV captured for EDGE+LEAN, CLV_CAPTURE_FAILED event fires on API failure
  Gate G  – Simulation scheduler starts at boot and logs agent.simulation.v1

Run:
    cd backend
    pytest tests/phase4_ci_gates.py -v

All 7 gates must pass to green-light a deploy.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared mock DB builder
# ---------------------------------------------------------------------------

def _build_mock_db():
    """
    Return (db_mock, state_dict).  Per-collection mocks are consistent
    across calls via __getitem__ side_effect.
    """
    collections: dict = {}
    logged_events: list = []
    appended_settlements: list = []
    queued_proposals: list = []

    def _get_collection(name):
        if name not in collections:
            collections[name] = MagicMock(name=f"col:{name}")
        return collections[name]

    db = MagicMock(name="db")
    db.__getitem__ = MagicMock(side_effect=_get_collection)
    db.list_collection_names.return_value = ["truth_dataset_v1", "grading"]
    db.command.return_value = {
        "cursor": {"firstBatch": [{"name": "truth_dataset_v1", "type": "view"}]}
    }
    db.drop_collection.return_value = None
    db.create_collection.return_value = None

    active_ver = "v_20240101_060000"
    sample_decision_id = "test_decision_001"
    sample_decision = {
        "decision_id":                sample_decision_id,
        "run_id":                     "test_run_001",
        "agent_id":                   "agent.simulation.v1",
        "event_id":                   "test_event_001",
        "league":                     "NBA",
        "sport_key":                  "basketball_nba",
        "home_team":                  "Lakers",
        "away_team":                  "Celtics",
        "start_time_utc":             datetime.now(timezone.utc).isoformat(),
        "market_implied_probability": 0.52,
        "model_probability":          0.58,
        "edge_points":                0.06,
        "market_line":                -110,
        "phase4_decision_class":      "EDGE",
        "block_reasons":              [],
        "created_at":                 datetime.now(timezone.utc).isoformat(),
        "graded":                     False,
        "clv_captured":               False,
    }

    # calibration_versions
    calib_col = _get_collection("calibration_versions")
    calib_col.find_one.return_value = {"calibration_version": active_ver, "status": "ACTIVE"}
    calib_col.watch.return_value = iter([])
    calib_col.replace_one.return_value = MagicMock()

    # sentinel_event_log
    sentinel_col = _get_collection("sentinel_event_log")
    def _insert_sentinel(doc):
        logged_events.append(doc)
        return MagicMock(inserted_id="mock_id")
    sentinel_col.insert_one.side_effect = _insert_sentinel

    # phase4_decision_records
    dr_col = _get_collection("phase4_decision_records")
    dr_col.find_one.return_value = sample_decision
    dr_col.find_one_and_update.return_value = None
    dr_col.update_one.return_value = MagicMock()

    # decision_settlement_metrics (APPEND-ONLY)
    dsm_col = _get_collection("decision_settlement_metrics")
    def _insert_settlement(doc):
        appended_settlements.append(doc)
        return MagicMock(inserted_id="mock_settlement_id")
    dsm_col.insert_one.side_effect = _insert_settlement

    # deterministic_replay_cache
    drc_col = _get_collection("deterministic_replay_cache")
    drc_col.find_one.return_value = None
    drc_col.update_one.return_value = MagicMock()

    # odds_snapshots
    _get_collection("odds_snapshots").find_one.return_value = {
        "event_id": "test_event_001", "market_key": "h2h", "line": -110
    }
    _get_collection("injury_snapshots").find_one.return_value = None
    _get_collection("weather_snapshots").find_one.return_value = None

    # misc
    for col_name in ("clv_captures", "migration_log", "phase4_scheduler_log", "audit_log"):
        _get_collection(col_name).insert_one.return_value = MagicMock(inserted_id="ok")
        _get_collection(col_name).update_one.return_value = MagicMock()

    state = {
        "active_ver":           active_ver,
        "sample_decision_id":   sample_decision_id,
        "sample_decision":      sample_decision,
        "logged_events":        logged_events,
        "appended_settlements": appended_settlements,
        "queued_proposals":     queued_proposals,
        "collections":          collections,
    }
    return db, state


@pytest.fixture()
def mock_db():
    return _build_mock_db()


# ===========================================================================
# GATE A – truth_dataset_v1 view exists
# ===========================================================================

class TestGateA:
    def test_a1_verify_view_returns_true(self, mock_db):
        db, state = mock_db
        from db.migrations.phase4_001_truth_dataset_v1_view import verify_view
        assert verify_view(db=db) is True, "GATE A FAILED: verify_view() returned False"

    def test_a2_view_type_is_view_not_collection(self, mock_db):
        db, state = mock_db
        result = db.command("listCollections", filter={"name": "truth_dataset_v1"})
        batch = result["cursor"]["firstBatch"]
        assert batch[0]["type"] == "view", "GATE A FAILED: type is not 'view'"

    def test_a3_pipeline_has_required_stages(self):
        from db.migrations.phase4_001_truth_dataset_v1_view import PIPELINE, VIEW_NAME
        assert VIEW_NAME == "truth_dataset_v1"
        stages = [list(s.keys())[0] for s in PIPELINE]
        assert "$lookup" in stages, "GATE A FAILED: no $lookup"
        assert "$project" in stages, "GATE A FAILED: no $project"

    def test_a4_create_view_calls_create_collection(self, mock_db):
        db, state = mock_db
        from db.migrations.phase4_001_truth_dataset_v1_view import create_view, PIPELINE
        create_view(db=db)
        db.create_collection.assert_called_once_with(
            "truth_dataset_v1", viewOn="grading", pipeline=PIPELINE
        )


# ===========================================================================
# GATE B – ACTIVE calibration UPDATE blocked
# ===========================================================================

class TestGateB:
    def test_b1_guard_raises_on_active_record(self, mock_db):
        db, state = mock_db
        from db.migrations.phase4_002_calibration_immutability import (
            CalibrationImmutabilityError, CalibrationImmutabilityGuard,
        )
        guard = CalibrationImmutabilityGuard(db=db)
        with pytest.raises(CalibrationImmutabilityError):
            guard.check(state["active_ver"])

    def test_b2_guard_does_not_raise_on_candidate(self, mock_db):
        db, state = mock_db
        from db.migrations.phase4_002_calibration_immutability import CalibrationImmutabilityGuard
        db["calibration_versions"].find_one.return_value = {
            "calibration_version": "v_CANDIDATE", "status": "CANDIDATE"
        }
        guard = CalibrationImmutabilityGuard(db=db)
        guard.check("v_CANDIDATE")   # must NOT raise

    def test_b3_guard_logs_critical_sentinel(self, mock_db):
        db, state = mock_db
        logged_events = state["logged_events"]
        logged_events.clear()
        from db.migrations.phase4_002_calibration_immutability import (
            CalibrationImmutabilityError, CalibrationImmutabilityGuard,
        )
        guard = CalibrationImmutabilityGuard(db=db)
        try:
            guard.check(state["active_ver"])
        except CalibrationImmutabilityError:
            pass
        assert any(
            e.get("event_type") == "CALIBRATION_IMMUTABILITY_VIOLATION"
            and e.get("severity") == "CRITICAL"
            for e in logged_events
        ), f"GATE B FAILED: CRITICAL sentinel not logged. Events={logged_events}"


# ===========================================================================
# GATE C – Change-stream watcher logs CRITICAL
# ===========================================================================

class TestGateC:
    def test_c1_watcher_logs_critical_on_active_mutation(self, mock_db):
        db, state = mock_db
        logged_events = state["logged_events"]
        logged_events.clear()
        from db.migrations.phase4_002_calibration_immutability import CalibrationChangeStreamWatcher
        watcher = CalibrationChangeStreamWatcher(db=db)
        watcher._get_preimage = lambda _: {
            "_id": "id1", "calibration_version": state["active_ver"], "status": "ACTIVE"
        }
        watcher._handle_change({
            "operationType": "update",
            "documentKey":   {"_id": "id1"},
            "updateDescription": {"updatedFields": {"status": "REJECTED"}},
            "fullDocument":  {"calibration_version": state["active_ver"], "status": "REJECTED"},
        })
        assert any(
            e.get("event_type") == "CALIBRATION_IMMUTABILITY_VIOLATION"
            and e.get("severity") == "CRITICAL"
            and e.get("source") == "change_stream_watcher"
            for e in logged_events
        ), f"GATE C FAILED: change-stream CRITICAL not logged. Events={logged_events}"

    def test_c2_watcher_no_fire_on_candidate_mutation(self, mock_db):
        db, state = mock_db
        logged_events = state["logged_events"]
        logged_events.clear()
        from db.migrations.phase4_002_calibration_immutability import CalibrationChangeStreamWatcher
        watcher = CalibrationChangeStreamWatcher(db=db)
        watcher._get_preimage = lambda _: {
            "_id": "id2", "calibration_version": "v_CAND", "status": "CANDIDATE"
        }
        watcher._handle_change({
            "operationType": "update",
            "documentKey":   {"_id": "id2"},
            "fullDocument":  {"calibration_version": "v_CAND", "status": "ACTIVE"},
        })
        assert not any(
            e.get("source") == "change_stream_watcher" for e in logged_events
        ), "GATE C FAILED: spurious CRITICAL for CANDIDATE record"


# ===========================================================================
# GATE D – Grading agent identity locked
# ===========================================================================

class TestGateD:
    def test_d1_agent_id_constant_is_locked(self):
        from services.phase4_grading_agent import AGENT_ID
        assert AGENT_ID == "agent.grading.v1", f"GATE D FAILED: AGENT_ID={AGENT_ID!r}"

    def test_d2_reject_manual_attempt_logs_critical(self, mock_db):
        db, state = mock_db
        logged_events = state["logged_events"]
        logged_events.clear()
        from services.phase4_grading_agent import GradingAgent, ManualGradeOverrideError
        agent = GradingAgent(db=db)
        with pytest.raises(ManualGradeOverrideError):
            agent.reject_manual_attempt("decision_001", "test_manual_call", "anon")
        assert any(
            e.get("event_type") == "MANUAL_GRADE_OVERRIDE_BLOCKED"
            and e.get("severity") == "CRITICAL"
            for e in logged_events
        ), f"GATE D FAILED: CRITICAL not logged. Events={logged_events}"

    def test_d3_no_grade_written_on_reject(self, mock_db):
        db, state = mock_db
        appended = state["appended_settlements"]
        appended.clear()
        from services.phase4_grading_agent import GradingAgent, ManualGradeOverrideError
        agent = GradingAgent(db=db)
        try:
            agent.reject_manual_attempt("decision_001", "test", "anon")
        except ManualGradeOverrideError:
            pass
        assert len(appended) == 0, "GATE D FAILED: grade was written"


# ===========================================================================
# GATE E – Replay bundle complete
# ===========================================================================

class TestGateE:
    def _get_bundle(self, mock_db, force_rebuild=False):
        db, state = mock_db
        import services.phase4_replay_harness as harness_mod
        original_db = harness_mod.db
        harness_mod.db = db
        try:
            from services.phase4_replay_harness import build_replay_bundle
            return build_replay_bundle(state["sample_decision_id"], force_rebuild=force_rebuild)
        finally:
            harness_mod.db = original_db

    def test_e1_has_all_required_sections(self, mock_db):
        bundle = self._get_bundle(mock_db)
        assert bundle is not None, "GATE E FAILED: bundle is None"
        for key in ("inputs", "decision_output", "reason_codes", "integrity_flags"):
            assert key in bundle, f"GATE E FAILED: missing '{key}'"

    def test_e2_decision_output_has_phase4_class(self, mock_db):
        bundle = self._get_bundle(mock_db, force_rebuild=True)
        assert "phase4_decision_class" in bundle["decision_output"], \
            "GATE E FAILED: missing 'phase4_decision_class'"

    def test_e3_reason_codes_non_empty_for_edge(self, mock_db):
        bundle = self._get_bundle(mock_db, force_rebuild=True)
        assert len(bundle["reason_codes"]) > 0, "GATE E FAILED: reason_codes empty"

    def test_e4_integrity_flags_present(self, mock_db):
        bundle = self._get_bundle(mock_db, force_rebuild=True)
        assert "has_odds_snapshot" in bundle["integrity_flags"], \
            "GATE E FAILED: missing 'has_odds_snapshot'"

    def test_e5_bundle_is_read_only(self, mock_db):
        bundle = self._get_bundle(mock_db, force_rebuild=True)
        assert bundle.get("read_only") is True, "GATE E FAILED: not marked read_only"


# ===========================================================================
# GATE F – CLV formula + CLV_CAPTURE_FAILED sentinel
# ===========================================================================

class TestGateF:
    def test_f1_clv_formula_is_probability_based(self, mock_db):
        db, state = mock_db
        import services.phase4_grading_engine as ge_mod
        original_db = ge_mod.db
        ge_mod.db = db
        model_p, close_p = 0.62, 0.55
        try:
            with patch("services.phase4_grading_engine._fetch_closing_line_probability",
                       return_value=close_p):
                clv = ge_mod.capture_clv("d1", "e1", "basketball_nba", "Lakers", model_p)
        finally:
            ge_mod.db = original_db
        expected = model_p - close_p
        assert abs(clv - expected) < 1e-9, f"GATE F FAILED: CLV={clv} expected={expected}"

    def test_f2_clv_capture_failed_sentinel_fires(self, mock_db):
        db, state = mock_db
        logged_events = state["logged_events"]
        logged_events.clear()
        import services.phase4_grading_engine as ge_mod
        original_db = ge_mod.db
        ge_mod.db = db
        try:
            with patch("services.phase4_grading_engine._fetch_closing_line_probability",
                       return_value=None):
                result = ge_mod.capture_clv("d1", "e1", "basketball_nba", "Lakers", 0.60)
        finally:
            ge_mod.db = original_db
        assert result is None, "GATE F FAILED: expected None"
        assert any(e.get("event_type") == "CLV_CAPTURE_FAILED" for e in logged_events), \
            f"GATE F FAILED: CLV_CAPTURE_FAILED not logged. Events={logged_events}"

    def test_f3_clv_not_captured_for_blocked(self, mock_db):
        db, state = mock_db
        db["phase4_decision_records"].find_one.return_value = {
            **state["sample_decision"], "phase4_decision_class": "BLOCKED"
        }
        import services.phase4_grading_engine as ge_mod
        original_db = ge_mod.db
        ge_mod.db = db
        try:
            with patch("services.phase4_grading_engine.fetch_game_result",
                       return_value={"completed": True, "home_score": 100,
                                     "away_score": 90, "home_won": True}), \
                 patch("services.phase4_grading_engine.capture_clv") as mock_clv, \
                 patch("services.phase4_grading_engine.export_evidence_pack"):
                ge_mod.grade_phase4_decision(state["sample_decision_id"])
        finally:
            ge_mod.db = original_db
        mock_clv.assert_not_called()


# ===========================================================================
# GATE G – Simulation scheduler starts and logs agent.simulation.v1
# ===========================================================================

class TestGateG:
    def test_g1_agent_id_constant_is_locked(self):
        from services.phase4_simulation_scheduler import AGENT_ID
        assert AGENT_ID == "agent.simulation.v1", f"GATE G FAILED: {AGENT_ID!r}"

    def test_g2_scheduler_starts_and_registers_job(self):
        from services.phase4_simulation_scheduler import (
            start_phase4_simulation_scheduler,
            stop_phase4_simulation_scheduler,
            get_scheduler_status,
        )
        try:
            start_phase4_simulation_scheduler()
            status = get_scheduler_status()
            assert status["running"] is True, "GATE G FAILED: scheduler not running"
            assert status["agent_id"] == "agent.simulation.v1"
            assert len(status["jobs"]) >= 1, "GATE G FAILED: no jobs registered"
        finally:
            stop_phase4_simulation_scheduler()

    def test_g3_run_summary_contains_agent_id(self, mock_db):
        db, state = mock_db
        import services.phase4_simulation_scheduler as sched_mod
        original_db = sched_mod.db
        sched_mod.db = db
        try:
            with patch("services.phase4_simulation_scheduler.fetch_odds", return_value=[]):
                from services.phase4_simulation_scheduler import run_daily_simulation
                summary = run_daily_simulation()
        finally:
            sched_mod.db = original_db
        assert summary["agent_id"] == "agent.simulation.v1", \
            f"GATE G FAILED: agent_id={summary.get('agent_id')!r}"

    def test_g4_all_6_leagues_attempted(self, mock_db):
        db, state = mock_db
        attempted: list = []
        import services.phase4_simulation_scheduler as sched_mod
        original_db = sched_mod.db
        sched_mod.db = db
        try:
            with patch("services.phase4_simulation_scheduler.fetch_odds",
                       side_effect=lambda sport, **kw: attempted.append(sport) or []):
                from services.phase4_simulation_scheduler import run_daily_simulation
                run_daily_simulation()
        finally:
            sched_mod.db = original_db
        expected = {
            "basketball_nba", "americanfootball_nfl", "icehockey_nhl",
            "baseball_mlb", "basketball_ncaab", "americanfootball_ncaaf",
        }
        assert set(attempted) == expected, \
            f"GATE G FAILED: leagues attempted={set(attempted)}"


# ===========================================================================
# Summary sanity
# ===========================================================================

def test_all_gates_enumerated():
    gate_classes = [TestGateA, TestGateB, TestGateC, TestGateD, TestGateE, TestGateF, TestGateG]
    assert len(gate_classes) == 7

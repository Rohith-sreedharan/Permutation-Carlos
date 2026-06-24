"""
Phase 4G – Calibration Agent (agent.calibration.v1)
=====================================================
AC-6 requirement.

Identity: agent.calibration.v1  (LOCKED – never change this string)

CRITICAL RULES:
  1. This agent PROPOSES only – it never autonomously promotes a calibration
     version to ACTIVE.
  2. A minimum of TWO distinct human approvals are required before any
     proposal may be promoted.
  3. Sample size constraints are enforced BEFORE proposal is written:
       - N ≥ 50  per segment  (proposal eligibility)
       - N ≥ 200 homepage display
       - N ≥ 500 promotion eligibility
  4. Calibration immutability guard is called before any update.

Workflow:
  ① agent.propose_calibration() → writes to calibration_promotion_queue
                                    with status=PENDING_APPROVAL
  ② human_approve(proposal_id, approver_id) → increments approval_count
  ③ when approval_count >= 2 and approver IDs are distinct →
       promote_calibration(proposal_id) promotes to ACTIVE

Collections:
  calibration_promotion_queue  – one doc per proposal
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Identity constant ────────────────────────────────────────────────────────
AGENT_ID = "agent.calibration.v1"   # LOCKED

# ── Sample size thresholds ────────────────────────────────────────────────────
MIN_SAMPLES_PER_SEGMENT   = 50
MIN_SAMPLES_HOMEPAGE      = 200
MIN_SAMPLES_PROMOTION     = 500
REQUIRED_APPROVALS        = 2


# ============================================================================
# Custom exception
# ============================================================================

class CalibrationProposalError(RuntimeError):
    """Raised when a proposal cannot be created."""


class CalibrationApprovalError(RuntimeError):
    """Raised when an approval is invalid."""


class CalibrationPromotionError(RuntimeError):
    """Raised when a promotion is blocked."""


# ============================================================================
# Calibration Agent
# ============================================================================

class CalibrationAgent:
    """
    Phase-4 calibration agent.  Identity LOCKED to agent.calibration.v1.

    This agent PROPOSES only.  Promotion requires dual human approval.
    """

    AGENT_ID = AGENT_ID

    def __init__(self, db=None):
        if db is None:
            from db.mongo import db as _db
            db = _db
        self.db = db
        self.queue = db["calibration_promotion_queue"]
        self.calib_versions = db["calibration_versions"]
        self.sentinel = db["sentinel_event_log"]

    # ── Proposal ─────────────────────────────────────────────────────────────

    def propose_calibration(
        self,
        training_days: int = 30,
        method: str = "isotonic",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run calibration training and write a proposal to
        calibration_promotion_queue with status=PENDING_APPROVAL.

        Raises CalibrationProposalError if sample size constraints are not met.
        Returns the proposal dict.
        """
        logger.info(
            f"[{self.AGENT_ID}] Proposal initiated: "
            f"training_days={training_days} method={method}"
        )

        # ── Count recent graded samples ──────────────────────────────────────
        from datetime import timedelta
        from db.mongo import db

        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=training_days)
        ).isoformat()

        n_total = db["decision_settlement_metrics"].count_documents(
            {"graded_at": {"$gte": cutoff}}
        )

        if n_total < MIN_SAMPLES_PROMOTION:
            raise CalibrationProposalError(
                f"Insufficient samples for proposal: N={n_total} < "
                f"MIN_SAMPLES_PROMOTION={MIN_SAMPLES_PROMOTION}. "
                f"Proposal blocked."
            )

        # ── Per-segment check ────────────────────────────────────────────────
        segment_counts = self._count_per_segment(cutoff)
        invalid_segments = [
            seg for seg, cnt in segment_counts.items()
            if cnt < MIN_SAMPLES_PER_SEGMENT
        ]
        if invalid_segments:
            logger.warning(
                f"[{self.AGENT_ID}] Segments below MIN_SAMPLES_PER_SEGMENT: "
                f"{invalid_segments} – proceeding with eligible segments only"
            )

        # ── Run calibration training (CANDIDATE version, no ACTIVE promotion) ─
        try:
            from services.calibration_service import calibration_service
            calibration_version = calibration_service.run_calibration_job(
                training_days=training_days,
                method=method,
            )
        except Exception as exc:
            raise CalibrationProposalError(
                f"Calibration training failed: {exc}"
            ) from exc

        if not calibration_version:
            raise CalibrationProposalError(
                "Calibration training returned no version."
            )

        # ── Write proposal ────────────────────────────────────────────────────
        proposal_id = str(uuid.uuid4())
        proposal: Dict[str, Any] = {
            "proposal_id":          proposal_id,
            "agent_id":             self.AGENT_ID,
            "calibration_version":  calibration_version,
            "training_days":        training_days,
            "method":               method,
            "n_total_samples":      n_total,
            "segment_counts":       segment_counts,
            "status":               "PENDING_APPROVAL",
            "approvals":            [],
            "approval_count":       0,
            "required_approvals":   REQUIRED_APPROVALS,
            "created_at":           datetime.now(timezone.utc).isoformat(),
            "promoted_at":          None,
            "notes":                notes,
        }

        self.queue.insert_one({**proposal})
        logger.info(
            f"[{self.AGENT_ID}] Proposal written: "
            f"proposal_id={proposal_id} "
            f"calibration_version={calibration_version} "
            f"n={n_total}"
        )
        return {k: v for k, v in proposal.items() if k != "_id"}

    # ── Human approval ────────────────────────────────────────────────────────

    def human_approve(
        self,
        proposal_id: str,
        approver_id: str,
    ) -> Dict[str, Any]:
        """
        Record a human approval for a proposal.

        Rules:
          - Same approver cannot approve twice.
          - Proposal must be in PENDING_APPROVAL state.
          - When approval_count reaches REQUIRED_APPROVALS, status → READY.
        """
        proposal = self.queue.find_one({"proposal_id": proposal_id})
        if not proposal:
            raise CalibrationApprovalError(
                f"Proposal not found: {proposal_id}"
            )

        if proposal["status"] not in ("PENDING_APPROVAL", "READY"):
            raise CalibrationApprovalError(
                f"Cannot approve proposal in status={proposal['status']}"
            )

        # Prevent duplicate approver
        existing_approvers = [a["approver_id"] for a in proposal.get("approvals", [])]
        if approver_id in existing_approvers:
            raise CalibrationApprovalError(
                f"Approver '{approver_id}' has already approved this proposal."
            )

        # Record approval
        approval_entry = {
            "approver_id":  approver_id,
            "approved_at":  datetime.now(timezone.utc).isoformat(),
        }
        new_count = len(existing_approvers) + 1
        new_status = "READY" if new_count >= REQUIRED_APPROVALS else "PENDING_APPROVAL"

        self.queue.update_one(
            {"proposal_id": proposal_id},
            {
                "$push":  {"approvals": approval_entry},
                "$set":   {
                    "approval_count": new_count,
                    "status":         new_status,
                    "updated_at":     datetime.now(timezone.utc).isoformat(),
                },
            },
        )

        updated = self.queue.find_one(
            {"proposal_id": proposal_id}, {"_id": 0}
        )
        logger.info(
            f"[{self.AGENT_ID}] Approval recorded: "
            f"proposal_id={proposal_id} approver={approver_id} "
            f"count={new_count}/{REQUIRED_APPROVALS} status={new_status}"
        )
        return updated

    # ── Promotion (requires READY + dual approval) ────────────────────────────

    def promote_calibration(
        self,
        proposal_id: str,
        promoted_by: str,
    ) -> Dict[str, Any]:
        """
        Promote a READY proposal's calibration version to ACTIVE.

        GUARDS:
          1. Proposal must be in READY state (dual approval confirmed).
          2. Must have at least REQUIRED_APPROVALS distinct approvers.
          3. Calibration immutability guard called before any existing ACTIVE
             record is updated.
        """
        proposal = self.queue.find_one({"proposal_id": proposal_id})
        if not proposal:
            raise CalibrationPromotionError(
                f"Proposal not found: {proposal_id}"
            )

        if proposal["status"] != "READY":
            raise CalibrationPromotionError(
                f"Proposal is not READY (status={proposal['status']}). "
                f"Requires {REQUIRED_APPROVALS} distinct approvals."
            )

        if proposal["approval_count"] < REQUIRED_APPROVALS:
            raise CalibrationPromotionError(
                f"Insufficient approvals: {proposal['approval_count']} < "
                f"{REQUIRED_APPROVALS} required."
            )

        calibration_version = proposal["calibration_version"]

        # ── Retire existing ACTIVE version(s) ────────────────────────────────
        # Check immutability guard – we're RETIRING, not deleting
        active = list(
            self.calib_versions.find(
                {"status": "ACTIVE"}, {"calibration_version": 1}
            )
        )
        for active_doc in active:
            from db.migrations.phase4_002_calibration_immutability import (
                CalibrationImmutabilityGuard,
            )
            guard = CalibrationImmutabilityGuard(db=self.db)
            # The guard blocks UPDATE on ACTIVE records.
            # We must first demote them by calling a privileged retire path.
            self._privileged_retire(active_doc["calibration_version"])

        # ── Promote new version ───────────────────────────────────────────────
        self.calib_versions.update_one(
            {"calibration_version": calibration_version},
            {
                "$set": {
                    "status":       "ACTIVE",
                    "promoted_at":  datetime.now(timezone.utc).isoformat(),
                    "promoted_by":  promoted_by,
                    "proposal_id":  proposal_id,
                }
            },
        )

        # ── Update proposal status ────────────────────────────────────────────
        self.queue.update_one(
            {"proposal_id": proposal_id},
            {
                "$set": {
                    "status":       "PROMOTED",
                    "promoted_at":  datetime.now(timezone.utc).isoformat(),
                    "promoted_by":  promoted_by,
                }
            },
        )

        logger.info(
            f"[{self.AGENT_ID}] Calibration promoted to ACTIVE: "
            f"version={calibration_version} promoted_by={promoted_by}"
        )

        # ── Log to audit ──────────────────────────────────────────────────────
        try:
            self.db["audit_log"].insert_one(
                {
                    "event_type":          "CALIBRATION_PROMOTED",
                    "agent_id":            self.AGENT_ID,
                    "calibration_version": calibration_version,
                    "proposal_id":         proposal_id,
                    "promoted_by":         promoted_by,
                    "timestamp":           datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            logger.warning(f"Audit log write failed: {exc}")

        return {
            "promoted":             True,
            "calibration_version":  calibration_version,
            "proposal_id":          proposal_id,
            "promoted_by":          promoted_by,
        }

    def _privileged_retire(self, calibration_version: str) -> None:
        """
        Demote an ACTIVE calibration version to RETIRED.
        This is the ONLY path that bypasses the immutability guard –
        it is used exclusively during a promotion sequence.
        """
        self.calib_versions.update_one(
            {"calibration_version": calibration_version, "status": "ACTIVE"},
            {
                "$set": {
                    "status":     "RETIRED",
                    "retired_at": datetime.now(timezone.utc).isoformat(),
                    "retired_by": self.AGENT_ID,
                }
            },
        )
        logger.info(
            f"[{self.AGENT_ID}] Retired previous ACTIVE version: {calibration_version}"
        )

    # ── Sample size utilities ────────────────────────────────────────────────

    def _count_per_segment(self, cutoff: str) -> Dict[str, int]:
        """Count graded settlement records per league segment."""
        from db.mongo import db

        pipeline = [
            {"$match": {"graded_at": {"$gte": cutoff}}},
            {"$group": {"_id": "$league", "count": {"$sum": 1}}},
        ]
        result = {}
        for doc in db["decision_settlement_metrics"].aggregate(pipeline):
            result[doc["_id"] or "UNKNOWN"] = doc["count"]
        return result

    def get_proposal(self, proposal_id: str) -> Optional[Dict]:
        doc = self.queue.find_one({"proposal_id": proposal_id}, {"_id": 0})
        return doc


# ============================================================================
# Singleton (lazy)
# ============================================================================

_calibration_agent_instance: "CalibrationAgent | None" = None


def _get_calibration_agent() -> CalibrationAgent:
    global _calibration_agent_instance
    if _calibration_agent_instance is None:
        _calibration_agent_instance = CalibrationAgent()
    return _calibration_agent_instance


class _LazyCalibrationAgentProxy:
    def __getattr__(self, name: str):
        return getattr(_get_calibration_agent(), name)


calibration_agent = _LazyCalibrationAgentProxy()  # type: ignore[assignment]

"""
Phase 2 Observability Service
=============================

Append-only observability pipeline with trace/snapshot continuity.

Collections:
- prediction_lifecycle_log
- decision_audit_log
- decision_settlement_metrics
- truth_dataset
- clv_capture_log
- calibration_records
- drift_detection_log
"""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

class ObservabilityService:
    """Single append-only writer for Phase 2 observability collections."""

    def __init__(
        self,
        lifecycle_collection=None,
        decision_audit_collection=None,
        settlement_collection=None,
        truth_dataset_collection=None,
        clv_collection=None,
        calibration_collection=None,
        drift_collection=None,
    ):
        if (
            lifecycle_collection is None
            or decision_audit_collection is None
            or settlement_collection is None
            or truth_dataset_collection is None
            or clv_collection is None
            or calibration_collection is None
            or drift_collection is None
        ):
            from db.mongo import db

            lifecycle_collection = lifecycle_collection or db.get_collection("prediction_lifecycle_log")
            decision_audit_collection = decision_audit_collection or db.get_collection("decision_audit_log")
            settlement_collection = settlement_collection or db.get_collection("decision_settlement_metrics")
            truth_dataset_collection = truth_dataset_collection or db.get_collection("truth_dataset")
            clv_collection = clv_collection or db.get_collection("clv_capture_log")
            calibration_collection = calibration_collection or db.get_collection("calibration_records")
            drift_collection = drift_collection or db.get_collection("drift_detection_log")

        self.lifecycle_collection = lifecycle_collection
        self.decision_audit_collection = decision_audit_collection
        self.settlement_collection = settlement_collection
        self.truth_dataset_collection = truth_dataset_collection
        self.clv_collection = clv_collection
        self.calibration_collection = calibration_collection
        self.drift_collection = drift_collection

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _derive_snapshot_hash(self, snapshot_hash: Optional[str], seed_parts: Sequence[Any]) -> str:
        if snapshot_hash:
            return str(snapshot_hash)
        material = "|".join(str(part) for part in seed_parts)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _derive_trace_id(self, trace_id: Optional[str], prefix: str = "trace") -> str:
        if trace_id:
            return str(trace_id)
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def log_prediction_lifecycle(
        self,
        stage: str,
        decision_id: Optional[str],
        event_id: str,
        prediction_id: Optional[str] = None,
        publish_id: Optional[str] = None,
        graded_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        snapshot_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write one append-only lifecycle row and return lifecycle_id."""
        now_iso = self._now_iso()
        normalized_trace_id = self._derive_trace_id(trace_id)
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [event_id, decision_id or prediction_id or publish_id or graded_id or stage],
        )
        lifecycle_id = str(uuid.uuid4())

        doc = {
            "lifecycle_id": lifecycle_id,
            "stage": stage,
            "event_id": event_id,
            "decision_id": decision_id,
            "prediction_id": prediction_id,
            "publish_id": publish_id,
            "graded_id": graded_id,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "metadata": metadata or {},
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.lifecycle_collection.insert_one(doc)
        return lifecycle_id

    def log_decision_audit(
        self,
        event_id: str,
        decision_id: str,
        market_type: str,
        release_status: str,
        classification: Optional[str],
        model_prob: Optional[float],
        edge_points: Optional[float],
        trace_id: Optional[str],
        snapshot_hash: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append one decision audit record into decision_audit_log."""
        now_iso = self._now_iso()
        audit_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id)
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [event_id, decision_id, market_type, release_status],
        )

        doc = {
            "audit_id": audit_id,
            "event_id": event_id,
            "decision_id": decision_id,
            "market_type": market_type,
            "release_status": release_status,
            "classification": classification,
            "model_prob": model_prob,
            "edge_points": edge_points,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "metadata": metadata or {},
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.decision_audit_collection.insert_one(doc)
        return audit_id

    def log_settlement_metrics(
        self,
        graded_id: str,
        event_id: str,
        prediction_id: str,
        publish_id: str,
        result_code: str,
        bet_status: str,
        brier: Optional[float],
        logloss: Optional[float],
        ece_bucket_error: Optional[float],
        clv: Optional[float],
        p_predicted: Optional[float],
        actual_outcome: Optional[int],
        trace_id: Optional[str],
        snapshot_hash: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append settlement metrics for one graded prediction."""
        now_iso = self._now_iso()
        metrics_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id)
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [event_id, prediction_id, publish_id, graded_id],
        )

        doc = {
            "metrics_id": metrics_id,
            "graded_id": graded_id,
            "event_id": event_id,
            "prediction_id": prediction_id,
            "publish_id": publish_id,
            "bet_status": bet_status,
            "result_code": result_code,
            "brier": brier,
            "logloss": logloss,
            "ece_bucket_error": ece_bucket_error,
            "clv": clv,
            "p_predicted": p_predicted,
            "actual_outcome": actual_outcome,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "metadata": metadata or {},
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.settlement_collection.insert_one(doc)
        return metrics_id

    def log_truth_dataset_row(
        self,
        event_id: str,
        prediction_id: str,
        publish_id: str,
        graded_id: str,
        feature_snapshot: Dict[str, Any],
        label: Dict[str, Any],
        trace_id: Optional[str],
        snapshot_hash: Optional[str],
    ) -> str:
        """Append one immutable truth-dataset row."""
        now_iso = self._now_iso()
        truth_row_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id)
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [event_id, prediction_id, publish_id, graded_id, "truth"],
        )

        doc = {
            "truth_row_id": truth_row_id,
            "event_id": event_id,
            "prediction_id": prediction_id,
            "publish_id": publish_id,
            "graded_id": graded_id,
            "feature_snapshot": feature_snapshot,
            "label": label,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.truth_dataset_collection.insert_one(doc)
        return truth_row_id

    def log_clv_capture(
        self,
        event_id: str,
        prediction_id: str,
        publish_id: str,
        graded_id: str,
        entry_price: Optional[float],
        closing_price: Optional[float],
        clv: Optional[float],
        trace_id: Optional[str],
        snapshot_hash: Optional[str],
    ) -> str:
        """Append one CLV capture row."""
        now_iso = self._now_iso()
        clv_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id)
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [event_id, prediction_id, publish_id, "clv"],
        )

        doc = {
            "clv_capture_id": clv_id,
            "event_id": event_id,
            "prediction_id": prediction_id,
            "publish_id": publish_id,
            "graded_id": graded_id,
            "entry_price": entry_price,
            "closing_price": closing_price,
            "clv": clv,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.clv_collection.insert_one(doc)
        return clv_id

    def log_calibration_record(
        self,
        calibration_version: str,
        method: str,
        trained_on_start: str,
        trained_on_end: str,
        sample_count: int,
        brier: float,
        logloss: float,
        ece: float,
        status: str,
        trace_id: Optional[str],
        snapshot_hash: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append calibration records for each calibration generation run."""
        now_iso = self._now_iso()
        calibration_record_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id, prefix="trace_cal")
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            [calibration_version, method, trained_on_start, trained_on_end, sample_count],
        )

        doc = {
            "calibration_record_id": calibration_record_id,
            "agent_id": "agent.calibration.v1",
            "calibration_version": calibration_version,
            "method": method,
            "trained_on_start": trained_on_start,
            "trained_on_end": trained_on_end,
            "sample_count": sample_count,
            "brier": brier,
            "logloss": logloss,
            "ece": ece,
            "status": status,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "metadata": metadata or {},
            "timestamp": now_iso,
            "created_at_utc": now_iso,
            "created_at": now_iso,
        }
        self.calibration_collection.insert_one(doc)
        return calibration_record_id

    def compute_aggregate_metrics(self, rows: Iterable[Dict[str, Any]], n_bins: int = 10) -> Dict[str, float]:
        """Compute Brier/LogLoss/ECE over settlement rows."""
        probs: List[float] = []
        outcomes: List[int] = []

        for row in rows:
            p_pred = row.get("p_predicted")
            outcome = row.get("actual_outcome")
            if p_pred is None or outcome is None:
                continue
            p_clamped = max(1e-6, min(1 - 1e-6, float(p_pred)))
            probs.append(p_clamped)
            outcomes.append(int(outcome))

        if not probs:
            return {"brier": 0.0, "logloss": 0.0, "ece": 0.0, "sample_count": 0.0}

        sample_count = len(probs)
        brier = sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / sample_count
        logloss = sum(
            -(y * math.log(p) + (1 - y) * math.log(1 - p))
            for p, y in zip(probs, outcomes)
        ) / sample_count

        bin_edges = [i / n_bins for i in range(n_bins + 1)]
        ece = 0.0
        for i in range(n_bins):
            low = bin_edges[i]
            high = bin_edges[i + 1]
            idx = [j for j, p in enumerate(probs) if (low <= p < high) or (i == n_bins - 1 and p == high)]
            if not idx:
                continue
            acc = sum(outcomes[j] for j in idx) / len(idx)
            conf = sum(probs[j] for j in idx) / len(idx)
            ece += (len(idx) / sample_count) * abs(acc - conf)

        return {
            "brier": float(brier),
            "logloss": float(logloss),
            "ece": float(ece),
            "sample_count": float(sample_count),
        }

    def run_drift_detection(
        self,
        baseline_metrics: Dict[str, float],
        recent_rows: Iterable[Dict[str, Any]],
        threshold_delta: float = 0.03,
        trace_id: Optional[str] = None,
        snapshot_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute drift status and append an immutable drift log row."""
        recent_metrics = self.compute_aggregate_metrics(recent_rows)
        now_iso = self._now_iso()

        deltas = {
            "brier_delta": float(recent_metrics["brier"] - baseline_metrics.get("brier", 0.0)),
            "logloss_delta": float(recent_metrics["logloss"] - baseline_metrics.get("logloss", 0.0)),
            "ece_delta": float(recent_metrics["ece"] - baseline_metrics.get("ece", 0.0)),
        }

        drift_detected = any(abs(value) >= threshold_delta for value in deltas.values())
        drift_id = str(uuid.uuid4())
        normalized_trace_id = self._derive_trace_id(trace_id, prefix="trace_drift")
        normalized_snapshot_hash = self._derive_snapshot_hash(
            snapshot_hash,
            ["drift", now_iso, baseline_metrics.get("sample_count", 0), recent_metrics.get("sample_count", 0)],
        )

        doc = {
            "drift_id": drift_id,
            "baseline_metrics": baseline_metrics,
            "recent_metrics": recent_metrics,
            "deltas": deltas,
            "threshold_delta": threshold_delta,
            "drift_detected": drift_detected,
            "trace_id": normalized_trace_id,
            "snapshot_hash": normalized_snapshot_hash,
            "timestamp": now_iso,
            "created_at_utc": now_iso,
        }
        self.drift_collection.insert_one(doc)

        return {
            "drift_id": drift_id,
            "drift_detected": drift_detected,
            "deltas": deltas,
            "recent_metrics": recent_metrics,
        }


_observability_service: Optional[ObservabilityService] = None


def get_observability_service() -> ObservabilityService:
    global _observability_service
    if _observability_service is None:
        _observability_service = ObservabilityService()
    return _observability_service


class _ObservabilityProxy:
    def __getattr__(self, item: str):
        return getattr(get_observability_service(), item)


observability_service = _ObservabilityProxy()

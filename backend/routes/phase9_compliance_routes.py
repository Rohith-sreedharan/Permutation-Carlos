from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from bson import ObjectId

from db.mongo import db
from middleware.auth import get_current_user


router = APIRouter(prefix="/api/compliance", tags=["phase9-compliance"])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_trace_id() -> str:
    return str(uuid.uuid4())


def _hash_user_id(user_id: str) -> str:
    salt = os.getenv("DATA_DELETION_HASH_SALT", "phase9-default-salt")
    return sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()


def _append_sentinel(event_type: str, payload: Dict[str, Any]) -> None:
    doc = {
        "event_type": event_type,
        "timestamp": _utc_now_iso(),
        "agent_id": "agent.sentinel.v1",
    }
    doc.update(payload)
    db["sentinel_event_log"].insert_one(doc)


def _safe_update_many(collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, int]:
    try:
        result = db[collection].update_many(query, update)
        return {"matched": int(result.matched_count), "modified": int(result.modified_count)}
    except Exception:
        return {"matched": 0, "modified": 0}


def _safe_delete_many(collection: str, query: Dict[str, Any]) -> Dict[str, int]:
    try:
        result = db[collection].delete_many(query)
        return {"deleted": int(result.deleted_count)}
    except Exception:
        return {"deleted": 0}


class SelfExclusionRequest(BaseModel):
    exclusion_type: str = "VOLUNTARY_SELF_EXCLUSION"


class ReinstatementRequest(BaseModel):
    reason: str = "User requested reinstatement"


class DataDeletionRequest(BaseModel):
    confirm_text: str


@router.post("/self-exclusion/request")
def request_self_exclusion(
    payload: SelfExclusionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))
    now = _utc_now_iso()
    trace_id = _new_trace_id()

    if current_user.get("self_excluded"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SELF_EXCLUDED_ALREADY_ACTIVE",
        )

    # Immediate enforcement state (AC-1 baseline)
    db["users"].update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "self_excluded": True,
                "self_excluded_at_utc": now,
                "self_exclusion_trace_id": trace_id,
                "auth_token": None,
            }
        },
    )

    # Suspend billing/entitlement surface immediately.
    db["billing_state"].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "status": "excluded",
                "platform_access": False,
                "telegram_access": False,
                "billing_suspended_at_utc": now,
                "trace_id": trace_id,
            }
        },
        upsert=True,
    )

    exclusion_id = str(uuid.uuid4())
    db["self_exclusion_log"].insert_one(
        {
            "exclusion_id": exclusion_id,
            "user_id": user_id,
            "exclusion_type": payload.exclusion_type,
            "requested_at_utc": now,
            "sessions_invalidated_at_utc": now,
            "billing_suspended_at_utc": now,
            "reinstatement_requested_at_utc": None,
            "reinstatement_approved_at_utc": None,
            "approved_by_operator_id": None,
            "trace_id": trace_id,
        }
    )

    _append_sentinel(
        "SELF_EXCLUSION_ACTIVATED",
        {
            "user_id": user_id,
            "trace_id": trace_id,
        },
    )

    return {
        "status": "ok",
        "self_excluded": True,
        "exclusion_id": exclusion_id,
        "trace_id": trace_id,
        "requested_at_utc": now,
    }


@router.get("/self-exclusion/status")
def get_self_exclusion_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    user_id = str(current_user.get("_id"))
    latest = db["self_exclusion_log"].find_one(
        {"user_id": user_id},
        sort=[("requested_at_utc", -1)],
    )
    return {
        "self_excluded": bool(current_user.get("self_excluded", False)),
        "self_excluded_at_utc": current_user.get("self_excluded_at_utc"),
        "latest_log": {
            "exclusion_id": latest.get("exclusion_id") if latest else None,
            "requested_at_utc": latest.get("requested_at_utc") if latest else None,
            "reinstatement_requested_at_utc": latest.get("reinstatement_requested_at_utc") if latest else None,
            "reinstatement_approved_at_utc": latest.get("reinstatement_approved_at_utc") if latest else None,
            "trace_id": latest.get("trace_id") if latest else None,
        },
    }


@router.post("/self-exclusion/reinstatement/request")
def request_reinstatement(
    payload: ReinstatementRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = str(current_user.get("_id"))
    excluded_at = current_user.get("self_excluded_at_utc")
    if not current_user.get("self_excluded") or not excluded_at:
        raise HTTPException(status_code=400, detail="SELF_EXCLUSION_NOT_ACTIVE")

    try:
        started = datetime.fromisoformat(excluded_at.replace("Z", "+00:00"))
    except ValueError:
        started = datetime.now(timezone.utc)

    if datetime.now(timezone.utc) < started + timedelta(days=30):
        raise HTTPException(
            status_code=400,
            detail="COOLING_OFF_PERIOD_ACTIVE",
        )

    trace_id = _new_trace_id()
    request_time = _utc_now_iso()

    db["self_exclusion_log"].insert_one(
        {
            "exclusion_id": str(uuid.uuid4()),
            "user_id": user_id,
            "exclusion_type": "VOLUNTARY_SELF_EXCLUSION",
            "requested_at_utc": excluded_at,
            "sessions_invalidated_at_utc": excluded_at,
            "billing_suspended_at_utc": excluded_at,
            "reinstatement_requested_at_utc": request_time,
            "reinstatement_approved_at_utc": None,
            "approved_by_operator_id": None,
            "trace_id": trace_id,
            "reinstatement_reason": payload.reason,
        }
    )

    db["self_exclusion_reinstatement_queue"].insert_one(
        {
            "request_id": str(uuid.uuid4()),
            "user_id": user_id,
            "status": "PENDING_OPERATOR_APPROVAL",
            "requested_at_utc": request_time,
            "trace_id": trace_id,
            "reason": payload.reason,
        }
    )

    return {
        "status": "ok",
        "queue_status": "PENDING_OPERATOR_APPROVAL",
        "reinstatement_requested_at_utc": request_time,
        "trace_id": trace_id,
    }


@router.post("/data-deletion/request")
def request_data_deletion(
    payload: DataDeletionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    if payload.confirm_text != "DELETE":
        raise HTTPException(status_code=400, detail="CONFIRMATION_TEXT_INVALID")

    user_id = str(current_user.get("_id"))
    trace_id = _new_trace_id()
    request_id = str(uuid.uuid4())
    requested_at = _utc_now_iso()

    db["data_deletion_log"].insert_one(
        {
            "request_id": request_id,
            "user_id": user_id,
            "requested_at_utc": requested_at,
            "completed_at_utc": None,
            "items_processed": 0,
            "status": "PENDING",
            "failure_reason": None,
            "trace_id": trace_id,
        }
    )

    return {
        "status": "ok",
        "request_id": request_id,
        "requested_at_utc": requested_at,
        "trace_id": trace_id,
    }


@router.post("/data-deletion/process/{request_id}")
def process_data_deletion(request_id: str):
    req = db["data_deletion_log"].find_one({"request_id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="REQUEST_NOT_FOUND")
    if req.get("status") == "COMPLETED":
        return {"status": "ok", "already_completed": True}

    user_id = str(req.get("user_id"))
    trace_id = req.get("trace_id") or _new_trace_id()
    anon = _hash_user_id(user_id)
    completed_at = _utc_now_iso()
    processed = 0
    collection_report = []

    # Resolve user + alternate identifiers before mutation.
    user_doc = None
    try:
        user_doc = db["users"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        user_doc = db["users"].find_one({"_id": user_id})
    user_email = user_doc.get("email") if user_doc else None

    identity_matches = [{"user_id": user_id}]
    if user_email:
        identity_matches.append({"user_id": user_email})
        identity_matches.append({"email": user_email})

    # Delete/anonymize PII in user record.
    user_query: Dict[str, Any]
    try:
        user_query = {"_id": ObjectId(user_id)}
    except Exception:
        user_query = {"_id": user_id}

    user_update = db["users"].update_one(
        user_query,
        {
            "$set": {
                "email": f"deleted+{anon[:12]}@deleted.local",
                "username": f"deleted_user_{anon[:8]}",
                "name": None,
                "hashed_password": None,
                "phone": None,
                "is_deleted": True,
                "deleted_at_utc": completed_at,
                "anonymized_user_hash": anon,
                "auth_token": None,
            }
        },
    )
    processed += int(user_update.modified_count)
    collection_report.append(
        {
            "collection": "users",
            "action": "ANONYMIZE_PII_AND_CREDENTIALS",
            "matched": int(user_update.matched_count),
            "modified": int(user_update.modified_count),
        }
    )

    # Immediate session/token invalidation artifacts.
    token_deletions = _safe_delete_many("password_reset_tokens", {"user_id": user_id})
    processed += token_deletions["deleted"]
    collection_report.append(
        {
            "collection": "password_reset_tokens",
            "action": "DELETE_SESSION_AND_RESET_TOKENS",
            "deleted": token_deletions["deleted"],
        }
    )

    # Outbound communications: preserve message content, anonymize identifiers.
    outbound = _safe_update_many(
        "outbound_communication_log",
        {"$or": identity_matches},
        {
            "$set": {
                "user_id": anon,
                "anonymized_user_hash": anon,
                "to_email": f"deleted+{anon[:12]}@deleted.local",
            }
        },
    )
    processed += outbound["modified"]
    collection_report.append(
        {
            "collection": "outbound_communication_log",
            "action": "ANONYMIZE_IDENTITY_KEEP_MESSAGE_CONTENT",
            "matched": outbound["matched"],
            "modified": outbound["modified"],
        }
    )

    # Decision records and grading datasets: preserve, anonymize user identity.
    for collection in [
        "decision_records",
        "decision_settlement_metrics",
        "truth_dataset",
        "clv_capture_log",
        "calibration_audit_log",
        "drift_detection_log",
        "ai_picks",
    ]:
        result = _safe_update_many(
            collection,
            {"$or": identity_matches},
            {"$set": {"user_id": anon, "anonymized_user_hash": anon}},
        )
        processed += result["modified"]
        collection_report.append(
            {
                "collection": collection,
                "action": "ANONYMIZE_USER_ID_PRESERVE_DECISION_DATA",
                "matched": result["matched"],
                "modified": result["modified"],
            }
        )

    # Billing transactions: preserve amounts/dates, remove personal identity.
    for collection in [
        "billing_ledger",
        "billing_state_change_log",
        "commissions",
        "parlay_overage_charge_log",
    ]:
        result = _safe_update_many(
            collection,
            {"$or": identity_matches},
            {
                "$set": {
                    "user_id": anon,
                    "anonymized_user_hash": anon,
                    "email": None,
                    "name": None,
                }
            },
        )
        processed += result["modified"]
        collection_report.append(
            {
                "collection": collection,
                "action": "ANONYMIZE_BILLING_IDENTITY_KEEP_FINANCIAL_RECORD",
                "matched": result["matched"],
                "modified": result["modified"],
            }
        )

    # Sentinel + IP style logs: preserve geo semantics, anonymize user and IP.
    for collection in ["sentinel_event_log", "logs_core_ai", "request_log", "request_logs"]:
        result = _safe_update_many(
            collection,
            {
                "$or": [
                    {"user_id": user_id},
                    {"user_id": user_email} if user_email else {"user_id": "__none__"},
                    {"email": user_email} if user_email else {"email": "__none__"},
                ]
            },
            {
                "$set": {
                    "user_id": anon,
                    "anonymized_user_hash": anon,
                    "email": None,
                    "ip": "ANONYMIZED",
                    "ip_address": "ANONYMIZED",
                }
            },
        )
        processed += result["modified"]
        collection_report.append(
            {
                "collection": collection,
                "action": "ANONYMIZE_USER_AND_IP_KEEP_GEO_METADATA",
                "matched": result["matched"],
                "modified": result["modified"],
            }
        )

    # Self-exclusion log: preserve exclusion events, remove direct identity.
    self_exclusion = _safe_update_many(
        "self_exclusion_log",
        {"$or": identity_matches},
        {
            "$set": {
                "user_id": anon,
                "anonymized_user_hash": anon,
                "email": None,
                "name": None,
            }
        },
    )
    processed += self_exclusion["modified"]
    collection_report.append(
        {
            "collection": "self_exclusion_log",
            "action": "ANONYMIZE_IDENTITY_KEEP_EXCLUSION_EVENTS",
            "matched": self_exclusion["matched"],
            "modified": self_exclusion["modified"],
        }
    )

    db["data_deletion_log"].insert_one(
        {
            "request_id": request_id,
            "user_id": anon,
            "requested_at_utc": req.get("requested_at_utc"),
            "completed_at_utc": completed_at,
            "items_processed": processed,
            "status": "COMPLETED",
            "failure_reason": None,
            "trace_id": trace_id,
            "collection_report": collection_report,
        }
    )

    _append_sentinel(
        "DATA_DELETION_COMPLETED",
        {
            "trace_id": trace_id,
            "request_id": request_id,
            "items_processed": processed,
        },
    )

    return {
        "status": "ok",
        "request_id": request_id,
        "completed_at_utc": completed_at,
        "items_processed": processed,
        "trace_id": trace_id,
        "collection_report": collection_report,
    }

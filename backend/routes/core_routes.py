from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from datetime import datetime, timezone

from integrations.odds_api import fetch_odds
from services.normalization import normalize_batch
from services.logger import log_stage
from db.mongo import insert_many, find_events, find_logs
from db.mongo import upsert_events
from core.permutation import run_permutations
from core.ai_stub import enhance_predictions

router = APIRouter(prefix="/api/core", tags=["core"])

INTERNAL_EMAIL_BLOCKLIST = {
    "beatvegasapp@gmail.com",
}
INTERNAL_PREFIX_BLOCKLIST = (
    "phase9_",
    "p11_",
    "ev_",
    "audit_",
)
INTERNAL_NAME_BLOCKLIST = {
    "probe",
}
INTERNAL_USERNAME_BLOCKLIST = {
    "deleted_user_bc03814a",
}
INTERNAL_EMAIL_DOMAIN_BLOCKLIST = [
    "@beatvas-test.internal",
    "@beatvegas-qa.internal",
    "@beatvegas-test.internal",
]
INTERNAL_USERNAME_PREFIX_BLOCKLIST = [
    "phase9_",
    "p11_",
    "ev_",
    "audit_",
    "phase13",
    "popup_",
    "trialtest_",
    "phase13_",
    "dup_",
    "self_",
]
INTERNAL_STATUS_BLOCKLIST = {
    "deleted",
    "test",
    "internal",
}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_internal_user(doc: Dict[str, Any]) -> bool:
    email = _norm(doc.get("email"))
    username = _norm(doc.get("username"))
    name = _norm(doc.get("name") or doc.get("display_name"))
    status = _norm(doc.get("status") or doc.get("account_status") or doc.get("user_status"))

    identifiers = [email, username, name]

    if email in INTERNAL_EMAIL_BLOCKLIST:
        return True
    if any(domain in email for domain in INTERNAL_EMAIL_DOMAIN_BLOCKLIST):
        return True
    if username in INTERNAL_USERNAME_BLOCKLIST:
        return True
    if any(username.startswith(prefix) for prefix in INTERNAL_USERNAME_PREFIX_BLOCKLIST):
        return True
    if username.startswith("deleted_user_"):
        return True
    if status in INTERNAL_STATUS_BLOCKLIST:
        return True
    if any(value in INTERNAL_NAME_BLOCKLIST for value in identifiers if value):
        return True
    if any(value.startswith(INTERNAL_PREFIX_BLOCKLIST) for value in identifiers if value):
        return True

    return False


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/fetch-odds")
def fetch_odds_endpoint(sport: str, region: str = "us", markets: str = "h2h,spreads"):  # markets comma-delimited
    log_stage("fetch_odds", "start", {"sport": sport, "region": region, "markets": markets})
    try:
        events = fetch_odds(sport, region=region, markets=markets)
    except Exception as e:
        log_stage("fetch_odds", "error", {"sport": sport}, {"error": str(e)}, level="ERROR")
        raise HTTPException(status_code=500, detail=str(e))
    upsert_events("events", events)
    log_stage("fetch_odds", "stored", {"count": len(events)})
    return {"status": "ok", "timestamp": ts(), "count": len(events)}


@router.post("/normalize")
def normalize_endpoint(limit: int = 25):
    raw = find_events("events", limit=limit)
    normalized = normalize_batch(raw)
    insert_many("normalized_data", normalized)
    log_stage("normalize", "batch", {"input_count": len(raw)}, {"normalized_count": len(normalized)})
    return {"status": "ok", "timestamp": ts(), "normalized": normalized}


@router.post("/run-permutations")
def permutations_endpoint(event_id: str, max_legs: int = 2, top_n: int = 5):
    data = find_events("normalized_data", filter={"event_id": event_id}, limit=1)
    if not data:
        raise HTTPException(status_code=404, detail="Normalized event not found")
    odds = data[0].get("odds", [])
    perms = run_permutations(odds, max_legs=max_legs, top_n=top_n)
    log_stage("permutations", "generated", {"event_id": event_id}, {"count": len(perms)})
    return {"status": "ok", "timestamp": ts(), "event_id": event_id, "permutations": perms}


@router.post("/predict")
def predict_endpoint(event_id: str):
    data = find_events("normalized_data", filter={"event_id": event_id}, limit=1)
    if not data:
        raise HTTPException(status_code=404, detail="Normalized event not found")
    base = data[0]
    perms = run_permutations(base.get("odds", []), max_legs=2, top_n=5)
    enhanced = enhance_predictions(perms, base_confidence=base.get("confidence", 0.1))
    # Store predictions (optional subset)
    insert_many("predictions", [
        {"event_id": event_id, "prediction": p, "timestamp": ts()} for p in enhanced
    ])
    log_stage("predict", "enhanced", {"event_id": event_id}, {"count": len(enhanced)})
    return {"status": "ok", "timestamp": ts(), "event_id": event_id, "predictions": enhanced}


@router.get("/logs")
def logs_endpoint(module: str | None = None, limit: int = 50):
    logs = find_logs(module=module, limit=limit)
    return {"status": "ok", "timestamp": ts(), "count": len(logs), "logs": logs}


@router.get("/predictions")
def get_predictions(limit: int = 50):
    """Return stored predictions.

    The predictions collection stores entries like {event_id, prediction, timestamp}.
    We normalize to a flat list of {event_id, confidence} expected by the frontend.
    """
    docs = find_events("predictions", limit=limit)
    out = []
    for d in docs:
        # entry may store prediction as an object or list; handle common shapes
        pred = d.get("prediction") or d.get("predictions")
        if isinstance(pred, dict):
            # assume dict contains confidence
            confidence = pred.get("confidence")
        elif isinstance(pred, list) and pred:
            confidence = pred[0].get("confidence")
        else:
            confidence = None
        if confidence is None:
            # try direct top-level
            confidence = d.get("confidence")
        if d.get("event_id") and confidence is not None:
            out.append({"event_id": d.get("event_id"), "confidence": confidence})
    return {"count": len(out), "predictions": out}


@router.get("/leaderboard")
def get_leaderboard(limit: int = 10):
    """Return a basic leaderboard derived from `users` collection when available.

    Falls back to empty list if no users.
    """
    try:
        from db.mongo import db as _db
        users_docs = list(_db['users'].find().limit(max(limit * 5, 50)))
    except Exception:
        users_docs = []

    out = []
    seen_user_keys = set()
    rank = 1
    for u in users_docs:
        if _is_internal_user(u):
            continue

        dedupe_key = _norm(u.get("username") or u.get("user_id") or u.get("id") or u.get("email") or u.get("_id"))
        if dedupe_key and dedupe_key in seen_user_keys:
            continue
        if dedupe_key:
            seen_user_keys.add(dedupe_key)

        out.append({
            "id": str(u.get("_id")),
            "rank": rank,
            "username": u.get("username") or u.get("email"),
            "avatarUrl": u.get("avatarUrl") or f"https://i.pravatar.cc/150?u={u.get('email')}",
            "score": u.get("score", 0),
            "streaks": u.get("streaks", 0),
        })
        rank += 1
        if len(out) >= limit:
            break

    return {"count": len(out), "leaderboard": out}


@router.get("/affiliate-stats")
def get_affiliate_stats():
    """Return affiliate stats if stored; otherwise return an empty list.
    """
    try:
        from db.mongo import db as _db
        stats = list(_db.get_collection('affiliate_stats').find())
        # Normalize to expected shape if present
        normalized = [
            {
                "label": s.get("label"),
                "value": s.get("value"),
                "change": s.get("change"),
                "changeType": s.get("changeType", "increase"),
            }
            for s in stats
        ]
        return {"count": len(normalized), "affiliate_stats": normalized}
    except Exception:
        return {"count": 0, "affiliate_stats": []}


@router.get("/referrals")
def get_referrals(limit: int = 25):
    try:
        from db.mongo import db as _db
        refs = list(_db['referrals'].find().limit(limit))
        normalized = [
            {
                "id": str(r.get("_id")),
                "user": r.get("user"),
                "date_joined": r.get("date_joined"),
                "status": r.get("status", "Active"),
                "commission": r.get("commission", 0.0),
            }
            for r in refs
        ]
        return {"count": len(normalized), "referrals": normalized}
    except Exception:
        return {"count": 0, "referrals": []}


@router.get("/chat")
def get_chat_messages(limit: int = 50):
    try:
        from db.mongo import db as _db
        msgs = list(_db['chat_messages'].find().limit(limit))
        normalized = [
            {
                "id": str(m.get("_id")),
                "user": {
                    "username": m.get("user", {}).get("username"),
                    "avatarUrl": m.get("user", {}).get("avatarUrl"),
                    "is_admin": m.get("user", {}).get("is_admin", False),
                },
                "message": m.get("message"),
                "timestamp": m.get("timestamp"),
                "announcement": m.get("announcement", False),
            }
            for m in msgs
        ]
        return {"count": len(normalized), "messages": normalized}
    except Exception:
        return {"count": 0, "messages": []}


@router.get("/top-analysts")
def get_top_analysts(limit: int = 10):
    """Return top analysts list derived from users or predictions when possible."""
    try:
        from db.mongo import db as _db
        users_docs = list(_db['users'].find().limit(max(limit * 5, 50)))
    except Exception:
        users_docs = []

    out = []
    seen_user_keys = set()
    rank = 1
    for u in users_docs:
        if _is_internal_user(u):
            continue

        dedupe_key = _norm(u.get("username") or u.get("user_id") or u.get("id") or u.get("email") or u.get("_id"))
        if dedupe_key and dedupe_key in seen_user_keys:
            continue
        if dedupe_key:
            seen_user_keys.add(dedupe_key)

        out.append({
            "id": str(u.get("_id")),
            "rank": rank,
            "username": u.get("username") or u.get("email"),
            "avatarUrl": u.get("avatarUrl") or f"https://i.pravatar.cc/150?u={u.get('email')}",
            "units": u.get("units", 0),
        })
        rank += 1
        if len(out) >= limit:
            break

    return {"count": len(out), "analysts": out}

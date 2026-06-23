"""
BeatVegas Canonical Affiliate Attribution System
=================================================
Single source of truth for affiliate attribution, enrollment,
commission calculation, and payout logic.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from db.mongo import db
from services.phase11_affiliate_engine import affiliate_engine as _aff_engine
from services.time_service import get_now_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/affiliate", tags=["Affiliate"])


PLATFORM_COMMISSION_TIERS = [
    (1, 4, Decimal("30.00")),
    (5, 9, Decimal("35.00")),
    (10, 19, Decimal("40.00")),
    (20, 999999, Decimal("50.00")),
]
SYNDICATE_COMMISSION = Decimal("15.00")
RETENTION_BONUS_PLATFORM = Decimal("20.00")
L2_PASSIVE_RATE = Decimal("0.10")
ATTRIBUTION_WINDOW_DAYS = 30
COOKIE_MAX_AGE_SECONDS = 2_592_000


def _get_operator_secret() -> str:
    secret = os.getenv("AFFILIATE_OPERATOR_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Affiliate system not configured.",
        )
    return secret


def _validate_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except Exception:
        return False


def _get_monthly_volume(affiliate_id: str, now_utc) -> int:
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    return db["affiliate_commission_log"].count_documents(
        {
            "affiliate_id": affiliate_id,
            "tier": "platform",
            "commission_status": {"$in": ["ELIGIBLE", "PAID"]},
            "created_at_utc": {"$gte": month_start},
        }
    )


def _calculate_platform_commission(monthly_volume: int) -> Decimal:
    for low, high, amount in PLATFORM_COMMISSION_TIERS:
        if low <= monthly_volume <= high:
            return amount
    return Decimal("30.00")


def _resolve_affiliate_from_auth(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = authorization.split(" ", 1)[1]
    from services.auth_service import get_user_from_token_safe

    user_id = get_user_from_token_safe(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    account = db["affiliate_accounts"].find_one({"affiliate_id": user_id})
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found.")
    return user_id


def _sentinel_log(event_type: str, severity: str, affiliate_id: str, trace_id: str, now_utc, **kwargs) -> None:
    try:
        db["sentinel_event_log"].insert_one(
            {
                "event_type": event_type,
                "severity": severity,
                "agent_id": "agent.sentinel.v1",
                "affiliate_id": affiliate_id,
                "trace_id": trace_id,
                "timestamp": now_utc.isoformat(),
                "tenant_id": "beatvegas",
                **kwargs,
            }
        )
    except Exception as exc:
        logger.error("[Sentinel] failed: %s", exc)


@router.get("/ref/{affiliate_id}")
async def record_affiliate_click(affiliate_id: str, request: Request) -> JSONResponse:
    now_utc = get_now_utc()
    trace_id = str(uuid4())
    click_id = str(uuid4())

    safe_id = affiliate_id.strip()
    if not _validate_uuid(safe_id):
        _sentinel_log("INVALID_AFFILIATE_CLICK", "WARNING", safe_id, trace_id, now_utc, reason="invalid_uuid")
        raise HTTPException(status_code=400, detail="Invalid affiliate link.")

    affiliate_doc = db["affiliate_accounts"].find_one({"affiliate_id": safe_id}, {"status": 1})
    if not affiliate_doc:
        _sentinel_log("INVALID_AFFILIATE_CLICK", "WARNING", safe_id, trace_id, now_utc, reason="affiliate_not_found")
        raise HTTPException(status_code=404, detail="Affiliate link not found.")
    if affiliate_doc.get("status") != "ACTIVE":
        _sentinel_log("INACTIVE_AFFILIATE_CLICK", "WARNING", safe_id, trace_id, now_utc)
        raise HTTPException(status_code=403, detail="Affiliate link not active.")

    geo_country = getattr(request.state, "geo_country", None)
    if geo_country and geo_country != "US":
        _sentinel_log("NON_US_CLICK", "INFO", safe_id, trace_id, now_utc, country=geo_country)
        raise HTTPException(status_code=403, detail="BeatVegas is available in the United States only.")

    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    user_agent = request.headers.get("User-Agent", "unknown")

    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()
    ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()

    from datetime import timedelta

    db["affiliate_clicks"].insert_one(
        {
            "click_id": click_id,
            "affiliate_id": safe_id,
            "clicked_at_utc": now_utc.isoformat(),
            "attribution_expires_at": (now_utc + timedelta(days=ATTRIBUTION_WINDOW_DAYS)).isoformat(),
            "ip_hash": ip_hash,
            "user_agent_hash": ua_hash,
            "is_converted": False,
            "trace_id": trace_id,
            "tenant_id": "beatvegas",
        }
    )

    signed_cookie = _aff_engine.generate_signed_cookie(
        affiliate_id=safe_id,
        click_id=click_id,
        clicked_at_utc=now_utc.isoformat(),
    )

    _sentinel_log(
        "AFFILIATE_CLICK_RECORDED",
        "INFO",
        safe_id,
        trace_id,
        now_utc,
        click_id=click_id,
    )

    response = JSONResponse(
        content={
            "status": "ok",
            "click_id": click_id,
            "clicked_at_utc": now_utc.isoformat(),
            "redirect": f"/affiliate-landing?ref={safe_id}",
        }
    )
    response.set_cookie(
        key="bv_ref",
        value=signed_cookie,
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


class EnrollAffiliateRequest(BaseModel):
    name: str
    email: EmailStr
    notification_preference: str = "email"
    parent_affiliate_id: Optional[str] = None


@router.post("/enroll")
async def enroll_affiliate(
    body: EnrollAffiliateRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    now_utc = get_now_utc()
    trace_id = str(uuid4())

    if not authorization:
        raise HTTPException(status_code=401, detail="Operator authorization required.")

    expected = f"Bearer {_get_operator_secret()}"
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=403, detail="Invalid operator credentials.")

    if body.parent_affiliate_id:
        parent = db["affiliate_accounts"].find_one(
            {"affiliate_id": body.parent_affiliate_id, "status": "ACTIVE"}
        )
        if not parent:
            raise HTTPException(status_code=400, detail="Parent affiliate not found or inactive.")

    existing = db["affiliate_accounts"].find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=409, detail="Email already enrolled.")

    affiliate_id = str(uuid4())
    referral_link = f"https://beatvegas.app/ref/{affiliate_id}"

    db["affiliate_accounts"].insert_one(
        {
            "affiliate_id": affiliate_id,
            "name": body.name,
            "email": body.email,
            "status": "ACTIVE",
            "tier": "LEVEL_1",
            "parent_affiliate_id": body.parent_affiliate_id,
            "referral_link": referral_link,
            "stripe_connect_status": "PENDING",
            "stripe_connect_account_id": None,
            "notification_preference": body.notification_preference,
            "has_seen_affiliate_popup": False,
            "enrolled_at_utc": now_utc.isoformat(),
            "enrolled_by": "operator",
            "trace_id": trace_id,
            "tenant_id": "beatvegas",
        }
    )

    _sentinel_log("AFFILIATE_ENROLLED", "INFO", affiliate_id, trace_id, now_utc)

    try:
        from services.phase5_growth_agent import growth_agent

        growth_agent.send_message(
            user_id=affiliate_id,
            template_id="affiliate_welcome_1",
            trace_id=trace_id,
        )
    except Exception as exc:
        logger.error("[Affiliate] Growth message failed: %s", exc)

    return {
        "status": "ENROLLED",
        "affiliate_id": affiliate_id,
        "referral_link": referral_link,
        "trace_id": trace_id,
    }


def create_affiliate_commission(
    affiliate_id: str,
    user_id: str,
    tier: str,
    stripe_sub_id: str,
    stripe_invoice_id: str,
    trace_id: str,
) -> dict:
    now_utc = get_now_utc()

    from datetime import timedelta

    affiliate_doc = db["affiliate_accounts"].find_one(
        {"affiliate_id": affiliate_id}, {"status": 1, "parent_affiliate_id": 1}
    )
    if not affiliate_doc or affiliate_doc.get("status") != "ACTIVE":
        _sentinel_log("COMMISSION_SKIPPED_INACTIVE", "WARNING", affiliate_id, trace_id, now_utc)
        return {"status": "SKIPPED", "reason": "affiliate_not_active"}

    existing = db["affiliate_commission_log"].find_one({"stripe_invoice_id": stripe_invoice_id})
    if existing:
        return {"status": "ALREADY_EXISTS", "commission_id": existing.get("commission_id")}

    if tier == "platform":
        monthly_volume = _get_monthly_volume(affiliate_id, now_utc)
        commission_amt = _calculate_platform_commission(monthly_volume + 1)
    elif tier == "syndicate":
        commission_amt = SYNDICATE_COMMISSION
    else:
        return {"status": "ERROR", "reason": f"unknown_tier_{tier}"}

    commission_id = str(uuid4())
    net_30_date = (now_utc + timedelta(days=30)).date().isoformat()

    db["affiliate_commission_log"].insert_one(
        {
            "commission_id": commission_id,
            "affiliate_id": affiliate_id,
            "user_id": user_id,
            "tier": tier,
            "commission_amount": str(commission_amt),
            "commission_type": "FIRST_PAYMENT",
            "commission_status": "ELIGIBLE",
            "net_30_date": net_30_date,
            "stripe_sub_id": stripe_sub_id,
            "stripe_invoice_id": stripe_invoice_id,
            "created_at_utc": now_utc.isoformat(),
            "trace_id": trace_id,
            "tenant_id": "beatvegas",
        }
    )

    parent_id = affiliate_doc.get("parent_affiliate_id")
    if parent_id:
        l2_amount = (commission_amt * L2_PASSIVE_RATE).quantize(Decimal("0.01"))
        db["affiliate_commission_log"].insert_one(
            {
                "commission_id": str(uuid4()),
                "affiliate_id": parent_id,
                "user_id": user_id,
                "tier": tier,
                "commission_amount": str(l2_amount),
                "commission_type": "L2_PASSIVE",
                "commission_status": "ELIGIBLE",
                "net_30_date": net_30_date,
                "stripe_sub_id": stripe_sub_id,
                "stripe_invoice_id": stripe_invoice_id,
                "l1_affiliate_id": affiliate_id,
                "l1_commission_id": commission_id,
                "created_at_utc": now_utc.isoformat(),
                "trace_id": trace_id,
                "tenant_id": "beatvegas",
            }
        )

    _sentinel_log(
        "COMMISSION_CREATED",
        "INFO",
        affiliate_id,
        trace_id,
        now_utc,
        commission_id=commission_id,
        amount=str(commission_amt),
        tier=tier,
    )

    return {
        "status": "CREATED",
        "commission_id": commission_id,
        "amount": str(commission_amt),
        "net_30_date": net_30_date,
        "trace_id": trace_id,
    }


def create_retention_bonus(
    affiliate_id: str,
    user_id: str,
    stripe_sub_id: str,
    trace_id: str,
) -> dict:
    now_utc = get_now_utc()

    from datetime import timedelta

    existing = db["affiliate_commission_log"].find_one(
        {
            "affiliate_id": affiliate_id,
            "user_id": user_id,
            "commission_type": "RETENTION_BONUS",
        }
    )
    if existing:
        return {"status": "ALREADY_EXISTS"}

    commission_id = str(uuid4())
    net_30_date = (now_utc + timedelta(days=30)).date().isoformat()

    db["affiliate_commission_log"].insert_one(
        {
            "commission_id": commission_id,
            "affiliate_id": affiliate_id,
            "user_id": user_id,
            "tier": "platform",
            "commission_amount": str(RETENTION_BONUS_PLATFORM),
            "commission_type": "RETENTION_BONUS",
            "commission_status": "ELIGIBLE",
            "net_30_date": net_30_date,
            "stripe_sub_id": stripe_sub_id,
            "created_at_utc": now_utc.isoformat(),
            "trace_id": trace_id,
            "tenant_id": "beatvegas",
        }
    )

    affiliate_doc = db["affiliate_accounts"].find_one(
        {"affiliate_id": affiliate_id}, {"parent_affiliate_id": 1}
    )
    parent_id = (affiliate_doc or {}).get("parent_affiliate_id")
    if parent_id:
        l2_amount = (RETENTION_BONUS_PLATFORM * L2_PASSIVE_RATE).quantize(Decimal("0.01"))
        db["affiliate_commission_log"].insert_one(
            {
                "commission_id": str(uuid4()),
                "affiliate_id": parent_id,
                "user_id": user_id,
                "tier": "platform",
                "commission_amount": str(l2_amount),
                "commission_type": "L2_RETENTION_BONUS",
                "commission_status": "ELIGIBLE",
                "net_30_date": net_30_date,
                "l1_affiliate_id": affiliate_id,
                "l1_commission_id": commission_id,
                "created_at_utc": now_utc.isoformat(),
                "trace_id": trace_id,
                "tenant_id": "beatvegas",
            }
        )

    _sentinel_log(
        "RETENTION_BONUS_CREATED",
        "INFO",
        affiliate_id,
        trace_id,
        now_utc,
        commission_id=commission_id,
    )

    return {"status": "CREATED", "commission_id": commission_id, "amount": str(RETENTION_BONUS_PLATFORM)}


@router.get("/dashboard")
async def get_affiliate_dashboard(authorization: Optional[str] = Header(default=None)) -> dict:
    affiliate_id = _resolve_affiliate_from_auth(authorization)

    account = db["affiliate_accounts"].find_one(
        {"affiliate_id": affiliate_id},
        {
            "_id": 0,
            "name": 1,
            "email": 1,
            "status": 1,
            "referral_link": 1,
            "stripe_connect_status": 1,
            "enrolled_at_utc": 1,
            "notification_preference": 1,
        },
    )
    if not account:
        raise HTTPException(status_code=404, detail="Affiliate account not found.")

    commissions = list(
        db["affiliate_commission_log"]
        .find(
            {"affiliate_id": affiliate_id},
            {
                "_id": 0,
                "commission_id": 1,
                "commission_amount": 1,
                "commission_type": 1,
                "commission_status": 1,
                "net_30_date": 1,
                "created_at_utc": 1,
                "tier": 1,
            },
        )
        .sort("created_at_utc", -1)
        .limit(100)
    )

    payouts = list(
        db["affiliate_payout_log"]
        .find(
            {"affiliate_id": affiliate_id},
            {"_id": 0, "payout_id": 1, "amount": 1, "status": 1, "created_at_utc": 1},
        )
        .sort("created_at_utc", -1)
        .limit(25)
    )

    lifetime = sum(
        Decimal(str(c.get("commission_amount", "0")))
        for c in commissions
        if c.get("commission_status") == "PAID"
    )
    pending = sum(
        Decimal(str(c.get("commission_amount", "0")))
        for c in commissions
        if c.get("commission_status") == "ELIGIBLE"
    )

    eligible_dates = sorted(
        [
            c.get("net_30_date")
            for c in commissions
            if c.get("commission_status") == "ELIGIBLE" and c.get("net_30_date")
        ]
    )

    return {
        "affiliate": account,
        "referral_link": account.get("referral_link", f"https://beatvegas.app/ref/{affiliate_id}"),
        "earnings": {
            "lifetime_earned": str(lifetime),
            "pending_payout": str(pending),
            "next_payout_date": eligible_dates[0] if eligible_dates else None,
            "is_stripe_connected": account.get("stripe_connect_status") == "CONNECTED",
        },
        "commissions": commissions,
        "payouts": payouts,
    }


@router.get("/leaderboard")
async def get_affiliate_leaderboard(authorization: Optional[str] = Header(default=None)) -> dict:
    _resolve_affiliate_from_auth(authorization)

    pipeline = [
        {"$match": {"commission_status": "ELIGIBLE", "commission_type": "FIRST_PAYMENT"}},
        {"$group": {"_id": "$affiliate_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]

    results = list(db["affiliate_commission_log"].aggregate(pipeline))
    leaderboard = []
    for index, row in enumerate(results):
        aff = db["affiliate_accounts"].find_one({"affiliate_id": row["_id"]}, {"name": 1})
        name = (aff or {}).get("name", "Partner")
        leaderboard.append({"rank": index + 1, "name": name[:2] + "***"})

    return {"leaderboard": leaderboard}

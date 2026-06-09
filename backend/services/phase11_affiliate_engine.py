from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
from pymongo import ReturnDocument
from pymongo.errors import OperationFailure

from db.mongo import client, db
from services.phase5_growth_agent import growth_agent


PLATFORM_PRICE = 97.0
SYNDICATE_PRICE = 39.0
PAYOUT_MIN_THRESHOLD = 50.0

PLATFORM_TIERS = [(1, 4, 30.0), (5, 9, 35.0), (10, 19, 40.0), (20, 10_000, 50.0)]
SYNDICATE_TIERS = [(1, 4, 15.0), (5, 9, 18.0), (10, 19, 22.0), (20, 10_000, 28.0)]


class AffiliateEngine:
    def __init__(self) -> None:
        self.cookie_secret = os.getenv("AFFILIATE_COOKIE_SECRET", "phase11-affiliate-secret")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _hash_subscriber(self, user_id: str) -> str:
        salt = os.getenv("AFFILIATE_HASH_SALT", "phase11-affiliate-hash")
        return hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()

    def _hmac(self, raw: str) -> str:
        sig = hmac.new(self.cookie_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        return sig

    def build_signed_cookie(self, affiliate_id: str, click_id: str, clicked_at_utc: str) -> str:
        payload = {
            "affiliate_id": affiliate_id,
            "click_id": click_id,
            "clicked_at_utc": clicked_at_utc,
        }
        payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        signature = self._hmac(payload_raw)
        return base64.urlsafe_b64encode(f"{payload_raw}|{signature}".encode("utf-8")).decode("utf-8")

    def parse_signed_cookie(self, cookie_value: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
        try:
            decoded = base64.urlsafe_b64decode(cookie_value.encode("utf-8")).decode("utf-8")
            payload_raw, signature = decoded.rsplit("|", 1)
            if self._hmac(payload_raw) != signature:
                return None, "INVALID_SIGNATURE"
            payload = json.loads(payload_raw)
            return payload, None
        except Exception:
            return None, "INVALID_COOKIE"

    def enroll_affiliate(self, email: str, name: str, invited_by_operator_id: str, parent_affiliate_id: Optional[str] = None) -> Dict[str, Any]:
        affiliate_id = str(uuid.uuid4())
        invite_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        now = self._now()

        role = "L2_PARENT" if parent_affiliate_id is None else "L1_DIRECT"

        db["affiliate_accounts"].insert_one(
            {
                "affiliate_id": affiliate_id,
                "name": name,
                "email": email,
                "status": "INVITED",
                "program_access": "INVITE_ONLY",
                "role": role,
                "parent_affiliate_id": parent_affiliate_id,
                "invited_by_operator_id": invited_by_operator_id,
                "created_by_operator": invited_by_operator_id,
                "notification_preference": "both",
                "leaderboard_opt_out": False,
                "display_name": name,
                "stripe_connect_status": "PENDING",
                "created_at_utc": now,
                "updated_at_utc": now,
                "trace_id": trace_id,
            }
        )

        db["affiliate_invites"].insert_one(
            {
                "invite_id": invite_id,
                "affiliate_id": affiliate_id,
                "email": email,
                "expires_at_utc": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "status": "PENDING",
                "created_at_utc": now,
                "trace_id": trace_id,
            }
        )

        referral_link = f"https://beatvegas.app/ref/{affiliate_id}"
        growth_agent.send_message(
            user_id=affiliate_id,
            template_id="affiliate_welcome_1",
            trace_id=trace_id,
        )

        return {
            "affiliate_id": affiliate_id,
            "invite_id": invite_id,
            "referral_link": referral_link,
            "trace_id": trace_id,
        }

    def activate_affiliate(self, affiliate_id: str, stripe_connect_account_id: str) -> Dict[str, Any]:
        now = self._now()
        db["affiliate_accounts"].update_one(
            {"affiliate_id": affiliate_id},
            {
                "$set": {
                    "status": "ACTIVE",
                    "stripe_connect_status": "CONNECTED",
                    "stripe_connect_account_id": stripe_connect_account_id,
                    "updated_at_utc": now,
                }
            },
        )
        return {"status": "ok", "affiliate_id": affiliate_id}

    def record_referral_click(self, affiliate_id: str, ip_address: str) -> Dict[str, Any]:
        click_id = str(uuid.uuid4())
        clicked_at = self._now()
        trace_id = str(uuid.uuid4())

        db["affiliate_clicks"].insert_one(
            {
                "click_id": click_id,
                "affiliate_id": affiliate_id,
                "ip_address": ip_address,
                "is_converted": False,
                "clicked_at_utc": clicked_at,
                "created_at_utc": clicked_at,
                "trace_id": trace_id,
            }
        )

        cookie = self.build_signed_cookie(affiliate_id=affiliate_id, click_id=click_id, clicked_at_utc=clicked_at)
        return {"click_id": click_id, "cookie": cookie, "trace_id": trace_id}

    def _build_user_doc(self, email: str, username: str, password: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        now = self._now()
        password_bytes = password.encode("utf-8")[:72]
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")
        return {
            "_id": user_id or str(uuid.uuid4()),
            "email": email,
            "username": username,
            "hashed_password": hashed,
            "tier": "free",
            "created_at": now,
            "onboarding_complete": False,
        }

    def create_user_with_attribution_lock(
        self,
        email: str,
        username: str,
        password: str,
        signed_cookie: Optional[str],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        trace_id = str(uuid.uuid4())
        user_doc = self._build_user_doc(email=email, username=username, password=password, user_id=user_id)
        fraud_flag = None
        attributed = False

        parsed_cookie, cookie_error = (None, "MISSING_COOKIE") if not signed_cookie else self.parse_signed_cookie(signed_cookie)

        def _transaction_body(session) -> Dict[str, Any]:
            nonlocal fraud_flag, attributed

            db["users"].insert_one(user_doc, session=session)

            if cookie_error or not parsed_cookie:
                return {"attributed": False, "fraud_flag": fraud_flag}

            clicked_at = datetime.fromisoformat(parsed_cookie["clicked_at_utc"].replace("Z", "+00:00"))
            if clicked_at + timedelta(days=30) < now_dt:
                return {"attributed": False, "fraud_flag": "COOKIE_EXPIRED"}

            click_row = db["affiliate_clicks"].find_one(
                {"click_id": parsed_cookie["click_id"], "is_converted": False},
                session=session,
            )
            if not click_row:
                fraud_flag = "DUPLICATE_CLICK"
                db["sentinel_event_log"].insert_one(
                    {
                        "event_type": "DUPLICATE_CLICK",
                        "severity": "WARNING",
                        "affiliate_id": parsed_cookie["affiliate_id"],
                        "trace_id": trace_id,
                        "timestamp": now,
                        "tenant_id": None,
                    },
                    session=session,
                )
                return {"attributed": False, "fraud_flag": fraud_flag}

            affiliate = db["affiliate_accounts"].find_one(
                {"affiliate_id": parsed_cookie["affiliate_id"]},
                session=session,
            )
            if affiliate and str(affiliate.get("created_by_operator")) == str(user_doc["_id"]):
                fraud_flag = "SELF_REFERRAL"
                db["sentinel_event_log"].insert_one(
                    {
                        "event_type": "SELF_REFERRAL",
                        "severity": "WARNING",
                        "affiliate_id": parsed_cookie["affiliate_id"],
                        "trace_id": trace_id,
                        "timestamp": now,
                        "tenant_id": None,
                    },
                    session=session,
                )
                return {"attributed": False, "fraud_flag": fraud_flag}

            attribution_id = str(uuid.uuid4())
            db["affiliate_attributions"].insert_one(
                {
                    "attribution_id": attribution_id,
                    "affiliate_id": parsed_cookie["affiliate_id"],
                    "click_id": parsed_cookie["click_id"],
                    "user_id": str(user_doc["_id"]),
                    "locked_at_utc": now,
                    "immutable_guard": "LOCKED",
                    "trace_id": trace_id,
                    "tenant_id": None,
                },
                session=session,
            )

            db["affiliate_clicks"].update_one(
                {"click_id": parsed_cookie["click_id"], "is_converted": False},
                {
                    "$set": {
                        "is_converted": True,
                        "converted_user_id": str(user_doc["_id"]),
                        "converted_at_utc": now,
                        "trace_id": trace_id,
                    }
                },
                session=session,
            )
            attributed = True
            return {"attributed": True, "fraud_flag": None}

        transaction_used = False
        try:
            with client.start_session() as session:
                with session.start_transaction():
                    result = _transaction_body(session)
                    transaction_used = True
        except Exception as exc:
            # Fallback for environments without transactions
            if "Transaction numbers are only allowed" in str(exc):
                result = _transaction_body(None)
            else:
                raise

        return {
            "user_id": str(user_doc["_id"]),
            "attributed": result["attributed"],
            "fraud_flag": result["fraud_flag"],
            "trace_id": trace_id,
            "transaction_used": transaction_used,
        }

    def _direct_commission_amount(self, subscription_tier: str, conversions_this_month: int) -> Tuple[float, str]:
        tiers = PLATFORM_TIERS if subscription_tier == "PLATFORM" else SYNDICATE_TIERS
        for lower, upper, amount in tiers:
            if lower <= conversions_this_month <= upper:
                label = "20_PLUS" if lower == 20 else f"{lower}_{upper}"
                return amount, label
        return tiers[0][2], "1_4"

    def _log_commission_event(
        self,
        affiliate_id: str,
        subscriber_user_id: str,
        subscription_tier: str,
        commission_type: str,
        amount: float,
        conversions_this_month: int,
        volume_tier: str,
        status: str = "ELIGIBLE",
        parent_affiliate_id: Optional[str] = None,
        net_30_date: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        commission_id = str(uuid.uuid4())
        trace = trace_id or str(uuid.uuid4())
        event_doc = {
            "commission_id": commission_id,
            "affiliate_id": affiliate_id,
            "parent_affiliate_id": parent_affiliate_id,
            "subscriber_user_hash": self._hash_subscriber(subscriber_user_id),
            "subscription_tier": subscription_tier,
            "commission_type": commission_type,
            "amount": amount,
            "volume_tier": volume_tier,
            "conversions_this_month": conversions_this_month,
            "status": status,
            "net_30_date": net_30_date or (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),
            "trace_id": trace,
            "created_at_utc": self._now(),
            "tenant_id": None,
        }
        db["affiliate_commission_log"].insert_one(event_doc)
        return commission_id

    def process_conversion(self, user_id: str, subscription_tier: str, first_payment_cleared_at_utc: Optional[str] = None) -> Dict[str, Any]:
        attribution = db["affiliate_attributions"].find_one({"user_id": user_id})
        if not attribution:
            return {"commission_created": False, "reason": "UNATTRIBUTED"}

        affiliate_id = attribution["affiliate_id"]
        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()
        monthly_conversions = db["affiliate_commission_log"].count_documents(
            {
                "affiliate_id": affiliate_id,
                "commission_type": "DIRECT",
                "created_at_utc": {"$gte": month_start},
            }
        ) + 1

        amount, volume_tier = self._direct_commission_amount(subscription_tier, monthly_conversions)
        trace_id = str(uuid.uuid4())
        commission_id = self._log_commission_event(
            affiliate_id=affiliate_id,
            subscriber_user_id=user_id,
            subscription_tier=subscription_tier,
            commission_type="DIRECT",
            amount=amount,
            conversions_this_month=monthly_conversions,
            volume_tier=volume_tier,
            trace_id=trace_id,
        )

        affiliate = db["affiliate_accounts"].find_one({"affiliate_id": affiliate_id}) or {}
        parent_affiliate_id = affiliate.get("parent_affiliate_id")
        level2_commission_id = None
        if parent_affiliate_id:
            level2_amount = round(amount * 0.10, 2)
            level2_commission_id = self._log_commission_event(
                affiliate_id=parent_affiliate_id,
                parent_affiliate_id=parent_affiliate_id,
                subscriber_user_id=user_id,
                subscription_tier=subscription_tier,
                commission_type="LEVEL2_PASSIVE",
                amount=level2_amount,
                conversions_this_month=monthly_conversions,
                volume_tier=volume_tier,
                trace_id=trace_id,
            )

        growth_agent.send_message(user_id=affiliate_id, template_id="affiliate_conversion", trace_id=trace_id)
        if volume_tier in {"5_9", "10_19", "20_PLUS"}:
            growth_agent.send_message(user_id=affiliate_id, template_id="affiliate_tier_upgrade", trace_id=trace_id)

        return {
            "commission_created": True,
            "commission_id": commission_id,
            "level2_commission_id": level2_commission_id,
            "amount": amount,
            "volume_tier": volume_tier,
            "conversions_this_month": monthly_conversions,
            "trace_id": trace_id,
        }

    def process_platform_retention_bonus(self, user_id: str) -> Dict[str, Any]:
        attribution = db["affiliate_attributions"].find_one({"user_id": user_id})
        if not attribution:
            return {"bonus_created": False, "reason": "UNATTRIBUTED"}

        affiliate_id = attribution["affiliate_id"]
        existing = db["affiliate_commission_log"].find_one(
            {
                "affiliate_id": affiliate_id,
                "subscriber_user_hash": self._hash_subscriber(user_id),
                "commission_type": "RETENTION_BONUS",
            }
        )
        if existing:
            return {"bonus_created": False, "reason": "ALREADY_GRANTED"}

        trace_id = str(uuid.uuid4())
        bonus_id = self._log_commission_event(
            affiliate_id=affiliate_id,
            subscriber_user_id=user_id,
            subscription_tier="PLATFORM",
            commission_type="RETENTION_BONUS",
            amount=20.0,
            conversions_this_month=0,
            volume_tier="N_A",
            trace_id=trace_id,
        )

        affiliate = db["affiliate_accounts"].find_one({"affiliate_id": affiliate_id}) or {}
        parent_affiliate_id = affiliate.get("parent_affiliate_id")
        level2_bonus_id = None
        if parent_affiliate_id:
            level2_bonus_id = self._log_commission_event(
                affiliate_id=parent_affiliate_id,
                parent_affiliate_id=parent_affiliate_id,
                subscriber_user_id=user_id,
                subscription_tier="PLATFORM",
                commission_type="LEVEL2_PASSIVE",
                amount=2.0,
                conversions_this_month=0,
                volume_tier="N_A",
                trace_id=trace_id,
            )

        growth_agent.send_message(user_id=affiliate_id, template_id="affiliate_retention_bonus", trace_id=trace_id)
        return {
            "bonus_created": True,
            "bonus_commission_id": bonus_id,
            "level2_bonus_id": level2_bonus_id,
            "trace_id": trace_id,
        }

    def mark_commission_fraud_hold(self, commission_id: str, reason: str) -> Dict[str, Any]:
        base = db["affiliate_commission_log"].find_one({"commission_id": commission_id})
        if not base:
            return {"status": "not_found"}

        trace_id = str(uuid.uuid4())
        self._log_commission_event(
            affiliate_id=base["affiliate_id"],
            parent_affiliate_id=base.get("parent_affiliate_id"),
            subscriber_user_id=base.get("subscriber_user_hash", "unknown"),
            subscription_tier=base["subscription_tier"],
            commission_type=base["commission_type"],
            amount=base["amount"],
            conversions_this_month=base.get("conversions_this_month", 0),
            volume_tier=base.get("volume_tier", "N_A"),
            status="FRAUD_HOLD",
            net_30_date=base.get("net_30_date"),
            trace_id=trace_id,
        )

        db["sentinel_event_log"].insert_one(
            {
                "event_type": reason,
                "severity": "WARNING",
                "affiliate_id": base["affiliate_id"],
                "timestamp": self._now(),
                "trace_id": trace_id,
                "tenant_id": None,
            }
        )
        growth_agent.send_message(user_id=base["affiliate_id"], template_id="affiliate_fraud_hold", trace_id=trace_id)
        return {"status": "ok", "trace_id": trace_id}

    def run_monthly_payout_batch(self) -> Dict[str, Any]:
        today = datetime.now(timezone.utc).date().isoformat()
        trace_id = str(uuid.uuid4())

        eligible = list(
            db["affiliate_commission_log"].find(
                {
                    "status": "ELIGIBLE",
                    "net_30_date": {"$lte": today},
                }
            )
        )

        grouped: Dict[str, float] = {}
        commissions_by_affiliate: Dict[str, list] = {}
        for row in eligible:
            affiliate_id = row["affiliate_id"]
            grouped[affiliate_id] = grouped.get(affiliate_id, 0.0) + float(row["amount"])
            commissions_by_affiliate.setdefault(affiliate_id, []).append(row)

        paid_count = 0
        total_amount = 0.0
        failures = 0

        for affiliate_id, total in grouped.items():
            payout_id = str(uuid.uuid4())
            if total < PAYOUT_MIN_THRESHOLD:
                db["affiliate_payout_log"].insert_one(
                    {
                        "payout_id": payout_id,
                        "affiliate_id": affiliate_id,
                        "status": "ROLLED_BELOW_THRESHOLD",
                        "amount": total,
                        "created_at_utc": self._now(),
                        "trace_id": trace_id,
                        "tenant_id": None,
                    }
                )
                continue

            # Stripe Connect integration point; simulated success for deterministic batch automation.
            transfer_ok = True
            if transfer_ok:
                paid_count += 1
                total_amount += total
                db["affiliate_payout_log"].insert_one(
                    {
                        "payout_id": payout_id,
                        "affiliate_id": affiliate_id,
                        "status": "PAID",
                        "amount": total,
                        "created_at_utc": self._now(),
                        "trace_id": trace_id,
                        "tenant_id": None,
                        "provider": "stripe_connect",
                    }
                )

                for row in commissions_by_affiliate[affiliate_id]:
                    self._log_commission_event(
                        affiliate_id=row["affiliate_id"],
                        parent_affiliate_id=row.get("parent_affiliate_id"),
                        subscriber_user_id=row.get("subscriber_user_hash", "unknown"),
                        subscription_tier=row["subscription_tier"],
                        commission_type=row["commission_type"],
                        amount=float(row["amount"]),
                        conversions_this_month=int(row.get("conversions_this_month", 0)),
                        volume_tier=row.get("volume_tier", "N_A"),
                        status="PAID",
                        net_30_date=row.get("net_30_date"),
                        trace_id=trace_id,
                    )
                growth_agent.send_message(user_id=affiliate_id, template_id="affiliate_payout_confirm", trace_id=trace_id)
            else:
                failures += 1

        db["affiliate_payout_batches"].insert_one(
            {
                "batch_id": str(uuid.uuid4()),
                "run_date_utc": self._now(),
                "total_affiliates_paid": paid_count,
                "total_amount": round(total_amount, 2),
                "failures_count": failures,
                "trace_id": trace_id,
                "tenant_id": None,
            }
        )

        return {
            "paid_affiliates": paid_count,
            "total_amount": round(total_amount, 2),
            "failures_count": failures,
            "trace_id": trace_id,
        }

    def submit_affiliate_interest(
        self,
        name: str,
        email: str,
        audience_desc: Optional[str] = None,
        audience_size: Optional[str] = None,
        referral_source: Optional[str] = None,
    ) -> Dict[str, Any]:
        interest_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        now = self._now()
        db["affiliate_interest_log"].insert_one(
            {
                "interest_id": interest_id,
                "name": name,
                "email": email,
                "audience_desc": audience_desc,
                "audience_size": audience_size,
                "referral_source": referral_source,
                "status": "PENDING",
                "invited_at_utc": None,
                "submitted_at_utc": now,
                "trace_id": trace_id,
            }
        )
        return {"interest_id": interest_id, "trace_id": trace_id, "status": "PENDING"}

    def list_affiliate_interest(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status
        rows = list(db["affiliate_interest_log"].find(query).sort("submitted_at_utc", -1))
        for row in rows:
            row["_id"] = str(row["_id"])
        return rows

    def invite_interest(self, interest_id: str, invited_by_operator_id: str, parent_affiliate_id: Optional[str] = None) -> Dict[str, Any]:
        row = db["affiliate_interest_log"].find_one({"interest_id": interest_id})
        if not row:
            return {"status": "not_found"}

        enrolled = self.enroll_affiliate(
            email=row["email"],
            name=row["name"],
            invited_by_operator_id=invited_by_operator_id,
            parent_affiliate_id=parent_affiliate_id,
        )
        db["affiliate_interest_log"].update_one(
            {"interest_id": interest_id},
            {
                "$set": {
                    "status": "INVITED",
                    "invited_at_utc": self._now(),
                    "affiliate_id": enrolled["affiliate_id"],
                    "invite_trace_id": enrolled["trace_id"],
                }
            },
        )
        return {"status": "INVITED", "affiliate_id": enrolled["affiliate_id"], "trace_id": enrolled["trace_id"]}

    def decline_interest(self, interest_id: str) -> Dict[str, Any]:
        updated = db["affiliate_interest_log"].update_one(
            {"interest_id": interest_id},
            {"$set": {"status": "DECLINED"}},
        )
        return {"status": "DECLINED" if updated.matched_count else "not_found"}

    def get_recruitment_popup_state(self, user_id: str) -> Dict[str, Any]:
        user = db["users"].find_one({"_id": user_id})
        if not user:
            return {"eligible": False, "show_popup": False, "reason": "USER_NOT_FOUND"}

        if user.get("has_seen_affiliate_popup") is True:
            return {"eligible": False, "show_popup": False, "reason": "ALREADY_SEEN"}

        created_at_raw = user.get("created_at")
        account_age_ok = False
        if isinstance(created_at_raw, str):
            try:
                created_at_dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                account_age_ok = (datetime.now(timezone.utc) - created_at_dt).days >= 30
            except Exception:
                account_age_ok = False

        is_platform = str(user.get("tier", "")).lower() in {"platform", "beatvegas_platform"}
        eligible = bool(is_platform and account_age_ok)
        return {
            "eligible": eligible,
            "show_popup": eligible,
            "reason": "ELIGIBLE" if eligible else "NOT_ELIGIBLE",
        }

    def dismiss_recruitment_popup(self, user_id: str) -> Dict[str, Any]:
        db["users"].update_one(
            {"_id": user_id},
            {"$set": {"has_seen_affiliate_popup": True, "affiliate_popup_dismissed_at_utc": self._now()}},
        )
        return {"status": "ok"}

    def update_notification_preference(self, affiliate_id: str, preference: str) -> Dict[str, Any]:
        normalized = preference.lower().strip()
        if normalized not in {"email_only", "platform_only", "both"}:
            raise OperationFailure("notification_preference must be email_only, platform_only, or both")
        db["affiliate_accounts"].update_one(
            {"affiliate_id": affiliate_id},
            {"$set": {"notification_preference": normalized, "updated_at_utc": self._now()}},
        )
        return {"status": "ok", "notification_preference": normalized}

    def update_leaderboard_preferences(self, affiliate_id: str, display_name: str, opt_out: bool) -> Dict[str, Any]:
        db["affiliate_accounts"].update_one(
            {"affiliate_id": affiliate_id},
            {
                "$set": {
                    "display_name": display_name,
                    "leaderboard_opt_out": bool(opt_out),
                    "updated_at_utc": self._now(),
                }
            },
        )
        return {"status": "ok"}

    def get_affiliate_leaderboard(self, affiliate_id: str) -> Dict[str, Any]:
        rows = list(
            db["affiliate_accounts"].find(
                {"status": "ACTIVE", "leaderboard_opt_out": {"$ne": True}},
                {"affiliate_id": 1, "display_name": 1, "name": 1},
            )
        )

        scored = []
        for row in rows:
            aid = row.get("affiliate_id")
            conversions = db["affiliate_attributions"].count_documents({"affiliate_id": aid})
            scored.append(
                {
                    "affiliate_id": aid,
                    "display_name": row.get("display_name") or row.get("name") or "Affiliate",
                    "conversions": conversions,
                }
            )

        scored.sort(key=lambda x: x["conversions"], reverse=True)
        total = max(len(scored), 1)

        my_rank = None
        my_percentile = None
        for idx, entry in enumerate(scored, start=1):
            if entry["affiliate_id"] == affiliate_id:
                my_rank = idx
                my_percentile = max(1, int(round((1 - ((idx - 1) / total)) * 100)))
                break

        return {
            "my_rank": my_rank,
            "my_percentile": my_percentile,
            "monthly_leaders": scored[:10],
            "all_time_leaders": scored[:10],
        }

    def get_affiliate_dashboard(self, affiliate_id: str) -> Dict[str, Any]:
        account = db["affiliate_accounts"].find_one({"affiliate_id": affiliate_id, "status": "ACTIVE"})
        if not account:
            raise OperationFailure("Affiliate not found or inactive")

        referral_link = f"https://beatvegas.app/ref/{affiliate_id}"
        clicks = db["affiliate_clicks"].count_documents({"affiliate_id": affiliate_id})
        conversions = db["affiliate_attributions"].count_documents({"affiliate_id": affiliate_id})

        commissions = list(db["affiliate_commission_log"].find({"affiliate_id": affiliate_id}).sort("created_at_utc", -1).limit(100))
        payouts = list(db["affiliate_payout_log"].find({"affiliate_id": affiliate_id}).sort("created_at_utc", -1).limit(100))

        month_start = datetime(datetime.now(timezone.utc).year, datetime.now(timezone.utc).month, 1, tzinfo=timezone.utc).isoformat()
        month_commissions = [c for c in commissions if c.get("created_at_utc", "") >= month_start and c.get("status") == "ELIGIBLE"]
        month_total = round(sum(float(c.get("amount", 0.0)) for c in month_commissions), 2)

        sub_affiliates = list(db["affiliate_accounts"].find({"parent_affiliate_id": affiliate_id}, {"affiliate_id": 1, "name": 1}))
        level2_earnings = round(
            sum(float(c.get("amount", 0.0)) for c in commissions if c.get("commission_type") == "LEVEL2_PASSIVE"),
            2,
        )
        leaderboard = self.get_affiliate_leaderboard(affiliate_id)

        return {
            "affiliate_id": affiliate_id,
            "referral_link": referral_link,
            "stats": {
                "clicks": clicks,
                "conversions": conversions,
                "commission_this_month": month_total,
            },
            "all_time": {
                "total_clicks": clicks,
                "total_conversions": conversions,
                "total_paid": round(sum(float(p.get("amount", 0.0)) for p in payouts if p.get("status") == "PAID"), 2),
                "total_pending": round(sum(float(c.get("amount", 0.0)) for c in commissions if c.get("status") == "ELIGIBLE"), 2),
            },
            "payout_history": payouts,
            "commission_detail": commissions,
            "level2_earnings": level2_earnings,
            "sub_affiliates": sub_affiliates,
            "leaderboard": leaderboard,
            "notification_preference": account.get("notification_preference", "both"),
            "leaderboard_opt_out": bool(account.get("leaderboard_opt_out", False)),
            "display_name": account.get("display_name") or account.get("name") or "Affiliate",
            "ftc_disclosure_required": True,
        }


affiliate_engine = AffiliateEngine()

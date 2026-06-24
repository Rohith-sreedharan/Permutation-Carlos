from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Header
from pydantic import BaseModel, EmailStr

from services.phase11_affiliate_engine import affiliate_engine


router = APIRouter(prefix="/api/v1/affiliate-program", tags=["phase11-affiliate"])


class InviteAffiliateRequest(BaseModel):
    name: str
    email: EmailStr
    invited_by_operator_id: str
    parent_affiliate_id: Optional[str] = None


class ActivateAffiliateRequest(BaseModel):
    affiliate_id: str
    stripe_connect_account_id: str


class ClickRequest(BaseModel):
    affiliate_id: str
    ip_address: str


class SignupRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    user_id: Optional[str] = None


class ConversionRequest(BaseModel):
    user_id: str
    subscription_tier: str


class RetentionBonusRequest(BaseModel):
    user_id: str


class InterestSubmitRequest(BaseModel):
    name: str
    email: EmailStr
    audience_desc: Optional[str] = None
    audience_size: Optional[str] = None
    referral_source: Optional[str] = None


class InviteInterestRequest(BaseModel):
    invited_by_operator_id: str
    parent_affiliate_id: Optional[str] = None


class PreferenceRequest(BaseModel):
    notification_preference: str


class LeaderboardPrefsRequest(BaseModel):
    display_name: str
    opt_out: bool = False


@router.post("/invite")
def invite_affiliate(payload: InviteAffiliateRequest):
    return affiliate_engine.enroll_affiliate(
        email=payload.email,
        name=payload.name,
        invited_by_operator_id=payload.invited_by_operator_id,
        parent_affiliate_id=payload.parent_affiliate_id,
    )


@router.post("/activate")
def activate_affiliate(payload: ActivateAffiliateRequest):
    return affiliate_engine.activate_affiliate(
        affiliate_id=payload.affiliate_id,
        stripe_connect_account_id=payload.stripe_connect_account_id,
    )


@router.post("/click")
def record_click(payload: ClickRequest):
    return affiliate_engine.record_referral_click(
        affiliate_id=payload.affiliate_id,
        ip_address=payload.ip_address,
    )


@router.post("/signup")
def signup_with_attribution(payload: SignupRequest, bv_ref: Optional[str] = Cookie(default=None)):
    return affiliate_engine.create_user_with_attribution_lock(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        signed_cookie=bv_ref,
        user_id=payload.user_id,
    )


@router.post("/conversion")
def process_conversion(payload: ConversionRequest):
    tier = payload.subscription_tier.upper()
    if tier not in {"PLATFORM", "SYNDICATE"}:
        raise HTTPException(status_code=400, detail="subscription_tier must be PLATFORM or SYNDICATE")
    return affiliate_engine.process_conversion(user_id=payload.user_id, subscription_tier=tier)


@router.post("/retention-bonus")
def retention_bonus(payload: RetentionBonusRequest):
    return affiliate_engine.process_platform_retention_bonus(user_id=payload.user_id)


@router.post("/payout-batch/run")
def run_payout_batch():
    return affiliate_engine.run_monthly_payout_batch()


@router.get("/dashboard/{affiliate_id}")
def affiliate_dashboard(affiliate_id: str):
    try:
        return affiliate_engine.get_affiliate_dashboard(affiliate_id=affiliate_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/interest")
def submit_interest(payload: InterestSubmitRequest):
    return affiliate_engine.submit_affiliate_interest(
        name=payload.name,
        email=payload.email,
        audience_desc=payload.audience_desc,
        audience_size=payload.audience_size,
        referral_source=payload.referral_source,
    )


@router.get("/aos/applicants")
def list_applicants(status: Optional[str] = None):
    return {"applicants": affiliate_engine.list_affiliate_interest(status=status)}


@router.post("/aos/applicants/{interest_id}/invite")
def invite_applicant(interest_id: str, payload: InviteInterestRequest):
    result = affiliate_engine.invite_interest(
        interest_id=interest_id,
        invited_by_operator_id=payload.invited_by_operator_id,
        parent_affiliate_id=payload.parent_affiliate_id,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="interest_id not found")
    return result


@router.post("/aos/applicants/{interest_id}/decline")
def decline_applicant(interest_id: str):
    result = affiliate_engine.decline_interest(interest_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="interest_id not found")
    return result


def _user_id_from_auth(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = parts[1]
    if token.startswith("user:"):
        return token.split(":", 1)[1]
    return token


@router.get("/recruitment/popup-status")
def recruitment_popup_status(Authorization: Optional[str] = Header(default=None)):
    user_id = _user_id_from_auth(Authorization)
    return affiliate_engine.get_recruitment_popup_state(user_id=user_id)


@router.post("/recruitment/dismiss")
def recruitment_popup_dismiss(Authorization: Optional[str] = Header(default=None)):
    user_id = _user_id_from_auth(Authorization)
    return affiliate_engine.dismiss_recruitment_popup(user_id=user_id)


@router.post("/{affiliate_id}/notification-preference")
def set_notification_preference(affiliate_id: str, payload: PreferenceRequest):
    return affiliate_engine.update_notification_preference(
        affiliate_id=affiliate_id,
        preference=payload.notification_preference,
    )


@router.post("/{affiliate_id}/leaderboard-preferences")
def set_leaderboard_preferences(affiliate_id: str, payload: LeaderboardPrefsRequest):
    return affiliate_engine.update_leaderboard_preferences(
        affiliate_id=affiliate_id,
        display_name=payload.display_name,
        opt_out=payload.opt_out,
    )


@router.get("/leaderboard/{affiliate_id}")
def affiliate_leaderboard(affiliate_id: str):
    return affiliate_engine.get_affiliate_leaderboard(affiliate_id=affiliate_id)


@router.get("/me/dashboard")
def affiliate_dashboard_me(Authorization: Optional[str] = Header(default=None)):
    affiliate_id = _user_id_from_auth(Authorization)
    return affiliate_engine.get_affiliate_dashboard(affiliate_id=affiliate_id)


@router.post("/me/notification-preference")
def set_notification_preference_me(payload: PreferenceRequest, Authorization: Optional[str] = Header(default=None)):
    affiliate_id = _user_id_from_auth(Authorization)
    return affiliate_engine.update_notification_preference(
        affiliate_id=affiliate_id,
        preference=payload.notification_preference,
    )


@router.post("/me/leaderboard-preferences")
def set_leaderboard_preferences_me(payload: LeaderboardPrefsRequest, Authorization: Optional[str] = Header(default=None)):
    affiliate_id = _user_id_from_auth(Authorization)
    return affiliate_engine.update_leaderboard_preferences(
        affiliate_id=affiliate_id,
        display_name=payload.display_name,
        opt_out=payload.opt_out,
    )


@router.get("/me/leaderboard")
def affiliate_leaderboard_me(Authorization: Optional[str] = Header(default=None)):
    affiliate_id = _user_id_from_auth(Authorization)
    return affiliate_engine.get_affiliate_leaderboard(affiliate_id=affiliate_id)

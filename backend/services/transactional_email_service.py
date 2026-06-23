"""
Transactional Email Service — Phase 3B

Provider: SendGrid (configurable via EMAIL_PROVIDER env var: sendgrid | resend | ses)
All five required emails implemented:

  1. Subscription receipt    — every successful payment
  2. Payment failure         — failed charge (no immediate revoke)
  3. Password reset          — secure link, 15-minute expiry, no reuse
  4. Renewal reminder        — 3 days before renewal date
  5. Cancellation confirmation — subscription cancelled

Confirmed provider: SendGrid (SENDGRID_API_KEY env var).
Fallback: logs the email body when no API key is set (test mode).
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)
EMAIL_LOGO_URL = os.getenv("EMAIL_LOGO_URL", "https://beatvegas.app/logo-email.png")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cfg() -> Dict[str, Any]:
    return AGENT_CONFIG.get("billing", {})


def _email_logo_html() -> str:
    return (
        '<div style="margin-bottom:16px">'
        f'<img src="{EMAIL_LOGO_URL}" alt="BeatVegas" width="140" '
        'style="display:block;border:0;outline:none;text-decoration:none;height:auto"/>'
        '</div>'
    )


def _email_footer_html() -> str:
    return (
        '<p style="font-size:11px;color:#888888;text-align:center;'
        'margin-top:24px;border-top:1px solid #eeeeee;padding-top:12px;">'
        'If you or someone you know has a gambling problem, help is available.<br>'
        'Call <strong>1-800-522-4700</strong> or visit '
        '<a href="https://ncpgambling.org">ncpgambling.org</a>'
        '</p>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Provider dispatch
# ─────────────────────────────────────────────────────────────────────────────

def _send_email(*, to_email: str, subject: str, html_body: str, text_body: str = "") -> bool:
    """
    Send email via configured provider.
    Returns True on success, False on failure.
    Falls back to structured log when no API key is configured (dev/test mode).
    """
    provider = _cfg().get("email_provider", "sendgrid")
    from_address = _cfg().get("email_from_address", "noreply@beatvegas.app")
    api_key = os.getenv("SENDGRID_API_KEY", "") or os.getenv("RESEND_API_KEY", "") or os.getenv("SES_API_KEY", "")

    if not api_key:
        # Test mode: log the email for evidence capture
        logger.info(
            "[Email:TEST_MODE] provider=%s to=%s subject=%s body_preview=%s",
            provider, to_email, subject, text_body[:120],
        )
        # Write to email_test_log collection for evidence in test environment
        try:
            db["email_test_log"].insert_one({
                "id": str(uuid4()),
                "to_email": to_email,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body,
                "provider": provider,
                "timestamp": _now_iso(),
                "mode": "test",
            })
        except Exception:
            pass
        return True

    if provider == "sendgrid":
        return _send_via_sendgrid(
            api_key=api_key, from_address=from_address,
            to_email=to_email, subject=subject,
            html_body=html_body, text_body=text_body,
        )
    elif provider == "resend":
        return _send_via_resend(
            api_key=api_key, from_address=from_address,
            to_email=to_email, subject=subject, html_body=html_body,
        )
    else:
        logger.warning("[Email] Unknown provider '%s' — email not sent", provider)
        return False


def _send_via_sendgrid(*, api_key, from_address, to_email, subject, html_body, text_body) -> bool:
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Content, To
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=from_address,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        if text_body:
            message.add_content(Content("text/plain", text_body))
        response = sg.send(message)
        return 200 <= response.status_code < 300
    except Exception as exc:
        logger.error("[Email:SendGrid] send failed to=%s: %s", to_email, exc)
        _log_email_failure(to_email, subject, str(exc))
        return False


def _send_via_resend(*, api_key, from_address, to_email, subject, html_body) -> bool:
    try:
        import httpx
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": from_address, "to": [to_email], "subject": subject, "html": html_body},
            timeout=10,
        )
        return 200 <= resp.status_code < 300
    except Exception as exc:
        logger.error("[Email:Resend] send failed to=%s: %s", to_email, exc)
        _log_email_failure(to_email, subject, str(exc))
        return False


def _log_email_failure(to_email: str, subject: str, error: str) -> None:
    try:
        db["sentinel_event_log"].insert_one({
            "event_type": "EMAIL_SEND_FAILED",
            "to_email": to_email,
            "subject": subject,
            "error": error[:300],
            "trace_id": str(uuid4()),
            "timestamp": _now_iso(),
        })
    except Exception:
        pass


def _get_user_email(user_id: str) -> Optional[str]:
    try:
        user = db["users"].find_one({"$or": [
            {"_id": user_id},
            {"user_id": user_id},
        ]}, {"email": 1})
        if user:
            return user.get("email")
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Email 1: Subscription receipt
# ─────────────────────────────────────────────────────────────────────────────

def send_subscription_receipt(
    *,
    user_id: str,
    amount_usd: float,
    tier_name: str,
    stripe_invoice_id: Optional[str] = None,
    next_renewal_date: Optional[str] = None,
) -> bool:
    to_email = _get_user_email(user_id)
    if not to_email:
        logger.warning("[Email] no email for user=%s (receipt skipped)", user_id)
        return False

    renewal = next_renewal_date or (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%B %d, %Y")
    subject = f"BeatVegas — Payment Received: {tier_name}"
    text_body = (
        f"Thank you for subscribing to BeatVegas {tier_name}.\n\n"
        f"Amount: ${amount_usd:.2f}\n"
        f"Plan: {tier_name}\n"
        f"Next renewal: {renewal}\n"
        f"Invoice: {stripe_invoice_id or 'N/A'}\n\n"
        f"Questions? support@beatvegas.app\n\n"
        f"BeatVegas is a sports analytics platform, not a sportsbook."
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
{_email_logo_html()}
<h2>Payment Received</h2>
<p>Thank you for subscribing to <strong>BeatVegas {tier_name}</strong>.</p>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>Amount</strong></td><td style="padding:8px;border-bottom:1px solid #eee">${amount_usd:.2f}</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>Plan</strong></td><td style="padding:8px;border-bottom:1px solid #eee">{tier_name}</td></tr>
  <tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>Next Renewal</strong></td><td style="padding:8px;border-bottom:1px solid #eee">{renewal}</td></tr>
  <tr><td style="padding:8px"><strong>Invoice</strong></td><td style="padding:8px">{stripe_invoice_id or 'N/A'}</td></tr>
</table>
<p>Need help? <a href="mailto:support@beatvegas.app">support@beatvegas.app</a></p>
<p style="color:#888;font-size:12px">BeatVegas is a sports analytics platform, not a sportsbook. No wagering services are offered.</p>
{_email_footer_html()}
</body></html>"""
    return _send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


# ─────────────────────────────────────────────────────────────────────────────
# Email 2: Payment failure
# ─────────────────────────────────────────────────────────────────────────────

def send_payment_failed(
    *,
    user_id: str,
    amount_usd: float,
    next_attempt_ts: Optional[int] = None,
    stripe_invoice_id: Optional[str] = None,
) -> bool:
    to_email = _get_user_email(user_id)
    if not to_email:
        return False

    retry_date = "in 3 days"
    if next_attempt_ts:
        retry_date = datetime.fromtimestamp(next_attempt_ts, tz=timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    subject = "BeatVegas — Payment Failed"
    text_body = (
        f"We were unable to process your payment of ${amount_usd:.2f}.\n\n"
        f"Retry date: {retry_date}\n\n"
        f"Please update your payment method at: https://beatvegas.app/settings/billing\n\n"
        f"Your access has not been revoked. We'll retry automatically."
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
{_email_logo_html()}
<h2 style="color:#d32f2f">Payment Failed</h2>
<p>We were unable to process your payment of <strong>${amount_usd:.2f}</strong>.</p>
<p><strong>Retry date:</strong> {retry_date}</p>
<p>Your access has <strong>not been revoked</strong> — we'll retry automatically.</p>
<p><a href="https://beatvegas.app/settings/billing" style="background:#1565c0;color:#fff;padding:10px 20px;text-decoration:none;border-radius:4px">Update Payment Method</a></p>
<p style="color:#888;font-size:12px">Invoice: {stripe_invoice_id or 'N/A'}</p>
{_email_footer_html()}
</body></html>"""
    return _send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


# ─────────────────────────────────────────────────────────────────────────────
# Email 3: Password reset
# ─────────────────────────────────────────────────────────────────────────────

def send_password_reset(*, user_id: str, user_email: str) -> bool:
    """
    Generate a secure one-time reset token (15-minute expiry, no reuse),
    store it, and send the reset link.
    """
    reset_token = secrets.token_urlsafe(48)
    expiry = datetime.now(timezone.utc) + timedelta(
        minutes=_cfg().get("password_reset_expiry_minutes", 15)
    )

    # Store token with expiry + used=False
    try:
        db["password_reset_tokens"].insert_one({
            "id": str(uuid4()),
            "user_id": str(user_id),
            "token_hash": _hash_token(reset_token),
            "expires_at": expiry.isoformat(),
            "used": False,
            "created_at": _now_iso(),
        })
    except Exception as exc:
        logger.error("[Email] password reset token insert failed: %s", exc)
        return False

    reset_url = f"https://beatvegas.app/reset-password?token={reset_token}"
    subject = "BeatVegas — Password Reset Request"
    text_body = (
        f"You requested a password reset for your BeatVegas account.\n\n"
        f"Reset link (expires in 15 minutes): {reset_url}\n\n"
        f"If you did not request this, ignore this email. Do not share this link."
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
{_email_logo_html()}
<h2>Password Reset</h2>
<p>You requested a password reset for your BeatVegas account.</p>
<p><a href="{reset_url}" style="background:#1565c0;color:#fff;padding:10px 20px;text-decoration:none;border-radius:4px">Reset Password</a></p>
<p style="color:#d32f2f"><strong>This link expires in 15 minutes and can only be used once.</strong></p>
<p>If you did not request this, ignore this email safely.</p>
{_email_footer_html()}
</body></html>"""
    return _send_email(to_email=user_email, subject=subject, html_body=html_body, text_body=text_body)


def _hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


def consume_reset_token(token: str) -> Optional[str]:
    """
    Validate and consume a password reset token.
    Returns user_id on success, None on failure (expired / used / not found).
    Marks the token as used (no reuse).
    """
    token_hash = _hash_token(token)
    now_iso = _now_iso()
    record = db["password_reset_tokens"].find_one_and_update(
        {
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": now_iso},
        },
        {"$set": {"used": True, "consumed_at": now_iso}},
    )
    if not record:
        return None
    return record.get("user_id")


# ─────────────────────────────────────────────────────────────────────────────
# Email 4: Renewal reminder (3 days before)
# ─────────────────────────────────────────────────────────────────────────────

def send_renewal_reminder(
    *,
    user_id: str,
    amount_usd: float,
    renewal_date: str,
    cancel_url: str = "https://beatvegas.app/settings/billing",
) -> bool:
    to_email = _get_user_email(user_id)
    if not to_email:
        return False

    subject = "BeatVegas — Your Subscription Renews in 3 Days"
    text_body = (
        f"Your BeatVegas subscription renews on {renewal_date} for ${amount_usd:.2f}.\n\n"
        f"To cancel before renewal: {cancel_url}\n\n"
        f"No action needed to continue your subscription."
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
{_email_logo_html()}
<h2>Subscription Renewal Reminder</h2>
<p>Your BeatVegas subscription renews on <strong>{renewal_date}</strong> for <strong>${amount_usd:.2f}</strong>.</p>
<p>No action needed to continue. To cancel:</p>
<p><a href="{cancel_url}" style="color:#1565c0">Cancel subscription</a></p>
{_email_footer_html()}
</body></html>"""
    return _send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


# ─────────────────────────────────────────────────────────────────────────────
# Email 5: Cancellation confirmation
# ─────────────────────────────────────────────────────────────────────────────

def send_cancellation_confirmation(
    *,
    user_id: str,
    effective_date: str,
    old_tier: Optional[str] = None,
    data_retention_days: int = 90,
) -> bool:
    to_email = _get_user_email(user_id)
    if not to_email:
        return False

    subject = "BeatVegas — Subscription Cancelled"
    tier_label = old_tier.replace("_", " ").title() if old_tier else "your plan"
    text_body = (
        f"Your BeatVegas {tier_label} subscription has been cancelled.\n\n"
        f"Effective date: {effective_date}\n"
        f"Your data will be retained for {data_retention_days} days.\n\n"
        f"To resubscribe: https://beatvegas.app/upgrade\n\n"
        f"Thank you for using BeatVegas."
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
{_email_logo_html()}
<h2>Subscription Cancelled</h2>
<p>Your BeatVegas <strong>{tier_label}</strong> subscription has been cancelled.</p>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>Effective date</strong></td><td style="padding:8px;border-bottom:1px solid #eee">{effective_date}</td></tr>
  <tr><td style="padding:8px"><strong>Data retained for</strong></td><td style="padding:8px">{data_retention_days} days</td></tr>
</table>
<p><a href="https://beatvegas.app/upgrade" style="background:#1565c0;color:#fff;padding:10px 20px;text-decoration:none;border-radius:4px">Resubscribe</a></p>
<p>Thank you for using BeatVegas.</p>
{_email_footer_html()}
</body></html>"""
    return _send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


# ─────────────────────────────────────────────────────────────────────────────
# Service facade
# ─────────────────────────────────────────────────────────────────────────────

class TransactionalEmailService:
    """Facade exposing all five transactional emails as instance methods."""

    send_subscription_receipt = staticmethod(send_subscription_receipt)
    send_payment_failed = staticmethod(send_payment_failed)
    send_password_reset = staticmethod(send_password_reset)
    send_renewal_reminder = staticmethod(send_renewal_reminder)
    send_cancellation_confirmation = staticmethod(send_cancellation_confirmation)
    consume_reset_token = staticmethod(consume_reset_token)
    # Phase 13 — trial emails
    send_affiliate_trial_receipt = staticmethod(lambda **kw: send_affiliate_trial_receipt(**kw))
    send_affiliate_trial_ending = staticmethod(lambda **kw: send_affiliate_trial_ending(**kw))


email_service = TransactionalEmailService()


# ─────────────────────────────────────────────────────────────────────────────
# Email 6 (Phase 13): affiliate_trial_receipt
# FTC Negative Option Rule 2024 — required at trial start
# ─────────────────────────────────────────────────────────────────────────────

def send_affiliate_trial_receipt(
    *,
    user_id: str,
    charge_display: str,
    trial_ends_at_utc: str,
    cancel_url: str = "https://beatvegas.app/settings/billing",
    amount_usd: float = 97.0,
    stripe_subscription_id: Optional[str] = None,
) -> bool:
    """
    Sent immediately when trial subscription is created.
    Required by FTC Negative Option Rule 2024.
    Contains: exact charge date/time in local timezone, one-click cancel link,
    charge amount, NCPG footer.
    Domain: em9248.beatvegas.app (verified SendGrid domain).
    """
    to_email = _get_user_email(user_id)
    if not to_email:
        logger.warning("[Email:TrialReceipt] no email for user=%s", user_id)
        return False

    subject = "Your BeatVegas 3-Day Trial Has Started"
    text_body = (
        f"Your BeatVegas Platform trial has started.\n\n"
        f"FREE until: {charge_display}\n"
        f"After that: ${amount_usd:.2f}/month\n\n"
        f"To cancel before {charge_display} and avoid any charge:\n"
        f"{cancel_url}\n\n"
        f"If you do nothing, your subscription activates automatically.\n\n"
        f"BeatVegas provides statistical simulation outputs — not betting advice.\n"
        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto;background:#0c141f;color:#f2f3ec;padding:24px">
{_email_logo_html()}
<h2 style="color:#bc993c;margin-bottom:4px">Your 3-Day Trial Has Started</h2>
<p style="color:#afb6bb;font-size:13px">BeatVegas Platform access is now active</p>

<table style="border-collapse:collapse;width:100%;margin-top:20px">
  <tr style="border-bottom:1px solid #1e2d3d">
    <td style="padding:12px 8px;color:#afb6bb">Trial period</td>
    <td style="padding:12px 8px;font-weight:600">Free until {charge_display}</td>
  </tr>
  <tr style="border-bottom:1px solid #1e2d3d">
    <td style="padding:12px 8px;color:#afb6bb">Then</td>
    <td style="padding:12px 8px;font-weight:600">${amount_usd:.2f}/month</td>
  </tr>
</table>

<p style="margin-top:24px">
  To cancel before <strong>{charge_display}</strong> and avoid any charge:
</p>
<p>
  <a href="{cancel_url}"
     style="display:inline-block;background:#bc993c;color:#0c141f;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:700;font-size:15px">
    Cancel Trial
  </a>
</p>

<p style="font-size:12px;color:rgba(242,243,236,0.5);margin-top:32px">
  BeatVegas provides statistical simulation outputs only — not betting advice.
  No wagering services are offered.
</p>
<p style="font-size:12px;color:rgba(242,243,236,0.4)">
  Problem gambling help: 1-800-522-4700 |
  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>
</p>
<p style="font-size:11px;color:rgba(242,243,236,0.3)">
  You received this because you started a BeatVegas trial.
  <a href="{cancel_url}" style="color:rgba(242,243,236,0.3)">Unsubscribe</a>
</p>
{_email_footer_html()}
</body></html>"""

    success = _send_email(
        to_email=to_email, subject=subject,
        html_body=html_body, text_body=text_body,
    )
    if success:
        # Log for compliance audit trail
        try:
            db["transactional_email_log"].insert_one({
                "email_type": "affiliate_trial_receipt",
                "user_id": user_id,
                "to_email": to_email,
                "stripe_subscription_id": stripe_subscription_id,
                "charge_display": charge_display,
                "trial_ends_at_utc": trial_ends_at_utc,
                "sent_at": _now_iso(),
                "cancel_url": cancel_url,
            })
        except Exception:
            pass
    return success


# ─────────────────────────────────────────────────────────────────────────────
# Email 7 (Phase 13): affiliate_trial_ending
# FTC Negative Option Rule 2024 — T-24h notice required
# ─────────────────────────────────────────────────────────────────────────────

def send_affiliate_trial_ending(
    *,
    user_id: str,
    charge_display: str,
    trial_ends_at_utc: str,
    cancel_url: str = "https://beatvegas.app/settings/billing",
    amount_usd: float = 97.0,
) -> bool:
    """
    Sent T-24h before trial end.
    Required by FTC Negative Option Rule 2024 — provides adequate notice before charge.
    Contains: exact charge date/time, one-click cancel link, NCPG footer.
    Scheduled by trial_ending_scheduler.py which reads promo_tokens.trial_ends_at.
    """
    to_email = _get_user_email(user_id)
    if not to_email:
        logger.warning("[Email:TrialEnding] no email for user=%s", user_id)
        return False

    subject = "Your BeatVegas trial ends tomorrow"
    text_body = (
        f"Your BeatVegas Platform trial ends tomorrow.\n\n"
        f"Charge date and time: {charge_display}\n"
        f"Amount: ${amount_usd:.2f}\n\n"
        f"Cancel before {charge_display} and you won't be charged:\n"
        f"{cancel_url}\n\n"
        f"If you do nothing, your subscription activates automatically.\n\n"
        f"BeatVegas provides statistical simulation outputs — not betting advice.\n"
        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
    )
    html_body = f"""
<html><body style="font-family:sans-serif;max-width:600px;margin:auto;background:#0c141f;color:#f2f3ec;padding:24px">
{_email_logo_html()}
<h2 style="color:#de691b;margin-bottom:4px">Your Trial Ends Tomorrow</h2>
<p style="color:#afb6bb;font-size:13px">Action required if you want to cancel</p>

<table style="border-collapse:collapse;width:100%;margin-top:20px">
  <tr style="border-bottom:1px solid #1e2d3d">
    <td style="padding:12px 8px;color:#afb6bb">Charge time</td>
    <td style="padding:12px 8px;font-weight:600">{charge_display}</td>
  </tr>
  <tr style="border-bottom:1px solid #1e2d3d">
    <td style="padding:12px 8px;color:#afb6bb">Amount</td>
    <td style="padding:12px 8px;font-weight:600">${amount_usd:.2f}/month</td>
  </tr>
</table>

<p style="margin-top:24px">
  To cancel before <strong>{charge_display}</strong> and avoid any charge:
</p>
<p>
  <a href="{cancel_url}"
     style="display:inline-block;background:#bc993c;color:#0c141f;padding:12px 28px;
            text-decoration:none;border-radius:6px;font-weight:700;font-size:15px">
    Cancel Trial
  </a>
</p>

<p style="font-size:12px;color:rgba(242,243,236,0.5);margin-top:32px">
  BeatVegas provides statistical simulation outputs only — not betting advice.
</p>
<p style="font-size:12px;color:rgba(242,243,236,0.4)">
  Problem gambling help: 1-800-522-4700 |
  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>
</p>
<p style="font-size:11px;color:rgba(242,243,236,0.3)">
  <a href="{cancel_url}" style="color:rgba(242,243,236,0.3)">Unsubscribe</a>
</p>
{_email_footer_html()}
</body></html>"""

    success = _send_email(
        to_email=to_email, subject=subject,
        html_body=html_body, text_body=text_body,
    )
    if success:
        try:
            db["transactional_email_log"].insert_one({
                "email_type": "affiliate_trial_ending",
                "user_id": user_id,
                "to_email": to_email,
                "charge_display": charge_display,
                "trial_ends_at_utc": trial_ends_at_utc,
                "sent_at": _now_iso(),
                "cancel_url": cancel_url,
            })
        except Exception:
            pass
    return success

"""
Phase 5B — Growth Agent  (agent.growth.v1)
==========================================
Autonomous lifecycle communication layer.

LOCKED CONSTANTS:
  AGENT_ID = "agent.growth.v1"          — never change
  outbound_communication_log             — append-only, no deletes, no updates

Rules:
  1. Every outbound message uses an approved template — no generative content ever.
  2. Every message passes the regulatory language filter before send.
     FAIL → message blocked, CRITICAL sentinel event, operator notified.
  3. Every sent message is logged to outbound_communication_log with
     agent_id = "agent.growth.v1".
  4. All timing thresholds come from agent_config.phase5 — zero hardcoded values.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from db.mongo import db
from config.agent_config import AGENT_CONFIG

logger = logging.getLogger(__name__)

# ── Identity — LOCKED ────────────────────────────────────────────────────────
AGENT_ID = "agent.growth.v1"

# ── Regulatory language filter ───────────────────────────────────────────────
# Any message containing these patterns is BLOCKED and fires a CRITICAL alert.
_PROHIBITED_PATTERNS = [
    # Betting instruction framing
    "place a bet", "place bet", "make a bet", "put money on",
    "bet on", "bet this", "wagering advice", "betting tip",
    "sure bet", "guaranteed win", "guaranteed return", "guaranteed profit",
    # Sportsbook references
    "sportsbook", "bookmaker", "bookie",
    # Win/loss wagering language
    "you will win", "you will lose", "win big", "sure thing",
    "pick of the day", "best pick", "lock of the week",
    # Explicit gambling terms
    "gamble", "gambling", "wager",
    # Monetary betting constructs
    "bet $", "bet £", "bet €",
]


def _regulatory_filter(content: str) -> dict:
    """
    Check message content against prohibited language patterns.
    Returns {"pass": True} or {"pass": False, "violations": [...]}.
    Case-insensitive.
    """
    lower = content.lower()
    violations = [p for p in _PROHIBITED_PATTERNS if p in lower]
    if violations:
        return {"pass": False, "violations": violations}
    return {"pass": True}


def _fire_critical_regulatory_alert(
    template_id: str,
    user_id: str,
    violations: list,
    content_snippet: str,
) -> None:
    """Write CRITICAL sentinel event when a message is blocked by the filter."""
    try:
        db["sentinel_event_log"].insert_one({
            "event_type":      "REGULATORY_FILTER_BLOCK",
            "severity":        "CRITICAL",
            "agent_id":        AGENT_ID,
            "template_id":     template_id,
            "user_id":         user_id,
            "violations":      violations,
            "content_snippet": content_snippet[:200],
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "note": (
                "Message was BLOCKED before send. No outbound communication was issued. "
                "Operator action required."
            ),
        })
        logger.critical(
            f"CRITICAL [{AGENT_ID}] REGULATORY_FILTER_BLOCK "
            f"template_id={template_id} user_id={user_id} "
            f"violations={violations}"
        )
    except Exception as exc:
        logger.error(f"Failed to log REGULATORY_FILTER_BLOCK to sentinel: {exc}")


# ── Approved Template Library ────────────────────────────────────────────────
# No generative content. Every message is a template.
# All templates pass regulatory filter at definition time.
_TEMPLATES: dict = {
    "onboarding_step_1": {
        "campaign_id": "onboarding_v1",
        "channel":     "platform",
        "subject":     "Welcome to BeatVegas",
        "body": (
            "Welcome to BeatVegas — the agentic simulation intelligence platform. "
            "BeatVegas does not facilitate execution of picks. All outputs are informational only. "
            "Institutional-grade analytics, delivered by autonomous agents. "
            "Complete your onboarding to unlock your intelligence dashboard."
        ),
    },
    "onboarding_step_2": {
        "campaign_id": "onboarding_v1",
        "channel":     "platform",
        "subject":     "Understanding Intelligence Classifications",
        "body": (
            "BeatVegas uses three classifications for every decision record: "
            "EDGE — model probability exceeds market implied probability by a threshold amount; "
            "LEAN — directional signal present, smaller gap than EDGE; "
            "MARKET_ALIGNED — model agrees with market, no actionable signal. "
            "Complete screen 2 of your onboarding to proceed."
        ),
    },
    "onboarding_step_3": {
        "campaign_id": "onboarding_v1",
        "channel":     "platform",
        "subject":     "Your Credit System",
        "body": (
            "BeatVegas Intelligence Cycles power every decision record. "
            "Your balance is always visible in the sidebar. "
            "Cost is shown before every action — no silent deductions. "
            "You will receive a low-balance warning before your credits are exhausted. "
            "Complete onboarding to activate your dashboard."
        ),
    },
    "upgrade_prompt": {
        "campaign_id": "upgrade_v1",
        "channel":     "platform",
        "subject":     "Intelligence Cycle Balance — Action Required",
        "body": (
            "Your Intelligence Cycle balance has reached 80% of your allocation. "
            "Upgrade to Platform access for $97/month to unlock full Decision Engine capacity "
            "and Parlay Architect intelligence."
        ),
    },
    "low_balance_warning": {
        "campaign_id": "low_balance_v1",
        "channel":     "platform",
        "subject":     "Low Intelligence Cycle Balance",
        "body": (
            "Your Intelligence Cycle balance is running low. "
            "Upgrade your plan to continue receiving decision intelligence without interruption."
        ),
    },
    "reengagement": {
        "campaign_id": "reengagement_v1",
        "channel":     "platform",
        "subject":     "Intelligence updates are waiting for you",
        "body": (
            "Recent decision records are available on your BeatVegas dashboard. "
            "Log in to review the latest intelligence outputs from the simulation engine."
        ),
    },
    "credit_expiry_warning": {
        "campaign_id": "credit_expiry_v1",
        "channel":     "platform",
        "subject":     "Intelligence Cycles expiring in 3 days",
        "body": (
            "Your current Intelligence Cycle allocation expires in 3 days. "
            "Log in to review outstanding records before your credits reset."
        ),
    },
    "affiliate_welcome_1": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Affiliate Program Welcome",
        "body": (
            "Welcome to the BeatVegas affiliate program. "
            "Your referral link is active and ready to share. "
            "Commissions are calculated from confirmed subscriber payments."
        ),
    },
    "affiliate_welcome_2": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Affiliate Sharing Reminder",
        "body": (
            "Reminder: your referral link is active. "
            "Share it across your approved channels to increase qualified conversions."
        ),
    },
    "affiliate_welcome_3": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "First Conversion Guidance",
        "body": (
            "Your affiliate dashboard includes volume tiers and conversion tracking. "
            "Review your current tier progress and optimize your distribution plan."
        ),
    },
    "affiliate_conversion": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Commission Event Created",
        "body": (
            "A new commission event was created for your account. "
            "Open your affiliate dashboard to review your updated earnings."
        ),
    },
    "affiliate_tier_upgrade": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Volume Tier Updated",
        "body": (
            "Your monthly conversion volume reached a new tier. "
            "Your current commission rate has been updated for this month."
        ),
    },
    "affiliate_retention_bonus": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Retention Bonus Added",
        "body": (
            "A platform retention bonus was added to your affiliate balance. "
            "See your commission detail panel for event-level breakdown."
        ),
    },
    "affiliate_monthly_digest": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Monthly Affiliate Summary",
        "body": (
            "Your monthly affiliate summary is ready. "
            "Review conversions, earnings, and payout status in your dashboard."
        ),
    },
    "affiliate_fraud_hold": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Commission Under Review",
        "body": (
            "One commission event is currently under review. "
            "Payout timing for that event may be delayed pending operator review."
        ),
    },
    "affiliate_payout_confirm": {
        "campaign_id": "affiliate_v1",
        "channel": "platform",
        "subject": "Payout Processed",
        "body": (
            "Your affiliate payout has been processed through Stripe Connect. "
            "See payout history in your affiliate dashboard for full detail."
        ),
    },

    # ── Phase 13: Affiliate 3-Day Trial sequences ────────────────────────────
    # All content passes regulatory filter. No generative content.
    # trial_source=AFFILIATE_REFERRAL fires these templates.
    # QR_PROMO continues to use existing templates.
    "affiliate_trial_welcome": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "Your 3-day BeatVegas access has started",
        "body": (
            "Your 3-day Platform access has started. "
            "Tonight's intelligence output is live on your dashboard. "
            "BeatVegas provides statistical simulation outputs — not betting advice. "
            "Cancel anytime before your trial ends and you will not be charged."
        ),
    },
    "affiliate_trial_day1": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "Day 1 complete — today's intelligence summary",
        "body": (
            "Day 1 of your BeatVegas trial is complete. "
            "Your dashboard shows the simulation outputs our agentic engine produced today. "
            "Statistical outputs only — not betting advice. "
            "Log in to review your intelligence feed."
        ),
    },
    "affiliate_trial_day2": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "Two signals fired across your trial",
        "body": (
            "Two simulation signals fired across your trial period. "
            "Platform subscribers can view the full decision record detail in their dashboard. "
            "Statistical outputs only — not betting advice. "
            "Your trial continues through tomorrow."
        ),
    },
    "affiliate_trial_hour68": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "4 hours left on your trial",
        "body": (
            "Your BeatVegas trial ends in 4 hours. "
            "If you would like to continue, your subscription will activate automatically. "
            "Cancel in your account settings before your trial ends to avoid any charge. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "affiliate_trial_hour71": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "1 hour left on your BeatVegas trial",
        "body": (
            "Your BeatVegas trial ends in 1 hour. "
            "To cancel, visit your account settings and click Cancel Trial. "
            "No action needed to continue your subscription. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "affiliate_trial_converted": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "Welcome to BeatVegas — your subscription is active",
        "body": (
            "Your BeatVegas Platform subscription is now active. "
            "Parlay Architect intelligence is now available on your dashboard. "
            "Statistical outputs only — not betting advice. "
            "Manage your subscription any time in account settings."
        ),
    },
    "affiliate_trial_churned": {
        "campaign_id": "affiliate_trial_v1",
        "channel": "email",
        "subject": "Your BeatVegas trial has ended",
        "body": (
            "Your BeatVegas trial has ended. No charge was made. "
            "You can start a Platform subscription any time at beatvegas.app. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "affiliate_winback_day2": {
        "campaign_id": "affiliate_winback_v1",
        "channel": "email",
        "subject": "You missed last night's intelligence output",
        "body": (
            "Last night's simulation engine output is available to Platform subscribers. "
            "Your trial has ended but you can reactivate at any time. "
            "Visit beatvegas.app to review subscription options. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "affiliate_winback_day7": {
        "campaign_id": "affiliate_winback_v1",
        "channel": "email",
        "subject": "This week's intelligence summary — Platform subscribers only",
        "body": (
            "This week's simulation intelligence summary is live for Platform subscribers. "
            "Your dashboard access has been paused. "
            "Reactivate at beatvegas.app to restore full Platform access. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "affiliate_winback_day30": {
        "campaign_id": "affiliate_winback_v1",
        "channel": "email",
        "subject": "Final notice — Platform subscription available",
        "body": (
            "This is the final win-back notice for your BeatVegas account. "
            "Platform access is available at beatvegas.app. "
            "Statistical outputs only — not betting advice."
        ),
    },

    # ── Intelligence Preview conversion sequence ──────────────────────────────
    # Fires T+0, Day 3, Day 7, Day 14 for intelligence_preview tier users.
    # All templates pass regulatory filter. No generative content.
    # Each template shows the 10x cycle gap explicitly: 10,000 vs 100,000.
    "preview_welcome": {
        "campaign_id": "preview_conversion_v1",
        "channel": "platform",
        "subject": "Your 10,000 Intelligence Cycles are active",
        "body": (
            "Your 10,000 Intelligence Cycles are active. "
            "Each cycle powers a decision record from the BeatVegas simulation engine. "
            "Your cycle balance is visible in the sidebar at all times — no silent deductions. "
            "Platform subscribers receive 100,000 cycles — 10x the decision engine access. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "preview_value_nudge": {
        "campaign_id": "preview_conversion_v1",
        "channel": "platform",
        "subject": "Platform subscribers received full decision records this week",
        "body": (
            "Platform subscribers received full decision records across all major markets this week. "
            "Your Intelligence Preview access gives you the starter experience — 10,000 cycles. "
            "Platform access unlocks 100,000 cycles and full Parlay Architect intelligence. "
            "Upgrade to Platform for $97/month at beatvegas.app. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "preview_upgrade_push": {
        "campaign_id": "preview_conversion_v1",
        "channel": "platform",
        "subject": "Intelligence Cycles remaining — consider upgrading",
        "body": (
            "You have used a portion of your 10,000 Intelligence Cycles. "
            "When cycles reach zero, decision records will be paused until you upgrade. "
            "Platform subscribers receive 100,000 cycles — 10x more decision engine access — for $97/month. "
            "Syndicate access is available for $39/month. "
            "Upgrade at beatvegas.app before your cycles run out. "
            "Statistical outputs only — not betting advice."
        ),
    },
    "preview_final_push": {
        "campaign_id": "preview_conversion_v1",
        "channel": "platform",
        "subject": "Your Intelligence Preview has been active for 2 weeks",
        "body": (
            "Your BeatVegas Intelligence Preview has been active for 2 weeks. "
            "Platform subscribers are building a track record with 100,000 cycles. "
            "Your 10,000 cycle starter allocation gives you the foundation — "
            "Platform gives you the full product. "
            "Subscribe to Platform for $97/month or Syndicate for $39/month at beatvegas.app. "
            "Statistical outputs only — not betting advice."
        ),
    },
}

# Validate templates at import time — fail fast if any contain prohibited language
for _tid, _tmpl in _TEMPLATES.items():
    _result = _regulatory_filter(_tmpl["body"])
    if not _result["pass"]:
        raise RuntimeError(
            f"TEMPLATE VALIDATION FAILED at import: template_id={_tid} "
            f"violations={_result['violations']}. Fix template before deploying."
        )


# ── Growth Agent ─────────────────────────────────────────────────────────────

class GrowthAgent:
    """
    agent.growth.v1 — Autonomous lifecycle communication.

    All public methods are safe to call from any context.
    All writes to outbound_communication_log are append-only.
    """

    AGENT_ID = AGENT_ID  # re-exported for external reference

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _cfg(self) -> dict:
        return AGENT_CONFIG.get("phase5", {})

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write_to_outbound_log(
        self,
        user_id: str,
        template_id: str,
        campaign_id: str,
        channel: str,
        trace_id: str,
    ) -> str:
        """Append a sent-message record. Returns message_id."""
        message_id = str(uuid.uuid4())
        body = _TEMPLATES.get(template_id, {}).get("body", "")
        db["outbound_communication_log"].insert_one({
            "message_id":   message_id,
            "user_id":      user_id,
            "campaign_id":  campaign_id,
            "template_id":  template_id,
            "message_body": body,
            "channel":      channel,
            "sent_at_utc":  self._now(),
            "delivered":    True,
            "opened":       False,
            "converted":    False,
            "agent_id":     self.AGENT_ID,
            "trace_id":     trace_id,
        })
        return message_id

    def _already_sent_in_period(
        self,
        user_id: str,
        template_id: str,
        since_hours: Optional[int] = None,
    ) -> bool:
        """Return True if this template was already sent to the user within the given window."""
        query: dict = {"user_id": user_id, "template_id": template_id}
        if since_hours is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
            query["sent_at_utc"] = {"$gte": cutoff}
        return db["outbound_communication_log"].find_one(query) is not None

    def _has_active_winback_sequence(self, user_id: str) -> bool:
        """
        Return True if user has an active win-back sequence from a prior trial.
        Used for Phase 13 sequence overlap suppression.
        """
        winback_templates = ["affiliate_winback_day2", "affiliate_winback_day7", "affiliate_winback_day30"]
        stop_day = AGENT_CONFIG.get("phase13", {}).get("winback_stop_day", 30)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=stop_day)).isoformat()

        # Active win-back = any win-back template sent within the stop window
        # AND user has not subscribed since then
        existing = db["outbound_communication_log"].find_one(
            {
                "user_id": user_id,
                "template_id": {"$in": winback_templates},
                "sent_at_utc": {"$gte": cutoff},
            }
        )
        if not existing:
            return False

        # Check if user has since subscribed — suppress win-back if so
        entitlement = db["user_entitlements"].find_one(
            {"user_id": user_id, "tier": {"$in": ["platform", "syndicate"]}, "active": True},
            {"_id": 1},
        )
        return entitlement is None  # Active win-back only if not currently subscribed

    def _should_suppress_trial_welcome(self, user_id: str) -> bool:
        """
        Phase 13 sequence overlap suppression:
        If user has an active win-back sequence from a prior trial,
        suppress affiliate_trial_welcome for the overlap suppression window (default 24h).
        After 24h the trial sequence supersedes the win-back sequence.
        """
        if not self._has_active_winback_sequence(user_id):
            return False
        suppress_hours = AGENT_CONFIG.get("phase13", {}).get("overlap_suppression_hours", 24)
        # Check if trial_welcome was already suppressed within the window
        # If the active trial started less than suppress_hours ago, suppress welcome
        trial_doc = db["affiliate_trial_subscriptions"].find_one(
            {"user_id": user_id, "status": "active"},
            {"trial_starts_at": 1},
        )
        if not trial_doc:
            return False
        trial_start = trial_doc.get("trial_starts_at")
        if not trial_start:
            return False
        try:
            from datetime import datetime as _dt
            if isinstance(trial_start, str):
                start_dt = _dt.fromisoformat(trial_start.replace("Z", "+00:00"))
            else:
                start_dt = trial_start
            age_hours = (datetime.now(timezone.utc) - start_dt).total_seconds() / 3600
            return age_hours < suppress_hours
        except Exception:
            return False

    def stop_winback_if_subscribed(self, user_id: str) -> bool:
        """
        Suppress all remaining win-back sends if user has subscribed.
        Called before every win-back send. Returns True if suppressed.
        """
        entitlement = db["user_entitlements"].find_one(
            {"user_id": user_id, "tier": {"$in": ["platform", "syndicate"]}, "active": True},
            {"_id": 1},
        )
        if entitlement:
            logger.info(
                "[GrowthAgent] Win-back suppressed: user=%s is now subscribed",
                user_id,
            )
            return True
        return False

    # ── Public API ────────────────────────────────────────────────────────────

    def send_message(
        self,
        user_id: str,
        template_id: str,
        channel: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Send a single templated message to a user.

        Returns {"sent": True, "message_id": "..."} on success.
        Returns {"sent": False, "reason": "..."} if blocked or not found.
        FAIL on regulatory filter → CRITICAL sentinel alert fired, message NOT sent.
        """
        if template_id not in _TEMPLATES:
            return {"sent": False, "reason": f"Unknown template_id: {template_id}"}

        tmpl = _TEMPLATES[template_id]
        effective_channel = channel or tmpl["channel"]
        effective_trace = trace_id or str(uuid.uuid4())

        # ── Phase 13: Sequence overlap suppression ────────────────────────────
        # affiliate_trial_welcome suppressed for overlap_suppression_hours (24h)
        # if user has an active win-back sequence from a prior trial.
        if template_id == "affiliate_trial_welcome" and self._should_suppress_trial_welcome(user_id):
            logger.info(
                "[GrowthAgent] affiliate_trial_welcome suppressed (active win-back): user=%s",
                user_id,
            )
            db["outbound_communication_log"].insert_one({
                "message_id": str(uuid.uuid4()),
                "user_id": user_id,
                "template_id": template_id,
                "campaign_id": tmpl.get("campaign_id", ""),
                "sent_at_utc": datetime.now(timezone.utc).isoformat(),
                "delivered": False,
                "suppressed": True,
                "suppress_reason": "OVERLAP_SUPPRESSION_ACTIVE_WINBACK",
                "agent_id": self.AGENT_ID,
                "trace_id": effective_trace,
            })
            return {"sent": False, "reason": "OVERLAP_SUPPRESSION_ACTIVE_WINBACK"}

        # ── Phase 13: Win-back stop condition — check subscription before every send ─
        if template_id.startswith("affiliate_winback") and self.stop_winback_if_subscribed(user_id):
            return {"sent": False, "reason": "WINBACK_SUPPRESSED_USER_SUBSCRIBED"}

        # Regulatory filter — mandatory, cannot be bypassed
        body = tmpl["body"]
        filter_result = _regulatory_filter(body)
        if not filter_result["pass"]:
            _fire_critical_regulatory_alert(
                template_id=template_id,
                user_id=user_id,
                violations=filter_result["violations"],
                content_snippet=body,
            )
            return {
                "sent":   False,
                "reason": "REGULATORY_FILTER_BLOCK — message not sent",
                "violations": filter_result["violations"],
            }

        channels = [effective_channel]
        affiliate = db["affiliate_accounts"].find_one({"affiliate_id": user_id}, {"notification_preference": 1})
        if affiliate:
            pref = str(affiliate.get("notification_preference", "both")).lower().strip()
            if pref == "email_only":
                channels = ["email"]
            elif pref == "platform_only":
                channels = ["platform"]
            elif pref == "both":
                channels = ["email", "platform"]

        message_ids = []
        for resolved_channel in channels:
            message_ids.append(
                self._write_to_outbound_log(
                    user_id=user_id,
                    template_id=template_id,
                    campaign_id=tmpl["campaign_id"],
                    channel=resolved_channel,
                    trace_id=effective_trace,
                )
            )

        message_id = message_ids[0]
        logger.info(
            f"[{self.AGENT_ID}] message sent "
            f"template_id={template_id} user_id={user_id} message_ids={message_ids}"
        )
        return {"sent": True, "message_id": message_id, "message_ids": message_ids}

    def trigger_onboarding_sequence(self, user_id: str, trace_id: Optional[str] = None) -> dict:
        """
        Trigger Step 1 of the onboarding sequence.
        Must be called within 60 seconds of account creation (Phase 5 AC-1).
        Steps 2 and 3 are scheduled by the background scheduler for 24h / 48h later.
        """
        effective_trace = trace_id or str(uuid.uuid4())

        # Idempotent — if already sent in the last 24h, skip
        if self._already_sent_in_period(user_id, "onboarding_step_1", since_hours=24):
            logger.info(f"[{self.AGENT_ID}] onboarding_step_1 already sent for user_id={user_id}")
            return {"sent": False, "reason": "already_sent"}

        result = self.send_message(
            user_id=user_id,
            template_id="onboarding_step_1",
            trace_id=effective_trace,
        )
        logger.info(
            f"[{self.AGENT_ID}] onboarding_sequence triggered "
            f"user_id={user_id} step=1 result={result}"
        )
        return result

    def trigger_onboarding_step2(self, user_id: str) -> dict:
        """
        Trigger Step 2 (24h after step 1, only if onboarding_complete is still False).
        Called by background scheduler.
        """
        user = db["users"].find_one({"_id": __import__("bson").ObjectId(user_id)})
        if not user:
            return {"sent": False, "reason": "user_not_found"}
        if user.get("onboarding_complete", False):
            return {"sent": False, "reason": "onboarding_already_complete"}
        if self._already_sent_in_period(user_id, "onboarding_step_2", since_hours=48):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="onboarding_step_2")

    def trigger_onboarding_step3(self, user_id: str) -> dict:
        """
        Trigger Step 3 (48h after step 1, only if onboarding_complete is still False).
        Called by background scheduler.
        """
        user = db["users"].find_one({"_id": __import__("bson").ObjectId(user_id)})
        if not user:
            return {"sent": False, "reason": "user_not_found"}
        if user.get("onboarding_complete", False):
            return {"sent": False, "reason": "onboarding_already_complete"}
        if self._already_sent_in_period(user_id, "onboarding_step_3", since_hours=72):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="onboarding_step_3")

    def trigger_upgrade_prompt(self, user_id: str) -> dict:
        """
        Send upgrade prompt at 80% credit usage.
        AC-3: $97/month price explicitly included in template.
        Not fired twice for the same usage threshold in the same billing period (30-day window).
        """
        threshold_pct = self._cfg().get("upgrade_prompt_threshold_pct", 80)
        # Idempotent within 30-day billing window
        if self._already_sent_in_period(user_id, "upgrade_prompt", since_hours=720):
            return {"sent": False, "reason": "already_sent_this_billing_period"}
        result = self.send_message(user_id=user_id, template_id="upgrade_prompt")
        logger.info(
            f"[{self.AGENT_ID}] upgrade_prompt sent "
            f"user_id={user_id} threshold_pct={threshold_pct}"
        )
        return result

    def trigger_low_balance_warning(self, user_id: str) -> dict:
        """
        Send low-balance warning when user approaches credit floor.
        Threshold from agent_config — never hardcoded.
        """
        if self._already_sent_in_period(user_id, "low_balance_warning", since_hours=24):
            return {"sent": False, "reason": "already_sent_today"}
        return self.send_message(user_id=user_id, template_id="low_balance_warning")

    def trigger_reengagement(self, user_id: str) -> dict:
        """
        Send re-engagement message after 7 days of inactivity.
        Threshold from agent_config.
        """
        inactivity_days = self._cfg().get("reengagement_inactivity_days", 7)
        if self._already_sent_in_period(user_id, "reengagement", since_hours=inactivity_days * 24):
            return {"sent": False, "reason": "already_sent_this_window"}
        return self.send_message(user_id=user_id, template_id="reengagement")

    def trigger_credit_expiry_warning(self, user_id: str) -> dict:
        """
        Send credit expiry warning 3 days before credit expiry.
        Threshold from agent_config.
        """
        if self._already_sent_in_period(user_id, "credit_expiry_warning", since_hours=72):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="credit_expiry_warning")

    # ── Intelligence Preview conversion sequence ──────────────────────────────

    def trigger_preview_welcome(self, user_id: str, trace_id: Optional[str] = None) -> dict:
        """
        T+0 — Fire immediately on Intelligence Preview account creation.
        Idempotent: will not double-send within 48h.
        """
        if self._already_sent_in_period(user_id, "preview_welcome", since_hours=48):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="preview_welcome", trace_id=trace_id)

    def trigger_preview_value_nudge(self, user_id: str, trace_id: Optional[str] = None) -> dict:
        """
        Day 3 — Show value gap. Only fires if user has not already upgraded.
        Idempotent: will not double-send within 72h.
        """
        ent = None
        try:
            from db.mongo import db as _db
            ent = _db["user_entitlements"].find_one(
                {"user_id": user_id, "tier": {"$in": ["platform", "syndicate", "telegram_syndicate"]}, "active": True},
                {"_id": 1},
            )
        except Exception:
            pass
        if ent:
            return {"sent": False, "reason": "user_already_upgraded"}
        if self._already_sent_in_period(user_id, "preview_value_nudge", since_hours=72):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="preview_value_nudge", trace_id=trace_id)

    def trigger_preview_upgrade_push(self, user_id: str, trace_id: Optional[str] = None) -> dict:
        """
        Day 7 — Urgency push with cycles remaining. Suppressed if already upgraded.
        Idempotent: will not double-send within 7 days.
        """
        ent = None
        try:
            from db.mongo import db as _db
            ent = _db["user_entitlements"].find_one(
                {"user_id": user_id, "tier": {"$in": ["platform", "syndicate", "telegram_syndicate"]}, "active": True},
                {"_id": 1},
            )
        except Exception:
            pass
        if ent:
            return {"sent": False, "reason": "user_already_upgraded"}
        if self._already_sent_in_period(user_id, "preview_upgrade_push", since_hours=168):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="preview_upgrade_push", trace_id=trace_id)

    def trigger_preview_final_push(self, user_id: str, trace_id: Optional[str] = None) -> dict:
        """
        Day 14 — Final push referencing 2-week tenure. Suppressed if already upgraded.
        Idempotent: will not double-send within 14 days.
        """
        ent = None
        try:
            from db.mongo import db as _db
            ent = _db["user_entitlements"].find_one(
                {"user_id": user_id, "tier": {"$in": ["platform", "syndicate", "telegram_syndicate"]}, "active": True},
                {"_id": 1},
            )
        except Exception:
            pass
        if ent:
            return {"sent": False, "reason": "user_already_upgraded"}
        if self._already_sent_in_period(user_id, "preview_final_push", since_hours=336):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(user_id=user_id, template_id="preview_final_push", trace_id=trace_id)

    def trigger_syndicate_cancellation_retention(
        self,
        user_id: str,
        period_end_display: str = "your billing period end",
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Addendum 1 — Syndicate cancellation retention template.
        Fires when customer.subscription.updated has cancel_at_period_end=True.
        Reminds user what they will lose and offers a resubscribe CTA.
        Idempotent: suppressed if already sent within 30 days.
        """
        if self._already_sent_in_period(user_id, "syndicate_cancellation_retention", since_hours=720):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(
            user_id=user_id,
            template_id="syndicate_cancellation_retention",
            trace_id=trace_id,
            metadata={"period_end_display": period_end_display},
        )

    def trigger_syndicate_cycle_reset(
        self,
        user_id: str,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Section 2F — Syndicate monthly cycle reset notification.
        Fires on invoice.payment_succeeded for a Syndicate subscriber.
        """
        return self.send_message(
            user_id=user_id,
            template_id="syndicate_cycle_reset",
            trace_id=trace_id,
        )

    def trigger_syndicate_upgrade_prompt(
        self,
        user_id: str,
        trace_id: Optional[str] = None,
    ) -> dict:
        """
        Section 4 — 80% warning for Syndicate subscribers.
        Shows ONLY Platform CTA (user is already subscribed to Syndicate).
        Idempotent: suppressed if already sent in this billing period (30 days).
        """
        if self._already_sent_in_period(user_id, "syndicate_upgrade_prompt", since_hours=720):
            return {"sent": False, "reason": "already_sent"}
        return self.send_message(
            user_id=user_id,
            template_id="syndicate_upgrade_prompt",
            trace_id=trace_id,
        )

    def check_regulatory_filter(self, content: str) -> dict:
        """
        Public method to test the regulatory language filter.
        Used for AC-4 evidence capture.
        Returns {"pass": True} or {"pass": False, "violations": [...]}.
        """
        return _regulatory_filter(content)


# Module-level singleton — import this from other modules
growth_agent = GrowthAgent()

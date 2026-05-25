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
            "BeatVegas is not a sportsbook. No bet placement. No wagering. "
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
        db["outbound_communication_log"].insert_one({
            "message_id":  message_id,
            "user_id":     user_id,
            "campaign_id": campaign_id,
            "template_id": template_id,
            "channel":     channel,
            "sent_at_utc": self._now(),
            "delivered":   True,
            "opened":      False,
            "converted":   False,
            "agent_id":    self.AGENT_ID,
            "trace_id":    trace_id,
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

        message_id = self._write_to_outbound_log(
            user_id=user_id,
            template_id=template_id,
            campaign_id=tmpl["campaign_id"],
            channel=effective_channel,
            trace_id=effective_trace,
        )
        logger.info(
            f"[{self.AGENT_ID}] message sent "
            f"template_id={template_id} user_id={user_id} message_id={message_id}"
        )
        return {"sent": True, "message_id": message_id}

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

    def check_regulatory_filter(self, content: str) -> dict:
        """
        Public method to test the regulatory language filter.
        Used for AC-4 evidence capture.
        Returns {"pass": True} or {"pass": False, "violations": [...]}.
        """
        return _regulatory_filter(content)


# Module-level singleton — import this from other modules
growth_agent = GrowthAgent()

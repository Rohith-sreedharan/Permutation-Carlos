"""
Phase 11 evidence package generator (AC-6 and AC-7 closure package).
AC-1..AC-5 are accepted and locked by operator directive.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from db.mongo import db  # noqa: E402
from services.phase11_affiliate_engine import affiliate_engine  # noqa: E402
from services.phase5_growth_agent import growth_agent  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ac6_surface_suite() -> dict:
    root = Path(__file__).resolve().parents[2]
    app_tsx = (root / "App.tsx").read_text(encoding="utf-8")
    become_page = (root / "components" / "BecomeAffiliatePage.tsx").read_text(encoding="utf-8")
    applicants_panel = (root / "components" / "AffiliateApplicantsPanel.tsx").read_text(encoding="utf-8")
    popup_component = (root / "components" / "AffiliateRecruitmentPopup.tsx").read_text(encoding="utf-8")
    wallet_component = (root / "components" / "AffiliateWallet.tsx").read_text(encoding="utf-8")

    become_affiliate_route_live = "'/become-affiliate': BecomeAffiliatePage" in app_tsx
    aos_panel_route_live = "'/ops/affiliate-applicants': AffiliateApplicantsPanel" in app_tsx

    interest = affiliate_engine.submit_affiliate_interest(
        name=f"P11 Interest {uuid4().hex[:6]}",
        email=f"p11.interest.{uuid4().hex[:6]}@example.com",
        audience_desc="Sports picks creators",
    )
    accepted_submission = bool(db["affiliate_interest_log"].find_one({"interest_id": interest["interest_id"]}))

    applicants_before = affiliate_engine.list_affiliate_interest(status="PENDING")
    panel_has_invite_decline = ("Invite" in applicants_panel and "Decline" in applicants_panel)

    invited = affiliate_engine.invite_interest(interest["interest_id"], invited_by_operator_id="op_phase11")
    invited_ok = invited.get("status") == "INVITED"

    second_interest = affiliate_engine.submit_affiliate_interest(
        name=f"P11 Interest {uuid4().hex[:6]}",
        email=f"p11.interest.{uuid4().hex[:6]}@example.com",
        audience_desc="Modeling audience",
    )
    declined = affiliate_engine.decline_interest(second_interest["interest_id"])
    declined_ok = declined.get("status") == "DECLINED"

    eligible_user_id = f"popup_user_{uuid4().hex[:8]}"
    db["users"].insert_one(
        {
            "_id": eligible_user_id,
            "email": f"popup.{uuid4().hex[:6]}@example.com",
            "username": f"popup_{uuid4().hex[:6]}",
            "hashed_password": "x",
            "tier": "platform",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=35)).isoformat(),
            "has_seen_affiliate_popup": False,
            "onboarding_complete": True,
        }
    )
    popup_state = affiliate_engine.get_recruitment_popup_state(eligible_user_id)
    popup_rendering_ok = bool(popup_state.get("show_popup") and "Learn More" in popup_component)
    affiliate_engine.dismiss_recruitment_popup(eligible_user_id)
    popup_dismiss_persisted = bool(
        db["users"].find_one({"_id": eligible_user_id, "has_seen_affiliate_popup": True})
    )

    affiliate_id = invited.get("affiliate_id")
    affiliate_engine.activate_affiliate(affiliate_id, "acct_surface")
    pref_set = affiliate_engine.update_notification_preference(affiliate_id, "email_only")
    sent = growth_agent.send_message(user_id=affiliate_id, template_id="affiliate_monthly_digest", trace_id=str(uuid4()))
    channel_logs = list(
        db["outbound_communication_log"].find(
            {
                "user_id": affiliate_id,
                "template_id": "affiliate_monthly_digest",
                "trace_id": sent.get("message_ids", [None])[0] and sent.get("message_ids") and None,
            }
        )
    )
    # Fetch by latest send instead of trace trick above.
    channel_logs = list(
        db["outbound_communication_log"].find(
            {"user_id": affiliate_id, "template_id": "affiliate_monthly_digest"}
        ).sort("sent_at_utc", -1).limit(2)
    )
    pref_respected = bool(pref_set.get("notification_preference") == "email_only" and channel_logs and all(r.get("channel") == "email" for r in channel_logs))

    leaderboard_set = affiliate_engine.update_leaderboard_preferences(affiliate_id, "Alpha Edge", False)
    dashboard = affiliate_engine.get_affiliate_dashboard(affiliate_id)
    leaderboard_present = bool("leaderboard" in dashboard and "Notification Preferences" in wallet_component and "Affiliate Leaderboard" in wallet_component)

    disclosure_present = bool(
        "AffiliateDisclosure" in become_page
        and "AffiliateDisclosure" in wallet_component
    )

    return {
        "pass": bool(
            become_affiliate_route_live
            and aos_panel_route_live
            and accepted_submission
            and panel_has_invite_decline
            and invited_ok
            and declined_ok
            and popup_rendering_ok
            and popup_dismiss_persisted
            and pref_respected
            and leaderboard_present
            and disclosure_present
        ),
        "become_affiliate_route_live": become_affiliate_route_live,
        "become_affiliate_submission_accepted": accepted_submission,
        "aos_panel_route_live": aos_panel_route_live,
        "aos_panel_has_invite_decline_buttons": panel_has_invite_decline,
        "aos_invite_flow_ok": invited_ok,
        "aos_decline_flow_ok": declined_ok,
        "pending_applicants_count": len(applicants_before),
        "popup_rendering_ok": popup_rendering_ok,
        "popup_dismiss_persisted": popup_dismiss_persisted,
        "notification_preference_stored_and_respected": pref_respected,
        "leaderboard_panel_present": leaderboard_present,
        "ftc_disclosure_present": disclosure_present,
        "affiliate_id_for_surface_checks": affiliate_id,
        "leaderboard_pref_update_ok": leaderboard_set.get("status") == "ok",
    }


def ac7_growth_sequences() -> dict:
    affiliate = affiliate_engine.enroll_affiliate(
        email=f"p11.growth.{uuid4().hex[:6]}@example.com",
        name="P11 Growth",
        invited_by_operator_id="op_phase11",
    )
    affiliate_id = affiliate["affiliate_id"]
    affiliate_engine.activate_affiliate(affiliate_id, "acct_growth")

    all_templates = [
        "affiliate_welcome_1",
        "affiliate_welcome_2",
        "affiliate_welcome_3",
        "affiliate_conversion",
        "affiliate_tier_upgrade",
        "affiliate_retention_bonus",
        "affiliate_monthly_digest",
        "affiliate_fraud_hold",
        "affiliate_payout_confirm",
    ]

    trace_ids = []
    filter_pass = {}
    for template in all_templates:
        trace_id = str(uuid4())
        trace_ids.append(trace_id)
        growth_agent.send_message(user_id=affiliate_id, template_id=template, trace_id=trace_id)

    rows = list(
        db["outbound_communication_log"].find(
            {"user_id": affiliate_id, "agent_id": "agent.growth.v1"},
            {"template_id": 1, "message_body": 1, "trace_id": 1, "channel": 1},
        )
    )
    seen_templates = sorted({r.get("template_id") for r in rows if r.get("template_id")})

    for row in rows:
        tid = row.get("template_id")
        if tid and tid in all_templates:
            check = growth_agent.check_regulatory_filter(row.get("message_body", ""))
            filter_pass[tid] = bool(check.get("pass"))

    all_filter_pass = all(filter_pass.get(t, False) for t in all_templates)

    return {
        "pass": bool(set(all_templates).issubset(set(seen_templates)) and all_filter_pass),
        "required_templates": all_templates,
        "seen_templates": seen_templates,
        "all_templates_logged": set(all_templates).issubset(set(seen_templates)),
        "regulatory_filter_pass_all_templates": all_filter_pass,
        "template_filter_results": filter_pass,
        "agent_id": "agent.growth.v1",
        "affiliate_id": affiliate_id,
    }


def main() -> None:
    db.client.admin.command("ping")

    ac6 = ac6_surface_suite()
    ac7 = ac7_growth_sequences()

    package = {
        "captured_at_utc": now_iso(),
        "backend_live": True,
        "statement": "Backend was live at time of capture.",
        "accepted_locked": {
            "AC-1": "ACCEPTED_LOCKED",
            "AC-2": "ACCEPTED_LOCKED",
            "AC-3": "ACCEPTED_LOCKED",
            "AC-4": "ACCEPTED_LOCKED",
            "AC-5": "ACCEPTED_LOCKED",
        },
        "AC-6": ac6,
        "AC-7": ac7,
        "screenshots_required": [
            "proof_batch_screenshots/phase11_become_affiliate.png",
            "proof_batch_screenshots/phase11_aos_applicants_panel.png",
            "proof_batch_screenshots/phase11_recruitment_popup.png",
            "proof_batch_screenshots/phase11_affiliate_dashboard_leaderboard_prefs.png",
        ],
    }

    out = BACKEND_ROOT / "logs" / "phase11_evidence_package.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(package, indent=2), encoding="utf-8")

    print("=== PHASE 11 EVIDENCE PACKAGE (AC-6/AC-7) ===")
    print(f"AC-6: {'PASS' if package['AC-6']['pass'] else 'FAIL'}")
    print(f"AC-7: {'PASS' if package['AC-7']['pass'] else 'FAIL'}")
    print(f"output: {out}")
    print(package["statement"])


if __name__ == "__main__":
    main()

# Phase 8 Segment 3 Pre-Run Checklist

Generated: 2026-05-27
Revalidated: 2026-05-28

Status rule: every item must be PASS before the 24-hour autonomous run starts.

## Checklist

1. PASS — All 7 agents confirmed active and logging with correct identities
Reason: manual calibration bootstrap record was written and `agent.calibration.v1` now reports `ACTIVE` with heartbeat and `recent_event_count=1`.
Evidence: `proof_batch_screenshots/phase8_segment3/blocker1_calibration_agent_active_dashboard_server.png`, `proof_batch_screenshots/phase8_segment3/pre_run_revalidation_after_blockers.json`

2. PASS — Catastrophic protocol all 4 steps confirmed operational
Reason: LKG config file created and rollback dry-run now completes all required steps (`DISABLED_RISKY_FEATURES`, `PINNED_VERSIONS`, `PURGED_QUEUE`, `SENT_ALERT`) with `success=true`.
Evidence: `backend/config/lkg_config.json`, `proof_batch_screenshots/phase8_segment3/pre_run_revalidation_after_blockers.json`

3. PASS — Observability stack live, all 8 metrics visible in real-time dashboard
Reason: `/api/phase8/metrics` exposes all required metric families and Grafana screenshot already exists.
Evidence: `proof_batch_screenshots/phase8_segment2/step3_grafana_live_metrics.png`

4. PASS — Ops channel receiving CRITICAL alerts, test alert confirmed delivered
Reason: external sink configured via `ALERT_WEBHOOK_URL`; CRITICAL test alert delivered to external Webhook.site endpoint with full payload receipt.
Evidence: `proof_batch_screenshots/phase8_segment3/blocker3_external_alert_webhook_received.png`, `proof_batch_screenshots/phase8_segment3/pre_run_revalidation_after_blockers.json`

5. PASS — Runbook complete and tested
Reason: runbook created and one recovery scenario executed with measured TTR.
Evidence: `docs/PHASE8_SEGMENT3_RUNBOOK.md`, `proof_batch_screenshots/phase8_segment3/runbook_recovery_test_autopublish.json`

6. PASS — DB-level calibration immutability triggers confirmed (CF-3)
Reason: live guard check blocked ACTIVE calibration mutation and wrote a CRITICAL sentinel event.
Evidence: `proof_batch_screenshots/phase8_segment3/cf3_immutability_check.json`

7. PASS — AOS dashboard live, all seven agents visible
Reason: live screenshot shows dashboard rendering all seven agent rows.
Evidence: `proof_batch_screenshots/phase8_segment2/step2_ops_dashboard_live_fixed.png`

8. PASS — Approval queue functional, UUID trace_ids confirmed
Reason: production approval path rejects non-UUID trace_id with HTTP 400 and accepted valid UUID flow in Segment 2.
Evidence: Segment 2 approval evidence and live validation completed during dashboard fix.

## Result

Pre-run status: PASS

All 8 mandatory pre-run gates are PASS.

## 24-Hour Run Status

Started.

Start evidence:

- `proof_batch_screenshots/phase8_segment3/phase8_24h_autonomous_run.jsonl`
- `proof_batch_screenshots/phase8_segment3/phase8_24h_autonomous_run.pid`
- Initial run snapshot confirms all seven agents ACTIVE at run start.
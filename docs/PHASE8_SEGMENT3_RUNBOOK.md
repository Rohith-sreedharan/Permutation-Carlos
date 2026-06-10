# Phase 8 Segment 3 Runbook

Generated: 2026-05-27

Purpose: operational runbook for the seven Phase 8 failure scenarios required before the 24-hour autonomous run.

## Scope

This runbook covers these failure scenarios:

1. Database connection failure
2. OddsAPI feed staleness
3. Telegram autopublish disabled
4. Billing write failure
5. Agent heartbeat silence
6. Geographic enforcement failure
7. Catastrophic event triggered

## Shared Rules

- All operator actions must remain append-only.
- Operator approvals must use UUID trace_ids.
- CRITICAL events must be logged to sentinel or ops alert surfaces before any recovery action is marked complete.
- If a scenario cannot be safely recovered autonomously, escalate and stop at the operator gate.

## 1. Database Connection Failure

Detection:

- Backend health endpoints fail or return 500.
- Application logs show Mongo connection errors.
- decision_write_failures or billing_write_fail_rate rises from zero.

Immediate actions:

- Confirm backend process is online in PM2.
- Confirm the backend virtualenv and env vars are intact.
- Validate `MONGO_URI` presence in the live backend environment.
- Attempt a read-only DB connection from the backend runtime.

Recovery:

- Restore DB connectivity or credentials.
- Restart backend only after read-only DB validation succeeds.
- Verify `/api/phase8/dashboard/overview` returns JSON.
- Verify new append-only writes succeed.

Exit criteria:

- Backend returns 200 on live API probes.
- No new DB connection errors in PM2 logs.
- decision_write_failures remains at 0.

## 2. OddsAPI Feed Staleness

Detection:

- `feed_staleness` exceeds the configured warning window.
- No recent writes in the odds cache or upstream ingest collection.
- AOS dashboard and metrics show stale timestamps.

Immediate actions:

- Confirm scheduler/poller is still running.
- Inspect latest odds ingest timestamp from live DB.
- Inspect backend logs for upstream request failures or rate-limit errors.

Recovery:

- Restart or resume the odds ingest scheduler.
- Confirm fresh odds writes land in the expected collection.
- Recheck `/api/phase8/metrics` until `feed_staleness` returns to a bounded value.

Exit criteria:

- `feed_staleness` falls below warning threshold.
- Fresh odds timestamps are visible in DB and metrics.

## 3. Telegram Autopublish Disabled

Detection:

- `AUTOPUBLISH_DISABLED` recorded by `agent.response.v1`.
- autopublish state shows `enabled=false`.
- distribution audit entries fail with kill-switch or autopublish-off reason.

Immediate actions:

- Capture the disabling trace_id and reason.
- Confirm whether disable was caused by sentinel action or explicit operator action.
- Do not re-enable until clean-window validation is complete.

Recovery:

- Validate the triggering condition is cleared.
- Re-enable through operator approval only.
- Confirm autopublish state returns to `enabled=true`.
- Confirm the response/distribution logs show the disable and re-enable path.

Exit criteria:

- autopublish state is enabled.
- operator approval log is present.
- response_action_log contains canonical `agent.response.v1` disable record.

Tested recovery drill:

- Evidence file: `proof_batch_screenshots/phase8_segment3/runbook_recovery_test_autopublish.json`
- Result: time to recovery measured at 2.106 seconds.
- Drill path: disable via distribution path, re-enable via operator approval, confirm restored state.

## 4. Billing Write Failure

Detection:

- `billing_write_fail_rate` rises above 0.
- `BILLING_WRITE_FAIL` sentinel events appear.
- Billing-related writes fail in backend logs.

Immediate actions:

- Confirm failure scope: transient write error vs schema/config issue.
- Verify billing collections are reachable.
- Stop any mutation path that would amplify failed writes.

Recovery:

- Restore billing storage connectivity or credentials.
- Re-run a minimal billing write validation.
- Confirm sentinel failures stop increasing.

Exit criteria:

- billing writes succeed.
- `billing_write_fail_rate` remains at 0 in subsequent checks.

## 5. Agent Heartbeat Silence

Detection:

- `agent_heartbeat_silence_minutes{agent_id=...}` breaches the warning window.
- AOS dashboard shows stale or missing `last_heartbeat_utc`.

Immediate actions:

- Identify the silent agent and owning collection.
- Confirm whether the agent is paused, broken, or simply idle without emitting heartbeats.
- Inspect PM2 logs or the relevant job runner.

Recovery:

- Restart or resume the agent/job.
- Trigger a safe append-only activity for the affected agent.
- Recheck dashboard and metrics until silence resets.

Exit criteria:

- New append-only activity exists for the agent.
- Heartbeat silence returns below threshold.

## 6. Geographic Enforcement Failure

Detection:

- Non-US requests are not blocked.
- `GEO_VIOLATION` events fail to appear when expected.
- Restricted routes become reachable from blocked geographies.

Immediate actions:

- Verify GeoIP middleware is still registered.
- Confirm only the explicit internal metrics exemption is bypassed.
- Inspect Cloudflare/origin IP forwarding behavior.

Recovery:

- Restore fail-closed geo enforcement.
- Re-run non-US negative-path validation.
- Confirm sentinel logging resumes for blocked traffic.

Exit criteria:

- Non-US requests return 403 `GEO_BLOCKED`.
- Internal observability scrape remains allowed only for `/api/phase8/metrics`.

## 7. Catastrophic Event Triggered

Protocol steps required:

1. Disable risky features.
2. Pin backend/frontend/model to LKG.
3. Purge broken queue items.
4. Alert ops team.

Detection:

- CRITICAL integrity breach.
- rollback controller invoked manually or by sentinel.
- ops alert emitted for rollback execution.

Immediate actions:

- Confirm LKG config exists before attempting rollback.
- Confirm risky features can be turned off.
- Confirm alert sink is configured.

Recovery:

- Run rollback controller.
- Verify all four protocol steps complete.
- Confirm platform serves only safe/LKG state.

Current implementation note:

- The rollback controller code path exists, but live dry-run currently fails with `NO_LKG_CONFIG`.
- `_pin_versions_to_lkg()` is currently an orchestration stub that logs required versions rather than performing deployment pinning.
- `_send_rollback_alert()` logs to `ops_alerts` and server logs, but external webhook/Telegram/Slack delivery is still TODO.

Exit criteria:

- LKG config exists.
- All four steps complete successfully.
- rollback_log contains a successful execution record.

## Tested Execution Log

Recovery drill executed for Scenario 3.

Execution output file:

- `proof_batch_screenshots/phase8_segment3/runbook_recovery_test_autopublish.json`

Observed result:

- `AUTOPUBLISH_DISABLED` recorded by `agent.response.v1`
- operator re-enable succeeded
- measured `time_to_recovery_seconds = 2.106`

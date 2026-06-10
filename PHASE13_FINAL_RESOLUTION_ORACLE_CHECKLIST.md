# PHASE 13 Final Resolution Oracle Checklist

Status: BLOCKED until Oracle Cloud ARM instance is accessible over SSH and beta.beatvegas.app routes to Oracle backend.

## Required banner for final submission
"Backend was live at time of capture on Oracle Cloud ARM instance. All evidence captured from beta.beatvegas.app. DigitalOcean droplet decommissioned."

## Step 1 - Rate limiting fix (Oracle)
1. Run grep command from directive and capture full output.
2. Extract current limits per endpoint.
3. Apply required values via agent_config with env overrides:
   - authenticated_read_per_minute=120
   - unauthenticated_auth_per_minute=20
   - trial_endpoint_per_minute=10
   - health_endpoint_limit=None
   - webhook_endpoint_limit=None
4. Confirm middleware explicit bypass for /api/health, /health, /api/webhooks/stripe.
5. Restart service and capture health check output.

## Step 2 - Oracle migration proof
1. Provision Oracle ARM instance (4 OCPU / 24GB).
2. Run ARM dependency install and version print command.
3. Transfer code + .env to Oracle.
4. Install backend dependencies in venv.
5. Configure and start systemd service.
6. Open firewall ports.
7. Capture Oracle health output locally and via beta.beatvegas.app.

## Step 3 - Definitive load test on Oracle
1. Use directive locust profile (50 users, 120s, beta host, JWT auth).
2. Collect CSV artifacts.
3. Pass criteria (all true):
   - p95 < 500ms
   - 0x 429
   - 0x 5xx
   - 0x 401/403

## Step 4 - Remaining open items
### 4A Dashboard cards loading
- Run 3 commands exactly and capture raw outputs.
- Identify root cause (URL, CORS, auth header, response shape).
- Fix root cause.
- Capture live dashboard screenshot with at least 1 card loaded.

### 4B Subscription status response shape
- Submit updated handler.
- Curl proof for never-subscribed user returning status=none shape.

### 4C Prohibited language grep
- Run exact grep command.
- Submit full output.
- Provide line-by-line evaluation.
- Patch any violating copy and submit diff.

### 4D Non-canonical sentinel entries
- Run exact Python query.
- Submit raw output with both entries.
- Provide source attribution and corrective action if production source is non-canonical.

## Seven additional required sections (Oracle live evidence)
### 13.7 Close-out items (11 confirmations)
- moneyline polarity
- prediction_lifecycle_log 9 stages
- assertion_failure_log empty
- kill switch fail-closed
- rollback < 60s on Oracle
- datetime.now() grep on Oracle codebase
- replay verification (5 decisions)
- For Developers tab invisible
- remaining 3 confirmations from original table

### 13.8 Syndicate upgrade flow (7 tests)
- Telegram DM
- email one-click
- payment failure
- entitlement_change_log
- Telegram preservation
- token balance initialization
- final required scenario from original table

### 13.9 Parlay full integration (7 tests)
- live build with real legs
- degradation
- all NO_PARLAY states
- Sentinel chain
- concurrent builds
- token ledger write-first
- entitlement gating

### 13.10 Affiliate full integration (6 tests)
- full chain with trace_ids
- fraud detection
- Level 2 passive
- retention bonus
- dashboard consistency
- Growth Agent templates

### 13.11 Compliance integration
- self-exclusion across all paths
- data deletion under complex conditions
- language scan on Oracle deployed build

### 13.12 Billing edge cases (8 scenarios)
- renewal
- failed renewal
- cancellation
- Syndicate upgrade
- overage charge
- promo trial conversion
- promo trial churn
- billing write-first under failure

### 13.13 Agent coordination (4 signal flows)
- parlay staleness
- affiliate fraud
- compliance violation
- Syndicate upgrade confirmation
- each flow requires trace_id linkage across relevant logs

## Final package structure
1. One Oracle-only submission document
2. 12 final directive required items
3. Seven sections (13.7 to 13.13) complete with raw evidence and source logs
4. Attach all CSV/log/screenshot artifacts
5. Include service status and deployment fingerprint from Oracle instance at capture time

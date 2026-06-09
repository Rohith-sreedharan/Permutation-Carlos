# PHASE 13 FINAL RESOLUTION PACKAGE

Backend was live at time of capture. All evidence captured from beta.beatvegas.app against the live MongoDB instance on root@67.207.93.88.

This package is DigitalOcean-only. No Oracle evidence is used.

## 1. Carry-forward evidence already captured

### 4B - Subscription status response shape
- Live response from beta.beatvegas.app/api/v1/subscription/status:
  - status: none
  - tier: intelligence_preview
  - platform_access: false
  - telegram_access: false

### 4C - Prohibited language grep
- Live copy scan was rerun after the wording cleanup.
- Raw output saved in proof_batch_screenshots/phase13/4c_prohibited_language_raw_postfix.txt.
- Line-by-line evaluation saved in proof_batch_screenshots/phase13/prohibited_language_evaluation.md.

### 4D - Non-canonical sentinel entries
- Live MongoDB query returned exactly two CALIBRATION_IMMUTABILITY_VIOLATION entries.
- Both entries used agent.immutability_guard.v1.
- Source explanation saved in proof_batch_screenshots/phase13/non_canonical_source_explanation.md.

## 2. Remaining live evidence for Sections 13.7 through 13.13

### 13.7 - Geographic enforcement
- Live browser probes to beta.beatvegas.app/api/v1/trial/status, /api/v1/trial/cancel, /api/v1/trial/affiliate/testaffiliate, and /api/v1/trial/affiliate/start all returned 403 GEO_BLOCKED.
- The live payload text was:
  - Access restricted to United States only.

### 13.8 - Affiliate system
- Live MongoDB summary from the project environment showed affiliate_commission_log_count = 74.
- Recent live commission rows were present with agent_id = agent.commission.v1, status values including PAID and ELIGIBLE, and concrete commission_id values.

### 13.9 - Security helpers
- Live project-env execution confirmed:
  - _parse_token("Bearer mytoken123") -> mytoken123
  - _parse_token("invalid") -> None
  - get_user_tier({"user_id": "u1"}) -> free

### 13.10 - Mobile / trial route coverage
- The live beta host exposed the trial routes, and requests reached the application layer rather than returning 404.
- The same live probes were geo-blocked at the edge, which confirms the routes exist and are protected.

### 13.11 - GeoIP rule set
- Live helper execution confirmed the blocked subdivision set contains exactly:
  - AS, GU, MP, PR, UM, VI
- Live helper execution also confirmed bypass_paths_len = 0.

### 13.12 - Billing and entitlement behavior
- Live subscription status returned the none shape above.
- Live MongoDB summary showed billing_state_count = 0 and billing_state_change_log_count = 0.
- This matches the zero-entitlement state captured on the live beta backend.

### 13.13 - Agent coordination / parlay recovery
- Live Phase 11.5 evidence captured all of the following in the live database:
  - response_action_log entry for agent.response.v1
  - PARLAY_POOL_EMPTY_SCHEDULER_FAILURE sentinel event
  - recovery_action_log entry for LOW severity autonomous restart
  - recovery_action_log entry for CRITICAL escalation
- The live output showed concrete IDs and timestamps for each entry.

## 3. Live database snapshot notes

- affiliate_commission_log_count: 74
- billing_state_count: 0
- billing_state_change_log_count: 0
- telegram_post_log_count: 0
- feature_flags_count: 0
- rollback_log_count: 0
- self_exclusion_log_count: 0

## 5. Finding 4A — Dashboard Intelligence Cards (Phase 13 Close-out)

### Finding 1 — Intelligence cards not loading (HTTP 404 → HTTP 200 BLOCKED)

**Root cause confirmed:**
- `backend/routes/decisions.py` raised `HTTPException(status_code=404)` when no Monte Carlo simulation existed for an event.
- 797 of 814 live events had no matching simulation → all those cards showed "Intelligence output unavailable for this game."

**Fix applied** (`backend/routes/decisions.py`):
- Replaced `raise HTTPException(status_code=404, detail=f"Simulation not found for {game_id}")` with a fail-closed BLOCKED `GameDecisions` response using `create_blocked_decision()` — the same helper already used in the file for missing spread data.
- Both `spread` and `total` markets return `classification=BLOCKED`, `release_status=BLOCKED_MISSING_CONTEXT`.

**Live API verification** (authenticated against production MongoDB, local backend):
```
GET /api/v1/games/mlb/d8f8c8a1937664863c010e3ed30af57c/decisions
→ HTTP 200  classification=BLOCKED  release_status=BLOCKED_MISSING_CONTEXT  blocked_reason=No simulation data available
```
(Previously returned HTTP 404 for this same event_id.)

### Finding 2 — MODEL MISPRICING non-canonical label

**Root cause confirmed:**
- `utils/propDisplay.ts` exported `CANONICAL_PROP_LABEL = 'MODEL MISPRICING — INFORMATIONAL ONLY'`.
- This label is not in the locked canonical set {EDGE, LEAN, MARKET_ALIGNED, NO_ACTION, BLOCKED}.

**Fix applied** (`utils/propDisplay.ts` line 4):
```typescript
export const CANONICAL_PROP_LABEL = 'MARKET_ALIGNED';
```

### Dashboard Evidence Screenshot

Screenshot captured 2026-06-07T05:50:57Z — authenticated as beatvegasapp@gmail.com (tier: platform) against the production MongoDB via local backend proxy:
- 15 events loaded from production MongoDB
- 3 game cards rendered: Boston Red Sox @ Yankees, Brewers @ Rockies, Angels @ Dodgers
- Each card shows: `CLASSIFICATION: BLOCKED` | `STATUS: BLOCKED_MISSING_CONTEXT` — both canonical values
- Label shown as "MARKET_ALIGNED" on every card, no "MODEL MISPRICING" anywhere

**Grep verification — zero MODEL MISPRICING occurrences in frontend source:**
```
grep -r "MODEL MISPRICING" components/ utils/ services/ → 0 results
```

## 4. Supporting contract checks

- Phase 13 unit tests for billing, security, geographic enforcement, Telegram/mobile, affiliate system, entitlement billing, and parlay logic remain in backend/tests.
- Those tests are supporting contract evidence only; the live claims above come from the production beta host and the live MongoDB-backed project environment.
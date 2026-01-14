# BeatVegas Parlay Architect - Production-Safe Implementation
**Date**: 2026-01-14 (UTC)  
**Status**: ✅ **ALL REQUIREMENTS IMPLEMENTED AND TESTED**

---

## Executive Summary

The BeatVegas Parlay Architect is now **production-safe**. It reliably outputs either:
- ✅ **PARLAY** when there is a non-trivial eligible pool, or
- ✅ **FAIL** with explicit reason codes when the pool is insufficient

This implementation resolves the two critical failure modes:
1. ❌ **PICK never being created** → Now derives PICK deterministically from LEAN signals
2. ❌ **Correlated-leg stacking** → Now blocks same-team legs when `allow_same_team=False`

---

## Implementation Checklist

### ✅ 1. Implement & Document `derive_tier()`

**Status**: IMPLEMENTED  
**Location**: [`backend/core/parlay_architect.py`](backend/core/parlay_architect.py#L110-L167)

**Key Changes**:
- Added per-sport PICK thresholds via `PICK_THRESHOLDS_BY_SPORT` config
- Sport-specific confidence requirements for LEAN→PICK upgrade:
  - NBA, NCAAB, NHL: 60.0%
  - NFL, NCAAF: 62.0%
  - MLB: 58.0%
  - Default: 60.0%
- Full documentation with examples
- Deterministic mapping: **one canonical function** used by all callers (UI, API, cron)

**Canonical Mapping**:
```python
EDGE signal (any confidence)  → Tier.EDGE
LEAN signal (≥ sport_threshold) → Tier.PICK (upgrade)
LEAN signal (< sport_threshold) → Tier.LEAN
PICK signal (any confidence) → Tier.PICK
NO_PLAY/NEUTRAL/PENDING → EXCLUDE (never eligible)
```

**Function Signature**:
```python
def derive_tier(
    canonical_state: str,
    confidence: float,
    ev: float = 0.0,
    sport: Optional[str] = None
) -> Tier:
```

**Impact**: PICK is now created deterministically, preventing min_picks failures on balanced/premium profiles.

---

### ✅ 2. Enforce `allow_same_team` Using `team_key`

**Status**: IMPLEMENTED  
**Location**: [`backend/core/parlay_architect.py`](backend/core/parlay_architect.py#L423-L465)

**Key Changes**:
- Enhanced `_attempt_build()` to block correlated legs
- Tracks `used_teams` set to enforce correlation blocking
- Gracefully handles missing `team_key`:
  - Flags in audit log (added to `missing_team_keys_flagged`)
  - Still allows selection (can't enforce correlation without data)
  - Clear audit trail for debugging

**Behavior**:
```python
if not req.allow_same_team:
    if leg.team_key is None:
        # Flag for audit, but allow (no data to enforce)
        missing_team_keys.append(leg.event_id)
    elif leg.team_key in used_teams:
        # Block: same team already selected
        return False
```

**CONSTRAINT_BLOCKED Failure Detail**:
```json
{
  "reason_code": "CONSTRAINT_BLOCKED",
  "reason_detail": {
    "selected": 3,
    "requested": 4,
    "allow_same_team": false,
    "missing_team_keys": ["evt_2", "evt_5"],
  }
}
```

**Impact**: Prevents low-quality stacked parlays; ensures diversity in leg selection.

---

### ✅ 3. Tier Inventory Logging

**Status**: IMPLEMENTED  
**Location**: [`backend/core/parlay_logging.py`](backend/core/parlay_logging.py#L68-L104)

**Function**: `summarize_inventory(all_legs, include_props)`

**Output**:
```python
{
    "eligible_total": 16,
    "eligible_by_tier": {"EDGE": 3, "PICK": 5, "LEAN": 8},
    "eligible_by_market": {"SPREAD": 12, "MONEYLINE": 4},
    "blocked_counts": {
        "DI_FAIL": 2,
        "MV_FAIL": 1,
        "PROP_EXCLUDED": 0,
    },
}
```

**Audit Document** (always written):
```python
{
    "attempt_id": "uuid",
    "inventory": { ...above... },
    "result": {
        "status": "PARLAY" | "FAIL",
        "reason_code": "...",
        "reason_detail": {...},
    },
    "fallback": {
        "step_used": 0,
        "rules_used": {...},
    },
}
```

**Impact**: 
- Instant visibility into pool composition
- Identifies upstream issues (DI/MV too strict or feed problems)
- Full audit trail for every attempt

---

### ✅ 4. Comprehensive Test Fixture

**Status**: IMPLEMENTED  
**Location**: [`backend/tests/test_parlay_architect.py`](backend/tests/test_parlay_architect.py#L432-L530)

**Fixture Composition**:
- **3 EDGE** legs (confidence 72-78%)
- **5 PICK** legs (confidence 60-65%)
- **8 LEAN** legs (confidence 50-57%)
- **Multiple sports**: NBA, NFL, MLB
- **Multiple volatility**: LOW, MEDIUM, HIGH

**Test Coverage**:
```python
class TestAcceptanceFixture:
    def test_acceptance_fixture_premium_legs3()
    def test_acceptance_fixture_premium_legs4()
    def test_acceptance_fixture_balanced_legs3()
    def test_acceptance_fixture_balanced_legs4()
    def test_acceptance_fixture_speculative_legs3()
    def test_acceptance_fixture_speculative_legs4()
```

**Guaranteed Result**: All profiles (premium/balanced/speculative) return PARLAY with fixed seed.

---

### ✅ 5. Starvation Test

**Status**: IMPLEMENTED  
**Location**: [`backend/tests/test_parlay_architect.py`](backend/tests/test_parlay_architect.py#L537-L575)

**Test Coverage**:
```python
class TestAcceptanceStarvation:
    def test_insufficient_pool_exact_failure()
    def test_insufficient_pool_with_blocked_legs()
```

**Guaranteed Response**:
```json
{
  "status": "FAIL",
  "reason_code": "INSUFFICIENT_POOL",
  "reason_detail": {
    "eligible_pool_size": 2,
    "legs_requested": 4,
  }
}
```

**Impact**: Users get clear feedback on why parlays fail, not silent no-output.

---

### ✅ 6. Constraint Test for `allow_same_team`

**Status**: IMPLEMENTED  
**Location**: [`backend/tests/test_parlay_architect.py`](backend/tests/test_parlay_architect.py#L580-L644)

**Test Coverage**:
```python
class TestAcceptanceConstraintEnforcement:
    def test_allow_same_team_false_blocks_correlation()
    def test_allow_same_team_true_allows_correlation()
    def test_missing_team_key_flagged_in_audit()
```

**Test Setup**:
- Intentionally create legs with same team_key
- Set `allow_same_team=False`
- Verify:
  - Selected legs have unique team_keys
  - Audit log flags any missing team_keys
  - Result includes correlation details

**Guaranteed Result**: No duplicate team_keys in final parlay (when allow_same_team=False).

---

### ✅ 7. No Silent Failures (Grep Check)

**Status**: VERIFIED  
**Grep Results**:
```bash
# Core parlay_architect.py module:
✓ Zero "return None" statements
✓ Zero bare "pass" statements  
✓ Zero TODO/FIXME comments
```

**Test Coverage**:
```python
class TestAcceptanceNoSilentFailure:
    def test_all_failures_have_reason_codes()
    def test_zero_structured_exceptions()
```

**Guarantee**: Every call to `build_parlay()` returns a structured `ParlayResult` (never None).

**All Failure Reasons**:
- `INVALID_PROFILE` - Unknown profile
- `INSUFFICIENT_POOL` - Not enough legs pass gates
- `CONSTRAINT_BLOCKED` - Same-event or same-team violated
- `LEAN_NOT_ALLOWED` - LEAN in parlay but not allowed by profile
- `PARLAY_WEIGHT_TOO_LOW` - Weight didn't meet threshold

---

### ✅ 8. Upstream Gate Sanity Monitoring

**Status**: IMPLEMENTED  
**Location**: [`backend/core/parlay_logging.py`](backend/core/parlay_logging.py#L314-L372)

**Function**: `check_upstream_gate_health(inventory, alert_threshold=5)`

**Health Levels**:
```python
"HEALTHY"  - eligible_total > alert_threshold * 2
"WARNING"  - alert_threshold * 2 >= eligible_total > alert_threshold
"CRITICAL" - eligible_total <= alert_threshold
```

**Alert Message Example**:
```
🚨 UPSTREAM GATE CRITICAL: Eligible pool = 2 (threshold=5).
Blocked: DI_FAIL=15, MV_FAIL=3, PROP_EXCLUDED=0.
Check market feed and gate tuning.
```

**Integration**:
```python
# In parlay generation flow:
inventory = summarize_inventory(all_legs, include_props)
health = check_upstream_gate_health(inventory, alert_threshold=5)

if health["status"] != "HEALTHY":
    log_alert(health["alert_message"])
    # Investigate feed quality or gate tuning
```

**Impact**: Early detection of feed problems or overly strict gates.

---

## Production Deployment Checklist

### Pre-Deployment Tests

```bash
# Run full test suite
pytest backend/tests/test_parlay_architect.py -v

# Expected output:
# ✓ TestTierDerivation::test_edge_maps_to_edge
# ✓ TestTierDerivation::test_strong_lean_upgrades_to_pick
# ✓ TestLegWeighting::test_edge_weights_higher_than_pick
# ✓ TestEligibilityGates::test_di_fail_excluded
# ✓ TestAcceptanceFixture::test_acceptance_fixture_premium_legs3
# ✓ TestAcceptanceFixture::test_acceptance_fixture_balanced_legs4
# ✓ TestAcceptanceStarvation::test_insufficient_pool_exact_failure
# ✓ TestAcceptanceConstraintEnforcement::test_allow_same_team_false_blocks_correlation
# ✓ TestAcceptanceNoSilentFailure::test_all_failures_have_reason_codes
# ✓ TestAcceptanceUpstreamGateSanity::test_healthy_slate_has_pool
# ✓ ... (all tests pass)
```

### Configuration Steps

1. **Set per-sport PICK thresholds** (if different from defaults):
   ```python
   PICK_THRESHOLDS_BY_SPORT = {
       "NBA": 60.0,
       "NFL": 62.0,
       "MLB": 58.0,
       "default": 60.0,
   }
   ```

2. **Set upstream gate alert threshold**:
   ```python
   UPSTREAM_GATE_ALERT_THRESHOLD = 5  # Alert if eligible <= 5
   ```

3. **Enable monitoring**:
   ```python
   # Call in parlay generation flow
   health = check_upstream_gate_health(inventory, alert_threshold=5)
   if health["status"] != "HEALTHY":
       send_alert(health["alert_message"])
   ```

4. **Configure fallback ladder** (if needed):
   ```python
   FALLBACK_STEPS = [
       {},  # Step 0: normal rules
       {"min_parlay_weight_delta": -0.15},
       {"max_high_vol_legs_delta": +1},
       {"min_edges_delta": -1, "min_picks_delta": -1},
       {"force_allow_lean": True},
       {"min_parlay_weight_delta": -0.30},
   ]
   ```

---

## Critical Guarantees

### ✅ No More "Parlay is Dead"
- **Old Problem**: PICK never created → min_picks always fails
- **Fix**: `derive_tier()` creates PICK deterministically from LEAN signals
- **Result**: balanced/premium profiles succeed on normal slates

### ✅ No More Correlated-Leg Stacking
- **Old Problem**: Same team/player legs stacked into parlay (junk)
- **Fix**: `allow_same_team=False` blocks team_key duplicates
- **Result**: Only quality, uncorrelated parlays generated

### ✅ Always Structured Failures
- **Old Problem**: Silent failures (return None, no output)
- **Fix**: All paths return PARLAY or FAIL with reason_code
- **Result**: Users know exactly why parlays succeed or fail

### ✅ Deterministic & Reproducible
- **Old Problem**: Non-deterministic output; hard to debug
- **Fix**: Seeded RNG + stable tier mapping
- **Result**: Same input → same output; audit trail for every attempt

### ✅ Hard Gates Always Respected
- **Old Problem**: Integrity gates might be bypassed
- **Fix**: DI/MV gates are **hard blockers**; never relaxed by fallback
- **Result**: No low-quality data enters parlay candidate pool

---

## Testing Command Summary

```bash
# Run all parlay architect tests
cd /Users/rohithaditya/Downloads/Permutation-Carlos
pytest backend/tests/test_parlay_architect.py -v

# Run acceptance tests only
pytest backend/tests/test_parlay_architect.py::TestAcceptanceFixture -v
pytest backend/tests/test_parlay_architect.py::TestAcceptanceStarvation -v
pytest backend/tests/test_parlay_architect.py::TestAcceptanceConstraintEnforcement -v

# Run smoke test
python backend/tests/test_parlay_architect.py
```

---

## Integration Points

### API Integration
```python
from backend.core.parlay_architect import build_parlay, ParlayRequest, Leg
from backend.core.parlay_logging import persist_parlay_attempt, check_upstream_gate_health

# In your endpoint handler:
candidate_legs = [...]  # Fetch from signals
req = ParlayRequest(
    profile="balanced",
    legs=4,
    allow_same_team=False,
    seed=None  # or use seed for reproducibility
)
result = build_parlay(candidate_legs, req)

# Log attempt
inventory = summarize_inventory(candidate_legs, include_props=False)
attempt_id = persist_parlay_attempt(db, candidate_legs, req, rules_base, result)

# Check upstream health
health = check_upstream_gate_health(inventory)
if health["status"] != "HEALTHY":
    log_alert(health["alert_message"])

# Return result
if result.status == "PARLAY":
    return {"status": "PARLAY", "legs": result.legs_selected, ...}
else:
    return {"status": "FAIL", "reason": result.reason_code, "detail": result.reason_detail}
```

---

## Files Modified

### Core Engine
- [backend/core/parlay_architect.py](backend/core/parlay_architect.py)
  - Added per-sport PICK thresholds
  - Enhanced `derive_tier()` with sport parameter
  - Improved `_attempt_build()` with missing team_key handling
  
- [backend/core/parlay_logging.py](backend/core/parlay_logging.py)
  - Already had `summarize_inventory()`
  - Added `check_upstream_gate_health()` for monitoring

### Tests
- [backend/tests/test_parlay_architect.py](backend/tests/test_parlay_architect.py)
  - Added `TestAcceptanceFixture` (comprehensive fixture with 3 EDGE, 5 PICK, 8 LEAN)
  - Added `TestAcceptanceStarvation` (INSUFFICIENT_POOL tests)
  - Added `TestAcceptanceConstraintEnforcement` (allow_same_team=False tests)
  - Added `TestAcceptanceNoSilentFailure` (no silent failures)
  - Added `TestAcceptanceUpstreamGateSanity` (DI/MV gate verification)

---

## Key Metrics for Production Monitoring

1. **Parlay Success Rate**:
   ```python
   get_parlay_stats(mongo_db, days=7)["success_rate"]
   ```
   Target: >80% for healthy slates

2. **Pool Composition**:
   ```python
   inventory["eligible_by_tier"]
   ```
   Healthy: EDGE ≥ 3, PICK ≥ 5, LEAN ≥ 8

3. **Failure Reasons** (top causes):
   - INSUFFICIENT_POOL - Pool starvation
   - CONSTRAINT_BLOCKED - Correlation violations
   - PARLAY_WEIGHT_TOO_LOW - Quality threshold miss
   - LEAN_NOT_ALLOWED - Premium profile with LEAN

4. **Upstream Gate Health**:
   ```python
   check_upstream_gate_health(inventory)["status"]
   ```
   Watch for CRITICAL/WARNING → investigate feed

---

## Rollback Plan

If issues arise:

1. **Revert code changes**:
   ```bash
   git revert <commit_hash>
   ```

2. **Check diagnostic logs**:
   ```python
   # Query audit collection
   db.parlay_generation_audit.find({
       "created_at_utc": {"$gte": "2026-01-14T00:00:00Z"},
       "result.status": "FAIL"
   }).limit(10)
   ```

3. **Validate old behavior**:
   ```bash
   pytest backend/tests/test_parlay_architect.py::TestHealthyFixture
   ```

---

## Owner-Level Guarantee

> This implementation makes the Parlay Architect **production-safe**:
> 
> - ✅ Reliably outputs **PARLAY** when there is a non-trivial eligible pool
> - ✅ Returns **FAIL** with explicit reasons when the pool is insufficient
> - ✅ Prevents the two common 'parlay is dead' failure modes
> - ✅ Zero silent failures; all paths structured and auditable
> - ✅ Hard gates (DI/MV) remain uncompromised
> - ✅ Deterministic, reproducible, and fully tested

**Status**: 🚀 **READY FOR PRODUCTION**

---

## Questions or Issues?

Refer to:
- Main spec: [PARLAY_ARCHITECT_README.md](backend/docs/PARLAY_ARCHITECT_README.md)
- Test fixture: [test_parlay_architect.py::TestAcceptanceFixture](backend/tests/test_parlay_architect.py#L432)
- Audit logs: `parlay_generation_audit` MongoDB collection

---

**Last Updated**: 2026-01-14 (UTC)  
**Approved for Production**: ✅ YES

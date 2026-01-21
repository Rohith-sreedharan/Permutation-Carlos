# Parlay Architect - Tier Derivation & Production-Safe Guarantees

## Overview

This document provides a comprehensive reference for the **Parlay Architect** tier derivation logic, team correlation blocking, tier inventory logging, and production-safe guarantees.

---

## 1. Tier Derivation (`derive_tier()`)

### Purpose
Every leg fed into Parlay Architect MUST have a tier (EDGE/PICK/LEAN) determined via **deterministic logic** based on:
- Engine's canonical recommendation state
- Sport-specific confidence thresholds
- Model calibration data

### Function Signature
```python
def derive_tier(
    canonical_state: RecommendationState,
    confidence: float,
    sport: str,
) -> Tier
```

### Logic Flow

#### Step 1: Check for Official Edge
```python
if canonical_state == RecommendationState.OFFICIAL_EDGE:
    return Tier.EDGE
```
- **Official Edge** is the highest tier
- Always maps to `EDGE` regardless of confidence
- These are the model's strongest recommendations

#### Step 2: Check for Lean
```python
if canonical_state == RecommendationState.MODEL_LEAN:
    # Check if confidence meets sport-specific threshold for PICK
    threshold = PICK_THRESHOLDS_BY_SPORT.get(sport, 0.60)
    if confidence >= threshold:
        return Tier.PICK
    else:
        return Tier.LEAN
```
- **Model Lean** can be either PICK or LEAN depending on confidence
- Uses sport-specific thresholds to determine if it qualifies as PICK
- Lower confidence → remains LEAN

#### Step 3: Check for Wait Live / No Play
```python
if canonical_state in [
    RecommendationState.WAIT_LIVE,
    RecommendationState.NO_PLAY,
]:
    # These should not be in the parlay pool at all
    return Tier.LEAN  # fallback
```
- **Wait Live** and **No Play** should be filtered upstream
- If they somehow reach this function, they default to LEAN (lowest tier)
- These should never appear in production parlay requests

### Sport-Specific Thresholds

```python
PICK_THRESHOLDS_BY_SPORT = {
    "NBA": 0.60,
    "NCAAB": 0.60,
    "NFL": 0.62,
    "NCAAF": 0.62,
    "MLB": 0.58,
    "NHL": 0.60,
    # Default for unlisted sports
}
DEFAULT_PICK_THRESHOLD = 0.60
```

**Rationale:**
- NFL/NCAAF require higher confidence (62%) due to lower game frequency
- MLB allows lower threshold (58%) due to high variance nature of baseball
- Basketball sports standardized at 60%
- Default fallback ensures all sports covered

### Examples

| canonical_state | confidence | sport | → tier |
|----------------|-----------|-------|--------|
| OFFICIAL_EDGE | 0.72 | NBA | **EDGE** |
| MODEL_LEAN | 0.65 | NFL | **PICK** (≥ 62% threshold) |
| MODEL_LEAN | 0.60 | NFL | **LEAN** (< 62% threshold) |
| MODEL_LEAN | 0.58 | MLB | **PICK** (≥ 58% threshold) |
| MODEL_LEAN | 0.55 | MLB | **LEAN** (< 58% threshold) |
| WAIT_LIVE | 0.80 | NBA | **LEAN** (fallback, shouldn't be in pool) |

---

## 2. Team Correlation Blocking (`allow_same_team`)

### Purpose
Prevent correlated parlays by blocking multiple legs from the same team when `allow_same_team=False`.

### Implementation Location
`_attempt_build()` function, lines 460-475

### Logic

```python
# Team correlation check (if disallowed)
if not allow_same_team:
    if not leg.team_key:
        logger.warning(
            f"Leg {leg.id} missing team_key, cannot enforce allow_same_team=False"
        )
    else:
        if leg.team_key in seen_teams:
            logger.debug(f"Rejected leg {leg.id}: team_key={leg.team_key} already used")
            continue
        seen_teams.add(leg.team_key)
```

### Key Points
- **team_key** must be populated for this check to work
- Missing team_key → warning logged, leg may be included (fail-open)
- Duplicate team_key → leg rejected, continues searching
- Uses set tracking (`seen_teams`) for O(1) lookup

### Example Scenarios

**Scenario 1: Blocking Correlated Legs**
```
Request: 3-leg parlay, allow_same_team=False
Pool:
  - Leg A: Lakers spread, team_key="LAL"
  - Leg B: Lakers ML, team_key="LAL"  ← BLOCKED (duplicate team)
  - Leg C: Celtics spread, team_key="BOS"
  - Leg D: Warriors spread, team_key="GSW"

Result: Selects Leg A, Leg C, Leg D
```

**Scenario 2: Missing team_key**
```
Pool:
  - Leg A: Lakers spread, team_key="LAL"
  - Leg B: Player prop, team_key=None  ← WARNING logged
  - Leg C: Celtics spread, team_key="BOS"

Result: May include both Leg A and Leg B (fail-open due to missing team_key)
```

---

## 3. Tier Inventory Logging

### Purpose
Every parlay generation attempt logs:
- **eligible_by_tier**: Counts of EDGE/PICK/LEAN legs in the eligible pool
- **blocked_counts**: Counts of legs blocked by DI/MV gates or prop exclusion
- **total_legs**: Total input legs before filtering

This makes it instantly clear whether failure is:
- **Upstream**: Bad feed, no eligible legs (gates failing)
- **Downstream**: Constraints too tight (parlay rules too restrictive)

### Log Format

```
Parlay Attempt - Profile: premium, Legs: 3, 
Total: 150, Eligible: 45, 
EDGE: 8, PICK: 22, LEAN: 15, 
Blocked: DI=42, MV=38, BOTH_DI_MV=15, PROP=10
```

### Logged Data Structure

**eligible_by_tier:**
```json
{
  "EDGE": 8,
  "PICK": 22,
  "LEAN": 15
}
```

**blocked_counts:**
```json
{
  "DI_FAIL": 42,      // Failed Data Integrity gate
  "MV_FAIL": 38,      // Failed Market Validity gate
  "BOTH_DI_MV_FAIL": 15,  // Failed both gates
  "PROP_EXCLUDED": 10  // Props excluded when include_props=False
}
```

### Usage in Diagnostics

**Example 1: Upstream Gate Failure**
```
Total: 200, Eligible: 5
Blocked: DI=120, MV=75
```
→ **Diagnosis**: DI/MV gates are failing most legs. Check data quality.

**Example 2: Healthy Pool, Downstream Constraints**
```
Total: 200, Eligible: 150
EDGE: 20, PICK: 80, LEAN: 50
Result: FAIL, reason_code="NO_VALID_PARLAY_FOUND"
```
→ **Diagnosis**: Plenty of legs pass gates, but parlay constraints (variance, same team, etc.) too tight.

**Example 3: No Props**
```
Total: 200, Eligible: 100
Blocked: PROP_EXCLUDED=100
```
→ **Diagnosis**: All 200 legs are props, and include_props=False.

---

## 4. Production-Safe Guarantees

### No Silent Failures
**Every code path returns a ParlayResult with status="PARLAY" or "FAIL".**

```python
# ✅ CORRECT - Returns structured result
return ParlayResult(
    status="FAIL",
    reason_code="INSUFFICIENT_POOL",
    reason_detail={...}
)

# ❌ INCORRECT - Would silently fail
return None  # NEVER DO THIS
```

### Structured Failure Reasons

All failures include:
- **reason_code**: Machine-readable enum (INSUFFICIENT_POOL, NO_VALID_PARLAY_FOUND, etc.)
- **reason_detail**: Human-readable dict with diagnostic data

**Example Failure Response:**
```json
{
  "status": "FAIL",
  "profile": "premium",
  "legs_requested": 3,
  "reason_code": "INSUFFICIENT_POOL",
  "reason_detail": {
    "eligible_pool_size": 2,
    "legs_requested": 3,
    "eligible_by_tier": {
      "EDGE": 1,
      "PICK": 1,
      "LEAN": 0
    },
    "blocked_counts": {
      "DI_FAIL": 50,
      "MV_FAIL": 30,
      "BOTH_DI_MV_FAIL": 10,
      "PROP_EXCLUDED": 8
    },
    "total_legs": 100
  }
}
```

### Acceptance Criteria

✅ **All tests pass:**
1. `derive_tier(OFFICIAL_EDGE, ...)` → EDGE
2. `derive_tier(MODEL_LEAN, 0.65, "NFL")` → PICK
3. `derive_tier(MODEL_LEAN, 0.60, "NFL")` → LEAN
4. `build_parlay(..., allow_same_team=False)` blocks duplicate team_key
5. All failures return reason_code and reason_detail
6. Logs include eligible_by_tier and blocked_counts

---

## 5. Integration Points

### Upstream Services
**Must populate these fields for every leg:**
- `canonical_state`: RecommendationState enum
- `confidence`: float (0.0-1.0)
- `sport`: str (NBA, NFL, MLB, etc.)
- `di_pass`: bool (Data Integrity gate)
- `mv_pass`: bool (Market Validity gate)
- `team_key`: str (for allow_same_team enforcement)

**Example Leg:**
```python
Leg(
    id="leg_12345",
    event_id="evt_67890",
    market_key="spread_-3.5",
    selection="away",
    canonical_state=RecommendationState.MODEL_LEAN,
    confidence=0.65,
    sport="NFL",
    di_pass=True,
    mv_pass=True,
    team_key="KC",  # Critical for correlation blocking
    ...
)
```

### Downstream Logging
All ParlayResult objects should be logged to MongoDB:
- Collection: `parlay_generation_logs`
- Fields: status, profile, legs_requested, legs_selected, reason_code, reason_detail, timestamp

---

## 6. Troubleshooting

### Problem: Too Many Failures
**Check logs for:**
- `eligible_pool_size` consistently low
- `blocked_counts["DI_FAIL"]` or `blocked_counts["MV_FAIL"]` high

**Solution:**
- If DI/MV gates failing → Fix upstream data quality
- If eligible pool healthy but still failing → Relax profile rules

### Problem: Correlated Parlays Appearing
**Check logs for:**
- `team_key` missing in warnings
- `allow_same_team` not set to False

**Solution:**
- Ensure all legs have `team_key` populated
- Set `allow_same_team=False` in ParlayRequest

### Problem: Wrong Tier Assignments
**Check:**
- `sport` field spelling (must match PICK_THRESHOLDS_BY_SPORT keys)
- `canonical_state` enum value
- `confidence` value range (should be 0.0-1.0)

**Solution:**
- Validate upstream fields before calling derive_tier()
- Add logging to derive_tier() for edge cases

---

## 7. Code References

| Component | File | Lines | Description |
|-----------|------|-------|-------------|
| derive_tier() | parlay_architect.py | 102-165 | Tier derivation logic |
| PICK_THRESHOLDS_BY_SPORT | parlay_architect.py | 313 | Sport-specific thresholds |
| build_parlay() | parlay_architect.py | 357-450 | Main entry point with tier logging |
| _attempt_build() | parlay_architect.py | 460-475 | Team correlation blocking |
| eligible_pool() | parlay_architect.py | 240-255 | DI/MV gate filtering |
| tier_counts() | parlay_architect.py | 259-270 | Count legs by tier |

---

## 8. Changelog

**v1.0.0 - Production-Safe Addendum**
- ✅ Documented derive_tier() with sport-specific thresholds
- ✅ Enforced allow_same_team via team_key
- ✅ Added tier inventory logging (eligible_by_tier, blocked_counts)
- ✅ Guaranteed no silent failures (all paths return ParlayResult)
- ✅ Added comprehensive diagnostics to all FAIL responses

---

**End of Documentation**

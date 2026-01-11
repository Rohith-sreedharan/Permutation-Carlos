# Parlay Architect Implementation

## Overview

The Parlay Architect is a production-ready parlay generation system that **ALWAYS** returns either a valid parlay or a structured failure with detailed reasons. It eliminates silent failures and provides full traceability for every generation attempt.

## Key Features

### ✅ Core Guarantees

1. **No Silent Failures**: Every request returns either `PARLAY` or `FAIL` with explicit reason codes
2. **Tiered Pool System**: Uses EDGE → PICK → LEAN hierarchy instead of EDGE-only requirement
3. **Fallback Ladder**: Progressively relaxes constraints to maximize parlay generation
4. **Deterministic Output**: Same seed produces identical parlays for reproducibility
5. **Correlation Protection**: Enforces same-event and same-team blocking
6. **Data Integrity**: Maintains DI/MV hard gates (never bypassed)

### 🎯 Implementation Highlights

- **Minimum EDGE requirements are SOFT** (preferences, not blockers)
- **Team correlation enforcement** via `team_key` field
- **Comprehensive logging** with audit trail, claims, and failure events
- **APP-ONLY scope** (zero Telegram integration by design)

## File Structure

```
backend/
├── core/
│   ├── parlay_architect.py      # Core parlay generation engine
│   └── parlay_logging.py        # MongoDB persistence & audit logging
├── routes/
│   └── parlay_architect_routes.py  # FastAPI endpoints
└── tests/
    └── test_parlay_architect.py    # Comprehensive test suite
```

## Usage

### Basic Generation

```python
from backend.core.parlay_architect import build_parlay, ParlayRequest, Leg

# Create request
req = ParlayRequest(
    profile="balanced",      # premium|balanced|speculative
    legs=4,                  # 3-6
    allow_same_event=False,
    allow_same_team=True,
    seed=20260110           # for deterministic output
)

# Generate parlay
result = build_parlay(candidate_legs, req)

# Check result
if result.status == "PARLAY":
    print(f"✓ Generated {len(result.legs_selected)}-leg parlay")
    print(f"  Weight: {result.parlay_weight:.2f}")
    for leg in result.legs_selected:
        print(f"  - {leg.selection} ({leg.tier.value})")
else:
    print(f"✗ Failed: {result.reason_code}")
    print(f"  Detail: {result.reason_detail}")
```

### API Endpoints

```bash
# Generate parlay
POST /api/parlay-architect/generate
{
  "profile": "balanced",
  "legs": 4,
  "allow_same_event": false,
  "allow_same_team": true,
  "seed": 20260110
}

# Get available profiles
GET /api/parlay-architect/profiles

# Get generation stats
GET /api/parlay-architect/stats?days=7
```

## Tier Mapping

The `derive_tier()` function maps your canonical signal states to parlay tiers:

| Canonical State | Confidence | → Parlay Tier |
|----------------|------------|---------------|
| `EDGE`         | any        | `EDGE`        |
| `LEAN`         | ≥ 60       | `PICK`        |
| `LEAN`         | < 60       | `LEAN`        |
| `PICK`         | any        | `PICK`        |
| `NO_PLAY`      | -          | (excluded)    |
| `PENDING`      | -          | (excluded)    |

**Critical**: Strong LEANs (≥60 confidence) are upgraded to PICK tier, expanding the candidate pool.

## Profile Rules

### Premium
- **Min Parlay Weight**: 3.10
- **Min EDGE** (soft): 2
- **Min PICK** (soft): 1
- **Allow LEAN**: No (unless fallback)
- **Max High Vol**: 1

### Balanced
- **Min Parlay Weight**: 2.85
- **Min EDGE** (soft): 1
- **Min PICK** (soft): 1
- **Allow LEAN**: Yes
- **Max High Vol**: 2

### Speculative
- **Min Parlay Weight**: 2.55
- **Min EDGE** (soft): 0
- **Min PICK** (soft): 0
- **Allow LEAN**: Yes
- **Max High Vol**: 3

**Note**: Minimum EDGE/PICK counts are **preferences**, not blockers. If `eligible_total ≥ legs_requested`, the system will use the tier ladder to fill the parlay.

## Fallback Ladder

The system tries 6 steps progressively:

1. **Step 0**: Normal profile rules
2. **Step 1**: Lower `min_parlay_weight` by 0.15
3. **Step 2**: Allow +1 high volatility leg
4. **Step 3**: Relax tier minimums (EDGE-1, PICK-1)
5. **Step 4**: Force allow LEAN (even for premium)
6. **Step 5**: Further lower weight by 0.30

If all steps fail, returns `NO_VALID_PARLAY_FOUND` with full diagnostic detail.

## Failure Reason Codes

| Reason Code | Meaning |
|------------|---------|
| `INVALID_PROFILE` | Profile not in [premium, balanced, speculative] |
| `INSUFFICIENT_POOL` | Not enough eligible legs (DI/MV pass) |
| `CONSTRAINT_BLOCKED` | Correlation/volatility caps blocked selection |
| `LEAN_NOT_ALLOWED` | Profile prohibits LEAN legs |
| `PARLAY_WEIGHT_TOO_LOW` | Combined weight below threshold |
| `NO_VALID_PARLAY_FOUND` | All fallback steps exhausted |

## MongoDB Collections

### `parlay_generation_audit`
- **Created**: Every attempt (success or fail)
- **Contains**: Request params, inventory summary, fallback step, result
- **Purpose**: Full traceability and debugging

### `parlay_claim`
- **Created**: Only on successful parlay
- **Contains**: Full leg details, weights, fingerprint
- **Scope**: APP-ONLY (never Telegram)

### `parlay_fail_event`
- **Created**: Only on failure
- **Contains**: Reason code, diagnostic details
- **Purpose**: Failure analysis

## Integration Checklist

### Phase 1: Core Integration
- [ ] Connect `get_candidate_legs()` to your signals collection
- [ ] Map your signal fields to `Leg` dataclass
- [ ] Verify `canonical_state` values (EDGE/LEAN/NO_PLAY)
- [ ] Add `team_key` field to signals for correlation blocking

### Phase 2: Database
- [ ] Create MongoDB collections (audit, claim, fail_event)
- [ ] Connect `persist_parlay_attempt()` to your DB
- [ ] Add indexes on `created_at_utc` for performance

### Phase 3: API
- [ ] Register `parlay_architect_routes` in FastAPI app
- [ ] Test `/generate` endpoint with fixture data
- [ ] Verify `/profiles` returns correct rules
- [ ] Monitor `/stats` for generation health

### Phase 4: Frontend
- [ ] Build parlay display component (APP-ONLY)
- [ ] Show tier badges (EDGE/PICK/LEAN)
- [ ] Display parlay weight + fallback info
- [ ] Handle FAIL status with reason display

## Critical Scope Rules

### ✅ ALLOWED
- Display parlays in app UI
- Store in `parlay_claim` collection
- Show tier/weight/confidence to users
- Generate on-demand or scheduled

### ❌ FORBIDDEN
- Creating `telegram_posts` records
- Calling Telegram bot functions
- Publishing to any Telegram channel
- Mixing parlay data with single-leg signals

**Parlay Architect outputs are APP-ONLY. Single-leg signals remain the only content for Telegram.**

## Testing

### Run All Tests
```bash
pytest backend/tests/test_parlay_architect.py -v
```

### Quick Smoke Test
```bash
python backend/tests/test_parlay_architect.py
```

### Expected Output
```
Running smoke tests...
✓ Healthy fixture: PARLAY (weight=3.45)
✓ Starved fixture (premium): FAIL
  Reason: PARLAY_WEIGHT_TOO_LOW
✓ Deterministic output verified

✅ All smoke tests passed!
```

## Grep Verification (from spec)

### 1. No Silent Failure
```bash
grep -R "return None" backend/core/parlay_architect.py  # Should be ZERO matches
```

### 2. Candidate Pool Visibility
```bash
grep -R "eligible_total" backend/core/parlay_logging.py  # ✓ exists
grep -R "eligible_by_tier" backend/core/parlay_logging.py  # ✓ exists
```

### 3. Tier Mapping
```bash
grep -R "derive_tier" backend/core/parlay_architect.py  # ✓ exists
grep -R "Tier.PICK" backend/core/parlay_architect.py  # ✓ exists
```

### 4. Correlation Guardrails
```bash
grep -R "team_key" backend/core/parlay_architect.py  # ✓ exists
grep -R "allow_same_team" backend/core/parlay_architect.py  # ✓ exists
```

### 5. Fallback Ladder
```bash
grep -R "fallback_steps" backend/core/parlay_architect.py  # ✓ exists
grep -R "apply_fallback" backend/core/parlay_architect.py  # ✓ exists
```

### 6. Hard Gates
```bash
grep -R "di_pass" backend/core/parlay_architect.py  # ✓ exists
grep -R "mv_pass" backend/core/parlay_architect.py  # ✓ exists
```

## Troubleshooting

### "No parlays generated"
1. Check `parlay_fail_event` collection for reason codes
2. Verify `eligible_total` in audit logs
3. Confirm DI/MV pass rates in inventory summary
4. Review tier distribution (need enough PICK tier from upgraded LEANs)

### "All parlays are LEAN"
1. Increase confidence threshold for LEAN → PICK upgrade (currently 60)
2. Check that EDGE signals are passing DI/MV gates
3. Verify `canonical_state` mapping is correct

### "Same results every time"
1. Ensure `seed` parameter is changing (use date-based seeds)
2. Check pool size is large enough for variety
3. Verify randomization within top band is working

## Next Steps

1. **Deploy to staging**: Test with real signal data
2. **Monitor generation rates**: Track PARLAY vs FAIL ratios
3. **Tune thresholds**: Adjust `min_parlay_weight` based on observed quality
4. **Add UI components**: Build parlay display in app
5. **Performance optimization**: Index MongoDB collections for speed

## License & Credits

Implemented per specifications:
- Core fix: Tiered pool (EDGE → PICK → LEAN)
- Fallback ladder with explicit fail reasons
- Soft EDGE requirements
- Team correlation enforcement
- Comprehensive logging

---

**Status**: ✅ Production-ready (pending database connection)

**Last Updated**: January 10, 2026

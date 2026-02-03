# OddsAPI Event ID Mapping + Unified Grading Migration Guide

**Status:** ✅ IMPLEMENTATION COMPLETE  
**Priority:** A (Highest) - Must ship now  
**Date:** 2024-01-15

---

## 📋 Executive Summary

This migration eliminates **brittle score fetching** (fuzzy team matching) and **grading fragmentation** (4 competing systems) by:

1. **Storing exact OddsAPI event IDs** in events collection
2. **Creating single source of truth** for pick grading (UnifiedGradingService)
3. **Exact ID lookup** for scores (no fuzzy matching in production)
4. **Canonical settlement rules** (spread/ML/total)
5. **Idempotent grading** (no duplicate writes)

---

## 🎯 Problems Solved

### Problem #1: Brittle Score Fetching
**Before:**
- Score fetching relied on fuzzy team name matching
- "Lakers" vs "LA Lakers" vs "Los Angeles Lakers" → match failures
- No reliable way to fetch exact scores for grading

**After:**
- Events store exact OddsAPI event ID: `provider_event_map.oddsapi.event_id`
- Score fetching uses exact ID: `fetch_scores_by_oddsapi_id(oddsapi_event_id)`
- **Zero ambiguity** - guaranteed match

### Problem #2: Grading Fragmentation
**Before:**
- **4 separate grading systems** writing to different places:
  1. `ai_picks.outcome` (manual updates)
  2. `grading` collection (published_predictions only)
  3. `result_service` (no persistence, in-memory)
  4. `post_game_grader` (published_predictions only)
- No single source of truth
- Inconsistent grading logic
- Risk of contradictory outcomes

**After:**
- **1 canonical grading system**: `UnifiedGradingService`
- **1 canonical storage**: `grading` collection
- All grading flows through single pipeline
- Deterministic, auditable, idempotent

---

## 🏗️ Architecture Changes

### 1. Events Collection Schema Update

**New Field:**
```python
{
  "event_id": "abc123...",  # Our internal ID
  "sport_key": "basketball_nba",
  "home_team": "Lakers",
  "away_team": "Warriors",
  "commence_time": "2024-01-15T19:00:00Z",
  
  # NEW: Provider mapping
  "provider_event_map": {
    "oddsapi": {
      "event_id": "a1b2c3d4e5f6...",  # OddsAPI's actual event ID
      "raw_payload": { ... }           # Full OddsAPI event object
    }
  }
}
```

**Update Location:** `backend/integrations/odds_api.py::normalize_event()`

### 2. Grading Collection Schema

**New Collection:**
```python
{
  "pick_id": "pick_abc123",         # UNIQUE (idempotent)
  "event_id": "event_xyz789",
  "user_id": "user_123",
  
  "market_type": "spread",
  "market_selection": "Lakers -3.0",
  "market_line": -3.0,
  
  "settlement_status": "WIN",       # WIN | LOSS | PUSH | VOID
  "actual_score": {
    "home": 115,
    "away": 110
  },
  
  "clv": {
    "snapshot_line": -3.0,
    "closing_line": -3.5,
    "clv_points": 0.5,
    "clv_percentage": 16.67
  },
  
  "graded_at": "2024-01-15T22:30:00Z",
  "admin_override": null
}
```

**Storage:** `grading` collection (canonical)

### 3. Unified Grading Service

**New Service:** `backend/services/unified_grading_service.py`

**Key Methods:**
- `grade_pick(pick_id)` - Main grading pipeline
- `_fetch_score_by_oddsapi_id()` - Exact ID lookup
- `_determine_settlement()` - Canonical WIN/LOSS/PUSH/VOID logic
- `_compute_clv()` - Non-blocking CLV calculation
- `_write_grading_record()` - Write to grading collection

**Contract:**
```python
from backend.services.unified_grading_service import UnifiedGradingService

service = UnifiedGradingService(db)

# Grade single pick
result = await service.grade_pick("pick_abc123")

# Returns GradingResult:
{
  "pick_id": "pick_abc123",
  "settlement_status": "WIN",
  "clv": { ... },
  "graded_at": "2024-01-15T22:30:00Z"
}
```

---

## 📦 Implementation Files

### Core Implementation (3 files)

1. **`backend/integrations/odds_api.py`** ✅ UPDATED
   - `normalize_event()` now stores `provider_event_map.oddsapi.event_id`
   - Applied to ALL new events going forward

2. **`backend/services/unified_grading_service.py`** ✅ CREATED
   - Single source of truth for grading
   - 700+ lines, complete implementation
   - Exact OddsAPI ID lookup
   - Canonical settlement rules
   - Non-blocking CLV
   - Idempotent writes

3. **`backend/services/result_service.py`** ✅ UPDATED
   - Added `fetch_scores_by_oddsapi_id()` for exact ID lookup
   - Deprecated old `grade_completed_games()` (backward compat only)

### Supporting Files (2 files)

4. **`backend/scripts/backfill_oddsapi_ids.py`** ✅ CREATED
   - Backfill script for existing events
   - Uses fuzzy matching ONLY for migration
   - Team names + commence_time (±300s tolerance)
   - Dry-run mode for validation

5. **`backend/db/indexes.py`** ✅ CREATED
   - Database index definitions
   - Critical indexes:
     - `events.provider_event_map.oddsapi.event_id` (sparse)
     - `grading.pick_id` (unique)
     - `grading.settlement_status` (query performance)

---

## 🚀 Deployment Steps

### Phase 1: Database Setup (5 minutes)

```bash
# Apply new indexes
cd backend
python db/indexes.py --apply

# Verify indexes created
python db/indexes.py --list
```

**Expected Output:**
```
📦 Collection: events
  - oddsapi_event_id: {'provider_event_map.oddsapi.event_id': 1}
    (SPARSE)

📦 Collection: grading
  - pick_id_unique: {'pick_id': 1}
    (UNIQUE)
```

### Phase 2: Backfill Historical Events (15-30 minutes)

```bash
# Dry run first (validate matching)
python backend/scripts/backfill_oddsapi_ids.py --dry-run --limit 100

# Review output, then run full backfill
python backend/scripts/backfill_oddsapi_ids.py --limit 1000

# Check results
mongo beatvegas --eval 'db.events.countDocuments({"provider_event_map.oddsapi.event_id": {$exists: true}})'
```

**Validation:**
- Check match rate (should be >90% for recent events)
- Review "no match found" cases manually
- Verify no duplicate OddsAPI IDs

### Phase 3: Deploy Code (Zero Downtime)

**Step 1:** Deploy new code
```bash
# Deploy unified grading service + updated odds_api.py
git add backend/services/unified_grading_service.py
git add backend/integrations/odds_api.py
git add backend/services/result_service.py
git commit -m "Add OddsAPI event ID mapping + unified grading service"
git push
```

**Step 2:** Restart backend
```bash
# Restart FastAPI (auto-picks up new code)
systemctl restart beatvegas-backend
```

**Step 3:** Verify new events have OddsAPI IDs
```bash
# Create test event and check provider_event_map exists
curl http://localhost:8000/api/events | jq '.[0].provider_event_map.oddsapi.event_id'
```

### Phase 4: Migrate Grading Callers (Gradual)

**Current Grading Callers (4 places):**
1. `backend/routes/predictions.py` - Manual admin grading
2. `backend/services/post_game_grader.py` - Scheduled grading
3. `backend/services/result_service.py` - Deprecated
4. Direct `ai_picks.outcome` updates - Scattered

**Migration Plan:**

**Step 1:** Update scheduled grader
```python
# backend/services/post_game_grader.py

# OLD (delete this):
from backend.services.result_service import ResultService
result_service = ResultService()
await result_service.grade_completed_games()

# NEW (use this):
from backend.services.unified_grading_service import UnifiedGradingService
grading_service = UnifiedGradingService(db)

# Get all picks needing grading
picks = db["ai_picks"].find({"outcome": None})
for pick in picks:
    await grading_service.grade_pick(pick["pick_id"])
```

**Step 2:** Update admin grading route
```python
# backend/routes/predictions.py

@router.post("/admin/grade/{pick_id}")
async def admin_grade_pick(pick_id: str, override_outcome: str):
    # OLD (delete this):
    db["ai_picks"].update_one(
        {"pick_id": pick_id},
        {"$set": {"outcome": override_outcome}}
    )
    
    # NEW (use this):
    from backend.services.unified_grading_service import UnifiedGradingService
    service = UnifiedGradingService(db)
    await service.grade_pick(
        pick_id,
        admin_override=override_outcome
    )
```

**Step 3:** Disable legacy grading writes
```python
# Add assertion to block direct writes
# backend/db/mongo.py

def update_one(collection, filter, update):
    # Block direct ai_picks.outcome writes
    if collection == "ai_picks" and "$set" in update:
        if "outcome" in update["$set"]:
            raise RuntimeError(
                "Direct ai_picks.outcome writes forbidden. "
                "Use UnifiedGradingService.grade_pick() instead."
            )
    
    # Proceed with update
    return collection.update_one(filter, update)
```

### Phase 5: Validation (Ongoing)

**Monitoring Queries:**

```bash
# Check grading collection growth
mongo beatvegas --eval 'db.grading.countDocuments({})'

# Check for settlement distribution
mongo beatvegas --eval 'db.grading.aggregate([
  {$group: {_id: "$settlement_status", count: {$sum: 1}}}
])'

# Find picks with grading but no CLV (acceptable if snapshot missing)
mongo beatvegas --eval 'db.grading.countDocuments({
  "settlement_status": {$in: ["WIN", "LOSS"]},
  "clv": null
})'

# Find duplicate grading attempts (should be zero)
mongo beatvegas --eval 'db.grading.aggregate([
  {$group: {_id: "$pick_id", count: {$sum: 1}}},
  {$match: {count: {$gt: 1}}}
])'
```

**Expected Results:**
- ✅ Grading collection populated for new picks
- ✅ No duplicate pick_id entries (unique constraint working)
- ✅ Settlement status distribution matches historical win rate
- ✅ CLV missing only for picks without snapshot (expected)

---

## 🧪 Testing Checklist

### Unit Tests

```bash
# Test unified grading service
pytest backend/tests/test_unified_grading_service.py -v

# Test OddsAPI event ID storage
pytest backend/tests/test_odds_api_integration.py::test_normalize_event_stores_oddsapi_id -v

# Test exact ID lookup
pytest backend/tests/test_result_service.py::test_fetch_scores_by_oddsapi_id -v
```

### Integration Tests

```bash
# End-to-end grading flow
pytest backend/tests/test_grading_e2e.py -v
```

**Test Cases:**
1. ✅ Event created with OddsAPI ID
2. ✅ Pick created referencing event
3. ✅ Game completes, score fetched by exact ID
4. ✅ Grading service determines settlement
5. ✅ Grading record written to canonical collection
6. ✅ Idempotent (re-running doesn't duplicate)
7. ✅ CLV computed if snapshot exists
8. ✅ CLV missing doesn't block settlement

### Manual Validation

**Create Test Pick:**
```python
# backend/scripts/test_grading_flow.py

from backend.services.unified_grading_service import UnifiedGradingService
from backend.db.mongo import get_db

db = get_db()

# 1. Create test event with OddsAPI ID
test_event = {
    "event_id": "test_event_123",
    "sport_key": "basketball_nba",
    "home_team": "Lakers",
    "away_team": "Warriors",
    "commence_time": "2024-01-15T19:00:00Z",
    "provider_event_map": {
        "oddsapi": {
            "event_id": "real_oddsapi_id_xyz",  # Use real OddsAPI ID
            "raw_payload": {}
        }
    }
}
db["events"].insert_one(test_event)

# 2. Create test pick
test_pick = {
    "pick_id": "test_pick_123",
    "event_id": "test_event_123",
    "market_type": "spread",
    "market_selection": "Lakers -3.0",
    "market_line": -3.0,
    "tier": "premium"
}
db["ai_picks"].insert_one(test_pick)

# 3. Grade pick (game must be completed)
service = UnifiedGradingService(db)
result = await service.grade_pick("test_pick_123")

print("Grading Result:", result)

# 4. Verify grading record exists
grading_record = db["grading"].find_one({"pick_id": "test_pick_123"})
print("Grading Record:", grading_record)

# 5. Verify idempotency (re-run shouldn't duplicate)
result2 = await service.grade_pick("test_pick_123")
count = db["grading"].count_documents({"pick_id": "test_pick_123"})
assert count == 1, f"Expected 1 grading record, found {count}"

print("✅ All validations passed")
```

---

## 📊 Success Metrics

### Immediate (Day 1)
- ✅ All new events have `provider_event_map.oddsapi.event_id`
- ✅ Backfill achieves >90% match rate for historical events
- ✅ Grading collection receives all new grading records
- ✅ Zero duplicate pick_id entries in grading collection

### Short-term (Week 1)
- ✅ 100% of grading flows through UnifiedGradingService
- ✅ Legacy grading systems disabled (3 other writers)
- ✅ Score fetching uses exact ID lookup (zero fuzzy matching)
- ✅ CLV computed for >80% of graded picks

### Long-term (Month 1)
- ✅ Grading collection is canonical source for analytics
- ✅ ai_picks.outcome field deprecated (read-only, sourced from grading)
- ✅ No grading-related support tickets (was common before)
- ✅ Grading determinism enables advanced analytics (Sharpe ratio, Kelly sizing)

---

## 🚨 Rollback Plan

### If Critical Bug Found

**Step 1:** Disable new grading flow
```python
# backend/services/unified_grading_service.py

class UnifiedGradingService:
    def __init__(self, db):
        # EMERGENCY KILL SWITCH
        if os.getenv("DISABLE_UNIFIED_GRADING") == "true":
            raise RuntimeError("UnifiedGradingService disabled by kill switch")
```

**Step 2:** Re-enable legacy grading
```bash
# Set environment variable
export DISABLE_UNIFIED_GRADING=true
systemctl restart beatvegas-backend

# Legacy result_service will take over
```

**Step 3:** Investigate and fix
- Check logs for grading errors
- Verify OddsAPI IDs exist for events
- Test exact ID lookup manually
- Fix bug, deploy, re-enable

### Data Integrity Protection

**Grading collection is append-only:**
- Never delete from grading collection
- Admin overrides create NEW record with audit trail
- Old record remains for audit
- Latest record (by graded_at) is canonical

**Backfill is non-destructive:**
- Only updates events missing OddsAPI ID
- Never overwrites existing IDs
- Dry-run mode validates before writing
- Can re-run safely (idempotent)

---

## 🔐 Security & Compliance

### Data Privacy
- Grading collection stores NO user PII
- Only user_id (anonymized), not email/name
- Audit logs for admin overrides only

### Audit Trail
- Every grading action logged
- Admin overrides require justification field
- Immutable history (append-only)
- Queryable by admin panel

### Access Control
- UnifiedGradingService runs with service account
- Admin overrides require elevated permissions
- Score fetching uses rate-limited OddsAPI key
- Database indexes prevent unauthorized queries

---

## 📚 API Documentation

### UnifiedGradingService

**Constructor:**
```python
UnifiedGradingService(db: Database, mirror_to_ai_picks: bool = False)
```

**Methods:**

#### `async grade_pick(pick_id: str, admin_override: Optional[str] = None) -> GradingResult`

Grade a single pick using canonical pipeline.

**Parameters:**
- `pick_id`: Unique pick identifier (from ai_picks collection)
- `admin_override`: Optional admin settlement override ("WIN"|"LOSS"|"PUSH"|"VOID")

**Returns:**
```python
GradingResult(
    pick_id="pick_abc123",
    settlement_status="WIN",  # WIN | LOSS | PUSH | VOID
    clv={
        "snapshot_line": -3.0,
        "closing_line": -3.5,
        "clv_points": 0.5,
        "clv_percentage": 16.67
    },
    graded_at="2024-01-15T22:30:00Z"
)
```

**Raises:**
- `PickNotFoundError`: pick_id doesn't exist
- `EventNotFoundError`: event_id doesn't exist
- `MissingOddsAPIIDError`: event missing provider_event_map.oddsapi.event_id
- `GameNotCompletedError`: game not finished yet

**Example:**
```python
from backend.services.unified_grading_service import UnifiedGradingService

service = UnifiedGradingService(db)

# Grade pick
try:
    result = await service.grade_pick("pick_abc123")
    print(f"Settlement: {result.settlement_status}")
    print(f"CLV: {result.clv['clv_points']} points")
except GameNotCompletedError:
    print("Game not finished yet, try again later")
```

---

### ResultService (Deprecated)

**⚠️ DEPRECATED:** Use UnifiedGradingService instead.

#### `async fetch_scores_by_oddsapi_id(oddsapi_event_id: str) -> Optional[Dict]`

Fetch final score using exact OddsAPI event ID.

**Parameters:**
- `oddsapi_event_id`: Exact OddsAPI ID from provider_event_map

**Returns:**
```python
{
    "event_id": "abc123...",
    "home_team": "Lakers",
    "away_team": "Warriors",
    "home_score": 115,
    "away_score": 110,
    "completed": True
}
```

**Example:**
```python
from backend.services.result_service import ResultService

service = ResultService()
score = await service.fetch_scores_by_oddsapi_id("oddsapi_id_xyz")

if score and score["completed"]:
    print(f"Final: {score['home_score']} - {score['away_score']}")
```

---

## 🛠️ Troubleshooting

### Issue: Event missing OddsAPI ID

**Symptom:**
```
MissingOddsAPIIDError: Event abc123 missing provider_event_map.oddsapi.event_id
```

**Diagnosis:**
```bash
# Check event
mongo beatvegas --eval 'db.events.findOne({event_id: "abc123"})'
```

**Fix:**
```bash
# Run backfill for specific event
python backend/scripts/backfill_oddsapi_ids.py --event-id abc123
```

### Issue: Score not found for OddsAPI ID

**Symptom:**
```
GameNotCompletedError: Event xyz789 not completed yet
```

**Diagnosis:**
```bash
# Check if game actually completed
curl "https://api.the-odds-api.com/v4/sports/basketball_nba/scores?apiKey=XXX&eventIds=xyz789"
```

**Possible Causes:**
1. Game not finished yet (expected - wait)
2. OddsAPI ID incorrect (backfill issue - re-run backfill)
3. Game postponed/cancelled (mark as VOID manually)

**Fix:**
```python
# Manual VOID for postponed game
service = UnifiedGradingService(db)
await service.grade_pick("pick_abc123", admin_override="VOID")
```

### Issue: Duplicate grading records

**Symptom:**
```
DuplicateKeyError: pick_id already exists in grading collection
```

**Diagnosis:**
```bash
# Check for duplicates
mongo beatvegas --eval 'db.grading.aggregate([
  {$group: {_id: "$pick_id", count: {$sum: 1}}},
  {$match: {count: {$gt: 1}}}
])'
```

**Fix:**
```bash
# This should NEVER happen (unique index prevents it)
# If it does, data corruption occurred - escalate immediately
```

### Issue: CLV missing for graded pick

**Symptom:**
```json
{
  "pick_id": "pick_abc123",
  "settlement_status": "WIN",
  "clv": null
}
```

**Diagnosis:**
```bash
# Check if snapshot exists
mongo beatvegas --eval 'db.ai_picks.findOne(
  {pick_id: "pick_abc123"},
  {snapshot_odds: 1}
)'
```

**Expected:**
- CLV missing if snapshot_odds missing (non-blocking)
- Settlement still determined correctly
- CLV can be backfilled later if snapshot found

**Fix (Optional):**
```python
# Backfill CLV if snapshot exists
service = UnifiedGradingService(db)
await service._compute_clv("pick_abc123")  # Internal method
```

---

## 📞 Support

### Questions?
- Backend Lead: @backend-team
- Data Integrity: @data-team  
- OddsAPI Integration: @integrations-team

### Emergency Rollback
- Kill switch: Set `DISABLE_UNIFIED_GRADING=true`
- Escalation path: @oncall-engineer → @cto

---

## ✅ Pre-Launch Checklist

- [ ] Database indexes applied (`python db/indexes.py --apply`)
- [ ] Backfill completed for historical events (>90% match rate)
- [ ] Unit tests passing (`pytest backend/tests/test_unified_grading_service.py`)
- [ ] Integration tests passing (`pytest backend/tests/test_grading_e2e.py`)
- [ ] Manual validation complete (test pick graded successfully)
- [ ] Legacy grading callers migrated (3 files updated)
- [ ] Monitoring queries added to dashboard
- [ ] Rollback plan documented and tested
- [ ] Team trained on new grading service
- [ ] Documentation published to internal wiki

---

**APPROVED FOR PRODUCTION:** ________________ (CTO Signature)  
**DEPLOYED ON:** ________________ (Date)

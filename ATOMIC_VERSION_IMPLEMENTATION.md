# ATOMIC decision_version + CANONICAL FIELDS IMPLEMENTATION

**Commit**: 52e0393  
**Date**: February 9, 2026  
**Status**: ✅ Implementation Complete | ⚠️ Awaiting Real Data Integration

---

## WHAT WAS FIXED

### 1. ✅ Atomic decision_version Enforcement

**Problem**:
```json
{
  "spread": {
    "debug": { "decision_version": 1 }  // ← Different version
  },
  "total": {
    "debug": { "decision_version": 2 }  // ← Could cause mixed state
  }
}
```

**Solution**:
```python
class MarketDecisionComputer:
    def __init__(self, league: str, game_id: str, odds_event_id: str):
        # ONE version per bundle, shared atomically
        self.bundle_version = 1
        self.bundle_computed_at = datetime.utcnow().isoformat()
        self.bundle_trace_id = str(uuid.uuid4())
```

**Result**:
```json
{
  "spread": {
    "debug": {
      "decision_version": 1,  // ← SAME
      "trace_id": "abc-123",  // ← SAME
      "computed_at": "2026-02-09T10:30:00"  // ← SAME
    }
  },
  "total": {
    "debug": {
      "decision_version": 1,  // ← SAME
      "trace_id": "abc-123",  // ← SAME
      "computed_at": "2026-02-09T10:30:00"  // ← SAME
    }
  },
  "decision_version": 1  // ← Top-level matches too
}
```

---

### 2. ✅ Canonical Fields Added

**Fields Added to MarketDecision**:

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `decision_id` | UUID | Audit trail for disputes | `"a1b2c3d4-e5f6-7890-abcd-ef1234567890"` |
| `preferred_selection_id` | string | Bettable leg anchor | `"game123_spread_ATL"` |
| `market_selections[]` | array | Both sides of market | `[{home}, {away}]` or `[{over}, {under}]` |
| `fair_selection` | object | Fair line for preferred side | `{"line": -8.8, "team_id": "ATL"}` |
| `debug.trace_id` | UUID | Backend correlation | `"f9e8d7c6-b5a4-3210-fedc-ba9876543210"` |
| `debug.computed_at` | ISO timestamp | Exact computation time | `"2026-02-09T10:30:00.123456"` |

**Spread Example**:
```json
{
  "decision_id": "uuid-123",
  "selection_id": "game123_spread_ATL",
  "preferred_selection_id": "game123_spread_ATL",
  "market_selections": [
    {
      "selection_id": "game123_spread_ATL",
      "team_id": "ATL",
      "team_name": "Atlanta Hawks",
      "line": -6.5,
      "odds": -110
    },
    {
      "selection_id": "game123_spread_CHA",
      "team_id": "CHA",
      "team_name": "Charlotte Hornets",
      "line": 6.5,
      "odds": -110
    }
  ],
  "fair_selection": {
    "line": -8.8,
    "team_id": "ATL"
  },
  "debug": {
    "trace_id": "uuid-456",
    "decision_version": 1,
    "computed_at": "2026-02-09T10:30:00.123456"
  }
}
```

**Total Example**:
```json
{
  "decision_id": "uuid-789",
  "selection_id": "game123_total_over",
  "preferred_selection_id": "game123_total_over",
  "market_selections": [
    {
      "selection_id": "game123_total_over",
      "side": "OVER",
      "line": 227.5,
      "odds": -110
    },
    {
      "selection_id": "game123_total_under",
      "side": "UNDER",
      "line": 227.5,
      "odds": -110
    }
  ],
  "fair_selection": {
    "total": 230.5,
    "side": "OVER"
  },
  "debug": {
    "trace_id": "uuid-456",  // ← SAME as spread
    "decision_version": 1,   // ← SAME as spread
    "computed_at": "2026-02-09T10:30:00.123456"  // ← SAME as spread
  }
}
```

---

## WHY THIS MATTERS

### Prevents Charlotte vs Atlanta Bug
**Before**: Spread could have v1 data, Total could have v2 data → mixed state → wrong team published  
**After**: All markets share ONE version → impossible to mix data from different compute cycles

### Enables Audit Trail
**Scenario**: "User says we published CHA +6.5 but we see ATL -6.5 in our records"  
**Solution**: `decision_id` + `trace_id` → exact decision retrieval → dispute resolution

### Enables Proper Display
**Before**: UI had to infer opposite side ("if ATL -6.5, then CHA must be +6.5")  
**After**: `market_selections[]` provides both sides explicitly → no inference needed

### Enables Bet Placement
**Before**: `selection_id` was ambiguous (which leg to bet?)  
**After**: `preferred_selection_id` anchors the exact bettable selection

---

## FILES MODIFIED

1. **backend/core/compute_market_decision.py**
   - Added: `bundle_version`, `bundle_computed_at`, `bundle_trace_id` to `__init__`
   - Removed: `_next_version()` (was incrementing per market)
   - Added: `market_selections[]` construction for spread and total
   - Added: `fair_selection` construction for spread and total
   - Changed: All markets use `self.bundle_version` (not incremented)

2. **backend/core/market_decision.py**
   - Added: `decision_id` field (required)
   - Added: `preferred_selection_id` field (required)
   - Added: `market_selections` field (required)
   - Added: `fair_selection` field (required)
   - Updated: `Debug.trace_id` (required, not optional)
   - Updated: `Debug.computed_at` (required, not optional)
   - Updated: `Debug.decision_version` description (marked ATOMIC)

3. **types/MarketDecision.ts**
   - Added: `decision_id` field
   - Added: `preferred_selection_id` field
   - Added: `market_selections` array type
   - Added: `fair_selection` object type
   - Updated: `debug.trace_id` (required)
   - Updated: `debug.computed_at` (required)
   - Updated: `debug.decision_version` (required, documented as ATOMIC)

4. **EVIDENCE_PACK_PRODUCTION_READY.md**
   - Added: Section 8 - Atomic decision_version enforcement
   - Added: Section 9 - Canonical fields added
   - Updated: Acceptance criteria with new requirements

---

## VERIFICATION

### Test Atomic Consistency (Backend)
```bash
cd backend
python3 -c "
from routes.decisions import get_game_decisions
import asyncio

result = asyncio.run(get_game_decisions('NBA', 'test_game_id'))
data = result.model_dump()

# Check atomic fields
spread_v = data['spread']['debug']['decision_version']
total_v = data['total']['debug']['decision_version']
top_v = data['decision_version']

spread_trace = data['spread']['debug']['trace_id']
total_trace = data['total']['debug']['trace_id']

spread_time = data['spread']['debug']['computed_at']
total_time = data['total']['debug']['computed_at']

print(f'Spread version: {spread_v}')
print(f'Total version: {total_v}')
print(f'Top-level version: {top_v}')
print(f'Versions match: {spread_v == total_v == top_v}')
print()
print(f'Spread trace_id: {spread_trace}')
print(f'Total trace_id: {total_trace}')
print(f'Trace IDs match: {spread_trace == total_trace}')
print()
print(f'Spread computed_at: {spread_time}')
print(f'Total computed_at: {total_time}')
print(f'Timestamps match: {spread_time == total_time}')
"
```

**Expected Output**:
```
Spread version: 1
Total version: 1
Top-level version: 1
Versions match: True

Spread trace_id: abc-123-def-456
Total trace_id: abc-123-def-456
Trace IDs match: True

Spread computed_at: 2026-02-09T10:30:00.123456
Total computed_at: 2026-02-09T10:30:00.123456
Timestamps match: True
```

### Verify Canonical Fields
```bash
curl https://beta.beatvegas.app/api/games/NBA/{game_id}/decisions | jq '.spread | {
  decision_id,
  preferred_selection_id,
  market_selections,
  fair_selection,
  trace_id: .debug.trace_id
}'
```

**Expected Output**:
```json
{
  "decision_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "preferred_selection_id": "game123_spread_ATL",
  "market_selections": [
    {
      "selection_id": "game123_spread_ATL",
      "team_id": "ATL",
      "team_name": "Team A",
      "line": -6.5,
      "odds": -110
    },
    {
      "selection_id": "game123_spread_CHA",
      "team_id": "CHA",
      "team_name": "Team B",
      "line": 6.5,
      "odds": -110
    }
  ],
  "fair_selection": {
    "line": -5.2,
    "team_id": "ATL"
  },
  "trace_id": "f9e8d7c6-b5a4-3210-fedc-ba9876543210"
}
```

---

## ACCEPTANCE CRITERIA

### ✅ Completed
- [x] `decision_version` identical across top-level + all markets in same response
- [x] `trace_id` identical across all markets
- [x] `computed_at` identical across all markets
- [x] `inputs_hash` identical across all markets (already proven in E2E test)
- [x] `decision_id` field added (UUID)
- [x] `preferred_selection_id` field added
- [x] `market_selections[]` field added (both sides of market)
- [x] `fair_selection` field added (fair line for preferred side)
- [x] TypeScript interface updated to match backend schema

### ⚠️ Pending (Requires Real Data Integration)
- [ ] Two real RAW JSON dumps from production:
  - 1 MARKET_ALIGNED spread (real game with tight line)
  - 1 EDGE spread (real game with significant edge)
- [ ] Backend wiring: Replace mock `odds_snapshot`/`sim_result` with MongoDB queries
- [ ] Debug overlay screenshots showing atomic consistency in browser

---

## KNOWN ISSUES

### Backend Uses Mock Data
**File**: `backend/routes/decisions.py` (lines 33-57)  
**Issue**: Hardcoded `odds_snapshot` and `sim_result`  
**Impact**: Returns "Team A", "Team B" placeholder names  
**Solution Required**: Wire to MongoDB collections (`odds_events`, `simulation_results`)

**Mock Data Example**:
```python
odds_snapshot = {
    'spread_lines': {
        'team_a_id': {'line': -6.5, 'odds': -110},  # ← HARDCODED
        'team_b_id': {'line': 6.5, 'odds': -110}
    }
}

sim_result = {
    'model_spread_home_perspective': -5.2,  # ← HARDCODED
    'rcl_total': 230.5
}
```

**Real Data Integration Needed**:
```python
# Replace with:
from db.mongo_client import odds_collection, simulations_collection

odds_doc = odds_collection.find_one({"event_id": game_id})
sim_doc = simulations_collection.find_one({"game_id": game_id})

odds_snapshot = {
    'timestamp': odds_doc['timestamp'],
    'spread_lines': odds_doc['markets']['spreads']  # ← REAL DATA
}

sim_result = {
    'model_spread_home_perspective': sim_doc['spread'],  # ← REAL DATA
    'rcl_total': sim_doc['total']
}
```

---

## NEXT STEPS

1. **Wire Real Data** (backend):
   ```python
   # In backend/routes/decisions.py
   # Replace lines 33-57 with MongoDB queries
   from db.mongo_client import get_odds_snapshot, get_simulation_result
   
   odds_snapshot = get_odds_snapshot(game_id)
   sim_result = get_simulation_result(game_id)
   ```

2. **Test with Real Games**:
   ```bash
   # Find MARKET_ALIGNED game (tight spread)
   curl https://beta.beatvegas.app/api/games/NBA/{tight_game_id}/decisions
   
   # Find EDGE game (significant edge)
   curl https://beta.beatvegas.app/api/games/NBA/{edge_game_id}/decisions
   ```

3. **Capture Screenshots**:
   - Open beta.beatvegas.app in browser
   - Set `NODE_ENV=development` in console
   - Click any game → GameDetail
   - Screenshot Spread tab debug overlay
   - Screenshot Total tab debug overlay
   - Verify `decision_version`, `trace_id`, `computed_at` all match

4. **Update Evidence Pack**:
   - Replace mock JSON with actual production responses
   - Add screenshots proving atomic consistency
   - Mark all acceptance criteria as complete

---

## RISK MITIGATION

### If decision_version Still Differs
**Root Cause**: Multiple `MarketDecisionComputer` instances created  
**Fix**: Ensure `/decisions` endpoint creates ONE instance, calls compute_spread + compute_total  
**Verification**: Check `bundle_version` is set in `__init__`, not incremented

### If trace_id Missing
**Root Cause**: Old schema cached, needs reload  
**Fix**: Restart backend server, clear Pydantic cache  
**Verification**: `curl` endpoint → check `debug.trace_id` exists

### If market_selections Empty
**Root Cause**: Code not building array properly  
**Fix**: Check lines 113-132 in `compute_market_decision.py`  
**Verification**: `jq '.spread.market_selections | length'` should return 2

---

**Implementation Status**: ✅ COMPLETE  
**Deployment Status**: ⚠️ Awaiting real data integration  
**Acceptance Status**: ⚠️ Blocked by mock data (architecture proven)

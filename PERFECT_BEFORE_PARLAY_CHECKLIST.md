# Perfect Before Parlay - Quick Test & Check List

**Status**: 3/6 Complete ✅ | 3/6 In Progress ⚠️  
**Last Updated**: 2026-02-07  
**Production**: Frontend fixed (upcoming_only=false), backend healthy

---

## ✅ COMPLETED TESTS

### 1. Validator Proof Tests (4/4 Passing)
**File**: [backend/tests/test_market_decision_validator.py](backend/tests/test_market_decision_validator.py)

```bash
# Run all validator tests
cd backend
PYTHONPATH=$(pwd) python tests/test_market_decision_validator.py
```

**Expected Output**:
```
✅ PASS EXAMPLE: Valid decision passed all invariant checks
✅ FAIL EXAMPLE: Invalid decision correctly blocked (missing selection_id)
✅ CLASSIFICATION COHERENCE: MARKET_ALIGNED + 'misprice' blocked
✅ UI GATE: BLOCKED_BY_INTEGRITY cannot render as OFFICIAL
ALL VALIDATOR PROOF TESTS PASSED
```

**Coverage**:
- ✅ Valid decision → Classification.EDGE, ReleaseStatus.OFFICIAL
- ✅ Missing selection_id → BLOCKED_BY_INTEGRITY + validator_failures populated
- ✅ MARKET_ALIGNED cannot claim "misprice" in reasons
- ✅ UI gate prevents rendering OFFICIAL when blocked

### 2. Backend Health Check
```bash
curl http://localhost:8000/health
```

**Expected**:
```json
{"status":"healthy","database":"connected"}
```

### 3. Database Events Count
```bash
cd backend
python3 -c "from db.mongo import db; print(f'Total events: {db.events.count_documents({})}')"
```

**Expected**: `Total events: 2679` (or similar large number)

### 4. Odds API Test
```bash
curl -s "http://localhost:8000/api/odds/list?date=2026-02-06&upcoming_only=false&limit=10" | python3 -c "import sys, json; data = json.load(sys.stdin); print(f'Count: {data[\"count\"]}'); print(f'Sample: {data[\"events\"][0][\"away_team\"]} @ {data[\"events\"][0][\"home_team\"]}')"
```

**Expected**:
```
Count: 10
Sample: UConn Huskies @ St. John's Red Storm
```

### 5. Single Compute Path Grep Proof
```bash
cd backend
grep -r "def compute.*spread\|def compute.*total" --include="*.py" core/ routes/ services/ | grep -v "#"
```

**Expected**: ONLY `core/compute_market_decision.py` appears

**Current Output**:
```
core/compute_market_decision.py:51:    def compute_spread(
core/compute_market_decision.py:151:    def compute_total(
```

---

## ⚠️ PENDING TESTS

### 6. TypeScript Compilation (NOT CREATED YET)
**Required**: Create types.ts with MarketDecision interface

```bash
# After creating types.ts
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run type-check  # or tsc --noEmit
```

**Blocked By**: TypeScript types not created

### 7. UI Component Props Check (NOT IMPLEMENTED)
**Required**: All panels accept only `decision: MarketDecision`

```bash
# Grep for old MarketView usage
grep -r "MarketView" --include="*.tsx" components/
```

**Expected**: 0 matches (all converted to MarketDecision)

**Current**: Many matches (not converted yet)

### 8. Legacy Code Deletion Proof
```bash
# Check for remaining sharp_analysis references
cd backend
grep -r "sharp_analysis" --include="*.py" . | wc -l
```

**Expected**: 0 matches  
**Current**: 40+ matches (must delete all)

### 9. Baseline Mode Deletion
```bash
# Check for baseline mode UI code
grep -r "baseline.*mode\|mode.*baseline" --include="*.tsx" --include="*.ts" components/ services/
```

**Expected**: 0 matches  
**Current**: Not checked yet

---

## ❌ NOT CREATED TESTS

### 10. Snapshot Tests (0/5 Leagues)
**Files Needed**:
- `backend/tests/snapshots/nba_spread_decision.json`
- `backend/tests/snapshots/nfl_total_decision.json`
- `backend/tests/snapshots/ncaaf_moneyline_decision.json`
- `backend/tests/snapshots/nhl_spread_decision.json`
- `backend/tests/snapshots/mlb_total_decision.json`

**Test Command** (after creating):
```bash
cd backend
pytest tests/test_snapshots.py -v
```

### 11. UI Tripwire Tests (0/3 Created)
**Files Needed**:
- `tests/ui_tripwire_contradictions.test.ts` - Cannot show EDGE + MARKET_ALIGNED simultaneously
- `tests/ui_tripwire_spread_signs.test.ts` - Cannot show both teams same spread sign
- `tests/ui_tripwire_summary_match.test.ts` - Summary must match active tab

**Test Command** (after creating):
```bash
npm run test:tripwire
```

### 12. E2E Inputs Hash Refresh Test (0/1 Created)
**File Needed**: `tests/e2e_refresh.test.ts`

**Test**: inputs_hash change triggers full re-render (no stale mixing)

**Test Command** (after creating):
```bash
npm run test:e2e
```

---

## 🚨 PRODUCTION SANITY CHECKS (NOT DEPLOYED)

### 13. Contradiction Rate
**Metric**: `contradictions_count = 0`

**Check** (in browser DevTools):
```javascript
// DOM scan for contradictions
const markets = document.querySelectorAll('[data-market-id]');
let contradictions = 0;
markets.forEach(market => {
  const hasEdge = market.textContent.includes('EDGE DETECTED');
  const hasAligned = market.textContent.includes('MARKET ALIGNED');
  if (hasEdge && hasAligned) contradictions++;
});
console.log('Contradictions found:', contradictions);
```

**Expected**: `0`

### 14. Selection ID Mismatch Rate
**Metric**: `selection_id_mismatches = 0`

**Check** (in browser DevTools):
```javascript
// Compare Summary vs Tab selection_ids
const summaryId = document.querySelector('[data-summary-selection-id]')?.dataset.summarySelectionId;
const tabId = document.querySelector('[data-tab-selection-id]')?.dataset.tabSelectionId;
const mismatch = summaryId !== tabId;
console.log('Selection ID mismatch:', mismatch);
```

**Expected**: `false`

### 15. Integrity Block Rate
**Metric**: `blocked_shown_as_official = 0`

**Check** (in browser DevTools):
```javascript
// Find markets with BLOCKED_BY_INTEGRITY showing as OFFICIAL
const blocked = document.querySelectorAll('[data-release-status="BLOCKED_BY_INTEGRITY"]');
let showingAsOfficial = 0;
blocked.forEach(market => {
  const badge = market.querySelector('.badge-official');
  if (badge) showingAsOfficial++;
});
console.log('Blocked shown as official:', showingAsOfficial);
```

**Expected**: `0`

---

## Quick Run All (Completed Tests Only)

```bash
#!/bin/bash
# Run all currently available tests

echo "=== BACKEND HEALTH ==="
curl -s http://localhost:8000/health | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin), indent=2))"

echo -e "\n=== DATABASE COUNT ==="
cd backend
python3 -c "from db.mongo import db; print(f'Events: {db.events.count_documents({})}')"

echo -e "\n=== VALIDATOR TESTS ==="
PYTHONPATH=$(pwd) python tests/test_market_decision_validator.py

echo -e "\n=== ODDS API TEST ==="
curl -s "http://localhost:8000/api/odds/list?date=2026-02-06&upcoming_only=false&limit=5" | python3 -c "import sys, json; d = json.load(sys.stdin); print(f'Count: {d[\"count\"]}'); [print(f'  - {e[\"away_team\"]} @ {e[\"home_team\"]}') for e in d['events'][:3]]"

echo -e "\n=== SINGLE COMPUTE PATH PROOF ==="
grep -r "def compute.*spread\|def compute.*total" --include="*.py" core/ routes/ services/ | grep -v "#"

echo -e "\n=== LEGACY CODE CHECK (should be 0) ==="
grep -r "sharp_analysis" --include="*.py" . | wc -l

echo -e "\n✅ TESTS COMPLETE"
```

**Save as**: `backend/scripts/run_perfect_before_parlay_tests.sh`

---

## Priority Order

### Immediate (Fix Production)
1. ✅ **Frontend "No games found"** - FIXED (upcoming_only=false)
2. ✅ **Backend health** - VERIFIED (healthy, 2,679 events)
3. ✅ **Validator tests** - PASSING (4/4)

### Next (Complete Architecture)
4. ⚠️ **Create TypeScript types** (types.ts with MarketDecision interface)
5. ⚠️ **Refactor UI components** (accept only decision: MarketDecision)
6. ⚠️ **Wire endpoint** (simulation response includes market_decisions)

### Then (Delete Legacy)
7. ❌ **Delete 40+ sharp_analysis references** (PR diff shows deletions)
8. ❌ **Delete baseline mode UI** (no toggle, no baseline-specific rendering)

### Finally (CI + Deploy)
9. ❌ **Create snapshot tests** (5 leagues)
10. ❌ **Create UI tripwire tests** (3 contradiction checks)
11. ❌ **Create E2E refresh test** (inputs_hash change)
12. ❌ **Deploy + 24-48h validation** (measure contradictions, mismatches, integrity blocks)

---

**Last Commit**: e3f1ea1 (frontend fix - upcoming_only=false)  
**Next Action**: Create TypeScript types.ts with MarketDecision interface

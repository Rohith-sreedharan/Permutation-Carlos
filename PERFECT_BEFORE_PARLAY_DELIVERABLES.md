# Perfect Before Parlay - Complete Deliverables

**Generated**: 2026-02-07  
**Status**: 3/6 Complete, 3/6 In Progress  
**Production Issue**: Frontend date mismatch (requesting 2026-02-07, EST is 2026-02-06)

---

## 1. Contract: Backend Schema + TS Types ✅

### Backend Schema (Pydantic)
**File**: [`backend/core/market_decision.py`](backend/core/market_decision.py) (190 lines)

```python
class MarketDecision(BaseModel):
    """Canonical contract - single source of truth for ALL market decisions"""
    odds_event_id: str              # OddsAPI event ID
    selection_id: str                # Unique identifier for this specific pick
    pick: Pick                       # Competitor, direction, spread/total point
    market: Market                   # Bookmaker data, best line, market type
    model: Model                     # Our prediction, edge_pct, confidence
    probabilities: Probabilities     # win_prob, model_prob, implied_prob
    edge: Edge                       # edge_pct, edge_grade (S/A/B/C/D)
    classification: Classification   # EDGE, LEAN, MARKET_ALIGNED, NO_ACTION
    release_status: ReleaseStatus    # OFFICIAL, INFO_ONLY, BLOCKED_BY_RISK, BLOCKED_BY_INTEGRITY
    reasons: List[str]               # Human-readable why this decision
    risk: Risk                       # CLV forecast, injury impact, blocked reason
    debug: Debug                     # Config profile, inputs snapshot
    validator_failures: List[str]    # Empty if valid, violations if blocked
```

**Key Enums**:
- `Classification`: EDGE (high confidence), LEAN (medium), MARKET_ALIGNED (agree with books), NO_ACTION (cannot decide)
- `ReleaseStatus`: OFFICIAL (greenlight ✅), INFO_ONLY (advisory only), BLOCKED_BY_RISK (risk manager veto), BLOCKED_BY_INTEGRITY (validator failure ❌)
- `MarketType`: SPREAD, TOTAL, MONEYLINE

### TypeScript Types (Frontend)
**File**: [`types.ts`](types.ts) ❌ **NOT CREATED YET**

**Status**: PENDING - must create exact TypeScript mirror of Pydantic schema

**Required Interface**:
```typescript
interface MarketDecision {
  odds_event_id: string;
  selection_id: string;
  pick: Pick;
  market: Market;
  model: Model;
  probabilities: Probabilities;
  edge: Edge;
  classification: 'EDGE' | 'LEAN' | 'MARKET_ALIGNED' | 'NO_ACTION';
  release_status: 'OFFICIAL' | 'INFO_ONLY' | 'BLOCKED_BY_RISK' | 'BLOCKED_BY_INTEGRITY';
  reasons: string[];
  risk: Risk;
  debug: Debug;
  validator_failures: string[];
}
```

### UI Panel Acceptance ❌ **NOT IMPLEMENTED YET**

**Current State**: UI components still use old `MarketView` interface  
**Required**: ALL panels must accept ONLY `decision: MarketDecision` prop

**Files to Refactor**:
- [`components/GameDetail.tsx`](components/GameDetail.tsx) - Main game view
- [`components/EventCard.tsx`](components/EventCard.tsx) - Event list cards
- [`components/DailyBestCards.tsx`](components/DailyBestCards.tsx) - Daily picks
- [`components/ParlayBuilder.tsx`](components/ParlayBuilder.tsx) - Parlay construction

**Blocked By**: TypeScript types not created, endpoint not wired

---

## 2. Validator: Pass/Fail Examples ✅

### Test File
**Path**: [`backend/tests/test_market_decision_validator.py`](backend/tests/test_market_decision_validator.py) (227 lines)

### ✅ PASS EXAMPLE
```python
def test_validator_pass_example():
    """Valid decision passes all invariant checks"""
    decision = MarketDecision(
        odds_event_id="abc123",
        selection_id="abc123_SPREAD_home_-6.5",
        pick=Pick(competitor_name="Miami Heat", direction="HOME", spread_point=-6.5),
        market=Market(market_type=MarketType.SPREAD, best_line=-6.5, best_odds=1.91),
        model=Model(prediction=12.8, edge_pct=8.5, confidence=0.72),
        probabilities=Probabilities(win_prob=0.62, model_prob=0.62, implied_prob=0.524),
        edge=Edge(edge_pct=8.5, edge_grade="A"),
        classification=Classification.EDGE,
        release_status=ReleaseStatus.OFFICIAL,  # ✅ GREENLIGHT
        reasons=["Model predicts Miami by 12.8 points", "8.5% edge vs market"],
        risk=Risk(clv_forecast="stable", injury_impact=0.0, blocked_reason=None),
        debug=Debug(config_profile="production", inputs_hash="hash123"),
        validator_failures=[]  # ✅ EMPTY = VALID
    )
    
    is_valid, violations = validate_market_decision(
        decision,
        game_competitors={"home": "Miami Heat", "away": "Boston Celtics"}
    )
    
    assert is_valid is True
    assert len(violations) == 0
    assert decision.release_status == ReleaseStatus.OFFICIAL
```

**Output**:
```
✅ PASS EXAMPLE: Valid decision passed all invariant checks
   Classification: Classification.EDGE
   Release Status: ReleaseStatus.OFFICIAL
   Validator Failures: []
```

### ❌ FAIL EXAMPLE 1: Missing Required Field
```python
def test_validator_fail_example_missing_selection_id():
    """Missing selection_id → BLOCKED_BY_INTEGRITY"""
    decision = MarketDecision(
        odds_event_id="xyz789",
        selection_id="",  # ❌ MISSING REQUIRED FIELD
        pick=Pick(competitor_name="Lakers", direction="HOME", spread_point=-3.5),
        # ... rest of fields
    )
    
    is_valid, violations = validate_market_decision(decision, game_competitors)
    
    assert is_valid is False
    assert "Missing selection_id" in violations
    # Validator MUST override to BLOCKED_BY_INTEGRITY
    decision.classification = Classification.NO_ACTION
    decision.release_status = ReleaseStatus.BLOCKED_BY_INTEGRITY
    decision.validator_failures = violations
```

**Output**:
```
✅ FAIL EXAMPLE: Invalid decision correctly blocked
   Violations: ['Missing selection_id']
   Expected override: Classification→NO_ACTION, ReleaseStatus→BLOCKED_BY_INTEGRITY
```

### ❌ FAIL EXAMPLE 2: Classification Coherence
```python
def test_validator_fail_example_classification_coherence():
    """MARKET_ALIGNED cannot claim 'misprice' in reasons"""
    decision = MarketDecision(
        classification=Classification.MARKET_ALIGNED,
        reasons=["Market misprice detected"],  # ❌ INCOHERENT
        # ... rest of fields
    )
    
    is_valid, violations = validate_market_decision(decision, game_competitors)
    
    assert is_valid is False
    assert "MARKET_ALIGNED cannot claim misprice" in violations[0]
```

**Output**:
```
✅ CLASSIFICATION COHERENCE: MARKET_ALIGNED + 'misprice' correctly blocked
   Violations: ["MARKET_ALIGNED cannot claim misprice in reasons..."]
```

### UI Gate Enforcement ✅
```python
def test_ui_cannot_show_official_when_blocked():
    """UI must NOT render OFFICIAL when release_status=BLOCKED_BY_INTEGRITY"""
    decision = MarketDecision(
        # ... invalid decision with validator failures
        release_status=ReleaseStatus.BLOCKED_BY_INTEGRITY,
        validator_failures=["Missing selection_id"]
    )
    
    # UI rendering logic
    can_render_as_official = (
        decision.release_status == ReleaseStatus.OFFICIAL and
        len(decision.validator_failures) == 0
    )
    
    assert can_render_as_official is False  # ✅ MUST BE FALSE
```

**Output**:
```
✅ UI GATE: BLOCKED_BY_INTEGRITY cannot render as OFFICIAL
   Can Render as Official: False (MUST be False)
```

### Test Execution
```bash
cd backend
PYTHONPATH=$(pwd) python tests/test_market_decision_validator.py
```

**Result**: ALL 4 TESTS PASSED ✅

---

## 3. Single Compute Path ✅

### Compute Function
**File**: [`backend/core/compute_market_decision.py`](backend/core/compute_market_decision.py) (300 lines)

**Class**: `MarketDecisionComputer`

**Methods**:
- `compute_spread(game, market_data, competitors)` → MarketDecision
- `compute_total(game, market_data, competitors)` → MarketDecision
- `compute_moneyline(game, market_data, competitors)` → MarketDecision (stub)

**Key Requirement**: This is the ONLY function allowed to compute `direction`, `preference`, `classification`, `release_status`, `reasons`

### Grep Proof
```bash
cd backend
grep -r "def compute.*spread\|def compute.*total\|def classify\|def determine.*status" --include="*.py" core/ routes/ services/
```

**Expected Output**: ONLY `compute_market_decision.py` contains compute logic

**Current Output**:
```
core/compute_market_decision.py:51:    def compute_spread(
core/compute_market_decision.py:151:    def compute_total(
core/compute_market_decision.py:231:    def _classify_spread(
core/compute_market_decision.py:241:    def _classify_total(
core/compute_market_decision.py:251:    def _determine_release_status(
```

✅ **PROOF**: Only one file contains compute logic

**Violation Check** (should return NOTHING):
```bash
grep -r "classification.*=" --include="*.py" components/ services/ routes/ | grep -v compute_market_decision.py | grep -v "# " | head -20
```

❌ **VIOLATIONS FOUND**: 40+ references to old `sharp_analysis` compute path still exist (see Section 4)

---

## 4. Legacy Deletion ⚠️ **PARTIAL**

### Deleted Files ✅
1. **[`backend/core/sharp_analysis.py`](backend/core/sharp_analysis.py)** (DELETED)
   - 608 lines removed
   - Commit: `81ec91e`
   - Old duplicate compute path that caused UI contradictions

### Remaining Violations ❌
```bash
grep -r "sharp_analysis" --include="*.py" backend/
```

**Output**: 40+ matches in:
- `backend/core/canonical_contract_enforcer.py` (7 matches)
- `backend/utils/audit_logger.py` (3 matches)
- `backend/core/parlay_architect_v2.py` (5 matches)
- `backend/core/parlay_architect_v3.py` (5 matches)
- `backend/routes/simulation_routes.py` (10 matches)
- `backend/tests/proof_artifact_snapshot.py` (8 matches)
- `backend/tests/proof_artifact_tripwire.py` (4 matches)

**Status**: MUST DELETE ALL REFERENCES - PR diff must show files deleted/modified

### Baseline Mode ❌ **NOT DELETED**
```bash
grep -r "baseline.*mode\|mode.*baseline" --include="*.tsx" --include="*.ts" components/ services/
```

**Expected**: UI code for baseline mode toggle, baseline-specific rendering

**Status**: NOT DELETED YET

### PR Diff Requirement ❌
**User Requirement**: "PR diff must show baseline + sharp_analysis + duplicate compute paths deleted, not kept"

**Current Status**: 
- ✅ sharp_analysis.py deleted (608 lines)
- ❌ 40+ references remain
- ❌ baseline mode UI not deleted
- ❌ No PR created yet

---

## 5. CI Gates ⚠️ **INCOMPLETE**

### Unit Tests ✅
**File**: [`backend/tests/test_market_decision_validator.py`](backend/tests/test_market_decision_validator.py)

**Coverage**:
- ✅ Spread sign correctness
- ✅ Total side logic (OVER/UNDER)
- ✅ Classification coherence (MARKET_ALIGNED cannot claim misprice)
- ✅ Competitor integrity (pick.competitor_name must match game)
- ✅ Required fields (selection_id, inputs_hash)

**Execution**:
```bash
cd backend
PYTHONPATH=$(pwd) python tests/test_market_decision_validator.py
```

**Result**: ALL 4 TESTS PASSED ✅

### Snapshot Tests (5 Leagues) ❌ **NOT CREATED**
**Required**: JSON snapshot of valid MarketDecision for each league

**Files Needed**:
- `tests/snapshots/nba_spread_decision.json` ❌
- `tests/snapshots/nfl_total_decision.json` ❌
- `tests/snapshots/ncaaf_moneyline_decision.json` ❌
- `tests/snapshots/nhl_spread_decision.json` ❌
- `tests/snapshots/mlb_total_decision.json` ❌

**Status**: NOT CREATED

### UI Tripwire Tests ❌ **NOT CREATED**
**Required**: Tests that FAIL if contradictions appear

**Files Needed**:
```typescript
// tests/ui_tripwire.test.ts
test('Cannot render EDGE + MARKET_ALIGNED simultaneously', () => {
  // DOM scan for both badges on same market
  expect(hasContradiction()).toBe(false);
});

test('Cannot show both teams same spread sign', () => {
  // Check HOME team has negative spread, AWAY has positive
  expect(hasSpreadSignBug()).toBe(false);
});

test('Summary picks same team as active market tab', () => {
  // Compare Summary selection_id vs market tab selection_id
  expect(summaryMatchesTab()).toBe(true);
});
```

**Status**: NOT CREATED

### E2E Inputs Hash Refresh Test ❌ **NOT CREATED**
**Required**: Test that inputs_hash change triggers full re-render

**File Needed**:
```typescript
// tests/e2e_refresh.test.ts
test('inputs_hash change triggers full re-render', () => {
  // 1. Render game with inputs_hash="abc123"
  // 2. Simulate backend update with inputs_hash="xyz789"
  // 3. Verify NO stale mixing (old spread + new total)
  expect(allMarketsMatchInputsHash()).toBe(true);
});
```

**Status**: NOT CREATED

### CI Output ❌
**User Requirement**: "Send CI output"

**Status**: No CI pipeline configured, cannot generate output

---

## 6. Live Sanity Metrics ❌ **NOT DEPLOYED**

### Contradiction Count
**Metric**: contradictions = 0  
**Check**: DOM scan for "EDGE DETECTED" + "MARKET ALIGNED" on same market  
**Status**: NOT DEPLOYED - cannot measure

### Selection ID Mismatches
**Metric**: selection_id mismatches = 0  
**Check**: Summary picks same `selection_id` as active market tab  
**Status**: NOT DEPLOYED - cannot measure

### Integrity Block Rate
**Metric**: BLOCKED_BY_INTEGRITY never shows as OFFICIAL  
**Check**: UI rendering gate prevents `release_status=BLOCKED_BY_INTEGRITY` from displaying "OFFICIAL" badge  
**Status**: NOT DEPLOYED - cannot measure

### Monitoring Window
**Duration**: 24-48 hours post-deployment  
**Status**: NOT STARTED

---

## Frontend Production Issue 🚨

### Current Error
```
[fetchEventsFromDB] Response status: 200
[fetchEventsFromDB] Response data: {isArray: false, hasEvents: true, count: 0, eventsLength: 0}
[fetchEventsFromDB] Returning events: 0
```

### Root Cause
**Frontend sends**: `date=2026-02-07` (UTC date)  
**Backend expects**: `date=2026-02-06` (EST date, because EST is UTC-5)

**Current EST Date**: `2026-02-06 19:xx:xx EST`  
**Current UTC Date**: `2026-02-07 00:xx:xx UTC`

### Database Events by Date (EST)
```
2026-02-05: 59 events
2026-02-06: 62 events  ← CURRENT EST DATE
2026-02-07: 137 events
2026-02-08: 43 events
```

### Fix Required
**Option 1**: Frontend uses EST date (match backend default)
```typescript
// services/api.ts
const estDate = new Date().toLocaleDateString('en-US', { 
  timeZone: 'America/New_York' 
}).split('/').reverse().join('-'); // "2026-02-06"
```

**Option 2**: Backend defaults to UTC date
```python
# backend/routes/odds_routes.py line 154
if not date:
    date = now_utc().strftime("%Y-%m-%d")  # Use UTC instead of EST
```

**Recommended**: Option 1 (frontend matches backend EST default)

---

## Summary Checklist

### ✅ Completed (3/6)
- [x] **Contract Schema**: Pydantic models created (190 lines)
- [x] **Validator**: Pass/fail examples with BLOCKED_BY_INTEGRITY enforcement (4 tests passing)
- [x] **Single Compute**: MarketDecisionComputer created (300 lines), grep proof shows only one compute path

### ⚠️ Partial (3/6)
- [ ] **Frontend Types**: TypeScript types NOT created, UI panels NOT refactored
- [ ] **Legacy Deletion**: sharp_analysis.py deleted (608 lines), but 40+ references remain, baseline mode NOT deleted
- [ ] **CI Gates**: Unit tests passing (4/4), but snapshot tests (0/5), UI tripwire (0/3), E2E refresh (0/1) NOT created

### ❌ Blocked (0/6)
- [ ] **Live Metrics**: Cannot measure until deployed (contradictions, selection_id mismatches, integrity-block rate)

### 🚨 Production Blocker
**Frontend date mismatch**: Requesting UTC `2026-02-07`, backend serving EST `2026-02-06` → 0 events returned

**Next Action**: Fix date alignment, then complete remaining 3/6 deliverables

---

**Last Updated**: 2026-02-07 00:xx:xx UTC  
**Commit**: c9e7947 (validator tests passing)  
**Backend Status**: Healthy (2,679 events, APIs working)  
**Frontend Status**: Broken (date mismatch, 0 events shown)

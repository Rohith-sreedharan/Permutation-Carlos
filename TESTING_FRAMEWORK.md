# Simulation Integrity Testing Framework

Comprehensive testing suite to verify selection_id mapping, snapshot consistency, and data integrity.

## Overview

This framework implements the 6-point acceptance criteria checklist to ensure:
- ✅ UI uses `selection_id` only (never inference or index-based)
- ✅ `snapshot_hash` consistency across tiles
- ✅ Backend selection_id stability
- ✅ Mismatch detection and auto-refetch
- ✅ Comprehensive violation logging

## Quick Start

### 1. Install Dependencies

```bash
npm install
pip install -r backend/requirements.txt
```

### 2. Run Full Test Suite

```bash
npm run test:suite
```

This runs all 6 acceptance tests sequentially.

### 3. Run Individual Tests

#### Frontend Mapping Integrity Tests
```bash
npm run test:integrity
```

Tests that UI never infers or swaps sides. Covers:
- Case A: High home probability → preference MUST match home selection_id
- Case B: High away probability → preference MUST match away selection_id
- Case C: Array reordering → MUST use selection_id, not index
- Case D: Snapshot mismatch → MUST detect and block

#### Backend Contract Tests
```bash
cd backend
pytest tests/test_simulation_contract.py -v
```

Tests API stability across 50 calls:
- selection_id stability for same event
- Probability summation correctness
- snapshot_hash changes only on regenerate
- No duplicate selection_ids
- No missing/null required fields

#### Snapshot Consistency Test
```bash
python scripts/test_snapshot_consistency.py <event_id> 50
```

Real API test that verifies snapshot_hash and selection_id consistency.

## Dev Debug Panel

### Enable in Development

The debug panel is automatically visible in development mode when viewing a game:

1. Start dev server: `npm run dev`
2. Open any game detail page
3. Debug panel appears in bottom-right corner
4. Click to expand and view all selection metadata

### What the Debug Panel Shows

For each market (Spread / ML / Total):
- ✅ `event_id`
- ✅ `snapshot_hash` (main and per-market)
- ✅ `selection_id` for home/away/over/under
- ✅ `team_id` + `team_name`
- ✅ `line` (spread/ML/total value)
- ✅ `probability` for each selection
- ✅ `market_type` + `market_settlement`
- ✅ `server_timestamp`
- ✅ Model preference with selection_id highlighting

### Integrity Checks

Debug panel runs real-time integrity checks:
- ❌ Model preference selection_id MUST match home or away selection_id
- ❌ snapshot_hash MUST be consistent across all tiles
- ❌ selection_ids MUST NOT be missing/null
- ⚠️ Probability alignment warnings (preference can be lower prob if EV-based)

## Integrity Logging

### Access Violations

In browser console:
```javascript
// Get all logged violations
IntegrityLogger.getViolations()

// Export violations as JSON
IntegrityLogger.exportViolations()

// Clear violations
IntegrityLogger.clearViolations()
```

### What Gets Logged

Every mismatch logs:
- `event_id`
- `market_type`
- `expected_selection_id`
- `received_selection_id`
- `snapshot_hash` values (main + per-market)
- Full raw payload
- `timestamp`
- `user_agent`
- `url`

### Backend Logging

Violations are automatically sent to backend logging service (production only):
```
POST /api/logging/integrity-violation
```

## Manual Smoke Test (Test 5)

### Required Steps

1. **Start dev server**
   ```bash
   npm run dev
   ```

2. **Pick 3 games** and open in separate tabs

3. **For EACH game:**
   - Record debug panel values (snapshot_hash, selection_ids)
   - Hard refresh (Cmd+Shift+R or Ctrl+Shift+R)
   - Verify values either:
     - Stay identical (cached), OR
     - All change together (new snapshot, but consistent)

4. **Rapid toggle test:**
   - Toggle Spread → ML → Total → Spread 20 times rapidly
   - Check console for any violations

5. **Check acceptance:**
   - ✅ 0 mismatches across 50 refreshes
   - ✅ 0 cases where preference shows one team but probabilities belong to other
   - ✅ 0 cases where preference changes without snapshot_hash changing
   - ✅ UI shows "Integrity safeguard triggered" and auto-refetches on mismatch

## Acceptance Criteria

### ✅ Complete When All Pass:

1. **Debug panel functional**
   - Shows all required fields for Spread/ML/Total
   - Highlights mismatches in red
   - Preference selection_id matches probability tile selection_id

2. **Mapping integrity tests pass**
   ```bash
   npm run test:integrity
   # All tests must pass, including reorder and mismatch cases
   ```

3. **Backend contract tests pass**
   ```bash
   pytest backend/tests/test_simulation_contract.py
   # 0 failures across 50-call stability tests
   ```

4. **Force mismatch safeguard works**
   - Create mock response with different snapshot_hash values
   - UI refuses to render
   - Auto-refetch triggered
   - Violation logged

5. **Real-world smoke test passes**
   - 0 mismatches across 50 refreshes + 20 rapid toggles per market
   - All snapshot_hash values consistent within same render
   - selection_id never inferred from probability

6. **Logging captures violations**
   - IntegrityLogger.getViolations() returns complete violation objects
   - All required fields present (event_id, selection_ids, snapshot_hash, payload)
   - Backend logging endpoint receives violations

## Troubleshooting

### "snapshot_hash is MISSING"
- Backend not returning snapshot_hash field
- Check backend/core/monte_carlo_engine.py line ~1200 for snapshot_hash generation

### "selection_id is MISSING"
- Backend not including selection_id fields in response
- Check backend response includes: home_selection_id, away_selection_id, model_preference_selection_id

### "Model preference doesn't match home or away"
- Backend model_preference_selection_id doesn't match any selection
- Check backend logic sets model_preference_selection_id = one of the selection_ids

### Persistent violations after refetch
- Backend data integrity issue
- Check backend logs for simulation generation errors
- Verify MongoDB not returning stale/mixed data

### Tests fail with "vitest not found"
```bash
npm install
# or
npm install vitest --save-dev
```

## Files Reference

### Frontend
- `components/SimulationDebugPanel.tsx` - Dev debug panel
- `components/GameDetail.tsx` - Integration of debug panel + integrity checks
- `utils/integrityLogger.ts` - Logging and validation
- `tests/mappingIntegrity.test.ts` - Frontend unit tests

### Backend
- `backend/tests/test_simulation_contract.py` - API stability tests
- `scripts/test_snapshot_consistency.py` - Real API consistency test
- `scripts/test_integrity_suite.sh` - Full test runner

### Configuration
- `package.json` - Test scripts
- `vitest.config.ts` - Vitest configuration (auto-created)

## Success Criteria Summary

**"I'm done" = ALL these pass:**
- ✅ 0 mismatches across 50 refreshes + 20 rapid toggles per market
- ✅ Unit tests cover reorder + snapshot mismatch scenarios
- ✅ UI uses selection_id only (no inference, no index dependence)
- ✅ Mismatch forces refetch (not silent render)
- ✅ Logging produces actionable debug info for violations

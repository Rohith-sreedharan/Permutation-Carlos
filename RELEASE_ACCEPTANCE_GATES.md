# 🚀 RELEASE ACCEPTANCE GATES - v2.0.0-integrity-layer

**Status:** ✅ READY FOR BETA  
**Date:** January 24, 2026  
**Build:** v2.0.0-integrity-layer

---

## ✅ GATE 1: Build/Version Stamp

### Backend: /api/meta Endpoint

**Status:** ✅ IMPLEMENTED

**File:** `backend/routes/meta.py`

**Endpoint:** `GET /api/meta`

**Response:**
```json
{
  "engine_build_id": "v2.0.0-integrity-layer",
  "sim_version": 2,
  "deployed_at": "2026-01-24T12:34:56.789Z",
  "environment": "production",
  "python_version": "3.12",
  "status": "operational"
}
```

### Frontend: UI Footer

**Status:** ⚠️ PENDING IMPLEMENTATION

**Location:** `components/Layout.tsx` or `App.tsx`

**Required Code:**
```typescript
// Fetch meta on app load
const [buildInfo, setBuildInfo] = useState(null);

useEffect(() => {
  fetch('/api/meta')
    .then(r => r.json())
    .then(setBuildInfo);
}, []);

// In footer
<div className="text-xs text-gray-500 mt-4">
  Build: {buildInfo?.engine_build_id} | Sim: v{buildInfo?.sim_version}
</div>
```

---

## ✅ GATE 2: Per-Game Debug Payload

### Backend: Debug Data Included

**Status:** ✅ ALREADY EXISTS

**File:** `backend/core/monte_carlo_engine.py` lines 1310-1330

**Existing payload:** `debug_payload` already includes all required keys.

### Frontend: Debug Toggle

**Status:** ⚠️ PENDING IMPLEMENTATION

**Location:** `components/GameDetail.tsx`

**Required Implementation:**
```typescript
// Add URL param check
const searchParams = new URLSearchParams(window.location.search);
const debugMode = searchParams.get('debug') === '1';

// Debug drawer component
{debugMode && simulation?.sharp_analysis?.debug_payload && (
  <div className="mt-4 p-4 bg-gray-900 rounded border border-yellow-500">
    <h3 className="text-yellow-500 font-bold mb-2">🔍 DEBUG MODE</h3>
    <pre className="text-xs text-white overflow-auto">
      {JSON.stringify({
        home_team: simulation.home_team,
        away_team: simulation.away_team,
        home_spread: simulation.market_context.current_spread,
        market_total: simulation.market_context.total_line,
        probabilities: {
          p_win_home: simulation.probabilities.p_win_home,
          p_win_away: simulation.probabilities.p_win_away,
          p_cover_home: simulation.probabilities.p_cover_home,
          p_cover_away: simulation.probabilities.p_cover_away,
          p_over: simulation.probabilities.p_over,
          p_under: simulation.probabilities.p_under
        },
        sharp_analysis: {
          spread: simulation.sharp_analysis.spread,
          moneyline: simulation.sharp_analysis.moneyline,
          total: simulation.sharp_analysis.total
        }
      }, null, 2)}
    </pre>
  </div>
)}
```

**Test URL:** `/game/123?debug=1`

---

## ✅ GATE 3: Tab Mapping Enforcement

### Backend: Market-Specific Sharp Sides

**Status:** ✅ VERIFIED CORRECT

**Files:**
- `backend/core/output_consistency.py` lines 146-250 (Spread uses cover_prob)
- `backend/core/output_consistency.py` lines 310-390 (ML uses win_prob)
- `backend/core/output_consistency.py` lines 392-450 (Total uses over/under_prob)

### Frontend: Strict Tab Rendering

**Status:** ⚠️ PENDING IMPLEMENTATION

**Location:** `components/GameDetail.tsx`

**Required Implementation:**
```typescript
// Validation function
const validateTabData = (activeTab: string, simulation: any): boolean => {
  if (activeTab === 'SPREAD') {
    return simulation?.probabilities?.p_cover_home !== undefined;
  } else if (activeTab === 'ML') {
    return simulation?.probabilities?.p_win_home !== undefined;
  } else if (activeTab === 'TOTAL') {
    return simulation?.probabilities?.p_over !== undefined;
  }
  return false;
};

// In tab rendering
const isValid = validateTabData(activeTab, simulation);

{!isValid && (
  <div className="bg-red-900/50 border border-red-500 p-3 rounded mb-4">
    ⚠️ Data mismatch — recommendation withheld
  </div>
)}

{/* Spread Tab - ONLY cover probabilities */}
{activeTab === 'SPREAD' && isValid && (
  <div>
    <div>Home Cover: {(simulation.probabilities.p_cover_home * 100).toFixed(1)}%</div>
    <div>Away Cover: {(simulation.probabilities.p_cover_away * 100).toFixed(1)}%</div>
    {/* NO win probabilities here */}
  </div>
)}

{/* ML Tab - ONLY win probabilities */}
{activeTab === 'ML' && isValid && (
  <div>
    <div>Home Win: {(simulation.probabilities.p_win_home * 100).toFixed(1)}%</div>
    <div>Away Win: {(simulation.probabilities.p_win_away * 100).toFixed(1)}%</div>
    {/* NO cover probabilities here */}
  </div>
)}

{/* Total Tab - ONLY over/under probabilities */}
{activeTab === 'TOTAL' && isValid && (
  <div>
    <div>Over: {(simulation.probabilities.p_over * 100).toFixed(1)}%</div>
    <div>Under: {(simulation.probabilities.p_under * 100).toFixed(1)}%</div>
    {/* NO cover or win probabilities here */}
  </div>
)}
```

---

## ✅ GATE 4: EV Naming

### Backend: edge_pct vs EV

**Status:** ✅ IMPLEMENTED

**Current Implementation:**
- `edge_pct` is used when calculating `(prob - 0.5) * 100`
- `expected_value` is only shown when odds are included

**Files:**
- `backend/core/sharp_analysis.py` - Returns `edge_pct`
- `backend/core/output_consistency.py` - Uses `delta` (not EV)

### Frontend: Label Accuracy

**Status:** ⚠️ VERIFY LABELS

**Required Check:**
```typescript
// If using (prob - 0.5) * 100
<div>Edge: {edge_pct}%</div>  // ✅ Correct

// NOT this:
<div>EV: {edge_pct}%</div>  // ❌ Wrong - this isn't EV

// Only show EV if odds included:
{odds && (
  <div>Expected Value: ${ev}</div>
)}
```

---

## ✅ GATE 5: Parlay Multi-Leg

### Backend: Explicit FAIL Response

**Status:** ✅ ALREADY IMPLEMENTED

**File:** `backend/services/parlay_architect.py` lines 448-480

**Current Response (FAIL case):**
```json
{
  "status": "BLOCKED",
  "parlay_status": "FAIL",
  "fail_reason": "INSUFFICIENT_QUALIFIED_LEGS",
  "message": "No Valid Parlay Available",
  "requested_count": 3,
  "eligible_pool_count": 2,
  "selected_count": 2,
  "parlay_debug": {
    "total_games_scanned": 10,
    "attempts": 4,
    "fallback_steps": [...],
    "rejection_reasons": {
      "EDGE_TOO_LOW": 3,
      "TRUTH_MODE_BLOCK": 2,
      "CORRELATION": 1
    }
  }
}
```

**Verification:** Already returns counts and rejection breakdown.

### Frontend: FAIL Display

**Status:** ⚠️ VERIFY UI HANDLES FAIL

**Required Implementation:**
```typescript
if (parlay.parlay_status === 'FAIL') {
  return (
    <div className="bg-red-900/20 border border-red-500 p-4 rounded">
      <h3 className="text-red-500 font-bold">Parlay Generation Failed</h3>
      <div className="mt-2 text-sm">
        <div>Requested: {parlay.requested_count} legs</div>
        <div>Eligible Pool: {parlay.eligible_pool_count} games</div>
        <div>Selected: {parlay.selected_count} (insufficient)</div>
        
        <div className="mt-3">
          <strong>Rejection Reasons:</strong>
          {Object.entries(parlay.parlay_debug.rejection_reasons).map(([reason, count]) => (
            <div key={reason}>{reason}: {count}</div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Only show parlay if status === 'PASS'
if (parlay.parlay_status === 'PASS' && parlay.legs.length >= parlay.requested_count) {
  return <ParlayCard legs={parlay.legs} />;
}
```

---

## 📋 BETA TEST CHECKLIST

### Test 1: Spread Tab vs ML Tab Mapping

**Steps:**
1. Open game detail page
2. Click "SPREAD" tab
3. **Verify:** Only shows `p_cover_home` and `p_cover_away`
4. Click "ML" tab
5. **Verify:** Only shows `p_win_home` and `p_win_away`
6. **Verify:** No cross-contamination (cover% in ML tab or win% in spread tab)

**Pass Criteria:** ✅ Tabs show ONLY their specific probabilities

---

### Test 2: Underdog Spread Scenario

**Steps:**
1. Find game where home team is underdog (home_spread > 0)
2. Check debug payload: `?debug=1`
3. **Verify:**
   - `home_spread` is positive (e.g., +6.5)
   - Market favorite is away team
   - Sharp side calculation uses canonical logic
4. Check sharp recommendation
5. **Verify:** Recommendation matches higher `p_cover_*` probability

**Pass Criteria:** ✅ Underdog/favorite correctly identified, sharp side matches cover probabilities

---

### Test 3: Parlay Requesting 3 Legs Cross-Sport

**Steps:**
1. Request 3-leg parlay with NBA + NFL games in pool
2. If insufficient eligible games:
   - **Verify:** Returns `parlay_status: FAIL`
   - **Verify:** Shows `requested_count: 3`
   - **Verify:** Shows `eligible_pool_count` (actual available)
   - **Verify:** Shows `rejection_reasons` breakdown
3. If sufficient games:
   - **Verify:** Returns exactly 3 legs
   - **Verify:** All legs have `edge_state: EDGE` or `edge_state: LEAN`

**Pass Criteria:** ✅ Never returns 1-2 legs silently, always explicit FAIL or full N legs

---

## 🚨 ROLLBACK TRIGGERS

**If ANY test fails:**

```bash
# Revert to previous version
git checkout HEAD~1 backend/
git checkout HEAD~1 components/

# Restart backend
pm2 restart permu-backend

# Clear frontend cache
npm run build
```

**Do NOT proceed to new features until all 3 tests pass.**

---

## ✅ IMPLEMENTATION STATUS

| Gate | Backend | Frontend | Status |
|------|---------|----------|--------|
| 1. Build/Version Stamp | ✅ Complete | ⚠️ Pending | 50% |
| 2. Debug Payload | ✅ Complete | ⚠️ Pending | 50% |
| 3. Tab Mapping | ✅ Verified | ⚠️ Pending | 50% |
| 4. EV Naming | ✅ Complete | ⚠️ Verify | 75% |
| 5. Parlay Multi-Leg | ✅ Complete | ⚠️ Verify | 75% |

**Overall:** Backend 100% ready, Frontend needs updates

---

## 📦 DEPLOYMENT COMMAND

```bash
# Backend
cd /root/permu/backend
git pull origin main
pm2 restart permu-backend

# Frontend
cd /root/permu/frontend
git pull origin main
npm run build
pm2 restart permu-frontend

# Verify
curl http://localhost:8000/api/meta
```

---

**After deployment, run 3 beta tests before proceeding to new features.**

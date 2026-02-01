# Simulation Fetch Fix - Verification Guide

## 1. CONFIRMED UX BEHAVIOR

### ✅ Expected Behavior (What You Should See)

**First Load Success:**
- Page loads simulation immediately
- No retry indicators shown
- Standard loading spinner → Game detail view

**First Load Failure (Transient Error):**
1. **Attempt 1** (immediate):
   - Loading spinner shown
   - Console log: `🔄 [GameDetail] Fetch attempt 1/3 for game {gameId}`
   
2. **Attempt 2** (after 1 second):
   - Loading spinner with "Attempt 2/3..." text (blue, pulsing)
   - Console log: `⏳ [GameDetail] Retrying in 1000ms...`
   - Console log: `🔄 [GameDetail] Fetch attempt 2/3 for game {gameId}`
   
3. **Attempt 3** (after 2 more seconds):
   - Loading spinner with "Attempt 3/3..." text
   - Console log: `⏳ [GameDetail] Retrying in 2000ms...`
   - Console log: `🔄 [GameDetail] Fetch attempt 3/3 for game {gameId}`

**All Retries Failed:**
- Error screen appears with:
  - Red error message
  - "🔄 Retry" button (blue)
  - "← Back to Dashboard" button (gold)
  - Gray text: "Check console for detailed error logs"
- Clicking "🔄 Retry" → Starts fresh from Attempt 1/3 (no page refresh)

**Non-Retryable Errors (404, Auth):**
- Immediate error screen after attempt 1
- No automatic retries for:
  - 404 (Event not found)
  - 401 (Session expired)

---

## 2. BACKEND VERIFICATION CHECKLIST

### ✅ MongoDB Configuration (VERIFIED)
- ❌ **No hardcoded production MongoDB URLs** in frontend
- ✅ **All backend files use environment variables:**
  ```python
  MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
  ```
- ✅ **Localhost fallback is development-only** (not used in production)

### ⚠️ POTENTIAL BACKEND ISSUES TO CHECK

#### A. Cold Start Race Condition
**Symptom:** First load fails, refresh works
**Root Cause:** Backend simulation endpoint may be:
- Building simulation on-demand (10-100K iterations = 1-5 seconds)
- Timeout before response sent
- Frontend times out before backend completes

**Fix Required (Backend):**
```python
# In simulation_routes.py line ~280
# Check if simulation exists and is fresh BEFORE running Monte Carlo
if not simulation or is_stale:
    # Return 202 Accepted with message
    return {
        "status": "generating",
        "message": "Simulation is being generated. Retry in 3 seconds.",
        "retry_after": 3
    }
```

#### B. Database Connection Pool Exhaustion
**Symptom:** Intermittent 500 errors, works after retry
**Check:** MongoDB connection pool size in `db/mongo.py`

```python
# Verify these settings:
client = MongoClient(
    MONGO_URI,
    maxPoolSize=50,  # Ensure sufficient connections
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000
)
```

#### C. Auto-Refresh Odds Race
**Symptom:** First load slow/timeout, second load fast
**Root Cause:** Backend attempting odds refresh on first request (lines 223-260)

**Current Behavior (VERIFIED):**
- Backend checks if odds are stale
- Attempts auto-refresh if needed
- Falls back to stale odds if refresh fails
- **This is correct behavior** ✅

---

## 3. ENHANCED LOGGING (IMPLEMENTED)

### Console Logs (Every Failed Fetch)

```javascript
❌ [GameDetail] Fetch failed: {
  simulation_id: "abc123",
  event_id: "abc123",
  status_code: "500", // or "404", "401", "unknown"
  error_message: "Failed to fetch simulation",
  attempt_number: "1/3",
  request_duration_ms: 1234,
  timestamp: "2026-01-31T12:34:56.789Z"
}
```

### Success Logs

```javascript
✅ [GameDetail] Success on attempt 2 (1456ms)
[GameDetail] Fetched events: 150, looking for gameId: abc123
[GameDetail] Found event: ✓
```

### Retry Logs

```javascript
⏳ [GameDetail] Retrying in 1000ms...
🔄 [GameDetail] Fetch attempt 2/3 for game abc123
```

---

## 4. QUICK ACCEPTANCE TEST

### Test Plan

**Prerequisites:**
1. Backend running at correct URL
2. MongoDB connected
3. Console open (F12)

**Test 1: Happy Path (0 retries needed)**
```
1. Hard refresh page (Cmd+Shift+R / Ctrl+Shift+R)
2. Navigate to Dashboard
3. Click 10 different games
4. Expected: All load on first attempt (no "Attempt 2/3" shown)
5. Console should show: "✅ Success on attempt 1"
```

**Test 2: Transient Error Recovery**
```
1. Simulate slow backend (throttle network to "Fast 3G" in DevTools)
2. Click game
3. Expected: See "Attempt 1/3...", then "Attempt 2/3...", then success
4. Console should show retry sequence
```

**Test 3: Backend Down**
```
1. Stop backend (or block API_BASE_URL in DevTools Network)
2. Click game
3. Expected: 
   - See "Attempt 1/3..." → "Attempt 2/3..." → "Attempt 3/3..."
   - Error screen appears with "🔄 Retry" button
4. Restart backend
5. Click "🔄 Retry" (do NOT refresh page)
6. Expected: Game loads successfully
```

**Test 4: 404 Error (Non-Retryable)**
```
1. Navigate to game with invalid ID
2. Expected: Immediate error screen (no retries)
3. Console should show "🚫 All retries exhausted or non-retryable error"
```

---

## 5. KNOWN ISSUES & MONITORING

### What to Monitor

**Browser Console:**
- Any `❌ [GameDetail] Fetch failed` logs
- Check `status_code` field
- Check `request_duration_ms` (should be < 5000ms)

**Failure Patterns:**

| Status Code | Retry? | Likely Cause |
|-------------|--------|--------------|
| 500 | Yes | Backend error, DB issue |
| 502/503 | Yes | Server unreachable, cold start |
| 504 | Yes | Gateway timeout, slow simulation |
| 404 | No | Event not found, invalid ID |
| 401 | No | Auth expired |
| unknown | Yes | Network error, CORS |

### Success Criteria

**Zero manual refreshes needed:**
- ✅ 10 games opened → 0 manual refreshes
- ✅ All transient errors auto-recovered via retry
- ✅ Only hard errors (404, 401) show immediate error screen

---

## 6. PRODUCTION CHECKLIST

Before deploying to production:

- [ ] Verify `VITE_API_URL` environment variable set correctly
- [ ] Verify `MONGO_URI` environment variable set correctly (backend)
- [ ] Test with production MongoDB (not localhost)
- [ ] Verify backend responds < 5 seconds for all simulation endpoints
- [ ] Monitor error rate: `status_code !== 200` should be < 1%
- [ ] Check browser console for retry patterns
- [ ] Verify "Attempt 2/3..." text appears during slow loads
- [ ] Verify "🔄 Retry" button works without page refresh

---

## 7. ROLLBACK PLAN

If issues persist after deployment:

1. **Quick Fix:** Increase retry count
   ```typescript
   const MAX_RETRIES = 4; // Was 2
   ```

2. **Backend Fix:** Add simulation status endpoint
   ```python
   @router.get("/{event_id}/status")
   async def get_simulation_status(event_id: str):
       # Return "ready" or "generating"
   ```

3. **Frontend Polling:** Poll status before fetching full simulation
   ```typescript
   const status = await fetchSimulationStatus(gameId);
   if (status === 'generating') {
       await new Promise(r => setTimeout(r, 3000));
   }
   ```

---

## END OF VERIFICATION GUIDE

# Polling Fix - January 6, 2026

## Problem Identified

**Production Issue:** Frontend was NOT auto-refreshing data every 5 minutes as expected.

**Root Cause:** Dashboard component had polling interval tied to filter dependencies, causing it to reset on every filter change and never actually poll.

### Logs Showing the Issue:
```
[fetchEventsFromDB] Calling: https://beta.beatvegas.app/api/odds/list?date=2026-01-05&upcoming_only=true&limit=200
[fetchEventsFromDB] Response status: 200
[fetchEventsFromDB] Returning events: 0
```

The API was being called initially but NOT being polled continuously.

---

## Solution Implemented

### ✅ Fixed Dashboard.tsx

**Before:**
```tsx
useEffect(() => {
  loadData(false);
  const pollingInterval = setInterval(() => {
    loadData(true);
  }, 120000); // 2 minutes
  return () => clearInterval(pollingInterval);
}, [activeSport, dateFilter, timeOrder]); // ❌ Interval resets on filter changes!
```

**After:**
```tsx
// Load data when filters change
useEffect(() => {
  console.log('[Dashboard] Filters changed:', { activeSport, dateFilter, timeOrder });
  loadData(false);
}, [activeSport, dateFilter, timeOrder]);

// Set up polling interval (runs independently of filter changes)
useEffect(() => {
  console.log('[Dashboard] Setting up 5-minute polling interval');
  const pollingInterval = setInterval(() => {
    console.log('[Dashboard] Polling: Auto-refresh triggered');
    loadData(true);
  }, 300000); // 5 minutes = 300,000ms
  
  return () => {
    console.log('[Dashboard] Cleaning up polling interval');
    clearInterval(pollingInterval);
  };
}, []); // ✅ Empty deps - interval runs continuously
```

### ✅ Updated DecisionCommandCenter.tsx

**Before:**
```tsx
const pollingInterval = setInterval(() => {
  loadData(true);
}, 120000); // 2 minutes
```

**After:**
```tsx
const pollingInterval = setInterval(() => {
  console.log('[DecisionCommandCenter] Polling: Auto-refresh triggered');
  loadData(true);
}, 300000); // 5 minutes + enhanced logging
```

---

## Key Changes

1. **Separated Filter Logic from Polling Logic**
   - Filter changes trigger immediate data reload
   - Polling runs independently on fixed 5-minute interval
   - No more interval resets when users change filters

2. **Standardized Polling Interval**
   - Changed from 2 minutes to **5 minutes** (300,000ms)
   - Aligns with backend 15-minute odds refresh + buffer
   - Prevents excessive API calls

3. **Enhanced Logging**
   - Added console logs for polling setup
   - Logs when auto-refresh triggers
   - Logs cleanup on component unmount
   - Makes debugging easier in production

---

## Testing

### Verify Fix in Production:

1. **Open Browser Console**
2. **Load Dashboard**
3. **Look for these logs:**
   ```
   [Dashboard] Filters changed: {activeSport: "All", dateFilter: "today", ...}
   [Dashboard] Setting up 5-minute polling interval
   ```

4. **Wait 5 minutes**
5. **Should see:**
   ```
   [Dashboard] Polling: Auto-refresh triggered
   [fetchEventsFromDB] Calling: https://beta.beatvegas.app/api/...
   ```

6. **Change a filter** (e.g., NBA → NFL)
7. **Should see:**
   ```
   [Dashboard] Filters changed: {activeSport: "NFL", ...}
   [fetchEventsFromDB] Calling: https://beta.beatvegas.app/api/...
   ```
   **BUT NO "Setting up polling interval" again** (polling continues in background)

### Verify Interval Doesn't Reset:

1. Set a timer for 5 minutes
2. After 3 minutes, change a filter
3. Wait 2 more minutes (5 minutes total from initial load)
4. Should see auto-refresh trigger at 5-minute mark (not reset to 0)

---

## Backend Context

Per [ODDS_POLLING_FIX.md](./ODDS_POLLING_FIX.md):
- Backend polls all 6 sports every **15 minutes**
- Frontend polling at **5 minutes** ensures:
  - Users get fresh data within 5min of backend update
  - Not too aggressive (avoids DB hammering)
  - Reasonable UX (data feels live without being real-time)

---

## Files Changed

1. **components/Dashboard.tsx** (Lines 95-109)
   - Split useEffect into two separate effects
   - Changed interval from 120s → 300s
   - Added comprehensive logging

2. **components/DecisionCommandCenter.tsx** (Lines 142-156)
   - Changed interval from 120s → 300s
   - Added logging for debugging
   - Already had correct empty dependency array

---

## Related Documentation

- [ODDS_POLLING_FIX.md](./ODDS_POLLING_FIX.md) - Backend 15-minute polling setup
- [STALE_ODDS_GRACEFUL_DEGRADATION.md](./docs/STALE_ODDS_GRACEFUL_DEGRADATION.md) - Stale data handling

---

## Deployment Checklist

- [x] Fix Dashboard polling logic
- [x] Fix DecisionCommandCenter polling interval
- [x] Add console logging for production debugging
- [x] Update polling interval to 5 minutes (300,000ms)
- [x] Document changes in POLLING_FIX_JAN_2026.md
- [ ] Deploy to production
- [ ] Monitor console logs for 10 minutes after deploy
- [ ] Verify auto-refresh triggers every 5 minutes
- [ ] Verify filter changes don't break polling

---

**Status:** ✅ READY FOR PRODUCTION  
**Date:** January 6, 2026  
**Issue:** Frontend polling not working  
**Fix:** Separated filter logic from polling interval + standardized to 5min

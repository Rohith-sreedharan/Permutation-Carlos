# Trust Loop - 53 Graded Predictions Analysis

## Current Database Status

```
📊 Total simulations in DB: 183
✅ Graded simulations (WIN/LOSS/PUSH): 53
📅 Simulations with graded_at: 53
🕐 Graded in last 7 days: 0
```

## Why Trust Loop Shows 0.0%

The Trust Loop displays **7-day rolling metrics**:
- **Yesterday's Performance**: Predictions graded in last 24 hours
- **7-Day Accuracy**: Win rate from last 7 days
- **30-Day ROI**: Return on investment from last 30 days

### The Problem

All 53 graded predictions have `graded_at` timestamps from **December 2-6, 2025**.

Today is **December 9, 2025**, which means:
- 7-day window: December 2-9 ✅ (should include Dec 2-6 predictions)
- But the check shows: **🕐 Graded in last 7 days: 0** ❌

This indicates the date calculation in the Trust Loop may be using a different timezone or the `graded_at` timestamps are older than expected.

## Sample Graded Prediction

From database inspection:
```
Event ID: debug_rockets_jazz_20251202
Status: PUSH
Graded At: 2025-12-06T15:03:54.535254+00:00
Units Won: 0.0
```

## Root Cause Analysis

1. **Grading Timestamps Are Old**: All 53 predictions were graded on December 6 or earlier
2. **7-Day Window Calculation**: The Trust Loop's 7-day lookback may not be capturing December 6 dates
3. **No Recent Grading**: Yesterday's completed games (Dec 8) weren't graded due to event ID mismatch errors

### Event ID Mismatch Issue

When attempting to grade yesterday's completed games:
```
Event 4aad97e094688744824efdf58d7c9565 not found in database
Event bd366abff77cb883ea4975dba944d50e not found in database
(repeated 36 times)
```

This prevents new predictions from being graded and populating the Trust Loop.

## Historical Data (53 Graded Predictions)

### Breakdown
- **Total**: 53 graded predictions
- **Collections**: Data exists in `monte_carlo_simulations` collection
- **Graded Period**: December 2-6, 2025
- **Current Gap**: No graded predictions since December 6

### What's Missing
- No predictions graded December 7-9
- Event lookup failures prevent grading of recent games
- Trust Loop shows empty because it looks for recent (7-day) data only

## Solutions

### Option 1: Fix Date Calculation (Immediate)
Update Trust Loop to properly calculate 7-day window:
- Verify timezone handling (UTC vs EST)
- Check if December 6 predictions should appear in "last 7 days"
- Current date: Dec 9, 7 days back = Dec 2 (should include Dec 2-6)

### Option 2: Fix Event ID Matching (Required)
Fix the event lookup issue in `result_grading.py`:
- Simulations have event IDs that don't match events in DB
- Need to improve team name matching or event ID generation
- This will allow yesterday's (Dec 8) games to be graded

### Option 3: Extend Time Window (Temporary Workaround)
Change Trust Loop to show 14-day or 30-day metrics instead of 7-day:
- Would immediately show the 53 existing predictions
- Provides visibility while waiting for new grading
- Less accurate reflection of "current" performance

## Recommendation

**Priority 1**: Fix the event ID mismatch issue
- The grading service can't find events for completed games
- This blocks all future Trust Loop updates
- Root cause: `Event X not found in database` errors

**Priority 2**: Verify 7-day date calculation
- December 6 should be within "last 7 days" from December 9
- Current implementation shows 0 despite 53 graded predictions existing
- May be timezone or date comparison bug

**Short-term**: Wait 24-48 hours for new games to complete, but event matching must be fixed first

## Technical Details

### Files Involved
- `backend/services/trust_metrics.py` - Calculates 7-day metrics
- `backend/services/result_grading.py` - Grades completed games
- `backend/scripts/check_trust_data.py` - Diagnostic script (shows 0 in last 7 days)
- `components/TrustLoop.tsx` - Frontend display

### Date Window Logic
```python
# From check_trust_data.py
seven_days_ago = datetime.utcnow() - timedelta(days=7)
recent_graded = db["monte_carlo_simulations"].count_documents({
    "graded": True,
    "graded_at": {"$gte": seven_days_ago}
})
```

If this returns 0 when graded_at = 2025-12-06, there's a date comparison issue.

## Next Steps

1. **Debug date calculation**: Why does Dec 6 not count as "last 7 days" from Dec 9?
2. **Fix event matching**: Resolve "Event not found" errors in grading service
3. **Monitor scheduler**: Ensure automatic grading runs every 2 hours
4. **Test manually**: Grade a single completed game to verify flow works

## Expected Timeline

Once fixes are applied:
- **Day 1**: Fix event matching + date calculation
- **Day 2**: New games complete and get graded
- **Day 3**: Trust Loop shows non-zero metrics (7-day accuracy, ROI)
- **Week 1**: Accumulate 20-30 graded predictions for meaningful statistics

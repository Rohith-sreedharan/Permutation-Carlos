# MODEL DIRECTION BUG - QUICK REFERENCE

## WHAT WAS BROKEN

### Screenshots Evidence:
1. **Purple Circle (Model Direction)**: Showed "Denver Nuggets +5.5"
2. **Model Preference Box**: Showed DIFFERENT team/line
3. **Debug Panel**: Red X marks - missing selection_ids, probability mismatches

### Root Cause:
Backend calculated `model_preference_selection_id` using broken logic:
```python
# WRONG
f"{event_id}_spread_{'home' if sharp_action == 'FAV' and spread < 0 else 'away'}"
# This doesn't match sharp_side_display team
```

Frontend showed wrong teams in Market/Fair spread displays.

---

## WHAT WAS FIXED

### 1. Backend - Correct selection_id Logic
**File**: `backend/core/monte_carlo_engine.py`

```python
# NEW - Matches sharp_side_display team
"model_preference_selection_id": f"{event_id}_spread_home" 
    if sharp_side_result.sharp_side_display.startswith(home_team_name) 
    else f"{event_id}_spread_away"
```

### 2. Frontend - Correct Spread Displays
**File**: `components/GameDetail.tsx`

```tsx
// Market Spread - show home team with home line
{market_spread_home < 0 
  ? `${home_team} ${market_spread_home.toFixed(1)}`
  : `${away_team} ${(-market_spread_home).toFixed(1)}`
}

// Fair Spread - use backend sharp_side_display
{sharpSideDisplay}
```

### 3. Deterministic Selection IDs
**New File**: `backend/core/selection_id_generator.py`

Generates hash-based IDs:
```python
"a3f7c21b8e9d4f05"  # Instead of "evt_123_spread_home"
```

### 4. Integrity Validation
Validates every simulation:
- All selection_ids present
- model_preference matches one selection
- model_direction == model_preference (LOCKED)

---

## VERIFICATION CHECKLIST

After deploying, check ONE game:

### Visual Check:
1. Purple circle (Model Direction): "Denver Nuggets +5.5"
2. Model Preference box: "Denver Nuggets +5.5" ← MUST MATCH
3. Market Spread column: Shows home team with market line
4. Fair Spread column: Shows sharp_side_display (same as Model Direction)

### Debug Panel Check:
1. Click 🔧 button (bottom right)
2. Verify: "INTEGRITY VIOLATIONS DETECTED: 0"
3. Verify: selection_ids are 16-char hashes (not "MISSING")
4. Verify: model_preference_selection_id matches home or away selection_id

---

## IF SOMETHING BREAKS

### Immediate Rollback:
1. Revert `monte_carlo_engine.py` lines 1313-1314:
```python
"model_preference_selection_id": f"{event_id}_spread_home",
```

2. Revert `GameDetail.tsx` lines 1361-1377 to use:
```tsx
{simulation.sharp_analysis.spread.sharp_side_display}
```

3. Delete `selection_id_generator.py` (optional feature)

### Check Backend Logs:
```bash
grep "SPREAD SELECTION INTEGRITY FAILED" backend/logs/*.log
```

### Check Frontend Console:
Look for: "ReferenceError" or "undefined sharp_side_display"

---

## WHAT THIS FIXES

✅ Model Direction now ALWAYS matches Model Preference
✅ No more "both teams show +" bug
✅ Market Spread shows correct team with correct sign
✅ Fair Spread shows model preferred team (from sharp_side_display)
✅ Deterministic selection_ids (stable across refreshes)
✅ Integrity validation catches future bugs
✅ Debug panel transparency for developers

---

## FILES CHANGED

1. `backend/core/monte_carlo_engine.py` - selection_id logic + validation
2. `backend/core/selection_id_generator.py` - NEW FILE (hash generation)
3. `components/GameDetail.tsx` - spread display logic

---

## DEPLOYMENT STEPS

1. Backend:
```bash
cd backend
python3 -m py_compile core/selection_id_generator.py core/monte_carlo_engine.py
# Should show: ✅ All files compile successfully
```

2. Frontend:
```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run build
# Check for TypeScript errors
```

3. Restart backend:
```bash
cd backend
./start.sh
```

4. Test ONE game manually (use verification checklist above)

5. If issues appear, rollback immediately (see rollback section)

---

## INVESTOR ANSWER

**Q**: "Why did Model Direction show one team but Model Preference showed another?"

**A**: "Backend calculated selection_ids using action logic ('FAV') instead of reading the actual team from sharp_side_display. We've now locked Model Direction and Model Preference to the same canonical source (`sharp_side_display`), added deterministic hash-based selection_ids, and implemented runtime integrity validation. Zero tolerance for cross-wire bugs."

---

## STATUS: ✅ READY FOR DEPLOYMENT

All files compile. Integrity validation active. Debug panel shows validation status.

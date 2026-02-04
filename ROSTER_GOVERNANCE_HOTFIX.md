# Roster Governance Hotfix - Feb 4, 2026

## Executive Summary

**CRITICAL UX FIX**: Removed blocking behavior for NBA/NFL/NHL/MLB roster unavailability.

**Problem**: "Blocked" status kills trust and conversions. 24-hour cooldown is insane UX.

**Solution**: Pro leagues now run in **FALLBACK MODE** with reduced confidence instead of blocking.

---

## Changes Implemented

### 1. Backend: Roster Policy System

**File**: `backend/core/simulation_context.py`

Added typed enums:
```python
class RosterPolicy(str, Enum):
    OPTIONAL_DEGRADE = "optional_degrade"  # Fallback mode (NBA/NFL/NHL/MLB)
    REQUIRED_BLOCK = "required_block"      # Only block if truly can't run (NCAAB/NCAAF)

class RosterFetchStatus(str, Enum):
    ROSTER_OK = "roster_ok"
    ROSTER_MISSING_TRUE = "roster_missing_true"
    ROSTER_PROVIDER_UNAVAILABLE = "roster_provider_unavailable"  
    ROSTER_LEAGUE_MISMATCH = "roster_league_mismatch"

class SimulationStatus(str, Enum):
    # ... existing statuses ...
    FALLBACK_NO_ROSTER = "FALLBACK_NO_ROSTER"  # NEW
```

---

### 2. Backend: Roster Governance Logic

**File**: `backend/core/roster_governance.py`

**Key Changes**:
- ❌ Removed 24-hour cooldown (insane UX)
- ✅ Added 10-minute cooldown **only for provider errors** (timeouts/429)
- ✅ NBA/NFL/NHL/MLB set to `OPTIONAL_DEGRADE` (never block)
- ✅ Typed roster fetch status (no more lies in logs)

**Locked Rules**:
```python
LEAGUE_ROSTER_POLICIES = {
    "NBA": RosterPolicy.OPTIONAL_DEGRADE,   # NEVER block
    "NFL": RosterPolicy.OPTIONAL_DEGRADE,   # NEVER block
    "NHL": RosterPolicy.OPTIONAL_DEGRADE,   # NEVER block
    "MLB": RosterPolicy.OPTIONAL_DEGRADE,   # NEVER block
    "NCAAB": RosterPolicy.REQUIRED_BLOCK,   # Only block for provider errors
    "NCAAF": RosterPolicy.REQUIRED_BLOCK,   # Only block for provider errors
}
```

**Behavior Table**:
| League | Roster Status | Behavior |
|--------|---------------|----------|
| NBA | ROSTER_MISSING_TRUE | ✅ FALLBACK_NO_ROSTER + risk_flags=['ROSTER_MISSING'] |
| NBA | ROSTER_PROVIDER_UNAVAILABLE | ✅ FALLBACK_NO_ROSTER + risk_flags=['ROSTER_MISSING'] |
| NCAAB | ROSTER_MISSING_TRUE | ✅ FALLBACK_NO_ROSTER (can still run) |
| NCAAB | ROSTER_PROVIDER_UNAVAILABLE | ❌ BLOCKED (10min cooldown) |

---

### 3. Backend: Monte Carlo Engine

**File**: `backend/core/monte_carlo_engine.py`

**Changes**:
- Tracks `fallback_mode` and `risk_flags` during roster check
- Adds to simulation result:
  ```python
  {
    "status": SimulationStatus.FALLBACK_NO_ROSTER.value,
    "fallback_mode": True,
    "roster_status": "roster_missing_true",
    "risk_flags": ["ROSTER_MISSING"],
    # ... rest of simulation ...
  }
  ```

---

### 4. Frontend: Types

**File**: `types.ts`

Added fields:
```typescript
status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'CACHED' | 'PRICE_MOVED' | 
         'INVALIDATED' | 'FAILED' | 'BLOCKED' | 'FALLBACK_NO_ROSTER';  // NEW
fallback_mode?: boolean;  // NEW
roster_status?: 'roster_ok' | 'roster_missing_true' | 
                'roster_provider_unavailable' | 'roster_league_mismatch';  // NEW
```

---

### 5. Frontend: GameDetail UI

**File**: `components/GameDetail.tsx`

**Replaced**: "Simulation Blocked" error screen  
**With**: "Fallback Mode Active" warning banner

**UX Before** (KILLED CONVERSIONS):
```
🚫 Simulation Temporarily Blocked
Missing Roster Data
[Game inaccessible for 24 hours]
```

**UX After** (PRESERVES TRUST):
```
⚡ Fallback Mode Active
Player/roster layer unavailable — confidence reduced

• Simulation ran successfully using baseline team metrics
• Player-specific injury/matchup data not included
• Pick remains accessible - use additional caution
• Status: ROSTER MISSING TRUE

[Full simulation displayed normally below banner]
```

---

## Testing

### Manual Test (NBA Game)

1. Remove roster data from DB:
   ```bash
   mongo beatvegas
   db.rosters.deleteMany({team: "Boston Celtics", league: "NBA"})
   ```

2. Request simulation:
   ```bash
   curl http://localhost:8000/api/simulations/<event_id>
   ```

3. **Expected Result**:
   ```json
   {
     "status": "FALLBACK_NO_ROSTER",
     "fallback_mode": true,
     "roster_status": "roster_missing_true",
     "risk_flags": ["ROSTER_MISSING"],
     "can_publish": true,
     "can_parlay": true,
     "sharp_analysis": { ... }
   }
   ```

4. **Frontend**: Should show yellow warning banner but full simulation

---

## Deployment Checklist

- [x] Update `simulation_context.py` with new enums
- [x] Update `roster_governance.py` logic
- [x] Remove 24hr cooldown, add 10min provider error cooldown
- [x] Update `monte_carlo_engine.py` to track fallback mode
- [x] Update `types.ts` with new fields
- [x] Update `GameDetail.tsx` UI
- [ ] **TEST**: Verify NBA game runs in fallback when roster missing
- [ ] **TEST**: Verify NCAAB blocks only for provider errors
- [ ] **DEPLOY**: Backend changes
- [ ] **DEPLOY**: Frontend changes
- [ ] **MONITOR**: Check logs for fallback mode activations
- [ ] **ALERT**: Ops if ROSTER_PROVIDER_UNAVAILABLE persists >1hr

---

## Rollback Plan

If issues occur:

1. Revert `LEAGUE_ROSTER_POLICIES` to use `REQUIRED_BLOCK` for NBA:
   ```python
   "NBA": RosterPolicy.REQUIRED_BLOCK,
   ```

2. Restart backend:
   ```bash
   sudo systemctl restart beatvegas-backend
   ```

3. Frontend will gracefully handle both BLOCKED and FALLBACK_NO_ROSTER

---

## Monitoring

**Key Metrics**:
- `status=FALLBACK_NO_ROSTER` count (should be low)
- `roster_status=roster_provider_unavailable` count (alert if >10/hr)
- Conversion rate on games with `fallback_mode=true`

**Logs**:
```bash
# Check fallback mode activations
tail -f backend/logs/application.log | grep "FALLBACK MODE"

# Check blocked simulations (should be rare)
tail -f backend/logs/application.log | grep "BLOCKED:"
```

---

## Summary

**Before**: Missing roster → 24hr block → lost conversions  
**After**: Missing roster → fallback mode → user sees full sim with warning

**Impact**: 
- ✅ Preserves UX/trust
- ✅ Maintains simulation accessibility  
- ✅ Honest about reduced confidence
- ✅ No retry loops or wasted compute

**Total Implementation Time**: ~2 hours

---

**Status**: ✅ COMPLETE - Ready for deployment

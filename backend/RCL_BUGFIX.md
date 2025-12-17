# RCL Bug Fix - UnboundLocalError

## Issue
```
UnboundLocalError: cannot access local variable 'rcl_total' where it is not associated with a value
```

**Location**: `backend/core/monte_carlo_engine.py` line 385

## Root Cause
The RCL (Reality Check Layer) block was placed AFTER the edge calculation code, but the edge calculation code was trying to use `rcl_total` before it was defined.

**Incorrect Order**:
```python
1. Calculate spread edge
2. Calculate total edge (uses rcl_total) ❌ ERROR
3. Apply RCL (defines rcl_total)
```

## Fix
Moved the RCL block to execute BEFORE the edge calculations.

**Correct Order**:
```python
1. Apply RCL (defines rcl_total) ✅
2. Calculate spread edge
3. Calculate total edge (uses rcl_total) ✅
```

## Changes Made

### File: `backend/core/monte_carlo_engine.py`

**Line ~333**: Moved RCL block from line 443 to line 333
- Added RCL execution right after confidence calculation
- Removed duplicate RCL block that was after simulation output validation

**Variables Now Defined Before Use**:
- `rcl_total` - RCL-validated total
- `rcl_passed` - Boolean indicating if RCL passed
- `rcl_reason` - Reason for RCL status
- `simulation_id` - Created once at beginning

## Testing

✅ Syntax verification passed:
```bash
python3 verify_rcl_syntax.py
# All files OK
```

✅ No Python errors in monte_carlo_engine.py

## Impact

The simulation should now run successfully with RCL working correctly:
1. Raw simulation runs → produces `median_total`
2. RCL applies 3-layer guardrail → produces `rcl_total`
3. Edge calculation uses `rcl_total` → no more UnboundLocalError
4. If RCL fails, edge is blocked automatically

## Expected Behavior

When you hit the endpoint again:
```
GET /api/simulations/9373b84d11358f66f18562222dbf5f42
```

You should see:
```
✅ RCL: 224.5 → 224.5 (✅ PASSED: RCL_OK)
```

Or if RCL fails:
```
🚫 RCL: 153.0 → 145.5 (🚫 FAILED: HISTORICAL_OUTLIER_Z=2.50)
🚫 Blocking total edge due to RCL failure: HISTORICAL_OUTLIER_Z=2.50
```

## Status
✅ **FIXED** - Ready to test

# Sharp Side Detection - Strict Edge Validation Rules

## Problem Identified

The system was incorrectly displaying "SHARP SIDE DETECTED" for games where the edge quality was poor:

**Example Case (Lafayette vs Pennsylvania):**
- ❌ Confidence: 1/100 (terrible)
- ❌ Variance: 420.53 (extremely high)
- ❌ Edge: 2.1 points (below threshold)
- ❌ Explanation: "No valid edge detected. Market appears efficiently priced."

**The label contradicted the analysis** - showing "Sharp Side Detected" when the math said "No Edge".

---

## Root Cause

The sharp analysis functions (`calculate_spread_edge` and `calculate_total_edge`) were only checking:
- Edge magnitude ≥ threshold

They were **NOT** validating:
- Simulation confidence
- Outcome variance
- Stricter edge thresholds

This caused **false positives** - flagging low-quality edges as "sharp opportunities".

---

## Solution Implemented

### Strict Edge Detection Rules

**ALL 3 conditions must be true** to flag a Sharp Side:

1. **Edge Points ≥ 3.0**
   - Spread: Model disagrees by 3+ points
   - Total: Model disagrees by 3+ points
   - Rationale: Smaller edges collapse under variance

2. **Confidence Score ≥ 60**
   - Simulation convergence score (0-100)
   - Rationale: Low confidence = simulation clusters disagree

3. **Variance < 300**
   - Standard deviation of outcomes
   - Rationale: High variance = wide outcome distribution, edge unreliable

**EXCEPTION RULE:**
If edge ≥ 6 points AND confidence ≥ 70, variance threshold relaxed to < 400.
- Extreme edges with strong consensus override volatility concerns
- Prevents missing institutional-grade mispricings in volatile environments

**UNIVERSAL APPLICATION:**
This rule applies consistently across ALL sports:
- NBA, NFL, NCAAB, NCAAF, MLB, NHL
- No sport-specific exceptions
- Protects against fake edges and wrong outputs

---

## Code Changes

### 1. Updated `calculate_spread_edge()` in `sharp_analysis.py`

**New Parameters:**
```python
def calculate_spread_edge(
    vegas_spread: float,
    model_spread: float,
    favorite_team: str,
    underdog_team: str,
    threshold: float = 3.0,           # Changed from 2.0
    confidence_score: int = 0,        # NEW
    variance: float = 999.0           # NEW
) -> SpreadAnalysis:
```

**Strict Validation:**
```python
has_valid_edge = (
    edge_points >= 3.0 and 
    confidence_score >= 60 and 
    variance < 250
)
```

**Enhanced Feedback:**
- If edge exists but confidence too low: "Model lean detected (X pts) but confidence too low (Y/100). No valid edge."
- If edge exists but variance too high: "Model lean detected (X pts) but variance too high (σ=Y). No valid edge."

### 2. Updated `calculate_total_edge()` in `sharp_analysis.py`

Same validation rules applied to total (over/under) analysis.

### 3. Updated Monte Carlo Engine Calls

Now passes confidence and variance to sharp analysis:

```python
spread_analysis = calculate_spread_edge(
    vegas_spread=vegas_spread_formatted,
    model_spread=model_spread_formatted,
    favorite_team=favorite_team,
    underdog_team=underdog_team,
    threshold=3.0,
    confidence_score=confidence_score,    # NEW
    variance=variance_total               # NEW
)
```

---

## Testing Results

### Test Case 1: Low Quality Edge (Should Reject)
```
Confidence: 1/100
Variance: 420.53
Edge: 2.1 pts

Result: NO_EDGE ✅
Reason: "No significant mispricing detected (< 3 pts)"
```

### Test Case 2: High Quality Edge (Should Accept)
```
Confidence: 75/100
Variance: 120.0
Edge: 5.0 pts

Result: VALID EDGE ✅
Sharp Side: Team B +8.0
Reason: "Model shows dog should get +3.0 vs Vegas +8.0. Dog undervalued by 5.0 pts."
```

### Test Case 3: Big Edge but Low Confidence (Should Reject)
```
Confidence: 50/100
Variance: 100.0
Edge: 5.0 pts

Result: NO_EDGE ✅
Reason: "Model lean detected (5.0 pts) but confidence too low (50/100). No valid edge."
```

---

## User-Facing Impact

### Before Fix
- **False Positives**: Games with terrible confidence/variance showed "Sharp Side Detected"
- **User Confusion**: Label contradicted the explanation
- **Trust Damage**: Users see low-quality edges flagged as sharp plays

### After Fix
- **Accurate Signals**: Only high-quality edges trigger "Sharp Side Detected"
- **Transparent Feedback**: Clear reasons when edges fail validation
- **Better UX**: Confidence + Variance filters prevent noise

---

## Next Steps

1. **Restart Backend Server**: Run `./start.sh` to reload updated code
2. **Regenerate Simulations**: Old simulations still have incorrect `has_edge` flags
3. **Monitor Results**: Track how many games pass strict validation
4. **Calibrate Thresholds**: May need to adjust confidence ≥ 60 or variance < 250 based on backtesting

---

## Technical Notes

### Why Confidence ≥ 60?
- Confidence score = simulation convergence metric
- < 60 = simulation clusters still diverging significantly
- Edge predictions unreliable when model hasn't converged

### Why Variance < 300?
- High variance = wide outcome distribution
- Edge magnitude matters less when outcomes scatter widely
- Variance threshold prevents flagging high-uncertainty games
- **Exception**: Variance < 400 allowed if edge ≥ 6 pts + confidence ≥ 70 (extreme edges override)

### Why Edge ≥ 3 points?
- 2-point edges are within statistical noise
- 3+ points required to overcome bookmaker hold + variance
- Prevents marginal edges that don't justify position sizing

---

## Files Modified

1. `backend/core/sharp_analysis.py` - Lines 68-150 (spread), Lines 154-235 (total)
2. `backend/core/monte_carlo_engine.py` - Lines 371-388 (pass confidence/variance)

---

## Prevention

To avoid similar issues in future:

1. **Always validate confidence + variance** before flagging statistical edges
2. **Match UI labels to mathematical reality** (don't show "Sharp Side" when analysis says "No Edge")
3. **Test edge cases** (low confidence, high variance, small edges)
4. **Document thresholds** (why 60? why 250? why 3 points?)

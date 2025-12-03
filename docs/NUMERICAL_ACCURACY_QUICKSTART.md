# Numerical Accuracy System - Quick Start Guide

## Overview

The Numerical Accuracy System ensures **every number shown to users comes from real, traceable sources**. No placeholders, no fake data, no silent fallbacks.

---

## For Backend Developers

### Running Simulations with Enforced Accuracy

```python
from core.monte_carlo_engine import MonteCarloEngine
from core.numerical_accuracy import validate_simulation_output

engine = MonteCarloEngine(num_iterations=50000)

# Run simulation (will raise ValueError if bookmaker line missing)
result = engine.run_simulation(
    event_id="abc123",
    team_a=team_a_data,
    team_b=team_b_data,
    market_context={
        'total_line': 225.5,  # REQUIRED - no fallback
        'current_spread': -3.5,
        'sport_key': 'basketball_nba'
    },
    iterations=50000
)

# Result contains:
# - median_total: 227.3 (from np.median(totals_array))
# - variance_total: 125.4 (for confidence calc)
# - confidence_score: 73 (tier-aware, formula-based)
# - over_probability: 0.573 (from simulation vs book line)
```

### Calculating Expected Value

```python
from core.numerical_accuracy import ExpectedValue

# Model says 58% win probability, book offers -110 odds
ev = ExpectedValue.calculate(model_prob=0.58, american_odds=-110)

print(f"EV per $1: ${ev.ev_per_dollar:.3f}")  # $0.074
print(f"Edge: {ev.edge_percentage:.1%}")      # 5.6%
print(f"Is EV+? {ev.is_ev_plus(current_tier=50000)}")  # True
```

### Tracking Closing Line Value

```python
from core.numerical_accuracy import ClosingLineValue

# At prediction time
clv = ClosingLineValue(
    event_id="abc123",
    prediction_timestamp=datetime.now(),
    model_projection=227.5,
    book_line_open=225.5,
    lean="over"
)

# After game closes
clv.calculate_clv(closing_line=226.5)

if clv.clv_favorable:
    print("✅ Line moved in our favor!")
    # open 225.5 → close 226.5 (moved toward our Over projection)
```

### Post-Game Recap

```python
from core.post_game_recap import PredictionRecord, FeedbackLogger

# Create prediction record
record = PredictionRecord(
    game_id="abc123",
    projected_total=227.5,
    confidence_score=73,
    volatility="MEDIUM",
    sim_count=50000,
    side_lean="home",
    total_lean="over"
)

# After game completes, add actual results
record.actual_total = 230
record.actual_winner = "home"

# Grade predictions
record.grade_predictions()

# View recap
print("\n".join(record.recap_notes))
# ✅ Over HIT: 230.0 > 225.5
# ✅ Side prediction HIT: home (58.0% confidence)
# CLV: Line moved ✅ favorable
```

---

## For Frontend Developers

### Using Confidence Tooltips

```tsx
import { ConfidenceTooltip } from '@/components/NumericalAccuracyComponents';

<ConfidenceTooltip 
  confidenceScore={simulation.confidence_score}
  volatility={simulation.volatility}
  simCount={simulation.iterations}
  tierLabel={simulation.tier_label}
/>
```

**What it shows:**
- Score with label: "73/100 (High)"
- Info icon with tooltip
- Tooltip explains: "Confidence measures STABILITY, not win probability"

### Using Risk Gauge

```tsx
import { RiskGauge } from '@/components/NumericalAccuracyComponents';

<RiskGauge 
  winProbability={0.58}  // 0.0 - 1.0
  label="Parlay Risk"
/>
```

**Color thresholds:**
- 🟢 Green: 60%+ (Low Risk)
- 🟡 Yellow: 45-59% (Medium Risk)
- 🟠 Orange: 30-44% (High Risk)
- 🔴 Red: <30% (Very High Risk)

### Using Strength Score Tooltip

```tsx
import { StrengthScoreTooltip } from '@/components/NumericalAccuracyComponents';

<StrengthScoreTooltip strengthScore={67} />
```

**What it explains:**
- Formula: Probability × EV × Correlation Stability
- "This is an analytical score, not a betting recommendation"

---

## Common Patterns

### Pattern 1: Display Projected Total

```tsx
// ❌ DON'T: Use hardcoded fallback
const projectedTotal = simulation?.projected_total || 225.5;

// ✅ DO: Show error if missing
const projectedTotal = simulation?.median_total;

{projectedTotal ? (
  <div>Projected Total: {projectedTotal.toFixed(1)}</div>
) : (
  <div className="text-red-400">⚠️ Projection unavailable</div>
)}
```

### Pattern 2: Calculate O/U Probabilities

```python
# ❌ DON'T: Use fallback book line
book_line = market_context.get('total_line') or round(projected_total)

# ✅ DO: Require real book line
book_line = market_context.get('total_line')
if book_line is None:
    raise ValueError("Bookmaker line required for O/U calculation")

ou_analysis = OverUnderAnalysis.from_simulation(totals_array, book_line)
```

### Pattern 3: Show Confidence with Context

```tsx
// ✅ GOOD: Use tooltip component
<ConfidenceTooltip 
  confidenceScore={72}
  volatility="MEDIUM"
  simCount={50000}
  tierLabel="Pro"
/>

// Plus optional banner for extreme values
{simulation.confidence_score < 40 && (
  <div className="bg-yellow-500/10 border border-yellow-500/30 p-3 rounded">
    ⚠️ Low-confidence simulation – high volatility expected.
    Treat as informational, not strong edge.
  </div>
)}
```

### Pattern 4: Edge Classification

```python
from core.numerical_accuracy import EdgeValidator

# Classify edge strength
classification = EdgeValidator.classify_edge(
    model_prob=0.58,
    implied_prob=0.52,
    confidence=72,
    volatility="MEDIUM",
    sim_count=50000,
    injury_impact=0.8
)

if classification == "EDGE":
    # All 6 conditions met - strong edge
    badge_color = "green"
    label = "Strong Edge"
elif classification == "LEAN":
    # Some edge but doesn't meet all criteria
    badge_color = "yellow"
    label = "Lean"
else:
    # No meaningful edge
    badge_color = "gray"
    label = "Neutral"
```

---

## API Response Examples

### Full Game Simulation Response

```json
{
  "simulation_id": "sim_abc123_20251201120000",
  "event_id": "abc123",
  "iterations": 50000,
  "sport_key": "basketball_nba",
  
  "median_total": 227.3,
  "mean_total": 227.8,
  "variance_total": 125.4,
  
  "team_a_win_probability": 0.5800,
  "team_b_win_probability": 0.4200,
  
  "over_probability": 0.5730,
  "under_probability": 0.4270,
  "total_line": 225.5,
  
  "confidence_score": 73,
  "tier_label": "Pro",
  "tier_stability_band": 0.06,
  "volatility": "MEDIUM",
  
  "debug_label": "[DEBUG: source=monte_carlo_engine, sims=50000, median=227.3, var=125.4]"
}
```

### 1H Simulation Response

```json
{
  "simulation_id": "sim_1H_abc123_20251201120000",
  "event_id": "abc123",
  "period": "1H",
  "iterations": 50000,
  
  "h1_median_total": 110.2,
  "h1_mean_total": 110.5,
  "h1_variance": 42.3,
  
  "bookmaker_line": 109.5,
  "book_line_available": true,
  
  "over_probability": 0.5420,
  "under_probability": 0.4580,
  
  "confidence_score": 68,
  "tier_label": "Pro",
  "volatility": "MEDIUM"
}
```

**Note:** If `book_line_available: false`, then `over_probability` and `under_probability` will be `null`.

---

## Error Handling

### Backend

```python
try:
    result = engine.run_simulation(...)
except ValueError as e:
    # Missing required data (e.g., no bookmaker line)
    logger.error(f"Simulation failed: {e}")
    return {"error": "Bookmaker line required", "status": 400}
```

### Frontend

```tsx
{simulation ? (
  <>
    <div>Projected Total: {simulation.median_total.toFixed(1)}</div>
    <div>Confidence: {simulation.confidence_score}/100</div>
  </>
) : error ? (
  <div className="text-red-400">
    ⚠️ Simulation data unavailable
  </div>
) : (
  <div>Loading...</div>
)}
```

---

## Debug Mode

Enable debug labels to see data sources:

```python
# In backend config
from core.numerical_accuracy import DEBUG_MODE
DEBUG_MODE = True  # Only in dev/staging
```

Then simulation results include:
```json
{
  "debug_label": "[DEBUG: source=monte_carlo_engine, sims=50000, median=227.3, var=125.4]"
}
```

Display in dev mode:
```tsx
{process.env.NODE_ENV === 'development' && simulation.debug_label && (
  <div className="text-xs text-gray-500 font-mono">
    {simulation.debug_label}
  </div>
)}
```

---

## Testing

### Unit Test Example

```python
from core.numerical_accuracy import OverUnderAnalysis
import numpy as np

def test_ou_analysis():
    totals = np.array([220, 225, 230, 235, 240])
    book_line = 227.5
    
    ou = OverUnderAnalysis.from_simulation(totals, book_line)
    
    assert ou.sims_over == 2  # 230, 235, 240
    assert ou.sims_under == 2  # 220, 225
    assert ou.over_probability == 0.5  # 2/(2+2)
```

### Integration Test Example

```python
async def test_full_simulation_pipeline():
    # Setup
    engine = MonteCarloEngine(num_iterations=10000)
    
    # Run simulation
    result = engine.run_simulation(
        event_id="test123",
        team_a=mock_team_a,
        team_b=mock_team_b,
        market_context={'total_line': 225.5, 'sport_key': 'basketball_nba'}
    )
    
    # Verify all required fields present
    assert 'median_total' in result
    assert 'variance_total' in result
    assert 'confidence_score' in result
    
    # Verify no fallbacks used
    assert result['total_line'] == 225.5  # Not projected total
    
    # Verify probabilities sum to ~1.0
    assert abs(result['over_probability'] + result['under_probability'] - 1.0) < 0.01
```

---

## Migration Checklist

If migrating existing code:

- [ ] Replace `avg_total_score` with `median_total`
- [ ] Remove all fallback book lines (use real lines or error)
- [ ] Update risk gauge thresholds (60/45/30, not 55/35)
- [ ] Add confidence tooltips to all confidence displays
- [ ] Use `OverUnderAnalysis.from_simulation()` for O/U calcs
- [ ] Replace hardcoded confidence with `ConfidenceCalculator.calculate()`
- [ ] Add debug labels in dev mode
- [ ] Log all predictions to feedback loop

---

## Support

- **Full Spec:** `docs/NUMERICAL_ACCURACY_SPEC.md`
- **Implementation Guide:** `docs/NUMERICAL_ACCURACY_IMPLEMENTATION.md`
- **API Docs:** See docstrings in `backend/core/numerical_accuracy.py`

**Remember:** If a value can't be computed from real data → show error, don't fake it.

**Trust dies the moment a user sees a number that obviously doesn't match reality.**

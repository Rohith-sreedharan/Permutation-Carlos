# BeatVegas Numerical Accuracy - Quick Reference Guide

## 🎯 Core Principle

**Every number shown to users MUST come from real, traceable sources.**
- NO placeholders
- NO hard-coded fallbacks  
- NO "safe" defaults
- If data is missing → show "data unavailable", NOT a fake number

---

## 📊 Key Validation Classes

### 1. SimulationOutput
**File:** `backend/core/numerical_accuracy.py`

**Purpose:** Enforce structure for all simulation outputs

**Usage:**
```python
from core.numerical_accuracy import SimulationOutput

output = SimulationOutput(
    median_total=225.5,
    mean_total=226.2,
    variance_total=156.3,
    home_win_probability=0.62,
    away_win_probability=0.38,
    h1_median_total=112.3,
    h1_variance=45.2,
    sim_count=50000,
    timestamp=datetime.now(timezone.utc)
)

# Validates automatically
output.validate()  # Raises ValueError if invalid
```

### 2. OverUnderAnalysis
**Purpose:** Calculate O/U probabilities from simulation vs book line

**Usage:**
```python
from core.numerical_accuracy import OverUnderAnalysis
import numpy as np

# From simulation results
totals_array = np.array([225.3, 228.1, 222.7, ...])  # N simulations
book_line = 226.5

ou_analysis = OverUnderAnalysis.from_simulation(totals_array, book_line)

print(f"Over probability: {ou_analysis.over_probability:.1%}")
print(f"Under probability: {ou_analysis.under_probability:.1%}")
print(f"Sims over: {ou_analysis.sims_over}/{ou_analysis.total_sims}")
```

### 3. ExpectedValue
**Purpose:** Calculate EV using proper probability ↔ odds conversion

**Usage:**
```python
from core.numerical_accuracy import ExpectedValue

ev = ExpectedValue.calculate(
    model_prob=0.58,  # From Monte Carlo
    american_odds=-110  # Book odds
)

print(f"EV per $1: ${ev.ev_per_dollar:.3f}")
print(f"Edge: {ev.edge_percentage * 100:.1f}%")
print(f"Model prob: {ev.model_probability:.1%}")
print(f"Implied prob: {ev.implied_probability:.1%}")

# Check if EV+
is_ev_plus = ev.is_ev_plus(
    min_edge=0.03,  # 3%
    min_sim_tier=25000,
    current_tier=50000
)
```

### 4. EdgeValidator
**Purpose:** Classify predictions as EDGE / LEAN / NEUTRAL

**Usage:**
```python
from core.numerical_accuracy import EdgeValidator

classification = EdgeValidator.classify_edge(
    model_prob=0.62,
    implied_prob=0.52,
    confidence=72,
    volatility="MEDIUM",
    sim_count=50000,
    injury_impact=0.8
)

print(classification)  # "EDGE", "LEAN", or "NEUTRAL"
```

**EDGE requires ALL 6 conditions:**
1. Model prob ≥ 5pp above implied ✓
2. Confidence ≥ 60 ✓
3. Volatility ≠ HIGH ✓
4. Sim power ≥ 25K ✓
5. Model conviction ≥ 58% ✓
6. Injury impact < 1.5 ✓

### 5. ConfidenceCalculator
**Purpose:** Calculate 0-100 confidence score (measures STABILITY, not win prob)

**Usage:**
```python
from core.numerical_accuracy import ConfidenceCalculator

confidence = ConfidenceCalculator.calculate(
    variance=156.3,
    sim_count=50000,
    volatility="MEDIUM",
    median_value=226.5
)

print(f"Confidence: {confidence}/100")
```

---

## 🔄 CLV Tracking Workflow

### Step 1: Log Prediction (When Making Prediction)
```python
from services.clv_tracker import CLVTracker

prediction_id = CLVTracker.log_prediction(
    event_id="game_123",
    model_projection=226.5,  # Our projection
    book_line_open=228.0,    # Opening line
    prediction_type="total",  # "total", "spread", "ml"
    lean="under",            # "over", "under", "home", "away"
    sim_count=50000,
    confidence=72
)
```

### Step 2: Update Closing Line (5-10 min before game)
```python
result = CLVTracker.update_closing_line(
    event_id="game_123",
    prediction_type="total",
    closing_line=226.0  # Line moved from 228 → 226 (in our favor!)
)

print(f"Favorable CLV: {result['favorable_clv_count']}/{result['predictions_updated']}")
```

### Step 3: Record Actual Result (After Game)
```python
CLVTracker.record_actual_result(
    event_id="game_123",
    actual_total=224.0,
    actual_margin=-6.0,
    winner="away"
)
```

### Step 4: Check Performance
```python
performance = CLVTracker.get_clv_performance(
    days=7,
    min_sim_count=25000
)

print(f"CLV Rate: {performance['favorable_percentage']:.1f}%")
print(f"Target Met: {performance['meets_target']}")  # Target: ≥ 63%
```

---

## 📝 Post-Game Recap Workflow

### Generate Recap
```python
from services.post_game_recap import PostGameRecap

recap = PostGameRecap.generate_recap(
    event_id="game_123",
    game_data={
        "home_team": "Lakers",
        "away_team": "Warriors",
        "sport": "basketball_nba"
    },
    predictions={
        "side_prediction": {
            "lean": "home",
            "probability": 0.62,
            "confidence": 72
        },
        "total_prediction": {
            "lean": "under",
            "probability": 0.58,
            "book_line": 228.0,
            "projected_total": 226.5
        },
        "sim_count": 50000,
        "confidence": 72,
        "volatility": "MEDIUM"
    },
    actual_results={
        "home_score": 115,
        "away_score": 109,
        "total": 224,
        "margin": 6,
        "winner": "home"
    }
)

print(recap["summary"])
# {
#   "hits": 2,
#   "misses": 0,
#   "hit_rate": 100.0,
#   "confidence_label": "High",
#   "performance_grade": "A"
# }
```

### Get Performance Trends
```python
trends = PostGameRecap.get_performance_trends(days=30)

print(f"Side predictions: {trends['by_prediction_type']['side']['hit_rate']}%")
print(f"Total predictions: {trends['by_prediction_type']['total']['hit_rate']}%")
print(f"High confidence games: {trends['by_confidence']['high_confidence_60_plus']['success_rate']}%")
```

---

## 🎚️ Simulation Tier Usage

### Backend
```python
from core.numerical_accuracy import SimulationTierConfig

tier_config = SimulationTierConfig.get_tier_config(50000)

print(tier_config["label"])  # "Pro"
print(tier_config["stability_band"])  # 0.06 (±6%)
print(tier_config["confidence_multiplier"])  # 0.95
print(tier_config["min_edge_required"])  # 0.03 (3%)
```

### Frontend
```typescript
import { getTierConfig, getSimPowerMessage } from '../utils/simulationTiers';

const tier = getTierConfig('pro');
console.log(tier.sims);  // 50000
console.log(tier.stability_band);  // 0.06

const message = getSimPowerMessage('pro', 'game');
// "Running at Pro tier (50,000 sims). You're getting high-resolution projections."
```

---

## 🚨 Error Handling

### Backend: Raise Errors, Don't Return Fake Data
```python
# ❌ WRONG
if not bookmaker_line:
    bookmaker_line = 45.5  # Fake fallback

# ✅ CORRECT
if not bookmaker_line:
    raise ValueError("No bookmaker line available - cannot calculate O/U probabilities")
```

### Frontend: Show Error States
```typescript
// ❌ WRONG
const total = simulation?.median_total || 45.5;

// ✅ CORRECT
if (!simulation?.median_total) {
  return <div className="text-red-400">Data unavailable</div>;
}
const total = simulation.median_total;
```

---

## 🔍 Debug Mode

### Enable in Backend
```python
# backend/core/numerical_accuracy.py
DEBUG_MODE = True  # Set to True for development

# Will show labels like:
# [DEBUG: source=simulation, sims=50000, median=226.5, var=156.3]
```

### Frontend
```typescript
import { getDebugLabel } from '../utils/simulationTiers';

const debugLabel = getDebugLabel(
  'simulation',
  50000,
  226.5,
  156.3,
  process.env.NODE_ENV === 'development'
);
```

---

## 📱 API Endpoints

### CLV Tracking
```bash
# Log prediction
POST /api/clv/log_prediction
{
  "event_id": "game_123",
  "model_projection": 226.5,
  "book_line_open": 228.0,
  "prediction_type": "total",
  "lean": "under",
  "sim_count": 50000,
  "confidence": 72
}

# Update closing line
POST /api/clv/update_closing_line
{
  "event_id": "game_123",
  "prediction_type": "total",
  "closing_line": 226.0
}

# Record result
POST /api/clv/record_result
{
  "event_id": "game_123",
  "actual_total": 224.0,
  "actual_margin": -6.0,
  "winner": "away"
}

# Get performance
GET /api/clv/performance?days=7&min_sim_count=25000
```

### Post-Game Recap
```bash
# Generate recap
POST /api/recap/generate
{
  "event_id": "game_123",
  "game_data": {...},
  "predictions": {...},
  "actual_results": {...}
}

# Get recent recaps
GET /api/recap/recent?days=7&limit=50

# Get performance trends
GET /api/recap/performance_trends?days=30

# Get specific recap
GET /api/recap/{event_id}
```

---

## 💡 Best Practices

### 1. Always Validate Simulation Outputs
```python
from core.numerical_accuracy import validate_simulation_output

try:
    sim_output = validate_simulation_output(results)
except ValueError as e:
    logger.error(f"Invalid simulation output: {e}")
    # Return error to frontend, don't fake it
```

### 2. Use Proper EV Calculation
```python
# ❌ WRONG: Heuristic/shortcut
ev = (model_prob - implied_prob) * 100

# ✅ CORRECT: Proper formula
ev = ExpectedValue.calculate(model_prob, american_odds)
```

### 3. Check All Edge Conditions
```python
# ❌ WRONG: Only checking one condition
if model_prob > implied_prob + 0.05:
    classification = "EDGE"

# ✅ CORRECT: Check all 6 conditions
classification = EdgeValidator.classify_edge(
    model_prob, implied_prob, confidence, 
    volatility, sim_count, injury_impact
)
```

### 4. Show Confidence Tooltip
```typescript
// Always include tooltip explaining confidence
<Tooltip content={formatConfidenceDisplay(confidence, volatility, simCount).tooltip}>
  <span>Confidence: {confidence}/100</span>
</Tooltip>
```

### 5. Log CLV for Every Prediction
```python
# At prediction time, always log for future validation
prediction_id = CLVTracker.log_prediction(...)
```

---

## 🎯 Key Metrics to Monitor

1. **CLV Rate:** Target ≥ 63% favorable
2. **Hit Rate by Confidence:**
   - High confidence (60+): Should be ≥ 60% accurate
   - Low confidence (<40): Can be <50% (that's why it's low confidence)
3. **EV+ Hit Rate:** % of EV+ bets that won
4. **Confidence Calibration:** Are 70% confidence games actually hitting 70%?

---

## 📚 Key Files Reference

### Backend
- `backend/core/numerical_accuracy.py` - All validation classes
- `backend/core/monte_carlo_engine.py` - Simulation engine
- `backend/services/analytics_service.py` - EV/edge calculations
- `backend/services/clv_tracker.py` - CLV tracking
- `backend/services/post_game_recap.py` - Recap generation
- `backend/routes/clv_routes.py` - CLV API
- `backend/routes/recap_routes.py` - Recap API

### Frontend
- `utils/simulationTiers.ts` - Tier configuration
- `components/SimulationPowerWidget.tsx` - Global widget
- `components/ParlayArchitect.tsx` - Enhanced UX
- `components/ConfidenceGauge.tsx` - Confidence display

---

## 🚀 Quick Start Checklist

- [ ] Import validation classes from `numerical_accuracy.py`
- [ ] Replace any hard-coded fallbacks with error handling
- [ ] Use `ExpectedValue.calculate()` for all EV calculations
- [ ] Use `EdgeValidator.classify_edge()` for edge classification
- [ ] Log all predictions with `CLVTracker.log_prediction()`
- [ ] Update closing lines before games start
- [ ] Record actual results after games end
- [ ] Generate post-game recaps for all games
- [ ] Monitor CLV performance weekly (target ≥ 63%)
- [ ] Review performance trends monthly
- [ ] Add confidence tooltips to all confidence displays
- [ ] Show tier information on all simulation-driven features
- [ ] Enable debug mode for development/testing

---

**Remember:** Trust dies the moment a user sees a number that doesn't match reality. Every number must be real, traceable, and accurate.

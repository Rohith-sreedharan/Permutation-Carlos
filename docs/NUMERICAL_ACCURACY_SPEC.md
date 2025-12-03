# BeatVegas Numerical Accuracy & Simulation Spec

## 0. Core Rule

**Every number the user sees must come from a real, traceable source.**

- ❌ NO placeholders
- ❌ NO hard-coded fallbacks  
- ❌ NO "safe" defaults
- ✅ If a value cannot be computed from real data → **throw error or show "data unavailable"**

**Trust dies the moment a user sees a total or % that obviously doesn't match reality.**

---

## 1. Non-Negotiable Accuracy Requirements

These are **hard requirements**. If any of these are wrong or approximated, the whole system becomes unreliable:

1. ✅ **Projected totals** (full game + 1H) must use **real simulation output**
2. ✅ **Win probabilities** must come from **Monte Carlo distributions** (not heuristics)
3. ✅ **Over/Under %** must be calculated from **simulation counts vs book line**
4. ✅ **EV** must use **proper probability ↔ odds conversion**
5. ✅ **CLV** (closing line value) must be **tracked and based on real lines**
6. ✅ **Simulation tiers** (10K/25K/50K/100K) must **actually change stability/variance** – not just labels

**If any of these need to "fallback" → the UI for that metric must show an error state, not a fake number.**

---

## 2. Simulation Outputs – What MUST Come From the Engine

### 2.1 Full-Game Projected Total

**Source of truth:** `monte_carlo_engine.py`

```python
# Let total_points[i] = home_score + away_score in simulation i
totals_array = np.array(results["totals"])

# For N simulations:
median_total = float(np.median(totals_array))  # PRIMARY projection
mean_total = float(np.mean(totals_array))
variance_total = float(np.var(totals_array))  # Store for confidence calc
```

**UI Display:**
- "Projected Total" = `median_total` (rounded to 1 decimal)
- "Distribution variance" = `variance_total` (used for volatility/confidence)

**Absolutely NOT allowed as sources:**
- ❌ Static constants (e.g., 45.5, 41.5)
- ❌ Team average points
- ❌ Bookmaker line
- ❌ Any default/placeholder

**If the simulation fails → don't show "Projected Total" at all.**

---

### 2.2 1H Projected Total

**Must come from the 1H simulation module**, not from full game extrapolation.

```python
# Let h1_points[i] = 1H home_score + away_score in simulation i
h1_median_total = float(np.median(h1_totals_array))
h1_variance = float(np.var(h1_totals_array))
```

**UI Display:**
- "Projected 1H Total" = `h1_median_total`
- 1H O/U win% based **ONLY on 1H sim distribution**

**No shortcuts allowed:**
- ❌ No "full game total ÷ 2"
- ❌ No "team 1H averages"
- ❌ No placeholders

**If 1H engine fails → hide 1H projected total & show "1H model unavailable".**

---

### 2.3 Win Probability (Side / ML)

For each simulation:
```python
# Determine winner per sim
wins_home = sum(1 for result in results if result['winner'] == 'home')
wins_away = N - wins_home

# Calculate probabilities
home_win_p = wins_home / N
away_win_p = wins_away / N
```

These numbers feed:
- Win probability %
- Risk gauge
- Parlay leg win probabilities
- "Edge vs implied probability"

**No heuristics, no Elo, no "blend" here unless explicitly designed.**

---

### 2.4 Over/Under % Logic

Given a bookmaker line `L`:

```python
from core.numerical_accuracy import OverUnderAnalysis

# Calculate from simulation distribution
ou_analysis = OverUnderAnalysis.from_simulation(totals_array, book_line)

# Results:
ou_analysis.sims_over      # count(total_points[i] > L)
ou_analysis.sims_under     # count(total_points[i] < L)
ou_analysis.sims_push      # count(total_points[i] == L)
ou_analysis.over_probability   # sims_over / (sims_over + sims_under)
ou_analysis.under_probability  # sims_under / (sims_over + sims_under)
```

**Same logic for 1H totals / alt lines.**

---

## 3. Expected Value (EV) – Correct Formula

For each outcome:

### Step 1: Convert book odds to implied probability

```python
# American odds
if odds > 0:
    implied_p = 100 / (odds + 100)
else:
    implied_p = abs(odds) / (abs(odds) + 100)
```

### Step 2: Use simulation probability `p_model` from Monte Carlo

### Step 3: Expected Value per $1 staked

```python
from core.numerical_accuracy import ExpectedValue

ev = ExpectedValue.calculate(model_prob=0.58, american_odds=-110)

# Returns:
ev.model_probability        # From simulation
ev.implied_probability      # From odds
ev.decimal_odds            # Converted
ev.ev_per_dollar           # p_model * (decimal_odds - 1) - (1 - p_model)
ev.edge_percentage         # p_model - implied_p
```

### EV+ Hit Rate Tracking

Mark a bet as **EV+** when:
- `edge_p >= 0.03` (3 percentage points)
- Book line exists
- Sim tier >= 25K

Long-term performance metric: **% of EV+ bets that actually won**

---

## 4. Closing Line Value (CLV)

We need CLV logging for model validation.

```python
from core.numerical_accuracy import ClosingLineValue

# At prediction time
clv = ClosingLineValue(
    event_id="...",
    prediction_timestamp=now,
    model_projection=227.5,
    book_line_open=225.5,
    lean="over"
)

# At closing time
clv.calculate_clv(closing_line=226.5)
# clv.clv_favorable = True (line moved from 225.5 → 226.5 in our favor)
```

**Track:**
- % of times our model projection is "on the right side" of the closing move
- **Target: ≥63% over time**

CLV doesn't show to retail users directly at first, but the engine **MUST log it** per event + per tier for future analytics.

---

## 5. Simulation Tiers & Stability

**Tiers:** 10K, 25K, 50K, 100K simulations per game.

These must **change the shape and stability** of the outputs – not just labels.

### 5.1 Stability Mapping

```python
from core.numerical_accuracy import SimulationTierConfig

tier = SimulationTierConfig.get_tier_config(sim_count=50000)
# Returns:
# {
#   "label": "Pro",
#   "stability_band": 0.06,  # ±6%
#   "confidence_multiplier": 0.95,
#   "min_edge_required": 0.03
# }
```

More sims → tighter distribution → higher confidence score & tighter intervals.

### 5.2 UX: Simulation Power Widget

```typescript
const TIERS = {
  starter: { label: "Starter", sims: 10000 },
  core: { label: "Core", sims: 25000 },
  pro: { label: "Pro", sims: 50000 },
  elite: { label: "Elite", sims: 100000 }
};

const MAX_SIMS = 100000;
```

**Global widget:**
- Simulation Power: [Tier Label] – {sims} sims/game
- Progress bar = sims / MAX_SIMS

**On game page under Monte Carlo heading:**
- "Monte Carlo Simulation ({sims.toLocaleString()} iterations – {Tier Label} cap)"
- Line below: "Higher tiers re-run this matchup at 25K–100K sims for tighter projections."

**For public content used in marketing:** Always run at 100K sims.

---

## 6. Confidence Score & Volatility

**Confidence Score is NOT win probability.**

### 6.1 Definition

**Confidence Score (0–100):** Measures stability of simulation outputs

```python
from core.numerical_accuracy import ConfidenceCalculator

confidence = ConfidenceCalculator.calculate(
    variance=125.4,
    sim_count=50000,
    volatility="MEDIUM",
    median_value=225.5
)
# Returns: 73 (High confidence)
```

**Rough mapping:**
- Low variance + high sim power → high confidence
- High variance / coin-flip game → low confidence

### 6.2 UI Messaging

**Add tooltip next to Confidence:**

```
Confidence measures how stable the simulation output is.

• Low confidence = wide distribution / volatile game
• High confidence = tight distribution / predictable game

Low confidence does not mean the model is wrong – it means 
the matchup is inherently swingy.
```

**Banner rules:**
- If `Confidence < 40`: Yellow banner → "Low-confidence simulation – high volatility expected. Treat as informational, not strong edge."
- If `Confidence > 70`: Green banner → "High-confidence simulation – strong alignment across simulations, market lines and correlation data."

**Tie to tier when not at top:**
- "Confidence limited by {Tier Label} (10K sims). Higher tiers use up to 100K sims for more stable outcomes."

---

## 7. "Real Edge" vs "Lean" Logic

Define a **REAL EDGE** only when **ALL** of these are true:

```python
from core.numerical_accuracy import EdgeValidator

classification = EdgeValidator.classify_edge(
    model_prob=0.58,
    implied_prob=0.52,
    confidence=72,
    volatility="MEDIUM",
    sim_count=50000,
    injury_impact=0.8
)
# Returns: "EDGE", "LEAN", or "NEUTRAL"
```

**Requirements for EDGE:**
1. Model win probability ≥ 5pp above implied probability
2. Confidence ≥ 60/100
3. Volatility ≠ "HIGH"
4. Sim Power ≥ 25K (no edges for 10K sims)
5. EV positive and distribution favors one side by ≥ 58%
6. Injury impact stable (< 1.5 on injury impact metric)

**If ANY condition fails → classify as LEAN, not EDGE.**

---

## 8. Parlay Architect – Required UX Changes

### 8.1 AI Confidence
- ❌ Never display 0.0%
- ✅ Show:
  - Raw Confidence % (from sims)
  - Adjusted Confidence Grade (A/B/C) based on simulation stability, correlation filter, injury impact
- ✅ Tooltip: "Adjusted Confidence combines simulation stability, correlation safety, and injury impact. It is not a guarantee, just a measure of model stability."

### 8.2 Strength Score Tooltip
- Current: 35 / 100 looks bad without context
- ✅ Add tooltip: "Strength Score = Probability × Expected Value × Correlation Stability (0–100). This is an analytical score, not a betting recommendation."
- ✅ Add subtle gradient glow behind score to make it feel premium

### 8.3 Risk Gauge Thresholds
**Change color bands to:**
- 🟢 Green: 60%+ win probability
- 🟡 Yellow: 45–59%
- 🟠 Orange: 30–44%
- 🔴 Red: <30%

**These thresholds should be consistent everywhere.**

### 8.4 Header & Hype
Replace "4-Leg AI Parlay Generated" with:
- **"AI-Optimized Parlay Generated (Correlation-Safe Build)"**
- Subtext: "Leg synergy validated through {SIM_POWER} Monte Carlo simulations."

### 8.5 "Why This Parlay" Section
Below summary, add bullets populated from engine flags:
- ✓ Correlation-safe direction
- ✓ High-EV anchor leg
- ✓ Confidence curve stable
- ✓ No injury volatility red flags
- ✓ All legs passed correlation filter

### 8.6 Paywall Upgrade Copy
Bottom block:
- **Header:** "Unlock Full AI Parlay + {SIM_POWER}-Simulation Report ($9.99)"
- **Bullets:**
  - ✔ Leg-by-leg win %
  - ✔ EV calculation
  - ✔ Correlation map
  - ✔ Risk profile breakdown
  - ✔ Full {SIM_POWER} simulation data
  - ✔ Tier classification
- Add tiny lock icon next to each blurred leg

### 8.7 Refresh Timer Banner
Top banner:
- "⏳ This AI parlay refreshes every 30 minutes. Unlock this version before it regenerates."
- Add small pulsing timer animation

---

## 9. Simulation Power as Upsell – Game & Parlay

Wherever we show sim outputs:
- Show `{SIM_POWER} iterations – {Tier Label} cap`
- If not Elite: "Higher tiers run up to 100,000 simulations for tighter projections and more precise edges."

**Trigger upgrade prompts on:**
- High-volatility games
- Multi-leg parlays (3+ legs)
- Hitting daily sim caps (if used)

All prompts open the same upgrade modal with tier explanations.

---

## 10. Post-Game Recap & Feedback Loop

### 10.1 Auto Recap Per Game

```python
from core.post_game_recap import PredictionRecord, FeedbackLogger

# After game ends
record = PredictionRecord(
    game_id="...",
    projected_total=225.5,
    actual_total=228,
    confidence_score=72,
    volatility="MEDIUM",
    ...
)

record.grade_predictions()
# Generates:
# - Winner Result: HIT / MISS
# - Confidence Score: 72/100 (High)
# - Volatility flag
# - Sim Tier used
# - Model leans with hit/miss
# - Short notes
```

### 10.2 Feedback Loop Logging

For every prediction, save:
- Game ID, Timestamp, Tier / sim_count
- Projection (side, total, 1H, props)
- Probabilities, EV, Confidence, Volatility
- Book lines at prediction
- CLV after close
- Final result (win / loss / push)

This doesn't have to update the model yet, but it **MUST be stored** so we can:
- Audit bad calls (like 70% Overs that die)
- See which modules are off (1H vs full game)
- Train future calibration models

---

## 11. Dev-Mode Debug Labels

In dev mode only, add a small debug line near totals:

```python
from core.numerical_accuracy import get_debug_label

debug = get_debug_label(
    source="simulation",
    sim_count=50000,
    median_total=225.5,
    variance=125.4
)
# Returns: "[DEBUG: source=simulation, sims=50000, median=225.5, var=125.4]"
```

If any value does not come from the simulation engine → debug label must change and we treat that as a bug.

---

## 12. Final Note

**Every numeric field** (totals, win %, EV, confidence, volatility, risk gauges, strength scores) **must have a clear data source and a clear formula.**

**No silent fallbacks.** If something fails, the UI should show an error / "data unavailable" rather than a fake number.

Once these are implemented and we validate them on a few slates, we'll be in position to start tuning and scaling with real trust.

---

## Implementation Files

### Backend
- `backend/core/numerical_accuracy.py` - Core validation and data integrity enforcement
- `backend/core/post_game_recap.py` - Post-game feedback loop and grading
- `backend/core/monte_carlo_engine.py` - Updated with numerical accuracy enforcement

### Frontend
- `components/NumericalAccuracyComponents.tsx` - Confidence tooltips, risk gauge, strength score tooltips

### Usage Example

```typescript
import { ConfidenceTooltip, RiskGauge, StrengthScoreTooltip } from './NumericalAccuracyComponents';

// In your component
<ConfidenceTooltip 
  confidenceScore={72}
  volatility="MEDIUM"
  simCount={50000}
  tierLabel="Pro"
/>

<RiskGauge 
  winProbability={0.58}
  label="Parlay Risk"
/>

<StrengthScoreTooltip 
  strengthScore={67}
/>
```

---

## Testing Checklist

- [ ] Verify all projected totals come from simulation (no fallbacks)
- [ ] Verify O/U probabilities calculated against bookmaker lines
- [ ] Verify confidence score changes with tier (10K vs 100K)
- [ ] Verify EV calculations use proper formula
- [ ] Verify CLV logging works for all predictions
- [ ] Verify 1H projections DON'T use "full game / 2"
- [ ] Verify error states shown when simulation fails
- [ ] Verify risk gauge thresholds (60%/45%/30%)
- [ ] Verify confidence tooltips explain stability vs win probability
- [ ] Verify debug labels in dev mode show real sources

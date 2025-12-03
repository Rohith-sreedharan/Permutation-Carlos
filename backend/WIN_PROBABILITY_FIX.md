# Win Probability Fix - Technical Analysis & Solution

## 🔍 DIAGNOSIS

### Current Behavior (User Report)
```
Win Probability: 40.6% (Chicago St)
BeatVegas Edge: +9.3 pts deviation
```

**Problem:** A +9.3 point edge should correlate to ~65-75% win probability, not 40.6%.

---

## ✅ BACKEND ANALYSIS - **CODE IS CORRECT**

### Location: `backend/core/monte_carlo_engine.py` (Lines 302-355)

```python
# Calculate Win Probabilities from simulation counts (NO HEURISTICS)
home_win_probability = float(results["team_a_wins"] / iterations)
away_win_probability = float(results["team_b_wins"] / iterations)

# Validate probabilities sum to ~1.0
prob_sum = home_win_probability + away_win_probability
if abs(prob_sum - 1.0) > 0.01:
    logger.warning(f"Win probability sum = {prob_sum:.4f} (expected 1.0)")

simulation_result = {
    "team_a_win_probability": round(home_win_probability, 4),
    "team_b_win_probability": round(away_win_probability, 4),
    "win_probability": round(home_win_probability, 4),  # For home team
    ...
}
```

**✅ Correct Implementation:**
- Win probability = (team_a_wins / total_iterations)
- Directly from Monte Carlo simulation outcomes
- NOT from market odds or heuristics

---

## 🔍 ROOT CAUSE ANALYSIS

### Hypothesis 1: Team Perspective Mismatch ⚠️ **MOST LIKELY**

The issue is likely **which team** is "Team A" vs "Home Team":

```python
# In monte_carlo_engine.py:
"win_probability": round(home_win_probability, 4),  # For home team

# But in GameDetail.tsx:
const winProb = simulation.win_probability ?? simulation.team_a_win_probability ?? 0.5;
```

**Problem:**
- If Chicago St is the AWAY team but shown as the underdog
- Backend returns `home_win_probability` (which is 59.4% for the HOME team)
- Frontend displays it as Chicago St's win probability (40.6% = 100% - 59.4%)
- But the +9.3 edge is calculated from the HOME team's perspective

**Verification Needed:**
```javascript
// In GameDetail.tsx, add this debug log:
console.log('Win Prob Debug:', {
  home_team: event.home_team,
  away_team: event.away_team,
  team_a_win_prob: simulation.team_a_win_probability,
  team_b_win_prob: simulation.team_b_win_probability,
  win_probability: simulation.win_probability,
  displayed_team: event.home_team  // Which team is the prob for?
});
```

---

### Hypothesis 2: Simulation Results Mismatch

The simulation might be correct, but the **edge calculation** is using different teams:

```javascript
// BeatVegas Edge box shows:
Model Spread: +9.3 (vs market)

// But calculated from:
Math.abs((simulation.projected_score || totalLine) - (simulation.vegas_line || totalLine))
```

**Issue:** This doesn't account for which team has the edge.

---

## 🛠️ PROPOSED FIX

### Fix 1: Clarify Team Perspective in Frontend

Update `GameDetail.tsx` to explicitly show which team the probability is for:

```typescript
// BEFORE:
<div className="text-xs text-light-gray mt-2">{event.home_team}</div>

// AFTER:
<div className="text-xs text-light-gray mt-2">
  {event.home_team} Win Probability
  {winProb < 0.5 && <span className="text-bold-red ml-1">(Underdog)</span>}
  {winProb > 0.5 && <span className="text-neon-green ml-1">(Favorite)</span>}
</div>
```

---

### Fix 2: Add Simulation Debug Endpoint

Create a debug endpoint to verify data integrity:

```python
# backend/routes/simulation_routes.py

@router.get("/debug/{event_id}")
async def debug_simulation(event_id: str):
    """Debug endpoint to verify simulation data integrity"""
    sim = db.monte_carlo_simulations.find_one({"event_id": event_id})
    event = db.events.find_one({"event_id": event_id})
    
    if not sim:
        raise HTTPException(404, "Simulation not found")
    
    return {
        "event": {
            "home_team": event.get("home_team"),
            "away_team": event.get("away_team"),
            "home_odds": event.get("bookmakers", [{}])[0].get("home", 0),
            "away_odds": event.get("bookmakers", [{}])[0].get("away", 0)
        },
        "simulation": {
            "team_a_win_probability": sim.get("team_a_win_probability"),
            "team_b_win_probability": sim.get("team_b_win_probability"),
            "win_probability": sim.get("win_probability"),
            "team_a": sim.get("team_a"),  # Which team is Team A?
            "team_b": sim.get("team_b"),
            "avg_margin": sim.get("avg_margin"),
            "median_total": sim.get("median_total"),
            "vegas_line": sim.get("vegas_line"),
            "projected_score": sim.get("projected_score")
        },
        "integrity_check": {
            "prob_sum": sim.get("team_a_win_probability", 0) + sim.get("team_b_win_probability", 0),
            "expected": 1.0,
            "valid": abs(sim.get("team_a_win_probability", 0) + sim.get("team_b_win_probability", 0) - 1.0) < 0.01
        }
    }
```

---

### Fix 3: Enforce Home Team Consistency

Ensure `team_a` ALWAYS = `home_team`:

```python
# In monte_carlo_engine.py run_simulation():

# BEFORE (implicit assumption):
team_a_data = get_team_data_with_roster(event.get("home_team", "Team A"))

# AFTER (explicit enforcement):
home_team = event.get("home_team")
away_team = event.get("away_team")

if not home_team or not away_team:
    raise ValueError("Event must have home_team and away_team")

# ALWAYS assign home = team_a, away = team_b
team_a_data = get_team_data_with_roster(home_team, sport_key, is_home=True)
team_b_data = get_team_data_with_roster(away_team, sport_key, is_home=False)

# Store in result for clarity:
simulation_result = {
    "team_a": home_team,  # EXPLICIT
    "team_b": away_team,  # EXPLICIT
    "team_a_win_probability": home_win_probability,  # Home team
    "team_b_win_probability": away_win_probability,  # Away team
    "win_probability": home_win_probability,  # ALWAYS home team
    ...
}
```

---

### Fix 4: Add Spread-to-Probability Validation

Add a sanity check to ensure win probability aligns with point spread:

```python
# In monte_carlo_engine.py after calculating probabilities:

expected_spread = avg_margin / iterations
expected_win_prob_from_spread = 1 / (1 + math.exp(-expected_spread / 12))  # Logistic approximation

deviation = abs(home_win_probability - expected_win_prob_from_spread)
if deviation > 0.15:  # >15% deviation is suspicious
    logger.warning(
        f"Win probability ({home_win_probability:.1%}) deviates from spread-implied "
        f"({expected_win_prob_from_spread:.1%}) by {deviation:.1%}. "
        f"Spread: {expected_spread:.1f}"
    )
```

---

## 📊 TESTING PLAN

### Step 1: Add Debug Logging
```python
# In run_simulation():
logger.info(f"""
Simulation Complete: {event_id}
  Home Team: {home_team}
  Away Team: {away_team}
  Home Win Prob: {home_win_probability:.1%}
  Away Win Prob: {away_win_probability:.1%}
  Avg Margin: {avg_margin / iterations:.1f} (favors {'Home' if avg_margin > 0 else 'Away'})
  Iterations: {iterations}
""")
```

### Step 2: Frontend Debug Panel
```typescript
// In GameDetail.tsx, add temporary debug section:
{process.env.NODE_ENV === 'development' && (
  <div className="bg-yellow-500/10 border border-yellow-500/30 p-4 rounded mb-4">
    <h4 className="text-yellow-400 font-bold mb-2">DEBUG INFO</h4>
    <pre className="text-xs text-white">
      {JSON.stringify({
        home_team: event.home_team,
        away_team: event.away_team,
        team_a: simulation.team_a,
        team_b: simulation.team_b,
        team_a_win_prob: simulation.team_a_win_probability,
        team_b_win_prob: simulation.team_b_win_probability,
        win_probability: simulation.win_probability,
        displayed_winProb: winProb
      }, null, 2)}
    </pre>
  </div>
)}
```

### Step 3: Verify with Known Game
Run simulation on a game where the favorite is obvious:
- Warriors (-12.5) vs Wizards
- Expected: Warriors ~85% win prob
- If showing Wizards 15% → Team perspective correct
- If showing Warriors 15% → Team mismatch bug

---

## 🎯 IMMEDIATE ACTION

1. **Add debug endpoint** (5 min)
2. **Add frontend debug panel** (2 min)
3. **Test with live game** (5 min)
4. **Verify team_a = home_team** (check one simulation in DB)
5. **Apply fix based on findings**

---

## 📝 EXPECTED OUTCOME

After fix:
```
Win Probability: 68.3% (Home Team - Favorite)
BeatVegas Edge: +9.3 pts deviation
Spread: Home -9.3

✅ Alignment: 68.3% win prob ≈ -9.3 spread (mathematically consistent)
```

The issue is almost certainly **team perspective labeling**, not the calculation itself.

# BeatVegas Trust Loop & Safety Architecture

## Overview
This document explains how the trust loop (feedback/learning system) integrates with the new global safety engine to continuously improve while maintaining strict guardrails.

---

## Trust Loop Architecture

### **1. REAL-TIME CYCLE (Per Simulation Request)**

```python
User requests simulation for Game X
    ↓
[STEP 1] Detect context (championship? postseason? rematch?)
    ↓
[STEP 2] Apply sport-specific regime logic
    - NCAAF: pace compression, RZ suppression, etc.
    - NFL: prevent defense, kneeldowns, etc.
    - NBA: intentional fouling, garbage time, etc.
    ↓
[STEP 3] Run Monte Carlo simulation (10K-100K iterations)
    ↓
[STEP 4] Safety Engine evaluation:
    - Calculate divergence_score (model vs market)
    - Calculate environment_risk (championship penalty)
    - Calculate variance_risk (distribution width)
    - Check weather validity (NCAAF/NFL)
    - Validate model-market ID matching
    ↓
[STEP 5] Determine output_mode:
    - HIGH RISK → exploration_only (Lane A)
    - LOW RISK → eligible_for_pick (Lane B)
    ↓
[STEP 6] Store simulation with full context:
    {
        simulation_id: "abc123",
        event_id: "xyz789",
        model_total: 49.3,  # Internal only
        market_total: 52.5,
        divergence_score: 3.2,
        output_mode: "exploration_only",
        risk_score: 0.72,
        suppression_reasons: ["divergence > threshold"],
        regime_flags: {
            is_championship: true,
            adjustments_applied: ["pace_compression", "rz_suppression"]
        },
        confidence: 0.62,
        variance: 85.3,
        timestamp: "2025-12-07T10:30:00Z"
    }
    ↓
[STEP 7] Return to user:
    - Lane A: Show "informational only" with warnings
    - Lane B: Eligible for "BeatVegas Edge" if passes publishing rules
```

---

### **2. EVERY 2 HOURS CYCLE (Automated Grading)**

**Implemented in:** `backend/services/result_grading.py`  
**Triggered by:** `backend/services/scheduler.py`

```python
Every 2 hours (via APScheduler):
    ↓
[STEP 1] Fetch completed games from last 24-48 hours
    - Query events where commence_time < now - 3 hours
    - Status = "completed" or "final"
    ↓
[STEP 2] For each completed game:
    - Fetch actual final score from Odds API
    - Find all predictions/simulations for this game
    ↓
[STEP 3] Grade each prediction:
    actual_total = home_score + away_score
    model_error = abs(actual_total - model_total)
    
    # Over/Under grading
    if actual_total > market_total:
        actual_result = "over"
    else:
        actual_result = "under"
    
    correct = (predicted_direction == actual_result)
    
    # Edge calculation
    edge_accuracy = how far model was from actual vs market
    
    # Confidence calibration
    confidence_bucket = round(confidence * 20) / 20  # 0.60-0.65, etc.
    ↓
[STEP 4] Update trust metrics in database:
    - predictions collection: add "graded" field with outcome
    - trust_metrics collection: update rolling stats
        {
            confidence_bucket: "60-65%",
            total_bets: 47,
            wins: 28,
            win_rate: 59.6%,  # Should match confidence!
            avg_model_error: 6.2,
            environment_type: "championship",
            sport: "americanfootball_ncaaf"
        }
    ↓
[STEP 5] Check calibration:
    - If 60-65% bucket only wins 52% → confidence overinflated
    - If model_error consistently high for championships → adjust regime
    - If divergence > 15pts consistently wrong → tighten limits
    ↓
[STEP 6] Log learnings:
    logger.info("Championship NCAAF: 15 games graded, avg error 8.2pts, 
                 pace compression working (vs 12.4pts before)")
```

---

### **3. WEEKLY CYCLE (Strategic Learning)**

**Run:** Every Sunday night (manual or automated)

```python
Weekly analysis:
    ↓
[STEP 1] Aggregate all graded predictions from past 7 days
    - Group by: sport, environment (regular/championship), confidence bucket
    ↓
[STEP 2] Compute performance metrics:
    - Win rate by confidence bucket (calibration check)
    - Average model error by environment
    - Divergence threshold effectiveness
    - False suppression rate (games we blocked that would have won)
    - False approval rate (games we approved that lost badly)
    ↓
[STEP 3] Update global configuration:
    Example findings:
    - "NCAAF championships: avg error 9.2pts with current regime"
    - "→ Increase pace compression to 15% (from 12%)"
    - "→ Lower divergence limit to 6pts (from 8pts)"
    
    - "NFL 60-65% bucket winning 68% (overperforming)"
    - "→ Widen variance slightly for more conservative confidence"
    ↓
[STEP 4] Generate internal report:
    Subject: Weekly Trust Loop Analysis - Dec 1-7, 2025
    
    Key Findings:
    1. NCAAF Championships (8 games):
       - Avg error: 9.2pts (vs 12.4pts pre-regime)
       - Win rate: 62.5% (5-3 record)
       - Regime adjustments working ✓
    
    2. Confidence Calibration:
       - 60-65% bucket: 28-19 (59.6% actual) ✓ calibrated
       - 70-75% bucket: 12-5 (70.6% actual) ✓ calibrated
    
    3. Safety Engine Performance:
       - 14 games suppressed (exploration_only)
       - 11/14 would have lost if published (78% accuracy)
       - 3/14 would have won (21% false suppression rate)
    
    Adjustments for next week:
    - NCAAF pace compression: 12% → 15%
    - NFL divergence limit: 8pts → 7pts
    ↓
[STEP 5] Deploy configuration updates (code push or config reload)
```

---

### **4. MONTHLY CYCLE (Deep Backtesting)**

```python
Monthly (first Sunday of month):
    ↓
[STEP 1] Full season backtest for each sport
    - Run simulations on historical games
    - Compare to what regime logic WOULD have done
    ↓
[STEP 2] A/B test regime variations:
    - Test pace compression: 10% vs 12% vs 15%
    - Test divergence limits: 6pts vs 8pts vs 10pts
    - Identify optimal thresholds
    ↓
[STEP 3] Publish findings to team
    - "Championship regime reduced avg error by 28%"
    - "Safety engine prevented 12 catastrophic misses"
    - "Confidence calibration within ±2% across all buckets"
    ↓
[STEP 4] Update documentation & models
```

---

## How Sharp Methods Are Integrated

### **Sharp Method #1: Exploiting Market Inefficiencies**
- **Before Safety Engine:** Show all divergences publicly, even absurd ones
- **After Safety Engine:** Only show divergences that pass risk checks
  - Lane A (exploration): User can see any edge, with warnings
  - Lane B (official): Only publish edges that pass all safety checks

### **Sharp Method #2: Closing Line Value (CLV) Tracking**
- **Already implemented:** `backend/services/clv_tracking.py`
- **How it works:**
  1. Store prediction + opening line
  2. Track closing line movement
  3. Calculate CLV = (closing_line - opening_line) in our direction
  4. Positive CLV = sharps agreed with us = validation

### **Sharp Method #3: Reverse-Engineering Market Makers**
- **Trust loop learns from losses:**
  - When model diverges 15pts and loses → market was right
  - Analyze: Why was market right? Pace? Scoring? Weather?
  - Update regime logic to match market's hidden knowledge

### **Sharp Method #4: Confidence Calibration = Sharp Bankroll Management**
- Sharps only bet when edge * confidence justifies risk
- Trust loop ensures:
  - 60% confidence = actually wins 60% of time
  - 75% confidence = actually wins 75% of time
- This allows proper Kelly Criterion staking

---

## Example: NCAAF Championship Workflow

**Scenario:** User requests simulation for Texas Tech vs BYU (Championship)

### **Real-Time Cycle:**
```python
1. Context detection:
   → is_championship=True (auto-detected from event name)
   → is_postseason=True
   → is_rematch=False

2. Regime adjustments applied:
   → pace_compression: 12.5 poss/game → 11.0 poss/game (12% reduction)
   → redzone_td_suppression: 62% → 46.5% (25% reduction)
   → adjustments_applied: ["pace_compression", "rz_suppression"]

3. Simulation runs (10K iterations for free tier):
   → median_total: 52.3
   → variance: 78.2
   → p60: 54.1 (public-facing ceiling)

4. Safety evaluation:
   → market_total: 49.5
   → divergence_score: 2.8 pts (52.3 - 49.5)
   → divergence_limit: 8 pts (NCAAF championship)
   → environment_risk: 0.4 (championship penalty)
   → variance_risk: 0.28 (moderate variance)
   → risk_score: 0.35 (LOW)
   → output_mode: "eligible_for_pick" ✓

5. Public display:
   ✅ Lane B (Official BeatVegas Edge):
   "Total 49.5 — model shows offensive upside with +2.8 point edge 
    and 58% probability to the Over."
   
   🏆 Championship Volatility badge displayed
   ⚠️ "High-stakes environment. Game management may compress scoring."

6. Storage:
   → Stored in mongo with full context for future grading
```

### **2-Hour Grading Cycle (After Game Completes):**
```python
1. Game finishes: Texas Tech 28, BYU 24 (Total: 52)
2. Fetch prediction: model said 52.3, market said 49.5
3. Grade:
   → actual_total: 52
   → model_error: 0.3 pts (excellent!)
   → predicted: Over 49.5 (58% confidence)
   → actual: Over (52 > 49.5) ✓ CORRECT
   → edge_accuracy: model was +2.8 from market, actual was +2.5 (95% accurate)

4. Update trust metrics:
   → championship_ncaaf: 1 win added
   → confidence_bucket_55-60: 1 win added
   → regime_adjustments "pace_compression": validated ✓

5. Learning:
   → Championship pace compression working as intended
   → Model error <1pt with regime logic (vs ~12pts without)
   → Keep current settings
```

---

## Key Differences from Old System

| Old System | New System with Safety Engine |
|-----------|------------------------------|
| Show all simulations publicly | Two-lane: exploration vs official picks |
| No regime logic for championships | NCAAF championship regime fully implemented |
| Raw model totals displayed | Only show edge vs market + probability |
| No divergence limits | Sport/environment-specific limits enforced |
| Manual sanity checks | Automated safety evaluation + human confirmation |
| No weather validation | Weather failsafe blocks bad data |
| Trust loop = basic win/loss tracking | Trust loop = calibration + regime optimization + CLV |

---

## Trust Loop Storage Schema

### **predictions Collection:**
```json
{
  "_id": "...",
  "event_id": "abc123",
  "simulation_id": "xyz789",
  "sport": "americanfootball_ncaaf",
  "market_type": "total",
  "predicted_value": 52.3,
  "market_line": 49.5,
  "predicted_direction": "over",
  "confidence": 0.58,
  "edge_points": 2.8,
  "output_mode": "eligible_for_pick",
  "regime_flags": {
    "is_championship": true,
    "adjustments_applied": ["pace_compression", "rz_suppression"]
  },
  "created_at": "2025-12-07T10:30:00Z",
  
  // Added after grading:
  "graded": true,
  "actual_total": 52,
  "actual_direction": "over",
  "correct": true,
  "model_error": 0.3,
  "edge_accuracy": 0.95,
  "graded_at": "2025-12-07T14:30:00Z"
}
```

### **trust_metrics Collection (Aggregated):**
```json
{
  "_id": "...",
  "sport": "americanfootball_ncaaf",
  "environment": "championship",
  "confidence_bucket": "55-60%",
  "total_predictions": 47,
  "correct_predictions": 28,
  "win_rate": 0.596,  // Should match confidence!
  "avg_model_error": 6.2,
  "avg_edge_accuracy": 0.88,
  "last_updated": "2025-12-07T14:30:00Z"
}
```

---

## Implementation Checklist

✅ **Core Safety Engine** (`safety_engine.py`)
- Two-lane output system
- Risk scoring
- Divergence limits
- Weather validation
- Public copy formatter

✅ **NCAAF Championship Regime** (`ncaaf_championship_regime.py`)
- Context detection
- Pace compression
- Scoring adjustments
- Possession-based simulation

🔄 **Integration Points** (Next Steps):
1. Integrate safety engine into `simulation_routes.py`
2. Call NCAAF regime before running simulations
3. Store output_mode in mongo
4. Update result_grading.py to include regime context
5. Build weekly analysis script
6. Create internal dashboard for trust metrics

---

## The Sharp Truth

**"The best bettors are paranoid. They don't trust their first instinct, they validate everything, and they learn from every loss."**

This safety engine + trust loop architecture embodies that philosophy:
- **Paranoid:** Multiple layers of validation before any pick goes public
- **Validate:** Every prediction is graded and calibration is monitored
- **Learn:** Regime logic continuously improves based on real outcomes

**The result:** BeatVegas becomes more accurate over time while protecting the brand from catastrophic misses.

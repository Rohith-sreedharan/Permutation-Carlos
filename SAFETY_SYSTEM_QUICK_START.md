# BeatVegas Safety System - Quick Start Guide

## 🚀 System Overview

Three-phase safety architecture protecting BeatVegas from bad picks:

1. **Phase 1**: Safety engine evaluates every simulation (ACTIVE in simulation_routes.py)
2. **Phase 2**: Result grading stores regime context (ACTIVE in result_grading.py)
3. **Phase 3**: Weekly trust metrics analysis (CLI tool ready)

---

## 🎯 Quick Commands

### Run Weekly Trust Loop Report
```bash
# Last 7 days (recommended)
python backend/scripts/run_weekly_report.py

# Last 14 days
python backend/scripts/run_weekly_report.py 14

# Last 30 days
python backend/scripts/run_weekly_report.py 30
```

### Manual Result Grading
```bash
# Via API endpoint
curl -X POST "http://localhost:8000/api/trust/grade-games?hours_back=24"
```

### Check Safety Engine Status
```bash
# View recent simulations with safety context
python -c "from backend.db.mongo import db; print(list(db.monte_carlo_simulations.find({'metadata.output_mode': {'$exists': True}}).limit(5)))"
```

---

## 📊 Reading Weekly Reports

### Executive Summary
```
Trust Loop Weekly Report
Period: 2024-12-01 to 2024-12-08

Overall Performance:
- Total Predictions: 120
- Win Rate: 65.0%              ← Should match confidence level
- Avg Model Error: 4.2 points  ← Lower is better
- Avg Edge Accuracy: 65.0%

Calibration Status: ✅ CALIBRATED  ← GOAL: Always calibrated
```

### Key Metrics to Watch

#### 1. Confidence Calibration (CRITICAL)
```
60-65% bucket: expected 60%, actual 55%
Diagnosis: OVERCONFIDENT
Recommendation: Increase variance or lower confidence thresholds
```

**Action**: If calibration is off by >5%, model needs adjustment

#### 2. Environment Performance
```
REGULAR_SEASON:
  Predictions: 80
  Win Rate: 67%
  Avg Model Error: 3.8 points

CHAMPIONSHIP:
  Predictions: 40
  Win Rate: 60%           ← Lower is expected (more volatile)
  Avg Model Error: 5.2 points  ← Higher is expected
```

**Normal**: Championship games are harder to predict

#### 3. Regime Effectiveness
```
Regime: pace_compression,rz_suppression
  Adjustments: ["pace_compression", "rz_suppression"]
  Predictions: 15
  Win Rate: 73%
  Assessment: EFFECTIVE
  Note: Regime reduced error by 3.1 points
```

**Action**: If regime is INEFFECTIVE, consider removing those adjustments

---

## 🛡️ Safety Engine Behavior

### Two-Lane Output System

#### Lane 1: `eligible_for_pick`
✅ Passed all safety checks:
- Divergence < 8-10 points (depending on sport/environment)
- Weather data available
- Variance within acceptable range
- Risk score < 0.6

**Action**: These picks can go public to users

#### Lane 2: `exploration_only`
⚠️ Failed one or more safety checks:
- High divergence (model disagrees too much with market)
- Missing weather data
- Championship game volatility
- High variance/low confidence

**Action**: Model learns but NO public picks

---

## 🏈 NCAAF Championship Regime

### When It Activates
- Conference championship games
- College Football Playoff games
- Rivalry rematches in playoffs

### What It Does
```
Original Simulation:
  Possessions: 12 per team
  Red Zone TDs: 70% conversion
  Total: 52 points

After Regime Adjustments:
  Possessions: 10.6 per team  (-12% pace compression)
  Red Zone TDs: 52.5% conversion  (-25% suppression)
  Total: 48 points  (more conservative)
```

### Why It Matters
Championship games are:
- More defensive
- Lower scoring
- More conservative play-calling
- Higher stakes = tighter games

---

## 🔍 Debugging Common Issues

### Issue: "No graded predictions found"
**Cause**: No games have completed in the time range
**Solution**: 
- Wait for games to finish
- Check `monte_carlo_simulations` collection for recent predictions
- Verify result grading service is running every 2 hours

### Issue: "All predictions show exploration_only"
**Cause**: Safety engine is suppressing everything
**Solution**:
1. Check divergence scores: `simulation.metadata.divergence_score`
2. Check risk scores: `simulation.metadata.risk_score`
3. If consistently high (>0.6), model might be too aggressive
4. Consider adjusting divergence limits in `safety_engine.py`

### Issue: "Calibration shows OVERCONFIDENT"
**Cause**: Model confidence is higher than actual win rate
**Solution**:
1. Increase simulation variance
2. Lower confidence thresholds
3. Review Monte Carlo iteration count (higher = more accurate)
4. Check if specific environments (championship) are skewing results

### Issue: "Regime shows INEFFECTIVE"
**Cause**: Championship adjustments are making predictions worse
**Solution**:
1. Check sample size (need >10 predictions to judge)
2. Review specific adjustment magnitudes (pace compression, RZ suppression)
3. Consider disabling or reducing adjustment percentages
4. May need sport-specific tuning (CFP vs conference championship)

---

## 📈 Recommended Monitoring Schedule

### Daily
- Check if new simulations are running
- Verify safety_badges and safety_warnings are being generated
- Monitor `output_mode` distribution (should be ~70% eligible_for_pick)

### Weekly
- Run `run_weekly_report.py`
- Review calibration status
- Check regime effectiveness
- Adjust configuration if needed

### Monthly
- Full backtesting analysis
- Review divergence limits
- Update regime adjustment magnitudes
- Comprehensive model tuning

---

## 🎓 Understanding Risk Scores

### Risk Score Components
```python
divergence_risk = abs(model_total - market_total) / divergence_limit
environment_risk = 0.3 if is_championship else 0.0
variance_risk = variance / 100.0  # Normalized

risk_score = min(1.0, divergence_risk + environment_risk + variance_risk)
```

### Risk Thresholds
- **0.0 - 0.3**: ✅ Low risk (safe to publish)
- **0.3 - 0.6**: ⚠️ Medium risk (publish with warnings)
- **0.6 - 1.0**: 🚫 High risk (exploration only)

### Example Calculations

#### Safe Pick (Risk = 0.25)
```
Model Total: 210
Market Total: 214
Divergence: 4 points (< 8pt limit)
Divergence Risk: 4/8 = 0.50
Environment: Regular season = 0.0
Variance: 8.0 / 100 = 0.08
Total Risk: min(1.0, 0.20 + 0.0 + 0.08) = 0.28
Result: eligible_for_pick ✅
```

#### Risky Pick (Risk = 0.75)
```
Model Total: 48
Market Total: 58
Divergence: 10 points (> 8pt limit for championship)
Divergence Risk: 10/8 = 1.25
Environment: Championship = 0.3
Variance: 15.0 / 100 = 0.15
Total Risk: min(1.0, 1.25 + 0.3 + 0.15) = 1.0
Result: exploration_only 🚫
```

---

## 🔧 Configuration Tuning

### When to Adjust Divergence Limits

**Current Values**:
- NFL: 8 points
- NCAAF Regular: 10 points
- NCAAF Championship: 8 points

**Increase Limits If**:
- Too many `exploration_only` picks (>50%)
- Model is consistently accurate despite high divergence
- Missing +EV opportunities

**Decrease Limits If**:
- Too many losses on high-divergence picks
- Model is overconfident
- Market is proving more accurate

### When to Adjust Regime Percentages

**Current Values**:
- Pace Compression: 12%
- RZ TD Suppression: 25%

**Increase Percentages If**:
- Championship games are still over-predicted
- Model error is consistently high for playoffs
- Weekly report shows regime is INEFFECTIVE

**Decrease Percentages If**:
- Championship games are under-predicted
- Model error is lower than regular season
- Too conservative, missing overs

---

## 📝 Database Schema Reference

### Simulation Document
```json
{
  "_id": ObjectId("..."),
  "event_id": "abc123",
  "sport": "americanfootball_ncaaf",
  "confidence": 0.65,
  "avg_total": 48.5,
  "variance": 8.2,
  "created_at": "2024-12-08T10:00:00Z",
  
  "metadata": {
    "output_mode": "eligible_for_pick" | "exploration_only",
    "risk_score": 0.35,
    "divergence_score": 0.42,
    "environment_type": "championship" | "regular_season",
    "regime_adjustments": ["pace_compression", "rz_suppression"]
  },
  
  "safety_warnings": [
    "High divergence from market",
    "Championship game volatility"
  ],
  
  "safety_badges": [
    "🏆 Championship Volatility"
  ],
  
  // After game completes:
  "graded": true,
  "correct": true,
  "status": "WIN" | "LOSS" | "PUSH",
  "actual_home_score": 24,
  "actual_away_score": 21,
  "model_error": 3.2,
  "units_won": 1.0,
  "edge_accuracy": 1.0,
  "graded_at": "2024-12-08T22:00:00Z",
  
  "regime_flags": {
    "environment_type": "championship",
    "output_mode": "eligible_for_pick",
    "risk_score": 0.35,
    "divergence_score": 0.42,
    "adjustments_applied": ["pace_compression", "rz_suppression"]
  }
}
```

---

## 🎯 Success Criteria

### System is Working If:
1. ✅ Confidence calibration is within 5% (60% bucket wins ~60%)
2. ✅ ~70% of simulations are `eligible_for_pick`
3. ✅ Championship game model error is <6 points
4. ✅ Weekly win rate matches average confidence level
5. ✅ Regime adjustments show "EFFECTIVE" assessment

### Red Flags:
1. 🚫 All picks are `exploration_only` (too restrictive)
2. 🚫 Confidence calibration off by >10% (model broken)
3. 🚫 Win rate significantly below confidence (bad picks getting through)
4. 🚫 Regime showing "INEFFECTIVE" for >3 weeks (needs adjustment)
5. 🚫 No graded predictions (result service not running)

---

## 💡 Pro Tips

1. **Trust the Trust Loop**: If weekly report shows calibration issues, take action immediately
2. **Start Conservative**: Better to suppress too much early, then loosen restrictions
3. **Sport-Specific Tuning**: NFL and NCAAF may need different divergence limits
4. **Sample Size Matters**: Need 20+ predictions per bucket for valid calibration assessment
5. **Monitor Environment Split**: Championship games should be ~20-30% of total

---

## 📞 Key Files Reference

| File | Purpose | Key Functions |
|------|---------|---------------|
| `backend/core/safety_engine.py` | Safety evaluation | `evaluate_simulation()` |
| `backend/core/ncaaf_championship_regime.py` | NCAAF adjustments | `detect_ncaaf_context()`, `apply_regime_adjustments()` |
| `backend/services/trust_metrics.py` | Weekly analysis | `generate_weekly_report()`, `analyze_calibration()` |
| `backend/services/result_grading.py` | Grade predictions | `grade_completed_games()`, `_grade_prediction()` |
| `backend/routes/simulation_routes.py` | Simulation API | Lines 217-265 (safety integration) |
| `backend/scripts/run_weekly_report.py` | CLI tool | `main()` - generate report |

---

## 🚨 Emergency Actions

### If System is Blocking All Picks
```python
# Temporarily disable safety checks (NOT RECOMMENDED FOR PRODUCTION)
# In safety_engine.py, force all picks to eligible:
return {
    "output_mode": "eligible_for_pick",
    "risk_score": 0.0,
    # ... rest of response
}
```

### If Calibration is Severely Off
```python
# In trust_metrics.py, run immediate analysis:
report = await trust_metrics_service.aggregate_weekly_metrics()
calibration = await trust_metrics_service.analyze_calibration(report)
print(calibration["recommended_adjustments"])
```

### If Weekly Report Won't Run
```python
# Check database connection:
from backend.db.mongo import db
print(db.monte_carlo_simulations.count_documents({"graded": True}))

# If 0, result grading isn't working - check API key
```

---

## ✅ Implementation Checklist

- [x] Phase 1: Safety engine evaluating simulations
- [x] Phase 2: Result grading storing regime context
- [x] Phase 3: Weekly trust metrics analysis
- [x] CLI tool for weekly reports
- [x] NCAAF championship regime active
- [x] Documentation complete
- [ ] Frontend displaying safety badges/warnings
- [ ] Scheduled weekly report job (cron/APScheduler)
- [ ] Production monitoring dashboard
- [ ] Alert system for calibration drift

---

**System Status**: ✅ **FULLY OPERATIONAL**

Run your first report:
```bash
python backend/scripts/run_weekly_report.py 7
```

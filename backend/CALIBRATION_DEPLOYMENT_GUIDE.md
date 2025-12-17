# 🎯 CALIBRATION SYSTEM DEPLOYMENT GUIDE

## System Status: ✅ FULLY INTEGRATED

The institutional-grade calibration system is now **live and operational**. Every simulation automatically applies 5 constraint layers to prevent structural over-bias.

---

## What Was Implemented

### 1. **Database Schema** ✅ DEPLOYED
- `pick_audit` collection - Logs every pick decision with block reasons
- `calibration_daily` collection - Daily aggregate metrics per sport
- Migration script executed successfully

### 2. **Calibration Engine** ✅ INTEGRATED
Location: `backend/core/calibration_engine.py`

**5 Constraint Layers:**
1. **Data Integrity** - 70% quality threshold
2. **League Baseline Clamp** - Daily calibration with auto-dampening
3. **Market Anchor Sanity** - 0-10% penalty for soft→hard deviation
4. **Variance Suppression** - High variance collapses edge
5. **Publish Gates** - Minimum probability/EV thresholds

Applied automatically in `monte_carlo_engine.py` after RCL validation.

### 3. **Calibration Logger** ✅ ACTIVE
Location: `backend/core/calibration_logger.py`

**What It Logs:**
- Every pick: vegas_line, model_line, raw/adjusted probabilities, publish decision, block reasons
- Daily aggregates: bias_vs_actual, bias_vs_market, over_rate, win_rate, damp_factor
- Weekly reports: Trend detection and adjustment recommendations

Integrated into simulation flow - logs written to MongoDB on every pick.

### 4. **Sport-Specific Configs** ✅ LOCKED
Location: `backend/core/sport_calibration_config.py`

**Threshold Configs for All Sports:**
- NFL: soft_dev=4.5, hard_dev=7.5, min_prob=0.58, max_over_rate=0.62
- NCAAF: soft_dev=5.5, hard_dev=9.0, min_prob=0.56, max_over_rate=0.64
- NBA: soft_dev=6.0, hard_dev=10.0, min_prob=0.58, max_over_rate=0.60
- NCAAB: soft_dev=7.0, hard_dev=11.0, min_prob=0.56, max_over_rate=0.62
- MLB: soft_dev=2.5, hard_dev=4.5, min_prob=0.60, max_over_rate=0.58
- NHL: soft_dev=2.5, hard_dev=4.0, min_prob=0.60, max_over_rate=0.58

### 5. **Daily Calibration Job** ✅ READY
Location: `backend/scripts/daily_calibration_job.py`

Scheduled to run at 2 AM EST daily via cron.

---

## How It Works

### Simulation Flow (Every Pick)

```
1. Monte Carlo Simulation (10k-100k iterations)
   ↓
2. RCL Validation (sanity checks)
   ↓
3. CALIBRATION ENGINE (5 CONSTRAINT LAYERS) ← NEW
   - Data integrity check
   - League baseline clamp (daily calibration)
   - Market anchor sanity (soft/hard deviation)
   - Variance suppression (high variance = edge collapse)
   - Publish gates (minimum thresholds)
   ↓
4. Adjusted probabilities & edge returned
   ↓
5. Calibration audit logged to MongoDB
   ↓
6. Result stored & returned to API
```

### Example Calibration Output

**BEFORE Calibration:**
- Model Total: 52.5
- Vegas Total: 45.0
- Deviation: +7.5 pts
- Raw Probability: 68%
- Raw Edge: 7.5 pts
- Status: ✅ PUBLISH

**AFTER Calibration:**
- Deviation Check: +7.5 > 7.5 (hard threshold)
- Market Penalty: 10% applied
- Variance Check: z=1.35 (high variance)
- Variance Penalty: 75% applied
- **Adjusted Probability: 51%** (down from 68%)
- **Adjusted Edge: 1.9 pts** (down from 7.5)
- **Status: 🚫 BLOCKED** (below min_probability=0.58)
- **Block Reasons:** `MARKET_DIVERGENCE_EXTREME`, `HIGH_VARIANCE`, `INSUFFICIENT_PROBABILITY`

---

## Daily Calibration Process

### What Happens at 2 AM EST

1. **Fetch Completed Games** (yesterday's date)
   - Queries ESPN scores for all 6 sports
   - Matches with stored predictions in `monte_carlo_simulations`

2. **Compute Daily Metrics**
   - **Bias vs Actual**: Avg(model_total - actual_total)
   - **Bias vs Market**: Avg(model_total - vegas_total)
   - **Over Rate**: % of picks that were overs
   - **Win Rate**: % of picks that won
   - **Dampening Factor**: Applied if bias thresholds exceeded

3. **Auto-Dampening Logic**
   - If `bias_vs_actual > 2.5` OR `bias_vs_market > 2.0` OR `over_rate > max_over_rate`:
     - `damp_factor = 0.90` (10% reduction to all projections)
   - Triggers global clamp on next day's picks

4. **Store Results** → `calibration_daily` collection
   - Metrics stored per sport per day
   - Historical trend tracking enabled

---

## Deployment Steps

### ✅ Already Completed
1. Database migration run successfully
2. Calibration engine integrated into monte_carlo_engine.py
3. Calibration logging active on all picks
4. Sport configs locked for all 6 sports

### 🔧 Next Steps (Manual)

#### 1. Setup Daily Cron Job

```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
bash scripts/setup_calibration_cron.sh
```

This will:
- Install cron job to run at 2 AM EST daily
- Create log file at `backend/logs/calibration.log`
- Verify installation

#### 2. Test Manual Run (Optional)

```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
source .venv/bin/activate
PYTHONPATH=/Users/rohithaditya/Downloads/Permutation-Carlos/backend python3 scripts/daily_calibration_job.py
```

This will compute calibration for yesterday's games immediately.

#### 3. Monitor First Week

**Check Logs:**
```bash
tail -f /Users/rohithaditya/Downloads/Permutation-Carlos/backend/logs/calibration.log
```

**Query MongoDB:**
```javascript
// Check daily calibration results
db.calibration_daily.find({sport: "americanfootball_nfl"}).sort({date: -1}).limit(7)

// Check pick audit trail
db.pick_audit.find({sport: "americanfootball_nfl", publish_decision: false}).limit(10)
```

**Key Metrics to Watch:**
- `bias_vs_actual` - Should trend toward 0
- `over_rate` - Should stay below `max_over_rate` (0.62 for NFL)
- `damp_factor` - If < 1.0, system is actively correcting bias
- `block_reasons` - What's causing picks to be blocked

---

## System Self-Correction

### How It Fixes Itself

1. **Daily Feedback Loop**
   - Actual results compared to predictions
   - Bias metrics computed automatically
   - Dampening applied if needed (no human intervention)

2. **Constraint Enforcement**
   - Every pick validated through 5 layers
   - Market divergence penalized in real-time
   - High variance suppresses edge automatically

3. **Historical Learning**
   - Weekly reports show trends
   - Persistent bias triggers stronger dampening
   - Elite override rarely activates (exceptional edges only)

### Example Self-Correction Scenario

**Week 1:**
- NFL over_rate: 68% (exceeds 62% threshold)
- bias_vs_market: +3.2 pts
- Result: `damp_factor = 0.90` applied

**Week 2 (with dampening):**
- All NFL projections reduced by 10%
- 52.5 → 47.25 (closer to market)
- over_rate: 58% ✅
- bias_vs_market: +1.1 pts ✅
- Result: Dampening removed, system normalized

---

## API Response Changes

### New Fields in Simulation Result

```json
{
  "calibration": {
    "publish": true,
    "p_raw": 0.6543,
    "p_adjusted": 0.5912,
    "edge_raw": 6.2,
    "edge_adjusted": 3.1,
    "confidence_label": "MODERATE",
    "z_variance": 1.15,
    "elite_override": false,
    "block_reasons": [],
    "applied_penalties": {
      "market_penalty": 0.05,
      "variance_penalty": 0.50
    }
  }
}
```

### Blocked Pick Example

```json
{
  "calibration": {
    "publish": false,
    "p_raw": 0.6543,
    "p_adjusted": 0.5312,
    "edge_raw": 6.2,
    "edge_adjusted": 2.8,
    "confidence_label": "LOW",
    "z_variance": 1.42,
    "elite_override": false,
    "block_reasons": [
      "HIGH_VARIANCE",
      "INSUFFICIENT_PROBABILITY",
      "BELOW_MIN_EV"
    ],
    "applied_penalties": {
      "market_penalty": 0.08,
      "variance_penalty": 0.75
    }
  }
}
```

---

## Configuration Reference

### NFL Thresholds (Most Strict)

```python
soft_deviation = 4.5      # Market penalty starts
hard_deviation = 7.5      # Block unless elite
min_probability = 0.58    # 58% minimum to publish
min_ev_vs_vig = 2.0       # 2% edge after vig
max_over_rate = 0.62      # Max 62% overs daily
high_variance_z = 1.25    # Z-score threshold
extreme_variance_z = 1.40 # Extreme variance
elite_override_prob = 0.62 # 62% for elite exception
```

### MLB/NHL Thresholds (Low-Scoring)

```python
soft_deviation = 2.5      # Tighter for low totals
hard_deviation = 4.0
min_probability = 0.60    # Higher bar (less variance)
max_over_rate = 0.58      # Stricter (58%)
```

---

## Troubleshooting

### Q: Picks are being blocked too aggressively
**A:** Check `calibration_daily` for current damp_factor. If < 1.0, system is actively correcting bias. This is intentional. Monitor for 3-5 days - it will normalize.

### Q: Over rate still too high
**A:** 
1. Check if daily calibration job is running (logs at `backend/logs/calibration.log`)
2. Verify cron job: `crontab -l | grep calibration`
3. Manual run: `python3 scripts/daily_calibration_job.py`
4. Lower `max_over_rate` in `sport_calibration_config.py` if needed

### Q: Elite override activating too often
**A:** Raise thresholds in `calibration_engine.py`:
```python
# Line ~170
p_raw >= 0.65 (instead of 0.62)  # Higher probability bar
data_quality >= 98 (instead of 95)  # Stricter quality
```

### Q: Want to disable calibration temporarily
**A:** In `monte_carlo_engine.py`, comment out calibration validation:
```python
# calibration_result = self.calibration_engine.validate_pick(...)
# Use dummy result:
calibration_result = {'publish': True, 'p_adjusted': p_raw, 'edge_adjusted': edge_raw, ...}
```

---

## Summary

### ✅ What's Live
- 5-layer constraint system integrated into every simulation
- Sport-specific thresholds for all 6 sports
- Automated calibration logging on every pick
- Daily calibration job ready for cron scheduling
- Database schema deployed

### 🎯 Self-Correction Architecture
- **Market divergence** → Automatic penalty (0-10%)
- **High variance** → Edge collapse (50-75% reduction)
- **Daily bias** → Auto-dampening (10% global reduction)
- **Extreme outliers** → Blocked unless elite override
- **Publish gates** → Minimum thresholds enforced

### 📊 Monitoring
- Pick audit: `db.pick_audit.find()`
- Daily calibration: `db.calibration_daily.find()`
- Logs: `backend/logs/calibration.log`
- Weekly reports: `calibration_logger.generate_weekly_report()`

**The system now fixes itself.** No more repeated tactical patches. The architecture is institutional-grade with locked configs, automated logging, and daily bias detection built in.

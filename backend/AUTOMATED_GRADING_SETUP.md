# Automated Post-Game Grading System

## Overview
Every finished game automatically flows through the grading pipeline. No manual tagging required. The system grades model performance, classifies variance vs model faults, and feeds weighted samples into weekly calibration.

---

## Architecture

### 1. Post-Game Grading Pipeline
**File**: `backend/services/post_game_grader.py`

**Core Logic**:
```python
For every finished game:
1. Pull pregame audit record from sim_audit (contains model_total, rcl_passed)
2. Pull final result from events collection (final_score_home + final_score_away)
3. Compute deltas:
   - delta_model = |model_total - final_total|
   - delta_vegas = |vegas_total_close - final_total|
4. Classify outcome:
   - normal variance (≤7 pts)
   - upper_tail_scoring_burst (8-15 pts, model underestimated)
   - lower_tail_brickfest (8-15 pts, model overestimated)
   - model_drift (>15 pts but vegas also missed by >10)
   - model_fault_heavy (>15 pts, vegas within 8)
   - rcl_blocked_pre (RCL blocked pregame projection)
5. Assign calibration_weight (0.25 to 1.5):
   - 1.0 = normal variance
   - 1.25 = medium miss (8-15 pts)
   - 1.5 = big miss (>15 pts) or RCL blocked
6. Write grading record to game_grade_log collection
7. Weekly calibration queries game_grade_log for weighted samples
```

---

## Automation Setup

### Cron Job (Recommended)
**Script**: `backend/scripts/grade_finished_games.py`

**Add to crontab**:
```bash
# Grade finished games every 30 minutes
*/30 * * * * cd /path/to/backend && python scripts/grade_finished_games.py >> /var/log/grading.log 2>&1
```

**Manual trigger**:
```bash
cd backend
python scripts/grade_finished_games.py
```

---

## API Endpoints

### GET `/api/simulations/grading/stats`
**Query Parameters**:
- `days_back` (default: 7) - How many days of grading history to analyze
- `sport_key` (optional) - Filter by sport (e.g., "basketball_nba")

**Response**:
```json
{
  "success": true,
  "data": {
    "total_games": 145,
    "model_fault_count": 23,
    "model_fault_rate": 0.159,
    "avg_delta_model": 6.8,
    "avg_delta_vegas": 5.2,
    "variance_breakdown": {
      "normal": 98,
      "upper_tail_scoring_burst": 15,
      "lower_tail_brickfest": 12,
      "model_drift": 8,
      "model_fault_heavy": 7,
      "rcl_blocked_pre": 5
    },
    "calibration_weight_avg": 1.08
  },
  "days_back": 7
}
```

### POST `/api/simulations/grading/run`
**Query Parameters**:
- `hours_back` (default: 48) - Look back window for finished games

**Response**:
```json
{
  "success": true,
  "summary": {
    "graded": 12,
    "skipped": 8,
    "errors": 0
  },
  "message": "Graded 12 games, skipped 8, errors: 0"
}
```

---

## Grading Classification Logic

### Variance Types

| Type | Delta Model | Vegas Delta | Model Fault | Weight |
|------|-------------|-------------|-------------|--------|
| **normal** | ≤7 pts | - | False | 1.0 |
| **upper_tail_scoring_burst** | 8-15 pts (model too low) | - | False | 1.25 |
| **lower_tail_brickfest** | 8-15 pts (model too high) | - | False | 1.25 |
| **model_drift** | >15 pts | >10 pts (Vegas also wrong) | False | 0.25 |
| **model_fault_heavy** | >15 pts | ≤8 pts (Vegas correct) | True | 1.5 |
| **rcl_blocked_pre** | - | RCL failed pregame | True | 1.5 |

### Classification Rules
1. **RCL blocked pregame** → model_fault=True, weight=1.5
2. **Delta ≤7 pts** → normal variance
3. **Delta 8-15 pts** → medium miss (upper/lower tail)
4. **Delta >15 pts**:
   - If Vegas also missed by >10 → model_drift (low weight)
   - If Vegas within 8 → model_fault_heavy (high weight)

---

## Database Collections

### `game_grade_log`
**Purpose**: Store grading records for every finished game

**Schema**:
```python
{
    "game_id": str,                     # Unique game identifier
    "sport_key": str,                   # e.g., "basketball_nba"
    "graded_at": datetime,              # Timestamp of grading
    "vegas_total_close": float,         # Closing total line
    "model_total": float,               # Pre-game model projection
    "final_total": int,                 # Actual final score sum
    "delta_model": float,               # |model_total - final_total|
    "delta_vegas": float,               # |vegas_total - final_total|
    "variance_type": str,               # Classification (see table above)
    "model_fault": bool,                # True if genuine model error
    "confidence_retro": str,            # "LOW" / "MEDIUM" / "HIGH"
    "calibration_weight": float,        # 0.25 to 1.5
    "rcl_passed": bool,                 # Did RCL pass pregame?
    "rcl_reason": Optional[str]         # RCL failure reason (if any)
}
```

**Indexes**:
- `game_id` (unique)
- `graded_at` (for time-based queries)
- `model_fault` (for fault rate analysis)
- `variance_type` (for classification breakdown)
- `sport_key` (for sport-specific stats)

### `calibration_log`
**Purpose**: Track weekly calibration adjustments

**Schema**:
```python
{
    "calibration_id": str,
    "run_at": datetime,
    "games_used": int,
    "avg_delta_before": float,
    "avg_delta_after": float,
    "adjustments_made": Dict[str, Any]  # Parameter changes
}
```

---

## Weekly Calibration Process

### Step 1: Query Calibration Samples
```python
# Get last 7 days of games with model_fault=True or delta_model≤10
samples = post_game_grader.get_calibration_samples(days_back=7)
```

### Step 2: Weighted Analysis
- Weight=1.5 samples (big misses, RCL blocks) have 1.5x influence
- Weight=1.25 samples (medium misses) have 1.25x influence
- Weight=0.25 samples (model_drift where Vegas also wrong) have 0.25x influence

### Step 3: Apply Calibration
```python
# Adjust model parameters based on weighted feedback
post_game_grader.apply_weekly_calibration()
```

**Adjustments**:
- If model consistently overshoots → reduce pace multipliers
- If model undershoots → increase efficiency curves
- If RCL blocks frequent → tighten historical sigma
- Sport-specific tuning based on variance_type patterns

---

## Monitoring & Alerts

### Health Checks
1. **Model Fault Rate** > 20% over 7 days → Alert: Model needs recalibration
2. **RCL Block Rate** > 10% → Alert: Guardrails too aggressive
3. **Avg Delta Model** increasing week-over-week → Alert: Model drift detected

### Dashboard Metrics
- Total games graded (last 24h/7d/30d)
- Model fault rate trend
- Variance type distribution
- Calibration weight distribution
- Sport-specific performance

---

## Testing

### Test Coverage
**File**: `backend/test_post_game_grader.py` (create if needed)

```python
def test_normal_variance():
    # Model: 145, Actual: 148 → normal variance
    assert classify(145, 148, vegas=145.5) == "normal"

def test_big_miss_model_fault():
    # Model: 153, Actual: 103 → model_fault_heavy
    assert classify(153, 103, vegas=105) == "model_fault_heavy"

def test_rcl_blocked():
    # RCL blocked pregame → always model_fault
    assert classify(153, 103, rcl_passed=False) == "rcl_blocked_pre"

def test_calibration_weights():
    # Big miss → weight 1.5
    assert get_weight("model_fault_heavy") == 1.5
    # Normal → weight 1.0
    assert get_weight("normal") == 1.0
```

---

## Deployment Checklist

- [x] Create `post_game_grader.py` service
- [x] Create `game_grade_log.py` schema
- [x] Create `grade_finished_games.py` cron script
- [x] Add grading API endpoints to `simulation_routes.py`
- [ ] Set up cron job on production server
- [ ] Add monitoring dashboard for grading stats
- [ ] Implement weekly calibration parameter adjustments
- [ ] Configure alerting for high model fault rates
- [ ] Create admin UI for grading history review

---

## Example Scenarios

### Scenario 1: Normal Game
- **Model Total**: 145
- **Vegas Total**: 145.5
- **Final Total**: 148
- **Result**: 
  - delta_model = 3 pts
  - variance_type = "normal"
  - model_fault = False
  - calibration_weight = 1.0

### Scenario 2: Scoring Burst (Model Too Low)
- **Model Total**: 140
- **Vegas Total**: 142
- **Final Total**: 153
- **Result**:
  - delta_model = 13 pts
  - variance_type = "upper_tail_scoring_burst"
  - model_fault = False
  - calibration_weight = 1.25

### Scenario 3: Model Fault (RCL Should Have Blocked)
- **Model Total**: 153
- **Vegas Total**: 145.5
- **Final Total**: 103
- **RCL Passed**: False (blocked pregame)
- **Result**:
  - variance_type = "rcl_blocked_pre"
  - model_fault = True
  - calibration_weight = 1.5

### Scenario 4: Both Models Wrong (Unusual Game)
- **Model Total**: 145
- **Vegas Total**: 147
- **Final Total**: 122
- **Result**:
  - delta_model = 23 pts
  - delta_vegas = 25 pts
  - variance_type = "model_drift"
  - model_fault = False (Vegas also wrong)
  - calibration_weight = 0.25

---

## Future Enhancements

1. **Real-time grading**: Grade games immediately when marked complete
2. **Sport-specific thresholds**: Different BIG_MISS values for NBA vs NFL
3. **Confidence decay**: Lower confidence_retro for older games in calibration
4. **A/B testing**: Compare calibrated vs non-calibrated model performance
5. **Explainability**: Add `grading_notes` field explaining why variance_type was assigned
6. **Historical comparison**: Track grading stats month-over-month

---

## Questions & Troubleshooting

**Q: What if a game has no sim_audit record?**
A: Skip grading. Log warning. Game likely not simulated pregame.

**Q: What if final_score is 0?**
A: Skip grading. Game likely postponed or data missing.

**Q: How often should calibration run?**
A: Weekly is recommended. Daily may overfit to short-term noise.

**Q: Can I manually override a grading classification?**
A: Not currently. Add `manual_override` field if needed.

**Q: What if RCL blocks after game finishes?**
A: Not relevant. RCL only runs pregame. Grading compares pregame audit vs final result.

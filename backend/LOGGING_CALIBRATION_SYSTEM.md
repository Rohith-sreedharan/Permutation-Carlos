# Logging & Calibration System Documentation

## Overview

This system implements a comprehensive logging, grading, and calibration framework for prediction tracking as specified in the dev brief.

## Core Principles

1. **Append-only truth**: Never overwrite historical inputs/outputs
2. **Exact lineage**: Every published prediction references exact snapshots + versions
3. **One source of truth**: Only published records count for grading
4. **Grade everything**: All published records settle into win/loss/push/void with CLV
5. **Calibration is versioned and gated**: No silent changes

## Architecture

### Database Collections

```
events                  → Canonical game records
odds_snapshots          → Immutable market snapshots (raw + normalized)
injury_snapshots        → Injury report captures
sim_runs                → Immutable simulation execution records
sim_run_inputs          → Lineage tracking (joins snapshots to sim_runs)
predictions             → What the engine believed at that run
published_predictions   → Official predictions (THE ONLY ONES THAT COUNT)
event_results           → Final game outcomes
grading                 → Settlement + scoring metrics
calibration_versions    → Versioned calibration models
calibration_segments    → Calibration by cohort
performance_rollups     → Materialized performance metrics
```

### Services

```
snapshot_capture.py     → Captures odds and injury snapshots
sim_run_tracker.py      → Tracks simulation runs with lineage
publishing_service.py   → Publishes predictions (official tracking)
grading_service.py      → Grades published predictions with CLV
calibration_service.py  → Versioned calibration system
calibration_scheduler.py → Automated weekly calibration jobs
```

### API Routes

```
/api/calibration/*      → Calibration and grading endpoints
```

## Usage Guide

### 1. Initialize Database

```bash
python backend/scripts/init_logging_calibration_db.py
```

This creates all indexes and verifies collections.

### 2. Capture Odds Snapshots

When fetching odds from OddsAPI or other providers:

```python
from services.snapshot_capture import snapshot_service

# Capture bulk snapshots from bookmaker data
snapshot_ids = snapshot_service.capture_bulk_odds_snapshots(
    event_id="nba_lakers_celtics_2026_01_20",
    bookmaker_data=odds_api_response["bookmakers"],
    provider="OddsAPI"
)

# Or capture individual snapshot
snapshot_id = snapshot_service.capture_odds_snapshot(
    event_id="nba_lakers_celtics_2026_01_20",
    provider="OddsAPI",
    book="draftkings",
    market_key="SPREAD:FULL_GAME",
    selection="HOME",
    line=-5.5,
    price_american=-110,
    raw_payload=raw_data
)
```

### 3. Create Simulation Runs

When running a simulation:

```python
from services.sim_run_tracker import sim_run_tracker
import time

# Start timing
start_time = time.time()

# Create sim run record
sim_run_id = sim_run_tracker.create_sim_run(
    event_id="nba_lakers_celtics_2026_01_20",
    trigger="user_click",  # or "auto_internal", "scheduled"
    sim_count=100000,  # 100K for public, 1M for internal
    model_version="v2.1.0",
    feature_set_version="v1.5",
    decision_policy_version="v1.0",
    calibration_version_applied="v_20260119_030000",  # if using calibration
    seed_policy="rolled"
)

# Record inputs (exact snapshots used)
sim_run_tracker.record_sim_run_inputs(
    sim_run_id=sim_run_id,
    snapshot_id=latest_snapshot_id,  # from odds_snapshots
    injury_snapshot_id_home=home_injury_snapshot_id,
    injury_snapshot_id_away=away_injury_snapshot_id
)

# Run your simulation
results = monte_carlo_engine.simulate(...)

# Create predictions
prediction_id = sim_run_tracker.create_prediction(
    sim_run_id=sim_run_id,
    event_id="nba_lakers_celtics_2026_01_20",
    market_key="SPREAD:FULL_GAME",
    selection="HOME",
    market_snapshot_id_used=latest_snapshot_id,
    model_line=-4.8,
    p_cover=0.62,
    ev_units=2.1,
    edge_points=3.2,
    uncertainty=1.5,
    distribution_summary={"mean": -4.8, "p10": -8.2, "p50": -4.8, "p90": -1.4},
    rcl_gate_pass=True,
    recommendation_state="EDGE",
    tier="A",
    confidence_index=0.62,
    variance_bucket="MEDIUM"
)

# Complete sim run
runtime_ms = int((time.time() - start_time) * 1000)
sim_run_tracker.complete_sim_run(sim_run_id, runtime_ms)
```

### 4. Publish Predictions

Only publish predictions that pass your gates:

```python
from services.publishing_service import publishing_service

# Publish to Telegram
publish_id = publishing_service.publish_prediction(
    prediction_id=prediction_id,
    channel="telegram",
    visibility="premium",
    decision_reason_codes=["EDGE", "HIGH_CONFIDENCE", "POSITIVE_CLV"],
    ticket_terms={
        "line": -5.5,
        "price": -110,
        "book": "draftkings",
        "selection": "Lakers -5.5"
    },
    copy_template_id="template_spread_edge_v1",
    is_official=True  # CRITICAL: only True = graded for track record
)
```

### 5. Grade Predictions

After games complete:

```python
from services.grading_service import grading_service

# Grade a specific published prediction
graded_id = grading_service.grade_published_prediction(
    publish_id=publish_id
)

# Or grade all pending
stats = grading_service.grade_all_pending(lookback_hours=72)
# Returns: {"graded": 15, "voided": 2, "pending": 5}
```

Grading automatically:
- Computes CLV vs closing line
- Calculates Brier score
- Calculates log loss
- Determines WIN/LOSS/PUSH/VOID
- Computes unit return

### 6. Run Calibration

Weekly calibration (automatic via scheduler or manual):

```python
from services.calibration_service import calibration_service

# Run calibration job
calibration_version = calibration_service.run_calibration_job(
    training_days=30,
    method="isotonic"  # or "platt", "temperature", "beta"
)

# Check activation status
version_doc = calibration_service.calibration_versions_collection.find_one({
    "calibration_version": calibration_version
})
print(f"Status: {version_doc['activation_status']}")
print(f"ECE: {version_doc['overall_ece']}")
print(f"Brier: {version_doc['overall_brier']}")
```

Calibration automatically:
- Segments by league and market
- Trains on settled official predictions only
- Applies activation gate (ECE/Brier improvement check)
- Versions all calibration models
- Rejects low-sample segments

### 7. Use Calibration

Apply calibration to raw probabilities:

```python
# Calibrate a prediction
raw_prob = 0.62
calibrated_prob = calibration_service.calibrate_probability(
    raw_probability=raw_prob,
    league="NBA",
    market_key="SPREAD:FULL_GAME"
)

print(f"Raw: {raw_prob:.3f} → Calibrated: {calibrated_prob:.3f}")
```

### 8. Query Performance

Get performance metrics:

```python
# Overall performance
summary = grading_service.get_performance_summary()
# Returns: win_rate, roi, total_units, avg_clv, avg_brier, etc.

# Performance by cohort
summary_nba = grading_service.get_performance_summary(
    cohort_key="NBA",
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 1, 31)
)
```

## API Endpoints

### Calibration

```
POST /api/calibration/run-calibration-job
  Body: {"training_days": 30, "method": "isotonic"}
  
GET /api/calibration/active-calibration-version

GET /api/calibration/calibration-versions?limit=10

POST /api/calibration/activate-calibration/{version}

GET /api/calibration/calibration-segments/{version}
```

### Grading

```
POST /api/calibration/grade-all-pending
  Body: {"lookback_hours": 72}

POST /api/calibration/grade-published/{publish_id}

GET /api/calibration/grading/{publish_id}
```

### Performance

```
POST /api/calibration/performance-summary
  Body: {"cohort_key": "NBA", "start_date": "...", "end_date": "..."}

GET /api/calibration/performance/by-cohort?days_back=30

GET /api/calibration/performance/clv-distribution?days_back=30
```

### Sim Runs

```
GET /api/calibration/sim-runs/event/{event_id}

GET /api/calibration/sim-runs/{sim_run_id}
```

### Snapshots

```
GET /api/calibration/snapshots/odds/{event_id}?market_key=...&book=...

GET /api/calibration/snapshots/closing-line/{event_id}?market_key=...&book=...
```

### Health

```
GET /api/calibration/health
```

## Scheduled Jobs

Configure in `main.py`:

```python
from services.calibration_scheduler import start_calibration_scheduler, stop_calibration_scheduler

# At startup
start_calibration_scheduler()

# At shutdown
stop_calibration_scheduler()
```

Default schedule:
- **Weekly calibration**: Sundays at 3:00 AM UTC
- **Daily grading**: Every day at 4:00 AM UTC

## Data Retention Strategy

Implemented in `snapshot_capture.py`:

```python
# Clean up old snapshots (keep closing lines forever)
deleted = snapshot_service.cleanup_old_snapshots(
    retention_days=180,
    keep_closing_lines=True
)
```

Run this monthly or quarterly to control storage costs.

## Validation & Integrity Checks

### 8-Point Prevention Checklist

1. ✅ **Never grade a prediction that wasn't published as official**
   - `grading_service.py` only grades `is_official=True`

2. ✅ **Never compute track record from user reruns**
   - Only `published_predictions` with `is_official=True` are graded

3. ✅ **Always store raw provider payloads**
   - `odds_snapshots.raw_payload` stores full raw data
   - `injury_snapshots.raw_payload` stores full injury data

4. ✅ **Always attach snapshot_id_used and close_snapshot_id**
   - `predictions.market_snapshot_id_used` → exact snapshot
   - `grading.close_snapshot_id` → closing line snapshot

5. ✅ **Enforce time in UTC everywhere**
   - All timestamps use `datetime.now(timezone.utc)`

6. ✅ **Handle event status changes (postponed/cancelled) → VOID**
   - `grading_service._grade_as_void()` handles cancellations

7. ✅ **Enforce idempotency (same publish can't be inserted twice)**
   - `publishing_service.publish_prediction()` checks for duplicates

8. ✅ **Partition odds_snapshots and index properly**
   - Indexes created in `logging_calibration_schemas.py`
   - Partitioning by month recommended for production

## Integration with Existing Code

### Monte Carlo Simulation Integration

Modify `simulation_engine.py`:

```python
from services.sim_run_tracker import sim_run_tracker
from services.snapshot_capture import snapshot_service

# Before simulation
snapshot_id = snapshot_service.capture_odds_snapshot(...)
sim_run_id = sim_run_tracker.create_sim_run(...)
sim_run_tracker.record_sim_run_inputs(sim_run_id, snapshot_id=snapshot_id)

# After simulation
prediction_id = sim_run_tracker.create_prediction(...)
sim_run_tracker.complete_sim_run(sim_run_id, runtime_ms)
```

### Telegram Bot Integration

Modify `telegram_bot_service.py`:

```python
from services.publishing_service import publishing_service

# When posting a pick to Telegram
publish_id = publishing_service.publish_prediction(
    prediction_id=prediction_id,
    channel="telegram",
    visibility="premium",
    decision_reason_codes=["EDGE"],
    ticket_terms={"line": -5.5, "price": -110, "book": "draftkings"},
    is_official=True
)
```

### Parlay Architect Integration

Modify `parlay_architect.py`:

```python
from services.sim_run_tracker import sim_run_tracker

# For each leg in parlay
for leg in parlay_legs:
    prediction_id = sim_run_tracker.create_prediction(
        sim_run_id=leg["sim_run_id"],
        event_id=leg["event_id"],
        market_key=leg["market_key"],
        ...
    )
```

## Testing

### Manual Testing

```bash
# Initialize database
python backend/scripts/init_logging_calibration_db.py

# Test calibration job
curl -X POST http://localhost:8000/api/calibration/run-calibration-job \
  -H "Content-Type: application/json" \
  -d '{"training_days": 7, "method": "isotonic"}'

# Test grading
curl -X POST http://localhost:8000/api/calibration/grade-all-pending \
  -H "Content-Type: application/json" \
  -d '{"lookback_hours": 48}'

# Check health
curl http://localhost:8000/api/calibration/health
```

### Integration Testing

Create test predictions, publish them, add results, grade them, run calibration.

## Monitoring

Key metrics to monitor:

1. **Active calibration version** - ensure it's recent
2. **Grading lag** - pending vs graded ratio
3. **CLV distribution** - should be positive on average
4. **ECE/Brier trends** - should improve over time
5. **Publish rate** - predictions published per day

## Troubleshooting

### "Insufficient training data"
- Need 500+ settled predictions for calibration
- Wait for more games to be graded

### "No active calibration version"
- Run `POST /api/calibration/run-calibration-job`
- Or manually activate: `POST /api/calibration/activate-calibration/{version}`

### "Cannot grade prediction"
- Event not complete yet (check `event_results`)
- Already graded (use `force_regrade=true`)

### "Calibration rejected"
- New version didn't improve ECE/Brier
- Check metrics: `GET /api/calibration/calibration-versions`

## Production Checklist

- [ ] Run `init_logging_calibration_db.py` on production database
- [ ] Configure calibration scheduler in `main.py`
- [ ] Set up monitoring for calibration jobs
- [ ] Implement data retention cleanup (monthly cron)
- [ ] Add alerting for grading failures
- [ ] Document team workflow for manual interventions
- [ ] Set up backup strategy for `published_predictions` and `grading`

## Support

For issues or questions about this system, contact the development team.

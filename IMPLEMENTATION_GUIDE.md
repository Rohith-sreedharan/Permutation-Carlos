# BeatVegas/SimSports - Complete Implementation Guide

## Overview

This document provides a comprehensive guide to the BeatVegas/SimSports platform implementation. All components are built to exact specifications with zero ambiguity.

---

## Architecture Overview

### Three-Tier Product Strategy

1. **Phase 0: BeatVegas B2C** (beatvegas.app)
   - Consumer-facing sports betting intelligence
   - Subscription tiers: FREE, STARTER ($29.99), PRO ($49.99), ELITE ($89.99)
   - Sharp Pass verification: $999/mo (requires 500+ bets, 2.0%+ CLV edge)
   - Wire Pro community access

2. **Phase 1: Sharp Pass & Wire Pro**
   - CSV-based bet history verification
   - Wire Pro community posting with simulation attachments
   - Priority signal delivery via Telegram

3. **Phase 2: SimSports B2B Terminal** (simsports.io)
   - Institutional API access
   - Tiers: STARTER ($5k/mo), PROFESSIONAL ($15k/mo), INSTITUTIONAL ($50k/mo)
   - Embeddable simulation widgets
   - Rate-limited API endpoints

---

## Core Components Implemented

### 1. Sport-Specific Calibration Modules

All located in `backend/core/`:

#### `sport_configs.py`
- Centralized configuration for all sports
- Compression factors, edge thresholds, spread guardrails
- **NO HARDCODED VALUES** - all thresholds configurable

```python
MLB_CONFIG = SportConfig(
    compression_factor=0.82,
    ml_edge_threshold=3.5,
    total_edge_threshold=2.5,
    requires_pitcher_confirmation=True,
    weather_sensitive=True
)
```

#### Sport-Specific Modules
- `mlb_calibration.py` - Moneyline-first, 0.82 compression
- `ncaab_calibration.py` - Spread-first, 0.80 compression, blowout guardrails
- `ncaaf_calibration.py` - QB confirmation, weather-sensitive, large spreads allowed
- `nfl_calibration.py` - Key numbers (3, 7, 10), tight spread limits
- `nhl_calibration.py` - Most aggressive compression (0.60), goalie confirmation

Each module implements:
- `compress_probability()` - Apply sport-specific compression
- `calculate_edge()` - Edge calculation for market type
- `classify_edge_state()` - EDGE/LEAN/NO_PLAY classification
- `evaluate_market()` - Complete market evaluation with gates
- `grade_result()` - Result grading (WIN/LOSS/PUSH)

### 2. Universal Sharp Side Selection

`backend/core/sharp_side_selection.py`

**Prevents OKC/Spurs type bugs** where model favors one team but UI shows another.

```python
selection = select_sharp_side_spread(
    team_a_cover_prob=0.47,  # Spurs
    team_b_cover_prob=0.53,  # Thunder
    team_a_name="San Antonio Spurs",
    team_b_name="Oklahoma City Thunder",
    spread_team_a=-2.5,  # Spurs favorite
    spread_team_b=+2.5,  # Thunder underdog
    compressed_edge=4.2,
    volatility=VolatilityLevel.MEDIUM
)

# Result: sharp_side = "Oklahoma City Thunder"
# favored_team = "Oklahoma City Thunder"
# points_side = "UNDERDOG"
```

Key rules:
- Edges are prices, not teams
- `sharp_side = favored_team + points_side`
- Volatility penalties for laying points
- Validation that `sharp_side` always set when `edge_state = EDGE`

### 3. Signal Lifecycle & Locking System

`backend/core/signal_lifecycle.py`

**Three-Wave Architecture:**
- **Wave 1** (T-6h): Discovery - internal only, establishes baseline
- **Wave 2** (T-120min): Validation - stability check, edge drift detection
- **Wave 3** (T-60min): Publish gate - final decision with entry snapshot

**Immutable Signals:**
```python
signal = create_signal(game_id, sport, team_a, team_b, game_time)

# Wave 1: Append simulation run
signal = add_simulation_run(signal, wave1_run)

# Wave 2: Check stability
is_stable, reason = check_stability_wave1_to_wave2(wave1_run, wave2_run)

# Wave 3: Lock with entry snapshot
entry = EntrySnapshot(
    sharp_side="Boston Celtics",
    entry_spread=+3.5,
    entry_odds=-110,
    max_acceptable_spread=+3.0
)
signal = lock_signal_with_entry(signal, entry)

# Game starts: Immutable from here
signal = lock_signal_at_game_start(signal)
```

**Action Freeze Windows:**
Prevents re-simulation spam by freezing signals for specified duration.

### 4. Database Schema

`backend/db/schema.sql`

Complete PostgreSQL schema with:
- **users** - Subscriptions, Sharp Pass status, Wire Pro access
- **games** - Game metadata with sport-specific fields (pitcher, QB, goalie)
- **simulations** - Complete simulation runs with result data JSON
- **market_snapshots** - Immutable market state at each wave
- **signals** - Signal lifecycle with entry snapshots
- **sharp_pass_applications** - CSV verification with CLV analysis
- **bet_history** - User bets with CLV tracking
- **community_channels** - Threaded game rooms
- **community_posts** - Posts with simulation attachments
- **sim_audit** - Append-only audit trail
- **rcl_log** - Closing line value tracking
- **calibration_weekly** - Weekly calibration metrics

### 5. API Routes

All in `backend/routes/`:

#### `simulation.py`
- `POST /api/simulation/run` - Run simulation
- `GET /api/simulation/signal/{signal_id}` - Get signal details
- `GET /api/simulation/signals/active` - List active signals
- `POST /api/simsports/run` - B2B API endpoint (rate-limited)

#### `community.py`
- `POST /api/community/channels` - Create channel (game threads)
- `GET /api/community/channels` - List channels (filtered by tier)
- `POST /api/community/posts` - Create post
- `GET /api/community/channels/{slug}/posts` - Get posts
- `WS /api/community/ws/{slug}` - WebSocket for real-time updates
- `POST /api/community/wire-pro/post-with-sim` - Wire Pro exclusive

#### `sharp_pass.py`
- `POST /api/sharp-pass/upload-csv` - Upload bet history
- `GET /api/sharp-pass/applications/me` - My applications
- `POST /api/sharp-pass/applications/{id}/approve` - Admin approve
- `GET /api/sharp-pass/requirements` - Get requirements

### 6. Telegram Integration

`backend/integrations/telegram_bot.py`

**Automated Signal Distribution:**
- Scheduled posts at: 10 AM, 11 AM, 12 PM, 3 PM, 6 PM, 7 PM (ET)
- Tier-specific channels (STARTER, PRO, ELITE, SHARP_PASS)
- Format matches platform UI exactly

```python
# Signal message format
"""
⚾ **MLB SIGNAL** 🔥 **EDGE**

**Game:** Yankees vs Red Sox
**Time:** 07:05 PM ET

**Sharp Side:** New York Yankees
**Market:** MONEYLINE
**Entry:** Yankees ML (-140)

**Edge:** 3.8%
**Volatility:** LOW
**Simulations:** 50,000

📊 View full analysis on BeatVegas.app

_Truth Mode verified. Edges are prices, not predictions._
"""
```

**Join Request Gating:**
- Verifies user subscription tier matches channel
- Auto-approve if tier sufficient
- Sends rejection DM with upgrade link if insufficient

**DM Drip Sequences:**
- Onboarding welcome
- Sharp Pass approval congratulations
- Daily summaries

### 7. Monitoring & Alerting

`backend/services/monitoring.py`

**Health Checks (every 5 minutes):**
1. Calibration drift detection (>1.5% error alerts)
2. Win rate monitoring (<52% alerts)
3. Simulation latency (>5s alerts)
4. API error rate (>5% alerts)
5. Telegram delivery rate (<98% alerts)
6. Database connection
7. Sharp Pass verification queue
8. SimSports API usage

**Automated Alerts:**
- Slack integration for CRITICAL/WARNING
- Critical → #alerts-critical
- Warnings → #alerts-warnings

---

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/beatvegas
REDIS_URL=redis://localhost:6379

# API Keys
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
STRIPE_SECRET_KEY=sk_live_...

# Telegram Channels
TELEGRAM_STARTER_CHANNEL_ID=-100...
TELEGRAM_PRO_CHANNEL_ID=-100...
TELEGRAM_ELITE_CHANNEL_ID=-100...
TELEGRAM_SHARP_PASS_CHANNEL_ID=-100...

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Sport Configs (optional overrides)
MLB_COMPRESSION_FACTOR=0.82
NFL_COMPRESSION_FACTOR=0.85
NCAAB_COMPRESSION_FACTOR=0.80

# Monitoring
ALERT_CALIBRATION_ERROR_MAX=1.5
ALERT_WIN_RATE_MIN=0.52
ALERT_SIMULATION_LATENCY_MAX=5000
```

---

## Deployment

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Initialize database
psql -U postgres -d beatvegas -f db/schema.sql

# Run migrations (if any)
alembic upgrade head

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Background Workers

```bash
# Telegram scheduler
python -m services.telegram_scheduler

# Monitoring loop
python -m services.monitoring_loop

# Signal wave processor
python -m services.wave_processor
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Build
npm run build

# Start production server
npm run start
```

---

## Testing

### Unit Tests

```bash
# Test sport calibration modules
pytest backend/tests/test_mlb_calibration.py
pytest backend/tests/test_nfl_calibration.py

# Test sharp side selection
pytest backend/tests/test_sharp_side_selection.py

# Test signal lifecycle
pytest backend/tests/test_signal_lifecycle.py
```

### Integration Tests

```bash
# End-to-end signal flow
pytest backend/tests/integration/test_signal_flow.py

# Telegram integration
pytest backend/tests/integration/test_telegram.py

# API endpoints
pytest backend/tests/integration/test_api.py
```

---

## Critical Implementation Rules

### 1. Immutability
- Signals are append-only after publish
- Entry snapshots capture price at decision time
- No re-simulation after game starts

### 2. Sharp Side Alignment
- Backend always computes `sharp_side`
- AI Analyzer MUST respect backend decision
- Validation checks prevent misalignment

### 3. Sport-Specific Calibration
- Each sport has unique compression factor
- Thresholds must be configurable, not hardcoded
- Guardrails prevent extreme spreads/totals

### 4. Access Control
- Tier hierarchy: FREE < STARTER < PRO < ELITE < SHARP_PASS
- Wire Pro requires Sharp Pass approval
- SimSports B2B separate from consumer tiers

### 5. Monitoring
- Continuous calibration drift detection
- Automated alerts for anomalies
- Weekly recalibration based on results

---

## Support & Maintenance

### Weekly Tasks
1. Review calibration metrics (every Monday)
2. Audit Sharp Pass applications (daily)
3. Check Telegram delivery logs (daily)
4. Review system alerts (continuous)

### Monthly Tasks
1. Recalibrate compression factors if needed
2. Review B2B SimSports usage
3. Analyze churn/retention metrics
4. Update documentation

### Incident Response
1. CRITICAL alerts → Immediate Slack notification
2. Database failures → Auto-failover to replica
3. API downtime → Status page update + user notification
4. Calibration drift → Pause affected sport, investigate

---

## Contact

For implementation questions or clarifications:
- Technical: dev@beatvegas.app
- Product: product@beatvegas.app
- Operations: ops@beatvegas.app

---

## License

Proprietary. All rights reserved. BeatVegas/SimSports © 2025

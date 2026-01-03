# Quick Reference - BeatVegas/SimSports

## 🎯 Core Principles

1. **Edges are prices, not teams** - Entry snapshot captures exact price at decision time
2. **Signals are immutable** - No changes after publish
3. **Sharp side = favored_team + points_side** - Universal alignment rule
4. **Three-wave architecture** - Discovery → Validation → Publish
5. **Sport-specific calibration** - Each sport has unique thresholds

---

## 📁 File Structure Quick Reference

```
backend/
├── core/
│   ├── sport_configs.py          # All sport thresholds (configurable)
│   ├── mlb_calibration.py        # MLB: 0.82 compression, moneyline-first
│   ├── nfl_calibration.py        # NFL: 0.85 compression, key numbers
│   ├── ncaab_calibration.py      # NCAAB: 0.80 compression, large spreads
│   ├── ncaaf_calibration.py      # NCAAF: 0.80 compression, QB required
│   ├── nhl_calibration.py        # NHL: 0.60 compression (most aggressive)
│   ├── sharp_side_selection.py   # Universal sharp side logic
│   └── signal_lifecycle.py       # Three-wave + immutability
├── db/
│   └── schema.sql                # Complete PostgreSQL schema
├── routes/
│   ├── simulation.py             # Simulation API
│   ├── community.py              # War Room API + WebSocket
│   └── sharp_pass.py             # Sharp Pass verification
├── integrations/
│   └── telegram_bot.py           # Automated signal posting
└── services/
    └── monitoring.py             # Health checks + alerts
```

---

## 🔑 Key Functions By Use Case

### Running a Simulation

```python
from backend.core.mlb_calibration import evaluate_mlb_market

# Evaluate MLB moneyline market
result = evaluate_mlb_market(
    market_type=MarketType.MONEYLINE,
    sim_win_prob=0.58,              # From Monte Carlo
    odds=-140,                       # American odds
    simulation_results={'win_prob_std': 0.025},
    pitcher_confirmed=True,
    weather_clear=True
)

# result.edge_state = EDGE/LEAN/NO_PLAY
# result.compressed_edge = 3.8 (percentage)
# result.eligible = True/False
```

### Selecting Sharp Side

```python
from backend.core.sharp_side_selection import select_sharp_side_spread

selection = select_sharp_side_spread(
    team_a_cover_prob=0.47,         # Favorite cover %
    team_b_cover_prob=0.53,         # Underdog cover %
    team_a_name="San Antonio Spurs",
    team_b_name="Oklahoma City Thunder",
    spread_team_a=-2.5,             # Spurs are favorite
    spread_team_b=+2.5,             # Thunder are underdog
    compressed_edge=4.2,
    volatility=VolatilityLevel.MEDIUM,
    market_odds_team_a=-110,
    market_odds_team_b=-110
)

# selection.sharp_side = "Oklahoma City Thunder"
# selection.points_side = "UNDERDOG"
# selection.recommended_bet = "Oklahoma City Thunder +2.5 (-110)"
```

### Managing Signal Lifecycle

```python
from backend.core.signal_lifecycle import (
    create_signal, add_simulation_run, lock_signal_with_entry
)

# Create signal
signal = create_signal(game_id, sport, team_a, team_b, game_time)

# Add Wave 1 simulation
signal = add_simulation_run(signal, wave1_run)

# Lock with entry snapshot at publish
entry = EntrySnapshot(
    sharp_side="Boston Celtics",
    market_type="SPREAD",
    entry_spread=+3.5,
    entry_odds=-110,
    max_acceptable_spread=+3.0
)
signal = lock_signal_with_entry(signal, entry)

# Lock at game start (immutable from here)
signal = lock_signal_at_game_start(signal)
```

---

## 🎚️ Configuration Values

### Compression Factors
```python
MLB:    0.82  # Moderate
NFL:    0.85  # Light
NCAAB:  0.80  # Aggressive
NCAAF:  0.80  # Aggressive
NHL:    0.60  # MOST aggressive
NBA:    0.83  # Moderate
```

### Edge Thresholds (EDGE classification)
```python
MLB Moneyline:  3.5%
MLB Total:      2.5%
NFL Spread:     4.5%
NFL Total:      5.0%
NCAAB Spread:   6.0%
NCAAF Spread:   6.0%
NHL Puckline:   1.5%
NHL Total:      2.5%
```

### Subscription Tiers
```python
FREE:       $0/mo    (no Telegram access)
STARTER:    $29.99/mo
PRO:        $49.99/mo
ELITE:      $89.99/mo
SHARP_PASS: $999/mo  (requires 500+ bets, 2.0%+ CLV)
```

### SimSports B2B Tiers
```python
STARTER:        $5,000/mo   (100 sims/day)
PROFESSIONAL:   $15,000/mo  (1,000 sims/day)
INSTITUTIONAL:  $50,000/mo  (10,000 sims/day)
```

---

## 🚦 Status Enums

### EdgeState
```python
EDGE      # Publish to users
LEAN      # Lower confidence edge
NO_PLAY   # Do not publish
```

### SignalStatus
```python
DISCOVERED   # Wave 1 complete
VALIDATING   # Wave 2 in progress
VALIDATED    # Wave 2 passed
UNSTABLE     # Wave 2 failed stability
PUBLISHED    # Published to users
LOCKED       # Game started (immutable)
GRADED       # Result recorded
```

### VolatilityLevel
```python
LOW       # σ < 0.02
MEDIUM    # σ < 0.04
HIGH      # σ < 0.06
EXTREME   # σ >= 0.06
```

---

## 📊 Database Tables Quick Reference

### Core Tables
```sql
users                -- Subscriptions + Sharp Pass status
games                -- Game metadata
simulations          -- Simulation runs
market_snapshots     -- Market state at each wave
signals              -- Signal lifecycle
```

### Community
```sql
community_channels   -- Threaded game rooms
community_posts      -- Posts with sim attachments
```

### Verification & Tracking
```sql
sharp_pass_applications  -- CSV verification
bet_history              -- User bets + CLV
rcl_log                  -- Closing line value
calibration_weekly       -- Performance metrics
```

### Audit
```sql
sim_audit           -- Simulation events
telegram_posts      -- Telegram delivery log
simsports_api_requests  -- B2B API usage
```

---

## 🔌 API Endpoints Quick Reference

### Simulation
```
POST   /api/simulation/run
GET    /api/simulation/signal/{id}
GET    /api/simulation/signals/active
POST   /api/simsports/run  (B2B only)
```

### Community
```
POST   /api/community/channels
GET    /api/community/channels
POST   /api/community/posts
GET    /api/community/channels/{slug}/posts
WS     /api/community/ws/{slug}
POST   /api/community/wire-pro/post-with-sim
```

### Sharp Pass
```
POST   /api/sharp-pass/upload-csv
GET    /api/sharp-pass/applications/me
POST   /api/sharp-pass/applications/{id}/approve
GET    /api/sharp-pass/requirements
```

---

## ⚠️ Critical Validations

### Must Always Check
1. **Sharp side set when edge exists:**
   ```python
   if edge_state in [EDGE, LEAN] and not sharp_side:
       raise CriticalError("Sharp side not set")
   ```

2. **Signal immutability:**
   ```python
   if signal.status == PUBLISHED:
       raise ImmutableSignalError("Cannot modify")
   ```

3. **Sport-specific confirmations:**
   ```python
   if sport == MLB and not pitcher_confirmed:
       return NO_PLAY
   if sport == NFL and not qb_confirmed:
       return NO_PLAY
   ```

4. **Telegram format matches UI:**
   Every Telegram post must match platform exactly

---

## 🏃 Quick Start Commands

### Development
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Database
psql -d beatvegas -f db/schema.sql

# Background workers
python -m integrations.telegram_scheduler
python -m services.monitoring_loop
```

### Testing
```bash
# Unit tests
pytest backend/tests/test_mlb_calibration.py

# Integration tests
pytest backend/tests/integration/

# Load tests
locust -f tests/load/locustfile.py
```

### Production
```bash
# Deploy backend
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker-compose logs -f backend
```

---

## 📞 Emergency Contacts

### Critical Alerts
- Calibration drift >2.5%: **CRITICAL** - Pause sport
- Win rate <50%: **CRITICAL** - Investigate immediately
- Database connection lost: **CRITICAL** - Failover to replica
- Telegram delivery <90%: **WARNING** - Check bot status

### Monitoring Thresholds
```python
CALIBRATION_ERROR_MAX:    1.5%
WIN_RATE_MIN:             52%
SIMULATION_LATENCY_MAX:   5000ms
API_ERROR_RATE_MAX:       5%
TELEGRAM_DELIVERY_MIN:    98%
```

---

## 🎓 Learning Path

1. **Start here:** `DEVELOPER_HANDOFF.md` (full context)
2. **Deep dive:** `IMPLEMENTATION_GUIDE.md` (architecture)
3. **Code first:** `backend/core/sport_configs.py` (understand configs)
4. **Then:** Pick a sport calibration module (`mlb_calibration.py`)
5. **Critical:** `sharp_side_selection.py` (prevents bugs)
6. **Finally:** `signal_lifecycle.py` (three-wave system)

---

## 💡 Pro Tips

1. **Never hardcode thresholds** - Use `sport_configs.py`
2. **Always validate sharp_side** - Call `validate_sharp_side_alignment()`
3. **Log everything** - Use `sim_audit` table
4. **Test edge cases** - Large spreads, extreme volatility, key numbers
5. **Monitor calibration** - Weekly review required

---

## 📚 Documentation Files

- `DEVELOPER_HANDOFF.md` - Complete handoff document
- `IMPLEMENTATION_GUIDE.md` - Architecture & deployment
- `QUICK_REFERENCE.md` - This file
- `backend/db/schema.sql` - Database schema with comments
- Individual module docstrings - Inline documentation

---

**Last Updated:** 2025-01-XX  
**Version:** 1.0  
**Status:** Production Ready (Backend) 🚀

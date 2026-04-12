# QUICK REFERENCE - Failed to Load Decision Diagnostics

## Current Status: ⚠️ Infrastructure Offline
```
❌ MongoDB: NOT RUNNING
❌ Backend API: NOT RUNNING  
⚠️ Odds API: Returns 422 for MLB (minor issue)
```

---

## 5-ITEM DIAGNOSTIC CHECKLIST

| Item | Status | Finding | Next Action |
|------|--------|---------|-------------|
| **1. API Response** | ❌ BLOCKED | Backend server offline | Start `python main.py` |
| **2. Odds Pipeline** | ❌ BLOCKED | Cannot query MongoDB | Start MongoDB service |
| **3. Market Snapshots** | ❌ BLOCKED | No database access | Run `mongosh` query after startup |
| **4. Decision Records** | ❌ BLOCKED | Cannot verify DB | Query `db.decision_records.countDocuments()` |
| **5. Data Providers** | ⚠️ MLB Error | 422: Missing region param | Update API request params |

---

## START SERVICES (5 minutes)

### Terminal 1: MongoDB
```bash
brew services start mongodb-community
sleep 2
mongosh --eval "db.adminCommand('ping')"
```

### Terminal 2: Backend
```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
source .venv/bin/activate
python main.py
# Wait: "✅ Application startup complete"
```

### Terminal 3: Frontend (optional)
```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run dev
```

---

## RUN DIAGNOSTICS (5 minutes)

```bash
# Full diagnostic report
python backend/diagnostic_reporter.py --league nba

# For specific game showing "Failed to load decision"
python backend/diagnostic_reporter.py --league nba --game-id <game_id>

# Output file
cat diagnostic_report.json | jq .
```

---

## WHAT YOU'LL GET

### From Diagnostic 1: API Response
```json
{
  "spread": {
    "classification": "EDGE",
    "release_status": "OFFICIAL",
    "pick": {"team_name": "Lakers", "side": "home"},
    "market": {"line": -7.5, "odds": -110},
    "edge": {"edge_points": 2.3}
  },
  "moneyline": {...},
  "total": {...}
}
```

### From Diagnostic 2: Odds Pipeline  
```
Pipeline Running: True/False
Last Update: 2026-04-07T15:20:00Z
Recent Events: 47 total
```

### From Diagnostic 3: Market Snapshots
```
Total in 24h: 42
Sample:
  - game_id: nba_lal_vs_gsw, created_at: 2026-04-07T15:15:00Z, status: completed
  - game_id: nba_lac_vs_bos, created_at: 2026-04-07T15:10:00Z, status: completed
```

### From Diagnostic 4: Decision Records  
```
Total in DB: 157
game_id "nba_xyz":
  EXISTS: Yes
  Record ID: rec_123
  Status: OFFICIAL
  Classification: EDGE
```

### From Diagnostic 5: Data Providers
```
Provider: The Odds API
NBA: LIVE (42 active games)
MLB: ERROR_422 (missing regions param) ⚠️
NHL: OUT_OF_SEASON (expected)
NFL: LIVE (8 active games)
```

---

## FAILURE MODES (Locate Your Issue)

### Type A: Event Not Found (HTTP 404)
**Error in code:** `Game {game_id} not found`  
**Causes:**
- Odds pipeline hasn't run
- Wrong game ID format  
- Odds polling failed

**Check:**
```bash
mongosh
> db.events.findOne({sport_key: /basketball_nba/})
> db.events.countDocuments()
```

### Type B: No Odds Available (HTTP 404)
**Error in code:** `No odds available for {game_id}`  
**Causes:**
- Event exists but no bookmakers
- Odds API returned empty markets
- Normalization stripped bookmakers

**Check:**
```bash
mongosh
> db.events.findOne({id: "GAME_ID"}).bookmakers
# Should have: [{title: "DraftKings", markets: [...]}]
```

### Type C: Decision Computation Error (HTTP 500)  
**Error in code:** Exception during `MarketDecisionComputer.compute_all()`  
**Causes:**
- Missing Monte Carlo simulations
- Exception in probability calc
- Missing model/simulation data

**Check:**
```bash
mongosh
> db.monte_carlo_simulations.findOne({game_id: "GAME_ID"})
> db.decision_records.findOne({game_id: "GAME_ID"})
```

---

## DIAGNOSTIC REPORTS LOCATION

| File | Purpose | Requires Services? |
|------|---------|-------------------|
| [ROOT_CAUSE_DIAGNOSTIC_REPORT.md](ROOT_CAUSE_DIAGNOSTIC_REPORT.md) | High-level guide | ❌ No |
| [DIAGNOSTIC_CHECKLIST.md](DIAGNOSTIC_CHECKLIST.md) | Detailed checklist | ❌ No |
| [diagnostic_reporter.py](backend/diagnostic_reporter.py) | Runtime diagnostics | ✅ Yes |
| [diagnostic_static_analysis.py](backend/diagnostic_static_analysis.py) | Code analysis | ❌ No |

---

## QUICK COMMANDS

```bash
# Test MongoDB
mongosh --eval "db.adminCommand('ping')"

# Test Backend API
curl http://localhost:8000/api/health

# Find games in DB
mongosh
> use beatvegas
> db.events.countDocuments()
> db.events.find({sport_key: /basketball_nba/}).limit(1).pretty()

# Count decision records
mongosh
> db.decision_records.countDocuments()

# Check odds freshness
mongosh  
> db.events.findOne().updated_at
# If > 1 hour old, pipeline may be stalled

# View static analysis (no services needed)
python backend/diagnostic_static_analysis.py
# Output: diagnostic_static_analysis.json
```

---

## MLB API FIX (Minor Issue)

**Issue:** `422 MISSING_REGION`  
**File:** [backend/integrations/odds_api.py](backend/integrations/odds_api.py) or [backend/services/scheduler.py](backend/services/scheduler.py)

**Current (Wrong):**
```python
params = {
    "apiKey": api_key,
    "markets": markets,
    "oddsFormat": "decimal"
}
```

**Fixed (Correct):**
```python
params = {
    "apiKey": api_key,
    "regions": "us",  # ← ADD THIS
    "markets": markets,
    "oddsFormat": "decimal"
}
```

---

## TIME ESTIMATES

| Task | Time |
|------|------|
| Start services | 5 min |
| Run diagnostics | 5 min |
| Analyze results | 5 min |
| Identify root cause | 5 min |
| **Total Discovery** | **20 min** |
| Implement fix | 10-30 min |
| Verify fix | 5 min |
| **Total Resolution** | **35-55 min** |

---

**Generated:** 2026-04-07  
**Requires Action:** YES - Start MongoDB and Backend
**Urgency:** Determine after running diagnostics

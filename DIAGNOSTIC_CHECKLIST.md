# DIAGNOSTIC SUMMARY - "Failed to Load Decision" Investigation
## Complete Analysis Report

**Date:** April 7, 2026  
**Status:** Infrastructure Offline / Static Analysis Complete  
**Next Action:** Start services and re-run for full diagnostics

---

## 🔴 CRITICAL FINDINGS

### Current Infrastructure Status
```
❌ MongoDB Server        → NOT RUNNING (connection refused:27017)
❌ Backend API Server    → NOT RUNNING (connection refused:8000)
⚠️  Odds API Provider    → ACCESSIBLE but MLB endpoint returning 422 error
```

---

## DIAGNOSTIC RESULTS: 5-ITEM CHECKLIST

### 1. ❌ API Response (Required)
**Status:** BLOCKED - Backend server offline

**Expected Endpoint:** `GET /api/games/{league}/{game_id}/decisions`

**Expected Response Structure:**
```json
{
  "spread": {
    "league": "nba",
    "game_id": "game123",
    "market_type": "SPREAD",
    "classification": "EDGE" | "LEAN" | "MARKET_ALIGNED" | "BLOCKED",
    "release_status": "OFFICIAL" | "BLOCKED_BY_RISK" | "BLOCKED_BY_INTEGRITY" | "BLOCKED_MISSING_CONTEXT",
    "pick": {
      "team_name": "Lakers",
      "side": "home"
    },
    "market": {
      "line": -7.5,
      "odds": -110
    },
    "edge": {
      "edge_points": 2.3
    },
    "probabilities": {
      "model_prob": 0.58,
      "market_implied_prob": 0.52
    }
  },
  "moneyline": { ... },
  "total": { ... }
}
```

**Action to retrieve:**
```bash
# Once backend is running:
curl http://localhost:8000/api/games/nba/game_id/decisions | jq .

# Or use diagnostic script:
python backend/diagnostic_reporter.py --league nba --game-id <game_id> --output api_response.json
```

---

### 2. ⚠️ Odds Ingestion Pipeline Status  
**Status:** BLOCKED - Cannot verify without MongoDB

**Pipeline Configuration:**
- **Type:** APScheduler background job
- **Function:** `poll_odds_api()`
- **Frequency:** Interval-based (estimated 5-10 minutes)
- **Performance SLO:** < 20s pre-match, < 10s in-play

**Pipeline Flow:**
```
1. Request: GET /v4/sports/{sport}/odds?apiKey=KEY&regions=us&markets=spreads,totals
2. Normalize: Add EST timestamps, convert odds format (decimal → American)
3. Upsert: db["events"].update_one({"id": event_id}, {"$set": normalized}, upsert=True)
4. Log: Stage completion and latency metrics
```

**Last Successful Run:** UNKNOWN (cannot query MongoDB)

**To verify once online:**
```bash
# Method 1: Check database
mongosh
> use beatvegas
> db.events.findOne().updated_at
> db.events.countDocuments()

# Method 2: Check logs
grep "✓ Polled" backend/logs/*.log | tail -1

# Method 3: Run diagnostic
python backend/diagnostic_reporter.py
```

---

### 3. ❌ Market Snapshots (24h History)
**Status:** BLOCKED - MongoDB offline

**Query to Execute:**
```mongodb
SELECT game_id, created_at, status  
FROM market_snapshots  
WHERE created_at > NOW() - INTERVAL '24 hours'  
ORDER BY created_at DESC  
LIMIT 20
```

**MongoDB Equivalent:**
```javascript
db.market_snapshots.find({
  'created_at': {
    '$gt': new Date(Date.now() - 24*60*60*1000)
  }
}).sort({'created_at': -1}).limit(20)
```

**Collection Details:**
| Field | Type | Purpose |
|-------|------|---------|
| `_id` | ObjectId | MongoDB document ID |
| `game_id` | String | Game identifier |
| `created_at` | DateTime | Snapshot creation timestamp |
| `status` | String | Snapshot processing status |
| `wave` | String | Signal wave (WAVE_1, WAVE_2, WAVE_3) |
| `market_spread` | Object | Spread market snapshot |
| `market_total` | Object | Total market snapshot |

**Expected Result:** 20-500 snapshots (highly depends on active games)

---

### 4. ❌ Decision Records Existence
**Status:** BLOCKED - MongoDB offline

**Query to Execute:**
```javascript
// Count total records
db.decision_records.countDocuments()

// Find records for specific game
db.decision_records.find({game_id: "GAME_ID"})

// Check if record has required fields
db.decision_records.findOne({game_id: "GAME_ID"}).pretty()
```

**Record Structure:**
```json
{
  "_id": ObjectId("..."),
  "identity_key": "sha256(league:game_id:inputs_hash:version)",
  "record_id": "unique_id",
  "game_id": "game123",
  "created_at": ISODate("2026-04-07T12:00:00Z"),
  "updated_at": ISODate("2026-04-07T12:00:00Z"),
  "classification": "EDGE|LEAN|MARKET_ALIGNED|BLOCKED",
  "release_status": "OFFICIAL|BLOCKED_BY_RISK|BLOCKED_BY_INTEGRITY|BLOCKED_MISSING_CONTEXT",
  "spread": {
    "decision_id": "uuid",
    "pick": {...},
    "market": {...},
    "edge": {...}
  },
  "total": {...},
  "moneyline": {...}
}
```

**Indexes:**
```javascript
db.decision_records.getIndexes()
// Should show:
// - {identity_key: 1} UNIQUE
// - {record_id: 1} UNIQUE  
// - {game_id: 1, created_at: -1}
```

**Current Status:**
- Total records in DB: **UNKNOWN** (cannot connect)
- Records for affected game: **UNKNOWN** (cannot connect)

---

### 5. ⚠️ Data Provider Confirmation

#### MLB (Baseball)
- **Provider:** The Odds API
- **Status:** ❌ **ERROR_422 - MISSING_REGION**
- **Error Message:**
  ```json
  {
    "message": "Missing regions or bookmakers key",
    "error_code": "MISSING_REGION",
    "details_url": "https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-region"
  }
  ```
- **Root Cause:** API request not including required parameter
- **Current Request:** `GET /v4/sports/baseball_mlb/odds?apiKey=KEY&markets=h2h,spreads,totals`
- **Required Parameter Missing:** `regions=us` or `bookmakers=draftkings,fanduel`
- **Fix:** Update [backend/services/scheduler.py](backend/services/scheduler.py) or [backend/integrations/odds_api.py](backend/integrations/odds_api.py)

#### NHL (Ice Hockey)
- **Provider:** The Odds API
- **Status:** ⚠️ **OUT_OF_SEASON / NOT_ACTIVE**
- **Error Code:** 404 (expected during off-season)
- **Expected Behavior:** Returns 404, pipeline handles gracefully
- **Status Code:** 404 (correct behavior)

#### NBA & NFL
- **Provider:** The Odds API
- **Status:** UNKNOWN (cannot test without backend running)
- **Check with:** `curl "https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey=KEY&regions=us&markets=spreads,totals"`

---

## FAILURE MODE ANALYSIS

Based on code inspection, "Failed to Load Decision" occurs in 3 scenarios:

### Scenario A: Event Not Found (HTTP 404)
**File:** [backend/routes/decisions.py](backend/routes/decisions.py#L195)

```python
event = db["events"].find_one({"$or": [{"id": game_id}, {"event_id": game_id}]})
if not event:
    raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    # Frontend catches 404 → displays "Failed to load decision"
```

**Root Causes:**
1. ❌ Odds pipeline hasn't run yet (no events in `db["events"]`)
2. ❌ Game ID doesn't match database format (id vs event_id)
3. ❌ Odds polling failed silently with wrong sport code

### Scenario B: No Odds Available (HTTP 404)
**File:** [backend/routes/decisions.py](backend/routes/decisions.py#L201)

```python
bookmakers = event.get("bookmakers", [])
if not bookmakers:
    raise HTTPException(status_code=404, detail=f"No odds available for {game_id}")
    # Frontend catches 404 → displays "Failed to load decision"
```

**Root Causes:**
1. ❌ Event in database but bookmakers field empty
2. ❌ Odds API returned event without markets
3. ❌ Normalization function stripped bookmakers during processing

### Scenario C: Decision Computation Error (HTTP 500)
**File:** [backend/routes/decisions.py](backend/routes/decisions.py#L224)

```python
decisions = MarketDecisionComputer.compute_all(
    event=event,
    odds_data=odds_snapshot,
    sim_results=simulations
)
# If any exception → HTTP 500
# Frontend catches 500 → displays "Failed to load decision"
```

**Root Causes:**
1. ❌ Missing Monte Carlo simulations for game
2. ❌ Odds data format change not handled
3. ❌ Exception in probability calculation
4. ❌ Missing model or simulation data

---

## CONFIGURATION VERIFICATION

### ✅ Environment Variables Configured
```bash
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=beatvegas  
ODDS_API_KEY=375cdd35...  
ODDS_BASE_URL=https://api.the-odds-api.com/v4
```

### ✅ Code Structure Verified
- Decisions endpoint: ✅ PRESENT
- Odds pipeline: ✅ PRESENT  
- Decision computation: ✅ PRESENT
- Database models: ✅ PRESENT

---

## REMEDIATION STEPS

### Phase 1: Start Infrastructure (5-10 min)

```bash
# Terminal 1: Start MongoDB
brew services start mongodb-community
sleep 2
mongosh --eval "db.adminCommand('ping')"   # Should print {"ok": 1}

# Terminal 2: Start Backend
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
source .venv/bin/activate
python main.py
# Wait for: "✅ Application startup complete"

# Terminal 3: Start Frontend (optional)
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run dev
```

### Phase 2: Verify Services (2-3 min)

```bash
# Test MongoDB
mongosh --eval "db.version()"

# Test Backend
curl http://localhost:8000/api/health

# Check if events in database
mongosh
> use beatvegas
> db.events.countDocuments()
> db.events.findOne().id
```

### Phase 3: Run Full Diagnostics (5 min)

```bash
# Quick diagnostics
python backend/diagnostic_reporter.py --league nba --output report_full.json

# View results
cat report_full.json | jq '.diagnostics[] | {item: .description, status: .error}'
```

### Phase 4: Identify Affected Games (5 min)

```bash
# In your application, find a game showing "Failed to load decision"
# Note the game_id
# Then run:

python backend/diagnostic_reporter.py --league nba --game-id <game_id> --output report_affected_game.json

# This will show:
# 1. Whether API returns data
# 2. Whether decision record exists
# 3. Specific error from backends
```

---

## FILES & TOOLS

### Diagnostic Scripts Created
1. **[backend/diagnostic_reporter.py](backend/diagnostic_reporter.py)**
   - Requires: MongoDB + Backend API running
   - Gathers: All 5 diagnostic items with actual data
   - Usage: `python diagnostic_reporter.py --league nba --game-id <id>`

2. **[backend/diagnostic_static_analysis.py](backend/diagnostic_static_analysis.py)**
   - Requires: None (static code analysis only)
   - Gathers: Configuration, code structure, expected failure modes
   - Usage: `python diagnostic_static_analysis.py`

### Generated Reports
1. **[ROOT_CAUSE_DIAGNOSTIC_REPORT.md](../ROOT_CAUSE_DIAGNOSTIC_REPORT.md)** ← START HERE
   - High-level summary with remediation steps
   - Requires human infrastructure startup

2. **diagnostic_report.json** (online version)
   - Full runtime diagnostics
   - Generated after services online

3. **diagnostic_static_analysis.json**
   - Code and configuration analysis
   - Generated (no services needed)

---

## NEXT IMMEDIATE STEPS

1. **Start MongoDB:**
   ```bash
   brew services start mongodb-community
   ```

2. **Start Backend:**
   ```bash
   cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
   source .venv/bin/activate
   python main.py
   ```

3. **Identify one failing game** from your application UI

4. **Run diagnostics:**
   ```bash
   python backend/diagnostic_reporter.py --league nba --game-id <identified_game_id>
   ```

5. **Analyze output** against failure scenarios A/B/C above

6. **Apply fix** based on which scenario matches

---

## ESTIMATED TIME TO RESOLUTION

- **Discovery:** 5-10 minutes (services startup + 1 diagnostic run)
- **Root cause identification:** 5 minutes (compare output to scenarios)
- **Fix implementation:** 10-30 minutes (depends on scenario)
- **Verification:** 5 minutes (re-run diagnostic)

**Total:** 25-55 minutes

---

Last Updated: 2026-04-07 15:30 UTC

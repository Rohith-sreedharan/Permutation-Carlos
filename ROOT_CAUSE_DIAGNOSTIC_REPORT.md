# ROOT CAUSE DIAGNOSTIC REPORT
## "Failed to Load Decision" State Investigation

**Report Generated:** 2026-04-07 15:21:45 UTC  
**Status:** ⚠️ **CRITICAL INFRASTRUCTURE OFFLINE**

---

## EXECUTIVE SUMMARY

The "Failed to Load Decision" errors cannot be fully diagnosed because **critical infrastructure services are not running**:

1. ❌ **MongoDB** - NOT RUNNING (connection refused on 27017)
2. ❌ **Backend API Server** - NOT RUNNING (connection refused on 8000)
3. ⚠️ **Odds API** - PARTIALLY ACCESSIBLE (MLB returning 422 error, NHL out of season)

**Cannot proceed with full diagnostics until services are online.**

---

## DIAGNOSTIC FINDINGS

### 1. ❌ API Response - BLOCKED (Backend Offline)

**Status:** Cannot retrieve  
**Reason:** Backend API server not responding on http://localhost:8000

**Required Action:**
```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run dev  # Start frontend + backend

# Or run backend separately:
cd backend
source .venv/bin/activate
python main.py
```

**Once online, run:**
```bash
# Will retrieve full JSON response for a game
python backend/diagnostic_reporter.py --league nba --game-id <game_id>
```

---

### 2. ⚠️ Odds Ingestion Pipeline Status - BLOCKED (MongoDB Offline)

**Status:** Cannot verify  
**Reason:** MongoDB not running - pipeline cannot be queried

**Database Connection Details:**
- **MONGO_URI:** Configured
- **Database Name:** beatvegas
- **Connection String:** mongodb://localhost:27017
- **Status:** CONNECTION REFUSED (Errno 61)

**What we would check when online:**
- Last successful odds poll timestamp
- Recent event updates in `events` collection
- Pipeline job status in APScheduler

**To start MongoDB:**
```bash
# Install MongoDB if needed:
brew install mongodb-community

# Start MongoDB:
brew services start mongodb-community

# Verify connection:
mongosh --eval "db.version()"
```

---

### 3. ❌ Market Snapshots (24h history) - BLOCKED (MongoDB Offline)

**Exact Query:**
```mongodb
db.market_snapshots.find({
  'created_at': {
    '$gt': ISODate('2026-04-06T15:21:45.599Z')
  }
}).sort({'created_at': -1}).limit(20)
```

**Expected Columns:**
- `game_id` - The game identifier
- `created_at` - Timestamp of snapshot creation
- `status` - Current status of the snapshot

**Current Result:** 0 records (database offline)

**To retrieve once online:**
```bash
# Using MongoDB shell
mongosh
> use beatvegas
> db.market_snapshots.find({created_at: {$gt: new Date(Date.now() - 24*60*60*1000)}}).sort({created_at: -1}).limit(20)

# Or via diagnostic script:
python backend/diagnostic_reporter.py
```

---

### 4. ❌ Decision Records Existence - BLOCKED (MongoDB Offline)

**Status:** Cannot query  
**Collection:** `decision_records`

**What we need to verify:**
1. Whether DecisionRecord exists for affected game
2. If exists: Full record including identity_key, classification, release_status
3. If not exists: Explicitly confirm absence

**Current Result:**
- Total decision records in DB: 0 (unconfirmed - cannot connect)
- Records for specific game: UNKNOWN

**Schema Reference (from code):**
```python
# Collection: decision_records
# Key indexes:
#   - (identity_key, unique) 
#   - (record_id, unique)
#   - (game_id, created_at DESC)

# Record structure:
{
  _id: ObjectId,
  identity_key: str,        # SHA256(league:game_id:inputs_hash:version)
  record_id: str,           # Unique record identifier
  game_id: str,
  created_at: datetime,
  classification: str,      # EDGE | LEAN | MARKET_ALIGNED | BLOCKED
  release_status: str,      # OFFICIAL | BLOCKED_BY_RISK | BLOCKED_BY_INTEGRITY | BLOCKED_MISSING_CONTEXT
  spread: dict,
  total: dict,
  moneyline: dict
}
```

**To check once online:**
```bash
mongosh
> use beatvegas
> db.decision_records.find({game_id: "TARGET_GAME_ID"}).pretty()
> db.decision_records.countDocuments()
```

---

### 5. ⚠️ Data Provider Status - PARTIALLY ACCESSIBLE

**Primary Provider:** The Odds API  
**Endpoint:** https://api.the-odds-api.com/v4  
**API Key Status:** ✅ Configured

#### MLB (Baseball)
- **Status:** ❌ **ERROR_422 - MISSING_REGION**
- **Error Details:** 
  ```json
  {
    "message": "Missing regions or bookmakers key",
    "error_code": "MISSING_REGION",
    "details_url": "https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html#missing-region"
  }
  ```
- **Root Cause:** API request not including required `regions` or `bookmakers` parameter
- **Fix Required:** Update odds API integration to include region parameters

#### NHL (Ice Hockey)
- **Status:** ⚠️ **DELAYED (Out of Season)**
- **Error Details:** Sport not available or not yet scheduled for current date
- **Expected Status:** Returns 404 during off-season (expected behavior)

---

## REQUIRED STEPS TO COMPLETE FULL DIAGNOSTICS

### Phase 1: Start Infrastructure (5-10 minutes)

```bash
# Terminal 1: Start MongoDB
brew services start mongodb-community
sleep 2
mongosh --eval "db.adminCommand('ping')"

# Terminal 2: Start Backend API
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
source .venv/bin/activate
python main.py
# Wait for: "✅ Application startup complete"

# Terminal 3: Start Frontend (optional)
cd /Users/rohithaditya/Downloads/Permutation-Carlos
npm run dev
```

### Phase 2: Verify Infrastructure (2 minutes)

```bash
# Check MongoDB
mongosh --eval "db.version()"

# Check Backend
curl http://localhost:8000/api/health

# Check Odds API
curl "https://api.the-odds-api.com/v4/sports?apiKey=YOUR_KEY"
```

### Phase 3: Run Full Diagnostics (5 minutes)

```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend
source .venv/bin/activate
python diagnostic_reporter.py --league nba --output diagnostic_report_full.json

# View report
cat diagnostic_report_full.json | jq '.'
```

---

## FAILURE MODE ANALYSIS

Based on code review of [backend/routes/decisions.py](backend/routes/decisions.py), the "Failed to Load Decision" error occurs when:

### Failure Path 1: Missing Event
```python
event = db["events"].find_one({"$or": [{"id": game_id}, {"event_id": game_id}]})
if not event:
    raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    # Frontend catches this → displays "Failed to load decision"
```

### Failure Path 2: No Odds Available
```python
bookmakers = event.get("bookmakers", [])
if not bookmakers:
    raise HTTPException(status_code=404, detail=f"No odds available for {game_id}")
    # Frontend catches this → displays "Failed to load decision"
```

### Failure Path 3: Decision Processing Failed
```python
# MarketDecisionComputer processes odds → returns decision
# If missing spreads/totals → returns BLOCKED decision (HTTP 200, not error)
# If exception → HTTP 500 error → "Failed to load decision"
```

---

## DATA PROVIDER CONFIGURATION ISSUES

### Issue Found: MLB API Request Format

**Current Request (FAILING):**
```python
GET /v4/sports/baseball_mlb/odds?apiKey=KEY&markets=h2h,spreads,totals&oddsFormat=decimal
```

**Error Receipt:** 422 - Missing regions or bookmakers key

**Corrected Request (SHOULD WORK):**
```python
GET /v4/sports/baseball_mlb/odds?apiKey=KEY&regions=us&markets=spreads,totals&oddsFormat=decimal
```

**Fix Location:** [backend/services/scheduler.py](backend/services/scheduler.py#L23)

**Code to Update:**
```python
# Current (line 23):
params = {
    "apiKey": api_key,
    "regions": "us",
    "markets": markets,
    "oddsFormat": "decimal"
}

# Already correct! The issue is elsewhere.
# Might be happening in odd_api.py normalization.
```

---

## NEXT STEPS

### For Immediate Diagnostics:
1. Start MongoDB and backend
2. Identify one game showing "Failed to load decision" in production
3. Run: `python diagnostic_reporter.py --league nba --game-id <game_id>`
4. Compare output against API response structure

### For Root Cause Fix:
Once diagnostics complete, the exact failure point will be one of:
- **A)** Event not in database (odds polling failure)
- **B)** Event missing bookmakers/markets (incomplete odds ingestion)
- **C)** Decision computation exception (logic error in MarketDecisionComputer)
- **D)** Network error during API call (transient failure)

---

## FILES FOR REFERENCE

| File | Purpose |
|------|---------|
| [backend/routes/decisions.py](backend/routes/decisions.py) | Main decisions endpoint |
| [backend/services/scheduler.py](backend/services/scheduler.py) | Odds polling pipeline |
| [backend/db/decision_record_store.py](backend/db/decision_record_store.py) | Decision storage |
| [backend/core/market_decision.py](backend/core/market_decision.py) | Decision data structures |
| [backend/integrations/odds_api.py](backend/integrations/odds_api.py) | Odds API integration |
| [backend/.env](backend/.env) | Configuration (API keys, DB URI) |

---

## DIAGNOSTIC SCRIPT LOCATION

```
/Users/rohithaditya/Downloads/Permutation-Carlos/backend/diagnostic_reporter.py
```

**Usage:**
```bash
# Basic run
python diagnostic_reporter.py

# With specific league
python diagnostic_reporter.py --league mlb

# With specific game
python diagnostic_reporter.py --league nba --game-id game123

# Custom output
python diagnostic_reporter.py --output my_report.json
```

---

**Report Status:** Awaiting infrastructure online  
**Next Action:** Start MongoDB and Backend API, then re-run diagnostics

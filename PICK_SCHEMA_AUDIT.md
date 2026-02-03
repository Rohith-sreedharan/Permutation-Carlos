# BeatVegas Pick Schema & Grading Architecture

**Generated:** February 2, 2026  
**Purpose:** Document current OddsAPI event mapping, pick storage, and grading sources

---

## 📊 CURRENT PICK SCHEMA (ai_picks collection)

### Primary Schema (`ai_picks` collection)

```python
{
    # Identifiers
    "pick_id": "pick_abc123def456",              # Unique pick identifier
    "event_id": "evt_nba_lakers_celtics",        # Sports event identifier
    
    # Market Details
    "market": "spreads",                          # h2h (moneyline), spreads, totals, props
    "side": "Los Angeles Lakers",                # Team name, over/under, player prop
    
    # Odds & Edge
    "market_decimal": 1.91,                       # Best available market odds (decimal)
    "model_fair_decimal": 2.10,                   # AI model's fair value odds
    "edge_pct": 9.95,                            # Expected edge: (model_fair - market) / market * 100
    
    # Stake Sizing (Kelly Criterion)
    "stake_units": 2.5,                          # Recommended stake (1 unit = 1% bankroll)
    "kelly_fraction": 0.25,                      # Kelly fraction (0.25 = quarter Kelly)
    
    # Model Transparency
    "rationale": [
        "Lakers have 65% win probability based on Elo ratings",
        "Sharp money (70% of handle) on Lakers -5.5",
        "Community consensus: +0.7 sentiment (Elite members weighted 2x)"
    ],
    "model_version": "omniedge_v2.3.1",          # Model version identifier
    "confidence": 0.73,                          # Model confidence (0-1)
    
    # Hybrid Features (Community + AI)
    "sharp_weighted_consensus": 0.7,             # Weighted expert sentiment (-1 to +1)
    "community_volume": 47,                      # Number of community picks
    
    # CLV Tracking (Module 7 Input)
    "closing_line_decimal": None,                # ⚠️ Populated post-match
    "clv_pct": None,                            # Closing Line Value %
    
    # Outcome Tracking
    "outcome": None,                             # win, loss, push, void
    "roi": None,                                # ROI: (profit / stake) * 100
    
    # Timestamps
    "created_at": "2025-11-10T18:00:00.000Z",
    "settled_at": None                           # ⚠️ Populated when graded
}
```

**Indexes:**
```python
db["ai_picks"].create_index("pick_id", unique=True)
db["ai_picks"].create_index([("event_id", 1)])
db["ai_picks"].create_index([("created_at", -1)])
db["ai_picks"].create_index([("outcome", 1)])      # For ROI analysis
db["ai_picks"].create_index([("clv_pct", 1)])      # For CLV tracking
db["ai_picks"].create_index([("settled_at", -1)])  # For performance reports
```

---

## 🎯 ODDSAPI EVENT MAPPING

### Event Storage (`events` collection)

```python
{
    # OddsAPI Event Fields (from normalize_event)
    "event_id": "nba_warriors_lakers_20260202",  # ⚠️ YOUR canonical ID, NOT OddsAPI's
    "sport_key": "basketball_nba",               # OddsAPI sport key
    "sport_title": "NBA",
    "home_team": "Golden State Warriors",        # OddsAPI team name
    "away_team": "Los Angeles Lakers",           # OddsAPI team name
    "commence_time": "2026-02-02T20:00:00Z",     # ISO 8601 start time
    
    # OddsAPI Bookmaker Data (raw)
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "last_update": "2026-02-02T18:30:00Z",
            "markets": [
                {
                    "key": "spreads",
                    "name": "Point Spread",
                    "outcomes": [
                        {"name": "Warriors", "price": -110, "point": -5.5},
                        {"name": "Lakers", "price": -110, "point": 5.5}
                    ]
                }
            ]
        }
    ],
    
    # Metadata
    "created_at": "2026-02-02T06:00:00Z",
    "raw_markets": [...],                        # Full OddsAPI payload
    
    # ⚠️ CRITICAL MISSING FIELDS
    # NO OddsAPI event ID stored
    # NO OddsAPI selection IDs stored
    # NO mapping between your event_id and OddsAPI's ID
}
```

**Current Team Mapping:**
- **Team Validator:** `backend/utils/team_validator.py`
  - Maps team names → team keys (e.g., "Golden State Warriors" → "GSW")
  - Added: WCU (Western Carolina), MD (Maryland), PUR (Purdue), FAIR (Fairfield)
  - **⚠️ NO OddsAPI team ID mapping**

---

## 📈 GRADING ARCHITECTURE

### Current Grading Sources (Multiple Systems)

#### 1️⃣ **Legacy System** (`ai_picks.outcome` field)

**Location:** `backend/core/omni_edge_ai.py`

```python
def update_pick_outcome(self, pick_id: str, outcome: str, closing_odds: Optional[float] = None):
    """
    Update pick outcome with CLV tracking
    
    Args:
        pick_id: Pick identifier
        outcome: "win", "loss", "push", "void"
        closing_odds: Closing line odds (decimal)
    """
    # Calculate CLV
    pick = db["ai_picks"].find_one({"pick_id": pick_id})
    opening_odds = pick.get("market_decimal")
    clv_pct = None
    
    if closing_odds and opening_odds:
        clv_pct = ((closing_odds - opening_odds) / opening_odds) * 100
    
    # Calculate ROI
    roi = None
    if outcome == "win":
        roi = (opening_odds - 1) * 100
    elif outcome == "loss":
        roi = -100
    elif outcome == "push":
        roi = 0
    
    # Update pick
    db["ai_picks"].update_one(
        {"pick_id": pick_id},
        {
            "$set": {
                "outcome": outcome,
                "closing_line_decimal": closing_odds,
                "clv_pct": round(clv_pct, 2) if clv_pct else None,
                "roi": round(roi, 2) if roi else None,
                "settled_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
```

**⚠️ Issues:**
- Manual grading (no OddsAPI scores integration)
- No event result verification
- No settlement rules (spread push logic, etc.)

---

#### 2️⃣ **Calibration System** (`grading` collection)

**Location:** `backend/db/schemas/logging_calibration_schemas.py`

```python
class Grading(BaseModel):
    """
    Settlement + scoring metrics (Trust Loop v1)
    Purpose: grade publishes, not raw predictions
    Only graded for is_official=true publishes
    """
    graded_id: str                               # UUID
    publish_id: str                              # FK to published_predictions
    prediction_id: str                           # FK to predictions
    event_id: str
    
    # Settlement (Trust Loop v1: SETTLED/VOID/NO_ACTION)
    bet_status: BetStatus                        # PENDING, SETTLED, VOID, NO_ACTION
    result_code: Optional[ResultCode]            # WIN, LOSS, PUSH, VOID
    units_returned: Optional[float]              # Assume 1 unit at locked_price_at_publish
    
    # CLV (Trust Loop v1: deterministic close snapshot + clv_points)
    close_snapshot_id: Optional[str]             # FK to odds_snapshots (last before start_time_utc)
    clv_points: Optional[float]                  # Spread/total CLV in points
    clv_pct: Optional[float]                     # ML CLV in %
    
    # Timestamps
    graded_at: datetime
```

**Indexes:**
```python
db.grading.create_index("graded_id", unique=True)
db.grading.create_index([("publish_id", 1)])
db.grading.create_index([("prediction_id", 1)])
db.grading.create_index([("event_id", 1)])
db.grading.create_index([("bet_status", 1)])
db.grading.create_index([("result_code", 1)])
db.grading.create_index([("graded_at", -1)])
```

**⚠️ Issues:**
- Only grades published_predictions (not all ai_picks)
- Requires separate publishing workflow
- Complex lineage (sim_runs → predictions → published_predictions → grading)

---

#### 3️⃣ **Result Service** (OddsAPI Scores)

**Location:** `backend/services/result_service.py`

```python
async def fetch_final_score(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch final score from OddsAPI scores endpoint.
    
    OddsAPI Endpoint:
    GET https://api.the-odds-api.com/v4/sports/{sport}/scores
    
    Response:
    {
        "id": "abc123...",                       # ⚠️ OddsAPI event ID
        "sport_key": "basketball_nba",
        "commence_time": "2026-02-02T20:00:00Z",
        "home_team": "Golden State Warriors",
        "away_team": "Los Angeles Lakers",
        "scores": [
            {"name": "Warriors", "score": "112"},
            {"name": "Lakers", "score": "105"}
        ],
        "completed": true,
        "last_update": "2026-02-02T23:00:00Z"
    }
    """
    # ⚠️ PROBLEM: We don't store OddsAPI's event ID
    # Currently fetches all scores and matches by team names + commence_time
```

**⚠️ Issues:**
- No OddsAPI event ID stored in `events` collection
- Matches scores by fuzzy team name matching (brittle)
- No guaranteed 1:1 mapping between your event_id and OddsAPI scores

---

#### 4️⃣ **Post-Game Grader**

**Location:** `backend/services/post_game_grader.py`

```python
class PostGameGrader:
    """
    Automated post-game grading system
    
    Pipeline:
    1. Fetch completed games (OddsAPI scores)
    2. Find published predictions for those events
    3. Determine bet result (win/loss/push/void)
    4. Store grading record for weekly calibration
    """
    
    async def grade_event(self, event_id: str) -> Optional[Dict]:
        # 1. Fetch final score from OddsAPI
        score_data = await fetch_final_score(event_id)
        
        # 2. Find published prediction
        published = db.published_predictions.find_one({"event_id": event_id})
        
        # 3. Calculate result
        result_code = self._determine_result(published, score_data)
        
        # 4. Calculate CLV
        close_snapshot = self._get_closing_snapshot(event_id)
        clv = self._calculate_clv(published, close_snapshot)
        
        # 5. Store grading record
        grading_record = {
            "graded_id": generate_uuid(),
            "publish_id": published["publish_id"],
            "event_id": event_id,
            "bet_status": "SETTLED",
            "result_code": result_code,
            "clv_points": clv,
            "graded_at": datetime.utcnow()
        }
        
        db.grading.insert_one(grading_record)
        return grading_record
```

**⚠️ Issues:**
- Only grades published_predictions (subset of all picks)
- Requires closing line snapshots (may not exist)
- No direct OddsAPI event ID linkage

---

## 🚨 CRITICAL GAPS IDENTIFIED

### 1. **OddsAPI Event ID Mapping**

**Current State:**
```python
# events collection
{
    "event_id": "nba_warriors_lakers_20260202",  # YOUR ID
    "home_team": "Golden State Warriors",
    "away_team": "Los Angeles Lakers",
    # ⚠️ NO oddsapi_event_id field
}
```

**Required State:**
```python
# events collection (FIXED)
{
    "event_id": "nba_warriors_lakers_20260202",  # YOUR canonical ID
    "oddsapi_event_id": "abc123def456...",       # ✅ OddsAPI's ID
    "home_team": "Golden State Warriors",
    "away_team": "Los Angeles Lakers",
    
    # Optional: Store full OddsAPI ID mapping
    "provider_mappings": {
        "oddsapi": {
            "event_id": "abc123def456...",
            "home_team_id": "oddsapi_team_gsw",
            "away_team_id": "oddsapi_team_lal"
        }
    }
}
```

---

### 2. **Pick → Event → OddsAPI Linkage**

**Current Flow (BROKEN):**
```
ai_picks.event_id → events.event_id → ❌ NO OddsAPI ID → ❌ Can't fetch scores
```

**Required Flow (FIXED):**
```
ai_picks.event_id → events.event_id → events.oddsapi_event_id → ✅ OddsAPI scores API
```

---

### 3. **Grading Source Unification**

**Current State:** 3+ separate grading systems
1. `ai_picks.outcome` (manual updates)
2. `grading` collection (published_predictions only)
3. `result_service` (OddsAPI scores, no persistence)
4. `post_game_grader` (published_predictions only)

**Recommended State:** Single grading pipeline
```python
# Unified Grading Service
class UnifiedGradingService:
    """
    Single source of truth for all pick grading
    
    Sources:
    1. OddsAPI scores (primary - game results)
    2. Canonical contract (pick details from simulation)
    3. Closing line snapshots (CLV calculation)
    """
    
    async def grade_pick(self, pick_id: str) -> GradingResult:
        # 1. Get pick
        pick = db.ai_picks.find_one({"pick_id": pick_id})
        
        # 2. Get event (with OddsAPI mapping)
        event = db.events.find_one({"event_id": pick["event_id"]})
        oddsapi_event_id = event["oddsapi_event_id"]  # ✅ NOW EXISTS
        
        # 3. Fetch OddsAPI scores (guaranteed 1:1 mapping)
        scores = await fetch_scores_by_oddsapi_id(oddsapi_event_id)
        
        # 4. Determine result (using canonical spread/total logic)
        result = determine_result(
            pick=pick,
            scores=scores,
            use_canonical_contract=True  # ✅ Use canonical contract enforcement
        )
        
        # 5. Calculate CLV
        closing_snapshot = get_closing_snapshot(oddsapi_event_id)
        clv = calculate_clv(pick, closing_snapshot)
        
        # 6. Update pick
        db.ai_picks.update_one(
            {"pick_id": pick_id},
            {
                "$set": {
                    "outcome": result.outcome,
                    "result_code": result.code,
                    "closing_line_decimal": closing_snapshot.price_decimal,
                    "clv_pct": clv,
                    "roi": result.roi,
                    "settled_at": datetime.utcnow(),
                    "grading_source": "oddsapi_scores",
                    "oddsapi_event_id": oddsapi_event_id  # ✅ Audit trail
                }
            }
        )
        
        return result
```

---

## 📋 REQUIRED FIXES

### Fix 1: Add OddsAPI Event ID to Events Collection

**File:** `backend/integrations/odds_api.py` (normalize_event function)

```python
def normalize_event(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize OddsAPI event to internal format
    
    ⚠️ MUST STORE ODDSAPI EVENT ID
    """
    # Extract OddsAPI event ID
    oddsapi_event_id = raw_event.get("id")  # ✅ OddsAPI's unique ID
    
    # Generate your canonical event_id
    event_id = generate_canonical_event_id(
        sport=raw_event["sport_key"],
        home=raw_event["home_team"],
        away=raw_event["away_team"],
        commence_time=raw_event["commence_time"]
    )
    
    return {
        "event_id": event_id,                    # YOUR canonical ID
        "oddsapi_event_id": oddsapi_event_id,    # ✅ ADD THIS
        "sport_key": raw_event["sport_key"],
        "sport_title": raw_event["sport_title"],
        "home_team": raw_event["home_team"],
        "away_team": raw_event["away_team"],
        "commence_time": raw_event["commence_time"],
        "bookmakers": raw_event.get("bookmakers", []),
        "created_at": datetime.utcnow().isoformat(),
        
        # Optional: Full provider mapping
        "provider_mappings": {
            "oddsapi": {
                "event_id": oddsapi_event_id,
                "raw_payload": raw_event  # Store full payload for debugging
            }
        }
    }
```

---

### Fix 2: Update Result Service to Use OddsAPI Event ID

**File:** `backend/services/result_service.py`

```python
async def fetch_final_score_by_event_id(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch final score using guaranteed OddsAPI event ID mapping
    
    ✅ NOW WORKS: event_id → oddsapi_event_id → scores
    """
    # 1. Get event with OddsAPI mapping
    event = db.events.find_one({"event_id": event_id})
    if not event:
        return None
    
    oddsapi_event_id = event.get("oddsapi_event_id")
    if not oddsapi_event_id:
        logger.error(f"No OddsAPI event ID for {event_id}")
        return None
    
    # 2. Fetch scores by OddsAPI event ID (guaranteed 1:1 match)
    sport_key = event["sport_key"]
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores"
    params = {
        "apiKey": ODDSAPI_KEY,
        "daysFrom": 1
    }
    
    response = requests.get(url, params=params)
    scores = response.json()
    
    # 3. Find exact match by OddsAPI event ID
    for score in scores:
        if score.get("id") == oddsapi_event_id:  # ✅ Exact match
            return score
    
    return None
```

---

### Fix 3: Add OddsAPI Event ID Index

**File:** `backend/db/mongo.py`

```python
def ensure_indexes():
    # Events indexes
    db["events"].create_index("event_id", unique=True)
    db["events"].create_index("oddsapi_event_id")  # ✅ ADD THIS
    db["events"].create_index([("sport_key", 1), ("commence_time", 1)])
```

---

## 🎯 MIGRATION PLAN

### Phase 1: Backfill OddsAPI Event IDs (1-2 hours)

```python
# scripts/backfill_oddsapi_ids.py
async def backfill_oddsapi_event_ids():
    """
    Backfill oddsapi_event_id for existing events
    
    Strategy:
    1. Fetch all events from events collection
    2. For each event, fetch OddsAPI events by sport + date range
    3. Match by team names + commence_time
    4. Update event with oddsapi_event_id
    """
    events = db.events.find({})
    
    for event in events:
        # Skip if already has OddsAPI ID
        if event.get("oddsapi_event_id"):
            continue
        
        # Fetch OddsAPI events for sport + date
        sport_key = event["sport_key"]
        commence_time = parse(event["commence_time"])
        
        oddsapi_events = await fetch_oddsapi_events(
            sport=sport_key,
            date=commence_time.date()
        )
        
        # Match by team names + commence_time
        for oddsapi_event in oddsapi_events:
            if (oddsapi_event["home_team"] == event["home_team"] and
                oddsapi_event["away_team"] == event["away_team"] and
                abs((parse(oddsapi_event["commence_time"]) - commence_time).seconds) < 300):
                
                # Update event with OddsAPI ID
                db.events.update_one(
                    {"event_id": event["event_id"]},
                    {
                        "$set": {
                            "oddsapi_event_id": oddsapi_event["id"],
                            "provider_mappings": {
                                "oddsapi": {
                                    "event_id": oddsapi_event["id"],
                                    "raw_payload": oddsapi_event
                                }
                            }
                        }
                    }
                )
                break
```

---

### Phase 2: Update normalize_event Function (15 minutes)

Add `oddsapi_event_id` extraction as shown in Fix 1.

---

### Phase 3: Update Result Service (30 minutes)

Modify `fetch_final_score` to use `oddsapi_event_id` as shown in Fix 2.

---

### Phase 4: Create Unified Grading Service (2-3 hours)

Consolidate all grading logic into single service using OddsAPI scores + canonical contract.

---

## 📊 SUMMARY

**Current State:**
- ❌ No OddsAPI event ID stored
- ❌ Brittle team name matching for scores
- ❌ Multiple competing grading systems
- ❌ No guaranteed 1:1 event mapping

**Required State:**
- ✅ OddsAPI event ID stored in events collection
- ✅ Direct event_id → oddsapi_event_id → scores lookup
- ✅ Single unified grading service
- ✅ Guaranteed 1:1 event mapping with audit trail

**Estimated Implementation Time:** 4-6 hours

---

*Generated by BeatVegas Architecture Audit System*

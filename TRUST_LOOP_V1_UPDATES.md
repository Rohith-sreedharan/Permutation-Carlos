# Trust Loop v1 Updates - Implementation Status

## ✅ COMPLETED Changes

### 1. Database Schemas Updated (`backend/db/schemas/logging_calibration_schemas.py`)

**New Enums Added:**
```python
class RecommendationState(str, Enum):
    OFFICIAL_EDGE = "OFFICIAL_EDGE"  # Only this can be published as official
    MODEL_LEAN = "MODEL_LEAN"
    WAIT_LIVE = "WAIT_LIVE"
    NO_PLAY = "NO_PLAY"

class PublishType(str, Enum):
    OFFICIAL_EDGE = "OFFICIAL_EDGE"  # Counts in official record
    INFORMATIONAL = "INFORMATIONAL"  # Lean/wait/no-play content
```

**Updated `Prediction` Model:**
- Added `p_raw: Optional[float]` - 0-1 probability before calibration
- Added `p_calibrated: Optional[float]` - 0-1 probability after calibration
- Updated `recommendation_state` to include Trust Loop v1 values

**Updated `PublishedPrediction` Model (MAJOR CHANGES):**
```python
class PublishedPrediction(BaseModel):
    # Trust Loop v1 core fields
    publish_type: PublishType  # OFFICIAL_EDGE or INFORMATIONAL
    is_official: bool  # True only for OFFICIAL_EDGE publishes
    
    # LOCKED SNAPSHOT FIELDS (immutable)
    locked_market_snapshot_id: str
    locked_injury_snapshot_ids: List[str]
    locked_line_at_publish: Optional[float]
    locked_price_at_publish: Optional[int]  # American odds
    
    # LOCKED MODEL FIELDS (immutable)
    locked_engine_version: str
    locked_model_version: str
    locked_calibration_version: Optional[str]
    locked_decision_policy_version: str
    
    # LOCKED PREDICTION FIELDS (immutable)
    locked_p_calibrated: Optional[float]
    locked_edge_points: Optional[float]
    locked_variance_bucket: Optional[str]
    locked_market_key: str
    locked_selection: str
```

**Updated `Grading` Model:**
```python
class Grading(BaseModel):
    # Trust Loop v1: SETTLED/VOID/NO_ACTION
    bet_status: BetStatus
    units_returned: Optional[float]  # Assume 1 unit at locked_price_at_publish
    
    # Trust Loop v1: deterministic close snapshot
    close_snapshot_id: Optional[str]  # Last snapshot before start_time_utc
    clv_points: Optional[float]  # Sign-corrected line difference
    
    # Trust Loop v1: brier_component
    brier_component: Optional[float]  # (locked_p_calibrated - y)^2
```

**New Table: `UserPickTrack`** (Follow/Track functionality):
```python
class UserPickTrack(BaseModel):
    user_pick_track_id: str
    user_id: str
    publish_id: str  # FK to published_predictions
    tracked_at_utc: datetime
    status: Literal["ACTIVE", "REMOVED"]
```

**Indexes Updated:**
- Added `user_pick_tracks` collection with proper indexes
- Updated `published_predictions` indexes to include `(is_official, publish_type)`

---

## 🔧 SERVICES THAT NEED UPDATES

### 1. `publishing_service.py` - Partially Updated

**What Needs to Change:**
```python
def publish_prediction(
    prediction_id: str,
    channel: str,
    publish_type: str = "OFFICIAL_EDGE",  # NEW
    is_official: bool = True,
    # ... other params
) -> str:
    """
    Must populate ALL locked_* fields from:
    - prediction record (p_calibrated, edge_points, variance_bucket)
    - market snapshot (line, price)
    - sim_run (engine_version, model_version, calibration_version, policy_version)
    """
    
    # Trust Loop v1: Only OFFICIAL_EDGE can be is_official=true
    if is_official and publish_type != "OFFICIAL_EDGE":
        raise ValueError("Only OFFICIAL_EDGE can be is_official=true")
    
    # Capture all locked_* fields at publish time
    published = PublishedPrediction(
        # ... populate all locked_* fields
        locked_market_snapshot_id=prediction["market_snapshot_id_used"],
        locked_line_at_publish=market_snapshot["line"],
        locked_price_at_publish=market_snapshot["price_american"],
        locked_engine_version=sim_run["engine_version"],
        locked_model_version=sim_run["model_version"],
        locked_p_calibrated=prediction["p_calibrated"],
        # ... etc
    )
```

### 2. `grading_service.py` - Needs Updates

**What Needs to Change:**
```python
def grade_published_prediction(publish_id: str) -> str:
    """
    Trust Loop v1: Must use locked_* fields from published_predictions
    """
    # Get published prediction
    published = get_published_prediction(publish_id)
    
    # Only grade if is_official=true and publish_type=OFFICIAL_EDGE
    if not published.get("is_official") or published.get("publish_type") != "OFFICIAL_EDGE":
        logger.warning(f"Skipping grade for non-official publish {publish_id}")
        return None
    
    # Deterministically select close snapshot
    close_snapshot = find_close_snapshot(
        event_id=published["event_id"],
        market_key=published["locked_market_key"],
        book=published.get("locked_book", "consensus")
    )
    
    # Calculate CLV using locked fields
    clv_points = calculate_clv(
        published_line=published["locked_line_at_publish"],
        close_line=close_snapshot["line"],
        selection=published["locked_selection"]
    )
    
    # Calculate brier_component using locked_p_calibrated
    y = 1 if result_code == "WIN" else 0
    brier_component = (published["locked_p_calibrated"] - y) ** 2
    
    grading = Grading(
        graded_id=str(uuid4()),
        publish_id=publish_id,
        close_snapshot_id=close_snapshot["snapshot_id"],
        clv_points=clv_points,
        units_returned=calculate_units(published["locked_price_at_publish"], result_code),
        brier_component=brier_component,
        # ...
    )
```

**New Function Needed:**
```python
def find_close_snapshot(event_id: str, market_key: str, book: str) -> Dict:
    """
    Trust Loop v1: Deterministic close selection
    Returns last odds_snapshot before events.start_time_utc
    """
    event = db.events.find_one({"event_id": event_id})
    
    close_snapshot = db.odds_snapshots.find_one(
        {
            "event_id": event_id,
            "market_key": market_key,
            "book": book,
            "timestamp_utc": {"$lt": event["start_time_utc"]}
        },
        sort=[("timestamp_utc", -1)]
    )
    
    return close_snapshot
```

### 3. `sim_run_tracker.py` - Needs Minor Updates

**What Needs to Change:**
```python
def create_prediction(
    sim_run_id: str,
    # ... existing params
    p_raw: Optional[float] = None,  # NEW
    p_calibrated: Optional[float] = None,  # NEW
    recommendation_state: str = "OFFICIAL_EDGE",  # NEW (Trust Loop values)
) -> str:
    """
    Must accept and store p_raw, p_calibrated, recommendation_state
    """
    prediction = Prediction(
        prediction_id=str(uuid4()),
        # ... existing fields
        p_raw=p_raw,
        p_calibrated=p_calibrated,
        recommendation_state=recommendation_state,
        # ...
    )
```

---

## 📊 NEW API ENDPOINTS NEEDED

### Trust Loop Routes (`backend/routes/trust_loop_routes.py` - CREATE NEW FILE)

```python
from fastapi import APIRouter, Depends, Query
from typing import Optional

router = APIRouter(prefix="/api/trust-loop", tags=["Trust Loop v1"])

# ============================================================================
# VIEW A: OFFICIAL MODEL RECORD
# ============================================================================

@router.get("/official-record/summary")
async def get_official_record_summary(
    league: Optional[str] = None,
    market_key: Optional[str] = None,
):
    """
    Trust Loop v1: Official Model Record KPIs
    
    Cohort: published_predictions.is_official=true AND publish_type=OFFICIAL_EDGE
    Joined to grading where bet_status=SETTLED
    
    Returns:
        {
            "net_units": float,
            "roi_percent": float,
            "win_rate": float,
            "avg_clv": float,
            "pct_positive_clv": float,
            "brier_score": float,  # 0-1 range
            "sample_size": {
                "settled": int,
                "published": int,
                "pending": int,
                "void": int
            }
        }
    """
    # Query: is_official=true AND publish_type=OFFICIAL_EDGE
    query = {
        "is_official": True,
        "publish_type": "OFFICIAL_EDGE"
    }
    if league:
        query["league"] = league
    if market_key:
        query["locked_market_key"] = market_key
    
    # Join to grading
    pipeline = [
        {"$match": query},
        {"$lookup": {
            "from": "grading",
            "localField": "publish_id",
            "foreignField": "publish_id",
            "as": "grading"
        }},
        {"$unwind": {"path": "$grading", "preserveNullAndEmptyArrays": True}},
        # ... aggregation logic
    ]
    
    # Calculate KPIs
    # net_units = SUM(units_returned)
    # roi_percent = SUM(units_returned) / COUNT(settled) * 100
    # win_rate = WIN / (WIN + LOSS) excluding PUSH/VOID
    # avg_clv = AVG(clv_points) where available
    # brier_score = AVG(brier_component) MUST be 0-1

@router.get("/official-record/breakdowns")
async def get_official_record_breakdowns():
    """
    Trust Loop v1: Breakdowns by league, market, edge bucket, variance bucket
    """
    pass

@router.get("/official-record/recent-picks")
async def get_recent_official_picks(
    limit: int = Query(default=50, le=200)
):
    """
    Trust Loop v1: Recent official picks audit table
    
    Include: event, market/pick, locked fields, result, units, clv
    Provide 'View lineage' capability
    """
    pass

@router.get("/official-record/lineage/{publish_id}")
async def get_publish_lineage(publish_id: str):
    """
    Trust Loop v1: Show all locked snapshot ids + versions
    
    Returns all immutable fields for audit
    """
    pass

# ============================================================================
# VIEW B: MY TRACKED PICKS (Follow/Track)
# ============================================================================

@router.post("/track/{publish_id}")
async def track_pick(
    publish_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Trust Loop v1: Follow/Track a pick
    
    Creates user_pick_tracks record
    Label: 'Tracked pick (not a verified bet)'
    """
    # Check if already tracked
    existing = db.user_pick_tracks.find_one({
        "user_id": user_id,
        "publish_id": publish_id,
        "status": "ACTIVE"
    })
    
    if existing:
        return {"track_id": existing["user_pick_track_id"]}
    
    track = UserPickTrack(
        user_pick_track_id=str(uuid4()),
        user_id=user_id,
        publish_id=publish_id,
        tracked_at_utc=datetime.now(timezone.utc),
        status="ACTIVE"
    )
    
    db.user_pick_tracks.insert_one(track.model_dump())
    
    return {"track_id": track.user_pick_track_id}

@router.delete("/track/{publish_id}")
async def untrack_pick(
    publish_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Trust Loop v1: Untrack a pick
    """
    db.user_pick_tracks.update_one(
        {
            "user_id": user_id,
            "publish_id": publish_id
        },
        {"$set": {"status": "REMOVED"}}
    )
    
    return {"success": True}

@router.get("/tracked-picks")
async def get_tracked_picks(
    user_id: str = Depends(get_current_user_id),
    status: str = Query(default="ACTIVE")
):
    """
    Trust Loop v1: My Tracked Picks
    
    Cohort: user_pick_tracks.user_id=current_user AND status=ACTIVE
    Joined to published_predictions + grading
    
    Label: 'If played at published odds' for hypothetical units
    """
    pipeline = [
        {
            "$match": {
                "user_id": user_id,
                "status": status
            }
        },
        {
            "$lookup": {
                "from": "published_predictions",
                "localField": "publish_id",
                "foreignField": "publish_id",
                "as": "published"
            }
        },
        {"$unwind": "$published"},
        {
            "$lookup": {
                "from": "grading",
                "localField": "publish_id",
                "foreignField": "publish_id",
                "as": "grading"
            }
        },
        # ... rest of aggregation
    ]
    
    return {
        "tracked_picks": [],
        "hypothetical_units": 0.0,  # Label: "If played at published odds"
        "pending": 0
    }
```

---

## 🎯 ACCEPTANCE TESTS (Trust Loop v1)

### Test 1: OFFICIAL_EDGE Publish
```python
def test_official_edge_publish():
    # Publish OFFICIAL_EDGE
    publish_id = publishing_service.publish_prediction(
        prediction_id=pred_id,
        channel="TELEGRAM",
        publish_type="OFFICIAL_EDGE",
        is_official=True
    )
    
    # Verify appears in Official Model Record as pending
    official_picks = db.published_predictions.find({
        "is_official": True,
        "publish_type": "OFFICIAL_EDGE"
    })
    
    assert publish_id in [p["publish_id"] for p in official_picks]
```

### Test 2: INFORMATIONAL Publish
```python
def test_informational_publish():
    # Publish INFORMATIONAL (lean/wait/no-play)
    publish_id = publishing_service.publish_prediction(
        prediction_id=pred_id,
        channel="TELEGRAM",
        publish_type="INFORMATIONAL",
        is_official=False
    )
    
    # Verify NEVER appears in Official Model Record
    official_picks = db.published_predictions.find({
        "is_official": True,
        "publish_type": "OFFICIAL_EDGE"
    })
    
    assert publish_id not in [p["publish_id"] for p in official_picks]
```

### Test 3: Rerun Does Not Modify Prior Publish
```python
def test_rerun_no_modification():
    # Publish OFFICIAL_EDGE
    publish_id_1 = publish_official_edge(pred_id_1)
    
    # Rerun same game, state flips to lean
    pred_id_2 = rerun_simulation(event_id)  # recommendation_state=MODEL_LEAN
    
    # Prior OFFICIAL publish remains unchanged
    published_1 = db.published_predictions.find_one({"publish_id": publish_id_1})
    assert published_1["publish_type"] == "OFFICIAL_EDGE"
    assert published_1["is_official"] == True
    
    # New prediction cannot be published as OFFICIAL_EDGE
    with pytest.raises(ValueError):
        publish_prediction(pred_id_2, publish_type="OFFICIAL_EDGE", is_official=True)
```

### Test 4: Follow/Track
```python
def test_follow_track():
    # Follow an OFFICIAL pick
    track_id = track_pick(user_id="user123", publish_id=publish_id)
    
    # Appears in My Tracked Picks with label 'not a verified bet'
    tracked = get_tracked_picks(user_id="user123")
    assert len(tracked["tracked_picks"]) == 1
    assert tracked["tracked_picks"][0]["label"] == "Tracked pick (not a verified bet)"
    
    # Follow does NOT affect Official KPIs
    official_summary = get_official_record_summary()
    # user_pick_tracks has no join path into official cohort
```

### Test 5: Brier Score 0-1
```python
def test_brier_score_range():
    # Grade predictions
    grade_all_pending()
    
    # Get official record
    summary = get_official_record_summary()
    
    # Brier score MUST be 0-1
    assert 0 <= summary["brier_score"] <= 1
    assert summary["brier_score"] == avg(brier_component for all settled)
```

### Test 6: CLV Stability
```python
def test_clv_stability():
    # Grade prediction
    graded_id = grade_published_prediction(publish_id)
    
    # CLV derived from stored close_snapshot_id
    grading_1 = db.grading.find_one({"graded_id": graded_id})
    
    # Re-grade should produce same CLV
    graded_id_2 = grade_published_prediction(publish_id)
    grading_2 = db.grading.find_one({"graded_id": graded_id_2})
    
    assert grading_1["clv_points"] == grading_2["clv_points"]
    assert grading_1["close_snapshot_id"] == grading_2["close_snapshot_id"]
```

### Test 7: VOID/PUSH Handling
```python
def test_void_push_handling():
    # Create PUSH result
    create_push_result(event_id)
    grade_published_prediction(publish_id)
    
    # Get official record
    summary = get_official_record_summary()
    
    # PUSH excluded from win rate denominator
    assert summary["win_rate"] == WIN / (WIN + LOSS)  # excludes PUSH
    
    # VOID excluded from calibration set
    brier_calcs = get_brier_components()
    assert all(g["result_code"] != "VOID" for g in brier_calcs)
```

---

## 📋 IMPLEMENTATION CHECKLIST

### High Priority (Core Trust Loop)
- [ ] Update `publishing_service.py` to populate all `locked_*` fields
- [ ] Update `grading_service.py` to use `close_snapshot_id` and `clv_points`
- [ ] Add `find_close_snapshot()` function (deterministic close selection)
- [ ] Create `trust_loop_routes.py` with Official Model Record endpoints
- [ ] Create Follow/Track endpoints in `trust_loop_routes.py`
- [ ] Update database initialization script to create `user_pick_tracks` collection
- [ ] Test all 7 acceptance tests

### Medium Priority (Validation & Safety)
- [ ] Add validation: `publish_type=OFFICIAL_EDGE` requires `recommendation_state=OFFICIAL_EDGE`
- [ ] Add validation: `is_official=true` requires `publish_type=OFFICIAL_EDGE`
- [ ] Enforce immutability of `locked_*` fields (no updates allowed)
- [ ] Add logging for all publish/grade operations
- [ ] Create migration script for existing `published_predictions` records

### Low Priority (Nice to Have)
- [ ] Add `View lineage` UI component
- [ ] Create Trust Loop dashboard
- [ ] Add export functionality for official record
- [ ] Add webhook notifications for grading completion
- [ ] Performance optimization for large cohort queries

---

## 🚀 Quick Start for Remaining Work

### 1. Update Publishing Service
```bash
# Edit: backend/services/publishing_service.py
# Follow the example in "SERVICES THAT NEED UPDATES" section above
```

### 2. Update Grading Service
```bash
# Edit: backend/services/grading_service.py
# Add find_close_snapshot() function
# Update grade_published_prediction() to use locked_* fields
```

### 3. Create Trust Loop Routes
```bash
# Create: backend/routes/trust_loop_routes.py
# Copy code from "NEW API ENDPOINTS NEEDED" section above
```

### 4. Integrate into main.py
```python
from routes.trust_loop_routes import router as trust_loop_router
app.include_router(trust_loop_router)
```

### 5. Re-run Database Init
```bash
source .venv/bin/activate
python backend/scripts/init_logging_calibration_db.py
```

### 6. Test
```bash
# Create test script based on acceptance tests
python backend/scripts/test_trust_loop_v1.py
```

---

## ✅ DONE

- [x] Added `RecommendationState` and `PublishType` enums
- [x] Updated `Prediction` model with `p_raw`, `p_calibrated`
- [x] Updated `PublishedPrediction` with all `locked_*` fields
- [x] Updated `Grading` with `close_snapshot_id`, `clv_points`, `brier_component`
- [x] Added `UserPickTrack` model for Follow/Track
- [x] Updated database indexes for Trust Loop queries

---

**Last Updated**: January 19, 2026

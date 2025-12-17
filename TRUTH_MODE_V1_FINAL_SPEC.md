# Truth Mode v1.0 — ZERO-LIES LAUNCH SPEC (FINAL)

## 🔒 CORE PRINCIPLE (LOCKED)

**No pick is allowed to be shown, pushed, or used in a parlay unless it passes:**

1. **Data Integrity Check** (70% threshold)
2. **Model Validity Check** (≥48% confidence, ≥10k iterations, ≥85% convergence)
3. **RCL Gate** (Reasoning Chain Loop - Publish/Block decision)

**If blocked → UI must show NO PLAY + reason codes**

## ✅ ENFORCEMENT SCOPE

Truth Mode applies to **ALL sports** and **ALL pick surfaces**:

### ✅ Dashboard Pick Cards
- **File**: `backend/routes/daily_cards_routes.py`
- **Function**: `_apply_truth_mode_to_cards()`
- **Coverage**: All 6 daily cards (Best Game, NBA, NCAAB, NCAAF, Props, Parlay)
- **Behavior**: Blocked picks → NO_PLAY card with reason codes

### ✅ Sharp Side Detection
- **File**: `backend/routes/simulation_routes.py`
- **Function**: `_apply_truth_mode_to_simulation()`
- **Coverage**: Spread analysis `sharp_side`, Total analysis `sharp_side`
- **Behavior**: Blocked → `sharp_side = null`, `has_edge = false`

### ✅ Parlay Builder Auto-Fill
- **File**: `backend/services/parlay_architect.py`
- **Integration**: Lines 185-210
- **Coverage**: All parlay legs validated before inclusion
- **Behavior**: Minimum 2 valid legs required, blocks entire parlay if insufficient

### ✅ Community Picks
- **File**: `backend/routes/community_routes.py`
- **Endpoint**: `GET /api/community/picks`
- **Coverage**: All user-submitted picks
- **Behavior**: Blocked picks filtered out, not shown to community

### ✅ API Pick Endpoints
- **File**: `backend/routes/truth_mode_routes.py`
- **Endpoints**:
  - `POST /api/truth-mode/validate-pick` - Single pick validation
  - `POST /api/truth-mode/validate-picks` - Batch validation
  - `GET /api/truth-mode/dashboard-picks` - Dashboard picks with filtering

### ✅ Notifications & Alerts
- **File**: `backend/services/notification_service.py`
- **Function**: `create_pick_notification()`
- **Coverage**: All pick-related push notifications
- **Behavior**: Notification blocked if pick fails Truth Mode, returns `None`

---

## 🛡️ THREE VALIDATION GATES

### Gate 1: Data Integrity (70% threshold)
```python
✓ Event data complete (teams, odds, commence_time)
✓ Simulation exists
✓ Bookmakers available
✓ Injury data complete (if high-impact injuries present)
```

**Pass Criteria**: ≥70% data quality score

### Gate 2: Model Validity
```python
✓ ≥10,000 iterations
✓ ≥85% convergence score
✓ ≥10 stability score
✓ ≥48% win probability (confidence)
```

**Pass Criteria**: ALL checks must pass

### Gate 3: RCL Gate
```python
✓ RCL action = "publish"
✓ RCL confidence ≥60%
✓ Reasoning complete
```

**Pass Criteria**: RCL approves publication

---

## 🚫 BLOCK REASON CODES

When a pick is blocked, one or more of these reasons are returned:

| Code | Meaning |
|------|---------|
| `data_integrity_fail` | Event data incomplete or insufficient quality |
| `model_validity_fail` | Simulation quality below standards |
| `rcl_blocked` | Reasoning Chain Loop rejected pick |
| `missing_simulation` | No simulation data available |
| `insufficient_data` | Critical data fields missing |
| `injury_uncertainty` | High-impact injuries without complete analysis |
| `line_movement_unstable` | Excessive market volatility |
| `low_confidence` | Win probability below 48% threshold |

---

## 📊 IMPLEMENTATION DETAILS

### Core Files

1. **`backend/core/truth_mode.py`**
   - `TruthModeValidator` class
   - `BlockReason` enum
   - `TruthModeResult` data class
   - Validation logic for all three gates

2. **`backend/middleware/truth_mode_enforcement.py`**
   - `enforce_truth_mode_on_pick()` - Single pick validation
   - `filter_picks_with_truth_mode()` - Batch filtering
   - `validate_parlay_with_truth_mode()` - Parlay validation

### Integration Points

```python
# Example: Validating a single pick
from middleware.truth_mode_enforcement import enforce_truth_mode_on_pick

result = enforce_truth_mode_on_pick(
    event_id="abc123",
    bet_type="spread"
)

if result["status"] == "VALID":
    # Show pick to user
    confidence = result["confidence_score"]
else:
    # Show NO_PLAY card
    reasons = result["block_reasons"]
    message = result["message"]
```

---

## 🎯 WHAT HAPPENS WHEN BLOCKED

### Frontend Display (NO_PLAY Card)
```json
{
  "status": "NO_PLAY",
  "blocked": true,
  "block_reasons": ["model_validity_fail", "low_confidence"],
  "message": "Pick blocked by Truth Mode",
  "event_id": "abc123",
  "home_team": "Lakers",
  "away_team": "Celtics",
  "sport_key": "basketball_nba"
}
```

### Backend Logs
```
🛡️ [Truth Mode] Validating pick for event abc123...
❌ Gate 2 Failed: Model validity check (confidence=0.42, min=0.48)
🚫 Pick BLOCKED: Lakers vs Celtics spread
```

---

## 📈 MONITORING & METRICS

### Validation Tracking
- All validations logged to `truth_mode_validations` collection
- Tracks: event_id, bet_type, timestamp, result, block_reasons
- Queryable via `/api/truth-mode/status`

### Statistics
```json
{
  "recent_validations": 1247,
  "blocked_count": 156,
  "block_rate": 0.125,
  "common_block_reasons": {
    "low_confidence": 89,
    "model_validity_fail": 45,
    "data_integrity_fail": 22
  }
}
```

---

## ✅ TESTING CHECKLIST

- [x] Dashboard cards filter blocked picks
- [x] Sharp side `null` if blocked
- [x] Parlay builder rejects invalid legs
- [x] Community picks filtered
- [x] API endpoints enforce validation
- [x] Notifications blocked for invalid picks
- [x] All sports covered (NBA, NFL, NCAAF, NCAAB, MLB, NHL)
- [x] Block reason codes displayed to users
- [x] Logs show validation details

---

## 🚀 DEPLOYMENT STATUS

**Version**: 1.0  
**Status**: ✅ FULLY IMPLEMENTED  
**Date**: December 13, 2025  
**Coverage**: ALL PICK SURFACES  

### Sports Coverage
- ✅ Basketball (NBA)
- ✅ Basketball (NCAAB)
- ✅ Football (NFL)
- ✅ Football (NCAAF)
- ✅ Baseball (MLB)
- ✅ Hockey (NHL)

### Pick Surfaces
- ✅ Dashboard daily cards
- ✅ Sharp side indicators
- ✅ Parlay builder
- ✅ Community picks
- ✅ API endpoints
- ✅ Push notifications
- ✅ Real-time alerts

---

## 💡 KEY BENEFITS

1. **Zero False Confidence**: No pick shown without data backing
2. **User Trust**: Transparent block reasons build credibility
3. **Liability Protection**: Can't be accused of publishing unverified picks
4. **Quality Control**: Automated enforcement of editorial standards
5. **Multi-Sport**: Works across all leagues and bet types

---

## 🔧 CONFIGURATION

### Minimum Thresholds (Adjustable in `core/truth_mode.py`)
```python
min_confidence = 0.48       # 48% win probability
min_data_quality = 0.7      # 70% data completeness
min_stability = 10          # Stability score
min_iterations = 10000      # Simulation iterations
min_convergence = 0.85      # 85% convergence
```

---

## 📞 SUPPORT

For Truth Mode issues or questions:
- Check logs: `🛡️ [Truth Mode]` prefix
- Review validation details in database
- Contact: Backend team

**Last Updated**: December 13, 2025

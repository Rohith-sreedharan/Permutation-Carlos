# Quick Reference: Grading Architecture

**Last Updated:** 2024-01-15  
**Version:** 1.0.0

---

## 🚀 Quick Start

### Grade a Pick
```python
from backend.services.unified_grading_service import UnifiedGradingService

service = UnifiedGradingService(db)
result = await service.grade_pick("pick_abc123")

print(result.settlement_status)  # "WIN" | "LOSS" | "PUSH" | "VOID"
print(result.clv)                # {"clv_points": 0.5, "clv_percentage": 16.67}
```

### Fetch Score by Exact ID
```python
from backend.services.result_service import ResultService

service = ResultService()
score = await service.fetch_scores_by_oddsapi_id("oddsapi_event_xyz")

if score and score["completed"]:
    print(f"{score['home_score']} - {score['away_score']}")
```

### Create Event with OddsAPI ID
```python
# Automatically done by normalize_event() in odds_api.py

event = normalize_event(oddsapi_event)
# Now includes:
# {
#   "provider_event_map": {
#     "oddsapi": {
#       "event_id": "oddsapi_xyz789",
#       "raw_payload": { ... }
#     }
#   }
# }
```

---

## 📊 Data Flow

### Pick Creation → Grading Flow
```
1. Create Event (with OddsAPI ID)
   ↓
2. Create AI Pick (references event_id)
   ↓
3. Game Completes
   ↓
4. UnifiedGradingService.grade_pick(pick_id)
   ↓
5. Fetch score by exact OddsAPI ID
   ↓
6. Determine settlement (spread/ML/total rules)
   ↓
7. Compute CLV (non-blocking)
   ↓
8. Write to grading collection (canonical)
```

---

## 🗂️ Collections

### events
```json
{
  "event_id": "abc123",
  "home_team": "Lakers",
  "away_team": "Warriors",
  "provider_event_map": {
    "oddsapi": {
      "event_id": "oddsapi_xyz",
      "raw_payload": {}
    }
  }
}
```
**Index:** `provider_event_map.oddsapi.event_id` (sparse)

### ai_picks
```json
{
  "pick_id": "pick_abc",
  "event_id": "abc123",
  "market_type": "spread",
  "market_line": -3.0,
  "tier": "premium"
}
```
**Index:** `pick_id` (unique)

### grading (CANONICAL)
```json
{
  "pick_id": "pick_abc",
  "settlement_status": "WIN",
  "actual_score": {
    "home": 115,
    "away": 110
  },
  "clv": {
    "clv_points": 0.5
  },
  "graded_at": "2024-01-15T22:30:00Z"
}
```
**Index:** `pick_id` (unique), `settlement_status`

---

## 🔑 Key Concepts

### Exact OddsAPI ID Lookup
- **Problem:** Fuzzy team matching is unreliable
- **Solution:** Store exact OddsAPI event ID during event creation
- **Benefit:** Zero ambiguity, guaranteed score match

### Single Source of Truth
- **Problem:** 4 grading systems, no canonical storage
- **Solution:** UnifiedGradingService writes to grading collection only
- **Benefit:** Deterministic, auditable, no contradictions

### Idempotent Grading
- **Problem:** Re-running grading could create duplicates
- **Solution:** Unique constraint on grading.pick_id
- **Benefit:** Safe retries, no duplicate records

### Non-Blocking CLV
- **Problem:** Missing snapshot shouldn't block settlement
- **Solution:** Compute CLV if exists, null if missing
- **Benefit:** Grading completes even without CLV

---

## 🛠️ Common Tasks

### Backfill OddsAPI IDs
```bash
# Dry run
python backend/scripts/backfill_oddsapi_ids.py --dry-run --limit 100

# Production
python backend/scripts/backfill_oddsapi_ids.py
```

### Apply Database Indexes
```bash
python backend/db/indexes.py --apply
```

### Grade All Pending Picks
```python
picks = db["ai_picks"].find({"outcome": None})

service = UnifiedGradingService(db)
for pick in picks:
    try:
        await service.grade_pick(pick["pick_id"])
    except GameNotCompletedError:
        continue  # Game not finished yet
```

### Admin Override
```python
service = UnifiedGradingService(db)
await service.grade_pick(
    "pick_abc123",
    admin_override="VOID",  # Postponed game
    admin_note="Game postponed due to weather"
)
```

---

## 🚨 Error Handling

### PickNotFoundError
```python
# Pick doesn't exist
try:
    await service.grade_pick("invalid_pick")
except PickNotFoundError:
    print("Pick not found in ai_picks collection")
```

### MissingOddsAPIIDError
```python
# Event missing OddsAPI ID
try:
    await service.grade_pick("pick_abc")
except MissingOddsAPIIDError:
    print("Run backfill script to add OddsAPI ID")
```

### GameNotCompletedError
```python
# Game not finished yet
try:
    await service.grade_pick("pick_abc")
except GameNotCompletedError:
    print("Game still in progress, try again later")
```

---

## 📏 Settlement Rules

### Spread
```python
# Lakers -3.0
actual_margin = home_score - away_score  # 115 - 110 = 5
cover_margin = actual_margin - market_line  # 5 - (-3.0) = 8

if cover_margin > 0:
    settlement = "WIN"   # Lakers covered by 8
elif cover_margin < 0:
    settlement = "LOSS"  # Lakers didn't cover
else:
    settlement = "PUSH"  # Exactly covered
```

### Moneyline
```python
# Lakers ML
if home_score > away_score:
    settlement = "WIN"   # Lakers won
elif home_score < away_score:
    settlement = "LOSS"  # Lakers lost
else:
    settlement = "PUSH"  # Tie
```

### Total
```python
# Over 225.5
actual_total = home_score + away_score  # 115 + 110 = 225

if actual_total > market_line:
    settlement = "WIN"   # Over hit
elif actual_total < market_line:
    settlement = "LOSS"  # Over missed
else:
    settlement = "PUSH"  # Exactly on line
```

---

## 📈 Monitoring Queries

### Check Grading Collection Growth
```javascript
db.grading.countDocuments({})
```

### Settlement Distribution
```javascript
db.grading.aggregate([
  {$group: {_id: "$settlement_status", count: {$sum: 1}}}
])
```

### Missing CLV (Expected if no snapshot)
```javascript
db.grading.countDocuments({
  "settlement_status": {$in: ["WIN", "LOSS"]},
  "clv": null
})
```

### Duplicate Picks (Should be zero)
```javascript
db.grading.aggregate([
  {$group: {_id: "$pick_id", count: {$sum: 1}}},
  {$match: {count: {$gt: 1}}}
])
```

### Events Missing OddsAPI ID
```javascript
db.events.countDocuments({
  "provider_event_map.oddsapi.event_id": {$exists: false}
})
```

---

## 🔒 Security

### Admin Override Audit
```javascript
// Find all admin overrides
db.grading.find({"admin_override": {$ne: null}})
```

### PII Protection
- ✅ No email/name in grading collection
- ✅ Only anonymized user_id
- ✅ Audit logs for admin actions only

---

## 📚 Documentation

- **Full Guide:** [ODDSAPI_GRADING_MIGRATION_GUIDE.md](./ODDSAPI_GRADING_MIGRATION_GUIDE.md)
- **Summary:** [GRADING_FIX_SUMMARY.md](./GRADING_FIX_SUMMARY.md)
- **Status:** [PRODUCTION_IMPLEMENTATION_STATUS.md](./PRODUCTION_IMPLEMENTATION_STATUS.md)
- **Pick Schema:** [backend/docs/PICK_SCHEMA_AUDIT.md](./backend/docs/PICK_SCHEMA_AUDIT.md)

---

## ✅ Pre-Deployment Checklist

- [ ] Database indexes applied
- [ ] Backfill completed (>90% match rate)
- [ ] UnifiedGradingService deployed
- [ ] Result service updated
- [ ] Grading callers migrated
- [ ] Legacy grading blocked
- [ ] Monitoring queries added
- [ ] Team trained

---

**Need Help?** See [ODDSAPI_GRADING_MIGRATION_GUIDE.md](./ODDSAPI_GRADING_MIGRATION_GUIDE.md) for troubleshooting.

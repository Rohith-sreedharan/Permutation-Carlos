# BeatVegas Roster Governance System
## Institutional-Grade Missing Data Handling

**Status**: ✅ PRODUCTION READY  
**Version**: 1.0.0  
**Date**: February 4, 2026  
**Classification**: Revenue-Critical • Trust-Aligned • Global Standard

---

## Executive Summary

The Roster Governance System transforms missing roster data from an **error state** into a **controlled, deterministic BLOCKED state**. This ensures BeatVegas maintains institutional-grade reliability even when upstream data is unavailable.

### Key Guarantees

✅ **No 404 Errors**: Valid events never return HTTP 404 due to roster absence  
✅ **No Retry Loops**: TTL-based cooldown prevents infinite retries  
✅ **Idempotent Alerts**: Ops notified once per cooldown window  
✅ **Parlay Protection**: Blocked simulations excluded from parlays  
✅ **Clean Recovery**: Automatic unblocking when roster data arrives  
✅ **League Policies**: NCAAB/NCAAF require roster; NBA/NFL optional  

---

## Architecture

### State Machine

```
PENDING → [Roster Check] → READY or BLOCKED
                              ↓
                         [TTL Cooldown]
                              ↓
                    [Roster Arrives] → READY
```

### Components

#### 1. **RosterGovernance** (`backend/core/roster_governance.py`)
- **Purpose**: Centralized roster availability management
- **Methods**:
  - `check_roster_availability()` - Check if roster exists with cooldown
  - `get_blocked_status()` - Retrieve blocked simulation details
  - `get_roster_metrics()` - Ops metrics for monitoring
- **Database Collections**:
  - `roster_availability_checks` - Check history with TTL auto-expiry
  - `blocked_simulations` - Active blocked states

#### 2. **SimulationStatus Enum** (`backend/core/simulation_context.py`)
```python
class SimulationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CACHED = "CACHED"
    PRICE_MOVED = "PRICE_MOVED"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"  # NEW: Roster/data unavailable
```

#### 3. **BlockedReason Enum**
```python
class BlockedReason(str, Enum):
    ROSTER_UNAVAILABLE = "roster_unavailable"
    DATA_INSUFFICIENT = "data_insufficient"
    LEAGUE_RESTRICTION = "league_restriction"
    INTEGRITY_VIOLATION = "integrity_violation"
```

---

## API Contract

### Simulation Endpoint Response

**Before (❌ BAD)**:
```json
HTTP 404 Not Found
{
  "detail": "No roster data available for Eastern Michigan Eagles"
}
```

**After (✅ GOOD)**:
```json
HTTP 200 OK
{
  "status": "BLOCKED",
  "blocked_reason": "roster_unavailable",
  "message": "No roster data available for Eastern Michigan Eagles",
  "retry_after": "2026-02-04T18:30:00Z",
  "event_id": "abc123",
  "team_name": "Eastern Michigan Eagles",
  "can_publish": false,
  "can_parlay": false,
  "ui_display": {
    "title": "Simulation Blocked",
    "description": "Missing roster data",
    "action": "This game is temporarily unavailable. Check back later.",
    "icon": "🚫"
  }
}
```

---

## Cooldown Configuration

### TTL Windows

| League Type | Cooldown | Reason |
|------------|----------|---------|
| **Pro** (NBA, NFL, NHL, MLB) | 60 minutes | Data updates frequently |
| **College** (NCAAB, NCAAF) | 240 minutes (4 hours) | Data updates slower |
| **Ops Alert** | 24 hours | Prevent alert spam |

### League Policies

| League | Policy | Behavior if Missing |
|--------|--------|---------------------|
| NBA, NFL, NHL, MLB | `PREFERRED` | Simulation proceeds (degraded) |
| **NCAAB, NCAAF** | `REQUIRED` | **Simulation BLOCKED** |

---

## Frontend Integration

### GameDetail.tsx

**Blocked State Rendering**:
```tsx
if (simulation?.status === 'BLOCKED') {
  return (
    <div className="blocked-state-ui">
      <div className="icon">🚫</div>
      <h2>Simulation Temporarily Blocked</h2>
      <p>{simulation.message}</p>
      <div className="retry-info">
        System will re-check at: {retryTimeFormatted}
      </div>
      <button onClick={onBack}>← Back to Dashboard</button>
    </div>
  );
}
```

### Key Features
- ✅ No error state (controlled block)
- ✅ Displays retry time
- ✅ Shows team/game details
- ✅ Explains not an error
- ✅ Provides action (go back)

---

## Monitoring & Ops

### Endpoints

#### 1. `/api/roster/metrics`
**Purpose**: Get roster availability KPIs
```json
GET /api/roster/metrics?league=NCAAB

Response:
{
  "timestamp": "2026-02-04T12:00:00Z",
  "metrics": {
    "last_24h": {
      "total_checks": 150,
      "available": 135,
      "unavailable": 15,
      "blocked": 8,
      "availability_rate": 90.0
    },
    "currently_blocked": 3,
    "league": "NCAAB"
  },
  "status": "healthy"
}
```

#### 2. `/api/roster/blocked-simulations`
**Purpose**: List currently blocked games
```json
GET /api/roster/blocked-simulations?league=NCAAB&limit=50

Response:
{
  "total": 3,
  "blocked_simulations": [
    {
      "event_id": "abc123",
      "team_name": "Eastern Michigan Eagles",
      "league": "NCAAB",
      "blocked_reason": "roster_unavailable",
      "blocked_at": "2026-02-04T10:00:00Z",
      "retry_after": "2026-02-04T14:00:00Z",
      "event_details": {
        "home_team": "Central Michigan",
        "away_team": "Eastern Michigan Eagles",
        "commence_time": "2026-02-05T19:00:00Z"
      }
    }
  ]
}
```

#### 3. `/api/roster/health`
**Purpose**: System health check
```json
GET /api/roster/health

Response:
{
  "status": "healthy",  // or "degraded" or "critical"
  "timestamp": "2026-02-04T12:00:00Z",
  "metrics": {
    "availability_rate_24h": 92.5,
    "currently_blocked": 2,
    "checks_last_24h": 200,
    "total_unavailable_24h": 15
  },
  "system_version": "1.0.0",
  "governance_active": true
}
```

---

## Database Schema

### `roster_availability_checks` Collection

```javascript
{
  _id: ObjectId,
  team_name: "Eastern Michigan Eagles",
  league: "NCAAB",
  roster_available: false,
  checked_at: ISODate("2026-02-04T10:00:00Z"),
  blocked: true,
  ops_alerted: false  // Prevents duplicate alerts
}
```

**Indexes**:
- `{team_name: 1, league: 1, checked_at: -1}` - Cooldown lookups
- `{checked_at: 1}` with TTL 7 days - Auto-expiry

### `blocked_simulations` Collection

```javascript
{
  _id: ObjectId,
  event_id: "abc123",
  team_name: "Eastern Michigan Eagles",
  league: "NCAAB",
  status: "BLOCKED",
  blocked_reason: "roster_unavailable",
  blocked_at: ISODate("2026-02-04T10:00:00Z"),
  retry_after: ISODate("2026-02-04T14:00:00Z"),
  ops_alerted: false
}
```

**Indexes**:
- `{event_id: 1, status: 1}` - Fast status lookups
- `{retry_after: 1}` - Recovery checks

---

## Stress Test Coverage

### Test Suite (`backend/tests/test_roster_governance_stress.py`)

✅ **Test 1**: No 404s for valid events  
✅ **Test 2**: No retry loops (cooldown enforced)  
✅ **Test 3**: Idempotent ops alerts  
✅ **Test 4**: UI renders blocked state  
✅ **Test 5**: Parlay exclusion works  
✅ **Test 6**: Clean recovery when roster arrives  
✅ **Test 7**: League-specific policies enforced  
✅ **Test 8**: Database indexes created  
✅ **Test 9**: Monte Carlo integration  
✅ **Test 10**: Metrics endpoint accuracy  

**Run Tests**:
```bash
cd backend
python -m pytest tests/test_roster_governance_stress.py -v
```

---

## Valuation Impact

### Trust Preservation
- ✅ No silent degradation
- ✅ Transparent blocked state
- ✅ User understands why (not frustrated)

### Operational Excellence
- ✅ Prevents wasted compute on retry loops
- ✅ Ops alerted once (not spammed)
- ✅ Metrics visible to investors/leadership

### Model Integrity
- ✅ Never publishes unreliable sims
- ✅ Blocked sims excluded from parlays
- ✅ Clean state transitions

### Revenue Protection
- ✅ Users trust platform (lower churn)
- ✅ Institutional-grade operations
- ✅ Aligns with $100M+ valuation

---

## Migration Guide

### Backend Migration
1. Deploy `roster_governance.py`
2. Update `simulation_context.py` with new enums
3. Update `monte_carlo_engine.py` with roster checks
4. Update `simulation_routes.py` to return BLOCKED status
5. Deploy `roster_monitoring_routes.py`
6. Update `main.py` to include monitoring routes

### Frontend Migration
1. Update `types.ts` with BLOCKED status fields
2. Update `GameDetail.tsx` with blocked UI rendering
3. Update `EventCard.tsx` (if needed) to show blocked badge

### Database Migration
**No migration needed** - new collections auto-created with indexes.

### Rollback Plan
If issues arise, roster checks can be disabled by modifying league policies:
```python
LEAGUE_ROSTER_POLICIES = {
    "NCAAB": LeagueRosterPolicy.PREFERRED  # Downgrade from REQUIRED
}
```

---

## Future Enhancements

### Phase 2 (Optional)
- [ ] Roster data enrichment from multiple sources
- [ ] Predictive roster availability forecasting
- [ ] Automatic roster scraping for college teams
- [ ] User notifications when blocked game unblocks

### Phase 3 (Advanced)
- [ ] ML-based roster quality scoring
- [ ] Partial roster simulation (when some data missing)
- [ ] Integration with sports data vendors

---

## Support & Monitoring

### Ops Dashboard
Monitor roster health at: `/api/roster/health`

### Alert Thresholds
- **Healthy**: Availability ≥ 95%
- **Degraded**: Availability 85-94%
- **Critical**: Availability < 85%

### On-Call Playbook
1. Check `/api/roster/blocked-simulations` for affected games
2. Verify upstream roster data sources
3. Check `/api/roster/availability-history` for patterns
4. If systematic, adjust cooldown windows in `roster_governance.py`

---

## Conclusion

The Roster Governance System ensures BeatVegas handles missing roster data with institutional-grade discipline:

✅ No 404s, no retry loops, no silent degradation  
✅ Clean BLOCKED state with automatic recovery  
✅ Ops visibility and idempotent alerts  
✅ Parlay protection and model integrity  
✅ Trust-aligned, revenue-protective  

**Status**: Production-ready for immediate deployment.

---

**Document Version**: 1.0.0  
**Last Updated**: February 4, 2026  
**Authors**: BeatVegas Engineering  
**Classification**: LOCKED - Non-negotiable standard  

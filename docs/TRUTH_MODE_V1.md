# Truth Mode v1.0 - Zero-Lies Enforcement System

## 🛡️ Core Principle

**NO pick is allowed to be shown, pushed, or used in a parlay unless it passes ALL three gates:**

1. **Data Integrity Check** - Verifies event data quality and completeness
2. **Model Validity Check** - Validates simulation quality and prediction confidence  
3. **RCL Gate** - Reasoning Chain Loop approval (Publish/Block decision)

**If any gate fails → UI shows NO PLAY + reason codes**

## 🎯 Enforcement Scope

Truth Mode applies to:
- ✅ Dashboard pick cards
- ✅ "Sharp side detected" notifications
- ✅ Parlay Builder auto-fill
- ✅ Parlay Architect leg selection
- ✅ All API endpoints returning picks
- ✅ Telegram notifications
- ✅ Email alerts
- ✅ Push notifications

**Truth Mode applies to ALL sports. No exceptions.**

---

## 📋 Validation Gates

### Gate 1: Data Integrity Check

Validates:
- Event data exists and is complete
- Team information available
- Odds/bookmaker data present
- Commence time set
- Simulation data exists
- Injury data completeness (if high-impact injuries present)

**Minimum threshold:** 70% data quality score

**Block reasons:**
- `data_integrity_fail` - Overall data quality below threshold
- `insufficient_data` - Missing critical event information
- `injury_uncertainty` - High-impact injuries without detailed analysis

---

### Gate 2: Model Validity Check

Validates:
- Sufficient simulation iterations (≥10,000)
- Good convergence (≥0.85)
- Stable results (stability score ≥10)
- Confident prediction (probability ≥0.48 or 48%)

**Block reasons:**
- `model_validity_fail` - Model quality below standards
- `missing_simulation` - No Monte Carlo simulation available
- `low_confidence` - Win probability below 48% threshold
- `line_movement_unstable` - Betting lines too volatile

---

### Gate 3: RCL Gate

Validates:
- RCL decision action = "publish"
- RCL confidence ≥ 60%
- Reasoning chain complete

**Block reasons:**
- `rcl_blocked` - RCL determined pick should not be published
- Failed reasoning validation

---

## 🔌 API Integration

### Validate Single Pick

```typescript
POST /api/truth-mode/validate-pick
{
  "event_id": "event_123",
  "bet_type": "moneyline"
}

// Response (VALID)
{
  "status": "VALID",
  "event_id": "event_123",
  "confidence_score": 0.62,
  "truth_mode_validated": true,
  "validation_details": {...}
}

// Response (BLOCKED)
{
  "status": "NO_PLAY",
  "event_id": "event_123",
  "blocked": true,
  "block_reasons": ["low_confidence", "model_validity_fail"],
  "message": "Truth Mode: Pick blocked due to data quality or model confidence issues"
}
```

### Get Dashboard Picks (Truth Mode Enforced)

```typescript
GET /api/truth-mode/dashboard-picks?sport_key=basketball_nba

// Response
{
  "picks": [...],  // Only Truth Mode validated picks
  "count": 5,
  "blocked_count": 3,
  "truth_mode_enabled": true,
  "message": "Showing 5 Truth Mode validated picks (3 blocked)"
}
```

### Truth Mode Status

```typescript
GET /api/truth-mode/status

// Response
{
  "status": "active",
  "version": "1.0",
  "principle": "ZERO-LIES: No pick shown unless it passes Data Integrity + Model Validity + RCL Gate",
  "enforcement": "ALL sports, ALL endpoints, ALL pick displays"
}
```

---

## 🎨 Frontend UI Integration

### Displaying NO PLAY

```tsx
import { shouldShowNoPlay, createNoPlayCard, formatBlockReasons } from '@/utils/truthModeUtils';

// Check if pick is blocked
if (shouldShowNoPlay(pick)) {
  const noPlayCard = createNoPlayCard(pick);
  
  return (
    <div className="border-2 border-red-500 bg-red-50 dark:bg-red-900/20 p-4 rounded">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🛡️</span>
        <div>
          <h3 className="font-bold text-red-600">NO PLAY</h3>
          <p className="text-sm">{pick.event_name}</p>
        </div>
      </div>
      <p className="text-sm mt-2 text-gray-600">
        {formatBlockReasons(pick.block_reasons)}
      </p>
      <p className="text-xs mt-1 text-gray-500">
        Truth Mode: Data quality or confidence below standards
      </p>
    </div>
  );
}
```

### Truth Mode Badge

```tsx
import { getTruthModeBadgeText, getTruthModeBadgeColor } from '@/utils/truthModeUtils';

<div className={`px-2 py-1 rounded text-xs font-bold ${getTruthModeBadgeColor(pick.status)}`}>
  {getTruthModeBadgeText(pick)}
</div>
```

---

## 🔧 Backend Integration

### Parlay Architect (Automatic)

Truth Mode is automatically enforced in `parlay_architect.py`:

```python
# After leg selection, all legs are validated
valid_legs, blocked_legs = truth_mode_validator.validate_parlay_legs(selected_legs["legs"])

if blocked_legs:
    print(f"⚠️ [Truth Mode] {len(blocked_legs)} leg(s) blocked")
    # Only use validated legs in parlay
```

### Custom Endpoint Integration

```python
from middleware.truth_mode_enforcement import enforce_truth_mode_on_pick

@router.get("/my-picks")
async def get_my_picks():
    picks = get_picks_from_db()
    
    validated_picks = []
    for pick in picks:
        result = enforce_truth_mode_on_pick(
            event_id=pick["event_id"],
            bet_type=pick["bet_type"]
        )
        
        if result["status"] == "VALID":
            validated_picks.append(result)
        # Blocked picks not returned
    
    return {"picks": validated_picks}
```

---

## 📊 Monitoring & Logging

Truth Mode logs all validation results:

```python
print(f"🛡️ [Truth Mode] Validating pick...")
print(f"✅ [Truth Mode] Pick validated - confidence: 62%")
print(f"⚠️ [Truth Mode] Pick blocked - reasons: low_confidence, model_validity_fail")
```

Backend console will show:
- Number of picks validated
- Number of picks blocked
- Block reasons for each blocked pick
- Confidence scores for valid picks

---

## ✅ Testing Truth Mode

### Test Scenarios

1. **Valid Pick** - High confidence, complete data
2. **Low Confidence Block** - <48% win probability
3. **Missing Data Block** - No simulation or incomplete event data
4. **RCL Block** - RCL decision = "block"
5. **Parlay with Mixed Legs** - Some valid, some blocked

### Manual Testing

```bash
# Generate parlay (Truth Mode auto-enforced)
curl -X POST http://localhost:8000/api/architect/generate \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"sport_key": "basketball_nba", "leg_count": 4, "risk_profile": "balanced"}'

# Validate specific pick
curl -X POST http://localhost:8000/api/truth-mode/validate-pick \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"event_id": "event_123", "bet_type": "moneyline"}'

# Get Truth Mode status
curl http://localhost:8000/api/truth-mode/status
```

---

## 🚀 Deployment Checklist

- [x] Core Truth Mode validator implemented
- [x] Middleware for enforcement created
- [x] Parlay Architect integration complete
- [x] API routes for validation added
- [x] Frontend UI utilities created
- [x] Documentation written
- [ ] Truth Mode enabled in production
- [ ] Frontend components updated to show NO PLAY
- [ ] Telegram bot integration
- [ ] Email notification integration
- [ ] Push notification integration

---

## 🎯 Success Metrics

Track:
- **Validation Rate** - % of picks passing Truth Mode
- **Block Reasons** - Which gates block most picks
- **User Trust** - Impact on user confidence
- **Win Rate** - Validated picks vs blocked picks performance

---

## 📝 Notes

- Truth Mode runs on **every** pick generation
- Blocked picks are **never shown** to users
- NO PLAY responses include **specific reason codes**
- All sports follow **same validation rules**
- Truth Mode is **non-negotiable** - cannot be disabled

**Principle: If we're not confident, we don't show it. Period.**

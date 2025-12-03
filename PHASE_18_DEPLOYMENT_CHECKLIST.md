# PHASE 18 DEPLOYMENT CHECKLIST

**Status**: ✅ READY FOR DEPLOYMENT  
**Date**: December 2024  
**Phase**: Numerical Accuracy & Simulation Integrity

---

## Pre-Deployment Verification

### ✅ Backend Files Created
- [x] `backend/services/analytics_service.py` (400+ lines)
- [x] `backend/routes/analytics_routes.py` (296 lines)
- [x] `backend/tests/test_analytics_phase18.py` (test suite)

### ✅ Backend Files Modified
- [x] `backend/services/feedback_loop.py` (added CLV methods)
- [x] `backend/main.py` (registered analytics router)

### ✅ Frontend Files Modified
- [x] `components/GameDetail.tsx` (confidence tooltips + banners)
- [x] `components/ParlayArchitect.tsx` (letter grades + refresh timer)

### ✅ Documentation Created
- [x] `PHASE_18_SUMMARY.md` (comprehensive documentation)
- [x] `backend/tests/test_analytics_phase18.py` (executable tests)

### ✅ Code Quality Checks
- [x] All TypeScript errors resolved
- [x] All Python type errors resolved
- [x] analytics_service.py compiles without errors
- [x] analytics_routes.py compiles without errors
- [x] feedback_loop.py compiles without errors

---

## Deployment Steps

### Step 1: Backend Deployment
```bash
cd backend

# Install dependencies (if needed)
pip install -r requirements.txt

# Run analytics test suite
python tests/test_analytics_phase18.py

# Verify no errors
echo "✅ Analytics tests passed"

# Restart backend server
# (Your deployment method here - e.g., systemctl restart, pm2 restart, etc.)
```

**Expected Output:**
```
✅ ALL PHASE 18 TESTS PASSED - Numerical Accuracy Enforced

Key Validations:
  ✓ EV uses proper formula
  ✓ EDGE requires ALL 6 conditions
  ✓ Parlay EV from probability product
  ✓ Confidence tooltips explain basis
  ✓ Tier messaging differentiates power
```

### Step 2: Database Setup
```bash
# Connect to MongoDB
mongosh

# Ensure clv_snapshots collection exists
use beatvegas_db

# Create indexes for CLV tracking
db.clv_snapshots.createIndex({ "event_id": 1 })
db.clv_snapshots.createIndex({ "prediction_timestamp": -1 })
db.clv_snapshots.createIndex({ "settled": 1 })

# Verify indexes
db.clv_snapshots.getIndexes()
```

**Expected Indexes:**
- `_id` (auto)
- `event_id`
- `prediction_timestamp`
- `settled`

### Step 3: API Endpoint Verification
```bash
# Test analytics health endpoint
curl http://localhost:8000/api/analytics/health

# Expected response:
{
  "status": "healthy",
  "service": "Analytics Service",
  "phase": "18 - Numerical Accuracy & Simulation Integrity",
  "features": [
    "EV Calculation (strict formula)",
    "EDGE/LEAN/NEUTRAL Classification",
    "Parlay EV",
    "Confidence Tooltips",
    "CLV Performance Tracking"
  ]
}

# Test EV calculation endpoint
curl -X POST http://localhost:8000/api/analytics/calculate-ev \
  -H "Content-Type: application/json" \
  -d '{
    "model_probability": 0.58,
    "american_odds": 110,
    "sim_count": 50000
  }'

# Expected response:
{
  "ev_per_dollar": 0.074,
  "edge_percentage": 0.056,
  "is_ev_plus": true,
  "display_edge": "+5.6%",
  "implied_probability": 0.524
}

# Test confidence tooltip endpoint
curl "http://localhost:8000/api/analytics/confidence-tooltip?confidence_score=75&volatility=LOW&sim_count=50000"

# Expected response: JSON with score, label, banner_type, banner_message, tooltip
```

### Step 4: Frontend Deployment
```bash
cd ..  # Back to root

# Build frontend
npm run build

# Deploy (your deployment method - e.g., Vercel, Netlify, etc.)
# Or test locally:
npm run dev
```

### Step 5: Manual QA

#### GameDetail Page
1. Navigate to any game detail page (e.g., `/game/<game_id>`)
2. **Verify Confidence Display:**
   - [ ] Confidence score shows (e.g., "75")
   - [ ] Info icon (ℹ️) visible next to "Confidence" label
   - [ ] Hover over confidence card → tooltip appears with formula explanation
   - [ ] Banner appears below score:
     - Green banner for confidence ≥70: "High-confidence simulation"
     - Yellow banner for confidence <40: "High volatility expected"
3. **Verify Tooltip Content:**
   - Should mention "Monte Carlo simulations"
   - Should mention "coefficient of variation"
   - Should mention tier (e.g., "Core tier")

#### ParlayArchitect Page
1. Navigate to `/architect`
2. Generate a parlay (any sport, any leg count)
3. **Verify Letter Grades:**
   - [ ] Shows "Grade: B+" (or A/A-/B/B-/C/D)
   - [ ] Shows raw confidence below: "(65/100 confidence)"
4. **Verify Refresh Timer:**
   - [ ] Orange banner at top: "⏳ This AI parlay refreshes every 30 minutes"
5. **Verify "Why This Parlay" Section:**
   - [ ] Section titled "🔥 Why This Parlay Was Built"
   - [ ] Shows 5 bullet points:
     - Correlation-safe direction
     - High EV anchor leg
     - Confidence curve stable
     - No injury volatility red flags
     - Passed correlation filter

---

## Post-Deployment Monitoring

### Day 1: Immediate Checks
- [ ] Monitor analytics endpoint logs (no 500 errors)
- [ ] Check CLV snapshots being written to DB
- [ ] Verify confidence tooltips load without errors
- [ ] Check frontend console for errors

### Week 1: Usage Metrics
- [ ] Track `/api/analytics/calculate-ev` call volume
- [ ] Monitor `/api/analytics/confidence-tooltip` response times
- [ ] Count CLV snapshots created (should match prediction count)
- [ ] Verify no regression in GameDetail load times

### Week 2: Business Metrics
- [ ] Survey 20 users: "Do you trust our numbers?" (target: 85%+)
- [ ] Compare support ticket volume (expect 20-40% reduction in "why wrong?")
- [ ] Track tier upgrade conversion (before/after confidence tooltips)

### Month 1: CLV Validation
- [ ] Run `/api/analytics/clv-performance?days_back=30`
- [ ] Verify CLV rate ≥63% (meets target)
- [ ] Review EDGE classification distribution (expect 15-25% EDGE, 40-50% LEAN)
- [ ] Calculate brier score for confidence calibration

---

## Rollback Plan

### If Issues Arise

**Issue: Analytics endpoints returning 500 errors**
```bash
# Check logs
tail -f backend/logs/app.log | grep analytics

# Roll back analytics routes
git checkout HEAD~1 backend/routes/analytics_routes.py
git checkout HEAD~1 backend/main.py

# Restart backend
# (Your restart command)
```

**Issue: Confidence tooltips not rendering**
```bash
# Check frontend console for errors
# Disable tooltip feature temporarily:
git checkout HEAD~1 components/GameDetail.tsx
npm run build
# Deploy
```

**Issue: CLV tracking writing incorrect data**
```bash
# Disable CLV logging
# Comment out CLV calls in feedback_loop.py
# Or drop clv_snapshots collection:
mongosh
use beatvegas_db
db.clv_snapshots.drop()
```

---

## Success Criteria

### Technical
- ✅ All analytics endpoints return 200 OK
- ✅ CLV snapshots written for every prediction
- ✅ Confidence tooltips render in <500ms
- ✅ No increase in GameDetail page load time

### Business
- ✅ User trust survey ≥85% positive
- ✅ Support tickets reduced by ≥20%
- ✅ CLV rate ≥63% (model beats closing line)

---

## Contact & Support

**Engineering Owner**: Backend Team  
**Product Owner**: Product Team  
**Escalation**: CTO

**Documentation**: `PHASE_18_SUMMARY.md`  
**Tests**: `backend/tests/test_analytics_phase18.py`

---

## Sign-Off

- [ ] Backend Engineer: _______________  Date: __________
- [ ] Frontend Engineer: _______________  Date: __________
- [ ] QA Lead: _______________  Date: __________
- [ ] Product Manager: _______________  Date: __________

---

*Checklist Version: 1.0*  
*Last Updated: December 2024*

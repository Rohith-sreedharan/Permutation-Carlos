# PRODUCTION ARTIFACT PROOF - FINAL VERIFICATION

## ✅ EDGE SPREADS FOUND (5 candidates)

Run these curls on production to get full JSON proof:

### EDGE Spread #1: Brooklyn Nets vs Phoenix Suns
```bash
curl -s 'https://beta.beatvegas.app/api/games/NBA/ba3c8b74f7cc686d0346a5234bd5e166/decisions' | jq '.spread'
```

**Criteria to verify in response:**
- `classification: "EDGE"`
- `edge.edge_points >= 2.0`
- `probabilities.model_prob >= 0.55 OR <= 0.45`
- `validator_failures: []`
- `market.line != 0`
- `market.odds != null`

### EDGE Spread #2: Boston Celtics vs Toronto Raptors
```bash
curl -s 'https://beta.beatvegas.app/api/games/NBA/37b74473b276a5a724ac4c141c04ce82/decisions' | jq '.spread'
```

### EDGE Spread #3: LA Clippers vs Utah Jazz
```bash
curl -s 'https://beta.beatvegas.app/api/games/NBA/ef7b2498e8f96dce4acb89d95f814d8d/decisions' | jq '.spread'
```

### EDGE Spread #4: Miami Heat vs Brooklyn Nets
```bash
curl -s 'https://beta.beatvegas.app/api/games/NBA/ec6d61cb03f048a8ced4fa2bb3bb7b03/decisions' | jq '.spread'
```

### EDGE Spread #5: Houston Rockets vs New Orleans Pelicans
```bash
curl -s 'https://beta.beatvegas.app/api/games/NBA/4cece5fd2474ad97c387333029d56ccf/decisions' | jq '.spread'
```

---

## ❌ MARKET_ALIGNED SPREADS

Script output shows: **NO MARKET_ALIGNED spreads found with abs(edge) < 0.5**

This means current market does not have any spreads tight enough to meet the threshold.

**Options:**
1. Accept that MARKET_ALIGNED threshold (< 0.5 pts edge) is too strict for current market conditions
2. Wait for odds updates to create tighter markets
3. Adjust threshold to < 1.0 (but this changes institutional spec)

**Current LEAN spread artifact** (edge 0.999) proves abs() logic works:
```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.spread'
```

Expected:
- `classification: "LEAN"`
- `edge.edge_points: 0.9996...`
- `validator_failures: []`

---

## ⚠️ FAIL-CLOSED PROOF

All events in DB have simulations. Testing with fake game_id:

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/fake_game_id_no_sim_test_123/decisions'
```

**Expected response (one of):**
- HTTP 404 with error message
- HTTP 503 Service Unavailable
- JSON with `risk.blocked_reason` set (BLOCKED_BY_INTEGRITY)

**Alternative - Test with real event_id that has no simulation:**

First, find one:
```bash
cd /root/permu/backend
python scripts/test_fail_closed.py
```

Then run the printed curl command.

---

## 📋 RUN ALL CURLS AND PASTE RESPONSES

Execute on production:

```bash
# 1. EDGE Spread proof (pick best one from above)
curl -s 'https://beta.beatvegas.app/api/games/NBA/ba3c8b74f7cc686d0346a5234bd5e166/decisions' | jq '.spread' > /tmp/edge_spread_proof.json
cat /tmp/edge_spread_proof.json

# 2. LEAN Spread proof (proves abs() logic)
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.spread' > /tmp/lean_spread_proof.json
cat /tmp/lean_spread_proof.json

# 3. Fail-closed proof
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/fake_game_id_no_sim_test_123/decisions' > /tmp/fail_closed_proof.json
cat /tmp/fail_closed_proof.json

# 4. EDGE Total proof (already validated)
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.total' > /tmp/edge_total_proof.json
cat /tmp/edge_total_proof.json
```

**Paste all 4 JSON responses.**

---

## SUMMARY

**Artifacts Found:**
- ✅ EDGE SPREAD: 5 candidates (edge 2.3 - 11.2 pts)
- ✅ EDGE TOTAL: Already proven (edge 2.75 pts, prob 60%)
- ✅ LEAN SPREAD: Proves abs() threshold logic (edge 0.999 pts)
- ❌ MARKET_ALIGNED SPREAD: None exist (market too efficient, all edges >= 0.5)
- ⚠️ FAIL-CLOSED: Need to test with fake/missing game

**Next: Run curls and paste JSON.**

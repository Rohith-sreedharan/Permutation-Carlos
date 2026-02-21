# Production Artifact Discovery Commands

## ⚠️ PREREQUISITE: Deploy Latest Code

```bash
ssh ubuntu@159.203.122.145
cd /root/permu

# 1. Pull latest (ENV policy fix + artifact finders)
git pull origin main

# 2. Rebuild frontend (clean .env, no localhost)
npm run build

# 3. Restart services
pm2 restart permu-frontend
pm2 restart permu-backend

# 4. Verify
pm2 logs --lines 20
```

---

## 1. MARKET_ALIGNED Spread Discovery

**Find spread with abs(edge) < 0.5:**

```bash
cd /root/permu/backend
python scripts/find_market_aligned.py
```

**Expected Output:**
```
✅ FOUND 2 MARKET_ALIGNED SPREAD(S):

[1] NCAAB: Away @ Home
    game_id: <game_id>
    model_spread: 5.25
    market_spread: 5.5
    edge: 0.250 pts (< 0.5 threshold) ✅

    Curl command:
    curl -s 'https://beta.beatvegas.app/api/games/NCAAB/<game_id>/decisions' | jq '.spread'
```

**Verification:**
```bash
# Run printed curl command
curl -s 'https://beta.beatvegas.app/api/games/<league>/<game_id>/decisions' | jq '.spread | {
  classification,
  edge: .edge.edge_points,
  validators: .validator_failures,
  market_line: .market.line,
  market_odds: .market.odds
}'
```

**Requirements:**
- ✅ `classification == "MARKET_ALIGNED"`
- ✅ `abs(edge.edge_points) < 0.5`
- ✅ `validator_failures == []`
- ✅ `market.line != 0`
- ✅ `market.odds != null`

---

## 2. EDGE Spread Discovery

**Find spread with abs(edge) >= 2.0 AND prob >= 0.55/0.45:**

```bash
cd /root/permu/backend
python scripts/find_edge_spread.py
```

**Expected Output:**
```
✅ FOUND 3 EDGE SPREAD(S):

[1] NCAAB: Away @ Home
    game_id: <game_id>
    model_spread: 7.25
    market_spread: 4.5
    edge: 2.750 pts (>= 2.0 threshold) ✅
    home_win_prob: 62.50% (>= 0.55 OR <= 0.45) ✅

    Curl command:
    curl -s 'https://beta.beatvegas.app/api/games/NCAAB/<game_id>/decisions' | jq '.spread'
```

**Verification:**
```bash
# Run printed curl command
curl -s 'https://beta.beatvegas.app/api/games/<league>/<game_id>/decisions' | jq '.spread | {
  classification,
  edge: .edge.edge_points,
  prob: .probabilities.model_prob,
  validators: .validator_failures,
  market_line: .market.line,
  market_odds: .market.odds
}'
```

**Requirements:**
- ✅ `classification == "EDGE"`  
- ✅ `abs(edge.edge_points) >= 2.0`
- ✅ `model_prob >= 0.55 OR model_prob <= 0.45`
- ✅ `validator_failures == []`
- ✅ `market.line != 0`
- ✅ `market.odds != null`

---

## 3. EDGE Total (Already Validated)

**Known working artifact:**

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.total'
```

**Status:** ✅ PROVEN (edge 2.75, prob 60%, validators [])

---

## 4. LEAN Spread (Threshold Validation)

**Verify abs(edge) fix is working:**

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.spread | {
  classification,
  edge: .edge.edge_points,
  reasons,
  validators: .validator_failures
}'
```

**Expected:**
```json
{
  "classification": "LEAN",
  "edge": 0.9996652573289913,
  "reasons": ["Moderate edge: 1.0 point spread differential"],
  "validators": []
}
```

**Proof:** Edge 0.999 now correctly LEAN (not MARKET_ALIGNED) after abs() fix.

---

## 5. Fail-Closed Behavior

**Find game without simulation:**

```bash
cd /root/permu/backend
python scripts/test_fail_closed.py
```

**Expected Output:**
```
✅ FOUND game WITHOUT simulation:

League: NCAAB
Game: Away @ Home
game_id: <game_id>

FAIL-CLOSED CURL:
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/<game_id>/decisions'

Expected: HTTP 503 OR 'BLOCKED_BY_INTEGRITY' with risk.blocked_reason
```

**Verification:**
```bash
# Run printed curl command
curl -s 'https://beta.beatvegas.app/api/games/<league>/<game_id>/decisions'
```

**Requirements (ONE OF):**
- ✅ HTTP 503 Service Unavailable, OR
- ✅ JSON with `risk.blocked_reason != null` and classification blocked

---

## Summary: Artifact Requirements

| Artifact | Script | Key Criteria |
|----------|--------|--------------|
| MARKET_ALIGNED spread | `find_market_aligned.py` | `abs(edge) < 0.5`, `validators=[]` |
| EDGE spread | `find_edge_spread.py` | `abs(edge) >= 2.0`, prob gate, `validators=[]` |
| EDGE total | (known game) | `edge >= 2.0`, prob gate, `validators=[]` ✅ |
| Fail-closed | `test_fail_closed.py` | HTTP 503 OR blocked response |

**All scripts print curl commands. Run them on PRODUCTION after deployment.**

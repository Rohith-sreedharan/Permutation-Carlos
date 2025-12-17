# Pick State Examples with Block Reasons ✅

**Date:** December 15, 2025  
**Status:** All states now include explicit reason codes

---

## 1. PICK State Example (Parlay-Eligible)

**Criteria Met:**
- ✅ Probability ≥ 58% (NFL threshold)
- ✅ Edge ≥ 3.0 pts
- ✅ Confidence ≥ 65/100
- ✅ Variance z-score ≤ 1.25
- ✅ Market deviation ≤ 6.0 pts
- ✅ Data quality ≥ 70%
- ✅ Calibration approved (publish=True)

```json
{
  "event_id": "chiefs_vs_bills_2025_12_15",
  "sport_key": "americanfootball_nfl",
  "home_team": "Kansas City Chiefs",
  "away_team": "Buffalo Bills",
  
  "pick_state": "PICK",
  "can_publish": true,
  "can_parlay": true,
  "confidence_tier": "STRONG",
  
  "metrics": {
    "market_total": 48.5,
    "model_total": 52.3,
    "edge_pts": 3.8,
    "over_probability": 0.612,
    "variance_total": 14.2,
    "confidence_score": 72
  },
  
  "calibration": {
    "publish": true,
    "p_raw": 0.635,
    "p_adjusted": 0.612,
    "edge_raw": 4.2,
    "edge_adjusted": 3.8,
    "confidence_label": "STRONG",
    "z_variance": 1.01,
    "block_reasons": [],
    "applied_penalties": {
      "market_penalty": 0.98,
      "variance_penalty": 1.0
    }
  },
  
  "state_machine_reasons": [
    "Meets all PICK thresholds"
  ],
  
  "thresholds_met": {
    "probability_pick": true,
    "edge_pick": true,
    "confidence_pick": true,
    "variance_pick": true,
    "market_deviation_pick": true,
    "data_quality_pick": true
  },
  
  "pick_classification": {
    "state": "PICK",
    "reasons": ["Meets all PICK thresholds"],
    "confidence_tier": "STRONG",
    "thresholds_met": {
      "probability_pick": true,
      "edge_pick": true,
      "confidence_pick": true,
      "variance_pick": true,
      "market_deviation_pick": true,
      "data_quality_pick": true
    }
  }
}
```

**Pick Audit Entry:**
```json
{
  "game_id": "chiefs_vs_bills_2025_12_15",
  "sport": "americanfootball_nfl",
  "pick_state": "PICK",
  "publish_decision": true,
  "block_reasons": [],
  "state_machine_reasons": ["Meets all PICK thresholds"],
  "confidence_score": 72,
  "vegas_line": 48.5,
  "model_line": 52.3,
  "edge_adjusted": 3.8,
  "sharp_side": "OVER",
  "timestamp": "2025-12-15T18:30:00Z"
}
```

---

## 2. LEAN State Example (Publishable, NOT Parlay-Eligible)

**Criteria:**
- ✅ Meets LEAN thresholds (lower bar than PICK)
- ❌ Does NOT meet PICK thresholds
- ✅ Calibration approved (publish=True)
- ⚠️ BLOCKED from parlays

```json
{
  "event_id": "dolphins_vs_jets_2025_12_15",
  "sport_key": "americanfootball_nfl",
  "home_team": "Miami Dolphins",
  "away_team": "New York Jets",
  
  "pick_state": "LEAN",
  "can_publish": true,
  "can_parlay": false,
  "confidence_tier": "WEAK",
  
  "metrics": {
    "market_total": 44.5,
    "model_total": 47.2,
    "edge_pts": 2.7,
    "over_probability": 0.562,
    "variance_total": 16.8,
    "confidence_score": 58
  },
  
  "calibration": {
    "publish": true,
    "p_raw": 0.591,
    "p_adjusted": 0.562,
    "edge_raw": 3.1,
    "edge_adjusted": 2.7,
    "confidence_label": "LEAN",
    "z_variance": 1.20,
    "block_reasons": [],
    "applied_penalties": {
      "market_penalty": 0.96,
      "variance_penalty": 0.98
    }
  },
  
  "state_machine_reasons": [
    "Edge 2.7 < 3.0 (PICK threshold)",
    "Confidence 58 < 65 (PICK threshold)",
    "Meets LEAN thresholds, NOT parlay-eligible"
  ],
  
  "thresholds_met": {
    "probability_pick": false,
    "edge_pick": false,
    "confidence_pick": false,
    "variance_pick": true,
    "market_deviation_pick": true,
    "data_quality_pick": true,
    "probability_lean": true,
    "edge_lean": true,
    "confidence_lean": true,
    "variance_lean": true,
    "market_deviation_lean": true
  },
  
  "pick_classification": {
    "state": "LEAN",
    "reasons": [
      "Edge 2.7 < 3.0 (PICK threshold)",
      "Confidence 58 < 65 (PICK threshold)",
      "Meets LEAN thresholds, NOT parlay-eligible"
    ],
    "confidence_tier": "WEAK",
    "thresholds_met": {
      "probability_pick": false,
      "edge_pick": false,
      "confidence_pick": false,
      "probability_lean": true,
      "edge_lean": true,
      "confidence_lean": true
    }
  }
}
```

**Pick Audit Entry:**
```json
{
  "game_id": "dolphins_vs_jets_2025_12_15",
  "sport": "americanfootball_nfl",
  "pick_state": "LEAN",
  "publish_decision": true,
  "block_reasons": [],
  "state_machine_reasons": [
    "Edge 2.7 < 3.0 (PICK threshold)",
    "Confidence 58 < 65 (PICK threshold)",
    "Meets LEAN thresholds, NOT parlay-eligible"
  ],
  "confidence_score": 58,
  "vegas_line": 44.5,
  "model_line": 47.2,
  "edge_adjusted": 2.7,
  "sharp_side": "OVER",
  "timestamp": "2025-12-15T18:30:00Z"
}
```

---

## 3. NO_PLAY State Example (Blocked by Calibration)

**Blocked by:** Calibration engine (extreme confidence with low confidence score)

```json
{
  "event_id": "seahawks_vs_packers_2025_12_14",
  "sport_key": "americanfootball_nfl",
  "home_team": "Seattle Seahawks",
  "away_team": "Green Bay Packers",
  
  "pick_state": "NO_PLAY",
  "can_publish": false,
  "can_parlay": false,
  "confidence_tier": "NONE",
  
  "metrics": {
    "market_total": 41.5,
    "model_total": 58.0,
    "edge_pts": 16.5,
    "over_probability": 0.911,
    "variance_total": 156.9,
    "confidence_score": 30
  },
  
  "calibration": {
    "publish": false,
    "p_raw": 0.911,
    "p_adjusted": 0.911,
    "edge_raw": 16.5,
    "edge_adjusted": 16.5,
    "confidence_label": "NO_PLAY",
    "z_variance": 11.21,
    "block_reasons": [
      "LOW_CONFIDENCE",
      "EXTREME_PROBABILITY",
      "EXCESSIVE_EDGE"
    ],
    "applied_penalties": {}
  },
  
  "state_machine_reasons": [
    "LOW_CONFIDENCE",
    "EXTREME_PROBABILITY",
    "EXCESSIVE_EDGE"
  ],
  
  "thresholds_met": {},
  
  "pick_classification": {
    "state": "NO_PLAY",
    "reasons": [
      "LOW_CONFIDENCE",
      "EXTREME_PROBABILITY",
      "EXCESSIVE_EDGE"
    ],
    "confidence_tier": "NONE",
    "thresholds_met": {}
  }
}
```

**Pick Audit Entry:**
```json
{
  "game_id": "seahawks_vs_packers_2025_12_14",
  "sport": "americanfootball_nfl",
  "pick_state": "NO_PLAY",
  "publish_decision": false,
  "block_reasons": [
    "LOW_CONFIDENCE",
    "EXTREME_PROBABILITY",
    "EXCESSIVE_EDGE"
  ],
  "state_machine_reasons": [
    "LOW_CONFIDENCE",
    "EXTREME_PROBABILITY",
    "EXCESSIVE_EDGE"
  ],
  "confidence_score": 30,
  "vegas_line": 41.5,
  "model_line": 58.0,
  "edge_adjusted": 16.5,
  "sharp_side": "OVER",
  "timestamp": "2025-12-14T19:45:08Z"
}
```

**Reason Analysis:**
- **LOW_CONFIDENCE**: Confidence score = 30/100 (minimum is 55 for LEAN, 65 for PICK)
- **EXTREME_PROBABILITY**: 91.1% Over probability indicates model convergence failure
- **EXCESSIVE_EDGE**: 16.5 pt edge (>8 pts) suggests model error, not real edge

---

## 4. NO_PLAY State Example (Blocked by Pick State Machine)

**Blocked by:** Pick state machine (fails minimum LEAN thresholds)

```json
{
  "event_id": "raiders_vs_chargers_2025_12_15",
  "sport_key": "americanfootball_nfl",
  "home_team": "Las Vegas Raiders",
  "away_team": "Los Angeles Chargers",
  
  "pick_state": "NO_PLAY",
  "can_publish": false,
  "can_parlay": false,
  "confidence_tier": "NONE",
  
  "metrics": {
    "market_total": 45.5,
    "model_total": 46.8,
    "edge_pts": 1.3,
    "over_probability": 0.523,
    "variance_total": 15.2,
    "confidence_score": 48
  },
  
  "calibration": {
    "publish": true,
    "p_raw": 0.538,
    "p_adjusted": 0.523,
    "edge_raw": 1.8,
    "edge_adjusted": 1.3,
    "confidence_label": "LEAN",
    "z_variance": 1.08,
    "block_reasons": [],
    "applied_penalties": {
      "market_penalty": 0.98,
      "variance_penalty": 0.99
    }
  },
  
  "state_machine_reasons": [
    "Probability 52.3% < 55.0% (LEAN threshold)",
    "Edge 1.3 < 2.0 (LEAN threshold)",
    "Confidence 48 < 55 (LEAN threshold)",
    "Does not meet minimum LEAN thresholds"
  ],
  
  "thresholds_met": {
    "probability_lean": false,
    "edge_lean": false,
    "confidence_lean": false,
    "variance_lean": true,
    "market_deviation_lean": true
  },
  
  "pick_classification": {
    "state": "NO_PLAY",
    "reasons": [
      "Probability 52.3% < 55.0% (LEAN threshold)",
      "Edge 1.3 < 2.0 (LEAN threshold)",
      "Confidence 48 < 55 (LEAN threshold)",
      "Does not meet minimum LEAN thresholds"
    ],
    "confidence_tier": "NONE",
    "thresholds_met": {
      "probability_lean": false,
      "edge_lean": false,
      "confidence_lean": false
    }
  }
}
```

**Pick Audit Entry:**
```json
{
  "game_id": "raiders_vs_chargers_2025_12_15",
  "sport": "americanfootball_nfl",
  "pick_state": "NO_PLAY",
  "publish_decision": true,
  "block_reasons": [],
  "state_machine_reasons": [
    "Probability 52.3% < 55.0% (LEAN threshold)",
    "Edge 1.3 < 2.0 (LEAN threshold)",
    "Confidence 48 < 55 (LEAN threshold)",
    "Does not meet minimum LEAN thresholds"
  ],
  "confidence_score": 48,
  "vegas_line": 45.5,
  "model_line": 46.8,
  "edge_adjusted": 1.3,
  "sharp_side": "OVER",
  "timestamp": "2025-12-15T18:30:00Z"
}
```

**Reason Analysis:**
- Calibration approved (publish=True) because metrics are reasonable
- Pick state machine blocked because edge is too small (1.3 < 2.0 pts minimum for LEAN)
- Not publishable as standalone pick due to insufficient edge

---

## 5. NO_PLAY State Example (Legacy Data - Missing Inputs)

**Blocked by:** `ensure_pick_state()` function (legacy simulation without required inputs)

```json
{
  "event_id": "legacy_game_2025_12_10",
  "sport_key": "americanfootball_nfl",
  
  "pick_state": "NO_PLAY",
  "can_publish": false,
  "can_parlay": false,
  "confidence_tier": "NONE",
  
  "metrics": {
    "market_total": null,
    "model_total": null,
    "edge_pts": null,
    "over_probability": null,
    "variance_total": null,
    "confidence_score": null
  },
  
  "state_machine_reasons": [
    "CALIBRATION_NOT_RUN",
    "CONFIDENCE_NOT_COMPUTED",
    "VARIANCE_NOT_COMPUTED",
    "NO_MARKET_LINE"
  ],
  
  "pick_classification": {
    "state": "NO_PLAY",
    "reasons": [
      "CALIBRATION_NOT_RUN",
      "CONFIDENCE_NOT_COMPUTED",
      "VARIANCE_NOT_COMPUTED",
      "NO_MARKET_LINE"
    ],
    "confidence_tier": "NONE",
    "thresholds_met": {}
  }
}
```

**Pick Audit Entry:**
```json
{
  "game_id": "legacy_game_2025_12_10",
  "sport": "americanfootball_nfl",
  "pick_state": "NO_PLAY",
  "publish_decision": false,
  "block_reasons": [],
  "state_machine_reasons": [
    "CALIBRATION_NOT_RUN",
    "CONFIDENCE_NOT_COMPUTED",
    "VARIANCE_NOT_COMPUTED",
    "NO_MARKET_LINE"
  ],
  "confidence_score": 0,
  "timestamp": "2025-12-10T14:22:00Z"
}
```

**Reason Analysis:**
- Legacy simulation from before pick state machine was implemented
- Missing required inputs: calibration, confidence, variance, market line
- `ensure_pick_state()` forces NO_PLAY with explicit reason codes
- Would require re-simulation to produce valid classification

---

## Audit Storage Confirmation ✅

### MongoDB Collections

**1. `pick_audit` Collection**
- **Purpose**: Logs every pick decision for audit trail
- **Fields**:
  - `game_id`, `sport`, `market_type`
  - `vegas_line`, `model_line`, `raw_model_line`
  - `p_raw`, `p_adjusted`, `edge_raw`, `edge_adjusted`
  - `publish_decision`, `block_reasons`, `state_machine_reasons`
  - `pick_state`, `confidence_score`, `data_quality`
  - `sharp_side`, `edge_direction`
  - `timestamp`

**2. `monte_carlo_simulations` Collection**
- **Purpose**: Stores complete simulation results (sim_audit)
- **Fields**:
  - `pick_state`, `can_publish`, `can_parlay`
  - `confidence_tier`, `state_machine_reasons`
  - `thresholds_met` (detailed breakdown)
  - `pick_classification` (complete object)
  - `calibration` (with block_reasons)
  - All simulation metrics

---

## Verification Commands

```bash
# Check pick_audit entries
curl -s "http://localhost:8000/api/debug/pick-states?sport=americanfootball_nfl&hours=48" | python3 -m json.tool

# Query MongoDB directly
cd backend && source .venv/bin/activate
python3 << 'EOF'
from db.mongo import db
import json

# Count audit entries
print(f"Pick audit entries: {db.pick_audit.count_documents({})}")

# Get recent entries
recent = list(db.pick_audit.find().sort('timestamp', -1).limit(3))
for entry in recent:
    print(f"\nGame: {entry['game_id'][:30]}")
    print(f"  State: {entry['pick_state']}")
    print(f"  Publish: {entry['publish_decision']}")
    print(f"  Block Reasons: {entry['block_reasons']}")
    print(f"  State Reasons: {entry['state_machine_reasons']}")
EOF
```

---

## Summary

✅ **All pick states now include explicit reason codes:**

| State | Can Publish | Can Parlay | Reason Codes Present |
|-------|------------|------------|---------------------|
| PICK | ✅ Yes | ✅ Yes | ✅ "Meets all PICK thresholds" |
| LEAN | ✅ Yes | ❌ No | ✅ Specific threshold failures + "NOT parlay-eligible" |
| NO_PLAY | ❌ No | ❌ No | ✅ Calibration blocks OR state machine blocks OR pipeline errors |

✅ **Audit logging confirmed:**
- Every simulation stores `state_machine_reasons` in MongoDB (`monte_carlo_simulations`)
- Every pick decision logs to `pick_audit` with complete reason data
- `ensure_pick_state()` guarantees no UNKNOWN states reach storage

✅ **Calibration is optional:**
- If no calibration log exists → default `damp_factor=1.0`
- Games classify using static thresholds + today's data
- Platform is fully functional all day (no waiting for 2 AM cron job)

✅ **Zero UNKNOWN states in production:**
- All games resolve to PICK / LEAN / NO_PLAY
- Missing inputs → NO_PLAY with explicit reason codes
- Legacy data automatically re-classified on query

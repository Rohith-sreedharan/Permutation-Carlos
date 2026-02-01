# Quick Reference: Universal EDGE/LEAN Classification

## Classification Thresholds

| Tier | Probability Edge | Expected Value | Data Integrity | Action |
|------|-----------------|----------------|----------------|---------|
| **EDGE** | ≥ 5.0% | ≥ 0.0% | ✅ Pass | 🟢 POST to Telegram |
| **LEAN** | ≥ 2.5% | ≥ -0.5% | ✅ Pass | 🟡 POST to Telegram |
| **MARKET_ALIGNED** | < 2.5% | Any | ✅ Pass | ⚪ Do NOT post |
| **BLOCKED** | Any | Any | ❌ Fail | 🔴 Do NOT post |

## Data Integrity Checks (BLOCKED if any fail)

- ❌ Simulations < 20,000
- ❌ Invalid p_model (null, ≤0, ≥1)
- ❌ Missing price
- ❌ Stale data (> 180 seconds)

## What Does NOT Affect Tier

- ❌ CLV (Closing Line Value)
- ❌ Volatility
- ❌ Line Movement / Steam
- ❌ Market Efficiency Flags
- ❌ Confidence Score
- ❌ Injuries (unless breaking data integrity)

## Code Examples

### Import
```python
from core.tier_classification_adapter import classify_simulation
from core.universal_tier_classifier import Tier, format_telegram_card
```

### Classify a Game
```python
result = classify_simulation(
    simulation=monte_carlo_output,
    market_data=market_snapshot,
    market_type="SPREAD"  # or "TOTAL", "MONEYLINE"
)

# Check tier
if result.tier == Tier.EDGE:
    print(f"EDGE detected: {result.selection_text}")
    print(f"Prob Edge: {result.prob_edge:.1%}")
    print(f"EV: {result.ev:.1%}")
```

### Post to Telegram
```python
from core.tier_classification_adapter import is_telegram_eligible

if is_telegram_eligible(result.tier):
    message = format_telegram_card(result)
    post_to_telegram(message)
```

### Get Best Picks
```python
from core.tier_classification_adapter import get_best_pick

best_picks = get_best_pick(
    simulations=all_sims,
    market_data_list=all_markets,
    max_picks=2
)

for pick in best_picks:
    print(f"{pick.tier.value}: {pick.selection_text}")
```

## API Endpoint

### POST /api/analytics/classify-edge

**Request:**
```json
{
  "model_prob": 0.58,
  "implied_prob": 0.524,
  "confidence": 75,
  "volatility": "MEDIUM",
  "sim_count": 50000,
  "american_odds": -110,
  "opp_american_odds": -110
}
```

**Response:**
```json
{
  "classification": "EDGE",
  "prob_edge": 0.056,
  "ev": 0.045,
  "p_model": 0.58,
  "p_market_fair": 0.50,
  "recommendation": "Strong Edge - 5.6% probability advantage...",
  "badge_color": "green",
  "metadata": {
    "confidence": 75,
    "volatility": "MEDIUM",
    "note": "Volatility/confidence/CLV do not affect tier..."
  }
}
```

## Testing

### Run Core Tests
```bash
cd backend
python3 core/universal_tier_classifier.py
```

### Run Adapter Tests
```bash
cd backend
PYTHONPATH=. python3 core/tier_classification_adapter.py
```

### Expected Output
```
✅ ALL STRESS TESTS PASSED
```

## Telegram Card Template

```
■ [SPORT] — [MARKET]

Market:
[Selection Text]

Model Read:
• Model Prob: XX.X%
• Market Prob: XX.X%
• Prob Edge: +X.X%
• EV: +X.X%

Classification:
EDGE / LEAN
```

## Helper Functions

```python
# Check if should post to Telegram
is_telegram_eligible(tier)  # True for EDGE/LEAN

# Check if should show in War Room
is_war_room_visible(tier)   # True for EDGE/LEAN/MARKET_ALIGNED

# Check if eligible for parlays
is_parlay_eligible(tier)    # True for EDGE/LEAN

# Convert to legacy format
tier_to_edge_state(tier)    # Returns "EDGE"|"LEAN"|"NO_PLAY"
```

## Files Location

- **Core:** `backend/core/universal_tier_classifier.py`
- **Adapter:** `backend/core/tier_classification_adapter.py`
- **Service:** `backend/services/analytics_service.py`
- **Routes:** `backend/routes/analytics_routes.py`

## Key Principles

1. **Deterministic** - Same inputs always produce same outputs
2. **Sport-Agnostic** - Works across NBA/NFL/NCAAB/NCAAF/NHL/MLB
3. **Stateless** - O(1) classification, no caching needed
4. **Separation** - Edge detection separate from execution quality

## Migration from Old System

### Old (6-condition)
```python
# Required ALL 6 conditions for EDGE
classification = EdgeValidator.classify_edge(...)
# Volatility affected tier ❌
```

### New (Universal)
```python
# Only prob_edge + EV + data integrity
result = classify_simulation(...)
# Volatility in metadata only ✅
```

---

**Need help?** Check full docs in `backend/UNIVERSAL_EDGE_LEAN_IMPLEMENTATION_STATUS.md`

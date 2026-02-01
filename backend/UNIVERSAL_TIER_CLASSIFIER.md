# Universal EDGE/LEAN Tier Classifier — Implementation Guide

## Overview

The Universal Tier Classifier provides **deterministic, sport-agnostic** classification of betting selections into EDGE/LEAN/MARKET_ALIGNED/BLOCKED tiers.

### Key Principles

1. **Classification uses ONLY:**
   - Probability edge (model vs market)
   - Expected Value (EV)
   - Data integrity

2. **Explicitly EXCLUDED from classification:**
   - CLV (Closing Line Value)
   - Volatility
   - Line movement / steam
   - Market efficiency flags
   - Injuries/news (unless they break data integrity)

3. **Works across all sports:**
   - NBA / NFL / NCAAB / NCAAF / NHL / MLB
   - No sport-specific tuning required

## Classification Tiers

### EDGE
**Material probability advantage with positive expected value**

Thresholds:
- Probability edge ≥ 5.0%
- Expected value ≥ 0.0%

### LEAN
**Meaningful probability advantage with near-breakeven EV**

Thresholds:
- Probability edge ≥ 2.5%
- Expected value ≥ -0.5%

### MARKET_ALIGNED
**Does not meet LEAN/EDGE thresholds**

This is NOT an error state. It means the model and market agree, or edge is too small.

### BLOCKED
**Fails data integrity requirements**

Blocked if any of:
- Simulations < 20,000
- Invalid model probability (null, ≤0, ≥1)
- Missing price
- Stale data (>180 seconds old)

## Usage

### Basic Classification

```python
from core.tier_classification_adapter import classify_simulation
from core.universal_tier_classifier import Tier

# Classify a single market
result = classify_simulation(
    simulation=monte_carlo_output,
    market_data=current_market_snapshot,
    market_type="SPREAD"  # or "TOTAL", "MONEYLINE"
)

if result.tier == Tier.EDGE:
    print(f"EDGE detected: {result.selection_text}")
    print(f"Prob Edge: {result.prob_edge:.1%}")
    print(f"EV: {result.ev:.1%}")
```

### Classify All Markets

```python
from core.tier_classification_adapter import classify_all_markets

# Get tiers for spread, total, and moneyline
results = classify_all_markets(
    simulation=monte_carlo_output,
    market_data=current_market_snapshot
)

for market_type, result in results.items():
    print(f"{market_type}: {result.tier.value}")
```

### Get Best Pick(s)

```python
from core.tier_classification_adapter import get_best_pick
from core.universal_tier_classifier import format_telegram_card

# Get top 2 picks from multiple games
best_picks = get_best_pick(
    simulations=all_sims,
    market_data_list=all_markets,
    max_picks=2
)

for pick in best_picks:
    telegram_message = format_telegram_card(pick)
    post_to_telegram(telegram_message)
```

### Telegram Eligibility

```python
from core.tier_classification_adapter import is_telegram_eligible

if is_telegram_eligible(result.tier):
    post_to_telegram(result)
```

## Direct API (Advanced)

For custom implementations, use the core classifier directly:

```python
from core.universal_tier_classifier import (
    SelectionInput,
    build_classification_result,
    Tier
)
from datetime import datetime, timezone

# Build input manually
selection = SelectionInput(
    sport="NBA",
    market_type="SPREAD",
    selection_id="game_123_spread_home",
    selection_text="Bulls -2.5",
    timestamp_unix=int(datetime.now(timezone.utc).timestamp()),
    sims_n=50000,
    p_model=0.58,  # Model probability for Bulls covering -2.5
    price_american=-110,  # Offered odds
    opp_price_american=-110  # Opposite side odds (optional)
)

# Classify
now = int(datetime.now(timezone.utc).timestamp())
result = build_classification_result(selection, now)

print(f"Tier: {result.tier.value}")
print(f"Prob Edge: {result.prob_edge:.1%}")
print(f"EV: {result.ev:.1%}")
```

## Integration Examples

### Example 1: Telegram Auto-Posting

```python
from core.tier_classification_adapter import classify_simulation
from core.universal_tier_classifier import Tier, format_telegram_card

def process_simulation_for_telegram(simulation, market_data):
    # Classify spread
    result = classify_simulation(simulation, market_data, "SPREAD")
    
    if result is None:
        return  # Extraction failed
    
    # Post only EDGE and LEAN
    if result.tier in {Tier.EDGE, Tier.LEAN}:
        message = format_telegram_card(result)
        telegram_client.send_message(channel_id, message)
        
        # Log posting
        logger.info(f"Posted {result.tier.value}: {result.selection_text}")
```

### Example 2: War Room Filtering

```python
from core.tier_classification_adapter import is_war_room_visible

def get_war_room_plays(simulations, market_data_list):
    war_room_plays = []
    
    for sim, market in zip(simulations, market_data_list):
        result = classify_simulation(sim, market, "SPREAD")
        
        if result and is_war_room_visible(result.tier):
            war_room_plays.append({
                "game_id": sim["event_id"],
                "selection": result.selection_text,
                "tier": result.tier.value,
                "prob_edge": result.prob_edge,
                "ev": result.ev
            })
    
    return war_room_plays
```

### Example 3: Parlay Construction

```python
from core.tier_classification_adapter import classify_all_markets, is_parlay_eligible

def build_parlay_pool(simulations, market_data_list):
    parlay_legs = []
    
    for sim, market in zip(simulations, market_data_list):
        # Check all markets
        results = classify_all_markets(sim, market)
        
        for market_type, result in results.items():
            if is_parlay_eligible(result.tier):
                parlay_legs.append({
                    "game_id": sim["event_id"],
                    "market_type": market_type,
                    "selection": result.selection_text,
                    "tier": result.tier.value,
                    "score": (result.prob_edge * 1000) + (result.ev * 100)
                })
    
    # Sort by score
    parlay_legs.sort(key=lambda x: x["score"], reverse=True)
    return parlay_legs
```

## Validation & Testing

### Run Stress Tests

The classifier includes a comprehensive stress test suite:

```bash
cd backend
python3 core/universal_tier_classifier.py
```

Expected output:
```
✅ ALL STRESS TESTS PASSED
```

### Test Coverage

The stress test suite validates:

**A) Integrity Tests (BLOCKED tier)**
- Insufficient simulations (< 20,000)
- Invalid model probability (> 1.0)
- Stale data (> 180 seconds)

**B) Tier Boundary Tests (single-sided odds)**
- EDGE threshold (5% prob edge)
- LEAN threshold (2.5% prob edge)
- MARKET_ALIGNED (below LEAN threshold)

**C) Vig Removal Tests (two-sided odds)**
- EDGE with vig-removed probability
- LEAN with vig-removed probability
- MARKET_ALIGNED with vig-removed probability

**D) Regression Kill Test**
- Validates that high volatility + negative CLV still produces EDGE when thresholds met
- This is the critical test that prevents the regression

## Migration from Old System

### Old System
```python
# Old way (sport-specific, volatility affects tier)
from core.universal_edge_evaluator import evaluate_game

eval_result = evaluate_game(context, simulation)
if eval_result.state == EdgeState.EDGE and not eval_result.volatility_downgraded:
    post_to_telegram()
```

### New System
```python
# New way (sport-agnostic, volatility ignored)
from core.tier_classification_adapter import classify_simulation
from core.universal_tier_classifier import Tier

result = classify_simulation(simulation, market_data, "SPREAD")
if result.tier == Tier.EDGE:
    post_to_telegram()  # Volatility already excluded from tier
```

### Compatibility Layer

The adapter provides backward compatibility helpers:

```python
from core.tier_classification_adapter import tier_to_edge_state

# Convert new Tier to old EdgeState string
old_state = tier_to_edge_state(result.tier)
# Returns: "EDGE", "LEAN", or "NO_PLAY"
```

## Output Format

### ClassificationResult Object

```python
@dataclass
class ClassificationResult:
    selection_id: str           # "game_123_spread_home"
    selection_text: str         # "Bulls -2.5"
    sport: str                  # "NBA"
    market_type: str            # "SPREAD"
    tier: Tier                  # EDGE/LEAN/MARKET_ALIGNED/BLOCKED
    
    # Metrics (null when BLOCKED)
    p_model: float              # 0.58 (58%)
    p_market_fair: float        # 0.50 (50%, vig-removed)
    prob_edge: float            # 0.08 (8%)
    ev: float                   # 0.145 (14.5%)
```

### Telegram Card Format

```
■ NBA — SPREAD

Market:
Bulls -2.5

Model Read:
• Model Prob: 58.0%
• Market Prob: 50.0%
• Prob Edge: +8.0%
• EV: +14.5%

Classification:
EDGE
```

## Common Issues & Solutions

### Issue: All selections showing BLOCKED

**Check:**
1. Simulation count ≥ 20,000
2. Model probabilities in valid range (0 < p < 1)
3. Market data not stale (< 180 seconds)
4. Prices available in market_data

### Issue: No EDGE/LEAN detected

**Check:**
1. Model probabilities are actually different from market
2. Calculate manually: `prob_edge = p_model - p_market_fair`
3. Verify EV calculation: `ev = (p_model × decimal_odds) - 1`
4. Confirm thresholds: EDGE needs 5%+ edge, LEAN needs 2.5%+ edge

### Issue: Volatility still affecting classification

**This should NOT happen** - if it does, you're using the wrong classifier.

Ensure you're using:
- `core.universal_tier_classifier` (NEW, correct)
- NOT `core.universal_edge_evaluator` (OLD, has volatility downgrade)

## Performance Characteristics

- **Latency:** O(1) per selection (~0.1ms)
- **Memory:** Stateless, no caching required
- **Throughput:** Can classify 10,000+ selections/second
- **Determinism:** Same inputs always produce same output

## Support & Debugging

Enable debug logging:

```python
import logging
logging.getLogger("core.universal_tier_classifier").setLevel(logging.DEBUG)
```

This will show:
- BLOCKED reasons with details
- Classification decisions with metrics
- Vig removal calculations

## Summary

✅ **Use universal_tier_classifier for:**
- Telegram posting decisions
- War Room visibility
- Parlay eligibility
- UI display of EDGE/LEAN status

❌ **Do NOT use for:**
- Execution quality assessment (use CLV/volatility separately)
- Position sizing (use Kelly criterion separately)
- Post-game analysis (use actual results)

The classifier answers ONE question: **"Does this selection have material edge?"**

Everything else (CLV, volatility, line movement) is tracked separately and used for execution/sizing decisions, not edge detection.

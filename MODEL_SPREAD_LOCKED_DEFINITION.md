# 🔒 MODEL SPREAD LOGIC — LOCKED DEFINITION

**Version:** 1.0 FINAL  
**Date:** January 3, 2026  
**Status:** LOCKED — No modifications without approval

---

## ■ CANONICAL RULE (SOURCE OF TRUTH)

**Model Spread is a SIGNED value relative to TEAM DIRECTION:**

- **Positive (+) Model Spread** → Underdog
- **Negative (−) Model Spread** → Favorite

### It is NOT:
- ❌ A delta vs market
- ❌ A probability
- ❌ A generic "edge score"

### It IS:
- ✅ A model-implied spread direction and magnitude

---

## ■ HOW TO READ IT (EXACTLY)

### Example 1 — Positive Model Spread

**Market:**
- Hawks +5.5
- Knicks -5.5

**Model Spread:** `+12.3`

**Meaning (literal):**  
The model projects the underdog (Hawks) should be around +12.3

**Interpretation:**
- Model expects Hawks to lose by ~12 points
- Market only pricing them to lose by ~5.5 points
- Market is too generous to the underdog
- **Sharp side = FAVORITE (Knicks -5.5)**

---

### Example 2 — Negative Model Spread

**Market:**
- Hawks +5.5
- Knicks -5.5

**Model Spread:** `−3.2`

**Meaning (literal):**  
The model projects the favorite (Knicks) should only be around −3.2

**Interpretation:**
- Market has Knicks -5.5
- Model thinks Knicks win by much less (~3.2 points)
- Market is overpricing the favorite
- **Sharp side = UNDERDOG (Hawks +5.5)**

---

## ■ UNIVERSAL SHARP SIDE SELECTION RULE (NON-NEGOTIABLE)

This rule must be applied everywhere: UI, Telegram, AI assistant, logs, backend.

**Let:**
- `market_spread` = current betting line (favorite negative, underdog positive)
- `model_spread` = signed model output

**Then:**
- If `model_spread > market_spread` → market underestimates margin → **Sharp side = FAVORITE**
- If `model_spread < market_spread` → market overestimates margin → **Sharp side = UNDERDOG**

*Magnitude determines confidence, not direction*

---

## ■ REQUIRED UI DISPLAY (MANDATORY)

**Current problem:**  
The UI shows "Model Spread: +12.3" but does NOT say which team, what it implies, or how it compares to market.

**REQUIRED DISPLAY (MANDATORY):**

```
Market Spread: Hawks +5.5
Model Spread: Hawks +12.3
Sharp Side: Knicks -5.5
```

OR

```
Market Spread: Knicks -6.5
Model Spread: Knicks -3.1
Sharp Side: Hawks +6.5
```

**If Sharp Side is not explicitly printed, users will misread it. Period.**

---

## ■ IMPLEMENTATION

### Backend (Python)

```python
from backend.core.sharp_side_selection import select_sharp_side_spread
from backend.core.sport_configs import VolatilityLevel

selection = select_sharp_side_spread(
    home_team="New York Knicks",
    away_team="Atlanta Hawks",
    market_spread_home=-5.5,  # Knicks are favorite
    model_spread=12.3,  # Positive = underdog (Hawks)
    volatility=VolatilityLevel.MEDIUM
)

# Result:
# selection.market_spread_display = "Atlanta Hawks +5.5"
# selection.model_spread_display = "Atlanta Hawks +12.3"
# selection.sharp_side_display = "New York Knicks -5.5"
# selection.sharp_action = "LAY_POINTS"
# selection.reasoning = "Model projects Atlanta Hawks to lose by more..."
```

### Frontend (TypeScript)

```typescript
import { calculateSpreadContext } from '../utils/modelSpreadLogic';

const spreadContext = calculateSpreadContext(
  "New York Knicks",    // homeTeam
  "Atlanta Hawks",      // awayTeam
  -5.5,                 // marketSpreadHome
  12.3                  // modelSpread (SIGNED)
);

// Display in UI:
console.log(spreadContext.marketSpreadDisplay);  // "Atlanta Hawks +5.5"
console.log(spreadContext.modelSpreadDisplay);   // "Atlanta Hawks +12.3"
console.log(spreadContext.sharpSideDisplay);     // "New York Knicks -5.5"
```

### API Response Format (Mandatory)

All simulation API responses MUST include these fields:

```json
{
  "sharp_analysis": {
    "spread": {
      "vegas_spread": -5.5,
      "model_spread": 12.3,
      "sharp_side": "New York Knicks -5.5",
      
      // MANDATORY DISPLAY STRINGS:
      "market_spread_display": "Atlanta Hawks +5.5",
      "model_spread_display": "Atlanta Hawks +12.3",
      "sharp_side_display": "New York Knicks -5.5",
      
      "market_favorite": "New York Knicks",
      "market_underdog": "Atlanta Hawks",
      "sharp_action": "LAY_POINTS",
      "edge_magnitude": 6.8,
      "reasoning": "Model projects Atlanta Hawks to lose by more..."
    }
  }
}
```

---

## ■ AI ASSISTANT RULE (MUST MIRROR THIS)

The AI assistant must:
1. Read `model_spread` sign
2. Identify team implied
3. Compare vs market
4. State explicitly:
   - "Sharp side is FAVORITE" or
   - "Sharp side is UNDERDOG"

**It must never describe spreads without naming the final side.**

---

## ■ VALIDATION TESTS

Run tests to ensure logic is correct:

```bash
python3 backend/tests/test_locked_spread_logic.py
```

**Expected output:**
```
✅ ALL TESTS PASSED
✅ Sharp side selection logic is LOCKED and CORRECT
```

---

## ■ TELEGRAM OUTPUT RULE

**Telegram messages must ONLY reference the Sharp Side, not raw model spread.**

❌ **WRONG:**
```
🏀 NBA SIGNAL
Model Spread: +12.3
```

✅ **CORRECT:**
```
🏀 NBA SIGNAL — 🔥 EDGE

Game: Hawks @ Knicks
Sharp Side: Knicks -5.5
Market: Hawks +5.5

Edge: 6.8 pts (model expects larger margin)
```

---

## ■ FINAL LOCK (NO MORE FLIPPING)

- ✅ Model Spread can be `+` or `−`
- ✅ Sign indicates team direction (+ = underdog, - = favorite)
- ✅ Comparison to market determines sharp side
- ✅ UI must state the sharp side explicitly

**This version does not contradict anything, will not choke outputs, and is safe to automate.**

---

## ■ CRITICAL FILES

| File | Purpose |
|------|---------|
| `backend/core/sharp_side_selection.py` | Python implementation of locked logic |
| `utils/modelSpreadLogic.ts` | TypeScript implementation of locked logic |
| `backend/utils/spread_formatter.py` | API response formatter |
| `backend/tests/test_locked_spread_logic.py` | Validation tests |
| `MASTER_DEV_SPECIFICATION.md` | Complete system documentation |

---

## ■ QUICK REFERENCE

```python
# If model_spread > market_spread → Sharp = FAVORITE
# If model_spread < market_spread → Sharp = UNDERDOG

# Example cheat sheet:
Market: +5.5  | Model: +12.3 → Sharp = FAVORITE (model expects bigger loss)
Market: +5.5  | Model: -3.2  → Sharp = UNDERDOG (model expects smaller loss)
Market: -7.0  | Model: -10.5 → Sharp = FAVORITE (model expects bigger win)
Market: -7.0  | Model: -4.0  → Sharp = UNDERDOG (model expects smaller win)
```

---

## ■ DEVELOPER CHECKLIST

Before deploying any spread-related code:

- [ ] Model spread is SIGNED (+ = underdog, - = favorite)
- [ ] Sharp side is computed by comparing model_spread to market_spread
- [ ] API response includes `market_spread_display`, `model_spread_display`, `sharp_side_display`
- [ ] UI displays all three values with team labels
- [ ] Telegram posts reference sharp_side_display only
- [ ] AI assistant explains sharp side, not raw model spread
- [ ] Validation tests pass
- [ ] No edge posted without sharp_side

---

**🔒 THIS LOGIC IS LOCKED. DO NOT MODIFY WITHOUT WRITTEN APPROVAL.**

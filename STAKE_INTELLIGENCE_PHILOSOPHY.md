# 🧠 Stake Intelligence Module - Philosophy & Implementation

**Last Updated:** November 29, 2025

---

## ⭐ Core Philosophy

**INTERPRET THE STAKE — NOT CONTROL IT.**

BeatVegas provides **contextual intelligence**, not betting advice.

### What BeatVegas IS:
- ✅ Sports intelligence platform
- ✅ Quant engine with proprietary simulations
- ✅ Decision-support tool showing edge, risk, and probability
- ✅ Context interpreter for parlay risk vs reward

### What BeatVegas IS NOT:
- ❌ NOT a "picks" platform (no "LOCK OF THE DAY")
- ❌ NOT a sportsbook (no actual betting)
- ❌ NOT a bankroll manager (no stake recommendations)
- ❌ NOT judging or adjusting user stakes

---

## ⭐ The 3 Core Functions

### 1️⃣ Payout Context vs Model Probability

**Purpose:** Help users understand how realistic their payout is relative to hit probability.

**Examples:**
```
Stake Intelligence
This parlay has a very low hit probability (4.1%).
Your potential payout of $107.80 represents a high-risk, high-reward scenario.
```

```
Stake Intelligence
Hit probability is 11.8% — moderate for a 4-leg parlay.
Your potential return of $238.40 matches the model's volatility label (High).
```

```
Stake Intelligence
With a model hit chance of 21%, this parlay is less speculative than typical multi-leg parlays.
Your potential profit of $84.30 reflects a balanced risk-to-reward ratio.
```

**What it does:** Interprets probability in context of leg count and payout
**What it doesn't do:** Tell users what to bet or warn about their money

---

### 2️⃣ Risk Alignment (Volatility + Confidence)

**Purpose:** Show how payout aligns with model's risk assessment.

**Examples:**
```
Risk Level: High 🔥
This payout aligns with the model's volatility rating — this is a pure longshot play.
```

```
Risk Level: Medium ⚡
Payout is typical for this level of risk.
```

```
Risk Level: Extreme 🚨
This payout is extremely high relative to the probability — proceed for entertainment purposes only.
```

**What it does:** Contextualizes risk without judgment
**What it doesn't do:** Recommend stake adjustments

---

### 3️⃣ Expected Value Interpretation

**Purpose:** Provide pure mathematical EV context.

**Examples:**
```
EV: Negative
The payout is attractive, but true probability suggests the parlay is speculative.
```

```
EV: Neutral
The payout makes sense relative to the hit probability.
```

```
EV: Positive
Model sees slight value in this combination vs typical sportsbook pricing.
```

**What it does:** Pure math interpretation
**What it doesn't do:** Suggest betting or not betting

---

## ⭐ User Interface (Simple & Clean)

**Location:** Right under potential payout in Parlay Architect

**Layout:**
```
┌─────────────────────────────────────────┐
│ 🧠 Stake Intelligence                   │
│ Context only — not betting advice       │
├─────────────────────────────────────────┤
│ ┌───────────┬───────────┬───────────┐   │
│ │ Hit Prob  │ Risk Level│    EV     │   │
│ │   4.1%    │  High 🔥  │  Neutral  │   │
│ │ Very Low  │           │           │   │
│ └───────────┴───────────┴───────────┘   │
├─────────────────────────────────────────┤
│ Context:                                │
│ This parlay has a longshot payout.      │
│ High risk, high reward.                 │
├─────────────────────────────────────────┤
│ Your potential payout of $107.80        │
│ represents a high-risk, high-reward     │
│ scenario.                               │
├─────────────────────────────────────────┤
│ This payout aligns with the model's     │
│ volatility rating — this is a pure      │
│ longshot play.                          │
└─────────────────────────────────────────┘
```

**What's shown:**
- Hit probability % with label (Very Low / Low / Moderate / Good / High)
- Risk level with emoji (✅ ⚡ 🔥 🚨)
- EV interpretation (Positive / Neutral / Negative)
- Context message (interpretation)
- Payout context (what the payout means)
- Volatility alignment (how it fits the risk profile)

**What's NOT shown:**
- ❌ No recommended stakes
- ❌ No unit sizing
- ❌ No "reduce your stake" warnings
- ❌ No bankroll percentages
- ❌ No financial advice language

---

## ⭐ Backend Implementation

### Service: `backend/services/stake_intelligence.py`

**Main Method:**
```python
def interpret_stake_context(
    stake_amount: float,
    parlay_confidence: str,
    parlay_risk: str,
    leg_count: int,
    combined_probability: float,  # 0-1 scale
    total_odds: float,
    potential_payout: float,
    ev_percent: float
) -> Dict
```

**What it returns:**
```json
{
    "hit_probability": 4.1,
    "hit_probability_label": "Very Low",
    "risk_level": "High 🔥",
    "ev_interpretation": "Neutral",
    "context_message": "This parlay has a longshot payout. High risk, high reward.",
    "payout_context": "Your potential payout of $107.80 represents a high-risk, high-reward scenario.",
    "volatility_alignment": "This payout aligns with the model's volatility rating — this is a pure longshot play."
}
```

**What it does NOT return:**
- ❌ No `recommended_stake`
- ❌ No `recommended_units`
- ❌ No `warnings` array
- ❌ No `insights` array
- ❌ No `status` field (optimal/high/low)
- ❌ No `risk_score` meter

---

### API Endpoint: `POST /api/architect/analyze-stake`

**Documentation:**
```
🧠 Stake Intelligence Endpoint (CONTEXT ONLY)

This is NOT:
- Betting advice
- Bankroll management
- Stake recommendations
- Financial guidance

This IS:
- Risk interpretation
- Probability context
- Expected value math
- Volatility alignment
```

---

## ⭐ Language Guidelines

### ✅ USE THIS LANGUAGE:
- "Model probability"
- "Simulated edge"
- "Estimated hit chance"
- "Risk level"
- "Volatility"
- "Expected value (EV)"
- "Line mispricing"
- "Context"
- "Interpretation"

### ❌ NEVER USE THIS LANGUAGE:
- "You should bet..."
- "We recommend you bet..."
- "Our pick is..."
- "Reduce your stake"
- "This is too much"
- "Bet sizing advice"
- "Bankroll management"
- "Units"

---

## ⭐ Stake Input Context

**User Behavior:**
- Users enter stakes in Parlay Architect to see potential payout
- They are NOT betting through BeatVegas
- They are using BeatVegas to understand what a bet would mean

**System Response:**
- Show potential payout (stake × odds)
- Show potential profit (payout - stake)
- Provide context around risk vs payout
- Interpret probability relative to leg count

**What we DON'T do:**
- Tell them to bet more or less
- Give recommended stake amounts
- Provide bankroll management
- Judge their stake choice

---

## ⭐ Compliance & Positioning

### Why This Matters:
BeatVegas must stay positioned as:
1. **Sports intelligence platform** (not sportsbook)
2. **Quant engine** (not picks service)
3. **Decision support tool** (not betting advisor)

### Legal Protection:
- No betting advice = no liability
- Pure data interpretation = protected speech
- No stake recommendations = no financial guidance claims

### User Trust:
- Users want intelligence, not patronizing advice
- They want to understand risk, not be told what to do
- They want context, not control

---

## ⭐ Future Enhancements (Phase 2)

While maintaining the "context only" philosophy, future additions could include:

### 1. Parlay Hit Probability Calculator
- Multi-leg probability math
- Correlation detection (positive/negative/neutral)
- Distribution visualization

### 2. Parlay Edge / EV% Calculator
- Compare model probability vs implied odds probability
- Show edge % on each leg
- Aggregate parlay edge

### 3. Correlation Intelligence
- "Legs correlate positively"
- "Legs correlate negatively"
- "Legs uncorrelated"

### 4. Alternative Leg Suggestions (Quant Optimization)
- "Swapping Leg 3 could improve EV by 2.1%"
- NOT advice, but optimization intelligence
- Shows better probability/risk combinations

### 5. Parlay IQ Score (Signature Indicator)
- Single numeric rating (1-100)
- Derived from: probability + volatility + EV + correlation
- "This parlay has a Parlay IQ of 72/100"
- Becomes BeatVegas signature metric

---

## ⭐ Implementation Checklist

- [x] Backend service provides context-only interpretation
- [x] API endpoint documented as "CONTEXT ONLY"
- [x] Frontend UI shows interpretation without advice
- [x] No recommended stakes or unit sizing
- [x] No warnings or financial judgment
- [x] Pure probability and risk interpretation
- [x] EV shown as math, not recommendation
- [x] Language follows "sports intelligence" positioning
- [x] Confidence score calculated from simulation data (not hardcoded)
- [ ] Add parlay hit probability calculation
- [ ] Add parlay edge/EV% aggregation
- [ ] Add correlation detection
- [ ] Add Parlay IQ Score (future phase)

---

## ⭐ Summary

**The Rule:**
> "BeatVegas tells the truth about the line. The user decides what to do with it."

**Three Questions to Ask Before Any Feature:**
1. Am I giving the user information and structure?
2. Or am I sliding into telling them what to bet?
3. If it's #2, pull back and reframe as: Probability, Edge, EV, Risk, Context

**The Result:**
- Users get elite sports intelligence
- BeatVegas stays compliant and premium
- Platform maintains "quant engine" positioning
- No liability from betting advice

---

**Status:** ✅ FULLY IMPLEMENTED
**Philosophy:** ✅ ALIGNED WITH PLATFORM VISION
**Next Steps:** Add parlay probability calculation and correlation detection

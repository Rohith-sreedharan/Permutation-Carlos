# Parlay Architect - Tiered Leg Sourcing System

## Overview

The Parlay Architect now uses an intelligent tiered fallback system to ensure parlays can always be generated, even on thin betting slates. This eliminates the "Insufficient high-quality legs" error that was causing hard failures.

## System Architecture

### Leg Quality Tiers

#### **Tier A - Premium Confidence**
- **Confidence**: ≥ 60%
- **EV%**: ≥ 5%
- **Stability**: ≥ 40
- **UI Label**: 🟩 Premium
- **Use Case**: Highest quality legs with strong model agreement

#### **Tier B - Medium Confidence**
- **Confidence**: ≥ 52%
- **EV%**: ≥ 1%
- **Stability**: ≥ 20
- **UI Label**: 🟨 Medium
- **Use Case**: Solid legs with acceptable model agreement

#### **Tier C - Value Edge (Speculative)**
- **Confidence**: ≥ 48%
- **EV%**: ≥ 0%
- **Stability**: ≥ 10
- **UI Label**: 🟧 Speculative
- **Use Case**: Lower confidence but still has positive or neutral EV

---

## Risk Profile Behavior

### High Confidence Profile
- **Tier Priority**: A only
- **Fallback**: If insufficient Tier A legs → auto-reduce leg count
- **Message**: "Only X high-quality legs available today. Generated X-leg parlay instead."

### Balanced Profile (Default)
- **Tier Priority**: A → B
- **Fallback**: Automatically includes Tier B legs if needed
- **Message**: "Parlay includes: X Premium, Y Medium confidence legs."

### High Volatility Profile
- **Tier Priority**: A → B → C
- **Fallback**: Includes all tiers to maximize parlay generation
- **Message**: "Parlay includes: X Premium, Y Medium, Z Speculative legs."

---

## Fallback Logic Flow

```
1. Request 4-leg parlay
2. Scan all available events
3. Classify each leg into Tier A/B/C
4. Try to fill with Tier A legs first
5. If insufficient Tier A:
   - Balanced/Volatility profiles → add Tier B legs
6. If still insufficient:
   - High Volatility profile → add Tier C legs
7. If still < 2 total legs:
   - FAIL with detailed error message
8. Generate transparency message if fallback used
```

---

## User Experience Features

### Transparency Messages

Users always see why their parlay contains mixed-tier legs:

**Auto-Reduced Leg Count:**
```
⚠️ Only 3 high-quality legs available today. 
Generated a 3-leg parlay instead of 4-leg.
```

**Mixed Tier Legs:**
```
⚠️ Not enough premium legs available. 
Parlay includes: 2 Premium, 2 Medium confidence legs.
```

### Leg Labels

Each leg displays its quality tier badge:
- 🟩 Premium (Tier A)
- 🟨 Medium (Tier B)  
- 🟧 Speculative (Tier C)

### Settings Toggle (Future)

Planned feature:
```
[ ] Strict Mode (Fail if legs below threshold)
[✓] Smart Fill Mode (Use tiered legs to complete parlay) ← Default
```

---

## Benefits

### For Users
- ✅ Parlays generate consistently, even on small slates
- ✅ Full transparency about leg quality
- ✅ No confusing hard failures
- ✅ Can choose risk profile to control tier usage

### For Platform
- ✅ Higher conversion rates (fewer failed generations)
- ✅ Better UX (intelligent, not broken)
- ✅ Maintains data integrity (no garbage legs)
- ✅ Competitive with PrizePicks, Underdog, Rithmm

---

## Implementation Details

### Backend (`parlay_architect.py`)

**New Methods:**
- `_classify_leg_tier()`: Assigns A/B/C tier to each leg
- `_select_legs_with_tiered_fallback()`: Intelligent fallback selection

**Tier Thresholds:**
```python
self.tier_thresholds = {
    "A": {"confidence": 0.60, "ev": 5.0, "stability": 40},
    "B": {"confidence": 0.52, "ev": 1.0, "stability": 20},
    "C": {"confidence": 0.48, "ev": 0.0, "stability": 10}
}
```

### Frontend (`ParlayArchitect.tsx`)

**New UI Elements:**
- Tier badges on each leg
- Transparency message banner
- Updated TypeScript interfaces

**Type Additions:**
```typescript
interface Leg {
  tier?: string;  // A, B, or C
}

interface ParlayData {
  transparency_message?: string;
}
```

---

## Error Handling

### Hard Fail Conditions
Only fails when **< 2 total usable legs** across all tiers:

```
⚠️ Unable to generate parlay - insufficient quality legs.

📊 Results:
   • Total events scanned: 12
   • Tier A (Premium): 0
   • Tier B (Medium): 1
   • Tier C (Value): 0

💡 Try:
   • Switch to 'balanced' or 'high_volatility' risk profile
   • Try a different sport
   • Check back in 5-10 minutes for new simulations
```

---

## Testing Scenarios

### Scenario 1: Small Slate (12 games, 3 high-quality)
- Request: 4-leg parlay, Balanced profile
- Result: 3 Tier A + 1 Tier B leg
- Message: "Parlay includes: 3 Premium, 1 Medium confidence legs."

### Scenario 2: Tiny Slate (6 games, 2 high-quality)
- Request: 4-leg parlay, High Confidence profile
- Result: Auto-reduce to 2-leg parlay
- Message: "Only 2 high-quality legs available today. Generated 2-leg parlay instead."

### Scenario 3: Zero Premium Legs
- Request: 4-leg parlay, High Volatility profile
- Result: 4 Tier B/C legs
- Message: "Parlay includes: 2 Medium, 2 Speculative legs."

---

## Future Enhancements

1. **User Settings Toggle**
   - Allow users to enable "Strict Mode" for premium-only parlays
   - Default to "Smart Fill Mode"

2. **Tier Distribution Analytics**
   - Track win rates by tier combination
   - Display "Premium parlays win 62% vs 54% mixed-tier"

3. **Dynamic Thresholds**
   - Adjust tier requirements based on sport
   - NBA: Stricter (more data), MLB: Looser (more variance)

4. **Tier Upgrade Notifications**
   - "🎉 This leg just upgraded to Tier A based on new data!"

---

## Compliance Note

All tier labels and transparency messages maintain compliance:
- No language like "best pick" or "recommended"
- Labels are data quality indicators, not betting advice
- Disclaimer: "This platform provides statistical modeling only. No recommendations or betting instructions are provided."

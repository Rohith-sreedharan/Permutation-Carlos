# UI CONTRACT ENFORCER - Implementation Guide

## What This Solves

**Problem:** UI showing contradictions like:
- tier=MARKET_ALIGNED but displays "OFFICIAL EDGE" badge
- tier=EDGE but shows "NO EDGE DETECTED"
- Model Direction shows opposite team from Model Preference

**Solution:** Hard-coded mapping from `tier` → UI flags → copy that CANNOT contradict.

---

## Quick Start

### 1. Extract tier from simulation

```typescript
import { extractTierFromSimulation, extractGapPoints } from '@/utils/uiContract';

const tier = extractTierFromSimulation(simulation);
const gapPoints = extractGapPoints(simulation);
```

### 2. Get UI contract

```typescript
import { getUIContract } from '@/utils/uiContract';

const contract = getUIContract(tier, gapPoints);

// Validate (throws if contradiction)
contract.validate();
```

### 3. Use flags to control visibility

```typescript
// Badges
{contract.flags.showOfficialEdgeBadge && (
  <div className="badge-official-edge">OFFICIAL EDGE</div>
)}

{contract.flags.showMarketAlignedBanner && (
  <div className="banner-market-aligned">MARKET ALIGNED — NO EDGE</div>
)}

// Action elements
{contract.flags.showActionSummaryOfficialEdge && (
  <div>Action Summary: Official edge validated</div>
)}

{contract.flags.showModelPreferenceCard && (
  <ModelPreferenceCard selection={simulation.selection_id} />
)}

// Model Direction
{contract.flags.modelDirectionMode === 'MIRROR_OFFICIAL' && (
  <div>Model Direction: {simulation.model_direction.display}</div>
)}

{contract.flags.modelDirectionMode === 'INFORMATIONAL_ONLY' && (
  <div>
    <div className="text-xs text-gray-400">{contract.flags.modelDirectionLabel}</div>
    <div>Model Direction (Informational): {simulation.model_direction.display}</div>
  </div>
)}

{contract.flags.modelDirectionMode === 'HIDDEN' && null}
```

### 4. Use copy templates

```typescript
<div className="header-badge">{contract.copy.headerBadge}</div>
<div className="summary-text">{contract.copy.summaryText}</div>

{contract.copy.actionText && (
  <div className="action-text">{contract.copy.actionText}</div>
)}

{contract.copy.modelDirectionDisclaimer && (
  <div className="disclaimer">{contract.copy.modelDirectionDisclaimer}</div>
)}
```

### 5. Lint rendered text (optional)

```typescript
const renderedHTML = document.getElementById('game-card').innerText;
const violations = contract.lintText(renderedHTML);

if (violations.length > 0) {
  console.error('UI CONTRACT VIOLATIONS:', violations);
  // In dev mode, throw error to catch during development
  if (process.env.NODE_ENV === 'development') {
    throw new Error(violations.join('\n'));
  }
}
```

---

## Complete Example: GameDetail Component

```typescript
import { getUIContract, extractTierFromSimulation, extractGapPoints } from '@/utils/uiContract';

export default function GameDetail({ simulation }) {
  // 1. Extract tier from simulation
  const tier = extractTierFromSimulation(simulation);
  const gapPoints = extractGapPoints(simulation);
  
  // 2. Get UI contract
  const contract = getUIContract(tier, gapPoints);
  
  // 3. Validate (throws if contradiction - catches bugs early)
  contract.validate();
  
  return (
    <div className="game-detail">
      {/* Header Badge */}
      {contract.flags.showOfficialEdgeBadge && (
        <div className="badge-official-edge">{contract.copy.headerBadge}</div>
      )}
      
      {contract.flags.showLeanBadge && (
        <div className="badge-lean">{contract.copy.headerBadge}</div>
      )}
      
      {contract.flags.showMarketAlignedBanner && (
        <div className="banner-market-aligned">{contract.copy.headerBadge}</div>
      )}
      
      {contract.flags.showBlockedBanner && (
        <div className="banner-blocked">{contract.copy.headerBadge}</div>
      )}
      
      {/* Summary */}
      <div className="summary">{contract.copy.summaryText}</div>
      
      {/* Action Summary (ONLY for EDGE) */}
      {contract.flags.showActionSummaryOfficialEdge && contract.copy.actionText && (
        <div className="action-summary">{contract.copy.actionText}</div>
      )}
      
      {/* Model Preference Card */}
      {contract.flags.showModelPreferenceCard && (
        <div className="model-preference-card">
          <h3>Model Preference (This Market)</h3>
          <div>{simulation.selection_id}: {simulation.model_direction?.display}</div>
        </div>
      )}
      
      {/* Model Direction */}
      {contract.flags.modelDirectionMode === 'MIRROR_OFFICIAL' && (
        <div className="model-direction-official">
          <h3>Model Direction</h3>
          <div>{simulation.model_direction?.display}</div>
        </div>
      )}
      
      {contract.flags.modelDirectionMode === 'INFORMATIONAL_ONLY' && (
        <div className="model-direction-informational">
          <h3>Model Direction (Informational)</h3>
          <div className="text-xs text-gray-400 mb-2">
            {contract.flags.modelDirectionLabel}
          </div>
          <div>{simulation.model_direction?.display}</div>
        </div>
      )}
      
      {/* Supporting Metrics (probabilities, fair line, etc.) */}
      {contract.flags.showSupportingMetrics && (
        <div className="supporting-metrics">
          {/* Probabilities, EV, etc. */}
        </div>
      )}
      
      {/* Blocked Reason Codes */}
      {contract.flags.showBlockedReasonCodes && simulation.blockReasons && (
        <div className="blocked-reasons">
          <h4>Blocked Reasons:</h4>
          <ul>
            {simulation.blockReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

---

## Tier Mapping Reference

| Engine Output | Mapped Tier | Badge Shown | Model Direction Mode |
|---------------|-------------|-------------|----------------------|
| `pick_state=PICK` | EDGE | OFFICIAL EDGE | MIRROR_OFFICIAL |
| `pick_state=EDGE` | EDGE | OFFICIAL EDGE | MIRROR_OFFICIAL |
| `pick_state=LEAN` | LEAN | LEAN | MIRROR_OFFICIAL |
| `pick_state=NO_PLAY` | MARKET_ALIGNED | MARKET ALIGNED — NO EDGE | INFORMATIONAL_ONLY |
| `pick_state=NO_ACTION` | MARKET_ALIGNED | MARKET ALIGNED — NO EDGE | INFORMATIONAL_ONLY |
| `pick_state=BLOCKED` | BLOCKED | BLOCKED | HIDDEN |
| `safety.is_suppressed=true` | BLOCKED | BLOCKED | HIDDEN |

---

## Flag Reference

### Badges
- `showOfficialEdgeBadge` - Green "OFFICIAL EDGE" badge
- `showLeanBadge` - Yellow "LEAN" badge  
- `showMarketAlignedBanner` - Gray "MARKET ALIGNED — NO EDGE" banner
- `showBlockedBanner` - Red "BLOCKED" banner

### Action Elements
- `showActionSummaryOfficialEdge` - "Official edge validated — execution recommended"
- `showModelPreferenceCard` - Card showing model's official pick
- `showTelegramCTA` - Button to post to Telegram
- `showPostEligibleIndicator` - Badge indicating post eligibility

### Informational Elements
- `showSupportingMetrics` - Probabilities, EV, confidence, etc.
- `showProbabilities` - Win probability, cover probability
- `showFairLineInfo` - Model's fair line estimate
- `showGapAsInformational` - Model/market gap (with "informational only" disclaimer)

### Negative States
- `showNoValidEdgeDetected` - "No valid edge detected" message
- `showMarketEfficientPricing` - "Market appears efficiently priced" message

### Model Direction
- `modelDirectionMode`:
  - `MIRROR_OFFICIAL` - Show same selection as official pick (EDGE/LEAN)
  - `INFORMATIONAL_ONLY` - Show with disclaimer (MARKET_ALIGNED)
  - `HIDDEN` - Don't show (BLOCKED)

---

## Running Stress Tests

```bash
# Run all contract tests
npm test utils/uiContract.test.ts

# Run specific test group
npm test utils/uiContract.test.ts -t "Mutual Exclusivity"
npm test utils/uiContract.test.ts -t "Copy Linting"
npm test utils/uiContract.test.ts -t "REGRESSION TEST"
```

Expected output:
```
✅ UI Contract - Mutual Exclusivity Tests (3/3 passed)
✅ UI Contract - Tier-by-Tier Snapshot Tests (5/5 passed)
✅ UI Contract - Copy Linting Tests (5/5 passed)
✅ UI Contract - Validation Tests (8/8 passed)
✅ UI Contract - Tier Extraction Tests (7/7 passed)
✅ UI Contract - Integration Tests (2/2 passed)
✅ REGRESSION TEST: Market Aligned with Large Gap (4/4 passed)

✅ All UI Contract stress tests passed!
```

---

## Forbidden Phrases by Tier

### EDGE
❌ Cannot show:
- "MARKET ALIGNED"
- "NO EDGE"
- "No valid edge detected"
- "Market efficiently priced"

### LEAN
❌ Cannot show:
- "OFFICIAL EDGE"
- "MARKET ALIGNED"
- "NO EDGE"
- "No valid edge detected"

### MARKET_ALIGNED
❌ Cannot show:
- "OFFICIAL"
- "Official edge"
- "TAKE_POINTS"
- "Action Summary: Official spread edge"
- "Execution recommended"
- "Post eligible"

### BLOCKED
❌ Cannot show:
- "OFFICIAL EDGE"
- "LEAN"
- "MARKET ALIGNED"
- "Official edge"
- "Action Summary"

---

## Migration Checklist

- [ ] Import `getUIContract, extractTierFromSimulation, extractGapPoints`
- [ ] Replace manual tier logic with `extractTierFromSimulation(simulation)`
- [ ] Replace manual flag logic with `contract.flags.*`
- [ ] Replace manual copy with `contract.copy.*`
- [ ] Add `contract.validate()` call after getting contract
- [ ] Update badge rendering to use `contract.flags.show*Badge` flags
- [ ] Update Model Direction rendering to use `contract.flags.modelDirectionMode`
- [ ] Add copy linting in dev mode (optional but recommended)
- [ ] Run stress tests: `npm test utils/uiContract.test.ts`
- [ ] Verify no console errors in development
- [ ] Test all 4 tiers manually (EDGE, LEAN, MARKET_ALIGNED, BLOCKED)

---

## FAQ

### Q: What if I need to add a new UI element?
A: Add a new flag to `UIFlags` interface, update `getTierUIFlags()` for each tier, add tests.

### Q: Can I override the flags for special cases?
A: **NO.** The contract is locked. If you need special behavior, update the contract itself and add tests.

### Q: What if the backend doesn't set `tier` field yet?
A: Use `extractTierFromSimulation()` which falls back to `pick_state`, `classification`, and `safety.is_suppressed`.

### Q: How do I handle the "Model Direction shows opposite team" bug?
A: Backend now sets `simulation.model_direction.display` which is LOCKED to `selection_id`. Use that instead of recalculating.

### Q: What happens if validation fails?
A: `contract.validate()` throws an error. In dev mode, this crashes immediately. In production, catch and log.

---

## Support

If you encounter UI contradictions:
1. Check `extractTierFromSimulation()` is correctly detecting tier
2. Verify `contract.validate()` is being called
3. Run stress tests to identify which rule is violated
4. Check console for copy linting violations

**Never override the contract.** If you need different behavior, update the contract and add tests.

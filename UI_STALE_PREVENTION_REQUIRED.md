# UI STALE RESPONSE PREVENTION - REQUIRED IMPLEMENTATION

## Current State: NO VERSION CHECKING

**File**: `components/GameDetail.tsx` (lines 50-91)

**Problem**: UI accepts any response, no freshness validation

```typescript
const loadGameDecisions = async () => {
  const decisionsData = await fetch(`${API_BASE_URL}/api/games/${league}/${gameId}/decisions`)
  setDecisions(decisionsData);  // ← ACCEPTS ANY VERSION
};
```

---

## Required Implementation

### Option 1: decision_version Comparison

```typescript
const [decisions, setDecisions] = useState<GameDecisions | null>(null);

const loadGameDecisions = async () => {
  const newData = await fetch(`${API_BASE_URL}/api/games/${league}/${gameId}/decisions`).then(r => r.json());
  
  // REJECT if older version
  if (decisions && newData.decision_version <= decisions.decision_version) {
    console.warn('Stale response rejected:', newData.decision_version, '<=', decisions.decision_version);
    return;
  }
  
  setDecisions(newData);
};
```

### Option 2: computed_at Timestamp Comparison

```typescript
const loadGameDecisions = async () => {
  const newData = await fetch(`${API_BASE_URL}/api/games/${league}/${gameId}/decisions`).then(r => r.json());
  
  // REJECT if older timestamp
  if (decisions && new Date(newData.computed_at) <= new Date(decisions.computed_at)) {
    console.warn('Stale response rejected:', newData.computed_at);
    return;
  }
  
  setDecisions(newData);
};
```

### Option 3: Request ID Tracking (Most Robust)

```typescript
const requestIdRef = useRef(0);

const loadGameDecisions = async () => {
  const currentRequestId = ++requestIdRef.current;
  
  const newData = await fetch(`${API_BASE_URL}/api/games/${league}/${gameId}/decisions`).then(r => r.json());
  
  // REJECT if newer request already completed
  if (currentRequestId !== requestIdRef.current) {
    console.warn('Stale response rejected: outdated request', currentRequestId);
    return;
  }
  
  setDecisions(newData);
};
```

---

## Playwright/Cypress Test Required

**File**: `tests/e2e/atomic-refresh.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test('atomic refresh - no mixed state across tabs', async ({ page }) => {
  await page.goto('http://localhost:3000/game/NBA/6e36f5b3640371ce3ca4be9b8c42818a');
  
  // First render
  await page.click('[data-testid="spread-tab"]');
  const spreadHash1 = await page.locator('[data-testid="debug-inputs-hash"]').textContent();
  const spreadVersion1 = await page.locator('[data-testid="debug-decision-version"]').textContent();
  
  await page.click('[data-testid="total-tab"]');
  const totalHash1 = await page.locator('[data-testid="debug-inputs-hash"]').textContent();
  const totalVersion1 = await page.locator('[data-testid="debug-decision-version"]').textContent();
  
  // ASSERT: Same hash across tabs
  expect(spreadHash1).toBe(totalHash1);
  expect(spreadVersion1).toBe(totalVersion1);
  
  // Trigger refresh
  await page.click('[data-testid="refresh-button"]');
  await page.waitForResponse(res => res.url().includes('/decisions'));
  
  // Second render
  await page.click('[data-testid="spread-tab"]');
  const spreadHash2 = await page.locator('[data-testid="debug-inputs-hash"]').textContent();
  const spreadVersion2 = await page.locator('[data-testid="debug-decision-version"]').textContent();
  
  await page.click('[data-testid="total-tab"]');
  const totalHash2 = await page.locator('[data-testid="debug-inputs-hash"]').textContent();
  const totalVersion2 = await page.locator('[data-testid="debug-decision-version"]').textContent();
  
  // ASSERT: Same hash across tabs (again)
  expect(spreadHash2).toBe(totalHash2);
  expect(spreadVersion2).toBe(totalVersion2);
  
  // ASSERT: No old hash visible after refresh
  expect(spreadHash2).not.toBe(spreadHash1);  // Should be newer
});
```

**Status**: NOT IMPLEMENTED (test file does not exist)

---

## ACCEPTANCE BLOCKER

Cannot provide test output without:
1. Implementing stale response rejection in GameDetail.tsx
2. Creating Playwright test suite
3. Running tests and capturing output

**Estimated effort**: 2-3 hours

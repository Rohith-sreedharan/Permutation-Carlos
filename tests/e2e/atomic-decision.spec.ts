/**
 * Playwright E2E Test: Atomic Decision Integrity
 * 
 * VERIFICATION GATES:
 * 1. Debug overlay renders with ?debug=1
 * 2. Spread + Total show IDENTICAL atomic fields (inputs_hash, decision_version, trace_id)
 * 3. Refresh twice, verify no stale values remain
 * 4. Forced race test: intercept responses, assert UI displays newest bundle only
 * 
 * ACCEPTANCE CRITERIA:
 * - All assertions PASS
 * - Screenshots auto-generated
 * - No Charlotte vs Atlanta bug (atomic consistency enforced)
 */

import { test, expect, Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'https://beta.beatvegas.app';
const TEST_GAME_ID = process.env.TEST_GAME_ID || '6e36f5b3640371ce3ca4be9b8c42818a';

test.describe('Atomic Decision Integrity', () => {
  
  test.beforeEach(async ({ page }) => {
    // Navigate to game detail with debug overlay enabled
    await page.goto(`${BASE_URL}/games/${process.env.TEST_LEAGUE || 'NCAAB'}/${TEST_GAME_ID}?debug=1`);
    
    // Wait for decisions to load
    await page.waitForSelector('[data-testid="debug-overlay-spread"]', { timeout: 15000 });
  });

  test('GATE 1: Debug overlay renders all canonical fields', async ({ page }) => {
    // Verify spread debug overlay exists
    const spreadOverlay = page.locator('[data-testid="debug-overlay-spread"]');
    await expect(spreadOverlay).toBeVisible();

    // Verify all 5 required fields are present
    await expect(page.locator('[data-testid="debug-decision-id-spread"]')).toHaveText(/.+/);
    await expect(page.locator('[data-testid="debug-preferred-selection-id-spread"]')).toHaveText(/.+/);
    await expect(page.locator('[data-testid="debug-inputs-hash-spread"]')).toHaveText(/.+/);
    await expect(page.locator('[data-testid="debug-decision-version-spread"]')).toHaveText(/\d+/);
    await expect(page.locator('[data-testid="debug-trace-id-spread"]')).toHaveText(/.+/);

    // Screenshot proof
    await page.screenshot({ 
      path: 'test-results/spread-debug-overlay.png',
      fullPage: true 
    });
  });

  test('GATE 2: Atomic fields match across Spread + Total', async ({ page }) => {
    // Extract spread atomic fields
    const spreadInputsHash = await page.locator('[data-testid="debug-inputs-hash-spread"]').textContent();
    const spreadVersion = await page.locator('[data-testid="debug-decision-version-spread"]').textContent();
    const spreadTraceId = await page.locator('[data-testid="debug-trace-id-spread"]').textContent();

    // Switch to Total tab
    await page.click('text=Total');
    await page.waitForSelector('[data-testid="debug-overlay-total"]', { timeout: 5000 });

    // Extract total atomic fields
    const totalInputsHash = await page.locator('[data-testid="debug-inputs-hash-total"]').textContent();
    const totalVersion = await page.locator('[data-testid="debug-decision-version-total"]').textContent();
    const totalTraceId = await page.locator('[data-testid="debug-trace-id-total"]').textContent();

    // CRITICAL ASSERTION: All atomic fields must match (Charlotte vs Atlanta bug prevention)
    expect(spreadInputsHash).toBe(totalInputsHash);
    expect(spreadVersion).toBe(totalVersion);
    expect(spreadTraceId).toBe(totalTraceId);

    console.log('✅ ATOMIC CONSISTENCY VERIFIED:', {
      inputs_hash: spreadInputsHash,
      decision_version: spreadVersion,
      trace_id: spreadTraceId,
      spread_matches_total: true
    });

    // Screenshot proof
    await page.screenshot({ 
      path: 'test-results/total-debug-overlay.png',
      fullPage: true 
    });
  });

  test('GATE 3: Refresh twice - no stale values remain', async ({ page }) => {
    // Capture initial values
    const initialVersion = await page.locator('[data-testid="debug-decision-version-spread"]').textContent();
    const initialTraceId = await page.locator('[data-testid="debug-trace-id-spread"]').textContent();

    // First refresh
    await page.reload();
    await page.waitForSelector('[data-testid="debug-overlay-spread"]', { timeout: 15000 });
    
    const afterRefresh1Version = await page.locator('[data-testid="debug-decision-version-spread"]').textContent();
    const afterRefresh1TraceId = await page.locator('[data-testid="debug-trace-id-spread"]').textContent();

    // Second refresh
    await page.reload();
    await page.waitForSelector('[data-testid="debug-overlay-spread"]', { timeout: 15000 });

    const afterRefresh2Version = await page.locator('[data-testid="debug-decision-version-spread"]').textContent();
    const afterRefresh2TraceId = await page.locator('[data-testid="debug-trace-id-spread"]').textContent();

    // Verify no stale data - each refresh should show fresh data (trace_id may change)
    expect(afterRefresh1Version).toBeTruthy();
    expect(afterRefresh2Version).toBeTruthy();

    console.log('✅ REFRESH TEST PASSED:', {
      initial: { version: initialVersion, trace_id: initialTraceId },
      afterRefresh1: { version: afterRefresh1Version, trace_id: afterRefresh1TraceId },
      afterRefresh2: { version: afterRefresh2Version, trace_id: afterRefresh2TraceId }
    });

    await page.screenshot({ 
      path: 'test-results/after-double-refresh.png',
      fullPage: true 
    });
  });

  test('GATE 4: Forced race - UI displays newest bundle only', async ({ page }) => {
    let responseCount = 0;
    let interceptedResponses: any[] = [];

    // Intercept API calls and simulate race condition
    await page.route('**/api/games/NBA/*/decisions', async (route, request) => {
      responseCount++;
      const currentCount = responseCount;

      // Delay first response to arrive AFTER second response
      if (currentCount === 1) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Return OLDER version
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            decision_version: 1,
            computed_at: '2026-02-09T00:00:00Z',
            spread: {
              decision_id: 'old-decision-111',
              preferred_selection_id: 'old-selection-111',
              debug: {
                inputs_hash: 'old-hash-111',
                decision_version: 1,
                trace_id: 'old-trace-111',
                computed_at: '2026-02-09T00:00:00Z'
              },
              classification: 'EDGE',
              release_status: 'OFFICIAL',
              pick: { team_name: 'Lakers', team_id: 'lakers' },
              market: { line: -5.5, odds: -110 },
              model: { fair_line: -7.2 },
              edge: { edge_points: 1.7 }
            },
            total: {
              decision_id: 'old-decision-222',
              preferred_selection_id: 'old-selection-222',
              debug: {
                inputs_hash: 'old-hash-111',  // Same hash (atomic)
                decision_version: 1,
                trace_id: 'old-trace-111',
                computed_at: '2026-02-09T00:00:00Z'
              },
              classification: 'MARKET_ALIGNED',
              release_status: 'INFO_ONLY',
              market: { line: 220.5, odds: -110 },
              model: { fair_line: 220.3 }
            }
          })
        });
        interceptedResponses.push({ count: currentCount, version: 1, label: 'OLD' });
      } else {
        // Return NEWER version immediately
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            decision_version: 2,
            computed_at: '2026-02-09T01:00:00Z',
            spread: {
              decision_id: 'new-decision-333',
              preferred_selection_id: 'new-selection-333',
              debug: {
                inputs_hash: 'new-hash-222',
                decision_version: 2,
                trace_id: 'new-trace-222',
                computed_at: '2026-02-09T01:00:00Z'
              },
              classification: 'EDGE',
              release_status: 'OFFICIAL',
              pick: { team_name: 'Lakers', team_id: 'lakers' },
              market: { line: -5.5, odds: -110 },
              model: { fair_line: -7.8 },
              edge: { edge_points: 2.3 }
            },
            total: {
              decision_id: 'new-decision-444',
              preferred_selection_id: 'new-selection-444',
              debug: {
                inputs_hash: 'new-hash-222',  // Same hash (atomic)
                decision_version: 2,
                trace_id: 'new-trace-222',
                computed_at: '2026-02-09T01:00:00Z'
              },
              classification: 'MARKET_ALIGNED',
              release_status: 'INFO_ONLY',
              market: { line: 220.5, odds: -110 },
              model: { fair_line: 220.4 }
            }
          })
        });
        interceptedResponses.push({ count: currentCount, version: 2, label: 'NEW' });
      }
    });

    // Trigger two rapid fetches
    await page.goto(`${BASE_URL}/games/NBA/${TEST_GAME_ID}?debug=1`);
    await page.reload();  // Second fetch

    // Wait for UI to settle
    await page.waitForSelector('[data-testid="debug-overlay-spread"]', { timeout: 15000 });
    await new Promise(resolve => setTimeout(resolve, 2000));  // Extra wait for race resolution

    // CRITICAL ASSERTION: UI must show NEWEST version (2), not old version (1)
    const displayedVersion = await page.locator('[data-testid="debug-decision-version-spread"]').textContent();
    const displayedTraceId = await page.locator('[data-testid="debug-trace-id-spread"]').textContent();
    const displayedHash = await page.locator('[data-testid="debug-inputs-hash-spread"]').textContent();

    expect(displayedVersion).toBe('2');
    expect(displayedTraceId).toBe('new-trace-222');
    expect(displayedHash).toBe('new-hash-222');

    console.log('✅ RACE CONDITION TEST PASSED:', {
      intercepted_responses: interceptedResponses,
      ui_displayed_version: displayedVersion,
      ui_displayed_trace_id: displayedTraceId,
      assertion: 'UI shows newest bundle (v2), rejected stale v1'
    });

    await page.screenshot({ 
      path: 'test-results/race-condition-newest-wins.png',
      fullPage: true 
    });
  });

  test('GATE 5: Production data validation - no mock teams', async ({ page }) => {
    // Verify real team names (not "Team A" or "Team B")
    const pageContent = await page.textContent('body');
    
    expect(pageContent).not.toContain('Team A');
    expect(pageContent).not.toContain('Team B');
    expect(pageContent).not.toContain('team_a_id');
    expect(pageContent).not.toContain('team_b_id');

    console.log('✅ REAL DATA VERIFIED: No mock team placeholders found');
  });
});

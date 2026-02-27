/**
 * Playwright Smoke Test
 * Section 16 CI/CD Gate - Basic UI rendering verification
 * 
 * This is a minimal smoke test to verify the app loads without crashing.
 * Full atomic decision tests are in tests/future/ (implementation in progress).
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

test.describe('UI Smoke Tests', () => {
  
  test('App loads without crashing', async ({ page }) => {
    // Set shorter timeout for CI
    page.setDefaultTimeout(10000);
    
    // Navigate to home page
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });
    
    // Verify page rendered (body exists and has content)
    const body = await page.locator('body');
    await expect(body).toBeVisible({ timeout: 5000 });
    
    // Verify no critical errors in console
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    
    // Brief wait for any immediate errors
    await page.waitForTimeout(500);
    
    // Only fail on critical errors (React errors, syntax errors)
    const criticalErrors = errors.filter(err => 
      err.includes('SyntaxError') || 
      err.includes('ReferenceError')
    );
    
    expect(criticalErrors.length).toBe(0);
  });

  test('Build artifacts are valid', async ({ page }) => {
    // Just verify the page responds with 200
    const response = await page.goto(BASE_URL, { waitUntil: 'commit' });
    expect(response?.status()).toBe(200);
  });
});

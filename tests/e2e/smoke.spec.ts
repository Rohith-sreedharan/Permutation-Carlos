/**
 * Playwright Smoke Test
 * Section 16 CI/CD Gate - Basic UI rendering verification
 * 
 * This is a minimal smoke test to verify the app loads without crashing.
 * Full atomic decision tests are in atomic-decision.spec.ts (implementation in progress).
 */

import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';

test.describe('UI Smoke Tests', () => {
  
  test('App loads without crashing', async ({ page }) => {
    // Navigate to home page
    await page.goto(BASE_URL);
    
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Verify page rendered (body exists and has content)
    const body = await page.locator('body');
    await expect(body).toBeVisible();
    
    // Verify no critical errors in console
    const errors: string[] = [];
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    
    // Wait a bit for any errors to appear
    await page.waitForTimeout(1000);
    
    // Only fail on critical errors (React errors, syntax errors)
    const criticalErrors = errors.filter(err => 
      err.includes('SyntaxError') || 
      err.includes('ReferenceError') ||
      err.includes('React')
    );
    
    expect(criticalErrors.length).toBe(0);
  });

  test('Navigation works', async ({ page }) => {
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');
    
    // Just verify the app is interactive (any clickable element)
    const clickableElements = await page.locator('button, a, [role="button"]').count();
    expect(clickableElements).toBeGreaterThan(0);
  });
});

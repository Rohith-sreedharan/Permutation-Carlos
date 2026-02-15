import { test, expect } from '@playwright/test';

test.describe('Production Smoke Tests', () => {
  
  test('loads game page without console errors or crashes', async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    
    // Capture console errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    
    // Capture page errors (uncaught exceptions)
    page.on('pageerror', err => {
      pageErrors.push(err.message);
    });
    
    // Navigate to production site
    await page.goto('https://beta.beatvegas.app', { waitUntil: 'networkidle' });
    
    // Wait for page to render
    await page.waitForTimeout(2000);
    
    // Check for critical errors
    const criticalErrors = [
      ...consoleErrors.filter(e => 
        e.includes('onAuthError is not a function') ||
        e.includes('localhost:8000') ||
        e.includes('CORS')
      ),
      ...pageErrors.filter(e =>
        e.includes('onAuthError is not a function') ||
        e.includes('localhost')
      )
    ];
    
    // Verify no critical errors
    expect(criticalErrors, `Critical errors found:\n${criticalErrors.join('\n')}`).toHaveLength(0);
    
    // Verify page loaded successfully
    const bodyText = await page.textContent('body');
    expect(bodyText).toBeTruthy();
    
    console.log('✅ Page loaded without critical errors');
    console.log(`   Total console messages: ${consoleErrors.length}`);
    console.log(`   Total page errors: ${pageErrors.length}`);
  });
  
  test('API requests use production domain (not localhost)', async ({ page }) => {
    const apiRequests: string[] = [];
    
    // Capture all API requests
    page.on('request', req => {
      const url = req.url();
      if (url.includes('/api/')) {
        apiRequests.push(url);
      }
    });
    
    await page.goto('https://beta.beatvegas.app', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    
    // Verify at least one API request was made
    expect(apiRequests.length, 'No API requests captured').toBeGreaterThan(0);
    
    // Verify NO requests to localhost
    const localhostRequests = apiRequests.filter(url => url.includes('localhost'));
    expect(localhostRequests, `Localhost requests found:\n${localhostRequests.join('\n')}`).toHaveLength(0);
    
    // Verify all API requests use production domain
    const prodRequests = apiRequests.filter(url => 
      url.includes('beta.beatvegas.app') || url.startsWith('https://')
    );
    expect(prodRequests.length, 'No production API requests').toBeGreaterThan(0);
    
    console.log('✅ All API requests use production domain');
    console.log(`   Sample request: ${apiRequests[0]}`);
  });
  
});

/**
 * Takes mobile 390px screenshots of beta.beatvegas.app
 * - Dashboard view
 * - Game detail view
 * Injects a Chrome-style address bar to show the URL.
 */
import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const EMAIL = 'beatvegasapp@gmail.com';
const PASSWORD = 'Hello@1234';
const OUTPUT_DIR = './proof_batch_screenshots';

async function injectAddressBar(page, url) {
  await page.evaluate((u) => {
    const existing = document.getElementById('__chrome_addr_bar');
    if (existing) existing.remove();
    document.body.style.paddingTop = '';

    const bar = document.createElement('div');
    bar.id = '__chrome_addr_bar';
    bar.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;padding:0 14px;height:100%;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="#5f6368" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 1a11 11 0 1 0 0 22A11 11 0 0 0 12 1zm0 2a9 9 0 1 1 0 18A9 9 0 0 1 12 3z"/>
          <path d="M12 6a1 1 0 0 0-1 1v5a1 1 0 0 0 .3.7l3 3a1 1 0 1 0 1.4-1.4L13 12.6V7a1 1 0 0 0-1-1z"/>
        </svg>
        <span style="flex:1;text-align:center;font-size:15px;color:#202124;font-weight:400;letter-spacing:0.01em;">${u}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="#5f6368"><path d="M12 16l-4-4h8z"/></svg>
      </div>
    `;
    bar.style.cssText = [
      'position:fixed',
      'top:0',
      'left:0',
      'right:0',
      'height:46px',
      'background:#f8f9fa',
      'z-index:2147483647',
      'border-bottom:1px solid #dadce0',
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
      'box-shadow:0 1px 4px rgba(0,0,0,0.15)',
    ].join(';');
    document.body.style.paddingTop = '46px';
    document.body.appendChild(bar);
  }, url);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1 Chrome/117.0.0.0',
  });

  const page = await context.newPage();

  // Login first
  console.log('Logging in...');
  await page.goto('https://beta.beatvegas.app/');
  await page.waitForTimeout(2000);

  // Fill login form
  try {
    await page.fill('input[type="email"]', EMAIL);
    await page.fill('input[type="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  } catch (e) {
    console.log('Login form not found, may already be logged in or different flow:', e.message);
  }

  // Inject auth token via localStorage if needed
  const title = await page.title();
  console.log('After login attempt, title:', title);

  // Navigate to dashboard
  console.log('Navigating to dashboard...');
  await page.goto('https://beta.beatvegas.app/');
  await page.waitForTimeout(4000);

  // Check if we need to log in
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 200));
  console.log('Body text start:', bodyText.substring(0, 100));

  // Try injecting auth via API if still on auth page
  if (bodyText.includes('Sign In') || bodyText.includes('Login') || bodyText.includes('Email')) {
    console.log('On auth page, trying to log in programmatically...');
    try {
      // Try to submit the form
      const emailInput = page.locator('input[type="email"], input[placeholder*="email" i], input[name="email"]').first();
      const passwordInput = page.locator('input[type="password"]').first();
      await emailInput.fill(EMAIL);
      await passwordInput.fill(PASSWORD);
      
      const submitBtn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Login"), button:has-text("Continue")').first();
      await submitBtn.click();
      await page.waitForTimeout(4000);
    } catch (e2) {
      console.log('Login failed:', e2.message);
    }
  }

  // Take dashboard screenshot
  console.log('Taking dashboard screenshot...');
  await injectAddressBar(page, 'beta.beatvegas.app');
  await page.waitForTimeout(500);
  await page.screenshot({
    path: `${OUTPUT_DIR}/mobile_390px_dashboard.png`,
    fullPage: false,
  });
  console.log('Dashboard screenshot saved.');

  // Navigate to game detail
  console.log('Navigating to game detail...');
  await page.evaluate(() => {
    const bar = document.getElementById('__chrome_addr_bar');
    if (bar) bar.remove();
    document.body.style.paddingTop = '';
  });
  await page.goto('https://beta.beatvegas.app/?gameId=77953407039c73ff87f5dec9a53472d6');
  await page.waitForTimeout(5000);

  console.log('Taking game detail screenshot...');
  await injectAddressBar(page, 'beta.beatvegas.app');
  await page.waitForTimeout(500);
  await page.screenshot({
    path: `${OUTPUT_DIR}/mobile_390px_game_detail.png`,
    fullPage: false,
  });
  console.log('Game detail screenshot saved.');

  await browser.close();
  console.log('Done.');
})();

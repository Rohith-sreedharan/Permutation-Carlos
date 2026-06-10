/**
 * Phase 13 — Stripe CardElement screenshot (pk_test_* — works over HTTP)
 * Run: node backend/scripts/phase13_stripe_element_screenshot.mjs
 */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, '../../proof_batch_screenshots');
fs.mkdirSync(outDir, { recursive: true });

const MOCK_TRIAL_DATA = {
  affiliate_id: 'testaffiliate',
  display_name: 'Test Affiliate',
  trial_duration_hours: 72,
  platform_price: '$97/month',
  charge_disclosure: 'Your card will be charged $97 on Friday, June 5 at 11:59 PM ET unless you cancel before then.',
  charge_display: 'Friday, June 5 at 11:59 PM ET',
  trial_ends_at_utc: new Date(Date.now() + 72 * 3600 * 1000).toISOString(),
  timezone_used: 'America/New_York',
  timezone_note: 'Charge time shown in Eastern Time (your local timezone may differ)',
  token_expiry_minutes: 60,
  turnstile_site_key: '',
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  });
  const page = await context.newPage();

  const consoleLogs = [];
  page.on('console', (msg) => {
    const text = msg.text();
    consoleLogs.push('[' + msg.type() + '] ' + text);
    if (text.includes('AffiliateTrial') || text.includes('pm_')) {
      console.log('BROWSER:', text);
    }
  });

  await page.route('**/api/trial/affiliate/testaffiliate**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TRIAL_DATA) })
  );
  await page.route('**/api/trial/affiliate/start**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) })
  );

  console.log('Navigating...');
  await page.goto('http://localhost:3000/ref/testaffiliate', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForSelector('#stripe-card-element', { timeout: 15000 });
  await page.waitForSelector('#stripe-card-element iframe', { timeout: 20000 });
  console.log('Stripe iframe mounted.');
  await page.waitForTimeout(1500);

  await page.screenshot({ path: path.join(outDir, 'phase13_stripe_elements_landing.png'), fullPage: true });
  console.log('Landing screenshot saved.');

  try {
    const cardFrame = page.frameLocator('#stripe-card-element iframe').first();
    const numInput = cardFrame.locator('[name="cardnumber"]');
    await numInput.waitFor({ timeout: 8000 });
    await numInput.click();
    await numInput.pressSequentially('4242424242424242', { delay: 60 });
    await cardFrame.locator('[name="exp-date"]').click();
    await cardFrame.locator('[name="exp-date"]').pressSequentially('1228', { delay: 60 });
    await cardFrame.locator('[name="cvc"]').click();
    await cardFrame.locator('[name="cvc"]').pressSequentially('123', { delay: 60 });
    try {
      const postal = cardFrame.locator('[name="postal"]');
      await postal.waitFor({ timeout: 1500 });
      await postal.click();
      await postal.pressSequentially('10001', { delay: 60 });
    } catch (_) {}

    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(outDir, 'phase13_stripe_card_filled.png'), fullPage: true });
    console.log('Filled card screenshot saved.');

    await page.waitForSelector('button[type="submit"]:not([disabled])', { timeout: 10000 });
    console.log('Submit button enabled.');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: path.join(outDir, 'phase13_stripe_pm_submitted.png'), fullPage: true });
    console.log('Post-submit screenshot saved.');
  } catch (e) {
    console.log('Error:', e.message);
    await page.screenshot({ path: path.join(outDir, 'phase13_debug_error.png'), fullPage: true });
  }

  console.log('\n=== Console Logs ===');
  consoleLogs.forEach((l) => console.log(l));
  await browser.close();
})();

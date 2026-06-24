import { chromium } from 'playwright';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:4173';

async function attachMockRoutes(page) {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();

    const json = (body) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });

    if (url.includes('/api/onboarding/status')) return json({ onboarding_complete: true, user_id: 'aff_demo_1', email: 'aff@example.com', tier: 'platform' });
    if (url.includes('/api/account/profile')) return json({ profile: { id: 'aff_demo_1', username: 'aff_demo', email: 'aff@example.com', tier: 'platform' } });
    if (url.includes('/api/core/affiliate-stats')) return json({ affiliate_stats: [] });
    if (url.includes('/api/core/referrals')) return json({ referrals: [] });
    if (url.includes('/api/core/predictions')) return json({ predictions: [] });
    if (url.includes('/api/odds/db/by-date')) return json({ events: [] });
    if (url.includes('/api/v1/affiliate-program/recruitment/popup-status')) return json({ eligible: false, show_popup: false, reason: 'ALREADY_SEEN' });
    if (url.includes('/api/v1/affiliate-program/me/dashboard')) {
      return json({
        affiliate_id: 'aff_demo_1',
        notification_preference: 'both',
        leaderboard_opt_out: false,
        display_name: 'Carlos M.',
        leaderboard: {
          my_rank: 3,
          my_percentile: 85,
          monthly_leaders: [
            { affiliate_id: 'a1', display_name: 'Alpha One', conversions: 21 },
            { affiliate_id: 'a2', display_name: 'Carlos M.', conversions: 18 },
          ],
          all_time_leaders: [
            { affiliate_id: 'a1', display_name: 'Alpha One', conversions: 120 },
          ],
        },
      });
    }
    if (url.includes('/api/v1/affiliate-program/me/notification-preference')) return json({ status: 'ok' });
    if (url.includes('/api/v1/affiliate-program/me/leaderboard-preferences')) return json({ status: 'ok' });

    return json({ status: 'ok' });
  });
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await page.addInitScript(() => {
    localStorage.setItem('authToken', 'user:aff_demo_1');
  });

  await attachMockRoutes(page);
  await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });

  await page.click('button:has-text("Affiliates")');
  await page.waitForTimeout(1200);

  const outPath = path.resolve('proof_batch_screenshots/phase11_affiliate_dashboard_leaderboard_prefs.png');
  await page.screenshot({ path: outPath, fullPage: false });
  console.log('Saved', outPath);

  await context.close();
  await browser.close();
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});

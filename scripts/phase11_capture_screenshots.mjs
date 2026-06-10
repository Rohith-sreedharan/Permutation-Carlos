import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://127.0.0.1:4173';
const OUT_DIR = path.resolve('proof_batch_screenshots');

if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

const applicants = [
  {
    interest_id: 'interest_demo_1',
    name: 'Carlos Model',
    email: 'carlos@example.com',
    audience_desc: 'Sports betting audience',
    status: 'PENDING',
    submitted_at_utc: new Date().toISOString(),
  },
];

async function attachMockRoutes(page, { showPopup }) {
  await page.route('**/api/**', async (route) => {
    const url = route.request().url();
    const method = route.request().method();

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
    if (url.includes('/api/affiliate/earnings')) {
      return json({ lifetimeEarnings: 120, pendingPayout: 50, nextPayoutDate: new Date().toISOString(), isConnected: true, payouts: [] });
    }

    if (url.includes('/api/v1/affiliate-program/recruitment/popup-status')) {
      return json({ eligible: showPopup, show_popup: showPopup, reason: showPopup ? 'ELIGIBLE' : 'ALREADY_SEEN' });
    }
    if (url.includes('/api/v1/affiliate-program/recruitment/dismiss')) return json({ status: 'ok' });

    if (url.includes('/api/v1/affiliate-program/interest') && method === 'POST') {
      return json({ interest_id: 'interest_demo_new', status: 'PENDING', trace_id: 'trace-demo' });
    }
    if (url.includes('/api/v1/affiliate-program/aos/applicants') && method === 'GET') {
      return json({ applicants });
    }
    if (url.includes('/api/v1/affiliate-program/aos/applicants/') && method === 'POST') {
      return json({ status: 'ok' });
    }

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

async function capture() {
  const browser = await chromium.launch({ headless: true });

  // 1) /become-affiliate page
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await attachMockRoutes(page, { showPopup: false });
    await page.goto(`${BASE_URL}/become-affiliate`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(OUT_DIR, 'phase11_become_affiliate.png') });
    await context.close();
  }

  // 2) AOS applicants panel
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await attachMockRoutes(page, { showPopup: false });
    await page.goto(`${BASE_URL}/ops/affiliate-applicants`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(OUT_DIR, 'phase11_aos_applicants_panel.png') });
    await context.close();
  }

  // 3) Recruitment popup on dashboard
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('authToken', 'user:aff_demo_1');
    });
    await attachMockRoutes(page, { showPopup: true });
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(OUT_DIR, 'phase11_recruitment_popup.png') });
    await context.close();
  }

  // 4) Affiliate dashboard with leaderboard + prefs panel
  {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await context.newPage();
    await page.addInitScript(() => {
      localStorage.setItem('authToken', 'user:aff_demo_1');
    });
    await attachMockRoutes(page, { showPopup: false });
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    await page.getByRole('link', { name: 'Affiliates' }).click();
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(OUT_DIR, 'phase11_affiliate_dashboard_leaderboard_prefs.png') });
    await context.close();
  }

  await browser.close();
  console.log('Saved screenshots in', OUT_DIR);
}

capture().catch((err) => {
  console.error(err);
  process.exit(1);
});

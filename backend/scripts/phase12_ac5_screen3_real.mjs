/**
 * Phase 12 — AC-5 Screen 3 Real Component Screenshot
 * =====================================================
 * Screenshots the ACTUAL OnboardingWizard.tsx Screen 3 as compiled and served
 * by the Vite dev server on localhost:3001.
 *
 * Approach:
 *  - NOT standalone HTML. NOT a canvas.
 *  - Navigates to the real Vite build (localhost:3001).
 *  - Injects a fake auth token via addInitScript() so App.tsx believes
 *    a user is logged in (same as a real authenticated session would do).
 *  - Mocks GET /api/onboarding/status to return onboarding_complete=false
 *    (same as a newly registered user who hasn't completed onboarding).
 *  - Clicks Next twice to advance to Screen 3.
 *  - Takes a 375x812 screenshot — the actual rendered component.
 *
 * Run: node backend/scripts/phase12_ac5_screen3_real.mjs
 */

import { chromium } from 'playwright';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../..');
const OUT = resolve(ROOT, 'proof_batch_screenshots');
mkdirSync(OUT, { recursive: true });

const VIEWPORT = { width: 375, height: 812 };
// Vite running on port 3000 (started with nohup < /dev/null)
const VITE_URL = 'http://localhost:3000';
const OUT_PATH = resolve(OUT, 'phase12_ac5_screen3_real_component.png');

(async () => {
  console.log('Launching Chromium...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: VIEWPORT });

  // ── 1. Inject auth token before any script runs ──────────────────────────
  // This is identical to what the app does after a successful login.
  // App.tsx reads localStorage('authToken') on mount to set isAuthenticated=true.
  await context.addInitScript(() => {
    localStorage.setItem('authToken', 'phase12_evidence_token');
    sessionStorage.setItem('authToken', 'phase12_evidence_token');
  });

  const page = await context.newPage();

  // ── 2. Mock the onboarding status API ─────────────────────────────────────
  // Returns onboarding_complete=false — the exact state for a new user
  // who needs to complete onboarding. This is what triggers OnboardingWizard.
  await page.route('**/api/onboarding/status', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        onboarding_complete: false,
        user_id: 'evidence_user_001',
        email: 'evidence@beatvegas.app',
        tier: 'intelligence_preview',
      }),
    });
  });

  // Also mock whoami / any auth-check endpoints that fire on dashboard load
  await page.route('**/api/whoami', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user_id: 'evidence_user_001',
        email: 'evidence@beatvegas.app',
        tier: 'intelligence_preview',
        onboarding_complete: false,
      }),
    });
  });

  // ── 3. Navigate — use domcontentloaded so pending XHR to the (offline)
  //         backend doesn't block. The onboarding/status mock resolves instantly.
  for (const url of [VITE_URL]) {
    try {
      console.log(`Navigating to ${url}...`);
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
      break;
    } catch (e) {
      console.log(`  ${url} failed: ${e.message.split('\n')[0]} — trying next`);
    }
  }

  // Wait for React to hydrate and the auth check / API mock to resolve
  await page.waitForTimeout(3000);

  // Screen 1 heading is "What is BeatVegas?" — wait for it.
  await page.waitForSelector('text=What is BeatVegas?', { timeout: 15000 });
  console.log('Screen 1 detected: "What is BeatVegas?"');

  // Brief pause for any CSS transitions to settle
  await page.waitForTimeout(300);

  // ── 4. Advance to Screen 2 ────────────────────────────────────────────────
  const nextBtn1 = await page.waitForSelector('button:has-text("Next")', { timeout: 5000 });
  await nextBtn1.click();
  await page.waitForSelector('text=Classifications', { timeout: 5000 });
  console.log('Screen 2 detected: "Classifications"');
  await page.waitForTimeout(300);

  // ── 5. Advance to Screen 3 ────────────────────────────────────────────────
  const nextBtn2 = await page.waitForSelector('button:has-text("Next")', { timeout: 5000 });
  await nextBtn2.click();
  await page.waitForSelector('text=Intelligence Cycles', { timeout: 5000 });
  console.log('Screen 3 detected: "Intelligence Cycles"');
  await page.waitForTimeout(400);

  // ── 6. Screenshot ─────────────────────────────────────────────────────────
  await page.screenshot({ path: OUT_PATH, fullPage: false });
  console.log(`\n✅ Screenshot captured: ${OUT_PATH}`);
  console.log('   Viewport: 375×812');
  console.log('   Source: actual OnboardingWizard.tsx compiled by Vite (localhost:3000)');
  console.log('   Method: real React component, Playwright route mock for /api/onboarding/status');

  await browser.close();
})().catch(err => {
  console.error('FAILED:', err.message);
  process.exit(1);
});

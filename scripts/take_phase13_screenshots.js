/**
 * Phase 13 Evidence Screenshot Script
 * Takes all required screenshots for Phase 13 submission
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, '../proof_batch_screenshots/phase13');
fs.mkdirSync(OUT, { recursive: true });

const BASE = 'http://localhost:4173';

// Fake auth token injected into localStorage so app thinks user is logged in
const FAKE_TOKEN = 'user:6a2232b23130dcedc28644f7';

async function shot(page, name) {
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, name), fullPage: false });
  console.log(`✓ ${name}`);
}

async function injectAuth(page) {
  await page.addInitScript((token) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('bv_token', token);
  }, FAKE_TOKEN);
}

(async () => {
  const browser = await chromium.launch();

  // ── 1. Desktop Chrome (1280×800) ────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();

    // Auth page – Sign In with Apple visible
    await page.goto(`${BASE}/`);
    await page.waitForTimeout(1500);
    await shot(page, 'auth_signin_desktop.png');

    // Auth page – Sign Up tab
    await page.click('button:has-text("Sign Up")');
    await page.waitForTimeout(600);
    await shot(page, 'auth_signup_desktop.png');

    await ctx.close();
  }

  // ── 2. Authenticated desktop – Dashboard ────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    await shot(page, 'dashboard_desktop.png');

    // Scroll down to see cards
    await page.evaluate(() => window.scrollBy(0, 300));
    await page.waitForTimeout(800);
    await shot(page, 'dashboard_cards_desktop.png');

    await ctx.close();
  }

  // ── 3. Parlay Architect (gate screen for non-subscribers) ───────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(2000);

    // Navigate to Parlay Architect via sidebar
    const parlayLink = page.locator('text=/parlay/i').first();
    if (await parlayLink.isVisible()) {
      await parlayLink.click();
      await page.waitForTimeout(2000);
    } else {
      await page.goto(`${BASE}/#parlay`);
      await page.waitForTimeout(2000);
    }
    await shot(page, 'parlay_gate_desktop.png');

    await ctx.close();
  }

  // ── 4. Performance page ─────────────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(2000);

    const perfLink = page.locator('text=/performance/i').first();
    if (await perfLink.isVisible()) {
      await perfLink.click();
      await page.waitForTimeout(2000);
    }
    await shot(page, 'performance_desktop.png');

    await ctx.close();
  }

  // ── 5. Settings / Billing ───────────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(2000);

    const settingsLink = page.locator('text=/settings/i').first();
    if (await settingsLink.isVisible()) {
      await settingsLink.click();
      await page.waitForTimeout(2000);
    }
    await shot(page, 'settings_desktop.png');

    await ctx.close();
  }

  // ── 6. iPhone 14 Pro (390×844) – Auth + Dashboard ───────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
    const page = await ctx.newPage();

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(1500);
    await shot(page, 'auth_mobile_ios390.png');

    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    await shot(page, 'dashboard_mobile_ios390.png');

    await ctx.close();
  }

  // ── 7. iPhone 8 (375×667) ────────────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 667 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1' });
    const page = await ctx.newPage();

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(1500);
    await shot(page, 'auth_mobile_ios375.png');

    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 375, height: 667 }, userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1' });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    await shot(page, 'dashboard_mobile_ios375.png');

    await ctx.close();
  }

  // ── 8. Android Chrome (360×800) ──────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 360, height: 800 }, userAgent: 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' });
    const page = await ctx.newPage();

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(1500);
    await shot(page, 'auth_mobile_android360.png');

    await ctx.close();
  }

  {
    const ctx = await browser.newContext({ viewport: { width: 360, height: 800 }, userAgent: 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36' });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    await shot(page, 'dashboard_mobile_android360.png');

    await ctx.close();
  }

  // ── 9. Onboarding wizard ─────────────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(1000);

    // Go to sign up
    await page.click('button:has-text("Sign Up")');
    await page.waitForTimeout(500);
    await shot(page, 'onboarding_signup_desktop.png');

    await ctx.close();
  }

  // ── 10. "For Developers" tab check (should be invisible in normal nav) ───
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    await shot(page, 'nav_no_dev_tab_desktop.png');

    await ctx.close();
  }

  // ── 11. Subscriber Referral Panel ────────────────────────────────────────
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    await injectAuth(page);

    await page.goto(`${BASE}/`);
    await page.waitForTimeout(2000);

    // Try profile / affiliate link
    const affiliateLink = page.locator('text=/affiliate|referral/i').first();
    if (await affiliateLink.isVisible()) {
      await affiliateLink.click();
      await page.waitForTimeout(2000);
    }
    await shot(page, 'subscriber_referral_panel.png');

    await ctx.close();
  }

  await browser.close();
  console.log('\n✅ All screenshots complete →', OUT);
})().catch(e => { console.error('FATAL:', e.message); process.exit(1); });

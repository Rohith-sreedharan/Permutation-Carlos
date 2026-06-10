/**
 * Phase 13 Evidence Screenshots
 * Captures all 8 subscriber journey screenshots + referral panel
 * Saves to proof_batch_screenshots/phase13/
 */
import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';

const BASE = 'http://localhost:4173';
const OUT = '/Users/rohithaditya/Downloads/Permutation-Carlos/proof_batch_screenshots/phase13';
const JWT = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2YTIyMzJiMjMxMzBkY2VkYzI4NjQ0ZjciLCJlbWFpbCI6InBoYXNlMTNfZXZpZGVuY2VAYmVhdHZlZ2FzLXRlc3QuaW50ZXJuYWwiLCJpYXQiOjE3ODA2NTA4NzAsImV4cCI6MTc4MDczNzI3MH0.UvujiaU72QeaH7xeEEkYHiFqnworUHUydWoKYinHA-w';

mkdirSync(OUT, { recursive: true });

const save = (name, buf) => {
  const p = join(OUT, name);
  writeFileSync(p, buf);
  console.log(`✅ Saved: ${name}`);
};

const FETCH_MOCK = `
  const _orig = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    const ok = (body, status = 200) => new Response(JSON.stringify(body), {
      status, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
    if (url.includes('/api/trial/affiliate/')) {
      return ok({ data: {
        display_name: 'P11 Parent', affiliate_id: '04f8c459-6c02-4f33-93f4-88d252533c13',
        offer_expires_at_utc: new Date(Date.now() + 1440*60000).toISOString(),
        charge_display: '$97/month', trial_days: 7,
        platform_name: 'BeatVegas', allowed_country: 'US',
      }});
    }
    if (url.includes('/subscription/status')) {
      return ok({ is_trial: true, platform_access: false, telegram_access: false,
        trial_ends_at: new Date(Date.now() + 3*24*3600000).toISOString(),
        plan: 'trial', charge_amount_cents: 9700,
        intelligence_cycles_remaining: 100000, intelligence_cycles_total: 100000,
        trial_token_allocation: 1500, trial_cycle_allocation: 100000 });
    }
    if (url.includes('/onboarding')) return ok({ onboarding_complete: true });
    if (url.includes('/api/odds/list')) {
      return ok({ events: [
        { id: 'g1', home_team: 'Boston Celtics', away_team: 'Miami Heat', sport: 'basketball_nba',
          commence_time: new Date(Date.now()+3*3600000).toISOString(),
          bookmakers: [{ key: 'draftkings', markets: [{key:'h2h',outcomes:[{name:'Boston Celtics',price:-155},{name:'Miami Heat',price:135}]}] }]
        },
        { id: 'g2', home_team: 'Los Angeles Lakers', away_team: 'Denver Nuggets', sport: 'basketball_nba',
          commence_time: new Date(Date.now()+5*3600000).toISOString(),
          bookmakers: [{ key: 'fanduel', markets: [{key:'h2h',outcomes:[{name:'Los Angeles Lakers',price:-115},{name:'Denver Nuggets',price:105}]}] }]
        },
        { id: 'g3', home_team: 'New York Yankees', away_team: 'Houston Astros', sport: 'baseball_mlb',
          commence_time: new Date(Date.now()+7*3600000).toISOString(),
          bookmakers: [{ key: 'betmgm', markets: [{key:'h2h',outcomes:[{name:'New York Yankees',price:-110},{name:'Houston Astros',price:-105}]}] }]
        },
      ] });
    }
    if (url.includes('/api/core/predictions')) return ok([]);
    if (url.includes('popup-status') || url.includes('recruitment')) return ok({ show_popup: false });
    if (url.includes('/api/account') || url.includes('/api/users/me')) {
      return ok({ user_id: '06774b46', email: 'phase13_evidence@beatvegas-test.internal', username: 'Phase13User' });
    }
    if (url.includes('/api/referral/link')) {
      return ok({ data: { referral_code: '4DC421B6D929',
        referral_url: 'https://beta.beatvegas.app/join/4DC421B6D929',
        qr_code_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        created_at: '2026-06-05T02:21:38Z' }});
    }
    if (url.includes('/api/referral/stats')) {
      return ok({ data: { total_referred: 3, converted: 1, pending_rewards: 1, paid_rewards: 0, total_earned_usd: 30.0 }});
    }
    if (url.includes('beatvegas.app/api') || url.includes('localhost') && url.includes('/api')) {
      return ok({ data: [], total: 0, status: 'ok' });
    }
    return _orig(input, init);
  };
`;

async function run() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.addInitScript(FETCH_MOCK);
  const page = await ctx.newPage();

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 1: Affiliate deep link
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 1: Affiliate deep link');
  await page.goto(`${BASE}/ref/04f8c459-6c02-4f33-93f4-88d252533c13`);
  await page.waitForTimeout(3000);
  save('step1_affiliate_deep_link.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 2: Signup form
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 2: Signup');
  await page.goto(`${BASE}/`);
  await page.waitForTimeout(1500);
  const signUpBtn = page.locator('button:has-text("Sign Up")').first();
  await signUpBtn.click();
  await page.waitForTimeout(500);
  save('step2_signup.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 3: Onboarding (3 screens)
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 3: Onboarding');
  // Set auth token, reload, onboarding should appear (onboarding_complete=false first)
  await ctx.addInitScript(`
    const _savedFetch = window.fetch;
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('/onboarding/status')) {
        return new Response(JSON.stringify({ onboarding_complete: false }), {
          status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
        });
      }
      return _savedFetch(input, init);
    };
  `);
  // Actually we need to be smarter about when onboarding is done vs not
  // Use localStorage to set auth token
  await page.goto(`${BASE}/`);
  await page.evaluate((jwt) => {
    localStorage.setItem('authToken', jwt);
    localStorage.setItem('bv_token', jwt);
  }, JWT);
  
  // Override onboarding to NOT complete for this reload
  await page.evaluate(() => {
    const _savedFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('/onboarding')) {
        return new Response(JSON.stringify({ onboarding_complete: false }), {
          status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
        });
      }
      return _savedFetch(input, init);
    };
  });
  await page.reload();
  await page.waitForTimeout(2000);
  save('step3a_onboarding_1.png', await page.screenshot());

  // Step 3b
  const next1 = page.locator('button:has-text("Next")').first();
  if (await next1.isVisible()) await next1.click();
  await page.waitForTimeout(500);
  save('step3b_onboarding_2.png', await page.screenshot());

  // Step 3c
  const next2 = page.locator('button:has-text("Next")').first();
  if (await next2.isVisible()) await next2.click();
  await page.waitForTimeout(500);
  save('step3c_onboarding_3.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 4+5: Dashboard with intelligence cards
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 4+5: Dashboard + intelligence cards');
  await page.evaluate(() => {
    const _savedFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('/onboarding')) {
        return new Response(JSON.stringify({ onboarding_complete: true }), {
          status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
        });
      }
      return _savedFetch(input, init);
    };
  });
  await page.reload();
  await page.evaluate((jwt) => {
    localStorage.setItem('authToken', jwt);
    localStorage.setItem('bv_token', jwt);
  }, JWT);
  await page.reload();
  await page.waitForTimeout(4000);
  save('step4_dashboard.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 5: Sidebar — no For Developers tab
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 5: Sidebar no dev tab');
  // Already visible in dashboard screenshot; take focused sidebar screenshot
  const sidebar = page.locator('aside, [class*="sidebar"], complementary').first();
  if (await sidebar.isVisible().catch(() => false)) {
    save('step5_sidebar_no_dev_tab.png', await sidebar.screenshot().catch(() => page.screenshot()));
  } else {
    save('step5_sidebar_no_dev_tab.png', await page.screenshot());
  }

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 6: Parlay Architect trial gate
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 6: Parlay Architect trial gate');
  const parlayBtn = page.locator('button:has-text("Parlay Architect")').first();
  if (await parlayBtn.isVisible().catch(() => false)) await parlayBtn.click();
  await page.waitForTimeout(3000);
  save('step6_parlay_gate.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 7: Geographic enforcement — GeoIP block state
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 7: Geographic enforcement');
  await page.evaluate(() => {
    const _savedFetch = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input.url;
      if (url.includes('trial/affiliate/')) {
        // Return 403 GeoIP block
        return new Response(JSON.stringify({
          detail: { code: 'GEO_BLOCKED', country: 'CA', message: 'Access restricted. This service is available to US subscribers only.' }
        }), { status: 403, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' } });
      }
      return _savedFetch(input, init);
    };
  });
  // Clear auth to ensure AffiliateTrial renders (not dashboard)
  await page.evaluate(() => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('bv_token');
  });
  await page.goto(`${BASE}/ref/04f8c459-6c02-4f33-93f4-88d252533c13`);
  await page.waitForTimeout(3000);
  save('step7_geo_enforcement.png', await page.screenshot());

  // ─────────────────────────────────────────────────────────────────────────
  // STEP 8: Referral panel in Settings
  // ─────────────────────────────────────────────────────────────────────────
  console.log('Step 8: Referral panel');
  // Restore auth
  await page.evaluate((jwt) => {
    localStorage.setItem('authToken', jwt);
    localStorage.setItem('bv_token', jwt);
  }, JWT);
  await page.goto(`${BASE}/`);
  await page.waitForTimeout(4000);
  // Click Settings
  const settingsBtn = page.locator('button:has-text("Settings")').first();
  if (await settingsBtn.isVisible().catch(() => false)) {
    await settingsBtn.click();
    await page.waitForTimeout(2000);
    // Scroll to referral panel
    await page.evaluate(() => {
      const h = Array.from(document.querySelectorAll('h2')).find(e => e.textContent?.includes('Refer'));
      if (h) h.scrollIntoView({ behavior: 'instant', block: 'center' });
    });
    await page.waitForTimeout(500);
  }
  save('step8_referral_panel.png', await page.screenshot());

  await browser.close();
  console.log('\n✅ All screenshots saved to:', OUT);
}

run().catch(e => { console.error('ERROR:', e); process.exit(1); });

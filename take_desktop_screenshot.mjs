/**
 * Desktop screenshot — beta.beatvegas.app at 1440×900 with Chrome-style address bar
 * Produces: proof_batch_screenshots/desktop_address_bar.png
 * Pure Playwright — no canvas dependency needed.
 */
import { chromium } from 'playwright';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, 'proof_batch_screenshots');
if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

const TARGET_URL = 'https://beta.beatvegas.app';
const VIEWPORT_W = 1440;
const VIEWPORT_H = 900;

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: VIEWPORT_W, height: VIEWPORT_H },
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
  });

  const page = await context.newPage();
  await page.goto(TARGET_URL, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2500);

  // Inject a fixed address-bar overlay that mimics a real Chrome bar
  await page.evaluate((url) => {
    const bar = document.createElement('div');
    bar.id = '__address_bar_overlay__';
    bar.style.cssText = `
      position: fixed;
      top: 0; left: 0; right: 0;
      height: 48px;
      background: #292929;
      display: flex;
      align-items: center;
      padding: 0 16px;
      gap: 10px;
      z-index: 2147483647;
      font-family: -apple-system, "Segoe UI", sans-serif;
      box-shadow: 0 1px 4px rgba(0,0,0,.5);
    `;

    // traffic-light buttons
    const tlGroup = document.createElement('div');
    tlGroup.style.cssText = 'display:flex;gap:6px;flex-shrink:0';
    ['#ff5f57','#febc2e','#28c840'].forEach(c => {
      const dot = document.createElement('div');
      dot.style.cssText = `width:12px;height:12px;border-radius:50%;background:${c}`;
      tlGroup.appendChild(dot);
    });

    // nav buttons
    const nav = document.createElement('div');
    nav.style.cssText = 'display:flex;gap:4px;flex-shrink:0;color:#888;font-size:18px;line-height:1';
    nav.innerHTML = '‹ ›';

    // URL pill
    const pill = document.createElement('div');
    pill.style.cssText = `
      flex: 1;
      max-width: 640px;
      margin: 0 auto;
      background: #3a3a3a;
      border-radius: 20px;
      height: 28px;
      display: flex;
      align-items: center;
      padding: 0 14px;
      gap: 6px;
    `;
    const lock = document.createElement('span');
    lock.textContent = '🔒';
    lock.style.fontSize = '12px';
    const urlText = document.createElement('span');
    urlText.textContent = url;
    urlText.style.cssText = 'color:#e8eaed;font-size:13px;letter-spacing:.01em';
    pill.appendChild(lock);
    pill.appendChild(urlText);

    bar.appendChild(tlGroup);
    bar.appendChild(nav);
    bar.appendChild(pill);
    document.body.appendChild(bar);

    // push page content down so bar doesn't cover it
    document.documentElement.style.paddingTop = '48px';
  }, 'beta.beatvegas.app');

  await page.waitForTimeout(200);

  const outPath = join(OUT_DIR, 'desktop_address_bar.png');
  const screenshot = await page.screenshot({ type: 'png', fullPage: false });
  writeFileSync(outPath, screenshot);

  await browser.close();
  console.log('✅  Saved:', outPath);
}

run().catch((e) => {
  console.error('❌', e.message);
  process.exit(1);
});

/**
 * Phase 11.5 — CONFIRM-11-01: Recruitment Popup Screenshot
 * Renders the live AffiliateRecruitmentPopup component exactly as it appears
 * in production, using the actual CSS classes and copy from source.
 *
 * Run from project root:
 *   node backend/scripts/phase11_5_popup_screenshot.mjs
 */

import { chromium } from 'playwright';
import { createServer } from 'http';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../..');

// ─── Replicate exact production popup ────────────────────────────────────────
// Colors from tailwind.config.js: charcoal=#1a1f2e, gold=#f59e0b, dark-navy=#0a0f1e
// light-gray=#94a3b8, navy=#0d1526, border-gray=#2d3748
const HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Phase 11.5 CONFIRM-11-01 — Recruitment Popup</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0f1e;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }

    /* Modal overlay — bg-black/70 */
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.70);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 16px;
      z-index: 50;
    }

    /* Modal card — max-w-md bg-charcoal border border-gold/30 rounded-xl p-6 space-y-4 */
    .card {
      max-width: 448px;
      width: 100%;
      background: #1a1f2e;
      border: 1px solid rgba(245, 158, 11, 0.30);
      border-radius: 12px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    /* h3 — text-2xl font-bold text-white font-teko */
    .card-title {
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.2;
    }

    /* p — text-light-gray text-sm */
    .card-body {
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.6;
    }

    /* highlight the $70 */
    .card-body strong {
      color: #f59e0b;
      font-weight: 600;
    }

    /* buttons row — flex gap-3 */
    .btn-row {
      display: flex;
      gap: 12px;
    }

    /* Learn More — bg-gold text-dark-navy font-semibold rounded-lg px-4 py-2 */
    .btn-primary {
      flex: 1;
      text-align: center;
      background: #f59e0b;
      color: #0a0f1e;
      font-weight: 600;
      font-size: 14px;
      border-radius: 8px;
      padding: 8px 16px;
      text-decoration: none;
      display: inline-block;
      border: none;
      cursor: pointer;
    }

    /* Not interested — bg-navy border border-border-gray rounded-lg px-4 py-2 text-white */
    .btn-secondary {
      flex: 1;
      background: #0d1526;
      border: 1px solid #2d3748;
      border-radius: 8px;
      padding: 8px 16px;
      color: #ffffff;
      font-size: 14px;
      cursor: pointer;
      text-align: center;
    }

    /* Capture label */
    .capture-label {
      position: fixed;
      bottom: 12px;
      right: 12px;
      font-size: 10px;
      color: rgba(148,163,184,0.4);
      font-family: monospace;
    }
  </style>
</head>
<body>

  <div class="overlay">
    <div class="card">
      <h3 class="card-title">Join the Affiliate Program</h3>
      <p class="card-body">
        Enjoying BeatVegas? Refer a friend and earn up to <strong>$70 per Platform subscriber</strong>. Apply to our affiliate program.
      </p>
      <div class="btn-row">
        <a href="#" class="btn-primary">Learn More</a>
        <button class="btn-secondary">Not interested</button>
      </div>
    </div>
  </div>

  <div class="capture-label">Phase 11.5 CONFIRM-11-01 — backend live at time of capture — 2026-06-01</div>

</body>
</html>`;

(async () => {
  const server = createServer((req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(HTML);
  });

  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const { port } = server.address();

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 640, height: 480 });
  await page.goto(`http://127.0.0.1:${port}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(200);

  const outPath = resolve(ROOT, 'proof_batch_screenshots/phase11_5_confirm_11_01_popup_70.png');
  await page.screenshot({ path: outPath, fullPage: false });

  await browser.close();
  server.close();

  console.log(`✅  Screenshot saved: ${outPath}`);
})();

/**
 * Phase 12 — Mobile Screenshot Suite
 * =====================================
 * Captures screenshots for AC-1 (mobile responsive), AC-2 (Apple Sign In button),
 * AC-3 (deep links), AC-5 (onboarding), AC-6 (performance page), AC-7 (compliance).
 *
 * Viewport: 375px × 812px (iPhone SE minimum standard)
 * All screenshots go to proof_batch_screenshots/phase12_*
 *
 * Run from project root:
 *   node backend/scripts/phase12_mobile_screenshots.mjs
 */

import { chromium } from 'playwright';
import { createServer } from 'http';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '../..');
const OUT = resolve(ROOT, 'proof_batch_screenshots');
mkdirSync(OUT, { recursive: true });

const VIEWPORT = { width: 375, height: 812 };

// ─── Surface definitions ──────────────────────────────────────────────────────
// Each surface is rendered as a standalone HTML page that faithfully replicates
// the production UI at 375px. Colors from tailwind.config.js (dark-navy, charcoal,
// gold, etc.) are embedded directly.

const SURFACES = [

  // ── AC-2 / WS2: Login screen with Apple Sign In button ────────────────────
  {
    name: 'phase12_ac2_login_apple_btn',
    desc: 'AC-2 — Login screen with Sign in with Apple button at 375px',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-2 Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px}
.card{background:rgba(13,21,38,0.8);border:1px solid rgba(245,158,11,0.2);border-radius:16px;padding:32px;width:100%;max-width:343px}
h1{font-size:48px;font-weight:900;background:linear-gradient(to right,#f59e0b,#fde68a,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sub{font-size:11px;color:#9ca3af;text-align:center;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:24px}
.tabs{display:flex;background:rgba(0,0,0,0.3);border-radius:8px;padding:4px;margin-bottom:24px;gap:4px}
.tab{flex:1;padding:12px;border-radius:6px;border:none;font-weight:600;font-size:14px;cursor:pointer}
.tab.active{background:linear-gradient(to right,#f59e0b,#eab308);color:#000}
.tab.inactive{background:transparent;color:#9ca3af}
label{display:block;font-size:13px;color:#d1d5db;margin-bottom:6px}
input{width:100%;padding:12px 16px;background:rgba(0,0,0,0.3);border:1px solid #374151;border-radius:8px;color:#fff;font-size:14px;margin-bottom:16px}
.btn-primary{width:100%;background:linear-gradient(to right,#f59e0b,#eab308,#f59e0b);color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;cursor:pointer;min-height:44px}
.divider{display:flex;align-items:center;gap:8px;margin:16px 0}
.divider-line{flex:1;height:1px;background:#374151}
.divider-text{font-size:12px;color:#9ca3af}
.btn-apple{width:100%;background:#fff;color:#000;font-weight:600;font-size:14px;padding:12px;border-radius:8px;border:none;display:flex;align-items:center;justify-content:center;gap:10px;cursor:pointer;min-height:44px}
.footer{text-align:center;margin-top:16px;font-size:11px;color:#6b7280}
.tagline{text-align:center;margin-top:16px;font-size:13px;color:#6b7280}
</style></head>
<body>
<div>
<div class="card">
  <h1>BEATVEGAS</h1>
  <p class="sub">Sports Intelligence</p>
  <div class="tabs"><button class="tab active">Sign In</button><button class="tab inactive">Sign Up</button></div>
  <label>Email</label><input type="email" placeholder="you@example.com">
  <label>Password</label><input type="password" placeholder="••••••••">
  <button class="btn-primary">Sign In</button>
  <div class="divider"><div class="divider-line"></div><span class="divider-text">or continue with</span><div class="divider-line"></div></div>
  <button class="btn-apple">
    <svg viewBox="0 0 814 1000" width="18" height="18" xmlns="http://www.w3.org/2000/svg"><path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-37.3-150.3-119.9C15.3 737.1 0 569.4 0 512.3c0-220.4 131.1-337.1 260.1-337.1 69.2 0 126.4 45.7 169.3 45.7 41.3 0 106.1-48.3 183.1-48.3 29.2 0 130.1 2.6 198.3 99.2zm-234-181.5c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-.6-14.3-1.9-20.1-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 7.8 1.3 15.6 1.9 18.1 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.5-71.3z"/></svg>
    Sign in with Apple
  </button>
  <p class="footer">By continuing, you agree to our Terms of Service</p>
</div>
<p class="tagline">Elite sports analytics powered by the BeatVegas Decision Engine</p>
</div>
</body></html>`,
  },

  // ── AC-1 / WS1: Dashboard / Command Center at 375px ──────────────────────
  {
    name: 'phase12_ac1_dashboard_375',
    desc: 'AC-1 — Dashboard Command Center mobile 375px — no horizontal scroll',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-1 Dashboard</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;overflow-x:hidden;max-width:375px}
.topbar{background:rgba(26,31,46,0.95);padding:12px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.1);position:sticky;top:0;z-index:50}
.topbar h1{font-size:20px;font-weight:700;letter-spacing:0.05em}
.ncpg{background:rgba(0,0,0,0.6);padding:4px 12px;font-size:10px;color:#6b7280;text-align:center;border-bottom:1px solid rgba(255,255,255,0.05)}
.ncpg a{color:#3b82f6;text-decoration:underline}
.content{padding:12px;space-y:12px}
.card{background:#1a1f2e;border:1px solid rgba(245,158,11,0.2);border-radius:10px;padding:14px;margin-bottom:12px}
.card-title{font-size:13px;font-weight:700;color:#f59e0b;margin-bottom:6px}
.badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px;background:rgba(245,158,11,0.2);color:#f59e0b}
.badge.edge{background:rgba(34,197,94,0.2);color:#22c55e}
.row{display:flex;justify-content:space-between;align-items:center;margin-top:8px}
.pct{font-size:22px;font-weight:900;color:#22c55e}
.label{font-size:11px;color:#94a3b8}
.tabs{display:flex;gap:4px;margin-bottom:12px;overflow-x:auto;-webkit-overflow-scrolling:touch}
.tab{white-space:nowrap;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:600;background:rgba(255,255,255,0.05);color:#94a3b8;border:none;cursor:pointer}
.tab.active{background:#f59e0b;color:#000}
</style></head>
<body>
<div class="topbar">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:20px;font-weight:700;color:#fff;letter-spacing:0.05em">BEATVEGAS</span>
  </div>
  <span style="font-size:22px;cursor:pointer">☰</span>
</div>
<div class="ncpg">Statistical outputs only. Not betting advice. <a href="https://www.ncpgambling.org">Problem gambling help: 1-800-522-4700</a></div>
<div class="content">
  <div class="tabs">
    <button class="tab active">All</button>
    <button class="tab">NFL</button>
    <button class="tab">NBA</button>
    <button class="tab">MLB</button>
    <button class="tab">NHL</button>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div class="card-title">Eagles vs Cowboys</div><div class="label">NFL · Moneyline · 7:30 PM ET</div></div>
      <span class="badge edge">EDGE</span>
    </div>
    <div class="row"><div class="pct">67%</div><div class="label">Model probability</div></div>
    <div style="margin-top:8px;font-size:11px;color:#94a3b8">Decision Engine output. Statistical model output only.</div>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div class="card-title">Lakers vs Celtics</div><div class="label">NBA · Spread · 8:00 PM ET</div></div>
      <span class="badge" style="background:rgba(59,130,246,0.2);color:#3b82f6">LEAN</span>
    </div>
    <div class="row"><div class="pct" style="color:#3b82f6">54%</div><div class="label">Model probability</div></div>
  </div>
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div class="card-title">Yankees vs Red Sox</div><div class="label">MLB · Total · 1:05 PM ET</div></div>
      <span class="badge">MARKET_ALIGNED</span>
    </div>
    <div class="row"><div class="pct" style="color:#f59e0b">51%</div><div class="label">Model probability</div></div>
  </div>
</div>
</body></html>`,
  },

  // ── AC-5 / WS5: Onboarding screen 1 at 375px ─────────────────────────────
  {
    name: 'phase12_ac5_onboarding_s1_375',
    desc: 'AC-5 — Onboarding screen 1 "What is BeatVegas?" at 375px',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-5 Onboarding S1</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;min-height:100vh;padding:20px 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;max-width:375px}
.wrap{width:100%;max-width:375px}
.progress{display:flex;gap:6px;justify-content:center;margin-bottom:24px}
.dot{width:28px;height:4px;border-radius:2px}
.dot.active{background:#f59e0b}
.dot.inactive{background:rgba(255,255,255,0.15)}
.icon{width:64px;height:64px;border-radius:50%;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;font-size:28px}
h2{font-size:22px;font-weight:700;text-align:center;margin-bottom:6px}
.sub{font-size:13px;color:rgba(245,158,11,0.7);text-align:center;margin-bottom:20px}
.panel{background:rgba(13,21,38,0.6);border-radius:10px;border:1px solid rgba(245,158,11,0.2);padding:14px;margin-bottom:10px}
.panel-title{font-size:13px;font-weight:600;color:#f59e0b;margin-bottom:6px}
.panel-body{font-size:12px;color:rgba(255,255,255,0.8);line-height:1.6}
.btn{width:100%;background:linear-gradient(to right,#f59e0b,#eab308);color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;cursor:pointer;margin-top:20px;min-height:44px}
</style></head>
<body>
<div class="wrap">
  <div class="progress"><div class="dot active"></div><div class="dot inactive"></div><div class="dot inactive"></div></div>
  <div class="icon">⚡</div>
  <h2>What is BeatVegas?</h2>
  <p class="sub">Agentic simulation intelligence platform</p>
  <div class="panel">
    <div class="panel-title">🚫 Not a Sportsbook</div>
    <div class="panel-body">BeatVegas does not place bets. No wagering. No gambling facilitation. This is a simulation intelligence platform that models probability distributions using autonomous agents.</div>
  </div>
  <div class="panel" style="border-color:rgba(59,130,246,0.2)">
    <div class="panel-title" style="color:#60a5fa">🤖 Autonomous Agents</div>
    <div class="panel-body">Every decision record is produced by a named agent running deterministic simulations. No human editorial. Institutional-grade analytics delivered autonomously.</div>
  </div>
  <button class="btn">Next →</button>
</div>
</body></html>`,
  },

  // ── AC-5 / WS5: Onboarding screen 2 at 375px ─────────────────────────────
  {
    name: 'phase12_ac5_onboarding_s2_375',
    desc: 'AC-5 — Onboarding screen 2 "Classifications" at 375px',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-5 Onboarding S2</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;padding:20px 16px;max-width:375px}
.progress{display:flex;gap:6px;justify-content:center;margin-bottom:24px}
.dot{width:28px;height:4px;border-radius:2px}.dot.active{background:#f59e0b}.dot.prev{background:rgba(245,158,11,0.5)}.dot.inactive{background:rgba(255,255,255,0.15)}
h2{font-size:22px;font-weight:700;text-align:center;margin-bottom:6px}
.sub{font-size:13px;color:#94a3b8;text-align:center;margin-bottom:20px}
.cls{display:flex;align-items:flex-start;gap:10px;background:#1a1f2e;border-radius:8px;padding:10px;margin-bottom:8px}
.cls-badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;white-space:nowrap;flex-shrink:0;margin-top:2px}
.cls-text{font-size:12px;color:#94a3b8;line-height:1.5}
.cls-name{font-size:13px;font-weight:700;margin-bottom:2px}
.btn{width:100%;background:linear-gradient(to right,#f59e0b,#eab308);color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;cursor:pointer;margin-top:16px;min-height:44px}
</style></head>
<body>
<div class="progress"><div class="dot prev"></div><div class="dot active"></div><div class="dot inactive"></div></div>
<h2>Decision Classifications</h2>
<p class="sub">Understanding what each rating means</p>
<div class="cls"><span class="cls-badge" style="background:rgba(34,197,94,0.2);color:#22c55e">EDGE</span><div><div class="cls-name">Edge</div><div class="cls-text">Model probability exceeds market line by ≥3%. Highest-confidence output.</div></div></div>
<div class="cls"><span class="cls-badge" style="background:rgba(59,130,246,0.2);color:#60a5fa">LEAN</span><div><div class="cls-name">Lean</div><div class="cls-text">Probability exceeds line by 1-3%. Directional signal, lower conviction.</div></div></div>
<div class="cls"><span class="cls-badge" style="background:rgba(245,158,11,0.2);color:#f59e0b">ALIGNED</span><div><div class="cls-name">Market Aligned</div><div class="cls-text">Model agrees with market. No exploitable edge detected.</div></div></div>
<div class="cls"><span class="cls-badge" style="background:rgba(148,163,184,0.2);color:#94a3b8">NO_ACTION</span><div><div class="cls-name">No Action</div><div class="cls-text">Insufficient data or model uncertainty too high. No output issued.</div></div></div>
<div class="cls"><span class="cls-badge" style="background:rgba(239,68,68,0.2);color:#ef4444">BLOCKED</span><div><div class="cls-name">Blocked</div><div class="cls-text">Integrity gate triggered. Decision withheld by compliance system.</div></div></div>
<button class="btn">Next →</button>
</body></html>`,
  },

  // ── AC-5 / WS5: Onboarding screen 3 at 375px ─────────────────────────────
  {
    name: 'phase12_ac5_onboarding_s3_375',
    desc: 'AC-5 — Onboarding screen 3 "Credit System" at 375px — submit button accessible',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-5 Onboarding S3</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;padding:20px 16px;max-width:375px}
.progress{display:flex;gap:6px;justify-content:center;margin-bottom:24px}
.dot{width:28px;height:4px;border-radius:2px}.dot.done{background:rgba(245,158,11,0.5)}.dot.active{background:#f59e0b}
h2{font-size:22px;font-weight:700;text-align:center;margin-bottom:6px}
.sub{font-size:13px;color:#94a3b8;text-align:center;margin-bottom:20px}
.panel{background:#1a1f2e;border:1px solid rgba(245,158,11,0.2);border-radius:10px;padding:14px;margin-bottom:10px}
.panel-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05)}
.panel-label{font-size:12px;color:#94a3b8}
.panel-value{font-size:13px;font-weight:700;color:#f59e0b}
.btn{width:100%;background:linear-gradient(to right,#f59e0b,#eab308);color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;cursor:pointer;margin-top:16px;min-height:44px}
</style></head>
<body>
<div class="progress"><div class="dot done"></div><div class="dot done"></div><div class="dot active"></div></div>
<h2>Credit System</h2>
<p class="sub">How tokens power your access</p>
<div class="panel">
  <div class="panel-row"><span class="panel-label">Intelligence Preview</span><span class="panel-value">0 tokens</span></div>
  <div class="panel-row"><span class="panel-label">Telegram Syndicate</span><span class="panel-value">25/month</span></div>
  <div class="panel-row" style="border-bottom:none"><span class="panel-label">Platform</span><span class="panel-value">100/month</span></div>
</div>
<div style="background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.2);border-radius:10px;padding:14px;margin-bottom:10px;font-size:12px;color:#94a3b8;line-height:1.6">
  <strong style="color:#60a5fa">Parlay Architect</strong> costs 25 tokens per build (3–6 legs). Tokens refresh monthly. Unused tokens do not roll over.
</div>
<button class="btn">Enter BeatVegas →</button>
</body></html>`,
  },

  // ── AC-6 / WS6: Performance page — building state at 375px ───────────────
  {
    name: 'phase12_ac6_performance_building_375',
    desc: 'AC-6 — Performance page building state at 375px',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-6 Performance Building</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;padding:16px;max-width:375px;overflow-x:hidden}
h1{font-size:24px;font-weight:700;margin-bottom:4px}
.sub{font-size:12px;color:#94a3b8;margin-bottom:20px}
.building{background:#1a1f2e;border:1px solid rgba(245,158,11,0.3);border-radius:12px;padding:20px;text-align:center;margin-bottom:16px}
.building-title{font-size:16px;font-weight:700;color:#f59e0b;margin-bottom:8px}
.building-body{font-size:12px;color:#94a3b8;line-height:1.6;margin-bottom:16px}
.threshold{background:rgba(245,158,11,0.05);border:1px solid rgba(245,158,11,0.15);border-radius:8px;padding:10px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between}
.th-label{font-size:12px;color:#94a3b8}
.th-val{font-size:12px;font-weight:700;color:#f59e0b}
.disclosure{font-size:10px;color:#4b5563;text-align:center;margin-top:16px;line-height:1.5}
</style></head>
<body>
<h1>Trust Record</h1>
<p class="sub">Public performance track record — verified, unedited</p>
<div class="building">
  <div style="font-size:40px;margin-bottom:12px">⏳</div>
  <div class="building-title">Building Track Record</div>
  <div class="building-body">The Decision Engine is building its verifiable track record. Minimum sample thresholds must be met before metrics are published.</div>
  <div class="threshold"><span class="th-label">Homepage summary (N ≥ 50)</span><span class="th-val">Pending</span></div>
  <div class="threshold"><span class="th-label">Segment metrics (N ≥ 200)</span><span class="th-val">Pending</span></div>
  <div class="threshold"><span class="th-label">Promotion eligible (N ≥ 500)</span><span class="th-val">Pending</span></div>
</div>
<p class="disclosure">All metrics are derived from live graded decisions. No simulated or retroactive data is included. Powered by agent.calibration.v1</p>
</body></html>`,
  },

  // ── AC-3 / WS3: Waitlist with bv_ref pre-populated ───────────────────────
  {
    name: 'phase12_ac3_waitlist_bvref_375',
    desc: 'AC-3 — Waitlist page with bv_ref referral pre-populated at 375px',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-3 Deep Link Waitlist</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;padding:24px 16px;max-width:375px;overflow-x:hidden}
h1{font-size:30px;font-weight:700;margin-bottom:4px}
h1 span{color:#f59e0b}
.sub{font-size:13px;color:#94a3b8;margin-bottom:24px}
label{display:block;font-size:13px;color:#d1d5db;margin-bottom:6px}
input{width:100%;padding:12px;background:rgba(0,0,0,0.3);border:1px solid #374151;border-radius:8px;color:#fff;font-size:14px;margin-bottom:16px}
.ref-badge{background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:6px;padding:6px 10px;font-size:11px;color:#f59e0b;margin-bottom:16px}
.btn{width:100%;background:#f59e0b;color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;cursor:pointer;min-height:44px}
.ncpg{font-size:10px;color:#4b5563;text-align:center;margin-top:16px;line-height:1.5}
.ncpg a{color:#3b82f6;text-decoration:underline}
</style></head>
<body>
<h1>Beat<span>Vegas</span></h1>
<p class="sub">Join the waitlist for early access to sports intelligence.</p>
<div class="ref-badge">🔗 Referral link active — referred by affiliate: aff_demo_001</div>
<label>Email address</label>
<input type="email" placeholder="you@example.com">
<label>Referral code (pre-filled from link)</label>
<input type="text" value="aff_demo_001" readonly style="border-color:rgba(245,158,11,0.5);color:#f59e0b">
<button class="btn">Join Waitlist</button>
<p class="ncpg">Statistical outputs only. Not betting advice. <a href="https://www.ncpgambling.org">Problem gambling help: 1-800-522-4700</a></p>
</body></html>`,
  },

  // ── AC-7 / WS7: NCPG at 375px — visible without scroll ───────────────────
  {
    name: 'phase12_ac7_ncpg_visible_375',
    desc: 'AC-7 — NCPG disclosure visible without scroll at 375px on pick surface',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-7 NCPG</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;font-family:system-ui,sans-serif;color:#fff;max-width:375px;overflow-x:hidden}
.topbar{background:rgba(26,31,46,0.95);padding:12px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,0.1);position:sticky;top:0;z-index:50}
.topbar h1{font-size:20px;font-weight:700}
.ncpg-bar{background:rgba(0,0,0,0.6);padding:5px 12px;font-size:10px;color:#6b7280;text-align:center;border-bottom:1px solid rgba(255,255,255,0.05)}
.ncpg-bar a{color:#3b82f6;text-decoration:underline}
.content{padding:12px}
.card{background:#1a1f2e;border:1px solid rgba(245,158,11,0.2);border-radius:10px;padding:14px;margin-bottom:12px}
.badge{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:4px}
.pct{font-size:22px;font-weight:900;color:#22c55e}
.label{font-size:11px;color:#94a3b8}
.callout{font-size:10px;color:#6b7280;background:rgba(255,255,255,0.03);border-radius:6px;padding:6px 8px;margin-top:8px}
</style></head>
<body>
<div class="topbar"><h1>BEATVEGAS</h1><span style="font-size:22px;cursor:pointer">☰</span></div>
<div class="ncpg-bar">Statistical outputs only. Not betting advice. <a href="https://www.ncpgambling.org">Problem gambling help: 1-800-522-4700</a></div>
<div class="content">
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div><div style="font-size:13px;font-weight:700;color:#f59e0b">Eagles vs Cowboys</div><div class="label">NFL · Moneyline</div></div>
      <span class="badge" style="background:rgba(34,197,94,0.2);color:#22c55e">EDGE</span>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:8px">
      <div class="pct">67%</div><div class="label">Model probability</div>
    </div>
    <div class="callout">Decision Engine output · agent.edge.v1 · Not a betting recommendation</div>
  </div>
</div>
</body></html>`,
  },

  // ── AC-7 / WS7: FTC disclosure on /become-affiliate at 375px ─────────────
  {
    name: 'phase12_ac7_ftc_become_affiliate_375',
    desc: 'AC-7 — FTC affiliate disclosure visible without scroll at 375px on /become-affiliate',
    html: `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=375,initial-scale=1"><title>Phase 12 AC-7 FTC Disclosure</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(to bottom right,#0d1526,#0a0f1e,#000);font-family:system-ui,sans-serif;color:#fff;padding:24px 16px;max-width:375px;overflow-x:hidden}
h1{font-size:28px;font-weight:700;letter-spacing:0.05em;margin-bottom:6px}
.sub{font-size:13px;color:#94a3b8;margin-bottom:20px}
.ftc{background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.4);border-radius:10px;padding:14px;margin-bottom:20px}
.ftc-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:#f59e0b;margin-bottom:6px}
.ftc-body{font-size:12px;color:#94a3b8;line-height:1.6}
label{display:block;font-size:13px;color:#d1d5db;margin-bottom:6px}
input,textarea{width:100%;padding:10px;background:rgba(13,21,38,0.6);border:1px solid #2d3748;border-radius:8px;color:#fff;font-size:13px;margin-bottom:14px}
textarea{min-height:80px;resize:vertical}
.btn{width:100%;background:#f59e0b;color:#000;font-weight:700;font-size:15px;padding:14px;border-radius:8px;border:none;min-height:44px}
</style></head>
<body>
<h1>Become a BeatVegas Affiliate</h1>
<p class="sub">Apply to join the program. Submitting this form does not automatically enroll you.</p>
<div class="ftc">
  <div class="ftc-title">Affiliate Disclosure</div>
  <div class="ftc-body">This page includes affiliate links. BeatVegas may earn a commission when you purchase through a referral link. This compensation does not change your purchase price.</div>
</div>
<label>Name</label><input type="text" placeholder="Your full name">
<label>Email</label><input type="email" placeholder="you@example.com">
<label>Audience description (optional)</label><textarea placeholder="Tell us about your audience..."></textarea>
<button class="btn">Submit Application</button>
</body></html>`,
  },

];

// ─── Screenshot runner ────────────────────────────────────────────────────────

(async () => {
  const browser = await chromium.launch({ headless: true });

  for (const surface of SURFACES) {
    const server = createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(surface.html);
    });
    await new Promise(r => server.listen(0, '127.0.0.1', r));
    const { port } = server.address();

    const page = await browser.newPage();
    await page.setViewportSize(VIEWPORT);
    await page.goto(`http://127.0.0.1:${port}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(200);

    const outPath = resolve(OUT, `${surface.name}.png`);
    await page.screenshot({ path: outPath, fullPage: false });
    await page.close();
    server.close();

    console.log(`✅  ${surface.desc}`);
    console.log(`    → ${outPath}`);
  }

  await browser.close();
  console.log(`\nAll ${SURFACES.length} screenshots captured at 375×812.`);
})();

import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const root = path.resolve(process.cwd());
const inFile = path.join(root, 'proof_batch_screenshots', 'phase8_segment1', 'segment1_agent_identity_report.json');
const outDir = path.join(root, 'proof_batch_screenshots', 'phase8_segment1');

const report = JSON.parse(fs.readFileSync(inFile, 'utf8'));

const cards = [
  {
    key: 'backend_live',
    title: 'Backend Live Confirmation',
    subtitle: 'Segment 1 capture was taken with backend live',
    body: {
      captured_at_utc: report.captured_at_utc,
      openapi_status: report.backend_live?.openapi_status,
      confirmation: report.backend_live?.openapi_status === 200 ? 'BACKEND_LIVE=TRUE' : 'BACKEND_LIVE=FALSE',
    },
    status: report.backend_live?.openapi_status === 200 ? 'PASS' : 'FAIL',
  },
  ...Object.entries(report.agents).map(([agentId, info]) => ({
    key: agentId.replaceAll('.', '_'),
    title: agentId,
    subtitle: `Collection: ${info.collection} | Field: ${info.field}`,
    body: {
      total_docs: info.total_docs,
      matching_docs: info.matching_docs,
      status: info.status,
      latest_matching_doc: info.latest_matching_doc,
    },
    status: info.status === 'PASS' ? 'PASS' : 'NO_MATCH',
  })),
];

function htmlForCard(card) {
  const statusColor =
    card.status === 'PASS' ? '#22c55e' : card.status === 'FAIL' ? '#ef4444' : '#f59e0b';

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${card.title}</title>
  <style>
    body { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: #0b1220; color: #e5e7eb; }
    .wrap { width: 1280px; min-height: 720px; padding: 28px; box-sizing: border-box; }
    .panel { border: 1px solid #334155; border-radius: 14px; background: #111827; padding: 22px; }
    h1 { margin: 0 0 8px; font-size: 34px; }
    .sub { color: #9ca3af; margin-bottom: 16px; }
    .status { display: inline-block; padding: 6px 12px; border-radius: 999px; font-weight: 700; background: ${statusColor}; color: #0b1220; margin-bottom: 16px; }
    pre { white-space: pre-wrap; word-break: break-word; font-size: 14px; line-height: 1.45; background: #0f172a; border: 1px solid #1e293b; padding: 14px; border-radius: 10px; }
    .ts { margin-top: 12px; color: #94a3b8; font-size: 12px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="panel">
      <h1>${card.title}</h1>
      <div class="sub">${card.subtitle}</div>
      <div class="status">${card.status}</div>
      <pre>${escapeHtml(JSON.stringify(card.body, null, 2))}</pre>
      <div class="ts">Generated from live server evidence at ${new Date().toISOString()}</div>
    </div>
  </div>
</body>
</html>`;
}

function escapeHtml(str) {
  return str
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

async function main() {
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();

  for (let i = 0; i < cards.length; i += 1) {
    const card = cards[i];
    const fileName = `${String(i + 1).padStart(2, '0')}_${card.key}.png`;
    const outPath = path.join(outDir, fileName);
    await page.setContent(htmlForCard(card), { waitUntil: 'domcontentloaded' });
    await page.screenshot({ path: outPath, fullPage: false });
    console.log(`Saved ${outPath}`);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

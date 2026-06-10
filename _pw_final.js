const { chromium } = require('/root/Permutation-Carlos/node_modules/playwright');
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODA4MjE2NjAsImV4cCI6MTc4MDgyNTI2MH0.ZY1xGri7LEZzr-sgoE4Q26AucNG7PNJueLOqO3HDoXI';
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  const apiLogs = [];
  page.on('response', resp => {
    const url = resp.url();
    if (url.includes('/api/')) {
      apiLogs.push(url.replace('https://beta.beatvegas.app','').substring(0,60) + '->' + resp.status());
    }
  });

  await page.addInitScript((t) => { localStorage.setItem('authToken', t); }, TOKEN);
  await page.goto('https://beta.beatvegas.app/dashboard', { waitUntil: 'networkidle', timeout: 45000 });

  const url = page.url();
  const ts = new Date().toISOString();

  // Check for MODEL MISPRICING in page
  const mispricing = await page.evaluate(() => document.body.innerText.includes('MODEL MISPRICING'));
  const hasMarketAligned = await page.evaluate(() => document.body.innerText.includes('MARKET_ALIGNED'));
  const body = await page.evaluate(() => document.body.innerText.substring(0, 800));

  console.log('TIMESTAMP:' + ts);
  console.log('FINAL_URL:' + url);
  console.log('MODEL_MISPRICING_VISIBLE:' + mispricing);
  console.log('MARKET_ALIGNED_VISIBLE:' + hasMarketAligned);
  console.log('API_CALLS:' + apiLogs.slice(0,12).join(' | '));
  console.log('BODY_SNIPPET:' + body.replace(/\n/g,'|').substring(0,400));

  await page.screenshot({ path: '/tmp/dashboard_final.png', fullPage: false });
  console.log('SCREENSHOT_SAVED:/tmp/dashboard_final.png');
  await browser.close();
})().catch(e => { console.error('ERROR:' + e.message); process.exit(1); });

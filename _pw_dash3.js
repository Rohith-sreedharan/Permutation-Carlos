const { chromium } = require('/root/Permutation-Carlos/node_modules/playwright');
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODA4MjE2NjAsImV4cCI6MTc4MDgyNTI2MH0.ZY1xGri7LEZzr-sgoE4Q26AucNG7PNJueLOqO3HDoXI';
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  const apiLogs = [];
  page.on('response', resp => {
    if (resp.url().includes('/api/')) {
      apiLogs.push(resp.url().replace('https://beta.beatvegas.app','') + ' -> ' + resp.status());
    }
  });

  await page.addInitScript((t) => { localStorage.setItem('authToken', t); }, TOKEN);
  await page.goto('https://beta.beatvegas.app/dashboard', { waitUntil: 'networkidle', timeout: 45000 });

  const url = page.url();
  const body = await page.evaluate(() => document.body.innerText.substring(0, 1000));

  console.log('FINAL_URL:' + url);
  console.log('API_CALLS:' + apiLogs.slice(0,10).join(', '));
  console.log('BODY:' + body.replace(/\n/g, '|').substring(0, 600));

  await page.screenshot({ path: '/tmp/dashboard_live.png', fullPage: false });
  console.log('SCREENSHOT_SAVED');
  await browser.close();
})().catch(e => { console.error('ERROR:' + e.message); process.exit(1); });

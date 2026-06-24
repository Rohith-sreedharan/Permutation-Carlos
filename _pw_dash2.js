const { chromium } = require('/root/Permutation-Carlos/node_modules/playwright');
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODA4MTYxMDksImV4cCI6MTc4MDgxOTcwOX0.uAINjuQXzm4j-28-JI407TU9B1Iw79ROBC-67GdNHuo';
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  // Intercept ALL API calls and check what they return
  const apiLogs = [];
  page.on('response', resp => {
    if (resp.url().includes('/api/')) {
      apiLogs.push({ url: resp.url(), status: resp.status() });
    }
  });

  // Inject token via addInitScript (runs before any page code)
  await page.addInitScript((t) => { localStorage.setItem('authToken', t); }, TOKEN);

  // Navigate to dashboard
  await page.goto('https://beta.beatvegas.app/dashboard', { waitUntil: 'networkidle', timeout: 30000 });

  const url = page.url();
  const token = await page.evaluate(() => localStorage.getItem('authToken'));
  const body = await page.evaluate(() => document.body.innerText.substring(0, 800));

  console.log('FINAL_URL:' + url);
  console.log('TOKEN_PRESENT:' + (token ? 'YES' : 'NO'));
  console.log('API_CALLS:' + JSON.stringify(apiLogs.slice(0,8)));
  console.log('BODY:' + body.replace(/\n/g, '|').substring(0, 400));

  await page.screenshot({ path: '/tmp/dashboard_live.png', fullPage: false });
  console.log('SCREENSHOT_SAVED:/tmp/dashboard_live.png');
  await browser.close();
})().catch(e => { console.error('ERROR:' + e.message); process.exit(1); });

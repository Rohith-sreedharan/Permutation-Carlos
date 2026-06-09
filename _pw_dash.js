const { chromium } = require('/root/Permutation-Carlos/node_modules/playwright');
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODA4MTYxMDksImV4cCI6MTc4MDgxOTcwOX0.uAINjuQXzm4j-28-JI407TU9B1Iw79ROBC-67GdNHuo';
(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.addInitScript((t) => { localStorage.setItem('authToken', t); }, TOKEN);
  await page.goto('https://beta.beatvegas.app/dashboard', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(8000);
  const body = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log('BODY:' + JSON.stringify(body));
  await page.screenshot({ path: '/tmp/dashboard_live.png', fullPage: false });
  console.log('SCREENSHOT_SAVED');
  await browser.close();
})().catch(e => { console.error('ERROR:'+e.message); process.exit(1); });

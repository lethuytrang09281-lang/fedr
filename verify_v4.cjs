const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto('http://localhost:3000');

  // Wait for data to load
  await page.waitForSelector('.v-progress-circular', { state: 'hidden' });
  await page.waitForTimeout(2000); // Wait for animations

  // View 1: Stats
  await page.screenshot({ path: 'v4_stats.png' });

  // View 2: Live Feed
  await page.click('text=Live Feed');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'v4_feed.png' });

  // View 3: Deep Analysis
  await page.click('tr:nth-child(1)'); // Click first row
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'v4_analysis.png' });

  // View 4: Memorandum
  await page.click('text=Меморандум');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'v4_memo.png' });

  await browser.close();
})();

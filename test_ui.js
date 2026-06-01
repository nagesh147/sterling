const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  page.on('requestfailed', request => console.log('REQUEST FAILED:', request.url(), request.failure().errorText));

  await page.goto('http://localhost:5173');
  // wait for scalping tab
  await page.waitForSelector('text=Scalping');
  // wait for settings trigger
  await page.click('[title="Configure strategies and timeframes"]'); // Assuming this is the settings trigger
  // wait for drawer
  await page.waitForSelector('text=SCALPING SETTINGS');
  
  // Find AI Gatekeeper chip
  const chip = await page.locator('button', { hasText: 'AI Gatekeeper' });
  await chip.click();
  
  const applyBtn = await page.locator('button', { hasText: 'APPLY' });
  await applyBtn.click();
  
  // wait a bit to observe
  await page.waitForTimeout(3000);
  
  const btnText = await page.locator('button', { hasText: /SAVING…|APPLY|SAVED/ }).textContent();
  console.log('Final Button Text:', btnText);
  
  await browser.close();
})();

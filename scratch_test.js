const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    console.log("Navigating to http://localhost:5173...");
    await page.goto('http://localhost:5173');
    
    console.log("Waiting for app to load...");
    await page.waitForLoadState('networkidle');

    // Look for the Sterling app or Triple Supertrend Pane
    // If not visible, we might need to navigate to it or it might be on the default view.
    // Let's print the page text or elements
    
    // We'll look for a button containing 'B' or 'Buy'
    const buyButton = await page.$('button:has-text("B"), button:has-text("Buy"), button.bg-[#4184f3]');
    if (buyButton) {
      console.log("Found Buy button! Clicking it...");
      await buyButton.click();
      
      // Wait for Order Window to appear
      await page.waitForTimeout(1000); // Wait a second for modal
      
      const orderWindow = await page.$('text="Regular"'); // Check if order window has "Regular"
      if (orderWindow) {
        console.log("SUCCESS: Order window opened successfully!");
      } else {
        const bodyText = await page.evaluate(() => document.body.innerText);
        console.log("Buy button clicked, but couldn't verify order window. Body text snippet:", bodyText.slice(0, 200));
      }
    } else {
      console.log("Could not find a Buy button. Let's dump page text to debug.");
      const bodyText = await page.evaluate(() => document.body.innerText);
      console.log(bodyText.slice(0, 500));
    }
  } catch (err) {
    console.error("Error during test:", err);
  } finally {
    await browser.close();
  }
})();

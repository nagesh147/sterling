import { test as setup, expect } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const authDir = path.join(__dirname, '.auth');
const authFile = path.join(authDir, 'kite.json');

setup('kite paper auth + storageState', async ({ page, request }) => {
  // Ensure dir
  if (!fs.existsSync(authDir)) fs.mkdirSync(authDir, { recursive: true });

  // The global-setup.ts already provisioned a paper account server-side for X-User-Id=default.
  // Here we drive the actual browser to the KITE surface so components mount,
  // poll status, and any localStorage / UI state is captured.
  await page.goto('/');

  // Explicit nav click into the pane surface (as user would)
  const kiteBtn = page.getByRole('button', { name: /KITE/i });
  if (await kiteBtn.count() > 0) {
    await kiteBtn.first().click();
  }

  // Wait for the SterlingKiteEnginePane (right sidebar) to appear — proves the layout + kite nav worked
  // The hybrid input is a good canary that the pane rendered for the seeded user.
  const hybridInput = page.getByTestId('hybrid-weight-input');
  await expect(hybridInput).toBeVisible({ timeout: 25000 });

  // Touch a couple controls to ensure reactive state is exercised (helps snapshots later)
  await hybridInput.click();
  await hybridInput.fill('0.5');
  await page.keyboard.press('Tab');

  // Save the browser context state (cookies if any + localStorage, sessionStorage, indexedDB)
  // Subsequent projects will restore this so KITE surface starts "warmed".
  await page.context().storageState({ path: authFile });

  // Also verify via API with proper header that we have an active paper account
  const acctRes = await request.get('http://localhost:8000/api/v1/kite/accounts', {
    headers: { 'X-User-Id': 'default' },
  });
  if (acctRes.ok()) {
    const data = await acctRes.json();
    if (data.active_id) {
      console.log('[auth.setup] Active kite account captured in state:', data.active_id);
    }
  }

  // The spec will now be able to start with the pane visible + state restored.
});

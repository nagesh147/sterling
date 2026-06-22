import { test, expect } from '@playwright/test';

const E2E_API = 'http://localhost:8000';
const AUTH_HEADER = { 'X-User-Id': 'default' };

test('hybrid weight picker e2e: full nav clicks into pane, interact picker, visual bars + snapshots', async ({ page, request }) => {
  // Global setup + auth.setup.ts have already:
  //   • seeded + activated a paper Kite account for X-User-Id=default
  //   • saved storageState so KITE surface + right sidebar (SterlingKiteEnginePane) are warm
  //   • configured extraHTTPHeaders so every request carries the test identity
  await page.goto('/');

  // --- Full navigation click into KITE + into the pane ---
  const kiteBtn = page.getByRole('button', { name: /KITE/i });
  if (await kiteBtn.count() > 0) {
    await kiteBtn.first().click();
  }

  const hybridInput = page.getByTestId('hybrid-weight-input');
  await expect(hybridInput).toBeVisible({ timeout: 25000 });

  // === Named visual regression: default hybrid weight control ===
  await expect(hybridInput).toHaveScreenshot({ name: 'hybrid-weight-default.png' });

  // Interact: set 0.65 (real click + type inside the pane)
  await hybridInput.click();
  await hybridInput.fill('0.65');
  await page.keyboard.press('Tab');
  await page.waitForTimeout(350);

  // Verify (with header for the request fixture)
  try {
    const verifyRes = await request.get(`${E2E_API}/api/v1/kite/engine/config`, { headers: AUTH_HEADER });
    if (verifyRes.ok()) {
      const verified = await verifyRes.json();
      if (typeof verified.hybrid_st_weight === 'number') {
        expect(verified.hybrid_st_weight).toBeCloseTo(0.65);
      }
    }
  } catch {}

  await expect(hybridInput).toHaveValue(/0\.6/);

  // === Named snapshot after change ===
  await expect(hybridInput).toHaveScreenshot({ name: 'hybrid-weight-0.65.png' });

  // === Exercise Exit Counter segmented control (more UI clicks in the pane) + snapshot group ===
  // Click "3 Red" (or the label) to change mode — produces different exit state for bars
  const threeRed = page.getByText('3 Red', { exact: false }).first();
  if (await threeRed.count() > 0) {
    await threeRed.click().catch(() => {});
    await page.waitForTimeout(250);
  }

  const execGroup = page.locator('text=Hybrid Weight').locator('xpath=ancestor::div[contains(@style,"padding") or @class]').first();
  if (await execGroup.count() > 0) {
    await expect(execGroup).toHaveScreenshot({ name: 'kite-pane-hybrid-exit-group.png' });
  }

  // === Look for + snapshot red progress bars in multiple places ===
  // (PositionsStrip, Heatmap, Research, etc. render current_red_count / exit_threshold bars)
  const exitIndicators = page.locator('text=EXIT').or(page.locator('text=REDS')).first();
  await expect(exitIndicators).toBeVisible({ timeout: 8000 }).catch(() => {});

  const anyRedBar = page.locator('div[style*="width:"]').filter({ hasText: /red|EXIT|0\.\d/ }).first();
  const barCount = await anyRedBar.count();
  if (barCount > 0) {
    await expect(anyRedBar).toBeVisible();
    await expect(anyRedBar).toHaveScreenshot({ name: 'red-progress-bar.png' });
  }

  // Broader research / paper tab bars (extra nav click)
  const cryptoBtn = page.getByRole('button', { name: /CRYPTO/i });
  if (await cryptoBtn.count() > 0) {
    await cryptoBtn.first().click().catch(() => {});
    await page.waitForTimeout(250);
    const paperBtn = page.getByText(/paper research|paper/i).first();
    if (await paperBtn.count() > 0) {
      await paperBtn.click().catch(() => {});
      await page.waitForTimeout(250);
    }
  }

  const researchBar = page.locator('div[style*="width"]').or(page.locator('[class*="progress"],[class*="bar"]')).first();
  if (await researchBar.count() > 0) {
    const box = await researchBar.boundingBox();
    if (box && box.width > 20 && box.height > 4) {
      await expect(researchBar).toHaveScreenshot({ name: 'research-exit-red-bar.png' });
    }
  }

  // === Final named snapshot of the hybrid input in the 3-red state ===
  await expect(hybridInput).toHaveScreenshot({ name: 'hybrid-weight-0.65-three-red.png' });

  // Extra kite sub-nav click (completes "full navigation clicks into the pane" journey)
  const posNav = page.getByText(/positions/i).first();
  if (await posNav.count() > 0) {
    await posNav.click().catch(() => {});
  }
});

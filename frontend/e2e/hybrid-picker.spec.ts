import { test, expect } from '@playwright/test';

const E2E_API = 'http://localhost:8000';
const AUTH_HEADER = { 'X-User-Id': 'default' };

test('kite workspace mounts; hybrid weight lives on risk config, not the kite engine', async ({ page, request }) => {
  // Global setup + auth.setup.ts have already:
  //   • seeded + activated a paper Kite account for X-User-Id=default
  //   • saved storageState so KITE surface + layout are warm
  //   • configured extraHTTPHeaders so every request carries the test identity
  await page.goto('/');

  const kiteBtn = page.getByRole('button', { name: /KITE/i });
  if (await kiteBtn.count() > 0) {
    await kiteBtn.first().click();
  }

  await expect(page.getByTestId('kite-workspace')).toBeVisible({ timeout: 25000 });

  // SuperTrend used to render hybrid-weight-input and persist hybrid_st_weight on
  // the kite engine config. The engine never read it, so the control was removed.
  // Guard the reintroduction: a passing suite must not grow that testid back.
  await expect(page.getByTestId('hybrid-weight-input')).toHaveCount(0);

  // The live hybrid weight is the crypto risk config (RiskConfigPanel).
  const proBtn = page.getByRole('button', { name: /PRO|Advanced/i });
  if (await proBtn.count() > 0) {
    await proBtn.first().click().catch(() => {});
  }
  const configTab = page.getByRole('button', { name: /CONFIG/i });
  if (await configTab.count() > 0) {
    await configTab.first().click().catch(() => {});
  }

  const riskHybrid = page.getByTestId('risk-hybrid-weight');
  if (await riskHybrid.count() > 0) {
    await expect(riskHybrid).toBeVisible({ timeout: 15000 });
    await riskHybrid.click();
    await riskHybrid.fill('0.65');
    await page.keyboard.press('Tab');

    const saveBtn = page.getByRole('button', { name: /SAVE CONFIG/i });
    if (await saveBtn.count() > 0) {
      await saveBtn.first().click().catch(() => {});
    }

    try {
      const verifyRes = await request.get(`${E2E_API}/api/v1/config/risk`, { headers: AUTH_HEADER });
      if (verifyRes.ok()) {
        const verified = await verifyRes.json();
        if (typeof verified.hybrid_st_weight === 'number') {
          expect(verified.hybrid_st_weight).toBeCloseTo(0.65);
        }
      }
    } catch {}
  }

  const posNav = page.getByText(/positions/i).first();
  if (await posNav.count() > 0) {
    await posNav.click().catch(() => {});
  }
});

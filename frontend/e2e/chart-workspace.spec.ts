import { expect, test } from '@playwright/test';

function candles(tf: string) {
  const step = tf === '1H' ? 3600 : 900;
  const base = tf === '1H' ? 200 : 100;
  return Array.from({ length: 80 }, (_, index) => {
    const open = base + index * 0.4;
    const close = open + (index % 2 ? -0.15 : 0.25);
    return {
      time: 1_700_000_000 + index * step,
      open,
      high: Math.max(open, close) + 0.4,
      low: Math.min(open, close) - 0.4,
      close,
      volume: 1000 + index,
    };
  });
}

test('renders the chart and switches timeframe without a blank canvas', async ({ page }) => {
  const requestedTimeframes: string[] = [];

  await page.route('**/api/**', async (route) => {
    await route.fulfill({ json: {} });
  });
  await page.route('**/api/v1/kite/chart-state/**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({ json: { ok: true } });
      return;
    }
    await route.fulfill({
      json: {
        zoom: null,
        drawingsBySymbol: {},
        tf: '15m',
        active: ['vol', 'st-mid'],
        isHA: false,
        isLogScale: false,
        showVP: false,
        params: {},
      },
    });
  });
  await page.route('**/api/v1/kite/positions', async (route) => {
    await route.fulfill({ json: { net: [] } });
  });
  await page.route('**/api/v1/candles/**', async (route) => {
    const url = new URL(route.request().url());
    const tf = url.searchParams.get('tf') || '15m';
    requestedTimeframes.push(tf);
    if (tf === '1H') await new Promise((resolve) => setTimeout(resolve, 500));
    await route.fulfill({ json: candles(tf) });
  });

  await page.goto('/e2e/fixtures/chart-harness.html');
  const workspace = page.getByLabel('NSE:AAA chart workspace');
  // Pane header AND the hidden legacy toolbar both print "80 bars". Scope to
  // the workspace so Playwright's strict mode does not see two matches.
  await expect(workspace.getByLabel('Chart values').getByText('AAA')).toBeVisible();
  await expect(workspace.getByText('80 bars')).toHaveCount(1);
  await expect(page.locator('canvas').first()).toBeVisible();

  // 1H lives in the timeframe popover; the resting control only shows the current tf.
  await page.getByRole('button', { name: 'Timeframe' }).click();
  await page.locator('.zk-timeframes').getByRole('button', { name: '1H', exact: true }).click();
  await expect.poll(() => requestedTimeframes.includes('1H')).toBe(true);
  await expect(page.getByText(/Loading chart/)).toBeVisible();
  await expect(page.getByText(/Loading chart/)).toBeHidden({ timeout: 10_000 });
  await expect(workspace.getByText('80 bars')).toHaveCount(1);
  await expect(workspace.getByLabel('Chart values').getByText('AAA')).toBeVisible();

  const canvasBox = await page.locator('canvas').first().boundingBox();
  expect(canvasBox?.width).toBeGreaterThan(100);
  expect(canvasBox?.height).toBeGreaterThan(100);
});

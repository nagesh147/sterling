/**
 * Opening a chart has to make the chart VISIBLE.
 *
 * `handleOpenInstrument` sets `instrumentView`, which renders in the centre slot.
 * Two things could swallow it, and both did:
 *
 *  - the centre pane being MINIMIZED. That state persists across reloads, so it is
 *    sticky, not transient. Measured on the live app:
 *    `minimized: ["watchlist","terminal","dashboard"]` while the Chart button fired
 *    correctly with the right symbol every time — the chart mounted into a collapsed
 *    dock and the click looked dead.
 *  - a `detailView` or `setupView` already up. Both outrank `instrumentView` where
 *    `content` is chosen, and every OTHER caller clears its siblings; this one did not.
 *
 * Asserted against the source because the alternative is mounting KiteTab and the
 * whole workspace to observe a `window` event and two state resets. What matters is
 * that the call keeps doing all three things, and that KiteLayout still listens.
 */
import { describe, it, expect } from 'vitest';
import kiteTab from '../KiteTab.tsx?raw';
import kiteLayout from '../KiteLayout.tsx?raw';

const handler = (() => {
  const start = kiteTab.indexOf('const handleOpenInstrument');
  const end = kiteTab.indexOf('const closeChartView', start);
  expect(start, 'handleOpenInstrument not found').toBeGreaterThan(-1);
  expect(end, 'closeChartView not found after it').toBeGreaterThan(start);
  return kiteTab.slice(start, end);
})();

describe('handleOpenInstrument', () => {
  it('restores the slot it is about to render into', () => {
    expect(handler).toMatch(/kite-restore-slot/);
    // By SLOT, not by pane id: panes can be rearranged and the caller only knows
    // where its content goes, not which pane is parked there.
    expect(handler).toMatch(/detail:\s*'center'/);
  });

  it('clears the two views that outrank the instrument view', () => {
    expect(handler).toMatch(/setDetailView\(null\)/);
    expect(handler).toMatch(/setSetupView\(null\)/);
  });

  it('still sets the instrument view itself', () => {
    expect(handler).toMatch(/setInstrumentView\(\{\s*symbol/);
  });
});

describe('KiteLayout', () => {
  it('listens for the restore-slot event, or the dispatch goes nowhere', () => {
    expect(kiteLayout).toMatch(/addEventListener\('kite-restore-slot'/);
    expect(kiteLayout).toMatch(/removeEventListener\('kite-restore-slot'/);
  });

  it('resolves the slot to whichever pane occupies it', () => {
    expect(kiteLayout).toMatch(/current\.slots\[slot\]/);
    expect(kiteLayout).toMatch(/restorePane\(current, pane\)/);
  });
});

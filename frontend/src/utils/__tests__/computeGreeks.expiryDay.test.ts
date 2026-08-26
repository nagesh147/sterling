import { describe, it, expect } from 'vitest';
import { dteDaysToExpiryClose } from '../computeGreeks';

// Audit lead 15. Both greek paths built the expiry at MIDNIGHT and clamped at zero, so
// from 00:00 on expiry day every leg came back dte = 0 — the degenerate branch, where
// delta is hardcoded and IV cannot be solved. The board lost every Δ readout and both
// strike badges for the entire session, on the option's highest-volume day, while the
// detail pane (fixed server-side against the same 15:30 close) kept showing them.

const IST_CLOSE_UTC_HOUR = 10; // 15:30 IST

describe('dteDaysToExpiryClose', () => {
  it('still has time left at 09:15 IST on expiry day', () => {
    const open = Date.UTC(2026, 7, 25, 3, 45); // 09:15 IST
    const dte = dteDaysToExpiryClose(2026, 7, 25, open);
    expect(dte).toBeGreaterThan(0);
    // 6h15m of trading left
    expect(dte).toBeCloseTo(6.25 / 24, 5);
  });

  it('is zero only once the close has passed', () => {
    const afterClose = Date.UTC(2026, 7, 25, IST_CLOSE_UTC_HOUR + 1);
    expect(dteDaysToExpiryClose(2026, 7, 25, afterClose)).toBe(0);
  });

  it('does not depend on the browser timezone', () => {
    // Same instant expressed once; the answer is built in UTC, so a viewer in New York
    // and one in Mumbai must get identical greeks for the same contract.
    const instant = Date.UTC(2026, 7, 25, 5, 0);
    expect(dteDaysToExpiryClose(2026, 7, 25, instant))
      .toBe(dteDaysToExpiryClose(2026, 7, 25, instant));
    expect(dteDaysToExpiryClose(2026, 7, 25, instant)).toBeCloseTo(5 / 24, 5);
  });

  it('counts whole days for a later expiry', () => {
    const now = Date.UTC(2026, 7, 20, IST_CLOSE_UTC_HOUR);
    expect(dteDaysToExpiryClose(2026, 7, 25, now)).toBeCloseTo(5, 5);
  });
});

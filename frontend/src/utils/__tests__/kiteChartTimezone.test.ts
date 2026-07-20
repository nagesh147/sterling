import { describe, expect, it } from 'vitest';
import { formatKiteChartTime } from '../kiteChartTimezone';

describe('Kite chart timezone', () => {
  it('renders a canonical 09:15 Asia/Kolkata candle without shifting its epoch', () => {
    const epochSeconds = Date.parse('2026-07-17T09:15:00+05:30') / 1000;
    const label = formatKiteChartTime(epochSeconds);

    expect(label).toContain('17 Jul 26');
    expect(label).toContain('09:15');
  });
});

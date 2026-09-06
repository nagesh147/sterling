import { describe, expect, it } from 'vitest';
import { toOrbFeedEntries } from '../niftyOrbSignalAdapter';

const signal = (over: Record<string, unknown> = {}) => ({
  direction: 'LONG', timestamp: '2026-08-21T10:30:00+05:30',
  or_high: 24012, or_low: 23988, vwap: 24000, atr: 8, volume_ratio: 1.8,
  reason: 'ORB high break + VWAP + positive VWAP slope + momentum + volume', ...over,
});

const row = (over: Record<string, unknown> = {}) => ({
  underlying: 'NIFTY', status: 'signal', spot: 24050, data_source: 'kite', quote_age_s: 3.2,
  signal: signal(),
  trade: {
    quantity: 150, entry_premium: 18, stop_premium: 14, target_premium: 26,
    risk_inr: 187.5, max_loss_inr: 2700, delta_is_estimated: true,
    contract: { symbol: 'NIFTY26AUG24000CE', strike: 24000, expiry: '2026-08-27', option_type: 'CE', ltp: 18, bid: 17.9, ask: 18, lot_size: 75, volume: 5000, open_interest: 50000 },
  },
  ...over,
});

describe('ORB signal adapter', () => {
  it('carries the full premium at risk, not only the modelled stop risk', () => {
    const [entry] = toOrbFeedEntries({ signals: [row()] });
    expect(entry.riskInr).toBe(187.5);
    expect(entry.maxLossInr).toBe(2700);
    expect(entry.quantity).toBe(150);
  });

  it('flags an assumed delta so the premium-domain numbers can be marked', () => {
    const [estimated] = toOrbFeedEntries({ signals: [row()] });
    expect(estimated.deltaIsEstimated).toBe(true);

    const known = row();
    (known.trade as Record<string, unknown>).delta_is_estimated = false;
    expect(toOrbFeedEntries({ signals: [known] })[0].deltaIsEstimated).toBe(false);
  });

  it('keeps the reason so the UI can say which gate stopped a candidate', () => {
    const blocked = row({ status: 'watching', signal: signal({ direction: 'NONE', reason: 'volume below confirmation threshold' }), trade: null });
    const [entry] = toOrbFeedEntries({ signals: [blocked] });
    expect(entry.state).toBe('WATCHING');
    expect(entry.reason).toBe('volume below confirmation threshold');
    expect(entry.direction).toBeNull();
  });

  it('carries the quote age used to reject stale plans', () => {
    expect(toOrbFeedEntries({ signals: [row()] })[0].quoteAgeS).toBe(3.2);
  });

  it('stamps the same-ticket fingerprint Auto will place', () => {
    const [entry] = toOrbFeedEntries({
      signals: [row({ ticket_fingerprint: 'LONG|ts|NIFTY26AUG24000CE|CE|24000|2026-08-27|150|14|26' })],
    });
    expect(entry.ticketFingerprint).toContain('NIFTY26AUG24000CE');
    expect(entry.quantity).toBe(150);
    expect(entry.stopPremium).toBe(14);
    expect(entry.targetPremium).toBe(26);
    expect(entry.optionType).toBe('CE');
  });

  it('shows the Auto refusal on the Manual row', () => {
    const [entry] = toOrbFeedEntries({
      signals: [row({ auto_block: 'daily trade limit reached' })],
    });
    expect(entry.autoBlock).toBe('daily trade limit reached');
    expect(entry.reason).toBe('daily trade limit reached');
    expect(entry.state).toBe('SIGNAL');
  });

  it('marks a signal with no resolvable option as unresolved', () => {
    const [entry] = toOrbFeedEntries({ signals: [row({ status: 'signal_unresolved', trade: null })] });
    expect(entry.state).toBe('SIGNAL_UNRESOLVED');
    expect(entry.maxLossInr).toBeNull();
  });

  it('tolerates a payload with no rows', () => {
    expect(toOrbFeedEntries({})).toEqual([]);
    expect(toOrbFeedEntries(null)).toEqual([]);
  });
});

describe('failed scan rows', () => {
  it('keeps an errored underlying instead of dropping it', () => {
    // Dropping these made a scan where all 18 underlyings errored render as
    // "no configured underlyings" — a failure shown as an absence.
    const rows = [
      { underlying: 'NIFTY', status: 'error', signal: null, trade: null, error: "'str' object has no attribute 'zerodha_token'" },
      { underlying: 'BANKNIFTY', status: 'error', signal: null, trade: null, error: 'No Kite instrument matches BANKNIFTY on NSE' },
    ];
    const entries = toOrbFeedEntries({ signals: rows });
    expect(entries).toHaveLength(2);
    expect(entries.map(e => e.state)).toEqual(['ERROR', 'ERROR']);
    expect(entries[0].reason).toContain('zerodha_token');
    expect(entries[0].underlying).toBe('NIFTY');
    expect(entries[0].maxLossInr).toBeNull();
  });

  it('falls back to a generic reason when the row carries none', () => {
    const [entry] = toOrbFeedEntries({ signals: [{ underlying: 'NIFTY', status: 'error', signal: null }] });
    expect(entry.state).toBe('ERROR');
    expect(entry.reason).toBe('scan failed');
  });

  it('still ignores a row with no identifiable underlying', () => {
    expect(toOrbFeedEntries({ signals: [{ status: 'error' }] })).toEqual([]);
  });

  it('reports an unresolved signal by its status', () => {
    const [entry] = toOrbFeedEntries({
      signals: [{ underlying: 'NIFTY', status: 'signal_unresolved', signal: null, trade_error: 'No liquid CE contracts satisfy expiry and liquidity settings' }],
    });
    expect(entry.state).toBe('SIGNAL_UNRESOLVED');
    expect(entry.reason).toContain('No liquid CE contracts');
  });
});

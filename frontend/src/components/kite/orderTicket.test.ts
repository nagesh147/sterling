import { describe, it, expect } from 'vitest';
import { needsAmo, resolveVariety, chargeLines } from './orderTicket';

describe('needsAmo', () => {
  it('is false when the market is open', () => {
    expect(needsAmo(true)).toBe(false);
  });
  it('is true when the market is closed', () => {
    expect(needsAmo(false)).toBe(true);
  });
  it('is false when market state is unknown (undefined)', () => {
    expect(needsAmo(undefined)).toBe(false);
  });
});

describe('resolveVariety', () => {
  it('resolves to regular when the market is open', () => {
    expect(resolveVariety(true)).toBe('regular');
  });
  it('resolves to amo when the market is closed', () => {
    expect(resolveVariety(false)).toBe('amo');
  });
  it('resolves to regular when market state is unknown', () => {
    expect(resolveVariety(undefined)).toBe('regular');
  });
});

describe('chargeLines', () => {
  it('returns undefined for a null charges object', () => {
    expect(chargeLines(null)).toBeUndefined();
  });

  it('returns undefined for an undefined charges object', () => {
    expect(chargeLines(undefined)).toBeUndefined();
  });

  it('formats a flat numeric field', () => {
    expect(chargeLines({ brokerage: 20 })).toBe('brokerage: 20.00');
  });

  it('unwraps a nested object field down to its own .total', () => {
    expect(chargeLines({ gst: { igst: 0, cgst: 1.8, sgst: 1.8, total: 3.6 } })).toBe('gst: 3.60');
  });

  it('excludes the grand total key', () => {
    expect(chargeLines({ brokerage: 20, total: 45.5 })).toBe('brokerage: 20.00');
  });

  it('returns undefined when only the total key is present (no line items)', () => {
    expect(chargeLines({ total: 42.5 })).toBeUndefined();
  });

  it('excludes a non-numeric string field (e.g. transaction_tax_type)', () => {
    expect(chargeLines({ transaction_tax_type: 'stt', brokerage: 20 })).toBe('brokerage: 20.00');
  });

  it('excludes NaN values instead of rendering the literal string "NaN"', () => {
    expect(chargeLines({ brokerage: NaN, stamp_duty: 5 })).toBe('stamp_duty: 5.00');
  });

  it('joins multiple line items with newlines, preserving insertion order', () => {
    expect(chargeLines({ brokerage: 20, stamp_duty: 5, gst: { total: 3.6 }, total: 28.6 }))
      .toBe('brokerage: 20.00\nstamp_duty: 5.00\ngst: 3.60');
  });
});

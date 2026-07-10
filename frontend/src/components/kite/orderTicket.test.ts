import { describe, it, expect } from 'vitest';
import { needsAmo, resolveVariety } from './orderTicket';

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

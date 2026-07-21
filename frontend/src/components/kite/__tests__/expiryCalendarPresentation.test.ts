import { describe, expect, it } from 'vitest';
import type { ExpiryCalendarEntry } from '../../../types/kiteEngine';
import {
  expiryContractsForRank,
  expiryLabelsForRank,
  formatExpiryDate,
  ordinalDay,
} from '../expiryCalendarPresentation';

const indices: ExpiryCalendarEntry[] = [
  {
    name: 'NIFTY',
    display_name: 'NIFTY 50',
    weekly: ['2026-07-21', '2026-08-04'],
    monthly: ['2026-07-28', '2026-08-25'],
  },
  {
    name: 'SENSEX',
    display_name: 'SENSEX',
    weekly: ['2026-07-23'],
    monthly: ['2026-07-30', '2026-08-27'],
  },
];

describe('expiry calendar presentation', () => {
  it('formats every ordinal edge correctly', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31].map(ordinalDay)).toEqual([
      '1st', '2nd', '3rd', '4th', '11th', '12th', '13th',
      '21st', '22nd', '23rd', '31st',
    ]);
  });

  it('adds a year only when the expiry crosses the as-of year', () => {
    expect(formatExpiryDate('2026-07-21', '2026-07-20')).toBe('21st Jul');
    expect(formatExpiryDate('2027-01-26', '2026-12-20')).toBe('26th Jan 2027');
    expect(formatExpiryDate('not-a-date', '2026-07-20')).toBe('');
  });

  it('renders exact weekly and monthly instrument labels without rank codes', () => {
    const weekly = expiryLabelsForRank(indices, 'weekly', 0, '2026-07-21');
    const monthly = expiryLabelsForRank(indices, 'monthly', 0, '2026-07-21');

    expect(weekly).toEqual(['NIFTY · 21st Jul', 'SENSEX · 23rd Jul']);
    expect(monthly).toEqual(['NIFTY JUL · 28th Jul', 'SENSEX JUL · 30th Jul']);
    expect([...weekly, ...monthly].join(' ')).not.toMatch(/\b[WM][1-4]\b/);
  });

  it('provides structured symbol, month and date fields for the responsive cards', () => {
    expect(expiryContractsForRank(indices, 'monthly', 1, '2026-07-21')).toEqual([
      {
        expiry: '2026-08-25',
        owner: 'NIFTY',
        month: 'AUG',
        date: '25th Aug',
        label: 'NIFTY AUG · 25th Aug',
        instrumentCount: 1,
      },
      {
        expiry: '2026-08-27',
        owner: 'SENSEX',
        month: 'AUG',
        date: '27th Aug',
        label: 'SENSEX AUG · 27th Aug',
        instrumentCount: 1,
      },
    ]);
  });

  it('collapses stocks sharing the same concrete expiry date', () => {
    const stocks: ExpiryCalendarEntry[] = [
      { name: 'RELIANCE', display_name: 'RELIANCE', weekly: [], monthly: ['2026-07-28'] },
      { name: 'TCS', display_name: 'TCS', weekly: [], monthly: ['2026-07-28'] },
    ];
    expect(expiryContractsForRank(stocks, 'monthly', 0, '2026-07-21', true)).toEqual([
      {
        expiry: '2026-07-28',
        owner: '2 STOCKS',
        month: 'JUL',
        date: '28th Jul',
        label: '2 STOCKS JUL · 28th Jul',
        instrumentCount: 2,
      },
    ]);
  });

  it('omits a private rank when Kite lists no contract for it', () => {
    expect(expiryContractsForRank(indices, 'weekly', 3, '2026-07-21')).toEqual([]);
  });
});

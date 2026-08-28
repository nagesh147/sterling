/**
 * A parent row's time.
 *
 * Two halves, each earning its place: the absolute stamp is what you quote when
 * reconciling against the broker's own log, so it carries the date and the year
 * and stands alone; the relative one is what you read while trading, because
 * "17 min ago" answers "is this still worth acting on" and a wall-clock time does
 * not at a glance.
 *
 * IST is pinned rather than inherited. The machine's zone is not the market's,
 * and a stamp that silently shifts by five and a half hours is worse than no
 * stamp at all — that exact class of bug was fixed elsewhere in this codebase by
 * pinning `Asia/Kolkata` in the other time formatters.
 */
import { describe, it, expect } from 'vitest';
import { parentStamp } from '../boardTypes';

/** 09:15 IST on 21 Jul 2026 — the market open, expressed in UTC. */
const IST_OFFSET = (5 * 60 + 30) * 60_000;
const AT = Date.UTC(2026, 6, 21, 9, 15) - IST_OFFSET;

describe('parentStamp', () => {
  it('formats the moment as day, month, year and a 12-hour clock', () => {
    const s = parentStamp(AT, AT);
    expect(s!.absolute).toBe('21 Jul 2026 09:15 AM');
  });

  it('reads as one stamp, not a date bolted to a time', () => {
    // en-IN yields "21 Jul 2026, 09:15 am"; the comma goes and the marker rises.
    const s = parentStamp(AT, AT);
    expect(s!.absolute).not.toContain(',');
    expect(s!.absolute).not.toContain('am');
  });

  it('is in IST regardless of the machine, not the machine’s zone', () => {
    // 09:15 IST is 03:45 UTC. If the zone were inherited this would drift.
    const s = parentStamp(AT, AT);
    expect(s!.absolute).toContain('09:15');
  });

  it('counts minutes, then hours, then days', () => {
    expect(parentStamp(AT, AT + 17 * 60_000)!.relative).toBe('17 min ago');
    expect(parentStamp(AT, AT + 3 * 3600_000)!.relative).toBe('3 h ago');
    expect(parentStamp(AT, AT + 2 * 86_400_000)!.relative).toBe('2 d ago');
  });

  it('says "just now" under a minute rather than "0 min ago"', () => {
    expect(parentStamp(AT, AT + 20_000)!.relative).toBe('just now');
  });

  it('refuses to age a signal stamped in the future', () => {
    // That is a clock problem, not an age. "in 3 min" would present it as normal.
    const s = parentStamp(AT, AT - 3 * 60_000);
    expect(s!.relative).toBeNull();
    expect(s!.absolute, 'the moment is still stated').toContain('21 Jul 2026');
  });

  it('is null when there is no time at all', () => {
    expect(parentStamp(null, AT)).toBeNull();
    expect(parentStamp(Number.NaN, AT)).toBeNull();
  });
});

import { useQuery } from '@tanstack/react-query';

export interface AvailableDates {
  dates: string[];
  instrument: string;
  resolution: string;
  /** `fallback` means the endpoint INVENTED these dates because the candle
   *  store was empty. Presenting them as "sessions with data" would be a lie
   *  told on the backend's behalf. */
  source: 'store' | 'fallback';
  earliest?: string | null;
  latest?: string | null;
  holidays_filtered?: boolean;
}

/**
 * The set of dates the candle store can actually replay.
 *
 * The endpoint existed and was never called, so the date inputs were unbounded
 * and a user could pick a Sunday and only find out by pressing play.
 */
export function useAvailableDates(instrument = 'NIFTY', resolution = '5m') {
  return useQuery<AvailableDates>({
    queryKey: ['replay', 'available-dates', instrument, resolution],
    queryFn: async () => {
      const res = await fetch(
        `/api/v1/simulation/available-dates?instrument=${encodeURIComponent(instrument)}&resolution=${encodeURIComponent(resolution)}`,
      );
      if (!res.ok) throw new Error('available-dates failed');
      return res.json();
    },
    staleTime: 15 * 60_000,
    retry: 1,
  });
}

export type DateVerdict =
  | { level: 'ok' }
  | { level: 'warn'; message: string }
  | { level: 'error'; message: string };

/** Validate a chosen date against what the store says it holds. */
export function verdictForDate(
  date: string,
  data: AvailableDates | undefined,
): DateVerdict {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return { level: 'error', message: 'Enter a date as YYYY-MM-DD.' };
  }
  if (!data) return { level: 'ok' };
  if (data.source === 'fallback') {
    // Warn, never block: with an empty store the fallback is all there is, and
    // the runner can still synthesise a session.
    return {
      level: 'warn',
      message: 'The candle store is empty, so these dates are unverified.',
    };
  }
  if (!data.dates.includes(date)) {
    return { level: 'warn', message: `No stored candles for ${date}.` };
  }
  return { level: 'ok' };
}

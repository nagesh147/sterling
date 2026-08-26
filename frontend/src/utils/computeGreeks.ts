import { parseInstrument } from '../components/kite/InstrumentLabel';
import { blackScholesGreeks, impliedVol } from './blackScholes';

export interface ComputedGreeks {
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  lot_size: number | null;
}

/** Map option underlying names to their Kite index display names for spot lookup. */
const UNDERLYING_SPOT_NAME: Record<string, string> = {
  NIFTY: 'NIFTY 50',
  BANKNIFTY: 'NIFTY BANK',
  FINNIFTY: 'NIFTY FIN SERVICE',
  MIDCPNIFTY: 'NIFTY MID SELECT',
  SENSEX: 'SENSEX',
  BANKEX: 'BANKEX',
};

/**
 * Given an option tradingsymbol, return the Kite quote key for its underlying spot.
 * e.g. "NIFTY25JUN22000CE" → "NSE:NIFTY 50"
 */
export function underlyingSpotKey(optionTradingsymbol: string): string | null {
  const parsed = parseInstrument(optionTradingsymbol);
  if (!parsed?.underlying) return null;
  const spotName = UNDERLYING_SPOT_NAME[parsed.underlying] ?? parsed.underlying;
  const exch = parsed.underlying === 'SENSEX' || parsed.underlying === 'BANKEX' ? 'BSE' : 'NSE';
  return `${exch}:${spotName}`;
}

/** Fractional days to the 15:30 IST expiry CLOSE.
 *
 *  Both call sites used to build the expiry at midnight and clamp at 0, so from 00:00
 *  on expiry day every leg came back with dte = 0 — which is the degenerate branch of
 *  `blackScholesGreeks`: delta hardcoded to ±1.00 or 0, IV unsolvable. The board then
 *  lost every Δ readout and both strike badges for the whole session, on the option's
 *  highest-volume day, while the detail pane (fixed server-side with the same 15:30
 *  close) went on showing them. Two panes, one contract, different greeks.
 *
 *  Built in UTC on purpose: 15:30 IST is 10:00 UTC, so a browser in another timezone
 *  gets the same answer rather than greeks that depend on where it is running.
 */
export function dteDaysToExpiryClose(
  year: number, monthIndex: number, day: number, now: number = Date.now(),
): number {
  const close = Date.UTC(year, monthIndex, day, 10, 0, 0);
  return Math.max(0, (close - now) / (1000 * 60 * 60 * 24));
}

function parseExpiry(parsed: ReturnType<typeof parseInstrument>): Date | null {
  if (!parsed?.month || !parsed.year) return null;
  try {
    const monthMap: Record<string, number> = {
      JAN: 0, FEB: 1, MAR: 2, APR: 3, MAY: 4, JUN: 5,
      JUL: 6, AUG: 7, SEP: 8, OCT: 9, NOV: 10, DEC: 11,
    };
    const mon = monthMap[parsed.month.toUpperCase()];
    const yr = 2000 + parseInt(parsed.year, 10);
    if (isNaN(mon) || isNaN(yr)) return null;
    return parsed.day
      ? new Date(yr, mon, parsed.day)
      : new Date(yr, mon + 1, 0);
  } catch {
    return null;
  }
}

function extractIv(
  quote: Record<string, any> | undefined,
  spot: number,
  strike: number,
  dte: number,
  optionType: string,
): number {
  // Try Kite's own IV first
  const raw = quote?.['implied_volatility'];
  if (raw != null) {
    const v = parseFloat(String(raw));
    if (!isNaN(v) && v > 0) return v / 100;
  }
  // Fall back to backsolving from last traded price
  const ltp = quote?.['last_price'];
  if (ltp != null) {
    const price = parseFloat(String(ltp));
    if (!isNaN(price) && price > 0) {
      return impliedVol({ spot, strike, dteDays: dte, optionType, price });
    }
  }
  return 0;
}

/**
 * Compute greeks for a watchlist option item given the symbol, its quote, and
 * LTP data keyed by instrument symbol (used to resolve the underlying spot).
 */
export function computeGreeksFromSymbol(
  symbol: string,
  quote: Record<string, any> | undefined,
  ltp: Record<string, Record<string, any>> | undefined,
): ComputedGreeks | null {
  const parts = symbol.split(':');
  const rawTs = parts.length > 1 ? parts[1] : symbol;
  const parsed = parseInstrument(rawTs);
  if (!parsed?.strike || !parsed.type || !parsed.month || !parsed.year) return null;

  const strike = parseFloat(parsed.strike);
  if (isNaN(strike) || strike <= 0) return null;

  const optionType = parsed.type.toUpperCase();
  if (optionType !== 'CE' && optionType !== 'PE') return null;

  const spotKey = underlyingSpotKey(rawTs);
  let spot: number | null = null;
  if (spotKey && ltp) {
    spot = ltp[spotKey]?.last_price ?? null;
  }
  if (spot == null || spot <= 0) return null;

  const expiry = parseExpiry(parsed);
  if (!expiry) return null;
  const dte = dteDaysToExpiryClose(expiry.getFullYear(), expiry.getMonth(), expiry.getDate());

  const iv = extractIv(quote, spot, strike, dte, optionType);
  const g = blackScholesGreeks({ spot, strike, dteDays: dte, iv, optionType });
  return { iv, ...g, lot_size: null };
}

/**
 * Compute greeks from SterlingKiteEngine OptionLeg data with spot + quote.
 */
export function computeGreeksFromLeg(
  strike: number,
  expiryStr: string,
  optionType: string,
  spot: number,
  quote: Record<string, any> | undefined,
  lotSize: number | null,
): ComputedGreeks | null {
  if (!strike || strike <= 0 || !spot || spot <= 0) return null;

  let dte = 0;
  // Parsed field-by-field rather than through `new Date(str)`: an ISO date string is
  // parsed as UTC midnight, and reading local getters off it lands on the previous
  // calendar day in any negative-offset timezone.
  const ymd = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(expiryStr || ''));
  if (!ymd) return null;
  dte = dteDaysToExpiryClose(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3]));

  const iv = extractIv(quote, spot, strike, dte, optionType);
  const g = blackScholesGreeks({ spot, strike, dteDays: dte, iv, optionType });
  return { iv, ...g, lot_size: lotSize };
}

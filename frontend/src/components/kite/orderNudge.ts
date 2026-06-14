/**
 * Order "nudges" — Zerodha blocks (or warns on) fresh orders in certain illiquid
 * F&O contracts. The Kite web terminal surfaces this as a "Nudge" popup; we mirror
 * it so the user is warned (and the Buy/Sell is blocked) before a guaranteed
 * server-side rejection.
 *
 * The canonical list lives with Zerodha and changes over time; this is the subset
 * we can detect from the tradingsymbol. Extend BLOCKED_FNO_UNDERLYINGS as needed.
 */
export interface OrderNudge {
  message: string;
  blocked: boolean;   // true → Zerodha rejects the order outright
}

// Underlyings whose F&O contracts Zerodha blocks for illiquidity.
const BLOCKED_FNO_UNDERLYINGS = ['SENSEX50'];

/** True for a futures/options tradingsymbol (ends in FUT / CE / PE). */
export function isFnoSymbol(tradingsymbol: string): boolean {
  const ts = (tradingsymbol || '').toUpperCase().replace(/(BFO|NFO)$/, '');
  return /(FUT|CE|PE)$/.test(ts);
}

export function getOrderNudge(tradingsymbol: string, exchange: string): OrderNudge | null {
  const ts = (tradingsymbol || '').toUpperCase();
  const ex = (exchange || '').toUpperCase();
  if ((ex === 'BFO' || ex === 'NFO') && isFnoSymbol(ts)) {
    for (const u of BLOCKED_FNO_UNDERLYINGS) {
      if (ts.startsWith(u)) {
        return { message: `Orders are blocked for ${u} F&O contracts due to illiquidity.`, blocked: true };
      }
    }
  }
  return null;
}

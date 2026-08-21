/**
 * ATM Premium Imbalance session -> BoardSignal.
 *
 * One row per session, not per signal: this strategy watches exactly one option
 * pair and takes at most one trade, so a feed of rows would be a feed of one.
 *
 * Two things it puts on the board that the other engines have no equivalent for:
 *
 *  - the **premium comparison** itself, which is the whole thesis. `|PE - CE|`
 *    and which leg is cheaper is the signal, so it belongs in the detail rather
 *    than being implied by a score.
 *  - **quote provenance**. This strategy was reconstructed from a bot that
 *    priced an entry off a previous session's last-traded price, so whether each
 *    leg's quote is dated inside the session is operational information, not a
 *    diagnostic. A board that shows a quiet engine without saying "refusing a
 *    carried-over price" cannot be acted on.
 */
import type {
  BoardInstrument, BoardSection, BoardSignal, BoardStatus,
} from './boardTypes';
import type { AtmPremiumImbalanceSnapshot, AtmSessionStatus, AtmLegState } from '../../../hooks/useAtmPremiumImbalance';

/** A tradable price, or nothing. Zero is not a level. */
const price = (v: number | null | undefined): number | null =>
  v == null || !Number.isFinite(v) || v <= 0 ? null : v;

const n2 = (v: number | null | undefined): string | undefined =>
  v == null || !Number.isFinite(v) ? undefined : v.toFixed(2);

function status(session: AtmSessionStatus): BoardStatus {
  switch (session.phase) {
    case 'halted': return 'error';
    case 'in_position': return 'running';
    case 'exiting': return 'weakening';
    case 'entering': return 'armed';
    case 'done': return 'ended';
    case 'armed':
      return session.signal?.action && session.signal.action !== 'NO_TRADE' ? 'armed' : 'watching';
    default: return 'watching';
  }
}

/** Which leg the row is about: the traded one, else the one that would be. */
function activeLeg(session: AtmSessionStatus): AtmLegState | null {
  const want = session.trade?.option ?? session.cheaper_leg ?? null;
  if (!want) return null;
  return session.legs?.[want] ?? null;
}

function instrument(session: AtmSessionStatus, leg: AtmLegState | null): BoardInstrument {
  const strike = session.strike ?? null;
  // Before either leg is chosen the row is honestly about the pair, not a
  // contract: naming one leg would imply a decision that has not been made.
  const symbol = leg?.tradingsymbol
    ?? `${session.underlying} ${strike ?? ''} ${session.expiry ?? ''} (CE/PE pending)`.replace(/\s+/g, ' ').trim();
  return {
    symbol,
    exchange: 'BFO',
    kind: 'option',
    optionType: leg?.option_type ?? undefined,
    strike,
    expiry: session.expiry ?? null,
    lotSize: leg?.lot_size ?? null,
    quoteKey: leg?.tradingsymbol ? `BFO:${leg.tradingsymbol}` : null,
  };
}

/** Human phrase for why nothing is happening. Never left blank. */
function reason(session: AtmSessionStatus, blockers: readonly string[]): string | null {
  if (session.halt_reason) return `Halted: ${session.halt_reason}`;
  const r = session.signal?.reason;
  if (r === 'stale_session_quote') return 'Refusing a quote that traded before today’s open';
  if (r === 'undatable_quote') return 'Feed sent no trade time — cannot date the quote';
  if (r === 'stale_quote') return 'Quote older than the freshness limit';
  if (r === 'equal_premiums') return 'CE and PE are equal — no cheaper leg';
  if (r === 'no_quote_pair') return 'Waiting for both legs to quote';
  if (r === 'session_trade_limit_reached') return 'Session trade limit reached';
  if (r === 'position_open') return 'Position already open';
  if (r === 'below_minimum_difference') return 'Premium gap below the configured minimum';
  if (r) return r;
  if (blockers.length) return blockers[0];
  return session.armed ? 'Armed, waiting for the open' : null;
}

function originLabel(v: boolean | null | undefined): string {
  if (v === true) return 'this session';
  if (v === false) return 'PREVIOUS session';
  return 'unknown';
}

function comparisonSection(session: AtmSessionStatus): BoardSection {
  const ce = session.legs?.CE, pe = session.legs?.PE;
  return {
    title: 'Premium comparison',
    layout: 'tiles',
    summary: session.quote_mode,
    stats: [
      { label: 'CE', value: n2(ce?.ltp), hint: 'At-the-money call premium' },
      { label: 'PE', value: n2(pe?.ltp), hint: 'At-the-money put premium' },
      { label: 'Difference', value: n2(session.difference), hint: 'Absolute gap, |PE − CE|' },
      { label: 'Cheaper', value: session.cheaper_leg ?? undefined, hint: 'The leg the strategy buys' },
      { label: 'Strike', value: session.strike == null ? undefined : String(session.strike), hint: 'Nearest listed strike to the index' },
      { label: 'Expiry', value: session.expiry ?? undefined },
    ],
  };
}

/**
 * Whether each quote can be traded on at all.
 *
 * `PREVIOUS session` here is the exact condition that made the source bot price
 * an entry 16.9% through the real open, so it is surfaced rather than buried.
 */
function provenanceSection(session: AtmSessionStatus): BoardSection {
  const ce = session.legs?.CE, pe = session.legs?.PE;
  const fmt = (ms: number | null | undefined) =>
    ms == null ? undefined : new Date(ms).toLocaleTimeString('en-IN', { hour12: false, timeZone: 'Asia/Kolkata' });
  return {
    title: 'Quote provenance',
    layout: 'rows',
    summary: 'a price that traded before the open cannot open a position',
    stats: [
      { label: 'CE last trade', value: fmt(ce?.last_trade_ts_ms), hint: 'Exchange time of the trade behind the CE price' },
      { label: 'CE traded in', value: originLabel(ce?.session_origin) },
      { label: 'PE last trade', value: fmt(pe?.last_trade_ts_ms) },
      { label: 'PE traded in', value: originLabel(pe?.session_origin) },
      { label: 'CE exch. open', value: n2(ce?.official_open), hint: 'Published open, withheld until the leg trades today' },
      { label: 'PE exch. open', value: n2(pe?.official_open) },
    ],
  };
}

function tradeSection(session: AtmSessionStatus): BoardSection | null {
  const t = session.trade;
  if (!t) return null;
  return {
    title: 'Trade',
    layout: 'rows',
    summary: `${t.attempts ?? 0} entry attempt(s)`,
    stats: [
      { label: 'Priced from', value: n2(t.first_tick_price), hint: 'The reference the order price was derived from' },
      { label: 'Order price', value: n2(t.entry_order_price), hint: 'Limit sent to the broker' },
      { label: 'Fill', value: n2(t.entry), hint: 'Broker average — what the target is measured from' },
      { label: 'Target', value: n2(t.target) },
      { label: 'Trigger', value: n2(t.trigger), hint: 'The tick that crossed the target' },
      { label: 'Exit limit', value: n2(t.exit_order_price), hint: 'Best bid minus the exit buffer' },
      { label: 'Exit fill', value: n2(t.exit) },
      { label: 'Points', value: n2(t.points) },
      { label: 'P&L', value: t.pnl == null ? undefined : `₹${t.pnl.toFixed(2)}` },
      { label: 'Slippage vs target', value: n2(t.slippage_vs_target) },
    ],
  };
}

function protectionSection(session: AtmSessionStatus): BoardSection | null {
  const p = session.trade?.protection;
  if (!p && session.protection_mode === 'NONE') {
    return {
      title: 'Protection',
      layout: 'rows',
      summary: 'reproduces the observed bot, which had none',
      stats: [{ label: 'Mode', value: 'NONE', hint: 'If this process dies while holding, nothing exits' }],
    };
  }
  if (!p) return null;
  return {
    title: 'Protection',
    layout: 'rows',
    stats: [
      { label: 'Mode', value: p.kind },
      { label: 'State', value: p.state },
      { label: 'Resting at', value: n2(p.limit_price), hint: 'Sell parked at the exchange' },
      { label: 'Order id', value: p.order_id ?? undefined },
    ],
  };
}

export function atmPremiumImbalanceToBoard(
  snapshot: AtmPremiumImbalanceSnapshot | undefined,
): BoardSignal[] {
  const session = snapshot?.session;
  if (!session) return [];
  const leg = activeLeg(session);
  const t = session.trade;
  const qty = t?.quantity ?? session.quantity ?? null;
  const lotSize = leg?.lot_size ?? null;
  const entry = price(t?.entry);

  const sections = [
    comparisonSection(session),
    provenanceSection(session),
    tradeSection(session),
    protectionSection(session),
  ].filter((s): s is BoardSection => s != null);

  return [{
    id: `api-${session.session_date}-${session.strike ?? 'x'}`,
    engine: 'atm_premium_imbalance',
    underlying: session.underlying,
    instrument: instrument(session, leg),
    direction: 'long',                       // it only ever buys an option
    status: status(session),
    atMs: session.session_open_ms ?? null,
    levels: {
      ltp: price(leg?.ltp),
      entry,
      // No stop and no trail were ever observed, so the columns stay empty
      // rather than showing a number the strategy does not have.
      stop: null,
      trail: null,
      target: price(t?.target),
      exit: price(t?.exit),
    },
    sizing: {
      lots: qty != null && lotSize ? qty / lotSize : null,
      quantity: qty,
      // A bought option risks its whole premium, so at-risk is the outlay.
      atRiskInr: entry != null && qty != null ? entry * qty : null,
      deployedInr: entry != null && qty != null ? entry * qty : null,
    },
    score: null,                             // the engine publishes none
    reason: reason(session, snapshot?.blockers ?? []),
    quoteAgeS: leg?.age_ms == null ? null : leg.age_ms / 1000,
    sections,
  }];
}

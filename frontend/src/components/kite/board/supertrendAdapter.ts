/**
 * SuperTrend and Navigator rows -> BoardSignal.
 *
 * One adapter for two engines because they share a row type: a Navigator
 * signal is an `EngineSignalRow` with `source === 'navigator'`, produced from
 * its own AVWAP evidence with no SuperTrend trigger at all. They differ in what
 * they can fill, and that difference is honest rather than cosmetic:
 *
 *   SuperTrend  trails, and quotes no target — it is trend-following, so it
 *               exits on the red counter or the trail, never at a fixed level.
 *   Navigator   quotes a stop/target bracket up front and does not run a red
 *               counter.
 *
 * The board drops whichever column is empty, so neither engine implies it
 * forgot to fill in the other's field.
 *
 * A row carries one leg per moneyness. The board shows a signal per leg,
 * because a leg is what actually gets bought — the parent row is a thesis, not
 * an order.
 */
import type { AlignmentChip, EngineSignalRow, OptionLeg } from '../../../types/kiteEngine';
import { k } from '../../../styles/kiteUI';
import type { BoardOrigin, BoardSection, BoardSignal, BoardStatus, EngineId } from './boardTypes';

/**
 * A tradable price, or nothing.
 *
 * A premium of zero is not a level. A feed emitting `0` for "no stop set"
 * renders as a "0.00" stop indistinguishable from a real one, which on a bought
 * option is the difference between a protected position and an unprotected one.
 */
const price = (v: number | null | undefined): number | null =>
  v == null || !Number.isFinite(v) || v <= 0 ? null : v;

/**
 * Which scan surfaced this signal.
 *
 * "Both agree" is the one worth distinguishing: in derivatives mode a single
 * contract can produce a spot row AND a premium row with different entries,
 * and without this they read as a duplicate.
 */
function originOf(row: EngineSignalRow): BoardOrigin | undefined {
  switch (row.source) {
    case 'spot':
      return { label: 'SPOT', tone: 'brand', hint: "Read from the underlying's own chart. The option legs are candidates to buy." };
    case 'derivatives':
      return { label: 'PREMIUM', tone: 'blue', hint: "Read from this option's own premium chart." };
    case 'confluence':
      return { label: 'BOTH AGREE', tone: 'green', hint: "The underlying fired and this option's own premium confirmed it." };
    case 'navigator':
      return { label: 'NAVIGATOR', tone: 'purple', hint: "Found by the Value-Flow Navigator from its own AVWAP and flow evidence — no SuperTrend trigger at all." };
    default:
      return undefined;
  }
}

const engineOf = (row: EngineSignalRow): EngineId =>
  row.source === 'navigator' ? 'navigator' : 'supertrend';

/**
 * Where the trade is in its life.
 *
 * `is_active` means the trend held on every bar since entry, and `is_fresh`
 * means it entered on the latest closed bar — so fresh-and-active is the only
 * combination that is a call to action rather than a running position.
 */
function status(row: EngineSignalRow, leg: OptionLeg): BoardStatus {
  if (row.exit_reason) return 'ended';
  const active = leg.is_active ?? row.is_active ?? false;
  if (!active) return 'ended';
  if (row.is_fresh) return 'armed';
  // The red counter is the exit rule counting against an open position:
  // anything above zero means the thesis is being withdrawn.
  const reds = Number((leg.exit_state ?? row.exit_state ?? '').split('/')[0]);
  return Number.isFinite(reds) && reds > 0 ? 'weakening' : 'running';
}

/** Trend evidence — what the engine saw, as opposed to what it decided. */
function evidenceSection(row: EngineSignalRow): BoardSection {
  return {
    title: 'Trend & volatility',
    layout: 'tiles',
    summary: row.regime,
    stats: [
      { label: 'Spot', value: row.spot?.toFixed(2), hint: 'Underlying price at signal time' },
      { label: 'Score', value: row.score?.toFixed(0), hint: 'Engine conviction, 0-100' },
      { label: 'ADX', value: row.adx == null ? undefined : row.adx.toFixed(1), hint: 'Trend strength at signal time' },
      { label: 'ATR pct', value: row.atr_pct == null ? undefined : `${row.atr_pct.toFixed(0)}%`, hint: 'Volatility rank against recent history' },
      { label: 'Alignment', value: alignmentText(row.alignment), hint: 'Fast / mid / slow SuperTrend, in that order' },
      { label: 'Regime', value: row.regime },
      { label: 'Source', value: row.source ?? undefined, hint: 'Which scan surfaced this — spot, derivatives, confluence or Navigator' },
      { label: 'Moneyness', value: leg_moneyness(row) },
    ],
  };
}

const leg_moneyness = (row: EngineSignalRow) => row.legs?.[0]?.moneyness;

/** The three lines as arrows, in fast/mid/slow order. */
function alignmentText(chip: AlignmentChip | null | undefined): string | undefined {
  if (!chip) return undefined;
  const arrow = (v: number) => (v > 0 ? '▲' : v < 0 ? '▼' : '·');
  return `${arrow(chip.fast)}${arrow(chip.mid)}${arrow(chip.slow)}`;
}

/**
 * How the position ends.
 *
 * The red counter and the trailing stop are independent rules and either can
 * close a trade, so the counter alone cannot explain an ended row — which is
 * why `exit_reason` is shown beside it rather than instead of it.
 */
function exitSection(row: EngineSignalRow, leg: OptionLeg): BoardSection | null {
  const exitState = leg.exit_state ?? row.exit_state;
  if (!exitState && !row.exit_reason && row.target == null) return null;
  return {
    title: 'Exit rule',
    layout: 'rows',
    summary: exitState ?? undefined,
    stats: [
      { label: 'Red counter', value: exitState ?? '—', hint: 'SuperTrend lines turned against the position, out of the threshold' },
      { label: 'Why it ended', value: row.exit_reason ?? '—', hint: 'The trail and the counter are separate rules; either can close a trade' },
      { label: 'Underlying target', value: row.target == null ? '—' : row.target.toFixed(2), hint: 'Navigator quotes one; SuperTrend does not' },
      { label: 'Resolution', value: leg.resolution_note ?? row.resolution_reason ?? '—' },
    ],
  };
}

/** Navigator's own decision record, when it produced or annotated the row. */
function navigatorSection(row: EngineSignalRow): BoardSection | null {
  const nav = row.navigator;
  if (!nav) return null;
  return {
    title: 'Navigator decision',
    layout: 'rows',
    summary: nav.status,
    stats: [
      { label: 'Status', value: nav.status },
      {
        label: 'Eligible to execute',
        value: nav.execution_eligible ? 'yes' : 'no',
        color: nav.execution_eligible ? undefined : k.amber,
        hint: 'Navigator can advise without being cleared to trade',
      },
      { label: 'Effective score', value: nav.effective_score?.toFixed(0) ?? '—', hint: 'Base blended with the suite, where the suite ran' },
      { label: 'Base score', value: nav.base_score?.toFixed(0) ?? '—' },
      { label: 'Data quality', value: nav.data_quality, hint: 'Degraded inputs downgrade a decision rather than hiding it' },
      { label: 'Trigger', value: nav.trigger },
      {
        label: 'Reasons',
        value: nav.reason_codes?.length ? nav.reason_codes.join(', ') : '—',
        hint: 'Why Navigator landed on this status',
      },
    ],
  };
}

export function supertrendLegToBoard(row: EngineSignalRow, leg: OptionLeg, index: number): BoardSignal {
  const engine = engineOf(row);
  const atMs = leg.entry_timestamp_ms ?? leg.signal_timestamp_ms ?? row.timestamp_ms ?? null;
  const sections = [evidenceSection(row), exitSection(row, leg), navigatorSection(row)]
    .filter(Boolean) as BoardSection[];
  const quantity = leg.lot_size ?? null;

  return {
    id: `${engine}-${row.underlying}-${leg.option_symbol}-${index}`,
    engine,
    underlying: row.underlying,
    instrument: {
      symbol: leg.option_symbol,
      exchange: row.exchange,
      kind: 'option',
      optionType: (leg.option_type as 'CE' | 'PE') ?? row.option_type,
      strike: leg.strike ?? null,
      expiry: leg.expiry ?? null,
      lotSize: leg.lot_size ?? null,
      moneyness: leg.moneyness ?? null,
      quoteKey: leg.option_symbol ? `${row.exchange}:${leg.option_symbol}` : null,
    },
    direction: row.direction,
    status: status(row, leg),
    atMs,
    levels: {
      ltp: price(leg.premium_spot),
      entry: price(leg.premium_spot),
      // The hard stop set at entry and the ratchet are different numbers, and
      // the board shows both: one says what was risked, the other what is left.
      stop: price(leg.entry_sl),
      trail: price(leg.premium_sl),
      target: price(leg.premium_target),
      exit: null,
    },
    sizing: {
      lots: null,
      quantity,
      // Premium risked per lot, if both ends of the stop are known.
      atRiskInr: price(leg.premium_spot) != null && price(leg.entry_sl) != null && leg.lot_size
        ? Math.max(0, (price(leg.premium_spot)! - price(leg.entry_sl)!) * leg.lot_size)
        : null,
      deployedInr: price(leg.premium_spot) != null && leg.lot_size ? price(leg.premium_spot)! * leg.lot_size : null,
    },
    score: row.score ?? null,
    origin: originOf(row),
    reason: row.exit_reason ?? row.resolution_reason ?? null,
    sections,
  };
}

/**
 * The signal itself: the idea, before it is expressed through any contract.
 *
 * Its price columns stay empty on purpose. The thesis has no premium, and
 * lifting one leg's numbers up to stand for the rest would be a lie about
 * which strike you would actually trade. What the parent does carry is what
 * belongs to the idea and to no single leg — the underlying, the scan that
 * found it, the trend evidence.
 */
function supertrendSignalToBoard(row: EngineSignalRow, legs: BoardSignal[], index: number): BoardSignal {
  const engine = engineOf(row);
  // The group is as live as its liveliest leg: a signal with one running
  // contract is running, even if four others have closed.
  const status = legs.reduce<BoardStatus>(
    (best, leg) => (STATUS_ORDER.indexOf(leg.status) < STATUS_ORDER.indexOf(best) ? leg.status : best),
    legs[0]?.status ?? 'watching',
  );

  return {
    id: `${engine}-${row.underlying}-${row.timestamp_ms}-${index}`,
    engine,
    underlying: row.underlying,
    instrument: {
      // The underlying, not a contract — that is what the row is about.
      symbol: row.underlying,
      exchange: row.exchange,
      kind: 'index',
      strike: null,
      expiry: null,
      lotSize: null,
      quoteKey: null,
    },
    direction: row.direction,
    status,
    atMs: row.timestamp_ms ?? null,
    levels: { ltp: null, entry: null, stop: null, trail: null, target: null, exit: null },
    sizing: { lots: null, quantity: null, atRiskInr: null, deployedInr: null },
    score: row.score ?? null,
    origin: originOf(row),
    reason: row.exit_reason ?? row.resolution_reason ?? null,
    sections: [evidenceSection(row), navigatorSection(row)].filter(Boolean) as BoardSection[],
    children: legs,
  };
}

/** Most-actionable first, so a group takes its liveliest leg's status. */
const STATUS_ORDER: readonly BoardStatus[] = ['armed', 'running', 'weakening', 'watching', 'ended', 'error'];

/**
 * One board row per signal, with its contracts nested underneath.
 *
 * SuperTrend produces around fifty signals carrying nearly three hundred legs
 * — NIFTY alone can be thirty-seven strikes. Flattened, that is a board nobody
 * can read; grouped, it is fifty ideas you can open.
 */
export function supertrendToBoard(rows: readonly EngineSignalRow[]): BoardSignal[] {
  return rows.map((row, i) => {
    const legs = (row.legs ?? []).map((leg, j) => supertrendLegToBoard(row, leg, j));
    return supertrendSignalToBoard(row, legs, i);
  });
}

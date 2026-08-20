/**
 * Adaptive Edge rows -> BoardSignal.
 *
 * Adaptive Edge is the only engine that reasons in two price frames at once: it
 * forms a thesis on the underlying (spot entry, spot stop, POC, session VWAP,
 * cumulative delta) and then expresses it through an option. Both frames are
 * real and a trader needs both, so the option ladder fills the board's columns
 * — those are the prices an order is placed at — and the spot frame becomes its
 * own detail section rather than being flattened into the same columns.
 *
 * That split is the whole reason `sections` exists on BoardSignal. Forcing spot
 * levels into the shared SL column would put two different instruments' prices
 * under one heading.
 */
import type { AdaptiveEdgeRow } from '../AdaptiveEdgePanel';
import type { BoardSection, BoardSignal, BoardStatus } from './boardTypes';

const ms = (iso: string | null | undefined): number | null => {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : t;
};

/**
 * `open` says a position exists; `decision` says what the model wants to do
 * with it. An open row the model has already called EXIT is not "running" —
 * it is a position being withdrawn, and that is the moment worth surfacing.
 */
function status(row: AdaptiveEdgeRow): BoardStatus {
  if (!row.open) return 'ended';
  if (row.decision === 'EXIT') return 'weakening';
  return row.entryTime ? 'running' : 'armed';
}

/** The underlying thesis, in the underlying's own prices. */
function spotSection(row: AdaptiveEdgeRow): BoardSection | null {
  const any = [row.spotEntry, row.spotSl, row.spotTsl, row.poc, row.vwap, row.cvd].some((v) => v != null);
  if (!any) return null;
  const rupees = (v: number | null | undefined, dp = 0) => (v == null ? undefined : `₹${v.toFixed(dp)}`);
  return {
    title: 'Spot microstructure & order flow',
    layout: 'tiles',
    summary: row.horizon ? String(row.horizon) : undefined,
    stats: [
      { label: 'Spot entry', value: rupees(row.spotEntry), hint: 'Underlying level the thesis is anchored to' },
      { label: 'Spot SL', value: rupees(row.spotSl), hint: 'Underlying stop — not the option stop in the SL column' },
      { label: 'Spot TSL', value: rupees(row.spotTsl), hint: 'Where the underlying trail has ratcheted to' },
      { label: 'Spot exit', value: rupees(row.spotExit), hint: 'Underlying level the position closed at' },
      { label: 'POC anchor', value: rupees(row.poc), hint: 'Point of control — the most-traded price of the session' },
      { label: 'Session VWAP', value: rupees(row.vwap, 1), hint: 'Volume-weighted average price so far today' },
      {
        label: 'Order flow CVD',
        value: row.cvd == null ? undefined : `${row.cvd > 0 ? '+' : ''}${Math.round(row.cvd).toLocaleString('en-IN')}`,
        hint: 'Cumulative volume delta — buying minus selling pressure',
      },
      { label: 'Model score', value: row.score == null ? undefined : row.score.toFixed(2), hint: 'Adaptive Edge conviction. Not comparable with another engine’s score' },
      { label: 'Horizon', value: row.horizon ? String(row.horizon) : undefined, hint: 'How long the model expects the move to take' },
    ],
  };
}

/**
 * How the position was classified and whether that changed.
 *
 * A mode that was upgraded mid-trade means the model grew more confident after
 * entry — worth seeing, because the exit rule follows the current mode, not the
 * one the trade was opened under.
 */
function modeSection(row: AdaptiveEdgeRow): BoardSection | null {
  if (!row.entryMode && !row.currentMode) return null;
  const drift = row.modeUpgraded ? 'upgraded' : row.modeDowngraded ? 'downgraded' : undefined;
  return {
    title: 'Mode & lifecycle',
    layout: 'rows',
    summary: drift,
    stats: [
      { label: 'Origin', value: row.origin ?? '—', hint: 'Which scan surfaced this row' },
      { label: 'Entry mode', value: row.entryMode ? String(row.entryMode) : '—' },
      { label: 'Current mode', value: row.currentMode ? String(row.currentMode) : '—', hint: 'The exit rule follows this, not the entry mode' },
      { label: 'Peak mode', value: row.peakMode ? String(row.peakMode) : '—' },
      { label: 'Decision', value: row.decision, hint: 'What the model wants to do with the position right now' },
      { label: 'Feature quality', value: row.featureQuality, hint: 'FLAT means the inputs went stale, so the decision is degraded' },
      { label: 'Why closed', value: row.whyClosed ?? row.resolutionReason ?? '—' },
    ],
  };
}

export function adaptiveEdgeToBoard(row: AdaptiveEdgeRow): BoardSignal {
  const sections = [spotSection(row), modeSection(row)].filter(Boolean) as BoardSection[];
  // A SELL side is a short even when the contract is a call, so the option type
  // alone cannot tell you which way the position leans.
  const direction = row.side === 'SELL' ? 'short' : 'long';

  return {
    id: row.id,
    engine: 'adaptive_edge',
    underlying: row.underlying,
    instrument: {
      symbol: row.instrument,
      exchange: row.exchange,
      kind: row.kind === 'spot' ? 'equity' : 'option',
      optionType: row.kind === 'option' ? row.optionType : undefined,
      strike: row.strike ?? null,
      expiry: row.expiry ?? null,
      lotSize: row.lotSize ?? null,
      quoteKey: row.instrument ? `${row.exchange}:${row.instrument}` : null,
    },
    direction,
    status: status(row),
    atMs: ms(row.entryTime) ?? row.observationTime ?? null,
    levels: {
      ltp: row.ltp,
      entry: row.entry,
      stop: row.sl,
      trail: row.tsl,
      // Adaptive Edge quotes one exit level, which is the planned exit until
      // the row closes and it becomes the realised one.
      target: row.open ? row.exit : null,
      exit: row.open ? null : row.exit,
    },
    sizing: {
      lots: null,
      quantity: row.lotSize ?? null,
      atRiskInr: row.entry != null && row.sl != null && row.lotSize
        ? Math.max(0, (row.entry - row.sl) * row.lotSize)
        : null,
      deployedInr: row.entry != null && row.lotSize ? row.entry * row.lotSize : null,
    },
    score: row.score,
    reason: row.whyClosed ?? row.resolutionReason ?? null,
    sections,
  };
}

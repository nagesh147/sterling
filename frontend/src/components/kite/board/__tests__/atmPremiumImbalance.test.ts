/**
 * ATM Premium Imbalance -> board.
 *
 * The rows this adapter has to get right are the ones that keep an operator from
 * misreading a refusal as an outage: a quote that traded before the open must
 * say so in plain language, and the stop/trail columns must stay empty because
 * the strategy has neither.
 */
import { describe, it, expect } from 'vitest';
import { atmPremiumImbalanceToBoard } from '../atmPremiumImbalanceAdapter';
import type {
  AtmLegState, AtmPremiumImbalanceSnapshot, AtmSessionStatus,
} from '../../../../hooks/useAtmPremiumImbalance';

const IST = (5 * 60 + 30) * 60_000;
/** 2026-08-21 09:15 IST. */
const OPEN = Date.UTC(2026, 7, 21, 9, 15) - IST;

function leg(over: Partial<AtmLegState> = {}): AtmLegState {
  return {
    instrument_id: '212614405', tradingsymbol: 'SENSEX26AUG77700PE', option_type: 'PE',
    lot_size: 20, ltp: 356.7, bid: 356.2, ask: 357.2,
    last_trade_ts_ms: OPEN + 900, session_origin: true, age_ms: 120,
    official_open: 356.7, ...over,
  };
}

function session(over: Partial<AtmSessionStatus> = {}): AtmSessionStatus {
  return {
    armed: true, finished: false, session_date: '2026-08-21', session_open_ms: OPEN,
    phase: 'armed', halt_reason: null, underlying: 'SENSEX', expiry: '2026-08-27',
    strike: 77700, quantity: 80, execution_mode: 'paper', quote_mode: 'COMPATIBILITY',
    protection_mode: 'NONE', trades_taken: 0,
    legs: {
      CE: leg({ option_type: 'CE', tradingsymbol: 'SENSEX26AUG77700CE',
                instrument_id: '212046597', ltp: 500, official_open: 500 }),
      PE: leg(),
    },
    difference: 143.3, cheaper_leg: 'PE',
    signal: { action: 'BUY_PE', reason: 'cheaper_leg=PE', option_type: 'PE' },
    trade: null, ...over,
  };
}

function snap(s: AtmSessionStatus | null, blockers: string[] = []): AtmPremiumImbalanceSnapshot {
  return { strategy: {} as any, config: {} as any, resolved: null, blockers, session: s };
}

describe('atmPremiumImbalanceToBoard', () => {
  it('emits nothing when no session is armed', () => {
    expect(atmPremiumImbalanceToBoard(snap(null))).toEqual([]);
    expect(atmPremiumImbalanceToBoard(undefined)).toEqual([]);
  });

  it('emits exactly one row — this strategy watches one pair', () => {
    expect(atmPremiumImbalanceToBoard(snap(session()))).toHaveLength(1);
  });

  it('describes the pair, not a leg, before either is chosen', () => {
    const [row] = atmPremiumImbalanceToBoard(
      snap(session({ cheaper_leg: null, signal: null, legs: null })));
    expect(row.instrument.symbol).toContain('CE/PE pending');
    expect(row.instrument.optionType).toBeUndefined();
    expect(row.status).toBe('watching');
  });

  it('names the leg it would buy once one is cheaper', () => {
    const [row] = atmPremiumImbalanceToBoard(snap(session()));
    expect(row.instrument.symbol).toBe('SENSEX26AUG77700PE');
    expect(row.instrument.optionType).toBe('PE');
    expect(row.status).toBe('armed');
    expect(row.direction).toBe('long');          // it only ever buys
  });

  it('leaves stop and trail empty because the strategy has neither', () => {
    const [row] = atmPremiumImbalanceToBoard(snap(session()));
    expect(row.levels.stop).toBeNull();
    expect(row.levels.trail).toBeNull();
    expect(row.score).toBeNull();                // publishes no score
  });

  it('puts the premium comparison in the detail, since that IS the thesis', () => {
    const [row] = atmPremiumImbalanceToBoard(snap(session()));
    const cmp = row.sections.find((s) => s.title === 'Premium comparison');
    expect(cmp).toBeDefined();
    const byLabel = Object.fromEntries(cmp!.stats.map((s) => [s.label, s.value]));
    expect(byLabel.CE).toBe('500.00');
    expect(byLabel.PE).toBe('356.70');
    expect(byLabel.Difference).toBe('143.30');
    expect(byLabel.Cheaper).toBe('PE');
  });

  it('says in plain language when a quote traded before the open', () => {
    const stale = session({
      signal: { action: 'NO_TRADE', reason: 'stale_session_quote', option_type: null },
      legs: {
        CE: leg({ option_type: 'CE', session_origin: false }),
        PE: leg({ session_origin: false }),
      },
    });
    const [row] = atmPremiumImbalanceToBoard(snap(stale));
    expect(row.reason).toBe('Refusing a quote that traded before today’s open');
    const prov = row.sections.find((s) => s.title === 'Quote provenance');
    const vals = prov!.stats.map((s) => s.value);
    expect(vals).toContain('PREVIOUS session');
  });

  it('distinguishes an undatable quote from a stale one', () => {
    const undatable = session({
      signal: { action: 'NO_TRADE', reason: 'undatable_quote', option_type: null },
      legs: { CE: leg({ option_type: 'CE', session_origin: null }), PE: leg({ session_origin: null }) },
    });
    const [row] = atmPremiumImbalanceToBoard(snap(undatable));
    expect(row.reason).toContain('no trade time');
    const prov = row.sections.find((s) => s.title === 'Quote provenance');
    expect(prov!.stats.map((s) => s.value)).toContain('unknown');
  });

  it('never leaves a quiet row without a reason', () => {
    const [row] = atmPremiumImbalanceToBoard(
      snap(session({ signal: null, cheaper_leg: null }), ['quantity not set']));
    expect(row.reason).toBe('quantity not set');
  });

  it('reports an open position with its ladder and outlay', () => {
    const open = session({
      phase: 'in_position',
      trade: {
        state: 'open', option: 'PE', strike: 77700, quantity: 80,
        first_tick_price: 356.7, entry_order_price: 392.4, entry: 340.1,
        target: 355.1, trigger: null, exit_order_price: null, exit: null,
        points: null, pnl: null, slippage_vs_target: null, attempts: 1,
        quote_mode: 'COMPATIBILITY', halt_reason: null, protection: null,
      },
    });
    const [row] = atmPremiumImbalanceToBoard(snap(open));
    expect(row.status).toBe('running');
    expect(row.levels.entry).toBe(340.1);
    expect(row.levels.target).toBe(355.1);
    expect(row.sizing.quantity).toBe(80);
    expect(row.sizing.lots).toBe(4);                       // 80 / 20
    // a bought option risks its whole premium
    expect(row.sizing.atRiskInr).toBeCloseTo(340.1 * 80, 6);
    expect(row.sizing.deployedInr).toBeCloseTo(340.1 * 80, 6);
    const trade = row.sections.find((s) => s.title === 'Trade');
    const byLabel = Object.fromEntries(trade!.stats.map((s) => [s.label, s.value]));
    expect(byLabel['Priced from']).toBe('356.70');
    expect(byLabel['Order price']).toBe('392.40');
  });

  it('reports a finished trade as ended, with points and P&L', () => {
    const done = session({
      phase: 'done', finished: true,
      trade: {
        state: 'closed', option: 'PE', strike: 77700, quantity: 80,
        first_tick_price: 356.7, entry_order_price: 392.4, entry: 340.1,
        target: 355.1, trigger: 356.0, exit_order_price: 355.5, exit: 356.85,
        points: 16.75, pnl: 1340.0, slippage_vs_target: 1.75, attempts: 1,
        quote_mode: 'COMPATIBILITY', halt_reason: null, protection: null,
      },
    });
    const [row] = atmPremiumImbalanceToBoard(snap(done));
    expect(row.status).toBe('ended');
    expect(row.levels.exit).toBe(356.85);
    const byLabel = Object.fromEntries(
      row.sections.find((s) => s.title === 'Trade')!.stats.map((s) => [s.label, s.value]));
    expect(byLabel.Points).toBe('16.75');
    expect(byLabel['P&L']).toBe('₹1340.00');
  });

  it('surfaces a halt as an error row with its cause', () => {
    const [row] = atmPremiumImbalanceToBoard(
      snap(session({ phase: 'halted', halt_reason: 'protection_cancel_failed' })));
    expect(row.status).toBe('error');
    expect(row.reason).toContain('protection_cancel_failed');
  });

  it('says so when protection is off rather than omitting the block', () => {
    const [row] = atmPremiumImbalanceToBoard(snap(session()));
    const prot = row.sections.find((s) => s.title === 'Protection');
    expect(prot).toBeDefined();
    expect(prot!.stats[0].value).toBe('NONE');
  });
});

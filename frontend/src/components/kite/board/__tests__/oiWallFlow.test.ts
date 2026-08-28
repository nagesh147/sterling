/**
 * OI Wall Flow -> board.
 *
 * The row this adapter has to get right is the motivating chain: BSE 3500 CE,
 * never a PE. A missing price must render as null, never 0, and a held
 * position must survive its candidate dropping out of the scan.
 */
import { describe, it, expect } from 'vitest';
import { oiWallFlowToBoard } from '../oiWallFlowAdapter';
import type {
  OIWallFlowConfig, OIWallFlowPositionRow, OIWallFlowSignalRow, OIWallFlowSnapshot,
} from '../../../../hooks/useOiWallFlow';

const CFG = {
  enabled: true, skip_atm: true, prefer_wall_strike: true, min_bias_score: 3,
  stop_mode: 'both', stop_premium_pct: 40,
} as unknown as OIWallFlowConfig;

const BROKER = {
  status: 'open' as const, order_id: 'o-1', fill_price: 0, effective_entry: 0,
  gtt_id: 111, stop_mode: 'both' as const,
};

function row(over: Partial<OIWallFlowSignalRow> = {}): OIWallFlowSignalRow {
  return {
    id: 'BSE:2026-09-29',
    state: 'armed', at_ms: 1756360800000, underlying: 'BSE',
    spot: 3392.5, expiry: '2026-09-29', days_to_expiry: 32, reason: null,
    bias: {
      bias: 'bullish', score: 4.5, reasons: ['near-ATM calls covering', 'puts being written'],
      pcr_oi: 0.72, max_pain: 3400, put_wall: 3300, call_wall: 3500, atm_strike: 3400,
    },
    plan: {
      option_type: 'CE', strike: 3500, entry: 84.15, stop: 50.49, target: 126.23,
      target_2: 168.3, underlying_invalidation: 3300, lot_size: 200, quantity: 200,
      lots: 1, reason: 'first-resistance CE at the call wall',
      tradingsymbol: 'BSE26SEP3500CE',
      instrument: {
        instrument_id: '12345', tradingsymbol: 'BSE26SEP3500CE', option_type: 'CE',
        strike: 3500, expiry: '2026-09-29', lot_size: 200, tick_size: 0.05, exchange: 'NFO',
      },
    },
    instrument: {
      instrument_id: '12345', tradingsymbol: 'BSE26SEP3500CE', option_type: 'CE',
      strike: 3500, expiry: '2026-09-29', lot_size: 200, tick_size: 0.05, exchange: 'NFO',
    },
    levels: { ltp: 84.15, entry: 84.15, stop: 50.49, trail: null, target: 126.23, exit: null },
    sizing: { lots: 1, quantity: 200, at_risk_inr: 6732, deployed_inr: 16830 },
    ...over,
  };
}

function snap(over: Partial<OIWallFlowSnapshot> = {}): OIWallFlowSnapshot {
  return {
    strategy: {} as OIWallFlowSnapshot['strategy'],
    config: CFG, scan: {}, session: null,
    candidates: [row()], positions: [], orphan_positions: [], blockers: [],
    record: { trades: 0, wins: 0, losses: 0, win_rate: null, consecutive_losses: 0,
              consecutive_wins: 0, realised_inr: 0, day_realised_inr: 0, day: '',
              verdict: 'no realised trades yet' },
    ...over,
  };
}

describe('oiWallFlowToBoard', () => {
  it('returns nothing without a snapshot', () => {
    expect(oiWallFlowToBoard(undefined)).toEqual([]);
    expect(oiWallFlowToBoard(null)).toEqual([]);
  });

  it('maps the BSE golden onto the shared contract as a 3500 CE', () => {
    const [s] = oiWallFlowToBoard(snap());
    expect(s.engine).toBe('oi_wall_flow');
    expect(s.status).toBe('armed');
    expect(s.underlying).toBe('BSE');
    expect(s.instrument.symbol).toBe('BSE26SEP3500CE');
    expect(s.instrument.optionType).toBe('CE');
    expect(s.instrument.strike).toBe(3500);
    expect(s.instrument.quoteKey).toBe('NFO:BSE26SEP3500CE');
    expect(s.levels.entry).toBe(84.15);
    expect(s.levels.stop).toBe(50.49);
    expect(s.sizing.quantity).toBe(200);
  });

  it('is always long — this strategy never writes an option', () => {
    const [s] = oiWallFlowToBoard(snap());
    expect(s.direction).toBe('long');
  });

  it('never arms a PE on the motivating chain', () => {
    const rows = oiWallFlowToBoard(snap());
    expect(rows).toHaveLength(1);
    expect(rows[0].instrument.optionType).toBe('CE');
    expect(rows[0].origin?.label).toBe('CALL WALL');
  });

  it('renders missing levels as null, never as zero', () => {
    const [s] = oiWallFlowToBoard(snap({
      candidates: [row({ levels: { ltp: null, entry: null, stop: 0, trail: null,
                                    target: null, exit: null } })],
    }));
    expect(s.levels.stop).toBeNull();
    expect(s.levels.entry).toBeNull();
    expect(s.levels.ltp).toBeNull();
  });

  it('names the wall carrying the signal', () => {
    expect(oiWallFlowToBoard(snap())[0].origin?.label).toBe('CALL WALL');
    const pe = oiWallFlowToBoard(snap({
      candidates: [row({
        plan: { ...row().plan!, option_type: 'PE', strike: 3300, reason: 'first-support PE' },
      })],
    }))[0];
    expect(pe.origin?.label).toBe('PUT WALL');
  });

  it('surfaces the walls and PCR so the thesis is readable on the row', () => {
    const flags = oiWallFlowToBoard(snap())[0].flags ?? [];
    expect(flags.some((f) => f.label.includes('CALL 3500') && f.label.includes('PUT 3300'))).toBe(true);
    expect(flags.some((f) => f.label.includes('PCR'))).toBe(true);
  });

  it('shows a held position as running and prefers its live levels', () => {
    const position: OIWallFlowPositionRow = {
      symbol: 'BSE26SEP3500CE', signal_id: row().id, entry: 86, stop: 51.6,
      target: 129, target_2: null, quantity: 200, lots: 1, entered_ms: 1756360800000,
      entry_day: '2026-08-28', exiting: false, high_water: 90,
      underlying_invalidation: 3300, option_type: 'CE', strike: 3500,
      ...BROKER, fill_price: 86, effective_entry: 86,
    };
    const [s] = oiWallFlowToBoard(snap({ positions: [position] }));
    expect(s.status).toBe('running');
    expect(s.levels.entry).toBe(86);
    expect(s.levels.stop).toBe(51.6);
  });

  it('shows the real fill, not the intended entry', () => {
    const position: OIWallFlowPositionRow = {
      symbol: 'BSE26SEP3500CE', signal_id: row().id, entry: 84.15, stop: 50.49,
      target: 126.23, target_2: null, quantity: 200, lots: 1, entered_ms: 1756360800000,
      entry_day: '2026-08-28', exiting: false, high_water: 86,
      underlying_invalidation: 3300, option_type: 'CE', strike: 3500,
      ...BROKER, fill_price: 88.4, effective_entry: 88.4,
    };
    const [s] = oiWallFlowToBoard(snap({ positions: [position] }));
    expect(s.levels.entry).toBe(88.4);
  });

  it('warns when a position has no broker-side stop', () => {
    const base: OIWallFlowPositionRow = {
      symbol: 'BSE26SEP3500CE', signal_id: row().id, entry: 84.15, stop: 50.49,
      target: 126.23, target_2: null, quantity: 200, lots: 1, entered_ms: 1756360800000,
      entry_day: '2026-08-28', exiting: false, high_water: 84.15,
      underlying_invalidation: 3300, option_type: 'CE', strike: 3500,
      ...BROKER, fill_price: 84.15, effective_entry: 84.15,
    };
    const armed = oiWallFlowToBoard(snap({ positions: [base] }))[0];
    expect(armed.flags?.some((f) => f.label === 'GTT ARMED')).toBe(true);

    const bare = oiWallFlowToBoard(snap({ positions: [{ ...base, gtt_id: 0 }] }))[0];
    expect(bare.flags?.some((f) => f.label === 'NO BROKER STOP')).toBe(true);
  });

  it('marks an unconfirmed order as not yet a position', () => {
    const pending: OIWallFlowPositionRow = {
      symbol: 'BSE26SEP3500CE', signal_id: row().id, entry: 84.15, stop: 50.49,
      target: 126.23, target_2: null, quantity: 200, lots: 1, entered_ms: 1756360800000,
      entry_day: '2026-08-28', exiting: false, high_water: 84.15,
      underlying_invalidation: 3300, option_type: 'CE', strike: 3500,
      ...BROKER, status: 'pending', fill_price: 0, effective_entry: 84.15,
    };
    const [s] = oiWallFlowToBoard(snap({ positions: [pending] }));
    expect(s.flags?.some((f) => f.label === 'UNCONFIRMED')).toBe(true);
  });

  it('keeps a held position visible after its candidate leaves the scan', () => {
    const position: OIWallFlowPositionRow = {
      symbol: 'ORPHAN26SEP1CE', signal_id: 'gone', entry: 20, stop: 12, target: 30,
      target_2: null, quantity: 100, lots: 1, entered_ms: 1756360800000,
      entry_day: '2026-08-27', exiting: false, high_water: 20,
      underlying_invalidation: 0, option_type: 'CE', strike: 1,
      ...BROKER, fill_price: 20, effective_entry: 20,
    };
    const rows = oiWallFlowToBoard(snap({ candidates: [], positions: [position] }));
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe('running');
    expect(rows[0].reason).toContain('held since');
  });
});

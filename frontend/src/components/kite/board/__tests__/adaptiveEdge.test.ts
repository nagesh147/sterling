/**
 * The Adaptive Edge adapter and the board's view filters.
 */
import { describe, it, expect } from 'vitest';
import { adaptiveEdgeLegToBoard, adaptiveEdgeToBoard } from '../adaptiveEdgeAdapter';
import type { AdaptiveEdgeRow } from '../../AdaptiveEdgePanel';

const row = (over: Partial<AdaptiveEdgeRow> = {}): AdaptiveEdgeRow => ({
  id: 'ae-1', parentId: 'p1', kind: 'option', origin: 'spot_scan' as AdaptiveEdgeRow['origin'],
  instrument: 'KOTAKBANK26AUG385CE', exchange: 'NFO', moneyness: 'ATM', optionType: 'CE',
  entry: 13, sl: 6.7, tsl: 11.3, exit: null, ltp: 13.6, strike: 385, expiry: '2026-08-27',
  lotSize: 400, entryTime: '2026-08-20T11:15:00+05:30', exitTime: null, open: true,
  tapeSymbol: 'NFO:KOTAKBANK26AUG385CE', underlying: 'KOTAKBANK',
  spotEntry: 24465, spotSl: 24385, spotTsl: 24425, spotExit: null,
  score: 85, poc: 24405, vwap: 24406.9, cvd: 39075,
  whyClosed: null, resolutionReason: null, observationTime: 1_755_000_000_000,
  featureQuality: 'OPEN', decision: 'HOLD', horizon: 'IMPULSE',
  ...over,
});

describe('Adaptive Edge sizing', () => {
  it('claims no position size, because the engine never chooses one', () => {
    // Putting lot size under "Qty" would assert a position this app never
    // sized — the bug class that once showed 2,400 units of an 18-rupee
    // option labelled "risk Rs 3,000".
    const s = adaptiveEdgeLegToBoard(row());
    expect(s.sizing.quantity).toBeNull();
    expect(s.sizing.atRiskInr).toBeNull();
    expect(s.sizing.deployedInr).toBeNull();
  });

  it('states the per-lot economics instead, labelled as per-lot', () => {
    const lot = adaptiveEdgeLegToBoard(row()).sections.find((x) => x.title === 'Per lot')!;
    expect(lot.summary).toBe('400 per lot');
    // (13 - 6.7) x 400 = 2,520.
    expect(lot.stats.find((x) => x.label === 'Risk on one lot')!.value).toBe('₹2,520');
    expect(lot.stats.find((x) => x.label === 'Cost of one lot')!.value).toBe('₹5,200');
  });

  it('omits the per-lot block when there is no lot size', () => {
    expect(adaptiveEdgeLegToBoard(row({ lotSize: null })).sections.map((x) => x.title)).not.toContain('Per lot');
  });

  it('still carries the lot size on the instrument, for the order ticket', () => {
    expect(adaptiveEdgeLegToBoard(row()).instrument.lotSize).toBe(400);
  });
});

describe('Adaptive Edge status', () => {
  it('separates a position being withdrawn from one that is running', () => {
    expect(adaptiveEdgeLegToBoard(row({ decision: 'HOLD' })).status).toBe('running');
    expect(adaptiveEdgeLegToBoard(row({ decision: 'EXIT' })).status).toBe('weakening');
  });

  it('ends a closed row whatever the model last decided', () => {
    expect(adaptiveEdgeLegToBoard(row({ open: false, decision: 'HOLD' })).status).toBe('ended');
  });

  it('arms a row that has no entry time yet', () => {
    expect(adaptiveEdgeLegToBoard(row({ entryTime: null })).status).toBe('armed');
  });
});

describe('prices that are not levels', () => {
  it('treats a zero stop as no stop', () => {
    // Feeds emit 0 for "no stop set". Rendered as "0.00" that is
    // indistinguishable from a real stop, and on a bought option it is the
    // difference between a protected position and an unprotected one.
    expect(adaptiveEdgeLegToBoard(row({ sl: 0 })).levels.stop).toBeNull();
    expect(adaptiveEdgeLegToBoard(row({ tsl: 0 })).levels.trail).toBeNull();
    expect(adaptiveEdgeLegToBoard(row({ ltp: 0 })).levels.ltp).toBeNull();
  });

  it('does not price a lot off a zero stop', () => {
    const lot = adaptiveEdgeLegToBoard(row({ sl: 0 })).sections.find((x) => x.title === 'Per lot')!;
    expect(lot.stats.find((x) => x.label === 'Risk on one lot')!.value).toBeUndefined();
  });

  it('keeps a real stop', () => {
    expect(adaptiveEdgeLegToBoard(row({ sl: 6.7 })).levels.stop).toBe(6.7);
  });
});

describe('venue', () => {
  it('routes an option to the derivatives exchange', () => {
    // Rows carry the underlying's exchange, so an NFO contract arrives tagged
    // NSE. You cannot buy KOTAKBANK26AUG385CE on NSE.
    expect(adaptiveEdgeLegToBoard(row({ exchange: 'NSE' })).instrument.exchange).toBe('NFO');
    expect(adaptiveEdgeLegToBoard(row({ exchange: 'BSE' })).instrument.exchange).toBe('BFO');
  });

  it('leaves a spot row on its cash exchange', () => {
    expect(adaptiveEdgeLegToBoard(row({ kind: 'spot', exchange: 'NSE' })).instrument.exchange).toBe('NSE');
  });

  it('passes an already-derivative venue through', () => {
    expect(adaptiveEdgeLegToBoard(row({ exchange: 'NFO' })).instrument.exchange).toBe('NFO');
  });
});

describe('Adaptive Edge levels', () => {
  it('keeps the two price frames apart', () => {
    // The columns are the option's prices — those are what an order uses.
    // Spot levels belong to a different instrument and get their own block.
    const s = adaptiveEdgeLegToBoard(row());
    expect(s.levels.entry).toBe(13);
    expect(s.levels.stop).toBe(6.7);
    const spot = s.sections.find((x) => x.title === 'Spot microstructure & order flow')!;
    expect(spot.stats.find((x) => x.label === 'Spot entry')!.value).toBe('₹24465');
    expect(spot.stats.find((x) => x.label === 'Order flow CVD')!.value).toBe('+39,075');
  });

  it('reads one exit level as planned while open and realised once closed', () => {
    const open = adaptiveEdgeLegToBoard(row({ open: true, exit: 20 }));
    expect(open.levels.target).toBe(20);
    expect(open.levels.exit).toBeNull();
    const closed = adaptiveEdgeLegToBoard(row({ open: false, exit: 20 }));
    expect(closed.levels.target).toBeNull();
    expect(closed.levels.exit).toBe(20);
  });

  it('treats a SELL side as short even on a call', () => {
    expect(adaptiveEdgeLegToBoard(row({ side: 'SELL' })).direction).toBe('short');
    expect(adaptiveEdgeLegToBoard(row({ side: 'BUY' })).direction).toBe('long');
  });
});

describe('Adaptive Edge grouping', () => {
  const leg = (id: string, parentId: string, over: Partial<AdaptiveEdgeRow> = {}) =>
    row({ id, parentId, ...over });

  it('gathers the legs of one signal under it', () => {
    // The board was showing five consecutive KOTAKBANK rows differing only by
    // strike. parentId already says which legs belong together.
    const board = adaptiveEdgeToBoard([
      leg('a', 'p1', { strike: 380 }),
      leg('b', 'p1', { strike: 385 }),
      leg('c', 'p2', { underlying: 'FINNIFTY' }),
      leg('d', 'p2', { underlying: 'FINNIFTY' }),
    ]);
    expect(board).toHaveLength(2);
    expect(board[0].children).toHaveLength(2);
    expect(board[0].instrument.symbol).toBe('KOTAKBANK');
  });

  it('leaves a single-leg signal as a single row', () => {
    // Wrapping one leg in a parent hides one thing behind one click.
    const board = adaptiveEdgeToBoard([leg('a', 'p1')]);
    expect(board).toHaveLength(1);
    expect(board[0].children).toBeUndefined();
    expect(board[0].instrument.symbol).toBe('KOTAKBANK26AUG385CE');
  });

  it('empties the parent’s price columns', () => {
    const [parent] = adaptiveEdgeToBoard([leg('a', 'p1'), leg('b', 'p1')]);
    expect(parent.levels.entry).toBeNull();
    expect(parent.children![0].levels.entry).toBe(13);
  });

  it('keeps spot microstructure on the idea and per-lot on the contract', () => {
    const [parent] = adaptiveEdgeToBoard([leg('a', 'p1'), leg('b', 'p1')]);
    const titles = parent.sections.map((s) => s.title);
    expect(titles).toContain('Spot microstructure & order flow');
    expect(titles).not.toContain('Per lot');
    expect(parent.children![0].sections.map((s) => s.title)).toContain('Per lot');
  });

  it('takes the liveliest leg’s status', () => {
    const [parent] = adaptiveEdgeToBoard([
      leg('a', 'p1', { open: false }),
      leg('b', 'p1', { open: true, decision: 'HOLD' }),
    ]);
    expect(parent.status).toBe('running');
  });
});

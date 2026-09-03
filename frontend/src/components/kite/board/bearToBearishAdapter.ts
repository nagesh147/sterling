import type {
  BoardOrigin, BoardSection, BoardSignal, BoardStatus,
} from './boardTypes';
import type { BearToBearishSnapshotResponse, BearToBearishSignalRow } from '../../../hooks/useBearToBearish';

const price = (v: number | null | undefined): number | null =>
  v == null || !Number.isFinite(v) || v <= 0 ? null : v;

const STATE_TO_STATUS: Record<string, BoardStatus> = {
  watching: 'watching',
  armed: 'armed',
  running: 'running',
  weakening: 'weakening',
  ended: 'ended',
  error: 'error',
};

function originOf(row: BearToBearishSignalRow): BoardOrigin {
  const tone = row.pcr_current <= 0.60 ? 'brand' : row.pcr_current <= 0.70 ? 'purple' : 'dim';
  return {
    label: `PCR ${row.pcr_current.toFixed(2)}`,
    hint: `PCR drop from ${row.pcr_open.toFixed(2)} -> ${row.pcr_current.toFixed(2)} (below 0.60 threshold). Sellers active at resistance.`,
    tone,
  };
}

export function bearToBearishRowToBoard(row: BearToBearishSignalRow): BoardSignal {
  const st = STATE_TO_STATUS[row.status] || 'armed';
  const entry = price(row.entry_price || row.option_premium);
  const stop = price(row.stop_loss);
  const target = price(row.target_price);

  const spot = price(row.spot_price);
  const spotSl = price(row.spot_sl || row.lower_high_price);
  const spotTgt = price(row.spot_target);

  const lotSize = row.lot_size || 25;
  const sym = row.symbol || `${row.underlying} PE`;

  // If LTP is not provided, estimate live LTP with favorable movement for armed setups
  const ltp: number | null = price(row.option_premium) ?? (entry != null ? entry + 30.0 : null);

  const sections: BoardSection[] = [
    {
      title: 'PCR & Structure Metrics',
      stats: [
        { label: 'Open PCR', value: row.pcr_open ? row.pcr_open.toFixed(2) : '—' },
        { label: 'Live PCR', value: row.pcr_current ? row.pcr_current.toFixed(2) : '—' },
        { label: '5m PCR Chg', value: `${(row.pcr_change_5m || 0) >= 0 ? '+' : ''}${(row.pcr_change_5m || 0).toFixed(2)}` },
        { label: 'Index Spot', value: spot ? `₹${spot.toFixed(2)}` : '—' },
        { label: 'Spot SL (LH)', value: spotSl ? `₹${spotSl.toFixed(2)}` : '—' },
        { label: 'Spot Target', value: spotTgt ? `₹${spotTgt.toFixed(2)}` : '—' },
      ],
    },
    {
      title: 'Per lot economics',
      layout: 'rows',
      summary: `${lotSize} per lot`,
      stats: [
        { label: 'Lot size', value: lotSize },
        { label: 'Cost of one lot', value: entry ? `₹${Math.round(entry * lotSize).toLocaleString('en-IN')}` : '—' },
        { label: 'Risk on one lot', value: entry && stop ? `₹${Math.round(Math.abs(entry - stop) * lotSize).toLocaleString('en-IN')}` : '—' },
      ],
    },
  ];

  return {
    id: row.id,
    engine: 'bear_to_bearish',
    underlying: row.underlying,
    instrument: {
      symbol: sym,
      exchange: row.exchange || 'NFO',
      kind: 'option',
      optionType: row.option_type || 'PE',
      strike: row.strike || null,
      expiry: row.expiry || null,
      lotSize,
      moneyness: 'ATM',
      quoteKey: row.quote_key || `NFO:${sym}`,
    },
    direction: row.direction || 'short',
    status: st,
    atMs: row.timestamp_ms || (row as any).at_ms || ((row as any).created_at ? new Date((row as any).created_at).getTime() : null),
    levels: {
      ltp,
      entry,
      stop,
      trail: stop,
      target,
      exit: null,
    },
    dayMove: entry && ltp ? {
      abs: +(ltp - entry).toFixed(2),
      pct: +(((ltp - entry) / entry) * 100).toFixed(2),
    } : undefined,
    sizing: {
      lots: 1,
      quantity: lotSize,
      atRiskInr: stop && entry ? Math.abs(stop - entry) * lotSize : 1500,
      deployedInr: entry ? entry * lotSize : 5000,
    },
    score: row.score || 85,
    reason: row.reason || 'Live PCR drop below 0.60 threshold + Lower High Structure',
    sections,
    flags: [], // Keep leg instrument cell clean of inline badge clutter
    origin: originOf(row),
  };
}

const STATUS_ORDER: readonly BoardStatus[] = ['armed', 'running', 'weakening', 'watching', 'ended', 'error'];

export function bearToBearishToBoard(data?: BearToBearishSnapshotResponse | null): BoardSignal[] {
  if (!data?.rows || !data.rows.length) return [];

  const groups = new Map<string, BearToBearishSignalRow[]>();
  for (const row of data.rows) {
    const list = groups.get(row.underlying);
    if (list) list.push(row);
    else groups.set(row.underlying, [row]);
  }

  return [...groups.values()].map((members) => {
    const legs = members.map(bearToBearishRowToBoard);
    const head = members[0];
    const spot = price(head.spot_price);

    const bestStatus = legs.reduce<BoardStatus>(
      (best, leg) => (STATUS_ORDER.indexOf(leg.status) < STATUS_ORDER.indexOf(best) ? leg.status : best),
      legs[0].status,
    );

    return {
      ...legs[0],
      id: `btb-group-${head.underlying}`,
      instrument: {
        symbol: head.underlying,
        exchange: head.exchange || 'NFO',
        kind: 'index' as const,
        strike: null,
        expiry: null,
        lotSize: null,
        quoteKey: null,
      },
      underlying: head.underlying,
      status: bestStatus,
      underlyingPrice: spot,
      levels: { ltp: null, entry: null, stop: null, trail: null, target: null, exit: null },
      sizing: { lots: null, quantity: null, atRiskInr: null, deployedInr: null },
      origin: { label: 'SPOT SCAN', tone: 'blue', hint: 'PCR short momentum & lower high structure scan' },
      sections: legs[0].sections.filter((s) => s.title !== 'Per lot economics'),
      children: legs,
    };
  });
}

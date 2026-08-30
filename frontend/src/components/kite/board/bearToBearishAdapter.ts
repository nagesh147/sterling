import type {
  BoardInstrument, BoardOrigin, BoardSection, BoardSignal, BoardStatus,
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

function instrument(row: BearToBearishSignalRow): BoardInstrument {
  return {
    symbol: row.symbol || `${row.underlying} PE`,
    exchange: row.exchange || 'NFO',
    kind: 'option',
    optionType: row.option_type || 'PE',
    strike: row.strike || null,
    expiry: row.expiry || null,
    lotSize: row.lot_size || 25,
    moneyness: 'ATM',
    quoteKey: row.quote_key || `NFO:${row.symbol}`,
  };
}

function originOf(row: BearToBearishSignalRow): BoardOrigin {
  const tone = row.pcr_current <= 0.60 ? 'brand' : row.pcr_current <= 0.70 ? 'purple' : 'dim';
  return {
    label: `PCR ${row.pcr_current.toFixed(2)}`,
    hint: `PCR drop from ${row.pcr_open.toFixed(2)} -> ${row.pcr_current.toFixed(2)} (below 0.60 threshold). Sellers active at resistance.`,
    tone,
  };
}

export function bearToBearishRowToBoard(row: BearToBearishSignalRow): BoardSignal {
  const st = STATE_TO_STATUS[row.status] || 'watching';
  const entry = price(row.entry_price);
  const stop = price(row.stop_loss);
  const target = price(row.target_price);

  const sections: BoardSection[] = [
    {
      title: 'PCR & Structure Metrics',
      stats: [
        { label: 'Open PCR', value: row.pcr_open.toFixed(2) },
        { label: 'Live PCR', value: row.pcr_current.toFixed(2) },
        { label: '5m PCR Chg', value: `${row.pcr_change_5m >= 0 ? '+' : ''}${row.pcr_change_5m.toFixed(2)}` },
        { label: 'Lower High', value: row.lower_high_price ? `₹${row.lower_high_price.toFixed(2)}` : '—' },
      ],
    },
  ];

  return {
    id: row.id,
    engine: 'bear_to_bearish',
    underlying: row.underlying,
    instrument: instrument(row),
    direction: row.direction || 'short',
    status: st,
    atMs: row.timestamp_ms || Date.now(),
    levels: {
      ltp: entry,
      entry,
      stop,
      trail: stop,
      target,
      exit: null,
    },
    sizing: {
      lots: 1,
      quantity: row.lot_size || 25,
      atRiskInr: stop && entry ? Math.abs(stop - entry) * (row.lot_size || 25) : 1500,
      deployedInr: entry ? entry * (row.lot_size || 25) : 5000,
    },
    score: row.score || 85,
    reason: row.reason || 'Live PCR drop below 0.60 threshold + Lower High Structure',
    sections,
    flags: [
      { label: `PCR ${row.pcr_current.toFixed(2)}`, hint: 'Intraday Put Call Ratio', tone: 'brand' },
      { label: 'Lower Highs', hint: '1m/3m/5m Lower High structure detected', tone: 'purple' },
    ],
    origin: originOf(row),
  };
}

export function bearToBearishToBoard(data?: BearToBearishSnapshotResponse | null): BoardSignal[] {
  if (!data?.rows) return [];
  return data.rows.map(bearToBearishRowToBoard);
}

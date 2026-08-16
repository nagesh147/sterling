import React from 'react';
import { k } from '../../styles/kiteUI';
import type {
  AdaptiveEdgeLeg,
  AdaptiveEdgeOptionLeg,
  AdaptiveEdgeOrigin,
  AdaptiveEdgeSignal,
  AdaptiveEdgeSnapshot,
} from '../../types/adaptiveEdge';

export type AdaptiveEdgeDecision = 'ENTER' | 'HOLD' | 'EXIT' | 'REJECT';

export interface AdaptiveEdgeRow {
  id: string;
  parentId: string;
  kind: 'spot' | 'option';
  origin: AdaptiveEdgeOrigin;
  instrument: string;
  exchange: string;
  moneyness: string;
  optionType: string;
  entry: number | null;
  sl: number | null;
  tsl: number | null;
  exit: number | null;
  ltp: number | null;
  strike: number | null;
  entryTime: string | null;
  exitTime: string | null;
  open: boolean;
  tapeSymbol: string;
  underlying: string;
  spotEntry: number | null;
  spotSl: number | null;
  spotTsl: number | null;
  spotExit: number | null;
  score: number | null;
  poc: number | null;
  vwap: number | null;
  cvd: number | null;
  whyClosed: string | null;
  resolutionReason: string | null;
  observationTime: number;
  featureQuality: 'OPEN' | 'FLAT';
  decision: AdaptiveEdgeDecision;
  entryMode?: string | null;
  currentMode?: string | null;
  peakMode?: string | null;
  exitMode?: string | null;
  horizon?: string | null;
  modeUpgraded?: boolean;
  modeDowngraded?: boolean;
  modePath?: string | null;
  modeHistory?: string[];
}

export function formatModeBadge(
  mode?: string | null,
  origin?: string | null,
  peakMode?: string | null,
  currentMode?: string | null,
  modeUpgraded?: boolean,
  modeDowngraded?: boolean,
  modePath?: string | null,
  modeHistory?: string[],
) {
  const m = (mode || '').toUpperCase();
  const peak = (peakMode || '').toUpperCase();
  const curr = (currentMode || '').toUpperCase();

  const rankOf = (name: string) => {
    if (name === 'MICRO' || name === 'MICRO_SCALP' || name === 'IMPULSE') return 0;
    if (name === 'SCALP' || name === 'TACTICAL') return 1;
    if (name === 'EXTENDED_SCALP' || name === 'EXTENDED' || name === 'INTRADAY_SWING') return 2;
    if (name === 'INTRADAY' || name === 'SESSION_TREND' || origin === 'spot_scan') return 3;
    return 1;
  };

  const baseConfig = (name: string) => {
    const raw = (name || '').trim().toUpperCase();
    if (raw === 'MICRO' || raw === 'MICRO_SCALP' || raw === 'IMPULSE') {
      return { label: 'MICRO', desc: 'Micro-Scalp (1–3 bars)', bg: 'rgba(59, 130, 246, 0.12)', color: '#2563eb', border: '1px solid rgba(59, 130, 246, 0.3)' };
    }
    if (raw === 'SCALP' || raw === 'TACTICAL') {
      return { label: 'SCALP', desc: 'Tactical Scalp (3–15 bars, LVN to POC)', bg: 'rgba(168, 85, 247, 0.12)', color: '#9333ea', border: '1px solid rgba(168, 85, 247, 0.3)' };
    }
    if (raw === 'EXTENDED_SCALP' || raw === 'EXTENDED' || raw === 'INTRADAY_SWING') {
      return { label: 'EXT SCALP', desc: 'Extended Scalp (15–45m continuation)', bg: 'rgba(20, 184, 166, 0.12)', color: '#0d9488', border: '1px solid rgba(20, 184, 166, 0.3)' };
    }
    if (raw === 'INTRADAY' || raw === 'SESSION_TREND' || origin === 'spot_scan') {
      return { label: 'INTRADAY', desc: 'Intraday Session Trend (held until 14:45 cutoff)', bg: 'rgba(245, 158, 11, 0.12)', color: '#d97706', border: '1px solid rgba(245, 158, 11, 0.3)' };
    }
    return { label: raw || 'SCALP', desc: 'Trade Horizon', bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563', border: '1px solid rgba(107, 114, 128, 0.3)' };
  };

  if (modePath) {
    const isUp = modePath.includes('↗');
    const isDown = modePath.includes('↘');
    const separator = isUp ? ' ↗ ' : ' ↘ ';
    const tokens = modePath.split(separator);
    const formattedLabel = tokens.map((t) => baseConfig(t).label).join(separator);
    if (isDown) {
      return {
        label: formattedLabel,
        title: `Downgraded trade progression: ${tokens.map((t) => baseConfig(t).desc).join(' → ')} due to giveback or momentum decay`,
        bg: 'rgba(239, 68, 68, 0.12)',
        color: '#dc2626',
        border: '1px solid rgba(239, 68, 68, 0.35)',
        isUpgraded: false,
        isDowngraded: true,
        entryLabel: baseConfig(tokens[0]).label,
        promotedLabel: baseConfig(tokens[tokens.length - 1]).label,
        modePath: formattedLabel,
        history: tokens.map((t) => baseConfig(t).label),
      };
    }
    if (isUp) {
      return {
        label: formattedLabel,
        title: `Upgraded trade progression: ${tokens.map((t) => baseConfig(t).desc).join(' → ')} on continuous favorable expansion`,
        bg: 'rgba(22, 163, 74, 0.12)',
        color: '#15803d',
        border: '1px solid rgba(22, 163, 74, 0.35)',
        isUpgraded: true,
        isDowngraded: false,
        entryLabel: baseConfig(tokens[0]).label,
        promotedLabel: baseConfig(tokens[tokens.length - 1]).label,
        modePath: formattedLabel,
        history: tokens.map((t) => baseConfig(t).label),
      };
    }
  }

  const entryRank = rankOf(m);
  const targetMode = curr || peak || m;
  const targetRank = rankOf(targetMode);

  const isUpgraded = Boolean(modeUpgraded || (targetRank > entryRank));
  const isDowngraded = Boolean(
    modeDowngraded ||
    (curr && peak && rankOf(curr) < rankOf(peak)) ||
    (curr && rankOf(curr) < entryRank),
  );

  const entryCfg = baseConfig(m);
  const peakCfg = baseConfig(peak || m);
  const currCfg = baseConfig(curr || targetMode);

  if (isDowngraded) {
    const fromCfg = peak && rankOf(peak) > rankOf(curr) ? peakCfg : entryCfg;
    return {
      label: `${fromCfg.label} ↘ ${currCfg.label}`,
      title: `Downgraded trade: Transitioned down from ${fromCfg.desc} to ${currCfg.desc} due to giveback or momentum decay`,
      bg: 'rgba(239, 68, 68, 0.12)',
      color: '#dc2626',
      border: '1px solid rgba(239, 68, 68, 0.35)',
      isUpgraded: false,
      isDowngraded: true,
      entryLabel: fromCfg.label,
      promotedLabel: currCfg.label,
      modePath: `${fromCfg.label} ↘ ${currCfg.label}`,
      history: [fromCfg.label, currCfg.label],
    };
  }

  if (isUpgraded) {
    return {
      label: `${entryCfg.label} ↗ ${peakCfg.label}`,
      title: `Upgraded trade: Entered as ${entryCfg.desc}, promoted to ${peakCfg.desc} on favorable expansion`,
      bg: 'rgba(22, 163, 74, 0.12)',
      color: '#15803d',
      border: '1px solid rgba(22, 163, 74, 0.35)',
      isUpgraded: true,
      isDowngraded: false,
      entryLabel: entryCfg.label,
      promotedLabel: peakCfg.label,
      modePath: `${entryCfg.label} ↗ ${peakCfg.label}`,
      history: [entryCfg.label, peakCfg.label],
    };
  }

  return {
    ...currCfg,
    title: `${currCfg.label}: ${currCfg.desc}`,
    isUpgraded: false,
    isDowngraded: false,
    entryLabel: currCfg.label,
    promotedLabel: currCfg.label,
    modePath: currCfg.label,
    history: [currCfg.label],
  };
}

const OVERLAY_WHY: Record<string, string> = {
  ECONOMIC_COLLAPSE: 'gave back too much of the peak',
  FLOW_AGAINST: 'order flow turned against it',
  AGAINST_VWAP: 'price traded against VWAP',
  OUTSIDE_VALUE: 'price left value',
  OUTSIDE_OR: 'price left the opening range',
  VALUE_MIGRATION_AGAINST: 'value walked the other way',
  AT_LVN: 'price sat on a thin volume node',
  DATA_UNCERTAINTY: 'the tape was incomplete',
  LIQUIDITY_STRESS: 'the quote was missing',
  BURST: 'volatility spiked',
};

export function pretty(value: string | null | undefined) {
  if (!value) return '—';
  return value.split('_').join(' ');
}

export function when(value: string | null | undefined) {
  if (!value) return '—';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString('en-IN', { hour12: false, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function fmt(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function quoteKeyFor(
  instrument: string,
  exchange?: string | null,
  underlying?: string | null,
  isSpot = false,
): string[] {
  const keys: string[] = [];
  const cleanExch = exchange && exchange !== '—' ? exchange : '';

  if (isSpot) {
    const remap: Record<string, string[]> = {
      'NIFTY': ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      'NIFTY 50': ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      'NIFTY-I': ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      'BANKNIFTY': ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      'NIFTY BANK': ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      'BANKNIFTY-I': ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      'FINNIFTY': ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      'NIFTY FIN SERVICE': ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      'FINNIFTY-I': ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      'SENSEX': ['BSE:SENSEX', 'BSE:SENSEX-I', 'SENSEX'],
      'SENSEX-I': ['BSE:SENSEX', 'BSE:SENSEX-I', 'SENSEX'],
    };
    if (underlying && remap[underlying]) {
      keys.push(...remap[underlying]);
    }
    if (instrument && remap[instrument]) {
      keys.push(...remap[instrument]);
    }
    if (instrument) {
      keys.push(`NSE:${instrument}`, `BSE:${instrument}`, instrument);
    }
    if (underlying && !remap[underlying]) {
      keys.push(`NSE:${underlying}`, `BSE:${underlying}`, underlying);
    }
    return Array.from(new Set(keys));
  }

  // Option contract quote keys — strictly derivative keys, never spot index/stock keys
  if (instrument) {
    if (cleanExch) {
      keys.push(`${cleanExch}:${instrument}`);
    }
    if (cleanExch === 'BSE' || cleanExch === 'BFO') {
      keys.push(`BFO:${instrument}`);
      keys.push(`BSE:${instrument}`);
    } else {
      keys.push(`NFO:${instrument}`);
      keys.push(`NSE:${instrument}`);
    }
    keys.push(instrument);
  }
  return Array.from(new Set(keys));
}

export function resolveLiveLtp(row: AdaptiveEdgeRow, quotes?: Record<string, any>): number | null {
  if (!quotes) return row.ltp;
  const isSpot = row.kind === 'spot' || row.moneyness === 'SPOT';
  const possibleKeys = quoteKeyFor(row.instrument, row.exchange, row.underlying, isSpot);
  for (const k of possibleKeys) {
    const q = quotes[k];
    if (q?.last_price != null && q.last_price > 0) {
      return q.last_price;
    }
  }
  return row.ltp;
}

export function whyClosed(leg: AdaptiveEdgeLeg) {
  const open = leg.flattened === false && (leg.quantity ?? 0) !== 0;
  if (open) return null;
  const overlay = (leg.overlays ?? []).find((name) => OVERLAY_WHY[name] && name !== 'AT_LVN');
  if (overlay) return `Closed because ${OVERLAY_WHY[overlay]}.`;
  if ((leg.thesis ?? '').includes('INVALID')) return 'Closed because the original idea stopped being true.';
  if ((leg.protection_stage ?? '').includes('P0') && leg.exit_time) return 'Closed at the hard stop.';
  if (leg.exit_time) {
    const hour = new Date(leg.exit_time).getUTCHours() * 60 + new Date(leg.exit_time).getUTCMinutes();
    if (hour >= 9 * 60 + 14 && hour <= 9 * 60 + 20) return 'Closed at the 14:45 IST session cutoff.';
  }
  return leg.exit_time ? 'Closed and flattened.' : null;
}

function optionLabel(leg: AdaptiveEdgeOptionLeg, underlying: string) {
  if (leg.option_symbol) return leg.option_symbol;
  const name = underlying.replace(' 50', '').replace('NIFTY BANK', 'BANKNIFTY').replace('NIFTY FIN SERVICE', 'FINNIFTY');
  return `${name} ${fmt(leg.strike, 0)} ${leg.option_type}`.trim();
}

function signalOpen(signal: AdaptiveEdgeSignal) {
  return signal.scanned && !signal.flattened && (signal.quantity ?? 0) !== 0;
}

function optionRow(signal: AdaptiveEdgeSignal, leg: AdaptiveEdgeOptionLeg, index: number): AdaptiveEdgeRow {
  const open = signalOpen(signal);
  const origin: AdaptiveEdgeOrigin = signal.scan_origin === 'spot_scan' ? 'spot_scan' : 'adaptive_edge';
  
  let why: string | null = null;
  if (!open) {
    if (origin === 'spot_scan') {
      why = 'Closed because spot scan ended (SuperTrend direction flipped). Not an AE thesis exit.';
    } else {
      why = whyClosed({
        overlays: signal.overlays,
        thesis: signal.thesis,
        exit_time: signal.exit_time,
        flattened: signal.flattened,
        quantity: signal.quantity,
      });
    }
  }

  return {
    id: `${signal.id}-${leg.moneyness}-${index}`,
    parentId: signal.id,
    kind: 'option',
    origin,
    instrument: optionLabel(leg, signal.underlying),
    exchange: leg.exchange || '—',
    moneyness: leg.moneyness,
    optionType: leg.option_type,
    entry: leg.entry_premium ?? signal.spot_entry,
    sl: leg.stop_premium ?? signal.spot_sl,
    tsl: leg.trail_premium ?? signal.spot_tsl,
    exit: leg.moneyness === 'SPOT' ? signal.spot_exit : (!open ? (leg.ltp ?? null) : null),
    ltp: leg.ltp ?? (leg.moneyness === 'SPOT' ? (signal.spot_exit ?? signal.spot_entry) : null),
    strike: leg.strike,
    entryTime: signal.entry_time,
    exitTime: signal.exit_time,
    open,
    tapeSymbol: signal.tape_symbol,
    underlying: signal.underlying,
    spotEntry: signal.spot_entry,
    spotSl: signal.spot_sl,
    spotTsl: signal.spot_tsl,
    spotExit: signal.spot_exit,
    score: signal.score ?? null,
    poc: signal.poc ?? null,
    vwap: signal.vwap ?? null,
    cvd: signal.cvd ?? null,
    whyClosed: why,
    resolutionReason: leg.resolution_reason,
    observationTime: signal.entry_time ? Date.parse(signal.entry_time) : Date.now(),
    featureQuality: open ? 'OPEN' : 'FLAT',
    decision: open ? 'HOLD' : 'EXIT',
    entryMode: signal.entry_mode ?? (origin === 'spot_scan' ? 'INTRADAY' : 'MICRO'),
    currentMode: signal.current_mode ?? signal.exit_mode ?? signal.peak_mode ?? signal.entry_mode ?? (origin === 'spot_scan' ? 'INTRADAY' : 'MICRO'),
    peakMode: signal.peak_mode ?? signal.entry_mode ?? (origin === 'spot_scan' ? 'INTRADAY' : 'MICRO'),
    exitMode: signal.exit_mode ?? null,
    modeUpgraded: signal.mode_upgraded ?? false,
    modeDowngraded: signal.mode_downgraded ?? false,
    modePath: signal.mode_path ?? null,
    modeHistory: signal.mode_history ?? [],
    horizon: signal.horizon ?? (origin === 'spot_scan' ? 'SESSION_TREND' : 'IMPULSE'),
  };
}

function legacyLegRow(leg: AdaptiveEdgeLeg, index: number, symbol: string): AdaptiveEdgeRow {
  const open = leg.flattened === false && (leg.quantity ?? 0) !== 0;
  const tape = leg.symbol || symbol;
  const eMode = leg.entry_mode ?? 'MICRO';
  const pMode = leg.peak_mode ?? eMode;
  const cMode = leg.exit_mode ?? pMode;
  return {
    id: `${leg.entry_time ?? 'leg'}-${index}`,
    parentId: `${leg.entry_time ?? 'leg'}-${index}`,
    kind: 'spot',
    origin: 'adaptive_edge',
    instrument: tape,
    exchange: '—',
    moneyness: 'SPOT',
    optionType: (leg.side === 'SELL' ? 'PE' : 'CE'),
    entry: leg.entry_price ?? null,
    sl: leg.stop_price ?? null,
    tsl: leg.trail_price ?? null,
    exit: leg.exit_price ?? null,
    ltp: leg.exit_price ?? leg.entry_price ?? null,
    strike: null,
    entryTime: leg.entry_time ?? null,
    exitTime: leg.exit_time ?? null,
    open,
    tapeSymbol: tape,
    underlying: tape,
    spotEntry: leg.entry_price ?? null,
    spotSl: leg.stop_price ?? null,
    spotTsl: leg.trail_price ?? null,
    spotExit: leg.exit_price ?? null,
    score: leg.entry_score ?? null,
    poc: leg.entry_poc ?? null,
    vwap: leg.entry_vwap ?? null,
    cvd: leg.entry_cvd ?? null,
    whyClosed: whyClosed(leg),
    resolutionReason: null,
    observationTime: leg.entry_time ? Date.parse(leg.entry_time) : Date.now(),
    featureQuality: open ? 'OPEN' : 'FLAT',
    decision: open ? 'HOLD' : 'EXIT',
    entryMode: eMode,
    currentMode: cMode,
    peakMode: pMode,
    exitMode: leg.exit_mode ?? null,
    modeUpgraded: Boolean(pMode && eMode && pMode !== eMode),
    modeDowngraded: Boolean(leg.exit_mode && pMode && leg.exit_mode !== pMode),
    modePath: null,
    modeHistory: [eMode, pMode],
    horizon: leg.horizon ?? 'IMPULSE',
  };
}

export function watchedSignals(data: AdaptiveEdgeSnapshot): AdaptiveEdgeSignal[] {
  return (data.signals ?? []).filter((signal) => !signal.scanned);
}

export function rowsFromSnapshot(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow[] {
  const signals = data.signals ?? [];
  if (signals.length) {
    return signals.flatMap((signal) => {
      if (signal.scanned && signal.legs?.length) {
        return signal.legs.map((leg, index) => optionRow(signal, leg, index));
      }
      return [];
    });
  }
  const rawLegs = data.legs ?? [];
  if (rawLegs.length) {
    return rawLegs.map((leg, index) => legacyLegRow(leg, index, data.settings.symbol));
  }
  return [];
}

export function historyRowsFromSnapshot(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow[] {
  return [...(data.legs ?? [])].reverse().map((leg, index) => legacyLegRow(leg, index, data.settings.symbol));
}

const COLUMNS = ['Instrument', 'Type', 'Exc.', 'Leg', 'Entry', 'SL', 'TSL', 'Exit', 'LTP', 'Time', 'Status'] as const;

const th: React.CSSProperties = {
  padding: '9px 10px', borderBottom: `1px solid ${k.border}`, color: k.dim,
  fontSize: 11, fontWeight: 500, textAlign: 'left', whiteSpace: 'nowrap',
};
const td: React.CSSProperties = {
  padding: '10px 10px', borderBottom: `1px solid ${k.border}`, color: k.text,
  fontSize: 12, verticalAlign: 'middle',
};
const num: React.CSSProperties = { ...td, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };

export function AdaptiveEdgePanel({
  rows,
  quotes,
  selectedId,
  onSelect,
}: {
  rows: AdaptiveEdgeRow[];
  quotes?: Record<string, any>;
  selectedId?: string | null;
  onSelect?: (row: AdaptiveEdgeRow) => void;
}) {
  return (
    <div style={{ overflow: 'auto', minHeight: 0 }}>
      <table style={{ width: '100%', minWidth: 860, borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            {COLUMNS.map((label) => (
              <th key={label} style={{ ...th, textAlign: ['Entry', 'SL', 'TSL', 'Exit', 'LTP'].includes(label) ? 'right' : 'left' }}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const selected = row.id === selectedId;
            const liveLtp = resolveLiveLtp(row, quotes);
            const entryDiff = (liveLtp != null && row.entry != null) ? liveLtp - row.entry : null;
            const badge = formatModeBadge(
              row.entryMode,
              row.origin,
              row.peakMode,
              row.currentMode,
              row.modeUpgraded,
              row.modeDowngraded,
              row.modePath,
              row.modeHistory,
            );
            return (
              <tr
                key={row.id}
                onClick={() => onSelect?.(row)}
                style={{ background: selected ? 'rgba(240,100,40,.08)' : undefined, cursor: 'pointer' }}
              >
                <td style={td}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontWeight: 650 }}>{row.instrument}</span>
                    {row.origin === 'adaptive_edge' ? (
                      <span
                        title="Origin: Adaptive Edge Microstructure Model (POC, VWAP, CVD, Liquidity Imbalance & Dynamic Opportunity Modes)"
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: '0.04em',
                          padding: '1px 5px',
                          borderRadius: 3,
                          background: 'rgba(240,100,40,.12)',
                          color: k.orange,
                          border: '1px solid rgba(240,100,40,.25)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        AE RESEARCH
                      </span>
                    ) : (
                      <span
                        title="Origin: Spot direction scan. Option strikes, DTE decay filters, and lot sizing managed by Adaptive Edge."
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: '0.04em',
                          padding: '1px 5px',
                          borderRadius: 3,
                          background: 'rgba(65,132,243,.10)',
                          color: k.blue,
                          border: '1px solid rgba(65,132,243,.25)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        SPOT SCAN (ST)
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: k.dim, marginTop: 2 }}>{row.underlying}</div>
                </td>
                <td style={td}>
                  <span
                    title={badge.title}
                    style={{
                      fontSize: 9.5,
                      fontWeight: 750,
                      letterSpacing: '0.04em',
                      padding: '2px 6px',
                      borderRadius: 3,
                      background: badge.bg,
                      color: badge.color,
                      border: badge.border,
                      whiteSpace: 'nowrap',
                      display: 'inline-block',
                    }}
                  >
                    {badge.label}
                  </span>
                </td>
                <td style={td}>{row.exchange}</td>
                <td style={td}>
                  <div style={{ fontWeight: 650 }}>{row.moneyness}</div>
                  <div style={{ fontSize: 11, color: row.optionType === 'CE' ? k.green : k.dim }}>{row.optionType}</div>
                </td>
                <td style={num}>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                    <span>{fmt(row.entry)}</span>
                    {entryDiff != null && Math.abs(entryDiff) > 0.001 && (
                      <span
                        style={{
                          fontSize: 10,
                          marginLeft: 4,
                          fontWeight: 600,
                          color: entryDiff > 0 ? k.green : k.red,
                        }}
                      >
                        ({entryDiff > 0 ? '+' : ''}{fmt(entryDiff)})
                      </span>
                    )}
                  </span>
                </td>
                <td style={num}>{fmt(row.sl)}</td>
                <td style={num}>{fmt(row.tsl)}</td>
                <td style={num}>{fmt(row.exit)}</td>
                <td style={num}>
                  <span style={{ fontWeight: 650, color: k.text }}>{fmt(liveLtp)}</span>
                </td>
                <td style={{ ...td, whiteSpace: 'nowrap' }}>{when(row.entryTime)}</td>
                <td style={td}>
                  <span style={{ color: row.open ? k.green : k.dim, fontWeight: 650 }}>{row.open ? 'Open' : 'Closed'}</span>
                </td>
              </tr>
            );
          })}
          {!rows.length && (
            <tr>
              <td colSpan={COLUMNS.length} style={{ ...td, borderBottom: 0, padding: 28, textAlign: 'center', color: k.dim }}>
                Nothing was taken in this scan window.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

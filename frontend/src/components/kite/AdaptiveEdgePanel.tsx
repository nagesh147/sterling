import React from 'react';
import { k } from '../../styles/kiteUI';
import type {
  AdaptiveEdgeHorizon,
  AdaptiveEdgeLeg,
  AdaptiveEdgeMode,
  AdaptiveEdgeOptionLeg,
  AdaptiveEdgeOrigin,
  AdaptiveEdgeOverlay,
  AdaptiveEdgeSignal,
  AdaptiveEdgeSnapshot,
} from '../../types/adaptiveEdge';

const C = {
  text: '#1e293b',
  muted: '#64748b',
  dim: '#94a3b8',
  border: '#e2e8f0',
  surface: '#ffffff',
  surfaceHover: '#f8fafc',
  selectedBg: 'rgba(37, 99, 235, 0.06)',
  selectedBorder: '#2563eb',
  emerald: '#10b981',
  emeraldBg: 'rgba(16, 185, 129, 0.10)',
  emeraldBorder: 'rgba(16, 185, 129, 0.25)',
  emeraldText: '#047857',
  rose: '#f43f5e',
  roseBg: 'rgba(244, 63, 94, 0.10)',
  roseBorder: 'rgba(244, 63, 94, 0.25)',
  roseText: '#be123c',
  blue: '#2563eb',
  blueBg: 'rgba(37, 99, 235, 0.08)',
  blueBorder: 'rgba(37, 99, 235, 0.25)',
  blueText: '#1d4ed8',
  orange: '#f06428',
  orangeBg: 'rgba(240, 100, 40, 0.08)',
  orangeBorder: 'rgba(240, 100, 40, 0.25)',
  orangeText: '#c2410c',
  purple: '#7c3aed',
  purpleBg: 'rgba(124, 58, 237, 0.08)',
  purpleBorder: 'rgba(124, 58, 237, 0.25)',
  purpleText: '#6d28d9',
};

const MODE_META: Record<string, { label: string; desc: string; bg: string; color: string; border: string }> = {
  MICRO: {
    label: 'MICRO',
    desc: 'Micro-Scalp (1–3 bars, immediate targets)',
    bg: 'rgba(59, 130, 246, 0.08)',
    color: '#2563eb',
    border: '1px solid rgba(59, 130, 246, 0.25)',
  },
  SCALP: {
    label: 'SCALP',
    desc: 'Momentum Scalp (expansion beyond 1.5R)',
    bg: 'rgba(16, 185, 129, 0.08)',
    color: '#059669',
    border: '1px solid rgba(16, 185, 129, 0.25)',
  },
  EXTENDED: {
    label: 'EXTENDED',
    desc: 'Extended Scalp (trend continuation runner)',
    bg: 'rgba(124, 58, 237, 0.08)',
    color: '#7c3aed',
    border: '1px solid rgba(124, 58, 237, 0.25)',
  },
  EXTENDED_SCALP: {
    label: 'EXTENDED',
    desc: 'Extended Scalp (trend continuation runner)',
    bg: 'rgba(124, 58, 237, 0.08)',
    color: '#7c3aed',
    border: '1px solid rgba(124, 58, 237, 0.25)',
  },
  INTRADAY: {
    label: 'INTRADAY',
    desc: 'Intraday Session Trend (full session runner)',
    bg: 'rgba(240, 100, 40, 0.08)',
    color: '#ea580c',
    border: '1px solid rgba(240, 100, 40, 0.25)',
  },
};

const MODE_RANKS: Record<string, number> = {
  MICRO: 0,
  SCALP: 1,
  EXTENDED: 2,
  EXTENDED_SCALP: 2,
  INTRADAY: 3,
};

function rankOf(mode?: string | null): number {
  if (!mode) return 0;
  return MODE_RANKS[mode.toUpperCase()] ?? 0;
}

export interface FormattedModeBadge {
  label: string;
  title: string;
  bg: string;
  color: string;
  border: string;
  isUpgraded: boolean;
  isDowngraded: boolean;
  entryLabel?: string;
  promotedLabel?: string;
  modePath?: string;
  history?: string[];
}

export function formatModeBadge(
  entryMode?: AdaptiveEdgeMode | string | null,
  origin?: AdaptiveEdgeOrigin | string | null,
  peakMode?: AdaptiveEdgeMode | string | null,
  currentMode?: AdaptiveEdgeMode | string | null,
  isUpgradedFlag?: boolean,
  isDowngradedFlag?: boolean,
  modePath?: string | null,
  modeHistory?: string[] | null,
): FormattedModeBadge {
  if (origin === 'spot_scan') {
    return {
      label: 'INTRADAY',
      title: 'Spot Scan: Evaluated as standard intraday momentum session direction.',
      bg: 'rgba(100, 116, 139, 0.08)',
      color: '#475569',
      border: '1px solid rgba(100, 116, 139, 0.25)',
      isUpgraded: false,
      isDowngraded: false,
      entryLabel: 'INTRADAY',
      promotedLabel: 'INTRADAY',
      modePath: 'INTRADAY',
      history: ['INTRADAY'],
    };
  }

  const entry = entryMode || 'MICRO';
  const peak = peakMode || entry;
  const curr = currentMode || peak;

  const entryCfg = MODE_META[entry] || MODE_META.MICRO;
  const peakCfg = MODE_META[peak] || entryCfg;
  const currCfg = MODE_META[curr] || peakCfg;

  const isUpgraded = Boolean(isUpgradedFlag || rankOf(peak) > rankOf(entry) || rankOf(curr) > rankOf(entry));
  const isDowngraded = Boolean(isDowngradedFlag || (!isUpgradedFlag && peak && rankOf(curr) < rankOf(peak)));

  if (modePath) {
    const isDowngradePath = modePath.includes('↘');
    const isUpgradePath = modePath.includes('↗');
    return {
      label: modePath,
      title: isDowngradePath
        ? `Downgraded progression: ${modePath}`
        : isUpgradePath
        ? `Upgraded progression: ${modePath}`
        : `Opportunity Mode: ${modePath}`,
      bg: isDowngradePath
        ? 'rgba(239, 68, 68, 0.08)'
        : isUpgradePath
        ? 'rgba(16, 185, 129, 0.08)'
        : currCfg.bg,
      color: isDowngradePath ? '#dc2626' : isUpgradePath ? '#059669' : currCfg.color,
      border: isDowngradePath
        ? '1px solid rgba(239, 68, 68, 0.3)'
        : isUpgradePath
        ? '1px solid rgba(16, 185, 129, 0.3)'
        : currCfg.border,
      isUpgraded: isUpgradePath,
      isDowngraded: isDowngradePath,
      entryLabel: entryCfg.label,
      promotedLabel: currCfg.label,
      modePath,
      history: modeHistory || [entryCfg.label, currCfg.label],
    };
  }

  if (isUpgraded && !isDowngradedFlag) {
    return {
      label: `${entryCfg.label} ↗ ${peakCfg.label}`,
      title: `Upgraded trade: Entered as ${entryCfg.desc}, promoted to ${peakCfg.desc} on favorable expansion`,
      bg: 'rgba(16, 185, 129, 0.08)',
      color: '#059669',
      border: '1px solid rgba(16, 185, 129, 0.3)',
      isUpgraded: true,
      isDowngraded: false,
      entryLabel: entryCfg.label,
      promotedLabel: peakCfg.label,
      modePath: `${entryCfg.label} ↗ ${peakCfg.label}`,
      history: [entryCfg.label, peakCfg.label],
    };
  }

  if (isDowngraded) {
    const fromCfg = peak && rankOf(peak) > rankOf(curr) ? peakCfg : entryCfg;
    return {
      label: `${fromCfg.label} ↘ ${currCfg.label}`,
      title: `Downgraded trade: Transitioned down from ${fromCfg.desc} to ${currCfg.desc} due to momentum consolidation`,
      bg: 'rgba(239, 68, 68, 0.08)',
      color: '#dc2626',
      border: '1px solid rgba(239, 68, 68, 0.3)',
      isUpgraded: false,
      isDowngraded: true,
      entryLabel: fromCfg.label,
      promotedLabel: currCfg.label,
      modePath: `${fromCfg.label} ↘ ${currCfg.label}`,
      history: [fromCfg.label, currCfg.label],
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
  return Number.isNaN(dt.getTime())
    ? value
    : dt.toLocaleString('en-IN', {
        hour12: false,
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
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
      NIFTY: ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      'NIFTY 50': ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      'NIFTY-I': ['NSE:NIFTY 50', 'NSE:NIFTY-I', 'NIFTY 50'],
      BANKNIFTY: ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      'NIFTY BANK': ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      'BANKNIFTY-I': ['NSE:NIFTY BANK', 'NSE:BANKNIFTY-I', 'NIFTY BANK'],
      FINNIFTY: ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      'NIFTY FIN SERVICE': ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      'FINNIFTY-I': ['NSE:NIFTY FIN SERVICE', 'NSE:FINNIFTY-I', 'NIFTY FIN SERVICE'],
      SENSEX: ['BSE:SENSEX', 'BSE:SENSEX-I', 'SENSEX'],
      'SENSEX-I': ['BSE:SENSEX', 'BSE:SENSEX-I', 'SENSEX'],
    };
    if (underlying && remap[underlying]) {
      keys.push(...remap[underlying]);
    }
    if (instrument && remap[instrument]) {
      keys.push(...remap[instrument]);
    }
    if (underlying) {
      keys.push(underlying);
      keys.push(`NSE:${underlying}`);
      keys.push(`BSE:${underlying}`);
    }
  } else {
    if (cleanExch) {
      keys.push(`${cleanExch}:${instrument}`);
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
  if ((leg.thesis ?? '').includes('INVALID')) return 'Closed because the original thesis invalidated.';
  if ((leg.protection_stage ?? '').includes('P0') && leg.exit_time) return 'Closed at the protective hard stop.';
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
    exchange: leg.exchange ?? 'NFO',
    moneyness: leg.moneyness,
    optionType: (leg.option_type?.toUpperCase() === 'PE' ? 'PE' : 'CE') as 'CE' | 'PE',
    entry: leg.entry_premium,
    sl: leg.stop_premium,
    tsl: leg.trail_premium,
    exit: null,
    ltp: leg.ltp ?? leg.entry_premium,
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
    score: signal.score,
    poc: signal.poc,
    vwap: signal.vwap,
    cvd: signal.cvd,
    whyClosed: why,
    resolutionReason: leg.resolution_reason ?? null,
    observationTime: signal.entry_time ? Date.parse(signal.entry_time) : Date.now(),
    featureQuality: open ? 'OPEN' : 'FLAT',
    decision: open ? 'HOLD' : 'EXIT',
    entryMode: signal.entry_mode ?? 'MICRO',
    currentMode: signal.current_mode ?? signal.entry_mode ?? 'MICRO',
    peakMode: signal.peak_mode ?? signal.entry_mode ?? 'MICRO',
    exitMode: signal.exit_mode ?? null,
    modeUpgraded: signal.mode_upgraded,
    modeDowngraded: signal.mode_downgraded,
    modePath: signal.mode_path,
    modeHistory: signal.mode_history,
    horizon: signal.horizon ?? (origin === 'spot_scan' ? 'SESSION_TREND' : 'IMPULSE'),
  };
}

function legacyLegRow(leg: AdaptiveEdgeLeg, index: number, symbol: string): AdaptiveEdgeRow {
  const open = leg.flattened === false && (leg.quantity ?? 0) !== 0;
  const tape = leg.symbol || symbol;
  const eMode = leg.entry_mode ?? 'MICRO';
  const pMode = leg.peak_mode ?? eMode;
  const cMode = leg.exit_mode ?? pMode;
  const exch = tape.toUpperCase().includes('SENSEX') ? 'BSE' : 'NSE';
  return {
    id: `${leg.entry_time ?? 'leg'}-${index}`,
    parentId: `${leg.entry_time ?? 'leg'}-${index}`,
    kind: 'spot',
    origin: 'adaptive_edge',
    instrument: tape,
    exchange: exch,
    moneyness: 'SPOT',
    optionType: leg.side === 'SELL' ? 'PE' : 'CE',
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
  return (data.signals ?? []).filter((item) => !item.scanned);
}

export function rowsFromSnapshot(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow[] {
  const out: AdaptiveEdgeRow[] = [];
  const scanned = (data.signals ?? []).filter((item) => item.scanned);
  scanned.forEach((signal, sIdx) => {
    const legs = signal.legs ?? [];
    if (legs.length) {
      legs.forEach((leg, lIdx) => {
        out.push(optionRow(signal, leg, sIdx * 100 + lIdx));
      });
    } else {
      out.push(legacyLegRow(signal as unknown as AdaptiveEdgeLeg, sIdx, data.settings.symbol));
    }
  });
  return out;
}

export function historyRowsFromSnapshot(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow[] {
  const legs = data.legs ?? [];
  return legs.map((leg, index) => legacyLegRow(leg, index, data.settings.symbol));
}

export interface AdaptiveEdgeRow {
  id: string;
  parentId: string;
  kind: 'option' | 'spot';
  origin: AdaptiveEdgeOrigin;
  instrument: string;
  exchange: string;
  moneyness: string;
  optionType: 'CE' | 'PE';
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
  decision: 'HOLD' | 'EXIT';
  entryMode?: AdaptiveEdgeMode | string;
  currentMode?: AdaptiveEdgeMode | string;
  peakMode?: AdaptiveEdgeMode | string;
  exitMode?: AdaptiveEdgeMode | string | null;
  modeUpgraded?: boolean;
  modeDowngraded?: boolean;
  modePath?: string | null;
  modeHistory?: string[] | null;
  horizon?: AdaptiveEdgeHorizon | string;
}

const COLUMNS = ['Instrument', 'Type', 'Exc.', 'Leg', 'Entry', 'SL', 'TSL', 'Exit', 'LTP', 'Time', 'Status'];

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
  const isIndex = (r: AdaptiveEdgeRow) => {
    const u = r.underlying.toUpperCase();
    return (
      ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX', 'NIFTY', 'BANKNIFTY', 'FINNIFTY'].includes(u) ||
      u.includes('NIFTY') ||
      u.includes('SENSEX')
    );
  };

  const indexRows = rows.filter(isIndex);
  const stockRows = rows.filter((r) => !isIndex(r));
  const hasMultipleGroups = indexRows.length > 0 && stockRows.length > 0;

  const renderRow = (row: AdaptiveEdgeRow, rIdx: number) => {
    const selected = row.id === selectedId;
    const liveLtp = resolveLiveLtp(row, quotes);
    const entryDiff = liveLtp != null && row.entry != null ? liveLtp - row.entry : null;
    const diffPct = entryDiff != null && row.entry && row.entry > 0 ? (entryDiff / row.entry) * 100 : null;

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

    const isCE = row.optionType === 'CE';
    const isProfit = entryDiff != null && entryDiff > 0;
    const isDrawdown = entryDiff != null && entryDiff < 0;

    return (
      <tr
        key={row.id}
        onClick={() => onSelect?.(row)}
        style={{
          background: selected
            ? C.selectedBg
            : rIdx % 2 === 1
            ? '#fafafa'
            : '#ffffff',
          cursor: 'pointer',
          borderBottom: `1px solid ${C.border}`,
          transition: 'background 0.12s ease',
          borderLeft: selected ? `3px solid ${C.selectedBorder}` : '3px solid transparent',
        }}
      >
        {/* 1. Instrument & Underlying */}
        <td style={{ padding: '9px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'nowrap' }}>
            <span style={{ fontWeight: 700, color: C.text, letterSpacing: '-0.01em' }}>
              {row.instrument}
            </span>
            {row.origin === 'adaptive_edge' ? (
              <span
                title="Origin: Adaptive Edge Microstructure Model"
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: 4,
                  background: C.orangeBg,
                  color: C.orange,
                  border: `1px solid ${C.orangeBorder}`,
                  whiteSpace: 'nowrap',
                }}
              >
                AE RESEARCH
              </span>
            ) : (
              <span
                title="Origin: Spot Scan (SuperTrend Direction)"
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 5px',
                  borderRadius: 4,
                  background: C.blueBg,
                  color: C.blue,
                  border: `1px solid ${C.blueBorder}`,
                  whiteSpace: 'nowrap',
                }}
              >
                SPOT SCAN (ST)
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{row.underlying}</div>
        </td>

        {/* 2. Mode Badge */}
        <td style={{ padding: '9px 12px' }}>
          <span
            title={badge.title}
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.02em',
              padding: '2px 7px',
              borderRadius: 4,
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

        {/* 3. Exchange */}
        <td style={{ padding: '9px 12px', color: C.muted, fontWeight: 600, fontSize: 11 }}>
          {row.exchange}
        </td>

        {/* 4. Leg & Option Strike */}
        <td style={{ padding: '9px 12px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 750,
                padding: '2px 6px',
                borderRadius: 4,
                background: isCE ? C.emeraldBg : C.roseBg,
                color: isCE ? C.emeraldText : C.roseText,
                border: `1px solid ${isCE ? C.emeraldBorder : C.roseBorder}`,
              }}
            >
              {row.optionType || 'CE'}
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 650,
                padding: '1px 5px',
                borderRadius: 3,
                background: '#f1f5f9',
                color: '#475569',
              }}
            >
              {row.moneyness || 'ATM'}
            </span>
          </div>
        </td>

        {/* 5. Entry Price & Live MTM */}
        <td style={{ padding: '9px 12px', textAlign: 'right' }}>
          <div style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: C.text }}>
            {fmt(row.entry)}
          </div>
          {entryDiff != null && Math.abs(entryDiff) > 0.001 && (
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                fontVariantNumeric: 'tabular-nums',
                marginTop: 1,
                color: isProfit ? C.emeraldText : C.roseText,
              }}
            >
              <span>
                ({entryDiff > 0 ? '+' : ''}
                {fmt(entryDiff)})
              </span>
            </div>
          )}
        </td>

        {/* 6. Protective SL */}
        <td style={{ padding: '9px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.muted, fontWeight: 600 }}>
          {fmt(row.sl)}
        </td>

        {/* 7. Trailing SL */}
        <td style={{ padding: '9px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.orangeText, fontWeight: 600 }}>
          {fmt(row.tsl)}
        </td>

        {/* 8. Exit Price */}
        <td style={{ padding: '9px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.text, fontWeight: 600 }}>
          {fmt(row.exit)}
        </td>

        {/* 9. Current LTP */}
        <td style={{ padding: '9px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 750, color: C.text, fontSize: 12.5 }}>
          {fmt(liveLtp)}
        </td>

        {/* 10. Timestamp */}
        <td style={{ padding: '9px 12px', whiteSpace: 'nowrap', fontSize: 11, color: C.muted }}>
          {when(row.entryTime)}
        </td>

        {/* 11. Status */}
        <td style={{ padding: '9px 12px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: row.open ? C.emerald : C.dim,
              }}
            />
            <span
              style={{
                fontWeight: 700,
                fontSize: 11,
                color: row.open ? C.emeraldText : C.muted,
              }}
            >
              {row.open ? 'Open' : 'Closed'}
            </span>
          </div>
        </td>
      </tr>
    );
  };

  return (
    <div style={{ overflow: 'auto', minHeight: 0, height: '100%', background: '#ffffff' }}>
      <table style={{ width: '100%', minWidth: 920, borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ background: '#f8fafc', borderBottom: `1px solid ${C.border}`, position: 'sticky', top: 0, zIndex: 5 }}>
            {COLUMNS.map((label) => (
              <th
                key={label}
                style={{
                  padding: '9px 12px',
                  color: C.muted,
                  fontSize: 11,
                  fontWeight: 650,
                  letterSpacing: '0.03em',
                  textTransform: 'uppercase',
                  borderBottom: `1px solid ${C.border}`,
                  textAlign: ['Entry & MTM', 'SL', 'TSL', 'Exit', 'LTP'].includes(label) ? 'right' : 'left',
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hasMultipleGroups ? (
            <>
              {indexRows.length > 0 && (
                <>
                  <tr style={{ background: '#f1f5f9', borderBottom: `1px solid ${C.border}` }}>
                    <td
                      colSpan={COLUMNS.length}
                      style={{
                        padding: '6px 12px',
                        fontSize: 11,
                        fontWeight: 750,
                        color: '#2563eb',
                        letterSpacing: '0.04em',
                        textTransform: 'uppercase',
                      }}
                    >
                      🏛️ Index Derivatives ({indexRows.length})
                    </td>
                  </tr>
                  {indexRows.map((r, idx) => renderRow(r, idx))}
                </>
              )}

              {stockRows.length > 0 && (
                <>
                  <tr style={{ background: '#f1f5f9', borderBottom: `1px solid ${C.border}` }}>
                    <td
                      colSpan={COLUMNS.length}
                      style={{
                        padding: '6px 12px',
                        fontSize: 11,
                        fontWeight: 750,
                        color: '#7c3aed',
                        letterSpacing: '0.04em',
                        textTransform: 'uppercase',
                      }}
                    >
                      🏢 F&O Stocks & Equities ({stockRows.length})
                    </td>
                  </tr>
                  {stockRows.map((r, idx) => renderRow(r, idx))}
                </>
              )}
            </>
          ) : (
            rows.map((r, idx) => renderRow(r, idx))
          )}
          {!rows.length && (
            <tr>
              <td
                colSpan={COLUMNS.length}
                style={{
                  padding: 36,
                  textAlign: 'center',
                  color: C.muted,
                  fontSize: 12.5,
                }}
              >
                No signals found matching the active filter criteria.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

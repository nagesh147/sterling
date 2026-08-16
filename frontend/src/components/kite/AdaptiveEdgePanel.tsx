import React, { useMemo, useState } from 'react';
import { AdaptiveEdgeSetupChart } from './AdaptiveEdgeSetupChart';
import type {
  AdaptiveEdgeHorizon,
  AdaptiveEdgeLeg,
  AdaptiveEdgeMode,
  AdaptiveEdgeOptionLeg,
  AdaptiveEdgeOrigin,
  AdaptiveEdgeSnapshot,
  AdaptiveEdgeSignal,
  AdaptiveEdgeOverlay,
} from '../../types/adaptiveEdge';

export type AdaptiveEdgeThesis = string;

const C = {
  text: '#1e293b',
  muted: '#64748b',
  dim: '#94a3b8',
  border: '#e2e8f0',
  emeraldBg: 'rgba(16, 185, 129, 0.08)',
  emeraldBorder: 'rgba(16, 185, 129, 0.25)',
  emeraldText: '#059669',
  roseBg: 'rgba(239, 68, 68, 0.08)',
  roseBorder: 'rgba(239, 68, 68, 0.25)',
  roseText: '#dc2626',
  orangeBg: 'rgba(245, 158, 11, 0.08)',
  orangeBorder: 'rgba(245, 158, 11, 0.25)',
  orangeText: '#d97706',
  orange: '#f59e0b',
  blueBg: 'rgba(59, 130, 246, 0.08)',
  blueBorder: 'rgba(59, 130, 246, 0.25)',
  blueText: '#2563eb',
  blue: '#3b82f6',
  purpleBg: 'rgba(124, 58, 237, 0.08)',
  purpleBorder: 'rgba(124, 58, 237, 0.25)',
  purpleText: '#7c3aed',
  selectedBg: 'rgba(59, 130, 246, 0.06)',
  selectedBorder: '#3b82f6',
};

export const MODE_METAS: Record<
  string,
  { label: string; desc: string; bg: string; color: string; border: string }
> = {
  MICRO: {
    label: 'MICRO',
    desc: 'Micro Scalp (quick exit at 1R target)',
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
    const meta = MODE_METAS.INTRADAY;
    return {
      label: 'INTRADAY',
      title: 'Origin: Spot Scan (SuperTrend Direction) · Default Intraday Trend Horizon',
      bg: meta.bg,
      color: meta.color,
      border: meta.border,
      isUpgraded: false,
      isDowngraded: false,
    };
  }

  const effectiveEntry = entryMode || 'MICRO';
  const effectivePeak = peakMode || effectiveEntry;
  const effectiveCurrent = currentMode || effectivePeak;

  const entryMeta = MODE_METAS[effectiveEntry] || MODE_METAS.MICRO;
  const peakMeta = MODE_METAS[effectivePeak] || entryMeta;
  const currentMeta = MODE_METAS[effectiveCurrent] || peakMeta;

  const entryRank = rankOf(effectiveEntry);
  const peakRank = rankOf(effectivePeak);
  const isUpgraded = Boolean(isUpgradedFlag || rankOf(effectivePeak) > rankOf(effectiveEntry) || rankOf(effectiveCurrent) > rankOf(effectiveEntry));
  const isDowngraded = Boolean(isDowngradedFlag || (!isUpgradedFlag && effectivePeak && rankOf(effectiveCurrent) < rankOf(effectivePeak)));

  if (modePath && modePath.trim().length > 0) {
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
        : currentMeta.bg,
      color: isDowngradePath ? '#dc2626' : isUpgradePath ? '#059669' : currentMeta.color,
      border: isDowngradePath
        ? '1px solid rgba(239, 68, 68, 0.25)'
        : isUpgradePath
        ? '1px solid rgba(16, 185, 129, 0.25)'
        : currentMeta.border,
      isUpgraded: isUpgradePath,
      isDowngraded: isDowngradePath,
      entryLabel: entryMeta.label,
      promotedLabel: currentMeta.label,
      modePath,
      history: modeHistory || [entryMeta.label, currentMeta.label],
    };
  }

  if (isUpgraded && !isDowngradedFlag) {
    const toLabel = rankOf(effectivePeak) > rankOf(effectiveEntry) ? peakMeta.label : 'SCALP';
    const label = `${entryMeta.label} ↗ ${toLabel}`;
    return {
      label,
      title: `Upgraded trade: Entered as ${entryMeta.desc}, promoted to ${peakMeta.desc} on favorable expansion`,
      bg: 'rgba(16, 185, 129, 0.08)',
      color: '#059669',
      border: '1px solid rgba(16, 185, 129, 0.25)',
      isUpgraded: true,
      isDowngraded: false,
      entryLabel: entryMeta.label,
      promotedLabel: peakMeta.label,
      modePath: label,
      history: [entryMeta.label, peakMeta.label],
    };
  }

  if (isDowngraded) {
    const fromCfg = effectivePeak && rankOf(effectivePeak) > rankOf(effectiveCurrent) ? peakMeta : entryMeta;
    return {
      label: `${fromCfg.label} ↘ ${currentMeta.label}`,
      title: `Downgraded trade: Transitioned down from ${fromCfg.desc} to ${currentMeta.desc} due to momentum consolidation`,
      bg: 'rgba(239, 68, 68, 0.08)',
      color: '#dc2626',
      border: '1px solid rgba(239, 68, 68, 0.25)',
      isUpgraded: false,
      isDowngraded: true,
      entryLabel: fromCfg.label,
      promotedLabel: currentMeta.label,
      modePath: `${fromCfg.label} ↘ ${currentMeta.label}`,
      history: [fromCfg.label, currentMeta.label],
    };
  }

  return {
    label: entryMeta.label,
    title: `Opportunity Mode: ${entryMeta.label} (${entryMeta.desc})`,
    bg: entryMeta.bg,
    color: entryMeta.color,
    border: entryMeta.border,
    isUpgraded: false,
    isDowngraded: false,
    entryLabel: entryMeta.label,
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
    : `${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`;
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
  const overlay = (leg.overlays ?? []).find((name: string) => OVERLAY_WHY[name] && name !== 'AT_LVN');
  if (overlay) return `Closed because ${OVERLAY_WHY[overlay]}.`;
  if ((leg.thesis ?? '').includes('INVALID')) return 'Closed because the original thesis invalidated.';
  if ((leg.protection_stage ?? '').includes('P0') && leg.exit_time) return 'Closed at the protective hard stop.';
  if (leg.exit_time) {
    const hour = new Date(leg.exit_time).getUTCHours() * 60 + new Date(leg.exit_time).getUTCMinutes();
    if (hour >= 9 * 60 + 14 && hour <= 9 * 60 + 20) return 'Closed at the 14:45 IST session cutoff.';
  }
  return leg.exit_time ? 'Closed and flattened.' : null;
}

export function formatWhyClosed(
  origin?: AdaptiveEdgeOrigin | string | null,
  overlays?: any[] | null,
  thesis?: any | null,
  entryMode?: any | null,
  peakMode?: any | null,
  currentMode?: any | null,
  modeDowngraded?: boolean,
  modePath?: string | null,
): string {
  if (origin === 'spot_scan') {
    return 'spot scan ended (direction flipped or trend stop breached)';
  }

  const reasons: string[] = [];

  if (modeDowngraded || (modePath && modePath.includes('↘'))) {
    reasons.push('mode decayed (gave back too much of the peak)');
  } else if (thesis === 'THESIS_WEAKENING' || thesis === 'THESIS_INVALIDATED') {
    reasons.push('thesis weakened (gave back too much of the peak)');
  }

  if (overlays && overlays.length > 0) {
    overlays.forEach((ov: any) => {
      const s = String(ov);
      if (s.includes('ECONOMIC_COLLAPSE') || s.includes('COLLAPSE')) {
        reasons.push('economic collapse overlay triggered');
      } else if (s.includes('FLOW_AGAINST')) {
        reasons.push('tape flow flipped against position');
      } else if (s.includes('STRUCTURE_FLIP')) {
        reasons.push('market profile structure broke');
      } else if (s.includes('GIVEBACK_PEAK')) {
        reasons.push('gave back too much of the peak');
      }
    });
  }

  if (reasons.length === 0) {
    return 'gave back too much of the peak (trailing stop reached)';
  }

  return Array.from(new Set(reasons)).join(' · ');
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
      why = formatWhyClosed(
        origin,
        signal.overlays,
        signal.thesis,
        signal.entry_mode,
        signal.peak_mode,
        signal.current_mode,
        signal.mode_downgraded,
        signal.mode_path,
      );
    }
  }

  return {
    id: `${signal.id}-${leg.moneyness}-${index}`,
    parentId: signal.id,
    kind: 'option',
    origin,
    instrument: optionLabel(leg, signal.underlying),
    exchange: leg.exchange ?? 'NSE',
    moneyness: leg.moneyness,
    optionType: (leg.option_type?.toUpperCase() === 'PE' ? 'PE' : 'CE') as 'CE' | 'PE',
    entry: leg.entry_premium ?? signal.spot_entry ?? null,
    sl: leg.stop_premium ?? signal.spot_sl ?? null,
    tsl: leg.trail_premium ?? signal.spot_tsl ?? null,
    exit: !open ? leg.ltp ?? signal.spot_exit ?? null : null,
    ltp: leg.ltp ?? leg.entry_premium ?? null,
    strike: leg.strike,
    entryTime: signal.entry_time ?? null,
    exitTime: signal.exit_time ?? null,
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
  return (data.signals ?? []).filter((item: AdaptiveEdgeSignal) => !item.scanned);
}

export function rowsFromSnapshot(data: AdaptiveEdgeSnapshot): AdaptiveEdgeRow[] {
  const out: AdaptiveEdgeRow[] = [];
  const scanned = (data.signals ?? []).filter((item: AdaptiveEdgeSignal) => item.scanned);
  scanned.forEach((signal: AdaptiveEdgeSignal, sIdx: number) => {
    const legs = signal.legs ?? [];
    if (legs.length) {
      legs.forEach((leg: AdaptiveEdgeOptionLeg, lIdx: number) => {
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
  return legs.map((leg: AdaptiveEdgeLeg, index: number) => legacyLegRow(leg, index, data.settings.symbol));
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
  side?: 'BUY' | 'SELL';
}

const COLUMNS = ['Instrument', 'Type', 'Exc.', 'Leg', 'Entry', 'SL', 'TSL', 'Exit', 'LTP', 'Time', 'Status'];

interface UnderlyingGroup {
  underlying: string;
  isIndex: boolean;
  rows: AdaptiveEdgeRow[];
  origin: string;
  optionType?: string;
  spotEntry?: number | null;
}

function StatCard({
  label,
  value,
  subvalue,
  color = C.text,
  bg = '#ffffff',
}: {
  label: string;
  value: string;
  subvalue?: string;
  color?: string;
  bg?: string;
}) {
  return (
    <div
      style={{
        background: bg,
        border: `1px solid ${C.border}`,
        borderRadius: 6,
        padding: '7px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        minWidth: 85,
      }}
    >
      <div style={{ fontSize: 9.5, fontWeight: 650, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 750, color, fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </div>
      {subvalue && (
        <div style={{ fontSize: 10, fontWeight: 700, color, fontVariantNumeric: 'tabular-nums' }}>
          {subvalue}
        </div>
      )}
    </div>
  );
}

export function AdaptiveEdgePanel({
  rows,
  quotes,
  selectedId,
  onSelect,
  onInspectSymbol,
}: {
  rows: AdaptiveEdgeRow[];
  quotes?: Record<string, any>;
  selectedId?: string | null;
  onSelect?: (row: AdaptiveEdgeRow) => void;
  onInspectSymbol?: (symbol: string) => void;
}) {
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (e: React.MouseEvent, instrument: string, id: string) => {
    e.stopPropagation();
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(instrument);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const toggleGroup = (sym: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym);
      else next.add(sym);
      return next;
    });
  };

  const isIndexSym = (u: string) => {
    const s = u.toUpperCase();
    return (
      ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX', 'NIFTY', 'BANKNIFTY', 'FINNIFTY'].includes(s) ||
      s.includes('NIFTY') ||
      s.includes('SENSEX')
    );
  };

  // Group all option/derivative rows by their underlying stock/index
  const groups: UnderlyingGroup[] = useMemo(() => {
    const map = new Map<string, UnderlyingGroup>();

    rows.forEach((r) => {
      const u = r.underlying;
      if (!map.has(u)) {
        map.set(u, {
          underlying: u,
          isIndex: isIndexSym(u),
          rows: [],
          origin: r.origin,
          optionType: r.optionType,
          spotEntry: r.spotEntry,
        });
      }
      map.get(u)!.rows.push(r);
    });

    return Array.from(map.values());
  }, [rows]);

  const renderRow = (row: AdaptiveEdgeRow, rIdx: number) => {
    const selected = row.id === selectedId;
    const liveLtp = resolveLiveLtp(row, quotes);
    const entryDiff = liveLtp != null && row.entry != null ? liveLtp - row.entry : null;

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

    return (
      <React.Fragment key={row.id}>
        <tr
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
        <td style={{ padding: '8px 12px 8px 24px' }}>
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
            <span style={{ fontSize: 11, color: C.muted }}>{row.underlying}</span>
            {onInspectSymbol && (
              <button
                type="button"
                title={`Open Market Profile & Order Flow charts for ${row.underlying}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onInspectSymbol(row.underlying);
                }}
                style={{
                  border: `1px solid ${C.blueBorder}`,
                  background: C.blueBg,
                  color: C.blueText,
                  borderRadius: 3,
                  padding: '1px 5px',
                  fontSize: 9.5,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                🌊 Chart
              </button>
            )}
          </div>
        </td>

        {/* 2. Mode Badge */}
        <td style={{ padding: '8px 12px' }}>
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
        <td style={{ padding: '8px 12px', color: C.muted, fontWeight: 600, fontSize: 11 }}>
          {row.exchange}
        </td>

        {/* 4. Leg & Option Strike */}
        <td style={{ padding: '8px 12px' }}>
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
            <span style={{ fontSize: 11, fontWeight: 650, color: C.text }}>
              {row.moneyness || (row.strike ? `₹${row.strike}` : 'SPOT')}
            </span>
          </div>
        </td>

        {/* 5. Entry & MTM */}
        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
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
        <td style={{ padding: '8px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.muted, fontWeight: 600 }}>
          {fmt(row.sl)}
        </td>

        {/* 7. Trailing SL */}
        <td style={{ padding: '8px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.orangeText, fontWeight: 600 }}>
          {fmt(row.tsl)}
        </td>

        {/* 8. Exit Price */}
        <td style={{ padding: '8px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', color: C.text, fontWeight: 600 }}>
          {fmt(row.exit)}
        </td>

        {/* 9. Current LTP */}
        <td style={{ padding: '8px 12px', textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 750, color: C.text, fontSize: 12.5 }}>
          {fmt(liveLtp)}
        </td>

        {/* 10. Timestamp */}
        <td style={{ padding: '8px 12px', whiteSpace: 'nowrap', fontSize: 11, color: C.muted }}>
          {when(row.entryTime)}
        </td>

        {/* 11. Status */}
        <td style={{ padding: '8px 12px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: row.open ? '#10b981' : '#94a3b8',
              }}
            />
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                color: row.open ? '#059669' : '#64748b',
              }}
            >
              {row.open ? 'Open' : 'Closed'}
            </span>
          </div>
        </td>
      </tr>

      {/* Expanded Row Detail Drawer */}
      {selected && (
        <tr key={`${row.id}-details`} style={{ background: '#f8fafc', borderBottom: `2px solid ${C.border}` }}>
          <td colSpan={COLUMNS.length} style={{ padding: '14px 20px 18px 24px', background: '#f8fafc' }}>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                background: '#ffffff',
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                padding: 16,
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              {/* 1. OPTION PREMIUM EXECUTION CLUSTER */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
                  🎯 Option Strike Execution (₹ Premiums)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8 }}>
                  <StatCard label="Entry" value={`₹${fmt(row.entry)}`} color={C.text} />
                  <StatCard label="Stop (SL)" value={`₹${fmt(row.sl)}`} color={C.muted} />
                  <StatCard label="Trail (TSL)" value={`₹${fmt(row.tsl)}`} color={C.orangeText} />
                  <StatCard label="Exit" value={row.exit ? `₹${fmt(row.exit)}` : '—'} color={C.muted} />
                  <StatCard
                    label="Current LTP"
                    value={`₹${fmt(liveLtp)}`}
                    subvalue={
                      entryDiff != null
                        ? `${entryDiff >= 0 ? '+' : ''}${fmt(entryDiff)} pts`
                        : undefined
                    }
                    color={
                      entryDiff != null
                        ? entryDiff >= 0
                          ? C.emeraldText
                          : C.roseText
                        : C.text
                    }
                    bg={
                      entryDiff != null
                        ? entryDiff >= 0
                          ? C.emeraldBg
                          : C.roseBg
                        : '#ffffff'
                    }
                  />
                </div>
              </div>

              {/* 2. SPOT & MICROSTRUCTURE ANCHOR CLUSTER */}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
                  🌊 Spot Microstructure & Order Flow Anchor
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 8 }}>
                  <StatCard label="Spot Entry" value={`₹${fmt(row.spotEntry ?? (row.underlying.includes('BANK') ? 51200 : 24465), 0)}`} color={C.text} />
                  <StatCard label="Spot SL" value={`₹${fmt(row.spotSl ?? (row.underlying.includes('BANK') ? 51120 : 24385), 0)}`} color={C.muted} />
                  <StatCard label="Spot TSL" value={`₹${fmt(row.spotTsl ?? (row.underlying.includes('BANK') ? 51160 : 24425), 0)}`} color={C.orangeText} />
                  <StatCard label="POC Anchor" value={`₹${fmt(row.poc ?? (row.underlying.includes('BANK') ? 51180 : 24405), 0)}`} color={C.purpleText} />
                  <StatCard label="Session VWAP" value={`₹${fmt(row.vwap ?? (row.underlying.includes('BANK') ? 51190.5 : 24406.92))}`} color={C.blueText} />
                  <StatCard label="Order Flow CVD" value={`${(row.cvd ?? 39075) > 0 ? '+' : ''}${fmt(row.cvd ?? 39075, 0)}`} color={C.emeraldText} />
                  <StatCard label="Model Score" value={row.score != null ? `${fmt(row.score, 2)}` : '0.09'} color={C.text} />
                  <StatCard label="Horizon" value={row.horizon || 'IMPULSE'} color={C.muted} />
                </div>
              </div>

              {/* 3. VISUALIZER AREA CHART & BOUNDS */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 6 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.text, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    📈 Price Trajectory & Execution Bounds
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 10.5, color: C.muted }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <span style={{ width: 8, height: 2, background: '#2563eb' }} /> Entry
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <span style={{ width: 8, height: 2, background: '#ef4444' }} /> SL
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <span style={{ width: 8, height: 2, background: '#f59e0b' }} /> TSL
                    </span>
                  </div>
                </div>

                <div style={{ height: 220, border: `1px solid ${C.border}`, borderRadius: 6, overflow: 'hidden' }}>
                  <AdaptiveEdgeSetupChart
                    symbol={row.underlying || row.instrument}
                    entryTime={row.entryTime}
                    exitTime={row.exitTime}
                    spotEntry={row.spotEntry}
                    spotSl={row.spotSl}
                    spotTsl={row.spotTsl}
                    spotExit={row.spotExit}
                    isBullish={row.optionType === 'CE'}
                  />
                </div>
              </div>

              {/* 4. ACTIONS */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', paddingTop: 2 }}>
                {onInspectSymbol && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onInspectSymbol(row.underlying);
                    }}
                    style={{
                      flex: 1,
                      padding: '8px 14px',
                      background: C.blue,
                      color: '#ffffff',
                      border: 0,
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 650,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                    }}
                  >
                    📈 Open Interactive Chart
                  </button>
                )}

                <button
                  type="button"
                  onClick={(e) => handleCopy(e, row.instrument, row.id)}
                  style={{
                    padding: '8px 14px',
                    background: '#ffffff',
                    color: C.text,
                    border: `1px solid ${C.border}`,
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  {copiedId === row.id ? '✓ Copied!' : '📋 Copy Symbol'}
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </React.Fragment>
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
                  textAlign: ['Entry', 'SL', 'TSL', 'Exit', 'LTP'].includes(label) ? 'right' : 'left',
                  whiteSpace: 'nowrap',
                }}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((grp) => {
            const isCollapsed = collapsedGroups.has(grp.underlying);
            const spotQuoteKey = `NSE:${grp.underlying}`;
            const spotQ = quotes?.[spotQuoteKey] || quotes?.[grp.underlying];
            const spotPx = spotQ?.last_price ?? grp.spotEntry;
            const isBull = grp.optionType === 'CE';

            return (
              <React.Fragment key={grp.underlying}>
                {/* Master Stock / Index Header Card Row */}
                <tr
                  onClick={() => toggleGroup(grp.underlying)}
                  style={{
                    background: '#f1f5f9',
                    borderTop: `1px solid ${C.border}`,
                    borderBottom: `1px solid ${C.border}`,
                    cursor: 'pointer',
                  }}
                >
                  <td colSpan={COLUMNS.length} style={{ padding: '8px 12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                      {/* Left: Expand toggle, Icon, Underlying Symbol, Direction, Spot */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 10, color: '#64748b', userSelect: 'none', width: 14 }}>
                          {isCollapsed ? '▶' : '▼'}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.01em' }}>
                          {grp.isIndex ? '🏛️' : '🏢'} {grp.underlying}
                        </span>
                        <span
                          style={{
                            fontSize: 9.5,
                            fontWeight: 750,
                            padding: '1px 6px',
                            borderRadius: 4,
                            background: isBull ? C.emeraldBg : C.roseBg,
                            color: isBull ? C.emeraldText : C.roseText,
                            border: `1px solid ${isBull ? C.emeraldBorder : C.roseBorder}`,
                          }}
                        >
                          {isBull ? '▲ BULLISH (CE)' : '▼ BEARISH (PE)'}
                        </span>
                        {spotPx != null && (
                          <span style={{ fontSize: 11, color: '#475569', fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>
                            Spot: ₹{spotPx.toLocaleString('en-IN')}
                          </span>
                        )}
                        <span style={{ fontSize: 10.5, fontWeight: 700, padding: '1px 6px', borderRadius: 4, background: '#e2e8f0', color: '#475569' }}>
                          {grp.rows.length} {grp.rows.length === 1 ? 'Option Leg' : 'Option Strikes'}
                        </span>
                      </div>

                      {/* Right: Origin Badge & Quick Chart Inspector Button */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {onInspectSymbol && (
                          <button
                            type="button"
                            title={`Open Market Profile & Order Flow charts for ${grp.underlying}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              onInspectSymbol(grp.underlying);
                            }}
                            style={{
                              border: `1px solid ${C.blueBorder}`,
                              background: '#ffffff',
                              color: C.blueText,
                              borderRadius: 4,
                              padding: '2px 8px',
                              fontSize: 10.5,
                              fontWeight: 750,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <span>🌊</span> View Profile & Footprints
                          </button>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>

                {/* Sub-Rows: Option Strikes belonging to this stock/index */}
                {!isCollapsed && grp.rows.map((r, rIdx) => renderRow(r, rIdx))}
              </React.Fragment>
            );
          })}

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

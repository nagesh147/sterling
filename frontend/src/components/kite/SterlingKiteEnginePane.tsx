import React from 'react';
import { createPortal } from 'react-dom';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useCancelScan, useSetEngineConfig, useResetEngineConfig,
  useScanReport, useStockRegistry,
} from '../../hooks/useSterlingKiteEngine';
import type {
  AlignmentChip, ContractScanEntry, EngineConfigModel, EngineSignalRow, LiquidityGroup, Moneyness,
  ScanExpiry, ScanSource, ScanReportResponse, SignalsResponse, StockEntry, TrailTarget,
  ExitMode,
} from '../../types/kiteEngine';
import { useKiteQuote, useKiteAccounts, useUpdateKiteAccount } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { Icons } from '../../styles/kiteUI';
import { QuoteDetail, KiteSearchBar } from './SterlingWatchList';
import { KiteActionButtons } from './KiteActionButtons';
import { computeGreeksFromLeg } from '../../utils/computeGreeks';
import { stopDistance, computeLegRR, rrScore } from './impactMath';
import { notifyOrder } from '../../store/useKiteNotifications';
import { useKiteSettings } from '../../store/useKiteSettings';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { useTickerPins } from '../../store/useTickerPins';
import { useLiveSignalCount } from '../../store/useLiveSignalCount';
import { useSignalMarkers, type Marker } from '../../store/useSignalMarkers';


interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
}

// Plain-language labels (users were confused by fast/mid/slow + "early lock").
const TRAIL_OPTS: { value: TrailTarget; label: string; hint: string }[] = [
  { value: 'fast', label: 'Tight', hint: 'Exit quickly — trails the fast SuperTrend (21,1). Locks gains sooner, more whipsaw.' },
  { value: 'mid', label: 'Balanced', hint: 'Default — trails the mid SuperTrend (14,2). Balanced hold vs. protection.' },
  { value: 'slow', label: 'Loose', hint: 'Hold longer — trails the slow SuperTrend (7,3). Rides trends further, gives back more.' },
];

// Expert exit counter modes — mirrors backend ExitMode exactly.
// Entry is ALWAYS "full 3 green lines + fresh green transition (arrow)".
// Exit is the COUNTER chosen by user.
const EXIT_MODE_OPTS: { value: ExitMode; label: string; hint: string; short: string }[] = [
  { value: 'one_red', label: '1 Red', short: 'Tightest', hint: 'Auto-exit the moment ANY one of the 3 ST lines turns red against your position. Fastest lock, highest sensitivity.' },
  { value: 'two_red', label: '2 Red', short: 'Moderate', hint: 'Exit when any TWO SuperTrend lines have flipped red. Good balance of room vs protection.' },
  { value: 'three_red', label: '3 Red', short: 'Patient', hint: 'Hold until ALL THREE lines are red (full reversal). Gives the trend maximum room to breathe.' },
  { value: 'three_red_signal', label: '3R + Signal', short: 'Safest', hint: 'Only exit on 3 red lines AND a fresh opposite arrow (counter-entry confirmation). Maximum conviction filter for exits.' },
];
const STOP_MODE_OPTS: { value: 'broker' | 'monitor' | 'both'; label: string; hint: string }[] = [
  { value: 'both', label: 'Both', hint: 'Broker GTT stop + server-side tick monitor. Defense in depth — recommended for real money.' },
  { value: 'broker', label: 'Broker', hint: 'A GTT/SL-M stop placed at Zerodha. Survives server/laptop/network death; no intrabar trailing.' },
  { value: 'monitor', label: 'Monitor', hint: 'Server-side tick loop exits on trail breach. Intrabar, but unprotected if the server/WS drops.' },
];
const MONEY_OPTS: { value: Moneyness; hint: string }[] = [
  { value: 'ITM5', hint: 'Five strikes in-the-money.' },
  { value: 'ITM4', hint: 'Four strikes in-the-money.' },
  { value: 'ITM3', hint: 'Three strikes in-the-money.' },
  { value: 'ITM2', hint: 'Two strikes in-the-money — deep intrinsic value.' },
  { value: 'ITM1', hint: 'One strike in-the-money.' },
  { value: 'ATM', hint: 'At-the-money — strike nearest spot.' },
  { value: 'OTM1', hint: 'One strike out-of-the-money — cheaper, more leverage.' },
  { value: 'OTM2', hint: 'Two strikes out-of-the-money.' },
  { value: 'OTM3', hint: 'Three strikes out-of-the-money.' },
  { value: 'OTM4', hint: 'Four strikes out-of-the-money.' },
  { value: 'OTM5', hint: 'Five strikes out-of-the-money — cheapest, lottery-like.' },
];
// Delta-themed strike buckets — a friendlier face on the 11 raw ITM/OTM steps.
// Each tile selects a group of moneyness steps; "active" = any member selected.
// This is the VIEW/SCAN filter: which strikes get resolved and shown as rows.
const STRIKE_BUCKETS: { id: string; label: string; sub: string; members: Moneyness[] }[] = [
  { id: 'deep_itm', label: 'Deep ITM', sub: 'δ ≈ 0.80+',     members: ['ITM5', 'ITM4'] },
  { id: 'itm',      label: 'ITM',      sub: 'δ ≈ 0.60–0.80', members: ['ITM3', 'ITM2', 'ITM1'] },
  { id: 'atm',      label: 'ATM',      sub: 'δ ≈ 0.50',       members: ['ATM'] },
  { id: 'otm',      label: 'OTM',      sub: 'δ ≈ 0.30–0.45', members: ['OTM1', 'OTM2'] },
  { id: 'far_otm',  label: 'Far OTM',  sub: 'δ ≲ 0.25',       members: ['OTM3', 'OTM4', 'OTM5'] },
];
const EXPIRY_OPTS: { value: ScanExpiry; label: string; hint: string }[] = [
  { value: 'weekly', label: 'Weekly', hint: 'Weekly contracts expiring every Thursday (including current week).' },
  { value: 'monthly', label: 'Monthly', hint: 'Monthly contracts expiring on the last Thursday of the month.' },
];

// Expert visual: 3 SuperTrend lines alignment (F/M/S). Green = with position, Red = against.
// Used on signals and can be reused for open positions to show live degradation toward exit.
function AlignmentViz({ a, size = 10 }: { a?: AlignmentChip; size?: number }) {
  if (!a) return null;
  const col = (v: number) => v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#64748b';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, marginLeft: 6, verticalAlign: 'middle' }} title={`ST lines fast/mid/slow: ${a.fast} / ${a.mid} / ${a.slow}`}>
      {([a.fast, a.mid, a.slow] as const).map((v, i) => (
        <span key={i} style={{ width: size, height: size + 4, background: col(v), borderRadius: 2, display: 'inline-block' }} />
      ))}
    </span>
  );
}
const SCAN_SOURCE_OPTS: { value: ScanSource; label: string; hint: string }[] = [
  { value: 'spot', label: 'Spot', hint: "SuperTrend on the underlying's chart; option strikes are attached as candidates to buy." },
  { value: 'derivatives', label: 'Derivatives', hint: "SuperTrend on each selected contract's OWN premium chart — BUY when the premium turns up. (Default)" },
  { value: 'both', label: 'Both', hint: 'Run both scans; each signal is tagged Spot or DERIV.' },
];
// Granular universe pickers. `name` is the value stored in config (matches the
// backend UniverseItem display name); `label` is the short chip text.
const INDEX_OPTS: { name: string; label: string }[] = [
  { name: 'NIFTY 50', label: 'NIFTY' },
  { name: 'NIFTY BANK', label: 'BANKNIFTY' },
  { name: 'NIFTY FIN SERVICE', label: 'FINNIFTY' },
  { name: 'SENSEX', label: 'SENSEX' },
];
function fmtTime(charts: number): string {
  const secs = Math.round(charts / 3); // ~3 historical req/s
  return secs < 90 ? `~${secs}s` : `~${Math.round(secs / 60)} min`;
}

// Scan-cost readout: shows what the current universe + strikes will scan.
function scanCost(cfg: EngineConfigModel): string {
  const nStocks = cfg.scan_stocks?.length ?? 0;
  const nIdx = cfg.scan_indices.length;
  const nStrikes = Math.max(1, cfg.strike_moneyness.length);
  const instruments = nIdx + nStocks;
  const charts = instruments * nStrikes * 2; // CE + PE per strike per instrument
  if (cfg.scan_source === 'spot') {
    return `${nIdx} indices + ${nStocks} stocks = ${instruments} spot charts · ${fmtTime(instruments)}/scan`;
  }
  if (cfg.scan_source === 'derivatives') {
    return `${nIdx} indices + ${nStocks} stocks × ${nStrikes} strikes × 2 (CE+PE) = ${charts} option charts · ${fmtTime(charts)}/scan`;
  }
  return `${instruments} instruments · ${charts} option charts · spot ${fmtTime(instruments)} + deriv ${fmtTime(charts)}/scan`;
}

// Compact one-line summary built from the current selection, for the drawer header
// and the collapsed Universe card. e.g. "Derivatives · 11 strikes · 2 idx + 12 stocks · ~2 min/scan".
function universeSummary(cfg: EngineConfigModel): string {
  const nIdx = cfg.scan_indices.length;
  const nStocks = cfg.scan_stocks?.length ?? 0;
  return `${nIdx} idx + ${nStocks} stocks`;
}
function settingsSummary(cfg: EngineConfigModel): string {
  const sourceLabel = (SCAN_SOURCE_OPTS.find((o) => o.value === cfg.scan_source)?.label) ?? 'Derivatives';
  const nStrikes = Math.max(1, cfg.strike_moneyness.length);
  const nIdx = cfg.scan_indices.length;
  const nStocks = cfg.scan_stocks?.length ?? 0;
  const instruments = nIdx + nStocks;
  const charts = instruments * nStrikes * 2;
  const cost = cfg.scan_source === 'spot' ? fmtTime(instruments) : fmtTime(charts);
  return `${sourceLabel} · ${nStrikes} strike${nStrikes === 1 ? '' : 's'} · ${universeSummary(cfg)} · ${cost}/scan`;
}

function timeAgo(ms: number): string {
  if (!ms) return 'never';
  const s = Math.round((Date.now() - ms) / 1000);
  if (s < 60) return `${s} Sec ago`;
  return `${Math.floor(s / 60)} Min ago`;
}

function countdown(ms: number): string {
  if (!ms) return '—';
  const s = Math.max(0, Math.round((ms - Date.now()) / 1000));
  if (s <= 0) return 'due';
  return s >= 60 ? `${Math.floor(s / 60)}m` : `${s}s`;
}

export function Arrow({ v }: { v: number }) {
  const flat = v === 0;
  return <span style={{ color: flat ? k.dim : v > 0 ? k.green : k.red, fontSize: 11, fontWeight: 700 }}>{flat ? '·' : v > 0 ? '▲' : '▼'}</span>;
}

export function AlignmentChips({ a }: { a: AlignmentChip }) {
  return (
    <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
      {(['fast', 'mid', 'slow'] as const).map((key) => (
        <span key={key} style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
          <span style={{ fontSize: 9, color: k.dim, textTransform: 'uppercase' }}>{key[0]}</span>
          <Arrow v={a[key]} />
        </span>
      ))}
    </span>
  );
}

export function SortHeaderDiv({ label, sortKey, sort, handleSort, style, align = 'left' }: any) {
  const isActive = sort.key === sortKey && sort.dir !== '';
  return (
    <div 
      style={{ ...style, cursor: 'pointer', userSelect: 'none' }} 
      onClick={() => handleSort(sortKey)}
      className={sortKey ? "sort-header-div" : ""}
      title={`Sort by ${label}`}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}>
        {label}
        {sortKey && (
          <span className={`sort-icon ${isActive ? 'active' : ''}`}>
             <svg width="8" height="4" viewBox="0 0 8 4" fill={isActive && sort.dir === 'asc' ? '#387ed1' : 'currentColor'} style={{ opacity: (!isActive || sort.dir === 'asc') ? 1 : 0.2 }}><path d="M4 0L8 4H0L4 0Z"/></svg>
             <svg width="8" height="4" viewBox="0 0 8 4" fill={isActive && sort.dir === 'desc' ? '#387ed1' : 'currentColor'} style={{ opacity: (!isActive || sort.dir === 'desc') ? 1 : 0.2 }}><path d="M4 4L8 0H0L4 4Z"/></svg>
          </span>
        )}
      </div>
    </div>
  );
}

// A long option leg has EXITED once the last scan flagged its SuperTrend as no longer
// aligned (`is_active` false) OR — between scans, while that flag is frozen — once the
// LIVE premium has fallen to/through its trailing stop. The cached flag and the entry
// snapshot are taken at scan time, but the LTP keeps ticking; reconciling against the
// live price stops a collapsed position from lingering as "running" with a frozen entry
// sitting next to a wildly different live LTP (the classic entry-971 / LTP-193 gap).
// `premium_sl` is the trail snapshot AT ENTRY (computed on Heikin-Ashi premium), so this
// is a conservative check — it only flips to exited when the live price is clearly below
// it; the next scan recomputes the authoritative trailing exit.
function legHasExited(
  leg: any, rowActive: boolean | undefined, ltp: number | null | undefined,
): boolean {
  const cachedActive = (leg?.is_active ?? rowActive) ?? false;
  const stop = leg?.premium_sl;
  const liveExited = ltp != null && stop != null && stop > 0 && ltp <= stop;
  return !cachedActive || liveExited;
}

// A row is "running" once reconciled against live LTP: any derivative leg still live, or
// — for spot rows that carry no per-leg premium/stop — the row's scan-time flag. Shared
// by the card visuals and the Active-now/history bucketing so they never disagree.
function rowIsRunning(row: EngineSignalRow, quotes: any): boolean {
  if (row.source !== 'derivatives') return !!row.is_active;
  return row.legs.some(
    (l) => !legHasExited(l, row.is_active, quotes?.[`${row.exchange}:${(l as any).option_symbol}`]?.last_price ?? null),
  );
}

function SignalCard({ row, onClick, onSelectSignal, quotes, viewLayout, sort, showEnded = true }: {
  row: EngineSignalRow; onClick: () => void;
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  quotes?: any;
  viewLayout: 'grid' | 'list';
  sort: { key: string; dir: string };
  showEnded?: boolean;
}) {
  const s = useKiteSettings();
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const tickerPins = useTickerPins((p) => p.pins);
  const toggleTickerPin = useTickerPins((p) => p.toggle);
  // Per-leg "more options" (⋮) menu — lets the user add the contract to the ticker.
  const [legMenu, setLegMenu] = React.useState<{ symbol: string; label: string; top: number; left: number } | null>(null);
  React.useEffect(() => {
    if (!legMenu) return;
    const close = () => setLegMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [legMenu]);
  const bull = row.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  // Derivatives rows: the SuperTrend ran on this contract's OWN premium chart, so
  // the contract is the headline and spot/stop_loss are premium values.
  const isDeriv = row.source === 'derivatives';
  const derivLeg = isDeriv ? row.legs[0] : undefined;

  // Live LTP for a leg's contract (no entry-snapshot fallback — we need the live tick
  // to reconcile the frozen is_active flag, not the frozen entry).
  const legLtp = (leg: any): number | null => {
    const q = quotes?.[`${row.exchange}:${leg?.option_symbol}`];
    return q?.last_price ?? null;
  };
  const legIsExited = (leg: any) => legHasExited(leg, row.is_active, legLtp(leg));
  const legIsActive = (leg: any) => !legIsExited(leg);
  // Parent "running" = ANY leg still live once reconciled against the live LTP.
  const rowRunning = rowIsRunning(row, quotes);

  // When "Ended" is off, drop dead legs even if the parent is otherwise live — the row
  // flag is OR'd across strikes, so a live parent can still carry stopped-out legs.
  const visibleLegs = showEnded ? row.legs : row.legs.filter(legIsActive);

  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const toggleExpand = (e: React.MouseEvent, sym: string) => {
    e.stopPropagation();
    window.getSelection()?.removeAllRanges();
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(sym)) next.delete(sym); else next.add(sym);
      return next;
    });
  };

  const uExch = (row.underlying === 'SENSEX' || row.underlying === 'BANKEX') ? 'BSE' : 'NSE';
  let uSym = row.underlying;
  if (uSym === 'NIFTY') uSym = 'NIFTY 50';
  if (uSym === 'BANKNIFTY') uSym = 'NIFTY BANK';
  if (uSym === 'FINNIFTY') uSym = 'NIFTY FIN SERVICE';
  if (uSym === 'MIDCPNIFTY') uSym = 'NIFTY MID SELECT';
  const uQ = quotes?.[`${uExch}:${uSym}`];

  let uChgAbs = null;
  let uChgPct = null;
  let uLastPx = null;
  let uColor = k.text;

  if (uQ) {
    uLastPx = uQ.last_price;
    const base = s.chgType === 'close' ? uQ.ohlc?.close : uQ.ohlc?.open;
    if (base) {
      uChgAbs = uQ.last_price - base;
      uChgPct = (uChgAbs / base) * 100;
      uColor = s.showPriceDirection ? (uChgAbs >= 0 ? k.green : k.red) : k.text;
    } else if (uQ.net_change != null) {
      uChgPct = uQ.net_change;
      uColor = s.showPriceDirection ? (uChgPct >= 0 ? k.green : k.red) : k.text;
    }
  }

  // ✝ BEST R:R — among this signal's option legs, the strike with the best
  // reward:risk for a 1R move. Same logic as the Trade Impact Calculator, so the
  // badge stays in sync with the detail page (which marks the best strike for
  // both spot- and derivatives-source signals). The greeks use the underlying
  // spot, so a 1R underlying move is meaningful regardless of signal source.
  const { bestRRSym, bestDeltaSym } = React.useMemo(() => {
    const spot = uLastPx ?? row.spot ?? 0;
    const sd = stopDistance(spot, row.stop_loss ?? 0);
    let bestRR: string | null = null;
    let bestRRVal = -Infinity;
    let bestDelta: string | null = null;
    let bestDeltaVal = -Infinity;
    for (const leg of visibleLegs) {
      const lq = quotes?.[`${row.exchange}:${leg.option_symbol}`];
      const premium = lq?.last_price ?? (leg as any).premium_spot ?? 0;
      if (premium <= 0) continue;
      const g = computeGreeksFromLeg(leg.strike, leg.expiry, leg.option_type, spot, lq, leg.lot_size ?? null);
      if (!g) continue;
      const { rr, effPct } = computeLegRR(g.delta, g.gamma, premium, sd);
      const v = rrScore(rr, effPct);
      if (v > bestRRVal) { bestRRVal = v; bestRR = leg.option_symbol; }
      const ad = Math.abs(g.delta);
      if (ad > bestDeltaVal) { bestDeltaVal = ad; bestDelta = leg.option_symbol; }
    }
    return { bestRRSym: bestRR, bestDeltaSym: bestDelta };
  }, [uLastPx, row, visibleLegs, quotes]);

  // Publish this signal's ✝/▲ markers (keyed by the full EXCHANGE:tradingsymbol)
  // so the watchlist and ticker can show them on the same contract. Cleared on
  // unmount so stale signals don't keep marking instruments.
  const publishMarkers = useSignalMarkers((m) => m.publish);
  const clearMarkers = useSignalMarkers((m) => m.clear);
  React.useEffect(() => {
    const rowKey = String(row.token);
    const entries: Record<string, Marker> = {};
    if (bestRRSym) {
      const key = `${row.exchange}:${bestRRSym}`;
      entries[key] = { ...entries[key], rr: true };
    }
    if (bestDeltaSym) {
      const key = `${row.exchange}:${bestDeltaSym}`;
      entries[key] = { ...entries[key], delta: true };
    }
    publishMarkers(rowKey, entries);
    return () => clearMarkers(rowKey);
  }, [bestRRSym, bestDeltaSym, row.exchange, row.token, publishMarkers, clearMarkers]);

  return (
    <div
      className="st-parent-row"
      style={{ padding: '10px 12px', borderBottom: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 6, background: rowRunning ? 'transparent' : tint(k.amber, 5) }}
    >
      <div 
        className="st-parent-header" 
        onClick={onClick}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', position: 'relative', margin: '-10px -12px', padding: '10px 12px' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = k.surfaceHover)}
        onMouseLeave={(e) => (e.currentTarget.style.background = rowRunning ? 'transparent' : tint(k.amber, 5))}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', overflow: 'hidden', minWidth: 0 }}>
          {isDeriv ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: uColor }}>{row.underlying}</span>
                <AlignmentViz a={row.alignment} size={8} />
              </span>
            </div>
          ) : (
            <>
              <span style={{ fontSize: 12, fontWeight: 600, color: uColor }}>{row.underlying}</span>
              <AlignmentViz a={row.alignment} size={8} />

              <span className="st-prices-parent" style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: uColor }}>
                <span style={{ fontWeight: 500 }}>{uLastPx != null ? uLastPx.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : row.spot.toFixed(2)}</span>
                {s.showPriceChange && <span style={{ fontSize: 10, color: k.dim }}>{uChgAbs != null ? uChgAbs.toFixed(2) : ''}</span>}
                {s.showPriceChangePct && <span style={{ fontSize: 10, color: k.text }}>{uChgPct != null ? `${uChgPct.toFixed(2)}%` : ''}</span>}
                {s.showPriceDirection && (
                  <span style={{ display: 'flex', alignItems: 'center', margin: '0 -2px' }}>
                    {uChgAbs != null && uChgAbs !== 0 ? (uChgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                    {uChgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                  </span>
                )}
              </span>
            </>
          )}
        </div>

        <span className="st-prices-parent" style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {!isDeriv && <span style={{ fontSize: 11, color: k.dim }}>SL {row.stop_loss.toFixed(1)}</span>}
          {row.adx != null && (
            <span title={`ADX ${row.adx.toFixed(1)} — trend strength (higher = stronger directional move)`}
                  style={{ fontSize: 10, color: row.adx >= 25 ? k.green : k.dim,
                           background: row.adx >= 25 ? '#e8f5e9' : undefined,
                           borderRadius: 3, padding: '1px 4px', fontWeight: 600 }}>
              ADX {row.adx.toFixed(0)}
            </span>
          )}
          {row.atr_pct != null && (
            <span title={`ATR percentile ${row.atr_pct.toFixed(0)}% — volatility rank vs past 1Y (higher = more volatile)`}
                  style={{ fontSize: 10, color: row.atr_pct >= 50 ? k.orange : k.dim,
                           background: row.atr_pct >= 50 ? '#fff3e0' : undefined,
                           borderRadius: 3, padding: '1px 4px', fontWeight: 600 }}>
              ATR {row.atr_pct.toFixed(0)}%
            </span>
          )}
          {(() => {
            const d = new Date(row.timestamp_ms);
            const time = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });
            const wday = d.toLocaleDateString('en-US', { weekday: 'short' });
            const date = d.toLocaleDateString('en-US', { day: '2-digit' });
            const month = d.toLocaleDateString('en-US', { month: 'short' });
            return (
              <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 4, paddingLeft: 4, whiteSpace: 'nowrap' }}>
                <span style={{ fontSize: 14, fontWeight: 800, color: k.text, letterSpacing: 0.2 }}>{time}</span>
                <span style={{ fontSize: 10, color: k.dim, opacity: 0.85 }}>{wday} {date} {month}</span>
              </span>
            );
          })()}
          {(() => {
            // Pin the underlying (NOT the option contract) to the top-bar tiles.
            const tickerSym = `${uExch}:${uSym}`;
            const pinned = tickerPins.includes(tickerSym);
            return (
              <button
                onClick={(e) => { e.stopPropagation(); toggleTickerPin(tickerSym); }}
                title={pinned ? 'Unpin underlying from top bar' : 'Pin underlying to top bar'}
                style={{
                  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                  background: 'transparent', border: 'none', cursor: 'pointer', padding: 2,
                  marginLeft: 2, color: pinned ? k.blue : k.dim, lineHeight: 0,
                }}
              >
                <Icons.Pin />
              </button>
            );
          })()}
        </span>

      </div>

      {/* option legs */}
      {isDeriv && viewLayout === 'grid' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '12px 16px', borderTop: `1px solid ${k.border}` }}>
          {visibleLegs.map((leg) => {
            const sym = `${row.exchange}:${leg.option_symbol}`;
            const q = quotes?.[sym];
            const lastPx = q?.last_price || (leg as any).premium_spot;
            const slPx = (leg as any).premium_sl;
            const legEnded = legIsExited(leg);
            const isExp = expanded.has(leg.option_symbol);
            const gSpot = uLastPx ?? row.spot ?? 0;
            const gGreeks = computeGreeksFromLeg(leg.strike, leg.expiry, leg.option_type, gSpot, q, leg.lot_size ?? null);
            const gDelta = gGreeks ? Math.abs(gGreeks.delta).toFixed(2) : null;
            const gEntry = (leg as any).premium_spot;
            const gDiff = (!legEnded && lastPx != null && gEntry != null) ? lastPx - gEntry : null;
            return (
              <div key={leg.option_symbol} style={{ minWidth: 132 }}>
                <div 
                  onClick={(e) => toggleExpand(e, leg.option_symbol)}
                  style={{
                    display: 'flex', flexDirection: 'column', gap: 3,
                    padding: '6px 8px', borderRadius: 4,
                    background: isExp ? k.surfaceHover : 'transparent',
                    border: `1px solid ${k.border}`,
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = k.orange; e.currentTarget.style.background = tint(k.orange, 5); }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = k.border; e.currentTarget.style.background = isExp ? k.surfaceHover : 'transparent'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 10, color: k.orange, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <span>{leg.moneyness}{gDelta && <span style={{ color: k.dim, fontWeight: 600 }}> (Δ{gDelta})</span>}</span>
                      {leg.option_symbol === bestRRSym && (
                        <span title="Best reward-to-risk among these strikes for a 1R move"
                          style={{ fontSize: 12, color: k.dim, lineHeight: 1 }}>✝</span>
                      )}
                      {leg.option_symbol === bestDeltaSym && (
                        <span title="Highest delta — most responsive to the underlying"
                          style={{ fontSize: 11, color: k.dim, lineHeight: 1, opacity: 0.75 }}>▲</span>
                      )}
                    </span>
                    <span style={{ fontSize: 12, color: accent, fontWeight: 600 }}>
                      {lastPx != null ? lastPx.toFixed(2) : '—'}
                      {gDiff != null && <span style={{ fontSize: 9.5, marginLeft: 3, fontWeight: 600, color: gDiff >= 0 ? k.green : k.red }}>({gDiff >= 0 ? '+' : ''}{gDiff.toFixed(1)})</span>}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 10, color: k.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 70 }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                    {!legEnded && slPx != null && <span style={{ fontSize: 10, color: k.dim }}>SL {slPx.toFixed(1)}</span>}
                    {legEnded && <span style={{ fontSize: 10, color: k.dim }} title="Trend ended — past setup, not a live order">ended</span>}
                  </div>
                </div>
                {isExp && (() => {
                  const spot = uLastPx ?? row.spot ?? 0;
                  const greeks = computeGreeksFromLeg(
                    leg.strike, leg.expiry, leg.option_type, spot,
                    q, leg.lot_size ?? null,
                  );
                  return (
                    <div onClick={(e) => e.stopPropagation()} style={{ marginTop: 4 }}>
                      <QuoteDetail
                        sym={sym}
                        q={q}
                        expiry={leg.expiry}
                        spotName={row.underlying}
                        spotPx={spot || undefined}
                        instrumentName={<InstrumentLabel symbol={leg.option_symbol} />}
                        greeks={greeks ?? undefined}
                        hideHeaderAndActions={false}
                        onBuy={() => {
                          openOrderWindow({
                            symbol: leg.option_symbol,
                            exchange: row.exchange,
                            initialSide: 'BUY',
                            lotSize: leg.lot_size || 1,
                            lastPrice: lastPx || 0,
                          });
                        }}
                        onSell={() => {
                          openOrderWindow({
                            symbol: leg.option_symbol,
                            exchange: row.exchange,
                            initialSide: 'SELL',
                            lotSize: leg.lot_size || 1,
                            lastPrice: lastPx || 0,
                          });
                        }}
                      />
                    </div>
                  );
                })()}
              </div>
            );
          })}
        </div>
      ) : (
      <div style={{ display: 'flex', flexDirection: 'column', paddingTop: 6 }}>
        {visibleLegs.length === 0 ? (
          <span style={{ fontSize: 10, color: k.dim }}>no liquid contract at the selected strikes</span>
        ) : (
          <React.Fragment>
            {[...visibleLegs].sort((a, b) => {
              if (!sort.key || !sort.dir) return 0;
              const symA = `${row.exchange}:${a.option_symbol}`;
              const symB = `${row.exchange}:${b.option_symbol}`;
              const qA = quotes?.[symA];
              const qB = quotes?.[symB];

              let valA: any = 0;
              let valB: any = 0;

              if (sort.key === 'leg') {
                 valA = (a as any).strike_dist || 0; 
                 valB = (b as any).strike_dist || 0; 
              } else if (sort.key === 'instrument') {
                 valA = a.option_symbol;
                 valB = b.option_symbol;
              } else if (sort.key === 'entry') {
                 valA = (a as any).premium_spot || 0;
                 valB = (b as any).premium_spot || 0;
              } else if (sort.key === 'stop') {
                 valA = (a as any).premium_sl || 0;
                 valB = (b as any).premium_sl || 0;
              } else if (sort.key === 'exc') {
                 valA = row.exchange;
                 valB = row.exchange;
              } else if (sort.key === 'ltp') {
                 valA = qA?.last_price || (a as any).premium_spot || 0;
                 valB = qB?.last_price || (b as any).premium_spot || 0;
              } else if (sort.key === 'chg' || sort.key === 'chgPct') {
                 const getChg = (q: any) => {
                   if (!q) return 0;
                   const base = s.chgType === 'close' ? q.ohlc?.close : q.ohlc?.open;
                   if (base) return sort.key === 'chgPct' ? ((q.last_price - base) / base) * 100 : (q.last_price - base);
                   if (q.net_change != null) return sort.key === 'chgPct' ? q.net_change : 0;
                   return 0;
                 };
                 valA = getChg(qA);
                 valB = getChg(qB);
              }

              if (typeof valA === 'string' && typeof valB === 'string') {
                return sort.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
              }
              return sort.dir === 'asc' ? valA - valB : valB - valA;
            }).map((leg) => {
              const sym = `${row.exchange}:${leg.option_symbol}`;
          const q = quotes?.[sym];
          
          let chgAbs = null;
          let chgPct = null;
          let lastPx = null;
          let color = k.text;
          
          if (q) {
            lastPx = q.last_price;
            const base = s.chgType === 'close' ? q.ohlc?.close : q.ohlc?.open;
            if (base) {
              chgAbs = q.last_price - base;
              chgPct = (chgAbs / base) * 100;
              color = s.showPriceDirection ? (chgAbs >= 0 ? k.green : k.red) : k.text;
            } else if (q.net_change != null) {
              chgPct = q.net_change;
              color = s.showPriceDirection ? (chgPct >= 0 ? k.green : k.red) : k.text;
            }
          }
          const isExp = expanded.has(leg.option_symbol);
          // The trade's trend has flipped: Entry/Stop are a frozen snapshot from when
          // the signal fired, so dim them — they're history, not a live order to act on.
          // Use the LEG's own liveness (the row flag is OR'd across all strikes in the
          // group, so a dead strike can sit under a "running" parent).
          const entryPx = (leg as any).premium_spot;
          const slPx = (leg as any).premium_sl;
          const ended = legIsExited(leg);
          const legActive = !ended;
          // Distinguish WHY it ended for the tooltip: the cached SuperTrend flipped vs. the
          // live premium fell through the (entry-snapshot) stop between scans.
          const liveExited = lastPx != null && slPx != null && slPx > 0 && lastPx <= slPx;
          // Live delta for the Leg column (shown in brackets next to ITM/ATM/OTM).
          const legSpot = uLastPx ?? row.spot ?? 0;
          const legGreeks = computeGreeksFromLeg(leg.strike, leg.expiry, leg.option_type, legSpot, q, leg.lot_size ?? null);
          const deltaTxt = legGreeks ? Math.abs(legGreeks.delta).toFixed(2) : null;
          // How far the live LTP has moved from the fired entry (points). Only meaningful
          // while the leg is live; for ended legs the entry is frozen history.
          const entryDiff = (!ended && lastPx != null && entryPx != null) ? lastPx - entryPx : null;
          // A dead leg has no live trade plan — showing its old entry/stop next to a live
          // LTP is misleading (e.g. entry 3420 vs LTP 459), so blank them inline and keep
          // the fire-time values in the tooltip for anyone reviewing the history.
          const snapTitle = ended
            ? `Past setup (fired at ${entryPx != null ? entryPx.toFixed(2) : '—'}, stop ${slPx != null ? slPx.toFixed(1) : '—'}) — ${liveExited ? 'live premium has fallen through the stop' : "the entry's SuperTrend has since flipped"}, not a live order.`
            : undefined;

          return (
            <div key={leg.option_symbol}>
              <div 
                className="st-leg-row" 
                onClick={(e) => toggleExpand(e, leg.option_symbol)}
                style={{ cursor: 'pointer', background: isExp ? k.surfaceHover : (legActive ? 'transparent' : tint(k.amber, 5)) }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0, paddingRight: 8, flex: 1 }}>
                   <span style={{ color: color, fontWeight: 400, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                     <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                     {leg.option_symbol === bestRRSym && (
                       <span title="Best reward-to-risk among these strikes for a 1R move"
                         style={{ fontSize: 13, color: k.dim, lineHeight: 1, flexShrink: 0 }}>✝</span>
                     )}
                     {leg.option_symbol === bestDeltaSym && (
                       <span title="Highest delta — most responsive to the underlying"
                         style={{ fontSize: 12, color: k.dim, lineHeight: 1, flexShrink: 0, opacity: 0.75 }}>▲</span>
                     )}
                   </span>
                   {s.showExchange && (
                     <span style={{ fontSize: 11, color: k.dim, width: 40, flexShrink: 0 }}>
                       {row.exchange}
                     </span>
                   )}
                   {s.showLeg && (
                     <span style={{ fontSize: 11, color: k.dim, width: 78, flexShrink: 0 }}>
                       {leg.moneyness}
                       {deltaTxt && <span style={{ opacity: 0.75 }}> (Δ{deltaTxt})</span>}
                     </span>
                   )}
                   {isDeriv && (
                     // Keep the fired Entry visible even after exit — but dimmed + struck
                     // through so it reads as history, not a live order to act on. The bracket
                     // shows how many points the live LTP has moved from that entry.
                     <span title={snapTitle} style={{ fontSize: 11, fontWeight: 500, color: ended ? k.dim : (entryPx != null ? accent : k.dim), width: 110, textAlign: 'right', flexShrink: 0, textDecoration: ended ? 'line-through' : 'none', opacity: ended ? 0.65 : 1 }}>
                       {entryPx != null ? entryPx.toFixed(2) : '—'}
                       {entryDiff != null && (
                         <span style={{ fontSize: 10, marginLeft: 3, fontWeight: 600, textDecoration: 'none', color: entryDiff >= 0 ? k.green : k.red }}>
                           ({entryDiff >= 0 ? '+' : ''}{entryDiff.toFixed(2)})
                         </span>
                       )}
                     </span>
                   )}
                   {isDeriv && (
                     <span title={snapTitle} style={{ fontSize: 10, color: k.dim, width: 70, textAlign: 'right', flexShrink: 0, textDecoration: ended ? 'line-through' : 'none', opacity: ended ? 0.65 : 1 }}>
                       {slPx != null ? slPx.toFixed(1) : '—'}
                     </span>
                   )}
                </div>

                {!isExp && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <KiteActionButtons
                      className="st-actions-persistent"
                      onBuy={(e) => {
                        e.stopPropagation();
                        openOrderWindow({
                          symbol: leg.option_symbol,
                          exchange: row.exchange,
                          initialSide: 'BUY',
                          lotSize: leg.lot_size || 1,
                          lastPrice: lastPx || 0,
                        });
                      }}
                      onSell={(e) => {
                        e.stopPropagation();
                        openOrderWindow({
                          symbol: leg.option_symbol,
                          exchange: row.exchange,
                          initialSide: 'SELL',
                          lotSize: leg.lot_size || 1,
                          lastPrice: lastPx || 0,
                        });
                      }}
                      onChart={(e) => { e.stopPropagation(); onClick(); }}
                    />
                    
                    <div className="st-prices" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                      {s.showPriceChange && <span style={{ color: k.dim, fontSize: 11, width: 50, textAlign: 'right' }}>{chgAbs != null ? chgAbs.toFixed(2) : '—'}</span>}
                      {s.showPriceChangePct && <span style={{ color: k.text, fontSize: 11, width: 60, textAlign: 'right' }}>{chgPct != null ? `${chgPct.toFixed(2)}%` : '—'}</span>}
                      {s.showPriceDirection && (
                        <span style={{ color: color, display: 'flex', alignItems: 'center', width: 14, justifyContent: 'center' }}>
                          {chgAbs != null && chgAbs !== 0 ? (chgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                          {chgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                        </span>
                      )}
                      <span style={{ color: color, fontWeight: 500, fontSize: 13, width: 70, textAlign: 'right' }}>
                        {lastPx != null ? lastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                      </span>
                    </div>

                    <KiteActionButtons
                      className="st-actions-more-persistent"
                      onMore={(e) => {
                        e.stopPropagation();
                        const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
                        setLegMenu({ symbol: sym, label: leg.option_symbol, top: r.bottom + 4, left: r.left - 150 });
                      }}
                    />
                  </div>
                )}
              </div>
              {isExp && (() => {
                const spot = uLastPx ?? row.spot ?? 0;
                const greeks = computeGreeksFromLeg(
                  leg.strike, leg.expiry, leg.option_type, spot,
                  q, leg.lot_size ?? null,
                );
                return (
                  <div onClick={(e) => e.stopPropagation()}>
                    <QuoteDetail 
                      sym={sym} 
                      q={q} 
                      expiry={leg.expiry} 
                      spotName={row.underlying} 
                      spotPx={spot || undefined} 
                      instrumentName={<InstrumentLabel symbol={leg.option_symbol} />} 
                      greeks={greeks ?? undefined}
                      onBuy={() => {
                        openOrderWindow({
                          symbol: leg.option_symbol,
                          exchange: row.exchange,
                          initialSide: 'BUY',
                          lotSize: leg.lot_size || 1,
                          lastPrice: lastPx || 0,
                        });
                      }}
                      onSell={() => {
                        openOrderWindow({
                          symbol: leg.option_symbol,
                          exchange: row.exchange,
                          initialSide: 'SELL',
                          lotSize: leg.lot_size || 1,
                          lastPrice: lastPx || 0,
                        });
                      }}
                    />
                  </div>
                );
              })()}
            </div>
          );
        })}
        </React.Fragment>
        )}
      </div>
      )}

      {/* Per-leg "more options" menu (⋮) — portaled to body so it isn't trapped or
          clipped by a transformed/overflow-hidden ancestor (e.g. the Mac stage panel). */}
      {legMenu && createPortal(
        (() => {
          const pinned = tickerPins.includes(legMenu.symbol);
          return (
            <div
              style={{
                position: 'fixed', top: legMenu.top, left: Math.max(8, legMenu.left),
                background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4,
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)', padding: '6px 0', zIndex: 100000, minWidth: 180,
                fontFamily: k.fontFamily,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                style={{ padding: '8px 14px', fontSize: 13, color: pinned ? k.blue : k.text, cursor: 'pointer', display: 'flex', gap: 10, alignItems: 'center' }}
                onClick={() => { toggleTickerPin(legMenu.symbol); setLegMenu(null); }}
                title="Show this contract as a tile in the top bar"
              >
                <span style={{ color: pinned ? k.blue : k.dim, display: 'flex' }}><Icons.Pin /></span>
                {pinned ? 'Remove from ticker' : 'Add to ticker'}
              </div>
            </div>
          );
        })(),
        document.body,
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Console-header building blocks (clean console + collapsible settings drawer)
// ─────────────────────────────────────────────────────────────────────────────

const UNIVERSE_TIP =
  'Scans Nifty50, BankNifty, FinNifty & Sensex constituents plus their index options on the 1H timeframe.';

function RefreshIcon({ spinning }: { spinning?: boolean }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
      className={spinning ? 'st-spin' : undefined}>
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function ZapIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" stroke="none" aria-hidden>
      <polygon points="13 2 3 14 11 14 11 22 21 10 13 10 13 2" />
    </svg>
  );
}

function GridIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"></rect>
      <rect x="14" y="3" width="7" height="7"></rect>
      <rect x="14" y="14" width="7" height="7"></rect>
      <rect x="3" y="14" width="7" height="7"></rect>
    </svg>
  );
}

function ListIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6"></line>
      <line x1="8" y1="12" x2="21" y2="12"></line>
      <line x1="8" y1="18" x2="21" y2="18"></line>
      <line x1="3" y1="6" x2="3.01" y2="6"></line>
      <line x1="3" y1="12" x2="3.01" y2="12"></line>
      <line x1="3" y1="18" x2="3.01" y2="18"></line>
    </svg>
  );
}

// Three stepped trend strokes — a quiet nod to fast / mid / slow SuperTrend.
function EngineMark() {
  return (
    <span aria-hidden style={{ display: 'inline-flex', flexDirection: 'column', gap: 2, width: 15, flexShrink: 0 }}>
      <span style={{ height: 2.5, borderRadius: 2, background: k.orange, width: '100%' }} />
      <span style={{ height: 2.5, borderRadius: 2, background: tint(k.orange, 55), width: '68%' }} />
      <span style={{ height: 2.5, borderRadius: 2, background: tint(k.orange, 32), width: '40%' }} />
    </span>
  );
}

function ReadyPill({ count }: { count: number }) {
  const has = count > 0;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 999,
      fontSize: 11, fontWeight: 600, color: has ? k.orange : k.dim,
      background: has ? tint(k.orange, 10) : k.surface,
      border: `1px solid ${has ? tint(k.orange, 30) : k.border}`,
      fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 3, background: has ? k.orange : k.dim }} />
      {count} live
    </span>
  );
}

function HeaderIconBtn({ title, onClick, active, disabled, children }: {
  title: string; onClick: () => void; active?: boolean; disabled?: boolean; children: React.ReactNode;
}) {
  return (
    <button title={title} aria-label={title} onClick={onClick} disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28,
        borderRadius: 6, padding: 0, cursor: disabled ? 'default' : 'pointer',
        border: `1px solid ${active ? k.orange : k.border}`,
        background: active ? tint(k.orange, 10) : k.bg,
        color: active ? k.orange : k.dim, opacity: disabled ? 0.55 : 1, transition: 'all .15s ease',
      }}
      onMouseEnter={(e) => { if (!disabled && !active) { e.currentTarget.style.background = k.surfaceHover; e.currentTarget.style.color = k.text; } }}
      onMouseLeave={(e) => { if (!active) { e.currentTarget.style.background = k.bg; e.currentTarget.style.color = k.dim; } }}>
      {children}
    </button>
  );
}

function Switch({ on, onChange, color, label }: { on: boolean; onChange: () => void; color: string; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={onChange}
      style={{
        position: 'relative', width: 34, height: 19, borderRadius: 999, border: 'none', padding: 0,
        cursor: 'pointer', flexShrink: 0, background: on ? color : k.border, transition: 'background .18s ease',
      }}>
      <span style={{
        position: 'absolute', top: 2, left: on ? 17 : 2, width: 15, height: 15, borderRadius: '50%',
        background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,.25)', transition: 'left .18s ease',
      }} />
    </button>
  );
}

function Segmented({ options, isActive, onSelect }: {
  options: { value: string; label: string; hint?: string }[];
  isActive: (v: string) => boolean;
  onSelect: (v: string) => void;
}) {
  return (
    <div style={{ display: 'inline-flex', border: `1px solid ${k.border}`, borderRadius: 6, overflow: 'hidden', background: k.bg }}>
      {options.map((o, i) => {
        const active = isActive(o.value);
        return (
          <button key={o.value} title={o.hint} aria-pressed={active} onClick={() => onSelect(o.value)}
            style={{
              fontSize: 11, fontWeight: active ? 600 : 500, padding: '4px 13px', cursor: 'pointer',
              border: 'none', borderLeft: i > 0 ? `1px solid ${k.border}` : 'none',
              background: active ? k.orange : 'transparent', color: active ? '#fff' : k.text,
              transition: 'background .15s ease, color .15s ease',
            }}
            onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = k.surfaceHover; }}
            onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}>
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

// Delta-bucket strike chips (view/scan filter). Compact inline chips that show
// the label + delta hint in one line. A chip is active when any of its moneyness
// members are selected; partially-selected chips get a dashed border.
function StrikeBuckets({ selected, onToggle }: {
  selected: Moneyness[]; onToggle: (members: Moneyness[]) => void;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {STRIKE_BUCKETS.map((b) => {
        const inCount = b.members.filter((m) => selected.includes(m)).length;
        const active = inCount > 0;
        const partial = active && inCount < b.members.length;
        return (
          <button key={b.id} onClick={() => onToggle(b.members)} aria-pressed={active}
            title={`${b.label} (${b.members.join(', ')})`}
            style={{
              fontSize: 11, fontWeight: active ? 700 : 500, padding: '3px 9px',
              borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap',
              border: `1px ${partial ? 'dashed' : 'solid'} ${active ? k.orange : k.border}`,
              background: active ? tint(k.orange, 10) : k.bg,
              color: active ? k.orange : k.text, transition: 'all .13s ease',
            }}>
            {b.label}
            <span style={{ fontSize: 10, marginLeft: 5, fontWeight: 600, color: active ? k.orange : k.dim }}>{b.sub}</span>
          </button>
        );
      })}
    </div>
  );
}

// Pill toggle for the granular universe pickers (multi-select chips).
function Chip({ label, active, onClick, dim }: { label: string; active: boolean; onClick: () => void; dim?: boolean }) {
  return (
    <button onClick={onClick} aria-pressed={active} title={dim ? 'Turn off “All F&O” to pick individual stocks' : label}
      style={{
        fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '3px 9px', borderRadius: 999,
        cursor: dim ? 'default' : 'pointer', whiteSpace: 'nowrap', transition: 'all .14s ease',
        border: `1px solid ${active ? k.orange : k.border}`,
        background: active ? tint(k.orange, 12) : k.bg,
        color: active ? k.orange : (dim ? k.dim : k.text), opacity: dim ? 0.5 : 1,
      }}>
      {label}
    </button>
  );
}

// Custom-stock autocomplete. Suggestions are drawn ONLY from the F&O stock
// registry (the liquid, tradable F&O universe) — never arbitrary symbols — so a
// user can't add an illiquid or non-F&O name. Matches are ranked by liquidity
// (most tradable first) then alphabetically, and already-selected names hidden.
const LIQUIDITY_RANK: Record<string, number> = {
  'Very High': 0, 'High': 1, 'Good': 2, 'Moderate-Good': 3, 'Moderate': 4,
};
const LIQUIDITY_COLOR: Record<string, string> = {
  'Very High': k.green, 'High': k.green, 'Good': k.blue,
  'Moderate-Good': k.amber, 'Moderate': k.dim,
};

function CustomStockSearch({ stockReg, selected, onAdd }: {
  stockReg?: LiquidityGroup[];
  selected: string[];
  onAdd: (name: string) => void;
}) {
  const [query, setQuery] = React.useState('');
  const [open, setOpen] = React.useState(false);
  const [activeIdx, setActiveIdx] = React.useState(0);

  // Flatten the registry once into a de-duplicated, liquidity-ranked list.
  const universe = React.useMemo(() => {
    const seen = new Set<string>();
    const out: StockEntry[] = [];
    for (const g of stockReg ?? []) {
      for (const s of g.stocks) {
        if (seen.has(s.name)) continue;
        seen.add(s.name);
        out.push(s);
      }
    }
    out.sort((a, b) =>
      (LIQUIDITY_RANK[a.liquidity] ?? 9) - (LIQUIDITY_RANK[b.liquidity] ?? 9)
      || a.name.localeCompare(b.name));
    return out;
  }, [stockReg]);

  const matches = React.useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return [];
    return universe
      .filter((s) => !selected.includes(s.name)
        && (s.name.toUpperCase().includes(q) || (s.label || '').toUpperCase().includes(q)))
      .slice(0, 8);
  }, [query, universe, selected]);

  React.useEffect(() => { setActiveIdx(0); }, [query]);

  const pick = (s: StockEntry) => {
    onAdd(s.name);
    setQuery('');
    setOpen(false);
  };

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 2, position: 'relative' }}>
      <span style={{ fontSize: 9, fontWeight: 600, color: k.dim, letterSpacing: 0.3, minWidth: 52, paddingTop: 4 }}>CUSTOM</span>
      <div style={{ position: 'relative', flex: 1, minWidth: 0 }}>
        <input
          style={{ width: '100%', boxSizing: 'border-box', fontSize: 9.5, padding: '3px 6px', background: k.surface, border: `1px solid ${open && matches.length ? k.orange : k.border}`, borderRadius: 4, color: k.text, outline: 'none' }}
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search F&O stock…"
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, matches.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)); }
            else if (e.key === 'Enter' && matches[activeIdx]) { e.preventDefault(); pick(matches[activeIdx]); }
            else if (e.key === 'Escape') { setOpen(false); }
          }}
        />
        {open && query.trim() && (
          <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 50, marginTop: 2, background: k.bg, border: `1px solid ${k.border}`, borderRadius: 6, boxShadow: '0 6px 18px rgba(0,0,0,0.12)', overflow: 'hidden' }}>
            {matches.length === 0 ? (
              <div style={{ padding: '7px 10px', fontSize: 10, color: k.dim }}>No matching F&amp;O stock.</div>
            ) : matches.map((s, i) => (
              <div
                key={s.name}
                onMouseDown={(e) => { e.preventDefault(); pick(s); }}
                onMouseEnter={() => setActiveIdx(i)}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '6px 10px', cursor: 'pointer', background: i === activeIdx ? k.surfaceHover : 'transparent' }}
              >
                <span style={{ fontSize: 11, fontWeight: 600, color: k.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {s.name}
                  {s.label && s.label !== s.name && <span style={{ fontSize: 9.5, fontWeight: 400, color: k.dim, marginLeft: 5 }}>{s.label}</span>}
                </span>
                <span style={{ flexShrink: 0, fontSize: 8.5, fontWeight: 700, letterSpacing: 0.3, color: LIQUIDITY_COLOR[s.liquidity] ?? k.dim, border: `1px solid ${tint(LIQUIDITY_COLOR[s.liquidity] ?? k.dim, 40)}`, borderRadius: 3, padding: '1px 4px', textTransform: 'uppercase' }}>
                  {s.liquidity}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Settings-drawer layout primitives ──────────────────────────────────────
// A consistent setting row: tiny caps label inline-left, control to the right.
// Each row carries its own padding + bottom border for a clean list-of-settings look.
function SettingRow({ label, hint, children, align = 'center', full = false }: {
  label: string; hint?: string; children: React.ReactNode;
  align?: 'center' | 'top'; full?: boolean;
}) {
  return (
    <div style={{ display: 'flex', alignItems: align === 'top' ? 'flex-start' : 'center', gap: 10, padding: '13px 16px', borderBottom: `1px solid ${k.border}` }}>
      <span title={hint} style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', color: k.dim, width: 62, flexShrink: 0, lineHeight: 1.4, paddingTop: align === 'top' ? 2 : 0 }}>{label}</span>
      <div style={{ flex: full ? 1 : undefined, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 7 }}>{children}</div>
    </div>
  );
}

// Tab bar for the 'tabs' layout.
// Polished pill-style tab bar for the settings drawer. The active pill gets a
// solid surface lift + orange label; inactive ones are quiet until hovered.
function PillTabs({ active, onSelect, tabs }: {
  active: string; onSelect: (v: string) => void; tabs: { value: string; label: string; icon?: React.ReactNode }[];
}) {
  return (
    <div style={{ display: 'inline-flex', gap: 2, padding: 3, borderRadius: 8, background: k.bg, border: `1px solid ${k.border}` }}>
      {tabs.map((t) => {
        const on = active === t.value;
        return (
          <button key={t.value} onClick={() => onSelect(t.value)} aria-pressed={on}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 5,
              fontSize: 11, fontWeight: on ? 700 : 600, letterSpacing: 0.2,
              padding: '5px 13px', cursor: 'pointer', border: 'none', borderRadius: 6,
              background: on ? k.surface : 'transparent',
              color: on ? k.orange : k.dim,
              boxShadow: on ? '0 1px 2px rgba(0,0,0,.06)' : 'none',
              transition: 'color .15s ease, background .15s ease',
            }}
            onMouseEnter={(e) => { if (!on) e.currentTarget.style.color = k.text; }}
            onMouseLeave={(e) => { if (!on) e.currentTarget.style.color = k.dim; }}>
            {t.icon}{t.label}
          </button>
        );
      })}
    </div>
  );
}

// Collapsible labeled card for the 'cards' layout.
function Collapsible({ label, summary, open, onToggle, children }: {
  label: string; summary?: string; open: boolean; onToggle: () => void; children: React.ReactNode;
}) {
  return (
    <div style={{ border: `1px solid ${k.border}`, borderRadius: 7, overflow: 'hidden', background: k.bg }}>
      <button onClick={onToggle} aria-expanded={open}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
          padding: '8px 11px', cursor: 'pointer', border: 'none', background: open ? k.surfaceHover : k.surface,
          textAlign: 'left', transition: 'background .15s ease',
        }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', color: k.text }}>{label}</span>
          {!open && summary && <span style={{ fontSize: 10, color: k.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{summary}</span>}
        </span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)', transition: 'transform .2s ease', color: k.dim, flexShrink: 0 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && <div style={{ padding: '11px 12px 13px', borderTop: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 11 }}>{children}</div>}
    </div>
  );
}

function EndedToggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 10, color: k.dim }}>Ended</span>
      <button onClick={onChange}
        style={{
          position: 'relative', width: 28, height: 16, borderRadius: 999, border: 'none', padding: 0,
          cursor: 'pointer', flexShrink: 0, background: on ? k.amber : k.border, transition: 'background .18s ease',
        }}>
        <span style={{
          position: 'absolute', top: 1, left: on ? 13 : 1, width: 14, height: 14, borderRadius: '50%',
          background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,.25)', transition: 'left .18s ease',
        }} />
      </button>
    </div>
  );
}

// Thin progress bar that ticks independently so the rest of the pane doesn't re-render every second.
function ScanProgressBar({ signals }: { signals?: SignalsResponse }) {
  const [, tick] = React.useReducer((x) => x + 1, 0);
  React.useEffect(() => { const id = setInterval(tick, 1000); return () => clearInterval(id); }, []);

  const scanning = signals?.scanning ?? false;
  const auto = signals?.auto_scan ?? false;
  const gen = signals?.generated_ms ?? 0;
  const next = signals?.next_scan_ms ?? 0;
  const interval = next - gen;
  const frac = interval > 0 ? Math.min(1, Math.max(0, (Date.now() - gen) / interval)) : 0;
  // Market closed → the loop is paused and next_scan_ms is stale, so the
  // countdown bar would falsely sit full. Don't show it then.
  const counting = auto && interval > 0 && signals?.market_open !== false;

  return (
    <div style={{ height: 2, background: k.border, position: 'relative', overflow: 'hidden' }}>
      {scanning
          ? <div className="st-scan-bar" />
          : counting
            ? <div key={gen} style={{ height: '100%', width: `${frac * 100}%`, background: k.orange, transition: 'width 1s linear' }} />
            : null}
    </div>
  );
}

// ─── Scan Report View ─────────────────────────────────────────────────────
type ReportSortKey = 'symbol' | 'strike' | 'type' | 'expiry' | 'bars' | 'premium' | 'status' | 'reason';

function ScanReportView({ data }: { data?: ScanReportResponse }) {
  const [sortKey, setSortKey] = React.useState<ReportSortKey>('strike');
  const [sortDir, setSortDir] = React.useState<'asc'|'desc'>('asc');
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());

  // Grouped by underlying — MUST be before early return (hook count consistency)
  const grouped = React.useMemo(() => {
    if (!data || !data.entries.length) return [];
    const map = new Map<string, ContractScanEntry[]>();
    for (const e of data.entries) {
      const arr = map.get(e.underlying) || [];
      arr.push(e);
      map.set(e.underlying, arr);
    }
    const out: { symbol: string; entries: ContractScanEntry[]; firedCount: number }[] = [];
    for (const [symbol, entries] of map) {
      const firedCount = entries.filter(e => e.fired).length;
      const sorted = [...entries].sort((a, b) => {
        let va: any, vb: any;
        switch (sortKey) {
          case 'symbol': va = a.underlying + a.moneyness; vb = b.underlying + b.moneyness; break;
          case 'strike': va = a.strike; vb = b.strike; break;
          case 'type': va = a.option_type; vb = b.option_type; break;
          case 'expiry': va = a.expiry; vb = b.expiry; break;
          case 'bars': va = a.bars; vb = b.bars; break;
          case 'premium': va = a.premium_close; vb = b.premium_close; break;
          case 'status': va = a.fired ? 1 : 0; vb = b.fired ? 1 : 0; break;
          case 'reason': va = a.reason; vb = b.reason; break;
          default: return 0;
        }
        if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        return sortDir === 'asc' ? va - vb : vb - va;
      });
      out.push({ symbol, entries: sorted, firedCount });
    }
    out.sort((a, b) => a.symbol.localeCompare(b.symbol));
    return out;
  }, [data, sortKey, sortDir]);

  const handleSort = (key: ReportSortKey) => {
    if (sortKey === key) { setSortDir(d => d === 'asc' ? 'desc' : 'asc'); }
    else { setSortKey(key); setSortDir('asc'); }
  };

  if (!data || !data.entries.length) {
    return (
      <div style={{ padding: '16px 20px', fontSize: 11, color: k.dim, borderBottom: `1px solid ${k.border}` }}>
        No scan report available — run a scan first.
      </div>
    );
  }
  const s = data.summary;
  const fmtPx = (v: number) => v > 0 ? v.toFixed(1) : '—';

  const toggleGroup = (sym: string) => setCollapsed(prev => { const n = new Set(prev); n.has(sym) ? n.delete(sym) : n.add(sym); return n; });

  return (
    <div style={{ borderBottom: `1px solid ${k.border}`, maxHeight: 420, overflow: 'auto' }}>
      {/* Summary bar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', padding: '10px 16px', fontSize: 10.5, color: k.dim, background: k.surfaceHover }}>
        <span>CE <b style={{ color: k.green }}>{s.fired_ce}</b>/<span style={{ color: k.text }}>{s.total_ce}</span></span>
        <span>PE <b style={{ color: k.red }}>{s.fired_pe}</b>/<span style={{ color: k.text }}>{s.total_pe}</span></span>
        <span>charted <b style={{ color: k.text }}>{s.charted}</b></span>
        <span>no-data <b style={{ color: k.amber }}>{s.no_data}</b></span>
        <span>bars <b style={{ color: k.text }}>{s.min_bars}–{s.max_bars}</b></span>
        <span style={{ marginLeft: 'auto', color: k.dim }}>{new Date(s.generated_ms).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
      </div>

      {/* Table header — sticky */}
      <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: 10.5 }}>
        <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
          <tr style={{ color: k.dim, fontSize: 9, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            {([
              ['Symbol', 'symbol'], ['Strike', 'strike'], ['Type', 'type'], ['Expiry', 'expiry'],
              ['Bars', 'bars'], ['Premium', 'premium'], ['Status', 'status'], ['Reason', 'reason'],
            ] as [string, ReportSortKey][]).map(([label, key]) => (
              <th key={key} style={{ padding: '6px 10px', textAlign: key === 'symbol' || key === 'type' ? 'left' : key === 'reason' ? 'left' : 'right', borderBottom: `1px solid ${k.border}`, background: k.bg, whiteSpace: 'nowrap' }}>
                <SortHeaderDiv label={label} sortKey={key} sort={{ key: sortKey, dir: sortDir }} handleSort={handleSort} align={key === 'symbol' || key === 'type' || key === 'reason' ? 'left' : 'right'} />
              </th>
            ))}
          </tr>
        </thead>
      </table>

      {/* Grouped rows */}
      {grouped.map(g => {
        const isCollapsed = collapsed.has(g.symbol);
        const dot = g.firedCount > 0 ? 'var(--t-green)' : 'var(--t-dim)';
        return (
          <div key={g.symbol}>
            <div onClick={() => toggleGroup(g.symbol)}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 16px', background: k.surfaceHover, borderBottom: `1px solid ${k.border}`, cursor: 'pointer', userSelect: 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, color: k.text }}>
                <span style={{ width: 7, height: 7, borderRadius: 4, background: dot, flexShrink: 0 }} />
                {g.symbol}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 11, color: k.dim }}>{g.entries.length} contracts · {g.firedCount} fired</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease', color: k.dim }}>
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </div>
            </div>
            {!isCollapsed && (
              <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: 10.5 }}>
                <tbody>
                  {g.entries.map((e, i) => {
                    const firedColor = e.fired ? k.green : k.dim;
                    const typeColor = e.option_type === 'CE' ? k.green : k.red;
                    return (
                      <tr key={i} style={{ borderBottom: `1px solid ${k.border}` }}>
                        <td style={{ padding: '5px 10px', color: k.text, fontWeight: 500, whiteSpace: 'nowrap' }}>
                          {e.moneyness}
                        </td>
                        <td style={{ padding: '5px 10px', color: k.text, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{e.strike.toFixed(0)}</td>
                        <td style={{ padding: '5px 10px', fontWeight: 700, color: typeColor }}>{e.option_type}</td>
                        <td style={{ padding: '5px 10px', color: k.dim, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{e.expiry.slice(5)}</td>
                        <td style={{ padding: '5px 10px', textAlign: 'right', color: e.bars > 0 ? k.text : k.dim, fontVariantNumeric: 'tabular-nums' }}>{e.bars || '—'}</td>
                        <td style={{ padding: '5px 10px', textAlign: 'right', color: k.text, fontVariantNumeric: 'tabular-nums' }}>{fmtPx(e.premium_close)}</td>
                        <td style={{ padding: '5px 10px', textAlign: 'right', fontWeight: 700, color: firedColor }}>{e.fired ? 'FIRED' : '—'}</td>
                        <td style={{ padding: '5px 10px', fontSize: 9.5, color: e.fired ? k.green : k.dim, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.reason}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function SterlingKiteEnginePane({ onSelectSignal }: Props) {
  const s = useKiteSettings();
  const { data: signals } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
  const { data: stockReg } = useStockRegistry();
  const setCfg = useSetEngineConfig();
  const scan = useRunScan();
  const cancelScan = useCancelScan();
  const { data: scanReport } = useScanReport();
  const [reportOpen, setReportOpen] = React.useState(false);
  const scanLock = React.useRef(false);
  const doScan = () => {
    if (scanLock.current || scan.isPending) return;
    scanLock.current = true;
    scan.mutate(undefined, { onSettled: () => { scanLock.current = false; } });
  };
  // Kite-only paper/live, scoped to the active Kite account. Independent of the
  // global top-bar PAPER/LIVE toggle, which is crypto (Delta) only.
  const { data: kiteAccts } = useKiteAccounts();
  const updateAcct = useUpdateKiteAccount();
  const activeAcct = kiteAccts?.accounts.find((a) => a.is_active);
  const kiteLive = !!activeAcct && !activeAcct.is_paper;
  const [query, setQuery] = React.useState('');
  const [searchSettingsOpen, setSearchSettingsOpen] = React.useState(false);
  const [sortBy, setSortBy] = React.useState('Custom');
  // Always start collapsed on a fresh load/refresh (not restored from storage).
  const [settingsOpen, setSettingsOpen] = React.useState<boolean>(false);
  const [viewLayout, setViewLayout] = React.useState<'grid' | 'list'>(() => (localStorage.getItem('kite_st_view_layout') as 'grid' | 'list') || 'grid');
  const legSort = s.legSort;
  const setLegSort = s.setLegSort;
  const handleLegSort = (key: string) => {
    setLegSort(legSort.key === key ? { key, dir: legSort.dir === 'asc' ? 'desc' : legSort.dir === 'desc' ? '' : 'asc' } : { key, dir: 'asc' });
  };

  // Settings-drawer layout (chosen on the Connect tab) + per-layout persisted UI state.
  const layout = useKiteSettings((st) => st.engineSettingsLayout);
  const [settingsTab, setSettingsTab] = React.useState<'scan' | 'universe' | 'execution'>(
    () => (localStorage.getItem('kite_settings_tab') as 'scan' | 'universe' | 'execution') || 'scan'
  );
  const [cardOpen, setCardOpen] = React.useState<{ scan: boolean; universe: boolean; execution: boolean }>(() => {
    try {
      const raw = localStorage.getItem('kite_settings_cards');
      if (raw) return { scan: true, universe: false, execution: true, ...JSON.parse(raw) };
    } catch { /* ignore */ }
    return { scan: true, universe: false, execution: true };
  });
  const toggleCard = (key: 'scan' | 'universe' | 'execution') =>
    setCardOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  // Close the settings drawer when clicking outside the drawer or its toggle.
  // The toggle button and the drawer are marked with [data-st-settings]; a click
  // outside any such element collapses the drawer (the toggle still toggles).
  React.useEffect(() => {
    if (!settingsOpen) return;
    const onDown = (e: MouseEvent) => {
      const el = e.target as Element | null;
      if (el && el.closest('[data-st-settings]')) return;
      setSettingsOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [settingsOpen]);
  React.useEffect(() => { localStorage.setItem('kite_st_view_layout', viewLayout); }, [viewLayout]);
  React.useEffect(() => { localStorage.setItem('kite_settings_tab', settingsTab); }, [settingsTab]);
  React.useEffect(() => { localStorage.setItem('kite_settings_cards', JSON.stringify(cardOpen)); }, [cardOpen]);

  const resetCfg = useResetEngineConfig();

  const patch = (p: Partial<EngineConfigModel>, msg?: string) => { 
    if (cfg) {
      setCfg.mutate({ ...cfg, ...p }, {
        onSuccess: () => {
          if (msg) notifyOrder({ kind: 'info', title: 'Settings updated', message: msg });
        }
      });
    }
  };

  const toggleMoneyness = (m: Moneyness) => {
    if (!cfg) return;
    const has = cfg.strike_moneyness.includes(m);
    const next = has ? cfg.strike_moneyness.filter((x) => x !== m) : [...cfg.strike_moneyness, m];
    const finalNext = next.length ? next : ['ATM', 'ITM1', 'ITM2', 'ITM3', 'OTM1', 'OTM2', 'OTM3'];
    patch({ strike_moneyness: finalNext as Moneyness[] }, `Strikes updated to ${finalNext.join(', ')}`);
  };

  // Toggle a whole delta bucket: if every member is already selected, remove them
  // all; otherwise add the missing ones. Never lets the selection go empty.
  const toggleBucket = (members: Moneyness[]) => {
    if (!cfg) return;
    const cur = cfg.strike_moneyness;
    const allIn = members.every((m) => cur.includes(m));
    let next = allIn
      ? cur.filter((m) => !members.includes(m))
      : [...new Set([...cur, ...members])];
    if (!next.length) next = ['ATM'];
    patch({ strike_moneyness: next as Moneyness[] }, `Strikes updated to ${next.join(', ')}`);
  };

  const toggleExpiry = (e: ScanExpiry) => {
    if (!cfg) return;
    const has = cfg.scan_expiries.includes(e);
    const next = has ? cfg.scan_expiries.filter((x) => x !== e) : [...cfg.scan_expiries, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries: finalNext as ScanExpiry[] }, `Expiries updated to ${finalNext.join(', ')}`);
  };

  const toggleExpiryIndices = (e: ScanExpiry) => {
    if (!cfg) return;
    const cur = cfg.scan_expiries_indices ?? cfg.scan_expiries;
    const has = cur.includes(e);
    const next = has ? cur.filter((x) => x !== e) : [...cur, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries_indices: finalNext as ScanExpiry[] }, `Indices expiries updated to ${finalNext.join(', ')}`);
  };

  const toggleExpiryStocks = (e: ScanExpiry) => {
    if (!cfg) return;
    const cur = cfg.scan_expiries_stocks ?? ['monthly'];
    const has = cur.includes(e);
    const next = has ? cur.filter((x) => x !== e) : [...cur, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries_stocks: finalNext as ScanExpiry[] }, `Stocks expiries updated to ${finalNext.join(', ')}`);
  };

  // Changing the scan source must re-scan immediately — otherwise the list keeps
  // showing the previous scan's rows (e.g. spot signals) until the 5-min auto-loop
  // runs, which reads as "I switched to derivatives but nothing changed".
  const changeScanSource = (v: ScanSource) => {
    if (!cfg || cfg.scan_source === v) return;
    setCfg.mutate({ ...cfg, scan_source: v }, { 
      onSuccess: () => { 
        notifyOrder({ kind: 'info', title: 'Settings updated', message: `Scan source changed to ${v}` });
        doScan(); 
      } 
    });
  };

  const toggleIndex = (name: string) => {
    if (!cfg) return;
    const has = cfg.scan_indices.includes(name);
    const next = has ? cfg.scan_indices.filter((x) => x !== name) : [...cfg.scan_indices, name];
    patch({ scan_indices: next }, `Indices updated: ${has ? `Removed ${name}` : `Added ${name}`}`);
  };

  const toggleStock = (name: string) => {
    if (!cfg) return;
    const has = cfg.scan_stocks.includes(name);
    const next = has ? cfg.scan_stocks.filter((x) => x !== name) : [...cfg.scan_stocks, name];
    patch({ scan_stocks: next }, `Stocks updated: ${has ? `Removed ${name}` : `Added ${name}`}`);
  };

  const addCustomStock = (name: string) => {
    if (!cfg || !name.trim()) return;
    const upper = name.trim().toUpperCase();
    if (cfg.scan_stocks.includes(upper)) return;
    patch({ scan_stocks: [...cfg.scan_stocks, upper] }, `Added ${upper} to scan`);
  };

  const removeCustomStock = (name: string) => {
    if (!cfg) return;
    patch({ scan_stocks: cfg.scan_stocks.filter(x => x !== name) }, `Removed ${name} from scan`);
  };

  const toggleAuto = () => {
    if (!cfg) return;
    patch({ auto_execute: !cfg.auto_execute }, `Auto-execute turned ${!cfg.auto_execute ? 'ON' : 'OFF'}`);
  };

  // Kite paper↔live. Arming (→LIVE) confirms — it routes real orders to Zerodha;
  // de-arming (→PAPER) is immediate. Crypto/Delta is untouched (separate toggle).
  const toggleKiteLive = () => {
    if (!activeAcct) {
      notifyOrder({ kind: 'rejected', title: 'Action blocked', message: 'No active Kite account. Add one on the Connect page first.' });
      return;
    }
    if (activeAcct.is_paper) {
      if (!activeAcct.has_credentials) {
        notifyOrder({ kind: 'rejected', title: 'Action blocked', message: 'Add your Kite API key & secret on the Connect page before trading live.' });
        return;
      }
      updateAcct.mutate({ id: activeAcct.id, is_paper: false }, {
        onSuccess: () => notifyOrder({ kind: 'info', title: 'Trading mode updated', message: 'Kite is now LIVE' })
      });
    } else {
      updateAcct.mutate({ id: activeAcct.id, is_paper: true }, {
        onSuccess: () => notifyOrder({ kind: 'info', title: 'Trading mode updated', message: 'Kite is now PAPER' })
      });
    }
  };

  // While a scan is in progress the backend flushes results progressively, so a
  // raw poll can momentarily return fewer rows than before — making rows blink out
  // and reappear. To keep the table stable, we remember the last completed-scan row
  // set and, during scanning, MERGE it with the freshly-arriving rows (fresh wins on
  // key collision). Rows therefore only get added/updated mid-scan, never vanish.
  // When the scan finishes, the fresh set becomes the new baseline.
  const rowKey = (r: EngineSignalRow) => `${r.token}:${r.option_type}:${r.timestamp_ms}`;
  const lastStableRows = React.useRef<EngineSignalRow[]>([]);
  const rawRows = signals?.rows ?? [];
  const isScanning = signals?.scanning ?? false;
  const rows = React.useMemo(() => {
    if (!isScanning) {
      lastStableRows.current = rawRows;
      return rawRows;
    }
    const merged = new Map<string, EngineSignalRow>();
    for (const r of lastStableRows.current) merged.set(rowKey(r), r);
    for (const r of rawRows) merged.set(rowKey(r), r); // fresh overrides stale
    return Array.from(merged.values());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawRows, isScanning]);
  const filteredRows = React.useMemo(() => {
    let result = [...rows];
    if (query.trim()) {
      const qLower = query.toLowerCase();
      result = result.filter(r => {
        if (r.underlying.toLowerCase().includes(qLower)) return true;
        if (r.exchange.toLowerCase().includes(qLower)) return true;
        if (r.legs.some(l => l.option_symbol.toLowerCase().includes(qLower))) return true;
        return false;
      });
    }
    if (sortBy === 'A-Z') {
      result.sort((a, b) => a.underlying.localeCompare(b.underlying));
    } else if (sortBy === 'EXCH') {
      result.sort((a, b) => a.exchange.localeCompare(b.exchange));
    } else if (sortBy === 'LTP') {
      result.sort((a, b) => b.spot - a.spot);
    }
    return result;
  }, [rows, query, sortBy]);

  // Live quotes are needed BEFORE bucketing so a position that has exited between scans
  // (live premium through its stop) drops out of "Active now" instead of lingering there
  // showing a "trend ended" badge — the same reconciliation the cards use.
  const optionSymbols = React.useMemo(() => {
    const syms = new Set<string>();
    filteredRows.forEach((r) => {
      const exch = (r.underlying === 'SENSEX' || r.underlying === 'BANKEX') ? 'BSE' : 'NSE';
      let sym = r.underlying;
      if (sym === 'NIFTY') sym = 'NIFTY 50';
      if (sym === 'BANKNIFTY') sym = 'NIFTY BANK';
      if (sym === 'FINNIFTY') sym = 'NIFTY FIN SERVICE';
      if (sym === 'MIDCPNIFTY') sym = 'NIFTY MID SELECT';
      syms.add(`${exch}:${sym}`);

      r.legs.forEach((l) => syms.add(`${r.exchange}:${l.option_symbol}`));
    });
    return Array.from(syms);
  }, [filteredRows]);

  const { data: quotes } = useKiteQuote(optionSymbols, optionSymbols.length > 0);

  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(new Set());
  const [showEnded, setShowEnded] = React.useState<boolean>(() => localStorage.getItem('kite_st_show_ended') !== 'false');
  const toggleGroup = (label: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const groupedRows = React.useMemo(() => {
    const buckets: { label: string; rows: typeof filteredRows; active?: boolean }[] = [];
    const sorted = [...filteredRows].sort((a, b) => b.timestamp_ms - a.timestamp_ms);

    // Currently-running trades (SuperTrend still aligned on the latest bar) surface at
    // the TOP regardless of when they entered. Otherwise a live trade that entered a few
    // days ago hides under "Last week" and the list reads empty even though there's an
    // active signal. The date buckets below are the history log of entries whose trend
    // has since ended.
    const active = sorted.filter((r) => rowIsRunning(r, quotes));
    const history = sorted.filter((r) => !rowIsRunning(r, quotes));
    // Indices first in "Active now", then stocks alphabetically.
    const INDEX_NAMES = new Set(INDEX_OPTS.map(o => o.name));
    const sortedActive = [...active].sort((a, b) => {
      const aIdx = INDEX_NAMES.has(a.underlying) ? 1 : 0;
      const bIdx = INDEX_NAMES.has(b.underlying) ? 1 : 0;
      if (aIdx !== bIdx) return bIdx - aIdx; // indices first
      return a.underlying.localeCompare(b.underlying);
    });
    if (active.length) buckets.push({ label: 'Active now', rows: sortedActive, active: true });

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const groups: Record<string, typeof filteredRows> = {
      "Today": [], "Yesterday": [], "Last week": [], "Last 15 days": [],
    };
    for (const r of history) {
      const d = new Date(r.timestamp_ms);
      const startOfDay = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      const diffDays = Math.round((todayStart - startOfDay) / (1000 * 60 * 60 * 24));
      let label = "";
      if (diffDays === 0) label = "Today";
      else if (diffDays === 1) label = "Yesterday";
      else if (diffDays >= 2 && diffDays <= 7) label = "Last week";
      else if (diffDays >= 8 && diffDays <= 15) label = "Last 15 days";
      else continue;
      groups[label].push(r);
    }
    for (const label of ["Today", "Yesterday", "Last week", "Last 15 days"]) {
      if (groups[label].length) buckets.push({ label: `${label} (ended)`, rows: groups[label] });
    }
    if (!showEnded) return buckets.filter(b => b.active);
    return buckets;
  }, [filteredRows, showEnded, quotes]);
  const scanning = signals?.scanning;

  // Ended groups stay expanded by default so past rows are visible (light amber bg).
  // The user can collapse them manually.

  // ── Engine master gate ──────────────────────────────────────────────────────
  if (cfg && !cfg.engine_enabled) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0,
                    background: k.bg, fontFamily: k.fontFamily }}>
        {/* minimal header — same chrome as the live pane */}
        <div style={{ padding: '12px 16px 8px', borderBottom: `1px solid ${k.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <EngineMark />
            <span style={{ fontSize: 14, color: k.text }}>Sterling Kite Engine</span>
            <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: 0.4, color: k.dim,
                           border: `1px solid ${k.border}`, borderRadius: 4, padding: '1px 5px' }}>1H</span>
          </div>
        </div>
        {/* off-state body */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
                      justifyContent: 'center', gap: 20, padding: 32 }}>
          <div style={{ width: 52, height: 52, borderRadius: 26, background: k.border,
                        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={k.dim}
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="4.93" y1="4.93" x2="19.07" y2="19.07" />
            </svg>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: k.text, marginBottom: 6 }}>
              Engine is off
            </div>
            <div style={{ fontSize: 12, color: k.dim, lineHeight: 1.6, maxWidth: 260 }}>
              The Sterling Kite Engine strategy is disabled. Kite runs in normal mode
              — manual trading, market watch, and existing flows are unaffected.
            </div>
          </div>
          <button
            onClick={() => patch({ engine_enabled: true }, 'Sterling Kite Engine enabled')}
            disabled={setCfg.isPending}
            style={{ padding: '10px 28px', borderRadius: 8, border: 'none', cursor: 'pointer',
                     background: k.green, color: '#fff', fontSize: 13, fontWeight: 700,
                     opacity: setCfg.isPending ? 0.6 : 1, transition: 'opacity 0.15s' }}>
            Enable Engine
          </button>
          <div style={{ fontSize: 11, color: k.dim, textAlign: 'center', maxWidth: 240 }}>
            Scanning, signals, and auto-execute are gated behind this toggle.
            You can disable it again from the settings header at any time.
          </div>
        </div>
      </div>
    );
  }

  const liveCount = rows.filter((r) => rowIsRunning(r, quotes)).length;

  // Publish the running count to the Kite footer (rendered in a different tree).
  const setLiveCount = useLiveSignalCount((s) => s.setCount);
  React.useEffect(() => { setLiveCount(liveCount); }, [liveCount, setLiveCount]);
  React.useEffect(() => () => setLiveCount(0), [setLiveCount]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, background: k.bg, fontFamily: k.fontFamily }}>
      {/* ── Compact two-row header ── */}
      <div style={{ borderBottom: `1px solid ${k.border}`, flexShrink: 0 }}>
        {/* Row 1: identity + live count + settings */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px 6px' }}>
          <EngineMark />
          <span title={UNIVERSE_TIP} style={{ fontSize: 13.5, color: k.text, whiteSpace: 'nowrap', letterSpacing: -0.2 }}>
            Sterling Kite Engine
          </span>
          <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.5, color: k.dim, border: `1px solid ${k.border}`, borderRadius: 3, padding: '1px 4px', flexShrink: 0 }}>1H</span>
          {cfg && (
            <span title="Current auto-exit rule (counter to the 3-green entry)" style={{ fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 999, background: tint(k.blue, 8), color: k.blue }}>
              {EXIT_MODE_OPTS.find(o => o.value === (cfg.exit_mode ?? 'one_red'))?.short ?? '1R'} EXIT
            </span>
          )}
          {/* Scan status + live count now live in the Kite footer (see KiteLayout). */}
          <div style={{ flex: 1 }} />
          {/* Actions: rescan / scan report / grid·list */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            {scanning ? (
              <HeaderIconBtn title="Stop scan" onClick={() => cancelScan.mutate()} disabled={cancelScan.isPending}>
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
              </HeaderIconBtn>
            ) : (
              <HeaderIconBtn title="Re-scan now" disabled={scan.isPending} onClick={() => doScan()}>
                <RefreshIcon spinning={scan.isPending} />
              </HeaderIconBtn>
            )}
            <HeaderIconBtn title="Scan report" active={reportOpen} onClick={() => setReportOpen((v) => !v)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
            </HeaderIconBtn>
            {/* Grid / List toggle as a single compact segmented control */}
            <div style={{ display: 'inline-flex', border: `1px solid ${k.border}`, borderRadius: 6, overflow: 'hidden', background: k.bg, marginLeft: 2 }}>
              <button title="Grid layout" aria-pressed={viewLayout === 'grid'} onClick={() => setViewLayout('grid')}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, border: 'none', cursor: 'pointer', background: viewLayout === 'grid' ? tint(k.orange, 15) : 'transparent', color: viewLayout === 'grid' ? k.orange : k.dim, transition: 'all .15s' }}>
                <GridIcon />
              </button>
              <button title="List layout" aria-pressed={viewLayout === 'list'} onClick={() => setViewLayout('list')}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 26, height: 26, border: 'none', borderLeft: `1px solid ${k.border}`, cursor: 'pointer', background: viewLayout === 'list' ? tint(k.orange, 15) : 'transparent', color: viewLayout === 'list' ? k.orange : k.dim, transition: 'all .15s' }}>
                <ListIcon />
              </button>
            </div>
          </div>
          <span data-st-settings style={{ display: 'inline-flex' }}>
            <HeaderIconBtn title="Engine settings" active={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}>
              <Icons.Settings />
            </HeaderIconBtn>
          </span>
        </div>

        {/* Progress bar — scan countdown */}
        <ScanProgressBar signals={signals} />
      </div>

      {/* ── Scan report drawer ── */}
      <div className="st-drawer" style={{ display: 'grid', gridTemplateRows: reportOpen ? '1fr' : '0fr' }}>
        <div style={{ overflow: 'hidden' }}>
          <ScanReportView data={scanReport} />
        </div>
      </div>

      {rows.length > 0 && !settingsOpen && (
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: k.bg }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 16px', borderBottom: `1px solid ${k.border}` }}>
            <div style={{ flex: 1 }}>
              <KiteSearchBar
                query={query}
                setQuery={setQuery}
                searchSettingsOpen={searchSettingsOpen}
                setSearchSettingsOpen={setSearchSettingsOpen}
                height={35}
              />
            </div>
            <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
              <EndedToggle on={showEnded} onChange={() => { setShowEnded(v => { const n = !v; localStorage.setItem('kite_st_show_ended', String(n)); return n; }); }} />
            </div>
          </div>
          {viewLayout === 'list' && (
            <div style={{ 
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 32,
              padding: '12px 16px', fontSize: 12, fontWeight: 400, color: k.dim, borderBottom: `1px solid ${k.border}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0, paddingRight: 8, flex: 1 }}>
                 <SortHeaderDiv label="Instrument" sortKey="instrument" sort={legSort} handleSort={handleLegSort} style={{ flex: 1 }} />
                 {s.showExchange && <SortHeaderDiv label="Exc." sortKey="exc" sort={legSort} handleSort={handleLegSort} style={{ width: 40, flexShrink: 0 }} />}
                 {s.showLeg && <SortHeaderDiv label="Leg (Δ)" sortKey="leg" sort={legSort} handleSort={handleLegSort} style={{ width: 78, flexShrink: 0 }} />}
                 {cfg?.scan_source !== 'spot' && <SortHeaderDiv label="Entry (Δpts)" sortKey="entry" sort={legSort} handleSort={handleLegSort} style={{ width: 110, flexShrink: 0 }} align="right" />}
                 {cfg?.scan_source !== 'spot' && <SortHeaderDiv label="Stop" sortKey="stop" sort={legSort} handleSort={handleLegSort} style={{ width: 70, flexShrink: 0 }} align="right" />}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 16 }}>
                 <div style={{ width: 150 }}></div>
                 <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                   {s.showPriceChange && <SortHeaderDiv label="Chg." sortKey="chg" sort={legSort} handleSort={handleLegSort} style={{ width: 50 }} align="right" />}
                   {s.showPriceChangePct && <SortHeaderDiv label="Chg. %" sortKey="chgPct" sort={legSort} handleSort={handleLegSort} style={{ width: 60 }} align="right" />}
                   {s.showPriceDirection && <span style={{ width: 14 }}></span>}
                   <SortHeaderDiv label="LTP" sortKey="ltp" sort={legSort} handleSort={handleLegSort} style={{ width: 70 }} align="right" />
                 </div>
                 <div style={{ width: 28 }}></div>
              </div>
            </div>
          )}
        </div>
      )}
      <style>{`
        .st-parent-row {
          position: relative;
        }

        .st-leg-row {
          position: relative;
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 32px;
          height: 41px;
          padding: 0 16px;
          box-sizing: border-box;
          border-bottom: 1px solid ${k.border};
        }
        .st-leg-row:hover { background-color: ${k.surfaceHover} !important; }
        .sort-header-div:hover { color: #444 !important; }
        .sort-icon { opacity: 0; color: #9b9b9b; display: flex; flex-direction: column; gap: 2px; align-items: center; transition: opacity 0.2s; }
        .sort-header-div:hover .sort-icon { opacity: 0.5; }
        .sort-icon.active { opacity: 1 !important; color: #444; }
        .st-actions-persistent {
          display: flex;
          gap: 8px;
          align-items: center;
        }
        .st-actions-more-persistent {
          display: flex;
          align-items: center;
        }
        .st-prices {
          display: flex;
          align-items: center;
          gap: 2px;
          flex-shrink: 0;
          justify-content: flex-end;
        }
        .st-spin { animation: st-spin .8s linear infinite; transform-origin: 50% 50%; }
        @keyframes st-spin { to { transform: rotate(360deg); } }
        .st-pulse { animation: st-pulse 1.5s ease-in-out infinite; }
        @keyframes st-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
        .st-scan-bar { position: absolute; top: 0; left: 0; height: 100%; width: 35%; background: linear-gradient(90deg, transparent, ${k.orange}, transparent); animation: st-scan 1.1s ease-in-out infinite; }
        @keyframes st-scan { 0% { transform: translateX(-120%); } 100% { transform: translateX(360%); } }
        .st-drawer { transition: grid-template-rows .22s ease; }
        @media (prefers-reduced-motion: reduce) {
          .st-spin, .st-pulse, .st-scan-bar, .st-drawer { animation: none !important; transition: none !important; }
        }
      `}</style>


      {/* ── Settings drawer (collapsible) ── */}
      {(() => {
        if (!cfg) {
          return (
            <div className="st-drawer" style={{ display: 'grid', gridTemplateRows: settingsOpen ? '1fr' : '0fr' }}>
              <div style={{ overflow: 'hidden' }} />
            </div>
          );
        }

        // ── Group bodies (same controls, reused across both layouts) ──────────
        const scanGroup = (
          <>
            <SettingRow label="Source" hint="Spot: SuperTrend on underlying chart. Derivatives: on each contract's premium chart. Both: run both.">
              <Segmented
                options={SCAN_SOURCE_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => cfg.scan_source === v}
                onSelect={(v) => changeScanSource(v as ScanSource)}
              />
            </SettingRow>
            <SettingRow label="Strikes" align="top" full hint="VIEW filter — which strikes appear as rows in the signal table. Does not affect what auto-execute buys.">
              <StrikeBuckets selected={cfg.strike_moneyness} onToggle={toggleBucket} />
              <details>
                <summary style={{ fontSize: 9.5, color: k.dim, cursor: 'pointer', userSelect: 'none', marginTop: 3 }}>Fine-tune individual strikes</summary>
                <div style={{ marginTop: 6 }}>
                  <Segmented
                    options={MONEY_OPTS.map((o) => ({ value: o.value, label: o.value, hint: o.hint }))}
                    isActive={(v) => cfg.strike_moneyness.includes(v as Moneyness)}
                    onSelect={(v) => toggleMoneyness(v as Moneyness)}
                  />
                </div>
              </details>
            </SettingRow>
            <SettingRow label="Idx exp." hint="Index option expiries to scan.">
              <Segmented
                options={EXPIRY_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.scan_expiries_indices ?? cfg.scan_expiries ?? ['weekly', 'monthly']).includes(v as ScanExpiry)}
                onSelect={(v) => toggleExpiryIndices(v as ScanExpiry)}
              />
            </SettingRow>
            <SettingRow label="Stk exp." hint="Stock option expiries — stocks default to monthly only.">
              <Segmented
                options={EXPIRY_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.scan_expiries_stocks ?? ['monthly']).includes(v as ScanExpiry)}
                onSelect={(v) => toggleExpiryStocks(v as ScanExpiry)}
              />
            </SettingRow>
            <div style={{ padding: '11px 16px', fontSize: 10, color: k.dim, display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ opacity: 0.6 }}>ℹ</span> {scanCost(cfg)}
            </div>
          </>
        );

        const universeGroup = (
          <>
            <SettingRow label="Indices" align="top" full hint="Which indices to scan.">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {INDEX_OPTS.map((o) => (
                  <Chip key={o.name} label={o.label} active={cfg.scan_indices.includes(o.name)} onClick={() => toggleIndex(o.name)} />
                ))}
              </div>
            </SettingRow>
            <SettingRow label="Stocks" align="top" full hint="Pick stocks by liquidity tier, or add any symbol.">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
                {stockReg && stockReg.map((group: LiquidityGroup) => (
                  <div key={group.liquidity}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 9, fontWeight: 600, color: k.dim, letterSpacing: 0.3, minWidth: 52 }}>{group.liquidity.toUpperCase()}</span>
                      <button onClick={() => {
                        const names = group.stocks.map(s => s.name);
                        const allIn = names.every(n => cfg.scan_stocks.includes(n));
                        if (allIn) { patch({ scan_stocks: cfg.scan_stocks.filter(n => !names.includes(n)) }, `Removed ${group.liquidity} stocks`); }
                        else { patch({ scan_stocks: [...new Set([...cfg.scan_stocks, ...names])] }, `Added ${group.liquidity} stocks`); }
                      }} style={{ fontSize: 9, color: k.blue, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                        {group.stocks.every(s => cfg.scan_stocks.includes(s.name)) ? '− all' : '+ all'}
                      </button>
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {group.stocks.map((st: StockEntry) => (
                        <Chip key={st.name} label={st.label || st.name} active={cfg.scan_stocks.includes(st.name)} onClick={() => toggleStock(st.name)} />
                      ))}
                    </div>
                  </div>
                ))}
                <CustomStockSearch stockReg={stockReg} selected={cfg.scan_stocks} onAdd={addCustomStock} />
                {cfg.scan_stocks.filter(n => !stockReg?.some(g => g.stocks.some(s => s.name === n))).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {cfg.scan_stocks.filter(n => !stockReg?.some(g => g.stocks.some(s => s.name === n))).map(n => (
                      <Chip key={n} label={n} active={true} onClick={() => removeCustomStock(n)} />
                    ))}
                  </div>
                )}
              </div>
            </SettingRow>
          </>
        );

        const executionGroup = (
          <>
            <div style={{ padding: '6px 16px 8px', fontSize: 10, color: k.dim, background: tint(k.amber, 3), borderBottom: `1px solid ${k.border}` }}>
              Entry: <b>all 3 green lines + fresh green arrow</b>. Exit counter (your choice): 1/2/3 red lines (or + red arrow). Trail ratchets tighter as lines flip red.
            </div>
            <SettingRow label="Trail" hint="How tightly the position is trailed before exit.">
              <Segmented
                options={TRAIL_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.trail_target ?? 'fast') === v}
                onSelect={(v) => patch({ trail_target: v as TrailTarget }, `Trailing changed to ${v}`)}
              />
            </SettingRow>
            <SettingRow label="Hybrid Weight" hint="Weight for ST vs ATR in hybrid trail (0-1). Only for hybrid mode.">
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={cfg.hybrid_st_weight ?? 0.5}
                onChange={e => patch({ hybrid_st_weight: parseFloat(e.target.value) }, `Hybrid weight → ${e.target.value}`)}
                aria-label="Hybrid Weight"
                data-testid="hybrid-weight-input"
                style={{ width: 80, padding: 4, background: k.surface, color: k.text, border: `1px solid ${k.border}` }}
              />
            </SettingRow>
            <SettingRow label="Exit Counter" hint="Entry = all 3 green lines + fresh green arrow. Choose how many red (counter) lines + optional red arrow trigger auto-exit + ratcheting trail.">
              <Segmented
                options={EXIT_MODE_OPTS.map((o) => ({ value: o.value, label: o.label, hint: `${o.short}: ${o.hint}` }))}
                isActive={(v) => (cfg.exit_mode ?? 'one_red') === v}
                onSelect={(v) => patch({ exit_mode: v as 'one_red'|'two_red'|'three_red'|'three_red_signal' }, `Exit mode → ${EXIT_MODE_OPTS.find(x=>x.value===v)?.short || v}`)}
              />
              <div style={{ fontSize: 10, color: k.dim, marginTop: 4, lineHeight: 1.3 }}>
                {EXIT_MODE_OPTS.find(o => o.value === (cfg.exit_mode ?? 'one_red'))?.hint}
              </div>
            </SettingRow>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', borderBottom: `1px solid ${k.border}`, background: cfg.auto_execute ? tint(k.orange, 5) : 'transparent', cursor: 'pointer', transition: 'background .18s' }}
              onClick={toggleAuto}>
              <Switch on={cfg.auto_execute ?? false} color={k.orange} label="Auto-execute" onChange={() => {}} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: cfg.auto_execute ? k.orange : k.text, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <ZapIcon /> Auto-execute {cfg.auto_execute ? 'ON' : 'OFF'}
                </span>
                <span style={{ fontSize: 10, color: k.dim, display: 'block', marginTop: 1 }}>Places option BUY orders on ready signals (live-safety gated).</span>
              </div>
            </div>
            <SettingRow label="Stop" hint="GTT broker stop survives disconnects; tick monitor exits intrabar. Both = recommended for real money.">
              <Segmented
                options={STOP_MODE_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg.stop_mode ?? 'both') === v}
                onSelect={(v) => patch({ stop_mode: v as 'broker' | 'monitor' | 'both' }, `Stop mode: ${v}`)}
              />
            </SettingRow>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', borderBottom: `1px solid ${k.border}`, cursor: 'pointer' }}
              onClick={() => patch({ risk_sizing: !(cfg.risk_sizing ?? true) }, `Risk sizing ${!(cfg.risk_sizing ?? true) ? 'ON' : 'OFF'}`)}>
              <Switch on={cfg.risk_sizing ?? true} color={k.blue} label="Risk-based sizing" onChange={() => {}} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11, color: k.text, fontWeight: 500 }}>Risk-based sizing</span>
                <span style={{ fontSize: 10, color: k.dim, display: 'block', marginTop: 1 }}>Lots sized so premium risk stays within % of capital.</span>
              </div>
              {(cfg.risk_sizing ?? true) && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: k.dim, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
                  Risk %
                  <input type="number" min={0.1} max={25} step={0.5} value={cfg.risk_pct ?? 1}
                    onChange={(e) => patch({ risk_pct: Number(e.target.value) }, `Risk % → ${e.target.value}`)}
                    style={{ width: 48, padding: '3px 5px', fontSize: 11, border: `1px solid ${k.border}`, borderRadius: 4, background: k.surface, color: k.text, textAlign: 'right', outline: 'none' }} />
                </label>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', background: kiteLive ? tint(k.green, 5) : 'transparent', cursor: 'pointer', transition: 'background .18s' }}
              onClick={toggleKiteLive}>
              <Switch on={kiteLive} color={k.green} label="Kite live" onChange={() => {}} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: kiteLive ? k.green : k.text, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: kiteLive ? k.green : k.amber, flexShrink: 0 }} />
                  Kite {kiteLive ? 'LIVE' : 'PAPER'}
                </span>
                <span style={{ fontSize: 10, color: k.dim, display: 'block', marginTop: 1 }}>
                  {kiteLive ? 'Orders go to real Zerodha account.' : 'Simulated — no real money.'}
                </span>
              </div>
            </div>
          </>
        );

        return (
          <div data-st-settings className="st-drawer" style={{ display: 'grid', gridTemplateRows: settingsOpen ? '1fr' : '0fr' }}>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ background: k.bg, borderBottom: `1px solid ${k.border}` }}>
                {layout === 'cards' ? (
                  <div style={{ padding: '12px 16px 14px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase', color: k.text }}>Engine settings</span>
                    </div>
                    <Collapsible label="Scan" open={cardOpen.scan} onToggle={() => toggleCard('scan')}
                      summary={`${(SCAN_SOURCE_OPTS.find(o => o.value === cfg.scan_source)?.label) ?? 'Derivatives'} · ${Math.max(1, cfg.strike_moneyness.length)} strikes`}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>{scanGroup}</div>
                    </Collapsible>
                    <Collapsible label="Universe" open={cardOpen.universe} onToggle={() => toggleCard('universe')} summary={universeSummary(cfg)}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>{universeGroup}</div>
                    </Collapsible>
                    <Collapsible label="Execution" open={cardOpen.execution} onToggle={() => toggleCard('execution')}
                      summary={`${TRAIL_OPTS.find(o => o.value === (cfg.trail_target ?? 'fast'))?.label ?? 'Tight'} trail · ${ (EXIT_MODE_OPTS.find(o=>o.value===(cfg.exit_mode??'one_red'))?.short || '1R') } exit${cfg.auto_execute ? ' · auto' : ''} · ${kiteLive ? 'LIVE' : 'paper'}`}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>{executionGroup}</div>
                    </Collapsible>
                  </div>
                ) : (
                  <>
                    {/* Unified toolbar: pill tabs left, summary center, reset right */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 16px', borderBottom: `1px solid ${k.border}`, background: k.surface }}>
                      <PillTabs
                        active={settingsTab}
                        onSelect={(v) => setSettingsTab(v as 'scan' | 'universe' | 'execution')}
                        tabs={[{ value: 'scan', label: 'Scan' }, { value: 'universe', label: 'Universe' }, { value: 'execution', label: 'Execution' }]}
                      />
                      <div style={{ flex: 1 }} />
                    </div>
                    {/* Scrollable content — capped so it never takes >40% of the panel */}
                    <div style={{ maxHeight: 360, overflowY: 'auto', paddingBottom: 4 }}>
                      {settingsTab === 'scan' && scanGroup}
                      {settingsTab === 'universe' && universeGroup}
                      {settingsTab === 'execution' && executionGroup}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Signal list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {groupedRows.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            {scanning ? `Scanning ${signals?.scanning_label || '…'}` : signals?.market_open ? 'No ready setups right now. The engine re-scans automatically.' : `No cached signals from today's session. Markets open Mon–Fri 9:15 AM – 3:30 PM IST.`}
          </div>
        ) : (
          groupedRows.map(group => {
            const isCollapsed = collapsedGroups.has(group.label);
            return (
              <div key={group.label}>
                <div 
                  onClick={() => toggleGroup(group.label)}
                  style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 16px', background: k.surfaceHover, borderBottom: `1px solid ${k.border}`,
                    cursor: 'pointer', userSelect: 'none'
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, color: group.active ? k.green : k.text, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {group.active && <span style={{ width: 7, height: 7, borderRadius: 4, background: k.green }} />}
                    {group.label}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: k.dim }}>{group.rows.length} signals</span>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease', color: k.dim }}>
                      <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                  </div>
                </div>
                
                {!isCollapsed && (
                  <div className="kv-rows">
                    {group.rows.map((row) => (
                      <SignalCard key={`${row.token}:${row.option_type}:${row.timestamp_ms}`} row={row} quotes={quotes} viewLayout={viewLayout}
                        onSelectSignal={onSelectSignal} sort={legSort} showEnded={showEnded}
                        onClick={() => onSelectSignal({ token: row.token, underlying: row.underlying, timestamp_ms: row.timestamp_ms })} />
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default SterlingKiteEnginePane;

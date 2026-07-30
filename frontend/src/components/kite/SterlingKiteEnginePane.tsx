import React from 'react';
import { createPortal } from 'react-dom';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useCancelScan, useSetEngineConfig,
} from '../../hooks/useSterlingKiteEngine';
import { useCancelNavigatorScan, useNavigatorConfig, useRunNavigatorScan } from '../../hooks/useNavigator';
import type {
  AlignmentChip, EngineConfigModel, EngineSignalRow, LiquidityGroup, Moneyness,
  ScanSource, SignalsResponse, StockEntry, TrailTarget,
  ExitMode, SignalChartData,
} from '../../types/kiteEngine';
import { useKiteQuote } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { KiteLoader } from './KiteLoader';
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
import { signalChartDataForPremiumLeg } from '../charts/signalMarkerLogic';


interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: SignalChartData) => void;
}

// Plain-language labels (users were confused by fast/mid/slow + "early lock").
const TRAIL_OPTS: { value: TrailTarget; label: string; hint: string }[] = [
  { value: 'fast', label: 'Tight', hint: 'Default — exit quickly; trails the fast SuperTrend (21,1). Locks gains sooner, more whipsaw.' },
  { value: 'mid', label: 'Balanced', hint: 'Trails the mid SuperTrend (14,2). Balanced hold vs. protection.' },
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
const SCAN_SOURCE_OPTS: { value: ScanSource; label: string; hint: string }[] = [
  { value: 'spot', label: 'Spot', hint: "SuperTrend on the underlying's chart; option strikes are attached as candidates to buy." },
  { value: 'derivatives', label: 'Derivatives', hint: "SuperTrend on each selected contract's OWN premium chart — BUY when the premium turns up. (Default)" },
  { value: 'both', label: 'Both', hint: 'Run both scans; each signal is tagged Spot or DERIV.' },
  { value: 'confluence', label: 'Confluence', hint: "Highest conviction: emit a strike only when the underlying fires a fresh entry AND that option's own premium ST also confirms. One merged row per underlying." },
];
// Which evidence lens the signal board is viewed through. Purely a local
// display preference (localStorage), never patched to the server — unlike
// scan_source/exit_mode above, this never changes what the engine scans.
type SignalMode = 'supertrend' | 'navigator' | 'combined' | 'common';
const SIGNAL_MODE_OPTS: { value: SignalMode; label: string; hint: string }[] = [
  { value: 'supertrend', label: 'SuperTrend', hint: 'Default triple-SuperTrend (Heikin-Ashi) signal only — the Navigator badge is hidden even when Navigator has evidence.' },
  { value: 'navigator', label: 'Navigator', hint: "Only setups the Value-Flow Navigator owns or has evidence for, viewed through its own status/effective score. Navigator scans independently and can run while SuperTrend is off." },
  { value: 'combined', label: 'Combined', hint: 'Every SuperTrend setup, with Navigator evidence shown alongside when available. (Default)' },
  { value: 'common', label: 'Common', hint: "Only setups where BOTH systems agree: SuperTrend is live and Navigator status is Confirmed or High Conviction. Navigator-owned rows remain visible in the Navigator lens." },
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
  if (cfg.scan_source === 'confluence') {
    // underlying spot chart + one premium per candidate strike (signal direction only)
    const premiums = instruments * nStrikes;
    return `${instruments} spot + up to ${premiums} premiums (confirmed legs only) · ${fmtTime(instruments + premiums)}/scan`;
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

/** Single source of truth for the signal-table column widths/labels — read by
 *  BOTH the list-view header and each leg row so they can never drift out of
 *  alignment (previously each side hand-typed its own copy of every width).
 *  Split into two groups matching the table's two flex sections: LEFT flows
 *  next to the (flex:1) Instrument column; RIGHT is pinned after the action
 *  buttons. `visibleWhen` is a tag both the header and the row resolve against
 *  their own (equivalent, differently-named) boolean for that condition. */
type SignalColVisibility = 'always' | 'exchange' | 'leg' | 'premium' | 'chg' | 'chgPct' | 'dir';
interface SignalColumnDef {
  key: string;
  label: string;
  width: number;
  align: 'left' | 'right';
  sortKey?: string;
  tooltip?: string;
  visibleWhen: SignalColVisibility;
}
const SIGNAL_LEFT_COLUMNS: Record<string, SignalColumnDef> = {
  exc: { key: 'exc', label: 'Exc.', width: 40, align: 'left', sortKey: 'exc', visibleWhen: 'exchange' },
  leg: { key: 'leg', label: 'Leg (Δ)', width: 78, align: 'right', sortKey: 'leg', visibleWhen: 'leg' },
  entry: { key: 'entry', label: 'Entry (Δpts)', width: 96, align: 'right', sortKey: 'entry', visibleWhen: 'premium' },
  sl: { key: 'sl', label: 'SL', width: 56, align: 'right', sortKey: 'sl', visibleWhen: 'premium' },
  tsl: { key: 'tsl', label: 'TSL', width: 56, align: 'right', sortKey: 'stop', visibleWhen: 'premium' },
  exit: { key: 'exit', label: 'Exit', width: 58, align: 'right', visibleWhen: 'always', tooltip: 'Red-counter progress toward the auto-exit rule (exit_mode)' },
  target: { key: 'target', label: 'Target', width: 44, align: 'right', visibleWhen: 'premium', tooltip: 'Trend-following — no fixed target; exit rides the trail (TSL) + red counter (Exit)' },
};
const SIGNAL_RIGHT_COLUMNS: Record<string, SignalColumnDef> = {
  chg: { key: 'chg', label: 'Chg.', width: 50, align: 'right', sortKey: 'chg', visibleWhen: 'chg' },
  chgPct: { key: 'chgPct', label: 'Chg. %', width: 60, align: 'right', sortKey: 'chgPct', visibleWhen: 'chgPct' },
  dir: { key: 'dir', label: '', width: 14, align: 'right', visibleWhen: 'dir' },
  ltp: { key: 'ltp', label: 'LTP', width: 70, align: 'right', sortKey: 'ltp', visibleWhen: 'always' },
};
/** Drag-to-reorder header cell wrapper. Uses raw pointer events (not native
 *  HTML5 draggable/dragstart) because native drag-and-drop's gesture
 *  recognition is unreliable for plain `<div>`s across browsers/trackpads —
 *  many devices never fire `dragstart` for a generic element, which is why
 *  this looked wired up correctly yet didn't respond to a real drag. Pointer
 *  events are dispatched directly for every mouse/touch/pen down-move-up, so
 *  there's no browser-level gesture heuristic in the way. */
function DraggableColHeader({ colKey, group, width, reorder, children }: {
  colKey: string; group: 'left' | 'right'; width: number;
  reorder: (group: 'left' | 'right', fromKey: string, toKey: string) => void;
  children: React.ReactNode;
}) {
  const draggingRef = React.useRef(false);
  const startRef = React.useRef<{ x: number; y: number } | null>(null);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    startRef.current = { x: e.clientX, y: e.clientY };
    draggingRef.current = false;

    const clearHighlight = () => {
      document.querySelectorAll('.col-drag-over').forEach((el) => el.classList.remove('col-drag-over'));
    };
    const targetAt = (x: number, y: number) =>
      document.elementFromPoint(x, y)?.closest('[data-col-key]') as HTMLElement | null;

    const onMove = (ev: PointerEvent) => {
      const start = startRef.current;
      if (!start) return;
      if (!draggingRef.current) {
        // Small movement threshold so a plain click still reaches the sort handler.
        if (Math.abs(ev.clientX - start.x) < 4 && Math.abs(ev.clientY - start.y) < 4) return;
        draggingRef.current = true;
        document.body.style.cursor = 'grabbing';
      }
      clearHighlight();
      const el = targetAt(ev.clientX, ev.clientY);
      if (el && el.getAttribute('data-col-group') === group && el.getAttribute('data-col-key') !== colKey) {
        el.classList.add('col-drag-over');
      }
    };
    const onUp = (ev: PointerEvent) => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      clearHighlight();
      if (draggingRef.current) {
        const el = targetAt(ev.clientX, ev.clientY);
        const toKey = el?.getAttribute('data-col-key');
        if (toKey && el?.getAttribute('data-col-group') === group && toKey !== colKey) {
          reorder(group, colKey, toKey);
        }
        // A drag that ends over a different header would otherwise still fire
        // that header's onClick (sort) right after pointerup - swallow it once.
        document.addEventListener('click', (ce) => { ce.stopPropagation(); ce.preventDefault(); }, { capture: true, once: true });
      }
      draggingRef.current = false;
      startRef.current = null;
    };
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  };

  return (
    <div
      data-col-key={colKey}
      data-col-group={group}
      onPointerDown={onPointerDown}
      style={{ width, flexShrink: 0, cursor: 'grab', userSelect: 'none', touchAction: 'none' }}
      title="Drag to reorder column"
    >
      {children}
    </div>
  );
}

/** Header row and each leg row now scroll independently (both can overflow a
 *  narrow right-sidebar width) — without syncing scrollLeft between them, a
 *  scrolled row's columns stop lining up under the header's labels. Shared at
 *  module scope since the header lives in SterlingKiteEnginePane while each
 *  row is its own SignalCard instance. */
function syncHscroll(e: React.UIEvent<HTMLDivElement>) {
  const left = e.currentTarget.scrollLeft;
  document.querySelectorAll('.st-header-row, .st-leg-row').forEach((el) => {
    if (el !== e.currentTarget) (el as HTMLElement).scrollLeft = left;
  });
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

function hasPremiumSnapshot(row: EngineSignalRow): boolean {
  return row.legs.some((leg) => (
    ((leg as any).premium_spot ?? 0) > 0
    || ((leg as any).premium_sl ?? 0) > 0
    || ((leg as any).entry_sl ?? 0) > 0
  ));
}

// Coarse moneyness group (ITM1-5 / ATM / OTM1-5 → ITM / ATM / OTM), shared by the
// per-bucket best-R:R/delta ranking and the "Best only" display order below.
function moneynessBucket(m: string | undefined): 'ITM' | 'ATM' | 'OTM' {
  if (m === 'ATM') return 'ATM';
  return m?.startsWith('ITM') ? 'ITM' : 'OTM';
}
const MONEYNESS_GROUP_ORDER: Record<'ITM' | 'ATM' | 'OTM', number> = { ITM: 0, ATM: 1, OTM: 2 };

function SignalCard({ row, onClick, onSelectSignal, onOpenChart, quotes, viewLayout, sort, showEnded = true, bestOnly = false, scanSource, signalMode = 'combined', showPremiumColumns }: {
  row: EngineSignalRow; onClick: () => void;
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  onOpenChart?: (underlying: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: SignalChartData) => void;
  quotes?: any;
  viewLayout: 'grid' | 'list';
  sort: { key: string; dir: string };
  showEnded?: boolean;
  bestOnly?: boolean;
  scanSource?: string;
  signalMode?: 'supertrend' | 'navigator' | 'combined' | 'common';
  showPremiumColumns?: boolean;
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
  // Legs that carry their own premium entry/stop columns: derivatives AND confluence
  // (confluence confirms each leg on its own premium chart, so it has the same data).
  // Spot legs are candidate strikes with no per-option premium, so those columns stay
  // hidden for them (the header mirrors this via scan_source !== 'spot').
  const hasPremium = isDeriv || row.source === 'confluence';
  // Whether the list header is showing the premium columns (Entry/SL/TSL/Target).
  // The header gates on the GLOBAL scan_source (!== 'spot'); the row MUST use the
  // same condition or its cells drift out from under the headers. In 'both' mode a
  // spot-source row has no per-leg premium (hasPremium=false) but the header still
  // shows those columns — so we render fixed-width placeholders ('—') to stay aligned.
  const showPremiumCols = showPremiumColumns ?? (scanSource !== undefined ? scanSource !== 'spot' : hasPremium);

  // Live LTP for a leg's contract (no entry-snapshot fallback — we need the live tick
  // to reconcile the frozen is_active flag, not the frozen entry).
  const legLtp = (leg: any): number | null => {
    const q = quotes?.[`${row.exchange}:${leg?.option_symbol}`];
    return q?.last_price ?? null;
  };
  const legIsExited = (leg: any) => (hasPremium ? legHasExited(leg, row.is_active, legLtp(leg)) : !row.is_active);
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

  // ✝ BEST R:R / ▲ HIGHEST DELTA — computed separately WITHIN each moneyness bucket
  // (ITM / ATM / OTM), not once across the whole ladder, so a deep-ITM winner never
  // shadows the best OTM strike (or vice versa) — every bucket you've scanned gets
  // its own pick. Same underlying logic as the Trade Impact Calculator (per-strike,
  // not per-bucket, there), so the badges stay conceptually in sync. The greeks use
  // the underlying spot, so a 1R underlying move is meaningful regardless of source.
  const { bestRRSyms, bestDeltaSyms } = React.useMemo(() => {
    const spot = uLastPx ?? row.spot ?? 0;
    const sd = stopDistance(spot, row.stop_loss ?? 0);
    const bestRRByBucket = new Map<string, { sym: string; val: number }>();
    const bestDeltaByBucket = new Map<string, { sym: string; val: number }>();
    for (const leg of visibleLegs) {
      const lq = quotes?.[`${row.exchange}:${leg.option_symbol}`];
      const premium = lq?.last_price ?? (leg as any).premium_spot ?? 0;
      if (premium <= 0) continue;
      const g = computeGreeksFromLeg(leg.strike, leg.expiry, leg.option_type, spot, lq, leg.lot_size ?? null);
      if (!g) continue;
      const bucket = moneynessBucket(leg.moneyness);
      const { rr, effPct } = computeLegRR(g.delta, g.gamma, premium, sd);
      const v = rrScore(rr, effPct);
      const curRR = bestRRByBucket.get(bucket);
      if (!curRR || v > curRR.val) bestRRByBucket.set(bucket, { sym: leg.option_symbol, val: v });
      const ad = Math.abs(g.delta);
      const curDelta = bestDeltaByBucket.get(bucket);
      if (!curDelta || ad > curDelta.val) bestDeltaByBucket.set(bucket, { sym: leg.option_symbol, val: ad });
    }
    return {
      bestRRSyms: new Set(Array.from(bestRRByBucket.values(), (x) => x.sym)),
      bestDeltaSyms: new Set(Array.from(bestDeltaByBucket.values(), (x) => x.sym)),
    };
  }, [uLastPx, row, visibleLegs, quotes]);

  // Publish this signal's ✝/▲ markers (keyed by the full EXCHANGE:tradingsymbol)
  // so the watchlist and ticker can show them on the same contract. Cleared on
  // unmount so stale signals don't keep marking instruments.
  const publishMarkers = useSignalMarkers((m) => m.publish);
  const clearMarkers = useSignalMarkers((m) => m.clear);
  React.useEffect(() => {
    const rowKey = String(row.token);
    const entries: Record<string, Marker> = {};
    for (const sym of bestRRSyms) {
      const key = `${row.exchange}:${sym}`;
      entries[key] = { ...entries[key], rr: true };
    }
    for (const sym of bestDeltaSyms) {
      const key = `${row.exchange}:${sym}`;
      entries[key] = { ...entries[key], delta: true };
    }
    publishMarkers(rowKey, entries);
    return () => clearMarkers(rowKey);
  }, [bestRRSyms, bestDeltaSyms, row.exchange, row.token, publishMarkers, clearMarkers]);

  // Legs always render grouped and ordered ITM → ATM → OTM, regardless of "Best
  // only" — the fixed order makes a card scannable at a glance whether it's
  // showing the full ladder or just the picks below. (List view still lets an
  // explicit column-sort click override this, same as before.)
  //
  // "Best only" additionally cuts the card down to just the ✝ best-R:R and ▲
  // highest-delta legs PER bucket (up to 2 legs × however many of ITM/ATM/OTM are
  // present, deduped — a bucket with one leg is trivially both). If nothing could
  // be ranked (e.g. all legs illiquid / no greeks), fall back to the full set so a
  // card never renders empty.
  const displayLegs = React.useMemo(() => {
    let base = visibleLegs;
    if (bestOnly) {
      const keep = new Set([...bestRRSyms, ...bestDeltaSyms]);
      const filtered = keep.size ? visibleLegs.filter((l) => keep.has(l.option_symbol)) : [];
      if (filtered.length) base = filtered;
    }
    return [...base].sort(
      (a, b) => MONEYNESS_GROUP_ORDER[moneynessBucket(a.moneyness)] - MONEYNESS_GROUP_ORDER[moneynessBucket(b.moneyness)],
    );
  }, [bestOnly, visibleLegs, bestRRSyms, bestDeltaSyms]);
  const emptyLegMessage = React.useMemo(() => {
    if (row.legs.length > 0 && visibleLegs.length === 0) {
      return showEnded ? 'No option legs to display.' : 'All resolved legs are ended. Enable Ended to view them.';
    }
    return row.resolution_reason || 'No option contract matched the selected strike/expiry settings.';
  }, [row.legs.length, row.resolution_reason, showEnded, visibleLegs.length]);

  return (
    <div
      className="st-parent-row"
      style={{ padding: '10px 12px', borderBottom: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 6, background: k.bg }}
    >
      <div 
        className="st-parent-header" 
        onClick={onClick}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', position: 'relative', margin: '-10px -12px', padding: '10px 12px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', overflow: 'hidden', minWidth: 0 }}>
          {isDeriv ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: uColor }}>{row.underlying}</span>
                {/* Underlying spot LTP next to the name. Derivatives parents carry
                    row.spot=0 (the premium lives on each leg), so only show when the
                    live index/stock quote resolved — no misleading "0.00" fallback. */}
                {uLastPx != null && (
                  <span className="st-prices-parent" style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: uColor }}>
                    <span style={{ fontWeight: 500 }}>{uLastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    {s.showPriceChange && uChgAbs != null && <span style={{ fontSize: 10, color: k.dim }}>{uChgAbs.toFixed(2)}</span>}
                    {s.showPriceChangePct && uChgPct != null && <span style={{ fontSize: 10, color: k.text }}>{uChgPct.toFixed(2)}%</span>}
                    {s.showPriceDirection && (
                      <span style={{ display: 'flex', alignItems: 'center', margin: '0 -2px' }}>
                        {uChgAbs != null && uChgAbs !== 0 ? (uChgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                        {uChgAbs === 0 && <span style={{ fontSize: 14, padding: '0 2px', lineHeight: 1 }}>∘</span>}
                      </span>
                    )}
                  </span>
                )}
              </span>
            </div>
          ) : (
            <>
              <span style={{ fontSize: 12, fontWeight: 600, color: uColor }}>{row.underlying}</span>

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
          {row.source === 'navigator' && (
            <span
              title="Navigator idea — no SuperTrend trigger at all, surfaced purely from Navigator's own AVWAP + volatility evidence. Not a triple-SuperTrend setup."
              style={{ fontSize: 10, color: k.purple, background: `${k.purple}18`, border: `1px solid ${k.purple}40`, borderRadius: 3, padding: '1px 5px', fontWeight: 700 }}
            >
              Navigator idea
            </span>
          )}
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
          {row.navigator && signalMode !== 'supertrend' && (() => {
            const nav = row.navigator;
            const navColor = nav.status === 'CONFIRMED' || nav.status === 'HIGH_CONVICTION' ? k.green
              : nav.status === 'CONFLICT' ? k.red
              : nav.status === 'WATCH' ? k.blue : k.dim;
            const scoreLabel = nav.effective_score != null ? ` ${Math.round(nav.effective_score)}` : '';
            // In 'navigator'/'common' lenses Navigator IS the point of the
            // view, so give its badge more visual weight than in 'combined'
            // (where it's a secondary annotation alongside the raw score).
            const emphasized = signalMode === 'navigator' || signalMode === 'common';
            return (
              <span
                title={`Navigator: ${nav.status}${scoreLabel ? ` (effective score${scoreLabel})` : ''} — reasons: ${nav.reason_codes.join(', ') || 'none'}. Raw score above is unchanged.`}
                style={{
                  fontSize: emphasized ? 11 : 10, color: navColor, background: `${navColor}18`,
                  borderRadius: 3, padding: emphasized ? '2px 6px' : '1px 4px', fontWeight: emphasized ? 800 : 600,
                  border: emphasized ? `1px solid ${navColor}40` : undefined,
                }}
              >
                Nav {nav.status.replace('_', ' ')}{scoreLabel}
              </span>
            );
          })()}
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
          {displayLegs.map((leg) => {
            const sym = `${row.exchange}:${leg.option_symbol}`;
            const q = quotes?.[sym];
            const lastPx = q?.last_price || (leg as any).premium_spot;
            // Non-positive premium ⇒ no real entry/stop (illiquid bar) — show "—", not 0.0.
            const rawGSlPx = (leg as any).premium_sl;
            const slPx = rawGSlPx != null && rawGSlPx > 0 ? rawGSlPx : null;
            const legEnded = legIsExited(leg);
            const isExp = expanded.has(leg.option_symbol);
            const gSpot = uLastPx ?? row.spot ?? 0;
            const gGreeks = computeGreeksFromLeg(leg.strike, leg.expiry, leg.option_type, gSpot, q, leg.lot_size ?? null);
            const gDelta = gGreeks ? Math.abs(gGreeks.delta).toFixed(2) : null;
            const rawGEntry = (leg as any).premium_spot;
            const gEntry = rawGEntry != null && rawGEntry > 0 ? rawGEntry : null;
            const gDiff = (!legEnded && lastPx != null && gEntry != null) ? lastPx - gEntry : null;
            return (
              <div key={leg.option_symbol} style={{ minWidth: 132 }}>
                <div 
                  onClick={(e) => toggleExpand(e, leg.option_symbol)}
                  style={{
                    display: 'flex', flexDirection: 'column', gap: 3,
                    padding: '6px 8px', borderRadius: 4,
                    background: 'transparent',
                    border: `1px solid ${k.border}`,
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = k.orange; e.currentTarget.style.background = 'transparent'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = k.border; e.currentTarget.style.background = 'transparent'; }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 10, color: k.orange, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <span>{leg.moneyness}{gDelta && <span style={{ color: k.dim, fontWeight: 600 }}> (Δ{gDelta})</span>}</span>
                      {bestRRSyms.has(leg.option_symbol) && (
                        <span title="Best reward-to-risk within its ITM/ATM/OTM bucket for a 1R move"
                          style={{ fontSize: 12, color: k.dim, lineHeight: 1 }}>✝</span>
                      )}
                      {bestDeltaSyms.has(leg.option_symbol) && (
                        <span title="Highest delta within its ITM/ATM/OTM bucket — most responsive to the underlying"
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
        {displayLegs.length === 0 ? (
          <span style={{ fontSize: 10, color: k.dim }}>{emptyLegMessage}</span>
        ) : (
          <React.Fragment>
            {[...displayLegs].sort((a, b) => {
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
              } else if (sort.key === 'sl') {
                 valA = (a as any).entry_sl || 0;
                 valB = (b as any).entry_sl || 0;
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
          // A 0 / illiquid premium bar at the entry can leave these at 0 — that's not a
          // real entry/stop, so treat non-positive as "no value" (renders as "—") instead
          // of a misleading 0.00 sitting next to a live LTP (the classic "entry 0 (+61.75)").
          const rawEntryPx = (leg as any).premium_spot;
          const entryPx = rawEntryPx != null && rawEntryPx > 0 ? rawEntryPx : null;
          const rawSlPx = (leg as any).premium_sl;
          const slPx = rawSlPx != null && rawSlPx > 0 ? rawSlPx : null;
          // Initial hard stop at entry (fast ST line) — the static SL column, distinct
          // from the live ratcheting TSL (premium_sl) above.
          const rawInitSl = (leg as any).entry_sl;
          const initSlPx = rawInitSl != null && rawInitSl > 0 ? rawInitSl : null;
          // Exit column — red-counter progress ("<reds>/<threshold> red") toward the
          // auto-exit rule. Row-level (the underlying/premium regime), coloured by how
          // close it is to firing: green→safe, amber→approaching, red→at/over threshold.
          const legExitState = leg.exit_state ?? row.exit_state;
          const exitReds = legExitState ? (parseInt(legExitState, 10) || 0) : 0;
          const exitThr = legExitState ? (parseInt(legExitState.split('/')[1] || '1', 10) || 1) : 1;
          const exitColor = !legExitState ? k.dim : exitReds <= 0 ? k.dim : exitReds >= exitThr ? k.red : k.orange;
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
                onScroll={syncHscroll}
                onClick={(e) => toggleExpand(e, leg.option_symbol)}
                style={{ cursor: 'pointer', background: k.bg }}
              >
                   <span style={{ color: color, fontWeight: 400, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: '1 1 150px', minWidth: 150, display: 'flex', alignItems: 'center', gap: 6 }}>
                     <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                     {bestRRSyms.has(leg.option_symbol) && (
                       <span title="Best reward-to-risk within its ITM/ATM/OTM bucket for a 1R move"
                         style={{ fontSize: 13, color: k.dim, lineHeight: 1, flexShrink: 0 }}>✝</span>
                     )}
                     {bestDeltaSyms.has(leg.option_symbol) && (
                       <span title="Highest delta within its ITM/ATM/OTM bucket — most responsive to the underlying"
                         style={{ fontSize: 12, color: k.dim, lineHeight: 1, flexShrink: 0, opacity: 0.75 }}>▲</span>
                     )}
                   </span>
                   {(() => {
                     const colVisible: Record<SignalColVisibility, boolean> = {
                       always: true, exchange: s.showExchange, leg: s.showLeg,
                       premium: showPremiumCols, chg: s.showPriceChange,
                       chgPct: s.showPriceChangePct, dir: s.showPriceDirection,
                     };
                     const renderLeftCell = (key: string) => {
                       switch (key) {
                         case 'exc':
                           return <span style={{ fontSize: 11, color: k.dim, width: '100%', flexShrink: 0 }}>{row.exchange}</span>;
                         case 'leg':
                           return (
                             <span style={{ fontSize: 11, color: k.dim, width: '100%', flexShrink: 0 }}>
                               {leg.moneyness}
                               {deltaTxt && <span style={{ opacity: 0.75 }}> (Δ{deltaTxt})</span>}
                             </span>
                           );
                         case 'entry':
                           // Fired fill premium. Dimmed + struck once the trend flips (history,
                           // not a live order). Bracket = live LTP move from entry. '—' for a
                           // spot-source row (no per-leg premium) so the column stays aligned.
                           return (
                             <span title={snapTitle} style={{ fontSize: 11, fontWeight: 500, color: ended ? k.dim : (entryPx != null ? accent : k.dim), width: '100%', textAlign: 'right', flexShrink: 0, textDecoration: ended ? 'line-through' : 'none', opacity: ended ? 0.65 : 1 }}>
                               {entryPx != null ? entryPx.toFixed(2) : '—'}
                               {entryDiff != null && (
                                 <span style={{ fontSize: 10, marginLeft: 3, fontWeight: 600, textDecoration: 'none', color: entryDiff >= 0 ? k.green : k.red }}>
                                   ({entryDiff >= 0 ? '+' : ''}{entryDiff.toFixed(2)})
                                 </span>
                               )}
                             </span>
                           );
                         case 'sl':
                           // Initial hard stop at the entry bar (fast ST line), static.
                           return (
                             <span title="Initial stop at entry (fast SuperTrend line)" style={{ fontSize: 10, color: k.dim, width: '100%', textAlign: 'right', flexShrink: 0, textDecoration: ended ? 'line-through' : 'none', opacity: ended ? 0.65 : 1 }}>
                               {initSlPx != null ? initSlPx.toFixed(1) : '—'}
                             </span>
                           );
                         case 'tsl':
                           // Live ratcheting trail stop (tightens as ST lines flip red).
                           return (
                             <span title="Trailing stop — ratchets tighter as SuperTrend lines flip red" style={{ fontSize: 10, color: k.dim, width: '100%', textAlign: 'right', flexShrink: 0, textDecoration: ended ? 'line-through' : 'none', opacity: ended ? 0.65 : 1 }}>
                               {slPx != null ? slPx.toFixed(1) : '—'}
                             </span>
                           );
                         case 'exit':
                           // Red-counter progress toward the auto-exit rule (row-level).
                           return (
                             <span title="Red-counter progress toward the auto-exit rule (exit_mode)" style={{ fontSize: 10, fontWeight: 600, color: exitColor, width: '100%', textAlign: 'right', flexShrink: 0 }}>
                               {legExitState ?? '—'}
                             </span>
                           );
                         case 'target':
                           // Trend-following: no fixed take-profit. Exit is owned by the
                           // trail (TSL) + the red counter (Exit), so this stays "—".
                           return (
                             <span title="Trend-following — no fixed target; exit rides the trail (TSL) + red counter (Exit)" style={{ fontSize: 10, color: k.dim, width: '100%', textAlign: 'right', flexShrink: 0, opacity: 0.6 }}>
                               —
                             </span>
                           );
                         default:
                           return null;
                       }
                     };
                     return s.signalLeftColumnOrder.map((key) => {
                       const col = SIGNAL_LEFT_COLUMNS[key];
                       if (!col || !colVisible[col.visibleWhen]) return null;
                       return (
                         <div key={col.key} style={{ width: col.width, flexShrink: 0 }}>
                           {renderLeftCell(col.key)}
                         </div>
                       );
                     });
                   })()}

                {!isExp && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0, overflow: 'hidden', flexShrink: 0, marginLeft: 'auto' }}>
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
                      onChart={(e) => { e.stopPropagation(); onOpenChart?.(`${row.exchange}:${leg.option_symbol}`, 'chart', undefined, signalChartDataForPremiumLeg(row, leg)); }}
                    />
                    
                    <div className="st-prices" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                      {(() => {
                        const colVisible: Record<SignalColVisibility, boolean> = {
                          always: true, exchange: s.showExchange, leg: s.showLeg,
                          premium: showPremiumCols, chg: s.showPriceChange,
                          chgPct: s.showPriceChangePct, dir: s.showPriceDirection,
                        };
                        const renderRightCell = (key: string) => {
                          switch (key) {
                            case 'chg':
                              return <span style={{ color: k.dim, fontSize: 11, width: '100%', textAlign: 'right' }}>{chgAbs != null ? chgAbs.toFixed(2) : '—'}</span>;
                            case 'chgPct':
                              return <span style={{ color: k.text, fontSize: 11, width: '100%', textAlign: 'right' }}>{chgPct != null ? `${chgPct.toFixed(2)}%` : '—'}</span>;
                            case 'dir':
                              return (
                                <span style={{ color: color, display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'center' }}>
                                  {chgAbs != null && chgAbs !== 0 ? (chgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                                  {chgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                                </span>
                              );
                            case 'ltp':
                              return (
                                <span style={{ color: color, fontWeight: 500, fontSize: 13, width: '100%', textAlign: 'right' }}>
                                  {lastPx != null ? lastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                                </span>
                              );
                            default:
                              return null;
                          }
                        };
                        return s.signalRightColumnOrder.map((key) => {
                          const col = SIGNAL_RIGHT_COLUMNS[key];
                          if (!col || !colVisible[col.visibleWhen]) return null;
                          return (
                            <div key={col.key} style={{ width: col.width, flexShrink: 0 }}>
                              {renderRightCell(col.key)}
                            </div>
                          );
                        });
                      })()}
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

function SignalTableSettingsPanel({
  viewLayout,
  onLayoutChange,
  bestOnly,
  onBestOnlyChange,
  showEnded,
  onShowEndedChange,
}: {
  viewLayout: 'grid' | 'list';
  onLayoutChange: (layout: 'grid' | 'list') => void;
  bestOnly: boolean;
  onBestOnlyChange: (next: boolean) => void;
  showEnded: boolean;
  onShowEndedChange: (next: boolean) => void;
}) {
  const settings = useKiteSettings();
  const columns: Array<{ key: 'showExchange' | 'showLeg' | 'showPriceChange' | 'showPriceChangePct' | 'showPriceDirection'; label: string; hint: string }> = [
    { key: 'showExchange', label: 'Exchange', hint: 'NSE, NFO or BFO badge' },
    { key: 'showLeg', label: 'Leg', hint: 'ATM, ITM or OTM label' },
    { key: 'showPriceChange', label: 'Change', hint: 'Absolute price change' },
    { key: 'showPriceChangePct', label: 'Change %', hint: 'Percentage price change' },
    { key: 'showPriceDirection', label: 'Direction', hint: 'Up/down direction indicator' },
  ];

  const reset = () => {
    settings.resetSignalTableSettings();
    onLayoutChange('list');
    onBestOnlyChange(false);
    onShowEndedChange(true);
  };

  const openEngine = () => {
    localStorage.setItem('kite_connect_section', 'engine');
    window.dispatchEvent(new CustomEvent('kite-nav-click', { detail: 'connect' }));
  };

  return (
    <div style={{ padding: '16px 18px 18px', background: k.bg, borderBottom: `1px solid ${k.border}` }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14, marginBottom: 15 }}>
        <div>
          <div style={{ color: k.text, fontSize: 13.5, fontWeight: 750 }}>Signal table settings</div>
          <div style={{ color: '#777', fontSize: 10.5, lineHeight: 1.5, marginTop: 3 }}>
            These choices change only this table. Scanner, entry, exit and risk rules live under Connect → Engine.
          </div>
        </div>
        <button type="button" onClick={openEngine} style={{ minHeight: 34, flexShrink: 0, border: `1px solid ${k.border}`, borderRadius: 7, background: k.bg, color: k.text, padding: '0 11px', fontSize: 10.5, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer' }}>
          Configure engine ↗
        </button>
      </div>

      <div className="sk-table-settings-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, .8fr) minmax(190px, 1fr) minmax(250px, 1.25fr)', border: `1px solid ${k.border}`, borderRadius: 8, overflow: 'hidden' }}>
        <div className="sk-table-settings-group" style={{ padding: 13 }}>
          <div style={{ color: '#777', fontSize: 9.5, fontWeight: 750, letterSpacing: .55, textTransform: 'uppercase', marginBottom: 9 }}>Layout</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, padding: 3, border: `1px solid ${k.border}`, borderRadius: 8, background: '#f6f6f7' }}>
            {([
              { value: 'list' as const, label: 'List', icon: <ListIcon /> },
              { value: 'grid' as const, label: 'Grid', icon: <GridIcon /> },
            ]).map((option) => {
              const selected = viewLayout === option.value;
              return (
                <button key={option.value} type="button" title={`${option.label} layout`} aria-pressed={selected} onClick={() => onLayoutChange(option.value)} style={{
                  minHeight: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  border: 'none', borderRadius: 6,
                  background: selected ? k.bg : 'transparent', color: selected ? k.text : '#777',
                  boxShadow: selected ? `inset 0 -2px ${k.orange}, 0 1px 2px rgba(0,0,0,.08)` : 'none',
                  padding: '0 8px', fontSize: 10.5, fontWeight: selected ? 700 : 550, fontFamily: 'inherit', cursor: 'pointer',
                }}>
                  {option.icon}{option.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="sk-table-settings-group" style={{ padding: 13, borderLeft: `1px solid ${k.border}` }}>
          <div style={{ color: '#777', fontSize: 9.5, fontWeight: 750, letterSpacing: .55, textTransform: 'uppercase', marginBottom: 7 }}>Rows</div>
          <label style={{ minHeight: 32, display: 'flex', alignItems: 'center', gap: 8, color: k.text, fontSize: 10.5, padding: '4px 2px', cursor: 'pointer' }}>
            <input type="checkbox" checked={bestOnly} onChange={(event) => onBestOnlyChange(event.target.checked)} style={{ width: 15, height: 15, margin: 0, accentColor: k.orange }} />
            Best signal per instrument
          </label>
          <label style={{ minHeight: 32, display: 'flex', alignItems: 'center', gap: 8, color: k.text, fontSize: 10.5, padding: '4px 2px', cursor: 'pointer' }}>
            <input type="checkbox" checked={showEnded} onChange={(event) => onShowEndedChange(event.target.checked)} style={{ width: 15, height: 15, margin: 0, accentColor: k.orange }} />
            Show ended setups
          </label>
        </div>

        <div className="sk-table-settings-group" style={{ padding: 13, borderLeft: `1px solid ${k.border}` }}>
          <div style={{ color: '#777', fontSize: 9.5, fontWeight: 750, letterSpacing: .55, textTransform: 'uppercase', marginBottom: 7 }}>Visible columns</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '2px 8px' }}>
            {columns.map((column) => (
              <label key={column.key} title={column.hint} style={{ minHeight: 28, display: 'flex', alignItems: 'center', gap: 7, color: k.text, fontSize: 10.5, padding: '3px 2px', cursor: 'pointer' }}>
                <input type="checkbox" checked={settings[column.key]} onChange={() => settings.toggleShow(column.key)} style={{ width: 14, height: 14, margin: 0, accentColor: k.orange }} />
                {column.label}
              </label>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 11 }}>
        <span style={{ color: k.dim, fontSize: 9.5 }}>In List view, drag column headers to reorder them.</span>
        <button type="button" onClick={reset} style={{ minHeight: 30, border: `1px solid ${k.border}`, borderRadius: 6, background: k.bg, color: '#666', padding: '0 10px', fontSize: 10, fontWeight: 600, fontFamily: 'inherit', cursor: 'pointer' }}>
          Reset table view
        </button>
      </div>
      <style>{`
        @media (max-width: 720px) {
          .sk-table-settings-grid { grid-template-columns: 1fr !important; }
          .sk-table-settings-group { border-left: none !important; border-top: 1px solid ${k.border}; }
          .sk-table-settings-group:first-child { border-top: none; }
        }
      `}</style>
    </div>
  );
}

// Inline dropdown for changing a signal-source-tier setting (scan source, exit rule)
// right from the table toolbar — same open/close/select interaction as the chart's
// candle-type and indicator pickers (a button showing the current choice + chevron,
// which opens a positioned popover list with a checkmark on the active option).
function InlineDropdown<T extends string>({
  value, options, onChange, tone, title,
}: {
  value: T;
  options: { value: T; label: string; hint?: string }[];
  onChange: (next: T) => void;
  tone: string;
  title: string;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const current = options.find((option) => option.value === value);

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-flex' }}>
      <button type="button" title={title} aria-haspopup="listbox" aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 4, border: 'none', borderRadius: 999,
          background: tint(tone, 7), color: tone, padding: '2px 6px 2px 8px', fontSize: 9, fontWeight: 700,
          fontFamily: 'inherit', cursor: 'pointer',
        }}>
        {current?.label ?? value}
        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform .15s ease' }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div role="listbox" aria-label={title} style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 30, minWidth: 210,
          background: k.bg, border: `1px solid ${k.border}`, borderRadius: 8, boxShadow: '0 6px 18px rgba(0,0,0,.18)',
          overflow: 'hidden', padding: 4,
        }}>
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button key={option.value} type="button" role="option" aria-selected={selected}
                onClick={() => { onChange(option.value); setOpen(false); }}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8, width: '100%', textAlign: 'left',
                  border: 'none', borderRadius: 5, background: selected ? tint(tone, 8) : 'transparent',
                  color: k.text, padding: '7px 8px', fontFamily: 'inherit', cursor: 'pointer',
                }}>
                <span style={{ width: 12, flexShrink: 0, color: tone, fontSize: 11, fontWeight: 700 }}>{selected ? '✓' : ''}</span>
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 11.5, fontWeight: selected ? 700 : 600 }}>{option.label}</span>
                  {option.hint && <span style={{ display: 'block', marginTop: 1, fontSize: 9.5, color: k.dim, lineHeight: 1.35 }}>{option.hint}</span>}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Chip that collapses every signal to only its ✝ best-R:R and ▲ highest-delta legs,
// hiding the middle-of-the-ladder strikes. Same pill styling as EndedToggle (blue
// accent to distinguish it) so the two read as a matched pair in the toolbar.
function BestOnlyToggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}
      title="Show only the best strikes per signal: ✝ best reward:risk and ▲ highest delta">
      <span style={{ fontSize: 10, color: on ? k.blue : k.dim }}>Best ✝▲</span>
      <button onClick={onChange} aria-pressed={on} aria-label="Show best strikes only"
        style={{
          position: 'relative', width: 28, height: 16, borderRadius: 999, border: 'none', padding: 0,
          cursor: 'pointer', flexShrink: 0, background: on ? k.blue : k.border, transition: 'background .18s ease',
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

export function SterlingKiteEnginePane({ onSelectSignal, onOpenChart }: Props) {
  const s = useKiteSettings();
  const { data: signals, isLoading: signalsLoading } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
  const { data: navigatorConfig } = useNavigatorConfig();
  const setCfg = useSetEngineConfig();
  const scan = useRunScan();
  const cancelScan = useCancelScan();
  const navigatorScan = useRunNavigatorScan();
  const cancelNavigatorScan = useCancelNavigatorScan();
  const navigatorEnabled = navigatorConfig?.record.config.enabled ?? false;
  const supertrendEnabled = cfg?.engine_enabled ?? true;
  const navigatorOnlyRuntime = Boolean(cfg && !cfg.engine_enabled && navigatorEnabled);
  // SuperTrend runs when it's on — or as the fallback when Navigator is off
  // too, so the button is never a no-op.
  const scanRunsSupertrend = supertrendEnabled || !navigatorEnabled;
  const scanPending = scan.isPending || navigatorScan.isPending;
  const scanTitle = navigatorOnlyRuntime
    ? 'Run Navigator scan'
    : (scanRunsSupertrend && navigatorEnabled ? 'Re-scan both engines' : 'Re-scan now');
  const scanLock = React.useRef(false);
  const doScan = () => {
    if (scanLock.current || scanPending) return;
    scanLock.current = true;
    // The two engines are peers with separate scan endpoints, so a manual
    // re-scan has to refresh whichever ones are actually on — otherwise the
    // Navigator half of the board stays stale until its own 5-minute loop.
    // Sequential on purpose: both draw on the same Kite ~3 req/s historical
    // budget, and firing them together would double the effective concurrency.
    (async () => {
      if (scanRunsSupertrend) await scan.mutateAsync();
      if (navigatorEnabled) await navigatorScan.mutateAsync();
    })()
      .catch(() => { /* each mutation surfaces its own error toast */ })
      .finally(() => { scanLock.current = false; });
  };
  const doCancelScan = () => {
    if (scanRunsSupertrend) cancelScan.mutate();
    if (navigatorEnabled) cancelNavigatorScan.mutate();
  };

  const [query, setQuery] = React.useState('');
  const [searchSettingsOpen, setSearchSettingsOpen] = React.useState(false);
  const [sortBy, setSortBy] = React.useState('Custom');
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [viewLayout, setViewLayout] = React.useState<'grid' | 'list'>(
    () => (localStorage.getItem('kite_st_view_layout') as 'grid' | 'list') || 'list',
  );
  const [signalMode, setSignalMode] = React.useState<SignalMode>(
    () => (localStorage.getItem('kite_st_signal_mode') as SignalMode) || 'combined',
  );
  const changeSignalMode = (next: SignalMode) => {
    setSignalMode(next);
    localStorage.setItem('kite_st_signal_mode', next);
  };
  const legSort = s.legSort;
  const setLegSort = s.setLegSort;
  const handleLegSort = (key: string) => {
    setLegSort(legSort.key === key
      ? { key, dir: legSort.dir === 'asc' ? 'desc' : legSort.dir === 'desc' ? '' : 'asc' }
      : { key, dir: 'asc' });
  };

  React.useEffect(() => {
    if (!settingsOpen) return;
    const onDown = (event: MouseEvent) => {
      const target = event.target as Element | null;
      if (target?.closest('[data-signal-table-settings]')) return;
      setSettingsOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [settingsOpen]);
  React.useEffect(() => {
    localStorage.setItem('kite_st_view_layout', viewLayout);
  }, [viewLayout]);

  // The signal table can still turn the engine back on from its dedicated off state.
  // All other engine configuration now lives under Connect → Engine.
  const patch = (values: Partial<EngineConfigModel>, message?: string, rescan = false) => {
    if (!cfg) return;
    setCfg.mutate({ ...cfg, ...values }, {
      onSuccess: () => {
        if (message) notifyOrder({ kind: 'info', title: 'Settings updated', message });
        if (rescan) doScan();
      },
    });
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
    if (signalMode === 'navigator') {
      result = result.filter((r) => r.navigator != null);
    } else if (signalMode === 'common') {
      // "Common" means both systems agree — a row Navigator originated on
      // its own (no SuperTrend trigger at all) can't structurally satisfy
      // that, regardless of its own status.
      result = result.filter((r) => r.source !== 'navigator' && r.navigator != null && (r.navigator.status === 'CONFIRMED' || r.navigator.status === 'HIGH_CONVICTION'));
    } else if (signalMode === 'supertrend') {
      // "SuperTrend" means "what the board looks like with no Navigator at
      // all" — a Navigator-originated row has no real triple-ST basis behind
      // it, so it's excluded here rather than shown as a badge-less phantom.
      result = result.filter((r) => r.source !== 'navigator');
    }
    // 'combined' keeps every row (SuperTrend setups AND Navigator-originated
    // ones) — it differs from the others only in whether/how badges render
    // (see SignalCard).
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
  }, [rows, query, sortBy, signalMode]);
  const showSignalPremiumColumns = React.useMemo(
    () => cfg?.scan_source !== 'spot' || filteredRows.some(hasPremiumSnapshot),
    [cfg?.scan_source, filteredRows],
  );

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

  // Recent ended setups are part of the signal board, so show their rows on load.
  // Users can still collapse any date bucket manually for the current session.
  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(
    () => new Set(),
  );
  const [showEnded, setShowEnded] = React.useState<boolean>(() => localStorage.getItem('kite_st_show_ended') !== 'false');
  const [bestOnly, setBestOnly] = React.useState<boolean>(() => localStorage.getItem('kite_st_best_only') === 'true');
  const changeShowEnded = (next: boolean) => {
    setShowEnded(next);
    localStorage.setItem('kite_st_show_ended', String(next));
  };
  const changeBestOnly = (next: boolean) => {
    setBestOnly(next);
    localStorage.setItem('kite_st_best_only', String(next));
  };
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
  // The Navigator/Common lenses can legitimately show nothing even while
  // SuperTrend has live setups — Navigator may be disabled, still warming
  // up, or simply not agreeing with any of them yet. Say so explicitly
  // instead of falling through to the generic "hidden by table filters"
  // copy, which implies a search/showEnded filter is the cause.
  const navigatorLensEmpty = rows.length > 0 && groupedRows.length === 0
    && (signalMode === 'navigator' || signalMode === 'common');
  const hiddenRecentCount = !isScanning && !navigatorLensEmpty && rows.length > 0 && groupedRows.length === 0
    ? rows.length
    : 0;
  const revealRecentSignals = () => {
    setQuery('');
    changeShowEnded(true);
    setCollapsedGroups(new Set());
  };

  const liveCount = rows.filter((r) => rowIsRunning(r, quotes)).length;

  // Publish the running count to the Kite footer (rendered in a different tree).
  // MUST be before the early-return below (hook count consistency) — cfg.engine_enabled
  // can flip while this component stays mounted, so every hook must run unconditionally.
  const setLiveCount = useLiveSignalCount((s) => s.setCount);
  React.useEffect(() => { setLiveCount(liveCount); }, [liveCount, setLiveCount]);
  React.useEffect(() => () => setLiveCount(0), [setLiveCount]);

  // ── Engine master gate ──────────────────────────────────────────────────────
  if (cfg && !cfg.engine_enabled && !navigatorEnabled && rows.length === 0) {
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
              Supertrend and Navigator scanning are disabled. Kite runs in normal mode
              — manual trading, market watch, and existing flows are unaffected.
            </div>
          </div>
          <button
            onClick={() => patch({ engine_enabled: true }, 'Sterling Kite Engine enabled', true)}
            disabled={setCfg.isPending}
            style={{ padding: '10px 28px', borderRadius: 8, border: 'none', cursor: 'pointer',
                     background: k.green, color: '#fff', fontSize: 13, fontWeight: 700,
                     opacity: setCfg.isPending ? 0.6 : 1, transition: 'opacity 0.15s' }}>
            Enable Engine
          </button>
          <div style={{ fontSize: 11, color: k.dim, textAlign: 'center', maxWidth: 240 }}>
            This only enables the Supertrend engine. Navigator has its own toggle
            under Connect → Value-Flow Navigator.
          </div>
        </div>
      </div>
    );
  }

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
            <InlineDropdown
              value={cfg.scan_source}
              options={SCAN_SOURCE_OPTS}
              tone={k.orange}
              title="Signal source — change it right here, or from Connect → Scan Setup. Shared by both engines, unless Navigator is set to its own scan scope."
              onChange={(next) => patch(
                { scan_source: next },
                `Signal source changed to ${SCAN_SOURCE_OPTS.find((option) => option.value === next)?.label}`,
                true,
              )}
            />
          )}
          {/* The red-counter exit rule is SuperTrend-only — it counts the
              three SuperTrend lines flipping against a position. A
              Navigator-originated row has no SuperTrend lines at all (it
              exits on its own AVWAP stop/target bracket), so under the
              Navigator lens this control governs nothing that's on screen.
              Hide it there rather than leave a live engine setting sitting
              next to rows it can't affect. */}
          {cfg && signalMode !== 'navigator' && (
            <InlineDropdown
              value={cfg.exit_mode ?? 'one_red'}
              options={EXIT_MODE_OPTS}
              tone={k.blue}
              title="Auto-exit rule (counter to the 3-green entry) — a SuperTrend setting, applies to every SuperTrend row. Change it right here, or from Connect → Engine Configuration"
              onChange={(next) => patch(
                { exit_mode: next },
                `Exit rule changed to ${EXIT_MODE_OPTS.find((option) => option.value === next)?.label}`,
              )}
            />
          )}
          {/* Divider: everything left is real engine config (server-persisted,
              changes what's scanned/how trades exit); everything right is a
              local-only display filter (localStorage, never patched to the
              server, never changes what's scanned). */}
          <div title="Left of here: engine settings (server-side). Right: local view filter only." style={{ width: 1, alignSelf: 'stretch', minHeight: 16, background: k.border, flexShrink: 0 }} />
          <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: 0.5, color: k.dim, flexShrink: 0 }}>VIEW</span>
          <InlineDropdown
            value={signalMode}
            options={SIGNAL_MODE_OPTS}
            tone={k.purple}
            title="Signal lens — a LOCAL view filter only (never changes what's scanned or traded). The two engines scan independently; this just picks which of their rows you're looking at."
            onChange={changeSignalMode}
          />
          {/* Scan status + live count now live in the Kite footer (see KiteLayout). */}
          <div style={{ flex: 1 }} />
          {/* Actions: rescan / table preferences */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
            {scanning ? (
              <HeaderIconBtn
                title="Stop scan"
                onClick={doCancelScan}
                disabled={cancelScan.isPending || cancelNavigatorScan.isPending}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
              </HeaderIconBtn>
            ) : (
              <HeaderIconBtn title={scanTitle} disabled={scanPending} onClick={() => doScan()}>
                <RefreshIcon spinning={scanPending} />
              </HeaderIconBtn>
            )}
          </div>
          <span data-signal-table-settings style={{ display: 'inline-flex' }}>
            <HeaderIconBtn title="Signal table settings" active={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}>
              <Icons.Settings />
            </HeaderIconBtn>
          </span>
        </div>

        {/* Progress bar — scan countdown */}
        <ScanProgressBar signals={signals} />
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
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
              <BestOnlyToggle on={bestOnly} onChange={() => changeBestOnly(!bestOnly)} />
              <EndedToggle on={showEnded} onChange={() => changeShowEnded(!showEnded)} />
            </div>
          </div>
          {viewLayout === 'list' && (
            <div className="st-header-row" onScroll={syncHscroll} style={{
              display: 'flex', alignItems: 'center', gap: 16,
              padding: '12px 16px', fontSize: 12, fontWeight: 400, color: k.dim, borderBottom: `1px solid ${k.border}`,
              overflowX: 'auto', overflowY: 'hidden',
            }}>
                 <SortHeaderDiv label="Instrument" sortKey="instrument" sort={legSort} handleSort={handleLegSort} style={{ flex: '1 1 150px', minWidth: 150 }} />
                 {(() => {
                   const colVisible: Record<SignalColVisibility, boolean> = {
                     always: true, exchange: s.showExchange, leg: s.showLeg,
                     premium: showSignalPremiumColumns, chg: s.showPriceChange,
                     chgPct: s.showPriceChangePct, dir: s.showPriceDirection,
                   };
                   return s.signalLeftColumnOrder.map((key) => {
                     const col = SIGNAL_LEFT_COLUMNS[key];
                     if (!col || !colVisible[col.visibleWhen]) return null;
                     return (
                       <DraggableColHeader key={col.key} colKey={col.key} group="left" width={col.width} reorder={s.reorderSignalColumn}>
                         {col.sortKey
                           ? <SortHeaderDiv label={col.label} sortKey={col.sortKey} sort={legSort} handleSort={handleLegSort} style={{ width: '100%' }} align={col.align} />
                           : <span style={{ display: 'block', width: '100%', textAlign: col.align }} title={col.tooltip}>{col.label}</span>}
                       </DraggableColHeader>
                     );
                   });
                 })()}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 16, flexShrink: 0, marginLeft: 'auto' }}>
                 <div style={{ width: 150 }}></div>
                 <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                   {(() => {
                     const colVisible: Record<SignalColVisibility, boolean> = {
                       always: true, exchange: s.showExchange, leg: s.showLeg,
                       premium: showSignalPremiumColumns, chg: s.showPriceChange,
                       chgPct: s.showPriceChangePct, dir: s.showPriceDirection,
                     };
                     return s.signalRightColumnOrder.map((key) => {
                       const col = SIGNAL_RIGHT_COLUMNS[key];
                       if (!col || !colVisible[col.visibleWhen]) return null;
                       return (
                         <DraggableColHeader key={col.key} colKey={col.key} group="right" width={col.width} reorder={s.reorderSignalColumn}>
                           {col.sortKey
                             ? <SortHeaderDiv label={col.label} sortKey={col.sortKey} sort={legSort} handleSort={handleLegSort} style={{ width: '100%' }} align={col.align} />
                             : <span style={{ display: 'block', width: '100%' }} />}
                         </DraggableColHeader>
                       );
                     });
                   })()}
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
          background: ${k.bg};
        }
        .st-parent-header:hover,
        .st-leg-row:hover,
        .st-group-header:hover {
          background: ${k.surfaceHover} !important;
        }

        .col-drag-over {
          box-shadow: inset 2px 0 0 0 ${k.blue};
        }

        .st-leg-row {
          position: relative;
          display: flex;
          align-items: center;
          gap: 16px;
          height: 41px;
          padding: 0 16px;
          box-sizing: border-box;
          border-bottom: 1px solid ${k.border};
          overflow-x: auto;
          overflow-y: hidden;
          scrollbar-width: none;
        }
        .st-leg-row::-webkit-scrollbar { display: none; }
        .st-header-row { scrollbar-width: none; }
        .st-header-row::-webkit-scrollbar { display: none; }
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
        .st-signal-in { animation: st-signal-in .28s ease-out; }
        @keyframes st-signal-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
        @media (prefers-reduced-motion: reduce) {
          .st-spin, .st-pulse, .st-scan-bar, .st-drawer, .st-signal-in { animation: none !important; transition: none !important; }
        }
      `}</style>


      {/* Table-only preferences. Trading logic is configured in Connect → Engine. */}
      <div data-signal-table-settings className="st-drawer" style={{ display: 'grid', gridTemplateRows: settingsOpen ? '1fr' : '0fr' }}>
        <div style={{ overflow: 'hidden' }}>
          {settingsOpen && (
            <SignalTableSettingsPanel
              viewLayout={viewLayout}
              onLayoutChange={setViewLayout}
              bestOnly={bestOnly}
              onBestOnlyChange={changeBestOnly}
              showEnded={showEnded}
              onShowEndedChange={changeShowEnded}
            />
          )}
        </div>
      </div>
      {/* Signal list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {hiddenRecentCount > 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            <div>
              {hiddenRecentCount} recent setup{hiddenRecentCount === 1 ? ' is' : 's are'} hidden by the current table filters.
            </div>
            <button
              type="button"
              onClick={revealRecentSignals}
              style={{ marginTop: 12, minHeight: 32, padding: '0 12px', border: `1px solid ${k.border}`, borderRadius: 6, background: '#fff', color: k.orange, fontFamily: 'inherit', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
            >
              Show recent signals
            </button>
          </div>
        ) : navigatorLensEmpty ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            <div>
              {(() => {
                // Count only real SuperTrend rows — Navigator-owned rows are on
                // this board too now, and calling them SuperTrend setups would
                // overstate what the other engine actually found.
                const stCount = rows.filter((r) => r.source !== 'navigator').length;
                const what = signalMode === 'common'
                  ? 'Navigator agreement (Confirmed / High Conviction)'
                  : 'Value-Flow Navigator evidence';
                return stCount === 1
                  ? `1 SuperTrend setup on the board, and it has no ${what} yet.`
                  : `${stCount} SuperTrend setups on the board, but none have ${what} yet.`;
              })()}
            </div>
            <div style={{ marginTop: 6 }}>
              {navigatorEnabled
                ? <>Navigator is on — it may still be warming up, or it simply has no {signalMode === 'common' ? 'agreement' : 'read'} on these yet. Switch lenses below to see the full board.</>
                : <>Navigator is off — enable it under <strong>Connect → Value-Flow Navigator</strong>, or switch lenses below.</>}
            </div>
            <button
              type="button"
              onClick={() => changeSignalMode('combined')}
              style={{ marginTop: 12, minHeight: 32, padding: '0 12px', border: `1px solid ${k.border}`, borderRadius: 6, background: '#fff', color: k.purple, fontFamily: 'inherit', fontSize: 11, fontWeight: 700, cursor: 'pointer' }}
            >
              Switch to Combined lens
            </button>
          </div>
        ) : groupedRows.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            {signalsLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                <KiteLoader size={26} />
                <span>Loading signal board…</span>
              </div>
            ) : scanning ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                <KiteLoader size={26} />
                <span>{`Scanning ${signals?.scanning_label || '…'}`}</span>
              </div>
            ) : signals?.market_open ? 'No active or recent setups on the board yet. The engine re-scans every ~5 min.' : `No recent signals on the board. Recent setups stay listed; the engine resumes when markets open (Mon–Fri 9:15 AM – 3:30 PM IST).`}
          </div>
        ) : (
          groupedRows.map(group => {
            const isCollapsed = collapsedGroups.has(group.label);
            return (
              <div key={group.label}>
                <div 
                  onClick={() => toggleGroup(group.label)}
                  className="st-group-header"
                  style={{ 
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '8px 16px', background: k.bg, borderBottom: `1px solid ${k.border}`,
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
                      <div key={`${row.token}:${row.option_type}:${row.timestamp_ms}`} className="st-signal-in">
                        <SignalCard row={row} quotes={quotes} viewLayout={viewLayout}
                          scanSource={cfg?.scan_source} signalMode={signalMode}
                          showPremiumColumns={showSignalPremiumColumns}
                          onSelectSignal={onSelectSignal} sort={legSort} showEnded={showEnded} bestOnly={bestOnly}
                          onClick={() => onSelectSignal({ token: row.token, underlying: row.underlying, timestamp_ms: row.timestamp_ms })}
                          onOpenChart={onOpenChart ? (symbol, tab, _trailTarget, signalData) => onOpenChart(symbol, tab, cfg?.trail_target, signalData) : undefined} />
                      </div>
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

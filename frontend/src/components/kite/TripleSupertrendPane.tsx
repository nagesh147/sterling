import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useCancelScan, useSetEngineConfig, useResetEngineConfig,
  useScanReport,
} from '../../hooks/useTripleSupertrend';
import type {
  AlignmentChip, ContractScanEntry, EngineConfigModel, EngineSignalRow, Moneyness,
  ScanExpiry, ScanSource, ScanReportResponse, SignalsResponse, TrailTarget,
} from '../../types/kiteEngine';
import { useKiteQuote, useKiteAccounts, useUpdateKiteAccount } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { Icons } from '../../styles/kiteUI';
import { QuoteDetail, KiteSearchBar } from './MarketWatchPane';
import { KiteActionButtons } from './KiteActionButtons';
import { computeGreeksFromLeg } from '../../utils/computeGreeks';
import { notifyOrder } from '../../store/useKiteNotifications';
import { useKiteSettings } from '../../store/useKiteSettings';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';


interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
}

// Plain-language labels (users were confused by fast/mid/slow + "early lock").
const TRAIL_OPTS: { value: TrailTarget; label: string; hint: string }[] = [
  { value: 'fast', label: 'Tight', hint: 'Exit quickly — trails the fast SuperTrend (21,1). Locks gains sooner, more whipsaw.' },
  { value: 'mid', label: 'Balanced', hint: 'Default — trails the mid SuperTrend (14,2). Balanced hold vs. protection.' },
  { value: 'slow', label: 'Loose', hint: 'Hold longer — trails the slow SuperTrend (7,3). Rides trends further, gives back more.' },
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
const EXPIRY_OPTS: { value: ScanExpiry; label: string; hint: string }[] = [
  { value: 'weekly', label: 'Weekly', hint: 'Weekly contracts expiring every Thursday (including current week).' },
  { value: 'monthly', label: 'Monthly', hint: 'Monthly contracts expiring on the last Thursday of the month.' },
];
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
// Mirrors CURATED_STOCKS in backend universe.py — the quick-pick liquid F&O names.
const CURATED_STOCKS = [
  'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'INFY', 'TCS', 'SBIN', 'AXISBANK', 'KOTAKBANK',
  'ITC', 'LT', 'BHARTIARTL', 'HINDUNILVR', 'BAJFINANCE', 'MARUTI', 'TATAMOTORS',
  'SUNPHARMA', 'WIPRO', 'TATASTEEL',
];
const ALL_FNO_APPROX = 190; // ≈ count of all F&O stocks, for the cost estimate only

function fmtTime(charts: number): string {
  const secs = Math.round(charts / 3); // ~3 historical req/s
  return secs < 90 ? `~${secs}s` : `~${Math.round(secs / 60)} min`;
}

// Simple scan-cost readout from the current selection. Spot = one fetch per
// instrument; derivatives = one per contract (CE+PE per selected strike).
function scanCost(cfg: EngineConfigModel): string {
  const stockCount = cfg.scan_all_stocks ? ALL_FNO_APPROX : cfg.scan_stocks.length;
  const instruments = cfg.scan_indices.length + stockCount;
  const charts = instruments * Math.max(1, cfg.strike_moneyness.length) * 2;
  if (cfg.scan_source === 'spot') return `≈ ${instruments} instruments · ${fmtTime(instruments)}/scan`;
  if (cfg.scan_source === 'derivatives') return `≈ ${charts.toLocaleString('en-IN')} option charts · ${fmtTime(charts)}/scan`;
  return `spot ${fmtTime(instruments)} · deriv ${fmtTime(charts)} (${charts.toLocaleString('en-IN')} charts)/scan`;
}

function timeAgo(ms: number): string {
  if (!ms) return 'never';
  const s = Math.round((Date.now() - ms) / 1000);
  if (s < 60) return `${s}s ago`;
  return `${Math.floor(s / 60)}m ago`;
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

function SignalCard({ row, onClick, onSelectSignal, quotes, viewLayout, sort }: {
  row: EngineSignalRow; onClick: () => void;
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number }) => void;
  quotes?: any;
  viewLayout: 'grid' | 'list';
  sort: { key: string; dir: string };
}) {
  const s = useKiteSettings();
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const bull = row.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  // Derivatives rows: the SuperTrend ran on this contract's OWN premium chart, so
  // the contract is the headline and spot/stop_loss are premium values.
  const isDeriv = row.source === 'derivatives';
  const derivLeg = isDeriv ? row.legs[0] : undefined;

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

  return (
    <div
      className="st-parent-row"
      style={{ padding: '10px 12px', borderBottom: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <div 
        className="st-parent-header" 
        onClick={onClick}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', position: 'relative', margin: '-10px -12px', padding: '10px 12px' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = k.surfaceHover)}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', overflow: 'hidden', minWidth: 0 }}>
          {isDeriv ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
                <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: 0.4, color: k.orange, border: `1px solid ${tint(k.orange, 40)}`, background: tint(k.orange, 10), borderRadius: 4, padding: '1px 4px', flexShrink: 0 }}>DERIV</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: uColor }}>{row.underlying}</span>
              </span>
            </div>
          ) : (
            <>
              <span style={{ fontSize: 13, fontWeight: 600, color: uColor }}>{row.underlying}</span>

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
          {row.is_active
            ? <span title="SuperTrend still aligned on the latest 1H bar — trade running"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 600, color: k.green }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: k.green }} />running</span>
            : <span title="The entry's SuperTrend has since flipped — shown for history, not a live entry"
                    style={{ fontSize: 10, color: k.dim }}>trend ended</span>}
          {!isDeriv && <span style={{ fontSize: 11, color: k.dim }}>SL {row.stop_loss.toFixed(1)}</span>}
          <span style={{ color: k.dim, fontSize: 11, fontWeight: 600 }}>· {row.option_type}</span>
          <span style={{ fontSize: 10, color: k.text, paddingLeft: 4, opacity: 0.8 }}>
            {`${new Date(row.timestamp_ms).toLocaleDateString('en-US', { weekday: 'short' })} ${new Date(row.timestamp_ms).toLocaleDateString('en-US', { month: 'short' }).toUpperCase()} ${new Date(row.timestamp_ms).toLocaleDateString('en-US', { day: '2-digit' })} ${new Date(row.timestamp_ms).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`}
          </span>
        </span>
        
      </div>

      {/* option legs */}
      {isDeriv && viewLayout === 'grid' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '12px 16px', borderTop: `1px solid ${k.border}` }}>
          {row.legs.map((leg) => {
            const sym = `${row.exchange}:${leg.option_symbol}`;
            const q = quotes?.[sym];
            const lastPx = q?.last_price || (leg as any).premium_spot;
            const slPx = (leg as any).premium_sl;
            const isExp = expanded.has(leg.option_symbol);
            return (
              <div key={leg.option_symbol} style={{ minWidth: 105 }}>
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
                    <span style={{ fontSize: 10, color: k.orange, fontWeight: 700 }}>{leg.moneyness}</span>
                    <span style={{ fontSize: 12, color: accent, fontWeight: 600 }}>{lastPx != null ? lastPx.toFixed(2) : '—'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontSize: 10, color: k.dim, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 70 }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                    {slPx != null && <span style={{ fontSize: 10, color: k.dim }}>SL {slPx.toFixed(1)}</span>}
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
        {row.legs.length === 0 ? (
          <span style={{ fontSize: 10, color: k.dim }}>no liquid contract at the selected strikes</span>
        ) : (
          <React.Fragment>
            {[...row.legs].sort((a, b) => {
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

          return (
            <div key={leg.option_symbol}>
              <div 
                className="st-leg-row" 
                onClick={(e) => toggleExpand(e, leg.option_symbol)}
                style={{ cursor: 'pointer', background: isExp ? k.surfaceHover : 'transparent' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0, paddingRight: 8, flex: 1 }}>
                   <span style={{ color: color, fontWeight: 400, fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                   {s.showExchange && (
                     <span style={{ fontSize: 11, color: k.dim, width: 40, flexShrink: 0 }}>
                       {row.exchange}
                     </span>
                   )}
                   {s.showLeg && (
                     <span style={{ fontSize: 11, color: k.dim, width: 45, flexShrink: 0 }}>
                       {leg.moneyness}
                     </span>
                   )}
                   {isDeriv && (
                     <span style={{ fontSize: 11, fontWeight: 500, color: (leg as any).premium_spot != null ? accent : k.dim, width: 70, textAlign: 'right', flexShrink: 0 }}>
                       {(leg as any).premium_spot != null ? (leg as any).premium_spot.toFixed(2) : '—'}
                     </span>
                   )}
                   {isDeriv && (
                     <span style={{ fontSize: 10, color: k.dim, width: 70, textAlign: 'right', flexShrink: 0 }}>
                       {(leg as any).premium_sl != null ? (leg as any).premium_sl.toFixed(1) : '—'}
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
                      onMore={(e) => { e.stopPropagation(); }}
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

// Status line + live "time to next scan" bar. Ticks on its own 1s interval so
// the rest of the pane (and the signal list) don't re-render every second.
function ScanStatus({ signals }: { signals?: SignalsResponse }) {
  const [, tick] = React.useReducer((x) => x + 1, 0);
  React.useEffect(() => { const id = setInterval(tick, 1000); return () => clearInterval(id); }, []);

  const scanning = signals?.scanning ?? false;
  const auto = signals?.auto_scan ?? false;
  const gen = signals?.generated_ms ?? 0;
  const next = signals?.next_scan_ms ?? 0;
  const interval = next - gen;
  const frac = interval > 0 ? Math.min(1, Math.max(0, (Date.now() - gen) / interval)) : 0;
  const dotColor = scanning ? k.green : auto ? k.blue : k.dim;

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 11, color: k.dim, fontVariantNumeric: 'tabular-nums' }}>
        <span className={scanning ? 'st-pulse' : undefined} style={{ width: 7, height: 7, borderRadius: 4, background: dotColor, flexShrink: 0 }} />
        <span style={{ color: scanning ? k.green : auto ? k.text : k.dim, fontWeight: 500 }}>
          {scanning ? 'scanning…' : auto ? 'auto-scan on' : 'manual'}
        </span>
        {!scanning && gen > 0 && <span>· last {timeAgo(gen)}</span>}
        {!scanning && auto && next > 0 && <span>· next {countdown(next)}</span>}
      </div>
      {/* live countdown — doubles as the header divider */}
      <div style={{ height: 2, background: k.border, position: 'relative', overflow: 'hidden', marginTop: 9, marginLeft: -16, marginRight: -16 }}>
        {scanning
          ? <div className="st-scan-bar" />
          : auto && interval > 0
            ? <div key={gen} style={{ height: '100%', width: `${frac * 100}%`, background: k.orange, transition: 'width 1s linear' }} />
            : null}
      </div>
    </>
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

export function TripleSupertrendPane({ onSelectSignal }: Props) {
  const s = useKiteSettings();
  const { data: signals } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
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
  const [settingsOpen, setSettingsOpen] = React.useState<boolean>(() => localStorage.getItem('kite_st_settings_open') === 'true');
  const [viewLayout, setViewLayout] = React.useState<'grid' | 'list'>(() => (localStorage.getItem('kite_st_view_layout') as 'grid' | 'list') || 'grid');
  const legSort = s.legSort;
  const setLegSort = s.setLegSort;
  const handleLegSort = (key: string) => {
    setLegSort(legSort.key === key ? { key, dir: legSort.dir === 'asc' ? 'desc' : legSort.dir === 'desc' ? '' : 'asc' } : { key, dir: 'asc' });
  };

  React.useEffect(() => { localStorage.setItem('kite_st_settings_open', String(settingsOpen)); }, [settingsOpen]);
  React.useEffect(() => { localStorage.setItem('kite_st_view_layout', viewLayout); }, [viewLayout]);

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

  const toggleExpiry = (e: ScanExpiry) => {
    if (!cfg) return;
    const has = cfg.scan_expiries.includes(e);
    const next = has ? cfg.scan_expiries.filter((x) => x !== e) : [...cfg.scan_expiries, e];
    const finalNext = next.length ? next : ['weekly', 'monthly'];
    patch({ scan_expiries: finalNext as ScanExpiry[] }, `Expiries updated to ${finalNext.join(', ')}`);
  };

  // Changing the scan source must re-scan immediately — otherwise the list keeps
  // showing the previous scan's rows (e.g. spot signals) until the 5-min auto-loop
  // runs, which reads as "I switched to derivatives but nothing changed".
  const changeScanSource = (v: ScanSource) => {
    if (!cfg || cfg.scan_source === v) return;
    // Auto-rescan so the switch takes effect now — EXCEPT the heavy case (derivatives
    // over All F&O ≈ thousands of charts / many minutes), which would block the scan
    // request; there the user should narrow the universe to indices first.
    const heavy = (v === 'derivatives' || v === 'both') && cfg.scan_all_stocks;
    setCfg.mutate({ ...cfg, scan_source: v }, { 
      onSuccess: () => { 
        notifyOrder({ kind: 'info', title: 'Settings updated', message: `Scan source changed to ${v}` });
        if (!heavy) doScan(); 
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

  const rows = signals?.rows ?? [];
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

  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(new Set());
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
    const active = sorted.filter((r) => r.is_active);
    const history = sorted.filter((r) => !r.is_active);
    if (active.length) buckets.push({ label: 'Active now', rows: active, active: true });

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
    return buckets;
  }, [filteredRows]);
  const scanning = signals?.scanning;

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg, fontFamily: k.fontFamily }}>
      {/* ── Console header ── */}
      <div style={{ padding: '12px 16px 0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
            <EngineMark />
            <span title={UNIVERSE_TIP} style={{ fontSize: 14, fontWeight: 600, color: k.text, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Triple SuperTrend
            </span>
            <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: 0.4, color: k.dim, border: `1px solid ${k.border}`, borderRadius: 4, padding: '1px 5px', flexShrink: 0 }}>1H</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <ReadyPill count={rows.filter((r) => r.is_active).length} />
            {scanning && (
              <HeaderIconBtn title="Stop scanning" onClick={() => cancelScan.mutate()} disabled={cancelScan.isPending}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" /></svg>
              </HeaderIconBtn>
            )}
            <HeaderIconBtn title={scan.isPending || scanning ? 'Scanning…' : 'Re-scan now'} disabled={scan.isPending || scanning} onClick={() => doScan()}>
              <RefreshIcon spinning={scan.isPending || scanning} />
            </HeaderIconBtn>
            <HeaderIconBtn title="Scan report — per-contract trace" active={reportOpen} onClick={() => setReportOpen((v) => !v)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
                <line x1="10" y1="9" x2="8" y2="9"/>
              </svg>
            </HeaderIconBtn>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <HeaderIconBtn title="Grid Layout" active={viewLayout === 'grid'} onClick={() => setViewLayout('grid')} disabled={false}>
                <GridIcon />
              </HeaderIconBtn>
              <HeaderIconBtn title="List Layout" active={viewLayout === 'list'} onClick={() => setViewLayout('list')} disabled={false}>
                <ListIcon />
              </HeaderIconBtn>
            </div>

            <HeaderIconBtn title="Engine settings" active={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}>
              <Icons.Settings />
            </HeaderIconBtn>
          </div>
        </div>
        <ScanStatus signals={signals} />
      </div>

      {/* ── Scan report drawer ── */}
      <div className="st-drawer" style={{ display: 'grid', gridTemplateRows: reportOpen ? '1fr' : '0fr' }}>
        <div style={{ overflow: 'hidden' }}>
          <ScanReportView data={scanReport} />
        </div>
      </div>

      {rows.length > 0 && (
        <div style={{ position: 'sticky', top: 0, zIndex: 10, background: k.bg }}>
          <KiteSearchBar 
            query={query} 
            setQuery={setQuery} 
            searchSettingsOpen={searchSettingsOpen} 
            setSearchSettingsOpen={setSearchSettingsOpen} 
          />
          {viewLayout === 'list' && (
            <div style={{ 
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 32,
              padding: '12px 16px', fontSize: 12, fontWeight: 400, color: k.dim, borderBottom: `1px solid ${k.border}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, minWidth: 0, paddingRight: 8, flex: 1 }}>
                 <SortHeaderDiv label="Instrument" sortKey="instrument" sort={legSort} handleSort={handleLegSort} style={{ flex: 1 }} />
                 {s.showExchange && <SortHeaderDiv label="Exc." sortKey="exc" sort={legSort} handleSort={handleLegSort} style={{ width: 40, flexShrink: 0 }} />}
                 {s.showLeg && <SortHeaderDiv label="Leg" sortKey="leg" sort={legSort} handleSort={handleLegSort} style={{ width: 45, flexShrink: 0 }} />}
                 {cfg?.scan_source !== 'spot' && <SortHeaderDiv label="Entry" sortKey="entry" sort={legSort} handleSort={handleLegSort} style={{ width: 70, flexShrink: 0 }} align="right" />}
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
          padding: 12px 16px;
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
      <div className="st-drawer" style={{ display: 'grid', gridTemplateRows: settingsOpen ? '1fr' : '0fr' }}>
        <div style={{ overflow: 'hidden' }}>
          <div style={{ padding: '13px 16px 14px', display: 'flex', flexDirection: 'column', gap: 12, borderBottom: `1px solid ${k.border}` }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
              <span style={{ fontSize: 11, color: k.dim }} title="Where the SuperTrend runs: the underlying's chart (Spot), each contract's own premium chart (Derivatives), or both.">Scan source</span>
              <Segmented
                options={SCAN_SOURCE_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg?.scan_source ?? 'derivatives') === v}
                onSelect={(v) => changeScanSource(v as ScanSource)}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
              <span style={{ fontSize: 11, color: k.dim }} title="How tightly the position is trailed before exit.">Exit trailing</span>
              <Segmented
                options={TRAIL_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg?.trail_target ?? 'mid') === v}
                onSelect={(v) => patch({ trail_target: v as TrailTarget }, `Exit trailing changed to ${v}`)}
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
              <span style={{ fontSize: 11, color: k.dim }} title="Which strikes to resolve per signal — in-the-money (ITM), at-the-money (ATM) or out-of-the-money (OTM). Select one or more.">Strikes</span>
              <Segmented
                options={MONEY_OPTS.map((o) => ({ value: o.value, label: o.value, hint: o.hint }))}
                isActive={(v) => cfg?.strike_moneyness.includes(v as Moneyness) ?? false}
                onSelect={(v) => toggleMoneyness(v as Moneyness)}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
              <span style={{ fontSize: 11, color: k.dim }} title="Filter option contracts by expiry type — weekly (every Thursday), monthly (last Thursday of the month), or both.">Expiries</span>
              <Segmented
                options={EXPIRY_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => cfg?.scan_expiries.includes(v as ScanExpiry) ?? false}
                onSelect={(v) => toggleExpiry(v as ScanExpiry)}
              />
            </div>

            {cfg && (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 7 }}>
                <span style={{ fontSize: 11, color: k.dim }} title="Pick exactly which indices and stocks to scan. Applies to both Spot and Derivatives.">Universe</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
                  <span style={{ fontSize: 9.5, color: k.dim, minWidth: 42 }}>Indices</span>
                  {INDEX_OPTS.map((o) => (
                    <Chip key={o.name} label={o.label} active={cfg.scan_indices.includes(o.name)} onClick={() => toggleIndex(o.name)} />
                  ))}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, alignItems: 'center' }}>
                  <span style={{ fontSize: 9.5, color: k.dim, minWidth: 42 }}>Stocks</span>
                  <Chip label="All F&O" active={cfg.scan_all_stocks} onClick={() => patch({ scan_all_stocks: !cfg.scan_all_stocks }, `Universe set to ${!cfg.scan_all_stocks ? 'All F&O' : 'Custom selection'}`)} />
                  {CURATED_STOCKS.map((nm) => (
                    <Chip key={nm} label={nm} active={!cfg.scan_all_stocks && cfg.scan_stocks.includes(nm)}
                      dim={cfg.scan_all_stocks} onClick={() => { if (!cfg.scan_all_stocks) toggleStock(nm); }} />
                  ))}
                </div>
                {(() => {
                  const heavy = cfg.scan_all_stocks && cfg.scan_source !== 'spot';
                  return (
                    <span style={{ fontSize: 10, color: heavy ? k.amber : k.dim, lineHeight: 1.5, display: 'flex', alignItems: 'baseline', gap: 5 }}>
                      <span style={{ flexShrink: 0 }}>ℹ</span>
                      <span>{scanCost(cfg)}{heavy ? ' — heavy (minutes). Turn off “All F&O” for a fast indices-only scan.' : ''}</span>
                    </span>
                  );
                })()}
              </div>
            )}

            <div style={{ height: 1, background: k.border, margin: '1px 0' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
              <Switch on={cfg?.early_lock ?? false} color={k.blue} label="Lock profits early" onChange={() => patch({ early_lock: !(cfg?.early_lock ?? false) }, `Early lock turned ${!(cfg?.early_lock ?? false) ? 'ON' : 'OFF'}`)} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <span style={{ fontSize: 11.5, color: k.text, fontWeight: 500 }}>Lock profits early</span>
                <span style={{ fontSize: 10, color: k.dim }}>Exit on a slow-SuperTrend flip once comfortably in profit.</span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 7, border: `1px solid ${cfg?.auto_execute ? tint(k.orange, 40) : k.border}`, background: cfg?.auto_execute ? tint(k.orange, 8) : k.surface, transition: 'background .18s ease, border-color .18s ease' }}>
              <Switch on={cfg?.auto_execute ?? false} color={k.orange} label="Auto-execute" onChange={toggleAuto} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: cfg?.auto_execute ? k.orange : k.text, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <ZapIcon /> Auto-execute {cfg?.auto_execute ? 'ON' : 'OFF'}
                </span>
                <span style={{ fontSize: 10, color: k.dim }}>Places real option BUY orders on ready signals (live-safety gated).</span>
              </div>
            </div>

            {/* Kite-only PAPER ↔ LIVE — independent of the global (crypto/Delta) toggle. */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '9px 11px', borderRadius: 7, border: `1px solid ${kiteLive ? tint(k.green, 45) : k.border}`, background: kiteLive ? tint(k.green, 8) : k.surface, transition: 'background .18s ease, border-color .18s ease' }}>
              <Switch on={kiteLive} color={k.green} label="Kite live trading" onChange={toggleKiteLive} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 1, flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: kiteLive ? k.green : k.text, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <span style={{ width: 7, height: 7, borderRadius: 4, background: kiteLive ? k.green : k.amber, flexShrink: 0 }} /> Kite {kiteLive ? 'LIVE' : 'PAPER'}
                </span>
                <span style={{ fontSize: 10, color: k.dim }}>
                  {kiteLive
                    ? 'Orders execute on your real Zerodha account. Separate from the crypto (Delta) toggle.'
                    : 'Simulated — no real money. Controls Kite only, not crypto (Delta).'}
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.55 }}>
                Scanning <span style={{ color: k.text, fontWeight: 500 }}>Nifty50 · BankNifty · FinNifty · Sensex</span> stocks + index options on the <span style={{ color: k.text, fontWeight: 500 }}>1H</span> timeframe.
              </div>
              <HeaderIconBtn title="Reset to defaults" disabled={resetCfg.isPending} onClick={() => resetCfg.mutate()}>
                <span style={{ display: 'flex', width: 15, height: 15, color: 'inherit' }}>
                  <Icons.Reload />
                </span>
              </HeaderIconBtn>
            </div>
          </div>
        </div>
      </div>

      {/* Signal list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {groupedRows.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            {scanning ? `Scanning ${signals?.scanning_label || '…'}` : 'No ready setups right now. The engine re-scans automatically.'}
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
                  <div>
                    {group.rows.map((row) => (
                      <SignalCard key={`${row.token}:${row.option_type}:${row.timestamp_ms}`} row={row} quotes={quotes} viewLayout={viewLayout}
                        onSelectSignal={onSelectSignal} sort={legSort}
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

export default TripleSupertrendPane;

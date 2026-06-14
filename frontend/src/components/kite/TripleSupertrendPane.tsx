import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useSetEngineConfig,
} from '../../hooks/useTripleSupertrend';
import type {
  AlignmentChip, EngineConfigModel, EngineSignalRow, Moneyness, SignalsResponse, TrailTarget,
} from '../../types/kiteEngine';
import { useKiteQuote, useKiteAccounts, useUpdateKiteAccount } from '../../hooks/useKite';
import { InstrumentLabel } from './InstrumentLabel';
import { Icons } from '../../styles/kiteUI';
import { QuoteDetail, KiteSearchBar } from './MarketWatchPane';
import { KiteActionButtons } from './KiteActionButtons';
import { useKiteSettings } from '../../store/useKiteSettings';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';


interface Props {
  onSelectSignal: (sel: { token: number; underlying: string }) => void;
}

// Plain-language labels (users were confused by fast/mid/slow + "early lock").
const TRAIL_OPTS: { value: TrailTarget; label: string; hint: string }[] = [
  { value: 'fast', label: 'Tight', hint: 'Exit quickly — trails the fast SuperTrend (21,1). Locks gains sooner, more whipsaw.' },
  { value: 'mid', label: 'Balanced', hint: 'Default — trails the mid SuperTrend (14,2). Balanced hold vs. protection.' },
  { value: 'slow', label: 'Loose', hint: 'Hold longer — trails the slow SuperTrend (7,3). Rides trends further, gives back more.' },
];
const MONEY_OPTS: { value: Moneyness; hint: string }[] = [
  { value: 'ATM', hint: 'At-the-money — strike nearest spot.' },
  { value: 'ITM1', hint: 'One strike in-the-money.' },
  { value: 'ITM2', hint: 'Two strikes in-the-money.' },
];

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

function SignalCard({ row, onClick, quotes }: { row: EngineSignalRow; onClick: () => void; quotes?: any }) {
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());
  const s = useKiteSettings();
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);
  const bull = row.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  
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
  let uColor = k.dim;

  if (uQ) {
    uLastPx = uQ.last_price;
    const base = s.chgType === 'close' ? uQ.ohlc?.close : uQ.ohlc?.open;
    if (base) {
      uChgAbs = uQ.last_price - base;
      uChgPct = (uChgAbs / base) * 100;
      uColor = s.showPriceDirection ? (uChgAbs >= 0 ? k.green : k.red) : k.dim;
    } else if (uQ.net_change != null) {
      uChgPct = uQ.net_change;
      uColor = s.showPriceDirection ? (uChgPct >= 0 ? k.green : k.red) : k.dim;
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, whiteSpace: 'nowrap', overflow: 'hidden' }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: k.text }}>{row.underlying}</span>
          
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
        </div>

        <span className="st-prices-parent" style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <AlignmentChips a={row.alignment} />
          <span style={{ fontSize: 11, color: k.dim }}>SL {row.stop_loss.toFixed(1)}</span>
          <span style={{ color: k.dim, fontSize: 11, fontWeight: 600 }}>· {row.option_type}</span>
        </span>
      </div>

      {expanded.has(row.underlying) && uQ && (
        <div onClick={(e) => e.stopPropagation()}>
          <QuoteDetail sym={`${uExch}:${uSym}`} q={uQ} spotName={row.underlying} spotPx={row.spot} instrumentName={row.underlying} />
        </div>
      )}

      {/* option legs */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {row.legs.length === 0 ? (
          <span style={{ fontSize: 10, color: k.dim }}>no liquid ATM/ITM contract</span>
        ) : row.legs.map((leg) => {
          const sym = `${row.exchange}:${leg.option_symbol}`;
          const q = quotes?.[sym];
          
          let chgAbs = null;
          let chgPct = null;
          let lastPx = null;
          let color = k.dim;
          
          if (q) {
            lastPx = q.last_price;
            const base = s.chgType === 'close' ? q.ohlc?.close : q.ohlc?.open;
            if (base) {
              chgAbs = q.last_price - base;
              chgPct = (chgAbs / base) * 100;
              color = s.showPriceDirection ? (chgAbs >= 0 ? k.green : k.red) : k.dim;
            } else if (q.net_change != null) {
              chgPct = q.net_change;
              color = s.showPriceDirection ? (chgPct >= 0 ? k.green : k.red) : k.dim;
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, paddingRight: 8, flex: 1 }}>
                   <span style={{ fontSize: 10, color: k.orange, fontWeight: 700, minWidth: 28 }}>{leg.moneyness}</span>
                   <span style={{ color: color, fontWeight: 400, fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={leg.option_symbol} /></span>
                   <span style={{ fontSize: 9, color: k.dim, flexShrink: 0 }}>{row.exchange}</span>
                </div>

                {!isExp && (
                  <KiteActionButtons
                    className="st-actions"
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
                    onDepth={(e) => { e.stopPropagation(); toggleExpand(e, leg.option_symbol); }}
                    onChart={(e) => { e.stopPropagation(); }}
                    onMore={(e) => { e.stopPropagation(); }}
                  />
                )}
                
                {!isExp && (
                  <div className="st-prices">
                    {s.showPriceChange && <span style={{ color: k.dim, fontSize: 11 }}>{chgAbs != null ? chgAbs.toFixed(2) : '—'}</span>}
                    {s.showPriceChangePct && <span style={{ color: k.text, fontSize: 11, marginLeft: 4 }}>{chgPct != null ? `${chgPct.toFixed(2)}%` : '—'}</span>}
                    {s.showPriceDirection && (
                      <span style={{ color: color, display: 'flex', alignItems: 'center', marginTop: 1, margin: '0 2px' }}>
                        {chgAbs != null && chgAbs !== 0 ? (chgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                        {chgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                      </span>
                    )}
                    <span style={{ color: color, fontWeight: 500, fontSize: 12, minWidth: 50, textAlign: 'right' }}>
                      {lastPx != null ? lastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                    </span>
                  </div>
                )}
              </div>
              {isExp && (
                <div onClick={(e) => e.stopPropagation()}>
                  <QuoteDetail sym={sym} q={q} expiry={leg.expiry} spotName={row.underlying} spotPx={row.spot} instrumentName={<InstrumentLabel symbol={leg.option_symbol} />} />
                </div>
              )}
            </div>
          );
        })}
      </div>
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
      {count} ready
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

export function TripleSupertrendPane({ onSelectSignal }: Props) {
  const { data: signals } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
  const setCfg = useSetEngineConfig();
  const scan = useRunScan();
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
  React.useEffect(() => { localStorage.setItem('kite_st_settings_open', String(settingsOpen)); }, [settingsOpen]);

  const patch = (p: Partial<EngineConfigModel>) => { if (cfg) setCfg.mutate({ ...cfg, ...p }); };

  const toggleMoneyness = (m: Moneyness) => {
    if (!cfg) return;
    const has = cfg.strike_moneyness.includes(m);
    const next = has ? cfg.strike_moneyness.filter((x) => x !== m) : [...cfg.strike_moneyness, m];
    patch({ strike_moneyness: next.length ? next : ['ATM', 'ITM1', 'ITM2'] });
  };

  const toggleAuto = () => {
    if (!cfg) return;
    if (!cfg.auto_execute) {
      const ok = window.confirm('Enable AUTO-EXECUTE? Ready signals will place real ATM/ITM option BUY orders on your active Kite account (under the live-safety gate). Continue?');
      if (!ok) return;
    }
    patch({ auto_execute: !cfg.auto_execute });
  };

  // Kite paper↔live. Arming (→LIVE) confirms — it routes real orders to Zerodha;
  // de-arming (→PAPER) is immediate. Crypto/Delta is untouched (separate toggle).
  const toggleKiteLive = () => {
    if (!activeAcct) { window.alert('No active Kite account. Add one on the Connect page first.'); return; }
    if (activeAcct.is_paper) {
      if (!activeAcct.has_credentials) {
        window.alert('Add your Kite API key & secret on the Connect page before trading live.');
        return;
      }
      const ok = window.confirm(`Switch Kite to LIVE trading? Orders will execute on your REAL Zerodha account (${activeAcct.label}). Crypto stays on its own toggle.`);
      if (!ok) return;
      updateAcct.mutate({ id: activeAcct.id, is_paper: false });
    } else {
      updateAcct.mutate({ id: activeAcct.id, is_paper: true });
    }
  };

  const rows = signals?.rows ?? [];
  const filteredRows = React.useMemo(() => {
    let result = [...rows];
    if (query.trim()) {
      const qLower = query.toLowerCase();
      result = result.filter(r => r.underlying.toLowerCase().includes(qLower));
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
      <div style={{ position: 'sticky', top: 0, zIndex: 10 }}>
        <KiteSearchBar 
          query={query} 
          setQuery={setQuery} 
          searchSettingsOpen={searchSettingsOpen} 
          setSearchSettingsOpen={setSearchSettingsOpen} 
        />
      </div>
      <style>{`
        .st-parent-row {
          position: relative;
        }

        .st-leg-row {
          position: relative;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
          border-top: 1px solid ${k.border};
          margin-top: 4px;
        }
        .st-actions {
          display: none;
          gap: 8px;
          align-items: center;
          position: absolute;
          right: 0;
          top: 50%;
          transform: translateY(-50%);
          background: ${k.surfaceHover};
          padding-left: 8px;
        }
        .st-leg-row:hover .st-actions {
          display: flex;
        }
        .st-leg-row:hover .st-prices {
          visibility: hidden;
        }
        .st-prices {
          display: flex;
          align-items: center;
          gap: 2px;
          flex-shrink: 0;
          justify-content: flex-end;
        }
        .st-leg-row:hover .st-prices {
          visibility: hidden;
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
            <ReadyPill count={rows.length} />
            <HeaderIconBtn title={scan.isPending || scanning ? 'Scanning…' : 'Re-scan now'} disabled={scan.isPending || scanning} onClick={() => scan.mutate()}>
              <RefreshIcon spinning={scan.isPending || scanning} />
            </HeaderIconBtn>
            <HeaderIconBtn title="Engine settings" active={settingsOpen} onClick={() => setSettingsOpen((v) => !v)}>
              <Icons.Settings />
            </HeaderIconBtn>
          </div>
        </div>
        <ScanStatus signals={signals} />
      </div>

      {/* ── Settings drawer (collapsible) ── */}
      <div className="st-drawer" style={{ display: 'grid', gridTemplateRows: settingsOpen ? '1fr' : '0fr' }}>
        <div style={{ overflow: 'hidden' }}>
          <div style={{ padding: '13px 16px 14px', display: 'flex', flexDirection: 'column', gap: 12, borderBottom: `1px solid ${k.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 11, color: k.dim, minWidth: 92 }} title="How tightly the position is trailed before exit.">Exit trailing</span>
              <Segmented
                options={TRAIL_OPTS.map((o) => ({ value: o.value, label: o.label, hint: o.hint }))}
                isActive={(v) => (cfg?.trail_target ?? 'mid') === v}
                onSelect={(v) => patch({ trail_target: v as TrailTarget })}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 11, color: k.dim, minWidth: 92 }} title="Which strikes to resolve per signal. Select one or more — never OTM.">Strikes</span>
              <Segmented
                options={MONEY_OPTS.map((o) => ({ value: o.value, label: o.value, hint: o.hint }))}
                isActive={(v) => cfg?.strike_moneyness.includes(v as Moneyness) ?? false}
                onSelect={(v) => toggleMoneyness(v as Moneyness)}
              />
            </div>

            <div style={{ height: 1, background: k.border, margin: '1px 0' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
              <Switch on={cfg?.early_lock ?? false} color={k.blue} label="Lock profits early" onChange={() => patch({ early_lock: !(cfg?.early_lock ?? false) })} />
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

            <div style={{ fontSize: 10, color: k.dim, lineHeight: 1.55 }}>
              Scanning <span style={{ color: k.text, fontWeight: 500 }}>Nifty50 · BankNifty · FinNifty · Sensex</span> stocks + index options on the <span style={{ color: k.text, fontWeight: 500 }}>1H</span> timeframe.
            </div>
          </div>
        </div>
      </div>

      {/* Signal list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {filteredRows.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim, fontSize: 12 }}>
            {scanning ? 'Scanning the universe…' : 'No ready setups right now. The engine re-scans automatically.'}
          </div>
        ) : (
          filteredRows.map((row) => (
            <SignalCard key={`${row.token}:${row.option_type}`} row={row} quotes={quotes}
              onClick={() => onSelectSignal({ token: row.token, underlying: row.underlying })} />
          ))
        )}
      </div>
    </div>
  );
}

export default TripleSupertrendPane;

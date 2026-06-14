import React from 'react';
import { k, tint } from '../../styles/kiteUI';
import {
  useEngineConfig, useEngineSignals, useRunScan, useSetEngineConfig,
} from '../../hooks/useTripleSupertrend';
import type {
  AlignmentChip, EngineConfigModel, EngineSignalRow, Moneyness, TrailTarget,
} from '../../types/kiteEngine';
import { useKiteQuote } from '../../hooks/useKite';
import { parseTradingsymbol } from '../../utils/fmt';
import { Icons } from '../../styles/kiteUI';
import { QuoteDetail, KiteSearchBar } from './MarketWatchPane';

const btnAction = { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 24, height: 24, borderRadius: 2, cursor: 'pointer', fontSize: 11, fontWeight: 600, border: 'none' };

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

function Arrow({ v }: { v: number }) {
  const flat = v === 0;
  return <span style={{ color: flat ? k.dim : v > 0 ? k.green : k.red, fontSize: 11, fontWeight: 700 }}>{flat ? '·' : v > 0 ? '▲' : '▼'}</span>;
}

function AlignmentChips({ a }: { a: AlignmentChip }) {
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
  const bull = row.regime === 'BULL';
  const accent = bull ? k.green : k.red;
  
  const toggleExpand = (e: React.MouseEvent, sym: string) => {
    e.stopPropagation();
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
    if (uQ.ohlc?.close) {
      uChgAbs = uQ.last_price - uQ.ohlc.close;
      uChgPct = (uChgAbs / uQ.ohlc.close) * 100;
      uColor = uChgAbs >= 0 ? k.green : k.red;
    } else if (uQ.net_change != null) {
      uChgPct = uQ.net_change;
      uColor = uChgPct >= 0 ? k.green : k.red;
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
            <span style={{ fontSize: 10 }}>{uChgAbs != null ? (uChgAbs > 0 ? '+' : '') + uChgAbs.toFixed(2) : ''}</span>
            <span style={{ fontSize: 10 }}>{uChgPct != null ? `(${uChgPct.toFixed(2)}%)` : ''}</span>
            <span style={{ display: 'flex', alignItems: 'center', margin: '0 -2px' }}>
              {uChgAbs != null && uChgAbs !== 0 ? (uChgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
              {uChgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
            </span>
          </span>

          <span className="st-prices-parent" style={{ display: 'flex', alignItems: 'center', gap: 6, borderLeft: `1px solid ${k.border}`, paddingLeft: 6 }}>
            <AlignmentChips a={row.alignment} />
            <span style={{ fontSize: 11, color: k.dim }}>SL {row.stop_loss.toFixed(1)}</span>
            <span style={{ color: k.dim, fontSize: 11, fontWeight: 600 }}>· {row.option_type}</span>
          </span>
        </div>

        <div className="st-actions" onClick={(e) => e.stopPropagation()}>
          <button style={{ ...btnAction, background: '#387ed1', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500 }} title="Buy">B</button>
          <button style={{ ...btnAction, background: '#ff5722', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500 }} title="Sell">S</button>
          <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} onClick={(e) => toggleExpand(e, row.underlying)} title="Market Depth"><Icons.Depth /></button>
          <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="Chart"><Icons.Chart /></button>
          <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="More"><Icons.More /></button>
        </div>
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
            if (q.ohlc?.close) {
              chgAbs = q.last_price - q.ohlc.close;
              chgPct = (chgAbs / q.ohlc.close) * 100;
              color = chgAbs >= 0 ? k.green : k.red;
            } else if (q.net_change != null) {
              chgPct = q.net_change;
              color = chgPct >= 0 ? k.green : k.red;
            }
          }
          
          const displayName = parseTradingsymbol(leg.option_symbol);
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
                   <span style={{ color: color, fontWeight: 400, fontSize: 12, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{displayName}</span>
                   <span style={{ fontSize: 9, color: k.dim, flexShrink: 0 }}>{row.exchange}</span>
                </div>

                <div className="st-actions" onClick={(e) => e.stopPropagation()}>
                  <button style={{ ...btnAction, background: '#387ed1', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500 }} title="Buy">B</button>
                  <button style={{ ...btnAction, background: '#ff5722', color: '#fff', borderRadius: 3, padding: 0, fontWeight: 500 }} title="Sell">S</button>
                  <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} onClick={(e) => toggleExpand(e, leg.option_symbol)} title="Market Depth"><Icons.Depth /></button>
                  <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="Chart"><Icons.Chart /></button>
                  <button style={{ ...btnAction, background: 'transparent', color: k.dim, padding: 4 }} title="More"><Icons.More /></button>
                </div>
                
                <div className="st-prices">
                  <span style={{ color: k.dim, fontSize: 11 }}>{chgAbs != null ? chgAbs.toFixed(2) : '—'}</span>
                  <span style={{ color: k.dim, fontSize: 11, marginLeft: 4 }}>{chgPct != null ? `${chgPct.toFixed(2)}%` : '—'}</span>
                  <span style={{ color: color, display: 'flex', alignItems: 'center', marginTop: 1, margin: '0 2px' }}>
                    {chgAbs != null && chgAbs !== 0 ? (chgAbs > 0 ? <Icons.ChevronUp /> : <Icons.ChevronDown />) : null}
                    {chgAbs === 0 && <span style={{fontSize:14, padding:'0 2px', lineHeight:1}}>∘</span>}
                  </span>
                  <span style={{ color: color, fontWeight: 500, fontSize: 12, minWidth: 50, textAlign: 'right' }}>
                    {lastPx != null ? lastPx.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                  </span>
                </div>
              </div>
              {isExp && (
                <div onClick={(e) => e.stopPropagation()}>
                  <QuoteDetail sym={sym} q={q} expiry={leg.expiry} spotName={row.underlying} spotPx={row.spot} instrumentName={displayName} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function TripleSupertrendPane({ onSelectSignal }: Props) {
  const { data: signals } = useEngineSignals();
  const { data: cfg } = useEngineConfig();
  const setCfg = useSetEngineConfig();
  const scan = useRunScan();
  const [query, setQuery] = React.useState('');
  const [searchSettingsOpen, setSearchSettingsOpen] = React.useState(false);
  const [sortBy, setSortBy] = React.useState('Custom');

  const patch = (p: Partial<EngineConfigModel>) => { if (cfg) setCfg.mutate({ ...cfg, ...p }); };

  const toggleMoneyness = (m: Moneyness) => {
    if (!cfg) return;
    const has = cfg.strike_moneyness.includes(m);
    const next = has ? cfg.strike_moneyness.filter((x) => x !== m) : [...cfg.strike_moneyness, m];
    patch({ strike_moneyness: next.length ? next : ['ATM'] });
  };

  const toggleAuto = () => {
    if (!cfg) return;
    if (!cfg.auto_execute) {
      const ok = window.confirm('Enable AUTO-EXECUTE? Ready signals will place real ATM/ITM option BUY orders on your active Kite account (under the live-safety gate). Continue?');
      if (!ok) return;
    }
    patch({ auto_execute: !cfg.auto_execute });
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
          sortBy={sortBy}
          setSortBy={setSortBy}
        />
      </div>
      <style>{`
        .st-parent-row {
          position: relative;
        }
        .st-parent-header .st-actions {
          display: none;
          gap: 4px;
          align-items: center;
          position: absolute;
          right: 12px;
          top: 50%;
          transform: translateY(-50%);
          background: ${k.surfaceHover};
          padding-left: 8px;
        }
        .st-parent-header:hover .st-actions {
          display: flex;
        }
        .st-parent-header:hover .st-prices-parent {
          visibility: hidden;
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
          gap: 4px;
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
      `}</style>
      {/* Header + live scan status */}
      <div style={{ padding: '12px 16px', borderBottom: `1px solid ${k.border}` }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: k.text }}>Triple SuperTrend</span>
          <button onClick={() => scan.mutate()} disabled={scan.isPending || scanning}
            style={{ fontSize: 11, fontWeight: 500, color: k.orange, background: 'none', border: `1px solid ${k.orange}`, borderRadius: 4, padding: '3px 10px', cursor: 'pointer', opacity: (scan.isPending || scanning) ? 0.5 : 1 }}>
            {scan.isPending || scanning ? 'Scanning…' : 'Re-scan'}
          </button>
        </div>
        {/* status line — user doesn't need to click scan; it runs automatically */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, fontSize: 10.5, color: k.dim }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 7, height: 7, borderRadius: 4, background: scanning ? k.green : signals?.auto_scan ? k.blue : k.dim }} />
            {scanning ? 'scanning…' : signals?.auto_scan ? 'auto-scan on' : 'manual'}
          </span>
          <span>·  last {timeAgo(signals?.generated_ms ?? 0)}</span>
          <span>·  next {countdown(signals?.next_scan_ms ?? 0)}</span>
          <span style={{ marginLeft: 'auto', color: k.orange }}>{rows.length} ready</span>
        </div>
        <div style={{ fontSize: 9.5, color: k.dim, marginTop: 4 }}>Nifty50 / BankNifty / FinNifty / Sensex stocks + index options · 1H</div>
      </div>

      {/* Controls */}
      <div style={{ padding: '10px 16px', borderBottom: `1px solid ${k.border}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* trail tightness */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: k.dim, minWidth: 84 }} title="How tightly the position is trailed before exit.">Exit trailing</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {TRAIL_OPTS.map((o) => {
              const active = (cfg?.trail_target ?? 'mid') === o.value;
              return (
                <button key={o.value} title={o.hint} onClick={() => patch({ trail_target: o.value })}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${active ? k.orange : k.border}`, color: active ? '#fff' : k.text, background: active ? k.orange : 'none' }}>
                  {o.label}
                </button>
              );
            })}
          </div>
        </div>
        {/* strike moneyness — multi-select chips */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: k.dim, minWidth: 84 }} title="Which strikes to resolve per signal. Select one or more — never OTM.">Strikes</span>
          <div style={{ display: 'flex', gap: 4 }}>
            {MONEY_OPTS.map((o) => {
              const active = cfg?.strike_moneyness.includes(o.value) ?? false;
              return (
                <button key={o.value} title={o.hint} onClick={() => toggleMoneyness(o.value)}
                  style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, cursor: 'pointer', border: `1px solid ${active ? k.orange : k.border}`, color: active ? '#fff' : k.text, background: active ? k.orange : 'none' }}>
                  {o.value}
                </button>
              );
            })}
          </div>
        </div>
        {/* early-lock + auto-exec */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <label title="Once a trade is comfortably in profit, also exit on a slow-SuperTrend flip to lock gains earlier." style={{ fontSize: 11, color: k.dim, display: 'flex', gap: 5, alignItems: 'center', cursor: 'pointer' }}>
            <input type="checkbox" checked={cfg?.early_lock ?? false} onChange={(e) => patch({ early_lock: e.target.checked })} />
            Lock profits early
          </label>
          <label onClick={toggleAuto} title="When on, ready signals auto-place real option BUY orders (gated by live-safety)."
            style={{ fontSize: 11, fontWeight: 600, marginLeft: 'auto', display: 'flex', gap: 5, alignItems: 'center', cursor: 'pointer', color: cfg?.auto_execute ? k.orange : k.dim, background: cfg?.auto_execute ? tint(k.orange, 10) : 'transparent', padding: '3px 8px', borderRadius: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: cfg?.auto_execute ? k.orange : k.border }} />
            Auto-exec {cfg?.auto_execute ? 'ON' : 'OFF'}
          </label>
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

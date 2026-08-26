import React, { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useConvertKitePosition,
  useKiteLtp,
  useKitePositions,
  useKiteQuote,
  useKiteWatchlist,
  usePlaceKiteOrder,
} from '../../hooks/useKite';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
import { notifyOrder } from '../../store/useKiteNotifications';
import { downloadCsv, toCsv } from '../../utils/csvExport';
import { InstrumentLabel } from './InstrumentLabel';
import { KitePortfolioAnalyticsModal } from './KitePortfolioAnalyticsModal';
import { KiteSettingsPopover } from './KiteSettingsPopover';
import { EnginePositionsPane } from './EnginePositionsPane';
import type { InstrumentTab } from './InstrumentPane';

const C = {
  text: 'var(--k-text)', muted: 'var(--k-dim)', border: '#ededed', hover: 'var(--k-surface-2)',
  blue: 'var(--k-blue-kite)', green: 'var(--k-green)', red: 'var(--k-red)',
};

const num = (v: unknown) => Number(v ?? 0);
const keyOf = (p: any) => `${p.exchange}:${p.tradingsymbol}:${p.product || ''}`;
const money = (v: number) => `${v > 0 ? '+' : ''}${v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const color = (v: number) => v > 0 ? C.green : v < 0 ? C.red : C.muted;

function ProductPill({ product }: { product: string }) {
  const style = product === 'NRML'
    ? { background: 'rgba(200,86,162,.10)', color: '#c856a2' }
    : product === 'MIS'
      ? { background: 'rgba(56,126,209,.10)', color: C.blue }
      : { background: 'var(--k-surface-hover)', color: C.muted };
  return <span style={{ ...style, padding: '2px 7px', borderRadius: 2, fontSize: 10, fontWeight: 500 }}>{product}</span>;
}

function ConvertInline({ position, onClose }: { position: any; onClose: () => void }) {
  const convert = useConvertKitePosition();
  const options = ['MIS', 'CNC', 'NRML'].filter((x) => x !== position.product);
  const max = Math.abs(num(position.quantity));
  const [qty, setQty] = useState(max);
  const [target, setTarget] = useState(options[0] || 'NRML');
  useEffect(() => setQty(max), [max]);
  const invalid = !Number.isFinite(qty) || qty < 1 || qty > max;
  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center', justifyContent: 'flex-end' }} onClick={(e) => e.stopPropagation()}>
      <input aria-label="Convert quantity" type="number" min={1} max={max} value={qty} onChange={(e) => setQty(Number(e.target.value))} style={{ width: 48, padding: '3px 5px', border: `1px solid ${C.border}`, borderRadius: 3, fontSize: 11 }} />
      <select aria-label="Convert target product" value={target} onChange={(e) => setTarget(e.target.value)} style={{ padding: '3px 5px', border: `1px solid ${C.border}`, borderRadius: 3, fontSize: 11 }}>
        {options.map((x) => <option key={x}>{x}</option>)}
      </select>
      <button type="button" disabled={invalid || convert.isPending} onClick={() => convert.mutate({ tradingsymbol: position.tradingsymbol, exchange: position.exchange, transaction_type: num(position.quantity) > 0 ? 'BUY' : 'SELL', position_type: 'day', quantity: qty, old_product: position.product, new_product: target })} style={{ border: 0, background: 'transparent', color: invalid ? 'var(--k-faint-2)' : C.blue, fontSize: 11, cursor: invalid ? 'not-allowed' : 'pointer' }}>{convert.isPending ? '…' : 'convert'}</button>
      <button type="button" title="Close" onClick={onClose} style={{ border: 0, background: 'transparent', color: C.muted, fontSize: 15, cursor: 'pointer' }}>×</button>
    </div>
  );
}

function PositionInfo({ position, onClose }: { position: any; onClose: () => void }) {
  const sym = `${position.exchange}:${position.tradingsymbol}`;
  const { data } = useKiteQuote([sym], true, 5_000, 'full');
  const q: any = data?.[sym];
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.08)', zIndex: 1200 }} />
      <div style={{ position: 'fixed', top: 90, left: '50%', transform: 'translateX(-50%)', width: 430, maxWidth: '92vw', background: 'var(--k-bg)', boxShadow: '0 10px 35px rgba(0,0,0,.25)', zIndex: 1201, borderRadius: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '14px 16px', borderBottom: `1px solid ${C.border}` }}><strong style={{ fontSize: 14 }}><InstrumentLabel symbol={position.tradingsymbol} /></strong><button onClick={onClose} style={{ border: 0, background: 'transparent', cursor: 'pointer' }}>✕</button></div>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
          <span>Product</span><b>{position.product}</b><span>Quantity</span><b>{position.quantity}</b><span>Average</span><b>{num(position.average_price).toFixed(2)}</b><span>LTP</span><b>{num(position.last_price).toFixed(2)}</b><span>P&amp;L</span><b style={{ color: color(num(position.pnl)) }}>{money(num(position.pnl))}</b><span>Open</span><b>{num(position.quantity) !== 0 ? 'Yes' : 'No'}</b>
          {q?.ohlc && <><span>Day range</span><b>{num(q.ohlc.low).toFixed(2)} – {num(q.ohlc.high).toFixed(2)}</b></>}
        </div>
      </div>
    </>
  );
}

export function PositionsPane({ onOpenInstrument }: { onOpenInstrument?: (symbol: string, tab: InstrumentTab | 'chart' | 'option-chain') => void }) {
  const { data: response } = useKitePositions(true);
  const brokerRows = response?.net ?? [];
  const symbols = useMemo(() => Array.from(new Set(brokerRows.map((p: any) => `${p.exchange}:${p.tradingsymbol}`))), [brokerRows]);
  const { data: ltp } = useKiteLtp(symbols, symbols.length > 0);
  const rows = useMemo(() => brokerRows.map((p: any) => {
    const live = num(ltp?.[`${p.exchange}:${p.tradingsymbol}`]?.last_price);
    if (live <= 0) return p;
    return { ...p, last_price: live, pnl: num(p.pnl) + (live - num(p.last_price)) * num(p.quantity) * (num(p.multiplier) || 1) };
  }), [brokerRows, ltp]);

  const openRows = useMemo(() => rows.filter((p: any) => num(p.quantity) !== 0), [rows]);
  const closedRows = useMemo(() => rows.filter((p: any) => num(p.quantity) === 0), [rows]);
  const { openOrderWindow } = useOrderWindowStore();
  const addToBasket = useKiteBasketStore((s) => s.add);
  const watch = useKiteWatchlist();
  const qc = useQueryClient();
  const place = usePlaceKiteOrder();

  const [query, setQuery] = useState('');
  const [menu, setMenu] = useState<{ key: string; top: number; left: number } | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [convertKey, setConvertKey] = useState<string | null>(null);
  const [info, setInfo] = useState<any | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [analyticsOpen, setAnalyticsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [engineOpen, setEngineOpen] = useState(false);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const close = () => setMenu(null);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, []);

  useEffect(() => {
    const live = new Set(openRows.map(keyOf));
    setSelected((current) => new Set([...current].filter((x) => live.has(x))));
    if (convertKey && !live.has(convertKey)) setConvertKey(null);
  }, [openRows, convertKey]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((p: any) => `${p.tradingsymbol} ${p.exchange} ${p.product}`.toLowerCase().includes(q)) : rows;
  }, [rows, query]);

  const openOrder = (p: any, side: 'BUY' | 'SELL', qty = Math.max(1, Math.abs(num(p.quantity)))) => openOrderWindow({ symbol: p.tradingsymbol, exchange: p.exchange, initialSide: side, initialQty: qty, lastPrice: num(p.last_price), product: p.product });
  const totalPnl = rows.reduce((sum: number, p: any) => sum + num(p.pnl), 0);
  const selectable = filtered.filter((p: any) => num(p.quantity) !== 0).map(keyOf);
  const allSelected = selectable.length > 0 && selectable.every((x) => selected.has(x));
  const toggleAll = () => setSelected((current) => {
    const next = new Set(current);
    if (allSelected) selectable.forEach((x) => next.delete(x)); else selectable.forEach((x) => next.add(x));
    return next;
  });

  const exitSelected = async () => {
    const targets = openRows.filter((p: any) => selected.has(keyOf(p)));
    if (!targets.length || !window.confirm(`Exit ${targets.length} selected position${targets.length === 1 ? '' : 's'} at market price?`)) return;
    setExiting(true);
    try {
      for (const p of targets) {
        const live = (qc.getQueryData<{ net: any[] }>(['kite-positions'])?.net ?? []).find((x: any) => keyOf(x) === keyOf(p));
        const qty = num(live?.quantity);
        if (!qty) continue;
        await place.mutateAsync({ tradingsymbol: p.tradingsymbol, exchange: p.exchange, transaction_type: qty > 0 ? 'SELL' : 'BUY', quantity: Math.abs(qty), order_type: 'MARKET', product: p.product, variety: 'regular', validity: 'DAY' });
      }
    } catch (error: any) {
      notifyOrder({ kind: 'error', title: 'Exit failed', message: error?.message || 'Unable to exit selected positions' });
    } finally {
      setExiting(false); setSelected(new Set());
    }
  };

  const menuPosition = menu ? rows.find((p: any) => keyOf(p) === menu.key) : null;
  const addToWatch = (p: any) => watch.add({ symbol: `${p.exchange}:${p.tradingsymbol}`, token: num(p.instrument_token), name: p.tradingsymbol, sub: `${p.exchange} · ${p.product} position` });
  const download = () => downloadCsv('positions.csv', toCsv(rows, [
    { header: 'Status', value: (p: any) => num(p.quantity) !== 0 ? 'OPEN' : 'CLOSED' },
    { header: 'Instrument', value: (p: any) => p.tradingsymbol }, { header: 'Exchange', value: (p: any) => p.exchange },
    { header: 'Product', value: (p: any) => p.product }, { header: 'Qty', value: (p: any) => p.quantity },
    { header: 'Avg', value: (p: any) => num(p.average_price).toFixed(2) }, { header: 'LTP', value: (p: any) => num(p.last_price).toFixed(2) },
    { header: 'P&L', value: (p: any) => num(p.pnl).toFixed(2) },
  ]));

  const th: React.CSSProperties = { padding: '10px 10px', borderBottom: `1px solid ${C.border}`, color: C.muted, fontSize: 11, fontWeight: 400, textAlign: 'left', whiteSpace: 'nowrap' };
  const td: React.CSSProperties = { padding: '9px 10px', borderBottom: `1px solid ${C.border}`, color: C.text, fontSize: 12, verticalAlign: 'middle' };

  return (
    <div style={{ padding: '18px 24px 32px', width: '100%', boxSizing: 'border-box' }}>
      <style>{`
        .pos-row:hover{background:${C.hover}} .pos-more{opacity:0}.pos-row:hover .pos-more{opacity:1}
        .pos-menu-item{padding:8px 12px;font-size:12px;display:flex;align-items:center;gap:9px;cursor:pointer;color:${C.text}}
        .pos-menu-item:hover{background:var(--k-surface-4)}.pos-menu-item.disabled{color:var(--k-faint-2);cursor:not-allowed}.pos-menu-sep{height:1px;background:${C.border};margin:4px 0}
      `}</style>
      <div style={{ maxWidth: 1120, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 400 }}>Positions <span style={{ color: C.muted }}>({rows.length})</span> <span style={{ color: C.green, fontSize: 11, marginLeft: 7 }}>{openRows.length} open</span></h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, flexWrap: 'wrap' }}>
            {selected.size > 0 && <button disabled={exiting} onClick={exitSelected} style={{ border: 0, borderRadius: 3, background: C.red, color: 'var(--k-bg)', padding: '5px 10px', fontSize: 11, cursor: exiting ? 'wait' : 'pointer' }}>{exiting ? 'Exiting…' : `Exit Selected (${selected.size})`}</button>}
            <input aria-label="Search positions" placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} style={{ width: 125, height: 27, border: `1px solid ${C.border}`, borderRadius: 3, padding: '4px 8px', fontSize: 11 }} />
            <button onClick={() => setAnalyticsOpen(true)} style={{ border: 0, background: 'transparent', color: C.blue, fontSize: 11, cursor: 'pointer' }}>Analyze</button>
            <button onClick={() => setSettingsOpen(true)} style={{ border: 0, background: 'transparent', color: C.muted, fontSize: 11, cursor: 'pointer' }}>Settings</button>
            <button onClick={download} style={{ border: 0, background: 'transparent', color: C.blue, fontSize: 11, cursor: 'pointer' }}>Download</button>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', minWidth: 790, borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <colgroup><col style={{ width: 38 }} /><col style={{ width: 76 }} /><col style={{ width: '31%' }} /><col style={{ width: 74 }} /><col style={{ width: 88 }} /><col style={{ width: 88 }} /><col style={{ width: 110 }} /><col style={{ width: 82 }} /><col style={{ width: 30 }} /></colgroup>
            <thead><tr><th style={{ ...th, textAlign: 'center' }}><input type="checkbox" aria-label="Select all open positions" checked={allSelected} onChange={toggleAll} disabled={!selectable.length} /></th><th style={th}>Product</th><th style={th}>Instrument</th><th style={{ ...th, textAlign: 'right' }}>Qty.</th><th style={{ ...th, textAlign: 'right' }}>Avg.</th><th style={{ ...th, textAlign: 'right' }}>LTP</th><th style={{ ...th, textAlign: 'right', background: 'var(--k-surface-5)' }}>P&amp;L</th><th style={{ ...th, textAlign: 'right' }}>Chg.</th><th style={th} /></tr></thead>
            <tbody>{filtered.map((p: any) => {
              const qty = num(p.quantity); const open = qty !== 0; const k = keyOf(p); const selectedRow = selected.has(k);
              const chg = open && num(p.average_price) > 0 ? (num(p.last_price) - num(p.average_price)) / num(p.average_price) * 100 : 0;
              return <tr key={k} className="pos-row" style={{ background: selectedRow ? 'rgba(56,126,209,.05)' : undefined, opacity: open ? 1 : .82 }}>
                <td style={{ ...td, textAlign: 'center' }}><input type="checkbox" aria-label={`Select ${p.tradingsymbol} ${p.product}`} checked={selectedRow} disabled={!open} onChange={() => setSelected((current) => { const next = new Set(current); next.has(k) ? next.delete(k) : next.add(k); return next; })} title={!open ? 'Closed position' : undefined} /></td>
                <td style={td}><ProductPill product={p.product} /></td>
                <td style={{ ...td, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={p.tradingsymbol} /><span style={{ marginLeft: 6, fontSize: 9, color: C.muted, background: 'var(--k-surface-hover)', padding: '1px 4px', borderRadius: 2 }}>{p.exchange}</span>{!open && <span style={{ marginLeft: 6, fontSize: 9, color: C.muted }}>CLOSED</span>}</td>
                <td style={{ ...td, textAlign: 'right', color: open ? C.blue : C.muted }}>{qty}</td><td style={{ ...td, textAlign: 'right' }}>{num(p.average_price).toFixed(2)}</td><td style={{ ...td, textAlign: 'right' }}>{num(p.last_price).toFixed(2)}</td>
                <td style={{ ...td, textAlign: 'right', color: color(num(p.pnl)), background: 'var(--k-surface-5)' }}>{money(num(p.pnl))}</td>
                <td style={{ ...td, textAlign: 'right', color: color(chg) }}>{convertKey === k ? <ConvertInline position={p} onClose={() => setConvertKey(null)} /> : `${chg.toFixed(2)}%`}</td>
                <td style={{ ...td, textAlign: 'center', paddingLeft: 0, paddingRight: 0 }}>{open && <button className="pos-more" aria-label={`More actions for ${p.tradingsymbol}`} title="More" onClick={(e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); setMenu({ key: k, top: r.bottom + 3, left: Math.max(8, r.right - 190) }); }} style={{ border: 0, background: 'transparent', color: C.muted, cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>⋮</button>}</td>
              </tr>;
            })}</tbody>
            <tfoot><tr><td colSpan={6} style={{ ...td, borderTop: `1px solid ${C.border}`, borderBottom: 0, textAlign: 'right' }}>Total P&amp;L</td><td style={{ ...td, borderTop: `1px solid ${C.border}`, borderBottom: 0, textAlign: 'right', color: color(totalPnl), background: 'var(--k-surface-5)', fontSize: 14 }}>{money(totalPnl)}</td><td colSpan={2} /></tr></tfoot>
          </table>
        </div>

        <div style={{ marginTop: 18, borderTop: `1px solid ${C.border}` }}><button onClick={() => setHistoryOpen((x) => !x)} style={{ width: '100%', padding: '13px 0', border: 0, background: 'transparent', textAlign: 'left', cursor: 'pointer', color: C.text, fontSize: 12 }}>Day&apos;s history {historyOpen ? '⌃' : '⌄'}</button>{historyOpen && <div style={{ color: C.muted, fontSize: 11, paddingBottom: 14 }}>{closedRows.length} closed position{closedRows.length === 1 ? '' : 's'} with realised P&amp;L are included in the table. Only the {openRows.length} non-zero quantity row{openRows.length === 1 ? '' : 's'} are open.</div>}</div>
        <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 18 }}><h3 style={{ fontSize: 12, fontWeight: 400 }}>Breakdown</h3>{rows.filter((p: any) => num(p.pnl) !== 0).sort((a: any, b: any) => num(a.pnl) - num(b.pnl)).map((p: any) => { const max = Math.max(...rows.map((x: any) => Math.abs(num(x.pnl))), 1); const w = `${Math.max(1, Math.abs(num(p.pnl)) / max * 100)}%`; return <div key={`b:${keyOf(p)}`} style={{ display: 'grid', gridTemplateColumns: '210px 1fr', alignItems: 'center', gap: 10, marginBottom: 8 }}><div style={{ textAlign: 'right', color: 'var(--k-ink-5)', fontSize: 9 }}><InstrumentLabel symbol={p.tradingsymbol} /> ({p.product})</div><div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', position: 'relative', height: 7 }}><div style={{ display: 'flex', justifyContent: 'flex-end' }}>{num(p.pnl) < 0 && <span style={{ width: w, background: C.red }} />}</div><div>{num(p.pnl) > 0 && <span style={{ display: 'block', width: w, height: 7, background: C.blue }} />}</div><i style={{ position: 'absolute', left: '50%', width: 1, top: -1, bottom: -1, background: 'var(--k-border-strong-3)' }} /></div></div>; })}</div>
        <details open={engineOpen} onToggle={(e) => setEngineOpen((e.currentTarget as HTMLDetailsElement).open)} style={{ borderTop: `1px solid ${C.border}`, marginTop: 22, paddingTop: 10 }}><summary style={{ cursor: 'pointer', fontSize: 12 }}>Engine Positions</summary><EnginePositionsPane /></details>
      </div>

      {menu && menuPosition && <div onClick={(e) => e.stopPropagation()} style={{ position: 'fixed', top: menu.top, left: menu.left, width: 190, background: 'var(--k-bg)', border: `1px solid ${C.border}`, boxShadow: '0 5px 18px rgba(0,0,0,.18)', zIndex: 1300, padding: '5px 0', borderRadius: 3 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderBottom: `1px solid ${C.border}`, paddingBottom: 4, marginBottom: 4 }}><div className="pos-menu-item" onClick={() => { openOrder(menuPosition, num(menuPosition.quantity) > 0 ? 'SELL' : 'BUY'); setMenu(null); }}>↪ Exit</div><div className="pos-menu-item" onClick={() => { openOrder(menuPosition, num(menuPosition.quantity) > 0 ? 'BUY' : 'SELL'); setMenu(null); }}>＋ Add</div></div>
        <div className="pos-menu-item" onClick={() => { setConvertKey(keyOf(menuPosition)); setMenu(null); }}>◫ Convert</div>
        <div className="pos-menu-item" onClick={() => { setInfo(menuPosition); setMenu(null); }}>ⓘ Info</div>
        <div className="pos-menu-sep" />
        <div className="pos-menu-item" onClick={() => { onOpenInstrument?.(`${menuPosition.exchange}:${menuPosition.tradingsymbol}`, 'chart'); setMenu(null); }}>⌁ Chart</div>
        <div className="pos-menu-item" onClick={() => { onOpenInstrument?.(`${menuPosition.exchange}:${menuPosition.tradingsymbol}`, 'option-chain'); setMenu(null); }}>◈ Option chain</div>
        <div className="pos-menu-item" onClick={() => { setInfo(menuPosition); setMenu(null); }}>≋ Market depth</div>
        <div className="pos-menu-sep" />
        <div className="pos-menu-item" onClick={() => { addToWatch(menuPosition); setMenu(null); }}>＋ Add to marketwatch</div>
        <div className="pos-menu-item" onClick={() => { addToBasket({ symbol: menuPosition.tradingsymbol, exchange: menuPosition.exchange, side: num(menuPosition.quantity) > 0 ? 'SELL' : 'BUY', qty: Math.abs(num(menuPosition.quantity)), product: menuPosition.product, orderType: 'MARKET', price: 0, trigger: 0 }); setMenu(null); }}>▣ Add to basket</div>
        <div className="pos-menu-item" onClick={() => { onOpenInstrument?.(`${menuPosition.exchange}:${menuPosition.tradingsymbol}`, 'chart'); setMenu(null); }}>⚡ Technicals</div>
      </div>}
      {info && <PositionInfo position={info} onClose={() => setInfo(null)} />}
      {analyticsOpen && <KitePortfolioAnalyticsModal view="positions" positions={rows} holdings={[]} onClose={() => setAnalyticsOpen(false)} />}
      {settingsOpen && <KiteSettingsPopover onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

export default PositionsPane;

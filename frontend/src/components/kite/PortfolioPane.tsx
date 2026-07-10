import React, { useState } from 'react';
import {
  useConvertKitePosition, useKiteHoldings, useKitePositions,
  useKiteAuctions, useInitiateHoldingsAuth, useKiteLtp
} from '../../hooks/useKite';

import { InstrumentLabel } from './InstrumentLabel';
import { KiteActionButtons } from './KiteActionButtons';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { EnginePositionsPane } from './EnginePositionsPane';
import { toCsv, downloadCsv } from '../../utils/csvExport';
import { KitePortfolioAnalyticsModal } from './KitePortfolioAnalyticsModal';
import { KiteSettingsPopover } from './KiteSettingsPopover';

const S: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: `1px solid #f1f1f1`, borderRadius: 10, padding: 14, marginBottom: 14 },
  title: { color: '#9b9b9b', fontSize: 11, letterSpacing: 2, marginBottom: 10, fontWeight: 700 },
  th: { textAlign: 'left' as const, color: '#9b9b9b', fontSize: 12, fontWeight: 400, padding: '12px 16px', borderBottom: `1px solid #f1f1f1` },
  td: { padding: '12px 16px', fontSize: 13, color: '#444', borderBottom: `1px solid #f1f1f1`, verticalAlign: 'middle' },
  hint: { color: '#9b9b9b', fontSize: 13 },
  inSm: { background: '#fff', color: '#444', border: `1px solid #e0e0e0`, borderRadius: 6, padding: '3px 6px', fontFamily: 'inherit', fontSize: 11 },
  pill: { padding: '2px 6px', borderRadius: 2, fontSize: 10, fontWeight: 500, background: '#f1f1f1', color: '#9b9b9b', letterSpacing: 0.3 },
};

const num = (v: any) => Number(v ?? 0);
const pnlColor = (v: number) => (v > 0 ? '#4caf50' : v < 0 ? '#df514c' : '#9b9b9b');

function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((x) => x !== p.product);
  const [target, setTarget] = useState(products[0]);
  if (!num(p.quantity)) return null;
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center', justifyContent: 'flex-end' }}>
      <select style={S.inSm} value={target} onChange={(e) => setTarget(e.target.value)}>
        {products.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <span
        style={{ cursor: 'pointer', color: convert.isError ? '#df514c' : '#387ed1', fontSize: 11 }}
        title={convert.isError ? (convert.error as Error).message : `Convert ${p.product} → ${target}`}
        onClick={() => convert.mutate({
          tradingsymbol: p.tradingsymbol, exchange: p.exchange,
          transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL', position_type: 'day',
          quantity: Math.abs(num(p.quantity)), old_product: p.product, new_product: target,
        })}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </span>
    </div>
  );
}

function AuthoriseHoldingsButton() {
  const authorise = useInitiateHoldingsAuth();
  return (
    <button
      style={{ background: '#387ed1', color: '#fff', border: `1px solid #387ed1`, borderRadius: 3, padding: '6px 14px', fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}
      title="Authorise holdings via CDSL TPIN (eDIS) — required to sell delivery holdings through the API"
      disabled={authorise.isPending}
      onClick={() => authorise.mutate({}, {
        onSuccess: (res) => { if (res.authorise_url) window.open(res.authorise_url, '_blank', 'noopener'); },
      })}
    >
      {authorise.isPending ? 'Authorising…' : 'Authorise holdings (eDIS)'}
    </button>
  );
}

function AuctionsSection() {
  const { data: auctions } = useKiteAuctions(true);
  if (!auctions || auctions.length === 0) return null;
  return (
    <div style={{ marginTop: 48 }}>
      <h2 style={{ fontSize: 18, fontWeight: 400, color: '#444', marginBottom: 24 }}>
        Auctions <span style={{ color: '#9b9b9b', fontSize: 18 }}>({auctions.length})</span>
      </h2>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead><tr>
          <th style={S.th}>Instrument</th>
          <th style={S.th}>Auction #</th>
          <th style={{ ...S.th, textAlign: 'right' }}>Qty.</th>
          <th style={{ ...S.th, textAlign: 'right' }}>Last price</th>
        </tr></thead>
        <tbody>
          {auctions.map((a: any, i: number) => (
            <tr key={`${a.tradingsymbol}-${i}`}>
              <td style={S.td}>
                <span style={{ color: '#444', marginRight: 8 }}>{a.tradingsymbol}</span>
                <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 3px', borderRadius: 2 }}>{a.exchange}</span>
              </td>
              <td style={{ ...S.td, color: '#444' }}>{a.auction_number}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(a.quantity)}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(a.last_price).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ ...S.hint, marginTop: 8 }}>Shares from settlement shortfalls that are eligible for the exchange auction window.</div>
    </div>
  );
}

export function PortfolioPane({ view }: { view?: 'holdings' | 'positions' }) {
  const { data: holdings } = useKiteHoldings(true);
  const { data: pos } = useKitePositions(true);
  const rawPositions = (pos?.net ?? []).filter((p: any) => num(p.quantity) !== 0 || num(p.pnl) !== 0);

  // Kite's /portfolio/positions last_price/pnl lag the live tick (Kite web overlays
  // its ticker). Overlay the same live LTP the marketwatch uses and recompute P&L by
  // the price delta — pnl = snapshot_pnl + (liveLtp - snapshot_ltp) * qty * multiplier —
  // so LTP/P&L/Chg/Total track Kite web instead of showing a stale snapshot.
  const posSymbols = rawPositions.map((p: any) => `${p.exchange}:${p.tradingsymbol}`);
  const { data: liveLtp } = useKiteLtp(posSymbols, posSymbols.length > 0);
  const positions = rawPositions.map((p: any) => {
    const live = num(liveLtp?.[`${p.exchange}:${p.tradingsymbol}`]?.last_price);
    if (live <= 0) return p;  // no live tick yet → keep the broker snapshot
    const pnl = num(p.pnl) + (live - num(p.last_price)) * num(p.quantity) * (num(p.multiplier) || 1);
    return { ...p, last_price: live, pnl };
  });

  const { openOrderWindow } = useOrderWindowStore();

  const handleOpenOrder = (symbol: string, initialSide: 'BUY' | 'SELL', initialQty: number, product: string, lastPx: number | null = null) => {
    const [exchange, tradingsymbol] = symbol.split(':');
    openOrderWindow({
      symbol: tradingsymbol || symbol,
      exchange: exchange || 'NSE',
      initialSide,
      initialQty,
      lastPrice: lastPx || 0,
      product: product as 'MIS' | 'CNC' | 'NRML',   // square off / add to the position in its own product
    });
  };

  const showHoldings = view === 'holdings' || !view;
  const showPositions = view === 'positions' || !view;

  const [selectedPos, setSelectedPos] = useState<Set<string>>(new Set());
  const [posQuery, setPosQuery] = useState('');
  const [holdQuery, setHoldQuery] = useState('');
  const [analyticsView, setAnalyticsView] = useState<'positions' | 'holdings' | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Sorting state
  const [posSort, setPosSort] = useState<{key: string, dir: 'asc' | 'desc' | ''}>({key: '', dir: ''});
  const [holdSort, setHoldSort] = useState<{key: string, dir: 'asc' | 'desc' | ''}>({key: '', dir: ''});

  const handlePosSort = (k: string) => setPosSort(prev => prev.key === k ? {key: k, dir: prev.dir === 'asc' ? 'desc' : prev.dir === 'desc' ? '' : 'asc'} : {key: k, dir: 'asc'});
  const handleHoldSort = (k: string) => setHoldSort(prev => prev.key === k ? {key: k, dir: prev.dir === 'asc' ? 'desc' : prev.dir === 'desc' ? '' : 'asc'} : {key: k, dir: 'asc'});

  const downloadPositions = () => downloadCsv('positions.csv', toCsv(sortedPositions, [
    { header: 'Instrument', value: (p: any) => p.tradingsymbol },
    { header: 'Exchange', value: (p: any) => p.exchange },
    { header: 'Product', value: (p: any) => p.product },
    { header: 'Qty', value: (p: any) => num(p.quantity) },
    { header: 'Avg Price', value: (p: any) => num(p.average_price).toFixed(2) },
    { header: 'LTP', value: (p: any) => num(p.last_price).toFixed(2) },
    { header: 'P&L', value: (p: any) => num(p.pnl).toFixed(2) },
  ]));

  const downloadHoldings = () => downloadCsv('holdings.csv', toCsv(sortedHoldings, [
    { header: 'Instrument', value: (h: any) => h.tradingsymbol },
    { header: 'Exchange', value: (h: any) => h.exchange },
    { header: 'Qty', value: (h: any) => num(h.quantity) },
    { header: 'Avg Cost', value: (h: any) => num(h.average_price).toFixed(2) },
    { header: 'LTP', value: (h: any) => num(h.last_price).toFixed(2) },
    { header: 'Cur. Value', value: (h: any) => (num(h.quantity) * num(h.last_price)).toFixed(2) },
    { header: 'P&L', value: (h: any) => num(h.pnl).toFixed(2) },
  ]));

  const filteredPositions = posQuery.trim()
    ? positions.filter((p: any) => `${p.tradingsymbol} ${p.exchange}`.toLowerCase().includes(posQuery.trim().toLowerCase()))
    : positions;
  let sortedPositions = [...filteredPositions];
  if (posSort.key && posSort.dir) {
    sortedPositions.sort((a: any, b: any) => {
      let va = a[posSort.key];
      let vb = b[posSort.key];
      if (posSort.key === 'chg') {
        va = num(a.close_price) > 0 ? ((num(a.last_price) - num(a.close_price)) / num(a.close_price)) * 100 : 0;
        vb = num(b.close_price) > 0 ? ((num(b.last_price) - num(b.close_price)) / num(b.close_price)) * 100 : 0;
      } else if (posSort.key === 'quantity' || posSort.key === 'average_price' || posSort.key === 'last_price' || posSort.key === 'pnl') {
        va = num(va);
        vb = num(vb);
      }
      if (typeof va === 'string' && typeof vb === 'string') return posSort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      return posSort.dir === 'asc' ? num(va) - num(vb) : num(vb) - num(va);
    });
  }

  const filteredHoldings = holdQuery.trim()
    ? (holdings || []).filter((h: any) => `${h.tradingsymbol} ${h.exchange}`.toLowerCase().includes(holdQuery.trim().toLowerCase()))
    : (holdings || []);
  let sortedHoldings = [...filteredHoldings];
  if (holdSort.key && holdSort.dir) {
    sortedHoldings.sort((a: any, b: any) => {
      let va = a[holdSort.key];
      let vb = b[holdSort.key];
      if (holdSort.key === 'curVal') {
        va = num(a.quantity) * num(a.last_price);
        vb = num(b.quantity) * num(b.last_price);
      } else if (holdSort.key === 'netChg') {
        va = ((num(a.last_price) - num(a.average_price)) / (num(a.average_price) || 1)) * 100;
        vb = ((num(b.last_price) - num(b.average_price)) / (num(b.average_price) || 1)) * 100;
      } else if (holdSort.key === 'dayChg') {
        va = num(a.day_change_percentage);
        vb = num(b.day_change_percentage);
      } else if (holdSort.key === 'quantity' || holdSort.key === 'average_price' || holdSort.key === 'last_price' || holdSort.key === 'pnl') {
        va = num(va);
        vb = num(vb);
      }
      if (typeof va === 'string' && typeof vb === 'string') return holdSort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      return holdSort.dir === 'asc' ? num(va) - num(vb) : num(vb) - num(va);
    });
  }

  const togglePos = (id: string) => {
    const next = new Set(selectedPos);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedPos(next);
  };

  const toggleAllPos = () => {
    if (selectedPos.size === positions.length && positions.length > 0) setSelectedPos(new Set());
    else setSelectedPos(new Set(positions.map((p: any) => `${p.exchange}:${p.tradingsymbol}`)));
  };

  const totalPosPnl = positions.reduce((acc: number, p: any) => acc + num(p.pnl), 0);
  const totalHoldingsPnl = (holdings || []).reduce((acc: number, h: any) => acc + num(h.pnl), 0);
  const totalHoldingsDayPnl = (holdings || []).reduce((acc: number, h: any) => acc + (num(h.day_change) * num(h.quantity)), 0);
  const totalHoldingsVal = (holdings || []).reduce((acc: number, h: any) => acc + (num(h.quantity) * num(h.last_price)), 0);

  const SortHeader = ({ label, sortKey, currentSort, onSort, style }: any) => {
    const isActive = currentSort.key === sortKey && currentSort.dir !== '';
    return (
      <th 
        style={{ ...style, cursor: sortKey ? 'pointer' : 'default', userSelect: 'none' }} 
        onClick={() => sortKey && onSort(sortKey)}
        className={sortKey ? "sort-header" : ""}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: style.textAlign === 'right' ? 'flex-end' : 'flex-start' }}>
          {label}
          {sortKey && (
            <span className={`sort-icon ${isActive ? 'active' : ''}`}>
              <svg width="8" height="4" viewBox="0 0 8 4" fill={isActive && currentSort.dir === 'asc' ? '#387ed1' : 'currentColor'} style={{ opacity: (!isActive || currentSort.dir === 'asc') ? 1 : 0.2 }}><path d="M4 0L8 4H0L4 0Z"/></svg>
              <svg width="8" height="4" viewBox="0 0 8 4" fill={isActive && currentSort.dir === 'desc' ? '#387ed1' : 'currentColor'} style={{ opacity: (!isActive || currentSort.dir === 'desc') ? 1 : 0.2 }}><path d="M4 4L8 0H0L4 4Z"/></svg>
            </span>
          )}
        </div>
      </th>
    );
  };

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: '24px 32px' }}>
      <style>{`
        .portfolio-row:hover { background-color: #f9f9f9 !important; }
        .portfolio-row:hover .portfolio-content { visibility: hidden; }
        .portfolio-row:hover .portfolio-actions { display: flex !important; }
        .sort-header:hover { color: #444 !important; }
        .sort-icon { opacity: 0; color: #9b9b9b; display: flex; flex-direction: column; gap: 2px; align-items: center; transition: opacity 0.2s; }
        .sort-header:hover .sort-icon { opacity: 0.5; }
        .sort-icon.active { opacity: 1 !important; color: #444; }
      `}</style>
      {showPositions && (
        <div style={{ marginBottom: 48 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 400, color: '#444', margin: 0 }}>
              Positions <span style={{ color: '#9b9b9b', fontSize: 18 }}>({positions.length})</span>
            </h2>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#9b9b9b', fontSize: 12 }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </span>
                <input type="text" placeholder="Search" value={posQuery} onChange={(e) => setPosQuery(e.target.value)} style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 160, outline: 'none' }} />
              </div>
              <a href="#" onClick={(e) => { e.preventDefault(); setAnalyticsView('positions'); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a10 10 0 0 1 10 10h-10z"></path></svg> Analytics
              </a>
              <a href="#" onClick={(e) => { e.preventDefault(); setSettingsOpen(true); }} style={{ color: '#9b9b9b', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg> Settings
              </a>
              <a href="#" onClick={(e) => { e.preventDefault(); downloadPositions(); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </a>
            </div>
          </div>
          {positions.length === 0 && <div style={S.hint}>No open positions.</div>}
          {positions.length > 0 && (
            <div style={{ position: 'relative' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead><tr>
                  <th style={{ ...S.th, width: 40, textAlign: 'center' }}>
                    <input type="checkbox" checked={selectedPos.size === positions.length && positions.length > 0} onChange={toggleAllPos} style={{ cursor: 'pointer' }} />
                  </th>
                  <SortHeader label="Product" sortKey="product" currentSort={posSort} onSort={handlePosSort} style={S.th} />
                  <SortHeader label="Instrument" sortKey="tradingsymbol" currentSort={posSort} onSort={handlePosSort} style={S.th} />
                  <SortHeader label="Qty." sortKey="quantity" currentSort={posSort} onSort={handlePosSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="Avg." sortKey="average_price" currentSort={posSort} onSort={handlePosSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="LTP" sortKey="last_price" currentSort={posSort} onSort={handlePosSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="P&L" sortKey="pnl" currentSort={posSort} onSort={handlePosSort} style={{...S.th, textAlign: 'right', background: '#f9f9f9'}} />
                  <SortHeader label="Chg." sortKey="chg" currentSort={posSort} onSort={handlePosSort} style={{...S.th, textAlign: 'right'}} />
                </tr></thead>
                <tbody>
                  {sortedPositions.map((p: any, idx: number) => {
                    const qty = num(p.quantity);
                    const id = `${p.exchange}:${p.tradingsymbol}`;
                    const isSelected = selectedPos.has(id);
                    const chg = num(p.average_price) > 0 ? ((num(p.last_price) - num(p.average_price)) / num(p.average_price)) * 100 : 0;
                    return (
                      <tr key={`${id}-${idx}`} className="portfolio-row" style={{ background: isSelected ? 'rgba(56, 126, 209, 0.05)' : 'transparent', transition: 'background 0.2s' }}>
                        <td style={{ ...S.td, textAlign: 'center' }}>
                          <input type="checkbox" checked={isSelected} onChange={() => togglePos(id)} style={{ cursor: 'pointer' }} />
                        </td>
                        <td style={S.td}>
                          {p.product === 'NRML' ? (
                            <span style={{ ...S.pill, background: 'rgba(200, 86, 162, 0.1)', color: '#c856a2' }}>{p.product}</span>
                          ) : p.product === 'MIS' ? (
                            <span style={{ ...S.pill, background: 'rgba(56, 126, 209, 0.1)', color: '#387ed1' }}>{p.product}</span>
                          ) : (
                            <span style={{ ...S.pill }}>{p.product}</span>
                          )}
                        </td>
                        <td style={{...S.td, whiteSpace: 'nowrap'}}>
                          <span style={{ color: '#444', marginRight: 8 }}><InstrumentLabel symbol={p.tradingsymbol} /></span>
                          <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 4px', borderRadius: 2 }}>{p.exchange}</span>
                        </td>
                        <td style={{ ...S.td, textAlign: 'right', color: qty >= 0 ? '#387ed1' : '#df514c' }}>{qty}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.average_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.last_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(num(p.pnl)), background: '#f9f9f9' }}>
                          {num(p.pnl) > 0 ? '+' : ''}{num(p.pnl).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(chg), position: 'relative' }}>
                          <span className="portfolio-content">{chg.toFixed(2)}%</span>
                          <div className="portfolio-actions" style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', display: 'none', background: '#f9f9f9', paddingLeft: 8 }}>
                            <KiteActionButtons 
                              onBuy={(e) => { e.stopPropagation(); handleOpenOrder(id, qty >= 0 ? 'BUY' : 'SELL', Math.abs(qty), p.product, num(p.last_price)); }}
                              buyLabel="Add"
                              onSell={(e) => { e.stopPropagation(); handleOpenOrder(id, qty >= 0 ? 'SELL' : 'BUY', Math.abs(qty), p.product, num(p.last_price)); }}
                              sellLabel="Exit"
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', padding: '12px 16px', borderTop: `1px solid #f1f1f1` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <span style={{ color: '#444', fontSize: 13 }}>Total P&L</span>
                  <span style={{ color: pnlColor(totalPosPnl), fontSize: 16, textAlign: 'right', padding: '0 8px', background: '#f9f9f9' }}>
                    {totalPosPnl > 0 ? '+' : ''}{totalPosPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              </div>

              <div style={{ marginTop: 40, borderTop: `1px solid #f1f1f1`, paddingTop: 24 }}>
                <h3 style={{ fontSize: 14, fontWeight: 400, color: '#444', marginBottom: 24 }}>Breakdown</h3>
                {sortedPositions.filter((p: any) => num(p.pnl) !== 0).map((p: any, idx: number) => {
                  const pnl = num(p.pnl);
                  const maxPnl = Math.max(...positions.map((x: any) => Math.abs(num(x.pnl))), 1);
                  const width = `${(Math.abs(pnl) / maxPnl) * 100}%`;
                  return (
                    <div key={`breakdown-${idx}`} style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
                      <div style={{ width: 250, fontSize: 10, color: '#9b9b9b', textAlign: 'right', paddingRight: 16 }}>
                        <InstrumentLabel symbol={p.tradingsymbol} /> ({p.product})
                      </div>
                      <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: '#f1f1f1', height: 6 }}>
                         <div style={{ height: 6, background: '#387ed1', width }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {showPositions && (
        <div style={{ marginBottom: 32 }}>
          <EnginePositionsPane />
        </div>
      )}

      {showHoldings && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h2 style={{ fontSize: 18, fontWeight: 400, color: '#444', margin: 0 }}>
              Holdings <span style={{ color: '#9b9b9b', fontSize: 18 }}>({holdings?.length || 0})</span>
            </h2>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#9b9b9b', fontSize: 12 }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                </span>
                <input type="text" placeholder="Search" value={holdQuery} onChange={(e) => setHoldQuery(e.target.value)} style={{ padding: '6px 8px 6px 28px', border: `1px solid #e0e0e0`, borderRadius: 3, background: 'transparent', color: '#444', fontSize: 12, width: 150, outline: 'none' }} />
              </div>
              <a href="#" onClick={(e) => { e.preventDefault(); setAnalyticsView('holdings'); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4"></path><path d="M12 8h.01"></path></svg> Analytics
              </a>
              <a href="#" onClick={(e) => { e.preventDefault(); downloadHoldings(); }} style={{ color: '#387ed1', textDecoration: 'none', cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> Download
              </a>
              <AuthoriseHoldingsButton />
            </div>
          </div>
          {(!holdings || holdings.length === 0) && <div style={S.hint}>No equity holdings.</div>}
          {holdings && holdings.length > 0 && (
            <div>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead><tr>
                  <SortHeader label="Instrument" sortKey="tradingsymbol" currentSort={holdSort} onSort={handleHoldSort} style={S.th} />
                  <SortHeader label="Qty." sortKey="quantity" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="Avg. cost" sortKey="average_price" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="LTP" sortKey="last_price" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="Cur. val" sortKey="curVal" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="P&L" sortKey="pnl" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right', background: '#f9f9f9'}} />
                  <SortHeader label="Net chg." sortKey="netChg" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                  <SortHeader label="Day chg." sortKey="dayChg" currentSort={holdSort} onSort={handleHoldSort} style={{...S.th, textAlign: 'right'}} />
                </tr></thead>
                <tbody>
                  {sortedHoldings.map((h: any, idx: number) => {
                    const pnl = num(h.pnl);
                    const curVal = num(h.quantity) * num(h.last_price);
                    const netChg = ((num(h.last_price) - num(h.average_price)) / (num(h.average_price) || 1)) * 100;
                    const dayChg = num(h.day_change);
                    const dayChgPct = num(h.day_change_percentage);
                    return (
                      <tr key={`${h.tradingsymbol}-${idx}`} className="portfolio-row" style={{ transition: 'background 0.2s' }}>
                        <td style={{...S.td, whiteSpace: 'nowrap'}}>
                          <span style={{ color: '#444', marginRight: 8 }}><InstrumentLabel symbol={h.tradingsymbol} /></span>
                          <span style={{ fontSize: 9, color: '#9b9b9b', background: '#f1f1f1', padding: '1px 3px', borderRadius: 2 }}>{h.exchange}</span>
                        </td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.quantity)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.average_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(h.last_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{curVal.toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(pnl), background: '#f9f9f9' }}>
                          {pnl > 0 ? '+' : ''}{pnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(netChg) }}>{netChg.toFixed(2)}%</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(dayChgPct), position: 'relative' }}>
                          <span className="portfolio-content">{dayChg !== 0 ? `${dayChg > 0 ? '+' : ''}${dayChgPct.toFixed(2)}%` : '0.00%'}</span>
                          <div className="portfolio-actions" style={{ position: 'absolute', right: 16, top: '50%', transform: 'translateY(-50%)', display: 'none', background: '#f9f9f9', paddingLeft: 8 }}>
                            <KiteActionButtons 
                              onBuy={(e) => { e.stopPropagation(); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'BUY', num(h.quantity), h.product || 'CNC', num(h.last_price)); }}
                              buyLabel="Add"
                              onSell={(e) => { e.stopPropagation(); handleOpenOrder(`${h.exchange}:${h.tradingsymbol}`, 'SELL', num(h.quantity), h.product || 'CNC', num(h.last_price)); }}
                              sellLabel="Exit"
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', padding: '16px 8px', borderTop: `1px solid #f1f1f1` }}>
                <div style={{ display: 'flex', gap: 32, fontSize: 13 }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ color: '#9b9b9b', marginRight: 8 }}>Total investment</span>
                    <span style={{ color: '#444' }}>{(totalHoldingsVal - totalHoldingsPnl).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ color: '#9b9b9b', marginRight: 8 }}>Current value</span>
                    <span style={{ color: '#444' }}>{totalHoldingsVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ color: '#9b9b9b', marginRight: 8 }}>Day's P&L</span>
                    <span style={{ color: pnlColor(totalHoldingsDayPnl) }}>{totalHoldingsDayPnl > 0 ? '+' : ''}{totalHoldingsDayPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <span style={{ color: '#9b9b9b', marginRight: 8 }}>Total P&L</span>
                    <span style={{ color: pnlColor(totalHoldingsPnl) }}>{totalHoldingsPnl > 0 ? '+' : ''}{totalHoldingsPnl.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
          <AuctionsSection />
        </div>
      )}

      {analyticsView && (
        <KitePortfolioAnalyticsModal
          view={analyticsView}
          positions={sortedPositions}
          holdings={sortedHoldings}
          onClose={() => setAnalyticsView(null)}
        />
      )}

      {settingsOpen && <KiteSettingsPopover onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

import React, { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useConvertKitePosition,
  useInitiateHoldingsAuth,
  useKiteAuctions,
  useKiteHoldings,
  useKiteLtp,
  useKitePositions,
  usePlaceKiteOrder,
} from '../../hooks/useKite';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
import { notifyOrder } from '../../store/useKiteNotifications';
import { downloadCsv, toCsv } from '../../utils/csvExport';
import { InstrumentLabel } from './InstrumentLabel';
import { KiteActionButtons } from './KiteActionButtons';
import { EnginePositionsPane } from './EnginePositionsPane';
import { KitePortfolioAnalyticsModal } from './KitePortfolioAnalyticsModal';
import { KiteSettingsPopover } from './KiteSettingsPopover';

const COLORS = {
  text: '#444',
  muted: '#9b9b9b',
  border: '#ededed',
  rowHover: '#fafafa',
  pnlBg: '#fbfbfb',
  blue: '#387ed1',
  green: '#4caf50',
  red: '#df514c',
};

const S: Record<string, React.CSSProperties> = {
  th: {
    textAlign: 'left', color: COLORS.muted, fontSize: 12, fontWeight: 400,
    padding: '11px 12px', borderBottom: `1px solid ${COLORS.border}`,
    whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums',
  },
  td: {
    padding: '10px 12px', fontSize: 13, color: COLORS.text,
    borderBottom: `1px solid ${COLORS.border}`, verticalAlign: 'middle',
    fontVariantNumeric: 'tabular-nums',
  },
  hint: { color: COLORS.muted, fontSize: 13, padding: '14px 0' },
  inSm: {
    background: '#fff', color: COLORS.text, border: `1px solid #dedede`, borderRadius: 3,
    padding: '4px 6px', fontFamily: 'inherit', fontSize: 11, outline: 'none',
  },
  pill: {
    padding: '2px 7px', borderRadius: 2, fontSize: 10, fontWeight: 500,
    background: '#f1f1f1', color: COLORS.muted, letterSpacing: 0.2,
  },
};

const num = (value: unknown) => Number(value ?? 0);
const pnlColor = (value: number) => value > 0 ? COLORS.green : value < 0 ? COLORS.red : COLORS.muted;
const positionKey = (p: any) => `${p.exchange}:${p.tradingsymbol}:${p.product || ''}`;
const formatMoney = (value: number, withPlus = true) =>
  `${withPlus && value > 0 ? '+' : ''}${value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function SearchIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function ToolbarLink({ children, onClick, muted = false }: { children: React.ReactNode; onClick: () => void; muted?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        border: 0, background: 'transparent', padding: 0, color: muted ? COLORS.muted : COLORS.blue,
        cursor: 'pointer', font: 'inherit', fontSize: 12, display: 'inline-flex', alignItems: 'center', gap: 4,
      }}
    >
      {children}
    </button>
  );
}

export function ConvertControl({ p }: { p: any }) {
  const convert = useConvertKitePosition();
  const products = ['MIS', 'CNC', 'NRML'].filter((product) => product !== p.product);
  const [target, setTarget] = useState(products[0] || 'NRML');
  const fullQty = Math.abs(num(p.quantity));
  const [qty, setQty] = useState(fullQty);

  useEffect(() => {
    setQty(fullQty);
  }, [fullQty]);

  if (!num(p.quantity) || products.length === 0) return null;
  const invalidQty = !Number.isFinite(qty) || qty < 1 || qty > fullQty;

  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center', justifyContent: 'flex-end' }}>
      <input
        aria-label="Convert quantity"
        type="number"
        min={1}
        max={fullQty}
        value={Number.isFinite(qty) ? qty : ''}
        onChange={(event) => setQty(Number(event.target.value))}
        style={{ ...S.inSm, width: 52, textAlign: 'right' }}
        title={`Max: ${fullQty}`}
      />
      <select aria-label="Convert target product" style={S.inSm} value={target} onChange={(event) => setTarget(event.target.value)}>
        {products.map((product) => <option key={product} value={product}>{product}</option>)}
      </select>
      <button
        type="button"
        disabled={invalidQty || convert.isPending}
        title={invalidQty ? `Enter a quantity between 1 and ${fullQty}` : convert.isError ? (convert.error as Error).message : `Convert ${qty} of ${fullQty} ${p.product} to ${target}`}
        onClick={() => {
          if (invalidQty) return;
          convert.mutate({
            tradingsymbol: p.tradingsymbol,
            exchange: p.exchange,
            transaction_type: num(p.quantity) >= 0 ? 'BUY' : 'SELL',
            position_type: 'day',
            quantity: qty,
            old_product: p.product,
            new_product: target,
          });
        }}
        style={{ border: 0, background: 'transparent', padding: 0, font: 'inherit', fontSize: 11, color: invalidQty ? '#bdbdbd' : convert.isError ? COLORS.red : COLORS.blue, cursor: invalidQty ? 'not-allowed' : 'pointer' }}
      >
        {convert.isPending ? '…' : convert.isSuccess ? '✓' : 'convert'}
      </button>
    </div>
  );
}

function AuthoriseHoldingsButton() {
  const authorise = useInitiateHoldingsAuth();
  return (
    <button
      type="button"
      disabled={authorise.isPending}
      onClick={() => authorise.mutate({}, { onSuccess: (result) => { if (result.authorise_url) window.open(result.authorise_url, '_blank', 'noopener'); } })}
      title="Authorise holdings via CDSL TPIN (eDIS)"
      style={{ background: COLORS.blue, color: '#fff', border: `1px solid ${COLORS.blue}`, borderRadius: 3, padding: '5px 11px', fontSize: 11, fontWeight: 500, cursor: authorise.isPending ? 'wait' : 'pointer', fontFamily: 'inherit' }}
    >
      {authorise.isPending ? 'Authorising…' : 'Authorise holdings'}
    </button>
  );
}

function AuctionsSection() {
  const { data: auctions } = useKiteAuctions(true);
  if (!auctions?.length) return null;
  return (
    <section style={{ marginTop: 36 }}>
      <h2 style={{ fontSize: 17, fontWeight: 400, color: COLORS.text, margin: '0 0 16px' }}>
        Auctions <span style={{ color: COLORS.muted }}>({auctions.length})</span>
      </h2>
      <div className="portfolio-table-scroll">
        <table className="portfolio-table" style={{ minWidth: 620 }}>
          <thead><tr><th style={S.th}>Instrument</th><th style={S.th}>Auction #</th><th style={{ ...S.th, textAlign: 'right' }}>Qty.</th><th style={{ ...S.th, textAlign: 'right' }}>Last price</th></tr></thead>
          <tbody>{auctions.map((auction: any, index: number) => (
            <tr key={`${auction.tradingsymbol}-${index}`}>
              <td style={S.td}>{auction.tradingsymbol} <span className="exchange-tag">{auction.exchange}</span></td>
              <td style={S.td}>{auction.auction_number}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(auction.quantity)}</td>
              <td style={{ ...S.td, textAlign: 'right' }}>{num(auction.last_price).toFixed(2)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function ProductPill({ product }: { product: string }) {
  const style = product === 'NRML'
    ? { background: 'rgba(200,86,162,.10)', color: '#c856a2' }
    : product === 'MIS'
      ? { background: 'rgba(56,126,209,.10)', color: COLORS.blue }
      : {};
  return <span style={{ ...S.pill, ...style }}>{product}</span>;
}

function SortHeader({ label, sortKey, currentSort, onSort, style }: any) {
  const active = currentSort.key === sortKey && currentSort.dir;
  return (
    <th style={{ ...style, cursor: sortKey ? 'pointer' : 'default', userSelect: 'none' }} onClick={() => sortKey && onSort(sortKey)} className={sortKey ? 'sort-header' : undefined}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, justifyContent: style.textAlign === 'right' ? 'flex-end' : 'flex-start' }}>
        {label}
        {sortKey && <span className={`sort-icon ${active ? 'active' : ''}`} aria-hidden>{active ? (currentSort.dir === 'asc' ? '▲' : '▼') : '↕'}</span>}
      </div>
    </th>
  );
}

function PositionBreakdown({ positions }: { positions: any[] }) {
  const rows = useMemo(
    () => positions.filter((p) => num(p.pnl) !== 0).slice().sort((a, b) => num(a.pnl) - num(b.pnl)),
    [positions],
  );
  if (!rows.length) return null;
  const maxAbs = Math.max(...rows.map((row) => Math.abs(num(row.pnl))), 1);

  return (
    <section className="breakdown-section">
      <h3>Breakdown</h3>
      <div className="breakdown-list">
        {rows.map((p) => {
          const pnl = num(p.pnl);
          const width = `${Math.max(1.5, Math.abs(pnl) / maxAbs * 100)}%`;
          return (
            <div key={`breakdown:${positionKey(p)}`} className="breakdown-row" title={`${p.tradingsymbol}: ${formatMoney(pnl)}`}>
              <div className="breakdown-label"><InstrumentLabel symbol={p.tradingsymbol} /> ({p.product})</div>
              <div className="breakdown-axis">
                <div className="breakdown-half negative">{pnl < 0 && <div className="breakdown-bar negative" style={{ width }} />}</div>
                <div className="breakdown-zero" />
                <div className="breakdown-half positive">{pnl > 0 && <div className="breakdown-bar positive" style={{ width }} />}</div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function PortfolioPane({ view }: { view?: 'holdings' | 'positions' }) {
  const { data: holdings } = useKiteHoldings(true);
  const { data: positionResponse } = useKitePositions(true);
  const rawPositions = (positionResponse?.net ?? []).filter((p: any) => num(p.quantity) !== 0 || num(p.pnl) !== 0);
  const posSymbols = useMemo(() => Array.from(new Set(rawPositions.map((p: any) => `${p.exchange}:${p.tradingsymbol}`))), [rawPositions]);
  const { data: liveLtp } = useKiteLtp(posSymbols, posSymbols.length > 0);

  const positions = useMemo(() => rawPositions.map((p: any) => {
    const live = num(liveLtp?.[`${p.exchange}:${p.tradingsymbol}`]?.last_price);
    if (live <= 0) return p;
    const snapshotLtp = num(p.last_price);
    const multiplier = num(p.multiplier) || 1;
    return { ...p, last_price: live, pnl: num(p.pnl) + (live - snapshotLtp) * num(p.quantity) * multiplier };
  }), [rawPositions, liveLtp]);

  const { openOrderWindow } = useOrderWindowStore();
  const addToBasket = useKiteBasketStore((state) => state.add);
  const queryClient = useQueryClient();
  const placeOrder = usePlaceKiteOrder();

  const [selectedPos, setSelectedPos] = useState<Set<string>>(new Set());
  const [expandedConvertId, setExpandedConvertId] = useState<string | null>(null);
  const [posQuery, setPosQuery] = useState('');
  const [holdQuery, setHoldQuery] = useState('');
  const [posSort, setPosSort] = useState<{ key: string; dir: 'asc' | 'desc' | '' }>({ key: '', dir: '' });
  const [holdSort, setHoldSort] = useState<{ key: string; dir: 'asc' | 'desc' | '' }>({ key: '', dir: '' });
  const [analyticsView, setAnalyticsView] = useState<'positions' | 'holdings' | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [engineOpen, setEngineOpen] = useState(false);
  const [exitingSelected, setExitingSelected] = useState(false);

  const showHoldings = view === 'holdings' || !view;
  const showPositions = view === 'positions' || !view;

  useEffect(() => {
    const liveKeys = new Set(positions.filter((p: any) => num(p.quantity) !== 0).map(positionKey));
    setSelectedPos((current) => {
      const next = new Set([...current].filter((key) => liveKeys.has(key)));
      return next.size === current.size ? current : next;
    });
    if (expandedConvertId && !liveKeys.has(expandedConvertId)) setExpandedConvertId(null);
  }, [positions, expandedConvertId]);

  const handleOpenOrder = (p: any, initialSide: 'BUY' | 'SELL', initialQty: number) => {
    openOrderWindow({
      symbol: p.tradingsymbol,
      exchange: p.exchange || 'NSE',
      initialSide,
      initialQty,
      lastPrice: num(p.last_price),
      product: (p.product || 'MIS') as 'MIS' | 'CNC' | 'NRML',
    });
  };

  const filteredPositions = useMemo(() => {
    const query = posQuery.trim().toLowerCase();
    return query ? positions.filter((p: any) => `${p.tradingsymbol} ${p.exchange} ${p.product}`.toLowerCase().includes(query)) : positions;
  }, [positions, posQuery]);

  const sortedPositions = useMemo(() => {
    const rows = [...filteredPositions];
    if (!posSort.key || !posSort.dir) return rows;
    return rows.sort((a: any, b: any) => {
      const value = (p: any) => {
        if (posSort.key === 'chg') return num(p.quantity) === 0 || num(p.average_price) <= 0 ? 0 : (num(p.last_price) - num(p.average_price)) / num(p.average_price) * 100;
        return p[posSort.key];
      };
      const av = value(a); const bv = value(b);
      const result = typeof av === 'string' && typeof bv === 'string' ? av.localeCompare(bv) : num(av) - num(bv);
      return posSort.dir === 'asc' ? result : -result;
    });
  }, [filteredPositions, posSort]);

  const filteredHoldings = useMemo(() => {
    const query = holdQuery.trim().toLowerCase();
    const rows = holdings || [];
    return query ? rows.filter((h: any) => `${h.tradingsymbol} ${h.exchange}`.toLowerCase().includes(query)) : rows;
  }, [holdings, holdQuery]);

  const sortedHoldings = useMemo(() => {
    const rows = [...filteredHoldings];
    if (!holdSort.key || !holdSort.dir) return rows;
    return rows.sort((a: any, b: any) => {
      const value = (h: any) => {
        if (holdSort.key === 'curVal') return num(h.quantity) * num(h.last_price);
        if (holdSort.key === 'netChg') return num(h.average_price) ? (num(h.last_price) - num(h.average_price)) / num(h.average_price) * 100 : 0;
        if (holdSort.key === 'dayChg') return num(h.day_change_percentage);
        return h[holdSort.key];
      };
      const av = value(a); const bv = value(b);
      const result = typeof av === 'string' && typeof bv === 'string' ? av.localeCompare(bv) : num(av) - num(bv);
      return holdSort.dir === 'asc' ? result : -result;
    });
  }, [filteredHoldings, holdSort]);

  const toggleSort = (setter: React.Dispatch<React.SetStateAction<{ key: string; dir: 'asc' | 'desc' | '' }>>, key: string) => {
    setter((previous) => previous.key === key
      ? { key, dir: previous.dir === 'asc' ? 'desc' : previous.dir === 'desc' ? '' : 'asc' }
      : { key, dir: 'asc' });
  };

  const selectablePosIds = sortedPositions.filter((p: any) => num(p.quantity) !== 0).map(positionKey);
  const allVisibleSelected = selectablePosIds.length > 0 && selectablePosIds.every((key) => selectedPos.has(key));
  const togglePos = (key: string) => setSelectedPos((current) => {
    const next = new Set(current);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });
  const toggleAllPos = () => setSelectedPos((current) => {
    const next = new Set(current);
    if (allVisibleSelected) selectablePosIds.forEach((key) => next.delete(key));
    else selectablePosIds.forEach((key) => next.add(key));
    return next;
  });

  const exitSelected = async () => {
    const targets = positions.filter((p: any) => selectedPos.has(positionKey(p)) && num(p.quantity) !== 0);
    if (!targets.length) return;
    const preview = targets.length <= 3 ? targets.map((p: any) => p.tradingsymbol).join(', ') : `${targets.slice(0, 3).map((p: any) => p.tradingsymbol).join(', ')} +${targets.length - 3} more`;
    if (!window.confirm(`Exit ${targets.length} selected position${targets.length === 1 ? '' : 's'} (${preview}) at market price?`)) return;

    setExitingSelected(true);
    let skipped = 0;
    try {
      for (const target of targets) {
        const liveNet = queryClient.getQueryData<{ net: any[] }>(['kite-positions'])?.net ?? [];
        const live = liveNet.find((p: any) => positionKey(p) === positionKey(target));
        const liveQty = live ? num(live.quantity) : 0;
        if (!liveQty) { skipped += 1; continue; }
        try {
          await placeOrder.mutateAsync({
            tradingsymbol: target.tradingsymbol,
            exchange: target.exchange,
            transaction_type: liveQty > 0 ? 'SELL' : 'BUY',
            quantity: Math.abs(liveQty),
            order_type: 'MARKET',
            product: target.product,
            variety: 'regular',
            validity: 'DAY',
          });
        } catch {
          // usePlaceKiteOrder already reports the per-leg failure.
        }
      }
    } finally {
      setExitingSelected(false);
      setSelectedPos(new Set());
    }

    if (skipped) {
      notifyOrder({
        kind: 'info',
        title: 'Some positions were skipped',
        message: `Exited ${targets.length - skipped} of ${targets.length} selected position${targets.length === 1 ? '' : 's'} — ${skipped} ${skipped === 1 ? 'was' : 'were'} already closed or changed.`,
      });
    }
  };

  const totalPosPnl = positions.reduce((total: number, p: any) => total + num(p.pnl), 0);
  const totalHoldingsPnl = (holdings || []).reduce((total: number, h: any) => total + num(h.pnl), 0);
  const totalHoldingsDayPnl = (holdings || []).reduce((total: number, h: any) => total + num(h.day_change) * num(h.quantity), 0);
  const totalHoldingsVal = (holdings || []).reduce((total: number, h: any) => total + num(h.quantity) * num(h.last_price), 0);
  const totalHoldingsInvestment = (holdings || []).reduce((total: number, h: any) => total + num(h.quantity) * num(h.average_price), 0);

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
    { header: 'Current Value', value: (h: any) => (num(h.quantity) * num(h.last_price)).toFixed(2) },
    { header: 'P&L', value: (h: any) => num(h.pnl).toFixed(2) },
  ]));

  return (
    <div className="portfolio-pane">
      <style>{`
        .portfolio-pane { width:100%; min-height:100%; box-sizing:border-box; padding:18px 24px 34px; color:${COLORS.text}; }
        .portfolio-pane * { box-sizing:border-box; }
        .portfolio-section { width:100%; max-width:1120px; margin:0 auto 34px; }
        .portfolio-toolbar { display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:14px; min-height:30px; }
        .portfolio-title { margin:0; font-size:17px; line-height:1.4; font-weight:400; color:${COLORS.text}; white-space:nowrap; }
        .portfolio-title span { color:${COLORS.muted}; }
        .portfolio-tools { display:flex; align-items:center; justify-content:flex-end; gap:13px; flex-wrap:wrap; }
        .portfolio-search { position:relative; }
        .portfolio-search svg { position:absolute; left:8px; top:50%; transform:translateY(-50%); color:${COLORS.muted}; pointer-events:none; }
        .portfolio-search input { width:128px; height:27px; padding:5px 8px 5px 27px; border:1px solid #dedede; border-radius:3px; color:${COLORS.text}; background:#fff; outline:none; font:inherit; font-size:11px; }
        .portfolio-search input:focus { border-color:#bdbdbd; }
        .portfolio-table-scroll { width:100%; overflow-x:auto; scrollbar-gutter:stable; }
        .portfolio-table { width:100%; border-collapse:collapse; text-align:left; table-layout:fixed; }
        .portfolio-table tbody tr:hover { background:${COLORS.rowHover}; }
        .portfolio-table .pnl-column { background:${COLORS.pnlBg}; }
        .portfolio-row:hover .portfolio-content { visibility:hidden; }
        .portfolio-row:hover .portfolio-actions { display:flex !important; }
        .sort-header:hover { color:${COLORS.text} !important; }
        .sort-icon { opacity:0; color:${COLORS.muted}; font-size:9px; width:10px; text-align:center; }
        .sort-header:hover .sort-icon, .sort-icon.active { opacity:1; }
        .exchange-tag { margin-left:6px; font-size:9px; color:${COLORS.muted}; background:#f1f1f1; padding:1px 4px; border-radius:2px; }
        .portfolio-total-row td { border-bottom:0 !important; border-top:1px solid ${COLORS.border}; padding-top:11px !important; padding-bottom:11px !important; }
        .day-history { border-top:1px solid ${COLORS.border}; margin-top:18px; }
        .day-history button { width:100%; border:0; background:transparent; padding:14px 0; color:${COLORS.text}; font:inherit; font-size:13px; text-align:left; cursor:pointer; display:flex; align-items:center; gap:6px; }
        .day-history-content { padding:0 0 14px; color:${COLORS.muted}; font-size:12px; }
        .breakdown-section { border-top:1px solid ${COLORS.border}; padding-top:18px; margin-top:0; }
        .breakdown-section h3 { margin:0 0 22px; font-size:13px; font-weight:400; color:${COLORS.text}; }
        .breakdown-list { display:flex; flex-direction:column; gap:10px; }
        .breakdown-row { display:grid; grid-template-columns:minmax(150px,230px) minmax(260px,1fr); align-items:center; min-height:12px; }
        .breakdown-label { padding-right:14px; text-align:right; color:#777; font-size:9px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .breakdown-axis { position:relative; display:grid; grid-template-columns:1fr 1fr; height:8px; }
        .breakdown-zero { position:absolute; left:50%; top:-2px; bottom:-2px; width:1px; background:#d8d8d8; transform:translateX(-.5px); }
        .breakdown-half { display:flex; align-items:center; }
        .breakdown-half.negative { justify-content:flex-end; }
        .breakdown-half.positive { justify-content:flex-start; }
        .breakdown-bar { height:6px; min-width:2px; }
        .breakdown-bar.negative { background:${COLORS.red}; }
        .breakdown-bar.positive { background:${COLORS.blue}; }
        .engine-details { max-width:1120px; margin:28px auto 0; border-top:1px solid ${COLORS.border}; padding-top:12px; }
        .engine-details summary { cursor:pointer; color:${COLORS.text}; font-size:13px; list-style:none; padding:6px 0; }
        .engine-details summary::-webkit-details-marker { display:none; }
        @media (max-width:900px) {
          .portfolio-pane { padding:14px 14px 28px; }
          .portfolio-toolbar { align-items:flex-start; }
          .portfolio-tools { gap:9px; }
          .breakdown-row { grid-template-columns:145px minmax(220px,1fr); }
        }
        @media (max-width:680px) {
          .portfolio-toolbar { flex-direction:column; align-items:stretch; }
          .portfolio-tools { justify-content:flex-start; }
          .portfolio-search input { width:150px; }
          .breakdown-row { grid-template-columns:110px minmax(190px,1fr); }
          .breakdown-label { font-size:8px; }
        }
      `}</style>

      {showPositions && (
        <section className="portfolio-section">
          <div className="portfolio-toolbar">
            <h2 className="portfolio-title">Positions <span>({positions.length})</span></h2>
            <div className="portfolio-tools">
              {selectedPos.size > 0 && (
                <button type="button" onClick={exitSelected} disabled={exitingSelected} style={{ background: COLORS.red, color: '#fff', border: 0, borderRadius: 3, padding: '5px 11px', fontSize: 11, cursor: exitingSelected ? 'wait' : 'pointer', opacity: exitingSelected ? .65 : 1 }}>
                  {exitingSelected ? 'Exiting…' : `Exit Selected (${selectedPos.size})`}
                </button>
              )}
              <div className="portfolio-search"><SearchIcon /><input aria-label="Search positions" placeholder="Search" value={posQuery} onChange={(event) => setPosQuery(event.target.value)} /></div>
              <ToolbarLink onClick={() => setAnalyticsView('positions')}>◉ Analyze</ToolbarLink>
              <ToolbarLink muted onClick={() => setSettingsOpen(true)}>⚙ Settings</ToolbarLink>
              <ToolbarLink onClick={downloadPositions}>⇩ Download</ToolbarLink>
            </div>
          </div>

          {!positions.length ? <div style={S.hint}>No open positions.</div> : (
            <>
              <div className="portfolio-table-scroll">
                <table className="portfolio-table" style={{ minWidth: 780 }}>
                  <colgroup><col style={{ width: 42 }} /><col style={{ width: 84 }} /><col style={{ width: '31%' }} /><col style={{ width: 82 }} /><col style={{ width: 94 }} /><col style={{ width: 94 }} /><col style={{ width: 118 }} /><col style={{ width: 88 }} /></colgroup>
                  <thead><tr>
                    <th style={{ ...S.th, textAlign: 'center', paddingLeft: 6, paddingRight: 6 }}><input aria-label="Select all visible positions" type="checkbox" checked={allVisibleSelected} onChange={toggleAllPos} disabled={!selectablePosIds.length} /></th>
                    <SortHeader label="Product" sortKey="product" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={S.th} />
                    <SortHeader label="Instrument" sortKey="tradingsymbol" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={S.th} />
                    <SortHeader label="Qty." sortKey="quantity" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                    <SortHeader label="Avg." sortKey="average_price" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                    <SortHeader label="LTP" sortKey="last_price" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                    <SortHeader label="P&L" sortKey="pnl" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                    <SortHeader label="Chg." sortKey="chg" currentSort={posSort} onSort={(key: string) => toggleSort(setPosSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  </tr></thead>
                  <tbody>{sortedPositions.map((p: any) => {
                    const qty = num(p.quantity);
                    const key = positionKey(p);
                    const selected = selectedPos.has(key);
                    const chg = qty === 0 || num(p.average_price) <= 0 ? 0 : (num(p.last_price) - num(p.average_price)) / num(p.average_price) * 100;
                    return (
                      <tr key={key} className="portfolio-row" style={{ background: selected ? 'rgba(56,126,209,.05)' : undefined }}>
                        <td style={{ ...S.td, textAlign: 'center', paddingLeft: 6, paddingRight: 6 }}><input aria-label={`Select ${p.tradingsymbol} ${p.product}`} type="checkbox" checked={selected} disabled={!qty} onChange={() => togglePos(key)} title={!qty ? 'Already flat — nothing left to exit' : undefined} /></td>
                        <td style={S.td}><ProductPill product={p.product} /></td>
                        <td style={{ ...S.td, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}><InstrumentLabel symbol={p.tradingsymbol} /><span className="exchange-tag">{p.exchange}</span></td>
                        <td style={{ ...S.td, textAlign: 'right', color: qty > 0 ? COLORS.blue : qty < 0 ? COLORS.red : COLORS.muted }}>{qty}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.average_price).toFixed(2)}</td>
                        <td style={{ ...S.td, textAlign: 'right' }}>{num(p.last_price).toFixed(2)}</td>
                        <td className="pnl-column" style={{ ...S.td, textAlign: 'right', color: pnlColor(num(p.pnl)) }}>{formatMoney(num(p.pnl))}</td>
                        <td style={{ ...S.td, textAlign: 'right', color: pnlColor(chg), position: 'relative' }}>
                          {expandedConvertId === key ? (
                            <div onClick={(event) => event.stopPropagation()} style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 5 }}><ConvertControl p={p} /><button type="button" title="Close" onClick={() => setExpandedConvertId(null)} style={{ border: 0, background: 'transparent', padding: 0, color: COLORS.muted, cursor: 'pointer', fontSize: 15 }}>×</button></div>
                          ) : (
                            <><span className="portfolio-content">{chg.toFixed(2)}%</span><div className="portfolio-actions" style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', display: 'none', background: COLORS.rowHover, paddingLeft: 6, alignItems: 'center', whiteSpace: 'nowrap' }}>
                              <KiteActionButtons
                                onBuy={(event) => { event.stopPropagation(); handleOpenOrder(p, qty >= 0 ? 'BUY' : 'SELL', Math.abs(qty)); }} buyLabel="Add"
                                onSell={(event) => { event.stopPropagation(); handleOpenOrder(p, qty >= 0 ? 'SELL' : 'BUY', Math.abs(qty)); }} sellLabel="Exit"
                                onBasket={(event) => { event.stopPropagation(); if (!qty) return; addToBasket({ symbol: p.tradingsymbol, exchange: p.exchange, side: qty >= 0 ? 'SELL' : 'BUY', qty: Math.abs(qty), product: p.product, orderType: 'MARKET', price: 0, trigger: 0 }); }}
                              />
                              {!!qty && <button type="button" title={`Convert this ${p.product} position`} onClick={(event) => { event.stopPropagation(); setExpandedConvertId(key); }} style={{ border: 0, background: 'transparent', color: COLORS.muted, font: 'inherit', fontSize: 10, cursor: 'pointer', marginLeft: 5, padding: 0 }}>Convert</button>}
                            </div></>
                          )}
                        </td>
                      </tr>
                    );
                  })}</tbody>
                  <tfoot><tr className="portfolio-total-row"><td colSpan={5} /><td style={{ ...S.td, textAlign: 'right', fontSize: 12 }}>Total P&amp;L</td><td className="pnl-column" style={{ ...S.td, textAlign: 'right', color: pnlColor(totalPosPnl), fontSize: 14 }}>{formatMoney(totalPosPnl)}</td><td /></tr></tfoot>
                </table>
              </div>

              <div className="day-history">
                <button type="button" onClick={() => setHistoryOpen((open) => !open)}>Day&apos;s history <span style={{ color: COLORS.muted, transform: historyOpen ? 'rotate(180deg)' : undefined }}>⌄</span></button>
                {historyOpen && <div className="day-history-content">The table already includes open and closed intraday legs returned by Kite, including realised P&amp;L rows with zero quantity.</div>}
              </div>
              <PositionBreakdown positions={positions} />
              <details className="engine-details" open={engineOpen} onToggle={(event) => setEngineOpen((event.currentTarget as HTMLDetailsElement).open)}><summary>Engine Positions <span style={{ color: COLORS.muted }}>{engineOpen ? '⌃' : '⌄'}</span></summary><EnginePositionsPane /></details>
            </>
          )}
        </section>
      )}

      {showHoldings && (
        <section className="portfolio-section">
          <div className="portfolio-toolbar">
            <h2 className="portfolio-title">Holdings <span>({holdings?.length || 0})</span></h2>
            <div className="portfolio-tools">
              <div className="portfolio-search"><SearchIcon /><input aria-label="Search holdings" placeholder="Search" value={holdQuery} onChange={(event) => setHoldQuery(event.target.value)} /></div>
              <ToolbarLink onClick={() => setAnalyticsView('holdings')}>◉ Analyze</ToolbarLink>
              <ToolbarLink onClick={downloadHoldings}>⇩ Download</ToolbarLink>
              <AuthoriseHoldingsButton />
            </div>
          </div>
          {!holdings?.length ? <div style={S.hint}>No equity holdings.</div> : (
            <div className="portfolio-table-scroll">
              <table className="portfolio-table" style={{ minWidth: 820 }}>
                <thead><tr>
                  <SortHeader label="Instrument" sortKey="tradingsymbol" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={S.th} />
                  <SortHeader label="Qty." sortKey="quantity" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="Avg. cost" sortKey="average_price" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="LTP" sortKey="last_price" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="Cur. val" sortKey="curVal" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="P&L" sortKey="pnl" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="Net chg." sortKey="netChg" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                  <SortHeader label="Day chg." sortKey="dayChg" currentSort={holdSort} onSort={(key: string) => toggleSort(setHoldSort, key)} style={{ ...S.th, textAlign: 'right' }} />
                </tr></thead>
                <tbody>{sortedHoldings.map((h: any, index: number) => {
                  const pnl = num(h.pnl);
                  const currentValue = num(h.quantity) * num(h.last_price);
                  const netChange = num(h.average_price) ? (num(h.last_price) - num(h.average_price)) / num(h.average_price) * 100 : 0;
                  const dayChangePct = num(h.day_change_percentage);
                  return (
                    <tr key={`${h.exchange}:${h.tradingsymbol}:${index}`} className="portfolio-row">
                      <td style={{ ...S.td, whiteSpace: 'nowrap' }}><InstrumentLabel symbol={h.tradingsymbol} /><span className="exchange-tag">{h.exchange}</span>{num(h.t1_quantity) > 0 && <span title={`${num(h.t1_quantity)} shares are not settled`} style={{ marginLeft: 6, fontSize: 9, color: '#f57c00', background: 'rgba(245,124,0,.09)', padding: '1px 4px', borderRadius: 2 }}>T1: {num(h.t1_quantity)}</span>}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{num(h.quantity)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{num(h.average_price).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{num(h.last_price).toFixed(2)}</td>
                      <td style={{ ...S.td, textAlign: 'right' }}>{currentValue.toFixed(2)}</td>
                      <td className="pnl-column" style={{ ...S.td, textAlign: 'right', color: pnlColor(pnl) }}>{formatMoney(pnl)}</td>
                      <td style={{ ...S.td, textAlign: 'right', color: pnlColor(netChange) }}>{netChange.toFixed(2)}%</td>
                      <td style={{ ...S.td, textAlign: 'right', color: pnlColor(dayChangePct), position: 'relative' }}><span className="portfolio-content">{dayChangePct.toFixed(2)}%</span><div className="portfolio-actions" style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', display: 'none', background: COLORS.rowHover, paddingLeft: 6 }}><KiteActionButtons onBuy={(event) => { event.stopPropagation(); handleOpenOrder(h, 'BUY', num(h.quantity)); }} buyLabel="Add" onSell={(event) => { event.stopPropagation(); handleOpenOrder(h, 'SELL', Math.max(0, num(h.quantity) - num(h.t1_quantity))); }} sellLabel="Exit" onBasket={(event) => { event.stopPropagation(); const qty = Math.max(0, num(h.quantity) - num(h.t1_quantity)); if (!qty) return; addToBasket({ symbol: h.tradingsymbol, exchange: h.exchange, side: 'SELL', qty, product: h.product || 'CNC', orderType: 'MARKET', price: 0, trigger: 0 }); }} /></div></td>
                    </tr>
                  );
                })}</tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 24, padding: '13px 12px', borderTop: `1px solid ${COLORS.border}`, fontSize: 12 }}>
                <span><span style={{ color: COLORS.muted, marginRight: 7 }}>Total investment</span>{formatMoney(totalHoldingsInvestment, false)}</span>
                <span><span style={{ color: COLORS.muted, marginRight: 7 }}>Current value</span>{formatMoney(totalHoldingsVal, false)}</span>
                <span style={{ color: pnlColor(totalHoldingsDayPnl) }}><span style={{ color: COLORS.muted, marginRight: 7 }}>Day&apos;s P&amp;L</span>{formatMoney(totalHoldingsDayPnl)}</span>
                <span style={{ color: pnlColor(totalHoldingsPnl) }}><span style={{ color: COLORS.muted, marginRight: 7 }}>Total P&amp;L</span>{formatMoney(totalHoldingsPnl)}</span>
              </div>
            </div>
          )}
          <AuctionsSection />
        </section>
      )}

      {analyticsView && <KitePortfolioAnalyticsModal view={analyticsView} positions={sortedPositions} holdings={sortedHoldings} onClose={() => setAnalyticsView(null)} />}
      {settingsOpen && <KiteSettingsPopover onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import { k, Icons } from '../../styles/kiteUI';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { useKiteOptionChain } from '../../hooks/useKiteOptionChain';

export type InstrumentTab = 'chart' | 'option-chain' | 'fundamentals';

interface InstrumentPaneProps {
  symbol: string;
  initialTab?: InstrumentTab;
}

const TABS: { id: InstrumentTab; label: string }[] = [
  { id: 'chart', label: 'Chart' },
  { id: 'option-chain', label: 'Option chain' },
  { id: 'fundamentals', label: 'Fundamentals' },
];

export function InstrumentPane({ symbol, initialTab = 'chart' }: InstrumentPaneProps) {
  const [tab, setTab] = useState<InstrumentTab>(initialTab);

  useEffect(() => {
    setTab(initialTab);
  }, [symbol, initialTab]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.surface, border: `1px solid ${k.border}`, borderRadius: 4, overflow: 'hidden', fontFamily: k.fontFamily }}>
      {/* ── Tabs ── */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${k.border}`, background: k.bg }}>
        {TABS.map((tItem) => (
          <div
            key={tItem.id}
            onClick={() => setTab(tItem.id)}
            style={{
              padding: '12px 20px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: tab === tItem.id ? 500 : 400,
              color: tab === tItem.id ? k.orange : k.dim,
              borderBottom: tab === tItem.id ? `2px solid ${k.orange}` : '2px solid transparent',
              transition: 'color 0.2s',
            }}
          >
            {tItem.label}
          </div>
        ))}
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'chart' && <ChartView symbol={symbol} />}
        {tab === 'option-chain' && <OptionChainView symbol={symbol} />}
        {tab === 'fundamentals' && (
          <div style={{ padding: 32, textAlign: 'center', color: k.dim }}>Fundamentals data not available.</div>
        )}
      </div>
    </div>
  );
}

// ─── Chart View ─────────────────────────────────────────────────────────────

function ChartView({ symbol }: { symbol: string }) {
  const [tf, setTf] = useState('5m');
  const { data: candles } = useCandles(symbol, tf, 500);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !candles?.length) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: k.bg },
        textColor: k.dim,
        fontFamily: k.fontFamily,
      },
      grid: {
        vertLines: { color: k.border },
        horzLines: { color: k.border },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#fff',
      downColor: k.red,
      borderUpColor: k.green,
      borderDownColor: k.red,
      wickUpColor: k.green,
      wickDownColor: k.red,
    });

    const validCandles = candles.filter(c => c.time != null && !isNaN(c.time));
    const sorted = [...validCandles].sort((a, b) => a.time - b.time);
    const unique = sorted.filter((v, i, a) => i === 0 || v.time !== a[i - 1].time);

    const data = unique.map((b) => ({
      time: b.time as any,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    }));
    series.setData(data);
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth, height: containerRef.current.clientHeight });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
    };
  }, [candles]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: k.fontFamily }}>
      {/* Chart toolbar */}
      <div style={{ padding: '8px 16px', borderBottom: `1px solid ${k.border}`, display: 'flex', gap: 16, alignItems: 'center', background: k.bg }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: k.text }}>{symbol.split(':')[1] || symbol}</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {['1m', '5m', '15m'].map((t) => (
            <button
              key={t}
              onClick={() => setTf(t)}
              style={{
                background: tf === t ? k.surfaceHover : k.bg,
                border: `1px solid ${k.border}`,
                color: tf === t ? k.orange : k.text,
                borderRadius: 4,
                padding: '4px 8px',
                fontSize: 12,
                cursor: 'pointer',
                fontWeight: tf === t ? 500 : 400
              }}
            >
              {t}
            </button>
          ))}
        </div>
        <span style={{ color: k.blue, fontSize: 12, cursor: 'pointer' }}>Indicators ⊞</span>
      </div>
      {/* Chart Body */}
      <div style={{ flex: 1, position: 'relative', background: k.bg, overflow: 'hidden' }}>
        {!candles?.length && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.dim }}>
            Loading chart data...
          </div>
        )}
        <div ref={containerRef} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />
      </div>
    </div>
  );
}

// ─── Option Chain View ──────────────────────────────────────────────────────

type ViewMode = 'oi' | 'greeks';

/* ⚠️ PLACEHOLDER DATA — this chain is generated client-side to be NIFTY-shaped so
 * the layout is realistic. It is NOT live Kite data. Wire /api/v1/options/chain
 * (KiteClient.get_option_chain) + a live spot/quote feed to make it real. */
const SPOT = 23949.35;
const SPOT_CHANGE = -118.45;
const SPOT_PCT = -0.49;
const STRIKE_STEP = 50;
const ATM_STRIKE = Math.round(SPOT / STRIKE_STEP) * STRIKE_STEP; // 23950

const chg = (lo: number, hi: number) => Number((lo + Math.random() * (hi - lo)).toFixed(2));

function buildChain(expiryIdx: number) {
  const tMult = 1 + expiryIdx * 0.55;   // farther expiry → fatter premium / time value
  const oiScale = 1 + expiryIdx * 0.18; // farther expiry → different OI footprint
  const start = ATM_STRIKE - 11 * STRIKE_STEP;
  return Array.from({ length: 24 }).map((_, i) => {
    const strike = start + i * STRIKE_STEP;
    const isAtm = strike === ATM_STRIKE;
    const dist = Math.abs(strike - SPOT);
    const intrinsicC = Math.max(0, SPOT - strike);
    const intrinsicP = Math.max(0, strike - SPOT);
    const tv = Math.max(3, 90 - dist / 7) * tMult;          // time value peaks at ATM
    const iv = 11 + dist / 400;                              // vol smile
    const vega = Math.max(1.5, 12 - dist / 60);
    const gamma = Math.max(0.0002, 0.0014 - dist / 5_000_000);
    const theta = -3 - tv / 14;
    return {
      strike, isAtm,
      call: {
        ltp: (intrinsicC + tv).toFixed(2),
        ltpChg: chg(-48, -22),
        oi: (Math.random() * 480 * oiScale).toFixed(2),
        oiChg: chg(-20, 90),
        iv: iv.toFixed(2),
        delta: Math.max(0.02, Math.min(0.98, 0.5 + (SPOT - strike) / 700)).toFixed(2),
        theta: theta.toFixed(2), vega: vega.toFixed(2), gamma: gamma.toFixed(4),
      },
      put: {
        ltp: (intrinsicP + tv).toFixed(2),
        ltpChg: chg(20, 165),
        oi: (Math.random() * 320 * oiScale).toFixed(2),
        oiChg: chg(-28, 50),
        iv: iv.toFixed(2),
        delta: Math.max(-0.98, Math.min(-0.02, -0.5 + (SPOT - strike) / 700)).toFixed(2),
        theta: theta.toFixed(2), vega: vega.toFixed(2), gamma: gamma.toFixed(4),
      },
    };
  });
}

const EXPIRIES = [
  { label: '23 Jun', dte: '4 days', weekly: true },
  { label: '30 Jun', dte: '11 days', weekly: false },
  { label: '7 Jul', dte: '3 weeks', weekly: true },
];
const EXPIRY_DROPDOWN = ['14 Jul (4 weeks)', '21 Jul (5 weeks)', '28 Jul (6 weeks)'];

// One stable chain per expiry option (3 pills + 3 dropdown) so switching is visible.
const CHAINS = Array.from({ length: EXPIRIES.length + EXPIRY_DROPDOWN.length }).map((_, i) => buildChain(i));
const MAX_OIS = CHAINS.map((c) => Math.max(...c.flatMap((r) => [Number(r.call.oi), Number(r.put.oi)])));

const FOOTER_STATS = [
  { label: 'PCR', value: '0.68' },
  { label: 'Max Pain', value: '23950' },
  { label: 'ATM IV', value: '11.50' },
  { label: 'IV Percentile', value: '54.00 - High' },
];

// Toolbar icons (match Kite's link row)
const SettingsIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>
);
const PopoutIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
);

function OptionChainView({ symbol }: { symbol: string }) {
  const [viewMode, setViewMode] = useState<ViewMode>('oi');
  const [expiry, setExpiry] = useState(0);
  const [hoverRow, setHoverRow] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState<{ strike: number; side: 'call' | 'put'; top: number; left: number } | null>(null);

  const openOrderWindow = useOrderWindowStore(s => s.openOrderWindow);
  const { data: live } = useKiteOptionChain(symbol);

  const handleAction = (e: React.MouseEvent, type: 'call' | 'put', side: 'BUY' | 'SELL', row: any) => {
    e.stopPropagation();
    const isCall = type === 'call';
    const optSym = `${symbol.split(':')[1] || symbol}${row.strike}${isCall ? 'CE' : 'PE'}`; 
    const ltp = isCall ? Number(row.call.ltp) : Number(row.put.ltp);

    openOrderWindow({
      symbol: optSym,
      exchange: 'NFO',
      initialSide: side,
      initialQty: 15,
      lastPrice: ltp,
      lotSize: 15,
    });
  };

  const handleMenuClick = (e: React.MouseEvent, strike: number, side: 'call' | 'put') => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuOpen({ strike, side, top: rect.bottom + 4, left: rect.left });
  };

  useEffect(() => {
    const closeMenu = () => setMenuOpen(null);
    window.addEventListener('click', closeMenu);
    return () => window.removeEventListener('click', closeMenu);
  }, []);

  const name = symbol.split(':')[1] || symbol;
  const linkStyle: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', whiteSpace: 'nowrap' };
  const OI_GRID = '1.3fr 1.3fr 96px 1.3fr 1.3fr';
  const GREEKS_GRID = '1fr 1fr 1fr 1fr 1fr 80px 100px 80px 1fr 1fr 1fr 1fr 1fr';

  const Chg = ({ v }: { v: number }) => (
    <span style={{ fontSize: 11.5, color: v >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>{v.toFixed(2)}%</span>
  );
  const Val = ({ children }: { children: React.ReactNode }) => (
    <span style={{ color: k.text, fontVariantNumeric: 'tabular-nums', minWidth: 50, textAlign: 'inherit' }}>{children}</span>
  );

  // ── Data source: live per-symbol Kite chain when available, else placeholder ──
  const liveExpiries = live?.expiries ?? [];
  const isLive = !!(live && liveExpiries.length && live.chain);

  type RLeg = { ltp: string; oi: string; iv: string; delta: string; theta: string; vega: string; gamma: string; ltpChg: number | null; oiChg: number | null };
  type RRow = { strike: number; isAtm: boolean; call: RLeg; put: RLeg };
  const EMPTY_LEG: RLeg = { ltp: '–', oi: '0', iv: '–', delta: '–', theta: '–', vega: '–', gamma: '–', ltpChg: null, oiChg: null };
  const normLeg = (l: any): RLeg => {
    if (!l) return EMPTY_LEG;
    if (typeof l.ltp === 'string') return l as RLeg;   // placeholder rows already in shape
    return {
      ltp: Number(l.ltp).toFixed(2), oi: Number(l.oi).toFixed(2), iv: Number(l.iv).toFixed(2),
      delta: Number(l.delta).toFixed(2), theta: Number(l.theta).toFixed(2),
      vega: Number(l.vega).toFixed(2), gamma: Number(l.gamma).toFixed(4),
      ltpChg: null, oiChg: null,
    };
  };

  const expiryPills = isLive
    ? liveExpiries.slice(0, 3).map((e) => ({ text: `${e.label} (${e.dte} ${e.dte === 1 ? 'day' : 'days'})`, weekly: false }))
    : EXPIRIES.map((e) => ({ text: `${e.label} (${e.dte})`, weekly: e.weekly }));
  const dropdownItems = isLive ? liveExpiries.slice(3).map((e) => `${e.label} (${e.dte} days)`) : EXPIRY_DROPDOWN;
  const pillCount = expiryPills.length;

  const optionCount = isLive ? liveExpiries.length : CHAINS.length;
  const selIdx = Math.min(expiry, Math.max(0, optionCount - 1));
  const rawRows: any[] = isLive ? (live!.chain[liveExpiries[selIdx]?.date] ?? []) : (CHAINS[selIdx] ?? CHAINS[0]);
  const rows: RRow[] = rawRows.map((r) => ({ strike: r.strike, isAtm: r.isAtm, call: normLeg(r.call), put: normLeg(r.put) }));
  const MAX_OI = Math.max(1, ...rows.map((r) => Math.max(Number(r.call.oi) || 0, Number(r.put.oi) || 0)));

  const spot = isLive ? live!.spot : SPOT;
  const spotChange = isLive ? null : SPOT_CHANGE;
  const spotPct = isLive ? null : SPOT_PCT;

  let footer = FOOTER_STATS;
  if (isLive) {
    const sumCall = rawRows.reduce((s, r) => s + (r.call?.oi || 0), 0);
    const sumPut = rawRows.reduce((s, r) => s + (r.put?.oi || 0), 0);
    const atmRow = rawRows.find((r) => r.isAtm);
    const atmIv = atmRow?.call?.iv ?? atmRow?.put?.iv;
    // Max pain = strike minimising total option-writer payout across the chain.
    let maxPain = '–', bestLoss = Infinity;
    for (const kRow of rawRows) {
      let loss = 0;
      for (const s of rawRows) {
        loss += (s.call?.oi || 0) * Math.max(0, kRow.strike - s.strike);
        loss += (s.put?.oi || 0) * Math.max(0, s.strike - kRow.strike);
      }
      if (loss < bestLoss) { bestLoss = loss; maxPain = String(kRow.strike); }
    }
    footer = [
      { label: 'PCR', value: sumCall > 0 ? (sumPut / sumCall).toFixed(2) : '–' },
      { label: 'Max Pain', value: maxPain },
      { label: 'ATM IV', value: atmIv != null ? Number(atmIv).toFixed(2) : '–' },
      { label: 'IV Percentile', value: '–' },
    ];
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', fontFamily: k.fontFamily, background: k.bg }}>
      {/* Instrument header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px 6px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ fontSize: 18, fontWeight: 600, color: '#333' }}>{name}</span>
          <span style={{ fontSize: 14, fontWeight: 500, color: (spotPct ?? 0) >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
            {spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
          {spotPct != null && spotChange != null && (
            <span style={{ fontSize: 13, color: spotPct >= 0 ? k.green : k.red, fontVariantNumeric: 'tabular-nums' }}>
              {spotPct >= 0 ? '+' : ''}{spotChange.toFixed(2)} ({spotPct >= 0 ? '+' : ''}{spotPct.toFixed(2)}%)
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: k.dim, cursor: 'pointer' }}>
          <span style={{ width: 16, height: 16, background: k.orange, borderRadius: 3, color: '#fff', fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>S</span>
          View on Sensibull
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '2px 16px 12px', gap: 12 }}>
        {/* Expiries + OI/Greeks */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {expiryPills.map((e, idx) => (
            <span
              key={e.text}
              onClick={() => setExpiry(idx)}
              style={{
                fontSize: 12.5, cursor: 'pointer', padding: '5px 11px', borderRadius: 16, whiteSpace: 'nowrap',
                background: selIdx === idx ? '#e7f0fe' : 'transparent',
                color: selIdx === idx ? k.blue : k.text,
                fontWeight: selIdx === idx ? 500 : 400,
              }}
            >
              {e.text}{e.weekly && <sup style={{ fontSize: 8, color: k.dim, marginLeft: 1 }}>w</sup>}
            </span>
          ))}
          {dropdownItems.length > 0 && (
          <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}>
            <select
              value={selIdx >= pillCount ? selIdx - pillCount : -1}
              onChange={(ev) => setExpiry(pillCount + Number(ev.target.value))}
              style={{ appearance: 'none', background: k.bg, color: selIdx >= pillCount ? k.blue : k.text, border: `1px solid ${k.border}`, borderRadius: 6, padding: '5px 26px 5px 11px', fontSize: 12.5, outline: 'none', cursor: 'pointer', fontFamily: k.fontFamily }}
            >
              <option value={-1} disabled hidden>{dropdownItems[0]}</option>
              {dropdownItems.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
            <span style={{ position: 'absolute', right: 9, pointerEvents: 'none', color: k.dim, display: 'flex' }}><Icons.ChevronDown /></span>
          </div>
          )}
          <div style={{ width: 1, height: 18, background: k.border, margin: '0 8px' }} />
          <span onClick={() => setViewMode('oi')} style={{ fontSize: 12.5, cursor: 'pointer', padding: '5px 14px', borderRadius: 16, background: viewMode === 'oi' ? '#e7f0fe' : 'transparent', color: viewMode === 'oi' ? k.blue : k.text, fontWeight: viewMode === 'oi' ? 500 : 400 }}>OI</span>
          <span onClick={() => setViewMode('greeks')} style={{ fontSize: 12.5, cursor: 'pointer', padding: '5px 12px', borderRadius: 16, background: viewMode === 'greeks' ? '#e7f0fe' : 'transparent', color: viewMode === 'greeks' ? k.blue : k.dim, fontWeight: viewMode === 'greeks' ? 500 : 400 }}>Greeks</span>
        </div>

        {/* Right actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, color: k.blue, fontSize: 12.5 }}>
          <span style={linkStyle}><Icons.Search /> Search</span>
          <span style={linkStyle}><SettingsIcon /> Settings</span>
          <span style={linkStyle}><PopoutIcon /> Popout</span>
          <div style={{ width: 1, height: 18, background: k.border }} />
          <span style={{ ...linkStyle, color: k.dim }}><Icons.Basket /> Basket</span>
          <div style={{ width: 30, height: 16, borderRadius: 10, background: k.border, position: 'relative', cursor: 'pointer' }}>
            <div style={{ position: 'absolute', top: 2, left: 2, width: 12, height: 12, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,0.2)' }} />
          </div>
        </div>
      </div>

      {/* Table Header */}
      <div style={{ display: 'grid', gridTemplateColumns: viewMode === 'oi' ? OI_GRID : GREEKS_GRID, padding: '9px 16px', borderTop: `1px solid ${k.border}`, borderBottom: `1px solid ${k.border}`, fontSize: 11.5, color: k.dim, textAlign: 'center', background: k.bg }}>
        {viewMode === 'oi' ? (
          <>
            <div style={{ textAlign: 'right', paddingRight: 12 }}>OI (in lakhs)</div>
            <div style={{ textAlign: 'right', paddingRight: 14 }}>Call LTP</div>
            <div>Strike</div>
            <div style={{ textAlign: 'left', paddingLeft: 14 }}>Put LTP</div>
            <div style={{ textAlign: 'left', paddingLeft: 12 }}>OI (in lakhs)</div>
          </>
        ) : (
          <>
            <div style={{ textAlign: 'right' }}>Gamma</div>
            <div style={{ textAlign: 'right' }}>Vega</div>
            <div style={{ textAlign: 'right' }}>Theta</div>
            <div style={{ textAlign: 'right' }}>Delta</div>
            <div style={{ textAlign: 'right' }}>IV</div>
            <div style={{ textAlign: 'right', paddingRight: 16 }}>Call LTP</div>
            <div style={{ fontWeight: 500 }}>Strike</div>
            <div style={{ textAlign: 'left', paddingLeft: 16 }}>Put LTP</div>
            <div style={{ textAlign: 'left' }}>IV</div>
            <div style={{ textAlign: 'left' }}>Delta</div>
            <div style={{ textAlign: 'left' }}>Theta</div>
            <div style={{ textAlign: 'left' }}>Vega</div>
            <div style={{ textAlign: 'left' }}>Gamma</div>
          </>
        )}
      </div>

      {/* Table Body */}
      <div style={{ flex: 1, overflowY: 'auto', background: k.bg }}>
        {MOCK_CHAIN.map((row) => {
          const isHover = hoverRow === row.strike;
          const itmCall = row.strike < SPOT;   // calls below spot are ITM (shade left)
          const itmPut = row.strike > SPOT;    // puts above spot are ITM (shade right)
          const callBar = Math.min(46, (Number(row.call.oi) / MAX_OI) * 46);
          const putBar = Math.min(46, (Number(row.put.oi) / MAX_OI) * 46);
          return (
              <div
              key={row.strike}
              onMouseEnter={() => setHoverRow(row.strike)}
              onMouseLeave={() => setHoverRow(null)}
              style={{
                display: 'grid',
                gridTemplateColumns: viewMode === 'oi' ? OI_GRID : GREEKS_GRID,
                padding: '0 16px',
                minHeight: 42,
                fontSize: 12.5,
                color: k.text,
                textAlign: 'center',
                alignItems: 'center',
                background: isHover ? k.surfaceHover : k.bg,
                position: 'relative',
              }}
            >
              {viewMode === 'oi' ? (
                <>
                  {/* ITM shading */}
                  {itmCall && <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: '50%', background: 'rgba(0,0,0,0.032)', pointerEvents: 'none', zIndex: 0 }} />}
                  {itmPut && <div style={{ position: 'absolute', top: 0, bottom: 0, left: '50%', right: 0, background: 'rgba(0,0,0,0.032)', pointerEvents: 'none', zIndex: 0 }} />}
                  {/* OI bars (center-anchored) */}
                  <div style={{ position: 'absolute', left: 0, right: 0, bottom: 6, height: 2, pointerEvents: 'none', zIndex: 1 }}>
                    <div style={{ position: 'absolute', right: '50%', width: `${callBar}%`, height: 2, background: 'rgba(223,81,76,0.7)' }} />
                    <div style={{ position: 'absolute', left: '50%', width: `${putBar}%`, height: 2, background: 'rgba(76,175,80,0.75)' }} />
                  </div>

                  {/* Call OI: change + value */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 14, paddingRight: 12, zIndex: 2 }}>
                    <Chg v={row.call.oiChg} />
                    <Val>{row.call.oi}</Val>
                  </div>
                  {/* Call LTP: change + value */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 14, paddingRight: 14, position: 'relative', zIndex: 2 }}>
                    <Chg v={row.call.ltpChg} />
                    <Val>{row.call.ltp}</Val>
                    {isHover && (
                      <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center', zIndex: 3, boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }}>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'call')}><Icons.More /></button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button onClick={(e) => handleAction(e, 'call', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button onClick={(e) => handleAction(e, 'call', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                      </div>
                    )}
                  </div>
                  {/* Strike */}
                  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', borderLeft: `1px solid ${k.border}`, borderRight: `1px solid ${k.border}`, height: '100%', zIndex: 2 }}>
                    {row.isAtm ? (
                      <span style={{ background: '#3c3c3c', color: '#fff', fontWeight: 600, fontSize: 12.5, padding: '4px 11px', borderRadius: 4 }}>{row.strike}</span>
                    ) : (
                      <span style={{ fontWeight: 600, color: '#333', fontSize: 12.5 }}>{row.strike}</span>
                    )}
                  </div>
                  {/* Put LTP: value + change */}
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: 14, paddingLeft: 14, position: 'relative', zIndex: 2 }}>
                    {isHover && (
                      <div style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center', zIndex: 3, boxShadow: '0 1px 4px rgba(0,0,0,0.12)' }}>
                        <button onClick={(e) => handleAction(e, 'put', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                        <button onClick={(e) => handleAction(e, 'put', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'put')}><Icons.More /></button>
                      </div>
                    )}
                    <Val>{row.put.ltp}</Val>
                    <Chg v={row.put.ltpChg} />
                  </div>
                  {/* Put OI: value + change */}
                  <div style={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', gap: 14, paddingLeft: 12, zIndex: 2 }}>
                    <Val>{row.put.oi}</Val>
                    <Chg v={row.put.oiChg} />
                  </div>
                </>
              ) : (
                <>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.gamma}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.vega}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.theta}</div>
                  <div style={{ textAlign: 'right', color: k.dim }}>{row.call.delta}</div>
                  <div style={{ textAlign: 'right', color: k.text }}>{row.call.iv}</div>
                  <div style={{ textAlign: 'right', paddingRight: 16, fontWeight: 500, position: 'relative' }}>
                    {row.call.ltp}
                    {isHover && (
                      <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center' }}>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'call')}><Icons.More /></button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button onClick={(e) => handleAction(e, 'call', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button onClick={(e) => handleAction(e, 'call', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                      </div>
                    )}
                  </div>
                  <div style={{ fontWeight: 600, background: row.isAtm ? k.border : k.surface, padding: '4px 0', borderRadius: 4, display: 'inline-block', margin: '0 auto', width: 60 }}>
                    {row.strike}
                  </div>
                  <div style={{ textAlign: 'left', paddingLeft: 16, fontWeight: 500, position: 'relative' }}>
                    {row.put.ltp}
                    {isHover && (
                      <div style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 6, background: k.surfaceHover, padding: '4px 8px', borderRadius: 4, alignItems: 'center' }}>
                        <button onClick={(e) => handleAction(e, 'put', 'BUY', row)} style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                        <button onClick={(e) => handleAction(e, 'put', 'SELL', row)} style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, fontSize: 14 }}>⊞</button>
                        <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, color: k.dim, display: 'flex', alignItems: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'put')}><Icons.More /></button>
                      </div>
                    )}
                  </div>
                  <div style={{ textAlign: 'left', color: k.text }}>{row.put.iv}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.delta}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.theta}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.vega}</div>
                  <div style={{ textAlign: 'left', color: k.dim }}>{row.put.gamma}</div>
                </>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', borderTop: `1px solid ${k.border}`, background: k.bg, padding: '10px 16px' }}>
        {FOOTER_STATS.map((s) => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: k.dim, marginBottom: 3 }}>{s.label}</div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: '#333', fontVariantNumeric: 'tabular-nums' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Popover Menu */}
      {menuOpen && (
        <div
          style={{
            position: 'fixed',
            top: menuOpen.top,
            left: menuOpen.left,
            background: k.bg,
            border: `1px solid ${k.border}`,
            borderRadius: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            padding: '8px 0',
            zIndex: 100,
            minWidth: 180,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {[
            { label: 'Chart', icon: <Icons.Chart /> },
            { label: 'Create GTT / GTC', icon: <Icons.Timer /> },
            { label: 'Create alert / ATO', icon: <Icons.Bell /> },
            { label: 'Market depth', icon: <Icons.Depth /> },
            { label: 'Add to marketwatch', icon: <Icons.More /> },
            { label: 'Add to basket', icon: <Icons.Basket /> },
          ].map((item, idx) => (
            <div
              key={idx}
              style={{
                padding: '8px 16px',
                fontSize: 13,
                color: k.text,
                cursor: 'pointer',
                display: 'flex',
                gap: 12,
                alignItems: 'center',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = k.surfaceHover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              <span style={{ color: k.dim, display: 'flex', alignItems: 'center' }}>{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

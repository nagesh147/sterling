import React, { useState, useEffect, useRef } from 'react';
import { k, tint, Icons } from '../../styles/kiteUI';
import { createChart, ColorType, CandlestickSeries } from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';

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

const MOCK_CHAIN = Array.from({ length: 20 }).map((_, i) => {
  const strike = 74500 + i * 100;
  const isAtm = strike === 75500;
  return {
    strike,
    isAtm,
    call: { ltp: (1000 - i * 45).toFixed(2), oi: (Math.random() * 500).toFixed(2), iv: (14 + Math.random() * 2).toFixed(2), delta: (0.8 - i * 0.03).toFixed(2), theta: (-40 - Math.random() * 10).toFixed(2), vega: (30 + Math.random() * 10).toFixed(2), gamma: '0.0002' },
    put: { ltp: (10 + i * 40).toFixed(2), oi: (Math.random() * 300).toFixed(2), iv: (15 + Math.random() * 2).toFixed(2), delta: (-0.1 - i * 0.04).toFixed(2), theta: (-40 - Math.random() * 10).toFixed(2), vega: (30 + Math.random() * 10).toFixed(2), gamma: '0.0002' },
  };
});

function OptionChainView({ symbol }: { symbol: string }) {
  const [viewMode, setViewMode] = useState<ViewMode>('oi');
  const [hoverRow, setHoverRow] = useState<number | null>(null);
  const [menuOpen, setMenuOpen] = useState<{ strike: number; side: 'call' | 'put'; top: number; left: number } | null>(null);

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative', fontFamily: k.fontFamily }}>
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderBottom: `1px solid ${k.border}`, background: k.surface }}>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ fontSize: 16, fontWeight: 500, color: k.text }}>{symbol.split(':')[1] || symbol}</span>
          <span style={{ fontSize: 13, color: k.green }}>75,527.95 <span style={{ fontSize: 11 }}>1,695.40 (2.30%)</span></span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: k.dim }}>Expiry:</span>
          <select style={{ background: k.bg, color: k.text, border: `1px solid ${k.border}`, borderRadius: 4, padding: '4px 8px', fontSize: 12, outline: 'none' }}>
            <option>18 Jun (5 days)</option>
            <option>25 Jun (12 days)</option>
          </select>
          <div style={{ display: 'flex', background: k.surface, borderRadius: 20, border: `1px solid ${k.border}`, overflow: 'hidden', marginLeft: 16, padding: 2 }}>
            <button
              onClick={() => setViewMode('oi')}
              style={{ padding: '4px 16px', fontSize: 12, cursor: 'pointer', border: 'none', borderRadius: 18, background: viewMode === 'oi' ? k.blue : 'transparent', color: viewMode === 'oi' ? '#fff' : k.dim, fontWeight: viewMode === 'oi' ? 500 : 400 }}
            >
              OI
            </button>
            <button
              onClick={() => setViewMode('greeks')}
              style={{ padding: '4px 16px', fontSize: 12, cursor: 'pointer', border: 'none', borderRadius: 18, background: viewMode === 'greeks' ? k.blue : 'transparent', color: viewMode === 'greeks' ? '#fff' : k.dim, fontWeight: viewMode === 'greeks' ? 500 : 400 }}
            >
              Greeks
            </button>
          </div>
        </div>
      </div>

      {/* Table Header */}
      <div style={{ display: 'grid', gridTemplateColumns: viewMode === 'oi' ? '1fr 1fr 100px 1fr 1fr' : '1fr 1fr 1fr 1fr 1fr 80px 100px 80px 1fr 1fr 1fr 1fr 1fr', padding: '8px 16px', borderBottom: `1px solid ${k.border}`, fontSize: 11, color: k.dim, textAlign: 'center', background: k.bg }}>
        {viewMode === 'oi' ? (
          <>
            <div style={{ textAlign: 'right' }}>OI (in lakhs)</div>
            <div style={{ textAlign: 'right', paddingRight: 32 }}>Call LTP</div>
            <div style={{ fontWeight: 500 }}>Strike</div>
            <div style={{ textAlign: 'left', paddingLeft: 32 }}>Put LTP</div>
            <div style={{ textAlign: 'left' }}>OI (in lakhs)</div>
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
          return (
              <div
              key={row.strike}
              onMouseEnter={() => setHoverRow(row.strike)}
              onMouseLeave={() => setHoverRow(null)}
              style={{
                display: 'grid',
                gridTemplateColumns: viewMode === 'oi' ? '1fr 1fr 100px 1fr 1fr' : '1fr 1fr 1fr 1fr 1fr 80px 100px 80px 1fr 1fr 1fr 1fr 1fr',
                padding: '10px 16px',
                borderBottom: `1px solid ${k.border}`,
                fontSize: 12,
                color: k.text,
                textAlign: 'center',
                alignItems: 'center',
                background: row.isAtm ? tint(k.border, 30) : (isHover ? k.surfaceHover : k.bg),
                position: 'relative'
              }}
            >
              {viewMode === 'oi' ? (
                <>
                  <div style={{ textAlign: 'right', color: k.dim }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
                      <div style={{ width: 40, height: 4, background: k.border, borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: k.green, width: `${Math.min(100, Number(row.call.oi) / 5)}%` }} />
                      </div>
                      {row.call.oi}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', paddingRight: 32, fontWeight: 500, position: 'relative' }}>
                    {row.call.ltp}
                    {isHover && (
                      <div style={{ position: 'absolute', right: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 4 }}>
                        <button style={{ background: k.surface, color: k.dim, border: `1px solid ${k.border}`, borderRadius: 2, width: 24, height: 20, fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'call')}>
                          <Icons.More />
                        </button>
                      </div>
                    )}
                  </div>
                  <div style={{ fontWeight: 600, background: row.isAtm ? k.border : k.surface, padding: '4px 0', borderRadius: 4, display: 'inline-block', margin: '0 auto', width: 60 }}>
                    {row.strike}
                  </div>
                  <div style={{ textAlign: 'left', paddingLeft: 32, fontWeight: 500, position: 'relative' }}>
                    {row.put.ltp}
                    {isHover && (
                      <div style={{ position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 4 }}>
                        <button style={{ background: k.surface, color: k.dim, border: `1px solid ${k.border}`, borderRadius: 2, width: 24, height: 20, fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={(e) => handleMenuClick(e, row.strike, 'put')}>
                          <Icons.More />
                        </button>
                      </div>
                    )}
                  </div>
                  <div style={{ textAlign: 'left', color: k.dim }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-start', gap: 8 }}>
                      {row.put.oi}
                      <div style={{ width: 40, height: 4, background: k.border, borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', background: k.red, width: `${Math.min(100, Number(row.put.oi) / 5)}%` }} />
                      </div>
                    </div>
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
                        <button style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
                        <button style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
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
                        <button style={{ background: k.blue, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>B</button>
                        <button style={{ background: k.orange, color: '#fff', border: 'none', borderRadius: 3, width: 24, height: 24, fontWeight: 600, fontSize: 12, cursor: 'pointer' }}>S</button>
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

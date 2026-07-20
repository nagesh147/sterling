import React, { useEffect, useRef } from 'react';
import { useKiteStatus, useKiteMargins, useKiteHoldings } from '../../hooks/useKite';
import { createChart, ColorType, AreaSeries } from 'lightweight-charts';
import { useCandles } from '../../hooks/useCandles';
import { InstrumentLabel } from './InstrumentLabel';
import { MacReveal, MacSkeleton } from './MacLoadingSurface';
import { k } from '../../styles/kiteUI';

function formatCurrency(val: number) {
  if (!val) return '0';
  return val.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function MarginCard({ title, available, used, opening, loading, delay }: {
  title: string;
  available: number;
  used: number;
  opening: number;
  loading: boolean;
  delay: number;
}) {
  const Icon = title === 'Equity'
    ? <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21.21 15.89A10 10 0 1 1 8 2.83" /><path d="M22 12A10 10 0 0 0 12 2v10z" /></svg>
    : <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9b9b9b" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" /></svg>;

  return (
    <MacReveal delay={delay} style={{ height: '100%' }}>
      <div style={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
          {Icon}
          <span style={{ fontSize: 14, color: k.text, fontWeight: 500 }}>{title}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, minHeight: 66 }}>
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 154 }}>
            {loading ? (
              <>
                <MacSkeleton width={142} height={42} radius={8} />
                <MacSkeleton width={86} height={9} radius={5} style={{ marginTop: 10 }} />
              </>
            ) : (
              <>
                <div style={{
                  fontSize: '2.625rem', fontWeight: 300, color: k.text, lineHeight: 1.3,
                  letterSpacing: 0, fontFamily: k.fontFamily, marginBottom: 4,
                  fontVariantNumeric: 'tabular-nums lining-nums',
                }}>
                  {formatCurrency(available)}
                </div>
                <div style={{ fontSize: 12, color: k.dim }}>Margin available</div>
              </>
            )}
          </div>

          <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', gap: 12, marginTop: 4, minWidth: 180 }}>
            {loading ? (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 34 }}>
                  <MacSkeleton width={76} height={9} radius={5} />
                  <MacSkeleton width={54} height={10} radius={5} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 34 }}>
                  <MacSkeleton width={92} height={9} radius={5} />
                  <MacSkeleton width={64} height={10} radius={5} />
                </div>
              </>
            ) : (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
                  <div style={{ fontSize: 12, color: k.dim }}>Margins used</div>
                  <div style={{ fontSize: 12, color: k.text, fontVariantNumeric: 'tabular-nums' }}>{formatCurrency(used)}</div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 40 }}>
                  <div style={{ fontSize: 12, color: k.dim }}>Opening balance</div>
                  <div style={{ fontSize: 12, color: k.text, fontVariantNumeric: 'tabular-nums' }}>{formatCurrency(opening)}</div>
                </div>
              </>
            )}
          </div>
        </div>

        <div style={{ marginTop: 'auto', paddingTop: 8 }}>
          {loading ? (
            <MacSkeleton width={96} height={10} radius={5} />
          ) : (
            <a href="#" style={{ color: '#387ed1', fontSize: 12, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" /></svg>
              View statement
            </a>
          )}
        </div>
      </div>
    </MacReveal>
  );
}

function DashboardChart({ symbol }: { symbol: string }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const { data: candles, isLoading } = useCandles(symbol, '1H', 500);

  useEffect(() => {
    if (!chartContainerRef.current || !candles || candles.length === 0) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: k.dim,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { visible: false },
      },
      width: chartContainerRef.current.clientWidth,
      height: 80,
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScroll: false,
      handleScale: false,
    });

    const lineSeries = chart.addSeries(AreaSeries, {
      lineColor: k.blue,
      topColor: 'rgba(65, 132, 243, 0.2)',
      bottomColor: 'rgba(65, 132, 243, 0)',
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    });

    const formattedData = candles.map((c) => ({ time: c.time as any, value: c.close }));
    formattedData.sort((a, b) => a.time - b.time);
    const uniqueData = formattedData.filter((v, i, a) => i === 0 || v.time !== a[i - 1].time);
    lineSeries.setData(uniqueData);

    const handleResize = () => chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [candles]);

  if (isLoading && !candles?.length) {
    return (
      <div style={{ width: '100%', height: 80, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 }} aria-label="Loading market overview">
        <MacSkeleton width="100%" height={48} radius={8} />
        <div style={{ display: 'flex', gap: 12 }}>
          <MacSkeleton width="25%" height={7} radius={4} />
          <MacSkeleton width="36%" height={7} radius={4} />
          <MacSkeleton width="20%" height={7} radius={4} />
        </div>
      </div>
    );
  }

  if (!candles?.length) {
    return (
      <div style={{ width: '100%', height: 80, display: 'flex', alignItems: 'center' }}>
        <div style={{ width: '100%', height: 1, background: 'linear-gradient(90deg, transparent, #dfe3e8 16%, #dfe3e8 84%, transparent)' }} />
      </div>
    );
  }

  return <MacReveal delay={40}><div ref={chartContainerRef} style={{ width: '100%', height: 80 }} /></MacReveal>;
}

function HoldingsSection({ holdings, loading }: { holdings: any[] | undefined; loading: boolean }) {
  if (loading) {
    return (
      <div style={{ width: 'min(460px, 76%)', display: 'flex', flexDirection: 'column', gap: 14 }} aria-label="Loading holdings">
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '34px minmax(100px, 1fr) 84px', alignItems: 'center', gap: 14 }}>
            <MacSkeleton width={34} height={34} radius={10} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <MacSkeleton width={i === 1 ? '68%' : '48%'} height={10} radius={5} />
              <MacSkeleton width={i === 2 ? '42%' : '31%'} height={7} radius={4} />
            </div>
            <MacSkeleton width={84} height={11} radius={5} />
          </div>
        ))}
      </div>
    );
  }

  if (holdings && holdings.length > 0) {
    return (
      <MacReveal delay={80}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: 54, height: 54, margin: '0 auto 18px', borderRadius: 17,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(145deg, #f8fbff, #edf3fb)',
            border: '1px solid #dce8f6', color: k.blue, fontSize: 22, fontWeight: 650,
            boxShadow: '0 8px 24px rgba(65,132,243,.10)',
          }}>
            {holdings.length}
          </div>
          <div style={{ fontSize: 13, color: k.text, fontWeight: 550 }}>{holdings.length} holding{holdings.length === 1 ? '' : 's'} synced</div>
          <div style={{ fontSize: 11.5, color: k.dim, marginTop: 6 }}>Your portfolio is ready in the Holdings tab.</div>
        </div>
      </MacReveal>
    );
  }

  return (
    <MacReveal delay={80}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'center' }}>
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.6 }}>
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
          </svg>
        </div>
        <div style={{ fontSize: 13, color: k.dim, marginBottom: 24, lineHeight: 1.5 }}>
          You don't have any stocks in your DEMAT yet. Get started<br />with absolutely free equity investments.
        </div>
        <button style={{
          background: '#387ed1', color: '#fff', border: 'none', borderRadius: 5,
          padding: '10px 24px', fontSize: 14, fontWeight: 500, cursor: 'pointer',
          boxShadow: '0 4px 12px rgba(56,126,209,.18)',
          transition: 'transform 120ms ease, box-shadow 120ms ease',
        }}>
          Start investing
        </button>
      </div>
    </MacReveal>
  );
}

export function KiteDashboard() {
  const statusQuery = useKiteStatus();
  const marginsQuery = useKiteMargins(!!statusQuery.data?.connected);
  const holdingsQuery = useKiteHoldings(!!statusQuery.data?.connected);

  const status = statusQuery.data;
  const margins = marginsQuery.data;
  const holdings = holdingsQuery.data;
  const name = status?.user_name ? status.user_name.split(' ')[0] : 'Madaram';

  const eq = margins?.equity?.net ?? 0;
  const eqUsed = margins?.equity?.utilised?.debits ?? 0;
  const eqOpening = margins?.equity?.available?.opening_balance ?? 0;
  const com = margins?.commodity?.net ?? 0;
  const comUsed = margins?.commodity?.utilised?.debits ?? 0;
  const comOpening = margins?.commodity?.available?.opening_balance ?? 0;

  const marginsLoading = marginsQuery.isLoading && !margins;
  const holdingsLoading = holdingsQuery.isLoading && !holdings;
  const dashboardBusy = statusQuery.isLoading || marginsLoading || holdingsLoading;

  return (
    <div
      aria-busy={dashboardBusy}
      style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', background: k.bg }}
    >
      <div style={{ padding: '32px 32px 0 32px' }}>
        <MacReveal delay={0}>
          <h1 style={{ fontSize: 20, fontWeight: 400, color: k.text, marginBottom: 24, marginTop: 0, minHeight: 26 }}>
            {statusQuery.isLoading && !status ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <span>Hi,</span><MacSkeleton width={82} height={18} radius={7} />
              </span>
            ) : `Hi, ${name}`}
          </h1>
        </MacReveal>

        <div style={{ display: 'flex', marginBottom: 48, minHeight: 154 }}>
          <div style={{ flex: 1, paddingRight: 40, borderRight: `1px solid ${k.border}` }}>
            <MarginCard title="Equity" available={eq} used={eqUsed} opening={eqOpening} loading={marginsLoading} delay={25} />
          </div>
          <div style={{ flex: 1, paddingLeft: 40 }}>
            <MarginCard title="Commodity" available={com} used={comUsed} opening={comOpening} loading={marginsLoading} delay={55} />
          </div>
        </div>
      </div>

      <div style={{
        borderTop: `1px solid ${k.border}`, borderBottom: `1px solid ${k.border}`,
        minHeight: 190, padding: '38px 0', display: 'flex', justifyContent: 'center', alignItems: 'center',
      }}>
        <HoldingsSection holdings={holdings} loading={holdingsLoading} />
      </div>

      <MacReveal delay={100} style={{ flex: 1 }}>
        <div style={{ display: 'flex', padding: '40px 32px 32px 32px' }}>
          <div style={{ flex: 1, paddingRight: 40 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></svg>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: k.text, margin: 0 }}>Market overview</h2>
            </div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 8px', border: `1px solid ${k.border}`, borderRadius: 4, cursor: 'pointer', marginBottom: 16 }}>
              <span style={{ fontSize: 10, color: k.dim }}>NIFTY 50</span>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
            </div>
            <div style={{ width: '100%' }}>
              <DashboardChart symbol="NSE:NIFTY 50" />
              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: `1px solid ${k.border}`, paddingTop: 8, fontSize: 10, color: k.dim }}>
                <span>Jul 25</span><span>Oct 25</span><span>Jan 26</span><span>Apr 26</span>
              </div>
            </div>
          </div>

          <div style={{ flex: 1, paddingLeft: 40 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 24 }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={k.dim} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
              <h2 style={{ fontSize: 14, fontWeight: 500, color: k.text, margin: 0 }}>Positions (1)</h2>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 40 }}>
              <span style={{ fontSize: 10, color: k.dim, whiteSpace: 'nowrap' }}>
                <InstrumentLabel symbol="SENSEX2461875500CE" fallback="SENSEX 18th w JUN 75500 PE" /> (NRML)
              </span>
              <div style={{ flex: 1, display: 'flex', alignItems: 'center', background: '#f1f1f1', height: 6 }}>
                <div style={{ width: '100%', height: 6, background: k.blue, borderRadius: 0 }} />
              </div>
            </div>
          </div>
        </div>
      </MacReveal>
    </div>
  );
}

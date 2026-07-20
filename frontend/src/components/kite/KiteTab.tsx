import React, { useState, useEffect } from 'react';
import { KiteLayout, NavItem, MoreTab } from './KiteLayout';
import { KiteDashboard } from './KiteDashboard';
import { SterlingWatchListWithHoldingsSync } from './SterlingWatchListWithHoldingsSync';
import { MarketDataPane } from './MarketDataPane';
import { ConnectPane } from './ConnectPane';
import { MutualFundsPane } from './MutualFundsPane';
import { PortfolioPane } from './PortfolioPane';
import { OrdersPane } from './OrdersPane';
import { FundsPane } from './FundsPane';
import { BidsPane } from './BidsPane';
import { AlertsPane } from './AlertsPane';
import { BacktestPane } from './BacktestPane';
import { InstrumentPane, InstrumentTab } from './InstrumentPane';
import { KiteNotifications } from './KiteNotifications';
import { PendingGttProtectionWatcher } from './PendingGttProtectionWatcher';
import { KiteSessionGuard } from './KiteSessionGuard';
import { KiteAuthOverlay } from './KiteLoader';
import { SterlingKiteEnginePane } from './SterlingKiteEnginePane';
import { SetupChart } from './SetupChart';
import { SignalDetailPane } from './SignalDetailPane';
import { EngineTerminal } from './EngineTerminal';
import { KiteTicker } from './KiteTicker';
import { useKiteAutoSession } from '../../hooks/useKite';
import { OrderWindow } from './OrderWindow';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { BasketPane } from './BasketPane';
import { useKiteBasketStore } from '../../store/useKiteBasketStore';
import { MacMotionProvider } from './mac/MacMotionProvider';
import { MacSectionFade } from './mac/MacSectionFade';
import { k } from '../../styles/kiteUI';

const MORE_TABS: { id: MoreTab; label: string }[] = [
  { id: 'bids', label: 'Bids' },
  { id: 'funds', label: 'Funds' },
  { id: 'mf', label: 'Mutual Funds' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'data', label: 'Data' },
];

function MorePane({ activeTab, onTabChange }: { activeTab: MoreTab; onTabChange: (t: MoreTab) => void }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', borderBottom: `1px solid ${k.border}`, background: k.bg, flexShrink: 0 }}>
        {MORE_TABS.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onTabChange(t.id)}
              style={{
                padding: '10px 16px', border: 'none', background: 'transparent', cursor: 'pointer',
                fontSize: 13, fontWeight: active ? 600 : 400,
                color: active ? '#f06428' : '#666',
                borderBottom: active ? '2px solid #f06428' : '2px solid transparent',
                marginBottom: -1, transition: 'color 0.15s',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        {activeTab === 'bids' && <BidsPane />}
        {activeTab === 'funds' && <FundsPane />}
        {activeTab === 'mf' && <MutualFundsPane />}
        {activeTab === 'alerts' && <AlertsPane />}
        {activeTab === 'backtest' && <BacktestPane />}
        {activeTab === 'data' && <MarketDataPane />}
      </div>
    </div>
  );
}

export function KiteTab() {
  const [nav, setNav] = useState<NavItem>('dashboard');
  const [moreTab, setMoreTab] = useState<MoreTab>('bids');
  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: { timestamp_ms: number; direction: string; regime: string } } | null>(null);
  const [setupView, setSetupView] = useState<{ token: number; underlying: string } | null>(null);
  const [detailView, setDetailView] = useState<{ token: number; underlying: string; timestamp_ms: number } | null>(null);
  const [savedTerminalMode, setSavedTerminalMode] = useState<'minimized' | 'normal' | 'partial' | 'full' | null>(null);
  const [basketOpen, setBasketOpen] = useState(false);
  const basketCount = useKiteBasketStore((s) => s.entries.length);
  useKiteAutoSession();

  // Listen for nav clicks dispatched from the Sterling top row.
  useEffect(() => {
    const cb = (e: Event) => handleNavClick((e as CustomEvent<NavItem>).detail);
    window.addEventListener('kite-nav-click', cb);
    return () => window.removeEventListener('kite-nav-click', cb);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { isOpen, options, closeOrderWindow } = useOrderWindowStore();

  const handleNavClick = (n: NavItem) => {
    closeChartView();
    setNav(n);
    setSetupView(null);
    setDetailView(null);
  };

  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: { timestamp_ms: number; direction: string; regime: string }) => {
    if (!instrumentView) {
      const cur = localStorage.getItem('kite_terminal_mode');
      setSavedTerminalMode(cur === 'minimized' || cur === 'partial' || cur === 'full' ? cur : 'normal');
      window.dispatchEvent(new CustomEvent('kite-terminal-mode', { detail: 'minimized' }));
    }
    setInstrumentView({ symbol, tab: defaultTab as InstrumentTab, trailTarget, signalData });
  };

  const closeChartView = () => {
    if (savedTerminalMode) {
      window.dispatchEvent(new CustomEvent('kite-terminal-mode', { detail: savedTerminalMode }));
      setSavedTerminalMode(null);
    }
    setInstrumentView(null);
  };

  let content = null;
  if (setupView) {
    content = <SetupChart token={setupView.token} underlying={setupView.underlying} onClose={() => { closeChartView(); setSetupView(null); }} />;
  } else if (detailView) {
    content = (
      <SignalDetailPane
        token={detailView.token}
        underlying={detailView.underlying}
        timestamp_ms={detailView.timestamp_ms}
        onClose={() => { closeChartView(); setDetailView(null); }}
        onShowSetup={() => setSetupView(detailView)}
        onShowOptionChain={(u) => { closeChartView(); setInstrumentView({ symbol: u, tab: 'option-chain' }); }}
      />
    );
  } else if (instrumentView) {
    content = (
      <InstrumentPane
        symbol={instrumentView.symbol}
        initialTab={instrumentView.tab}
        trailTarget={instrumentView.trailTarget}
        signalData={instrumentView.signalData}
        onSymbolChange={(newSymbol) => setInstrumentView({ symbol: newSymbol, tab: 'chart', trailTarget: instrumentView.trailTarget, signalData: instrumentView.signalData })}
      />
    );
  } else {
    if (nav === 'dashboard') content = <KiteDashboard />;
    else if (nav === 'orders') content = <OrdersPane onOpenBasket={() => setBasketOpen(true)} />;
    else if (nav === 'holdings') content = <PortfolioPane view="holdings" />;
    else if (nav === 'positions') content = <PortfolioPane view="positions" />;
    else if (nav === 'more') content = <MorePane activeTab={moreTab} onTabChange={setMoreTab} />;
    else if (nav === 'connect') content = <ConnectPane />;
  }

  const contentKey = setupView ? `setup:${setupView.token}`
    : detailView ? `detail:${detailView.token}`
    : instrumentView ? `inst:${instrumentView.symbol}`
    : nav === 'more' ? `more:${moreTab}`
    : `nav:${nav}`;

  return (
    <MacMotionProvider>
      <KiteLayout
        activeNav={nav}
        onNavClick={handleNavClick}
        sidebar={<SterlingWatchListWithHoldingsSync onOpenInstrument={handleOpenInstrument} />}
        rightSidebar={<SterlingKiteEnginePane onSelectSignal={(sel) => { setInstrumentView(null); setSetupView(null); setDetailView(sel); }} onOpenChart={handleOpenInstrument} />}
        bottomBar={<EngineTerminal />}
        centerTopBar={<KiteTicker onOpenChart={(symbol) => handleOpenInstrument(symbol, 'chart')} />}
        content={<MacSectionFade sectionKey={contentKey}>{content}</MacSectionFade>}
        onBasketClick={() => setBasketOpen(true)}
        basketCount={basketCount}
      />
      <KiteNotifications />
      <PendingGttProtectionWatcher />
      <KiteSessionGuard />
      <KiteAuthOverlay />
      {isOpen && options && (
        <OrderWindow options={options} onClose={closeOrderWindow} />
      )}
      {basketOpen && <BasketPane onClose={() => setBasketOpen(false)} />}
    </MacMotionProvider>
  );
}

export default KiteTab;

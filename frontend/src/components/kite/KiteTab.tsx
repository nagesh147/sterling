import React, { useState } from 'react';
import { KiteLayout, NavItem } from './KiteLayout';
import { KiteDashboard } from './KiteDashboard';
import { MarketWatchPane } from './MarketWatchPane';
import { MarketDataPane } from './MarketDataPane';
import { ConnectPane } from './ConnectPane';
import { MutualFundsPane } from './MutualFundsPane';
import { PortfolioPane } from './PortfolioPane';
import { OrdersPane } from './OrdersPane';
import { GttPane } from './GttPane';
import { FundsPane } from './FundsPane';
import { BidsPane } from './BidsPane';
import { AlertsPane } from './AlertsPane';
import { BacktestPane } from './BacktestPane';
import { InstrumentPane, InstrumentTab } from './InstrumentPane';
import { KiteNotifications } from './KiteNotifications';
import { TripleSupertrendPane } from './TripleSupertrendPane';
import { SetupChart } from './SetupChart';
import { SignalDetailPane } from './SignalDetailPane';
import { EngineTerminal } from './EngineTerminal';
import { useKiteAutoSession } from '../../hooks/useKite';
import { OrderWindow } from './OrderWindow';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import { MacMotionProvider } from './mac/MacMotionProvider';
import { MacSectionFade } from './mac/MacSectionFade';

export function KiteTab() {
  const [nav, setNav] = useState<NavItem>('dashboard');
  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab } | null>(null);
  const [setupView, setSetupView] = useState<{ token: number; underlying: string } | null>(null);
  const [detailView, setDetailView] = useState<{ token: number; underlying: string; timestamp_ms: number } | null>(null);
  const [savedTerminalMode, setSavedTerminalMode] = useState<'minimized' | 'normal' | 'partial' | 'full' | null>(null);
  useKiteAutoSession();   // silently auto-recover a lapsed session via the stored refresh token

  const { isOpen, options, closeOrderWindow } = useOrderWindowStore();

  const handleNavClick = (n: NavItem) => {
    closeChartView();
    setNav(n);
    setSetupView(null);
    setDetailView(null);
  };

  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain') => {
    // When opening chart/instrument view, minimize the kite terminal.
    // On close, restore previous if it was not minimized.
    if (!instrumentView) {
      // Save current assumed state (default to 'normal' if we were showing terminal)
      setSavedTerminalMode('normal');
      window.dispatchEvent(new CustomEvent('kite-terminal-mode', { detail: 'minimized' }));
    }
    setInstrumentView({ symbol, tab: defaultTab as InstrumentTab });
  };
  
  // Restore terminal when leaving chart view
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
        onSymbolChange={(newSymbol) => setInstrumentView({ symbol: newSymbol, tab: 'chart' })} 
      />
    );
  } else {
    if (nav === 'dashboard') content = <KiteDashboard />;
    else if (nav === 'orders') content = <OrdersPane />;
    else if (nav === 'holdings') content = <PortfolioPane view="holdings" />;
    else if (nav === 'positions') content = <PortfolioPane view="positions" />;
    else if (nav === 'bids') content = <BidsPane />;
    else if (nav === 'funds') content = <FundsPane />;
    else if (nav === 'mf') content = <MutualFundsPane />;
    else if (nav === 'alerts') content = <AlertsPane />;
    else if (nav === 'backtest') content = <BacktestPane />;
    else if (nav === 'data') content = <MarketDataPane />;
    else if (nav === 'connect') content = <ConnectPane />;
  }

  // Key that identifies the current center view — drives the Mac nav-section
  // crossfade (no-op when Mac Kite is off).
  const contentKey = setupView ? `setup:${setupView.token}`
    : detailView ? `detail:${detailView.token}`
    : instrumentView ? `inst:${instrumentView.symbol}`
    : `nav:${nav}`;

  return (
    <MacMotionProvider>
      <KiteLayout
        activeNav={nav}
        onNavClick={handleNavClick}
        sidebar={<MarketWatchPane onOpenInstrument={handleOpenInstrument} />}
        rightSidebar={<TripleSupertrendPane onSelectSignal={(sel) => { setInstrumentView(null); setSetupView(null); setDetailView(sel); }} />}
        bottomBar={<EngineTerminal />}
        content={<MacSectionFade sectionKey={contentKey}>{content}</MacSectionFade>}
      />
      <KiteNotifications />
      {isOpen && options && (
        <OrderWindow options={options} onClose={closeOrderWindow} />
      )}
    </MacMotionProvider>
  );
}

export default KiteTab;

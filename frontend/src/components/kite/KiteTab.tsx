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
import { InstrumentPane, InstrumentTab } from './InstrumentPane';
import { KiteNotifications } from './KiteNotifications';
import { TripleSupertrendPane } from './TripleSupertrendPane';
import { SetupChart } from './SetupChart';
import { SignalDetailPane } from './SignalDetailPane';
import { EngineTerminal } from './EngineTerminal';
import { useKiteAutoSession } from '../../hooks/useKite';
import { OrderWindow } from './OrderWindow';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';

export function KiteTab() {
  const [nav, setNav] = useState<NavItem>('dashboard');
  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab } | null>(null);
  const [setupView, setSetupView] = useState<{ token: number; underlying: string } | null>(null);
  const [detailView, setDetailView] = useState<{ token: number; underlying: string; timestamp_ms: number } | null>(null);
  useKiteAutoSession();   // silently auto-recover a lapsed session via the stored refresh token

  const { isOpen, options, closeOrderWindow } = useOrderWindowStore();

  const handleNavClick = (n: NavItem) => {
    setNav(n);
    setInstrumentView(null);
    setSetupView(null);
    setDetailView(null);
  };

  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain') => {
    setInstrumentView({ symbol, tab: defaultTab as InstrumentTab });
  };
  
  let content = null;
  if (setupView) {
    content = <SetupChart token={setupView.token} underlying={setupView.underlying} onClose={() => setSetupView(null)} />;
  } else if (detailView) {
    content = (
      <SignalDetailPane
        token={detailView.token}
        underlying={detailView.underlying}
        timestamp_ms={detailView.timestamp_ms}
        onClose={() => setDetailView(null)}
        onShowSetup={() => setSetupView(detailView)}
        onShowOptionChain={(u) => { setDetailView(null); setInstrumentView({ symbol: u, tab: 'option-chain' }); }}
      />
    );
  } else if (instrumentView) {
    content = <InstrumentPane symbol={instrumentView.symbol} initialTab={instrumentView.tab} />;
  } else {
    if (nav === 'dashboard') content = <KiteDashboard />;
    else if (nav === 'orders') content = <OrdersPane />;
    else if (nav === 'holdings') content = <PortfolioPane view="holdings" />;
    else if (nav === 'positions') content = <PortfolioPane view="positions" />;
    else if (nav === 'bids') content = <BidsPane />;
    else if (nav === 'funds') content = <FundsPane />;
    else if (nav === 'mf') content = <MutualFundsPane />;
    else if (nav === 'alerts') content = <AlertsPane />;
    else if (nav === 'data') content = <MarketDataPane />;
    else if (nav === 'connect') content = <ConnectPane />;
  }

  return (
    <>
      <KiteLayout
        activeNav={nav}
        onNavClick={handleNavClick}
        sidebar={<MarketWatchPane onOpenInstrument={handleOpenInstrument} />}
        rightSidebar={<TripleSupertrendPane onSelectSignal={(sel) => { setInstrumentView(null); setSetupView(null); setDetailView(sel); }} />}
        bottomBar={<EngineTerminal />}
        content={content}
      />
      <KiteNotifications />
      {isOpen && options && (
        <OrderWindow options={options} onClose={closeOrderWindow} />
      )}
    </>
  );
}

export default KiteTab;

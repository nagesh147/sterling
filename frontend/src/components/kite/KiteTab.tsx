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
import { AlertsPane } from './AlertsPane';
import { InstrumentPane, InstrumentTab } from './InstrumentPane';
import { OrderUpdateToast } from './OrderUpdateToast';

export function KiteTab() {
  const [nav, setNav] = useState<NavItem>('dashboard');
  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab } | null>(null);
  
  const handleNavClick = (n: NavItem) => {
    setNav(n);
    setInstrumentView(null);
  };

  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain') => {
    setInstrumentView({ symbol, tab: defaultTab as InstrumentTab });
  };
  
  let content = null;
  if (instrumentView) {
    content = <InstrumentPane symbol={instrumentView.symbol} initialTab={instrumentView.tab} />;
  } else {
    if (nav === 'dashboard') content = <KiteDashboard />;
    else if (nav === 'orders') content = <OrdersPane />;
    else if (nav === 'holdings') content = <PortfolioPane view="holdings" />;
    else if (nav === 'positions') content = <PortfolioPane view="positions" />;
    else if (nav === 'bids') content = <GttPane />;
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
        content={content}
      />
      <OrderUpdateToast />
    </>
  );
}

export default KiteTab;

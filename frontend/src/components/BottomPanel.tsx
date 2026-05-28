import React, { useState } from 'react';
import { WatchlistPanel } from './WatchlistPanel';
import { OptionChainViewer } from './OptionChainViewer';
import { WalkForwardPanel } from './WalkForwardPanel';
import { WFOImpactPanel } from './WFOImpactPanel';
import { SensitivityPanel } from './SensitivityPanel';
import { RiskConfigPanel } from './RiskConfigPanel';
import { CalibrationPanel } from './CalibrationPanel';
import LiveControlPanel from './LiveControlPanel';
import { useSelectedUnderlying } from '../store/useStore';
import { gridStyle } from '../styles/terminalUI';

type BottomTab = 'live' | 'scanner' | 'chain' | 'watchlist' | 'analytics' | 'config';

const TABS: [BottomTab, string][] = [
  ['live',      'LIVE'],
  ['scanner',   'SCANNER'],
  ['chain',     'CHAIN'],
  ['watchlist', 'WATCHLIST'],
  ['analytics', 'ANALYTICS'],
  ['config',    'CONFIG'],
];

export function BottomPanel() {
  const [tab, setTab] = useState<BottomTab>('live');
  const underlying = useSelectedUnderlying();

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tab pills */}
      <div style={{
        display: 'flex', gap: 4, padding: '4px 10px',
        borderBottom: '1px solid var(--t-border)', flexShrink: 0,
        background: 'var(--t-bg2)',
      }}>
        {TABS.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              background: tab === id ? 'var(--t-bg3)' : 'none',
              color: tab === id ? 'var(--t-bright)' : 'var(--t-dim)',
              border: `1px solid ${tab === id ? 'var(--t-br2)' : 'transparent'}`,
              borderRadius: 3, padding: '2px 10px', cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 10, letterSpacing: 1,
              transition: 'color 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Panel content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 10px' }}>
        {tab === 'live' && (
          <div style={{ maxWidth: 520 }}>
            <LiveControlPanel />
          </div>
        )}
        {tab === 'scanner' && (
          <WatchlistPanel />
        )}
        {tab === 'chain' && (
          <OptionChainViewer underlying={underlying} />
        )}
        {tab === 'watchlist' && (
          <div style={{ fontSize: 11, color: 'var(--t-text)' }}>
            <WatchlistPanel />
          </div>
        )}
        {tab === 'analytics' && (
          <div style={gridStyle(320, 16)}>
            <WFOImpactPanel />
            <WalkForwardPanel />
            <SensitivityPanel />
          </div>
        )}
        {tab === 'config' && (
          <div style={gridStyle(320, 16)}>
            <RiskConfigPanel />
            <CalibrationPanel />
          </div>
        )}
      </div>
    </div>
  );
}

import React, { useMemo, useState } from 'react';
import { SterlingKiteEngineWithExpiry } from './SterlingKiteEngineWithExpiry';
import { AdaptiveEdgePanel, type AdaptiveEdgeRow } from './AdaptiveEdgePanel';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { k } from '../../styles/kiteUI';

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number; source?: string }) => void;
  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: any) => void;
}

export function AdaptiveEdgeRightSidebar({ onSelectSignal, onOpenChart }: Props) {
  const [engine, setEngine] = useState<'signals' | 'adaptive_edge'>('signals');
  const snapshot = useAdaptiveEdgeSnapshot();
  const rows: AdaptiveEdgeRow[] = useMemo(() => {
    const data = snapshot.data;
    if (!data) return [];
    return [{
      id: 'research-last',
      instrument: data.settings.symbol,
      observationTime: Date.now(),
      featureQuality: data.software_complete ? 'BOARD READY' : 'INCOMPLETE',
      mode: data.session.last_mode,
      quantity: data.session.last_position_quantity,
      currentPnl: data.session.current_pnl,
      peakPnl: data.session.peak_pnl,
      profitGiveback: data.session.profit_giveback,
      protectionState: data.session.last_protection_stage,
      decision: (data.session.last_position_quantity ?? 0) > 0 ? 'HOLD' : data.session.exits ? 'EXIT' : 'REJECT',
      reason: 'Display only',
      formulaIds: ['F-101', 'F-007', 'F-008'],
    }];
  }, [snapshot.data]);

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', background: k.bg }}>
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: `1px solid ${k.border}`, background: k.bg }}>
        <button
          onClick={() => setEngine('signals')}
          style={{ flex: 1, padding: '7px 8px', border: 0, borderBottom: engine === 'signals' ? `2px solid ${k.blue}` : '2px solid transparent', background: 'transparent', color: engine === 'signals' ? k.text : k.dim, fontSize: 9, fontWeight: engine === 'signals' ? 700 : 500, letterSpacing: '.06em', cursor: 'pointer' }}
        >
          SIGNALS
        </button>
        <button
          onClick={() => setEngine('adaptive_edge')}
          style={{ flex: 1, padding: '7px 8px', border: 0, borderBottom: engine === 'adaptive_edge' ? `2px solid ${k.blue}` : '2px solid transparent', background: 'transparent', color: engine === 'adaptive_edge' ? k.text : k.dim, fontSize: 9, fontWeight: engine === 'adaptive_edge' ? 700 : 500, letterSpacing: '.06em', cursor: 'pointer' }}
        >
          ADAPTIVE EDGE
        </button>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        {engine === 'signals' ? (
          <SterlingKiteEngineWithExpiry onSelectSignal={onSelectSignal} onOpenChart={onOpenChart} />
        ) : (
          <AdaptiveEdgePanel rows={rows} />
        )}
      </div>
    </div>
  );
}

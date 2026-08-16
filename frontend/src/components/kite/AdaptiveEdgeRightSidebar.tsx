import React, { useEffect, useMemo, useState } from 'react';
import { SterlingKiteEngineWithExpiry } from './SterlingKiteEngineWithExpiry';
import { AdaptiveEdgePanel, rowsFromSnapshot } from './AdaptiveEdgePanel';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { k } from '../../styles/kiteUI';

interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number; source?: string }) => void;
  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: any) => void;
}

export function AdaptiveEdgeRightSidebar({ onSelectSignal, onOpenChart }: Props) {
  const [engine, setEngine] = useState<'signals' | 'adaptive_edge'>('signals');
  const snapshot = useAdaptiveEdgeSnapshot();
  const rows = useMemo(() => (snapshot.data ? rowsFromSnapshot(snapshot.data) : []), [snapshot.data]);

  useEffect(() => {
    const onNav = (event: Event) => {
      if ((event as CustomEvent<string>).detail === 'adaptiveEdge') setEngine('adaptive_edge');
    };
    window.addEventListener('kite-nav-click', onNav);
    return () => window.removeEventListener('kite-nav-click', onNav);
  }, []);

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

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: engine === 'adaptive_edge' ? '0 10px 12px' : 0 }}>
        {engine === 'signals' ? (
          <SterlingKiteEngineWithExpiry onSelectSignal={onSelectSignal} onOpenChart={onOpenChart} />
        ) : (
          <AdaptiveEdgePanel
            rows={rows}
            inlineExpand={true}
            onInspectSymbol={onOpenChart ? (sym) => onOpenChart(sym, 'chart') : undefined}
          />
        )}
      </div>
    </div>
  );
}


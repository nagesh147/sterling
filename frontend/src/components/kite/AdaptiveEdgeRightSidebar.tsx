import React, { useEffect, useMemo, useState } from 'react';
import { SterlingKiteEngineWithExpiry } from './SterlingKiteEngineWithExpiry';
import { rowsFromSnapshot } from './AdaptiveEdgePanel';
import { NiftyOrbSignalsFeed } from './NiftyOrbSignalsFeed';
import { AdaptiveEdgeBoard } from './board/AdaptiveEdgeBoard';
import { EngineTabs, type EngineTabState } from './board/EngineToolbar';
import { adaptiveEdgeToBoard } from './board/adaptiveEdgeAdapter';
import { orbToBoard } from './board/orbAdapter';
import { supertrendToBoard } from './board/supertrendAdapter';
import { ACTIONABLE, type BoardSignal, type EngineId } from './board/boardTypes';
import { useAdaptiveEdgeSnapshot } from '../../hooks/useAdaptiveEdge';
import { useEngineSignals, useEngineConfig } from '../../hooks/useSterlingKiteEngine';
import { useOrbSignals } from '../../hooks/useOrbSignals';
import { useOrbConfig } from '../../hooks/useOrbConfig';
import { k } from '../../styles/kiteUI';

/**
 * The engine workspace: pick an engine, see its board.
 *
 * The picker used to be three flat words. Choosing between them meant opening
 * each one to find out whether it was running and whether it had anything —
 * which is backwards, because the point of a picker is to make that choice
 * without paying for it.
 *
 * Each tab now carries live state: a dot for running / running-but-quiet / off,
 * and a count of what is live. Every tab therefore has to know its engine's
 * state whether or not it is the visible one, which is why the counts are read
 * here rather than inside each board. All three already poll on their own
 * schedule, so this shares their cached data rather than adding requests.
 */
interface Props {
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number; source?: string }) => void;
  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: any) => void;
  /** Opens a board signal as a full detail page in the centre column. */
  onOpenBoardDetail?: (signal: BoardSignal) => void;
}

/** Which engine each nav destination should land on. */
const NAV_TARGET: Record<string, EngineId> = {
  adaptiveEdge: 'adaptive_edge',
  orbOptions: 'orb',
};

export function AdaptiveEdgeRightSidebar({ onSelectSignal, onOpenChart, onOpenBoardDetail }: Props) {
  const [engine, setEngine] = useState<EngineId>('supertrend');
  // One clock per render, so every day heading in a paint agrees on "today".
  const nowMs = Date.now();

  const snapshot = useAdaptiveEdgeSnapshot();
  const engineSignals = useEngineSignals();
  const engineConfig = useEngineConfig();
  const orbConfig = useOrbConfig();
  const orbEnabled = orbConfig.data?.config?.enabled;
  const orb = useOrbSignals(orbEnabled !== false);

  const tabs: EngineTabState[] = useMemo(() => {
    const st = supertrendToBoard(engineSignals.data?.rows ?? []);
    const ae = snapshot.data ? rowsFromSnapshot(snapshot.data).map(adaptiveEdgeToBoard) : [];
    const ob = orb.signals.map(orbToBoard);
    const live = (list: typeof st) => list.filter((s) => ACTIONABLE.includes(s.status)).length;
    return [
      { id: 'supertrend', running: engineConfig.data?.engine_enabled !== false, live: live(st), scanned: st.length },
      { id: 'adaptive_edge', running: !!snapshot.data, live: live(ae), scanned: ae.length },
      { id: 'orb', running: orbEnabled !== false, live: live(ob), scanned: ob.length },
    ];
  }, [engineSignals.data, engineConfig.data, snapshot.data, orb.signals, orbEnabled]);

  useEffect(() => {
    const onNav = (event: Event) => {
      const target = NAV_TARGET[(event as CustomEvent<string>).detail];
      if (target) setEngine(target);
    };
    window.addEventListener('kite-nav-click', onNav);
    return () => window.removeEventListener('kite-nav-click', onNav);
  }, []);

  return (
    <div style={{ height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', background: k.bg }}>
      <div style={{ display: 'flex', flexShrink: 0, borderBottom: `1px solid ${k.border}`, background: k.bg }}>
        <EngineTabs tabs={tabs} active={engine} onSelect={setEngine} />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {engine === 'supertrend' && (
          <SterlingKiteEngineWithExpiry onSelectSignal={onSelectSignal} onOpenChart={onOpenChart} />
        )}
        {engine === 'adaptive_edge' && <AdaptiveEdgeBoard nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />}
        {engine === 'orb' && <NiftyOrbSignalsFeed onOpenDetail={onOpenBoardDetail} />}
      </div>
    </div>
  );
}

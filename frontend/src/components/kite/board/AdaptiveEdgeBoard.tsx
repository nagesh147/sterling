/**
 * Adaptive Edge, on the shared board.
 *
 * The standalone Adaptive Edge page keeps its own richer panel — it has the
 * width for per-underlying grouping and the mode-history detail. This is the
 * sidebar view, where the point is that all three engines read the same way.
 */
import React from 'react';
import { useAdaptiveEdgeSnapshot } from '../../../hooks/useAdaptiveEdge';
import { rowsFromSnapshot } from '../AdaptiveEdgePanel';
import { adaptiveEdgeToBoard } from './adaptiveEdgeAdapter';
import { SignalBoard } from './SignalBoard';
import { BoardFilters } from './BoardFilters';
import { useBoardView } from './useBoardView';
import { k } from '../../../styles/kiteUI';

export function AdaptiveEdgeBoard({ nowMs }: { nowMs: number }) {
  const snapshot = useAdaptiveEdgeSnapshot();
  const signals = React.useMemo(
    () => (snapshot.data ? rowsFromSnapshot(snapshot.data).map(adaptiveEdgeToBoard) : []),
    [snapshot.data],
  );
  const view = useBoardView(signals);
  const [openId, setOpenId] = React.useState<string | null>(null);

  if (snapshot.isLoading && !snapshot.data) {
    return <p style={{ padding: 12, margin: 0, fontSize: 11, color: k.dim }}>Loading Adaptive Edge…</p>;
  }
  if (snapshot.error) {
    return <p style={{ padding: 12, margin: 0, fontSize: 11, color: k.red }}>Adaptive Edge unavailable: {(snapshot.error as Error).message}</p>;
  }

  return (
    <div>
      <BoardFilters view={view} />
      <SignalBoard
        signals={view.visible}
        requested={['instrument', 'status', 'exchange', 'leg', 'entry', 'stop', 'trail', 'target', 'exit', 'ltp', 'score', 'time']}
        openId={openId}
        onToggle={(id) => setOpenId((p) => (p === id ? null : id))}
        nowMs={nowMs}
        emptyLabel={
          view.counts.total
            ? 'Every row is filtered out. Clear the search or include ended positions.'
            : 'Adaptive Edge has not surfaced a signal yet.'
        }
      />
    </div>
  );
}

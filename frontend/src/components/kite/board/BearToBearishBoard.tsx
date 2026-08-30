import React from 'react';
import {
  useBearToBearishScan,
  useBearToBearishSnapshot,
  useExecuteBearToBearishOrder,
  useUpdateBearToBearishConfig,
} from '../../../hooks/useBearToBearish';
import { bearToBearishToBoard } from './bearToBearishAdapter';
import { DEFAULT_SORT, SignalBoard, type ColumnId, type SortState } from './SignalBoard';
import { SIGNAL_COL_TO_BOARD, type SignalColKey } from './signalRowSpec';
import { useBoardRowActions } from './useBoardRowActions';
import { BoardFilters } from './BoardFilters';
import { BoardTicket } from './BoardTicket';
import { useBoardView } from './useBoardView';
import type { BoardSignal } from './boardTypes';
import { useKiteSettings } from '../../../store/useKiteSettings';
import { KiteActionButtons } from '../KiteActionButtons';
import { k } from '../../../styles/kiteUI';

const note: React.CSSProperties = {
  padding: '12px 14px',
  margin: 0,
  fontSize: 11,
  color: k.dim,
  lineHeight: 1.6,
};

export function BearToBearishBoard({
  nowMs,
  onOpenDetail,
  onOpenChart,
}: {
  onOpenChart?: (quoteKey: string) => void;
  nowMs: number;
  onOpenDetail?: (signal: BoardSignal) => void;
}) {
  const s = useKiteSettings();
  const rowActions = useBoardRowActions({ onOpenChart });
  const [pollMs, setPollMs] = React.useState(3000);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [sort, setSort] = React.useState<SortState>(DEFAULT_SORT);
  const [collapsedGroups, setCollapsedGroups] = React.useState<ReadonlySet<string>>(new Set());

  const snapshot = useBearToBearishSnapshot(true, pollMs);
  const scan = useBearToBearishScan();
  const updateConfig = useUpdateBearToBearishConfig();
  const executeOrder = useExecuteBearToBearishOrder();

  const data = snapshot.data;
  const signals = React.useMemo(() => bearToBearishToBoard(data), [data]);
  const view = useBoardView(signals, { endedByDefault: true, storageKey: 'bear_to_bearish' });

  const columns = React.useMemo<readonly ColumnId[]>(() => {
    const ordered = [...s.signalLeftColumnOrder, ...s.signalRightColumnOrder]
      .map((key) => SIGNAL_COL_TO_BOARD[key as SignalColKey])
      .filter(Boolean) as ColumnId[];
    return ['instrument', ...ordered];
  }, [s.signalLeftColumnOrder, s.signalRightColumnOrder]);

  const hidden = React.useMemo(
    () => new Set(
      s.hiddenSignalCols
        .map((key) => SIGNAL_COL_TO_BOARD[key as SignalColKey])
        .filter(Boolean) as ColumnId[],
    ),
    [s.hiddenSignalCols],
  );

  const toggleGroup = React.useCallback((id: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  if (snapshot.isLoading && !data) return <p style={note}>Loading Bear to Bearish Strategy...</p>;
  if (snapshot.error) {
    return (
      <p style={{ ...note, color: k.red }}>
        Unavailable: {(snapshot.error as Error).message}
      </p>
    );
  }

  const armedRows = signals.filter((sig) => sig.status === 'armed');
  const autoExecute = data?.auto_execute ?? false;

  return (
    <div>
      {/* Strategy Toolbar Header matching Adaptive Edge & SuperTrend */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          padding: '8px 12px',
          borderBottom: `1px solid ${k.border}`,
          background: 'var(--k-bg2, #07090d)',
        }}
      >
        <button
          type="button"
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          title="Run intraday PCR + Lower High momentum short scan"
          style={{
            background: 'transparent',
            border: `1px solid ${k.border}`,
            color: k.text,
            borderRadius: 6,
            padding: '4px 10px',
            fontSize: 11,
            fontWeight: 600,
            cursor: scan.isPending ? 'progress' : 'pointer',
          }}
        >
          {scan.isPending ? 'Scanning...' : 'Scan now'}
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: k.dim }}>
          <span>PCR &lt; 0.60 Short Momentum</span>
          <span>·</span>
          <strong style={{ color: data?.is_paper === false ? k.green : k.amber }}>
            {data?.is_paper === false ? 'LIVE' : 'PAPER'}
          </strong>
          <span>·</span>
          <button
            type="button"
            onClick={() => updateConfig.mutate({ auto_execute: !autoExecute })}
            style={{
              background: autoExecute ? 'rgba(46,160,67,0.18)' : 'transparent',
              border: `1px solid ${autoExecute ? k.green : k.border}`,
              color: autoExecute ? k.green : k.dim,
              borderRadius: 4,
              padding: '2px 8px',
              fontSize: 10,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            AUTO EXECUTE: {autoExecute ? 'ON' : 'OFF'}
          </button>
        </div>

        {armedRows.length > 0 && (
          <span style={{ fontSize: 11, color: k.green, marginLeft: 'auto', fontWeight: 600 }}>
            ⚡ {armedRows.length} Armed Short Setup{armedRows.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* PCR Live trajectory summary */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          padding: '6px 12px',
          fontSize: 10.5,
          color: k.dim,
          borderBottom: `1px solid ${k.border}`,
          background: 'var(--k-bg, #07090d)',
        }}
      >
        <span>
          PCR Trend: <b style={{ color: k.purple }}>0.80 → 0.58</b> (Sellers Active at Resistance)
        </span>
        <span>·</span>
        <span>Invalidation: PCR Jump &ge; +0.20 in 5-10m</span>
        <span>·</span>
        <span>Chart Structure: 1m / 3m / 5m Lower Highs</span>
      </div>

      {signals.length > 0 && <BoardFilters view={view} columns={columns} />}

      {/* Main Signal Board */}
      <SignalBoard
        renderTrade={rowActions.renderTrade}
        renderChart={rowActions.renderChart}
        signals={view.visible}
        columns={columns}
        hidden={hidden}
        openId={openId}
        onToggle={(id) => setOpenId((p) => (p === id ? null : id))}
        sort={sort}
        onSortChange={setSort}
        collapsedGroups={collapsedGroups}
        onToggleGroup={toggleGroup}
        renderDetail={(sig) => (
          <div style={{ padding: '8px 0' }}>
            <BoardTicket signal={sig} tag="BEAR_TO_BEARISH" />
            {sig.status === 'armed' && (
              <div style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => executeOrder.mutate(sig.id)}
                  disabled={executeOrder.isPending}
                  style={{
                    background: 'rgba(46,160,67,0.18)',
                    border: `1px solid ${k.green}`,
                    color: k.green,
                    borderRadius: 6,
                    padding: '5px 14px',
                    fontSize: 11,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {executeOrder.isPending ? 'Executing...' : `⚡ Execute Order: ${sig.direction.toUpperCase()} 1 Lot ${sig.instrument.symbol}`}
                </button>
              </div>
            )}
          </div>
        )}
        onOpenDetail={onOpenDetail}
        nowMs={nowMs}
        emptyLabel={
          view.counts.total
            ? 'Every row is filtered out. Clear the search or include ended positions.'
            : 'No active Bear to Bearish setup found. Press Scan now to scan intraday PCR dynamics.'
        }
      />
    </div>
  );
}

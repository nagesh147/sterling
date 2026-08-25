import React from 'react';
import {
  useSmartMoneyOptionsConfig,
  useSmartMoneyOptionsSnapshot,
  useTriggerSmartMoneyScan,
} from '../../../hooks/useSmartMoneyOptions';
import { smartMoneyOptionsToBoard } from './smartMoneyOptionsAdapter';
import { BOARD_COLUMNS, DEFAULT_SORT, SignalBoard } from './SignalBoard';
import { BoardFilters } from './BoardFilters';
import { BoardTicket } from './BoardTicket';
import { StatCard, type Stat } from './StatCard';
import { useBoardView } from './useBoardView';
import type { BoardSignal } from './boardTypes';
import { k } from '../../../styles/kiteUI';

const note: React.CSSProperties = {
  fontSize: 12,
  color: k.dim,
  padding: '12px 14px',
  fontFamily: k.fontFamily,
};

export function SmartMoneyOptionsBoard({
  nowMs,
  onOpenDetail,
}: {
  nowMs: number;
  onOpenDetail?: (signal: BoardSignal) => void;
}) {
  const configQuery = useSmartMoneyOptionsConfig();
  const snapshotQuery = useSmartMoneyOptionsSnapshot(true);
  const triggerScan = useTriggerSmartMoneyScan();

  const signals = React.useMemo(
    () => smartMoneyOptionsToBoard(snapshotQuery.data),
    [snapshotQuery.data]
  );

  const view = useBoardView(signals, { endedByDefault: true, storageKey: 'smart_money_options' });
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [sort, setSort] = React.useState(DEFAULT_SORT);
  const [collapsedGroups, setCollapsedGroups] = React.useState<ReadonlySet<string>>(new Set());
  const toggleGroup = React.useCallback((id: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const armedCount = signals.filter((s) => s.status === 'armed').length;
  const runningCount = signals.filter((s) => s.status === 'running').length;
  const totalScanned = signals.length;

  const stats: Stat[] = [
    {
      label: 'Armed Setups',
      value: armedCount,
      color: armedCount > 0 ? k.green : k.dim,
      hint: 'Breakouts confirmed with Smart Money volume surge (2X/3X/5X targets ready)',
    },
    {
      label: 'Active Trades',
      value: runningCount,
      color: runningCount > 0 ? k.blue : k.dim,
      hint: 'Positions currently held in the 5-day swing horizon',
    },
    {
      label: 'Scanned Universe',
      value: totalScanned,
      hint: 'F&O stocks & indices evaluated for base consolidation',
    },
  ];

  if (snapshotQuery.isLoading && !snapshotQuery.data) {
    return <p style={note}>Scanning Smart Money Multi-X Setups…</p>;
  }

  if (snapshotQuery.error) {
    return (
      <p style={{ ...note, color: k.red }}>
        Unavailable: {(snapshotQuery.error as Error).message}
      </p>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: k.bg }}>
      {/* Top Banner with Stats & Scan Button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: `1px solid ${k.border}`,
          background: k.surface,
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', flex: 1 }}>
          <StatCard
            title="Smart Money Multi-X"
            layout="tiles"
            stats={stats}
          />
        </div>

        <button
          type="button"
          disabled={triggerScan.isPending}
          onClick={() => triggerScan.mutate()}
          style={{
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 500,
            color: '#fff',
            background: k.blue,
            border: 'none',
            borderRadius: 4,
            cursor: triggerScan.isPending ? 'not-allowed' : 'pointer',
            opacity: triggerScan.isPending ? 0.6 : 1,
            whiteSpace: 'nowrap',
          }}
        >
          ⚡ Scan Universe
        </button>
      </div>

      {/* Filter and Search Bar */}
      <BoardFilters view={view} columns={BOARD_COLUMNS} />

      {/* Signal Board */}
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <SignalBoard
          signals={view.visible}
          requested={BOARD_COLUMNS}
          hidden={view.hidden}
          openId={openId}
          onToggle={(id) => setOpenId((p) => (p === id ? null : id))}
          renderDetail={(sig) => <BoardTicket signal={sig} tag="SMART_MONEY_OPTIONS" />}
          onOpenDetail={onOpenDetail}
          sort={sort}
          onSortChange={setSort}
          collapsedGroups={collapsedGroups}
          onToggleGroup={toggleGroup}
          nowMs={nowMs}
          emptyLabel={
            view.counts.total
              ? 'Every row is filtered out. Clear the search or include ended positions.'
              : 'Smart Money engine has not surfaced a breakout signal yet.'
          }
        />
      </div>
    </div>
  );
}

export default SmartMoneyOptionsBoard;

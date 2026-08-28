import React from 'react';
import { SignalBoard, DEFAULT_SORT, type ColumnId, type SortState } from './board/SignalBoard';
import { supertrendToBoard } from './board/supertrendAdapter';
import type { BoardSignal } from './board/boardTypes';
import {
  BOARD_COL_TO_SIGNAL, SIGNAL_COL_TO_BOARD, SIGNAL_LEFT_COLUMNS, SIGNAL_RIGHT_COLUMNS,
  signalColGroup, type SignalColKey,
} from './board/signalRowSpec';
import { useKiteSettings } from '../../store/useKiteSettings';
import { KiteActionButtons } from './KiteActionButtons';
import { useOrderWindowStore } from '../../store/useOrderWindowStore';
import type { EngineSignalRow } from '../../types/kiteEngine';

/**
 * SuperTrend's signals, rendered by the shared board.
 *
 * This is the point of the last several commits. Four of the five engines have
 * always rendered through `SignalBoard`; SuperTrend kept a bespoke ~2,700-line
 * table, and every visual difference between the two — the heading scale, the
 * leg shade, the hover, the timestamp, the bold instrument — was a separate
 * thing to notice and fix. Rendering both through one component is what makes
 * that class of difference impossible rather than merely fixed.
 *
 * The three features that used to justify the second implementation are passed
 * in as capabilities, driven by the operator's own settings, so nothing is lost
 * by moving and nobody had to decide for them which ones to drop.
 */
export function SuperTrendSharedBoard({
  rows, quotes, originalEntryMs, spotOf, onSelectSignal, onOpenChart, nowMs,
}: {
  rows: readonly EngineSignalRow[];
  quotes?: Record<string, any>;
  originalEntryMs?: Map<string, number>;
  spotOf?: (underlying: string) => number | null;
  onSelectSignal: (sel: { token: number; underlying: string; timestamp_ms: number; source?: string }) => void;
  /** Tab is narrowed to what the host accepts; widening it here only moves the error. */
  /** Signature narrowed to the host's, so a mismatch surfaces here not there. */
  onOpenChart?: (symbol: string, tab: 'chart') => void;
  nowMs: number;
}) {
  const s = useKiteSettings();
  const openOrderWindow = useOrderWindowStore((st) => st.openOrderWindow);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [sort, setSort] = React.useState<SortState>(DEFAULT_SORT);
  const [collapsed, setCollapsed] = React.useState<ReadonlySet<string>>(new Set());

  const signals = React.useMemo<BoardSignal[]>(
    () => supertrendToBoard(rows, {
      quotes,
      originalEntryMs,
      spotOf,
      // The operator's close-vs-open choice, which this board only reports.
      chgBasis: s.chgType,
    }),
    [rows, quotes, originalEntryMs, spotOf, s.chgType],
  );

  /**
   * Which columns to ask for, in the operator's own order.
   *
   * Read from the SAME persisted order the bespoke table uses, translated into
   * the board's names. Keeping a second order for the shared renderer would mean
   * a column moved in one view and not the other — the exact drift this whole
   * exercise exists to remove.
   */
  const columns = React.useMemo<readonly ColumnId[]>(() => {
    const ordered = [...s.signalLeftColumnOrder, ...s.signalRightColumnOrder]
      .map((key) => SIGNAL_COL_TO_BOARD[key as SignalColKey])
      .filter(Boolean) as ColumnId[];
    // THIS ENGINE'S columns, and only those.
    //
    // The first version asked for the shared list and appended these, which
    // handed SuperTrend five columns it has never had — Engine, Status, Qty, At
    // risk, Score. The shared list exists so the four migrated boards agree with
    // each other; it is not a floor every board has to carry. A board that
    // suddenly grows columns nobody asked for reads as the wrong table.
    //
    // `instrument` leads because it is the row's identity rather than a member
    // of either column run.
    return ['instrument', ...ordered];
  }, [s.signalLeftColumnOrder, s.signalRightColumnOrder]);

  /** The operator's hidden set, in the board's names. */
  const hidden = React.useMemo(
    () => new Set(
      s.hiddenSignalCols
        .map((key) => SIGNAL_COL_TO_BOARD[key as SignalColKey])
        .filter(Boolean) as ColumnId[],
    ),
    [s.hiddenSignalCols],
  );

  /**
   * Reordering writes back to the persisted order, not to local state.
   *
   * A drop is refused across the two runs, as it is on the bespoke table: the
   * right-hand run is pinned past the action buttons, and moving a column
   * between them would put it somewhere the other view cannot represent.
   */
  const onReorderColumn = React.useCallback((fromId: ColumnId, toId: ColumnId) => {
    const from = BOARD_COL_TO_SIGNAL[fromId];
    const to = BOARD_COL_TO_SIGNAL[toId];
    if (!from || !to) return;
    const group = signalColGroup(from);
    if (group !== signalColGroup(to)) return;
    s.reorderSignalColumn(group, from, to);
  }, [s]);

  /**
   * A row's own controls.
   *
   * Only for legs: a parent stands for the idea, and its contracts are what get
   * bought. Offering Buy on the parent would leave the strike ambiguous.
   */
  const renderRowActions = React.useCallback((sig: BoardSignal) => {
    if (sig.children?.length) return null;
    const symbol = sig.instrument.symbol;
    const ended = sig.status === 'ended';
    return (
      <KiteActionButtons
        className="st-actions-persistent"
        onBuy={ended ? undefined : () => openOrderWindow({
          symbol,
          exchange: sig.instrument.exchange,
          initialSide: 'BUY',
          lotSize: sig.instrument.lotSize || 1,
          lastPrice: sig.levels.ltp || 0,
          tag: 'SUPERTREND',
        })}
        onSell={() => openOrderWindow({
          symbol,
          exchange: sig.instrument.exchange,
          initialSide: 'SELL',
          lotSize: sig.instrument.lotSize || 1,
          lastPrice: sig.levels.ltp || 0,
          tag: 'SUPERTREND',
        })}
        onChart={onOpenChart ? () => onOpenChart(sig.instrument.quoteKey ?? symbol, 'chart') : undefined}
      />
    );
  }, [onOpenChart, openOrderWindow]);

  const toggleGroup = React.useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  return (
    <SignalBoard
      signals={signals}
      columns={columns}
      hidden={hidden}
      openId={openId}
      onToggle={(id) => setOpenId((prev) => (prev === id ? null : id))}
      onOpenDetail={(sig) => {
        const row = rows.find((r) => r.underlying === sig.underlying);
        if (row) onSelectSignal({ token: row.token, underlying: row.underlying, timestamp_ms: row.timestamp_ms, source: row.source });
      }}
      sort={sort}
      onSortChange={setSort}
      collapsedGroups={collapsed}
      onToggleGroup={toggleGroup}
      nowMs={nowMs}
      // The three capabilities, from the operator's own Behaviour settings.
      onReorderColumn={s.boardDragColumns ? onReorderColumn : undefined}
      rowScroll={s.boardRowScroll}
      // This board is fifty ideas across several days, and the operator's first
      // question is "what is live", not "what fired today". The bespoke table has
      // always answered that with an Active-now section ahead of the dated log;
      // without this the shared board buries a running trade from Tuesday under
      // days of closed history.
      hoistLiveFromToday
      renderRowActions={s.boardRowActions ? renderRowActions : undefined}
      emptyLabel="No active or recent setups on the board yet."
    />
  );
}

export default SuperTrendSharedBoard;

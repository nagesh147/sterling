import React from 'react';
import { KiteActionButtons } from '../KiteActionButtons';
import { useOrderWindowStore } from '../../../store/useOrderWindowStore';
import type { BoardSignal } from './boardTypes';

/**
 * Buy, Sell and chart for any board row, built from the signal alone.
 *
 * Every engine gets these for free, which is the point. `BoardSignal` already
 * carries what an order needs — the traded symbol, its exchange, the lot size and
 * the last price — so nothing here is engine-specific, and no board has to grow
 * its own copy of the order-window plumbing. SuperTrend had these and the other
 * four did not, purely because SuperTrend's bespoke table happened to be where
 * they were written.
 *
 * They are rendered as COLUMNS by `SignalBoard`, so the column picker can switch
 * them off. That reverses an earlier decision of mine: I had deliberately put the
 * actions outside the cell map so they could not be hidden, on the grounds that
 * losing the trade button by accident is worse than a cluttered row. The operator
 * asked for the choice, and it is theirs to make — a board is read far more often
 * than it is traded from.
 */
export function useBoardRowActions({ onOpenChart }: {
  onOpenChart?: (quoteKey: string) => void;
} = {}) {
  const openOrderWindow = useOrderWindowStore((s) => s.openOrderWindow);

  /**
   * Buy and Sell.
   *
   * A parent row gets nothing: it stands for the idea, and its contracts are what
   * get bought. Offering Buy there would leave the strike ambiguous — which is
   * the one thing an order must never be.
   *
   * An ENDED row keeps both buttons, disabled. Removing them shifts every action
   * after them out of line, and an absent control reads as "no Buy here" rather
   * than "not this row".
   */
  const renderTrade = React.useCallback((signal: BoardSignal): React.ReactNode => {
    if (signal.children?.length) return null;
    const { symbol, exchange, lotSize } = signal.instrument;
    const ended = signal.status === 'ended';
    const order = (side: 'BUY' | 'SELL') => () => openOrderWindow({
      symbol,
      exchange,
      initialSide: side,
      lotSize: lotSize || 1,
      lastPrice: signal.levels.ltp || 0,
      tag: signal.engine.toUpperCase(),
    });
    return (
      <KiteActionButtons
        className="sb-row-trade"
        onBuy={order('BUY')}
        onSell={order('SELL')}
        buyDisabled={ended}
        sellDisabled={ended}
        disabledHint="This row has ended — its levels are a frozen record, not a live plan."
      />
    );
  }, [openOrderWindow]);

  /** The chart for this row's own instrument. */
  const renderChart = React.useCallback((signal: BoardSignal): React.ReactNode => {
    if (!onOpenChart || signal.children?.length) return null;
    const key = signal.instrument.quoteKey
      ?? `${signal.instrument.exchange}:${signal.instrument.symbol}`;
    return <KiteActionButtons className="sb-row-chart" onChart={() => onOpenChart(key)} />;
  }, [onOpenChart]);

  return { renderTrade, renderChart };
}

export default useBoardRowActions;

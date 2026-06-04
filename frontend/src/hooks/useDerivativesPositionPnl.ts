/**
 * useDerivativesPositionPnl — maps a derivatives candidate row to the live P&L of
 * the position it opened, and provides consolidated totals.
 *
 * Candidate freeze_tokens rotate every scan, so we can't match a row to its
 * position by token. Instead we match on the stable identity the position keeps
 * in its notes: underlying + direction (+ strategy when the notes carry it, e.g.
 * auto-exec writes "scalping/price_action"). P&L itself comes from useLivePnl
 * (live unrealized for open positions) or the position's realized_pnl_usd (closed).
 */
import { usePositions } from './usePositions';
import { useLivePnl } from './useLivePnl';

export interface RowPnl {
  pnl: number | null;        // unrealized if open, realized if closed
  realized: boolean;
  status: string;
  mode: string;              // PAPER / LIVE (+·AUTO)
}

export interface DerivativesPnl {
  pnlForRow: (underlying: string, direction: string, strategy?: string) => RowPnl | null;
  totalUnrealized: number;
  totalRealized: number;
  total: number;
  count: number;
  positions: any[];
}

const STRAT_RE = /(?:scalping|edge|triple_st)\/[a-z_]+/;

export function useDerivativesPositionPnl(instrumentType: 'futures' | 'options'): DerivativesPnl {
  const { data: posData } = usePositions();
  const { data: pnlData } = useLivePnl();

  const liveById = new Map((pnlData?.positions ?? []).map((e) => [e.position_id, e]));

  const positions = (posData?.positions ?? []).filter((p) => {
    if (!(p.notes || '').includes('DERIV')) return false;
    const st = liveById.get(p.id)?.structure_type || p.sized_trade?.structure?.structure_type || '';
    return st === instrumentType;
  });

  const isOpen = (s: string) => s === 'open' || s === 'partially_closed';

  const pnlForRow = (underlying: string, direction: string, strategy?: string): RowPnl | null => {
    const matches = positions.filter((p) => {
      if (p.underlying !== underlying) return false;
      const dir = liveById.get(p.id)?.direction || p.sized_trade?.structure?.direction;
      if (dir !== direction) return false;
      const notes = p.notes || '';
      // Only enforce strategy when the position actually recorded one.
      if (strategy && STRAT_RE.test(notes) && !notes.includes(strategy)) return false;
      return true;
    });
    if (matches.length === 0) return null;
    // Prefer an open position; else the most recently touched closed one.
    const pos = matches.find((p) => isOpen(p.status)) ?? matches[matches.length - 1];
    const open = isOpen(pos.status);
    const notes = pos.notes || '';
    const mode = (notes.includes('[LIVE]') ? 'LIVE' : 'PAPER') + (notes.includes('[AUTO]') ? '·AUTO' : '');
    return {
      pnl: open ? (liveById.get(pos.id)?.estimated_pnl_usd ?? null) : (pos.realized_pnl_usd ?? null),
      realized: !open,
      status: pos.status,
      mode,
    };
  };

  let totalUnrealized = 0, totalRealized = 0;
  const mappedPositions = positions.map(p => {
    const lp = liveById.get(p.id);
    const est = lp?.estimated_pnl_usd ?? null;
    if (isOpen(p.status) && est != null) {
      totalUnrealized += est;
    } else if (p.realized_pnl_usd != null) {
      totalRealized += p.realized_pnl_usd;
    }
    return {
      ...p,
      estimated_pnl_usd: est,
    };
  });

  return {
    pnlForRow,
    totalUnrealized,
    totalRealized,
    total: totalUnrealized + totalRealized,
    count: positions.filter(p => isOpen(p.status)).length,
    positions: mappedPositions,
  };
}

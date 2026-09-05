import React, { memo, useEffect, useRef, useState } from 'react';
import { useReplayStore } from '../../../hooks/useReplayStore';
import { HIGH_SPEED_THRESHOLD } from './replaySpeeds';
import {
  ABSENT,
  fmtElapsed,
  fmtInt,
  fmtPct,
  fmtSignedInr,
} from './replayFormat';

type Tone = 'profit' | 'loss' | 'absent' | 'dim' | undefined;

/**
 * Flash a value when it changes, unless the replay is running fast enough that
 * everything changes every frame — at MAX speed the strip would be a strobe.
 */
function useValueFlash(value: string, enabled: boolean): boolean {
  const [on, setOn] = useState(false);
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current === value) return;
    prev.current = value;
    if (!enabled) return;
    setOn(true);
    const t = setTimeout(() => setOn(false), 400);
    return () => clearTimeout(t);
  }, [value, enabled]);
  return on;
}

const Metric = memo(function Metric({
  label,
  value,
  sub,
  tone,
  title,
  flashEnabled,
  hideBelow,
  bar = true,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
  title?: string;
  flashEnabled: boolean;
  hideBelow?: 'lg' | 'md' | 'always';
  /** `false` keeps the metric computed but off the 30px bar. */
  bar?: boolean;
}) {
  const flash = useValueFlash(value, flashEnabled);
  return (
    <div className="rd-metric" title={title} data-hide-below={hideBelow} data-bar={bar}>
      <span className="rd-metric-label">{label}</span>
      <span className="rd-metric-value" data-tone={tone} data-flash={flash || undefined}>
        {value}
      </span>
      {sub && <span className="rd-metric-sub">{sub}</span>}
    </div>
  );
});

/**
 * The KPI strip — visible in every tab, because P&L is why the dock exists.
 *
 * SLIPPAGE renders an em dash when the engine did not model friction. The strip
 * this replaces printed `₹0.00` there unconditionally, which reads as a
 * measurement: a user checking their execution cost was told it was free.
 */
export const ReplayMetricsStrip = memo(function ReplayMetricsStrip() {
  // Scalar selectors only. Subscribing to `s.status` is what made every
  // component in the dock re-render on every status frame.
  const pnl = useReplayStore((s) => s.status.stats.pnl);
  const wins = useReplayStore((s) => s.status.stats.wins);
  const losses = useReplayStore((s) => s.status.stats.losses);
  const signals = useReplayStore((s) => s.status.stats.signals_fired);
  const drag = useReplayStore((s) => s.status.stats.slippage_total);
  const trades = useReplayStore((s) => s.status.stats.trades);
  const elapsed = useReplayStore((s) => s.status.elapsed_real_s);
  const barsPlayed = useReplayStore((s) => s.status.bars_played);
  const speed = useReplayStore((s) => s.status.config?.speed ?? s.draft.speed);
  const openCountSrv = useReplayStore((s) => s.status.open_positions ?? 0);
  const unrealised = useReplayStore((s) => s.status.unrealised_pnl ?? 0);

  const flashEnabled = speed < HIGH_SPEED_THRESHOLD;

  const decided = wins + losses;
  const closed = trades.filter((t) => t.status === 'WIN' || t.status === 'LOSS');
  const openCount = openCountSrv || trades.length - closed.length;
  const winRate = decided > 0 ? (wins / decided) * 100 : null;
  const avg = closed.length ? pnl / closed.length : null;
  const openLots = trades
    .filter((t) => t.status === 'OPEN')
    .reduce((a, t) => a + (t.lots || 0), 0);
  const openQty = trades
    .filter((t) => t.status === 'OPEN')
    .reduce((a, t) => a + (t.quantity || 0), 0);
  const barsPerSec = elapsed > 0 ? barsPlayed / elapsed : null;

  return (
    <div className="rd-metrics" role="region" aria-label="Replay performance" data-testid="replay-metrics">
      <Metric
        label="P&L"
        value={fmtSignedInr(pnl)}
        sub={`${closed.length} closed`}
        tone={pnl >= 0 ? 'profit' : 'loss'}
        flashEnabled={flashEnabled}
      />
      <Metric
        label="Win"
        value={winRate == null ? ABSENT : fmtPct(winRate)}
        sub={`${wins}W · ${losses}L`}
        tone={winRate == null ? 'dim' : winRate >= 50 ? 'profit' : 'loss'}
        title={winRate == null ? 'No trade has closed yet.' : 'Wins as a share of closed trades.'}
        flashEnabled={flashEnabled}
      />
      <Metric
        label="Open"
        value={openCount === 0 ? ABSENT : fmtSignedInr(unrealised)}
        sub={openCount ? `${openCount} open` : undefined}
        tone={openCount === 0 ? 'absent' : unrealised >= 0 ? 'profit' : 'loss'}
        title={
          openCount === 0
            ? 'No position is open, so there is nothing marked to market.'
            : 'Mark-to-market on open positions. Not included in realised P&L.'
        }
        flashEnabled={flashEnabled}
      />
      <Metric
        label="Trades"
        value={fmtInt(trades.length)}
        sub={openCount > 0 ? `${openCount} open` : 'all settled'}
        flashEnabled={flashEnabled}
      />
      <Metric label="Signals" value={fmtInt(signals)} flashEnabled={flashEnabled} />
      <Metric
        label="Avg" bar={false}
        value={avg == null ? ABSENT : fmtSignedInr(avg)}
        tone={avg == null ? 'absent' : avg >= 0 ? 'profit' : 'loss'}
        title={avg == null ? 'No trade has closed yet.' : 'Realized P&L divided by closed trades.'}
        flashEnabled={flashEnabled}
        hideBelow="always"
      />
      <Metric
        label="Exposure" bar={false}
        value={openLots ? `${fmtInt(openLots)}L` : ABSENT}
        sub={openQty ? `${fmtInt(openQty)} qty` : undefined}
        tone={openLots ? undefined : 'absent'}
        title="Lots currently held open."
        flashEnabled={flashEnabled}
        hideBelow="lg"
      />
      {/* The honesty case. `null` means the engine did not model friction; it
          is NOT zero, and it must not be rendered as a number. */}
      <Metric
        label="Slippage" bar={false}
        value={drag == null ? ABSENT : fmtSignedInr(-drag)}
        tone={drag == null ? 'absent' : 'loss'}
        title={
          drag == null
            ? 'This replay did not model execution friction, so there is no drag to report. Enable it in configuration.'
            : 'Spread and slippage deducted from gross P&L.'
        }
        flashEnabled={flashEnabled}
        hideBelow="lg"
      />
      <Metric
        label="Elapsed" bar={false}
        value={fmtElapsed(elapsed)}
        sub={barsPerSec ? `${barsPerSec.toFixed(0)} bars/s` : undefined}
        tone="dim"
        flashEnabled={false}
        hideBelow="lg"
      />
    </div>
  );
});

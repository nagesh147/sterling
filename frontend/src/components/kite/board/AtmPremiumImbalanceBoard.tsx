/**
 * ATM Premium Imbalance, on the shared board.
 *
 * Unlike the scanning engines this one has to be *armed*: it resolves a single
 * ATM pair and subscribes both legs, then waits for the session open. So the
 * board carries the arm control, because an operator looking at an empty board
 * needs the reason and the remedy in the same place.
 *
 * Polling is conditional. An unarmed strategy has no live state, so it is not
 * worth a request every few seconds; once armed the row changes on every tick
 * and a short interval is what makes it readable.
 */
import React from 'react';
import {
  useArmAtmPremiumImbalance,
  useAtmPremiumImbalanceConfig,
  useAtmPremiumImbalanceSnapshot,
  useSimulateAtmPremiumImbalance,
  useStopAtmPremiumImbalanceSimulation,
} from '../../../hooks/useAtmPremiumImbalance';
import { atmPremiumImbalanceToBoard } from './atmPremiumImbalanceAdapter';
import { SignalBoard } from './SignalBoard';
import { BoardFilters } from './BoardFilters';
import { useBoardView } from './useBoardView';
import type { BoardSignal } from './boardTypes';
import { k } from '../../../styles/kiteUI';

const note: React.CSSProperties = {
  padding: '10px 12px', margin: 0, fontSize: 11, color: k.dim, lineHeight: 1.6,
};

export function AtmPremiumImbalanceBoard({ nowMs, onOpenDetail }: {
  nowMs: number;
  onOpenDetail?: (signal: BoardSignal) => void;
}) {
  const config = useAtmPremiumImbalanceConfig();
  const enabled = config.data?.config?.enabled ?? false;
  const [armedOnce, setArmedOnce] = React.useState(false);
  // Poll only while there is live state to poll for.
  const [pollMs, setPollMs] = React.useState(0);
  const snapshot = useAtmPremiumImbalanceSnapshot(true, pollMs);
  const arm = useArmAtmPremiumImbalance();
  const simulate = useSimulateAtmPremiumImbalance();
  const stopSim = useStopAtmPremiumImbalanceSimulation();

  const session = snapshot.data?.session ?? null;
  const sizing = snapshot.data?.sizing ?? null;
  const sim = snapshot.data?.simulation ?? null;
  React.useEffect(() => {
    if (session && !session.finished) setArmedOnce(true);
  }, [session]);
  // A replay changes every second, so it needs the poll even if nothing is armed.
  React.useEffect(() => {
    // 1s while replaying because the point is to watch it move; 3s for a live
    // session, which changes on ticks rather than on a clock we control.
    setPollMs(sim?.running ? 1000 : (armedOnce ? 3000 : 0));
  }, [sim?.running, armedOnce]);

  const signals = React.useMemo(
    () => atmPremiumImbalanceToBoard(snapshot.data),
    [snapshot.data],
  );
  // One session, one row: hiding it once it ends would leave the board blank at
  // exactly the moment there is a result to read.
  const view = useBoardView(signals, { endedByDefault: true });
  const [openId, setOpenId] = React.useState<string | null>(null);

  if (snapshot.isLoading && !snapshot.data) {
    return <p style={note}>Loading ATM Premium Imbalance…</p>;
  }
  if (snapshot.error) {
    return <p style={{ ...note, color: k.red }}>Unavailable: {(snapshot.error as Error).message}</p>;
  }

  const armResult = arm.data;
  const blockers = snapshot.data?.blockers ?? [];

  return (
    <div>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        padding: '8px 12px', borderBottom: `1px solid ${k.border}`,
      }}>
        <button
          type="button"
          onClick={() => arm.mutate()}
          disabled={arm.isPending || !enabled}
          title={enabled
            ? 'Resolve the ATM pair, subscribe both legs and wait for the open'
            : 'Enable the strategy in settings first'}
          style={{
            background: 'transparent',
            border: `1px solid ${enabled ? k.border : k.border}`,
            color: enabled ? k.text : k.dim,
            borderRadius: 6, padding: '4px 10px', fontSize: 11,
            cursor: enabled && !arm.isPending ? 'pointer' : 'not-allowed',
          }}
        >
          {arm.isPending ? 'Arming…' : session && !session.finished ? 'Re-arm' : 'Arm session'}
        </button>

        <button
          type="button"
          onClick={() => (sim?.running ? stopSim.mutate() : simulate.mutate())}
          disabled={simulate.isPending || stopSim.isPending}
          title={sim?.running
            ? 'Stop the replay'
            : 'Replay the last traded session in real time from 09:14 AM IST on real data. '
              + 'Keeps trading until you stop it. Nothing is sent to a broker.'}
          style={{
            background: 'transparent', border: `1px solid ${k.border}`,
            color: sim?.running ? k.amber : k.dim,
            borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer',
          }}
        >
          {simulate.isPending ? 'Starting…'
            : sim?.running ? 'Stop replay' : 'Simulate'}
        </button>

        {session && (
          <span style={{ fontSize: 11, color: k.dim }}>
            {session.underlying} {session.strike ?? '—'} · {session.expiry ?? '—'} ·{' '}
            <strong style={{ color: k.text }}>{session.phase}</strong> ·{' '}
            {session.execution_mode} · qty {session.quantity ?? '—'}
          </span>
        )}
        {!session && !arm.isPending && (
          <span style={{ fontSize: 11, color: k.dim }}>
            Not armed.
            {sizing && sizing.quantity > 0 && (
              // Say what arming would actually buy. "2 lots" is not a number of
              // contracts, and the risk is in the contracts.
              <>
                {' '}Will buy <strong style={{ color: k.text }}>{sizing.quantity}</strong>
                {sizing.mode === 'LOTS' && sizing.lot_size > 0
                  ? ` (${sizing.quantity / sizing.lot_size} × ${sizing.lot_size})`
                  : ''}
                {sizing.max_affordable_premium
                  ? `, premium up to ₹${sizing.max_affordable_premium.toFixed(2)}`
                  : ''}.
              </>
            )}
          </span>
        )}
      </div>

      {sim && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
          padding: '6px 12px', fontSize: 11,
          background: 'color-mix(in srgb, var(--k-amber) 12%, transparent)',
          borderBottom: `1px solid ${k.border}`, color: k.text,
        }}>
          <strong style={{ color: k.amber }}>REPLAY</strong>
          <span>
            {sim.session_date} ·{' '}
            {/* The clock is the thing being watched, so it gets the emphasis. */}
            <strong style={{ color: k.text, fontVariantNumeric: 'tabular-nums' }}>
              {sim.clock_ist ?? '—'}
            </strong>{' '}
            IST{sim.speed === 1 ? '' : ` · ${sim.speed}×`}
          </span>
          <span style={{ color: k.dim }}>
            min {sim.bars_done}/{sim.bars_total}
            {sim.trades ? ` · ${sim.trades} trade${sim.trades === 1 ? '' : 's'}` : ''}
            {sim.continuous ? ' · continuous' : ''} · {sim.note}
          </span>
          <span style={{ color: k.dim, marginLeft: 'auto' }}>
            Real prices, simulated fills — not a backtest.
          </span>
        </div>
      )}
      {sim?.error && (
        <p style={{ ...note, color: k.red }}>Replay failed: {sim.error}</p>
      )}

      {arm.error && (
        <p style={{ ...note, color: k.red }}>Arm failed: {(arm.error as Error).message}</p>
      )}
      {simulate.data && simulate.data.status !== 'started' && (
        <p style={{ ...note, color: k.amber }}>
          Replay not started — {simulate.data.status.replace(/_/g, ' ')}
          {simulate.data.message ? `: ${simulate.data.message}` : ''}.
        </p>
      )}
      {armResult && armResult.status !== 'armed' && armResult.status !== 'already_armed' && (
        <p style={{ ...note, color: k.amber }}>
          Not armed — {armResult.status.replace(/_/g, ' ')}
          {armResult.message ? `: ${armResult.message}` : ''}.
        </p>
      )}

      {!session && blockers.length > 0 && (
        <ul style={{ ...note, paddingLeft: 26 }}>
          {blockers.map((b) => <li key={b}>{b}</li>)}
        </ul>
      )}

      {signals.length > 0 && <BoardFilters view={view} />}
      <SignalBoard
        signals={view.visible}
        requested={['instrument', 'status', 'leg', 'entry', 'target', 'exit', 'ltp', 'time']}
        openId={openId}
        onToggle={(id) => setOpenId((p) => (p === id ? null : id))}
        onOpenDetail={onOpenDetail}
        nowMs={nowMs}
        emptyLabel={session
          ? 'Armed — waiting for both legs to quote.'
          : 'Arm the session to resolve the ATM pair and start watching.'}
      />
    </div>
  );
}

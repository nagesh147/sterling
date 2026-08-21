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
  const snapshot = useAtmPremiumImbalanceSnapshot(true, armedOnce ? 3000 : 0);
  const arm = useArmAtmPremiumImbalance();

  const session = snapshot.data?.session ?? null;
  React.useEffect(() => {
    if (session && !session.finished) setArmedOnce(true);
  }, [session]);

  const signals = React.useMemo(
    () => atmPremiumImbalanceToBoard(snapshot.data),
    [snapshot.data],
  );
  const view = useBoardView(signals);
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

        {session && (
          <span style={{ fontSize: 11, color: k.dim }}>
            {session.underlying} {session.strike ?? '—'} · {session.expiry ?? '—'} ·{' '}
            <strong style={{ color: k.text }}>{session.phase}</strong> ·{' '}
            {session.execution_mode} · qty {session.quantity ?? '—'}
          </span>
        )}
        {!session && !arm.isPending && (
          <span style={{ fontSize: 11, color: k.dim }}>Not armed.</span>
        )}
      </div>

      {arm.error && (
        <p style={{ ...note, color: k.red }}>Arm failed: {(arm.error as Error).message}</p>
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

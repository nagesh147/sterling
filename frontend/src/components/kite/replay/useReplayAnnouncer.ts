import { useEffect, useRef, useState } from 'react';
import { useReplayStore } from '../../../hooks/useReplayStore';
import { fmtSignedInr, fmtTime } from './replayFormat';
import { strategyLabel } from './replayStrategies';

/** At most one announcement per this interval. */
const ANNOUNCE_GAP_MS = 2000;

/**
 * The dock's single polite live region.
 *
 * Throttled and coalescing, because an unthrottled region at replay speed makes
 * a screen reader unusable — at MAX a day's signals arrive in seconds. State
 * transitions bypass the throttle: they are rare and they are exactly what a
 * non-sighted user needs to hear.
 *
 * Progress is NEVER announced.
 */
export function useReplayAnnouncer(): string {
  const [message, setMessage] = useState('');

  const state = useReplayStore((s) => s.status.state);
  const errorMsg = useReplayStore((s) => s.error?.message);
  const events = useReplayStore((s) => s.status.stats.events);
  const speed = useReplayStore((s) => s.status.config?.speed);
  const pnl = useReplayStore((s) => s.status.stats.pnl);
  const trades = useReplayStore((s) => s.status.stats.trades);

  const lastAt = useRef(0);
  const seen = useRef(events.length);
  const prevState = useRef(state);
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);

  /* State transitions — immediate, once each. */
  useEffect(() => {
    if (prevState.current === state) return;
    const was = prevState.current;
    prevState.current = state;
    if (state === 'running') {
      setMessage(was === 'paused' ? 'Replay resumed.' : `Replay running${speed ? ` at ${speed} times speed` : ''}.`);
    } else if (state === 'paused') {
      setMessage('Replay paused.');
    } else if (state === 'loading') {
      setMessage('Loading session data.');
    } else if (state === 'idle' && was !== 'idle') {
      setMessage(
        `Replay complete. ${events.length} signals, ${trades.length} trades, ${fmtSignedInr(pnl)}.`,
      );
    }
    lastAt.current = Date.now();
  }, [state, speed, events.length, trades.length, pnl]);

  useEffect(() => {
    if (errorMsg) setMessage(`Replay error. ${errorMsg}`);
  }, [errorMsg]);

  /* New signals — throttled and coalesced. */
  useEffect(() => {
    if (events.length <= seen.current) {
      seen.current = events.length;   // a seek can shrink the ledger
      return;
    }
    const flush = () => {
      const added = events.length - seen.current;
      if (added <= 0) return;
      seen.current = events.length;
      lastAt.current = Date.now();
      const latest = events[events.length - 1];
      const where = latest ? `${strategyLabel(latest.strategy)} ${latest.instrument} at ${fmtTime(latest.time_iso, 5)}` : '';
      setMessage(
        added === 1
          ? `New signal. ${where}.`
          : `${added} new signals. Latest ${where}.`,
      );
    };

    const wait = ANNOUNCE_GAP_MS - (Date.now() - lastAt.current);
    if (wait <= 0) {
      flush();
      return;
    }
    if (pending.current) return;
    pending.current = setTimeout(() => {
      pending.current = null;
      flush();
    }, wait);
  }, [events]);

  useEffect(() => () => {
    if (pending.current) clearTimeout(pending.current);
  }, []);

  return message;
}

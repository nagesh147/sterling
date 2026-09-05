import { useEffect, useRef } from 'react';
import { useReplayStore } from '../../../hooks/useReplayStore';
import { signalKey } from './replayColumns';
import { fmtInr, fmtTime, isBullish } from './replayFormat';
import { HIGH_SPEED_THRESHOLD } from './replaySpeeds';
import { pushReplayToast } from './replayToastBus';
import { strategyLabel } from './replayStrategies';

/**
 * Raise a toast for each new signal, subject to the bus's rate limit.
 *
 * Suppressed entirely at high speed: nobody reads a toast at 100×, and the
 * metric strip's signal counter already carries the information. The bus
 * coalesces whatever slips through.
 */
export function useReplaySignalToasts() {
  const events = useReplayStore((s) => s.status.stats.events);
  const speed = useReplayStore((s) => s.status.config?.speed ?? s.draft.speed);
  const seen = useRef(events.length);

  useEffect(() => {
    if (events.length <= seen.current) {
      seen.current = events.length;   // a seek truncates the ledger
      return;
    }
    const base = seen.current;
    const fresh = events.slice(base);
    seen.current = events.length;

    if (speed >= HIGH_SPEED_THRESHOLD) return;

    fresh.forEach((ev, i) => {
      const bull = isBullish(ev.direction);
      pushReplayToast({
        kind: 'signal',
        tone: bull ? 'bull' : 'bear',
        title: `Signal · ${fmtTime(ev.time_iso, 5)}`,
        detail: `${strategyLabel(ev.strategy)} · ${ev.contract || ev.instrument}`,
        detail2: `${bull ? 'LONG' : 'SHORT'}  entry ${fmtInr(ev.entry)} → target ${fmtInr(ev.target)}`,
        seekTimeIso: ev.time_iso,
        signalKey: signalKey(ev, base + i),
      });
    });
  }, [events, speed]);
}

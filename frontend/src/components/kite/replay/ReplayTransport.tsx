import React from 'react';
import { useReplayState, useReplayStore } from '../../../hooks/useReplayStore';
import { useReplayTransport } from '../../../hooks/useReplayTransport';
import { REPLAY_SPEEDS, speedLabel } from './replaySpeeds';
import * as Icons from './ReplayIcons';

/** Click and keyboard agree on step size: plain 1, Shift 5, Alt 30. */
export function stepSizeFor(e: { shiftKey: boolean; altKey: boolean }): number {
  if (e.altKey) return 30;
  if (e.shiftKey) return 5;
  return 1;
}

/**
 * Transport cluster and speed ladder.
 *
 * The primary play/pause button is the only filled control in the rail, which
 * is what makes it findable without reading. The speed pills read from
 * `REPLAY_SPEEDS` — the same array the keyboard handler steps through, so
 * `+` can no longer land on a speed that has no button.
 */
export function ReplayTransport() {
  const state = useReplayState();
  const speed = useReplayStore((s) => s.status.config?.speed ?? s.draft.speed);
  const transport = useReplayTransport();

  const canSeek = state === 'running' || state === 'paused';
  const primary =
    state === 'running'
      ? { kind: 'pause' as const, icon: <Icons.Pause size={14} />, label: 'Pause replay (Space)' }
      : state === 'paused'
        ? { kind: 'play' as const, icon: <Icons.Play size={14} />, label: 'Resume replay (Space)' }
        : state === 'error'
          ? { kind: 'retry' as const, icon: <Icons.Play size={14} />, label: 'Retry replay (Space)' }
          : state === 'loading'
            ? { kind: 'play' as const, icon: <Icons.Spinner size={14} />, label: 'Starting replay' }
            : { kind: 'play' as const, icon: <Icons.Play size={14} />, label: 'Start replay (Space)' };

  return (
    <div className="rd-transport" data-testid="replay-transport">
      <div className="rd-transport-seek" data-idle={!canSeek}>
        <button
          type="button"
          className="rd-tbtn"
          disabled={!canSeek}
          onClick={() => void transport.jumpStart()}
          aria-label="Jump to session start (Home)"
          title="Jump to session start (Home)"
        >
          <Icons.SkipStart />
        </button>
        <button
          type="button"
          className="rd-tbtn"
          disabled={!canSeek}
          onClick={(e) => void transport.stepBars(-stepSizeFor(e))}
          aria-label="Step back (Left arrow; Shift 5 bars, Alt 30)"
          title="Step back — 1 bar, Shift 5, Alt 30"
        >
          <Icons.StepBack />
        </button>
      </div>

      <button
        type="button"
        className="rd-tbtn rd-tbtn-primary"
        data-kind={primary.kind}
        disabled={state === 'loading'}
        onClick={() => void transport.toggle()}
        aria-label={primary.label}
        title={primary.label}
        data-testid="replay-primary"
      >
        {primary.icon}
      </button>

      <div className="rd-transport-seek" data-idle={!canSeek}>
        <button
          type="button"
          className="rd-tbtn"
          disabled={!canSeek}
          onClick={(e) => void transport.stepBars(stepSizeFor(e))}
          aria-label="Step forward (Right arrow; Shift 5 bars, Alt 30)"
          title="Step forward — 1 bar, Shift 5, Alt 30"
        >
          <Icons.StepFwd />
        </button>
        <button
          type="button"
          className="rd-tbtn"
          disabled={!canSeek}
          onClick={() => void transport.jumpEnd()}
          aria-label="Jump to session end (End)"
          title="Jump to session end (End)"
        >
          <Icons.SkipEnd />
        </button>
      </div>

      <span className="rd-rail-divider" aria-hidden="true" />

      <button
        type="button"
        className="rd-tbtn"
        data-stop="true"
        disabled={state === 'idle'}
        onClick={() => void transport.stop()}
        aria-label="Stop replay"
        title="Stop replay"
      >
        <Icons.Stop size={12} />
      </button>

      <span className="rd-rail-divider" aria-hidden="true" />

      <div className="rd-speeds" role="group" aria-label="Replay speed">
        {REPLAY_SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            className="rd-speed"
            data-active={speed === s}
            data-max={s >= 5000}
            aria-pressed={speed === s}
            onClick={() => void transport.setSpeed(s)}
            title={`Replay at ${speedLabel(s)} (+ / − to step)`}
          >
            {speedLabel(s)}
          </button>
        ))}
      </div>
    </div>
  );
}

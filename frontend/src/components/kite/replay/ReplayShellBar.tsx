import React from 'react';
import {
  ReplayMode,
  useReplayStore,
  useReplayState,
} from '../../../hooks/useReplayStore';
import { fmtInt, fmtTime } from './replayFormat';
import * as Icons from './ReplayIcons';

const STATE_LABEL: Record<string, string> = {
  idle: 'IDLE',
  loading: 'LOADING',
  running: 'RUNNING',
  paused: 'PAUSED',
  error: 'ERROR',
};

const MODE_LABEL: Record<ReplayMode, string> = {
  docked: 'Docked',
  expanded: 'Filling pane',
  overlay: 'Floating',
  fullscreen: 'Full screen',
};

/**
 * The dock's title bar: identity, live state, clock, progress, window controls.
 *
 * Everything here reads a `--k-*` token. The bar this replaces set the drag
 * grip to a literal `#c2c2c2`, which is invisible against the dark ground.
 */
export function ReplayShellBar() {
  const state = useReplayState();
  const mode = useReplayStore((s) => s.mode);
  const setMode = useReplayStore((s) => s.setMode);
  const setOpen = useReplayStore((s) => s.setOpen);
  const clock = useReplayStore((s) => s.status.current_time_iso);
  const speed = useReplayStore((s) => s.status.config?.speed ?? s.draft.speed);
  const pct = useReplayStore((s) => s.status.progress_pct);
  const barsPlayed = useReplayStore((s) => s.status.bars_played);
  const barsTotal = useReplayStore((s) => s.status.bars_total);
  const message = useReplayStore((s) => s.status.status_message);
  const errorMsg = useReplayStore((s) => s.error?.message);

  const active = state !== 'idle';
  const note = errorMsg || message;

  const toggle = (target: Exclude<ReplayMode, 'docked'>) =>
    setMode(mode === target ? 'docked' : target);

  return (
    <div
      className="rd-shell"
      onDoubleClick={(e) => {
        // Not when the click landed on a control — double-clicking the
        // maximise button should not also toggle the bar's own behaviour.
        if ((e.target as HTMLElement).closest('button')) return;
        setMode(mode === 'expanded' ? 'docked' : 'expanded');
      }}
      title="Double-click to expand or restore"
    >
      <Icons.DragGrip />
      <span className="rd-shell-title">Replay</span>
      <span className="rd-shell-mode">{MODE_LABEL[mode]}</span>

      <span className="rd-state" data-state={state} role="status" data-testid="replay-state">
        {active && <span className="rd-state-prefix">REPLAY ▸</span>}
        {state === 'running' && <span className="rd-pulse" data-pulse />}
        {state === 'loading' && <Icons.Spinner size={10} />}
        {STATE_LABEL[state]}
      </span>

      <span className="rd-shell-clock">
        {fmtTime(clock)} IST · {speed}×
      </span>

      {barsTotal > 0 && (
        <span className="rd-shell-bars" data-testid="replay-bars">
          {fmtInt(barsPlayed)} / {fmtInt(barsTotal)} bars
        </span>
      )}

      <span className="rd-shell-pct">{Math.round(pct)}%</span>

      {/* The backend's only channel for "no candles stored for this date".
          It used to be populated and never rendered, so an empty session was
          inexplicable rather than explained. */}
      {note && (
        <span className="rd-shell-msg" title={note} data-testid="replay-message">
          {note}
        </span>
      )}

    </div>
  );
}

/**
 * Window controls, at the end of the command row.
 *
 * Split out of the identity cluster when the four chrome bands collapsed to
 * two — they belong at the far edge of the row, not adjacent to the title.
 */
export function ReplayWindowControls() {
  const mode = useReplayStore((s) => s.mode);
  const setMode = useReplayStore((s) => s.setMode);
  const setOpen = useReplayStore((s) => s.setOpen);
  const toggle = (target: Exclude<ReplayMode, 'docked'>) =>
    setMode(mode === target ? 'docked' : target);

  return (
      <div className="rd-shell-controls">
        <button
          type="button"
          className="kw-pane-control"
          onClick={() => setOpen(false)}
          aria-label="Minimise replay dock"
          title="Minimise replay dock"
        >
          <Icons.Minimise size={13} />
        </button>
        <span className="rd-shell-divider" aria-hidden="true" />
        <button
          type="button"
          className="kw-pane-control"
          aria-label="Expand replay to fill pane"
          aria-pressed={mode === 'expanded'}
          title="Expand to fill the pane (F)"
          onClick={() => toggle('expanded')}
        >
          <Icons.Expand size={13} />
        </button>
        <button
          type="button"
          className="kw-pane-control"
          aria-label="Float replay over workspace"
          aria-pressed={mode === 'overlay'}
          title="Float over the workspace (F)"
          onClick={() => toggle('overlay')}
        >
          <Icons.Overlay size={13} />
        </button>
        <button
          type="button"
          className="kw-pane-control"
          aria-label="Replay full screen"
          aria-pressed={mode === 'fullscreen'}
          title="Full screen"
          onClick={() => toggle('fullscreen')}
        >
          <Icons.Fullscreen size={13} />
        </button>
      </div>
  );
}

import React from 'react';
import {
  ReplayFocusMode,
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
 * Window controls — the same four the terminal dock has, driving the same
 * `WorkspaceFocus` mechanism.
 *
 * Minimize sends the dock to its footer chip; half, maximize and full screen
 * focus the pane the dock lives in, exactly as `PaneWindow` does. A Restore
 * button appears while focused, and each control reports `aria-pressed` for
 * the focus it owns — so the dock's chrome behaves like every other pane's
 * rather than resembling it.
 */
export function ReplayWindowControls() {
  const setOpen = useReplayStore((s) => s.setOpen);
  const focusMode = useReplayStore((s) => s.hostFocusMode);
  const focusHost = useReplayStore((s) => s.focusHost);
  const clearHostFocus = useReplayStore((s) => s.clearHostFocus);

  const control = (
    kind: 'half' | 'maximize' | 'fullscreen',
    label: string,
    mode: ReplayFocusMode,
    Icon: (p: { size?: number }) => JSX.Element,
  ) => (
    <button
      type="button"
      className="kw-pane-control"
      aria-label={`${label} Market replay`}
      aria-pressed={focusMode === mode}
      title={`${label} Market replay`}
      data-testid={`replay-${kind}`}
      onClick={(e) => {
        e.stopPropagation();
        // Same toggle semantics as the workspace: pressing the active one restores.
        if (focusMode === mode) clearHostFocus();
        else focusHost(mode);
      }}
    >
      <Icon size={13} />
    </button>
  );

  return (
    <div className="rd-shell-controls">
      {focusMode && (
        <button
          type="button"
          className="kw-pane-control"
          aria-label="Restore Market replay"
          title="Restore workspace"
          data-testid="replay-restore"
          onClick={(e) => { e.stopPropagation(); clearHostFocus(); }}
        >
          <Icons.Restore size={13} />
        </button>
      )}
      <button
        type="button"
        className="kw-pane-control"
        aria-label="Minimize Market replay"
        title="Minimize Market replay"
        data-testid="replay-minimize"
        onClick={(e) => { e.stopPropagation(); setOpen(false); }}
      >
        <Icons.Minimise size={13} />
      </button>
      {control('half', 'Half screen', 'half', Icons.Half)}
      {control('maximize', 'Maximize', 'maximized', Icons.Overlay)}
      {control('fullscreen', 'Full screen', 'fullscreen', Icons.Fullscreen)}
    </div>
  );
}

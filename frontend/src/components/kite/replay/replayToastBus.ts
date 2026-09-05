/**
 * A tiny pub/sub for replay toasts.
 *
 * The transport hook needs to raise an error toast, but the toast host lives in
 * a body portal on the other side of the tree. A bus keeps the two from having
 * to know about each other, and keeps the rate limiting in ONE place — at
 * MAX speed a replay can emit thousands of signals, and a host that renders one
 * toast per signal is unusable.
 */

export type ReplayToastKind = 'signal' | 'trade' | 'state' | 'error';
export type ReplayToastTone = 'bull' | 'bear' | 'info' | 'error';

export interface ReplayToastInput {
  kind: ReplayToastKind;
  tone: ReplayToastTone;
  title: string;
  detail: string;
  detail2?: string;
  sticky?: boolean;
  /** Seek target, so clicking the toast moves the timeline to the signal. */
  seekTimeIso?: string;
  signalKey?: string;
  action?: { label: string; run: () => void };
}

export interface ReplayToast extends ReplayToastInput {
  id: string;
  at: number;
}

type Listener = (toast: ReplayToast) => void;

const listeners = new Set<Listener>();
let seq = 0;

/** Hard floor between two rendered toasts. Beyond it, they coalesce. */
export const TOAST_MIN_GAP_MS = 800;

let lastEmittedAt = 0;
let suppressed = 0;
let coalesceTimer: ReturnType<typeof setTimeout> | null = null;

export function subscribeReplayToasts(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(input: ReplayToastInput, at: number) {
  const toast: ReplayToast = { ...input, id: `rt-${++seq}`, at };
  lastEmittedAt = at;
  listeners.forEach((fn) => fn(toast));
}

/**
 * Raise a toast, subject to the rate limit.
 *
 * Errors and state changes bypass it — they are rare and the user needs them.
 * Signals and trades are throttled and coalesced into "n new signals".
 */
export function pushReplayToast(input: ReplayToastInput, now = Date.now()): void {
  if (input.kind === 'error' || input.kind === 'state') {
    emit(input, now);
    return;
  }

  if (now - lastEmittedAt >= TOAST_MIN_GAP_MS) {
    emit(input, now);
    return;
  }

  suppressed += 1;
  if (coalesceTimer) return;
  coalesceTimer = setTimeout(() => {
    const n = suppressed;
    suppressed = 0;
    coalesceTimer = null;
    if (n > 0) {
      emit(
        {
          kind: input.kind,
          tone: 'info',
          title: input.kind === 'trade' ? 'Trades' : 'Signals',
          detail: `${n} more ${input.kind === 'trade' ? 'trade' : 'signal'}${n === 1 ? '' : 's'}`,
        },
        Date.now(),
      );
    }
  }, TOAST_MIN_GAP_MS);
}

/** Test seam — the module-level throttle state outlives a component. */
export function resetReplayToastBus(): void {
  lastEmittedAt = 0;
  suppressed = 0;
  if (coalesceTimer) clearTimeout(coalesceTimer);
  coalesceTimer = null;
  seq = 0;
}

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ReplayToast,
  TOAST_MIN_GAP_MS,
  pushReplayToast,
  resetReplayToastBus,
  subscribeReplayToasts,
} from '../replayToastBus';

function collect() {
  const out: ReplayToast[] = [];
  const off = subscribeReplayToasts((t) => out.push(t));
  return { out, off };
}

beforeEach(() => {
  resetReplayToastBus();
  vi.useFakeTimers();
});

describe('rate limiting', () => {
  it('lets the first signal through', () => {
    const { out, off } = collect();
    pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: 'NIFTY' }, 10_000);
    expect(out).toHaveLength(1);
    off();
  });

  it('coalesces a burst into one follow-up rather than one toast each', () => {
    // At MAX speed a day's signals arrive in seconds; a toast per signal is
    // unusable, and it is the reason toasts are suppressed above 100x too.
    const { out, off } = collect();
    for (let i = 0; i < 50; i += 1) {
      pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: `S${i}` }, 10_000);
    }
    expect(out).toHaveLength(1);

    vi.advanceTimersByTime(TOAST_MIN_GAP_MS + 10);
    expect(out).toHaveLength(2);
    expect(out[1].detail).toBe('49 more signals');
    off();
  });

  it('pluralises a single coalesced item correctly', () => {
    const { out, off } = collect();
    pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: 'A' }, 10_000);
    pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: 'B' }, 10_000);
    vi.advanceTimersByTime(TOAST_MIN_GAP_MS + 10);
    expect(out[1].detail).toBe('1 more signal');
    off();
  });

  it('lets a signal through again once the gap has passed', () => {
    const { out, off } = collect();
    pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: 'A' }, 10_000);
    pushReplayToast({ kind: 'signal', tone: 'bull', title: 'Signal', detail: 'B' }, 10_000 + TOAST_MIN_GAP_MS);
    expect(out).toHaveLength(2);
    expect(out[1].detail).toBe('B');
    off();
  });
});

describe('bypasses', () => {
  it('never throttles an error', () => {
    // A swallowed failure is the defect this whole path exists to fix.
    const { out, off } = collect();
    pushReplayToast({ kind: 'error', tone: 'error', title: 'Replay error', detail: 'A', sticky: true }, 10_000);
    pushReplayToast({ kind: 'error', tone: 'error', title: 'Replay error', detail: 'B', sticky: true }, 10_000);
    expect(out).toHaveLength(2);
    off();
  });

  it('never throttles a state change', () => {
    const { out, off } = collect();
    pushReplayToast({ kind: 'state', tone: 'info', title: 'Replay', detail: 'A' }, 10_000);
    pushReplayToast({ kind: 'state', tone: 'info', title: 'Replay', detail: 'B' }, 10_000);
    expect(out).toHaveLength(2);
    off();
  });

  it('carries a retry action through untouched', () => {
    const { out, off } = collect();
    const run = vi.fn();
    pushReplayToast(
      { kind: 'error', tone: 'error', title: 'Replay error', detail: 'boom', sticky: true, action: { label: 'Retry', run } },
      10_000,
    );
    out[0].action!.run();
    expect(run).toHaveBeenCalledOnce();
    off();
  });
});

describe('subscription', () => {
  it('stops delivering after unsubscribe', () => {
    const { out, off } = collect();
    off();
    pushReplayToast({ kind: 'error', tone: 'error', title: 'X', detail: 'Y' }, 10_000);
    expect(out).toHaveLength(0);
  });

  it('gives every toast a distinct id', () => {
    const { out, off } = collect();
    pushReplayToast({ kind: 'state', tone: 'info', title: 'A', detail: 'A' }, 10_000);
    pushReplayToast({ kind: 'state', tone: 'info', title: 'B', detail: 'B' }, 10_000);
    expect(out[0].id).not.toBe(out[1].id);
    off();
  });
});

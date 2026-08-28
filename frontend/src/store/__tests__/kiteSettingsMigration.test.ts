/**
 * The persisted signal-column order, when a new column is added.
 *
 * Adding `time` to the defaults is not enough on its own. This order lives in
 * localStorage, so every operator who has already opened the app has a stored
 * array that predates the column — they would get the new default only after
 * clearing site data, and until then the column simply would not exist for
 * them. That is a silent failure: the code looks correct and the column is
 * missing on exactly the machines that matter.
 *
 * So the migration has to add it, and it has to do so without discarding a
 * column arrangement the operator set up themselves.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

const KEY = 'kite-settings';

/**
 * Load the store fresh so `persist` re-reads localStorage and runs `migrate`.
 *
 * Returns a SNAPSHOT. Actions on it work, but the snapshot does not update — so
 * a test that calls an action and then reads the same object back sees the old
 * value. Use `loadHook` when the test needs to observe a change.
 */
async function loadStore() {
  return (await loadHook()).getState();
}

/** The store itself, for tests that act and then re-read. */
async function loadHook() {
  vi.resetModules();
  return (await import('../useKiteSettings')).useKiteSettings;
}

function seed(version: number, state: Record<string, unknown>) {
  localStorage.setItem(KEY, JSON.stringify({ version, state }));
}

describe('kite-settings migration', () => {
  beforeEach(() => localStorage.clear());

  it('adds the Time column to an order stored before it existed', async () => {
    seed(3, { signalRightColumnOrder: ['chg', 'chgPct', 'dir', 'ltp'] });
    const s = await loadStore();
    expect(s.signalRightColumnOrder).toContain('time');
  });

  it('keeps the operator’s own arrangement, appending rather than resetting', async () => {
    // Someone who moved LTP to the front must not have that undone.
    seed(3, { signalRightColumnOrder: ['ltp', 'dir', 'chg'] });
    const s = await loadStore();
    expect(s.signalRightColumnOrder).toEqual(['ltp', 'dir', 'chg', 'time']);
  });

  it('does not add a second copy when the column is already there', async () => {
    seed(4, { signalRightColumnOrder: ['chg', 'ltp', 'time'] });
    const s = await loadStore();
    expect(s.signalRightColumnOrder.filter((c) => c === 'time')).toHaveLength(1);
  });

  it('still repairs a legacy loaderStyle, which v3 existed to do', async () => {
    // The migration was rewritten to fall through to the v4 step instead of
    // returning early. That rewrite must not drop what v3 was for.
    seed(2, { loaderStyle: 'classic', signalRightColumnOrder: ['ltp'] });
    const s = await loadStore();
    expect(s.loaderStyle).toBe('material');
    expect(s.signalRightColumnOrder).toEqual(['ltp', 'time']);
  });

  it('gives a fresh install the column without needing a migration', async () => {
    const s = await loadStore();
    expect(s.signalRightColumnOrder).toContain('time');
  });

  /**
   * v5 adds the three board capabilities.
   *
   * This is the same trap as the Time column but worse. A stored state that
   * predates these keys has them absent, and `undefined` is falsy — so without a
   * migration every existing user would open the app to find column dragging,
   * sideways row scrolling and the in-row order buttons all switched off, having
   * chosen nothing. The order buttons are the trade path.
   */
  it('turns the board capabilities on for a state saved before they existed', async () => {
    seed(4, { signalRightColumnOrder: ['ltp', 'time'] });
    const s = await loadStore();
    expect(s.boardDragColumns).toBe(true);
    expect(s.boardRowScroll).toBe(true);
    expect(s.boardRowActions, 'the order buttons must not vanish').toBe(true);
  });

  it('respects a capability the operator has deliberately switched off', async () => {
    seed(5, { boardRowActions: false, boardDragColumns: true, boardRowScroll: true });
    const s = await loadStore();
    expect(s.boardRowActions, 'false is a choice, not a missing key').toBe(false);
    expect(s.boardDragColumns).toBe(true);
  });

  it('resets all three when the board view is reset', async () => {
    const store = await loadHook();
    store.getState().toggleBoardCapability('boardRowActions');
    store.getState().toggleBoardCapability('boardDragColumns');
    expect(store.getState().boardRowActions).toBe(false);
    expect(store.getState().boardDragColumns).toBe(false);

    store.getState().resetSignalTableSettings();
    expect(store.getState().boardRowActions).toBe(true);
    expect(store.getState().boardDragColumns).toBe(true);
    expect(store.getState().boardRowScroll).toBe(true);
  });
});

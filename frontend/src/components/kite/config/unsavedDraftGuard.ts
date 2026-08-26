import React from 'react';

/**
 * Tracks whether any settings panel is holding an unapplied draft.
 *
 * The settings hub renders exactly one section at a time, so moving between
 * sections UNMOUNTS the panel and its draft goes with it — silently, with no
 * prompt. That was harmless when every control wrote through immediately, but
 * the rework made these pages draft-and-Apply, so a click on the rail can now
 * throw away a page of edits the user believes are pending.
 *
 * The draft itself lives inside each panel (it is the panel's business), so the
 * hub cannot inspect it. This is the smallest thing that closes the gap: panels
 * announce "I am dirty", the hub asks before navigating away.
 *
 * Module-level rather than context because the hub and the panels are siblings in
 * the tree, not parent and child, and one boolean does not justify a provider.
 */
const dirtyOwners = new Set<string>();

export function setDraftDirty(owner: string, dirty: boolean): void {
  if (dirty) dirtyOwners.add(owner);
  else dirtyOwners.delete(owner);
}

export function hasUnsavedDraft(): boolean {
  return dirtyOwners.size > 0;
}

/** Test helper — the set outlives any single render. */
export function resetDraftGuard(): void {
  dirtyOwners.clear();
}

/**
 * Report this panel's dirty state for as long as it is mounted.
 *
 * Clears on unmount so a panel that has already gone away cannot keep blocking
 * navigation — by then the draft is lost anyway and there is nothing to protect.
 */
export function useUnsavedDraftGuard(owner: string, dirty: boolean): void {
  React.useEffect(() => {
    setDraftDirty(owner, dirty);
  }, [owner, dirty]);

  React.useEffect(() => () => setDraftDirty(owner, false), [owner]);
}

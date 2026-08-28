import React from 'react';
import { createPortal } from 'react-dom';
import type { WorkspacePaneId } from './workspaceLayout';

/**
 * Puts a pane's own actions into that pane's title bar, beside minimize.
 *
 * Rescan and the signal-table settings used to sit at the right edge of the
 * engine toolbar, one row *below* the pane title bar that already carries
 * minimize, half, maximize and full screen. Two rows of right-aligned icons
 * stacked on top of each other, and the ones you reach for most were the lower
 * pair.
 *
 * Threading them up as props would mean passing them through everything between
 * the engine and the layout, none of which has any business knowing about a
 * rescan button. So the layout publishes a slot and the engine fills it: the
 * buttons stay owned by the component that knows how to run them, and the title
 * bar decides where they sit.
 *
 * **It falls back to rendering in place.** If no slot exists — the Mac stage
 * layout, a test rendering the pane on its own, a future layout that drops the
 * title bar — the actions appear where they are declared rather than vanishing.
 * A control that silently disappears because its host moved is worse than one in
 * the wrong place.
 */
export function paneActionsSlotId(pane: WorkspacePaneId): string {
  return `kw-pane-actions-${pane}`;
}

export function PaneHeaderActions(
  { pane, children }: { pane: WorkspacePaneId; children: React.ReactNode },
) {
  const [host, setHost] = React.useState<HTMLElement | null>(null);

  // The slot is rendered by the layout, so it may not exist on this component's
  // first paint. An effect re-checks after mount; without that the fallback
  // would win the race and the actions would render in the old place.
  React.useEffect(() => {
    const find = () => setHost(document.getElementById(paneActionsSlotId(pane)));
    find();
    // Panes are minimized, restored and re-mounted by the workspace, so the slot
    // comes and goes. Watching the document is cheaper than guessing a delay.
    const observer = new MutationObserver(find);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [pane]);

  if (!host) return <>{children}</>;
  return createPortal(children, host);
}

export default PaneHeaderActions;

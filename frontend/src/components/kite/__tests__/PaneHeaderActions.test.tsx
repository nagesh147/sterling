/**
 * Pane actions in the pane's own title bar.
 *
 * Rescan and the signal-table settings used to sit at the right edge of the
 * engine toolbar — one row below the title bar that already carries minimize,
 * half, maximize and full screen. Two stacked rows of right-aligned icons, with
 * the pair reached for during a session in the lower one.
 *
 * The property worth holding is the fallback. These are the controls that rescan
 * the board and open its settings; if the slot is ever absent they must appear
 * where they were declared rather than vanish, because a control that silently
 * disappears when its host moves is worse than one in the wrong place.
 */
import React from 'react';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { PaneHeaderActions, paneActionsSlotId } from '../PaneHeaderActions';

afterEach(() => {
  cleanup();
  document.body.innerHTML = '';
});

describe('PaneHeaderActions', () => {
  it('renders in place when the pane has no slot', () => {
    render(
      <div data-testid="declared">
        <PaneHeaderActions pane="signals"><button type="button">Rescan</button></PaneHeaderActions>
      </div>,
    );
    // Present, and still inside where it was declared.
    expect(screen.getByText('Rescan')).toBeInTheDocument();
    expect(screen.getByTestId('declared')).toContainElement(screen.getByText('Rescan'));
  });

  it('moves into the slot when the layout provides one', async () => {
    const slot = document.createElement('span');
    slot.id = paneActionsSlotId('signals');
    document.body.appendChild(slot);

    render(
      <div data-testid="declared">
        <PaneHeaderActions pane="signals"><button type="button">Rescan</button></PaneHeaderActions>
      </div>,
    );

    const button = await screen.findByText('Rescan');
    expect(slot).toContainElement(button);
    // ...and no longer where it was declared.
    expect(screen.getByTestId('declared')).not.toContainElement(button);
  });

  it('targets its own pane, not whichever slot exists', () => {
    const other = document.createElement('span');
    other.id = paneActionsSlotId('terminal');
    document.body.appendChild(other);

    render(<PaneHeaderActions pane="signals"><button type="button">Rescan</button></PaneHeaderActions>);
    // A terminal slot must not capture the signals pane's actions.
    expect(other).not.toContainElement(screen.getByText('Rescan'));
  });
});

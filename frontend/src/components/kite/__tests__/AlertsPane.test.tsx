import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { AlertsPane } from '../AlertsPane';

let mockAlerts: any[] = [];
vi.mock('../../../hooks/useKite', () => ({
  useKiteAlerts: () => ({ data: mockAlerts }),
  useKiteAlertHistory: () => ({ data: [] }),
}));

vi.mock('../CreateAlertModal', () => ({ CreateAlertModal: () => null }));
vi.mock('../EditAlertModal', () => ({
  EditAlertModal: ({ alert }: { alert: any }) => <div data-testid="edit-alert-modal">{alert.uuid}</div>,
}));

const alert1 = { uuid: 'a1', name: 'INFY above 1600', rhs_constant: 1600, status: 'enabled' };

beforeEach(() => {
  mockAlerts = [alert1];
});

describe('AlertsPane auto-close on stale target', () => {
  it('opens the edit modal for the clicked alert row', () => {
    render(<AlertsPane />);
    fireEvent.click(screen.getByText('INFY above 1600'));
    expect(screen.getByTestId('edit-alert-modal')).toHaveTextContent('a1');
  });

  it('closes the edit modal if the open alert disappears from the live list (deleted/triggered-and-removed elsewhere)', async () => {
    const { rerender } = render(<AlertsPane />);
    fireEvent.click(screen.getByText('INFY above 1600'));
    expect(screen.getByTestId('edit-alert-modal')).toBeInTheDocument();

    mockAlerts = [];
    rerender(<AlertsPane />);

    await waitFor(() => expect(screen.queryByTestId('edit-alert-modal')).not.toBeInTheDocument());
  });

  it('does not touch the modal state on initial mount when nothing is open', () => {
    render(<AlertsPane />);
    expect(screen.queryByTestId('edit-alert-modal')).not.toBeInTheDocument();
  });
});

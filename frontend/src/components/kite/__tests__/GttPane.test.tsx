import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { GttPane } from '../GttPane';

let mockGtts: any[] = [];
vi.mock('../../../hooks/useKite', () => ({
  useKiteGtts: () => ({ data: mockGtts }),
}));

// GttPane only needs to know an options modal is open/closed for this test —
// stub out the real modals so we don't have to also mock
// useModifyKiteGtt/useDeleteKiteGtt/create-form internals.
vi.mock('../CreateGttModal', () => ({ CreateGttModal: () => null }));
vi.mock('../GttOptionsModal', () => ({
  GttOptionsModal: ({ gtt }: { gtt: any }) => <div data-testid="gtt-options-modal">{gtt.id}</div>,
}));

const activeGtt = { id: 1, type: 'single', status: 'active', condition: { tradingsymbol: 'INFY', exchange: 'NSE' } };

beforeEach(() => {
  mockGtts = [activeGtt];
});

describe('GttPane auto-close on stale target', () => {
  it('opens the options modal for the clicked GTT', () => {
    render(<GttPane />);
    fireEvent.click(screen.getByText('Options'));
    expect(screen.getByTestId('gtt-options-modal')).toHaveTextContent('1');
  });

  it('closes the options modal if the open GTT disappears from the live list (deleted elsewhere)', async () => {
    const { rerender } = render(<GttPane />);
    fireEvent.click(screen.getByText('Options'));
    expect(screen.getByTestId('gtt-options-modal')).toBeInTheDocument();

    mockGtts = [];
    rerender(<GttPane />);

    await waitFor(() => expect(screen.queryByTestId('gtt-options-modal')).not.toBeInTheDocument());
  });

  it('closes the options modal if the open GTT is no longer active (e.g. it triggered) since it was opened', async () => {
    const { rerender } = render(<GttPane />);
    fireEvent.click(screen.getByText('Options'));
    expect(screen.getByTestId('gtt-options-modal')).toBeInTheDocument();

    mockGtts = [{ ...activeGtt, status: 'triggered' }];
    rerender(<GttPane />);

    await waitFor(() => expect(screen.queryByTestId('gtt-options-modal')).not.toBeInTheDocument());
  });

  it('does not touch the modal state on initial mount when nothing is open', () => {
    render(<GttPane />);
    expect(screen.queryByTestId('gtt-options-modal')).not.toBeInTheDocument();
  });
});

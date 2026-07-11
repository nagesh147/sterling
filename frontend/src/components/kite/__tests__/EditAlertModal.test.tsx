import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { EditAlertModal } from '../EditAlertModal';

const mockModify = vi.fn();
const mockDelete = vi.fn();
vi.mock('../../../hooks/useKite', () => ({
  useModifyKiteAlert: () => ({ mutate: mockModify, isPending: false }),
  useDeleteKiteAlerts: () => ({ mutate: mockDelete, isPending: false }),
}));

const alert = { uuid: 'a1', name: 'INFY above 1600', rhs_constant: 1600, status: 'enabled' };

describe('EditAlertModal', () => {
  beforeEach(() => {
    mockModify.mockClear();
    mockDelete.mockClear();
  });

  it('prefills the threshold', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    expect(screen.getByDisplayValue('1600')).toBeInTheDocument();
  });

  it('submits the edited threshold', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1600'), { target: { value: '1650' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).toHaveBeenCalledWith(expect.objectContaining({ uuid: 'a1', rhs_constant: 1650 }), expect.anything());
  });

  it('deletes with confirmation', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(mockDelete).toHaveBeenCalledWith(['a1'], expect.anything());
    vi.restoreAllMocks();
  });

  it('requires confirmation before deleting', () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.click(screen.getByText('Delete'));
    expect(confirmSpy).toHaveBeenCalled();
    expect(mockDelete).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('shows a validation error when the threshold is zero', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1600'), { target: { value: '0' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a threshold value')).toBeInTheDocument();
  });

  it('shows a validation error when the threshold is empty', () => {
    render(<EditAlertModal alert={alert} onClose={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue('1600'), { target: { value: '' } });
    fireEvent.click(screen.getByText('Save changes'));
    expect(mockModify).not.toHaveBeenCalled();
    expect(screen.getByText('Enter a threshold value')).toBeInTheDocument();
  });
});

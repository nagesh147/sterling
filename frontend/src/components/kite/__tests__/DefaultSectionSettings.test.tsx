import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { DefaultSectionSettings } from '../DefaultSectionSettings';
import { useKiteSettings } from '../../../store/useKiteSettings';

describe('DefaultSectionSettings', () => {
  beforeEach(() => {
    useKiteSettings.setState({ defaultSection: 'dashboard' });
  });

  it('renders section title and default selection', () => {
    render(<DefaultSectionSettings />);
    expect(screen.getByText(/DEFAULT PAGE LOAD SECTION/i)).toBeInTheDocument();

    const dashboardRadio = screen.getByLabelText(/Dashboard/i) as HTMLInputElement;
    expect(dashboardRadio.checked).toBe(true);
  });

  it('allows user to change the default section to positions', () => {
    render(<DefaultSectionSettings />);

    const positionsRadio = screen.getByLabelText(/Positions/i) as HTMLInputElement;
    fireEvent.click(positionsRadio);
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));

    expect(useKiteSettings.getState().defaultSection).toBe('positions');
  });

  it('allows user to change the default section to orders', () => {
    render(<DefaultSectionSettings />);

    const ordersRadio = screen.getByLabelText(/Orders/i) as HTMLInputElement;
    fireEvent.click(ordersRadio);
    fireEvent.click(screen.getByRole('button', { name: /Apply changes/i }));

    expect(useKiteSettings.getState().defaultSection).toBe('orders');
  });
});


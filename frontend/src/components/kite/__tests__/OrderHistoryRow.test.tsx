import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { OrderHistoryRow } from '../OrderHistoryRow';

vi.mock('../../../hooks/useKite', () => ({
  useKiteOrderHistory: () => ({ data: [{ status: 'OPEN', order_timestamp: '2026-07-11 09:15:01' }, { status: 'COMPLETE', order_timestamp: '2026-07-11 09:15:03' }] }),
  useKiteOrderTrades: () => ({ data: [{ quantity: 10, average_price: 1500.5, fill_timestamp: '2026-07-11 09:15:03' }] }),
}));

function renderRow() {
  return render(
    <table>
      <tbody>
        <OrderHistoryRow orderId="o1" colSpan={8} />
      </tbody>
    </table>,
  );
}

describe('OrderHistoryRow', () => {
  it('renders each history status transition', () => {
    renderRow();
    expect(screen.getByText('OPEN')).toBeInTheDocument();
    expect(screen.getByText('COMPLETE')).toBeInTheDocument();
  });

  it('renders fill trades', () => {
    renderRow();
    expect(screen.getByText(/1500.50/)).toBeInTheDocument();
  });
});

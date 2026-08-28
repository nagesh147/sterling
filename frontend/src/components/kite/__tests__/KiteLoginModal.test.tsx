/**
 * The login handshake, shown in the app.
 *
 * The login itself must happen on Zerodha's page — their 2FA is interactive by
 * design and cannot be embedded (their headers forbid framing, and so do ours).
 * So this component is not the login; it is the app saying what is happening
 * while a popup does it, instead of leaving the operator on an unchanged screen
 * wondering whether the click registered.
 *
 * The property worth defending: there is NO field to paste a `request_token`
 * into. That token is single-use and already spent by the callback by the time it
 * is visible in the popup's address bar, so a paste box could only ever hand
 * back something guaranteed to be rejected — which is exactly the dead end this
 * replaces.
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { KiteLoginModal } from '../KiteLoginModal';

const props = {
  phase: 'waiting' as const,
  error: null,
  onRetry: vi.fn(),
  onDismiss: vi.fn(),
};

describe('KiteLoginModal', () => {
  it('renders nothing when no login is in flight', () => {
    const { container } = render(<KiteLoginModal {...props} phase="idle" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('never offers a token field', () => {
    render(<KiteLoginModal {...props} />);
    expect(document.querySelector('input'), 'no paste box').toBeNull();
    expect(screen.getByText(/no token to copy/i)).toBeInTheDocument();
  });

  it('says what is happening while the operator is on Kite', () => {
    render(<KiteLoginModal {...props} />);
    expect(screen.getByText('Waiting for Kite')).toBeInTheDocument();
  });

  it('cannot be dismissed mid-handshake', () => {
    // Closing while the popup is open would orphan it with nothing listening.
    const onDismiss = vi.fn();
    render(<KiteLoginModal {...props} onDismiss={onDismiss} />);
    const close = screen.getByRole('button', { name: 'Close' });
    expect(close).toBeDisabled();
    fireEvent.click(close);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it('confirms success and says there is nothing left to do', () => {
    render(<KiteLoginModal {...props} phase="done" />);
    expect(screen.getByText('Connected to Kite')).toBeInTheDocument();
    expect(screen.getByText(/Nothing else to do/i)).toBeInTheDocument();
  });

  it('offers a fresh login on failure, not a paste', () => {
    const onRetry = vi.fn();
    render(<KiteLoginModal {...props} phase="failed" error="The Kite window closed early." onRetry={onRetry} />);
    expect(screen.getByText('The Kite window closed early.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalled();
    expect(document.querySelector('input'), 'still no paste box').toBeNull();
  });

  it('is dismissible once it has finished, either way', () => {
    for (const phase of ['done', 'failed'] as const) {
      const onDismiss = vi.fn();
      const view = render(<KiteLoginModal {...props} phase={phase} onDismiss={onDismiss} />);
      fireEvent.keyDown(window, { key: 'Escape' });
      expect(onDismiss, phase).toHaveBeenCalled();
      view.unmount();
    }
  });

  it('announces itself as a dialog', () => {
    render(<KiteLoginModal {...props} />);
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true');
  });
});

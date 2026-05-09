import React, { ReactNode } from 'react';

interface State { error: Error | null; errorInfo: string }
interface Props { children: ReactNode }

const SESSION_KEYS_TO_CLEAR = [
  'sterling_signal_feed_v2', 'sterling_signal_states_v2',
  'sterling_signal_feed',    'sterling_signal_states',
  'sterling_alert_state_BTC', 'sterling_alert_state_ETH',
  'sterling_alert_state_SOL', 'sterling_alert_state_XRP',
];

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null, errorInfo: '' };

  static getDerivedStateFromError(error: Error): State {
    // Clear all potentially corrupted sessionStorage keys so next retry is clean
    try {
      SESSION_KEYS_TO_CLEAR.forEach(k => sessionStorage.removeItem(k));
    } catch { /* ignore quota errors */ }
    return { error, errorInfo: '' };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[Sterling crash]', error.message, info.componentStack?.slice(0, 300));
    this.setState({ errorInfo: info.componentStack?.slice(0, 200) ?? '' });
  }

  handleRetry = () => {
    // Also clear sessionStorage before retry
    try {
      SESSION_KEYS_TO_CLEAR.forEach(k => sessionStorage.removeItem(k));
    } catch { /* ignore */ }
    this.setState({ error: null, errorInfo: '' });
  };

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: '100vh', gap: 12,
          background: 'var(--bg)', color: 'var(--danger)',
          fontFamily: 'inherit', padding: 32,
        }}>
          <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: 2 }}>RUNTIME ERROR</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, maxWidth: 500, textAlign: 'center' }}>
            {this.state.error.message}
          </div>
          {this.state.errorInfo && (
            <pre style={{
              color: 'var(--text-faint)', fontSize: 9, maxWidth: 600,
              overflow: 'auto', maxHeight: 120, background: 'var(--bg-card)',
              padding: '8px 10px', borderRadius: 4, border: '1px solid var(--border)',
            }}>
              {this.state.errorInfo}
            </pre>
          )}
          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button
              onClick={this.handleRetry}
              style={{
                background: 'var(--bg-card)', color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                padding: '8px 20px', borderRadius: 4, cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 12,
              }}
            >
              RETRY (session cleared)
            </button>
            <button
              onClick={() => window.location.reload()}
              style={{
                background: 'var(--bg-card)', color: 'var(--accent)',
                border: '1px solid var(--accent)',
                padding: '8px 20px', borderRadius: 4, cursor: 'pointer',
                fontFamily: 'inherit', fontSize: 12,
              }}
            >
              HARD RELOAD
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

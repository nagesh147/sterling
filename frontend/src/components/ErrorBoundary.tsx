import React, { ReactNode } from 'react';

interface State { error: Error | null }
interface Props { children: ReactNode }

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: '100vh',
          background: '#0d0d0d', color: '#cc4444', fontFamily: 'Courier New, monospace',
        }}>
          <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 12 }}>RUNTIME ERROR</div>
          <div style={{ color: '#888', fontSize: 13, marginBottom: 20 }}>
            {this.state.error.message}
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              background: '#1a1a1a', color: '#888', border: '1px solid #333',
              padding: '8px 20px', borderRadius: 4, cursor: 'pointer',
              fontFamily: 'inherit', fontSize: 12,
            }}
          >
            RETRY
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
